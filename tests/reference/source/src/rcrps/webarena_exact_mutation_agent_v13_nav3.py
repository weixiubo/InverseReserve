"""PACT-v13 WebArena agent with bounded public navigation V3.

This successor is development-informed by the sealed navigation-v2 failures.
It changes only public observation indexing, bounded navigation recovery, and
the exact-mutation adapter's form-less edit-surface binding.  Rewards, task
identifiers, evaluator fields, hidden state, routes, and selectors remain
outside the method boundary.
"""

from __future__ import annotations

from .recovery_capacity import remaining_after_action as _remaining_capacity_after_proposal

import hashlib
from collections import Counter
from typing import Any

from .confirmation_agents_v13 import complete_public_commit_metrics_v13
from .pact_controller_v8 import inverse_action_cost_v8
from .pact_controller_v10 import interrupt_repair_action_cost_v10
from .pact_controller_v13 import (
    FailClosedTransactionRuntimeV13,
    bind_complete_public_commit_certificate_v13,
)
from .webarena_exact_mutation_agent_v1 import (
    _certificate_record,
    _restoration_record,
)
from .webarena_exact_mutation_agent_v13 import ExactMutationTransferAgentV13
from .webarena_exact_mutation_v2 import (
    certify_exact_mutation_commit_v2,
    compile_exact_mutation_goal_v2,
    compile_exact_mutation_inventory_v2,
)
from .webarena_executor_v3 import WebArenaConfirmationExecutorV3
from .webarena_public_navigation_v3 import (
    check_public_navigation_effect_v3,
    compile_public_navigation_v3,
    detect_public_recovery_signal_v3,
    navigation_messages_v3,
    resolve_public_navigation_v3,
)


