from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from rcrps.contextual_binding import (  # noqa: E402
    CONTEXT_BINDER_MAXIMUM_CANDIDATES,
    contextual_binder_prompts,
)


def test_contextual_prompt_binds_physical_control_and_spatial_context() -> None:
    first, second = contextual_binder_prompts(
        instruction="Rename the card named Budget review.",
        candidate_ocr="",
    )

    assert "BRACKETED PHYSICAL CONTROL" in first
    assert "nearby rendered labels" in first
    assert "Candidate OCR: <empty>" in first
    assert "A = NO" in first and "B = YES" in first
    assert "A = YES" in second and "B = NO" in second
    assert CONTEXT_BINDER_MAXIMUM_CANDIDATES == 12
