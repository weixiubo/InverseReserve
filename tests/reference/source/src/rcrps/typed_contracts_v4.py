"""Typed component contracts and scoped restoration for PACT v4."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .goal_contracts_v4 import StructuredGoalContract
from .pact_grounding_v3 import exploration_query
from .transaction_actions import ContractAction as ContractActionV3
from .transaction_actions_v4 import ContractActionV4
from .typed_contracts_v3 import (
    check_sequence_postcondition,
    infer_sequence_contract,
)
from .typed_observation import (
    ContractCheck,
    SemanticSnapshot,
    semantic_delta,
)


TEXT_INPUT_ROLES = frozenset({"combobox", "searchbox", "textbox"})
FORM_CONTROL_ROLES = frozenset(
    {
        "button",
        "checkbox",
        "combobox",
        "radio",
        "searchbox",
        "select",
        "spinbutton",
        "switch",
        "textbox",
    }
)
AUTOCOMPLETE_VALUES = frozenset({"both", "inline", "list"})
COMPENSATOR_LABELS = frozenset({"cancel", "dismiss", "no thanks", "not now"})
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
SCOPED_KINDS = frozenset(
    {
        "autocomplete_query",
        "datepicker_open",
        "editable_field_assignment",
        "native_select_update",
        "calendar_month_shift",
    }
)


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
    return not _public_boolean(snapshot, bid, "readonly") and not _public_boolean(
        snapshot, bid, "disabled"
    )


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
        or _public_popup_kind(snapshot, bid) == "listbox"
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
        and "hasdatepicker" in element.class_tokens
        and element.clickable
    )


def _is_suggestion_surface(snapshot: SemanticSnapshot, bid: str) -> bool:
    element = snapshot.get(bid)
    if element is None or not snapshot.is_effectively_visible(bid):
        return False
    role_surface = element.role.casefold() in {"listbox", "menu"}
    library_surface = (
        "ui-autocomplete" in element.class_tokens
        and "ui-autocomplete-input" not in element.class_tokens
    )
    return role_surface or library_surface


def _is_calendar_surface(snapshot: SemanticSnapshot, bid: str) -> bool:
    element = snapshot.get(bid)
    return bool(
        element is not None
        and snapshot.is_effectively_visible(bid)
        and "ui-datepicker" in element.class_tokens
        and "hasdatepicker" not in element.class_tokens
    )


def public_calendar_context(
    snapshot: SemanticSnapshot,
) -> tuple[int, int] | None:
    months = []
    years = []
    for element in snapshot.elements:
        if not snapshot.is_effectively_visible(element.bid):
            continue
        text = _normalized_scalar_text(element.name or element.subtree_text)
        if "ui-datepicker-month" in element.class_tokens and text in MONTH_NAMES:
            months.append(MONTH_NAMES[text])
        if "ui-datepicker-year" in element.class_tokens and text.isdigit() and len(text) == 4:
            years.append(int(text))
    if len(months) == 1 and len(years) == 1:
        return months[0], years[0]
    return None


def _normalized_scalar_text(value: object) -> str:
    return " ".join(str(value or "").split()).strip().casefold()


def _shift_month(month: int, year: int, delta: int) -> tuple[int, int]:
    index = year * 12 + month - 1 + delta
    return index % 12 + 1, index // 12


def _visible_surface_projection(
    snapshot: SemanticSnapshot,
    predicate: Any,
) -> tuple[tuple[str, str, str], ...]:
    return tuple(
        sorted(
            (
                element.role.casefold(),
                element.dom_tag.casefold(),
                " ".join(sorted(element.class_tokens)),
            )
            for element in snapshot.elements
            if predicate(snapshot, element.bid)
        )
    )


def public_selected_values(
    snapshot: SemanticSnapshot,
    listbox_bid: str,
) -> tuple[str, ...]:
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


def _v4_action(action: ContractActionV3) -> ContractActionV4:
    argument: str | tuple[str, ...] | None = action.argument
    return ContractActionV4(
        action.operation,
        action.bid,
        argument,
        action.enable_autocomplete_menu,
    )


@dataclass(frozen=True)
class TransactionContractV4:
    kind: str
    semantic_bid: str
    action: ContractActionV4
    inverse_actions: tuple[ContractActionV4, ...]
    expected_value: str | None = None
    prior_value: str | None = None
    expected_options: tuple[str, ...] = ()
    prior_options: tuple[str, ...] = ()
    projection_kind: str = "global"
    dynamic_compensator_labels: tuple[str, ...] = ()
    maximum_interrupt_repairs: int = 0
    legacy_contract: object | None = None
    prior_calendar: tuple[int, int] | None = None
    expected_calendar: tuple[int, int] | None = None
    dynamic_inverse_class_token: str | None = None

    def __post_init__(self) -> None:
        if not self.kind.strip() or not self.semantic_bid.strip():
            raise ValueError("transaction kind and semantic bid must be nonempty")
        if not self.inverse_actions and self.dynamic_inverse_class_token is None:
            raise ValueError("transaction requires at least one inverse action")
        if self.projection_kind not in {"global", *SCOPED_KINDS}:
            raise ValueError(f"unsupported restoration projection: {self.projection_kind}")
        if self.kind in {"autocomplete_query", "editable_field_assignment"}:
            if self.expected_value is None or self.prior_value is None:
                raise ValueError("field transaction requires expected and prior values")
        if self.kind == "native_select_update" and not self.expected_options:
            raise ValueError("native selection transaction requires expected options")
        if self.kind == "calendar_month_shift":
            if (
                self.prior_calendar is None
                or self.expected_calendar is None
                or self.dynamic_inverse_class_token
                not in {"ui-datepicker-prev", "ui-datepicker-next"}
            ):
                raise ValueError("calendar shift requires contexts and a public inverse")
            if self.inverse_actions:
                raise ValueError("calendar shift inverse must be dynamically recompiled")
        if self.maximum_interrupt_repairs < 0 or self.maximum_interrupt_repairs > 1:
            raise ValueError("interrupt repair budget must be zero or one")
        if set(self.dynamic_compensator_labels) - COMPENSATOR_LABELS:
            raise ValueError("transaction contains an unsafe compensator label")


@dataclass(frozen=True)
class TransactionDecisionV4:
    allowed: bool
    contract: TransactionContractV4 | None
    reason: str


def infer_transaction_contract(
    snapshot: SemanticSnapshot,
    action_bid: str,
    goal: StructuredGoalContract,
) -> TransactionDecisionV4:
    """Infer a grounded reversible transaction from public state and goal spans."""

    element = snapshot.get(action_bid)
    if element is None or not snapshot.is_effectively_visible(action_bid):
        return TransactionDecisionV4(False, None, "action element is absent or invisible")

    selection = goal.selection_for_bid(action_bid)
    if selection is not None and (
        element.dom_tag.casefold() == "select" or element.role.casefold() == "listbox"
    ):
        prior = public_selected_values(snapshot, action_bid)
        return TransactionDecisionV4(
            True,
            TransactionContractV4(
                kind="native_select_update",
                semantic_bid=action_bid,
                action=ContractActionV4("select_option", action_bid, selection.values),
                inverse_actions=(
                    ContractActionV4("select_option", action_bid, prior),
                ),
                expected_options=tuple(sorted(selection.values)),
                prior_options=prior,
                projection_kind="native_select_update",
            ),
            "public native options uniquely resolve the goal selection",
        )

    if goal.date_anchor is not None:
        direction = None
        if "ui-datepicker-prev" in element.class_tokens:
            direction = -1
        elif "ui-datepicker-next" in element.class_tokens:
            direction = 1
        if direction is not None:
            current_context = public_calendar_context(snapshot)
            target_index = goal.date_anchor.year * 12 + goal.date_anchor.month
            current_index = (
                current_context[1] * 12 + current_context[0]
                if current_context is not None
                else target_index
            )
            desired_direction = (
                -1 if target_index < current_index else 1 if target_index > current_index else 0
            )
            disabled = "ui-state-disabled" in element.class_tokens or not element.clickable
            fields = [
                row
                for row in snapshot.elements
                if "hasdatepicker" in row.class_tokens
                and snapshot.is_effectively_visible(row.bid)
            ]
            if (
                current_context is not None
                and direction == desired_direction
                and not disabled
                and len(fields) == 1
            ):
                inverse = (
                    "ui-datepicker-next"
                    if direction < 0
                    else "ui-datepicker-prev"
                )
                return TransactionDecisionV4(
                    True,
                    TransactionContractV4(
                        kind="calendar_month_shift",
                        semantic_bid=fields[0].bid,
                        action=ContractActionV4("click", action_bid),
                        inverse_actions=(),
                        projection_kind="calendar_month_shift",
                        prior_calendar=current_context,
                        expected_calendar=_shift_month(
                            current_context[0], current_context[1], direction
                        ),
                        dynamic_inverse_class_token=inverse,
                    ),
                    "public calendar navigation moves one month toward the goal date",
                )

    assignment = goal.assignment_for_bid(action_bid)
    if assignment is not None and _is_editable(snapshot, action_bid):
        prior = _public_value(snapshot, action_bid)
        if is_public_autocomplete(snapshot, action_bid):
            return TransactionDecisionV4(
                True,
                TransactionContractV4(
                    kind="autocomplete_query",
                    semantic_bid=action_bid,
                    action=ContractActionV4(
                        "fill", action_bid, assignment.value, True
                    ),
                    inverse_actions=(
                        ContractActionV4("press", action_bid, "Escape"),
                        ContractActionV4("fill", action_bid, prior, False),
                    ),
                    expected_value=assignment.value,
                    prior_value=prior,
                    projection_kind="autocomplete_query",
                ),
                "public autocomplete field is bound to a goal-span assignment",
            )
        return TransactionDecisionV4(
            True,
            TransactionContractV4(
                kind="editable_field_assignment",
                semantic_bid=action_bid,
                action=ContractActionV4("fill", action_bid, assignment.value, False),
                inverse_actions=(
                    ContractActionV4("fill", action_bid, prior, False),
                ),
                expected_value=assignment.value,
                prior_value=prior,
                projection_kind="editable_field_assignment",
                dynamic_compensator_labels=tuple(sorted(COMPENSATOR_LABELS)),
                maximum_interrupt_repairs=1,
            ),
            "editable public field is bound to a goal-span assignment",
        )

    if is_public_autocomplete(snapshot, action_bid) and goal.exact_constraint is not None:
        query = exploration_query(goal.exact_constraint)
        if query:
            prior = _public_value(snapshot, action_bid)
            return TransactionDecisionV4(
                True,
                TransactionContractV4(
                    kind="autocomplete_query",
                    semantic_bid=action_bid,
                    action=ContractActionV4("fill", action_bid, query, True),
                    inverse_actions=(
                        ContractActionV4("press", action_bid, "Escape"),
                        ContractActionV4("fill", action_bid, prior, False),
                    ),
                    expected_value=query,
                    prior_value=prior,
                    projection_kind="autocomplete_query",
                ),
                "public autocomplete field is bound to a positive goal query",
            )

    if (
        is_public_datepicker(snapshot, action_bid)
        and goal.date_anchor is not None
        and not _visible_surface_projection(snapshot, _is_calendar_surface)
        and _normalized(_public_value(snapshot, action_bid))
        != _normalized(goal.date_anchor.canonical)
    ):
        return TransactionDecisionV4(
            True,
            TransactionContractV4(
                kind="datepicker_open",
                semantic_bid=action_bid,
                action=ContractActionV4("click", action_bid),
                inverse_actions=(ContractActionV4("press", action_bid, "Escape"),),
                expected_value=goal.date_anchor.canonical,
                prior_value=_public_value(snapshot, action_bid),
                projection_kind="datepicker_open",
            ),
            "readonly public date-picker field is bound to an explicit date span",
        )

    query = (
        exploration_query(goal.exact_constraint)
        if goal.exact_constraint is not None
        else None
    )
    legacy = infer_sequence_contract(snapshot, action_bid, query=query)
    if legacy.allowed and legacy.contract is not None:
        contract = legacy.contract
        return TransactionDecisionV4(
            True,
            TransactionContractV4(
                kind=contract.kind,
                semantic_bid=contract.semantic_bid,
                action=_v4_action(contract.action),
                inverse_actions=tuple(_v4_action(row) for row in contract.inverse_actions),
                projection_kind="global",
                legacy_contract=contract,
            ),
            legacy.reason,
        )

    return TransactionDecisionV4(
        False,
        None,
        "no goal-grounded public semantic type with a certified inverse",
    )


def _field_projection(snapshot: SemanticSnapshot, bid: str) -> tuple[object, ...]:
    element = snapshot.get(bid)
    if element is None:
        return ("absent", bid)
    return (
        "field",
        element.role.casefold(),
        element.dom_tag.casefold(),
        _public_value(snapshot, bid),
        _public_boolean(snapshot, bid, "readonly"),
        _public_boolean(snapshot, bid, "disabled"),
        snapshot.is_effectively_visible(bid),
    )


def _form_projection(snapshot: SemanticSnapshot) -> tuple[tuple[object, ...], ...]:
    rows = []
    for element in snapshot.elements:
        role = element.role.casefold()
        if not snapshot.is_effectively_visible(element.bid):
            continue
        if role not in FORM_CONTROL_ROLES and element.dom_tag.casefold() != "select":
            continue
        rows.append(
            (
                element.bid,
                role,
                element.dom_tag.casefold(),
                _public_value(snapshot, element.bid),
                _public_boolean(snapshot, element.bid, "disabled"),
                _public_boolean(snapshot, element.bid, "readonly"),
                _normalized(element.ax_property("checked")),
            )
        )
    compensators = tuple(
        sorted(
            (element.role.casefold(), _normalized(element.name))
            for element in snapshot.elements
            if snapshot.is_effectively_visible(element.bid)
            and _normalized(element.name) in COMPENSATOR_LABELS
            and element.role.casefold() in {"button", "link", "menuitem"}
        )
    )
    return tuple(sorted(rows)) + (("compensators", compensators),)


def contract_projection(
    snapshot: SemanticSnapshot,
    contract: TransactionContractV4,
) -> tuple[object, ...]:
    """Return the immutable public state footprint declared by a contract."""

    if contract.projection_kind == "global":
        return ("global", snapshot.semantic_fingerprint())
    if contract.projection_kind == "autocomplete_query":
        surfaces = _visible_surface_projection(snapshot, _is_suggestion_surface)
        return ("autocomplete_query", _field_projection(snapshot, contract.semantic_bid), surfaces)
    if contract.projection_kind == "datepicker_open":
        surfaces = _visible_surface_projection(snapshot, _is_calendar_surface)
        return ("datepicker_open", _field_projection(snapshot, contract.semantic_bid), surfaces)
    if contract.projection_kind == "editable_field_assignment":
        return ("editable_field_assignment", _form_projection(snapshot))
    if contract.projection_kind == "native_select_update":
        element = snapshot.get(contract.semantic_bid)
        descendants = () if element is None else tuple(
            sorted(
                (
                    row.dom_attribute("value", ""),
                    _normalized(row.ax_property("selected")) == "true"
                    or row.dom_attribute("selected") is not None,
                )
                for row in snapshot.descendants(contract.semantic_bid, relation="dom")
                if row.dom_tag.casefold() == "option"
            )
        )
        return (
            "native_select_update",
            _field_projection(snapshot, contract.semantic_bid),
            descendants,
        )
    if contract.projection_kind == "calendar_month_shift":
        return (
            "calendar_month_shift",
            _field_projection(snapshot, contract.semantic_bid),
            public_calendar_context(snapshot),
            bool(_visible_surface_projection(snapshot, _is_calendar_surface)),
        )
    raise ValueError(f"unsupported contract projection: {contract.projection_kind}")


def check_transaction_postcondition(
    before: SemanticSnapshot,
    after: SemanticSnapshot,
    contract: TransactionContractV4,
) -> ContractCheck:
    delta = semantic_delta(before, after)
    if contract.kind == "autocomplete_query":
        value_matches = _public_value(after, contract.semantic_bid) == contract.expected_value
        before_surfaces = _visible_surface_projection(before, _is_suggestion_surface)
        after_surfaces = _visible_surface_projection(after, _is_suggestion_surface)
        surface_added = bool(after_surfaces) and after_surfaces != before_surfaces
        passed = value_matches and surface_added
        return ContractCheck(
            passed,
            (
                "query value and public suggestion surface appeared"
                if passed
                else "query value or public suggestion-surface postcondition failed"
            ),
            delta,
        )
    if contract.kind == "datepicker_open":
        before_surfaces = _visible_surface_projection(before, _is_calendar_surface)
        after_surfaces = _visible_surface_projection(after, _is_calendar_surface)
        passed = bool(after_surfaces) and after_surfaces != before_surfaces
        return ContractCheck(
            passed,
            "public calendar surface appeared" if passed else "calendar surface did not appear",
            delta,
        )
    if contract.kind == "editable_field_assignment":
        passed = _public_value(after, contract.semantic_bid) == contract.expected_value
        return ContractCheck(
            passed,
            "public field value matches the goal assignment"
            if passed
            else "public field value does not match the goal assignment",
            delta,
        )
    if contract.kind == "native_select_update":
        passed = public_selected_values(after, contract.semantic_bid) == contract.expected_options
        return ContractCheck(
            passed,
            "public selected option set matches the goal"
            if passed
            else "public selected option set does not match the goal",
            delta,
        )
    if contract.kind == "calendar_month_shift":
        passed = public_calendar_context(after) == contract.expected_calendar
        return ContractCheck(
            passed,
            "public calendar moved exactly one month toward the goal"
            if passed
            else "public calendar month-shift postcondition failed",
            delta,
        )
    if contract.legacy_contract is None:
        raise ValueError(f"unsupported transaction contract kind: {contract.kind}")
    return check_sequence_postcondition(before, after, contract.legacy_contract)


def check_transaction_restoration(
    before: SemanticSnapshot,
    restored: SemanticSnapshot,
    contract: TransactionContractV4,
) -> ContractCheck:
    delta = semantic_delta(before, restored)
    passed = contract_projection(before, contract) == contract_projection(
        restored, contract
    )
    qualifier = "global semantic" if contract.projection_kind == "global" else "contract-footprint"
    return ContractCheck(
        passed,
        f"{qualifier} state restored" if passed else f"{qualifier} state differs",
        delta,
    )


def synthesize_public_compensator(
    before: SemanticSnapshot,
    after: SemanticSnapshot,
    contract: TransactionContractV4,
) -> ContractActionV4 | None:
    """Return one newly visible abort control, failing closed on ambiguity."""

    candidates = public_compensator_bids(before, after, contract)
    return (
        ContractActionV4("click", candidates[0])
        if len(candidates) == 1
        else None
    )


def public_compensator_bids(
    before: SemanticSnapshot,
    after: SemanticSnapshot,
    contract: TransactionContractV4,
) -> tuple[str, ...]:
    """Enumerate newly visible public abort controls for audit and gating."""

    allowed = set(contract.dynamic_compensator_labels)
    if not allowed:
        return ()
    candidates = []
    for element in after.elements:
        if not after.is_effectively_visible(element.bid):
            continue
        if element.role.casefold() not in {"button", "link", "menuitem"}:
            continue
        if _normalized(element.name) not in allowed:
            continue
        was_visible = before.get(element.bid) is not None and before.is_effectively_visible(
            element.bid
        )
        if was_visible:
            continue
        if not element.clickable and element.role.casefold() not in {"button", "link", "menuitem"}:
            continue
        candidates.append(element.bid)
    return tuple(sorted(candidates))
