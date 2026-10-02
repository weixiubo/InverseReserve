"""Resolution-aware typed action envelopes for PACT-v8."""

from __future__ import annotations

from typing import Any, Iterable

from inversereserve.contracts.action_envelope_v7 import ActionEnvelopeV7, assemble_action_envelope_v7
from inversereserve.contracts.pact_grounding_v8 import unresolved_blocking_transactions_v8
from inversereserve.models.structured_planner_v4 import ActionCandidateV4


def _contract(record: Any) -> Any:
    return record.get("contract") if isinstance(record, dict) else record.contract


def assemble_action_envelope_v8(
    *,
    candidates: Iterable[ActionCandidateV4],
    admitted_certificate_bids: Iterable[str] = (),
    active_transactions: Iterable[Any] = (),
    completed_transactions: Iterable[Any] = (),
    resolved_semantic_bids: Iterable[str] = (),
) -> ActionEnvelopeV7:
    """Prioritize resolution of the top public typed overlay."""

    rows = tuple(candidates)
    admitted = tuple(admitted_certificate_bids)
    active = tuple(active_transactions)
    completed = tuple(completed_transactions)
    if admitted:
        return assemble_action_envelope_v7(
            candidates=rows,
            admitted_certificate_bids=admitted,
            active_transactions=active,
            completed_transactions=completed,
        )
    blockers = unresolved_blocking_transactions_v8(active, tuple(resolved_semantic_bids))
    if blockers:
        top = _contract(blockers[0])
        if top.kind == "autocomplete_query":
            return ActionEnvelopeV7(
                "abstain",
                (),
                (),
                "active autocomplete overlay has no certified resolution; unrelated actions are withheld",
            )
        shifts = tuple(
            candidate
            for candidate in rows
            if candidate.transaction_kind == "calendar_month_shift"
            and candidate.semantic_bid == top.semantic_bid
        )
        if shifts:
            return ActionEnvelopeV7(
                "transact",
                shifts,
                (),
                "unresolved datepicker exposes only goal-directed month-shift transactions",
            )
        return ActionEnvelopeV7(
            "abstain",
            (),
            (),
            "active datepicker has no certified goal-day resolution or goal-directed month shift",
        )
    return assemble_action_envelope_v7(
        candidates=rows,
        admitted_certificate_bids=(),
        active_transactions=active,
        completed_transactions=completed,
    )
