"""PACT-v9 confirmation driver with the v9 typed runtime."""

from __future__ import annotations

from typing import Any

from inversereserve.controllers.confirmation_agents_v8 import FullPactConfirmationDriverV8
from inversereserve.controllers.pact_controller_v9 import FailClosedTransactionRuntimeV9


class FullPactConfirmationDriverV9(FullPactConfirmationDriverV8):
    method_id = "full_pact_v9"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.runtime = FailClosedTransactionRuntimeV9(self.executor)
