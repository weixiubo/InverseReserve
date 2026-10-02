"""Public-only multi-field WebArena adapter for InverseReserve.

The adapter binds every target value to one visible public field inside one
DOM form.  It uses registered instruction grammars, verbatim instruction
spans, and public AX/DOM labels, roles, values, visibility, and topology.  It
does not receive task or template identifiers, site identity, routes,
selectors, evaluator fields, rewards, network traces, or hidden state.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from inversereserve.adapters.webarena.certificate_denial import CertificateDenial
from inversereserve.adapters.webarena.webarena_exact_mutation_v1 import _editable
from inversereserve.adapters.webarena.webarena_exact_mutation_v4 import _direct_label_tokens_v4
from inversereserve.adapters.webarena.webarena_goal_adapter_v1 import (
    PublicPayloadBindingV1,
    WebArenaGoalContractV1,
    _active_payload_bids,
    _field_label,
    _nearest_dom_form,
    _normalized,
    _public_value,
    compile_webarena_inventory_v1,
)
from inversereserve.contracts.goal_contracts_v4 import GoalSpan, compile_structured_goal
from inversereserve.contracts.pact_grounding_v4 import CommitCertificateV4, GroundingDecisionV4
from inversereserve.contracts.pact_grounding_v8 import (
    certify_commit_v8,
    commit_attempt_key_v8,
    unresolved_blocking_transactions_v8,
)
from inversereserve.contracts.transaction_actions_v4 import ContractActionV4
from inversereserve.contracts.typed_contracts_v4 import TEXT_INPUT_ROLES
from inversereserve.models.structured_planner_v4 import ActionCandidateV4, V4ActionInventory
from inversereserve.observations.typed_observation import SemanticElement, SemanticSnapshot

FORUM_RE = re.compile(
    '^\\s*(?P<action>create\\s+a\\s+new\\s+forum)\\s+with\\s+name\\s+and\\s+title\\s+[\\"“](?P<identity>[^\\"“”]{1,128})[\\"”]\\s*,\\s*description\\s+[\\"“](?P<description>[^\\"“”]{1,512})[\\"”]\\s*,\\s*and\\s+sidebar\\s+[\\"“](?P<sidebar>[^\\"“”]{1,512})[\\"”]\\s*\\.?\\s*$',
    re.IGNORECASE,
)
MILESTONE_RE = re.compile(
    '^\\s*(?P<action>create\\s+a\\s+milestone)\\s+in\\s+the\\s+current\\s+repo\\s+with\\s+title\\s+[\\"“](?P<title>[^\\"“”]{1,128})[\\"”].*?\\bstarting\\s+on\\s+(?P<start>[A-Za-z]+\\s+\\d{1,2},\\s+\\d{4})\\s+and\\s+ending\\s+(?:on\\s+(?P<end>[A-Za-z]+\\s+\\d{1,2},\\s+\\d{4})|in\\s+(?P<days>\\d{1,3})\\s+days\\s*\\(inclusive\\))\\s*\\.?\\s*$',
    re.IGNORECASE,
)
REDDIT_POST_RES = (
    re.compile(
        '^\\s*(?P<action>ask\\s+for\\s+advice)\\b.*?\\btitle\\s+it\\s+[\\"“](?P<title>[^\\"“”]{1,256})[\\"”]\\s+and\\s+in\\s+post\\s+details\\s+ask\\s+[\\"“](?P<body>[^\\"“”]{1,1024})[\\"”]\\s*\\.?\\s*$',
        re.IGNORECASE,
    ),
    re.compile(
        '^\\s*(?P<action>create\\s+a\\s+discussion\\s+post)\\s+titled\\s+[\\"“](?P<title>[^\\"“”]{1,256})[\\"”].*?\\bsimple\\s+prompt\\s*,\\s*[\\"“](?P<body>[^\\"“”]{1,1024})[\\"”]\\s*\\.?\\s*$',
        re.IGNORECASE,
    ),
    re.compile(
        '^\\s*(?P<action>create\\s+a\\s+post)\\b.*?\\btitle\\s+it\\s+[\\"“](?P<title>[^\\"“”]{1,256})[\\"”]\\s+and\\s+in\\s+post\\s+details\\s+ask\\s+[\\"“](?P<body>[^\\"“”]{1,1024})[\\"”]\\s*\\.?\\s*$',
        re.IGNORECASE,
    ),
    re.compile(
        '^\\s*(?P<action>post\\s+a\\s+notice)\\b.*?\\btitled\\s+[\\"“](?P<title>[^\\"“”]{1,256})[\\"”]\\s*\\.\\s*set\\s+post\\s+details\\s+to\\s+[\\"“](?P<body>[^\\"“”]{1,1024})[\\"”]\\s*\\.?\\s*$',
        re.IGNORECASE,
    ),
)
DATE_FORMAT = "%B %d, %Y"
SUBMIT_PREFIXES = frozenset({"create", "save", "submit", "update"})


def _span(text: str, match: re.Match[str], group: str) -> GoalSpan:
    start, end = match.span(group)
    return GoalSpan(text[start:end], start, end)


def _iso_date(value: str) -> str:
    return datetime.strptime(value, DATE_FORMAT).date().isoformat()


@dataclass(frozen=True)
class MultiFieldSpecV1:
    key: str
    value: str
    anchor_groups: tuple[tuple[str, ...], ...]
    action_span: GoalSpan
    value_span: GoalSpan
    normalization: str

    def record(self) -> dict[str, object]:
        return {
            "key": self.key,
            "value": self.value,
            "anchor_groups": [list(group) for group in self.anchor_groups],
            "action_span": self.action_span.record(),
            "value_span": self.value_span.record(),
            "normalization": self.normalization,
        }


@dataclass(frozen=True)
class MultiFieldClauseV1:
    kind: str
    fields: tuple[MultiFieldSpecV1, ...]

    def record(self) -> dict[str, object]:
        return {"kind": self.kind, "fields": [field.record() for field in self.fields]}


def parse_multifield_goal_v1(goal: str) -> MultiFieldClauseV1 | None:
    """Parse one registered multi-field grammar from the verbatim instruction."""
    text = str(goal).strip()
    forum = FORUM_RE.fullmatch(text)
    if forum is not None:
        action = _span(text, forum, "action")
        identity = _span(text, forum, "identity")
        description = _span(text, forum, "description")
        sidebar = _span(text, forum, "sidebar")
        return MultiFieldClauseV1(
            "reddit_forum_creation",
            (
                MultiFieldSpecV1("name", identity.text, (("name",),), action, identity, "verbatim"),
                MultiFieldSpecV1("title", identity.text, (("title",),), action, identity, "verbatim"),
                MultiFieldSpecV1(
                    "description", description.text, (("description",),), action, description, "verbatim"
                ),
                MultiFieldSpecV1("sidebar", sidebar.text, (("sidebar",),), action, sidebar, "verbatim"),
            ),
        )
    for pattern in REDDIT_POST_RES:
        post = pattern.fullmatch(text)
        if post is None:
            continue
        action = _span(text, post, "action")
        title = _span(text, post, "title")
        body = _span(text, post, "body")
        return MultiFieldClauseV1(
            "reddit_post_creation",
            (
                MultiFieldSpecV1("body", body.text, (("body",),), action, body, "verbatim"),
                MultiFieldSpecV1("title", title.text, (("title",),), action, title, "verbatim"),
            ),
        )
    milestone = MILESTONE_RE.fullmatch(text)
    if milestone is None:
        return None
    action = _span(text, milestone, "action")
    title = _span(text, milestone, "title")
    start = _span(text, milestone, "start")
    start_date = datetime.strptime(start.text, DATE_FORMAT).date()
    if milestone.group("end") is not None:
        due = _span(text, milestone, "end")
        due_value = _iso_date(due.text)
        due_normalization = "explicit_date_to_iso"
    else:
        due = _span(text, milestone, "days")
        days = int(due.text)
        if not 1 <= days <= 90:
            return None
        due_value = (start_date + timedelta(days=days - 1)).isoformat()
        due_normalization = "inclusive_day_count_from_start_to_iso"
    return MultiFieldClauseV1(
        "gitlab_milestone_creation",
        (
            MultiFieldSpecV1("title", title.text, (("title",),), action, title, "verbatim"),
            MultiFieldSpecV1(
                "start_date",
                start_date.isoformat(),
                (("start", "starts"), ("date",)),
                action,
                start,
                "explicit_date_to_iso",
            ),
            MultiFieldSpecV1(
                "due_date", due_value, (("due", "end"), ("date",)), action, due, due_normalization
            ),
        ),
    )


def _matches_field(snapshot: SemanticSnapshot, element: SemanticElement, field: MultiFieldSpecV1) -> bool:
    tokens = _direct_label_tokens_v4(snapshot, element)
    return all((tokens.intersection(group) for group in field.anchor_groups))


def _submit_like(element: SemanticElement) -> bool:
    label = _normalized(element.name or element.subtree_text)
    first = label.split()[0] if label else ""
    return bool(element.role.casefold() == "button" and element.clickable and (first in SUBMIT_PREFIXES))


def _public_dom_action_available(snapshot: SemanticSnapshot, element: SemanticElement) -> bool:
    """Accept an offscreen action only when public DOM state says it is usable."""
    if not element.clickable:
        return False
    for candidate in (element,) + snapshot.ancestors(element.bid, relation="dom"):
        attributes = dict(candidate.dom_attributes)
        if str(attributes.get("aria-hidden", "")).casefold() == "true":
            return False
        if "hidden" in attributes:
            return False
        style = re.sub("\\s+", "", str(attributes.get("style", ""))).casefold()
        if "display:none" in style or "visibility:hidden" in style:
            return False
    return True


def _visible_submit_bids(snapshot: SemanticSnapshot, form_bid: str) -> tuple[str, ...]:
    return tuple(
        sorted(
            {
                element.bid
                for element in snapshot.descendants(form_bid, relation="dom")
                if _submit_like(element) and _public_dom_action_available(snapshot, element)
            }
        )
    )


def _resolve_bindings(
    snapshot: SemanticSnapshot, clause: MultiFieldClauseV1 | None
) -> tuple[tuple[PublicPayloadBindingV1, ...], str]:
    if clause is None:
        return ((), "instruction is outside the frozen multi-field grammars")
    resolved: list[tuple[MultiFieldSpecV1, SemanticElement]] = []
    for field in clause.fields:
        candidates = _matching_text_fields(snapshot, field)
        if len(candidates) != 1:
            return ((), f"public field {field.key} resolved to {len(candidates)} visible editable controls")
        resolved.append((field, candidates[0]))
    bids = [element.bid for _field, element in resolved]
    if len(set(bids)) != len(bids):
        return ((), "two instruction fields resolved to one public control")
    forms = [_nearest_dom_form(snapshot, bid) for bid in bids]
    if any((form is None for form in forms)):
        return ((), "a bound public field is outside a DOM form")
    form_bids = {form.bid for form in forms if form is not None}
    if len(form_bids) != 1:
        return ((), "bound public fields do not share one DOM form")
    form_bid = next(iter(form_bids))
    submit_bids = _visible_submit_bids(snapshot, form_bid)
    if len(submit_bids) != 1:
        return ((), "the shared public form does not expose exactly one create/save/submit action")
    submit_bid = submit_bids[0]
    bindings = tuple(
        (
            PublicPayloadBindingV1(
                bid=element.bid,
                label=_field_label(snapshot, element),
                value=field.value,
                action_span=field.action_span,
                value_span=field.value_span,
                form_bid=form_bid,
                submit_bid=submit_bid,
                binding_kind=f"multifield_{clause.kind}_{field.key}",
            )
            for field, element in resolved
        )
    )
    return (bindings, f"one public form binds all {len(bindings)} declared fields and one commit")


@dataclass(frozen=True)
class MultiFieldCompilationV1:
    goal_contract: WebArenaGoalContractV1
    clause: MultiFieldClauseV1 | None
    resolution: str

    @property
    def allowed(self) -> bool:
        return bool(
            self.clause is not None
            and len(self.goal_contract.payload_bindings) == len(self.clause.fields)
            and (len(self.clause.fields) >= 2)
        )

    def record(self) -> dict[str, object]:
        record = self.goal_contract.record()
        record["webarena_multifield_v1"] = {
            "clause": None if self.clause is None else self.clause.record(),
            "resolution": self.resolution,
            "allowed": self.allowed,
            "uses_task_id": False,
            "uses_template_id": False,
            "uses_site_identity": False,
            "uses_site_specific_route": False,
            "uses_site_specific_selector": False,
            "uses_evaluator": False,
            "uses_reward": False,
            "uses_network_log": False,
            "uses_hidden_state": False,
        }
        return record


def compile_multifield_goal_v1(goal: str, snapshot: SemanticSnapshot) -> MultiFieldCompilationV1:
    text = str(goal).strip()
    base = compile_structured_goal(text, snapshot)
    clause = parse_multifield_goal_v1(text)
    bindings, resolution = _resolve_bindings(snapshot, clause)
    contract = WebArenaGoalContractV1(
        base=base, reply_payload=None, payload_bindings=bindings, payload_resolution=resolution
    )
    contract.validate_provenance()
    return MultiFieldCompilationV1(contract, clause, resolution)


def compile_multifield_inventory_v1(
    snapshot: SemanticSnapshot, goal: str, *, compilation: MultiFieldCompilationV1 | None = None
) -> V4ActionInventory:
    if compilation is None:
        compilation = compile_multifield_goal_v1(goal, snapshot)
    elif compilation.goal_contract.goal != str(goal).strip():
        raise ValueError("persisted multi-field goal does not match instruction")
    inventory = compile_webarena_inventory_v1(snapshot, goal, goal_contract=compilation.goal_contract)
    rows = {row.bid: row for row in inventory.candidates}
    submit_bids = {binding.submit_bid for binding in compilation.goal_contract.payload_bindings}
    for submit_bid in submit_bids:
        if submit_bid in rows:
            continue
        element = snapshot.get(submit_bid)
        if (
            element is None
            or not _submit_like(element)
            or (not _public_dom_action_available(snapshot, element))
        ):
            continue
        rows[submit_bid] = ActionCandidateV4(
            bid=submit_bid,
            action=ContractActionV4("click", submit_bid),
            role=element.role or element.dom_tag,
            label=element.name or element.subtree_text,
            state=(),
            transaction_kind=None,
            semantic_bid=submit_bid,
            parent_bid=element.ax_parent_bid or element.dom_parent_bid,
            publicly_actionable_offscreen=not snapshot.is_effectively_visible(submit_bid),
        )
    candidates = tuple(
        sorted(
            rows.values(),
            key=lambda row: (row.parent_bid or "", row.semantic_bid, row.bid, row.action.operation),
        )
    )
    return V4ActionInventory(
        inventory.allowed, inventory.reason, inventory.goal_contract, candidates, inventory.contracts
    )


def certify_multifield_commit_v1(
    *,
    current: SemanticSnapshot,
    compilation: MultiFieldCompilationV1,
    candidate: ActionCandidateV4,
    inventory: tuple[ActionCandidateV4, ...],
    active_transactions: tuple[Any, ...],
    quarantined_commit_keys: frozenset[tuple[object, ...]] = frozenset(),
) -> CommitCertificateV4:
    """Certify one shared-form commit after every declared field is active."""
    goal = compilation.goal_contract
    base = certify_commit_v8(
        current=current,
        goal=goal,
        candidate=candidate,
        inventory=inventory,
        active_transactions=active_transactions,
        quarantined_commit_keys=quarantined_commit_keys,
    )
    binding_bids = tuple(sorted((row.bid for row in goal.payload_bindings)))
    denied = CertificateDenial("multifield_form_action", binding_bids)
    if not compilation.allowed or not _submit_like_candidate(candidate):
        return base
    rows_by_bid = {row.bid: row for row in inventory}
    if len(rows_by_bid) != len(inventory) or rows_by_bid.get(candidate.bid) != candidate:
        return denied("candidate is absent from the unique current inventory")
    action = current.get(candidate.bid)
    if action is None or not _public_dom_action_available(current, action):
        return denied("multi-field form action is not publicly actionable")
    payload_rejection = _multifield_payload_rejection(current, goal, active_transactions, denied)
    if payload_rejection is not None:
        return payload_rejection
    candidate_form = _nearest_dom_form(current, candidate.bid)
    expected_forms = _payload_form_bids(goal)
    if candidate_form is None or expected_forms != {candidate_form.bid}:
        return denied("the fields and action are not in one public form")
    if {binding.submit_bid for binding in goal.payload_bindings} != {candidate.bid}:
        return denied("the current action differs from the bound form action")
    competing = _competing_multifield_actions(current, candidate_form, inventory)
    if competing != (candidate.bid,):
        return denied("multi-field form action is ambiguous", competing=competing)
    return _finalize_multifield_commit(
        current, candidate, active_transactions, quarantined_commit_keys, denied, competing
    )


def _submit_like_candidate(candidate: ActionCandidateV4) -> bool:
    label = _normalized(candidate.label)
    first = label.split()[0] if label else ""
    return bool(
        candidate.transaction_kind is None
        and candidate.role.casefold() == "button"
        and (first in SUBMIT_PREFIXES)
    )


__all__ = [
    "MultiFieldClauseV1",
    "MultiFieldCompilationV1",
    "MultiFieldSpecV1",
    "certify_multifield_commit_v1",
    "compile_multifield_goal_v1",
    "compile_multifield_inventory_v1",
    "parse_multifield_goal_v1",
]


def _matching_text_fields(snapshot: SemanticSnapshot, field: MultiFieldSpecV1) -> list[SemanticElement]:
    return [
        element
        for element in snapshot.elements
        if _editable(element, snapshot)
        and element.role.casefold() in TEXT_INPUT_ROLES
        and (element.dom_tag.casefold() in {"input", "textarea"})
        and _matches_field(snapshot, element, field)
    ]


def _finalize_multifield_commit(
    current: SemanticSnapshot,
    candidate: ActionCandidateV4,
    active_transactions: tuple[Any, ...],
    quarantined_commit_keys: frozenset[tuple[object, ...]],
    denied: CertificateDenial,
    competing: tuple[str, ...],
) -> CommitCertificateV4:
    binding_bids = denied.binding_bids
    try:
        key = commit_attempt_key_v8(
            current=current, action=candidate.action, active_transactions=active_transactions
        )
    except Exception as error:
        return denied(f"public effect key failed: {type(error).__name__}")
    if key in quarantined_commit_keys:
        return denied("the same multi-field action already had zero public effect")
    grounding = GroundingDecisionV4(
        True,
        "one shared-form public action is grounded by all active field transactions",
        "multifield_form_action",
        binding_bids,
        competing,
        candidate.bid,
    )
    return CommitCertificateV4(True, grounding.reason, grounding, candidate.action, key[0], key[1])


def _competing_multifield_actions(
    current: SemanticSnapshot, candidate_form: SemanticElement, inventory: tuple[ActionCandidateV4, ...]
) -> tuple[str, ...]:
    return tuple(
        sorted(
            (
                row.bid
                for row in inventory
                if _submit_like_candidate(row)
                and (form := _nearest_dom_form(current, row.bid)) is not None
                and (form.bid == candidate_form.bid)
            )
        )
    )


def _multifield_payload_rejection(
    current: SemanticSnapshot,
    goal: WebArenaGoalContractV1,
    active_transactions: tuple[Any, ...],
    denied: CertificateDenial,
) -> CommitCertificateV4 | None:
    binding_bids = denied.binding_bids
    blockers = unresolved_blocking_transactions_v8(active_transactions, ())
    if blockers:
        return denied("a blocking typed overlay remains unresolved")
    if _active_payload_bids(active_transactions, goal) != binding_bids:
        return denied("not every declared multi-field transaction is active")
    if any(
        (
            _normalized(_public_value(current, binding.bid)) != _normalized(binding.value)
            for binding in goal.payload_bindings
        )
    ):
        return denied("a current public field value differs from the instruction")
    return None


def _payload_form_bids(goal: WebArenaGoalContractV1) -> set[str]:
    return {binding.form_bid for binding in goal.payload_bindings}
