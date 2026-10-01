from __future__ import annotations

from types import SimpleNamespace

import pytest

from rcrps import minimal_cleanup_replan_capacity_driver_v1 as module
from rcrps.capacity_reserve_drivers_v18 import StackWideCapacityDriverV18


def driver(active: int):
    value = module.MinimalCleanupReplanDriverV1.__new__(
        module.MinimalCleanupReplanDriverV1
    )
    value.runtime = SimpleNamespace(
        active=[SimpleNamespace(contract=object()) for _ in range(active)],
        halted=False,
    )
    value.executor = SimpleNamespace(actions=[], done=False)
    value.restorations = []
    value.minimal_cleanup_attempts = 0
    value.minimal_cleanup_passes = 0
    value.minimal_cleanup_failures = 0
    value.minimal_cleanup_actions = 0
    events: list[dict] = []
    value.audit = events.append
    value.inventory = lambda: SimpleNamespace(
        contract_by_bid={"candidate": object()}
    )
    return value, events


def test_blocked_transaction_restores_only_top_then_replans(monkeypatch) -> None:
    value, events = driver(3)
    monkeypatch.setattr(
        StackWideCapacityDriverV18,
        "inverse_reserve",
        lambda _self, _candidate, _decision: (False, 7),
    )
    monkeypatch.setattr(module, "inverse_action_cost_v8", lambda _contract: 2)
    monkeypatch.setattr(
        module,
        "_restoration_record",
        lambda outcome: {"passed": outcome.passed},
    )

    def restore_top(_trigger):
        value.runtime.active.pop()
        value.executor.actions.append(object())
        return SimpleNamespace(passed=True)

    value.runtime.restore_top = restore_top
    with pytest.raises(module._ReplanFromPartiallyRestoredState):
        value.inverse_reserve(SimpleNamespace(bid="candidate"), "transact")

    assert len(value.runtime.active) == 2
    assert value.minimal_cleanup_attempts == 1
    assert value.minimal_cleanup_passes == 1
    assert value.minimal_cleanup_failures == 0
    assert value.minimal_cleanup_actions == 1
    assert value.restorations == [{"passed": True}]
    assert [event["phase"] for event in events] == ["request", "outcome"]
    assert events[0]["registered_active_inverse_cost"] == 6
    assert events[1]["active_obligations_after_cleanup"] == 2
    assert events[1]["stale_proposal_executed"] is False


def test_feasible_transaction_preserves_live_stack(monkeypatch) -> None:
    value, events = driver(2)
    monkeypatch.setattr(
        StackWideCapacityDriverV18,
        "inverse_reserve",
        lambda _self, _candidate, _decision: (True, 5),
    )
    assert value.inverse_reserve(
        SimpleNamespace(bid="candidate"), "transact"
    ) == (True, 5)
    assert len(value.runtime.active) == 2
    assert value.minimal_cleanup_attempts == 0
    assert events == []


def test_failed_top_restoration_rejects_without_replan(monkeypatch) -> None:
    value, events = driver(2)
    monkeypatch.setattr(
        StackWideCapacityDriverV18,
        "inverse_reserve",
        lambda _self, _candidate, _decision: (False, 5),
    )
    monkeypatch.setattr(module, "inverse_action_cost_v8", lambda _contract: 1)
    monkeypatch.setattr(
        module,
        "_restoration_record",
        lambda outcome: {"passed": outcome.passed},
    )
    value.runtime.restore_top = lambda _trigger: SimpleNamespace(passed=False)
    allowed, reserve = value.inverse_reserve(
        SimpleNamespace(bid="candidate"), "transact"
    )
    assert (allowed, reserve) == (False, 2)
    assert value.minimal_cleanup_failures == 1
    assert value.minimal_cleanup_passes == 0
    assert events[-1]["replan_from_realized_state"] is False


def test_driver_is_distinct_stack_wide_policy() -> None:
    assert issubclass(
        module.MinimalCleanupReplanDriverV1,
        StackWideCapacityDriverV18,
    )
    assert (
        module.MinimalCleanupReplanDriverV1.method_id
        == "minimal_lifo_cleanup_replan_v1"
    )
