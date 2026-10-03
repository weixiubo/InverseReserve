from __future__ import annotations

from collections import Counter
from typing import Any, Iterable

from inversereserve.studies.confirmation_statistics_v7 import exact_paired_greater
from inversereserve.studies.episode_grid import matches_registered_grid
from inversereserve.studies.inversereserve_capacity_regime_successor_v3 import _all_rows_respect_budgets
from inversereserve.studies.inversereserve_live_resource_stress_v1 import _active_count, _metric
from inversereserve.studies.inversereserve_v19_unified_development_v1 import (
    ACTION_BUDGETS,
    BUDGET_LEVELS,
    COMMON_BUDGETS,
    DRIVERS,
    GENERATION,
    OUTCOME_DEFINITIONS,
    RUNTIME_DEPLOYMENT,
    TASK_FAMILIES,
    summarize_rows,
)
from inversereserve.studies.inversereserve_v19_unified_development_v1 import ARMS as ARMS
from inversereserve.studies.inversereserve_v19_unified_development_v1 import FULL_METHOD as FULL_METHOD
from inversereserve.studies.inversereserve_v19_unified_development_v1 import LOCAL_ABLATION as LOCAL_ABLATION
from inversereserve.studies.inversereserve_v19_unified_development_v1 import SAFE_BASELINE as SAFE_BASELINE
from inversereserve.studies.pact_statistics import paired_binary_comparison
from inversereserve.studies.validation import require

"Frozen independent confirmation design for the completed PACT-v19 method."
CANDIDATE = "InverseReserve-v19-unified-confirmation-v1"
STATUS = "independent_confirmation_frozen_before_any_35101_through_35120_reset"
SEEDS = tuple(range(35101, 35121))
BOOTSTRAP_SAMPLES = 50000
BOOTSTRAP_SEED = 270729
PRIMARY_ALPHA = 0.01
PREREGISTRATION = {
    "path": "paper/aaai27/notes/2026-07-21_inversereserve_v19_unified_confirmation_v1_preregistration.md",
    "sha256": "11cb35efc7b78a28fae1deb52304f699d6cbc3f51f7701e77ce3f613449ab81d",
}
PURPOSE = {
    "claim_status": "independent_confirmation",
    "method_status": "exact development-tested PACT-v19 method",
    "question": "whether stack-wide reserve closes successful v19 episodes safely and improves closed success over the one-active safe control",
    "development_rows_in_confirmation": 0,
    "outcome_based_exclusion_allowed": False,
}
PRIMARY_ANALYSIS = {
    "endpoint": "closed_success",
    "paired_unit": "task_horizon_seed_cell",
    "full_method": FULL_METHOD,
    "baseline": SAFE_BASELINE,
    "test": "one_sided_exact_paired_mcnemar_sign",
    "bootstrap_unit": "seed_cluster_shared_across_18_task_horizon_strata",
    "bootstrap_samples": BOOTSTRAP_SAMPLES,
    "bootstrap_seed": BOOTSTRAP_SEED,
    "alpha": PRIMARY_ALPHA,
    "multiplicity": "one_primary_efficacy_hypothesis",
}
CONFIRMATION_GATES = {
    "minimum_stack_closed_successes": 180,
    "minimum_stack_closed_successes_per_family": 10,
    "minimum_net_paired_closed_successes": 36,
    "maximum_one_sided_exact_p": PRIMARY_ALPHA,
    "bootstrap_lower_bound_strictly_positive": True,
    "complete_exact_grid": True,
    "zero_infrastructure_failures": True,
    "planner_is_exercised": True,
    "all_rows_respect_hard_budgets": True,
    "stack_has_zero_failed_stop_stranding": True,
    "stack_has_zero_runtime_halts": True,
    "stack_restorations_all_pass": True,
    "stack_has_zero_unsafe_local_admissions": True,
    "stack_has_zero_v19_scope_failures": True,
    "stack_closes_every_success": True,
    "stack_goal_mutation_discharge_activates": True,
    "stack_reserve_rejection_activates": True,
    "local_has_zero_v19_scope_failures": True,
    "local_unsafe_boundary_activates": True,
    "safe_control_has_zero_failed_stop_stranding": True,
    "safe_control_has_zero_runtime_halts": True,
    "safe_control_restorations_all_pass": True,
    "safe_control_has_zero_v19_scope_failures": True,
    "safe_control_closes_every_success": True,
    "safe_control_cap_activates": True,
}
DECISION_RULE = {
    "activation": "open only after the complete v19 unified development result passes every frozen gate",
    "on_pass": "seal and report the complete independent confirmation without pooling development rows",
    "on_failure": "seal every observed row without replay or outcome exclusion and open no replacement confirmation for this submission",
}


