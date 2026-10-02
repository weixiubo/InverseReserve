from __future__ import annotations

from pathlib import Path

import pytest

from inversereserve.contracts.goal_contracts_v4 import compile_structured_goal
from inversereserve.contracts.typed_contracts_v4 import infer_transaction_contract
from inversereserve.controllers.pact_controller_v4 import (
    ActionExecutionV4,
    FailClosedTransactionRuntimeV4,
    RuntimeHaltedV4,
)
from inversereserve.observations.typed_observation import SemanticElement, SemanticSnapshot

ROOT = Path(__file__).resolve().parents[1]


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


def login(
    *, value: str = "", disabled: bool = False, popup: bool = False, cancels: int = 1
) -> SemanticSnapshot:
    rows = [
        element("form", text="Username OK"),
        element("row", text="Username", dom_parent="form"),
        element(
            "user",
            role="textbox",
            tag="input",
            attributes={"value": value, **({"disabled": ""} if disabled else {})},
            properties={"value": value, "readonly": False, "disabled": disabled},
            dom_parent="row",
            clickable=True,
        ),
        element(
            "submit",
            role="button",
            name="OK",
            tag="button",
            properties={"disabled": disabled},
            dom_parent="form",
            clickable=True,
        ),
    ]
    if popup:
        rows.extend(
            (
                element("popup", text="Exit to home?", dom_parent="form"),
                element("unsafe", role="button", name="OK", tag="button", dom_parent="popup", clickable=True),
            )
        )
        for index in range(cancels):
            rows.append(
                element(
                    f"cancel{index}",
                    role="button",
                    name="Cancel",
                    tag="button",
                    dom_parent="popup",
                    clickable=True,
                )
            )
    return SemanticSnapshot(tuple(rows))


def contract(before: SemanticSnapshot):
    goal = compile_structured_goal('Enter the username "michel" and press login.', before)
    decision = infer_transaction_contract(before, "user", goal)
    assert decision.allowed and decision.contract is not None
    return decision.contract


class ScriptedExecutor:
    def __init__(self, rows: list[tuple[str, str, ActionExecutionV4]]) -> None:
        self.rows = list(rows)
        self.calls: list[tuple[str, str]] = []

    def __call__(self, action, role: str) -> ActionExecutionV4:
        expected_role, expected_code, result = self.rows.pop(0)
        code = action.browsergym_code(viewport_width=800, viewport_height=600)
        assert role == expected_role
        assert code == expected_code
        self.calls.append((role, code))
        return result


def test_v4_runtime_admits_and_restores_a_normal_field_transaction() -> None:
    before = login()
    filled = login(value="michel")
    executor = ScriptedExecutor(
        [
            ("typed_forward", "fill('user', 'michel', False)", ActionExecutionV4(filled)),
            ("typed_inverse", "fill('user', '', False)", ActionExecutionV4(before)),
        ]
    )
    runtime = FailClosedTransactionRuntimeV4(executor)
    outcome = runtime.transact(before=before, contract=contract(before), candidate_label="Username")
    assert outcome.admitted and (not outcome.halted)
    assert len(runtime.active) == 1
    restored = runtime.restore_top("test cleanup")
    assert restored.passed
    assert runtime.active == []
    assert [event["type"] for event in runtime.events] == ["action", "postcondition", "action", "restoration"]


def test_v4_runtime_compensates_public_cancel_and_retries_once() -> None:
    before = login()
    interrupted = login(disabled=True, popup=True)
    filled = login(value="michel")
    executor = ScriptedExecutor(
        [
            ("typed_forward", "fill('user', 'michel', False)", ActionExecutionV4(interrupted)),
            ("typed_compensator", "click('cancel0')", ActionExecutionV4(before)),
            ("typed_retry", "fill('user', 'michel', False)", ActionExecutionV4(filled)),
        ]
    )
    runtime = FailClosedTransactionRuntimeV4(executor)
    outcome = runtime.transact(before=before, contract=contract(before), candidate_label="Username")
    assert outcome.admitted
    assert outcome.interrupt_repairs == 1
    assert outcome.restoration is not None and outcome.restoration.passed
    assert runtime.active[0].interrupt_repairs == 1
    assert [event["type"] for event in runtime.events] == [
        "action",
        "postcondition",
        "compensator_grounding",
        "action",
        "restoration",
        "action",
        "postcondition",
    ]


def test_v4_runtime_halts_without_clicking_ambiguous_compensators() -> None:
    before = login()
    interrupted = login(disabled=True, popup=True, cancels=2)
    executor = ScriptedExecutor(
        [("typed_forward", "fill('user', 'michel', False)", ActionExecutionV4(interrupted))]
    )
    runtime = FailClosedTransactionRuntimeV4(executor)
    outcome = runtime.transact(before=before, contract=contract(before), candidate_label="Username")
    assert not outcome.admitted and outcome.halted
    assert len(executor.calls) == 1
    assert runtime.events[-1]["type"] == "fail_closed"
    with pytest.raises(RuntimeHaltedV4):
        runtime.transact(before=before, contract=contract(before), candidate_label="Username")


def test_v4_runtime_treats_terminal_forward_or_compensation_as_fail_closed() -> None:
    before = login()
    executor = ScriptedExecutor(
        [
            (
                "typed_forward",
                "fill('user', 'michel', False)",
                ActionExecutionV4(login(value="michel"), terminated=True),
            )
        ]
    )
    runtime = FailClosedTransactionRuntimeV4(executor)
    outcome = runtime.transact(before=before, contract=contract(before), candidate_label="Username")
    assert outcome.halted and (not outcome.admitted)
    assert "terminated" in runtime.halt_reason


def calendar(month: str, suffix: str) -> SemanticSnapshot:
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
            element(f"surface{suffix}", tag="div", attributes={"class": "ui-datepicker"}),
            element(
                f"prev{suffix}",
                role="link",
                name="Prev",
                tag="a",
                attributes={"class": "ui-datepicker-prev"},
                clickable=True,
            ),
            element(
                f"next{suffix}",
                role="link",
                name="Next",
                tag="a",
                attributes={"class": "ui-datepicker-next"},
                clickable=True,
            ),
            element(f"month{suffix}", text=month, tag="span", attributes={"class": "ui-datepicker-month"}),
            element(f"year{suffix}", text="2016", tag="span", attributes={"class": "ui-datepicker-year"}),
        )
    )


def test_v4_runtime_recompiles_calendar_inverse_after_dom_rebuild() -> None:
    december = calendar("December", "0")
    november = calendar("November", "1")
    rebuilt_december = calendar("December", "2")
    goal = compile_structured_goal("Select 10/31/2016 as the date and hit submit.", december)
    decision = infer_transaction_contract(december, "prev0", goal)
    assert decision.allowed and decision.contract is not None
    executor = ScriptedExecutor(
        [
            ("typed_forward", "click('prev0')", ActionExecutionV4(november)),
            ("typed_inverse", "click('next1')", ActionExecutionV4(rebuilt_december)),
        ]
    )
    runtime = FailClosedTransactionRuntimeV4(executor)
    outcome = runtime.transact(before=december, contract=decision.contract, candidate_label="Prev")
    assert outcome.admitted
    restored = runtime.restore_top("calendar cleanup")
    assert restored.passed
    assert any((event["type"] == "dynamic_inverse_grounding" for event in runtime.events))
