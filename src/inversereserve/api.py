"""Stable episode API. The environment and planner are explicit injected boundaries."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Callable, Literal, Protocol

from inversereserve.controllers.capacity_reserve_drivers_v20 import (
    SingleActiveObligationDriverV20,
    StackWideCapacityDriverV20,
    TopCleanupReplanDriverV20,
)
from inversereserve.controllers.capacity_reserve_drivers_v22 import (
    TaskReserveSingleActiveDriverV22,
    TaskReserveTopCleanupDriverV22,
)
from inversereserve.controllers.confirmation_ablation_agents_v13 import (
    RawOpenLoopConfirmationDriverV13,
    TypedNoCertificateConfirmationDriverV13,
)
from inversereserve.controllers.confirmation_agents_v13 import FullPactConfirmationDriverV13

Method = Literal[
    "full",
    "raw",
    "typed",
    "stack-reserve",
    "single-active",
    "top-cleanup",
    "task-reserve-single",
    "task-reserve-cleanup",
]

METHODS = {
    "full",
    "raw",
    "typed",
    "stack-reserve",
    "single-active",
    "top-cleanup",
    "task-reserve-single",
    "task-reserve-cleanup",
}
Planner = Callable[[list[dict[str, str]]], dict[str, Any]]


class Environment(Protocol):
    def step(self, code: str) -> tuple[dict[str, Any], float, bool, bool, dict[str, Any]]: ...


@dataclass(frozen=True)
class Budgets:
    maximum_gui_actions: int = 40
    maximum_planner_calls: int = 40
    maximum_wall_seconds: float = 300.0

    def __post_init__(self) -> None:
        import math

        for name in ("maximum_gui_actions", "maximum_planner_calls"):
            value = getattr(self, name)
            if type(value) is not int or value < 0:
                raise ValueError(f"{name} must be a nonnegative integer")
        if isinstance(self.maximum_wall_seconds, bool) or not isinstance(
            self.maximum_wall_seconds, (int, float)
        ):
            raise ValueError("maximum_wall_seconds must be a finite positive number")
        if not math.isfinite(self.maximum_wall_seconds) or self.maximum_wall_seconds <= 0:
            raise ValueError("maximum_wall_seconds must be a finite positive number")


def run_episode(
    *,
    environment: Environment,
    observation: dict[str, Any],
    planner: Planner,
    budgets: Budgets | None = None,
    method: Method = "full",
) -> dict[str, Any]:
    """Run the maintained matched method, without filesystem or service discovery."""
    drivers = {
        "full": FullPactConfirmationDriverV13,
        "raw": RawOpenLoopConfirmationDriverV13,
        "typed": TypedNoCertificateConfirmationDriverV13,
        "stack-reserve": StackWideCapacityDriverV20,
        "single-active": SingleActiveObligationDriverV20,
        "top-cleanup": TopCleanupReplanDriverV20,
        "task-reserve-single": TaskReserveSingleActiveDriverV22,
        "task-reserve-cleanup": TaskReserveTopCleanupDriverV22,
    }
    if method not in drivers:
        raise ValueError(f"Unknown method: {method}")
    driver = drivers[method](
        environment=environment,
        observation=observation,
        budgets=asdict(budgets or Budgets()),
        planner_generate=planner,
    )
    driver.run()
    result = dict(driver.result())
    result["controller_candidate"] = result["candidate"]
    result["candidate"] = "inversereserve-maintained-episode-v1"
    result["historical_evidence"] = False
    return result
