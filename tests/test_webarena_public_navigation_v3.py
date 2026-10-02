from __future__ import annotations

from pathlib import Path

from inversereserve.adapters.webarena.webarena_public_navigation_v3 import (
    check_public_navigation_effect_v3,
    compile_public_navigation_v3,
    detect_public_recovery_signal_v3,
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
    clickable: bool = False,
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
        visible=True,
        clickable=clickable,
        bbox=(0.0, 0.0, 100.0, 20.0),
    )


def page(*rows: SemanticElement) -> SemanticSnapshot:
    return SemanticSnapshot(tuple(rows))


def test_standard_public_button_is_eligible_without_optional_click_marker() -> None:
    current = page(
        element(
            "account",
            role="button",
            name="MarvelsGrantMan136",
            tag="button",
            attributes={"aria-haspopup": "true", "aria-expanded": "false"},
            clickable=False,
        ),
        element(
            "disabled",
            role="button",
            name="Account settings",
            tag="button",
            attributes={"disabled": ""},
            clickable=False,
        ),
        element("form", role="form", name="Profile form", tag="form", clickable=False),
        element(
            "implicit-submit", role="button", name="Continue", tag="button", parent="form", clickable=False
        ),
        element(
            "associated-submit",
            role="button",
            name="Continue",
            tag="button",
            attributes={"form": "profile-form"},
            clickable=False,
        ),
        element(
            "save", role="button", name="Save", tag="button", attributes={"type": "submit"}, clickable=False
        ),
    )
    inventory = compile_public_navigation_v3(
        current, current_url="http://reddit.local/", goal="change my bio"
    )
    assert {row.bid for row in inventory.candidates} == {"account"}
    account = inventory.candidates[0]
    assert account.disclosure_score == 2
    assert inventory.standard_controls_without_action_marker == 5


def test_state_action_attempts_require_public_recovery_for_second_try() -> None:
    current = page(
        element("home", role="link", name="Home", tag="a", attributes={"href": "/"}, clickable=True)
    )
    first = compile_public_navigation_v3(
        current, current_url="http://gitlab.local/error", goal="edit my profile"
    )
    candidate = first.candidates[0]
    counts = {candidate.state_action_key: 1}
    exhausted = compile_public_navigation_v3(
        current, current_url="http://gitlab.local/error", goal="edit my profile", attempt_counts=counts
    )
    assert exhausted.candidates == ()
    retry = compile_public_navigation_v3(
        current,
        current_url="http://gitlab.local/error",
        goal="edit my profile",
        attempt_counts=counts,
        retry_authorized=True,
    )
    assert len(retry.candidates) == 1
    assert retry.candidates[0].attempt_ordinal == 2
    assert retry.candidates[0].retry_authorized is True
    twice = {candidate.state_action_key: 2}
    assert not compile_public_navigation_v3(
        current,
        current_url="http://gitlab.local/error",
        goal="edit my profile",
        attempt_counts=twice,
        retry_authorized=True,
    ).candidates


def test_public_502_text_enables_recovery_without_status_or_network_inputs() -> None:
    current = page(
        element(
            "message",
            role="heading",
            name="GitLab is not responding (502). Try refreshing or going back.",
            tag="h1",
        )
    )
    signal = detect_public_recovery_signal_v3(current)
    assert signal.detected is True
    assert set(signal.matched_public_patterns) == {"bad_gateway", "not_responding", "retry_guidance"}
    assert signal.record()["uses_status_code"] is False
    assert signal.record()["uses_network_log"] is False


def test_navigation_attempt_keys_are_unique_while_state_action_key_is_stable() -> None:
    before = page(
        element(
            "profile", role="link", name="Profile", tag="a", attributes={"href": "/profile"}, clickable=True
        )
    )
    first_inventory = compile_public_navigation_v3(
        before, current_url="http://example.local/", goal="edit profile"
    )
    first = first_inventory.candidates[0]
    second_inventory = compile_public_navigation_v3(
        before,
        current_url="http://example.local/",
        goal="edit profile",
        attempt_counts={first.state_action_key: 1},
        retry_authorized=True,
    )
    second = second_inventory.candidates[0]
    first_effect = check_public_navigation_effect_v3(
        before=before,
        after=before,
        before_url="http://example.local/",
        after_url="http://example.local/",
        candidate=first,
    )
    second_effect = check_public_navigation_effect_v3(
        before=before,
        after=before,
        before_url="http://example.local/",
        after_url="http://example.local/",
        candidate=second,
    )
    assert first_effect.state_action_key == second_effect.state_action_key
    assert first_effect.attempt_key != second_effect.attempt_key
