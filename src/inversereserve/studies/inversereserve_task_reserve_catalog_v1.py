from __future__ import annotations

from collections import Counter
from contextlib import contextmanager
from typing import Any, Iterable, Iterator

from inversereserve.controllers.capacity_reserve_drivers_v18 import RESERVATION_EVENT_V18
from inversereserve.controllers.capacity_reserve_drivers_v21 import (
    RUNTIME_VERSION_V21,
    TASK_RESERVE_SINGLE_ACTIVE_V21,
    TASK_RESERVE_SOURCE_V21,
    TASK_RESERVE_TOP_CLEANUP_V21,
    TaskReserveSingleActiveDriverV21,
    TaskReserveTopCleanupDriverV21,
)
from inversereserve.controllers.capacity_reserve_drivers_v21 import TASK_RESERVE_V21 as TASK_RESERVE_V21
from inversereserve.studies import inversereserve_miniwob_catalog_replication_v1 as catalog
from inversereserve.studies import inversereserve_miniwob_transfer_v2 as v2
from inversereserve.studies.validation import require

"Prospective binding-budget catalog study with a shared task reserve."
CANDIDATE = "InverseReserve-task-reserve-complete-catalog-v1"
STATUS = "frozen_before_any_37401_through_37420_reset_with_binding_budget_five"
FULL_METHOD = TASK_RESERVE_TOP_CLEANUP_V21
SAFE_BASELINE = TASK_RESERVE_SINGLE_ACTIVE_V21
ARMS = (FULL_METHOD, SAFE_BASELINE)
DRIVERS = {FULL_METHOD: TaskReserveTopCleanupDriverV21, SAFE_BASELINE: TaskReserveSingleActiveDriverV21}
SEEDS = tuple(range(37401, 37421))
MAXIMUM_GUI_ACTIONS = 5
COMMON_BUDGETS = dict(catalog.COMMON_BUDGETS)
GENERATION = dict(catalog.GENERATION)
RUNTIME_DEPLOYMENT = dict(catalog.RUNTIME_DEPLOYMENT)
PLANNER_MODEL = {
    **catalog.PLANNER_MODEL,
    "snapshot_files_sha256": dict(catalog.PLANNER_MODEL["snapshot_files_sha256"]),
}
BOOTSTRAP_SAMPLES = catalog.BOOTSTRAP_SAMPLES
BOOTSTRAP_SEED = 270736
ALPHA = 0.05
PREREGISTRATION = {
    "path": "paper/aaai27/notes/2026-07-26_inversereserve_task_reserve_catalog_v1_preregistration.md",
    "sha256": "a6a2a7846a80ce750ee1861da019cdd2ce90daf1a09f54a959ff72c1a3cc9b26",
}
COVERAGE_SURVEY = dict(catalog.COVERAGE_SURVEY)
DEVELOPMENT_RECORD = dict(catalog.DEVELOPMENT_RECORD)
INTERFACE_COMPLETION = {**catalog.INTERFACE_COMPLETION, "rules": list(catalog.INTERFACE_COMPLETION["rules"])}
CATALOG_TASKS = tuple(catalog.CATALOG_TASKS)
ELIGIBLE_TASKS = CATALOG_TASKS
PRIMARY_TASKS = CATALOG_TASKS
NEW_TEMPLATE_EXACT_TASKS = tuple(catalog.NEW_TEMPLATE_EXACT_TASKS)
SEEN_TEMPLATE_NEW_EXACT_TASKS = tuple(catalog.SEEN_TEMPLATE_NEW_EXACT_TASKS)
PREVIOUSLY_EXERCISED_EXACT_TASKS = tuple(catalog.PREVIOUSLY_EXERCISED_EXACT_TASKS)
PURPOSE = {
    "claim_status": "prospective_binding_budget_task_reserve_strong_control",
    "confirmation_status": "fresh_seed_complete_catalog_replication_not_external_confirmation",
    "selection_status": "complete transaction catalog and B=5 fixed before seeds 37401--37420; no task-level or outcome-level exclusion",
    "question": "whether stack-wide solvent nesting improves closed success over a one-active control when both preserve the same one-call terminal task reserve",
    "outcome_based_exclusion_allowed": False,
}
OUTCOME_DEFINITIONS = {
    **catalog.OUTCOME_DEFINITIONS,
    "planner_task_reserve": "one action retained at every reversible prerequisite for the structured goal contract's future terminal call",
    "task_reserve_block": "a prerequisite rejected by h=1 that inverse-only accounting would admit at the same public state",
}
PRIMARY_ANALYSIS = {
    **catalog.PRIMARY_ANALYSIS,
    "name": "paired_complete_catalog_task_reserve_strong_control",
    "full_method": FULL_METHOD,
    "baseline": SAFE_BASELINE,
    "population": "complete transaction-eligible MiniWoB++ catalog",
    "tasks": list(PRIMARY_TASKS),
    "maximum_gui_actions": MAXIMUM_GUI_ACTIONS,
    "planner_task_reserve": TASK_RESERVE_V21,
    "bootstrap_seed": BOOTSTRAP_SEED,
    "alpha": ALPHA,
    "minimum_full_closed_successes": 150,
    "minimum_net_paired_closed_successes": 20,
}
VALIDITY_GATES = {
    "complete_exact_grid": True,
    "zero_infrastructure_failures": True,
    "planner_is_exercised": True,
    "all_rows_respect_hard_budgets": True,
    "both_policies_zero_failed_stop_stranding": True,
    "both_policies_zero_runtime_halts": True,
    "all_restoration_attempts_pass": True,
    "both_policies_zero_v20_scope_failures": True,
    "all_successes_are_closed": True,
    "full_method_nested_admission_activates": True,
    "safe_baseline_cap_activates": True,
    "goal_terminal_promotion_activates": True,
    "task_reserve_events_are_source_bound": True,
    "every_capacity_transaction_applies_h1": True,
    "every_capacity_commit_applies_h0": True,
    "task_reserve_block_activates": True,
    "inverse_reserve_rejection_activates": True,
    "minimum_full_closed_successes": True,
    "minimum_net_paired_closed_successes": True,
    "bootstrap_lower_bound_strictly_positive": True,
    "paired_two_sided_exact_p_below_alpha": True,
}
DECISION_RULE = {
    "on_pass": "report the complete fresh-seed task-reserve comparison regardless of effect magnitude beyond the frozen gates",
    "on_failure": "seal every opened row and the complete result; make no positive task-reserve catalog claim and open no replacement population",
}
PLANNER_TASK_RESERVE = {
    "units": TASK_RESERVE_V21,
    "source": TASK_RESERVE_SOURCE_V21,
    "applied_when": "reversible prerequisite transaction",
    "consumed_when": "freshly certified terminal commit",
    "inferred_by_runtime": False,
    "shared_by_both_arms": True,
}


