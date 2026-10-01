from __future__ import annotations

import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from rcrps import inversereserve_capacity_regime_successor_v3 as design


def protocol() -> dict[str, Any]:
    return design.build_protocol(
        scientific_source_commit="a" * 40,
        source_sha256={"source.py": "b" * 64},
        preregistration_path="paper/aaai27/notes/successor.md",
        preregistration_sha256="c" * 64,
        predecessor={"failed_cross_family": True, "development_only": True},
        repositories={"miniwob": "d" * 40},
        created_utc="2026-07-20T00:00:00Z",
    )


def test_protocol_freezes_fresh_two_regime_population() -> None:
    value = protocol()
    assert value["status"] == "sealed_before_any_successor_seed_reset"
    assert value["fresh_seeds"] == list(range(29701, 29741))
    assert value["sequence_family_size"] == 7
    assert value["outcome_based_exclusion_allowed"] is False
    assert value["partial_reexecution_allowed"] is False
    assert value["episode_replay_allowed"] is False
    assert value["method_revision"]["runtime"] == "PACT-v18"
    assert value["runtime_deployment"] == {
        "model_weights_and_dtype_unchanged": True,
        "visible_cuda_devices": 1,
        "cuda_visible_devices": "0",
        "device_map": "auto",
    }
    assert value["method_revision"]["shared_by_both_active_arms"] is True
    assert (
        value["method_revision"]["reserve_scope_is_the_only_active_arm_difference"]
        is True
    )
    assert design.TASK_REGIME_BUDGETS == {
        "use-autocomplete-nodelay": {"tight": 3, "opportunity": 5},
        "login-user-popup": {"tight": 3, "opportunity": 7},
        "book-flight-nodelay": {"tight": 7, "opportunity": 21},
    }


def test_manifest_is_exact_unique_and_counterbalanced() -> None:
    value = protocol()
    rows = design.episode_manifest(value)
    assert len(rows) == design.expected_episodes() == 720
    assert len({row["episode_id"] for row in rows}) == 720
    assert {row["regime"] for row in rows} == {"tight", "opportunity"}
    assert design.arm_order_counts(value) == {
        arm: {0: 80, 1: 80, 2: 80} for arm in design.ARMS
    }
    for row in rows:
        assert row["maximum_gui_actions"] == design.TASK_REGIME_BUDGETS[
            row["task"]
        ][row["regime"]]


def fake_result(
    episode: dict[str, Any],
    *,
    success: bool = False,
    active: int = 0,
    restored: bool = False,
    unsafe: bool = False,
    reserve_stop: bool = False,
    clearance_restored: bool = False,
    active_clearance: bool = False,
    scope_consumed: bool = False,
) -> dict[str, Any]:
    method = episode["method"]
    active_method = method != design.ABSTAIN_BASELINE
    gui_actions = 0 if not active_method else 2
    typed_transactions = 0 if not active_method else 1
    trace = []
    if active_method:
        trace.append(
            {
                "type": "cross_family_reservation_v3",
                "reservation_rule": (
                    "proposal_local"
                    if method == design.LOCAL_ABLATION
                    else "stack_wide"
                ),
                "allowed": not reserve_stop,
                "remaining_after_action": 0 if unsafe else 4,
                "stack_wide_required_inverse_cost": 2,
            }
        )
    return {
        "episode": episode,
        "success": success,
        "infrastructure_failure": False,
        "active_transactions_at_stop": [{} for _ in range(active)],
        "metrics": {
            "gui_actions": gui_actions,
            "typed_transactions": typed_transactions,
            "planner_calls": int(active_method),
            "planner_actual_calls": int(active_method),
            "restoration_attempts": int(restored),
            "restoration_passes": int(restored),
            "runtime_halted": False,
            "interrupt_clearance_restoration_attempts_v16": int(
                clearance_restored
            ),
            "interrupt_clearance_restoration_passes_v16": int(
                clearance_restored
            ),
            "proposal_clearance_restoration_attempts_v16": int(
                clearance_restored and not active_clearance
            ),
            "proposal_clearance_restoration_passes_v16": int(
                clearance_restored and not active_clearance
            ),
            "active_restore_clearance_restoration_attempts_v16": int(active_clearance),
            "active_restore_clearance_restoration_passes_v16": int(active_clearance),
            "interrupt_clearance_reservation_passes_v16": int(clearance_restored),
            "active_restore_clearance_reservation_passes_v16": int(active_clearance),
            "inverse_action_error_effect_checks_v17": 0,
            "inverse_action_error_effect_passes_v17": 0,
            "inverse_action_error_effect_failures_v17": 0,
            "certified_scope_consumption_checks_v18": int(scope_consumed),
            "certified_scope_consumption_passes_v18": int(scope_consumed),
            "certified_scope_consumption_failures_v18": 0,
            "certified_scope_consumed_transactions_v18": 3 * int(scope_consumed),
            "wall_seconds": 1.0,
        },
        "trace": trace,
    }


