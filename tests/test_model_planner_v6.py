from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from rcrps.model_planner_v6 import (  # noqa: E402
    action_candidate_from_prompt_record_v6,
    canonical_planner_output_v6,
    parse_planner_decision_v6,
    planner_messages_v6,
)
from rcrps.structured_planner_v4 import ActionCandidateV4  # noqa: E402
from rcrps.transaction_actions_v4 import ContractActionV4  # noqa: E402


def candidate(
    bid: str,
    *,
    label: str,
    transaction_kind: str | None,
    operation: str = "click",
    argument: str | None = None,
) -> ActionCandidateV4:
    return ActionCandidateV4(
        bid=bid,
        action=ContractActionV4(operation, bid, argument),
        role="textbox" if transaction_kind else "button",
        label=label,
        state=(),
        transaction_kind=transaction_kind,
        semantic_bid=bid,
        parent_bid=None,
    )


def rows() -> tuple[ActionCandidateV4, ...]:
    return (
        candidate(
            "field",
            label="Tags",
            transaction_kind="autocomplete_query",
            operation="fill",
            argument="Som",
        ),
        candidate("submit", label="Submit", transaction_kind=None),
    )


def goal_contract() -> dict:
    return {
        "exact_constraint": {
            "kind": "prefix_suffix",
            "prefix": "Som",
            "suffix": "alia",
            "exact": None,
        },
        "field_assignments": [],
        "date_anchor": None,
        "option_selections": [],
        "role_anchor": None,
        "terminal_intent": None,
        "objective_anchor": None,
        "widget_kind_anchor": None,
    }


def test_v6_planner_messages_expose_bound_arguments_and_transaction_state() -> None:
    messages = planner_messages_v6(
        goal='Enter an item that starts with "Som" and ends with "alia".',
        goal_contract=goal_contract(),
        candidates=rows(),
        active_transactions=({"bid": "other", "transaction_kind": "field"},),
        completed_transactions=({"bid": "done"},),
    )
    assert [row["role"] for row in messages] == ["system", "user"]
    user = messages[1]["content"]
    assert '"arg": "Som"' in user
    assert '"transaction_kind": "autocomplete_query"' in user
    assert '"bid": "other"' in user
    assert '"bid": "done"' in user
    assert "task ID" not in user


def test_v6_parser_accepts_only_role_consistent_strict_json() -> None:
    transact = parse_planner_decision_v6(
        '{"decision":"transact","bid":"field"}', rows()
    )
    assert transact.decision == "transact"
    assert transact.candidate is not None
    assert transact.candidate.action.argument == "Som"

    commit = parse_planner_decision_v6(
        '{"decision":"commit","bid":"submit"}', rows()
    )
    assert commit.decision == "commit"
    assert commit.bid == "submit"

    abstain = parse_planner_decision_v6(
        '{"decision":"abstain","bid":null}', rows()
    )
    assert abstain.candidate is None


@pytest.mark.parametrize(
    "raw, message",
    (
        ('{"decision":"commit","bid":"field"}', "non-transaction"),
        ('{"decision":"transact","bid":"submit"}', "typed transaction"),
        ('{"decision":"abstain","bid":"submit"}', "null bid"),
        ('{"decision":"commit","bid":"missing"}', "absent"),
        ('{"decision":"click","bid":"submit"}', "must be transact"),
        ('{"decision":1,"bid":"submit"}', "JSON string"),
        ('{"decision":"commit","bid":1}', "JSON string or null"),
        ('{"decision":"commit","bid":"submit","why":"x"}', "exactly"),
        ('{"decision":"commit","bid":"submit"} trailing', "text after"),
    ),
)
def test_v6_parser_rejects_unsafe_or_semantically_invalid_outputs(
    raw: str,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        parse_planner_decision_v6(raw, rows())


def test_v6_canonical_output_round_trips_without_prose() -> None:
    raw = canonical_planner_output_v6("transact", "field")
    assert raw == '{"bid":"field","decision":"transact"}'
    assert json.loads(raw) == {"decision": "transact", "bid": "field"}
    assert parse_planner_decision_v6(raw, rows()).bid == "field"


def test_v6_parser_handles_generators_and_rejects_duplicate_bids() -> None:
    decision = parse_planner_decision_v6(
        '{"decision":"commit","bid":"submit"}', (row for row in rows())
    )
    assert decision.bid == "submit"

    duplicate = (rows()[0], rows()[0])
    with pytest.raises(ValueError, match="duplicate BIDs"):
        parse_planner_decision_v6(
            '{"decision":"transact","bid":"field"}', duplicate
        )


def test_v6_candidate_prompt_record_round_trip_is_exact() -> None:
    original = rows()[0]
    restored = action_candidate_from_prompt_record_v6(original.prompt_record())
    assert restored == original
    assert restored.prompt_record() == original.prompt_record()

    select = original.prompt_record()
    select.update(
        {
            "bid": "list",
            "semantic_bid": "list",
            "op": "select_option",
            "enable_autocomplete_menu": False,
            "transaction_kind": "native_select_update",
        }
    )
    select["arg"] = ["Somalia"]
    restored_select = action_candidate_from_prompt_record_v6(select)
    assert restored_select.action.argument == ("Somalia",)


@pytest.mark.parametrize(
    "mutation, message",
    (
        ({"extra": 1}, "schema"),
        ({"bid": 1}, "bid must"),
        ({"arg": 1}, "argument"),
        ({"enable_autocomplete_menu": 1}, "Boolean"),
        ({"state": []}, "state"),
    ),
)
def test_v6_candidate_prompt_record_rejects_schema_drift(
    mutation: dict, message: str
) -> None:
    record = rows()[0].prompt_record()
    record.update(mutation)
    with pytest.raises(ValueError, match=message):
        action_candidate_from_prompt_record_v6(record)
