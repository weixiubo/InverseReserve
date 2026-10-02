from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from inversereserve.studies import inversereserve_exogenous_handoff_v2 as design

ROOT = Path(__file__).resolve().parents[1]


def protocol() -> dict[str, Any]:
    return design.build_protocol(
        scientific_source_commit="a" * 40,
        source_sha256={"source.py": "b" * 64},
        preregistration_path="paper/aaai27/notes/handoff-v2.md",
        preregistration_sha256="c" * 64,
        predecessor={"sealed_predecessors_retained": True},
        repositories={"miniwob": "d" * 40},
        created_utc="2026-07-28T06:00:00Z",
    )


def test_successor_changes_only_explicit_template_date_and_audit() -> None:
    value = protocol()
    assert value["candidate"] == "InverseReserve-exogenous-handoff-v2"
    assert value["planner_model"]["chat_template_date"] == "21 July 2026"
    assert value["expected_episodes"] == 160
    assert value["fresh_seeds"] == list(range(39001, 39021))
    assert value["prestart_supersession"]["claims_opened"] == 0
    assert value["prestart_supersession"]["episodes_opened"] == 0
    assert value["prestart_supersession"]["scientific_outcome_observed"] is False
    assert value["validity_gates"] == design.VALIDITY_GATES
    assert value["decision_rule"] == design.DECISION_RULE


def test_successor_manifest_remains_exact_and_counterbalanced() -> None:
    value = protocol()
    rows = design.episode_manifest(value)
    assert len(rows) == len({row["episode_id"] for row in rows}) == 160
    assert design.arm_order_counts(value) == {arm: {0: 40, 1: 40} for arm in design.ARMS}
    analysis = design.analyze_rows([], value, all_claims_complete=False)
    assert analysis["checks"]["complete_exact_grid"] is False
    assert analysis["passed"] is False


def test_successor_rejects_template_date_or_prestart_rewrite() -> None:
    changed_date = protocol()
    changed_date["planner_model"]["chat_template_date"] = "28 July 2026"
    with pytest.raises(ValueError, match="model contract changed"):
        design.validate_protocol(changed_date)
    changed_audit = protocol()
    changed_audit["prestart_supersession"]["claims_opened"] = 1
    with pytest.raises(ValueError, match="supersession changed"):
        design.validate_protocol(changed_audit)
