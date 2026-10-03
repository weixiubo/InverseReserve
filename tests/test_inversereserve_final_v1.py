from __future__ import annotations

import copy
from pathlib import Path

from inversereserve.studies import inversereserve_final_v1 as final

ROOT = Path(__file__).resolve().parents[1]


def protocol() -> dict:
    return {
        "candidate": "InverseReserve-final-v1-protocol",
        "status": "sealed_after_c458_diagnosis_before_any_final_reset",
        "created_utc": "2026-07-17T00:00:00Z",
        "scientific_source_commit": "0" * 40,
        "development_context": {
            "c458_status": "sealed_failed_development_gate",
            "c458_result_sha256": final.C458_RESULT_SHA256,
            "c458_successes": 120,
            "c458_episodes": 120,
            "selected_final_driver": final.FULL_METHOD,
            "v14_population_navigation_in_final_method": False,
            "c458_used_as_final_evidence": False,
        },
        "arms": list(final.ARMS),
        "full_method": final.FULL_METHOD,
        "baselines": list(final.BASELINES),
        "tasks": [{"task_id": task_id, "family_group": family} for task_id, family in final.TASKS],
        "final_seeds": list(final.FINAL_SEEDS),
        "expected_task_seed_cells": len(final.TASKS) * len(final.FINAL_SEEDS),
        "expected_episodes": len(final.TASKS) * len(final.FINAL_SEEDS) * len(final.ARMS),
        "budgets": dict(final.EXPECTED_BUDGETS),
        "generation": dict(final.EXPECTED_GENERATION),
        "statistics": dict(final.EXPECTED_STATISTICS),
        "confirmation_gates": dict(final.EXPECTED_GATES),
        "information_boundary": dict(final.EXPECTED_INFORMATION_BOUNDARY),
        "decision_rule": dict(final.EXPECTED_DECISION_RULE),
        "model_checkpoint": "Qwen3.5-9B",
        "source_sha256": {},
        "preregistration": {},
        "outputs": {
            "run_directory": "runs/inversereserve_final_v1",
            "result": "validation/inversereserve_final_result_v1.json",
        },
    }


def test_manifest_is_complete_unique_and_counterbalanced() -> None:
    payload = protocol()
    final.validate_protocol_shape(payload)
    rows = final.episode_manifest(payload)
    assert len(rows) == 360
    assert len({row["episode_id"] for row in rows}) == 360
    assert final.arm_order_counts(payload) == {arm: {0: 40, 1: 40, 2: 40} for arm in final.ARMS}


def test_protocol_rejects_old_seeds_and_the_v14_arm() -> None:
    payload = protocol()
    payload["final_seeds"][0] = 27601
    try:
        final.validate_protocol_shape(payload)
    except ValueError as error:
        assert "seed population" in str(error)
    else:
        raise AssertionError("an already opened seed was accepted")
    payload = protocol()
    payload["arms"][2] = "full_pact_v14"
    try:
        final.validate_protocol_shape(payload)
    except ValueError as error:
        assert "arm order" in str(error)
    else:
        raise AssertionError("the unvalidated v14 arm was accepted")


def ledger_row() -> dict:
    return {
        "success": True,
        "active_transactions_at_stop": [
            {"bid": "submit", "transaction_kind": "editable_assignment", "operation": "set value"}
        ],
        "completed_transactions_at_stop": [],
        "trace": [
            {
                "type": "inverse_budget_reservation",
                "allowed": True,
                "active_inverse_cost": 1,
                "remaining_after_action": 2,
            }
        ],
        "metrics": {"typed_transactions": 1, "inverse_reservation_audits": 1},
    }


def test_terminal_ledger_accepts_a_solvent_active_terminal_transaction() -> None:
    audit = final.terminal_ledger_audit([ledger_row()])
    assert audit["exact_accounting"] is True
    assert audit["all_reservations_solvent"] is True
    assert audit["active_transactions_at_terminal_stop"] == 1
    assert audit["successful_episodes_with_active_ledger"] == 1


def test_terminal_ledger_rejects_count_mismatch_and_insolvency() -> None:
    mismatch = ledger_row()
    mismatch["metrics"]["typed_transactions"] = 2
    assert final.terminal_ledger_audit([mismatch])["exact_accounting"] is False
    insolvent = copy.deepcopy(ledger_row())
    insolvent["trace"][0]["active_inverse_cost"] = 3
    assert final.terminal_ledger_audit([insolvent])["all_reservations_solvent"] is False


def test_terminal_ledger_allows_a_safe_zero_action_failure() -> None:
    row = {
        "success": False,
        "active_transactions_at_stop": [],
        "completed_transactions_at_stop": [],
        "trace": [],
        "metrics": {"typed_transactions": 0, "inverse_reservation_audits": 0},
    }
    audit = final.terminal_ledger_audit([row])
    assert audit["exact_accounting"] is True
    assert audit["all_reservations_solvent"] is True


def test_complete_commit_audit_recomputes_metrics() -> None:
    row = {
        "runtime_events": [{"type": "complete_public_commit_observation_check_v13", "passed": True}],
        "metrics": {
            "complete_public_commit_checks_v13": 1,
            "complete_public_commit_passes_v13": 1,
            "complete_public_commit_rejections_v13": 0,
        },
    }
    assert final.complete_commit_audit([row]) == {
        "checks": 1,
        "passes": 1,
        "rejections": 0,
        "exact_accounting": True,
        "all_pass": True,
    }
    row["metrics"]["complete_public_commit_passes_v13"] = 0
    assert final.complete_commit_audit([row])["exact_accounting"] is False
