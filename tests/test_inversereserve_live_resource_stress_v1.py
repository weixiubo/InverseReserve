from __future__ import annotations

import copy
from types import SimpleNamespace

from rcrps.inversereserve_live_resource_stress_v1 import (
    ARMS,
    GUI_ACTION_BUDGETS,
    SEEDS,
    ProposalLocalReserveStressDriverV13,
    StackWideReserveStressDriverV13,
    analyze_rows,
    episode_manifest,
)
from rcrps.transaction_actions_v4 import ContractActionV4
from rcrps.typed_contracts_v4 import TransactionContractV4


def _contract(bid: str) -> TransactionContractV4:
    return TransactionContractV4(
        kind="editable_field_assignment",
        semantic_bid=bid,
        action=ContractActionV4("fill", bid, "new", False),
        inverse_actions=(ContractActionV4("fill", bid, "old", False),),
        expected_value="new",
        prior_value="old",
        projection_kind="editable_field_assignment",
    )


def _driver(cls, *, active: int, budget: int, executed: int):
    driver = object.__new__(cls)
    contract = _contract("proposal")
    driver.runtime = SimpleNamespace(
        active=[
            SimpleNamespace(contract=_contract(f"active{index}"))
            for index in range(active)
        ]
    )
    driver.executor = SimpleNamespace(actions=[None] * executed)
    driver.budgets = {"maximum_gui_actions": budget}
    driver.inverse_reservation_audits = 0
    driver.trace = []
    driver.inventory = lambda: SimpleNamespace(
        contract_by_bid={"proposal": contract}
    )
    driver.audit = lambda event: driver.trace.append(event)
    return driver


def test_only_stack_wide_arm_rejects_jointly_insolvent_proposal() -> None:
    candidate = SimpleNamespace(bid="proposal")
    full = _driver(
        StackWideReserveStressDriverV13,
        active=2,
        budget=4,
        executed=1,
    )
    local = _driver(
        ProposalLocalReserveStressDriverV13,
        active=2,
        budget=4,
        executed=1,
    )
    assert full.inverse_reserve(candidate, "transact") == (False, 3)
    assert local.inverse_reserve(candidate, "transact") == (True, 1)
    assert full.trace[0]["stack_wide_required_inverse_cost"] == 3
    assert local.trace[0]["stack_wide_required_inverse_cost"] == 3


def test_terminal_action_also_preserves_active_stack_reserve() -> None:
    candidate = SimpleNamespace(bid="commit")
    full = _driver(
        StackWideReserveStressDriverV13,
        active=2,
        budget=3,
        executed=1,
    )
    local = _driver(
        ProposalLocalReserveStressDriverV13,
        active=2,
        budget=3,
        executed=1,
    )
    assert full.inverse_reserve(candidate, "commit") == (False, 2)
    assert local.inverse_reserve(candidate, "commit") == (True, 0)


def _protocol() -> dict:
    return {
        "candidate": "InverseReserve-live-resource-stress-v1",
        "status": "sealed_before_any_stress_episode_reset",
        "arms": list(ARMS),
        "task": "choose-date-nodelay",
        "fresh_seeds": list(SEEDS),
        "gui_action_budgets": list(GUI_ACTION_BUDGETS),
        "common_budgets": {
            "maximum_planner_calls": 1,
            "maximum_wall_seconds": 60.0,
        },
        "expected_episodes": len(ARMS) * len(SEEDS) * len(GUI_ACTION_BUDGETS),
        "planner_policy": {"expected_calls": 0, "on_any_call": "fail_the_episode"},
        "confirmation_gates": {
            "minimum_seed_cluster_safety_wins": 1,
            "maximum_one_sided_sign_pvalue": 1.0,
        },
        "source_sha256": {},
        "preregistration": {},
    }


def test_manifest_is_complete_unique_and_counterbalanced() -> None:
    rows = episode_manifest(_protocol())
    assert len(rows) == 160
    assert len({row["episode_id"] for row in rows}) == 160
    assert {
        (row["seed"], row["maximum_gui_actions"])
        for row in rows
    } == set((seed, budget) for seed in SEEDS for budget in GUI_ACTION_BUDGETS)
    assert sum(row["arm_position"] == 0 for row in rows) == 80


def _result(episode: dict, *, full: bool) -> dict:
    if full:
        metrics = {
            "gui_actions": episode["maximum_gui_actions"],
            "planner_calls": 0,
            "inverse_reservation_stops": 1,
            "restoration_attempts": 1,
            "restoration_passes": 1,
            "runtime_halted": False,
        }
        return {
            "episode": episode,
            "success": False,
            "infrastructure_failure": False,
            "metrics": metrics,
            "active_transactions_at_stop": [],
            "trace": [],
        }
    metrics = {
        "gui_actions": episode["maximum_gui_actions"],
        "planner_calls": 0,
        "inverse_reservation_stops": 0,
        "restoration_attempts": 1,
        "restoration_passes": 0,
        "runtime_halted": True,
    }
    return {
        "episode": episode,
        "success": False,
        "infrastructure_failure": False,
        "metrics": metrics,
        "active_transactions_at_stop": [{"bid": "active"}],
        "trace": [
            {
                "reservation_rule": "proposal_local",
                "allowed": True,
                "remaining_after_action": 0,
                "stack_wide_required_inverse_cost": 1,
            }
        ],
    }


def test_analysis_detects_live_safety_separation() -> None:
    protocol = _protocol()
    rows = []
    for episode in episode_manifest(protocol):
        rows.append(
            _result(
                copy.deepcopy(episode),
                full=episode["method"] == ARMS[0],
            )
        )
    analysis = analyze_rows(rows, protocol, all_claims_complete=True)
    assert analysis["passed"] is True
    assert analysis["paired_safety"]["cell_losses"] == 0
    assert analysis["metrics"][ARMS[1]]["unsafe_local_admissions"] == 80
