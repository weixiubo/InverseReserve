from __future__ import annotations

from collections import Counter
from typing import Any, Iterable

from inversereserve.controllers.capacity_reserve_drivers_v20 import (
    SINGLE_ACTIVE_OBLIGATION_V20,
    SINGLE_OBLIGATION_POLICY_EVENT_V20,
    TOP_CLEANUP_REPLAN_V20,
    SingleActiveObligationDriverV20,
    TopCleanupReplanDriverV20,
)
from inversereserve.studies import inversereserve_miniwob_transfer_v1 as v1
from inversereserve.studies.episode_grid import matches_registered_grid
from inversereserve.studies.external_statistics import exact_mcnemar
from inversereserve.studies.inversereserve_capacity_regime_successor_v3 import _all_rows_respect_budgets
from inversereserve.studies.inversereserve_cross_planner_replication_v1 import GENERATION as GENERATION
from inversereserve.studies.inversereserve_cross_planner_replication_v1 import PLANNER_MODEL as PLANNER_MODEL
from inversereserve.studies.inversereserve_cross_planner_replication_v1 import (
    RUNTIME_DEPLOYMENT as RUNTIME_DEPLOYMENT,
)
from inversereserve.studies.inversereserve_live_resource_stress_v1 import _active_count, _metric
from inversereserve.studies.pact_statistics import paired_binary_comparison
from inversereserve.studies.validation import require

"Frozen outcome-informed MiniWoB++ interface-completion study."
CANDIDATE = "InverseReserve-miniwob-interface-completion-v2"
STATUS = "frozen_after_outcome_informed_generic_v20_development_before_any_37201_through_37220_reset"
FULL_METHOD = TOP_CLEANUP_REPLAN_V20
SAFE_BASELINE = SINGLE_ACTIVE_OBLIGATION_V20
ARMS = (FULL_METHOD, SAFE_BASELINE)
DRIVERS = {FULL_METHOD: TopCleanupReplanDriverV20, SAFE_BASELINE: SingleActiveObligationDriverV20}
SEEDS = tuple(range(37201, 37221))
MAXIMUM_GUI_ACTIONS = 32
COMMON_BUDGETS = {"maximum_planner_calls": 40, "maximum_wall_seconds": 300.0}
BOOTSTRAP_SAMPLES = 50000
BOOTSTRAP_SEED = 270734
ALPHA = 0.05
PREREGISTRATION = {
    "path": "paper/aaai27/notes/2026-07-23_inversereserve_miniwob_transfer_v2_preregistration.md",
    "sha256": "b33037e5542bb4570126a4ab6f615483a4eee7b7df420111423efbfaee5d5b1e",
}
COVERAGE_SURVEY = dict(v1.COVERAGE_SURVEY)
DEVELOPMENT_RECORD = {
    "path": "validation/inversereserve_pact_v20_development_v1.json",
    "sha256": "05381dcfde9b93443c3da6f79d73929705a9eb40a92ee0a5cd47ec8f5fca3649",
    "source_commit": "4a1582563f6d41d584f6b9fa1ba85a506c1aa4aa",
    "status": "complete_outcome_informed_development",
    "paper_evidence_allowed": False,
}
SURVEY_SEEDS = v1.SURVEY_SEEDS
PRIOR_EXACT_TASKS = v1.PRIOR_EXACT_TASKS
VARIANT_SUFFIXES = v1.VARIANT_SUFFIXES
ELIGIBLE_TASKS = v1.ELIGIBLE_TASKS
NEW_TEMPLATE_EXACT_TASKS = v1.NEW_TEMPLATE_EXACT_TASKS
PRIMARY_TASKS = v1.PRIMARY_TASKS
INTERFACE_COMPLETION = {
    "development_status": "outcome_informed_from_sealed_invalid_transfer_v1",
    "shared_by_both_arms": True,
    "task_identifiers_or_selectors_used": False,
    "rules": [
        "for an explicit public terminal-intent goal, defer exact-target alias promotion while a typed prerequisite remains unopened",
        "consume a certificate-bound contiguous navigation suffix only after an effective exact-target commit",
        "suppress repeated navigation by public semantic identity",
        "restore the active top and replan before navigation outside its public transaction frame",
    ],
}
PURPOSE = {
    "claim_status": "outcome_informed_fresh_seed_interface_completion",
    "confirmation_status": "not_independent_confirmation",
    "selection_status": "task population fixed outcome-free before transfer v1; no task added or removed after v1 outcomes",
    "question": "whether the retained opportunity-preserving policy remains useful after generic public-interface completion on fresh seeds",
    "outcome_based_exclusion_allowed": False,
}
OUTCOME_DEFINITIONS = {
    **v1.OUTCOME_DEFINITIONS,
    "v20_scope_failure": "a certificate-bound resolved scope is not one supported contiguous active-stack suffix",
    "goal_terminal_promotion": "a unique public exact target uses the public terminal-intent prerequisite guard before promotion",
    "frame_cleanup": "verified top restoration followed by replanning before an out-of-frame navigation proposal",
}
PRIMARY_ANALYSIS = {
    **v1.PRIMARY_ANALYSIS,
    "full_method": FULL_METHOD,
    "baseline": SAFE_BASELINE,
    "bootstrap_seed": BOOTSTRAP_SEED,
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
    "goal_navigation_consumption_activates": True,
    "frame_cleanup_activates_without_failure": True,
}
DECISION_RULE = {
    "on_pass": "report the complete outcome-informed fresh-seed comparison regardless of effect direction",
    "on_failure": "seal every opened row, report failed validity gates, and make no positive fresh-seed interface-completion claim",
}


