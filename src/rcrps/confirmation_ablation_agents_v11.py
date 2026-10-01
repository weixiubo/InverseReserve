"""Matched controls for a complete PACT-v11 final-stage re-execution."""

from __future__ import annotations

from typing import Any

from .confirmation_ablation_agents_v10 import (
    RawOpenLoopConfirmationDriverV10,
    TypedNoCertificateConfirmationDriverV10,
)
from .confirmation_agents_v11 import FullPactConfirmationDriverV11
from .pact_controller_v11 import FailClosedTransactionRuntimeV11


def _unchanged_public_inverse_skips(driver: Any) -> int:
    return sum(
        event.get("type") == "restoration"
        and event.get("inverse_skipped") is True
        and event.get("certificate_scope") == "complete_public_snapshot"
        for event in driver.runtime.events
    )


class RawOpenLoopConfirmationDriverV11(RawOpenLoopConfirmationDriverV10):
    """Version-labeled raw control for a complete v11 matched rerun."""

    method_id = "raw_open_loop_v11_matched"


class TypedNoCertificateConfirmationDriverV11(
    TypedNoCertificateConfirmationDriverV10
):
    """Remove only commit certificates while retaining the v11 runtime."""

    method_id = "typed_no_certificate_v11"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.runtime = FailClosedTransactionRuntimeV11(
            self.executor,
            self.interrupt_repair_reservation,
        )

    def result(self) -> dict[str, Any]:
        result = super().result()
        result["metrics"]["unchanged_public_inverse_skips"] = (
            _unchanged_public_inverse_skips(self)
        )
        return result


MATCHED_CONFIRMATION_DRIVERS_V11 = {
    "raw_open_loop_v11_matched": RawOpenLoopConfirmationDriverV11,
    "typed_no_certificate_v11": TypedNoCertificateConfirmationDriverV11,
    "full_pact_v11": FullPactConfirmationDriverV11,
}
