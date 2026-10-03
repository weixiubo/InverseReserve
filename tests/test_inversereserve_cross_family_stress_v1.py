from __future__ import annotations

import copy
from types import SimpleNamespace

import pytest

from inversereserve.studies import inversereserve_cross_family_stress_v1 as design


def _protocol() -> dict:
    return design.build_protocol(
        scientific_source_commit="0" * 40,
        source_sha256={},
        preregistration_path="paper/aaai27/notes/cross-family.md",
        preregistration_sha256="0" * 64,
        predecessor={"passed": True},
        repositories={"browsergym": "a", "miniwob_plusplus": "b"},
        created_utc="2026-07-19T00:00:00Z",
    )


def _endpoint_row(*, success: bool = False) -> dict:
    return {
        "success": success,
        "infrastructure_failure": False,
        "active_transactions_at_stop": [],
        "metrics": {
            "gui_actions": 0,
            "typed_transactions": 0,
            "runtime_halted": False,
            "restoration_attempts": 0,
            "restoration_passes": 0,
        },
    }


def test_activity_endpoint_rejects_the_clean_noop_degeneracy() -> None:
    abstain = _endpoint_row()
    assert design.clean_or_success(abstain)
    assert not design.activity_constrained_endpoint(abstain)

    success = _endpoint_row(success=True)
    success["metrics"].update(gui_actions=2, typed_transactions=1)
    assert design.activity_constrained_endpoint(success)

    recovered = _endpoint_row()
    recovered["metrics"].update(
        gui_actions=2,
        typed_transactions=1,
        restoration_attempts=1,
        restoration_passes=1,
    )
    assert design.activity_constrained_endpoint(recovered)

    stranded = copy.deepcopy(recovered)
    stranded["active_transactions_at_stop"] = [{"bid": "stranded"}]
    assert not design.activity_constrained_endpoint(stranded)


def test_manifest_is_fresh_complete_and_counterbalanced() -> None:
    protocol = _protocol()
    rows = design.episode_manifest(protocol)
    assert len(rows) == 600
    assert len({row["episode_id"] for row in rows}) == 600
    assert min(row["seed"] for row in rows) == 29301
    assert max(row["seed"] for row in rows) == 29320
    assert {row["task"] for row in rows} == set(design.TASK_BUDGETS)
    for arm in design.ARMS:
        assert sum(row["method"] == arm for row in rows) == 200
        position_counts = [
            sum(row["method"] == arm and row["arm_position"] == position for row in rows)
            for position in range(3)
        ]
        assert max(position_counts) - min(position_counts) <= 1


def _analysis_row(episode: dict) -> dict:
    method = episode["method"]
    task = episode["task"]
    low_budget = episode["maximum_gui_actions"] == min(design.TASK_BUDGETS[task])
    row = {
        "episode": copy.deepcopy(episode),
        "success": False,
        "infrastructure_failure": False,
        "active_transactions_at_stop": [],
        "trace": [],
        "runtime_events": [],
        "method_input": {"goal_sha256": (f"{task}-{episode['seed']}-{episode['maximum_gui_actions']}")},
        "metrics": {
            "gui_actions": 0,
            "typed_transactions": 0,
            "planner_calls": 0,
            "planner_actual_calls": 0,
            "planner_cache_hits": 0,
            "inverse_reservation_stops": 0,
            "restoration_attempts": 0,
            "restoration_passes": 0,
            "runtime_halted": False,
            "wall_seconds": 0.1,
        },
    }
    if method == design.ABSTAIN_BASELINE:
        return row

    contract_kind = {
        "use-autocomplete-nodelay": "autocomplete_text",
        "login-user-popup": "editable_value",
        "book-flight-nodelay": "flight_field",
    }[task]
    row["runtime_events"] = [
        {
            "type": "postcondition",
            "context": "typed forward",
            "contract_kind": contract_kind,
            "passed": True,
        }
    ]
    row["metrics"].update(
        gui_actions=min(2, episode["maximum_gui_actions"]),
        typed_transactions=1,
        planner_calls=int(task != "use-autocomplete-nodelay"),
        planner_actual_calls=int(method == design.FULL_METHOD and task == "login-user-popup"),
    )
    if not low_budget:
        row["success"] = True
        return row
    event_index = 0
    if task != "use-autocomplete-nodelay":
        row["trace"].append(
            {
                "event_index": event_index,
                "type": "envelope_decision_v8",
                "model": {"cache_key": "planner"},
            }
        )
        event_index += 1
    row["trace"].append(
        {
            "event_index": event_index,
            "type": "cross_family_reservation_v1",
            "reservation_rule": ("stack_wide" if method == design.FULL_METHOD else "proposal_local"),
            "decision": "transact",
            "bid": "candidate",
            "registered_active_inverse_cost": 1,
            "proposal_inverse_cost": 1,
            "stack_wide_required_inverse_cost": 2,
            "applied_inverse_reserve": (2 if method == design.FULL_METHOD else 1),
            "remaining_after_action": 1,
            "allowed": method == design.LOCAL_ABLATION,
        }
    )
    if method == design.FULL_METHOD:
        row["metrics"].update(
            inverse_reservation_stops=1,
            restoration_attempts=1,
            restoration_passes=1,
        )
        return row

    row["active_transactions_at_stop"] = [{"bid": "stranded"}]
    row["metrics"].update(restoration_attempts=1, restoration_passes=0)
    return row


