"""Public goal-terminal and navigation-scope rules for PACT v20.

V19 treats every row with a registered inverse as a transaction, even when
that same public row is the uniquely preferred exact goal target. It consumes
form mutations only after an effective terminal commit, whereas a small set of
blocking overlays may be consumed after an effective commit. The rules below
close both gaps without task identifiers,
page selectors, evaluator fields, or reward:

* a unique preferred exact target is compiled as a commit, not a transaction;
* an effective exact-target commit may consume a structurally bound or
  terminal navigation suffix; and
* repeated navigation rows are suppressed by semantic identity.
"""

from __future__ import annotations

import re
from dataclasses import replace
from typing import Any, Iterable

from inversereserve.contracts.pact_grounding_v3 import satisfies_constraint
from inversereserve.contracts.pact_grounding_v4 import transaction_scope_bids
from inversereserve.contracts.pact_grounding_v19 import resolved_by_commit_v19
from inversereserve.models.structured_planner_v4 import ActionCandidateV4, V4ActionInventory
from inversereserve.observations.typed_observation import SemanticSnapshot

GOAL_NAVIGATION_KINDS_V20 = frozenset({"disclosure_toggle", "menu_hover", "tab_switch", "tree_folder_toggle"})
EXACT_TARGET_COMMIT_ANCHOR_V20 = "exact_target"
PREFERRED_EXACT_TARGET_ROLES_V20 = {
    "button": 0,
    "file": 0,
    "link": 0,
    "menuitem": 0,
    "option": 0,
    "treeitem": 0,
    "listitem": 1,
    "tab": 2,
    "generic": 2,
}


def _normalize(value: object) -> str:
    return re.sub("\\s+", " ", str(value or "")).strip().casefold()


def _candidate_visible(current: SemanticSnapshot, candidate: ActionCandidateV4) -> bool:
    action = current.get(candidate.bid)
    semantic = current.get(candidate.semantic_bid)
    return bool(
        action is not None
        and semantic is not None
        and (candidate.publicly_actionable_offscreen or current.is_effectively_visible(candidate.bid))
        and (
            candidate.publicly_actionable_offscreen or current.is_effectively_visible(candidate.semantic_bid)
        )
    )


def _publicly_related_alias(
    current: SemanticSnapshot, candidate: ActionCandidateV4, preferred: ActionCandidateV4
) -> bool:
    if candidate.bid == preferred.bid:
        return True
    if candidate.semantic_bid == preferred.semantic_bid:
        return True
    preferred_bids = {preferred.bid, preferred.semantic_bid}
    candidate_bids = {candidate.bid, candidate.semantic_bid}
    for relation in ("ax", "dom"):
        preferred_ancestors = {
            row.bid for bid in preferred_bids for row in current.ancestors(bid, relation=relation)
        }
        candidate_ancestors = {
            row.bid for bid in candidate_bids for row in current.ancestors(bid, relation=relation)
        }
        if candidate_bids & preferred_ancestors:
            return True
        if preferred_bids & candidate_ancestors:
            return True
    return False


