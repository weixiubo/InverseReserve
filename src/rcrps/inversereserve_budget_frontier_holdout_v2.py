"""Frozen independent budget-frontier holdout for InverseReserve.

This successor answers the post-review question with externally observable,
mutually separated outcomes. It never treats the method's own admission rule
as success and replaces the degenerate abstention control with a depth-one
act-then-restore policy on the identical runtime.
"""

from __future__ import annotations

from collections import Counter
from typing import Any, Iterable

from . import inversereserve_postreview_development_v1 as development
from .capacity_reserve_drivers_v18 import (
    ONE_STEP_CAP_EVENT_V18,
    ONE_STEP_RESTORE_V18,
    PROPOSAL_LOCAL_V18,
    STACK_WIDE_V18,
    OneStepRestoreCapacityDriverV18,
    ProposalLocalCapacityDriverV18,
    StackWideCapacityDriverV18,
)
from .inversereserve_capacity_regime_successor_v3 import (
    V16_CLEARANCE_METRICS,
    _all_rows_respect_budgets,
    _restoration_evidence_is_clean,
    certified_scope_discharge_endpoint_v18,
)
from .inversereserve_live_resource_stress_v1 import (
    _active_count,
    _metric,
    _one_sided_sign_pvalue,
)


CANDIDATE = "InverseReserve-budget-frontier-holdout-v2"
STATUS = "sealed_before_any_frontier_seed_reset"
FULL_METHOD = STACK_WIDE_V18
LOCAL_ABLATION = PROPOSAL_LOCAL_V18
SAFE_BASELINE = ONE_STEP_RESTORE_V18
ARMS = (FULL_METHOD, LOCAL_ABLATION, SAFE_BASELINE)
DRIVERS = {
    FULL_METHOD: StackWideCapacityDriverV18,
    LOCAL_ABLATION: ProposalLocalCapacityDriverV18,
    SAFE_BASELINE: OneStepRestoreCapacityDriverV18,
}
SEEDS = tuple(range(31701, 31721))
BUDGET_LEVELS = ("low", "medium", "high")
TASK_BUDGETS = {
    "use-autocomplete-nodelay": {"low": 3, "medium": 4, "high": 5},
    "login-user-popup": {"low": 3, "medium": 5, "high": 7},
    "book-flight-nodelay": {"low": 7, "medium": 14, "high": 21},
    "choose-date-nodelay": {"low": 3, "medium": 8, "high": 16},
}
TASK_FAMILIES = {
    "use-autocomplete-nodelay": "autocomplete",
    "login-user-popup": "login_interrupt",
    "book-flight-nodelay": "flight_composite",
    "choose-date-nodelay": "date_picker_holdout",
}
COMMON_BUDGETS = {"maximum_planner_calls": 3, "maximum_wall_seconds": 60.0}
GENERATION = {"enable_thinking": False, "do_sample": False, "max_new_tokens": 64}
RUNTIME_DEPLOYMENT = {
    "model_weights_and_dtype_unchanged": True,
    "visible_cuda_devices": 1,
    "cuda_visible_devices": "0",
    "device_map": "auto",
}
SEQUENCE_FAMILY_SIZE = 8
OUTCOME_DEFINITIONS = {
    "official_task_success": "environment-provided binary task success",
    "physical_stranding": (
        "task failure with at least one active typed obligation at episode stop"
    ),
    "verified_restoration": (
        "at least one ordinary or interrupt-clearance restoration attempt, all "
        "attempts verified, and no active typed obligation at episode stop"
    ),
    "runtime_halt": "runtime_halted is true in the sealed episode metrics",
    "work": "GUI actions, typed transactions, and certified commits",
    "reporting_rule": (
        "report every outcome separately and a mutually exclusive terminal-mode "
        "decomposition; do not use solvent_activity_endpoint or unsafe admission "
        "as a success outcome"
    ),
}
PRIMARY_COMPARISON = {
    "name": "budget_frontier_safety_utility_against_depth_one_safe_control",
    "safety": "physical stranding and runtime halt, reported separately",
    "utility": "official task success, reported separately",
    "effort": "typed transactions and GUI actions, reported separately",
    "inferential_unit": "seed cluster across all twelve task-budget cells",
    "comparison": "stack-wide InverseReserve versus one-step-then-restore",
    "multiplicity": (
        "one-sided exact seed-cluster sign test with an eight-look Bonferroni "
        "upper bound covering the retained adaptive sequence"
    ),
}
CONFIRMATION_GATES = {
    "complete_exact_grid": True,
    "zero_infrastructure_failures": True,
    "planner_is_exercised": True,
    "all_rows_respect_hard_budgets": True,
    "stack_has_zero_physical_stranding": True,
    "stack_has_zero_runtime_halts": True,
    "stack_restorations_all_pass": True,
    "safe_baseline_has_zero_physical_stranding": True,
    "safe_baseline_has_zero_runtime_halts": True,
    "safe_baseline_restorations_all_pass": True,
    "safe_baseline_forward_action_cap_holds": True,
    "minimum_safe_baseline_episodes_with_forward_action": 200,
    "minimum_stack_high_budget_task_successes": 70,
    "minimum_stack_task_success_advantage_over_safe_baseline": 60,
    "minimum_stack_typed_transaction_advantage_over_safe_baseline": 80,
    "stack_success_is_nondecreasing_across_budget_levels": True,
    "minimum_local_physical_stranding_families": 2,
    "maximum_eighth_look_adjusted_sign_pvalue": 0.05,
}
DECISION_RULE = {
    "on_pass": (
        "report the independent budget frontier using only the prespecified "
        "separate safety, utility, restoration, halt, and work outcomes"
    ),
    "on_failure": (
        "seal all rows, report the failed gate without outcome exclusions, and "
        "make no positive budget-frontier confirmation claim"
    ),
}


