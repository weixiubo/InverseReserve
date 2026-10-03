"""Task-blind physical-action band scope for deployed screenshot proposals."""

from __future__ import annotations

import dataclasses
import statistics
from typing import Any, Iterable

from inversereserve.observations.click_preview import WordBox
from inversereserve.observations.factorized_action_binding import (
    DirectionalScopeConfig,
    DirectionalScopeDecision,
    scope_action_candidates_to_entity,
)
from inversereserve.observations.factorized_binding import EntityAnchor, EntityScopeConfig, entity_anchors
from inversereserve.observations.preview_transaction import instruction_target_tokens, normalized_tokens


@dataclasses.dataclass(frozen=True)
class ActionBandScopeConfig:
    minimum_normalized_below_offset: float = 2.5
    maximum_normalized_below_offset: float = 6.0
    band_height_multiplier: float = 1.0
    minimum_band_pixels: float = 10.0
    horizontal_merge_pixels: float = 20.0
    minimum_structural_x_clusters: int = 3

    def __post_init__(self) -> None:
        if self.minimum_normalized_below_offset < 0.0:
            raise ValueError("minimum below offset must be nonnegative")
        if self.maximum_normalized_below_offset <= self.minimum_normalized_below_offset:
            raise ValueError("maximum below offset must exceed minimum")
        if self.band_height_multiplier <= 0.0 or self.minimum_band_pixels <= 0.0:
            raise ValueError("band scale must be positive")
        if self.horizontal_merge_pixels <= 0.0:
            raise ValueError("horizontal merge must be positive")
        if self.minimum_structural_x_clusters <= 0:
            raise ValueError("minimum structural clusters must be positive")


@dataclasses.dataclass(frozen=True)
class ActionBandCandidate:
    candidate_id: str
    normalized_below_offset: float
    band_center_y: float


@dataclasses.dataclass(frozen=True)
class ActionBandScopeDecision:
    applied: bool
    entity_tokens: tuple[str, ...]
    anchors: tuple[EntityAnchor, ...]
    used_action_band: bool
    band_center_y: float | None
    structural_x_clusters: int
    retained: tuple[ActionBandCandidate, ...]
    fallback_decision: DirectionalScopeDecision
    reason: str


def _candidate_id(candidate: Any) -> str:
    return str(getattr(candidate, "proposal_id", getattr(candidate, "candidate_id", "")))


def _candidate_source(candidate: Any) -> str:
    return str(getattr(candidate, "source", ""))


def _candidate_text(candidate: Any) -> str:
    return str(getattr(candidate, "text", "") or "")


def _candidate_bbox(candidate: Any) -> tuple[float, float, float, float]:
    return tuple((float(value) for value in candidate.bbox_xyxy))


def _candidate_point(candidate: Any) -> tuple[float, float]:
    value = getattr(candidate, "point", None)
    if value is not None:
        return (float(value[0]), float(value[1]))
    box = _candidate_bbox(candidate)
    return ((box[0] + box[2]) / 2.0, (box[1] + box[3]) / 2.0)


def _best_anchor_offset(candidate: Any, anchors: tuple[EntityAnchor, ...]) -> tuple[float, float]:
    _x, y = _candidate_point(candidate)
    values = []
    for anchor in anchors:
        anchor_y = (anchor.bbox_xyxy[1] + anchor.bbox_xyxy[3]) / 2.0
        anchor_height = max(1.0, anchor.bbox_xyxy[3] - anchor.bbox_xyxy[1])
        scale = max(8.0, anchor_height)
        values.append(((y - anchor_y) / scale, abs(y - anchor_y)))
    return min(values, key=lambda row: row[1])


def _x_clusters(candidates: list[Any], merge: float) -> int:
    xs = sorted((_candidate_point(candidate)[0] for candidate in candidates))
    if not xs:
        return 0
    clusters = 1
    prior = xs[0]
    for value in xs[1:]:
        if value - prior >= merge:
            clusters += 1
        prior = value
    return clusters


def _bands(candidates: list[Any], tolerance: float) -> list[list[Any]]:
    rows: list[list[Any]] = []
    for candidate in sorted(candidates, key=lambda row: _candidate_point(row)[1]):
        y = _candidate_point(candidate)[1]
        destination = None
        for band in rows:
            center = statistics.fmean((_candidate_point(row)[1] for row in band))
            if abs(y - center) <= tolerance:
                destination = band
                break
        if destination is None:
            rows.append([candidate])
        else:
            destination.append(candidate)
    return rows