def promote_unique_exact_target_v20(
    current: SemanticSnapshot, inventory: V4ActionInventory, *, transaction_history: Iterable[Any] = ()
) -> tuple[V4ActionInventory, dict[str, Any] | None]:
    """Promote one public leaf-like exact target after visible prerequisites."""
    constraint = getattr(inventory.goal_contract, "exact_constraint", None)
    if constraint is None or getattr(constraint, "kind", None) != "exact":
        return (inventory, None)
    matching = _matching_exact_targets(current, inventory, constraint)
    if not matching:
        return (inventory, None)
    preferred = _unique_preferred_target(matching)
    if preferred is None:
        return (inventory, None)
    aliases = _related_target_aliases(current, matching, preferred)
    if aliases is None:
        return (inventory, None)
    alias_bids = {preferred.bid, *(row.bid for row in aliases)}
    unfinished_typed_rows = _unfinished_typed_candidates(inventory, alias_bids)
    history = tuple(transaction_history)
    terminal_intent = getattr(inventory.goal_contract, "terminal_intent", None)
    if unfinished_typed_rows and terminal_intent is not None and (not history):
        return (inventory, None)
    original_kind = preferred.transaction_kind
    if original_kind is None and (not aliases):
        return (inventory, None)
    removed_alias_bids = {row.bid for row in aliases}
    updated = promoted_inventory(inventory, preferred, removed_alias_bids)
    return (
        updated,
        {
            "type": "goal_terminal_promotion_v20",
            "promoted_bid": preferred.bid,
            "promoted_role": preferred.role,
            "semantic_bid": preferred.semantic_bid,
            "label": preferred.label,
            "original_transaction_kind": original_kind,
            "removed_related_alias_bids": sorted(removed_alias_bids),
            "basis": "unique preferred public exact target after a registered transaction"
            if history
            else "unique preferred public exact target without typed prerequisite",
        },
    )


def suppress_repeated_navigation_v20(
    inventory: V4ActionInventory, *, active_transactions: Iterable[Any], completed_transactions: Iterable[Any]
) -> V4ActionInventory:
    """Do not revisit one navigation semantic under a different inferred kind."""
    used = _used_navigation_bids(tuple(active_transactions) + tuple(completed_transactions))
    if not used:
        return inventory
    rows = tuple(
        (
            row
            for row in inventory.candidates
            if not (row.transaction_kind in GOAL_NAVIGATION_KINDS_V20 and row.semantic_bid in used)
        )
    )
    if rows == inventory.candidates:
        return inventory
    row_bids = {row.bid for row in rows}
    return V4ActionInventory(
        inventory.allowed,
        inventory.reason,
        inventory.goal_contract,
        rows,
        tuple(((bid, contract) for bid, contract in inventory.contracts if bid in row_bids)),
    )


def navigation_contract_requires_replan_v20(
    current: SemanticSnapshot, contract: Any, active_transactions: tuple[Any, ...]
) -> bool:
    """Require restoration before a navigation action outside the active top."""
    if not active_transactions or contract.kind not in GOAL_NAVIGATION_KINDS_V20:
        return False
    top = active_transactions[-1]
    if top.contract.kind not in GOAL_NAVIGATION_KINDS_V20:
        return False
    scope = transaction_scope_bids(current, top)
    action_bid = str(getattr(contract.action, "bid", "") or "")
    return str(contract.semantic_bid) not in scope and action_bid not in scope


def resolved_by_commit_v20(
    *,
    current: SemanticSnapshot,
    candidate: ActionCandidateV4,
    active_transactions: tuple[Any, ...],
    certificate: Any,
    terminal: bool,
) -> tuple[str, ...]:
    """Resolve v19 scopes plus one certificate-bound navigation suffix."""
    resolved = set(
        resolved_by_commit_v19(
            current=current,
            candidate=candidate,
            active_transactions=active_transactions,
            certificate=certificate,
            terminal=terminal,
        )
    )
    grounding = getattr(certificate, "grounding", None)
    if (
        getattr(certificate, "allowed", False) is not True
        or grounding is None
        or getattr(grounding, "anchor_kind", None) != EXACT_TARGET_COMMIT_ANCHOR_V20
    ):
        return tuple(sorted(resolved))
    structurally_bound = []
    for index, transaction in enumerate(active_transactions):
        if transaction.contract.kind not in GOAL_NAVIGATION_KINDS_V20:
            continue
        scope = transaction_scope_bids(current, transaction)
        if candidate.bid in scope or candidate.semantic_bid in scope:
            structurally_bound.append(index)
    if structurally_bound:
        start = min(structurally_bound)
        suffix = active_transactions[start:]
        if all((transaction.contract.kind in GOAL_NAVIGATION_KINDS_V20 for transaction in suffix)):
            resolved.update((str(transaction.contract.semantic_bid) for transaction in suffix))
    if terminal:
        resolved.update(_terminal_navigation_suffix(active_transactions))
    return tuple(sorted(resolved))


