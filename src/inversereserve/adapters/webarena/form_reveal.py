"""Bounded public form reveal: resolve visible identities, prove joint bounds, then admit one scroll."""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Mapping

from inversereserve.adapters.webarena.webarena_exact_mutation_v1 import (
    _anchor_score,
    _submit_like_label,
    _tokens,
    parse_exact_mutation_v1,
)
from inversereserve.adapters.webarena.webarena_goal_adapter_v1 import _nearest_dom_form, _public_boolean
from inversereserve.adapters.webarena.webarena_public_navigation_v3 import navigation_state_action_key_v3
from inversereserve.adapters.webarena.webarena_public_navigation_v4 import _normalized_text
from inversereserve.contracts.typed_contracts_v4 import TEXT_INPUT_ROLES
from inversereserve.observations.typed_observation import SemanticElement, SemanticSnapshot

MAXIMUM_PUBLIC_FORM_SCROLL_PIXELS_V6 = 4096
MAXIMUM_PUBLIC_FORM_SCROLL_VIEWPORTS_V6 = 4
MAXIMUM_LOCAL_LABEL_DESCENDANTS_V6 = 32


def _publicly_rendered_v6(snapshot: SemanticSnapshot, element: SemanticElement) -> bool:
    """Separate off-viewport public content from hidden DOM state."""
    if element.bbox is None or element.bbox[2] <= 0 or element.bbox[3] <= 0:
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


def _tokens_from_v6(values: list[object]) -> set[str]:
    return {token for value in values for token in _tokens(value)}


def _direct_label_tokens_v6(snapshot: SemanticSnapshot, element: SemanticElement) -> set[str]:
    values: list[object] = [
        element.name,
        element.subtree_text,
        element.dom_attribute("placeholder", ""),
        element.dom_attribute("aria-label", ""),
        element.dom_attribute("name", ""),
        element.dom_attribute("id", ""),
    ]
    element_id = _normalized_text(element.dom_attribute("id", ""))
    labelled_by = {token for token in str(element.dom_attribute("aria-labelledby", "")).split() if token}
    for candidate in snapshot.elements:
        if not _publicly_rendered_v6(snapshot, candidate):
            continue
        candidate_id = str(candidate.dom_attribute("id", ""))
        explicit_for = _normalized_text(candidate.dom_attribute("for", ""))
        if (
            element_id
            and candidate.dom_tag.casefold() == "label"
            and (explicit_for == element_id)
            or (candidate_id and candidate_id in labelled_by)
        ):
            values.extend((candidate.name, candidate.subtree_text))
    return _tokens_from_v6(values)


def _local_wrapper_tokens_v6(snapshot: SemanticSnapshot, element: SemanticElement) -> set[str]:
    for ancestor in snapshot.ancestors(element.bid, relation="dom"):
        if ancestor.dom_tag.casefold() == "form":
            break
        descendants = snapshot.descendants(ancestor.bid, relation="dom")
        if len(descendants) <= MAXIMUM_LOCAL_LABEL_DESCENDANTS_V6 and _publicly_rendered_v6(
            snapshot, ancestor
        ):
            return _tokens_from_v6([ancestor.name, ancestor.subtree_text])
    return set()


def _rendered_editable_v6(snapshot: SemanticSnapshot, element: SemanticElement) -> bool:
    return bool(
        _publicly_rendered_v6(snapshot, element)
        and (
            element.role.casefold() in TEXT_INPUT_ROLES or element.dom_tag.casefold() in {"input", "textarea"}
        )
        and (not _public_boolean(element, "readonly"))
        and (not _public_boolean(element, "disabled"))
    )


def _matching_rendered_fields_v6(
    snapshot: SemanticSnapshot, anchor_tokens: tuple[str, ...], *, include_local_wrapper: bool
) -> tuple[str, ...]:
    matches = []
    for element in snapshot.elements:
        if not _rendered_editable_v6(snapshot, element):
            continue
        labels = _direct_label_tokens_v6(snapshot, element)
        if include_local_wrapper:
            labels |= _local_wrapper_tokens_v6(snapshot, element)
        if _anchor_score(anchor_tokens, labels) == len(anchor_tokens):
            matches.append(element.bid)
    return tuple(sorted(matches))


