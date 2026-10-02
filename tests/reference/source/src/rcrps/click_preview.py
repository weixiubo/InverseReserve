"""Surface-independent click-risk gating and evidence-local commit binding."""

from __future__ import annotations

import csv
import math
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from .evidence import retain_instruction_tokens, tokenize


@dataclass(frozen=True)
class ClickRiskGate:
    """A frozen upper-risk threshold for proposed click previews."""

    maximum_risk: float

    def __post_init__(self) -> None:
        if not 0.0 <= self.maximum_risk <= 1.0:
            raise ValueError("maximum_risk must be in [0, 1]")

    def allows(self, risk_score: float) -> bool:
        if not math.isfinite(risk_score) or not 0.0 <= risk_score <= 1.0:
            return False
        return risk_score <= self.maximum_risk + 1e-12


@dataclass(frozen=True)
class CandidateProvenanceConfig:
    """Pixel-only rule for deciding whether a control appeared after preview."""

    pixel_threshold: int = 12
    minimum_changed_pixels: int = 16
    minimum_changed_fraction: float = 0.02

    def __post_init__(self) -> None:
        if self.pixel_threshold < 0:
            raise ValueError("pixel_threshold must be nonnegative")
        if self.minimum_changed_pixels <= 0:
            raise ValueError("minimum_changed_pixels must be positive")
        if not 0.0 < self.minimum_changed_fraction <= 1.0:
            raise ValueError("minimum_changed_fraction must be in (0, 1]")


@dataclass(frozen=True)
class CandidateProvenance:
    """Observed pixel provenance for one candidate support box."""

    bbox_xyxy: tuple[int, int, int, int]
    changed_pixels: int
    total_pixels: int
    changed_fraction: float
    novel: bool


@dataclass(frozen=True)
class ProvenanceRiskDecision:
    """Joint structural-provenance and calibrated-risk decision."""

    allowed: bool
    reason: str
    risk_score: float
    provenance: CandidateProvenance


@dataclass(frozen=True)
class StateProvenanceRiskGate:
    """Permit click previews only for old controls below a frozen risk bound."""

    maximum_risk: float

    def __post_init__(self) -> None:
        ClickRiskGate(self.maximum_risk)

    def decide(
        self,
        *,
        risk_score: float,
        provenance: CandidateProvenance,
    ) -> ProvenanceRiskDecision:
        if provenance.novel:
            return ProvenanceRiskDecision(
                allowed=False,
                reason="novel_control_reserved_for_evidence_bound_commit",
                risk_score=float(risk_score),
                provenance=provenance,
            )
        if not math.isfinite(risk_score) or not 0.0 <= risk_score <= 1.0:
            reason = "invalid_risk_score"
            allowed = False
        elif risk_score > self.maximum_risk + 1e-12:
            reason = "risk_above_frozen_threshold"
            allowed = False
        else:
            reason = "old_control_below_frozen_threshold"
            allowed = True
        return ProvenanceRiskDecision(
            allowed=allowed,
            reason=reason,
            risk_score=float(risk_score),
            provenance=provenance,
        )


@dataclass(frozen=True)
class WordBox:
    """One screenshot-OCR word with absolute pixel provenance."""

    text: str
    bbox_xyxy: tuple[int, int, int, int]
    confidence: float
    block: int = 0
    paragraph: int = 0
    line: int = 0


@dataclass(frozen=True)
class LocalizedCommit:
    """Instruction-matching text localized inside one response surface."""

    point: tuple[float, float]
    bbox_xyxy: tuple[int, int, int, int]
    text: str
    matched_tokens: tuple[str, ...]
    novel_matched_tokens: tuple[str, ...]
    confidence: float


def restricted_binary_probability(
    first_logit: float,
    second_logit: float,
) -> float:
    """Return the second class probability under a two-token softmax."""

    if not math.isfinite(first_logit) or not math.isfinite(second_logit):
        raise ValueError("binary logits must be finite")
    difference = float(first_logit) - float(second_logit)
    if difference >= 0.0:
        exponent = math.exp(-difference)
        return exponent / (1.0 + exponent)
    exponent = math.exp(difference)
    return 1.0 / (1.0 + exponent)


