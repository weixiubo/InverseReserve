"""Directional refinement for actions attached below or beside an entity label."""

from __future__ import annotations

import dataclasses
from typing import Any, Iterable

from inversereserve.observations.click_preview import WordBox
from inversereserve.observations.factorized_binding import (
    EntityAnchor,
    EntityScopeConfig,
    EntityScopeDecision,
    scope_candidates_to_entity,
)


@dataclasses.dataclass(frozen=True)
class DirectionalScopeConfig:
    """Reject controls belonging to a preceding rendered row."""

    maximum_normalized_above_offset: float = 0.5

    def __post_init__(self) -> None:
        if self.maximum_normalized_above_offset < 0.0:
            raise ValueError("maximum_normalized_above_offset must be nonnegative")


@dataclasses.dataclass(frozen=True)
class DirectionalScopedCandidate:
    candidate_id: str
    normalized_above_offset: float


@dataclasses.dataclass(frozen=True)
class DirectionalScopeDecision:
    applied: bool
    entity_tokens: tuple[str, ...]
    anchors: tuple[EntityAnchor, ...]
    base_decision: EntityScopeDecision
    retained: tuple[DirectionalScopedCandidate, ...]
    reason: str


def _candidate_id(candidate: Any) -> str:
    return str(getattr(candidate, "proposal_id", getattr(candidate, "candidate_id", "")))


def _candidate_bbox(candidate: Any) -> tuple[float, float, float, float]:
    value = candidate.bbox_xyxy
    return tuple(float(item) for item in value)  # type: ignore[return-value]


def _above_offset(candidate: Any, anchors: tuple[EntityAnchor, ...]) -> float:
    box = _candidate_bbox(candidate)
    center_y = (box[1] + box[3]) / 2.0
    candidate_height = max(1.0, box[3] - box[1])
    values = []
    for anchor in anchors:
        anchor_box = tuple(float(value) for value in anchor.bbox_xyxy)
        anchor_y = (anchor_box[1] + anchor_box[3]) / 2.0
        anchor_height = max(1.0, anchor_box[3] - anchor_box[1])
        scale = max(8.0, candidate_height, anchor_height)
        values.append((abs(center_y - anchor_y), (anchor_y - center_y) / scale))
    return min(values)[1]


def scope_action_candidates_to_entity(
    *,
    instruction: str,
    words: Iterable[WordBox],
    candidates: Iterable[Any],
    entity_config: EntityScopeConfig | None = None,
    directional_config: DirectionalScopeConfig | None = None,
) -> tuple[list[Any], DirectionalScopeDecision]:
    """Apply entity-row scope, then remove controls substantially above it."""

    rows = list(candidates)
    base_rows, base = scope_candidates_to_entity(
        instruction=instruction,
        words=words,
        candidates=rows,
        config=entity_config,
    )
    if not base.applied or not base.anchors or not base_rows:
        return base_rows, DirectionalScopeDecision(
            applied=base.applied,
            entity_tokens=base.entity_tokens,
            anchors=base.anchors,
            base_decision=base,
            retained=(),
            reason=base.reason,
        )
    cfg = directional_config or DirectionalScopeConfig()
    offsets = {_candidate_id(candidate): _above_offset(candidate, base.anchors) for candidate in base_rows}
    retained = [
        candidate
        for candidate in base_rows
        if offsets[_candidate_id(candidate)] <= cfg.maximum_normalized_above_offset + 1e-12
    ]
    retained.sort(
        key=lambda candidate: (
            abs(offsets[_candidate_id(candidate)]),
            _candidate_id(candidate),
        )
    )
    audit = tuple(
        DirectionalScopedCandidate(
            candidate_id=_candidate_id(candidate),
            normalized_above_offset=offsets[_candidate_id(candidate)],
        )
        for candidate in retained
    )
    return retained, DirectionalScopeDecision(
        applied=True,
        entity_tokens=base.entity_tokens,
        anchors=base.anchors,
        base_decision=base,
        retained=audit,
        reason="directionally_scoped" if retained else "no_nonpreceding_candidate",
    )
