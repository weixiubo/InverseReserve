"""Standard-widget-kind commit certificate for PACT v6."""

from __future__ import annotations

from typing import Any

from inversereserve.contracts.pact_grounding_v4 import (
    CommitCertificateV4,
    GroundingDecisionV4,
    stack_signature_v4,
)
from inversereserve.contracts.pact_grounding_v5 import canonical_equivalent_bid_v5, verify_commit_grounding_v5
from inversereserve.models.structured_planner_v4 import ActionCandidateV4
from inversereserve.models.structured_planner_v6 import (
    StructuredGoalContractV6,
    element_matches_widget_kind_v6,
)
from inversereserve.observations.typed_observation import SemanticSnapshot


def verify_commit_grounding_v6(
    *,
    current: SemanticSnapshot,
    goal: Any,
    candidate: ActionCandidateV4,
    inventory: tuple[ActionCandidateV4, ...],
    active_transactions: tuple[Any, ...],
) -> GroundingDecisionV4:
    base = verify_commit_grounding_v5(
        current=current,
        goal=goal,
        candidate=candidate,
        inventory=inventory,
        active_transactions=active_transactions,
    )
    if base.allowed:
        return base
    if not isinstance(goal, StructuredGoalContractV6) or goal.widget_kind_anchor is None:
        return base
    rows_by_bid = {row.bid: row for row in inventory}
    if len(rows_by_bid) != len(inventory) or rows_by_bid.get(candidate.bid) != candidate:
        return GroundingDecisionV4(
            False,
            "candidate is not one authoritative v6 inventory row",
            "explicit_widget_kind",
        )
    kind = goal.widget_kind_anchor.kind
    competing = tuple(
        sorted(
            row.bid
            for row in inventory
            if (element := current.get(row.semantic_bid)) is not None
            and current.is_effectively_visible(element.bid)
            and element_matches_widget_kind_v6(element, kind)
        )
    )
    canonical = canonical_equivalent_bid_v5(current, competing)
    if canonical is None:
        return GroundingDecisionV4(
            False,
            "standard widget-kind grounding has no public representative",
            "explicit_widget_kind",
            (),
            competing,
        )
    if candidate.bid != canonical:
        return GroundingDecisionV4(
            False,
            "candidate is not the canonical standard widget-kind representative",
            "explicit_widget_kind",
            (),
            competing,
        )
    return GroundingDecisionV4(
        True,
        "explicit indefinite standard widget kind admits its canonical public-order leaf",
        "explicit_widget_kind",
        (),
        competing,
        canonical,
    )


def certify_commit_v6(
    *,
    current: SemanticSnapshot,
    goal: Any,
    candidate: ActionCandidateV4,
    inventory: tuple[ActionCandidateV4, ...],
    active_transactions: tuple[Any, ...],
) -> CommitCertificateV4:
    grounding = verify_commit_grounding_v6(
        current=current,
        goal=goal,
        candidate=candidate,
        inventory=inventory,
        active_transactions=active_transactions,
    )
    if not grounding.allowed:
        return CommitCertificateV4(False, grounding.reason, grounding)
    try:
        fingerprint = current.semantic_fingerprint()
    except Exception as error:
        return CommitCertificateV4(
            False,
            f"public observation fingerprint failed: {type(error).__name__}",
            grounding,
        )
    return CommitCertificateV4(
        True,
        grounding.reason,
        grounding,
        candidate.action,
        fingerprint,
        stack_signature_v4(active_transactions),
    )