def derive_population(survey: dict[str, Any]) -> dict[str, Any]:
    return catalog.derive_population(survey)


def validate_population(population: dict[str, Any]) -> None:
    catalog.validate_population(population)


def task_records(population: dict[str, Any]) -> list[dict[str, Any]]:
    validate_population(population)
    return [
        {
            **population["task_metadata"][task],
            "primary_population": True,
            "new_template_population": task in NEW_TEMPLATE_EXACT_TASKS,
            "previously_exercised_population": task in PREVIOUSLY_EXERCISED_EXACT_TASKS,
            "maximum_gui_actions": MAXIMUM_GUI_ACTIONS,
            "planner_task_reserve": TASK_RESERVE_V21,
        }
        for task in CATALOG_TASKS
    ]


def expected_episodes() -> int:
    return len(ARMS) * len(SEEDS) * len(CATALOG_TASKS)


def _episode_manifest(protocol: dict[str, Any]) -> list[dict[str, Any]]:
    metadata = protocol["population"]["task_metadata"]
    rows: list[dict[str, Any]] = []
    for seed_index, seed in enumerate(SEEDS):
        for task_index, task in enumerate(CATALOG_TASKS):
            rotation = (seed_index + task_index) % len(ARMS)
            order = ARMS[rotation:] + ARMS[:rotation]
            for arm_position, method in enumerate(order):
                rows.append(
                    {
                        "episode_index": len(rows),
                        "seed_index": seed_index,
                        "task_index": task_index,
                        "arm_position": arm_position,
                        "task": task,
                        "family_group": metadata[task]["template_group"],
                        "population_stratum": metadata[task]["template_status"],
                        "primary_population": True,
                        "new_template_population": task in NEW_TEMPLATE_EXACT_TASKS,
                        "budget_level": "binding_b5",
                        "seed": seed,
                        "maximum_gui_actions": MAXIMUM_GUI_ACTIONS,
                        "planner_task_reserve": TASK_RESERVE_V21,
                        "method": method,
                        "episode_id": f"{task}__seed{seed}__b{MAXIMUM_GUI_ACTIONS}__h{TASK_RESERVE_V21}__{method}",
                    }
                )
    if len(rows) != expected_episodes() or len({row["episode_id"] for row in rows}) != len(rows):
        raise ValueError("task-reserve catalog manifest changed")
    return rows


