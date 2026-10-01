"""WebArena exact-mutation successor using the PACT-v11 runtime."""

from __future__ import annotations

from typing import Any

from .pact_controller_v11 import FailClosedTransactionRuntimeV11
from .webarena_exact_mutation_agent_v2 import ExactMutationTransferAgentV2


class ExactMutationTransferAgentV11(ExactMutationTransferAgentV2):
    """Keep the frozen V2 boundary while guarding public no-effect inverses."""

    method_id = "full_pact_v11_webarena_exact_mutation_v2"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.runtime = FailClosedTransactionRuntimeV11(
            self.executor,
            self.interrupt_repair_reservation,
        )

    def result(self) -> dict[str, Any]:
        result = super().result()
        result["candidate"] = "WebArena-exact-mutation-agent-v11-episode"
        result["metrics"]["unchanged_public_inverse_skips"] = sum(
            event.get("type") == "restoration"
            and event.get("inverse_skipped") is True
            and event.get("certificate_scope") == "complete_public_snapshot"
            for event in self.runtime.events
        )
        return result
