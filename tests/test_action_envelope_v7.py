from __future__ import annotations

from pathlib import Path

import pytest

from inversereserve.contracts.action_envelope_v7 import (
    assemble_action_envelope_v7,
    envelope_messages_v7,
    resolve_action_envelope_v7,
)
from inversereserve.contracts.transaction_actions_v4 import ContractActionV4
from inversereserve.models.structured_planner_v4 import ActionCandidateV4

ROOT = Path(__file__).resolve().parents[1]


def row(bid: str, kind: str | None, *, label: str | None = None) -> ActionCandidateV4:
    return ActionCandidateV4(
        bid=bid,
        action=ContractActionV4("click", bid),
        role="link" if kind == "calendar_month_shift" else "button",
        label=label or bid,
        state=(),
        transaction_kind=kind,
        semantic_bid="date" if kind == "calendar_month_shift" else bid,
        parent_bid=None,
    )


def goal_contract() -> dict:
    return {
        "exact_constraint": None,
        "field_assignments": [],
        "date_anchor": None,
        "option_selections": [],
        "role_anchor": None,
        "terminal_intent": None,
        "objective_anchor": None,
        "widget_kind_anchor": None,
    }


def test_v7_fresh_certificate_dominates_premature_typed_and_form_rows() -> None:
    rows = (row("field", "editable_field_assignment"), row("submit", None))
    envelope = assemble_action_envelope_v7(candidates=rows, admitted_certificate_bids=("submit",))
    assert envelope.decision == "commit"
    assert [candidate.bid for candidate in envelope.candidates] == ["submit"]
    assert envelope.model_call_required is False
    resolution = resolve_action_envelope_v7(envelope)
    assert (resolution.decision, resolution.bid, resolution.source) == (
        "commit",
        "submit",
        "singleton_envelope",
    )


def test_v7_unfinished_typed_rows_exclude_active_control_and_form_distractor() -> None:
    rows = (
        row("username", "editable_field_assignment"),
        row("password", "editable_field_assignment"),
        row("login", None),
    )
    envelope = assemble_action_envelope_v7(
        candidates=rows,
        active_transactions=({"transaction_kind": "editable_field_assignment", "semantic_bid": "password"},),
    )
    assert envelope.decision == "transact"
    assert [candidate.bid for candidate in envelope.candidates] == ["username"]
    assert resolve_action_envelope_v7(envelope).bid == "username"


def test_v7_calendar_shift_is_repeatable_while_component_open_is_not() -> None:
    rows = (
        row("open", "datepicker_open"),
        row("next", "calendar_month_shift", label="Next"),
        row("submit", None),
    )
    history = (
        {"transaction_kind": "datepicker_open", "semantic_bid": "open"},
        {"transaction_kind": "calendar_month_shift", "semantic_bid": "date"},
    )
    envelope = assemble_action_envelope_v7(candidates=rows, active_transactions=history)
    assert [candidate.bid for candidate in envelope.candidates] == ["next"]


def test_v7_empty_envelope_abstains_without_model() -> None:
    envelope = assemble_action_envelope_v7(candidates=(row("irrelevant", None),))
    assert envelope.decision == "abstain"
    resolution = resolve_action_envelope_v7(envelope)
    assert resolution.bid is None
    assert resolution.source == "empty_envelope"


def test_v7_multirow_envelope_uses_model_only_with_fixed_decision() -> None:
    envelope = assemble_action_envelope_v7(
        candidates=(row("from", "autocomplete_query"), row("to", "autocomplete_query"))
    )
    assert envelope.model_call_required is True
    messages = envelope_messages_v7(
        goal="Fill both fields.", goal_contract=goal_contract(), envelope=envelope
    )
    assert "FIXED DECISION: transact" in messages[1]["content"]
    assert "submit" not in messages[1]["content"].casefold()
    resolution = resolve_action_envelope_v7(envelope, model_output='{"decision":"transact","bid":"to"}')
    assert resolution.bid == "to"
    assert resolution.source == "shared_model"
    with pytest.raises(ValueError, match="fixed envelope decision"):
        resolve_action_envelope_v7(envelope, model_output='{"decision":"abstain","bid":null}')


def test_v7_fail_closed_invariants_reject_ambiguous_or_mistyped_certificates() -> None:
    rows = (row("a", None), row("b", None))
    with pytest.raises(ValueError, match="multiple fresh"):
        assemble_action_envelope_v7(candidates=rows, admitted_certificate_bids=("a", "b"))
    with pytest.raises(ValueError, match="typed row"):
        assemble_action_envelope_v7(
            candidates=(row("field", "editable_field_assignment"),), admitted_certificate_bids=("field",)
        )


def test_v7_singleton_and_abstain_reject_unnecessary_model_calls() -> None:
    singleton = assemble_action_envelope_v7(candidates=(row("field", "editable_field_assignment"),))
    with pytest.raises(ValueError, match="must not receive"):
        resolve_action_envelope_v7(singleton, model_output='{"decision":"transact","bid":"field"}')
    abstain = assemble_action_envelope_v7(candidates=())
    with pytest.raises(ValueError, match="must not receive"):
        resolve_action_envelope_v7(abstain, model_output='{"decision":"abstain","bid":null}')