@dataclass(frozen=True)
class PublicExactFormRevealV6:
    anchor_tokens: tuple[str, ...]
    direct_match_bids: tuple[str, ...]
    local_wrapper_match_bids: tuple[str, ...]
    target_bid: str | None
    form_bid: str | None
    submit_match_bids: tuple[str, ...]
    submit_bid: str | None
    viewport_width: int
    viewport_height: int
    joint_scroll_interval: tuple[float, float] | None
    delta_y: int | None
    exhausted: bool
    resolution: str

    @property
    def allowed(self) -> bool:
        return bool(
            self.target_bid
            and self.form_bid
            and self.submit_bid
            and (self.joint_scroll_interval is not None)
            and (self.delta_y not in {None, 0})
            and (not self.exhausted)
        )

    def record(self) -> dict[str, object]:
        return {
            "anchor_tokens": list(self.anchor_tokens),
            "direct_match_bids": list(self.direct_match_bids),
            "local_wrapper_match_bids": list(self.local_wrapper_match_bids),
            "target_bid": self.target_bid,
            "form_bid": self.form_bid,
            "submit_match_bids": list(self.submit_match_bids),
            "submit_bid": self.submit_bid,
            "viewport_width": self.viewport_width,
            "viewport_height": self.viewport_height,
            "joint_scroll_interval": None
            if self.joint_scroll_interval is None
            else list(self.joint_scroll_interval),
            "delta_y": self.delta_y,
            "exhausted": self.exhausted,
            "resolution": self.resolution,
            "allowed": self.allowed,
            "minimum_visible_fraction": 0.5,
            "maximum_scroll_pixels": MAXIMUM_PUBLIC_FORM_SCROLL_PIXELS_V6,
            "maximum_scroll_viewports": MAXIMUM_PUBLIC_FORM_SCROLL_VIEWPORTS_V6,
            "uses_public_accessible_name": True,
            "uses_public_dom_attributes": True,
            "uses_public_bbox": True,
            "uses_public_viewport": True,
            "uses_site_identity": False,
            "uses_site_specific_selector": False,
            "uses_site_specific_route": False,
            "uses_task_id": False,
            "uses_evaluator": False,
            "uses_reward": False,
            "uses_network_log": False,
            "uses_hidden_state": False,
        }


def _reveal_evidence_v6(
    *,
    anchor_tokens: tuple[str, ...],
    direct_match_bids: tuple[str, ...],
    local_wrapper_match_bids: tuple[str, ...],
    viewport_width: int,
    viewport_height: int,
    resolution: str,
    **changes: Any,
) -> PublicExactFormRevealV6:
    values: dict[str, Any] = {
        "target_bid": None,
        "form_bid": None,
        "submit_match_bids": (),
        "submit_bid": None,
        "joint_scroll_interval": None,
        "delta_y": None,
        "exhausted": False,
    }
    values.update(changes)
    return PublicExactFormRevealV6(
        anchor_tokens=anchor_tokens,
        direct_match_bids=direct_match_bids,
        local_wrapper_match_bids=local_wrapper_match_bids,
        viewport_width=int(viewport_width),
        viewport_height=int(viewport_height),
        resolution=resolution,
        **values,
    )


