from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

import inversereserve.controllers.confirmation_agents_v7 as confirmation_agents
from inversereserve.controllers.confirmation_agents_v7 import (
    FullPactConfirmationDriverV7,
    RawOpenLoopConfirmationDriverV7,
    TypedNoCertificateConfirmationDriverV7,
)

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


class SuccessfulEnvironment:
    def __init__(self) -> None:
        self.calls = []

    def step(self, code: str):
        self.calls.append(code)
        return (observation(), 1.0, True, False, {"message": "success"})


BUDGETS = {"maximum_gui_actions": 5, "maximum_planner_calls": 5, "maximum_wall_seconds": 30.0}


def model(messages: list[dict[str, str]]) -> dict:
    json.dumps(messages)
    return {
        "cache_key": "key",
        "cache_hit": False,
        "raw_output": '{"decision":"commit","bid":"1"}',
        "input_tokens": 10,
        "generated_tokens": 5,
    }


@pytest.mark.parametrize(
    "driver_class, method_id, expected_planner_calls, expected_certified",
    (
        (FullPactConfirmationDriverV7, "full_pact_v7", 0, 1),
        (RawOpenLoopConfirmationDriverV7, "raw_open_loop", 1, 0),
        (TypedNoCertificateConfirmationDriverV7, "typed_no_certificate", 1, 0),
    ),
)
def test_confirmation_arms_execute_same_public_terminal_action(
    driver_class, method_id: str, expected_planner_calls: int, expected_certified: int
) -> None:
    environment = SuccessfulEnvironment()
    driver = driver_class(
        environment=environment, observation=observation(), budgets=BUDGETS, planner_generate=model
    )
    driver.run()
    result = driver.result()
    assert result["success"] is True
    assert result["terminated"] is True
    assert result["infrastructure_failure"] is False
    assert result["method_failure"] is None
    assert result["metrics"]["gui_actions"] == 1
    assert result["metrics"]["planner_calls"] == expected_planner_calls
    assert result["metrics"]["certified_commits"] == expected_certified
    assert result["metrics"]["wrong_terminal_commits"] == 0
    assert environment.calls == ["click('1')"]
    assert result["actions"][0]["method_received_reward"] is False
    assert result["evaluation_audit"]["reward_or_info_forwarded_to_method"] is False
    assert "episode" not in result
    assert not hasattr(driver, "episode")


def test_full_pact_singleton_certificate_never_calls_model() -> None:

    def forbidden(_messages):
        raise AssertionError("singleton envelope called the model")

    driver = FullPactConfirmationDriverV7(
        environment=SuccessfulEnvironment(),
        observation=observation(),
        budgets=BUDGETS,
        planner_generate=forbidden,
    )
    driver.run()
    assert driver.result()["success"] is True


def test_raw_parse_failure_executes_no_action_and_is_not_infrastructure() -> None:

    def invalid(_messages):
        return {
            "cache_key": "bad",
            "cache_hit": False,
            "raw_output": "not-json",
            "input_tokens": 1,
            "generated_tokens": 1,
        }

    environment = SuccessfulEnvironment()
    driver = RawOpenLoopConfirmationDriverV7(
        environment=environment, observation=observation(), budgets=BUDGETS, planner_generate=invalid
    )
    driver.run()
    result = driver.result()
    assert result["success"] is False
    assert result["metrics"]["planner_parse_failures"] == 1
    assert result["method_failure"].startswith("planner parse failed")
    assert result["infrastructure_failure"] is False
    assert environment.calls == []


def test_planner_overrun_stops_before_any_gui_action(monkeypatch: pytest.MonkeyPatch) -> None:
    moments = iter((0.0, 0.0, 31.0, 31.0))
    monkeypatch.setattr(confirmation_agents.time, "monotonic", lambda: next(moments))
    environment = SuccessfulEnvironment()
    driver = RawOpenLoopConfirmationDriverV7(
        environment=environment, observation=observation(), budgets=BUDGETS, planner_generate=model
    )
    driver.run()
    result = driver.result()
    assert result["method_failure"] == "wall-clock budget exhausted after planner call"
    assert result["metrics"]["planner_calls"] == 1
    assert result["metrics"]["wall_seconds"] == 31.0
    assert environment.calls == []