def test_analysis_enforces_activity_planner_and_sequence_gates() -> None:
    protocol = _protocol()
    rows = [_analysis_row(row) for row in design.episode_manifest(protocol)]
    result = design.analyze_rows(rows, protocol, all_claims_complete=True)
    assert result["passed"] is True
    assert all(result["checks"].values())
    paired = result["paired_activity_endpoint"]
    assert paired["cell_wins"] == 60
    assert paired["cell_losses"] == 0
    assert paired["seed_cluster_wins"] == 20
    assert paired["sequence_adjusted_pvalue_upper_bound"] < 0.05
    assert paired["planner_mediated_paired_wins"] == 40
    assert paired["coactivated_effect_families"] == 2
    assert paired["observed_contract_kinds"] == [
        "autocomplete_text",
        "editable_value",
        "flight_field",
    ]
    abstain = result["metrics"][design.ABSTAIN_BASELINE]
    assert abstain["clean_or_success_episodes"] == 200
    assert abstain["activity_endpoint_episodes"] == 0


def test_analysis_fails_if_one_family_lacks_planner_before_divergence() -> None:
    protocol = _protocol()
    rows = [_analysis_row(row) for row in design.episode_manifest(protocol)]
    for row in rows:
        episode = row["episode"]
        if (
            episode["task"] == "login-user-popup"
            and episode["maximum_gui_actions"] == min(design.TASK_BUDGETS["login-user-popup"])
            and episode["method"] in design.RESERVE_ARMS
        ):
            row["trace"] = [event for event in row["trace"] if event.get("type") != "envelope_decision_v8"]
    result = design.analyze_rows(rows, protocol, all_claims_complete=True)
    assert result["passed"] is False
    assert result["checks"]["minimum_coactivated_effect_families"] is False


def test_protocol_rejects_task_budget_or_endpoint_mutation() -> None:
    protocol = _protocol()
    changed_budget = copy.deepcopy(protocol)
    changed_budget["tasks"][0]["gui_action_budgets"].append(5)
    with pytest.raises(ValueError, match="task-budget"):
        design.validate_protocol(changed_budget)

    changed_endpoint = copy.deepcopy(protocol)
    changed_endpoint["primary_outcome"]["name"] = "clean_or_success"
    with pytest.raises(ValueError, match="primary outcome"):
        design.validate_protocol(changed_endpoint)


def test_active_arms_share_one_code_path_except_reserve_accounting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    full_class = design.StackWideCrossFamilyDriverV15
    local_class = design.ProposalLocalCrossFamilyDriverV15
    for name in (
        "inventory",
        "fresh_envelope",
        "run_policy",
        "inverse_reserve",
        "result",
    ):
        assert getattr(full_class, name) is getattr(local_class, name)
    allowed_class_fields = {"__module__", "__doc__", "method_id", "stack_wide"}
    assert set(full_class.__dict__) == allowed_class_fields
    assert set(local_class.__dict__) == allowed_class_fields

    from inversereserve.studies.designs import inversereserve_cross_family_stress_v1 as reserve_design

    monkeypatch.setattr(reserve_design, "inverse_action_cost_v8", int)

    def driver(driver_class: type) -> tuple[object, list[dict]]:
        instance = driver_class.__new__(driver_class)
        instance.runtime = SimpleNamespace(active=[SimpleNamespace(contract=2)])
        instance.budgets = {"maximum_gui_actions": 4}
        instance.executor = SimpleNamespace(actions=[{"prior": True}])
        instance.inventory = lambda: SimpleNamespace(contract_by_bid={"candidate": 1})
        instance.inverse_reservation_audits = 0
        audit: list[dict] = []
        instance.audit = audit.append
        return instance, audit

    full, full_audit = driver(full_class)
    local, local_audit = driver(local_class)
    candidate = SimpleNamespace(bid="candidate")
    assert full.inverse_reserve(candidate, "transact") == (False, 3)
    assert local.inverse_reserve(candidate, "transact") == (True, 1)
    ignored = {"reservation_rule", "applied_inverse_reserve", "allowed"}
    assert {key: value for key, value in full_audit[0].items() if key not in ignored} == {
        key: value for key, value in local_audit[0].items() if key not in ignored
    }