def task_records() -> list[dict[str, Any]]:
    return [
        {"task_id": task, "family_group": family, "budget_levels": dict(ACTION_BUDGETS)}
        for task, family in TASK_FAMILIES.items()
    ]


def expected_episodes() -> int:
    return len(ARMS) * len(SEEDS) * len(TASK_FAMILIES) * len(BUDGET_LEVELS)


def build_protocol(
    *,
    scientific_source_commit: str,
    source_sha256: dict[str, str],
    predecessor: dict[str, Any],
    repositories: dict[str, str],
    created_utc: str,
) -> dict[str, Any]:
    protocol = {
        "candidate": CANDIDATE,
        "status": STATUS,
        "created_utc": created_utc,
        "scientific_source_commit": scientific_source_commit,
        "preregistration": dict(PREREGISTRATION),
        "predecessor": predecessor,
        "purpose": dict(PURPOSE),
        "arms": list(ARMS),
        "isolated_method_differences": {
            FULL_METHOD: "stack-wide active-plus-proposal inverse reserve",
            LOCAL_ABLATION: "proposal-only inverse reserve",
            SAFE_BASELINE: "stack-wide inverse reserve plus at most one active obligation",
        },
        "tasks": task_records(),
        "confirmation_seeds": list(SEEDS),
        "budget_levels": list(BUDGET_LEVELS),
        "uniform_action_budgets": dict(ACTION_BUDGETS),
        "common_budgets": dict(COMMON_BUDGETS),
        "generation": dict(GENERATION),
        "runtime_deployment": dict(RUNTIME_DEPLOYMENT),
        "expected_episodes": expected_episodes(),
        "outcome_definitions": dict(OUTCOME_DEFINITIONS),
        "primary_analysis": dict(PRIMARY_ANALYSIS),
        "confirmation_gates": dict(CONFIRMATION_GATES),
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
        "unexpected PACT-v19 confirmation identity",
    )
    require(
        not (tuple(protocol.get("arms", ())) != ARMS or set(DRIVERS) != set(ARMS)),
        "PACT-v19 confirmation arms changed",
    )
    require(not protocol.get("tasks") != task_records(), "PACT-v19 confirmation task grid changed")
    require(not tuple(protocol.get("confirmation_seeds", ())) != SEEDS, "PACT-v19 confirmation seeds changed")
    require(
        not tuple(protocol.get("budget_levels", ())) != BUDGET_LEVELS,
        "PACT-v19 confirmation budget levels changed",
    )
    require(
        not protocol.get("uniform_action_budgets") != ACTION_BUDGETS, "PACT-v19 confirmation horizons changed"
    )
    require(
        not protocol.get("common_budgets") != COMMON_BUDGETS, "PACT-v19 confirmation common budgets changed"
    )
    require(not protocol.get("generation") != GENERATION, "PACT-v19 confirmation generation changed")
    require(
        not protocol.get("runtime_deployment") != RUNTIME_DEPLOYMENT,
        "PACT-v19 confirmation deployment changed",
    )
    require(not protocol.get("purpose") != PURPOSE, "PACT-v19 confirmation purpose changed")
    require(
        not protocol.get("preregistration") != PREREGISTRATION,
        "PACT-v19 confirmation preregistration changed",
    )
    require(
        not protocol.get("outcome_definitions") != OUTCOME_DEFINITIONS,
        "PACT-v19 confirmation outcomes changed",
    )
    require(not protocol.get("primary_analysis") != PRIMARY_ANALYSIS, "PACT-v19 primary analysis changed")
    require(
        not protocol.get("confirmation_gates") != CONFIRMATION_GATES, "PACT-v19 confirmation gates changed"
    )
    require(not protocol.get("decision_rule") != DECISION_RULE, "PACT-v19 confirmation decision rule changed")
    require(
        not protocol.get("expected_episodes") != expected_episodes(),
        "PACT-v19 confirmation episode count changed",
    )
    for key in ("predecessor", "repositories", "source_sha256"):
        if not isinstance(protocol.get(key), dict):
            raise ValueError(f"PACT-v19 confirmation {key} binding is absent")
    for key in (
        "outcome_based_exclusion_allowed",
        "partial_reexecution_allowed",
        "completed_episode_replay_allowed",
    ):
        if protocol.get(key) is not False:
            raise ValueError(f"PACT-v19 confirmation {key} changed")


