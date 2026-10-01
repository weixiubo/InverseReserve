from __future__ import annotations

from typing import Any

from rcrps import inversereserve_v19_unified_development_v1 as design


def protocol() -> dict[str, Any]:
    return design.build_protocol(
        scientific_source_commit="a" * 40,
        source_sha256={"source.py": "b" * 64},
        predecessor={"retained": True},
        repositories={"miniwob": "c" * 40},
        created_utc="2026-07-21T15:00:00Z",
    )


def fake_result(
    episode: dict[str, Any],
    *,
    success: bool,
    active: int = 0,
    reserve_rejection: bool = False,
    goal_consumption: int = 0,
    planner_actual_calls: int = 0,
) -> dict[str, Any]:
    restoration = int(not success)
    reservation_rule = (
        "proposal_local"
        if episode["method"] == design.LOCAL_ABLATION
        else "stack_wide"
    )
    return {
        "episode": episode,
        "success": success,
        "infrastructure_failure": False,
        "active_transactions_at_stop": [{} for _ in range(active)],
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
        },
        "trace": [
            {
                "type": "cross_family_reservation_v3",
                "reservation_rule": reservation_rule,
                "allowed": not reserve_rejection,
                "remaining_after_action": 0,
                "stack_wide_required_inverse_cost": 2,
            }
        ],
    }


def test_protocol_is_uniform_nonconfirmatory_and_create_once() -> None:
    value = protocol()
    assert value["status"] == (
        "development_only_frozen_before_any_35001_or_35002_reset"
    )
    assert value["development_seeds"] == [35001, 35002]
    assert value["uniform_action_budgets"] == {
        "tight": 8,
        "medium": 16,
        "ample": 32,
    }
    assert all(
        task["budget_levels"] == value["uniform_action_budgets"]
        for task in value["tasks"]
    )
    assert value["purpose"]["claim_status"] == (
        "development_only_no_submission_claim"
    )
    assert value["outcome_based_exclusion_allowed"] is False
    assert value["partial_reexecution_allowed"] is False
    assert value["completed_episode_replay_allowed"] is False


def test_manifest_is_exact_unique_and_counterbalanced() -> None:
    value = protocol()
    rows = design.episode_manifest(value)
    assert len(rows) == len({row["episode_id"] for row in rows}) == 108
    assert set(row["task"] for row in rows) == set(design.TASK_FAMILIES)
    assert set(row["method"] for row in rows) == set(design.ARMS)
    assert design.arm_order_counts(value) == {
        arm: {0: 12, 1: 12, 2: 12} for arm in design.ARMS
    }


def test_synthetic_functional_population_passes_frozen_gates() -> None:
    value = protocol()
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
            rows.append(
                fake_result(
                    episode,
                    success=episode["budget_level"] == "ample",
                    goal_consumption=int(episode["budget_level"] == "ample"),
                )
            )
    analysis = design.analyze_rows(rows, value, all_claims_complete=True)
    assert analysis["metrics"][design.FULL_METHOD]["closed_successes"] == 24
    assert analysis["metrics"][design.FULL_METHOD]["reserve_rejections"] == 12
    assert all(analysis["checks"].values())
    assert analysis["passed"] is True


def test_open_success_and_missing_row_fail_closed() -> None:
    value = protocol()
    manifest = design.episode_manifest(value)
    rows = [fake_result(episode, success=False) for episode in manifest]
    stack = next(
        row
        for row in rows
        if row["episode"]["method"] == design.FULL_METHOD
    )
    stack["success"] = True
    stack["active_transactions_at_stop"] = [{}]
    analysis = design.analyze_rows(rows, value, all_claims_complete=True)
    assert analysis["checks"]["stack_closes_every_success"] is False
    assert analysis["passed"] is False

    incomplete = design.analyze_rows(
        rows[:-1], value, all_claims_complete=False
    )
    assert incomplete["exact_manifest"] is False
    assert incomplete["checks"]["complete_exact_grid"] is False


def test_v19_arms_share_the_same_runtime_family() -> None:
    assert design.DRIVERS[design.FULL_METHOD].method_id == (
        "stack_wide_reserve_v19"
    )
    assert design.DRIVERS[design.LOCAL_ABLATION].method_id == (
        "proposal_local_reserve_v19"
    )
    assert design.DRIVERS[design.SAFE_BASELINE].method_id == (
        "single_active_obligation_v19"
    )
    assert issubclass(
        design.DRIVERS[design.SAFE_BASELINE],
        design.DRIVERS[design.FULL_METHOD],
    )
