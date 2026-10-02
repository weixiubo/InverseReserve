"""Exact public mutation with scoped field-label binding.

V3 correctly projects standard control semantics, but its inherited label
matcher may inherit an entire form's accessibility text into every input.
That is conservative yet too coarse for ordinary multi-field profile forms.
V4 keeps the frozen V3 path whenever it binds and otherwise retries only with
public, field-local evidence: the control's own accessible/DOM attributes,
an explicitly associated ``label``, and finally one small DOM wrapper.

No task identifier, site identity, route, selector, evaluator field, reward,
network trace, or hidden state enters the binding.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from inversereserve.adapters.webarena.webarena_exact_mutation_v1 import (
    ExactMutationClauseV1,
    _anchor_score,
    _editable,
    _field_label,
    _nearest_dom_form,
    _tokens,
    _visible_submit_bids,
    parse_exact_mutation_v1,
)
from inversereserve.adapters.webarena.webarena_exact_mutation_v2 import (
    ExactMutationCompilationV2,
    _contract,
    _form_evidence,
    compile_exact_mutation_goal_v2,
    compile_exact_mutation_inventory_v2,
)
from inversereserve.adapters.webarena.webarena_exact_mutation_v3 import (
    ExactMutationCompilationV3,
    ExactMutationProjectionEvidenceV3,
    certify_exact_mutation_commit_v3,
    project_exact_mutation_snapshot_v3,
)
from inversereserve.adapters.webarena.webarena_goal_adapter_v1 import PublicPayloadBindingV1
from inversereserve.contracts.pact_grounding_v4 import CommitCertificateV4
from inversereserve.models.structured_planner_v4 import ActionCandidateV4, V4ActionInventory
from inversereserve.observations.typed_observation import SemanticElement, SemanticSnapshot

MAXIMUM_LOCAL_LABEL_DESCENDANTS_V4 = 32


def _normalized(value: object) -> str:
    return " ".join(str(value or "").casefold().split())


def _tokens_from(values: list[object]) -> set[str]:
    return {token for value in values for token in _tokens(value)}


def _direct_label_tokens_v4(
    snapshot: SemanticSnapshot,
    element: SemanticElement,
) -> set[str]:
    """Use only evidence explicitly attached to one public control."""

    values: list[object] = [
        element.name,
        element.subtree_text,
        element.dom_attribute("placeholder", ""),
        element.dom_attribute("aria-label", ""),
        element.dom_attribute("name", ""),
        element.dom_attribute("id", ""),
    ]
    element_id = _normalized(element.dom_attribute("id", ""))
    labelled_by = {token for token in str(element.dom_attribute("aria-labelledby", "")).split() if token}
    for candidate in snapshot.elements:
        if not snapshot.is_effectively_visible(candidate.bid):
            continue
        candidate_id = str(candidate.dom_attribute("id", ""))
        explicit_for = _normalized(candidate.dom_attribute("for", ""))
        associated = bool(
            (element_id and candidate.dom_tag.casefold() == "label" and explicit_for == element_id)
            or (candidate_id and candidate_id in labelled_by)
        )
        if associated:
            values.extend((candidate.name, candidate.subtree_text))
    return _tokens_from(values)


def _local_wrapper_tokens_v4(
    snapshot: SemanticSnapshot,
    element: SemanticElement,
) -> set[str]:
    """Return one bounded, non-form DOM wrapper's public text."""

    for ancestor in snapshot.ancestors(element.bid, relation="dom"):
        if ancestor.dom_tag.casefold() == "form":
            break
        descendants = snapshot.descendants(ancestor.bid, relation="dom")
        if len(descendants) <= MAXIMUM_LOCAL_LABEL_DESCENDANTS_V4:
            return _tokens_from([ancestor.name, ancestor.subtree_text])
    return set()


@dataclass(frozen=True)
class ScopedFieldBindingEvidenceV4:
    direct_match_bids: tuple[str, ...]
    local_wrapper_match_bids: tuple[str, ...]
    winning_bid: str | None
    resolution_tier: str

    def record(self) -> dict[str, object]:
        return {
            "direct_match_bids": list(self.direct_match_bids),
            "local_wrapper_match_bids": list(self.local_wrapper_match_bids),
            "winning_bid": self.winning_bid,
            "resolution_tier": self.resolution_tier,
            "maximum_local_label_descendants": (MAXIMUM_LOCAL_LABEL_DESCENDANTS_V4),
            "uses_public_accessible_name": True,
            "uses_public_dom_attributes": True,
            "uses_explicit_label_association": True,
            "uses_site_identity": False,
            "uses_site_specific_selector": False,
            "uses_site_specific_route": False,
            "uses_task_id": False,
            "uses_evaluator": False,
            "uses_reward": False,
            "uses_network_log": False,
            "uses_hidden_state": False,
        }


def _matching_bids(
    snapshot: SemanticSnapshot,
    clause: ExactMutationClauseV1,
    *,
    include_local_wrapper: bool,
) -> tuple[str, ...]:
    matches: list[str] = []
    for element in snapshot.elements:
        if not _editable(element, snapshot):
            continue
        labels = _direct_label_tokens_v4(snapshot, element)
        if include_local_wrapper:
            labels |= _local_wrapper_tokens_v4(snapshot, element)
        if _anchor_score(clause.anchor_tokens, labels) == len(clause.anchor_tokens):
            matches.append(element.bid)
    return tuple(sorted(matches))


