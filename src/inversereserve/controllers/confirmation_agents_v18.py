"""PACT-v18 confirmation driver with certified commit-scope consumption."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from inversereserve.controllers.confirmation_agents_v17 import FullPactConfirmationDriverV17
from inversereserve.controllers.pact_controller_v18 import FailClosedTransactionRuntimeV18


class _CertifiedCommitResolutionSetV18(set[str]):
    """Intercept inherited commit-resolution updates without editing old runtimes."""

    def __init__(
        self,
        driver: "FullPactConfirmationDriverV18",
        values: Iterable[str] = (),
    ) -> None:
        super().__init__(str(value) for value in values)
        self.driver = driver

    def update(self, *others: Iterable[str]) -> None:
        values = {str(value) for other in others for value in other}
        newly_resolved = tuple(sorted(values - self))
        super().update(values)
        if newly_resolved:
            self.driver._consume_resolved_commit_scope_v18(newly_resolved)


def certified_scope_consumption_metrics_v18(driver: Any) -> dict[str, int]:
    checks = [
        event for event in driver.runtime.events if event.get("type") == "certified_scope_consumption_v18"
    ]
    return {
        "certified_scope_consumption_checks_v18": len(checks),
        "certified_scope_consumption_passes_v18": sum(event.get("allowed") is True for event in checks),
        "certified_scope_consumption_failures_v18": sum(event.get("allowed") is False for event in checks),
        "certified_scope_consumed_transactions_v18": sum(
            int(event.get("consumed_transactions", 0)) for event in checks
        ),
    }


class FullPactConfirmationDriverV18(FullPactConfirmationDriverV17):
    """Keep v17 behavior and discharge only certified resolved scope suffixes."""

    method_id = "full_pact_v18"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        already_resolved = tuple(self.resolved_semantic_bids)
        self.runtime = FailClosedTransactionRuntimeV18(
            self.executor,
            self.interrupt_repair_reservation,
            self.active_restore_clearance_reservation_v16,
        )
        self.resolved_semantic_bids = _CertifiedCommitResolutionSetV18(self, already_resolved)

    def _latest_effective_commit_bid_v18(self) -> str:
        for event in reversed(self.trace):
            event_type = event.get("type")
            if event_type == "certified_commit_result_v8":
                if event.get("executed") is True and event.get("halted") is False:
                    return str(event.get("bid", ""))
            if event_type == "population_navigation_effect_result_v14":
                if event.get("effective") is True and event.get("resolution_passed") is True:
                    return str(event.get("bid", ""))
        return ""

    def _consume_resolved_commit_scope_v18(self, resolved_semantic_bids: tuple[str, ...]) -> None:
        self.runtime.consume_resolved_commit_scope_v18(
            resolved_semantic_bids,
            commit_bid=self._latest_effective_commit_bid_v18(),
        )

    def result(self) -> dict[str, Any]:
        result = super().result()
        result["metrics"].update(certified_scope_consumption_metrics_v18(self))
        return result


__all__ = [
    "FullPactConfirmationDriverV18",
    "certified_scope_consumption_metrics_v18",
]
