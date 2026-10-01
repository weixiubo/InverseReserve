"""Exact mutation with typed URL values and viewport editor surfaces.

V5 preserves the frozen V4 compiler whenever it already binds.  It adds two
public, fail-closed rules learned from the complete navigation-v6 development
population:

* a bare hostname is prefixed with ``https://`` only for a visible
  ``input[type=url]``; and
* a form-less field may bind to one exact Save leaf in the same bounded,
  semantic viewport editor shell when a public Back/Cancel witness is present.

No task identifier, site identity, route, selector, evaluator field, reward,
network trace, or hidden state enters either rule.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, replace
from typing import Any

from .pact_grounding_v4 import CommitCertificateV4, GroundingDecisionV4
from .pact_grounding_v8 import (
    commit_attempt_key_v8,
    unresolved_blocking_transactions_v8,
)
from .structured_planner_v4 import ActionCandidateV4, V4ActionInventory
from .typed_observation import SemanticElement, SemanticSnapshot
from .webarena_exact_mutation_v1 import (
    _editable,
    _tokens,
    parse_exact_mutation_v1,
)
from .webarena_exact_mutation_v2 import (
    ExactMutationCompilationV2,
    _contract,
    _dom_chain,
    _lowest_common_dom_ancestor,
    _surface_descendant_bids,
    compile_exact_mutation_inventory_v2,
)
from .webarena_exact_mutation_v3 import (
    ExactMutationProjectionEvidenceV3,
    project_exact_mutation_snapshot_v3,
)
from .webarena_exact_mutation_v4 import (
    ExactMutationCompilationV4,
    ScopedFieldBindingEvidenceV4,
    _matching_bids,
    certify_exact_mutation_commit_v4,
    compile_exact_mutation_goal_v4,
)
from .webarena_goal_adapter_v1 import (
    PublicPayloadBindingV1,
    _active_payload_bids,
    _field_label,
    _nearest_dom_form,
    _normalized,
    _public_boolean,
    _public_value,
)


MAXIMUM_VIEWPORT_SURFACE_DESCENDANTS_V5 = 1024
MAXIMUM_VIEWPORT_SURFACE_AREA_RATIO_V5 = 2.0
SEMANTIC_SURFACE_TAGS_V5 = frozenset(
    {"article", "dialog", "form", "main", "section"}
)
SEMANTIC_SURFACE_ROLES_V5 = frozenset(
    {"article", "dialog", "form", "main", "region"}
)
NEUTRAL_LABEL_TOKENS_V5 = frozenset(
    {
        ("back",),
        ("go", "back"),
        ("cancel",),
        ("close",),
        ("discard",),
    }
)
BARE_HOST_URL_V5 = re.compile(
    r"(?=.{1,512}\Z)"
    r"(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+"
    r"[a-z]{2,63}"
    r"(?::[0-9]{1,5})?"
    r"(?:/[^\s]*)?",
    flags=re.IGNORECASE,
)
URI_SCHEME_V5 = re.compile(r"[a-z][a-z0-9+.-]*:", re.IGNORECASE)


def _button_like_v5(element: SemanticElement) -> bool:
    return bool(
        (
            element.role.casefold() == "button"
            or element.dom_tag.casefold() == "button"
        )
        and element.clickable
        and not _public_boolean(element, "disabled")
    )


def _label_tokens_v5(element: SemanticElement) -> tuple[str, ...]:
    return _tokens(element.name or element.subtree_text)


def _is_exact_save_leaf_v5(element: SemanticElement) -> bool:
    return _button_like_v5(element) and _label_tokens_v5(element) == ("save",)


def _is_neutral_leaf_v5(element: SemanticElement) -> bool:
    return bool(
        _button_like_v5(element)
        and _label_tokens_v5(element) in NEUTRAL_LABEL_TOKENS_V5
    )


def _is_public_ancestor_v5(
    snapshot: SemanticSnapshot,
    ancestor_bid: str,
    descendant_bid: str,
) -> bool:
    return ancestor_bid == descendant_bid or any(
        row.bid == ancestor_bid
        for row in snapshot.ancestors(descendant_bid, relation="dom")
    )


def _valid_bbox_v5(
    bbox: tuple[float, float, float, float] | None,
) -> bool:
    return bool(
        bbox is not None
        and all(math.isfinite(value) for value in bbox)
        and bbox[2] > 0
        and bbox[3] > 0
    )


def _bbox_center_in_viewport_v5(
    element: SemanticElement,
    *,
    viewport_width: int,
    viewport_height: int,
) -> bool:
    if not _valid_bbox_v5(element.bbox):
        return False
    assert element.bbox is not None
    x, y, width, height = element.bbox
    return bool(
        0 <= x + width / 2 <= viewport_width
        and 0 <= y + height / 2 <= viewport_height
    )


def _semantic_surface_v5(element: SemanticElement) -> bool:
    return bool(
        element.dom_tag.casefold() in SEMANTIC_SURFACE_TAGS_V5
        or element.role.casefold() in SEMANTIC_SURFACE_ROLES_V5
    )


@dataclass(frozen=True)
class ExactMutationProjectionEvidenceV5:
    legacy: ExactMutationProjectionEvidenceV3
    token_back_neutralization_bids: tuple[str, ...]

    @property
    def non_text_input_bids(self) -> tuple[str, ...]:
        return self.legacy.non_text_input_bids

    @property
    def back_neutralization_bids(self) -> tuple[str, ...]:
        return tuple(
            sorted(
                set(self.legacy.back_neutralization_bids)
                | set(self.token_back_neutralization_bids)
            )
        )

    def record(self) -> dict[str, object]:
        record = self.legacy.record()
        record["back_neutralization_bids"] = list(
            self.back_neutralization_bids
        )
        record["legacy_exact_back_neutralization_bids"] = list(
            self.legacy.back_neutralization_bids
        )
        record["token_back_neutralization_bids"] = list(
            self.token_back_neutralization_bids
        )
        record.update(
            {
                "uses_public_button_tokens": True,
                "uses_site_identity": False,
                "uses_site_specific_selector": False,
                "uses_site_specific_route": False,
                "uses_task_id": False,
                "uses_evaluator": False,
                "uses_reward": False,
                "uses_network_log": False,
                "uses_hidden_state": False,
            }
        )
        return record


def project_exact_mutation_snapshot_v5(
    snapshot: SemanticSnapshot,
) -> tuple[SemanticSnapshot, ExactMutationProjectionEvidenceV5]:
    projected, legacy = project_exact_mutation_snapshot_v3(snapshot)
    rows = []
    token_backs = []
    for element in projected.elements:
        original = snapshot.get(element.bid)
        if (
            original is not None
            and _button_like_v5(original)
            and _label_tokens_v5(original) in {
                ("back",),
                ("go", "back"),
            }
            and element.bid not in legacy.back_neutralization_bids
        ):
            token_backs.append(element.bid)
            element = replace(
                element,
                name="Cancel",
                subtree_text="Cancel",
            )
        rows.append(element)
    return (
        SemanticSnapshot(tuple(rows)),
        ExactMutationProjectionEvidenceV5(
            legacy,
            tuple(sorted(token_backs)),
        ),
    )


@dataclass(frozen=True)
class PublicTypedValueNormalizationV5:
    verbatim_value: str
    execution_value: str
    input_type: str
    rule: str
    applied: bool

    def record(self) -> dict[str, object]:
        return {
            "verbatim_value": self.verbatim_value,
            "execution_value": self.execution_value,
            "input_type": self.input_type,
            "rule": self.rule,
            "applied": self.applied,
            "uses_public_input_type": True,
            "uses_site_identity": False,
            "uses_site_specific_selector": False,
            "uses_site_specific_route": False,
            "uses_task_id": False,
            "uses_evaluator": False,
            "uses_reward": False,
            "uses_network_log": False,
            "uses_hidden_state": False,
        }


def _typed_value_normalization_v5(
    element: SemanticElement,
    value: str,
) -> PublicTypedValueNormalizationV5:
    input_type = str(element.dom_attribute("type", "")).strip().casefold()
    if input_type != "url":
        return PublicTypedValueNormalizationV5(
            value, value, input_type, "non_url_input", False
        )
    if value != value.strip() or not value:
        return PublicTypedValueNormalizationV5(
            value, value, input_type, "noncanonical_whitespace", False
        )
    if URI_SCHEME_V5.match(value):
        return PublicTypedValueNormalizationV5(
            value, value, input_type, "explicit_uri_scheme", False
        )
    if BARE_HOST_URL_V5.fullmatch(value) is None:
        return PublicTypedValueNormalizationV5(
            value, value, input_type, "not_a_bare_hostname_url", False
        )
    return PublicTypedValueNormalizationV5(
        value,
        f"https://{value}",
        input_type,
        "url_input_bare_hostname_https",
        True,
    )


@dataclass(frozen=True)
class PublicViewportEditorSurfaceEvidenceV5:
    kind: str
    surface_bid: str
    submit_bid: str
    neutral_bids: tuple[str, ...]
    commit_representation_bids: tuple[str, ...]
    canonical_chain_bids: tuple[str, ...]
    ignored_save_option_bids: tuple[str, ...]
    target_depth: int
    submit_depth: int
    descendant_count: int
    viewport_width: int
    viewport_height: int
    surface_bbox: tuple[float, float, float, float]
    target_bbox: tuple[float, float, float, float]
    submit_bbox: tuple[float, float, float, float]
    surface_area_ratio: float

    def record(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "surface_bid": self.surface_bid,
            "submit_bid": self.submit_bid,
            "neutral_bids": list(self.neutral_bids),
            "commit_representation_bids": list(
                self.commit_representation_bids
            ),
            "canonical_chain_bids": list(self.canonical_chain_bids),
            "ignored_save_option_bids": list(
                self.ignored_save_option_bids
            ),
            "target_depth": self.target_depth,
            "submit_depth": self.submit_depth,
            "descendant_count": self.descendant_count,
            "maximum_descendants": (
                MAXIMUM_VIEWPORT_SURFACE_DESCENDANTS_V5
            ),
            "viewport_width": self.viewport_width,
            "viewport_height": self.viewport_height,
            "surface_bbox": list(self.surface_bbox),
            "target_bbox": list(self.target_bbox),
            "submit_bbox": list(self.submit_bbox),
            "surface_area_ratio": self.surface_area_ratio,
            "maximum_surface_area_ratio": (
                MAXIMUM_VIEWPORT_SURFACE_AREA_RATIO_V5
            ),
            "uses_public_bbox": True,
            "uses_public_dom_ancestry": True,
            "uses_exact_public_action_label": True,
            "uses_public_neutral_witness": True,
            "uses_site_identity": False,
            "uses_site_specific_selector": False,
            "uses_site_specific_route": False,
            "uses_task_id": False,
            "uses_evaluator": False,
            "uses_reward": False,
            "uses_network_log": False,
            "uses_hidden_state": False,
        }


def _viewport_action_sets_v5(
    snapshot: SemanticSnapshot,
    surface_bid: str,
    *,
    viewport_width: int,
    viewport_height: int,
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    surface_bids = _surface_descendant_bids(snapshot, surface_bid)
    exact_leaves = []
    neutral = []
    representations = []
    save_options = []
    for bid in surface_bids:
        element = snapshot.get(bid)
        if (
            element is None
            or not snapshot.is_effectively_visible(bid)
            or not _bbox_center_in_viewport_v5(
                element,
                viewport_width=viewport_width,
                viewport_height=viewport_height,
            )
        ):
            continue
        tokens = _label_tokens_v5(element)
        if _is_exact_save_leaf_v5(element):
            exact_leaves.append(bid)
        if _is_neutral_leaf_v5(element):
            neutral.append(bid)
        if element.clickable and tokens == ("save",):
            representations.append(bid)
        if _button_like_v5(element) and tokens == ("save", "options"):
            save_options.append(bid)
    return (
        tuple(sorted(set(exact_leaves))),
        tuple(sorted(set(neutral))),
        tuple(sorted(set(representations))),
        tuple(sorted(set(save_options))),
    )


def _resolve_viewport_surface_v5(
    snapshot: SemanticSnapshot,
    goal: str,
    *,
    viewport_width: int,
    viewport_height: int,
) -> tuple[
    tuple[PublicPayloadBindingV1, ...],
    PublicViewportEditorSurfaceEvidenceV5 | None,
    str,
    ScopedFieldBindingEvidenceV4,
]:
    clause = parse_exact_mutation_v1(str(goal).strip())
    if clause is None:
        scoped = ScopedFieldBindingEvidenceV4((), (), None, "outside_grammar")
        return (), None, "instruction is outside the exact-mutation grammar", scoped

    direct = _matching_bids(
        snapshot,
        clause,
        include_local_wrapper=False,
    )
    local: tuple[str, ...] = ()
    winners = direct
    tier = "direct_public_label"
    if not winners:
        local = _matching_bids(
            snapshot,
            clause,
            include_local_wrapper=True,
        )
        winners = local
        tier = "bounded_local_wrapper"
    if len(winners) != 1:
        scoped = ScopedFieldBindingEvidenceV4(
            direct,
            local,
            None,
            "ambiguous" if winners else "no_match",
        )
        return (
            (),
            None,
            "viewport editor target is ambiguous" if winners else (
                "no scoped public field matches the mutation anchor"
            ),
            scoped,
        )

    target = snapshot.get(winners[0])
    if target is None or not _editable(target, snapshot):
        raise ValueError("viewport editor target disappeared")
    scoped = ScopedFieldBindingEvidenceV4(
        direct,
        local,
        target.bid,
        tier,
    )
    if _nearest_dom_form(snapshot, target.bid) is not None:
        return (
            (),
            None,
            "viewport fallback does not replace a DOM-form decision",
            scoped,
        )
    if not _bbox_center_in_viewport_v5(
        target,
        viewport_width=viewport_width,
        viewport_height=viewport_height,
    ):
        return (), None, "exact target is not centered in the viewport", scoped

    solutions = {}
    for action in snapshot.elements:
        if (
            not snapshot.is_effectively_visible(action.bid)
            or not _is_exact_save_leaf_v5(action)
            or not _bbox_center_in_viewport_v5(
                action,
                viewport_width=viewport_width,
                viewport_height=viewport_height,
            )
        ):
            continue
        common = _lowest_common_dom_ancestor(snapshot, target.bid, action.bid)
        if common is None:
            continue
        surface, target_depth, submit_depth = common
        if not _semantic_surface_v5(surface) or not _valid_bbox_v5(surface.bbox):
            continue
        assert surface.bbox is not None
        descendant_count = len(snapshot.descendants(surface.bid, relation="dom"))
        if descendant_count > MAXIMUM_VIEWPORT_SURFACE_DESCENDANTS_V5:
            continue
        area_ratio = (
            surface.bbox[2]
            * surface.bbox[3]
            / float(viewport_width * viewport_height)
        )
        if area_ratio > MAXIMUM_VIEWPORT_SURFACE_AREA_RATIO_V5:
            continue
        exact, neutral, representations, save_options = (
            _viewport_action_sets_v5(
                snapshot,
                surface.bid,
                viewport_width=viewport_width,
                viewport_height=viewport_height,
            )
        )
        if exact != (action.bid,) or not neutral:
            continue
        if not representations or any(
            not _is_public_ancestor_v5(snapshot, bid, action.bid)
            for bid in representations
        ):
            continue
        evidence = PublicViewportEditorSurfaceEvidenceV5(
            "public_viewport_editor_surface",
            surface.bid,
            action.bid,
            neutral,
            representations,
            representations,
            save_options,
            target_depth,
            submit_depth,
            descendant_count,
            viewport_width,
            viewport_height,
            surface.bbox,
            target.bbox,  # type: ignore[arg-type]
            action.bbox,  # type: ignore[arg-type]
            area_ratio,
        )
        solutions[(action.bid, surface.bid)] = evidence

    if len(solutions) != 1:
        return (
            (),
            None,
            "viewport editor surface is ambiguous" if solutions else (
                "no bounded viewport editor exposes one exact Save and a neutral witness"
            ),
            scoped,
        )
    evidence = next(iter(solutions.values()))
    binding = PublicPayloadBindingV1(
        bid=target.bid,
        label=_field_label(snapshot, target),
        value=clause.value,
        action_span=clause.action_span,
        value_span=clause.value_span,
        form_bid=evidence.surface_bid,
        submit_bid=evidence.submit_bid,
        binding_kind="exact_public_viewport_editor_surface_mutation",
    )
    return (
        (binding,),
        evidence,
        (
            "one bounded semantic viewport editor binds one exact field, "
            "canonical Save leaf, and neutral witness"
        ),
        scoped,
    )


def _normalize_inner_v5(
    inner: ExactMutationCompilationV2,
    snapshot: SemanticSnapshot,
) -> tuple[ExactMutationCompilationV2, PublicTypedValueNormalizationV5 | None]:
    bindings = tuple(inner.goal_contract.payload_bindings)
    if len(bindings) != 1:
        return inner, None
    binding = bindings[0]
    element = snapshot.get(binding.bid)
    if element is None:
        raise ValueError("exact mutation binding disappeared before normalization")
    normalization = _typed_value_normalization_v5(element, binding.value)
    if not normalization.applied:
        return inner, normalization
    normalized_binding = replace(
        binding,
        value=normalization.execution_value,
        binding_kind=f"{binding.binding_kind}_typed_url_canonicalized",
    )
    resolution = (
        f"{inner.resolution}; public input type canonicalized one bare URL hostname"
    )
    contract = _contract(
        base=inner.goal_contract.base,
        bindings=(normalized_binding,),
        resolution=resolution,
    )
    return (
        ExactMutationCompilationV2(
            contract,
            inner.clause,
            resolution,
            inner.surface,
        ),
        normalization,
    )


@dataclass(frozen=True)
class ExactMutationCompilationV5:
    inner: ExactMutationCompilationV2
    projection: ExactMutationProjectionEvidenceV5
    scoped_binding: ScopedFieldBindingEvidenceV4 | None
    value_normalization: PublicTypedValueNormalizationV5 | None
    viewport_surface: PublicViewportEditorSurfaceEvidenceV5 | None

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
        record["webarena_exact_mutation_v5"] = {
            "clause": None if self.clause is None else self.clause.record(),
            "resolution": self.resolution,
            "allowed": self.allowed,
            "surface": None if self.surface is None else self.surface.record(),
            "projection": self.projection.record(),
            "scoped_binding": (
                None
                if self.scoped_binding is None
                else self.scoped_binding.record()
            ),
            "typed_value_normalization": (
                None
                if self.value_normalization is None
                else self.value_normalization.record()
            ),
            "viewport_surface_binding": (
                None
                if self.viewport_surface is None
                else self.viewport_surface.record()
            ),
            "legacy_v4_binding_retained": self.viewport_surface is None,
            "execution_uses_original_snapshot": True,
            "freshness_uses_original_snapshot": True,
        }
        return record


def compile_exact_mutation_goal_v5(
    goal: str,
    snapshot: SemanticSnapshot,
    *,
    viewport_width: int,
    viewport_height: int,
) -> ExactMutationCompilationV5:
    if viewport_width <= 0 or viewport_height <= 0:
        raise ValueError("viewport dimensions must be positive")
    projected, projection = project_exact_mutation_snapshot_v5(snapshot)
    legacy = compile_exact_mutation_goal_v4(goal, snapshot)
    if legacy.allowed:
        inner, normalization = _normalize_inner_v5(legacy.inner, snapshot)
        return ExactMutationCompilationV5(
            inner,
            projection,
            legacy.scoped_binding,
            normalization,
            None,
        )

    bindings, surface, resolution, scoped = _resolve_viewport_surface_v5(
        projected,
        goal,
        viewport_width=viewport_width,
        viewport_height=viewport_height,
    )
    if not bindings or surface is None:
        return ExactMutationCompilationV5(
            legacy.inner,
            projection,
            scoped,
            None,
            None,
        )
    contract = _contract(
        base=legacy.goal_contract.base,
        bindings=bindings,
        resolution=resolution,
    )
    inner = ExactMutationCompilationV2(
        contract,
        parse_exact_mutation_v1(str(goal).strip()),
        resolution,
        surface,  # type: ignore[arg-type]
    )
    inner, normalization = _normalize_inner_v5(inner, snapshot)
    return ExactMutationCompilationV5(
        inner,
        projection,
        scoped,
        normalization,
        surface,
    )


def compile_exact_mutation_inventory_v5(
    snapshot: SemanticSnapshot,
    goal: str,
    *,
    compilation: ExactMutationCompilationV5 | None = None,
    viewport_width: int,
    viewport_height: int,
) -> V4ActionInventory:
    if compilation is None:
        compilation = compile_exact_mutation_goal_v5(
            goal,
            snapshot,
            viewport_width=viewport_width,
            viewport_height=viewport_height,
        )
    return compile_exact_mutation_inventory_v2(
        snapshot,
        goal,
        compilation=compilation.inner,
    )


def certify_exact_mutation_commit_v5(
    *,
    current: SemanticSnapshot,
    compilation: ExactMutationCompilationV5,
    candidate: ActionCandidateV4,
    inventory: tuple[ActionCandidateV4, ...],
    active_transactions: tuple[Any, ...],
    resolved_semantic_bids: tuple[str, ...] = (),
    quarantined_commit_keys: frozenset[tuple[object, ...]] = frozenset(),
) -> CommitCertificateV4:
    if compilation.viewport_surface is None:
        return certify_exact_mutation_commit_v4(
            current=current,
            compilation=ExactMutationCompilationV4(
                compilation.inner,
                compilation.projection.legacy,
                compilation.scoped_binding,
            ),
            candidate=candidate,
            inventory=inventory,
            active_transactions=active_transactions,
            resolved_semantic_bids=resolved_semantic_bids,
            quarantined_commit_keys=quarantined_commit_keys,
        )

    binding_bids = tuple(
        sorted(row.bid for row in compilation.goal_contract.payload_bindings)
    )

    def denied(
        reason: str,
        *,
        competing: tuple[str, ...] = (),
    ) -> CommitCertificateV4:
        return CommitCertificateV4(
            False,
            reason,
            GroundingDecisionV4(
                False,
                reason,
                "exact_mutation_public_viewport_editor_surface_action",
                binding_bids,
                competing,
            ),
        )

    surface = compilation.viewport_surface
    rows_by_bid = {row.bid: row for row in inventory}
    if (
        not compilation.allowed
        or len(rows_by_bid) != len(inventory)
        or rows_by_bid.get(candidate.bid) != candidate
    ):
        return denied("candidate is absent from the unique current inventory")
    candidate_element = current.get(candidate.bid)
    if (
        candidate_element is None
        or not current.is_effectively_visible(candidate.bid)
        or not _is_exact_save_leaf_v5(candidate_element)
    ):
        return denied("bound viewport action is not one visible exact Save leaf")
    blockers = unresolved_blocking_transactions_v8(
        active_transactions,
        resolved_semantic_bids,
    )
    if blockers:
        return CommitCertificateV4(
            False,
            "a blocking typed overlay remains unresolved",
            GroundingDecisionV4(
                False,
                "a blocking typed overlay remains unresolved",
                "exact_mutation_public_viewport_editor_surface_action",
                tuple(
                    sorted(
                        row.contract.semantic_bid for row in blockers
                    )
                ),
            ),
        )
    goal = compilation.goal_contract
    if _active_payload_bids(active_transactions, goal) != binding_bids:
        return denied("the exact-value field transaction is not active")
    if any(
        _normalized(_public_value(current, binding.bid))
        != _normalized(binding.value)
        for binding in goal.payload_bindings
    ):
        return denied("the current public field value does not match the instruction")

    surface_bids = _surface_descendant_bids(current, surface.surface_bid)
    if any(binding.bid not in surface_bids for binding in goal.payload_bindings):
        return denied("the exact field left its bound viewport editor surface")
    expected_submit = {binding.submit_bid for binding in goal.payload_bindings}
    if expected_submit != {candidate.bid} or candidate.bid not in surface_bids:
        return denied("the current action differs from the bound viewport Save")
    exact, neutral, representations, save_options = _viewport_action_sets_v5(
        current,
        surface.surface_bid,
        viewport_width=surface.viewport_width,
        viewport_height=surface.viewport_height,
    )
    competing = tuple(
        sorted(
            row.bid
            for row in inventory
            if row.bid in surface_bids
            and (element := current.get(row.bid)) is not None
            and _is_exact_save_leaf_v5(element)
        )
    )
    if exact != (candidate.bid,) or competing != (candidate.bid,):
        return denied("viewport editor exact Save leaf is ambiguous", competing=competing)
    if (
        not neutral
        or neutral != surface.neutral_bids
        or representations != surface.commit_representation_bids
        or save_options != surface.ignored_save_option_bids
    ):
        return denied("viewport editor Save or neutral witness changed")
    if any(
        not _is_public_ancestor_v5(current, bid, candidate.bid)
        for bid in representations
    ):
        return denied("viewport editor Save canonicalization chain changed")

    fresh = compile_exact_mutation_goal_v5(
        goal.goal,
        current,
        viewport_width=surface.viewport_width,
        viewport_height=surface.viewport_height,
    )
    fresh_bindings = tuple(fresh.goal_contract.payload_bindings)
    if (
        not fresh.allowed
        or fresh.viewport_surface != surface
        or fresh.projection != compilation.projection
        or fresh.value_normalization != compilation.value_normalization
        or fresh_bindings != tuple(goal.payload_bindings)
    ):
        return denied("fresh viewport editor binding changed before commit")
    try:
        key = commit_attempt_key_v8(
            current=current,
            action=candidate.action,
            active_transactions=active_transactions,
        )
    except Exception as error:
        return denied(f"public effect key failed: {type(error).__name__}")
    if key in quarantined_commit_keys:
        return CommitCertificateV4(
            False,
            "the same viewport Save already had zero public effect",
            GroundingDecisionV4(
                False,
                "the same viewport Save already had zero public effect",
                "no_effect_quarantine",
                binding_bids,
                competing,
            ),
        )
    grounding = GroundingDecisionV4(
        True,
        (
            "one canonical public viewport Save is grounded by the active "
            "exact-value transaction and neutral witness"
        ),
        "exact_mutation_public_viewport_editor_surface_action",
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
