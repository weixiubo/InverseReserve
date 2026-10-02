from __future__ import annotations

from pathlib import Path

from inversereserve.autocomplete_population_resolution_v14 import (
    certify_population_commit_v14,
    certify_population_probe_v14,
    inspect_autocomplete_population_v14,
)
from inversereserve.contracts.action_envelope_v7 import ActionEnvelopeV7
from inversereserve.controllers.confirmation_agents_v14 import FullPactConfirmationDriverV14
from inversereserve.controllers.pact_controller_v4 import ActiveTransactionV4
from inversereserve.controllers.pact_controller_v14 import FailClosedTransactionRuntimeV14
from inversereserve.observations.typed_observation import SemanticDelta

from .test_webarena_exact_mutation_agent_v1 import QueueEnvironment, forbidden_model, observation

ROOT = Path(__file__).resolve().parents[1]
GOAL = "Book the cheapest one-way flight from: CRW to: RAP on 12/04/2016."
BUDGETS = {
    "maximum_gui_actions": 12,
    "maximum_planner_calls": 12,
    "maximum_wall_seconds": 30.0,
    "maximum_navigation_candidates": 64,
}
SUGGESTIONS = (
    "Cedar Rapids, IA (CID)",
    "Grand Rapids, MI (GRR)",
    "Grand Rapids, MN (GPZ)",
    "Rapid City, SD (RAP)",
)


def form_nodes(*, to_value: str) -> list[dict]:
    return [
        {"bid": "form", "role": "form", "name": "From To Departure Date Search", "tag": "form"},
        {
            "bid": "from",
            "role": "textbox",
            "name": "From:",
            "tag": "input",
            "attributes": {"class": "ui-autocomplete-input", "value": "CRW"},
            "properties": {"readonly": False, "value": "CRW"},
            "parent": "form",
            "clickable": True,
        },
        {
            "bid": "to",
            "role": "textbox",
            "name": "To:",
            "tag": "input",
            "attributes": {"class": "ui-autocomplete-input", "value": to_value},
            "properties": {"readonly": False, "value": to_value},
            "parent": "form",
            "clickable": True,
        },
        {
            "bid": "date",
            "role": "textbox",
            "name": "Departure Date",
            "tag": "input",
            "attributes": {"class": "hasDatepicker", "readonly": "", "value": "12/04/2016"},
            "properties": {"readonly": True, "value": "12/04/2016"},
            "parent": "form",
            "clickable": True,
        },
        {
            "bid": "search",
            "role": "button",
            "name": "Search",
            "tag": "button",
            "parent": "form",
            "clickable": True,
        },
    ]


def flight_observation(
    *,
    to_value: str,
    selected_index: int | None = None,
    include_surface: bool = True,
    include_target_identity: bool = True,
) -> dict:
    nodes = form_nodes(to_value=to_value)
    if include_surface:
        nodes.append(
            {
                "bid": "menu",
                "role": "list",
                "name": " ".join(SUGGESTIONS),
                "tag": "ul",
                "attributes": {"class": "ui-autocomplete ui-menu"},
            }
        )
        for index, label in enumerate(SUGGESTIONS):
            if index == 3 and (not include_target_identity):
                continue
            classes = "ui-menu-item-wrapper"
            if selected_index == index:
                classes += " ui-state-active"
            nodes.append(
                {
                    "bid": f"item{index}",
                    "role": "listitem",
                    "name": label,
                    "tag": "li",
                    "attributes": {"class": "ui-menu-item"},
                    "parent": "menu",
                    "visible": index != 3,
                }
            )
            nodes.append(
                {
                    "bid": f"leaf{index}",
                    "role": "option",
                    "name": label,
                    "tag": "div",
                    "attributes": {"class": classes, "id": f"choice-{index}"},
                    "properties": {"selected": selected_index == index},
                    "parent": f"item{index}",
                    "visible": index != 3,
                    "clickable": index != 3,
                }
            )
    return observation(nodes, url="http://miniwob.local/book-flight-nodelay", goal=GOAL)


