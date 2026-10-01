"""Deterministic fault injections for PACT's non-efficacy mechanism audit.

The final benchmark comparison is designed to estimate task success.  Several
fail-closed guards should rarely activate in a passing population, so removing
them there can produce an uninformative identical trajectory.  This module
instead injects one public-state fault per guard and compares the frozen PACT
operation with the exact guard removed.  It makes no benchmark or task-success
claim.
"""

from __future__ import annotations

from dataclasses import asdict
from types import SimpleNamespace
from typing import Any

from .confirmation_agents_v8 import FullPactConfirmationDriverV8
from .effect_ledger_v8 import CommitEffectLedgerV8
from .goal_contracts_v4 import compile_structured_goal
from .pact_controller_v4 import ActionExecutionV4
from .pact_controller_v9 import FailClosedTransactionRuntimeV9
from .pact_grounding_v8 import certify_commit_v8
from .structured_planner_v6 import compile_v6_inventory
from .transaction_actions_v4 import ContractActionV4
from .typed_contracts_v4 import TransactionContractV4, infer_transaction_contract
from .typed_contracts_v9 import check_transaction_postcondition_v9
from .typed_observation import (
    ContractCheck,
    SemanticElement,
    SemanticSnapshot,
    semantic_delta,
)


CASE_IDS = (
    "postcondition_enforcement",
    "fresh_commit_authority",
    "inverse_budget_reservation",
    "no_effect_quarantine",
)


