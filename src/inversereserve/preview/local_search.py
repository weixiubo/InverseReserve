"""Local refinements, manifold traces and posterior batches share an explicit state."""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable

import numpy as np

from ..interface import PreviewObservation, QueryEvent
from ..search import GeometryConfig, KernelConfig, coordinate_key, posterior_batch


@dataclass(frozen=True, kw_only=True)
class LocalSearchRequest:
    width: int
    height: int
    pool: list[dict[str, Any]]
    observe: Callable[[tuple[float, float]], PreviewObservation]
    descriptors: Any
    kernel: KernelConfig
    geometry: GeometryConfig
    maximum_queries: int
    maximum_refined_anchors: int = 4
    anchor_novelty_pixels: float = 32.0
    posterior_batch_size: int = 8
    maximum_inducing: int = 32
    novelty_weight: float = 0.05
    trace_stop_after_consecutive_nonresponses: int = 3


@dataclass
class LocalSearchState:
    events: list[QueryEvent] = field(init=False)
    local_groups: dict[int, dict[str, Any]] = field(init=False)
    local_queue: deque[dict[str, Any]] = field(init=False)
    next_group_id: int = field(init=False)
    pool_batch_queue: deque[int] = field(init=False)
    pool_points: Any = field(init=False)
    pool_responses: list[float] = field(init=False)
    pool_xy: Any = field(init=False)
    queried_coordinate_keys: set[tuple[int, int]] = field(init=False)
    queried_pool: list[int] = field(init=False)
    excluded_pool: set[int] = field(default_factory=set)
    refined_anchors: list[tuple[float, float]] = field(init=False)
    trace_anchor: tuple[float, float] = field(init=False)
    trace_axis: str = field(init=False)
    trace_consecutive_nonresponses: dict[int, int] = field(init=False)
    trace_queue: deque[dict[str, Any]] = field(init=False)
    trace_triggered: bool = field(init=False)


