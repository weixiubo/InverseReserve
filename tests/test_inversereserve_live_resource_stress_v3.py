from __future__ import annotations

import copy

from rcrps import inversereserve_live_resource_stress_v3 as design
from rcrps.inversereserve_live_resource_stress_v1 import (
    FULL_METHOD,
    LOCAL_ABLATION,
)


def _protocol() -> dict:
    return design.build_protocol(
        scientific_source_commit="0" * 40,
        source_sha256={},
        preregistration_path="paper/aaai27/notes/v3.md",
        preregistration_sha256="0" * 64,
        created_utc="2026-07-19T00:00:00Z",
    )


def _row(*, success: bool = False) -> dict:
    return {
        "success": success,
        "infrastructure_failure": False,
        "active_transactions_at_stop": [],
        "metrics": {
            "runtime_halted": False,
            "restoration_attempts": 0,
            "restoration_passes": 0,
        },
    }


def test_clean_withhold_is_obligation_safe_before_fresh_data() -> None:
    assert design.obligation_safe(_row())

    active = _row()
    active["active_transactions_at_stop"] = [{"bid": "older"}]
    assert not design.obligation_safe(active)

    failed_restore = _row()
    failed_restore["metrics"].update(
        restoration_attempts=1,
        restoration_passes=0,
    )
    assert not design.obligation_safe(failed_restore)

    halted = _row()
    halted["metrics"]["runtime_halted"] = True
    assert not design.obligation_safe(halted)

    infrastructure = _row(success=True)
    infrastructure["infrastructure_failure"] = True
    assert not design.obligation_safe(infrastructure)


def test_success_remains_safe_under_the_v2_endpoint_boundary() -> None:
    successful = _row(success=True)
    successful["active_transactions_at_stop"] = [{"bid": "retained"}]
    assert design.obligation_safe(successful)


def test_v3_manifest_is_fresh_complete_and_counterbalanced() -> None:
    rows = design.episode_manifest(_protocol())
    assert len(rows) == 160
    assert min(row["seed"] for row in rows) == 29201
    assert max(row["seed"] for row in rows) == 29220
    assert len({row["episode_id"] for row in rows}) == 160
    for arm in design.ARMS:
        assert sum(row["method"] == arm for row in rows) == 80
        assert sum(
            row["method"] == arm and row["arm_position"] == 0 for row in rows
        ) == 40


def _analysis_row(episode: dict, *, unsafe_local: bool) -> dict:
    row = {
        "episode": copy.deepcopy(episode),
        "success": False,
        "infrastructure_failure": False,
        "active_transactions_at_stop": [],
        "trace": [],
        "runtime_events": [],
        "metrics": {
            "runtime_halted": False,
            "restoration_attempts": 1,
            "restoration_passes": 1,
            "inverse_reservation_stops": 1,
            "planner_calls": 0,
            "gui_actions": min(2, episode["maximum_gui_actions"]),
        },
    }
    if episode["method"] == FULL_METHOD:
        row["runtime_events"] = [{"type": "live_dynamic_inverse_grounding_v15"}]
    if unsafe_local:
        row["active_transactions_at_stop"] = [{"bid": "stranded"}]
        row["metrics"].update(
            runtime_halted=True,
            restoration_attempts=1,
            restoration_passes=0,
            inverse_reservation_stops=0,
        )
        row["trace"] = [
            {
                "reservation_rule": "proposal_local",
                "allowed": True,
                "remaining_after_action": 0,
                "stack_wide_required_inverse_cost": 1,
            }
        ]
    return row


def test_v3_analysis_uses_the_frozen_obligation_safety_estimand() -> None:
    protocol = _protocol()
    rows = []
    for episode in design.episode_manifest(protocol):
        unsafe_local = (
            episode["method"] == LOCAL_ABLATION
            and episode["maximum_gui_actions"] == 2
        )
        rows.append(_analysis_row(episode, unsafe_local=unsafe_local))
    result = design.analyze_rows(rows, protocol, all_claims_complete=True)
    assert result["passed"] is True
    paired = result["paired_obligation_safety"]
    assert paired["cell_wins"] == 20
    assert paired["cell_losses"] == 0
    assert paired["seed_cluster_wins"] == 20
    assert result["metrics"][FULL_METHOD]["obligation_safe_episodes"] == 80
    assert result["metrics"][LOCAL_ABLATION]["obligation_safe_episodes"] == 60
