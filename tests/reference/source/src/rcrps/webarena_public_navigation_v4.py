"""Stable public semantic binding for bounded WebArena navigation.

V4 retains the frozen V3 candidate inventory and adds three fail-closed
resolvers learned from the complete V3 development failures: stable rebinding
across public re-renders, exact quoted-entity navigation, and deterministic
matching for one replay of a previously effective public route prefix.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from .webarena_exact_mutation_v1 import parse_exact_mutation_v1
from .webarena_public_navigation_v1 import _normalized_url
from .webarena_public_navigation_v3 import (
    NAVIGATION_TAG_V3,
    PublicNavigationCandidateV3,
    PublicNavigationInventoryV3,
)


def _normalized_text(value: object) -> str:
    return " ".join(str(value or "").casefold().split())


@dataclass(frozen=True)
class PublicNavigationSignatureV4:
    label: str
    kind: str
    href: str | None

    def record(self) -> dict[str, object]:
        return {"label": self.label, "kind": self.kind, "href": self.href}

    @classmethod
    def from_record(
        cls, value: Mapping[str, object]
    ) -> "PublicNavigationSignatureV4":
        if set(value) != {"label", "kind", "href"}:
            raise ValueError("public navigation signature schema changed")
        href = value["href"]
        if href is not None and not isinstance(href, str):
            raise ValueError("public navigation signature href is invalid")
        return cls(
            _normalized_text(value["label"]),
            _normalized_text(value["kind"]),
            None if href is None else _normalized_url(href),
        )


def public_navigation_signature_v4(
    candidate: PublicNavigationCandidateV3,
) -> PublicNavigationSignatureV4:
    return PublicNavigationSignatureV4(
        _normalized_text(candidate.label),
        _normalized_text(candidate.kind),
        None if candidate.href is None else _normalized_url(candidate.href),
    )


def match_public_navigation_signature_v4(
    inventory: PublicNavigationInventoryV3,
    signature: PublicNavigationSignatureV4 | Mapping[str, object],
) -> PublicNavigationCandidateV3 | None:
    if not isinstance(signature, PublicNavigationSignatureV4):
        signature = PublicNavigationSignatureV4.from_record(signature)
    matches = [
        row
        for row in inventory.candidates
        if public_navigation_signature_v4(row) == signature
    ]
    return matches[0] if len(matches) == 1 else None


@dataclass(frozen=True)
class PublicNavigationDecisionV4:
    decision: str
    candidate: PublicNavigationCandidateV3 | None
    reason: str
    resolution_source: str
    requested_bid: str | None = None

    @property
    def allowed(self) -> bool:
        return self.decision == "click" and self.candidate is not None

    def record(self) -> dict[str, object]:
        return {
            "decision": self.decision,
            "bid": None if self.candidate is None else self.candidate.bid,
            "requested_bid": self.requested_bid,
            "reason": self.reason,
            "resolution_source": self.resolution_source,
            "allowed": self.allowed,
        }


def _navigation_payload(model_output: str) -> dict[str, object]:
    matches = list(NAVIGATION_TAG_V3.finditer(str(model_output)))
    if len(matches) != 1:
        raise ValueError(
            "navigation model output must contain exactly one tagged object"
        )
    try:
        payload = json.loads(matches[0].group("payload"))
    except json.JSONDecodeError as error:
        raise ValueError("navigation model output is not valid JSON") from error
    if not isinstance(payload, dict) or set(payload) != {"decision", "bid"}:
        raise ValueError("navigation model output schema changed")
    return payload


def resolve_public_navigation_v4(
    inventory: PublicNavigationInventoryV3,
    *,
    model_output: str,
    navigation_history: Iterable[Mapping[str, object]] = (),
) -> PublicNavigationDecisionV4:
    payload = _navigation_payload(model_output)
    if payload["decision"] == "abstain" and payload["bid"] is None:
        return PublicNavigationDecisionV4(
            "abstain",
            None,
            "public navigator abstained",
            "model_abstention",
        )
    if payload["decision"] != "click" or not isinstance(payload["bid"], str):
        raise ValueError("navigation model decision is invalid")
    requested_bid = payload["bid"]
    current = [
        row for row in inventory.candidates if row.bid == requested_bid
    ]
    if len(current) == 1:
        return PublicNavigationDecisionV4(
            "click",
            current[0],
            "one current public navigation bid was selected",
            "current_bid",
            requested_bid,
        )
    if current:
        raise ValueError("current public navigation bid is ambiguous")

    prior_signature: PublicNavigationSignatureV4 | None = None
    for event in reversed(tuple(navigation_history)):
        if str(event.get("bid", "")) != requested_bid:
            continue
        raw_signature = event.get("stable_signature")
        if not isinstance(raw_signature, Mapping):
            continue
        prior_signature = PublicNavigationSignatureV4.from_record(
            raw_signature
        )
        break
    if prior_signature is None:
        raise ValueError(
            "navigation model selected a bid outside the current inventory"
        )
    rebound = match_public_navigation_signature_v4(
        inventory, prior_signature
    )
    if rebound is None:
        raise ValueError(
            "stale navigation bid has no unique current semantic match"
        )
    return PublicNavigationDecisionV4(
        "click",
        rebound,
        "one stale public bid rebound to one stable current semantic control",
        "stable_semantic_rebind",
        requested_bid,
    )


QUOTED_SPAN_V4 = re.compile(r'(["“])(?P<text>.*?)(?:["”])')


def quoted_entity_navigation_decision_v4(
    goal: str,
    inventory: PublicNavigationInventoryV3,
) -> PublicNavigationDecisionV4 | None:
    """Bind one quoted entity in the mutation field span to one current row."""

    clause = parse_exact_mutation_v1(str(goal).strip())
    if clause is None:
        return None
    entities = {
        _normalized_text(match.group("text"))
        for match in QUOTED_SPAN_V4.finditer(clause.field_text)
        if _normalized_text(match.group("text"))
    }
    if not entities:
        return None
    matches = [
        row
        for row in inventory.candidates
        if _normalized_text(row.label) in entities
    ]
    if len(matches) != 1:
        return None
    return PublicNavigationDecisionV4(
        "click",
        matches[0],
        "one quoted public entity exactly matched one current control",
        "unique_quoted_entity",
    )


def route_prefix_signatures_v4(
    navigation_history: Iterable[Mapping[str, object]],
    *,
    maximum_steps: int = 8,
) -> tuple[PublicNavigationSignatureV4, ...]:
    """Extract the effective pre-error route prefix from public audit rows."""

    rows: list[PublicNavigationSignatureV4] = []
    for event in navigation_history:
        if not bool(event.get("effective")):
            continue
        recovery = event.get("public_recovery_signal_before")
        if isinstance(recovery, Mapping) and bool(recovery.get("detected")):
            continue
        raw_signature = event.get("stable_signature")
        if not isinstance(raw_signature, Mapping):
            continue
        signature = PublicNavigationSignatureV4.from_record(raw_signature)
        if not rows or rows[-1] != signature:
            rows.append(signature)
    return tuple(rows[-int(maximum_steps) :])
