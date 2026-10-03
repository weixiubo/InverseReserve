"""Fail-closed successor runtime and commit gate for PACT v3.

The frozen C428 implementation remains untouched.  This module joins the
parameterized action surface, typed postconditions, restoration certificates,
and positive target constraints needed by a future fresh-task protocol.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict, dataclass

from .pact_grounding_v3 import ConstraintCertificate, verify_commit_constraint
from .structured_planner import ActionCandidate
from .transaction_actions import ActionSequenceContract, ContractAction
from .typed_contracts_v3 import (
    check_sequence_postcondition,
    check_sequence_restoration,
)
from .typed_observation import (
    ContractCheck,
    SemanticDelta,
    SemanticSnapshot,
    semantic_delta,
)


@dataclass(frozen=True)
class ActionExecution:
    """Public result returned by an injected GUI-action executor."""

    snapshot: SemanticSnapshot
    terminated: bool = False
    truncated: bool = False
    action_error: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.snapshot, SemanticSnapshot):
            raise ValueError("action execution requires a semantic snapshot")
        if not isinstance(self.terminated, bool) or not isinstance(
            self.truncated, bool
        ):
            raise ValueError("terminal flags must be Boolean")
        if not isinstance(self.action_error, str):
            raise ValueError("action_error must be text")

    @property
    def terminal(self) -> bool:
        return self.terminated or self.truncated


@dataclass(frozen=True)
class ActiveSequenceTransaction:
    contract: ActionSequenceContract
    candidate_label: str
    before: SemanticSnapshot
    after: SemanticSnapshot
    delta: SemanticDelta

    def planner_record(self) -> dict[str, object]:
        return {
            "bid": self.contract.action.bid,
            "label": self.candidate_label,
            "preview_kind": self.contract.kind,
            "semantic_bid": self.contract.semantic_bid,
        }

    def completed_record(self, *, target_found: bool) -> dict[str, object]:
        return {**self.planner_record(), "target_found": bool(target_found)}


@dataclass(frozen=True)
class RestorationOutcome:
    attempted: bool
    passed: bool
    reason: str
    check: ContractCheck | None
    final_snapshot: SemanticSnapshot | None


@dataclass(frozen=True)
class ExplorationOutcome:
    admitted: bool
    reason: str
    postcondition: ContractCheck | None
    restoration: RestorationOutcome | None
    halted: bool


@dataclass(frozen=True)
class CommitCertificate:
    allowed: bool
    reason: str
    grounding: ConstraintCertificate
    supporting_transaction_depth: int | None
    competing_bids: tuple[str, ...] = ()
    certified_bid: str | None = None
    certified_operation: str | None = None
    observation_fingerprint: tuple[tuple[object, ...], ...] = ()
    active_stack_signature: tuple[tuple[str, str, str | None], ...] = ()


@dataclass(frozen=True)
class CommitOutcome:
    executed: bool
    reason: str
    result: ActionExecution | None
    halted: bool


class RuntimeHalted(RuntimeError):
    """Raised when code attempts another action after a fail-closed event."""


ActionExecutor = Callable[[ContractAction, str], ActionExecution]


def _stack_signature(
    transactions: tuple[ActiveSequenceTransaction, ...]
    | list[ActiveSequenceTransaction],
) -> tuple[tuple[str, str, str | None], ...]:
    return tuple(
        (
            transaction.contract.kind,
            transaction.contract.semantic_bid,
            transaction.contract.action.bid,
        )
        for transaction in transactions
    )


def sequence_transaction_scope_bids(
    current: SemanticSnapshot,
    transaction: ActiveSequenceTransaction,
) -> frozenset[str]:
    bids = set(transaction.delta.added_visible_bids)
    bids.update(transaction.delta.changed_visible_bids)
    bids.add(transaction.contract.semantic_bid)
    if transaction.contract.action.bid is not None:
        bids.add(transaction.contract.action.bid)
    for relation in ("ax", "dom"):
        bids.update(
            element.bid
            for element in current.descendants(
                transaction.contract.semantic_bid,
                relation=relation,
            )
        )
    return frozenset(bids)


def certify_commit(
    *,
    goal: str,
    current: SemanticSnapshot,
    candidate: ActionCandidate,
    inventory: tuple[ActionCandidate, ...],
    active_transactions: tuple[ActiveSequenceTransaction, ...],
) -> CommitCertificate:
    """Require positive grounding, active-state scope, and uniqueness."""

    grounding = verify_commit_constraint(
        goal=goal,
        candidate_label=candidate.label,
        candidate_role=candidate.role,
        current=current,
    )
    if not grounding.allowed:
        return CommitCertificate(False, grounding.reason, grounding, None)

    rows_by_bid = {row.bid: row for row in inventory}
    if len(rows_by_bid) != len(inventory):
        return CommitCertificate(
            False,
            "visible action inventory contains duplicate bids",
            grounding,
            None,
        )
    if rows_by_bid.get(candidate.bid) != candidate:
        return CommitCertificate(
            False,
            "candidate is not the authoritative visible inventory row",
            grounding,
            None,
        )

    eligible: list[
        tuple[int, ActionCandidate, ConstraintCertificate, int | None, str]
    ] = []
    for row in inventory:
        try:
            action_element = current.get(row.bid)
            semantic_element = current.get(row.semantic_bid)
            visible = (
                action_element is not None
                and semantic_element is not None
                and current.is_effectively_visible(row.bid)
                and current.is_effectively_visible(row.semantic_bid)
            )
        except (TypeError, ValueError):
            visible = False
        if not visible:
            continue
        row_grounding = verify_commit_constraint(
            goal=goal,
            candidate_label=row.label,
            candidate_role=row.role,
            current=current,
        )
        if not row_grounding.allowed:
            continue
        if not active_transactions:
            eligible.append(
                (
                    0,
                    row,
                    row_grounding,
                    None,
                    "unique positive public target certificate permits a direct commit",
                )
            )
            continue

        supporting_values = set(row_grounding.supporting_value_bids)
        for reverse_index, transaction in enumerate(
            reversed(active_transactions), start=1
        ):
            try:
                scope = sequence_transaction_scope_bids(current, transaction)
            except (TypeError, ValueError):
                continue
            depth = len(active_transactions) - reverse_index + 1
            if row.bid in scope or row.semantic_bid in scope:
                eligible.append(
                    (
                        0,
                        row,
                        row_grounding,
                        depth,
                        "commit target is structurally bound to an active transaction",
                    )
                )
                break
            if supporting_values & set(scope):
                eligible.append(
                    (
                        1,
                        row,
                        row_grounding,
                        depth,
                        "commit is supported by a grounded public value "
                        "in an active transaction",
                    )
                )
                break

    if not eligible:
        return CommitCertificate(
            False,
            "no visible grounded candidate has a valid transaction scope",
            grounding,
            None,
        )
    best_strength = min(row[0] for row in eligible)
    best = [row for row in eligible if row[0] == best_strength]
    competing_bids = tuple(sorted({row[1].bid for row in best}))
    if len(competing_bids) != 1:
        return CommitCertificate(
            False,
            "positive target grounding is ambiguous in the strongest public scope",
            grounding,
            None,
            competing_bids,
        )
    selected = best[0]
    if selected[1].bid != candidate.bid:
        return CommitCertificate(
            False,
            "planner candidate is not the uniquely certified visible target",
            grounding,
            None,
            competing_bids,
        )
    try:
        fingerprint = current.semantic_fingerprint()
    except (TypeError, ValueError):
        return CommitCertificate(
            False,
            "current public observation has no stable semantic fingerprint",
            grounding,
            None,
            competing_bids,
        )
    return CommitCertificate(
        True,
        selected[4],
        selected[2],
        selected[3],
        competing_bids,
        selected[1].bid,
        selected[1].operation,
        fingerprint,
        _stack_signature(active_transactions),
    )


class FailClosedTransactionRuntime:
    """Execute typed previews and make restoration failure terminal to policy.

    A transaction is removed from the stack only after its complete inverse
    sequence and semantic restoration certificate pass.  Once halted, every
    public method that could execute a GUI action raises ``RuntimeHalted``.
    """

    def __init__(self, executor: ActionExecutor) -> None:
        self._executor = executor
        self.active: list[ActiveSequenceTransaction] = []
        self.completed: list[dict[str, object]] = []
        self.events: list[dict[str, object]] = []
        self.halted = False
        self.halt_reason: str | None = None

    def _audit(self, event: dict[str, object]) -> None:
        self.events.append({"event_index": len(self.events), **event})

    def _require_live(self) -> None:
        if self.halted:
            raise RuntimeHalted(self.halt_reason or "PACT runtime is halted")

    def _halt(self, reason: str) -> None:
        if not self.halted:
            self.halted = True
            self.halt_reason = reason
            self._audit({"type": "fail_closed", "reason": reason})

    def _execute_action(
        self,
        action: ContractAction,
        role: str,
    ) -> ActionExecution | None:
        self._require_live()
        try:
            result = self._executor(action, role)
        except Exception as error:  # state after an executor error is unknown
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
        if not isinstance(result, ActionExecution):
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

    def _restoration_check(
        self,
        before: SemanticSnapshot,
        current: SemanticSnapshot,
        *,
        context: str,
    ) -> ContractCheck | None:
        try:
            return check_sequence_restoration(before, current)
        except Exception as error:
            self._audit(
                {
                    "type": "verification_exception",
                    "context": context,
                    "reason": f"{type(error).__name__}: {error}",
                }
            )
            return None

    def _retain_unresolved(
        self,
        transaction: ActiveSequenceTransaction,
        *,
        remove_active: bool,
    ) -> None:
        if not remove_active and transaction not in self.active:
            self.active.append(transaction)

    def _restore_transaction(
        self,
        transaction: ActiveSequenceTransaction,
        *,
        trigger: str,
        remove_active: bool,
    ) -> RestorationOutcome:
        final_snapshot: SemanticSnapshot | None = None
        for action in transaction.contract.inverse_actions:
            result = self._execute_action(action, "typed_inverse")
            if result is None:
                self._retain_unresolved(
                    transaction,
                    remove_active=remove_active,
                )
                return RestorationOutcome(
                    True,
                    False,
                    self.halt_reason or "inverse executor failed",
                    None,
                    None,
                )
            final_snapshot = result.snapshot
            if result.terminal:
                reason = "inverse action terminated or truncated the environment"
                self._retain_unresolved(
                    transaction,
                    remove_active=remove_active,
                )
                self._halt(reason)
                return RestorationOutcome(True, False, reason, None, final_snapshot)
            if result.action_error:
                reason = f"inverse action reported an error: {result.action_error}"
                self._retain_unresolved(
                    transaction,
                    remove_active=remove_active,
                )
                self._halt(reason)
                return RestorationOutcome(True, False, reason, None, final_snapshot)

        assert final_snapshot is not None
        check = self._restoration_check(
            transaction.before,
            final_snapshot,
            context="inverse restoration certificate",
        )
        if check is None:
            reason = "semantic restoration verifier raised an exception"
            self._retain_unresolved(
                transaction,
                remove_active=remove_active,
            )
            self._halt(reason)
            return RestorationOutcome(True, False, reason, None, final_snapshot)
        self._audit(
            {
                "type": "restoration",
                "trigger": trigger,
                "passed": check.passed,
                "reason": check.reason,
                "delta": asdict(check.delta),
            }
        )
        if not check.passed:
            reason = "semantic restoration certificate failed"
            self._retain_unresolved(
                transaction,
                remove_active=remove_active,
            )
            self._halt(reason)
            return RestorationOutcome(True, False, reason, check, final_snapshot)

        if remove_active:
            if not self.active or self.active[-1] is not transaction:
                raise RuntimeError("restoration must pop the current transaction top")
            self.active.pop()
        self.completed.append(transaction.completed_record(target_found=False))
        return RestorationOutcome(
            True,
            True,
            "inverse sequence restored the pre-transaction fingerprint",
            check,
            final_snapshot,
        )

    def explore(
        self,
        *,
        before: SemanticSnapshot,
        contract: ActionSequenceContract,
        candidate_label: str,
    ) -> ExplorationOutcome:
        self._require_live()
        result = self._execute_action(contract.action, "typed_preview")
        if result is None:
            return ExplorationOutcome(
                False,
                self.halt_reason or "preview executor failed",
                None,
                None,
                True,
            )
        if result.terminal:
            reason = "typed preview terminated or truncated the environment"
            self._halt(reason)
            return ExplorationOutcome(False, reason, None, None, True)

        verifier_error: str | None = None
        try:
            postcondition = check_sequence_postcondition(
                before,
                result.snapshot,
                contract,
            )
        except Exception as error:
            postcondition = None
            verifier_error = f"{type(error).__name__}: {error}"
            self._audit(
                {
                    "type": "verification_exception",
                    "context": "typed postcondition",
                    "reason": verifier_error,
                }
            )
        if postcondition is not None:
            self._audit(
                {
                    "type": "postcondition",
                    "contract": asdict(contract),
                    "passed": postcondition.passed,
                    "reason": postcondition.reason,
                    "delta": asdict(postcondition.delta),
                }
            )
            delta = postcondition.delta
        else:
            try:
                delta = semantic_delta(before, result.snapshot)
            except Exception:
                delta = SemanticDelta((), (), (), ())
        transaction = ActiveSequenceTransaction(
            contract,
            candidate_label,
            before,
            result.snapshot,
            delta,
        )
        if (
            postcondition is not None
            and postcondition.passed
            and not result.action_error
        ):
            self.active.append(transaction)
            return ExplorationOutcome(
                True,
                "typed postcondition admitted the transaction",
                postcondition,
                None,
                False,
            )

        unchanged = self._restoration_check(
            before,
            result.snapshot,
            context="rejected preview unchanged-state certificate",
        )
        if unchanged is not None and unchanged.passed:
            self._audit(
                {
                    "type": "restoration",
                    "trigger": "preview rejected in unchanged state",
                    "passed": True,
                    "reason": unchanged.reason,
                    "delta": asdict(unchanged.delta),
                    "inverse_skipped": True,
                }
            )
            self.completed.append(transaction.completed_record(target_found=False))
            if verifier_error is not None:
                self._halt("typed postcondition verifier raised an exception")
            return ExplorationOutcome(
                False,
                "preview was rejected and public state was already unchanged",
                postcondition,
                RestorationOutcome(
                    False,
                    True,
                    "no inverse needed for an unchanged public state",
                    unchanged,
                    result.snapshot,
                ),
                self.halted,
            )

        restoration = self._restore_transaction(
            transaction,
            trigger=(
                "preview action error"
                if result.action_error
                else "typed postcondition failed"
            ),
            remove_active=False,
        )
        if verifier_error is not None and restoration.passed:
            self._halt("typed postcondition verifier raised an exception")
        return ExplorationOutcome(
            False,
            "preview rejected after typed restoration"
            if restoration.passed
            else restoration.reason,
            postcondition,
            restoration,
            self.halted,
        )

    def restore_top(self, trigger: str) -> RestorationOutcome:
        self._require_live()
        if not self.active:
            return RestorationOutcome(
                False,
                True,
                "transaction stack is already empty",
                None,
                None,
            )
        return self._restore_transaction(
            self.active[-1],
            trigger=trigger,
            remove_active=True,
        )

    def restore_all(self, trigger: str) -> tuple[RestorationOutcome, ...]:
        self._require_live()
        outcomes = []
        while self.active and not self.halted:
            outcome = self.restore_top(trigger)
            outcomes.append(outcome)
            if not outcome.passed:
                break
        return tuple(outcomes)

    def commit(
        self,
        *,
        current: SemanticSnapshot,
        action: ContractAction,
        certificate: CommitCertificate,
    ) -> CommitOutcome:
        """Execute only the exact action bound to a fresh positive certificate."""

        self._require_live()
        if not certificate.allowed:
            reason = "commit certificate was not admitted"
            self._audit({"type": "commit_rejected", "reason": reason})
            return CommitOutcome(False, reason, None, False)
        try:
            fingerprint = current.semantic_fingerprint()
        except Exception as error:
            reason = f"commit observation fingerprint failed: {type(error).__name__}"
            self._audit({"type": "commit_rejected", "reason": reason})
            self._halt(reason)
            return CommitOutcome(False, reason, None, True)
        if fingerprint != certificate.observation_fingerprint:
            reason = "commit certificate is stale for the current public observation"
            self._audit({"type": "commit_rejected", "reason": reason})
            return CommitOutcome(False, reason, None, False)
        if _stack_signature(self.active) != certificate.active_stack_signature:
            reason = "commit certificate is stale for the active transaction stack"
            self._audit({"type": "commit_rejected", "reason": reason})
            return CommitOutcome(False, reason, None, False)
        if (
            action.bid != certificate.certified_bid
            or action.operation != certificate.certified_operation
        ):
            reason = "commit action differs from the certified BID or operation"
            self._audit({"type": "commit_rejected", "reason": reason})
            return CommitOutcome(False, reason, None, False)

        result = self._execute_action(action, "commit")
        if result is None:
            return CommitOutcome(
                False,
                self.halt_reason or "commit executor failed",
                None,
                True,
            )
        if result.action_error:
            reason = f"commit action reported an error: {result.action_error}"
            self._halt(reason)
            return CommitOutcome(False, reason, result, True)
        return CommitOutcome(
            True,
            "fresh positive certificate authorized the exact commit action",
            result,
            False,
        )
