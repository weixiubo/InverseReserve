"""Frozen minimal-cleanup successor for InverseReserve.

This eleventh adaptive look evaluates the stronger safe policy requested after
the tenth-look analysis.  The comparator preserves every capacity-feasible
stack.  Only when exact stack-wide reserve blocks a requested transaction does
it restore one top LIFO obligation, discard the stale proposal, and replan from
the realized public state.
"""

from __future__ import annotations

from collections import Counter
from typing import Any, Iterable

from . import inversereserve_budget_frontier_holdout_v2 as frontier
from . import inversereserve_postreview_development_v1 as development
from .capacity_reserve_drivers_v18 import (
    STACK_WIDE_V18,
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
from .minimal_cleanup_replan_capacity_driver_v1 import (
    MINIMAL_CLEANUP_REPLAN_V1,
    MINIMAL_CLEANUP_POLICY_EVENT_V1,
    MinimalCleanupReplanDriverV1,
)


CANDIDATE = "InverseReserve-minimal-cleanup-successor-v1"
STATUS = "sealed_before_any_minimal_cleanup_seed_reset"
FULL_METHOD = STACK_WIDE_V18
SAFE_BASELINE = MINIMAL_CLEANUP_REPLAN_V1
ARMS = (FULL_METHOD, SAFE_BASELINE)
DRIVERS = {
    FULL_METHOD: StackWideCapacityDriverV18,
    SAFE_BASELINE: MinimalCleanupReplanDriverV1,
}
SEEDS = tuple(range(32001, 32021))
BUDGET_LEVELS = tuple(frontier.BUDGET_LEVELS)
TASK_BUDGETS = {
    task: dict(levels) for task, levels in frontier.TASK_BUDGETS.items()
}
TASK_FAMILIES = dict(frontier.TASK_FAMILIES)
COMMON_BUDGETS = dict(frontier.COMMON_BUDGETS)
GENERATION = dict(frontier.GENERATION)
RUNTIME_DEPLOYMENT = dict(frontier.RUNTIME_DEPLOYMENT)
RUNTIME_DEPLOYMENT["cuda_visible_devices"] = "0"
PRESTART_SUPERSESSION = {
    "protocols": [
        {
            "protocol_path": (
                "validation/inversereserve_minimal_cleanup_successor_v1_"
                "gpu0_superseded_prestart_protocol.json"
            ),
            "protocol_sha256": (
                "dc5d2917e5454ea6156c051c41f0fd6f1d9f361d37e01d88434476492a14b569"
            ),
            "scientific_source_commit": (
                "2b42f539f8efe977b19572a7b3e5a3f1a26bf0f8"
            ),
            "claims_opened": 0,
            "episodes_opened": 0,
            "reason": "gpu0_occupied_by_external_queue_before_any_reset",
        },
        {
            "protocol_path": (
                "validation/inversereserve_minimal_cleanup_successor_v1_"
                "gpu1_legacy_runtime_superseded_prestart_protocol.json"
            ),
            "protocol_sha256": (
                "080a05784148da019458048da4a45349c94dc33c8bca1b5ac447036c6c02cb38"
            ),
            "scientific_source_commit": (
                "39e95105b829fb688a981519988e542a2793eed4"
            ),
            "claims_opened": 0,
            "episodes_opened": 0,
            "reason": "legacy_single_gpu_validator_accepted_only_gpu0",
        },
        {
            "protocol_path": (
                "validation/inversereserve_minimal_cleanup_successor_v1_"
                "gpu1_v2_superseded_prestart_protocol.json"
            ),
            "protocol_sha256": (
                "fb6e26a3868578fddfc52be9b5d29b3579afc1181850d47b76e2eebf63fad933"
            ),
            "scientific_source_commit": (
                "a7af95f954ac607c4451fd75efb9554823869af2"
            ),
            "claims_opened": 0,
            "episodes_opened": 0,
            "reason": (
                "gpu1_external_queue_active_after_gpu0_compute_became_idle"
            ),
        },
    ],
    "replacement_changes_only_deployment_validation": True,
}
SEQUENCE_FAMILY_SIZE = 11
OUTCOME_DEFINITIONS = {
    "official_task_success": "environment-provided binary task success",
    "closed_task_success": (
        "official task success with no active typed obligation at episode stop"
    ),
    "physical_stranding": (
        "task failure with at least one active typed obligation at episode stop"
    ),
    "verified_restoration": (
        "at least one ordinary or interrupt-clearance restoration attempt, all "
        "attempts verified, and no active typed obligation at episode stop"
    ),
    "runtime_halt": "runtime_halted is true in the sealed episode metrics",
    "minimal_cleanup_policy": (
        "preserve a live stack whenever stack-wide reserve admits the proposal; "
        "on a capacity rejection, restore exactly one top LIFO obligation, "
        "discard the stale proposal, and replan from realized public state"
    ),
    "reporting_rule": (
        "report official success, failed-stop stranding, runtime halt, verified "
        "restoration, work, and successful-stop active obligations separately"
    ),
}
PRIMARY_COMPARISON = {
    "name": "stack_wide_against_reserve_guided_minimal_cleanup_control",
    "safety": "failed-stop physical stranding and runtime halt, separately",
    "utility": "closed task success; official task success is secondary",
    "effort": "typed transactions and GUI actions",
    "inferential_unit": "fresh-seed cluster across all twelve task-budget cells",
    "comparison": (
        "stack-wide InverseReserve versus an identical stack-wide runtime that "
        "preserves feasible work and restores only one top obligation after an "
        "exact reserve rejection before replanning"
    ),
    "multiplicity": (
        "the paired sign statistic and eleven-look bound are descriptive; no "
        "new confirmatory p-value is claimed for this adaptively selected policy"
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
    "minimal_cleanup_has_zero_physical_stranding": True,
    "minimal_cleanup_has_zero_runtime_halts": True,
    "minimal_cleanup_restorations_all_pass": True,
    "minimal_cleanup_policy_holds": True,
    "minimal_cleanup_policy_binds_live": True,
    "minimal_cleanup_has_zero_policy_failures": True,
    "minimal_cleanup_preserves_lower_obligation_live": True,
    "minimum_minimal_cleanup_closed_successes": 80,
    "minimum_minimal_cleanup_success_families": 3,
    "minimum_stack_closed_successes": 80,
    "minimal_cleanup_closed_noninferiority_to_stack": 0,
}
DECISION_RULE = {
    "on_pass": (
        "report the frozen eleventh-look result as an adaptive stronger-policy "
        "comparison, including whether minimal cleanup improves, ties, or trails "
        "persistent InverseReserve"
    ),
    "on_failure": (
        "seal all rows, report the failed gates without exclusions, and make no "
        "positive stronger-baseline successor claim"
    ),
}
SELECTION_DISCLOSURE = {
    "policy_selected_after_adaptive_tenth_look": True,
    "gates_selected_before_any_new_seed_reset": True,
    "retrospective_proxy_used": False,
    "fresh_seeds_selected_before_any_reset": True,
    "old_episode_reuse_allowed": False,
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
        "prestart_supersession": dict(PRESTART_SUPERSESSION),
        "arms": list(ARMS),
        "isolated_policy_difference": (
            "both arms use the same stack-wide inverse reserve; only the "
            "comparator restores the top live obligation and replans before a "
            "requested transaction, without executing the stale proposal"
        ),
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
        "preregistration": {
            "path": preregistration_path,
            "sha256": preregistration_sha256,
        },
        "outcome_based_exclusion_allowed": False,
        "partial_reexecution_allowed": False,
        "episode_replay_allowed": False,
    }
    validate_protocol(protocol)
    return protocol


def validate_protocol(protocol: dict[str, Any]) -> None:
    if protocol.get("candidate") != CANDIDATE or protocol.get("status") != STATUS:
        raise ValueError("unexpected minimal-cleanup successor identity")
    if tuple(protocol.get("arms", ())) != ARMS or set(DRIVERS) != set(ARMS):
        raise ValueError("minimal-cleanup successor arms changed")
    if protocol.get("tasks") != task_records():
        raise ValueError("minimal-cleanup task grid changed")
    if tuple(protocol.get("fresh_seeds", ())) != SEEDS:
        raise ValueError("minimal-cleanup successor seeds changed")
    if tuple(protocol.get("budget_levels", ())) != BUDGET_LEVELS:
        raise ValueError("minimal-cleanup budget levels changed")
    if protocol.get("common_budgets") != COMMON_BUDGETS:
        raise ValueError("minimal-cleanup common budgets changed")
    if protocol.get("generation") != GENERATION:
        raise ValueError("minimal-cleanup generation changed")
    if protocol.get("runtime_deployment") != RUNTIME_DEPLOYMENT:
        raise ValueError("minimal-cleanup deployment changed")
    if protocol.get("prestart_supersession") != PRESTART_SUPERSESSION:
        raise ValueError("minimal-cleanup prestart supersession changed")
    if protocol.get("expected_episodes") != expected_episodes():
        raise ValueError("minimal-cleanup episode count changed")
    if protocol.get("outcome_definitions") != OUTCOME_DEFINITIONS:
        raise ValueError("minimal-cleanup outcomes changed")
    if protocol.get("primary_comparison") != PRIMARY_COMPARISON:
        raise ValueError("minimal-cleanup primary comparison changed")
    if protocol.get("confirmation_gates") != CONFIRMATION_GATES:
        raise ValueError("minimal-cleanup gates changed")
    if protocol.get("decision_rule") != DECISION_RULE:
        raise ValueError("minimal-cleanup decision rule changed")
    if protocol.get("selection_disclosure") != SELECTION_DISCLOSURE:
        raise ValueError("minimal-cleanup selection disclosure changed")
    if protocol.get("sequence_family_size") != SEQUENCE_FAMILY_SIZE:
        raise ValueError("minimal-cleanup multiplicity family changed")
    if protocol.get("adaptive_history_disclosed") is not True:
        raise ValueError("minimal-cleanup adaptive history disclosure changed")
    for key in ("predecessor", "repositories", "source_sha256", "preregistration"):
        if not isinstance(protocol.get(key), dict):
            raise ValueError(f"minimal-cleanup {key} binding is absent")
    for key in (
        "outcome_based_exclusion_allowed",
        "partial_reexecution_allowed",
        "episode_replay_allowed",
    ):
        if protocol.get(key) is not False:
            raise ValueError(f"minimal-cleanup {key} changed")


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
        raise ValueError("minimal-cleanup manifest is incomplete")
    if len({row["episode_id"] for row in rows}) != len(rows):
        raise ValueError("minimal-cleanup manifest is duplicated")
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
        event
        for event in row.get("trace", ())
        if isinstance(event, dict)
        and event.get("type") == MINIMAL_CLEANUP_POLICY_EVENT_V1
    )


def _cleanup_request_events(row: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    return tuple(event for event in _policy_events(row) if event.get("phase") == "request")


def _cleanup_outcome_events(row: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    return tuple(event for event in _policy_events(row) if event.get("phase") == "outcome")


def minimal_cleanup_policy_holds(row: dict[str, Any]) -> bool:
    requests = _cleanup_request_events(row)
    outcomes = _cleanup_outcome_events(row)
    if len(requests) != len(outcomes):
        return False
    if len(requests) != _metric(row, "minimal_cleanup_attempts"):
        return False
    for request, outcome in zip(requests, outcomes, strict=True):
        active = request.get("active_obligations_before_proposal")
        if type(active) is not int or active < 1:
            return False
        if not (
            request.get("policy") == "restore_one_top_obligation_then_replan"
            and request.get("decision") == "transact"
            and request.get("stale_proposal_execution_allowed") is False
            and outcome.get("policy") == request.get("policy")
            and outcome.get("bid") == request.get("bid")
            and outcome.get("active_obligations_before_proposal") == active
            and outcome.get("stale_proposal_executed") is False
            and outcome.get("replan_from_realized_state")
            is outcome.get("cleanup_passed")
        ):
            return False
        if outcome.get("cleanup_passed") is True and (
            outcome.get("active_obligations_after_cleanup") != active - 1
        ):
            return False
    return True


def _maximum_observed_active(row: dict[str, Any]) -> int:
    values = [_active_count(row)]
    values.extend(
        int(event["active_obligations_before_proposal"])
        for event in _cleanup_request_events(row)
        if type(event.get("active_obligations_before_proposal")) is int
    )
    return max(values, default=-1)

def summarize_rows(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    rows = tuple(rows)
    base = development.summarize_rows(rows)
    modes = Counter(terminal_outcome_mode(row) for row in rows)
    policy_rows = tuple(
        row
        for row in rows
        if row.get("episode", {}).get("method") == SAFE_BASELINE
    )
    base.update(
        {
            "physical_stranding_episodes": sum(
                physical_stranding(row) for row in rows
            ),
            "runtime_halt_episodes": sum(runtime_halt(row) for row in rows),
            "verified_restoration_episodes": sum(
                verified_restoration(row) for row in rows
            ),
            "certified_scope_discharge_episodes": sum(
                certified_scope_discharge_endpoint_v18(row) for row in rows
            ),
            "forward_policy_actions": sum(
                _forward_policy_actions(row) for row in rows
            ),
            "episodes_with_forward_action": sum(
                _forward_policy_actions(row) > 0 for row in rows
            ),
            "closed_task_successes": sum(
                bool(row.get("success")) and _active_count(row) == 0
                for row in rows
            ),
            "minimal_cleanup_policy_events": sum(
                len(_policy_events(row)) for row in policy_rows
            ),
            "minimal_cleanup_attempts": sum(
                _metric(row, "minimal_cleanup_attempts") for row in policy_rows
            ),
            "minimal_cleanup_passes": sum(
                _metric(row, "minimal_cleanup_passes") for row in policy_rows
            ),
            "minimal_cleanup_failures": sum(
                _metric(row, "minimal_cleanup_failures") for row in policy_rows
            ),
            "minimal_cleanup_actions": sum(
                _metric(row, "minimal_cleanup_actions") for row in policy_rows
            ),
            "minimal_cleanup_policy_violating_episodes": sum(
                not minimal_cleanup_policy_holds(row) for row in policy_rows
            ),
            "minimal_cleanup_preserved_lower_obligation_events": sum(
                event.get("cleanup_passed") is True
                and int(event.get("active_obligations_after_cleanup", 0)) > 0
                for row in policy_rows
                for event in _cleanup_outcome_events(row)
            ),
            "maximum_observed_active_obligations": max(
                (_maximum_observed_active(row) for row in policy_rows),
                default=0,
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
                full_row = indexed[(task, level, seed, FULL_METHOD)]
                safe_row = indexed[(task, level, seed, SAFE_BASELINE)]
                full = bool(full_row.get("success")) and _active_count(full_row) == 0
                safe = bool(safe_row.get("success")) and _active_count(safe_row) == 0
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
    safe = metrics[SAFE_BASELINE]
    safe_rows = tuple(
        row
        for row in rows
        if row.get("episode", {}).get("method") == SAFE_BASELINE
    )
    safe_success_families = sum(
        any(
            bool(row.get("success"))
            and row.get("episode", {}).get("family_group") == family
            for row in safe_rows
        )
        for family in set(TASK_FAMILIES.values())
    )
    gates = protocol["confirmation_gates"]
    checks = {
        "complete_exact_grid": exact_manifest and bool(all_claims_complete),
        "zero_infrastructure_failures": sum(
            value["infrastructure_failures"] for value in metrics.values()
        )
        == 0,
        "planner_is_exercised": sum(
            value["planner_calls"] for value in metrics.values()
        )
        > 0,
        "all_rows_respect_hard_budgets": _all_rows_respect_budgets(
            rows, protocol
        ),
        "stack_has_zero_physical_stranding": (
            full["physical_stranding_episodes"] == 0
        ),
        "stack_has_zero_runtime_halts": full["runtime_halt_episodes"] == 0,
        "stack_restorations_all_pass": _all_attempted_restorations_pass(full),
        "minimal_cleanup_has_zero_physical_stranding": (
            safe["physical_stranding_episodes"] == 0
        ),
        "minimal_cleanup_has_zero_runtime_halts": (
            safe["runtime_halt_episodes"] == 0
        ),
        "minimal_cleanup_restorations_all_pass": (
            _all_attempted_restorations_pass(safe)
        ),
        "minimal_cleanup_policy_holds": (
            safe["minimal_cleanup_policy_violating_episodes"] == 0
            and all(minimal_cleanup_policy_holds(row) for row in safe_rows)
        ),
        "minimal_cleanup_policy_binds_live": safe["minimal_cleanup_attempts"] > 0,
        "minimal_cleanup_has_zero_policy_failures": (
            safe["minimal_cleanup_failures"] == 0
            and safe["minimal_cleanup_passes"] == safe["minimal_cleanup_attempts"]
        ),
        "minimal_cleanup_preserves_lower_obligation_live": (
            safe["minimal_cleanup_preserved_lower_obligation_events"] > 0
        ),
        "minimum_minimal_cleanup_closed_successes": (
            safe["closed_task_successes"]
            >= int(gates["minimum_minimal_cleanup_closed_successes"])
        ),
        "minimum_minimal_cleanup_success_families": (
            safe_success_families
            >= int(gates["minimum_minimal_cleanup_success_families"])
        ),
        "minimum_stack_closed_successes": (
            full["closed_task_successes"]
            >= int(gates["minimum_stack_closed_successes"])
        ),
        "minimal_cleanup_closed_noninferiority_to_stack": (
            safe["closed_task_successes"] - full["closed_task_successes"]
            >= int(gates["minimal_cleanup_closed_noninferiority_to_stack"])
        ),
    }
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
