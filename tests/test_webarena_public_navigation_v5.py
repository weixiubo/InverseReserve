from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from rcrps.typed_observation import SemanticElement, SemanticSnapshot  # noqa: E402
from rcrps.webarena_public_navigation_v3 import (  # noqa: E402
    compile_public_navigation_v3,
)
from rcrps.webarena_public_navigation_v5 import (  # noqa: E402
    compile_public_navigation_v5,
    opened_row_edit_decision_v5,
    quoted_entity_row_action_decision_v5,
)


GOAL = 'Change the page title of "Home Page" page on my site to "New".'


def element(
    bid: str,
    *,
    role: str,
    name: str,
    tag: str,
    parent: str | None = None,
    href: str | None = None,
    clickable: bool = True,
) -> SemanticElement:
    attributes = {} if href is None else {"href": href}
    return SemanticElement(
        bid=bid,
        role=role,
        name=name,
        subtree_text=name,
        ax_properties=(),
        ax_parent_bid=parent,
        dom_tag=tag,
        dom_attributes=tuple(sorted(attributes.items())),
        dom_parent_bid=parent,
        visible=True,
        clickable=clickable,
        bbox=(0.0, 0.0, 100.0, 20.0),
    )


def grid_snapshot() -> SemanticSnapshot:
    return SemanticSnapshot(
        (
            element("page", role="main", name="Pages", tag="main", clickable=False),
            element("row_home", role="row", name="Home Page row", tag="tr", parent="page", clickable=False),
            element("home", role="gridcell", name="Home Page", tag="td", parent="row_home"),
            element("identifier", role="gridcell", name="home", tag="td", parent="row_home"),
            element("layout", role="gridcell", name="1 column", tag="td", parent="row_home"),
            element("select_home", role="button", name="Select", tag="button", parent="row_home"),
            element("row_other", role="row", name="Other row", tag="tr", parent="page", clickable=False),
            element("other", role="gridcell", name="Other Page", tag="td", parent="row_other"),
            element("select_other", role="button", name="Select", tag="button", parent="row_other"),
        )
    )


def test_row_action_is_promoted_and_preempts_inline_entity_click() -> None:
    snapshot = grid_snapshot()
    base = compile_public_navigation_v3(
        snapshot,
        current_url="http://example.local/admin/cms/page/",
        goal=GOAL,
        maximum_candidates=2,
    )
    assert "select_home" not in {row.bid for row in base.candidates}

    inventory = compile_public_navigation_v5(
        snapshot,
        current_url="http://example.local/admin/cms/page/",
        goal=GOAL,
        maximum_candidates=2,
    )
    assert inventory.row_action_binding.allowed is True
    assert inventory.row_action_binding.entity_bid == "home"
    assert inventory.row_action_binding.row_bids == ("row_home",)
    assert inventory.row_action_binding.action_bid == "select_home"
    assert inventory.row_action_binding.promoted is True
    assert "select_home" in {row.bid for row in inventory.candidates}

    decision = quoted_entity_row_action_decision_v5(inventory)
    assert decision is not None
    assert decision.candidate.bid == "select_home"
    assert decision.resolution_source == "quoted_entity_row_action"


def test_opened_row_requires_one_exact_visible_edit_action() -> None:
    snapshot = SemanticSnapshot(
        (
            element("edit", role="menuitem", name="Edit", tag="a", href="/edit/2"),
            element("delete", role="menuitem", name="Delete", tag="button"),
        )
    )
    inventory = compile_public_navigation_v5(
        snapshot,
        current_url="http://example.local/admin/cms/page/",
        goal=GOAL,
    )
    decision = opened_row_edit_decision_v5(inventory)
    assert decision is not None
    assert decision.candidate.bid == "edit"
    assert decision.resolution_source == "opened_row_edit"


def test_row_action_binding_fails_closed_when_two_rows_match_entity() -> None:
    snapshot = SemanticSnapshot(
        grid_snapshot().elements
        + (
            element("row_duplicate", role="row", name="Duplicate", tag="tr", parent="page", clickable=False),
            element("home_duplicate", role="gridcell", name="Home Page", tag="td", parent="row_duplicate"),
            element("select_duplicate", role="button", name="Select", tag="button", parent="row_duplicate"),
        )
    )
    inventory = compile_public_navigation_v5(
        snapshot,
        current_url="http://example.local/admin/cms/page/",
        goal=GOAL,
    )
    assert inventory.row_action_binding.allowed is False
    assert quoted_entity_row_action_decision_v5(inventory) is None
