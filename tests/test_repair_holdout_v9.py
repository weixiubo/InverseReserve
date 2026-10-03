from __future__ import annotations

import copy
from pathlib import Path

import pytest

from inversereserve.studies.matched_confirmation_v9 import (
    EXPECTED_BUDGETS,
    EXPECTED_GENERATION,
    FULL_METHOD,
    TASKS,
)
from inversereserve.studies.repair_holdout_v9 import (
    EXPECTED_DECISION_RULE,
    EXPECTED_GATES,
    EXPECTED_INFORMATION_BOUNDARY,
    REPAIR_HOLDOUT_SEEDS,
    analyze_holdout_rows,
    episode_manifest,
    validate_protocol_shape,
)

ROOT = Path(__file__).resolve().parents[1]


def protocol() -> dict:
    return {
        "candidate": "PACT-v9-repair-holdout-protocol",
        "status": "sealed_before_repair_holdout",
        "activation": {"fresh_visible_development": {"path": "validation/c452.json", "sha256": "1" * 64}},
        "method": FULL_METHOD,
        "tasks": [{"task_id": task_id, "family_group": family_group} for task_id, family_group in TASKS],
        "repair_holdout_seeds": list(REPAIR_HOLDOUT_SEEDS),
        "expected_episodes": len(TASKS) * len(REPAIR_HOLDOUT_SEEDS),
        "budgets": copy.deepcopy(EXPECTED_BUDGETS),
        "generation": copy.deepcopy(EXPECTED_GENERATION),
        "holdout_gates": copy.deepcopy(EXPECTED_GATES),
        "information_boundary": copy.deepcopy(EXPECTED_INFORMATION_BOUNDARY),
        "decision_rule": copy.deepcopy(EXPECTED_DECISION_RULE),
    }


def episode_row(episode: dict) -> dict:
    runtime_events = []
    if episode["task"] == "use-autocomplete-nodelay":
        runtime_events.append(
            {
                "event_index": 0,
                "type": "postcondition",
                "contract_kind": "autocomplete_query",
                "passed": True,
                "reason": "query value and newly populated suggestion rows appeared",
                "checker_version": "PACT-v9-suggestion-population",
            }
        )
    return {
        "candidate": "PACT-v9-repair-holdout-episode",
        "complete": True,
        "episode": episode,
        "success": True,
        "terminated": True,
        "truncated": False,
        "method_failure": None,
        "infrastructure_failure": False,
        "infrastructure_error": None,
        "method_input": {
            "goal": "public goal",
            "goal_sha256": f"goal-{episode['task']}-{episode['seed']}",
            "controller_arm": FULL_METHOD,
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
        "runtime_events": runtime_events,
        "effect_ledger_v8": [{"key_sha256": f"effect-{episode['episode_id']}", "effective": True}],
        "metrics": {
            "gui_actions": 1,
            "planner_calls": 0,
            "planner_actual_calls": 0,
            "planner_cache_hits": 0,
            "planner_parse_failures": 0,
            "typed_transactions": 1,
            "certified_commits": 1,
            "uncertified_commits": 0,
            "restoration_attempts": 0,
            "restoration_passes": 0,
            "wrong_terminal_commits": 0,
            "terminal_transactions": 0,
            "action_errors": 0,
            "commit_effect_passes": 1,
            "commit_effect_failures": 0,
            "quarantined_commit_keys": 0,
            "resolved_transaction_bids": 1,
            "inverse_reservation_audits": 1,
            "inverse_reservation_stops": 0,
            "runtime_halted": False,
            "wall_seconds": 1.0,
        },
    }


def passing_rows() -> list[dict]:
    return [episode_row(row) for row in episode_manifest(protocol())]


def test_repair_holdout_protocol_and_manifest_are_exact() -> None:
    frozen = protocol()
    validate_protocol_shape(frozen)
    rows = episode_manifest(frozen)
    assert len(rows) == 60
    assert [row["seed"] for row in rows[:: len(TASKS)]] == list(REPAIR_HOLDOUT_SEEDS)
    assert {row["method"] for row in rows} == {FULL_METHOD}
    assert len({row["episode_id"] for row in rows}) == 60


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("repair_holdout_seeds", list(range(27411, 27420))),
        ("expected_episodes", 59),
        ("budgets", {**EXPECTED_BUDGETS, "maximum_gui_actions": 41}),
        ("holdout_gates", {**EXPECTED_GATES, "require_all_60_success": False}),
    ],
)
def test_repair_holdout_protocol_rejects_population_or_gate_weakening(
    field: str, replacement: object
) -> None:
    mutated = protocol()
    mutated[field] = replacement
    with pytest.raises(ValueError):
        validate_protocol_shape(mutated)


def test_repair_holdout_analysis_passes_only_complete_perfect_rows() -> None:
    result = analyze_holdout_rows(passing_rows(), protocol(), all_claims_complete=True)
    assert result["passed"] is True
    assert all(result["checks"].values())
    assert result["metrics"]["success"] == 60
    assert result["metrics"]["minimum_family_successes"] == 10
    assert result["autocomplete_check_count"] == 10


def test_repair_holdout_retains_failures_and_rejects_repeated_effects() -> None:
    rows = passing_rows()
    failed = rows[0]
    failed["success"] = False
    failed["method_failure"] = "failed closed"
    failed["runtime_events"] = [
        {
            "event_index": 0,
            "type": "postcondition",
            "contract_kind": "editable_field_assignment",
            "passed": False,
            "reason": "value mismatch",
        }
    ]
    failed["effect_ledger_v8"] *= 2
    result = analyze_holdout_rows(rows, protocol(), all_claims_complete=True)
    assert result["passed"] is False
    assert result["metrics"]["success"] == 59
    assert result["checks"]["all_60_success"] is False
    assert result["checks"]["zero_method_failures"] is False
    assert result["checks"]["zero_unrecovered_postconditions"] is False
    assert result["checks"]["zero_repeated_effect_keys"] is False


def test_repair_holdout_requires_complete_claims_and_v9_autocomplete_checks() -> None:
    rows = passing_rows()
    for row in rows:
        row["runtime_events"] = []
    result = analyze_holdout_rows(rows, protocol(), all_claims_complete=False)
    assert result["passed"] is False
    assert result["checks"]["all_claims_complete_and_single_open"] is False
    assert result["checks"]["all_observed_autocomplete_checks_are_v9"] is False
    assert result["checks"]["every_autocomplete_episode_has_passing_v9_check"] is False


def test_repair_holdout_requires_v9_check_in_every_autocomplete_episode() -> None:
    rows = passing_rows()
    autocomplete = next((row for row in rows if row["episode"]["task"] == "use-autocomplete-nodelay"))
    autocomplete["runtime_events"] = []
    result = analyze_holdout_rows(rows, protocol(), all_claims_complete=True)
    assert result["passed"] is False
    assert result["checks"]["all_observed_autocomplete_checks_are_v9"] is True
    assert result["checks"]["every_autocomplete_episode_has_passing_v9_check"] is False