@dataclass(frozen=True)
class PublicScrollActionV6:
    delta_y: int
    operation: str = field(default="scroll", init=False)
    bid: None = field(default=None, init=False)

    def __post_init__(self) -> None:
        if (
            not isinstance(self.delta_y, int)
            or self.delta_y == 0
            or abs(self.delta_y) > MAXIMUM_PUBLIC_FORM_SCROLL_PIXELS_V6
        ):
            raise ValueError("public form scroll delta is unsafe")

    def browsergym_code(
        self, *, viewport_width: int | None = None, viewport_height: int | None = None
    ) -> str:
        if viewport_width is None or viewport_height is None or viewport_width <= 0 or (viewport_height <= 0):
            raise ValueError("public form scroll requires a viewport")
        if abs(self.delta_y) > MAXIMUM_PUBLIC_FORM_SCROLL_VIEWPORTS_V6 * int(viewport_height):
            raise ValueError("public form scroll exceeds viewport bound")
        return f"scroll(0, {self.delta_y})"


@dataclass(frozen=True)
class PublicFormRevealCandidateV6:
    bid: str
    label: str
    state_action_key: str
    prior_attempts: int
    delta_y: int
    role: str = "form"
    kind: str = "public_exact_form_scroll"
    href: None = None
    retry_authorized: bool = False

    @property
    def action(self) -> PublicScrollActionV6:
        return PublicScrollActionV6(self.delta_y)

    @property
    def attempt_ordinal(self) -> int:
        return self.prior_attempts + 1

    def record(self, *, include_key: bool = True) -> dict[str, object]:
        row: dict[str, object] = {
            "bid": self.bid,
            "label": self.label,
            "role": self.role,
            "kind": self.kind,
            "href": self.href,
            "goal_overlap": 0,
            "context_overlap": 0,
            "generic_navigation_overlap": 0,
            "disclosure_score": 0,
            "context": "",
            "state": [],
            "prior_attempts": self.prior_attempts,
            "attempt_ordinal": self.attempt_ordinal,
            "retry_authorized": False,
            "action_operation": "scroll",
            "delta_y": self.delta_y,
        }
        if include_key:
            row["state_action_key"] = self.state_action_key
        return row


def _rendered_submit_bids_v6(snapshot: SemanticSnapshot, form_bid: str) -> tuple[str, ...]:
    return tuple(
        sorted(
            {
                element.bid
                for element in snapshot.descendants(form_bid, relation="dom")
                if _publicly_rendered_v6(snapshot, element)
                and (element.role.casefold() == "button" or element.dom_tag.casefold() == "button")
                and element.clickable
                and (not _public_boolean(element, "disabled"))
                and _submit_like_label(element.name or element.subtree_text)
            }
        )
    )


def _half_visible_scroll_interval_v6(
    element: SemanticElement, *, viewport_width: int, viewport_height: int
) -> tuple[float, float] | None:
    if element.bbox is None:
        return None
    x, y, width, height = element.bbox
    if width <= 0 or height <= 0 or x + width / 2.0 < 0 or (x + width / 2.0 > viewport_width):
        return None
    return (y - viewport_height + height / 2.0, y + height / 2.0)


def _exact_form_reveal_v6(
    *,
    snapshot: SemanticSnapshot,
    goal: str,
    viewport_width: int,
    viewport_height: int,
    public_state_key: str,
    attempt_counts: Mapping[str, int] | None,
) -> tuple[PublicExactFormRevealV6, PublicFormRevealCandidateV6 | None]:
    clause = parse_exact_mutation_v1(str(goal).strip())
    anchors = () if clause is None else clause.anchor_tokens
    direct = (
        () if clause is None else _matching_rendered_fields_v6(snapshot, anchors, include_local_wrapper=False)
    )
    local: tuple[str, ...] = ()
    winners = direct
    if clause is not None and (not winners):
        local = _matching_rendered_fields_v6(snapshot, anchors, include_local_wrapper=True)
        winners = local
    context = FormRevealContext(anchors, direct, local, viewport_width, viewport_height)
    if clause is None:
        return (context.evidence("outside exact-mutation grammar"), None)
    if len(winners) != 1:
        return (
            context.evidence(
                "rendered exact field is ambiguous" if winners else "no rendered exact field matches"
            ),
            None,
        )
    target = snapshot.get(winners[0])
    if target is None:
        raise ValueError("rendered exact target disappeared")
    form = _nearest_dom_form(snapshot, target.bid)
    if form is None:
        return (context.evidence("rendered exact field is outside a DOM form", target_bid=target.bid), None)
    submits = _rendered_submit_bids_v6(snapshot, form.bid)
    common = {"target_bid": target.bid, "form_bid": form.bid, "submit_match_bids": submits}
    if len(submits) != 1:
        return (
            context.evidence(
                "rendered form submit is ambiguous" if submits else "rendered form has no standard submit",
                **common,
            ),
            None,
        )
    submit = snapshot.get(submits[0])
    if submit is None:
        raise ValueError("rendered exact submit disappeared")
    common["submit_bid"] = submit.bid
    return _admit_form_scroll(
        snapshot, target, submit, form, common, context, public_state_key, attempt_counts
    )


