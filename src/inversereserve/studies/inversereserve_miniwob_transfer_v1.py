from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable

from inversereserve.controllers.capacity_reserve_drivers_v18 import RESERVATION_EVENT_V18
from inversereserve.controllers.capacity_reserve_drivers_v19 import (
    SINGLE_OBLIGATION_POLICY_EVENT_V19,
)
from inversereserve.studies.designs.inversereserve_miniwob_transfer_v1 import ALPHA as ALPHA
from inversereserve.studies.designs.inversereserve_miniwob_transfer_v1 import ARMS as ARMS
from inversereserve.studies.designs.inversereserve_miniwob_transfer_v1 import (
    BOOTSTRAP_SAMPLES as BOOTSTRAP_SAMPLES,
)
from inversereserve.studies.designs.inversereserve_miniwob_transfer_v1 import BOOTSTRAP_SEED as BOOTSTRAP_SEED
from inversereserve.studies.designs.inversereserve_miniwob_transfer_v1 import CANDIDATE as CANDIDATE
from inversereserve.studies.designs.inversereserve_miniwob_transfer_v1 import COMMON_BUDGETS as COMMON_BUDGETS
from inversereserve.studies.designs.inversereserve_miniwob_transfer_v1 import (
    COVERAGE_SURVEY as COVERAGE_SURVEY,
)
from inversereserve.studies.designs.inversereserve_miniwob_transfer_v1 import DECISION_RULE as DECISION_RULE
from inversereserve.studies.designs.inversereserve_miniwob_transfer_v1 import DRIVERS as DRIVERS
from inversereserve.studies.designs.inversereserve_miniwob_transfer_v1 import ELIGIBLE_TASKS as ELIGIBLE_TASKS
from inversereserve.studies.designs.inversereserve_miniwob_transfer_v1 import FULL_METHOD as FULL_METHOD
from inversereserve.studies.designs.inversereserve_miniwob_transfer_v1 import (
    MAXIMUM_GUI_ACTIONS as MAXIMUM_GUI_ACTIONS,
)
from inversereserve.studies.designs.inversereserve_miniwob_transfer_v1 import (
    NEW_TEMPLATE_EXACT_TASKS as NEW_TEMPLATE_EXACT_TASKS,
)
from inversereserve.studies.designs.inversereserve_miniwob_transfer_v1 import (
    OUTCOME_DEFINITIONS as OUTCOME_DEFINITIONS,
)
from inversereserve.studies.designs.inversereserve_miniwob_transfer_v1 import (
    PREREGISTRATION as PREREGISTRATION,
)
from inversereserve.studies.designs.inversereserve_miniwob_transfer_v1 import (
    PRIMARY_ANALYSIS as PRIMARY_ANALYSIS,
)
from inversereserve.studies.designs.inversereserve_miniwob_transfer_v1 import PRIMARY_TASKS as PRIMARY_TASKS
from inversereserve.studies.designs.inversereserve_miniwob_transfer_v1 import PURPOSE as PURPOSE
from inversereserve.studies.designs.inversereserve_miniwob_transfer_v1 import SAFE_BASELINE as SAFE_BASELINE
from inversereserve.studies.designs.inversereserve_miniwob_transfer_v1 import SEEDS as SEEDS
from inversereserve.studies.designs.inversereserve_miniwob_transfer_v1 import STATUS as STATUS
from inversereserve.studies.designs.inversereserve_miniwob_transfer_v1 import VALIDITY_GATES as VALIDITY_GATES
from inversereserve.studies.designs.inversereserve_miniwob_transfer_v1 import (
    VARIANT_SUFFIXES as VARIANT_SUFFIXES,
)
from inversereserve.studies.designs.inversereserve_miniwob_transfer_v1 import (
    arm_order_counts as arm_order_counts,
)
from inversereserve.studies.designs.inversereserve_miniwob_transfer_v1 import build_protocol as build_protocol
from inversereserve.studies.designs.inversereserve_miniwob_transfer_v1 import (
    episode_manifest as episode_manifest,
)
from inversereserve.studies.designs.inversereserve_miniwob_transfer_v1 import (
    expected_episodes as expected_episodes,
)
from inversereserve.studies.designs.inversereserve_miniwob_transfer_v1 import (
    normalize_task_template as normalize_task_template,
)
from inversereserve.studies.designs.inversereserve_miniwob_transfer_v1 import task_records as task_records
from inversereserve.studies.designs.inversereserve_miniwob_transfer_v1 import (
    validate_population as validate_population,
)
from inversereserve.studies.designs.inversereserve_miniwob_transfer_v1 import (
    validate_protocol as validate_protocol,
)
from inversereserve.studies.episode_grid import matches_registered_grid
from inversereserve.studies.external_statistics import exact_mcnemar
from inversereserve.studies.inversereserve_capacity_regime_successor_v3 import _all_rows_respect_budgets
from inversereserve.studies.inversereserve_live_resource_stress_v1 import _active_count, _metric
from inversereserve.studies.pact_statistics import paired_binary_comparison

