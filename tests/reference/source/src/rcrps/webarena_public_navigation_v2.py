"""Broader public-only navigation for WebArena development.

The v1 navigator admitted only explicit same-origin links and a small set of
disclosure controls.  That boundary was too narrow on the three registered
development pages: account menus and JavaScript-backed navigation controls
were omitted, leaving the planner no relevant public action.  V2 keeps the
same information boundary while exposing labelled, visible, clickable
non-form controls together with short public ancestor context.

No task identifier, evaluator field, reward, hidden state, CSS selector, or
site-specific route enters this module.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any, Iterable
from urllib.parse import urlsplit

from .transaction_actions_v4 import ContractActionV4
from .typed_observation import SemanticElement, SemanticSnapshot
from .webarena_public_navigation_v1 import (
    DANGEROUS_LINK_PATH_V1,
    DANGEROUS_LINK_TEXT_V1,
    GOAL_STOPWORDS_V1,
    TERMINAL_CONTROL_TEXT_V1,
    _normalized_url,
    _same_origin_http_href,
    _state,
    _tokens,
)


NAVIGATION_TAG_V2 = re.compile(
    r"<INVERSE_NAVIGATION>(?P<payload>.*?)</INVERSE_NAVIGATION>",
    re.DOTALL,
)
FORM_ROLES_V2 = frozenset(
    {
        "checkbox",
        "combobox",
        "listbox",
        "option",
        "radio",
        "searchbox",
        "slider",
        "spinbutton",
        "textbox",
    }
)
FORM_TAGS_V2 = frozenset({"select", "textarea"})
CONTROL_ROLES_V2 = frozenset(
    {
        "button",
        "link",
        "menuitem",
        "tab",
        "treeitem",
    }
)
CONTROL_TAGS_V2 = frozenset({"a", "button"})
GENERIC_NAVIGATION_TOKENS_V2 = frozenset(
    {
        "account",
        "admin",
        "address",
        "content",
        "dashboard",
        "edit",
        "menu",
        "orders",
        "pages",
        "preferences",
        "profile",
        "settings",
        "user",
    }
)


def _text(value: object, *, limit: int = 180) -> str:
    normalized = " ".join(str(value or "").split())
    return normalized[:limit]


def _label(element: SemanticElement) -> str:
    return _text(element.name or element.subtree_text)


def _context(snapshot: SemanticSnapshot, element: SemanticElement) -> str:
    """Return bounded public ancestry, excluding the candidate's own label."""

    own = _label(element).casefold()
    pieces: list[str] = []
    ancestors = (
        snapshot.ancestors(element.bid, relation="ax")[:3]
        + snapshot.ancestors(element.bid, relation="dom")[:3]
    )
    for ancestor in ancestors:
        value = _text(ancestor.name or ancestor.subtree_text, limit=120)
        if not value or value.casefold() == own or value in pieces:
            continue
        pieces.append(value)
        if len(" | ".join(pieces)) >= 300:
            break
    return _text(" | ".join(pieces), limit=320)


def _safe_click_kind(
    element: SemanticElement,
    *,
    current_url: str,
) -> tuple[str, str | None] | None:
    role = element.role.casefold()
    tag = element.dom_tag.casefold()
    label = _label(element)
    if not label or DANGEROUS_LINK_TEXT_V1.search(label):
        return None
    if role in FORM_ROLES_V2 or tag in FORM_TAGS_V2:
        return None
    input_type = str(element.dom_attribute("type", "")).casefold()
    if tag == "input" and input_type != "button":
        return None
    if input_type in {"submit", "reset"} or element.dom_attribute("formaction"):
        return None

    is_link = role == "link" or tag == "a"
    if is_link:
        raw_href = str(element.dom_attribute("href", "") or "").strip()
        href = _same_origin_http_href(current_url, raw_href)
        if href is not None:
            return "same_origin_get_link", href
        if raw_href:
            parsed = urlsplit(raw_href)
            if parsed.scheme or parsed.netloc:
                return None
            if DANGEROUS_LINK_PATH_V1.search(raw_href):
                return None
            if not raw_href.startswith(("#", "javascript:")):
                return None
        if TERMINAL_CONTROL_TEXT_V1.search(label):
            return None
        return "public_click_control", None

    if (
        role not in CONTROL_ROLES_V2
        and tag not in CONTROL_TAGS_V2
        and not element.clickable
    ):
        return None
    if TERMINAL_CONTROL_TEXT_V1.search(label):
        return None
    return "public_click_control", None


def _object_sha256(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")
    ).hexdigest()