__all__ = [
    "EXACT_TARGET_COMMIT_ANCHOR_V20",
    "GOAL_NAVIGATION_KINDS_V20",
    "navigation_contract_requires_replan_v20",
    "promote_unique_exact_target_v20",
    "resolved_by_commit_v20",
    "suppress_repeated_navigation_v20",
]


def _matching_exact_targets(
    current: SemanticSnapshot, inventory: V4ActionInventory, constraint: Any
) -> tuple[ActionCandidateV4, ...]:
    return tuple(
        (
            row
            for row in inventory.candidates
            if row.action.operation == "click"
            and _candidate_visible(current, row)
            and satisfies_constraint(row.label, constraint)
        )
    )


def _unique_preferred_target(matching: tuple[ActionCandidateV4, ...]) -> ActionCandidateV4 | None:
    ranked = [(PREFERRED_EXACT_TARGET_ROLES_V20.get(row.role.casefold(), 3), row) for row in matching]
    best_rank = min((rank for rank, _row in ranked))
    best = tuple((row for rank, row in ranked if rank == best_rank))
    if len(best) != 1:
        return None
    preferred = best[0]
    return preferred


def _related_target_aliases(
    current: SemanticSnapshot, matching: tuple[ActionCandidateV4, ...], preferred: ActionCandidateV4
) -> tuple[ActionCandidateV4, ...] | None:
    aliases = tuple(
        (
            row
            for row in matching
            if row.bid != preferred.bid
            and _normalize(row.label) == _normalize(preferred.label)
            and _publicly_related_alias(current, row, preferred)
        )
    )
    unrelated = tuple((row for row in matching if row.bid != preferred.bid and row not in aliases))
    if unrelated:
        return None
    return aliases


def promoted_inventory(
    inventory: V4ActionInventory, preferred: ActionCandidateV4, removed_alias_bids: set[str]
) -> V4ActionInventory:
    promoted = replace(preferred, transaction_kind=None)
    rows = tuple(
        (
            promoted if row.bid == preferred.bid else row
            for row in inventory.candidates
            if row.bid not in removed_alias_bids
        )
    )
    contracts = tuple(
        (
            (bid, contract)
            for bid, contract in inventory.contracts
            if bid != preferred.bid and bid not in removed_alias_bids
        )
    )
    updated = V4ActionInventory(inventory.allowed, inventory.reason, inventory.goal_contract, rows, contracts)
    return updated


def _used_navigation_bids(records: tuple[Any, ...]) -> set[str]:
    used = set()
    for record in records:
        contract = record.get("contract") if isinstance(record, dict) else getattr(record, "contract", None)
        kind = (
            str(contract.get("kind", ""))
            if isinstance(contract, dict)
            else str(getattr(contract, "kind", ""))
        )
        semantic_bid = (
            str(contract.get("semantic_bid", ""))
            if isinstance(contract, dict)
            else str(getattr(contract, "semantic_bid", ""))
        )
        if not contract and isinstance(record, dict):
            kind = str(record.get("transaction_kind", ""))
            semantic_bid = str(record.get("semantic_bid", ""))
        if kind in GOAL_NAVIGATION_KINDS_V20 and semantic_bid:
            used.add(semantic_bid)
    return used


def _terminal_navigation_suffix(active_transactions: tuple[Any, ...]) -> tuple[str, ...]:
    start = len(active_transactions)
    while start > 0 and active_transactions[start - 1].contract.kind in GOAL_NAVIGATION_KINDS_V20:
        start -= 1
    return tuple((str(transaction.contract.semantic_bid) for transaction in active_transactions[start:]))


def _unfinished_typed_candidates(inventory: V4ActionInventory, alias_bids: set[str]) -> tuple[Any, ...]:
    return tuple(
        (
            row
            for row in inventory.candidates
            if row.bid not in alias_bids and row.transaction_kind is not None
        )
    )
