"""Prompt and selection contracts for the frozen external 9B interfaces."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from .click_preview import label_symmetric_risk


BINDER_COMMON = (
    "You are a conservative GUI commit-evidence verifier. Image 1 is the full "
    "current screen. Image 2 shows one proposed control inside red corner "
    "brackets while preserving its complete support and local context. Decide "
    "whether this control uniquely denotes the exact final target explicitly "
    "requested by the instruction. A disclosure control, parent container, "
    "menu opener, tab, folder, More button, or merely related icon is not the "
    "final target. Use only the instruction and rendered pixels."
)
BINDER_SUFFIX = "Instruction: {instruction}\nCandidate OCR: {candidate_ocr}"
BINDER_NO_A_YES_B = "Answer one letter only. A = NO exact binding. B = YES exact binding."
BINDER_YES_A_NO_B = "Answer one letter only. A = YES exact binding. B = NO exact binding."
BINDER_MINIMUM_SCORE = 0.90
BINDER_MINIMUM_MARGIN = 0.15
BINDER_MAXIMUM_CANDIDATES = 12


def risk_prompts(
    *,
    instruction: str,
    ocr_lines: str,
    frozen_prompt: dict[str, str],
) -> tuple[str, str]:
    """Construct byte-identical C413 label-symmetric risk prompts."""

    suffix = frozen_prompt["assessment_suffix"].format(
        instruction=instruction,
        ocr_lines=ocr_lines,
    )
    first = "\n".join(
        (
            frozen_prompt["common"],
            suffix,
            frozen_prompt["orientation_safe_A_risky_B"],
        )
    )
    second = "\n".join(
        (
            frozen_prompt["common"],
            suffix,
            frozen_prompt["orientation_risky_A_safe_B"],
        )
    )
    return first, second


def binder_prompts(
    *,
    instruction: str,
    candidate_ocr: str,
) -> tuple[str, str]:
    suffix = BINDER_SUFFIX.format(
        instruction=instruction,
        candidate_ocr=candidate_ocr.strip() or "<empty>",
    )
    return (
        "\n".join((BINDER_COMMON, suffix, BINDER_NO_A_YES_B)),
        "\n".join((BINDER_COMMON, suffix, BINDER_YES_A_NO_B)),
    )


def label_symmetric_yes_score(
    *,
    no_a_yes_b_logits: tuple[float, float],
    yes_a_no_b_logits: tuple[float, float],
) -> float:
    """Average YES probability across an A/B meaning swap."""

    return label_symmetric_risk(
        safe_a_risky_b_logits=no_a_yes_b_logits,
        risky_a_safe_b_logits=yes_a_no_b_logits,
    )


@dataclass(frozen=True)
class VisualBindingDecision:
    candidate_id: str
    score: float
    runner_up_score: float | None
    margin: float | None


def select_visual_binding(
    rows: Iterable[dict[str, Any]],
    *,
    minimum_score: float = BINDER_MINIMUM_SCORE,
    minimum_margin: float = BINDER_MINIMUM_MARGIN,
) -> VisualBindingDecision | None:
    """Require a high-scoring unique physical candidate."""

    if not 0.0 <= minimum_score <= 1.0:
        raise ValueError("minimum_score must be in [0, 1]")
    if not 0.0 <= minimum_margin <= 1.0:
        raise ValueError("minimum_margin must be in [0, 1]")
    ordered = sorted(
        (
            {
                "candidate_id": str(row["candidate_id"]),
                "score": float(row["score"]),
            }
            for row in rows
        ),
        key=lambda row: (-row["score"], row["candidate_id"]),
    )
    if not ordered or ordered[0]["score"] + 1e-12 < minimum_score:
        return None
    if len({row["candidate_id"] for row in ordered}) != len(ordered):
        raise ValueError("duplicate visual-binding candidate id")
    runner_up = ordered[1]["score"] if len(ordered) > 1 else None
    margin = ordered[0]["score"] - runner_up if runner_up is not None else None
    if margin is not None and margin + 1e-12 < minimum_margin:
        return None
    return VisualBindingDecision(
        candidate_id=ordered[0]["candidate_id"],
        score=ordered[0]["score"],
        runner_up_score=runner_up,
        margin=margin,
    )
