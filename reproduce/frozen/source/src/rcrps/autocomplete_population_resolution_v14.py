"""Public, bounded autocomplete-population resolution for PACT-v14.

The repair is intentionally narrower than generic keyboard exploration.  It
applies only to one unresolved top-of-stack autocomplete transaction whose
goal-bound value occurs in exactly one retained public menu item.  ArrowDown
is used only as a reversible probe; Enter is certified only after a fresh
public selected-state marker identifies that exact item.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable

from .pact_controller_v12 import complete_public_fingerprint_v12
from .pact_grounding_v4 import (
    CommitCertificateV4,
    GroundingDecisionV4,
    stack_signature_v4,
)
from .pact_grounding_v8 import (
    commit_attempt_key_v8,
    unresolved_blocking_transactions_v8,
)
from .structured_planner_v4 import ActionCandidateV4
from .transaction_actions_v4 import ContractActionV4
from .typed_observation import SemanticElement, SemanticSnapshot


MAX_PUBLIC_AUTOCOMPLETE_ITEMS_V14 = 32
SELECTION_CLASS_TOKENS_V14 = frozenset(
    {"ui-state-active", "ui-state-focus"}
)


def _normalize(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _token_match(observed: object, expected: object) -> bool:
    observed_text = _normalize(observed).casefold()
    expected_text = _normalize(expected).casefold()
    if not observed_text or not expected_text:
        return False
    if observed_text == expected_text:
        return True
    return (
        re.search(
            rf"(?<![\w]){re.escape(expected_text)}(?![\w])",
            observed_text,
        )
        is not None
    )


def _truthy(value: object) -> bool:
    return value is True or str(value or "").strip().casefold() == "true"


def _contract(record: Any) -> Any:
    return record.get("contract") if isinstance(record, dict) else record.contract


def _structural_surface(element: SemanticElement) -> bool:
    return element.role.casefold() in {"listbox", "menu", "list"} or (
        "ui-autocomplete" in element.class_tokens
        and "ui-autocomplete-input" not in element.class_tokens
    )


def _item_like(element: SemanticElement) -> bool:
    return bool(
        element.role.casefold() in {"option", "menuitem", "listitem"}
        or element.dom_tag.casefold() == "li"
        or "ui-menu-item" in element.class_tokens
        or "ui-menu-item-wrapper" in element.class_tokens
    )


def _public_text(element: SemanticElement) -> str:
    values = []
    for value in (element.name, element.subtree_text):
        normalized = _normalize(value)
        if normalized and normalized not in values:
            values.append(normalized)
    return " ".join(values)


def _public_field_values(
    snapshot: SemanticSnapshot,
    field_bid: str,
) -> tuple[str, ...]:
    field = snapshot.get(field_bid)
    if field is None:
        return ()
    values = []
    for value in (
        field.ax_property("value"),
        field.dom_attribute("value", ""),
    ):
        normalized = _normalize(value)
        if normalized and normalized not in values:
            values.append(normalized)
    return tuple(values)


def _top_level_items(
    snapshot: SemanticSnapshot,
    surface: SemanticElement,
) -> tuple[SemanticElement, ...]:
    """Return one public identity per suggestion, including offscreen rows."""

    for relation in ("dom", "ax"):
        descendants = snapshot.descendants(surface.bid, relation=relation)
        item_bids = {row.bid for row in descendants if _item_like(row)}
        roots = []
        for row in descendants:
            if row.bid not in item_bids or not _public_text(row):
                continue
            nested = any(
                ancestor.bid in item_bids
                for ancestor in snapshot.ancestors(row.bid, relation=relation)
                if ancestor.bid != surface.bid
            )
            if not nested:
                roots.append(row)
        if roots:
            # SemanticSnapshot intentionally canonicalizes elements by BID and
            # does not retain a DOM sibling index.  The method never infers an
            # Enter action from this order; it scans fresh selection markers.
            return tuple(sorted(roots, key=lambda row: row.bid))
    return ()


def _selected_evidence(
    snapshot: SemanticSnapshot,
    *,
    field: SemanticElement,
    surface: SemanticElement,
    item: SemanticElement,
) -> tuple[str, ...]:
    rows = (item,) + snapshot.descendants(item.bid, relation="dom")
    evidence = []
    if any(_truthy(row.ax_property("selected")) for row in rows):
        evidence.append("ax_selected")
    if any(_truthy(row.dom_attribute("aria-selected")) for row in rows):
        evidence.append("aria_selected")
    if any(SELECTION_CLASS_TOKENS_V14 & row.class_tokens for row in rows):
        evidence.append("jquery_active_class")

    active_ids = {
        _normalize(field.dom_attribute("aria-activedescendant", "")),
        _normalize(surface.dom_attribute("aria-activedescendant", "")),
    }
    active_ids.discard("")
    item_ids = {
        _normalize(row.dom_attribute("id", "")) for row in rows
    }
    item_ids.discard("")
    if active_ids & item_ids:
        evidence.append("aria_activedescendant")
    return tuple(evidence)


@dataclass(frozen=True)
class PublicAutocompleteItemV14:
    bid: str
    label: str
    canonical_index: int
    selected_evidence: tuple[str, ...] = ()

    @property
    def selected(self) -> bool:
        return bool(self.selected_evidence)

    def signature(self) -> tuple[object, ...]:
        return (self.canonical_index, self.bid, self.label)


@dataclass(frozen=True)
class AutocompletePopulationInspectionV14:
    eligible: bool
    reason: str
    field_bid: str | None = None
    surface_bid: str | None = None
    expected_value: str | None = None
    items: tuple[PublicAutocompleteItemV14, ...] = ()
    target_bid: str | None = None
    selected_bids: tuple[str, ...] = ()

    @property
    def selected_bid(self) -> str | None:
        return self.selected_bids[0] if len(self.selected_bids) == 1 else None

    @property
    def target_item(self) -> PublicAutocompleteItemV14 | None:
        return next(
            (row for row in self.items if row.bid == self.target_bid),
            None,
        )

    @property
    def population_signature(self) -> tuple[tuple[object, ...], ...]:
        return tuple(row.signature() for row in self.items)

    def record(self) -> dict[str, object]:
        return {
            "eligible": self.eligible,
            "reason": self.reason,
            "field_bid": self.field_bid,
            "surface_bid": self.surface_bid,
            "expected_value": self.expected_value,
            "item_count": len(self.items),
            "items": [
                {
                    "bid": row.bid,
                    "label": row.label,
                    "canonical_index": row.canonical_index,
                    "selected_evidence": list(row.selected_evidence),
                }
                for row in self.items
            ],
            "target_bid": self.target_bid,
            "selected_bids": list(self.selected_bids),
        }


def _rejected(reason: str) -> AutocompletePopulationInspectionV14:
    return AutocompletePopulationInspectionV14(False, reason)


def inspect_autocomplete_population_v14(
    *,
    current: SemanticSnapshot,
    goal: Any,
    active_transactions: Iterable[Any],
    resolved_semantic_bids: Iterable[str] = (),
) -> AutocompletePopulationInspectionV14:
    """Inspect one public menu without deriving authority from option order."""

    active = tuple(active_transactions)
    blockers = unresolved_blocking_transactions_v8(
        active,
        tuple(resolved_semantic_bids),
    )
    if len(blockers) != 1:
        return _rejected("resolution requires exactly one unresolved typed blocker")
    blocker = blockers[0]
    contract = _contract(blocker)
    if contract.kind != "autocomplete_query":
        return _rejected("the unresolved blocker is not an autocomplete transaction")
    if not active or _contract(active[-1]) != contract:
        return _rejected("autocomplete resolution requires the unresolved stack top")

    field_bid = str(contract.semantic_bid)
    expected = _normalize(contract.expected_value)
    if not expected:
        return _rejected("autocomplete transaction has no expected public value")
    assignments = tuple(
        row
        for row in goal.field_assignments
        if str(row.bid) == field_bid
        and _normalize(row.value).casefold() == expected.casefold()
    )
    if len(assignments) != 1:
        return _rejected("expected value is not one unique goal-bound field assignment")
    field = current.get(field_bid)
    if field is None or not current.is_effectively_visible(field_bid):
        return _rejected("goal-bound autocomplete field is not freshly visible")

    surfaces = tuple(
        row
        for row in current.elements
        if _structural_surface(row) and current.is_effectively_visible(row.bid)
    )
    if len(surfaces) != 1:
        return _rejected("public autocomplete surface is absent or ambiguous")
    surface = surfaces[0]
    if not _token_match(_public_text(surface), expected):
        return _rejected("visible suggestion owner does not contain the goal token")

    roots = _top_level_items(current, surface)
    if not roots:
        return _rejected("suggestion owner exposes no ordered public item identities")
    if len(roots) > MAX_PUBLIC_AUTOCOMPLETE_ITEMS_V14:
        return _rejected("public suggestion population exceeds the frozen probe bound")

    items = tuple(
        PublicAutocompleteItemV14(
            bid=row.bid,
            label=_public_text(row),
            canonical_index=index,
            selected_evidence=_selected_evidence(
                current,
                field=field,
                surface=surface,
                item=row,
            ),
        )
        for index, row in enumerate(roots)
    )
    targets = tuple(row for row in items if _token_match(row.label, expected))
    if len(targets) != 1:
        return _rejected("goal token is absent or ambiguous in public item identities")
    selected = tuple(row.bid for row in items if row.selected)
    if len(selected) > 1:
        return _rejected("public autocomplete selection marker is ambiguous")

    values = _public_field_values(current, field_bid)
    selected_item = next(
        (row for row in items if row.bid == (selected[0] if selected else None)),
        None,
    )
    allowed_values = (expected,) + (
        (selected_item.label,) if selected_item is not None else ()
    )
    field_is_consistent = bool(values) and all(
        any(_token_match(value, allowed) for allowed in allowed_values)
        for value in values
    )
    if not field_is_consistent:
        return _rejected("public field value is inconsistent with query and selection")

    return AutocompletePopulationInspectionV14(
        True,
        "one goal-bound public autocomplete population is eligible",
        field_bid,
        surface.bid,
        expected,
        items,
        targets[0].bid,
        selected,
    )


@dataclass(frozen=True)
class PopulationNavigationCertificateV14:
    allowed: bool
    reason: str
    certified_action: ContractActionV4 | None = None
    field_bid: str | None = None
    surface_bid: str | None = None
    target_bid: str | None = None
    population_signature: tuple[tuple[object, ...], ...] = ()
    observation_fingerprint: tuple[tuple[object, ...], ...] = ()
    active_stack_signature: tuple[tuple[object, ...], ...] = ()


def certify_population_probe_v14(
    *,
    current: SemanticSnapshot,
    inspection: AutocompletePopulationInspectionV14,
    active_transactions: Iterable[Any],
) -> PopulationNavigationCertificateV14:
    if not inspection.eligible or inspection.field_bid is None:
        return PopulationNavigationCertificateV14(False, inspection.reason)
    if inspection.selected_bid == inspection.target_bid:
        return PopulationNavigationCertificateV14(
            False,
            "target is already freshly selected; another probe is forbidden",
        )
    try:
        fingerprint = complete_public_fingerprint_v12(current)
        stack = stack_signature_v4(tuple(active_transactions))
        action = ContractActionV4("press", inspection.field_bid, "ArrowDown")
    except Exception as error:
        return PopulationNavigationCertificateV14(
            False,
            f"population probe certificate failed: {type(error).__name__}: {error}",
        )
    return PopulationNavigationCertificateV14(
        True,
        "fresh complete-public population state certifies one bounded ArrowDown probe",
        action,
        inspection.field_bid,
        inspection.surface_bid,
        inspection.target_bid,
        inspection.population_signature,
        fingerprint,
        stack,
    )


def population_resolution_candidate_v14(
    inspection: AutocompletePopulationInspectionV14,
) -> ActionCandidateV4:
    if not inspection.eligible or inspection.field_bid is None:
        raise ValueError("population resolution candidate requires an eligible inspection")
    target = inspection.target_item
    if target is None or inspection.surface_bid is None:
        raise ValueError("eligible population inspection lost its target identity")
    return ActionCandidateV4(
        bid=inspection.field_bid,
        action=ContractActionV4("press", inspection.field_bid, "Enter"),
        role="combobox",
        label=target.label,
        state=(
            ("population_surface_bid", inspection.surface_bid),
            ("population_target_bid", target.bid),
            ("population_target_canonical_index", target.canonical_index),
        ),
        transaction_kind=None,
        semantic_bid=inspection.field_bid,
        parent_bid=inspection.surface_bid,
    )


def certify_population_commit_v14(
    *,
    current: SemanticSnapshot,
    inspection: AutocompletePopulationInspectionV14,
    active_transactions: Iterable[Any],
    quarantined_commit_keys: frozenset[tuple[object, ...]] = frozenset(),
) -> tuple[ActionCandidateV4 | None, CommitCertificateV4]:
    grounding = GroundingDecisionV4(
        False,
        inspection.reason,
        "active_autocomplete_population_selection_v14",
    )
    if (
        not inspection.eligible
        or inspection.selected_bid is None
        or inspection.selected_bid != inspection.target_bid
    ):
        return None, CommitCertificateV4(False, grounding.reason, grounding)

    candidate = population_resolution_candidate_v14(inspection)
    active = tuple(active_transactions)
    try:
        key = commit_attempt_key_v8(
            current=current,
            action=candidate.action,
            active_transactions=active,
        )
        fingerprint = complete_public_fingerprint_v12(current)
        stack = stack_signature_v4(active)
    except Exception as error:
        reason = f"population commit certificate failed: {type(error).__name__}"
        rejected = GroundingDecisionV4(
            False,
            reason,
            "active_autocomplete_population_selection_v14",
        )
        return None, CommitCertificateV4(False, reason, rejected)
    if key in quarantined_commit_keys:
        reason = "the same population Enter commit already had zero public effect"
        rejected = GroundingDecisionV4(
            False,
            reason,
            "no_effect_quarantine",
            (inspection.field_bid or "", inspection.target_bid or ""),
        )
        return None, CommitCertificateV4(False, reason, rejected)

    grounding = GroundingDecisionV4(
        True,
        "one fresh public selected-state marker identifies the unique goal-bound population item",
        "active_autocomplete_population_selection_v14",
        tuple(
            row
            for row in (
                inspection.field_bid,
                inspection.surface_bid,
                inspection.target_bid,
            )
            if row is not None
        ),
        (inspection.target_bid or "",),
        inspection.field_bid,
    )
    return candidate, CommitCertificateV4(
        True,
        grounding.reason,
        grounding,
        candidate.action,
        fingerprint,
        stack,
    )


@dataclass(frozen=True)
class PopulationResolutionEffectV14:
    passed: bool
    reason: str
    evidence_bids: tuple[str, ...] = ()


def verify_population_resolution_effect_v14(
    *,
    after: SemanticSnapshot,
    inspection: AutocompletePopulationInspectionV14,
) -> PopulationResolutionEffectV14:
    if (
        not inspection.eligible
        or inspection.field_bid is None
        or inspection.expected_value is None
    ):
        return PopulationResolutionEffectV14(
            False,
            "population resolution effect lacks an eligible predecessor",
        )
    values = _public_field_values(after, inspection.field_bid)
    if not any(_token_match(value, inspection.expected_value) for value in values):
        return PopulationResolutionEffectV14(
            False,
            "post-Enter public field value does not contain the goal token",
            (inspection.field_bid,),
        )
    open_surfaces = tuple(
        row.bid
        for row in after.elements
        if _structural_surface(row)
        and after.is_effectively_visible(row.bid)
        and _token_match(_public_text(row), inspection.expected_value)
    )
    if open_surfaces:
        return PopulationResolutionEffectV14(
            False,
            "post-Enter goal-bearing autocomplete surface remained visible",
            (inspection.field_bid,) + open_surfaces,
        )
    return PopulationResolutionEffectV14(
        True,
        "post-Enter public field contains the goal token and the suggestion surface closed",
        tuple(
            row
            for row in (inspection.field_bid, inspection.target_bid)
            if row is not None
        ),
    )


__all__ = [
    "AutocompletePopulationInspectionV14",
    "MAX_PUBLIC_AUTOCOMPLETE_ITEMS_V14",
    "PopulationNavigationCertificateV14",
    "PopulationResolutionEffectV14",
    "PublicAutocompleteItemV14",
    "certify_population_commit_v14",
    "certify_population_probe_v14",
    "inspect_autocomplete_population_v14",
    "population_resolution_candidate_v14",
    "verify_population_resolution_effect_v14",
]
