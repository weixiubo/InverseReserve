"""Frozen reviewer-driven strong-control study for the PACT-v19 method.

The study is prospective with respect to seeds 36101--36120, but adaptive with
respect to the broader project: three PDF-only reviews selected the dynamic
comparators after the sealed PACT-v19 study.  It therefore never calls itself
an independent confirmation or a replacement for the failed v19 omnibus gate.
"""

from __future__ import annotations

from collections import Counter
from typing import Any, Iterable

from .capacity_reserve_drivers_v18 import RESERVATION_EVENT_V18
from .capacity_reserve_drivers_v19 import (
    STACK_WIDE_V19,
    StackWideCapacityDriverV19,
)
from .capacity_safe_dynamic_controls_v19 import (
    COMPLETE_CLEANUP_REPLAN_V19,
    TOP_CLEANUP_REPLAN_V19,
    CompleteCleanupReplanDriverV19,
    TopCleanupReplanDriverV19,
)
from .confirmation_statistics_v7 import holm_rejections
from .external_statistics import exact_mcnemar
from .inversereserve_capacity_regime_successor_v3 import (
    _all_rows_respect_budgets,
)
from .inversereserve_live_resource_stress_v1 import _active_count, _metric
from .inversereserve_v19_unified_development_v1 import (
    ACTION_BUDGETS,
    BUDGET_LEVELS,
    COMMON_BUDGETS,
    GENERATION,
    OUTCOME_DEFINITIONS,
    TASK_FAMILIES,
)
from .pact_statistics import paired_binary_comparison


CANDIDATE = "InverseReserve-strong-control-successor-v1"
STATUS = "reviewer_driven_frozen_before_any_36101_through_36120_reset"
FULL_METHOD = STACK_WIDE_V19
COMPLETE_CONTROL = COMPLETE_CLEANUP_REPLAN_V19
TOP_CONTROL = TOP_CLEANUP_REPLAN_V19
CONTROLS = (COMPLETE_CONTROL, TOP_CONTROL)
ARMS = (FULL_METHOD, *CONTROLS)
DRIVERS = {
    FULL_METHOD: StackWideCapacityDriverV19,
    COMPLETE_CONTROL: CompleteCleanupReplanDriverV19,
    TOP_CONTROL: TopCleanupReplanDriverV19,
}
SEEDS = tuple(range(36101, 36121))
BOOTSTRAP_SAMPLES = 50_000
BOOTSTRAP_SEED = 270_731
ALPHA = 0.05
PREREGISTRATION = {
    "path": (
        "paper/aaai27/notes/"
        "2026-07-23_inversereserve_strong_control_successor_v1_preregistration.md"
    ),
    "sha256": (
        "00217942824ce23a48d92e87942b53248c16e4a3b25e07a855e4a84ac96778ad"
    ),
}
PURPOSE = {
    "claim_status": "prospective_reviewer_driven_strong_control_successor",
    "confirmation_status": "not_independent_confirmation_or_v19_replacement",
    "method_status": "unchanged frozen PACT-v19 method",
    "question": (
        "how persistent stack-wide admission compares with complete-stack and "
        "one-top cleanup-and-replan safe policies in the same broad population"
    ),
    "selection_disclosure": (
        "dynamic controls selected after three blank-context PDF-only reviews"
    ),
    "outcome_based_exclusion_allowed": False,
}
PRIMARY_ANALYSIS = {
    "endpoint": "closed_success",
    "paired_unit": "task_horizon_seed_cell",
    "cluster_unit": "seed_shared_across_all_18_task_horizon_strata",
    "full_method": FULL_METHOD,
    "controls": list(CONTROLS),
    "bootstrap_samples": BOOTSTRAP_SAMPLES,
    "bootstrap_seed": BOOTSTRAP_SEED,
    "seed_aggregate_test": "two_sided_exact_sign",
    "multiplicity": "Holm_step_down_over_two_frozen_dynamic_controls",
    "alpha": ALPHA,
    "efficacy_gate": "none_report_complete_comparison_regardless_of_direction",
}
VALIDITY_GATES = {
    "complete_exact_grid": True,
    "zero_infrastructure_failures": True,
    "planner_is_exercised": True,
    "all_rows_respect_hard_budgets": True,
    "all_policies_zero_failed_stop_stranding": True,
    "all_policies_zero_runtime_halts": True,
    "all_policy_restorations_pass": True,
    "all_policies_zero_v19_scope_failures": True,
    "all_successes_are_closed": True,
    "stack_goal_mutation_discharge_activates": True,
    "stack_reserve_rejection_activates": True,
    "complete_cleanup_policy_activates_and_passes": True,
    "top_cleanup_policy_activates_and_passes": True,
}
DECISION_RULE = {
    "on_pass": (
        "report the complete reviewer-driven strong-control comparison "
        "regardless of effect direction while retaining v19's failed status"
    ),
    "on_failure": (
        "seal every opened row, report failed validity gates, and make no "
        "positive strong-control claim"
    ),
}
RUNTIME_DEPLOYMENT = {
    "model_weights_and_dtype_unchanged": True,
    "visible_cuda_devices": 1,
    "cuda_visible_devices": "1",
    "device_map": "auto",
}


