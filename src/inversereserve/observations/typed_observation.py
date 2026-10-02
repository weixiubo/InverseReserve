"""Semantic GUI snapshots and typed preview contracts.

The module consumes BrowserGym's benchmark-standard accessibility tree, DOM
snapshot, and public extra-element properties.  It never reads task state,
reward, source-defined answers, or evaluator fields.  Its purpose is to turn
an otherwise ambiguous click into a small, checkable transaction contract:
an operation, a structural precondition, an expected postcondition, and a
channel-specific inverse.
"""

from __future__ import annotations

import json
import re
from typing import Any, Mapping

from inversereserve.observations.semantic_types import (
    RELEVANT_AX_PROPERTIES as RELEVANT_AX_PROPERTIES,
)
from inversereserve.observations.semantic_types import (
    RELEVANT_DOM_ATTRIBUTES as RELEVANT_DOM_ATTRIBUTES,
)
from inversereserve.observations.semantic_types import (
    ContractCheck as ContractCheck,
)
from inversereserve.observations.semantic_types import (
    ContractDecision as ContractDecision,
)
from inversereserve.observations.semantic_types import (
    PreviewContract as PreviewContract,
)
from inversereserve.observations.semantic_types import (
    SemanticDelta as SemanticDelta,
)
from inversereserve.observations.semantic_types import (
    SemanticElement as SemanticElement,
)
from inversereserve.observations.semantic_types import (
    SemanticSnapshot as SemanticSnapshot,
)

FOLDER_CLASS_TOKENS = frozenset({"folder", "directory"})
FILE_CLASS_TOKENS = frozenset({"file", "document"})


def _json_scalar(value: Any) -> bool | int | float | str | None:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _normalize_text(value: Any) -> str:
    return re.sub("\\s+", " ", str(value or "")).strip()


def _to_string(strings: list[str], index: int) -> str | None:
    return None if index == -1 else strings[index]


