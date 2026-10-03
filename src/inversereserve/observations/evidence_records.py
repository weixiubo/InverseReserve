"""Stable public evidence fields for successful and failed preview attempts."""

from __future__ import annotations

import hashlib
from typing import Any


def grounded_evidence_fields(observation: Any) -> dict[str, Any]:
    if observation is None:
        return {
            "response": None,
            "changed_pixels": None,
            "changed_fraction": None,
            "evidence": "",
            "evidence_sha256": "",
            "primary_source": None,
            "panels": [],
            "components": [],
            "panel_ocr": [],
            "component_ocr": [],
            "channels": [],
            "whole_screen_novelty": [],
            "ocr_calls": 0,
        }
    return {
        "response": bool(observation.response),
        "changed_pixels": observation.changed_pixels,
        "changed_fraction": observation.changed_fraction,
        "evidence": observation.evidence,
        "evidence_sha256": hashlib.sha256(observation.evidence.encode("utf-8")).hexdigest()
        if observation is not None and observation.evidence
        else "",
        "primary_source": observation.primary_source,
        "panels": [
            {
                "bbox_xyxy": list(panel.bbox_xyxy),
                "stratum_pixels": panel.stratum_pixels,
                "changed_overlap_pixels": panel.changed_overlap_pixels,
                "fill_fraction": panel.fill_fraction,
                "changed_overlap_fraction": panel.changed_overlap_fraction,
            }
            for panel in observation.panels
        ],
        "components": [
            {"bbox_xyxy": list(panel.bbox_xyxy), "changed_pixels": panel.changed_overlap_pixels}
            for panel in observation.panels
        ],
        "panel_ocr": list(observation.panel_ocr),
        "component_ocr": list(observation.panel_ocr),
        "channels": [
            {
                "source": channel.source,
                "text": channel.text,
                "bbox_xyxy": list(channel.bbox_xyxy) if channel.bbox_xyxy is not None else None,
            }
            for channel in observation.channels
        ],
        "whole_screen_novelty": list(observation.whole_screen_novelty),
        "ocr_calls": observation.ocr_calls,
    }


def adapter_evidence_fields(observation: Any) -> dict[str, Any]:
    if observation is None:
        return {
            "response": None,
            "changed_pixels": None,
            "changed_fraction": None,
            "evidence": "",
            "evidence_sha256": "",
            "components": [],
            "component_ocr": [],
            "whole_screen_novelty": [],
            "ocr_calls": 0,
        }
    return {
        "response": bool(observation.response),
        "changed_pixels": observation.changed_pixels,
        "changed_fraction": observation.changed_fraction,
        "evidence": observation.evidence,
        "evidence_sha256": hashlib.sha256(observation.evidence.encode("utf-8")).hexdigest()
        if observation is not None and observation.evidence
        else "",
        "components": [
            {"bbox_xyxy": list(component.bbox_xyxy), "changed_pixels": component.changed_pixels}
            for component in observation.components
        ],
        "component_ocr": list(observation.component_ocr),
        "whole_screen_novelty": list(observation.whole_screen_novelty),
        "ocr_calls": observation.ocr_calls,
    }
