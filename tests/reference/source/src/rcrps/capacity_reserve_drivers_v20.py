"""PACT-v20 capacity policies with public frame-compatible replanning."""

from __future__ import annotations

from .recovery_capacity import remaining_after_action as _remaining_capacity_after_proposal

from typing import Any

from .capacity_reserve_drivers_v18 import RESERVATION_EVENT_V18
from .confirmation_agents_v7 import _restoration_record
from .confirmation_agents_v20 import FullPactConfirmationDriverV20
from .pact_controller_v8 import inverse_action_cost_v8
from .pact_goal_scope_v20 import navigation_contract_requires_replan_v20


STACK_WIDE_V20 = "stack_wide_reserve_v20"
SINGLE_ACTIVE_OBLIGATION_V20 = "single_active_obligation_v20"
TOP_CLEANUP_REPLAN_V20 = "top_cleanup_replan_v20"
SINGLE_OBLIGATION_POLICY_EVENT_V20 = "single_obligation_policy_v20"
FRAME_CLEANUP_EVENT_V20 = "frame_compatible_cleanup_replan_v20"
TOP_CLEANUP_EVENT_V20 = "top_cleanup_replan_policy_v20"


class _ReplanAfterFrameCleanupV20(RuntimeError):
    """Internal transfer after verified frame cleanup changes public state."""


class _ReplanAfterCapacityCleanupV20(RuntimeError):
    """Internal transfer after reserve-guided cleanup changes public state."""


class CapacityReserveDriverV20(FullPactConfirmationDriverV20):
    """Stack-wide reserve plus cleanup before a frame-incompatible navigation."""

    stack_wide = True

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.frame_cleanup_attempts_v20 = 0
        self.frame_cleanup_passes_v20 = 0
        self.frame_cleanup_failures_v20 = 0
        self.frame_cleanup_actions_v20 = 0

    def _maybe_frame_cleanup_v20(self, candidate: Any, decision: str) -> None:
        if decision != "transact" or not self.runtime.active:
            return
        inventory = self.inventory()
        contract = inventory.contract_by_bid.get(candidate.bid)
        if contract is None or not navigation_contract_requires_replan_v20(
            self.executor.snapshot,
            contract,
            tuple(self.runtime.active),
        ):
            return

        active_before = len(self.runtime.active)
        actions_before = len(self.executor.actions)
        self.frame_cleanup_attempts_v20 += 1
        self.audit(
            {
                "type": FRAME_CLEANUP_EVENT_V20,
                "phase": "request",
                "decision": decision,
                "bid": candidate.bid,
                "active_obligations_before_proposal": active_before,
                "stale_proposal_execution_allowed": False,
                "reason": (
                    "navigation proposal is outside the public scope of the "
                    "active top"
                ),
            }
        )
        outcome = self.runtime.restore_top(
            "public frame cleanup before PACT-v20 replanning"
        )
        self.restorations.append(_restoration_record(outcome))
        actions_spent = len(self.executor.actions) - actions_before
        active_after = len(self.runtime.active)
        passed = (
            outcome.passed
            and not self.runtime.halted
            and active_after == active_before - 1
        )
        self.frame_cleanup_actions_v20 += actions_spent
        self.frame_cleanup_passes_v20 += int(passed)
        self.frame_cleanup_failures_v20 += int(not passed)
        self.audit(
            {
                "type": FRAME_CLEANUP_EVENT_V20,
                "phase": "outcome",
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
            raise _ReplanAfterFrameCleanupV20

    def _capacity_reserve_v20(
        self, candidate: Any, decision: str
    ) -> tuple[bool, int]:
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
        applied_reserve = (
            stack_wide_reserve if self.stack_wide else proposal_reserve
        )
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
                "runtime_version": "PACT-v20",
            }
        )
        return allowed, applied_reserve

    def inverse_reserve(self, candidate: Any, decision: str) -> tuple[bool, int]:
        self._maybe_frame_cleanup_v20(candidate, decision)
        return self._capacity_reserve_v20(candidate, decision)

    def run_policy(self) -> None:
        while not self.executor.done and self.within_budget():
            try:
                super().run_policy()
            except _ReplanAfterFrameCleanupV20:
                continue
            return

    def result(self) -> dict[str, Any]:
        result = super().result()
        result["metrics"].update(
            {
                "frame_cleanup_attempts_v20": self.frame_cleanup_attempts_v20,
                "frame_cleanup_passes_v20": self.frame_cleanup_passes_v20,
                "frame_cleanup_failures_v20": self.frame_cleanup_failures_v20,
                "frame_cleanup_actions_v20": self.frame_cleanup_actions_v20,
            }
        )
        return result


class StackWideCapacityDriverV20(CapacityReserveDriverV20):
    method_id = STACK_WIDE_V20
    stack_wide = True


class SingleActiveObligationDriverV20(StackWideCapacityDriverV20):
    """Depth-one control sharing every PACT-v20 mechanism."""

    method_id = SINGLE_ACTIVE_OBLIGATION_V20

    def inverse_reserve(self, candidate: Any, decision: str) -> tuple[bool, int]:
        self._maybe_frame_cleanup_v20(candidate, decision)
        active_count = len(self.runtime.active)
        if decision == "transact" and active_count >= 1:
            active_reserve = sum(
                inverse_action_cost_v8(transaction.contract)
                for transaction in self.runtime.active
            )
            self.inverse_reservation_audits += 1
            self.audit(
                {
                    "type": SINGLE_OBLIGATION_POLICY_EVENT_V20,
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
        allowed, reserve = self._capacity_reserve_v20(candidate, decision)
        self.audit(
            {
                "type": SINGLE_OBLIGATION_POLICY_EVENT_V20,
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


class TopCleanupReplanDriverV20(StackWideCapacityDriverV20):
    """Restore one top obligation after a stack-wide capacity rejection."""

    method_id = TOP_CLEANUP_REPLAN_V20

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
                "type": TOP_CLEANUP_EVENT_V20,
                "phase": "request",
                "decision": decision,
                "bid": candidate.bid,
                "active_obligations_before_proposal": active_before,
                "registered_active_inverse_cost": registered_before,
                "blocked_stack_wide_reserve": reserve,
                "stale_proposal_execution_allowed": False,
            }
        )
        outcome = self.runtime.restore_top(
            "reserve-guided top cleanup before PACT-v20 replanning"
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
                "type": TOP_CLEANUP_EVENT_V20,
                "phase": "outcome",
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
            raise _ReplanAfterCapacityCleanupV20
        return False, sum(
            inverse_action_cost_v8(transaction.contract)
            for transaction in self.runtime.active
        )

    def run_policy(self) -> None:
        while not self.executor.done and self.within_budget():
            try:
                super().run_policy()
            except _ReplanAfterCapacityCleanupV20:
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
    "FRAME_CLEANUP_EVENT_V20",
    "SINGLE_ACTIVE_OBLIGATION_V20",
    "SINGLE_OBLIGATION_POLICY_EVENT_V20",
    "STACK_WIDE_V20",
    "TOP_CLEANUP_EVENT_V20",
    "TOP_CLEANUP_REPLAN_V20",
    "CapacityReserveDriverV20",
    "SingleActiveObligationDriverV20",
    "StackWideCapacityDriverV20",
    "TopCleanupReplanDriverV20",
]
