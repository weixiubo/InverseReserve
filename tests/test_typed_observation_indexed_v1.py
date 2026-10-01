from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from rcrps.typed_observation import SemanticElement, SemanticSnapshot  # noqa: E402
from rcrps.typed_observation_indexed_v1 import (  # noqa: E402
    IndexedSemanticSnapshotV1,
)


def element(
    bid: str,
    *,
    parent: str | None = None,
    visible: bool = True,
    attributes: dict[str, str] | None = None,
) -> SemanticElement:
    return SemanticElement(
        bid=bid,
        role="generic",
        name=bid,
        subtree_text=bid,
        ax_properties=(),
        ax_parent_bid=parent,
        dom_tag="div",
        dom_attributes=tuple(sorted((attributes or {}).items())),
        dom_parent_bid=parent,
        visible=visible,
        clickable=False,
        bbox=(0.0, 0.0, 10.0, 10.0),
    )


def test_indexed_snapshot_preserves_lookup_visibility_and_traversal() -> None:
    frozen = SemanticSnapshot(
        (
            element("root"),
            element("first", parent="root"),
            element("second", parent="root"),
            element("hidden", parent="first", attributes={"aria-hidden": "true"}),
            element("child", parent="hidden"),
            element("geometric-parent", visible=False),
            element("visible-child", parent="geometric-parent"),
            element("orphan", parent="missing"),
        )
    )
    indexed = IndexedSemanticSnapshotV1.from_snapshot(frozen)

    for bid in (
        "root",
        "first",
        "second",
        "hidden",
        "child",
        "geometric-parent",
        "visible-child",
        "orphan",
        "none",
    ):
        assert indexed.get(bid) == frozen.get(bid)
        assert indexed.is_effectively_visible(bid) == frozen.is_effectively_visible(bid)
    for relation in ("ax", "dom"):
        for bid in ("root", "first", "hidden", "orphan"):
            assert indexed.children(bid, relation=relation) == frozen.children(
                bid, relation=relation
            )
            assert indexed.ancestors(bid, relation=relation) == frozen.ancestors(
                bid, relation=relation
            )
            assert indexed.descendants(bid, relation=relation) == frozen.descendants(
                bid, relation=relation
            )
    assert indexed.semantic_fingerprint() == frozen.semantic_fingerprint()
    assert IndexedSemanticSnapshotV1.from_snapshot(indexed) is indexed
    copied_lookup = indexed.by_bid
    copied_lookup.pop("root")
    assert indexed.get("root") is not None
