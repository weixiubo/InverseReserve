from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from inversereserve.contracts.goal_contracts_v4 import compile_structured_goal
from inversereserve.contracts.typed_contracts_v4 import infer_transaction_contract
from inversereserve.controllers.confirmation_agents_v10 import FullPactConfirmationDriverV10
from inversereserve.controllers.pact_controller_v4 import ActionExecutionV4
from inversereserve.controllers.pact_controller_v10 import (
    FailClosedTransactionRuntimeV10,
    InterruptRepairReservationV10,
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
        rows.append(element("popup", text="Exit to home?", dom_parent="form"))
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


def editable_contract(before: SemanticSnapshot):
    goal = compile_structured_goal('Enter the username "michel" and press login.', before)
    decision = infer_transaction_contract(before, "user", goal)
    assert decision.allowed and decision.contract is not None
    assert decision.contract.maximum_interrupt_repairs == 1
    return decision.contract


class ScriptedExecutor:
    def __init__(self, rows: list[tuple[str, str, ActionExecutionV4]]) -> None:
        self.rows = list(rows)
        self.calls: list[tuple[str, str]] = []

    def __call__(self, action, role: str) -> ActionExecutionV4:
        expected_role, expected_code, result = self.rows.pop(0)
        code = action.browsergym_code(viewport_width=800, viewport_height=600)
        assert (role, code) == (expected_role, expected_code)
        self.calls.append((role, code))
        return result


def test_v10_uses_registered_inverse_when_compensator_is_ambiguous() -> None:
    before = login()
    interrupted = login(disabled=True, popup=True, cancels=2)
    executor = ScriptedExecutor(
        [
            ("typed_forward", "fill('user', 'michel', False)", ActionExecutionV4(interrupted)),
            ("typed_inverse", "fill('user', '', False)", ActionExecutionV4(before)),
        ]
    )

    def forbidden_reservation(_contract):
        raise AssertionError("ambiguous compensators must not request repair budget")

    runtime = FailClosedTransactionRuntimeV10(executor, forbidden_reservation)
    outcome = runtime.transact(before=before, contract=editable_contract(before), candidate_label="Username")
    assert not outcome.admitted and (not outcome.halted)
    assert outcome.restoration is not None and outcome.restoration.passed
    assert [role for role, _code in executor.calls] == ["typed_forward", "typed_inverse"]
    grounding = next((event for event in runtime.events if event["type"] == "compensator_grounding"))
    assert grounding["policy"] == "inverse"
    assert grounding["allowed"] is False


def test_v10_preserves_inverse_reserve_instead_of_attempting_repair() -> None:
    before = login()
    interrupted = login(disabled=True, popup=True)
    executor = ScriptedExecutor(
        [
            ("typed_forward", "fill('user', 'michel', False)", ActionExecutionV4(interrupted)),
            ("typed_inverse", "fill('user', '', False)", ActionExecutionV4(before)),
        ]
    )
    runtime = FailClosedTransactionRuntimeV10(
        executor,
        lambda _contract: InterruptRepairReservationV10(
            remaining_gui_actions=2, repair_pair_actions=2, registered_inverse_reserve=1
        ),
    )
    outcome = runtime.transact(before=before, contract=editable_contract(before), candidate_label="Username")
    assert not outcome.admitted and (not outcome.halted)
    assert outcome.restoration is not None and outcome.restoration.passed
    assert [role for role, _code in executor.calls] == ["typed_forward", "typed_inverse"]
    reservation = next((event for event in runtime.events if event["type"] == "interrupt_repair_reservation"))
    assert reservation["allowed"] is False


def test_v10_attempts_repair_only_when_retry_leaves_inverse_reserved() -> None:
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
    runtime = FailClosedTransactionRuntimeV10(
        executor,
        lambda _contract: InterruptRepairReservationV10(
            remaining_gui_actions=3, repair_pair_actions=2, registered_inverse_reserve=1
        ),
    )
    outcome = runtime.transact(before=before, contract=editable_contract(before), candidate_label="Username")
    assert outcome.admitted and (not outcome.halted)
    assert [role for role, _code in executor.calls] == ["typed_forward", "typed_compensator", "typed_retry"]
    assert runtime.active[0].interrupt_repairs == 1


def reservation_driver(*, maximum_gui_actions: int):
    before = login()
    driver = object.__new__(FullPactConfirmationDriverV10)
    driver.budgets = {"maximum_gui_actions": maximum_gui_actions}
    driver.executor = SimpleNamespace(actions=[{"role": "typed_forward"}])
    driver.runtime = SimpleNamespace(active=[])
    driver.trace = []
    driver.interrupt_repair_reservation_audits = 0
    driver.interrupt_repair_reservation_fallbacks = 0
    return (driver, editable_contract(before))


def pre_forward_reserve_driver(*, maximum_gui_actions: int):
    contract = editable_contract(login())
    driver = object.__new__(FullPactConfirmationDriverV10)
    driver.budgets = {"maximum_gui_actions": maximum_gui_actions}
    driver.executor = SimpleNamespace(actions=[{"role": "typed_forward"}])
    driver.runtime = SimpleNamespace(active=[SimpleNamespace(contract=contract)])
    driver.trace = []
    driver.inverse_reservation_audits = 0
    driver.inventory = lambda: SimpleNamespace(contract_by_bid={contract.semantic_bid: contract})
    return (driver, SimpleNamespace(bid=contract.semantic_bid))


def test_v10_pre_forward_gate_locks_paper_b3_solvency_counterexample() -> None:
    insolvent, candidate = pre_forward_reserve_driver(maximum_gui_actions=3)
    allowed, reserve = insolvent.inverse_reserve(candidate, "transact")
    assert not allowed and reserve == 2
    assert insolvent.trace[-1] == {
        "event_index": 0,
        "type": "inverse_budget_reservation",
        "decision": "transact",
        "bid": candidate.bid,
        "active_inverse_cost": 2,
        "remaining_after_action": 1,
        "allowed": False,
    }
    solvent, candidate = pre_forward_reserve_driver(maximum_gui_actions=4)
    allowed, reserve = solvent.inverse_reserve(candidate, "transact")
    assert allowed and reserve == 2
    assert solvent.trace[-1]["remaining_after_action"] == 2


def test_v10_driver_accounts_for_compensator_retry_and_inverse_separately() -> None:
    solvent, contract = reservation_driver(maximum_gui_actions=4)
    reservation = solvent.interrupt_repair_reservation(contract)
    assert reservation.allowed
    assert reservation.remaining_gui_actions == 3
    assert reservation.repair_pair_actions == 2
    assert reservation.registered_inverse_reserve == 1
    insolvent, contract = reservation_driver(maximum_gui_actions=3)
    reservation = insolvent.interrupt_repair_reservation(contract)
    assert not reservation.allowed
    assert insolvent.interrupt_repair_reservation_fallbacks == 1
    assert insolvent.trace[-1]["allowed"] is False


def test_v10_reservation_equation_matches_every_small_integer_boundary() -> None:
    for remaining in range(9):
        for repair_pair in range(1, 5):
            for inverse_reserve in range(1, 7):
                reservation = InterruptRepairReservationV10(
                    remaining_gui_actions=remaining,
                    repair_pair_actions=repair_pair,
                    registered_inverse_reserve=inverse_reserve,
                )
                expected = remaining - repair_pair >= inverse_reserve
                assert reservation.allowed is expected
                if reservation.allowed:
                    assert remaining - repair_pair - inverse_reserve >= 0


def test_v10_driver_reserves_active_stack_plus_current_inverse() -> None:
    active_contract = SimpleNamespace(dynamic_inverse_class_token=None, inverse_actions=(object(), object()))
    solvent, proposal = reservation_driver(maximum_gui_actions=6)
    solvent.runtime.active = [SimpleNamespace(contract=active_contract)]
    reservation = solvent.interrupt_repair_reservation(proposal)
    assert reservation.remaining_gui_actions == 5
    assert reservation.repair_pair_actions == 2
    assert reservation.registered_inverse_reserve == 3
    assert reservation.allowed
    insolvent, proposal = reservation_driver(maximum_gui_actions=5)
    insolvent.runtime.active = [SimpleNamespace(contract=active_contract)]
    reservation = insolvent.interrupt_repair_reservation(proposal)
    assert reservation.remaining_gui_actions == 4
    assert reservation.registered_inverse_reserve == 3
    assert not reservation.allowed


def test_v10_failed_retry_spends_preserved_inverse_and_restores() -> None:
    before = login()
    interrupted = login(disabled=True, popup=True)
    wrong_retry = login(value="other")
    executor = ScriptedExecutor(
        [
            ("typed_forward", "fill('user', 'michel', False)", ActionExecutionV4(interrupted)),
            ("typed_compensator", "click('cancel0')", ActionExecutionV4(before)),
            ("typed_retry", "fill('user', 'michel', False)", ActionExecutionV4(wrong_retry)),
            ("typed_inverse", "fill('user', '', False)", ActionExecutionV4(before)),
        ]
    )
    runtime = FailClosedTransactionRuntimeV10(
        executor,
        lambda _contract: InterruptRepairReservationV10(
            remaining_gui_actions=4, repair_pair_actions=2, registered_inverse_reserve=1
        ),
    )
    outcome = runtime.transact(before=before, contract=editable_contract(before), candidate_label="Username")
    assert not outcome.admitted and (not outcome.halted)
    assert outcome.restoration is not None and outcome.restoration.passed
    assert runtime.active == []
    assert [role for role, _code in executor.calls] == [
        "typed_forward",
        "typed_compensator",
        "typed_retry",
        "typed_inverse",
    ]
