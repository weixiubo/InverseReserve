"""PACT-v15 WebArena agent with scoped mutation and row navigation V5."""

from __future__ import annotations

from .recovery_capacity import remaining_after_action as _remaining_capacity_after_proposal

import hashlib
from typing import Any

from .pact_controller_v8 import inverse_action_cost_v8
from .pact_controller_v10 import interrupt_repair_action_cost_v10
from .pact_controller_v13 import bind_complete_public_commit_certificate_v13
from .webarena_exact_mutation_agent_v1 import (
    _certificate_record,
    _restoration_record,
)
from .webarena_exact_mutation_agent_v14_nav4 import (
    ExactMutationTransferAgentV14Nav4,
)
from .webarena_exact_mutation_v4 import (
    certify_exact_mutation_commit_v4,
    compile_exact_mutation_goal_v4,
    compile_exact_mutation_inventory_v4,
)
from .webarena_public_navigation_v3 import (
    check_public_navigation_effect_v3,
    detect_public_recovery_signal_v3,
    navigation_messages_v3,
)
from .webarena_public_navigation_v4 import (
    PublicNavigationDecisionV4,
    match_public_navigation_signature_v4,
    public_navigation_signature_v4,
    quoted_entity_navigation_decision_v4,
    resolve_public_navigation_v4,
)
from .webarena_public_navigation_v5 import (
    compile_public_navigation_v5,
    opened_row_edit_decision_v5,
    quoted_entity_row_action_decision_v5,
)


