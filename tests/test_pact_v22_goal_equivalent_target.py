from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from rcrps.goal_contracts_v4 import compile_structured_goal  # noqa: E402
from rcrps.pact_goal_scope_v22 import (  # noqa: E402
    promote_goal_equivalent_exact_target_v22,
)
from rcrps.structured_planner_v4 import (  # noqa: E402
    ActionCandidateV4,
    V4ActionInventory,
)
from rcrps.transaction_actions_v4 import ContractActionV4  # noqa: E402
from rcrps.typed_contracts_v4 import TransactionContractV4  # noqa: E402
from rcrps.typed_observation import (  # noqa: E402
    SemanticElement,
    SemanticSnapshot,
)


def element(
    bid: str,
    *,
    role: str,
    name: str,
    parent: str | None = None,
) -> SemanticElement:
    return SemanticElement(
        bid=bid,
        role=role,
        name=name,
        subtree_text=name,
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
    *,
    role: str,
    label: str,
    semantic_bid: str | None = None,
    parent: str | None = None,
    kind: str | None = None,
) -> ActionCandidateV4:
    return ActionCandidateV4(
        bid=bid,
        action=ContractActionV4("click", bid),
        role=role,
        label=label,
        state=(),
        transaction_kind=kind,
        semantic_bid=semantic_bid or bid,
        parent_bid=parent,
    )


def contract(
    kind: str,
    semantic_bid: str,
    action_bid: str,
) -> TransactionContractV4:
    return TransactionContractV4(
        kind=kind,
        semantic_bid=semantic_bid,
        action=ContractActionV4("click", action_bid),
        inverse_actions=(ContractActionV4("click", action_bid),),
        projection_kind="global",
    )


def inventory(
    current: SemanticSnapshot,
    goal: str,
    rows: tuple[ActionCandidateV4, ...],
    contracts: tuple[tuple[str, TransactionContractV4], ...],
) -> V4ActionInventory:
    return V4ActionInventory(
        True,
        "fixture",
        compile_structured_goal(goal, current),
        rows,
        contracts,
    )


def test_v22_promotes_canonical_member_of_declared_folder_file_class() -> None:
    current = SemanticSnapshot(
        (
            element("16", role="tree", name="root"),
            element("21", role="listitem", name="Myron", parent="16"),
            element("23", role="generic", name="", parent="21"),
            element("29", role="file", name="Myron", parent="16"),
            element("30", role="generic", name="", parent="29"),
            element("31", role="listitem", name="Vanda", parent="16"),
            element("33", role="generic", name="", parent="31"),
        )
    )
    folder = candidate(
        "23",
        role="listitem",
        label="Myron",
        semantic_bid="21",
        parent="16",
        kind="tree_folder_toggle",
    )
    file = candidate(
        "30",
        role="file",
        label="Myron",
        semantic_bid="29",
        parent="16",
    )
    other = candidate(
        "33",
        role="listitem",
        label="Vanda",
        semantic_bid="31",
        parent="16",
        kind="tree_folder_toggle",
    )
    value = inventory(
        current,
        'Navigate through the file tree. Find and click on the folder or file '
        'named "Myron".',
        (folder, file, other),
        (
            ("23", contract("tree_folder_toggle", "21", "23")),
            ("33", contract("tree_folder_toggle", "31", "33")),
        ),
    )
    promoted, record = promote_goal_equivalent_exact_target_v22(
        current,
        value,
    )
    assert record is not None
    assert record["promotion_rule"] == "goal_equivalent_terminal_promotion_v22"
    assert record["promoted_bid"] == "30"
    assert record["removed_related_alias_bids"] == ["23"]
    assert tuple(row.bid for row in promoted.candidates) == ("30", "33")
    assert promoted.candidates[0].transaction_kind is None
    assert tuple(bid for bid, _contract in promoted.contracts) == ("33",)


def test_v22_retains_unqualified_duplicate_target_ambiguity() -> None:
    current = SemanticSnapshot(
        (
            element("a", role="button", name="Target"),
            element("b", role="button", name="Target"),
        )
    )
    rows = (
        candidate("a", role="button", label="Target", kind="tab_switch"),
        candidate("b", role="button", label="Target", kind="tab_switch"),
    )
    value = inventory(
        current,
        'Click "Target".',
        rows,
        (
            ("a", contract("tab_switch", "a", "a")),
            ("b", contract("tab_switch", "b", "b")),
        ),
    )
    unchanged, record = promote_goal_equivalent_exact_target_v22(
        current,
        value,
    )
    assert record is None
    assert unchanged == value


def test_v22_retains_form_prerequisite_before_submit() -> None:
    current = SemanticSnapshot(
        (
            element("field", role="textbox", name="Title"),
            element("submit", role="button", name="Submit"),
        )
    )
    rows = (
        candidate(
            "field",
            role="textbox",
            label="Title",
            kind="editable_field_assignment",
        ),
        candidate("submit", role="button", label="Submit"),
    )
    value = inventory(
        current,
        'Fill the title and click "Submit".',
        rows,
        (
            (
                "field",
                TransactionContractV4(
                    kind="editable_field_assignment",
                    semantic_bid="field",
                    action=ContractActionV4("fill", "field", "new"),
                    inverse_actions=(
                        ContractActionV4("fill", "field", "old"),
                    ),
                    expected_value="new",
                    prior_value="old",
                    projection_kind="editable_field_assignment",
                ),
            ),
        ),
    )
    unchanged, record = promote_goal_equivalent_exact_target_v22(
        current,
        value,
    )
    assert record is None
    assert unchanged == value
