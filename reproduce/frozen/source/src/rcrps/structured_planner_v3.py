"""Goal-conditioned public action inventory for successor PACT contracts.

The immutable C428 planner inventory represents only argument-free contracts.
This successor layer derives a bounded public query from the instruction,
recompiles parameterized contracts, and exposes their preview kind without
placing task IDs, evaluator fields, or hidden answers in the model interface.
"""

from __future__ import annotations

from dataclasses import dataclass

from .pact_grounding_v3 import (
    ConstraintCompilation,
    TargetConstraint,
    compile_target_constraint,
    exploration_query,
)
from .structured_planner import ActionCandidate, action_candidates
from .typed_contracts_v3 import infer_sequence_contract
from .typed_observation import SemanticSnapshot


@dataclass(frozen=True)
class SuccessorActionInventory:
    allowed: bool
    reason: str
    constraint: TargetConstraint | None
    query: str | None
    candidates: tuple[ActionCandidate, ...]

    def constraint_record(self) -> dict[str, str | None] | None:
        return self.constraint.record() if self.constraint is not None else None


def _recompile_candidate(
    snapshot: SemanticSnapshot,
    candidate: ActionCandidate,
    *,
    query: str | None,
) -> ActionCandidate:
    decision = infer_sequence_contract(snapshot, candidate.bid, query=query)
    if not decision.allowed or decision.contract is None:
        return candidate
    contract = decision.contract
    if contract.action.bid != candidate.bid:
        raise ValueError("sequence contract action BID differs from inventory BID")
    semantic = snapshot.get(contract.semantic_bid)
    if semantic is None:
        raise ValueError("sequence contract semantic target is absent")
    return ActionCandidate(
        bid=candidate.bid,
        operation=contract.action.operation,
        role=semantic.role or candidate.role,
        label=candidate.label,
        state=candidate.state,
        preview_kind=contract.kind,
        semantic_bid=contract.semantic_bid,
        parent_bid=semantic.ax_parent_bid or semantic.dom_parent_bid,
    )


def successor_action_inventory(
    snapshot: SemanticSnapshot,
    goal: str,
) -> SuccessorActionInventory:
    """Expose v3 exploration only after a positive goal constraint compiles."""

    compilation: ConstraintCompilation = compile_target_constraint(goal)
    if not compilation.allowed or compilation.constraint is None:
        return SuccessorActionInventory(
            False,
            compilation.reason,
            None,
            None,
            (),
        )
    query = exploration_query(compilation.constraint)
    base = action_candidates(snapshot)
    candidates = tuple(
        _recompile_candidate(snapshot, candidate, query=query)
        for candidate in base
    )
    typed_count = sum(row.preview_kind is not None for row in candidates)
    return SuccessorActionInventory(
        True,
        f"positive target constraint exposed {typed_count} typed explorations",
        compilation.constraint,
        query,
        candidates,
    )