def episode_manifest(protocol: dict[str, Any]) -> list[dict[str, Any]]:
    validate_protocol(protocol)
    rows: list[dict[str, Any]] = []
    for seed_index, seed in enumerate(SEEDS):
        for task_index, (task, family) in enumerate(TASK_FAMILIES.items()):
            for level_index, level in enumerate(BUDGET_LEVELS):
                rotation = (seed_index + task_index + level_index) % len(ARMS)
                order = ARMS[rotation:] + ARMS[:rotation]
                for arm_position, method in enumerate(order):
                    budget = ACTION_BUDGETS[level]
                    rows.append(
                        {
                            "episode_index": len(rows),
                            "seed_index": seed_index,
                            "task_index": task_index,
                            "budget_level_index": level_index,
                            "arm_position": arm_position,
                            "task": task,
                            "family_group": family,
                            "budget_level": level,
                            "seed": seed,
                            "maximum_gui_actions": budget,
                            "method": method,
                            "episode_id": f"{task}__seed{seed}__{level}{budget}__{method}",
                        }
                    )
    if len(rows) != expected_episodes():
        raise ValueError("PACT-v19 confirmation manifest is incomplete")
    if len({row["episode_id"] for row in rows}) != len(rows):
        raise ValueError("PACT-v19 confirmation manifest is duplicated")
    return rows


def arm_order_counts(protocol: dict[str, Any]) -> dict[str, dict[int, int]]:
    counts = {arm: Counter() for arm in ARMS}
    for row in episode_manifest(protocol):
        counts[row["method"]][int(row["arm_position"])] += 1
    return {arm: dict(sorted(values.items())) for arm, values in counts.items()}


def _runtime_halt(row: dict[str, Any]) -> bool:
    return bool(row.get("metrics", {}).get("runtime_halted"))


def _closed_success(row: dict[str, Any]) -> bool:
    return bool(row.get("success")) and _active_count(row) == 0 and (not _runtime_halt(row))


def _family_closed_successes(rows: tuple[dict[str, Any], ...], method: str) -> dict[str, int]:
    return {
        family: sum(
            (
                _closed_success(row)
                for row in rows
                if row.get("episode", {}).get("method") == method
                and row.get("episode", {}).get("family_group") == family
            )
        )
        for family in TASK_FAMILIES.values()
    }


def _primary_comparison(rows: tuple[dict[str, Any], ...]) -> dict[str, Any]:
    normalized = []
    for row in rows:
        episode = row.get("episode", {})
        if episode.get("method") not in (FULL_METHOD, SAFE_BASELINE):
            continue
        normalized.append(
            {
                "method": episode.get("method"),
                "task": f"{episode.get('family_group')}::{episode.get('budget_level')}",
                "seed": episode.get("seed"),
                "success": _closed_success(row),
                "infrastructure_failure": bool(row.get("infrastructure_failure")),
            }
        )
    comparison = paired_binary_comparison(
        normalized,
        full_method=FULL_METHOD,
        baseline=SAFE_BASELINE,
        bootstrap_samples=BOOTSTRAP_SAMPLES,
        bootstrap_seed=BOOTSTRAP_SEED,
    )
    comparison["exact_mcnemar_one_sided_full_greater_p"] = exact_paired_greater(
        comparison["discordant_full_success_baseline_failure"],
        comparison["discordant_full_failure_baseline_success"],
    )
    stack_family = _family_closed_successes(rows, FULL_METHOD)
    safe_family = _family_closed_successes(rows, SAFE_BASELINE)
    family_denominator = len(SEEDS) * len(BUDGET_LEVELS)
    comparison["observed_task_family_differences"] = {
        family: (stack_family[family] - safe_family[family]) / family_denominator
        for family in TASK_FAMILIES.values()
    }
    return comparison


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
    family_closed = {arm: _family_closed_successes(rows, arm) for arm in ARMS}
    comparison: dict[str, Any] | None = None
    if exact_manifest:
        comparison = _primary_comparison(rows)
    stack = metrics[FULL_METHOD]
    local = metrics[LOCAL_ABLATION]
    safe = metrics[SAFE_BASELINE]
    net_paired = int(comparison["net_paired_successes"]) if comparison else -1
    one_sided_p = float(comparison["exact_mcnemar_one_sided_full_greater_p"]) if comparison else 1.0
    bootstrap_lower = float(comparison["bootstrap_95_percent_ci"][0]) if comparison else float("-inf")
    safe_cap_events = sum(
        (
            _metric(row, "single_obligation_cap_events")
            for row in rows
            if row.get("episode", {}).get("method") == SAFE_BASELINE
        )
    )
    checks = _rows_confirmation_checks(
        all_claims_complete=all_claims_complete,
        bootstrap_lower=bootstrap_lower,
        exact_manifest=exact_manifest,
        family_closed=family_closed,
        local=local,
        metrics=metrics,
        net_paired=net_paired,
        one_sided_p=one_sided_p,
        protocol=protocol,
        rows=rows,
        safe=safe,
        safe_cap_events=safe_cap_events,
        stack=stack,
    )
    by_task_budget = _aggregate_by_task_budget(rows)
    return {
        "claim_status": PURPOSE["claim_status"],
        "exact_manifest": exact_manifest,
        "all_claims_complete": all_claims_complete,
        "metrics": metrics,
        "family_closed_successes": family_closed,
        "safe_control_cap_events": safe_cap_events,
        "primary_comparison": comparison,
        "checks": checks,
        "passed": all(checks.values()),
        "by_task_budget": by_task_budget,
    }


