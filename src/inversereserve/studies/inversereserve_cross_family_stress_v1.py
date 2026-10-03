from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from inversereserve.studies.designs.inversereserve_cross_family_stress_v1 import (
    ABSTAIN_BASELINE as ABSTAIN_BASELINE,
)
from inversereserve.studies.designs.inversereserve_cross_family_stress_v1 import ARMS as ARMS
from inversereserve.studies.designs.inversereserve_cross_family_stress_v1 import CANDIDATE as CANDIDATE
from inversereserve.studies.designs.inversereserve_cross_family_stress_v1 import (
    COMMON_BUDGETS as COMMON_BUDGETS,
)
from inversereserve.studies.designs.inversereserve_cross_family_stress_v1 import (
    CONFIRMATION_GATES as CONFIRMATION_GATES,
)
from inversereserve.studies.designs.inversereserve_cross_family_stress_v1 import (
    DECISION_RULE as DECISION_RULE,
)
from inversereserve.studies.designs.inversereserve_cross_family_stress_v1 import DRIVERS as DRIVERS
from inversereserve.studies.designs.inversereserve_cross_family_stress_v1 import FULL_METHOD as FULL_METHOD
from inversereserve.studies.designs.inversereserve_cross_family_stress_v1 import GENERATION as GENERATION
from inversereserve.studies.designs.inversereserve_cross_family_stress_v1 import (
    LOCAL_ABLATION as LOCAL_ABLATION,
)
from inversereserve.studies.designs.inversereserve_cross_family_stress_v1 import (
    PRIMARY_OUTCOME as PRIMARY_OUTCOME,
)
from inversereserve.studies.designs.inversereserve_cross_family_stress_v1 import SEEDS as SEEDS
from inversereserve.studies.designs.inversereserve_cross_family_stress_v1 import (
    SEQUENCE_FAMILY_SIZE as SEQUENCE_FAMILY_SIZE,
)
from inversereserve.studies.designs.inversereserve_cross_family_stress_v1 import STATUS as STATUS
from inversereserve.studies.designs.inversereserve_cross_family_stress_v1 import TASK_BUDGETS as TASK_BUDGETS
from inversereserve.studies.designs.inversereserve_cross_family_stress_v1 import (
    TASK_FAMILIES as TASK_FAMILIES,
)
from inversereserve.studies.designs.inversereserve_cross_family_stress_v1 import (
    AlwaysAbstainDriverV15 as AlwaysAbstainDriverV15,
)
from inversereserve.studies.designs.inversereserve_cross_family_stress_v1 import (
    ProposalLocalCrossFamilyDriverV15 as ProposalLocalCrossFamilyDriverV15,
)
from inversereserve.studies.designs.inversereserve_cross_family_stress_v1 import (
    StackWideCrossFamilyDriverV15 as StackWideCrossFamilyDriverV15,
)
from inversereserve.studies.designs.inversereserve_cross_family_stress_v1 import (
    _CrossFamilyReserveDriverV15 as _CrossFamilyReserveDriverV15,
)
from inversereserve.studies.designs.inversereserve_cross_family_stress_v1 import (
    arm_order_counts as arm_order_counts,
)
from inversereserve.studies.designs.inversereserve_cross_family_stress_v1 import (
    build_protocol as build_protocol,
)
from inversereserve.studies.designs.inversereserve_cross_family_stress_v1 import (
    episode_manifest as episode_manifest,
)
from inversereserve.studies.designs.inversereserve_cross_family_stress_v1 import (
    expected_episodes as expected_episodes,
)
from inversereserve.studies.designs.inversereserve_cross_family_stress_v1 import task_records as task_records
from inversereserve.studies.designs.inversereserve_cross_family_stress_v1 import (
    validate_protocol as validate_protocol,
)
from inversereserve.studies.episode_grid import matches_registered_grid
from inversereserve.studies.inversereserve_live_resource_stress_v1 import (
    _active_count,
    _metric,
    _one_sided_sign_pvalue,
    _unsafe_local_admissions,
)

