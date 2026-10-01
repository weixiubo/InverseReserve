from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from rcrps.click_preview import WordBox  # noqa: E402
from rcrps.deployed_action_scope_v2 import (  # noqa: E402
    scope_deployed_action_candidates_v2,
)
from rcrps.screenshot_candidates import ScreenshotCandidate  # noqa: E402


def candidate(index: int, x: float, text: str = "") -> ScreenshotCandidate:
    return ScreenshotCandidate(
        proposal_id=f"candidate_{index:03d}",
        source="ocr" if text else "component",
        source_proposal_id=f"source_{index:03d}",
        source_ordinal=index,
        score=1.0,
        point=(x, 218.0),
        bbox_xyxy=(int(x - 8), 210, int(x + 8), 226),
        text=text,
    )


def test_noisy_icon_ocr_does_not_veto_the_physical_action_band() -> None:
    words = (WordBox("@alice", (230, 155, 285, 172), 95.0, 1, 1, 1),)
    actions = [
        candidate(0, 250),
        candidate(1, 302),
        candidate(2, 354, text="oa"),
        candidate(3, 406, text="v"),
        candidate(4, 458),
    ]

    scoped, decision = scope_deployed_action_candidates_v2(
        instruction='For the user @alice, click the "Edit" control.',
        words=words,
        candidates=actions,
    )

    assert set(scoped) == set(actions)
    assert decision.reason == "repeated_action_band_v2"
    assert decision.structural_x_clusters == 5