@dataclass(frozen=True)
class PublicNavigationCandidateV2:
    bid: str
    label: str
    role: str
    kind: str
    href: str | None
    goal_overlap: int
    context_overlap: int
    generic_navigation_overlap: int
    context: str
    state: tuple[tuple[str, Any], ...]

    @property
    def action(self) -> ContractActionV4:
        return ContractActionV4("click", self.bid)

    def record(self) -> dict[str, object]:
        return {
            "bid": self.bid,
            "label": self.label,
            "role": self.role,
            "kind": self.kind,
            "href": self.href,
            "goal_overlap": self.goal_overlap,
            "context_overlap": self.context_overlap,
            "generic_navigation_overlap": self.generic_navigation_overlap,
            "context": self.context,
            "state": [[name, value] for name, value in self.state],
        }


@dataclass(frozen=True)
class PublicNavigationInventoryV2:
    candidates: tuple[PublicNavigationCandidateV2, ...]
    visible_clickable_count: int
    visible_eligible_count: int
    duplicate_href_count: int
    omitted_count: int
    maximum_candidates: int

    def record(self) -> dict[str, object]:
        return {
            "candidates": [row.record() for row in self.candidates],
            "visible_clickable_count": self.visible_clickable_count,
            "visible_eligible_count": self.visible_eligible_count,
            "duplicate_href_count": self.duplicate_href_count,
            "omitted_count": self.omitted_count,
            "maximum_candidates": self.maximum_candidates,
            "uses_task_id": False,
            "uses_evaluator": False,
            "uses_reward": False,
            "uses_hidden_state": False,
            "uses_site_specific_route": False,
            "uses_css_selector": False,
        }


def navigation_attempt_key_v2(
    *,
    snapshot: SemanticSnapshot,
    current_url: str,
    bid: str,
) -> str:
    return _object_sha256(
        {
            "semantic_fingerprint": snapshot.semantic_fingerprint(),
            "url": _normalized_url(current_url),
            "bid": str(bid),
        }
    )


def _rank(row: PublicNavigationCandidateV2) -> tuple[object, ...]:
    label_tokens = _tokens(row.label)
    weak_label = not label_tokens or all(token.isdigit() for token in label_tokens)
    return (
        -row.goal_overlap,
        -row.context_overlap,
        -row.generic_navigation_overlap,
        weak_label,
        row.kind == "same_origin_get_link",
        row.label.casefold(),
        row.bid,
    )


def compile_public_navigation_v2(
    snapshot: SemanticSnapshot,
    *,
    current_url: str,
    goal: str,
    quarantined_attempt_keys: Iterable[str] = (),
    maximum_candidates: int = 64,
) -> PublicNavigationInventoryV2:
    if not 1 <= int(maximum_candidates) <= 128:
        raise ValueError("public navigation candidate bound is invalid")
    parsed = urlsplit(str(current_url))
    if parsed.scheme not in {"http", "https"} or parsed.hostname is None:
        raise ValueError("current public URL is not an HTTP origin")
    goal_tokens = set(_tokens(goal)) - GOAL_STOPWORDS_V1
    quarantined = set(str(key) for key in quarantined_attempt_keys)
    visible_clickable = 0
    rows: list[PublicNavigationCandidateV2] = []
    for element in snapshot.elements:
        if not snapshot.is_effectively_visible(element.bid) or not element.clickable:
            continue
        visible_clickable += 1
        kind = _safe_click_kind(element, current_url=current_url)
        if kind is None:
            continue
        attempt_key = navigation_attempt_key_v2(
            snapshot=snapshot,
            current_url=current_url,
            bid=element.bid,
        )
        if attempt_key in quarantined:
            continue
        candidate_kind, href = kind
        label = _label(element)
        context = _context(snapshot, element)
        label_tokens = set(_tokens(label)) | set(_tokens(href or ""))
        context_tokens = set(_tokens(context))
        rows.append(
            PublicNavigationCandidateV2(
                bid=element.bid,
                label=label,
                role=element.role or element.dom_tag,
                kind=candidate_kind,
                href=href,
                goal_overlap=len(goal_tokens & label_tokens),
                context_overlap=len(goal_tokens & context_tokens),
                generic_navigation_overlap=len(
                    (label_tokens | context_tokens) & GENERIC_NAVIGATION_TOKENS_V2
                ),
                context=context,
                state=_state(element),
            )
        )
    if len({row.bid for row in rows}) != len(rows):
        raise ValueError("public navigation inventory has duplicate bids")

    # One public destination needs one candidate.  Prefer the candidate with
    # the strongest semantic label/context rather than repeated numeric badges.
    best_by_href: dict[str, PublicNavigationCandidateV2] = {}
    controls: list[PublicNavigationCandidateV2] = []
    duplicate_hrefs = 0
    for row in rows:
        if row.href is None:
            controls.append(row)
            continue
        previous = best_by_href.get(row.href)
        if previous is None or _rank(row) < _rank(previous):
            if previous is not None:
                duplicate_hrefs += 1
            best_by_href[row.href] = row
        else:
            duplicate_hrefs += 1
    unique_rows = controls + list(best_by_href.values())
    ranked = sorted(unique_rows, key=_rank)

    # Preserve public controls even on link-dense dashboards.  These controls
    # contain the account/sidebar disclosures omitted by v1.
    control_quota = min(24, int(maximum_candidates))
    ranked_controls = [row for row in ranked if row.href is None]
    retained = ranked_controls[:control_quota]
    retained_bids = {row.bid for row in retained}
    retained.extend(
        row
        for row in ranked
        if row.bid not in retained_bids
    )
    retained = retained[: int(maximum_candidates)]
    return PublicNavigationInventoryV2(
        tuple(retained),
        visible_clickable,
        len(unique_rows),
        duplicate_hrefs,
        max(0, len(unique_rows) - len(retained)),
        int(maximum_candidates),
    )


