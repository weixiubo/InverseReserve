"""Budgeted observations and posterior scheduling, independent of topology phases."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from ..interface import QueryEvent
from ..search import KernelConfig, coordinate_key, posterior_batch
from .frontier import evidence_signature
from .types import QuotientRequest


def topology_receipt(request: QuotientRequest) -> dict[str, Any]:
    return {
        "anchor_query_index": None,
        "rank": None,
        "topology_enabled": request.enable_topology,
        "rank_two_allowed": request.allow_rank_two,
        "posterior_mode": request.posterior_mode,
        "progressive_rank_two": request.progressive_rank_two,
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


@dataclass
class QuotientQueries:
    request: QuotientRequest
    events: list[QueryEvent] = field(default_factory=list)
    queried_keys: set[tuple[int, int]] = field(default_factory=set)
    queried_pool: list[int] = field(default_factory=list)
    excluded_pool: set[int] = field(default_factory=set)
    labels: list[float] = field(default_factory=list)
    seen_signatures: set[str] = field(default_factory=set)
    seed_cursor: int = 0
    pool_points: Any = field(init=False)
    pool_xy: Any = field(init=False)
    topology: dict[str, Any] = field(init=False)

    def __post_init__(self):
        request = self.request
        if request.width <= 0 or request.height <= 0:
            raise ValueError("screen dimensions must be positive")
        if request.descriptors.shape[0] != len(request.pool):
            raise ValueError("descriptor count differs from support pool")
        if request.posterior_mode not in {"quotient", "static_tail"}:
            raise ValueError(f"unknown posterior mode: {request.posterior_mode}")
        self.pool_points = np.asarray([row["point"] for row in request.pool], dtype=np.float32)
        self.pool_xy = self.pool_points / np.asarray([request.width, request.height], dtype=np.float32)
        self.topology = topology_receipt(request)

    @property
    def available(self) -> bool:
        return len(self.events) < self.request.maximum_queries

    def in_bounds(self, point):
        return 0 <= point[0] < self.request.width and 0 <= point[1] < self.request.height

    def execute(self, point, *, pool_index, source, query_kind):
        key = coordinate_key(point)
        if key in self.queried_keys or not self.available:
            return None, None, False
        self.queried_keys.add(key)
        observation = self.request.observe(point)
        if observation.point != point:
            raise ValueError("observation coordinate differs from query")
        signature_fn = (
            self.request.signature_fn if self.request.signature_fn is not None else evidence_signature
        )
        signature = signature_fn(observation.evidence)
        novel = signature is not None and signature not in self.seen_signatures
        event = QueryEvent(
            query_index=len(self.events) + 1,
            point=point,
            pool_index=pool_index,
            source=source,
            query_kind=query_kind,
            positive=bool(observation.positive),
            evidence=str(observation.evidence),
        )
        self.events.append(event)
        if signature is not None:
            self.seen_signatures.add(signature)
        if pool_index is not None:
            self.queried_pool.append(pool_index)
            self.labels.append(float(novel))
            counter = "novel_pool_observations" if novel else "repeat_or_null_pool_observations"
            self.topology[counter] += 1
        self.topology["quotient_classes"] = len(self.seen_signatures)
        return event, signature, novel

    def query_pool(self, index, kind):
        point = tuple(float(value) for value in self.pool_points[index])
        if coordinate_key(point) in self.queried_keys:
            self.excluded_pool.add(index)
            return None, None, False
        return self.execute(
            point, pool_index=index, source=str(self.request.pool[index]["source"]), query_kind=kind
        )

    def seed(self, *, find_anchor):
        while self.seed_cursor < min(self.request.seed_maximum, len(self.request.pool)) and self.available:
            event, signature, _ = self.query_pool(self.seed_cursor, "quotient_seed")
            self.seed_cursor += 1
            if find_anchor and event is not None and signature is not None:
                self.topology["anchor_query_index"] = event.query_index
                return event, signature
        return None, None

    def finish_pool(self):
        self.seed(find_anchor=False)
        if self.request.posterior_mode == "static_tail":
            while self.seed_cursor < len(self.request.pool) and self.available:
                self.query_pool(self.seed_cursor, "quotient_static_tail")
                self.seed_cursor += 1
        while self.request.posterior_mode == "quotient" and self.available:
            batch = self.posterior()
            if not batch:
                break
            for index in batch:
                if not self.available:
                    break
                self.query_pool(index, "quotient_posterior")
        self.topology["quotient_classes"] = len(self.seen_signatures)
        self.topology["query_kind_counts"] = dict(
            sorted(Counter(event.query_kind for event in self.events).items())
        )

    def posterior(self):
        queried = set(self.queried_pool)
        unqueried = [
            index
            for index in range(len(self.request.pool))
            if index not in queried and index not in self.excluded_pool
        ]
        if not unqueried or not self.queried_pool:
            return []
        return posterior_batch(
            pool_xy=self.pool_xy,
            descriptors=self.request.descriptors,
            queried_indices=self.queried_pool,
            responses=self.labels,
            unqueried_indices=unqueried,
            config=KernelConfig(
                descriptor="dinov2_vits14", spatial_length_scale=0.1, visual_weight=1.0, visual_cosine_power=2
            ),
            maximum_inducing=self.request.maximum_inducing,
            batch_size=min(
                self.request.config.posterior_refresh_batch_size,
                self.request.maximum_queries - len(self.events),
            ),
            novelty_weight=self.request.novelty_weight,
        )
