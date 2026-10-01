from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

from rcrps.confirmation_agents_v19 import (  # noqa: E402
    FullPactConfirmationDriverV19,
    certified_scope_consumption_metrics_v19,
)
from rcrps.pact_controller_v4 import ActiveTransactionV4  # noqa: E402
from rcrps.pact_controller_v19 import FailClosedTransactionRuntimeV19  # noqa: E402
from rcrps.pact_grounding_v19 import resolved_by_commit_v19  # noqa: E402
from rcrps.transaction_actions_v4 import ContractActionV4  # noqa: E402
from rcrps.typed_contracts_v4 import TransactionContractV4  # noqa: E402
from rcrps.typed_observation import semantic_delta  # noqa: E402
from test_pact_controller_v15 import (  # noqa: E402
    _RerenderingCalendarExecutor,
    _calendar,
)


def runtime() -> FailClosedTransactionRuntimeV19:
    return FailClosedTransactionRuntimeV19(
        _RerenderingCalendarExecutor(),
        lambda _contract: None,
        lambda _contract: None,
    )


def transaction(kind: str, semantic_bid: str) -> ActiveTransactionV4:
    before = _calendar("December", suffix="0")
    after = _calendar("November", suffix="1")
    if kind in {"autocomplete_query", "editable_field_assignment"}:
        contract = TransactionContractV4(
            kind=kind,
            semantic_bid=semantic_bid,
            action=ContractActionV4("fill", semantic_bid, "new"),
            inverse_actions=(ContractActionV4("fill", semantic_bid, "old"),),
            expected_value="new",
            prior_value="old",
            projection_kind=kind,
        )
    elif kind == "native_select_update":
        contract = TransactionContractV4(
            kind=kind,
            semantic_bid=semantic_bid,
            action=ContractActionV4("select_option", semantic_bid, ("new",)),
            inverse_actions=(
                ContractActionV4("select_option", semantic_bid, ("old",)),
            ),
            expected_options=("new",),
            prior_options=("old",),
            projection_kind=kind,
        )
    else:
        contract = TransactionContractV4(
            kind=kind,
            semantic_bid=semantic_bid,
            action=ContractActionV4("click", semantic_bid),
            inverse_actions=(ContractActionV4("click", semantic_bid),),
            projection_kind="global",
        )
    return ActiveTransactionV4(
        contract,
        kind,
        before,
        after,
        semantic_delta(before, after),
    )


def certificate(*, anchor: str, evidence: tuple[str, ...], allowed: bool = True):
    return SimpleNamespace(
        allowed=allowed,
        grounding=SimpleNamespace(anchor_kind=anchor, evidence_bids=evidence),
    )


def test_v19_grounding_adds_only_goal_evidenced_mutations() -> None:
    active = (
        transaction("editable_field_assignment", "user"),
        transaction("native_select_update", "country"),
        transaction("arbitrary_crossing_scope", "other"),
    )
    value = resolved_by_commit_v19(
        current=active[0].after,
        candidate=SimpleNamespace(bid="submit", semantic_bid="submit"),
        active_transactions=active,
        certificate=certificate(
            anchor="state_supported_form_action",
            evidence=("user", "country", "other"),
        ),
        terminal=True,
    )
    assert value == ("country", "user")


def test_v19_effective_form_commit_consumes_exact_goal_mutation_suffix() -> None:
    value = runtime()
    value.active = [
        transaction("editable_field_assignment", "user"),
        transaction("editable_field_assignment", "password"),
    ]
    consumed = value.consume_resolved_commit_scope_v19(
        ("user", "password"),
        commit_bid="submit",
        anchor_kind="state_supported_form_action",
        evidence_bids=("user", "password"),
    )
    assert len(consumed) == 2
    assert value.active == []
    assert value.halted is False
    assert all(row["committed"] is True for row in value.completed)


def test_v19_rejects_nonblocking_discharge_without_goal_state_anchor() -> None:
    value = runtime()
    original = transaction("editable_field_assignment", "user")
    value.active = [original]
    consumed = value.consume_resolved_commit_scope_v19(
        ("user",),
        commit_bid="submit",
        anchor_kind="exact_target",
        evidence_bids=("user",),
    )
    assert consumed == ()
    assert value.active == [original]
    assert value.halted is True


def test_v19_rejects_missing_goal_evidence_without_stack_mutation() -> None:
    value = runtime()
    original = transaction("native_select_update", "country")
    value.active = [original]
    consumed = value.consume_resolved_commit_scope_v19(
        ("country",),
        commit_bid="submit",
        anchor_kind="state_supported_form_action",
        evidence_bids=("other",),
    )
    assert consumed == ()
    assert value.active == [original]
    assert value.halted is True


