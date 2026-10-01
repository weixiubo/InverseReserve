from __future__ import annotations

import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from rcrps.pact_controller_v4 import ActiveTransactionV4  # noqa: E402
from rcrps.typed_observation import (  # noqa: E402
    SemanticElement,
    SemanticSnapshot,
    semantic_delta,
)
from rcrps.webarena_exact_mutation_v2 import (  # noqa: E402
    certify_exact_mutation_commit_v2,
    compile_exact_mutation_goal_v2,
    compile_exact_mutation_inventory_v2,
)


GOAL = 'Change the page title of "Home" page on my site to "Welcome".'


def element(
    bid: str,
    *,
    role: str = "generic",
    name: str = "",
    tag: str = "div",
    parent: str | None = None,
    value: str | None = None,
    clickable: bool = False,
) -> SemanticElement:
    properties: dict[str, object] = {}
    if value is not None:
        properties.update({"value": value, "readonly": False, "disabled": False})
    return SemanticElement(
        bid=bid,
        role=role,
        name=name,
        subtree_text=name,
        ax_properties=tuple(sorted(properties.items())),
        ax_parent_bid=parent,
        dom_tag=tag,
        dom_attributes=(),
        dom_parent_bid=parent,
        visible=True,
        clickable=clickable,
        bbox=(0.0, 0.0, 100.0, 20.0),
    )


def inline_editor(
    *,
    value: str = "Home Page",
    include_cancel: bool = True,
    second_save: bool = False,
) -> SemanticSnapshot:
    rows = [
        element("page", tag="main"),
        element("table", role="table", tag="table", parent="page"),
        element("body", role="rowgroup", tag="tbody", parent="table"),
        element("row", role="row", tag="tr", parent="body"),
        element(
            "title",
            role="textbox",
            name="Page Title",
            tag="input",
            parent="row",
            value=value,
        ),
        element(
            "save",
            role="button",
            name="Save",
            tag="button",
            parent="row",
            clickable=True,
        ),
    ]
    if include_cancel:
        rows.append(
            element(
                "cancel",
                role="button",
                name="Cancel",
                tag="button",
                parent="row",
                clickable=True,
            )
        )
    if second_save:
        rows.append(
            element(
                "update",
                role="button",
                name="Update",
                tag="button",
                parent="row",
                clickable=True,
            )
        )
    return SemanticSnapshot(tuple(rows))


def test_formless_surface_binds_one_field_save_and_cancel_witness() -> None:
    current = inline_editor()
    compilation = compile_exact_mutation_goal_v2(GOAL, current)
    assert compilation.allowed is True
    assert compilation.surface is not None
    assert compilation.surface.kind == "public_edit_surface"
    assert compilation.surface.surface_bid == "row"
    assert compilation.surface.submit_bid == "save"
    assert compilation.surface.cancel_bids == ("cancel",)
    assert compilation.goal_contract.assignment_for_bid("title").value == "Welcome"
    assignments = [
        row
        for row in compilation.goal_contract.field_assignments
        if str(row.bid) == "title"
    ]
    assert len(assignments) == 1


def test_literal_dom_form_keeps_the_frozen_v1_binding_path() -> None:
    current = SemanticSnapshot(
        (
            element("page", tag="main"),
            element("form", role="form", name="Settings", tag="form", parent="page"),
            element(
                "title",
                role="textbox",
                name="Page Title",
                tag="input",
                parent="form",
                value="Home Page",
            ),
            element(
                "save",
                role="button",
                name="Save",
                tag="button",
                parent="form",
                clickable=True,
            ),
        )
    )
    compilation = compile_exact_mutation_goal_v2(GOAL, current)
    assert compilation.allowed is True
    assert compilation.surface is not None
    assert compilation.surface.kind == "dom_form"


@pytest.mark.parametrize(
    "snapshot",
    [inline_editor(include_cancel=False), inline_editor(second_save=True)],
)
def test_formless_surface_fails_closed_without_unique_save_and_cancel(
    snapshot: SemanticSnapshot,
) -> None:
    compilation = compile_exact_mutation_goal_v2(GOAL, snapshot)
    assert compilation.allowed is False
    assert compilation.goal_contract.payload_bindings == ()


def test_formless_surface_commit_requires_active_exact_value_transaction() -> None:
    before = inline_editor(value="Home Page")
    filled = inline_editor(value="Welcome")
    before_compilation = compile_exact_mutation_goal_v2(GOAL, before)
    before_inventory = compile_exact_mutation_inventory_v2(
        before,
        GOAL,
        compilation=before_compilation,
    )
    contract = before_inventory.contract_by_bid["title"]
    active = ActiveTransactionV4(
        contract,
        "Page Title",
        before,
        filled,
        semantic_delta(before, filled),
    )
    fresh = compile_exact_mutation_goal_v2(GOAL, filled)
    inventory = compile_exact_mutation_inventory_v2(
        filled,
        GOAL,
        compilation=fresh,
    )
    submit = next(row for row in inventory.candidates if row.bid == "save")
    denied = certify_exact_mutation_commit_v2(
        current=filled,
        compilation=fresh,
        candidate=submit,
        inventory=inventory.candidates,
        active_transactions=(),
    )
    assert denied.allowed is False
    admitted = certify_exact_mutation_commit_v2(
        current=filled,
        compilation=fresh,
        candidate=submit,
        inventory=inventory.candidates,
        active_transactions=(active,),
    )
    assert admitted.allowed is True
    assert admitted.grounding.anchor_kind == (
        "exact_mutation_public_edit_surface_action"
    )