def task_records() -> list[dict[str, Any]]:
    return [
        {
            "task_id": task,
            "family_group": family,
            "budget_levels": dict(ACTION_BUDGETS),
        }
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
        "isolated_policy_differences": {
            FULL_METHOD: "persistent stack-wide active-plus-proposal reserve",
            COMPLETE_CONTROL: (
                "restore the complete live LIFO stack and replan before a "
                "requested transaction"
            ),
            TOP_CONTROL: (
                "after a stack-wide capacity rejection, restore one top "
                "obligation and replan"
            ),
        },
        "tasks": task_records(),
        "successor_seeds": list(SEEDS),
        "budget_levels": list(BUDGET_LEVELS),
        "uniform_action_budgets": dict(ACTION_BUDGETS),
        "common_budgets": dict(COMMON_BUDGETS),
        "generation": dict(GENERATION),
        "runtime_deployment": dict(RUNTIME_DEPLOYMENT),
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
        raise ValueError("unexpected strong-control successor identity")
    if tuple(protocol.get("arms", ())) != ARMS or set(DRIVERS) != set(ARMS):
        raise ValueError("strong-control successor arms changed")
    if protocol.get("tasks") != task_records():
        raise ValueError("strong-control successor task grid changed")
    if tuple(protocol.get("successor_seeds", ())) != SEEDS:
        raise ValueError("strong-control successor seeds changed")
    if tuple(protocol.get("budget_levels", ())) != BUDGET_LEVELS:
        raise ValueError("strong-control successor budget levels changed")
    if protocol.get("uniform_action_budgets") != ACTION_BUDGETS:
        raise ValueError("strong-control successor horizons changed")
    if protocol.get("common_budgets") != COMMON_BUDGETS:
        raise ValueError("strong-control successor common budgets changed")
    if protocol.get("generation") != GENERATION:
        raise ValueError("strong-control successor generation changed")
    if protocol.get("runtime_deployment") != RUNTIME_DEPLOYMENT:
        raise ValueError("strong-control successor deployment changed")
    fixed = {
        "purpose": PURPOSE,
        "preregistration": PREREGISTRATION,
        "primary_analysis": PRIMARY_ANALYSIS,
        "validity_gates": VALIDITY_GATES,
        "decision_rule": DECISION_RULE,
        "outcome_definitions": OUTCOME_DEFINITIONS,
    }
    for key, value in fixed.items():
        if protocol.get(key) != value:
            raise ValueError(f"strong-control successor {key} changed")
    if protocol.get("expected_episodes") != expected_episodes():
        raise ValueError("strong-control successor episode count changed")
    for key in ("predecessor", "repositories", "source_sha256"):
        if not isinstance(protocol.get(key), dict):
            raise ValueError(f"strong-control successor {key} binding is absent")
    for key in (
        "outcome_based_exclusion_allowed",
        "partial_reexecution_allowed",
        "completed_episode_replay_allowed",
    ):
        if protocol.get(key) is not False:
            raise ValueError(f"strong-control successor {key} changed")


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
                            "episode_id": (
                                f"{task}__seed{seed}__{level}{budget}__{method}"
                            ),
                        }
                    )
    if len(rows) != expected_episodes():
        raise ValueError("strong-control successor manifest is incomplete")
    if len({row["episode_id"] for row in rows}) != len(rows):
        raise ValueError("strong-control successor manifest is duplicated")
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


