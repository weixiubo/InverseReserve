from __future__ import annotations

import time
from pathlib import Path

import pytest
from PIL import Image

from inversereserve.observations.click_preview import WordBox
from inversereserve.observations.preview_transaction import (
    METHOD_ORDER,
    METHOD_SPECS,
    BudgetExhausted,
    BudgetLedger,
    ExternalBudgetConfig,
    FrozenPlattGate,
    RestorationConfig,
    bind_unique_visible_text,
    hover_relevance,
    instruction_target_tokens,
    restoration_certificate,
)

ROOT = Path(__file__).resolve().parents[1]


def test_method_ablation_axes_are_explicit() -> None:
    assert tuple(METHOD_SPECS) == METHOD_ORDER
    assert not METHOD_SPECS["passive"].permits_preview
    assert METHOD_SPECS["risk_only"].uses_semantic_risk
    assert not METHOD_SPECS["risk_only"].restores_after_preview
    assert METHOD_SPECS["click_restore"].restores_after_preview
    assert not METHOD_SPECS["click_restore"].uses_semantic_risk
    assert not METHOD_SPECS["rps_no_provenance"].blocks_novel_click_preview
    assert not METHOD_SPECS["rps_no_binding"].requires_evidence_binding
    assert METHOD_SPECS["full_rps"].blocks_novel_click_preview
    assert METHOD_SPECS["full_rps"].requires_evidence_binding


def test_c418_platt_gate_is_monotone_and_conservative() -> None:
    gate = FrozenPlattGate()
    assert gate.calibrate(0.1) < gate.calibrate(0.5) < gate.calibrate(0.9)
    assert gate.allows(0.1)
    assert not gate.allows(0.9)
    assert not gate.allows(float("nan"))


def test_instruction_target_uses_final_quoted_phrase_and_css_tokens() -> None:
    instruction = 'Click the "Menu" button, then find the item with the "ui-icon-play" icon.'
    assert instruction_target_tokens(instruction) == ("play",)


def test_instruction_target_rejects_earlier_disclosure_quote() -> None:
    instruction = 'Click the "Menu" button, and then find and click on the item with the icon.'
    assert instruction_target_tokens(instruction) == ()
    assert instruction_target_tokens("Expand the section below and click submit.") == ("submit",)
    assert instruction_target_tokens("Select Parent>Child>Leaf") == ("leaf",)


def test_text_binding_requires_unique_exact_target() -> None:
    boxes = (
        WordBox("Save", (10, 10, 40, 22), 95.0, 1, 1, 1),
        WordBox("Playback", (10, 30, 70, 42), 90.0, 2, 1, 1),
    )
    binding = bind_unique_visible_text(instruction='Click the item labeled "Save".', word_boxes=boxes)
    icon_binding = bind_unique_visible_text(
        instruction='Click the item with the "ui-icon-play" icon.', word_boxes=boxes
    )
    assert binding is not None
    assert binding.text == "Save"
    assert binding.point == (25.0, 16.0)
    assert icon_binding is None
    assert hover_relevance('Click the item with the "ui-icon-play" icon.', "Playback")[0] == 1


def test_text_binding_abstains_on_disjoint_tie() -> None:
    boxes = (
        WordBox("Cancel", (10, 10, 50, 22), 95.0, 1, 1, 1),
        WordBox("Cancel", (80, 10, 120, 22), 95.0, 2, 1, 1),
    )
    assert bind_unique_visible_text(instruction='Click "Cancel".', word_boxes=boxes) is None


def test_restoration_certificate_uses_count_and_fraction() -> None:
    reference = Image.new("RGB", (100, 100), "white")
    restored = reference.copy()
    restored.putpixel((0, 0), (0, 0, 0))
    strict = RestorationConfig(maximum_changed_pixels=0, maximum_changed_fraction=0.0)
    passing = restoration_certificate(reference, restored)
    failing = restoration_certificate(reference, restored, strict)
    assert passing.passed
    assert passing.changed_pixels == 1
    assert passing.changed_fraction == 0.0001
    assert not failing.passed


def test_budget_ledger_refuses_overrun() -> None:
    ledger = BudgetLedger(ExternalBudgetConfig(maximum_gui_actions=2))
    ledger.require_gui_capacity(2)
    ledger.consume_gui_action(2)
    with pytest.raises(BudgetExhausted):
        ledger.require_gui_capacity(1)
    with pytest.raises(BudgetExhausted):
        ledger.consume_gui_action()
    ledger.consume_scroll(6)
    with pytest.raises(BudgetExhausted):
        ledger.consume_scroll()


def test_mandatory_restoration_can_cross_wall_cap_but_not_gui_cap() -> None:
    ledger = BudgetLedger(
        ExternalBudgetConfig(maximum_gui_actions=1, maximum_wall_seconds=0.01), started=time.monotonic() - 1.0
    )
    with pytest.raises(BudgetExhausted, match="wall_seconds"):
        ledger.consume_gui_action()
    ledger.consume_restoration_gui_action()
    assert ledger.gui_actions == 1
    assert ledger.restoration_cleanup_actions == 1
    with pytest.raises(BudgetExhausted, match="gui_actions"):
        ledger.consume_restoration_gui_action()
