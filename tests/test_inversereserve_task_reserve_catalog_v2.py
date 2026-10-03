from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from inversereserve.studies import inversereserve_task_reserve_catalog_v2 as design

ROOT = Path(__file__).resolve().parents[1]


def _protocol() -> dict:
    survey = json.loads(
        (
            Path(__file__).parent / "fixtures" / "inversereserve_miniwob_public_input_coverage_survey_v1.json"
        ).read_text(encoding="utf-8")
    )
    population = design.derive_population(survey)
    return design.build_protocol(
        scientific_source_commit="0" * 40,
        source_sha256={},
        predecessor={},
        repositories={},
        population=population,
        survey_binding=design.COVERAGE_SURVEY,
        created_utc="2026-07-28T00:00:00Z",
    )


def test_protocol_freezes_disjoint_confirmation_and_modern_planner() -> None:
    protocol = _protocol()
    assert protocol["candidate"] == design.CANDIDATE
    assert protocol["maximum_gui_actions"] == 5
    assert protocol["planner_task_reserve"]["units"] == 1
    assert protocol["planner_runtime"] == {
        "model": "Qwen/Qwen3.5-9B",
        "snapshot_manifest_sha256": "cc7e227dba021e290dc47b04192090d45f56baf3d3c190e727141d01b2235e2c",
        "enable_thinking": False,
        "do_sample": False,
        "max_new_tokens": 64,
        "response_contract": "json_decision_and_bid",
        "api_key_required": False,
    }
    assert protocol["method_revision"] == design.METHOD_REVISION
    assert len(protocol["tasks"]) == len(design.CATALOG_TASKS) == 19
    assert protocol["outcome_based_exclusion_allowed"] is False
    assert protocol["partial_reexecution_allowed"] is False
    assert protocol["completed_episode_replay_allowed"] is False


def test_manifest_is_complete_unique_fresh_and_counterbalanced() -> None:
    protocol = _protocol()
    rows = design.episode_manifest(protocol)
    assert len(rows) == design.expected_episodes() == 760
    assert len({row["episode_id"] for row in rows}) == 760
    assert {row["seed"] for row in rows} == set(range(37501, 37521))
    assert {row["task"] for row in rows} == set(design.CATALOG_TASKS)
    assert {row["maximum_gui_actions"] for row in rows} == {5}
    assert {row["planner_task_reserve"] for row in rows} == {1}
    assert {row["budget_level"] for row in rows} == {"binding_b5"}
    assert design.arm_order_counts(protocol) == {
        design.FULL_METHOD: {0: 190, 1: 190},
        design.SAFE_BASELINE: {0: 190, 1: 190},
    }


def test_protocol_tampering_fails_closed() -> None:
    protocol = _protocol()
    changed_revision = deepcopy(protocol)
    changed_revision["method_revision"]["ordinary_duplicate_targets_fail_closed"] = False
    with pytest.raises(ValueError, match="method revision changed"):
        design.validate_protocol(changed_revision)
    changed_planner = deepcopy(protocol)
    changed_planner["planner_runtime"]["model"] = "different-model"
    with pytest.raises(ValueError, match="planner runtime changed"):
        design.validate_protocol(changed_planner)
