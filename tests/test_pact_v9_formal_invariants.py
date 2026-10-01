from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from rcrps.confirmation_agents_v8 import FullPactConfirmationDriverV8  # noqa: E402
from rcrps.goal_contracts_v4 import compile_structured_goal  # noqa: E402
from rcrps.pact_controller_v4 import (  # noqa: E402
    ActionExecutionV4,
    ActiveTransactionV4,
    FailClosedTransactionRuntimeV4,
    RuntimeHaltedV4,
)
from rcrps.pact_grounding_v8 import certify_commit_v8  # noqa: E402
from rcrps.structured_planner_v6 import compile_v6_inventory  # noqa: E402
from rcrps.transaction_actions_v4 import ContractActionV4  # noqa: E402
from rcrps.typed_contracts_v4 import (  # noqa: E402
    TransactionContractV4,
    infer_transaction_contract,
)
from rcrps.typed_observation import (  # noqa: E402
    SemanticDelta,
    SemanticElement,
    SemanticSnapshot,
)


def element(
    bid: str,
    *,
    role: str = "generic",
    name: str = "",
    text: str = "",
    tag: str = "div",
    value: str | None = None,
    dom_parent: str | None = None,
    clickable: bool = False,
) -> SemanticElement:
    attributes = {} if value is None else {"value": value}
    properties = {} if value is None else {"value": value, "readonly": False}
    return SemanticElement(
        bid=bid,
        role=role,
        name=name,
        subtree_text=text,
        ax_properties=tuple(sorted(properties.items())),
        ax_parent_bid=None,
        dom_tag=tag,
        dom_attributes=tuple(sorted(attributes.items())),
        dom_parent_bid=dom_parent,
        visible=True,
        clickable=clickable,
        bbox=(0.0, 0.0, 20.0, 10.0),
    )


def direct_button_snapshot(*, extra: bool = False) -> SemanticSnapshot:
    rows = [
        element(
            "button",
            role="button",
            name="Continue",
            tag="button",
            clickable=True,
        )
    ]
    if extra:
        rows.append(element("status", text="changed"))
    return SemanticSnapshot(tuple(rows))


def direct_button_certificate(snapshot: SemanticSnapshot):
    inventory = compile_v6_inventory(snapshot, 'Click on a "button" widget.')
    candidate = next(row for row in inventory.candidates if row.bid == "button")
    certificate = certify_commit_v8(
        current=snapshot,
        goal=inventory.goal_contract,
        candidate=candidate,
        inventory=inventory.candidates,
        active_transactions=(),
    )
    assert certificate.allowed
    return candidate, certificate


class ForbiddenExecutor:
    def __init__(self) -> None:
        self.calls = 0

    def __call__(self, _action, _role: str) -> ActionExecutionV4:
        self.calls += 1
        raise AssertionError("rejected commit reached the executor")


def dummy_active(snapshot: SemanticSnapshot) -> ActiveTransactionV4:
    contract = TransactionContractV4(
        kind="editable_field_assignment",
        semantic_bid="field",
        action=ContractActionV4("fill", "field", "x", False),
        inverse_actions=(ContractActionV4("fill", "field", "", False),),
        expected_value="x",
        prior_value="",
        projection_kind="editable_field_assignment",
    )
    return ActiveTransactionV4(
        contract=contract,
        candidate_label="field",
        before=snapshot,
        after=snapshot,
        delta=SemanticDelta((), (), (), ()),
    )


def test_commit_authority_rejects_stale_observation_stack_or_action() -> None:
    snapshot = direct_button_snapshot()
    candidate, certificate = direct_button_certificate(snapshot)

    stale_executor = ForbiddenExecutor()
    stale_runtime = FailClosedTransactionRuntimeV4(stale_executor)
    stale = stale_runtime.commit(
        current=direct_button_snapshot(extra=True),
        action=candidate.action,
        certificate=certificate,
    )
    assert not stale.executed and not stale.halted
    assert stale_executor.calls == 0
    assert "stale" in stale.reason

    stack_executor = ForbiddenExecutor()
    stack_runtime = FailClosedTransactionRuntimeV4(stack_executor)
    stack_runtime.active.append(dummy_active(snapshot))
    stack = stack_runtime.commit(
        current=snapshot,
        action=candidate.action,
        certificate=certificate,
    )
    assert not stack.executed and not stack.halted
    assert stack_executor.calls == 0
    assert "stack" in stack.reason

    action_executor = ForbiddenExecutor()
    action_runtime = FailClosedTransactionRuntimeV4(action_executor)
    mismatch = action_runtime.commit(
        current=snapshot,
        action=ContractActionV4("click", "different"),
        certificate=certificate,
    )
    assert not mismatch.executed and not mismatch.halted
    assert action_executor.calls == 0
    assert "differs" in mismatch.reason


