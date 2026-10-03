from __future__ import annotations

from collections import Counter
from typing import Any, Iterable

from inversereserve.controllers.capacity_reserve_drivers_v18 import STACK_WIDE_V18, StackWideCapacityDriverV18
from inversereserve.controllers.cleanup_replan_capacity_driver_v1 import (
    CLEANUP_REPLAN_POLICY_EVENT_V1,
    DEMAND_CLEANUP_REPLAN_V1,
    DemandCleanupReplanDriverV1,
)
from inversereserve.studies import inversereserve_budget_frontier_holdout_v2 as frontier
from inversereserve.studies import inversereserve_postreview_development_v1 as development
from inversereserve.studies.episode_grid import matches_registered_grid
from inversereserve.studies.inversereserve_capacity_regime_successor_v3 import (
    V16_CLEARANCE_METRICS,
    _all_rows_respect_budgets,
    _restoration_evidence_is_clean,
    certified_scope_discharge_endpoint_v18,
)
from inversereserve.studies.inversereserve_live_resource_stress_v1 import (
    _active_count,
    _metric,
    _one_sided_sign_pvalue,
)
from inversereserve.studies.validation import require

"Frozen cleanup-and-replan successor for InverseReserve.\n\nThis tenth adaptive look was selected after a clean simulated-review panel.\nIt compares InverseReserve against an otherwise identical safe controller that\nrestores its complete registered LIFO stack when a requested transaction meets\nlive obligations, then replans from the realized post-cleanup public state.\n"
CANDIDATE = "InverseReserve-cleanup-replan-successor-v1"
STATUS = "sealed_before_any_cleanup_replan_seed_reset"
FULL_METHOD = STACK_WIDE_V18
SAFE_BASELINE = DEMAND_CLEANUP_REPLAN_V1
ARMS = (FULL_METHOD, SAFE_BASELINE)
DRIVERS = {FULL_METHOD: StackWideCapacityDriverV18, SAFE_BASELINE: DemandCleanupReplanDriverV1}
SEEDS = tuple(range(31901, 31921))
BUDGET_LEVELS = tuple(frontier.BUDGET_LEVELS)
TASK_BUDGETS = {task: dict(levels) for task, levels in frontier.TASK_BUDGETS.items()}
TASK_FAMILIES = dict(frontier.TASK_FAMILIES)
COMMON_BUDGETS = dict(frontier.COMMON_BUDGETS)
GENERATION = dict(frontier.GENERATION)
RUNTIME_DEPLOYMENT = dict(frontier.RUNTIME_DEPLOYMENT)
SEQUENCE_FAMILY_SIZE = 10
OUTCOME_DEFINITIONS = {
    "official_task_success": "environment-provided binary task success",
    "closed_task_success": "official task success with no active typed obligation at episode stop",
    "physical_stranding": "task failure with at least one active typed obligation at episode stop",
    "verified_restoration": "at least one ordinary or interrupt-clearance restoration attempt, all attempts verified, and no active typed obligation at episode stop",
    "runtime_halt": "runtime_halted is true in the sealed episode metrics",
    "cleanup_replan_policy": "when a transact proposal meets live obligations, restore the complete registered LIFO stack, discard the stale proposal, and replan from the realized public state",
    "reporting_rule": "report official success, failed-stop stranding, runtime halt, verified restoration, work, and successful-stop active obligations separately",
}
PRIMARY_COMPARISON = {
    "name": "stack_wide_against_demand_cleanup_replan_safe_control",
    "safety": "failed-stop physical stranding and runtime halt, separately",
    "utility": "closed task success; official task success is secondary",
    "effort": "typed transactions and GUI actions",
    "inferential_unit": "fresh-seed cluster across all twelve task-budget cells",
    "comparison": "stack-wide InverseReserve versus an identical stack-wide runtime that restores live obligations and replans before a conflicting proposal",
    "multiplicity": "one-sided exact seed-cluster sign test on closed success with a ten-look Bonferroni upper bound covering the retained adaptive sequence",
}
CONFIRMATION_GATES = {
    "complete_exact_grid": True,
    "zero_infrastructure_failures": True,
    "planner_is_exercised": True,
    "all_rows_respect_hard_budgets": True,
    "stack_has_zero_physical_stranding": True,
    "stack_has_zero_runtime_halts": True,
    "stack_restorations_all_pass": True,
    "cleanup_replan_has_zero_physical_stranding": True,
    "cleanup_replan_has_zero_runtime_halts": True,
    "cleanup_replan_restorations_all_pass": True,
    "cleanup_replan_policy_holds": True,
    "cleanup_replan_policy_binds_live": True,
    "cleanup_replan_has_zero_policy_failures": True,
    "cleanup_replan_successes_close_all_obligations": True,
    "minimum_cleanup_replan_closed_successes": 40,
    "minimum_cleanup_replan_success_families": 2,
    "minimum_stack_closed_successes": 80,
    "minimum_stack_closed_success_advantage_over_cleanup_replan": 15,
    "maximum_tenth_look_adjusted_closed_sign_pvalue": 0.05,
}
DECISION_RULE = {
    "on_pass": "report this explicitly reviewer-driven tenth-look successor as evidence against a demand-triggered cleanup-and-replan safe comparator",
    "on_failure": "seal all rows, report the failed gates without exclusions, and make no positive stronger-baseline successor claim",
}
SELECTION_DISCLOSURE = {
    "baseline_selected_after_clean_simulated_review": True,
    "gates_selected_before_any_new_seed_reset": True,
    "retrospective_proxy_used": False,
    "fresh_seeds_selected_before_any_reset": True,
    "old_episode_reuse_allowed": False,
}


