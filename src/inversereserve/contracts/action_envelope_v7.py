"""Typed PACT-v7 action envelopes for model-constrained arbitration."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Iterable

from inversereserve.contracts.pact_grounding_v6 import certify_commit_v6
from inversereserve.models.model_planner_v6 import (
    PlannerDecisionV6,
    compact_goal_contract_record,
    parse_planner_decision_v6,
)
from inversereserve.models.structured_planner_v4 import ActionCandidateV4, V4ActionInventory
from inversereserve.observations.typed_observation import SemanticSnapshot

ENVELOPE_SYSTEM_PROMPT_V7 = 'You are the shared model chooser inside a PACT typed action envelope.\nPACT has already fixed the safe decision type and removed stale, premature, uncertified, and already-used rows.\nEvery remaining action argument is bound to an exact public goal span.\n\nChoose exactly one BID from the envelope.\nAll listed rows have the same fixed decision type. Do not change that type.\nWhen several rows remain, their execution order is semantically free; choose the row that most directly advances the structured goal.\nOutput exactly one compact JSON object and no prose:\n  {"decision":"FIXED_DECISION","bid":"BID"}\n'


@dataclass(frozen=True)
class ActionEnvelopeV7:
    decision: str
    candidates: tuple[ActionCandidateV4, ...]
    admitted_certificate_bids: tuple[str, ...]
    reason: str

    def __post_init__(self) -> None:
        if self.decision not in {"transact", "commit", "abstain"}:
            raise ValueError("invalid v7 envelope decision")
        if len({candidate.bid for candidate in self.candidates}) != len(self.candidates):
            raise ValueError("v7 envelope contains duplicate BIDs")
        if self.decision == "abstain" and self.candidates:
            raise ValueError("abstain envelope must be empty")
        if self.decision != "abstain" and (not self.candidates):
            raise ValueError("action envelope cannot be empty")
        self._validate_candidate_types()
        if self.decision != "commit" and self.admitted_certificate_bids:
            raise ValueError("only a commit envelope may carry admitted certificates")
        if (
            set(self.admitted_certificate_bids) != {candidate.bid for candidate in self.candidates}
            and self.decision == "commit"
        ):
            raise ValueError("commit envelope and admitted certificates disagree")

    @property
    def model_call_required(self) -> bool:
        return len(self.candidates) > 1

    def record(self) -> dict[str, Any]:
        return {
            "decision": self.decision,
            "candidates": [candidate.prompt_record() for candidate in self.candidates],
            "admitted_certificate_bids": list(self.admitted_certificate_bids),
            "reason": self.reason,
            "model_call_required": self.model_call_required,
        }

    def _validate_candidate_types(self) -> None:
        if self.decision == "transact" and any(
            (candidate.transaction_kind is None for candidate in self.candidates)
        ):
            raise ValueError("transaction envelope contains an untyped row")
        if self.decision == "commit" and any(
            (candidate.transaction_kind is not None for candidate in self.candidates)
        ):
            raise ValueError("commit envelope contains a typed row")


@dataclass(frozen=True)
class EnvelopeResolutionV7:
    decision: str
    bid: str | None
    candidate: ActionCandidateV4 | None
    source: str


def _history_value(record: Any, name: str) -> Any:
    if isinstance(record, dict):
        return record.get(name)
    contract = getattr(record, "contract", None)
    if contract is None:
        return getattr(record, name, None)
    if name == "transaction_kind":
        return contract.kind
    if name == "semantic_bid":
        return contract.semantic_bid
    return getattr(record, name, None)


def _already_used(candidate: ActionCandidateV4, history: tuple[Any, ...]) -> bool:
    if candidate.transaction_kind == "calendar_month_shift":
        return False
    return any(
        (
            _history_value(record, "transaction_kind") == candidate.transaction_kind
            and _history_value(record, "semantic_bid") == candidate.semantic_bid
            for record in history
        )
    )


def assemble_action_envelope_v7(
    *,
    candidates: Iterable[ActionCandidateV4],
    admitted_certificate_bids: Iterable[str] = (),
    active_transactions: Iterable[Any] = (),
    completed_transactions: Iterable[Any] = (),
) -> ActionEnvelopeV7:
    """Assemble an envelope from fresh certificate decisions and typed history."""
    rows = tuple(candidates)
    by_bid = {candidate.bid: candidate for candidate in rows}
    if len(by_bid) != len(rows):
        raise ValueError("authoritative inventory contains duplicate BIDs")
    admitted = tuple(admitted_certificate_bids)
    if len(admitted) != len(set(admitted)):
        raise ValueError("duplicate admitted certificate BID")
    if len(admitted) > 1:
        raise ValueError("multiple fresh commit certificates violate fail-closed v7")
    if admitted:
        bid = admitted[0]
        candidate = by_bid.get(bid)
        if candidate is None:
            raise ValueError("admitted certificate BID is absent from inventory")
        if candidate.transaction_kind is not None:
            raise ValueError("admitted commit certificate names a typed row")
        return ActionEnvelopeV7(
            "commit", (candidate,), admitted, "one fresh PACT-v6 commit certificate fixes the action"
        )
    history = tuple(active_transactions) + tuple(completed_transactions)
    unfinished = tuple(
        (
            candidate
            for candidate in rows
            if candidate.transaction_kind is not None and (not _already_used(candidate, history))
        )
    )
    if unfinished:
        return ActionEnvelopeV7(
            "transact", unfinished, (), "no commit is certified; unfinished goal-bound typed rows remain"
        )
    return ActionEnvelopeV7(
        "abstain", (), (), "no fresh commit certificate or unfinished typed transaction exists"
    )


def compile_action_envelope_v7(
    *,
    current: SemanticSnapshot,
    inventory: V4ActionInventory,
    active_transactions: Iterable[Any] = (),
    completed_transactions: Iterable[Any] = (),
) -> ActionEnvelopeV7:
    """Compute a fresh action envelope using only public PACT state."""
    active = tuple(active_transactions)
    admitted = []
    for candidate in inventory.candidates:
        if candidate.transaction_kind is not None:
            continue
        certificate = certify_commit_v6(
            current=current,
            goal=inventory.goal_contract,
            candidate=candidate,
            inventory=inventory.candidates,
            active_transactions=active,
        )
        if certificate.allowed:
            admitted.append(candidate.bid)
    return assemble_action_envelope_v7(
        candidates=inventory.candidates,
        admitted_certificate_bids=admitted,
        active_transactions=active,
        completed_transactions=completed_transactions,
    )


def envelope_messages_v7(
    *,
    goal: str,
    goal_contract: Any,
    envelope: ActionEnvelopeV7,
    active_transactions: Iterable[dict[str, Any]] = (),
    completed_transactions: Iterable[dict[str, Any]] = (),
) -> list[dict[str, str]]:
    if not envelope.model_call_required:
        raise ValueError("singleton and abstain envelopes must not call the model")
    inventory = "\n".join(
        (
            json.dumps(candidate.prompt_record(), ensure_ascii=False, sort_keys=True)
            for candidate in envelope.candidates
        )
    )
    system = ENVELOPE_SYSTEM_PROMPT_V7.replace("FIXED_DECISION", envelope.decision)
    user = f"GOAL:\n{str(goal).strip()}\n\nSTRUCTURED GOAL CONTRACT:\n{json.dumps(compact_goal_contract_record(goal_contract), ensure_ascii=False, sort_keys=True)}\n\nFIXED DECISION: {envelope.decision}\n\nACTIVE TRANSACTIONS:\n{json.dumps(tuple(active_transactions), ensure_ascii=False, sort_keys=True)}\n\nCOMPLETED TRANSACTIONS:\n{json.dumps(tuple(completed_transactions), ensure_ascii=False, sort_keys=True)}\n\nTYPED ACTION ENVELOPE ({len(envelope.candidates)} rows):\n{inventory}"
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def resolve_action_envelope_v7(
    envelope: ActionEnvelopeV7, *, model_output: str | None = None
) -> EnvelopeResolutionV7:
    if envelope.decision == "abstain":
        if model_output is not None:
            raise ValueError("abstain envelope must not receive model output")
        return EnvelopeResolutionV7("abstain", None, None, "empty_envelope")
    if not envelope.model_call_required:
        if model_output is not None:
            raise ValueError("singleton envelope must not receive model output")
        candidate = envelope.candidates[0]
        return EnvelopeResolutionV7(envelope.decision, candidate.bid, candidate, "singleton_envelope")
    if model_output is None:
        raise ValueError("multi-row envelope requires model output")
    parsed: PlannerDecisionV6 = parse_planner_decision_v6(model_output, envelope.candidates)
    if parsed.decision != envelope.decision:
        raise ValueError("model changed the fixed envelope decision")
    return EnvelopeResolutionV7(parsed.decision, parsed.bid, parsed.candidate, "shared_model")