def _v2_patch() -> dict[str, Any]:
    return {
        "CANDIDATE": CANDIDATE,
        "STATUS": STATUS,
        "FULL_METHOD": FULL_METHOD,
        "SAFE_BASELINE": SAFE_BASELINE,
        "ARMS": ARMS,
        "DRIVERS": DRIVERS,
        "SEEDS": SEEDS,
        "MAXIMUM_GUI_ACTIONS": MAXIMUM_GUI_ACTIONS,
        "COMMON_BUDGETS": COMMON_BUDGETS,
        "GENERATION": GENERATION,
        "RUNTIME_DEPLOYMENT": RUNTIME_DEPLOYMENT,
        "PLANNER_MODEL": PLANNER_MODEL,
        "BOOTSTRAP_SAMPLES": BOOTSTRAP_SAMPLES,
        "BOOTSTRAP_SEED": BOOTSTRAP_SEED,
        "ALPHA": ALPHA,
        "PREREGISTRATION": PREREGISTRATION,
        "COVERAGE_SURVEY": COVERAGE_SURVEY,
        "DEVELOPMENT_RECORD": DEVELOPMENT_RECORD,
        "INTERFACE_COMPLETION": INTERFACE_COMPLETION,
        "ELIGIBLE_TASKS": ELIGIBLE_TASKS,
        "NEW_TEMPLATE_EXACT_TASKS": NEW_TEMPLATE_EXACT_TASKS,
        "PRIMARY_TASKS": PRIMARY_TASKS,
        "PURPOSE": PURPOSE,
        "OUTCOME_DEFINITIONS": OUTCOME_DEFINITIONS,
        "PRIMARY_ANALYSIS": PRIMARY_ANALYSIS,
        "VALIDITY_GATES": VALIDITY_GATES,
        "DECISION_RULE": DECISION_RULE,
        "validate_population": validate_population,
        "task_records": task_records,
        "episode_manifest": _episode_manifest,
    }


@contextmanager
def _configured_v2() -> Iterator[None]:
    patch = _v2_patch()
    previous = {name: getattr(v2, name) for name in patch}
    for name, value in patch.items():
        setattr(v2, name, value)
    try:
        yield
    finally:
        for name, value in previous.items():
            setattr(v2, name, value)


def build_protocol(**kwargs: Any) -> dict[str, Any]:
    with _configured_v2():
        protocol = v2.build_protocol(**kwargs)
    protocol["isolated_policy_difference"] = (
        "both arms share the frozen PACT-v20 compiler, stack-wide inverse accounting, one-call planner task reserve, planner, executor, restoration, and certification; only the control refuses a second simultaneous typed obligation"
    )
    protocol["planner_task_reserve"] = dict(PLANNER_TASK_RESERVE)
    validate_protocol(protocol)
    return protocol


