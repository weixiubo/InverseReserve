"""Response-conditioned spatial-visual search used by RC-RPS development."""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass
from typing import Any, Callable

from .interface import PreviewObservation, QueryEvent


@dataclass(frozen=True)
class KernelConfig:
    descriptor: str
    spatial_length_scale: float
    visual_weight: float
    visual_cosine_power: int


@dataclass(frozen=True)
class GeometryConfig:
    initial_seed_budget: int
    maximum_local_points_per_positive_basin: int
    trace_step_pixels: int


def pairwise_distance(left: Any, right: Any) -> Any:
    import numpy as np

    difference = left[:, None, :] - right[None, :, :]
    return np.sqrt(np.maximum(np.sum(difference * difference, axis=2), 0.0))


def kernel_matrix(
    xy_left: Any,
    descriptor_left: Any,
    xy_right: Any,
    descriptor_right: Any,
    config: KernelConfig,
) -> Any:
    import numpy as np

    distance = pairwise_distance(xy_left, xy_right)
    scaled = math.sqrt(3.0) * distance / config.spatial_length_scale
    spatial = (1.0 + scaled) * np.exp(-scaled)
    if config.visual_weight == 0:
        return spatial.astype(np.float64)
    cosine = np.clip(descriptor_left @ descriptor_right.T, 0.0, 1.0)
    visual = cosine**config.visual_cosine_power
    return (spatial + config.visual_weight * visual).astype(np.float64)


def farthest_subset(
    candidates: list[int], selected: list[int], xy: Any, maximum: int
) -> list[int]:
    remaining = list(dict.fromkeys(candidates))
    output = list(selected)
    while remaining and len(output) < maximum:
        if not output:
            chosen = min(remaining)
        else:
            import numpy as np

            selected_xy = xy[np.asarray(output)]
            distances = pairwise_distance(xy[np.asarray(remaining)], selected_xy)
            minimum = distances.min(axis=1)
            best_value = float(minimum.max())
            tied = [
                index
                for index, value in zip(remaining, minimum)
                if abs(float(value) - best_value) <= 1e-12
            ]
            chosen = min(tied)
        output.append(chosen)
        remaining.remove(chosen)
    return output


def select_inducing(
    queried_indices: list[int], responses: list[float], xy: Any, maximum: int
) -> list[int]:
    positive = [
        index for index, response in zip(queried_indices, responses) if response > 0.5
    ]
    negative = [
        index for index, response in zip(queried_indices, responses) if response <= 0.5
    ]
    selected = farthest_subset(positive, [], xy, maximum)
    if len(selected) < maximum:
        selected = farthest_subset(negative, selected, xy, maximum)
    return selected[:maximum]


def posterior_batch(
    *,
    pool_xy: Any,
    descriptors: Any,
    queried_indices: list[int],
    responses: list[float],
    unqueried_indices: list[int],
    config: KernelConfig,
    maximum_inducing: int,
    batch_size: int,
    novelty_weight: float,
) -> list[int]:
    import numpy as np

    inducing = select_inducing(queried_indices, responses, pool_xy, maximum_inducing)
    if not inducing or not unqueried_indices or batch_size <= 0:
        return []
    index_to_response = {
        index: response for index, response in zip(queried_indices, responses)
    }
    y = np.asarray([index_to_response[index] for index in inducing], dtype=np.float64)
    inducing_array = np.asarray(inducing, dtype=np.int64)
    candidate_array = np.asarray(unqueried_indices, dtype=np.int64)
    k_mm = kernel_matrix(
        pool_xy[inducing_array],
        descriptors[inducing_array],
        pool_xy[inducing_array],
        descriptors[inducing_array],
        config,
    )
    k_mm += np.eye(len(inducing), dtype=np.float64) * 0.001
    k_xm = kernel_matrix(
        pool_xy[candidate_array],
        descriptors[candidate_array],
        pool_xy[inducing_array],
        descriptors[inducing_array],
        config,
    )
    try:
        alpha = np.linalg.solve(k_mm, y)
        mean = k_xm @ alpha
        solved = np.linalg.solve(k_mm, k_xm.T).T
    except np.linalg.LinAlgError:
        inverse = np.linalg.pinv(k_mm)
        mean = k_xm @ inverse @ y
        solved = k_xm @ inverse
    prior_variance = 1.0 + config.visual_weight
    variance = np.maximum(
        prior_variance - np.sum(k_xm * solved, axis=1),
        0.0,
    )
    queried_xy = pool_xy[np.asarray(queried_indices, dtype=np.int64)]
    novelty = pairwise_distance(pool_xy[candidate_array], queried_xy).min(axis=1)
    score = mean + 2.0 * np.sqrt(variance) + novelty_weight * novelty
    ranked = sorted(
        zip(candidate_array.tolist(), score.tolist()),
        key=lambda row: (-row[1], row[0]),
    )
    return [index for index, _ in ranked[:batch_size]]


