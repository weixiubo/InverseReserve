from __future__ import annotations

from inversereserve.contracts.typed_contracts_v4 import TransactionContractV4


def inverse_action_cost_v8(contract: TransactionContractV4) -> int:
    """Conservative GUI actions needed to restore one active transaction."""

    if contract.dynamic_inverse_class_token is not None:
        return 1
    return len(contract.inverse_actions)


def remaining_after_action(maximum_gui_actions: int, used_actions: int) -> int:
    """Remaining slots after the proposed action; negative values stay negative."""
    return int(maximum_gui_actions) - used_actions - 1
