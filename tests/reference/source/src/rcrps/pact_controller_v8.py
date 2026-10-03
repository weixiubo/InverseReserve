"""PACT-v8 typed runtime and inverse-budget accounting."""

from __future__ import annotations

from dataclasses import asdict

from .pact_controller_v4 import FailClosedTransactionRuntimeV4
from .typed_contracts_v4 import TransactionContractV4
from .typed_contracts_v8 import check_transaction_postcondition_v8
from .typed_observation import ContractCheck, SemanticSnapshot


from .recovery_capacity import (
    inverse_action_cost_v8 as inverse_action_cost_v8,
)


class FailClosedTransactionRuntimeV8(FailClosedTransactionRuntimeV4):
    """V4 runtime with the frozen, narrowly extended v8 postcondition."""

    def _check_postcondition(
        self,
        before: SemanticSnapshot,
        after: SemanticSnapshot,
        contract: TransactionContractV4,
        *,
        context: str,
    ) -> ContractCheck | None:
        try:
            check = check_transaction_postcondition_v8(before, after, contract)
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
                "checker_version": "PACT-v8-cross-channel",
            }
        )
        return check
