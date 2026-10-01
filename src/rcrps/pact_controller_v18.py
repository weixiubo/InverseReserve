"""PACT-v18 runtime with certified consumption of committed GUI scopes.

An effective, goal-grounded commit can intentionally close a transient GUI
surface whose transactions share one semantic scope.  V18 discharges such
transactions only when they form a contiguous active-stack suffix and belong
to the explicitly supported blocking kinds.  Everything else remains active
and the runtime halts fail closed.
"""

from __future__ import annotations

from collections.abc import Iterable

from .pact_controller_v4 import ActiveTransactionV4
from .pact_controller_v17 import FailClosedTransactionRuntimeV17
from .pact_grounding_v8 import BLOCKING_TRANSACTION_KINDS_V8


class FailClosedTransactionRuntimeV18(FailClosedTransactionRuntimeV17):
    """Consume only an effect-verified commit's contiguous resolved suffix."""

    def consume_resolved_commit_scope_v18(
        self,
        resolved_semantic_bids: Iterable[str],
        *,
        commit_bid: str,
    ) -> tuple[ActiveTransactionV4, ...]:
        self._require_live()
        resolved = frozenset(str(bid) for bid in resolved_semantic_bids)
        if not resolved:
            return ()
        if not str(commit_bid):
            reason = "resolved commit scope lacks an effect-verified commit binding"
            self._audit(
                {
                    "type": "certified_scope_consumption_v18",
                    "allowed": False,
                    "reason": reason,
                    "commit_bid": "",
                    "resolved_semantic_bids": sorted(resolved),
                }
            )
            self._halt(reason)
            return ()

        matched = [
            index
            for index, transaction in enumerate(self.active)
            if str(transaction.contract.semantic_bid) in resolved
        ]
        if not matched:
            reason = "resolved commit scope is absent from the active stack"
            self._audit(
                {
                    "type": "certified_scope_consumption_v18",
                    "allowed": False,
                    "reason": reason,
                    "commit_bid": str(commit_bid),
                    "resolved_semantic_bids": sorted(resolved),
                }
            )
            self._halt(reason)
            return ()

        start = min(matched)
        suffix = tuple(self.active[start:])
        suffix_positions = list(range(start, len(self.active)))
        suffix_scopes = {str(row.contract.semantic_bid) for row in suffix}
        kinds_supported = all(
            row.contract.kind in BLOCKING_TRANSACTION_KINDS_V8 for row in suffix
        )
        contiguous = matched == suffix_positions and suffix_scopes == set(resolved)
        if not contiguous or not kinds_supported:
            reason = (
                "resolved commit scope is not one supported contiguous active-stack suffix"
            )
            self._audit(
                {
                    "type": "certified_scope_consumption_v18",
                    "allowed": False,
                    "reason": reason,
                    "commit_bid": str(commit_bid),
                    "resolved_semantic_bids": sorted(resolved),
                    "matched_positions": matched,
                    "active_depth": len(self.active),
                    "suffix_kinds": [row.contract.kind for row in suffix],
                }
            )
            self._halt(reason)
            return ()

        del self.active[start:]
        for transaction in suffix:
            self.completed.append(
                {
                    **transaction.planner_record(),
                    "restored": False,
                    "committed": True,
                    "trigger": "effect-verified certified scope consumption v18",
                    "commit_bid": str(commit_bid),
                }
            )
        self._audit(
            {
                "type": "certified_scope_consumption_v18",
                "allowed": True,
                "reason": "effective certified commit consumed one contiguous scope suffix",
                "commit_bid": str(commit_bid),
                "resolved_semantic_bids": sorted(resolved),
                "consumed_transactions": len(suffix),
                "consumed_kinds": [row.contract.kind for row in suffix],
                "remaining_active_depth": len(self.active),
            }
        )
        return suffix


__all__ = ["FailClosedTransactionRuntimeV18"]
