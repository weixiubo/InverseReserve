"""Public-only navigation scaffold for WebArena exact-mutation transfer.

PACT governs the environment-changing mutation once its typed target is
visible.  Before that point, this module exposes a conservative base-agent
inventory containing same-origin HTTP links and non-submit navigation
controls.  It consumes no task ID, evaluator, reward, hidden state, CSS
selector, or site-specific route.  Dangerous, terminal, cross-origin, and
repeated no-effect candidates fail closed.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any, Iterable
from urllib.parse import urljoin, urlsplit, urlunsplit

from inversereserve.contracts.transaction_actions_v4 import ContractActionV4
from inversereserve.observations.typed_observation import SemanticElement, SemanticSnapshot

NAVIGATION_TAG_V1 = re.compile(
    r"<PACT_NAVIGATION>(?P<payload>.*?)</PACT_NAVIGATION>",
    re.DOTALL,
)
SAFE_CONTROL_ROLES_V1 = frozenset({"button", "menuitem", "tab", "treeitem"})
GOAL_STOPWORDS_V1 = frozenset(
    {
        "a",
        "an",
        "as",
        "change",
        "for",
        "in",
        "my",
        "of",
        "on",
        "set",
        "the",
        "to",
        "update",
    }
)
DANGEROUS_LINK_TEXT_V1 = re.compile(
    r"\b(?:delete|destroy|logout|log\s*out|sign\s*out|remove|unsubscribe|"
    r"checkout|place\s+order|purchase|buy\s+now|merge|close\s+account)\b",
    re.IGNORECASE,
)
DANGEROUS_LINK_PATH_V1 = re.compile(
    r"(?:^|[/_-])(?:delete|destroy|logout|signout|remove|unsubscribe|checkout|"
    r"purchase|merge)(?:$|[/_?&=-])",
    re.IGNORECASE,
)
TERMINAL_CONTROL_TEXT_V1 = re.compile(
    r"\b(?:apply|approve|buy|change|checkout|confirm|create|delete|destroy|"
    r"invite|merge|order|pay|post|purchase|reject|remove|reply|save|send|"
    r"submit|update)\b",
    re.IGNORECASE,
)


def _tokens(value: object) -> tuple[str, ...]:
    return tuple(re.findall(r"[a-z0-9]+", str(value).casefold()))


def _normalized_label(element: SemanticElement) -> str:
    return " ".join(str(element.name or element.subtree_text).split())


def _normalized_url(value: str) -> str:
    parsed = urlsplit(str(value))
    return urlunsplit(
        (
            parsed.scheme.casefold(),
            parsed.netloc.casefold(),
            parsed.path or "/",
            parsed.query,
            "",
        )
    )


def _same_origin_http_href(current_url: str, href: object) -> str | None:
    text = str(href or "").strip()
    if not text or text.startswith(("#", "javascript:", "mailto:", "tel:")):
        return None
    current = urlsplit(str(current_url))
    resolved = urlsplit(urljoin(str(current_url), text))
    if (
        current.scheme not in {"http", "https"}
        or resolved.scheme != current.scheme
        or resolved.hostname != current.hostname
        or resolved.port != current.port
        or resolved.username is not None
        or resolved.password is not None
    ):
        return None
    normalized = _normalized_url(resolved.geturl())
    if DANGEROUS_LINK_PATH_V1.search(urlsplit(normalized).path + "?" + urlsplit(normalized).query):
        return None
    return normalized


def _public_link_candidate(
    element: SemanticElement,
    *,
    current_url: str,
) -> tuple[str, str] | None:
    role = element.role.casefold()
    tag = element.dom_tag.casefold()
    if role != "link" and tag != "a":
        return None
    label = _normalized_label(element)
    if not label or DANGEROUS_LINK_TEXT_V1.search(label):
        return None
    href = _same_origin_http_href(current_url, element.dom_attribute("href"))
    if href is None:
        return None
    return "same_origin_get_link", href


def _public_control_candidate(element: SemanticElement) -> str | None:
    role = element.role.casefold()
    tag = element.dom_tag.casefold()
    if role not in SAFE_CONTROL_ROLES_V1 and not (
        tag in {"button", "input"} and str(element.dom_attribute("type", "button")).casefold() == "button"
    ):
        return None
    label = _normalized_label(element)
    if not label or TERMINAL_CONTROL_TEXT_V1.search(label):
        return None
    button_type = str(element.dom_attribute("type", "")).casefold()
    if button_type in {"submit", "reset"} or element.dom_attribute("formaction"):
        return None
    if role == "button" and not any(
        (
            element.ax_property("hasPopup"),
            element.dom_attribute("aria-haspopup"),
            element.ax_property("expanded") is not None,
            element.dom_attribute("aria-expanded") is not None,
            button_type == "button",
        )
    ):
        return None
    return "public_nonterminal_control"


def _state(element: SemanticElement) -> tuple[tuple[str, Any], ...]:
    names = {"expanded", "hasPopup", "pressed", "selected"}
    return tuple((name, value) for name, value in element.ax_properties if name in names)


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
class PublicNavigationCandidateV1:
    bid: str
    label: str
    role: str
    kind: str
    href: str | None
    goal_overlap: int
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
            "state": [[name, value] for name, value in self.state],
        }


@dataclass(frozen=True)
class PublicNavigationInventoryV1:
    candidates: tuple[PublicNavigationCandidateV1, ...]
    visible_eligible_count: int
    omitted_count: int
    maximum_candidates: int

    def record(self) -> dict[str, object]:
        return {
            "candidates": [row.record() for row in self.candidates],
            "visible_eligible_count": self.visible_eligible_count,
            "omitted_count": self.omitted_count,
            "maximum_candidates": self.maximum_candidates,
            "uses_task_id": False,
            "uses_evaluator": False,
            "uses_reward": False,
            "uses_hidden_state": False,
            "uses_site_specific_route": False,
        }


def navigation_attempt_key_v1(
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


def compile_public_navigation_v1(
    snapshot: SemanticSnapshot,
    *,
    current_url: str,
    goal: str,
    quarantined_attempt_keys: Iterable[str] = (),
    maximum_candidates: int = 64,
) -> PublicNavigationInventoryV1:
    if not 1 <= int(maximum_candidates) <= 128:
        raise ValueError("public navigation candidate bound is invalid")
    parsed = urlsplit(str(current_url))
    if parsed.scheme not in {"http", "https"} or parsed.hostname is None:
        raise ValueError("current public URL is not an HTTP origin")
    goal_tokens = set(_tokens(goal)) - GOAL_STOPWORDS_V1
    quarantined = set(str(key) for key in quarantined_attempt_keys)
    rows = []
    for element in snapshot.elements:
        if not snapshot.is_effectively_visible(element.bid) or not element.clickable:
            continue
        link = _public_link_candidate(element, current_url=current_url)
        if link is not None:
            kind, href = link
        else:
            kind = _public_control_candidate(element)
            href = None
        if kind is None:
            continue
        key = navigation_attempt_key_v1(
            snapshot=snapshot,
            current_url=current_url,
            bid=element.bid,
        )
        if key in quarantined:
            continue
        label = _normalized_label(element)
        evidence_tokens = set(_tokens(label)) | set(_tokens(href or ""))
        rows.append(
            PublicNavigationCandidateV1(
                bid=element.bid,
                label=label,
                role=element.role or element.dom_tag,
                kind=kind,
                href=href,
                goal_overlap=len(goal_tokens & evidence_tokens),
                state=_state(element),
            )
        )
    by_bid = {row.bid: row for row in rows}
    if len(by_bid) != len(rows):
        raise ValueError("public navigation inventory has duplicate bids")
    ranked = tuple(
        sorted(
            rows,
            key=lambda row: (
                -row.goal_overlap,
                row.kind != "same_origin_get_link",
                row.label.casefold(),
                row.bid,
            ),
        )
    )
    retained = ranked[: int(maximum_candidates)]
    return PublicNavigationInventoryV1(
        retained,
        len(ranked),
        len(ranked) - len(retained),
        int(maximum_candidates),
    )


def navigation_messages_v1(
    *,
    goal: str,
    current_url: str,
    inventory: PublicNavigationInventoryV1,
    navigation_history: Iterable[dict[str, Any]] = (),
) -> list[dict[str, str]]:
    payload = {
        "goal": str(goal),
        "current_url": _normalized_url(current_url),
        "candidates": [row.record() for row in inventory.candidates],
        "recent_navigation": list(navigation_history)[-8:],
    }
    return [
        {
            "role": "system",
            "content": (
                "Select one public navigation candidate that moves toward the goal. "
                "Do not invent a bid. Respond with exactly "
                '<PACT_NAVIGATION>{"decision":"click","bid":"..."}'
                "</PACT_NAVIGATION>, or use decision abstain and bid null."
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
class PublicNavigationDecisionV1:
    decision: str
    candidate: PublicNavigationCandidateV1 | None
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


def resolve_public_navigation_v1(
    inventory: PublicNavigationInventoryV1,
    *,
    model_output: str,
) -> PublicNavigationDecisionV1:
    matches = list(NAVIGATION_TAG_V1.finditer(str(model_output)))
    if len(matches) != 1:
        raise ValueError("navigation model output must contain exactly one tagged object")
    try:
        payload = json.loads(matches[0].group("payload"))
    except json.JSONDecodeError as error:
        raise ValueError("navigation model output is not valid JSON") from error
    if not isinstance(payload, dict) or set(payload) != {"decision", "bid"}:
        raise ValueError("navigation model output schema changed")
    decision = payload["decision"]
    bid = payload["bid"]
    if decision == "abstain" and bid is None:
        return PublicNavigationDecisionV1("abstain", None, "base navigator abstained")
    if decision != "click" or not isinstance(bid, str):
        raise ValueError("navigation model decision is invalid")
    matches_by_bid = [row for row in inventory.candidates if row.bid == bid]
    if len(matches_by_bid) != 1:
        raise ValueError("navigation model selected a bid outside the current inventory")
    return PublicNavigationDecisionV1(
        "click",
        matches_by_bid[0],
        "one current public navigation bid was selected",
    )


@dataclass(frozen=True)
class PublicNavigationEffectV1:
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


def check_public_navigation_effect_v1(
    *,
    before: SemanticSnapshot,
    after: SemanticSnapshot,
    before_url: str,
    after_url: str,
    candidate: PublicNavigationCandidateV1,
) -> PublicNavigationEffectV1:
    key = navigation_attempt_key_v1(
        snapshot=before,
        current_url=before_url,
        bid=candidate.bid,
    )
    url_changed = _normalized_url(before_url) != _normalized_url(after_url)
    semantic_changed = before.semantic_fingerprint() != after.semantic_fingerprint()
    effective = url_changed or semantic_changed
    return PublicNavigationEffectV1(
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