"Frozen design for a planner-enabled cross-family InverseReserve stress.\n\nThe experiment changes only inverse-reserve accounting between the two active\narms.  A third always-abstain arm measures the degenerate clean-stop baseline.\nThe primary endpoint requires actual transactional activity, so abstention\ncannot satisfy it.\n"
RESERVE_ARMS = (FULL_METHOD, LOCAL_ABLATION)


def clean_or_success(row: dict[str, Any]) -> bool:
    if bool(row.get("infrastructure_failure")):
        return False
    if bool(row.get("success")):
        return True
    return (
        not bool(row.get("metrics", {}).get("runtime_halted"))
        and _active_count(row) == 0
        and (_metric(row, "restoration_passes") == _metric(row, "restoration_attempts"))
    )


def activity_constrained_endpoint(row: dict[str, Any]) -> bool:
    if bool(row.get("infrastructure_failure")):
        return False
    active = _metric(row, "gui_actions") > 0 and _metric(row, "typed_transactions") > 0
    if bool(row.get("success")):
        return active
    return active and _metric(row, "restoration_attempts") > 0 and clean_or_success(row)


def _stranded_obligation(row: dict[str, Any]) -> bool:
    return not bool(row.get("success")) and _active_count(row) > 0


def _contract_kinds(row: dict[str, Any]) -> set[str]:
    return {
        str(event["contract_kind"])
        for event in row.get("runtime_events", ())
        if event.get("type") == "postcondition"
        and event.get("context") == "typed forward"
        and (event.get("passed") is True)
        and event.get("contract_kind")
    }


def _planner_before_first_reserve_divergence(full_row: dict[str, Any], local_row: dict[str, Any]) -> bool:
    full_reserve = [
        event for event in full_row.get("trace", ()) if event.get("type") == "cross_family_reservation_v1"
    ]
    local_reserve = [
        event for event in local_row.get("trace", ()) if event.get("type") == "cross_family_reservation_v1"
    ]
    shared_fields = (
        "decision",
        "bid",
        "registered_active_inverse_cost",
        "proposal_inverse_cost",
        "stack_wide_required_inverse_cost",
        "remaining_after_action",
    )
    for full_event, local_event in zip(full_reserve, local_reserve, strict=False):
        if any((full_event.get(key) != local_event.get(key) for key in shared_fields)):
            return False
        if full_event.get("allowed") == local_event.get("allowed"):
            continue

        def model_precedes(row: dict[str, Any], event: dict[str, Any]) -> bool:
            boundary = int(event.get("event_index", -1))
            return any(
                (
                    candidate.get("type") == "envelope_decision_v8"
                    and candidate.get("model") is not None
                    and (int(candidate.get("event_index", -1)) < boundary)
                    for candidate in row.get("trace", ())
                )
            )

        return model_precedes(full_row, full_event) and model_precedes(local_row, local_event)
    return False


