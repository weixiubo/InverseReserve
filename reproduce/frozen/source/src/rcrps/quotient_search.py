"""Quotient-space reversible preview search (Q-RPS).

The controller groups restoration-certified preview actions by normalized OCR
evidence and adapts its traversal to an observed zero-, one-, or two-dimensional
response topology. This module imports no evaluator world or task type.
"""

from __future__ import annotations

import hashlib
import math
import re
from collections import Counter, defaultdict, deque
from dataclasses import dataclass
from statistics import median
from typing import Any, Callable

from .interface import PreviewObservation, QueryEvent
from .search import KernelConfig, coordinate_key, posterior_batch


WHITESPACE = re.compile(r"\s+")


@dataclass(frozen=True)
class QuotientConfig:
    rank_one_trace_step_pixels: int
    rank_two_coarse_trace_step_pixels: int
    posterior_refresh_batch_size: int


@dataclass(frozen=True)
class QuotientSearchResult:
    events: list[QueryEvent]
    topology: dict[str, Any]


def normalize_evidence(evidence: str) -> str:
    return WHITESPACE.sub(" ", evidence.lower()).strip()


def evidence_signature(evidence: str) -> str | None:
    normalized = normalize_evidence(evidence)
    if not normalized:
        return None
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def axis_point(
    anchor: tuple[float, float], axis: str, signed_distance: float
) -> tuple[float, float]:
    if axis == "horizontal":
        return anchor[0] + signed_distance, anchor[1]
    return anchor[0], anchor[1] + signed_distance


def axis_coordinate(point: tuple[float, float], axis: str) -> float:
    return point[0] if axis == "horizontal" else point[1]


def noncontiguous_signature_repeat(
    observations: list[tuple[float, str | None]]
) -> bool:
    ordered = [
        signature
        for _, signature in sorted(observations)
        if signature is not None
    ]
    compressed = []
    for signature in ordered:
        if not compressed or compressed[-1] != signature:
            compressed.append(signature)
    return len(compressed) != len(set(compressed))


def signature_representatives(
    observations: list[tuple[float, str | None]]
) -> list[tuple[float, str]]:
    coordinates: dict[str, list[float]] = defaultdict(list)
    for coordinate, signature in observations:
        if signature is not None:
            coordinates[signature].append(coordinate)
    return sorted(
        (float(median(values)), signature) for signature, values in coordinates.items()
    )


def farthest_cartesian_frontier(
    horizontal: list[tuple[float, str]],
    vertical: list[tuple[float, str]],
    anchor: tuple[float, float],
) -> list[tuple[float, float]]:
    """Order off-axis Cartesian representatives by normalized farthest distance."""

    return [
        point
        for _, point in farthest_cartesian_frontier_entries(
            horizontal, vertical, anchor, covered_pairs=set()
        )
    ]


def farthest_cartesian_frontier_entries(
    horizontal: list[tuple[float, str]],
    vertical: list[tuple[float, str]],
    anchor: tuple[float, float],
    *,
    covered_pairs: set[tuple[str, str]],
) -> list[tuple[tuple[str, str], tuple[float, float]]]:
    """Return pair-keyed farthest entries for a current Cartesian frontier."""

    nx = len(horizontal)
    ny = len(vertical)
    anchor_x = min(range(nx), key=lambda index: abs(horizontal[index][0] - anchor[0]))
    anchor_y = min(range(ny), key=lambda index: abs(vertical[index][0] - anchor[1]))
    selected = {(index, anchor_y) for index in range(nx)} | {
        (anchor_x, index) for index in range(ny)
    }
    for x_index in range(nx):
        for y_index in range(ny):
            pair = (horizontal[x_index][1], vertical[y_index][1])
            if pair in covered_pairs:
                selected.add((x_index, y_index))
    remaining = [
        (x_index, y_index)
        for x_index in range(nx)
        for y_index in range(ny)
        if x_index != anchor_x and y_index != anchor_y
        and (horizontal[x_index][1], vertical[y_index][1]) not in covered_pairs
    ]

    def normalized_distance(left: tuple[int, int], right: tuple[int, int]) -> float:
        dx = (left[0] - right[0]) / max(nx - 1, 1)
        dy = (left[1] - right[1]) / max(ny - 1, 1)
        return dx * dx + dy * dy

    minimum_distance = {
        candidate: min(normalized_distance(candidate, point) for point in selected)
        for candidate in remaining
    }
    order: list[tuple[tuple[str, str], tuple[float, float]]] = []
    while remaining:
        best_value = max(minimum_distance[candidate] for candidate in remaining)
        chosen = min(
            candidate
            for candidate in remaining
            if abs(minimum_distance[candidate] - best_value) <= 1e-12
        )
        remaining.remove(chosen)
        pair = (horizontal[chosen[0]][1], vertical[chosen[1]][1])
        order.append(
            (pair, (horizontal[chosen[0]][0], vertical[chosen[1]][0]))
        )
        for candidate in remaining:
            minimum_distance[candidate] = min(
                minimum_distance[candidate],
                normalized_distance(candidate, chosen),
            )
    return order