def normalize_task_template(task: str) -> str:
    return v1.normalize_task_template(task)


def derive_population(survey: dict[str, Any]) -> dict[str, Any]:
    return v1.derive_population(survey)


def validate_population(population: dict[str, Any]) -> None:
    v1.validate_population(population)


def task_records(population: dict[str, Any]) -> list[dict[str, Any]]:
    validate_population(population)
    return [
        {
            **population["task_metadata"][task],
            "primary_population": task in PRIMARY_TASKS,
            "new_template_population": task in NEW_TEMPLATE_EXACT_TASKS,
            "maximum_gui_actions": MAXIMUM_GUI_ACTIONS,
        }
        for task in ELIGIBLE_TASKS
    ]


def expected_episodes() -> int:
    return len(ARMS) * len(SEEDS) * len(ELIGIBLE_TASKS)


def build_protocol(
    *,
    scientific_source_commit: str,
    source_sha256: dict[str, str],
    predecessor: dict[str, Any],
    repositories: dict[str, str],
    population: dict[str, Any],
    survey_binding: dict[str, Any],
    created_utc: str,
) -> dict[str, Any]:
    validate_population(population)
    if survey_binding != COVERAGE_SURVEY:
        raise ValueError("coverage survey binding changed")
    protocol = {
        "candidate": CANDIDATE,
        "status": STATUS,
        "created_utc": created_utc,
        "scientific_source_commit": scientific_source_commit,
        "preregistration": dict(PREREGISTRATION),
        "predecessor": predecessor,
        "purpose": dict(PURPOSE),
        "coverage_survey": dict(COVERAGE_SURVEY),
        "development_record": dict(DEVELOPMENT_RECORD),
        "population": population,
        "interface_completion": {**INTERFACE_COMPLETION, "rules": list(INTERFACE_COMPLETION["rules"])},
        "arms": list(ARMS),
        "isolated_policy_difference": "both arms share PACT-v20 contracts, public-interface completion, stack-wide capacity accounting, planner, executor, restoration, and verification; the baseline alone refuses a second simultaneous typed obligation",
        "tasks": task_records(population),
        "fresh_seeds": list(SEEDS),
        "maximum_gui_actions": MAXIMUM_GUI_ACTIONS,
        "common_budgets": dict(COMMON_BUDGETS),
        "generation": dict(GENERATION),
        "runtime_deployment": dict(RUNTIME_DEPLOYMENT),
        "planner_model": {
            **PLANNER_MODEL,
            "snapshot_files_sha256": dict(PLANNER_MODEL["snapshot_files_sha256"]),
        },
        "expected_episodes": expected_episodes(),
        "outcome_definitions": dict(OUTCOME_DEFINITIONS),
        "primary_analysis": dict(PRIMARY_ANALYSIS),
        "validity_gates": dict(VALIDITY_GATES),
        "decision_rule": dict(DECISION_RULE),
        "repositories": dict(repositories),
        "source_sha256": dict(sorted(source_sha256.items())),
        "outcome_based_exclusion_allowed": False,
        "partial_reexecution_allowed": False,
        "completed_episode_replay_allowed": False,
    }
    validate_protocol(protocol)
    return protocol


