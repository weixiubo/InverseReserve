from __future__ import annotations

import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from rcrps.typed_observation import SemanticElement, SemanticSnapshot  # noqa: E402
from rcrps.webarena_exact_mutation_agent_v16_nav6 import (  # noqa: E402
    ExactMutationTransferAgentV16Nav6,
)
from rcrps.webarena_public_navigation_v6 import (  # noqa: E402
    PublicFormRevealCandidateV6,
    compile_public_navigation_v6,
    exact_form_reveal_decision_v6,
    quoted_entity_row_action_decision_v6,
)


FORM_GOAL = "set the homepage URL on my profile to helloworld.xyz"
ROW_GOAL = 'Change the page title of "Home Page" page on my site to "New".'


def element(
    bid: str,
    *,
    role: str,
    name: str,
    tag: str,
    parent: str | None = None,
    visible: bool = True,
    clickable: bool = True,
    bbox: tuple[float, float, float, float] | None = (
        0.0,
        0.0,
        100.0,
        20.0,
    ),
    attributes: dict[str, str] | None = None,
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
        bbox=bbox,
    )


def offscreen_form_snapshot() -> SemanticSnapshot:
    return SemanticSnapshot(
        (
            element(
                "form",
                role="form",
                name="Profile",
                tag="form",
                visible=False,
                clickable=False,
                bbox=(250.0, 100.0, 1000.0, 2200.0),
            ),
            element(
                "target",
                role="textbox",
                name="Website url",
                tag="input",
                parent="form",
                visible=False,
                bbox=(610.0, 1522.0, 320.0, 34.0),
                attributes={
                    "id": "user_website_url",
                    "name": "user[website_url]",
                },
            ),
            element(
                "submit",
                role="button",
                name="Update profile settings",
                tag="button",
                parent="form",
                visible=False,
                bbox=(281.0, 2212.0, 164.0, 32.0),
            ),
        )
    )


def test_exact_form_reveal_computes_joint_public_scroll() -> None:
    inventory = compile_public_navigation_v6(
        offscreen_form_snapshot(),
        current_url="http://example.local/-/profile",
        goal=FORM_GOAL,
        viewport_width=1280,
        viewport_height=720,
    )
    evidence = inventory.exact_form_reveal
    assert evidence.allowed is True
    assert evidence.target_bid == "target"
    assert evidence.submit_bid == "submit"
    assert evidence.joint_scroll_interval == (1508.0, 1539.0)
    assert evidence.delta_y == 1524

    decision = exact_form_reveal_decision_v6(inventory)
    assert decision is not None
    assert decision.allowed is True
    assert isinstance(decision.candidate, PublicFormRevealCandidateV6)
    assert decision.candidate.action.browsergym_code(
        viewport_width=1280,
        viewport_height=720,
    ) == "scroll(0, 1524)"


def test_v16_agent_preempts_model_with_exact_form_reveal() -> None:
    inventory = compile_public_navigation_v6(
        offscreen_form_snapshot(),
        current_url="http://example.local/-/profile",
        goal=FORM_GOAL,
        viewport_width=1280,
        viewport_height=720,
    )
    agent = ExactMutationTransferAgentV16Nav6.__new__(
        ExactMutationTransferAgentV16Nav6
    )
    agent.recovery_replay_queue = []
    agent.pending_row_edit = False
    agent.method_failure = None
    decision = agent._deterministic_navigation_decision(
        inventory=inventory,
        recovery_detected=False,
    )
    assert decision.resolution_source == "exact_form_boundary_reveal"


