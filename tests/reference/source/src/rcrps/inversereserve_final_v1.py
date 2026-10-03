"""Frozen design and analysis for the independent InverseReserve final grid."""

from __future__ import annotations

from collections import Counter
from typing import Any, Iterable

from .confirmation_ablation_agents_v13 import MATCHED_CONFIRMATION_DRIVERS_V13
from .confirmation_statistics_v7 import confirmation_comparisons
from .matched_confirmation_v9 import _no_action_after_terminal
from .matched_confirmation_v10 import aggregate_arm, repair_reservation_event_audit


ARMS = (
    "raw_open_loop_v13_matched",
    "typed_no_certificate_v13",
    "full_pact_v13",
)
FULL_METHOD = "full_pact_v13"
BASELINES = ("raw_open_loop_v13_matched", "typed_no_certificate_v13")
NO_CERTIFICATE_METHOD = "typed_no_certificate_v13"
FINAL_SEEDS = tuple(range(27701, 27721))
TASKS = (
    ("choose-date-nodelay", "date_picker"),
    ("use-autocomplete-nodelay", "autocomplete"),
    ("book-flight-nodelay", "flight_composite"),
    ("login-user-popup", "login_interrupt"),
    ("click-scroll-list", "scroll_list"),
    ("click-widget", "direct_widget_control"),
)
EXPECTED_BUDGETS = {
    "maximum_gui_actions": 40,
    "maximum_planner_calls": 40,
    "maximum_wall_seconds": 300.0,
}
EXPECTED_GENERATION = {
    "enable_thinking": False,
    "do_sample": False,
    "max_new_tokens": 64,
}
EXPECTED_STATISTICS = {
    "bootstrap_samples": 50_000,
    "bootstrap_seed": 270_727,
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
    "full_zero_terminal_transactions": True,
    "full_zero_uncertified_commits": True,
    "full_zero_action_errors": True,
    "full_zero_runtime_halts": True,
    "full_zero_unrecovered_postconditions": True,
    "full_zero_no_effect_commits": True,
    "full_zero_inverse_reservation_stops": True,
    "full_zero_interrupt_repair_reservation_fallbacks": True,
    "full_all_attempted_restorations_pass": True,
    "full_no_success_with_method_failure": True,
    "full_terminal_ledger_exact": True,
    "full_all_reservations_solvent": True,
    "full_complete_commit_freshness": True,
    "no_certificate_must_execute_uncertified_commit": True,
}
EXPECTED_INFORMATION_BOUNDARY = {
    "c458_seed_range_opened_and_sealed": True,
    "c458_episode_replay_allowed": False,
    "old_27411_27420_partition_opened": False,
    "old_27501_27520_partition_opened": False,
    "final_27701_27720_partition_opened": False,
    "one_reset_per_task_seed_arm": True,
    "task_seed_reward_and_evaluator_harness_only": True,
    "reward_or_evaluator_forwarded_to_method": False,
    "c458_failure_authorizes_this_grid": False,
    "independent_post_diagnosis_protocol": True,
}
EXPECTED_DECISION_RULE = {
    "on_pass": (
        "seal the complete result and use it as the sole primary matched "
        "MiniWoB evidence for the InverseReserve paper"
    ),
    "on_failure": (
        "seal every outcome without replay or exclusion and remove any "
        "unsupported primary efficacy claim"
    ),
}
C458_RESULT_SHA256 = (
    "bcb7687a0c236bf58fb9d5e1e449469ae5eabdd0241f13549c7bf571fd9afda7"
)
TOP_LEVEL_KEYS = {
    "candidate",
    "status",
    "created_utc",
    "scientific_source_commit",
    "development_context",
    "arms",
    "full_method",
    "baselines",
    "tasks",
    "final_seeds",
    "expected_task_seed_cells",
    "expected_episodes",
    "budgets",
    "generation",
    "statistics",
    "confirmation_gates",
    "information_boundary",
    "decision_rule",
    "model_checkpoint",
    "source_sha256",
    "preregistration",
    "outputs",
}