def label_symmetric_risk(
    *,
    safe_a_risky_b_logits: tuple[float, float],
    risky_a_safe_b_logits: tuple[float, float],
) -> float:
    """Average risky probability across an A/B label-order swap."""

    risky_when_b = restricted_binary_probability(*safe_a_risky_b_logits)
    safe_when_b = restricted_binary_probability(*risky_a_safe_b_logits)
    risky_when_a = 1.0 - safe_when_b
    return (risky_when_b + risky_when_a) / 2.0


def candidate_provenance(
    reference: Any,
    current: Any,
    bbox_xyxy: tuple[int, int, int, int],
    config: CandidateProvenanceConfig | None = None,
) -> CandidateProvenance:
    """Measure whether a candidate support box appeared after the reference."""

    import numpy as np

    cfg = config or CandidateProvenanceConfig()
    reference_pixels = np.asarray(reference.convert("RGB"), dtype=np.int16)
    current_pixels = np.asarray(current.convert("RGB"), dtype=np.int16)
    if reference_pixels.shape != current_pixels.shape:
        raise ValueError(
            f"image shapes differ: {reference_pixels.shape} != {current_pixels.shape}"
        )
    height, width = current_pixels.shape[:2]
    left = max(0, min(width, int(math.floor(bbox_xyxy[0]))))
    top = max(0, min(height, int(math.floor(bbox_xyxy[1]))))
    right = max(0, min(width, int(math.ceil(bbox_xyxy[2]))))
    bottom = max(0, min(height, int(math.ceil(bbox_xyxy[3]))))
    if right <= left or bottom <= top:
        raise ValueError("candidate bbox must have positive clipped area")
    difference = np.max(
        np.abs(
            current_pixels[top:bottom, left:right]
            - reference_pixels[top:bottom, left:right]
        ),
        axis=2,
    )
    changed_pixels = int((difference >= cfg.pixel_threshold).sum())
    total_pixels = int(difference.size)
    changed_fraction = changed_pixels / total_pixels
    novel = (
        changed_pixels >= cfg.minimum_changed_pixels
        and changed_fraction + 1e-12 >= cfg.minimum_changed_fraction
    )
    return CandidateProvenance(
        bbox_xyxy=(left, top, right, bottom),
        changed_pixels=changed_pixels,
        total_pixels=total_pixels,
        changed_fraction=changed_fraction,
        novel=novel,
    )


def candidate_context_crop(
    image: Any,
    point: tuple[float, float],
    *,
    half_width: int = 160,
    half_height: int = 96,
    output_size: tuple[int, int] = (640, 384),
    bracket_radius: int = 20,
    bracket_length: int = 8,
    bracket_width: int = 3,
) -> Any:
    """Return a local target view marked by non-occluding corner brackets."""

    from PIL import ImageDraw

    for name, value in (
        ("half_width", half_width),
        ("half_height", half_height),
        ("bracket_radius", bracket_radius),
        ("bracket_length", bracket_length),
        ("bracket_width", bracket_width),
    ):
        if value <= 0:
            raise ValueError(f"{name} must be positive")
    if output_size[0] <= 0 or output_size[1] <= 0:
        raise ValueError("output_size must be positive")
    rgb = image.convert("RGB")
    x, y = float(point[0]), float(point[1])
    left = max(0, int(math.floor(x - half_width)))
    top = max(0, int(math.floor(y - half_height)))
    right = min(rgb.width, int(math.ceil(x + half_width)))
    bottom = min(rgb.height, int(math.ceil(y + half_height)))
    if right <= left or bottom <= top:
        raise ValueError("candidate point lies outside the image")
    crop = rgb.crop((left, top, right, bottom))
    center_x = x - left
    center_y = y - top
    draw = ImageDraw.Draw(crop)
    color = (255, 0, 0)
    inner_left = center_x - bracket_radius
    inner_right = center_x + bracket_radius
    inner_top = center_y - bracket_radius
    inner_bottom = center_y + bracket_radius
    segments = (
        (inner_left, inner_top, inner_left + bracket_length, inner_top),
        (inner_left, inner_top, inner_left, inner_top + bracket_length),
        (inner_right - bracket_length, inner_top, inner_right, inner_top),
        (inner_right, inner_top, inner_right, inner_top + bracket_length),
        (inner_left, inner_bottom, inner_left + bracket_length, inner_bottom),
        (inner_left, inner_bottom - bracket_length, inner_left, inner_bottom),
        (inner_right - bracket_length, inner_bottom, inner_right, inner_bottom),
        (inner_right, inner_bottom - bracket_length, inner_right, inner_bottom),
    )
    for segment in segments:
        draw.line(segment, fill=color, width=bracket_width)
    return crop.resize(output_size)


