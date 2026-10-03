from __future__ import annotations

from pathlib import Path

import pytest

from inversereserve.contracts.transaction_actions import ActionSequenceContract, ContractAction
from inversereserve.controllers.pact_controller_v3 import (
    ActionExecution,
    ActiveSequenceTransaction,
    FailClosedTransactionRuntime,
    RuntimeHalted,
    certify_commit,
)
from inversereserve.models.structured_planner import ActionCandidate
from inversereserve.observations.typed_observation import SemanticDelta, SemanticElement, SemanticSnapshot

ROOT = Path(__file__).resolve().parents[1]


def element(
    bid: str,
    *,
    role: str = "button",
    name: str | None = None,
    parent: str | None = None,
    expanded: bool | None = None,
    value: str | None = None,
) -> SemanticElement:
    properties: list[tuple[str, object]] = []
    if expanded is not None:
        properties.append(("expanded", expanded))
    if value is not None:
        properties.append(("value", value))
    return SemanticElement(
        bid=bid,
        role=role,
        name=name or bid,
        subtree_text=name or bid,
        ax_properties=tuple(properties),
        ax_parent_bid=parent,
        dom_tag="input" if role in {"combobox", "textbox"} else "button",
        dom_attributes=(),
        dom_parent_bid=parent,
        visible=True,
        clickable=True,
        bbox=(0.0, 0.0, 10.0, 10.0),
    )


def disclosure_states() -> tuple[SemanticSnapshot, SemanticSnapshot]:
    before = SemanticSnapshot((element("toggle", expanded=False),))
    after = SemanticSnapshot(
        (element("toggle", expanded=True), element("panel", role="region", parent="toggle"))
    )
    return (before, after)


def disclosure_contract(bid: str = "toggle") -> ActionSequenceContract:
    return ActionSequenceContract(
        kind="disclosure_toggle",
        semantic_bid=bid,
        action=ContractAction("click", bid),
        inverse_actions=(ContractAction("click", bid),),
    )


def candidate(
    bid: str, label: str, *, role: str = "button", semantic_bid: str | None = None
) -> ActionCandidate:
    return ActionCandidate(
        bid=bid,
        operation="click",
        role=role,
        label=label,
        state=(),
        preview_kind=None,
        semantic_bid=semantic_bid or bid,
        parent_bid=None,
    )


class ScriptedExecutor:
    def __init__(self, rows: list[ActionExecution | Exception]) -> None:
        self.rows = list(rows)
        self.calls: list[tuple[ContractAction, str]] = []

    def __call__(self, action: ContractAction, role: str) -> ActionExecution:
        self.calls.append((action, role))
        row = self.rows.pop(0)
        if isinstance(row, Exception):
            raise row
        return row


def admitted_transaction(before: SemanticSnapshot, after: SemanticSnapshot) -> ActiveSequenceTransaction:
    return ActiveSequenceTransaction(
        disclosure_contract(), "Toggle", before, after, SemanticDelta(("panel",), (), ("toggle",), ("panel",))
    )


def test_commit_requires_a_positive_constraint_even_without_transactions() -> None:
    current = SemanticSnapshot((element("save", name="Save"),))
    save = candidate("save", "Save")
    rejected = certify_commit(
        goal="Do what is appropriate.",
        current=current,
        candidate=save,
        inventory=(save,),
        active_transactions=(),
    )
    admitted = certify_commit(
        goal='Click the button labeled "Save".',
        current=current,
        candidate=save,
        inventory=(save,),
        active_transactions=(),
    )
    assert not rejected.allowed
    assert admitted.allowed
    assert admitted.supporting_transaction_depth is None


def test_terminal_form_commit_can_bind_to_active_public_input_value() -> None:
    before = SemanticSnapshot((element("country", role="combobox", value=""),))
    current = SemanticSnapshot(
        (element("country", role="combobox", value="Mongolia"), element("submit", name="Submit"))
    )
    transaction = ActiveSequenceTransaction(
        ActionSequenceContract(
            "combobox_suggestion",
            "country",
            ContractAction("fill", "country", "Mon", True),
            (ContractAction("press", "country", "Escape"), ContractAction("fill", "country", "", False)),
        ),
        "Country",
        before,
        current,
        SemanticDelta(("submit",), (), ("country",), ("Mongolia",)),
    )
    submit = candidate("submit", "Submit")
    certificate = certify_commit(
        goal='Enter an item that starts with "Mon" and ends with "ia".',
        current=current,
        candidate=submit,
        inventory=(submit,),
        active_transactions=(transaction,),
    )
    assert certificate.allowed
    assert certificate.supporting_transaction_depth == 1
    assert certificate.grounding.supporting_value_bids == ("country",)


def test_grounded_unrelated_commit_is_blocked_while_transaction_is_active() -> None:
    before, after = disclosure_states()
    transaction = admitted_transaction(before, after)
    current = SemanticSnapshot(after.elements + (element("save", name="Save"),))
    save = candidate("save", "Save")
    certificate = certify_commit(
        goal='Click the button labeled "Save".',
        current=current,
        candidate=save,
        inventory=(save,),
        active_transactions=(transaction,),
    )
    assert not certificate.allowed
    assert "valid transaction scope" in certificate.reason


