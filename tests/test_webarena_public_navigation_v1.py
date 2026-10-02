from __future__ import annotations

import json
from pathlib import Path

import pytest

from inversereserve.adapters.webarena.webarena_public_navigation_v1 import (
    check_public_navigation_effect_v1,
    compile_public_navigation_v1,
    navigation_attempt_key_v1,
    navigation_messages_v1,
    resolve_public_navigation_v1,
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
    properties: dict[str, object] | None = None,
    visible: bool = True,
    clickable: bool = True,
) -> SemanticElement:
    return SemanticElement(
        bid=bid,
        role=role,
        name=name,
        subtree_text=name,
        ax_properties=tuple(sorted((properties or {}).items())),
        ax_parent_bid=None,
        dom_tag=tag,
        dom_attributes=tuple(sorted((attributes or {}).items())),
        dom_parent_bid=None,
        visible=visible,
        clickable=clickable,
        bbox=(0.0, 0.0, 100.0, 20.0),
    )


def snapshot(*rows: SemanticElement) -> SemanticSnapshot:
    return SemanticSnapshot(tuple(rows))


def public_page() -> SemanticSnapshot:
    return snapshot(
        element(
            "profile",
            role="link",
            name="Edit profile and homepage",
            tag="a",
            attributes={"href": "/-/profile"},
        ),
        element(
            "address",
            role="link",
            name="Change Address",
            tag="a",
            attributes={"href": "/customer/address/edit/1"},
        ),
        element(
            "external",
            role="link",
            name="External help",
            tag="a",
            attributes={"href": "https://evil.example/help"},
        ),
        element("logout", role="link", name="Sign out", tag="a", attributes={"href": "/users/sign_out"}),
        element(
            "menu",
            role="button",
            name="Account menu",
            tag="button",
            attributes={"type": "button", "aria-haspopup": "menu"},
            properties={"hasPopup": True, "expanded": False},
        ),
        element("save", role="button", name="Save changes", tag="button", attributes={"type": "submit"}),
        element(
            "hidden", role="link", name="Profile", tag="a", attributes={"href": "/hidden"}, visible=False
        ),
    )


def test_navigation_inventory_uses_only_same_origin_gets_and_nonterminal_controls() -> None:
    inventory = compile_public_navigation_v1(
        public_page(),
        current_url="http://127.0.0.1:22023/",
        goal="set the homepage URL on my GitLab profile to example.org",
    )
    assert [row.bid for row in inventory.candidates] == ["profile", "address", "menu"]
    profile = inventory.candidates[0]
    assert profile.kind == "same_origin_get_link"
    assert profile.href == "http://127.0.0.1:22023/-/profile"
    assert profile.goal_overlap >= 2
    assert profile.action.operation == "click"
    assert profile.action.bid == "profile"
    assert inventory.record()["uses_task_id"] is False
    assert inventory.record()["uses_site_specific_route"] is False


def test_cross_origin_session_terminal_hidden_and_submit_candidates_are_excluded() -> None:
    inventory = compile_public_navigation_v1(
        public_page(), current_url="http://127.0.0.1:22023/", goal="change my profile"
    )
    observed = {row.bid for row in inventory.candidates}
    assert not observed & {"external", "logout", "save", "hidden"}


def test_public_candidate_bound_is_deterministic_and_reports_omissions() -> None:
    rows = tuple(
        (
            element(
                f"link{index}",
                role="link",
                name=f"Page {index}",
                tag="a",
                attributes={"href": f"/page/{index}"},
            )
            for index in range(5)
        )
    )
    inventory = compile_public_navigation_v1(
        snapshot(*rows), current_url="http://127.0.0.1:20999/", goal="Open Page 3", maximum_candidates=2
    )
    assert inventory.visible_eligible_count == 5
    assert inventory.omitted_count == 3
    assert inventory.candidates[0].bid == "link3"


