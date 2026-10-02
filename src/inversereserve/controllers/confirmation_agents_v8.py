"""PACT-v8 confirmation driver with effect and restoration guarantees."""

from __future__ import annotations

from typing import Any

from inversereserve.contracts.action_envelope_v8 import assemble_action_envelope_v8
from inversereserve.contracts.pact_grounding_v8 import certify_commit_v8, resolved_by_commit_v8
from inversereserve.controllers.confirmation_agents_v7 import (
    FullPactConfirmationDriverV7,
    _active_records,
    _certificate_record,
)
from inversereserve.controllers.envelope_policy import admit_transaction, resolve_step
from inversereserve.controllers.pact_controller_v8 import (
    FailClosedTransactionRuntimeV8,
    inverse_action_cost_v8,
)
from inversereserve.core.effect_ledger_v8 import CommitEffectLedgerV8
from inversereserve.core.recovery_capacity import remaining_after_action as _remaining_capacity_after_proposal


class FullPactConfirmationDriverV8(FullPactConfirmationDriverV7):
    method_id = "full_pact_v8"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.runtime = FailClosedTransactionRuntimeV8(self.executor)
        self.effect_ledger = CommitEffectLedgerV8()
        self.resolved_semantic_bids: set[str] = set()
        self.inverse_reservation_stops = 0
        self.inverse_reservation_audits = 0

    def fresh_envelope(self, inventory: Any) -> tuple[Any, dict[str, Any], list[dict[str, Any]]]:
        admitted = []
        certificates = {}
        audit = []
        current = self.executor.snapshot
        active = tuple(self.runtime.active)
        resolved = tuple(sorted(self.resolved_semantic_bids))
        for candidate in inventory.candidates:
            if candidate.transaction_kind is not None:
                continue
            certificate = certify_commit_v8(
                current=current,
                goal=inventory.goal_contract,
                candidate=candidate,
                inventory=inventory.candidates,
                active_transactions=active,
                resolved_semantic_bids=resolved,
                quarantined_commit_keys=self.effect_ledger.frozen_quarantine(),
            )
            certificates[candidate.bid] = certificate
            audit.append(
                {
                    "bid": candidate.bid,
                    "allowed": certificate.allowed,
                    "anchor_kind": certificate.grounding.anchor_kind,
                    "reason": certificate.reason,
                }
            )
            if certificate.allowed:
                admitted.append(candidate.bid)
        envelope = assemble_action_envelope_v8(
            candidates=inventory.candidates,
            admitted_certificate_bids=admitted,
            active_transactions=active,
            completed_transactions=tuple(self.runtime.completed),
            resolved_semantic_bids=resolved,
        )
        return (envelope, certificates, audit)

    def inverse_reserve(self, candidate: Any, decision: str) -> tuple[bool, int]:
        reserve = sum((inverse_action_cost_v8(transaction.contract) for transaction in self.runtime.active))
        if decision == "transact":
            inventory = self.inventory()
            contract = inventory.contract_by_bid.get(candidate.bid)
            if contract is None:
                return (False, reserve)
            reserve += inverse_action_cost_v8(contract)
        remaining_after_action = _remaining_capacity_after_proposal(
            self.budgets["maximum_gui_actions"], len(self.executor.actions)
        )
        allowed = remaining_after_action >= reserve
        self.inverse_reservation_audits += 1
        self.audit(
            {
                "type": "inverse_budget_reservation",
                "decision": decision,
                "bid": candidate.bid,
                "active_inverse_cost": reserve,
                "remaining_after_action": remaining_after_action,
                "allowed": allowed,
            }
        )
        return (allowed, reserve)

    def run_policy(self) -> None:
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
                self.method_failure = f"PACT-v8 envelope abstained: {envelope.reason}"
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
            if not self._commit_policy_candidate_v8(current, candidate, certificates):
                break
        if not self.executor.done:
            self.cleanup_runtime(self.runtime)

    def result(self) -> dict[str, Any]:
        result = super().result()
        result["effect_ledger_v8"] = list(self.effect_ledger.records)
        result["resolved_semantic_bids_v8"] = sorted(self.resolved_semantic_bids)
        result["metrics"].update(
            {
                "commit_effect_passes": sum((row["effective"] for row in self.effect_ledger.records)),
                "commit_effect_failures": sum((not row["effective"] for row in self.effect_ledger.records)),
                "quarantined_commit_keys": len(self.effect_ledger.quarantined_keys),
                "resolved_transaction_bids": len(self.resolved_semantic_bids),
                "inverse_reservation_audits": self.inverse_reservation_audits,
                "inverse_reservation_stops": self.inverse_reservation_stops,
            }
        )
        return result

    def _commit_policy_candidate_v8(
        self,
        current: Any,
        candidate: Any,
        certificates: dict[str, Any],
        *,
        missing_message: str = "commit envelope lacked a fresh v8 certificate",
    ) -> bool:
        certificate = certificates.get(candidate.bid)
        if certificate is None or not certificate.allowed:
            self.method_failure = missing_message
            return False
        active_before = tuple(self.runtime.active)
        outcome = self.runtime.commit(current=current, action=candidate.action, certificate=certificate)
        self.certified_commits += 1
        self.audit(
            {
                "type": "certified_commit_result_v8",
                "bid": candidate.bid,
                "anchor_kind": certificate.grounding.anchor_kind,
                "certificate": _certificate_record(certificate),
                "executed": outcome.executed,
                "reason": outcome.reason,
                "halted": outcome.halted,
                "terminal": bool(outcome.result and outcome.result.terminal),
            }
        )
        if not outcome.executed or outcome.halted or outcome.result is None:
            self.method_failure = outcome.reason
            return False
        effect = self.effect_ledger.assess(
            before=current,
            after=outcome.result.snapshot,
            action=candidate.action,
            active_transactions=active_before,
            terminal=outcome.result.terminal or self.executor.success,
        )
        newly_resolved = ()
        if effect.effective:
            newly_resolved = resolved_by_commit_v8(
                current=current, candidate=candidate, active_transactions=active_before
            )
            self.resolved_semantic_bids.update(newly_resolved)
        self.audit(
            {
                "type": "commit_effect_result_v8",
                "bid": candidate.bid,
                "effective": effect.effective,
                "reason": effect.reason,
                "quarantined": effect.quarantined,
                "key_sha256": effect.key_sha256,
                "resolved_semantic_bids": list(newly_resolved),
            }
        )
        if self.executor.done and (not self.executor.success):
            self.wrong_terminal_commits += 1
        return True
