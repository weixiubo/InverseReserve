from __future__ import annotations

from collections import Counter
from typing import Any, Iterable

from inversereserve.controllers.confirmation_ablation_agents_v9 import MATCHED_CONFIRMATION_DRIVERS_V9
from inversereserve.studies.confirmation_statistics_v7 import confirmation_comparisons
from inversereserve.studies.pact_statistics import (
    restoration_summary,
    wilson_interval,
    zero_event_upper_bound,
)
from inversereserve.studies.validation import require

"Result-independent protocol and analysis core for final PACT-v9 evidence.\n\nThis module contains no final outcomes and performs no environment resets.  It\ndefines the exact three-arm intervention, manifest, aggregation, and decision\nrule that a later source-bound protocol may activate only after the fresh\ndevelopment and repair-holdout gates pass.\n"
ARMS = ("raw_open_loop_v9_matched", "typed_no_certificate_v9", "full_pact_v9")
FULL_METHOD = "full_pact_v9"
BASELINES = ("raw_open_loop_v9_matched", "typed_no_certificate_v9")
NO_CERTIFICATE_METHOD = "typed_no_certificate_v9"
FINAL_CONFIRMATION_SEEDS = tuple(range(27501, 27521))
TASKS = (
    ("choose-date-nodelay", "date_picker"),
    ("use-autocomplete-nodelay", "autocomplete"),
    ("book-flight-nodelay", "flight_composite"),
    ("login-user-popup", "login_interrupt"),
    ("click-scroll-list", "scroll_list"),
    ("click-widget", "direct_widget_control"),
)
EXPECTED_BUDGETS = {"maximum_gui_actions": 40, "maximum_planner_calls": 40, "maximum_wall_seconds": 300.0}
EXPECTED_GENERATION = {"enable_thinking": False, "do_sample": False, "max_new_tokens": 64}
EXPECTED_STATISTICS = {
    "bootstrap_samples": 50000,
    "bootstrap_seed": 270727,
    "familywise_alpha": 0.05,
    "bootstrap_unit": "seed cluster shared across all task families",
    "multiplicity": "Holm step-down over both full-method comparisons",
}
EXPECTED_GATES = {
    "full_minimum_successes": 114,
    "full_minimum_successes_per_family": 18,
    "minimum_net_paired_wins_per_baseline": 12,
    "require_positive_cluster_bootstrap_lower_per_baseline": True,
    "require_holm_rejection_per_baseline": True,
    "full_zero_parser_failures": True,
    "full_zero_wrong_terminal_commits": True,
    "full_zero_terminal_previews": True,
    "full_zero_uncertified_commits": True,
    "full_zero_action_errors": True,
    "full_zero_runtime_halts": True,
    "full_zero_method_failures": True,
    "full_zero_unrecovered_postconditions": True,
    "full_zero_no_effect_commits": True,
    "full_zero_inverse_reservation_stops": True,
    "full_all_attempted_restorations_pass": True,
    "no_certificate_must_execute_uncertified_commit": True,
}
EXPECTED_INFORMATION_BOUNDARY = {
    "fresh_visible_development_opened": True,
    "repair_holdout_opened": True,
    "final_confirmation_opened": False,
    "task_seed_reward_and_evaluator_harness_only": True,
    "reward_or_evaluator_forwarded_to_method": False,
    "one_reset_per_task_seed_arm": True,
}
EXPECTED_DECISION_RULE = {
    "on_pass": "report the complete three-arm PACT-v9 causal confirmation and activate the evidence-bound paper migration",
    "on_failure": "preserve and report the complete negative confirmation without making the strong PACT efficacy claim",
}
METRIC_NAMES = (
    "gui_actions",
    "planner_calls",
    "planner_actual_calls",
    "planner_cache_hits",
    "planner_parse_failures",
    "typed_transactions",
    "certified_commits",
    "uncertified_commits",
    "restoration_attempts",
    "restoration_passes",
    "wrong_terminal_commits",
    "terminal_transactions",
    "action_errors",
    "commit_effect_passes",
    "commit_effect_failures",
    "quarantined_commit_keys",
    "resolved_transaction_bids",
    "inverse_reservation_audits",
    "inverse_reservation_stops",
)
CORE_SAFETY_METRICS = (
    "planner_parse_failures",
    "wrong_terminal_commits",
    "terminal_transactions",
    "uncertified_commits",
    "action_errors",
    "commit_effect_failures",
    "inverse_reservation_stops",
)


