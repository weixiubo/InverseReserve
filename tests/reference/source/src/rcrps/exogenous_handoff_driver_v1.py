"""Systematic host-requested handoff on the frozen stack-wide runtime."""

from __future__ import annotations

from typing import Any

from .capacity_reserve_drivers_v18 import StackWideCapacityDriverV18
from .pact_controller_v8 import inverse_action_cost_v8


EXOGENOUS_HANDOFF_EVENT_V1 = "exogenous_handoff_v1"
HANDOFF_DEPTH_ONE_V1 = "stack_wide_handoff_depth_one_v1"
HANDOFF_DEPTH_TWO_V1 = "stack_wide_handoff_depth_two_v1"


class _ExogenousHandoffMixinV1:
    """Request handoff at the first live prefix reaching ``target_depth``.

    The inherited policy loop checks ``within_budget`` before every new
    proposal. Returning ``False`` at that boundary transfers control to the
    inherited verified complete-LIFO cleanup. No action, proposal, or recovery
    primitive is changed.
    """

    target_depth = 1

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.exogenous_handoff_requested_v1 = False
        self.exogenous_handoff_active_before_v1 = 0
        self.exogenous_handoff_registered_cost_v1 = 0
        self.exogenous_handoff_remaining_before_v1 = 0
        self.exogenous_handoff_actions_before_v1 = 0
        self.exogenous_handoff_restoration_attempts_v1 = 0
        self.exogenous_handoff_restoration_passes_v1 = 0
        self.exogenous_handoff_active_after_v1 = 0
        self.exogenous_handoff_passed_v1 = False

    def within_budget(self) -> bool:
        active = tuple(self.runtime.active)
        if (
            not self.exogenous_handoff_requested_v1
            and len(active) >= self.target_depth
        ):
            registered_cost = sum(
                inverse_action_cost_v8(transaction.contract)
                for transaction in active
            )
            action_count = len(self.executor.actions)
            remaining = (
                int(self.budgets["maximum_gui_actions"]) - action_count
            )
            self.exogenous_handoff_requested_v1 = True
            self.exogenous_handoff_active_before_v1 = len(active)
            self.exogenous_handoff_registered_cost_v1 = registered_cost
            self.exogenous_handoff_remaining_before_v1 = remaining
            self.exogenous_handoff_actions_before_v1 = action_count
            self.method_failure = (
                "external host requested persistent handoff"
            )
            self.audit(
                {
                    "type": EXOGENOUS_HANDOFF_EVENT_V1,
                    "phase": "request",
                    "target_depth": self.target_depth,
                    "active_obligations_before_handoff": len(active),
                    "registered_inverse_cost_before_handoff": registered_cost,
                    "remaining_gui_actions_before_handoff": remaining,
                    "gui_actions_before_handoff": action_count,
                    "request_is_exogenous": True,
                    "recovery_program": "complete_registered_lifo_stack",
                }
            )
            return False
        return super().within_budget()

    def run_policy(self) -> None:
        restorations_before = len(self.restorations)
        super().run_policy()
        if not self.exogenous_handoff_requested_v1:
            return
        new_restorations = self.restorations[restorations_before:]
        attempts = len(new_restorations)
        passes = sum(bool(row.get("passed")) for row in new_restorations)
        active_after = len(self.runtime.active)
        passed = bool(
            attempts > 0
            and attempts == passes
            and active_after == 0
            and not self.runtime.halted
            and len(self.executor.actions)
            <= int(self.budgets["maximum_gui_actions"])
        )
        self.exogenous_handoff_restoration_attempts_v1 = attempts
        self.exogenous_handoff_restoration_passes_v1 = passes
        self.exogenous_handoff_active_after_v1 = active_after
        self.exogenous_handoff_passed_v1 = passed
        self.audit(
            {
                "type": EXOGENOUS_HANDOFF_EVENT_V1,
                "phase": "outcome",
                "target_depth": self.target_depth,
                "active_obligations_before_handoff": (
                    self.exogenous_handoff_active_before_v1
                ),
                "active_obligations_after_handoff": active_after,
                "registered_inverse_cost_before_handoff": (
                    self.exogenous_handoff_registered_cost_v1
                ),
                "remaining_gui_actions_before_handoff": (
                    self.exogenous_handoff_remaining_before_v1
                ),
                "restoration_attempts": attempts,
                "restoration_passes": passes,
                "runtime_halted": bool(self.runtime.halted),
                "handoff_passed": passed,
            }
        )

    def result(self) -> dict[str, Any]:
        result = super().result()
        result["metrics"].update(
            {
                "exogenous_handoff_target_depth_v1": self.target_depth,
                "exogenous_handoff_requested_v1": int(
                    self.exogenous_handoff_requested_v1
                ),
                "exogenous_handoff_active_before_v1": (
                    self.exogenous_handoff_active_before_v1
                ),
                "exogenous_handoff_registered_cost_v1": (
                    self.exogenous_handoff_registered_cost_v1
                ),
                "exogenous_handoff_remaining_before_v1": (
                    self.exogenous_handoff_remaining_before_v1
                ),
                "exogenous_handoff_actions_before_v1": (
                    self.exogenous_handoff_actions_before_v1
                ),
                "exogenous_handoff_restoration_attempts_v1": (
                    self.exogenous_handoff_restoration_attempts_v1
                ),
                "exogenous_handoff_restoration_passes_v1": (
                    self.exogenous_handoff_restoration_passes_v1
                ),
                "exogenous_handoff_active_after_v1": (
                    self.exogenous_handoff_active_after_v1
                ),
                "exogenous_handoff_passed_v1": int(
                    self.exogenous_handoff_passed_v1
                ),
            }
        )
        return result


class StackWideHandoffDepthOneV1(
    _ExogenousHandoffMixinV1,
    StackWideCapacityDriverV18,
):
    """Request host handoff at the first live obligation."""

    method_id = HANDOFF_DEPTH_ONE_V1
    target_depth = 1


class StackWideHandoffDepthTwoV1(
    _ExogenousHandoffMixinV1,
    StackWideCapacityDriverV18,
):
    """Request host handoff at the first two-obligation live prefix."""

    method_id = HANDOFF_DEPTH_TWO_V1
    target_depth = 2


__all__ = [
    "EXOGENOUS_HANDOFF_EVENT_V1",
    "HANDOFF_DEPTH_ONE_V1",
    "HANDOFF_DEPTH_TWO_V1",
    "StackWideHandoffDepthOneV1",
    "StackWideHandoffDepthTwoV1",
]