def test_v19_rejects_noncontiguous_goal_scope_without_stack_mutation() -> None:
    value = runtime()
    first = transaction("editable_field_assignment", "user")
    second = transaction("native_select_update", "country")
    value.active = [first, second]
    consumed = value.consume_resolved_commit_scope_v19(
        ("user",),
        commit_bid="submit",
        anchor_kind="state_supported_form_action",
        evidence_bids=("user",),
    )
    assert consumed == ()
    assert value.active == [first, second]
    assert value.halted is True


def test_v19_driver_consumes_through_existing_audit_boundary() -> None:
    driver = object.__new__(FullPactConfirmationDriverV19)
    driver.runtime = runtime()
    driver.runtime.active = [transaction("editable_field_assignment", "user")]
    driver.trace = []
    driver.resolved_semantic_bids = set()
    driver._pending_commit_scope_v19 = None
    driver.audit(
        {
            "type": "certified_commit_result_v8",
            "bid": "submit",
            "executed": True,
            "halted": False,
            "terminal": True,
            "certificate": {
                "grounding": {
                    "anchor_kind": "state_supported_form_action",
                    "evidence_bids": ["user"],
                }
            },
        }
    )
    driver.audit({"type": "commit_effect_result_v8", "effective": True})
    assert driver.runtime.active == []
    assert driver.resolved_semantic_bids == {"user"}
    assert certified_scope_consumption_metrics_v19(driver) == {
        "certified_scope_consumption_checks_v19": 1,
        "certified_scope_consumption_passes_v19": 1,
        "certified_scope_consumption_failures_v19": 0,
        "certified_scope_consumed_transactions_v19": 1,
        "goal_mutation_consumption_passes_v19": 1,
    }


def test_v19_driver_retains_goal_mutation_for_nonterminal_effect() -> None:
    driver = object.__new__(FullPactConfirmationDriverV19)
    original = transaction("editable_field_assignment", "user")
    driver.runtime = runtime()
    driver.runtime.active = [original]
    driver.trace = []
    driver.resolved_semantic_bids = set()
    driver._pending_commit_scope_v19 = None
    driver.audit(
        {
            "type": "certified_commit_result_v8",
            "bid": "submit",
            "executed": True,
            "halted": False,
            "terminal": False,
            "certificate": {
                "grounding": {
                    "anchor_kind": "state_supported_form_action",
                    "evidence_bids": ["user"],
                }
            },
        }
    )
    driver.audit({"type": "commit_effect_result_v8", "effective": True})
    assert driver.runtime.active == [original]
    assert driver.resolved_semantic_bids == set()
    assert certified_scope_consumption_metrics_v19(driver)[
        "certified_scope_consumption_checks_v19"
    ] == 0


def test_v19_driver_retains_goal_mutation_when_commit_has_no_effect() -> None:
    driver = object.__new__(FullPactConfirmationDriverV19)
    original = transaction("editable_field_assignment", "user")
    driver.runtime = runtime()
    driver.runtime.active = [original]
    driver.trace = []
    driver.resolved_semantic_bids = set()
    driver._pending_commit_scope_v19 = None
    driver.audit(
        {
            "type": "certified_commit_result_v8",
            "bid": "submit",
            "executed": True,
            "halted": False,
            "terminal": True,
            "certificate": {
                "grounding": {
                    "anchor_kind": "state_supported_form_action",
                    "evidence_bids": ["user"],
                }
            },
        }
    )
    driver.audit({"type": "commit_effect_result_v8", "effective": False})
    assert driver.runtime.active == [original]
    assert driver.resolved_semantic_bids == set()
    assert certified_scope_consumption_metrics_v19(driver)[
        "certified_scope_consumption_checks_v19"
    ] == 0


def test_v19_preserves_v18_blocking_scope_consumption() -> None:
    driver = object.__new__(FullPactConfirmationDriverV19)
    driver.runtime = runtime()
    driver.runtime.active = [transaction("autocomplete_query", "query")]
    driver.trace = [
        {
            "type": "certified_commit_result_v8",
            "bid": "suggestion",
            "executed": True,
            "halted": False,
        }
    ]
    driver._consume_resolved_commit_scope_v18(("query",))
    assert driver.runtime.active == []
    assert driver.runtime.halted is False
    event = driver.runtime.events[-1]
    assert event["type"] == "certified_scope_consumption_v19"
    assert event["allowed"] is True
    assert event["consumed_kinds"] == ["autocomplete_query"]
