from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from inversereserve.adapters.webarena.webarena_exact_mutation_agent_v2 import ExactMutationTransferAgentV2
from inversereserve.adapters.webarena.webarena_exact_mutation_agent_v11 import ExactMutationTransferAgentV11
from inversereserve.adapters.webarena.webarena_executor_v2 import WebArenaConfirmationExecutorV2
from inversereserve.contracts.transaction_actions_v4 import ContractActionV4
from inversereserve.controllers.pact_controller_v10 import FailClosedTransactionRuntimeV10
from inversereserve.controllers.pact_controller_v11 import FailClosedTransactionRuntimeV11
from inversereserve.observations.typed_observation import SemanticSnapshot

ROOT = Path(__file__).resolve().parents[1]


class _Screen:
    shape = (720, 1280, 3)


class _RewardingEnvironment:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def step(self, code: str):
        self.calls.append(code)
        observation = {"screenshot": _Screen(), "last_action_error": ""}
        return (observation, 1.0, False, False, {"message": "hidden evaluator info"})


def test_reward_and_evaluator_info_cannot_stop_or_enter_method_records(monkeypatch) -> None:
    sentinel = SemanticSnapshot(())
    monkeypatch.setattr(WebArenaConfirmationExecutorV2, "snapshot", property(lambda _self: sentinel))
    environment = _RewardingEnvironment()
    executor = WebArenaConfirmationExecutorV2(
        environment, {"screenshot": _Screen(), "last_action_error": ""}, maximum_gui_actions=2
    )
    first = executor(ContractActionV4("click", "313"), "commit")
    second = executor(ContractActionV4("click", "314"), "navigation")
    assert first.snapshot is sentinel and second.snapshot is sentinel
    assert environment.calls == ["click_no_wait('313')", "click('314')"]
    assert executor.success is False
    assert executor.done is False
    serialized = repr(executor.actions)
    assert "1.0" not in serialized
    assert "hidden evaluator info" not in serialized
    assert all((row["reward_used_for_control"] is False for row in executor.actions))
    assert all((row["evaluator_info_used_for_control"] is False for row in executor.actions))


def test_v2_agent_replaces_the_feedback_coupled_executor() -> None:
    observation = {
        "goal": "change the public field to the requested exact value",
        "screenshot": _Screen(),
        "last_action_error": "",
    }
    budgets = {
        "maximum_gui_actions": 40,
        "maximum_planner_calls": 40,
        "maximum_wall_seconds": 900.0,
        "maximum_navigation_candidates": 64,
    }
    agent = ExactMutationTransferAgentV2(
        environment=_RewardingEnvironment(),
        observation=observation,
        budgets=budgets,
        planner_generate=lambda _messages: {},
    )
    assert isinstance(agent.executor, WebArenaConfirmationExecutorV2)
    assert isinstance(agent.runtime, FailClosedTransactionRuntimeV10)
    assert agent.runtime._executor is agent.executor
    assert agent.method_id == "full_pact_v10_webarena_exact_mutation_v2"


def test_v11_webarena_successor_changes_only_the_transaction_runtime() -> None:
    observation = {
        "goal": "change the public field to the requested exact value",
        "screenshot": _Screen(),
        "last_action_error": "",
    }
    budgets = {
        "maximum_gui_actions": 40,
        "maximum_planner_calls": 40,
        "maximum_wall_seconds": 900.0,
        "maximum_navigation_candidates": 64,
    }
    agent = ExactMutationTransferAgentV11(
        environment=_RewardingEnvironment(),
        observation=observation,
        budgets=budgets,
        planner_generate=lambda _messages: {},
    )
    assert isinstance(agent.executor, WebArenaConfirmationExecutorV2)
    assert isinstance(agent.runtime, FailClosedTransactionRuntimeV11)
    assert agent.runtime._executor is agent.executor
    assert agent.method_id == "full_pact_v11_webarena_exact_mutation_v2"


def test_v2_agent_reserves_compensator_retry_separately_from_inverse() -> None:
    agent = object.__new__(ExactMutationTransferAgentV2)
    agent.budgets = {"maximum_gui_actions": 4}
    agent.executor = SimpleNamespace(actions=[{"role": "typed_forward"}])
    agent.runtime = SimpleNamespace(active=[])
    agent.trace = []
    agent.interrupt_repair_reservation_audits = 0
    agent.interrupt_repair_reservation_fallbacks = 0
    contract = SimpleNamespace(
        maximum_interrupt_repairs=1, dynamic_inverse_class_token=None, inverse_actions=(object(),)
    )
    reservation = agent.interrupt_repair_reservation(contract)
    assert reservation.remaining_gui_actions == 3
    assert reservation.repair_pair_actions == 2
    assert reservation.registered_inverse_reserve == 1
    assert reservation.allowed is True
    assert agent.trace[-1]["type"] == "interrupt_repair_reservation_v10"


def test_v2_pre_forward_guard_reserves_repair_inverse_and_commit(monkeypatch) -> None:
    import inversereserve.adapters.webarena.webarena_exact_mutation_agent_v2 as module

    agent = object.__new__(ExactMutationTransferAgentV2)
    agent.executor = SimpleNamespace(snapshot=object(), actions=[])
    agent.goal = "public goal"
    agent.budgets = {"maximum_gui_actions": 4}
    agent.trace = []
    agent.inverse_reservation_audits = 0
    agent.inverse_reservation_stops = 0
    agent.method_failure = None
    contract = SimpleNamespace(
        maximum_interrupt_repairs=1, dynamic_inverse_class_token=None, inverse_actions=(object(),)
    )
    binding = SimpleNamespace(bid="field", label="Field")
    compilation = SimpleNamespace(goal_contract=SimpleNamespace(payload_bindings=(binding,)))
    inventory = SimpleNamespace(contract_by_bid={"field": contract})
    monkeypatch.setattr(module, "compile_exact_mutation_inventory_v1", lambda *_args, **_kwargs: inventory)
    agent.execute_exact_mutation(compilation)
    assert agent.inverse_reservation_stops == 1
    assert "repair budget reservation stopped" in agent.method_failure
    event = agent.trace[-1]
    assert event["inverse_action_cost"] == 1
    assert event["commit_action_cost"] == 1
    assert event["interrupt_repair_action_cost"] == 2
    assert event["required_after_forward"] == 4
    assert event["remaining_after_forward"] == 3
    assert event["allowed"] is False