def validate_protocol_shape(protocol: dict[str, Any]) -> None:
    """Reject any later protocol that weakens the result-independent design."""
    require(
        not protocol.get("candidate") != "PACT-v9-final-matched-confirmation-protocol",
        "unexpected final PACT-v9 protocol candidate",
    )
    require(
        not protocol.get("status") != "sealed_before_final_confirmation",
        "final protocol must be sealed before any reset",
    )
    require(not tuple(protocol.get("arms", ())) != ARMS, "final matched arm order changed")
    require(not set(MATCHED_CONFIRMATION_DRIVERS_V9) != set(ARMS), "PACT-v9 matched driver registry changed")
    require(not protocol.get("full_method") != FULL_METHOD, "final full-method identifier changed")
    require(not tuple(protocol.get("baselines", ())) != BASELINES, "final baseline family changed")
    tasks = tuple(
        ((str(row.get("task_id")), str(row.get("family_group"))) for row in protocol.get("tasks", ()))
    )
    require(not tasks != TASKS, "final task-family population changed")
    require(
        not tuple(protocol.get("final_confirmation_seeds", ())) != FINAL_CONFIRMATION_SEEDS,
        "final confirmation seed partition changed",
    )
    require(
        not int(protocol.get("expected_task_seed_cells", -1)) != len(TASKS) * len(FINAL_CONFIRMATION_SEEDS),
        "final paired-cell count changed",
    )
    require(
        not int(protocol.get("expected_episodes", -1))
        != len(TASKS) * len(FINAL_CONFIRMATION_SEEDS) * len(ARMS),
        "final episode count changed",
    )
    require(not protocol.get("budgets") != EXPECTED_BUDGETS, "final equal budgets changed")
    require(not protocol.get("generation") != EXPECTED_GENERATION, "final model generation settings changed")
    require(not protocol.get("statistics") != EXPECTED_STATISTICS, "final statistical analysis changed")
    require(not protocol.get("confirmation_gates") != EXPECTED_GATES, "final confirmation gates changed")
    require(
        not protocol.get("information_boundary") != EXPECTED_INFORMATION_BOUNDARY,
        "final information boundary changed",
    )
    require(
        not protocol.get("decision_rule") != EXPECTED_DECISION_RULE,
        "final confirmation decision rule changed",
    )
    require(
        not set(protocol.get("activation", {})) != {"fresh_visible_development", "repair_holdout"},
        "final activation must bind both preceding gates",
    )


def episode_manifest(protocol: dict[str, Any]) -> list[dict[str, Any]]:
    """Return a deterministic, counterbalanced, complete three-arm grid."""
    validate_protocol_shape(protocol)
    rows: list[dict[str, Any]] = []
    for seed_index, seed in enumerate(protocol["final_confirmation_seeds"]):
        for task_index, task in enumerate(protocol["tasks"]):
            rotation = (seed_index + task_index) % len(ARMS)
            order = ARMS[rotation:] + ARMS[:rotation]
            for arm_position, method in enumerate(order):
                task_id = str(task["task_id"])
                rows.append(
                    {
                        "episode_index": len(rows),
                        "task_index": task_index,
                        "seed_index": seed_index,
                        "arm_position": arm_position,
                        "task": task_id,
                        "family_group": str(task["family_group"]),
                        "seed": int(seed),
                        "method": method,
                        "episode_id": f"{task_id}__seed{int(seed)}__{method}",
                    }
                )
    if len(rows) != int(protocol["expected_episodes"]):
        raise ValueError("final manifest count changed")
    if len({row["episode_id"] for row in rows}) != len(rows):
        raise ValueError("final manifest contains duplicate episode identifiers")
    return rows


