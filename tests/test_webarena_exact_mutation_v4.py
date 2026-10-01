from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from rcrps.typed_observation import SemanticElement, SemanticSnapshot  # noqa: E402
from rcrps.webarena_exact_mutation_v3 import (  # noqa: E402
    compile_exact_mutation_goal_v3,
)
from rcrps.webarena_exact_mutation_v4 import (  # noqa: E402
    compile_exact_mutation_goal_v4,
)


GOAL = 'Change the homepage on my GitLab profile to "https://example.com".'


def element(
    bid: str,
    *,
    role: str = "generic",
    name: str = "",
    subtree_text: str | None = None,
    tag: str = "div",
    ax_parent: str | None = None,
    dom_parent: str | None = None,
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
        subtree_text=name if subtree_text is None else subtree_text,
        ax_properties=tuple(sorted(properties.items())),
        ax_parent_bid=ax_parent,
        dom_tag=tag,
        dom_attributes=tuple(sorted((attributes or {}).items())),
        dom_parent_bid=dom_parent,
        visible=True,
        clickable=clickable,
        bbox=(0.0, 0.0, 100.0, 20.0),
    )


def broad_accessibility_form() -> SemanticSnapshot:
    return SemanticSnapshot(
        (
            element("page", tag="main"),
            element(
                "form",
                role="form",
                name="Edit Profile",
                subtree_text="Name Twitter Website url Location Update profile settings",
                tag="form",
                ax_parent="page",
                dom_parent="page",
            ),
            element("website_group", tag="div", ax_parent="form", dom_parent="form"),
            element("location_group", tag="div", ax_parent="form", dom_parent="form"),
            element(
                "website",
                role="textbox",
                name="Website url",
                tag="input",
                ax_parent="form",
                dom_parent="website_group",
                value="",
                attributes={
                    "id": "user_website_url",
                    "name": "user[website_url]",
                    "placeholder": "https://website.com",
                    "type": "text",
                },
            ),
            element(
                "location",
                role="textbox",
                name="Location",
                tag="input",
                ax_parent="form",
                dom_parent="location_group",
                value="Boston, MA",
                attributes={
                    "id": "user_location",
                    "name": "user[location]",
                    "placeholder": "City, country",
                    "type": "text",
                },
            ),
            element(
                "save",
                role="button",
                name="Update profile settings",
                tag="button",
                ax_parent="form",
                dom_parent="form",
                clickable=True,
                attributes={"type": "submit"},
            ),
        )
    )


def test_scoped_labels_recover_standard_multifield_form() -> None:
    snapshot = broad_accessibility_form()
    assert compile_exact_mutation_goal_v3(GOAL, snapshot).allowed is False

    compilation = compile_exact_mutation_goal_v4(GOAL, snapshot)
    assert compilation.allowed is True
    assert compilation.goal_contract.payload_bindings[0].bid == "website"
    assert compilation.goal_contract.payload_bindings[0].submit_bid == "save"
    assert compilation.surface.kind == "dom_form"
    assert compilation.scoped_binding is not None
    assert compilation.scoped_binding.direct_match_bids == ("website",)
    assert compilation.scoped_binding.winning_bid == "website"
    assert compilation.scoped_binding.resolution_tier == "direct_public_label"


def test_scoped_binding_record_has_no_forbidden_source() -> None:
    record = compile_exact_mutation_goal_v4(
        GOAL, broad_accessibility_form()
    ).record()["webarena_exact_mutation_v4"]["scoped_binding"]
    assert record["uses_site_identity"] is False
    assert record["uses_site_specific_selector"] is False
    assert record["uses_site_specific_route"] is False
    assert record["uses_task_id"] is False
    assert record["uses_evaluator"] is False
    assert record["uses_network_log"] is False
