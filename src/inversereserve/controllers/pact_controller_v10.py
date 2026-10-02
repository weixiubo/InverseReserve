"""PACT-v10 runtime with reserve-preserving interrupt repair."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from inversereserve.contracts.transaction_actions_v4 import ContractActionV4
from inversereserve.contracts.typed_contracts_v4 import TransactionContractV4, public_compensator_bids
from inversereserve.controllers.pact_controller_v4 import (
    ActionExecutionV4,
    ActiveTransactionV4,
    RestorationOutcomeV4,
    TransactionOutcomeV4,
)
from inversereserve.controllers.pact_controller_v9 import FailClosedTransactionRuntimeV9
from inversereserve.observations.typed_observation import ContractCheck, SemanticSnapshot, semantic_delta


@dataclass(frozen=True)
class InterruptRepairReservationV10:
    """Exact GUI-action accounting after the first forward has executed."""

    remaining_gui_actions: int
    repair_pair_actions: int
    registered_inverse_reserve: int

    def __post_init__(self) -> None:
        if self.remaining_gui_actions < 0:
            raise ValueError("remaining GUI actions cannot be negative")
        if self.repair_pair_actions < 1:
            raise ValueError("an interrupt repair must consume at least one action")
        if self.registered_inverse_reserve < 1:
            raise ValueError("interrupt repair requires a registered inverse reserve")

    @property
    def allowed(self) -> bool:
        return self.remaining_gui_actions - self.repair_pair_actions >= self.registered_inverse_reserve


InterruptRepairReserveV10 = Callable[[TransactionContractV4], InterruptRepairReservationV10]


def interrupt_repair_action_cost_v10(contract: TransactionContractV4) -> int:
    """Worst-case compensator-plus-retry actions for the frozen repair policy."""
    return 2 * contract.maximum_interrupt_repairs


class FailClosedTransactionRuntimeV10(FailClosedTransactionRuntimeV9):
    """V9 postconditions plus reserve-preserving interrupt repair.

    An interrupt compensator and its retry are discretionary: they run only
    when both actions leave the complete active-plus-proposal inverse reserve
    untouched.  Otherwise the runtime takes the proposal's registered inverse.
    Ambiguous compensators are likewise never clicked and fall back to that
    inverse instead of leaving an avoidable unresolved mutation.
    """

    def __init__(self, executor, interrupt_repair_reserve: InterruptRepairReserveV10) -> None:
        super().__init__(executor)
        if not callable(interrupt_repair_reserve):
            raise ValueError("PACT-v10 requires an interrupt-repair reserve callback")
        self._interrupt_repair_reserve = interrupt_repair_reserve

    def _interrupt_repair_policy(
        self, contract: TransactionContractV4, compensators: tuple[str, ...]
    ) -> tuple[str, str]:
        if len(compensators) != 1:
            return ("inverse", "public interrupt compensator is ambiguous")
        if contract.maximum_interrupt_repairs < 1:
            return ("inverse", "public interrupt repair is not registered")
        reservation = self._interrupt_repair_reserve(contract)
        expected_pair_cost = interrupt_repair_action_cost_v10(contract)
        if reservation.repair_pair_actions != expected_pair_cost:
            raise ValueError("interrupt-repair reservation used the wrong pair cost")
        self._audit(
            {
                "type": "interrupt_repair_reservation",
                "remaining_gui_actions": reservation.remaining_gui_actions,
                "repair_pair_actions": reservation.repair_pair_actions,
                "registered_inverse_reserve": reservation.registered_inverse_reserve,
                "allowed": reservation.allowed,
            }
        )
        if not reservation.allowed:
            return ("inverse", "interrupt repair would consume registered inverse reserve")
        return ("attempt", "interrupt repair preserves registered inverse reserve")

    def _attempt_interrupt_repair_v10(
        self,
        *,
        before: SemanticSnapshot,
        contract: TransactionContractV4,
        candidate_label: str,
        post: ContractCheck | None,
        compensator_bid: str,
    ) -> TransactionOutcomeV4:
        compensation = self._execute(ContractActionV4("click", compensator_bid), "typed_compensator")
        if compensation is None:
            return TransactionOutcomeV4(
                False, self.halt_reason or "compensator executor failed", post, None, 0, True
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
            before, compensation.snapshot, contract, trigger="dynamic public compensation"
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
        return self._retry_compensated_transaction_v10(
            before, contract, candidate_label, post, restored, compensation
        )

    def transact(
        self, *, before: SemanticSnapshot, contract: TransactionContractV4, candidate_label: str
    ) -> TransactionOutcomeV4:
        """Execute a transaction while preserving every inverse reservation."""
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
        post = self._check_postcondition(before, first.snapshot, contract, context="typed forward")
        if post is not None and post.passed and (not first.action_error):
            transaction = ActiveTransactionV4(
                contract, candidate_label, before, first.snapshot, post.delta, 0
            )
            self.active.append(transaction)
            return TransactionOutcomeV4(
                True, "typed postcondition admitted the transaction", post, None, 0, False
            )
        if self.halted:
            return TransactionOutcomeV4(False, self.halt_reason or "verification failed", post, None, 0, True)
        compensators = public_compensator_bids(before, first.snapshot, contract)
        if compensators:
            policy, reason = self._interrupt_repair_policy(contract, compensators)
            self._audit(
                {
                    "type": "compensator_grounding",
                    "candidate_bids": list(compensators),
                    "allowed": policy == "attempt",
                    "policy": policy,
                    "reason": reason,
                }
            )
            if policy == "attempt":
                return self._attempt_interrupt_repair_v10(
                    before=before,
                    contract=contract,
                    candidate_label=candidate_label,
                    post=post,
                    compensator_bid=compensators[0],
                )
            if policy != "inverse":
                raise RuntimeError(f"unknown PACT-v10 interrupt policy: {policy}")
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
            trigger="forward action error" if first.action_error else "postcondition failed",
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

    def _retry_compensated_transaction_v10(
        self,
        before: SemanticSnapshot,
        contract: TransactionContractV4,
        candidate_label: str,
        post: ContractCheck | None,
        restored: ContractCheck,
        compensation: ActionExecutionV4,
    ) -> TransactionOutcomeV4:
        retry = self._execute(contract.action, "typed_retry")
        if retry is None:
            return TransactionOutcomeV4(
                False,
                self.halt_reason or "retry executor failed",
                post,
                RestorationOutcomeV4(True, True, restored.reason, restored, compensation.snapshot),
                1,
                True,
            )
        if retry.terminal:
            reason = "typed retry terminated or truncated the environment"
            self._halt(reason)
            return TransactionOutcomeV4(False, reason, post, None, 1, True)
        retry_post = self._check_postcondition(before, retry.snapshot, contract, context="typed retry")
        if retry_post is not None and retry_post.passed and (not retry.action_error):
            transaction = ActiveTransactionV4(
                contract, candidate_label, before, retry.snapshot, retry_post.delta, 1
            )
            self.active.append(transaction)
            return TransactionOutcomeV4(
                True,
                "public compensation restored state and one retry passed",
                retry_post,
                RestorationOutcomeV4(True, True, restored.reason, restored, compensation.snapshot),
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
        restoration = self._static_restore(failed, trigger="retry postcondition failed", remove_active=False)
        return TransactionOutcomeV4(
            False,
            "retry postcondition failed after one compensation",
            retry_post,
            restoration,
            1,
            self.halted,
        )
