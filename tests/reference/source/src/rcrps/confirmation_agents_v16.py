"""PACT-v16 confirmation driver with interrupt-clearance restoration."""

from __future__ import annotations

from typing import Any

from .confirmation_agents_v15 import FullPactConfirmationDriverV15
from .pact_controller_v8 import inverse_action_cost_v8
from .pact_controller_v16 import (
    ActiveRestoreClearanceReservationV16,
    FailClosedTransactionRuntimeV16,
)
from .typed_contracts_v4 import TransactionContractV4


def interrupt_clearance_metrics_v16(driver: Any) -> dict[str, int]:
    events = driver.runtime.events
    return {
        "interrupt_clearance_reservation_audits_v16": sum(
            event.get("type") == "interrupt_clearance_reservation_v16"
            for event in events
        ),
        "interrupt_clearance_reservation_passes_v16": sum(
            event.get("type") == "interrupt_clearance_reservation_v16"
            and event.get("allowed") is True
            for event in events
        ),
        "interrupt_clearance_projection_passes_v16": sum(
            event.get("type") == "interrupt_clearance_projection_v16"
            and event.get("passed") is True
            for event in events
        ),
        "interrupt_clearance_inverse_fallbacks_v16": sum(
            event.get("type") == "interrupt_clearance_projection_v16"
            and event.get("passed") is False
            for event in events
        ),
        "active_restore_clearance_reservation_audits_v16": sum(
            event.get("type") == "active_restore_clearance_reservation_v16"
            for event in events
        ),
        "active_restore_clearance_reservation_passes_v16": sum(
            event.get("type") == "active_restore_clearance_reservation_v16"
            and event.get("allowed") is True
            for event in events
        ),
        "active_restore_clearance_projection_passes_v16": sum(
            event.get("type") == "active_restore_clearance_projection_v16"
            and event.get("passed") is True
            for event in events
        ),
        "active_restore_clearance_inverse_fallbacks_v16": sum(
            event.get("type") == "active_restore_clearance_projection_v16"
            and event.get("passed") is False
            for event in events
        ),
        "proposal_clearance_restoration_attempts_v16": sum(
            event.get("type") == "interrupt_clearance_restoration_v16"
            and event.get("phase") == "rejected_forward"
            for event in events
        ),
        "proposal_clearance_restoration_passes_v16": sum(
            event.get("type") == "interrupt_clearance_restoration_v16"
            and event.get("phase") == "rejected_forward"
            and event.get("passed") is True
            for event in events
        ),
        "active_restore_clearance_restoration_attempts_v16": sum(
            event.get("type") == "interrupt_clearance_restoration_v16"
            and event.get("phase") == "active_restore"
            for event in events
        ),
        "active_restore_clearance_restoration_passes_v16": sum(
            event.get("type") == "interrupt_clearance_restoration_v16"
            and event.get("phase") == "active_restore"
            and event.get("passed") is True
            for event in events
        ),
        "interrupt_clearance_restoration_attempts_v16": sum(
            event.get("type") == "interrupt_clearance_restoration_v16"
            for event in events
        ),
        "interrupt_clearance_restoration_passes_v16": sum(
            event.get("type") == "interrupt_clearance_restoration_v16"
            and event.get("passed") is True
            for event in events
        ),
    }


class FullPactConfirmationDriverV16(FullPactConfirmationDriverV15):
    """Keep v15 grounding while adding the v16 interrupt-clearance branch."""

    method_id = "full_pact_v16"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.runtime = FailClosedTransactionRuntimeV16(
            self.executor,
            self.interrupt_repair_reservation,
            self.active_restore_clearance_reservation_v16,
        )

    def active_restore_clearance_reservation_v16(
        self,
        _contract: TransactionContractV4,
    ) -> ActiveRestoreClearanceReservationV16:
        # The restored transaction is already in runtime.active, so the
        # complete active reserve is summed exactly once.
        reservation = ActiveRestoreClearanceReservationV16(
            remaining_gui_actions=(
                int(self.budgets["maximum_gui_actions"])
                - len(self.executor.actions)
            ),
            clearance_actions=1,
            active_inverse_reserve=sum(
                inverse_action_cost_v8(transaction.contract)
                for transaction in self.runtime.active
            ),
        )
        self.audit(
            {
                "type": "active_restore_clearance_reservation_v16",
                "remaining_gui_actions": reservation.remaining_gui_actions,
                "clearance_actions": reservation.clearance_actions,
                "active_inverse_reserve": reservation.active_inverse_reserve,
                "allowed": reservation.allowed,
            }
        )
        return reservation

    def result(self) -> dict[str, Any]:
        result = super().result()
        result["metrics"].update(interrupt_clearance_metrics_v16(self))
        return result


__all__ = [
    "FullPactConfirmationDriverV16",
    "interrupt_clearance_metrics_v16",
]
