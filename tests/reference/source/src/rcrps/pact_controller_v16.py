"""PACT-v16 runtime with reserve-preserving interrupt clearance.

V10 permits a compensator only when compensator plus retry leaves every
registered inverse untouched.  When that pair is unaffordable, immediately
executing an inverse can itself be impossible because the interrupt disables
the contracted control.  V16 adds one strictly cheaper branch: execute the
unique registered compensator, do not retry, and either accept its verified
restoration or spend the still-reserved inverse immediately.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict, dataclass

from .pact_controller_v4 import (
    ActionExecutionV4,
    ActiveTransactionV4,
    RestorationOutcomeV4,
    TransactionOutcomeV4,
)
from .pact_controller_v10 import interrupt_repair_action_cost_v10
from .pact_controller_v15 import FailClosedTransactionRuntimeV15
from .transaction_actions_v4 import ContractActionV4
from .typed_contracts_v4 import (
    TransactionContractV4,
    check_transaction_restoration,
    public_compensator_bids,
)
from .typed_observation import ContractCheck, SemanticSnapshot, semantic_delta


@dataclass(frozen=True)
class ActiveRestoreClearanceReservationV16:
    """One public clearance action that leaves the active inverse stack intact."""

    remaining_gui_actions: int
    clearance_actions: int
    active_inverse_reserve: int

    def __post_init__(self) -> None:
        if self.remaining_gui_actions < 0:
            raise ValueError("remaining GUI actions cannot be negative")
        if self.clearance_actions != 1:
            raise ValueError("PACT-v16 clearance is exactly one GUI action")
        if self.active_inverse_reserve < 1:
            raise ValueError("active restoration requires a positive inverse reserve")

    @property
    def allowed(self) -> bool:
        return (
            self.remaining_gui_actions - self.clearance_actions
            >= self.active_inverse_reserve
        )


ActiveRestoreClearanceReserveV16 = Callable[
    [TransactionContractV4], ActiveRestoreClearanceReservationV16
]


class FailClosedTransactionRuntimeV16(FailClosedTransactionRuntimeV15):
    """Clear a unique interrupt without borrowing inverse capacity."""

    def __init__(
        self,
        executor,
        interrupt_repair_reserve,
        active_restore_clearance_reserve: ActiveRestoreClearanceReserveV16,
    ) -> None:
        super().__init__(executor, interrupt_repair_reserve)
        if not callable(active_restore_clearance_reserve):
            raise ValueError(
                "PACT-v16 requires an active-restore clearance reserve callback"
            )
        self._active_restore_clearance_reserve = active_restore_clearance_reserve
        self._pending_interrupt_mode_v16: str | None = None

    def _interrupt_repair_policy(
        self,
        contract: TransactionContractV4,
        compensators: tuple[str, ...],
    ) -> tuple[str, str]:
        self._pending_interrupt_mode_v16 = None
        if len(compensators) != 1:
            return "inverse", "public interrupt compensator is ambiguous"
        if contract.maximum_interrupt_repairs < 1:
            return "inverse", "public interrupt repair is not registered"
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
        if reservation.allowed:
            self._pending_interrupt_mode_v16 = "compensate_then_retry"
            return "attempt", "interrupt repair preserves registered inverse reserve"

        clearance_actions = 1
        clearance_allowed = (
            reservation.remaining_gui_actions - clearance_actions
            >= reservation.registered_inverse_reserve
        )
        self._audit(
            {
                "type": "interrupt_clearance_reservation_v16",
                "remaining_gui_actions": reservation.remaining_gui_actions,
                "clearance_actions": clearance_actions,
                "registered_inverse_reserve": reservation.registered_inverse_reserve,
                "retry_actions": 0,
                "allowed": clearance_allowed,
            }
        )
        if clearance_allowed:
            self._pending_interrupt_mode_v16 = "clear_then_restore"
            return (
                "attempt",
                "unique interrupt clearance leaves the complete inverse reserve",
            )
        return "inverse", "interrupt clearance would consume registered inverse reserve"

    def _clear_then_restore_v16(
        self,
        *,
        before: SemanticSnapshot,
        contract: TransactionContractV4,
        candidate_label: str,
        post: ContractCheck | None,
        compensator_bid: str,
    ) -> TransactionOutcomeV4:
        compensation = self._execute(
            ContractActionV4("click", compensator_bid),
            "typed_compensator",
        )
        if compensation is None:
            return TransactionOutcomeV4(
                False,
                self.halt_reason or "interrupt-clearance executor failed",
                post,
                None,
                0,
                True,
            )
        if compensation.terminal or compensation.action_error:
            reason = (
                "interrupt clearance terminated or truncated the environment"
                if compensation.terminal
                else "interrupt clearance reported an error: "
                f"{compensation.action_error}"
            )
            self._halt(reason)
            return TransactionOutcomeV4(False, reason, post, None, 0, True)

        try:
            clearance_check = check_transaction_restoration(
                before,
                compensation.snapshot,
                contract,
            )
        except Exception as error:
            reason = (
                "interrupt-clearance verifier raised an exception: "
                f"{type(error).__name__}: {error}"
            )
            self._audit(
                {
                    "type": "verification_exception",
                    "context": "reserve-preserving interrupt clearance v16",
                    "reason": reason,
                }
            )
            self._halt(reason)
            return TransactionOutcomeV4(False, reason, post, None, 1, True)

        self._audit(
            {
                "type": "interrupt_clearance_projection_v16",
                "passed": clearance_check.passed,
                "reason": clearance_check.reason,
                "projection_kind": contract.projection_kind,
                "retry_issued": False,
            }
        )
        if clearance_check.passed:
            self._audit(
                {
                    "type": "restoration",
                    "trigger": "reserve-preserving interrupt clearance v16",
                    "projection_kind": contract.projection_kind,
                    "passed": True,
                    "reason": clearance_check.reason,
                    "global_delta": asdict(clearance_check.delta),
                    "global_delta_empty": not clearance_check.delta.changed,
                    "attempted": True,
                    "inverse_skipped": True,
                }
            )
            self._audit(
                {
                    "type": "interrupt_clearance_restoration_v16",
                    "phase": "rejected_forward",
                    "passed": True,
                    "inverse_issued": False,
                    "reason": clearance_check.reason,
                }
            )
            restoration = RestorationOutcomeV4(
                True,
                True,
                clearance_check.reason,
                clearance_check,
                compensation.snapshot,
            )
            return TransactionOutcomeV4(
                False,
                "unique interrupt clearance restored the rejected forward",
                post,
                restoration,
                1,
                False,
            )

        failed = ActiveTransactionV4(
            contract,
            candidate_label,
            before,
            compensation.snapshot,
            semantic_delta(before, compensation.snapshot),
            1,
        )
        restoration = self._static_restore(
            failed,
            trigger="interrupt clearance followed by registered inverse v16",
            remove_active=False,
        )
        self._audit(
            {
                "type": "interrupt_clearance_restoration_v16",
                "phase": "rejected_forward",
                "passed": restoration.passed,
                "inverse_issued": True,
                "reason": restoration.reason,
            }
        )
        return TransactionOutcomeV4(
            False,
            (
                "unique interrupt clearance enabled registered restoration"
                if restoration.passed
                else restoration.reason
            ),
            post,
            restoration,
            1,
            self.halted,
        )

    def _attempt_interrupt_repair_v10(
        self,
        *,
        before: SemanticSnapshot,
        contract: TransactionContractV4,
        candidate_label: str,
        post: ContractCheck | None,
        compensator_bid: str,
    ) -> TransactionOutcomeV4:
        mode = self._pending_interrupt_mode_v16
        self._pending_interrupt_mode_v16 = None
        if mode == "compensate_then_retry":
            return super()._attempt_interrupt_repair_v10(
                before=before,
                contract=contract,
                candidate_label=candidate_label,
                post=post,
                compensator_bid=compensator_bid,
            )
        if mode == "clear_then_restore":
            return self._clear_then_restore_v16(
                before=before,
                contract=contract,
                candidate_label=candidate_label,
                post=post,
                compensator_bid=compensator_bid,
            )
        raise RuntimeError("PACT-v16 interrupt attempt has no frozen policy mode")

    def _active_restore_clearance_v16(
        self,
        transaction: ActiveTransactionV4,
        *,
        trigger: str,
        remove_active: bool,
        compensator_bid: str,
    ) -> RestorationOutcomeV4:
        reservation = self._active_restore_clearance_reserve(transaction.contract)
        self._audit(
            {
                "type": "active_restore_clearance_reservation_v16",
                "remaining_gui_actions": reservation.remaining_gui_actions,
                "clearance_actions": reservation.clearance_actions,
                "active_inverse_reserve": reservation.active_inverse_reserve,
                "allowed": reservation.allowed,
            }
        )
        if not reservation.allowed:
            return super()._static_restore(
                transaction,
                trigger=trigger,
                remove_active=remove_active,
            )

        clearance: ActionExecutionV4 | None = self._execute(
            ContractActionV4("click", compensator_bid),
            "typed_restore_compensator",
        )
        if clearance is None:
            return RestorationOutcomeV4(
                True,
                False,
                self.halt_reason or "active-restore clearance executor failed",
                None,
                None,
            )
        if clearance.terminal or clearance.action_error:
            reason = (
                "active-restore clearance terminated or truncated the environment"
                if clearance.terminal
                else "active-restore clearance reported an error: "
                f"{clearance.action_error}"
            )
            self._halt(reason)
            return RestorationOutcomeV4(True, False, reason, None, clearance.snapshot)

        try:
            check = check_transaction_restoration(
                transaction.before,
                clearance.snapshot,
                transaction.contract,
            )
        except Exception as error:
            reason = (
                "active-restore clearance verifier raised an exception: "
                f"{type(error).__name__}: {error}"
            )
            self._audit(
                {
                    "type": "verification_exception",
                    "context": "active-restore interrupt clearance v16",
                    "reason": reason,
                }
            )
            self._halt(reason)
            return RestorationOutcomeV4(True, False, reason, None, clearance.snapshot)

        self._audit(
            {
                "type": "active_restore_clearance_projection_v16",
                "passed": check.passed,
                "reason": check.reason,
                "projection_kind": transaction.contract.projection_kind,
            }
        )
        if check.passed:
            if remove_active:
                if not self.active or self.active[-1] is not transaction:
                    raise RuntimeError(
                        "clearance restoration must pop the active transaction top"
                    )
                self.active.pop()
            self.completed.append(
                {
                    **transaction.planner_record(),
                    "restored": True,
                    "trigger": trigger,
                    "interrupt_clearance_v16": True,
                }
            )
            self._audit(
                {
                    "type": "restoration",
                    "trigger": "active-restore interrupt clearance v16",
                    "projection_kind": transaction.contract.projection_kind,
                    "passed": True,
                    "reason": check.reason,
                    "global_delta": asdict(check.delta),
                    "global_delta_empty": not check.delta.changed,
                    "attempted": True,
                    "inverse_skipped": True,
                }
            )
            self._audit(
                {
                    "type": "interrupt_clearance_restoration_v16",
                    "phase": "active_restore",
                    "passed": True,
                    "inverse_issued": False,
                    "reason": check.reason,
                }
            )
            return RestorationOutcomeV4(
                True,
                True,
                check.reason,
                check,
                clearance.snapshot,
            )

        outcome = super()._static_restore(
            transaction,
            trigger=f"{trigger}; after reserve-preserving clearance v16",
            remove_active=remove_active,
        )
        self._audit(
            {
                "type": "interrupt_clearance_restoration_v16",
                "phase": "active_restore",
                "passed": outcome.passed,
                "inverse_issued": True,
                "reason": outcome.reason,
            }
        )
        return outcome

    def _static_restore(
        self,
        transaction: ActiveTransactionV4,
        *,
        trigger: str,
        remove_active: bool,
    ) -> RestorationOutcomeV4:
        # Rejected forwards already receive proposal-aware clearance in
        # _clear_then_restore_v16. This branch is exclusively for an item that
        # is already charged to the active inverse stack.
        current = self._live_public_snapshot_v15
        if (
            remove_active
            and current is not None
            and transaction.contract.maximum_interrupt_repairs >= 1
        ):
            compensators = public_compensator_bids(
                transaction.before,
                current,
                transaction.contract,
            )
            self._audit(
                {
                    "type": "active_restore_compensator_grounding_v16",
                    "candidate_bids": list(compensators),
                    "allowed": len(compensators) == 1,
                }
            )
            if len(compensators) == 1:
                return self._active_restore_clearance_v16(
                    transaction,
                    trigger=trigger,
                    remove_active=remove_active,
                    compensator_bid=compensators[0],
                )
        return super()._static_restore(
            transaction,
            trigger=trigger,
            remove_active=remove_active,
        )


__all__ = [
    "ActiveRestoreClearanceReservationV16",
    "ActiveRestoreClearanceReserveV16",
    "FailClosedTransactionRuntimeV16",
]
