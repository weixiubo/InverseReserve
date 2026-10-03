"""Noise-robust online evidence quotienting for reversible preview search."""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from .evidence import retain_instruction_tokens, tokenize
from .interface import QueryEvent

WHITESPACE = re.compile(r"\s+")
DECIMAL_TOKEN = re.compile(r"^[0-9]+\.[0-9]+$")


@dataclass(frozen=True)
class RobustQuotientConfig:
    minimum_shared_decimal_anchors: int = 2
    minimum_decimal_containment: float = 0.4
    minimum_shared_general_tokens: int = 2
    minimum_general_containment: float = 0.95
    maximum_exemplars_per_class: int = 8
    stable_token_minimum_support: int = 2


@dataclass(frozen=True)
class EvidenceFeatures:
    normalized: str
    tokens: frozenset[str]
    decimal_anchors: frozenset[str]


@dataclass
class RobustEvidenceClass:
    class_index: int
    first_features: EvidenceFeatures
    exemplars: list[EvidenceFeatures] = field(default_factory=list)
    token_support: Counter[str] = field(default_factory=Counter)
    observations: int = 0

    @property
    def identifier(self) -> str:
        return f"rqm:{self.class_index:06d}"

    def stable_tokens(self, minimum_support: int) -> frozenset[str]:
        output = set(self.first_features.tokens)
        output.update(token for token, count in self.token_support.items() if count >= minimum_support)
        return frozenset(output)


@dataclass(frozen=True)
class RobustEvidenceDecision:
    point: tuple[float, float]
    raw_evidence: str
    class_identifier: str
    first_query_index: int
    score: float
    runner_up_score: float


@dataclass(frozen=True)
class RobustEvidenceRanking:
    best_class_identifier: str | None
    best_score: float
    runner_up_score: float
    scores: dict[str, float]


def normalize_raw_evidence(evidence: str) -> str:
    return WHITESPACE.sub(" ", evidence.lower()).strip()


def containment(left: frozenset[str], right: frozenset[str]) -> tuple[float, int]:
    if not left or not right:
        return 0.0, 0
    shared = len(left & right)
    return shared / min(len(left), len(right)), shared


class RobustQuotientMemory:
    """Assign raw OCR observations to deterministic, task-blind evidence classes."""

    def __init__(
        self,
        *,
        initial_screen_tokens: set[str] | frozenset[str],
        config: RobustQuotientConfig | None = None,
    ) -> None:
        self.initial_screen_tokens = set(initial_screen_tokens)
        self.config = config or RobustQuotientConfig()
        self.classes: list[RobustEvidenceClass] = []
        self.assignments: list[str | None] = []

    def features(self, evidence: str) -> EvidenceFeatures | None:
        normalized = normalize_raw_evidence(evidence)
        if not normalized:
            return None
        tokens = frozenset(tokenize(evidence))
        decimals = frozenset(
            token
            for token in tokens
            if token not in self.initial_screen_tokens and DECIMAL_TOKEN.fullmatch(token)
        )
        return EvidenceFeatures(normalized, tokens, decimals)

    def _match_score(self, observed: EvidenceFeatures, exemplar: EvidenceFeatures) -> tuple[int, float, int]:
        if observed.normalized == exemplar.normalized:
            return 3, 1.0, len(observed.tokens & exemplar.tokens)
        decimal_containment, shared_decimals = containment(observed.decimal_anchors, exemplar.decimal_anchors)
        if (
            shared_decimals >= self.config.minimum_shared_decimal_anchors
            and decimal_containment + 1e-12 >= self.config.minimum_decimal_containment
        ):
            return 2, decimal_containment, shared_decimals
        observed_general = frozenset(token for token in observed.tokens if len(token) >= 2)
        exemplar_general = frozenset(token for token in exemplar.tokens if len(token) >= 2)
        general_containment, shared_general = containment(observed_general, exemplar_general)
        if (
            shared_general >= self.config.minimum_shared_general_tokens
            and general_containment + 1e-12 >= self.config.minimum_general_containment
        ):
            return 1, general_containment, shared_general
        return 0, 0.0, 0

    def best_existing_class(self, evidence: str) -> tuple[RobustEvidenceClass | None, tuple[int, float, int]]:
        features = self.features(evidence)
        if features is None:
            return None, (0, 0.0, 0)
        best_class = None
        best_key = (0, 0.0, 0, 0)
        best_score = (0, 0.0, 0)
        for evidence_class in self.classes:
            score = max(
                (self._match_score(features, exemplar) for exemplar in evidence_class.exemplars),
                default=(0, 0.0, 0),
            )
            key = (*score, -evidence_class.class_index)
            if key > best_key:
                best_key = key
                best_score = score
                best_class = evidence_class
        if best_score[0] == 0:
            return None, best_score
        return best_class, best_score

    def observe(self, evidence: str) -> str | None:
        features = self.features(evidence)
        if features is None:
            self.assignments.append(None)
            return None
        evidence_class, _ = self.best_existing_class(evidence)
        if evidence_class is None:
            evidence_class = RobustEvidenceClass(
                class_index=len(self.classes),
                first_features=features,
            )
            self.classes.append(evidence_class)
        evidence_class.exemplars.append(features)
        if len(evidence_class.exemplars) > self.config.maximum_exemplars_per_class:
            evidence_class.exemplars = evidence_class.exemplars[-self.config.maximum_exemplars_per_class :]
        evidence_class.token_support.update(features.tokens)
        evidence_class.observations += 1
        self.assignments.append(evidence_class.identifier)
        return evidence_class.identifier

    def class_by_identifier(self, identifier: str) -> RobustEvidenceClass:
        prefix, raw_index = identifier.split(":", 1)
        if prefix != "rqm":
            raise ValueError(f"invalid RQM class identifier: {identifier}")
        evidence_class = self.classes[int(raw_index)]
        if evidence_class.identifier != identifier:
            raise ValueError(f"RQM class identifier mismatch: {identifier}")
        return evidence_class

    def stable_document_tokens(self, identifier: str) -> frozenset[str]:
        return self.class_by_identifier(identifier).stable_tokens(self.config.stable_token_minimum_support)

    def snapshot(self) -> list[dict[str, Any]]:
        return [
            {
                "class_identifier": evidence_class.identifier,
                "observations": evidence_class.observations,
                "first_tokens": sorted(evidence_class.first_features.tokens),
                "stable_tokens": sorted(
                    evidence_class.stable_tokens(self.config.stable_token_minimum_support)
                ),
                "exemplars": len(evidence_class.exemplars),
            }
            for evidence_class in self.classes
        ]


