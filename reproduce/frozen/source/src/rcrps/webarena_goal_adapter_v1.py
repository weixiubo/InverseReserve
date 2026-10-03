"""Outcome-blind public-action adapter for bounded WebArena transfer studies.

The frozen PACT-v9 compiler recognizes explicit ``field label: value`` style
instructions.  WebArena reply intents instead use an action construction such
as ``Reply ... with \"payload\"``.  This module binds that verbatim payload to a
public textarea only when the current AX/DOM observation supplies one unique,
editable textarea inside a form with one public submit-like action.

No task ID, evaluator specification, reward, source answer, or site-private
state is accepted by this interface.  Ambiguous public structure fails closed.
The module is deliberately separate from the C451-frozen PACT-v9 sources.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable

from .goal_contracts_v4 import GoalSpan, StructuredGoalContract, compile_structured_goal
from .pact_grounding_v4 import CommitCertificateV4, GroundingDecisionV4
from .pact_grounding_v8 import (
    commit_attempt_key_v8,
    certify_commit_v8,
    unresolved_blocking_transactions_v8,
)
from .structured_planner_v4 import (
    ActionCandidateV4,
    V4ActionInventory,
    compile_v4_inventory,
)
from .typed_contracts_v4 import TransactionContractV4, infer_transaction_contract
from .typed_observation import SemanticElement, SemanticSnapshot


PUBLIC_SUBMIT_LABELS_V1 = frozenset(
    {
        "add comment",
        "comment",
        "post",
        "reply",
        "save",
        "submit",
    }
)


def _normalized(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip().casefold()


def _span(goal: str, start: int, end: int) -> GoalSpan:
    return GoalSpan(goal[start:end], start, end)


def _public_boolean(element: SemanticElement, name: str) -> bool:
    value = element.ax_property(name)
    if value is None:
        value = element.dom_attribute(name)
    if value is None:
        value = element.dom_attribute(f"aria-{name}")
    return value is True or _normalized(value) == "true"


def _public_value(snapshot: SemanticSnapshot, bid: str) -> str:
    element = snapshot.get(bid)
    if element is None:
        return ""
    value = element.ax_property("value")
    if value is None:
        value = element.dom_attribute("value", "")
    return "" if value is None else str(value)


def _nearest_dom_form(snapshot: SemanticSnapshot, bid: str) -> SemanticElement | None:
    element = snapshot.get(bid)
    if element is None:
        return None
    if element.dom_tag.casefold() == "form":
        return element
    return next(
        (
            ancestor
            for ancestor in snapshot.ancestors(bid, relation="dom")
            if ancestor.dom_tag.casefold() == "form"
        ),
        None,
    )


def _field_label(snapshot: SemanticSnapshot, element: SemanticElement) -> str:
    for value in (element.name, element.subtree_text):
        if _normalized(value):
            return " ".join(str(value).split())
    for relation in ("ax", "dom"):
        for ancestor in snapshot.ancestors(element.bid, relation=relation):
            for value in (ancestor.name, ancestor.subtree_text):
                if _normalized(value):
                    return " ".join(str(value).split())
    placeholder = str(element.dom_attribute("placeholder", "")).strip()
    return placeholder or "textarea"


def _candidate_is_submit_like(candidate: ActionCandidateV4) -> bool:
    return bool(
        candidate.transaction_kind is None
        and candidate.role.casefold() == "button"
        and _normalized(candidate.label) in PUBLIC_SUBMIT_LABELS_V1
    )


def _visible_submit_bids_in_form(
    snapshot: SemanticSnapshot,
    form_bid: str,
) -> tuple[str, ...]:
    bids = []
    for element in snapshot.descendants(form_bid, relation="dom"):
        if not snapshot.is_effectively_visible(element.bid):
            continue
        label = _normalized(element.name or element.subtree_text)
        if (
            element.role.casefold() == "button"
            and element.clickable
            and label in PUBLIC_SUBMIT_LABELS_V1
        ):
            bids.append(element.bid)
    return tuple(sorted(set(bids)))


@dataclass(frozen=True)
class ReplyPayloadClauseV1:
    value: str
    action_span: GoalSpan
    value_span: GoalSpan

    def record(self) -> dict[str, object]:
        return {
            "kind": "reply_with_quoted_payload",
            "value": self.value,
            "action_span": self.action_span.record(),
            "value_span": self.value_span.record(),
        }


@dataclass(frozen=True)
class PublicPayloadBindingV1:
    bid: str
    label: str
    value: str
    action_span: GoalSpan
    value_span: GoalSpan
    form_bid: str
    submit_bid: str
    binding_kind: str = "reply_with_quoted_payload"

    def record(self) -> dict[str, object]:
        return {
            "bid": self.bid,
            "public_label": self.label,
            "value": self.value,
            "instruction_action_span": self.action_span.record(),
            "value_span": self.value_span.record(),
            "binding_kind": self.binding_kind,
            "public_form_bid": self.form_bid,
            "public_submit_bid": self.submit_bid,
        }


@dataclass(frozen=True)
class WebArenaGoalContractV1:
    base: StructuredGoalContract
    reply_payload: ReplyPayloadClauseV1 | None
    payload_bindings: tuple[PublicPayloadBindingV1, ...]
    payload_resolution: str

    @property
    def goal(self) -> str:
        return self.base.goal

    @property
    def exact_constraint(self) -> Any:
        return self.base.exact_constraint

    @property
    def field_assignments(self) -> tuple[Any, ...]:
        rows: list[Any] = list(self.base.field_assignments)
        for binding in self.payload_bindings:
            equivalent = any(
                str(row.bid) == binding.bid
                and _normalized(row.value) == _normalized(binding.value)
                for row in rows
            )
            if not equivalent:
                rows.append(binding)
        return tuple(rows)

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
    def rejected_reasons(self) -> tuple[str, ...]:
        return self.base.rejected_reasons

    @property
    def allowed(self) -> bool:
        return self.base.allowed or bool(self.payload_bindings)

    def assignment_for_bid(self, bid: str) -> Any | None:
        rows = [row for row in self.field_assignments if str(row.bid) == str(bid)]
        return rows[0] if len(rows) == 1 else None

    def selection_for_bid(self, bid: str) -> Any | None:
        return self.base.selection_for_bid(bid)

    def validate_provenance(self) -> None:
        self.base.validate_provenance()
        spans: list[GoalSpan] = []
        if self.reply_payload is not None:
            spans.extend(
                (self.reply_payload.action_span, self.reply_payload.value_span)
            )
        for binding in self.payload_bindings:
            spans.extend((binding.action_span, binding.value_span))
            if not binding.bid or not binding.form_bid or not binding.submit_bid:
                raise ValueError("public payload binding is structurally incomplete")
            if not binding.value or len(binding.value) > 512:
                raise ValueError("public payload binding has an invalid value")
        for span in spans:
            if self.goal[span.start : span.end] != span.text:
                raise ValueError("WebArena payload anchor is not verbatim provenance")

    def record(self) -> dict[str, object]:
        self.validate_provenance()
        record = self.base.record()
        record["allowed"] = self.allowed
        record["webarena_public_adapter_v1"] = {
            "reply_payload": (
                self.reply_payload.record()
                if self.reply_payload is not None
                else None
            ),
            "payload_bindings": [row.record() for row in self.payload_bindings],
            "payload_resolution": self.payload_resolution,
            "uses_task_id": False,
            "uses_evaluator": False,
            "uses_reward": False,
        }
        return record


def parse_reply_payload_v1(goal: str) -> ReplyPayloadClauseV1 | None:
    """Parse one verbatim reply payload without consulting task metadata."""

    text = str(goal).strip()
    clauses = list(
        re.finditer(
            r"\bwith(?:\s+my)?(?:\s+(?:comment|reply))?\s*"
            r"[\"“](?P<value>[^\"“”]{1,512})[\"”]",
            text,
            flags=re.IGNORECASE,
        )
    )
    if len(clauses) != 1:
        return None
    clause = clauses[0]
    verb = re.match(r"\s*(?:please\s+)?(?P<verb>reply)\b", text, re.IGNORECASE)
    if verb is None or verb.end("verb") > clause.start():
        return None
    value_start, value_end = clause.span("value")
    return ReplyPayloadClauseV1(
        text[value_start:value_end],
        _span(text, verb.start("verb"), verb.end("verb")),
        _span(text, value_start, value_end),
    )


def _resolve_payload_bindings_v1(
    snapshot: SemanticSnapshot,
    clause: ReplyPayloadClauseV1 | None,
) -> tuple[tuple[PublicPayloadBindingV1, ...], str]:
    if clause is None:
        return (), "instruction exposes no unique reply-with-quoted-payload clause"
    rows: list[tuple[SemanticElement, SemanticElement, str]] = []
    for element in snapshot.elements:
        if not snapshot.is_effectively_visible(element.bid):
            continue
        if element.dom_tag.casefold() != "textarea" or element.role.casefold() != "textbox":
            continue
        if _public_boolean(element, "readonly") or _public_boolean(element, "disabled"):
            continue
        form = _nearest_dom_form(snapshot, element.bid)
        if form is None:
            continue
        submit_bids = _visible_submit_bids_in_form(snapshot, form.bid)
        if len(submit_bids) != 1:
            continue
        rows.append((element, form, submit_bids[0]))
    if len(rows) != 1:
        return (), (
            "reply payload did not resolve to exactly one visible editable textarea "
            "inside a form with one public submit action"
        )
    element, form, submit_bid = rows[0]
    return (
        (
            PublicPayloadBindingV1(
                bid=element.bid,
                label=_field_label(snapshot, element),
                value=clause.value,
                action_span=clause.action_span,
                value_span=clause.value_span,
                form_bid=form.bid,
                submit_bid=submit_bid,
            ),
        ),
        "one public reply form uniquely binds the verbatim instruction payload",
    )


def compile_webarena_goal_contract_v1(
    goal: str,
    snapshot: SemanticSnapshot,
) -> WebArenaGoalContractV1:
    base = compile_structured_goal(goal, snapshot)
    clause = parse_reply_payload_v1(base.goal)
    bindings, reason = _resolve_payload_bindings_v1(snapshot, clause)
    contract = WebArenaGoalContractV1(base, clause, bindings, reason)
    contract.validate_provenance()
    return contract


def _candidate_state(element: SemanticElement) -> tuple[tuple[str, Any], ...]:
    keep = {"checked", "disabled", "expanded", "pressed", "selected", "value"}
    return tuple((name, value) for name, value in element.ax_properties if name in keep)


def compile_webarena_inventory_v1(
    snapshot: SemanticSnapshot,
    goal: str,
    *,
    goal_contract: WebArenaGoalContractV1 | None = None,
) -> V4ActionInventory:
    """Compile base public controls plus fail-closed reply payload transactions."""

    if goal_contract is None:
        goal_contract = compile_webarena_goal_contract_v1(goal, snapshot)
    elif goal_contract.goal != str(goal).strip():
        raise ValueError("persisted WebArena goal contract does not match instruction")
    else:
        goal_contract.validate_provenance()

    base = compile_v4_inventory(snapshot, goal, goal_contract=goal_contract)
    rows = {row.bid: row for row in base.candidates}
    contracts = dict(base.contracts)
    for binding in goal_contract.payload_bindings:
        decision = infer_transaction_contract(snapshot, binding.bid, goal_contract)
        if not decision.allowed or decision.contract is None:
            raise ValueError("public payload binding did not compile to a transaction")
        contract: TransactionContractV4 = decision.contract
        element = snapshot.get(binding.bid)
        if element is None:
            raise ValueError("bound public textarea disappeared during inventory compilation")
        contracts[binding.bid] = contract
        rows[binding.bid] = ActionCandidateV4(
            bid=binding.bid,
            action=contract.action,
            role=element.role or element.dom_tag,
            label=binding.label,
            state=_candidate_state(element),
            transaction_kind=contract.kind,
            semantic_bid=contract.semantic_bid,
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
        goal_contract.allowed,
        (
            f"public WebArena adapter exposed {len(goal_contract.payload_bindings)} "
            "verbatim payload transactions"
        ),
        goal_contract,  # type: ignore[arg-type]
        candidates,
        tuple(sorted(contracts.items())),
    )


def _active_payload_bids(
    active_transactions: Iterable[Any],
    goal: WebArenaGoalContractV1,
) -> tuple[str, ...]:
    expected = {binding.bid: binding.value for binding in goal.payload_bindings}
    matched = []
    for transaction in active_transactions:
        contract = transaction.contract if hasattr(transaction, "contract") else transaction["contract"]
        bid = str(contract.semantic_bid)
        if (
            contract.kind == "editable_field_assignment"
            and bid in expected
            and str(contract.expected_value) == expected[bid]
        ):
            matched.append(bid)
    return tuple(sorted(set(matched)))


def certify_webarena_commit_v1(
    *,
    current: SemanticSnapshot,
    goal: WebArenaGoalContractV1,
    candidate: ActionCandidateV4,
    inventory: tuple[ActionCandidateV4, ...],
    active_transactions: tuple[Any, ...],
    resolved_semantic_bids: tuple[str, ...] = (),
    quarantined_commit_keys: frozenset[tuple[object, ...]] = frozenset(),
) -> CommitCertificateV4:
    """Extend v8 certification with one same-form public reply action."""

    base = certify_commit_v8(
        current=current,
        goal=goal,
        candidate=candidate,
        inventory=inventory,
        active_transactions=active_transactions,
        resolved_semantic_bids=resolved_semantic_bids,
        quarantined_commit_keys=quarantined_commit_keys,
    )
    if base.allowed or not goal.payload_bindings:
        return base
    rows_by_bid = {row.bid: row for row in inventory}
    if len(rows_by_bid) != len(inventory) or rows_by_bid.get(candidate.bid) != candidate:
        return base
    if not _candidate_is_submit_like(candidate):
        return base
    if not current.is_effectively_visible(candidate.bid):
        return base
    blockers = unresolved_blocking_transactions_v8(
        active_transactions, resolved_semantic_bids
    )
    if blockers:
        return CommitCertificateV4(
            False,
            "a blocking typed overlay remains unresolved",
            GroundingDecisionV4(
                False,
                "a blocking typed overlay remains unresolved",
                "payload_form_action",
                tuple(sorted({row.contract.semantic_bid for row in blockers})),
            ),
        )
    binding_bids = tuple(sorted(binding.bid for binding in goal.payload_bindings))
    if _active_payload_bids(active_transactions, goal) != binding_bids:
        return base
    if any(
        _normalized(_public_value(current, binding.bid))
        != _normalized(binding.value)
        for binding in goal.payload_bindings
    ):
        return base
    form_bids = {binding.form_bid for binding in goal.payload_bindings}
    candidate_form = _nearest_dom_form(current, candidate.bid)
    if candidate_form is None or form_bids != {candidate_form.bid}:
        return base
    submit_rows = tuple(
        row
        for row in inventory
        if _candidate_is_submit_like(row)
        and (form := _nearest_dom_form(current, row.bid)) is not None
        and form.bid == candidate_form.bid
    )
    competing = tuple(sorted(row.bid for row in submit_rows))
    if competing != (candidate.bid,):
        return CommitCertificateV4(
            False,
            "payload form action is ambiguous",
            GroundingDecisionV4(
                False,
                "payload form action is ambiguous",
                "payload_form_action",
                binding_bids,
                competing,
            ),
        )
    try:
        key = commit_attempt_key_v8(
            current=current,
            action=candidate.action,
            active_transactions=active_transactions,
        )
    except Exception as error:
        return CommitCertificateV4(
            False,
            f"public effect key failed: {type(error).__name__}",
            GroundingDecisionV4(False, "public effect key failed", "payload_form_action"),
        )
    if key in quarantined_commit_keys:
        return CommitCertificateV4(
            False,
            "the same payload form action already had zero public effect",
            GroundingDecisionV4(
                False,
                "the same payload form action already had zero public effect",
                "no_effect_quarantine",
                binding_bids,
                competing,
            ),
        )
    grounding = GroundingDecisionV4(
        True,
        "one same-form public action is supported by the active verbatim payload transaction",
        "payload_form_action",
        binding_bids,
        competing,
        candidate.bid,
    )
    return CommitCertificateV4(
        True,
        grounding.reason,
        grounding,
        candidate.action,
        key[0],
        key[1],
    )
