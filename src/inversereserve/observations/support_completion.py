"""Task-blind support completion for small high-chroma interactive regions."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class HighChromaSupportConfig:
    saturation_minimum: int = 128
    component_area_minimum: int = 16
    component_area_maximum_fraction: float = 0.25
    connectivity: int = 8
    merge_distance_pixels: float = 4.0


def _too_close(
    point: list[float] | tuple[float, float], retained: list[dict[str, Any]], distance: float
) -> bool:
    return any(
        (
            math.hypot(float(point[0]) - float(row["point"][0]), float(point[1]) - float(row["point"][1]))
            <= distance
            for row in retained
        )
    )


def high_chroma_component_points(
    image: Any, config: HighChromaSupportConfig | None = None
) -> list[dict[str, Any]]:
    """Return deterministic high-chroma component centroids from RGB pixels only."""
    import cv2
    import numpy as np

    cfg = config or HighChromaSupportConfig()
    pixels = np.asarray(image)
    if pixels.ndim != 3 or pixels.shape[2] != 3:
        raise ValueError("high-chroma support expects an HxWx3 RGB image")
    _validate_high_chroma_config(cfg)
    height, width = pixels.shape[:2]
    saturation = cv2.cvtColor(pixels.astype(np.uint8), cv2.COLOR_RGB2HSV)[:, :, 1]
    count, labels, stats, centroids = cv2.connectedComponentsWithStats(
        (saturation >= cfg.saturation_minimum).astype(np.uint8), connectivity=cfg.connectivity
    )
    maximum_area = cfg.component_area_maximum_fraction * width * height
    rows = []
    for label in range(1, count):
        x, y, component_width, component_height, area = [int(value) for value in stats[label]]
        if area < cfg.component_area_minimum or area > maximum_area:
            continue
        component_saturation = saturation[labels == label]
        mean_saturation = float(component_saturation.mean()) if component_saturation.size else 0.0
        center_x, center_y = [float(value) for value in centroids[label]]
        rows.append(
            {
                "proposal_id": "",
                "source": "high_chroma_component",
                "score": mean_saturation * math.sqrt(float(area)),
                "point": [center_x, center_y],
                "bbox_xywh": [x, y, component_width, component_height],
                "area": area,
            }
        )
    rows.sort(
        key=lambda row: (
            -float(row["score"]),
            -int(row["area"]),
            float(row["point"][1]),
            float(row["point"][0]),
        )
    )
    retained: list[dict[str, Any]] = []
    for row in rows:
        if _too_close(row["point"], retained, cfg.merge_distance_pixels):
            continue
        row = dict(row)
        row["proposal_id"] = f"high_chroma_{len(retained):04d}"
        retained.append(row)
    return retained


def append_high_chroma_tail(
    base_pool: list[dict[str, Any]], image: Any, config: HighChromaSupportConfig | None = None
) -> tuple[list[dict[str, Any]], int]:
    """Append non-overlapping chromatic centroids without changing the base prefix."""
    cfg = config or HighChromaSupportConfig()
    retained = [dict(row) for row in base_pool]
    added = 0
    for ordinal, proposal in enumerate(high_chroma_component_points(image, cfg)):
        if _too_close(proposal["point"], retained, cfg.merge_distance_pixels):
            continue
        retained.append(
            {
                "pool_id": f"pool_{len(retained):04d}",
                "origin": "source_complete_tail",
                "source": proposal["source"],
                "source_proposal_id": proposal["proposal_id"],
                "source_ordinal": ordinal,
                "score": round(float(proposal["score"]), 8),
                "point": [round(float(proposal["point"][0]), 3), round(float(proposal["point"][1]), 3)],
                "bbox_xywh": proposal["bbox_xywh"],
                "area": int(proposal["area"]),
            }
        )
        added += 1
    return (retained, added)


def _validate_high_chroma_config(cfg: HighChromaSupportConfig) -> None:
    if not 0 <= cfg.saturation_minimum <= 255:
        raise ValueError("saturation_minimum must be in [0, 255]")
    if cfg.component_area_minimum <= 0:
        raise ValueError("component_area_minimum must be positive")
    if not 0 < cfg.component_area_maximum_fraction <= 1:
        raise ValueError("component_area_maximum_fraction must be in (0, 1]")
    if cfg.connectivity not in {4, 8}:
        raise ValueError("connectivity must be 4 or 8")
    if cfg.merge_distance_pixels < 0:
        raise ValueError("merge_distance_pixels must be nonnegative")
