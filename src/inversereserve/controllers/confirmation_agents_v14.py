"""PACT-v14 confirmation driver with bounded public autocomplete resolution."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from inversereserve.autocomplete_population_resolution_v14 import (
    AutocompletePopulationInspectionV14,
    certify_population_commit_v14,
    certify_population_probe_v14,
    inspect_autocomplete_population_v14,
    verify_population_resolution_effect_v14,
)
from inversereserve.contracts.pact_grounding_v8 import resolved_by_commit_v8
from inversereserve.controllers.confirmation_agents_v7 import (
    _active_records,
    _restoration_record,
)
from inversereserve.controllers.confirmation_agents_v13 import FullPactConfirmationDriverV13
from inversereserve.controllers.envelope_policy import admit_transaction, resolve_step
from inversereserve.controllers.pact_controller_v8 import inverse_action_cost_v8
from inversereserve.controllers.pact_controller_v14 import FailClosedTransactionRuntimeV14
from inversereserve.core.recovery_capacity import remaining_after_action as _remaining_capacity_after_proposal


@dataclass
class _PopulationNavigationSessionV14:
    field_bid: str
    surface_bid: str
    target_bid: str
    population_signature: tuple[tuple[object, ...], ...]
    maximum_probes: int
    probes: int = 0
    seen_selected_bids: set[str] = field(default_factory=set)


class FullPactConfirmationDriverV14(FullPactConfirmationDriverV13):
    """V13 plus a reversible scan for non-actionable autocomplete rows."""

    method_id = "full_pact_v14"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.runtime = FailClosedTransactionRuntimeV14(self.executor, self.interrupt_repair_reservation)
        self._population_session: _PopulationNavigationSessionV14 | None = None
        self.population_navigation_eligibility_checks = 0
        self.population_navigation_activations = 0
        self.population_navigation_probes = 0
        self.population_navigation_fresh_selection_passes = 0
        self.population_navigation_fresh_selection_rejections = 0
        self.population_navigation_reservation_stops = 0
        self.population_navigation_restoration_passes = 0
        self.population_navigation_commit_passes = 0
        self.population_navigation_commit_failures = 0

    def _population_reserve(self, *, action_kind: str, field_bid: str) -> bool:
        reserve = sum((inverse_action_cost_v8(transaction.contract) for transaction in self.runtime.active))
        remaining_after_action = _remaining_capacity_after_proposal(
            self.budgets["maximum_gui_actions"], len(self.executor.actions)
        )
        allowed = remaining_after_action >= reserve
        self.audit(
            {
                "type": "population_navigation_inverse_reservation_v14",
                "action_kind": action_kind,
                "field_bid": field_bid,
                "active_inverse_cost": reserve,
                "remaining_after_action": remaining_after_action,
                "allowed": allowed,
            }
        )
        if not allowed:
            self.population_navigation_reservation_stops += 1
        return allowed

    def _stop_population_navigation(self, reason: str, *, restore: bool) -> str:
        self.method_failure = f"PACT-v14 population navigation stopped: {reason}"
        if restore and (not self.executor.done) and (not self.runtime.halted) and self.runtime.active:
            outcome = self.runtime.restore_top("PACT-v14 population navigation stopped")
            self.restorations.append(_restoration_record(outcome))
            self.population_navigation_restoration_passes += int(outcome.passed)
            self.audit(
                {
                    "type": "population_navigation_restoration_v14",
                    "attempted": outcome.attempted,
                    "passed": outcome.passed,
                    "reason": outcome.reason,
                }
            )
            if not outcome.passed:
                self.method_failure = f"{self.method_failure}; restoration failed: {outcome.reason}"
        self._population_session = None
        return "stop"

    def _new_or_validate_session(
        self, inspection: AutocompletePopulationInspectionV14
    ) -> tuple[_PopulationNavigationSessionV14 | None, str | None]:
        assert inspection.field_bid is not None
        assert inspection.surface_bid is not None
        assert inspection.target_bid is not None
        session = self._population_session
        if session is None:
            session = _PopulationNavigationSessionV14(
                field_bid=inspection.field_bid,
                surface_bid=inspection.surface_bid,
                target_bid=inspection.target_bid,
                population_signature=inspection.population_signature,
                maximum_probes=len(inspection.items),
            )
            self._population_session = session
            self.population_navigation_activations += 1
            return (session, None)
        if (
            session.field_bid != inspection.field_bid
            or session.surface_bid != inspection.surface_bid
            or session.target_bid != inspection.target_bid
            or (session.population_signature != inspection.population_signature)
        ):
            return (None, "public population identity changed during navigation")
        return (session, None)

    def _commit_population_selection(
        self, *, current: Any, inspection: AutocompletePopulationInspectionV14
    ) -> str:
        candidate, certificate = certify_population_commit_v14(
            current=current,
            inspection=inspection,
            active_transactions=tuple(self.runtime.active),
            quarantined_commit_keys=self.effect_ledger.frozen_quarantine(),
        )
        if candidate is None or not certificate.allowed:
            self.population_navigation_fresh_selection_rejections += 1
            return self._stop_population_navigation(certificate.reason, restore=True)
        assert inspection.field_bid is not None
        if not self._population_reserve(
            action_kind="selected_population_enter", field_bid=inspection.field_bid
        ):
            return self._stop_population_navigation(
                "Enter would consume the registered active inverse reserve", restore=True
            )
        active_before = tuple(self.runtime.active)
        outcome = self.runtime.commit(current=current, action=candidate.action, certificate=certificate)
        self.certified_commits += 1
        self.audit(
            {
                "type": "population_navigation_commit_result_v14",
                "bid": candidate.bid,
                "target_bid": inspection.target_bid,
                "executed": outcome.executed,
                "reason": outcome.reason,
                "halted": outcome.halted,
                "terminal": bool(outcome.result and outcome.result.terminal),
            }
        )
        if not outcome.executed or outcome.halted or outcome.result is None:
            self.population_navigation_commit_failures += 1
            return self._stop_population_navigation(outcome.reason, restore=not outcome.halted)
        effect = self.effect_ledger.assess(
            before=current,
            after=outcome.result.snapshot,
            action=candidate.action,
            active_transactions=active_before,
            terminal=outcome.result.terminal or self.executor.success,
        )
        resolution = verify_population_resolution_effect_v14(
            after=outcome.result.snapshot, inspection=inspection
        )
        self.audit(
            {
                "type": "population_navigation_effect_result_v14",
                "bid": candidate.bid,
                "effective": effect.effective,
                "effect_reason": effect.reason,
                "quarantined": effect.quarantined,
                "key_sha256": effect.key_sha256,
                "resolution_passed": resolution.passed,
                "resolution_reason": resolution.reason,
                "resolution_evidence_bids": list(resolution.evidence_bids),
            }
        )
        if outcome.result.terminal and (not self.executor.success):
            self.wrong_terminal_commits += 1
        if not effect.effective or not resolution.passed:
            self.population_navigation_commit_failures += 1
            return self._stop_population_navigation(
                resolution.reason if not resolution.passed else effect.reason,
                restore=not outcome.result.terminal,
            )
        newly_resolved = resolved_by_commit_v8(
            current=current, candidate=candidate, active_transactions=active_before
        )
        if inspection.field_bid not in newly_resolved:
            self.population_navigation_commit_failures += 1
            return self._stop_population_navigation(
                "certified Enter did not resolve its active field scope", restore=not outcome.result.terminal
            )
        self.resolved_semantic_bids.update(newly_resolved)
        self.population_navigation_commit_passes += 1
        self.audit(
            {
                "type": "population_navigation_resolution_v14",
                "field_bid": inspection.field_bid,
                "target_bid": inspection.target_bid,
                "resolved_semantic_bids": list(newly_resolved),
            }
        )
        self._population_session = None
        return "continue"

    def handle_abstained_envelope(
        self, *, current: Any, inventory: Any, envelope: Any, certificates: dict[str, Any]
    ) -> str:
        del inventory
        if envelope.decision != "abstain":
            raise ValueError("population resolver received a non-abstain envelope")
        if any((certificate.allowed for certificate in certificates.values())):
            raise RuntimeError("abstain envelope contradicts an admitted standard certificate")
        self.population_navigation_eligibility_checks += 1
        inspection = inspect_autocomplete_population_v14(
            current=current,
            goal=self.goal_contract,
            active_transactions=tuple(self.runtime.active),
            resolved_semantic_bids=tuple(sorted(self.resolved_semantic_bids)),
        )
        self.audit(
            {
                "type": "population_navigation_eligibility_v14",
                "inspection": inspection.record(),
                "session_active": self._population_session is not None,
                "standard_certificate_admissions": 0,
            }
        )
        if not inspection.eligible:
            if self._population_session is None:
                return "not_handled"
            self.population_navigation_fresh_selection_rejections += 1
            return self._stop_population_navigation(inspection.reason, restore=True)
        session, session_error = self._new_or_validate_session(inspection)
        if session is None:
            self.population_navigation_fresh_selection_rejections += 1
            return self._stop_population_navigation(
                session_error or "population session validation failed", restore=True
            )
        return self._advance_population_session(current, inspection, session)

    def run_policy(self) -> None:
        """Run the frozen v13 loop with only the isolated v14 abstain branch."""
        while not self.executor.done and self.within_budget():
            inventory = self.inventory()
            current = self.executor.snapshot
            envelope, certificates, certificate_audit = self.fresh_envelope(inventory)
            step = {
                "type": "envelope_decision_v8",
                "inventory_count": len(inventory.candidates),
                "envelope": envelope.record(),
                "certificate_audit": certificate_audit,
                "active_transactions": _active_records(self.runtime),
                "resolved_semantic_bids": sorted(self.resolved_semantic_bids),
                "quarantined_commit_count": len(self.effect_ledger.quarantined_keys),
                "resolution": None,
                "model": None,
            }
            resolution = resolve_step(self, envelope, step)
            if resolution is None:
                break
            if resolution.decision == "abstain" or resolution.candidate is None:
                handling = self.handle_abstained_envelope(
                    current=current, inventory=inventory, envelope=envelope, certificates=certificates
                )
                if handling == "continue":
                    continue
                if handling == "stop":
                    break
                if handling != "not_handled":
                    raise RuntimeError(f"unknown abstained-envelope handling result: {handling}")
                self.method_failure = f"PACT-v14 envelope abstained: {envelope.reason}"
                break
            candidate = resolution.candidate
            reserve_allowed, reserve = self.inverse_reserve(candidate, resolution.decision)
            if not reserve_allowed:
                self.inverse_reservation_stops += 1
                self.method_failure = (
                    f"inverse budget reservation stopped progress; required {reserve} GUI actions"
                )
                break
            if resolution.decision == "transact":
                if not admit_transaction(self, inventory, current, candidate, "typed_transaction_result_v8"):
                    break
                continue
            if not self._commit_policy_candidate_v8(
                current,
                candidate,
                certificates,
                missing_message="commit envelope lacked a fresh v13 certificate",
            ):
                break
        if not self.executor.done:
            self.cleanup_runtime(self.runtime)

    def result(self) -> dict[str, Any]:
        result = super().result()
        result["metrics"].update(
            {
                "population_navigation_eligibility_checks": self.population_navigation_eligibility_checks,
                "population_navigation_activations": self.population_navigation_activations,
                "population_navigation_probes": self.population_navigation_probes,
                "population_navigation_fresh_selection_passes": self.population_navigation_fresh_selection_passes,
                "population_navigation_fresh_selection_rejections": self.population_navigation_fresh_selection_rejections,
                "population_navigation_reservation_stops": self.population_navigation_reservation_stops,
                "population_navigation_restoration_passes": self.population_navigation_restoration_passes,
                "population_navigation_commit_passes": self.population_navigation_commit_passes,
                "population_navigation_commit_failures": self.population_navigation_commit_failures,
            }
        )
        return result

    def _advance_population_session(self, current: Any, inspection: Any, session: Any) -> str:
        selected_bid = inspection.selected_bid
        if selected_bid == inspection.target_bid:
            self.population_navigation_fresh_selection_passes += 1
            return self._commit_population_selection(current=current, inspection=inspection)
        if session.probes > 0 and selected_bid is None:
            self.population_navigation_fresh_selection_rejections += 1
            return self._stop_population_navigation(
                "ArrowDown produced no unique fresh public selected-state marker", restore=True
            )
        if selected_bid is not None and selected_bid in session.seen_selected_bids:
            self.population_navigation_fresh_selection_rejections += 1
            return self._stop_population_navigation(
                "public selection cycled before reaching the goal-bound item", restore=True
            )
        if session.probes >= session.maximum_probes:
            self.population_navigation_fresh_selection_rejections += 1
            return self._stop_population_navigation(
                "bounded probe population was exhausted without target selection", restore=True
            )
        if selected_bid is not None:
            session.seen_selected_bids.add(selected_bid)
        assert inspection.field_bid is not None
        if not self._population_reserve(action_kind="arrow_down_probe", field_bid=inspection.field_bid):
            return self._stop_population_navigation(
                "ArrowDown would consume the registered active inverse reserve", restore=True
            )
        certificate = certify_population_probe_v14(
            current=current, inspection=inspection, active_transactions=tuple(self.runtime.active)
        )
        if not certificate.allowed:
            self.population_navigation_fresh_selection_rejections += 1
            return self._stop_population_navigation(certificate.reason, restore=True)
        outcome = self.runtime.execute_population_probe(current=current, certificate=certificate)
        self.audit(
            {
                "type": "population_navigation_probe_result_v14",
                "field_bid": inspection.field_bid,
                "probe_index": session.probes,
                "executed": outcome.executed,
                "reason": outcome.reason,
                "halted": outcome.halted,
            }
        )
        if not outcome.executed or outcome.halted:
            self.population_navigation_fresh_selection_rejections += 1
            return self._stop_population_navigation(outcome.reason, restore=not outcome.halted)
        session.probes += 1
        self.population_navigation_probes += 1
        return "continue"


__all__ = ["FullPactConfirmationDriverV14"]
