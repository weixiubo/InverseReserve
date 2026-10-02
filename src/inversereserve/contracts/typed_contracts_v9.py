"""Suggestion-population evidence for the PACT-v9 typed postcondition."""

from __future__ import annotations

from inversereserve.contracts.typed_contracts_v4 import TransactionContractV4
from inversereserve.contracts.typed_contracts_v8 import (
    _query_aligned_text,
    check_transaction_postcondition_v8,
)
from inversereserve.observations.typed_observation import (
    ContractCheck,
    SemanticDelta,
    SemanticElement,
    SemanticSnapshot,
)


def _structural_suggestion_surface(element: SemanticElement) -> bool:
    """Recognize a public suggestion owner without trusting visibility timing."""

    role_surface = element.role.casefold() in {"listbox", "menu"}
    library_surface = (
        "ui-autocomplete" in element.class_tokens and "ui-autocomplete-input" not in element.class_tokens
    )
    return role_surface or library_surface


def _has_structural_suggestion_owner(snapshot: SemanticSnapshot, element: SemanticElement) -> bool:
    if _structural_suggestion_surface(element):
        return True
    ancestors = {
        row.bid: row
        for relation in ("dom", "ax")
        for row in snapshot.ancestors(element.bid, relation=relation)
    }
    return any(_structural_suggestion_surface(row) for row in ancestors.values())


def query_aligned_added_suggestion_rows_v9(
    after: SemanticSnapshot,
    delta: SemanticDelta,
    expected: str,
) -> tuple[str, ...]:
    """Return new query-aligned text grounded under a public suggestion owner."""

    rows = []
    for bid in delta.added_visible_bids:
        element = after.get(bid)
        if element is None or not after.is_effectively_visible(bid):
            continue
        if not _has_structural_suggestion_owner(after, element):
            continue
        text = element.subtree_text or element.name
        if text and _query_aligned_text((text,), expected) and text not in rows:
            rows.append(text)
    return tuple(rows)


def check_transaction_postcondition_v9(
    before: SemanticSnapshot,
    after: SemanticSnapshot,
    contract: TransactionContractV4,
) -> ContractCheck:
    """Apply v8 first, then admit a structurally grounded populated surface."""

    base = check_transaction_postcondition_v8(before, after, contract)
    if base.passed or contract.kind != "autocomplete_query":
        return base
    target_changed = contract.semantic_bid in base.delta.changed_visible_bids
    suggestion_rows = query_aligned_added_suggestion_rows_v9(
        after,
        base.delta,
        contract.expected_value or "",
    )
    if not target_changed or not suggestion_rows:
        return base
    return ContractCheck(
        True,
        "public field mutation and query-aligned newly populated suggestion rows corroborate the autocomplete forward",
        base.delta,
    )
