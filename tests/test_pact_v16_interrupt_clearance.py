from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

from rcrps.confirmation_agents_v16 import (  # noqa: E402
    interrupt_clearance_metrics_v16,
)
from rcrps.confirmation_agents_v16 import FullPactConfirmationDriverV16  # noqa: E402
from rcrps.pact_controller_v4 import ActionExecutionV4  # noqa: E402
from rcrps.pact_controller_v10 import InterruptRepairReservationV10  # noqa: E402
from rcrps.pact_controller_v16 import (  # noqa: E402
    ActiveRestoreClearanceReservationV16,
    FailClosedTransactionRuntimeV16,
)
from test_pact_v10_recovery_reservation import (  # noqa: E402
    ScriptedExecutor,
    editable_contract,
    login,
)


def reservation(*, remaining: int) -> InterruptRepairReservationV10:
    return InterruptRepairReservationV10(
        remaining_gui_actions=remaining,
        repair_pair_actions=2,
        registered_inverse_reserve=1,
    )


def active_reservation(
    *, remaining: int, reserve: int = 1
) -> ActiveRestoreClearanceReservationV16:
    return ActiveRestoreClearanceReservationV16(
        remaining_gui_actions=remaining,
        clearance_actions=1,
        active_inverse_reserve=reserve,
    )


def test_v16_clears_interrupt_without_retry_when_clearance_restores() -> None:
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
                "click('cancel0')",
                ActionExecutionV4(before),
            ),
        ]
    )
    runtime = FailClosedTransactionRuntimeV16(
        executor,
        lambda _contract: reservation(remaining=2),
        lambda _contract: active_reservation(remaining=2),
    )
    outcome = runtime.transact(
        before=before,
        contract=editable_contract(before),
        candidate_label="Username",
    )
    assert not outcome.admitted and not outcome.halted
    assert outcome.interrupt_repairs == 1
    assert outcome.restoration is not None
    assert outcome.restoration.attempted and outcome.restoration.passed
    assert [role for role, _code in executor.calls] == [
        "typed_forward",
        "typed_compensator",
    ]
    assert not executor.rows
    clearance = next(
        event
        for event in runtime.events
        if event["type"] == "interrupt_clearance_reservation_v16"
    )
    assert clearance == {
        "event_index": clearance["event_index"],
        "type": "interrupt_clearance_reservation_v16",
        "remaining_gui_actions": 2,
        "clearance_actions": 1,
        "registered_inverse_reserve": 1,
        "retry_actions": 0,
        "allowed": True,
    }
    assert any(
        event.get("type") == "interrupt_clearance_projection_v16"
        and event.get("passed") is True
        for event in runtime.events
    )
    metrics = interrupt_clearance_metrics_v16(SimpleNamespace(runtime=runtime))
    assert metrics["proposal_clearance_restoration_attempts_v16"] == 1
    assert metrics["proposal_clearance_restoration_passes_v16"] == 1
    assert metrics["active_restore_clearance_restoration_attempts_v16"] == 0


def test_v16_clearance_can_enable_the_still_reserved_inverse() -> None:
    before = login()
    interrupted = login(disabled=True, popup=True)
    enabled_but_changed = login(value="other")
    executor = ScriptedExecutor(
        [
            (
                "typed_forward",
                "fill('user', 'michel', False)",
                ActionExecutionV4(interrupted),
            ),
            (
                "typed_compensator",
                "click('cancel0')",
                ActionExecutionV4(enabled_but_changed),
            ),
            (
                "typed_inverse",
                "fill('user', '', False)",
                ActionExecutionV4(before),
            ),
        ]
    )
    runtime = FailClosedTransactionRuntimeV16(
        executor,
        lambda _contract: reservation(remaining=2),
        lambda _contract: active_reservation(remaining=2),
    )
    outcome = runtime.transact(
        before=before,
        contract=editable_contract(before),
        candidate_label="Username",
    )
    assert not outcome.admitted and not outcome.halted
    assert outcome.restoration is not None and outcome.restoration.passed
    assert [role for role, _code in executor.calls] == [
        "typed_forward",
        "typed_compensator",
        "typed_inverse",
    ]
    projection = next(
        event
        for event in runtime.events
        if event["type"] == "interrupt_clearance_projection_v16"
    )
    assert projection["passed"] is False


