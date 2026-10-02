"""Bounded public navigation with standard-control coverage and loop control.

V3 is informed only by the three already-open development episodes.  It adds
standard visible buttons and links even when BrowserGym omits its optional
``clickable`` marker, precomputes one public state key per observation, and
permits a second state-action attempt only after a public error page is seen.
No task identifier, evaluator field, reward, hidden state, CSS selector, or
site-specific route enters the interface.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from dataclasses import dataclass
from typing import Any, Iterable, Mapping
from urllib.parse import urlsplit

from inversereserve.adapters.webarena.webarena_public_navigation_v1 import (
    GOAL_STOPWORDS_V1,
    _normalized_url,
    _state,
    _tokens,
)
from inversereserve.adapters.webarena.webarena_public_navigation_v2 import (
    CONTROL_ROLES_V2,
    CONTROL_TAGS_V2,
    GENERIC_NAVIGATION_TOKENS_V2,
    _context,
    _label,
    _safe_click_kind,
)
from inversereserve.contracts.transaction_actions_v4 import ContractActionV4
from inversereserve.observations.typed_observation import SemanticElement, SemanticSnapshot

NAVIGATION_TAG_V3 = re.compile("<INVERSE_NAVIGATION>(?P<payload>.*?)</INVERSE_NAVIGATION>", re.DOTALL)
AMBIGUOUS_CONTROL_LABELS_V3 = frozenset({"action", "actions", "name", "option", "options", "select"})
PUBLIC_RECOVERY_PATTERNS_V3: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("bad_gateway", re.compile("\\bbad\\s+gateway\\b|\\b502\\b", re.I)),
    ("not_responding", re.compile("\\bnot\\s+responding\\b|\\btaking\\s+too\\s+much\\s+time\\b", re.I)),
    (
        "retry_guidance",
        re.compile(
            "\\btry\\s+(?:refreshing|again)\\b|\\bgoing\\s+back\\b|\\btemporar(?:y|ily)\\s+unavailable\\b|\\bservice\\s+unavailable\\b",
            re.I,
        ),
    ),
)


def _object_sha256(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode(
            "utf-8"
        )
    ).hexdigest()


def navigation_state_key_v3(*, snapshot: SemanticSnapshot, current_url: str) -> str:
    return _object_sha256(
        {"semantic_fingerprint": snapshot.semantic_fingerprint(), "url": _normalized_url(current_url)}
    )


def navigation_state_action_key_v3(*, state_key: str, bid: str) -> str:
    return _object_sha256({"public_state_key": str(state_key), "bid": str(bid)})


def navigation_attempt_key_v3(*, state_action_key: str, attempt_ordinal: int) -> str:
    if int(attempt_ordinal) < 1:
        raise ValueError("navigation attempt ordinal must be positive")
    return _object_sha256(
        {"state_action_key": str(state_action_key), "attempt_ordinal": int(attempt_ordinal)}
    )


def _public_disabled(element: SemanticElement) -> bool:
    values = (element.ax_property("disabled"), element.dom_attribute("aria-disabled"))
    return bool(
        element.dom_attribute("disabled", None) is not None
        or any((value is True or str(value).casefold() == "true" for value in values))
    )


def _inside_dom_form(snapshot: SemanticSnapshot, element: SemanticElement) -> bool:
    return bool(
        element.dom_tag.casefold() == "form"
        or any((row.dom_tag.casefold() == "form" for row in snapshot.ancestors(element.bid, relation="dom")))
    )


def _standard_control(element: SemanticElement) -> bool:
    return bool(element.role.casefold() in CONTROL_ROLES_V2 or element.dom_tag.casefold() in CONTROL_TAGS_V2)


def _disclosure_score(element: SemanticElement) -> int:
    values = (element.ax_property("hasPopup"), element.dom_attribute("aria-haspopup"))
    has_popup = any(
        (value is True or str(value).casefold() in {"true", "menu", "listbox", "dialog"} for value in values)
    )
    expanded_is_public = (
        element.ax_property("expanded") is not None or element.dom_attribute("aria-expanded") is not None
    )
    return int(has_popup) + int(expanded_is_public)


@dataclass(frozen=True)
class PublicRecoverySignalV3:
    detected: bool
    matched_public_patterns: tuple[str, ...]
    visible_text_sha256: str

    def record(self) -> dict[str, object]:
        return {
            "detected": self.detected,
            "matched_public_patterns": list(self.matched_public_patterns),
            "visible_text_sha256": self.visible_text_sha256,
            "uses_status_code": False,
            "uses_network_log": False,
            "uses_evaluator": False,
            "uses_hidden_state": False,
        }


def detect_public_recovery_signal_v3(snapshot: SemanticSnapshot) -> PublicRecoverySignalV3:
    pieces: list[str] = []
    seen: set[str] = set()
    for element in snapshot.elements:
        if not snapshot.is_effectively_visible(element.bid):
            continue
        value = " ".join(str(element.name or element.subtree_text).split())
        if value and value not in seen:
            seen.add(value)
            pieces.append(value[:500])
    public_text = "\n".join(pieces)
    matches = tuple((name for name, pattern in PUBLIC_RECOVERY_PATTERNS_V3 if pattern.search(public_text)))
    return PublicRecoverySignalV3(
        bool(matches), matches, hashlib.sha256(public_text.encode("utf-8")).hexdigest()
    )


@dataclass(frozen=True)
class PublicNavigationCandidateV3:
    bid: str
    label: str
    role: str
    kind: str
    href: str | None
    goal_overlap: int
    context_overlap: int
    generic_navigation_overlap: int
    disclosure_score: int
    context: str
    state: tuple[tuple[str, Any], ...]
    state_action_key: str
    prior_attempts: int
    retry_authorized: bool

    @property
    def action(self) -> ContractActionV4:
        return ContractActionV4("click", self.bid)

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
            "goal_overlap": self.goal_overlap,
            "context_overlap": self.context_overlap,
            "generic_navigation_overlap": self.generic_navigation_overlap,
            "disclosure_score": self.disclosure_score,
            "context": self.context,
            "state": [[name, value] for name, value in self.state],
            "prior_attempts": self.prior_attempts,
            "attempt_ordinal": self.attempt_ordinal,
            "retry_authorized": self.retry_authorized,
        }
        if include_key:
            row["state_action_key"] = self.state_action_key
        return row


@dataclass(frozen=True)
class PublicNavigationInventoryV3:
    candidates: tuple[PublicNavigationCandidateV3, ...]
    visible_action_marker_count: int
    visible_standard_control_count: int
    standard_controls_without_action_marker: int
    visible_eligible_count: int
    duplicate_href_count: int
    exhausted_attempt_count: int
    omitted_count: int
    maximum_candidates: int
    public_state_key: str
    retry_authorized: bool

    def record(self) -> dict[str, object]:
        return {
            "candidates": [row.record() for row in self.candidates],
            "visible_action_marker_count": self.visible_action_marker_count,
            "visible_standard_control_count": self.visible_standard_control_count,
            "standard_controls_without_action_marker": self.standard_controls_without_action_marker,
            "visible_eligible_count": self.visible_eligible_count,
            "duplicate_href_count": self.duplicate_href_count,
            "exhausted_attempt_count": self.exhausted_attempt_count,
            "omitted_count": self.omitted_count,
            "maximum_candidates": self.maximum_candidates,
            "public_state_key": self.public_state_key,
            "retry_authorized": self.retry_authorized,
            "uses_task_id": False,
            "uses_evaluator": False,
            "uses_reward": False,
            "uses_hidden_state": False,
            "uses_site_specific_route": False,
            "uses_css_selector": False,
        }

    def planner_records(self) -> list[dict[str, object]]:
        return [row.record(include_key=False) for row in self.candidates]


def _rank(row: PublicNavigationCandidateV3) -> tuple[object, ...]:
    label_tokens = set(_tokens(row.label))
    ambiguous = bool(label_tokens) and label_tokens <= AMBIGUOUS_CONTROL_LABELS_V3
    weak_label = not label_tokens or all((token.isdigit() for token in label_tokens))
    semantic_score = (
        row.goal_overlap
        + row.context_overlap
        + row.generic_navigation_overlap
        + row.disclosure_score
        - 2 * int(ambiguous)
    )
    return (
        -semantic_score,
        ambiguous,
        -row.goal_overlap,
        -row.context_overlap,
        -row.disclosure_score,
        -row.generic_navigation_overlap,
        weak_label,
        row.kind == "same_origin_get_link",
        row.label.casefold(),
        row.bid,
    )


def compile_public_navigation_v3(
    snapshot: SemanticSnapshot,
    *,
    current_url: str,
    goal: str,
    attempt_counts: Mapping[str, int] | None = None,
    retry_authorized: bool = False,
    maximum_candidates: int = 64,
) -> PublicNavigationInventoryV3:
    if not 1 <= int(maximum_candidates) <= 128:
        raise ValueError("public navigation candidate bound is invalid")
    parsed = urlsplit(str(current_url))
    if parsed.scheme not in {"http", "https"} or parsed.hostname is None:
        raise ValueError("current public URL is not an HTTP origin")
    counts = _normalized_attempt_counts(attempt_counts)
    if any((value < 0 for value in counts.values())):
        raise ValueError("navigation attempt count is negative")
    state_key = navigation_state_key_v3(snapshot=snapshot, current_url=current_url)
    goal_tokens = set(_tokens(goal)) - GOAL_STOPWORDS_V1
    action_markers = 0
    standard_controls = 0
    standard_without_marker = 0
    exhausted = 0
    rows: list[PublicNavigationCandidateV3] = []
    for element in snapshot.elements:
        if not snapshot.is_effectively_visible(element.bid):
            continue
        standard = _standard_control(element)
        action_markers += int(element.clickable)
        standard_controls += int(standard)
        standard_without_marker += int(standard and (not element.clickable))
        if _navigation_control_excluded(snapshot, element, standard):
            continue
        kind = _safe_click_kind(element, current_url=current_url)
        if kind is None:
            continue
        state_action_key, prior = _prior_navigation_attempts(state_key, element, counts)
        maximum_attempts = 2 if retry_authorized else 1
        if prior >= maximum_attempts:
            exhausted += 1
            continue
        rows.append(
            _navigation_candidate_v3(
                element, snapshot, goal_tokens, kind, state_action_key, prior, retry_authorized
            )
        )
    if len({row.bid for row in rows}) != len(rows):
        raise ValueError("public navigation inventory has duplicate bids")
    retained, unique_count, duplicate_hrefs = _rank_public_candidates_v3(rows, maximum_candidates)
    return PublicNavigationInventoryV3(
        tuple(retained),
        action_markers,
        standard_controls,
        standard_without_marker,
        unique_count,
        duplicate_hrefs,
        exhausted,
        max(0, unique_count - len(retained)),
        int(maximum_candidates),
        state_key,
        bool(retry_authorized),
    )


def navigation_messages_v3(
    *,
    goal: str,
    current_url: str,
    inventory: PublicNavigationInventoryV3,
    navigation_history: Iterable[dict[str, Any]] = (),
    recovery_signal: PublicRecoverySignalV3 | None = None,
) -> list[dict[str, str]]:
    recovery = recovery_signal or PublicRecoverySignalV3(False, (), hashlib.sha256(b"").hexdigest())
    payload = {
        "goal": str(goal),
        "current_url": _normalized_url(current_url),
        "public_recovery_signal": recovery.record(),
        "candidates": inventory.planner_records(),
        "recent_navigation": list(navigation_history)[-12:],
    }
    return [
        {
            "role": "system",
            "content": 'Navigate toward the requested editable field using only the current public candidates. This is navigation, not the final mutation. Personal-name disclosures and account/profile/settings/content/pages controls are legitimate intermediate steps. Avoid revisiting a recent state-action pair. When the public page says it is unavailable or asks to go back or retry, use a safe current back/home control. Never a bid. Abstain only when every candidate is clearly unrelated or terminal. Respond with exactly <INVERSE_NAVIGATION>{"decision":"click","bid":"..."}</INVERSE_NAVIGATION>, or decision abstain with a null bid.',
        },
        {
            "role": "user",
            "content": json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        },
    ]


@dataclass(frozen=True)
class PublicNavigationDecisionV3:
    decision: str
    candidate: PublicNavigationCandidateV3 | None
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


def resolve_public_navigation_v3(
    inventory: PublicNavigationInventoryV3, *, model_output: str
) -> PublicNavigationDecisionV3:
    matches = list(NAVIGATION_TAG_V3.finditer(str(model_output)))
    if len(matches) != 1:
        raise ValueError("navigation model output must contain exactly one tagged object")
    try:
        payload = json.loads(matches[0].group("payload"))
    except json.JSONDecodeError as error:
        raise ValueError("navigation model output is not valid JSON") from error
    if not isinstance(payload, dict) or set(payload) != {"decision", "bid"}:
        raise ValueError("navigation model output schema changed")
    if payload["decision"] == "abstain" and payload["bid"] is None:
        return PublicNavigationDecisionV3("abstain", None, "public navigator abstained")
    if payload["decision"] != "click" or not isinstance(payload["bid"], str):
        raise ValueError("navigation model decision is invalid")
    candidates = [row for row in inventory.candidates if row.bid == payload["bid"]]
    if len(candidates) != 1:
        raise ValueError("navigation model selected a bid outside the current inventory")
    return PublicNavigationDecisionV3(
        "click", candidates[0], "one current public navigation bid was selected"
    )


@dataclass(frozen=True)
class PublicNavigationEffectV3:
    effective: bool
    reason: str
    state_action_key: str
    attempt_key: str
    attempt_ordinal: int
    retry_authorized: bool
    url_changed: bool
    semantic_fingerprint_changed: bool

    def record(self) -> dict[str, object]:
        return {
            "effective": self.effective,
            "reason": self.reason,
            "state_action_key": self.state_action_key,
            "attempt_key": self.attempt_key,
            "attempt_ordinal": self.attempt_ordinal,
            "retry_authorized": self.retry_authorized,
            "url_changed": self.url_changed,
            "semantic_fingerprint_changed": self.semantic_fingerprint_changed,
        }


def check_public_navigation_effect_v3(
    *,
    before: SemanticSnapshot,
    after: SemanticSnapshot,
    before_url: str,
    after_url: str,
    candidate: PublicNavigationCandidateV3,
) -> PublicNavigationEffectV3:
    url_changed = _normalized_url(before_url) != _normalized_url(after_url)
    semantic_changed = before.semantic_fingerprint() != after.semantic_fingerprint()
    effective = url_changed or semantic_changed
    return PublicNavigationEffectV3(
        effective=effective,
        reason="public URL or semantic fingerprint changed"
        if effective
        else "navigation produced zero public effect",
        state_action_key=candidate.state_action_key,
        attempt_key=navigation_attempt_key_v3(
            state_action_key=candidate.state_action_key, attempt_ordinal=candidate.attempt_ordinal
        ),
        attempt_ordinal=candidate.attempt_ordinal,
        retry_authorized=candidate.retry_authorized,
        url_changed=url_changed,
        semantic_fingerprint_changed=semantic_changed,
    )


def _rank_public_candidates_v3(
    rows: list[PublicNavigationCandidateV3], maximum_candidates: int
) -> tuple[list[PublicNavigationCandidateV3], int, int]:
    best_by_href: dict[str, PublicNavigationCandidateV3] = {}
    controls: list[PublicNavigationCandidateV3] = []
    duplicate_hrefs = 0
    for row in rows:
        if row.href is None:
            controls.append(row)
            continue
        previous = best_by_href.get(row.href)
        if previous is None or _rank(row) < _rank(previous):
            duplicate_hrefs += int(previous is not None)
            best_by_href[row.href] = row
        else:
            duplicate_hrefs += 1
    unique_rows = controls + list(best_by_href.values())
    ranked = sorted(unique_rows, key=_rank)
    control_quota = min(24, int(maximum_candidates))
    ranked_controls = [row for row in ranked if row.href is None]
    retained = ranked_controls[:control_quota]
    retained_bids = {row.bid for row in retained}
    retained.extend((row for row in ranked if row.bid not in retained_bids))
    retained = retained[: int(maximum_candidates)]
    return (retained, len(unique_rows), duplicate_hrefs)


def _navigation_candidate_v3(
    element: SemanticElement,
    snapshot: SemanticSnapshot,
    goal_tokens: set[str],
    kind: tuple[str, str | None],
    state_action_key: str,
    prior: int,
    retry_authorized: bool,
) -> PublicNavigationCandidateV3:
    candidate_kind, href = kind
    label = _label(element)
    context = _context(snapshot, element)
    label_tokens = set(_tokens(label)) | set(_tokens(href or ""))
    context_tokens = set(_tokens(context))
    return PublicNavigationCandidateV3(
        bid=element.bid,
        label=label,
        role=element.role or element.dom_tag,
        kind=candidate_kind,
        href=href,
        goal_overlap=len(goal_tokens & label_tokens),
        context_overlap=len(goal_tokens & context_tokens),
        generic_navigation_overlap=len((label_tokens | context_tokens) & GENERIC_NAVIGATION_TOKENS_V2),
        disclosure_score=_disclosure_score(element),
        context=context,
        state=_state(element),
        state_action_key=state_action_key,
        prior_attempts=prior,
        retry_authorized=bool(retry_authorized and prior > 0),
    )


def _navigation_control_excluded(
    snapshot: SemanticSnapshot, element: SemanticElement, standard: bool
) -> bool:
    return (
        not element.clickable
        and (not standard)
        or _public_disabled(element)
        or _inside_dom_form(snapshot, element)
        or (element.dom_attribute("form", None) is not None)
    )


def _prior_navigation_attempts(
    state_key: str, element: SemanticElement, counts: Mapping[str, int]
) -> tuple[str, int]:
    state_action_key = navigation_state_action_key_v3(state_key=state_key, bid=element.bid)
    prior = int(counts[state_action_key])
    return (state_action_key, prior)


def _normalized_attempt_counts(attempt_counts: Mapping[str, int] | None) -> Counter[str]:
    return Counter({str(key): int(value) for key, value in (attempt_counts or {}).items()})
