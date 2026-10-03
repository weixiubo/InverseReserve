"""Validated Cartesian traversal with explicit covered-pair state."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from .axes import AxisExplorer
from .frontier import farthest_cartesian_frontier_entries


@dataclass
class RankTwoExplorer:
    axes: AxisExplorer
    covered_pairs: set[tuple[str, str]] = field(default_factory=set)

    @property
    def queries(self):
        return self.axes.queries

    @property
    def record(self):
        return self.queries.topology["rank_two"]

    def frontier(self):
        horizontal, vertical = self.axes.representatives()
        return farthest_cartesian_frontier_entries(
            horizontal, vertical, self.axes.anchor.point, covered_pairs=self.covered_pairs
        )

    def record_rebuild(self, cause, pending):
        horizontal, vertical = self.axes.representatives()
        self.record["frontier_rebuilds"].append(
            {
                "query_index": len(self.queries.events),
                "cause": cause,
                "horizontal_representatives": len(horizontal),
                "vertical_representatives": len(vertical),
                "pending_frontier": pending,
            }
        )

    def record_pair(self, pair, event, progressive):
        if progressive:
            self.covered_pairs.add(pair)
            if event is not None:
                self.record["frontier_pair_key_hashes"].append(
                    hashlib.sha256((pair[0] + "\0" + pair[1]).encode("utf-8")).hexdigest()
                )

    def validate(self, frontier, progressive):
        request = self.queries.request
        seen = set(self.queries.seen_signatures)
        validation = []
        cursor = 0
        kind = "progressive_validation" if progressive else "rank_two_validation"
        while (
            cursor < len(frontier)
            and len(validation) < request.frontier_validation_points
            and self.queries.available
        ):
            pair, point = frontier[cursor]
            cursor += 1
            event, signature, _ = self.queries.execute(point, pool_index=None, source=kind, query_kind=kind)
            self.record_pair(pair, event, progressive)
            if event is not None:
                validation.append((event, signature))
        positive = sum(signature is not None for _, signature in validation)
        novel = {signature for _, signature in validation if signature is not None and signature not in seen}
        accepted = (
            len(validation) == request.frontier_validation_points
            and positive >= request.frontier_validation_required_positive
            and len(novel) >= request.frontier_validation_required_novel
        )
        self.record.update(
            validation_queries=len(validation),
            validation_positive=positive,
            validation_novel=len(novel),
            accepted=accepted,
            frontier_queries=len(validation),
        )
        return cursor, accepted

    def consume_frontier(self, frontier, progressive):
        kind = "progressive_frontier" if progressive else "rank_two_frontier"
        for pair, point in frontier:
            if not self.queries.available:
                break
            event, _, _ = self.queries.execute(point, pool_index=None, source=kind, query_kind=kind)
            self.record_pair(pair, event, progressive)
            if event is not None:
                self.record["frontier_queries"] += 1

    def bootstrap(self, progressive):
        self.axes.start_two()
        if progressive:
            while not self.axes.repeated() and not self.axes.ready() and self.queries.available:
                if not self.axes.trace_next("progressive_axis_trace"):
                    break
            self.record["bootstrap_completion_query"] = len(self.queries.events)
        else:
            while self.axes.trace_next("rank_two_axis_trace"):
                pass
        self.axes.report()

    def continue_progressive(self):
        while self.queries.available:
            if self.axes.repeated():
                self.record["revoked_after_acceptance"] = True
                break
            frontier = self.frontier()
            if frontier:
                self.record_rebuild("axis_representative_update", len(frontier))
                self.consume_frontier(frontier, True)
                continue
            if not self.axes.trace_next("progressive_axis_trace"):
                break
        self.axes.report()
        horizontal, vertical = self.axes.representatives()
        self.record["frontier_points"] = max(len(horizontal) - 1, 0) * max(len(vertical) - 1, 0)
        self.record["covered_pair_keys"] = len(self.covered_pairs)

    def run(self):
        self.record["candidate"] = True
        request = self.queries.request
        if not request.allow_rank_two:
            self.record["rejected_by_ablation"] = True
            return
        progressive = request.progressive_rank_two
        self.bootstrap(progressive)
        if not self.axes.ready():
            return
        frontier = self.frontier()
        self.record["frontier_points"] = len(frontier)
        if progressive:
            self.record_rebuild("bootstrap", len(frontier))
        cursor, accepted = self.validate(frontier, progressive)
        if accepted:
            self.consume_frontier(frontier[cursor:], progressive)
            if progressive:
                self.continue_progressive()
