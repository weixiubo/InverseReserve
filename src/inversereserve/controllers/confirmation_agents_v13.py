"""PACT-v13 confirmation driver with complete-public commit freshness."""

from __future__ import annotations

from typing import Any

from inversereserve.contracts.action_envelope_v8 import assemble_action_envelope_v8
from inversereserve.contracts.pact_grounding_v8 import certify_commit_v8
from inversereserve.controllers.confirmation_agents_v12 import (
    FullPactConfirmationDriverV12,
    complete_public_no_effect_metrics_v12,
)
from inversereserve.controllers.pact_controller_v13 import (
    COMPLETE_PUBLIC_COMMIT_FINGERPRINT_VERSION_V13,
    FailClosedTransactionRuntimeV13,
    bind_complete_public_commit_certificate_v13,
)


def complete_public_commit_metrics_v13(driver: Any) -> dict[str, int]:
    events = driver.runtime.events
    checks = [
        event for event in events if event.get("type") == "complete_public_commit_observation_check_v13"
    ]
    return {
        "complete_public_commit_checks_v13": len(checks),
        "complete_public_commit_passes_v13": sum(event.get("passed") is True for event in checks),
        "complete_public_commit_rejections_v13": sum(event.get("passed") is False for event in checks),
    }


class FullPactConfirmationDriverV13(FullPactConfirmationDriverV12):
    """V12 plus complete-public binding for every terminal certificate."""

    method_id = "full_pact_v13"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.runtime = FailClosedTransactionRuntimeV13(
            self.executor,
            self.interrupt_repair_reservation,
        )

    def fresh_envelope(self, inventory: Any) -> tuple[Any, dict[str, Any], list[dict[str, Any]]]:
        admitted = []
        certificates = {}
        audit = []
        current = self.executor.snapshot
        active = tuple(self.runtime.active)
        resolved = tuple(sorted(self.resolved_semantic_bids))
        for candidate in inventory.candidates:
            if candidate.transaction_kind is not None:
                continue
            certificate = certify_commit_v8(
                current=current,
                goal=inventory.goal_contract,
                candidate=candidate,
                inventory=inventory.candidates,
                active_transactions=active,
                resolved_semantic_bids=resolved,
                quarantined_commit_keys=self.effect_ledger.frozen_quarantine(),
            )
            certificate = bind_complete_public_commit_certificate_v13(
                current,
                certificate,
            )
            certificates[candidate.bid] = certificate
            audit.append(
                {
                    "bid": candidate.bid,
                    "allowed": certificate.allowed,
                    "anchor_kind": certificate.grounding.anchor_kind,
                    "reason": certificate.reason,
                    "commit_fingerprint_version": (COMPLETE_PUBLIC_COMMIT_FINGERPRINT_VERSION_V13),
                }
            )
            if certificate.allowed:
                admitted.append(candidate.bid)
        envelope = assemble_action_envelope_v8(
            candidates=inventory.candidates,
            admitted_certificate_bids=admitted,
            active_transactions=active,
            completed_transactions=tuple(self.runtime.completed),
            resolved_semantic_bids=resolved,
        )
        return envelope, certificates, audit

    def result(self) -> dict[str, Any]:
        result = super().result()
        result["metrics"].update(complete_public_commit_metrics_v13(self))
        return result


__all__ = [
    "FullPactConfirmationDriverV13",
    "complete_public_commit_metrics_v13",
    "complete_public_no_effect_metrics_v12",
]
