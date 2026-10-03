"""PACT-v13 runtime with complete-public terminal-certificate freshness."""

from __future__ import annotations

from dataclasses import replace

from inversereserve.contracts.pact_grounding_v4 import CommitCertificateV4, stack_signature_v4
from inversereserve.contracts.transaction_actions_v4 import ContractActionV4
from inversereserve.controllers.pact_controller_v4 import CommitOutcomeV4
from inversereserve.controllers.pact_controller_v12 import (
    COMPLETE_PUBLIC_FINGERPRINT_VERSION_V12,
    FailClosedTransactionRuntimeV12,
    complete_public_fingerprint_v12,
)
from inversereserve.observations.typed_observation import SemanticSnapshot

COMPLETE_PUBLIC_COMMIT_FINGERPRINT_VERSION_V13 = f"{COMPLETE_PUBLIC_FINGERPRINT_VERSION_V12}-commit-v13"


def bind_complete_public_commit_certificate_v13(
    current: SemanticSnapshot,
    certificate: CommitCertificateV4,
) -> CommitCertificateV4:
    """Replace an admitted certificate's projected binding with all public fields."""

    if not certificate.allowed:
        return certificate
    try:
        fingerprint = complete_public_fingerprint_v12(current)
    except Exception as error:
        return CommitCertificateV4(
            False,
            f"complete-public commit fingerprint failed: {type(error).__name__}: {error}",
            certificate.grounding,
        )
    return replace(certificate, observation_fingerprint=fingerprint)


class FailClosedTransactionRuntimeV13(FailClosedTransactionRuntimeV12):
    """Recheck every retained public field before a certified terminal action."""

    def commit(
        self,
        *,
        current: SemanticSnapshot,
        action: ContractActionV4,
        certificate: CommitCertificateV4,
    ) -> CommitOutcomeV4:
        self._require_live()
        if not certificate.allowed or certificate.certified_action is None:
            reason = "commit certificate was not admitted"
            self._audit({"type": "commit_rejected", "reason": reason})
            return CommitOutcomeV4(False, reason, None, False)
        try:
            fingerprint = complete_public_fingerprint_v12(current)
        except Exception as error:
            reason = f"commit observation fingerprint failed: {type(error).__name__}"
            self._audit({"type": "commit_rejected", "reason": reason})
            self._halt(reason)
            return CommitOutcomeV4(False, reason, None, True)
        observation_matches = fingerprint == certificate.observation_fingerprint
        self._audit(
            {
                "type": "complete_public_commit_observation_check_v13",
                "passed": observation_matches,
                "fingerprint_version": (COMPLETE_PUBLIC_COMMIT_FINGERPRINT_VERSION_V13),
                "field_scope": "all_retained_semantic_snapshot_fields",
            }
        )
        if not observation_matches:
            reason = "commit certificate is stale for the current public observation"
            self._audit({"type": "commit_rejected", "reason": reason})
            return CommitOutcomeV4(False, reason, None, False)
        if stack_signature_v4(self.active) != certificate.active_stack_signature:
            reason = "commit certificate is stale for the active transaction stack"
            self._audit({"type": "commit_rejected", "reason": reason})
            return CommitOutcomeV4(False, reason, None, False)
        if action != certificate.certified_action:
            reason = "commit action differs from the certified operation or argument"
            self._audit({"type": "commit_rejected", "reason": reason})
            return CommitOutcomeV4(False, reason, None, False)
        result = self._execute(action, "commit")
        if result is None:
            return CommitOutcomeV4(
                False,
                self.halt_reason or "commit executor failed",
                None,
                True,
            )
        if result.action_error:
            reason = f"commit action reported an error: {result.action_error}"
            self._halt(reason)
            return CommitOutcomeV4(False, reason, result, True)
        return CommitOutcomeV4(
            True,
            "fresh complete-public certificate authorized the exact commit action",
            result,
            False,
        )
