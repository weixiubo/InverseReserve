from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from rcrps.goal_contracts_v4 import compile_structured_goal  # noqa: E402
from rcrps.pact_grounding_v4 import (  # noqa: E402
    certify_commit_v4,
    verify_commit_grounding_v4,
    verify_goal_state,
)
from rcrps.structured_planner_v4 import (  # noqa: E402
    ActionCandidateV4,
    compile_v4_inventory,
)
from rcrps.transaction_actions_v4 import ContractActionV4  # noqa: E402
from rcrps.typed_contracts_v4 import infer_transaction_contract  # noqa: E402
from rcrps.typed_observation import (  # noqa: E402
    SemanticDelta,
    SemanticElement,
    SemanticSnapshot,
)


def element(
    bid: str,
    *,
    role: str = "generic",
    name: str = "",
    text: str = "",
    tag: str = "div",
    attributes: dict[str, str] | None = None,
    properties: dict[str, object] | None = None,
    dom_parent: str | None = None,
    visible: bool = True,
    clickable: bool = False,
) -> SemanticElement:
    return SemanticElement(
        bid=bid,
        role=role,
        name=name,
        subtree_text=text,
        ax_properties=tuple(sorted((properties or {}).items())),
        ax_parent_bid=None,
        dom_tag=tag,
        dom_attributes=tuple(sorted((attributes or {}).items())),
        dom_parent_bid=dom_parent,
        visible=visible,
        clickable=clickable,
        bbox=(0.0, 0.0, 10.0, 10.0),
    )


def candidate(
    bid: str,
    *,
    role: str,
    label: str,
    parent: str | None = None,
) -> ActionCandidateV4:
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


def widget_snapshot(two: bool = False) -> SemanticSnapshot:
    rows = [
        element("check", role="checkbox", name="A", tag="input", clickable=True),
        element("radio", role="radio", name="B", tag="input", clickable=True),
    ]
    if two:
        rows.append(
            element("check2", role="checkbox", name="C", tag="input", clickable=True)
        )
    return SemanticSnapshot(tuple(rows))


def test_direct_role_certificate_requires_one_visible_authoritative_row() -> None:
    current = widget_snapshot()
    goal = compile_structured_goal('Click on a "checkbox" widget.', current)
    inventory = compile_v4_inventory(current, goal.goal)
    row = next(item for item in inventory.candidates if item.bid == "check")
    certificate = certify_commit_v4(
        current=current,
        goal=goal,
        candidate=row,
        inventory=inventory.candidates,
        active_transactions=(),
    )
    assert certificate.allowed
    assert certificate.grounding.anchor_kind == "direct_role"
    assert certificate.certified_action == ContractActionV4("click", "check")

    ambiguous_current = widget_snapshot(two=True)
    ambiguous_inventory = compile_v4_inventory(ambiguous_current, goal.goal)
    ambiguous_row = next(
        item for item in ambiguous_inventory.candidates if item.bid == "check"
    )
    rejected = certify_commit_v4(
        current=ambiguous_current,
        goal=compile_structured_goal(goal.goal, ambiguous_current),
        candidate=ambiguous_row,
        inventory=ambiguous_inventory.candidates,
        active_transactions=(),
    )
    assert not rejected.allowed
    assert rejected.grounding.competing_bids == ("check", "check2")


@dataclass(frozen=True)
class Active:
    contract: object
    delta: SemanticDelta


def autocomplete_states() -> tuple[SemanticSnapshot, SemanticSnapshot, object]:
    before = SemanticSnapshot(
        (
            element("body"),
            element(
                "field",
                role="textbox",
                name="Tags:",
                tag="input",
                attributes={"class": "ui-autocomplete-input", "value": ""},
                properties={"readonly": False, "value": ""},
                dom_parent="body",
                clickable=True,
            ),
            element("submit", role="button", name="Submit", tag="button", clickable=True),
        )
    )
    goal = compile_structured_goal(
        'Enter an item that starts with "Som" and ends with "alia".', before
    )
    contract = infer_transaction_contract(before, "field", goal).contract
    assert contract is not None
    after = SemanticSnapshot(
        (
            element("body", text="Somalia"),
            element(
                "field",
                role="textbox",
                name="Tags:",
                tag="input",
                attributes={"class": "ui-autocomplete-input", "value": "Som"},
                properties={"readonly": False, "value": "Som"},
                dom_parent="body",
                clickable=True,
            ),
            element(
                "menu",
                role="list",
                name="Somalia",
                tag="ul",
                attributes={"class": "ui-autocomplete"},
                dom_parent="body",
            ),
            element(
                "choice",
                role="listitem",
                name="Somalia",
                tag="li",
                dom_parent="menu",
                clickable=True,
            ),
            element("submit", role="button", name="Submit", tag="button", clickable=True),
        )
    )
    return before, after, contract


def test_active_autocomplete_scopes_exact_suggestion_and_blocks_early_submit() -> None:
    before, after, contract = autocomplete_states()
    goal = compile_structured_goal(
        'Enter an item that starts with "Som" and ends with "alia".', before
    )
    inventory = (
        candidate("choice", role="listitem", label="Somalia", parent="menu"),
        candidate("submit", role="button", label="Submit"),
    )
    active = (
        Active(
            contract,
            SemanticDelta(("menu", "choice"), (), ("body", "field"), ("Somalia",)),
        ),
    )
    choice = verify_commit_grounding_v4(
        current=after,
        goal=goal,
        candidate=inventory[0],
        inventory=inventory,
        active_transactions=active,
    )
    assert choice.allowed and choice.anchor_kind == "exact_target"

    early_submit = verify_commit_grounding_v4(
        current=after,
        goal=goal,
        candidate=inventory[1],
        inventory=inventory,
        active_transactions=active,
    )
    assert not early_submit.allowed


