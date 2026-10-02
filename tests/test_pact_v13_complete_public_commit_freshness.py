from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from inversereserve.adapters.webarena.webarena_exact_mutation_agent_v13 import ExactMutationTransferAgentV13
from inversereserve.contracts.pact_grounding_v4 import certify_commit_v4, verify_commit_grounding_v4
from inversereserve.controllers.confirmation_ablation_agents_v13 import MATCHED_CONFIRMATION_DRIVERS_V13
from inversereserve.controllers.confirmation_agents_v13 import FullPactConfirmationDriverV13
from inversereserve.controllers.pact_controller_v4 import ActionExecutionV4
from inversereserve.controllers.pact_controller_v13 import (
    FailClosedTransactionRuntimeV13,
    bind_complete_public_commit_certificate_v13,
)
from inversereserve.models.structured_planner_v4 import compile_v4_inventory
from inversereserve.observations.typed_observation import SemanticElement, SemanticSnapshot

from .test_pact_v11_no_effect_inverse_guard import forbidden_reservation
from .test_webarena_exact_mutation_agent_v1 import BUDGETS, QueueEnvironment, exact_form, forbidden_model

ROOT = Path(__file__).resolve().parents[1]


def element(
    bid: str, role: str, name: str, tag: str, attributes: dict[str, str], *, clickable: bool = False
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


def date_form() -> SemanticSnapshot:
    return SemanticSnapshot(
        (
            element("date", "textbox", "Date", "input", {"class": "hasDatepicker", "value": "10/27/2016"}),
            element("submit", "button", "Submit", "button", {}, clickable=True),
        )
    )


def certificate_fixture():
    before = date_form()
    inventory = compile_v4_inventory(before, "Select 10/27/2016 and press submit.")
    candidate = next((row for row in inventory.candidates if row.bid == "submit"))
    projected = certify_commit_v4(
        current=before,
        goal=inventory.goal_contract,
        candidate=candidate,
        inventory=inventory.candidates,
        active_transactions=(),
    )
    assert projected.allowed
    certificate = bind_complete_public_commit_certificate_v13(before, projected)
    assert certificate.allowed
    return (before, inventory, candidate, certificate)


def test_v13_rejects_a_commit_after_omitted_grounding_metadata_changes() -> None:
    before, inventory, candidate, certificate = certificate_fixture()
    date = before.get("date")
    submit = before.get("submit")
    assert date is not None and submit is not None
    current = SemanticSnapshot((replace(date, dom_attributes=(("value", "10/27/2016"),)), submit))
    assert before != current
    assert before.semantic_fingerprint() == current.semantic_fingerprint()
    grounding = verify_commit_grounding_v4(
        current=current,
        goal=inventory.goal_contract,
        candidate=candidate,
        inventory=inventory.candidates,
        active_transactions=(),
    )
    assert not grounding.allowed
    calls = []

    def forbidden_executor(_action, _role: str):
        calls.append((_action, _role))
        raise AssertionError("stale complete-public certificate reached executor")

    runtime = FailClosedTransactionRuntimeV13(forbidden_executor, forbidden_reservation)
    outcome = runtime.commit(current=current, action=candidate.action, certificate=certificate)
    assert not outcome.executed and (not outcome.halted)
    assert not calls
    check = next(
        (event for event in runtime.events if event["type"] == "complete_public_commit_observation_check_v13")
    )
    assert check["passed"] is False


def test_v13_executes_the_exact_action_when_the_complete_binding_is_fresh() -> None:
    before, _inventory, candidate, certificate = certificate_fixture()
    calls = []

    def executor(action, role: str) -> ActionExecutionV4:
        calls.append((action, role))
        return ActionExecutionV4(before, terminated=True)

    runtime = FailClosedTransactionRuntimeV13(executor, forbidden_reservation)
    outcome = runtime.commit(current=before, action=candidate.action, certificate=certificate)
    assert outcome.executed and (not outcome.halted)
    assert calls == [(candidate.action, "commit")]
    check = next(
        (event for event in runtime.events if event["type"] == "complete_public_commit_observation_check_v13")
    )
    assert check["passed"] is True


def test_v13_certificate_binding_fails_closed_on_ambiguous_public_identity() -> None:
    before, _inventory, _candidate, certificate = certificate_fixture()
    duplicate = SemanticSnapshot(before.elements + (before.elements[0],))
    rejected = bind_complete_public_commit_certificate_v13(duplicate, certificate)
    assert not rejected.allowed
    assert rejected.certified_action is None
    assert "unique BIDs" in rejected.reason


def test_v13_final_driver_surfaces_are_versioned_and_use_the_binding_hook() -> None:
    assert set(MATCHED_CONFIRMATION_DRIVERS_V13) == {
        "raw_open_loop_v13_matched",
        "typed_no_certificate_v13",
        "full_pact_v13",
    }
    assert MATCHED_CONFIRMATION_DRIVERS_V13["full_pact_v13"] is FullPactConfirmationDriverV13
    before, _inventory, _candidate, projected = certificate_fixture()
    assert ExactMutationTransferAgentV13.method_id == "full_pact_v13_webarena_exact_mutation_v2"
    assert projected.allowed
    assert projected.observation_fingerprint != before.semantic_fingerprint()


def test_v13_webarena_path_executes_with_one_complete_public_commit_check() -> None:
    environment = QueueEnvironment([exact_form(value="hello"), exact_form(value="hello", saved=True)])
    agent = ExactMutationTransferAgentV13(
        environment=environment,
        observation=exact_form(value="prior"),
        budgets=BUDGETS,
        planner_generate=forbidden_model,
    )
    agent.run()
    result = agent.result()
    assert result["method_commit_effective"] is True
    assert result["method_failure"] is None
    assert result["metrics"]["complete_public_commit_checks_v13"] == 1
    assert result["metrics"]["complete_public_commit_passes_v13"] == 1
    assert result["metrics"]["complete_public_commit_rejections_v13"] == 0
    assert any((event.get("type") == "exact_mutation_commit_certificate_v13" for event in result["trace"]))
