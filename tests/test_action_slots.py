from __future__ import annotations

from pathlib import Path

from inversereserve.observations.action_slots import ActionSlotConfig, consolidate_action_slots
from inversereserve.observations.screenshot_candidates import ScreenshotCandidate

ROOT = Path(__file__).resolve().parents[1]


def candidate(index: int, x: float, source: str, text: str = "") -> ScreenshotCandidate:
    return ScreenshotCandidate(
        proposal_id=f"candidate_{index:03d}",
        source=source,
        source_proposal_id=f"{source}_{index:03d}",
        source_ordinal=index,
        score=float(index + 1),
        point=(x, 100.0 + index % 2),
        bbox_xyxy=(int(x - 3), 96, int(x + 3), 105),
        text=text,
    )


def test_action_slots_merge_duplicates_drop_coverage_and_clear_icon_ocr() -> None:
    rows = [
        candidate(0, 100, "component"),
        candidate(1, 108, "corner"),
        candidate(2, 152, "ocr", text="oa"),
        candidate(3, 204, "component"),
        candidate(4, 300, "coverage"),
    ]
    slots, audit = consolidate_action_slots(
        rows, image_width=400, image_height=200, config=ActionSlotConfig(horizontal_merge_pixels=20.0)
    )
    assert len(slots) == 3
    assert slots[0].point[0] == 104.0
    assert slots[0].bbox_xyxy == (86, 86, 122, 114)
    assert slots[1].text == ""
    assert all((slot.source == "action_band" for slot in slots))
    assert audit.structural_candidates == 4
    assert audit.nonstructural_candidates_dropped == 1
    assert audit.x_clusters == 3
    assert audit.slots == 3


def test_coverage_chain_cannot_bridge_two_structural_slots() -> None:
    rows = [
        candidate(0, 100, "component"),
        candidate(1, 116, "coverage"),
        candidate(2, 132, "coverage"),
        candidate(3, 148, "component"),
    ]
    slots, audit = consolidate_action_slots(
        rows, image_width=240, image_height=200, config=ActionSlotConfig(horizontal_merge_pixels=20.0)
    )
    assert [slot.point[0] for slot in slots] == [100.0, 148.0]
    assert audit.nonstructural_candidates_dropped == 2


def test_action_slots_are_clipped_to_the_screen() -> None:
    slots, _audit = consolidate_action_slots([candidate(0, 5, "component")], image_width=40, image_height=120)
    assert slots[0].bbox_xyxy[0] == 0
    assert slots[0].bbox_xyxy[2] == 23
