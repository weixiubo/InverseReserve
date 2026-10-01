from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from rcrps.typed_contracts_v3 import (  # noqa: E402
    check_sequence_postcondition,
    check_sequence_restoration,
    infer_sequence_contract,
)
from rcrps.typed_observation import SemanticElement, SemanticSnapshot  # noqa: E402


def element(
    bid: str,
    *,
    role: str = "",
    name: str = "",
    properties: dict | None = None,
    tag: str = "div",
    attributes: dict | None = None,
    parent: str | None = None,
    visible: bool = True,
    clickable: bool = True,
) -> SemanticElement:
    return SemanticElement(
        bid=bid,
        role=role,
        name=name,
        subtree_text=name,
        ax_properties=tuple(sorted((properties or {}).items())),
        ax_parent_bid=parent,
        dom_tag=tag,
        dom_attributes=tuple(sorted((attributes or {}).items())),
        dom_parent_bid=parent,
        visible=visible,
        clickable=clickable,
        bbox=(0.0, 0.0, 10.0, 10.0),
    )


def test_standard_combobox_compiles_parameterized_preview_and_exact_inverse() -> None:
    before = SemanticSnapshot(
        (
            element(
                "combo1",
                role="combobox",
                name="Country",
                properties={"hasPopup": "listbox", "value": ""},
                tag="input",
                attributes={"aria-autocomplete": "list"},
                clickable=False,
            ),
        )
    )
    decision = infer_sequence_contract(before, "combo1", query="Mon")
    assert decision.allowed and decision.contract is not None
    assert decision.contract.kind == "combobox_suggestion"
    assert decision.contract.action.browsergym_code() == (
        "fill('combo1', 'Mon', True)"
    )
    assert [
        action.browsergym_code()
        for action in decision.contract.inverse_actions
    ] == ["press('combo1', 'Escape')", "fill('combo1', '', False)"]

    after = SemanticSnapshot(
        (
            element(
                "combo1",
                role="combobox",
                name="Country",
                properties={"hasPopup": "listbox", "value": "Mon"},
                tag="input",
                attributes={"aria-autocomplete": "list"},
                clickable=False,
            ),
            element("list1", role="listbox", name="Countries", clickable=False),
            element("option1", role="option", name="Mongolia", parent="list1"),
        )
    )
    check = check_sequence_postcondition(before, after, decision.contract)
    assert check.passed
    assert check.delta.added_visible_bids == ("list1", "option1")
    assert check_sequence_restoration(before, before).passed


def test_combobox_restores_a_nonempty_public_prior_value() -> None:
    before = SemanticSnapshot(
        (
            element(
                "combo1",
                role="combobox",
                properties={"hasPopup": "listbox", "value": "prior"},
                tag="input",
            ),
        )
    )
    decision = infer_sequence_contract(before, "combo1", query="new")
    assert decision.contract is not None
    assert decision.contract.inverse_actions[-1].browsergym_code() == (
        "fill('combo1', 'prior', False)"
    )


def test_plain_or_readonly_text_inputs_are_not_promoted_to_autocomplete() -> None:
    plain = SemanticSnapshot(
        (element("plain", role="textbox", tag="input", clickable=False),)
    )
    readonly = SemanticSnapshot(
        (
            element(
                "readonly",
                role="combobox",
                properties={"hasPopup": "listbox", "readonly": "true"},
                tag="input",
                attributes={"aria-autocomplete": "list"},
                clickable=False,
            ),
        )
    )
    assert not infer_sequence_contract(plain, "plain", query="x").allowed
    assert not infer_sequence_contract(readonly, "readonly", query="x").allowed


def test_autocomplete_requires_bounded_nonempty_query() -> None:
    snapshot = SemanticSnapshot(
        (
            element(
                "combo1",
                role="combobox",
                properties={"hasPopup": "listbox"},
                tag="input",
            ),
        )
    )
    empty = infer_sequence_contract(snapshot, "combo1", query="")
    blank = infer_sequence_contract(snapshot, "combo1", query="   ")
    long = infer_sequence_contract(snapshot, "combo1", query="x" * 257)
    assert not empty.allowed and "between 1 and 256" in empty.reason
    assert not blank.allowed and "between 1 and 256" in blank.reason
    assert not long.allowed and "between 1 and 256" in long.reason


