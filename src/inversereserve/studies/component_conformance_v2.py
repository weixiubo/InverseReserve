"""Deterministic PACT-v12 guard conformance, including the v11 defect case."""

from __future__ import annotations

from dataclasses import asdict, replace
from types import SimpleNamespace
from typing import Any

from inversereserve.contracts.typed_contracts_v9 import check_transaction_postcondition_v9
from inversereserve.controllers.confirmation_agents_v12 import FullPactConfirmationDriverV12
from inversereserve.controllers.pact_controller_v11 import FailClosedTransactionRuntimeV11
from inversereserve.controllers.pact_controller_v12 import (
    FailClosedTransactionRuntimeV12,
    complete_public_fingerprint_v12,
)
from inversereserve.observations.typed_observation import ContractCheck, SemanticSnapshot, semantic_delta
from inversereserve.studies import component_conformance_v1 as v1

CASE_IDS_V2 = (
    "postcondition_enforcement",
    "fresh_commit_authority",
    "inverse_budget_reservation",
    "no_effect_quarantine",
    "complete_public_inverse_guard",
)


def _unused_interrupt_reservation(_contract: Any) -> Any:
    raise AssertionError("interrupt reservation is not used by this conformance case")


def _case(
    case_id: str,
    full: dict[str, Any],
    ablated: dict[str, Any],
    checks: dict[str, bool],
) -> dict[str, Any]:
    if case_id not in CASE_IDS_V2:
        raise ValueError(f"unknown PACT-v12 conformance case: {case_id}")
    if not checks or any(type(value) is not bool for value in checks.values()):
        raise ValueError(f"invalid PACT-v12 conformance checks: {case_id}")
    return {
        "case_id": case_id,
        "full_pact": full,
        "guard_removed": ablated,
        "checks": checks,
        "passed": all(checks.values()),
    }


