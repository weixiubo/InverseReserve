"""PACT-v19 confirmation driver for exact intended-mutation discharge."""

from __future__ import annotations

from typing import Any

from .confirmation_agents_v18 import FullPactConfirmationDriverV18
from .pact_controller_v19 import FailClosedTransactionRuntimeV19
from .pact_grounding_v19 import goal_mutations_resolved_by_certificate_v19


def certified_scope_consumption_metrics_v19(driver: Any) -> dict[str, int]:
    checks = [
        event
        for event in driver.runtime.events
        if event.get("type") == "certified_scope_consumption_v19"
    ]
    return {
        "certified_scope_consumption_checks_v19": len(checks),
        "certified_scope_consumption_passes_v19": sum(
            event.get("allowed") is True for event in checks
        ),
        "certified_scope_consumption_failures_v19": sum(
            event.get("allowed") is False for event in checks
        ),
        "certified_scope_consumed_transactions_v19": sum(
            int(event.get("consumed_transactions", 0)) for event in checks
        ),
        "goal_mutation_consumption_passes_v19": sum(
            event.get("allowed") is True
            and any(
                kind in {"editable_field_assignment", "native_select_update"}
                for kind in event.get("consumed_kinds", ())
            )
            for event in checks
        ),
    }


class FullPactConfirmationDriverV19(FullPactConfirmationDriverV18):
    """V18 plus exact discharge of publicly certified intended mutations."""

    method_id = "full_pact_v19"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.runtime = FailClosedTransactionRuntimeV19(
            self.executor,
            self.interrupt_repair_reservation,
            self.active_restore_clearance_reservation_v16,
        )
        self._pending_commit_scope_v19: dict[str, Any] | None = None

    def audit(self, event: dict[str, Any]) -> None:
        """Consume goal mutations only after the inherited effect check passes.

        Older protocol-bound drivers cannot be edited without invalidating
        their source hashes.  V19 therefore uses the existing audit boundary:
        the fresh certificate event captures its exact public evidence and the
        following positive effect event and terminal executor outcome jointly
        authorize the new discharge.
        """

        if event.get("type") == "certified_commit_result_v8":
            certificate = event.get("certificate", {})
            grounding = (
                certificate.get("grounding", {})
                if isinstance(certificate, dict)
                else {}
            )
            self._pending_commit_scope_v19 = {
                "commit_bid": str(event.get("bid", "")),
                "executed": event.get("executed") is True,
                "halted": event.get("halted") is True,
                "terminal": event.get("terminal") is True,
                "anchor_kind": str(grounding.get("anchor_kind", "") or ""),
                "evidence_bids": tuple(
                    str(value) for value in grounding.get("evidence_bids", ())
                ),
                "active_transactions": tuple(self.runtime.active),
            }
        elif event.get("type") == "commit_effect_result_v8":
            metadata = self._pending_commit_scope_v19
            self._pending_commit_scope_v19 = None
            if (
                event.get("effective") is True
                and metadata is not None
                and metadata["executed"] is True
                and metadata["halted"] is False
                and metadata["terminal"] is True
            ):
                resolved = goal_mutations_resolved_by_certificate_v19(
                    active_transactions=tuple(metadata["active_transactions"]),
                    anchor_kind=str(metadata["anchor_kind"]),
                    evidence_bids=tuple(metadata["evidence_bids"]),
                )
                if resolved:
                    consumed = self.runtime.consume_resolved_commit_scope_v19(
                        resolved,
                        commit_bid=str(metadata["commit_bid"]),
                        anchor_kind=str(metadata["anchor_kind"]),
                        evidence_bids=tuple(metadata["evidence_bids"]),
                    )
                    if consumed:
                        set.update(self.resolved_semantic_bids, resolved)
                    event = {
                        **event,
                        "goal_mutation_resolved_semantic_bids_v19": list(resolved),
                        "goal_mutation_consumed_transactions_v19": len(consumed),
                    }
        super().audit(event)

    def _consume_resolved_commit_scope_v18(
        self, resolved_semantic_bids: tuple[str, ...]
    ) -> None:
        self.runtime.consume_resolved_commit_scope_v19(
            resolved_semantic_bids,
            commit_bid=self._latest_effective_commit_bid_v18(),
            anchor_kind="",
            evidence_bids=(),
        )

    def result(self) -> dict[str, Any]:
        result = super().result()
        result["metrics"].update(certified_scope_consumption_metrics_v19(self))
        return result


__all__ = [
    "FullPactConfirmationDriverV19",
    "certified_scope_consumption_metrics_v19",
]