def analyze_rows(
    rows: Iterable[dict[str, Any]], protocol: dict[str, Any], *, all_claims_complete: bool
) -> dict[str, Any]:
    """Analyze the sealed finite grid without outcome-based exclusions."""
    validate_protocol(protocol)
    rows = tuple(rows)
    manifest = episode_manifest(protocol)
    exact_manifest = matches_registered_grid(rows, manifest)
    indexed = {
        (
            int(row["episode"]["seed"]),
            str(row["episode"]["task"]),
            int(row["episode"]["maximum_gui_actions"]),
            str(row["episode"]["method"]),
        ): row
        for row in rows
        if isinstance(row.get("episode"), dict)
    }
    arm_metrics: dict[str, dict[str, Any]] = {}
    for arm in ARMS:
        arm_rows = tuple((row for row in rows if row.get("episode", {}).get("method") == arm))
        arm_metrics[arm] = _analyze_rows_arm_metrics_record(arm_rows=arm_rows)
    task_budget_rows = _aggregate_task_budgets(rows)
    paired = _paired_activity(indexed)
    _augment_task_metrics(rows, paired)
    coactivated_effect_families = sum(
        (bool(value["coactivated_effect"]) for value in paired.task_rows.values())
    )
    full_success_floor_families = sum(
        (
            int(value["full_task_successes"])
            >= int(protocol["confirmation_gates"]["minimum_full_task_successes_per_family"])
            for value in paired.task_rows.values()
        )
    )
    observed_contract_kinds = sorted(
        set().union(*(set(value["observed_contract_kinds"]) for value in paired.task_rows.values()))
    )
    full = arm_metrics[FULL_METHOD]
    local = arm_metrics[LOCAL_ABLATION]
    abstain = arm_metrics[ABSTAIN_BASELINE]
    expected_per_arm = expected_episodes() // len(ARMS)
    goal_hashes = _goal_hashes(rows)
    checks = _rows_confirmation_checks(
        abstain=abstain,
        adjusted_pvalue=paired.adjusted_pvalue,
        all_claims_complete=all_claims_complete,
        arm_metrics=arm_metrics,
        coactivated_effect_families=coactivated_effect_families,
        exact_manifest=exact_manifest,
        expected_per_arm=expected_per_arm,
        full=full,
        full_success_floor_families=full_success_floor_families,
        goal_hashes=goal_hashes,
        local=local,
        planner_mediated_paired_wins=paired.planner_mediated_paired_wins,
        protocol=protocol,
        rows=rows,
        seed_cluster_losses=paired.seed_cluster_losses,
        seed_cluster_wins=paired.seed_cluster_wins,
    )
    return {
        "metrics": arm_metrics,
        "by_task_budget": task_budget_rows,
        "paired_activity_endpoint": {
            "cell_wins": paired.cell_wins,
            "cell_losses": paired.cell_losses,
            "cell_ties": paired.cell_ties,
            "seed_cluster_wins": paired.seed_cluster_wins,
            "seed_cluster_losses": paired.seed_cluster_losses,
            "seed_cluster_ties": paired.seed_cluster_ties,
            "one_sided_exact_sign_pvalue": paired.sign_pvalue,
            "sequence_family_size": SEQUENCE_FAMILY_SIZE,
            "sequence_adjusted_pvalue_upper_bound": paired.adjusted_pvalue,
            "planner_mediated_paired_wins": paired.planner_mediated_paired_wins,
            "coactivated_effect_families": coactivated_effect_families,
            "seed_rows": paired.seed_rows,
            "by_task": paired.task_rows,
            "observed_contract_kinds": observed_contract_kinds,
        },
        "paired_task_success": {
            "full_only": paired.task_success_wins,
            "local_only": paired.task_success_losses,
            "ties": paired.task_success_ties,
        },
        "checks": checks,
        "passed": all(checks.values()),
    }


__all__ = [
    "ABSTAIN_BASELINE",
    "ARMS",
    "CANDIDATE",
    "COMMON_BUDGETS",
    "CONFIRMATION_GATES",
    "DECISION_RULE",
    "DRIVERS",
    "FULL_METHOD",
    "GENERATION",
    "LOCAL_ABLATION",
    "PRIMARY_OUTCOME",
    "SEEDS",
    "STATUS",
    "TASK_BUDGETS",
    "TASK_FAMILIES",
    "activity_constrained_endpoint",
    "analyze_rows",
    "arm_order_counts",
    "build_protocol",
    "clean_or_success",
    "episode_manifest",
    "expected_episodes",
    "task_records",
    "validate_protocol",
]


