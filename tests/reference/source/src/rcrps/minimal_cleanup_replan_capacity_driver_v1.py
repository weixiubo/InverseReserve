"""Reserve-guided minimal LIFO cleanup and replanning.

This controller keeps every capacity-feasible active obligation.  Only when the
exact stack-wide reserve rejects a requested transaction does it restore one
top obligation, discard the now-stale proposal, and replan from realized public
state.  Thus each state-changing intervention is the smallest legal LIFO
prefix, unlike unconditional complete-stack cleanup.
"""

from __future__ import annotations

from typing import Any

from .capacity_reserve_drivers_v18 import StackWideCapacityDriverV18
from .confirmation_agents_v7 import _restoration_record
from .pact_controller_v8 import inverse_action_cost_v8


MINIMAL_CLEANUP_REPLAN_V1 = "minimal_lifo_cleanup_replan_v1"
MINIMAL_CLEANUP_POLICY_EVENT_V1 = "minimal_lifo_cleanup_policy_v1"


class _ReplanFromPartiallyRestoredState(RuntimeError):
    """Internal control transfer after one verified inverse changes the state."""


class MinimalCleanupReplanDriverV1(StackWideCapacityDriverV18):
    """Preserve feasible work; on a capacity conflict, restore one LIFO item."""

    method_id = MINIMAL_CLEANUP_REPLAN_V1

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.minimal_cleanup_attempts = 0
        self.minimal_cleanup_passes = 0
        self.minimal_cleanup_failures = 0
        self.minimal_cleanup_actions = 0

    def inverse_reserve(self, candidate: Any, decision: str) -> tuple[bool, int]:
        contract = (
            self.inventory().contract_by_bid.get(candidate.bid)
            if decision == "transact"
            else None
        )
        allowed, reserve = super().inverse_reserve(candidate, decision)
        active_before = len(self.runtime.active)
        if (
            allowed
            or decision != "transact"
            or contract is None
            or active_before == 0
        ):
            return allowed, reserve

        actions_before = len(self.executor.actions)
        registered_before = sum(
            inverse_action_cost_v8(transaction.contract)
            for transaction in self.runtime.active
        )
        self.minimal_cleanup_attempts += 1
        self.audit(
            {
                "type": MINIMAL_CLEANUP_POLICY_EVENT_V1,
                "phase": "request",
                "policy": "restore_one_top_obligation_then_replan",
                "decision": decision,
                "bid": candidate.bid,
                "active_obligations_before_proposal": active_before,
                "registered_active_inverse_cost": registered_before,
                "blocked_stack_wide_reserve": reserve,
                "stale_proposal_execution_allowed": False,
            }
        )
        outcome = self.runtime.restore_top(
            "reserve-guided minimal cleanup before replanning"
        )
        self.restorations.append(_restoration_record(outcome))
        actions_spent = len(self.executor.actions) - actions_before
        active_after = len(self.runtime.active)
        passed = (
            outcome.passed
            and not self.runtime.halted
            and active_after == active_before - 1
        )
        self.minimal_cleanup_actions += actions_spent
        self.minimal_cleanup_passes += int(passed)
        self.minimal_cleanup_failures += int(not passed)
        self.audit(
            {
                "type": MINIMAL_CLEANUP_POLICY_EVENT_V1,
                "phase": "outcome",
                "policy": "restore_one_top_obligation_then_replan",
                "decision": decision,
                "bid": candidate.bid,
                "active_obligations_before_proposal": active_before,
                "active_obligations_after_cleanup": active_after,
                "cleanup_gui_actions": actions_spent,
                "cleanup_passed": passed,
                "replan_from_realized_state": passed,
                "stale_proposal_executed": False,
            }
        )
        if passed:
            raise _ReplanFromPartiallyRestoredState
        current_reserve = sum(
            inverse_action_cost_v8(transaction.contract)
            for transaction in self.runtime.active
        )
        return False, current_reserve

    def run_policy(self) -> None:
        while not self.executor.done and self.within_budget():
            try:
                super().run_policy()
            except _ReplanFromPartiallyRestoredState:
                continue
            return

    def result(self) -> dict[str, Any]:
        result = super().result()
        result["metrics"].update(
            {
                "minimal_cleanup_attempts": self.minimal_cleanup_attempts,
                "minimal_cleanup_passes": self.minimal_cleanup_passes,
                "minimal_cleanup_failures": self.minimal_cleanup_failures,
                "minimal_cleanup_actions": self.minimal_cleanup_actions,
            }
        )
        return result


__all__ = [
    "MINIMAL_CLEANUP_POLICY_EVENT_V1",
    "MINIMAL_CLEANUP_REPLAN_V1",
    "MinimalCleanupReplanDriverV1",
]
