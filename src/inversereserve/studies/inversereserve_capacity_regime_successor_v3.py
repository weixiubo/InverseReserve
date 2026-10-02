from __future__ import annotations

from typing import Any, Iterable

from inversereserve.controllers.capacity_reserve_drivers_v18 import (
    RESERVATION_EVENT_V18,
)
from inversereserve.studies import inversereserve_postreview_development_v1 as development
from inversereserve.studies.designs.inversereserve_capacity_regime_successor_v3 import (
    ABSTAIN_BASELINE as ABSTAIN_BASELINE,
)
from inversereserve.studies.designs.inversereserve_capacity_regime_successor_v3 import (
    ARMS as ARMS,
)
from inversereserve.studies.designs.inversereserve_capacity_regime_successor_v3 import (
    CANDIDATE as CANDIDATE,
)
from inversereserve.studies.designs.inversereserve_capacity_regime_successor_v3 import (
    COMMON_BUDGETS as COMMON_BUDGETS,
)
from inversereserve.studies.designs.inversereserve_capacity_regime_successor_v3 import (
    CONFIRMATION_GATES as CONFIRMATION_GATES,
)
from inversereserve.studies.designs.inversereserve_capacity_regime_successor_v3 import (
    DECISION_RULE as DECISION_RULE,
)
from inversereserve.studies.designs.inversereserve_capacity_regime_successor_v3 import (
    DRIVERS as DRIVERS,
)
from inversereserve.studies.designs.inversereserve_capacity_regime_successor_v3 import (
    FAMILY_SUCCESS_FLOORS as FAMILY_SUCCESS_FLOORS,
)
from inversereserve.studies.designs.inversereserve_capacity_regime_successor_v3 import (
    FULL_METHOD as FULL_METHOD,
)
from inversereserve.studies.designs.inversereserve_capacity_regime_successor_v3 import (
    GENERATION as GENERATION,
)
from inversereserve.studies.designs.inversereserve_capacity_regime_successor_v3 import (
    LOCAL_ABLATION as LOCAL_ABLATION,
)
from inversereserve.studies.designs.inversereserve_capacity_regime_successor_v3 import (
    METHOD_REVISION as METHOD_REVISION,
)
from inversereserve.studies.designs.inversereserve_capacity_regime_successor_v3 import (
    PRIMARY_OUTCOME as PRIMARY_OUTCOME,
)
from inversereserve.studies.designs.inversereserve_capacity_regime_successor_v3 import (
    RUNTIME_DEPLOYMENT as RUNTIME_DEPLOYMENT,
)
from inversereserve.studies.designs.inversereserve_capacity_regime_successor_v3 import (
    SEEDS as SEEDS,
)
from inversereserve.studies.designs.inversereserve_capacity_regime_successor_v3 import (
    SEQUENCE_FAMILY_SIZE as SEQUENCE_FAMILY_SIZE,
)
from inversereserve.studies.designs.inversereserve_capacity_regime_successor_v3 import (
    STATUS as STATUS,
)
from inversereserve.studies.designs.inversereserve_capacity_regime_successor_v3 import (
    TASK_FAMILIES as TASK_FAMILIES,
)
from inversereserve.studies.designs.inversereserve_capacity_regime_successor_v3 import (
    TASK_REGIME_BUDGETS as TASK_REGIME_BUDGETS,
)
from inversereserve.studies.designs.inversereserve_capacity_regime_successor_v3 import (
    arm_order_counts as arm_order_counts,
)
from inversereserve.studies.designs.inversereserve_capacity_regime_successor_v3 import (
    build_protocol as build_protocol,
)
from inversereserve.studies.designs.inversereserve_capacity_regime_successor_v3 import (
    episode_manifest as episode_manifest,
)
from inversereserve.studies.designs.inversereserve_capacity_regime_successor_v3 import (
    expected_episodes as expected_episodes,
)
from inversereserve.studies.designs.inversereserve_capacity_regime_successor_v3 import (
    task_records as task_records,
)
from inversereserve.studies.designs.inversereserve_capacity_regime_successor_v3 import (
    validate_protocol as validate_protocol,
)
from inversereserve.studies.episode_grid import matches_registered_grid
from inversereserve.studies.inversereserve_live_resource_stress_v1 import (
    _active_count,
    _metric,
    _one_sided_sign_pvalue,
    _unsafe_local_admissions,
)

