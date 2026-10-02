"""Structured goal and action inventory for PACT v4."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from inversereserve.contracts.goal_contracts_v4 import StructuredGoalContract, compile_structured_goal
from inversereserve.contracts.transaction_actions_v4 import ContractActionV4
from inversereserve.contracts.typed_contracts_v4 import TransactionContractV4, infer_transaction_contract
from inversereserve.models.structured_planner import ActionCandidate, action_candidates
from inversereserve.observations.typed_observation import SemanticElement, SemanticSnapshot


@dataclass(frozen=True)
class ActionCandidateV4:
    bid: str
    action: ContractActionV4
    role: str
    label: str
    state: tuple[tuple[str, Any], ...]
    transaction_kind: str | None
    semantic_bid: str
    parent_bid: str | None
    publicly_actionable_offscreen: bool = False

    def prompt_record(self) -> dict[str, Any]:
        argument: str | list[str] | None
        if isinstance(self.action.argument, tuple):
            argument = list(self.action.argument)
        else:
            argument = self.action.argument
        return {
            "bid": self.bid,
            "op": self.action.operation,
            "arg": argument,
            "enable_autocomplete_menu": self.action.enable_autocomplete_menu,
            "role": self.role,
            "label": self.label,
            "state": dict(self.state),
            "transaction_kind": self.transaction_kind,
            "semantic_bid": self.semantic_bid,
            "parent_bid": self.parent_bid,
            "publicly_actionable_offscreen": self.publicly_actionable_offscreen,
        }


@dataclass(frozen=True)
class V4ActionInventory:
    allowed: bool
    reason: str
    goal_contract: StructuredGoalContract
    candidates: tuple[ActionCandidateV4, ...]
    contracts: tuple[tuple[str, TransactionContractV4], ...]

    @property
    def contract_by_bid(self) -> dict[str, TransactionContractV4]:
        return dict(self.contracts)


def _state(element: SemanticElement) -> tuple[tuple[str, Any], ...]:
    keep = {"checked", "disabled", "expanded", "pressed", "selected", "value"}
    return tuple(((name, value) for name, value in element.ax_properties if name in keep))


def _public_option_label(snapshot: SemanticSnapshot, row: ActionCandidate) -> str:
    element = snapshot.get(row.semantic_bid)
    if element is None or element.role.casefold() != "option":
        return row.label
    value = str(element.dom_attribute("value", "")).strip()
    return value or row.label


def _component_choice_rows(snapshot: SemanticSnapshot) -> tuple[ActionCandidateV4, ...]:
    """Expose public jQuery UI menu leaves as semantic option controls."""
    rows = []
    for element in snapshot.elements:
        if not snapshot.is_effectively_visible(element.bid):
            continue
        if "ui-menu-item-wrapper" not in element.class_tokens:
            continue
        surface = next(
            (
                row
                for row in snapshot.ancestors(element.bid, relation="dom")
                if "ui-autocomplete" in row.class_tokens and snapshot.is_effectively_visible(row.bid)
            ),
            None,
        )
        if surface is None:
            continue
        label = (element.name or element.subtree_text).strip()
        if not label:
            continue
        rows.append(
            ActionCandidateV4(
                bid=element.bid,
                action=ContractActionV4("click", element.bid),
                role="option",
                label=label,
                state=_state(element),
                transaction_kind=None,
                semantic_bid=element.bid,
                parent_bid=element.dom_parent_bid,
            )
        )
    return tuple(rows)


def _currency_value(value: str) -> int | None:
    match = re.search("[$€£]\\s*(\\d+(?:\\.\\d{1,2})?)", value)
    if not match:
        return None
    return int(round(float(match.group(1)) * 100))


def _duration_minutes(value: str) -> int | None:
    matches = list(
        re.finditer(
            "(?<!\\w)(?:(\\d+)\\s*h(?:ours?)?\\s*)?(\\d+)\\s*m(?:in(?:ute)?s?)?(?!\\w)",
            value,
            flags=re.IGNORECASE,
        )
    )
    parsed = []
    for match in matches:
        hours = int(match.group(1) or 0)
        minutes = int(match.group(2))
        parsed.append(hours * 60 + minutes)
    return parsed[0] if len(parsed) == 1 else None


def _comparative_choice_rows(
    snapshot: SemanticSnapshot, goal: StructuredGoalContract
) -> tuple[ActionCandidateV4, ...]:
    """Compile public numeric alternatives without application selectors."""
    if goal.objective_anchor is None:
        return ()
    rows = []
    for element in snapshot.elements:
        if element.role.casefold() != "button" and element.dom_tag.casefold() != "button":
            continue
        label = (element.name or element.subtree_text).strip()
        price = _currency_value(label)
        if price is None:
            continue
        card_bid = None
        duration = None
        for ancestor in snapshot.ancestors(element.bid, relation="dom"):
            duration = _duration_minutes(ancestor.subtree_text or ancestor.name)
            if duration is not None:
                card_bid = ancestor.bid
                break
        if duration is None or card_bid is None:
            continue
        metric = price if goal.objective_anchor.kind == "min_cost" else duration
        rows.append(
            ActionCandidateV4(
                bid=element.bid,
                action=ContractActionV4("click", element.bid),
                role=element.role or element.dom_tag,
                label=label,
                state=tuple(
                    sorted(
                        {
                            **dict(_state(element)),
                            "objective_kind": goal.objective_anchor.kind,
                            "objective_metric": metric,
                            "public_card_bid": card_bid,
                            "public_cost_cents": price,
                            "public_duration_minutes": duration,
                        }.items()
                    )
                ),
                transaction_kind=None,
                semantic_bid=element.bid,
                parent_bid=element.ax_parent_bid or element.dom_parent_bid,
                publicly_actionable_offscreen=True,
            )
        )
    return tuple(rows)


def _candidate_from_base(
    snapshot: SemanticSnapshot, row: ActionCandidate, contract: TransactionContractV4 | None
) -> ActionCandidateV4:
    if contract is None:
        action = ContractActionV4(row.operation, row.bid)
        transaction_kind = None
        semantic_bid = row.semantic_bid
    else:
        action = contract.action
        transaction_kind = contract.kind
        semantic_bid = contract.semantic_bid
    return ActionCandidateV4(
        bid=row.bid,
        action=action,
        role=row.role,
        label=_public_option_label(snapshot, row),
        state=row.state,
        transaction_kind=transaction_kind,
        semantic_bid=semantic_bid,
        parent_bid=row.parent_bid,
    )


def compile_v4_inventory(
    snapshot: SemanticSnapshot, goal: str, *, goal_contract: StructuredGoalContract | None = None
) -> V4ActionInventory:
    """Compile per-row arguments and transaction types without a task ID."""
    if goal_contract is None:
        goal_contract = compile_structured_goal(goal, snapshot)
    elif goal_contract.goal != str(goal).strip():
        raise ValueError("persisted goal contract does not match the instruction")
    else:
        goal_contract.validate_provenance()
    if not goal_contract.allowed:
        return V4ActionInventory(
            False, "instruction exposes no supported public goal anchor", goal_contract, (), ()
        )
    rows: dict[str, ActionCandidateV4] = {}
    contracts: dict[str, TransactionContractV4] = {}
    for base in action_candidates(snapshot):
        decision = infer_transaction_contract(snapshot, base.bid, goal_contract)
        contract = decision.contract if decision.allowed else None
        if contract is not None:
            prior = contracts.get(base.bid)
            if prior is not None and prior != contract:
                raise ValueError(f"ambiguous v4 transaction contract for bid {base.bid}")
            contracts[base.bid] = contract
        rows[base.bid] = _candidate_from_base(snapshot, base, contract)
    _add_goal_selections(snapshot, goal_contract, rows, contracts)
    for component_row in _component_choice_rows(snapshot):
        if component_row.bid not in rows:
            rows[component_row.bid] = component_row
    for comparative_row in _comparative_choice_rows(snapshot, goal_contract):
        rows[comparative_row.bid] = comparative_row
    candidates = tuple(
        sorted(
            rows.values(),
            key=lambda row: (row.parent_bid or "", row.semantic_bid, row.bid, row.action.operation),
        )
    )
    return V4ActionInventory(
        True,
        f"structured goal exposed {len(contracts)} typed transactions",
        goal_contract,
        candidates,
        tuple(sorted(contracts.items())),
    )


def _add_goal_selections(
    snapshot: SemanticSnapshot,
    goal_contract: StructuredGoalContract,
    rows: dict[str, ActionCandidateV4],
    contracts: dict[str, TransactionContractV4],
) -> None:
    for selection in goal_contract.option_selections:
        if selection.bid in rows:
            continue
        decision = infer_transaction_contract(snapshot, selection.bid, goal_contract)
        if not decision.allowed or decision.contract is None:
            continue
        element = snapshot.get(selection.bid)
        if element is None:
            continue
        contract = decision.contract
        contracts[selection.bid] = contract
        rows[selection.bid] = ActionCandidateV4(
            bid=selection.bid,
            action=contract.action,
            role=element.role or element.dom_tag,
            label=", ".join(selection.values),
            state=_state(element),
            transaction_kind=contract.kind,
            semantic_bid=selection.bid,
            parent_bid=element.ax_parent_bid or element.dom_parent_bid,
        )
