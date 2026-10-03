"""Static target-scope guard for the bounded WebArena reply adapter.

The v1 adapter intentionally parses the payload in several reply wordings, but
one visible textarea is insufficient evidence that a targeted comment reply
should use the page-level post form.  This guard admits only instructions that
explicitly name the current post as their reply target.  It consumes goal text
and a public semantic snapshot only; task IDs and evaluator data are absent.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from inversereserve.adapters.webarena.webarena_goal_adapter_v1 import (
    ReplyPayloadClauseV1,
    WebArenaGoalContractV1,
    certify_webarena_commit_v1,
    compile_webarena_goal_contract_v1,
    compile_webarena_inventory_v1,
    parse_reply_payload_v1,
)
from inversereserve.contracts.goal_contracts_v4 import GoalSpan, StructuredGoalContract
from inversereserve.contracts.pact_grounding_v4 import CommitCertificateV4, GroundingDecisionV4
from inversereserve.models.structured_planner_v4 import ActionCandidateV4, V4ActionInventory
from inversereserve.observations.typed_observation import SemanticSnapshot

DIRECT_CURRENT_POST_V2 = re.compile(
    r"^\s*(?:please\s+)?reply\s+to\s+"
    r"(?P<target>(?:the\s+post(?:\s+on\s+this\s+page)?|this\s+post))"
    r"\s+with\b",
    flags=re.IGNORECASE,
)


@dataclass(frozen=True)
class DirectReplyScopeDecisionV2:
    allowed: bool
    reason: str
    payload: ReplyPayloadClauseV1 | None
    target_span: GoalSpan | None

    def record(self) -> dict[str, object]:
        return {
            "allowed": self.allowed,
            "reason": self.reason,
            "target_span": (None if self.target_span is None else self.target_span.record()),
            "payload_parsed": self.payload is not None,
            "uses_task_id": False,
            "uses_evaluator": False,
            "uses_reward": False,
        }


@dataclass(frozen=True)
class WebArenaGoalCompilationV2:
    goal_contract: WebArenaGoalContractV1
    scope: DirectReplyScopeDecisionV2

    def record(self) -> dict[str, object]:
        value = self.goal_contract.record()
        value["webarena_direct_reply_scope_v2"] = self.scope.record()
        return value


def classify_direct_reply_scope_v2(goal: str) -> DirectReplyScopeDecisionV2:
    """Admit only an exact current-post target with one quoted reply payload."""

    text = str(goal).strip()
    payload = parse_reply_payload_v1(text)
    if payload is None:
        return DirectReplyScopeDecisionV2(
            False,
            "instruction exposes no direct current-post quoted reply payload",
            None,
            None,
        )
    match = DIRECT_CURRENT_POST_V2.match(text)
    if match is None:
        return DirectReplyScopeDecisionV2(
            False,
            "reply target is not an explicit current-post target",
            payload,
            None,
        )
    start, end = match.span("target")
    target = GoalSpan(text[start:end], start, end)
    return DirectReplyScopeDecisionV2(
        True,
        "instruction explicitly targets the current post",
        payload,
        target,
    )


def _rejected_contract(
    goal: str,
    scope: DirectReplyScopeDecisionV2,
) -> WebArenaGoalContractV1:
    text = str(goal).strip()
    base = StructuredGoalContract(
        goal=text,
        exact_constraint=None,
        field_assignments=(),
        date_anchor=None,
        option_selections=(),
        role_anchor=None,
        terminal_intent=None,
        objective_anchor=None,
        rejected_reasons=(scope.reason,),
    )
    return WebArenaGoalContractV1(
        base=base,
        reply_payload=scope.payload,
        payload_bindings=(),
        payload_resolution=scope.reason,
    )


def compile_webarena_goal_v2(
    goal: str,
    snapshot: SemanticSnapshot,
) -> WebArenaGoalCompilationV2:
    scope = classify_direct_reply_scope_v2(goal)
    if scope.allowed:
        contract = compile_webarena_goal_contract_v1(goal, snapshot)
    else:
        contract = _rejected_contract(goal, scope)
    contract.validate_provenance()
    return WebArenaGoalCompilationV2(contract, scope)


def compile_webarena_inventory_v2(
    snapshot: SemanticSnapshot,
    goal: str,
    *,
    compilation: WebArenaGoalCompilationV2 | None = None,
) -> V4ActionInventory:
    if compilation is None:
        compilation = compile_webarena_goal_v2(goal, snapshot)
    elif compilation.goal_contract.goal != str(goal).strip():
        raise ValueError("persisted WebArena v2 goal does not match instruction")
    return compile_webarena_inventory_v1(
        snapshot,
        goal,
        goal_contract=compilation.goal_contract,
    )


def certify_webarena_commit_v2(
    *,
    current: SemanticSnapshot,
    compilation: WebArenaGoalCompilationV2,
    candidate: ActionCandidateV4,
    inventory: tuple[ActionCandidateV4, ...],
    active_transactions: tuple[object, ...],
    resolved_semantic_bids: tuple[str, ...] = (),
    quarantined_commit_keys: frozenset[tuple[object, ...]] = frozenset(),
) -> CommitCertificateV4:
    if not compilation.scope.allowed:
        return CommitCertificateV4(
            False,
            compilation.scope.reason,
            GroundingDecisionV4(
                False,
                compilation.scope.reason,
                "direct_reply_scope_guard",
            ),
        )
    return certify_webarena_commit_v1(
        current=current,
        goal=compilation.goal_contract,
        candidate=candidate,
        inventory=inventory,
        active_transactions=active_transactions,
        resolved_semantic_bids=resolved_semantic_bids,
        quarantined_commit_keys=quarantined_commit_keys,
    )
