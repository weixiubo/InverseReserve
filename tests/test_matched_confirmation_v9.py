from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from rcrps.matched_confirmation_v9 import (  # noqa: E402
    ARMS,
    BASELINES,
    EXPECTED_BUDGETS,
    EXPECTED_DECISION_RULE,
    EXPECTED_GATES,
    EXPECTED_GENERATION,
    EXPECTED_INFORMATION_BOUNDARY,
    EXPECTED_STATISTICS,
    FINAL_CONFIRMATION_SEEDS,
    FULL_METHOD,
    NO_CERTIFICATE_METHOD,
    TASKS,
    analyze_final_rows,
    arm_order_counts,
    episode_manifest,
    validate_protocol_shape,
)


def protocol() -> dict:
    return {
        "candidate": "PACT-v9-final-matched-confirmation-protocol",
        "status": "sealed_before_final_confirmation",
        "activation": {
            "fresh_visible_development": {
                "path": "validation/fresh.json",
                "sha256": "1" * 64,
            },
            "repair_holdout": {
                "path": "validation/holdout.json",
                "sha256": "2" * 64,
            },
        },
        "arms": list(ARMS),
        "full_method": FULL_METHOD,
        "baselines": list(BASELINES),
        "tasks": [
            {"task_id": task_id, "family_group": family_group}
            for task_id, family_group in TASKS
        ],
        "final_confirmation_seeds": list(FINAL_CONFIRMATION_SEEDS),
        "expected_task_seed_cells": len(TASKS) * len(FINAL_CONFIRMATION_SEEDS),
        "expected_episodes": len(TASKS) * len(FINAL_CONFIRMATION_SEEDS) * len(ARMS),
        "budgets": copy.deepcopy(EXPECTED_BUDGETS),
        "generation": copy.deepcopy(EXPECTED_GENERATION),
        "statistics": copy.deepcopy(EXPECTED_STATISTICS),
        "confirmation_gates": copy.deepcopy(EXPECTED_GATES),
        "information_boundary": copy.deepcopy(EXPECTED_INFORMATION_BOUNDARY),
        "decision_rule": copy.deepcopy(EXPECTED_DECISION_RULE),
    }


def episode_row(episode: dict) -> dict:
    cell_index = int(episode["seed_index"]) * len(TASKS) + int(
        episode["task_index"]
    )
    method = episode["method"]
    success = (
        method == FULL_METHOD
        or (method == NO_CERTIFICATE_METHOD and cell_index % 4 != 0)
        or (method == "raw_open_loop_v9_matched" and cell_index % 3 != 0)
    )
    metrics = {
        "gui_actions": 1,
        "planner_calls": 0,
        "planner_actual_calls": 0,
        "planner_cache_hits": 0,
        "planner_parse_failures": 0,
        "typed_transactions": int(method != "raw_open_loop_v9_matched"),
        "certified_commits": int(method == FULL_METHOD),
        "uncertified_commits": int(method != FULL_METHOD),
        "restoration_attempts": 0,
        "restoration_passes": 0,
        "wrong_terminal_commits": 0,
        "terminal_transactions": 0,
        "action_errors": 0,
        "commit_effect_passes": int(method != "raw_open_loop_v9_matched"),
        "commit_effect_failures": 0,
        "quarantined_commit_keys": 0,
        "resolved_transaction_bids": 0,
        "inverse_reservation_audits": int(method != "raw_open_loop_v9_matched"),
        "inverse_reservation_stops": 0,
        "runtime_halted": False,
        "wall_seconds": 1.0,
    }
    return {
        "candidate": "PACT-v9-final-matched-episode",
        "complete": True,
        "episode": episode,
        "success": bool(success),
        "terminated": bool(success),
        "truncated": False,
        "method_failure": None,
        "infrastructure_failure": False,
        "infrastructure_error": None,
        "method_input": {
            "goal": "same public goal",
            "goal_sha256": f"goal-{episode['task']}-{episode['seed']}",
            "controller_arm": method,
            "method_received_task_id": False,
            "method_received_seed": False,
            "method_received_reward": False,
            "method_received_evaluator_fields": False,
        },
        "evaluation_audit": {
            "reward_observed_by_harness": True,
            "evaluator_info_observed_by_harness": True,
            "reward_or_info_forwarded_to_method": False,
            "confirmation_episode": True,
        },
        "trace": [],
        "actions": [],
        "restorations": [],
        "runtime_events": [],
        "metrics": metrics,
    }


def passing_rows() -> list[dict]:
    return [episode_row(row) for row in episode_manifest(protocol())]


