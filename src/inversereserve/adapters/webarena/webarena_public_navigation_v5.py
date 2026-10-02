"""Row-scoped public navigation for exact mutation targets.

V4 could bind a uniquely quoted table entity, but clicking the entity itself
may invoke a public inline editor while the application's standard workflow is
exposed through a row-local ``Select``/``Actions`` disclosure and ``Edit``
item.  V5 scans at most 128 already-public navigation candidates, binds one
quoted entity to one semantic row, promotes that row's unique action control
into the frozen planner bound, and then accepts one unique visible ``Edit``
item after the disclosure opens.

The resolver uses no site identity, route, selector, task identifier,
evaluator field, reward, network trace, or hidden state.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Mapping

from inversereserve.adapters.webarena.webarena_exact_mutation_v1 import parse_exact_mutation_v1
from inversereserve.adapters.webarena.webarena_public_navigation_v3 import (
    PublicNavigationCandidateV3,
    PublicNavigationInventoryV3,
    compile_public_navigation_v3,
)
from inversereserve.adapters.webarena.webarena_public_navigation_v4 import (
    QUOTED_SPAN_V4,
    PublicNavigationDecisionV4,
    _normalized_text,
)
from inversereserve.observations.typed_observation import SemanticElement, SemanticSnapshot

MAXIMUM_PUBLIC_ROW_SCAN_V5 = 128
ROW_ACTION_LABELS_V5 = frozenset({"action", "actions", "select"})
EDIT_ACTION_LABELS_V5 = frozenset({"edit"})


def _quoted_field_entities_v5(goal: str) -> tuple[str, ...]:
    clause = parse_exact_mutation_v1(str(goal).strip())
    if clause is None:
        return ()
    return tuple(
        sorted(
            {
                _normalized_text(match.group("text"))
                for match in QUOTED_SPAN_V4.finditer(clause.field_text)
                if _normalized_text(match.group("text"))
            }
        )
    )


def _nearest_public_row_bids_v5(snapshot: SemanticSnapshot, element: SemanticElement) -> tuple[str, ...]:
    rows: list[str] = []
    if element.role.casefold() == "row" or element.dom_tag.casefold() == "tr":
        rows.append(element.bid)
    for relation in ("ax", "dom"):
        match = next(
            (
                ancestor.bid
                for ancestor in snapshot.ancestors(element.bid, relation=relation)
                if ancestor.role.casefold() == "row" or ancestor.dom_tag.casefold() == "tr"
            ),
            None,
        )
        if match is not None and match not in rows:
            rows.append(match)
    return tuple(rows)


def _belongs_to_row_v5(snapshot: SemanticSnapshot, element: SemanticElement, row_bid: str) -> bool:
    if element.bid == row_bid:
        return True
    return any(
        (
            ancestor.bid == row_bid
            for relation in ("ax", "dom")
            for ancestor in snapshot.ancestors(element.bid, relation=relation)
        )
    )


@dataclass(frozen=True)
class PublicRowActionBindingV5:
    quoted_entities: tuple[str, ...]
    entity_match_bids: tuple[str, ...]
    entity_bid: str | None
    row_bids: tuple[str, ...]
    row_action_match_bids: tuple[str, ...]
    action_bid: str | None
    promoted: bool
    resolution: str

    @property
    def allowed(self) -> bool:
        return bool(
            self.entity_bid
            and len(self.row_bids) == 1
            and self.action_bid
            and (len(self.row_action_match_bids) == 1)
        )

    def record(self) -> dict[str, object]:
        return {
            "quoted_entities": list(self.quoted_entities),
            "entity_match_bids": list(self.entity_match_bids),
            "entity_bid": self.entity_bid,
            "row_bids": list(self.row_bids),
            "row_action_match_bids": list(self.row_action_match_bids),
            "action_bid": self.action_bid,
            "promoted": self.promoted,
            "resolution": self.resolution,
            "allowed": self.allowed,
            "maximum_public_candidates_scanned": MAXIMUM_PUBLIC_ROW_SCAN_V5,
            "uses_public_row_semantics": True,
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


@dataclass(frozen=True)
class PublicNavigationInventoryV5:
    inner: PublicNavigationInventoryV3
    row_action_binding: PublicRowActionBindingV5

    @property
    def candidates(self) -> tuple[PublicNavigationCandidateV3, ...]:
        return self.inner.candidates

    def __getattr__(self, name: str) -> Any:
        return getattr(self.inner, name)

    def record(self) -> dict[str, object]:
        record = self.inner.record()
        record["row_action_binding_v5"] = self.row_action_binding.record()
        return record

    def planner_records(self) -> list[dict[str, object]]:
        return self.inner.planner_records()


def _row_action_binding_v5(
    *, snapshot: SemanticSnapshot, goal: str, expanded: PublicNavigationInventoryV3, retained_bids: set[str]
) -> tuple[PublicRowActionBindingV5, PublicNavigationCandidateV3 | None]:
    entities = _quoted_field_entities_v5(goal)
    if not entities:
        return (PublicRowActionBindingV5((), (), None, (), (), None, False, "no quoted field entity"), None)
    entity_matches = tuple(
        (row for row in expanded.candidates if _normalized_text(row.label) in set(entities))
    )
    if len(entity_matches) != 1:
        return (
            PublicRowActionBindingV5(
                entities,
                tuple((row.bid for row in entity_matches)),
                None,
                (),
                (),
                None,
                False,
                "quoted field entity is ambiguous" if entity_matches else "quoted field entity is absent",
            ),
            None,
        )
    entity = entity_matches[0]
    entity_element = snapshot.get(entity.bid)
    if entity_element is None:
        raise ValueError("quoted public entity disappeared")
    row_bids = _nearest_public_row_bids_v5(snapshot, entity_element)
    if len(row_bids) != 1:
        return (
            PublicRowActionBindingV5(
                entities,
                (entity.bid,),
                entity.bid,
                row_bids,
                (),
                None,
                False,
                "quoted public entity has no unique semantic row",
            ),
            None,
        )
    row_bid = row_bids[0]
    action_matches = _row_action_matches(snapshot, expanded, row_bid)
    if len(action_matches) != 1:
        return (
            PublicRowActionBindingV5(
                entities,
                (entity.bid,),
                entity.bid,
                row_bids,
                tuple((row.bid for row in action_matches)),
                None,
                False,
                "row action is ambiguous" if action_matches else "row exposes no standard action disclosure",
            ),
            None,
        )
    action = action_matches[0]
    promoted = action.bid not in retained_bids
    return (
        PublicRowActionBindingV5(
            entities,
            (entity.bid,),
            entity.bid,
            row_bids,
            (action.bid,),
            action.bid,
            promoted,
            "one quoted entity binds one row and one standard action disclosure",
        ),
        action,
    )


def compile_public_navigation_v5(
    snapshot: SemanticSnapshot,
    *,
    current_url: str,
    goal: str,
    attempt_counts: Mapping[str, int] | None = None,
    retry_authorized: bool = False,
    maximum_candidates: int = 64,
) -> PublicNavigationInventoryV5:
    if not 1 <= int(maximum_candidates) <= MAXIMUM_PUBLIC_ROW_SCAN_V5:
        raise ValueError("public navigation candidate bound is invalid")
    base = compile_public_navigation_v3(
        snapshot,
        current_url=current_url,
        goal=goal,
        attempt_counts=attempt_counts,
        retry_authorized=retry_authorized,
        maximum_candidates=int(maximum_candidates),
    )
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
    retained_bids = {row.bid for row in base.candidates}
    evidence, action = _row_action_binding_v5(
        snapshot=snapshot, goal=goal, expanded=expanded, retained_bids=retained_bids
    )
    if action is not None and action.bid not in retained_bids:
        candidates = (action,) + tuple((row for row in base.candidates if row.bid != action.bid))
        candidates = candidates[: int(maximum_candidates)]
        base = replace(
            base, candidates=candidates, omitted_count=max(0, base.visible_eligible_count - len(candidates))
        )
    return PublicNavigationInventoryV5(base, evidence)


def quoted_entity_row_action_decision_v5(
    inventory: PublicNavigationInventoryV5,
) -> PublicNavigationDecisionV4 | None:
    evidence = inventory.row_action_binding
    if not evidence.allowed or evidence.action_bid is None:
        return None
    matches = [row for row in inventory.candidates if row.bid == evidence.action_bid]
    if len(matches) != 1:
        raise ValueError("bound row action is absent from the retained inventory")
    return PublicNavigationDecisionV4(
        "click",
        matches[0],
        "one quoted public entity binds one row-local action disclosure",
        "quoted_entity_row_action",
    )


def opened_row_edit_decision_v5(inventory: PublicNavigationInventoryV5) -> PublicNavigationDecisionV4 | None:
    matches = [row for row in inventory.candidates if _normalized_text(row.label) in EDIT_ACTION_LABELS_V5]
    if len(matches) != 1:
        return None
    return PublicNavigationDecisionV4(
        "click", matches[0], "one opened public row action exposes one exact Edit control", "opened_row_edit"
    )


def _row_action_matches(
    snapshot: SemanticSnapshot, expanded: PublicNavigationInventoryV3, row_bid: str
) -> list[PublicNavigationCandidateV3]:
    action_matches: list[PublicNavigationCandidateV3] = []
    for candidate in expanded.candidates:
        if _normalized_text(candidate.label) not in ROW_ACTION_LABELS_V5:
            continue
        element = snapshot.get(candidate.bid)
        if element is not None and _belongs_to_row_v5(snapshot, element, row_bid):
            action_matches.append(candidate)
    return action_matches
