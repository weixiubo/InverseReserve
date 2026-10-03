from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

import inversereserve.adapters.webarena.webarena_multifield_agent_v4 as module

ROOT = Path(__file__).resolve().parents[1]


def make_agent(*, budget: int, issued_actions: int, active_costs: list[int]):
    agent = object.__new__(module.MultiFieldInverseReserveAgentV4)
    agent.runtime = SimpleNamespace(active=[SimpleNamespace(contract=cost) for cost in active_costs])
    agent.executor = SimpleNamespace(actions=[object()] * issued_actions)
    agent.budgets = {"maximum_gui_actions": budget}
    agent.minimum_stack_wide_slack = None
    agent.inverse_reservation_audits = 0
    agent.inverse_reservation_stops = 0
    agent.method_failure = None
    agent.trace = []
    agent.audit = agent.trace.append
    return agent


@pytest.mark.parametrize(("budget", "allowed", "slack"), ((3, False, -2), (4, False, -1), (5, True, 0)))
def test_second_field_precharges_one_commit(
    monkeypatch: pytest.MonkeyPatch, budget: int, allowed: bool, slack: int
) -> None:
    monkeypatch.setattr(module, "inverse_action_cost_v8", int)
    agent = make_agent(budget=budget, issued_actions=1, active_costs=[1])
    observed = agent._reserve_forward(binding=SimpleNamespace(bid="title", binding_kind="field"), contract=1)
    assert observed is allowed
    assert agent.trace == [
        {
            "type": "webarena_multifield_commit_margin_v4",
            "reservation_rule": "stack_wide_inverse_plus_one_commit",
            "bid": "title",
            "binding_kind": "field",
            "active_inverse_cost": 1,
            "proposal_inverse_cost": 1,
            "auxiliary_commit_margin": 1,
            "required_after_forward": 3,
            "remaining_after_forward": budget - 2,
            "commit_margin_slack": slack,
            "allowed": allowed,
        }
    ]


@pytest.mark.parametrize("budget", (3, 4, 5))
def test_first_field_remains_admissible(monkeypatch: pytest.MonkeyPatch, budget: int) -> None:
    monkeypatch.setattr(module, "inverse_action_cost_v8", int)
    agent = make_agent(budget=budget, issued_actions=0, active_costs=[])
    assert agent._reserve_forward(binding=SimpleNamespace(bid="body", binding_kind="field"), contract=1)
    assert agent.trace[0]["auxiliary_commit_margin"] == 1


def test_result_declares_auxiliary_margin(monkeypatch: pytest.MonkeyPatch) -> None:
    agent = object.__new__(module.MultiFieldInverseReserveAgentV4)
    monkeypatch.setattr(
        module.MultiFieldInverseReserveAgentV3, "result", lambda _self: {"candidate": "parent", "metrics": {}}
    )
    result = agent.result()
    assert result["auxiliary_commit_margin"] == 1
    assert result["candidate"].endswith("v4-commit-margin-episode")
