from __future__ import annotations

import ast
from pathlib import Path

import pytest

from inversereserve.contracts.transaction_actions import (
    ActionSequenceContract,
    ContractAction,
    adapt_legacy_contract,
)
from inversereserve.observations.typed_observation import PreviewContract

ROOT = Path(__file__).resolve().parents[1]


def test_parameterized_actions_compile_to_strict_browsergym_syntax() -> None:
    actions = (
        ContractAction("click", "B12"),
        ContractAction("hover", "a7"),
        ContractAction("fill", "field9", 'Montr"eal', True),
        ContractAction("clear", "field9"),
        ContractAction("press", "field9", "ControlOrMeta+a"),
    )
    codes = [action.browsergym_code() for action in actions]
    assert codes == [
        "click('B12')",
        "hover('a7')",
        "fill('field9', 'Montr\"eal', True)",
        "clear('field9')",
        "press('field9', 'ControlOrMeta+a')",
    ]
    for code in codes:
        ast.parse(code, mode="eval")


def test_text_argument_is_data_not_executable_code() -> None:
    adversarial = "x'); __import__('os').system('false'); #"
    code = ContractAction("fill", "safe1", adversarial, True).browsergym_code()
    expression = ast.parse(code, mode="eval").body
    assert isinstance(expression, ast.Call)
    assert isinstance(expression.func, ast.Name)
    assert expression.func.id == "fill"
    assert len(expression.args) == 3
    assert isinstance(expression.args[1], ast.Constant)
    assert expression.args[1].value == adversarial


def test_neutral_pointer_requires_and_clamps_viewport_dimensions() -> None:
    action = ContractAction("move_to_neutral_region")
    with pytest.raises(ValueError, match="requires viewport"):
        action.browsergym_code()
    assert action.browsergym_code(viewport_width=3, viewport_height=4) == "mouse_move(1, 1)"
    assert action.browsergym_code(viewport_width=800, viewport_height=600) == "mouse_move(795, 595)"


@pytest.mark.parametrize(
    ("action", "message"),
    [
        (lambda: ContractAction("click", "bad-bid"), "unsafe BrowserGym bid"),
        (lambda: ContractAction("fill", "B1"), "requires an argument"),
        (lambda: ContractAction("fill", "B1", 7), "argument must be text"),
        (lambda: ContractAction("clear", "B1", "text"), "cannot carry an argument"),
        (lambda: ContractAction("press", "B1", "Escape\nclick"), "unsafe key"),
        (lambda: ContractAction("unknown", "B1"), "unsupported contract action"),
    ],
)
def test_invalid_action_surfaces_are_rejected(action, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        action()


def test_contract_supports_multi_action_inverse_sequences() -> None:
    contract = ActionSequenceContract(
        kind="combobox_suggestion",
        semantic_bid="combo1",
        action=ContractAction("fill", "combo1", "Mon", True),
        inverse_actions=(ContractAction("press", "combo1", "Escape"), ContractAction("clear", "combo1")),
    )
    assert [action.operation for action in contract.inverse_actions] == ["press", "clear"]


def test_legacy_contract_adapter_preserves_c428_actions() -> None:
    disclosure = PreviewContract(
        kind="disclosure_toggle",
        action_bid="toggle1",
        semantic_bid="toggle1",
        operation="click",
        inverse_operation="click",
        inverse_bid="toggle1",
    )
    adapted = adapt_legacy_contract(disclosure)
    assert adapted.kind == disclosure.kind
    assert adapted.semantic_bid == disclosure.semantic_bid
    assert adapted.action.browsergym_code() == "click('toggle1')"
    assert [action.browsergym_code() for action in adapted.inverse_actions] == ["click('toggle1')"]
    assert adapted.prior_selected_bid is None
    menu = PreviewContract(
        kind="menu_hover",
        action_bid="menu1",
        semantic_bid="menu1",
        operation="hover",
        inverse_operation="move_to_neutral_region",
        inverse_bid=None,
    )
    adapted_menu = adapt_legacy_contract(menu)
    assert adapted_menu.action.browsergym_code() == "hover('menu1')"
    assert (
        adapted_menu.inverse_actions[0].browsergym_code(viewport_width=160, viewport_height=210)
        == "mouse_move(155, 205)"
    )


def test_legacy_tab_adapter_preserves_prior_selected_identity() -> None:
    tab = PreviewContract(
        kind="tab_switch",
        action_bid="tab2",
        semantic_bid="tab2",
        operation="click",
        inverse_operation="click",
        inverse_bid="tab1",
        prior_selected_bid="tab1",
    )
    adapted = adapt_legacy_contract(tab)
    assert adapted.prior_selected_bid == "tab1"


def test_reversible_contract_rejects_empty_or_unsafe_identity() -> None:
    click = ContractAction("click", "B1")
    with pytest.raises(ValueError, match="kind cannot be empty"):
        ActionSequenceContract(" ", "B1", click, (click,))
    with pytest.raises(ValueError, match="unsafe semantic bid"):
        ActionSequenceContract("toggle", "B-1", click, (click,))
    with pytest.raises(ValueError, match="requires at least one inverse"):
        ActionSequenceContract("toggle", "B1", click, ())
    with pytest.raises(ValueError, match="unsafe prior selected bid"):
        ActionSequenceContract("tab_switch", "B1", click, (click,), "B-2")
