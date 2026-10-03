"""Task-blind screenshot candidate proposals for external GUI evaluation."""

from __future__ import annotations

import math
from collections import deque
from dataclasses import asdict, dataclass
from typing import Any, Callable, Iterable

from .click_preview import WordBox, tesseract_word_boxes


@dataclass(frozen=True)
class ScreenshotCandidateConfig:
    """Frozen generic proposal geometry; no task field is accepted."""

    ocr_psm: int = 11
    ocr_scale: int = 2
    ocr_minimum_confidence: float = 50.0
    ocr_padding: int = 4
    corner_quality: float = 0.003
    corner_minimum_distance: float = 4.0
    maximum_ocr: int = 128
    maximum_corners: int = 128
    maximum_components: int = 128
    maximum_coverage: int = 128
    component_background_distance: float = 18.0
    component_minimum_area: int = 4
    component_maximum_area_fraction: float = 0.25
    point_box_half_width: int = 18
    point_box_half_height: int = 14
    merge_distance: float = 6.0
    global_cap: int = 128
    interleave_cycle: tuple[str, ...] = (
        "ocr",
        "structure",
        "structure",
        "coverage",
    )

    def __post_init__(self) -> None:
        positive_integer_fields = (
            "ocr_psm",
            "ocr_scale",
            "ocr_padding",
            "maximum_ocr",
            "maximum_corners",
            "maximum_components",
            "maximum_coverage",
            "component_minimum_area",
            "point_box_half_width",
            "point_box_half_height",
            "global_cap",
        )
        for name in positive_integer_fields:
            if int(getattr(self, name)) <= 0:
                raise ValueError(f"{name} must be positive")
        if not 0.0 <= self.ocr_minimum_confidence <= 100.0:
            raise ValueError("ocr_minimum_confidence must be in [0, 100]")
        if not 0.0 < self.corner_quality <= 1.0:
            raise ValueError("corner_quality must be in (0, 1]")
        if self.corner_minimum_distance <= 0.0:
            raise ValueError("corner_minimum_distance must be positive")
        if self.component_background_distance <= 0.0:
            raise ValueError("component_background_distance must be positive")
        if not 0.0 < self.component_maximum_area_fraction <= 1.0:
            raise ValueError("component_maximum_area_fraction must be in (0, 1]")
        if self.merge_distance < 0.0:
            raise ValueError("merge_distance must be nonnegative")
        if not self.interleave_cycle or set(self.interleave_cycle) != {
            "ocr",
            "structure",
            "coverage",
        }:
            raise ValueError("interleave_cycle must contain every frozen source")


@dataclass(frozen=True)
class ScreenshotCandidate:
    """One pixel-derived point and its visual support box."""

    proposal_id: str
    source: str
    source_proposal_id: str
    source_ordinal: int
    score: float
    point: tuple[float, float]
    bbox_xyxy: tuple[int, int, int, int]
    text: str = ""

    def to_json(self) -> dict[str, Any]:
        value = asdict(self)
        value["point"] = list(self.point)
        value["bbox_xyxy"] = list(self.bbox_xyxy)
        return value


def _point_box(
    point: tuple[float, float],
    width: int,
    height: int,
    config: ScreenshotCandidateConfig,
) -> tuple[int, int, int, int]:
    x, y = point
    left = max(0, int(math.floor(x - config.point_box_half_width)))
    top = max(0, int(math.floor(y - config.point_box_half_height)))
    right = min(width, int(math.ceil(x + config.point_box_half_width)))
    bottom = min(height, int(math.ceil(y + config.point_box_half_height)))
    if right <= left:
        right = min(width, left + 1)
    if bottom <= top:
        bottom = min(height, top + 1)
    return (left, top, right, bottom)


def _expanded_box(
    raw: tuple[int, int, int, int],
    width: int,
    height: int,
    padding: int,
) -> tuple[int, int, int, int]:
    return (
        max(0, int(raw[0]) - padding),
        max(0, int(raw[1]) - padding),
        min(width, int(raw[2]) + padding),
        min(height, int(raw[3]) + padding),
    )