def summarize_rows(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    rows = tuple(rows)
    return {
        "episodes": len(rows),
        "task_successes": sum(bool(row.get("success")) for row in rows),
        "closed_successes": sum(_closed_success(row) for row in rows),
        "successes_with_active_obligations": sum(
            bool(row.get("success")) and _active_count(row) > 0 for row in rows
        ),
        "closed_success_families": len(
            {
                str(row.get("episode", {}).get("family_group"))
                for row in rows
                if _closed_success(row)
            }
        ),
        "failed_stop_stranding_episodes": sum(
            _failed_stop_stranding(row) for row in rows
        ),
        "runtime_halt_episodes": sum(_runtime_halt(row) for row in rows),
        "rows_with_failed_restoration": sum(
            not _all_restorations_pass(row) for row in rows
        ),
        "reserve_rejections": sum(_reserve_rejections(row) for row in rows),
        "goal_mutation_consumption_passes_v19": sum(
            _metric(row, "goal_mutation_consumption_passes_v19") for row in rows
        ),
        "certified_scope_consumption_failures_v19": sum(
            _metric(row, "certified_scope_consumption_failures_v19")
            for row in rows
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
        "complete_cleanup_attempts": sum(
            _metric(row, "complete_cleanup_attempts") for row in rows
        ),
        "complete_cleanup_passes": sum(
            _metric(row, "complete_cleanup_passes") for row in rows
        ),
        "complete_cleanup_failures": sum(
            _metric(row, "complete_cleanup_failures") for row in rows
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
        "top_cleanup_preserved_lower_events": sum(
            _metric(row, "top_cleanup_preserved_lower_events") for row in rows
        ),
    }


def _seed_comparison(
    rows: tuple[dict[str, Any], ...], control: str
) -> dict[str, Any]:
    seed_rows = []
    wins = losses = ties = 0
    for seed in SEEDS:
        stack = sum(
            _closed_success(row)
            for row in rows
            if row.get("episode", {}).get("seed") == seed
            and row.get("episode", {}).get("method") == FULL_METHOD
        )
        baseline = sum(
            _closed_success(row)
            for row in rows
            if row.get("episode", {}).get("seed") == seed
            and row.get("episode", {}).get("method") == control
        )
        wins += stack > baseline
        losses += stack < baseline
        ties += stack == baseline
        seed_rows.append(
            {
                "seed": seed,
                "stack_closed": stack,
                "control_closed": baseline,
                "difference": stack - baseline,
            }
        )
    return {
        "control": control,
        "seed_cluster_wins": wins,
        "seed_cluster_losses": losses,
        "seed_cluster_ties": ties,
        "two_sided_exact_sign_p": exact_mcnemar(wins, losses),
        "seed_rows": seed_rows,
    }


def _comparisons(rows: tuple[dict[str, Any], ...]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    p_values: dict[str, float] = {}
    normalized = [
        {
            "method": row.get("episode", {}).get("method"),
            "task": (
                f"{row.get('episode', {}).get('family_group')}::"
                f"{row.get('episode', {}).get('budget_level')}"
            ),
            "seed": row.get("episode", {}).get("seed"),
            "success": _closed_success(row),
            "infrastructure_failure": bool(row.get("infrastructure_failure")),
        }
        for row in rows
    ]
    for offset, control in enumerate(CONTROLS):
        cell = paired_binary_comparison(
            normalized,
            full_method=FULL_METHOD,
            baseline=control,
            bootstrap_samples=BOOTSTRAP_SAMPLES,
            bootstrap_seed=BOOTSTRAP_SEED + offset,
        )
        seed = _seed_comparison(rows, control)
        output[control] = {
            "seed_cluster_primary": seed,
            "paired_cell_sensitivity_and_cluster_bootstrap": cell,
        }
        p_values[control] = float(seed["two_sided_exact_sign_p"])
    holm = holm_rejections(p_values, alpha=ALPHA)
    for control in CONTROLS:
        output[control]["holm_seed_cluster"] = holm[control]
    return {
        "full_method": FULL_METHOD,
        "controls": list(CONTROLS),
        "comparisons": output,
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
    stack = metrics[FULL_METHOD]
    complete = metrics[COMPLETE_CONTROL]
    top = metrics[TOP_CONTROL]
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
        "all_policies_zero_failed_stop_stranding": all(
            values["failed_stop_stranding_episodes"] == 0
            for values in metrics.values()
        ),
        "all_policies_zero_runtime_halts": all(
            values["runtime_halt_episodes"] == 0 for values in metrics.values()
        ),
        "all_policy_restorations_pass": all(
            values["rows_with_failed_restoration"] == 0
            for values in metrics.values()
        ),
        "all_policies_zero_v19_scope_failures": all(
            values["certified_scope_consumption_failures_v19"] == 0
            for values in metrics.values()
        ),
        "all_successes_are_closed": all(
            values["closed_successes"] == values["task_successes"]
            for values in metrics.values()
        ),
        "stack_goal_mutation_discharge_activates": (
            stack["goal_mutation_consumption_passes_v19"] > 0
        ),
        "stack_reserve_rejection_activates": stack["reserve_rejections"] > 0,
        "complete_cleanup_policy_activates_and_passes": (
            complete["complete_cleanup_attempts"] > 0
            and complete["complete_cleanup_passes"]
            == complete["complete_cleanup_attempts"]
            and complete["complete_cleanup_failures"] == 0
        ),
        "top_cleanup_policy_activates_and_passes": (
            top["top_cleanup_attempts"] > 0
            and top["top_cleanup_passes"] == top["top_cleanup_attempts"]
            and top["top_cleanup_failures"] == 0
        ),
    }
    by_task_horizon = []
    for task, family in TASK_FAMILIES.items():
        for level in BUDGET_LEVELS:
            by_task_horizon.append(
                {
                    "task": task,
                    "family_group": family,
                    "budget_level": level,
                    "maximum_gui_actions": ACTION_BUDGETS[level],
                    "arms": {
                        arm: summarize_rows(
                            row
                            for row in rows
                            if row.get("episode", {}).get("task") == task
                            and row.get("episode", {}).get("budget_level") == level
                            and row.get("episode", {}).get("method") == arm
                        )
                        for arm in ARMS
                    },
                }
            )
    comparisons = _comparisons(rows) if exact_manifest else None
    return {
        "claim_status": PURPOSE["claim_status"],
        "confirmation_status": PURPOSE["confirmation_status"],
        "exact_manifest": exact_manifest,
        "all_claims_complete": all_claims_complete,
        "metrics": metrics,
        "comparisons": comparisons,
        "checks": checks,
        "passed": all(checks.values()),
        "by_task_horizon": by_task_horizon,
    }


__all__ = [
    "ACTION_BUDGETS",
    "ARMS",
    "CANDIDATE",
    "COMPLETE_CONTROL",
    "CONTROLS",
    "DECISION_RULE",
    "DRIVERS",
    "FULL_METHOD",
    "PRIMARY_ANALYSIS",
    "PURPOSE",
    "SEEDS",
    "STATUS",
    "TOP_CONTROL",
    "VALIDITY_GATES",
    "analyze_rows",
    "arm_order_counts",
    "build_protocol",
    "episode_manifest",
    "expected_episodes",
    "summarize_rows",
    "validate_protocol",
]
