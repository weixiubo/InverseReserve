from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from inversereserve.controllers.pact_controller_v4 import ActionExecutionV4
from inversereserve.controllers.pact_controller_v11 import FailClosedTransactionRuntimeV11
from inversereserve.controllers.pact_controller_v12 import (
    FailClosedTransactionRuntimeV12,
    complete_public_fingerprint_v12,
)
from inversereserve.observations.typed_observation import SemanticSnapshot

from .test_pact_v11_no_effect_inverse_guard import (
    ScriptedExecutor,
    calendar,
    calendar_contract,
    editable_contract,
    forbidden_reservation,
    login,
)

ROOT = Path(__file__).resolve().parents[1]


def replace_element(snapshot: SemanticSnapshot, bid: str, **changes) -> SemanticSnapshot:
    rows = list(snapshot.elements)
    index = next((index for index, element in enumerate(rows) if element.bid == bid))
    rows[index] = replace(rows[index], **changes)
    return SemanticSnapshot(tuple(rows))


def class_only_change(snapshot: SemanticSnapshot) -> SemanticSnapshot:
    element = snapshot.get("user")
    assert element is not None
    attributes = dict(element.dom_attributes)
    attributes["class"] = "validation-error"
    return replace_element(snapshot, "user", dom_attributes=tuple(sorted(attributes.items())))


def test_v12_fingerprint_includes_every_retained_public_field() -> None:
    before = login()
    target = before.get("user")
    assert target is not None and target.bbox is not None
    variants = (
        class_only_change(before),
        replace_element(
            before, "user", ax_properties=tuple(sorted((*target.ax_properties, ("autocomplete", "list"))))
        ),
        replace_element(
            before,
            "user",
            dom_attributes=tuple(sorted((*target.dom_attributes, ("placeholder", "Username")))),
        ),
        replace_element(before, "user", bbox=(1.0, 0.0, 10.0, 10.0)),
    )
    for after in variants:
        assert before != after
        assert complete_public_fingerprint_v12(before) != complete_public_fingerprint_v12(after)


def test_v12_closes_the_v11_class_only_false_no_effect_certificate() -> None:
    before = login()
    after = class_only_change(before)
    assert before.semantic_fingerprint() == after.semantic_fingerprint()
    assert complete_public_fingerprint_v12(before) != complete_public_fingerprint_v12(after)
    v11_executor = ScriptedExecutor(
        [("typed_forward", "fill('user', 'michel', False)", ActionExecutionV4(after))]
    )
    v11 = FailClosedTransactionRuntimeV11(v11_executor, forbidden_reservation)
    v11_outcome = v11.transact(before=before, contract=editable_contract(before), candidate_label="Username")
    assert v11_outcome.restoration is not None
    assert not v11_outcome.restoration.attempted
    v12_executor = ScriptedExecutor(
        [
            ("typed_forward", "fill('user', 'michel', False)", ActionExecutionV4(after)),
            ("typed_inverse", "fill('user', '', False)", ActionExecutionV4(before)),
        ]
    )
    v12 = FailClosedTransactionRuntimeV12(v12_executor, forbidden_reservation)
    v12_outcome = v12.transact(before=before, contract=editable_contract(before), candidate_label="Username")
    assert not v12_outcome.admitted and (not v12_outcome.halted)
    assert v12_outcome.restoration is not None
    assert v12_outcome.restoration.attempted
    assert v12_outcome.restoration.passed
    assert [row["role"] for row in v12_executor.actions] == ["typed_forward", "typed_inverse"]
    check = next((event for event in v12.events if event["type"] == "complete_public_observation_check_v12"))
    assert check["passed"] is False


def test_v12_still_skips_inverse_after_a_truly_identical_snapshot() -> None:
    before = calendar("December", "0")
    executor = ScriptedExecutor([("typed_forward", "click('prev0')", ActionExecutionV4(before))])
    runtime = FailClosedTransactionRuntimeV12(executor, forbidden_reservation)
    outcome = runtime.transact(before=before, contract=calendar_contract(before), candidate_label="Prev")
    assert not outcome.admitted and (not outcome.halted)
    assert outcome.restoration is not None
    assert not outcome.restoration.attempted and outcome.restoration.passed
    assert [row["role"] for row in executor.actions] == ["typed_forward"]
    certificate = next(
        (event for event in runtime.events if event["type"] == "complete_public_no_effect_certificate_v12")
    )
    assert certificate["passed"] is True
    assert certificate["inverse_skipped"] is True


def test_v12_fails_closed_on_an_ambiguous_complete_public_snapshot() -> None:
    before = login()
    duplicate = SemanticSnapshot(before.elements + (before.elements[0],))
    executor = ScriptedExecutor(
        [("typed_forward", "fill('user', 'michel', False)", ActionExecutionV4(duplicate))]
    )
    runtime = FailClosedTransactionRuntimeV12(executor, forbidden_reservation)
    outcome = runtime.transact(before=before, contract=editable_contract(before), candidate_label="Username")
    assert not outcome.admitted and outcome.halted
    assert outcome.restoration is not None
    assert not outcome.restoration.attempted
    assert not outcome.restoration.passed
    assert [row["role"] for row in executor.actions] == ["typed_forward"]
    assert any(
        (
            event.get("type") == "verification_exception"
            and event.get("context") == "v12 complete-public no-effect certificate"
            for event in runtime.events
        )
    )
