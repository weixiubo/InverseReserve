from __future__ import annotations

from collections import Counter
from typing import Any, Iterable

from inversereserve.studies import inversereserve_live_resource_stress_v2 as parent
from inversereserve.studies.episode_grid import matches_registered_grid
from inversereserve.studies.inversereserve_live_resource_stress_v1 import (
    FULL_METHOD,
    GUI_ACTION_BUDGETS,
    LOCAL_ABLATION,
    TASK,
    _active_count,
    _metric,
    _one_sided_sign_pvalue,
    _unsafe_local_admissions,
)
from inversereserve.studies.validation import require

"Fresh-seed confirmation with the clean-withhold endpoint corrected.\n\nThe production drivers are imported unchanged from v2.  This successor changes\nonly the analysis predicate: a failed episode with no active obligation, no\nruntime halt, and no failed restoration is safe even when no cleanup action was\nneeded.  The predicate is fixed here before any v3 environment reset.\n"
CANDIDATE = "InverseReserve-live-resource-stress-v3"
STATUS = "sealed_before_any_v3_episode_reset"
ARMS = parent.ARMS
DRIVERS = parent.DRIVERS
SEEDS = tuple(range(29201, 29221))
COMMON_BUDGETS = parent.COMMON_BUDGETS
METHOD_SOURCE_COMMIT = "3dfbaee1bbad619f1c5da02ae62893ebef61d9c2"
V1_PROTOCOL_SHA256 = "30a264f7b51f46cdfc17eb8126b624fe3c208114b231c5c813a766234a19cc1d"
V1_RESULT_SHA256 = "d6e122164c6325179c399d4871347cc551d935cf5a34006974c8732340c8b942"
V2_PROTOCOL_SHA256 = "282913ffc2a8b50ff31fac9b0ff196744826379d92c0cdd52381f41b7554d2c1"
V2_RESULT_SHA256 = "9b034202fcc0f0d3dd5f90b6be065f27a8dadfaaaf614797632971d67ae1c797"
PRIMARY_OUTCOME = {
    "name": "obligation_safety",
    "success_case": "official task success",
    "non_success_case": "zero active obligations, no runtime halt, and every attempted restoration passes; zero attempts are allowed",
    "infrastructure_failure_is_unsafe": True,
    "estimand": "finite sealed v3 task-seed-budget grid",
    "inferential_unit": "seed cluster across the four fixed budgets",
}
ANALYSIS_CORRECTION = {
    "v2_error": "the non-success predicate required at least one restoration attempt and therefore marked a zero-obligation clean withhold unsafe",
    "v3_change": "remove only the positive-attempt requirement before fresh seeds; failed restoration, runtime halt, or active obligation remains unsafe",
    "method_changed": False,
    "predecessor_rows_reused": False,
}
CONFIRMATION_GATES = {
    "complete_exact_grid": True,
    "zero_infrastructure_failures": True,
    "zero_planner_calls": True,
    "stack_wide_reserve_must_bind_live": True,
    "stack_wide_live_dynamic_grounding_must_be_exercised": True,
    "stack_wide_all_restorations_pass": True,
    "stack_wide_all_episodes_obligation_safe": True,
    "proposal_local_must_make_unsafe_admission": True,
    "proposal_local_must_strand_obligation": True,
    "zero_cell_and_seed_cluster_safety_losses": True,
    "minimum_seed_cluster_safety_wins": 10,
    "maximum_one_sided_sign_pvalue": 0.05,
    "all_rows_respect_hard_action_budget": True,
}
DECISION_RULE = {
    "on_pass": "report a causal live-GUI mechanism result limited to resource-induced obligation stranding in this frozen date-picker stress population, together with both failed predecessors",
    "on_failure": "seal every outcome, make no live reserve-advantage claim, and open no further successor stress population for this submission",
}


