from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from rcrps.typed_observation import SemanticElement, SemanticSnapshot  # noqa: E402
from rcrps.webarena_public_navigation_v3 import (  # noqa: E402
    compile_public_navigation_v3,
)
from rcrps.webarena_public_navigation_v4 import (  # noqa: E402
    public_navigation_signature_v4,
    quoted_entity_navigation_decision_v4,
    resolve_public_navigation_v4,
    route_prefix_signatures_v4,
)


def element(
    bid: str,
    *,
    role: str,
    name: str,
    tag: str,
    href: str | None = None,
    clickable: bool = True,
) -> SemanticElement:
    attributes = {} if href is None else {"href": href}
    return SemanticElement(
        bid=bid,
        role=role,
        name=name,
        subtree_text=name,
        ax_properties=(),
        ax_parent_bid=None,
        dom_tag=tag,
        dom_attributes=tuple(sorted(attributes.items())),
        dom_parent_bid=None,
        visible=True,
        clickable=clickable,
        bbox=(0.0, 0.0, 100.0, 20.0),
    )


def inventory(*rows: SemanticElement):
    return compile_public_navigation_v3(
        SemanticSnapshot(tuple(rows)),
        current_url="http://example.local/",
        goal="edit the existing page",
    )


def test_stale_bid_rebinds_only_by_unique_stable_public_signature() -> None:
    previous = inventory(
        element(
            "309",
            role="link",
            name="Personal",
            tag="a",
            href="/dashboard/projects?personal=true&sort=name_asc",
        )
    )
    current = inventory(
        element(
            "310",
            role="link",
            name="Personal",
            tag="a",
            href="/dashboard/projects?personal=true&sort=name_asc",
        )
    )
    history = [
        {
            "bid": "309",
            "stable_signature": public_navigation_signature_v4(
                previous.candidates[0]
            ).record(),
        }
    ]
    decision = resolve_public_navigation_v4(
        current,
        model_output=(
            '<INVERSE_NAVIGATION>{"decision":"click","bid":"309"}'
            "</INVERSE_NAVIGATION>"
        ),
        navigation_history=history,
    )
    assert decision.allowed is True
    assert decision.candidate.bid == "310"
    assert decision.resolution_source == "stable_semantic_rebind"


def test_quoted_existing_entity_preempts_create_control() -> None:
    current = inventory(
        element("1493", role="gridcell", name="Home Page", tag="td"),
        element("718", role="button", name="Add New Page", tag="button"),
    )
    decision = quoted_entity_navigation_decision_v4(
        'Change the page title of "Home Page" page on my site to "New".',
        current,
    )
    assert decision is not None
    assert decision.candidate.bid == "1493"
    assert decision.resolution_source == "unique_quoted_entity"


def test_recovery_route_keeps_only_effective_pre_error_public_steps() -> None:
    first = inventory(
        element("1", role="link", name="Byte Blaze", tag="a", href="/byteblaze")
    ).candidates[0]
    second = inventory(
        element("2", role="link", name="Edit profile", tag="a", href="/-/profile")
    ).candidates[0]
    recovery = inventory(
        element("3", role="link", name="Home", tag="a", href="/")
    ).candidates[0]
    history = [
        {
            "effective": True,
            "stable_signature": public_navigation_signature_v4(first).record(),
            "public_recovery_signal_before": {"detected": False},
        },
        {
            "effective": True,
            "stable_signature": public_navigation_signature_v4(second).record(),
            "public_recovery_signal_before": {"detected": False},
        },
        {
            "effective": True,
            "stable_signature": public_navigation_signature_v4(recovery).record(),
            "public_recovery_signal_before": {"detected": True},
        },
    ]
    assert route_prefix_signatures_v4(history) == (
        public_navigation_signature_v4(first),
        public_navigation_signature_v4(second),
    )

