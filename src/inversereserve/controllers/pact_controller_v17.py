"""PACT-v17 runtime with effect-verified inverse completion.

An inverse action can report a transport-level timeout after its public effect
has already restored the contracted projection. V17 accepts such an inverse
only after the ordinary restoration verifier passes; otherwise it preserves
the fail-closed behavior. No retry or additional GUI action is hidden.
"""

from __future__ import annotations

from inversereserve.contracts.typed_contracts_v4 import public_compensator_bids
from inversereserve.controllers.pact_controller_v4 import ActiveTransactionV4, RestorationOutcomeV4
from inversereserve.controllers.pact_controller_v16 import FailClosedTransactionRuntimeV16
from inversereserve.observations.typed_observation import ContractCheck, SemanticSnapshot


class FailClosedTransactionRuntimeV17(FailClosedTransactionRuntimeV16):
    """Treat executor status as evidence, then decide from verified effects."""

    def _static_restore(
        self, transaction: ActiveTransactionV4, *, trigger: str, remove_active: bool
    ) -> RestorationOutcomeV4:
        contract = transaction.contract
        if contract.dynamic_inverse_class_token is not None:
            return super()._static_restore(transaction, trigger=trigger, remove_active=remove_active)
        current = self._live_public_snapshot_v15
        if (
            remove_active
            and current is not None
            and (contract.maximum_interrupt_repairs >= 1)
            and (len(public_compensator_bids(transaction.before, current, contract)) == 1)
        ):
            return super()._static_restore(transaction, trigger=trigger, remove_active=remove_active)
        final_snapshot, check, failure = self._execute_static_inverse_v17(transaction, trigger)
        if failure is not None:
            return failure
        if final_snapshot is None:
            reason = "registered static inverse sequence is empty"
            self._halt(reason)
            return RestorationOutcomeV4(True, False, reason, None, None)
        if check is None:
            check = self._check_restoration(transaction.before, final_snapshot, contract, trigger=trigger)
        if check is None or not check.passed:
            reason = self.halt_reason or "contract-footprint restoration failed"
            self._halt(reason)
            return RestorationOutcomeV4(True, False, reason, check, final_snapshot)
        if remove_active:
            if not self.active or self.active[-1] is not transaction:
                raise RuntimeError("restoration must pop the active transaction top")
            self.active.pop()
        self.completed.append({**transaction.planner_record(), "restored": True, "trigger": trigger})
        return RestorationOutcomeV4(True, True, check.reason, check, final_snapshot)

    def _execute_static_inverse_v17(
        self, transaction: ActiveTransactionV4, trigger: str
    ) -> tuple[SemanticSnapshot | None, ContractCheck | None, RestorationOutcomeV4 | None]:
        contract = transaction.contract
        final_snapshot = None
        check = None
        for action in contract.inverse_actions:
            result = self._execute(action, "typed_inverse")
            if result is None:
                return (
                    None,
                    None,
                    RestorationOutcomeV4(
                        True, False, self.halt_reason or "inverse executor failed", None, None
                    ),
                )
            final_snapshot = result.snapshot
            if result.terminal:
                reason = "inverse action terminated or truncated the environment"
                self._halt(reason)
                return (None, None, RestorationOutcomeV4(True, False, reason, None, final_snapshot))
            if result.action_error:
                check = self._check_restoration(
                    transaction.before,
                    final_snapshot,
                    contract,
                    trigger=f"{trigger}; inverse-error effect verification v17",
                )
                passed = check is not None and check.passed
                self._audit(
                    {
                        "type": "inverse_action_error_effect_check_v17",
                        "passed": passed,
                        "action_error": result.action_error,
                        "projection_kind": contract.projection_kind,
                        "reason": check.reason
                        if check is not None
                        else self.halt_reason or "restoration verifier failed",
                    }
                )
                if not passed:
                    reason = (
                        self.halt_reason or "inverse action errored and its public effect did not restore"
                    )
                    self._halt(reason)
                    return (None, None, RestorationOutcomeV4(True, False, reason, check, final_snapshot))
                break
        return (final_snapshot, check, None)


__all__ = ["FailClosedTransactionRuntimeV17"]
