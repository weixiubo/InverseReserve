from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from rcrps.goal_contracts_v4 import compile_structured_goal  # noqa: E402
from rcrps.structured_planner_v4 import compile_v4_inventory  # noqa: E402
from rcrps.typed_contracts_v4 import (  # noqa: E402
    check_transaction_postcondition,
    check_transaction_restoration,
    contract_projection,
    infer_transaction_contract,
    synthesize_public_compensator,
)
from rcrps.typed_observation import (  # noqa: E402
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
    ax_parent: str | None = None,
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
        ax_parent_bid=ax_parent,
        dom_tag=tag,
        dom_attributes=tuple(sorted((attributes or {}).items())),
        dom_parent_bid=dom_parent,
        visible=visible,
        clickable=clickable,
        bbox=(0.0, 0.0, 10.0, 10.0),
    )


def autocomplete_snapshot(*, value: str = "", surface: bool = False, hidden_text: str = "") -> SemanticSnapshot:
    rows = [
        element("body", text=hidden_text),
        element(
            "field",
            role="textbox",
            name="Tags:",
            tag="input",
            attributes={"class": "ui-autocomplete-input", "value": value},
            properties={"readonly": False, "value": value},
            dom_parent="body",
            clickable=True,
        ),
        element("submit", role="button", name="Submit", tag="button", clickable=True),
    ]
    if surface:
        rows.extend(
            (
                element(
                    "menu",
                    role="list",
                    name="Somalia",
                    tag="ul",
                    attributes={"class": "ui-menu ui-autocomplete"},
                    dom_parent="body",
                ),
                element(
                    "choice",
                    role="generic",
                    text="Somalia",
                    tag="div",
                    attributes={"class": "ui-menu-item-wrapper"},
                    dom_parent="menu",
                ),
            )
        )
    return SemanticSnapshot(tuple(rows))


def test_jquery_autocomplete_uses_goal_query_and_scoped_restoration() -> None:
    goal = 'Enter an item that starts with "Som" and ends with "alia".'
    before = autocomplete_snapshot()
    structured = compile_structured_goal(goal, before)
    decision = infer_transaction_contract(before, "field", structured)
    assert decision.allowed and decision.contract is not None
    contract = decision.contract
    assert contract.kind == "autocomplete_query"
    assert contract.action.browsergym_code() == "fill('field', 'Som', True)"

    after = autocomplete_snapshot(value="Som", surface=True, hidden_text="Somalia")
    post = check_transaction_postcondition(before, after, contract)
    assert post.passed

    restored = autocomplete_snapshot(hidden_text="Somalia")
    assert before.semantic_fingerprint() != restored.semantic_fingerprint()
    check = check_transaction_restoration(before, restored, contract)
    assert check.passed
    assert check.delta.changed_visible_bids == ("body",)

    inventory = compile_v4_inventory(after, goal)
    choices = [row for row in inventory.candidates if row.role == "option"]
    assert [(row.bid, row.label, row.action.operation) for row in choices] == [
        ("choice", "Somalia", "click")
    ]


def test_datepicker_requires_readonly_public_marker_and_calendar_surface() -> None:
    field = element(
        "date",
        role="textbox",
        tag="input",
        attributes={"class": "hasDatepicker", "readonly": "", "value": ""},
        properties={"readonly": True},
        clickable=True,
    )
    before = SemanticSnapshot((field,))
    goal = compile_structured_goal(
        "Select 10/31/2016 as the date and hit submit.", before
    )
    decision = infer_transaction_contract(before, "date", goal)
    assert decision.allowed and decision.contract is not None
    contract = decision.contract
    assert contract.kind == "datepicker_open"
    after = SemanticSnapshot(
        (
            field,
            element(
                "calendar",
                role="generic",
                tag="div",
                attributes={"class": "ui-datepicker ui-widget"},
            ),
        )
    )
    assert check_transaction_postcondition(before, after, contract).passed
    assert check_transaction_restoration(before, before, contract).passed


def login_snapshot(
    *,
    value: str = "",
    disabled: bool = False,
    popup: bool = False,
    two_cancels: bool = False,
) -> SemanticSnapshot:
    rows = [
        element("form", text="Username Password OK"),
        element("userrow", text="Username", dom_parent="form"),
        element(
            "user",
            role="textbox",
            tag="input",
            attributes={"value": value, **({"disabled": ""} if disabled else {})},
            properties={"readonly": False, "disabled": disabled, "value": value},
            dom_parent="userrow",
            clickable=True,
        ),
        element(
            "submit",
            role="button",
            name="OK",
            tag="button",
            attributes={**({"disabled": ""} if disabled else {})},
            properties={"disabled": disabled},
            dom_parent="form",
            clickable=True,
        ),
    ]
    if popup:
        rows.extend(
            (
                element("popup", text="Exit to home page?", dom_parent="form"),
                element(
                    "bad",
                    role="button",
                    name="OK",
                    tag="button",
                    dom_parent="popup",
                    clickable=True,
                ),
                element(
                    "cancel",
                    role="button",
                    name="Cancel",
                    tag="button",
                    dom_parent="popup",
                    clickable=True,
                ),
            )
        )
    if two_cancels:
        rows.append(
            element(
                "cancel2",
                role="button",
                name="Cancel",
                tag="button",
                dom_parent="popup",
                clickable=True,
            )
        )
    return SemanticSnapshot(tuple(rows))


