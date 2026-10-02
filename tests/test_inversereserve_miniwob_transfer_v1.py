from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from inversereserve.studies import inversereserve_miniwob_transfer_v1 as design

ROOT = Path(__file__).resolve().parents[1]
SURVEY = json.loads(
    (
        Path(__file__).parent / "fixtures" / "inversereserve_miniwob_public_input_coverage_survey_v1.json"
    ).read_text(encoding="utf-8")
)
POPULATION = design.derive_population(SURVEY)


def protocol() -> dict[str, Any]:
    return design.build_protocol(
        scientific_source_commit="a" * 40,
        source_sha256={"source.py": "b" * 64},
        predecessor={"sealed_strong_control": True},
        repositories={"miniwob": "c" * 40},
        population=deepcopy(POPULATION),
        survey_binding=dict(design.COVERAGE_SURVEY),
        created_utc="2026-07-23T08:00:00Z",
    )


def fake_result(
    episode: dict[str, Any],
    *,
    success: bool,
    planner_actual_calls: int = 0,
) -> dict[str, Any]:
    full = episode["method"] == design.FULL_METHOD
    restoration = int(not success)
    trace = []
    if full:
        trace.append(
            {
                "type": "cross_family_reservation_v3",
                "reservation_rule": "stack_wide",
                "decision": "transact",
                "registered_active_inverse_cost": 1,
                "stack_wide_required_inverse_cost": 2,
                "remaining_after_action": 20,
                "allowed": True,
            }
        )
    else:
        trace.append(
            {
                "type": "single_obligation_policy_v19",
                "decision": "transact",
                "allowed": False,
                "delegated_to_stack_wide_reserve": False,
            }
        )
    return {
        "episode": episode,
        "success": success,
        "infrastructure_failure": False,
        "active_transactions_at_stop": [],
        "metrics": {
            "gui_actions": 4,
            "typed_transactions": 1,
            "planner_calls": 1,
            "planner_actual_calls": planner_actual_calls,
            "wall_seconds": 1.0,
            "runtime_halted": False,
            "restoration_attempts": restoration,
            "restoration_passes": restoration,
            "interrupt_clearance_restoration_attempts_v16": 0,
            "interrupt_clearance_restoration_passes_v16": 0,
            "proposal_clearance_restoration_attempts_v16": 0,
            "proposal_clearance_restoration_passes_v16": 0,
            "active_restore_clearance_restoration_attempts_v16": 0,
            "active_restore_clearance_restoration_passes_v16": 0,
            "goal_mutation_consumption_passes_v19": int(success),
            "certified_scope_consumption_failures_v19": 0,
            "top_cleanup_attempts": 0,
            "top_cleanup_passes": 0,
            "top_cleanup_failures": 0,
        },
        "trace": trace,
    }


def synthetic_valid_rows(value: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for episode in design.episode_manifest(value):
        success = episode["method"] == design.FULL_METHOD or episode["task"] not in {
            "click-tab-2",
            "navigate-tree",
        }
        rows.append(
            fake_result(
                episode,
                success=success,
                planner_actual_calls=int(episode["episode_index"] == 0),
            )
        )
    return rows


def test_outcome_free_population_is_exact_and_template_conservative() -> None:
    assert POPULATION["eligible_exact_tasks"] == list(design.ELIGIBLE_TASKS)
    assert POPULATION["new_template_exact_tasks"] == list(design.NEW_TEMPLATE_EXACT_TASKS)
    assert POPULATION["primary_tasks"] == list(design.PRIMARY_TASKS)
    assert POPULATION["new_template_groups"] == [
        "click-collapsible",
        "click-menu",
        "click-tab",
        "enter-password",
        "navigate-tree",
    ]
    assert design.normalize_task_template("click-collapsible-2-nodelay") == ("click-collapsible")
    assert not set(design.PRIOR_EXACT_TASKS) & set(design.ELIGIBLE_TASKS)


def test_population_rejects_any_outcome_field() -> None:
    changed = deepcopy(SURVEY)
    changed["rows"][0]["success"] = False
    with pytest.raises(ValueError, match="forbidden outcome field"):
        design.derive_population(changed)


def test_protocol_and_manifest_freeze_fresh_balanced_grid() -> None:
    value = protocol()
    assert value["status"] == design.STATUS
    assert value["fresh_seeds"] == list(range(37101, 37121))
    assert value["maximum_gui_actions"] == 32
    assert value["expected_episodes"] == 560
    assert value["primary_analysis"]["efficacy_gate"].startswith("none_")
    assert value["outcome_based_exclusion_allowed"] is False
    rows = design.episode_manifest(value)
    assert len(rows) == len({row["episode_id"] for row in rows}) == 560
    assert design.arm_order_counts(value) == {arm: {0: 140, 1: 140} for arm in design.ARMS}


def test_synthetic_complete_grid_passes_without_an_efficacy_gate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(design, "BOOTSTRAP_SAMPLES", 100)
    value = protocol()
    analysis = design.analyze_rows(
        synthetic_valid_rows(value),
        value,
        all_claims_complete=True,
    )
    assert analysis["metrics"][design.FULL_METHOD]["closed_successes"] == 280
    assert analysis["metrics"][design.SAFE_BASELINE]["closed_successes"] == 240
    assert analysis["paired_stack_vs_safe_closed_success"]["tasks"] == list(design.PRIMARY_TASKS)
    assert all(analysis["checks"].values())
    assert analysis["passed"] is True


def test_open_success_and_incomplete_grid_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(design, "BOOTSTRAP_SAMPLES", 20)
    value = protocol()
    rows = synthetic_valid_rows(value)
    successful = next(row for row in rows if row["success"])
    successful["active_transactions_at_stop"] = [{}]
    analysis = design.analyze_rows(rows, value, all_claims_complete=True)
    assert analysis["checks"]["all_successes_are_closed"] is False
    assert analysis["passed"] is False

    incomplete = design.analyze_rows(
        rows[:-1],
        value,
        all_claims_complete=False,
    )
    assert incomplete["exact_manifest"] is False
    assert incomplete["comparisons"] is None
    assert incomplete["checks"]["complete_exact_grid"] is False
    assert incomplete["passed"] is False


def test_protocol_rejects_population_and_seed_tampering() -> None:
    value = deepcopy(protocol())
    value["population"]["primary_tasks"][0] = "book-flight"
    with pytest.raises(ValueError, match="population changed"):
        design.validate_protocol(value)

    value = deepcopy(protocol())
    value["fresh_seeds"][0] = 36101
    with pytest.raises(ValueError, match="seeds changed"):
        design.validate_protocol(value)
