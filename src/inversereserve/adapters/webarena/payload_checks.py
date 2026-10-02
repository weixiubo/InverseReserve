"""Shared active-obligation and public-value checks for mutation certificates."""

from __future__ import annotations

from typing import Any

from inversereserve.adapters.webarena.certificate_denial import CertificateDenial
from inversereserve.adapters.webarena.webarena_goal_adapter_v1 import (
    WebArenaGoalContractV1,
    _active_payload_bids,
    _normalized,
    _public_value,
)
from inversereserve.contracts.pact_grounding_v4 import CommitCertificateV4, GroundingDecisionV4
from inversereserve.contracts.pact_grounding_v8 import unresolved_blocking_transactions_v8
from inversereserve.observations.typed_observation import SemanticSnapshot


def active_payload_rejection(
    current: SemanticSnapshot,
    goal: WebArenaGoalContractV1,
    active_transactions: tuple[Any, ...],
    resolved_semantic_bids: tuple[str, ...],
    denied: CertificateDenial,
    *,
    deduplicate_blockers: bool = True,
) -> CommitCertificateV4 | None:
    blockers = unresolved_blocking_transactions_v8(active_transactions, resolved_semantic_bids)
    if blockers:
        return CommitCertificateV4(
            False,
            "a blocking typed overlay remains unresolved",
            GroundingDecisionV4(
                False,
                "a blocking typed overlay remains unresolved",
                denied.anchor_kind,
                tuple(
                    sorted(
                        {row.contract.semantic_bid for row in blockers}
                        if deduplicate_blockers
                        else (row.contract.semantic_bid for row in blockers)
                    )
                ),
            ),
        )
    if _active_payload_bids(active_transactions, goal) != denied.binding_bids:
        return denied("the exact-value field transaction is not active")
    if any(
        (
            _normalized(_public_value(current, binding.bid)) != _normalized(binding.value)
            for binding in goal.payload_bindings
        )
    ):
        return denied("the current public field value does not match the instruction")
    return None