"Frozen outcome-blind MiniWoB++ task-transfer study for InverseReserve."
SURVEY_SEEDS = (37001, 37002)
PRIOR_EXACT_TASKS = (
    "book-flight-nodelay",
    "choose-date-nodelay",
    "click-scroll-list",
    "click-widget",
    "login-user-popup",
    "use-autocomplete-nodelay",
)


def derive_population(survey: dict[str, Any]) -> dict[str, Any]:
    """Derive the task population without reading any task outcome."""
    if _survey_identity_changed(survey):
        raise ValueError("coverage survey identity or completeness changed")
    rows = survey.get("rows")
    tasks = survey.get("tasks")
    if not isinstance(rows, list) or not isinstance(tasks, list):
        raise ValueError("coverage survey task rows are absent")
    if len(rows) != 250 or len(tasks) != 125 or len(set(tasks)) != len(tasks):
        raise ValueError("coverage survey grid changed")
    grouped = _survey_grid(rows, tasks)
    eligible, metadata = _eligible_survey_tasks(tasks, grouped)
    eligible_tuple = tuple(eligible)
    if eligible_tuple != ELIGIBLE_TASKS:
        raise ValueError(f"outcome-free eligible task population changed: {eligible_tuple!r}")
    new_template_exact = _new_template_tasks(eligible_tuple, metadata)
    if new_template_exact != NEW_TEMPLATE_EXACT_TASKS:
        raise ValueError("new-template exact-task population changed")
    grouped_new: dict[str, list[str]] = defaultdict(list)
    for task in new_template_exact:
        grouped_new[str(metadata[task]["template_group"])].append(task)
    primary = tuple((min(grouped_new[template]) for template in sorted(grouped_new)))
    if primary != PRIMARY_TASKS:
        raise ValueError("canonical primary task population changed")
    return {
        "selection_rule": {
            "survey_seeds": list(SURVEY_SEEDS),
            "requires_reset_success_on_every_survey_seed": True,
            "requires_zero_environment_steps": True,
            "requires_reset_info_ignored": True,
            "requires_method_task_id_hidden": True,
            "requires_first_envelope_transact_on_every_survey_seed": True,
            "requires_typed_candidate_on_every_survey_seed": True,
            "excluded_prior_exact_tasks": list(PRIOR_EXACT_TASKS),
            "template_suffixes": list(VARIANT_SUFFIXES),
            "primary_canonical_rule": "lexicographically_first_eligible_exact_task_per_new_template",
            "outcome_based_exclusion_allowed": False,
        },
        "eligible_exact_tasks": list(eligible_tuple),
        "new_template_exact_tasks": list(new_template_exact),
        "primary_tasks": list(primary),
        "seen_template_new_exact_tasks": [task for task in eligible_tuple if task not in new_template_exact],
        "new_template_groups": sorted(grouped_new),
        "task_metadata": {task: metadata[task] for task in eligible_tuple},
    }


def _runtime_halt(row: dict[str, Any]) -> bool:
    return bool(row.get("metrics", {}).get("runtime_halted"))


def _closed_success(row: dict[str, Any]) -> bool:
    return bool(row.get("success")) and _active_count(row) == 0 and (not _runtime_halt(row))


def _failed_stop_stranding(row: dict[str, Any]) -> bool:
    return not bool(row.get("success")) and _active_count(row) > 0


def _all_restorations_pass(row: dict[str, Any]) -> bool:
    pairs = (
        ("restoration_attempts", "restoration_passes"),
        ("interrupt_clearance_restoration_attempts_v16", "interrupt_clearance_restoration_passes_v16"),
        ("proposal_clearance_restoration_attempts_v16", "proposal_clearance_restoration_passes_v16"),
        (
            "active_restore_clearance_restoration_attempts_v16",
            "active_restore_clearance_restoration_passes_v16",
        ),
    )
    return all((_metric(row, passed) == _metric(row, attempted) for attempted, passed in pairs))


def _reserve_rejections(row: dict[str, Any]) -> int:
    return sum(
        (
            event.get("type") == RESERVATION_EVENT_V18
            and event.get("reservation_rule") == "stack_wide"
            and (event.get("allowed") is False)
            for event in row.get("trace", ())
        )
    )