def test_final_protocol_shape_and_manifest_are_exact_and_counterbalanced() -> None:
    frozen = protocol()
    validate_protocol_shape(frozen)
    rows = episode_manifest(frozen)
    assert len(rows) == 360
    paired = {}
    for row in rows:
        paired.setdefault((row["task"], row["seed"]), set()).add(row["method"])
    assert len(paired) == 120
    assert all(methods == set(ARMS) for methods in paired.values())
    assert arm_order_counts(frozen) == {
        arm: {0: 40, 1: 40, 2: 40} for arm in ARMS
    }


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("final_confirmation_seeds", list(range(27501, 27520))),
        ("arms", list(reversed(ARMS))),
        ("expected_episodes", 359),
        ("budgets", {**EXPECTED_BUDGETS, "maximum_gui_actions": 41}),
        (
            "confirmation_gates",
            {**EXPECTED_GATES, "minimum_net_paired_wins_per_baseline": 11},
        ),
        (
            "decision_rule",
            {"on_pass": "report successes only", "on_failure": "replace seeds"},
        ),
    ],
)
def test_final_protocol_rejects_population_or_gate_weakening(
    field: str, replacement: object
) -> None:
    mutated = protocol()
    mutated[field] = replacement
    with pytest.raises(ValueError):
        validate_protocol_shape(mutated)


def test_final_analysis_passes_only_a_complete_strong_three_arm_result() -> None:
    result = analyze_final_rows(
        passing_rows(),
        protocol(),
        all_claims_complete=True,
    )
    assert result["passed"] is True
    assert all(result["checks"].values())
    assert result["strongest_other_arm"] == NO_CERTIFICATE_METHOD
    assert result["metrics"][FULL_METHOD]["success"] == 120
    assert result["metrics"][NO_CERTIFICATE_METHOD]["success"] == 90
    assert result["metrics"]["raw_open_loop_v9_matched"]["success"] == 80
    assert all(
        comparison["net_paired_successes"] >= 30
        for comparison in result["statistics"]["comparisons"].values()
    )


def test_verified_postcondition_recovery_is_allowed_but_unrecovered_is_not() -> None:
    rows = passing_rows()
    full = next(row for row in rows if row["episode"]["method"] == FULL_METHOD)
    full["runtime_events"] = [
        {
            "event_index": 0,
            "type": "postcondition",
            "passed": False,
            "contract_kind": "autocomplete_query",
            "reason": "first observation was stale",
        },
        {
            "event_index": 1,
            "type": "restoration",
            "passed": True,
            "trigger": "cleanup",
        },
    ]
    full["metrics"]["restoration_attempts"] = 1
    full["metrics"]["restoration_passes"] = 1
    recovered = analyze_final_rows(rows, protocol(), all_claims_complete=True)
    assert recovered["passed"] is True
    assert recovered["metrics"][FULL_METHOD]["raw_postcondition_failures"] == 1
    assert recovered["metrics"][FULL_METHOD]["unrecovered_postcondition_failures"] == 0

    full["runtime_events"] = full["runtime_events"][:1]
    full["metrics"]["restoration_attempts"] = 0
    full["metrics"]["restoration_passes"] = 0
    unrecovered = analyze_final_rows(rows, protocol(), all_claims_complete=True)
    assert unrecovered["passed"] is False
    assert unrecovered["checks"]["full_zero_unrecovered_postconditions"] is False


def test_final_analysis_rejects_integrity_and_targeted_ablation_failures() -> None:
    rows = passing_rows()
    one_cell = rows[0]["episode"]
    peer = next(
        row
        for row in rows
        if row["episode"]["task"] == one_cell["task"]
        and row["episode"]["seed"] == one_cell["seed"]
        and row["episode"]["method"] != one_cell["method"]
    )
    peer["method_input"]["goal_sha256"] = "different-goal"
    peer["method_input"]["controller_arm"] = FULL_METHOD
    for row in rows:
        if row["episode"]["method"] == NO_CERTIFICATE_METHOD:
            row["metrics"]["uncertified_commits"] = 0
    result = analyze_final_rows(rows, protocol(), all_claims_complete=False)
    assert result["passed"] is False
    assert result["checks"]["all_claims_complete_and_single_open"] is False
    assert result["checks"]["matched_goal_hashes_across_arms"] is False
    assert result["checks"]["controller_arm_matches_manifest"] is False
    assert result["checks"]["no_certificate_executes_targeted_ablation"] is False


def test_infrastructure_failure_is_retained_as_failure_and_fails_integrity_gate() -> None:
    rows = passing_rows()
    failed = rows[0]
    failed["success"] = False
    failed["infrastructure_failure"] = True
    failed["infrastructure_error"] = "reset failed"
    result = analyze_final_rows(rows, protocol(), all_claims_complete=True)
    assert result["passed"] is False
    assert result["checks"]["zero_infrastructure_failures"] is False
    arm = failed["episode"]["method"]
    assert result["metrics"][arm]["infrastructure_failures"] == 1