def scope_deployed_action_candidates(
    *,
    instruction: str,
    words: Iterable[WordBox],
    candidates: Iterable[Any],
    entity_config: EntityScopeConfig | None = None,
    directional_config: DirectionalScopeConfig | None = None,
    band_config: ActionBandScopeConfig | None = None,
) -> tuple[list[Any], ActionBandScopeDecision]:
    """Prefer a repeated physical-control band below an explicit entity label."""
    word_rows = list(words)
    candidate_rows = list(candidates)
    fallback_rows, fallback = scope_action_candidates_to_entity(
        instruction=instruction,
        words=word_rows,
        candidates=candidate_rows,
        entity_config=entity_config,
        directional_config=directional_config,
    )
    anchors = entity_anchors(instruction, word_rows)
    if not anchors:
        return (
            fallback_rows,
            ActionBandScopeDecision(
                applied=fallback.applied,
                entity_tokens=fallback.entity_tokens,
                anchors=(),
                used_action_band=False,
                band_center_y=None,
                structural_x_clusters=0,
                retained=(),
                fallback_decision=fallback,
                reason=fallback.reason,
            ),
        )
    cfg = band_config or ActionBandScopeConfig()
    target_tokens = set(instruction_target_tokens(instruction))
    eligible, offsets = _eligible_band_candidates(candidate_rows, target_tokens, anchors, cfg)
    anchor_height = statistics.median(
        (max(1.0, anchor.bbox_xyxy[3] - anchor.bbox_xyxy[1]) for anchor in anchors)
    )
    tolerance = max(cfg.minimum_band_pixels, cfg.band_height_multiplier * anchor_height)
    candidates_by_band = _bands(eligible, tolerance)
    scored = []
    for band in candidates_by_band:
        structural = [
            candidate for candidate in band if _candidate_source(candidate) in {"component", "corner"}
        ]
        structural_clusters = _x_clusters(structural, cfg.horizontal_merge_pixels)
        all_clusters = _x_clusters(band, cfg.horizontal_merge_pixels)
        center_y = statistics.fmean((_candidate_point(row)[1] for row in band))
        scored.append((structural_clusters, all_clusters, len(structural), -center_y, band))
    qualified = [row for row in scored if row[0] >= cfg.minimum_structural_x_clusters]
    if not qualified:
        return (
            fallback_rows,
            ActionBandScopeDecision(
                applied=True,
                entity_tokens=fallback.entity_tokens,
                anchors=anchors,
                used_action_band=False,
                band_center_y=None,
                structural_x_clusters=0,
                retained=(),
                fallback_decision=fallback,
                reason="no_repeated_action_band_fallback",
            ),
        )
    best = max(qualified, key=lambda row: row[:4])
    band = best[4]
    center_y = statistics.fmean((_candidate_point(row)[1] for row in band))
    band.sort(
        key=lambda candidate: (
            _candidate_point(candidate)[0],
            _candidate_source(candidate),
            _candidate_id(candidate),
        )
    )
    retained = tuple(
        (
            ActionBandCandidate(
                candidate_id=_candidate_id(candidate),
                normalized_below_offset=offsets[_candidate_id(candidate)],
                band_center_y=center_y,
            )
            for candidate in band
        )
    )
    return (
        band,
        ActionBandScopeDecision(
            applied=True,
            entity_tokens=fallback.entity_tokens,
            anchors=anchors,
            used_action_band=True,
            band_center_y=center_y,
            structural_x_clusters=int(best[0]),
            retained=retained,
            fallback_decision=fallback,
            reason="repeated_action_band",
        ),
    )


def _eligible_band_candidates(
    candidate_rows: list[Any],
    target_tokens: set[str],
    anchors: tuple[EntityAnchor, ...],
    cfg: ActionBandScopeConfig,
) -> tuple[list[Any], dict[str, float]]:
    eligible = []
    offsets = {}
    for candidate in candidate_rows:
        text_tokens = set(normalized_tokens(_candidate_text(candidate)))
        if text_tokens and (not target_tokens & text_tokens):
            continue
        offset, _distance = _best_anchor_offset(candidate, anchors)
        if not cfg.minimum_normalized_below_offset <= offset <= cfg.maximum_normalized_below_offset:
            continue
        offsets[_candidate_id(candidate)] = offset
        eligible.append(candidate)
    return (eligible, offsets)
