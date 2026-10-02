"""Exact mutation with joint public URL semantics.

V5 canonicalizes a bare hostname only when the bound control declares
``input[type=url]``.  The complete V7 development trace exposed a conventional
``input[type=text]`` whose public label and the goal both explicitly said URL.
V6 preserves the frozen V5 decision and adds one joint semantic rule: a bare
hostname is made absolute only when both the mutation clause and the uniquely
bound public field expose URL/website/homepage tokens.

No task identifier, site identity, route, selector, evaluator field, reward,
network trace, or hidden state enters the rule.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from inversereserve.adapters.webarena.webarena_exact_mutation_v2 import ExactMutationCompilationV2, _contract
from inversereserve.adapters.webarena.webarena_exact_mutation_v4 import _direct_label_tokens_v4
from inversereserve.adapters.webarena.webarena_exact_mutation_v5 import (
    BARE_HOST_URL_V5,
    URI_SCHEME_V5,
    ExactMutationCompilationV5,
    certify_exact_mutation_commit_v5,
    compile_exact_mutation_goal_v5,
    compile_exact_mutation_inventory_v5,
)
from inversereserve.contracts.pact_grounding_v4 import CommitCertificateV4
from inversereserve.models.structured_planner_v4 import ActionCandidateV4, V4ActionInventory
from inversereserve.observations.typed_observation import SemanticSnapshot

URL_SEMANTIC_TOKENS_V6 = frozenset({"homepage", "url", "website"})
TEXTUAL_URL_INPUT_TYPES_V6 = frozenset({"", "text"})


@dataclass(frozen=True)
class PublicJointUrlSemanticNormalizationV6:
    verbatim_value: str
    execution_value: str
    input_type: str
    clause_anchor_tokens: tuple[str, ...]
    field_semantic_tokens: tuple[str, ...]
    joint_url_tokens: tuple[str, ...]
    rule: str
    applied: bool

    def record(self) -> dict[str, object]:
        return {
            "verbatim_value": self.verbatim_value,
            "execution_value": self.execution_value,
            "input_type": self.input_type,
            "clause_anchor_tokens": list(self.clause_anchor_tokens),
            "field_semantic_tokens": list(self.field_semantic_tokens),
            "joint_url_tokens": list(self.joint_url_tokens),
            "rule": self.rule,
            "applied": self.applied,
            "uses_public_goal_tokens": True,
            "uses_public_accessible_name": True,
            "uses_public_dom_attributes": True,
            "uses_site_identity": False,
            "uses_site_specific_selector": False,
            "uses_site_specific_route": False,
            "uses_task_id": False,
            "uses_evaluator": False,
            "uses_reward": False,
            "uses_network_log": False,
            "uses_hidden_state": False,
        }


def _joint_url_semantic_normalization_v6(
    compilation: ExactMutationCompilationV5,
    snapshot: SemanticSnapshot,
) -> PublicJointUrlSemanticNormalizationV6 | None:
    bindings = tuple(compilation.goal_contract.payload_bindings)
    clause = compilation.clause
    if len(bindings) != 1 or clause is None:
        return None
    binding = bindings[0]
    element = snapshot.get(binding.bid)
    if element is None:
        raise ValueError("exact mutation binding disappeared")
    input_type = str(element.dom_attribute("type", "")).strip().casefold()
    clause_tokens = tuple(sorted(set(clause.anchor_tokens)))
    field_tokens = tuple(sorted(_direct_label_tokens_v4(snapshot, element)))
    clause_url = set(clause_tokens) & URL_SEMANTIC_TOKENS_V6
    field_url = set(field_tokens) & URL_SEMANTIC_TOKENS_V6
    joint = tuple(sorted(clause_url | field_url))
    value = binding.value

    if compilation.value_normalization is not None and compilation.value_normalization.applied:
        return PublicJointUrlSemanticNormalizationV6(
            value,
            value,
            input_type,
            clause_tokens,
            field_tokens,
            joint,
            "frozen_v5_typed_url_rule_retained",
            False,
        )
    if element.dom_tag.casefold() != "input":
        rule = "non_input_control"
    elif input_type not in TEXTUAL_URL_INPUT_TYPES_V6:
        rule = "non_textual_url_input"
    elif not clause_url:
        rule = "goal_lacks_url_semantics"
    elif not field_url:
        rule = "field_lacks_url_semantics"
    elif value != value.strip() or not value:
        rule = "noncanonical_whitespace"
    elif URI_SCHEME_V5.match(value):
        rule = "explicit_uri_scheme"
    elif BARE_HOST_URL_V5.fullmatch(value) is None:
        rule = "not_a_bare_hostname_url"
    else:
        return PublicJointUrlSemanticNormalizationV6(
            value,
            f"https://{value}",
            input_type,
            clause_tokens,
            field_tokens,
            joint,
            "joint_goal_field_url_semantics_https",
            True,
        )
    return PublicJointUrlSemanticNormalizationV6(
        value,
        value,
        input_type,
        clause_tokens,
        field_tokens,
        joint,
        rule,
        False,
    )


@dataclass(frozen=True)
class ExactMutationCompilationV6:
    inner: ExactMutationCompilationV2
    frozen_v5: ExactMutationCompilationV5
    semantic_url_normalization: PublicJointUrlSemanticNormalizationV6 | None

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
    def projection(self) -> Any:
        return self.frozen_v5.projection

    @property
    def scoped_binding(self) -> Any:
        return self.frozen_v5.scoped_binding

    @property
    def value_normalization(self) -> Any:
        return self.frozen_v5.value_normalization

    @property
    def viewport_surface(self) -> Any:
        return self.frozen_v5.viewport_surface

    @property
    def allowed(self) -> bool:
        return self.inner.allowed

    def as_v5(self) -> ExactMutationCompilationV5:
        return replace(self.frozen_v5, inner=self.inner)

    def record(self) -> dict[str, object]:
        record = self.goal_contract.record()
        frozen = self.frozen_v5.record()["webarena_exact_mutation_v5"]
        record["webarena_exact_mutation_v6"] = {
            "clause": None if self.clause is None else self.clause.record(),
            "resolution": self.resolution,
            "allowed": self.allowed,
            "surface": None if self.surface is None else self.surface.record(),
            "frozen_v5": frozen,
            "joint_url_semantic_normalization": (
                None if self.semantic_url_normalization is None else self.semantic_url_normalization.record()
            ),
            "execution_uses_original_snapshot": True,
            "freshness_uses_original_snapshot": True,
        }
        return record


def compile_exact_mutation_goal_v6(
    goal: str,
    snapshot: SemanticSnapshot,
    *,
    viewport_width: int,
    viewport_height: int,
) -> ExactMutationCompilationV6:
    frozen = compile_exact_mutation_goal_v5(
        goal,
        snapshot,
        viewport_width=viewport_width,
        viewport_height=viewport_height,
    )
    normalization = _joint_url_semantic_normalization_v6(frozen, snapshot)
    if normalization is None or not normalization.applied:
        return ExactMutationCompilationV6(
            frozen.inner,
            frozen,
            normalization,
        )
    bindings = tuple(frozen.goal_contract.payload_bindings)
    binding = replace(
        bindings[0],
        value=normalization.execution_value,
        binding_kind=(f"{bindings[0].binding_kind}_joint_url_semantic_canonicalized"),
    )
    resolution = (
        f"{frozen.resolution}; joint public goal and field URL semantics canonicalized one bare hostname"
    )
    contract = _contract(
        base=frozen.goal_contract.base,
        bindings=(binding,),
        resolution=resolution,
    )
    inner = ExactMutationCompilationV2(
        contract,
        frozen.clause,
        resolution,
        frozen.surface,
    )
    return ExactMutationCompilationV6(inner, frozen, normalization)


def compile_exact_mutation_inventory_v6(
    snapshot: SemanticSnapshot,
    goal: str,
    *,
    compilation: ExactMutationCompilationV6 | None = None,
    viewport_width: int,
    viewport_height: int,
) -> V4ActionInventory:
    if compilation is None:
        compilation = compile_exact_mutation_goal_v6(
            goal,
            snapshot,
            viewport_width=viewport_width,
            viewport_height=viewport_height,
        )
    return compile_exact_mutation_inventory_v5(
        snapshot,
        goal,
        compilation=compilation.as_v5(),
        viewport_width=viewport_width,
        viewport_height=viewport_height,
    )


def certify_exact_mutation_commit_v6(
    *,
    current: SemanticSnapshot,
    compilation: ExactMutationCompilationV6,
    candidate: ActionCandidateV4,
    inventory: tuple[ActionCandidateV4, ...],
    active_transactions: tuple[Any, ...],
    resolved_semantic_bids: tuple[str, ...] = (),
    quarantined_commit_keys: frozenset[tuple[object, ...]] = frozenset(),
) -> CommitCertificateV4:
    return certify_exact_mutation_commit_v5(
        current=current,
        compilation=compilation.as_v5(),
        candidate=candidate,
        inventory=inventory,
        active_transactions=active_transactions,
        resolved_semantic_bids=resolved_semantic_bids,
        quarantined_commit_keys=quarantined_commit_keys,
    )