def _recovery_for(events: list[dict[str, Any]], failed_index: int) -> str:
    later = [event for event in events if int(event.get("event_index", -1)) > failed_index]
    dynamic = any(
        (
            event.get("type") == "restoration"
            and event.get("trigger") == "dynamic public compensation"
            and (event.get("passed") is True)
            for event in later
        )
    ) and any(
        (
            event.get("type") == "postcondition"
            and event.get("context") == "typed retry"
            and (event.get("passed") is True)
            for event in later
        )
    )
    if dynamic:
        return "dynamic_compensation_restored_and_retry_passed"
    if any((event.get("type") == "restoration" and event.get("passed") is True for event in later)):
        return "static_restoration_passed"
    return "unrecovered"


def _metric(row: dict[str, Any], name: str) -> int:
    return int(row.get("metrics", {}).get(name, 0))


def aggregate_arm(rows: Iterable[dict[str, Any]], protocol: dict[str, Any]) -> dict[str, Any]:
    """Aggregate one arm without assuming v8-only metrics exist on raw control."""
    rows = tuple(rows)
    if not rows:
        raise ValueError("arm aggregation requires episode rows")
    by_family = _aggregate_families(rows, protocol)
    failures = _postcondition_failures(rows)
    success = sum((bool(row["success"]) for row in rows))
    totals = _arm_metric_totals(rows)
    runtime_halts = sum((bool(row["metrics"].get("runtime_halted")) for row in rows))
    method_failures = sum((row.get("method_failure") is not None for row in rows))
    infrastructure_failures = sum((bool(row.get("infrastructure_failure")) for row in rows))
    recovered = sum((row["recovery"] != "unrecovered" for row in failures))
    unrecovered = len(failures) - recovered
    output: dict[str, Any] = {
        "success": success,
        "episodes": len(rows),
        "success_rate": success / len(rows),
        "success_wilson_95_percent_interval": list(wilson_interval(success, len(rows))),
        "macro_success": sum((row["success_rate"] for row in by_family.values())) / len(by_family),
        "minimum_family_successes": min((row["success"] for row in by_family.values())),
        "minimum_family_success_rate": min((row["success_rate"] for row in by_family.values())),
        "by_family": by_family,
        **totals,
        "runtime_halts": runtime_halts,
        "method_failures": method_failures,
        "infrastructure_failures": infrastructure_failures,
        "raw_postcondition_failures": len(failures),
        "verified_postcondition_recoveries": recovered,
        "unrecovered_postcondition_failures": unrecovered,
        "postcondition_failure_rows": failures,
    }
    output["restoration"] = restoration_summary(
        [
            {
                "restoration_attempts": _metric(row, "restoration_attempts"),
                "restoration_passes": _metric(row, "restoration_passes"),
            }
            for row in rows
        ]
    )
    output["safety_episode_events"] = {}
    for name in CORE_SAFETY_METRICS:
        episodes_with_event = sum((_metric(row, name) > 0 for row in rows))
        output["safety_episode_events"][name] = {
            "episodes_with_event": episodes_with_event,
            "episodes": len(rows),
            "zero_event_upper_95_percent_bound": zero_event_upper_bound(len(rows))
            if episodes_with_event == 0
            else None,
        }
    return output


def _no_action_after_terminal(row: dict[str, Any]) -> bool:
    return not any(
        (
            float(action.get("reward", 0.0)) > 0.0
            or bool(action.get("terminated"))
            or bool(action.get("truncated"))
            for action in row.get("actions", [])[:-1]
        )
    )


