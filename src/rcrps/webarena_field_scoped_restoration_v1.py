"""Field-scoped restoration checks for WebArena editable assignments.

The frozen V4 contract library projects every visible form control for an
``editable_field_assignment``.  That footprint is broader than the declared
contract: an assignment owns one typed field's value and public status, not
unrelated controls that an asynchronous page update may add.  This module
keeps the global semantic delta for audit while certifying only the declared
field footprint.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from .pact_controller_v13 import FailClosedTransactionRuntimeV13
from .typed_contracts_v4 import TransactionContractV4
from .typed_observation import (
    ContractCheck,
    SemanticSnapshot,
    semantic_delta,
)


FIELD_RESTORATION_PROJECTION_V1 = "editable-field-value-status-v1"


def _normalized(value: Any) -> str:
    return " ".join(str(value or "").split()).casefold()


def _public_value(snapshot: SemanticSnapshot, bid: str) -> str:
    element = snapshot.get(bid)
    if element is None:
        return ""
    value = element.ax_property("value")
    if value is None:
        value = element.dom_attribute("value", "")
    return "" if value is None else str(value)


def _public_boolean(
    snapshot: SemanticSnapshot,
    bid: str,
    name: str,
) -> bool:
    element = snapshot.get(bid)
    if element is None:
        return False
    value = element.ax_property(name)
    if value is None:
        value = element.dom_attribute(name)
    if value is None:
        value = element.dom_attribute(f"aria-{name}")
    return value is True or _normalized(value) == "true"


def editable_field_projection_v1(
    snapshot: SemanticSnapshot,
    bid: str,
) -> tuple[object, ...]:
    """Return the typed value-and-status footprint owned by one field."""

    element = snapshot.get(bid)
    if element is None:
        return ("absent", bid)
    return (
        "field",
        element.role.casefold(),
        element.dom_tag.casefold(),
        _public_value(snapshot, bid),
        _public_boolean(snapshot, bid, "readonly"),
        _public_boolean(snapshot, bid, "disabled"),
        snapshot.is_effectively_visible(bid),
    )


def check_editable_field_restoration_v1(
    before: SemanticSnapshot,
    restored: SemanticSnapshot,
    contract: TransactionContractV4,
) -> ContractCheck:
    """Check exactly the declared editable-field restoration projection."""

    if (
        contract.kind != "editable_field_assignment"
        or contract.projection_kind != "editable_field_assignment"
    ):
        raise ValueError(
            "field-scoped restoration requires an editable assignment contract"
        )
    delta = semantic_delta(before, restored)
    passed = editable_field_projection_v1(
        before,
        contract.semantic_bid,
    ) == editable_field_projection_v1(
        restored,
        contract.semantic_bid,
    )
    return ContractCheck(
        passed,
        (
            "typed field value and status restored"
            if passed
            else "typed field value or status differs"
        ),
        delta,
    )


class FailClosedWebArenaFieldRuntimeV1(FailClosedTransactionRuntimeV13):
    """Use field-scoped restoration only for editable assignments."""

    def _check_restoration(
        self,
        before: SemanticSnapshot,
        restored: SemanticSnapshot,
        contract: TransactionContractV4,
        *,
        trigger: str,
    ) -> ContractCheck | None:
        if (
            contract.kind != "editable_field_assignment"
            or contract.projection_kind != "editable_field_assignment"
        ):
            return super()._check_restoration(
                before,
                restored,
                contract,
                trigger=trigger,
            )
        try:
            check = check_editable_field_restoration_v1(
                before,
                restored,
                contract,
            )
        except Exception as error:
            self._audit(
                {
                    "type": "verification_exception",
                    "context": trigger,
                    "reason": f"{type(error).__name__}: {error}",
                }
            )
            self._halt(f"{trigger} verifier raised an exception")
            return None
        self._audit(
            {
                "type": "restoration",
                "trigger": trigger,
                "projection_kind": FIELD_RESTORATION_PROJECTION_V1,
                "declared_contract_projection": contract.projection_kind,
                "semantic_bid": contract.semantic_bid,
                "passed": check.passed,
                "reason": check.reason,
                "global_delta": asdict(check.delta),
                "global_delta_empty": not check.delta.changed,
            }
        )
        return check


__all__ = [
    "FIELD_RESTORATION_PROJECTION_V1",
    "FailClosedWebArenaFieldRuntimeV1",
    "check_editable_field_restoration_v1",
    "editable_field_projection_v1",
]
