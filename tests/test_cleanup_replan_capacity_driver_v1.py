from __future__ import annotations

from types import SimpleNamespace

import pytest

from inversereserve.controllers import cleanup_replan_capacity_driver_v1 as module
from inversereserve.controllers.capacity_reserve_drivers_v18 import StackWideCapacityDriverV18


def driver(active: int) -> tuple[module.DemandCleanupReplanDriverV1, list[dict]]:
    value = module.DemandCleanupReplanDriverV1.__new__(module.DemandCleanupReplanDriverV1)
    value.runtime = SimpleNamespace(
        active=[SimpleNamespace(contract=object()) for _ in range(active)],
        halted=False,
    )
    value.executor = SimpleNamespace(actions=[], done=False)
    value.inverse_reservation_audits = 0
    value.cleanup_replan_attempts = 0
    value.cleanup_replan_passes = 0
    value.cleanup_replan_failures = 0
    value.cleanup_replan_actions = 0
    events: list[dict] = []
    value.audit = events.append
    return value, events


def test_live_transaction_triggers_verified_cleanup_then_replan(monkeypatch) -> None:
    value, events = driver(2)
    monkeypatch.setattr(module, "inverse_action_cost_v8", lambda _contract: 2)

    def cleanup(runtime) -> None:
        runtime.active.clear()
        value.executor.actions.extend([object(), object()])

    value.cleanup_runtime = cleanup
    with pytest.raises(module._ReplanFromRealizedState):
        value.inverse_reserve(SimpleNamespace(bid="candidate"), "transact")

    assert value.inverse_reservation_audits == 1
    assert value.cleanup_replan_attempts == 1
    assert value.cleanup_replan_passes == 1
    assert value.cleanup_replan_failures == 0
    assert value.cleanup_replan_actions == 2
    assert [event["phase"] for event in events] == ["request", "outcome"]
    assert events[0]["registered_active_inverse_cost"] == 4
    assert events[1]["active_obligations_after_cleanup"] == 0
    assert events[1]["replan_from_realized_state"] is True
    assert events[1]["stale_proposal_executed"] is False


def test_failed_cleanup_rejects_without_replan(monkeypatch) -> None:
    value, events = driver(1)
    monkeypatch.setattr(module, "inverse_action_cost_v8", lambda _contract: 3)

    def cleanup(runtime) -> None:
        runtime.halted = True
        value.executor.actions.append(object())

    value.cleanup_runtime = cleanup
    allowed, reserve = value.inverse_reserve(SimpleNamespace(bid="candidate"), "transact")

    assert (allowed, reserve) == (False, 3)
    assert value.cleanup_replan_failures == 1
    assert value.cleanup_replan_passes == 0
    assert events[-1]["cleanup_passed"] is False
    assert events[-1]["replan_from_realized_state"] is False


def test_empty_stack_and_commit_delegate_to_stack_wide(monkeypatch) -> None:
    calls = []

    def parent(self, candidate, decision):
        calls.append((candidate.bid, decision))
        self.inverse_reservation_audits += 1
        return True, 5

    monkeypatch.setattr(StackWideCapacityDriverV18, "inverse_reserve", parent)
    for active, decision in ((0, "transact"), (1, "commit")):
        value, events = driver(active)
        assert value.inverse_reserve(SimpleNamespace(bid="candidate"), decision) == (True, 5)
        assert not events
    assert calls == [("candidate", "transact"), ("candidate", "commit")]


def test_driver_is_stack_wide_and_distinct() -> None:
    assert issubclass(
        module.DemandCleanupReplanDriverV1,
        StackWideCapacityDriverV18,
    )
    assert module.DemandCleanupReplanDriverV1.method_id == "demand_cleanup_replan_v1"
