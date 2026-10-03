"""Metric declaration tables agree with original code on retained real episode rows."""

from __future__ import annotations

import copy
import importlib
import json
from pathlib import Path

import pytest

from .test_controller_differential import original_package as original_package

MODULES = [
    "inversereserve_cleanup_replan_successor_v1",
    "inversereserve_cross_planner_replication_v1",
    "inversereserve_minimal_cleanup_successor_v1",
    "inversereserve_miniwob_transfer_v1",
    "inversereserve_miniwob_transfer_v2",
    "inversereserve_model_family_replication_v1",
    "inversereserve_single_obligation_successor_v1",
    "inversereserve_strong_control_successor_v1",
    "inversereserve_v19_unified_development_v1",
]


@pytest.mark.parametrize("module", MODULES)
@pytest.mark.parametrize("subset", ["all", "failures", "empty"])
def test_metric_declarations_match_original(original_package, module, subset):
    folder = Path(__file__).resolve().parents[1] / "reproduce/frozen/episodes"
    rows = [json.loads(p.read_text()) for p in sorted(folder.glob("*.json"))]
    assert len(rows) == 360
    if subset == "failures":
        rows = [row for row in rows if not row.get("success")]
        assert rows
    elif subset == "empty":
        rows = []
    old = importlib.import_module("rcrps." + module)
    current = importlib.import_module("inversereserve.studies." + module)
    assert current.summarize_rows(copy.deepcopy(rows)) == old.summarize_rows(copy.deepcopy(rows))


def test_matched_confirmation_v10_analysis_matches_original(original_package):
    from .test_matched_confirmation_v9 import episode_row
    from .test_matched_confirmation_v9 import protocol as prior_protocol

    old = importlib.import_module("rcrps.matched_confirmation_v10")
    current = importlib.import_module("inversereserve.studies.matched_confirmation_v10")
    protocol = prior_protocol()
    protocol.update(
        candidate="PACT-v10-final-matched-confirmation-protocol",
        activation={"v10_trace_equivalence": {}, "repair_holdout": {}},
        arms=list(current.ARMS),
        full_method=current.FULL_METHOD,
        baselines=list(current.BASELINES),
        final_confirmation_seeds=list(current.FINAL_CONFIRMATION_SEEDS),
        statistics=current.EXPECTED_STATISTICS,
        confirmation_gates=current.EXPECTED_GATES,
        information_boundary=current.EXPECTED_INFORMATION_BOUNDARY,
        decision_rule=current.EXPECTED_DECISION_RULE,
    )
    manifest = current.episode_manifest(protocol)
    rows = []
    for episode in manifest:
        previous = {**episode, "method": episode["method"].replace("v10", "v9")}
        row = episode_row(previous)
        row["episode"] = episode
        row["method_input"]["controller_arm"] = episode["method"]
        rows.append(row)
    for complete in (True, False):
        assert current.analyze_final_rows(
            copy.deepcopy(rows), protocol, all_claims_complete=complete
        ) == old.analyze_final_rows(copy.deepcopy(rows), protocol, all_claims_complete=complete)
