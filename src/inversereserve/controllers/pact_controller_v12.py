"""PACT-v12 runtime with an actually complete public no-effect guard."""

from __future__ import annotations

from typing import Any

from inversereserve.controllers.pact_controller_v4 import ActiveTransactionV4, RestorationOutcomeV4
from inversereserve.controllers.pact_controller_v11 import FailClosedTransactionRuntimeV11
from inversereserve.observations.typed_observation import SemanticElement, SemanticSnapshot

COMPLETE_PUBLIC_FINGERPRINT_VERSION_V12 = "all-semantic-snapshot-fields-v12"


def _complete_element_record_v12(element: SemanticElement) -> tuple[Any, ...]:
    """Return every public field retained in one semantic element.

    ``SemanticElement.semantic_signature`` intentionally filters AX and DOM
    metadata.  That projection is useful for ordinary semantic deltas, but it
    is too weak to certify that a rejected action had no public effect: the
    controller itself consumes omitted fields such as DOM ``class`` tokens.
    This record therefore includes every field stored by ``SemanticElement``.
    """

    return (
        element.bid,
        element.role,
        element.name,
        element.subtree_text,
        tuple(sorted(element.ax_properties, key=lambda item: item[0])),
        element.ax_parent_bid,
        element.dom_tag,
        tuple(sorted(element.dom_attributes, key=lambda item: item[0])),
        element.dom_parent_bid,
        element.visible,
        element.clickable,
        element.bbox,
    )


def complete_public_fingerprint_v12(
    snapshot: SemanticSnapshot,
) -> tuple[tuple[Any, ...], ...]:
    """Canonicalize the complete retained public observation.

    BrowserGym observations have unique BIDs and deterministic element order.
    Sorting by BID makes the certificate insensitive only to container order;
    duplicate BIDs are rejected because they make public identity ambiguous.
    No retained AX, DOM, visibility, clickability, ancestry, or geometry field
    is projected away.
    """

    if not isinstance(snapshot, SemanticSnapshot):
        raise TypeError("complete-public fingerprint requires a semantic snapshot")
    if any(not isinstance(element, SemanticElement) for element in snapshot.elements):
        raise TypeError("semantic snapshot contains a non-semantic element")
    bids = [element.bid for element in snapshot.elements]
    if any(not isinstance(bid, str) or not bid for bid in bids):
        raise ValueError("complete-public fingerprint requires nonempty string BIDs")
    if len(set(bids)) != len(bids):
        raise ValueError("complete-public fingerprint requires unique BIDs")
    return tuple(
        _complete_element_record_v12(element)
        for element in sorted(snapshot.elements, key=lambda item: item.bid)
    )


class FailClosedTransactionRuntimeV12(FailClosedTransactionRuntimeV11):
    """Use full retained-observation equality before skipping an inverse.

    V11 correctly restored the no-effect branch but reused the projected
    semantic fingerprint.  Because contract compilation and inverse grounding
    also consume public fields omitted from that projection (notably DOM class
    tokens), a class-only mutation could be mislabeled as no effect.  V12 keeps
    every other v10/v11 branch unchanged and strengthens only this certificate.
    """

    def _unchanged_public_restoration(
        self,
        transaction: ActiveTransactionV4,
        *,
        trigger: str,
        remove_active: bool,
    ) -> RestorationOutcomeV4 | None:
        try:
            unchanged = complete_public_fingerprint_v12(
                transaction.before
            ) == complete_public_fingerprint_v12(transaction.after)
        except Exception as error:
            reason = (
                f"complete-public observation verifier raised an exception: {type(error).__name__}: {error}"
            )
            self._audit(
                {
                    "type": "verification_exception",
                    "context": "v12 complete-public no-effect certificate",
                    "reason": reason,
                    "fingerprint_version": (COMPLETE_PUBLIC_FINGERPRINT_VERSION_V12),
                }
            )
            self._halt(reason)
            return RestorationOutcomeV4(
                False,
                False,
                reason,
                None,
                transaction.after,
            )

        self._audit(
            {
                "type": "complete_public_observation_check_v12",
                "trigger": trigger,
                "passed": unchanged,
                "fingerprint_version": COMPLETE_PUBLIC_FINGERPRINT_VERSION_V12,
                "field_scope": "all_retained_semantic_snapshot_fields",
            }
        )
        if not unchanged:
            return None

        outcome = super()._unchanged_public_restoration(
            transaction,
            trigger=trigger,
            remove_active=remove_active,
        )
        if outcome is not None and outcome.passed and not outcome.attempted:
            self._audit(
                {
                    "type": "complete_public_no_effect_certificate_v12",
                    "trigger": trigger,
                    "passed": True,
                    "inverse_skipped": True,
                    "fingerprint_version": (COMPLETE_PUBLIC_FINGERPRINT_VERSION_V12),
                }
            )
        return outcome
