from __future__ import annotations

from pathlib import Path

from inversereserve.observations.contextual_binding import (
    CONTEXT_BINDER_MAXIMUM_CANDIDATES,
    contextual_binder_prompts,
)

ROOT = Path(__file__).resolve().parents[1]


def test_contextual_prompt_binds_physical_control_and_spatial_context() -> None:
    first, second = contextual_binder_prompts(
        instruction="Rename the card named Budget review.", candidate_ocr=""
    )
    assert "BRACKETED PHYSICAL CONTROL" in first
    assert "nearby rendered labels" in first
    assert "Candidate OCR: <empty>" in first
    assert "A = NO" in first and "B = YES" in first
    assert "A = YES" in second and "B = NO" in second
    assert CONTEXT_BINDER_MAXIMUM_CANDIDATES == 12