def validate_protocol_shape(protocol: dict[str, Any]) -> None:
    if set(protocol) != TOP_LEVEL_KEYS:
        raise ValueError("InverseReserve final protocol schema changed")
    if protocol.get("candidate") != "InverseReserve-final-v1-protocol":
        raise ValueError("unexpected InverseReserve final protocol candidate")
    if protocol.get("status") != (
        "sealed_after_c458_diagnosis_before_any_final_reset"
    ):
        raise ValueError("InverseReserve final protocol was not sealed pre-reset")
    if tuple(protocol.get("arms", ())) != ARMS:
        raise ValueError("InverseReserve final arm order changed")
    if set(MATCHED_CONFIRMATION_DRIVERS_V13) != set(ARMS):
        raise ValueError("v13 matched driver registry changed")
    if protocol.get("full_method") != FULL_METHOD:
        raise ValueError("InverseReserve final full method changed")
    if tuple(protocol.get("baselines", ())) != BASELINES:
        raise ValueError("InverseReserve final baselines changed")
    tasks = tuple(
        (str(row.get("task_id")), str(row.get("family_group")))
        for row in protocol.get("tasks", ())
    )
    if tasks != TASKS:
        raise ValueError("InverseReserve final task population changed")
    if tuple(protocol.get("final_seeds", ())) != FINAL_SEEDS:
        raise ValueError("InverseReserve final seed population changed")
    cells = len(TASKS) * len(FINAL_SEEDS)
    if protocol.get("expected_task_seed_cells") != cells:
        raise ValueError("InverseReserve final paired-cell count changed")
    if protocol.get("expected_episodes") != cells * len(ARMS):
        raise ValueError("InverseReserve final episode count changed")
    if protocol.get("budgets") != EXPECTED_BUDGETS:
        raise ValueError("InverseReserve final budgets changed")
    if protocol.get("generation") != EXPECTED_GENERATION:
        raise ValueError("InverseReserve final decoding changed")
    if protocol.get("statistics") != EXPECTED_STATISTICS:
        raise ValueError("InverseReserve final statistics changed")
    if protocol.get("confirmation_gates") != EXPECTED_GATES:
        raise ValueError("InverseReserve final gates changed")
    if protocol.get("information_boundary") != EXPECTED_INFORMATION_BOUNDARY:
        raise ValueError("InverseReserve final information boundary changed")
    if protocol.get("decision_rule") != EXPECTED_DECISION_RULE:
        raise ValueError("InverseReserve final decision rule changed")
    context = protocol.get("development_context")
    if not (
        isinstance(context, dict)
        and context.get("c458_status") == "sealed_failed_development_gate"
        and context.get("c458_result_sha256") == C458_RESULT_SHA256
        and context.get("c458_successes") == 120
        and context.get("c458_episodes") == 120
        and context.get("selected_final_driver") == FULL_METHOD
        and context.get("v14_population_navigation_in_final_method") is False
        and context.get("c458_used_as_final_evidence") is False
    ):
        raise ValueError("InverseReserve final development context changed")
    if protocol.get("model_checkpoint") != "Qwen3.5-9B":
        raise ValueError("InverseReserve final model checkpoint changed")
    if not isinstance(protocol.get("source_sha256"), dict):
        raise ValueError("InverseReserve final source bindings are absent")
    if not isinstance(protocol.get("preregistration"), dict):
        raise ValueError("InverseReserve final preregistration is absent")
    if protocol.get("outputs") != {
        "run_directory": "runs/inversereserve_final_v1",
        "result": "validation/inversereserve_final_result_v1.json",
    }:
        raise ValueError("InverseReserve final output paths changed")


