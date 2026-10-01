from __future__ import annotations

import inspect
import sys
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from rcrps.click_preview import WordBox
from rcrps.screenshot_candidates import (
    ScreenshotCandidate,
    ScreenshotCandidateConfig,
    coverage_candidates,
    interleave_candidates,
    ocr_candidates,
    propose_screenshot_candidates,
    radical_inverse,
)


def candidate(source: str, ordinal: int, x: float, y: float) -> ScreenshotCandidate:
    return ScreenshotCandidate(
        proposal_id="",
        source=source,
        source_proposal_id=f"{source}_{ordinal}",
        source_ordinal=ordinal,
        score=1.0,
        point=(x, y),
        bbox_xyxy=(int(x) - 1, int(y) - 1, int(x) + 1, int(y) + 1),
    )


def test_candidate_interface_is_task_blind() -> None:
    parameters = inspect.signature(propose_screenshot_candidates).parameters

    assert set(parameters) == {"image", "config", "ocr_extractor"}
    assert not ({"instruction", "target", "reward", "dom"} & set(parameters))


def test_ocr_candidates_preserve_pixels_and_text() -> None:
    observed: dict[str, object] = {}

    def extractor(_image: Image.Image, **kwargs: object) -> tuple[WordBox, ...]:
        observed.update(kwargs)
        return (
            WordBox("Menu", (10, 10, 30, 20), 91.0),
            WordBox("More", (70, 30, 90, 40), 82.0),
        )

    config = ScreenshotCandidateConfig(
        ocr_psm=11,
        ocr_scale=2,
        ocr_minimum_confidence=50.0,
        ocr_padding=4,
    )
    rows = ocr_candidates(Image.new("RGB", (100, 60), "white"), config, extractor=extractor)

    assert observed == {"psm": 11, "scale": 2, "minimum_confidence": 50.0}
    assert [row.text for row in rows] == ["Menu", "More"]
    assert rows[0].bbox_xyxy == (6, 6, 34, 24)
    assert rows[0].point == (20.0, 15.0)
    assert rows[0].to_json()["bbox_xyxy"] == [6, 6, 34, 24]


def test_interleave_order_cap_and_distance_merge() -> None:
    config = ScreenshotCandidateConfig(global_cap=6, merge_distance=2.0)
    rows = interleave_candidates(
        ocr=[candidate("ocr", 0, 10, 10), candidate("ocr", 1, 50, 10)],
        structure=[
            candidate("corner", 0, 20, 10),
            candidate("component", 1, 30, 10),
            candidate("corner", 2, 40, 10),
        ],
        coverage=[
            candidate("coverage", 0, 10.5, 10.5),
            candidate("coverage", 1, 60, 10),
        ],
        config=config,
    )

    assert [row.source for row in rows] == [
        "ocr",
        "corner",
        "component",
        "coverage",
        "ocr",
        "corner",
    ]
    assert [row.proposal_id for row in rows] == [f"candidate_{i:03d}" for i in range(6)]
    assert all(row.point != (10.5, 10.5) for row in rows)


def test_halton_coverage_is_deterministic_and_in_bounds() -> None:
    config = ScreenshotCandidateConfig(maximum_coverage=4)
    image = Image.new("RGB", (101, 61), "white")
    first = coverage_candidates(image, config)
    second = coverage_candidates(image, config)

    assert radical_inverse(1, 2) == 0.5
    assert radical_inverse(2, 2) == 0.25
    assert [row.to_json() for row in first] == [row.to_json() for row in second]
    assert first[0].point == (50.0, 20.0)
    assert all(0 <= row.point[0] < image.width for row in first)
    assert all(0 <= row.point[1] < image.height for row in first)
