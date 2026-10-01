from __future__ import annotations

import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from rcrps.confirmation_agents_v10 import (  # noqa: E402
    FullPactConfirmationDriverV10,
)
from rcrps.confirmation_agents_v11 import (  # noqa: E402
    FullPactConfirmationDriverV11,
)
from rcrps.goal_contracts_v4 import compile_structured_goal  # noqa: E402
from rcrps.pact_controller_v4 import ActionExecutionV4  # noqa: E402
from rcrps.pact_controller_v10 import InterruptRepairReservationV10  # noqa: E402
from rcrps.pact_controller_v11 import FailClosedTransactionRuntimeV11  # noqa: E402
from rcrps.typed_contracts_v4 import infer_transaction_contract  # noqa: E402
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
    dom_parent: str | None = None,
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
        visible=True,
        clickable=clickable,
        bbox=(0.0, 0.0, 10.0, 10.0),
    )


def login(
    *,
    value: str = "",
    disabled: bool = False,
    popup: bool = False,
) -> SemanticSnapshot:
    rows = [
        element("form", text="Username OK"),
        element("row", text="Username", dom_parent="form"),
        element(
            "user",
            role="textbox",
            tag="input",
            attributes={"value": value},
            properties={
                "value": value,
                "readonly": False,
                "disabled": disabled,
            },
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
    return SemanticSnapshot(tuple(rows))


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
            element(
                f"surface{suffix}",
                attributes={"class": "ui-datepicker"},
            ),
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
            element(
                f"month{suffix}",
                text=month,
                tag="span",
                attributes={"class": "ui-datepicker-month"},
            ),
            element(
                f"year{suffix}",
                text="2016",
                tag="span",
                attributes={"class": "ui-datepicker-year"},
            ),
        )
    )


def editable_contract(before: SemanticSnapshot):
    goal = compile_structured_goal(
        'Enter the username "michel" and press login.', before
    )
    decision = infer_transaction_contract(before, "user", goal)
    assert decision.allowed and decision.contract is not None
    return decision.contract


def calendar_contract(before: SemanticSnapshot):
    goal = compile_structured_goal(
        "Select 10/31/2016 as the date and hit submit.", before
    )
    decision = infer_transaction_contract(before, "prev0", goal)
    assert decision.allowed and decision.contract is not None
    return decision.contract


class ScriptedExecutor:
    def __init__(self, rows: list[tuple[str, str, ActionExecutionV4]]) -> None:
        self.rows = list(rows)
        self.actions: list[dict[str, str]] = []

    def __call__(self, action, role: str) -> ActionExecutionV4:
        expected_role, expected_code, result = self.rows.pop(0)
        code = action.browsergym_code(viewport_width=800, viewport_height=600)
        assert (role, code) == (expected_role, expected_code)
        self.actions.append({"role": role, "code": code})
        return result


def forbidden_reservation(_contract):
    raise AssertionError("interrupt reservation is not used in this case")


def test_v11_skips_a_dangerous_toggle_inverse_after_a_global_no_effect() -> None:
    before = calendar("December", "0")
    executor = ScriptedExecutor(
        [
            (
                "typed_forward",
                "click('prev0')",
                ActionExecutionV4(before),
            )
        ]
    )
    runtime = FailClosedTransactionRuntimeV11(executor, forbidden_reservation)
    outcome = runtime.transact(
        before=before,
        contract=calendar_contract(before),
        candidate_label="Prev",
    )

    assert not outcome.admitted and not outcome.halted
    assert outcome.restoration is not None
    assert not outcome.restoration.attempted and outcome.restoration.passed
    assert [row["role"] for row in executor.actions] == ["typed_forward"]
    restoration = next(
        event for event in runtime.events if event["type"] == "restoration"
    )
    assert restoration["certificate_scope"] == "complete_public_snapshot"
    assert restoration["inverse_skipped"] is True
    assert restoration["global_delta_empty"] is True


def test_v11_keeps_v10_static_restoration_after_a_changed_failure() -> None:
    before = login()
    wrong = login(value="michael")
    executor = ScriptedExecutor(
        [
            (
                "typed_forward",
                "fill('user', 'michel', False)",
                ActionExecutionV4(wrong),
            ),
            (
                "typed_inverse",
                "fill('user', '', False)",
                ActionExecutionV4(before),
            ),
        ]
    )
    runtime = FailClosedTransactionRuntimeV11(executor, forbidden_reservation)
    outcome = runtime.transact(
        before=before,
        contract=editable_contract(before),
        candidate_label="Username",
    )

    assert not outcome.admitted and not outcome.halted
    assert outcome.restoration is not None and outcome.restoration.passed
    assert outcome.restoration.attempted
    assert [row["role"] for row in executor.actions] == [
        "typed_forward",
        "typed_inverse",
    ]
    assert not any(event.get("inverse_skipped") for event in runtime.events)


def test_v11_skips_inverse_when_a_repair_retry_has_no_public_effect() -> None:
    before = login()
    interrupted = login(disabled=True, popup=True)
    executor = ScriptedExecutor(
        [
            (
                "typed_forward",
                "fill('user', 'michel', False)",
                ActionExecutionV4(interrupted),
            ),
            (
                "typed_compensator",
                "click('cancel')",
                ActionExecutionV4(before),
            ),
            (
                "typed_retry",
                "fill('user', 'michel', False)",
                ActionExecutionV4(before),
            ),
        ]
    )
    runtime = FailClosedTransactionRuntimeV11(
        executor,
        lambda _contract: InterruptRepairReservationV10(
            remaining_gui_actions=3,
            repair_pair_actions=2,
            registered_inverse_reserve=1,
        ),
    )
    outcome = runtime.transact(
        before=before,
        contract=editable_contract(before),
        candidate_label="Username",
    )

    assert not outcome.admitted and not outcome.halted
    assert outcome.restoration is not None
    assert not outcome.restoration.attempted and outcome.restoration.passed
    assert [row["role"] for row in executor.actions] == [
        "typed_forward",
        "typed_compensator",
        "typed_retry",
    ]


def test_v11_driver_reports_no_effect_inverse_skips(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    before = calendar("December", "0")
    executor = ScriptedExecutor(
        [
            (
                "typed_forward",
                "click('prev0')",
                ActionExecutionV4(before),
            )
        ]
    )
    driver = object.__new__(FullPactConfirmationDriverV11)
    driver.executor = executor
    driver.budgets = {"maximum_gui_actions": 40}
    driver.interrupt_repair_reservation_audits = 0
    driver.interrupt_repair_reservation_fallbacks = 0
    driver.trace = []
    driver.runtime = FailClosedTransactionRuntimeV11(
        executor,
        forbidden_reservation,
    )
    driver.runtime.transact(
        before=before,
        contract=calendar_contract(before),
        candidate_label="Prev",
    )

    monkeypatch.setattr(
        FullPactConfirmationDriverV10,
        "result",
        lambda _self: {"metrics": {}},
    )
    result = driver.result()
    assert result["metrics"]["unchanged_public_inverse_skips"] == 1
