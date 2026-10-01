from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from rcrps.structured_planner import planner_messages  # noqa: E402
from rcrps.structured_planner_v3 import successor_action_inventory  # noqa: E402
from rcrps.typed_observation import SemanticElement, SemanticSnapshot  # noqa: E402


def element(
    bid: str,
    *,
    role: str,
    name: str,
    tag: str,
    properties: tuple[tuple[str, object], ...] = (),
    attributes: tuple[tuple[str, str], ...] = (),
) -> SemanticElement:
    return SemanticElement(
        bid=bid,
        role=role,
        name=name,
        subtree_text=name,
        ax_properties=properties,
        ax_parent_bid=None,
        dom_tag=tag,
        dom_attributes=attributes,
        dom_parent_bid=None,
        visible=True,
        clickable=True,
        bbox=(0.0, 0.0, 10.0, 10.0),
    )


def snapshot() -> SemanticSnapshot:
    return SemanticSnapshot(
        (
            element(
                "country",
                role="combobox",
                name="Country",
                tag="input",
                properties=(
                    ("autocomplete", "list"),
                    ("hasPopup", "listbox"),
                ),
                attributes=(
                    ("aria-autocomplete", "list"),
                    ("aria-haspopup", "listbox"),
                ),
            ),
            element(
                "help",
                role="button",
                name="Open help",
                tag="button",
                properties=(("hasPopup", "dialog"),),
                attributes=(("aria-haspopup", "dialog"),),
            ),
            element(
                "save",
                role="button",
                name="Save",
                tag="button",
            ),
        )
    )


def test_successor_inventory_exposes_parameterized_and_popup_contracts() -> None:
    result = successor_action_inventory(
        snapshot(),
        'Enter an item that starts with "Mon" and ends with "ia".',
    )
    lookup = {row.bid: row for row in result.candidates}
    assert result.allowed
    assert result.query == "Mon"
    assert result.constraint_record() == {
        "kind": "prefix_suffix",
        "prefix": "Mon",
        "suffix": "ia",
        "exact": None,
    }
    assert lookup["country"].preview_kind == "combobox_suggestion"
    assert lookup["country"].operation == "fill"
    assert lookup["help"].preview_kind == "popup_dialog_open"
    assert lookup["help"].operation == "click"
    assert lookup["save"].preview_kind is None


def test_suffix_only_constraint_uses_click_popup_without_inventing_a_query() -> None:
    result = successor_action_inventory(
        snapshot(),
        'Choose an item that ends with "stan".',
    )
    lookup = {row.bid: row for row in result.candidates}
    assert result.allowed and result.query is None
    assert lookup["country"].preview_kind == "popup_dialog_open"
    assert lookup["country"].operation == "click"
    assert lookup["help"].preview_kind == "popup_dialog_open"


def test_missing_positive_constraint_produces_an_empty_planner_inventory() -> None:
    result = successor_action_inventory(snapshot(), "Do what is appropriate.")
    assert not result.allowed
    assert result.candidates == ()
    messages = planner_messages(goal="Do what is appropriate.", candidates=())
    assert "VISIBLE ACTION INVENTORY (0 rows)" in messages[1]["content"]


def test_exact_constraint_is_publicly_carried_into_planner_inventory() -> None:
    goal = 'Click the button labeled "Close".'
    result = successor_action_inventory(snapshot(), goal)
    lookup = {row.bid: row for row in result.candidates}
    assert result.allowed and result.query == "Close"
    assert lookup["help"].preview_kind == "popup_dialog_open"
    assert lookup["country"].preview_kind == "combobox_suggestion"
    messages = planner_messages(goal=goal, candidates=result.candidates)
    assert '"preview_kind": "popup_dialog_open"' in messages[1]["content"]
    assert '"preview_kind": "combobox_suggestion"' in messages[1]["content"]
