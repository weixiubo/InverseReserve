from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from inversereserve.controllers.confirmation_agents_v18 import (
    FullPactConfirmationDriverV18,
    _CertifiedCommitResolutionSetV18,
    certified_scope_consumption_metrics_v18,
)
from inversereserve.controllers.pact_controller_v4 import ActiveTransactionV4
from inversereserve.controllers.pact_controller_v18 import FailClosedTransactionRuntimeV18
from inversereserve.observations.typed_observation import semantic_delta

from .test_pact_controller_v15 import _calendar, _RerenderingCalendarExecutor, _shift

ROOT = Path(__file__).resolve().parents[1]


def runtime() -> tuple[FailClosedTransactionRuntimeV18, _RerenderingCalendarExecutor]:
    executor = _RerenderingCalendarExecutor()
    value = FailClosedTransactionRuntimeV18(executor, lambda _contract: None, lambda _contract: None)
    return (value, executor)


def active_calendar_runtime() -> FailClosedTransactionRuntimeV18:
    value, executor = runtime()
    first = value.transact(
        before=executor.snapshots[0],
        contract=_shift("prev0", prior=(12, 2016), expected=(11, 2016)),
        candidate_label="Prev",
    )
    second = value.transact(
        before=executor.snapshots[1],
        contract=_shift("prev1", prior=(11, 2016), expected=(10, 2016)),
        candidate_label="Prev",
    )
    assert first.admitted and second.admitted and (len(value.active) == 2)
    return value


def test_v18_effective_commit_consumes_one_contiguous_resolved_suffix() -> None:
    value = active_calendar_runtime()
    consumed = value.consume_resolved_commit_scope_v18(("date",), commit_bid="target-date")
    assert len(consumed) == 2
    assert value.active == []
    assert value.halted is False
    assert all((row["committed"] is True for row in value.completed))
    assert all((row["restored"] is False for row in value.completed))
    event = next((row for row in value.events if row.get("type") == "certified_scope_consumption_v18"))
    assert event["allowed"] is True
    assert event["consumed_transactions"] == 2


def test_v18_inherited_resolution_update_consumes_scope_without_parent_edit() -> None:
    driver = object.__new__(FullPactConfirmationDriverV18)
    driver.runtime = active_calendar_runtime()
    driver.trace = [
        {"type": "certified_commit_result_v8", "bid": "target-date", "executed": True, "halted": False}
    ]
    driver.resolved_semantic_bids = _CertifiedCommitResolutionSetV18(driver)
    driver.resolved_semantic_bids.update(("date",))
    assert driver.resolved_semantic_bids == {"date"}
    assert driver.runtime.active == []
    metrics = certified_scope_consumption_metrics_v18(driver)
    assert metrics == {
        "certified_scope_consumption_checks_v18": 1,
        "certified_scope_consumption_passes_v18": 1,
        "certified_scope_consumption_failures_v18": 0,
        "certified_scope_consumed_transactions_v18": 2,
    }


def test_v18_rejects_resolved_scope_without_commit_binding() -> None:
    value = active_calendar_runtime()
    original = tuple(value.active)
    consumed = value.consume_resolved_commit_scope_v18(("date",), commit_bid="")
    assert consumed == ()
    assert tuple(value.active) == original
    assert value.halted is True
    assert value.events[-2]["type"] == "certified_scope_consumption_v18"
    assert value.events[-2]["allowed"] is False


def test_v18_rejects_a_noncontiguous_resolved_scope_without_mutation() -> None:
    value, _executor = runtime()
    before = _calendar("December", suffix="0")
    after = _calendar("November", suffix="1")
    date_contract = _shift("prev0", prior=(12, 2016), expected=(11, 2016))
    other_contract = replace(date_contract, semantic_bid="other")
    value.active = [
        ActiveTransactionV4(date_contract, "Prev", before, after, semantic_delta(before, after)),
        ActiveTransactionV4(other_contract, "Other", before, after, semantic_delta(before, after)),
    ]
    original = tuple(value.active)
    consumed = value.consume_resolved_commit_scope_v18(("date",), commit_bid="target-date")
    assert consumed == ()
    assert tuple(value.active) == original
    assert value.halted is True
    check = next((row for row in value.events if row.get("type") == "certified_scope_consumption_v18"))
    assert check["allowed"] is False


def test_v18_rejects_an_unsupported_transaction_kind_without_mutation() -> None:
    value, _executor = runtime()
    before = _calendar("December", suffix="0")
    after = _calendar("November", suffix="1")
    unsupported = replace(
        _shift("prev0", prior=(12, 2016), expected=(11, 2016)), kind="arbitrary_crossing_scope"
    )
    transaction = ActiveTransactionV4(
        unsupported, "Unsupported", before, after, semantic_delta(before, after)
    )
    value.active = [transaction]
    consumed = value.consume_resolved_commit_scope_v18(("date",), commit_bid="target-date")
    assert consumed == ()
    assert value.active == [transaction]
    assert value.halted is True