def test_editable_assignment_exposes_only_unique_new_abort_compensator() -> None:
    before = login_snapshot()
    goal = compile_structured_goal(
        'Enter the username "michel" and press login.', before
    )
    decision = infer_transaction_contract(before, "user", goal)
    assert decision.allowed and decision.contract is not None
    contract = decision.contract
    assert contract.kind == "editable_field_assignment"

    success = login_snapshot(value="michel")
    assert check_transaction_postcondition(before, success, contract).passed

    interrupted = login_snapshot(disabled=True, popup=True)
    assert not check_transaction_postcondition(before, interrupted, contract).passed
    compensator = synthesize_public_compensator(before, interrupted, contract)
    assert compensator is not None
    assert compensator.browsergym_code() == "click('cancel')"
    assert contract_projection(before, contract) != contract_projection(
        interrupted, contract
    )
    assert check_transaction_restoration(before, before, contract).passed

    ambiguous = login_snapshot(disabled=True, popup=True, two_cancels=True)
    assert synthesize_public_compensator(before, ambiguous, contract) is None


def select_snapshot(selected: tuple[str, ...] = ()) -> SemanticSnapshot:
    return SemanticSnapshot(
        (
            element("select", role="listbox", tag="select"),
            element(
                "a",
                role="option",
                tag="option",
                attributes={"value": "Megan"},
                properties={"selected": "Megan" in selected},
                dom_parent="select",
                visible=False,
            ),
            element(
                "b",
                role="option",
                tag="option",
                attributes={"value": "Karleen"},
                properties={"selected": "Karleen" in selected},
                dom_parent="select",
                visible=False,
            ),
            element("submit", role="button", name="Submit", tag="button", clickable=True),
        )
    )


def test_native_selection_contract_serializes_values_and_restores_prior_set() -> None:
    before = select_snapshot()
    goal = compile_structured_goal(
        "Select Megan, Karleen from the scroll list and click Submit.", before
    )
    decision = infer_transaction_contract(before, "select", goal)
    assert decision.allowed and decision.contract is not None
    contract = decision.contract
    assert contract.action.browsergym_code() == (
        "select_option('select', ['Megan', 'Karleen'])"
    )
    after = select_snapshot(("Megan", "Karleen"))
    assert check_transaction_postcondition(before, after, contract).passed
    assert check_transaction_restoration(before, before, contract).passed


def test_v4_inventory_binds_arguments_and_keeps_direct_rows_untyped() -> None:
    before = autocomplete_snapshot()
    inventory = compile_v4_inventory(
        before, 'Enter an item that starts with "Som" and ends with "alia".'
    )
    assert inventory.allowed
    rows = {row.bid: row for row in inventory.candidates}
    assert rows["field"].transaction_kind == "autocomplete_query"
    assert rows["field"].prompt_record()["arg"] == "Som"
    assert rows["submit"].transaction_kind is None

    native = compile_v4_inventory(
        select_snapshot(),
        "Select Megan, Karleen from the scroll list and click Submit.",
    )
    native_rows = {row.bid: row for row in native.candidates}
    assert native_rows["select"].transaction_kind == "native_select_update"
    assert native_rows["select"].prompt_record()["arg"] == ["Megan", "Karleen"]


def test_v4_inventory_reuses_the_initial_goal_contract_across_state_changes() -> None:
    initial = autocomplete_snapshot()
    goal = 'Enter an item that starts with "Som" and ends with "alia".'
    first = compile_v4_inventory(initial, goal)
    later = autocomplete_snapshot(value="Somalia")
    replay = compile_v4_inventory(
        later,
        goal,
        goal_contract=first.goal_contract,
    )
    assert replay.goal_contract is first.goal_contract
    assert replay.goal_contract.exact_constraint is not None

    try:
        compile_v4_inventory(
            later,
            "a different instruction",
            goal_contract=first.goal_contract,
        )
    except ValueError as error:
        assert "does not match" in str(error)
    else:
        raise AssertionError("mismatched persisted goal contract was accepted")


def calendar_snapshot(
    *,
    month: str,
    year: str = "2016",
    offset: int = 0,
) -> SemanticSnapshot:
    return SemanticSnapshot(
        (
            element(
                "date",
                role="textbox",
                tag="input",
                attributes={"class": "hasDatepicker", "readonly": "", "value": ""},
                properties={"readonly": True},
                clickable=True,
            ),
            element(
                f"calendar{offset}",
                tag="div",
                attributes={"class": "ui-datepicker"},
            ),
            element(
                f"prev{offset}",
                role="link",
                name="Prev",
                tag="a",
                attributes={"class": "ui-datepicker-prev"},
                clickable=True,
            ),
            element(
                f"next{offset}",
                role="link",
                name="Next",
                tag="a",
                attributes={"class": "ui-datepicker-next"},
                clickable=True,
            ),
            element(
                f"month{offset}",
                text=month,
                tag="span",
                attributes={"class": "ui-datepicker-month"},
            ),
            element(
                f"year{offset}",
                text=year,
                tag="span",
                attributes={"class": "ui-datepicker-year"},
            ),
        )
    )


def test_calendar_month_shift_is_goal_directed_and_uses_dynamic_inverse() -> None:
    december = calendar_snapshot(month="December")
    goal = compile_structured_goal(
        "Select 10/31/2016 as the date and hit submit.", december
    )
    prev = infer_transaction_contract(december, "prev0", goal)
    assert prev.allowed and prev.contract is not None
    contract = prev.contract
    assert contract.kind == "calendar_month_shift"
    assert contract.expected_calendar == (11, 2016)
    assert contract.dynamic_inverse_class_token == "ui-datepicker-next"
    assert contract.inverse_actions == ()

    next_decision = infer_transaction_contract(december, "next0", goal)
    assert not next_decision.allowed
    november = calendar_snapshot(month="November", offset=1)
    assert check_transaction_postcondition(december, november, contract).passed
    rebuilt_december = calendar_snapshot(month="December", offset=2)
    restored = check_transaction_restoration(december, rebuilt_december, contract)
    assert restored.passed
    assert restored.delta.changed
