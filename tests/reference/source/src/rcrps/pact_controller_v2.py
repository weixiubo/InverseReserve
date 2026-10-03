"""C428 controller repairs derived from the complete failed C427 traces."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .pact_controller import (
    ActiveTransaction,
    CommitGrounding,
    goal_declares_state_prerequisite,
    ground_commit,
    transaction_scope_bids,
)
from .structured_planner import ActionCandidate
from .typed_observation import SemanticSnapshot


SAME_LEVEL_KINDS = frozenset({"tab_switch", "disclosure_toggle"})
PREFERRED_COMMIT_ROLES = {
    "button": 0,
    "link": 0,
    "file": 0,
    "menuitem": 0,
    "option": 0,
    "treeitem": 0,
    "listitem": 1,
    "generic": 2,
}


@dataclass(frozen=True)
class ExplorationRelation:
    nested: bool
    reason: str
    repeated_active: bool


def _shares_semantic_parent(
    current: SemanticSnapshot,
    candidate: ActionCandidate,
    transaction: ActiveTransaction,
) -> bool:
    active_element = current.get(transaction.contract.semantic_bid)
    candidate_element = current.get(candidate.semantic_bid) or current.get(candidate.bid)
    active_parents = {
        value
        for value in (
            active_element.ax_parent_bid if active_element else None,
            active_element.dom_parent_bid if active_element else None,
        )
        if value is not None
    }
    candidate_parents = {
        value
        for value in (
            candidate.parent_bid,
            candidate_element.ax_parent_bid if candidate_element else None,
            candidate_element.dom_parent_bid if candidate_element else None,
        )
        if value is not None
    }
    return bool(active_parents & candidate_parents)


def classify_exploration_relation(
    current: SemanticSnapshot,
    candidate: ActionCandidate,
    transaction: ActiveTransaction,
) -> ExplorationRelation:
    if (
        candidate.bid == transaction.contract.action_bid
        or candidate.semantic_bid == transaction.contract.semantic_bid
    ):
        return ExplorationRelation(False, "candidate repeats the active transaction", True)
    if (
        transaction.contract.kind in SAME_LEVEL_KINDS
        and candidate.preview_kind in SAME_LEVEL_KINDS
        and _shares_semantic_parent(current, candidate, transaction)
    ):
        return ExplorationRelation(
            False,
            "tab or disclosure with the same parent is a same-level search action",
            False,
        )
    scope = transaction_scope_bids(current, transaction)
    nested = candidate.bid in scope or candidate.semantic_bid in scope
    return ExplorationRelation(
        nested,
        "candidate is structurally inside the active delta"
        if nested
        else "candidate is outside the active delta",
        False,
    )


def unique_grounded_fallback(
    goal: str,
    candidates: Iterable[ActionCandidate],
    *,
    allow_state_prerequisite: bool = False,
) -> tuple[ActionCandidate | None, str]:
    unmet_state_prerequisite = (
        goal_declares_state_prerequisite(goal) and not allow_state_prerequisite
    )
    grounded = []
    for candidate in candidates:
        certificate = ground_commit(goal, candidate)
        if certificate.allowed and certificate.target_label is not None:
            if unmet_state_prerequisite and candidate.preview_kind is None:
                continue
            priority = PREFERRED_COMMIT_ROLES.get(candidate.role.casefold(), 3)
            grounded.append((priority, candidate))
    if not grounded:
        if unmet_state_prerequisite:
            return (
                None,
                "instruction state prerequisite has no active transaction or exact typed-target certificate",
            )
        return None, "no visible candidate has an exact target-label certificate"
    best_priority = min(priority for priority, _candidate in grounded)
    best = [candidate for priority, candidate in grounded if priority == best_priority]
    unique = {candidate.bid: candidate for candidate in best}
    if len(unique) != 1:
        return None, "target grounding is ambiguous among equally preferred controls"
    candidate = next(iter(unique.values()))
    return candidate, "one preferred visible control has an exact target-label certificate"


def downgrade_ungrounded_commit(
    grounding: CommitGrounding,
    candidate: ActionCandidate,
) -> bool:
    return not grounding.allowed and candidate.preview_kind is not None


def upgrade_grounded_exploration(
    goal: str,
    candidate: ActionCandidate,
) -> bool:
    grounding = ground_commit(goal, candidate)
    return (
        candidate.preview_kind is not None
        and grounding.allowed
        and grounding.target_label is not None
    )
