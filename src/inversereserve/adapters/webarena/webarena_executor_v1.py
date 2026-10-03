"""WebArena action executor with single-shot, navigation-decoupled commits."""

from __future__ import annotations

from inversereserve.contracts.transaction_actions_v4 import ContractActionV4
from inversereserve.controllers.confirmation_agents_v7 import ConfirmationExecutorV7
from inversereserve.controllers.pact_controller_v4 import ActionExecutionV4


def browsergym_code_webarena_v1(
    action: ContractActionV4,
    role: str,
    *,
    viewport_width: int,
    viewport_height: int,
) -> str:
    """Render one certified click event without coupling it to navigation wait."""

    if role == "commit" and action.operation == "click":
        assert action.bid is not None
        return f"click_no_wait({action.bid!r})"
    return action.browsergym_code(
        viewport_width=viewport_width,
        viewport_height=viewport_height,
    )


class WebArenaConfirmationExecutorV1(ConfirmationExecutorV7):
    """Preserve the v7 information boundary with a WebArena commit backend.

    The certificate continues to bind ``ContractActionV4('click', bid)``.  Only
    the Playwright synchronization policy changes: a commit emits exactly one
    click event and does not wait for navigation inside the 500 ms BrowserGym
    primitive.  The returned fresh public observation and effect ledger remain
    responsible for deciding whether the click had an effect.
    """

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
            observation, reward, terminated, truncated, info = self.environment.step(code)
        except Exception as error:
            self.infrastructure_error = f"{type(error).__name__}: {error}"
            raise
        self.observation = observation
        self.terminated = bool(terminated)
        self.truncated = bool(truncated)
        self.success = self.success or float(reward) > 0.0
        self.done = self.terminated or self.truncated or self.success
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
                "reward": float(reward),
                "terminated": self.terminated,
                "truncated": self.truncated,
                "last_action_error_before": prior_error,
                "last_action_error_after": action_error,
                "evaluator_reason": str(info.get("message", info.get("reason", ""))),
                "method_received_reward": False,
                "method_received_info": False,
            }
        )
        return ActionExecutionV4(
            self.snapshot,
            self.terminated,
            self.truncated,
            action_error,
        )
