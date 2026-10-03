"""Pure InverseReserve admission for the WebArena multi-field adapter.

V1 conservatively reserved a terminal commit and a discretionary two-action
interrupt repair before every field forward.  This V2 executor leaves those
policies at their own decision points and applies Equation (3) exactly at a
field admission: only the active and proposal inverse programs are charged.
"""

from __future__ import annotations

from typing import Any

from inversereserve.adapters.webarena.webarena_multifield_agent_v1 import MultiFieldInverseReserveAgentV1
from inversereserve.controllers.pact_controller_v8 import inverse_action_cost_v8
from inversereserve.core.recovery_capacity import remaining_after_action as _remaining_capacity_after_proposal


class MultiFieldInverseReserveAgentV2(MultiFieldInverseReserveAgentV1):
    """Apply the paper's exact active-plus-proposal inverse gate."""

    method_id = "inversereserve_webarena_multifield_v2"
    reserve_scope = "stack_wide_inverse_only"

    def _reserve_forward(
        self,
        *,
        binding: Any,
        contract: Any,
    ) -> bool:
        active_reserve = sum(
            inverse_action_cost_v8(transaction.contract) for transaction in self.runtime.active
        )
        proposal_reserve = inverse_action_cost_v8(contract)
        stack_wide_required = active_reserve + proposal_reserve
        remaining_after_forward = _remaining_capacity_after_proposal(
            self.budgets["maximum_gui_actions"], len(self.executor.actions)
        )
        slack = remaining_after_forward - stack_wide_required
        self._record_slack(slack)
        allowed = slack >= 0
        self.inverse_reservation_audits += 1
        self.audit(
            {
                "type": "webarena_multifield_inverse_reservation_v2",
                "reservation_rule": self.reserve_scope,
                "bid": binding.bid,
                "binding_kind": binding.binding_kind,
                "active_inverse_cost": active_reserve,
                "proposal_inverse_cost": proposal_reserve,
                "stack_wide_required_after_forward": stack_wide_required,
                "remaining_after_forward": remaining_after_forward,
                "inverse_reserve_slack": slack,
                "allowed": allowed,
            }
        )
        if not allowed:
            self.inverse_reservation_stops += 1
            self.method_failure = "complete multi-field inverse stack no longer fits"
        return allowed


__all__ = ["MultiFieldInverseReserveAgentV2"]