def validate_protocol(protocol: dict[str, Any]) -> None:
    with _configured_v2():
        v2.validate_protocol(protocol)
    require(
        not protocol.get("planner_task_reserve") != PLANNER_TASK_RESERVE,
        "task-reserve catalog planner reserve changed",
    )
    require(
        not protocol.get("expected_episodes") != expected_episodes(),
        "task-reserve catalog episode count changed",
    )


def episode_manifest(protocol: dict[str, Any]) -> list[dict[str, Any]]:
    validate_protocol(protocol)
    return _episode_manifest(protocol)


def arm_order_counts(protocol: dict[str, Any]) -> dict[str, dict[int, int]]:
    counts = Counter(((row["method"], row["arm_position"]) for row in episode_manifest(protocol)))
    return {arm: {position: counts[arm, position] for position in range(len(ARMS))} for arm in ARMS}


def _task_reserve_metrics(rows: Iterable[dict[str, Any]]) -> dict[str, int]:
    events = [
        event
        for row in rows
        for event in row.get("trace", ())
        if event.get("type") == RESERVATION_EVENT_V18 and event.get("runtime_version") == RUNTIME_VERSION_V21
    ]
    transactions = [event for event in events if event.get("decision") == "transact"]
    commits = [event for event in events if event.get("decision") == "commit"]
    return {
        "task_reserve_events": len(events),
        "capacity_transaction_gates": len(transactions),
        "capacity_commit_gates": len(commits),
        "transaction_gates_with_h1": sum(
            (event.get("applied_task_reserve") == TASK_RESERVE_V21 for event in transactions)
        ),
        "commit_gates_with_h0": sum((event.get("applied_task_reserve") == 0 for event in commits)),
        "source_bound_events": sum(
            (event.get("task_reserve_source") == TASK_RESERVE_SOURCE_V21 for event in events)
        ),
        "task_reserve_blocked_actions": sum(
            (
                event.get("inverse_only_allowed") is True and event.get("allowed") is False
                for event in transactions
            )
        ),
    }


