"""Matched confirmation agents for PACT-v7 and its frozen baselines."""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict
from typing import Any, Callable

from .action_envelope_v7 import (
    assemble_action_envelope_v7,
    envelope_messages_v7,
    resolve_action_envelope_v7,
)
from .model_planner_v6 import (
    parse_planner_decision_v6,
    planner_messages_v6,
)
from .pact_controller_v4 import (
    ActionExecutionV4,
    FailClosedTransactionRuntimeV4,
)
from .pact_grounding_v6 import certify_commit_v6
from .structured_planner_v6 import compile_v6_inventory
from .transaction_actions_v4 import ContractActionV4
from .typed_observation import SemanticSnapshot, semantic_snapshot


PlannerGenerateV7 = Callable[[list[dict[str, str]]], dict[str, Any]]


def object_sha256(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")
    ).hexdigest()


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


def _active_records(runtime: FailClosedTransactionRuntimeV4) -> list[dict[str, Any]]:
    return [transaction.planner_record() for transaction in runtime.active]


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


class ConfirmationExecutorV7:
    """BrowserGym executor that keeps evaluator outputs outside method inputs."""

    def __init__(
        self,
        environment: Any,
        observation: dict[str, Any],
        *,
        maximum_gui_actions: int,
    ) -> None:
        self.environment = environment
        self.observation = observation
        self.maximum_gui_actions = int(maximum_gui_actions)
        self.actions: list[dict[str, Any]] = []
        self.done = False
        self.terminated = False
        self.truncated = False
        self.success = False
        self.infrastructure_error: str | None = None

    @property
    def snapshot(self) -> SemanticSnapshot:
        return semantic_snapshot(
            self.observation["axtree_object"],
            self.observation["dom_object"],
            self.observation["extra_element_properties"],
        )

    def __call__(self, action: ContractActionV4, role: str) -> ActionExecutionV4:
        if self.done:
            raise RuntimeError("confirmation executor is already terminal")
        if len(self.actions) >= self.maximum_gui_actions:
            raise RuntimeError("confirmation GUI action budget exhausted")
        height, width = self.observation["screenshot"].shape[:2]
        code = action.browsergym_code(
            viewport_width=int(width), viewport_height=int(height)
        )
        prior_error = str(self.observation.get("last_action_error", ""))
        try:
            observation, reward, terminated, truncated, info = self.environment.step(
                code
            )
        except Exception as error:
            self.infrastructure_error = f"{type(error).__name__}: {error}"
            raise
        self.observation = observation
        self.terminated = bool(terminated)
        self.truncated = bool(truncated)
        self.success = self.success or float(reward) > 0.0
        self.done = self.terminated or self.truncated or self.success
        action_error = str(observation.get("last_action_error", ""))
        self.actions.append(
            {
                "action_index": len(self.actions),
                "role": role,
                "code": code,
                "reward": float(reward),
                "terminated": self.terminated,
                "truncated": self.truncated,
                "last_action_error_before": prior_error,
                "last_action_error_after": action_error,
                "evaluator_reason": str(info.get("message", info.get("reason", ""))),
                "method_received_reward": False,
                "method_received_info": False,
            }
        )
        return ActionExecutionV4(
            self.snapshot,
            self.terminated,
            self.truncated,
            action_error,
        )


