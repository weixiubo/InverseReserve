from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from rcrps.pact_grounding_v6 import certify_commit_v6  # noqa: E402
from rcrps.structured_planner_v6 import (  # noqa: E402
    StructuredGoalContractV6,
    compile_v6_inventory,
)
from rcrps.typed_observation import SemanticElement, SemanticSnapshot  # noqa: E402


def element(
    bid: str,
    *,
    role: str,
    tag: str,
    input_type: str = "",
    text: str,
    y: float,
    clickable: bool = False,
) -> SemanticElement:
    attributes = {"type": input_type} if input_type else {}
    return SemanticElement(
        bid=bid,
        role=role,
        name="",
        subtree_text=text,
        ax_properties=(),
        ax_parent_bid=None,
        dom_tag=tag,
        dom_attributes=tuple(sorted(attributes.items())),
        dom_parent_bid=None,
        visible=True,
        clickable=clickable,
        bbox=(3.0, y, 100.0, 30.0),
    )


def mixed_snapshot() -> SemanticSnapshot:
    return SemanticSnapshot(
        (
            element("14", role="textbox", tag="textarea", text="first", y=85.5),
            element("16", role="button", tag="button", text="button", y=135.0),
            element(
                "19",
                role="checkbox",
                tag="input",
                input_type="checkbox",
                text="check",
                y=178.5,
                clickable=True,
            ),
            element("21", role="textbox", tag="textarea", text="second", y=210.0),
            element(
                "24",
                role="radio",
                tag="input",
                input_type="radio",
                text="radio",
                y=264.0,
                clickable=True,
            ),
            element(
                "26",
                role="textbox",
                tag="input",
                input_type="text",
                text="plain",
                y=300.0,
                clickable=True,
            ),
        )
    )


def certificates(snapshot: SemanticSnapshot, goal: str):
    inventory = compile_v6_inventory(snapshot, goal)
    rows = []
    for candidate in inventory.candidates:
        certificate = certify_commit_v6(
            current=snapshot,
            goal=inventory.goal_contract,
            candidate=candidate,
            inventory=inventory.candidates,
            active_transactions=(),
        )
        rows.append((candidate, certificate))
    return inventory, rows


def test_textarea_leafs_enter_inventory_despite_false_clickable_heuristic() -> None:
    snapshot = mixed_snapshot()
    inventory, rows = certificates(snapshot, 'Click on a "textarea" widget.')
    assert isinstance(inventory.goal_contract, StructuredGoalContractV6)
    assert inventory.goal_contract.allowed
    assert inventory.goal_contract.widget_kind_anchor.kind == "textarea"
    textarea_rows = [
        row
        for row in inventory.candidates
        if dict(row.state).get("standard_widget_kind") == "textarea"
    ]
    assert [(row.bid, row.action.operation) for row in textarea_rows] == [
        ("14", "click"),
        ("21", "click"),
    ]
    admitted = [(row.bid, cert) for row, cert in rows if cert.allowed]
    assert len(admitted) == 1
    assert admitted[0][0] == "14"
    assert admitted[0][1].grounding.anchor_kind == "explicit_widget_kind"
    assert admitted[0][1].grounding.competing_bids == ("14", "21")


def test_text_widget_matches_input_but_not_textarea() -> None:
    snapshot = mixed_snapshot()
    inventory, rows = certificates(snapshot, 'Click on a "text" widget.')
    kinds = {
        row.bid: dict(row.state).get("standard_widget_kind")
        for row in inventory.candidates
    }
    assert kinds.get("26") == "text"
    assert kinds.get("14") is None
    admitted = [row.bid for row, cert in rows if cert.allowed]
    assert admitted == ["26"]


def test_standard_button_leaf_is_used_instead_of_clickable_container() -> None:
    snapshot = mixed_snapshot()
    inventory, rows = certificates(snapshot, 'Click on a "button" widget.')
    button = next(row for row in inventory.candidates if row.bid == "16")
    assert dict(button.state)["standard_widget_kind"] == "button"
    assert [row.bid for row, cert in rows if cert.allowed] == ["16"]


def test_definite_or_nonstandard_widget_does_not_enable_v6_adapter() -> None:
    snapshot = mixed_snapshot()
    definite = compile_v6_inventory(snapshot, 'Click the "textarea" widget.')
    assert not isinstance(definite.goal_contract, StructuredGoalContractV6)
    assert all(
        dict(row.state).get("standard_widget_kind") is None
        for row in definite.candidates
    )

    unsupported = compile_v6_inventory(snapshot, 'Click on a "canvas" widget.')
    assert not unsupported.allowed
    assert unsupported.candidates == ()
