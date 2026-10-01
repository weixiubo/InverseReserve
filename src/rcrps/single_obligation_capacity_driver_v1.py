"""Stronger safe comparator for the InverseReserve v18 runtime."""

from __future__ import annotations

from typing import Any

from .capacity_reserve_drivers_v18 import StackWideCapacityDriverV18
from .pact_controller_v8 import inverse_action_cost_v8


SINGLE_ACTIVE_OBLIGATION_V1 = "single_active_obligation_v1"
SINGLE_OBLIGATION_POLICY_EVENT_V1 = "single_obligation_policy_v1"


class SingleActiveObligationDriverV1(StackWideCapacityDriverV18):
    """Permit serial work while keeping at most one unresolved transaction."""

    method_id = SINGLE_ACTIVE_OBLIGATION_V1

    def inverse_reserve(self, candidate: Any, decision: str) -> tuple[bool, int]:
        active_count = len(self.runtime.active)
        if decision == "transact" and active_count >= 1:
            active_reserve = sum(
                inverse_action_cost_v8(transaction.contract)
                for transaction in self.runtime.active
            )
            self.inverse_reservation_audits += 1
            self.audit(
                {
                    "type": SINGLE_OBLIGATION_POLICY_EVENT_V1,
                    "policy": "at_most_one_active_obligation",
                    "decision": decision,
                    "bid": candidate.bid,
                    "active_obligations_before_proposal": active_count,
                    "registered_active_inverse_cost": active_reserve,
                    "allowed": False,
                    "delegated_to_stack_wide_reserve": False,
                    "reason": "second active transaction is forbidden",
                }
            )
            return False, active_reserve

        allowed, applied_reserve = super().inverse_reserve(candidate, decision)
        self.audit(
            {
                "type": SINGLE_OBLIGATION_POLICY_EVENT_V1,
                "policy": "at_most_one_active_obligation",
                "decision": decision,
                "bid": candidate.bid,
                "active_obligations_before_proposal": active_count,
                "applied_inverse_reserve": applied_reserve,
                "allowed": allowed,
                "delegated_to_stack_wide_reserve": True,
            }
        )
        return allowed, applied_reserve


__all__ = [
    "SINGLE_ACTIVE_OBLIGATION_V1",
    "SINGLE_OBLIGATION_POLICY_EVENT_V1",
    "SingleActiveObligationDriverV1",
]
