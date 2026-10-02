"""Consolidate heterogeneous same-band proposals into physical action slots."""

from __future__ import annotations

import dataclasses
import statistics
from typing import Any, Iterable

from .screenshot_candidates import ScreenshotCandidate


STRUCTURAL_ACTION_SOURCES = frozenset({"component", "corner", "ocr", "action_band"})


@dataclasses.dataclass(frozen=True)
class ActionSlotConfig:
    horizontal_merge_pixels: float = 20.0
    point_box_half_width: int = 18
    point_box_half_height: int = 14

    def __post_init__(self) -> None:
        if self.horizontal_merge_pixels <= 0.0:
            raise ValueError("horizontal merge must be positive")
        if self.point_box_half_width <= 0 or self.point_box_half_height <= 0:
            raise ValueError("action-slot half sizes must be positive")


@dataclasses.dataclass(frozen=True)
class ActionSlotAudit:
    input_candidates: int
    structural_candidates: int
    nonstructural_candidates_dropped: int
    x_clusters: int
    slots: int
    source_candidate_ids: tuple[tuple[str, ...], ...]


def _candidate_point(candidate: Any) -> tuple[float, float]:
    point = getattr(candidate, "point")
    return float(point[0]), float(point[1])


def _candidate_source(candidate: Any) -> str:
    return str(getattr(candidate, "source", ""))


def _candidate_id(candidate: Any) -> str:
    return str(getattr(candidate, "proposal_id", ""))


def _x_clusters(candidates: list[Any], merge: float) -> list[list[Any]]:
    clusters: list[list[Any]] = []
    for candidate in sorted(
        candidates,
        key=lambda row: (_candidate_point(row)[0], _candidate_point(row)[1], _candidate_id(row)),
    ):
        x = _candidate_point(candidate)[0]
        if not clusters:
            clusters.append([candidate])
            continue
        prior_x = max(_candidate_point(row)[0] for row in clusters[-1])
        if x - prior_x < merge:
            clusters[-1].append(candidate)
        else:
            clusters.append([candidate])
    return clusters


def consolidate_action_slots(
    candidates: Iterable[Any],
    *,
    image_width: int,
    image_height: int,
    config: ActionSlotConfig | None = None,
) -> tuple[list[ScreenshotCandidate], ActionSlotAudit]:
    """Emit one fixed-support candidate per structural x cluster."""

    cfg = config or ActionSlotConfig()
    rows = list(candidates)
    if image_width <= 0 or image_height <= 0:
        raise ValueError("image dimensions must be positive")
    # Coverage proposals are task-blind exploration points, not evidence for a
    # physical control.  Remove them *before* clustering so a chain of nearby
    # coverage points cannot bridge two distinct buttons into one slot.
    structural_rows = [
        candidate
        for candidate in rows
        if _candidate_source(candidate) in STRUCTURAL_ACTION_SOURCES
    ]
    clusters = _x_clusters(structural_rows, cfg.horizontal_merge_pixels)
    slots = []
    sources = []
    for cluster in clusters:
        x = statistics.median(_candidate_point(candidate)[0] for candidate in cluster)
        y = statistics.median(_candidate_point(candidate)[1] for candidate in cluster)
        left = max(0, int(round(x)) - cfg.point_box_half_width)
        top = max(0, int(round(y)) - cfg.point_box_half_height)
        right = min(image_width, int(round(x)) + cfg.point_box_half_width)
        bottom = min(image_height, int(round(y)) + cfg.point_box_half_height)
        if right <= left or bottom <= top:
            raise ValueError("empty consolidated action slot")
        ordinal = len(slots)
        source_ids = tuple(sorted(_candidate_id(candidate) for candidate in cluster))
        sources.append(source_ids)
        slots.append(
            ScreenshotCandidate(
                proposal_id=f"action_slot_{ordinal:03d}",
                source="action_band",
                source_proposal_id=f"action_band_{ordinal:03d}",
                source_ordinal=ordinal,
                score=max(float(getattr(candidate, "score", 0.0)) for candidate in cluster),
                point=(x, y),
                bbox_xyxy=(left, top, right, bottom),
                # Icon OCR is deliberately discarded after C418F showed that
                # dark physical icons receive arbitrary lexical hallucinations.
                text="",
            )
        )
    return slots, ActionSlotAudit(
        input_candidates=len(rows),
        structural_candidates=len(structural_rows),
        nonstructural_candidates_dropped=len(rows) - len(structural_rows),
        x_clusters=len(clusters),
        slots=len(slots),
        source_candidate_ids=tuple(sources),
    )
