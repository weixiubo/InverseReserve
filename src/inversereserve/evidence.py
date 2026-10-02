"""Online, observation-only evidence scoring for RC-RPS."""

from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass

from .interface import QueryEvent

TOKEN_PATTERN = re.compile(r"[a-z0-9]+(?:[.-][a-z0-9]+)*")


def tokenize(text: str) -> set[str]:
    """Return normalized tokens while preserving and splitting compounds."""

    tokens: set[str] = set()
    for match in TOKEN_PATTERN.findall(text.lower()):
        tokens.add(match)
        if "-" in match:
            tokens.update(part for part in match.split("-") if part)
    return tokens


def retain_instruction_tokens(text: str, stopwords: set[str]) -> tuple[str, ...]:
    """Extract evidence-bearing tokens without consulting preview evidence."""

    retained = []
    for token in sorted(tokenize(text)):
        if token in stopwords:
            continue
        if "-" in token and all(part in stopwords for part in token.split("-")):
            continue
        retained.append(token)
    return tuple(retained)


@dataclass(frozen=True)
class EvidenceDecision:
    """A threshold-passing evidence object selected by the controller."""

    point: tuple[float, float]
    evidence: str
    first_query_index: int
    score: float
    runner_up_score: float


@dataclass(frozen=True)
class EvidenceRanking:
    best_evidence: str | None
    best_score: float
    runner_up_score: float
    scores: dict[str, float]


class OnlineEvidenceTracker:
    """Score only evidence strings observed by the current task trace."""

    def __init__(
        self,
        *,
        instruction: str,
        initial_screen_tokens: set[str],
        stopwords: set[str],
        absolute_threshold: float,
        margin_threshold: float,
    ) -> None:
        self.retained_tokens = retain_instruction_tokens(instruction, stopwords)
        self.initial_screen_tokens = set(initial_screen_tokens)
        self.absolute_threshold = float(absolute_threshold)
        self.margin_threshold = float(margin_threshold)
        self._first_event_by_evidence: dict[str, QueryEvent] = {}

    @property
    def observed_evidence_count(self) -> int:
        return len(self._first_event_by_evidence)

    def observe(self, event: QueryEvent) -> EvidenceDecision | None:
        if event.positive and event.evidence.strip():
            self._first_event_by_evidence.setdefault(event.evidence, event)
        ranking = self.rank()
        if ranking.best_evidence is None:
            return None
        if ranking.best_score + 1e-12 < self.absolute_threshold:
            return None
        if ranking.best_score - ranking.runner_up_score + 1e-12 < self.margin_threshold:
            return None
        first = self._first_event_by_evidence[ranking.best_evidence]
        return EvidenceDecision(
            point=first.point,
            evidence=ranking.best_evidence,
            first_query_index=first.query_index,
            score=ranking.best_score,
            runner_up_score=ranking.runner_up_score,
        )

    def rank(self) -> EvidenceRanking:
        if not self.retained_tokens or not self._first_event_by_evidence:
            return EvidenceRanking(None, 0.0, 0.0, {})
        document_tokens = {evidence: tokenize(evidence) for evidence in self._first_event_by_evidence}
        document_count = len(document_tokens)
        weights = {}
        for token in self.retained_tokens:
            frequency = sum(token in tokens for tokens in document_tokens.values())
            weight = math.log((document_count + 1) / (frequency + 1)) + 1.0
            if token not in self.initial_screen_tokens:
                weight *= 2.0
            weights[token] = weight
        denominator = sum(weights.values())
        scores = {
            evidence: sum(weight for token, weight in weights.items() if token in tokens) / denominator
            for evidence, tokens in document_tokens.items()
        }
        ranked = sorted(
            scores,
            key=lambda evidence: (
                -scores[evidence],
                self._first_event_by_evidence[evidence].query_index,
                hashlib.sha256(evidence.encode("utf-8")).hexdigest(),
            ),
        )
        best = ranked[0]
        runner_up = scores[ranked[1]] if len(ranked) > 1 else 0.0
        return EvidenceRanking(best, scores[best], runner_up, scores)
