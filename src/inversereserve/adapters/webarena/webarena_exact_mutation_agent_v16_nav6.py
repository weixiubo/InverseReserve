"""PACT-v16 WebArena agent with bounded form reveal and canonical rows."""

from __future__ import annotations

import hashlib
from typing import Any

from inversereserve.adapters.webarena.webarena_exact_mutation_agent_v15_nav5 import (
    ExactMutationTransferAgentV15Nav5,
)
from inversereserve.adapters.webarena.webarena_public_navigation_v3 import (
    check_public_navigation_effect_v3,
    detect_public_recovery_signal_v3,
    navigation_messages_v3,
)
from inversereserve.adapters.webarena.webarena_public_navigation_v4 import (
    public_navigation_signature_v4,
    resolve_public_navigation_v4,
)
from inversereserve.adapters.webarena.webarena_public_navigation_v6 import (
    compile_public_navigation_v6,
    exact_form_reveal_decision_v6,
)


class ExactMutationTransferAgentV16Nav6(ExactMutationTransferAgentV15Nav5):
    """Close only the two complete public navigation-v5 failures."""

    method_id = "full_pact_v16_webarena_exact_mutation_nav6"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.exact_form_boundary_reveals = 0
        self.canonical_row_action_bindings = 0

    def _deterministic_navigation_decision(self, *, inventory: Any, recovery_detected: bool) -> Any:
        if self.recovery_replay_queue or self.pending_row_edit:
            return super()._deterministic_navigation_decision(
                inventory=inventory, recovery_detected=recovery_detected
            )
        reveal = exact_form_reveal_decision_v6(inventory)
        if reveal is not None:
            return reveal
        evidence = inventory.exact_form_reveal
        if evidence.target_bid is not None and evidence.form_bid is not None:
            self.method_failure = "rendered exact form has no one-shot joint public reveal"
            return None
        return super()._deterministic_navigation_decision(
            inventory=inventory, recovery_detected=recovery_detected
        )

    def navigate_once(self) -> None:
        before = self.executor.snapshot
        before_url = str(self.executor.observation.get("url", ""))
        recovery = detect_public_recovery_signal_v3(before)
        self.public_recovery_signals += int(recovery.detected)
        if recovery.detected:
            self._capture_recovery_route()
            if self.recovery_route_replay_used:
                self.method_failure = "replayed public route returned to a recovery page"
                self.audit(
                    {
                        "type": "public_navigation_decision_v6",
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
        height, width = self.executor.observation["screenshot"].shape[:2]
        inventory = compile_public_navigation_v6(
            before,
            current_url=before_url,
            goal=self.goal,
            viewport_width=int(width),
            viewport_height=int(height),
            attempt_counts=self.navigation_attempt_counts,
            retry_authorized=retry_authorized,
            maximum_candidates=int(self.budgets["maximum_navigation_candidates"]),
        )
        step: dict[str, Any] = {
            "type": "public_navigation_decision_v6",
            "inventory": inventory.record(),
            "public_recovery_signal": recovery.record(),
            "carried_public_recovery_credit": carried_recovery_credit,
            "recovery_route": [row.record() for row in self.recovery_route],
            "recovery_replay_remaining": [row.record() for row in self.recovery_replay_queue],
            "pending_row_edit": self.pending_row_edit,
            "planner_source": None,
            "model": None,
            "resolution": None,
        }
        if not inventory.candidates:
            self.method_failure = "public navigation exposed no safe current candidate"
            self.audit(step)
            return
        decision = self._deterministic_navigation_decision(
            inventory=inventory, recovery_detected=recovery.detected
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
                    inventory, model_output=model["raw_output"], navigation_history=self.navigation_history
                )
            except Exception as error:
                self.parse_failures += 1
                self.method_failure = f"navigation planner parse failed: {type(error).__name__}: {error}"
                self.audit(step)
                return
        step["planner_source"] = decision.resolution_source
        step["resolution"] = decision.record()
        self.audit(step)
        if not decision.allowed or decision.candidate is None:
            self.method_failure = "public base navigator abstained"
            return
        self._execute_navigation_v16_nav6(
            before, before_url, carried_recovery_credit, decision, inventory, recovery
        )

    def result(self) -> dict[str, Any]:
        result = super().result()
        result["candidate"] = "WebArena-exact-mutation-agent-v16-nav6-episode"
        result["navigation_version"] = "public_navigation_v6"
        result["exact_mutation_version"] = "public_edit_surface_v4_with_form_reveal_v6"
        result["metrics"].update(
            {
                "exact_form_boundary_reveals": self.exact_form_boundary_reveals,
                "canonical_row_action_bindings": self.canonical_row_action_bindings,
            }
        )
        return result

    def _execute_navigation_v16_nav6(
        self,
        before: Any,
        before_url: Any,
        carried_recovery_credit: Any,
        decision: Any,
        inventory: Any,
        recovery: Any,
    ) -> None:
        """Execute the chosen route and record its recovery/effect outcome."""
        candidate = decision.candidate
        signature = public_navigation_signature_v4(candidate)
        replay_step = decision.resolution_source == "recovery_route_replay"
        if replay_step:
            self.recovery_replay_queue.pop(0)
            self.recovery_route_replay_steps += 1
        self.stable_semantic_rebinds += int(decision.resolution_source == "stable_semantic_rebind")
        self.quoted_entity_bindings += int(decision.resolution_source == "unique_quoted_entity")
        self.quoted_entity_row_action_bindings += int(
            decision.resolution_source == "quoted_entity_row_action"
        )
        self.opened_row_edit_bindings += int(decision.resolution_source == "opened_row_edit")
        self.exact_form_boundary_reveals += int(decision.resolution_source == "exact_form_boundary_reveal")
        self.canonical_row_action_bindings += int(
            decision.resolution_source == "quoted_entity_row_action"
            and len(inventory.row_action_binding.row_action_match_bids) > 1
            and (inventory.row_action_binding.action_bid is not None)
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
        self.unrecovered_navigation_action_errors += int(has_action_error and (not effect.effective))
        after_recovery = detect_public_recovery_signal_v3(outcome.snapshot)
        retry_authorization_source = "none"
        if effect.retry_authorized:
            retry_authorization_source = (
                "current_public_recovery" if recovery.detected else "carried_public_recovery"
            )
        record = {
            **effect.record(),
            "bid": candidate.bid,
            "label": candidate.label,
            "kind": candidate.kind,
            "href": candidate.href,
            "stable_signature": signature.record(),
            "resolution_source": decision.resolution_source,
            "action_operation": candidate.action.operation,
            "action_error": outcome.action_error,
            "action_error_recovered_by_public_effect": recovered_action_error,
            "public_recovery_signal_before": recovery.record(),
            "carried_public_recovery_credit_before": carried_recovery_credit,
            "retry_authorization_source": retry_authorization_source,
            "public_recovery_signal_after": after_recovery.record(),
            "before_url_sha256": hashlib.sha256(before_url.encode("utf-8")).hexdigest(),
            "after_url_sha256": hashlib.sha256(after_url.encode("utf-8")).hexdigest(),
        }
        self.carried_public_recovery_credit = bool(recovery.detected and effect.effective)
        self.navigation_effects.append(record)
        self.navigation_history.append(
            {
                "bid": candidate.bid,
                "label": candidate.label,
                "kind": candidate.kind,
                "href": candidate.href,
                "stable_signature": signature.record(),
                "resolution_source": decision.resolution_source,
                "action_operation": candidate.action.operation,
                "state_action_key": effect.state_action_key,
                "attempt_key": effect.attempt_key,
                "attempt_ordinal": effect.attempt_ordinal,
                "retry_authorized": effect.retry_authorized,
                "retry_authorization_source": retry_authorization_source,
                "effective": effect.effective,
                "url_changed": effect.url_changed,
                "action_error": outcome.action_error,
                "action_error_recovered_by_public_effect": recovered_action_error,
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
                self.method_failure = "public recovery route replay produced zero public effect"
            elif decision.resolution_source == "exact_form_boundary_reveal":
                self.method_failure = "public exact form reveal produced zero public effect"
        if outcome.terminal:
            self.method_failure = "public navigation terminated before exact mutation"
