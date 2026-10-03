"""PACT-v10 confirmation driver with solvent interrupt repair."""

from __future__ import annotations

from typing import Any

from .confirmation_agents_v9 import FullPactConfirmationDriverV9
from .pact_controller_v8 import inverse_action_cost_v8
from .pact_controller_v10 import (
    FailClosedTransactionRuntimeV10,
    InterruptRepairReservationV10,
    interrupt_repair_action_cost_v10,
)
from .typed_contracts_v4 import TransactionContractV4


class RecoverySolventRepairDriverMixinV10:
    """Install and report the v10 repair-reservation policy on a v9 driver."""

    def _initialize_recovery_solvent_repair_v10(self) -> None:
        self.interrupt_repair_reservation_audits = 0
        self.interrupt_repair_reservation_fallbacks = 0
        self.runtime = FailClosedTransactionRuntimeV10(
            self.executor,
            self.interrupt_repair_reservation,
        )

    def interrupt_repair_reservation(
        self, contract: TransactionContractV4
    ) -> InterruptRepairReservationV10:
        registered_inverse_reserve = sum(
            inverse_action_cost_v8(transaction.contract)
            for transaction in self.runtime.active
        ) + inverse_action_cost_v8(contract)
        reservation = InterruptRepairReservationV10(
            remaining_gui_actions=(
                int(self.budgets["maximum_gui_actions"])
                - len(self.executor.actions)
            ),
            repair_pair_actions=interrupt_repair_action_cost_v10(contract),
            registered_inverse_reserve=registered_inverse_reserve,
        )
        self.interrupt_repair_reservation_audits += 1
        self.interrupt_repair_reservation_fallbacks += int(not reservation.allowed)
        self.audit(
            {
                "type": "interrupt_repair_reservation_v10",
                "remaining_gui_actions": reservation.remaining_gui_actions,
                "repair_pair_actions": reservation.repair_pair_actions,
                "registered_inverse_reserve": (
                    reservation.registered_inverse_reserve
                ),
                "allowed": reservation.allowed,
            }
        )
        return reservation

    def result(self) -> dict[str, Any]:
        result = super().result()
        inverse_fallbacks = sum(
            event.get("type") == "compensator_grounding"
            and event.get("policy") == "inverse"
            for event in self.runtime.events
        )
        result["metrics"].update(
            {
                "interrupt_repair_reservation_audits": (
                    self.interrupt_repair_reservation_audits
                ),
                "interrupt_repair_reservation_fallbacks": (
                    self.interrupt_repair_reservation_fallbacks
                ),
                "interrupt_repair_inverse_fallbacks": inverse_fallbacks,
            }
        )
        return result


class FullPactConfirmationDriverV10(
    RecoverySolventRepairDriverMixinV10,
    FullPactConfirmationDriverV9,
):
    """Full PACT with a separate budget guard for compensator-plus-retry."""

    method_id = "full_pact_v10"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._initialize_recovery_solvent_repair_v10()
