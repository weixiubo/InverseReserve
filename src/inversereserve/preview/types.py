from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from ..interface import PreviewObservation, QueryEvent


@dataclass(frozen=True)
class QuotientConfig:
    rank_one_trace_step_pixels: int
    rank_two_coarse_trace_step_pixels: int
    posterior_refresh_batch_size: int


@dataclass(frozen=True)
class QuotientSearchResult:
    events: list[QueryEvent]
    topology: dict[str, Any]


@dataclass(frozen=True, kw_only=True)
class QuotientRequest:
    width: int
    height: int
    pool: list[dict[str, Any]]
    observe: Callable[[tuple[float, float]], PreviewObservation]
    descriptors: Any
    config: QuotientConfig
    maximum_queries: int
    seed_maximum: int = 64
    scout_offsets: tuple[int, ...] = (8, 16, 32)
    trace_stop_after_consecutive_nulls: int = 3
    minimum_axis_signatures: int = 4
    frontier_validation_points: int = 4
    frontier_validation_required_positive: int = 3
    frontier_validation_required_novel: int = 3
    maximum_inducing: int = 64
    novelty_weight: float = 0.05
    enable_topology: bool = True
    allow_rank_two: bool = True
    posterior_mode: str = "quotient"
    progressive_rank_two: bool = False
    signature_fn: Callable[[str], str | None] | None = None
