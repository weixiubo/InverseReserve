"""Matched controls for the reserve-preserving PACT-v10 runtime."""

from __future__ import annotations

from typing import Any

from inversereserve.controllers.confirmation_ablation_agents_v9 import (
    RawOpenLoopConfirmationDriverV9,
    TypedNoCertificateConfirmationDriverV9,
)
from inversereserve.controllers.confirmation_agents_v10 import (
    FullPactConfirmationDriverV10,
    RecoverySolventRepairDriverMixinV10,
)


class RawOpenLoopConfirmationDriverV10(RawOpenLoopConfirmationDriverV9):
    """Version-labeled raw control for a PACT-v10 matched grid."""

    method_id = "raw_open_loop_v10_matched"


class TypedNoCertificateConfirmationDriverV10(
    RecoverySolventRepairDriverMixinV10,
    TypedNoCertificateConfirmationDriverV9,
):
    """Remove only commit certificates while retaining all v10 recovery guards."""

    method_id = "typed_no_certificate_v10"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._initialize_recovery_solvent_repair_v10()


MATCHED_CONFIRMATION_DRIVERS_V10 = {
    "raw_open_loop_v10_matched": RawOpenLoopConfirmationDriverV10,
    "typed_no_certificate_v10": TypedNoCertificateConfirmationDriverV10,
    "full_pact_v10": FullPactConfirmationDriverV10,
}
