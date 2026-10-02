"""Indexed, navigation-decoupled WebArena action execution."""

from __future__ import annotations

from typing import Any

from .pact_controller_v4 import ActionExecutionV4
from .transaction_actions_v4 import ContractActionV4
from .typed_observation import SemanticSnapshot, semantic_snapshot
from .typed_observation_indexed_v1 import IndexedSemanticSnapshotV1
from .webarena_executor_v2 import WebArenaConfirmationExecutorV2


def browsergym_code_webarena_v3(
    action: ContractActionV4,
    role: str,
    *,
    viewport_width: int,
    viewport_height: int,
) -> str:
    """Emit one click without coupling effect detection to a 500 ms wait."""

    if role in {"navigation", "commit"} and action.operation == "click":
        assert action.bid is not None
        return f"click_no_wait({action.bid!r})"
    return action.browsergym_code(
        viewport_width=viewport_width,
        viewport_height=viewport_height,
    )


class WebArenaConfirmationExecutorV3(WebArenaConfirmationExecutorV2):
    """Cache an indexed public snapshot and isolate all evaluator feedback."""

    def __init__(
        self,
        environment: Any,
        observation: dict[str, Any],
        *,
        maximum_gui_actions: int,
    ) -> None:
        super().__init__(
            environment,
            observation,
            maximum_gui_actions=maximum_gui_actions,
        )
        self._cached_observation: dict[str, Any] | None = None
        self._cached_snapshot: IndexedSemanticSnapshotV1 | None = None

    @property
    def snapshot(self) -> SemanticSnapshot:
        if (
            self._cached_observation is not self.observation
            or self._cached_snapshot is None
        ):
            raw = semantic_snapshot(
                self.observation["axtree_object"],
                self.observation["dom_object"],
                self.observation["extra_element_properties"],
            )
            self._cached_observation = self.observation
            self._cached_snapshot = IndexedSemanticSnapshotV1.from_snapshot(raw)
        return self._cached_snapshot

    def __call__(
        self, action: ContractActionV4, role: str
    ) -> ActionExecutionV4:
        if self.done:
            raise RuntimeError("confirmation executor is already terminal")
        if len(self.actions) >= self.maximum_gui_actions:
            raise RuntimeError("confirmation GUI action budget exhausted")
        height, width = self.observation["screenshot"].shape[:2]
        code = browsergym_code_webarena_v3(
            action,
            role,
            viewport_width=int(width),
            viewport_height=int(height),
        )
        prior_error = str(self.observation.get("last_action_error", ""))
        try:
            observation, _reward, terminated, truncated, _info = (
                self.environment.step(code)
            )
        except Exception as error:
            self.infrastructure_error = f"{type(error).__name__}: {error}"
            raise
        self.observation = observation
        self._cached_observation = None
        self._cached_snapshot = None
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
                    if role in {"navigation", "commit"}
                    and action.operation == "click"
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
