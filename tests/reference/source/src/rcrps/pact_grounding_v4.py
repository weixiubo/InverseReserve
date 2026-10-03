"""Fresh public-state commit certificates for structured PACT v4 goals."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable

from .goal_contracts_v4 import StructuredGoalContract
from .pact_grounding_v3 import satisfies_constraint
from .structured_planner_v4 import ActionCandidateV4
from .transaction_actions_v4 import ContractActionV4
from .typed_contracts_v4 import public_calendar_context, public_selected_values
from .typed_observation import SemanticSnapshot


FORM_ACTION_LABELS = frozenset(
    {"apply", "continue", "done", "login", "ok", "save", "search", "submit"}
)
TERMINAL_ALIASES = {
    "apply": frozenset({"apply", "ok"}),
    "continue": frozenset({"continue", "next", "ok"}),
    "done": frozenset({"done", "ok"}),
    "login": frozenset({"login", "ok", "submit"}),
    "ok": frozenset({"ok"}),
    "save": frozenset({"save", "ok"}),
    "search": frozenset({"search"}),
    "submit": frozenset({"submit", "ok"}),
}


def _normalize(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip().casefold()


def _public_value(snapshot: SemanticSnapshot, bid: str) -> str:
    element = snapshot.get(bid)
    if element is None:
        return ""
    value = element.ax_property("value")
    if value is None:
        value = element.dom_attribute("value", "")
    return "" if value is None else str(value)


def _value_token_match(observed: str, expected: str) -> bool:
    observed_normalized = _normalize(observed)
    expected_normalized = _normalize(expected)
    if not observed_normalized or not expected_normalized:
        return False
    if observed_normalized == expected_normalized:
        return True
    pattern = re.compile(
        rf"(?<![\w]){re.escape(expected_normalized)}(?![\w])",
        flags=re.IGNORECASE,
    )
    return pattern.search(observed_normalized) is not None


def _candidate_visible(
    snapshot: SemanticSnapshot,
    candidate: ActionCandidateV4,
) -> bool:
    action = snapshot.get(candidate.bid)
    semantic = snapshot.get(candidate.semantic_bid)
    return bool(
        action is not None
        and semantic is not None
        and (
            candidate.publicly_actionable_offscreen
            or snapshot.is_effectively_visible(candidate.bid)
        )
        and (
            candidate.publicly_actionable_offscreen
            or snapshot.is_effectively_visible(candidate.semantic_bid)
        )
    )


def transaction_scope_bids(
    current: SemanticSnapshot,
    transaction: Any,
) -> frozenset[str]:
    bids = set(transaction.delta.added_visible_bids)
    bids.update(transaction.delta.changed_visible_bids)
    bids.add(transaction.contract.semantic_bid)
    if transaction.contract.action.bid is not None:
        bids.add(transaction.contract.action.bid)
    for relation in ("ax", "dom"):
        bids.update(
            row.bid
            for row in current.descendants(
                transaction.contract.semantic_bid,
                relation=relation,
            )
        )
    return frozenset(bids)


def _state_requirements_present(goal: StructuredGoalContract) -> bool:
    prefix_constraint = bool(
        goal.exact_constraint is not None
        and goal.exact_constraint.kind in {"prefix", "suffix", "prefix_suffix"}
    )
    return bool(
        goal.field_assignments
        or goal.date_anchor
        or goal.option_selections
        or prefix_constraint
    )


@dataclass(frozen=True)
class GoalStateEvidenceV4:
    allowed: bool
    reason: str
    evidence_bids: tuple[str, ...]
    missing: tuple[str, ...]


def verify_goal_state(
    current: SemanticSnapshot,
    goal: StructuredGoalContract,
) -> GoalStateEvidenceV4:
    """Verify every structured intermediate value against public state."""

    evidence: list[str] = []
    missing: list[str] = []
    for assignment in goal.field_assignments:
        observed = _public_value(current, assignment.bid)
        if _value_token_match(observed, assignment.value):
            evidence.append(assignment.bid)
        else:
            missing.append(f"field:{assignment.bid}")

    if goal.exact_constraint is not None and goal.exact_constraint.kind in {
        "prefix",
        "suffix",
        "prefix_suffix",
    }:
        matches = [
            element.bid
            for element in current.elements
            if current.is_effectively_visible(element.bid)
            and element.role.casefold() in {"combobox", "searchbox", "textbox"}
            and satisfies_constraint(
                _public_value(current, element.bid), goal.exact_constraint
            )
        ]
        if len(matches) == 1:
            evidence.extend(matches)
        else:
            missing.append("text_target")

    if goal.date_anchor is not None:
        date_matches = [
            element.bid
            for element in current.elements
            if "hasdatepicker" in element.class_tokens
            and _normalize(_public_value(current, element.bid))
            == _normalize(goal.date_anchor.canonical)
        ]
        if len(date_matches) == 1:
            evidence.extend(date_matches)
        else:
            missing.append("date")

    for selection in goal.option_selections:
        observed = public_selected_values(current, selection.bid)
        if set(observed) == set(selection.values) and len(observed) == len(
            selection.values
        ):
            evidence.append(selection.bid)
        else:
            missing.append(f"selection:{selection.bid}")

    if not _state_requirements_present(goal):
        return GoalStateEvidenceV4(
            False,
            "goal exposes no public intermediate state requirement",
            (),
            (),
        )
    if missing:
        return GoalStateEvidenceV4(
            False,
            "structured goal state is incomplete",
            tuple(sorted(set(evidence))),
            tuple(missing),
        )
    return GoalStateEvidenceV4(
        True,
        "every structured goal value is present in public state",
        tuple(sorted(set(evidence))),
        (),
    )


@dataclass(frozen=True)
class GroundingDecisionV4:
    allowed: bool
    reason: str
    anchor_kind: str | None
    evidence_bids: tuple[str, ...] = ()
    competing_bids: tuple[str, ...] = ()
    certified_bid: str | None = None


def _decision_from_rows(
    candidate: ActionCandidateV4,
    rows: Iterable[ActionCandidateV4],
    *,
    reason: str,
    anchor_kind: str,
    evidence_bids: tuple[str, ...] = (),
) -> GroundingDecisionV4:
    competing = tuple(sorted({row.bid for row in rows}))
    if len(competing) != 1:
        return GroundingDecisionV4(
            False,
            f"{anchor_kind} grounding is ambiguous",
            anchor_kind,
            evidence_bids,
            competing,
        )
    if candidate.bid != competing[0]:
        return GroundingDecisionV4(
            False,
            "planner candidate is not the uniquely grounded row",
            anchor_kind,
            evidence_bids,
            competing,
        )
    return GroundingDecisionV4(
        True,
        reason,
        anchor_kind,
        evidence_bids,
        competing,
        candidate.bid,
    )


def _visible_inventory(
    current: SemanticSnapshot,
    inventory: tuple[ActionCandidateV4, ...],
) -> tuple[ActionCandidateV4, ...]:
    return tuple(row for row in inventory if _candidate_visible(current, row))


def _exact_rows(
    current: SemanticSnapshot,
    goal: StructuredGoalContract,
    inventory: tuple[ActionCandidateV4, ...],
) -> tuple[ActionCandidateV4, ...]:
    if goal.exact_constraint is None:
        return ()
    return tuple(
        row
        for row in _visible_inventory(current, inventory)
        if satisfies_constraint(row.label, goal.exact_constraint)
    )


def _active_value_rows(
    current: SemanticSnapshot,
    inventory: tuple[ActionCandidateV4, ...],
    active_transactions: tuple[Any, ...],
) -> tuple[tuple[ActionCandidateV4, ...], tuple[str, ...]]:
    for transaction in reversed(active_transactions):
        if transaction.contract.kind != "autocomplete_query":
            continue
        expected = transaction.contract.expected_value
        if not expected:
            continue
        scope = transaction_scope_bids(current, transaction)
        rows = tuple(
            row
            for row in _visible_inventory(current, inventory)
            if (row.bid in scope or row.semantic_bid in scope)
            and row.transaction_kind is None
            and _value_token_match(row.label, expected)
        )
        if rows:
            return rows, (transaction.contract.semantic_bid,)
    return (), ()


def _calendar_day_rows(
    current: SemanticSnapshot,
    goal: StructuredGoalContract,
    inventory: tuple[ActionCandidateV4, ...],
    active_transactions: tuple[Any, ...],
) -> tuple[tuple[ActionCandidateV4, ...], tuple[str, ...]]:
    if goal.date_anchor is None:
        return (), ()
    context = public_calendar_context(current)
    if context != (goal.date_anchor.month, goal.date_anchor.year):
        return (), ()
    expected_day = str(goal.date_anchor.day)
    for transaction in reversed(active_transactions):
        if transaction.contract.kind not in {
            "datepicker_open",
            "calendar_month_shift",
        }:
            continue
        scope = transaction_scope_bids(current, transaction)
        rows = tuple(
            row
            for row in _visible_inventory(current, inventory)
            if (row.bid in scope or row.semantic_bid in scope)
            and row.transaction_kind is None
            and _normalize(row.label) == expected_day
            and row.role.casefold() in {"button", "gridcell", "link"}
        )
        leaf_rows = tuple(
            row for row in rows if row.role.casefold() in {"button", "link"}
        )
        if leaf_rows:
            rows = leaf_rows
        if rows:
            return rows, (transaction.contract.semantic_bid,)
    return (), ()


def verify_commit_grounding_v4(
    *,
    current: SemanticSnapshot,
    goal: StructuredGoalContract,
    candidate: ActionCandidateV4,
    inventory: tuple[ActionCandidateV4, ...],
    active_transactions: tuple[Any, ...],
) -> GroundingDecisionV4:
    """Ground a commit by role, target, active evidence, or completed form state."""

    rows_by_bid = {row.bid: row for row in inventory}
    if len(rows_by_bid) != len(inventory) or rows_by_bid.get(candidate.bid) != candidate:
        return GroundingDecisionV4(
            False,
            "candidate is not one authoritative inventory row",
            None,
        )
    visible = _visible_inventory(current, inventory)

    if goal.role_anchor is not None:
        role_rows = tuple(
            row for row in visible if row.role.casefold() == goal.role_anchor.role
        )
        return _decision_from_rows(
            candidate,
            role_rows,
            reason="one visible row matches the explicit public widget role",
            anchor_kind="direct_role",
        )

    if goal.objective_anchor is not None:
        objective_rows = []
        for row in visible:
            state = dict(row.state)
            if state.get("objective_kind") != goal.objective_anchor.kind:
                continue
            metric = state.get("objective_metric")
            if not isinstance(metric, (int, float)):
                continue
            objective_rows.append((float(metric), row, str(state.get("public_card_bid", ""))))
        if objective_rows:
            optimum = min(item[0] for item in objective_rows)
            winners = tuple(item[1] for item in objective_rows if item[0] == optimum)
            evidence = tuple(sorted(item[2] for item in objective_rows if item[2]))
            return _decision_from_rows(
                candidate,
                winners,
                reason="one public alternative is the unique comparative optimum",
                anchor_kind=goal.objective_anchor.kind,
                evidence_bids=evidence,
            )

    exact_rows = _exact_rows(current, goal, inventory)
    exact_rows = tuple(
        row
        for row in exact_rows
        if not (
            row.role.casefold() == "button"
            and _normalize(row.label) in FORM_ACTION_LABELS
            and _state_requirements_present(goal)
        )
    )
    if exact_rows:
        if active_transactions:
            scoped = []
            for transaction in reversed(active_transactions):
                scope = transaction_scope_bids(current, transaction)
                scoped = [
                    row
                    for row in exact_rows
                    if row.bid in scope or row.semantic_bid in scope
                ]
                if scoped:
                    break
            if scoped:
                exact_rows = tuple(scoped)
        return _decision_from_rows(
            candidate,
            exact_rows,
            reason="one visible row satisfies the exact public goal constraint",
            anchor_kind="exact_target",
        )

    value_rows, value_evidence = _active_value_rows(
        current, inventory, active_transactions
    )
    if value_rows:
        return _decision_from_rows(
            candidate,
            value_rows,
            reason="one active autocomplete transaction exposes the grounded field value",
            anchor_kind="active_field_value",
            evidence_bids=value_evidence,
        )

    day_rows, day_evidence = _calendar_day_rows(
        current, goal, inventory, active_transactions
    )
    if day_rows:
        return _decision_from_rows(
            candidate,
            day_rows,
            reason="one active date-picker transaction exposes the goal day in goal month",
            anchor_kind="calendar_day",
            evidence_bids=day_evidence,
        )

    state = verify_goal_state(current, goal)
    if state.allowed:
        allowed_labels = FORM_ACTION_LABELS
        if goal.terminal_intent is not None:
            allowed_labels = TERMINAL_ALIASES[goal.terminal_intent.requested_label]
        form_rows = tuple(
            row
            for row in visible
            if row.role.casefold() == "button"
            and _normalize(row.label) in allowed_labels
            and row.transaction_kind is None
        )
        return _decision_from_rows(
            candidate,
            form_rows,
            reason="one form action is supported by complete public goal state",
            anchor_kind="state_supported_form_action",
            evidence_bids=state.evidence_bids,
        )

    return GroundingDecisionV4(
        False,
        "no unique public role, target, active evidence, or completed state grounds commit",
        None,
        state.evidence_bids,
    )


def stack_signature_v4(
    transactions: Iterable[Any],
) -> tuple[tuple[object, ...], ...]:
    rows = []
    for transaction in transactions:
        action = transaction.contract.action
        rows.append(
            (
                transaction.contract.kind,
                transaction.contract.semantic_bid,
                action.operation,
                action.bid,
                action.argument,
                action.enable_autocomplete_menu,
            )
        )
    return tuple(rows)


@dataclass(frozen=True)
class CommitCertificateV4:
    allowed: bool
    reason: str
    grounding: GroundingDecisionV4
    certified_action: ContractActionV4 | None = None
    observation_fingerprint: tuple[tuple[object, ...], ...] = ()
    active_stack_signature: tuple[tuple[object, ...], ...] = ()


def certify_commit_v4(
    *,
    current: SemanticSnapshot,
    goal: StructuredGoalContract,
    candidate: ActionCandidateV4,
    inventory: tuple[ActionCandidateV4, ...],
    active_transactions: tuple[Any, ...],
) -> CommitCertificateV4:
    grounding = verify_commit_grounding_v4(
        current=current,
        goal=goal,
        candidate=candidate,
        inventory=inventory,
        active_transactions=active_transactions,
    )
    if not grounding.allowed:
        return CommitCertificateV4(False, grounding.reason, grounding)
    try:
        fingerprint = current.semantic_fingerprint()
    except Exception as error:
        return CommitCertificateV4(
            False,
            f"public observation fingerprint failed: {type(error).__name__}",
            grounding,
        )
    return CommitCertificateV4(
        True,
        grounding.reason,
        grounding,
        candidate.action,
        fingerprint,
        stack_signature_v4(active_transactions),
    )
