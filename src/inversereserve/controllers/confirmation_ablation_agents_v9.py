"""Matched PACT-v9 controls that leave the frozen full method untouched."""

from __future__ import annotations

from typing import Any

from inversereserve.contracts.action_envelope_v8 import assemble_action_envelope_v8
from inversereserve.contracts.pact_grounding_v8 import commit_attempt_key_v8, resolved_by_commit_v8
from inversereserve.controllers.confirmation_agents_v7 import (
    RawOpenLoopConfirmationDriverV7,
    _active_records,
    object_sha256,
)
from inversereserve.controllers.confirmation_agents_v9 import FullPactConfirmationDriverV9
from inversereserve.controllers.envelope_policy import admit_transaction, resolve_step


class RawOpenLoopConfirmationDriverV9(RawOpenLoopConfirmationDriverV7):
    """Version-labeled frozen raw control for a PACT-v9 matched grid."""

    method_id = "raw_open_loop_v9_matched"


class TypedNoCertificateConfirmationDriverV9(FullPactConfirmationDriverV9):
    """Remove only commit grounding/scope certificates from full PACT-v9.

    Typed compilation, v9 postconditions, transaction state, LIFO rollback,
    inverse reservation, effect assessment, and no-effect quarantine remain
    active.  Every otherwise terminal public candidate is admitted to the
    envelope unless the exact observation/stack/action effect key was already
    quarantined.  Its execution is explicitly recorded as uncertified.
    """

    method_id = "typed_no_certificate_v9"

    def fresh_envelope(self, inventory: Any) -> tuple[Any, dict[str, Any], list[dict[str, Any]]]:
        admitted = []
        audit = []
        current = self.executor.snapshot
        active = tuple(self.runtime.active)
        quarantined = self.effect_ledger.frozen_quarantine()
        for candidate in inventory.candidates:
            if candidate.transaction_kind is not None:
                continue
            try:
                key = commit_attempt_key_v8(
                    current=current, action=candidate.action, active_transactions=active
                )
            except Exception as error:
                audit.append(
                    {
                        "bid": candidate.bid,
                        "allowed": False,
                        "anchor_kind": "certificate_ablation_effect_key_failure",
                        "reason": f"effect key failed: {type(error).__name__}",
                        "effect_key_sha256": None,
                    }
                )
                continue
            allowed = key not in quarantined
            audit.append(
                {
                    "bid": candidate.bid,
                    "allowed": allowed,
                    "anchor_kind": "certificate_ablation",
                    "reason": "grounding and scope certificate removed"
                    if allowed
                    else "same observation/stack/action effect key is quarantined",
                    "effect_key_sha256": object_sha256(key),
                }
            )
            if allowed:
                admitted.append(candidate.bid)
        envelope = assemble_action_envelope_v8(
            candidates=inventory.candidates,
            admitted_certificate_bids=admitted,
            active_transactions=active,
            completed_transactions=tuple(self.runtime.completed),
            resolved_semantic_bids=tuple(sorted(self.resolved_semantic_bids)),
        )
        return (envelope, {}, audit)

    def run_policy(self) -> None:
        while not self.executor.done and self.within_budget():
            inventory = self.inventory()
            current = self.executor.snapshot
            envelope, _certificates, certificate_audit = self.fresh_envelope(inventory)
            step = {
                "type": "envelope_decision_v9_no_certificate",
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
                self.method_failure = f"no-certificate envelope abstained: {envelope.reason}"
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
                if not admit_transaction(
                    self, inventory, current, candidate, "typed_transaction_result_v9_no_certificate"
                ):
                    break
                continue
            active_before = tuple(self.runtime.active)
            result = self.executor(candidate.action, "uncertified_commit")
            self.uncertified_commits += 1
            self.audit(
                {
                    "type": "uncertified_commit_result_v9",
                    "bid": candidate.bid,
                    "operation": candidate.action.operation,
                    "action_error": result.action_error,
                    "terminal": result.terminal,
                    "success": self.executor.success,
                }
            )
            if result.action_error:
                self.method_failure = f"uncertified commit action error: {result.action_error}"
                break
            effect = self.effect_ledger.assess(
                before=current,
                after=result.snapshot,
                action=candidate.action,
                active_transactions=active_before,
                terminal=result.terminal or self.executor.success,
            )
            newly_resolved = ()
            if effect.effective:
                newly_resolved = resolved_by_commit_v8(
                    current=current, candidate=candidate, active_transactions=active_before
                )
                self.resolved_semantic_bids.update(newly_resolved)
            self.audit(
                {
                    "type": "uncertified_commit_effect_result_v9",
                    "bid": candidate.bid,
                    "effective": effect.effective,
                    "reason": effect.reason,
                    "quarantined": effect.quarantined,
                    "key_sha256": effect.key_sha256,
                    "resolved_semantic_bids": list(newly_resolved),
                }
            )
            if result.terminal and (not self.executor.success):
                self.wrong_terminal_commits += 1
        if not self.executor.done:
            self.cleanup_runtime(self.runtime)


MATCHED_CONFIRMATION_DRIVERS_V9 = {
    "raw_open_loop_v9_matched": RawOpenLoopConfirmationDriverV9,
    "typed_no_certificate_v9": TypedNoCertificateConfirmationDriverV9,
    "full_pact_v9": FullPactConfirmationDriverV9,
}