def test_v16_keeps_compensator_retry_when_the_pair_is_solvent() -> None:
    before = login()
    interrupted = login(disabled=True, popup=True)
    filled = login(value="michel")
    executor = ScriptedExecutor(
        [
            (
                "typed_forward",
                "fill('user', 'michel', False)",
                ActionExecutionV4(interrupted),
            ),
            (
                "typed_compensator",
                "click('cancel0')",
                ActionExecutionV4(before),
            ),
            (
                "typed_retry",
                "fill('user', 'michel', False)",
                ActionExecutionV4(filled),
            ),
        ]
    )
    runtime = FailClosedTransactionRuntimeV16(
        executor,
        lambda _contract: reservation(remaining=3),
        lambda _contract: active_reservation(remaining=2),
    )
    outcome = runtime.transact(
        before=before,
        contract=editable_contract(before),
        candidate_label="Username",
    )
    assert outcome.admitted and not outcome.halted
    assert [role for role, _code in executor.calls] == [
        "typed_forward",
        "typed_compensator",
        "typed_retry",
    ]
    assert not any(
        event.get("type") == "interrupt_clearance_reservation_v16"
        for event in runtime.events
    )


def test_v16_never_clears_an_interrupt_if_one_action_would_borrow_reserve() -> None:
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
                "typed_inverse",
                "fill('user', '', False)",
                ActionExecutionV4(before),
            ),
        ]
    )
    runtime = FailClosedTransactionRuntimeV16(
        executor,
        lambda _contract: reservation(remaining=1),
        lambda _contract: active_reservation(remaining=1),
    )
    outcome = runtime.transact(
        before=before,
        contract=editable_contract(before),
        candidate_label="Username",
    )
    assert not outcome.admitted and not outcome.halted
    assert [role for role, _code in executor.calls] == [
        "typed_forward",
        "typed_inverse",
    ]
    clearance = next(
        event
        for event in runtime.events
        if event["type"] == "interrupt_clearance_reservation_v16"
    )
    assert clearance["allowed"] is False


def active_runtime(
    executor: ScriptedExecutor,
    *,
    remaining: int,
) -> FailClosedTransactionRuntimeV16:
    before = login()
    runtime = FailClosedTransactionRuntimeV16(
        executor,
        lambda _contract: reservation(remaining=3),
        lambda _contract: active_reservation(remaining=remaining),
    )
    admitted = runtime.transact(
        before=before,
        contract=editable_contract(before),
        candidate_label="Username",
    )
    assert admitted.admitted and len(runtime.active) == 1
    return runtime


def test_v16_active_clearance_enables_the_still_reserved_inverse() -> None:
    before = login()
    filled = login(value="michel")
    interrupted = login(value="michel", disabled=True, popup=True)
    enabled_but_changed = login(value="michel")
    executor = ScriptedExecutor(
        [
            (
                "typed_forward",
                "fill('user', 'michel', False)",
                ActionExecutionV4(filled),
            ),
            (
                "typed_restore_compensator",
                "click('cancel0')",
                ActionExecutionV4(enabled_but_changed),
            ),
            (
                "typed_inverse",
                "fill('user', '', False)",
                ActionExecutionV4(before),
            ),
        ]
    )
    runtime = active_runtime(executor, remaining=2)
    runtime._live_public_snapshot_v15 = interrupted
    outcome = runtime.restore_top("test cleanup")
    assert outcome.passed and not runtime.halted and not runtime.active
    assert [role for role, _code in executor.calls] == [
        "typed_forward",
        "typed_restore_compensator",
        "typed_inverse",
    ]
    assert any(
        event.get("type") == "active_restore_clearance_projection_v16"
        and event.get("passed") is False
        for event in runtime.events
    )
    metrics = interrupt_clearance_metrics_v16(SimpleNamespace(runtime=runtime))
    assert metrics["active_restore_clearance_restoration_attempts_v16"] == 1
    assert metrics["active_restore_clearance_restoration_passes_v16"] == 1
    assert metrics["proposal_clearance_restoration_attempts_v16"] == 0
    assert any(
        event.get("type") == "interrupt_clearance_restoration_v16"
        and event.get("phase") == "active_restore"
        and event.get("passed") is True
        for event in runtime.events
    )


