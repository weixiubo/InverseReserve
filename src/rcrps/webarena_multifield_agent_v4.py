"""WebArena multi-field InverseReserve with a one-call commit margin."""

from __future__ import annotations

from .recovery_capacity import remaining_after_action as _remaining_capacity_after_proposal

from typing import Any

from .pact_controller_v8 import inverse_action_cost_v8
from .webarena_multifield_agent_v3 import MultiFieldInverseReserveAgentV3


AUXILIARY_COMMIT_MARGIN_V4 = 1


class MultiFieldInverseReserveAgentV4(MultiFieldInverseReserveAgentV3):
    """Precharge one future terminal call without changing inverse reserve."""

    method_id = "inversereserve_webarena_multifield_v4_commit_margin"
    reserve_scope = "stack_wide_inverse_plus_one_commit"

    def _reserve_forward(
        self,
        *,
        binding: Any,
        contract: Any,
    ) -> bool:
        active_reserve = sum(
            inverse_action_cost_v8(transaction.contract)
            for transaction in self.runtime.active
        )
        proposal_reserve = inverse_action_cost_v8(contract)
        required = (
            active_reserve
            + proposal_reserve
            + AUXILIARY_COMMIT_MARGIN_V4
        )
        remaining_after_forward = _remaining_capacity_after_proposal(self.budgets["maximum_gui_actions"], len(self.executor.actions))
        slack = remaining_after_forward - required
        self._record_slack(slack)
        allowed = slack >= 0
        self.inverse_reservation_audits += 1
        self.audit(
            {
                "type": "webarena_multifield_commit_margin_v4",
                "reservation_rule": self.reserve_scope,
                "bid": binding.bid,
                "binding_kind": binding.binding_kind,
                "active_inverse_cost": active_reserve,
                "proposal_inverse_cost": proposal_reserve,
                "auxiliary_commit_margin": AUXILIARY_COMMIT_MARGIN_V4,
                "required_after_forward": required,
                "remaining_after_forward": remaining_after_forward,
                "commit_margin_slack": slack,
                "allowed": allowed,
            }
        )
        if not allowed:
            self.inverse_reservation_stops += 1
            self.method_failure = (
                "complete multi-field inverse stack and one-call commit "
                "margin no longer fit"
            )
        return allowed

    def result(self) -> dict[str, Any]:
        result = super().result()
        result["candidate"] = (
            "WebArena-multifield-InverseReserve-v4-commit-margin-episode"
        )
        result["auxiliary_commit_margin"] = AUXILIARY_COMMIT_MARGIN_V4
        return result


__all__ = [
    "AUXILIARY_COMMIT_MARGIN_V4",
    "MultiFieldInverseReserveAgentV4",
]
