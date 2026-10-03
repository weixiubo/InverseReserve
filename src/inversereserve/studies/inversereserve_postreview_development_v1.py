"""Development-only post-review budget-frontier diagnostic.

This population deliberately reuses seeds from the failed cross-family stress.
It cannot support a paper claim.  Its sole purpose is to decide whether a fresh
confirmation is scientifically justified: does stack-wide reservation recover
task utility after a small, fully reported increase in GUI-action capacity?
"""

from __future__ import annotations

from collections import Counter
from typing import Any, Iterable

from inversereserve.studies import inversereserve_cross_family_stress_v1 as parent
from inversereserve.studies.episode_grid import matches_registered_grid
from inversereserve.studies.inversereserve_live_resource_stress_v1 import (
    _active_count,
    _metric,
    _unsafe_local_admissions,
)
from inversereserve.studies.validation import require

CANDIDATE = "InverseReserve-postreview-budget-frontier-development-v1"
STATUS = "development_only_reuses_failed_cross_family_seeds"
FULL_METHOD = parent.FULL_METHOD
LOCAL_ABLATION = parent.LOCAL_ABLATION
ARMS = (FULL_METHOD, LOCAL_ABLATION)
DRIVERS = {arm: parent.DRIVERS[arm] for arm in ARMS}
SEEDS = tuple(range(29301, 29306))
TASK_BUDGETS = {
    "use-autocomplete-nodelay": (4, 5, 6),
    "login-user-popup": (5, 6, 7),
    "book-flight-nodelay": (11, 13, 15),
}
TASK_FAMILIES = {
    "use-autocomplete-nodelay": "autocomplete",
    "login-user-popup": "login_interrupt",
    "book-flight-nodelay": "flight_composite",
}
COMMON_BUDGETS = {"maximum_planner_calls": 3, "maximum_wall_seconds": 60.0}
GENERATION = {"enable_thinking": False, "do_sample": False, "max_new_tokens": 64}
PURPOSE = {
    "claim_status": "development_only_no_submission_claim",
    "reason_for_reusing_seeds": "the failed cross-family population is used only to map the additional capacity needed for safe task utility before any fresh confirmation",
    "question": "whether stack-wide reservation reaches proposal-local task success within a small additional GUI-action budget while reducing stranding",
    "forbidden_use": "no row, estimate, or selected budget from this diagnostic may be reported as confirmatory evidence",
}


def task_records() -> list[dict[str, Any]]:
    return [
        {"task_id": task, "family_group": TASK_FAMILIES[task], "gui_action_budgets": list(budgets)}
        for task, budgets in TASK_BUDGETS.items()
    ]


def expected_episodes() -> int:
    return len(ARMS) * len(SEEDS) * sum((len(budgets) for budgets in TASK_BUDGETS.values()))


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
        "predecessor": predecessor,
        "purpose": dict(PURPOSE),
        "arms": list(ARMS),
        "isolated_method_difference": "stack-wide active-plus-proposal inverse reserve versus proposal-only inverse reserve",
        "tasks": task_records(),
        "reused_development_seeds": list(SEEDS),
        "common_budgets": dict(COMMON_BUDGETS),
        "generation": dict(GENERATION),
        "expected_episodes": expected_episodes(),
        "outcome_based_exclusion_allowed": False,
        "partial_episode_replay_allowed": False,
        "repositories": dict(repositories),
        "source_sha256": dict(sorted(source_sha256.items())),
    }
    validate_protocol(protocol)
    return protocol


def validate_protocol(protocol: dict[str, Any]) -> None:
    require(
        not (protocol.get("candidate") != CANDIDATE or protocol.get("status") != STATUS),
        "unexpected post-review development identity",
    )
    require(not protocol.get("purpose") != PURPOSE, "post-review development purpose changed")
    require(
        not (tuple(protocol.get("arms", ())) != ARMS or set(DRIVERS) != set(ARMS)),
        "post-review development arms changed",
    )
    require(not protocol.get("tasks") != task_records(), "post-review development task-budget grid changed")
    require(
        not tuple(protocol.get("reused_development_seeds", ())) != SEEDS,
        "post-review development seeds changed",
    )
    require(not protocol.get("common_budgets") != COMMON_BUDGETS, "post-review development budgets changed")
    require(not protocol.get("generation") != GENERATION, "post-review development generation changed")
    require(
        not protocol.get("expected_episodes") != expected_episodes(),
        "post-review development episode count changed",
    )
    require(
        not protocol.get("outcome_based_exclusion_allowed") is not False,
        "post-review development exclusion rule changed",
    )
    require(
        not protocol.get("partial_episode_replay_allowed") is not False,
        "post-review development replay rule changed",
    )
    require(isinstance(protocol.get("predecessor"), dict), "failed cross-family predecessor is absent")
    require(isinstance(protocol.get("repositories"), dict), "repository pins are absent")
    require(isinstance(protocol.get("source_sha256"), dict), "source bindings are absent")


