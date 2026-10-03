"""Compact action inventory and strict planner interface for PACT agents."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Iterable

from .typed_observation import (
    FILE_CLASS_TOKENS,
    PreviewContract,
    SemanticElement,
    SemanticSnapshot,
    infer_preview_contract,
)


ACTIONABLE_ROLES = frozenset(
    {
        "button",
        "checkbox",
        "combobox",
        "link",
        "listitem",
        "menuitem",
        "option",
        "radio",
        "searchbox",
        "slider",
        "spinbutton",
        "switch",
        "tab",
        "textbox",
        "treeitem",
    }
)
STRUCTURAL_CONTAINER_ROLES = frozenset(
    {"dialog", "list", "menu", "tablist", "tabpanel", "tree"}
)
PLANNER_SYSTEM_PROMPT = """You are the grounded action planner for a GUI agent.
The action inventory is authoritative and contains only currently visible public controls.

Choose exactly one decision:
- commit: the inventory label/role directly identifies the requested terminal action now.
- explore: the requested evidence is not visible, and the chosen row has a non-null preview_kind that can reveal it.
- abstain: neither a grounded commit nor a relevant typed exploration is available.

Rules:
1. For a path such as Parent>Child>Leaf, explore the named parent in order and commit only the final leaf.
2. Do not commit a container merely because the target may be hidden below it.
3. Do not explore a row whose preview_kind is null.
4. Use only an exact bid from the inventory.
5. ACTIVE TYPED TRANSACTIONS are already open; do not explore the same control again.
6. Do not repeat a control listed under COMPLETED EXPLORATIONS.
7. Output exactly one compact JSON object and no prose:
   {"decision":"commit|explore|abstain","bid":"BID or null"}
