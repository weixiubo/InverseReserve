"""Family-blind screenshot observation adapter for live Q-RPS replay."""

from __future__ import annotations

import re
import subprocess
import tempfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

WHITESPACE = re.compile("\\s+")
WORD_PATTERN = re.compile("[a-z0-9]+(?:[.-][a-z0-9]+)*")


@dataclass(frozen=True)
class ChangedComponent:
    bbox_xyxy: tuple[int, int, int, int]
    changed_pixels: int


@dataclass(frozen=True)
class AdapterObservation:
    response: bool
    changed_pixels: int
    changed_fraction: float
    evidence: str
    components: tuple[ChangedComponent, ...]
    component_ocr: tuple[str, ...]
    whole_screen_novelty: tuple[str, ...]
    ocr_calls: int


def image_array(image: Any) -> Any:
    import numpy as np

    return np.asarray(image.convert("RGB"), dtype=np.uint8)


def changed_mask(reference: Any, observed: Any, pixel_threshold: int = 12) -> Any:
    import numpy as np

    left = image_array(reference).astype(np.int16)
    right = image_array(observed).astype(np.int16)
    if left.shape != right.shape:
        raise ValueError(f"image shapes differ: {left.shape} != {right.shape}")
    difference = np.max(np.abs(left - right), axis=2)
    return (difference >= pixel_threshold).astype(np.uint8)


def changed_fraction(reference: Any, observed: Any, pixel_threshold: int = 12) -> float:
    mask = changed_mask(reference, observed, pixel_threshold)
    return float(mask.sum()) / float(mask.shape[0] * mask.shape[1])


def extract_changed_components(
    mask: Any,
    *,
    grouping_kernel_size: int = 17,
    minimum_changed_pixels: int = 16,
    padding_pixels: int = 8,
    maximum_components: int = 12,
) -> tuple[ChangedComponent, ...]:
    import numpy as np

    if mask.ndim != 2:
        raise ValueError("changed mask must be two-dimensional")
    binary = (mask > 0).astype(np.uint8)
    height, width = binary.shape
    output = []
    try:
        raw_components = _opencv_components(binary, grouping_kernel_size)
    except ImportError:
        raw_components = _fallback_components(binary, grouping_kernel_size, height, width)
    for ys, xs in raw_components:
        changed = int(len(xs))
        if changed >= minimum_changed_pixels:
            left = max(0, int(xs.min()) - padding_pixels)
            top = max(0, int(ys.min()) - padding_pixels)
            right = min(width, int(xs.max()) + 1 + padding_pixels)
            bottom = min(height, int(ys.max()) + 1 + padding_pixels)
            output.append(ChangedComponent(bbox_xyxy=(left, top, right, bottom), changed_pixels=changed))
    output.sort(
        key=lambda component: (component.bbox_xyxy[1], component.bbox_xyxy[0], -component.changed_pixels)
    )
    return tuple(output[:maximum_components])


def preprocess_for_ocr(image: Any) -> Any:
    from PIL import Image, ImageOps

    grayscale = ImageOps.grayscale(image)
    resized = grayscale.resize((grayscale.width * 2, grayscale.height * 2), Image.Resampling.LANCZOS)
    return ImageOps.autocontrast(resized)


def _run_tesseract(image: Any, *, psm: int, tsv: bool, timeout_seconds: int) -> str:
    processed = preprocess_for_ocr(image)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as handle:
            temporary = Path(handle.name)
        processed.save(temporary)
        command = ["tesseract", str(temporary), "stdout", "-l", "eng", "--oem", "3", "--psm", str(psm)]
        if tsv:
            command.append("tsv")
        process = subprocess.run(
            command, text=True, capture_output=True, timeout=timeout_seconds, check=False
        )
        if process.returncode != 0:
            raise RuntimeError(f"tesseract failed ({process.returncode}): {process.stderr[-500:]}")
        return process.stdout
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def tesseract_text(image: Any, psm: int = 6, timeout_seconds: int = 30) -> str:
    return _run_tesseract(image, psm=psm, tsv=False, timeout_seconds=timeout_seconds)


def tesseract_words(image: Any, psm: int = 11, timeout_seconds: int = 30) -> list[str]:
    output = _run_tesseract(image, psm=psm, tsv=True, timeout_seconds=timeout_seconds)
    lines = output.splitlines()
    if not lines:
        return []
    header = lines[0].split("\t")
    try:
        text_index = header.index("text")
        confidence_index = header.index("conf")
    except ValueError as exc:
        raise ValueError("unexpected Tesseract TSV header") from exc
    words = []
    for line in lines[1:]:
        columns = line.split("\t")
        if len(columns) <= max(text_index, confidence_index):
            continue
        text = columns[text_index].strip()
        try:
            confidence = float(columns[confidence_index])
        except ValueError:
            confidence = -1.0
        if text and confidence >= 0:
            words.append(text)
    return words


def normalize_text(text: str) -> str:
    return WHITESPACE.sub(" ", text).strip()


def normalized_word_tokens(words: list[str]) -> list[str]:
    output = []
    for word in words:
        output.extend(WORD_PATTERN.findall(word.lower()))
    return output


def multiset_novel_words(reference_words: list[str], preview_words: list[str]) -> list[str]:
    remaining = Counter(normalized_word_tokens(reference_words))
    novelty = []
    for token in normalized_word_tokens(preview_words):
        if remaining[token] > 0:
            remaining[token] -= 1
        else:
            novelty.append(token)
    return novelty


