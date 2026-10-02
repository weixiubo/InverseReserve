"""Small offline environment and exact prerecorded observation replay."""

from __future__ import annotations

import copy
import json
import math
from pathlib import Path
from typing import Any

import numpy as np


def observation_record() -> dict[str, Any]:
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
        "viewport": [100, 100],
        "last_action_error": "",
    }


def decode_observation(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("A replay observation must be an object")
    required = {"goal", "axtree_object", "dom_object", "extra_element_properties", "viewport"}
    if not required.issubset(value):
        raise ValueError(f"Replay observation is missing {sorted(required - value.keys())}")
    size = value["viewport"]
    if (
        not isinstance(size, list)
        or len(size) != 2
        or any(type(v) is not int or not 1 <= v <= 4096 for v in size)
    ):
        raise ValueError("Replay viewport must be [height, width] between 1 and 4096")
    result = copy.deepcopy(value)
    result["screenshot"] = np.zeros((*size, 3), dtype=np.uint8)
    return result


class ReplayEnvironment:
    def __init__(self, record: dict[str, Any]) -> None:
        if set(record) != {"initial", "steps", "planner"} or not isinstance(record["steps"], list):
            raise ValueError("Replay requires initial, steps and planner")
        self.initial = decode_observation(record["initial"])
        self.steps = record["steps"]
        self.planner = record["planner"]
        if not isinstance(self.planner, dict):
            raise ValueError("Replay planner must map message hashes to model response records")
        for step in self.steps:
            if not isinstance(step, dict) or set(step) != {
                "action",
                "observation",
                "reward",
                "terminated",
                "truncated",
                "info",
            }:
                raise ValueError("Replay step schema changed")
            decode_observation(step["observation"])
            if (
                not isinstance(step["action"], str)
                or type(step["reward"]) not in {int, float}
                or not math.isfinite(step["reward"])
            ):
                raise ValueError("Replay action/reward is invalid")
            if (
                type(step["terminated"]) is not bool
                or type(step["truncated"]) is not bool
                or not isinstance(step["info"], dict)
            ):
                raise ValueError("Replay terminal flags/info are invalid")
        self.calls: list[str] = []

    def step(self, code: str) -> tuple[dict[str, Any], float, bool, bool, dict[str, Any]]:
        if len(self.calls) >= len(self.steps):
            raise ValueError("Replay exhausted; no unrecorded action may execute")
        step = self.steps[len(self.calls)]
        if code != step["action"]:
            raise ValueError(f"Replay action diverged at step {len(self.calls)}")
        self.calls.append(code)
        return (
            decode_observation(step["observation"]),
            float(step["reward"]),
            step["terminated"],
            step["truncated"],
            step["info"],
        )

    def generate(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        from inversereserve.controllers.confirmation_agents_v7 import object_sha256

        key = object_sha256(messages)
        response = self.planner.get(key)
        if not isinstance(response, dict) or not isinstance(response.get("raw_output"), str):
            raise ValueError(f"No prerecorded planner response for message hash {key}")
        return {"cache_key": key, "cache_hit": True, "input_tokens": 0, "generated_tokens": 0, **response}


def builtin_record(scenario: str = "commit") -> dict[str, Any]:
    if scenario not in {"commit", "no-effect", "action-error"}:
        raise ValueError("Builtin scenarios: commit, no-effect, action-error")
    observed = observation_record()
    if scenario == "action-error":
        observed["last_action_error"] = "injected action failure"
    return {
        "initial": observation_record(),
        "steps": [
            {
                "action": "click('1')",
                "observation": observed,
                "reward": float(scenario == "commit"),
                "terminated": scenario == "commit",
                "truncated": False,
                "info": {},
            }
        ],
        "planner": {},
    }


def load_replay(path: Path | None, scenario: str) -> ReplayEnvironment:
    record = json.loads(path.read_text(encoding="utf-8")) if path else builtin_record(scenario)
    if not isinstance(record, dict):
        raise ValueError("Replay file must contain an object")
    return ReplayEnvironment(record)
