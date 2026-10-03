"""Actual-browser preview transactions with provenance-bounded evidence."""

from __future__ import annotations

import time
from typing import Any, Callable

from inversereserve.interface import PreviewObservation
from inversereserve.observations.evidence_records import grounded_evidence_fields
from inversereserve.observations.grounded_evidence import (
    GroundedEvidenceObservation,
    extract_grounded_evidence,
)
from inversereserve.observations.live_observation import changed_fraction
from inversereserve.observations.live_replay import (
    LivePreviewRecorder,
    UnsafePreviewError,
    rgb_sha256,
    screenshot_image,
)


class GroundedLivePreviewRecorder(LivePreviewRecorder):
    """Execute reversible previews while retaining evidence provenance."""

    def __init__(
        self, *args: Any, extractor: Callable[..., GroundedEvidenceObservation] | None = None, **kwargs: Any
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
            raise UnsafePreviewError(f"reference drift {drift:.8f} exceeds {self.drift_threshold}", row)
        self.page.mouse.move(float(point[0]), float(point[1]))
        self.page.wait_for_timeout(self.wait_milliseconds)
        preview = screenshot_image(self.page)
        observation = None
        adapter_error = None
        try:
            observation = self.extractor(reference, preview, reference_words=self.reference_words)
        except Exception as exc:
            adapter_error = f"{type(exc).__name__}: {exc}"
        self.page.mouse.move(neutral_x, neutral_y)
        self.page.wait_for_timeout(self.wait_milliseconds)
        restored = screenshot_image(self.page)
        residual = changed_fraction(reference, restored)
        artifact = self._preview_artifact_if_needed(
            observation, query_index, adapter_error, residual, preview
        )
        row = {
            **base,
            "complete": adapter_error is None and residual <= self.restoration_threshold,
            "failure": "adapter_error"
            if adapter_error is not None
            else "restoration_failure"
            if residual > self.restoration_threshold
            else None,
            "adapter_error": adapter_error,
            "preview_rgb_sha256": rgb_sha256(preview),
            "restored_rgb_sha256": rgb_sha256(restored),
            "restored_p12_changed_fraction": residual,
            **grounded_evidence_fields(observation),
            "preview_artifact": artifact,
            "transaction_seconds": time.monotonic() - started,
        }
        self.audit.append(row)
        if self.progress is not None and (query_index % self.progress_every == 0 or not row["complete"]):
            self.progress(
                {
                    "state_id": self.state_id,
                    "method": self.method,
                    "queries": query_index,
                    "positive": sum((item.get("response") is True for item in self.audit)),
                    "seconds": round(sum((item["transaction_seconds"] for item in self.audit)), 1),
                }
            )
        if adapter_error is not None:
            raise UnsafePreviewError(adapter_error, row)
        if residual > self.restoration_threshold:
            raise UnsafePreviewError(
                f"restoration residual {residual:.8f} exceeds {self.restoration_threshold}", row
            )
        assert observation is not None
        return PreviewObservation(
            point=(float(point[0]), float(point[1])),
            positive=bool(observation.response),
            evidence=str(observation.evidence),
        )