__all__ = [
    "ACTION_BUDGETS",
    "ARMS",
    "CANDIDATE",
    "CONFIRMATION_GATES",
    "DECISION_RULE",
    "DRIVERS",
    "FULL_METHOD",
    "LOCAL_ABLATION",
    "PRIMARY_ANALYSIS",
    "PREREGISTRATION",
    "SAFE_BASELINE",
    "SEEDS",
    "analyze_rows",
    "arm_order_counts",
    "build_protocol",
    "episode_manifest",
    "expected_episodes",
    "validate_protocol",
]


def _rows_confirmation_checks(
    *,
    all_claims_complete: bool,
    bootstrap_lower: Any,
    exact_manifest: bool,
    family_closed: Any,
    local: Any,
    metrics: Any,
    net_paired: Any,
    one_sided_p: Any,
    protocol: Any,
    rows: tuple[dict[str, Any], ...],
    safe: Any,
    safe_cap_events: Any,
    stack: Any,
) -> dict[str, bool]:
    """Apply the registered decision gates to computed outcomes."""
    return {
        "complete_exact_grid": exact_manifest and all_claims_complete,
        "zero_infrastructure_failures": all(
            (values["infrastructure_failures"] == 0 for values in metrics.values())
        ),
        "planner_is_exercised": sum((values["planner_actual_calls"] for values in metrics.values())) > 0,
        "all_rows_respect_hard_budgets": _all_rows_respect_budgets(rows, protocol),
        "minimum_stack_closed_successes": stack["closed_successes"]
        >= CONFIRMATION_GATES["minimum_stack_closed_successes"],
        "minimum_stack_closed_successes_per_family": all(
            (
                value >= CONFIRMATION_GATES["minimum_stack_closed_successes_per_family"]
                for value in family_closed[FULL_METHOD].values()
            )
        ),
        "minimum_net_paired_closed_successes": net_paired
        >= CONFIRMATION_GATES["minimum_net_paired_closed_successes"],
        "maximum_one_sided_exact_p": one_sided_p <= CONFIRMATION_GATES["maximum_one_sided_exact_p"],
        "bootstrap_lower_bound_strictly_positive": bootstrap_lower > 0.0,
        "stack_has_zero_failed_stop_stranding": stack["failed_stop_stranding_episodes"] == 0,
        "stack_has_zero_runtime_halts": stack["runtime_halt_episodes"] == 0,
        "stack_restorations_all_pass": stack["rows_with_failed_restoration"] == 0,
        "stack_has_zero_unsafe_local_admissions": stack["unsafe_local_admissions"] == 0,
        "stack_has_zero_v19_scope_failures": stack["certified_scope_consumption_failures_v19"] == 0,
        "stack_closes_every_success": stack["closed_successes"] == stack["task_successes"],
        "stack_goal_mutation_discharge_activates": stack["goal_mutation_consumption_passes_v19"] > 0,
        "stack_reserve_rejection_activates": stack["reserve_rejections"] > 0,
        "local_has_zero_v19_scope_failures": local["certified_scope_consumption_failures_v19"] == 0,
        "local_unsafe_boundary_activates": local["unsafe_local_admissions"] > 0,
        "safe_control_has_zero_failed_stop_stranding": safe["failed_stop_stranding_episodes"] == 0,
        "safe_control_has_zero_runtime_halts": safe["runtime_halt_episodes"] == 0,
        "safe_control_restorations_all_pass": safe["rows_with_failed_restoration"] == 0,
        "safe_control_has_zero_v19_scope_failures": safe["certified_scope_consumption_failures_v19"] == 0,
        "safe_control_closes_every_success": safe["closed_successes"] == safe["task_successes"],
        "safe_control_cap_activates": safe_cap_events > 0,
    }


def _aggregate_by_task_budget(rows: tuple[dict[str, Any], ...]) -> list[dict[str, Any]]:
    by_task_budget = []
    for task, family in TASK_FAMILIES.items():
        for level in BUDGET_LEVELS:
            by_task_budget.append(
                {
                    "task": task,
                    "family_group": family,
                    "budget_level": level,
                    "maximum_gui_actions": ACTION_BUDGETS[level],
                    "arms": {
                        arm: summarize_rows(
                            (
                                row
                                for row in rows
                                if row.get("episode", {}).get("task") == task
                                and row.get("episode", {}).get("budget_level") == level
                                and (row.get("episode", {}).get("method") == arm)
                            )
                        )
                        for arm in ARMS
                    },
                }
            )
    return by_task_budget
