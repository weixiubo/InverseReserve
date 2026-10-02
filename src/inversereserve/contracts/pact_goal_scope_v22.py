"""PACT-v22 public goal-equivalent terminal target promotion.

PACT-v20 requires one structurally unique exact target.  MiniWoB++ tree
objectives can instead make a public disjunction explicit, for example
``folder or file named "Myron"``.  When every exact-label match is one of
those two declared alternatives, either match satisfies the public goal.
V22 selects a deterministic representative of that public equivalence class
and preserves fail-closed ambiguity for every other duplicate target.
"""

from __future__ import annotations

import re
from typing import Any, Iterable

from inversereserve.contracts.pact_goal_scope_v20 import (
    PREFERRED_EXACT_TARGET_ROLES_V20,
    promote_unique_exact_target_v20,
    promoted_inventory,
)
from inversereserve.contracts.pact_grounding_v3 import satisfies_constraint
from inversereserve.models.structured_planner_v4 import ActionCandidateV4, V4ActionInventory
from inversereserve.observations.typed_observation import SemanticSnapshot

GOAL_EQUIVALENT_PROMOTION_EVENT_V22 = "goal_equivalent_terminal_promotion_v22"
FOLDER_OR_FILE_PATTERN_V22 = re.compile("\\bfolder\\s+or\\s+file\\s+named\\b", re.IGNORECASE)


def _candidate_visible_v22(current: SemanticSnapshot, candidate: ActionCandidateV4) -> bool:
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


def _declared_tree_alternative_v22(candidate: ActionCandidateV4) -> str | None:
    role = candidate.role.casefold()
    if role == "file" and candidate.transaction_kind is None:
        return "file"
    if role in {"listitem", "treeitem"} and candidate.transaction_kind == "tree_folder_toggle":
        return "folder"
    return None


def promote_goal_equivalent_exact_target_v22(
    current: SemanticSnapshot, inventory: V4ActionInventory, *, transaction_history: Iterable[Any] = ()
) -> tuple[V4ActionInventory, dict[str, Any] | None]:
    """Promote a unique target or one explicitly declared target class.

    The v20 rule remains authoritative.  The only added branch recognizes the
    literal public disjunction ``folder or file named`` and requires every
    visible exact-label match to be classifiable as one of those alternatives.
    No task identifier, evaluator field, reward, or hidden state is inspected.
    """
    promoted, record = promote_unique_exact_target_v20(
        current, inventory, transaction_history=transaction_history
    )
    if record is not None:
        return (promoted, record)
    constraint = getattr(inventory.goal_contract, "exact_constraint", None)
    if (
        constraint is None
        or getattr(constraint, "kind", None) != "exact"
        or FOLDER_OR_FILE_PATTERN_V22.search(str(getattr(inventory.goal_contract, "goal", ""))) is None
    ):
        return (inventory, None)
    matching = _matching_goal_equivalents(current, inventory, constraint)
    if len(matching) < 2:
        return (inventory, None)
    alternatives = tuple((_declared_tree_alternative_v22(candidate) for candidate in matching))
    if any((alternative is None for alternative in alternatives)) or set(alternatives) != {"folder", "file"}:
        return (inventory, None)
    ranked = tuple(
        (
            (PREFERRED_EXACT_TARGET_ROLES_V20.get(candidate.role.casefold(), 3), candidate.bid, candidate)
            for candidate in matching
        )
    )
    preferred = min(ranked, key=lambda row: (row[0], row[1]))[2]
    removed_equivalent_bids = {candidate.bid for candidate in matching if candidate.bid != preferred.bid}
    updated = promoted_inventory(inventory, preferred, removed_equivalent_bids)
    return (
        updated,
        {
            "type": "goal_terminal_promotion_v20",
            "promotion_rule": GOAL_EQUIVALENT_PROMOTION_EVENT_V22,
            "promoted_bid": preferred.bid,
            "promoted_role": preferred.role,
            "semantic_bid": preferred.semantic_bid,
            "label": preferred.label,
            "original_transaction_kind": preferred.transaction_kind,
            "removed_related_alias_bids": sorted(removed_equivalent_bids),
            "declared_alternatives": sorted(set(alternatives)),
            "basis": "deterministic representative of the public folder-or-file exact-target equivalence class",
        },
    )


__all__ = [
    "FOLDER_OR_FILE_PATTERN_V22",
    "GOAL_EQUIVALENT_PROMOTION_EVENT_V22",
    "promote_goal_equivalent_exact_target_v22",
]


def _matching_goal_equivalents(
    current: SemanticSnapshot, inventory: V4ActionInventory, constraint: Any
) -> tuple[ActionCandidateV4, ...]:
    return tuple(
        (
            candidate
            for candidate in inventory.candidates
            if candidate.action.operation == "click"
            and _candidate_visible_v22(current, candidate)
            and satisfies_constraint(candidate.label, constraint)
        )
    )
