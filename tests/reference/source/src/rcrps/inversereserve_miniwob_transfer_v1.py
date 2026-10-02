"""Frozen outcome-blind MiniWoB++ task-transfer study for InverseReserve."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, Iterable

from .capacity_reserve_drivers_v18 import RESERVATION_EVENT_V18
from .capacity_reserve_drivers_v19 import (
    SINGLE_ACTIVE_OBLIGATION_V19,
    SINGLE_OBLIGATION_POLICY_EVENT_V19,
    SingleActiveObligationDriverV19,
)
from .capacity_safe_dynamic_controls_v19 import (
    TOP_CLEANUP_REPLAN_V19,
    TopCleanupReplanDriverV19,
)
from .external_statistics import exact_mcnemar
from .inversereserve_capacity_regime_successor_v3 import (
    _all_rows_respect_budgets,
)
from .inversereserve_cross_planner_replication_v1 import (
    GENERATION,
    PLANNER_MODEL,
    RUNTIME_DEPLOYMENT,
)
from .inversereserve_live_resource_stress_v1 import _active_count, _metric
from .pact_statistics import paired_binary_comparison


CANDIDATE = "InverseReserve-miniwob-task-transfer-v1"
STATUS = "frozen_after_outcome_free_survey_before_any_37101_through_37120_reset"
FULL_METHOD = TOP_CLEANUP_REPLAN_V19
SAFE_BASELINE = SINGLE_ACTIVE_OBLIGATION_V19
ARMS = (FULL_METHOD, SAFE_BASELINE)
DRIVERS = {
    FULL_METHOD: TopCleanupReplanDriverV19,
    SAFE_BASELINE: SingleActiveObligationDriverV19,
}
SURVEY_SEEDS = (37001, 37002)
SEEDS = tuple(range(37101, 37121))
MAXIMUM_GUI_ACTIONS = 32
COMMON_BUDGETS = {
    "maximum_planner_calls": 40,
    "maximum_wall_seconds": 300.0,
}
BOOTSTRAP_SAMPLES = 50_000
BOOTSTRAP_SEED = 270_733
ALPHA = 0.05
PREREGISTRATION = {
    "path": (
        "paper/aaai27/notes/"
        "2026-07-23_inversereserve_miniwob_transfer_v1_preregistration.md"
    ),
    "sha256": (
        "62c404873add63ecb332676295797a8ff40b5b49e358b63e224c245b5735a8a2"
    ),
}
COVERAGE_SURVEY = {
    "path": (
        "validation/"
        "inversereserve_miniwob_public_input_coverage_survey_v1.json"
    ),
    "sha256": (
        "f8268eb6c51ec481faebf9a527e0fca4c5920d0cc0e5526908b58378d159e7ef"
    ),
    "source_commit": "c6eded46b099b2e5eebdff791adcd0907ae89a23",
    "source_script": "scripts/inversereserve_miniwob_coverage_survey.py",
    "source_script_sha256": (
        "44264458c81ee0199f28b2ecd2f6865ac6ee3cbd775faf834ad1264a9c0efc2b"
    ),
}
PRIOR_EXACT_TASKS = (
    "book-flight-nodelay",
    "choose-date-nodelay",
    "click-scroll-list",
    "click-widget",
    "login-user-popup",
    "use-autocomplete-nodelay",
)
VARIANT_SUFFIXES = (
    "-nodelay",
    "-easy",
    "-medium",
    "-hard",
    "-popup",
    "-2",
)
ELIGIBLE_TASKS = (
    "book-flight",
    "choose-date",
    "choose-date-easy",
    "choose-date-medium",
    "click-collapsible",
    "click-collapsible-2",
    "click-collapsible-2-nodelay",
    "click-collapsible-nodelay",
    "click-menu",
    "click-tab-2",
    "enter-password",
    "login-user",
    "navigate-tree",
    "use-autocomplete",
)
NEW_TEMPLATE_EXACT_TASKS = (
    "click-collapsible",
    "click-collapsible-2",
    "click-collapsible-2-nodelay",
    "click-collapsible-nodelay",
    "click-menu",
    "click-tab-2",
    "enter-password",
    "navigate-tree",
)
PRIMARY_TASKS = (
    "click-collapsible",
    "click-menu",
    "click-tab-2",
    "enter-password",
    "navigate-tree",
)
PURPOSE = {
    "claim_status": "prospective_reviewer_driven_task_transfer",
    "confirmation_status": "not_independent_confirmation",
    "selection_status": (
        "task population fixed only from public inputs before fresh outcomes"
    ),
    "question": (
        "whether the retained InverseReserve policy transfers to exact tasks "
        "and normalized task templates absent from the earlier six-task grid"
    ),
    "outcome_based_exclusion_allowed": False,
}
OUTCOME_DEFINITIONS = {
    "official_task_success": "environment-provided binary task success",
    "closed_success": (
        "official task success with zero active typed obligations and no "
        "runtime halt"
    ),
    "failed_stop_stranding": (
        "task failure with at least one active typed obligation at episode stop"
    ),
    "verified_restoration": (
        "every attempted ordinary or clearance restoration passes"
    ),
    "runtime_halt": "runtime_halted is true in the sealed episode metrics",
    "reporting_rule": (
        "report utility, safety, restoration, policy activation, and work "
        "separately without a composite endpoint"
    ),
}
PRIMARY_ANALYSIS = {
    "endpoint": "closed_success",
    "population": "one canonical exact task per new normalized template",
    "canonical_rule": "lexicographically_first_eligible_exact_task",
    "tasks": list(PRIMARY_TASKS),
    "paired_unit": "task_seed_cell",
    "cluster_unit": "fresh seed shared across all primary tasks",
    "full_method": FULL_METHOD,
    "baseline": SAFE_BASELINE,
    "bootstrap_samples": BOOTSTRAP_SAMPLES,
    "bootstrap_seed": BOOTSTRAP_SEED,
    "seed_aggregate_test": "two_sided_exact_sign",
    "paired_cell_sensitivity": "two_sided_exact_mcnemar",
    "alpha": ALPHA,
    "efficacy_gate": "none_report_complete_comparison_regardless_of_direction",
}
VALIDITY_GATES = {
    "complete_exact_grid": True,
    "zero_infrastructure_failures": True,
    "planner_is_exercised": True,
    "all_rows_respect_hard_budgets": True,
    "both_policies_zero_failed_stop_stranding": True,
    "both_policies_zero_runtime_halts": True,
    "all_restoration_attempts_pass": True,
    "both_policies_zero_v19_scope_failures": True,
    "all_successes_are_closed": True,
    "full_method_nested_admission_activates": True,
    "safe_baseline_cap_activates": True,
}
DECISION_RULE = {
    "on_pass": (
        "report the complete outcome-blind task-transfer comparison regardless "
        "of effect direction"
    ),
    "on_failure": (
        "seal every opened row, report failed validity gates, and make no "
        "positive task-transfer claim"
    ),
}


def normalize_task_template(task: str) -> str:
    """Normalize only the suffixes frozen in the preregistration."""

    normalized = str(task)
    changed = True
    while changed:
        changed = False
        for suffix in VARIANT_SUFFIXES:
            if normalized.endswith(suffix):
                normalized = normalized[: -len(suffix)]
                changed = True
                break
    return normalized


def derive_population(survey: dict[str, Any]) -> dict[str, Any]:
    """Derive the task population without reading any task outcome."""

    if (
        survey.get("candidate")
        != "InverseReserve-MiniWoB-public-input-coverage-survey-v1"
        or survey.get("claim_status") != "development_only_no_task_outcomes"
        or tuple(survey.get("seeds", ())) != SURVEY_SEEDS
        or survey.get("summary", {}).get("tasks") != 125
        or survey.get("summary", {}).get("cells") != 250
        or survey.get("summary", {}).get("reset_failures") != 0
    ):
        raise ValueError("coverage survey identity or completeness changed")
    rows = survey.get("rows")
    tasks = survey.get("tasks")
    if not isinstance(rows, list) or not isinstance(tasks, list):
        raise ValueError("coverage survey task rows are absent")
    if len(rows) != 250 or len(tasks) != 125 or len(set(tasks)) != len(tasks):
        raise ValueError("coverage survey grid changed")

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

    prior_templates = {
        normalize_task_template(task) for task in PRIOR_EXACT_TASKS
    }
    metadata: dict[str, dict[str, Any]] = {}
    eligible = []
    for task in sorted(tasks):
        task_rows = sorted(grouped[task], key=lambda row: int(row["seed"]))
        if (
            tuple(int(row.get("seed", -1)) for row in task_rows) != SURVEY_SEEDS
            or any(row.get("reset_succeeded") is not True for row in task_rows)
            or any(int(row.get("environment_step_calls", -1)) != 0 for row in task_rows)
            or any(row.get("reset_info_ignored") is not True for row in task_rows)
            or any(row.get("method_received_task_id") is not False for row in task_rows)
        ):
            raise ValueError(f"coverage survey integrity failed for {task}")
        transaction_kinds = sorted(
            {
                str(kind)
                for row in task_rows
                for kind in row.get("transaction_kinds", ())
            }
        )
        qualifies = (
            task not in PRIOR_EXACT_TASKS
            and all(
                row.get("envelope", {}).get("decision") == "transact"
                for row in task_rows
            )
            and all(
                int(row.get("transaction_candidate_count", 0)) >= 1
                for row in task_rows
            )
        )
        if qualifies:
            template = normalize_task_template(task)
            eligible.append(task)
            metadata[task] = {
                "task_id": task,
                "template_group": template,
                "template_status": (
                    "seen_template_new_exact_task"
                    if template in prior_templates
                    else "new_template_new_exact_task"
                ),
                "transaction_kinds": transaction_kinds,
                "minimum_initial_transaction_candidates": min(
                    int(row["transaction_candidate_count"]) for row in task_rows
                ),
                "maximum_initial_transaction_candidates": max(
                    int(row["transaction_candidate_count"]) for row in task_rows
                ),
            }

    eligible_tuple = tuple(eligible)
    if eligible_tuple != ELIGIBLE_TASKS:
        raise ValueError(
            "outcome-free eligible task population changed: "
            f"{eligible_tuple!r}"
        )
    new_template_exact = tuple(
        task
        for task in eligible_tuple
        if metadata[task]["template_status"] == "new_template_new_exact_task"
    )
    if new_template_exact != NEW_TEMPLATE_EXACT_TASKS:
        raise ValueError("new-template exact-task population changed")
    grouped_new: dict[str, list[str]] = defaultdict(list)
    for task in new_template_exact:
        grouped_new[str(metadata[task]["template_group"])].append(task)
    primary = tuple(
        min(grouped_new[template]) for template in sorted(grouped_new)
    )
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
            "primary_canonical_rule": (
                "lexicographically_first_eligible_exact_task_per_new_template"
            ),
            "outcome_based_exclusion_allowed": False,
        },
        "eligible_exact_tasks": list(eligible_tuple),
        "new_template_exact_tasks": list(new_template_exact),
        "primary_tasks": list(primary),
        "seen_template_new_exact_tasks": [
            task for task in eligible_tuple if task not in new_template_exact
        ],
        "new_template_groups": sorted(grouped_new),
        "task_metadata": {
            task: metadata[task] for task in eligible_tuple
        },
    }


def validate_population(population: dict[str, Any]) -> None:
    if (
        tuple(population.get("eligible_exact_tasks", ())) != ELIGIBLE_TASKS
        or tuple(population.get("new_template_exact_tasks", ()))
        != NEW_TEMPLATE_EXACT_TASKS
        or tuple(population.get("primary_tasks", ())) != PRIMARY_TASKS
    ):
        raise ValueError("task-transfer population changed")
    metadata = population.get("task_metadata")
    if not isinstance(metadata, dict) or set(metadata) != set(ELIGIBLE_TASKS):
        raise ValueError("task-transfer metadata changed")
    for task in ELIGIBLE_TASKS:
        record = metadata[task]
        if (
            record.get("task_id") != task
            or record.get("template_group") != normalize_task_template(task)
            or not isinstance(record.get("transaction_kinds"), list)
            or int(record.get("minimum_initial_transaction_candidates", 0)) < 1
        ):
            raise ValueError(f"task-transfer metadata changed for {task}")
    if population.get("selection_rule", {}).get(
        "outcome_based_exclusion_allowed"
    ) is not False:
        raise ValueError("task-transfer outcome exclusion rule changed")


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
        "population": population,
        "arms": list(ARMS),
        "isolated_policy_difference": (
            "both arms share PACT-v19 contracts, stack-wide capacity "
            "accounting, planner, executor, and verification; the baseline "
            "alone refuses a second simultaneous typed obligation"
        ),
        "tasks": task_records(population),
        "fresh_seeds": list(SEEDS),
        "maximum_gui_actions": MAXIMUM_GUI_ACTIONS,
        "common_budgets": dict(COMMON_BUDGETS),
        "generation": dict(GENERATION),
        "runtime_deployment": dict(RUNTIME_DEPLOYMENT),
        "planner_model": {
            **PLANNER_MODEL,
            "snapshot_files_sha256": dict(
                PLANNER_MODEL["snapshot_files_sha256"]
            ),
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
    if protocol.get("candidate") != CANDIDATE or protocol.get("status") != STATUS:
        raise ValueError("unexpected task-transfer identity")
    population = protocol.get("population")
    if not isinstance(population, dict):
        raise ValueError("task-transfer population is absent")
    validate_population(population)
    if tuple(protocol.get("arms", ())) != ARMS or set(DRIVERS) != set(ARMS):
        raise ValueError("task-transfer arms changed")
    if protocol.get("tasks") != task_records(population):
        raise ValueError("task-transfer task records changed")
    if tuple(protocol.get("fresh_seeds", ())) != SEEDS:
        raise ValueError("task-transfer seeds changed")
    if protocol.get("maximum_gui_actions") != MAXIMUM_GUI_ACTIONS:
        raise ValueError("task-transfer action horizon changed")
    fixed = {
        "preregistration": PREREGISTRATION,
        "purpose": PURPOSE,
        "coverage_survey": COVERAGE_SURVEY,
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
            raise ValueError(f"task-transfer {key} changed")
    if protocol.get("expected_episodes") != expected_episodes():
        raise ValueError("task-transfer episode count changed")
    for key in ("predecessor", "repositories", "source_sha256"):
        if not isinstance(protocol.get(key), dict):
            raise ValueError(f"task-transfer {key} binding is absent")
    for key in (
        "outcome_based_exclusion_allowed",
        "partial_reexecution_allowed",
        "completed_episode_replay_allowed",
    ):
        if protocol.get(key) is not False:
            raise ValueError(f"task-transfer {key} changed")


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
                        "new_template_population": (
                            task in NEW_TEMPLATE_EXACT_TASKS
                        ),
                        "budget_level": "uniform_ample",
                        "seed": seed,
                        "maximum_gui_actions": MAXIMUM_GUI_ACTIONS,
                        "method": method,
                        "episode_id": (
                            f"{task}__seed{seed}__a{MAXIMUM_GUI_ACTIONS}__{method}"
                        ),
                    }
                )
    if len(rows) != expected_episodes():
        raise ValueError("task-transfer manifest is incomplete")
    if len({row["episode_id"] for row in rows}) != len(rows):
        raise ValueError("task-transfer manifest is duplicated")
    return rows


def arm_order_counts(protocol: dict[str, Any]) -> dict[str, dict[int, int]]:
    counts = {arm: Counter() for arm in ARMS}
    for row in episode_manifest(protocol):
        counts[row["method"]][int(row["arm_position"])] += 1
    return {arm: dict(sorted(values.items())) for arm, values in counts.items()}


def _runtime_halt(row: dict[str, Any]) -> bool:
    return bool(row.get("metrics", {}).get("runtime_halted"))


def _closed_success(row: dict[str, Any]) -> bool:
    return (
        bool(row.get("success"))
        and _active_count(row) == 0
        and not _runtime_halt(row)
    )


def _failed_stop_stranding(row: dict[str, Any]) -> bool:
    return not bool(row.get("success")) and _active_count(row) > 0


def _all_restorations_pass(row: dict[str, Any]) -> bool:
    pairs = (
        ("restoration_attempts", "restoration_passes"),
        (
            "interrupt_clearance_restoration_attempts_v16",
            "interrupt_clearance_restoration_passes_v16",
        ),
        (
            "proposal_clearance_restoration_attempts_v16",
            "proposal_clearance_restoration_passes_v16",
        ),
        (
            "active_restore_clearance_restoration_attempts_v16",
            "active_restore_clearance_restoration_passes_v16",
        ),
    )
    return all(
        _metric(row, passed) == _metric(row, attempted)
        for attempted, passed in pairs
    )


def _reserve_rejections(row: dict[str, Any]) -> int:
    return sum(
        event.get("type") == RESERVATION_EVENT_V18
        and event.get("reservation_rule") == "stack_wide"
        and event.get("allowed") is False
        for event in row.get("trace", ())
    )


def _nested_admissions(row: dict[str, Any]) -> int:
    return sum(
        event.get("type") == RESERVATION_EVENT_V18
        and event.get("reservation_rule") == "stack_wide"
        and event.get("decision") == "transact"
        and int(event.get("registered_active_inverse_cost", 0)) > 0
        and event.get("allowed") is True
        for event in row.get("trace", ())
    )


def _single_cap_rejections(row: dict[str, Any]) -> int:
    return sum(
        event.get("type") == SINGLE_OBLIGATION_POLICY_EVENT_V19
        and event.get("decision") == "transact"
        and event.get("allowed") is False
        and event.get("delegated_to_stack_wide_reserve") is False
        for event in row.get("trace", ())
    )


def summarize_rows(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    rows = tuple(rows)
    return {
        "episodes": len(rows),
        "task_successes": sum(bool(row.get("success")) for row in rows),
        "closed_successes": sum(_closed_success(row) for row in rows),
        "closed_success_templates": len(
            {
                str(row.get("episode", {}).get("family_group"))
                for row in rows
                if _closed_success(row)
            }
        ),
        "successes_with_active_obligations": sum(
            bool(row.get("success")) and _active_count(row) > 0 for row in rows
        ),
        "failed_stop_stranding_episodes": sum(
            _failed_stop_stranding(row) for row in rows
        ),
        "runtime_halt_episodes": sum(_runtime_halt(row) for row in rows),
        "rows_with_failed_restoration": sum(
            not _all_restorations_pass(row) for row in rows
        ),
        "reserve_rejections": sum(_reserve_rejections(row) for row in rows),
        "nested_admissions": sum(_nested_admissions(row) for row in rows),
        "single_active_cap_rejections": sum(
            _single_cap_rejections(row) for row in rows
        ),
        "goal_mutation_consumption_passes_v19": sum(
            _metric(row, "goal_mutation_consumption_passes_v19") for row in rows
        ),
        "certified_scope_consumption_failures_v19": sum(
            _metric(row, "certified_scope_consumption_failures_v19")
            for row in rows
        ),
        "top_cleanup_attempts": sum(
            _metric(row, "top_cleanup_attempts") for row in rows
        ),
        "top_cleanup_passes": sum(
            _metric(row, "top_cleanup_passes") for row in rows
        ),
        "top_cleanup_failures": sum(
            _metric(row, "top_cleanup_failures") for row in rows
        ),
        "gui_actions": sum(_metric(row, "gui_actions") for row in rows),
        "typed_transactions": sum(_metric(row, "typed_transactions") for row in rows),
        "planner_calls": sum(_metric(row, "planner_calls") for row in rows),
        "planner_actual_calls": sum(
            _metric(row, "planner_actual_calls") for row in rows
        ),
        "infrastructure_failures": sum(
            bool(row.get("infrastructure_failure")) for row in rows
        ),
    }


def _seed_cluster_comparison(
    rows: tuple[dict[str, Any], ...],
    tasks: tuple[str, ...],
) -> dict[str, Any]:
    seed_rows = []
    wins = losses = ties = 0
    for seed in SEEDS:
        full = sum(
            _closed_success(row)
            for row in rows
            if row.get("episode", {}).get("seed") == seed
            and row.get("episode", {}).get("task") in tasks
            and row.get("episode", {}).get("method") == FULL_METHOD
        )
        safe = sum(
            _closed_success(row)
            for row in rows
            if row.get("episode", {}).get("seed") == seed
            and row.get("episode", {}).get("task") in tasks
            and row.get("episode", {}).get("method") == SAFE_BASELINE
        )
        wins += full > safe
        losses += full < safe
        ties += full == safe
        seed_rows.append(
            {
                "seed": seed,
                "full_closed": full,
                "safe_closed": safe,
                "difference": full - safe,
            }
        )
    return {
        "seed_cluster_wins": wins,
        "seed_cluster_losses": losses,
        "seed_cluster_ties": ties,
        "two_sided_exact_sign_p": exact_mcnemar(wins, losses),
        "seed_rows": seed_rows,
    }


def _paired_comparison(
    rows: tuple[dict[str, Any], ...],
    tasks: tuple[str, ...],
    *,
    bootstrap_seed: int,
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
    rows: Iterable[dict[str, Any]],
    protocol: dict[str, Any],
    *,
    all_claims_complete: bool,
) -> dict[str, Any]:
    validate_protocol(protocol)
    rows = tuple(rows)
    manifest = episode_manifest(protocol)
    expected = {row["episode_id"]: row for row in manifest}
    observed = [str(row.get("episode", {}).get("episode_id")) for row in rows]
    exact_manifest = (
        len(rows) == len(manifest)
        and len(set(observed)) == len(rows)
        and set(observed) == set(expected)
        and all(
            row.get("episode")
            == expected.get(str(row.get("episode", {}).get("episode_id")))
            for row in rows
        )
    )
    metrics = {
        arm: summarize_rows(
            row for row in rows if row.get("episode", {}).get("method") == arm
        )
        for arm in ARMS
    }
    full = metrics[FULL_METHOD]
    safe = metrics[SAFE_BASELINE]
    checks = {
        "complete_exact_grid": exact_manifest and all_claims_complete,
        "zero_infrastructure_failures": all(
            values["infrastructure_failures"] == 0 for values in metrics.values()
        ),
        "planner_is_exercised": sum(
            values["planner_actual_calls"] for values in metrics.values()
        )
        > 0,
        "all_rows_respect_hard_budgets": _all_rows_respect_budgets(rows, protocol),
        "both_policies_zero_failed_stop_stranding": all(
            values["failed_stop_stranding_episodes"] == 0
            for values in metrics.values()
        ),
        "both_policies_zero_runtime_halts": all(
            values["runtime_halt_episodes"] == 0 for values in metrics.values()
        ),
        "all_restoration_attempts_pass": all(
            values["rows_with_failed_restoration"] == 0
            for values in metrics.values()
        ),
        "both_policies_zero_v19_scope_failures": all(
            values["certified_scope_consumption_failures_v19"] == 0
            for values in metrics.values()
        ),
        "all_successes_are_closed": all(
            values["closed_successes"] == values["task_successes"]
            for values in metrics.values()
        ),
        "full_method_nested_admission_activates": full["nested_admissions"] > 0,
        "safe_baseline_cap_activates": safe["single_active_cap_rejections"] > 0,
    }
    by_task = [
        {
            "task": task,
            "template_group": protocol["population"]["task_metadata"][task][
                "template_group"
            ],
            "primary_population": task in PRIMARY_TASKS,
            "new_template_population": task in NEW_TEMPLATE_EXACT_TASKS,
            "arms": {
                arm: summarize_rows(
                    row
                    for row in rows
                    if row.get("episode", {}).get("task") == task
                    and row.get("episode", {}).get("method") == arm
                )
                for arm in ARMS
            },
        }
        for task in ELIGIBLE_TASKS
    ]
    comparisons = None
    if exact_manifest and not any(
        bool(row.get("infrastructure_failure")) for row in rows
    ):
        comparisons = {
            "primary_canonical_new_templates": _paired_comparison(
                rows,
                PRIMARY_TASKS,
                bootstrap_seed=BOOTSTRAP_SEED,
            ),
            "secondary_all_new_template_exact_tasks": _paired_comparison(
                rows,
                NEW_TEMPLATE_EXACT_TASKS,
                bootstrap_seed=BOOTSTRAP_SEED + 1,
            ),
            "secondary_all_eligible_exact_tasks": _paired_comparison(
                rows,
                ELIGIBLE_TASKS,
                bootstrap_seed=BOOTSTRAP_SEED + 2,
            ),
        }
    return {
        "claim_status": PURPOSE["claim_status"],
        "confirmation_status": PURPOSE["confirmation_status"],
        "exact_manifest": exact_manifest,
        "all_claims_complete": all_claims_complete,
        "metrics": metrics,
        "paired_stack_vs_safe_closed_success": (
            comparisons["primary_canonical_new_templates"]
            if comparisons is not None
            else None
        ),
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
