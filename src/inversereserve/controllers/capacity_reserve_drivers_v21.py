"""PACT-v21 controls with a planner-certified one-call terminal reserve."""

from __future__ import annotations

from typing import Any

from inversereserve.controllers.capacity_reserve_drivers_v18 import RESERVATION_EVENT_V18
from inversereserve.controllers.capacity_reserve_drivers_v20 import (
    SingleActiveObligationDriverV20,
    TopCleanupReplanDriverV20,
)
from inversereserve.controllers.pact_controller_v8 import inverse_action_cost_v8
from inversereserve.core.recovery_capacity import remaining_after_action as _remaining_capacity_after_proposal

TASK_RESERVE_TOP_CLEANUP_V21 = "task_reserve_top_cleanup_v21"
TASK_RESERVE_SINGLE_ACTIVE_V21 = "task_reserve_single_active_v21"
TASK_RESERVE_V21 = 1
TASK_RESERVE_SOURCE_V21 = "structured_goal_terminal_intent_one_call"
RUNTIME_VERSION_V21 = "PACT-v21-task-reserve"


class _OneCallTaskReserveMixinV21:
    """Add ``h=1`` only while a reversible prerequisite is dispatched.

    The reserved call is the public goal contract's eventual terminal action.
    It is consumed at a commit decision, so commit itself uses ``h=0``.
    """

    stack_wide = True

    def _capacity_reserve_v20(self, candidate: Any, decision: str) -> tuple[bool, int]:
        active_reserve = sum(
            inverse_action_cost_v8(transaction.contract) for transaction in self.runtime.active
        )
        proposal_reserve = 0
        if decision == "transact":
            contract = self.inventory().contract_by_bid.get(candidate.bid)
            if contract is None:
                return False, active_reserve + TASK_RESERVE_V21
            proposal_reserve = inverse_action_cost_v8(contract)
        stack_wide_reserve = active_reserve + proposal_reserve
        applied_inverse_reserve = stack_wide_reserve if self.stack_wide else proposal_reserve
        applied_task_reserve = TASK_RESERVE_V21 if decision == "transact" else 0
        applied_total_reserve = applied_inverse_reserve + applied_task_reserve
        remaining_after_action = _remaining_capacity_after_proposal(
            self.budgets["maximum_gui_actions"], len(self.executor.actions)
        )
        allowed = remaining_after_action >= applied_total_reserve
        self.inverse_reservation_audits += 1
        self.audit(
            {
                "type": RESERVATION_EVENT_V18,
                "reservation_rule": "stack_wide",
                "task_reserve_rule": "structured_goal_one_call",
                "decision": decision,
                "bid": candidate.bid,
                "registered_active_inverse_cost": active_reserve,
                "proposal_inverse_cost": proposal_reserve,
                "stack_wide_required_inverse_cost": stack_wide_reserve,
                "applied_inverse_reserve": applied_inverse_reserve,
                "applied_task_reserve": applied_task_reserve,
                "applied_total_reserve": applied_total_reserve,
                "task_reserve_source": TASK_RESERVE_SOURCE_V21,
                "remaining_after_action": remaining_after_action,
                "inverse_only_allowed": (remaining_after_action >= applied_inverse_reserve),
                "allowed": allowed,
                "runtime_version": RUNTIME_VERSION_V21,
            }
        )
        return allowed, applied_total_reserve


class TaskReserveTopCleanupDriverV21(
    _OneCallTaskReserveMixinV21,
    TopCleanupReplanDriverV20,
):
    """Opportunity-preserving policy with the shared terminal reserve."""

    method_id = TASK_RESERVE_TOP_CLEANUP_V21


class TaskReserveSingleActiveDriverV21(
    _OneCallTaskReserveMixinV21,
    SingleActiveObligationDriverV20,
):
    """Depth-one sound control with the identical terminal reserve."""

    method_id = TASK_RESERVE_SINGLE_ACTIVE_V21


__all__ = [
    "RUNTIME_VERSION_V21",
    "TASK_RESERVE_SINGLE_ACTIVE_V21",
    "TASK_RESERVE_SOURCE_V21",
    "TASK_RESERVE_TOP_CLEANUP_V21",
    "TASK_RESERVE_V21",
    "TaskReserveSingleActiveDriverV21",
    "TaskReserveTopCleanupDriverV21",
]
