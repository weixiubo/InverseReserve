"""Response-conditioned spatial-visual search used by RC-RPS development."""

from __future__ import annotations

import math
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
    xy_left: Any, descriptor_left: Any, xy_right: Any, descriptor_right: Any, config: KernelConfig
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


def farthest_subset(candidates: list[int], selected: list[int], xy: Any, maximum: int) -> list[int]:
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
                for index, value in zip(remaining, minimum, strict=False)
                if abs(float(value) - best_value) <= 1e-12
            ]
            chosen = min(tied)
        output.append(chosen)
        remaining.remove(chosen)
    return output


def select_inducing(queried_indices: list[int], responses: list[float], xy: Any, maximum: int) -> list[int]:
    positive = [index for index, response in zip(queried_indices, responses, strict=False) if response > 0.5]
    negative = [index for index, response in zip(queried_indices, responses, strict=False) if response <= 0.5]
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
    index_to_response = {index: response for index, response in zip(queried_indices, responses, strict=False)}
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
    variance = np.maximum(prior_variance - np.sum(k_xm * solved, axis=1), 0.0)
    queried_xy = pool_xy[np.asarray(queried_indices, dtype=np.int64)]
    novelty = pairwise_distance(pool_xy[candidate_array], queried_xy).min(axis=1)
    score = mean + 2.0 * np.sqrt(variance) + novelty_weight * novelty
    ranked = sorted(
        zip(candidate_array.tolist(), score.tolist(), strict=False), key=lambda row: (-row[1], row[0])
    )
    return [index for index, _ in ranked[:batch_size]]


def coordinate_key(point: tuple[float, float]) -> tuple[int, int]:
    return (int(round(point[0] * 4)), int(round(point[1] * 4)))


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
    from .preview.local_search import LocalSearch, LocalSearchRequest

    return LocalSearch(
        LocalSearchRequest(
            width=width,
            height=height,
            pool=pool,
            observe=observe,
            descriptors=descriptors,
            kernel=kernel,
            geometry=geometry,
            maximum_queries=maximum_queries,
            maximum_refined_anchors=maximum_refined_anchors,
            anchor_novelty_pixels=anchor_novelty_pixels,
            posterior_batch_size=posterior_batch_size,
            maximum_inducing=maximum_inducing,
            novelty_weight=novelty_weight,
            trace_stop_after_consecutive_nonresponses=trace_stop_after_consecutive_nonresponses,
        )
    ).run()
