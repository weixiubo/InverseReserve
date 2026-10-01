"""Deterministic PACT-v13 conformance, including terminal-state freshness."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from . import component_conformance_v1 as v1
from . import component_conformance_v2 as v2
from .pact_controller_v12 import (
    FailClosedTransactionRuntimeV12,
    complete_public_fingerprint_v12,
)
from .pact_controller_v13 import (
    FailClosedTransactionRuntimeV13,
    bind_complete_public_commit_certificate_v13,
)
from .pact_grounding_v4 import certify_commit_v4, verify_commit_grounding_v4
from .structured_planner_v4 import compile_v4_inventory
from .typed_observation import SemanticElement, SemanticSnapshot


CASE_IDS_V3 = v2.CASE_IDS_V2 + ("complete_public_commit_guard",)


def _element(
    bid: str,
    role: str,
    name: str,
    tag: str,
    attributes: dict[str, str],
    *,
    clickable: bool = False,
) -> SemanticElement:
    return SemanticElement(
        bid=bid,
        role=role,
        name=name,
        subtree_text=name,
        ax_properties=(),
        ax_parent_bid=None,
        dom_tag=tag,
        dom_attributes=tuple(sorted(attributes.items())),
        dom_parent_bid=None,
        visible=True,
        clickable=clickable,
        bbox=(0.0, 0.0, 10.0, 10.0),
    )


def _date_form() -> SemanticSnapshot:
    return SemanticSnapshot(
        (
            _element(
                "date",
                "textbox",
                "Date",
                "input",
                {"class": "hasDatepicker", "value": "10/27/2016"},
            ),
            _element(
                "submit", "button", "Submit", "button", {}, clickable=True
            ),
        )
    )


def complete_public_commit_guard_case_v3() -> dict[str, Any]:
    before = _date_form()
    inventory = compile_v4_inventory(
        before,
        "Select 10/27/2016 and press submit.",
    )
    candidate = next(row for row in inventory.candidates if row.bid == "submit")
    projected = certify_commit_v4(
        current=before,
        goal=inventory.goal_contract,
        candidate=candidate,
        inventory=inventory.candidates,
        active_transactions=(),
    )
    if not projected.allowed:
        raise RuntimeError("terminal conformance fixture was not certified")
    certificate = bind_complete_public_commit_certificate_v13(before, projected)
    if not certificate.allowed:
        raise RuntimeError("terminal conformance fixture lost its v13 binding")

    date = before.get("date")
    submit = before.get("submit")
    if date is None or submit is None:
        raise RuntimeError("terminal conformance fixture lost a public element")
    current = SemanticSnapshot(
        (
            replace(date, dom_attributes=(("value", "10/27/2016"),)),
            submit,
        )
    )
    grounding = verify_commit_grounding_v4(
        current=current,
        goal=inventory.goal_contract,
        candidate=candidate,
        inventory=inventory.candidates,
        active_transactions=(),
    )

    v13_executor = v1._CountingExecutor(current)
    v13_runtime = FailClosedTransactionRuntimeV13(
        v13_executor,
        v2._unused_interrupt_reservation,
    )
    v13_outcome = v13_runtime.commit(
        current=current,
        action=candidate.action,
        certificate=certificate,
    )
    v12_executor = v1._CountingExecutor(current)
    v12_runtime = FailClosedTransactionRuntimeV12(
        v12_executor,
        v2._unused_interrupt_reservation,
    )
    v12_outcome = v12_runtime.commit(
        current=current,
        action=candidate.action,
        certificate=projected,
    )
    v13_checks = [
        event
        for event in v13_runtime.events
        if event.get("type")
        == "complete_public_commit_observation_check_v13"
    ]
    checks = {
        "mutation_is_real": before != current,
        "projected_fingerprint_misses_grounding_change": (
            before.semantic_fingerprint() == current.semantic_fingerprint()
        ),
        "complete_record_detects_grounding_change": (
            complete_public_fingerprint_v12(before)
            != complete_public_fingerprint_v12(current)
        ),
        "fresh_grounding_recheck_rejects": grounding.allowed is False,
        "v13_rejects_before_executor": (
            not v13_outcome.executed and len(v13_executor.calls) == 0
        ),
        "v13_records_failed_complete_public_check": (
            len(v13_checks) == 1 and v13_checks[0].get("passed") is False
        ),
        "projected_counterfactual_reaches_executor": (
            v12_outcome.executed
            and len(v12_executor.calls) == 1
            and v12_executor.calls[0]["role"] == "commit"
        ),
    }
    return {
        "case_id": "complete_public_commit_guard",
        "full_pact": {
            "projected_fingerprints_equal": (
                before.semantic_fingerprint() == current.semantic_fingerprint()
            ),
            "complete_records_equal": (
                complete_public_fingerprint_v12(before)
                == complete_public_fingerprint_v12(current)
            ),
            "fresh_grounding_allowed": grounding.allowed,
            "executed": v13_outcome.executed,
            "executor_calls": len(v13_executor.calls),
        },
        "guard_removed": {
            "runtime": "v12_projected_commit_counterfactual",
            "executed": v12_outcome.executed,
            "executor_calls": len(v12_executor.calls),
            "role": v12_executor.calls[0]["role"],
        },
        "checks": checks,
        "passed": all(checks.values()),
    }


def run_component_conformance_v3() -> dict[str, Any]:
    inherited = v2.run_component_conformance_v2()
    terminal = complete_public_commit_guard_case_v3()
    cases = [*inherited["cases"], terminal]
    checks = {
        "exact_case_inventory": tuple(case["case_id"] for case in cases)
        == CASE_IDS_V3,
        "all_case_checks_boolean": all(
            type(value) is bool
            for case in cases
            for value in case["checks"].values()
        ),
        "all_fault_injections_pass": all(case["passed"] for case in cases),
        "inherits_complete_public_no_effect_guard": inherited["passed"] is True,
        "runtime_terminal_guard_is_pact_v13": terminal["passed"] is True,
        "complete_public_terminal_counterexample_is_explicit": (
            terminal["full_pact"]["projected_fingerprints_equal"] is True
            and terminal["full_pact"]["complete_records_equal"] is False
            and terminal["full_pact"]["fresh_grounding_allowed"] is False
        ),
        "public_state_only": True,
        "no_model_reward_or_evaluator_input": True,
        "not_benchmark_efficacy": True,
    }
    return {
        "scope": (
            "deterministic PACT-v13 public-state fault-injection conformance; "
            "not benchmark efficacy"
        ),
        "cases": cases,
        "checks": checks,
        "passed": all(checks.values()),
    }
