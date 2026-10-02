"""End-to-end public agent for the bounded WebArena exact-mutation slice.

A conservative base navigator reaches a target form using only public
same-origin links or non-submit controls.  Once the exact field is visible,
PACT-v9 exclusively executes the typed fill, verifies its public
postcondition, reserves the inverse, and authorizes the bound same-form action
with a fresh certificate.  Official evaluator inputs and task IDs remain in
the harness and are never accepted by this class.
"""

from __future__ import annotations

from .recovery_capacity import remaining_after_action as _remaining_capacity_after_proposal

import hashlib
import json
import time
from dataclasses import asdict
from typing import Any, Callable

from .confirmation_agents_v7 import object_sha256
from .effect_ledger_v8 import CommitEffectLedgerV8
from .pact_controller_v8 import inverse_action_cost_v8
from .pact_controller_v9 import FailClosedTransactionRuntimeV9
from .webarena_exact_mutation_v1 import (
    certify_exact_mutation_commit_v1,
    compile_exact_mutation_goal_v1,
    compile_exact_mutation_inventory_v1,
)
from .webarena_executor_v1 import WebArenaConfirmationExecutorV1
from .webarena_public_navigation_v1 import (
    check_public_navigation_effect_v1,
    compile_public_navigation_v1,
    navigation_messages_v1,
    resolve_public_navigation_v1,
)


PlannerGenerateV1 = Callable[[list[dict[str, str]]], dict[str, Any]]


def _active_records(runtime: FailClosedTransactionRuntimeV9) -> list[dict[str, Any]]:
    return [transaction.planner_record() for transaction in runtime.active]


def _restoration_record(outcome: Any) -> dict[str, Any]:
    return {
        "attempted": outcome.attempted,
        "passed": outcome.passed,
        "reason": outcome.reason,
        "check": asdict(outcome.check) if outcome.check is not None else None,
        "final_snapshot_sha256": (
            object_sha256(outcome.final_snapshot.semantic_fingerprint())
            if outcome.final_snapshot is not None
            else None
        ),
    }


def _certificate_record(certificate: Any) -> dict[str, Any]:
    return {
        "allowed": certificate.allowed,
        "reason": certificate.reason,
        "grounding": asdict(certificate.grounding),
        "certified_action": (
            asdict(certificate.certified_action)
            if certificate.certified_action is not None
            else None
        ),
        "observation_fingerprint_sha256": object_sha256(
            certificate.observation_fingerprint
        ),
        "active_stack_signature": certificate.active_stack_signature,
    }


