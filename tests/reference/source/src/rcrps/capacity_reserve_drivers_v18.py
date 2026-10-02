"""Matched PACT-v18 drivers that differ only in inverse-reserve scope."""

from __future__ import annotations

from .recovery_capacity import remaining_after_action as _remaining_capacity_after_proposal

from typing import Any

from .confirmation_agents_v18 import FullPactConfirmationDriverV18
from .pact_controller_v8 import inverse_action_cost_v8


STACK_WIDE_V18 = "stack_wide_reserve_v18"
PROPOSAL_LOCAL_V18 = "proposal_local_reserve_v18"
ONE_STEP_RESTORE_V18 = "one_step_then_restore_v18"
ALWAYS_ABSTAIN = "always_abstain"
RESERVATION_EVENT_V18 = "cross_family_reservation_v3"
ONE_STEP_CAP_EVENT_V18 = "one_step_restore_cap_v18"


class CapacityReserveDriverV18(FullPactConfirmationDriverV18):
    """Apply one explicit reserve-accounting switch to the same v18 runtime."""

    stack_wide = True

    def inverse_reserve(self, candidate: Any, decision: str) -> tuple[bool, int]:
        active_reserve = sum(
            inverse_action_cost_v8(transaction.contract)
            for transaction in self.runtime.active
        )
        proposal_reserve = 0
        if decision == "transact":
            contract = self.inventory().contract_by_bid.get(candidate.bid)
            if contract is None:
                return False, active_reserve
            proposal_reserve = inverse_action_cost_v8(contract)
        stack_wide_reserve = active_reserve + proposal_reserve
        applied_reserve = stack_wide_reserve if self.stack_wide else proposal_reserve
        remaining_after_action = _remaining_capacity_after_proposal(self.budgets["maximum_gui_actions"], len(self.executor.actions))
        allowed = remaining_after_action >= applied_reserve
        self.inverse_reservation_audits += 1
        self.audit(
            {
                "type": RESERVATION_EVENT_V18,
                "reservation_rule": (
                    "stack_wide" if self.stack_wide else "proposal_local"
                ),
                "decision": decision,
                "bid": candidate.bid,
                "registered_active_inverse_cost": active_reserve,
                "proposal_inverse_cost": proposal_reserve,
                "stack_wide_required_inverse_cost": stack_wide_reserve,
                "applied_inverse_reserve": applied_reserve,
                "remaining_after_action": remaining_after_action,
                "allowed": allowed,
            }
        )
        return allowed, applied_reserve


class StackWideCapacityDriverV18(CapacityReserveDriverV18):
    method_id = STACK_WIDE_V18
    stack_wide = True


class ProposalLocalCapacityDriverV18(CapacityReserveDriverV18):
    method_id = PROPOSAL_LOCAL_V18
    stack_wide = False


class OneStepRestoreCapacityDriverV18(StackWideCapacityDriverV18):
    """Execute at most one forward action, then invoke ordinary restoration.

    This is a deliberately strong safe baseline: it uses the same grounded
    envelope, planner, typed transactions, and stack-wide inverse accounting
    as InverseReserve. Its only additional policy restriction is a depth-one
    forward-action cap. Cleanup remains the inherited verified runtime path.
    """

    method_id = ONE_STEP_RESTORE_V18

    def inverse_reserve(self, candidate: Any, decision: str) -> tuple[bool, int]:
        if len(self.executor.actions) < 1:
            return super().inverse_reserve(candidate, decision)
        active_reserve = sum(
            inverse_action_cost_v8(transaction.contract)
            for transaction in self.runtime.active
        )
        self.inverse_reservation_audits += 1
        self.audit(
            {
                "type": ONE_STEP_CAP_EVENT_V18,
                "decision": decision,
                "bid": candidate.bid,
                "forward_actions_already_executed": len(self.executor.actions),
                "registered_active_inverse_cost": active_reserve,
                "allowed": False,
                "reason": "predeclared depth-one forward-action cap",
            }
        )
        return False, active_reserve


class AlwaysAbstainCapacityDriverV18(FullPactConfirmationDriverV18):
    method_id = ALWAYS_ABSTAIN

    def run_policy(self) -> None:
        self.method_failure = "predeclared always-abstain baseline"


__all__ = [
    "ALWAYS_ABSTAIN",
    "ONE_STEP_CAP_EVENT_V18",
    "ONE_STEP_RESTORE_V18",
    "PROPOSAL_LOCAL_V18",
    "RESERVATION_EVENT_V18",
    "STACK_WIDE_V18",
    "AlwaysAbstainCapacityDriverV18",
    "CapacityReserveDriverV18",
    "OneStepRestoreCapacityDriverV18",
    "ProposalLocalCapacityDriverV18",
    "StackWideCapacityDriverV18",
]
