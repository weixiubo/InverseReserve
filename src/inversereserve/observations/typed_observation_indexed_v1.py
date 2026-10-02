"""Indexed, semantics-preserving view of a public GUI snapshot.

The frozen :class:`~inversereserve.observations.typed_observation.SemanticSnapshot` deliberately
keeps a minimal representation, but its lookup helpers rebuild dictionaries
and rescan every element.  That is inexpensive on the primary corpus and
quadratic on WebArena's larger admin grids.  This successor keeps the exact
same retained fields, visibility rules, traversal order, and fingerprint; it
only precomputes public lookup indexes.
"""

from __future__ import annotations

import re
from collections import deque
from dataclasses import dataclass, field
from typing import Any

from inversereserve.observations.typed_observation import SemanticElement, SemanticSnapshot


@dataclass(frozen=True)
class IndexedSemanticSnapshotV1(SemanticSnapshot):
    """A ``SemanticSnapshot`` subtype with immutable lookup indexes."""

    _by_bid_index: dict[str, SemanticElement] = field(init=False, repr=False, compare=False)
    _ax_children: dict[str, tuple[SemanticElement, ...]] = field(init=False, repr=False, compare=False)
    _dom_children: dict[str, tuple[SemanticElement, ...]] = field(init=False, repr=False, compare=False)
    _effectively_visible: frozenset[str] = field(init=False, repr=False, compare=False)
    _semantic_fingerprint: tuple[tuple[Any, ...], ...] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        by_bid = {element.bid: element for element in self.elements}
        if len(by_bid) != len(self.elements):
            raise ValueError("indexed semantic snapshot has duplicate bids")

        ax_rows: dict[str, list[SemanticElement]] = {}
        dom_rows: dict[str, list[SemanticElement]] = {}
        for element in self.elements:
            if element.ax_parent_bid is not None:
                ax_rows.setdefault(element.ax_parent_bid, []).append(element)
            if element.dom_parent_bid is not None:
                dom_rows.setdefault(element.dom_parent_bid, []).append(element)

        object.__setattr__(self, "_by_bid_index", by_bid)
        object.__setattr__(
            self,
            "_ax_children",
            {bid: tuple(rows) for bid, rows in ax_rows.items()},
        )
        object.__setattr__(
            self,
            "_dom_children",
            {bid: tuple(rows) for bid, rows in dom_rows.items()},
        )

        visibility_cache: dict[str, bool] = {}

        def visible(bid: str) -> bool:
            if bid in visibility_cache:
                return visibility_cache[bid]
            element = by_bid.get(bid)
            if element is None or not element.visible:
                visibility_cache[bid] = False
                return False
            candidates = [element]
            seen = {bid}
            current = element
            while current.dom_parent_bid is not None:
                parent_bid = current.dom_parent_bid
                if parent_bid in seen:
                    raise ValueError("cyclic semantic element ancestry")
                seen.add(parent_bid)
                parent = by_bid.get(parent_bid)
                if parent is None:
                    break
                candidates.append(parent)
                current = parent
            result = True
            for candidate in candidates:
                attributes = dict(candidate.dom_attributes)
                style = re.sub(r"\s+", "", str(attributes.get("style", ""))).casefold()
                if (
                    str(attributes.get("aria-hidden", "")).casefold() == "true"
                    or "hidden" in attributes
                    or "display:none" in style
                    or "visibility:hidden" in style
                ):
                    result = False
                    break
            visibility_cache[bid] = result
            return result

        retained = frozenset(element.bid for element in self.elements if visible(element.bid))
        object.__setattr__(self, "_effectively_visible", retained)
        object.__setattr__(
            self,
            "_semantic_fingerprint",
            tuple(
                sorted(element.semantic_signature() for element in self.elements if element.bid in retained)
            ),
        )

    @classmethod
    def from_snapshot(cls, snapshot: SemanticSnapshot) -> "IndexedSemanticSnapshotV1":
        if isinstance(snapshot, cls):
            return snapshot
        return cls(snapshot.elements)

    @property
    def by_bid(self) -> dict[str, SemanticElement]:
        return dict(self._by_bid_index)

    def get(self, bid: str | None) -> SemanticElement | None:
        if bid is None:
            return None
        return self._by_bid_index.get(str(bid))

    def children(self, bid: str, *, relation: str = "ax") -> tuple[SemanticElement, ...]:
        if relation == "ax":
            return self._ax_children.get(str(bid), ())
        if relation == "dom":
            return self._dom_children.get(str(bid), ())
        raise ValueError("relation must be 'ax' or 'dom'")

    def ancestors(self, bid: str, *, relation: str = "ax") -> tuple[SemanticElement, ...]:
        if relation not in {"ax", "dom"}:
            raise ValueError("relation must be 'ax' or 'dom'")
        field_name = "ax_parent_bid" if relation == "ax" else "dom_parent_bid"
        result: list[SemanticElement] = []
        seen = {str(bid)}
        current = self.get(str(bid))
        while current is not None:
            parent_bid = getattr(current, field_name)
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
        if relation not in {"ax", "dom"}:
            raise ValueError("relation must be 'ax' or 'dom'")
        result: list[SemanticElement] = []
        frontier = deque(self.children(str(bid), relation=relation))
        seen = {str(bid)}
        while frontier:
            element = frontier.popleft()
            if element.bid in seen:
                raise ValueError("cyclic semantic element descendants")
            seen.add(element.bid)
            result.append(element)
            frontier.extend(self.children(element.bid, relation=relation))
        return tuple(result)

    def is_effectively_visible(self, bid: str) -> bool:
        return str(bid) in self._effectively_visible

    def semantic_fingerprint(self) -> tuple[tuple[Any, ...], ...]:
        return self._semantic_fingerprint