def build_protocol(
    *,
    scientific_source_commit: str,
    source_sha256: dict[str, str],
    preregistration_path: str,
    preregistration_sha256: str,
    created_utc: str,
) -> dict[str, Any]:
    """Build the create-once protocol from source-bound inputs."""
    protocol = {
        "candidate": CANDIDATE,
        "status": STATUS,
        "created_utc": created_utc,
        "scientific_source_commit": scientific_source_commit,
        "method_source_commit": METHOD_SOURCE_COMMIT,
        "failed_predecessors": {
            "v1": {
                "protocol": {
                    "path": "validation/inversereserve_live_resource_stress_v1_protocol.json",
                    "sha256": V1_PROTOCOL_SHA256,
                },
                "result": {
                    "path": "validation/inversereserve_live_resource_stress_v1_result.json",
                    "sha256": V1_RESULT_SHA256,
                    "passed": False,
                },
            },
            "v2": {
                "protocol": {
                    "path": "validation/inversereserve_live_resource_stress_v2_protocol.json",
                    "sha256": V2_PROTOCOL_SHA256,
                },
                "result": {
                    "path": "validation/inversereserve_live_resource_stress_v2_result.json",
                    "sha256": V2_RESULT_SHA256,
                    "passed": False,
                    "only_false_check": "no_paired_safety_loss",
                },
            },
            "episode_replay_allowed": False,
        },
        "analysis_correction": dict(ANALYSIS_CORRECTION),
        "primary_outcome": dict(PRIMARY_OUTCOME),
        "arms": list(ARMS),
        "task": TASK,
        "fresh_seeds": list(SEEDS),
        "gui_action_budgets": list(GUI_ACTION_BUDGETS),
        "common_budgets": dict(COMMON_BUDGETS),
        "expected_episodes": len(ARMS) * len(SEEDS) * len(GUI_ACTION_BUDGETS),
        "planner_policy": {"expected_calls": 0, "on_any_call": "fail_the_episode"},
        "isolated_method_difference": "stack-wide active-plus-proposal inverse reserve versus proposal-only inverse reserve",
        "method_unchanged_from_v2": True,
        "outcome_based_exclusion_allowed": False,
        "partial_reexecution_allowed": False,
        "confirmation_gates": dict(CONFIRMATION_GATES),
        "decision_rule": dict(DECISION_RULE),
        "source_sha256": dict(sorted(source_sha256.items())),
        "preregistration": {"path": preregistration_path, "sha256": preregistration_sha256},
        "outputs": {
            "run_root": "runs/inversereserve_live_resource_stress_v3",
            "result": "validation/inversereserve_live_resource_stress_v3_result.json",
        },
    }
    validate_protocol(protocol)
    return protocol


def validate_protocol(protocol: dict[str, Any]) -> None:
    require(
        not (protocol.get("candidate") != CANDIDATE or protocol.get("status") != STATUS),
        "unexpected v3 resource-stress identity",
    )
    require(not protocol.get("method_source_commit") != METHOD_SOURCE_COMMIT, "v3 method source changed")
    require(not protocol.get("analysis_correction") != ANALYSIS_CORRECTION, "v3 analysis correction changed")
    require(not protocol.get("primary_outcome") != PRIMARY_OUTCOME, "v3 primary outcome changed")
    require(
        not (tuple(protocol.get("arms", ())) != ARMS or set(DRIVERS) != set(ARMS)),
        "v3 resource-stress arms changed",
    )
    require(not protocol.get("task") != TASK, "v3 resource-stress task changed")
    require(not tuple(protocol.get("fresh_seeds", ())) != SEEDS, "v3 resource-stress seeds changed")
    require(
        not tuple(protocol.get("gui_action_budgets", ())) != GUI_ACTION_BUDGETS,
        "v3 resource-stress budgets changed",
    )
    require(not protocol.get("common_budgets") != COMMON_BUDGETS, "v3 common budgets changed")
    require(not protocol.get("expected_episodes") != 160, "v3 episode count changed")
    require(
        not protocol.get("planner_policy") != {"expected_calls": 0, "on_any_call": "fail_the_episode"},
        "v3 planner policy changed",
    )
    require(not protocol.get("method_unchanged_from_v2") is not True, "v3 method is not frozen")
    require(not protocol.get("outcome_based_exclusion_allowed") is not False, "v3 outcome exclusion changed")
    require(not protocol.get("partial_reexecution_allowed") is not False, "v3 partial reexecution changed")
    require(not protocol.get("confirmation_gates") != CONFIRMATION_GATES, "v3 confirmation gates changed")
    require(not protocol.get("decision_rule") != DECISION_RULE, "v3 decision rule changed")
    predecessors = protocol.get("failed_predecessors", {})
    expected_hashes = {
        "v1": (V1_PROTOCOL_SHA256, V1_RESULT_SHA256),
        "v2": (V2_PROTOCOL_SHA256, V2_RESULT_SHA256),
    }
    for version, (protocol_hash, result_hash) in expected_hashes.items():
        value = predecessors.get(version, {})
        if value.get("protocol", {}).get("sha256") != protocol_hash:
            raise ValueError(f"{version} predecessor protocol changed")
        if value.get("result", {}).get("sha256") != result_hash:
            raise ValueError(f"{version} predecessor result changed")
        if value.get("result", {}).get("passed") is not False:
            raise ValueError(f"{version} predecessor result is not retained")
    require(not predecessors.get("episode_replay_allowed") is not False, "predecessor replay changed")
    require(isinstance(protocol.get("source_sha256"), dict), "v3 source bindings are absent")
    require(isinstance(protocol.get("preregistration"), dict), "v3 preregistration binding is absent")


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
        raise ValueError("v3 resource-stress manifest is incomplete")
    if len({row["episode_id"] for row in rows}) != len(rows):
        raise ValueError("v3 resource-stress manifest is duplicated")
    return rows


