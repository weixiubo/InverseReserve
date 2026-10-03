"""Argument-safe BrowserGym primitives for PACT v4 contracts."""

from __future__ import annotations

import re
from dataclasses import dataclass

BID_PATTERN = re.compile("[A-Za-z0-9]+")
SUPPORTED_OPERATIONS = frozenset(
    {"click", "hover", "fill", "clear", "press", "select_option", "move_to_neutral_region"}
)
BID_ONLY_OPERATIONS = frozenset({"click", "hover", "clear"})


def _valid_bid(value: str | None) -> bool:
    return value is not None and BID_PATTERN.fullmatch(value) is not None


def _valid_key_combination(value: str) -> bool:
    return (
        bool(value)
        and len(value) <= 64
        and all((character.isalnum() or character in {"+", "_", "-"} for character in value))
    )


@dataclass(frozen=True)
class ContractActionV4:
    operation: str
    bid: str | None = None
    argument: str | tuple[str, ...] | None = None
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
        if self.operation == "fill":
            if not isinstance(self.argument, str):
                raise ValueError("fill requires a text argument")
            if not isinstance(self.enable_autocomplete_menu, bool):
                raise ValueError("enable_autocomplete_menu must be Boolean")
            return
        if self.operation == "press":
            self._validate_press()
            return
        if self.operation == "select_option":
            self._validate_selection()
            return
        if self.operation == "clear":
            return
        raise AssertionError("unvalidated contract action operation")

    def browsergym_code(
        self, *, viewport_width: int | None = None, viewport_height: int | None = None
    ) -> str:
        if self.operation == "move_to_neutral_region":
            if viewport_width is None or viewport_height is None:
                raise ValueError("neutral pointer action requires viewport dimensions")
            if viewport_width <= 0 or viewport_height <= 0:
                raise ValueError("viewport dimensions must be positive")
            return f"mouse_move({max(1, viewport_width - 5)}, {max(1, viewport_height - 5)})"
        assert self.bid is not None
        if self.operation == "fill":
            assert isinstance(self.argument, str)
            return f"fill({self.bid!r}, {self.argument!r}, {self.enable_autocomplete_menu!r})"
        if self.operation == "press":
            assert isinstance(self.argument, str)
            return f"press({self.bid!r}, {self.argument!r})"
        if self.operation == "select_option":
            assert isinstance(self.argument, tuple)
            return f"select_option({self.bid!r}, {list(self.argument)!r})"
        return f"{self.operation}({self.bid!r})"

    def _validate_neutral(self) -> None:
        if self.bid is not None or self.argument is not None:
            raise ValueError("neutral pointer action cannot carry bid or argument")
        if self.enable_autocomplete_menu:
            raise ValueError("neutral pointer action cannot enable autocomplete")

    def _validate_bid_only(self) -> None:
        if self.argument is not None:
            raise ValueError(f"{self.operation} cannot carry an argument")
        if self.enable_autocomplete_menu:
            raise ValueError(f"{self.operation} cannot enable autocomplete")

    def _validate_press(self) -> None:
        if not isinstance(self.argument, str):
            raise ValueError("press requires a text argument")
        if not _valid_key_combination(self.argument):
            raise ValueError(f"unsafe key combination: {self.argument!r}")
        if self.enable_autocomplete_menu:
            raise ValueError("press cannot enable autocomplete")

    def _validate_selection(self) -> None:
        if not isinstance(self.argument, tuple) or any(
            (not isinstance(value, str) or not value or len(value) > 512 for value in self.argument)
        ):
            raise ValueError("select_option requires a tuple of safe values")
        if len(set(self.argument)) != len(self.argument):
            raise ValueError("select_option values must be unique")
        if self.enable_autocomplete_menu:
            raise ValueError("select_option cannot enable autocomplete")