class ExactMutationTransferAgentV1:
    """Public-only base navigation followed by one exact PACT transaction."""

    method_id = "full_pact_v9_webarena_exact_mutation_v1"

    def __init__(
        self,
        *,
        environment: Any,
        observation: dict[str, Any],
        budgets: dict[str, Any],
        planner_generate: PlannerGenerateV1,
    ) -> None:
        required = {
            "maximum_gui_actions",
            "maximum_planner_calls",
            "maximum_wall_seconds",
            "maximum_navigation_candidates",
        }
        if set(budgets) != required:
            raise ValueError("WebArena exact-mutation budget shape changed")
        if int(budgets["maximum_gui_actions"]) < 3:
            raise ValueError("exact mutation needs forward, inverse reserve, and commit")
        self.budgets = dict(budgets)
        self.goal = str(observation["goal"])
        self.executor = WebArenaConfirmationExecutorV1(
            environment,
            observation,
            maximum_gui_actions=int(budgets["maximum_gui_actions"]),
        )
        self.planner_generate = planner_generate
        self.runtime = FailClosedTransactionRuntimeV9(self.executor)
        self.effect_ledger = CommitEffectLedgerV8()
        self.trace: list[dict[str, Any]] = []
        self.navigation_history: list[dict[str, Any]] = []
        self.navigation_effects: list[dict[str, Any]] = []
        self.quarantined_navigation_keys: set[str] = set()
        self.restorations: list[dict[str, Any]] = []
        self.resolved_exact_transaction_bids: set[str] = set()
        self.planner_calls = 0
        self.planner_actual_calls = 0
        self.planner_cache_hits = 0
        self.parse_failures = 0
        self.typed_transactions = 0
        self.certified_commits = 0
        self.inverse_reservation_audits = 0
        self.inverse_reservation_stops = 0
        self.wrong_terminal_commits = 0
        self.target_form_reached = False
        self.method_commit_effective = False
        self.method_failure: str | None = None
        self.started = time.monotonic()
        self.final_compilation: Any | None = None

    def audit(self, event: dict[str, Any]) -> None:
        self.trace.append({"event_index": len(self.trace), **event})

    def within_budget(self) -> bool:
        if len(self.executor.actions) >= int(self.budgets["maximum_gui_actions"]):
            self.method_failure = "GUI action budget exhausted"
            return False
        if self.planner_calls >= int(self.budgets["maximum_planner_calls"]):
            self.method_failure = "planner call budget exhausted"
            return False
        if time.monotonic() - self.started > float(
            self.budgets["maximum_wall_seconds"]
        ):
            self.method_failure = "wall-clock budget exhausted"
            return False
        return True

    def call_model(self, messages: list[dict[str, str]]) -> dict[str, Any] | None:
        if self.planner_calls >= int(self.budgets["maximum_planner_calls"]):
            self.method_failure = "planner call budget exhausted"
            return None
        try:
            output = self.planner_generate(messages)
        except Exception as error:
            self.method_failure = (
                f"planner generation failed: {type(error).__name__}: {error}"
            )
            return None
        self.planner_calls += 1
        self.planner_cache_hits += int(bool(output["cache_hit"]))
        self.planner_actual_calls += int(not bool(output["cache_hit"]))
        if time.monotonic() - self.started > float(
            self.budgets["maximum_wall_seconds"]
        ):
            self.method_failure = "wall-clock budget exhausted after planner call"
            return None
        return {
            "messages_sha256": object_sha256(messages),
            "raw_output": str(output["raw_output"]),
            "input_tokens": int(output["input_tokens"]),
            "generated_tokens": int(output["generated_tokens"]),
            "cache_key": str(output["cache_key"]),
            "cache_hit": bool(output["cache_hit"]),
            "method_received_task_id": False,
            "method_received_seed": False,
            "method_received_reward": False,
            "method_received_evaluator_fields": False,
        }

    def navigate_once(self) -> None:
        before = self.executor.snapshot
        before_url = str(self.executor.observation.get("url", ""))
        inventory = compile_public_navigation_v1(
            before,
            current_url=before_url,
            goal=self.goal,
            quarantined_attempt_keys=self.quarantined_navigation_keys,
            maximum_candidates=int(
                self.budgets["maximum_navigation_candidates"]
            ),
        )
        step: dict[str, Any] = {
            "type": "public_navigation_decision_v1",
            "inventory": inventory.record(),
            "model": None,
            "resolution": None,
        }
        if not inventory.candidates:
            self.method_failure = "public navigation exposed no safe current candidate"
            self.audit(step)
            return
        messages = navigation_messages_v1(
            goal=self.goal,
            current_url=before_url,
            inventory=inventory,
            navigation_history=self.navigation_history,
        )
        model = self.call_model(messages)
        if model is None:
            self.audit(step)
            return
        step["model"] = model
        try:
            decision = resolve_public_navigation_v1(
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
        outcome = self.executor(candidate.action, "navigation")
        after_url = str(self.executor.observation.get("url", ""))
        effect = check_public_navigation_effect_v1(
            before=before,
            after=outcome.snapshot,
            before_url=before_url,
            after_url=after_url,
            candidate=candidate,
        )
        record = {
            **effect.record(),
            "bid": candidate.bid,
            "label": candidate.label,
            "before_url_sha256": hashlib.sha256(
                before_url.encode("utf-8")
            ).hexdigest(),
            "after_url_sha256": hashlib.sha256(
                after_url.encode("utf-8")
            ).hexdigest(),
        }
        self.navigation_effects.append(record)
        self.navigation_history.append(
            {
                "bid": candidate.bid,
                "label": candidate.label,
                "effective": effect.effective,
                "url_changed": effect.url_changed,
            }
        )
        if not effect.effective:
            self.quarantined_navigation_keys.add(effect.attempt_key)
        if outcome.action_error:
            self.method_failure = (
                f"public navigation action reported an error: {outcome.action_error}"
            )
        elif outcome.terminal:
            self.method_failure = "public navigation terminated before exact mutation"

    def execute_exact_mutation(self, compilation: Any) -> None:
        before = self.executor.snapshot
        inventory = compile_exact_mutation_inventory_v1(
            before,
            self.goal,
            compilation=compilation,
        )
        bindings = compilation.goal_contract.payload_bindings
        if len(bindings) != 1:
            self.method_failure = "exact target form did not bind one public field"
            return
        binding = bindings[0]
        contract = inventory.contract_by_bid.get(binding.bid)
        if contract is None:
            self.method_failure = "exact target field lacks a typed transaction"
            return
        inverse_reserve = inverse_action_cost_v8(contract)
        remaining_after_forward = _remaining_capacity_after_proposal(self.budgets["maximum_gui_actions"], len(self.executor.actions))
        required_after_forward = inverse_reserve + 1
        allowed = remaining_after_forward >= required_after_forward
        self.inverse_reservation_audits += 1
        self.audit(
            {
                "type": "inverse_budget_reservation",
                "bid": binding.bid,
                "inverse_action_cost": inverse_reserve,
                "commit_action_cost": 1,
                "remaining_after_forward": remaining_after_forward,
                "allowed": allowed,
            }
        )
        if not allowed:
            self.inverse_reservation_stops += 1
            self.method_failure = "inverse and commit budget reservation stopped mutation"
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
                "type": "exact_mutation_transaction_result_v1",
                "bid": binding.bid,
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
        fresh = compile_exact_mutation_goal_v1(self.goal, current)
        self.final_compilation = fresh
        if not fresh.allowed:
            self.method_failure = "exact mutation disappeared after typed forward"
            return
        fresh_inventory = compile_exact_mutation_inventory_v1(
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
            self.method_failure = "bound same-form action disappeared before commit"
            return
        certificate = certify_exact_mutation_commit_v1(
            current=current,
            compilation=fresh,
            candidate=submit,
            inventory=fresh_inventory.candidates,
            active_transactions=tuple(self.runtime.active),
            resolved_semantic_bids=tuple(sorted(self.resolved_exact_transaction_bids)),
            quarantined_commit_keys=self.effect_ledger.frozen_quarantine(),
        )
        self.audit(
            {
                "type": "exact_mutation_commit_certificate_v1",
                "bid": submit.bid,
                "certificate": _certificate_record(certificate),
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
                "type": "exact_mutation_commit_effect_v1",
                "bid": submit.bid,
                "effective": effect.effective,
                "reason": effect.reason,
                "quarantined": effect.quarantined,
                "key_sha256": effect.key_sha256,
            }
        )
        if committed.result.terminal:
            self.wrong_terminal_commits += 1
            self.method_failure = "exact mutation commit terminated before evaluator"
            return
        if not effect.effective:
            self.method_failure = effect.reason
            return
        self.resolved_exact_transaction_bids.add(binding.bid)
        self.method_commit_effective = True

    def _cleanup_failed_transaction(self) -> None:
        if (
            self.method_commit_effective
            or self.runtime.halted
            or not self.runtime.active
            or self.executor.done
        ):
            return
        try:
            outcomes = self.runtime.restore_all(
                "WebArena exact-mutation episode ended before effective commit"
            )
            self.restorations.extend(_restoration_record(row) for row in outcomes)
        except Exception as error:
            self.method_failure = self.method_failure or (
                f"cleanup failed: {type(error).__name__}: {error}"
            )

    def run_policy(self) -> None:
        while not self.method_commit_effective and self.within_budget():
            compilation = compile_exact_mutation_goal_v1(
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

    def run(self) -> None:
        try:
            self.run_policy()
        except Exception as error:
            if self.executor.infrastructure_error is not None:
                raise
            self.method_failure = self.method_failure or (
                f"driver failed: {type(error).__name__}: {error}"
            )
            self._cleanup_failed_transaction()

    def result(self) -> dict[str, Any]:
        action_errors = sum(
            bool(row["last_action_error_after"]) for row in self.executor.actions
        )
        return {
            "candidate": "WebArena-exact-mutation-agent-v1-episode",
            "complete": True,
            "method_commit_effective": self.method_commit_effective,
            "typed_target_form_reached": self.target_form_reached,
            "method_failure": self.method_failure,
            "infrastructure_failure": self.executor.infrastructure_error is not None,
            "infrastructure_error": self.executor.infrastructure_error,
            "method_input": {
                "goal": self.goal,
                "goal_sha256": hashlib.sha256(self.goal.encode("utf-8")).hexdigest(),
                "controller_arm": self.method_id,
                "method_received_task_id": False,
                "method_received_seed": False,
                "method_received_reward": False,
                "method_received_evaluator_fields": False,
                "method_received_hidden_state": False,
                "method_received_site_specific_route": False,
            },
            "evaluation_audit": {
                "reward_observed_by_harness": bool(self.executor.actions),
                "evaluator_info_observed_by_harness": bool(self.executor.actions),
                "reward_or_info_forwarded_to_method": False,
                "official_evaluator_called_by_method": False,
            },
            "goal_compilation": (
                None
                if self.final_compilation is None
                else self.final_compilation.record()
            ),
            "trace": self.trace,
            "actions": list(self.executor.actions),
            "navigation_history": self.navigation_history,
            "navigation_effects": self.navigation_effects,
            "restorations": self.restorations,
            "runtime_events": list(self.runtime.events),
            "active_transactions_at_stop": _active_records(self.runtime),
            "completed_transactions_at_stop": list(self.runtime.completed),
            "resolved_exact_transaction_bids": sorted(
                self.resolved_exact_transaction_bids
            ),
            "effect_ledger_v8": list(self.effect_ledger.records),
            "metrics": {
                "gui_actions": len(self.executor.actions),
                "navigation_actions": sum(
                    row["role"] == "navigation" for row in self.executor.actions
                ),
                "navigation_effect_passes": sum(
                    row["effective"] for row in self.navigation_effects
                ),
                "navigation_effect_failures": sum(
                    not row["effective"] for row in self.navigation_effects
                ),
                "quarantined_navigation_keys": len(
                    self.quarantined_navigation_keys
                ),
                "planner_calls": self.planner_calls,
                "planner_actual_calls": self.planner_actual_calls,
                "planner_cache_hits": self.planner_cache_hits,
                "planner_parse_failures": self.parse_failures,
                "typed_transactions": self.typed_transactions,
                "certified_commits": self.certified_commits,
                "uncertified_commits": 0,
                "restoration_attempts": len(self.restorations),
                "restoration_passes": sum(
                    row["passed"] for row in self.restorations
                ),
                "wrong_terminal_commits": self.wrong_terminal_commits,
                "terminal_transactions": sum(
                    row["role"] == "typed_forward"
                    and (row["terminated"] or row["truncated"])
                    for row in self.executor.actions
                ),
                "action_errors": action_errors,
                "commit_effect_passes": sum(
                    row["effective"] for row in self.effect_ledger.records
                ),
                "commit_effect_failures": sum(
                    not row["effective"] for row in self.effect_ledger.records
                ),
                "quarantined_commit_keys": len(
                    self.effect_ledger.quarantined_keys
                ),
                "resolved_transaction_bids": len(
                    self.resolved_exact_transaction_bids
                ),
                "inverse_reservation_audits": self.inverse_reservation_audits,
                "inverse_reservation_stops": self.inverse_reservation_stops,
                "runtime_halted": self.runtime.halted,
                "runtime_halt_reason": self.runtime.halt_reason,
                "wall_seconds": time.monotonic() - self.started,
            },
        }
