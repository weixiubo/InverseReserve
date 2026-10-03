from __future__ import annotations

import json
from pathlib import Path

import pytest

from inversereserve.adapters.webarena.webarena_public_navigation_v2 import (
    check_public_navigation_effect_v2,
    compile_public_navigation_v2,
    navigation_attempt_key_v2,
    navigation_messages_v2,
    resolve_public_navigation_v2,
)
from inversereserve.observations.typed_observation import SemanticElement, SemanticSnapshot

ROOT = Path(__file__).resolve().parents[1]


def element(
    bid: str,
    *,
    role: str,
    name: str,
    tag: str,
    attributes: dict[str, str] | None = None,
    parent: str | None = None,
    visible: bool = True,
    clickable: bool = True,
) -> SemanticElement:
    return SemanticElement(
        bid=bid,
        role=role,
        name=name,
        subtree_text=name,
        ax_properties=(),
        ax_parent_bid=parent,
        dom_tag=tag,
        dom_attributes=tuple(sorted((attributes or {}).items())),
        dom_parent_bid=parent,
        visible=visible,
        clickable=clickable,
        bbox=(0.0, 0.0, 100.0, 20.0),
    )


def snapshot(*rows: SemanticElement) -> SemanticSnapshot:
    return SemanticSnapshot(tuple(rows))


def public_page() -> SemanticSnapshot:
    return snapshot(
        element("header", role="banner", name="Account and navigation", tag="header", clickable=False),
        element("avatar", role="button", name="Byte Blaze", tag="button", parent="header"),
        element("profile", role="link", name="Edit profile", tag="a", attributes={"href": "/-/profile"}),
        element("jsmenu", role="link", name="Content", tag="a", attributes={"href": "#"}),
        element("numeric", role="link", name="0", tag="a", attributes={"href": "/project/-/issues"}),
        element("duplicate", role="link", name="Issues", tag="a", attributes={"href": "/project/-/issues"}),
        element("save", role="button", name="Save changes", tag="button", attributes={"type": "submit"}),
        element("delete", role="button", name="Delete account", tag="button"),
        element("field", role="textbox", name="Homepage URL", tag="input"),
        element("external", role="link", name="Help", tag="a", attributes={"href": "https://example.org"}),
    )


def test_v2_exposes_labelled_account_and_javascript_navigation_controls() -> None:
    inventory = compile_public_navigation_v2(
        public_page(), current_url="http://127.0.0.1:8023/", goal="set the homepage URL on my profile"
    )
    observed = {row.bid for row in inventory.candidates}
    assert {"avatar", "profile", "jsmenu", "duplicate"} <= observed
    assert not observed & {"numeric", "save", "delete", "field", "external"}
    avatar = next((row for row in inventory.candidates if row.bid == "avatar"))
    assert "Account and navigation" in avatar.context
    assert avatar.generic_navigation_overlap >= 1
    assert inventory.duplicate_href_count == 1
    assert inventory.record()["uses_site_specific_route"] is False


def test_control_quota_preserves_menus_on_link_dense_pages() -> None:
    rows = [
        element(
            f"link-{index}", role="link", name=str(index), tag="a", attributes={"href": f"/project/{index}"}
        )
        for index in range(90)
    ]
    rows.append(element("user-menu", role="button", name="User menu", tag="button"))
    inventory = compile_public_navigation_v2(
        snapshot(*rows), current_url="http://127.0.0.1:8023/", goal="edit my profile", maximum_candidates=64
    )
    assert "user-menu" in {row.bid for row in inventory.candidates}
    assert inventory.omitted_count == 27


def test_prompt_and_resolution_bind_one_current_bid() -> None:
    inventory = compile_public_navigation_v2(
        public_page(), current_url="http://127.0.0.1:8023/", goal="edit my profile"
    )
    messages = navigation_messages_v2(
        goal="edit my profile", current_url="http://127.0.0.1:8023/", inventory=inventory
    )
    payload = json.loads(messages[1]["content"])
    assert payload["goal"] == "edit my profile"
    decision = resolve_public_navigation_v2(
        inventory,
        model_output='<INVERSE_NAVIGATION>{"decision":"click","bid":"profile"}</INVERSE_NAVIGATION>',
    )
    assert decision.allowed is True
    with pytest.raises(ValueError, match="outside"):
        resolve_public_navigation_v2(
            inventory,
            model_output='<INVERSE_NAVIGATION>{"decision":"click","bid":"invented"}</INVERSE_NAVIGATION>',
        )


def test_no_effect_attempt_is_quarantined_at_the_same_public_state() -> None:
    before = public_page()
    first = compile_public_navigation_v2(before, current_url="http://127.0.0.1:8023/", goal="edit my profile")
    profile = next((row for row in first.candidates if row.bid == "profile"))
    key = navigation_attempt_key_v2(snapshot=before, current_url="http://127.0.0.1:8023/", bid=profile.bid)
    second = compile_public_navigation_v2(
        before, current_url="http://127.0.0.1:8023/", goal="edit my profile", quarantined_attempt_keys=(key,)
    )
    assert "profile" not in {row.bid for row in second.candidates}
    effect = check_public_navigation_effect_v2(
        before=before,
        after=before,
        before_url="http://127.0.0.1:8023/",
        after_url="http://127.0.0.1:8023/",
        candidate=profile,
    )
    assert effect.effective is False