class ConfirmationDriverV7:
    method_id = ""

    def __init__(
        self,
        *,
        environment: Any,
        observation: dict[str, Any],
        budgets: dict[str, Any],
        planner_generate: PlannerGenerateV7,
    ) -> None:
        self.budgets = budgets
        self.goal = str(observation["goal"])
        self.executor = ConfirmationExecutorV7(
            environment,
            observation,
            maximum_gui_actions=int(budgets["maximum_gui_actions"]),
        )
        self.initial_inventory = compile_v6_inventory(self.executor.snapshot, self.goal)
        self.goal_contract = self.initial_inventory.goal_contract
        self.planner_generate = planner_generate
        self.trace: list[dict[str, Any]] = []
        self.planner_calls = 0
        self.planner_cache_hits = 0
        self.planner_actual_calls = 0
        self.parse_failures = 0
        self.wrong_terminal_commits = 0
        self.terminal_transactions = 0
        self.certified_commits = 0
        self.uncertified_commits = 0
        self.typed_transactions = 0
        self.restorations: list[dict[str, Any]] = []
        self.method_failure: str | None = None
        self.started = time.monotonic()

    def audit(self, event: dict[str, Any]) -> None:
        self.trace.append({"event_index": len(self.trace), **event})

    def within_budget(self) -> bool:
        if len(self.executor.actions) >= int(self.budgets["maximum_gui_actions"]):
            self.method_failure = "GUI action budget exhausted"
            return False
        if self.planner_calls >= int(self.budgets["maximum_planner_calls"]):
            self.method_failure = "planner call budget exhausted"
            return False
        if time.monotonic() - self.started > float(self.budgets["maximum_wall_seconds"]):
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
            self.method_failure = f"planner generation failed: {type(error).__name__}: {error}"
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

    def inventory(self) -> Any:
        return compile_v6_inventory(
            self.executor.snapshot,
            self.goal,
            goal_contract=self.goal_contract,
        )

    def execute_uncertified(self, candidate: Any, role: str) -> ActionExecutionV4:
        result = self.executor(candidate.action, role)
        self.uncertified_commits += int(candidate.transaction_kind is None)
        if result.terminal and candidate.transaction_kind is None and not self.executor.success:
            self.wrong_terminal_commits += 1
        if result.terminal and candidate.transaction_kind is not None:
            self.terminal_transactions += 1
        return result

    def cleanup_runtime(self, runtime: FailClosedTransactionRuntimeV4) -> None:
        if self.executor.done or runtime.halted or not runtime.active:
            return
        try:
            outcomes = runtime.restore_all("confirmation episode ended without success")
            self.restorations.extend(_restoration_record(row) for row in outcomes)
        except Exception as error:
            self.method_failure = self.method_failure or (
                f"cleanup failed: {type(error).__name__}: {error}"
            )

    def run_policy(self) -> None:
        raise NotImplementedError

    def run(self) -> None:
        try:
            self.run_policy()
        except Exception as error:
            if self.executor.infrastructure_error is not None:
                raise
            self.method_failure = self.method_failure or (
                f"driver failed: {type(error).__name__}: {error}"
            )

    def result(self) -> dict[str, Any]:
        runtime_halted = bool(getattr(self, "runtime", None) and self.runtime.halted)
        runtime_halt_reason = (
            self.runtime.halt_reason if getattr(self, "runtime", None) else None
        )
        action_errors = sum(
            bool(row["last_action_error_after"]) for row in self.executor.actions
        )
        return {
            "candidate": "C444-matched-confirmation-episode",
            "complete": True,
            "success": bool(self.executor.success),
            "terminated": self.executor.terminated,
            "truncated": self.executor.truncated,
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
            },
            "evaluation_audit": {
                "reward_observed_by_harness": bool(self.executor.actions),
                "evaluator_info_observed_by_harness": bool(self.executor.actions),
                "reward_or_info_forwarded_to_method": False,
                "confirmation_episode": True,
            },
            "goal_contract": self.goal_contract.record(),
            "trace": self.trace,
            "actions": self.executor.actions,
            "restorations": self.restorations,
            "runtime_events": (
                list(self.runtime.events) if getattr(self, "runtime", None) else []
            ),
            "active_transactions_at_stop": (
                _active_records(self.runtime) if getattr(self, "runtime", None) else []
            ),
            "completed_transactions_at_stop": (
                list(self.runtime.completed) if getattr(self, "runtime", None) else []
            ),
            "metrics": {
                "gui_actions": len(self.executor.actions),
                "planner_calls": self.planner_calls,
                "planner_actual_calls": self.planner_actual_calls,
                "planner_cache_hits": self.planner_cache_hits,
                "planner_parse_failures": self.parse_failures,
                "typed_transactions": self.typed_transactions,
                "certified_commits": self.certified_commits,
                "uncertified_commits": self.uncertified_commits,
                "restoration_attempts": len(self.restorations),
                "restoration_passes": sum(row["passed"] for row in self.restorations),
                "wrong_terminal_commits": self.wrong_terminal_commits,
                "terminal_transactions": self.terminal_transactions,
                "action_errors": action_errors,
                "runtime_halted": runtime_halted,
                "runtime_halt_reason": runtime_halt_reason,
                "wall_seconds": time.monotonic() - self.started,
            },
        }