def _dom_records(dom_snapshot: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    strings = dom_snapshot["strings"]
    records: dict[str, dict[str, Any]] = {}
    for document in dom_snapshot["documents"]:
        nodes = document["nodes"]
        node_bids: dict[int, str] = {}
        node_attributes: dict[int, dict[str, str]] = {}
        for index, raw_attributes in enumerate(nodes["attributes"]):
            attributes = {}
            for offset in range(0, len(raw_attributes), 2):
                name = _to_string(strings, raw_attributes[offset])
                value = _to_string(strings, raw_attributes[offset + 1])
                if name is not None:
                    attributes[name] = "" if value is None else value
            node_attributes[index] = attributes
            if "bid" in attributes:
                node_bids[index] = attributes["bid"]
        for index, bid in node_bids.items():
            parent_index = int(nodes["parentIndex"][index])
            parent_bid = None
            while parent_index != -1:
                if parent_index in node_bids and node_bids[parent_index] != bid:
                    parent_bid = node_bids[parent_index]
                    break
                parent_index = int(nodes["parentIndex"][parent_index])
            tag = _to_string(strings, nodes["nodeName"][index]) or ""
            records[bid] = {
                "tag": tag.casefold(),
                "attributes": node_attributes[index],
                "parent_bid": parent_bid,
            }
    return records


def _ax_records(ax_tree: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    nodes = list(ax_tree["nodes"])
    node_id_to_index = {str(node["nodeId"]): index for index, node in enumerate(nodes)}
    parent_index: dict[int, int] = {}
    for index, node in enumerate(nodes):
        for child_id in node.get("childIds", []):
            child_index = node_id_to_index.get(str(child_id))
            if child_index is not None and child_index != index:
                parent_index[child_index] = index

    def subtree_names(index: int) -> tuple[str, ...]:
        names = []
        frontier = [index]
        seen = set()
        while frontier:
            current = frontier.pop(0)
            if current in seen:
                continue
            seen.add(current)
            node = nodes[current]
            name = _normalize_text(node.get("name", {}).get("value", ""))
            if name and name not in names:
                names.append(name)
            for child_id in node.get("childIds", []):
                child_index = node_id_to_index.get(str(child_id))
                if child_index is not None:
                    frontier.append(child_index)
        return tuple(names)

    records = {}
    for index, node in enumerate(nodes):
        bid = node.get("browsergym_id")
        if bid is None:
            continue
        bid = str(bid)
        parent_bid = None
        cursor = parent_index.get(index)
        while cursor is not None:
            parent = nodes[cursor]
            if parent.get("browsergym_id") is not None and str(parent["browsergym_id"]) != bid:
                parent_bid = str(parent["browsergym_id"])
                break
            cursor = parent_index.get(cursor)
        properties = {}
        for prop in node.get("properties", []):
            if "value" not in prop or "value" not in prop["value"]:
                continue
            properties[str(prop["name"])] = _json_scalar(prop["value"]["value"])
        names = subtree_names(index)
        records[bid] = {
            "role": str(node.get("role", {}).get("value", "")),
            "name": _normalize_text(node.get("name", {}).get("value", "")),
            "subtree_text": _normalize_text(" ".join(names)),
            "properties": properties,
            "parent_bid": parent_bid,
        }
    return records


def semantic_snapshot(
    ax_tree: Mapping[str, Any],
    dom_snapshot: Mapping[str, Any],
    extra_properties: Mapping[str, Mapping[str, Any]],
) -> SemanticSnapshot:
    """Build a deterministic public-observation snapshot keyed by BrowserGym bid."""
    ax = _ax_records(ax_tree)
    dom = _dom_records(dom_snapshot)
    bids = sorted(set(ax) | set(dom) | {str(bid) for bid in extra_properties})
    elements = []
    for bid in bids:
        ax_record = ax.get(bid, {})
        dom_record = dom.get(bid, {})
        extra = extra_properties.get(bid, {})
        bbox = extra.get("bbox")
        bbox_tuple = tuple((float(value) for value in bbox)) if bbox is not None else None
        raw_dom_attributes = dom_record.get("attributes", {})
        elements.append(
            SemanticElement(
                bid=bid,
                role=str(ax_record.get("role", "")),
                name=str(ax_record.get("name", "")),
                subtree_text=str(ax_record.get("subtree_text", "")),
                ax_properties=tuple(sorted(ax_record.get("properties", {}).items())),
                ax_parent_bid=ax_record.get("parent_bid"),
                dom_tag=str(dom_record.get("tag", "")),
                dom_attributes=tuple(
                    sorted(
                        (
                            (str(name), str(value))
                            for name, value in raw_dom_attributes.items()
                            if name != "bid" and (not name.startswith("browsergym_"))
                        )
                    )
                ),
                dom_parent_bid=dom_record.get("parent_bid"),
                visible=float(extra.get("visibility", 0.0)) >= 0.5,
                clickable=bool(extra.get("clickable", False)),
                bbox=bbox_tuple,
            )
        )
    return SemanticSnapshot(tuple(elements))


def semantic_delta(before: SemanticSnapshot, after: SemanticSnapshot) -> SemanticDelta:
    before_visible = {e.bid: e for e in before.elements if before.is_effectively_visible(e.bid)}
    after_visible = {e.bid: e for e in after.elements if after.is_effectively_visible(e.bid)}
    added = sorted(set(after_visible) - set(before_visible))
    removed = sorted(set(before_visible) - set(after_visible))
    common = set(before_visible) & set(after_visible)
    changed = sorted(
        (
            bid
            for bid in common
            if before_visible[bid].semantic_signature() != after_visible[bid].semantic_signature()
        )
    )
    text = []
    for bid in added:
        value = after_visible[bid].subtree_text or after_visible[bid].name
        if value and value not in text:
            text.append(value)
    return SemanticDelta(tuple(added), tuple(removed), tuple(changed), tuple(text))


def _nearest_role(snapshot: SemanticSnapshot, element: SemanticElement, role: str) -> SemanticElement | None:
    if element.role.casefold() == role.casefold():
        return element
    return next(
        (
            ancestor
            for ancestor in snapshot.ancestors(element.bid, relation="ax")
            if ancestor.role.casefold() == role.casefold()
        ),
        None,
    )


def _folder_owner(snapshot: SemanticSnapshot, element: SemanticElement) -> SemanticElement | None:
    class_tokens = element.class_tokens
    is_folder_control = bool(class_tokens & FOLDER_CLASS_TOKENS) or any(
        ("hitarea" in token for token in class_tokens)
    )
    if is_folder_control:
        return next(
            (
                ancestor
                for ancestor in snapshot.ancestors(element.bid, relation="dom")
                if ancestor.dom_tag == "li"
            ),
            element,
        )
    if element.dom_tag == "li":
        for descendant in snapshot.descendants(element.bid, relation="dom"):
            if not descendant.class_tokens & FOLDER_CLASS_TOKENS:
                continue
            nearest_list_item = next(
                (
                    ancestor
                    for ancestor in snapshot.ancestors(descendant.bid, relation="dom")
                    if ancestor.dom_tag == "li"
                ),
                None,
            )
            if nearest_list_item is not None and nearest_list_item.bid == element.bid:
                return element
    return None


def _folder_control(snapshot: SemanticSnapshot, owner: SemanticElement) -> SemanticElement | None:
    """Choose the stable leaf control, not a container whose box grows when open."""
    candidates = []
    for candidate in (owner,) + snapshot.descendants(owner.bid, relation="dom"):
        class_tokens = candidate.class_tokens
        is_folder_label = bool(class_tokens & FOLDER_CLASS_TOKENS)
        is_hit_area = any(("hitarea" in token for token in class_tokens))
        nearest_list_item = next(
            (
                ancestor
                for ancestor in snapshot.ancestors(candidate.bid, relation="dom")
                if ancestor.dom_tag == "li"
            ),
            candidate if candidate.dom_tag == "li" else None,
        )
        if (
            snapshot.is_effectively_visible(candidate.bid)
            and candidate.clickable
            and (is_folder_label or is_hit_area)
            and (nearest_list_item is not None)
            and (nearest_list_item.bid == owner.bid)
        ):
            area = candidate.bbox[2] * candidate.bbox[3] if candidate.bbox is not None else float("inf")
            candidates.append((int(not is_folder_label), area, candidate.bid, candidate))
    return min(candidates)[-1] if candidates else None


def infer_preview_contract(snapshot: SemanticSnapshot, action_bid: str) -> ContractDecision:
    element = snapshot.get(action_bid)
    if element is None or not snapshot.is_effectively_visible(action_bid):
        return ContractDecision(False, None, "action element is absent or invisible")
    menuitem = _nearest_role(snapshot, element, "menuitem")
    if menuitem is not None and menuitem.ax_property("hasPopup"):
        return ContractDecision(
            True,
            PreviewContract(
                kind="menu_hover",
                action_bid=menuitem.bid,
                semantic_bid=menuitem.bid,
                operation="hover",
                inverse_operation="move_to_neutral_region",
                inverse_bid=None,
            ),
            "menu item declares a popup",
        )
    tab = _nearest_role(snapshot, element, "tab")
    if tab is not None:
        decision = _infer_tab_preview(snapshot, tab)
        if decision is not None:
            return decision
    button = _nearest_role(snapshot, element, "button")
    if button is not None and button.ax_property("expanded") is False:
        return ContractDecision(
            True,
            PreviewContract(
                kind="disclosure_toggle",
                action_bid=action_bid,
                semantic_bid=button.bid,
                operation="click",
                inverse_operation="click",
                inverse_bid=action_bid,
            ),
            "button exposes a collapsed expanded-state predicate",
        )
    folder = _folder_owner(snapshot, element)
    if folder is not None:
        control = _folder_control(snapshot, folder)
        if control is None:
            return ContractDecision(False, None, "folder container has no stable public toggle control")
        return ContractDecision(
            True,
            PreviewContract(
                kind="tree_folder_toggle",
                action_bid=control.bid,
                semantic_bid=folder.bid,
                operation="click",
                inverse_operation="click",
                inverse_bid=control.bid,
            ),
            "public DOM semantics identify a stable folder/directory toggle",
        )
    return ContractDecision(False, None, "no supported public semantic type with a certified inverse")


def check_postcondition(
    before: SemanticSnapshot, after: SemanticSnapshot, contract: PreviewContract
) -> ContractCheck:
    delta = semantic_delta(before, after)
    target_after = after.get(contract.semantic_bid)
    if contract.kind == "disclosure_toggle":
        passed = bool(target_after and target_after.ax_property("expanded") is True)
        reason = "disclosure expanded" if passed else "disclosure did not expose expanded=true"
    elif contract.kind == "tab_switch":
        prior_after = after.get(contract.prior_selected_bid)
        passed = _tab_selection_transferred(target_after, prior_after)
        reason = "tab selection transferred" if passed else "tab selected-state did not transfer"
    elif contract.kind == "menu_hover":
        passed = any(
            (
                after.get(bid) is not None and after.get(bid).role.casefold() in {"menu", "menuitem"}
                for bid in delta.added_visible_bids
            )
        )
        reason = "submenu became visible" if passed else "hover did not reveal a submenu"
    elif contract.kind == "tree_folder_toggle":
        descendants = {e.bid for e in after.descendants(contract.semantic_bid, relation="ax")}
        passed = bool(descendants & set(delta.added_visible_bids))
        reason = "folder revealed descendants" if passed else "folder revealed no AX descendants"
    else:
        raise ValueError(f"unsupported contract kind: {contract.kind}")
    return ContractCheck(passed, reason, delta)


def check_restoration(before: SemanticSnapshot, restored: SemanticSnapshot) -> ContractCheck:
    delta = semantic_delta(before, restored)
    passed = before.semantic_fingerprint() == restored.semantic_fingerprint()
    return ContractCheck(
        passed,
        "semantic state restored" if passed else "semantic state differs from pre-preview state",
        delta,
    )


def _infer_tab_preview(snapshot: SemanticSnapshot, tab: SemanticElement) -> ContractDecision | None:
    target_control = tab if tab.clickable else _clickable_descendant(snapshot, tab.bid, None)
    if target_control is None:
        return ContractDecision(False, None, "tab has no public clickable control")
    siblings = snapshot.children(tab.ax_parent_bid, relation="ax") if tab.ax_parent_bid is not None else ()
    selected = next(
        (
            sibling
            for sibling in siblings
            if sibling.role.casefold() == "tab" and sibling.ax_property("selected") is True
        ),
        None,
    )
    if selected is not None:
        if selected.bid == tab.bid:
            return ContractDecision(False, None, "tab is already selected")
        inverse = _clickable_descendant(snapshot, selected.bid, selected if selected.clickable else None)
        if inverse is None:
            return ContractDecision(False, None, "selected tab has no public inverse control")
        return ContractDecision(
            True,
            PreviewContract(
                kind="tab_switch",
                action_bid=target_control.bid,
                semantic_bid=tab.bid,
                operation="click",
                inverse_operation="click",
                inverse_bid=inverse.bid,
                prior_selected_bid=selected.bid,
            ),
            "unselected tab has a public previously selected inverse",
        )
    if tab.ax_property("expanded") is False and tab.ax_property("controls"):
        return ContractDecision(
            True,
            PreviewContract(
                kind="disclosure_toggle",
                action_bid=target_control.bid,
                semantic_bid=tab.bid,
                operation="click",
                inverse_operation="click",
                inverse_bid=target_control.bid,
            ),
            "collapsed disclosure declares expanded state and a controlled region",
        )
    return None


def _clickable_descendant(
    snapshot: SemanticSnapshot, bid: str, fallback: SemanticElement | None = None
) -> SemanticElement | None:
    return next(
        (
            child
            for child in snapshot.descendants(bid, relation="ax")
            if snapshot.is_effectively_visible(child.bid) and child.clickable
        ),
        fallback,
    )


def _tab_selection_transferred(
    target_after: SemanticElement | None, prior_after: SemanticElement | None
) -> bool:
    return bool(
        target_after
        and target_after.ax_property("selected") is True
        and prior_after
        and (prior_after.ax_property("selected") is False)
    )
