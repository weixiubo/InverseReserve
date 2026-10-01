from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from rcrps import inversereserve_task_reserve_catalog_v1 as design


def _protocol() -> dict:
    survey = json.loads(
        (Path(__file__).parent / "fixtures" / "inversereserve_miniwob_public_input_coverage_survey_v1.json").read_text(encoding="utf-8")
    )
    population = design.derive_population(survey)
    return design.build_protocol(
        scientific_source_commit="0" * 40,
        source_sha256={},
        predecessor={},
        repositories={},
        population=population,
        survey_binding=design.COVERAGE_SURVEY,
        created_utc="2026-07-26T00:00:00Z",
    )


def test_protocol_fixes_complete_catalog_binding_budget_and_h1() -> None:
    protocol = _protocol()
    assert protocol["maximum_gui_actions"] == 5
    assert protocol["planner_task_reserve"] == {
        "units": 1,
        "source": "structured_goal_terminal_intent_one_call",
        "applied_when": "reversible prerequisite transaction",
        "consumed_when": "freshly certified terminal commit",
        "inferred_by_runtime": False,
        "shared_by_both_arms": True,
    }
    assert len(protocol["tasks"]) == len(design.CATALOG_TASKS) == 19
    assert all(row["planner_task_reserve"] == 1 for row in protocol["tasks"])
    assert protocol["outcome_based_exclusion_allowed"] is False
    assert protocol["partial_reexecution_allowed"] is False
    assert protocol["completed_episode_replay_allowed"] is False


def test_manifest_is_complete_unique_fresh_and_counterbalanced() -> None:
    protocol = _protocol()
    rows = design.episode_manifest(protocol)
    assert len(rows) == design.expected_episodes() == 760
    assert len({row["episode_id"] for row in rows}) == 760
    assert {row["seed"] for row in rows} == set(range(37401, 37421))
    assert {row["task"] for row in rows} == set(design.CATALOG_TASKS)
    assert {row["maximum_gui_actions"] for row in rows} == {5}
    assert {row["planner_task_reserve"] for row in rows} == {1}
    assert {row["budget_level"] for row in rows} == {"binding_b5"}
    assert design.arm_order_counts(protocol) == {
        design.FULL_METHOD: {0: 190, 1: 190},
        design.SAFE_BASELINE: {0: 190, 1: 190},
    }


def test_preregistered_gate_inventory_matches_analysis_contract() -> None:
    assert design.VALIDITY_GATES["task_reserve_block_activates"] is True
    assert design.VALIDITY_GATES[
        "every_capacity_transaction_applies_h1"
    ] is True
    assert design.VALIDITY_GATES[
        "minimum_net_paired_closed_successes"
    ] is True
    assert design.PRIMARY_ANALYSIS["minimum_full_closed_successes"] == 150
    assert (
        design.PRIMARY_ANALYSIS["minimum_net_paired_closed_successes"] == 20
    )


