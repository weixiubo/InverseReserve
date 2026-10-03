from __future__ import annotations

from pathlib import Path

from inversereserve.observations.click_preview import WordBox
from inversereserve.observations.factorized_action_binding import (
    DirectionalScopeConfig,
    scope_action_candidates_to_entity,
)
from inversereserve.observations.screenshot_candidates import ScreenshotCandidate

ROOT = Path(__file__).resolve().parents[1]


def candidate(candidate_id: str, x: float, y: float) -> ScreenshotCandidate:
    return ScreenshotCandidate(
        proposal_id=candidate_id,
        source="component",
        source_proposal_id=candidate_id,
        source_ordinal=int(candidate_id.rsplit("_", 1)[-1]),
        score=1.0,
        point=(x, y),
        bbox_xyxy=(int(x - 10), int(y - 15), int(x + 10), int(y + 15)),
    )


def test_directional_scope_removes_actions_from_the_preceding_row() -> None:
    words = (WordBox("@alice", (20, 200, 75, 216), 95.0, 1, 1, 1),)
    target_row = [candidate(f"candidate_{index}", 100 + 40 * index, 260) for index in range(5)]
    preceding_row = [candidate(f"candidate_{index + 5}", 100 + 40 * index, 140) for index in range(5)]
    scoped, decision = scope_action_candidates_to_entity(
        instruction='For the user @alice, click the "Like" control.',
        words=words,
        candidates=[*preceding_row, *target_row],
        directional_config=DirectionalScopeConfig(maximum_normalized_above_offset=0.5),
    )
    assert set(scoped) == set(target_row)
    assert decision.reason == "directionally_scoped"
    assert all((row.normalized_above_offset < 0.0 for row in decision.retained))


def test_directional_scope_preserves_controls_aligned_with_entity() -> None:
    words = (WordBox("Budget", (20, 100, 75, 116), 95.0, 1, 1, 1),)
    row = candidate("candidate_0", 200, 108)
    scoped, decision = scope_action_candidates_to_entity(
        instruction="Rename the card named 'Budget review'.", words=words, candidates=[row]
    )
    assert scoped == [row]
    assert decision.retained[0].normalized_above_offset == 0.0
