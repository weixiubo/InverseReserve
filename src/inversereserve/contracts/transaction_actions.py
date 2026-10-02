"""Safe parameterized action primitives for successor PACT contracts.

The frozen C428 controller only needs single, argument-free click/hover
operations.  Fresh interaction types such as autocomplete and cancelable
dialogs require text arguments and, frequently, more than one inverse action.
This module provides that representation without modifying the frozen C428
source surface.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from inversereserve.observations.typed_observation import PreviewContract

BID_PATTERN = re.compile("[A-Za-z0-9]+")
SUPPORTED_OPERATIONS = frozenset({"click", "hover", "fill", "clear", "press", "move_to_neutral_region"})
ARGUMENT_OPERATIONS = frozenset({"fill", "press"})
BID_ONLY_OPERATIONS = frozenset({"click", "hover", "clear"})


def _valid_bid(value: str | None) -> bool:
    return value is not None and BID_PATTERN.fullmatch(value) is not None


def _valid_key_combination(value: str) -> bool:
    if not value or len(value) > 64:
        return False
    return all((character.isalnum() or character in {"+", "_", "-"} for character in value))


@dataclass(frozen=True)
class ContractAction:
    """One public BrowserGym action with a fully grounded argument surface."""

    operation: str
    bid: str | None = None
    argument: str | None = None
    enable_autocomplete_menu: bool = False

    def __post_init__(self) -> None:
        if self.operation not in SUPPORTED_OPERATIONS:
            raise ValueError(f"unsupported contract action: {self.operation}")
        if self.operation == "move_to_neutral_region":
            self._validate_neutral()
            return
        if not _valid_bid(self.bid):
            raise ValueError(f"unsafe BrowserGym bid: {self.bid!r}")
        if self.operation in BID_ONLY_OPERATIONS:
            self._validate_bid_only()
            return
        if self.operation in ARGUMENT_OPERATIONS:
            if self.argument is None:
                raise ValueError(f"{self.operation} requires an argument")
            if not isinstance(self.argument, str):
                raise ValueError(f"{self.operation} argument must be text")
        if self.operation == "press":
            self._validate_press()
        if self.operation == "fill" and (not isinstance(self.enable_autocomplete_menu, bool)):
            raise ValueError("enable_autocomplete_menu must be Boolean")

    def browsergym_code(
        self, *, viewport_width: int | None = None, viewport_height: int | None = None
    ) -> str:
        """Compile the primitive to strict BrowserGym high-level Python syntax."""
        if self.operation == "move_to_neutral_region":
            if viewport_width is None or viewport_height is None:
                raise ValueError("neutral pointer action requires viewport dimensions")
            if viewport_width <= 0 or viewport_height <= 0:
                raise ValueError("viewport dimensions must be positive")
            return f"mouse_move({max(1, viewport_width - 5)}, {max(1, viewport_height - 5)})"
        assert self.bid is not None
        if self.operation == "fill":
            assert self.argument is not None
            return f"fill({self.bid!r}, {self.argument!r}, {self.enable_autocomplete_menu!r})"
        if self.operation == "press":
            assert self.argument is not None
            return f"press({self.bid!r}, {self.argument!r})"
        return f"{self.operation}({self.bid!r})"

    def _validate_neutral(self) -> None:
        if self.bid is not None or self.argument is not None:
            raise ValueError("neutral pointer action cannot carry a bid or argument")
        if self.enable_autocomplete_menu:
            raise ValueError("neutral pointer action cannot enable autocomplete")

    def _validate_bid_only(self) -> None:
        if self.argument is not None:
            raise ValueError(f"{self.operation} cannot carry an argument")
        if self.enable_autocomplete_menu:
            raise ValueError(f"{self.operation} cannot enable autocomplete")

    def _validate_press(self) -> None:
        assert self.argument is not None
        if not _valid_key_combination(self.argument):
            raise ValueError(f"unsafe key combination: {self.argument!r}")
        if self.enable_autocomplete_menu:
            raise ValueError("press cannot enable autocomplete")


@dataclass(frozen=True)
class ActionSequenceContract:
    """A parameterized preview and the complete sequence that should reverse it."""

    kind: str
    semantic_bid: str
    action: ContractAction
    inverse_actions: tuple[ContractAction, ...]
    prior_selected_bid: str | None = None

    def __post_init__(self) -> None:
        if not self.kind.strip():
            raise ValueError("contract kind cannot be empty")
        if not _valid_bid(self.semantic_bid):
            raise ValueError(f"unsafe semantic bid: {self.semantic_bid!r}")
        if not self.inverse_actions:
            raise ValueError("a reversible contract requires at least one inverse action")
        if self.prior_selected_bid is not None and (not _valid_bid(self.prior_selected_bid)):
            raise ValueError(f"unsafe prior selected bid: {self.prior_selected_bid!r}")


def adapt_legacy_contract(contract: PreviewContract) -> ActionSequenceContract:
    """Represent an immutable C428 contract through the successor action surface."""
    action = ContractAction(contract.operation, contract.action_bid)
    inverse = ContractAction(contract.inverse_operation, contract.inverse_bid)
    return ActionSequenceContract(
        kind=contract.kind,
        semantic_bid=contract.semantic_bid,
        action=action,
        inverse_actions=(inverse,),
        prior_selected_bid=contract.prior_selected_bid,
    )
