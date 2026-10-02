"""Public observation interpretation shared by contract inference and grounding."""

from __future__ import annotations

from typing import Any

from inversereserve.observations.typed_observation import SemanticSnapshot

TEXT_INPUT_ROLES = frozenset({"combobox", "searchbox", "textbox"})
AUTOCOMPLETE_VALUES = frozenset({"both", "inline", "list"})
MONTH_NAMES = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}


def _normalized(value: object) -> str:
    if value is True:
        return "true"
    if value is False or value is None:
        return ""
    return " ".join(str(value).split()).strip().casefold()


def _public_value(snapshot: SemanticSnapshot, bid: str) -> str:
    element = snapshot.get(bid)
    if element is None:
        return ""
    value = element.ax_property("value")
    if value is None:
        value = element.dom_attribute("value", "")
    return "" if value is None else str(value)


def _public_boolean(snapshot: SemanticSnapshot, bid: str, name: str) -> bool:
    element = snapshot.get(bid)
    if element is None:
        return False
    value = element.ax_property(name)
    if value is None:
        value = element.dom_attribute(name)
    if value is None:
        value = element.dom_attribute(f"aria-{name}")
    return value is True or _normalized(value) == "true"


def _is_editable(snapshot: SemanticSnapshot, bid: str) -> bool:
    element = snapshot.get(bid)
    if element is None or not snapshot.is_effectively_visible(bid):
        return False
    if element.role.casefold() not in TEXT_INPUT_ROLES:
        return False
    if element.dom_tag.casefold() not in {"input", "textarea"}:
        return False
    return not _public_boolean(snapshot, bid, "readonly") and (not _public_boolean(snapshot, bid, "disabled"))


def _public_popup_kind(snapshot: SemanticSnapshot, bid: str) -> str:
    element = snapshot.get(bid)
    if element is None:
        return ""
    value = element.ax_property("hasPopup")
    if _normalized(value) in {"", "false"}:
        value = element.dom_attribute("aria-haspopup")
    normalized = _normalized(value)
    return normalized if normalized in {"dialog", "grid", "listbox", "menu", "tree", "true"} else ""


def is_public_autocomplete(snapshot: SemanticSnapshot, bid: str) -> bool:
    element = snapshot.get(bid)
    if element is None or not _is_editable(snapshot, bid):
        return False
    role = element.role.casefold()
    ax_value = _normalized(element.ax_property("autocomplete"))
    dom_value = _normalized(element.dom_attribute("aria-autocomplete"))
    standard = (
        role == "combobox"
        or ax_value in AUTOCOMPLETE_VALUES
        or dom_value in AUTOCOMPLETE_VALUES
        or (_public_popup_kind(snapshot, bid) == "listbox")
    )
    library = "ui-autocomplete-input" in element.class_tokens
    return standard or library


def is_public_datepicker(snapshot: SemanticSnapshot, bid: str) -> bool:
    element = snapshot.get(bid)
    if element is None or not snapshot.is_effectively_visible(bid):
        return False
    return bool(
        element.dom_tag.casefold() == "input"
        and element.role.casefold() in TEXT_INPUT_ROLES
        and _public_boolean(snapshot, bid, "readonly")
        and ("hasdatepicker" in element.class_tokens)
        and element.clickable
    )


def _is_suggestion_surface(snapshot: SemanticSnapshot, bid: str) -> bool:
    element = snapshot.get(bid)
    if element is None or not snapshot.is_effectively_visible(bid):
        return False
    role_surface = element.role.casefold() in {"listbox", "menu"}
    library_surface = (
        "ui-autocomplete" in element.class_tokens and "ui-autocomplete-input" not in element.class_tokens
    )
    return role_surface or library_surface


def _is_calendar_surface(snapshot: SemanticSnapshot, bid: str) -> bool:
    element = snapshot.get(bid)
    return bool(
        element is not None
        and snapshot.is_effectively_visible(bid)
        and ("ui-datepicker" in element.class_tokens)
        and ("hasdatepicker" not in element.class_tokens)
    )


def public_calendar_context(snapshot: SemanticSnapshot) -> tuple[int, int] | None:
    months = []
    years = []
    for element in snapshot.elements:
        if not snapshot.is_effectively_visible(element.bid):
            continue
        text = _normalized_scalar_text(element.name or element.subtree_text)
        if "ui-datepicker-month" in element.class_tokens and text in MONTH_NAMES:
            months.append(MONTH_NAMES[text])
        if "ui-datepicker-year" in element.class_tokens and text.isdigit() and (len(text) == 4):
            years.append(int(text))
    if len(months) == 1 and len(years) == 1:
        return (months[0], years[0])
    return None


def _normalized_scalar_text(value: object) -> str:
    return " ".join(str(value or "").split()).strip().casefold()


def _shift_month(month: int, year: int, delta: int) -> tuple[int, int]:
    index = year * 12 + month - 1 + delta
    return (index % 12 + 1, index // 12)


def _visible_surface_projection(
    snapshot: SemanticSnapshot, predicate: Any
) -> tuple[tuple[str, str, str], ...]:
    return tuple(
        sorted(
            (
                (element.role.casefold(), element.dom_tag.casefold(), " ".join(sorted(element.class_tokens)))
                for element in snapshot.elements
                if predicate(snapshot, element.bid)
            )
        )
    )


def public_selected_values(snapshot: SemanticSnapshot, listbox_bid: str) -> tuple[str, ...]:
    values = []
    for element in snapshot.descendants(listbox_bid, relation="dom"):
        if element.dom_tag.casefold() != "option":
            continue
        selected = element.ax_property("selected")
        if selected is None:
            selected = element.dom_attribute("selected") is not None
        if selected is not True and _normalized(selected) != "true":
            continue
        value = str(element.dom_attribute("value", "")).strip()
        if value:
            values.append(value)
    return tuple(sorted(values))