def test_duplicate_public_targets_are_rejected_as_ambiguous() -> None:
    current = SemanticSnapshot((element("save1", name="Save"), element("save2", name="Save")))
    save1 = candidate("save1", "Save")
    save2 = candidate("save2", "Save")
    certificate = certify_commit(
        goal='Click the button labeled "Save".',
        current=current,
        candidate=save1,
        inventory=(save1, save2),
        active_transactions=(),
    )
    assert not certificate.allowed
    assert certificate.competing_bids == ("save1", "save2")
    assert "ambiguous" in certificate.reason


def test_commit_execution_is_bound_to_bid_observation_and_transaction_stack() -> None:
    current = SemanticSnapshot((element("save", name="Save"), element("other", name="Other")))
    save = candidate("save", "Save")
    other = candidate("other", "Other")
    certificate = certify_commit(
        goal='Click the button labeled "Save".',
        current=current,
        candidate=save,
        inventory=(save, other),
        active_transactions=(),
    )
    executor = ScriptedExecutor([ActionExecution(current)])
    runtime = FailClosedTransactionRuntime(executor)
    wrong_action = runtime.commit(
        current=current, action=ContractAction("click", "other"), certificate=certificate
    )
    stale_state = SemanticSnapshot(current.elements + (element("notice", role="status"),))
    stale = runtime.commit(
        current=stale_state, action=ContractAction("click", "save"), certificate=certificate
    )
    admitted = runtime.commit(
        current=current, action=ContractAction("click", "save"), certificate=certificate
    )
    assert not wrong_action.executed
    assert not stale.executed
    assert admitted.executed
    assert len(executor.calls) == 1


def test_commit_certificate_is_rejected_after_transaction_stack_changes() -> None:
    before, after = disclosure_states()
    save = candidate("save", "Save")
    current = SemanticSnapshot(after.elements + (element("save", name="Save", parent="toggle"),))
    transaction = admitted_transaction(before, after)
    transaction_current = ActiveSequenceTransaction(
        transaction.contract,
        transaction.candidate_label,
        transaction.before,
        current,
        SemanticDelta(("panel", "save"), (), ("toggle",), ("Save",)),
    )
    certificate = certify_commit(
        goal='Click the button labeled "Save".',
        current=current,
        candidate=save,
        inventory=(save,),
        active_transactions=(transaction_current,),
    )
    runtime = FailClosedTransactionRuntime(ScriptedExecutor([ActionExecution(current)]))
    outcome = runtime.commit(current=current, action=ContractAction("click", "save"), certificate=certificate)
    assert not outcome.executed
    assert "transaction stack" in outcome.reason


def test_runtime_admits_then_restores_a_certified_transaction() -> None:
    before, after = disclosure_states()
    executor = ScriptedExecutor([ActionExecution(after), ActionExecution(before)])
    runtime = FailClosedTransactionRuntime(executor)
    exploration = runtime.explore(before=before, contract=disclosure_contract(), candidate_label="Toggle")
    restoration = runtime.restore_top("test cleanup")
    assert exploration.admitted
    assert restoration.passed
    assert not runtime.active
    assert len(runtime.completed) == 1
    assert [role for _action, role in executor.calls] == ["typed_preview", "typed_inverse"]


def test_restore_all_is_lifo_and_checks_each_transaction_fingerprint() -> None:
    initial = SemanticSnapshot((element("outer", expanded=False),))
    outer_open = SemanticSnapshot(
        (element("outer", expanded=True), element("inner", parent="outer", expanded=False))
    )
    inner_open = SemanticSnapshot(
        (
            element("outer", expanded=True),
            element("inner", parent="outer", expanded=True),
            element("leaf", role="region", parent="inner"),
        )
    )
    executor = ScriptedExecutor(
        [
            ActionExecution(outer_open),
            ActionExecution(inner_open),
            ActionExecution(outer_open),
            ActionExecution(initial),
        ]
    )
    runtime = FailClosedTransactionRuntime(executor)
    assert runtime.explore(
        before=initial, contract=disclosure_contract("outer"), candidate_label="Outer"
    ).admitted
    assert runtime.explore(
        before=outer_open, contract=disclosure_contract("inner"), candidate_label="Inner"
    ).admitted
    outcomes = runtime.restore_all("cleanup")
    assert [row.passed for row in outcomes] == [True, True]
    assert not runtime.active
    inverse_bids = [action.bid for action, role in executor.calls if role == "typed_inverse"]
    assert inverse_bids == ["inner", "outer"]


def test_unchanged_failed_preview_skips_a_dangerous_inverse() -> None:
    before, _after = disclosure_states()
    executor = ScriptedExecutor([ActionExecution(before)])
    runtime = FailClosedTransactionRuntime(executor)
    outcome = runtime.explore(before=before, contract=disclosure_contract(), candidate_label="Toggle")
    assert not outcome.admitted
    assert outcome.restoration is not None
    assert outcome.restoration.passed and (not outcome.restoration.attempted)
    assert not runtime.halted
    assert len(executor.calls) == 1


