"""C418F repair: retain icon candidates with noisy nonempty OCR."""

from __future__ import annotations

import statistics
from typing import Any, Iterable

from .click_preview import WordBox
from .deployed_action_scope import (
    ActionBandCandidate,
    ActionBandScopeConfig,
    ActionBandScopeDecision,
    _bands,
    _best_anchor_offset,
    _candidate_id,
    _candidate_point,
    _candidate_source,
    _x_clusters,
)
from .factorized_action_binding import (
    DirectionalScopeConfig,
    scope_action_candidates_to_entity,
)
from .factorized_binding import EntityScopeConfig, entity_anchors


def scope_deployed_action_candidates_v2(
    *,
    instruction: str,
    words: Iterable[WordBox],
    candidates: Iterable[Any],
    entity_config: EntityScopeConfig | None = None,
    directional_config: DirectionalScopeConfig | None = None,
    band_config: ActionBandScopeConfig | None = None,
) -> tuple[list[Any], ActionBandScopeDecision]:
    """Use the physical action band even when an icon receives noisy OCR."""

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
        return fallback_rows, ActionBandScopeDecision(
            applied=fallback.applied,
            entity_tokens=fallback.entity_tokens,
            anchors=(),
            used_action_band=False,
            band_center_y=None,
            structural_x_clusters=0,
            retained=(),
            fallback_decision=fallback,
            reason=fallback.reason,
        )
    cfg = band_config or ActionBandScopeConfig()
    eligible = []
    offsets = {}
    for candidate in candidate_rows:
        # C418F showed that dark Edit/Repost icons can receive arbitrary
        # nonempty Tesseract strings.  OCR is evidence, not a physical-control
        # veto: the below-entity repeated band supplies the structural filter.
        offset, _distance = _best_anchor_offset(candidate, anchors)
        if not (
            cfg.minimum_normalized_below_offset
            <= offset
            <= cfg.maximum_normalized_below_offset
        ):
            continue
        offsets[_candidate_id(candidate)] = offset
        eligible.append(candidate)
    anchor_height = statistics.median(
        max(1.0, anchor.bbox_xyxy[3] - anchor.bbox_xyxy[1])
        for anchor in anchors
    )
    tolerance = max(
        cfg.minimum_band_pixels,
        cfg.band_height_multiplier * anchor_height,
    )
    scored = []
    for band in _bands(eligible, tolerance):
        structural = [
            candidate
            for candidate in band
            if _candidate_source(candidate) in {"component", "corner", "ocr"}
        ]
        structural_clusters = _x_clusters(structural, cfg.horizontal_merge_pixels)
        all_clusters = _x_clusters(band, cfg.horizontal_merge_pixels)
        center_y = statistics.fmean(_candidate_point(row)[1] for row in band)
        scored.append(
            (structural_clusters, all_clusters, len(structural), -center_y, band)
        )
    qualified = [
        row for row in scored if row[0] >= cfg.minimum_structural_x_clusters
    ]
    if not qualified:
        return fallback_rows, ActionBandScopeDecision(
            applied=True,
            entity_tokens=fallback.entity_tokens,
            anchors=anchors,
            used_action_band=False,
            band_center_y=None,
            structural_x_clusters=0,
            retained=(),
            fallback_decision=fallback,
            reason="no_repeated_action_band_fallback_v2",
        )
    best = max(qualified, key=lambda row: row[:4])
    band = best[4]
    center_y = statistics.fmean(_candidate_point(row)[1] for row in band)
    band.sort(
        key=lambda candidate: (
            _candidate_point(candidate)[0],
            _candidate_source(candidate),
            _candidate_id(candidate),
        )
    )
    retained = tuple(
        ActionBandCandidate(
            candidate_id=_candidate_id(candidate),
            normalized_below_offset=offsets[_candidate_id(candidate)],
            band_center_y=center_y,
        )
        for candidate in band
    )
    return band, ActionBandScopeDecision(
        applied=True,
        entity_tokens=fallback.entity_tokens,
        anchors=anchors,
        used_action_band=True,
        band_center_y=center_y,
        structural_x_clusters=int(best[0]),
        retained=retained,
        fallback_decision=fallback,
        reason="repeated_action_band_v2",
    )

