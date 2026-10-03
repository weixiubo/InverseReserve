"""Matched PACT-v19 drivers differing only in inverse-reserve scope."""

from __future__ import annotations

from typing import Any

from inversereserve.controllers.capacity_reserve_drivers_v18 import RESERVATION_EVENT_V18
from inversereserve.controllers.confirmation_agents_v19 import FullPactConfirmationDriverV19
from inversereserve.controllers.pact_controller_v8 import inverse_action_cost_v8
from inversereserve.core.recovery_capacity import remaining_after_action as _remaining_capacity_after_proposal

STACK_WIDE_V19 = "stack_wide_reserve_v19"
PROPOSAL_LOCAL_V19 = "proposal_local_reserve_v19"
SINGLE_ACTIVE_OBLIGATION_V19 = "single_active_obligation_v19"
SINGLE_OBLIGATION_POLICY_EVENT_V19 = "single_obligation_policy_v19"


class CapacityReserveDriverV19(FullPactConfirmationDriverV19):
    stack_wide = True

    def inverse_reserve(self, candidate: Any, decision: str) -> tuple[bool, int]:
        active_reserve = sum(
            inverse_action_cost_v8(transaction.contract) for transaction in self.runtime.active
        )
        proposal_reserve = 0
        if decision == "transact":
            contract = self.inventory().contract_by_bid.get(candidate.bid)
            if contract is None:
                return False, active_reserve
            proposal_reserve = inverse_action_cost_v8(contract)
        stack_wide_reserve = active_reserve + proposal_reserve
        applied_reserve = stack_wide_reserve if self.stack_wide else proposal_reserve
        remaining_after_action = _remaining_capacity_after_proposal(
            self.budgets["maximum_gui_actions"], len(self.executor.actions)
        )
        allowed = remaining_after_action >= applied_reserve
        self.inverse_reservation_audits += 1
        self.audit(
            {
                "type": RESERVATION_EVENT_V18,
                "reservation_rule": ("stack_wide" if self.stack_wide else "proposal_local"),
                "decision": decision,
                "bid": candidate.bid,
                "registered_active_inverse_cost": active_reserve,
                "proposal_inverse_cost": proposal_reserve,
                "stack_wide_required_inverse_cost": stack_wide_reserve,
                "applied_inverse_reserve": applied_reserve,
                "remaining_after_action": remaining_after_action,
                "allowed": allowed,
                "runtime_version": "PACT-v19",
            }
        )
        return allowed, applied_reserve


class StackWideCapacityDriverV19(CapacityReserveDriverV19):
    method_id = STACK_WIDE_V19
    stack_wide = True


class ProposalLocalCapacityDriverV19(CapacityReserveDriverV19):
    method_id = PROPOSAL_LOCAL_V19
    stack_wide = False


class SingleActiveObligationDriverV19(StackWideCapacityDriverV19):
    """Safe depth-one control sharing every PACT-v19 mechanism."""

    method_id = SINGLE_ACTIVE_OBLIGATION_V19

    def inverse_reserve(self, candidate: Any, decision: str) -> tuple[bool, int]:
        active_count = len(self.runtime.active)
        if decision == "transact" and active_count >= 1:
            active_reserve = sum(
                inverse_action_cost_v8(transaction.contract) for transaction in self.runtime.active
            )
            self.inverse_reservation_audits += 1
            self.audit(
                {
                    "type": SINGLE_OBLIGATION_POLICY_EVENT_V19,
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
        allowed, reserve = super().inverse_reserve(candidate, decision)
        self.audit(
            {
                "type": SINGLE_OBLIGATION_POLICY_EVENT_V19,
                "policy": "at_most_one_active_obligation",
                "decision": decision,
                "bid": candidate.bid,
                "active_obligations_before_proposal": active_count,
                "applied_inverse_reserve": reserve,
                "allowed": allowed,
                "delegated_to_stack_wide_reserve": True,
            }
        )
        return allowed, reserve


__all__ = [
    "PROPOSAL_LOCAL_V19",
    "SINGLE_ACTIVE_OBLIGATION_V19",
    "SINGLE_OBLIGATION_POLICY_EVENT_V19",
    "STACK_WIDE_V19",
    "CapacityReserveDriverV19",
    "ProposalLocalCapacityDriverV19",
    "SingleActiveObligationDriverV19",
    "StackWideCapacityDriverV19",
]