def _row(
    episode: dict[str, Any],
    *,
    success: bool,
    activate_interfaces: bool = False,
) -> dict[str, Any]:
    full = episode["method"] == design.FULL_METHOD
    trace = [
        {
            "type": "cross_family_reservation_v3",
            "reservation_rule": "stack_wide",
            "task_reserve_rule": "structured_goal_one_call",
            "decision": "transact",
            "registered_active_inverse_cost": int(full),
            "proposal_inverse_cost": 1,
            "stack_wide_required_inverse_cost": 1 + int(full),
            "applied_inverse_reserve": 1 + int(full),
            "applied_task_reserve": 1,
            "applied_total_reserve": 2 + int(full),
            "task_reserve_source": (
                "structured_goal_terminal_intent_one_call"
            ),
            "remaining_after_action": 4,
            "inverse_only_allowed": True,
            "allowed": True,
            "runtime_version": "PACT-v21-task-reserve",
        },
        {
            "type": "cross_family_reservation_v3",
            "reservation_rule": "stack_wide",
            "task_reserve_rule": "structured_goal_one_call",
            "decision": "commit",
            "registered_active_inverse_cost": int(full),
            "proposal_inverse_cost": 0,
            "stack_wide_required_inverse_cost": int(full),
            "applied_inverse_reserve": int(full),
            "applied_task_reserve": 0,
            "applied_total_reserve": int(full),
            "task_reserve_source": (
                "structured_goal_terminal_intent_one_call"
            ),
            "remaining_after_action": 3,
            "inverse_only_allowed": True,
            "allowed": True,
            "runtime_version": "PACT-v21-task-reserve",
        },
    ]
    if not full:
        trace.append(
            {
                "type": "single_obligation_policy_v20",
                "decision": "transact",
                "allowed": False,
                "delegated_to_stack_wide_reserve": False,
            }
        )
    if activate_interfaces:
        trace.extend(
            [
                {
                    "type": "cross_family_reservation_v3",
                    "reservation_rule": "stack_wide",
                    "task_reserve_rule": "structured_goal_one_call",
                    "decision": "transact",
                    "registered_active_inverse_cost": 0,
                    "proposal_inverse_cost": 1,
                    "stack_wide_required_inverse_cost": 1,
                    "applied_inverse_reserve": 1,
                    "applied_task_reserve": 1,
                    "applied_total_reserve": 2,
                    "task_reserve_source": (
                        "structured_goal_terminal_intent_one_call"
                    ),
                    "remaining_after_action": 1,
                    "inverse_only_allowed": True,
                    "allowed": False,
                    "runtime_version": "PACT-v21-task-reserve",
                },
                {
                    "type": "cross_family_reservation_v3",
                    "reservation_rule": "stack_wide",
                    "task_reserve_rule": "structured_goal_one_call",
                    "decision": "transact",
                    "registered_active_inverse_cost": 2,
                    "proposal_inverse_cost": 1,
                    "stack_wide_required_inverse_cost": 3,
                    "applied_inverse_reserve": 3,
                    "applied_task_reserve": 1,
                    "applied_total_reserve": 4,
                    "task_reserve_source": (
                        "structured_goal_terminal_intent_one_call"
                    ),
                    "remaining_after_action": 2,
                    "inverse_only_allowed": False,
                    "allowed": False,
                    "runtime_version": "PACT-v21-task-reserve",
                },
            ]
        )
    interface_value = int(activate_interfaces)
    return {
        "episode": episode,
        "success": success,
        "infrastructure_failure": False,
        "active_transactions_at_stop": [],
        "metrics": {
            "gui_actions": 4,
            "typed_transactions": 1,
            "planner_calls": 1,
            "planner_actual_calls": interface_value,
            "wall_seconds": 1.0,
            "runtime_halted": False,
            "restoration_attempts": 0,
            "restoration_passes": 0,
            "interrupt_clearance_restoration_attempts_v16": 0,
            "interrupt_clearance_restoration_passes_v16": 0,
            "proposal_clearance_restoration_attempts_v16": 0,
            "proposal_clearance_restoration_passes_v16": 0,
            "active_restore_clearance_restoration_attempts_v16": 0,
            "active_restore_clearance_restoration_passes_v16": 0,
            "certified_scope_consumption_failures_v20": 0,
            "goal_navigation_consumption_passes_v20": interface_value,
            "goal_mutation_consumption_passes_v20": interface_value,
            "goal_terminal_promotions_v20": interface_value,
            "frame_cleanup_attempts_v20": interface_value,
            "frame_cleanup_passes_v20": interface_value,
            "frame_cleanup_failures_v20": 0,
            "top_cleanup_attempts": 0,
            "top_cleanup_passes": 0,
            "top_cleanup_failures": 0,
        },
        "trace": trace,
    }


def _synthetic_valid_rows(protocol: dict[str, Any]) -> list[dict[str, Any]]:
    task_index = {
        task: index for index, task in enumerate(design.CATALOG_TASKS)
    }
    rows = []
    for episode in design.episode_manifest(protocol):
        cutoff = 10 if episode["method"] == design.FULL_METHOD else 8
        rows.append(
            _row(
                episode,
                success=task_index[episode["task"]] < cutoff,
                activate_interfaces=episode["episode_index"] == 0,
            )
        )
    return rows


def test_complete_synthetic_grid_passes_every_frozen_gate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(design, "BOOTSTRAP_SAMPLES", 100)
    protocol = _protocol()
    analysis = design.analyze_rows(
        _synthetic_valid_rows(protocol),
        protocol,
        all_claims_complete=True,
    )
    assert analysis["passed"] is True
    assert all(analysis["checks"].values())
    assert (
        analysis["metrics"][design.FULL_METHOD]["closed_successes"] == 200
    )
    assert (
        analysis["metrics"][design.SAFE_BASELINE]["closed_successes"] == 160
    )
    assert analysis["metrics"][design.FULL_METHOD]["nested_admissions"] > 0
    assert (
        analysis["metrics"][design.SAFE_BASELINE][
            "single_active_cap_rejections"
        ]
        > 0
    )


def test_h_tampering_or_incomplete_grid_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(design, "BOOTSTRAP_SAMPLES", 20)
    protocol = _protocol()
    rows = _synthetic_valid_rows(protocol)
    event = next(
        event
        for row in rows
        for event in row["trace"]
        if event.get("runtime_version") == "PACT-v21-task-reserve"
        and event.get("decision") == "transact"
    )
    event["applied_task_reserve"] = 0
    analysis = design.analyze_rows(
        rows,
        protocol,
        all_claims_complete=True,
    )
    assert analysis["checks"][
        "every_capacity_transaction_applies_h1"
    ] is False
    assert analysis["passed"] is False

    rows = _synthetic_valid_rows(protocol)[:-1]
    analysis = design.analyze_rows(
        rows,
        protocol,
        all_claims_complete=False,
    )
    assert analysis["checks"]["complete_exact_grid"] is False
    assert analysis["passed"] is False
