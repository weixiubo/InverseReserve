"""PACT-v17 confirmation driver with effect-verified inverse completion."""

from __future__ import annotations

from typing import Any

from .confirmation_agents_v16 import FullPactConfirmationDriverV16
from .pact_controller_v17 import FailClosedTransactionRuntimeV17


def inverse_error_effect_metrics_v17(driver: Any) -> dict[str, int]:
    checks = [
        event
        for event in driver.runtime.events
        if event.get("type") == "inverse_action_error_effect_check_v17"
    ]
    return {
        "inverse_action_error_effect_checks_v17": len(checks),
        "inverse_action_error_effect_passes_v17": sum(
            event.get("passed") is True for event in checks
        ),
        "inverse_action_error_effect_failures_v17": sum(
            event.get("passed") is False for event in checks
        ),
    }


class FullPactConfirmationDriverV17(FullPactConfirmationDriverV16):
    """Keep v16 reserve and clearance while verifying inverse error effects."""

    method_id = "full_pact_v17"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.runtime = FailClosedTransactionRuntimeV17(
            self.executor,
            self.interrupt_repair_reservation,
            self.active_restore_clearance_reservation_v16,
        )

    def result(self) -> dict[str, Any]:
        result = super().result()
        result["metrics"].update(inverse_error_effect_metrics_v17(self))
        return result


__all__ = [
    "FullPactConfirmationDriverV17",
    "inverse_error_effect_metrics_v17",
]