def test_fresh_exact_commit_is_the_only_commit_path_reaching_executor() -> None:
    snapshot = direct_button_snapshot()
    candidate, certificate = direct_button_certificate(snapshot)
    calls = []

    def executor(action, role: str) -> ActionExecutionV4:
        calls.append((action, role))
        return ActionExecutionV4(snapshot, terminated=True)

    runtime = FailClosedTransactionRuntimeV4(executor)
    outcome = runtime.commit(
        current=snapshot,
        action=candidate.action,
        certificate=certificate,
    )
    assert outcome.executed and not outcome.halted
    assert calls == [(candidate.action, "commit")]
    assert [event["type"] for event in runtime.events] == ["action"]


def field_snapshot(value: str) -> SemanticSnapshot:
    return SemanticSnapshot(
        (
            element("form", text="Username OK"),
            element("row", text="Username", dom_parent="form"),
            element(
                "field",
                role="textbox",
                tag="input",
                value=value,
                dom_parent="row",
                clickable=True,
            ),
            element(
                "submit",
                role="button",
                name="OK",
                tag="button",
                dom_parent="form",
                clickable=True,
            ),
        )
    )


def field_contract(before: SemanticSnapshot) -> TransactionContractV4:
    goal = compile_structured_goal(
        'Enter the username "michel" and press login.', before
    )
    decision = infer_transaction_contract(before, "field", goal)
    assert decision.allowed and decision.contract is not None
    return decision.contract


class ScriptedExecutor:
    def __init__(self, snapshots: list[SemanticSnapshot]) -> None:
        self.snapshots = list(snapshots)
        self.roles: list[str] = []

    def __call__(self, _action, role: str) -> ActionExecutionV4:
        self.roles.append(role)
        return ActionExecutionV4(self.snapshots.pop(0))


def test_failed_postcondition_executes_inverse_before_rejecting() -> None:
    before = field_snapshot("")
    wrong = field_snapshot("other")
    executor = ScriptedExecutor([wrong, before])
    runtime = FailClosedTransactionRuntimeV4(executor)
    outcome = runtime.transact(
        before=before,
        contract=field_contract(before),
        candidate_label="Username",
    )
    assert not outcome.admitted and not outcome.halted
    assert outcome.restoration is not None and outcome.restoration.passed
    assert runtime.active == []
    assert executor.roles == ["typed_forward", "typed_inverse"]
    assert [event["type"] for event in runtime.events] == [
        "action",
        "postcondition",
        "action",
        "restoration",
    ]


def test_unverified_restoration_halts_with_transaction_unresolved() -> None:
    before = field_snapshot("")
    filled = field_snapshot("michel")
    residual = field_snapshot("residual")
    executor = ScriptedExecutor([filled, residual])
    runtime = FailClosedTransactionRuntimeV4(executor)
    admitted = runtime.transact(
        before=before,
        contract=field_contract(before),
        candidate_label="Username",
    )
    assert admitted.admitted and len(runtime.active) == 1
    restored = runtime.restore_top("formal invariant test")
    assert not restored.passed
    assert runtime.halted and len(runtime.active) == 1
    assert runtime.events[-1]["type"] == "fail_closed"
    with pytest.raises(RuntimeHaltedV4):
        runtime.restore_top("must remain locked")


def reserve_driver(*, maximum_gui_actions: int):
    contract = TransactionContractV4(
        kind="autocomplete_query",
        semantic_bid="field",
        action=ContractActionV4("fill", "field", "Ma", True),
        inverse_actions=(
            ContractActionV4("press", "field", "Escape"),
            ContractActionV4("fill", "field", "", False),
        ),
        expected_value="Ma",
        prior_value="",
        projection_kind="autocomplete_query",
    )
    driver = object.__new__(FullPactConfirmationDriverV8)
    driver.budgets = {"maximum_gui_actions": maximum_gui_actions}
    driver.executor = SimpleNamespace(actions=[])
    driver.runtime = SimpleNamespace(active=[])
    driver.inverse_reservation_audits = 0
    driver.runtime_events = []
    driver.inventory = lambda: SimpleNamespace(contract_by_bid={"field": contract})
    driver.audit = driver.runtime_events.append
    return driver, SimpleNamespace(bid="field")


def test_forward_action_is_withheld_when_inverse_budget_is_insolvent() -> None:
    solvent, candidate = reserve_driver(maximum_gui_actions=3)
    allowed, reserve = solvent.inverse_reserve(candidate, "transact")
    assert allowed and reserve == 2

    insolvent, candidate = reserve_driver(maximum_gui_actions=2)
    allowed, reserve = insolvent.inverse_reserve(candidate, "transact")
    assert not allowed and reserve == 2
    assert insolvent.runtime_events[-1] == {
        "type": "inverse_budget_reservation",
        "decision": "transact",
        "bid": "field",
        "active_inverse_cost": 2,
        "remaining_after_action": 1,
        "allowed": False,
    }
