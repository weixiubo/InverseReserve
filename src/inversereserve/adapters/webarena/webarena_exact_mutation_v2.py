"""Exact public mutation with a fail-closed form-less edit-surface fallback.

The frozen V1 adapter requires a literal DOM ``form``.  Some public admin
interfaces expose an inline editable row with one target field, one Save
button, and one Cancel button but no form element.  V2 preserves V1 whenever a
form binds and otherwise accepts only one bounded public edit surface with an
unambiguous target and commit action.  It uses no site identity, route,
selector, task ID, reward, evaluator field, or hidden state.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from inversereserve.adapters.webarena.certificate_denial import CertificateDenial
from inversereserve.adapters.webarena.commit_finalization import CommitMessages, finalize_mutation_commit
from inversereserve.adapters.webarena.payload_checks import active_payload_rejection
from inversereserve.adapters.webarena.webarena_exact_mutation_v1 import (
    ExactMutationClauseV1,
    ExactMutationCompilationV1,
    _anchor_score,
    _candidate_is_submit_like,
    _editable,
    _label_tokens,
    _submit_like_label,
    certify_exact_mutation_commit_v1,
    compile_exact_mutation_goal_v1,
    parse_exact_mutation_v1,
)
from inversereserve.adapters.webarena.webarena_goal_adapter_v1 import (
    PublicPayloadBindingV1,
    WebArenaGoalContractV1,
    _field_label,
    _nearest_dom_form,
    _normalized,
    _public_boolean,
    compile_webarena_inventory_v1,
)
from inversereserve.contracts.goal_contracts_v4 import StructuredGoalContract
from inversereserve.contracts.pact_grounding_v4 import CommitCertificateV4, GroundingDecisionV4
from inversereserve.contracts.pact_grounding_v8 import (
    certify_commit_v8,
)
from inversereserve.models.structured_planner_v4 import ActionCandidateV4, V4ActionInventory
from inversereserve.observations.typed_observation import SemanticElement, SemanticSnapshot

CANCEL_PREFIXES_V2 = frozenset({"cancel", "close", "discard"})
MAXIMUM_SURFACE_DEPTH_V2 = 6
MAXIMUM_SURFACE_DESCENDANTS_V2 = 1024


def _first_token(value: object) -> str:
    normalized = _normalized(value)
    return normalized.split()[0] if normalized else ""


def _button_like(element: SemanticElement) -> bool:
    return bool(
        (element.role.casefold() == "button" or element.dom_tag.casefold() == "button")
        and element.clickable
        and (not _public_boolean(element, "disabled"))
    )


def _dom_chain(snapshot: SemanticSnapshot, bid: str) -> tuple[SemanticElement, ...]:
    element = snapshot.get(bid)
    if element is None:
        return ()
    return (element,) + snapshot.ancestors(bid, relation="dom")


def _lowest_common_dom_ancestor(
    snapshot: SemanticSnapshot, first_bid: str, second_bid: str
) -> tuple[SemanticElement, int, int] | None:
    first = _dom_chain(snapshot, first_bid)
    second = _dom_chain(snapshot, second_bid)
    second_depth = {element.bid: index for index, element in enumerate(second)}
    for first_index, element in enumerate(first):
        if element.bid in second_depth:
            return (element, first_index, second_depth[element.bid])
    return None


def _surface_descendant_bids(snapshot: SemanticSnapshot, surface_bid: str) -> frozenset[str]:
    return frozenset(
        {str(surface_bid)} | {element.bid for element in snapshot.descendants(surface_bid, relation="dom")}
    )


def _visible_surface_actions(
    snapshot: SemanticSnapshot, surface_bid: str
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    descendants = _surface_descendant_bids(snapshot, surface_bid)
    commits: list[str] = []
    cancels: list[str] = []
    for bid in descendants:
        element = snapshot.get(bid)
        if element is None or not snapshot.is_effectively_visible(bid) or (not _button_like(element)):
            continue
        label = element.name or element.subtree_text
        if _submit_like_label(label):
            commits.append(bid)
        if _first_token(label) in CANCEL_PREFIXES_V2:
            cancels.append(bid)
    return (tuple(sorted(set(commits))), tuple(sorted(set(cancels))))


@dataclass(frozen=True)
class PublicEditSurfaceEvidenceV2:
    kind: str
    surface_bid: str
    submit_bid: str
    cancel_bids: tuple[str, ...]
    target_depth: int
    submit_depth: int
    descendant_count: int

    def record(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "surface_bid": self.surface_bid,
            "submit_bid": self.submit_bid,
            "cancel_bids": list(self.cancel_bids),
            "target_depth": self.target_depth,
            "submit_depth": self.submit_depth,
            "descendant_count": self.descendant_count,
            "uses_site_specific_selector": False,
            "uses_site_specific_route": False,
            "uses_hidden_state": False,
        }


@dataclass(frozen=True)
class ExactMutationGoalContractV2(WebArenaGoalContractV1):
    """Prefer the exact binding over a conflicting generic parse on its bid."""

    @property
    def field_assignments(self) -> tuple[Any, ...]:
        bound_bids = {binding.bid for binding in self.payload_bindings}
        rows = [row for row in self.base.field_assignments if str(row.bid) not in bound_bids]
        rows.extend(self.payload_bindings)
        return tuple(rows)


@dataclass(frozen=True)
class ExactMutationCompilationV2:
    goal_contract: ExactMutationGoalContractV2
    clause: ExactMutationClauseV1 | None
    resolution: str
    surface: PublicEditSurfaceEvidenceV2 | None

    @property
    def allowed(self) -> bool:
        return bool(
            self.clause and len(self.goal_contract.payload_bindings) == 1 and (self.surface is not None)
        )

    def record(self) -> dict[str, object]:
        record = self.goal_contract.record()
        record["webarena_exact_mutation_v2"] = {
            "clause": None if self.clause is None else self.clause.record(),
            "resolution": self.resolution,
            "allowed": self.allowed,
            "surface": None if self.surface is None else self.surface.record(),
            "uses_task_id": False,
            "uses_evaluator": False,
            "uses_reward": False,
            "uses_hidden_state": False,
            "uses_site_specific_selector": False,
            "uses_site_specific_route": False,
        }
        return record


def _contract(
    *, base: StructuredGoalContract, bindings: tuple[PublicPayloadBindingV1, ...], resolution: str
) -> ExactMutationGoalContractV2:
    contract = ExactMutationGoalContractV2(
        base=base, reply_payload=None, payload_bindings=bindings, payload_resolution=resolution
    )
    contract.validate_provenance()
    return contract


def _form_evidence(
    snapshot: SemanticSnapshot, binding: PublicPayloadBindingV1
) -> PublicEditSurfaceEvidenceV2:
    target_chain = _dom_chain(snapshot, binding.bid)
    submit_chain = _dom_chain(snapshot, binding.submit_bid)
    target_depth = next((index for index, row in enumerate(target_chain) if row.bid == binding.form_bid))
    submit_depth = next((index for index, row in enumerate(submit_chain) if row.bid == binding.form_bid))
    return PublicEditSurfaceEvidenceV2(
        "dom_form",
        binding.form_bid,
        binding.submit_bid,
        (),
        target_depth,
        submit_depth,
        len(snapshot.descendants(binding.form_bid, relation="dom")),
    )


def _resolve_formless_surface(
    snapshot: SemanticSnapshot, clause: ExactMutationClauseV1 | None
) -> tuple[tuple[PublicPayloadBindingV1, ...], PublicEditSurfaceEvidenceV2 | None, str]:
    if clause is None:
        return ((), None, "instruction is outside the exact-mutation grammar")
    winners: list[SemanticElement] = []
    for element in snapshot.elements:
        if not _editable(element, snapshot):
            continue
        score = _anchor_score(clause.anchor_tokens, _label_tokens(snapshot, element))
        if score == len(clause.anchor_tokens):
            winners.append(element)
    if len(winners) != 1:
        return (
            (),
            None,
            "mutation anchor does not identify exactly one editable public field"
            if winners
            else "no visible editable public field matches the mutation anchor",
        )
    target = winners[0]
    if _nearest_dom_form(snapshot, target.bid) is not None:
        return ((), None, "the matching DOM form did not expose one safe commit action")
    solutions = _formless_surface_solutions(snapshot, target)
    unique = {
        (action.bid, surface.bid): (action, surface, cancels, target_depth, submit_depth, descendant_count)
        for action, surface, cancels, target_depth, submit_depth, descendant_count in solutions
    }
    if len(unique) != 1:
        return (
            (),
            None,
            "form-less edit surface is ambiguous"
            if unique
            else "no bounded public edit surface exposes one Save and a cancel witness",
        )
    action, surface, cancels, target_depth, submit_depth, descendant_count = next(iter(unique.values()))
    binding = PublicPayloadBindingV1(
        bid=target.bid,
        label=_field_label(snapshot, target),
        value=clause.value,
        action_span=clause.action_span,
        value_span=clause.value_span,
        form_bid=surface.bid,
        submit_bid=action.bid,
        binding_kind="exact_public_edit_surface_mutation",
    )
    evidence = PublicEditSurfaceEvidenceV2(
        "public_edit_surface", surface.bid, action.bid, cancels, target_depth, submit_depth, descendant_count
    )
    return (
        (binding,),
        evidence,
        "one bounded public edit surface binds one exact field, Save, and cancel witness",
    )


def compile_exact_mutation_goal_v2(goal: str, snapshot: SemanticSnapshot) -> ExactMutationCompilationV2:
    frozen = compile_exact_mutation_goal_v1(goal, snapshot)
    if frozen.allowed:
        bindings = tuple(frozen.goal_contract.payload_bindings)
        contract = _contract(base=frozen.goal_contract.base, bindings=bindings, resolution=frozen.resolution)
        return ExactMutationCompilationV2(
            contract, frozen.clause, frozen.resolution, _form_evidence(snapshot, bindings[0])
        )
    clause = parse_exact_mutation_v1(str(goal).strip())
    bindings, surface, resolution = _resolve_formless_surface(snapshot, clause)
    contract = _contract(base=frozen.goal_contract.base, bindings=bindings, resolution=resolution)
    return ExactMutationCompilationV2(contract, clause, resolution, surface)


def compile_exact_mutation_inventory_v2(
    snapshot: SemanticSnapshot, goal: str, *, compilation: ExactMutationCompilationV2 | None = None
) -> V4ActionInventory:
    if compilation is None:
        compilation = compile_exact_mutation_goal_v2(goal, snapshot)
    elif compilation.goal_contract.goal != str(goal).strip():
        raise ValueError("persisted exact-mutation goal does not match instruction")
    return compile_webarena_inventory_v1(snapshot, goal, goal_contract=compilation.goal_contract)


def certify_exact_mutation_commit_v2(
    *,
    current: SemanticSnapshot,
    compilation: ExactMutationCompilationV2,
    candidate: ActionCandidateV4,
    inventory: tuple[ActionCandidateV4, ...],
    active_transactions: tuple[Any, ...],
    resolved_semantic_bids: tuple[str, ...] = (),
    quarantined_commit_keys: frozenset[tuple[object, ...]] = frozenset(),
) -> CommitCertificateV4:
    if compilation.surface is None or compilation.surface.kind == "dom_form":
        legacy = ExactMutationCompilationV1(
            compilation.goal_contract, compilation.clause, compilation.resolution
        )
        return certify_exact_mutation_commit_v1(
            current=current,
            compilation=legacy,
            candidate=candidate,
            inventory=inventory,
            active_transactions=active_transactions,
            resolved_semantic_bids=resolved_semantic_bids,
            quarantined_commit_keys=quarantined_commit_keys,
        )
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
    binding_bids = tuple(sorted((row.bid for row in goal.payload_bindings)))
    denied = CertificateDenial("exact_mutation_public_edit_surface_action", binding_bids)
    if not compilation.allowed or not _candidate_is_submit_like(candidate):
        return base
    rows_by_bid = {row.bid: row for row in inventory}
    if len(rows_by_bid) != len(inventory) or rows_by_bid.get(candidate.bid) != candidate:
        return denied("candidate is absent from the unique current inventory")
    if not current.is_effectively_visible(candidate.bid):
        return denied("edit-surface action is not currently visible")
    payload_rejection = active_payload_rejection(
        current, goal, active_transactions, resolved_semantic_bids, denied
    )
    if payload_rejection is not None:
        return payload_rejection
    witness = _formless_surface_witness(current, compilation, candidate, inventory, denied)
    if isinstance(witness, CommitCertificateV4):
        return witness
    competing = witness
    return finalize_mutation_commit(
        current=current,
        candidate=candidate,
        active_transactions=active_transactions,
        quarantined_commit_keys=quarantined_commit_keys,
        denied=denied,
        competing=competing,
        messages=CommitMessages(
            "one public edit-surface action is grounded by the active exact-value transaction",
            "the same edit-surface action already had zero public effect",
            False,
        ),
    )


def _competing_surface_actions_v2(
    inventory: tuple[ActionCandidateV4, ...], surface_bids: set[str]
) -> tuple[str, ...]:
    return tuple(
        sorted((row.bid for row in inventory if row.bid in surface_bids and _candidate_is_submit_like(row)))
    )


def _formless_surface_solutions(
    snapshot: SemanticSnapshot, target: SemanticElement
) -> list[tuple[SemanticElement, SemanticElement, tuple[str, ...], int, int, int]]:
    solutions: list[tuple[SemanticElement, SemanticElement, tuple[str, ...], int, int, int]] = []
    for action in snapshot.elements:
        if (
            not snapshot.is_effectively_visible(action.bid)
            or not _button_like(action)
            or (not _submit_like_label(action.name or action.subtree_text))
        ):
            continue
        common = _lowest_common_dom_ancestor(snapshot, target.bid, action.bid)
        if common is None:
            continue
        surface, target_depth, submit_depth = common
        if (
            target_depth > MAXIMUM_SURFACE_DEPTH_V2
            or submit_depth > MAXIMUM_SURFACE_DEPTH_V2
            or surface.dom_tag.casefold() in {"html", "body"}
        ):
            continue
        descendants = snapshot.descendants(surface.bid, relation="dom")
        if len(descendants) > MAXIMUM_SURFACE_DESCENDANTS_V2:
            continue
        commits, cancels = _visible_surface_actions(snapshot, surface.bid)
        if commits != (action.bid,) or not cancels:
            continue
        solutions.append((action, surface, cancels, target_depth, submit_depth, len(descendants)))
    return solutions


def _formless_surface_witness(
    current: SemanticSnapshot,
    compilation: ExactMutationCompilationV2,
    candidate: ActionCandidateV4,
    inventory: tuple[ActionCandidateV4, ...],
    denied: CertificateDenial,
) -> tuple[str, ...] | CommitCertificateV4:
    goal = compilation.goal_contract
    binding_bids = denied.binding_bids
    assert compilation.surface is not None
    surface_bid = compilation.surface.surface_bid
    surface_bids = _surface_descendant_bids(current, surface_bid)
    if any((binding.bid not in surface_bids for binding in goal.payload_bindings)):
        return denied("the exact-value field left its bound public edit surface")
    expected_submit_bids = {binding.submit_bid for binding in goal.payload_bindings}
    if expected_submit_bids != {candidate.bid} or candidate.bid not in surface_bids:
        return denied("the current action differs from the bound edit-surface action")
    competing = _competing_surface_actions_v2(inventory, surface_bids)
    if competing != (candidate.bid,):
        return CommitCertificateV4(
            False,
            "exact-mutation edit-surface action is ambiguous",
            GroundingDecisionV4(
                False,
                "exact-mutation edit-surface action is ambiguous",
                "exact_mutation_public_edit_surface_action",
                binding_bids,
                competing,
            ),
        )
    commits, cancels = _visible_surface_actions(current, surface_bid)
    if commits != (candidate.bid,) or not cancels:
        return denied("the public edit-surface Save or cancel witness changed")
    return competing
