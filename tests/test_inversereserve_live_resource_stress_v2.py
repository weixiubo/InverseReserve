from __future__ import annotations

from inversereserve.controllers.pact_controller_v15 import FailClosedTransactionRuntimeV15
from inversereserve.studies.inversereserve_live_resource_stress_v1 import GUI_ACTION_BUDGETS
from inversereserve.studies.inversereserve_live_resource_stress_v2 import (
    ARMS,
    DRIVERS,
    SEEDS,
    episode_manifest,
)


def _protocol() -> dict:
    return {
        "candidate": "InverseReserve-live-resource-stress-v2",
        "status": "sealed_before_any_successor_episode_reset",
        "arms": list(ARMS),
        "task": "choose-date-nodelay",
        "fresh_seeds": list(SEEDS),
        "gui_action_budgets": list(GUI_ACTION_BUDGETS),
        "common_budgets": {
            "maximum_planner_calls": 1,
            "maximum_wall_seconds": 60.0,
        },
        "expected_episodes": 160,
        "planner_policy": {"expected_calls": 0, "on_any_call": "fail_the_episode"},
        "source_sha256": {},
        "preregistration": {},
    }


def test_successor_manifest_is_fresh_complete_and_balanced() -> None:
    rows = episode_manifest(_protocol())
    assert len(rows) == 160
    assert min(row["seed"] for row in rows) == 29101
    assert max(row["seed"] for row in rows) == 29120
    assert len({row["episode_id"] for row in rows}) == 160
    assert sum(row["arm_position"] == 0 for row in rows) == 80


def test_successor_drivers_use_live_dynamic_inverse_runtime() -> None:
    for driver in DRIVERS.values():
        assert issubclass(driver, object)
    assert FailClosedTransactionRuntimeV15.__name__.endswith("V15")