def ocr_candidates(
    image: Any,
    config: ScreenshotCandidateConfig,
    *,
    extractor: Callable[..., tuple[WordBox, ...]] = tesseract_word_boxes,
) -> list[ScreenshotCandidate]:
    """Return positioned OCR words from screenshot pixels only."""

    rgb = image.convert("RGB")
    boxes = extractor(
        rgb,
        psm=config.ocr_psm,
        scale=config.ocr_scale,
        minimum_confidence=config.ocr_minimum_confidence,
    )
    ordered = sorted(
        boxes,
        key=lambda row: (
            -float(row.confidence),
            row.bbox_xyxy[1],
            row.bbox_xyxy[0],
            row.text.lower(),
        ),
    )[: config.maximum_ocr]
    rows = []
    for index, box in enumerate(ordered):
        bbox = _expanded_box(
            box.bbox_xyxy,
            rgb.width,
            rgb.height,
            config.ocr_padding,
        )
        rows.append(
            ScreenshotCandidate(
                proposal_id="",
                source="ocr",
                source_proposal_id=f"ocr_{index:03d}",
                source_ordinal=index,
                score=float(box.confidence) / 100.0,
                point=((bbox[0] + bbox[2]) / 2.0, (bbox[1] + bbox[3]) / 2.0),
                bbox_xyxy=bbox,
                text=str(box.text),
            )
        )
    return rows


def corner_candidates(
    image: Any,
    config: ScreenshotCandidateConfig,
) -> list[ScreenshotCandidate]:
    """Return Shi--Tomasi corners with deterministic point support."""

    import cv2
    import numpy as np

    pixels = np.asarray(image.convert("RGB"), dtype=np.uint8)
    height, width = pixels.shape[:2]
    gray = cv2.cvtColor(pixels, cv2.COLOR_RGB2GRAY)
    response = cv2.cornerMinEigenVal(gray, blockSize=3, ksize=3)
    corners = cv2.goodFeaturesToTrack(
        gray,
        maxCorners=config.maximum_corners,
        qualityLevel=config.corner_quality,
        minDistance=config.corner_minimum_distance,
        blockSize=3,
        useHarrisDetector=False,
    )
    if corners is None:
        return []
    raw_rows = []
    for coordinates in np.asarray(corners).reshape(-1, 2):
        x = min(max(float(coordinates[0]), 0.0), float(width - 1))
        y = min(max(float(coordinates[1]), 0.0), float(height - 1))
        raw_rows.append((float(response[int(round(y)), int(round(x))]), x, y))
    raw_rows.sort(key=lambda row: (-row[0], row[2], row[1]))
    return [
        ScreenshotCandidate(
            proposal_id="",
            source="corner",
            source_proposal_id=f"corner_{index:03d}",
            source_ordinal=index,
            score=score,
            point=(x, y),
            bbox_xyxy=_point_box((x, y), width, height, config),
        )
        for index, (score, x, y) in enumerate(raw_rows[: config.maximum_corners])
    ]


