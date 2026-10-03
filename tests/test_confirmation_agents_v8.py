from __future__ import annotations

from pathlib import Path

import numpy as np

from inversereserve.controllers.confirmation_agents_v8 import FullPactConfirmationDriverV8

ROOT = Path(__file__).resolve().parents[1]


def observation() -> dict:
    return {
        "goal": 'Click on a "button" widget.',
        "axtree_object": {
            "nodes": [
                {
                    "nodeId": "node-1",
                    "browsergym_id": "1",
                    "role": {"value": "button"},
                    "name": {"value": "Continue"},
                    "properties": [],
                    "childIds": [],
                }
            ]
        },
        "dom_object": {
            "strings": ["button", "bid", "1"],
            "documents": [{"nodes": {"attributes": [[1, 2]], "parentIndex": [-1], "nodeName": [0]}}],
        },
        "extra_element_properties": {
            "1": {"visibility": 1.0, "clickable": True, "bbox": [5.0, 5.0, 80.0, 30.0]}
        },
        "screenshot": np.zeros((100, 100, 3), dtype=np.uint8),
        "last_action_error": "",
    }


class NoEffectEnvironment:
    def __init__(self, *, success: bool = False) -> None:
        self.calls: list[str] = []
        self.success = success

    def step(self, code: str):
        self.calls.append(code)
        return (observation(), float(self.success), self.success, False, {})


BUDGETS = {"maximum_gui_actions": 40, "maximum_planner_calls": 40, "maximum_wall_seconds": 30.0}


def forbidden_model(_messages):
    raise AssertionError("singleton v8 envelope called the model")


def test_v8_quarantines_same_state_commit_after_one_attempt() -> None:
    environment = NoEffectEnvironment()
    driver = FullPactConfirmationDriverV8(
        environment=environment, observation=observation(), budgets=BUDGETS, planner_generate=forbidden_model
    )
    driver.run()
    result = driver.result()
    assert result["success"] is False
    assert result["method_failure"].startswith("PACT-v8 envelope abstained")
    assert result["metrics"]["gui_actions"] == 1
    assert result["metrics"]["certified_commits"] == 1
    assert result["metrics"]["commit_effect_failures"] == 1
    assert result["metrics"]["quarantined_commit_keys"] == 1
    assert result["metrics"]["inverse_reservation_stops"] == 0
    assert environment.calls == ["click('1')"]


def test_v8_terminal_commit_counts_as_effective_without_public_delta() -> None:
    environment = NoEffectEnvironment(success=True)
    driver = FullPactConfirmationDriverV8(
        environment=environment, observation=observation(), budgets=BUDGETS, planner_generate=forbidden_model
    )
    driver.run()
    result = driver.result()
    assert result["success"] is True
    assert result["method_failure"] is None
    assert result["metrics"]["gui_actions"] == 1
    assert result["metrics"]["commit_effect_passes"] == 1
    assert result["metrics"]["commit_effect_failures"] == 0
    assert result["metrics"]["quarantined_commit_keys"] == 0
