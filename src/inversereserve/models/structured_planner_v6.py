"""Standard HTML widget-kind inventory for PACT v6 direct controls."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from inversereserve.contracts.goal_contracts_v4 import (
    GoalSpan,
    StructuredGoalContract,
    compile_structured_goal,
)
from inversereserve.contracts.transaction_actions_v4 import ContractActionV4
from inversereserve.models.structured_planner_v4 import ActionCandidateV4, V4ActionInventory
from inversereserve.models.structured_planner_v4 import compile_v4_inventory as _compile_v4_inventory
from inversereserve.observations.typed_observation import SemanticElement, SemanticSnapshot

STANDARD_WIDGET_KINDS = frozenset({"button", "checkbox", "radio", "text", "textarea"})


@dataclass(frozen=True)
class WidgetKindAnchorV6:
    kind: str
    span: GoalSpan
    existential: bool = True

    def __post_init__(self) -> None:
        if self.kind not in STANDARD_WIDGET_KINDS:
            raise ValueError(f"unsupported standard widget kind: {self.kind}")
        if not self.existential:
            raise ValueError("v6 widget-kind anchors must be explicitly existential")

    def record(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "span": self.span.record(),
            "existential": self.existential,
        }


@dataclass(frozen=True)
class StructuredGoalContractV6:
    base: StructuredGoalContract
    widget_kind_anchor: WidgetKindAnchorV6 | None

    @property
    def goal(self) -> str:
        return self.base.goal

    @property
    def exact_constraint(self) -> Any:
        return self.base.exact_constraint

    @property
    def field_assignments(self) -> Any:
        return self.base.field_assignments

    @property
    def date_anchor(self) -> Any:
        return self.base.date_anchor

    @property
    def option_selections(self) -> Any:
        return self.base.option_selections

    @property
    def role_anchor(self) -> Any:
        return self.base.role_anchor

    @property
    def terminal_intent(self) -> Any:
        return self.base.terminal_intent

    @property
    def objective_anchor(self) -> Any:
        return self.base.objective_anchor

    @property
    def rejected_reasons(self) -> Any:
        return self.base.rejected_reasons

    @property
    def allowed(self) -> bool:
        return self.base.allowed or self.widget_kind_anchor is not None

    def assignment_for_bid(self, bid: str) -> Any:
        return self.base.assignment_for_bid(bid)

    def selection_for_bid(self, bid: str) -> Any:
        return self.base.selection_for_bid(bid)

    def validate_provenance(self) -> None:
        self.base.validate_provenance()
        if self.widget_kind_anchor is not None:
            span = self.widget_kind_anchor.span
            if self.goal[span.start : span.end] != span.text:
                raise ValueError("widget-kind anchor is not verbatim provenance")

    def record(self) -> dict[str, object]:
        self.validate_provenance()
        record = self.base.record()
        record["allowed"] = self.allowed
        record["widget_kind_anchor"] = (
            self.widget_kind_anchor.record() if self.widget_kind_anchor is not None else None
        )
        return record


def compile_widget_kind_anchor_v6(goal: str) -> WidgetKindAnchorV6 | None:
    kinds = "|".join(sorted(STANDARD_WIDGET_KINDS, key=len, reverse=True))
    pattern = re.compile(
        rf"\b(?:click|press|activate)\s+(?:on\s+)?(?:a|an)\s*"
        rf"[\"“](?P<kind>{kinds})[\"”]\s+(?:widget|control)\b",
        flags=re.IGNORECASE,
    )
    matches = list(pattern.finditer(goal))
    if len(matches) != 1:
        return None
    match = matches[0]
    start, end = match.span("kind")
    return WidgetKindAnchorV6(
        match.group("kind").casefold(),
        GoalSpan(goal[start:end], start, end),
    )


def element_matches_widget_kind_v6(
    element: SemanticElement,
    kind: str,
) -> bool:
    tag = element.dom_tag.casefold()
    role = element.role.casefold()
    input_type = str(element.dom_attribute("type", "")).strip().casefold()
    if kind == "button":
        return tag == "button" and role == "button"
    if kind == "checkbox":
        return tag == "input" and input_type == "checkbox" and role == "checkbox"
    if kind == "radio":
        return tag == "input" and input_type == "radio" and role == "radio"
    if kind == "textarea":
        return tag == "textarea" and role == "textbox"
    if kind == "text":
        return bool(tag == "input" and role == "textbox" and input_type in {"", "input", "text"})
    raise ValueError(f"unsupported standard widget kind: {kind}")


def _state(element: SemanticElement) -> tuple[tuple[str, Any], ...]:
    keep = {"checked", "disabled", "selected", "value"}
    return tuple((name, value) for name, value in element.ax_properties if name in keep)


def _label(snapshot: SemanticSnapshot, element: SemanticElement) -> str:
    for value in (element.name, element.subtree_text):
        if str(value).strip():
            return " ".join(str(value).split())
    for relation in ("ax", "dom"):
        for ancestor in snapshot.ancestors(element.bid, relation=relation):
            for value in (ancestor.name, ancestor.subtree_text):
                if str(value).strip():
                    return " ".join(str(value).split())
    return ""


def compile_v6_inventory(
    snapshot: SemanticSnapshot,
    goal: str,
    *,
    goal_contract: StructuredGoalContractV6 | StructuredGoalContract | None = None,
) -> V4ActionInventory:
    """Add only standard public widget leaves to the frozen v4 inventory."""

    if goal_contract is None:
        base_goal = compile_structured_goal(goal, snapshot)
        wrapped = StructuredGoalContractV6(
            base_goal,
            compile_widget_kind_anchor_v6(base_goal.goal),
        )
    elif isinstance(goal_contract, StructuredGoalContractV6):
        wrapped = goal_contract
        base_goal = wrapped.base
        if wrapped.goal != str(goal).strip():
            raise ValueError("persisted v6 goal contract does not match instruction")
    else:
        base_goal = goal_contract
        wrapped = StructuredGoalContractV6(
            base_goal,
            compile_widget_kind_anchor_v6(base_goal.goal),
        )
    wrapped.validate_provenance()
    base_inventory = _compile_v4_inventory(
        snapshot,
        goal,
        goal_contract=base_goal,
    )
    anchor = wrapped.widget_kind_anchor
    if anchor is None:
        return base_inventory

    rows = {row.bid: row for row in base_inventory.candidates}
    for element in snapshot.elements:
        if not snapshot.is_effectively_visible(element.bid):
            continue
        if not element_matches_widget_kind_v6(element, anchor.kind):
            continue
        state = dict(_state(element))
        state["standard_widget_kind"] = anchor.kind
        rows[element.bid] = ActionCandidateV4(
            bid=element.bid,
            action=ContractActionV4("click", element.bid),
            role=element.role or element.dom_tag,
            label=_label(snapshot, element),
            state=tuple(sorted(state.items())),
            transaction_kind=None,
            semantic_bid=element.bid,
            parent_bid=element.ax_parent_bid or element.dom_parent_bid,
        )
    candidates = tuple(
        sorted(
            rows.values(),
            key=lambda row: (
                row.parent_bid or "",
                row.semantic_bid,
                row.bid,
                row.action.operation,
            ),
        )
    )
    return V4ActionInventory(
        wrapped.allowed,
        f"public goal exposed {sum(element_matches_widget_kind_v6(row, anchor.kind) for row in snapshot.elements)} standard {anchor.kind} leaves",
        wrapped,
        candidates,
        base_inventory.contracts,
    )
