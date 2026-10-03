from __future__ import annotations

from pathlib import Path

from inversereserve.contracts.goal_contracts_v4 import compile_structured_goal
from inversereserve.contracts.pact_grounding_v4 import certify_commit_v4
from inversereserve.contracts.pact_grounding_v5 import certify_commit_v5, compile_existential_policy_v5
from inversereserve.contracts.transaction_actions_v4 import ContractActionV4
from inversereserve.models.structured_planner_v4 import ActionCandidateV4, compile_v4_inventory
from inversereserve.observations.typed_observation import SemanticElement, SemanticSnapshot

ROOT = Path(__file__).resolve().parents[1]


def element(
    bid: str, *, role: str, name: str, x: float, y: float, parent: str | None = None
) -> SemanticElement:
    return SemanticElement(
        bid=bid,
        role=role,
        name=name,
        subtree_text=name,
        ax_properties=(),
        ax_parent_bid=None,
        dom_tag="input" if role == "checkbox" else "div",
        dom_attributes=(),
        dom_parent_bid=parent,
        visible=True,
        clickable=True,
        bbox=(x, y, 10.0, 10.0),
    )


def candidate(bid: str, role: str, label: str, parent: str | None = None) -> ActionCandidateV4:
    return ActionCandidateV4(
        bid=bid,
        action=ContractActionV4("click", bid),
        role=role,
        label=label,
        state=(),
        transaction_kind=None,
        semantic_bid=bid,
        parent_bid=parent,
    )


def test_explicit_indefinite_role_selects_top_left_public_representative() -> None:
    current = SemanticSnapshot(
        (
            element("30", role="checkbox", name="bottom", x=0, y=30),
            element("20", role="checkbox", name="right", x=20, y=10),
            element("10", role="checkbox", name="left", x=5, y=10),
        )
    )
    goal = compile_structured_goal('Click on a "checkbox" widget.', current)
    policy = compile_existential_policy_v5(goal)
    assert policy.allowed and policy.kind == "explicit_indefinite_role"
    inventory = compile_v4_inventory(current, goal.goal)
    by_bid = {row.bid: row for row in inventory.candidates}
    assert not certify_commit_v4(
        current=current,
        goal=goal,
        candidate=by_bid["10"],
        inventory=inventory.candidates,
        active_transactions=(),
    ).allowed
    admitted = certify_commit_v5(
        current=current,
        goal=goal,
        candidate=by_bid["10"],
        inventory=inventory.candidates,
        active_transactions=(),
    )
    assert admitted.allowed
    assert admitted.grounding.competing_bids == ("10", "20", "30")
    assert admitted.grounding.certified_bid == "10"
    assert not certify_commit_v5(
        current=current,
        goal=goal,
        candidate=by_bid["20"],
        inventory=inventory.candidates,
        active_transactions=(),
    ).allowed


def test_prefix_predicate_selects_first_public_satisfier() -> None:
    current = SemanticSnapshot(
        (
            element("field", role="textbox", name="Tags", x=0, y=0),
            element("22", role="option", name="Georgia", x=10, y=50, parent="menu"),
            element("24", role="option", name="Germany", x=10, y=70, parent="menu"),
        )
    )
    goal = compile_structured_goal('Enter an item that starts with "Ge".', current)
    policy = compile_existential_policy_v5(goal)
    assert policy.allowed and policy.kind == "predicate_satisfaction_set"
    inventory = (candidate("22", "option", "Georgia", "menu"), candidate("24", "option", "Germany", "menu"))
    first = certify_commit_v5(
        current=current, goal=goal, candidate=inventory[0], inventory=inventory, active_transactions=()
    )
    assert first.allowed
    assert first.grounding.certified_bid == "22"
    assert not certify_commit_v5(
        current=current, goal=goal, candidate=inventory[1], inventory=inventory, active_transactions=()
    ).allowed


def test_duplicate_exact_referents_remain_rejected() -> None:
    current = SemanticSnapshot(
        (
            element("1", role="button", name="Delete", x=0, y=10),
            element("2", role="button", name="Delete", x=0, y=20),
        )
    )
    goal = compile_structured_goal('Click the "Delete" button.', current)
    assert not compile_existential_policy_v5(goal).allowed
    inventory = (candidate("1", "button", "Delete"), candidate("2", "button", "Delete"))
    for row in inventory:
        certificate = certify_commit_v5(
            current=current, goal=goal, candidate=row, inventory=inventory, active_transactions=()
        )
        assert not certificate.allowed
        assert certificate.grounding.competing_bids == ("1", "2")


def test_definite_role_request_does_not_enable_existential_policy() -> None:
    current = SemanticSnapshot((element("1", role="checkbox", name="A", x=0, y=0),))
    goal = compile_structured_goal('Click the "checkbox" widget.', current)
    assert goal.role_anchor is not None
    assert not compile_existential_policy_v5(goal).allowed
