from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from rcrps.pact_controller_v4 import ActiveTransactionV4  # noqa: E402
from rcrps.typed_observation import (  # noqa: E402
    SemanticElement,
    SemanticSnapshot,
    semantic_delta,
)
from rcrps.webarena_exact_mutation_v2 import (  # noqa: E402
    compile_exact_mutation_goal_v2,
)
from rcrps.webarena_exact_mutation_v3 import (  # noqa: E402
    certify_exact_mutation_commit_v3,
    compile_exact_mutation_goal_v3,
    compile_exact_mutation_inventory_v3,
)


BIO_GOAL = 'Change my bio to "I am a robot" in the discussion forum'
PAGE_GOAL = 'Change the page title of "Home Page" page on my site to "New".'


def element(
    bid: str,
    *,
    role: str = "generic",
    name: str = "",
    tag: str = "div",
    parent: str | None = None,
    value: str | None = None,
    clickable: bool = False,
    attributes: dict[str, str] | None = None,
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
        dom_attributes=tuple(sorted((attributes or {}).items())),
        dom_parent_bid=parent,
        visible=True,
        clickable=clickable,
        bbox=(0.0, 0.0, 100.0, 20.0),
    )


def test_non_text_input_does_not_compete_with_public_text_field() -> None:
    current = SemanticSnapshot(
        (
            element("page", tag="main"),
            element("form", role="form", name="Biography", tag="form", parent="page"),
            element(
                "bio",
                role="textbox",
                name="Biography",
                tag="textarea",
                parent="form",
                value="old",
            ),
            element(
                "help",
                role="checkbox",
                name="Biography markdown help",
                tag="input",
                parent="form",
                clickable=True,
                attributes={"type": "checkbox"},
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
    assert compile_exact_mutation_goal_v2(BIO_GOAL, current).allowed is False
    compilation = compile_exact_mutation_goal_v3(BIO_GOAL, current)
    assert compilation.allowed is True
    assert compilation.goal_contract.payload_bindings[0].bid == "bio"
    assert compilation.projection.non_text_input_bids == ("help",)
    assert compilation.surface.kind == "dom_form"


def inline_editor(value: str) -> SemanticSnapshot:
    return SemanticSnapshot(
        (
            element("page", tag="main"),
            element("surface", tag="section", parent="page"),
            element(
                "title",
                role="textbox",
                name="Page Title",
                tag="input",
                parent="surface",
                value=value,
            ),
            element(
                "save",
                role="button",
                name="Save",
                tag="button",
                parent="surface",
                clickable=True,
            ),
            element(
                "back",
                role="button",
                name="Back",
                tag="button",
                parent="surface",
                clickable=True,
            ),
        )
    )


def test_back_is_a_public_neutralization_witness_with_real_freshness_key() -> None:
    before = inline_editor("Home Page")
    filled = inline_editor("New")
    assert compile_exact_mutation_goal_v2(PAGE_GOAL, before).allowed is False
    initial = compile_exact_mutation_goal_v3(PAGE_GOAL, before)
    assert initial.allowed is True
    assert initial.projection.back_neutralization_bids == ("back",)
    initial_inventory = compile_exact_mutation_inventory_v3(
        before, PAGE_GOAL, compilation=initial
    )
    contract = initial_inventory.contract_by_bid["title"]
    active = ActiveTransactionV4(
        contract,
        "Page Title",
        before,
        filled,
        semantic_delta(before, filled),
    )
    fresh = compile_exact_mutation_goal_v3(PAGE_GOAL, filled)
    inventory = compile_exact_mutation_inventory_v3(
        filled, PAGE_GOAL, compilation=fresh
    )
    submit = next(row for row in inventory.candidates if row.bid == "save")
    certificate = certify_exact_mutation_commit_v3(
        current=filled,
        compilation=fresh,
        candidate=submit,
        inventory=inventory.candidates,
        active_transactions=(active,),
    )
    assert certificate.allowed is True
    assert certificate.observation_fingerprint == filled.semantic_fingerprint()