def test_changed_failed_postcondition_is_inverted_before_continuing() -> None:
    before, _after = disclosure_states()
    unrelated = SemanticSnapshot(before.elements + (element("noise", role="region"),))
    executor = ScriptedExecutor([ActionExecution(unrelated), ActionExecution(before)])
    runtime = FailClosedTransactionRuntime(executor)
    outcome = runtime.explore(before=before, contract=disclosure_contract(), candidate_label="Toggle")
    assert not outcome.admitted
    assert outcome.restoration is not None and outcome.restoration.passed
    assert not runtime.halted
    assert len(executor.calls) == 2


def test_failed_restoration_halts_and_retains_unresolved_transaction() -> None:
    before, after = disclosure_states()
    residual = SemanticSnapshot(before.elements + (element("residual", role="region"),))
    executor = ScriptedExecutor([ActionExecution(after), ActionExecution(residual)])
    runtime = FailClosedTransactionRuntime(executor)
    assert runtime.explore(before=before, contract=disclosure_contract(), candidate_label="Toggle").admitted
    restoration = runtime.restore_top("test failure")
    assert not restoration.passed
    assert runtime.halted
    assert len(runtime.active) == 1
    calls_before = len(executor.calls)
    with pytest.raises(RuntimeHalted):
        runtime.restore_top("must not continue")
    assert len(executor.calls) == calls_before


def test_failed_unadmitted_preview_retains_unresolved_state_on_bad_inverse() -> None:
    before, _after = disclosure_states()
    unrelated = SemanticSnapshot(before.elements + (element("noise", role="region"),))
    executor = ScriptedExecutor([ActionExecution(unrelated), ActionExecution(unrelated)])
    runtime = FailClosedTransactionRuntime(executor)
    outcome = runtime.explore(before=before, contract=disclosure_contract(), candidate_label="Toggle")
    assert outcome.halted
    assert len(runtime.active) == 1
    assert runtime.active[0].after == unrelated


def test_terminal_preview_and_executor_exception_are_fail_closed() -> None:
    before, after = disclosure_states()
    terminal_runtime = FailClosedTransactionRuntime(
        ScriptedExecutor([ActionExecution(after, terminated=True)])
    )
    terminal = terminal_runtime.explore(
        before=before, contract=disclosure_contract(), candidate_label="Toggle"
    )
    assert terminal.halted and terminal_runtime.halted
    error_runtime = FailClosedTransactionRuntime(ScriptedExecutor([RuntimeError("browser disconnected")]))
    failed = error_runtime.explore(before=before, contract=disclosure_contract(), candidate_label="Toggle")
    assert failed.halted
    assert "executor error" in (error_runtime.halt_reason or "")


def test_postcondition_verifier_exception_restores_then_halts() -> None:
    before, after = disclosure_states()
    contract = ActionSequenceContract(
        "unsupported_kind", "toggle", ContractAction("click", "toggle"), (ContractAction("click", "toggle"),)
    )
    executor = ScriptedExecutor([ActionExecution(after), ActionExecution(before)])
    runtime = FailClosedTransactionRuntime(executor)
    outcome = runtime.explore(before=before, contract=contract, candidate_label="Toggle")
    assert outcome.halted
    assert outcome.restoration is not None and outcome.restoration.passed
    assert not runtime.active
    assert any((row["type"] == "verification_exception" for row in runtime.events))


def test_invalid_executor_result_halts_before_result_fields_are_used() -> None:
    before, _after = disclosure_states()

    def invalid_executor(_action: ContractAction, _role: str):
        return object()

    runtime = FailClosedTransactionRuntime(invalid_executor)
    outcome = runtime.explore(before=before, contract=disclosure_contract(), candidate_label="Toggle")
    assert outcome.halted
    assert runtime.halt_reason == "executor returned an invalid action result"


def test_inverse_error_stops_a_multi_action_sequence_immediately() -> None:
    before = SemanticSnapshot((element("country", role="combobox", value=""),))
    after = SemanticSnapshot(
        (element("country", role="combobox", value="Mon"), element("listbox", role="listbox"))
    )
    contract = ActionSequenceContract(
        "combobox_suggestion",
        "country",
        ContractAction("fill", "country", "Mon", True),
        (ContractAction("press", "country", "Escape"), ContractAction("fill", "country", "", False)),
    )
    executor = ScriptedExecutor(
        [
            ActionExecution(after),
            ActionExecution(after, action_error="key dispatch failed"),
            ActionExecution(before),
        ]
    )
    runtime = FailClosedTransactionRuntime(executor)
    assert runtime.explore(before=before, contract=contract, candidate_label="Country").admitted
    outcome = runtime.restore_top("cleanup")
    assert not outcome.passed and runtime.halted
    assert len(runtime.active) == 1
    assert len(executor.calls) == 2
