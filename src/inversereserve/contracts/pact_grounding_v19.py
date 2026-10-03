"""Certificate-bound discharge of intended public form mutations.

PACT-v18 consumes only transient blocking overlays.  V19 additionally permits
an effective, freshly certified terminal form commit to mark exact goal-state
mutations as committed.  The extension uses only semantic BIDs returned as
evidence by the complete public goal-state certificate.
"""

from __future__ import annotations

from typing import Any

from inversereserve.contracts.pact_grounding_v8 import resolved_by_commit_v8

GOAL_MUTATION_KINDS_V19 = frozenset({"editable_field_assignment", "native_select_update"})
GOAL_STATE_COMMIT_ANCHOR_V19 = "state_supported_form_action"


def _contract_field(contract: Any, name: str) -> str:
    if isinstance(contract, dict):
        return str(contract.get(name, ""))
    return str(getattr(contract, name, ""))


def goal_mutations_resolved_by_certificate_v19(
    *,
    active_transactions: tuple[Any, ...],
    anchor_kind: str,
    evidence_bids: tuple[str, ...],
) -> tuple[str, ...]:
    """Resolve exact intended mutations named by a goal-state certificate."""

    if anchor_kind != GOAL_STATE_COMMIT_ANCHOR_V19:
        return ()
    evidence = {str(value) for value in evidence_bids}
    resolved = set()
    for transaction in active_transactions:
        contract = (
            transaction.get("contract")
            if isinstance(transaction, dict)
            else getattr(transaction, "contract", None)
        )
        kind = _contract_field(contract, "kind")
        semantic_bid = _contract_field(contract, "semantic_bid")
        if kind in GOAL_MUTATION_KINDS_V19 and semantic_bid in evidence:
            resolved.add(semantic_bid)
    return tuple(sorted(resolved))


def resolved_by_commit_v19(
    *,
    current: Any,
    candidate: Any,
    active_transactions: tuple[Any, ...],
    certificate: Any,
    terminal: bool,
) -> tuple[str, ...]:
    """Return v18 scopes plus terminal-certified goal-state mutations."""

    resolved = set(
        resolved_by_commit_v8(
            current=current,
            candidate=candidate,
            active_transactions=active_transactions,
        )
    )
    if not terminal:
        return tuple(sorted(resolved))
    grounding = getattr(certificate, "grounding", None)
    if (
        getattr(certificate, "allowed", False) is not True
        or grounding is None
        or getattr(grounding, "anchor_kind", None) != GOAL_STATE_COMMIT_ANCHOR_V19
    ):
        return tuple(sorted(resolved))

    resolved.update(
        goal_mutations_resolved_by_certificate_v19(
            active_transactions=active_transactions,
            anchor_kind=str(grounding.anchor_kind),
            evidence_bids=tuple(str(value) for value in grounding.evidence_bids),
        )
    )
    return tuple(sorted(resolved))


__all__ = [
    "GOAL_MUTATION_KINDS_V19",
    "GOAL_STATE_COMMIT_ANCHOR_V19",
    "goal_mutations_resolved_by_certificate_v19",
    "resolved_by_commit_v19",
]
