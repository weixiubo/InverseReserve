"""Fail-closed typed-transaction runtime with public interrupt compensation."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict, dataclass

from .pact_grounding_v4 import CommitCertificateV4, stack_signature_v4
from .transaction_actions_v4 import ContractActionV4
from .typed_contracts_v4 import (
    TransactionContractV4,
    check_transaction_postcondition,
    check_transaction_restoration,
    public_compensator_bids,
)
from .typed_observation import ContractCheck, SemanticDelta, SemanticSnapshot, semantic_delta


from .transaction_state import (
    ActionExecutionV4 as ActionExecutionV4,
    ActiveTransactionV4 as ActiveTransactionV4,
    RestorationOutcomeV4 as RestorationOutcomeV4,
    TransactionOutcomeV4 as TransactionOutcomeV4,
    CommitOutcomeV4 as CommitOutcomeV4,
)










class RuntimeHaltedV4(RuntimeError):
    """Raised if a caller requests another action after fail-closed halt."""


ActionExecutorV4 = Callable[[ContractActionV4, str], ActionExecutionV4]


class FailClosedTransactionRuntimeV4:
    def __init__(self, executor: ActionExecutorV4) -> None:
        self._executor = executor
        self.active: list[ActiveTransactionV4] = []
        self.completed: list[dict[str, object]] = []
        self.events: list[dict[str, object]] = []
        self.halted = False
        self.halt_reason: str | None = None

    def _audit(self, event: dict[str, object]) -> None:
        self.events.append({"event_index": len(self.events), **event})

    def _require_live(self) -> None:
        if self.halted:
            raise RuntimeHaltedV4(self.halt_reason or "PACT v4 runtime is halted")

    def _halt(self, reason: str) -> None:
        if not self.halted:
            self.halted = True
            self.halt_reason = reason
            self._audit({"type": "fail_closed", "reason": reason})

    def _execute(
        self,
        action: ContractActionV4,
        role: str,
    ) -> ActionExecutionV4 | None:
        self._require_live()
        try:
            result = self._executor(action, role)
        except Exception as error:
            reason = f"executor error: {type(error).__name__}: {error}"
            self._audit(
                {
                    "type": "action_exception",
                    "role": role,
                    "action": asdict(action),
                    "reason": reason,
                }
            )
            self._halt(reason)
            return None
        if not isinstance(result, ActionExecutionV4):
            reason = "executor returned an invalid action result"
            self._audit(
                {
                    "type": "action_exception",
                    "role": role,
                    "action": asdict(action),
                    "reason": reason,
                }
            )
            self._halt(reason)
            return None
        self._audit(
            {
                "type": "action",
                "role": role,
                "action": asdict(action),
                "terminated": result.terminated,
                "truncated": result.truncated,
                "action_error": result.action_error,
            }
        )
        return result

    def _check_postcondition(
        self,
        before: SemanticSnapshot,
        after: SemanticSnapshot,
        contract: TransactionContractV4,
        *,
        context: str,
    ) -> ContractCheck | None:
        try:
            check = check_transaction_postcondition(before, after, contract)
        except Exception as error:
            self._audit(
                {
                    "type": "verification_exception",
                    "context": context,
                    "reason": f"{type(error).__name__}: {error}",
                }
            )
            self._halt(f"{context} verifier raised an exception")
            return None
        self._audit(
            {
                "type": "postcondition",
                "context": context,
                "contract_kind": contract.kind,
                "passed": check.passed,
                "reason": check.reason,
                "delta": asdict(check.delta),
            }
        )
        return check

    def _check_restoration(
        self,
        before: SemanticSnapshot,
        restored: SemanticSnapshot,
        contract: TransactionContractV4,
        *,
        trigger: str,
    ) -> ContractCheck | None:
        try:
            check = check_transaction_restoration(before, restored, contract)
        except Exception as error:
            self._audit(
                {
                    "type": "verification_exception",
                    "context": trigger,
                    "reason": f"{type(error).__name__}: {error}",
                }
            )
            self._halt(f"{trigger} verifier raised an exception")
            return None
        self._audit(
            {
                "type": "restoration",
                "trigger": trigger,
                "projection_kind": contract.projection_kind,
                "passed": check.passed,
                "reason": check.reason,
                "global_delta": asdict(check.delta),
                "global_delta_empty": not check.delta.changed,
            }
        )
        return check

    def _static_restore(
        self,
        transaction: ActiveTransactionV4,
        *,
        trigger: str,
        remove_active: bool,
    ) -> RestorationOutcomeV4:
        final_snapshot: SemanticSnapshot | None = None
        inverse_actions = transaction.contract.inverse_actions
        if transaction.contract.dynamic_inverse_class_token is not None:
            current = transaction.after
            candidates = [
                element.bid
                for element in current.elements
                if current.is_effectively_visible(element.bid)
                and transaction.contract.dynamic_inverse_class_token
                in element.class_tokens
                and "ui-state-disabled" not in element.class_tokens
                and element.clickable
            ]
            self._audit(
                {
                    "type": "dynamic_inverse_grounding",
                    "class_token": transaction.contract.dynamic_inverse_class_token,
                    "candidate_bids": sorted(candidates),
                    "allowed": len(candidates) == 1,
                }
            )
            if len(candidates) != 1:
                reason = "dynamic public inverse is absent or ambiguous"
                self._halt(reason)
                return RestorationOutcomeV4(True, False, reason, None, current)
            inverse_actions = (ContractActionV4("click", candidates[0]),)
        for action in inverse_actions:
            result = self._execute(action, "typed_inverse")
            if result is None:
                return RestorationOutcomeV4(
                    True,
                    False,
                    self.halt_reason or "inverse executor failed",
                    None,
                    None,
                )
            final_snapshot = result.snapshot
            if result.terminal or result.action_error:
                reason = (
                    "inverse action terminated or truncated the environment"
                    if result.terminal
                    else f"inverse action reported an error: {result.action_error}"
                )
                self._halt(reason)
                return RestorationOutcomeV4(True, False, reason, None, final_snapshot)
        assert final_snapshot is not None
        check = self._check_restoration(
            transaction.before,
            final_snapshot,
            transaction.contract,
            trigger=trigger,
        )
        if check is None or not check.passed:
            reason = self.halt_reason or "contract-footprint restoration failed"
            self._halt(reason)
            return RestorationOutcomeV4(True, False, reason, check, final_snapshot)
        if remove_active:
            if not self.active or self.active[-1] is not transaction:
                raise RuntimeError("restoration must pop the active transaction top")
            self.active.pop()
        self.completed.append(
            {**transaction.planner_record(), "restored": True, "trigger": trigger}
        )
        return RestorationOutcomeV4(True, True, check.reason, check, final_snapshot)

    def transact(
        self,
        *,
        before: SemanticSnapshot,
        contract: TransactionContractV4,
        candidate_label: str,
    ) -> TransactionOutcomeV4:
        self._require_live()
        first = self._execute(contract.action, "typed_forward")
        if first is None:
            return TransactionOutcomeV4(
                False, self.halt_reason or "forward executor failed", None, None, 0, True
            )
        if first.terminal:
            reason = "typed forward action terminated or truncated the environment"
            self._halt(reason)
            return TransactionOutcomeV4(False, reason, None, None, 0, True)
        post = self._check_postcondition(
            before,
            first.snapshot,
            contract,
            context="typed forward",
        )
        if post is not None and post.passed and not first.action_error:
            transaction = ActiveTransactionV4(
                contract, candidate_label, before, first.snapshot, post.delta, 0
            )
            self.active.append(transaction)
            return TransactionOutcomeV4(
                True,
                "typed postcondition admitted the transaction",
                post,
                None,
                0,
                False,
            )
        if self.halted:
            return TransactionOutcomeV4(
                False, self.halt_reason or "verification failed", post, None, 0, True
            )

        compensators = public_compensator_bids(before, first.snapshot, contract)
        if compensators:
            self._audit(
                {
                    "type": "compensator_grounding",
                    "candidate_bids": list(compensators),
                    "allowed": len(compensators) == 1,
                }
            )
            if len(compensators) != 1 or contract.maximum_interrupt_repairs < 1:
                reason = "public interrupt compensation is ambiguous or disallowed"
                self._halt(reason)
                return TransactionOutcomeV4(False, reason, post, None, 0, True)
            compensation = self._execute(
                ContractActionV4("click", compensators[0]),
                "typed_compensator",
            )
            if compensation is None:
                return TransactionOutcomeV4(
                    False,
                    self.halt_reason or "compensator executor failed",
                    post,
                    None,
                    0,
                    True,
                )
            if compensation.terminal or compensation.action_error:
                reason = (
                    "compensator terminated or truncated the environment"
                    if compensation.terminal
                    else f"compensator reported an error: {compensation.action_error}"
                )
                self._halt(reason)
                return TransactionOutcomeV4(False, reason, post, None, 0, True)
            restored = self._check_restoration(
                before,
                compensation.snapshot,
                contract,
                trigger="dynamic public compensation",
            )
            if restored is None or not restored.passed:
                reason = self.halt_reason or "dynamic public compensation did not restore state"
                self._halt(reason)
                return TransactionOutcomeV4(
                    False,
                    reason,
                    post,
                    RestorationOutcomeV4(True, False, reason, restored, compensation.snapshot),
                    1,
                    True,
                )
            retry = self._execute(contract.action, "typed_retry")
            if retry is None:
                return TransactionOutcomeV4(
                    False,
                    self.halt_reason or "retry executor failed",
                    post,
                    RestorationOutcomeV4(
                        True, True, restored.reason, restored, compensation.snapshot
                    ),
                    1,
                    True,
                )
            if retry.terminal:
                reason = "typed retry terminated or truncated the environment"
                self._halt(reason)
                return TransactionOutcomeV4(False, reason, post, None, 1, True)
            retry_post = self._check_postcondition(
                before,
                retry.snapshot,
                contract,
                context="typed retry",
            )
            if retry_post is not None and retry_post.passed and not retry.action_error:
                transaction = ActiveTransactionV4(
                    contract,
                    candidate_label,
                    before,
                    retry.snapshot,
                    retry_post.delta,
                    1,
                )
                self.active.append(transaction)
                return TransactionOutcomeV4(
                    True,
                    "public compensation restored state and one retry passed",
                    retry_post,
                    RestorationOutcomeV4(
                        True, True, restored.reason, restored, compensation.snapshot
                    ),
                    1,
                    False,
                )
            failed = ActiveTransactionV4(
                contract,
                candidate_label,
                before,
                retry.snapshot,
                retry_post.delta if retry_post is not None else semantic_delta(before, retry.snapshot),
                1,
            )
            restoration = self._static_restore(
                failed,
                trigger="retry postcondition failed",
                remove_active=False,
            )
            return TransactionOutcomeV4(
                False,
                "retry postcondition failed after one compensation",
                retry_post,
                restoration,
                1,
                self.halted,
            )

        failed = ActiveTransactionV4(
            contract,
            candidate_label,
            before,
            first.snapshot,
            post.delta if post is not None else semantic_delta(before, first.snapshot),
            0,
        )
        restoration = self._static_restore(
            failed,
            trigger=("forward action error" if first.action_error else "postcondition failed"),
            remove_active=False,
        )
        return TransactionOutcomeV4(
            False,
            "typed forward was rejected after static restoration"
            if restoration.passed
            else restoration.reason,
            post,
            restoration,
            0,
            self.halted,
        )

    def restore_top(self, trigger: str) -> RestorationOutcomeV4:
        self._require_live()
        if not self.active:
            return RestorationOutcomeV4(
                False, True, "transaction stack is already empty", None, None
            )
        return self._static_restore(
            self.active[-1], trigger=trigger, remove_active=True
        )

    def restore_all(self, trigger: str) -> tuple[RestorationOutcomeV4, ...]:
        self._require_live()
        outcomes = []
        while self.active and not self.halted:
            outcome = self.restore_top(trigger)
            outcomes.append(outcome)
            if not outcome.passed:
                break
        return tuple(outcomes)

    def consume_active_after_effective_commit(
        self,
        trigger: str,
    ) -> tuple[str, ...]:
        """Close obligations whose scope was consumed by a verified commit."""

        self._require_live()
        transactions = tuple(self.active)
        self.active.clear()
        for transaction in transactions:
            self.completed.append(
                {
                    **transaction.planner_record(),
                    "restored": False,
                    "committed": True,
                    "trigger": trigger,
                }
            )
        consumed = tuple(
            transaction.contract.semantic_bid for transaction in transactions
        )
        self._audit(
            {
                "type": "effective_commit_scope_consumed",
                "trigger": trigger,
                "transaction_count": len(transactions),
                "semantic_bids": list(consumed),
            }
        )
        return consumed

    def commit(
        self,
        *,
        current: SemanticSnapshot,
        action: ContractActionV4,
        certificate: CommitCertificateV4,
    ) -> CommitOutcomeV4:
        """Execute only the action bound to a fresh v4 public certificate."""

        self._require_live()
        if not certificate.allowed or certificate.certified_action is None:
            reason = "commit certificate was not admitted"
            self._audit({"type": "commit_rejected", "reason": reason})
            return CommitOutcomeV4(False, reason, None, False)
        try:
            fingerprint = current.semantic_fingerprint()
        except Exception as error:
            reason = f"commit observation fingerprint failed: {type(error).__name__}"
            self._audit({"type": "commit_rejected", "reason": reason})
            self._halt(reason)
            return CommitOutcomeV4(False, reason, None, True)
        if fingerprint != certificate.observation_fingerprint:
            reason = "commit certificate is stale for the current public observation"
            self._audit({"type": "commit_rejected", "reason": reason})
            return CommitOutcomeV4(False, reason, None, False)
        if stack_signature_v4(self.active) != certificate.active_stack_signature:
            reason = "commit certificate is stale for the active transaction stack"
            self._audit({"type": "commit_rejected", "reason": reason})
            return CommitOutcomeV4(False, reason, None, False)
        if action != certificate.certified_action:
            reason = "commit action differs from the certified operation or argument"
            self._audit({"type": "commit_rejected", "reason": reason})
            return CommitOutcomeV4(False, reason, None, False)
        result = self._execute(action, "commit")
        if result is None:
            return CommitOutcomeV4(
                False, self.halt_reason or "commit executor failed", None, True
            )
        if result.action_error:
            reason = f"commit action reported an error: {result.action_error}"
            self._halt(reason)
            return CommitOutcomeV4(False, reason, result, True)
        return CommitOutcomeV4(
            True,
            "fresh public certificate authorized the exact commit action",
            result,
            False,
        )
