"""Public-semantic successor contracts for parameterized GUI exploration.

This module is intentionally separate from the immutable C428 implementation.
It admits new interaction types only when benchmark-standard AX/DOM fields
identify both the transition class and a generic inverse.  Task IDs, CSS
selectors, evaluator fields, and source-defined targets are not inputs.
"""

from __future__ import annotations

from dataclasses import dataclass

from .transaction_actions import (
    ActionSequenceContract,
    ContractAction,
    adapt_legacy_contract,
)
from .typed_observation import (
    ContractCheck,
    PreviewContract,
    SemanticDelta,
    SemanticElement,
    SemanticSnapshot,
    check_postcondition,
    check_restoration,
    infer_preview_contract,
    semantic_delta,
)


LEGACY_KINDS = frozenset(
    {"disclosure_toggle", "tab_switch", "menu_hover", "tree_folder_toggle"}
)
POPUP_ROLES = {
    "dialog": frozenset({"dialog", "alertdialog"}),
    "grid": frozenset({"grid", "row", "gridcell"}),
    "listbox": frozenset({"listbox", "option"}),
    "menu": frozenset({"menu", "menuitem"}),
    "tree": frozenset({"tree", "treeitem"}),
    "true": frozenset(
        {"dialog", "alertdialog", "grid", "listbox", "menu", "tree"}
    ),
}
AUTOCOMPLETE_VALUES = frozenset({"both", "inline", "list"})
TEXT_INPUT_ROLES = frozenset({"combobox", "searchbox", "textbox"})
TEXT_INPUT_TAGS = frozenset({"input", "textarea"})


@dataclass(frozen=True)
class SequenceContractDecision:
    allowed: bool
    contract: ActionSequenceContract | None
    reason: str


def _normalized_scalar(value: object) -> str:
    if value is True:
        return "true"
    if value is False or value is None:
        return ""
    return str(value).strip().casefold()


def _public_popup_kind(element: SemanticElement) -> str:
    value = element.ax_property("hasPopup")
    if _normalized_scalar(value) in {"", "false"}:
        value = element.dom_attribute("aria-haspopup")
    normalized = _normalized_scalar(value)
    return normalized if normalized in POPUP_ROLES else ""


def _public_autocomplete(element: SemanticElement) -> bool:
    role = element.role.casefold()
    ax_value = _normalized_scalar(element.ax_property("autocomplete"))
    dom_value = _normalized_scalar(element.dom_attribute("aria-autocomplete"))
    popup = _public_popup_kind(element)
    explicit = (
        role == "combobox"
        or ax_value in AUTOCOMPLETE_VALUES
        or dom_value in AUTOCOMPLETE_VALUES
        or popup == "listbox"
    )
    contenteditable = _normalized_scalar(element.dom_attribute("contenteditable"))
    input_surface = (
        element.dom_tag.casefold() in TEXT_INPUT_TAGS
        or contenteditable == "true"
    )
    readonly = (
        _normalized_scalar(element.ax_property("readonly")) == "true"
        or element.dom_attribute("readonly") is not None
        or _normalized_scalar(element.dom_attribute("aria-readonly")) == "true"
    )
    return explicit and input_surface and role in TEXT_INPUT_ROLES and not readonly


def _public_value(element: SemanticElement) -> str:
    value = element.ax_property("value")
    if value is None:
        value = element.dom_attribute("value", "")
    return "" if value is None else str(value)


