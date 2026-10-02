"""PACT-v22 task-reserve controls with public target-class promotion."""

from __future__ import annotations

from typing import Any

from .capacity_reserve_drivers_v21 import (
    TaskReserveSingleActiveDriverV21,
    TaskReserveTopCleanupDriverV21,
)
from .confirmation_agents_v19 import FullPactConfirmationDriverV19
from .pact_goal_scope_v22 import (
    promote_goal_equivalent_exact_target_v22,
)


TASK_RESERVE_TOP_CLEANUP_V22 = "task_reserve_top_cleanup_v22"
TASK_RESERVE_SINGLE_ACTIVE_V22 = "task_reserve_single_active_v22"
RUNTIME_VERSION_V22 = "PACT-v22-goal-equivalent-target"


class _GoalEquivalentTargetMixinV22:
    """Replace only v20's target-promotion stage."""

    def inventory(self) -> Any:
        inventory = FullPactConfirmationDriverV19.inventory(self)
        promoted, record = promote_goal_equivalent_exact_target_v22(
            self.executor.snapshot,
            inventory,
            transaction_history=(
                tuple(self.runtime.active) + tuple(self.runtime.completed)
            ),
        )
        # FullPactConfirmationDriverV20.fresh_envelope emits this record and
        # otherwise retains its frozen certificate and scope-consumption path.
        self._last_promotion_v20 = record
        return promoted


class TaskReserveTopCleanupDriverV22(
    _GoalEquivalentTargetMixinV22,
    TaskReserveTopCleanupDriverV21,
):
    """Opportunity-preserving task-reserve policy with the v22 compiler."""

    method_id = TASK_RESERVE_TOP_CLEANUP_V22


class TaskReserveSingleActiveDriverV22(
    _GoalEquivalentTargetMixinV22,
    TaskReserveSingleActiveDriverV21,
):
    """Depth-one task-reserve control with the identical v22 compiler."""

    method_id = TASK_RESERVE_SINGLE_ACTIVE_V22


__all__ = [
    "RUNTIME_VERSION_V22",
    "TASK_RESERVE_SINGLE_ACTIVE_V22",
    "TASK_RESERVE_TOP_CLEANUP_V22",
    "TaskReserveSingleActiveDriverV22",
    "TaskReserveTopCleanupDriverV22",
]