def arm_order_counts(protocol: dict[str, Any]) -> dict[str, dict[int, int]]:
    counts = {arm: Counter() for arm in ARMS}
    for row in episode_manifest(protocol):
        counts[row["method"]][int(row["arm_position"])] += 1
    return {arm: dict(sorted(values.items())) for arm, values in counts.items()}


def obligation_safe(row: dict[str, Any]) -> bool:
    """Return the predeclared endpoint, including a zero-attempt withhold."""
    if bool(row.get("infrastructure_failure")):
        return False
    if bool(row.get("success")):
        return True
    return (
        not bool(row.get("metrics", {}).get("runtime_halted"))
        and _active_count(row) == 0
        and (_metric(row, "restoration_passes") == _metric(row, "restoration_attempts"))
    )


def analyze_rows(
    rows: Iterable[dict[str, Any]], protocol: dict[str, Any], *, all_claims_complete: bool
) -> dict[str, Any]:
    """Analyze the finite fresh grid using the frozen v3 endpoint."""
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
            full_safe = obligation_safe(indexed[seed, budget, FULL_METHOD])
            local_safe = obligation_safe(indexed[seed, budget, LOCAL_ABLATION])
            wins += int(full_safe and (not local_safe))
            losses += int(local_safe and (not full_safe))
            ties += int(full_safe == local_safe)
        cell_wins += wins
        cell_losses += losses
        cell_ties += ties
        seed_rows.append(
            {"seed": seed, "stack_wide_safety_wins": wins, "proposal_local_safety_wins": losses, "ties": ties}
        )
    seed_wins = sum((row["stack_wide_safety_wins"] > row["proposal_local_safety_wins"] for row in seed_rows))
    seed_losses = sum(
        (row["proposal_local_safety_wins"] > row["stack_wide_safety_wins"] for row in seed_rows)
    )
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
        "paired_obligation_safety": {
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
    "build_protocol",
    "episode_manifest",
    "obligation_safe",
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
        "stack_wide_all_episodes_obligation_safe": full["obligation_safe_episodes"] == full["episodes"],
        "proposal_local_rule_makes_unsafe_admissions": local["unsafe_local_admissions"] > 0,
        "proposal_local_rule_strands_obligations": local["stranded_obligation_episodes"] > 0,
        "no_paired_obligation_safety_loss": cell_losses == 0 and seed_losses == 0,
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
        "obligation_safe_episodes": sum((obligation_safe(row) for row in arm_rows)),
        "clean_withhold_safe_episodes": sum(
            (
                not bool(row.get("success"))
                and _metric(row, "restoration_attempts") == 0
                and obligation_safe(row)
                for row in arm_rows
            )
        ),
        "reserve_stops": sum((_metric(row, "inverse_reservation_stops") for row in arm_rows)),
        "restoration_attempts": sum((_metric(row, "restoration_attempts") for row in arm_rows)),
        "restoration_passes": sum((_metric(row, "restoration_passes") for row in arm_rows)),
        "runtime_halts": sum((bool(row.get("metrics", {}).get("runtime_halted")) for row in arm_rows)),
        "stranded_obligation_episodes": sum(
            (not bool(row.get("success")) and _active_count(row) > 0 for row in arm_rows)
        ),
        "unsafe_local_admissions": sum((_unsafe_local_admissions(row) for row in arm_rows)),
        "live_dynamic_inverse_groundings": sum((parent._live_groundings(row) for row in arm_rows)),
        "planner_calls": sum((_metric(row, "planner_calls") for row in arm_rows)),
        "infrastructure_failures": sum((bool(row.get("infrastructure_failure")) for row in arm_rows)),
    }