def task_records() -> list[dict[str, Any]]:
    return [
        {
            "task_id": task,
            "family_group": TASK_FAMILIES[task],
            "budget_levels": dict(levels),
        }
        for task, levels in TASK_BUDGETS.items()
    ]


def expected_episodes() -> int:
    cells = sum(len(levels) for levels in TASK_BUDGETS.values())
    return len(ARMS) * len(SEEDS) * cells


def build_protocol(
    *,
    scientific_source_commit: str,
    source_sha256: dict[str, str],
    preregistration_path: str,
    preregistration_sha256: str,
    predecessor: dict[str, Any],
    repositories: dict[str, str],
    created_utc: str,
) -> dict[str, Any]:
    protocol = {
        "candidate": CANDIDATE,
        "status": STATUS,
        "created_utc": created_utc,
        "scientific_source_commit": scientific_source_commit,
        "predecessor": predecessor,
        "sequence_family_size": SEQUENCE_FAMILY_SIZE,
        "adaptive_history_disclosed": True,
        "arms": list(ARMS),
        "isolated_policy_differences": {
            FULL_METHOD: "stack-wide active-plus-proposal inverse reserve",
            LOCAL_ABLATION: "proposal-only inverse reserve",
            SAFE_BASELINE: (
                "stack-wide inverse reserve plus a one-forward-action cap"
            ),
        },
        "tasks": task_records(),
        "fresh_seeds": list(SEEDS),
        "budget_levels": list(BUDGET_LEVELS),
        "common_budgets": dict(COMMON_BUDGETS),
        "generation": dict(GENERATION),
        "runtime_deployment": dict(RUNTIME_DEPLOYMENT),
        "expected_episodes": expected_episodes(),
        "outcome_definitions": dict(OUTCOME_DEFINITIONS),
        "primary_comparison": dict(PRIMARY_COMPARISON),
        "confirmation_gates": dict(CONFIRMATION_GATES),
        "decision_rule": dict(DECISION_RULE),
        "repositories": dict(repositories),
        "source_sha256": dict(sorted(source_sha256.items())),
        "preregistration": {
            "path": preregistration_path,
            "sha256": preregistration_sha256,
        },
        "selection_disclosure": (
            "budgets were fixed from retained earlier diagnostic and natural-task "
            "runs before any seed 31701--31720 reset; choose-date is a new held-out "
            "reserve family for the confirmatory grid"
        ),
        "outcome_based_exclusion_allowed": False,
        "partial_reexecution_allowed": False,
        "episode_replay_allowed": False,
    }
    validate_protocol(protocol)
    return protocol