def generate_quotient_query_order(
    *,
    width: int,
    height: int,
    pool: list[dict[str, Any]],
    observe: Callable[[tuple[float, float]], PreviewObservation],
    descriptors: Any,
    config: QuotientConfig,
    maximum_queries: int,
    seed_maximum: int = 64,
    scout_offsets: tuple[int, ...] = (8, 16, 32),
    trace_stop_after_consecutive_nulls: int = 3,
    minimum_axis_signatures: int = 4,
    frontier_validation_points: int = 4,
    frontier_validation_required_positive: int = 3,
    frontier_validation_required_novel: int = 3,
    maximum_inducing: int = 64,
    novelty_weight: float = 0.05,
    enable_topology: bool = True,
    allow_rank_two: bool = True,
    posterior_mode: str = "quotient",
    progressive_rank_two: bool = False,
    signature_fn: Callable[[str], str | None] | None = None,
) -> QuotientSearchResult:
    import numpy as np

    if width <= 0 or height <= 0:
        raise ValueError("screen dimensions must be positive")
    if descriptors.shape[0] != len(pool):
        raise ValueError("descriptor count differs from support pool")
    if posterior_mode not in {"quotient", "static_tail"}:
        raise ValueError(f"unknown posterior mode: {posterior_mode}")
    if signature_fn is None:
        signature_fn = evidence_signature
    pool_points = np.asarray([row["point"] for row in pool], dtype=np.float32)
    pool_xy = pool_points / np.asarray([width, height], dtype=np.float32)
    kernel = KernelConfig(
        descriptor="dinov2_vits14",
        spatial_length_scale=0.1,
        visual_weight=1.0,
        visual_cosine_power=2,
    )

    events: list[QueryEvent] = []
    queried_keys: set[tuple[int, int]] = set()
    queried_pool: list[int] = []
    excluded_pool: set[int] = set()
    quotient_labels: list[float] = []
    seen_signatures: set[str] = set()
    first_event_by_signature: dict[str, QueryEvent] = {}
    seed_cursor = 0
    topology: dict[str, Any] = {
        "anchor_query_index": None,
        "rank": None,
        "topology_enabled": enable_topology,
        "rank_two_allowed": allow_rank_two,
        "posterior_mode": posterior_mode,
        "progressive_rank_two": progressive_rank_two,
        "scout_queries": 0,
        "axis_varies": {"horizontal": False, "vertical": False},
        "axis_distinct_signatures": {"horizontal": 0, "vertical": 0},
        "rank_two": {
            "candidate": False,
            "rejected_by_ablation": False,
            "axis_representatives": {"horizontal": 0, "vertical": 0},
            "noncontiguous_repeat": False,
            "validation_queries": 0,
            "validation_positive": 0,
            "validation_novel": 0,
            "accepted": False,
            "frontier_points": 0,
            "frontier_queries": 0,
            "bootstrap_completion_query": None,
            "revoked_after_acceptance": False,
            "covered_pair_keys": 0,
            "frontier_pair_key_hashes": [],
            "frontier_rebuilds": [],
        },
        "quotient_classes": 0,
        "novel_pool_observations": 0,
        "repeat_or_null_pool_observations": 0,
    }

    def execute(
        point: tuple[float, float],
        *,
        pool_index: int | None,
        source: str,
        query_kind: str,
    ) -> tuple[QueryEvent | None, str | None, bool]:
        key = coordinate_key(point)
        if key in queried_keys or len(events) >= maximum_queries:
            return None, None, False
        queried_keys.add(key)
        observation = observe(point)
        if observation.point != point:
            raise ValueError("observation coordinate differs from query")
        signature = signature_fn(observation.evidence)
        novel = signature is not None and signature not in seen_signatures
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
        if signature is not None:
            first_event_by_signature.setdefault(signature, event)
            seen_signatures.add(signature)
        if pool_index is not None:
            queried_pool.append(pool_index)
            quotient_labels.append(float(novel))
            if novel:
                topology["novel_pool_observations"] += 1
            else:
                topology["repeat_or_null_pool_observations"] += 1
        topology["quotient_classes"] = len(seen_signatures)
        return event, signature, novel

    def query_pool(pool_index: int, query_kind: str) -> tuple[QueryEvent | None, str | None, bool]:
        point = tuple(float(value) for value in pool_points[pool_index])
        if coordinate_key(point) in queried_keys:
            excluded_pool.add(pool_index)
            return None, None, False
        return execute(
            point,
            pool_index=pool_index,
            source=str(pool[pool_index]["source"]),
            query_kind=query_kind,
        )

    anchor_event: QueryEvent | None = None
    anchor_signature: str | None = None
    while seed_cursor < min(seed_maximum, len(pool)) and len(events) < maximum_queries:
        event, signature, _ = query_pool(seed_cursor, "quotient_seed")
        seed_cursor += 1
        if enable_topology and event is not None and signature is not None:
            anchor_event = event
            anchor_signature = signature
            topology["anchor_query_index"] = event.query_index
            break

    axis_observations: dict[str, list[tuple[float, str | None]]] = {
        "horizontal": [],
        "vertical": [],
    }
    if anchor_event is not None and anchor_signature is not None:
        for axis in axis_observations:
            axis_observations[axis].append(
                (axis_coordinate(anchor_event.point, axis), anchor_signature)
            )

        def run_scout(distance: int, axes: tuple[str, ...]) -> None:
            for axis in axes:
                for sign in (-1, 1):
                    point = axis_point(anchor_event.point, axis, sign * distance)
                    if not (0 <= point[0] < width and 0 <= point[1] < height):
                        continue
                    event, signature, _ = execute(
                        point,
                        pool_index=None,
                        source="topology_scout",
                        query_kind="topology_scout",
                    )
                    if event is None:
                        continue
                    topology["scout_queries"] += 1
                    axis_observations[axis].append(
                        (axis_coordinate(point, axis), signature)
                    )

        def varying_axes() -> list[str]:
            output = []
            for axis in axis_observations:
                if any(
                    signature is not None and signature != anchor_signature
                    for _, signature in axis_observations[axis]
                ):
                    output.append(axis)
            return output

        if progressive_rank_two:
            for distance in (8, 16):
                run_scout(distance, ("horizontal", "vertical"))
            initial_varying = varying_axes()
            if len(initial_varying) == 1:
                nonvarying = (
                    "vertical" if initial_varying[0] == "horizontal" else "horizontal"
                )
                run_scout(32, (nonvarying,))
            elif not initial_varying:
                run_scout(32, ("horizontal", "vertical"))
        else:
            for distance in scout_offsets:
                run_scout(distance, ("horizontal", "vertical"))
        for axis in axis_observations:
            distinct = {
                signature
                for _, signature in axis_observations[axis]
                if signature is not None and signature != anchor_signature
            }
            topology["axis_distinct_signatures"][axis] = len(distinct)
            topology["axis_varies"][axis] = bool(distinct)
        varying = [axis for axis, value in topology["axis_varies"].items() if value]
        topology["rank"] = len(varying)

        if len(varying) == 1:
            axis = varying[0]
            queue: deque[tuple[int, int]] = deque([(-1, 1), (1, 1)])
            consecutive = {-1: 0, 1: 0}
            while queue and len(events) < maximum_queries:
                sign, step_index = queue.popleft()
                point = axis_point(
                    anchor_event.point,
                    axis,
                    sign * step_index * config.rank_one_trace_step_pixels,
                )
                if not (0 <= point[0] < width and 0 <= point[1] < height):
                    continue
                event, signature, _ = execute(
                    point,
                    pool_index=None,
                    source="rank_one_trace",
                    query_kind="rank_one_trace",
                )
                if event is None:
                    queue.append((sign, step_index + 1))
                    continue
                axis_observations[axis].append((axis_coordinate(point, axis), signature))
                consecutive[sign] = 0 if signature is not None else consecutive[sign] + 1
                if consecutive[sign] < trace_stop_after_consecutive_nulls:
                    queue.append((sign, step_index + 1))

        elif len(varying) == 2:
            topology["rank_two"]["candidate"] = True
            if not allow_rank_two:
                topology["rank_two"]["rejected_by_ablation"] = True
            elif progressive_rank_two:
                axis_queue: deque[tuple[str, int, int]] = deque(
                    [
                        ("horizontal", -1, 1),
                        ("horizontal", 1, 1),
                        ("vertical", -1, 1),
                        ("vertical", 1, 1),
                    ]
                )
                consecutive = {
                    ("horizontal", -1): 0,
                    ("horizontal", 1): 0,
                    ("vertical", -1): 0,
                    ("vertical", 1): 0,
                }

                def execute_next_axis_query() -> bool:
                    while axis_queue and len(events) < maximum_queries:
                        axis, sign, step_index = axis_queue.popleft()
                        point = axis_point(
                            anchor_event.point,
                            axis,
                            sign * step_index * config.rank_two_coarse_trace_step_pixels,
                        )
                        if not (0 <= point[0] < width and 0 <= point[1] < height):
                            continue
                        event, signature, _ = execute(
                            point,
                            pool_index=None,
                            source="progressive_axis_trace",
                            query_kind="progressive_axis_trace",
                        )
                        if event is None:
                            axis_queue.append((axis, sign, step_index + 1))
                            continue
                        axis_observations[axis].append(
                            (axis_coordinate(point, axis), signature)
                        )
                        key = (axis, sign)
                        consecutive[key] = (
                            0 if signature is not None else consecutive[key] + 1
                        )
                        if consecutive[key] < trace_stop_after_consecutive_nulls:
                            axis_queue.append((axis, sign, step_index + 1))
                        return True
                    return False

                def current_representatives() -> tuple[
                    list[tuple[float, str]], list[tuple[float, str]]
                ]:
                    return (
                        signature_representatives(axis_observations["horizontal"]),
                        signature_representatives(axis_observations["vertical"]),
                    )

                horizontal, vertical = current_representatives()
                repeated = noncontiguous_signature_repeat(
                    axis_observations["horizontal"]
                ) or noncontiguous_signature_repeat(axis_observations["vertical"])
                while (
                    not repeated
                    and (
                        len(horizontal) < minimum_axis_signatures
                        or len(vertical) < minimum_axis_signatures
                    )
                    and len(events) < maximum_queries
                ):
                    if not execute_next_axis_query():
                        break
                    horizontal, vertical = current_representatives()
                    repeated = noncontiguous_signature_repeat(
                        axis_observations["horizontal"]
                    ) or noncontiguous_signature_repeat(
                        axis_observations["vertical"]
                    )
                topology["rank_two"]["bootstrap_completion_query"] = len(events)
                topology["rank_two"]["axis_representatives"] = {
                    "horizontal": len(horizontal),
                    "vertical": len(vertical),
                }
                topology["rank_two"]["noncontiguous_repeat"] = repeated
                if (
                    not repeated
                    and len(horizontal) >= minimum_axis_signatures
                    and len(vertical) >= minimum_axis_signatures
                ):
                    covered_pairs: set[tuple[str, str]] = set()
                    frontier = farthest_cartesian_frontier_entries(
                        horizontal,
                        vertical,
                        anchor_event.point,
                        covered_pairs=covered_pairs,
                    )
                    topology["rank_two"]["frontier_points"] = len(frontier)
                    topology["rank_two"]["frontier_rebuilds"].append(
                        {
                            "query_index": len(events),
                            "cause": "bootstrap",
                            "horizontal_representatives": len(horizontal),
                            "vertical_representatives": len(vertical),
                            "pending_frontier": len(frontier),
                        }
                    )
                    seen_before_validation = set(seen_signatures)
                    validation_events: list[tuple[QueryEvent, str | None]] = []
                    frontier_cursor = 0
                    while (
                        frontier_cursor < len(frontier)
                        and len(validation_events) < frontier_validation_points
                        and len(events) < maximum_queries
                    ):
                        pair, point = frontier[frontier_cursor]
                        frontier_cursor += 1
                        event, signature, _ = execute(
                            point,
                            pool_index=None,
                            source="progressive_validation",
                            query_kind="progressive_validation",
                        )
                        covered_pairs.add(pair)
                        if event is not None:
                            validation_events.append((event, signature))
                            topology["rank_two"]["frontier_pair_key_hashes"].append(
                                hashlib.sha256(
                                    (pair[0] + "\0" + pair[1]).encode("utf-8")
                                ).hexdigest()
                            )
                    positive = sum(
                        signature is not None for _, signature in validation_events
                    )
                    novel_signatures = {
                        signature
                        for _, signature in validation_events
                        if signature is not None
                        and signature not in seen_before_validation
                    }
                    accepted = (
                        len(validation_events) == frontier_validation_points
                        and positive >= frontier_validation_required_positive
                        and len(novel_signatures) >= frontier_validation_required_novel
                    )
                    topology["rank_two"].update(
                        {
                            "validation_queries": len(validation_events),
                            "validation_positive": positive,
                            "validation_novel": len(novel_signatures),
                            "accepted": accepted,
                            "frontier_queries": len(validation_events),
                        }
                    )
                    if accepted:
                        # Finish the already frozen bootstrap-frontier order.
                        for pair, point in frontier[frontier_cursor:]:
                            if len(events) >= maximum_queries:
                                break
                            event, _, _ = execute(
                                point,
                                pool_index=None,
                                source="progressive_frontier",
                                query_kind="progressive_frontier",
                            )
                            covered_pairs.add(pair)
                            if event is not None:
                                topology["rank_two"]["frontier_queries"] += 1
                                topology["rank_two"][
                                    "frontier_pair_key_hashes"
                                ].append(
                                    hashlib.sha256(
                                        (pair[0] + "\0" + pair[1]).encode("utf-8")
                                    ).hexdigest()
                                )

                        while len(events) < maximum_queries:
                            horizontal, vertical = current_representatives()
                            repeated = noncontiguous_signature_repeat(
                                axis_observations["horizontal"]
                            ) or noncontiguous_signature_repeat(
                                axis_observations["vertical"]
                            )
                            if repeated:
                                topology["rank_two"][
                                    "revoked_after_acceptance"
                                ] = True
                                break
                            frontier = farthest_cartesian_frontier_entries(
                                horizontal,
                                vertical,
                                anchor_event.point,
                                covered_pairs=covered_pairs,
                            )
                            if frontier:
                                topology["rank_two"]["frontier_rebuilds"].append(
                                    {
                                        "query_index": len(events),
                                        "cause": "axis_representative_update",
                                        "horizontal_representatives": len(horizontal),
                                        "vertical_representatives": len(vertical),
                                        "pending_frontier": len(frontier),
                                    }
                                )
                                for pair, point in frontier:
                                    if len(events) >= maximum_queries:
                                        break
                                    event, _, _ = execute(
                                        point,
                                        pool_index=None,
                                        source="progressive_frontier",
                                        query_kind="progressive_frontier",
                                    )
                                    covered_pairs.add(pair)
                                    if event is not None:
                                        topology["rank_two"]["frontier_queries"] += 1
                                        topology["rank_two"][
                                            "frontier_pair_key_hashes"
                                        ].append(
                                            hashlib.sha256(
                                                (pair[0] + "\0" + pair[1]).encode(
                                                    "utf-8"
                                                )
                                            ).hexdigest()
                                        )
                                continue
                            if not execute_next_axis_query():
                                break

                        horizontal, vertical = current_representatives()
                        topology["rank_two"]["axis_representatives"] = {
                            "horizontal": len(horizontal),
                            "vertical": len(vertical),
                        }
                        topology["rank_two"]["noncontiguous_repeat"] = (
                            noncontiguous_signature_repeat(
                                axis_observations["horizontal"]
                            )
                            or noncontiguous_signature_repeat(
                                axis_observations["vertical"]
                            )
                        )
                        topology["rank_two"]["frontier_points"] = max(
                            len(horizontal) - 1, 0
                        ) * max(len(vertical) - 1, 0)
                        topology["rank_two"]["covered_pair_keys"] = len(
                            covered_pairs
                        )
            else:
                queue: deque[tuple[str, int, int]] = deque(
                    [
                        ("horizontal", -1, 1),
                        ("horizontal", 1, 1),
                        ("vertical", -1, 1),
                        ("vertical", 1, 1),
                    ]
                )
                consecutive = {
                    ("horizontal", -1): 0,
                    ("horizontal", 1): 0,
                    ("vertical", -1): 0,
                    ("vertical", 1): 0,
                }
                while queue and len(events) < maximum_queries:
                    axis, sign, step_index = queue.popleft()
                    point = axis_point(
                        anchor_event.point,
                        axis,
                        sign * step_index * config.rank_two_coarse_trace_step_pixels,
                    )
                    if not (0 <= point[0] < width and 0 <= point[1] < height):
                        continue
                    event, signature, _ = execute(
                        point,
                        pool_index=None,
                        source="rank_two_axis_trace",
                        query_kind="rank_two_axis_trace",
                    )
                    if event is None:
                        queue.append((axis, sign, step_index + 1))
                        continue
                    axis_observations[axis].append((axis_coordinate(point, axis), signature))
                    key = (axis, sign)
                    consecutive[key] = (
                        0 if signature is not None else consecutive[key] + 1
                    )
                    if consecutive[key] < trace_stop_after_consecutive_nulls:
                        queue.append((axis, sign, step_index + 1))

                horizontal = signature_representatives(axis_observations["horizontal"])
                vertical = signature_representatives(axis_observations["vertical"])
                repeated = noncontiguous_signature_repeat(
                    axis_observations["horizontal"]
                ) or noncontiguous_signature_repeat(axis_observations["vertical"])
                topology["rank_two"]["axis_representatives"] = {
                    "horizontal": len(horizontal),
                    "vertical": len(vertical),
                }
                topology["rank_two"]["noncontiguous_repeat"] = repeated
                if (
                    len(horizontal) >= minimum_axis_signatures
                    and len(vertical) >= minimum_axis_signatures
                    and not repeated
                ):
                    frontier = farthest_cartesian_frontier(
                        horizontal, vertical, anchor_event.point
                    )
                    topology["rank_two"]["frontier_points"] = len(frontier)
                    seen_before_validation = set(seen_signatures)
                    validation_events: list[tuple[QueryEvent, str | None]] = []
                    frontier_cursor = 0
                    while (
                        frontier_cursor < len(frontier)
                        and len(validation_events) < frontier_validation_points
                        and len(events) < maximum_queries
                    ):
                        point = frontier[frontier_cursor]
                        frontier_cursor += 1
                        event, signature, _ = execute(
                            point,
                            pool_index=None,
                            source="rank_two_validation",
                            query_kind="rank_two_validation",
                        )
                        if event is not None:
                            validation_events.append((event, signature))
                    positive = sum(
                        signature is not None for _, signature in validation_events
                    )
                    novel_signatures = {
                        signature
                        for _, signature in validation_events
                        if signature is not None
                        and signature not in seen_before_validation
                    }
                    accepted = (
                        len(validation_events) == frontier_validation_points
                        and positive >= frontier_validation_required_positive
                        and len(novel_signatures) >= frontier_validation_required_novel
                    )
                    topology["rank_two"].update(
                        {
                            "validation_queries": len(validation_events),
                            "validation_positive": positive,
                            "validation_novel": len(novel_signatures),
                            "accepted": accepted,
                            "frontier_queries": len(validation_events),
                        }
                    )
                    if accepted:
                        while (
                            frontier_cursor < len(frontier)
                            and len(events) < maximum_queries
                        ):
                            point = frontier[frontier_cursor]
                            frontier_cursor += 1
                            event, _, _ = execute(
                                point,
                                pool_index=None,
                                source="rank_two_frontier",
                                query_kind="rank_two_frontier",
                            )
                            if event is not None:
                                topology["rank_two"]["frontier_queries"] += 1
    elif enable_topology:
        topology["rank"] = "no_response_by_seed_64"
    else:
        topology["rank"] = "topology_disabled"

    # Resume the frozen seed prefix after any completed or rejected topology
    # operator, then spend remaining budget on expected new quotient classes.
    while seed_cursor < min(seed_maximum, len(pool)) and len(events) < maximum_queries:
        query_pool(seed_cursor, "quotient_seed")
        seed_cursor += 1

    if posterior_mode == "static_tail":
        while seed_cursor < len(pool) and len(events) < maximum_queries:
            query_pool(seed_cursor, "quotient_static_tail")
            seed_cursor += 1
    while posterior_mode == "quotient" and len(events) < maximum_queries:
        queried_set = set(queried_pool)
        unqueried = [
            index
            for index in range(len(pool))
            if index not in queried_set and index not in excluded_pool
        ]
        if not unqueried or not queried_pool:
            break
        batch = posterior_batch(
            pool_xy=pool_xy,
            descriptors=descriptors,
            queried_indices=queried_pool,
            responses=quotient_labels,
            unqueried_indices=unqueried,
            config=kernel,
            maximum_inducing=maximum_inducing,
            batch_size=min(
                config.posterior_refresh_batch_size,
                maximum_queries - len(events),
            ),
            novelty_weight=novelty_weight,
        )
        if not batch:
            break
        for pool_index in batch:
            if len(events) >= maximum_queries:
                break
            query_pool(pool_index, "quotient_posterior")

    topology["quotient_classes"] = len(seen_signatures)
    topology["query_kind_counts"] = dict(
        sorted(Counter(event.query_kind for event in events).items())
    )
    return QuotientSearchResult(events=events, topology=topology)
