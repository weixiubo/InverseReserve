"""Prospective live-GUI validation of host-requested persistent handoff."""

from __future__ import annotations

from collections import Counter
from typing import Any, Iterable

from . import inversereserve_model_family_replication_v1 as model_family
from .exogenous_handoff_driver_v1 import (
    HANDOFF_DEPTH_ONE_V1,
    HANDOFF_DEPTH_TWO_V1,
    StackWideHandoffDepthOneV1,
    StackWideHandoffDepthTwoV1,
)
from .inversereserve_capacity_regime_successor_v3 import (
    _all_rows_respect_budgets,
)
from .inversereserve_live_resource_stress_v1 import _active_count, _metric


CANDIDATE = "InverseReserve-exogenous-handoff-v1"
STATUS = "frozen_before_any_seed_39001_through_39020_reset"
DEPTH_ONE = HANDOFF_DEPTH_ONE_V1
DEPTH_TWO = HANDOFF_DEPTH_TWO_V1
ARMS = (DEPTH_ONE, DEPTH_TWO)
DRIVERS = {
    DEPTH_ONE: StackWideHandoffDepthOneV1,
    DEPTH_TWO: StackWideHandoffDepthTwoV1,
}
SEEDS = tuple(range(39001, 39021))
TASK_FAMILIES = dict(model_family.TASK_FAMILIES)
TASK_BUDGETS = {
    task: int(levels["high"])
    for task, levels in model_family.TASK_BUDGETS.items()
}
COMMON_BUDGETS = dict(model_family.COMMON_BUDGETS)
GENERATION = dict(model_family.GENERATION)
RUNTIME_DEPLOYMENT = dict(model_family.RUNTIME_DEPLOYMENT)
PLANNER_MODEL = {
    **model_family.PLANNER_MODEL,
    "snapshot_files_sha256": dict(
        model_family.PLANNER_MODEL["snapshot_files_sha256"]
    ),
}
MINIMUM_DEPTH_TWO_HANDOFFS = 40
MINIMUM_DEPTH_TWO_FAMILIES = 2
MINIMUM_TOTAL_HANDOFFS = 120
OUTCOME_DEFINITIONS = {
    "exogenous_handoff_request": (
        "the host interrupts before the next proposal at the first live "
        "prefix whose registered obligation depth reaches the frozen target"
    ),
    "successful_handoff": (
        "the complete registered LIFO program is attempted, every restoration "
        "verifies, the active stack is empty, no runtime halt occurs, and the "
        "hard GUI-action budget is respected"
    ),
    "activation": (
        "the requested live depth is reached before terminal completion; "
        "non-activation rows remain in the complete population"
    ),
    "estimand": (
        "finite four-family, two-depth, fresh-seed MiniWoB++ population"
    ),
}
PRIMARY_QUESTION = {
    "name": "systematic_live_exogenous_handoff",
    "question": (
        "whether the frozen stack-wide runtime actually executes and verifies "
        "its registered recovery program when a host takes control at depth "
        "one or depth two"
    ),
    "not_a_reserve_scope_comparison": True,
    "not_a_task_success_comparison": True,
    "intervention_timing": (
        "first proposal boundary after the target live depth materializes"
    ),
    "reporting": (
        "report every activation, non-activation, recovery, halt, active stop, "
        "budget check, task, depth, and fresh seed"
    ),
}
VALIDITY_GATES = {
    "complete_exact_grid": True,
    "zero_infrastructure_failures": True,
    "planner_is_exercised": True,
    "all_rows_respect_hard_budgets": True,
    "every_depth_one_row_activates": True,
    "minimum_depth_two_handoffs": MINIMUM_DEPTH_TWO_HANDOFFS,
    "minimum_depth_two_families": MINIMUM_DEPTH_TWO_FAMILIES,
    "minimum_total_handoffs": MINIMUM_TOTAL_HANDOFFS,
    "every_request_occurs_at_or_above_target_depth": True,
    "every_request_is_capacity_solvent": True,
    "every_requested_handoff_passes": True,
    "every_requested_restoration_verifies": True,
    "every_requested_handoff_empties_stack": True,
    "zero_requested_runtime_halts": True,
    "recovery_actions_do_not_exceed_registered_bound": True,
    "all_successes_lower_95_above_0_95": True,
}
DECISION_RULE = {
    "on_pass": (
        "report the complete systematic exogenous-handoff validation as "
        "prospective live execution evidence, with its finite supported scope"
    ),
    "on_failure": (
        "seal all rows without exclusion or replay and make no positive "
        "exogenous-handoff claim"
    ),
}
SELECTION_DISCLOSURE = {
    "selected_after_final_pdf_blind_reviews": True,
    "reviewer_requested_live_interruption_test": True,
    "adaptive_robustness_study_not_independent_confirmation": True,
    "fresh_seeds_frozen_before_any_reset": True,
    "no_reserve_scope_comparator": True,
    "no_predecessor_episode_reuse": True,
}