def driver_with_active_destination(outputs: list[dict]):
    initial = flight_observation(to_value="", include_surface=False)
    environment = QueueEnvironment(outputs)
    driver = FullPactConfirmationDriverV14(
        environment=environment, observation=initial, budgets=BUDGETS, planner_generate=forbidden_model
    )
    contract = driver.initial_inventory.contract_by_bid["to"]
    assert contract.kind == "autocomplete_query"
    assert contract.expected_value == "RAP"
    before = driver.executor.snapshot
    query = flight_observation(to_value="RAP")
    driver.executor.observation = query
    after = driver.executor.snapshot
    active = ActiveTransactionV4(
        contract=contract,
        candidate_label="To:",
        before=before,
        after=after,
        delta=SemanticDelta(
            ("menu", "item0", "leaf0", "item1", "leaf1", "item2", "leaf2", "item3", "leaf3"),
            (),
            ("to",),
            SUGGESTIONS,
        ),
    )
    driver.runtime.active.append(active)
    return (driver, environment, active)


def inspect(driver: FullPactConfirmationDriverV14):
    return inspect_autocomplete_population_v14(
        current=driver.executor.snapshot,
        goal=driver.goal_contract,
        active_transactions=tuple(driver.runtime.active),
        resolved_semantic_bids=tuple(driver.resolved_semantic_bids),
    )


def test_v14_inspects_a_unique_retained_non_actionable_target_identity() -> None:
    driver, _environment, _active = driver_with_active_destination([])
    result = inspect(driver)
    assert result.eligible
    assert result.field_bid == "to"
    assert result.surface_bid == "menu"
    assert result.target_bid == "item3"
    assert result.selected_bid is None
    assert len(result.items) == 4
    assert result.items[-1].label == "Rapid City, SD (RAP)"


def test_v14_rejects_aggregate_text_without_a_public_target_item_identity() -> None:
    driver, _environment, active = driver_with_active_destination([])
    driver.executor.observation = flight_observation(to_value="RAP", include_target_identity=False)
    active_without_target = ActiveTransactionV4(
        contract=active.contract,
        candidate_label=active.candidate_label,
        before=active.before,
        after=driver.executor.snapshot,
        delta=active.delta,
    )
    driver.runtime.active[:] = [active_without_target]
    result = inspect(driver)
    assert not result.eligible
    assert "absent or ambiguous" in result.reason


def test_v14_probe_runtime_rejects_a_stale_complete_public_certificate() -> None:
    driver, _environment, active = driver_with_active_destination([])
    inspection = inspect(driver)
    certificate = certify_population_probe_v14(
        current=driver.executor.snapshot, inspection=inspection, active_transactions=(active,)
    )
    assert certificate.allowed
    stale = flight_observation(to_value="RAP", selected_index=0)
    driver.executor.observation = stale
    calls = []

    def forbidden_executor(action, role):
        calls.append((action, role))
        raise AssertionError("stale probe reached executor")

    runtime = FailClosedTransactionRuntimeV14(forbidden_executor, lambda _contract: None)
    runtime.active.append(active)
    outcome = runtime.execute_population_probe(current=driver.executor.snapshot, certificate=certificate)
    assert not outcome.executed and (not outcome.halted)
    assert calls == []
    check = next(
        (event for event in runtime.events if event["type"] == "complete_public_population_probe_check_v14")
    )
    assert check["observation_matches"] is False


def test_v14_enter_certificate_requires_the_fresh_unique_target_selection() -> None:
    driver, _environment, active = driver_with_active_destination([])
    non_target = flight_observation(to_value="RAP", selected_index=0)
    driver.executor.observation = non_target
    non_target_inspection = inspect(driver)
    candidate, rejected = certify_population_commit_v14(
        current=driver.executor.snapshot, inspection=non_target_inspection, active_transactions=(active,)
    )
    assert candidate is None
    assert not rejected.allowed
    target = flight_observation(to_value="RAP", selected_index=3)
    driver.executor.observation = target
    target_inspection = inspect(driver)
    candidate, admitted = certify_population_commit_v14(
        current=driver.executor.snapshot, inspection=target_inspection, active_transactions=(active,)
    )
    assert candidate is not None
    assert candidate.action.browsergym_code() == "press('to', 'Enter')"
    assert admitted.allowed
    assert admitted.grounding.anchor_kind == "active_autocomplete_population_selection_v14"
    assert admitted.grounding.evidence_bids == ("to", "menu", "item3")


