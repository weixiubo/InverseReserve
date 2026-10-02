"""Outcome-independent study design and episode population; analysis remains in the parent study module."""

from __future__ import annotations

from collections import Counter
from typing import Any

from inversereserve.controllers.capacity_reserve_drivers_v18 import STACK_WIDE_V18, StackWideCapacityDriverV18
from inversereserve.controllers.minimal_cleanup_replan_capacity_driver_v1 import (
    MINIMAL_CLEANUP_REPLAN_V1,
    MinimalCleanupReplanDriverV1,
)
from inversereserve.studies import inversereserve_budget_frontier_holdout_v2 as frontier
from inversereserve.studies.validation import require

CANDIDATE = "InverseReserve-minimal-cleanup-successor-v1"
STATUS = "sealed_before_any_minimal_cleanup_seed_reset"
FULL_METHOD = STACK_WIDE_V18
SAFE_BASELINE = MINIMAL_CLEANUP_REPLAN_V1
ARMS = (FULL_METHOD, SAFE_BASELINE)
DRIVERS = {FULL_METHOD: StackWideCapacityDriverV18, SAFE_BASELINE: MinimalCleanupReplanDriverV1}
SEEDS = tuple(range(32001, 32021))
BUDGET_LEVELS = tuple(frontier.BUDGET_LEVELS)
TASK_BUDGETS = {task: dict(levels) for task, levels in frontier.TASK_BUDGETS.items()}
TASK_FAMILIES = dict(frontier.TASK_FAMILIES)
COMMON_BUDGETS = dict(frontier.COMMON_BUDGETS)
GENERATION = dict(frontier.GENERATION)
RUNTIME_DEPLOYMENT = dict(frontier.RUNTIME_DEPLOYMENT)
RUNTIME_DEPLOYMENT["cuda_visible_devices"] = "0"
PRESTART_SUPERSESSION = {
    "protocols": [
        {
            "protocol_path": "validation/inversereserve_minimal_cleanup_successor_v1_gpu0_superseded_prestart_protocol.json",
            "protocol_sha256": "dc5d2917e5454ea6156c051c41f0fd6f1d9f361d37e01d88434476492a14b569",
            "scientific_source_commit": "2b42f539f8efe977b19572a7b3e5a3f1a26bf0f8",
            "claims_opened": 0,
            "episodes_opened": 0,
            "reason": "gpu0_occupied_by_external_queue_before_any_reset",
        },
        {
            "protocol_path": "validation/inversereserve_minimal_cleanup_successor_v1_gpu1_legacy_runtime_superseded_prestart_protocol.json",
            "protocol_sha256": "080a05784148da019458048da4a45349c94dc33c8bca1b5ac447036c6c02cb38",
            "scientific_source_commit": "39e95105b829fb688a981519988e542a2793eed4",
            "claims_opened": 0,
            "episodes_opened": 0,
            "reason": "legacy_single_gpu_validator_accepted_only_gpu0",
        },
        {
            "protocol_path": "validation/inversereserve_minimal_cleanup_successor_v1_gpu1_v2_superseded_prestart_protocol.json",
            "protocol_sha256": "fb6e26a3868578fddfc52be9b5d29b3579afc1181850d47b76e2eebf63fad933",
            "scientific_source_commit": "a7af95f954ac607c4451fd75efb9554823869af2",
            "claims_opened": 0,
            "episodes_opened": 0,
            "reason": "gpu1_external_queue_active_after_gpu0_compute_became_idle",
        },
    ],
    "replacement_changes_only_deployment_validation": True,
}
SEQUENCE_FAMILY_SIZE = 11
OUTCOME_DEFINITIONS = {
    "official_task_success": "environment-provided binary task success",
    "closed_task_success": "official task success with no active typed obligation at episode stop",
    "physical_stranding": "task failure with at least one active typed obligation at episode stop",
    "verified_restoration": "at least one ordinary or interrupt-clearance restoration attempt, all attempts verified, and no active typed obligation at episode stop",
    "runtime_halt": "runtime_halted is true in the sealed episode metrics",
    "minimal_cleanup_policy": "preserve a live stack whenever stack-wide reserve admits the proposal; on a capacity rejection, restore exactly one top LIFO obligation, discard the stale proposal, and replan from realized public state",
    "reporting_rule": "report official success, failed-stop stranding, runtime halt, verified restoration, work, and successful-stop active obligations separately",
}
PRIMARY_COMPARISON = {
    "name": "stack_wide_against_reserve_guided_minimal_cleanup_control",
    "safety": "failed-stop physical stranding and runtime halt, separately",
    "utility": "closed task success; official task success is secondary",
    "effort": "typed transactions and GUI actions",
    "inferential_unit": "fresh-seed cluster across all twelve task-budget cells",
    "comparison": "stack-wide InverseReserve versus an identical stack-wide runtime that preserves feasible work and restores only one top obligation after an exact reserve rejection before replanning",
    "multiplicity": "the paired sign statistic and eleven-look bound are descriptive; no new confirmatory p-value is claimed for this adaptively selected policy",
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
    "on_pass": "report the frozen eleventh-look result as an adaptive stronger-policy comparison, including whether minimal cleanup improves, ties, or trails persistent InverseReserve",
    "on_failure": "seal all rows, report the failed gates without exclusions, and make no positive stronger-baseline successor claim",
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
        "prestart_supersession": dict(PRESTART_SUPERSESSION),
        "arms": list(ARMS),
        "isolated_policy_difference": "both arms use the same stack-wide inverse reserve; only the comparator restores the top live obligation and replans before a requested transaction, without executing the stale proposal",
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
        "unexpected minimal-cleanup successor identity",
    )
    require(
        not (tuple(protocol.get("arms", ())) != ARMS or set(DRIVERS) != set(ARMS)),
        "minimal-cleanup successor arms changed",
    )
    require(not protocol.get("tasks") != task_records(), "minimal-cleanup task grid changed")
    require(not tuple(protocol.get("fresh_seeds", ())) != SEEDS, "minimal-cleanup successor seeds changed")
    require(
        not tuple(protocol.get("budget_levels", ())) != BUDGET_LEVELS, "minimal-cleanup budget levels changed"
    )
    require(not protocol.get("common_budgets") != COMMON_BUDGETS, "minimal-cleanup common budgets changed")
    require(not protocol.get("generation") != GENERATION, "minimal-cleanup generation changed")
    require(
        not protocol.get("runtime_deployment") != RUNTIME_DEPLOYMENT, "minimal-cleanup deployment changed"
    )
    require(
        not protocol.get("prestart_supersession") != PRESTART_SUPERSESSION,
        "minimal-cleanup prestart supersession changed",
    )
    require(
        not protocol.get("expected_episodes") != expected_episodes(), "minimal-cleanup episode count changed"
    )
    require(
        not protocol.get("outcome_definitions") != OUTCOME_DEFINITIONS, "minimal-cleanup outcomes changed"
    )
    require(
        not protocol.get("primary_comparison") != PRIMARY_COMPARISON,
        "minimal-cleanup primary comparison changed",
    )
    require(not protocol.get("confirmation_gates") != CONFIRMATION_GATES, "minimal-cleanup gates changed")
    require(not protocol.get("decision_rule") != DECISION_RULE, "minimal-cleanup decision rule changed")
    require(
        not protocol.get("selection_disclosure") != SELECTION_DISCLOSURE,
        "minimal-cleanup selection disclosure changed",
    )
    require(
        not protocol.get("sequence_family_size") != SEQUENCE_FAMILY_SIZE,
        "minimal-cleanup multiplicity family changed",
    )
    require(
        not protocol.get("adaptive_history_disclosed") is not True,
        "minimal-cleanup adaptive history disclosure changed",
    )
    for key in ("predecessor", "repositories", "source_sha256", "preregistration"):
        if not isinstance(protocol.get(key), dict):
            raise ValueError(f"minimal-cleanup {key} binding is absent")
    for key in ("outcome_based_exclusion_allowed", "partial_reexecution_allowed", "episode_replay_allowed"):
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
                            "episode_id": f"{task}__seed{seed}__{level}{budget}__{method}",
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
