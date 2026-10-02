"""PACT-v11 confirmation driver with a public no-effect inverse guard."""

from __future__ import annotations

from typing import Any

from .confirmation_agents_v10 import FullPactConfirmationDriverV10
from .pact_controller_v11 import FailClosedTransactionRuntimeV11


class FullPactConfirmationDriverV11(FullPactConfirmationDriverV10):
    """V10 plus complete-public no-effect certification before inversion."""

    method_id = "full_pact_v11"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.runtime = FailClosedTransactionRuntimeV11(
            self.executor,
            self.interrupt_repair_reservation,
        )

    def result(self) -> dict[str, Any]:
        result = super().result()
        result["metrics"]["unchanged_public_inverse_skips"] = sum(
            event.get("type") == "restoration"
            and event.get("inverse_skipped") is True
            and event.get("certificate_scope") == "complete_public_snapshot"
            for event in self.runtime.events
        )
        return result
