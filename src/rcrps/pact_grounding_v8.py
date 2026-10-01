"""Resolution-aware, effect-quarantined commit certificates for PACT-v8."""

from __future__ import annotations

import re
from typing import Any, Iterable

from .pact_grounding_v4 import (
    CommitCertificateV4,
    GroundingDecisionV4,
    stack_signature_v4,
    transaction_scope_bids,
)
from .pact_grounding_v5 import canonical_equivalent_bid_v5
from .pact_grounding_v6 import verify_commit_grounding_v6
from .structured_planner_v4 import ActionCandidateV4
from .transaction_actions_v4 import ContractActionV4
from .typed_observation import SemanticSnapshot


BLOCKING_TRANSACTION_KINDS_V8 = frozenset(
    {"autocomplete_query", "datepicker_open", "calendar_month_shift"}
)


def _contract(record: Any) -> Any:
    return record.get("contract") if isinstance(record, dict) else record.contract


def unresolved_blocking_transactions_v8(
    active_transactions: Iterable[Any],
    resolved_semantic_bids: Iterable[str],
) -> tuple[Any, ...]:
    resolved = {str(bid) for bid in resolved_semantic_bids}
    output = []
    seen = set()
    for transaction in reversed(tuple(active_transactions)):
        contract = _contract(transaction)
        semantic_bid = str(contract.semantic_bid)
        if (
            contract.kind not in BLOCKING_TRANSACTION_KINDS_V8
            or semantic_bid in resolved
            or semantic_bid in seen
        ):
            continue
        output.append(transaction)
        seen.add(semantic_bid)
    return tuple(output)


def _field_assignment_matches(goal: Any, semantic_bid: str, expected: str) -> bool:
    return any(
        str(assignment.bid) == semantic_bid
        and str(assignment.value).casefold() == expected.casefold()
        for assignment in goal.field_assignments
    )


def _public_code_equivalence(
    *,
    current: SemanticSnapshot,
    goal: Any,
    candidate: ActionCandidateV4,
    inventory: tuple[ActionCandidateV4, ...],
    active_transactions: tuple[Any, ...],
    base: GroundingDecisionV4,
    resolved_semantic_bids: tuple[str, ...],
) -> GroundingDecisionV4 | None:
    if base.anchor_kind != "active_field_value" or len(base.competing_bids) < 2:
        return None
    unresolved = unresolved_blocking_transactions_v8(
        active_transactions, resolved_semantic_bids
    )
    transaction = next(
        (
            row
            for row in unresolved
            if _contract(row).kind == "autocomplete_query"
        ),
        None,
    )
    if transaction is None:
        return None
    contract = _contract(transaction)
    expected = str(contract.expected_value or "")
    if not re.fullmatch(r"[A-Z]{3}", expected):
        return None
    semantic_bid = str(contract.semantic_bid)
    if not _field_assignment_matches(goal, semantic_bid, expected):
        return None
    by_bid = {row.bid: row for row in inventory}
    code = re.compile(rf"(?<![A-Za-z0-9]){re.escape(expected)}(?![A-Za-z0-9])")
    if any(
        bid not in by_bid or code.search(str(by_bid[bid].label)) is None
        for bid in base.competing_bids
    ):
        return None
    canonical = canonical_equivalent_bid_v5(current, base.competing_bids)
    if canonical is None:
        return None
    if candidate.bid != canonical:
        return GroundingDecisionV4(
            False,
            "candidate is not the canonical representative of equivalent public airport-code suggestions",
            "active_field_equivalence",
            (semantic_bid,),
            base.competing_bids,
        )
    return GroundingDecisionV4(
        True,
        "all competing public suggestions share the exact goal airport code; canonical public-order representative admitted",
        "active_field_equivalence",
        (semantic_bid,),
        base.competing_bids,
        canonical,
    )


def verify_commit_grounding_v8(
    *,
    current: SemanticSnapshot,
    goal: Any,
    candidate: ActionCandidateV4,
    inventory: tuple[ActionCandidateV4, ...],
    active_transactions: tuple[Any, ...],
    resolved_semantic_bids: tuple[str, ...] = (),
) -> GroundingDecisionV4:
    base = verify_commit_grounding_v6(
        current=current,
        goal=goal,
        candidate=candidate,
        inventory=inventory,
        active_transactions=active_transactions,
    )
    if base.allowed:
        blockers = unresolved_blocking_transactions_v8(
            active_transactions, resolved_semantic_bids
        )
        if base.anchor_kind == "state_supported_form_action" and blockers:
            return GroundingDecisionV4(
                False,
                "form action is premature while a typed overlay transaction is unresolved",
                "unresolved_transaction_barrier",
                tuple(sorted({_contract(row).semantic_bid for row in blockers})),
                base.competing_bids,
            )
        return base
    equivalent = _public_code_equivalence(
        current=current,
        goal=goal,
        candidate=candidate,
        inventory=inventory,
        active_transactions=active_transactions,
        base=base,
        resolved_semantic_bids=resolved_semantic_bids,
    )
    return equivalent if equivalent is not None else base


def commit_attempt_key_v8(
    *,
    current: SemanticSnapshot,
    action: ContractActionV4,
    active_transactions: tuple[Any, ...],
) -> tuple[object, ...]:
    argument: object = action.argument
    if isinstance(argument, tuple):
        argument = tuple(argument)
    return (
        current.semantic_fingerprint(),
        stack_signature_v4(active_transactions),
        action.operation,
        action.bid,
        argument,
        action.enable_autocomplete_menu,
    )


def certify_commit_v8(
    *,
    current: SemanticSnapshot,
    goal: Any,
    candidate: ActionCandidateV4,
    inventory: tuple[ActionCandidateV4, ...],
    active_transactions: tuple[Any, ...],
    resolved_semantic_bids: tuple[str, ...] = (),
    quarantined_commit_keys: frozenset[tuple[object, ...]] = frozenset(),
) -> CommitCertificateV4:
    grounding = verify_commit_grounding_v8(
        current=current,
        goal=goal,
        candidate=candidate,
        inventory=inventory,
        active_transactions=active_transactions,
        resolved_semantic_bids=resolved_semantic_bids,
    )
    if not grounding.allowed:
        return CommitCertificateV4(False, grounding.reason, grounding)
    try:
        key = commit_attempt_key_v8(
            current=current,
            action=candidate.action,
            active_transactions=active_transactions,
        )
    except Exception as error:
        return CommitCertificateV4(
            False,
            f"public effect key failed: {type(error).__name__}",
            grounding,
        )
    if key in quarantined_commit_keys:
        rejected = GroundingDecisionV4(
            False,
            "the same certified action already had zero public effect at this observation and stack",
            "no_effect_quarantine",
            grounding.evidence_bids,
            grounding.competing_bids,
        )
        return CommitCertificateV4(False, rejected.reason, rejected)
    fingerprint = key[0]
    stack = key[1]
    return CommitCertificateV4(
        True,
        grounding.reason,
        grounding,
        candidate.action,
        fingerprint,
        stack,
    )


def resolved_by_commit_v8(
    *,
    current: SemanticSnapshot,
    candidate: ActionCandidateV4,
    active_transactions: tuple[Any, ...],
) -> tuple[str, ...]:
    resolved = set()
    for transaction in reversed(active_transactions):
        contract = _contract(transaction)
        if contract.kind not in BLOCKING_TRANSACTION_KINDS_V8:
            continue
        scope = transaction_scope_bids(current, transaction)
        if candidate.bid in scope or candidate.semantic_bid in scope:
            resolved.add(str(contract.semantic_bid))
    return tuple(sorted(resolved))