def episode_manifest(protocol: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the complete deterministic counterbalanced 360-episode grid."""

    validate_protocol_shape(protocol)
    rows: list[dict[str, Any]] = []
    for seed_index, seed in enumerate(protocol["final_seeds"]):
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
    expected = int(protocol["expected_episodes"])
    if len(rows) != expected or len({row["episode_id"] for row in rows}) != expected:
        raise ValueError("InverseReserve final manifest is incomplete or duplicated")
    return rows


def arm_order_counts(protocol: dict[str, Any]) -> dict[str, dict[int, int]]:
    counts = {arm: Counter() for arm in ARMS}
    for row in episode_manifest(protocol):
        counts[row["method"]][int(row["arm_position"])] += 1
    return {arm: dict(sorted(values.items())) for arm, values in counts.items()}


def _metric(row: dict[str, Any], name: str) -> int:
    return int(row.get("metrics", {}).get(name, 0))


def terminal_ledger_audit(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Audit retained terminal recovery ledgers without requiring them empty."""

    rows = tuple(rows)
    audits = []
    for row in rows:
        active = row.get("active_transactions_at_stop")
        completed = row.get("completed_transactions_at_stop")
        trace = row.get("trace")
        metrics = row.get("metrics", {})
        if not isinstance(active, list) or not isinstance(completed, list):
            audits.append({"exact": False, "reservations": False})
            continue
        typed = _metric(row, "typed_transactions")
        active_valid = all(
            isinstance(item, dict)
            and isinstance(item.get("bid"), str)
            and isinstance(item.get("transaction_kind"), str)
            and bool(item.get("transaction_kind"))
            and isinstance(item.get("operation"), str)
            for item in active
        )
        completed_valid = all(
            isinstance(item, dict) and item.get("restored") is True
            for item in completed
        )
        reserve_events = (
            [
                event
                for event in trace
                if event.get("type") == "inverse_budget_reservation"
            ]
            if isinstance(trace, list)
            else []
        )
        reservations = all(
            event.get("allowed") is True
            and isinstance(event.get("active_inverse_cost"), int)
            and isinstance(event.get("remaining_after_action"), int)
            and event["active_inverse_cost"] <= event["remaining_after_action"]
            for event in reserve_events
        )
        metric_audits = metrics.get("inverse_reservation_audits")
        if metric_audits is not None:
            reservations = reservations and int(metric_audits) == len(reserve_events)
        audits.append(
            {
                "exact": typed == len(active) + len(completed)
                and active_valid
                and completed_valid,
                "reservations": reservations,
                "active": len(active),
                "completed": len(completed),
                "typed": typed,
                "success": bool(row.get("success")),
            }
        )
    return {
        "episodes": len(audits),
        "typed_transactions": sum(int(row.get("typed", 0)) for row in audits),
        "active_transactions_at_terminal_stop": sum(
            int(row.get("active", 0)) for row in audits
        ),
        "completed_restorations_at_stop": sum(
            int(row.get("completed", 0)) for row in audits
        ),
        "successful_episodes_with_active_ledger": sum(
            bool(row.get("success")) and int(row.get("active", 0)) > 0
            for row in audits
        ),
        "exact_accounting": bool(audits) and all(row["exact"] for row in audits),
        "all_reservations_solvent": bool(audits)
        and all(row["reservations"] for row in audits),
    }


def complete_commit_audit(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Recompute every complete-public v13 commit check from runtime events."""

    rows = tuple(rows)
    checks = passes = rejections = 0
    exact = True
    for row in rows:
        events = [
            event
            for event in row.get("runtime_events", [])
            if event.get("type") == "complete_public_commit_observation_check_v13"
        ]
        event_passes = sum(event.get("passed") is True for event in events)
        event_rejections = sum(event.get("passed") is False for event in events)
        metrics = row.get("metrics", {})
        exact = exact and (
            metrics.get("complete_public_commit_checks_v13") == len(events)
            and metrics.get("complete_public_commit_passes_v13") == event_passes
            and metrics.get("complete_public_commit_rejections_v13")
            == event_rejections
        )
        checks += len(events)
        passes += event_passes
        rejections += event_rejections
    return {
        "checks": checks,
        "passes": passes,
        "rejections": rejections,
        "exact_accounting": bool(rows) and exact,
        "all_pass": checks > 0 and passes == checks and rejections == 0,
    }


def analyze_final_rows(
    rows: Iterable[dict[str, Any]],
    protocol: dict[str, Any],
    *,
    all_claims_complete: bool,
) -> dict[str, Any]:
    """Analyze the immutable grid without dropping failures or changing labels."""

    validate_protocol_shape(protocol)
    rows = tuple(rows)
    manifest = episode_manifest(protocol)
    expected = {row["episode_id"]: row for row in manifest}
    observed_ids = [str(row.get("episode", {}).get("episode_id")) for row in rows]
    exact_manifest = (
        len(rows) == len(manifest)
        and len(set(observed_ids)) == len(rows)
        and set(observed_ids) == set(expected)
        and all(
            row.get("episode")
            == expected.get(str(row.get("episode", {}).get("episode_id")))
            for row in rows
        )
    )
    arm_rows = {
        arm: tuple(
            row for row in rows if row.get("episode", {}).get("method") == arm
        )
        for arm in ARMS
    }
    expected_per_arm = int(protocol["expected_task_seed_cells"])
    complete_arms = all(len(arm_rows[arm]) == expected_per_arm for arm in ARMS)
    metrics = {arm: aggregate_arm(arm_rows[arm], protocol) for arm in ARMS}
    paired_input = [
        {
            "method": row["episode"]["method"],
            "task": row["episode"]["task"],
            "seed": row["episode"]["seed"],
            "success": bool(row["success"])
            and not bool(row["infrastructure_failure"]),
            "infrastructure_failure": False,
        }
        for row in rows
    ]
    statistics = confirmation_comparisons(
        paired_input,
        full_method=FULL_METHOD,
        baselines=BASELINES,
        bootstrap_samples=int(protocol["statistics"]["bootstrap_samples"]),
        bootstrap_seed=int(protocol["statistics"]["bootstrap_seed"]),
        alpha=float(protocol["statistics"]["familywise_alpha"]),
    )
    full_rows = arm_rows[FULL_METHOD]
    full = metrics[FULL_METHOD]
    gates = protocol["confirmation_gates"]
    comparisons = statistics["comparisons"]
    goal_hashes: dict[tuple[str, int], set[str]] = {}
    for row in rows:
        key = (str(row["episode"]["task"]), int(row["episode"]["seed"]))
        goal_hashes.setdefault(key, set()).add(
            str(row["method_input"]["goal_sha256"])
        )
    repair_audit = repair_reservation_event_audit(full_rows)
    ledger_audit = terminal_ledger_audit(full_rows)
    commit_audit = complete_commit_audit(full_rows)
    checks = {
        "complete_counterbalanced_manifest": exact_manifest and complete_arms,
        "all_claims_complete_and_single_open": bool(all_claims_complete),
        "zero_infrastructure_failures": all(
            not row.get("infrastructure_failure") for row in rows
        ),
        "zero_forbidden_method_inputs": all(
            row["method_input"]["method_received_task_id"] is False
            and row["method_input"]["method_received_seed"] is False
            and row["method_input"]["method_received_reward"] is False
            and row["method_input"]["method_received_evaluator_fields"] is False
            and row["evaluation_audit"]["reward_or_info_forwarded_to_method"]
            is False
            for row in rows
        ),
        "controller_arm_matches_manifest": all(
            row["method_input"]["controller_arm"] == row["episode"]["method"]
            for row in rows
        ),
        "matched_goal_hashes_across_arms": len(goal_hashes) == expected_per_arm
        and all(len(values) == 1 for values in goal_hashes.values()),
        "no_action_after_terminal_stop": all(
            _no_action_after_terminal(row) for row in rows
        ),
        "all_episode_budgets_respected": all(
            _metric(row, "gui_actions")
            <= protocol["budgets"]["maximum_gui_actions"]
            and _metric(row, "planner_calls")
            <= protocol["budgets"]["maximum_planner_calls"]
            and float(row["metrics"].get("wall_seconds", 0.0))
            <= protocol["budgets"]["maximum_wall_seconds"]
            for row in rows
        ),
        "full_minimum_successes": (
            full["success"] >= gates["full_minimum_successes"]
        ),
        "full_minimum_successes_per_family": (
            full["minimum_family_successes"]
            >= gates["full_minimum_successes_per_family"]
        ),
        "full_zero_parser_failures": full["planner_parse_failures"] == 0,
        "full_zero_wrong_terminal_commits": full["wrong_terminal_commits"] == 0,
        "full_zero_terminal_transactions": full["terminal_transactions"] == 0,
        "full_zero_uncertified_commits": full["uncertified_commits"] == 0,
        "full_zero_action_errors": full["action_errors"] == 0,
        "full_zero_runtime_halts": full["runtime_halts"] == 0,
        "full_zero_unrecovered_postconditions": (
            full["unrecovered_postcondition_failures"] == 0
        ),
        "full_zero_no_effect_commits": full["commit_effect_failures"] == 0,
        "full_zero_inverse_reservation_stops": (
            full["inverse_reservation_stops"] == 0
        ),
        "full_zero_interrupt_repair_reservation_fallbacks": (
            full["interrupt_repair_reservation_fallbacks"] == 0
        ),
        "full_repair_reservation_metrics_match_events": (
            repair_audit["exact_accounting"]
            and repair_audit["metrics_match_events"]
        ),
        "full_all_attempted_restorations_pass": (
            full["restoration_passes"] == full["restoration_attempts"]
        ),
        "full_no_success_with_method_failure": all(
            not row.get("success") or row.get("method_failure") is None
            for row in full_rows
        ),
        "full_terminal_ledger_exact": ledger_audit["exact_accounting"],
        "full_all_reservations_solvent": (
            ledger_audit["all_reservations_solvent"]
        ),
        "full_complete_commit_freshness": (
            commit_audit["exact_accounting"] and commit_audit["all_pass"]
        ),
        "full_model_only_for_multirow_envelopes": all(
            (event.get("model") is not None)
            == (len(event["envelope"]["candidates"]) > 1)
            for row in full_rows
            for event in row.get("trace", [])
            if event.get("type") == "envelope_decision_v8"
            and event["envelope"]["decision"] != "abstain"
        ),
        "no_certificate_executes_targeted_ablation": (
            metrics[NO_CERTIFICATE_METHOD]["uncertified_commits"] > 0
        ),
        "minimum_net_paired_wins_against_each_baseline": all(
            comparisons[baseline]["net_paired_successes"]
            >= gates["minimum_net_paired_wins_per_baseline"]
            for baseline in BASELINES
        ),
        "positive_cluster_bootstrap_lower_against_each_baseline": all(
            comparisons[baseline]["bootstrap_95_percent_ci"][0] > 0.0
            for baseline in BASELINES
        ),
        "holm_rejects_against_each_baseline": all(
            comparisons[baseline]["holm"]["rejected"] is True
            for baseline in BASELINES
        ),
    }
    return {
        "metrics": metrics,
        "statistics": statistics,
        "strongest_other_arm": max(
            BASELINES, key=lambda arm: (metrics[arm]["success"], arm)
        ),
        "repair_reservation_audit": repair_audit,
        "terminal_ledger_audit": ledger_audit,
        "complete_commit_audit": commit_audit,
        "checks": checks,
        "passed": all(checks.values()),
    }