def task_records() -> list[dict[str, Any]]:
    return [
        {
            "task_id": task,
            "family_group": TASK_FAMILIES[task],
            "maximum_gui_actions": budget,
        }
        for task, budget in TASK_BUDGETS.items()
    ]


def expected_episodes() -> int:
    return len(ARMS) * len(SEEDS) * len(TASK_BUDGETS)


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
        "predecessor": dict(predecessor),
        "arms": list(ARMS),
        "tasks": task_records(),
        "fresh_seeds": list(SEEDS),
        "common_budgets": dict(COMMON_BUDGETS),
        "generation": dict(GENERATION),
        "runtime_deployment": dict(RUNTIME_DEPLOYMENT),
        "planner_model": {
            **PLANNER_MODEL,
            "snapshot_files_sha256": dict(
                PLANNER_MODEL["snapshot_files_sha256"]
            ),
        },
        "expected_episodes": expected_episodes(),
        "outcome_definitions": dict(OUTCOME_DEFINITIONS),
        "primary_question": dict(PRIMARY_QUESTION),
        "validity_gates": dict(VALIDITY_GATES),
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
        raise ValueError("unexpected exogenous-handoff identity")
    if tuple(protocol.get("arms", ())) != ARMS or set(DRIVERS) != set(ARMS):
        raise ValueError("exogenous-handoff arms changed")
    if protocol.get("tasks") != task_records():
        raise ValueError("exogenous-handoff task population changed")
    if tuple(protocol.get("fresh_seeds", ())) != SEEDS:
        raise ValueError("exogenous-handoff seeds changed")
    if protocol.get("common_budgets") != COMMON_BUDGETS:
        raise ValueError("exogenous-handoff common budgets changed")
    if protocol.get("generation") != GENERATION:
        raise ValueError("exogenous-handoff generation changed")
    if protocol.get("runtime_deployment") != RUNTIME_DEPLOYMENT:
        raise ValueError("exogenous-handoff deployment changed")
    if protocol.get("planner_model") != PLANNER_MODEL:
        raise ValueError("exogenous-handoff model changed")
    if protocol.get("expected_episodes") != expected_episodes():
        raise ValueError("exogenous-handoff episode count changed")
    if protocol.get("outcome_definitions") != OUTCOME_DEFINITIONS:
        raise ValueError("exogenous-handoff outcomes changed")
    if protocol.get("primary_question") != PRIMARY_QUESTION:
        raise ValueError("exogenous-handoff question changed")
    if protocol.get("validity_gates") != VALIDITY_GATES:
        raise ValueError("exogenous-handoff gates changed")
    if protocol.get("decision_rule") != DECISION_RULE:
        raise ValueError("exogenous-handoff decision rule changed")
    if protocol.get("selection_disclosure") != SELECTION_DISCLOSURE:
        raise ValueError("exogenous-handoff disclosure changed")
    for key in ("predecessor", "repositories", "source_sha256", "preregistration"):
        if not isinstance(protocol.get(key), dict):
            raise ValueError(f"exogenous-handoff {key} binding is absent")
    for key in (
        "outcome_based_exclusion_allowed",
        "partial_reexecution_allowed",
        "episode_replay_allowed",
    ):
        if protocol.get(key) is not False:
            raise ValueError(f"exogenous-handoff {key} changed")