def coordinate_key(point: tuple[float, float]) -> tuple[int, int]:
    return int(round(point[0] * 4)), int(round(point[1] * 4))


def generate_query_order(
    *,
    width: int,
    height: int,
    pool: list[dict[str, Any]],
    observe: Callable[[tuple[float, float]], PreviewObservation],
    descriptors: Any,
    kernel: KernelConfig,
    geometry: GeometryConfig,
    maximum_queries: int,
    maximum_refined_anchors: int = 4,
    anchor_novelty_pixels: float = 32.0,
    posterior_batch_size: int = 8,
    maximum_inducing: int = 32,
    novelty_weight: float = 0.05,
    trace_stop_after_consecutive_nonresponses: int = 3,
) -> list[QueryEvent]:
    """Generate a shared response-search trace through the label-free API."""

    import numpy as np

    if width <= 0 or height <= 0:
        raise ValueError("screen dimensions must be positive")
    pool_points = np.asarray([row["point"] for row in pool], dtype=np.float32)
    pool_xy = pool_points / np.asarray([width, height], dtype=np.float32)
    if descriptors.shape[0] != len(pool):
        raise ValueError("descriptor count differs from support pool")

    events: list[QueryEvent] = []
    queried_pool: list[int] = []
    pool_responses: list[float] = []
    queried_coordinate_keys: set[tuple[int, int]] = set()
    refined_anchors: list[tuple[float, float]] = []
    local_queue: deque[dict[str, Any]] = deque()
    trace_queue: deque[dict[str, Any]] = deque()
    pool_batch_queue: deque[int] = deque()
    local_groups: dict[int, dict[str, Any]] = {}
    next_group_id = 0
    trace_triggered = False
    trace_consecutive_nonresponses = {-1: 0, 1: 0}
    trace_anchor = (0.0, 0.0)
    trace_axis = ""

    def execute(
        point: tuple[float, float],
        *,
        pool_index: int | None,
        source: str,
        query_kind: str,
    ) -> QueryEvent | None:
        key = coordinate_key(point)
        if key in queried_coordinate_keys or len(events) >= maximum_queries:
            return None
        queried_coordinate_keys.add(key)
        observation = observe(point)
        if observation.point != point:
            raise ValueError("observation coordinate differs from query")
        event = QueryEvent(
            query_index=len(events) + 1,
            point=point,
            pool_index=pool_index,
            source=source,
            query_kind=query_kind,
            positive=bool(observation.positive),
            evidence=str(observation.evidence),
        )
        events.append(event)
        if pool_index is not None:
            queried_pool.append(pool_index)
            pool_responses.append(float(event.positive))
        return event

    def anchor_is_novel(point: tuple[float, float]) -> bool:
        return all(
            math.hypot(point[0] - anchor[0], point[1] - anchor[1])
            > anchor_novelty_pixels
            for anchor in refined_anchors
        )

    def register_anchor(event: QueryEvent) -> None:
        nonlocal next_group_id
        if (
            not event.positive
            or len(refined_anchors) >= maximum_refined_anchors
            or not anchor_is_novel(event.point)
        ):
            return
        refined_anchors.append(event.point)
        group_id = next_group_id
        next_group_id += 1
        offsets = []
        for distance in (8, 16, 32):
            offsets.extend(
                [
                    ("horizontal", -distance, (event.point[0] - distance, event.point[1])),
                    ("horizontal", distance, (event.point[0] + distance, event.point[1])),
                    ("vertical", -distance, (event.point[0], event.point[1] - distance)),
                    ("vertical", distance, (event.point[0], event.point[1] + distance)),
                ]
            )
        offsets = offsets[: geometry.maximum_local_points_per_positive_basin]
        local_groups[group_id] = {
            "anchor": event.point,
            "expected": len(offsets),
            "results": [],
            "trace_evaluated": False,
        }
        for axis, signed_distance, point in offsets:
            if 0 <= point[0] < width and 0 <= point[1] < height:
                local_queue.append(
                    {
                        "group_id": group_id,
                        "axis": axis,
                        "signed_distance": signed_distance,
                        "point": point,
                    }
                )
            else:
                local_groups[group_id]["expected"] -= 1

    def schedule_trace(sign: int, step_index: int) -> None:
        delta = sign * step_index * geometry.trace_step_pixels
        point = (
            (trace_anchor[0] + delta, trace_anchor[1])
            if trace_axis == "horizontal"
            else (trace_anchor[0], trace_anchor[1] + delta)
        )
        if 0 <= point[0] < width and 0 <= point[1] < height:
            trace_queue.append(
                {"point": point, "axis": trace_axis, "sign": sign, "step": step_index}
            )

    def maybe_enqueue_trace(group_id: int) -> None:
        nonlocal trace_triggered, trace_anchor, trace_axis
        group = local_groups[group_id]
        if (
            trace_triggered
            or group["trace_evaluated"]
            or len(group["results"]) < group["expected"]
        ):
            return
        group["trace_evaluated"] = True
        evidence_by_axis = {"horizontal": set(), "vertical": set()}
        for result in group["results"]:
            event = result["event"]
            if event is not None and event.positive and event.evidence.strip():
                evidence_by_axis[result["axis"]].add(event.evidence)
        horizontal = len(evidence_by_axis["horizontal"])
        vertical = len(evidence_by_axis["vertical"])
        if max(horizontal, vertical) < 2 or horizontal == vertical:
            return
        trace_axis = "horizontal" if horizontal > vertical else "vertical"
        trace_anchor = group["anchor"]
        trace_triggered = True
        schedule_trace(-1, 1)
        schedule_trace(1, 1)

    def enqueue_posterior_batch() -> bool:
        queried_set = set(queried_pool)
        unqueried = [index for index in range(len(pool)) if index not in queried_set]
        if not unqueried or not queried_pool:
            return False
        batch = posterior_batch(
            pool_xy=pool_xy,
            descriptors=descriptors,
            queried_indices=queried_pool,
            responses=pool_responses,
            unqueried_indices=unqueried,
            config=kernel,
            maximum_inducing=maximum_inducing,
            batch_size=min(posterior_batch_size, maximum_queries - len(events)),
            novelty_weight=novelty_weight,
        )
        pool_batch_queue.extend(batch)
        return bool(batch)

    initial_count = min(geometry.initial_seed_budget, len(pool), maximum_queries)
    for pool_index in range(initial_count):
        point = tuple(float(value) for value in pool_points[pool_index])
        event = execute(
            point,
            pool_index=pool_index,
            source=str(pool[pool_index]["source"]),
            query_kind="initial_seed",
        )
        if event is not None:
            register_anchor(event)

    # The first posterior batch is selected from the frozen seed observations
    # before servicing seed-triggered refinements. Later batches wait until all
    # refinements triggered by the preceding batch have been serviced.
    if len(events) < maximum_queries:
        enqueue_posterior_batch()

    while len(events) < maximum_queries:
        if pool_batch_queue:
            pool_index = pool_batch_queue.popleft()
            point = tuple(float(value) for value in pool_points[pool_index])
            event = execute(
                point,
                pool_index=pool_index,
                source=str(pool[pool_index]["source"]),
                query_kind="posterior_pool",
            )
            if event is not None:
                register_anchor(event)
            continue
        if trace_queue:
            item = trace_queue.popleft()
            event = execute(
                item["point"],
                pool_index=None,
                source="manifold_trace",
                query_kind="manifold_trace",
            )
            sign = int(item["sign"])
            if event is None:
                schedule_trace(sign, int(item["step"]) + 1)
                continue
            register_anchor(event)
            if event.positive:
                trace_consecutive_nonresponses[sign] = 0
            else:
                trace_consecutive_nonresponses[sign] += 1
            if (
                trace_consecutive_nonresponses[sign]
                < trace_stop_after_consecutive_nonresponses
            ):
                schedule_trace(sign, int(item["step"]) + 1)
            continue
        if local_queue:
            item = local_queue.popleft()
            event = execute(
                item["point"],
                pool_index=None,
                source="local_refinement",
                query_kind="local_refinement",
            )
            if event is not None:
                register_anchor(event)
            group = local_groups[item["group_id"]]
            group["results"].append(
                {
                    "axis": item["axis"],
                    "signed_distance": item["signed_distance"],
                    "event": event,
                }
            )
            maybe_enqueue_trace(item["group_id"])
            continue

        if not enqueue_posterior_batch():
            break
    return events
