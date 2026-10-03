from __future__ import annotations

from pathlib import Path
from typing import Any

from inversereserve.studies import inversereserve_exogenous_handoff_v1 as design

ROOT = Path(__file__).resolve().parents[1]


def protocol() -> dict[str, Any]:
    return design.build_protocol(
        scientific_source_commit="a" * 40,
        source_sha256={"source.py": "b" * 64},
        preregistration_path="paper/aaai27/notes/handoff.md",
        preregistration_sha256="c" * 64,
        predecessor={"sealed_predecessors_retained": True},
        repositories={"miniwob": "d" * 40},
        created_utc="2026-07-28T06:00:00Z",
    )


def fake_result(episode: dict[str, Any], *, requested: bool, passed: bool = True) -> dict[str, Any]:
    depth = int(episode["handoff_target_depth"])
    actions_before = 2 if requested else 0
    recovery_actions = depth if requested else 0
    attempts = depth if requested else 0
    restoration_passes = attempts if passed else max(0, attempts - 1)
    active_after = 0 if passed or not requested else 1
    return {
        "episode": episode,
        "success": False,
        "infrastructure_failure": False,
        "active_transactions_at_stop": [] if active_after == 0 else [{"contract": {"kind": "fake"}}],
        "metrics": {
            "gui_actions": actions_before + recovery_actions,
            "typed_transactions": depth if requested else 1,
            "planner_calls": 1,
            "planner_actual_calls": 1,
            "wall_seconds": 1.0,
            "runtime_halted": bool(requested and (not passed)),
            "exogenous_handoff_target_depth_v1": depth,
            "exogenous_handoff_requested_v1": int(requested),
            "exogenous_handoff_active_before_v1": depth if requested else 0,
            "exogenous_handoff_registered_cost_v1": depth if requested else 0,
            "exogenous_handoff_remaining_before_v1": int(episode["maximum_gui_actions"]) - actions_before
            if requested
            else 0,
            "exogenous_handoff_actions_before_v1": actions_before,
            "exogenous_handoff_restoration_attempts_v1": attempts,
            "exogenous_handoff_restoration_passes_v1": restoration_passes,
            "exogenous_handoff_active_after_v1": active_after,
            "exogenous_handoff_passed_v1": int(requested and passed),
        },
    }


def test_protocol_freezes_complete_single_method_handoff_population() -> None:
    value = protocol()
    assert value["status"] == "frozen_before_any_seed_39001_through_39020_reset"
    assert value["fresh_seeds"] == list(range(39001, 39021))
    assert value["expected_episodes"] == 160
    assert value["planner_model"] == design.PLANNER_MODEL
    assert value["primary_question"]["not_a_reserve_scope_comparison"] is True
    assert value["selection_disclosure"]["adaptive_robustness_study_not_independent_confirmation"] is True
    assert value["outcome_based_exclusion_allowed"] is False
    assert value["partial_reexecution_allowed"] is False
    assert value["episode_replay_allowed"] is False


def test_manifest_is_exact_unique_and_counterbalanced() -> None:
    value = protocol()
    rows = design.episode_manifest(value)
    assert len(rows) == len({row["episode_id"] for row in rows}) == 160
    assert {row["handoff_target_depth"] for row in rows} == {1, 2}
    assert design.arm_order_counts(value) == {arm: {0: 40, 1: 40} for arm in design.ARMS}
    assert {
        (row["task"], row["maximum_gui_actions"]) for row in rows if row["method"] == design.DEPTH_ONE
    } == set(design.TASK_BUDGETS.items())


def test_synthetic_complete_population_passes_frozen_gates() -> None:
    value = protocol()
    depth_two_activation_tasks = set(list(design.TASK_BUDGETS)[:2])
    rows = []
    for episode in design.episode_manifest(value):
        requested = episode["method"] == design.DEPTH_ONE or episode["task"] in depth_two_activation_tasks
        rows.append(fake_result(episode, requested=requested))
    analysis = design.analyze_rows(rows, value, all_claims_complete=True)
    assert analysis["handoff_requests"] == 120
    assert analysis["handoff_passes"] == 120
    assert analysis["handoff_failures"] == 0
    assert len(analysis["depth_two_handoff_families"]) == 2
    assert analysis["all_successes_clopper_pearson_95_lower"] > 0.95
    assert all(analysis["checks"].values())
    assert analysis["passed"] is True


def test_failed_recovery_and_missing_row_fail_closed() -> None:
    value = protocol()
    manifest = design.episode_manifest(value)
    rows = [fake_result(episode, requested=True) for episode in manifest]
    rows[0] = fake_result(rows[0]["episode"], requested=True, passed=False)
    failed = design.analyze_rows(rows, value, all_claims_complete=True)
    assert failed["checks"]["every_requested_handoff_passes"] is False
    assert failed["checks"]["zero_requested_runtime_halts"] is False
    assert failed["passed"] is False
    incomplete = design.analyze_rows(rows[:-1], value, all_claims_complete=False)
    assert incomplete["checks"]["complete_exact_grid"] is False
    assert incomplete["passed"] is False
