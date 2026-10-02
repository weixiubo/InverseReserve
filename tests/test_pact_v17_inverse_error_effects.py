from __future__ import annotations

from pathlib import Path

from inversereserve.controllers.pact_controller_v4 import ActionExecutionV4
from inversereserve.controllers.pact_controller_v17 import FailClosedTransactionRuntimeV17

from .test_pact_v10_recovery_reservation import ScriptedExecutor, editable_contract, login
from .test_pact_v16_interrupt_clearance import active_reservation, reservation

ROOT = Path(__file__).resolve().parents[1]


def runtime_with_active(executor: ScriptedExecutor) -> FailClosedTransactionRuntimeV17:
    before = login()
    runtime = FailClosedTransactionRuntimeV17(
        executor,
        lambda _contract: reservation(remaining=3),
        lambda _contract: active_reservation(remaining=2),
    )
    admitted = runtime.transact(before=before, contract=editable_contract(before), candidate_label="Username")
    assert admitted.admitted
    return runtime


def test_v17_accepts_inverse_error_only_after_public_effect_is_restored() -> None:
    before = login()
    filled = login(value="michel")
    executor = ScriptedExecutor(
        [
            ("typed_forward", "fill('user', 'michel', False)", ActionExecutionV4(filled)),
            (
                "typed_inverse",
                "fill('user', '', False)",
                ActionExecutionV4(before, action_error="TimeoutError after the effect became public"),
            ),
        ]
    )
    runtime = runtime_with_active(executor)
    outcome = runtime.restore_top("test cleanup")
    assert outcome.passed and (not runtime.halted) and (not runtime.active)
    check = next(
        (event for event in runtime.events if event.get("type") == "inverse_action_error_effect_check_v17")
    )
    assert check["passed"] is True
    assert runtime.completed[-1]["restored"] is True


def test_v17_halts_when_inverse_error_did_not_restore_public_effect() -> None:
    filled = login(value="michel")
    executor = ScriptedExecutor(
        [
            ("typed_forward", "fill('user', 'michel', False)", ActionExecutionV4(filled)),
            (
                "typed_inverse",
                "fill('user', '', False)",
                ActionExecutionV4(filled, action_error="TimeoutError before restoration"),
            ),
        ]
    )
    runtime = runtime_with_active(executor)
    outcome = runtime.restore_top("test cleanup")
    assert not outcome.passed and runtime.halted and (len(runtime.active) == 1)
    check = next(
        (event for event in runtime.events if event.get("type") == "inverse_action_error_effect_check_v17")
    )
    assert check["passed"] is False


def test_v17_keeps_ordinary_verified_inverse_behavior() -> None:
    before = login()
    filled = login(value="michel")
    executor = ScriptedExecutor(
        [
            ("typed_forward", "fill('user', 'michel', False)", ActionExecutionV4(filled)),
            ("typed_inverse", "fill('user', '', False)", ActionExecutionV4(before)),
        ]
    )
    runtime = runtime_with_active(executor)
    outcome = runtime.restore_top("test cleanup")
    assert outcome.passed and (not runtime.halted) and (not runtime.active)
    assert not any((event.get("type") == "inverse_action_error_effect_check_v17" for event in runtime.events))
