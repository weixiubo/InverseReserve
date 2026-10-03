"""Prospective complete transaction-catalog replication for MiniWoB++."""

from __future__ import annotations

from collections import defaultdict
from contextlib import contextmanager
from typing import Any, Iterable, Iterator

from . import inversereserve_miniwob_transfer_v2 as v2


CANDIDATE = "InverseReserve-miniwob-complete-catalog-replication-v1"
STATUS = (
    "frozen_after_valid_interface_completion_v2_"
    "before_any_37301_through_37320_reset"
)
FULL_METHOD = v2.FULL_METHOD
SAFE_BASELINE = v2.SAFE_BASELINE
ARMS = v2.ARMS
DRIVERS = v2.DRIVERS
SEEDS = tuple(range(37301, 37321))
MAXIMUM_GUI_ACTIONS = v2.MAXIMUM_GUI_ACTIONS
COMMON_BUDGETS = dict(v2.COMMON_BUDGETS)
GENERATION = dict(v2.GENERATION)
RUNTIME_DEPLOYMENT = dict(v2.RUNTIME_DEPLOYMENT)
PLANNER_MODEL = {
    **v2.PLANNER_MODEL,
    "snapshot_files_sha256": dict(
        v2.PLANNER_MODEL["snapshot_files_sha256"]
    ),
}
BOOTSTRAP_SAMPLES = v2.BOOTSTRAP_SAMPLES
BOOTSTRAP_SEED = 270_735
ALPHA = v2.ALPHA
PREREGISTRATION = {
    "path": (
        "paper/aaai27/notes/"
        "2026-07-24_inversereserve_miniwob_catalog_replication_v1_"
        "preregistration.md"
    ),
    "sha256": (
        "38d258014a5ac28d6b6a2ea2e3072a75b234594a6f4af6566f83add1c685dfe7"
    ),
}
COVERAGE_SURVEY = dict(v2.COVERAGE_SURVEY)
DEVELOPMENT_RECORD = dict(v2.DEVELOPMENT_RECORD)
INTERFACE_COMPLETION = {
    **v2.INTERFACE_COMPLETION,
    "rules": list(v2.INTERFACE_COMPLETION["rules"]),
}
CATALOG_TASKS = (
    "book-flight",
    "book-flight-nodelay",
    "choose-date",
    "choose-date-easy",
    "choose-date-medium",
    "choose-date-nodelay",
    "click-collapsible",
    "click-collapsible-2",
    "click-collapsible-2-nodelay",
    "click-collapsible-nodelay",
    "click-menu",
    "click-scroll-list",
    "click-tab-2",
    "enter-password",
    "login-user",
    "login-user-popup",
    "navigate-tree",
    "use-autocomplete",
    "use-autocomplete-nodelay",
)
PREVIOUSLY_EXERCISED_EXACT_TASKS = (
    "book-flight-nodelay",
    "choose-date-nodelay",
    "click-scroll-list",
    "login-user-popup",
    "use-autocomplete-nodelay",
)
SEEN_TEMPLATE_NEW_EXACT_TASKS = tuple(
    task
    for task in v2.ELIGIBLE_TASKS
    if task not in v2.NEW_TEMPLATE_EXACT_TASKS
)
NEW_TEMPLATE_EXACT_TASKS = tuple(v2.NEW_TEMPLATE_EXACT_TASKS)
ELIGIBLE_TASKS = CATALOG_TASKS
PRIMARY_TASKS = CATALOG_TASKS
PURPOSE = {
    "claim_status": "prospective_complete_transaction_catalog_replication",
    "confirmation_status": (
        "fresh_seed_complete_catalog_replication_not_external_confirmation"
    ),
    "selection_status": (
        "complete transaction-eligible catalog fixed from the sealed "
        "zero-step survey; no task-level exclusion"
    ),
    "question": (
        "whether the frozen PACT-v20 method safely covers every bundled "
        "MiniWoB++ task whose surveyed first envelope is a typed transaction"
    ),
    "outcome_based_exclusion_allowed": False,
}
OUTCOME_DEFINITIONS = dict(v2.OUTCOME_DEFINITIONS)
PRIMARY_ANALYSIS = {
    **v2.PRIMARY_ANALYSIS,
    "population": "complete transaction-eligible bundled MiniWoB++ catalog",
    "canonical_rule": "retain every transaction-eligible surveyed task",
    "tasks": list(PRIMARY_TASKS),
    "bootstrap_seed": BOOTSTRAP_SEED,
}
VALIDITY_GATES = dict(v2.VALIDITY_GATES)
DECISION_RULE = {
    "on_pass": (
        "report the complete fresh-seed catalog comparison regardless of "
        "effect direction or significance"
    ),
    "on_failure": (
        "seal every opened row, report failed validity gates, and make no "
        "positive complete-catalog claim"
    ),
}


