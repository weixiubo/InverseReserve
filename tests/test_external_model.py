from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from rcrps.external_model import (  # noqa: E402
    binder_prompts,
    label_symmetric_yes_score,
    risk_prompts,
    select_visual_binding,
)


def test_risk_prompt_preserves_frozen_components() -> None:
    prompt = {
        "common": "COMMON",
        "assessment_suffix": "Instruction: {instruction}\n{ocr_lines}",
        "orientation_safe_A_risky_B": "A SAFE B RISKY",
        "orientation_risky_A_safe_B": "A RISKY B SAFE",
    }

    first, second = risk_prompts(
        instruction="Open details",
        ocr_lines="view: Details",
        frozen_prompt=prompt,
    )

    assert first == "COMMON\nInstruction: Open details\nview: Details\nA SAFE B RISKY"
    assert second == "COMMON\nInstruction: Open details\nview: Details\nA RISKY B SAFE"


def test_binder_prompt_is_commit_only_and_uses_empty_marker() -> None:
    first, second = binder_prompts(
        instruction='Click the "ui-icon-play" icon.',
        candidate_ocr="",
    )

    assert "exact final target" in first
    assert "menu opener" in first
    assert "Candidate OCR: <empty>" in first
    assert "A = NO" in first and "B = YES" in first
    assert "A = YES" in second and "B = NO" in second


def test_label_symmetric_yes_and_unique_selection() -> None:
    score = label_symmetric_yes_score(
        no_a_yes_b_logits=(0.0, 4.0),
        yes_a_no_b_logits=(4.0, 0.0),
    )
    selected = select_visual_binding(
        [
            {"candidate_id": "candidate_002", "score": 0.95},
            {"candidate_id": "candidate_001", "score": 0.70},
        ]
    )

    assert score > 0.98
    assert selected is not None
    assert selected.candidate_id == "candidate_002"
    assert selected.margin == 0.25


def test_visual_selection_abstains_below_score_or_margin() -> None:
    assert (
        select_visual_binding(
            [{"candidate_id": "candidate_001", "score": 0.89}]
        )
        is None
    )
    assert (
        select_visual_binding(
            [
                {"candidate_id": "candidate_001", "score": 0.95},
                {"candidate_id": "candidate_002", "score": 0.85},
            ]
        )
        is None
    )
