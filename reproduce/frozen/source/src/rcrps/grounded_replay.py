"""Actual-browser preview transactions with provenance-bounded evidence."""

from __future__ import annotations

import hashlib
import time
from typing import Any, Callable

from .grounded_evidence import GroundedEvidenceObservation, extract_grounded_evidence
from .interface import PreviewObservation
from .live_observation import changed_fraction
from .live_replay import (
    LivePreviewRecorder,
    UnsafePreviewError,
    rgb_sha256,
    screenshot_image,
)


class GroundedLivePreviewRecorder(LivePreviewRecorder):
    """Execute reversible previews while retaining evidence provenance."""

    def __init__(
        self,
        *args: Any,
        extractor: Callable[..., GroundedEvidenceObservation] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.extractor = extractor or extract_grounded_evidence

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
            observation = self.extractor(
                reference,
                preview,
                reference_words=self.reference_words,
            )
        except Exception as exc:  # restoration must still run after OCR failure
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
                "positive"
                if observation is not None and observation.response
                else "audit",
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
            "primary_source": observation.primary_source
            if observation is not None
            else None,
            "panels": (
                [
                    {
                        "bbox_xyxy": list(panel.bbox_xyxy),
                        "stratum_pixels": panel.stratum_pixels,
                        "changed_overlap_pixels": panel.changed_overlap_pixels,
                        "fill_fraction": panel.fill_fraction,
                        "changed_overlap_fraction": panel.changed_overlap_fraction,
                    }
                    for panel in observation.panels
                ]
                if observation is not None
                else []
            ),
            "components": (
                [
                    {
                        "bbox_xyxy": list(panel.bbox_xyxy),
                        "changed_pixels": panel.changed_overlap_pixels,
                    }
                    for panel in observation.panels
                ]
                if observation is not None
                else []
            ),
            "panel_ocr": list(observation.panel_ocr)
            if observation is not None
            else [],
            "component_ocr": list(observation.panel_ocr)
            if observation is not None
            else [],
            "channels": (
                [
                    {
                        "source": channel.source,
                        "text": channel.text,
                        "bbox_xyxy": list(channel.bbox_xyxy)
                        if channel.bbox_xyxy is not None
                        else None,
                    }
                    for channel in observation.channels
                ]
                if observation is not None
                else []
            ),
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
                    "positive": sum(
                        item.get("response") is True for item in self.audit
                    ),
                    "seconds": round(
                        sum(item["transaction_seconds"] for item in self.audit), 1
                    ),
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
