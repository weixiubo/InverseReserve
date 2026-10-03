"""Matched controls for the PACT-v13 final-stage re-execution."""

from __future__ import annotations

from typing import Any

from inversereserve.controllers.confirmation_ablation_agents_v12 import (
    RawOpenLoopConfirmationDriverV12,
    TypedNoCertificateConfirmationDriverV12,
)
from inversereserve.controllers.confirmation_agents_v13 import (
    FullPactConfirmationDriverV13,
    complete_public_commit_metrics_v13,
)
from inversereserve.controllers.pact_controller_v13 import FailClosedTransactionRuntimeV13


class RawOpenLoopConfirmationDriverV13(RawOpenLoopConfirmationDriverV12):
    method_id = "raw_open_loop_v13_matched"


class TypedNoCertificateConfirmationDriverV13(TypedNoCertificateConfirmationDriverV12):
    """Remove commit certificates while retaining every v13 recovery guard."""

    method_id = "typed_no_certificate_v13"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.runtime = FailClosedTransactionRuntimeV13(
            self.executor,
            self.interrupt_repair_reservation,
        )

    def result(self) -> dict[str, Any]:
        result = super().result()
        result["metrics"].update(complete_public_commit_metrics_v13(self))
        return result


MATCHED_CONFIRMATION_DRIVERS_V13 = {
    "raw_open_loop_v13_matched": RawOpenLoopConfirmationDriverV13,
    "typed_no_certificate_v13": TypedNoCertificateConfirmationDriverV13,
    "full_pact_v13": FullPactConfirmationDriverV13,
}
