from __future__ import annotations

from pathlib import Path

import pytest

from inversereserve.adapters.webarena.webarena_exact_mutation_v4 import compile_exact_mutation_goal_v4
from inversereserve.adapters.webarena.webarena_exact_mutation_v5 import (
    certify_exact_mutation_commit_v5,
    compile_exact_mutation_goal_v5,
    compile_exact_mutation_inventory_v5,
)
from inversereserve.controllers.pact_controller_v4 import ActiveTransactionV4
from inversereserve.observations.typed_observation import SemanticElement, SemanticSnapshot, semantic_delta

ROOT = Path(__file__).resolve().parents[1]
WIDTH = 1280
HEIGHT = 720
URL_GOAL = "set the homepage URL on my GitLab profile to helloworld.xyz"
PAGE_GOAL = 'Change the page title of "Home Page" page on my site to "This is the home page!! Leave here!!".'


def element(
    bid: str,
    *,
    role: str = "generic",
    name: str = "",
    subtree_text: str | None = None,
    tag: str = "div",
    parent: str | None = None,
    value: str | None = None,
    clickable: bool = False,
    bbox: tuple[float, float, float, float] | None = (0.0, 0.0, 100.0, 20.0),
    attributes: dict[str, str] | None = None,
) -> SemanticElement:
    properties: dict[str, object] = {}
    if value is not None:
        properties.update({"value": value, "readonly": False, "disabled": False})
    return SemanticElement(
        bid=bid,
        role=role,
        name=name,
        subtree_text=name if subtree_text is None else subtree_text,
        ax_properties=tuple(sorted(properties.items())),
        ax_parent_bid=parent,
        dom_tag=tag,
        dom_attributes=tuple(sorted((attributes or {}).items())),
        dom_parent_bid=parent,
        visible=True,
        clickable=clickable,
        bbox=bbox,
    )


def url_form(*, input_type: str = "url", value: str = "") -> SemanticSnapshot:
    return SemanticSnapshot(
        (
            element("page", role="main", tag="main", bbox=(0.0, 0.0, 1280.0, 720.0)),
            element(
                "form",
                role="form",
                name="Edit Profile",
                subtree_text="Website url Update profile settings",
                tag="form",
                parent="page",
                bbox=(100.0, 100.0, 900.0, 500.0),
            ),
            element("group", parent="form"),
            element(
                "website",
                role="textbox",
                name="Website url",
                tag="input",
                parent="group",
                value=value,
                bbox=(200.0, 200.0, 500.0, 30.0),
                attributes={"id": "user_website_url", "name": "user[website_url]", "type": input_type},
            ),
            element(
                "save",
                role="button",
                name="Update profile settings",
                tag="button",
                parent="form",
                clickable=True,
                bbox=(700.0, 500.0, 200.0, 40.0),
            ),
        )
    )


def deep_editor(
    *,
    value: str = "Home Page",
    include_back: bool = True,
    duplicate_save: bool = False,
    surface_bbox: tuple[float, float, float, float] = (88.0, 141.59375, 1177.0, 621.765625),
    target_bbox: tuple[float, float, float, float] | None = (404.75, 356.34375, 543.5, 33.03125),
) -> SemanticSnapshot:
    rows = [
        element("html", tag="html", bbox=(0.0, 0.0, 1280.0, 900.0)),
        element("body", tag="body", parent="html", bbox=(0.0, 0.0, 1265.0, 900.0)),
        element("main", role="main", tag="main", parent="body", bbox=surface_bbox),
        element("toolbar", parent="main"),
        element(
            "back",
            role="button",
            name="\ue626 Back",
            tag="button",
            parent="toolbar",
            clickable=True,
            bbox=(100.0, 157.0, 90.0, 45.0),
        ),
        element(
            "savewrapper",
            name="Save",
            subtree_text="Save Save options",
            parent="toolbar",
            clickable=True,
            bbox=(1087.0, 157.0, 133.0, 45.0),
        ),
        element(
            "save",
            role="button",
            name="Save",
            tag="button",
            parent="savewrapper",
            clickable=True,
            bbox=(1087.0, 157.0, 93.0, 45.0),
        ),
        element(
            "saveoptions",
            role="button",
            name="Save options",
            tag="button",
            parent="savewrapper",
            clickable=True,
            bbox=(1178.0, 157.0, 42.0, 45.0),
        ),
    ]
    parent = "main"
    for index in range(9):
        bid = f"layer{index}"
        rows.append(element(bid, parent=parent, bbox=surface_bbox))
        parent = bid
    rows.append(
        element(
            "title",
            role="textbox",
            name="Page Title *",
            subtree_text=f"Page Title * {value}",
            tag="input",
            parent=parent,
            value=value,
            bbox=target_bbox,
            attributes={"type": "text"},
        )
    )
    if not include_back:
        rows = [row for row in rows if row.bid != "back"]
    if duplicate_save:
        rows.append(
            element(
                "secondsave",
                role="button",
                name="Save",
                tag="button",
                parent="toolbar",
                clickable=True,
                bbox=(950.0, 157.0, 90.0, 45.0),
            )
        )
    return SemanticSnapshot(tuple(rows))