def validate_protocol(protocol: dict[str, Any]) -> None:
    if protocol.get("candidate") != CANDIDATE or protocol.get("status") != STATUS:
        raise ValueError("unexpected budget-frontier identity")
    if tuple(protocol.get("arms", ())) != ARMS or set(DRIVERS) != set(ARMS):
        raise ValueError("budget-frontier arms changed")
    if protocol.get("tasks") != task_records():
        raise ValueError("budget-frontier task grid changed")
    if tuple(protocol.get("fresh_seeds", ())) != SEEDS:
        raise ValueError("budget-frontier seeds changed")
    if tuple(protocol.get("budget_levels", ())) != BUDGET_LEVELS:
        raise ValueError("budget-frontier levels changed")
    if protocol.get("common_budgets") != COMMON_BUDGETS:
        raise ValueError("budget-frontier common budgets changed")
    if protocol.get("generation") != GENERATION:
        raise ValueError("budget-frontier generation changed")
    if protocol.get("runtime_deployment") != RUNTIME_DEPLOYMENT:
        raise ValueError("budget-frontier deployment changed")
    if protocol.get("expected_episodes") != expected_episodes():
        raise ValueError("budget-frontier episode count changed")
    if protocol.get("outcome_definitions") != OUTCOME_DEFINITIONS:
        raise ValueError("budget-frontier outcomes changed")
    if protocol.get("primary_comparison") != PRIMARY_COMPARISON:
        raise ValueError("budget-frontier primary comparison changed")
    if protocol.get("confirmation_gates") != CONFIRMATION_GATES:
        raise ValueError("budget-frontier gates changed")
    if protocol.get("decision_rule") != DECISION_RULE:
        raise ValueError("budget-frontier decision rule changed")
    if protocol.get("sequence_family_size") != SEQUENCE_FAMILY_SIZE:
        raise ValueError("budget-frontier multiplicity family changed")
    if protocol.get("adaptive_history_disclosed") is not True:
        raise ValueError("budget-frontier adaptive history disclosure changed")
    for key in ("predecessor", "repositories", "source_sha256", "preregistration"):
        if not isinstance(protocol.get(key), dict):
            raise ValueError(f"budget-frontier {key} binding is absent")
    for key in (
        "outcome_based_exclusion_allowed",
        "partial_reexecution_allowed",
        "episode_replay_allowed",
    ):
        if protocol.get(key) is not False:
            raise ValueError(f"budget-frontier {key} changed")


