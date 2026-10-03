from __future__ import annotations

from collections import Counter
from typing import Any, Iterable

from inversereserve.controllers.confirmation_agents_v15 import FullPactConfirmationDriverV15
from inversereserve.controllers.pact_controller_v8 import inverse_action_cost_v8
from inversereserve.core.recovery_capacity import remaining_after_action as _remaining_capacity_after_proposal
from inversereserve.studies.episode_grid import matches_registered_grid
from inversereserve.studies.inversereserve_live_resource_stress_v1 import (
    FULL_METHOD,
    GUI_ACTION_BUDGETS,
    LOCAL_ABLATION,
    TASK,
    _active_count,
    _metric,
    _one_sided_sign_pvalue,
    _recovery_safe,
    _unsafe_local_admissions,
)
from inversereserve.studies.validation import require

"Successor live resource stress after the v1 dynamic-grounding diagnosis."
ARMS = (FULL_METHOD, LOCAL_ABLATION)
SEEDS = tuple(range(29101, 29121))
COMMON_BUDGETS = {"maximum_planner_calls": 1, "maximum_wall_seconds": 60.0}


class _ResourceStressDriverV15(FullPactConfirmationDriverV15):
    stack_wide = True

    def inverse_reserve(self, candidate: Any, decision: str) -> tuple[bool, int]:
        active_reserve = sum(
            (inverse_action_cost_v8(transaction.contract) for transaction in self.runtime.active)
        )
        proposal_reserve = 0
        if decision == "transact":
            contract = self.inventory().contract_by_bid.get(candidate.bid)
            if contract is None:
                return (False, active_reserve)
            proposal_reserve = inverse_action_cost_v8(contract)
        stack_wide_reserve = active_reserve + proposal_reserve
        applied_reserve = stack_wide_reserve if self.stack_wide else proposal_reserve
        remaining_after_action = _remaining_capacity_after_proposal(
            self.budgets["maximum_gui_actions"], len(self.executor.actions)
        )
        allowed = remaining_after_action >= applied_reserve
        self.inverse_reservation_audits += 1
        self.audit(
            {
                "type": "live_resource_stress_reservation_v2",
                "reservation_rule": "stack_wide" if self.stack_wide else "proposal_local",
                "decision": decision,
                "bid": candidate.bid,
                "registered_active_inverse_cost": active_reserve,
                "proposal_inverse_cost": proposal_reserve,
                "stack_wide_required_inverse_cost": stack_wide_reserve,
                "applied_inverse_reserve": applied_reserve,
                "remaining_after_action": remaining_after_action,
                "allowed": allowed,
            }
        )
        return (allowed, applied_reserve)


class StackWideReserveStressDriverV15(_ResourceStressDriverV15):
    method_id = FULL_METHOD
    stack_wide = True


class ProposalLocalReserveStressDriverV15(_ResourceStressDriverV15):
    method_id = LOCAL_ABLATION
    stack_wide = False


DRIVERS = {FULL_METHOD: StackWideReserveStressDriverV15, LOCAL_ABLATION: ProposalLocalReserveStressDriverV15}


def validate_protocol(protocol: dict[str, Any]) -> None:
    require(
        not protocol.get("candidate") != "InverseReserve-live-resource-stress-v2",
        "unexpected successor resource-stress candidate",
    )
    require(
        not protocol.get("status") != "sealed_before_any_successor_episode_reset",
        "successor resource-stress protocol is not pre-reset sealed",
    )
    require(
        not (tuple(protocol.get("arms", ())) != ARMS or set(DRIVERS) != set(ARMS)),
        "successor resource-stress arms changed",
    )
    require(not protocol.get("task") != TASK, "successor resource-stress task changed")
    require(not tuple(protocol.get("fresh_seeds", ())) != SEEDS, "successor resource-stress seeds changed")
    require(
        not tuple(protocol.get("gui_action_budgets", ())) != GUI_ACTION_BUDGETS,
        "successor resource-stress budgets changed",
    )
    require(
        not protocol.get("common_budgets") != COMMON_BUDGETS,
        "successor resource-stress common budgets changed",
    )
    expected = len(ARMS) * len(SEEDS) * len(GUI_ACTION_BUDGETS)
    require(
        not protocol.get("expected_episodes") != expected, "successor resource-stress episode count changed"
    )
    require(
        not protocol.get("planner_policy") != {"expected_calls": 0, "on_any_call": "fail_the_episode"},
        "successor resource-stress planner policy changed",
    )
    require(isinstance(protocol.get("source_sha256"), dict), "successor source bindings are absent")
    require(isinstance(protocol.get("preregistration"), dict), "successor preregistration is absent")


