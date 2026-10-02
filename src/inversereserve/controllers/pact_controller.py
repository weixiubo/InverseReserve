"""Model-independent transaction-stack policy for Preview Action Contracts."""

from __future__ import annotations

import re
from dataclasses import dataclass

from inversereserve.models.structured_planner import ActionCandidate
from inversereserve.observations.typed_observation import PreviewContract, SemanticDelta, SemanticSnapshot

STATE_PREREQUISITE_PATTERNS = (
    re.compile(r"\bexpand\b", re.IGNORECASE),
    re.compile(r"\bswitch\s+between\b", re.IGNORECASE),
    re.compile(r"\bnavigate\s+through\b", re.IGNORECASE),
    re.compile(r"\bopen\b.+\bthen\b", re.IGNORECASE),
    re.compile(r"\bselect\s+[^>]+>", re.IGNORECASE),
)


@dataclass(frozen=True)
class ActiveTransaction:
    contract: PreviewContract
    candidate_label: str
    before: SemanticSnapshot
    after: SemanticSnapshot
    delta: SemanticDelta

    def planner_record(self) -> dict[str, str]:
        return {
            "bid": self.contract.action_bid,
            "label": self.candidate_label,
            "preview_kind": self.contract.kind,
            "semantic_bid": self.contract.semantic_bid,
        }

    def completed_record(self, *, target_found: bool) -> dict[str, object]:
        return {
            **self.planner_record(),
            "target_found": bool(target_found),
        }


@dataclass(frozen=True)
class CommitAdmission:
    allowed: bool
    reason: str
    supporting_transaction_depth: int | None


@dataclass(frozen=True)
class CommitGrounding:
    allowed: bool
    reason: str
    target_label: str | None


def _label(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().casefold()


def instruction_target_label(goal: str) -> str | None:
    quoted = re.findall(r'["“]([^"”]+)["”]', goal)
    if quoted:
        return re.sub(r"\s+", " ", quoted[-1]).strip()
    if goal.casefold().startswith("select "):
        return goal.split(">")[-1].removeprefix("Select ").strip()
    if "submit" in goal.casefold():
        return "submit"
    return None


def ground_commit(goal: str, candidate: ActionCandidate) -> CommitGrounding:
    """Verify exact public label grounding before a planner-declared commit."""

    target = instruction_target_label(goal)
    if target is None:
        return CommitGrounding(True, "instruction has no exact-label contract", None)
    observed = _label(candidate.label)
    expected = _label(target)
    aliases = {("x", "close"), ("close", "x")}
    if observed == expected or (expected, observed) in aliases:
        return CommitGrounding(True, "candidate label matches the instruction target", target)
    return CommitGrounding(
        False,
        "candidate label does not exactly match the instruction target",
        target,
    )


def goal_declares_state_prerequisite(goal: str) -> bool:
    return any(pattern.search(goal) for pattern in STATE_PREREQUISITE_PATTERNS)


def transaction_scope_bids(
    current: SemanticSnapshot,
    transaction: ActiveTransaction,
) -> frozenset[str]:
    bids = set(transaction.delta.added_visible_bids)
    bids.update(transaction.delta.changed_visible_bids)
    bids.add(transaction.contract.semantic_bid)
    for relation in ("ax", "dom"):
        bids.update(
            element.bid
            for element in current.descendants(
                transaction.contract.semantic_bid,
                relation=relation,
            )
        )
    return frozenset(bids)


def exploration_is_nested(
    current: SemanticSnapshot,
    candidate: ActionCandidate,
    transaction: ActiveTransaction,
) -> bool:
    scope = transaction_scope_bids(current, transaction)
    return candidate.bid in scope or candidate.semantic_bid in scope


def admit_commit(
    *,
    goal: str,
    current: SemanticSnapshot,
    candidate: ActionCandidate,
    active_transactions: tuple[ActiveTransaction, ...],
) -> CommitAdmission:
    if not active_transactions:
        return CommitAdmission(True, "direct grounded commit", None)
    for reverse_index, transaction in enumerate(reversed(active_transactions), start=1):
        scope = transaction_scope_bids(current, transaction)
        if candidate.bid in scope or candidate.semantic_bid in scope:
            depth = len(active_transactions) - reverse_index + 1
            return CommitAdmission(
                True,
                "commit target is structurally bound to an active transaction delta",
                depth,
            )
    if goal_declares_state_prerequisite(goal):
        return CommitAdmission(
            True,
            "goal explicitly requires the verified active state before commit",
            len(active_transactions),
        )
    return CommitAdmission(
        False,
        "commit target is outside every active transaction and no state prerequisite is declared",
        None,
    )