def _rows_confirmation_checks(
    *,
    abstain: Any,
    adjusted_pvalue: float,
    all_claims_complete: bool,
    arm_metrics: Any,
    coactivated_effect_families: int,
    exact_manifest: bool,
    expected_per_arm: int,
    full: Any,
    full_success_floor_families: int,
    goal_hashes: Any,
    local: Any,
    planner_mediated_paired_wins: int,
    protocol: Any,
    rows: tuple[dict[str, Any], ...],
    seed_cluster_losses: int,
    seed_cluster_wins: int,
) -> dict[str, bool]:
    """Apply the registered decision gates to computed outcomes."""
    return {
        "complete_exact_grid": exact_manifest
        and all_claims_complete
        and all((metrics["episodes"] == expected_per_arm for metrics in arm_metrics.values()))
        and all((len(values) == 1 for values in goal_hashes.values())),
        "zero_infrastructure_failures": all(
            (metrics["infrastructure_failures"] == 0 for metrics in arm_metrics.values())
        ),
        "planner_is_exercised": full["planner_calls"] > 0
        and local["planner_calls"] > 0
        and (full["planner_actual_calls"] + local["planner_actual_calls"] > 0),
        "stack_wide_reserve_binds_live": full["reserve_stops"] > 0,
        "stack_wide_restorations_all_pass": full["restoration_attempts"] > 0
        and full["restoration_passes"] == full["restoration_attempts"]
        and (full["runtime_halts"] == 0)
        and (full["stranded_obligation_episodes"] == 0),
        "proposal_local_makes_unsafe_admissions": local["unsafe_local_admissions"] > 0,
        "proposal_local_strands_obligations": local["stranded_obligation_episodes"] > 0,
        "full_activity_endpoint_rate_exceeds_local": full["activity_endpoint_episodes"]
        > local["activity_endpoint_episodes"],
        "minimum_coactivated_effect_families": coactivated_effect_families
        >= int(protocol["confirmation_gates"]["minimum_coactivated_effect_families"]),
        "minimum_planner_mediated_paired_wins": planner_mediated_paired_wins
        >= int(protocol["confirmation_gates"]["minimum_planner_mediated_paired_wins"]),
        "minimum_seed_cluster_net_wins": seed_cluster_wins - seed_cluster_losses
        >= int(protocol["confirmation_gates"]["minimum_seed_cluster_net_wins"]),
        "maximum_sequence_adjusted_sign_pvalue": adjusted_pvalue
        <= float(protocol["confirmation_gates"]["maximum_sequence_adjusted_sign_pvalue"]),
        "full_has_task_successes": full["task_successes"] > 0,
        "full_task_success_descriptive_guardrail_cells": full["task_successes"]
        + int(protocol["confirmation_gates"]["full_task_success_descriptive_guardrail_cells"])
        >= local["task_successes"],
        "minimum_task_families_with_full_success_floor": full_success_floor_families
        >= int(protocol["confirmation_gates"]["minimum_task_families_with_full_success_floor"]),
        "always_abstain_is_empirically_degenerate": abstain["episodes"] == expected_per_arm
        and abstain["task_successes"] == 0
        and (abstain["gui_actions"] == 0)
        and (abstain["typed_transactions"] == 0)
        and (abstain["planner_calls"] == 0)
        and (abstain["activity_endpoint_episodes"] == 0)
        and (abstain["clean_or_success_episodes"] == expected_per_arm),
        "all_rows_respect_hard_budgets": all(
            (
                _metric(row, "gui_actions") <= int(row.get("episode", {}).get("maximum_gui_actions", -1))
                and _metric(row, "planner_calls") <= int(protocol["common_budgets"]["maximum_planner_calls"])
                and (
                    float(row.get("metrics", {}).get("wall_seconds", 0.0))
                    <= float(protocol["common_budgets"]["maximum_wall_seconds"])
                )
                for row in rows
            )
        ),
    }


def _analyze_rows_arm_metrics_record(*, arm_rows: Any) -> dict[str, Any]:
    """Compute arm metrics record from explicit study inputs."""
    return {
        "episodes": len(arm_rows),
        "task_successes": sum((bool(row.get("success")) for row in arm_rows)),
        "clean_or_success_episodes": sum((clean_or_success(row) for row in arm_rows)),
        "activity_endpoint_episodes": sum((activity_constrained_endpoint(row) for row in arm_rows)),
        "episodes_with_gui_action": sum((_metric(row, "gui_actions") > 0 for row in arm_rows)),
        "episodes_with_typed_transaction": sum((_metric(row, "typed_transactions") > 0 for row in arm_rows)),
        "gui_actions": sum((_metric(row, "gui_actions") for row in arm_rows)),
        "typed_transactions": sum((_metric(row, "typed_transactions") for row in arm_rows)),
        "planner_calls": sum((_metric(row, "planner_calls") for row in arm_rows)),
        "planner_actual_calls": sum((_metric(row, "planner_actual_calls") for row in arm_rows)),
        "planner_cache_hits": sum((_metric(row, "planner_cache_hits") for row in arm_rows)),
        "reserve_stops": sum((_metric(row, "inverse_reservation_stops") for row in arm_rows)),
        "restoration_attempts": sum((_metric(row, "restoration_attempts") for row in arm_rows)),
        "restoration_passes": sum((_metric(row, "restoration_passes") for row in arm_rows)),
        "runtime_halts": sum((bool(row.get("metrics", {}).get("runtime_halted")) for row in arm_rows)),
        "stranded_obligation_episodes": sum((_stranded_obligation(row) for row in arm_rows)),
        "unsafe_local_admissions": sum((_unsafe_local_admissions(row) for row in arm_rows)),
        "infrastructure_failures": sum((bool(row.get("infrastructure_failure")) for row in arm_rows)),
    }