def compile_v5(goal: str, snapshot: SemanticSnapshot):
    return compile_exact_mutation_goal_v5(goal, snapshot, viewport_width=WIDTH, viewport_height=HEIGHT)


def test_url_input_canonicalizes_only_one_bare_hostname() -> None:
    compilation = compile_v5(URL_GOAL, url_form())
    assert compilation.allowed is True
    binding = compilation.goal_contract.payload_bindings[0]
    assert binding.value == "https://helloworld.xyz"
    assert binding.value_span.text == "helloworld.xyz"
    assert compilation.value_normalization is not None
    assert compilation.value_normalization.applied is True
    assert compilation.value_normalization.input_type == "url"
    assert compilation.value_normalization.rule == "url_input_bare_hostname_https"


@pytest.mark.parametrize(
    ("goal", "input_type", "expected_rule"),
    [
        ("set the homepage URL on my GitLab profile to https://example.com", "url", "explicit_uri_scheme"),
        (URL_GOAL, "text", "non_url_input"),
        ("set the homepage URL on my GitLab profile to not_a_hostname", "url", "not_a_bare_hostname_url"),
    ],
)
def test_url_normalization_is_fail_closed(goal: str, input_type: str, expected_rule: str) -> None:
    compilation = compile_v5(goal, url_form(input_type=input_type))
    assert compilation.allowed is True
    assert compilation.value_normalization is not None
    assert compilation.value_normalization.applied is False
    assert compilation.value_normalization.rule == expected_rule
    assert compilation.goal_contract.payload_bindings[0].value == compilation.clause.value


def test_deep_editor_binds_one_canonical_save_and_icon_back() -> None:
    snapshot = deep_editor()
    assert compile_exact_mutation_goal_v4(PAGE_GOAL, snapshot).allowed is False
    compilation = compile_v5(PAGE_GOAL, snapshot)
    assert compilation.allowed is True
    assert compilation.viewport_surface is not None
    surface = compilation.viewport_surface
    assert surface.surface_bid == "main"
    assert surface.submit_bid == "save"
    assert surface.target_depth > 6
    assert surface.neutral_bids == ("back",)
    assert surface.commit_representation_bids == ("save", "savewrapper")
    assert surface.ignored_save_option_bids == ("saveoptions",)
    assert compilation.projection.token_back_neutralization_bids == ("back",)
    assert compilation.goal_contract.payload_bindings[0].bid == "title"


@pytest.mark.parametrize(
    "snapshot",
    [
        deep_editor(include_back=False),
        deep_editor(duplicate_save=True),
        deep_editor(target_bbox=None),
        deep_editor(surface_bbox=(0.0, 0.0, 3000.0, 3000.0)),
    ],
)
def test_viewport_editor_fails_closed_on_missing_or_ambiguous_evidence(snapshot: SemanticSnapshot) -> None:
    compilation = compile_v5(PAGE_GOAL, snapshot)
    assert compilation.allowed is False
    assert compilation.viewport_surface is None


def test_viewport_editor_commit_requires_fresh_active_exact_transaction() -> None:
    before = deep_editor(value="Home Page")
    filled = deep_editor(value="This is the home page!! Leave here!!")
    before_compilation = compile_v5(PAGE_GOAL, before)
    before_inventory = compile_exact_mutation_inventory_v5(
        before, PAGE_GOAL, compilation=before_compilation, viewport_width=WIDTH, viewport_height=HEIGHT
    )
    contract = before_inventory.contract_by_bid["title"]
    active = ActiveTransactionV4(contract, "Page Title *", before, filled, semantic_delta(before, filled))
    fresh = compile_v5(PAGE_GOAL, filled)
    inventory = compile_exact_mutation_inventory_v5(
        filled, PAGE_GOAL, compilation=fresh, viewport_width=WIDTH, viewport_height=HEIGHT
    )
    submit = next((row for row in inventory.candidates if row.bid == "save"))
    denied = certify_exact_mutation_commit_v5(
        current=filled,
        compilation=fresh,
        candidate=submit,
        inventory=inventory.candidates,
        active_transactions=(),
    )
    assert denied.allowed is False
    admitted = certify_exact_mutation_commit_v5(
        current=filled,
        compilation=fresh,
        candidate=submit,
        inventory=inventory.candidates,
        active_transactions=(active,),
    )
    assert admitted.allowed is True
    assert admitted.grounding.anchor_kind == "exact_mutation_public_viewport_editor_surface_action"


def test_v5_record_excludes_forbidden_sources() -> None:
    record = compile_v5(PAGE_GOAL, deep_editor()).record()["webarena_exact_mutation_v5"]
    for evidence in (
        record["projection"],
        record["typed_value_normalization"],
        record["viewport_surface_binding"],
    ):
        assert evidence["uses_site_identity"] is False
        assert evidence["uses_site_specific_selector"] is False
        assert evidence["uses_site_specific_route"] is False
        assert evidence["uses_task_id"] is False
        assert evidence["uses_evaluator"] is False
        assert evidence["uses_reward"] is False
        assert evidence["uses_network_log"] is False
        assert evidence["uses_hidden_state"] is False