def test_no_effect_attempt_key_is_quarantined_only_at_same_public_state() -> None:
    before = public_page()
    first = compile_public_navigation_v1(before, current_url="http://127.0.0.1:22023/", goal="edit profile")
    selected = next((row for row in first.candidates if row.bid == "profile"))
    key = navigation_attempt_key_v1(snapshot=before, current_url="http://127.0.0.1:22023/", bid=selected.bid)
    quarantined = compile_public_navigation_v1(
        before, current_url="http://127.0.0.1:22023/", goal="edit profile", quarantined_attempt_keys=(key,)
    )
    assert "profile" not in {row.bid for row in quarantined.candidates}
    changed = snapshot(
        *before.elements, element("new", role="link", name="New page", tag="a", attributes={"href": "/new"})
    )
    changed_inventory = compile_public_navigation_v1(
        changed, current_url="http://127.0.0.1:22023/", goal="edit profile", quarantined_attempt_keys=(key,)
    )
    assert "profile" in {row.bid for row in changed_inventory.candidates}


def test_navigation_prompt_and_strict_resolution_bind_one_current_bid() -> None:
    inventory = compile_public_navigation_v1(
        public_page(), current_url="http://127.0.0.1:22023/", goal="edit my profile"
    )
    messages = navigation_messages_v1(
        goal="edit my profile",
        current_url="http://127.0.0.1:22023/",
        inventory=inventory,
        navigation_history=({"bid": "old"},),
    )
    payload = json.loads(messages[1]["content"])
    assert payload["goal"] == "edit my profile"
    assert {row["bid"] for row in payload["candidates"]} == {"profile", "address", "menu"}
    decision = resolve_public_navigation_v1(
        inventory, model_output='<PACT_NAVIGATION>{"decision":"click","bid":"profile"}</PACT_NAVIGATION>'
    )
    assert decision.allowed is True
    assert decision.candidate is not None
    assert decision.candidate.bid == "profile"
    abstain = resolve_public_navigation_v1(
        inventory, model_output='<PACT_NAVIGATION>{"decision":"abstain","bid":null}</PACT_NAVIGATION>'
    )
    assert abstain.allowed is False
    with pytest.raises(ValueError, match="outside"):
        resolve_public_navigation_v1(
            inventory, model_output='<PACT_NAVIGATION>{"decision":"click","bid":"invented"}</PACT_NAVIGATION>'
        )


@pytest.mark.parametrize(
    "model_output",
    [
        '{"decision":"click","bid":"profile"}',
        "<PACT_NAVIGATION>not json</PACT_NAVIGATION>",
        '<PACT_NAVIGATION>{"decision":"click","bid":"profile","url":"/x"}</PACT_NAVIGATION>',
        '<PACT_NAVIGATION>{"decision":"click","bid":"profile"}</PACT_NAVIGATION><PACT_NAVIGATION>{"decision":"abstain","bid":null}</PACT_NAVIGATION>',
    ],
)
def test_navigation_model_output_fails_closed(model_output: str) -> None:
    inventory = compile_public_navigation_v1(
        public_page(), current_url="http://127.0.0.1:22023/", goal="edit my profile"
    )
    with pytest.raises(ValueError):
        resolve_public_navigation_v1(inventory, model_output=model_output)


def test_navigation_effect_requires_url_or_public_semantic_change() -> None:
    before = public_page()
    inventory = compile_public_navigation_v1(
        before, current_url="http://127.0.0.1:22023/", goal="edit my profile"
    )
    candidate = next((row for row in inventory.candidates if row.bid == "profile"))
    no_effect = check_public_navigation_effect_v1(
        before=before,
        after=before,
        before_url="http://127.0.0.1:22023/",
        after_url="http://127.0.0.1:22023/",
        candidate=candidate,
    )
    assert no_effect.effective is False
    moved = check_public_navigation_effect_v1(
        before=before,
        after=before,
        before_url="http://127.0.0.1:22023/",
        after_url="http://127.0.0.1:22023/-/profile",
        candidate=candidate,
    )
    assert moved.effective is True
    assert moved.url_changed is True