def episode_manifest(protocol: dict[str, Any]) -> list[dict[str, Any]]:
    validate_protocol(protocol)
    rows: list[dict[str, Any]] = []
    for seed_index, seed in enumerate(SEEDS):
        for budget_index, budget in enumerate(GUI_ACTION_BUDGETS):
            rotation = (seed_index + budget_index) % len(ARMS)
            order = ARMS[rotation:] + ARMS[:rotation]
            for arm_position, method in enumerate(order):
                rows.append(
                    {
                        "episode_index": len(rows),
                        "seed_index": seed_index,
                        "budget_index": budget_index,
                        "arm_position": arm_position,
                        "task": TASK,
                        "seed": seed,
                        "maximum_gui_actions": budget,
                        "method": method,
                        "episode_id": f"{TASK}__seed{seed}__budget{budget}__{method}",
                    }
                )
    if len(rows) != int(protocol["expected_episodes"]):
        raise ValueError("successor resource-stress manifest is incomplete")
    if len({row["episode_id"] for row in rows}) != len(rows):
        raise ValueError("successor resource-stress manifest is duplicated")
    return rows


def arm_order_counts(protocol: dict[str, Any]) -> dict[str, dict[int, int]]:
    counts = {arm: Counter() for arm in ARMS}
    for row in episode_manifest(protocol):
        counts[row["method"]][int(row["arm_position"])] += 1
    return {arm: dict(sorted(values.items())) for arm, values in counts.items()}


def _live_groundings(row: dict[str, Any]) -> int:
    return sum(
        (event.get("type") == "live_dynamic_inverse_grounding_v15" for event in row.get("runtime_events", ()))
    )


