from __future__ import annotations

from pathlib import Path

from inversereserve.observations.click_preview import WordBox
from inversereserve.observations.deployed_action_scope import scope_deployed_action_candidates
from inversereserve.observations.screenshot_candidates import ScreenshotCandidate

ROOT = Path(__file__).resolve().parents[1]


def candidate(index: int, x: float, y: float, source: str = "component") -> ScreenshotCandidate:
    return ScreenshotCandidate(
        proposal_id=f"candidate_{index:03d}",
        source=source,
        source_proposal_id=f"{source}_{index:03d}",
        source_ordinal=index,
        score=1.0,
        point=(x, y),
        bbox_xyxy=(int(x - 8), int(y - 7), int(x + 8), int(y + 7)),
    )


def test_repeated_band_rejects_handle_glyphs_and_keeps_actions() -> None:
    words = (
        WordBox("@alice", (230, 155, 285, 172), 95.0, 1, 1, 1),
        WordBox("Status", (230, 182, 278, 198), 92.0, 1, 1, 2),
    )
    handle_glyphs = [candidate(index, 240 + 15 * index, 164) for index in range(3)]
    body_glyph = candidate(3, 250, 190)
    actions = [candidate(index + 4, 250 + 52 * index, 218) for index in range(5)]
    scoped, decision = scope_deployed_action_candidates(
        instruction='For the user @alice, click the "Like" control.',
        words=words,
        candidates=[*handle_glyphs, body_glyph, *actions],
    )
    assert set(scoped) == set(actions)
    assert decision.used_action_band
    assert decision.structural_x_clusters == 5
    assert decision.reason == "repeated_action_band"


def test_unique_same_row_control_uses_conservative_fallback() -> None:
    words = (WordBox("Budget", (20, 100, 75, 116), 95.0, 1, 1, 1),)
    pencil = candidate(0, 200, 108)
    scoped, decision = scope_deployed_action_candidates(
        instruction="Rename the card named 'Budget review'.", words=words, candidates=[pencil]
    )
    assert scoped == [pencil]
    assert not decision.used_action_band
    assert decision.reason == "no_repeated_action_band_fallback"
