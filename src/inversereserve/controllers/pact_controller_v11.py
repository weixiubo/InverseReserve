"""PACT-v11 runtime with a complete-public-no-effect inverse guard."""

from __future__ import annotations

from dataclasses import asdict

from inversereserve.controllers.pact_controller_v4 import ActiveTransactionV4, RestorationOutcomeV4
from inversereserve.controllers.pact_controller_v10 import FailClosedTransactionRuntimeV10
from inversereserve.observations.typed_observation import ContractCheck, semantic_delta


class FailClosedTransactionRuntimeV11(FailClosedTransactionRuntimeV10):
    """Skip a rejected proposal's inverse only after complete-public equality.

    V10 executes a registered inverse after every changed-or-rejected forward.
    That is correct when a public effect occurred, but a toggle-like inverse can
    manufacture a new mutation when the forward had no effect at all.  V11
    restores the complete-public no-effect certificate that existed in the v3
    runtime: equality of the full semantic fingerprint discharges a rejected
    forward or retry without issuing its inverse.  Cleanup of an admitted
    transaction and any public difference retain the exact v10 inverse,
    reserve, repair, and fail-closed behavior.
    """

    def _unchanged_public_restoration(
        self,
        transaction: ActiveTransactionV4,
        *,
        trigger: str,
        remove_active: bool,
    ) -> RestorationOutcomeV4 | None:
        try:
            unchanged = transaction.before.semantic_fingerprint() == transaction.after.semantic_fingerprint()
        except Exception as error:
            reason = (
                f"pre-inverse public no-effect verifier raised an exception: {type(error).__name__}: {error}"
            )
            self._audit(
                {
                    "type": "verification_exception",
                    "context": "pre-inverse complete-public no-effect certificate",
                    "reason": reason,
                }
            )
            self._halt(reason)
            return RestorationOutcomeV4(
                False,
                False,
                reason,
                None,
                transaction.after,
            )
        if not unchanged:
            return None

        delta = semantic_delta(transaction.before, transaction.after)
        if delta.changed:
            raise AssertionError("equal complete public fingerprints produced a nonempty delta")
        check = ContractCheck(
            True,
            "complete public semantic snapshot was already unchanged",
            delta,
        )
        self._audit(
            {
                "type": "restoration",
                "trigger": trigger,
                "projection_kind": transaction.contract.projection_kind,
                "certificate_scope": "complete_public_snapshot",
                "passed": True,
                "reason": check.reason,
                "global_delta": asdict(delta),
                "global_delta_empty": True,
                "inverse_skipped": True,
                "attempted": False,
            }
        )
        if remove_active:
            if not self.active or self.active[-1] is not transaction:
                raise RuntimeError("restoration must pop the active transaction top")
            self.active.pop()
        self.completed.append(
            {
                **transaction.planner_record(),
                "restored": True,
                "trigger": trigger,
                "inverse_skipped": True,
            }
        )
        return RestorationOutcomeV4(
            False,
            True,
            "inverse skipped because the complete public state was already unchanged",
            check,
            transaction.after,
        )

    def _static_restore(
        self,
        transaction: ActiveTransactionV4,
        *,
        trigger: str,
        remove_active: bool,
    ) -> RestorationOutcomeV4:
        if remove_active:
            return super()._static_restore(
                transaction,
                trigger=trigger,
                remove_active=True,
            )
        unchanged = self._unchanged_public_restoration(
            transaction,
            trigger=trigger,
            remove_active=remove_active,
        )
        if unchanged is not None:
            return unchanged
        return super()._static_restore(
            transaction,
            trigger=trigger,
            remove_active=remove_active,
        )
