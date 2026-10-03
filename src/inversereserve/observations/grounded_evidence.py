"""Provenance-bounded visual evidence for reversible preview interactions."""

from __future__ import annotations

import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from inversereserve.observations.live_observation import (
    changed_mask,
    multiset_novel_words,
    normalize_text,
    tesseract_words,
)


@dataclass(frozen=True)
class ResponsePanelConfig:
    """Frozen pixel and geometry rule for a low-RGB response-panel stratum."""

    red_maximum_exclusive: int = 80
    green_maximum_exclusive: int = 90
    blue_maximum_exclusive: int = 120
    pixel_change_threshold: int = 12
    minimum_response_changed_pixels: int = 16
    component_area_minimum: int = 500
    component_width_minimum: int = 60
    component_height_minimum: int = 24
    component_area_maximum_fraction: float = 0.25
    minimum_fill_fraction: float = 0.5
    minimum_changed_overlap_fraction: float = 0.8
    connectivity: int = 8
    padding_pixels: int = 5
    ocr_scale: int = 3


@dataclass(frozen=True)
class ResponsePanel:
    bbox_xyxy: tuple[int, int, int, int]
    stratum_pixels: int
    changed_overlap_pixels: int
    fill_fraction: float
    changed_overlap_fraction: float


@dataclass(frozen=True)
class EvidenceChannel:
    source: str
    text: str
    bbox_xyxy: tuple[int, int, int, int] | None


@dataclass(frozen=True)
class GroundedEvidenceObservation:
    response: bool
    changed_pixels: int
    changed_fraction: float
    evidence: str
    primary_source: str | None
    panels: tuple[ResponsePanel, ...]
    panel_ocr: tuple[str, ...]
    channels: tuple[EvidenceChannel, ...]
    whole_screen_novelty: tuple[str, ...]
    ocr_calls: int


def _validate_config(config: ResponsePanelConfig) -> None:
    for name in ("red_maximum_exclusive", "green_maximum_exclusive", "blue_maximum_exclusive"):
        value = getattr(config, name)
        if not 0 <= value <= 256:
            raise ValueError(f"{name} must be in [0, 256]")
    if config.pixel_change_threshold < 0:
        raise ValueError("pixel_change_threshold must be nonnegative")
    if config.minimum_response_changed_pixels <= 0:
        raise ValueError("minimum_response_changed_pixels must be positive")
    for name in (
        "component_area_minimum",
        "component_width_minimum",
        "component_height_minimum",
        "ocr_scale",
    ):
        if getattr(config, name) <= 0:
            raise ValueError(f"{name} must be positive")
    for name in (
        "component_area_maximum_fraction",
        "minimum_fill_fraction",
        "minimum_changed_overlap_fraction",
    ):
        value = getattr(config, name)
        if not 0 < value <= 1:
            raise ValueError(f"{name} must be in (0, 1]")
    if config.connectivity not in {4, 8}:
        raise ValueError("connectivity must be 4 or 8")
    if config.padding_pixels < 0:
        raise ValueError("padding_pixels must be nonnegative")


def extract_response_panels(
    reference: Any, preview: Any, config: ResponsePanelConfig | None = None
) -> tuple[ResponsePanel, ...]:
    """Extract deterministic, changed, near-solid low-RGB panels from RGB pixels."""
    import cv2
    import numpy as np

    cfg = config or ResponsePanelConfig()
    _validate_config(cfg)
    reference_pixels = np.asarray(reference.convert("RGB"), dtype=np.uint8)
    preview_pixels = np.asarray(preview.convert("RGB"), dtype=np.uint8)
    if reference_pixels.shape != preview_pixels.shape:
        raise ValueError(f"image shapes differ: {reference_pixels.shape} != {preview_pixels.shape}")
    height, width = preview_pixels.shape[:2]
    changed = changed_mask(reference, preview, pixel_threshold=cfg.pixel_change_threshold).astype(bool)
    stratum = (
        (preview_pixels[:, :, 0] < cfg.red_maximum_exclusive)
        & (preview_pixels[:, :, 1] < cfg.green_maximum_exclusive)
        & (preview_pixels[:, :, 2] < cfg.blue_maximum_exclusive)
    ).astype(np.uint8)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(stratum, connectivity=cfg.connectivity)
    maximum_area = cfg.component_area_maximum_fraction * height * width
    output = []
    for label in range(1, count):
        x, y, component_width, component_height, area = [int(value) for value in stats[label]]
        if not cfg.component_area_minimum <= area <= maximum_area:
            continue
        if component_width < cfg.component_width_minimum or component_height < cfg.component_height_minimum:
            continue
        fill_fraction = area / float(component_width * component_height)
        if fill_fraction + 1e-12 < cfg.minimum_fill_fraction:
            continue
        changed_overlap = int((changed & (labels == label)).sum())
        overlap_fraction = changed_overlap / float(area)
        if overlap_fraction + 1e-12 < cfg.minimum_changed_overlap_fraction:
            continue
        output.append(
            ResponsePanel(
                bbox_xyxy=(x, y, x + component_width, y + component_height),
                stratum_pixels=area,
                changed_overlap_pixels=changed_overlap,
                fill_fraction=fill_fraction,
                changed_overlap_fraction=overlap_fraction,
            )
        )
    output.sort(
        key=lambda panel: (
            -panel.changed_overlap_pixels,
            -panel.stratum_pixels,
            panel.bbox_xyxy[1],
            panel.bbox_xyxy[0],
        )
    )
    return tuple(output)


