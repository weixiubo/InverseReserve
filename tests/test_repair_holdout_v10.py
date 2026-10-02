from __future__ import annotations

import copy
from pathlib import Path

import pytest

from inversereserve.studies import repair_holdout_v10 as holdout

ROOT = Path(__file__).resolve().parents[1]


def protocol() -> dict:
    return {
        "candidate": "PACT-v10-repair-holdout-protocol",
        "status": "sealed_before_repair_holdout",
        "activation": {"v10_trace_equivalence": {"path": "validation/c453.json", "sha256": "1" * 64}},
        "method": holdout.FULL_METHOD,
        "tasks": [
            {"task_id": task_id, "family_group": family_group} for task_id, family_group in holdout.TASKS
        ],
        "repair_holdout_seeds": list(holdout.REPAIR_HOLDOUT_SEEDS),
        "expected_episodes": len(holdout.TASKS) * len(holdout.REPAIR_HOLDOUT_SEEDS),
        "budgets": copy.deepcopy(holdout.EXPECTED_BUDGETS),
        "generation": copy.deepcopy(holdout.EXPECTED_GENERATION),
        "holdout_gates": copy.deepcopy(holdout.EXPECTED_GATES),
        "information_boundary": copy.deepcopy(holdout.EXPECTED_INFORMATION_BOUNDARY),
        "decision_rule": copy.deepcopy(holdout.EXPECTED_DECISION_RULE),
    }


def episode_row(episode: dict) -> dict:
    runtime_events = []
    metrics = {
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
        "interrupt_repair_reservation_audits": 0,
        "interrupt_repair_reservation_fallbacks": 0,
        "interrupt_repair_inverse_fallbacks": 0,
        "runtime_halted": False,
        "wall_seconds": 1.0,
    }
    if episode["task"] == "use-autocomplete-nodelay":
        runtime_events.append(
            {
                "type": "postcondition",
                "contract_kind": "autocomplete_query",
                "passed": True,
                "checker_version": "PACT-v9-suggestion-population",
            }
        )
    if episode["task"] == "login-user-popup":
        runtime_events.extend(
            [
                {
                    "type": "interrupt_repair_reservation",
                    "remaining_gui_actions": 3,
                    "repair_pair_actions": 2,
                    "registered_inverse_reserve": 1,
                    "allowed": True,
                },
                {"type": "compensator_grounding", "policy": "attempt"},
            ]
        )
        metrics["interrupt_repair_reservation_audits"] = 1
    return {
        "episode": episode,
        "success": True,
        "terminated": True,
        "truncated": False,
        "method_failure": None,
        "infrastructure_failure": False,
        "method_input": {
            "goal_sha256": f"goal-{episode['task']}-{episode['seed']}",
            "controller_arm": holdout.FULL_METHOD,
            "method_received_task_id": False,
            "method_received_seed": False,
            "method_received_reward": False,
            "method_received_evaluator_fields": False,
        },
        "evaluation_audit": {"reward_or_info_forwarded_to_method": False},
        "trace": [],
        "actions": [],
        "runtime_events": runtime_events,
        "effect_ledger_v8": [{"key_sha256": f"effect-{episode['episode_id']}", "effective": True}],
        "metrics": metrics,
    }


def passing_rows() -> list[dict]:
    return [episode_row(row) for row in holdout.episode_manifest(protocol())]


def test_v10_repair_holdout_is_exact_and_exercises_changed_path() -> None:
    frozen = protocol()
    holdout.validate_protocol_shape(frozen)
    manifest = holdout.episode_manifest(frozen)
    assert len(manifest) == 60
    assert {row["method"] for row in manifest} == {"full_pact_v10"}
    result = holdout.analyze_holdout_rows(passing_rows(), frozen, all_claims_complete=True)
    assert result["passed"] is True
    assert result["metrics"]["interrupt_repair_reservation_audits"] == 10
    assert result["repair_reservation_audit"]["events"] == 10


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("repair_holdout_seeds", list(range(27411, 27420))),
        ("method", "full_pact_v9"),
        (
            "holdout_gates",
            {**holdout.EXPECTED_GATES, "require_zero_interrupt_repair_reservation_fallbacks": False},
        ),
    ],
)
def test_v10_repair_holdout_rejects_population_or_gate_weakening(field: str, replacement: object) -> None:
    mutated = protocol()
    mutated[field] = replacement
    with pytest.raises(ValueError):
        holdout.validate_protocol_shape(mutated)


def test_v10_repair_holdout_rejects_unexercised_or_insolvent_repair() -> None:
    unexercised = passing_rows()
    for row in unexercised:
        row["runtime_events"] = [
            event for event in row["runtime_events"] if event.get("type") == "postcondition"
        ]
        row["metrics"]["interrupt_repair_reservation_audits"] = 0
    result = holdout.analyze_holdout_rows(unexercised, protocol(), all_claims_complete=True)
    assert result["passed"] is False
    assert result["checks"]["repair_reservation_path_observed"] is False
    insolvent = passing_rows()
    repair_row = next((row for row in insolvent if row["episode"]["task"] == "login-user-popup"))
    event = next(
        (
            event
            for event in repair_row["runtime_events"]
            if event.get("type") == "interrupt_repair_reservation"
        )
    )
    event["remaining_gui_actions"] = 2
    event["allowed"] = False
    repair_row["metrics"]["interrupt_repair_reservation_fallbacks"] = 1
    repair_row["metrics"]["interrupt_repair_inverse_fallbacks"] = 1
    next((item for item in repair_row["runtime_events"] if item.get("type") == "compensator_grounding"))[
        "policy"
    ] = "inverse"
    result = holdout.analyze_holdout_rows(insolvent, protocol(), all_claims_complete=True)
    assert result["passed"] is False
    assert result["checks"]["zero_interrupt_repair_reservation_fallbacks"] is False
    assert result["checks"]["repair_reservation_metrics_match_events"] is True
