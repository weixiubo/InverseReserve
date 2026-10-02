from __future__ import annotations

from pathlib import Path
from typing import Any

from inversereserve.controllers.minimal_cleanup_replan_capacity_driver_v1 import (
    MINIMAL_CLEANUP_POLICY_EVENT_V1,
)
from inversereserve.studies import inversereserve_minimal_cleanup_successor_v1 as design

ROOT = Path(__file__).resolve().parents[1]


def protocol() -> dict[str, Any]:
    return design.build_protocol(
        scientific_source_commit="a" * 40,
        source_sha256={"source.py": "b" * 64},
        preregistration_path="paper/aaai27/notes/minimal.md",
        preregistration_sha256="c" * 64,
        predecessor={"adaptive_history_disclosed": True},
        repositories={"miniwob": "d" * 40},
        created_utc="2026-07-21T00:00:00Z",
    )


def fake_result(
    episode: dict[str, Any], *, success: bool = False, restored: bool = False, policy_bind: bool = False
) -> dict[str, Any]:
    is_policy = episode["method"] == design.SAFE_BASELINE
    clearance = int(restored)
    trace = []
    attempts = passes = 0
    if is_policy and policy_bind:
        attempts = passes = 1
        trace = [
            {
                "type": MINIMAL_CLEANUP_POLICY_EVENT_V1,
                "phase": "request",
                "policy": "restore_one_top_obligation_then_replan",
                "decision": "transact",
                "bid": "candidate",
                "active_obligations_before_proposal": 2,
                "registered_active_inverse_cost": 2,
                "blocked_stack_wide_reserve": 3,
                "stale_proposal_execution_allowed": False,
            },
            {
                "type": MINIMAL_CLEANUP_POLICY_EVENT_V1,
                "phase": "outcome",
                "policy": "restore_one_top_obligation_then_replan",
                "decision": "transact",
                "bid": "candidate",
                "active_obligations_before_proposal": 2,
                "active_obligations_after_cleanup": 1,
                "cleanup_gui_actions": 1,
                "cleanup_passed": True,
                "replan_from_realized_state": True,
                "stale_proposal_executed": False,
            },
        ]
    return {
        "episode": episode,
        "success": success,
        "infrastructure_failure": False,
        "active_transactions_at_stop": [],
        "metrics": {
            "gui_actions": 2,
            "typed_transactions": 2,
            "certified_commits": 0,
            "planner_calls": 1,
            "planner_actual_calls": 1,
            "inverse_reservation_audits": 1,
            "minimal_cleanup_attempts": attempts,
            "minimal_cleanup_passes": passes,
            "minimal_cleanup_failures": 0,
            "minimal_cleanup_actions": attempts,
            "restoration_attempts": 0,
            "restoration_passes": 0,
            "runtime_halted": False,
            "interrupt_clearance_restoration_attempts_v16": clearance,
            "interrupt_clearance_restoration_passes_v16": clearance,
            "proposal_clearance_restoration_attempts_v16": clearance,
            "proposal_clearance_restoration_passes_v16": clearance,
            "active_restore_clearance_restoration_attempts_v16": 0,
            "active_restore_clearance_restoration_passes_v16": 0,
            "interrupt_clearance_reservation_passes_v16": clearance,
            "active_restore_clearance_reservation_passes_v16": 0,
            "inverse_action_error_effect_checks_v17": 0,
            "inverse_action_error_effect_passes_v17": 0,
            "inverse_action_error_effect_failures_v17": 0,
            "certified_scope_consumption_checks_v18": 0,
            "certified_scope_consumption_passes_v18": 0,
            "certified_scope_consumption_failures_v18": 0,
            "certified_scope_consumed_transactions_v18": 0,
            "wall_seconds": 1.0,
        },
        "trace": trace,
    }


def test_protocol_freezes_fresh_grid_and_adaptive_disclosure() -> None:
    value = protocol()
    assert value["status"] == "sealed_before_any_minimal_cleanup_seed_reset"
    assert value["fresh_seeds"] == list(range(32001, 32021))
    assert value["expected_episodes"] == 480
    assert value["sequence_family_size"] == 11
    assert value["runtime_deployment"]["cuda_visible_devices"] == "0"
    assert value["prestart_supersession"] == design.PRESTART_SUPERSESSION
    assert len(value["prestart_supersession"]["protocols"]) == 3
    assert all(
        (
            row["claims_opened"] == row["episodes_opened"] == 0
            for row in value["prestart_supersession"]["protocols"]
        )
    )
    assert value["selection_disclosure"] == design.SELECTION_DISCLOSURE
    assert value["selection_disclosure"]["retrospective_proxy_used"] is False
    assert value["outcome_based_exclusion_allowed"] is False
    assert value["partial_reexecution_allowed"] is False
    assert value["episode_replay_allowed"] is False


def test_manifest_is_exact_unique_and_counterbalanced() -> None:
    value = protocol()
    rows = design.episode_manifest(value)
    assert len(rows) == len({row["episode_id"] for row in rows}) == 480
    assert {row["budget_level"] for row in rows} == set(design.BUDGET_LEVELS)
    assert design.arm_order_counts(value) == {arm: {0: 120, 1: 120} for arm in design.ARMS}


def test_synthetic_complete_population_passes_stronger_policy_gates() -> None:
    value = protocol()
    rows = []
    for episode in design.episode_manifest(value):
        success = episode["budget_level"] in {"medium", "high"}
        rows.append(
            fake_result(
                episode,
                success=success,
                restored=not success,
                policy_bind=episode["method"] == design.SAFE_BASELINE and episode["budget_level"] == "low",
            )
        )
    analysis = design.analyze_rows(rows, value, all_claims_complete=True)
    assert analysis["metrics"][design.FULL_METHOD]["closed_task_successes"] == 160
    safe = analysis["metrics"][design.SAFE_BASELINE]
    assert safe["closed_task_successes"] == 160
    assert safe["minimal_cleanup_preserved_lower_obligation_events"] == 80
    assert analysis["minimal_cleanup_success_families"] == 4
    assert all(analysis["checks"].values())
    assert analysis["passed"] is True


def test_policy_violation_and_missing_row_fail_closed() -> None:
    value = protocol()
    manifest = design.episode_manifest(value)
    incomplete = [fake_result(episode, restored=True) for episode in manifest[:-1]]
    assert design.analyze_rows(incomplete, value, all_claims_complete=False)["passed"] is False
    rows = [
        fake_result(
            episode,
            success=episode["budget_level"] in {"medium", "high"},
            restored=episode["budget_level"] == "low",
            policy_bind=episode["method"] == design.SAFE_BASELINE and episode["budget_level"] == "low",
        )
        for episode in manifest
    ]
    safe_row = next((row for row in rows if row["trace"]))
    safe_row["trace"][1]["active_obligations_after_cleanup"] = 0
    analysis = design.analyze_rows(rows, value, all_claims_complete=True)
    assert analysis["checks"]["minimal_cleanup_policy_holds"] is False
    assert analysis["passed"] is False


def test_stronger_policy_is_stack_wide_and_distinct() -> None:
    safe = design.DRIVERS[design.SAFE_BASELINE]
    full = design.DRIVERS[design.FULL_METHOD]
    assert safe.method_id == "minimal_lifo_cleanup_replan_v1"
    assert issubclass(safe, full)
    assert full.stack_wide is True
