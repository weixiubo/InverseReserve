"""Bind an admitted public mutation to its current effect identity."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from inversereserve.adapters.webarena.certificate_denial import CertificateDenial
from inversereserve.contracts.pact_grounding_v4 import CommitCertificateV4, GroundingDecisionV4
from inversereserve.contracts.pact_grounding_v8 import commit_attempt_key_v8
from inversereserve.models.structured_planner_v4 import ActionCandidateV4
from inversereserve.observations.typed_observation import SemanticSnapshot


@dataclass(frozen=True)
class CommitMessages:
    allowed: str
    quarantined: str
    bind_payload_on_error: bool = False


def finalize_mutation_commit(
    *,
    current: SemanticSnapshot,
    candidate: ActionCandidateV4,
    active_transactions: tuple[Any, ...],
    quarantined_commit_keys: frozenset[tuple[object, ...]],
    denied: CertificateDenial,
    competing: tuple[str, ...],
    messages: CommitMessages,
) -> CommitCertificateV4:
    try:
        key = commit_attempt_key_v8(
            current=current, action=candidate.action, active_transactions=active_transactions
        )
    except Exception as error:
        reason = f"public effect key failed: {type(error).__name__}"
        if messages.bind_payload_on_error:
            return denied(reason)
        return CommitCertificateV4(
            False, reason, GroundingDecisionV4(False, "public effect key failed", denied.anchor_kind)
        )
    if key in quarantined_commit_keys:
        return CommitCertificateV4(
            False,
            messages.quarantined,
            GroundingDecisionV4(
                False, messages.quarantined, "no_effect_quarantine", denied.binding_bids, competing
            ),
        )
    grounding = GroundingDecisionV4(
        True, messages.allowed, denied.anchor_kind, denied.binding_bids, competing, candidate.bid
    )
    return CommitCertificateV4(True, grounding.reason, grounding, candidate.action, key[0], key[1])
