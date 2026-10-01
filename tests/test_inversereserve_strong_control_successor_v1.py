from __future__ import annotations

from copy import deepcopy
from typing import Any

import pytest

from rcrps import inversereserve_strong_control_successor_v1 as design


def protocol() -> dict[str, Any]:
    return design.build_protocol(
        scientific_source_commit="a" * 40,
        source_sha256={"source.py": "b" * 64},
        predecessor={"sealed_v19_failed": True},
        repositories={"miniwob": "c" * 40},
        created_utc="2026-07-23T04:00:00Z",
    )


def fake_result(
    episode: dict[str, Any],
    *,
    success: bool,
    reserve_rejection: bool = False,
    planner_actual_calls: int = 0,
) -> dict[str, Any]:
    method = episode["method"]
    restoration = int(not success)
    complete = method == design.COMPLETE_CONTROL
    top = method == design.TOP_CONTROL
    policy_active = int(episode["budget_level"] == "tight")
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
            "goal_mutation_consumption_passes_v19": int(success),
            "certified_scope_consumption_failures_v19": 0,
            "complete_cleanup_attempts": int(complete) * policy_active,
            "complete_cleanup_passes": int(complete) * policy_active,
            "complete_cleanup_failures": 0,
            "top_cleanup_attempts": int(top) * policy_active,
            "top_cleanup_passes": int(top) * policy_active,
            "top_cleanup_failures": 0,
            "top_cleanup_preserved_lower_events": int(top) * policy_active,
        },
        "trace": [
            {
                "type": "cross_family_reservation_v3",
                "reservation_rule": "stack_wide",
                "allowed": not reserve_rejection,
                "remaining_after_action": 0,
                "stack_wide_required_inverse_cost": 2,
            }
        ],
    }


def synthetic_valid_rows(value: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for episode in design.episode_manifest(value):
        if episode["method"] == design.FULL_METHOD:
            success = episode["budget_level"] != "tight"
        elif episode["method"] == design.COMPLETE_CONTROL:
            success = episode["budget_level"] == "ample"
        else:
            success = episode["budget_level"] != "tight"
        rows.append(
            fake_result(
                episode,
                success=success,
                reserve_rejection=(
                    episode["method"] == design.FULL_METHOD
                    and episode["budget_level"] == "tight"
                ),
                planner_actual_calls=int(episode["episode_index"] == 0),
            )
        )
    return rows


def test_protocol_discloses_adaptive_status_and_freezes_new_population() -> None:
    value = protocol()
    assert value["status"] == (
        "reviewer_driven_frozen_before_any_36101_through_36120_reset"
    )
    assert value["purpose"]["confirmation_status"] == (
        "not_independent_confirmation_or_v19_replacement"
    )
    assert value["successor_seeds"] == list(range(36101, 36121))
    assert value["expected_episodes"] == 1080
    differences = value["isolated_policy_differences"]
    assert differences[design.COMPLETE_CONTROL] == (
        "restore the complete live LIFO stack and replan before a "
        "requested transaction"
    )
    assert differences[design.TOP_CONTROL].startswith(
        "after a stack-wide capacity rejection"
    )
    assert value["primary_analysis"]["efficacy_gate"] == (
        "none_report_complete_comparison_regardless_of_direction"
    )
    assert value["outcome_based_exclusion_allowed"] is False
    assert value["partial_reexecution_allowed"] is False
    assert value["completed_episode_replay_allowed"] is False


def test_manifest_is_unique_and_policy_order_balanced() -> None:
    value = protocol()
    rows = design.episode_manifest(value)
    assert len(rows) == len({row["episode_id"] for row in rows}) == 1080
    assert design.arm_order_counts(value) == {
        arm: {0: 120, 1: 120, 2: 120} for arm in design.ARMS
    }


def test_synthetic_complete_grid_passes_validity_without_efficacy_gate() -> None:
    value = protocol()
    analysis = design.analyze_rows(
        synthetic_valid_rows(value), value, all_claims_complete=True
    )
    assert analysis["metrics"][design.FULL_METHOD]["closed_successes"] == 240
    assert analysis["metrics"][design.COMPLETE_CONTROL]["closed_successes"] == 120
    assert analysis["metrics"][design.TOP_CONTROL]["closed_successes"] == 240
    assert analysis["comparisons"]["comparisons"][design.COMPLETE_CONTROL]
    assert analysis["comparisons"]["comparisons"][design.TOP_CONTROL]
    assert all(analysis["checks"].values())
    assert analysis["passed"] is True


def test_open_success_and_incomplete_grid_fail_closed() -> None:
    value = protocol()
    rows = synthetic_valid_rows(value)
    stack_success = next(
        row
        for row in rows
        if row["episode"]["method"] == design.FULL_METHOD and row["success"]
    )
    stack_success["active_transactions_at_stop"] = [{}]
    analysis = design.analyze_rows(rows, value, all_claims_complete=True)
    assert analysis["checks"]["all_successes_are_closed"] is False
    assert analysis["passed"] is False

    incomplete = design.analyze_rows(
        rows[:-1], value, all_claims_complete=False
    )
    assert incomplete["exact_manifest"] is False
    assert incomplete["comparisons"] is None
    assert incomplete["checks"]["complete_exact_grid"] is False
    assert incomplete["passed"] is False


def test_protocol_rejects_outcome_gate_and_seed_tampering() -> None:
    value = deepcopy(protocol())
    value["primary_analysis"]["efficacy_gate"] = "stack_must_win"
    with pytest.raises(ValueError, match="primary_analysis changed"):
        design.validate_protocol(value)

    value = deepcopy(protocol())
    value["successor_seeds"][0] = 35101
    with pytest.raises(ValueError, match="seeds changed"):
        design.validate_protocol(value)
