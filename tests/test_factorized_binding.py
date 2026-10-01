from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from rcrps.click_preview import WordBox  # noqa: E402
from rcrps.factorized_binding import (  # noqa: E402
    ACTION_BINDER_MAXIMUM_CANDIDATES,
    EntityScopeConfig,
    action_binder_prompts,
    entity_anchors,
    instruction_entity_tokens,
    scope_candidates_to_entity,
)
from rcrps.screenshot_candidates import ScreenshotCandidate  # noqa: E402


def candidate(
    candidate_id: str,
    point: tuple[float, float],
    bbox: tuple[int, int, int, int],
    *,
    text: str = "",
) -> ScreenshotCandidate:
    return ScreenshotCandidate(
        proposal_id=candidate_id,
        source="component",
        source_proposal_id=candidate_id,
        source_ordinal=int(candidate_id.rsplit("_", 1)[-1]),
        score=1.0,
        point=point,
        bbox_xyxy=bbox,
        text=text,
    )


def test_entity_extraction_prefers_handle_or_named_object_not_action() -> None:
    assert instruction_entity_tokens(
        'For the user @alice, click on the "Like" button.'
    ) == ("alice",)
    assert instruction_entity_tokens(
        "Rename the card named 'Budget review' to 'Budget review - zoomed'."
    ) == ("budget", "review")
    assert instruction_entity_tokens('Click the button labeled "OK".') == ("ok",)
    assert instruction_entity_tokens('Click "Submit".') == ()


def test_line_ocr_localizes_a_multiword_entity() -> None:
    words = (
        WordBox("Budget", (10, 20, 55, 36), 94.0, 1, 1, 1),
        WordBox("review", (60, 20, 110, 36), 92.0, 1, 1, 1),
        WordBox("Other", (10, 70, 55, 86), 90.0, 1, 1, 2),
    )

    anchors = entity_anchors(
        "Rename the card named 'Budget review' to 'Budget review - zoomed'.",
        words,
    )

    assert len(anchors) == 1
    assert anchors[0].bbox_xyxy == (10, 20, 110, 36)
    assert anchors[0].exact_matches == 2


def test_entity_anchor_tolerates_one_missing_token_but_not_zero() -> None:
    words = (
        WordBox("Roadmap", (10, 20, 75, 36), 94.0, 1, 1, 1),
        WordBox("Other", (10, 70, 55, 86), 90.0, 1, 1, 2),
    )

    anchors = entity_anchors(
        "Rename the card named 'Roadmap sync'.",
        words,
    )

    assert len(anchors) == 1
    assert anchors[0].text == "Roadmap"
    assert anchors[0].exact_matches == 1


def test_scope_removes_entity_label_parent_and_adjacent_rows() -> None:
    instruction = "Rename the card named 'Budget review'."
    words = (
        WordBox("Budget", (10, 20, 55, 36), 94.0, 1, 1, 1),
        WordBox("review", (60, 20, 110, 36), 92.0, 1, 1, 1),
        WordBox("Other", (10, 72, 55, 88), 90.0, 1, 1, 2),
    )
    target = candidate("candidate_01", (205, 28), (193, 16, 217, 40))
    adjacent = candidate("candidate_02", (205, 80), (193, 68, 217, 92))
    label = candidate(
        "candidate_03",
        (60, 28),
        (8, 18, 112, 38),
        text="Budget review",
    )
    parent = candidate("candidate_04", (115, 30), (0, 5, 230, 55))

    scoped, decision = scope_candidates_to_entity(
        instruction=instruction,
        words=words,
        candidates=[adjacent, label, parent, target],
        config=EntityScopeConfig(maximum_normalized_row_slack=0.75),
    )

    assert scoped == [target]
    assert decision.reason == "scoped"
    assert decision.rejected_entity_labels == ("candidate_03",)
    assert decision.rejected_parent_containers == ("candidate_04",)
    assert decision.retained[0].candidate_id == "candidate_01"


def test_scope_retains_multiple_actions_in_the_target_entity_row() -> None:
    instruction = 'For the user @alice, click on the "Like" button.'
    words = (
        WordBox("@alice", (10, 10, 60, 25), 95.0, 1, 1, 1),
        WordBox("@bob", (10, 130, 50, 145), 95.0, 2, 1, 1),
    )
    target_row = [
        candidate(f"candidate_0{index}", (30 + 35 * index, 70), (20 + 35 * index, 60, 40 + 35 * index, 80))
        for index in range(1, 5)
    ]
    other_row = candidate("candidate_05", (30, 185), (20, 175, 40, 195))

    scoped, decision = scope_candidates_to_entity(
        instruction=instruction,
        words=words,
        candidates=[other_row, *target_row],
    )

    assert {row.proposal_id for row in scoped} == {
        "candidate_01",
        "candidate_02",
        "candidate_03",
        "candidate_04",
    }
    assert len(decision.retained) == 4


def test_missing_explicit_entity_preserves_candidates_but_missing_ocr_abstains() -> None:
    row = candidate("candidate_01", (20, 20), (10, 10, 30, 30))
    unchanged, no_entity = scope_candidates_to_entity(
        instruction='Click "Submit".',
        words=(),
        candidates=[row],
    )
    missing, no_anchor = scope_candidates_to_entity(
        instruction='For the user @alice, click "Like".',
        words=(),
        candidates=[row],
    )

    assert unchanged == [row]
    assert not no_entity.applied
    assert missing == []
    assert no_anchor.reason == "entity_not_localized"


def test_action_prompt_declares_factorized_boundary() -> None:
    first, second = action_binder_prompts(
        instruction='For the user @alice, click on the "Like" button.',
        entity_tokens=("alice",),
        candidate_ocr="",
    )

    assert "separate" in first.lower()
    assert "Entity tokens already scoped: alice" in first
    assert "BRACKETED PHYSICAL CONTROL" in first
    assert "A = NO" in first and "B = YES" in first
    assert "A = YES" in second and "B = NO" in second
    assert ACTION_BINDER_MAXIMUM_CANDIDATES == 8