class LocalSearch:
    def __init__(self, request: LocalSearchRequest):
        self.request = request
        self.state = LocalSearchState()
        if self.request.width <= 0 or self.request.height <= 0:
            raise ValueError("screen dimensions must be positive")
        self.state.pool_points = np.asarray([row["point"] for row in self.request.pool], dtype=np.float32)
        self.state.pool_xy = self.state.pool_points / np.asarray(
            [self.request.width, self.request.height], dtype=np.float32
        )
        if self.request.descriptors.shape[0] != len(self.request.pool):
            raise ValueError("descriptor count differs from support pool")
        self.state.events: list[QueryEvent] = []
        self.state.queried_pool: list[int] = []
        self.state.pool_responses: list[float] = []
        self.state.queried_coordinate_keys: set[tuple[int, int]] = set()
        self.state.refined_anchors: list[tuple[float, float]] = []
        self.state.local_queue: deque[dict[str, Any]] = deque()
        self.state.trace_queue: deque[dict[str, Any]] = deque()
        self.state.pool_batch_queue: deque[int] = deque()
        self.state.local_groups: dict[int, dict[str, Any]] = {}
        self.state.next_group_id = 0
        self.state.trace_triggered = False
        self.state.trace_consecutive_nonresponses = {-1: 0, 1: 0}
        self.state.trace_anchor = (0.0, 0.0)
        self.state.trace_axis = ""

    def execute(
        self, point: tuple[float, float], *, pool_index: int | None, source: str, query_kind: str
    ) -> QueryEvent | None:
        key = coordinate_key(point)
        if key in self.state.queried_coordinate_keys:
            if pool_index is not None:
                self.state.excluded_pool.add(pool_index)
            return None
        if len(self.state.events) >= self.request.maximum_queries:
            return None
        self.state.queried_coordinate_keys.add(key)
        observation = self.request.observe(point)
        if observation.point != point:
            raise ValueError("observation coordinate differs from query")
        event = QueryEvent(
            query_index=len(self.state.events) + 1,
            point=point,
            pool_index=pool_index,
            source=source,
            query_kind=query_kind,
            positive=bool(observation.positive),
            evidence=str(observation.evidence),
        )
        self.state.events.append(event)
        if pool_index is not None:
            self.state.queried_pool.append(pool_index)
            self.state.pool_responses.append(float(event.positive))
        return event

    def anchor_is_novel(self, point: tuple[float, float]) -> bool:
        return all(
            (
                math.hypot(point[0] - anchor[0], point[1] - anchor[1]) > self.request.anchor_novelty_pixels
                for anchor in self.state.refined_anchors
            )
        )

    def register_anchor(self, event: QueryEvent) -> None:
        if (
            not event.positive
            or len(self.state.refined_anchors) >= self.request.maximum_refined_anchors
            or (not self.anchor_is_novel(event.point))
        ):
            return
        self.state.refined_anchors.append(event.point)
        group_id = self.state.next_group_id
        self.state.next_group_id += 1
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
        offsets = offsets[: self.request.geometry.maximum_local_points_per_positive_basin]
        self.state.local_groups[group_id] = {
            "anchor": event.point,
            "expected": len(offsets),
            "results": [],
            "trace_evaluated": False,
        }
        for axis, signed_distance, point in offsets:
            if 0 <= point[0] < self.request.width and 0 <= point[1] < self.request.height:
                self.state.local_queue.append(
                    {"group_id": group_id, "axis": axis, "signed_distance": signed_distance, "point": point}
                )
            else:
                self.state.local_groups[group_id]["expected"] -= 1

    def schedule_trace(self, sign: int, step_index: int) -> None:
        delta = sign * step_index * self.request.geometry.trace_step_pixels
        point = (
            (self.state.trace_anchor[0] + delta, self.state.trace_anchor[1])
            if self.state.trace_axis == "horizontal"
            else (self.state.trace_anchor[0], self.state.trace_anchor[1] + delta)
        )
        if 0 <= point[0] < self.request.width and 0 <= point[1] < self.request.height:
            self.state.trace_queue.append(
                {"point": point, "axis": self.state.trace_axis, "sign": sign, "step": step_index}
            )

    def maybe_enqueue_trace(self, group_id: int) -> None:
        group = self.state.local_groups[group_id]
        if (
            self.state.trace_triggered
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
        self.state.trace_axis = "horizontal" if horizontal > vertical else "vertical"
        self.state.trace_anchor = group["anchor"]
        self.state.trace_triggered = True
        self.schedule_trace(-1, 1)
        self.schedule_trace(1, 1)

    def enqueue_posterior_batch(self) -> bool:
        queried_set = set(self.state.queried_pool)
        unqueried = [
            index
            for index in range(len(self.request.pool))
            if index not in queried_set and index not in self.state.excluded_pool
        ]
        if not unqueried or not self.state.queried_pool:
            return False
        batch = posterior_batch(
            pool_xy=self.state.pool_xy,
            descriptors=self.request.descriptors,
            queried_indices=self.state.queried_pool,
            responses=self.state.pool_responses,
            unqueried_indices=unqueried,
            config=self.request.kernel,
            maximum_inducing=self.request.maximum_inducing,
            batch_size=min(
                self.request.posterior_batch_size, self.request.maximum_queries - len(self.state.events)
            ),
            novelty_weight=self.request.novelty_weight,
        )
        self.state.pool_batch_queue.extend(batch)
        return bool(batch)

    def initialize(self):
        initial_count = min(
            self.request.geometry.initial_seed_budget, len(self.request.pool), self.request.maximum_queries
        )
        for pool_index in range(initial_count):
            point = tuple((float(value) for value in self.state.pool_points[pool_index]))
            event = self.execute(
                point,
                pool_index=pool_index,
                source=str(self.request.pool[pool_index]["source"]),
                query_kind="initial_seed",
            )
            if event is not None:
                self.register_anchor(event)
        if len(self.state.events) < self.request.maximum_queries:
            self.enqueue_posterior_batch()

    def consume_pool(self):
        pool_index = self.state.pool_batch_queue.popleft()
        point = tuple((float(value) for value in self.state.pool_points[pool_index]))
        event = self.execute(
            point,
            pool_index=pool_index,
            source=str(self.request.pool[pool_index]["source"]),
            query_kind="posterior_pool",
        )
        if event is not None:
            self.register_anchor(event)
        return

    def consume_trace(self):
        item = self.state.trace_queue.popleft()
        event = self.execute(
            item["point"], pool_index=None, source="manifold_trace", query_kind="manifold_trace"
        )
        sign = int(item["sign"])
        if event is None:
            self.schedule_trace(sign, int(item["step"]) + 1)
            return
        self.register_anchor(event)
        if event.positive:
            self.state.trace_consecutive_nonresponses[sign] = 0
        else:
            self.state.trace_consecutive_nonresponses[sign] += 1
        if (
            self.state.trace_consecutive_nonresponses[sign]
            < self.request.trace_stop_after_consecutive_nonresponses
        ):
            self.schedule_trace(sign, int(item["step"]) + 1)
        return

    def consume_local(self):
        item = self.state.local_queue.popleft()
        event = self.execute(
            item["point"], pool_index=None, source="local_refinement", query_kind="local_refinement"
        )
        if event is not None:
            self.register_anchor(event)
        group = self.state.local_groups[item["group_id"]]
        group["results"].append(
            {"axis": item["axis"], "signed_distance": item["signed_distance"], "event": event}
        )
        self.maybe_enqueue_trace(item["group_id"])
        return

    def run(self):
        self.initialize()
        while len(self.state.events) < self.request.maximum_queries:
            if self.state.pool_batch_queue:
                self.consume_pool()
            elif self.state.trace_queue:
                self.consume_trace()
            elif self.state.local_queue:
                self.consume_local()
            elif not self.enqueue_posterior_batch():
                break
        return self.state.events
