"""PACT-v20 confirmation driver for exact goal-terminal navigation scopes."""

from __future__ import annotations

from typing import Any

from inversereserve.contracts.pact_goal_scope_v20 import (
    GOAL_NAVIGATION_KINDS_V20,
    promote_unique_exact_target_v20,
    resolved_by_commit_v20,
    suppress_repeated_navigation_v20,
)
from inversereserve.contracts.pact_grounding_v19 import GOAL_MUTATION_KINDS_V19
from inversereserve.controllers.confirmation_agents_v18 import FullPactConfirmationDriverV18
from inversereserve.controllers.confirmation_agents_v19 import FullPactConfirmationDriverV19
from inversereserve.controllers.pact_controller_v20 import FailClosedTransactionRuntimeV20


def certified_scope_consumption_metrics_v20(driver: Any) -> dict[str, int]:
    checks = [
        event for event in driver.runtime.events if event.get("type") == "certified_scope_consumption_v20"
    ]
    return {
        "certified_scope_consumption_checks_v20": len(checks),
        "certified_scope_consumption_passes_v20": sum(event.get("allowed") is True for event in checks),
        "certified_scope_consumption_failures_v20": sum(event.get("allowed") is False for event in checks),
        "certified_scope_consumed_transactions_v20": sum(
            int(event.get("consumed_transactions", 0)) for event in checks
        ),
        "goal_navigation_consumption_passes_v20": sum(
            event.get("allowed") is True
            and any(kind in GOAL_NAVIGATION_KINDS_V20 for kind in event.get("consumed_kinds", ()))
            for event in checks
        ),
        "goal_mutation_consumption_passes_v20": sum(
            event.get("allowed") is True
            and any(kind in GOAL_MUTATION_KINDS_V19 for kind in event.get("consumed_kinds", ()))
            for event in checks
        ),
        "goal_terminal_promotions_v20": sum(
            event.get("type") == "goal_terminal_promotion_v20" for event in driver.trace
        ),
    }


class FullPactConfirmationDriverV20(FullPactConfirmationDriverV19):
    """V19 plus public exact-target promotion and navigation-scope discharge."""

    method_id = "full_pact_v20"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.runtime = FailClosedTransactionRuntimeV20(
            self.executor,
            self.interrupt_repair_reservation,
            self.active_restore_clearance_reservation_v16,
        )
        self.resolved_semantic_bids = set(self.resolved_semantic_bids)
        self._pending_commit_scope_v20: dict[str, Any] | None = None
        self._commit_contexts_v20: dict[str, dict[str, Any]] = {}
        self._last_promotion_v20: dict[str, Any] | None = None
        self._promotion_keys_v20: set[tuple[object, ...]] = set()

    def inventory(self) -> Any:
        inventory = super().inventory()
        promoted, record = promote_unique_exact_target_v20(
            self.executor.snapshot,
            inventory,
            transaction_history=(tuple(self.runtime.active) + tuple(self.runtime.completed)),
        )
        self._last_promotion_v20 = record
        return promoted

    def fresh_envelope(self, inventory: Any) -> tuple[Any, dict[str, Any], list[dict[str, Any]]]:
        current = self.executor.snapshot
        active = tuple(self.runtime.active)
        filtered = suppress_repeated_navigation_v20(
            inventory,
            active_transactions=active,
            completed_transactions=tuple(self.runtime.completed),
        )
        envelope, certificates, audit = super().fresh_envelope(filtered)
        by_bid = {row.bid: row for row in filtered.candidates}
        self._commit_contexts_v20 = {
            bid: {
                "current": current,
                "candidate": by_bid[bid],
                "certificate": certificate,
                "active_transactions": active,
            }
            for bid, certificate in certificates.items()
            if certificate.allowed and bid in by_bid
        }
        record = self._last_promotion_v20
        if record is not None:
            key = (
                current.semantic_fingerprint(),
                str(record["promoted_bid"]),
                tuple(
                    (
                        row.contract.kind,
                        row.contract.semantic_bid,
                    )
                    for row in active
                ),
            )
            if key not in self._promotion_keys_v20:
                self._promotion_keys_v20.add(key)
                FullPactConfirmationDriverV18.audit(self, dict(record))
        return envelope, certificates, audit

    def audit(self, event: dict[str, Any]) -> None:
        if event.get("type") == "certified_commit_result_v8":
            context = self._commit_contexts_v20.get(str(event.get("bid", "")))
            self._pending_commit_scope_v20 = (
                {
                    **context,
                    "commit_bid": str(event.get("bid", "")),
                    "executed": event.get("executed") is True,
                    "halted": event.get("halted") is True,
                    "terminal": event.get("terminal") is True,
                }
                if context is not None
                else None
            )
        elif event.get("type") == "commit_effect_result_v8":
            metadata = self._pending_commit_scope_v20
            self._pending_commit_scope_v20 = None
            if (
                event.get("effective") is True
                and metadata is not None
                and metadata["executed"] is True
                and metadata["halted"] is False
            ):
                certificate = metadata["certificate"]
                resolved = resolved_by_commit_v20(
                    current=metadata["current"],
                    candidate=metadata["candidate"],
                    active_transactions=tuple(metadata["active_transactions"]),
                    certificate=certificate,
                    terminal=bool(metadata["terminal"]),
                )
                if resolved:
                    grounding = certificate.grounding
                    consumed = self.runtime.consume_resolved_commit_scope_v20(
                        resolved,
                        commit_bid=str(metadata["commit_bid"]),
                        anchor_kind=str(grounding.anchor_kind or ""),
                        evidence_bids=tuple(str(value) for value in grounding.evidence_bids),
                    )
                    if consumed:
                        set.update(self.resolved_semantic_bids, resolved)
                    event = {
                        **event,
                        "resolved_semantic_bids_v20": list(resolved),
                        "consumed_transactions_v20": len(consumed),
                    }
        FullPactConfirmationDriverV18.audit(self, event)

    def _consume_resolved_commit_scope_v18(self, resolved_semantic_bids: tuple[str, ...]) -> None:
        self.runtime.consume_resolved_commit_scope_v20(
            resolved_semantic_bids,
            commit_bid=self._latest_effective_commit_bid_v18(),
            anchor_kind="",
            evidence_bids=(),
        )

    def result(self) -> dict[str, Any]:
        result = super().result()
        result["metrics"].update(certified_scope_consumption_metrics_v20(self))
        return result


__all__ = [
    "FullPactConfirmationDriverV20",
    "certified_scope_consumption_metrics_v20",
]
