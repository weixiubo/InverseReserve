from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from rcrps.goal_contracts_v4 import compile_structured_goal
from rcrps.typed_observation import SemanticElement, SemanticSnapshot


def element(
    bid: str,
    *,
    role: str = "generic",
    name: str = "",
    text: str = "",
    tag: str = "div",
    attributes: dict[str, str] | None = None,
    properties: dict[str, object] | None = None,
    ax_parent: str | None = None,
    dom_parent: str | None = None,
    visible: bool = True,
    clickable: bool = False,
) -> SemanticElement:
    return SemanticElement(
        bid=bid,
        role=role,
        name=name,
        subtree_text=text,
        ax_properties=tuple(sorted((properties or {}).items())),
        ax_parent_bid=ax_parent,
        dom_tag=tag,
        dom_attributes=tuple(sorted((attributes or {}).items())),
        dom_parent_bid=dom_parent,
        visible=visible,
        clickable=clickable,
        bbox=(0.0, 0.0, 10.0, 10.0),
    )


def login_snapshot() -> SemanticSnapshot:
    return SemanticSnapshot(
        (
            element("form", text="Username Password OK"),
            element("userrow", text="Username", dom_parent="form"),
            element(
                "user",
                role="textbox",
                tag="input",
                properties={"readonly": False},
                dom_parent="userrow",
                clickable=True,
            ),
            element("passrow", text="Password", dom_parent="form"),
            element(
                "pass",
                role="textbox",
                tag="input",
                attributes={"type": "password"},
                properties={"readonly": False},
                dom_parent="passrow",
                clickable=True,
            ),
        )
    )


def flight_snapshot() -> SemanticSnapshot:
    return SemanticSnapshot(
        (
            element(
                "from",
                role="textbox",
                name="From:",
                tag="input",
                properties={"readonly": False},
                clickable=True,
            ),
            element(
                "to",
                role="textbox",
                name="To:",
                tag="input",
                properties={"readonly": False},
                clickable=True,
            ),
            element(
                "date",
                role="textbox",
                tag="input",
                attributes={"readonly": "", "class": "hasDatepicker"},
                properties={"readonly": True},
                clickable=True,
            ),
        )
    )


def scroll_snapshot(*, duplicate: bool = False) -> SemanticSnapshot:
    rows = [
        element("select1", role="listbox", tag="select"),
        element(
            "o1",
            role="option",
            tag="option",
            attributes={"value": "Megan"},
            dom_parent="select1",
            visible=False,
        ),
        element(
            "o2",
            role="option",
            tag="option",
            attributes={"value": "Karleen"},
            dom_parent="select1",
            visible=False,
        ),
        element(
            "o3",
            role="option",
            tag="option",
            attributes={"value": "Bonaire, Sint Eustatius and Saba"},
            dom_parent="select1",
            visible=False,
        ),
    ]
    if duplicate:
        rows.extend(
            (
                element("select2", role="listbox", tag="select"),
                element(
                    "o4",
                    role="option",
                    tag="option",
                    attributes={"value": "Megan"},
                    dom_parent="select2",
                    visible=False,
                ),
                element(
                    "o5",
                    role="option",
                    tag="option",
                    attributes={"value": "Karleen"},
                    dom_parent="select2",
                    visible=False,
                ),
            )
        )
    return SemanticSnapshot(tuple(rows))


def test_login_assignments_are_bound_to_public_labels_and_verbatim_spans() -> None:
    goal = (
        'Enter the username "cristin" and the password "Kw" into the text '
        "fields and press login."
    )
    contract = compile_structured_goal(goal, login_snapshot())
    assert contract.allowed
    assert [(row.bid, row.label, row.value) for row in contract.field_assignments] == [
        ("pass", "Password", "Kw"),
        ("user", "Username", "cristin"),
    ]
    assert contract.terminal_intent is not None
    assert contract.terminal_intent.requested_label == "login"
    contract.validate_provenance()
    for row in contract.field_assignments:
        assert goal[row.label_span.start : row.label_span.end] == row.label_span.text
        assert goal[row.value_span.start : row.value_span.end] == row.value


def test_flight_colon_assignments_and_date_are_separate_public_anchors() -> None:
    goal = (
        "Book the shortest one-way flight from: Midland/Odessa, TX "
        "to: Pensacola, FL on 12/05/2016."
    )
    contract = compile_structured_goal(goal, flight_snapshot())
    assert [(row.bid, row.value) for row in contract.field_assignments] == [
        ("from", "Midland/Odessa, TX"),
        ("to", "Pensacola, FL"),
    ]
    assert contract.date_anchor is not None
    assert contract.date_anchor.canonical == "12/05/2016"
    assert contract.date_anchor.span.text == "12/05/2016"
    assert contract.objective_anchor is not None
    assert contract.objective_anchor.kind == "min_duration"
    assert contract.objective_anchor.span.text == "shortest"


def test_offscreen_native_options_resolve_one_or_multiple_exact_values() -> None:
    single = compile_structured_goal(
        "Select Bonaire, Sint Eustatius and Saba from the scroll list and click Submit.",
        scroll_snapshot(),
    )
    assert single.option_selections[0].values == (
        "Bonaire, Sint Eustatius and Saba",
    )

    multiple = compile_structured_goal(
        "Select Megan, Karleen from the scroll list and click Submit.",
        scroll_snapshot(),
    )
    assert multiple.option_selections[0].values == ("Megan", "Karleen")
    assert multiple.exact_constraint is not None
    assert multiple.exact_constraint.exact == "Submit"
    assert multiple.terminal_intent is not None
    assert multiple.terminal_intent.requested_label == "submit"


def test_ambiguous_public_listbox_resolution_fails_closed() -> None:
    contract = compile_structured_goal(
        "Select Megan, Karleen from the scroll list and click Submit.",
        scroll_snapshot(duplicate=True),
    )
    assert contract.option_selections == ()
    assert "multiple public listboxes" in contract.rejected_reasons[0]


def test_explicit_widget_role_is_a_direct_public_role_anchor() -> None:
    goal = 'Click on a "checkbox" widget.'
    contract = compile_structured_goal(goal, SemanticSnapshot(()))
    assert contract.role_anchor is not None
    assert contract.role_anchor.role == "checkbox"
    assert contract.role_anchor.span.text == "checkbox"
    assert contract.exact_constraint is None


def test_invalid_or_ambiguous_dates_are_rejected_as_date_anchors() -> None:
    invalid = compile_structured_goal(
        "Select 02/31/2016 as the date and hit submit.",
        SemanticSnapshot(()),
    )
    assert invalid.date_anchor is None
    assert any("invalid calendar date" in row for row in invalid.rejected_reasons)

    ambiguous = compile_structured_goal(
        "Move 01/01/2016 to 02/02/2016.",
        SemanticSnapshot(()),
    )
    assert ambiguous.date_anchor is None
    assert any("ambiguous dates" in row for row in ambiguous.rejected_reasons)


def test_unrelated_quoted_values_do_not_become_field_assignments() -> None:
    contract = compile_structured_goal(
        'Type "secret" into "Search" and click "Go".',
        login_snapshot(),
    )
    assert contract.field_assignments == ()
    assert contract.role_anchor is None
    assert contract.exact_constraint is not None
    assert contract.exact_constraint.exact == "Go"