def test_autocomplete_postcondition_rejects_value_or_surface_mismatch() -> None:
    before = SemanticSnapshot(
        (
            element(
                "combo1",
                role="combobox",
                properties={"hasPopup": "listbox", "value": ""},
                tag="input",
            ),
        )
    )
    contract = infer_sequence_contract(before, "combo1", query="Mon").contract
    assert contract is not None
    wrong_value = SemanticSnapshot(
        (
            element(
                "combo1",
                role="combobox",
                properties={"hasPopup": "listbox", "value": "Other"},
                tag="input",
            ),
            element("list1", role="listbox", clickable=False),
        )
    )
    no_surface = SemanticSnapshot(
        (
            element(
                "combo1",
                role="combobox",
                properties={"hasPopup": "listbox", "value": "Mon"},
                tag="input",
            ),
        )
    )
    assert not check_sequence_postcondition(before, wrong_value, contract).passed
    assert not check_sequence_postcondition(before, no_surface, contract).passed


def test_explicit_closed_dialog_popup_compiles_escape_inverse() -> None:
    before = SemanticSnapshot(
        (
            element(
                "picker1",
                role="combobox",
                name="Date",
                properties={"hasPopup": False, "readonly": True},
                tag="input",
                attributes={"aria-haspopup": "dialog", "readonly": ""},
            ),
        )
    )
    decision = infer_sequence_contract(before, "picker1")
    assert decision.allowed and decision.contract is not None
    assert decision.contract.kind == "popup_dialog_open"
    assert decision.contract.action.browsergym_code() == "click('picker1')"
    assert decision.contract.inverse_actions[0].browsergym_code() == (
        "press('picker1', 'Escape')"
    )

    after = SemanticSnapshot(
        before.elements
        + (
            element("dialog1", role="dialog", name="Choose date", clickable=False),
            element("day1", role="button", name="1", parent="dialog1"),
        )
    )
    assert check_sequence_postcondition(before, after, decision.contract).passed


def test_popup_postcondition_rejects_an_unrelated_visible_delta() -> None:
    before = SemanticSnapshot(
        (
            element(
                "picker1",
                role="button",
                properties={"hasPopup": "dialog"},
            ),
        )
    )
    contract = infer_sequence_contract(before, "picker1").contract
    assert contract is not None
    unrelated = SemanticSnapshot(
        before.elements + (element("status1", role="status", name="Loading"),)
    )
    assert not check_sequence_postcondition(before, unrelated, contract).passed


def test_popup_postcondition_accepts_public_expanded_state() -> None:
    before = SemanticSnapshot(
        (
            element(
                "menu1",
                role="button",
                properties={"hasPopup": "menu"},
            ),
        )
    )
    contract = infer_sequence_contract(before, "menu1").contract
    assert contract is not None
    after = SemanticSnapshot(
        (
            element(
                "menu1",
                role="button",
                properties={"hasPopup": "menu", "expanded": True},
            ),
        )
    )
    assert check_sequence_postcondition(before, after, contract).passed


def test_unknown_button_and_already_open_popup_are_rejected() -> None:
    unknown = SemanticSnapshot((element("button1", role="button"),))
    opened = SemanticSnapshot(
        (
            element(
                "button2",
                role="button",
                properties={"hasPopup": "dialog", "expanded": True},
            ),
        )
    )
    assert not infer_sequence_contract(unknown, "button1").allowed
    assert not infer_sequence_contract(opened, "button2").allowed


def test_legacy_disclosure_remains_identical_and_uses_existing_checker() -> None:
    before = SemanticSnapshot(
        (
            element(
                "toggle1",
                role="button",
                properties={"expanded": False},
            ),
        )
    )
    after = SemanticSnapshot(
        (
            element(
                "toggle1",
                role="button",
                properties={"expanded": True},
            ),
            element("panel1", role="region", name="Evidence", parent="toggle1"),
        )
    )
    decision = infer_sequence_contract(before, "toggle1")
    assert decision.allowed and decision.contract is not None
    assert decision.contract.kind == "disclosure_toggle"
    assert check_sequence_postcondition(before, after, decision.contract).passed
