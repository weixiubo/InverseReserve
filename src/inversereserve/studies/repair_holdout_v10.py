from __future__ import annotations

from collections import Counter
from typing import Any, Iterable

from inversereserve.studies.episode_grid import matches_claim_bound_grid
from inversereserve.studies.matched_confirmation_v9 import _no_action_after_terminal
from inversereserve.studies.matched_confirmation_v10 import EXPECTED_BUDGETS as EXPECTED_BUDGETS
from inversereserve.studies.matched_confirmation_v10 import EXPECTED_GENERATION as EXPECTED_GENERATION
from inversereserve.studies.matched_confirmation_v10 import FULL_METHOD as FULL_METHOD
from inversereserve.studies.matched_confirmation_v10 import TASKS as TASKS
from inversereserve.studies.matched_confirmation_v10 import aggregate_arm, repair_reservation_event_audit
from inversereserve.studies.validation import require

"Result-independent repair holdout for recovery-solvent PACT-v10.\n\nThis module performs no environment reset.  It fixes a 60-episode one-open\npopulation and may be activated only by a passing, source-bound C452-to-v10\ntrace-equivalence artifact.  The final matched confirmation remains unopened.\n"
REPAIR_HOLDOUT_SEEDS = tuple(range(27411, 27421))
EXPECTED_INFORMATION_BOUNDARY = {
    "c452_v9_development_opened": True,
    "v10_trace_equivalence_derived": True,
    "repair_holdout_opened": False,
    "final_confirmation_opened": False,
    "task_seed_reward_and_evaluator_harness_only": True,
    "reward_or_evaluator_forwarded_to_method": False,
    "one_reset_per_task_seed": True,
}
EXPECTED_GATES = {
    "require_all_60_success": True,
    "require_every_family_10_of_10": True,
    "require_zero_infrastructure_failures": True,
    "require_zero_forbidden_method_inputs": True,
    "require_all_budgets_respected": True,
    "require_zero_parser_failures": True,
    "require_zero_action_errors": True,
    "require_zero_runtime_halts": True,
    "require_zero_method_failures": True,
    "require_zero_uncertified_commits": True,
    "require_zero_wrong_terminal_commits": True,
    "require_zero_terminal_transactions": True,
    "require_zero_unrecovered_postconditions": True,
    "require_every_raw_postcondition_failure_has_verified_recovery": True,
    "require_all_attempted_restorations_pass": True,
    "require_zero_repeated_effect_keys_within_episode": True,
    "require_zero_no_effect_commits": True,
    "require_zero_inverse_reservation_stops": True,
    "require_at_least_one_interrupt_repair_reservation_audit": True,
    "require_zero_interrupt_repair_reservation_fallbacks": True,
    "require_repair_reservation_metrics_match_events": True,
    "require_all_observed_autocomplete_checks_are_suggestion_population_v9": True,
    "require_every_autocomplete_episode_has_passing_suggestion_population_v9_check": True,
    "require_model_only_for_multirow_nonabstaining_envelopes": True,
}
EXPECTED_DECISION_RULE = {
    "on_pass": "seal the result-independent final PACT-v10 matched-confirmation protocol without changing the method",
    "on_failure": "stop, preserve the failed PACT-v10 repair-holdout artifact, and keep final confirmation unopened",
}


def validate_protocol_shape(protocol: dict[str, Any]) -> None:
    require(
        not protocol.get("candidate") != "PACT-v10-repair-holdout-protocol",
        "unexpected PACT-v10 repair-holdout candidate",
    )
    require(
        not protocol.get("status") != "sealed_before_repair_holdout",
        "repair holdout must be sealed before any reset",
    )
    require(not protocol.get("method") != FULL_METHOD, "repair-holdout method changed")
    tasks = tuple(
        ((str(row.get("task_id")), str(row.get("family_group"))) for row in protocol.get("tasks", ()))
    )
    require(not tasks != TASKS, "repair-holdout task population changed")
    require(
        not tuple(protocol.get("repair_holdout_seeds", ())) != REPAIR_HOLDOUT_SEEDS,
        "repair-holdout seed partition changed",
    )
    require(
        not int(protocol.get("expected_episodes", -1)) != len(TASKS) * len(REPAIR_HOLDOUT_SEEDS),
        "repair-holdout episode count changed",
    )
    require(not protocol.get("budgets") != EXPECTED_BUDGETS, "repair-holdout budgets changed")
    require(
        not protocol.get("generation") != EXPECTED_GENERATION, "repair-holdout generation settings changed"
    )
    require(not protocol.get("holdout_gates") != EXPECTED_GATES, "repair-holdout gates changed")
    require(
        not protocol.get("information_boundary") != EXPECTED_INFORMATION_BOUNDARY,
        "repair-holdout information boundary changed",
    )
    require(
        not set(protocol.get("activation", {})) != {"v10_trace_equivalence"},
        "repair holdout must bind exactly one passing v10-equivalence artifact",
    )
    require(
        not set(protocol["activation"]["v10_trace_equivalence"]) != {"path", "sha256"},
        "repair-holdout v10-equivalence reference changed",
    )
    require(
        not protocol.get("decision_rule") != EXPECTED_DECISION_RULE, "repair-holdout decision rule changed"
    )