def component_candidates(
    image: Any,
    config: ScreenshotCandidateConfig,
) -> list[ScreenshotCandidate]:
    """Return generic foreground components in Lab image space."""

    import cv2
    import numpy as np

    pixels = np.asarray(image.convert("RGB"), dtype=np.uint8)
    height, width = pixels.shape[:2]
    lab = cv2.cvtColor(pixels, cv2.COLOR_RGB2LAB).astype(np.float32)
    border_width = max(1, min(4, height // 8, width // 8))
    border = np.concatenate(
        [
            lab[:border_width, :, :].reshape(-1, 3),
            lab[-border_width:, :, :].reshape(-1, 3),
            lab[:, :border_width, :].reshape(-1, 3),
            lab[:, -border_width:, :].reshape(-1, 3),
        ],
        axis=0,
    )
    background = np.median(border, axis=0)
    distance = np.linalg.norm(lab - background[None, None, :], axis=2)
    mask = (distance >= config.component_background_distance).astype(np.uint8)
    count, labels, stats, centroids = cv2.connectedComponentsWithStats(
        mask,
        connectivity=8,
    )
    maximum_area = config.component_maximum_area_fraction * width * height
    raw_rows = []
    for label in range(1, count):
        x, y, component_width, component_height, area = [
            int(value) for value in stats[label]
        ]
        if (
            area < config.component_minimum_area
            or area > maximum_area
            or component_width <= 0
            or component_height <= 0
        ):
            continue
        values = distance[labels == label]
        contrast = float(values.mean()) if values.size else 0.0
        center_x, center_y = (float(value) for value in centroids[label])
        raw_rows.append(
            (
                contrast * math.sqrt(float(area)),
                area,
                center_x,
                center_y,
                (x, y, x + component_width, y + component_height),
            )
        )
    raw_rows.sort(key=lambda row: (-row[0], -row[1], row[3], row[2]))
    return [
        ScreenshotCandidate(
            proposal_id="",
            source="component",
            source_proposal_id=f"component_{index:03d}",
            source_ordinal=index,
            score=score,
            point=(center_x, center_y),
            bbox_xyxy=bbox,
        )
        for index, (score, _area, center_x, center_y, bbox) in enumerate(
            raw_rows[: config.maximum_components]
        )
    ]


def radical_inverse(index: int, base: int) -> float:
    if index < 0 or base <= 1:
        raise ValueError("radical_inverse expects index >= 0 and base > 1")
    result = 0.0
    factor = 1.0 / base
    while index:
        index, digit = divmod(index, base)
        result += digit * factor
        factor /= base
    return result


def coverage_candidates(
    image: Any,
    config: ScreenshotCandidateConfig,
) -> list[ScreenshotCandidate]:
    """Return deterministic Halton coverage points."""

    rgb = image.convert("RGB")
    rows = []
    for ordinal in range(config.maximum_coverage):
        index = ordinal + 1
        point = (
            radical_inverse(index, 2) * (rgb.width - 1),
            radical_inverse(index, 3) * (rgb.height - 1),
        )
        rows.append(
            ScreenshotCandidate(
                proposal_id="",
                source="coverage",
                source_proposal_id=f"coverage_{ordinal:03d}",
                source_ordinal=ordinal,
                score=1.0,
                point=point,
                bbox_xyxy=_point_box(point, rgb.width, rgb.height, config),
            )
        )
    return rows


def alternating_structure(
    corners: Iterable[ScreenshotCandidate],
    components: Iterable[ScreenshotCandidate],
) -> list[ScreenshotCandidate]:
    queues = [deque(corners), deque(components)]
    rows = []
    while any(queues):
        for queue in queues:
            if queue:
                rows.append(queue.popleft())
    return rows


def interleave_candidates(
    *,
    ocr: Iterable[ScreenshotCandidate],
    structure: Iterable[ScreenshotCandidate],
    coverage: Iterable[ScreenshotCandidate],
    config: ScreenshotCandidateConfig,
) -> list[ScreenshotCandidate]:
    """Interleave fixed source queues and merge nearby points."""

    queues = {
        "ocr": deque(ocr),
        "structure": deque(structure),
        "coverage": deque(coverage),
    }
    retained: list[ScreenshotCandidate] = []
    while any(queues.values()) and len(retained) < config.global_cap:
        progressed = False
        for source in config.interleave_cycle:
            queue = queues[source]
            while queue:
                row = queue.popleft()
                if any(
                    math.hypot(
                        row.point[0] - prior.point[0],
                        row.point[1] - prior.point[1],
                    )
                    <= config.merge_distance
                    for prior in retained
                ):
                    continue
                retained.append(
                    ScreenshotCandidate(
                        proposal_id=f"candidate_{len(retained):03d}",
                        source=row.source,
                        source_proposal_id=row.source_proposal_id,
                        source_ordinal=row.source_ordinal,
                        score=row.score,
                        point=row.point,
                        bbox_xyxy=row.bbox_xyxy,
                        text=row.text,
                    )
                )
                progressed = True
                break
            if len(retained) >= config.global_cap:
                break
        if not progressed:
            break
    return retained


def propose_screenshot_candidates(
    image: Any,
    config: ScreenshotCandidateConfig | None = None,
    *,
    ocr_extractor: Callable[..., tuple[WordBox, ...]] = tesseract_word_boxes,
) -> list[ScreenshotCandidate]:
    """Return a complete task-blind proposal sequence from one screenshot."""

    cfg = config or ScreenshotCandidateConfig()
    ocr = ocr_candidates(image, cfg, extractor=ocr_extractor)
    corners = corner_candidates(image, cfg)
    components = component_candidates(image, cfg)
    structure = alternating_structure(corners, components)
    coverage = coverage_candidates(image, cfg)
    return interleave_candidates(
        ocr=ocr,
        structure=structure,
        coverage=coverage,
        config=cfg,
    )