def candidate_box_context_crop(
    image: Any,
    bbox_xyxy: tuple[float, float, float, float],
    *,
    padding: int = 32,
    maximum_size: tuple[int, int] = (768, 384),
    maximum_upscale: float = 2.0,
    bracket_offset: int = 4,
    bracket_length: int = 12,
    bracket_width: int = 3,
) -> Any:
    """Show the full candidate box with context and non-occluding brackets."""

    from PIL import Image, ImageDraw

    if padding < 0:
        raise ValueError("padding must be nonnegative")
    for name, value in (
        ("bracket_offset", bracket_offset),
        ("bracket_length", bracket_length),
        ("bracket_width", bracket_width),
    ):
        if value <= 0:
            raise ValueError(f"{name} must be positive")
    if maximum_size[0] <= 0 or maximum_size[1] <= 0:
        raise ValueError("maximum_size must be positive")
    if maximum_upscale <= 0.0:
        raise ValueError("maximum_upscale must be positive")
    rgb = image.convert("RGB")
    box_left = max(0, min(rgb.width, int(math.floor(bbox_xyxy[0]))))
    box_top = max(0, min(rgb.height, int(math.floor(bbox_xyxy[1]))))
    box_right = max(0, min(rgb.width, int(math.ceil(bbox_xyxy[2]))))
    box_bottom = max(0, min(rgb.height, int(math.ceil(bbox_xyxy[3]))))
    if box_right <= box_left or box_bottom <= box_top:
        raise ValueError("candidate bbox must have positive clipped area")
    crop_left = max(0, box_left - padding)
    crop_top = max(0, box_top - padding)
    crop_right = min(rgb.width, box_right + padding)
    crop_bottom = min(rgb.height, box_bottom + padding)
    crop = rgb.crop((crop_left, crop_top, crop_right, crop_bottom))
    left = box_left - crop_left
    top = box_top - crop_top
    right = box_right - crop_left
    bottom = box_bottom - crop_top
    draw = ImageDraw.Draw(crop)
    color = (255, 0, 0)
    outer_left = max(0, left - bracket_offset)
    outer_top = max(0, top - bracket_offset)
    outer_right = min(crop.width - 1, right + bracket_offset)
    outer_bottom = min(crop.height - 1, bottom + bracket_offset)
    segments = (
        (outer_left, outer_top, outer_left + bracket_length, outer_top),
        (outer_left, outer_top, outer_left, outer_top + bracket_length),
        (outer_right - bracket_length, outer_top, outer_right, outer_top),
        (outer_right, outer_top, outer_right, outer_top + bracket_length),
        (outer_left, outer_bottom, outer_left + bracket_length, outer_bottom),
        (outer_left, outer_bottom - bracket_length, outer_left, outer_bottom),
        (outer_right - bracket_length, outer_bottom, outer_right, outer_bottom),
        (outer_right, outer_bottom - bracket_length, outer_right, outer_bottom),
    )
    for segment in segments:
        draw.line(segment, fill=color, width=bracket_width)
    scale = min(
        maximum_size[0] / crop.width,
        maximum_size[1] / crop.height,
        maximum_upscale,
    )
    output_size = (
        max(1, int(round(crop.width * scale))),
        max(1, int(round(crop.height * scale))),
    )
    if output_size != crop.size:
        crop = crop.resize(output_size, Image.Resampling.LANCZOS)
    return crop