def login_snapshot(*, username: str, password: str, popup: bool = False) -> SemanticSnapshot:
    rows = [
        element("form", text="Username Password OK"),
        element("urow", text="Username", dom_parent="form"),
        element(
            "user",
            role="textbox",
            tag="input",
            attributes={"value": username},
            properties={"readonly": False, "value": username},
            dom_parent="urow",
            clickable=True,
        ),
        element("prow", text="Password", dom_parent="form"),
        element(
            "pass",
            role="textbox",
            tag="input",
            attributes={"value": password},
            properties={"readonly": False, "value": password},
            dom_parent="prow",
            clickable=True,
        ),
        element("submit", role="button", name="OK", tag="button", clickable=True),
    ]
    if popup:
        rows.extend(
            (
                element("popup", text="Exit?", dom_parent="form"),
                element("popupok", role="button", name="OK", tag="button", clickable=True),
                element("cancel", role="button", name="Cancel", tag="button", clickable=True),
            )
        )
    return SemanticSnapshot(tuple(rows))


def test_form_action_requires_all_structured_values_and_unique_terminal() -> None:
    empty = login_snapshot(username="", password="")
    goal_text = (
        'Enter the username "michel" and the password "0Tl" into the text '
        "fields and press login."
    )
    goal = compile_structured_goal(goal_text, empty)
    complete = login_snapshot(username="michel", password="0Tl")
    evidence = verify_goal_state(complete, goal)
    assert evidence.allowed and evidence.evidence_bids == ("pass", "user")
    inventory = (candidate("submit", role="button", label="OK"),)
    admitted = verify_commit_grounding_v4(
        current=complete,
        goal=goal,
        candidate=inventory[0],
        inventory=inventory,
        active_transactions=(),
    )
    assert admitted.allowed
    assert admitted.anchor_kind == "state_supported_form_action"

    incomplete = login_snapshot(username="michel", password="")
    rejected = verify_commit_grounding_v4(
        current=incomplete,
        goal=goal,
        candidate=inventory[0],
        inventory=inventory,
        active_transactions=(),
    )
    assert not rejected.allowed

    popup = login_snapshot(username="michel", password="0Tl", popup=True)
    ambiguous_inventory = (
        candidate("submit", role="button", label="OK"),
        candidate("popupok", role="button", label="OK"),
        candidate("cancel", role="button", label="Cancel"),
    )
    ambiguous = verify_commit_grounding_v4(
        current=popup,
        goal=goal,
        candidate=ambiguous_inventory[0],
        inventory=ambiguous_inventory,
        active_transactions=(),
    )
    assert not ambiguous.allowed
    assert ambiguous.competing_bids == ("popupok", "submit")


def result_snapshot() -> SemanticSnapshot:
    rows = []
    for index, (price, duration, visible) in enumerate(
        ((1103, "5h 18m", True), (1185, "4h 2m", False), (617, "14h 13m", False), (1111, "2h 34m", False))
    ):
        card = f"card{index}"
        button = f"book{index}"
        rows.extend(
            (
                element(
                    card,
                    text=f"Book flight for ${price} Duration: {duration}",
                    visible=visible,
                ),
                element(
                    button,
                    role="button",
                    name=f"Book flight for ${price}",
                    tag="button",
                    dom_parent=card,
                    visible=visible,
                    clickable=visible,
                ),
            )
        )
    return SemanticSnapshot(tuple(rows))


def test_public_comparative_certificate_can_select_unique_offscreen_argmin() -> None:
    current = result_snapshot()
    shortest_goal = (
        "Book the shortest one-way flight from: A to: B on 10/27/2016."
    )
    shortest = compile_v4_inventory(current, shortest_goal)
    rows = [
        row
        for row in shortest.candidates
        if dict(row.state).get("objective_kind") == "min_duration"
    ]
    assert len(rows) == 4
    target = next(row for row in rows if row.bid == "book3")
    assert target.publicly_actionable_offscreen
    certificate = certify_commit_v4(
        current=current,
        goal=shortest.goal_contract,
        candidate=target,
        inventory=shortest.candidates,
        active_transactions=(),
    )
    assert certificate.allowed
    assert certificate.grounding.anchor_kind == "min_duration"
    assert certificate.grounding.competing_bids == ("book3",)

    cheapest_goal = (
        "Book the cheapest one-way flight from: A to: B on 10/27/2016."
    )
    cheapest = compile_v4_inventory(current, cheapest_goal)
    cheap_target = next(row for row in cheapest.candidates if row.bid == "book2")
    cheap_certificate = certify_commit_v4(
        current=current,
        goal=cheapest.goal_contract,
        candidate=cheap_target,
        inventory=cheapest.candidates,
        active_transactions=(),
    )
    assert cheap_certificate.allowed
    assert cheap_certificate.grounding.anchor_kind == "min_cost"
