from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from rcrps.pact_controller import (  # noqa: E402
    ActiveTransaction,
    admit_commit,
    exploration_is_nested,
    ground_commit,
    goal_declares_state_prerequisite,
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
        role="button",
        name=bid,
        subtree_text=bid,
        ax_properties=(),
        ax_parent_bid=parent,
        dom_tag="button",
        dom_attributes=(),
        dom_parent_bid=parent,
        visible=True,
        clickable=True,
        bbox=(0.0, 0.0, 10.0, 10.0),
    )


def candidate(bid: str, semantic_bid: str | None = None) -> ActionCandidate:
    return ActionCandidate(
        bid=bid,
        operation="click",
        role="button",
        label=bid,
        state=(),
        preview_kind="disclosure_toggle",
        semantic_bid=semantic_bid or bid,
        parent_bid=None,
    )


def transaction() -> tuple[ActiveTransaction, SemanticSnapshot]:
    before = SemanticSnapshot((element("section"),))
    after = SemanticSnapshot(
        (
            element("section"),
            element("panel", "section"),
            element("target", "panel"),
        )
    )
    contract = PreviewContract(
        kind="disclosure_toggle",
        action_bid="section",
        semantic_bid="section",
        operation="click",
        inverse_operation="click",
        inverse_bid="section",
    )
    active = ActiveTransaction(
        contract=contract,
        candidate_label="Section",
        before=before,
        after=after,
        delta=SemanticDelta(("panel", "target"), (), ("section",), ("Target",)),
    )
    return active, after


def test_nested_exploration_requires_membership_in_current_delta_scope() -> None:
    active, current = transaction()
    assert exploration_is_nested(current, candidate("target"), active)
    assert not exploration_is_nested(current, candidate("sibling"), active)


def test_commit_admission_accepts_direct_delta_and_explicit_state_dependency() -> None:
    active, current = transaction()
    direct = admit_commit(
        goal="Click Save",
        current=current,
        candidate=candidate("target"),
        active_transactions=(active,),
    )
    state_dependent = admit_commit(
        goal="Expand the section below and click submit.",
        current=current,
        candidate=candidate("submit"),
        active_transactions=(active,),
    )
    unrelated = admit_commit(
        goal="Click Save",
        current=current,
        candidate=candidate("unrelated"),
        active_transactions=(active,),
    )
    initial = admit_commit(
        goal="Click Save",
        current=current,
        candidate=candidate("save"),
        active_transactions=(),
    )

    assert direct.allowed and "structurally bound" in direct.reason
    assert state_dependent.allowed and "explicitly requires" in state_dependent.reason
    assert not unrelated.allowed
    assert initial.allowed and initial.supporting_transaction_depth is None


def test_state_prerequisite_templates_are_narrow() -> None:
    assert goal_declares_state_prerequisite("Switch between the tabs to find Save")
    assert goal_declares_state_prerequisite("Navigate through the file tree")
    assert goal_declares_state_prerequisite("Select Parent>Child")
    assert not goal_declares_state_prerequisite("Click Save")


def test_commit_grounding_preserves_quoted_punctuation_and_accessible_alias() -> None:
    exact = ground_commit('Click the link "Suspendisse.".', candidate("x"))
    missing_punctuation = ground_commit(
        'Click the link "Suspendisse.".',
        ActionCandidate("x", "click", "link", "Suspendisse", (), None, "x", None),
    )
    close_alias = ground_commit(
        'Click the button labeled "x".',
        ActionCandidate("close", "click", "button", "Close", (), None, "close", None),
    )
    exact_candidate = ActionCandidate(
        "target", "click", "link", "Suspendisse.", (), None, "target", None
    )

    assert not exact.allowed
    assert not missing_punctuation.allowed
    assert close_alias.allowed
    assert ground_commit('Click the link "Suspendisse.".', exact_candidate).allowed
