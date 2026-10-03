"""Contextual physical-control binding for commit candidates."""

from __future__ import annotations


CONTEXT_BINDER_COMMON = (
    "You are a conservative GUI physical-control binder. Image 1 is the full "
    "current screen. Image 2 preserves the candidate's local context and marks "
    "the exact proposed click support with red corner brackets. Decide whether "
    "the BRACKETED PHYSICAL CONTROL is the unique control that should be clicked "
    "next to perform the instruction. Bind the control to the requested entity "
    "using nearby rendered labels, rows, cards, menus, or other spatial context, "
    "and bind its visible icon/text to the requested action. Candidate OCR may "
    "be empty for an icon. A nearby matching label or parent container can supply "
    "context but is not itself a YES unless the brackets enclose the requested "
    "click-ready control. An edit/create icon associated with the named object can "
    "satisfy a rename/edit request; reply, retweet, like, menu, and similar icons "
    "must match both the requested action and the requested row/entity. Reject a "
    "disclosure parent when the instruction instead requests a later child. Use "
    "only the instruction and rendered pixels."
)
CONTEXT_BINDER_SUFFIX = "Instruction: {instruction}\nCandidate OCR: {candidate_ocr}"
CONTEXT_BINDER_NO_A_YES_B = (
    "Answer one letter only. A = NO exact physical binding. "
    "B = YES exact physical binding."
)
CONTEXT_BINDER_YES_A_NO_B = (
    "Answer one letter only. A = YES exact physical binding. "
    "B = NO exact physical binding."
)
CONTEXT_BINDER_MAXIMUM_CANDIDATES = 12


def contextual_binder_prompts(
    *,
    instruction: str,
    candidate_ocr: str,
) -> tuple[str, str]:
    suffix = CONTEXT_BINDER_SUFFIX.format(
        instruction=instruction,
        candidate_ocr=candidate_ocr.strip() or "<empty>",
    )
    return (
        "\n".join(
            (CONTEXT_BINDER_COMMON, suffix, CONTEXT_BINDER_NO_A_YES_B)
        ),
        "\n".join(
            (CONTEXT_BINDER_COMMON, suffix, CONTEXT_BINDER_YES_A_NO_B)
        ),
    )