@dataclass(frozen=True)
class FormRevealContext:
    anchor_tokens: tuple[str, ...]
    direct_match_bids: tuple[str, ...]
    local_wrapper_match_bids: tuple[str, ...]
    viewport_width: int
    viewport_height: int

    def evidence(self, resolution: str, **changes: Any) -> PublicExactFormRevealV6:
        return _reveal_evidence_v6(
            anchor_tokens=self.anchor_tokens,
            direct_match_bids=self.direct_match_bids,
            local_wrapper_match_bids=self.local_wrapper_match_bids,
            viewport_width=self.viewport_width,
            viewport_height=self.viewport_height,
            resolution=resolution,
            **changes,
        )


def _admit_form_scroll(
    snapshot: SemanticSnapshot,
    target: SemanticElement,
    submit: SemanticElement,
    form: SemanticElement,
    common: dict[str, Any],
    context: FormRevealContext,
    public_state_key: str,
    attempt_counts: Mapping[str, int] | None,
) -> tuple[PublicExactFormRevealV6, PublicFormRevealCandidateV6 | None]:
    viewport_width = context.viewport_width
    viewport_height = context.viewport_height
    intervals = [
        _half_visible_scroll_interval_v6(
            element, viewport_width=viewport_width, viewport_height=viewport_height
        )
        for element in (target, submit)
    ]
    if any((row is None for row in intervals)):
        return (context.evidence("exact form bounds are not vertically revealable", **common), None)
    present = _present_scroll_intervals(intervals)
    lower = max((row[0] for row in present))
    upper = min((row[1] for row in present))
    if math.ceil(lower) > math.floor(upper):
        return (context.evidence("exact field and submit cannot share one viewport", **common), None)
    minimum, maximum = (math.ceil(lower), math.floor(upper))
    delta = min(maximum, max(minimum, int(round((lower + upper) / 2.0))))
    common.update(joint_scroll_interval=(lower, upper), delta_y=delta)
    if (
        delta == 0
        or abs(delta) > MAXIMUM_PUBLIC_FORM_SCROLL_PIXELS_V6
        or abs(delta) > MAXIMUM_PUBLIC_FORM_SCROLL_VIEWPORTS_V6 * int(viewport_height)
    ):
        return (context.evidence("joint public form scroll is zero or out of bounds", **common), None)
    state_action_key = navigation_state_action_key_v3(state_key=public_state_key, bid=form.bid)
    counts = Counter({str(key): int(value) for key, value in (attempt_counts or {}).items()})
    prior = int(counts[state_action_key])
    exhausted = prior >= 1
    common["exhausted"] = exhausted
    result = context.evidence(
        "public form reveal was already attempted in this state"
        if exhausted
        else "one public scroll jointly reveals exact field and submit",
        **common,
    )
    if exhausted:
        return (result, None)
    return (
        result,
        PublicFormRevealCandidateV6(
            bid=form.bid,
            label="exact public mutation form bounds",
            state_action_key=state_action_key,
            prior_attempts=prior,
            delta_y=delta,
        ),
    )


def _present_scroll_intervals(intervals: Any) -> Any:
    return [row for row in intervals if row is not None]
