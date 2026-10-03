"""Theme-agnostic appearance surfaces for provenance-bounded evidence."""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from typing import Any, Callable

from .grounded_evidence import (
    EvidenceChannel,
    GroundedEvidenceObservation,
    ResponsePanel,
    tesseract_panel_text,
)
from .evidence import tokenize
from .live_observation import (
    changed_mask,
    multiset_novel_words,
    normalize_text,
    normalized_word_tokens,
    tesseract_words,
)


@dataclass(frozen=True)
class AppearanceSurfaceConfig:
    """Task-blind color-stratum and temporal-consistency parameters."""

    color_bin_width: int = 64
    pixel_change_threshold: int = 12
    minimum_response_changed_pixels: int = 16
    minimum_stratum_changed_pixels: int = 200
    component_area_minimum: int = 500
    component_width_minimum: int = 60
    component_height_minimum: int = 24
    component_area_maximum_fraction: float = 0.25
    minimum_fill_fraction: float = 0.50
    minimum_changed_overlap_fraction: float = 0.80
    frame_component_area_minimum: int = 200
    frame_maximum_fill_fraction: float = 0.25
    frame_minimum_boundary_coverage: float = 0.29
    frame_boundary_band_pixels: int = 3
    candidate_deduplication_iou: float = 0.80
    connectivity: int = 8
    maximum_candidates: int = 8
    padding_pixels: int = 5
    ocr_scale: int = 3


@dataclass(frozen=True)
class AppearanceSurface:
    bbox_xyxy: tuple[int, int, int, int]
    stratum_pixels: int
    changed_overlap_pixels: int
    fill_fraction: float
    changed_overlap_fraction: float
    color_code: int
    visual_score: float
    kind: str = "surface"
    boundary_coverage: float = 0.0


@dataclass(frozen=True)
class SurfaceReading:
    surface: AppearanceSurface
    text: str
    distinct_tokens: int
    tokens: int
    alphanumeric_characters: int


OCR_VIEWS = ((6, 3), (6, 2), (11, 2), (12, 2))
ALPHANUMERIC_RUN = re.compile(r"[a-z]+|[0-9]+(?:\.[0-9]+)?")


def _validate_config(config: AppearanceSurfaceConfig) -> None:
    if (
        config.color_bin_width <= 0
        or config.color_bin_width > 256
        or 256 % config.color_bin_width != 0
    ):
        raise ValueError("color_bin_width must be a positive divisor of 256")
    if config.pixel_change_threshold < 0:
        raise ValueError("pixel_change_threshold must be nonnegative")
    for name in (
        "minimum_response_changed_pixels",
        "minimum_stratum_changed_pixels",
        "component_area_minimum",
        "component_width_minimum",
        "component_height_minimum",
        "frame_component_area_minimum",
        "frame_boundary_band_pixels",
        "maximum_candidates",
        "ocr_scale",
    ):
        if getattr(config, name) <= 0:
            raise ValueError(f"{name} must be positive")
    for name in (
        "component_area_maximum_fraction",
        "minimum_fill_fraction",
        "minimum_changed_overlap_fraction",
        "frame_maximum_fill_fraction",
        "frame_minimum_boundary_coverage",
        "candidate_deduplication_iou",
    ):
        value = getattr(config, name)
        if not 0 < value <= 1:
            raise ValueError(f"{name} must be in (0, 1]")
    if config.connectivity not in {4, 8}:
        raise ValueError("connectivity must be 4 or 8")
    if config.padding_pixels < 0:
        raise ValueError("padding_pixels must be nonnegative")