def test_v16_active_clearance_can_restore_without_spending_inverse() -> None:
    before = login()
    filled = login(value="michel")
    interrupted = login(value="michel", disabled=True, popup=True)
    executor = ScriptedExecutor(
        [
            (
                "typed_forward",
                "fill('user', 'michel', False)",
                ActionExecutionV4(filled),
            ),
            (
                "typed_restore_compensator",
                "click('cancel0')",
                ActionExecutionV4(before),
            ),
        ]
    )
    runtime = active_runtime(executor, remaining=2)
    runtime._live_public_snapshot_v15 = interrupted
    outcome = runtime.restore_top("test cleanup")
    assert outcome.passed and not runtime.active
    assert [role for role, _code in executor.calls] == [
        "typed_forward",
        "typed_restore_compensator",
    ]
    restoration = next(
        event
        for event in runtime.events
        if event.get("type") == "restoration"
        and event.get("trigger") == "active-restore interrupt clearance v16"
    )
    assert restoration["inverse_skipped"] is True


def test_v16_active_clearance_is_disallowed_when_it_would_borrow_reserve() -> None:
    before = login()
    filled = login(value="michel")
    interrupted = login(value="michel", disabled=True, popup=True)
    executor = ScriptedExecutor(
        [
            (
                "typed_forward",
                "fill('user', 'michel', False)",
                ActionExecutionV4(filled),
            ),
            (
                "typed_inverse",
                "fill('user', '', False)",
                ActionExecutionV4(before),
            ),
        ]
    )
    runtime = active_runtime(executor, remaining=1)
    runtime._live_public_snapshot_v15 = interrupted
    outcome = runtime.restore_top("test cleanup")
    assert outcome.passed
    assert [role for role, _code in executor.calls] == [
        "typed_forward",
        "typed_inverse",
    ]
    reservation_event = next(
        event
        for event in runtime.events
        if event.get("type") == "active_restore_clearance_reservation_v16"
    )
    assert reservation_event["allowed"] is False


def test_v16_active_clearance_reservation_matches_small_integer_boundaries() -> None:
    for remaining in range(8):
        for inverse_reserve in range(1, 7):
            item = active_reservation(
                remaining=remaining,
                reserve=inverse_reserve,
            )
            assert item.allowed is (remaining - 1 >= inverse_reserve)
            if item.allowed:
                assert remaining - 1 - inverse_reserve >= 0


def test_v16_driver_reserves_the_complete_active_stack_exactly_once() -> None:
    contract = editable_contract(login())

    def make_driver(maximum_gui_actions: int) -> FullPactConfirmationDriverV16:
        driver = object.__new__(FullPactConfirmationDriverV16)
        driver.budgets = {"maximum_gui_actions": maximum_gui_actions}
        driver.executor = SimpleNamespace(actions=[object(), object()])
        driver.runtime = SimpleNamespace(
            active=[
                SimpleNamespace(contract=contract),
                SimpleNamespace(contract=contract),
            ]
        )
        driver.trace = []
        return driver

    exact = make_driver(5).active_restore_clearance_reservation_v16(contract)
    assert exact.remaining_gui_actions == 3
    assert exact.clearance_actions == 1
    assert exact.active_inverse_reserve == 2
    assert exact.allowed

    insolvent_driver = make_driver(4)
    insolvent = insolvent_driver.active_restore_clearance_reservation_v16(contract)
    assert insolvent.remaining_gui_actions == 2
    assert insolvent.active_inverse_reserve == 2
    assert not insolvent.allowed
    assert insolvent_driver.trace[-1]["allowed"] is False
