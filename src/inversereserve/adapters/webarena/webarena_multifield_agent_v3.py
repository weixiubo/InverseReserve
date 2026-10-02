"""WebArena multi-field InverseReserve with declared field restoration."""

from __future__ import annotations

from typing import Any

from inversereserve.adapters.webarena.webarena_field_scoped_restoration_v1 import (
    FIELD_RESTORATION_PROJECTION_V1,
    FailClosedWebArenaFieldRuntimeV1,
)
from inversereserve.adapters.webarena.webarena_multifield_agent_v2 import (
    MultiFieldInverseReserveAgentV2 as MultiFieldInverseReserveAgentV2,
)


class MultiFieldInverseReserveAgentV3(MultiFieldInverseReserveAgentV2):
    """Keep V2 admission and verify each editable field at its owned scope."""

    method_id = "inversereserve_webarena_multifield_v3"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.runtime = FailClosedWebArenaFieldRuntimeV1(self.executor, self.interrupt_repair_reservation)

    def result(self) -> dict[str, Any]:
        result = super().result()
        result["candidate"] = "WebArena-multifield-InverseReserve-v3-episode"
        result["restoration_projection_version"] = FIELD_RESTORATION_PROJECTION_V1
        return result


__all__ = ["MultiFieldInverseReserveAgentV3"]
