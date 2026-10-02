"""Controller-facing types for RC-RPS.

This module deliberately contains no evaluator labels. In particular, a
preview observation never carries a candidate, target, family, box, or success
identifier.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class PreviewObservation:
    """The complete black-box observation returned to the controller."""

    point: tuple[float, float]
    positive: bool
    evidence: str


@dataclass(frozen=True)
class QueryEvent:
    """One controller query without simulator-only evaluation labels."""

    query_index: int
    point: tuple[float, float]
    pool_index: int | None
    source: str
    query_kind: str
    positive: bool
    evidence: str

    def public_dict(self) -> dict[str, Any]:
        return {
            "query_index": self.query_index,
            "point": [round(self.point[0], 3), round(self.point[1], 3)],
            "pool_index": self.pool_index,
            "source": self.source,
            "query_kind": self.query_kind,
            "positive": self.positive,
            "evidence_sha256": (
                hashlib.sha256(self.evidence.encode("utf-8")).hexdigest() if self.evidence else ""
            ),
        }