class ExactMutationTransferAgentV15Nav5(ExactMutationTransferAgentV14Nav4):
    """Use only bounded public semantics to close the V4 development failures."""

    method_id = "full_pact_v15_webarena_exact_mutation_nav5"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.pending_row_edit = False
        self.quoted_entity_row_action_bindings = 0
        self.opened_row_edit_bindings = 0
        self.scoped_field_bindings = 0

    def _deterministic_navigation_decision(
        self,
        *,
        inventory: Any,
        recovery_detected: bool,
    ) -> PublicNavigationDecisionV4 | None:
        if (
            not recovery_detected
            and self.recovery_route_captured
            and not self.recovery_route_replay_used
            and self.recovery_route
        ):
            self.recovery_replay_queue = list(self.recovery_route)
            self.recovery_route_replay_used = True
        if self.recovery_replay_queue:
            candidate = match_public_navigation_signature_v4(
                inventory, self.recovery_replay_queue[0]
            )
            if candidate is None:
                self.method_failure = (
                    "public recovery route lost its unique semantic match"
                )
                return None
            return PublicNavigationDecisionV4(
                "click",
                candidate,
                "one frozen public route signature matched one current control",
                "recovery_route_replay",
            )

        if self.pending_row_edit:
            decision = opened_row_edit_decision_v5(inventory)
            if decision is None:
                self.method_failure = (
                    "opened public row action did not expose one exact Edit control"
                )
            return decision

        row_decision = quoted_entity_row_action_decision_v5(inventory)
        if row_decision is not None:
            return row_decision
        row_evidence = inventory.row_action_binding
        if row_evidence.entity_bid is not None and row_evidence.row_bids:
            self.method_failure = (
                "quoted public row has no unique standard action disclosure"
            )
            return None
        return quoted_entity_navigation_decision_v4(self.goal, inventory)

    def navigate_once(self) -> None:
        before = self.executor.snapshot
        before_url = str(self.executor.observation.get("url", ""))
        recovery = detect_public_recovery_signal_v3(before)
        self.public_recovery_signals += int(recovery.detected)
        if recovery.detected:
            self._capture_recovery_route()
            if self.recovery_route_replay_used:
                self.method_failure = (
                    "replayed public route returned to a recovery page"
                )
                self.audit(
                    {
                        "type": "public_navigation_decision_v5",
                        "inventory": None,
                        "public_recovery_signal": recovery.record(),
                        "planner_source": "repeated_recovery_stop",
                        "model": None,
                        "resolution": None,
                    }
                )
                return

        carried_recovery_credit = self.carried_public_recovery_credit
        retry_authorized = bool(recovery.detected or carried_recovery_credit)
        inventory = compile_public_navigation_v5(
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
            "type": "public_navigation_decision_v5",
            "inventory": inventory.record(),
            "public_recovery_signal": recovery.record(),
            "carried_public_recovery_credit": carried_recovery_credit,
            "recovery_route": [row.record() for row in self.recovery_route],
            "recovery_replay_remaining": [
                row.record() for row in self.recovery_replay_queue
            ],
            "pending_row_edit": self.pending_row_edit,
            "planner_source": None,
            "model": None,
            "resolution": None,
        }
        if not inventory.candidates:
            self.method_failure = (
                "public navigation exposed no safe current candidate"
            )
            self.audit(step)
            return

        decision = self._deterministic_navigation_decision(
            inventory=inventory,
            recovery_detected=recovery.detected,
        )
        if self.method_failure is not None:
            step["planner_source"] = "deterministic_fail_closed"
            self.audit(step)
            return
        model = None
        if decision is None:
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
                decision = resolve_public_navigation_v4(
                    inventory,
                    model_output=model["raw_output"],
                    navigation_history=self.navigation_history,
                )
            except Exception as error:
                self.parse_failures += 1
                self.method_failure = (
                    "navigation planner parse failed: "
                    f"{type(error).__name__}: {error}"
                )
                self.audit(step)
                return
        step["planner_source"] = decision.resolution_source
        step["resolution"] = decision.record()
        self.audit(step)
        if not decision.allowed or decision.candidate is None:
            self.method_failure = "public base navigator abstained"
            return

        candidate = decision.candidate
        signature = public_navigation_signature_v4(candidate)
        replay_step = decision.resolution_source == "recovery_route_replay"
        if replay_step:
            self.recovery_replay_queue.pop(0)
            self.recovery_route_replay_steps += 1
        self.stable_semantic_rebinds += int(
            decision.resolution_source == "stable_semantic_rebind"
        )
        self.quoted_entity_bindings += int(
            decision.resolution_source == "unique_quoted_entity"
        )
        self.quoted_entity_row_action_bindings += int(
            decision.resolution_source == "quoted_entity_row_action"
        )
        self.opened_row_edit_bindings += int(
            decision.resolution_source == "opened_row_edit"
        )

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
            "href": candidate.href,
            "stable_signature": signature.record(),
            "resolution_source": decision.resolution_source,
            "action_error": outcome.action_error,
            "action_error_recovered_by_public_effect": recovered_action_error,
            "public_recovery_signal_before": recovery.record(),
            "carried_public_recovery_credit_before": carried_recovery_credit,
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
                "href": candidate.href,
                "stable_signature": signature.record(),
                "resolution_source": decision.resolution_source,
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
                "public_recovery_signal_before": recovery.record(),
                "public_recovery_signal_after": after_recovery.record(),
            }
        )
        if effect.effective:
            if decision.resolution_source == "quoted_entity_row_action":
                self.pending_row_edit = True
            elif decision.resolution_source == "opened_row_edit":
                self.pending_row_edit = False
        else:
            self.quarantined_navigation_keys.add(effect.attempt_key)
            if replay_step:
                self.method_failure = (
                    "public recovery route replay produced zero public effect"
                )
        if outcome.terminal:
            self.method_failure = (
                "public navigation terminated before exact mutation"
            )

    def execute_exact_mutation(self, compilation: Any) -> None:
        before = self.executor.snapshot
        inventory = compile_exact_mutation_inventory_v4(
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
                "type": "exact_mutation_transaction_result_v4",
                "bid": binding.bid,
                "surface": compilation.surface.record(),
                "projection": compilation.projection.record(),
                "scoped_binding": (
                    None
                    if compilation.scoped_binding is None
                    else compilation.scoped_binding.record()
                ),
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
        fresh = compile_exact_mutation_goal_v4(self.goal, current)
        self.final_compilation = fresh
        if not fresh.allowed:
            self.method_failure = "exact mutation disappeared after typed forward"
            return
        fresh_inventory = compile_exact_mutation_inventory_v4(
            current,
            self.goal,
            compilation=fresh,
        )
        fresh_bindings = fresh.goal_contract.payload_bindings
        if len(fresh_bindings) != 1 or fresh_bindings[0].bid != binding.bid:
            self.method_failure = (
                "exact mutation binding changed after typed forward"
            )
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
            self.method_failure = (
                "bound edit-surface action disappeared before commit"
            )
            return
        certificate = certify_exact_mutation_commit_v4(
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
            current, certificate
        )
        self.audit(
            {
                "type": "exact_mutation_commit_certificate_v15_surface_v4",
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
                "type": "exact_mutation_commit_effect_v4",
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
            compilation = compile_exact_mutation_goal_v4(
                self.goal, self.executor.snapshot
            )
            self.final_compilation = compilation
            if compilation.allowed:
                self.target_form_reached = True
                self.scoped_field_bindings += int(
                    compilation.scoped_binding is not None
                    and compilation.scoped_binding.winning_bid is not None
                )
                self.execute_exact_mutation(compilation)
                break
            self.navigate_once()
            if self.method_failure is not None:
                break
        if not self.method_commit_effective and self.method_failure is None:
            self.method_failure = (
                "method stopped before an effective exact commit"
            )
        self._cleanup_failed_transaction()

    def result(self) -> dict[str, Any]:
        result = super().result()
        result["candidate"] = "WebArena-exact-mutation-agent-v15-nav5-episode"
        result["navigation_version"] = "public_navigation_v5"
        result["exact_mutation_version"] = "public_edit_surface_v4"
        result["metrics"].update(
            {
                "quoted_entity_row_action_bindings": (
                    self.quoted_entity_row_action_bindings
                ),
                "opened_row_edit_bindings": self.opened_row_edit_bindings,
                "scoped_field_bindings": self.scoped_field_bindings,
                "pending_row_edit_at_stop": self.pending_row_edit,
            }
        )
        return result