def extract_adapter_observation(
    reference: Any,
    preview: Any,
    *,
    reference_words: list[str] | None = None,
    text_ocr: Callable[[Any, int, int], str] | None = None,
    words_ocr: Callable[[Any, int, int], list[str]] | None = None,
) -> AdapterObservation:
    if text_ocr is None:

        def text_ocr(image, psm, timeout):
            return tesseract_text(image, psm=psm, timeout_seconds=timeout)

    if words_ocr is None:

        def words_ocr(image, psm, timeout):
            return tesseract_words(image, psm=psm, timeout_seconds=timeout)

    mask = changed_mask(reference, preview, pixel_threshold=12)
    changed = int(mask.sum())
    pixels = int(mask.shape[0] * mask.shape[1])
    response = changed >= 16
    if not response:
        return AdapterObservation(
            response=False,
            changed_pixels=changed,
            changed_fraction=changed / pixels,
            evidence="",
            components=tuple(),
            component_ocr=tuple(),
            whole_screen_novelty=tuple(),
            ocr_calls=0,
        )
    components = extract_changed_components(mask)
    component_texts, ocr_calls, seen_component_text = _read_changed_crops(components, preview, text_ocr)
    deduplicated = []
    for text in component_texts:
        key = text.lower()
        if key not in seen_component_text:
            seen_component_text.add(key)
            deduplicated.append(text)
    if reference_words is None:
        reference_words = words_ocr(reference, 11, 30)
        ocr_calls += 1
    preview_words = words_ocr(preview, 11, 30)
    ocr_calls += 1
    novelty = multiset_novel_words(reference_words, preview_words)
    novelty_text = " ".join(novelty)
    parts = list(deduplicated)
    if novelty_text and (not any((novelty_text in normalize_text(part).lower() for part in parts))):
        parts.append(novelty_text)
    evidence = " | ".join(parts)
    return AdapterObservation(
        response=True,
        changed_pixels=changed,
        changed_fraction=changed / pixels,
        evidence=evidence,
        components=components,
        component_ocr=tuple(deduplicated),
        whole_screen_novelty=tuple(novelty),
        ocr_calls=ocr_calls,
    )


def _opencv_components(binary: Any, grouping_kernel_size: int) -> list[tuple[Any, Any]]:
    import cv2
    import numpy as np

    kernel = np.ones((grouping_kernel_size, grouping_kernel_size), dtype=np.uint8)
    grouped = cv2.dilate(binary, kernel, iterations=1)
    count, labels, _, _ = cv2.connectedComponentsWithStats(grouped, connectivity=8)
    raw_components = []
    for label in range(1, count):
        ys, xs = np.where((labels == label) & (binary > 0))
        if len(xs):
            raw_components.append((ys, xs))
    return raw_components


def _fallback_components(
    binary: Any, grouping_kernel_size: int, height: int, width: int
) -> list[tuple[Any, Any]]:
    import numpy as np

    radius = grouping_kernel_size // 2
    padded_x = np.pad(binary, ((0, 0), (radius, radius)))
    cumulative_x = np.pad(np.cumsum(padded_x, axis=1, dtype=np.int32), ((0, 0), (1, 0)))
    horizontal = (
        cumulative_x[:, grouping_kernel_size:] - cumulative_x[:, :-grouping_kernel_size] > 0
    ).astype(np.uint8)
    padded_y = np.pad(horizontal, ((radius, radius), (0, 0)))
    cumulative_y = np.pad(np.cumsum(padded_y, axis=0, dtype=np.int32), ((1, 0), (0, 0)))
    grouped = cumulative_y[grouping_kernel_size:, :] - cumulative_y[:-grouping_kernel_size, :] > 0
    visited = np.zeros_like(grouped, dtype=bool)
    raw_components = []
    for start_y, start_x in np.argwhere(grouped):
        if visited[start_y, start_x]:
            continue
        raw_y, raw_x = _flood_component(binary, grouped, visited, start_y, start_x, height, width)
        if raw_x:
            raw_components.append((np.asarray(raw_y, dtype=np.int32), np.asarray(raw_x, dtype=np.int32)))
    return raw_components


def _flood_component(
    binary: Any, grouped: Any, visited: Any, start_y: int, start_x: int, height: int, width: int
) -> tuple[list[int], list[int]]:
    from collections import deque

    queue = deque([(int(start_y), int(start_x))])
    visited[start_y, start_x] = True
    raw_y = []
    raw_x = []
    while queue:
        y, x = queue.popleft()
        if binary[y, x]:
            raw_y.append(y)
            raw_x.append(x)
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                neighbor_y = y + dy
                neighbor_x = x + dx
                if (
                    0 <= neighbor_y < height
                    and 0 <= neighbor_x < width
                    and grouped[neighbor_y, neighbor_x]
                    and (not visited[neighbor_y, neighbor_x])
                ):
                    visited[neighbor_y, neighbor_x] = True
                    queue.append((neighbor_y, neighbor_x))
    return (raw_y, raw_x)


def _read_changed_crops(components, preview, text_ocr):
    """Read component and union crops before deduplicating text."""
    component_texts = []
    ocr_calls = 0
    crop_boxes = [component.bbox_xyxy for component in components]
    if len(crop_boxes) >= 2:
        crop_boxes.append(
            (
                min((box[0] for box in crop_boxes)),
                min((box[1] for box in crop_boxes)),
                max((box[2] for box in crop_boxes)),
                max((box[3] for box in crop_boxes)),
            )
        )
    for box in crop_boxes:
        text = normalize_text(text_ocr(preview.crop(box), 6, 30))
        ocr_calls += 1
        if text:
            component_texts.append(text)
    seen_component_text = set()
    return (component_texts, ocr_calls, seen_component_text)