def analyze_rows(
    rows: Iterable[dict[str, Any]], protocol: dict[str, Any], *, all_claims_complete: bool
) -> dict[str, Any]:
    validate_protocol(protocol)
    rows = tuple(rows)
    manifest = episode_manifest(protocol)
    exact_manifest = matches_registered_grid(rows, manifest)
    indexed = {
        (
            int(row["episode"]["seed"]),
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
    cell_wins = cell_losses = cell_ties = 0
    seed_rows = []
    for seed in SEEDS:
        wins = losses = ties = 0
        for budget in GUI_ACTION_BUDGETS:
            full_safe = _recovery_safe(indexed[seed, budget, FULL_METHOD])
            local_safe = _recovery_safe(indexed[seed, budget, LOCAL_ABLATION])
            wins += int(full_safe and (not local_safe))
            losses += int(local_safe and (not full_safe))
            ties += int(full_safe == local_safe)
        cell_wins += wins
        cell_losses += losses
        cell_ties += ties
        seed_rows.append({"seed": seed, "full_safety_wins": wins, "local_safety_wins": losses, "ties": ties})
    seed_wins = sum((row["full_safety_wins"] > row["local_safety_wins"] for row in seed_rows))
    seed_losses = sum((row["local_safety_wins"] > row["full_safety_wins"] for row in seed_rows))
    seed_ties = len(seed_rows) - seed_wins - seed_losses
    sign_pvalue = _one_sided_sign_pvalue(seed_wins, seed_losses)
    full = arm_metrics[FULL_METHOD]
    local = arm_metrics[LOCAL_ABLATION]
    checks = _rows_confirmation_checks(
        all_claims_complete=all_claims_complete,
        arm_metrics=arm_metrics,
        cell_losses=cell_losses,
        exact_manifest=exact_manifest,
        full=full,
        local=local,
        protocol=protocol,
        rows=rows,
        seed_losses=seed_losses,
        seed_wins=seed_wins,
        sign_pvalue=sign_pvalue,
    )
    return {
        "metrics": arm_metrics,
        "paired_safety": {
            "cell_wins": cell_wins,
            "cell_losses": cell_losses,
            "cell_ties": cell_ties,
            "seed_cluster_wins": seed_wins,
            "seed_cluster_losses": seed_losses,
            "seed_cluster_ties": seed_ties,
            "one_sided_exact_sign_pvalue": sign_pvalue,
            "seed_rows": seed_rows,
        },
        "checks": checks,
        "passed": all(checks.values()),
    }


__all__ = [
    "ARMS",
    "COMMON_BUDGETS",
    "DRIVERS",
    "SEEDS",
    "analyze_rows",
    "arm_order_counts",
    "episode_manifest",
    "validate_protocol",
]


def _rows_confirmation_checks(
    *,
    all_claims_complete: bool,
    arm_metrics: Any,
    cell_losses: int,
    exact_manifest: bool,
    full: Any,
    local: Any,
    protocol: Any,
    rows: tuple[dict[str, Any], ...],
    seed_losses: int,
    seed_wins: int,
    sign_pvalue: float,
) -> dict[str, bool]:
    """Apply the registered decision gates to computed outcomes."""
    return {
        "exact_complete_manifest": exact_manifest and all_claims_complete,
        "zero_infrastructure_failures": all(
            (metrics["infrastructure_failures"] == 0 for metrics in arm_metrics.values())
        ),
        "zero_planner_calls": all((metrics["planner_calls"] == 0 for metrics in arm_metrics.values())),
        "stack_wide_reserve_binds_live": full["reserve_stops"] > 0,
        "stack_wide_live_dynamic_grounding_exercised": full["live_dynamic_inverse_groundings"] > 0,
        "stack_wide_restorations_all_pass": full["restoration_attempts"] > 0
        and full["restoration_passes"] == full["restoration_attempts"]
        and (full["runtime_halts"] == 0)
        and (full["stranded_obligation_episodes"] == 0),
        "proposal_local_rule_makes_unsafe_admissions": local["unsafe_local_admissions"] > 0,
        "proposal_local_rule_strands_obligations": local["stranded_obligation_episodes"] > 0,
        "no_paired_safety_loss": cell_losses == 0 and seed_losses == 0,
        "minimum_seed_cluster_safety_wins": seed_wins
        >= int(protocol["confirmation_gates"]["minimum_seed_cluster_safety_wins"]),
        "seed_cluster_sign_test_passes": sign_pvalue
        <= float(protocol["confirmation_gates"]["maximum_one_sided_sign_pvalue"]),
        "all_rows_respect_hard_action_budget": all(
            (_metric(row, "gui_actions") <= int(row["episode"]["maximum_gui_actions"]) for row in rows)
        ),
    }


def _analyze_rows_arm_metrics_record(*, arm_rows: Any) -> dict[str, Any]:
    """Compute arm metrics record from explicit study inputs."""
    return {
        "episodes": len(arm_rows),
        "task_successes": sum((bool(row.get("success")) for row in arm_rows)),
        "recovery_safe_episodes": sum((_recovery_safe(row) for row in arm_rows)),
        "reserve_stops": sum((_metric(row, "inverse_reservation_stops") for row in arm_rows)),
        "restoration_attempts": sum((_metric(row, "restoration_attempts") for row in arm_rows)),
        "restoration_passes": sum((_metric(row, "restoration_passes") for row in arm_rows)),
        "runtime_halts": sum((bool(row.get("metrics", {}).get("runtime_halted")) for row in arm_rows)),
        "stranded_obligation_episodes": sum(
            (not bool(row.get("success")) and _active_count(row) > 0 for row in arm_rows)
        ),
        "unsafe_local_admissions": sum((_unsafe_local_admissions(row) for row in arm_rows)),
        "live_dynamic_inverse_groundings": sum((_live_groundings(row) for row in arm_rows)),
        "planner_calls": sum((_metric(row, "planner_calls") for row in arm_rows)),
        "infrastructure_failures": sum((bool(row.get("infrastructure_failure")) for row in arm_rows)),
    }
