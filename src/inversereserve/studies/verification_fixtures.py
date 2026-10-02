"""Deterministic bounded verification fixtures, separate from reserve and recovery assertions."""

from __future__ import annotations

from typing import Any

from inversereserve.contracts.transaction_actions_v4 import ContractActionV4
from inversereserve.controllers.pact_controller_v4 import ActionExecutionV4
from inversereserve.observations.typed_observation import SemanticElement, SemanticSnapshot


def _field_snapshot(depth: int, filled: int) -> SemanticSnapshot:
    if filled < 0 or filled > depth:
        raise ValueError("filled field count is outside the fixture")
    elements = []
    for index in range(depth):
        value = f"value-{index}" if index < filled else ""
        elements.append(
            SemanticElement(
                bid=f"field{index}",
                role="textbox",
                name=f"Field {index}",
                subtree_text=f"Field {index}",
                ax_properties=(("readonly", False), ("value", value)),
                ax_parent_bid=None,
                dom_tag="input",
                dom_attributes=(("value", value),),
                dom_parent_bid=None,
                visible=True,
                clickable=True,
                bbox=(0.0, float(index * 20), 100.0, 18.0),
            )
        )
    return SemanticSnapshot(tuple(elements))


class _LifoExecutor:
    def __init__(
        self,
        snapshots: tuple[SemanticSnapshot, ...],
        *,
        failure_position: int | None,
        failure_mode: str | None,
    ) -> None:
        self.snapshots = snapshots
        self.depth = len(snapshots) - 1
        self.failure_position = failure_position
        self.failure_mode = failure_mode
        self.forward_index = 0
        self.inverse_index = 0
        self.calls: list[dict[str, Any]] = []

    def __call__(self, action: ContractActionV4, role: str) -> ActionExecutionV4:
        self.calls.append({"role": role, "bid": action.bid, "operation": action.operation})
        if role == "typed_forward":
            self.forward_index += 1
            return ActionExecutionV4(self.snapshots[self.forward_index])
        if role != "typed_inverse":
            raise AssertionError(f"unexpected LIFO fixture role: {role}")
        position = self.inverse_index
        self.inverse_index += 1
        current = self.snapshots[self.depth - position]
        restored = self.snapshots[self.depth - position - 1]
        if position != self.failure_position:
            return ActionExecutionV4(restored)
        if self.failure_mode == "wrong_projection":
            return ActionExecutionV4(current)
        if self.failure_mode == "action_error":
            return ActionExecutionV4(current, action_error="injected inverse error")
        if self.failure_mode == "terminal_result":
            return ActionExecutionV4(current, terminated=True)
        if self.failure_mode == "executor_exception":
            raise RuntimeError("injected inverse executor exception")
        raise AssertionError(f"unknown LIFO failure mode: {self.failure_mode}")