class RobustOnlineEvidenceTracker:
    """Score task evidence over robust classes rather than noisy raw strings."""

    def __init__(
        self,
        *,
        instruction: str,
        initial_screen_tokens: set[str],
        stopwords: set[str],
        absolute_threshold: float,
        margin_threshold: float,
        config: RobustQuotientConfig | None = None,
    ) -> None:
        self.retained_tokens = retain_instruction_tokens(instruction, stopwords)
        self.initial_screen_tokens = set(initial_screen_tokens)
        self.absolute_threshold = float(absolute_threshold)
        self.margin_threshold = float(margin_threshold)
        self.memory = RobustQuotientMemory(
            initial_screen_tokens=initial_screen_tokens,
            config=config,
        )
        self._first_event_by_class: dict[str, QueryEvent] = {}

    def observe(self, event: QueryEvent) -> RobustEvidenceDecision | None:
        identifier = self.memory.observe(event.evidence if event.positive else "")
        if identifier is not None:
            self._first_event_by_class.setdefault(identifier, event)
        ranking = self.rank()
        if ranking.best_class_identifier is None:
            return None
        if ranking.best_score + 1e-12 < self.absolute_threshold:
            return None
        if ranking.best_score - ranking.runner_up_score + 1e-12 < self.margin_threshold:
            return None
        first = self._first_event_by_class[ranking.best_class_identifier]
        return RobustEvidenceDecision(
            point=first.point,
            raw_evidence=first.evidence,
            class_identifier=ranking.best_class_identifier,
            first_query_index=first.query_index,
            score=ranking.best_score,
            runner_up_score=ranking.runner_up_score,
        )

    def rank(self) -> RobustEvidenceRanking:
        if not self.retained_tokens or not self._first_event_by_class:
            return RobustEvidenceRanking(None, 0.0, 0.0, {})
        documents = {
            identifier: self.memory.stable_document_tokens(identifier)
            for identifier in self._first_event_by_class
        }
        document_count = len(documents)
        weights = {}
        for token in self.retained_tokens:
            frequency = sum(token in tokens for tokens in documents.values())
            weight = math.log((document_count + 1) / (frequency + 1)) + 1.0
            if token not in self.initial_screen_tokens:
                weight *= 2.0
            weights[token] = weight
        denominator = sum(weights.values())
        scores = {
            identifier: sum(weight for token, weight in weights.items() if token in tokens) / denominator
            for identifier, tokens in documents.items()
        }
        ranked = sorted(
            scores,
            key=lambda identifier: (
                -scores[identifier],
                self._first_event_by_class[identifier].query_index,
                self.memory.class_by_identifier(identifier).class_index,
            ),
        )
        best = ranked[0]
        runner_up = scores[ranked[1]] if len(ranked) > 1 else 0.0
        return RobustEvidenceRanking(best, scores[best], runner_up, scores)