def preprocess_panel_for_ocr(image: Any, scale: int = 3) -> Any:
    from PIL import Image, ImageOps

    if scale <= 0:
        raise ValueError("OCR scale must be positive")
    grayscale = ImageOps.autocontrast(ImageOps.grayscale(image))
    return grayscale.resize((grayscale.width * scale, grayscale.height * scale), Image.Resampling.LANCZOS)


def tesseract_panel_text(image: Any, psm: int = 6, timeout_seconds: int = 30, scale: int = 3) -> str:
    processed = preprocess_panel_for_ocr(image, scale=scale)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as handle:
            temporary = Path(handle.name)
        processed.save(temporary)
        process = subprocess.run(
            ["tesseract", str(temporary), "stdout", "-l", "eng", "--oem", "3", "--psm", str(psm)],
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
            check=False,
        )
        if process.returncode != 0:
            raise RuntimeError(f"tesseract failed ({process.returncode}): {process.stderr[-500:]}")
        return process.stdout
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _padded_crop(image: Any, panel: ResponsePanel, padding: int) -> Any:
    left, top, right, bottom = panel.bbox_xyxy
    return image.crop(
        (
            max(0, left - padding),
            max(0, top - padding),
            min(image.width, right + padding),
            min(image.height, bottom + padding),
        )
    )


def extract_grounded_evidence(
    reference: Any,
    preview: Any,
    *,
    reference_words: list[str] | None = None,
    config: ResponsePanelConfig | None = None,
    panel_text_ocr: Callable[[Any, int, int], str] | None = None,
    words_ocr: Callable[[Any, int, int], list[str]] | None = None,
) -> GroundedEvidenceObservation:
    """Return one primary channel without concatenating distinct visual sources."""
    cfg = config or ResponsePanelConfig()
    _validate_config(cfg)
    mask = changed_mask(reference, preview, pixel_threshold=cfg.pixel_change_threshold)
    changed_pixels = int(mask.sum())
    total_pixels = int(mask.shape[0] * mask.shape[1])
    response = changed_pixels >= cfg.minimum_response_changed_pixels
    if not response:
        return GroundedEvidenceObservation(
            response=False,
            changed_pixels=changed_pixels,
            changed_fraction=changed_pixels / total_pixels,
            evidence="",
            primary_source=None,
            panels=tuple(),
            panel_ocr=tuple(),
            channels=tuple(),
            whole_screen_novelty=tuple(),
            ocr_calls=0,
        )
    if panel_text_ocr is None:

        def panel_text_ocr(image, psm, timeout):
            return tesseract_panel_text(image, psm=psm, timeout_seconds=timeout, scale=cfg.ocr_scale)

    if words_ocr is None:

        def words_ocr(image, psm, timeout):
            return tesseract_words(image, psm=psm, timeout_seconds=timeout)

    panels = extract_response_panels(reference, preview, cfg)
    panel_texts = []
    channels = []
    ocr_calls = 0
    for panel in panels:
        crop = _padded_crop(preview, panel, cfg.padding_pixels)
        text = normalize_text(panel_text_ocr(crop, 6, 30))
        ocr_calls += 1
        panel_texts.append(text)
        if text:
            channels.append(
                EvidenceChannel(source="low_rgb_response_panel", text=text, bbox_xyxy=panel.bbox_xyxy)
            )
    novelty: list[str] = []
    if not channels:
        if reference_words is None:
            reference_words = words_ocr(reference, 11, 30)
            ocr_calls += 1
        preview_words = words_ocr(preview, 11, 30)
        ocr_calls += 1
        novelty = multiset_novel_words(reference_words, preview_words)
        novelty_text = " ".join(novelty)
        if novelty_text:
            channels.append(
                EvidenceChannel(
                    source="whole_screen_counterfactual_novelty", text=novelty_text, bbox_xyxy=None
                )
            )
    primary = channels[0] if channels else None
    return GroundedEvidenceObservation(
        response=True,
        changed_pixels=changed_pixels,
        changed_fraction=changed_pixels / total_pixels,
        evidence=primary.text if primary is not None else "",
        primary_source=primary.source if primary is not None else None,
        panels=panels,
        panel_ocr=tuple(panel_texts),
        channels=tuple(channels),
        whole_screen_novelty=tuple(novelty),
        ocr_calls=ocr_calls,
    )