def test_solvent_endpoint_requires_activity_and_no_unsafe_admission() -> None:
    manifest = design.episode_manifest(protocol())
    full = next(row for row in manifest if row["method"] == design.FULL_METHOD)
    local = next(row for row in manifest if row["method"] == design.LOCAL_ABLATION)
    abstain = next(
        row for row in manifest if row["method"] == design.ABSTAIN_BASELINE
    )
    assert design.solvent_activity_endpoint(fake_result(full, success=True))
    assert design.solvent_activity_endpoint(fake_result(full, restored=True))
    assert design.solvent_activity_endpoint(
        fake_result(full, clearance_restored=True)
    )
    discharged = fake_result(full, scope_consumed=True)
    assert design.solvent_activity_endpoint(discharged)
    assert (
        design.solvent_activity_endpoint_mode(discharged)
        == "certified_scope_discharge_v18"
    )
    discharged["active_transactions_at_stop"] = [{}]
    assert not design.solvent_activity_endpoint(discharged)
    assert not design.solvent_activity_endpoint(
        fake_result(local, success=True, unsafe=True)
    )
    assert not design.solvent_activity_endpoint(fake_result(abstain))


def test_synthetic_complete_population_passes_every_gate() -> None:
    value = protocol()
    rows = []
    for episode in design.episode_manifest(value):
        method = episode["method"]
        regime = episode["regime"]
        if method == design.FULL_METHOD:
            rows.append(
                fake_result(
                    episode,
                    success=regime == "opportunity",
                    restored=(
                        regime == "tight"
                        and episode["task"] != "book-flight-nodelay"
                    ),
                    reserve_stop=regime == "tight",
                    clearance_restored=(
                        regime == "tight"
                        and episode["task"] != "book-flight-nodelay"
                    ),
                    active_clearance=(
                        regime == "tight"
                        and episode["task"] == "login-user-popup"
                    ),
                    scope_consumed=regime == "tight",
                )
            )
        elif method == design.LOCAL_ABLATION:
            rows.append(
                fake_result(
                    episode,
                    success=regime == "opportunity",
                    active=int(regime == "tight"),
                    unsafe=regime == "tight",
                )
            )
        else:
            rows.append(fake_result(episode))
    analysis = design.analyze_rows(rows, value, all_claims_complete=True)
    assert analysis["exact_manifest"] is True
    assert analysis["paired_tight"]["seed_cluster_wins"] == 40
    assert analysis["opportunity_task_success"]["stack_wide"] == 120
    assert analysis["local_tight_unsafe_and_stranding_families"] == 3
    assert all(analysis["checks"].values())
    assert analysis["passed"] is True


def test_v3_active_arms_share_v18_and_differ_only_in_reserve_scope() -> None:
    full = design.DRIVERS[design.FULL_METHOD]
    local = design.DRIVERS[design.LOCAL_ABLATION]
    assert full.method_id == "stack_wide_reserve_v18"
    assert local.method_id == "proposal_local_reserve_v18"
    assert full.__bases__ == local.__bases__
    assert full.stack_wide is True
    assert local.stack_wide is False


def test_incomplete_population_fails_closed() -> None:
    value = protocol()
    rows = [
        fake_result(episode)
        for episode in design.episode_manifest(value)[:-1]
    ]
    analysis = design.analyze_rows(rows, value, all_claims_complete=False)
    assert analysis["exact_manifest"] is False
    assert analysis["checks"]["complete_exact_grid"] is False
    assert analysis["passed"] is False


def test_budget_gate_fails_closed_when_a_required_metric_is_absent() -> None:
    value = protocol()
    episode = design.episode_manifest(value)[0]
    row = fake_result(episode)
    del row["metrics"]["wall_seconds"]
    assert design._all_rows_respect_budgets((row,), value) is False


def test_protocol_rejects_gate_mutation() -> None:
    value = protocol()
    value["confirmation_gates"]["minimum_stack_opportunity_successes"] = 0
    try:
        design.validate_protocol(value)
    except ValueError as error:
        assert "gates changed" in str(error)
    else:
        raise AssertionError("gate mutation must be rejected")
