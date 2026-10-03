"""Actual-browser preview transactions for the frozen C368 adapter."""

from __future__ import annotations

import hashlib
import io
import time
from pathlib import Path
from typing import Any, Callable

from .interface import PreviewObservation
from .live_observation import changed_fraction, extract_adapter_observation


class UnsafePreviewError(RuntimeError):
    """Raised after recording a transaction that cannot safely continue."""

    def __init__(self, message: str, audit: dict[str, Any]):
        super().__init__(message)
        self.audit = audit


def screenshot_image(page: Any) -> Any:
    from PIL import Image

    return Image.open(io.BytesIO(page.screenshot(type="png", full_page=False))).convert(
        "RGB"
    )


def rgb_sha256(image: Any) -> str:
    import numpy as np

    array = np.ascontiguousarray(np.asarray(image.convert("RGB"), dtype=np.uint8))
    return hashlib.sha256(array.tobytes()).hexdigest()


def alignment_report(frozen: Any, observed: Any) -> dict[str, Any]:
    same_dimensions = frozen.size == observed.size
    fraction = changed_fraction(frozen, observed) if same_dimensions else 1.0
    frozen_hash = rgb_sha256(frozen)
    observed_hash = rgb_sha256(observed)
    return {
        "same_dimensions": same_dimensions,
        "frozen_size": list(frozen.size),
        "observed_size": list(observed.size),
        "frozen_rgb_sha256": frozen_hash,
        "observed_rgb_sha256": observed_hash,
        "p12_changed_fraction": fraction,
        "exact": same_dimensions and frozen_hash == observed_hash,
    }


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def save_png(image: Any, path: Path) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    image.save(temporary, format="PNG")
    temporary.replace(path)
    return {
        "path": path.as_posix(),
        "sha256": file_sha256(path),
        "rgb_sha256": rgb_sha256(image),
        "width": image.width,
        "height": image.height,
    }


class LivePreviewRecorder:
    """Execute and audit restoration-certified, family-blind preview queries."""

    def __init__(
        self,
        *,
        page: Any,
        initial_image: Any,
        reference_words: list[str],
        artifact_directory: Path,
        artifact_root: Path,
        state_id: str,
        method: str,
        neutral_coordinate: tuple[float, float] = (6.0, 6.0),
        wait_milliseconds: int = 200,
        drift_threshold: float = 0.001,
        restoration_threshold: float = 0.001,
        progress_every: int = 64,
        progress: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        self.page = page
        self.initial_image = initial_image
        self.reference_words = list(reference_words)
        self.artifact_directory = artifact_directory
        self.artifact_root = artifact_root
        self.state_id = state_id
        self.method = method
        self.neutral_coordinate = neutral_coordinate
        self.wait_milliseconds = int(wait_milliseconds)
        self.drift_threshold = float(drift_threshold)
        self.restoration_threshold = float(restoration_threshold)
        self.progress_every = int(progress_every)
        self.progress = progress
        self.audit: list[dict[str, Any]] = []

    def _artifact(self, preview: Any, query_index: int, suffix: str) -> dict[str, Any]:
        path = self.artifact_directory / f"query_{query_index:04d}_{suffix}.png"
        row = save_png(preview, path)
        row["path"] = path.relative_to(self.artifact_root).as_posix()
        return row

    def observe(self, point: tuple[float, float]) -> PreviewObservation:
        query_index = len(self.audit) + 1
        started = time.monotonic()
        neutral_x, neutral_y = self.neutral_coordinate
        self.page.mouse.move(neutral_x, neutral_y)
        self.page.wait_for_timeout(self.wait_milliseconds)
        reference = screenshot_image(self.page)
        drift = changed_fraction(self.initial_image, reference)
        base = {
            "query_index": query_index,
            "point": [float(point[0]), float(point[1])],
            "reference_rgb_sha256": rgb_sha256(reference),
            "reference_p12_drift_from_initial": drift,
            "preview_wait_milliseconds": self.wait_milliseconds,
            "restoration_wait_milliseconds": self.wait_milliseconds,
        }
        if drift > self.drift_threshold:
            row = {
                **base,
                "complete": False,
                "failure": "reference_drift",
                "transaction_seconds": time.monotonic() - started,
            }
            self.audit.append(row)
            raise UnsafePreviewError(
                f"reference drift {drift:.8f} exceeds {self.drift_threshold}", row
            )

        self.page.mouse.move(float(point[0]), float(point[1]))
        self.page.wait_for_timeout(self.wait_milliseconds)
        preview = screenshot_image(self.page)
        observation = None
        adapter_error = None
        try:
            observation = extract_adapter_observation(
                reference, preview, reference_words=self.reference_words
            )
        except Exception as exc:  # restoration still runs after OCR failure
            adapter_error = f"{type(exc).__name__}: {exc}"

        self.page.mouse.move(neutral_x, neutral_y)
        self.page.wait_for_timeout(self.wait_milliseconds)
        restored = screenshot_image(self.page)
        residual = changed_fraction(reference, restored)
        save_preview = (
            observation is not None and observation.response
        ) or query_index % 32 == 0 or adapter_error is not None or residual > self.restoration_threshold
        artifact = (
            self._artifact(
                preview,
                query_index,
                "positive" if observation is not None and observation.response else "audit",
            )
            if save_preview
            else None
        )
        row = {
            **base,
            "complete": adapter_error is None and residual <= self.restoration_threshold,
            "failure": (
                "adapter_error"
                if adapter_error is not None
                else "restoration_failure"
                if residual > self.restoration_threshold
                else None
            ),
            "adapter_error": adapter_error,
            "preview_rgb_sha256": rgb_sha256(preview),
            "restored_rgb_sha256": rgb_sha256(restored),
            "restored_p12_changed_fraction": residual,
            "response": bool(observation.response) if observation is not None else None,
            "changed_pixels": observation.changed_pixels if observation is not None else None,
            "changed_fraction": observation.changed_fraction if observation is not None else None,
            "evidence": observation.evidence if observation is not None else "",
            "evidence_sha256": (
                hashlib.sha256(observation.evidence.encode("utf-8")).hexdigest()
                if observation is not None and observation.evidence
                else ""
            ),
            "components": (
                [
                    {
                        "bbox_xyxy": list(component.bbox_xyxy),
                        "changed_pixels": component.changed_pixels,
                    }
                    for component in observation.components
                ]
                if observation is not None
                else []
            ),
            "component_ocr": list(observation.component_ocr)
            if observation is not None
            else [],
            "whole_screen_novelty": list(observation.whole_screen_novelty)
            if observation is not None
            else [],
            "ocr_calls": observation.ocr_calls if observation is not None else 0,
            "preview_artifact": artifact,
            "transaction_seconds": time.monotonic() - started,
        }
        self.audit.append(row)
        if self.progress is not None and (
            query_index % self.progress_every == 0 or not row["complete"]
        ):
            self.progress(
                {
                    "state_id": self.state_id,
                    "method": self.method,
                    "queries": query_index,
                    "positive": sum(item.get("response") is True for item in self.audit),
                    "seconds": round(sum(item["transaction_seconds"] for item in self.audit), 1),
                }
            )
        if adapter_error is not None:
            raise UnsafePreviewError(adapter_error, row)
        if residual > self.restoration_threshold:
            raise UnsafePreviewError(
                f"restoration residual {residual:.8f} exceeds {self.restoration_threshold}",
                row,
            )
        assert observation is not None
        return PreviewObservation(
            point=(float(point[0]), float(point[1])),
            positive=bool(observation.response),
            evidence=str(observation.evidence),
        )
