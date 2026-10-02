from __future__ import annotations

from collections import Counter
from typing import Any, Iterable

from inversereserve.controllers.minimal_cleanup_replan_capacity_driver_v1 import (
    MINIMAL_CLEANUP_POLICY_EVENT_V1,
)
from inversereserve.studies import inversereserve_budget_frontier_holdout_v2 as frontier
from inversereserve.studies import inversereserve_postreview_development_v1 as development
from inversereserve.studies.designs.inversereserve_minimal_cleanup_successor_v1 import (
    ARMS as ARMS,
)
from inversereserve.studies.designs.inversereserve_minimal_cleanup_successor_v1 import (
    BUDGET_LEVELS as BUDGET_LEVELS,
)
from inversereserve.studies.designs.inversereserve_minimal_cleanup_successor_v1 import (
    CANDIDATE as CANDIDATE,
)
from inversereserve.studies.designs.inversereserve_minimal_cleanup_successor_v1 import (
    COMMON_BUDGETS as COMMON_BUDGETS,
)
from inversereserve.studies.designs.inversereserve_minimal_cleanup_successor_v1 import (
    CONFIRMATION_GATES as CONFIRMATION_GATES,
)
from inversereserve.studies.designs.inversereserve_minimal_cleanup_successor_v1 import (
    DECISION_RULE as DECISION_RULE,
)
from inversereserve.studies.designs.inversereserve_minimal_cleanup_successor_v1 import (
    DRIVERS as DRIVERS,
)
from inversereserve.studies.designs.inversereserve_minimal_cleanup_successor_v1 import (
    FULL_METHOD as FULL_METHOD,
)
from inversereserve.studies.designs.inversereserve_minimal_cleanup_successor_v1 import (
    GENERATION as GENERATION,
)
from inversereserve.studies.designs.inversereserve_minimal_cleanup_successor_v1 import (
    OUTCOME_DEFINITIONS as OUTCOME_DEFINITIONS,
)
from inversereserve.studies.designs.inversereserve_minimal_cleanup_successor_v1 import (
    PRESTART_SUPERSESSION as PRESTART_SUPERSESSION,
)
from inversereserve.studies.designs.inversereserve_minimal_cleanup_successor_v1 import (
    PRIMARY_COMPARISON as PRIMARY_COMPARISON,
)
from inversereserve.studies.designs.inversereserve_minimal_cleanup_successor_v1 import (
    RUNTIME_DEPLOYMENT as RUNTIME_DEPLOYMENT,
)
from inversereserve.studies.designs.inversereserve_minimal_cleanup_successor_v1 import (
    SAFE_BASELINE as SAFE_BASELINE,
)
from inversereserve.studies.designs.inversereserve_minimal_cleanup_successor_v1 import (
    SEEDS as SEEDS,
)
from inversereserve.studies.designs.inversereserve_minimal_cleanup_successor_v1 import (
    SELECTION_DISCLOSURE as SELECTION_DISCLOSURE,
)
from inversereserve.studies.designs.inversereserve_minimal_cleanup_successor_v1 import (
    SEQUENCE_FAMILY_SIZE as SEQUENCE_FAMILY_SIZE,
)
from inversereserve.studies.designs.inversereserve_minimal_cleanup_successor_v1 import (
    STATUS as STATUS,
)
from inversereserve.studies.designs.inversereserve_minimal_cleanup_successor_v1 import (
    TASK_BUDGETS as TASK_BUDGETS,
)
from inversereserve.studies.designs.inversereserve_minimal_cleanup_successor_v1 import (
    TASK_FAMILIES as TASK_FAMILIES,
)
from inversereserve.studies.designs.inversereserve_minimal_cleanup_successor_v1 import (
    arm_order_counts as arm_order_counts,
)
from inversereserve.studies.designs.inversereserve_minimal_cleanup_successor_v1 import (
    build_protocol as build_protocol,
)
from inversereserve.studies.designs.inversereserve_minimal_cleanup_successor_v1 import (
    episode_manifest as episode_manifest,
)
from inversereserve.studies.designs.inversereserve_minimal_cleanup_successor_v1 import (
    expected_episodes as expected_episodes,
)
from inversereserve.studies.designs.inversereserve_minimal_cleanup_successor_v1 import (
    task_records as task_records,
)
from inversereserve.studies.designs.inversereserve_minimal_cleanup_successor_v1 import (
    validate_protocol as validate_protocol,
)
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

