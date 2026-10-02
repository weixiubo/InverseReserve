"""Strong state-changing safe controls for the frozen PACT-v19 runtime.

Both controls inherit the exact PACT-v19 contracts, stack-wide reserve,
planner, executor, and restoration verifier.  They differ only in what they do
after a live transaction conflicts with the current state:

* complete cleanup restores the full LIFO stack before replanning;
* top cleanup intervenes only after a stack-wide capacity rejection and
  restores exactly one top obligation before replanning.

Neither control executes a proposal observed before cleanup.
"""

from __future__ import annotations

from typing import Any

from .capacity_reserve_drivers_v19 import StackWideCapacityDriverV19
from .confirmation_agents_v7 import _restoration_record
from .pact_controller_v8 import inverse_action_cost_v8


COMPLETE_CLEANUP_REPLAN_V19 = "complete_cleanup_replan_v19"
TOP_CLEANUP_REPLAN_V19 = "top_cleanup_replan_v19"
COMPLETE_CLEANUP_EVENT_V19 = "complete_cleanup_replan_policy_v19"
TOP_CLEANUP_EVENT_V19 = "top_cleanup_replan_policy_v19"


class _ReplanFromCompletelyRestoredState(RuntimeError):
    """Internal transfer after verified complete cleanup changes the state."""


class _ReplanFromTopRestoredState(RuntimeError):
    """Internal transfer after one verified top restoration changes the state."""


class CompleteCleanupReplanDriverV19(StackWideCapacityDriverV19):
    """Restore the complete live stack before any further transaction."""

    method_id = COMPLETE_CLEANUP_REPLAN_V19

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.complete_cleanup_attempts = 0
        self.complete_cleanup_passes = 0
        self.complete_cleanup_failures = 0
        self.complete_cleanup_actions = 0

    def inverse_reserve(self, candidate: Any, decision: str) -> tuple[bool, int]:
        active_count = len(self.runtime.active)
        if decision != "transact" or active_count == 0:
            return super().inverse_reserve(candidate, decision)

        active_reserve = sum(
            inverse_action_cost_v8(transaction.contract)
            for transaction in self.runtime.active
        )
        actions_before = len(self.executor.actions)
        self.complete_cleanup_attempts += 1
        self.inverse_reservation_audits += 1
        self.audit(
            {
                "type": COMPLETE_CLEANUP_EVENT_V19,
                "phase": "request",
                "policy": "restore_complete_lifo_stack_then_replan",
                "decision": decision,
                "bid": candidate.bid,
                "active_obligations_before_proposal": active_count,
                "registered_active_inverse_cost": active_reserve,
                "stale_proposal_execution_allowed": False,
                "runtime_version": "PACT-v19",
            }
        )

        self.cleanup_runtime(self.runtime)
        actions_spent = len(self.executor.actions) - actions_before
        cleared = not self.runtime.active and not self.runtime.halted
        self.complete_cleanup_actions += actions_spent
        self.complete_cleanup_passes += int(cleared)
        self.complete_cleanup_failures += int(not cleared)
        self.audit(
            {
                "type": COMPLETE_CLEANUP_EVENT_V19,
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
                "runtime_version": "PACT-v19",
            }
        )
        if cleared:
            raise _ReplanFromCompletelyRestoredState
        return False, sum(
            inverse_action_cost_v8(transaction.contract)
            for transaction in self.runtime.active
        )

    def run_policy(self) -> None:
        while not self.executor.done and self.within_budget():
            try:
                super().run_policy()
            except _ReplanFromCompletelyRestoredState:
                continue
            return

    def result(self) -> dict[str, Any]:
        result = super().result()
        result["metrics"].update(
            {
                "complete_cleanup_attempts": self.complete_cleanup_attempts,
                "complete_cleanup_passes": self.complete_cleanup_passes,
                "complete_cleanup_failures": self.complete_cleanup_failures,
                "complete_cleanup_actions": self.complete_cleanup_actions,
            }
        )
        return result


class TopCleanupReplanDriverV19(StackWideCapacityDriverV19):
    """On a capacity rejection, restore one top obligation and replan."""

    method_id = TOP_CLEANUP_REPLAN_V19

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.top_cleanup_attempts = 0
        self.top_cleanup_passes = 0
        self.top_cleanup_failures = 0
        self.top_cleanup_actions = 0
        self.top_cleanup_preserved_lower_events = 0

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
        self.top_cleanup_attempts += 1
        self.audit(
            {
                "type": TOP_CLEANUP_EVENT_V19,
                "phase": "request",
                "policy": "restore_one_top_obligation_then_replan",
                "decision": decision,
                "bid": candidate.bid,
                "active_obligations_before_proposal": active_before,
                "registered_active_inverse_cost": registered_before,
                "blocked_stack_wide_reserve": reserve,
                "stale_proposal_execution_allowed": False,
                "runtime_version": "PACT-v19",
            }
        )
        outcome = self.runtime.restore_top(
            "reserve-guided top cleanup before PACT-v19 replanning"
        )
        self.restorations.append(_restoration_record(outcome))
        actions_spent = len(self.executor.actions) - actions_before
        active_after = len(self.runtime.active)
        passed = (
            outcome.passed
            and not self.runtime.halted
            and active_after == active_before - 1
        )
        self.top_cleanup_actions += actions_spent
        self.top_cleanup_passes += int(passed)
        self.top_cleanup_failures += int(not passed)
        self.top_cleanup_preserved_lower_events += int(passed and active_after > 0)
        self.audit(
            {
                "type": TOP_CLEANUP_EVENT_V19,
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
                "runtime_version": "PACT-v19",
            }
        )
        if passed:
            raise _ReplanFromTopRestoredState
        current_reserve = sum(
            inverse_action_cost_v8(transaction.contract)
            for transaction in self.runtime.active
        )
        return False, current_reserve

    def run_policy(self) -> None:
        while not self.executor.done and self.within_budget():
            try:
                super().run_policy()
            except _ReplanFromTopRestoredState:
                continue
            return

    def result(self) -> dict[str, Any]:
        result = super().result()
        result["metrics"].update(
            {
                "top_cleanup_attempts": self.top_cleanup_attempts,
                "top_cleanup_passes": self.top_cleanup_passes,
                "top_cleanup_failures": self.top_cleanup_failures,
                "top_cleanup_actions": self.top_cleanup_actions,
                "top_cleanup_preserved_lower_events": (
                    self.top_cleanup_preserved_lower_events
                ),
            }
        )
        return result


__all__ = [
    "COMPLETE_CLEANUP_EVENT_V19",
    "COMPLETE_CLEANUP_REPLAN_V19",
    "CompleteCleanupReplanDriverV19",
    "TOP_CLEANUP_EVENT_V19",
    "TOP_CLEANUP_REPLAN_V19",
    "TopCleanupReplanDriverV19",
]
