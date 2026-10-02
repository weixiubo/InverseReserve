from __future__ import annotations

from collections import Counter
from typing import Any, Iterable

from inversereserve.controllers.confirmation_ablation_agents_v10 import MATCHED_CONFIRMATION_DRIVERS_V10
from inversereserve.studies.confirmation_statistics_v7 import confirmation_comparisons
from inversereserve.studies.matched_confirmation_v9 import _no_action_after_terminal
from inversereserve.studies.matched_confirmation_v9 import aggregate_arm as aggregate_arm_v9
from inversereserve.studies.validation import require

"Result-independent final matched design for recovery-solvent PACT-v10."
ARMS = ("raw_open_loop_v10_matched", "typed_no_certificate_v10", "full_pact_v10")
FULL_METHOD = "full_pact_v10"
BASELINES = ("raw_open_loop_v10_matched", "typed_no_certificate_v10")
NO_CERTIFICATE_METHOD = "typed_no_certificate_v10"
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
    "full_zero_interrupt_repair_reservation_fallbacks": True,
    "full_repair_reservation_metrics_match_events": True,
    "full_all_attempted_restorations_pass": True,
    "no_certificate_must_execute_uncertified_commit": True,
}
EXPECTED_INFORMATION_BOUNDARY = {
    "c452_v9_development_opened": True,
    "v10_trace_equivalence_derived": True,
    "repair_holdout_opened": True,
    "final_confirmation_opened": False,
    "task_seed_reward_and_evaluator_harness_only": True,
    "reward_or_evaluator_forwarded_to_method": False,
    "one_reset_per_task_seed_arm": True,
}
EXPECTED_DECISION_RULE = {
    "on_pass": "report the complete three-arm PACT-v10 causal confirmation and activate the evidence-bound paper migration",
    "on_failure": "preserve and report the complete negative confirmation without making the strong PACT efficacy claim",
}
V10_METRIC_NAMES = (
    "interrupt_repair_reservation_audits",
    "interrupt_repair_reservation_fallbacks",
    "interrupt_repair_inverse_fallbacks",
)


def validate_protocol_shape(protocol: dict[str, Any]) -> None:
    require(
        not protocol.get("candidate") != "PACT-v10-final-matched-confirmation-protocol",
        "unexpected final PACT-v10 protocol candidate",
    )
    require(
        not protocol.get("status") != "sealed_before_final_confirmation",
        "final protocol must be sealed before any reset",
    )
    require(not tuple(protocol.get("arms", ())) != ARMS, "final matched arm order changed")
    require(
        not set(MATCHED_CONFIRMATION_DRIVERS_V10) != set(ARMS), "PACT-v10 matched driver registry changed"
    )
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
    expected_cells = len(TASKS) * len(FINAL_CONFIRMATION_SEEDS)
    require(
        not int(protocol.get("expected_task_seed_cells", -1)) != expected_cells,
        "final paired-cell count changed",
    )
    require(
        not int(protocol.get("expected_episodes", -1)) != expected_cells * len(ARMS),
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
        not set(protocol.get("activation", {})) != {"v10_trace_equivalence", "repair_holdout"},
        "final activation must bind both PACT-v10 predecessor gates",
    )


def episode_manifest(protocol: dict[str, Any]) -> list[dict[str, Any]]:
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


def _metric(row: dict[str, Any], name: str) -> int:
    return int(row.get("metrics", {}).get(name, 0))


def aggregate_arm(rows: Iterable[dict[str, Any]], protocol: dict[str, Any]) -> dict[str, Any]:
    rows = tuple(rows)
    output = aggregate_arm_v9(rows, protocol)
    for name in V10_METRIC_NAMES:
        output[name] = sum((_metric(row, name) for row in rows))
    return output


def repair_reservation_event_audit(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    rows = tuple(rows)
    events = [
        event
        for row in rows
        for event in row.get("runtime_events", [])
        if event.get("type") == "interrupt_repair_reservation"
    ]
    exact = _repair_accounting_exact(events)
    metric_audits = sum((_metric(row, "interrupt_repair_reservation_audits") for row in rows))
    metric_fallbacks = sum((_metric(row, "interrupt_repair_reservation_fallbacks") for row in rows))
    event_fallbacks = sum((not bool(event.get("allowed")) for event in events))
    inverse_groundings = sum(
        (
            event.get("type") == "compensator_grounding" and event.get("policy") == "inverse"
            for row in rows
            for event in row.get("runtime_events", [])
        )
    )
    metric_inverse_fallbacks = sum((_metric(row, "interrupt_repair_inverse_fallbacks") for row in rows))
    return {
        "events": len(events),
        "event_fallbacks": event_fallbacks,
        "inverse_groundings": inverse_groundings,
        "exact_accounting": exact,
        "metrics_match_events": metric_audits == len(events)
        and metric_fallbacks == event_fallbacks
        and (metric_inverse_fallbacks == inverse_groundings),
    }


def analyze_final_rows(
    rows: Iterable[dict[str, Any]], protocol: dict[str, Any], *, all_claims_complete: bool
) -> dict[str, Any]:
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
    strongest_other = max(BASELINES, key=lambda arm: (metrics[arm]["success"], arm))
    repair_audit = repair_reservation_event_audit(arm_rows[FULL_METHOD])
    checks = _final_rows_confirmation_checks(
        all_claims_complete=all_claims_complete,
        arm_rows=arm_rows,
        comparisons=comparisons,
        complete_arms=complete_arms,
        expected_per_arm=expected_per_arm,
        full=full,
        gates=gates,
        goal_hashes=goal_hashes,
        manifest_exact=manifest_exact,
        metrics=metrics,
        protocol=protocol,
        repair_audit=repair_audit,
        rows=rows,
    )
    return {
        "metrics": metrics,
        "statistics": statistics,
        "strongest_other_arm": strongest_other,
        "repair_reservation_audit": repair_audit,
        "checks": checks,
        "passed": all(checks.values()),
    }


def arm_order_counts(protocol: dict[str, Any]) -> dict[str, dict[int, int]]:
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
    expected_per_arm: int,
    full: Any,
    gates: Any,
    goal_hashes: Any,
    manifest_exact: Any,
    metrics: Any,
    protocol: Any,
    repair_audit: Any,
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
        "matched_goal_hashes_across_arms": len(goal_hashes) == expected_per_arm
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
        "full_zero_interrupt_repair_reservation_fallbacks": full["interrupt_repair_reservation_fallbacks"]
        == 0,
        "full_repair_reservation_metrics_match_events": repair_audit["exact_accounting"]
        and repair_audit["metrics_match_events"],
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


def _repair_accounting_exact(events: Any) -> Any:
    return all(
        (
            int(event.get("repair_pair_actions", -1)) == 2
            and int(event.get("registered_inverse_reserve", -1)) >= 1
            and (
                bool(event.get("allowed"))
                == (
                    int(event.get("remaining_gui_actions", -1)) - int(event.get("repair_pair_actions", -1))
                    >= int(event.get("registered_inverse_reserve", -1))
                )
            )
            for event in events
        )
    )
