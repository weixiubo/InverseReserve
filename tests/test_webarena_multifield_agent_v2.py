from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

import inversereserve.adapters.webarena.webarena_multifield_agent_v2 as module

ROOT = Path(__file__).resolve().parents[1]


def make_agent(*, budget: int, issued_actions: int, active_costs: list[int]):
    agent = object.__new__(module.MultiFieldInverseReserveAgentV2)
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


@pytest.mark.parametrize(("budget", "allowed", "slack"), ((3, False, -1), (4, True, 0), (5, True, 1)))
def test_second_field_uses_exact_inverse_only_frontier(
    monkeypatch: pytest.MonkeyPatch, budget: int, allowed: bool, slack: int
) -> None:
    monkeypatch.setattr(module, "inverse_action_cost_v8", int)
    agent = make_agent(budget=budget, issued_actions=1, active_costs=[1])
    observed = agent._reserve_forward(binding=SimpleNamespace(bid="title", binding_kind="field"), contract=1)
    assert observed is allowed
    assert agent.trace == [
        {
            "type": "webarena_multifield_inverse_reservation_v2",
            "reservation_rule": "stack_wide_inverse_only",
            "bid": "title",
            "binding_kind": "field",
            "active_inverse_cost": 1,
            "proposal_inverse_cost": 1,
            "stack_wide_required_after_forward": 2,
            "remaining_after_forward": budget - 2,
            "inverse_reserve_slack": slack,
            "allowed": allowed,
        }
    ]


def test_forward_gate_does_not_precharge_commit_or_optional_repair(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(module, "inverse_action_cost_v8", int)
    agent = make_agent(budget=4, issued_actions=1, active_costs=[1])
    assert agent._reserve_forward(binding=SimpleNamespace(bid="title", binding_kind="field"), contract=1)
    audit = agent.trace[0]
    assert "commit_action_cost" not in audit
    assert "interrupt_repair_action_cost" not in audit
    assert agent.inverse_reservation_stops == 0
    assert agent.method_failure is None
