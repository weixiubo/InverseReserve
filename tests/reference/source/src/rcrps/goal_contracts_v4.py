"""Structured public goal contracts for successor PACT experiments.

The compiler binds action arguments to exact spans in the user instruction and
to controls in a public semantic snapshot.  It never receives a task ID,
evaluator state, reward, or source-generated target.
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass
from typing import Iterable

from .pact_grounding_v3 import TargetConstraint, compile_target_constraint
from .typed_observation import SemanticElement, SemanticSnapshot


TEXT_INPUT_ROLES = frozenset({"combobox", "searchbox", "textbox"})
DIRECT_PUBLIC_ROLES = frozenset(
    {
        "button",
        "checkbox",
        "combobox",
        "link",
        "radio",
        "searchbox",
        "slider",
        "spinbutton",
        "switch",
        "tab",
        "textbox",
    }
)
DATE_PATTERN = re.compile(
    r"(?<!\d)(?P<month>0?[1-9]|1[0-2])/"
    r"(?P<day>0?[1-9]|[12]\d|3[01])/"
    r"(?P<year>19\d{2}|20\d{2})(?!\d)"
)


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", str(value)).strip().casefold()


def _clean_label(value: str) -> str:
    return re.sub(r"\s+", " ", str(value)).strip().rstrip(":").strip()


@dataclass(frozen=True)
class GoalSpan:
    text: str
    start: int
    end: int

    def __post_init__(self) -> None:
        if self.start < 0 or self.end <= self.start:
            raise ValueError("goal span offsets must identify nonempty text")
        if len(self.text) != self.end - self.start:
            raise ValueError("goal span text and offsets disagree")

    def record(self) -> dict[str, object]:
        return {"text": self.text, "start": self.start, "end": self.end}


@dataclass(frozen=True)
class FieldAssignment:
    bid: str
    label: str
    value: str
    label_span: GoalSpan
    value_span: GoalSpan

    def record(self) -> dict[str, object]:
        return {
            "bid": self.bid,
            "label": self.label,
            "value": self.value,
            "label_span": self.label_span.record(),
            "value_span": self.value_span.record(),
        }


@dataclass(frozen=True)
class DateAnchor:
    text: str
    month: int
    day: int
    year: int
    span: GoalSpan

    @property
    def canonical(self) -> str:
        return f"{self.month:02d}/{self.day:02d}/{self.year:04d}"

    def record(self) -> dict[str, object]:
        return {
            "text": self.text,
            "canonical": self.canonical,
            "month": self.month,
            "day": self.day,
            "year": self.year,
            "span": self.span.record(),
        }


@dataclass(frozen=True)
class OptionSelection:
    bid: str
    values: tuple[str, ...]
    phrase_span: GoalSpan

    def __post_init__(self) -> None:
        if not self.values or any(not value.strip() for value in self.values):
            raise ValueError("option selection requires nonempty values")

    def record(self) -> dict[str, object]:
        return {
            "bid": self.bid,
            "values": list(self.values),
            "phrase_span": self.phrase_span.record(),
        }


@dataclass(frozen=True)
class RoleAnchor:
    role: str
    span: GoalSpan

    def __post_init__(self) -> None:
        if self.role not in DIRECT_PUBLIC_ROLES:
            raise ValueError(f"unsupported direct public role: {self.role}")

    def record(self) -> dict[str, object]:
        return {"role": self.role, "span": self.span.record()}


@dataclass(frozen=True)
class TerminalIntent:
    requested_label: str
    span: GoalSpan

    def record(self) -> dict[str, object]:
        return {
            "requested_label": self.requested_label,
            "span": self.span.record(),
        }


@dataclass(frozen=True)
class ObjectiveAnchor:
    kind: str
    span: GoalSpan

    def __post_init__(self) -> None:
        if self.kind not in {"min_cost", "min_duration"}:
            raise ValueError(f"unsupported comparative objective: {self.kind}")

    def record(self) -> dict[str, object]:
        return {"kind": self.kind, "span": self.span.record()}


@dataclass(frozen=True)
class StructuredGoalContract:
    goal: str
    exact_constraint: TargetConstraint | None
    field_assignments: tuple[FieldAssignment, ...]
    date_anchor: DateAnchor | None
    option_selections: tuple[OptionSelection, ...]
    role_anchor: RoleAnchor | None
    terminal_intent: TerminalIntent | None
    objective_anchor: ObjectiveAnchor | None
    rejected_reasons: tuple[str, ...] = ()

    @property
    def allowed(self) -> bool:
        return bool(
            self.exact_constraint
            or self.field_assignments
            or self.date_anchor
            or self.option_selections
            or self.role_anchor
            or self.objective_anchor
        )

    def assignment_for_bid(self, bid: str) -> FieldAssignment | None:
        rows = [row for row in self.field_assignments if row.bid == bid]
        return rows[0] if len(rows) == 1 else None

    def selection_for_bid(self, bid: str) -> OptionSelection | None:
        rows = [row for row in self.option_selections if row.bid == bid]
        return rows[0] if len(rows) == 1 else None

    def validate_provenance(self) -> None:
        spans: list[GoalSpan] = []
        for row in self.field_assignments:
            spans.extend((row.label_span, row.value_span))
        if self.date_anchor is not None:
            spans.append(self.date_anchor.span)
        for row in self.option_selections:
            spans.append(row.phrase_span)
        if self.role_anchor is not None:
            spans.append(self.role_anchor.span)
        if self.terminal_intent is not None:
            spans.append(self.terminal_intent.span)
        if self.objective_anchor is not None:
            spans.append(self.objective_anchor.span)
        for span in spans:
            if self.goal[span.start : span.end] != span.text:
                raise ValueError("goal anchor is not verbatim provenance")

    def record(self) -> dict[str, object]:
        self.validate_provenance()
        return {
            "goal": self.goal,
            "allowed": self.allowed,
            "exact_constraint": (
                self.exact_constraint.record()
                if self.exact_constraint is not None
                else None
            ),
            "field_assignments": [row.record() for row in self.field_assignments],
            "date_anchor": (
                self.date_anchor.record() if self.date_anchor is not None else None
            ),
            "option_selections": [row.record() for row in self.option_selections],
            "role_anchor": (
                self.role_anchor.record() if self.role_anchor is not None else None
            ),
            "terminal_intent": (
                self.terminal_intent.record()
                if self.terminal_intent is not None
                else None
            ),
            "objective_anchor": (
                self.objective_anchor.record()
                if self.objective_anchor is not None
                else None
            ),
            "rejected_reasons": list(self.rejected_reasons),
        }


def _public_control_label(
    snapshot: SemanticSnapshot,
    element: SemanticElement,
) -> str:
    values = [element.name, element.subtree_text]
    for relation in ("ax", "dom"):
        for ancestor in snapshot.ancestors(element.bid, relation=relation):
            values.extend((ancestor.name, ancestor.subtree_text))
    for value in values:
        label = _clean_label(value)
        if label:
            return label
    placeholder = _clean_label(element.dom_attribute("placeholder", ""))
    return placeholder


def _is_editable(element: SemanticElement) -> bool:
    if element.role.casefold() not in TEXT_INPUT_ROLES:
        return False
    if element.dom_tag.casefold() not in {"input", "textarea"}:
        return False
    readonly = (
        element.ax_property("readonly") is True
        or element.dom_attribute("readonly") is not None
        or _normalize(element.dom_attribute("aria-readonly", "")) == "true"
    )
    disabled = (
        element.ax_property("disabled") is True
        or element.dom_attribute("disabled") is not None
        or _normalize(element.dom_attribute("aria-disabled", "")) == "true"
    )
    return not readonly and not disabled


def _span(goal: str, start: int, end: int) -> GoalSpan:
    return GoalSpan(goal[start:end], start, end)


def _quoted_assignment(
    goal: str,
    label: str,
) -> tuple[GoalSpan, GoalSpan] | None:
    escaped = re.escape(label)
    pattern = re.compile(
        rf"(?<![\w])(?P<label>{escaped})(?![\w])\s*[\"“]"
        rf"(?P<value>[^\"”]+)[\"”]",
        flags=re.IGNORECASE,
    )
    matches = list(pattern.finditer(goal))
    if len(matches) != 1:
        return None
    match = matches[0]
    return (
        _span(goal, match.start("label"), match.end("label")),
        _span(goal, match.start("value"), match.end("value")),
    )


def _colon_assignment(
    goal: str,
    label: str,
    all_labels: Iterable[str],
) -> tuple[GoalSpan, GoalSpan] | None:
    escaped = re.escape(label)
    pattern = re.compile(
        rf"(?<![\w])(?P<label>{escaped})(?![\w])\s*:\s*",
        flags=re.IGNORECASE,
    )
    matches = list(pattern.finditer(goal))
    if len(matches) != 1:
        return None
    match = matches[0]
    start = match.end()
    stops = [len(goal)]
    for other in all_labels:
        if _normalize(other) == _normalize(label):
            continue
        other_match = re.search(
            rf"(?<![\w]){re.escape(other)}(?![\w])\s*:",
            goal[start:],
            flags=re.IGNORECASE,
        )
        if other_match:
            stops.append(start + other_match.start())
    date_tail = re.search(r"\s+on\s+" + DATE_PATTERN.pattern, goal[start:])
    if date_tail:
        stops.append(start + date_tail.start())
    terminal_tail = re.search(
        r"\s+(?:and\s+then\s+|and\s+|then\s+)"
        r"(?:click|press|hit|submit|choose|select)\b",
        goal[start:],
        flags=re.IGNORECASE,
    )
    if terminal_tail:
        stops.append(start + terminal_tail.start())
    end = min(stops)
    while end > start and goal[end - 1] in " .;":
        end -= 1
    while start < end and goal[start].isspace():
        start += 1
    if start >= end:
        return None
    return (
        _span(goal, match.start("label"), match.end("label")),
        _span(goal, start, end),
    )


def _compile_field_assignments(
    goal: str,
    snapshot: SemanticSnapshot,
) -> tuple[tuple[FieldAssignment, ...], tuple[str, ...]]:
    controls = [
        element
        for element in snapshot.elements
        if snapshot.is_effectively_visible(element.bid) and _is_editable(element)
    ]
    labeled = [(element, _public_control_label(snapshot, element)) for element in controls]
    labeled = [(element, label) for element, label in labeled if label]
    label_counts: dict[str, int] = {}
    for _element, label in labeled:
        key = _normalize(label)
        label_counts[key] = label_counts.get(key, 0) + 1
    unique = [
        (element, label)
        for element, label in labeled
        if label_counts[_normalize(label)] == 1
    ]
    labels = tuple(label for _element, label in unique)
    rows = []
    rejected = []
    for element, label in unique:
        pair = _quoted_assignment(goal, label)
        if pair is None:
            pair = _colon_assignment(goal, label, labels)
        if pair is None:
            continue
        label_span, value_span = pair
        value = value_span.text.strip()
        if not value or len(value) > 512:
            rejected.append(f"field {label!r} has an empty or oversized value")
            continue
        rows.append(
            FieldAssignment(
                bid=element.bid,
                label=label,
                value=value,
                label_span=label_span,
                value_span=value_span,
            )
        )
    return tuple(sorted(rows, key=lambda row: row.bid)), tuple(rejected)


def _compile_date(goal: str) -> tuple[DateAnchor | None, str | None]:
    matches = list(DATE_PATTERN.finditer(goal))
    if len(matches) != 1:
        return None, ("instruction contains ambiguous dates" if matches else None)
    match = matches[0]
    month = int(match.group("month"))
    day = int(match.group("day"))
    year = int(match.group("year"))
    try:
        dt.date(year, month, day)
    except ValueError:
        return None, "instruction contains an invalid calendar date"
    span = _span(goal, match.start(), match.end())
    return DateAnchor(span.text, month, day, year, span), None


def _option_values(
    snapshot: SemanticSnapshot,
    listbox: SemanticElement,
) -> tuple[str, ...]:
    values = []
    for element in snapshot.descendants(listbox.bid, relation="dom"):
        if element.dom_tag.casefold() != "option":
            continue
        value = str(element.dom_attribute("value", "")).strip()
        if value and value not in values:
            values.append(value)
    return tuple(values)


def _resolve_option_phrase(
    phrase: str,
    options: tuple[str, ...],
) -> tuple[str, ...] | None:
    normalized_phrase = _normalize(phrase)
    normalized_options = [(value, _normalize(value)) for value in options]
    solutions: set[tuple[str, ...]] = set()

    def visit(position: int, chosen: tuple[str, ...]) -> None:
        while position < len(normalized_phrase) and normalized_phrase[position].isspace():
            position += 1
        if position == len(normalized_phrase):
            if chosen:
                solutions.add(chosen)
            return
        for original, normalized in normalized_options:
            if original in chosen:
                continue
            if not normalized_phrase.startswith(normalized, position):
                continue
            end = position + len(normalized)
            if end == len(normalized_phrase):
                visit(end, chosen + (original,))
                continue
            comma = re.match(r"\s*,\s*", normalized_phrase[end:])
            if comma:
                visit(end + comma.end(), chosen + (original,))

    visit(0, ())
    return next(iter(solutions)) if len(solutions) == 1 else None


def _selection_phrase(goal: str) -> GoalSpan | None:
    pattern = re.compile(
        r"\bselect\s+(?P<phrase>.+?)\s+from\s+(?:the\s+)?"
        r"[^.;]{0,80}?\b(?:list|listbox|select|dropdown)\b",
        flags=re.IGNORECASE,
    )
    matches = list(pattern.finditer(goal))
    if len(matches) != 1:
        return None
    match = matches[0]
    start, end = match.span("phrase")
    while start < end and goal[start].isspace():
        start += 1
    while end > start and goal[end - 1].isspace():
        end -= 1
    return _span(goal, start, end) if start < end else None


def _compile_option_selections(
    goal: str,
    snapshot: SemanticSnapshot,
) -> tuple[tuple[OptionSelection, ...], tuple[str, ...]]:
    phrase = _selection_phrase(goal)
    if phrase is None:
        return (), ()
    rows = []
    for element in snapshot.elements:
        is_listbox = (
            element.dom_tag.casefold() == "select"
            or element.role.casefold() == "listbox"
        )
        if not is_listbox:
            continue
        values = _option_values(snapshot, element)
        resolved = _resolve_option_phrase(phrase.text, values)
        if resolved is not None:
            rows.append(OptionSelection(element.bid, resolved, phrase))
    if len(rows) == 1:
        return (rows[0],), ()
    reason = (
        "option phrase does not resolve to one public listbox"
        if not rows
        else "option phrase resolves to multiple public listboxes"
    )
    return (), (reason,)


def _compile_role_anchor(goal: str) -> tuple[RoleAnchor | None, str | None]:
    roles = "|".join(sorted(DIRECT_PUBLIC_ROLES, key=len, reverse=True))
    pattern = re.compile(
        rf"\b(?:click|press|activate)\s+(?:on\s+)?(?:a|an|the)?\s*"
        rf"[\"“](?P<role>{roles})[\"”]\s+(?:widget|control)\b",
        flags=re.IGNORECASE,
    )
    matches = list(pattern.finditer(goal))
    if len(matches) != 1:
        return None, ("instruction contains ambiguous public roles" if matches else None)
    match = matches[0]
    start, end = match.span("role")
    return RoleAnchor(_normalize(match.group("role")), _span(goal, start, end)), None


def _compile_terminal_intent(
    goal: str,
) -> tuple[TerminalIntent | None, str | None]:
    labels = "apply|continue|done|login|ok|save|search|submit"
    pattern = re.compile(
        rf"\b(?:click|press|hit|activate)\s+(?:the\s+)?"
        rf"(?P<label>{labels})(?:\s+button)?\b",
        flags=re.IGNORECASE,
    )
    matches = list(pattern.finditer(goal))
    if len(matches) != 1:
        return None, ("instruction contains ambiguous terminal intents" if matches else None)
    match = matches[0]
    start, end = match.span("label")
    return TerminalIntent(_normalize(match.group("label")), _span(goal, start, end)), None


def _compile_objective(
    goal: str,
) -> tuple[ObjectiveAnchor | None, str | None]:
    patterns = {
        "min_cost": re.compile(r"\bcheapest\b", flags=re.IGNORECASE),
        "min_duration": re.compile(r"\bshortest\b", flags=re.IGNORECASE),
    }
    matches = [
        (kind, match)
        for kind, pattern in patterns.items()
        for match in pattern.finditer(goal)
    ]
    if len(matches) != 1:
        return None, ("instruction contains ambiguous comparative objectives" if matches else None)
    kind, match = matches[0]
    return ObjectiveAnchor(kind, _span(goal, match.start(), match.end())), None


def compile_structured_goal(
    goal: str,
    snapshot: SemanticSnapshot,
) -> StructuredGoalContract:
    """Compile public goal anchors with exact text provenance."""

    goal = str(goal).strip()
    exact_result = compile_target_constraint(goal)
    exact = exact_result.constraint if exact_result.allowed else None
    fields, field_rejections = _compile_field_assignments(goal, snapshot)
    date_anchor, date_rejection = _compile_date(goal)
    selections, selection_rejections = _compile_option_selections(goal, snapshot)
    role_anchor, role_rejection = _compile_role_anchor(goal)
    terminal_intent, terminal_rejection = _compile_terminal_intent(goal)
    objective_anchor, objective_rejection = _compile_objective(goal)
    rejected = list(field_rejections) + list(selection_rejections)
    if date_rejection:
        rejected.append(date_rejection)
    if role_rejection:
        rejected.append(role_rejection)
    if terminal_rejection:
        rejected.append(terminal_rejection)
    if objective_rejection:
        rejected.append(objective_rejection)
    contract = StructuredGoalContract(
        goal=goal,
        exact_constraint=exact,
        field_assignments=fields,
        date_anchor=date_anchor,
        option_selections=selections,
        role_anchor=role_anchor,
        terminal_intent=terminal_intent,
        objective_anchor=objective_anchor,
        rejected_reasons=tuple(rejected),
    )
    contract.validate_provenance()
    return contract
