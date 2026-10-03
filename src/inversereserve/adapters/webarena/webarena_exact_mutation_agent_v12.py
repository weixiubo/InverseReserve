"""WebArena exact-mutation successor using the PACT-v12 runtime."""

from __future__ import annotations

from typing import Any

from inversereserve.adapters.webarena.webarena_exact_mutation_agent_v2 import ExactMutationTransferAgentV2
from inversereserve.controllers.confirmation_agents_v12 import complete_public_no_effect_metrics_v12
from inversereserve.controllers.pact_controller_v12 import FailClosedTransactionRuntimeV12


class ExactMutationTransferAgentV12(ExactMutationTransferAgentV2):
    """Keep the frozen V2 boundary and use a complete no-effect certificate."""

    method_id = "full_pact_v12_webarena_exact_mutation_v2"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.runtime = FailClosedTransactionRuntimeV12(
            self.executor,
            self.interrupt_repair_reservation,
        )

    def result(self) -> dict[str, Any]:
        result = super().result()
        result["candidate"] = "WebArena-exact-mutation-agent-v12-episode"
        result["metrics"].update(complete_public_no_effect_metrics_v12(self))
        return result