class FullPactConfirmationDriverV7(ConfirmationDriverV7):
    method_id = "full_pact_v7"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.runtime = FailClosedTransactionRuntimeV4(self.executor)

    def fresh_envelope(self, inventory: Any) -> tuple[Any, dict[str, Any], list[dict[str, Any]]]:
        admitted = []
        certificates = {}
        audit = []
        current = self.executor.snapshot
        for candidate in inventory.candidates:
            if candidate.transaction_kind is not None:
                continue
            certificate = certify_commit_v6(
                current=current,
                goal=inventory.goal_contract,
                candidate=candidate,
                inventory=inventory.candidates,
                active_transactions=tuple(self.runtime.active),
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
        envelope = assemble_action_envelope_v7(
            candidates=inventory.candidates,
            admitted_certificate_bids=admitted,
            active_transactions=tuple(self.runtime.active),
            completed_transactions=tuple(self.runtime.completed),
        )
        return envelope, certificates, audit

    def run_policy(self) -> None:
        while not self.executor.done and self.within_budget():
            inventory = self.inventory()
            current = self.executor.snapshot
            envelope, certificates, certificate_audit = self.fresh_envelope(inventory)
            step = {
                "type": "envelope_decision",
                "observation_sha256": object_sha256(current.semantic_fingerprint()),
                "inventory_sha256": object_sha256(
                    [row.prompt_record() for row in inventory.candidates]
                ),
                "inventory_count": len(inventory.candidates),
                "envelope": envelope.record(),
                "certificate_audit": certificate_audit,
                "active_transactions": _active_records(self.runtime),
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
                    self.method_failure = f"planner parse failed: {type(error).__name__}: {error}"
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
                self.method_failure = "PACT-v7 action envelope abstained"
                break
            candidate = resolution.candidate
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
                        "type": "typed_transaction_result",
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
                self.method_failure = "commit envelope lacked a fresh certificate"
                break
            outcome = self.runtime.commit(
                current=current,
                action=candidate.action,
                certificate=certificate,
            )
            self.certified_commits += 1
            self.audit(
                {
                    "type": "certified_commit_result",
                    "bid": candidate.bid,
                    "anchor_kind": certificate.grounding.anchor_kind,
                    "certificate": _certificate_record(certificate),
                    "executed": outcome.executed,
                    "reason": outcome.reason,
                    "halted": outcome.halted,
                    "terminal": bool(outcome.result and outcome.result.terminal),
                }
            )
            if not outcome.executed or outcome.halted:
                self.method_failure = outcome.reason
                break
            if self.executor.done and not self.executor.success:
                self.wrong_terminal_commits += 1
        if not self.executor.done:
            self.cleanup_runtime(self.runtime)


class RawOpenLoopConfirmationDriverV7(ConfirmationDriverV7):
    method_id = "raw_open_loop"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.active_history: list[dict[str, Any]] = []

    def run_policy(self) -> None:
        while not self.executor.done and self.within_budget():
            inventory = self.inventory()
            messages = planner_messages_v6(
                goal=self.goal,
                goal_contract=self.goal_contract,
                candidates=inventory.candidates,
                active_transactions=self.active_history,
                completed_transactions=(),
            )
            model = self.call_model(messages)
            if model is None:
                break
            try:
                decision = parse_planner_decision_v6(
                    model["raw_output"], inventory.candidates
                )
            except Exception as error:
                self.parse_failures += 1
                self.method_failure = f"planner parse failed: {type(error).__name__}: {error}"
                self.audit({"type": "planner_failure", "model": model})
                break
            self.audit(
                {
                    "type": "raw_planner_decision",
                    "inventory_sha256": object_sha256(
                        [row.prompt_record() for row in inventory.candidates]
                    ),
                    "inventory_count": len(inventory.candidates),
                    "decision": decision.decision,
                    "bid": decision.bid,
                    "model": model,
                }
            )
            if decision.decision == "abstain" or decision.candidate is None:
                self.method_failure = "raw planner abstained"
                break
            candidate = decision.candidate
            result = self.execute_uncertified(candidate, "raw_open_loop")
            if result.action_error:
                self.method_failure = f"action error: {result.action_error}"
                break
            if decision.decision == "transact" and not result.terminal:
                self.active_history.append(
                    {
                        "bid": candidate.bid,
                        "label": candidate.label,
                        "transaction_kind": candidate.transaction_kind,
                        "semantic_bid": candidate.semantic_bid,
                        "operation": candidate.action.operation,
                        "argument": candidate.action.argument,
                        "interrupt_repairs": 0,
                    }
                )


class TypedNoCertificateConfirmationDriverV7(ConfirmationDriverV7):
    method_id = "typed_no_certificate"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.runtime = FailClosedTransactionRuntimeV4(self.executor)

    def run_policy(self) -> None:
        while not self.executor.done and self.within_budget():
            inventory = self.inventory()
            current = self.executor.snapshot
            messages = planner_messages_v6(
                goal=self.goal,
                goal_contract=self.goal_contract,
                candidates=inventory.candidates,
                active_transactions=_active_records(self.runtime),
                completed_transactions=self.runtime.completed,
            )
            model = self.call_model(messages)
            if model is None:
                break
            try:
                decision = parse_planner_decision_v6(
                    model["raw_output"], inventory.candidates
                )
            except Exception as error:
                self.parse_failures += 1
                self.method_failure = f"planner parse failed: {type(error).__name__}: {error}"
                self.audit({"type": "planner_failure", "model": model})
                break
            self.audit(
                {
                    "type": "typed_no_certificate_decision",
                    "inventory_sha256": object_sha256(
                        [row.prompt_record() for row in inventory.candidates]
                    ),
                    "inventory_count": len(inventory.candidates),
                    "decision": decision.decision,
                    "bid": decision.bid,
                    "active_transactions": _active_records(self.runtime),
                    "model": model,
                }
            )
            if decision.decision == "abstain" or decision.candidate is None:
                self.method_failure = "typed no-certificate planner abstained"
                break
            candidate = decision.candidate
            if decision.decision == "transact":
                unfinished = assemble_action_envelope_v7(
                    candidates=inventory.candidates,
                    active_transactions=tuple(self.runtime.active),
                    completed_transactions=tuple(self.runtime.completed),
                )
                if (
                    unfinished.decision != "transact"
                    or candidate.bid
                    not in {row.bid for row in unfinished.candidates}
                ):
                    self.method_failure = "planner repeated or mistyped an active transaction"
                    break
                contract = inventory.contract_by_bid.get(candidate.bid)
                if contract is None:
                    self.method_failure = "typed row lacked a transaction contract"
                    break
                outcome = self.runtime.transact(
                    before=current,
                    contract=contract,
                    candidate_label=candidate.label,
                )
                self.typed_transactions += 1
                self.audit(
                    {
                        "type": "typed_transaction_result",
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
            result = self.execute_uncertified(candidate, "uncertified_commit")
            if result.action_error:
                self.method_failure = f"action error: {result.action_error}"
                break
        if not self.executor.done:
            self.cleanup_runtime(self.runtime)


CONFIRMATION_DRIVERS_V7 = {
    "full_pact_v7": FullPactConfirmationDriverV7,
    "raw_open_loop": RawOpenLoopConfirmationDriverV7,
    "typed_no_certificate": TypedNoCertificateConfirmationDriverV7,
}