def task_records() -> list[dict[str, Any]]:
    return [
        {"task_id": task, "family_group": TASK_FAMILIES[task], "budget_levels": dict(levels)}
        for task, levels in TASK_BUDGETS.items()
    ]


def expected_episodes() -> int:
    cells = sum((len(levels) for levels in TASK_BUDGETS.values()))
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
        "isolated_policy_difference": "both arms use the same stack-wide inverse reserve; only the comparator restores the complete live stack and replans before a requested transaction, without executing the stale proposal",
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
        "selection_disclosure": dict(SELECTION_DISCLOSURE),
        "repositories": dict(repositories),
        "source_sha256": dict(sorted(source_sha256.items())),
        "preregistration": {"path": preregistration_path, "sha256": preregistration_sha256},
        "outcome_based_exclusion_allowed": False,
        "partial_reexecution_allowed": False,
        "episode_replay_allowed": False,
    }
    validate_protocol(protocol)
    return protocol


def validate_protocol(protocol: dict[str, Any]) -> None:
    require(
        not (protocol.get("candidate") != CANDIDATE or protocol.get("status") != STATUS),
        "unexpected cleanup-replan successor identity",
    )
    require(
        not (tuple(protocol.get("arms", ())) != ARMS or set(DRIVERS) != set(ARMS)),
        "cleanup-replan successor arms changed",
    )
    require(not protocol.get("tasks") != task_records(), "cleanup-replan task grid changed")
    require(not tuple(protocol.get("fresh_seeds", ())) != SEEDS, "cleanup-replan successor seeds changed")
    require(
        not tuple(protocol.get("budget_levels", ())) != BUDGET_LEVELS, "cleanup-replan budget levels changed"
    )
    require(not protocol.get("common_budgets") != COMMON_BUDGETS, "cleanup-replan common budgets changed")
    require(not protocol.get("generation") != GENERATION, "cleanup-replan generation changed")
    require(not protocol.get("runtime_deployment") != RUNTIME_DEPLOYMENT, "cleanup-replan deployment changed")
    require(
        not protocol.get("expected_episodes") != expected_episodes(), "cleanup-replan episode count changed"
    )
    require(not protocol.get("outcome_definitions") != OUTCOME_DEFINITIONS, "cleanup-replan outcomes changed")
    require(
        not protocol.get("primary_comparison") != PRIMARY_COMPARISON,
        "cleanup-replan primary comparison changed",
    )
    require(not protocol.get("confirmation_gates") != CONFIRMATION_GATES, "cleanup-replan gates changed")
    require(not protocol.get("decision_rule") != DECISION_RULE, "cleanup-replan decision rule changed")
    require(
        not protocol.get("selection_disclosure") != SELECTION_DISCLOSURE,
        "cleanup-replan selection disclosure changed",
    )
    require(
        not protocol.get("sequence_family_size") != SEQUENCE_FAMILY_SIZE,
        "cleanup-replan multiplicity family changed",
    )
    require(
        not protocol.get("adaptive_history_disclosed") is not True,
        "cleanup-replan adaptive history disclosure changed",
    )
    for key in ("predecessor", "repositories", "source_sha256", "preregistration"):
        if not isinstance(protocol.get(key), dict):
            raise ValueError(f"cleanup-replan {key} binding is absent")
    for key in ("outcome_based_exclusion_allowed", "partial_reexecution_allowed", "episode_replay_allowed"):
        if protocol.get(key) is not False:
            raise ValueError(f"cleanup-replan {key} changed")


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
                            "episode_id": f"{task}__seed{seed}__{level}{budget}__{method}",
                        }
                    )
    if len(rows) != expected_episodes():
        raise ValueError("cleanup-replan manifest is incomplete")
    if len({row["episode_id"] for row in rows}) != len(rows):
        raise ValueError("cleanup-replan manifest is duplicated")
    return rows