"Frozen two-regime successor for cross-family inverse reservation.\n\nTight cells test active recovery solvency.  Opportunity cells test whether\ntask utility returns once the registered inverse capacity is provisioned.\nThe population is a transparent seventh look after all retained failures.\n"
ACTIVE_ARMS = (FULL_METHOD, LOCAL_ABLATION)


def _stranded(row: dict[str, Any]) -> bool:
    return not bool(row.get("success")) and _active_count(row) > 0


V16_CLEARANCE_METRICS = (
    "interrupt_clearance_restoration_attempts_v16",
    "interrupt_clearance_restoration_passes_v16",
    "proposal_clearance_restoration_attempts_v16",
    "proposal_clearance_restoration_passes_v16",
    "active_restore_clearance_restoration_attempts_v16",
    "active_restore_clearance_restoration_passes_v16",
    "interrupt_clearance_reservation_passes_v16",
    "active_restore_clearance_reservation_passes_v16",
    "inverse_action_error_effect_checks_v17",
    "inverse_action_error_effect_passes_v17",
    "inverse_action_error_effect_failures_v17",
    "certified_scope_consumption_checks_v18",
    "certified_scope_consumption_passes_v18",
    "certified_scope_consumption_failures_v18",
    "certified_scope_consumed_transactions_v18",
)


def _reserve_stops_v3(row: dict[str, Any]) -> int:
    return sum(
        (
            event.get("type") == RESERVATION_EVENT_V18 and event.get("allowed") is False
            for event in row.get("trace", ())
        )
    )


def _restoration_evidence_is_clean(row: dict[str, Any]) -> bool:
    legacy_attempts = _metric(row, "restoration_attempts")
    clearance_attempts = _metric(row, "interrupt_clearance_restoration_attempts_v16")
    return (
        legacy_attempts + clearance_attempts > 0
        and _metric(row, "restoration_passes") == legacy_attempts
        and (_metric(row, "interrupt_clearance_restoration_passes_v16") == clearance_attempts)
    )


def certified_scope_discharge_endpoint_v18(row: dict[str, Any]) -> bool:
    return (
        _metric(row, "certified_scope_consumption_passes_v18") > 0
        and _metric(row, "certified_scope_consumption_failures_v18") == 0
        and (_metric(row, "certified_scope_consumed_transactions_v18") > 0)
        and (_active_count(row) == 0)
        and (not bool(row.get("metrics", {}).get("runtime_halted")))
    )


def solvent_activity_endpoint_mode(row: dict[str, Any]) -> str | None:
    if bool(row.get("infrastructure_failure")):
        return None
    if _metric(row, "gui_actions") <= 0 or _metric(row, "typed_transactions") <= 0:
        return None
    if _unsafe_local_admissions(row) > 0:
        return None
    if bool(row.get("metrics", {}).get("runtime_halted")):
        return None
    if bool(row.get("success")):
        return "task_success"
    if _restoration_evidence_is_clean(row) and _active_count(row) == 0:
        return "verified_restoration"
    if certified_scope_discharge_endpoint_v18(row):
        return "certified_scope_discharge_v18"
    return None


def solvent_activity_endpoint(row: dict[str, Any]) -> bool:
    return solvent_activity_endpoint_mode(row) is not None


