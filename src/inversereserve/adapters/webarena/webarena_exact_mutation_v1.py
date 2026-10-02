"""Public-only exact-mutation adapter for bounded WebArena transfer.

The adapter handles only the lexical population frozen by
``webarena_verified_select_exact_mutations.py``.  It parses a verbatim value
from a ``Change|Set|Update ... to|as ...`` instruction and binds it to one
uniquely matching visible editable field inside one public DOM form.  Task
IDs, evaluator specifications, rewards, hidden state, and site-specific CSS
selectors are absent from the interface.  Ambiguity fails closed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from inversereserve.adapters.webarena.certificate_denial import CertificateDenial
from inversereserve.adapters.webarena.commit_finalization import CommitMessages, finalize_mutation_commit
from inversereserve.adapters.webarena.payload_checks import active_payload_rejection
from inversereserve.adapters.webarena.webarena_goal_adapter_v1 import (
    PublicPayloadBindingV1,
    WebArenaGoalContractV1,
    _normalized,
    _public_boolean,
    compile_webarena_inventory_v1,
)
from inversereserve.adapters.webarena.webarena_goal_adapter_v1 import _field_label as _field_label
from inversereserve.adapters.webarena.webarena_goal_adapter_v1 import _nearest_dom_form as _nearest_dom_form
from inversereserve.contracts.goal_contracts_v4 import GoalSpan, compile_structured_goal
from inversereserve.contracts.pact_grounding_v4 import CommitCertificateV4, GroundingDecisionV4
from inversereserve.contracts.pact_grounding_v8 import (
    certify_commit_v8,
)
from inversereserve.contracts.typed_contracts_v4 import TEXT_INPUT_ROLES
from inversereserve.models.structured_planner_v4 import ActionCandidateV4, V4ActionInventory
from inversereserve.observations.typed_observation import SemanticElement, SemanticSnapshot

LEADING_MUTATION_V1 = re.compile("^\\s*(?P<verb>change|set|update)\\b", re.IGNORECASE)
VALUE_CONNECTOR_V1 = re.compile("\\b(?P<connector>to|as)\\b", re.IGNORECASE)
FORBIDDEN_COMPLEXITY_V1 = re.compile(
    "\\b(?:and|all|commit|branch|where|if|most|least|recent|each|assign|invite|number\\s+of|count\\s+of)\\b|[{}<>]",
    re.IGNORECASE,
)
FIELD_STOPWORDS_V1 = frozenset(
    {
        "my",
        "the",
        "on",
        "of",
        "for",
        "in",
        "discussion",
        "forum",
        "gitlab",
        "profile",
        "site",
        "first",
        "order",
        "ever",
    }
)
FIELD_ALIASES_V1 = {
    "bio": frozenset({"bio", "biography", "about"}),
    "status": frozenset({"status", "availability"}),
    "homepage": frozenset({"homepage", "website", "web", "url"}),
    "url": frozenset({"url", "website", "homepage"}),
    "page": frozenset({"page", "title"}),
    "title": frozenset({"title"}),
    "delivery": frozenset({"delivery", "shipping", "street", "address"}),
    "address": frozenset({"address"}),
}
SUBMIT_PREFIXES_V1 = frozenset({"change", "save", "submit", "update"})


def _span(text: str, start: int, end: int) -> GoalSpan:
    return GoalSpan(text[start:end], start, end)


def _tokens(value: object) -> tuple[str, ...]:
    return tuple(re.findall("[a-z0-9]+", str(value).casefold()))


def _unquoted_connectors(text: str) -> list[re.Match[str]]:
    quoted = False
    smart = False
    mask = [True] * len(text)
    for index, character in enumerate(text):
        if character == '"' and (not smart):
            quoted = not quoted
            mask[index] = False
            continue
        if character == "“" and (not quoted):
            smart = True
            mask[index] = False
            continue
        if character == "”" and smart and (not quoted):
            smart = False
            mask[index] = False
            continue
        if quoted or smart:
            mask[index] = False
    return [
        match
        for match in VALUE_CONNECTOR_V1.finditer(text)
        if all((mask[index] for index in range(match.start(), match.end())))
    ]


def _field_anchor_tokens(field_text: str) -> tuple[str, ...]:
    without_quotes = re.sub('["“][^"”]*["”]', " ", field_text)
    rows = []
    for token in _tokens(without_quotes):
        if token in FIELD_STOPWORDS_V1 or token in rows:
            continue
        rows.append(token)
    return tuple(rows)


@dataclass(frozen=True)
class ExactMutationClauseV1:
    verb: str
    field_text: str
    value: str
    anchor_tokens: tuple[str, ...]
    action_span: GoalSpan
    field_span: GoalSpan
    value_span: GoalSpan

    def record(self) -> dict[str, object]:
        return {
            "kind": "exact_public_field_mutation",
            "verb": self.verb,
            "field_text": self.field_text,
            "value": self.value,
            "anchor_tokens": list(self.anchor_tokens),
            "action_span": self.action_span.record(),
            "field_span": self.field_span.record(),
            "value_span": self.value_span.record(),
        }


def parse_exact_mutation_v1(goal: str) -> ExactMutationClauseV1 | None:
    """Parse one frozen exact-mutation clause from verbatim goal text."""
    text = str(goal).strip()
    verb = LEADING_MUTATION_V1.match(text)
    if verb is None or FORBIDDEN_COMPLEXITY_V1.search(text) is not None:
        return None
    connectors = [row for row in _unquoted_connectors(text) if row.start() > verb.end("verb")]
    if len(connectors) != 1:
        return None
    connector = connectors[0]
    field_start = verb.end("verb")
    while field_start < connector.start() and text[field_start].isspace():
        field_start += 1
    field_end = connector.start()
    while field_end > field_start and text[field_end - 1].isspace():
        field_end -= 1
    if field_end <= field_start:
        return None
    value_bounds = _mutation_value_span(text, connector.end("connector"))
    if value_bounds is None:
        return None
    value_start, value_end = value_bounds
    value = text[value_start:value_end]
    field_text = text[field_start:field_end]
    anchors = _field_anchor_tokens(field_text)
    if not value.strip() or len(value) > 512 or (not anchors):
        return None
    return ExactMutationClauseV1(
        verb.group("verb"),
        field_text,
        value,
        anchors,
        _span(text, verb.start("verb"), verb.end("verb")),
        _span(text, field_start, field_end),
        _span(text, value_start, value_end),
    )


def _editable(element: SemanticElement, snapshot: SemanticSnapshot) -> bool:
    role = element.role.casefold()
    tag = element.dom_tag.casefold()
    return bool(
        snapshot.is_effectively_visible(element.bid)
        and (role in TEXT_INPUT_ROLES or tag in {"input", "textarea"})
        and (not _public_boolean(element, "readonly"))
        and (not _public_boolean(element, "disabled"))
    )


def _label_tokens(snapshot: SemanticSnapshot, element: SemanticElement) -> set[str]:
    values = [
        element.name,
        element.subtree_text,
        element.dom_attribute("placeholder", ""),
        element.dom_attribute("aria-label", ""),
        element.dom_attribute("name", ""),
        element.dom_attribute("id", ""),
    ]
    for relation in ("ax", "dom"):
        ancestors = snapshot.ancestors(element.bid, relation=relation)
        if ancestors:
            values.extend((ancestors[0].name, ancestors[0].subtree_text))
    return {token for value in values for token in _tokens(value)}


def _anchor_score(anchor_tokens: tuple[str, ...], labels: set[str]) -> int:
    return sum(
        (bool(labels & set(FIELD_ALIASES_V1.get(token, frozenset({token})))) for token in anchor_tokens)
    )


def _submit_like_label(label: object) -> bool:
    tokens = _tokens(_normalized(label))
    return bool(tokens and tokens[0] in SUBMIT_PREFIXES_V1)


def _visible_submit_bids(snapshot: SemanticSnapshot, form_bid: str) -> tuple[str, ...]:
    rows = []
    for element in snapshot.descendants(form_bid, relation="dom"):
        if not snapshot.is_effectively_visible(element.bid):
            continue
        if (
            element.role.casefold() == "button"
            and element.clickable
            and _submit_like_label(element.name or element.subtree_text)
        ):
            rows.append(element.bid)
    return tuple(sorted(set(rows)))


def _resolve_binding(
    snapshot: SemanticSnapshot, clause: ExactMutationClauseV1 | None
) -> tuple[tuple[PublicPayloadBindingV1, ...], str]:
    if clause is None:
        return ((), "instruction is outside the frozen exact-mutation grammar")
    scored = []
    for element in snapshot.elements:
        if not _editable(element, snapshot):
            continue
        score = _anchor_score(clause.anchor_tokens, _label_tokens(snapshot, element))
        if score == len(clause.anchor_tokens):
            scored.append((score, element))
    if not scored:
        return ((), "no visible editable public field matches the mutation anchor")
    maximum = max((score for score, _element in scored))
    winners = [element for score, element in scored if score == maximum]
    if len(winners) != 1:
        return ((), "mutation anchor does not identify exactly one editable public field")
    element = winners[0]
    form = _nearest_dom_form(snapshot, element.bid)
    if form is None:
        return ((), "the uniquely matched public field is not inside a DOM form")
    submit_bids = _visible_submit_bids(snapshot, form.bid)
    if len(submit_bids) != 1:
        return ((), "the matched public form does not expose exactly one submit action")
    return (
        (
            PublicPayloadBindingV1(
                bid=element.bid,
                label=_field_label(snapshot, element),
                value=clause.value,
                action_span=clause.action_span,
                value_span=clause.value_span,
                form_bid=form.bid,
                submit_bid=submit_bids[0],
                binding_kind="exact_public_field_mutation",
            ),
        ),
        "one public editable field and one same-form action bind the exact value",
    )


@dataclass(frozen=True)
class ExactMutationCompilationV1:
    goal_contract: WebArenaGoalContractV1
    clause: ExactMutationClauseV1 | None
    resolution: str

    @property
    def allowed(self) -> bool:
        return bool(self.clause and self.goal_contract.payload_bindings)

    def record(self) -> dict[str, object]:
        record = self.goal_contract.record()
        record["webarena_exact_mutation_v1"] = {
            "clause": None if self.clause is None else self.clause.record(),
            "resolution": self.resolution,
            "allowed": self.allowed,
            "uses_task_id": False,
            "uses_evaluator": False,
            "uses_reward": False,
            "uses_hidden_state": False,
            "uses_site_specific_selector": False,
        }
        return record


def compile_exact_mutation_goal_v1(goal: str, snapshot: SemanticSnapshot) -> ExactMutationCompilationV1:
    text = str(goal).strip()
    base = compile_structured_goal(text, snapshot)
    clause = parse_exact_mutation_v1(text)
    bindings, resolution = _resolve_binding(snapshot, clause)
    contract = WebArenaGoalContractV1(
        base=base, reply_payload=None, payload_bindings=bindings, payload_resolution=resolution
    )
    contract.validate_provenance()
    return ExactMutationCompilationV1(contract, clause, resolution)


def compile_exact_mutation_inventory_v1(
    snapshot: SemanticSnapshot, goal: str, *, compilation: ExactMutationCompilationV1 | None = None
) -> V4ActionInventory:
    if compilation is None:
        compilation = compile_exact_mutation_goal_v1(goal, snapshot)
    elif compilation.goal_contract.goal != str(goal).strip():
        raise ValueError("persisted exact-mutation goal does not match instruction")
    return compile_webarena_inventory_v1(snapshot, goal, goal_contract=compilation.goal_contract)


def _candidate_is_submit_like(candidate: ActionCandidateV4) -> bool:
    return bool(
        candidate.transaction_kind is None
        and candidate.role.casefold() == "button"
        and _submit_like_label(candidate.label)
    )


def certify_exact_mutation_commit_v1(
    *,
    current: SemanticSnapshot,
    compilation: ExactMutationCompilationV1,
    candidate: ActionCandidateV4,
    inventory: tuple[ActionCandidateV4, ...],
    active_transactions: tuple[Any, ...],
    resolved_semantic_bids: tuple[str, ...] = (),
    quarantined_commit_keys: frozenset[tuple[object, ...]] = frozenset(),
) -> CommitCertificateV4:
    """Certify only one same-form action after the exact field is active."""
    goal = compilation.goal_contract
    base = certify_commit_v8(
        current=current,
        goal=goal,
        candidate=candidate,
        inventory=inventory,
        active_transactions=active_transactions,
        resolved_semantic_bids=resolved_semantic_bids,
        quarantined_commit_keys=quarantined_commit_keys,
    )
    if not compilation.allowed or not _candidate_is_submit_like(candidate):
        return base
    binding_bids = tuple(sorted((row.bid for row in compilation.goal_contract.payload_bindings)))
    denied = CertificateDenial("exact_mutation_form_action", binding_bids)
    rows_by_bid = {row.bid: row for row in inventory}
    if len(rows_by_bid) != len(inventory) or rows_by_bid.get(candidate.bid) != candidate:
        return denied("candidate is absent from the unique current inventory")
    if not current.is_effectively_visible(candidate.bid):
        return denied("exact-mutation form action is not currently visible")
    payload_rejection = active_payload_rejection(
        current, goal, active_transactions, resolved_semantic_bids, denied
    )
    if payload_rejection is not None:
        return payload_rejection
    candidate_form = _nearest_dom_form(current, candidate.bid)
    expected_forms = {binding.form_bid for binding in goal.payload_bindings}
    if candidate_form is None or expected_forms != {candidate_form.bid}:
        return denied("the exact-value field and action are not in one public form")
    expected_submit_bids = {binding.submit_bid for binding in goal.payload_bindings}
    if expected_submit_bids != {candidate.bid}:
        return denied("the current action differs from the bound public form action")
    competing = _competing_surface_actions_v1(current, inventory, candidate_form)
    if competing != (candidate.bid,):
        return CommitCertificateV4(
            False,
            "exact-mutation form action is ambiguous",
            GroundingDecisionV4(
                False,
                "exact-mutation form action is ambiguous",
                "exact_mutation_form_action",
                binding_bids,
                competing,
            ),
        )
    return finalize_mutation_commit(
        current=current,
        candidate=candidate,
        active_transactions=active_transactions,
        quarantined_commit_keys=quarantined_commit_keys,
        denied=denied,
        competing=competing,
        messages=CommitMessages(
            "one same-form public action is grounded by the active exact-value transaction",
            "the same exact-mutation action already had zero public effect",
            False,
        ),
    )


def _competing_surface_actions_v1(
    current: SemanticSnapshot, inventory: tuple[ActionCandidateV4, ...], candidate_form: SemanticElement
) -> tuple[str, ...]:
    return tuple(
        sorted(
            (
                row.bid
                for row in inventory
                if _candidate_is_submit_like(row)
                and (form := _nearest_dom_form(current, row.bid)) is not None
                and (form.bid == candidate_form.bid)
            )
        )
    )


def _mutation_value_span(text: str, start: int) -> tuple[int, int] | None:
    value_start = start
    while value_start < len(text) and text[value_start].isspace():
        value_start += 1
    if value_start >= len(text):
        return None
    if text[value_start] in {'"', "“"}:
        closing = '"' if text[value_start] == '"' else "”"
        value_end = text.find(closing, value_start + 1)
        if value_end < 0:
            return None
        value_start += 1
    else:
        value_end = len(text)
        while value_end > value_start and text[value_end - 1] in ". \t\r\n":
            value_end -= 1
    return (value_start, value_end)
