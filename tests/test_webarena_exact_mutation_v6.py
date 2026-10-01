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
from rcrps.webarena_exact_mutation_v6 import (  # noqa: E402
    certify_exact_mutation_commit_v6,
    compile_exact_mutation_goal_v6,
    compile_exact_mutation_inventory_v6,
)


WIDTH = 1280
HEIGHT = 720
URL_GOAL = "set the homepage URL on my GitLab profile to helloworld.xyz"


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
    attributes: dict[str, str] | None = None,
) -> SemanticElement:
    properties: dict[str, object] = {}
    if value is not None:
        properties.update(
            {"value": value, "readonly": False, "disabled": False}
        )
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
        bbox=(0.0, 0.0, 100.0, 20.0),
    )


def url_form(
    *,
    field_name: str = "Website url",
    input_type: str = "text",
    value: str = "",
    semantic_attributes: bool = True,
) -> SemanticSnapshot:
    return SemanticSnapshot(
        (
            element("page", role="main", tag="main"),
            element(
                "form",
                role="form",
                name="Edit Profile",
                subtree_text=f"{field_name} Update profile settings",
                tag="form",
                parent="page",
            ),
            element("group", parent="form"),
            element(
                "website",
                role="textbox",
                name=field_name,
                tag="input",
                parent="group",
                value=value,
                attributes=(
                    {
                        "id": "user_website_url",
                        "name": "user[website_url]",
                        "type": input_type,
                    }
                    if semantic_attributes
                    else {
                        "id": "profile_note",
                        "name": "profile[note]",
                        "type": input_type,
                    }
                ),
            ),
            element(
                "save",
                role="button",
                name="Update profile settings",
                tag="button",
                parent="form",
                clickable=True,
            ),
        )
    )


def compile_v6(goal: str, snapshot: SemanticSnapshot):
    return compile_exact_mutation_goal_v6(
        goal,
        snapshot,
        viewport_width=WIDTH,
        viewport_height=HEIGHT,
    )


def test_joint_public_url_semantics_canonicalize_text_input() -> None:
    compilation = compile_v6(URL_GOAL, url_form())
    assert compilation.allowed is True
    assert compilation.value_normalization is not None
    assert compilation.value_normalization.applied is False
    normalization = compilation.semantic_url_normalization
    assert normalization is not None
    assert normalization.applied is True
    assert normalization.input_type == "text"
    assert normalization.rule == "joint_goal_field_url_semantics_https"
    assert set(normalization.joint_url_tokens) == {"homepage", "url", "website"}
    binding = compilation.goal_contract.payload_bindings[0]
    assert binding.value == "https://helloworld.xyz"
    assert binding.value_span.text == "helloworld.xyz"


@pytest.mark.parametrize(
    ("goal", "expected_rule"),
    [
        (
            "set the homepage URL on my profile to https://example.com",
            "explicit_uri_scheme",
        ),
        (
            "set the homepage URL on my profile to not_a_hostname",
            "not_a_bare_hostname_url",
        ),
    ],
)
def test_joint_url_semantics_fail_closed(
    goal: str,
    expected_rule: str,
) -> None:
    compilation = compile_v6(goal, url_form())
    assert compilation.allowed is True
    normalization = compilation.semantic_url_normalization
    assert normalization is not None
    assert normalization.applied is False
    assert normalization.rule == expected_rule
    assert compilation.goal_contract.payload_bindings[0].value == (
        compilation.clause.value
    )


def test_missing_joint_semantics_never_canonicalize() -> None:
    no_goal_semantics = compile_v6(
        "set the profile note to helloworld.xyz",
        url_form(),
    )
    no_field_semantics = compile_v6(
        "set the homepage URL on my profile to helloworld.xyz",
        url_form(
            field_name="Profile note",
            semantic_attributes=False,
        ),
    )
    assert no_goal_semantics.allowed is False
    assert no_goal_semantics.semantic_url_normalization is None
    assert no_field_semantics.allowed is False
    assert no_field_semantics.semantic_url_normalization is None


def test_frozen_v5_url_input_decision_is_retained() -> None:
    compilation = compile_v6(URL_GOAL, url_form(input_type="url"))
    assert compilation.value_normalization is not None
    assert compilation.value_normalization.applied is True
    assert compilation.goal_contract.payload_bindings[0].value == (
        "https://helloworld.xyz"
    )
    normalization = compilation.semantic_url_normalization
    assert normalization is not None
    assert normalization.applied is False
    assert normalization.rule == "frozen_v5_typed_url_rule_retained"


def test_text_url_commit_requires_matching_fresh_transaction() -> None:
    before = url_form(value="")
    filled = url_form(value="https://helloworld.xyz")
    initial = compile_v6(URL_GOAL, before)
    initial_inventory = compile_exact_mutation_inventory_v6(
        before,
        URL_GOAL,
        compilation=initial,
        viewport_width=WIDTH,
        viewport_height=HEIGHT,
    )
    contract = initial_inventory.contract_by_bid["website"]
    active = ActiveTransactionV4(
        contract,
        "Website url",
        before,
        filled,
        semantic_delta(before, filled),
    )
    fresh = compile_v6(URL_GOAL, filled)
    inventory = compile_exact_mutation_inventory_v6(
        filled,
        URL_GOAL,
        compilation=fresh,
        viewport_width=WIDTH,
        viewport_height=HEIGHT,
    )
    submit = next(row for row in inventory.candidates if row.bid == "save")
    denied = certify_exact_mutation_commit_v6(
        current=filled,
        compilation=fresh,
        candidate=submit,
        inventory=inventory.candidates,
        active_transactions=(),
    )
    admitted = certify_exact_mutation_commit_v6(
        current=filled,
        compilation=fresh,
        candidate=submit,
        inventory=inventory.candidates,
        active_transactions=(active,),
    )
    assert denied.allowed is False
    assert admitted.allowed is True


def test_v6_semantic_record_is_public_and_source_bound() -> None:
    record = compile_v6(URL_GOAL, url_form()).record()[
        "webarena_exact_mutation_v6"
    ]
    evidence = record["joint_url_semantic_normalization"]
    assert evidence["uses_public_goal_tokens"] is True
    assert evidence["uses_public_accessible_name"] is True
    assert evidence["uses_public_dom_attributes"] is True
    for key in (
        "uses_site_identity",
        "uses_site_specific_selector",
        "uses_site_specific_route",
        "uses_task_id",
        "uses_evaluator",
        "uses_reward",
        "uses_network_log",
        "uses_hidden_state",
    ):
        assert evidence[key] is False
