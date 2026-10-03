"""Typed sequence execution state and outcomes, separate from the controller policy."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from inversereserve.contracts.pact_grounding_v3 import ConstraintCertificate
from inversereserve.contracts.transaction_actions import ActionSequenceContract, ContractAction
from inversereserve.observations.typed_observation import ContractCheck, SemanticDelta, SemanticSnapshot


@dataclass(frozen=True)
class ActionExecution:
    """Public result returned by an injected GUI-action executor."""

    snapshot: SemanticSnapshot
    terminated: bool = False
    truncated: bool = False
    action_error: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.snapshot, SemanticSnapshot):
            raise ValueError("action execution requires a semantic snapshot")
        if not isinstance(self.terminated, bool) or not isinstance(self.truncated, bool):
            raise ValueError("terminal flags must be Boolean")
        if not isinstance(self.action_error, str):
            raise ValueError("action_error must be text")

    @property
    def terminal(self) -> bool:
        return self.terminated or self.truncated


@dataclass(frozen=True)
class ActiveSequenceTransaction:
    contract: ActionSequenceContract
    candidate_label: str
    before: SemanticSnapshot
    after: SemanticSnapshot
    delta: SemanticDelta

    def planner_record(self) -> dict[str, object]:
        return {
            "bid": self.contract.action.bid,
            "label": self.candidate_label,
            "preview_kind": self.contract.kind,
            "semantic_bid": self.contract.semantic_bid,
        }

    def completed_record(self, *, target_found: bool) -> dict[str, object]:
        return {**self.planner_record(), "target_found": bool(target_found)}


@dataclass(frozen=True)
class RestorationOutcome:
    attempted: bool
    passed: bool
    reason: str
    check: ContractCheck | None
    final_snapshot: SemanticSnapshot | None


@dataclass(frozen=True)
class ExplorationOutcome:
    admitted: bool
    reason: str
    postcondition: ContractCheck | None
    restoration: RestorationOutcome | None
    halted: bool


@dataclass(frozen=True)
class CommitCertificate:
    allowed: bool
    reason: str
    grounding: ConstraintCertificate
    supporting_transaction_depth: int | None
    competing_bids: tuple[str, ...] = ()
    certified_bid: str | None = None
    certified_operation: str | None = None
    observation_fingerprint: tuple[tuple[object, ...], ...] = ()
    active_stack_signature: tuple[tuple[str, str, str | None], ...] = ()


@dataclass(frozen=True)
class CommitOutcome:
    executed: bool
    reason: str
    result: ActionExecution | None
    halted: bool


class RuntimeHalted(RuntimeError):
    """Raised when code attempts another action after a fail-closed event."""


ActionExecutor = Callable[[ContractAction, str], ActionExecution]
