from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from inversereserve.adapters.webarena.webarena_exact_mutation_agent_v1 import ExactMutationTransferAgentV1

ROOT = Path(__file__).resolve().parents[1]
GOAL = 'Change my bio to "hello" in the discussion forum'
BUDGETS = {
    "maximum_gui_actions": 10,
    "maximum_planner_calls": 10,
    "maximum_wall_seconds": 30.0,
    "maximum_navigation_candidates": 64,
}


def observation(nodes: list[dict], *, url: str, goal: str = GOAL) -> dict:
    strings: list[str] = []

    def string_index(value: object) -> int:
        text = str(value)
        if text not in strings:
            strings.append(text)
        return strings.index(text)

    by_bid = {row["bid"]: index for index, row in enumerate(nodes)}
    attributes = []
    parent_indexes = []
    node_names = []
    ax_nodes = []
    for index, row in enumerate(nodes):
        attrs = {"bid": row["bid"], **row.get("attributes", {})}
        attributes.append(
            [value for name, item in attrs.items() for value in (string_index(name), string_index(item))]
        )
        parent = row.get("parent")
        parent_indexes.append(-1 if parent is None else by_bid[parent])
        node_names.append(string_index(row.get("tag", "div")))
        children = [
            f"node-{child_index}"
            for child_index, child in enumerate(nodes)
            if child.get("parent") == row["bid"]
        ]
        ax_nodes.append(
            {
                "nodeId": f"node-{index}",
                "browsergym_id": row["bid"],
                "role": {"value": row.get("role", "generic")},
                "name": {"value": row.get("name", "")},
                "properties": [
                    {"name": name, "value": {"value": value}}
                    for name, value in row.get("properties", {}).items()
                ],
                "childIds": children,
            }
        )
    return {
        "goal": goal,
        "url": url,
        "axtree_object": {"nodes": ax_nodes},
        "dom_object": {
            "strings": strings,
            "documents": [
                {"nodes": {"attributes": attributes, "parentIndex": parent_indexes, "nodeName": node_names}}
            ],
        },
        "extra_element_properties": {
            row["bid"]: {
                "visibility": 1.0 if row.get("visible", True) else 0.0,
                "clickable": bool(row.get("clickable", False)),
                "bbox": [0.0, float(index * 25), 200.0, 20.0],
            }
            for index, row in enumerate(nodes)
        },
        "screenshot": np.zeros((720, 1280, 3), dtype=np.uint8),
        "last_action_error": "",
    }


def navigation_page() -> dict:
    return observation(
        [
            {"bid": "page", "role": "generic", "tag": "main"},
            {
                "bid": "nav",
                "role": "link",
                "name": "Edit profile bio",
                "tag": "a",
                "attributes": {"href": "/settings/profile"},
                "parent": "page",
                "clickable": True,
            },
        ],
        url="http://127.0.0.1:20999/",
    )


def exact_form(*, value: str, saved: bool = False) -> dict:
    nodes = [
        {"bid": "page", "role": "generic", "tag": "main"},
        {"bid": "form", "role": "form", "name": "Profile settings", "tag": "form", "parent": "page"},
        {
            "bid": "field",
            "role": "textbox",
            "name": "Bio",
            "tag": "input",
            "attributes": {"name": "bio", "type": "text"},
            "properties": {"value": value, "readonly": False, "disabled": False},
            "parent": "form",
        },
        {
            "bid": "submit",
            "role": "button",
            "name": "Save changes",
            "tag": "button",
            "attributes": {"type": "submit"},
            "parent": "form",
            "clickable": True,
        },
    ]
    if saved:
        nodes.append(
            {"bid": "saved", "role": "status", "name": "Profile saved", "tag": "div", "parent": "page"}
        )
    return observation(nodes, url="http://127.0.0.1:20999/settings/profile")


class QueueEnvironment:
    def __init__(self, outputs: list[dict]) -> None:
        self.outputs = list(outputs)
        self.calls: list[str] = []

    def step(self, code: str):
        self.calls.append(code)
        if not self.outputs:
            raise AssertionError("unexpected extra environment action")
        return (self.outputs.pop(0), 0.0, False, False, {})


def navigator(bid: str = "nav"):

    def generate(_messages: list[dict[str, str]]) -> dict:
        return {
            "cache_key": "navigation-key",
            "cache_hit": False,
            "raw_output": f'<PACT_NAVIGATION>{{"decision":"click","bid":"{bid}"}}</PACT_NAVIGATION>',
            "input_tokens": 20,
            "generated_tokens": 8,
        }

    return generate


def forbidden_model(_messages):
    raise AssertionError("target-form execution called navigation model")