def normalize_task_template(task: str) -> str:
    return v2.normalize_task_template(task)


def _survey_rows(survey: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    base_population = v2.derive_population(survey)
    v2.validate_population(base_population)
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in survey["rows"]:
        grouped[str(row["task"])].append(row)
    return grouped


def _metadata_for_task(
    task: str,
    rows: list[dict[str, Any]],
    *,
    template_status: str,
) -> dict[str, Any]:
    task_rows = sorted(rows, key=lambda row: int(row["seed"]))
    if (
        tuple(int(row.get("seed", -1)) for row in task_rows)
        != tuple(v2.SURVEY_SEEDS)
        or any(row.get("reset_succeeded") is not True for row in task_rows)
        or any(int(row.get("environment_step_calls", -1)) != 0 for row in task_rows)
        or any(row.get("reset_info_ignored") is not True for row in task_rows)
        or any(row.get("method_received_task_id") is not False for row in task_rows)
        or any(
            row.get("envelope", {}).get("decision") != "transact"
            for row in task_rows
        )
        or any(
            int(row.get("transaction_candidate_count", 0)) < 1
            for row in task_rows
        )
    ):
        raise ValueError(f"complete-catalog survey eligibility failed for {task}")
    transaction_kinds = sorted(
        {
            str(kind)
            for row in task_rows
            for kind in row.get("transaction_kinds", ())
        }
    )
    return {
        "task_id": task,
        "template_group": normalize_task_template(task),
        "template_status": template_status,
        "transaction_kinds": transaction_kinds,
        "minimum_initial_transaction_candidates": min(
            int(row["transaction_candidate_count"]) for row in task_rows
        ),
        "maximum_initial_transaction_candidates": max(
            int(row["transaction_candidate_count"]) for row in task_rows
        ),
    }


def derive_population(survey: dict[str, Any]) -> dict[str, Any]:
    """Derive the complete transaction catalog without reading task outcomes."""

    base_population = v2.derive_population(survey)
    grouped = _survey_rows(survey)
    metadata = dict(base_population["task_metadata"])
    for task in PREVIOUSLY_EXERCISED_EXACT_TASKS:
        metadata[task] = _metadata_for_task(
            task,
            grouped[task],
            template_status="previously_exercised_exact_task",
        )

    derived_catalog = tuple(
        sorted(
            task
            for task, rows in grouped.items()
            if all(
                row.get("envelope", {}).get("decision") == "transact"
                and int(row.get("transaction_candidate_count", 0)) >= 1
                for row in rows
            )
        )
    )
    if derived_catalog != CATALOG_TASKS:
        raise ValueError(
            "complete transaction catalog changed: "
            f"{derived_catalog!r}"
        )
    if set(metadata) != set(CATALOG_TASKS):
        raise ValueError("complete transaction metadata is incomplete")

    population = {
        "selection_rule": {
            "survey_seeds": list(v2.SURVEY_SEEDS),
            "requires_reset_success_on_every_survey_seed": True,
            "requires_zero_environment_steps": True,
            "requires_reset_info_ignored": True,
            "requires_method_task_id_hidden": True,
            "requires_first_envelope_transact_on_every_survey_seed": True,
            "requires_typed_candidate_on_every_survey_seed": True,
            "task_level_exclusions": [],
            "catalog_rule": (
                "retain every task with a typed transact envelope on both "
                "sealed survey resets"
            ),
            "outcome_based_exclusion_allowed": False,
        },
        "eligible_exact_tasks": list(CATALOG_TASKS),
        "primary_tasks": list(PRIMARY_TASKS),
        "new_template_exact_tasks": list(NEW_TEMPLATE_EXACT_TASKS),
        "seen_template_new_exact_tasks": list(
            SEEN_TEMPLATE_NEW_EXACT_TASKS
        ),
        "previously_exercised_exact_tasks": list(
            PREVIOUSLY_EXERCISED_EXACT_TASKS
        ),
        "new_template_groups": list(base_population["new_template_groups"]),
        "task_metadata": {
            task: metadata[task] for task in CATALOG_TASKS
        },
    }
    validate_population(population)
    return population


def validate_population(population: dict[str, Any]) -> None:
    expected_lists = {
        "eligible_exact_tasks": CATALOG_TASKS,
        "primary_tasks": PRIMARY_TASKS,
        "new_template_exact_tasks": NEW_TEMPLATE_EXACT_TASKS,
        "seen_template_new_exact_tasks": SEEN_TEMPLATE_NEW_EXACT_TASKS,
        "previously_exercised_exact_tasks": PREVIOUSLY_EXERCISED_EXACT_TASKS,
    }
    for key, expected in expected_lists.items():
        if tuple(population.get(key, ())) != expected:
            raise ValueError(f"complete-catalog {key} changed")
    metadata = population.get("task_metadata")
    if not isinstance(metadata, dict) or set(metadata) != set(CATALOG_TASKS):
        raise ValueError("complete-catalog metadata changed")
    for task in CATALOG_TASKS:
        record = metadata[task]
        if (
            record.get("task_id") != task
            or record.get("template_group") != normalize_task_template(task)
            or not isinstance(record.get("transaction_kinds"), list)
            or int(record.get("minimum_initial_transaction_candidates", 0)) < 1
        ):
            raise ValueError(f"complete-catalog metadata changed for {task}")
    selection = population.get("selection_rule", {})
    if (
        selection.get("task_level_exclusions") != []
        or selection.get("outcome_based_exclusion_allowed") is not False
    ):
        raise ValueError("complete-catalog exclusion rule changed")


def task_records(population: dict[str, Any]) -> list[dict[str, Any]]:
    validate_population(population)
    return [
        {
            **population["task_metadata"][task],
            "primary_population": True,
            "new_template_population": task in NEW_TEMPLATE_EXACT_TASKS,
            "previously_exercised_population": (
                task in PREVIOUSLY_EXERCISED_EXACT_TASKS
            ),
            "maximum_gui_actions": MAXIMUM_GUI_ACTIONS,
        }
        for task in CATALOG_TASKS
    ]


def _v2_patch() -> dict[str, Any]:
    return {
        "CANDIDATE": CANDIDATE,
        "STATUS": STATUS,
        "SEEDS": SEEDS,
        "MAXIMUM_GUI_ACTIONS": MAXIMUM_GUI_ACTIONS,
        "COMMON_BUDGETS": COMMON_BUDGETS,
        "BOOTSTRAP_SAMPLES": BOOTSTRAP_SAMPLES,
        "BOOTSTRAP_SEED": BOOTSTRAP_SEED,
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


def expected_episodes() -> int:
    return len(ARMS) * len(SEEDS) * len(CATALOG_TASKS)


def build_protocol(**kwargs: Any) -> dict[str, Any]:
    with _configured_v2():
        return v2.build_protocol(**kwargs)


def validate_protocol(protocol: dict[str, Any]) -> None:
    with _configured_v2():
        v2.validate_protocol(protocol)


def episode_manifest(protocol: dict[str, Any]) -> list[dict[str, Any]]:
    with _configured_v2():
        return v2.episode_manifest(protocol)


def arm_order_counts(protocol: dict[str, Any]) -> dict[str, dict[int, int]]:
    with _configured_v2():
        return v2.arm_order_counts(protocol)


def summarize_rows(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    with _configured_v2():
        return v2.summarize_rows(rows)


def analyze_rows(
    rows: Iterable[dict[str, Any]],
    protocol: dict[str, Any],
    *,
    all_claims_complete: bool,
) -> dict[str, Any]:
    materialized = tuple(rows)
    with _configured_v2():
        analysis = v2.analyze_rows(
            materialized,
            protocol,
            all_claims_complete=all_claims_complete,
        )
        comparisons = analysis.get("comparisons")
        if isinstance(comparisons, dict):
            primary = comparisons["primary_canonical_new_templates"]
            new_templates = comparisons[
                "secondary_all_new_template_exact_tasks"
            ]
            comparisons = {
                "primary_complete_transaction_catalog": primary,
                "secondary_new_template_exact_tasks": new_templates,
                "secondary_seen_template_new_exact_tasks": v2._paired_comparison(
                    materialized,
                    SEEN_TEMPLATE_NEW_EXACT_TASKS,
                    bootstrap_seed=BOOTSTRAP_SEED + 2,
                ),
                "secondary_previously_exercised_exact_tasks": (
                    v2._paired_comparison(
                        materialized,
                        PREVIOUSLY_EXERCISED_EXACT_TASKS,
                        bootstrap_seed=BOOTSTRAP_SEED + 3,
                    )
                ),
            }
            analysis["comparisons"] = comparisons
            analysis["paired_stack_vs_safe_closed_success"] = primary
        return analysis


__all__ = [
    "ARMS",
    "CANDIDATE",
    "CATALOG_TASKS",
    "COVERAGE_SURVEY",
    "DECISION_RULE",
    "DEVELOPMENT_RECORD",
    "DRIVERS",
    "ELIGIBLE_TASKS",
    "FULL_METHOD",
    "GENERATION",
    "INTERFACE_COMPLETION",
    "NEW_TEMPLATE_EXACT_TASKS",
    "PREVIOUSLY_EXERCISED_EXACT_TASKS",
    "PRIMARY_ANALYSIS",
    "PRIMARY_TASKS",
    "PLANNER_MODEL",
    "PURPOSE",
    "RUNTIME_DEPLOYMENT",
    "SAFE_BASELINE",
    "SEEDS",
    "SEEN_TEMPLATE_NEW_EXACT_TASKS",
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
    "task_records",
    "validate_population",
    "validate_protocol",
]
