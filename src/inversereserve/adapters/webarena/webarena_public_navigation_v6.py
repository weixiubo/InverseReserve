"""Geometry-bounded form reveal and canonical row navigation V6.

V6 adds only two public, fail-closed resolvers to frozen navigation-v5:
one joint-visibility form scroll and one ancestor-chain row-action
canonicalization. No site identity, route, selector, task identifier,
evaluator field, reward, network trace, or hidden state enters either path.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Mapping

from inversereserve.adapters.webarena.form_reveal import (
    MAXIMUM_LOCAL_LABEL_DESCENDANTS_V6 as MAXIMUM_LOCAL_LABEL_DESCENDANTS_V6,
)
from inversereserve.adapters.webarena.form_reveal import (
    MAXIMUM_PUBLIC_FORM_SCROLL_PIXELS_V6 as MAXIMUM_PUBLIC_FORM_SCROLL_PIXELS_V6,
)
from inversereserve.adapters.webarena.form_reveal import (
    MAXIMUM_PUBLIC_FORM_SCROLL_VIEWPORTS_V6 as MAXIMUM_PUBLIC_FORM_SCROLL_VIEWPORTS_V6,
)
from inversereserve.adapters.webarena.form_reveal import (
    FormRevealContext as FormRevealContext,
)
from inversereserve.adapters.webarena.form_reveal import (
    PublicExactFormRevealV6 as PublicExactFormRevealV6,
)
from inversereserve.adapters.webarena.form_reveal import (
    PublicFormRevealCandidateV6 as PublicFormRevealCandidateV6,
)
from inversereserve.adapters.webarena.form_reveal import (
    PublicScrollActionV6 as PublicScrollActionV6,
)
from inversereserve.adapters.webarena.form_reveal import (
    _admit_form_scroll as _admit_form_scroll,
)
from inversereserve.adapters.webarena.form_reveal import (
    _direct_label_tokens_v6 as _direct_label_tokens_v6,
)
from inversereserve.adapters.webarena.form_reveal import (
    _exact_form_reveal_v6 as _exact_form_reveal_v6,
)
from inversereserve.adapters.webarena.form_reveal import (
    _half_visible_scroll_interval_v6 as _half_visible_scroll_interval_v6,
)
from inversereserve.adapters.webarena.form_reveal import (
    _local_wrapper_tokens_v6 as _local_wrapper_tokens_v6,
)
from inversereserve.adapters.webarena.form_reveal import (
    _matching_rendered_fields_v6 as _matching_rendered_fields_v6,
)
from inversereserve.adapters.webarena.form_reveal import (
    _publicly_rendered_v6 as _publicly_rendered_v6,
)
from inversereserve.adapters.webarena.form_reveal import (
    _rendered_editable_v6 as _rendered_editable_v6,
)
from inversereserve.adapters.webarena.form_reveal import (
    _rendered_submit_bids_v6 as _rendered_submit_bids_v6,
)
from inversereserve.adapters.webarena.form_reveal import (
    _reveal_evidence_v6 as _reveal_evidence_v6,
)
from inversereserve.adapters.webarena.form_reveal import (
    _tokens_from_v6 as _tokens_from_v6,
)
from inversereserve.adapters.webarena.webarena_public_navigation_v3 import (
    PublicNavigationCandidateV3,
    PublicNavigationInventoryV3,
    compile_public_navigation_v3,
)
from inversereserve.adapters.webarena.webarena_public_navigation_v4 import (
    PublicNavigationDecisionV4,
    _normalized_text,
)
from inversereserve.adapters.webarena.webarena_public_navigation_v5 import (
    MAXIMUM_PUBLIC_ROW_SCAN_V5,
    compile_public_navigation_v5,
)
from inversereserve.observations.typed_observation import SemanticElement, SemanticSnapshot

STANDARD_LEAF_ROLES_V6 = frozenset({"button", "link", "menuitem"})
STANDARD_LEAF_TAGS_V6 = frozenset({"button", "a"})


def _is_public_ancestor_v6(snapshot: SemanticSnapshot, ancestor_bid: str, descendant_bid: str) -> bool:
    return ancestor_bid == descendant_bid or any(
        (
            ancestor.bid == ancestor_bid
            for relation in ("ax", "dom")
            for ancestor in snapshot.ancestors(descendant_bid, relation=relation)
        )
    )


def _standard_leaf_v6(element: SemanticElement) -> bool:
    return bool(
        element.role.casefold() in STANDARD_LEAF_ROLES_V6
        or element.dom_tag.casefold() in STANDARD_LEAF_TAGS_V6
    )


def _canonical_row_action_v6(
    snapshot: SemanticSnapshot, matches: list[PublicNavigationCandidateV3]
) -> tuple[PublicNavigationCandidateV3 | None, tuple[str, ...]]:
    if len(matches) == 1:
        return (matches[0], (matches[0].bid,))
    if len({_normalized_text(row.label) for row in matches}) != 1:
        return (None, ())
    leaves = [
        candidate
        for candidate in matches
        if (element := snapshot.get(candidate.bid)) is not None
        and _standard_leaf_v6(element)
        and all((_is_public_ancestor_v6(snapshot, other.bid, candidate.bid) for other in matches))
    ]
    if len(leaves) != 1:
        return (None, ())
    return (leaves[0], tuple((row.bid for row in matches)))


@dataclass(frozen=True)
class PublicRowActionBindingV6:
    quoted_entities: tuple[str, ...]
    entity_match_bids: tuple[str, ...]
    entity_bid: str | None
    row_bids: tuple[str, ...]
    row_action_match_bids: tuple[str, ...]
    canonical_chain_bids: tuple[str, ...]
    action_bid: str | None
    promoted: bool
    resolution: str

    @property
    def allowed(self) -> bool:
        return bool(
            self.entity_bid and len(self.row_bids) == 1 and self.row_action_match_bids and self.action_bid
        )

    def record(self) -> dict[str, object]:
        return {
            "quoted_entities": list(self.quoted_entities),
            "entity_match_bids": list(self.entity_match_bids),
            "entity_bid": self.entity_bid,
            "row_bids": list(self.row_bids),
            "row_action_match_bids": list(self.row_action_match_bids),
            "canonical_chain_bids": list(self.canonical_chain_bids),
            "action_bid": self.action_bid,
            "promoted": self.promoted,
            "canonicalization_used": bool(
                len(self.row_action_match_bids) > 1 and self.action_bid is not None
            ),
            "resolution": self.resolution,
            "allowed": self.allowed,
            "maximum_public_candidates_scanned": MAXIMUM_PUBLIC_ROW_SCAN_V5,
            "uses_public_row_semantics": True,
            "uses_public_ancestor_relations": True,
            "uses_exact_public_labels": True,
            "uses_site_identity": False,
            "uses_site_specific_selector": False,
            "uses_site_specific_route": False,
            "uses_task_id": False,
            "uses_evaluator": False,
            "uses_reward": False,
            "uses_network_log": False,
            "uses_hidden_state": False,
        }


def _upgrade_row_binding_v6(
    *,
    snapshot: SemanticSnapshot,
    frozen: Any,
    base: PublicNavigationInventoryV3,
    expanded: PublicNavigationInventoryV3,
) -> tuple[PublicRowActionBindingV6, PublicNavigationInventoryV3]:
    prior = frozen.row_action_binding
    raw = [row for row in expanded.candidates if row.bid in set(prior.row_action_match_bids)]
    action: PublicNavigationCandidateV3 | None = None
    chain: tuple[str, ...] = ()
    resolution = prior.resolution
    if prior.allowed and prior.action_bid is not None:
        matches = [row for row in base.candidates if row.bid == prior.action_bid]
        if len(matches) != 1:
            raise ValueError("frozen v5 row action disappeared")
        action, chain = (matches[0], (matches[0].bid,))
    elif len(raw) > 1:
        action, chain = _canonical_row_action_v6(snapshot, raw)
        resolution = (
            "one same-label public ancestor chain has one standard leaf action"
            if action is not None
            else "row action representations are not one canonical chain"
        )
    base, promoted = _promote_row_action(base, action)
    evidence = PublicRowActionBindingV6(
        prior.quoted_entities,
        prior.entity_match_bids,
        prior.entity_bid,
        prior.row_bids,
        prior.row_action_match_bids,
        chain,
        None if action is None else action.bid,
        bool(prior.promoted or promoted),
        resolution,
    )
    return (evidence, base)


@dataclass(frozen=True)
class PublicNavigationInventoryV6:
    inner: PublicNavigationInventoryV3
    row_action_binding: PublicRowActionBindingV6
    exact_form_reveal: PublicExactFormRevealV6

    @property
    def candidates(self) -> tuple[Any, ...]:
        return self.inner.candidates

    def __getattr__(self, name: str) -> Any:
        return getattr(self.inner, name)

    def record(self) -> dict[str, object]:
        record = self.inner.record()
        record["row_action_binding_v6"] = self.row_action_binding.record()
        record["exact_form_reveal_v6"] = self.exact_form_reveal.record()
        return record

    def planner_records(self) -> list[dict[str, object]]:
        return [row.record(include_key=False) for row in self.candidates]


def compile_public_navigation_v6(
    snapshot: SemanticSnapshot,
    *,
    current_url: str,
    goal: str,
    viewport_width: int,
    viewport_height: int,
    attempt_counts: Mapping[str, int] | None = None,
    retry_authorized: bool = False,
    maximum_candidates: int = 64,
) -> PublicNavigationInventoryV6:
    if (
        viewport_width <= 0
        or viewport_height <= 0
        or (not 1 <= int(maximum_candidates) <= MAXIMUM_PUBLIC_ROW_SCAN_V5)
    ):
        raise ValueError("public navigation viewport or candidate bound is invalid")
    frozen = compile_public_navigation_v5(
        snapshot,
        current_url=current_url,
        goal=goal,
        attempt_counts=attempt_counts,
        retry_authorized=retry_authorized,
        maximum_candidates=int(maximum_candidates),
    )
    base = frozen.inner
    expanded = (
        base
        if int(maximum_candidates) == MAXIMUM_PUBLIC_ROW_SCAN_V5
        else compile_public_navigation_v3(
            snapshot,
            current_url=current_url,
            goal=goal,
            attempt_counts=attempt_counts,
            retry_authorized=retry_authorized,
            maximum_candidates=MAXIMUM_PUBLIC_ROW_SCAN_V5,
        )
    )
    row_evidence, base = _upgrade_row_binding_v6(
        snapshot=snapshot, frozen=frozen, base=base, expanded=expanded
    )
    reveal_evidence, reveal = _exact_form_reveal_v6(
        snapshot=snapshot,
        goal=goal,
        viewport_width=int(viewport_width),
        viewport_height=int(viewport_height),
        public_state_key=base.public_state_key,
        attempt_counts=attempt_counts,
    )
    if reveal is not None:
        candidates = (reveal,) + tuple((row for row in base.candidates if row.bid != reveal.bid))
        base = replace(base, candidates=candidates[: int(maximum_candidates)])
    return PublicNavigationInventoryV6(base, row_evidence, reveal_evidence)


@dataclass(frozen=True)
class PublicFormRevealDecisionV6:
    decision: str
    candidate: PublicFormRevealCandidateV6 | None
    reason: str
    resolution_source: str

    @property
    def allowed(self) -> bool:
        return bool(self.decision == "scroll" and self.candidate is not None)

    def record(self) -> dict[str, object]:
        return {
            "decision": self.decision,
            "bid": None if self.candidate is None else self.candidate.bid,
            "requested_bid": None,
            "operation": "scroll",
            "delta_y": None if self.candidate is None else self.candidate.delta_y,
            "reason": self.reason,
            "resolution_source": self.resolution_source,
            "allowed": self.allowed,
        }


def exact_form_reveal_decision_v6(
    inventory: PublicNavigationInventoryV6,
) -> PublicFormRevealDecisionV6 | None:
    evidence = inventory.exact_form_reveal
    if not evidence.allowed or evidence.form_bid is None:
        return None
    matches = [
        row
        for row in inventory.candidates
        if isinstance(row, PublicFormRevealCandidateV6) and row.bid == evidence.form_bid
    ]
    if len(matches) != 1:
        raise ValueError("bound public form reveal is absent from the inventory")
    return PublicFormRevealDecisionV6(
        "scroll",
        matches[0],
        "one public scroll jointly reveals exact field and submit",
        "exact_form_boundary_reveal",
    )


def quoted_entity_row_action_decision_v6(
    inventory: PublicNavigationInventoryV6,
) -> PublicNavigationDecisionV4 | None:
    evidence = inventory.row_action_binding
    if not evidence.allowed or evidence.action_bid is None:
        return None
    matches = [row for row in inventory.candidates if row.bid == evidence.action_bid]
    if len(matches) != 1:
        raise ValueError("canonical row action is absent from the retained inventory")
    return PublicNavigationDecisionV4(
        "click", matches[0], "one quoted row has one canonical public leaf action", "quoted_entity_row_action"
    )


def _promote_row_action(
    base: PublicNavigationInventoryV3, action: PublicNavigationCandidateV3 | None
) -> tuple[PublicNavigationInventoryV3, bool]:
    retained_bids = {row.bid for row in base.candidates}
    promoted = bool(action is not None and action.bid not in retained_bids)
    if promoted:
        candidates = (action,) + tuple((row for row in base.candidates if row.bid != action.bid))
        base = replace(base, candidates=candidates[: base.maximum_candidates])
    return (base, promoted)