def test_exact_form_reveal_is_single_attempt_per_public_state() -> None:
    first = compile_public_navigation_v6(
        offscreen_form_snapshot(),
        current_url="http://example.local/-/profile",
        goal=FORM_GOAL,
        viewport_width=1280,
        viewport_height=720,
    )
    candidate = exact_form_reveal_decision_v6(first).candidate
    second = compile_public_navigation_v6(
        offscreen_form_snapshot(),
        current_url="http://example.local/-/profile",
        goal=FORM_GOAL,
        viewport_width=1280,
        viewport_height=720,
        attempt_counts={candidate.state_action_key: 1},
    )
    assert second.exact_form_reveal.exhausted is True
    assert second.exact_form_reveal.allowed is False
    assert exact_form_reveal_decision_v6(second) is None


@pytest.mark.parametrize(
    "mutation",
    [
        lambda rows: rows.__setitem__(
            1,
            element(
                "target",
                role="textbox",
                name="Website url",
                tag="input",
                parent="form",
                visible=False,
                bbox=None,
            ),
        ),
        lambda rows: rows.append(
            element(
                "other_target",
                role="textbox",
                name="Website URL",
                tag="input",
                parent="form",
                visible=False,
                bbox=(610.0, 1700.0, 320.0, 34.0),
            )
        ),
    ],
)
def test_exact_form_reveal_fails_closed_for_hidden_or_ambiguous_target(
    mutation,
) -> None:
    rows = list(offscreen_form_snapshot().elements)
    mutation(rows)
    inventory = compile_public_navigation_v6(
        SemanticSnapshot(tuple(rows)),
        current_url="http://example.local/-/profile",
        goal=FORM_GOAL,
        viewport_width=1280,
        viewport_height=720,
    )
    assert inventory.exact_form_reveal.allowed is False
    assert exact_form_reveal_decision_v6(inventory) is None


def canonical_row_snapshot(*, sibling_duplicate: bool = False) -> SemanticSnapshot:
    action_parent = "row" if sibling_duplicate else "action_cell"
    rows = [
        element(
            "page",
            role="main",
            name="Pages",
            tag="main",
            clickable=False,
        ),
        element(
            "row",
            role="row",
            name="Home Page row",
            tag="tr",
            parent="page",
            clickable=False,
        ),
        element(
            "home",
            role="gridcell",
            name="Home Page",
            tag="td",
            parent="row",
        ),
        element(
            "action_cell",
            role="gridcell",
            name="Select",
            tag="td",
            parent="row",
        ),
    ]
    if not sibling_duplicate:
        rows.append(
            element(
                "action_wrap",
                role="generic",
                name="Select",
                tag="div",
                parent="action_cell",
                clickable=False,
            )
        )
    rows.append(
        element(
            "action_button",
            role="button",
            name="Select",
            tag="button",
            parent=action_parent if sibling_duplicate else "action_wrap",
        )
    )
    return SemanticSnapshot(tuple(rows))


def test_row_action_canonicalizes_clickable_cell_to_descendant_button() -> None:
    inventory = compile_public_navigation_v6(
        canonical_row_snapshot(),
        current_url="http://example.local/admin/cms/page/",
        goal=ROW_GOAL,
        viewport_width=1280,
        viewport_height=720,
        maximum_candidates=2,
    )
    evidence = inventory.row_action_binding
    assert evidence.allowed is True
    assert set(evidence.row_action_match_bids) == {
        "action_button",
        "action_cell",
    }
    assert set(evidence.canonical_chain_bids) == {
        "action_cell",
        "action_button",
    }
    assert evidence.action_bid == "action_button"
    assert evidence.record()["canonicalization_used"] is True
    decision = quoted_entity_row_action_decision_v6(inventory)
    assert decision is not None
    assert decision.candidate.bid == "action_button"


def test_row_action_rejects_same_label_siblings() -> None:
    inventory = compile_public_navigation_v6(
        canonical_row_snapshot(sibling_duplicate=True),
        current_url="http://example.local/admin/cms/page/",
        goal=ROW_GOAL,
        viewport_width=1280,
        viewport_height=720,
    )
    assert inventory.row_action_binding.allowed is False
    assert quoted_entity_row_action_decision_v6(inventory) is None
