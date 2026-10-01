from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from rcrps.exogenous_handoff_driver_v1 import (
    EXOGENOUS_HANDOFF_EVENT_V1,
    HANDOFF_DEPTH_ONE_V1,
    HANDOFF_DEPTH_TWO_V1,
    StackWideHandoffDepthOneV1,
    StackWideHandoffDepthTwoV1,
    _ExogenousHandoffMixinV1,
)
from rcrps.capacity_reserve_drivers_v18 import StackWideCapacityDriverV18


def transaction(cost: int = 1) -> Any:
    return SimpleNamespace(
        contract=SimpleNamespace(
            dynamic_inverse_class_token=None,
            inverse_actions=tuple(object() for _ in range(cost)),
        )
    )


class _FakeBase:
    def __init__(self, *, depth: int, restoration_passes: bool = True) -> None:
        self.runtime = SimpleNamespace(
            active=[transaction() for _ in range(depth)],
            halted=False,
        )
        self.executor = SimpleNamespace(actions=[object(), object()])
        self.budgets = {"maximum_gui_actions": 8}
        self.restorations: list[dict[str, Any]] = []
        self.trace: list[dict[str, Any]] = []
        self.method_failure = None
        self.restoration_passes = restoration_passes

    def audit(self, event: dict[str, Any]) -> None:
        self.trace.append(event)

    def within_budget(self) -> bool:
        return True

    def run_policy(self) -> None:
        if self.within_budget():
            return
        for _row in tuple(self.runtime.active):
            self.restorations.append({"passed": self.restoration_passes})
        if self.restoration_passes:
            self.runtime.active.clear()
        else:
            self.runtime.halted = True

    def result(self) -> dict[str, Any]:
        return {"metrics": {}}


class _FakeDepthOne(_ExogenousHandoffMixinV1, _FakeBase):
    target_depth = 1


class _FakeDepthTwo(_ExogenousHandoffMixinV1, _FakeBase):
    target_depth = 2


def test_production_drivers_only_add_the_host_handoff_policy() -> None:
    assert issubclass(StackWideHandoffDepthOneV1, StackWideCapacityDriverV18)
    assert issubclass(StackWideHandoffDepthTwoV1, StackWideCapacityDriverV18)
    assert StackWideHandoffDepthOneV1.method_id == HANDOFF_DEPTH_ONE_V1
    assert StackWideHandoffDepthTwoV1.method_id == HANDOFF_DEPTH_TWO_V1
    assert StackWideHandoffDepthOneV1.target_depth == 1
    assert StackWideHandoffDepthTwoV1.target_depth == 2
    assert StackWideHandoffDepthOneV1.stack_wide is True
    assert StackWideHandoffDepthTwoV1.stack_wide is True


def test_first_eligible_live_prefix_requests_and_verifies_handoff() -> None:
    driver = _FakeDepthTwo(depth=2)
    driver.run_policy()
    metrics = driver.result()["metrics"]
    assert metrics["exogenous_handoff_requested_v1"] == 1
    assert metrics["exogenous_handoff_active_before_v1"] == 2
    assert metrics["exogenous_handoff_registered_cost_v1"] == 2
    assert metrics["exogenous_handoff_remaining_before_v1"] == 6
    assert metrics["exogenous_handoff_restoration_attempts_v1"] == 2
    assert metrics["exogenous_handoff_restoration_passes_v1"] == 2
    assert metrics["exogenous_handoff_active_after_v1"] == 0
    assert metrics["exogenous_handoff_passed_v1"] == 1
    assert [event["phase"] for event in driver.trace] == [
        "request",
        "outcome",
    ]
    assert all(
        event["type"] == EXOGENOUS_HANDOFF_EVENT_V1
        for event in driver.trace
    )


def test_depth_two_does_not_inject_at_a_depth_one_prefix() -> None:
    driver = _FakeDepthTwo(depth=1)
    driver.run_policy()
    metrics = driver.result()["metrics"]
    assert metrics["exogenous_handoff_requested_v1"] == 0
    assert metrics["exogenous_handoff_passed_v1"] == 0
    assert driver.trace == []
    assert len(driver.runtime.active) == 1


def test_failed_recovery_is_retained_as_failed_handoff() -> None:
    driver = _FakeDepthOne(depth=1, restoration_passes=False)
    driver.run_policy()
    metrics = driver.result()["metrics"]
    assert metrics["exogenous_handoff_requested_v1"] == 1
    assert metrics["exogenous_handoff_restoration_attempts_v1"] == 1
    assert metrics["exogenous_handoff_restoration_passes_v1"] == 0
    assert metrics["exogenous_handoff_active_after_v1"] == 1
    assert metrics["exogenous_handoff_passed_v1"] == 0
    assert driver.runtime.halted is True