def episode_manifest(protocol: dict[str, Any]) -> list[dict[str, Any]]:
    validate_protocol(protocol)
    rows: list[dict[str, Any]] = []
    for seed_index, seed in enumerate(SEEDS):
        for task_index, (task, budget) in enumerate(TASK_BUDGETS.items()):
            rotation = (seed_index + task_index) % len(ARMS)
            order = ARMS[rotation:] + ARMS[:rotation]
            for arm_position, method in enumerate(order):
                target_depth = 1 if method == DEPTH_ONE else 2
                rows.append(
                    {
                        "episode_index": len(rows),
                        "seed_index": seed_index,
                        "task_index": task_index,
                        "arm_position": arm_position,
                        "task": task,
                        "family_group": TASK_FAMILIES[task],
                        "seed": seed,
                        "maximum_gui_actions": budget,
                        "method": method,
                        "handoff_target_depth": target_depth,
                        "episode_id": (
                            f"{task}__seed{seed}__high{budget}"
                            f"__handoff_depth{target_depth}"
                        ),
                    }
                )
    if len(rows) != expected_episodes():
        raise ValueError("exogenous-handoff manifest is incomplete")
    if len({row["episode_id"] for row in rows}) != len(rows):
        raise ValueError("exogenous-handoff manifest is duplicated")
    return rows


def arm_order_counts(protocol: dict[str, Any]) -> dict[str, dict[int, int]]:
    counts = {arm: Counter() for arm in ARMS}
    for row in episode_manifest(protocol):
        counts[row["method"]][int(row["arm_position"])] += 1
    return {arm: dict(sorted(values.items())) for arm, values in counts.items()}


def _requested(row: dict[str, Any]) -> bool:
    return _metric(row, "exogenous_handoff_requested_v1") == 1


def _passed(row: dict[str, Any]) -> bool:
    return _metric(row, "exogenous_handoff_passed_v1") == 1


def _runtime_halted(row: dict[str, Any]) -> bool:
    return bool(row.get("metrics", {}).get("runtime_halted"))


def _recovery_actions(row: dict[str, Any]) -> int:
    return _metric(row, "gui_actions") - _metric(
        row, "exogenous_handoff_actions_before_v1"
    )