def _aggregate_task_budgets(rows: tuple[dict[str, Any], ...]) -> list[dict[str, Any]]:
    task_budget_rows = []
    for task, budgets in TASK_BUDGETS.items():
        for budget in budgets:
            record: dict[str, Any] = {
                "task": task,
                "family_group": TASK_FAMILIES[task],
                "maximum_gui_actions": budget,
                "arms": {},
            }
            for arm in ARMS:
                subset = tuple(
                    (
                        row
                        for row in rows
                        if row.get("episode", {}).get("task") == task
                        and row.get("episode", {}).get("maximum_gui_actions") == budget
                        and (row.get("episode", {}).get("method") == arm)
                    )
                )
                record["arms"][arm] = {
                    "episodes": len(subset),
                    "task_successes": sum((bool(row.get("success")) for row in subset)),
                    "activity_endpoint_episodes": sum((activity_constrained_endpoint(row) for row in subset)),
                    "gui_actions": sum((_metric(row, "gui_actions") for row in subset)),
                    "restoration_attempts": sum((_metric(row, "restoration_attempts") for row in subset)),
                    "stranded_obligation_episodes": sum((_stranded_obligation(row) for row in subset)),
                }
            task_budget_rows.append(record)
    return task_budget_rows


@dataclass
class PairedActivity:
    cell_wins: int
    cell_losses: int
    cell_ties: int
    task_success_wins: int
    task_success_losses: int
    task_success_ties: int
    planner_mediated_paired_wins: int
    seed_rows: list[dict[str, int]]
    task_rows: dict[str, dict[str, Any]]
    seed_cluster_wins: int
    seed_cluster_losses: int
    seed_cluster_ties: int
    sign_pvalue: float
    adjusted_pvalue: float


