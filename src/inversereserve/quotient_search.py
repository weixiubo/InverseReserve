"""Public quotient-search API. Queries, axis discovery and frontiers have separate state."""

from __future__ import annotations

from typing import Any, Callable

from .interface import PreviewObservation
from .preview.axes import AxisExplorer
from .preview.frontier import axis_coordinate as axis_coordinate
from .preview.frontier import axis_point as axis_point
from .preview.frontier import evidence_signature as evidence_signature
from .preview.frontier import farthest_cartesian_frontier as farthest_cartesian_frontier
from .preview.frontier import farthest_cartesian_frontier_entries as farthest_cartesian_frontier_entries
from .preview.frontier import noncontiguous_signature_repeat as noncontiguous_signature_repeat
from .preview.frontier import normalize_evidence as normalize_evidence
from .preview.frontier import signature_representatives as signature_representatives
from .preview.queries import QuotientQueries
from .preview.rank_two import RankTwoExplorer
from .preview.types import QuotientConfig as QuotientConfig
from .preview.types import QuotientRequest
from .preview.types import QuotientSearchResult as QuotientSearchResult


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
    request = QuotientRequest(
        width=width,
        height=height,
        pool=pool,
        observe=observe,
        descriptors=descriptors,
        config=config,
        maximum_queries=maximum_queries,
        seed_maximum=seed_maximum,
        scout_offsets=scout_offsets,
        trace_stop_after_consecutive_nulls=trace_stop_after_consecutive_nulls,
        minimum_axis_signatures=minimum_axis_signatures,
        frontier_validation_points=frontier_validation_points,
        frontier_validation_required_positive=frontier_validation_required_positive,
        frontier_validation_required_novel=frontier_validation_required_novel,
        maximum_inducing=maximum_inducing,
        novelty_weight=novelty_weight,
        enable_topology=enable_topology,
        allow_rank_two=allow_rank_two,
        posterior_mode=posterior_mode,
        progressive_rank_two=progressive_rank_two,
        signature_fn=signature_fn,
    )
    queries = QuotientQueries(request)
    anchor, signature = queries.seed(find_anchor=enable_topology)
    if anchor is not None and signature is not None:
        axes = AxisExplorer(queries, anchor, signature)
        varying = axes.discover()
        if len(varying) == 1:
            axes.trace_one(varying[0])
        elif len(varying) == 2:
            RankTwoExplorer(axes).run()
    elif enable_topology:
        queries.topology["rank"] = "no_response_by_seed_64"
    else:
        queries.topology["rank"] = "topology_disabled"
    queries.finish_pool()
    return QuotientSearchResult(events=queries.events, topology=queries.topology)
