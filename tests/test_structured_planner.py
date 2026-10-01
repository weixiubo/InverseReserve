from __future__ import annotations

import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from rcrps.structured_planner import (  # noqa: E402
    ActionCandidate,
    action_candidates,
    parse_planner_decision,
    planner_messages,
    render_action_inventory,
)
from rcrps.typed_observation import SemanticElement, SemanticSnapshot  # noqa: E402


def element(
    bid: str,
    *,
    role: str = "",
    name: str = "",
    parent: str | None = None,
    dom_parent: str | None = None,
    properties: dict | None = None,
    tag: str = "div",
    classes: str = "",
    visible: bool = True,
    clickable: bool = True,
    text: str = "",
) -> SemanticElement:
    attrs = (("class", classes),) if classes else ()
    return SemanticElement(
        bid=bid,
        role=role,
        name=name,
        subtree_text=text or name,
        ax_properties=tuple(sorted((properties or {}).items())),
        ax_parent_bid=parent,
        dom_tag=tag,
        dom_attributes=attrs,
        dom_parent_bid=dom_parent,
        visible=visible,
        clickable=clickable,
        bbox=(0.0, 0.0, 10.0, 10.0),
    )


def test_inventory_exposes_typed_exploration_and_direct_commit() -> None:
    snapshot = SemanticSnapshot(
        (
            element("list", role="tablist", clickable=False),
            element(
                "header",
                role="tab",
                name="Section 1",
                parent="list",
                properties={"expanded": False, "selected": False, "controls": "panel"},
            ),
            element("submit", role="button", name="Submit"),
        )
    )

    rows = action_candidates(snapshot)
    lookup = {row.bid: row for row in rows}
    assert lookup["header"].preview_kind == "disclosure_toggle"
    assert lookup["header"].operation == "click"
    assert lookup["submit"].preview_kind is None
    assert lookup["submit"].label == "Submit"
    rendered = render_action_inventory(rows)
    assert '"preview_kind": "disclosure_toggle"' in rendered
    assert '"label": "Submit"' in rendered


def test_terminal_button_descendant_is_not_suppressed_by_parent_contract() -> None:
    snapshot = SemanticSnapshot(
        (
            element("list", role="tablist", clickable=False),
            element(
                "section",
                role="tab",
                name="Section",
                parent="list",
                properties={"expanded": True, "selected": True},
                clickable=True,
            ),
            element(
                "submit-tab",
                role="tab",
                name="Submit",
                parent="list",
                properties={"expanded": False, "selected": False},
                clickable=True,
            ),
            element(
                "submit",
                role="button",
                name="Submit",
                parent="submit-tab",
            ),
        )
    )

    lookup = {row.bid: row for row in action_candidates(snapshot)}
    assert lookup["submit-tab"].preview_kind == "tab_switch"
    assert lookup["submit"].preview_kind is None
    assert lookup["submit"].role == "button"


def test_file_control_is_a_direct_candidate_with_owner_text() -> None:
    snapshot = SemanticSnapshot(
        (
            element("tree", role="list", tag="ul", clickable=False),
            element("li", role="listitem", parent="tree", tag="li", text="Report"),
            element(
                "file",
                dom_parent="li",
                tag="span",
                classes="file",
                clickable=False,
            ),
        )
    )
    lookup = {row.bid: row for row in action_candidates(snapshot)}
    assert lookup["file"].role == "file"
    assert lookup["file"].label == "Report"
    assert lookup["file"].preview_kind is None
    assert "li" not in lookup


def test_planner_parser_enforces_inventory_and_typed_exploration() -> None:
    direct = ActionCandidate("save", "click", "button", "Save", (), None, "save", None)
    typed = ActionCandidate(
        "section",
        "click",
        "tab",
        "Section",
        (("expanded", False),),
        "disclosure_toggle",
        "section",
        None,
    )
    rows = (direct, typed)

    commit = parse_planner_decision('{"decision":"commit","bid":"save"}', rows)
    explore = parse_planner_decision(
        '```json\n{"decision":"explore","bid":"section"}\n```', rows
    )
    abstain = parse_planner_decision('{"decision":"abstain","bid":null}', rows)
    assert commit.candidate == direct
    assert explore.candidate == typed
    assert abstain.candidate is None

    with pytest.raises(ValueError, match="untyped control"):
        parse_planner_decision('{"decision":"explore","bid":"save"}', rows)
    with pytest.raises(ValueError, match="absent"):
        parse_planner_decision('{"decision":"commit","bid":"missing"}', rows)
    with pytest.raises(ValueError, match="after the JSON"):
        parse_planner_decision(
            '{"decision":"commit","bid":"save"} explanation', rows
        )


def test_prompt_has_equal_grounded_schema() -> None:
    row = ActionCandidate("save", "click", "button", "Save", (), None, "save", None)
    messages = planner_messages(goal="Click Save", candidates=(row,))
    assert messages[0]["role"] == "system"
    assert "commit|explore|abstain" in messages[0]["content"]
    assert "ACTIVE TYPED TRANSACTIONS" in messages[1]["content"]
    assert "COMPLETED EXPLORATIONS" in messages[1]["content"]
    assert "VISIBLE ACTION INVENTORY (1 rows)" in messages[1]["content"]
    assert '"bid": "save"' in messages[1]["content"]
