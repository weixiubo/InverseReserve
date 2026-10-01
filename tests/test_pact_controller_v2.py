from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from rcrps.pact_controller import ActiveTransaction, CommitGrounding  # noqa: E402
from rcrps.pact_controller_v2 import (  # noqa: E402
    classify_exploration_relation,
    downgrade_ungrounded_commit,
    unique_grounded_fallback,
    upgrade_grounded_exploration,
)
from rcrps.structured_planner import ActionCandidate  # noqa: E402
from rcrps.typed_observation import (  # noqa: E402
    PreviewContract,
    SemanticDelta,
    SemanticElement,
    SemanticSnapshot,
)


def element(bid: str, parent: str | None = None) -> SemanticElement:
    return SemanticElement(
        bid=bid,
        role="tab",
        name=bid,
        subtree_text=bid,
        ax_properties=(),
        ax_parent_bid=parent,
        dom_tag="div",
        dom_attributes=(),
        dom_parent_bid=parent,
        visible=True,
        clickable=True,
        bbox=(0.0, 0.0, 10.0, 10.0),
    )


def candidate(
    bid: str,
    label: str | None = None,
    role: str = "tab",
    kind: str | None = "tab_switch",
    parent: str | None = "tabs",
) -> ActionCandidate:
    return ActionCandidate(
        bid=bid,
        operation="click",
        role=role,
        label=label or bid,
        state=(),
        preview_kind=kind,
        semantic_bid=bid,
        parent_bid=parent,
    )


def active(kind: str = "tab_switch", bid: str = "tab2") -> tuple[ActiveTransaction, SemanticSnapshot]:
    before = SemanticSnapshot((element("tabs"), element("tab1", "tabs"), element(bid, "tabs")))
    after = SemanticSnapshot(
        before.elements + (element("panel2", bid), element("nested", "panel2"))
    )
    contract = PreviewContract(kind, bid, bid, "click", "click", "tab1", None)
    transaction = ActiveTransaction(
        contract,
        bid,
        before,
        after,
        SemanticDelta(("panel2", "nested"), (), (bid,), ("evidence",)),
    )
    return transaction, after


def test_repeat_and_tab_sibling_are_never_nested() -> None:
    transaction, current = active()
    repeated = classify_exploration_relation(current, candidate("tab2"), transaction)
    sibling = classify_exploration_relation(current, candidate("tab3"), transaction)
    nested_menu_transaction, menu_current = active("menu_hover", "parent")
    nested = classify_exploration_relation(
        menu_current,
        candidate("nested", role="menuitem", kind="menu_hover"),
        nested_menu_transaction,
    )
    assert repeated.repeated_active and not repeated.nested
    assert not sibling.repeated_active and not sibling.nested
    assert nested.nested


def test_nested_disclosure_is_not_confused_with_disclosure_sibling() -> None:
    before = SemanticSnapshot(
        (element("root"), element("outer", "root"), element("sibling", "root"))
    )
    after = SemanticSnapshot(
        before.elements + (element("panel", "outer"), element("inner", "panel"))
    )
    transaction = ActiveTransaction(
        PreviewContract(
            "disclosure_toggle", "outer", "outer", "click", "click", None, None
        ),
        "outer",
        before,
        after,
        SemanticDelta(("panel", "inner"), (), ("outer",), ("nested",)),
    )
    nested = classify_exploration_relation(
        after,
        candidate(
            "inner", role="button", kind="disclosure_toggle", parent="panel"
        ),
        transaction,
    )
    sibling = classify_exploration_relation(
        after,
        candidate(
            "sibling", role="button", kind="disclosure_toggle", parent="root"
        ),
        transaction,
    )
    mixed_kind_sibling = classify_exploration_relation(
        after,
        candidate("sibling", role="tab", kind="tab_switch", parent="root"),
        transaction,
    )
    assert nested.nested and not nested.repeated_active
    assert not sibling.nested and not sibling.repeated_active
    assert not mixed_kind_sibling.nested and not mixed_kind_sibling.repeated_active


def test_unique_grounded_fallback_prefers_accessible_button_over_generic_wrapper() -> None:
    rows = (
        candidate("wrapper", "Close", "generic", None),
        candidate("button", "Close", "button", None),
        candidate("cancel", "Cancel", "button", None),
    )
    selected, reason = unique_grounded_fallback(
        'Click the button labeled "x".', rows
    )
    assert selected is not None and selected.bid == "button"
    assert "one preferred" in reason


def test_ambiguous_fallback_abstains_and_typed_wrong_commit_can_downgrade() -> None:
    rows = (
        candidate("save1", "Save", "button", None),
        candidate("save2", "Save", "button", None),
    )
    selected, reason = unique_grounded_fallback('Click "Save".', rows)
    assert selected is None and "ambiguous" in reason
    assert downgrade_ungrounded_commit(
        CommitGrounding(False, "mismatch", "target"), candidate("tab3")
    )
    assert not downgrade_ungrounded_commit(
        CommitGrounding(False, "mismatch", "target"),
        candidate("delete", role="button", kind=None),
    )


def test_fallback_requires_active_certificate_for_explicit_state_prerequisite() -> None:
    rows = (candidate("submit", "Submit", "button", None),)
    selected, reason = unique_grounded_fallback(
        "Expand the section below and click submit.", rows
    )
    assert selected is None
    assert "no active transaction" in reason
    selected, _reason = unique_grounded_fallback(
        "Expand the section below and click submit.",
        rows,
        allow_state_prerequisite=True,
    )
    assert selected is not None and selected.bid == "submit"


def test_exact_typed_goal_is_a_commit_even_when_control_can_expand() -> None:
    target = candidate(
        "marcella",
        "Marcella",
        "treeitem",
        "tree_folder_toggle",
        parent="tree",
    )
    goal = 'Navigate through the file tree and click "Marcella".'
    selected, _reason = unique_grounded_fallback(goal, (target,))
    assert selected == target
    assert upgrade_grounded_exploration(goal, target)
    assert not upgrade_grounded_exploration(goal, candidate("other", "Other"))
