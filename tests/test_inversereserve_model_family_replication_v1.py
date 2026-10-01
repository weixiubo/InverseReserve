from __future__ import annotations

import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from rcrps import inversereserve_model_family_replication_v1 as design
from rcrps.single_obligation_capacity_driver_v1 import (
    SINGLE_OBLIGATION_POLICY_EVENT_V1,
)


def protocol() -> dict[str, Any]:
    return design.build_protocol(
        scientific_source_commit="a" * 40,
        source_sha256={"source.py": "b" * 64},
        preregistration_path="paper/aaai27/notes/model-family.md",
        preregistration_sha256="c" * 64,
        predecessor={"adaptive_history_disclosed": True},
        repositories={"miniwob": "d" * 40},
        created_utc="2026-07-20T16:00:00Z",
    )


def fake_result(
    episode: dict[str, Any],
    *,
    success: bool = False,
    restored: bool = False,
    policy_cap: bool = False,
) -> dict[str, Any]:
    is_safe = episode["method"] == design.SAFE_BASELINE
    clearance = int(restored)
    trace = []
    inverse_audits = 0
    if is_safe:
        inverse_audits = 1
        active = int(policy_cap)
        trace = [
            {
                "type": SINGLE_OBLIGATION_POLICY_EVENT_V1,
                "policy": "at_most_one_active_obligation",
                "decision": "transact",
                "bid": "candidate",
                "active_obligations_before_proposal": active,
                "allowed": not policy_cap,
                "delegated_to_stack_wide_reserve": not policy_cap,
                **(
                    {"reason": "second active transaction is forbidden"}
                    if policy_cap
                    else {}
                ),
            }
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
            "inverse_reservation_audits": inverse_audits,
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


def test_protocol_freezes_model_family_grid_model_and_disclosure() -> None:
    value = protocol()
    assert value["status"] == (
        "sealed_before_any_model_family_seed_reset"
    )
    assert value["fresh_seeds"] == list(range(34001, 34021))
    assert value["expected_episodes"] == 480
    assert value["sequence_family_size"] == 13
    assert value["planner_model"] == design.PLANNER_MODEL
    assert value["planner_model"]["model_id"] == (
        "HuggingFaceTB/SmolLM3-3B"
    )
    assert value["selection_disclosure"] == design.SELECTION_DISCLOSURE
    assert value["selection_disclosure"][
        "selected_after_six_blank_context_reviews"
    ] is True
    assert value["selection_disclosure"][
        "replication_is_not_independent_method_confirmation"
    ] is True
    assert value["outcome_based_exclusion_allowed"] is False
    assert value["partial_reexecution_allowed"] is False
    assert value["episode_replay_allowed"] is False


def test_manifest_is_exact_unique_and_counterbalanced() -> None:
    value = protocol()
    rows = design.episode_manifest(value)
    assert len(rows) == len({row["episode_id"] for row in rows}) == 480
    assert {row["budget_level"] for row in rows} == set(
        design.BUDGET_LEVELS
    )
    assert design.arm_order_counts(value) == {
        arm: {0: 120, 1: 120} for arm in design.ARMS
    }
    assert {
        row["task"]
        for row in rows
        if row["family_group"] == "date_picker_holdout"
    } == {"choose-date-nodelay"}


def test_synthetic_complete_population_passes_all_frozen_gates() -> None:
    value = protocol()
    rows = []
    first_two_tasks = set(list(design.TASK_BUDGETS)[:2])
    for episode in design.episode_manifest(value):
        if episode["method"] == design.FULL_METHOD:
            success = episode["budget_level"] in {"medium", "high"}
            rows.append(
                fake_result(
                    episode,
                    success=success,
                    restored=not success,
                )
            )
        else:
            success = (
                episode["task"] in first_two_tasks
                and episode["budget_level"] == "medium"
            )
            rows.append(
                fake_result(
                    episode,
                    success=success,
                    restored=not success,
                    policy_cap=not success,
                )
            )
    analysis = design.analyze_rows(
        rows, value, all_claims_complete=True
    )
    assert analysis["exact_manifest"] is True
    assert analysis["metrics"][design.FULL_METHOD]["task_successes"] == 160
    assert analysis["metrics"][design.SAFE_BASELINE]["task_successes"] == 40
    assert analysis["single_obligation_success_families"] == 2
    assert analysis["paired_stack_vs_safe_closed_success"][
        "seed_cluster_wins"
    ] == 20
    assert analysis["closed_successes"] == {
        design.FULL_METHOD: 160,
        design.SAFE_BASELINE: 40,
    }
    assert all(analysis["checks"].values())
    assert analysis["passed"] is True


def test_policy_violation_and_missing_row_fail_closed() -> None:
    value = protocol()
    manifest = design.episode_manifest(value)
    incomplete = [
        fake_result(
            episode,
            restored=True,
            policy_cap=episode["method"] == design.SAFE_BASELINE,
        )
        for episode in manifest[:-1]
    ]
    assert design.analyze_rows(
        incomplete, value, all_claims_complete=False
    )["passed"] is False

    rows = []
    for episode in manifest:
        result = fake_result(
            episode,
            success=episode["method"] == design.FULL_METHOD,
            restored=episode["method"] == design.SAFE_BASELINE,
            policy_cap=episode["method"] == design.SAFE_BASELINE,
        )
        rows.append(result)
    safe_row = next(
        row
        for row in rows
        if row["episode"]["method"] == design.SAFE_BASELINE
    )
    safe_row["trace"][0]["active_obligations_before_proposal"] = 2
    analysis = design.analyze_rows(rows, value, all_claims_complete=True)
    assert analysis["checks"]["single_obligation_policy_holds"] is False
    assert analysis["passed"] is False


def test_safe_baseline_is_a_stronger_stack_wide_control() -> None:
    safe = design.DRIVERS[design.SAFE_BASELINE]
    full = design.DRIVERS[design.FULL_METHOD]
    assert safe.method_id == "single_active_obligation_v1"
    assert issubclass(safe, full)
    assert full.stack_wide is True