def test_agent_navigates_then_executes_typed_fill_and_fresh_commit() -> None:
    environment = QueueEnvironment(
        [exact_form(value="prior"), exact_form(value="hello"), exact_form(value="hello", saved=True)]
    )
    agent = ExactMutationTransferAgentV1(
        environment=environment, observation=navigation_page(), budgets=BUDGETS, planner_generate=navigator()
    )
    agent.run()
    result = agent.result()
    assert result["method_commit_effective"] is True
    assert result["typed_target_form_reached"] is True
    assert result["method_failure"] is None
    assert environment.calls == ["click('nav')", "fill('field', 'hello', False)", "click_no_wait('submit')"]
    assert [row["role"] for row in result["actions"]] == ["navigation", "typed_forward", "commit"]
    assert result["metrics"]["planner_calls"] == 1
    assert result["metrics"]["typed_transactions"] == 1
    assert result["metrics"]["certified_commits"] == 1
    assert result["metrics"]["commit_effect_passes"] == 1
    assert result["metrics"]["inverse_reservation_stops"] == 0
    assert result["resolved_exact_transaction_bids"] == ["field"]
    assert result["method_input"]["method_received_task_id"] is False
    assert result["evaluation_audit"]["official_evaluator_called_by_method"] is False


def test_agent_on_target_form_never_calls_navigation_model() -> None:
    environment = QueueEnvironment([exact_form(value="hello"), exact_form(value="hello", saved=True)])
    agent = ExactMutationTransferAgentV1(
        environment=environment,
        observation=exact_form(value="prior"),
        budgets=BUDGETS,
        planner_generate=forbidden_model,
    )
    agent.run()
    result = agent.result()
    assert result["method_commit_effective"] is True
    assert result["metrics"]["planner_calls"] == 0
    assert result["metrics"]["navigation_actions"] == 0
    assert environment.calls == ["fill('field', 'hello', False)", "click_no_wait('submit')"]


def test_navigation_parse_failure_executes_no_action_and_retains_failure() -> None:

    def invalid(_messages):
        return {
            "cache_key": "bad",
            "cache_hit": False,
            "raw_output": "not tagged JSON",
            "input_tokens": 1,
            "generated_tokens": 1,
        }

    environment = QueueEnvironment([])
    agent = ExactMutationTransferAgentV1(
        environment=environment, observation=navigation_page(), budgets=BUDGETS, planner_generate=invalid
    )
    agent.run()
    result = agent.result()
    assert result["method_commit_effective"] is False
    assert result["method_failure"].startswith("navigation planner parse failed")
    assert result["metrics"]["planner_parse_failures"] == 1
    assert environment.calls == []


def test_zero_effect_navigation_is_quarantined_and_not_repeated() -> None:
    same = navigation_page()
    environment = QueueEnvironment([same])
    agent = ExactMutationTransferAgentV1(
        environment=environment, observation=same, budgets=BUDGETS, planner_generate=navigator()
    )
    agent.run()
    result = agent.result()
    assert result["method_commit_effective"] is False
    assert result["method_failure"] == "public navigation exposed no safe current candidate"
    assert result["metrics"]["navigation_actions"] == 1
    assert result["metrics"]["navigation_effect_failures"] == 1
    assert result["metrics"]["quarantined_navigation_keys"] == 1
    assert environment.calls == ["click('nav')"]


def test_inverse_and_commit_reservation_stops_before_typed_forward() -> None:
    budgets = {**BUDGETS, "maximum_gui_actions": 3}
    environment = QueueEnvironment([exact_form(value="prior")])
    agent = ExactMutationTransferAgentV1(
        environment=environment, observation=navigation_page(), budgets=budgets, planner_generate=navigator()
    )
    agent.run()
    result = agent.result()
    assert result["method_commit_effective"] is False
    assert result["method_failure"] == "inverse and commit budget reservation stopped mutation"
    assert result["metrics"]["inverse_reservation_stops"] == 1
    assert result["metrics"]["typed_transactions"] == 0
    assert environment.calls == ["click('nav')"]


def test_result_is_json_serializable_and_contains_no_task_or_evaluator_input() -> None:
    environment = QueueEnvironment([exact_form(value="hello"), exact_form(value="hello", saved=True)])
    agent = ExactMutationTransferAgentV1(
        environment=environment,
        observation=exact_form(value="prior"),
        budgets=BUDGETS,
        planner_generate=forbidden_model,
    )
    agent.run()
    result = agent.result()
    serialized = json.dumps(result, ensure_ascii=False, sort_keys=True)
    assert "task_id" not in result
    assert "official_evaluation" not in result
    assert '"method_received_task_id": false' in serialized
    assert '"method_received_evaluator_fields": false' in serialized
