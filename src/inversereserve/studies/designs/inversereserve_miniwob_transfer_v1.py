"""Outcome-independent study design and episode population; analysis remains in the parent study module."""

from __future__ import annotations

from collections import Counter
from typing import Any

from inversereserve.controllers.capacity_reserve_drivers_v19 import (
    SINGLE_ACTIVE_OBLIGATION_V19,
    SingleActiveObligationDriverV19,
)
from inversereserve.controllers.capacity_safe_dynamic_controls_v19 import (
    TOP_CLEANUP_REPLAN_V19,
    TopCleanupReplanDriverV19,
)
from inversereserve.studies.inversereserve_cross_planner_replication_v1 import (
    GENERATION,
    PLANNER_MODEL,
    RUNTIME_DEPLOYMENT,
)
from inversereserve.studies.validation import require

CANDIDATE = "InverseReserve-miniwob-task-transfer-v1"
STATUS = "frozen_after_outcome_free_survey_before_any_37101_through_37120_reset"
FULL_METHOD = TOP_CLEANUP_REPLAN_V19
SAFE_BASELINE = SINGLE_ACTIVE_OBLIGATION_V19
ARMS = (FULL_METHOD, SAFE_BASELINE)
DRIVERS = {FULL_METHOD: TopCleanupReplanDriverV19, SAFE_BASELINE: SingleActiveObligationDriverV19}
SEEDS = tuple(range(37101, 37121))
MAXIMUM_GUI_ACTIONS = 32
COMMON_BUDGETS = {"maximum_planner_calls": 40, "maximum_wall_seconds": 300.0}
BOOTSTRAP_SAMPLES = 50000
BOOTSTRAP_SEED = 270733
ALPHA = 0.05
PREREGISTRATION = {
    "path": "paper/aaai27/notes/2026-07-23_inversereserve_miniwob_transfer_v1_preregistration.md",
    "sha256": "62c404873add63ecb332676295797a8ff40b5b49e358b63e224c245b5735a8a2",
}
COVERAGE_SURVEY = {
    "path": "validation/inversereserve_miniwob_public_input_coverage_survey_v1.json",
    "sha256": "f8268eb6c51ec481faebf9a527e0fca4c5920d0cc0e5526908b58378d159e7ef",
    "source_commit": "c6eded46b099b2e5eebdff791adcd0907ae89a23",
    "source_script": "scripts/inversereserve_miniwob_coverage_survey.py",
    "source_script_sha256": "44264458c81ee0199f28b2ecd2f6865ac6ee3cbd775faf834ad1264a9c0efc2b",
}
VARIANT_SUFFIXES = ("-nodelay", "-easy", "-medium", "-hard", "-popup", "-2")
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
PRIMARY_TASKS = ("click-collapsible", "click-menu", "click-tab-2", "enter-password", "navigate-tree")
PURPOSE = {
    "claim_status": "prospective_reviewer_driven_task_transfer",
    "confirmation_status": "not_independent_confirmation",
    "selection_status": "task population fixed only from public inputs before fresh outcomes",
    "question": "whether the retained InverseReserve policy transfers to exact tasks and normalized task templates absent from the earlier six-task grid",
    "outcome_based_exclusion_allowed": False,
}
OUTCOME_DEFINITIONS = {
    "official_task_success": "environment-provided binary task success",
    "closed_success": "official task success with zero active typed obligations and no runtime halt",
    "failed_stop_stranding": "task failure with at least one active typed obligation at episode stop",
    "verified_restoration": "every attempted ordinary or clearance restoration passes",
    "runtime_halt": "runtime_halted is true in the sealed episode metrics",
    "reporting_rule": "report utility, safety, restoration, policy activation, and work separately without a composite endpoint",
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
    "on_pass": "report the complete outcome-blind task-transfer comparison regardless of effect direction",
    "on_failure": "seal every opened row, report failed validity gates, and make no positive task-transfer claim",
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


def validate_population(population: dict[str, Any]) -> None:
    if (
        tuple(population.get("eligible_exact_tasks", ())) != ELIGIBLE_TASKS
        or tuple(population.get("new_template_exact_tasks", ())) != NEW_TEMPLATE_EXACT_TASKS
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
            or (not isinstance(record.get("transaction_kinds"), list))
            or (int(record.get("minimum_initial_transaction_candidates", 0)) < 1)
        ):
            raise ValueError(f"task-transfer metadata changed for {task}")
    if population.get("selection_rule", {}).get("outcome_based_exclusion_allowed") is not False:
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
        "isolated_policy_difference": "both arms share PACT-v19 contracts, stack-wide capacity accounting, planner, executor, and verification; the baseline alone refuses a second simultaneous typed obligation",
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
        "unexpected task-transfer identity",
    )
    population = protocol.get("population")
    require(isinstance(population, dict), "task-transfer population is absent")
    validate_population(population)
    require(
        not (tuple(protocol.get("arms", ())) != ARMS or set(DRIVERS) != set(ARMS)),
        "task-transfer arms changed",
    )
    require(not protocol.get("tasks") != task_records(population), "task-transfer task records changed")
    require(not tuple(protocol.get("fresh_seeds", ())) != SEEDS, "task-transfer seeds changed")
    require(
        not protocol.get("maximum_gui_actions") != MAXIMUM_GUI_ACTIONS, "task-transfer action horizon changed"
    )
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
    require(
        not protocol.get("expected_episodes") != expected_episodes(), "task-transfer episode count changed"
    )
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
                        "new_template_population": task in NEW_TEMPLATE_EXACT_TASKS,
                        "budget_level": "uniform_ample",
                        "seed": seed,
                        "maximum_gui_actions": MAXIMUM_GUI_ACTIONS,
                        "method": method,
                        "episode_id": f"{task}__seed{seed}__a{MAXIMUM_GUI_ACTIONS}__{method}",
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