"Frozen minimal-cleanup successor for InverseReserve.\n\nThis eleventh adaptive look evaluates the stronger safe policy requested after\nthe tenth-look analysis.  The comparator preserves every capacity-feasible\nstack.  Only when exact stack-wide reserve blocks a requested transaction does\nit restore one top LIFO obligation, discard the stale proposal, and replan from\nthe realized public state.\n"


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
            if isinstance(event, dict) and event.get("type") == MINIMAL_CLEANUP_POLICY_EVENT_V1
        )
    )


def _cleanup_request_events(row: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    return tuple((event for event in _policy_events(row) if event.get("phase") == "request"))


def _cleanup_outcome_events(row: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    return tuple((event for event in _policy_events(row) if event.get("phase") == "outcome"))


def minimal_cleanup_policy_holds(row: dict[str, Any]) -> bool:
    requests = _cleanup_request_events(row)
    outcomes = _cleanup_outcome_events(row)
    if len(requests) != len(outcomes):
        return False
    if len(requests) != _metric(row, "minimal_cleanup_attempts"):
        return False
    for request, outcome in zip(requests, outcomes, strict=True):
        if not _cleanup_pair_valid(request, outcome):
            return False
    return True


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
            "minimal_cleanup_policy_events": sum((len(_policy_events(row)) for row in policy_rows)),
            "minimal_cleanup_attempts": sum(
                (_metric(row, "minimal_cleanup_attempts") for row in policy_rows)
            ),
            "minimal_cleanup_passes": sum((_metric(row, "minimal_cleanup_passes") for row in policy_rows)),
            "minimal_cleanup_failures": sum(
                (_metric(row, "minimal_cleanup_failures") for row in policy_rows)
            ),
            "minimal_cleanup_actions": sum((_metric(row, "minimal_cleanup_actions") for row in policy_rows)),
            "minimal_cleanup_policy_violating_episodes": sum(
                (not minimal_cleanup_policy_holds(row) for row in policy_rows)
            ),
            "minimal_cleanup_preserved_lower_obligation_events": sum(
                (
                    event.get("cleanup_passed") is True
                    and int(event.get("active_obligations_after_cleanup", 0)) > 0
                    for row in policy_rows
                    for event in _cleanup_outcome_events(row)
                )
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
        "paired_stack_vs_safe_task_success": paired,
        "minimal_cleanup_success_families": safe_success_families,
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
    "PRESTART_SUPERSESSION",
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
    "minimal_cleanup_policy_holds",
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
        "minimal_cleanup_has_zero_physical_stranding": safe["physical_stranding_episodes"] == 0,
        "minimal_cleanup_has_zero_runtime_halts": safe["runtime_halt_episodes"] == 0,
        "minimal_cleanup_restorations_all_pass": _all_attempted_restorations_pass(safe),
        "minimal_cleanup_policy_holds": safe["minimal_cleanup_policy_violating_episodes"] == 0
        and all((minimal_cleanup_policy_holds(row) for row in safe_rows)),
        "minimal_cleanup_policy_binds_live": safe["minimal_cleanup_attempts"] > 0,
        "minimal_cleanup_has_zero_policy_failures": safe["minimal_cleanup_failures"] == 0
        and safe["minimal_cleanup_passes"] == safe["minimal_cleanup_attempts"],
        "minimal_cleanup_preserves_lower_obligation_live": safe[
            "minimal_cleanup_preserved_lower_obligation_events"
        ]
        > 0,
        "minimum_minimal_cleanup_closed_successes": safe["closed_task_successes"]
        >= int(gates["minimum_minimal_cleanup_closed_successes"]),
        "minimum_minimal_cleanup_success_families": safe_success_families
        >= int(gates["minimum_minimal_cleanup_success_families"]),
        "minimum_stack_closed_successes": full["closed_task_successes"]
        >= int(gates["minimum_stack_closed_successes"]),
        "minimal_cleanup_closed_noninferiority_to_stack": safe["closed_task_successes"]
        - full["closed_task_successes"]
        >= int(gates["minimal_cleanup_closed_noninferiority_to_stack"]),
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
        request.get("policy") == "restore_one_top_obligation_then_replan"
        and request.get("decision") == "transact"
        and (request.get("stale_proposal_execution_allowed") is False)
        and (outcome.get("policy") == request.get("policy"))
        and (outcome.get("bid") == request.get("bid"))
        and (outcome.get("active_obligations_before_proposal") == active)
        and (outcome.get("stale_proposal_executed") is False)
        and (outcome.get("replan_from_realized_state") is outcome.get("cleanup_passed"))
    ):
        return False
    if (
        outcome.get("cleanup_passed") is True
        and outcome.get("active_obligations_after_cleanup") != active - 1
    ):
        return False
    return True
