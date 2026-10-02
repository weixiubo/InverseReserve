"""Reward- and evaluator-isolated WebArena action executor.

The V1 executor kept reward and evaluator info out of planner messages but
still used reward to set its internal stop state.  This successor treats both
values as harness-only: they are discarded immediately and cannot affect
method-visible records or control flow.
"""

from __future__ import annotations

from inversereserve.adapters.webarena.webarena_executor_v1 import browsergym_code_webarena_v1
from inversereserve.contracts.transaction_actions_v4 import ContractActionV4
from inversereserve.controllers.confirmation_agents_v7 import ConfirmationExecutorV7
from inversereserve.controllers.pact_controller_v4 import ActionExecutionV4


class WebArenaConfirmationExecutorV2(ConfirmationExecutorV7):
    """Execute public GUI actions without reward/evaluator feedback channels."""

    def __call__(self, action: ContractActionV4, role: str) -> ActionExecutionV4:
        if self.done:
            raise RuntimeError("confirmation executor is already terminal")
        if len(self.actions) >= self.maximum_gui_actions:
            raise RuntimeError("confirmation GUI action budget exhausted")
        height, width = self.observation["screenshot"].shape[:2]
        code = browsergym_code_webarena_v1(
            action,
            role,
            viewport_width=int(width),
            viewport_height=int(height),
        )
        prior_error = str(self.observation.get("last_action_error", ""))
        try:
            observation, _reward, terminated, truncated, _info = self.environment.step(code)
        except Exception as error:
            self.infrastructure_error = f"{type(error).__name__}: {error}"
            raise
        self.observation = observation
        self.terminated = bool(terminated)
        self.truncated = bool(truncated)
        self.success = False
        self.done = self.terminated or self.truncated
        action_error = str(observation.get("last_action_error", ""))
        self.actions.append(
            {
                "action_index": len(self.actions),
                "role": role,
                "code": code,
                "certified_operation": action.operation,
                "certified_bid": action.bid,
                "execution_backend": (
                    "single_shot_click_no_wait"
                    if role == "commit" and action.operation == "click"
                    else "browsergym_standard"
                ),
                "terminated": self.terminated,
                "truncated": self.truncated,
                "last_action_error_before": prior_error,
                "last_action_error_after": action_error,
                "reward_used_for_control": False,
                "evaluator_info_used_for_control": False,
                "reward_or_info_retained_by_method": False,
            }
        )
        return ActionExecutionV4(
            self.snapshot,
            self.terminated,
            self.truncated,
            action_error,
        )
