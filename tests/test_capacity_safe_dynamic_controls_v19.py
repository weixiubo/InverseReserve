from __future__ import annotations

from types import SimpleNamespace

import pytest

from rcrps import capacity_safe_dynamic_controls_v19 as module
from rcrps.capacity_reserve_drivers_v19 import StackWideCapacityDriverV19


def complete_driver(active: int):
    value = module.CompleteCleanupReplanDriverV19.__new__(
        module.CompleteCleanupReplanDriverV19
    )
    value.runtime = SimpleNamespace(
        active=[SimpleNamespace(contract=object()) for _ in range(active)],
        halted=False,
    )
    value.executor = SimpleNamespace(actions=[], done=False)
    value.inverse_reservation_audits = 0
    value.complete_cleanup_attempts = 0
    value.complete_cleanup_passes = 0
    value.complete_cleanup_failures = 0
    value.complete_cleanup_actions = 0
    events: list[dict] = []
    value.audit = events.append
    return value, events


def top_driver(active: int):
    value = module.TopCleanupReplanDriverV19.__new__(
        module.TopCleanupReplanDriverV19
    )
    value.runtime = SimpleNamespace(
        active=[SimpleNamespace(contract=object()) for _ in range(active)],
        halted=False,
    )
    value.executor = SimpleNamespace(actions=[], done=False)
    value.restorations = []
    value.top_cleanup_attempts = 0
    value.top_cleanup_passes = 0
    value.top_cleanup_failures = 0
    value.top_cleanup_actions = 0
    value.top_cleanup_preserved_lower_events = 0
    events: list[dict] = []
    value.audit = events.append
    value.inventory = lambda: SimpleNamespace(
        contract_by_bid={"candidate": object()}
    )
    return value, events


def test_complete_control_restores_all_and_replans(monkeypatch) -> None:
    value, events = complete_driver(3)
    monkeypatch.setattr(module, "inverse_action_cost_v8", lambda _contract: 2)

    def cleanup(runtime) -> None:
        runtime.active.clear()
        value.executor.actions.extend([object(), object(), object()])

    value.cleanup_runtime = cleanup
    with pytest.raises(module._ReplanFromCompletelyRestoredState):
        value.inverse_reserve(SimpleNamespace(bid="candidate"), "transact")

    assert value.complete_cleanup_attempts == value.complete_cleanup_passes == 1
    assert value.complete_cleanup_failures == 0
    assert value.complete_cleanup_actions == 3
    assert value.inverse_reservation_audits == 1
    assert events[0]["registered_active_inverse_cost"] == 6
    assert events[-1]["active_obligations_after_cleanup"] == 0
    assert events[-1]["stale_proposal_executed"] is False


def test_complete_control_delegates_without_live_transaction(monkeypatch) -> None:
    calls = []

    def parent(self, candidate, decision):
        calls.append((candidate.bid, decision))
        return True, 4

    monkeypatch.setattr(StackWideCapacityDriverV19, "inverse_reserve", parent)
    for active, decision in ((0, "transact"), (2, "commit")):
        value, events = complete_driver(active)
        assert value.inverse_reserve(
            SimpleNamespace(bid="candidate"), decision
        ) == (True, 4)
        assert events == []
    assert calls == [("candidate", "transact"), ("candidate", "commit")]


def test_top_control_intervenes_only_after_capacity_rejection(monkeypatch) -> None:
    value, events = top_driver(3)
    monkeypatch.setattr(
        StackWideCapacityDriverV19,
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
    with pytest.raises(module._ReplanFromTopRestoredState):
        value.inverse_reserve(SimpleNamespace(bid="candidate"), "transact")

    assert len(value.runtime.active) == 2
    assert value.top_cleanup_attempts == value.top_cleanup_passes == 1
    assert value.top_cleanup_failures == 0
    assert value.top_cleanup_preserved_lower_events == 1
    assert value.restorations == [{"passed": True}]
    assert events[0]["blocked_stack_wide_reserve"] == 7
    assert events[-1]["stale_proposal_executed"] is False


def test_top_control_preserves_feasible_stack(monkeypatch) -> None:
    value, events = top_driver(2)
    monkeypatch.setattr(
        StackWideCapacityDriverV19,
        "inverse_reserve",
        lambda _self, _candidate, _decision: (True, 5),
    )
    assert value.inverse_reserve(
        SimpleNamespace(bid="candidate"), "transact"
    ) == (True, 5)
    assert len(value.runtime.active) == 2
    assert value.top_cleanup_attempts == 0
    assert events == []


def test_controls_use_the_exact_v19_stack_wide_runtime() -> None:
    assert issubclass(
        module.CompleteCleanupReplanDriverV19,
        StackWideCapacityDriverV19,
    )
    assert issubclass(
        module.TopCleanupReplanDriverV19,
        StackWideCapacityDriverV19,
    )
    assert (
        module.CompleteCleanupReplanDriverV19.method_id
        == "complete_cleanup_replan_v19"
    )
    assert module.TopCleanupReplanDriverV19.method_id == "top_cleanup_replan_v19"