def summarize_rows(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    materialized = tuple(rows)
    with _configured_v2():
        summary = v2.summarize_rows(materialized)
    summary.update(_task_reserve_metrics(materialized))
    return summary


def analyze_rows(
    rows: Iterable[dict[str, Any]], protocol: dict[str, Any], *, all_claims_complete: bool
) -> dict[str, Any]:
    materialized = tuple(rows)
    with _configured_v2():
        analysis = v2.analyze_rows(materialized, protocol, all_claims_complete=all_claims_complete)
    metrics = {
        arm: summarize_rows((row for row in materialized if row.get("episode", {}).get("method") == arm))
        for arm in ARMS
    }
    analysis["metrics"] = metrics
    full = metrics[FULL_METHOD]
    safe = metrics[SAFE_BASELINE]
    primary = analysis.get("paired_stack_vs_safe_closed_success")
    paired = (
        primary.get("paired_cell_sensitivity_and_seed_bootstrap", {}) if isinstance(primary, dict) else {}
    )
    interval = paired.get("bootstrap_95_percent_ci")
    if not isinstance(interval, list) or len(interval) != 2:
        interval = [float("-inf"), float("inf")]
    base_checks = analysis.get("checks", {})
    total_events = sum((values["task_reserve_events"] for values in metrics.values()))
    total_transactions = sum((values["capacity_transaction_gates"] for values in metrics.values()))
    total_commits = sum((values["capacity_commit_gates"] for values in metrics.values()))
    checks = _rows_confirmation_checks(
        base_checks=base_checks,
        full=full,
        interval=interval,
        metrics=metrics,
        paired=paired,
        total_commits=total_commits,
        total_events=total_events,
        total_transactions=total_transactions,
    )
    if set(checks) != set(VALIDITY_GATES):
        raise ValueError("task-reserve catalog validity inventory changed")
    analysis["checks"] = checks
    analysis["passed"] = all(checks.values())
    analysis["task_reserve_design"] = dict(PLANNER_TASK_RESERVE)
    analysis["binding_budget"] = MAXIMUM_GUI_ACTIONS
    analysis["claim_status"] = PURPOSE["claim_status"]
    analysis["confirmation_status"] = PURPOSE["confirmation_status"]
    analysis["baseline_closed_successes"] = safe["closed_successes"]
    return analysis


__all__ = [
    "ARMS",
    "CANDIDATE",
    "CATALOG_TASKS",
    "COVERAGE_SURVEY",
    "DECISION_RULE",
    "DRIVERS",
    "ELIGIBLE_TASKS",
    "FULL_METHOD",
    "GENERATION",
    "MAXIMUM_GUI_ACTIONS",
    "PLANNER_MODEL",
    "PLANNER_TASK_RESERVE",
    "PRIMARY_ANALYSIS",
    "PURPOSE",
    "RUNTIME_DEPLOYMENT",
    "SAFE_BASELINE",
    "SEEDS",
    "STATUS",
    "VALIDITY_GATES",
    "analyze_rows",
    "arm_order_counts",
    "build_protocol",
    "derive_population",
    "episode_manifest",
    "expected_episodes",
    "summarize_rows",
    "task_records",
    "validate_population",
    "validate_protocol",
]


def _rows_confirmation_checks(
    *,
    base_checks: Any,
    full: Any,
    interval: Any,
    metrics: Any,
    paired: Any,
    total_commits: Any,
    total_events: Any,
    total_transactions: Any,
) -> dict[str, bool]:
    """Apply the registered decision gates to computed outcomes."""
    return {
        "complete_exact_grid": base_checks.get("complete_exact_grid") is True,
        "zero_infrastructure_failures": base_checks.get("zero_infrastructure_failures") is True,
        "planner_is_exercised": base_checks.get("planner_is_exercised") is True,
        "all_rows_respect_hard_budgets": base_checks.get("all_rows_respect_hard_budgets") is True,
        "both_policies_zero_failed_stop_stranding": base_checks.get(
            "both_policies_zero_failed_stop_stranding"
        )
        is True,
        "both_policies_zero_runtime_halts": base_checks.get("both_policies_zero_runtime_halts") is True,
        "all_restoration_attempts_pass": base_checks.get("all_restoration_attempts_pass") is True,
        "both_policies_zero_v20_scope_failures": base_checks.get("both_policies_zero_v20_scope_failures")
        is True,
        "all_successes_are_closed": base_checks.get("all_successes_are_closed") is True,
        "full_method_nested_admission_activates": base_checks.get("full_method_nested_admission_activates")
        is True,
        "safe_baseline_cap_activates": base_checks.get("safe_baseline_cap_activates") is True,
        "goal_terminal_promotion_activates": base_checks.get("goal_terminal_promotion_activates") is True,
        "task_reserve_events_are_source_bound": total_events > 0
        and sum((values["source_bound_events"] for values in metrics.values())) == total_events,
        "every_capacity_transaction_applies_h1": total_transactions > 0
        and sum((values["transaction_gates_with_h1"] for values in metrics.values())) == total_transactions,
        "every_capacity_commit_applies_h0": total_commits > 0
        and sum((values["commit_gates_with_h0"] for values in metrics.values())) == total_commits,
        "task_reserve_block_activates": sum(
            (values["task_reserve_blocked_actions"] for values in metrics.values())
        )
        > 0,
        "inverse_reserve_rejection_activates": sum(
            (values["reserve_rejections"] for values in metrics.values())
        )
        > 0,
        "minimum_full_closed_successes": full["closed_successes"]
        >= PRIMARY_ANALYSIS["minimum_full_closed_successes"],
        "minimum_net_paired_closed_successes": int(paired.get("net_paired_successes", -1))
        >= PRIMARY_ANALYSIS["minimum_net_paired_closed_successes"],
        "bootstrap_lower_bound_strictly_positive": float(interval[0]) > 0.0,
        "paired_two_sided_exact_p_below_alpha": float(paired.get("exact_mcnemar_two_sided_p", 1.0)) < ALPHA,
    }