def _paired_activity(indexed: dict[tuple[int, str, int, str], dict[str, Any]]) -> PairedActivity:
    cell_wins = cell_losses = cell_ties = 0
    task_success_wins = task_success_losses = task_success_ties = 0
    planner_mediated_paired_wins = 0
    seed_rows = []
    task_rows = {
        task: {"full_wins": 0, "local_wins": 0, "ties": 0, "coactivated_paired_wins": 0}
        for task in TASK_BUDGETS
    }
    for seed in SEEDS:
        seed_wins = seed_losses = seed_ties = 0
        for task, budgets in TASK_BUDGETS.items():
            for budget in budgets:
                full_row = indexed[seed, task, budget, FULL_METHOD]
                local_row = indexed[seed, task, budget, LOCAL_ABLATION]
                full_safe = activity_constrained_endpoint(full_row)
                local_safe = activity_constrained_endpoint(local_row)
                win = int(full_safe and (not local_safe))
                loss = int(local_safe and (not full_safe))
                tie = int(full_safe == local_safe)
                seed_wins += win
                seed_losses += loss
                seed_ties += tie
                task_rows[task]["full_wins"] += win
                task_rows[task]["local_wins"] += loss
                task_rows[task]["ties"] += tie
                planner_before_divergence = bool(win) and _planner_before_first_reserve_divergence(
                    full_row, local_row
                )
                planner_mediated_paired_wins += int(planner_before_divergence)
                task_rows[task]["coactivated_paired_wins"] += int(
                    planner_before_divergence
                    and _metric(full_row, "inverse_reservation_stops") > 0
                    and (_unsafe_local_admissions(local_row) > 0)
                    and _stranded_obligation(local_row)
                )
                full_success = bool(full_row.get("success"))
                local_success = bool(local_row.get("success"))
                task_success_wins += int(full_success and (not local_success))
                task_success_losses += int(local_success and (not full_success))
                task_success_ties += int(full_success == local_success)
        cell_wins += seed_wins
        cell_losses += seed_losses
        cell_ties += seed_ties
        seed_rows.append(
            {
                "seed": seed,
                "full_activity_endpoint_wins": seed_wins,
                "local_activity_endpoint_wins": seed_losses,
                "ties": seed_ties,
            }
        )
    seed_cluster_wins = sum(
        (row["full_activity_endpoint_wins"] > row["local_activity_endpoint_wins"] for row in seed_rows)
    )
    seed_cluster_losses = sum(
        (row["local_activity_endpoint_wins"] > row["full_activity_endpoint_wins"] for row in seed_rows)
    )
    seed_cluster_ties = len(seed_rows) - seed_cluster_wins - seed_cluster_losses
    sign_pvalue = _one_sided_sign_pvalue(seed_cluster_wins, seed_cluster_losses)
    adjusted_pvalue = min(1.0, SEQUENCE_FAMILY_SIZE * sign_pvalue)
    return PairedActivity(
        cell_wins=cell_wins,
        cell_losses=cell_losses,
        cell_ties=cell_ties,
        task_success_wins=task_success_wins,
        task_success_losses=task_success_losses,
        task_success_ties=task_success_ties,
        planner_mediated_paired_wins=planner_mediated_paired_wins,
        seed_rows=seed_rows,
        task_rows=task_rows,
        seed_cluster_wins=seed_cluster_wins,
        seed_cluster_losses=seed_cluster_losses,
        seed_cluster_ties=seed_cluster_ties,
        sign_pvalue=sign_pvalue,
        adjusted_pvalue=adjusted_pvalue,
    )


def _augment_task_metrics(rows: tuple[dict[str, Any], ...], paired: PairedActivity) -> None:
    for task in TASK_BUDGETS:
        full_task_rows = tuple(
            (
                row
                for row in rows
                if row.get("episode", {}).get("task") == task
                and row.get("episode", {}).get("method") == FULL_METHOD
            )
        )
        local_task_rows = tuple(
            (
                row
                for row in rows
                if row.get("episode", {}).get("task") == task
                and row.get("episode", {}).get("method") == LOCAL_ABLATION
            )
        )
        paired.task_rows[task].update(
            {
                "full_reserve_stops": sum(
                    (_metric(row, "inverse_reservation_stops") for row in full_task_rows)
                ),
                "local_unsafe_admissions": sum((_unsafe_local_admissions(row) for row in local_task_rows)),
                "local_stranded_obligations": sum((_stranded_obligation(row) for row in local_task_rows)),
                "full_planner_calls": sum((_metric(row, "planner_calls") for row in full_task_rows)),
                "local_planner_calls": sum((_metric(row, "planner_calls") for row in local_task_rows)),
                "full_task_successes": sum((bool(row.get("success")) for row in full_task_rows)),
                "local_task_successes": sum((bool(row.get("success")) for row in local_task_rows)),
                "observed_contract_kinds": sorted(
                    set().union(*(_contract_kinds(row) for row in full_task_rows + local_task_rows))
                ),
            }
        )
        paired.task_rows[task]["coactivated_effect"] = paired.task_rows[task]["coactivated_paired_wins"] > 0


def _goal_hashes(rows: tuple[dict[str, Any], ...]) -> dict[tuple[str, int, int], set[str]]:
    goal_hashes: dict[tuple[str, int, int], set[str]] = {}
    for row in rows:
        episode = row.get("episode", {})
        key = (
            str(episode.get("task")),
            int(episode.get("seed", -1)),
            int(episode.get("maximum_gui_actions", -1)),
        )
        goal_hashes.setdefault(key, set()).add(str(row.get("method_input", {}).get("goal_sha256")))
    return goal_hashes
