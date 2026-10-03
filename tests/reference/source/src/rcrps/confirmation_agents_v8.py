"""PACT-v8 confirmation driver with effect and restoration guarantees."""

from __future__ import annotations

from .recovery_capacity import remaining_after_action as _remaining_capacity_after_proposal

from typing import Any

from .action_envelope_v7 import envelope_messages_v7, resolve_action_envelope_v7
from .action_envelope_v8 import assemble_action_envelope_v8
from .confirmation_agents_v7 import (
    FullPactConfirmationDriverV7,
    _active_records,
    _certificate_record,
)
from .effect_ledger_v8 import CommitEffectLedgerV8
from .pact_controller_v8 import (
    FailClosedTransactionRuntimeV8,
    inverse_action_cost_v8,
)
from .pact_grounding_v8 import (
    certify_commit_v8,
    resolved_by_commit_v8,
)


class FullPactConfirmationDriverV8(FullPactConfirmationDriverV7):
    method_id = "full_pact_v8"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.runtime = FailClosedTransactionRuntimeV8(self.executor)
        self.effect_ledger = CommitEffectLedgerV8()
        self.resolved_semantic_bids: set[str] = set()
        self.inverse_reservation_stops = 0
        self.inverse_reservation_audits = 0

    def fresh_envelope(
        self, inventory: Any
    ) -> tuple[Any, dict[str, Any], list[dict[str, Any]]]:
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
        return envelope, certificates, audit

    def inverse_reserve(self, candidate: Any, decision: str) -> tuple[bool, int]:
        reserve = sum(
            inverse_action_cost_v8(transaction.contract)
            for transaction in self.runtime.active
        )
        if decision == "transact":
            inventory = self.inventory()
            contract = inventory.contract_by_bid.get(candidate.bid)
            if contract is None:
                return False, reserve
            reserve += inverse_action_cost_v8(contract)
        remaining_after_action = _remaining_capacity_after_proposal(self.budgets["maximum_gui_actions"], len(self.executor.actions))
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
        return allowed, reserve

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
                "quarantined_commit_count": len(
                    self.effect_ledger.quarantined_keys
                ),
                "resolution": None,
                "model": None,
            }
            if envelope.decision == "abstain":
                resolution = resolve_action_envelope_v7(envelope)
            elif envelope.model_call_required:
                messages = envelope_messages_v7(
                    goal=self.goal,
                    goal_contract=self.goal_contract,
                    envelope=envelope,
                    active_transactions=_active_records(self.runtime),
                    completed_transactions=self.runtime.completed,
                )
                model = self.call_model(messages)
                if model is None:
                    self.audit(step)
                    break
                step["model"] = model
                try:
                    resolution = resolve_action_envelope_v7(
                        envelope, model_output=model["raw_output"]
                    )
                except Exception as error:
                    self.parse_failures += 1
                    self.method_failure = (
                        f"planner parse failed: {type(error).__name__}: {error}"
                    )
                    self.audit(step)
                    break
            else:
                resolution = resolve_action_envelope_v7(envelope)
            step["resolution"] = {
                "decision": resolution.decision,
                "bid": resolution.bid,
                "source": resolution.source,
            }
            self.audit(step)
            if resolution.decision == "abstain" or resolution.candidate is None:
                self.method_failure = f"PACT-v8 envelope abstained: {envelope.reason}"
                break
            candidate = resolution.candidate
            reserve_allowed, reserve = self.inverse_reserve(
                candidate, resolution.decision
            )
            if not reserve_allowed:
                self.inverse_reservation_stops += 1
                self.method_failure = (
                    f"inverse budget reservation stopped progress; required {reserve} GUI actions"
                )
                break
            if resolution.decision == "transact":
                contract = inventory.contract_by_bid.get(candidate.bid)
                if contract is None:
                    self.method_failure = "typed envelope row lacked a transaction contract"
                    break
                outcome = self.runtime.transact(
                    before=current,
                    contract=contract,
                    candidate_label=candidate.label,
                )
                self.typed_transactions += 1
                self.audit(
                    {
                        "type": "typed_transaction_result_v8",
                        "bid": candidate.bid,
                        "admitted": outcome.admitted,
                        "reason": outcome.reason,
                        "interrupt_repairs": outcome.interrupt_repairs,
                        "halted": outcome.halted,
                    }
                )
                if not outcome.admitted or outcome.halted:
                    self.terminal_transactions += int(self.executor.done)
                    self.method_failure = outcome.reason
                    break
                continue
            certificate = certificates.get(candidate.bid)
            if certificate is None or not certificate.allowed:
                self.method_failure = "commit envelope lacked a fresh v8 certificate"
                break
            active_before = tuple(self.runtime.active)
            outcome = self.runtime.commit(
                current=current,
                action=candidate.action,
                certificate=certificate,
            )
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
                break
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
                    current=current,
                    candidate=candidate,
                    active_transactions=active_before,
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
            if self.executor.done and not self.executor.success:
                self.wrong_terminal_commits += 1
        if not self.executor.done:
            self.cleanup_runtime(self.runtime)

    def result(self) -> dict[str, Any]:
        result = super().result()
        result["effect_ledger_v8"] = list(self.effect_ledger.records)
        result["resolved_semantic_bids_v8"] = sorted(self.resolved_semantic_bids)
        result["metrics"].update(
            {
                "commit_effect_passes": sum(
                    row["effective"] for row in self.effect_ledger.records
                ),
                "commit_effect_failures": sum(
                    not row["effective"] for row in self.effect_ledger.records
                ),
                "quarantined_commit_keys": len(
                    self.effect_ledger.quarantined_keys
                ),
                "resolved_transaction_bids": len(self.resolved_semantic_bids),
                "inverse_reservation_audits": self.inverse_reservation_audits,
                "inverse_reservation_stops": self.inverse_reservation_stops,
            }
        )
        return result