def _nested_admissions(row: dict[str, Any]) -> int:
    return sum(
        (
            event.get("type") == RESERVATION_EVENT_V18
            and event.get("reservation_rule") == "stack_wide"
            and (event.get("decision") == "transact")
            and (int(event.get("registered_active_inverse_cost", 0)) > 0)
            and (event.get("allowed") is True)
            for event in row.get("trace", ())
        )
    )


def _single_cap_rejections(row: dict[str, Any]) -> int:
    return sum(
        (
            event.get("type") == SINGLE_OBLIGATION_POLICY_EVENT_V19
            and event.get("decision") == "transact"
            and (event.get("allowed") is False)
            and (event.get("delegated_to_stack_wide_reserve") is False)
            for event in row.get("trace", ())
        )
    )


def summarize_rows(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    rows = tuple(rows)
    return _summarize_rows_summary_record(rows=rows)


def _seed_cluster_comparison(rows: tuple[dict[str, Any], ...], tasks: tuple[str, ...]) -> dict[str, Any]:
    seed_rows = []
    wins = losses = ties = 0
    for seed in SEEDS:
        full = sum(
            (
                _closed_success(row)
                for row in rows
                if row.get("episode", {}).get("seed") == seed
                and row.get("episode", {}).get("task") in tasks
                and (row.get("episode", {}).get("method") == FULL_METHOD)
            )
        )
        safe = sum(
            (
                _closed_success(row)
                for row in rows
                if row.get("episode", {}).get("seed") == seed
                and row.get("episode", {}).get("task") in tasks
                and (row.get("episode", {}).get("method") == SAFE_BASELINE)
            )
        )
        wins += full > safe
        losses += full < safe
        ties += full == safe
        seed_rows.append({"seed": seed, "full_closed": full, "safe_closed": safe, "difference": full - safe})
    return {
        "seed_cluster_wins": wins,
        "seed_cluster_losses": losses,
        "seed_cluster_ties": ties,
        "two_sided_exact_sign_p": exact_mcnemar(wins, losses),
        "seed_rows": seed_rows,
    }


def _paired_comparison(
    rows: tuple[dict[str, Any], ...], tasks: tuple[str, ...], *, bootstrap_seed: int
) -> dict[str, Any]:
    task_set = set(tasks)
    normalized = [
        {
            "method": row.get("episode", {}).get("method"),
            "task": row.get("episode", {}).get("task"),
            "seed": row.get("episode", {}).get("seed"),
            "success": _closed_success(row),
            "infrastructure_failure": bool(row.get("infrastructure_failure")),
        }
        for row in rows
        if row.get("episode", {}).get("task") in task_set
    ]
    return {
        "tasks": list(tasks),
        "seed_cluster_primary": _seed_cluster_comparison(rows, tasks),
        "paired_cell_sensitivity_and_seed_bootstrap": paired_binary_comparison(
            normalized,
            full_method=FULL_METHOD,
            baseline=SAFE_BASELINE,
            bootstrap_samples=BOOTSTRAP_SAMPLES,
            bootstrap_seed=bootstrap_seed,
        ),
    }


def analyze_rows(
    rows: Iterable[dict[str, Any]], protocol: dict[str, Any], *, all_claims_complete: bool
) -> dict[str, Any]:
    validate_protocol(protocol)
    rows = tuple(rows)
    manifest = episode_manifest(protocol)
    exact_manifest = matches_registered_grid(rows, manifest)
    metrics = {
        arm: summarize_rows((row for row in rows if row.get("episode", {}).get("method") == arm))
        for arm in ARMS
    }
    full = metrics[FULL_METHOD]
    safe = metrics[SAFE_BASELINE]
    checks = _rows_confirmation_checks(
        all_claims_complete=all_claims_complete,
        exact_manifest=exact_manifest,
        full=full,
        metrics=metrics,
        protocol=protocol,
        rows=rows,
        safe=safe,
    )
    by_task = _analyze_rows_by_task(protocol=protocol, rows=rows)
    comparisons = None
    if exact_manifest and (not any((bool(row.get("infrastructure_failure")) for row in rows))):
        comparisons = {
            "primary_canonical_new_templates": _paired_comparison(
                rows, PRIMARY_TASKS, bootstrap_seed=BOOTSTRAP_SEED
            ),
            "secondary_all_new_template_exact_tasks": _paired_comparison(
                rows, NEW_TEMPLATE_EXACT_TASKS, bootstrap_seed=BOOTSTRAP_SEED + 1
            ),
            "secondary_all_eligible_exact_tasks": _paired_comparison(
                rows, ELIGIBLE_TASKS, bootstrap_seed=BOOTSTRAP_SEED + 2
            ),
        }
    return {
        "claim_status": PURPOSE["claim_status"],
        "confirmation_status": PURPOSE["confirmation_status"],
        "exact_manifest": exact_manifest,
        "all_claims_complete": all_claims_complete,
        "metrics": metrics,
        "paired_stack_vs_safe_closed_success": comparisons["primary_canonical_new_templates"]
        if comparisons is not None
        else None,
        "comparisons": comparisons,
        "by_task": by_task,
        "checks": checks,
        "passed": all(checks.values()),
    }


__all__ = [
    "ARMS",
    "CANDIDATE",
    "COVERAGE_SURVEY",
    "DECISION_RULE",
    "DRIVERS",
    "ELIGIBLE_TASKS",
    "FULL_METHOD",
    "NEW_TEMPLATE_EXACT_TASKS",
    "PRIMARY_ANALYSIS",
    "PRIMARY_TASKS",
    "PURPOSE",
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
    "normalize_task_template",
    "summarize_rows",
    "validate_population",
    "validate_protocol",
]


def _rows_confirmation_checks(
    *,
    all_claims_complete: bool,
    exact_manifest: bool,
    full: Any,
    metrics: Any,
    protocol: Any,
    rows: tuple[dict[str, Any], ...],
    safe: Any,
) -> dict[str, bool]:
    """Apply the registered decision gates to computed outcomes."""
    return {
        "complete_exact_grid": exact_manifest and all_claims_complete,
        "zero_infrastructure_failures": all(
            (values["infrastructure_failures"] == 0 for values in metrics.values())
        ),
        "planner_is_exercised": sum((values["planner_actual_calls"] for values in metrics.values())) > 0,
        "all_rows_respect_hard_budgets": _all_rows_respect_budgets(rows, protocol),
        "both_policies_zero_failed_stop_stranding": all(
            (values["failed_stop_stranding_episodes"] == 0 for values in metrics.values())
        ),
        "both_policies_zero_runtime_halts": all(
            (values["runtime_halt_episodes"] == 0 for values in metrics.values())
        ),
        "all_restoration_attempts_pass": all(
            (values["rows_with_failed_restoration"] == 0 for values in metrics.values())
        ),
        "both_policies_zero_v19_scope_failures": all(
            (values["certified_scope_consumption_failures_v19"] == 0 for values in metrics.values())
        ),
        "all_successes_are_closed": all(
            (values["closed_successes"] == values["task_successes"] for values in metrics.values())
        ),
        "full_method_nested_admission_activates": full["nested_admissions"] > 0,
        "safe_baseline_cap_activates": safe["single_active_cap_rejections"] > 0,
    }


def _summarize_rows_summary_record(*, rows: Any) -> dict[str, Any]:
    """Compute summary record from explicit study inputs."""
    return {
        "episodes": len(rows),
        "task_successes": sum((bool(row.get("success")) for row in rows)),
        "closed_successes": sum((_closed_success(row) for row in rows)),
        "closed_success_templates": len(
            {str(row.get("episode", {}).get("family_group")) for row in rows if _closed_success(row)}
        ),
        "successes_with_active_obligations": sum(
            (bool(row.get("success")) and _active_count(row) > 0 for row in rows)
        ),
        "failed_stop_stranding_episodes": sum((_failed_stop_stranding(row) for row in rows)),
        "runtime_halt_episodes": sum((_runtime_halt(row) for row in rows)),
        "rows_with_failed_restoration": sum((not _all_restorations_pass(row) for row in rows)),
        "reserve_rejections": sum((_reserve_rejections(row) for row in rows)),
        "nested_admissions": sum((_nested_admissions(row) for row in rows)),
        "single_active_cap_rejections": sum((_single_cap_rejections(row) for row in rows)),
        "goal_mutation_consumption_passes_v19": sum(
            (_metric(row, "goal_mutation_consumption_passes_v19") for row in rows)
        ),
        "certified_scope_consumption_failures_v19": sum(
            (_metric(row, "certified_scope_consumption_failures_v19") for row in rows)
        ),
        "top_cleanup_attempts": sum((_metric(row, "top_cleanup_attempts") for row in rows)),
        "top_cleanup_passes": sum((_metric(row, "top_cleanup_passes") for row in rows)),
        "top_cleanup_failures": sum((_metric(row, "top_cleanup_failures") for row in rows)),
        "gui_actions": sum((_metric(row, "gui_actions") for row in rows)),
        "typed_transactions": sum((_metric(row, "typed_transactions") for row in rows)),
        "planner_calls": sum((_metric(row, "planner_calls") for row in rows)),
        "planner_actual_calls": sum((_metric(row, "planner_actual_calls") for row in rows)),
        "infrastructure_failures": sum((bool(row.get("infrastructure_failure")) for row in rows)),
    }


def _analyze_rows_by_task(*, protocol: Any, rows: Any) -> Any:
    """Compute by task from explicit study inputs."""
    return [
        {
            "task": task,
            "template_group": protocol["population"]["task_metadata"][task]["template_group"],
            "primary_population": task in PRIMARY_TASKS,
            "new_template_population": task in NEW_TEMPLATE_EXACT_TASKS,
            "arms": {
                arm: summarize_rows(
                    (
                        row
                        for row in rows
                        if row.get("episode", {}).get("task") == task
                        and row.get("episode", {}).get("method") == arm
                    )
                )
                for arm in ARMS
            },
        }
        for task in ELIGIBLE_TASKS
    ]


def _survey_grid(rows: list[dict[str, Any]], tasks: list[str]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    forbidden_outcome_keys = {
        "success",
        "reward",
        "terminated",
        "truncated",
        "evaluator",
        "evaluation",
        "reset_info",
    }
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("coverage survey contains a non-object row")
        if forbidden_outcome_keys & set(row):
            raise ValueError("coverage survey contains a forbidden outcome field")
        task = str(row.get("task", ""))
        if task not in tasks:
            raise ValueError("coverage survey contains an unknown task")
        grouped[task].append(row)
    if set(grouped) != set(tasks):
        raise ValueError("coverage survey task set changed")
    return grouped


def _eligible_survey_tasks(
    tasks: list[str], grouped: dict[str, list[dict[str, Any]]]
) -> tuple[list[str], dict[str, dict[str, Any]]]:
    prior_templates = {normalize_task_template(task) for task in PRIOR_EXACT_TASKS}
    metadata: dict[str, dict[str, Any]] = {}
    eligible = []
    for task in sorted(tasks):
        task_rows = sorted(grouped[task], key=lambda row: int(row["seed"]))
        if _survey_task_integrity_failed(task_rows):
            raise ValueError(f"coverage survey integrity failed for {task}")
        transaction_kinds = sorted(
            {str(kind) for row in task_rows for kind in row.get("transaction_kinds", ())}
        )
        qualifies = (
            task not in PRIOR_EXACT_TASKS
            and all((row.get("envelope", {}).get("decision") == "transact" for row in task_rows))
            and all((int(row.get("transaction_candidate_count", 0)) >= 1 for row in task_rows))
        )
        if qualifies:
            template = normalize_task_template(task)
            eligible.append(task)
            metadata[task] = {
                "task_id": task,
                "template_group": template,
                "template_status": "seen_template_new_exact_task"
                if template in prior_templates
                else "new_template_new_exact_task",
                "transaction_kinds": transaction_kinds,
                "minimum_initial_transaction_candidates": min(
                    (int(row["transaction_candidate_count"]) for row in task_rows)
                ),
                "maximum_initial_transaction_candidates": max(
                    (int(row["transaction_candidate_count"]) for row in task_rows)
                ),
            }
    return (eligible, metadata)


def _survey_task_integrity_failed(task_rows: list[dict[str, Any]]) -> bool:
    return (
        tuple((int(row.get("seed", -1)) for row in task_rows)) != SURVEY_SEEDS
        or any((row.get("reset_succeeded") is not True for row in task_rows))
        or any((int(row.get("environment_step_calls", -1)) != 0 for row in task_rows))
        or any((row.get("reset_info_ignored") is not True for row in task_rows))
        or any((row.get("method_received_task_id") is not False for row in task_rows))
    )


def _survey_identity_changed(survey: dict[str, Any]) -> bool:
    return (
        survey.get("candidate") != "InverseReserve-MiniWoB-public-input-coverage-survey-v1"
        or survey.get("claim_status") != "development_only_no_task_outcomes"
        or tuple(survey.get("seeds", ())) != SURVEY_SEEDS
        or (survey.get("summary", {}).get("tasks") != 125)
        or (survey.get("summary", {}).get("cells") != 250)
        or (survey.get("summary", {}).get("reset_failures") != 0)
    )


def _new_template_tasks(
    eligible_tuple: tuple[str, ...], metadata: dict[str, dict[str, Any]]
) -> tuple[str, ...]:
    return tuple(
        (
            task
            for task in eligible_tuple
            if metadata[task]["template_status"] == "new_template_new_exact_task"
        )
    )
