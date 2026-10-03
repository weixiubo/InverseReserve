"""Exact public mutation with conservative semantic control projection.

V2 intentionally treats every visible ``input`` element as potentially
editable and requires a Cancel-like witness for a form-less edit surface.
Public applications also expose typed action inputs and Back controls.  V3
projects only those two standard semantics before invoking the frozen V2
adapter:

* a non-text ``input`` is represented by its public control role instead of
  an editable text tag; and
* a visible Back button is represented as a neutralization witness.

The original snapshot is retained for execution, effect keys, freshness, and
all complete-public certificates.  No site identity, route, selector, task
identifier, evaluator field, reward, or hidden state enters the projection.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from inversereserve.adapters.webarena.webarena_exact_mutation_v1 import _submit_like_label
from inversereserve.adapters.webarena.webarena_exact_mutation_v2 import (
    ExactMutationCompilationV2,
    certify_exact_mutation_commit_v2,
    compile_exact_mutation_goal_v2,
    compile_exact_mutation_inventory_v2,
)
from inversereserve.contracts.pact_grounding_v4 import CommitCertificateV4, GroundingDecisionV4
from inversereserve.contracts.pact_grounding_v8 import commit_attempt_key_v8
from inversereserve.models.structured_planner_v4 import ActionCandidateV4, V4ActionInventory
from inversereserve.observations.typed_observation import SemanticElement, SemanticSnapshot

TEXT_INPUT_TYPES_V3 = frozenset({"", "email", "password", "search", "tel", "text", "url"})
TEXT_INPUT_ROLES_V3 = frozenset({"combobox", "searchbox", "textbox"})
BACK_LABELS_V3 = frozenset({"back", "go back"})


def _normalized(value: object) -> str:
    return " ".join(str(value or "").casefold().split())


def _is_non_text_input(element: SemanticElement) -> bool:
    if element.dom_tag.casefold() != "input":
        return False
    role = element.role.casefold()
    input_type = str(element.dom_attribute("type", "")).casefold()
    return bool(role not in TEXT_INPUT_ROLES_V3 and input_type not in TEXT_INPUT_TYPES_V3)


def _is_public_back_button(element: SemanticElement) -> bool:
    label = _normalized(element.name or element.subtree_text)
    return bool(
        element.clickable
        and (element.role.casefold() == "button" or element.dom_tag.casefold() == "button")
        and label in BACK_LABELS_V3
    )


@dataclass(frozen=True)
class ExactMutationProjectionEvidenceV3:
    non_text_input_bids: tuple[str, ...]
    back_neutralization_bids: tuple[str, ...]

    def record(self) -> dict[str, object]:
        return {
            "non_text_input_bids": list(self.non_text_input_bids),
            "back_neutralization_bids": list(self.back_neutralization_bids),
            "uses_public_role": True,
            "uses_public_input_type": True,
            "uses_public_button_label": True,
            "uses_site_identity": False,
            "uses_site_specific_selector": False,
            "uses_site_specific_route": False,
            "uses_task_id": False,
            "uses_evaluator": False,
            "uses_reward": False,
            "uses_hidden_state": False,
        }


def project_exact_mutation_snapshot_v3(
    snapshot: SemanticSnapshot,
) -> tuple[SemanticSnapshot, ExactMutationProjectionEvidenceV3]:
    """Return a public semantic projection plus an explicit change record."""

    rows: list[SemanticElement] = []
    non_text: list[str] = []
    backs: list[str] = []
    for element in snapshot.elements:
        projected = element
        if _is_non_text_input(element):
            non_text.append(element.bid)
            projected = replace(
                projected,
                dom_tag=("button" if element.role.casefold() == "button" else "div"),
            )
        if _is_public_back_button(element):
            backs.append(element.bid)
            projected = replace(
                projected,
                name="Cancel via Back",
                subtree_text="Cancel via Back",
            )
        rows.append(projected)
    return (
        SemanticSnapshot(tuple(rows)),
        ExactMutationProjectionEvidenceV3(tuple(sorted(non_text)), tuple(sorted(backs))),
    )


@dataclass(frozen=True)
class ExactMutationCompilationV3:
    inner: ExactMutationCompilationV2
    projection: ExactMutationProjectionEvidenceV3

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
        record["webarena_exact_mutation_v3"] = {
            "clause": None if self.clause is None else self.clause.record(),
            "resolution": self.resolution,
            "allowed": self.allowed,
            "surface": (None if self.surface is None else self.surface.record()),
            "projection": self.projection.record(),
            "execution_uses_original_snapshot": True,
            "freshness_uses_original_snapshot": True,
        }
        return record


def compile_exact_mutation_goal_v3(
    goal: str,
    snapshot: SemanticSnapshot,
) -> ExactMutationCompilationV3:
    projected, evidence = project_exact_mutation_snapshot_v3(snapshot)
    return ExactMutationCompilationV3(compile_exact_mutation_goal_v2(goal, projected), evidence)


def compile_exact_mutation_inventory_v3(
    snapshot: SemanticSnapshot,
    goal: str,
    *,
    compilation: ExactMutationCompilationV3 | None = None,
) -> V4ActionInventory:
    if compilation is None:
        compilation = compile_exact_mutation_goal_v3(goal, snapshot)
    return compile_exact_mutation_inventory_v2(
        snapshot,
        goal,
        compilation=compilation.inner,
    )


def certify_exact_mutation_commit_v3(
    *,
    current: SemanticSnapshot,
    compilation: ExactMutationCompilationV3,
    candidate: ActionCandidateV4,
    inventory: tuple[ActionCandidateV4, ...],
    active_transactions: tuple[Any, ...],
    resolved_semantic_bids: tuple[str, ...] = (),
    quarantined_commit_keys: frozenset[tuple[object, ...]] = frozenset(),
) -> CommitCertificateV4:
    """Certify on projected semantics, then bind the key to real public state."""

    projected, fresh_evidence = project_exact_mutation_snapshot_v3(current)
    if fresh_evidence != compilation.projection:
        reason = "exact-mutation public control projection changed"
        return CommitCertificateV4(
            False,
            reason,
            GroundingDecisionV4(False, reason, "public_control_projection"),
        )
    projected_certificate = certify_exact_mutation_commit_v2(
        current=projected,
        compilation=compilation.inner,
        candidate=candidate,
        inventory=inventory,
        active_transactions=active_transactions,
        resolved_semantic_bids=resolved_semantic_bids,
        quarantined_commit_keys=frozenset(),
    )
    if not projected_certificate.allowed:
        return projected_certificate
    try:
        key = commit_attempt_key_v8(
            current=current,
            action=candidate.action,
            active_transactions=active_transactions,
        )
    except Exception as error:
        reason = f"public effect key failed: {type(error).__name__}"
        return CommitCertificateV4(
            False,
            reason,
            GroundingDecisionV4(False, reason, "public_effect_key"),
        )
    if key in quarantined_commit_keys:
        reason = "the same exact-mutation action already had zero public effect"
        return CommitCertificateV4(
            False,
            reason,
            GroundingDecisionV4(
                False,
                reason,
                "no_effect_quarantine",
                tuple(sorted(row.bid for row in compilation.goal_contract.payload_bindings)),
                (candidate.bid,),
            ),
        )
    return replace(
        projected_certificate,
        observation_fingerprint=key[0],
        active_stack_signature=key[1],
    )


def projection_has_submit_semantics_v3(
    snapshot: SemanticSnapshot,
) -> bool:
    """Small diagnostic used by protocol sealers and regression tests."""

    projected, _evidence = project_exact_mutation_snapshot_v3(snapshot)
    return any(
        projected.is_effectively_visible(row.bid) and _submit_like_label(row.name or row.subtree_text)
        for row in projected.elements
    )