def analyze_final_rows(
    rows: Iterable[dict[str, Any]], protocol: dict[str, Any], *, all_claims_complete: bool
) -> dict[str, Any]:
    """Apply the frozen causal, safety, and integrity gates to final rows."""
    validate_protocol_shape(protocol)
    rows = tuple(rows)
    manifest = episode_manifest(protocol)
    expected_by_id = {row["episode_id"]: row for row in manifest}
    observed_ids = [str(row.get("episode", {}).get("episode_id")) for row in rows]
    manifest_exact = (
        len(rows) == len(manifest)
        and len(set(observed_ids)) == len(observed_ids)
        and (set(observed_ids) == set(expected_by_id))
        and all((row["episode"] == expected_by_id[row["episode"]["episode_id"]] for row in rows))
    )
    arm_rows = {
        arm: tuple((row for row in rows if row.get("episode", {}).get("method") == arm)) for arm in ARMS
    }
    expected_per_arm = int(protocol["expected_task_seed_cells"])
    complete_arms = all((len(arm_rows[arm]) == expected_per_arm for arm in ARMS))
    metrics = {arm: aggregate_arm(arm_rows[arm], protocol) for arm in ARMS if arm_rows[arm]}
    if set(metrics) != set(ARMS):
        raise ValueError("final rows do not contain all three arms")
    paired_input = _paired_success_input(rows)
    statistics = confirmation_comparisons(
        paired_input,
        full_method=FULL_METHOD,
        baselines=BASELINES,
        bootstrap_samples=int(protocol["statistics"]["bootstrap_samples"]),
        bootstrap_seed=int(protocol["statistics"]["bootstrap_seed"]),
        alpha=float(protocol["statistics"]["familywise_alpha"]),
    )
    full = metrics[FULL_METHOD]
    gates = protocol["confirmation_gates"]
    comparisons = statistics["comparisons"]
    goal_hashes: dict[tuple[str, int], set[str]] = {}
    for row in rows:
        key = (str(row["episode"]["task"]), int(row["episode"]["seed"]))
        goal_hashes.setdefault(key, set()).add(str(row["method_input"]["goal_sha256"]))
    other_successes = _baseline_successes(metrics)
    strongest_other = max(BASELINES, key=lambda arm: (other_successes[arm], arm))
    checks = _final_rows_confirmation_checks(
        all_claims_complete=all_claims_complete,
        arm_rows=arm_rows,
        comparisons=comparisons,
        complete_arms=complete_arms,
        full=full,
        gates=gates,
        goal_hashes=goal_hashes,
        manifest_exact=manifest_exact,
        metrics=metrics,
        protocol=protocol,
        rows=rows,
    )
    return {
        "metrics": metrics,
        "statistics": statistics,
        "strongest_other_arm": strongest_other,
        "checks": checks,
        "passed": all(checks.values()),
    }


def arm_order_counts(protocol: dict[str, Any]) -> dict[str, dict[int, int]]:
    """Expose counterbalancing counts for protocol audits and paper artifacts."""
    counts = {arm: Counter() for arm in ARMS}
    for row in episode_manifest(protocol):
        counts[row["method"]][int(row["arm_position"])] += 1
    return {arm: dict(sorted(values.items())) for arm, values in counts.items()}


