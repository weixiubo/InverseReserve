from __future__ import annotations

from copy import deepcopy
from typing import Any

import pytest

from rcrps import inversereserve_v19_unified_confirmation_v1 as design


def protocol() -> dict[str, Any]:
    return design.build_protocol(
        scientific_source_commit="a" * 40,
        source_sha256={"source.py": "b" * 64},
        predecessor={"development_passed": True},
        repositories={"miniwob": "c" * 40},
        created_utc="2026-07-21T15:30:00Z",
    )


def fake_result(
    episode: dict[str, Any],
    *,
    success: bool,
    reserve_rejection: bool = False,
    goal_consumption: int = 0,
    planner_actual_calls: int = 0,
) -> dict[str, Any]:
    restoration = int(not success)
    local = episode["method"] == design.LOCAL_ABLATION
    safe = episode["method"] == design.SAFE_BASELINE
    return {
        "episode": episode,
        "success": success,
        "infrastructure_failure": False,
        "active_transactions_at_stop": [],
        "metrics": {
            "gui_actions": min(4, episode["maximum_gui_actions"]),
            "typed_transactions": 1,
            "planner_calls": 1,
            "planner_actual_calls": planner_actual_calls,
            "wall_seconds": 1.0,
            "runtime_halted": False,
            "restoration_attempts": restoration,
            "restoration_passes": restoration,
            "interrupt_clearance_restoration_attempts_v16": 0,
            "interrupt_clearance_restoration_passes_v16": 0,
            "proposal_clearance_restoration_attempts_v16": 0,
            "proposal_clearance_restoration_passes_v16": 0,
            "active_restore_clearance_restoration_attempts_v16": 0,
            "active_restore_clearance_restoration_passes_v16": 0,
            "goal_mutation_consumption_passes_v19": goal_consumption,
            "certified_scope_consumption_failures_v19": 0,
            "certified_scope_consumed_transactions_v19": goal_consumption,
            "single_obligation_cap_events": int(safe),
        },
        "trace": [
            {
                "type": "cross_family_reservation_v3",
                "reservation_rule": "proposal_local" if local else "stack_wide",
                "allowed": not reserve_rejection,
                "remaining_after_action": 0,
                "stack_wide_required_inverse_cost": 2,
            }
        ],
    }


def synthetic_passing_rows(value: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for episode in design.episode_manifest(value):
        if episode["method"] == design.FULL_METHOD:
            success = episode["budget_level"] != "tight"
            rows.append(
                fake_result(
                    episode,
                    success=success,
                    reserve_rejection=not success,
                    goal_consumption=int(success),
                    planner_actual_calls=int(episode["episode_index"] == 0),
                )
            )
        elif episode["method"] == design.LOCAL_ABLATION:
            rows.append(fake_result(episode, success=True, goal_consumption=1))
        else:
            success = episode["budget_level"] == "ample"
            rows.append(
                fake_result(
                    episode,
                    success=success,
                    goal_consumption=int(success),
                )
            )
    return rows


def test_protocol_fixes_independent_population_and_inference() -> None:
    value = protocol()
    assert value["status"] == (
        "independent_confirmation_frozen_before_any_35101_through_35120_reset"
    )
    assert value["confirmation_seeds"] == list(range(35101, 35121))
    assert value["expected_episodes"] == 1080
    assert value["preregistration"] == design.PREREGISTRATION
    assert value["primary_analysis"] == {
        "endpoint": "closed_success",
        "paired_unit": "task_horizon_seed_cell",
        "full_method": design.FULL_METHOD,
        "baseline": design.SAFE_BASELINE,
        "test": "one_sided_exact_paired_mcnemar_sign",
        "bootstrap_unit": "seed_cluster_shared_across_18_task_horizon_strata",
        "bootstrap_samples": 50_000,
        "bootstrap_seed": 270_729,
        "alpha": 0.01,
        "multiplicity": "one_primary_efficacy_hypothesis",
    }
    assert value["outcome_based_exclusion_allowed"] is False
    assert value["partial_reexecution_allowed"] is False
    assert value["completed_episode_replay_allowed"] is False


def test_manifest_is_unique_and_balanced() -> None:
    value = protocol()
    rows = design.episode_manifest(value)
    assert len(rows) == len({row["episode_id"] for row in rows}) == 1080
    assert design.arm_order_counts(value) == {
        arm: {0: 120, 1: 120, 2: 120} for arm in design.ARMS
    }


def test_synthetic_confirmation_passes_every_frozen_gate() -> None:
    value = protocol()
    analysis = design.analyze_rows(
        synthetic_passing_rows(value), value, all_claims_complete=True
    )
    assert analysis["metrics"][design.FULL_METHOD]["closed_successes"] == 240
    assert analysis["metrics"][design.SAFE_BASELINE]["closed_successes"] == 120
    assert analysis["primary_comparison"]["paired_episodes"] == 360
    assert analysis["primary_comparison"]["net_paired_successes"] == 120
    assert min(
        analysis["family_closed_successes"][design.FULL_METHOD].values()
    ) == 40
    assert all(analysis["checks"].values())
    assert analysis["passed"] is True


def test_incomplete_and_open_success_fail_closed() -> None:
    value = protocol()
    rows = synthetic_passing_rows(value)
    stack_success = next(
        row
        for row in rows
        if row["episode"]["method"] == design.FULL_METHOD and row["success"]
    )
    stack_success["active_transactions_at_stop"] = [{}]
    analysis = design.analyze_rows(rows, value, all_claims_complete=True)
    assert analysis["checks"]["stack_closes_every_success"] is False
    assert analysis["passed"] is False

    incomplete = design.analyze_rows(
        rows[:-1], value, all_claims_complete=False
    )
    assert incomplete["exact_manifest"] is False
    assert incomplete["primary_comparison"] is None
    assert incomplete["checks"]["complete_exact_grid"] is False
    assert incomplete["passed"] is False


def test_protocol_rejects_threshold_tampering() -> None:
    value = deepcopy(protocol())
    value["confirmation_gates"]["minimum_stack_closed_successes"] = 179
    with pytest.raises(ValueError, match="confirmation gates changed"):
        design.validate_protocol(value)
