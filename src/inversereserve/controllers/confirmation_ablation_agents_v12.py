"""Matched controls for a complete PACT-v12 final-stage re-execution."""

from __future__ import annotations

from typing import Any

from inversereserve.controllers.confirmation_ablation_agents_v10 import (
    RawOpenLoopConfirmationDriverV10,
    TypedNoCertificateConfirmationDriverV10,
)
from inversereserve.controllers.confirmation_agents_v12 import (
    FullPactConfirmationDriverV12,
    complete_public_no_effect_metrics_v12,
)
from inversereserve.controllers.pact_controller_v12 import FailClosedTransactionRuntimeV12


class RawOpenLoopConfirmationDriverV12(RawOpenLoopConfirmationDriverV10):
    """Version-labeled raw control for a complete v12 matched rerun."""

    method_id = "raw_open_loop_v12_matched"


class TypedNoCertificateConfirmationDriverV12(TypedNoCertificateConfirmationDriverV10):
    """Remove only commit certificates while retaining the v12 runtime."""

    method_id = "typed_no_certificate_v12"

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


MATCHED_CONFIRMATION_DRIVERS_V12 = {
    "raw_open_loop_v12_matched": RawOpenLoopConfirmationDriverV12,
    "typed_no_certificate_v12": TypedNoCertificateConfirmationDriverV12,
    "full_pact_v12": FullPactConfirmationDriverV12,
}
