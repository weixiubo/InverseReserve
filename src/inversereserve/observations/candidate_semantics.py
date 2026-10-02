"""Visual context representation for candidate action semantics."""

from __future__ import annotations

import math
from typing import Any


def adaptive_candidate_context_crop(
    image: Any,
    bbox_xyxy: tuple[float, float, float, float],
    *,
    minimum_context_size: tuple[int, int] = (320, 192),
    candidate_padding: int = 32,
    maximum_output_size: tuple[int, int] = (768, 384),
    maximum_upscale: float = 2.0,
    bracket_offset: int = 4,
    bracket_length: int = 12,
    bracket_width: int = 3,
) -> Any:
    """Preserve a complete candidate box and a minimum contextual field."""

    from PIL import Image, ImageDraw

    if minimum_context_size[0] <= 0 or minimum_context_size[1] <= 0:
        raise ValueError("minimum_context_size must be positive")
    if candidate_padding < 0:
        raise ValueError("candidate_padding must be nonnegative")
    if maximum_output_size[0] <= 0 or maximum_output_size[1] <= 0:
        raise ValueError("maximum_output_size must be positive")
    if maximum_upscale <= 0.0:
        raise ValueError("maximum_upscale must be positive")
    for name, value in (
        ("bracket_offset", bracket_offset),
        ("bracket_length", bracket_length),
        ("bracket_width", bracket_width),
    ):
        if value <= 0:
            raise ValueError(f"{name} must be positive")

    rgb = image.convert("RGB")
    box_left = max(0, min(rgb.width, int(math.floor(bbox_xyxy[0]))))
    box_top = max(0, min(rgb.height, int(math.floor(bbox_xyxy[1]))))
    box_right = max(0, min(rgb.width, int(math.ceil(bbox_xyxy[2]))))
    box_bottom = max(0, min(rgb.height, int(math.ceil(bbox_xyxy[3]))))
    if box_right <= box_left or box_bottom <= box_top:
        raise ValueError("candidate bbox must have positive clipped area")

    requested_width = min(
        rgb.width,
        max(
            int(minimum_context_size[0]),
            box_right - box_left + 2 * candidate_padding,
        ),
    )
    requested_height = min(
        rgb.height,
        max(
            int(minimum_context_size[1]),
            box_bottom - box_top + 2 * candidate_padding,
        ),
    )
    crop_left = int(math.floor((box_left + box_right - requested_width) / 2.0))
    crop_top = int(math.floor((box_top + box_bottom - requested_height) / 2.0))
    crop_left = max(0, min(rgb.width - requested_width, crop_left))
    crop_top = max(0, min(rgb.height - requested_height, crop_top))
    crop_right = crop_left + requested_width
    crop_bottom = crop_top + requested_height
    if not (
        crop_left <= box_left < box_right <= crop_right and crop_top <= box_top < box_bottom <= crop_bottom
    ):
        raise ValueError("adaptive crop failed to preserve candidate support")

    crop = rgb.crop((crop_left, crop_top, crop_right, crop_bottom))
    left = box_left - crop_left
    top = box_top - crop_top
    right = box_right - crop_left
    bottom = box_bottom - crop_top
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
    draw = ImageDraw.Draw(crop)
    for segment in segments:
        draw.line(segment, fill=(255, 0, 0), width=bracket_width)

    scale = min(
        maximum_output_size[0] / crop.width,
        maximum_output_size[1] / crop.height,
        maximum_upscale,
    )
    output_size = (
        max(1, int(round(crop.width * scale))),
        max(1, int(round(crop.height * scale))),
    )
    if output_size != crop.size:
        crop = crop.resize(output_size, Image.Resampling.LANCZOS)
    return crop