def mark_click_coordinate(
    image: Any,
    point: tuple[float, float],
    *,
    radius: int = 16,
    width: int = 5,
) -> Any:
    """Return an RGB copy with a deterministic red cross at a proposed click."""

    from PIL import ImageDraw

    if radius <= 0 or width <= 0:
        raise ValueError("radius and width must be positive")
    output = image.convert("RGB").copy()
    x, y = (float(point[0]), float(point[1]))
    draw = ImageDraw.Draw(output)
    draw.ellipse(
        (x - radius, y - radius, x + radius, y + radius),
        outline=(255, 0, 0),
        width=width,
    )
    draw.line(
        (x - radius, y - radius, x + radius, y + radius),
        fill=(255, 0, 0),
        width=max(1, width - 1),
    )
    draw.line(
        (x - radius, y + radius, x + radius, y - radius),
        fill=(255, 0, 0),
        width=max(1, width - 1),
    )
    return output


def tesseract_word_boxes(
    image: Any,
    *,
    psm: int,
    scale: int,
    timeout_seconds: int = 30,
    offset_xy: tuple[int, int] = (0, 0),
    minimum_confidence: float = 0.0,
) -> tuple[WordBox, ...]:
    """Read positioned words from a screenshot crop through pinned Tesseract TSV."""

    from PIL import Image

    if scale <= 0 or timeout_seconds <= 0:
        raise ValueError("scale and timeout_seconds must be positive")
    rgb = image.convert("RGB")
    if scale != 1:
        rgb = rgb.resize(
            (rgb.width * scale, rgb.height * scale),
            resample=Image.Resampling.LANCZOS,
        )
    with tempfile.NamedTemporaryFile(suffix=".png") as handle:
        rgb.save(handle.name)
        process = subprocess.run(
            [
                "tesseract",
                handle.name,
                "stdout",
                "-l",
                "eng",
                "--oem",
                "3",
                "--psm",
                str(psm),
                "tsv",
            ],
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
            check=True,
        )
    output = []
    reader = csv.DictReader(process.stdout.splitlines(), delimiter="\t")
    offset_x, offset_y = offset_xy
    for row in reader:
        text = str(row.get("text") or "").strip()
        if not text:
            continue
        try:
            confidence = float(row["conf"])
            left = int(row["left"])
            top = int(row["top"])
            width = int(row["width"])
            height = int(row["height"])
            block = int(row["block_num"])
            paragraph = int(row["par_num"])
            line = int(row["line_num"])
        except (KeyError, TypeError, ValueError):
            continue
        if confidence < minimum_confidence or width <= 0 or height <= 0:
            continue
        x0 = offset_x + math.floor(left / scale)
        y0 = offset_y + math.floor(top / scale)
        x1 = offset_x + math.ceil((left + width) / scale)
        y1 = offset_y + math.ceil((top + height) / scale)
        output.append(
            WordBox(
                text=text,
                bbox_xyxy=(x0, y0, x1, y1),
                confidence=confidence,
                block=block,
                paragraph=paragraph,
                line=line,
            )
        )
    return tuple(output)


def _bbox_iou(
    left: tuple[int, int, int, int], right: tuple[int, int, int, int]
) -> float:
    x0 = max(left[0], right[0])
    y0 = max(left[1], right[1])
    x1 = min(left[2], right[2])
    y1 = min(left[3], right[3])
    intersection = max(0, x1 - x0) * max(0, y1 - y0)
    left_area = max(0, left[2] - left[0]) * max(0, left[3] - left[1])
    right_area = max(0, right[2] - right[0]) * max(0, right[3] - right[1])
    union = left_area + right_area - intersection
    return intersection / union if union else 0.0


def merge_word_box_views(
    views: Iterable[Iterable[WordBox]], *, iou_threshold: float = 0.5
) -> tuple[WordBox, ...]:
    """Deduplicate same-token OCR boxes while preserving higher-confidence geometry."""

    if not 0.0 < iou_threshold <= 1.0:
        raise ValueError("iou_threshold must be in (0, 1]")
    ordered = sorted(
        (box for view in views for box in view if tokenize(box.text)),
        key=lambda box: (
            -box.confidence,
            box.bbox_xyxy[1],
            box.bbox_xyxy[0],
            box.text.lower(),
        ),
    )
    retained: list[WordBox] = []
    for box in ordered:
        tokens = tokenize(box.text)
        if any(
            tokens == tokenize(prior.text)
            and _bbox_iou(box.bbox_xyxy, prior.bbox_xyxy) + 1e-12 >= iou_threshold
            for prior in retained
        ):
            continue
        retained.append(box)
    retained.sort(
        key=lambda box: (
            box.bbox_xyxy[1],
            box.bbox_xyxy[0],
            -box.confidence,
            box.text.lower(),
        )
    )
    return tuple(retained)