def episode_manifest(protocol: dict[str, Any]) -> list[dict[str, Any]]:
    validate_protocol(protocol)
    rows: list[dict[str, Any]] = []
    for seed_index, seed in enumerate(SEEDS):
        for task_index, (task, levels) in enumerate(TASK_BUDGETS.items()):
            for level_index, (level, budget) in enumerate(levels.items()):
                rotation = (seed_index + task_index + level_index) % len(ARMS)
                order = ARMS[rotation:] + ARMS[:rotation]
                for arm_position, method in enumerate(order):
                    rows.append(
                        {
                            "episode_index": len(rows),
                            "seed_index": seed_index,
                            "task_index": task_index,
                            "budget_level_index": level_index,
                            "arm_position": arm_position,
                            "task": task,
                            "family_group": TASK_FAMILIES[task],
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
        raise ValueError("budget-frontier manifest is incomplete")
    if len({row["episode_id"] for row in rows}) != len(rows):
        raise ValueError("budget-frontier manifest is duplicated")
    return rows


def arm_order_counts(protocol: dict[str, Any]) -> dict[str, dict[int, int]]:
    counts = {arm: Counter() for arm in ARMS}
    for row in episode_manifest(protocol):
        counts[row["method"]][int(row["arm_position"])] += 1
    return {arm: dict(sorted(values.items())) for arm, values in counts.items()}


def physical_stranding(row: dict[str, Any]) -> bool:
    return not bool(row.get("success")) and _active_count(row) > 0


def runtime_halt(row: dict[str, Any]) -> bool:
    return bool(row.get("metrics", {}).get("runtime_halted"))


def verified_restoration(row: dict[str, Any]) -> bool:
    return _restoration_evidence_is_clean(row) and _active_count(row) == 0


def terminal_outcome_mode(row: dict[str, Any]) -> str:
    if bool(row.get("infrastructure_failure")):
        return "infrastructure_failure"
    if bool(row.get("success")):
        return "task_success"
    if physical_stranding(row):
        return "physical_stranding"
    if runtime_halt(row):
        return "runtime_halt_without_stranding"
    if verified_restoration(row):
        return "verified_restoration"
    if certified_scope_discharge_endpoint_v18(row):
        return "certified_scope_discharge"
    return "safe_stop_without_verified_restoration"


def _one_step_cap_events(row: dict[str, Any]) -> int:
    return sum(
        event.get("type") == ONE_STEP_CAP_EVENT_V18
        for event in row.get("trace", ())
    )


def _forward_policy_actions(row: dict[str, Any]) -> int:
    return _metric(row, "typed_transactions") + _metric(row, "certified_commits")


def summarize_rows(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    rows = tuple(rows)
    base = development.summarize_rows(rows)
    modes = Counter(terminal_outcome_mode(row) for row in rows)
    base.update(
        {
            "physical_stranding_episodes": sum(physical_stranding(row) for row in rows),
            "runtime_halt_episodes": sum(runtime_halt(row) for row in rows),
            "verified_restoration_episodes": sum(
                verified_restoration(row) for row in rows
            ),
            "certified_scope_discharge_episodes": sum(
                certified_scope_discharge_endpoint_v18(row) for row in rows
            ),
            "one_step_cap_events": sum(_one_step_cap_events(row) for row in rows),
            "forward_policy_actions": sum(_forward_policy_actions(row) for row in rows),
            "episodes_with_forward_action": sum(
                _forward_policy_actions(row) > 0 for row in rows
            ),
            "terminal_outcome_modes": dict(sorted(modes.items())),
        }
    )
    for name in V16_CLEARANCE_METRICS:
        base[name] = sum(_metric(row, name) for row in rows)
    return base


def _all_attempted_restorations_pass(summary: dict[str, Any]) -> bool:
    legacy_attempts = int(summary["restoration_attempts"])
    clearance_attempts = int(
        summary["interrupt_clearance_restoration_attempts_v16"]
    )
    return (
        legacy_attempts + clearance_attempts > 0
        and int(summary["restoration_passes"]) == legacy_attempts
        and int(summary["interrupt_clearance_restoration_passes_v16"])
        == clearance_attempts
    )


def _paired_success(rows: tuple[dict[str, Any], ...]) -> dict[str, Any]:
    indexed = {
        (
            row["episode"]["task"],
            row["episode"]["budget_level"],
            int(row["episode"]["seed"]),
            row["episode"]["method"],
        ): row
        for row in rows
    }
    seed_rows = []
    cell_wins = cell_losses = cell_ties = 0
    for seed in SEEDS:
        wins = losses = ties = 0
        for task in TASK_BUDGETS:
            for level in BUDGET_LEVELS:
                full = bool(indexed[(task, level, seed, FULL_METHOD)].get("success"))
                safe = bool(indexed[(task, level, seed, SAFE_BASELINE)].get("success"))
                if full and not safe:
                    wins += 1
                    cell_wins += 1
                elif safe and not full:
                    losses += 1
                    cell_losses += 1
                else:
                    ties += 1
                    cell_ties += 1
        seed_rows.append({"seed": seed, "wins": wins, "losses": losses, "ties": ties})
    seed_wins = sum(row["wins"] > row["losses"] for row in seed_rows)
    seed_losses = sum(row["wins"] < row["losses"] for row in seed_rows)
    seed_ties = len(seed_rows) - seed_wins - seed_losses
    pvalue = _one_sided_sign_pvalue(seed_wins, seed_losses)
    return {
        "cell_wins": cell_wins,
        "cell_losses": cell_losses,
        "cell_ties": cell_ties,
        "seed_cluster_wins": seed_wins,
        "seed_cluster_losses": seed_losses,
        "seed_cluster_ties": seed_ties,
        "one_sided_exact_sign_pvalue": pvalue,
        "sequence_family_size": SEQUENCE_FAMILY_SIZE,
        "sequence_adjusted_pvalue_upper_bound": min(
            1.0, pvalue * SEQUENCE_FAMILY_SIZE
        ),
        "seed_rows": seed_rows,
    }


def _stack_success_nondecreasing(rows: tuple[dict[str, Any], ...]) -> bool:
    for task in TASK_BUDGETS:
        counts = []
        for level in BUDGET_LEVELS:
            counts.append(
                sum(
                    bool(row.get("success"))
                    for row in rows
                    if row.get("episode", {}).get("method") == FULL_METHOD
                    and row.get("episode", {}).get("task") == task
                    and row.get("episode", {}).get("budget_level") == level
                )
            )
        if counts != sorted(counts):
            return False
    return True


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
    by_task_budget = []
    for task, levels in TASK_BUDGETS.items():
        for level, budget in levels.items():
            by_task_budget.append(
                {
                    "task": task,
                    "family_group": TASK_FAMILIES[task],
                    "budget_level": level,
                    "maximum_gui_actions": budget,
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
    paired = _paired_success(rows) if exact_manifest else None
    full = metrics[FULL_METHOD]
    local = metrics[LOCAL_ABLATION]
    safe = metrics[SAFE_BASELINE]
    high_successes = sum(
        bool(row.get("success"))
        for row in rows
        if row.get("episode", {}).get("method") == FULL_METHOD
        and row.get("episode", {}).get("budget_level") == "high"
    )
    local_stranding_families = sum(
        any(
            physical_stranding(row)
            for row in rows
            if row.get("episode", {}).get("method") == LOCAL_ABLATION
            and row.get("episode", {}).get("family_group") == family
        )
        for family in TASK_FAMILIES.values()
    )
    safe_rows = tuple(
        row
        for row in rows
        if row.get("episode", {}).get("method") == SAFE_BASELINE
    )
    gates = protocol["confirmation_gates"]
    checks = {
        "complete_exact_grid": exact_manifest and bool(all_claims_complete),
        "zero_infrastructure_failures": sum(
            value["infrastructure_failures"] for value in metrics.values()
        )
        == 0,
        "planner_is_exercised": sum(value["planner_calls"] for value in metrics.values())
        > 0,
        "all_rows_respect_hard_budgets": _all_rows_respect_budgets(rows, protocol),
        "stack_has_zero_physical_stranding": full["physical_stranding_episodes"] == 0,
        "stack_has_zero_runtime_halts": full["runtime_halt_episodes"] == 0,
        "stack_restorations_all_pass": _all_attempted_restorations_pass(full),
        "safe_baseline_has_zero_physical_stranding": (
            safe["physical_stranding_episodes"] == 0
        ),
        "safe_baseline_has_zero_runtime_halts": safe["runtime_halt_episodes"] == 0,
        "safe_baseline_restorations_all_pass": _all_attempted_restorations_pass(safe),
        "safe_baseline_forward_action_cap_holds": all(
            _forward_policy_actions(row) <= 1 for row in safe_rows
        ),
        "minimum_safe_baseline_episodes_with_forward_action": (
            safe["episodes_with_forward_action"]
            >= int(gates["minimum_safe_baseline_episodes_with_forward_action"])
        ),
        "minimum_stack_high_budget_task_successes": (
            high_successes >= int(gates["minimum_stack_high_budget_task_successes"])
        ),
        "minimum_stack_task_success_advantage_over_safe_baseline": (
            full["task_successes"] - safe["task_successes"]
            >= int(gates["minimum_stack_task_success_advantage_over_safe_baseline"])
        ),
        "minimum_stack_typed_transaction_advantage_over_safe_baseline": (
            full["typed_transactions"] - safe["typed_transactions"]
            >= int(
                gates["minimum_stack_typed_transaction_advantage_over_safe_baseline"]
            )
        ),
        "stack_success_is_nondecreasing_across_budget_levels": (
            _stack_success_nondecreasing(rows)
        ),
        "minimum_local_physical_stranding_families": (
            local_stranding_families
            >= int(gates["minimum_local_physical_stranding_families"])
        ),
        "maximum_eighth_look_adjusted_sign_pvalue": bool(
            paired
            and paired["sequence_adjusted_pvalue_upper_bound"]
            <= float(gates["maximum_eighth_look_adjusted_sign_pvalue"])
        ),
    }
    return {
        "exact_manifest": exact_manifest,
        "all_claims_complete": bool(all_claims_complete),
        "arm_order_counts": arm_order_counts(protocol),
        "metrics": metrics,
        "by_task_budget": by_task_budget,
        "paired_stack_vs_safe_task_success": paired,
        "stack_high_budget_task_successes": high_successes,
        "local_physical_stranding_families": local_stranding_families,
        "checks": checks,
        "passed": all(checks.values()),
    }


__all__ = [
    "ARMS",
    "BUDGET_LEVELS",
    "CANDIDATE",
    "COMMON_BUDGETS",
    "CONFIRMATION_GATES",
    "DECISION_RULE",
    "DRIVERS",
    "FULL_METHOD",
    "GENERATION",
    "LOCAL_ABLATION",
    "OUTCOME_DEFINITIONS",
    "PRIMARY_COMPARISON",
    "RUNTIME_DEPLOYMENT",
    "SAFE_BASELINE",
    "SEEDS",
    "SEQUENCE_FAMILY_SIZE",
    "STATUS",
    "TASK_BUDGETS",
    "TASK_FAMILIES",
    "analyze_rows",
    "arm_order_counts",
    "build_protocol",
    "episode_manifest",
    "expected_episodes",
    "physical_stranding",
    "runtime_halt",
    "summarize_rows",
    "task_records",
    "terminal_outcome_mode",
    "validate_protocol",
    "verified_restoration",
]