def arm_order_counts(protocol: dict[str, Any]) -> dict[str, dict[int, int]]:
    counts = {arm: Counter() for arm in ARMS}
    for row in episode_manifest(protocol):
        counts[row["method"]][int(row["arm_position"])] += 1
    return {arm: dict(sorted(values.items())) for arm, values in counts.items()}


def physical_stranding(row: dict[str, Any]) -> bool:
    return frontier.physical_stranding(row)


def runtime_halt(row: dict[str, Any]) -> bool:
    return frontier.runtime_halt(row)


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


def _forward_policy_actions(row: dict[str, Any]) -> int:
    return _metric(row, "typed_transactions") + _metric(row, "certified_commits")


def _policy_events(row: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    return tuple(
        (
            event
            for event in row.get("trace", ())
            if isinstance(event, dict) and event.get("type") == CLEANUP_REPLAN_POLICY_EVENT_V1
        )
    )


def _cleanup_request_events(row: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    return tuple((event for event in _policy_events(row) if event.get("phase") == "request"))


def _cleanup_outcome_events(row: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    return tuple((event for event in _policy_events(row) if event.get("phase") == "outcome"))


def cleanup_replan_policy_holds(row: dict[str, Any]) -> bool:
    requests = _cleanup_request_events(row)
    outcomes = _cleanup_outcome_events(row)
    if len(requests) != len(outcomes):
        return False
    if len(requests) != _metric(row, "cleanup_replan_attempts"):
        return False
    for request, outcome in zip(requests, outcomes, strict=True):
        if not _cleanup_pair_valid(request, outcome):
            return False
    return _active_count(row) <= 1


def _maximum_observed_active(row: dict[str, Any]) -> int:
    values = [_active_count(row)]
    values.extend(
        (
            int(event["active_obligations_before_proposal"])
            for event in _cleanup_request_events(row)
            if type(event.get("active_obligations_before_proposal")) is int
        )
    )
    return max(values, default=-1)


def summarize_rows(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    rows = tuple(rows)
    base = development.summarize_rows(rows)
    modes = Counter((terminal_outcome_mode(row) for row in rows))
    policy_rows = tuple((row for row in rows if row.get("episode", {}).get("method") == SAFE_BASELINE))
    base.update(
        {
            "physical_stranding_episodes": sum((physical_stranding(row) for row in rows)),
            "runtime_halt_episodes": sum((runtime_halt(row) for row in rows)),
            "verified_restoration_episodes": sum((verified_restoration(row) for row in rows)),
            "certified_scope_discharge_episodes": sum(
                (certified_scope_discharge_endpoint_v18(row) for row in rows)
            ),
            "forward_policy_actions": sum((_forward_policy_actions(row) for row in rows)),
            "episodes_with_forward_action": sum((_forward_policy_actions(row) > 0 for row in rows)),
            "closed_task_successes": sum(
                (bool(row.get("success")) and _active_count(row) == 0 for row in rows)
            ),
            "cleanup_replan_policy_events": sum((len(_policy_events(row)) for row in policy_rows)),
            "cleanup_replan_attempts": sum((_metric(row, "cleanup_replan_attempts") for row in policy_rows)),
            "cleanup_replan_passes": sum((_metric(row, "cleanup_replan_passes") for row in policy_rows)),
            "cleanup_replan_failures": sum((_metric(row, "cleanup_replan_failures") for row in policy_rows)),
            "cleanup_replan_actions": sum((_metric(row, "cleanup_replan_actions") for row in policy_rows)),
            "cleanup_replan_policy_violating_episodes": sum(
                (not cleanup_replan_policy_holds(row) for row in policy_rows)
            ),
            "maximum_observed_active_obligations": max(
                (_maximum_observed_active(row) for row in policy_rows), default=0
            ),
            "terminal_outcome_modes": dict(sorted(modes.items())),
        }
    )
    for name in V16_CLEARANCE_METRICS:
        base[name] = sum((_metric(row, name) for row in rows))
    return base


def _all_attempted_restorations_pass(summary: dict[str, Any]) -> bool:
    legacy_attempts = int(summary["restoration_attempts"])
    clearance_attempts = int(summary["interrupt_clearance_restoration_attempts_v16"])
    return (
        legacy_attempts + clearance_attempts > 0
        and int(summary["restoration_passes"]) == legacy_attempts
        and (int(summary["interrupt_clearance_restoration_passes_v16"]) == clearance_attempts)
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
                full_row = indexed[task, level, seed, FULL_METHOD]
                safe_row = indexed[task, level, seed, SAFE_BASELINE]
                full = bool(full_row.get("success")) and _active_count(full_row) == 0
                safe = bool(safe_row.get("success")) and _active_count(safe_row) == 0
                if full and (not safe):
                    wins += 1
                    cell_wins += 1
                elif safe and (not full):
                    losses += 1
                    cell_losses += 1
                else:
                    ties += 1
                    cell_ties += 1
        seed_rows.append({"seed": seed, "wins": wins, "losses": losses, "ties": ties})
    seed_wins = sum((row["wins"] > row["losses"] for row in seed_rows))
    seed_losses = sum((row["wins"] < row["losses"] for row in seed_rows))
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
        "sequence_adjusted_pvalue_upper_bound": min(1.0, pvalue * SEQUENCE_FAMILY_SIZE),
        "seed_rows": seed_rows,
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
    by_task_budget = _aggregate_by_task_budget(rows)
    paired = _paired_success(rows) if exact_manifest else None
    full = metrics[FULL_METHOD]
    safe = metrics[SAFE_BASELINE]
    safe_rows = tuple((row for row in rows if row.get("episode", {}).get("method") == SAFE_BASELINE))
    safe_success_families = sum(
        (
            any(
                (
                    bool(row.get("success")) and row.get("episode", {}).get("family_group") == family
                    for row in safe_rows
                )
            )
            for family in set(TASK_FAMILIES.values())
        )
    )
    gates = protocol["confirmation_gates"]
    checks = _rows_confirmation_checks(
        all_claims_complete=all_claims_complete,
        exact_manifest=exact_manifest,
        full=full,
        gates=gates,
        metrics=metrics,
        paired=paired,
        protocol=protocol,
        rows=rows,
        safe=safe,
        safe_rows=safe_rows,
        safe_success_families=safe_success_families,
    )
    return {
        "exact_manifest": exact_manifest,
        "all_claims_complete": bool(all_claims_complete),
        "arm_order_counts": arm_order_counts(protocol),
        "metrics": metrics,
        "by_task_budget": by_task_budget,
        "paired_stack_vs_safe_closed_success": paired,
        "cleanup_replan_success_families": safe_success_families,
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
    "OUTCOME_DEFINITIONS",
    "PRIMARY_COMPARISON",
    "RUNTIME_DEPLOYMENT",
    "SAFE_BASELINE",
    "SEEDS",
    "SELECTION_DISCLOSURE",
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
    "cleanup_replan_policy_holds",
    "summarize_rows",
    "task_records",
    "terminal_outcome_mode",
    "validate_protocol",
    "verified_restoration",
]


def _rows_confirmation_checks(
    *,
    all_claims_complete: bool,
    exact_manifest: bool,
    full: Any,
    gates: Any,
    metrics: Any,
    paired: Any,
    protocol: Any,
    rows: tuple[dict[str, Any], ...],
    safe: Any,
    safe_rows: Any,
    safe_success_families: int,
) -> dict[str, bool]:
    """Apply the registered decision gates to computed outcomes."""
    return {
        "complete_exact_grid": exact_manifest and bool(all_claims_complete),
        "zero_infrastructure_failures": sum((value["infrastructure_failures"] for value in metrics.values()))
        == 0,
        "planner_is_exercised": sum((value["planner_calls"] for value in metrics.values())) > 0,
        "all_rows_respect_hard_budgets": _all_rows_respect_budgets(rows, protocol),
        "stack_has_zero_physical_stranding": full["physical_stranding_episodes"] == 0,
        "stack_has_zero_runtime_halts": full["runtime_halt_episodes"] == 0,
        "stack_restorations_all_pass": _all_attempted_restorations_pass(full),
        "cleanup_replan_has_zero_physical_stranding": safe["physical_stranding_episodes"] == 0,
        "cleanup_replan_has_zero_runtime_halts": safe["runtime_halt_episodes"] == 0,
        "cleanup_replan_restorations_all_pass": _all_attempted_restorations_pass(safe),
        "cleanup_replan_policy_holds": safe["cleanup_replan_policy_violating_episodes"] == 0
        and safe["maximum_observed_active_obligations"] <= 1
        and all((cleanup_replan_policy_holds(row) for row in safe_rows)),
        "cleanup_replan_policy_binds_live": safe["cleanup_replan_attempts"] > 0,
        "cleanup_replan_has_zero_policy_failures": safe["cleanup_replan_failures"] == 0
        and safe["cleanup_replan_passes"] == safe["cleanup_replan_attempts"],
        "cleanup_replan_successes_close_all_obligations": safe["successes_with_active_obligations"] == 0,
        "minimum_cleanup_replan_closed_successes": safe["closed_task_successes"]
        >= int(gates["minimum_cleanup_replan_closed_successes"]),
        "minimum_cleanup_replan_success_families": safe_success_families
        >= int(gates["minimum_cleanup_replan_success_families"]),
        "minimum_stack_closed_successes": full["closed_task_successes"]
        >= int(gates["minimum_stack_closed_successes"]),
        "minimum_stack_closed_success_advantage_over_cleanup_replan": full["closed_task_successes"]
        - safe["closed_task_successes"]
        >= int(gates["minimum_stack_closed_success_advantage_over_cleanup_replan"]),
        "maximum_tenth_look_adjusted_closed_sign_pvalue": bool(
            paired
            and paired["sequence_adjusted_pvalue_upper_bound"]
            <= float(gates["maximum_tenth_look_adjusted_closed_sign_pvalue"])
        ),
    }


def _aggregate_by_task_budget(rows: tuple[dict[str, Any], ...]) -> list[dict[str, Any]]:
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


def _cleanup_pair_valid(request: dict[str, Any], outcome: dict[str, Any]) -> bool:
    active = request.get("active_obligations_before_proposal")
    if type(active) is not int or active < 1:
        return False
    if not (
        request.get("policy") == "restore_complete_lifo_stack_then_replan"
        and request.get("decision") == "transact"
        and (request.get("stale_proposal_execution_allowed") is False)
        and (outcome.get("policy") == request.get("policy"))
        and (outcome.get("bid") == request.get("bid"))
        and (outcome.get("active_obligations_before_proposal") == active)
        and (outcome.get("stale_proposal_executed") is False)
        and (outcome.get("replan_from_realized_state") is outcome.get("cleanup_passed"))
    ):
        return False
    if outcome.get("cleanup_passed") is True and outcome.get("active_obligations_after_cleanup") != 0:
        return False
    return True
