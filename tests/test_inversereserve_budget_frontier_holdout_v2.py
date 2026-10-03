from __future__ import annotations

from pathlib import Path
from typing import Any

from inversereserve.studies import inversereserve_budget_frontier_holdout_v2 as design

ROOT = Path(__file__).resolve().parents[1]


def protocol() -> dict[str, Any]:
    return design.build_protocol(
        scientific_source_commit="a" * 40,
        source_sha256={"source.py": "b" * 64},
        preregistration_path="paper/aaai27/notes/frontier.md",
        preregistration_sha256="c" * 64,
        predecessor={"adaptive_history_disclosed": True},
        repositories={"miniwob": "d" * 40},
        created_utc="2026-07-20T10:00:00Z",
    )


def fake_result(
    episode: dict[str, Any],
    *,
    success: bool = False,
    active: int = 0,
    restored: bool = False,
    halted: bool = False,
    forward_actions: int = 1,
) -> dict[str, Any]:
    clearance = int(restored)
    return {
        "episode": episode,
        "success": success,
        "infrastructure_failure": False,
        "active_transactions_at_stop": [{} for _ in range(active)],
        "metrics": {
            "gui_actions": max(1, forward_actions),
            "typed_transactions": forward_actions,
            "certified_commits": 0,
            "planner_calls": 1,
            "planner_actual_calls": 1,
            "restoration_attempts": 0,
            "restoration_passes": 0,
            "runtime_halted": halted,
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
        "trace": [],
    }


def test_protocol_freezes_independent_outcomes_and_fresh_grid() -> None:
    value = protocol()
    assert value["status"] == "sealed_before_any_frontier_seed_reset"
    assert value["fresh_seeds"] == list(range(31701, 31721))
    assert value["expected_episodes"] == 720
    assert value["runtime_deployment"]["cuda_visible_devices"] == "0"
    assert value["adaptive_history_disclosed"] is True
    assert value["outcome_based_exclusion_allowed"] is False
    assert value["partial_reexecution_allowed"] is False
    assert value["episode_replay_allowed"] is False
    reporting = value["outcome_definitions"]["reporting_rule"]
    assert "do not use solvent_activity_endpoint" in reporting
    assert "unsafe admission" in reporting


def test_manifest_is_exact_unique_and_counterbalanced() -> None:
    value = protocol()
    rows = design.episode_manifest(value)
    assert len(rows) == len({row["episode_id"] for row in rows}) == 720
    assert {row["budget_level"] for row in rows} == set(design.BUDGET_LEVELS)
    assert design.arm_order_counts(value) == {arm: {0: 80, 1: 80, 2: 80} for arm in design.ARMS}
    assert {row["task"] for row in rows if row["family_group"] == "date_picker_holdout"} == {
        "choose-date-nodelay"
    }


def test_terminal_modes_are_mutually_exclusive_and_external() -> None:
    episode = design.episode_manifest(protocol())[0]
    assert design.terminal_outcome_mode(fake_result(episode, success=True)) == "task_success"
    assert design.terminal_outcome_mode(fake_result(episode, active=1)) == "physical_stranding"
    assert design.terminal_outcome_mode(fake_result(episode, halted=True)) == "runtime_halt_without_stranding"
    assert design.terminal_outcome_mode(fake_result(episode, restored=True)) == "verified_restoration"
    unsafe_success = fake_result(episode, success=True)
    unsafe_success["trace"] = [
        {
            "type": "cross_family_reservation_v3",
            "reservation_rule": "proposal_local",
            "allowed": True,
            "remaining_after_action": 0,
            "stack_wide_required_inverse_cost": 2,
        }
    ]
    assert design.terminal_outcome_mode(unsafe_success) == "task_success"


def test_synthetic_complete_population_passes_all_frozen_gates() -> None:
    value = protocol()
    rows = []
    for episode in design.episode_manifest(value):
        method = episode["method"]
        level = episode["budget_level"]
        if method == design.FULL_METHOD:
            rows.append(
                fake_result(
                    episode, success=level in {"medium", "high"}, restored=level == "low", forward_actions=2
                )
            )
        elif method == design.LOCAL_ABLATION:
            rows.append(
                fake_result(
                    episode,
                    success=level in {"medium", "high"},
                    active=int(level == "low"),
                    forward_actions=2,
                )
            )
        else:
            rows.append(fake_result(episode, restored=True, forward_actions=1))
    analysis = design.analyze_rows(rows, value, all_claims_complete=True)
    assert analysis["exact_manifest"] is True
    assert analysis["stack_high_budget_task_successes"] == 80
    assert analysis["local_physical_stranding_families"] == 4
    assert analysis["paired_stack_vs_safe_task_success"]["seed_cluster_wins"] == 20
    assert all(analysis["checks"].values())
    assert analysis["passed"] is True


def test_safe_baseline_is_acting_depth_one_control() -> None:
    safe = design.DRIVERS[design.SAFE_BASELINE]
    full = design.DRIVERS[design.FULL_METHOD]
    local = design.DRIVERS[design.LOCAL_ABLATION]
    assert safe.method_id == "one_step_then_restore_v18"
    assert issubclass(safe, full)
    assert full.stack_wide is True
    assert local.stack_wide is False


def test_missing_row_and_forward_cap_violation_fail_closed() -> None:
    value = protocol()
    manifest = design.episode_manifest(value)
    incomplete = [fake_result(episode, restored=True) for episode in manifest[:-1]]
    assert design.analyze_rows(incomplete, value, all_claims_complete=False)["passed"] is False
    rows = []
    for episode in manifest:
        restored = episode["method"] != design.FULL_METHOD
        result = fake_result(
            episode,
            success=episode["method"] == design.FULL_METHOD,
            restored=restored,
            forward_actions=2 if episode["method"] == design.SAFE_BASELINE else 1,
        )
        rows.append(result)
    analysis = design.analyze_rows(rows, value, all_claims_complete=True)
    assert analysis["checks"]["safe_baseline_forward_action_cap_holds"] is False
    assert analysis["passed"] is False
