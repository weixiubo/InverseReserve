"""PACT-v20 runtime for certificate-bound goal-navigation discharge."""

from __future__ import annotations

from collections.abc import Iterable

from .pact_controller_v4 import ActiveTransactionV4
from .pact_controller_v19 import FailClosedTransactionRuntimeV19
from .pact_goal_scope_v20 import (
    EXACT_TARGET_COMMIT_ANCHOR_V20,
    GOAL_NAVIGATION_KINDS_V20,
)
from .pact_grounding_v8 import BLOCKING_TRANSACTION_KINDS_V8
from .pact_grounding_v19 import (
    GOAL_MUTATION_KINDS_V19,
    GOAL_STATE_COMMIT_ANCHOR_V19,
)


class FailClosedTransactionRuntimeV20(FailClosedTransactionRuntimeV19):
    """Consume one exact suffix supported by an effective goal certificate."""

    def consume_resolved_commit_scope_v20(
        self,
        resolved_semantic_bids: Iterable[str],
        *,
        commit_bid: str,
        anchor_kind: str,
        evidence_bids: Iterable[str],
    ) -> tuple[ActiveTransactionV4, ...]:
        self._require_live()
        resolved = frozenset(str(bid) for bid in resolved_semantic_bids)
        evidence = frozenset(str(bid) for bid in evidence_bids)
        if not resolved:
            return ()
        if not str(commit_bid):
            self._reject_scope_v20(
                "resolved commit scope lacks an effect-verified commit binding",
                commit_bid="",
                anchor_kind=anchor_kind,
                evidence=evidence,
                resolved=resolved,
            )
            return ()

        matched = [
            index
            for index, transaction in enumerate(self.active)
            if str(transaction.contract.semantic_bid) in resolved
        ]
        if not matched:
            self._reject_scope_v20(
                "resolved commit scope is absent from the active stack",
                commit_bid=commit_bid,
                anchor_kind=anchor_kind,
                evidence=evidence,
                resolved=resolved,
            )
            return ()

        start = min(matched)
        suffix = tuple(self.active[start:])
        positions = list(range(start, len(self.active)))
        suffix_scopes = {str(row.contract.semantic_bid) for row in suffix}
        contiguous = matched == positions and suffix_scopes == set(resolved)
        kinds_supported = all(
            row.contract.kind in BLOCKING_TRANSACTION_KINDS_V8
            or (
                anchor_kind == GOAL_STATE_COMMIT_ANCHOR_V19
                and row.contract.kind in GOAL_MUTATION_KINDS_V19
                and str(row.contract.semantic_bid) in evidence
            )
            or (
                anchor_kind == EXACT_TARGET_COMMIT_ANCHOR_V20
                and row.contract.kind in GOAL_NAVIGATION_KINDS_V20
                and str(row.contract.semantic_bid) in resolved
            )
            for row in suffix
        )
        if not contiguous or not kinds_supported:
            self._reject_scope_v20(
                (
                    "resolved commit scope is not one certificate-supported "
                    "contiguous active-stack suffix"
                ),
                commit_bid=commit_bid,
                anchor_kind=anchor_kind,
                evidence=evidence,
                resolved=resolved,
                matched_positions=matched,
                suffix=suffix,
            )
            return ()

        del self.active[start:]
        for transaction in suffix:
            self.completed.append(
                {
                    **transaction.planner_record(),
                    "restored": False,
                    "committed": True,
                    "trigger": (
                        "effect-verified certificate-bound scope consumption v20"
                    ),
                    "commit_bid": str(commit_bid),
                    "commit_anchor_kind": str(anchor_kind),
                }
            )
        self._audit(
            {
                "type": "certified_scope_consumption_v20",
                "allowed": True,
                "reason": (
                    "effective certified commit consumed one exact supported suffix"
                ),
                "commit_bid": str(commit_bid),
                "anchor_kind": str(anchor_kind),
                "evidence_bids": sorted(evidence),
                "resolved_semantic_bids": sorted(resolved),
                "consumed_transactions": len(suffix),
                "consumed_kinds": [row.contract.kind for row in suffix],
                "remaining_active_depth": len(self.active),
            }
        )
        return suffix

    def _reject_scope_v20(
        self,
        reason: str,
        *,
        commit_bid: str,
        anchor_kind: str,
        evidence: frozenset[str],
        resolved: frozenset[str],
        matched_positions: list[int] | None = None,
        suffix: tuple[ActiveTransactionV4, ...] = (),
    ) -> None:
        event: dict[str, object] = {
            "type": "certified_scope_consumption_v20",
            "allowed": False,
            "reason": reason,
            "commit_bid": str(commit_bid),
            "anchor_kind": str(anchor_kind),
            "evidence_bids": sorted(evidence),
            "resolved_semantic_bids": sorted(resolved),
        }
        if matched_positions is not None:
            event.update(
                {
                    "matched_positions": matched_positions,
                    "active_depth": len(self.active),
                    "suffix_kinds": [row.contract.kind for row in suffix],
                }
            )
        self._audit(event)
        self._halt(reason)


__all__ = ["FailClosedTransactionRuntimeV20"]
