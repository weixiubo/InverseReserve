"""Offline accounting example; no browser or model dependency."""

import json

from inversereserve.contracts.transaction_actions_v4 import ContractActionV4
from inversereserve.contracts.typed_contracts_v4 import TransactionContractV4
from inversereserve.core.recovery_capacity import inverse_action_cost_v8, remaining_after_action


def example():
    contract = TransactionContractV4(
        kind="field_edit",
        semantic_bid="field",
        action=ContractActionV4("fill", "field", "new"),
        inverse_actions=(ContractActionV4("fill", "field", "old"),),
    )
    reserve = inverse_action_cost_v8(contract)
    return [
        {
            "maximum": budget,
            "used": 2,
            "reserve": reserve,
            "remaining_after_action": remaining_after_action(budget, 2),
            "allowed": remaining_after_action(budget, 2) >= reserve,
        }
        for budget in [2, 3, 4]
    ]


if __name__ == "__main__":
    print(json.dumps(example(), indent=2))