def episode_manifest(protocol: dict[str, Any]) -> list[dict[str, Any]]:
    validate_protocol_shape(protocol)
    rows = []
    for seed_index, seed in enumerate(protocol["repair_holdout_seeds"]):
        for task_index, task in enumerate(protocol["tasks"]):
            task_id = str(task["task_id"])
            rows.append(
                {
                    "episode_index": len(rows),
                    "task_index": task_index,
                    "seed_index": seed_index,
                    "arm_position": 0,
                    "task": task_id,
                    "family_group": str(task["family_group"]),
                    "seed": int(seed),
                    "method": FULL_METHOD,
                    "episode_id": f"{task_id}__seed{int(seed)}__{FULL_METHOD}",
                }
            )
    if len(rows) != int(protocol["expected_episodes"]):
        raise ValueError("repair-holdout manifest count changed")
    if len({row["episode_id"] for row in rows}) != len(rows):
        raise ValueError("repair-holdout manifest contains duplicates")
    return rows


def _metric(row: dict[str, Any], name: str) -> int:
    return int(row.get("metrics", {}).get(name, 0))


def analyze_holdout_rows(
    rows: Iterable[dict[str, Any]], protocol: dict[str, Any], *, all_claims_complete: bool
) -> dict[str, Any]:
    validate_protocol_shape(protocol)
    rows = tuple(rows)
    manifest = episode_manifest(protocol)
    manifest_exact = matches_claim_bound_grid(rows, manifest)
    metrics = aggregate_arm(rows, protocol)
    repair_audit = repair_reservation_event_audit(rows)
    repeated_effect_keys = {}
    for row in rows:
        counts = Counter((record["key_sha256"] for record in row.get("effect_ledger_v8", [])))
        repeated = {key: count for key, count in sorted(counts.items()) if count > 1}
        if repeated:
            repeated_effect_keys[row["episode"]["episode_id"]] = repeated
    autocomplete_checks = [
        (row["episode"]["episode_id"], event)
        for row in rows
        for event in row.get("runtime_events", [])
        if event.get("type") == "postcondition" and event.get("contract_kind") == "autocomplete_query"
    ]
    expected_per_family = len(REPAIR_HOLDOUT_SEEDS)
    expected_autocomplete_ids = {
        row["episode_id"] for row in manifest if row["task"] == "use-autocomplete-nodelay"
    }
    autocomplete_by_episode = {
        episode_id: [event for observed_id, event in autocomplete_checks if observed_id == episode_id]
        for episode_id in expected_autocomplete_ids
    }
    checks = _holdout_rows_confirmation_checks(
        all_claims_complete=all_claims_complete,
        autocomplete_by_episode=autocomplete_by_episode,
        autocomplete_checks=autocomplete_checks,
        expected_autocomplete_ids=expected_autocomplete_ids,
        expected_per_family=expected_per_family,
        manifest_exact=manifest_exact,
        metrics=metrics,
        protocol=protocol,
        repair_audit=repair_audit,
        repeated_effect_keys=repeated_effect_keys,
        rows=rows,
    )
    return {
        "metrics": metrics,
        "repair_reservation_audit": repair_audit,
        "repeated_effect_keys": repeated_effect_keys,
        "autocomplete_check_count": len(autocomplete_checks),
        "checks": checks,
        "passed": all(checks.values()),
    }