def _resolve_scoped_form_v4(
    snapshot: SemanticSnapshot,
    clause: ExactMutationClauseV1 | None,
) -> tuple[
    tuple[PublicPayloadBindingV1, ...],
    Any | None,
    str,
    ScopedFieldBindingEvidenceV4,
]:
    if clause is None:
        evidence = ScopedFieldBindingEvidenceV4((), (), None, "outside_grammar")
        return (), None, "instruction is outside the exact-mutation grammar", evidence

    direct = _matching_bids(snapshot, clause, include_local_wrapper=False)
    local: tuple[str, ...] = ()
    tier = "direct_public_label"
    winners = direct
    if not winners:
        local = _matching_bids(snapshot, clause, include_local_wrapper=True)
        winners = local
        tier = "bounded_local_wrapper"
    if len(winners) != 1:
        evidence = ScopedFieldBindingEvidenceV4(
            direct,
            local,
            None,
            "ambiguous" if winners else "no_match",
        )
        reason = (
            "scoped public labels identify multiple editable fields"
            if winners
            else "no scoped public label matches the mutation anchor"
        )
        return (), None, reason, evidence

    target = snapshot.get(winners[0])
    if target is None:
        raise ValueError("scoped exact-mutation target disappeared")
    form = _nearest_dom_form(snapshot, target.bid)
    if form is None:
        evidence = ScopedFieldBindingEvidenceV4(direct, local, None, tier)
        return (), None, "the scoped public field is not inside a DOM form", evidence
    submits = _visible_submit_bids(snapshot, form.bid)
    if len(submits) != 1:
        evidence = ScopedFieldBindingEvidenceV4(direct, local, None, tier)
        return (
            (),
            None,
            "the scoped public form does not expose exactly one submit action",
            evidence,
        )

    binding = PublicPayloadBindingV1(
        bid=target.bid,
        label=_field_label(snapshot, target),
        value=clause.value,
        action_span=clause.action_span,
        value_span=clause.value_span,
        form_bid=form.bid,
        submit_bid=submits[0],
        binding_kind="exact_public_scoped_field_mutation",
    )
    evidence = ScopedFieldBindingEvidenceV4(
        direct,
        local,
        target.bid,
        tier,
    )
    return (
        (binding,),
        _form_evidence(snapshot, binding),
        "one scoped public field and one same-form action bind the exact value",
        evidence,
    )


@dataclass(frozen=True)
class ExactMutationCompilationV4:
    inner: ExactMutationCompilationV2
    projection: ExactMutationProjectionEvidenceV3
    scoped_binding: ScopedFieldBindingEvidenceV4 | None

    @property
    def goal_contract(self) -> Any:
        return self.inner.goal_contract

    @property
    def clause(self) -> Any:
        return self.inner.clause

    @property
    def resolution(self) -> str:
        return self.inner.resolution

    @property
    def surface(self) -> Any:
        return self.inner.surface

    @property
    def allowed(self) -> bool:
        return self.inner.allowed

    def record(self) -> dict[str, object]:
        record = self.goal_contract.record()
        record["webarena_exact_mutation_v4"] = {
            "clause": None if self.clause is None else self.clause.record(),
            "resolution": self.resolution,
            "allowed": self.allowed,
            "surface": None if self.surface is None else self.surface.record(),
            "projection": self.projection.record(),
            "scoped_binding": (None if self.scoped_binding is None else self.scoped_binding.record()),
            "legacy_v3_binding_retained": self.scoped_binding is None,
            "execution_uses_original_snapshot": True,
            "freshness_uses_original_snapshot": True,
        }
        return record


def compile_exact_mutation_goal_v4(
    goal: str,
    snapshot: SemanticSnapshot,
) -> ExactMutationCompilationV4:
    projected, projection = project_exact_mutation_snapshot_v3(snapshot)
    legacy = compile_exact_mutation_goal_v2(goal, projected)
    if legacy.allowed:
        return ExactMutationCompilationV4(legacy, projection, None)

    clause = parse_exact_mutation_v1(str(goal).strip())
    bindings, surface, resolution, scoped = _resolve_scoped_form_v4(projected, clause)
    if not bindings:
        return ExactMutationCompilationV4(legacy, projection, scoped)
    contract = _contract(
        base=legacy.goal_contract.base,
        bindings=bindings,
        resolution=resolution,
    )
    return ExactMutationCompilationV4(
        ExactMutationCompilationV2(contract, clause, resolution, surface),
        projection,
        scoped,
    )


def compile_exact_mutation_inventory_v4(
    snapshot: SemanticSnapshot,
    goal: str,
    *,
    compilation: ExactMutationCompilationV4 | None = None,
) -> V4ActionInventory:
    if compilation is None:
        compilation = compile_exact_mutation_goal_v4(goal, snapshot)
    return compile_exact_mutation_inventory_v2(
        snapshot,
        goal,
        compilation=compilation.inner,
    )


def certify_exact_mutation_commit_v4(
    *,
    current: SemanticSnapshot,
    compilation: ExactMutationCompilationV4,
    candidate: ActionCandidateV4,
    inventory: tuple[ActionCandidateV4, ...],
    active_transactions: tuple[Any, ...],
    resolved_semantic_bids: tuple[str, ...] = (),
    quarantined_commit_keys: frozenset[tuple[object, ...]] = frozenset(),
) -> CommitCertificateV4:
    return certify_exact_mutation_commit_v3(
        current=current,
        compilation=ExactMutationCompilationV3(
            compilation.inner,
            compilation.projection,
        ),
        candidate=candidate,
        inventory=inventory,
        active_transactions=active_transactions,
        resolved_semantic_bids=resolved_semantic_bids,
        quarantined_commit_keys=quarantined_commit_keys,
    )