def extract_appearance_surfaces(
    reference: Any,
    preview: Any,
    config: AppearanceSurfaceConfig | None = None,
) -> tuple[AppearanceSurface, ...]:
    """Generate near-solid changed surfaces from fixed RGB color strata."""

    import cv2
    import numpy as np

    cfg = config or AppearanceSurfaceConfig()
    _validate_config(cfg)
    reference_pixels = np.asarray(reference.convert("RGB"), dtype=np.uint8)
    preview_pixels = np.asarray(preview.convert("RGB"), dtype=np.uint8)
    if reference_pixels.shape != preview_pixels.shape:
        raise ValueError(
            f"image shapes differ: {reference_pixels.shape} != {preview_pixels.shape}"
        )
    height, width = preview_pixels.shape[:2]
    changed = changed_mask(
        reference, preview, pixel_threshold=cfg.pixel_change_threshold
    ).astype(bool)
    levels = 256 // cfg.color_bin_width
    quantized = (preview_pixels // cfg.color_bin_width).astype(np.int32)
    color_codes = (
        (quantized[:, :, 0] * levels + quantized[:, :, 1]) * levels
        + quantized[:, :, 2]
    )
    changed_codes, changed_counts = np.unique(
        color_codes[changed], return_counts=True
    )
    maximum_area = cfg.component_area_maximum_fraction * height * width
    output = []
    for code, changed_count in zip(changed_codes, changed_counts, strict=True):
        if int(changed_count) < cfg.minimum_stratum_changed_pixels:
            continue
        temporal_stratum = (color_codes == int(code)) & changed
        count, labels, stats, _ = cv2.connectedComponentsWithStats(
            temporal_stratum.astype(np.uint8),
            connectivity=cfg.connectivity,
        )
        for label in range(1, count):
            x, y, component_width, component_height, area = [
                int(value) for value in stats[label]
            ]
            if area > maximum_area:
                continue
            if (
                component_width < cfg.component_width_minimum
                or component_height < cfg.component_height_minimum
            ):
                continue
            fill_fraction = area / float(component_width * component_height)
            component = labels[
                y : y + component_height, x : x + component_width
            ] == label
            band_width = min(
                cfg.frame_boundary_band_pixels,
                component_height // 2,
                component_width // 2,
            )
            boundary = np.zeros_like(component, dtype=bool)
            if band_width > 0:
                boundary[:band_width, :] = True
                boundary[-band_width:, :] = True
                boundary[:, :band_width] = True
                boundary[:, -band_width:] = True
            boundary_coverage = (
                float(component[boundary].mean()) if boundary.any() else 0.0
            )
            is_surface = (
                area >= cfg.component_area_minimum
                and fill_fraction + 1e-12 >= cfg.minimum_fill_fraction
            )
            is_frame = (
                area >= cfg.frame_component_area_minimum
                and fill_fraction <= cfg.frame_maximum_fill_fraction + 1e-12
                and boundary_coverage + 1e-12
                >= cfg.frame_minimum_boundary_coverage
            )
            if not is_surface and not is_frame:
                continue
            changed_overlap = int((changed & (labels == label)).sum())
            overlap_fraction = changed_overlap / float(area)
            if overlap_fraction + 1e-12 < cfg.minimum_changed_overlap_fraction:
                continue
            output.append(
                AppearanceSurface(
                    bbox_xyxy=(
                        x,
                        y,
                        x + component_width,
                        y + component_height,
                    ),
                    stratum_pixels=area,
                    changed_overlap_pixels=changed_overlap,
                    fill_fraction=fill_fraction,
                    changed_overlap_fraction=overlap_fraction,
                    color_code=int(code),
                    visual_score=changed_overlap
                    * (fill_fraction if is_surface else boundary_coverage),
                    kind="surface" if is_surface else "frame",
                    boundary_coverage=boundary_coverage,
                )
            )
    output.sort(
        key=lambda surface: (
            -surface.visual_score,
            -surface.changed_overlap_pixels,
            -surface.stratum_pixels,
            surface.bbox_xyxy[1],
            surface.bbox_xyxy[0],
            surface.color_code,
        )
    )
    retained = []
    for surface in output:
        if any(
            _bbox_iou(surface.bbox_xyxy, prior.bbox_xyxy)
            + 1e-12
            >= cfg.candidate_deduplication_iou
            for prior in retained
        ):
            continue
        retained.append(surface)
        if len(retained) >= cfg.maximum_candidates:
            break
    return tuple(retained)


def _bbox_iou(
    left: tuple[int, int, int, int], right: tuple[int, int, int, int]
) -> float:
    intersection_left = max(left[0], right[0])
    intersection_top = max(left[1], right[1])
    intersection_right = min(left[2], right[2])
    intersection_bottom = min(left[3], right[3])
    intersection = max(0, intersection_right - intersection_left) * max(
        0, intersection_bottom - intersection_top
    )
    left_area = (left[2] - left[0]) * (left[3] - left[1])
    right_area = (right[2] - right[0]) * (right[3] - right[1])
    return intersection / float(left_area + right_area - intersection)


def surface_text_information(text: str) -> tuple[int, int, int]:
    tokens = normalized_word_tokens([text])
    return len(set(tokens)), len(tokens), sum(character.isalnum() for character in text)


def expanded_ocr_tokens(text: str) -> set[str]:
    output = set(tokenize(text))
    for token in tuple(output):
        output.update(ALPHANUMERIC_RUN.findall(token))
    return output


def consensus_surface_evidence(texts: list[str] | tuple[str, ...]) -> str:
    """Return deterministic tokens supported by at least half of same-box OCR views."""

    nonempty = [normalize_text(text) for text in texts if normalize_text(text)]
    if not nonempty:
        return ""
    tokens_by_view = [expanded_ocr_tokens(text) for text in nonempty]
    support: Counter[str] = Counter()
    for tokens in tokens_by_view:
        support.update(tokens)
    minimum_support = max(1, (len(nonempty) + 1) // 2)
    stable = {
        token for token, count in support.items() if count >= minimum_support
    }
    observed_compounds = {
        token
        for tokens in tokens_by_view
        for token in tokens
        if "-" in token
        and all(part and part in stable for part in token.split("-"))
    }
    stable.update(observed_compounds)
    stable = sorted(stable)
    return " ".join(stable) if stable else max(nonempty, key=lambda text: (len(text), text))


def rank_surface_readings(
    readings: list[SurfaceReading] | tuple[SurfaceReading, ...],
) -> tuple[SurfaceReading, ...]:
    return tuple(
        sorted(
            readings,
            key=lambda reading: (
                -reading.distinct_tokens,
                -reading.tokens,
                -reading.alphanumeric_characters,
                -reading.surface.visual_score,
                -reading.surface.changed_overlap_pixels,
                reading.surface.bbox_xyxy[1],
                reading.surface.bbox_xyxy[0],
                reading.surface.color_code,
            ),
        )
    )


def _padded_crop(image: Any, surface: AppearanceSurface, padding: int) -> Any:
    left, top, right, bottom = surface.bbox_xyxy
    return image.crop(
        (
            max(0, left - padding),
            max(0, top - padding),
            min(image.width, right + padding),
            min(image.height, bottom + padding),
        )
    )


def extract_appearance_evidence(
    reference: Any,
    preview: Any,
    *,
    reference_words: list[str] | None = None,
    config: AppearanceSurfaceConfig | None = None,
    surface_text_ocr: Callable[[Any, int, int, int], str] | None = None,
    words_ocr: Callable[[Any, int, int], list[str]] | None = None,
) -> GroundedEvidenceObservation:
    """Select one information-bearing surface without merging candidate channels."""

    cfg = config or AppearanceSurfaceConfig()
    _validate_config(cfg)
    mask = changed_mask(
        reference, preview, pixel_threshold=cfg.pixel_change_threshold
    )
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
    if surface_text_ocr is None:
        surface_text_ocr = lambda image, psm, scale, timeout: tesseract_panel_text(
            image,
            psm=psm,
            timeout_seconds=timeout,
            scale=scale,
        )
    if words_ocr is None:
        words_ocr = lambda image, psm, timeout: tesseract_words(
            image, psm=psm, timeout_seconds=timeout
        )

    surfaces = extract_appearance_surfaces(reference, preview, cfg)
    readings = []
    crops = {}
    ocr_calls = 0
    for surface in surfaces:
        crop = _padded_crop(preview, surface, cfg.padding_pixels)
        crops[surface] = crop
        text = normalize_text(surface_text_ocr(crop, 6, cfg.ocr_scale, 30))
        ocr_calls += 1
        distinct, tokens, characters = surface_text_information(text)
        readings.append(
            SurfaceReading(surface, text, distinct, tokens, characters)
        )
    ranked = rank_surface_readings(readings)
    informative = [reading for reading in ranked if reading.text]
    novelty: list[str] = []
    primary_reading = informative[0] if informative else None
    primary_evidence = ""
    if primary_reading is not None:
        view_texts = [primary_reading.text]
        for psm, scale in OCR_VIEWS[1:]:
            view_texts.append(
                normalize_text(
                    surface_text_ocr(
                        crops[primary_reading.surface], psm, scale, 30
                    )
                )
            )
            ocr_calls += 1
        primary_evidence = consensus_surface_evidence(view_texts)
    channels = tuple(
        [
            EvidenceChannel(
                source="appearance_response_surface",
                text=primary_evidence,
                bbox_xyxy=primary_reading.surface.bbox_xyxy,
            )
        ]
        + [
            EvidenceChannel(
                source="appearance_response_surface",
                text=reading.text,
                bbox_xyxy=reading.surface.bbox_xyxy,
            )
            for reading in informative[1:]
        ]
        if primary_reading is not None and primary_evidence
        else []
    )
    if primary_reading is None:
        if reference_words is None:
            reference_words = words_ocr(reference, 11, 30)
            ocr_calls += 1
        preview_words = words_ocr(preview, 11, 30)
        ocr_calls += 1
        novelty = multiset_novel_words(reference_words, preview_words)
        novelty_text = " ".join(novelty)
        if novelty_text:
            channels = (
                EvidenceChannel(
                    source="whole_screen_counterfactual_novelty",
                    text=novelty_text,
                    bbox_xyxy=None,
                ),
            )

    if primary_reading is not None:
        selected_panel = ResponsePanel(
            bbox_xyxy=primary_reading.surface.bbox_xyxy,
            stratum_pixels=primary_reading.surface.stratum_pixels,
            changed_overlap_pixels=primary_reading.surface.changed_overlap_pixels,
            fill_fraction=primary_reading.surface.fill_fraction,
            changed_overlap_fraction=primary_reading.surface.changed_overlap_fraction,
        )
        evidence = primary_evidence
        primary_source = "appearance_response_surface"
        panels = (selected_panel,)
        panel_ocr = (primary_evidence,)
    else:
        evidence = channels[0].text if channels else ""
        primary_source = channels[0].source if channels else None
        panels = tuple()
        panel_ocr = tuple()
    return GroundedEvidenceObservation(
        response=True,
        changed_pixels=changed_pixels,
        changed_fraction=changed_pixels / total_pixels,
        evidence=evidence,
        primary_source=primary_source,
        panels=panels,
        panel_ocr=panel_ocr,
        channels=channels,
        whole_screen_novelty=tuple(novelty),
        ocr_calls=ocr_calls,
    )
