"""PACT-v15 confirmation driver with live dynamic-inverse grounding."""

from __future__ import annotations

from typing import Any

from inversereserve.controllers.confirmation_agents_v13 import FullPactConfirmationDriverV13
from inversereserve.controllers.pact_controller_v15 import FailClosedTransactionRuntimeV15


class FullPactConfirmationDriverV15(FullPactConfirmationDriverV13):
    """Keep PACT-v13 policy while refreshing each dynamic inverse live."""

    method_id = "full_pact_v15"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.runtime = FailClosedTransactionRuntimeV15(
            self.executor,
            self.interrupt_repair_reservation,
        )


__all__ = ["FullPactConfirmationDriverV15"]
