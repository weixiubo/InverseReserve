from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from inversereserve.contracts.transaction_actions_v4 import ContractActionV4
from inversereserve.contracts.typed_contracts_v4 import TransactionContractV4
from inversereserve.controllers.confirmation_agents_v15 import FullPactConfirmationDriverV15
from inversereserve.controllers.pact_controller_v15 import FailClosedTransactionRuntimeV15
from inversereserve.observations.typed_observation import SemanticElement, SemanticSnapshot

ROOT = Path(__file__).resolve().parents[1]


def _element(
    bid: str,
    *,
    name: str = "",
    text: str = "",
    tag: str = "div",
    class_name: str = "",
    role: str = "generic",
    clickable: bool = False,
) -> SemanticElement:
    return SemanticElement(
        bid=bid,
        role=role,
        name=name,
        subtree_text=text,
        ax_properties=(),
        ax_parent_bid=None,
        dom_tag=tag,
        dom_attributes=(("class", class_name),) if class_name else (),
        dom_parent_bid=None,
        visible=True,
        clickable=clickable,
        bbox=(0.0, 0.0, 100.0, 20.0),
    )


def _calendar(month: str, *, suffix: str) -> SemanticSnapshot:
    return SemanticSnapshot(
        (
            _element("date", tag="input", class_name="hasDatepicker", role="textbox", clickable=True),
            _element(f"surface{suffix}", class_name="ui-datepicker"),
            _element(
                f"prev{suffix}",
                name="Prev",
                tag="a",
                class_name="ui-datepicker-prev",
                role="link",
                clickable=True,
            ),
            _element(
                f"next{suffix}",
                name="Next",
                tag="a",
                class_name="ui-datepicker-next",
                role="link",
                clickable=True,
            ),
            _element(f"month{suffix}", text=month, tag="span", class_name="ui-datepicker-month"),
            _element(f"year{suffix}", text="2016", tag="span", class_name="ui-datepicker-year"),
        )
    )


def _shift(bid: str, *, prior: tuple[int, int], expected: tuple[int, int]) -> TransactionContractV4:
    return TransactionContractV4(
        kind="calendar_month_shift",
        semantic_bid="date",
        action=ContractActionV4("click", bid),
        inverse_actions=(),
        projection_kind="calendar_month_shift",
        prior_calendar=prior,
        expected_calendar=expected,
        dynamic_inverse_class_token="ui-datepicker-next",
    )


class _RerenderingCalendarExecutor:
    def __init__(self) -> None:
        self.snapshots = (
            _calendar("December", suffix="0"),
            _calendar("November", suffix="1"),
            _calendar("October", suffix="2"),
            _calendar("November", suffix="10"),
            _calendar("December", suffix="20"),
        )
        self.forward = 0
        self.inverse = 0
        self.inverse_bids = []

    def __call__(self, action, role):
        from inversereserve.controllers.pact_controller_v4 import ActionExecutionV4

        if role == "typed_forward":
            self.forward += 1
            return ActionExecutionV4(self.snapshots[self.forward])
        assert role == "typed_inverse"
        self.inverse_bids.append(action.bid)
        expected = ("next2", "next10")
        if action.bid != expected[self.inverse]:
            return ActionExecutionV4(
                self.snapshots[2 + self.inverse], action_error=f"stale inverse bid {action.bid}"
            )
        self.inverse += 1
        return ActionExecutionV4(self.snapshots[2 + self.inverse])


def test_dynamic_lifo_inverse_is_regrounded_after_each_rerender() -> None:
    executor = _RerenderingCalendarExecutor()
    runtime = FailClosedTransactionRuntimeV15(executor, lambda _contract: None)
    first = runtime.transact(
        before=executor.snapshots[0],
        contract=_shift("prev0", prior=(12, 2016), expected=(11, 2016)),
        candidate_label="Prev",
    )
    second = runtime.transact(
        before=executor.snapshots[1],
        contract=_shift("prev1", prior=(11, 2016), expected=(10, 2016)),
        candidate_label="Prev",
    )
    assert first.admitted and second.admitted
    outcomes = runtime.restore_all("live rerender regression")
    assert [row.passed for row in outcomes] == [True, True]
    assert executor.inverse_bids == ["next2", "next10"]
    assert runtime.active == []
    assert runtime.halted is False
    assert sum((event["type"] == "live_dynamic_inverse_grounding_v15" for event in runtime.events)) == 2


def test_terminal_commit_cannot_spend_an_active_inverse_reserve() -> None:
    driver = object.__new__(FullPactConfirmationDriverV15)
    contract = _shift("prev0", prior=(12, 2016), expected=(11, 2016))
    driver.runtime = SimpleNamespace(active=[SimpleNamespace(contract=contract)])
    driver.budgets = {"maximum_gui_actions": 1}
    driver.executor = SimpleNamespace(actions=[])
    driver.inverse_reservation_audits = 0
    events: list[dict[str, object]] = []
    driver.audit = events.append
    allowed, reserve = driver.inverse_reserve(SimpleNamespace(bid="terminal"), "commit")
    assert reserve == 1
    assert allowed is False
    assert driver.inverse_reservation_audits == 1
    assert events == [
        {
            "type": "inverse_budget_reservation",
            "decision": "commit",
            "bid": "terminal",
            "active_inverse_cost": 1,
            "remaining_after_action": 0,
            "allowed": False,
        }
    ]