def _final_rows_confirmation_checks(
    *,
    all_claims_complete: bool,
    arm_rows: Any,
    comparisons: list[dict[str, Any]],
    complete_arms: Any,
    full: Any,
    gates: Any,
    goal_hashes: Any,
    manifest_exact: Any,
    metrics: Any,
    protocol: Any,
    rows: tuple[dict[str, Any], ...],
) -> dict[str, bool]:
    """Apply the registered decision gates to computed outcomes."""
    return {
        "complete_counterbalanced_manifest": manifest_exact and complete_arms,
        "all_claims_complete_and_single_open": bool(all_claims_complete),
        "zero_infrastructure_failures": all((not row.get("infrastructure_failure") for row in rows)),
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
            (row["method_input"]["controller_arm"] == row["episode"]["method"] for row in rows)
        ),
        "matched_goal_hashes_across_arms": len(goal_hashes) == int(protocol["expected_task_seed_cells"])
        and all((len(values) == 1 for values in goal_hashes.values())),
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
        "full_minimum_successes": full["success"] >= gates["full_minimum_successes"],
        "full_minimum_successes_per_family": full["minimum_family_successes"]
        >= gates["full_minimum_successes_per_family"],
        "full_zero_parser_failures": full["planner_parse_failures"] == 0,
        "full_zero_wrong_terminal_commits": full["wrong_terminal_commits"] == 0,
        "full_zero_terminal_previews": full["terminal_transactions"] == 0,
        "full_zero_uncertified_commits": full["uncertified_commits"] == 0,
        "full_zero_action_errors": full["action_errors"] == 0,
        "full_zero_runtime_halts": full["runtime_halts"] == 0,
        "full_zero_method_failures": full["method_failures"] == 0,
        "full_zero_unrecovered_postconditions": full["unrecovered_postcondition_failures"] == 0,
        "full_zero_no_effect_commits": full["commit_effect_failures"] == 0,
        "full_zero_inverse_reservation_stops": full["inverse_reservation_stops"] == 0,
        "full_all_attempted_restorations_pass": full["restoration_passes"] == full["restoration_attempts"],
        "full_model_only_for_multirow_envelopes": all(
            (
                (event.get("model") is not None) == (len(event["envelope"]["candidates"]) > 1)
                for row in arm_rows[FULL_METHOD]
                for event in row.get("trace", [])
                if event.get("type") == "envelope_decision_v8" and event["envelope"]["decision"] != "abstain"
            )
        ),
        "no_certificate_executes_targeted_ablation": metrics[NO_CERTIFICATE_METHOD]["uncertified_commits"]
        > 0,
        "minimum_net_paired_wins_against_each_baseline": all(
            (
                comparisons[baseline]["net_paired_successes"] >= gates["minimum_net_paired_wins_per_baseline"]
                for baseline in BASELINES
            )
        ),
        "positive_cluster_bootstrap_lower_against_each_baseline": all(
            (comparisons[baseline]["bootstrap_95_percent_ci"][0] > 0.0 for baseline in BASELINES)
        ),
        "holm_rejects_against_each_baseline": all(
            (comparisons[baseline]["holm"]["rejected"] is True for baseline in BASELINES)
        ),
    }


def _postcondition_failures(rows: tuple[dict[str, Any], ...]) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    for row in rows:
        events = list(row.get("runtime_events", []))
        for event in events:
            if event.get("type") == "postcondition" and event.get("passed") is False:
                event_index = int(event.get("event_index", -1))
                failures.append(
                    {
                        "episode_id": row["episode"]["episode_id"],
                        "contract_kind": event.get("contract_kind"),
                        "reason": event.get("reason"),
                        "recovery": _recovery_for(events, event_index),
                    }
                )
    return failures


def _aggregate_families(
    rows: tuple[dict[str, Any], ...], protocol: dict[str, Any]
) -> dict[str, dict[str, Any]]:
    by_family: dict[str, dict[str, Any]] = {}
    for task in protocol["tasks"]:
        task_id = str(task["task_id"])
        subset = tuple((row for row in rows if row["episode"]["task"] == task_id))
        if not subset:
            raise ValueError(f"arm has no episodes for {task_id}")
        successes = sum((bool(row["success"]) for row in subset))
        by_family[task_id] = {
            "success": successes,
            "episodes": len(subset),
            "success_rate": successes / len(subset),
            "wilson_95_percent_interval": list(wilson_interval(successes, len(subset))),
        }
    return by_family


def _paired_success_input(rows: Any) -> Any:
    return [
        {
            "method": row["episode"]["method"],
            "task": row["episode"]["task"],
            "seed": row["episode"]["seed"],
            "success": bool(row["success"]) and (not bool(row["infrastructure_failure"])),
            "infrastructure_failure": False,
        }
        for row in rows
    ]


def _arm_metric_totals(rows: Any) -> Any:
    return {name: sum((_metric(row, name) for row in rows)) for name in METRIC_NAMES}


def _baseline_successes(metrics: dict[str, Any]) -> dict[str, Any]:
    return {arm: metrics[arm]["success"] for arm in BASELINES}
