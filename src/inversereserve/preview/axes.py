"""Axis scouting and traces expose observed response topology to frontier selection."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

from ..interface import QueryEvent
from .frontier import axis_coordinate, axis_point, noncontiguous_signature_repeat, signature_representatives
from .queries import QuotientQueries


@dataclass
class AxisExplorer:
    queries: QuotientQueries
    anchor: QueryEvent
    anchor_signature: str
    observations: dict[str, list[tuple[float, str | None]]] = field(init=False)
    queue: deque = field(default_factory=deque)
    consecutive: dict[tuple[str, int], int] = field(default_factory=dict)

    def __post_init__(self):
        self.observations = {
            axis: [(axis_coordinate(self.anchor.point, axis), self.anchor_signature)]
            for axis in ("horizontal", "vertical")
        }

    def scout(self, distance, axes):
        for axis in axes:
            for sign in (-1, 1):
                point = axis_point(self.anchor.point, axis, sign * distance)
                if not self.queries.in_bounds(point):
                    continue
                event, signature, _ = self.queries.execute(
                    point, pool_index=None, source="topology_scout", query_kind="topology_scout"
                )
                if event is not None:
                    self.queries.topology["scout_queries"] += 1
                    self.observations[axis].append((axis_coordinate(point, axis), signature))

    def varying_axes(self):
        return [
            axis
            for axis, rows in self.observations.items()
            if any(signature is not None and signature != self.anchor_signature for _, signature in rows)
        ]

    def discover(self):
        if self.queries.request.progressive_rank_two:
            for distance in (8, 16):
                self.scout(distance, ("horizontal", "vertical"))
            varying = self.varying_axes()
            if len(varying) == 1:
                self.scout(32, ("vertical" if varying[0] == "horizontal" else "horizontal",))
            elif not varying:
                self.scout(32, ("horizontal", "vertical"))
        else:
            for distance in self.queries.request.scout_offsets:
                self.scout(distance, ("horizontal", "vertical"))
        for axis, rows in self.observations.items():
            distinct = {
                signature
                for _, signature in rows
                if signature is not None and signature != self.anchor_signature
            }
            self.queries.topology["axis_distinct_signatures"][axis] = len(distinct)
            self.queries.topology["axis_varies"][axis] = bool(distinct)
        varying = [axis for axis, value in self.queries.topology["axis_varies"].items() if value]
        self.queries.topology["rank"] = len(varying)
        return varying

    def trace_one(self, axis):
        queue = deque([(-1, 1), (1, 1)])
        consecutive = {-1: 0, 1: 0}
        request = self.queries.request
        while queue and self.queries.available:
            sign, index = queue.popleft()
            point = axis_point(
                self.anchor.point, axis, sign * index * request.config.rank_one_trace_step_pixels
            )
            if not self.queries.in_bounds(point):
                continue
            event, signature, _ = self.queries.execute(
                point, pool_index=None, source="rank_one_trace", query_kind="rank_one_trace"
            )
            if event is None:
                queue.append((sign, index + 1))
                continue
            self.observations[axis].append((axis_coordinate(point, axis), signature))
            consecutive[sign] = 0 if signature is not None else consecutive[sign] + 1
            if consecutive[sign] < request.trace_stop_after_consecutive_nulls:
                queue.append((sign, index + 1))

    def start_two(self):
        self.queue = deque([(axis, sign, 1) for axis in ("horizontal", "vertical") for sign in (-1, 1)])
        self.consecutive = {(axis, sign): 0 for axis in ("horizontal", "vertical") for sign in (-1, 1)}

    def trace_next(self, kind):
        request = self.queries.request
        while self.queue and self.queries.available:
            axis, sign, index = self.queue.popleft()
            point = axis_point(
                self.anchor.point, axis, sign * index * request.config.rank_two_coarse_trace_step_pixels
            )
            if not self.queries.in_bounds(point):
                continue
            event, signature, _ = self.queries.execute(point, pool_index=None, source=kind, query_kind=kind)
            if event is None:
                self.queue.append((axis, sign, index + 1))
                continue
            self.observations[axis].append((axis_coordinate(point, axis), signature))
            key = axis, sign
            self.consecutive[key] = 0 if signature is not None else self.consecutive[key] + 1
            if self.consecutive[key] < request.trace_stop_after_consecutive_nulls:
                self.queue.append((axis, sign, index + 1))
            return True
        return False

    def representatives(self):
        return signature_representatives(self.observations["horizontal"]), signature_representatives(
            self.observations["vertical"]
        )

    def repeated(self):
        return noncontiguous_signature_repeat(
            self.observations["horizontal"]
        ) or noncontiguous_signature_repeat(self.observations["vertical"])

    def ready(self):
        horizontal, vertical = self.representatives()
        minimum = self.queries.request.minimum_axis_signatures
        return not self.repeated() and len(horizontal) >= minimum and len(vertical) >= minimum

    def report(self):
        horizontal, vertical = self.representatives()
        record = self.queries.topology["rank_two"]
        record["axis_representatives"] = {"horizontal": len(horizontal), "vertical": len(vertical)}
        record["noncontiguous_repeat"] = self.repeated()