def episode_manifest(protocol: dict[str, Any]) -> list[dict[str, Any]]:
    validate_protocol(protocol)
    rows: list[dict[str, Any]] = []
    for seed_index, seed in enumerate(SEEDS):
        for task_index, (task, budgets) in enumerate(TASK_BUDGETS.items()):
            for budget_index, budget in enumerate(budgets):
                rotation = (seed_index + task_index + budget_index) % len(ARMS)
                order = ARMS[rotation:] + ARMS[:rotation]
                for arm_position, method in enumerate(order):
                    rows.append(
                        {
                            "episode_index": len(rows),
                            "seed_index": seed_index,
                            "task_index": task_index,
                            "budget_index": budget_index,
                            "arm_position": arm_position,
                            "task": task,
                            "family_group": TASK_FAMILIES[task],
                            "seed": seed,
                            "maximum_gui_actions": budget,
                            "method": method,
                            "episode_id": f"{task}__seed{seed}__budget{budget}__{method}",
                        }
                    )
    if len(rows) != expected_episodes():
        raise ValueError("post-review development manifest is incomplete")
    if len({row["episode_id"] for row in rows}) != len(rows):
        raise ValueError("post-review development manifest is duplicated")
    return rows


def arm_order_counts(protocol: dict[str, Any]) -> dict[str, dict[int, int]]:
    counts = {arm: Counter() for arm in ARMS}
    for row in episode_manifest(protocol):
        counts[row["method"]][int(row["arm_position"])] += 1
    return {arm: dict(sorted(values.items())) for arm, values in counts.items()}


def _reserve_stops(row: dict[str, Any]) -> int:
    return sum(
        (
            event.get("type") == "cross_family_reservation_v1" and event.get("allowed") is False
            for event in row.get("trace", ())
        )
    )


def _stranded(row: dict[str, Any]) -> bool:
    return not bool(row.get("success")) and _active_count(row) > 0


def summarize_rows(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    rows = tuple(rows)
    return _summarize_rows_summary_record(rows=rows)


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
    return {
        "claim_status": PURPOSE["claim_status"],
        "exact_manifest": exact_manifest,
        "all_claims_complete": bool(all_claims_complete),
        "arm_order_counts": arm_order_counts(protocol),
        "metrics": metrics,
        "by_task_budget": by_task_budget,
        "complete": exact_manifest and bool(all_claims_complete),
    }


__all__ = [
    "ARMS",
    "CANDIDATE",
    "COMMON_BUDGETS",
    "DRIVERS",
    "FULL_METHOD",
    "GENERATION",
    "LOCAL_ABLATION",
    "PURPOSE",
    "SEEDS",
    "STATUS",
    "TASK_BUDGETS",
    "analyze_rows",
    "arm_order_counts",
    "build_protocol",
    "episode_manifest",
    "expected_episodes",
    "summarize_rows",
    "task_records",
    "validate_protocol",
]


def _summarize_rows_summary_record(*, rows: Any) -> dict[str, Any]:
    """Compute summary record from explicit study inputs."""
    return {
        "episodes": len(rows),
        "task_successes": sum((bool(row.get("success")) for row in rows)),
        "successes_with_active_obligations": sum(
            (bool(row.get("success")) and _active_count(row) > 0 for row in rows)
        ),
        "gui_actions": sum((_metric(row, "gui_actions") for row in rows)),
        "typed_transactions": sum((_metric(row, "typed_transactions") for row in rows)),
        "planner_calls": sum((_metric(row, "planner_calls") for row in rows)),
        "planner_actual_calls": sum((_metric(row, "planner_actual_calls") for row in rows)),
        "reserve_stops": sum((_reserve_stops(row) for row in rows)),
        "restoration_attempts": sum((_metric(row, "restoration_attempts") for row in rows)),
        "restoration_passes": sum((_metric(row, "restoration_passes") for row in rows)),
        "runtime_halts": sum((bool(row.get("metrics", {}).get("runtime_halted")) for row in rows)),
        "stranded_obligation_episodes": sum((_stranded(row) for row in rows)),
        "unsafe_local_admissions": sum((_unsafe_local_admissions(row) for row in rows)),
        "infrastructure_failures": sum((bool(row.get("infrastructure_failure")) for row in rows)),
    }


def _aggregate_by_task_budget(rows: tuple[dict[str, Any], ...]) -> list[dict[str, Any]]:
    by_task_budget = []
    for task, budgets in TASK_BUDGETS.items():
        for budget in budgets:
            by_task_budget.append(
                {
                    "task": task,
                    "family_group": TASK_FAMILIES[task],
                    "maximum_gui_actions": budget,
                    "arms": {
                        arm: summarize_rows(
                            (
                                row
                                for row in rows
                                if row.get("episode", {}).get("task") == task
                                and row.get("episode", {}).get("maximum_gui_actions") == budget
                                and (row.get("episode", {}).get("method") == arm)
                            )
                        )
                        for arm in ARMS
                    },
                }
            )
    return by_task_budget