class ExactMutationTransferAgentV13Nav3(ExactMutationTransferAgentV13):
    """Use indexed public observations and the bounded V3 recovery policy."""

    method_id = "full_pact_v13_webarena_exact_mutation_nav3"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.executor = WebArenaConfirmationExecutorV3(
            kwargs["environment"],
            kwargs["observation"],
            maximum_gui_actions=int(kwargs["budgets"]["maximum_gui_actions"]),
        )
        self.runtime = FailClosedTransactionRuntimeV13(
            self.executor,
            self.interrupt_repair_reservation,
        )
        self.navigation_attempt_counts: Counter[str] = Counter()
        self.raw_navigation_action_errors = 0
        self.recovered_navigation_action_errors = 0
        self.unrecovered_navigation_action_errors = 0
        self.public_recovery_signals = 0
        self.carried_public_recovery_credit = False

    def navigate_once(self) -> None:
        before = self.executor.snapshot
        before_url = str(self.executor.observation.get("url", ""))
        recovery = detect_public_recovery_signal_v3(before)
        self.public_recovery_signals += int(recovery.detected)
        carried_recovery_credit = self.carried_public_recovery_credit
        retry_authorized = bool(recovery.detected or carried_recovery_credit)
        inventory = compile_public_navigation_v3(
            before,
            current_url=before_url,
            goal=self.goal,
            attempt_counts=self.navigation_attempt_counts,
            retry_authorized=retry_authorized,
            maximum_candidates=int(
                self.budgets["maximum_navigation_candidates"]
            ),
        )
        step: dict[str, Any] = {
            "type": "public_navigation_decision_v3",
            "inventory": inventory.record(),
            "public_recovery_signal": recovery.record(),
            "carried_public_recovery_credit": carried_recovery_credit,
            "model": None,
            "resolution": None,
        }
        if not inventory.candidates:
            self.method_failure = "public navigation exposed no safe current candidate"
            self.audit(step)
            return
        messages = navigation_messages_v3(
            goal=self.goal,
            current_url=before_url,
            inventory=inventory,
            navigation_history=self.navigation_history,
            recovery_signal=recovery,
        )
        model = self.call_model(messages)
        if model is None:
            self.audit(step)
            return
        step["model"] = model
        try:
            decision = resolve_public_navigation_v3(
                inventory,
                model_output=model["raw_output"],
            )
        except Exception as error:
            self.parse_failures += 1
            self.method_failure = (
                f"navigation planner parse failed: {type(error).__name__}: {error}"
            )
            self.audit(step)
            return
        step["resolution"] = decision.record()
        self.audit(step)
        if not decision.allowed or decision.candidate is None:
            self.method_failure = "public base navigator abstained"
            return

        candidate = decision.candidate
        self.navigation_attempt_counts[candidate.state_action_key] += 1
        outcome = self.executor(candidate.action, "navigation")
        after_url = str(self.executor.observation.get("url", ""))
        effect = check_public_navigation_effect_v3(
            before=before,
            after=outcome.snapshot,
            before_url=before_url,
            after_url=after_url,
            candidate=candidate,
        )
        has_action_error = bool(outcome.action_error)
        recovered_action_error = bool(has_action_error and effect.effective)
        self.raw_navigation_action_errors += int(has_action_error)
        self.recovered_navigation_action_errors += int(recovered_action_error)
        self.unrecovered_navigation_action_errors += int(
            has_action_error and not effect.effective
        )
        after_recovery = detect_public_recovery_signal_v3(outcome.snapshot)
        retry_authorization_source = "none"
        if effect.retry_authorized:
            retry_authorization_source = (
                "current_public_recovery"
                if recovery.detected
                else "carried_public_recovery"
            )
        record = {
            **effect.record(),
            "bid": candidate.bid,
            "label": candidate.label,
            "kind": candidate.kind,
            "action_error": outcome.action_error,
            "action_error_recovered_by_public_effect": recovered_action_error,
            "public_recovery_signal_before": recovery.record(),
            "carried_public_recovery_credit_before": (
                carried_recovery_credit
            ),
            "retry_authorization_source": retry_authorization_source,
            "public_recovery_signal_after": after_recovery.record(),
            "before_url_sha256": hashlib.sha256(
                before_url.encode("utf-8")
            ).hexdigest(),
            "after_url_sha256": hashlib.sha256(
                after_url.encode("utf-8")
            ).hexdigest(),
        }
        self.carried_public_recovery_credit = bool(
            recovery.detected and effect.effective
        )
        self.navigation_effects.append(record)
        self.navigation_history.append(
            {
                "bid": candidate.bid,
                "label": candidate.label,
                "kind": candidate.kind,
                "state_action_key": effect.state_action_key,
                "attempt_key": effect.attempt_key,
                "attempt_ordinal": effect.attempt_ordinal,
                "retry_authorized": effect.retry_authorized,
                "retry_authorization_source": retry_authorization_source,
                "effective": effect.effective,
                "url_changed": effect.url_changed,
                "action_error": outcome.action_error,
                "action_error_recovered_by_public_effect": (
                    recovered_action_error
                ),
            }
        )
        if not effect.effective:
            self.quarantined_navigation_keys.add(effect.attempt_key)
        if outcome.terminal:
            self.method_failure = (
                "public navigation terminated before exact mutation"
            )

    def execute_exact_mutation(self, compilation: Any) -> None:
        """Execute PACT-v13 using the exact public edit-surface adapter V2."""

        before = self.executor.snapshot
        inventory = compile_exact_mutation_inventory_v2(
            before,
            self.goal,
            compilation=compilation,
        )
        bindings = compilation.goal_contract.payload_bindings
        if len(bindings) != 1:
            self.method_failure = (
                "exact target surface did not bind one public field"
            )
            return
        binding = bindings[0]
        contract = inventory.contract_by_bid.get(binding.bid)
        if contract is None:
            self.method_failure = "exact target field lacks a typed transaction"
            return
        inverse_reserve = inverse_action_cost_v8(contract)
        commit_action_cost = 1
        interrupt_repair_cost = interrupt_repair_action_cost_v10(contract)
        remaining_after_forward = _remaining_capacity_after_proposal(self.budgets["maximum_gui_actions"], len(self.executor.actions))
        required_after_forward = (
            inverse_reserve + commit_action_cost + interrupt_repair_cost
        )
        allowed = remaining_after_forward >= required_after_forward
        self.inverse_reservation_audits += 1
        self.audit(
            {
                "type": "inverse_budget_reservation",
                "bid": binding.bid,
                "inverse_action_cost": inverse_reserve,
                "commit_action_cost": commit_action_cost,
                "interrupt_repair_action_cost": interrupt_repair_cost,
                "required_after_forward": required_after_forward,
                "remaining_after_forward": remaining_after_forward,
                "allowed": allowed,
                "reservation_version": "PACT-v10-recovery-plus-commit",
            }
        )
        if not allowed:
            self.inverse_reservation_stops += 1
            self.method_failure = (
                "inverse, commit, and repair budget reservation stopped mutation"
            )
            return
        opened = self.runtime.transact(
            before=before,
            contract=contract,
            candidate_label=binding.label,
        )
        self.typed_transactions += 1
        if opened.restoration is not None:
            self.restorations.append(_restoration_record(opened.restoration))
        self.audit(
            {
                "type": "exact_mutation_transaction_result_v2",
                "bid": binding.bid,
                "surface": compilation.surface.record(),
                "admitted": opened.admitted,
                "reason": opened.reason,
                "interrupt_repairs": opened.interrupt_repairs,
                "halted": opened.halted,
            }
        )
        if not opened.admitted or opened.halted:
            self.method_failure = opened.reason
            return
        current = self.executor.snapshot
        fresh = compile_exact_mutation_goal_v2(self.goal, current)
        self.final_compilation = fresh
        if not fresh.allowed:
            self.method_failure = "exact mutation disappeared after typed forward"
            return
        fresh_inventory = compile_exact_mutation_inventory_v2(
            current,
            self.goal,
            compilation=fresh,
        )
        fresh_bindings = fresh.goal_contract.payload_bindings
        if len(fresh_bindings) != 1 or fresh_bindings[0].bid != binding.bid:
            self.method_failure = "exact mutation binding changed after typed forward"
            return
        submit = next(
            (
                row
                for row in fresh_inventory.candidates
                if row.bid == fresh_bindings[0].submit_bid
            ),
            None,
        )
        if submit is None:
            self.method_failure = "bound edit-surface action disappeared before commit"
            return
        certificate = certify_exact_mutation_commit_v2(
            current=current,
            compilation=fresh,
            candidate=submit,
            inventory=fresh_inventory.candidates,
            active_transactions=tuple(self.runtime.active),
            resolved_semantic_bids=tuple(
                sorted(self.resolved_exact_transaction_bids)
            ),
            quarantined_commit_keys=self.effect_ledger.frozen_quarantine(),
        )
        certificate = bind_complete_public_commit_certificate_v13(
            current,
            certificate,
        )
        self.audit(
            {
                "type": "exact_mutation_commit_certificate_v13_surface_v2",
                "bid": submit.bid,
                "certificate": _certificate_record(certificate),
                "fingerprint_scope": "all_retained_semantic_snapshot_fields",
            }
        )
        if not certificate.allowed:
            self.method_failure = certificate.reason
            return
        active_before = tuple(self.runtime.active)
        committed = self.runtime.commit(
            current=current,
            action=submit.action,
            certificate=certificate,
        )
        self.certified_commits += 1
        if not committed.executed or committed.halted or committed.result is None:
            self.method_failure = committed.reason
            return
        effect = self.effect_ledger.assess(
            before=current,
            after=committed.result.snapshot,
            action=submit.action,
            active_transactions=active_before,
            terminal=committed.result.terminal,
        )
        self.audit(
            {
                "type": "exact_mutation_commit_effect_v2",
                "bid": submit.bid,
                "effective": effect.effective,
                "reason": effect.reason,
                "quarantined": effect.quarantined,
                "key_sha256": effect.key_sha256,
            }
        )
        if committed.result.terminal:
            self.wrong_terminal_commits += 1
            self.method_failure = (
                "exact mutation commit terminated before evaluator"
            )
            return
        if not effect.effective:
            self.method_failure = effect.reason
            return
        self.resolved_exact_transaction_bids.add(binding.bid)
        self.method_commit_effective = True

    def run_policy(self) -> None:
        while not self.method_commit_effective and self.within_budget():
            compilation = compile_exact_mutation_goal_v2(
                self.goal,
                self.executor.snapshot,
            )
            self.final_compilation = compilation
            if compilation.allowed:
                self.target_form_reached = True
                self.execute_exact_mutation(compilation)
                break
            self.navigate_once()
            if self.method_failure is not None:
                break
        if not self.method_commit_effective and self.method_failure is None:
            self.method_failure = "method stopped before an effective exact commit"
        self._cleanup_failed_transaction()

    def result(self) -> dict[str, Any]:
        result = super().result()
        non_navigation_action_errors = sum(
            bool(row["last_action_error_after"])
            for row in self.executor.actions
            if row["role"] != "navigation"
        )
        raw_action_errors = (
            self.raw_navigation_action_errors + non_navigation_action_errors
        )
        unrecovered_action_errors = (
            self.unrecovered_navigation_action_errors
            + non_navigation_action_errors
        )
        result["candidate"] = "WebArena-exact-mutation-agent-v13-nav3-episode"
        result["navigation_version"] = "public_navigation_v3"
        result["observation_runtime"] = "indexed_semantic_snapshot_v1"
        result["exact_mutation_version"] = "public_edit_surface_v2"
        result["method_input"].update(
            {
                "method_received_network_log": False,
                "method_received_status_code": False,
                "method_received_css_selector": False,
            }
        )
        result["metrics"].update(complete_public_commit_metrics_v13(self))
        result["metrics"].update(
            {
                "action_errors": unrecovered_action_errors,
                "raw_action_errors": raw_action_errors,
                "recovered_navigation_action_errors": (
                    self.recovered_navigation_action_errors
                ),
                "unrecovered_action_errors": unrecovered_action_errors,
                "public_recovery_signals": self.public_recovery_signals,
                "distinct_navigation_state_actions": len(
                    self.navigation_attempt_counts
                ),
                "maximum_state_action_attempts": max(
                    self.navigation_attempt_counts.values(),
                    default=0,
                ),
            }
        )
        return result
