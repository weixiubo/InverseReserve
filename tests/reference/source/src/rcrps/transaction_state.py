from __future__ import annotations
from dataclasses import dataclass
from .typed_contracts_v4 import TransactionContractV4
from .typed_observation import ContractCheck, SemanticDelta, SemanticSnapshot


@dataclass(frozen=True)
class ActionExecutionV4:
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
class ActiveTransactionV4:
    contract: TransactionContractV4
    candidate_label: str
    before: SemanticSnapshot
    after: SemanticSnapshot
    delta: SemanticDelta
    interrupt_repairs: int = 0

    def planner_record(self) -> dict[str, object]:
        argument = self.contract.action.argument
        if isinstance(argument, tuple):
            argument = list(argument)
        return {
            "bid": self.contract.action.bid,
            "label": self.candidate_label,
            "transaction_kind": self.contract.kind,
            "semantic_bid": self.contract.semantic_bid,
            "operation": self.contract.action.operation,
            "argument": argument,
            "interrupt_repairs": self.interrupt_repairs,
        }

@dataclass(frozen=True)
class RestorationOutcomeV4:
    attempted: bool
    passed: bool
    reason: str
    check: ContractCheck | None
    final_snapshot: SemanticSnapshot | None

@dataclass(frozen=True)
class TransactionOutcomeV4:
    admitted: bool
    reason: str
    postcondition: ContractCheck | None
    restoration: RestorationOutcomeV4 | None
    interrupt_repairs: int
    halted: bool

@dataclass(frozen=True)
class CommitOutcomeV4:
    executed: bool
    reason: str
    result: ActionExecutionV4 | None
    halted: bool
