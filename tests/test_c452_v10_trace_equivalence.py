from __future__ import annotations

import copy
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from rcrps.c452_v10_trace_equivalence import (  # noqa: E402
    analyze_c452_rows,
    analyze_episode,
)


def event_rows(*, remaining: int = 4, grounding_count: int = 1) -> dict:
    trace = [
        {
            "event_index": 0,
            "type": "inverse_budget_reservation",
            "decision": "transact",
            "bid": "field",
            "active_inverse_cost": 1,
            "remaining_after_action": remaining,
            "allowed": True,
        },
        {
            "event_index": 1,
            "type": "typed_transaction_result_v8",
            "bid": "field",
            "admitted": True,
            "interrupt_repairs": 1,
            "halted": False,
        },
        {
            "event_index": 2,
            "type": "inverse_budget_reservation",
            "decision": "transact",
            "bid": "other",
            "active_inverse_cost": 2,
            "remaining_after_action": 2,
            "allowed": True,
        },
        {
            "event_index": 3,
            "type": "typed_transaction_result_v8",
            "bid": "other",
            "admitted": True,
            "interrupt_repairs": 0,
            "halted": False,
        },
    ]
    runtime = [
        {
            "event_index": index,
            "type": "compensator_grounding",
            "candidate_bids": ["dismiss"],
            "allowed": True,
        }
        for index in range(grounding_count)
    ]
    return {
        "episode": {
            "episode_id": "login-user-popup__seed27421__full_pact_v9",
            "task": "login-user-popup",
            "seed": 27421,
            "method": "full_pact_v9",
        },
        "success": True,
        "method_failure": None,
        "infrastructure_failure": False,
        "trace": trace,
        "runtime_events": runtime,
        "metrics": {"typed_transactions": 2, "runtime_halted": False},
    }


def test_c452_repair_trace_proves_v10_action_path_equivalence() -> None:
    audit = analyze_episode(event_rows(remaining=3))
    assert audit["v10_action_path_equivalent"] is True
    assert audit["interrupt_repairs"] == 1
    assert audit["minimum_v10_slack_after_repair"] == 0
    assert audit["repair_transactions"] == [
        {
            "transaction_ordinal": 0,
            "bid": "field",
            "result_bid": "field",
            "v9_allowed": True,
            "v9_admitted": True,
            "v9_halted": False,
            "interrupt_repairs": 1,
            "remaining_after_forward": 3,
            "registered_inverse_reserve": 1,
            "v10_repair_action_cost": 2,
            "v10_slack_after_repair": 0,
        }
    ]


def test_c452_trace_rejects_repair_that_would_spend_inverse_reserve() -> None:
    audit = analyze_episode(event_rows(remaining=2))
    assert audit["v10_action_path_equivalent"] is False
    assert (
        audit["checks"][
            "every_v9_repair_preserves_the_complete_inverse_reserve_under_v10"
        ]
        is False
    )
    assert audit["minimum_v10_slack_after_repair"] == -1


def test_c452_trace_rejects_ambiguous_or_unpaired_grounding() -> None:
    ambiguous = event_rows()
    ambiguous["runtime_events"][0]["candidate_bids"] = ["dismiss", "cancel"]
    assert analyze_episode(ambiguous)["v10_action_path_equivalent"] is False

    missing = event_rows(grounding_count=0)
    assert analyze_episode(missing)["v10_action_path_equivalent"] is False

    mismatched = event_rows()
    mismatched["trace"][1]["bid"] = "wrong"
    assert analyze_episode(mismatched)["v10_action_path_equivalent"] is False


def test_c452_aggregate_requires_nonvacuous_changed_branch_coverage() -> None:
    passing = event_rows()
    result = analyze_c452_rows([passing], expected_episodes=1)
    assert result["passed"] is True
    assert result["interrupt_repairs"] == 1

    no_repair = copy.deepcopy(passing)
    no_repair["trace"][1]["interrupt_repairs"] = 0
    no_repair["runtime_events"] = []
    result = analyze_c452_rows([no_repair], expected_episodes=1)
    assert result["passed"] is False
    assert result["checks"]["changed_interrupt_repair_branch_was_observed"] is False

    result = analyze_c452_rows([passing], expected_episodes=2)
    assert result["passed"] is False
    assert result["checks"]["complete_c452_episode_population"] is False