def infer_sequence_contract(
    snapshot: SemanticSnapshot,
    action_bid: str,
    *,
    query: str | None = None,
) -> SequenceContractDecision:
    """Infer a reversible action sequence from public semantics only."""

    legacy = infer_preview_contract(snapshot, action_bid)
    if legacy.allowed and legacy.contract is not None:
        return SequenceContractDecision(
            True,
            adapt_legacy_contract(legacy.contract),
            legacy.reason,
        )

    element = snapshot.get(action_bid)
    if element is None or not snapshot.is_effectively_visible(action_bid):
        return SequenceContractDecision(
            False,
            None,
            "action element is absent or invisible",
        )

    if query is not None and _public_autocomplete(element):
        if not query.strip() or len(query) > 256:
            return SequenceContractDecision(
                False,
                None,
                "autocomplete query must contain between 1 and 256 characters",
            )
        prior_value = _public_value(element)
        return SequenceContractDecision(
            True,
            ActionSequenceContract(
                kind="combobox_suggestion",
                semantic_bid=element.bid,
                action=ContractAction("fill", element.bid, query, True),
                inverse_actions=(
                    ContractAction("press", element.bid, "Escape"),
                    ContractAction("fill", element.bid, prior_value, False),
                ),
            ),
            "editable input exposes public autocomplete or listbox semantics",
        )

    popup_kind = _public_popup_kind(element)
    expanded = element.ax_property("expanded")
    if expanded is None:
        expanded = element.dom_attribute("aria-expanded")
    already_open = expanded is True or _normalized_scalar(expanded) == "true"
    if popup_kind and element.clickable and not already_open:
        return SequenceContractDecision(
            True,
            ActionSequenceContract(
                kind="popup_dialog_open",
                semantic_bid=element.bid,
                action=ContractAction("click", element.bid),
                inverse_actions=(ContractAction("press", element.bid, "Escape"),),
            ),
            f"control explicitly declares a closed {popup_kind} popup",
        )

    return SequenceContractDecision(
        False,
        None,
        "no supported public semantic type with a certified inverse sequence",
    )


def _added_roles(after: SemanticSnapshot, delta: SemanticDelta) -> frozenset[str]:
    return frozenset(
        element.role.casefold()
        for bid in delta.added_visible_bids
        if (element := after.get(bid)) is not None
    )


def check_sequence_postcondition(
    before: SemanticSnapshot,
    after: SemanticSnapshot,
    contract: ActionSequenceContract,
) -> ContractCheck:
    """Verify the typed successor transition against its public state change."""

    if contract.kind in LEGACY_KINDS:
        legacy_action = contract.action
        legacy_inverse = contract.inverse_actions[0]
        assert legacy_action.bid is not None
        return check_postcondition(
            before,
            after,
            PreviewContract(
                kind=contract.kind,
                action_bid=legacy_action.bid,
                semantic_bid=contract.semantic_bid,
                operation=legacy_action.operation,
                inverse_operation=legacy_inverse.operation,
                inverse_bid=legacy_inverse.bid,
                prior_selected_bid=contract.prior_selected_bid,
            ),
        )

    delta = semantic_delta(before, after)
    target_before = before.get(contract.semantic_bid)
    target_after = after.get(contract.semantic_bid)
    if target_before is None or target_after is None:
        return ContractCheck(False, "contract target disappeared", delta)

    if contract.kind == "combobox_suggestion":
        expected_value = str(contract.action.argument)
        value_matches = _public_value(target_after) == expected_value
        suggestion_roles = POPUP_ROLES["listbox"] | POPUP_ROLES["menu"]
        surface_added = bool(_added_roles(after, delta) & suggestion_roles)
        passed = value_matches and surface_added
        reason = (
            "query value and suggestion surface became public"
            if passed
            else "query value or suggestion surface postcondition failed"
        )
        return ContractCheck(passed, reason, delta)

    if contract.kind == "popup_dialog_open":
        popup_kind = _public_popup_kind(target_before)
        expected_roles = POPUP_ROLES.get(popup_kind, frozenset())
        expanded = target_after.ax_property("expanded")
        if expanded is None:
            expanded = target_after.dom_attribute("aria-expanded")
        expanded_true = expanded is True or _normalized_scalar(expanded) == "true"
        surface_added = bool(_added_roles(after, delta) & expected_roles)
        passed = expanded_true or surface_added
        reason = (
            "declared popup became public"
            if passed
            else "declared popup did not expose its expected public role or expanded state"
        )
        return ContractCheck(passed, reason, delta)

    raise ValueError(f"unsupported sequence contract kind: {contract.kind}")


def check_sequence_restoration(
    before: SemanticSnapshot,
    restored: SemanticSnapshot,
) -> ContractCheck:
    return check_restoration(before, restored)
