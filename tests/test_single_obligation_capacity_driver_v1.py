from __future__ import annotations

from types import SimpleNamespace

from rcrps import single_obligation_capacity_driver_v1 as module
from rcrps.capacity_reserve_drivers_v18 import StackWideCapacityDriverV18


def driver(active: int) -> tuple[module.SingleActiveObligationDriverV1, list[dict]]:
    value = module.SingleActiveObligationDriverV1.__new__(
        module.SingleActiveObligationDriverV1
    )
    value.runtime = SimpleNamespace(
        active=[SimpleNamespace(contract=object()) for _ in range(active)]
    )
    value.inverse_reservation_audits = 0
    events: list[dict] = []
    value.audit = events.append
    return value, events


def test_second_transaction_is_rejected_and_audited(monkeypatch) -> None:
    value, events = driver(1)
    monkeypatch.setattr(module, "inverse_action_cost_v8", lambda _contract: 3)
    allowed, reserve = value.inverse_reserve(
        SimpleNamespace(bid="candidate"), "transact"
    )
    assert allowed is False
    assert reserve == 3
    assert value.inverse_reservation_audits == 1
    assert events == [
        {
            "type": module.SINGLE_OBLIGATION_POLICY_EVENT_V1,
            "policy": "at_most_one_active_obligation",
            "decision": "transact",
            "bid": "candidate",
            "active_obligations_before_proposal": 1,
            "registered_active_inverse_cost": 3,
            "allowed": False,
            "delegated_to_stack_wide_reserve": False,
            "reason": "second active transaction is forbidden",
        }
    ]


def test_zero_active_or_commit_delegates_to_stack_wide(monkeypatch) -> None:
    calls = []

    def parent(self, candidate, decision):
        calls.append((candidate.bid, decision))
        self.inverse_reservation_audits += 1
        return True, 4

    monkeypatch.setattr(
        StackWideCapacityDriverV18,
        "inverse_reserve",
        parent,
    )
    for active, decision in ((0, "transact"), (1, "commit")):
        value, events = driver(active)
        allowed, reserve = value.inverse_reserve(
            SimpleNamespace(bid="candidate"), decision
        )
        assert (allowed, reserve) == (True, 4)
        assert value.inverse_reservation_audits == 1
        assert events[-1]["delegated_to_stack_wide_reserve"] is True
        assert events[-1]["active_obligations_before_proposal"] == active
    assert calls == [("candidate", "transact"), ("candidate", "commit")]


def test_driver_is_stack_wide_and_has_distinct_method_id() -> None:
    assert issubclass(
        module.SingleActiveObligationDriverV1,
        StackWideCapacityDriverV18,
    )
    assert (
        module.SingleActiveObligationDriverV1.method_id
        == "single_active_obligation_v1"
    )