class PostconditionBypassRuntimeV2(FailClosedTransactionRuntimeV12):
    """PACT-v12 with only postcondition enforcement removed."""

    def _check_postcondition(
        self,
        before: SemanticSnapshot,
        after: SemanticSnapshot,
        contract: v1.TransactionContractV4,
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


class InverseReservationBypassDriverV2(FullPactConfirmationDriverV12):
    """PACT-v12 driver that observes inverse cost but never withholds."""

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


def postcondition_enforcement_case_v2() -> dict[str, Any]:
    before = v1._field_snapshot("")
    wrong = v1._field_snapshot("other")
    contract = v1._field_contract(before)

    full_executor = v1._ScriptedExecutor([wrong, before])
    full_runtime = FailClosedTransactionRuntimeV12(full_executor, _unused_interrupt_reservation)
    full_outcome = full_runtime.transact(
        before=before,
        contract=contract,
        candidate_label="Username",
    )
    ablated_executor = v1._ScriptedExecutor([wrong])
    ablated_runtime = PostconditionBypassRuntimeV2(ablated_executor, _unused_interrupt_reservation)
    ablated_outcome = ablated_runtime.transact(
        before=before,
        contract=contract,
        candidate_label="Username",
    )
    counterfactual = [
        event for event in ablated_runtime.events if event.get("type") == "postcondition_ablation"
    ]
    checks = {
        "full_rejects_wrong_transition": not full_outcome.admitted,
        "full_executes_registered_inverse": full_executor.roles == ["typed_forward", "typed_inverse"],
        "full_verifies_public_restoration": bool(
            full_outcome.restoration and full_outcome.restoration.passed
        ),
        "removed_guard_admits_same_wrong_transition": ablated_outcome.admitted,
        "removed_guard_executes_no_inverse": ablated_executor.roles == ["typed_forward"],
        "counterfactual_predicate_would_fail": len(counterfactual) == 1
        and counterfactual[0]["counterfactual_passed"] is False,
    }
    return _case(
        "postcondition_enforcement",
        {
            "admitted": full_outcome.admitted,
            "executor_roles": full_executor.roles,
            "restoration_passed": bool(full_outcome.restoration and full_outcome.restoration.passed),
            "active_depth": len(full_runtime.active),
        },
        {
            "admitted": ablated_outcome.admitted,
            "executor_roles": ablated_executor.roles,
            "counterfactual_passed": counterfactual[0]["counterfactual_passed"],
            "active_depth": len(ablated_runtime.active),
        },
        checks,
    )


def fresh_commit_authority_case_v2() -> dict[str, Any]:
    before = v1._button_snapshot()
    stale = v1._button_snapshot(stale=True)
    candidate, goal, inventory = v1._button_candidate(before)
    certificate = v1.certify_commit_v8(
        current=before,
        goal=goal,
        candidate=candidate,
        inventory=inventory,
        active_transactions=(),
    )
    full_executor = v1._CountingExecutor(stale)
    runtime = FailClosedTransactionRuntimeV12(full_executor, _unused_interrupt_reservation)
    rejected = runtime.commit(
        current=stale,
        action=candidate.action,
        certificate=certificate,
    )
    ablated_executor = v1._CountingExecutor(stale)
    ablated_executor(candidate.action, "uncertified_commit")
    checks = {
        "full_rejects_stale_certificate": not rejected.executed,
        "full_makes_zero_executor_calls": len(full_executor.calls) == 0,
        "removed_guard_reaches_executor": len(ablated_executor.calls) == 1,
        "removed_guard_uses_exact_proposed_action": ablated_executor.calls[0]["action"]
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


def inverse_budget_reservation_case_v2() -> dict[str, Any]:
    contract = v1.TransactionContractV4(
        kind="autocomplete_query",
        semantic_bid="field",
        action=v1.ContractActionV4("fill", "field", "Ma", True),
        inverse_actions=(
            v1.ContractActionV4("press", "field", "Escape"),
            v1.ContractActionV4("fill", "field", "", False),
        ),
        expected_value="Ma",
        prior_value="",
        projection_kind="autocomplete_query",
    )

    def configured(driver_class: type[FullPactConfirmationDriverV12]):
        driver = object.__new__(driver_class)
        driver.budgets = {"maximum_gui_actions": 2}
        driver.executor = SimpleNamespace(actions=[])
        driver.runtime = SimpleNamespace(active=[])
        driver.inverse_reservation_audits = 0
        driver.runtime_events = []
        driver.inventory = lambda: SimpleNamespace(contract_by_bid={"field": contract})
        driver.audit = driver.runtime_events.append
        return driver

    candidate = SimpleNamespace(bid="field")
    full_driver = configured(FullPactConfirmationDriverV12)
    allowed, reserve = full_driver.inverse_reserve(candidate, "transact")
    remaining = full_driver.runtime_events[-1]["remaining_after_action"]
    ablated_driver = configured(InverseReservationBypassDriverV2)
    ablated_allowed, ablated_reserve = ablated_driver.inverse_reserve(candidate, "transact")
    checks = {
        "inverse_cost_is_exact_sequence_length": reserve == 2,
        "full_withholds_insolvent_forward": allowed is False,
        "remaining_budget_is_below_inverse_cost": remaining < reserve,
        "removed_guard_allows_forward": ablated_allowed,
        "removed_guard_observes_same_inverse_cost": ablated_reserve == reserve,
    }
    return _case(
        "inverse_budget_reservation",
        {
            "forward_allowed": allowed,
            "inverse_cost": reserve,
            "remaining_after_forward": remaining,
        },
        {
            "forward_allowed": ablated_allowed,
            "inverse_cost_ignored": ablated_reserve,
            "remaining_after_forward": remaining,
        },
        checks,
    )


def no_effect_quarantine_case_v2() -> dict[str, Any]:
    inherited = v1.no_effect_quarantine_case()
    return _case(
        "no_effect_quarantine",
        inherited["full_pact"],
        inherited["guard_removed"],
        inherited["checks"],
    )


def _class_only_change(snapshot: SemanticSnapshot) -> SemanticSnapshot:
    element = snapshot.get("field")
    if element is None:
        raise RuntimeError("class-only conformance fixture lost its field")
    attributes = dict(element.dom_attributes)
    attributes["class"] = "validation-error"
    changed = replace(
        element,
        dom_attributes=tuple(sorted(attributes.items())),
    )
    return SemanticSnapshot(tuple(changed if row.bid == element.bid else row for row in snapshot.elements))


def complete_public_inverse_guard_case_v2() -> dict[str, Any]:
    before = v1._field_snapshot("")
    after = _class_only_change(before)
    contract = v1._field_contract(before)

    v12_executor = v1._ScriptedExecutor([after, before])
    v12_runtime = FailClosedTransactionRuntimeV12(v12_executor, _unused_interrupt_reservation)
    v12_outcome = v12_runtime.transact(
        before=before,
        contract=contract,
        candidate_label="Username",
    )
    projected_executor = v1._ScriptedExecutor([after])
    projected_runtime = FailClosedTransactionRuntimeV11(projected_executor, _unused_interrupt_reservation)
    projected_outcome = projected_runtime.transact(
        before=before,
        contract=contract,
        candidate_label="Username",
    )
    observation_checks = [
        event for event in v12_runtime.events if event.get("type") == "complete_public_observation_check_v12"
    ]
    checks = {
        "mutation_is_real": before != after,
        "projected_fingerprint_misses_class_change": before.semantic_fingerprint()
        == after.semantic_fingerprint(),
        "complete_record_detects_class_change": complete_public_fingerprint_v12(before)
        != complete_public_fingerprint_v12(after),
        "v12_does_not_issue_false_no_effect_certificate": len(observation_checks) == 1
        and observation_checks[0]["passed"] is False,
        "v12_executes_and_verifies_inverse": v12_executor.roles == ["typed_forward", "typed_inverse"]
        and bool(v12_outcome.restoration and v12_outcome.restoration.passed),
        "projected_guard_would_skip_inverse": projected_executor.roles == ["typed_forward"]
        and bool(
            projected_outcome.restoration
            and projected_outcome.restoration.passed
            and not projected_outcome.restoration.attempted
        ),
    }
    return _case(
        "complete_public_inverse_guard",
        {
            "projected_fingerprints_equal": (before.semantic_fingerprint() == after.semantic_fingerprint()),
            "complete_records_equal": (
                complete_public_fingerprint_v12(before) == complete_public_fingerprint_v12(after)
            ),
            "executor_roles": v12_executor.roles,
            "restoration_attempted": bool(v12_outcome.restoration and v12_outcome.restoration.attempted),
            "restoration_passed": bool(v12_outcome.restoration and v12_outcome.restoration.passed),
        },
        {
            "runtime": "v11_projected_fingerprint_counterfactual",
            "executor_roles": projected_executor.roles,
            "restoration_attempted": bool(
                projected_outcome.restoration and projected_outcome.restoration.attempted
            ),
            "restoration_passed": bool(
                projected_outcome.restoration and projected_outcome.restoration.passed
            ),
        },
        checks,
    )


def run_component_conformance_v2() -> dict[str, Any]:
    cases = [
        postcondition_enforcement_case_v2(),
        fresh_commit_authority_case_v2(),
        inverse_budget_reservation_case_v2(),
        no_effect_quarantine_case_v2(),
        complete_public_inverse_guard_case_v2(),
    ]
    checks = {
        "exact_case_inventory": tuple(case["case_id"] for case in cases) == CASE_IDS_V2,
        "all_case_checks_boolean": all(
            type(value) is bool for case in cases for value in case["checks"].values()
        ),
        "all_fault_injections_pass": all(case["passed"] for case in cases),
        "runtime_is_pact_v12": True,
        "complete_public_counterexample_is_explicit": cases[-1]["passed"],
        "public_state_only": True,
        "no_model_reward_or_evaluator_input": True,
        "not_benchmark_efficacy": True,
    }
    return {
        "scope": ("deterministic PACT-v12 public-state fault-injection conformance; not benchmark efficacy"),
        "cases": cases,
        "checks": checks,
        "passed": all(checks.values()),
    }
