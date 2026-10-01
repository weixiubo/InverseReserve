from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from rcrps.confirmation_agents_v9 import FullPactConfirmationDriverV9  # noqa: E402
from rcrps.transaction_actions_v4 import ContractActionV4  # noqa: E402
from rcrps.typed_contracts_v4 import TransactionContractV4  # noqa: E402
from rcrps.typed_contracts_v8 import check_transaction_postcondition_v8  # noqa: E402
from rcrps.typed_contracts_v9 import (  # noqa: E402
    check_transaction_postcondition_v9,
    query_aligned_added_suggestion_rows_v9,
)
from rcrps.typed_observation import (  # noqa: E402
    SemanticElement,
    SemanticSnapshot,
    semantic_delta,
)


def element(
    bid: str,
    *,
    role: str = "generic",
    name: str = "",
    text: str = "",
    tag: str = "div",
    attributes: dict[str, str] | None = None,
    properties: dict[str, object] | None = None,
    dom_parent: str | None = None,
    ax_parent: str | None = None,
    visible: bool = True,
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
        clickable=role in {"option", "menuitem"},
        bbox=(0.0, 0.0, 80.0, 20.0),
    )


def field(value: str, *, ax_value: str = "") -> SemanticElement:
    return element(
        "17",
        role="textbox",
        name="Tags:",
        tag="input",
        attributes={"class": "ui-autocomplete-input", "value": value},
        properties={"readonly": False, "value": ax_value},
        dom_parent="body",
    )


def contract(expected: str = "Ma") -> TransactionContractV4:
    return TransactionContractV4(
        kind="autocomplete_query",
        semantic_bid="17",
        action=ContractActionV4("fill", "17", expected, True),
        inverse_actions=(
            ContractActionV4("press", "17", "Escape"),
            ContractActionV4("fill", "17", "", False),
        ),
        expected_value=expected,
        prior_value="",
        projection_kind="autocomplete_query",
    )


def before_with_existing_surface() -> SemanticSnapshot:
    return SemanticSnapshot(
        (
            element("body"),
            field(""),
            element(
                "20",
                role="list",
                tag="ul",
                attributes={"class": "ui-autocomplete"},
                dom_parent="body",
            ),
        )
    )


def populated_after(
    *, field_value: str = "Ma", suggestions: tuple[str, ...] = ("Macao", "Maldives")
) -> SemanticSnapshot:
    rows = tuple(
        element(
            str(21 + index),
            role="option",
            name=value,
            tag="li",
            dom_parent="20",
            ax_parent="20",
        )
        for index, value in enumerate(suggestions)
    )
    return SemanticSnapshot(
        (
            element("body"),
            field(field_value),
            element(
                "20",
                role="list",
                tag="ul",
                attributes={"class": "ui-autocomplete"},
                dom_parent="body",
            ),
            *rows,
        )
    )


def test_v9_accepts_query_aligned_population_of_existing_public_surface() -> None:
    before = before_with_existing_surface()
    after = populated_after()
    frozen = check_transaction_postcondition_v8(before, after, contract())
    assert not frozen.passed
    repaired = check_transaction_postcondition_v9(before, after, contract())
    assert repaired.passed
    assert "newly populated suggestion rows" in repaired.reason
    assert repaired.delta.changed_visible_bids == ("17",)
    assert repaired.delta.added_visible_bids == ("21", "22")
    assert query_aligned_added_suggestion_rows_v9(
        after, semantic_delta(before, after), "Ma"
    ) == ("Macao", "Maldives")


def test_v9_rejects_population_when_target_field_did_not_change() -> None:
    before = before_with_existing_surface()
    after = populated_after(field_value="")
    assert not check_transaction_postcondition_v9(before, after, contract()).passed


def test_v9_rejects_unrelated_text_even_under_suggestion_owner() -> None:
    before = before_with_existing_surface()
    after = populated_after(suggestions=("Zurich", "Oslo"))
    assert not check_transaction_postcondition_v9(before, after, contract()).passed


def test_v9_rejects_query_aligned_text_outside_suggestion_structure() -> None:
    before = before_with_existing_surface()
    after = SemanticSnapshot(
        (
            element("body"),
            field("Ma"),
            before.get("20"),
            element("30", name="Maldives", text="Maldives", dom_parent="body"),
        )
    )
    delta = semantic_delta(before, after)
    assert delta.newly_visible_text == ("Maldives",)
    assert query_aligned_added_suggestion_rows_v9(after, delta, "Ma") == ()
    assert not check_transaction_postcondition_v9(before, after, contract()).passed


def test_v9_driver_replaces_only_the_typed_runtime() -> None:
    assert FullPactConfirmationDriverV9.method_id == "full_pact_v9"
    assert FullPactConfirmationDriverV9.__mro__[1].__name__ == (
        "FullPactConfirmationDriverV8"
    )