def summarize_rows(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    rows = tuple(rows)
    base = development.summarize_rows(rows)
    base["reserve_stops"] = sum((_reserve_stops_v3(row) for row in rows))
    base.update(
        {
            "solvent_activity_endpoints": sum((solvent_activity_endpoint(row) for row in rows)),
            "certified_scope_discharge_endpoints_v18": sum(
                (solvent_activity_endpoint_mode(row) == "certified_scope_discharge_v18" for row in rows)
            ),
            "episodes_with_gui_action": sum((_metric(row, "gui_actions") > 0 for row in rows)),
            "episodes_with_typed_transaction": sum((_metric(row, "typed_transactions") > 0 for row in rows)),
        }
    )
    for name in V16_CLEARANCE_METRICS:
        base[name] = sum((_metric(row, name) for row in rows))
    return base


def _paired_tight(rows: tuple[dict[str, Any], ...]) -> dict[str, Any]:
    indexed = {
        (row["episode"]["task"], int(row["episode"]["seed"]), row["episode"]["method"]): row
        for row in rows
        if row.get("episode", {}).get("regime") == "tight"
        and row.get("episode", {}).get("method") in ACTIVE_ARMS
    }
    cell_wins = cell_losses = cell_ties = 0
    seed_rows = []
    for seed in SEEDS:
        full_wins = local_wins = ties = 0
        for task in TASK_REGIME_BUDGETS:
            full = solvent_activity_endpoint(indexed[task, seed, FULL_METHOD])
            local = solvent_activity_endpoint(indexed[task, seed, LOCAL_ABLATION])
            if full and (not local):
                full_wins += 1
                cell_wins += 1
            elif local and (not full):
                local_wins += 1
                cell_losses += 1
            else:
                ties += 1
                cell_ties += 1
        seed_rows.append({"seed": seed, "full_wins": full_wins, "local_wins": local_wins, "ties": ties})
    seed_wins = sum((row["full_wins"] > row["local_wins"] for row in seed_rows))
    seed_losses = sum((row["full_wins"] < row["local_wins"] for row in seed_rows))
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


def _all_rows_respect_budgets(rows: tuple[dict[str, Any], ...], protocol: dict[str, Any]) -> bool:
    maximum_planner_calls = int(protocol["common_budgets"]["maximum_planner_calls"])
    maximum_wall_seconds = float(protocol["common_budgets"]["maximum_wall_seconds"])
    for row in rows:
        metrics = row.get("metrics")
        episode = row.get("episode")
        if not isinstance(metrics, dict) or not isinstance(episode, dict):
            return False
        try:
            gui_actions = int(metrics["gui_actions"])
            planner_calls = int(metrics["planner_calls"])
            wall_seconds = float(metrics["wall_seconds"])
            maximum_gui_actions = int(episode["maximum_gui_actions"])
        except (KeyError, TypeError, ValueError):
            return False
        if not (
            0 <= gui_actions <= maximum_gui_actions
            and 0 <= planner_calls <= maximum_planner_calls
            and (0.0 <= wall_seconds <= maximum_wall_seconds)
        ):
            return False
    return True


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
    by_regime = _analyze_rows_by_regime(rows=rows)
    by_task_regime = _aggregate_by_task_regime(rows)
    paired_tight = _paired_tight(rows) if exact_manifest else None
    opportunity_full = by_regime["opportunity"][FULL_METHOD]["task_successes"]
    opportunity_local = by_regime["opportunity"][LOCAL_ABLATION]["task_successes"]
    full_family_success = _analyze_rows_full_family_success(rows=rows)
    local_tight_effect_families = _analyze_rows_local_tight_effect_families(rows=rows)
    full_metrics = metrics[FULL_METHOD]
    abstain_metrics = metrics[ABSTAIN_BASELINE]
    gates = protocol["confirmation_gates"]
    legacy_attempts = full_metrics["restoration_attempts"]
    clearance_attempts = full_metrics["interrupt_clearance_restoration_attempts_v16"]
    full_restorations_all_pass = (
        legacy_attempts + clearance_attempts > 0
        and full_metrics["restoration_passes"] == legacy_attempts
        and (full_metrics["interrupt_clearance_restoration_passes_v16"] == clearance_attempts)
    )
    checks = _rows_confirmation_checks(
        abstain_metrics=abstain_metrics,
        all_claims_complete=all_claims_complete,
        by_regime=by_regime,
        exact_manifest=exact_manifest,
        full_family_success=full_family_success,
        full_metrics=full_metrics,
        full_restorations_all_pass=full_restorations_all_pass,
        gates=gates,
        local_tight_effect_families=local_tight_effect_families,
        metrics=metrics,
        opportunity_full=opportunity_full,
        opportunity_local=opportunity_local,
        paired_tight=paired_tight,
        protocol=protocol,
        rows=rows,
    )
    return {
        "exact_manifest": exact_manifest,
        "all_claims_complete": bool(all_claims_complete),
        "arm_order_counts": arm_order_counts(protocol),
        "metrics": metrics,
        "by_regime": by_regime,
        "by_task_regime": by_task_regime,
        "paired_tight": paired_tight,
        "opportunity_task_success": {
            "stack_wide": opportunity_full,
            "proposal_local": opportunity_local,
            "stack_wide_by_family": full_family_success,
        },
        "local_tight_unsafe_and_stranding_families": local_tight_effect_families,
        "checks": checks,
        "passed": all(checks.values()),
    }


__all__ = [
    "ABSTAIN_BASELINE",
    "ACTIVE_ARMS",
    "ARMS",
    "CANDIDATE",
    "COMMON_BUDGETS",
    "CONFIRMATION_GATES",
    "DECISION_RULE",
    "DRIVERS",
    "FAMILY_SUCCESS_FLOORS",
    "FULL_METHOD",
    "GENERATION",
    "LOCAL_ABLATION",
    "METHOD_REVISION",
    "PRIMARY_OUTCOME",
    "SEEDS",
    "SEQUENCE_FAMILY_SIZE",
    "STATUS",
    "TASK_REGIME_BUDGETS",
    "analyze_rows",
    "arm_order_counts",
    "build_protocol",
    "certified_scope_discharge_endpoint_v18",
    "episode_manifest",
    "expected_episodes",
    "solvent_activity_endpoint",
    "solvent_activity_endpoint_mode",
    "summarize_rows",
    "task_records",
    "validate_protocol",
]


def _rows_confirmation_checks(
    *,
    abstain_metrics: Any,
    all_claims_complete: bool,
    by_regime: Any,
    exact_manifest: bool,
    full_family_success: Any,
    full_metrics: Any,
    full_restorations_all_pass: Any,
    gates: Any,
    local_tight_effect_families: int,
    metrics: Any,
    opportunity_full: Any,
    opportunity_local: Any,
    paired_tight: Any,
    protocol: Any,
    rows: tuple[dict[str, Any], ...],
) -> dict[str, bool]:
    """Apply the registered decision gates to computed outcomes."""
    return {
        "complete_exact_grid": exact_manifest and bool(all_claims_complete),
        "zero_infrastructure_failures": sum((value["infrastructure_failures"] for value in metrics.values()))
        == 0,
        "planner_is_exercised": sum((metrics[arm]["planner_calls"] for arm in ACTIVE_ARMS)) > 0,
        "stack_wide_reserve_binds_live": full_metrics["reserve_stops"] > 0,
        "stack_wide_has_zero_unsafe_admissions": full_metrics["unsafe_local_admissions"] == 0,
        "stack_wide_has_zero_runtime_halts": full_metrics["runtime_halts"] == 0,
        "stack_wide_restorations_all_pass": full_restorations_all_pass,
        "minimum_stack_interrupt_clearance_restorations_v16": full_metrics[
            "interrupt_clearance_restoration_passes_v16"
        ]
        >= int(gates["minimum_stack_interrupt_clearance_restorations_v16"]),
        "stack_wide_inverse_error_effect_checks_all_pass_v17": full_metrics[
            "inverse_action_error_effect_failures_v17"
        ]
        == 0,
        "minimum_stack_certified_scope_consumption_passes_v18": full_metrics[
            "certified_scope_consumption_passes_v18"
        ]
        >= int(gates["minimum_stack_certified_scope_consumption_passes_v18"]),
        "zero_stack_certified_scope_consumption_failures_v18": full_metrics[
            "certified_scope_consumption_failures_v18"
        ]
        == 0,
        "minimum_stack_certified_scope_discharge_endpoints_v18": full_metrics[
            "certified_scope_discharge_endpoints_v18"
        ]
        >= int(gates["minimum_stack_certified_scope_discharge_endpoints_v18"]),
        "minimum_stack_tight_endpoints": by_regime["tight"][FULL_METHOD]["solvent_activity_endpoints"]
        >= int(gates["minimum_stack_tight_endpoints"]),
        "minimum_tight_seed_cluster_net_wins": bool(
            paired_tight
            and paired_tight["seed_cluster_wins"] - paired_tight["seed_cluster_losses"]
            >= int(gates["minimum_tight_seed_cluster_net_wins"])
        ),
        "maximum_seventh_look_adjusted_sign_pvalue": bool(
            paired_tight
            and paired_tight["sequence_adjusted_pvalue_upper_bound"]
            <= float(gates["maximum_seventh_look_adjusted_sign_pvalue"])
        ),
        "minimum_stack_opportunity_successes": opportunity_full
        >= int(gates["minimum_stack_opportunity_successes"]),
        "maximum_stack_opportunity_success_deficit": opportunity_local - opportunity_full
        <= int(gates["maximum_stack_opportunity_success_deficit"]),
        "family_success_floors": all(
            (
                full_family_success[family] >= int(floor)
                for family, floor in gates["family_success_floors"].items()
            )
        ),
        "local_unsafe_and_stranding_families": local_tight_effect_families
        >= int(gates["local_unsafe_and_stranding_families"]),
        "always_abstain_is_empirically_degenerate": abstain_metrics["gui_actions"] == 0
        and abstain_metrics["typed_transactions"] == 0
        and (abstain_metrics["task_successes"] == 0)
        and (abstain_metrics["solvent_activity_endpoints"] == 0),
        "all_rows_respect_hard_budgets": _all_rows_respect_budgets(rows, protocol),
    }


def _analyze_rows_by_regime(*, rows: Any) -> Any:
    """Compute by regime from explicit study inputs."""
    return {
        regime: {
            arm: summarize_rows(
                (
                    row
                    for row in rows
                    if row.get("episode", {}).get("regime") == regime
                    and row.get("episode", {}).get("method") == arm
                )
            )
            for arm in ARMS
        }
        for regime in ("tight", "opportunity")
    }


def _analyze_rows_full_family_success(*, rows: Any) -> Any:
    """Compute full family success from explicit study inputs."""
    return {
        family: sum(
            (
                bool(row.get("success"))
                for row in rows
                if row.get("episode", {}).get("regime") == "opportunity"
                and row.get("episode", {}).get("method") == FULL_METHOD
                and (row.get("episode", {}).get("family_group") == family)
            )
        )
        for family in FAMILY_SUCCESS_FLOORS
    }


def _analyze_rows_local_tight_effect_families(*, rows: Any) -> Any:
    """Compute local tight effect families from explicit study inputs."""
    return sum(
        (
            any(
                (
                    row.get("episode", {}).get("regime") == "tight"
                    and row.get("episode", {}).get("method") == LOCAL_ABLATION
                    and (row.get("episode", {}).get("family_group") == family)
                    and (_unsafe_local_admissions(row) > 0)
                    for row in rows
                )
            )
            and any(
                (
                    row.get("episode", {}).get("regime") == "tight"
                    and row.get("episode", {}).get("method") == LOCAL_ABLATION
                    and (row.get("episode", {}).get("family_group") == family)
                    and _stranded(row)
                    for row in rows
                )
            )
            for family in FAMILY_SUCCESS_FLOORS
        )
    )


def _aggregate_by_task_regime(rows: tuple[dict[str, Any], ...]) -> list[dict[str, Any]]:
    by_task_regime = []
    for task, regimes in TASK_REGIME_BUDGETS.items():
        for regime, budget in regimes.items():
            by_task_regime.append(
                {
                    "task": task,
                    "family_group": TASK_FAMILIES[task],
                    "regime": regime,
                    "maximum_gui_actions": budget,
                    "arms": {
                        arm: summarize_rows(
                            (
                                row
                                for row in rows
                                if row.get("episode", {}).get("task") == task
                                and row.get("episode", {}).get("regime") == regime
                                and (row.get("episode", {}).get("method") == arm)
                            )
                        )
                        for arm in ARMS
                    },
                }
            )
    return by_task_regime