def validate_protocol(protocol: dict[str, Any]) -> None:
    require(
        not (protocol.get("candidate") != CANDIDATE or protocol.get("status") != STATUS),
        "unexpected interface-completion identity",
    )
    population = protocol.get("population")
    require(isinstance(population, dict), "interface-completion population is absent")
    validate_population(population)
    require(
        not (tuple(protocol.get("arms", ())) != ARMS or set(DRIVERS) != set(ARMS)),
        "interface-completion arms changed",
    )
    require(
        not protocol.get("tasks") != task_records(population), "interface-completion task records changed"
    )
    require(not tuple(protocol.get("fresh_seeds", ())) != SEEDS, "interface-completion seeds changed")
    require(
        not protocol.get("maximum_gui_actions") != MAXIMUM_GUI_ACTIONS,
        "interface-completion action horizon changed",
    )
    fixed = {
        "preregistration": PREREGISTRATION,
        "purpose": PURPOSE,
        "coverage_survey": COVERAGE_SURVEY,
        "development_record": DEVELOPMENT_RECORD,
        "interface_completion": INTERFACE_COMPLETION,
        "common_budgets": COMMON_BUDGETS,
        "generation": GENERATION,
        "runtime_deployment": RUNTIME_DEPLOYMENT,
        "planner_model": PLANNER_MODEL,
        "outcome_definitions": OUTCOME_DEFINITIONS,
        "primary_analysis": PRIMARY_ANALYSIS,
        "validity_gates": VALIDITY_GATES,
        "decision_rule": DECISION_RULE,
    }
    for key, expected in fixed.items():
        if protocol.get(key) != expected:
            raise ValueError(f"interface-completion {key} changed")
    require(
        not protocol.get("expected_episodes") != expected_episodes(),
        "interface-completion episode count changed",
    )
    for key in ("predecessor", "repositories", "source_sha256"):
        if not isinstance(protocol.get(key), dict):
            raise ValueError(f"interface-completion {key} binding is absent")
    for key in (
        "outcome_based_exclusion_allowed",
        "partial_reexecution_allowed",
        "completed_episode_replay_allowed",
    ):
        if protocol.get(key) is not False:
            raise ValueError(f"interface-completion {key} changed")


def episode_manifest(protocol: dict[str, Any]) -> list[dict[str, Any]]:
    validate_protocol(protocol)
    metadata = protocol["population"]["task_metadata"]
    rows: list[dict[str, Any]] = []
    for seed_index, seed in enumerate(SEEDS):
        for task_index, task in enumerate(ELIGIBLE_TASKS):
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
                        "primary_population": task in PRIMARY_TASKS,
                        "new_template_population": task in NEW_TEMPLATE_EXACT_TASKS,
                        "budget_level": "uniform_ample",
                        "seed": seed,
                        "maximum_gui_actions": MAXIMUM_GUI_ACTIONS,
                        "method": method,
                        "episode_id": f"{task}__seed{seed}__a{MAXIMUM_GUI_ACTIONS}__{method}",
                    }
                )
    if len(rows) != expected_episodes():
        raise ValueError("interface-completion manifest size changed")
    return rows


def arm_order_counts(protocol: dict[str, Any]) -> dict[str, dict[int, int]]:
    counts = Counter(((row["method"], row["arm_position"]) for row in episode_manifest(protocol)))
    return {method: {position: counts[method, position] for position in range(len(ARMS))} for method in ARMS}