def _holdout_rows_confirmation_checks(
    *,
    all_claims_complete: bool,
    autocomplete_by_episode: Any,
    autocomplete_checks: Any,
    expected_autocomplete_ids: Any,
    expected_per_family: Any,
    manifest_exact: Any,
    metrics: Any,
    protocol: Any,
    repair_audit: Any,
    repeated_effect_keys: Any,
    rows: tuple[dict[str, Any], ...],
) -> dict[str, bool]:
    """Apply the registered decision gates to computed outcomes."""
    return {
        "complete_one_open_manifest": manifest_exact,
        "all_claims_complete_and_single_open": bool(all_claims_complete),
        "final_confirmation_remains_unopened": protocol["information_boundary"]["final_confirmation_opened"]
        is False,
        "zero_infrastructure_failures": metrics["infrastructure_failures"] == 0,
        "zero_forbidden_method_inputs": all(
            (
                row["method_input"]["method_received_task_id"] is False
                and row["method_input"]["method_received_seed"] is False
                and (row["method_input"]["method_received_reward"] is False)
                and (row["method_input"]["method_received_evaluator_fields"] is False)
                and (row["evaluation_audit"]["reward_or_info_forwarded_to_method"] is False)
                for row in rows
            )
        ),
        "controller_arm_matches_manifest": all(
            (row["method_input"]["controller_arm"] == FULL_METHOD for row in rows)
        ),
        "no_action_after_reward_or_terminal_stop": all((_no_action_after_terminal(row) for row in rows)),
        "all_episode_budgets_respected": all(
            (
                _metric(row, "gui_actions") <= protocol["budgets"]["maximum_gui_actions"]
                and _metric(row, "planner_calls") <= protocol["budgets"]["maximum_planner_calls"]
                and (
                    float(row["metrics"].get("wall_seconds", 0.0))
                    <= protocol["budgets"]["maximum_wall_seconds"]
                )
                for row in rows
            )
        ),
        "all_60_success": metrics["success"] == int(protocol["expected_episodes"]),
        "every_family_10_of_10": all(
            (
                family["success"] == expected_per_family and family["episodes"] == expected_per_family
                for family in metrics["by_family"].values()
            )
        ),
        "zero_parser_failures": metrics["planner_parse_failures"] == 0,
        "zero_action_errors": metrics["action_errors"] == 0,
        "zero_runtime_halts": metrics["runtime_halts"] == 0,
        "zero_method_failures": metrics["method_failures"] == 0,
        "zero_uncertified_commits": metrics["uncertified_commits"] == 0,
        "zero_wrong_terminal_commits": metrics["wrong_terminal_commits"] == 0,
        "zero_terminal_transactions": metrics["terminal_transactions"] == 0,
        "zero_unrecovered_postconditions": metrics["unrecovered_postcondition_failures"] == 0,
        "all_raw_postconditions_recovered": metrics["verified_postcondition_recoveries"]
        == metrics["raw_postcondition_failures"],
        "all_attempted_restorations_pass": metrics["restoration_passes"] == metrics["restoration_attempts"],
        "zero_repeated_effect_keys": not repeated_effect_keys,
        "zero_no_effect_commits": metrics["commit_effect_failures"] == 0,
        "zero_inverse_reservation_stops": metrics["inverse_reservation_stops"] == 0,
        "repair_reservation_path_observed": metrics["interrupt_repair_reservation_audits"] > 0,
        "zero_interrupt_repair_reservation_fallbacks": metrics["interrupt_repair_reservation_fallbacks"] == 0,
        "repair_reservation_metrics_match_events": repair_audit["exact_accounting"]
        and repair_audit["metrics_match_events"],
        "all_observed_autocomplete_checks_are_suggestion_population_v9": bool(autocomplete_checks)
        and all(
            (
                event.get("checker_version") == "PACT-v9-suggestion-population"
                for _episode_id, event in autocomplete_checks
            )
        ),
        "every_autocomplete_episode_has_passing_suggestion_population_v9_check": set(
            (episode_id for episode_id, _event in autocomplete_checks)
        )
        == expected_autocomplete_ids
        and all(
            (
                any(
                    (
                        event.get("passed") is True
                        and event.get("checker_version") == "PACT-v9-suggestion-population"
                        for event in events
                    )
                )
                for events in autocomplete_by_episode.values()
            )
        ),
        "model_only_for_multirow_envelopes": all(
            (
                (event.get("model") is not None) == (len(event["envelope"]["candidates"]) > 1)
                for row in rows
                for event in row.get("trace", [])
                if event.get("type") == "envelope_decision_v8" and event["envelope"]["decision"] != "abstain"
            )
        ),
    }
