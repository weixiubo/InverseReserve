"""Existential-equivalence refinement for PACT public commit certificates.

PACT v4 correctly rejects duplicate referential targets but is too strict when
the instruction itself denotes a set of acceptable objects (for example, "a
checkbox" or any value satisfying a prefix predicate).  This module admits one
deterministic public-order representative only for those set-valued goals.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .goal_contracts_v4 import StructuredGoalContract
from .pact_grounding_v4 import (
    CommitCertificateV4,
    GroundingDecisionV4,
    stack_signature_v4,
    verify_commit_grounding_v4,
)
from .structured_planner_v4 import ActionCandidateV4
from .typed_observation import SemanticSnapshot


@dataclass(frozen=True)
class ExistentialPolicyV5:
    allowed: bool
    kind: str | None
    reason: str


def compile_existential_policy_v5(
    goal: StructuredGoalContract,
) -> ExistentialPolicyV5:
    """Recognize only explicit role indefinites and predicate-defined sets."""

    if goal.role_anchor is not None:
        role = re.escape(goal.role_anchor.role)
        pattern = re.compile(
            rf"\b(?:click|press|activate)\s+(?:on\s+)?(?:a|an)\s*"
            rf"[\"“]{role}[\"”]\s+(?:widget|control)\b",
            flags=re.IGNORECASE,
        )
        if pattern.search(goal.goal):
            return ExistentialPolicyV5(
                True,
                "explicit_indefinite_role",
                "instruction requests an arbitrary member of one public role",
            )
    if goal.exact_constraint is not None and goal.exact_constraint.kind in {
        "prefix",
        "suffix",
        "prefix_suffix",
    }:
        return ExistentialPolicyV5(
            True,
            "predicate_satisfaction_set",
            "instruction defines acceptable values by an explicit text predicate",
        )
    return ExistentialPolicyV5(
        False,
        None,
        "instruction does not expose a set-valued public target",
    )


def _bid_rank(value: str) -> tuple[int, int | str]:
    return (0, int(value)) if value.isdigit() else (1, value)


def _public_order_rank(
    current: SemanticSnapshot,
    bid: str,
) -> tuple[float, float, tuple[int, int | str]]:
    element = current.get(bid)
    if element is None or element.bbox is None:
        return (float("inf"), float("inf"), _bid_rank(bid))
    x, y, _width, _height = element.bbox
    return (float(y), float(x), _bid_rank(bid))


def canonical_equivalent_bid_v5(
    current: SemanticSnapshot,
    competing_bids: tuple[str, ...],
) -> str | None:
    if not competing_bids:
        return None
    if len(set(competing_bids)) != len(competing_bids):
        return None
    if any(current.get(bid) is None for bid in competing_bids):
        return None
    return min(competing_bids, key=lambda bid: _public_order_rank(current, bid))


def verify_commit_grounding_v5(
    *,
    current: SemanticSnapshot,
    goal: StructuredGoalContract,
    candidate: ActionCandidateV4,
    inventory: tuple[ActionCandidateV4, ...],
    active_transactions: tuple[Any, ...],
) -> GroundingDecisionV4:
    base = verify_commit_grounding_v4(
        current=current,
        goal=goal,
        candidate=candidate,
        inventory=inventory,
        active_transactions=active_transactions,
    )
    if base.allowed:
        return base
    policy = compile_existential_policy_v5(goal)
    compatible = bool(
        policy.allowed
        and len(base.competing_bids) > 1
        and (
            (
                policy.kind == "explicit_indefinite_role"
                and base.anchor_kind == "direct_role"
            )
            or (
                policy.kind == "predicate_satisfaction_set"
                and base.anchor_kind == "exact_target"
            )
        )
    )
    if not compatible:
        return base
    canonical = canonical_equivalent_bid_v5(current, base.competing_bids)
    if canonical is None:
        return GroundingDecisionV4(
            False,
            "set-valued grounding has no stable public-order representative",
            policy.kind,
            base.evidence_bids,
            base.competing_bids,
        )
    if candidate.bid != canonical:
        return GroundingDecisionV4(
            False,
            "candidate is not the canonical public-order representative",
            policy.kind,
            base.evidence_bids,
            base.competing_bids,
        )
    return GroundingDecisionV4(
        True,
        f"{policy.reason}; canonical public-order representative admitted",
        policy.kind,
        base.evidence_bids,
        base.competing_bids,
        canonical,
    )


def certify_commit_v5(
    *,
    current: SemanticSnapshot,
    goal: StructuredGoalContract,
    candidate: ActionCandidateV4,
    inventory: tuple[ActionCandidateV4, ...],
    active_transactions: tuple[Any, ...],
) -> CommitCertificateV4:
    grounding = verify_commit_grounding_v5(
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
