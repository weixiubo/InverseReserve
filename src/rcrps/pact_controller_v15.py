"""PACT-v15 runtime with live public grounding for dynamic LIFO inverses."""

from __future__ import annotations

from dataclasses import replace

from .pact_controller_v4 import (
    ActionExecutionV4,
    ActiveTransactionV4,
    RestorationOutcomeV4,
)
from .pact_controller_v13 import FailClosedTransactionRuntimeV13
from .transaction_actions_v4 import ContractActionV4
from .typed_observation import SemanticSnapshot


class FailClosedTransactionRuntimeV15(FailClosedTransactionRuntimeV13):
    """Resolve an already-registered dynamic inverse against live public state."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._live_public_snapshot_v15: SemanticSnapshot | None = None

    def _execute(
        self,
        action: ContractActionV4,
        role: str,
    ) -> ActionExecutionV4 | None:
        result = super()._execute(action, role)
        if result is not None:
            self._live_public_snapshot_v15 = result.snapshot
        return result

    def _static_restore(
        self,
        transaction: ActiveTransactionV4,
        *,
        trigger: str,
        remove_active: bool,
    ) -> RestorationOutcomeV4:
        token = transaction.contract.dynamic_inverse_class_token
        if token is not None:
            current = self._live_public_snapshot_v15
            if current is None:
                reason = "live public snapshot is absent for dynamic inverse grounding"
                self._halt(reason)
                return RestorationOutcomeV4(
                    True,
                    False,
                    reason,
                    None,
                    transaction.after,
                )
            refreshed = replace(transaction, after=current)
            if remove_active:
                if not self.active or self.active[-1] is not transaction:
                    raise RuntimeError(
                        "live dynamic inverse must refresh the active transaction top"
                    )
                self.active[-1] = refreshed
            transaction = refreshed
            self._audit(
                {
                    "type": "live_dynamic_inverse_grounding_v15",
                    "class_token": token,
                    "snapshot_scope": "current_post_action_public_snapshot",
                }
            )
        return super()._static_restore(
            transaction,
            trigger=trigger,
            remove_active=remove_active,
        )


__all__ = ["FailClosedTransactionRuntimeV15"]