def navigation_messages_v2(
    *,
    goal: str,
    current_url: str,
    inventory: PublicNavigationInventoryV2,
    navigation_history: Iterable[dict[str, Any]] = (),
) -> list[dict[str, str]]:
    payload = {
        "goal": str(goal),
        "current_url": _normalized_url(current_url),
        "candidates": [row.record() for row in inventory.candidates],
        "recent_navigation": list(navigation_history)[-10:],
    }
    return [
        {
            "role": "system",
            "content": (
                "Navigate toward the requested editable field using only the current "
                "public candidates. This is a navigation step, not the final mutation. "
                "Account, profile, settings, content, pages, orders, and menu controls "
                "are legitimate intermediate steps when supported by the goal. Prefer "
                "a semantically related menu or destination and never invent a bid. "
                "Abstain only when every candidate is clearly unrelated or terminal. "
                "Respond with exactly <INVERSE_NAVIGATION>{\"decision\":\"click\","
                "\"bid\":\"...\"}</INVERSE_NAVIGATION>, or decision abstain with "
                "a null bid."
            ),
        },
        {
            "role": "user",
            "content": json.dumps(
                payload,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ),
        },
    ]


@dataclass(frozen=True)
class PublicNavigationDecisionV2:
    decision: str
    candidate: PublicNavigationCandidateV2 | None
    reason: str

    @property
    def allowed(self) -> bool:
        return self.decision == "click" and self.candidate is not None

    def record(self) -> dict[str, object]:
        return {
            "decision": self.decision,
            "bid": None if self.candidate is None else self.candidate.bid,
            "reason": self.reason,
            "allowed": self.allowed,
        }


def resolve_public_navigation_v2(
    inventory: PublicNavigationInventoryV2,
    *,
    model_output: str,
) -> PublicNavigationDecisionV2:
    matches = list(NAVIGATION_TAG_V2.finditer(str(model_output)))
    if len(matches) != 1:
        raise ValueError("navigation model output must contain exactly one tagged object")
    try:
        payload = json.loads(matches[0].group("payload"))
    except json.JSONDecodeError as error:
        raise ValueError("navigation model output is not valid JSON") from error
    if not isinstance(payload, dict) or set(payload) != {"decision", "bid"}:
        raise ValueError("navigation model output schema changed")
    if payload["decision"] == "abstain" and payload["bid"] is None:
        return PublicNavigationDecisionV2(
            "abstain", None, "public navigator abstained"
        )
    if payload["decision"] != "click" or not isinstance(payload["bid"], str):
        raise ValueError("navigation model decision is invalid")
    candidates = [row for row in inventory.candidates if row.bid == payload["bid"]]
    if len(candidates) != 1:
        raise ValueError("navigation model selected a bid outside the current inventory")
    return PublicNavigationDecisionV2(
        "click", candidates[0], "one current public navigation bid was selected"
    )


@dataclass(frozen=True)
class PublicNavigationEffectV2:
    effective: bool
    reason: str
    attempt_key: str
    url_changed: bool
    semantic_fingerprint_changed: bool

    def record(self) -> dict[str, object]:
        return {
            "effective": self.effective,
            "reason": self.reason,
            "attempt_key": self.attempt_key,
            "url_changed": self.url_changed,
            "semantic_fingerprint_changed": self.semantic_fingerprint_changed,
        }


def check_public_navigation_effect_v2(
    *,
    before: SemanticSnapshot,
    after: SemanticSnapshot,
    before_url: str,
    after_url: str,
    candidate: PublicNavigationCandidateV2,
) -> PublicNavigationEffectV2:
    key = navigation_attempt_key_v2(
        snapshot=before,
        current_url=before_url,
        bid=candidate.bid,
    )
    url_changed = _normalized_url(before_url) != _normalized_url(after_url)
    semantic_changed = before.semantic_fingerprint() != after.semantic_fingerprint()
    effective = url_changed or semantic_changed
    return PublicNavigationEffectV2(
        effective,
        (
            "public URL or semantic fingerprint changed"
            if effective
            else "navigation produced zero public effect"
        ),
        key,
        url_changed,
        semantic_changed,
    )
