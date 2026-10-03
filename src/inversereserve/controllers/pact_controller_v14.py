"""PACT-v14 runtime support for fresh bounded autocomplete probes."""

from __future__ import annotations

from inversereserve.autocomplete_population_resolution_v14 import PopulationNavigationCertificateV14
from inversereserve.contracts.pact_grounding_v4 import stack_signature_v4
from inversereserve.contracts.transaction_actions_v4 import ContractActionV4
from inversereserve.controllers.pact_controller_v4 import CommitOutcomeV4
from inversereserve.controllers.pact_controller_v12 import complete_public_fingerprint_v12
from inversereserve.controllers.pact_controller_v13 import FailClosedTransactionRuntimeV13
from inversereserve.observations.typed_observation import SemanticSnapshot


class FailClosedTransactionRuntimeV14(FailClosedTransactionRuntimeV13):
    """Execute only one freshly bound ArrowDown probe at a time."""

    def execute_population_probe(
        self, *, current: SemanticSnapshot, certificate: PopulationNavigationCertificateV14
    ) -> CommitOutcomeV4:
        self._require_live()
        action = certificate.certified_action
        if not certificate.allowed or action is None:
            reason = "population probe certificate was not admitted"
            self._audit({"type": "population_probe_rejected_v14", "reason": reason})
            return CommitOutcomeV4(False, reason, None, False)
        if not all(
            (
                isinstance(value, str) and value
                for value in (certificate.field_bid, certificate.surface_bid, certificate.target_bid)
            )
        ):
            reason = "population probe certificate lacks public field, surface, or target identity"
            self._audit({"type": "population_probe_rejected_v14", "reason": reason})
            return CommitOutcomeV4(False, reason, None, False)
        expected_action = ContractActionV4("press", certificate.field_bid, "ArrowDown")
        if action != expected_action:
            reason = "population probe differs from the certified field-scoped ArrowDown"
            self._audit({"type": "population_probe_rejected_v14", "reason": reason})
            return CommitOutcomeV4(False, reason, None, False)
        rejection = self._verify_population_probe_binding(current, certificate)
        if rejection is not None:
            return rejection
        result = self._execute(action, "autocomplete_population_probe_v14")
        if result is None:
            return CommitOutcomeV4(False, self.halt_reason or "population probe executor failed", None, True)
        if result.terminal:
            reason = "autocomplete population probe terminated or truncated the environment"
            self._halt(reason)
            return CommitOutcomeV4(False, reason, result, True)
        if result.action_error:
            reason = f"population probe reported an error: {result.action_error}"
            self._halt(reason)
            return CommitOutcomeV4(False, reason, result, True)
        return CommitOutcomeV4(
            True, "fresh complete-public certificate authorized one bounded ArrowDown probe", result, False
        )

    def _verify_population_probe_binding(
        self, current: SemanticSnapshot, certificate: PopulationNavigationCertificateV14
    ) -> CommitOutcomeV4 | None:
        try:
            fingerprint = complete_public_fingerprint_v12(current)
        except Exception as error:
            reason = f"population probe observation fingerprint failed: {type(error).__name__}"
            self._audit({"type": "population_probe_rejected_v14", "reason": reason})
            self._halt(reason)
            return CommitOutcomeV4(False, reason, None, True)
        observation_matches = fingerprint == certificate.observation_fingerprint
        stack_matches = stack_signature_v4(self.active) == certificate.active_stack_signature
        top_matches = bool(
            self.active
            and self.active[-1].contract.kind == "autocomplete_query"
            and (self.active[-1].contract.semantic_bid == certificate.field_bid)
        )
        self._audit(
            {
                "type": "complete_public_population_probe_check_v14",
                "observation_matches": observation_matches,
                "stack_matches": stack_matches,
                "top_autocomplete_matches": top_matches,
                "population_item_count": len(certificate.population_signature),
                "field_bid": certificate.field_bid,
                "surface_bid": certificate.surface_bid,
                "target_bid": certificate.target_bid,
                "passed": observation_matches and stack_matches and top_matches,
            }
        )
        if not observation_matches:
            reason = "population probe certificate is stale for the public observation"
            self._audit({"type": "population_probe_rejected_v14", "reason": reason})
            return CommitOutcomeV4(False, reason, None, False)
        if not stack_matches or not top_matches:
            reason = "population probe certificate is stale for the active transaction stack"
            self._audit({"type": "population_probe_rejected_v14", "reason": reason})
            return CommitOutcomeV4(False, reason, None, False)
        return None


__all__ = ["FailClosedTransactionRuntimeV14"]
