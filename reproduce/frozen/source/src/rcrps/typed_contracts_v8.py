"""Cross-channel typed postconditions for PACT-v8.

The frozen v4 checker remains authoritative.  V8 adds one narrowly scoped
fallback for autocomplete widgets whose AX ``value`` channel can lag the DOM
mutation observed in the same BrowserGym snapshot.
"""

from __future__ import annotations

import re

from .typed_contracts_v4 import (
    TransactionContractV4,
    check_transaction_postcondition,
    contract_projection,
)
from .typed_observation import ContractCheck, SemanticSnapshot


def _normalize(value: object) -> str:
    return " ".join(str(value or "").split()).strip().casefold()


def _query_aligned_text(texts: tuple[str, ...], expected: str) -> bool:
    query = _normalize(expected)
    if not query:
        return False
    token = re.compile(rf"(?<![\w]){re.escape(query)}(?![\w])", re.IGNORECASE)
    for text in texts:
        normalized = _normalize(text)
        if token.search(normalized):
            return True
        if any(word.startswith(query) for word in re.findall(r"[\w]+", normalized)):
            return True
    return False


def check_transaction_postcondition_v8(
    before: SemanticSnapshot,
    after: SemanticSnapshot,
    contract: TransactionContractV4,
) -> ContractCheck:
    """Apply v4 first, then a conjunctive public autocomplete fallback."""

    base = check_transaction_postcondition(before, after, contract)
    if base.passed or contract.kind != "autocomplete_query":
        return base
    before_projection = contract_projection(before, contract)
    after_projection = contract_projection(after, contract)
    before_surfaces = before_projection[2]
    after_surfaces = after_projection[2]
    surface_added = bool(after_surfaces) and after_surfaces != before_surfaces
    target_changed = contract.semantic_bid in base.delta.changed_visible_bids
    query_aligned = _query_aligned_text(
        base.delta.newly_visible_text,
        contract.expected_value or "",
    )
    passed = bool(surface_added and target_changed and query_aligned)
    if not passed:
        return base
    return ContractCheck(
        True,
        "public field mutation and query-aligned suggestion surface corroborate the autocomplete forward",
        base.delta,
    )