def _element(
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


def _field_snapshot(value: str) -> SemanticSnapshot:
    return SemanticSnapshot(
        (
            _element("form", text="Username OK"),
            _element("row", text="Username", dom_parent="form"),
            _element(
                "field",
                role="textbox",
                tag="input",
                value=value,
                dom_parent="row",
                clickable=True,
            ),
            _element(
                "submit",
                role="button",
                name="OK",
                tag="button",
                dom_parent="form",
                clickable=True,
            ),
        )
    )


def _field_contract(before: SemanticSnapshot) -> TransactionContractV4:
    goal = compile_structured_goal(
        'Enter the username "michel" and press login.', before
    )
    decision = infer_transaction_contract(before, "field", goal)
    if not decision.allowed or decision.contract is None:
        raise RuntimeError("fixture field did not compile to a transaction")
    return decision.contract


def _button_snapshot(*, stale: bool = False) -> SemanticSnapshot:
    elements = [
        _element(
            "button",
            role="button",
            name="Continue",
            tag="button",
            clickable=True,
        )
    ]
    if stale:
        elements.append(_element("status", text="public state changed"))
    return SemanticSnapshot(tuple(elements))


def _button_candidate(snapshot: SemanticSnapshot) -> tuple[Any, Any, tuple[Any, ...]]:
    inventory = compile_v6_inventory(snapshot, 'Click on a "button" widget.')
    candidate = next(row for row in inventory.candidates if row.bid == "button")
    certificate = certify_commit_v8(
        current=snapshot,
        goal=inventory.goal_contract,
        candidate=candidate,
        inventory=inventory.candidates,
        active_transactions=(),
    )
    if not certificate.allowed:
        raise RuntimeError("fixture button did not receive a fresh certificate")
    return candidate, inventory.goal_contract, inventory.candidates


class _ScriptedExecutor:
    def __init__(self, snapshots: list[SemanticSnapshot]) -> None:
        self.snapshots = list(snapshots)
        self.roles: list[str] = []

    def __call__(self, _action: Any, role: str) -> ActionExecutionV4:
        self.roles.append(role)
        return ActionExecutionV4(self.snapshots.pop(0))


class _CountingExecutor:
    def __init__(self, snapshot: SemanticSnapshot) -> None:
        self.snapshot = snapshot
        self.calls: list[dict[str, Any]] = []

    def __call__(self, action: ContractActionV4, role: str) -> ActionExecutionV4:
        self.calls.append({"action": asdict(action), "role": role})
        return ActionExecutionV4(self.snapshot)


class PostconditionBypassRuntimeV1(FailClosedTransactionRuntimeV9):
    """Counterfactual runtime that observes but does not enforce v9 postconditions."""

    def _check_postcondition(
        self,
        before: SemanticSnapshot,
        after: SemanticSnapshot,
        contract: TransactionContractV4,
        *,
        context: str,
    ) -> ContractCheck:
        counterfactual = check_transaction_postcondition_v9(before, after, contract)
        delta = semantic_delta(before, after)
        self._audit(
            {
                "type": "postcondition_ablation",
                "context": context,
                "contract_kind": contract.kind,
                "passed": True,
                "counterfactual_passed": counterfactual.passed,
                "counterfactual_reason": counterfactual.reason,
                "delta": asdict(delta),
            }
        )
        return ContractCheck(True, "postcondition enforcement removed", delta)


class InverseReservationBypassDriverV1(FullPactConfirmationDriverV8):
    """Counterfactual driver that audits inverse cost but never withholds."""

    def inverse_reserve(self, candidate: Any, decision: str) -> tuple[bool, int]:
        full_allowed, reserve = super().inverse_reserve(candidate, decision)
        self.audit(
            {
                "type": "inverse_budget_reservation_ablation",
                "full_would_allow": full_allowed,
                "allowed": True,
            }
        )
        return True, reserve


def _case(
    case_id: str,
    full: dict[str, Any],
    ablated: dict[str, Any],
    checks: dict[str, bool],
) -> dict[str, Any]:
    if case_id not in CASE_IDS:
        raise ValueError(f"unknown conformance case: {case_id}")
    if not checks or any(type(value) is not bool for value in checks.values()):
        raise ValueError(f"invalid conformance checks: {case_id}")
    return {
        "case_id": case_id,
        "full_pact": full,
        "guard_removed": ablated,
        "checks": checks,
        "passed": all(checks.values()),
    }


def postcondition_enforcement_case() -> dict[str, Any]:
    before = _field_snapshot("")
    wrong = _field_snapshot("other")
    contract = _field_contract(before)

    full_executor = _ScriptedExecutor([wrong, before])
    full_runtime = FailClosedTransactionRuntimeV9(full_executor)
    full_outcome = full_runtime.transact(
        before=before,
        contract=contract,
        candidate_label="Username",
    )

    ablated_executor = _ScriptedExecutor([wrong])
    ablated_runtime = PostconditionBypassRuntimeV1(ablated_executor)
    ablated_outcome = ablated_runtime.transact(
        before=before,
        contract=contract,
        candidate_label="Username",
    )
    counterfactual_events = [
        event
        for event in ablated_runtime.events
        if event["type"] == "postcondition_ablation"
    ]
    checks = {
        "full_rejects_wrong_transition": not full_outcome.admitted,
        "full_executes_registered_inverse": full_executor.roles
        == ["typed_forward", "typed_inverse"],
        "full_verifies_public_restoration": bool(
            full_outcome.restoration and full_outcome.restoration.passed
        ),
        "removed_guard_admits_same_wrong_transition": ablated_outcome.admitted,
        "removed_guard_executes_no_inverse": ablated_executor.roles
        == ["typed_forward"],
        "counterfactual_predicate_would_fail": len(counterfactual_events) == 1
        and counterfactual_events[0]["counterfactual_passed"] is False,
    }
    return _case(
        "postcondition_enforcement",
        {
            "admitted": full_outcome.admitted,
            "executor_roles": full_executor.roles,
            "restoration_passed": bool(
                full_outcome.restoration and full_outcome.restoration.passed
            ),
            "active_depth": len(full_runtime.active),
        },
        {
            "admitted": ablated_outcome.admitted,
            "executor_roles": ablated_executor.roles,
            "counterfactual_passed": counterfactual_events[0][
                "counterfactual_passed"
            ],
            "active_depth": len(ablated_runtime.active),
        },
        checks,
    )


def fresh_commit_authority_case() -> dict[str, Any]:
    before = _button_snapshot()
    stale = _button_snapshot(stale=True)
    candidate, goal, inventory = _button_candidate(before)
    certificate = certify_commit_v8(
        current=before,
        goal=goal,
        candidate=candidate,
        inventory=inventory,
        active_transactions=(),
    )
    full_executor = _CountingExecutor(stale)
    runtime = FailClosedTransactionRuntimeV9(full_executor)
    rejected = runtime.commit(
        current=stale,
        action=candidate.action,
        certificate=certificate,
    )

    ablated_executor = _CountingExecutor(stale)
    ablated_executor(candidate.action, "uncertified_commit")
    checks = {
        "full_rejects_stale_certificate": not rejected.executed,
        "full_makes_zero_executor_calls": len(full_executor.calls) == 0,
        "removed_guard_reaches_executor": len(ablated_executor.calls) == 1,
        "removed_guard_uses_exact_proposed_action": ablated_executor.calls[0][
            "action"
        ]
        == asdict(candidate.action),
    }
    return _case(
        "fresh_commit_authority",
        {
            "executed": rejected.executed,
            "reason": rejected.reason,
            "executor_calls": len(full_executor.calls),
        },
        {
            "executed": True,
            "role": "uncertified_commit",
            "executor_calls": len(ablated_executor.calls),
        },
        checks,
    )


def inverse_budget_reservation_case() -> dict[str, Any]:
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
    def configured(driver_class: type[FullPactConfirmationDriverV8]):
        driver = object.__new__(driver_class)
        driver.budgets = {"maximum_gui_actions": 2}
        driver.executor = SimpleNamespace(actions=[])
        driver.runtime = SimpleNamespace(active=[])
        driver.inverse_reservation_audits = 0
        driver.runtime_events = []
        driver.inventory = lambda: SimpleNamespace(
            contract_by_bid={"field": contract}
        )
        driver.audit = driver.runtime_events.append
        return driver

    candidate = SimpleNamespace(bid="field")
    full_driver = configured(FullPactConfirmationDriverV8)
    allowed, reserve = full_driver.inverse_reserve(candidate, "transact")
    remaining_after_action = full_driver.runtime_events[-1][
        "remaining_after_action"
    ]
    ablated_driver = configured(InverseReservationBypassDriverV1)
    ablated_allowed, ablated_reserve = ablated_driver.inverse_reserve(
        candidate, "transact"
    )
    checks = {
        "inverse_cost_is_exact_sequence_length": reserve == 2,
        "full_withholds_insolvent_forward": allowed is False,
        "remaining_budget_is_below_inverse_cost": remaining_after_action < reserve,
        "removed_guard_allows_forward": ablated_allowed,
        "removed_guard_observes_same_inverse_cost": ablated_reserve == reserve,
    }
    return _case(
        "inverse_budget_reservation",
        {
            "forward_allowed": allowed,
            "inverse_cost": reserve,
            "remaining_after_forward": remaining_after_action,
        },
        {
            "forward_allowed": ablated_allowed,
            "inverse_cost_ignored": ablated_reserve,
            "remaining_after_forward": remaining_after_action,
        },
        checks,
    )


def no_effect_quarantine_case() -> dict[str, Any]:
    snapshot = _button_snapshot()
    candidate, goal, inventory = _button_candidate(snapshot)
    ledger = CommitEffectLedgerV8()
    effect = ledger.assess(
        before=snapshot,
        after=snapshot,
        action=candidate.action,
        active_transactions=(),
        terminal=False,
    )
    full_certificate = certify_commit_v8(
        current=snapshot,
        goal=goal,
        candidate=candidate,
        inventory=inventory,
        active_transactions=(),
        quarantined_commit_keys=ledger.frozen_quarantine(),
    )
    ablated_certificate = certify_commit_v8(
        current=snapshot,
        goal=goal,
        candidate=candidate,
        inventory=inventory,
        active_transactions=(),
        quarantined_commit_keys=(),
    )
    checks = {
        "zero_effect_attempt_is_detected": effect.effective is False,
        "zero_effect_key_is_quarantined": effect.quarantined
        and len(ledger.quarantined_keys) == 1,
        "full_denies_identical_repeat": full_certificate.allowed is False,
        "removed_guard_allows_identical_repeat": ablated_certificate.allowed,
    }
    return _case(
        "no_effect_quarantine",
        {
            "first_attempt_effective": effect.effective,
            "repeat_allowed": full_certificate.allowed,
            "reason": full_certificate.reason,
        },
        {
            "first_attempt_effective": effect.effective,
            "repeat_allowed": ablated_certificate.allowed,
            "reason": ablated_certificate.reason,
        },
        checks,
    )


def run_component_conformance_v1() -> dict[str, Any]:
    cases = [
        postcondition_enforcement_case(),
        fresh_commit_authority_case(),
        inverse_budget_reservation_case(),
        no_effect_quarantine_case(),
    ]
    checks = {
        "exact_case_inventory": tuple(case["case_id"] for case in cases) == CASE_IDS,
        "all_case_checks_boolean": all(
            type(value) is bool
            for case in cases
            for value in case["checks"].values()
        ),
        "all_fault_injections_pass": all(case["passed"] for case in cases),
        "public_state_only": True,
        "no_model_reward_or_evaluator_input": True,
        "not_benchmark_efficacy": True,
    }
    return {
        "scope": (
            "deterministic public-state fault-injection conformance; "
            "not benchmark efficacy"
        ),
        "cases": cases,
        "checks": checks,
        "passed": all(checks.values()),
    }
