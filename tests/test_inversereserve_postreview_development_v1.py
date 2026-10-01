from __future__ import annotations

from typing import Any

from rcrps import inversereserve_postreview_development_v1 as design


def protocol() -> dict[str, Any]:
    return design.build_protocol(
        scientific_source_commit="a" * 40,
        source_sha256={"source.py": "b" * 64},
        predecessor={"failed": True},
        repositories={"miniwob": "c" * 40},
        created_utc="2026-07-20T00:00:00Z",
    )


def test_development_population_is_explicitly_nonconfirmatory() -> None:
    value = protocol()
    assert value["status"] == "development_only_reuses_failed_cross_family_seeds"
    assert value["purpose"]["claim_status"] == "development_only_no_submission_claim"
    assert value["purpose"]["forbidden_use"].startswith("no row")
    assert value["reused_development_seeds"] == list(range(29301, 29306))
    assert value["outcome_based_exclusion_allowed"] is False
    assert value["partial_episode_replay_allowed"] is False


def test_manifest_is_complete_unique_and_counterbalanced() -> None:
    value = protocol()
    rows = design.episode_manifest(value)
    assert len(rows) == design.expected_episodes() == 90
    assert len({row["episode_id"] for row in rows}) == len(rows)
    assert set(row["method"] for row in rows) == set(design.ARMS)
    assert design.arm_order_counts(value) == {
        design.FULL_METHOD: {0: 23, 1: 22},
        design.LOCAL_ABLATION: {0: 22, 1: 23},
    }
    for row in rows:
        assert row["maximum_gui_actions"] in design.TASK_BUDGETS[row["task"]]


def fake_result(
    episode: dict[str, Any],
    *,
    success: bool = False,
    active: int = 0,
    halt: bool = False,
    reserve_stop: bool = False,
    unsafe_local: bool = False,
) -> dict[str, Any]:
    reservation_rule = (
        "proposal_local"
        if episode["method"] == design.LOCAL_ABLATION
        else "stack_wide"
    )
    return {
        "episode": episode,
        "success": success,
        "infrastructure_failure": False,
        "active_transactions_at_stop": [{} for _ in range(active)],
        "metrics": {
            "gui_actions": 3,
            "typed_transactions": 1,
            "planner_calls": 1,
            "planner_actual_calls": 0,
            "restoration_attempts": int(not success),
            "restoration_passes": int(not success and not halt),
            "runtime_halted": halt,
        },
        "trace": [
            {
                "type": "cross_family_reservation_v1",
                "reservation_rule": reservation_rule,
                "allowed": not reserve_stop,
                "remaining_after_action": 0 if unsafe_local else 3,
                "stack_wide_required_inverse_cost": 2,
            }
        ],
    }


def test_analysis_reports_task_utility_and_recovery_separately() -> None:
    value = protocol()
    manifest = design.episode_manifest(value)
    rows = []
    for episode in manifest:
        if episode["method"] == design.FULL_METHOD:
            rows.append(
                fake_result(
                    episode,
                    success=episode["maximum_gui_actions"] >= 6,
                    reserve_stop=episode["maximum_gui_actions"] < 6,
                )
            )
        else:
            rows.append(
                fake_result(
                    episode,
                    success=True,
                    active=1,
                    unsafe_local=True,
                )
            )
    analysis = design.analyze_rows(rows, value, all_claims_complete=True)
    assert analysis["complete"] is True
    assert analysis["claim_status"] == "development_only_no_submission_claim"
    assert analysis["metrics"][design.LOCAL_ABLATION][
        "unsafe_local_admissions"
    ] == 45
    assert analysis["metrics"][design.LOCAL_ABLATION][
        "successes_with_active_obligations"
    ] == 45
    assert analysis["metrics"][design.FULL_METHOD]["reserve_stops"] > 0
    assert len(analysis["by_task_budget"]) == 9


def test_analysis_fails_closed_on_incomplete_manifest() -> None:
    value = protocol()
    rows = [
        fake_result(episode)
        for episode in design.episode_manifest(value)[:-1]
    ]
    analysis = design.analyze_rows(rows, value, all_claims_complete=False)
    assert analysis["exact_manifest"] is False
    assert analysis["all_claims_complete"] is False
    assert analysis["complete"] is False


def test_protocol_rejects_any_claim_status_upgrade() -> None:
    value = protocol()
    value["purpose"]["claim_status"] = "confirmatory"
    try:
        design.validate_protocol(value)
    except ValueError as error:
        assert "purpose changed" in str(error)
    else:
        raise AssertionError("claim-status mutation must be rejected")
