"""Explicit public grounding identity for fail-closed certificate construction."""

from __future__ import annotations

from dataclasses import dataclass

from inversereserve.contracts.pact_grounding_v4 import CommitCertificateV4, GroundingDecisionV4


@dataclass(frozen=True)
class CertificateDenial:
    anchor_kind: str
    binding_bids: tuple[str, ...]

    def __call__(self, reason: str, *, competing: tuple[str, ...] = ()) -> CommitCertificateV4:
        return CommitCertificateV4(
            False, reason, GroundingDecisionV4(False, reason, self.anchor_kind, self.binding_bids, competing)
        )
