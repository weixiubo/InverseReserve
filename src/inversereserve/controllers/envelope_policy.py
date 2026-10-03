"""Shared model arbitration and typed admission phases for matched drivers."""

from __future__ import annotations

from typing import Any, Protocol

from inversereserve.contracts.action_envelope_v7 import (
    ActionEnvelopeV7,
    EnvelopeResolutionV7,
    envelope_messages_v7,
    resolve_action_envelope_v7,
)
from inversereserve.contracts.goal_contracts_v4 import StructuredGoalContract
from inversereserve.controllers.pact_controller_v4 import FailClosedTransactionRuntimeV4
from inversereserve.models.structured_planner_v4 import ActionCandidateV4, V4ActionInventory
from inversereserve.observations.typed_observation import SemanticSnapshot


class EnvelopeDriver(Protocol):
    goal: str
    goal_contract: StructuredGoalContract
    runtime: FailClosedTransactionRuntimeV4
    executor: Any
    parse_failures: int
    typed_transactions: int
    terminal_transactions: int
    method_failure: str | None

    def call_model(self, messages: list[dict[str, str]]) -> dict[str, Any] | None: ...
    def audit(self, record: dict[str, Any]) -> None: ...


def resolve_step(
    driver: EnvelopeDriver, envelope: ActionEnvelopeV7, step: dict[str, Any]
) -> EnvelopeResolutionV7 | None:
    """Record one arbitration; stop before execution on missing/invalid model output."""
    if envelope.decision == "abstain" or not envelope.model_call_required:
        resolution = resolve_action_envelope_v7(envelope)
    else:
        messages = envelope_messages_v7(
            goal=driver.goal,
            goal_contract=driver.goal_contract,
            envelope=envelope,
            active_transactions=[row.planner_record() for row in driver.runtime.active],
            completed_transactions=driver.runtime.completed,
        )
        model = driver.call_model(messages)
        if model is None:
            driver.audit(step)
            return None
        step["model"] = model
        try:
            resolution = resolve_action_envelope_v7(envelope, model_output=model["raw_output"])
        except Exception as error:
            driver.parse_failures += 1
            driver.method_failure = f"planner parse failed: {type(error).__name__}: {error}"
            driver.audit(step)
            return None
    step["resolution"] = {"decision": resolution.decision, "bid": resolution.bid, "source": resolution.source}
    driver.audit(step)
    return resolution


def admit_transaction(
    driver: EnvelopeDriver,
    inventory: V4ActionInventory,
    current: SemanticSnapshot,
    candidate: ActionCandidateV4,
    event_type: str,
) -> bool:
    """Execute one admitted transaction and account for its fail-closed outcome."""
    contract = inventory.contract_by_bid.get(candidate.bid)
    if contract is None:
        driver.method_failure = "typed envelope row lacked a transaction contract"
        return False
    outcome = driver.runtime.transact(before=current, contract=contract, candidate_label=candidate.label)
    driver.typed_transactions += 1
    driver.audit(
        {
            "type": event_type,
            "bid": candidate.bid,
            "admitted": outcome.admitted,
            "reason": outcome.reason,
            "interrupt_repairs": outcome.interrupt_repairs,
            "halted": outcome.halted,
        }
    )
    if not outcome.admitted or outcome.halted:
        driver.terminal_transactions += int(driver.executor.done)
        driver.method_failure = outcome.reason
        return False
    return True