"""


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _shorten(value: str, maximum: int = 180) -> str:
    value = _normalize_text(value)
    if len(value) <= maximum:
        return value
    return value[: maximum - 1].rstrip() + "…"


def _state(element: SemanticElement) -> tuple[tuple[str, Any], ...]:
    keep = {
        "checked",
        "disabled",
        "expanded",
        "hasPopup",
        "pressed",
        "selected",
        "value",
    }
    return tuple((name, value) for name, value in element.ax_properties if name in keep)


def _own_label(snapshot: SemanticSnapshot, element: SemanticElement) -> str:
    if element.name:
        return _shorten(element.name)
    if element.subtree_text:
        return _shorten(element.subtree_text)
    for relation in ("ax", "dom"):
        for ancestor in snapshot.ancestors(element.bid, relation=relation):
            if ancestor.name:
                return _shorten(ancestor.name)
            if ancestor.subtree_text:
                return _shorten(ancestor.subtree_text)
    return ""


@dataclass(frozen=True)
class ActionCandidate:
    bid: str
    operation: str
    role: str
    label: str
    state: tuple[tuple[str, Any], ...]
    preview_kind: str | None
    semantic_bid: str
    parent_bid: str | None

    def prompt_record(self) -> dict[str, Any]:
        return {
            "bid": self.bid,
            "op": self.operation,
            "role": self.role,
            "label": self.label,
            "state": dict(self.state),
            "preview_kind": self.preview_kind,
            "semantic_bid": self.semantic_bid,
            "parent_bid": self.parent_bid,
        }


@dataclass(frozen=True)
class PlannerDecision:
    decision: str
    bid: str | None
    candidate: ActionCandidate | None


def _contracts(snapshot: SemanticSnapshot) -> dict[str, PreviewContract]:
    contracts = {}
    for element in snapshot.elements:
        if not snapshot.is_effectively_visible(element.bid):
            continue
        decision = infer_preview_contract(snapshot, element.bid)
        if not decision.allowed or decision.contract is None:
            continue
        contract = decision.contract
        prior = contracts.get(contract.action_bid)
        if prior is not None and prior != contract:
            raise ValueError(f"ambiguous preview contract for bid {contract.action_bid}")
        contracts[contract.action_bid] = contract
    return contracts


def _file_control_owner(
    snapshot: SemanticSnapshot, element: SemanticElement
) -> SemanticElement | None:
    if not element.class_tokens & FILE_CLASS_TOKENS:
        return None
    return next(
        (
            ancestor
            for ancestor in snapshot.ancestors(element.bid, relation="dom")
            if ancestor.dom_tag == "li"
        ),
        element,
    )


def action_candidates(snapshot: SemanticSnapshot) -> tuple[ActionCandidate, ...]:
    """Compile a deduplicated, model-facing inventory from public observations."""

    contracts = _contracts(snapshot)
    contract_related_bids = set()
    stable_tree_owner_bids = set()
    for contract in contracts.values():
        contract_related_bids.add(contract.semantic_bid)
        contract_related_bids.update(
            element.bid
            for element in snapshot.descendants(contract.semantic_bid, relation="ax")
        )
        contract_related_bids.update(
            element.bid
            for element in snapshot.descendants(contract.semantic_bid, relation="dom")
        )
        if contract.kind == "tree_folder_toggle":
            stable_tree_owner_bids.add(contract.semantic_bid)
    for element in snapshot.elements:
        file_owner = _file_control_owner(snapshot, element)
        if file_owner is not None:
            stable_tree_owner_bids.add(file_owner.bid)
    candidates: dict[str, ActionCandidate] = {}
    for action_bid, contract in contracts.items():
        action = snapshot.get(action_bid)
        semantic = snapshot.get(contract.semantic_bid)
        if action is None or semantic is None:
            continue
        candidates[action_bid] = ActionCandidate(
            bid=action_bid,
            operation=contract.operation,
            role=semantic.role or semantic.dom_tag or action.role or action.dom_tag,
            label=_own_label(snapshot, semantic),
            state=_state(semantic),
            preview_kind=contract.kind,
            semantic_bid=semantic.bid,
            parent_bid=semantic.ax_parent_bid or semantic.dom_parent_bid,
        )

    for element in snapshot.elements:
        if not snapshot.is_effectively_visible(element.bid):
            continue
        file_owner = _file_control_owner(snapshot, element)
        if file_owner is not None:
            stable_tree_owner_bids.add(file_owner.bid)
            candidates[element.bid] = ActionCandidate(
                bid=element.bid,
                operation="click",
                role="file",
                label=_own_label(snapshot, file_owner),
                state=_state(file_owner),
                preview_kind=None,
                semantic_bid=file_owner.bid,
                parent_bid=file_owner.ax_parent_bid or file_owner.dom_parent_bid,
            )
            continue
        role = element.role.casefold()
        actionable = element.clickable or role in {"menuitem", "option"}
        if not actionable or role in STRUCTURAL_CONTAINER_ROLES:
            continue
        if element.bid in stable_tree_owner_bids:
            continue
        if (
            element.bid in contract_related_bids
            and element.bid not in contracts
            and role not in {"button", "link", "menuitem", "option"}
        ):
            continue
        if element.bid in candidates:
            continue
        label = _own_label(snapshot, element)
        if not label and role not in {"checkbox", "textbox", "searchbox", "slider"}:
            continue
        candidates[element.bid] = ActionCandidate(
            bid=element.bid,
            operation="click",
            role=element.role or element.dom_tag,
            label=label,
            state=_state(element),
            preview_kind=None,
            semantic_bid=element.bid,
            parent_bid=element.ax_parent_bid or element.dom_parent_bid,
        )
    return tuple(
        sorted(
            candidates.values(),
            key=lambda row: (
                row.parent_bid or "",
                row.semantic_bid,
                row.bid,
                row.operation,
            ),
        )
    )


def render_action_inventory(candidates: Iterable[ActionCandidate]) -> str:
    return "\n".join(
        json.dumps(candidate.prompt_record(), ensure_ascii=False, sort_keys=True)
        for candidate in candidates
    )


def planner_messages(
    *,
    goal: str,
    candidates: Iterable[ActionCandidate],
    completed_explorations: Iterable[dict[str, Any]] = (),
    active_transactions: Iterable[dict[str, Any]] = (),
) -> list[dict[str, Any]]:
    candidate_rows = tuple(candidates)
    history_rows = tuple(completed_explorations)
    active_rows = tuple(active_transactions)
    inventory = render_action_inventory(candidate_rows)
    user = (
        f"GOAL:\n{goal.strip()}\n\n"
        "ACTIVE TYPED TRANSACTIONS (already open; do not repeat):\n"
        f"{json.dumps(active_rows, ensure_ascii=False, sort_keys=True)}\n\n"
        "COMPLETED EXPLORATIONS (do not repeat):\n"
        f"{json.dumps(history_rows, ensure_ascii=False, sort_keys=True)}\n\n"
        f"VISIBLE ACTION INVENTORY ({len(candidate_rows)} rows):\n"
        f"{inventory if inventory else '<empty>'}"
    )
    return [
        {"role": "system", "content": PLANNER_SYSTEM_PROMPT},
        {"role": "user", "content": user},
    ]


def _single_json_object(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("```json"):
        stripped = stripped[len("```json") :]
        if stripped.endswith("```"):
            stripped = stripped[:-3]
        stripped = stripped.strip()
    decoder = json.JSONDecoder()
    value, end = decoder.raw_decode(stripped)
    if stripped[end:].strip():
        raise ValueError("planner output contains text after the JSON object")
    if not isinstance(value, dict):
        raise ValueError("planner output must be a JSON object")
    return value


def parse_planner_decision(
    text: str,
    candidates: Iterable[ActionCandidate],
) -> PlannerDecision:
    payload = _single_json_object(text)
    if set(payload) - {"decision", "bid"}:
        raise ValueError("planner output contains unknown keys")
    decision = str(payload.get("decision", ""))
    if decision not in {"commit", "explore", "abstain"}:
        raise ValueError("planner decision must be commit, explore, or abstain")
    bid_value = payload.get("bid")
    bid = None if bid_value is None else str(bid_value)
    lookup = {candidate.bid: candidate for candidate in candidates}
    if decision == "abstain":
        if bid is not None:
            raise ValueError("abstain must use a null bid")
        return PlannerDecision(decision, None, None)
    if bid is None or bid not in lookup:
        raise ValueError("planner bid is absent from the visible inventory")
    candidate = lookup[bid]
    if decision == "explore" and candidate.preview_kind is None:
        raise ValueError("planner tried to explore an untyped control")
    return PlannerDecision(decision, bid, candidate)
