"""PACT-v12 confirmation driver with a complete public no-effect guard."""

from __future__ import annotations

from typing import Any

from .confirmation_agents_v11 import FullPactConfirmationDriverV11
from .pact_controller_v12 import FailClosedTransactionRuntimeV12


def complete_public_no_effect_metrics_v12(driver: Any) -> dict[str, int]:
    events = driver.runtime.events
    return {
        "complete_public_observation_checks_v12": sum(
            event.get("type") == "complete_public_observation_check_v12"
            for event in events
        ),
        "complete_public_inverse_skips_v12": sum(
            event.get("type") == "complete_public_no_effect_certificate_v12"
            and event.get("passed") is True
            and event.get("inverse_skipped") is True
            for event in events
        ),
    }


class FullPactConfirmationDriverV12(FullPactConfirmationDriverV11):
    """V11 with equality over every retained public observation field."""

    method_id = "full_pact_v12"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.runtime = FailClosedTransactionRuntimeV12(
            self.executor,
            self.interrupt_repair_reservation,
        )

    def result(self) -> dict[str, Any]:
        result = super().result()
        result["metrics"].update(complete_public_no_effect_metrics_v12(self))
        return result
