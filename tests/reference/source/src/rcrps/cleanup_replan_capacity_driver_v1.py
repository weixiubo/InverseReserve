"""Demand-triggered cleanup-and-replan comparator for InverseReserve.

The comparator shares the complete stack-wide reserve, contracts, planner,
executor, and restoration verifier with InverseReserve. Its only policy
difference is that a requested transaction encountering live obligations first
restores the complete registered LIFO stack and then replans from the realized
public state. It never executes the stale pre-cleanup proposal.
"""

from __future__ import annotations

from typing import Any

from .capacity_reserve_drivers_v18 import StackWideCapacityDriverV18
from .pact_controller_v8 import inverse_action_cost_v8


DEMAND_CLEANUP_REPLAN_V1 = "demand_cleanup_replan_v1"
CLEANUP_REPLAN_POLICY_EVENT_V1 = "demand_cleanup_replan_policy_v1"


class _ReplanFromRealizedState(RuntimeError):
    """Internal control transfer after verified cleanup changes the state."""


class DemandCleanupReplanDriverV1(StackWideCapacityDriverV18):
    """Restore on a live transaction conflict, then re-enter the policy loop."""

    method_id = DEMAND_CLEANUP_REPLAN_V1

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.cleanup_replan_attempts = 0
        self.cleanup_replan_passes = 0
        self.cleanup_replan_failures = 0
        self.cleanup_replan_actions = 0

    def inverse_reserve(self, candidate: Any, decision: str) -> tuple[bool, int]:
        active_count = len(self.runtime.active)
        if decision != "transact" or active_count == 0:
            return super().inverse_reserve(candidate, decision)

        active_reserve = sum(
            inverse_action_cost_v8(transaction.contract)
            for transaction in self.runtime.active
        )
        actions_before = len(self.executor.actions)
        self.cleanup_replan_attempts += 1
        self.inverse_reservation_audits += 1
        self.audit(
            {
                "type": CLEANUP_REPLAN_POLICY_EVENT_V1,
                "phase": "request",
                "policy": "restore_complete_lifo_stack_then_replan",
                "decision": decision,
                "bid": candidate.bid,
                "active_obligations_before_proposal": active_count,
                "registered_active_inverse_cost": active_reserve,
                "stale_proposal_execution_allowed": False,
            }
        )

        self.cleanup_runtime(self.runtime)
        actions_spent = len(self.executor.actions) - actions_before
        cleared = not self.runtime.active and not self.runtime.halted
        self.cleanup_replan_actions += actions_spent
        self.cleanup_replan_passes += int(cleared)
        self.cleanup_replan_failures += int(not cleared)
        self.audit(
            {
                "type": CLEANUP_REPLAN_POLICY_EVENT_V1,
                "phase": "outcome",
                "policy": "restore_complete_lifo_stack_then_replan",
                "decision": decision,
                "bid": candidate.bid,
                "active_obligations_before_proposal": active_count,
                "active_obligations_after_cleanup": len(self.runtime.active),
                "cleanup_gui_actions": actions_spent,
                "cleanup_passed": cleared,
                "replan_from_realized_state": cleared,
                "stale_proposal_executed": False,
            }
        )
        if cleared:
            raise _ReplanFromRealizedState
        return False, sum(
            inverse_action_cost_v8(transaction.contract)
            for transaction in self.runtime.active
        )

    def run_policy(self) -> None:
        while not self.executor.done and self.within_budget():
            try:
                super().run_policy()
            except _ReplanFromRealizedState:
                continue
            return

    def result(self) -> dict[str, Any]:
        result = super().result()
        result["metrics"].update(
            {
                "cleanup_replan_attempts": self.cleanup_replan_attempts,
                "cleanup_replan_passes": self.cleanup_replan_passes,
                "cleanup_replan_failures": self.cleanup_replan_failures,
                "cleanup_replan_actions": self.cleanup_replan_actions,
            }
        )
        return result


__all__ = [
    "CLEANUP_REPLAN_POLICY_EVENT_V1",
    "DEMAND_CLEANUP_REPLAN_V1",
    "DemandCleanupReplanDriverV1",
]