def summarize_rows(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    rows = tuple(rows)
    requested = tuple(row for row in rows if _requested(row))
    return {
        "episodes": len(rows),
        "infrastructure_failures": sum(
            bool(row.get("infrastructure_failure")) for row in rows
        ),
        "gui_actions": sum(_metric(row, "gui_actions") for row in rows),
        "typed_transactions": sum(
            _metric(row, "typed_transactions") for row in rows
        ),
        "planner_calls": sum(_metric(row, "planner_calls") for row in rows),
        "planner_actual_calls": sum(
            _metric(row, "planner_actual_calls") for row in rows
        ),
        "handoff_requests": len(requested),
        "handoff_passes": sum(_passed(row) for row in requested),
        "handoff_failures": sum(not _passed(row) for row in requested),
        "requested_runtime_halts": sum(
            _runtime_halted(row) for row in requested
        ),
        "requested_active_after": sum(
            _metric(row, "exogenous_handoff_active_after_v1")
            for row in requested
        ),
        "requested_restoration_attempts": sum(
            _metric(row, "exogenous_handoff_restoration_attempts_v1")
            for row in requested
        ),
        "requested_restoration_passes": sum(
            _metric(row, "exogenous_handoff_restoration_passes_v1")
            for row in requested
        ),
        "maximum_requested_depth": max(
            (
                _metric(row, "exogenous_handoff_active_before_v1")
                for row in requested
            ),
            default=0,
        ),
        "maximum_registered_recovery_cost": max(
            (
                _metric(row, "exogenous_handoff_registered_cost_v1")
                for row in requested
            ),
            default=0,
        ),
        "maximum_recovery_actions": max(
            (_recovery_actions(row) for row in requested),
            default=0,
        ),
    }


def _all_success_lower_95(successes: int, trials: int) -> float:
    """Two-sided 95% Clopper-Pearson lower limit when every trial succeeds."""

    if trials <= 0 or successes != trials:
        return 0.0
    return (0.025) ** (1.0 / trials)


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
    exact_manifest = bool(
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
    requested = tuple(row for row in rows if _requested(row))
    depth_one_rows = tuple(
        row
        for row in rows
        if row.get("episode", {}).get("method") == DEPTH_ONE
    )
    depth_two_requests = tuple(
        row
        for row in requested
        if row.get("episode", {}).get("method") == DEPTH_TWO
    )
    depth_two_families = {
        str(row["episode"]["family_group"]) for row in depth_two_requests
    }
    by_task_depth = []
    for task, budget in TASK_BUDGETS.items():
        for arm in ARMS:
            subset = tuple(
                row
                for row in rows
                if row.get("episode", {}).get("task") == task
                and row.get("episode", {}).get("method") == arm
            )
            by_task_depth.append(
                {
                    "task": task,
                    "family_group": TASK_FAMILIES[task],
                    "maximum_gui_actions": budget,
                    "handoff_target_depth": 1 if arm == DEPTH_ONE else 2,
                    "metrics": summarize_rows(subset),
                }
            )
    requests = len(requested)
    passes = sum(_passed(row) for row in requested)
    lower_95 = _all_success_lower_95(passes, requests)
    checks = {
        "complete_exact_grid": exact_manifest and bool(all_claims_complete),
        "zero_infrastructure_failures": all(
            not row.get("infrastructure_failure") for row in rows
        ),
        "planner_is_exercised": sum(
            _metric(row, "planner_calls") for row in rows
        )
        > 0,
        "all_rows_respect_hard_budgets": _all_rows_respect_budgets(
            rows, protocol
        ),
        "every_depth_one_row_activates": bool(depth_one_rows)
        and all(_requested(row) for row in depth_one_rows),
        "minimum_depth_two_handoffs": (
            len(depth_two_requests) >= MINIMUM_DEPTH_TWO_HANDOFFS
        ),
        "minimum_depth_two_families": (
            len(depth_two_families) >= MINIMUM_DEPTH_TWO_FAMILIES
        ),
        "minimum_total_handoffs": requests >= MINIMUM_TOTAL_HANDOFFS,
        "every_request_occurs_at_or_above_target_depth": all(
            _metric(row, "exogenous_handoff_active_before_v1")
            >= int(row["episode"]["handoff_target_depth"])
            for row in requested
        ),
        "every_request_is_capacity_solvent": all(
            _metric(row, "exogenous_handoff_registered_cost_v1")
            <= _metric(row, "exogenous_handoff_remaining_before_v1")
            for row in requested
        ),
        "every_requested_handoff_passes": bool(requested)
        and all(_passed(row) for row in requested),
        "every_requested_restoration_verifies": all(
            _metric(row, "exogenous_handoff_restoration_attempts_v1") > 0
            and _metric(row, "exogenous_handoff_restoration_attempts_v1")
            == _metric(row, "exogenous_handoff_restoration_passes_v1")
            for row in requested
        ),
        "every_requested_handoff_empties_stack": all(
            _metric(row, "exogenous_handoff_active_after_v1") == 0
            and _active_count(row) == 0
            for row in requested
        ),
        "zero_requested_runtime_halts": all(
            not _runtime_halted(row) for row in requested
        ),
        "recovery_actions_do_not_exceed_registered_bound": all(
            0 < _recovery_actions(row)
            <= _metric(row, "exogenous_handoff_registered_cost_v1")
            for row in requested
        ),
        "all_successes_lower_95_above_0_95": lower_95 > 0.95,
    }
    if set(checks) != set(protocol["validity_gates"]):
        raise ValueError("exogenous-handoff checks changed")
    return {
        "exact_manifest": exact_manifest,
        "all_claims_complete": bool(all_claims_complete),
        "metrics": metrics,
        "by_task_depth": by_task_depth,
        "handoff_requests": requests,
        "handoff_passes": passes,
        "handoff_failures": requests - passes,
        "depth_two_handoff_families": sorted(depth_two_families),
        "all_successes_clopper_pearson_95_lower": lower_95,
        "checks": checks,
        "passed": all(checks.values()),
    }


__all__ = [
    "ARMS",
    "CANDIDATE",
    "COMMON_BUDGETS",
    "DECISION_RULE",
    "DEPTH_ONE",
    "DEPTH_TWO",
    "DRIVERS",
    "GENERATION",
    "OUTCOME_DEFINITIONS",
    "PLANNER_MODEL",
    "PRIMARY_QUESTION",
    "RUNTIME_DEPLOYMENT",
    "SEEDS",
    "SELECTION_DISCLOSURE",
    "STATUS",
    "TASK_BUDGETS",
    "TASK_FAMILIES",
    "VALIDITY_GATES",
    "analyze_rows",
    "arm_order_counts",
    "build_protocol",
    "episode_manifest",
    "expected_episodes",
    "summarize_rows",
    "task_records",
    "validate_protocol",
]
