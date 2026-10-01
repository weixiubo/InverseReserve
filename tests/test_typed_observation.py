from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from rcrps.typed_observation import (  # noqa: E402
    SemanticElement,
    SemanticSnapshot,
    check_postcondition,
    check_restoration,
    infer_preview_contract,
    semantic_delta,
)


def element(
    bid: str,
    *,
    role: str = "",
    name: str = "",
    parent: str | None = None,
    dom_parent: str | None = None,
    properties: dict | None = None,
    tag: str = "div",
    classes: str = "",
    visible: bool = True,
    clickable: bool = True,
    text: str = "",
) -> SemanticElement:
    attrs = (("class", classes),) if classes else ()
    return SemanticElement(
        bid=bid,
        role=role,
        name=name,
        subtree_text=text or name,
        ax_properties=tuple(sorted((properties or {}).items())),
        ax_parent_bid=parent,
        dom_tag=tag,
        dom_attributes=attrs,
        dom_parent_bid=dom_parent,
        visible=visible,
        clickable=clickable,
        bbox=(0.0, 0.0, 10.0, 10.0),
    )


def test_disclosure_contract_checks_expansion_and_same_control_inverse() -> None:
    before = SemanticSnapshot(
        (
            element("list", role="tablist", clickable=False),
            element(
                "header",
                role="tab",
                name="Section",
                parent="list",
                properties={"expanded": False, "selected": False, "controls": "panel"},
            ),
        )
    )
    after = SemanticSnapshot(
        (
            element("list", role="tablist", clickable=False),
            element(
                "header",
                role="tab",
                name="Section",
                parent="list",
                properties={"expanded": True, "selected": True, "controls": "panel"},
            ),
            element("panel", role="tabpanel", parent="header", text="new evidence"),
        )
    )

    decision = infer_preview_contract(before, "header")
    assert decision.allowed
    assert decision.contract is not None
    assert decision.contract.kind == "disclosure_toggle"
    assert decision.contract.inverse_bid == "header"
    assert check_postcondition(before, after, decision.contract).passed
    assert semantic_delta(before, after).newly_visible_text == ("new evidence",)
    assert check_restoration(before, before).passed


def test_tab_contract_records_previous_selected_control_as_inverse() -> None:
    before = SemanticSnapshot(
        (
            element("list", role="tablist", clickable=False),
            element(
                "tab1",
                role="tab",
                parent="list",
                properties={"selected": True, "expanded": True},
                clickable=False,
            ),
            element("link1", role="link", parent="tab1"),
            element(
                "tab2",
                role="tab",
                parent="list",
                properties={"selected": False, "expanded": False},
                clickable=False,
            ),
            element("link2", role="link", parent="tab2"),
        )
    )
    after = SemanticSnapshot(
        (
            element("list", role="tablist", clickable=False),
            element(
                "tab1",
                role="tab",
                parent="list",
                properties={"selected": False, "expanded": False},
                clickable=False,
            ),
            element("link1", role="link", parent="tab1"),
            element(
                "tab2",
                role="tab",
                parent="list",
                properties={"selected": True, "expanded": True},
                clickable=False,
            ),
            element("link2", role="link", parent="tab2"),
        )
    )

    decision = infer_preview_contract(before, "link2")
    assert decision.allowed
    assert decision.contract is not None
    assert decision.contract.kind == "tab_switch"
    assert decision.contract.action_bid == "link2"
    assert decision.contract.inverse_bid == "link1"
    assert decision.contract.inverse_bid != decision.contract.action_bid
    assert check_postcondition(before, after, decision.contract).passed


def test_popup_menu_uses_hover_and_neutral_pointer_inverse() -> None:
    before = SemanticSnapshot(
        (
            element("menu", role="menu", clickable=False),
            element(
                "parent",
                role="menuitem",
                name="Parent",
                parent="menu",
                properties={"hasPopup": "menu"},
            ),
        )
    )
    after = SemanticSnapshot(
        before.elements
        + (
            element("submenu", role="menu", parent="parent", clickable=False),
            element("leaf", role="menuitem", name="Leaf", parent="submenu"),
        )
    )

    decision = infer_preview_contract(before, "parent")
    assert decision.allowed
    assert decision.contract is not None
    assert decision.contract.operation == "hover"
    assert decision.contract.inverse_operation == "move_to_neutral_region"
    assert check_postcondition(before, after, decision.contract).passed


def test_public_folder_class_admits_toggle_but_file_is_rejected() -> None:
    snapshot = SemanticSnapshot(
        (
            element("tree", role="list", tag="ul", clickable=False),
            element("folder-li", role="listitem", parent="tree", tag="li"),
            element(
                "folder-span",
                role="",
                dom_parent="folder-li",
                tag="span",
                classes="folder",
            ),
            element("file-li", role="listitem", parent="tree", tag="li"),
            element(
                "file-span",
                role="",
                dom_parent="file-li",
                tag="span",
                classes="file",
            ),
            element(
                "nested-li",
                role="listitem",
                parent="folder-li",
                dom_parent="folder-li",
                tag="li",
            ),
            element(
                "nested-folder",
                dom_parent="nested-li",
                tag="span",
                classes="folder",
            ),
        )
    )

    folder = infer_preview_contract(snapshot, "folder-span")
    folder_from_container = infer_preview_contract(snapshot, "folder-li")
    tree_container = infer_preview_contract(snapshot, "tree")
    file = infer_preview_contract(snapshot, "file-span")
    assert folder.allowed and folder.contract is not None
    assert folder.contract.kind == "tree_folder_toggle"
    assert folder.contract.semantic_bid == "folder-li"
    assert folder.contract.action_bid == "folder-span"
    assert folder_from_container.contract == folder.contract
    assert not tree_container.allowed
    assert not file.allowed


def test_unknown_clickable_is_not_mislabelled_as_preview() -> None:
    snapshot = SemanticSnapshot((element("submit", role="button", name="Submit"),))
    decision = infer_preview_contract(snapshot, "submit")
    assert not decision.allowed
    assert decision.contract is None
    assert "certified inverse" in decision.reason


def test_public_hidden_ancestor_overrides_geometric_visibility() -> None:
    hidden_panel = element(
        "panel",
        role="tabpanel",
        tag="div",
        clickable=False,
    )
    hidden_panel = SemanticElement(
        **{
            **hidden_panel.__dict__,
            "dom_attributes": (("aria-hidden", "true"), ("style", "display: none")),
        }
    )
    submit = element(
        "submit",
        role="button",
        name="Submit",
        dom_parent="panel",
        visible=True,
    )
    snapshot = SemanticSnapshot((hidden_panel, submit))

    assert submit.visible
    assert not snapshot.is_effectively_visible("submit")
    assert infer_preview_contract(snapshot, "submit").reason == (
        "action element is absent or invisible"
    )
    assert snapshot.semantic_fingerprint() == ()
