"""Conservative pixel-only candidate text extraction primitives."""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from typing import Any, Iterable


@dataclass(frozen=True)
class CandidateTextConsensus:
    """A uniquely repeated normalized candidate label."""

    normalized_text: str
    agreement: int
    nonempty_views: int
    runner_up_agreement: int


def normalize_candidate_text(value: str) -> str:
    """Normalize visible ASCII words without semantic correction."""

    return " ".join(re.findall(r"[a-z0-9]+", str(value).lower()))


def candidate_text_consensus(
    view_texts: Iterable[str],
    *,
    minimum_agreement: int = 2,
) -> CandidateTextConsensus | None:
    """Accept only a unique repeated nonempty OCR string."""

    if minimum_agreement <= 0:
        raise ValueError("minimum_agreement must be positive")
    normalized = [normalize_candidate_text(value) for value in view_texts]
    retained = [value for value in normalized if value]
    if not retained:
        return None
    counts = Counter(retained)
    ordered = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    best_text, best_count = ordered[0]
    runner_up = ordered[1][1] if len(ordered) > 1 else 0
    if best_count < minimum_agreement or best_count == runner_up:
        return None
    return CandidateTextConsensus(
        normalized_text=best_text,
        agreement=best_count,
        nonempty_views=len(retained),
        runner_up_agreement=runner_up,
    )


def candidate_support_crop(
    image: Any,
    bbox_xyxy: tuple[float, float, float, float],
    *,
    padding: int = 4,
) -> Any:
    """Crop an unannotated candidate support box using frozen rounding."""

    if padding < 0:
        raise ValueError("padding must be nonnegative")
    rgb = image.convert("RGB")
    left = max(0, min(rgb.width, int(math.floor(bbox_xyxy[0])) - padding))
    top = max(0, min(rgb.height, int(math.floor(bbox_xyxy[1])) - padding))
    right = max(0, min(rgb.width, int(math.ceil(bbox_xyxy[2])) + padding))
    bottom = max(0, min(rgb.height, int(math.ceil(bbox_xyxy[3])) + padding))
    if right <= left or bottom <= top:
        raise ValueError("candidate bbox must have positive clipped area")
    return rgb.crop((left, top, right, bottom))
