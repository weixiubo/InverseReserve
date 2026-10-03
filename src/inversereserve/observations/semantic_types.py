"""Immutable public observation and contract records, independent of parsing and inference."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

RELEVANT_AX_PROPERTIES = frozenset(
    {
        "checked",
        "controls",
        "disabled",
        "expanded",
        "hasPopup",
        "invalid",
        "level",
        "multiselectable",
        "orientation",
        "pressed",
        "readonly",
        "required",
        "selected",
        "value",
    }
)
RELEVANT_DOM_ATTRIBUTES = frozenset(
    {
        "aria-checked",
        "aria-controls",
        "aria-disabled",
        "aria-expanded",
        "aria-haspopup",
        "aria-hidden",
        "aria-pressed",
        "aria-selected",
        "disabled",
        "hidden",
        "open",
        "role",
        "value",
    }
)


@dataclass(frozen=True)
class SemanticElement:
    bid: str
    role: str
    name: str
    subtree_text: str
    ax_properties: tuple[tuple[str, bool | int | float | str | None], ...]
    ax_parent_bid: str | None
    dom_tag: str
    dom_attributes: tuple[tuple[str, str], ...]
    dom_parent_bid: str | None
    visible: bool
    clickable: bool
    bbox: tuple[float, float, float, float] | None

    def ax_property(self, name: str, default: Any = None) -> Any:
        return dict(self.ax_properties).get(name, default)

    def dom_attribute(self, name: str, default: Any = None) -> Any:
        return dict(self.dom_attributes).get(name, default)

    @property
    def class_tokens(self) -> frozenset[str]:
        value = str(self.dom_attribute("class", ""))
        return frozenset((token.casefold() for token in value.split() if token))

    def semantic_signature(self) -> tuple[Any, ...]:
        ax_state = tuple(
            ((name, value) for name, value in self.ax_properties if name in RELEVANT_AX_PROPERTIES)
        )
        dom_state = tuple(
            ((name, value) for name, value in self.dom_attributes if name in RELEVANT_DOM_ATTRIBUTES)
        )
        return (
            self.bid,
            self.role,
            self.name,
            self.subtree_text,
            ax_state,
            self.dom_tag,
            dom_state,
            self.ax_parent_bid,
            self.dom_parent_bid,
            self.visible,
            self.clickable,
        )


@dataclass(frozen=True)
class SemanticSnapshot:
    elements: tuple[SemanticElement, ...]

    @property
    def by_bid(self) -> dict[str, SemanticElement]:
        return {element.bid: element for element in self.elements}

    def get(self, bid: str | None) -> SemanticElement | None:
        if bid is None:
            return None
        return self.by_bid.get(str(bid))

    def children(self, bid: str, *, relation: str = "ax") -> tuple[SemanticElement, ...]:
        field = "ax_parent_bid" if relation == "ax" else "dom_parent_bid"
        if relation not in {"ax", "dom"}:
            raise ValueError("relation must be 'ax' or 'dom'")
        return tuple((element for element in self.elements if getattr(element, field) == bid))

    def ancestors(self, bid: str, *, relation: str = "ax") -> tuple[SemanticElement, ...]:
        field = "ax_parent_bid" if relation == "ax" else "dom_parent_bid"
        if relation not in {"ax", "dom"}:
            raise ValueError("relation must be 'ax' or 'dom'")
        result = []
        seen = {bid}
        current = self.get(bid)
        while current is not None:
            parent_bid = getattr(current, field)
            if parent_bid is None:
                break
            if parent_bid in seen:
                raise ValueError("cyclic semantic element ancestry")
            seen.add(parent_bid)
            parent = self.get(parent_bid)
            if parent is None:
                break
            result.append(parent)
            current = parent
        return tuple(result)

    def descendants(self, bid: str, *, relation: str = "ax") -> tuple[SemanticElement, ...]:
        result = []
        frontier = list(self.children(bid, relation=relation))
        seen = {bid}
        while frontier:
            element = frontier.pop(0)
            if element.bid in seen:
                raise ValueError("cyclic semantic element descendants")
            seen.add(element.bid)
            result.append(element)
            frontier.extend(self.children(element.bid, relation=relation))
        return tuple(result)

    def is_effectively_visible(self, bid: str) -> bool:
        """Combine geometric visibility with public ancestor hiding semantics."""
        element = self.get(bid)
        if element is None or not element.visible:
            return False
        for candidate in (element,) + self.ancestors(bid, relation="dom"):
            attributes = dict(candidate.dom_attributes)
            if str(attributes.get("aria-hidden", "")).casefold() == "true":
                return False
            if "hidden" in attributes:
                return False
            style = re.sub("\\s+", "", str(attributes.get("style", ""))).casefold()
            if "display:none" in style or "visibility:hidden" in style:
                return False
        return True

    def semantic_fingerprint(self) -> tuple[tuple[Any, ...], ...]:
        return tuple(
            sorted(
                (
                    element.semantic_signature()
                    for element in self.elements
                    if self.is_effectively_visible(element.bid)
                )
            )
        )


@dataclass(frozen=True)
class SemanticDelta:
    added_visible_bids: tuple[str, ...]
    removed_visible_bids: tuple[str, ...]
    changed_visible_bids: tuple[str, ...]
    newly_visible_text: tuple[str, ...]

    @property
    def changed(self) -> bool:
        return bool(self.added_visible_bids or self.removed_visible_bids or self.changed_visible_bids)


@dataclass(frozen=True)
class PreviewContract:
    kind: str
    action_bid: str
    semantic_bid: str
    operation: str
    inverse_operation: str
    inverse_bid: str | None
    prior_selected_bid: str | None = None


@dataclass(frozen=True)
class ContractDecision:
    allowed: bool
    contract: PreviewContract | None
    reason: str


@dataclass(frozen=True)
class ContractCheck:
    passed: bool
    reason: str
    delta: SemanticDelta