def _inside(
    inner: tuple[int, int, int, int], outer: tuple[int, int, int, int]
) -> bool:
    center_x = (inner[0] + inner[2]) / 2.0
    center_y = (inner[1] + inner[3]) / 2.0
    return outer[0] <= center_x <= outer[2] and outer[1] <= center_y <= outer[3]


def _line_spans(boxes: Iterable[WordBox], maximum_words: int) -> list[WordBox]:
    groups: dict[tuple[int, int, int], list[WordBox]] = {}
    for box in boxes:
        groups.setdefault((box.block, box.paragraph, box.line), []).append(box)
    spans = []
    for group in groups.values():
        ordered = sorted(group, key=lambda box: (box.bbox_xyxy[0], box.bbox_xyxy[1]))
        for start in range(len(ordered)):
            for length in range(1, min(maximum_words, len(ordered) - start) + 1):
                window = ordered[start : start + length]
                spans.append(
                    WordBox(
                        text=" ".join(box.text for box in window),
                        bbox_xyxy=(
                            min(box.bbox_xyxy[0] for box in window),
                            min(box.bbox_xyxy[1] for box in window),
                            max(box.bbox_xyxy[2] for box in window),
                            max(box.bbox_xyxy[3] for box in window),
                        ),
                        confidence=sum(box.confidence for box in window) / len(window),
                        block=window[0].block,
                        paragraph=window[0].paragraph,
                        line=window[0].line,
                    )
                )
    return spans


def localize_instruction_commit(
    *,
    instruction: str,
    initial_screen_tokens: set[str],
    stopwords: set[str],
    response_bbox_xyxy: tuple[int, int, int, int],
    word_boxes: Iterable[WordBox],
    maximum_words_per_span: int = 4,
) -> LocalizedCommit | None:
    """Bind novel instruction evidence to one OCR span inside a response surface."""

    if maximum_words_per_span <= 0:
        raise ValueError("maximum_words_per_span must be positive")
    retained = set(retain_instruction_tokens(instruction, stopwords))
    novel = retained - set(initial_screen_tokens)
    if not novel:
        return None
    eligible = [
        box for box in word_boxes if _inside(box.bbox_xyxy, response_bbox_xyxy)
    ]
    candidates = []
    for span in _line_spans(eligible, maximum_words_per_span):
        tokens = tokenize(span.text)
        novel_hits = tuple(sorted(tokens & novel))
        retained_hits = tuple(sorted(tokens & retained))
        if not (tokens & novel):
            continue
        unmatched_tokens = tokens - retained
        area = max(1, span.bbox_xyxy[2] - span.bbox_xyxy[0]) * max(
            1, span.bbox_xyxy[3] - span.bbox_xyxy[1]
        )
        semantic_key = (
            -len(novel_hits),
            -len(retained_hits),
            -sum("-" in token or "." in token for token in retained_hits),
            len(unmatched_tokens),
            len(tokens),
        )
        candidates.append(
            (
                semantic_key
                + (
                    area,
                    -span.confidence,
                    span.bbox_xyxy[1],
                    span.bbox_xyxy[0],
                    span.text.lower(),
                ),
                semantic_key,
                span,
                retained_hits,
                novel_hits,
            )
        )
    if not candidates:
        return None
    _, selected_semantics, selected, retained_hits, novel_hits = min(
        candidates, key=lambda row: row[0]
    )
    if any(
        semantics == selected_semantics
        and _bbox_iou(span.bbox_xyxy, selected.bbox_xyxy) < 0.5
        for _, semantics, span, _, _ in candidates
        if span is not selected
    ):
        return None
    left, top, right, bottom = selected.bbox_xyxy
    return LocalizedCommit(
        point=((left + right) / 2.0, (top + bottom) / 2.0),
        bbox_xyxy=selected.bbox_xyxy,
        text=selected.text,
        matched_tokens=retained_hits,
        novel_matched_tokens=novel_hits,
        confidence=selected.confidence,
    )
