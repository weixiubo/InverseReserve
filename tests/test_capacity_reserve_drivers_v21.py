from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from inversereserve.controllers.capacity_reserve_drivers_v21 import (
    RUNTIME_VERSION_V21,
    TASK_RESERVE_SOURCE_V21,
    TaskReserveTopCleanupDriverV21,
)

ROOT = Path(__file__).resolve().parents[1]


def _driver(*, budget: int, actions: int, active_costs: tuple[int, ...]):
    driver = TaskReserveTopCleanupDriverV21.__new__(TaskReserveTopCleanupDriverV21)
    proposal = SimpleNamespace(dynamic_inverse_class_token=None, inverse_actions=(object(),))
    active = [
        SimpleNamespace(
            contract=SimpleNamespace(
                dynamic_inverse_class_token=None, inverse_actions=tuple((object() for _ in range(cost)))
            )
        )
        for cost in active_costs
    ]
    driver.runtime = SimpleNamespace(active=active)
    driver.budgets = {"maximum_gui_actions": budget}
    driver.executor = SimpleNamespace(actions=[object()] * actions)
    driver.inventory = lambda: SimpleNamespace(contract_by_bid={"candidate": proposal})
    driver.inverse_reservation_audits = 0
    driver.events = []
    driver.audit = driver.events.append
    return (driver, SimpleNamespace(bid="candidate"))


def test_h1_blocks_an_inverse_only_feasible_transaction() -> None:
    driver, candidate = _driver(budget=2, actions=0, active_costs=())
    allowed, required = driver._capacity_reserve_v20(candidate, "transact")
    assert allowed is False
    assert required == 2
    event = driver.events[-1]
    assert event["reservation_rule"] == "stack_wide"
    assert event["task_reserve_rule"] == "structured_goal_one_call"
    assert event["inverse_only_allowed"] is True
    assert event["applied_inverse_reserve"] == 1
    assert event["applied_task_reserve"] == 1
    assert event["applied_total_reserve"] == 2
    assert event["task_reserve_source"] == TASK_RESERVE_SOURCE_V21
    assert event["runtime_version"] == RUNTIME_VERSION_V21


def test_h1_is_consumed_at_commit() -> None:
    driver, candidate = _driver(budget=3, actions=1, active_costs=(1,))
    allowed, required = driver._capacity_reserve_v20(candidate, "commit")
    assert allowed is True
    assert required == 1
    event = driver.events[-1]
    assert event["applied_inverse_reserve"] == 1
    assert event["applied_task_reserve"] == 0
    assert event["applied_total_reserve"] == 1


def test_complete_stack_and_h1_are_both_counted() -> None:
    driver, candidate = _driver(budget=6, actions=1, active_costs=(1, 2))
    allowed, required = driver._capacity_reserve_v20(candidate, "transact")
    assert allowed is False
    assert required == 5
    event = driver.events[-1]
    assert event["registered_active_inverse_cost"] == 3
    assert event["proposal_inverse_cost"] == 1
    assert event["remaining_after_action"] == 4