def _single_cap_rejections(row: dict[str, Any]) -> int:
    return sum(
        (
            event.get("type") == SINGLE_OBLIGATION_POLICY_EVENT_V20
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
                v1._closed_success(row)
                for row in rows
                if row.get("episode", {}).get("seed") == seed
                and row.get("episode", {}).get("task") in tasks
                and (row.get("episode", {}).get("method") == FULL_METHOD)
            )
        )
        safe = sum(
            (
                v1._closed_success(row)
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
            "success": v1._closed_success(row),
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
    totals = {
        key: sum((values[key] for values in metrics.values()))
        for key in (
            "goal_terminal_promotions_v20",
            "goal_navigation_consumption_passes_v20",
            "frame_cleanup_passes_v20",
            "frame_cleanup_failures_v20",
        )
    }
    checks = _rows_confirmation_checks(
        all_claims_complete=all_claims_complete,
        exact_manifest=exact_manifest,
        full=full,
        metrics=metrics,
        protocol=protocol,
        rows=rows,
        safe=safe,
        totals=totals,
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
    "DEVELOPMENT_RECORD",
    "DRIVERS",
    "ELIGIBLE_TASKS",
    "FULL_METHOD",
    "INTERFACE_COMPLETION",
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
    totals: Any,
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
        "both_policies_zero_v20_scope_failures": all(
            (values["certified_scope_consumption_failures_v20"] == 0 for values in metrics.values())
        ),
        "all_successes_are_closed": all(
            (values["closed_successes"] == values["task_successes"] for values in metrics.values())
        ),
        "full_method_nested_admission_activates": full["nested_admissions"] > 0,
        "safe_baseline_cap_activates": safe["single_active_cap_rejections"] > 0,
        "goal_terminal_promotion_activates": totals["goal_terminal_promotions_v20"] > 0,
        "goal_navigation_consumption_activates": totals["goal_navigation_consumption_passes_v20"] > 0,
        "frame_cleanup_activates_without_failure": totals["frame_cleanup_passes_v20"] > 0
        and totals["frame_cleanup_failures_v20"] == 0,
    }


def _summarize_rows_summary_record(*, rows: Any) -> dict[str, Any]:
    """Compute summary record from explicit study inputs."""
    return {
        "episodes": len(rows),
        "task_successes": sum((bool(row.get("success")) for row in rows)),
        "closed_successes": sum((v1._closed_success(row) for row in rows)),
        "closed_success_templates": len(
            {str(row.get("episode", {}).get("family_group")) for row in rows if v1._closed_success(row)}
        ),
        "successes_with_active_obligations": sum(
            (bool(row.get("success")) and _active_count(row) > 0 for row in rows)
        ),
        "failed_stop_stranding_episodes": sum((v1._failed_stop_stranding(row) for row in rows)),
        "runtime_halt_episodes": sum((v1._runtime_halt(row) for row in rows)),
        "rows_with_failed_restoration": sum((not v1._all_restorations_pass(row) for row in rows)),
        "reserve_rejections": sum((v1._reserve_rejections(row) for row in rows)),
        "nested_admissions": sum((v1._nested_admissions(row) for row in rows)),
        "single_active_cap_rejections": sum((_single_cap_rejections(row) for row in rows)),
        "certified_scope_consumption_failures_v20": sum(
            (_metric(row, "certified_scope_consumption_failures_v20") for row in rows)
        ),
        "goal_navigation_consumption_passes_v20": sum(
            (_metric(row, "goal_navigation_consumption_passes_v20") for row in rows)
        ),
        "goal_mutation_consumption_passes_v20": sum(
            (_metric(row, "goal_mutation_consumption_passes_v20") for row in rows)
        ),
        "goal_terminal_promotions_v20": sum((_metric(row, "goal_terminal_promotions_v20") for row in rows)),
        "frame_cleanup_attempts_v20": sum((_metric(row, "frame_cleanup_attempts_v20") for row in rows)),
        "frame_cleanup_passes_v20": sum((_metric(row, "frame_cleanup_passes_v20") for row in rows)),
        "frame_cleanup_failures_v20": sum((_metric(row, "frame_cleanup_failures_v20") for row in rows)),
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
