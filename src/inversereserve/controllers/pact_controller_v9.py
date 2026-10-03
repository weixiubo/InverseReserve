"""PACT-v9 typed runtime with suggestion-population evidence."""

from __future__ import annotations

from dataclasses import asdict

from inversereserve.contracts.typed_contracts_v4 import TransactionContractV4
from inversereserve.contracts.typed_contracts_v9 import check_transaction_postcondition_v9
from inversereserve.controllers.pact_controller_v8 import FailClosedTransactionRuntimeV8
from inversereserve.observations.typed_observation import ContractCheck, SemanticSnapshot


class FailClosedTransactionRuntimeV9(FailClosedTransactionRuntimeV8):
    """V8 runtime with the narrow, public-only v9 postcondition extension."""

    def _check_postcondition(
        self,
        before: SemanticSnapshot,
        after: SemanticSnapshot,
        contract: TransactionContractV4,
        *,
        context: str,
    ) -> ContractCheck | None:
        try:
            check = check_transaction_postcondition_v9(before, after, contract)
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
                "checker_version": "PACT-v9-suggestion-population",
            }
        )
        return check