def test_v14_scans_by_fresh_selection_markers_then_commits_enter_once() -> None:
    outputs = [
        flight_observation(to_value="RAP", selected_index=0),
        flight_observation(to_value="RAP", selected_index=1),
        flight_observation(to_value="RAP", selected_index=2),
        flight_observation(to_value="RAP", selected_index=3),
        flight_observation(to_value="Rapid City, SD (RAP)", include_surface=False),
    ]
    driver, environment, _active = driver_with_active_destination(outputs)
    envelope = ActionEnvelopeV7("abstain", (), (), "active autocomplete overlay has no certified resolution")
    outcomes = []
    for _ in range(5):
        outcomes.append(
            driver.handle_abstained_envelope(
                current=driver.executor.snapshot, inventory=None, envelope=envelope, certificates={}
            )
        )
    assert outcomes == ["continue"] * 5
    assert environment.calls == [
        "press('to', 'ArrowDown')",
        "press('to', 'ArrowDown')",
        "press('to', 'ArrowDown')",
        "press('to', 'ArrowDown')",
        "press('to', 'Enter')",
    ]
    assert driver.method_failure is None
    assert driver.resolved_semantic_bids == {"to"}
    metrics = driver.result()["metrics"]
    assert metrics["population_navigation_eligibility_checks"] == 5
    assert metrics["population_navigation_activations"] == 1
    assert metrics["population_navigation_probes"] == 4
    assert metrics["population_navigation_fresh_selection_passes"] == 1
    assert metrics["population_navigation_fresh_selection_rejections"] == 0
    assert metrics["population_navigation_reservation_stops"] == 0
    assert metrics["population_navigation_commit_passes"] == 1
    assert metrics["population_navigation_commit_failures"] == 0
    assert metrics["population_navigation_restoration_passes"] == 0


def test_v14_missing_fresh_selection_marker_restores_instead_of_blind_scanning() -> None:
    outputs = [flight_observation(to_value="RAP", selected_index=None)]
    driver, environment, _active = driver_with_active_destination(outputs)
    envelope = ActionEnvelopeV7("abstain", (), (), "unresolved autocomplete")
    first = driver.handle_abstained_envelope(
        current=driver.executor.snapshot, inventory=None, envelope=envelope, certificates={}
    )
    assert first == "continue"
    environment.outputs.extend(
        [
            flight_observation(to_value="RAP", include_surface=False),
            flight_observation(to_value="", include_surface=False),
        ]
    )
    second = driver.handle_abstained_envelope(
        current=driver.executor.snapshot, inventory=None, envelope=envelope, certificates={}
    )
    assert second == "stop"
    assert "no unique fresh public selected-state marker" in driver.method_failure
    assert environment.calls == ["press('to', 'ArrowDown')", "press('to', 'Escape')", "fill('to', '', False)"]
    metrics = driver.result()["metrics"]
    assert metrics["population_navigation_probes"] == 1
    assert metrics["population_navigation_fresh_selection_rejections"] == 1
    assert metrics["population_navigation_restoration_passes"] == 1


def test_v14_reservation_stop_spends_only_the_preexisting_inverse() -> None:
    outputs = [
        flight_observation(to_value="RAP", include_surface=False),
        flight_observation(to_value="", include_surface=False),
    ]
    driver, environment, _active = driver_with_active_destination(outputs)
    driver.budgets["maximum_gui_actions"] = 2
    envelope = ActionEnvelopeV7("abstain", (), (), "unresolved autocomplete")
    outcome = driver.handle_abstained_envelope(
        current=driver.executor.snapshot, inventory=None, envelope=envelope, certificates={}
    )
    assert outcome == "stop"
    assert "consume the registered active inverse reserve" in driver.method_failure
    assert environment.calls == ["press('to', 'Escape')", "fill('to', '', False)"]
    metrics = driver.result()["metrics"]
    assert metrics["population_navigation_probes"] == 0
    assert metrics["population_navigation_reservation_stops"] == 1
    assert metrics["population_navigation_restoration_passes"] == 1


def test_v14_driver_is_a_versioned_v13_extension() -> None:
    assert FullPactConfirmationDriverV14.method_id == "full_pact_v14"
    assert FullPactConfirmationDriverV14.__mro__[1].__name__ == "FullPactConfirmationDriverV13"
