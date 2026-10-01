"""Strict shared model-planner interface for PACT v6 matched experiments."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Iterable

from .structured_planner_v4 import ActionCandidateV4
from .transaction_actions_v4 import ContractActionV4


PLANNER_SYSTEM_PROMPT_V6 = """You are the shared grounded planner for a GUI agent.
The structured goal contract and public action inventory are authoritative.
Every action argument is already bound to an exact goal span; never invent or edit it.

Choose exactly one decision:
- transact: execute a row whose transaction_kind is non-null. Use this for a reversible field fill, component opening, calendar shift, or native selection needed before the goal can be certified.
- commit: execute a row whose transaction_kind is null and whose public label/role/state is the requested target, a suggestion satisfying the goal predicate, a goal date, a completed-form action, or the comparative optimum.
- abstain: no relevant grounded transaction or commit row is available.

Rules:
1. Do not transact an already active or completed control.
2. Prefer unfinished goal-bound transactions before a form action.
3. A visible suggestion satisfying prefix/suffix constraints is a commit, not a new transaction.
4. Calendar Prev/Next is a transaction only when its row has transaction_kind=calendar_month_shift; the goal day is a commit only in the goal month/year.
5. Direct standard widgets and comparative optimum rows are commits with zero exploratory transaction.
6. For an explicit a/an widget or a predicate-defined set with several acceptable rows, use the first matching row in the listed public canonical order.
7. Use exactly one BID from the inventory. Never use task IDs, hidden state, or unlisted actions.
8. Output exactly one compact JSON object and no prose:
   {"decision":"transact|commit|abstain","bid":"BID or null"}
"""


@dataclass(frozen=True)
class PlannerDecisionV6:
    decision: str
    bid: str | None
    candidate: ActionCandidateV4 | None


PROMPT_RECORD_KEYS_V6 = frozenset(
    {
        "bid",
        "op",
        "arg",
        "enable_autocomplete_menu",
        "role",
        "label",
        "state",
        "transaction_kind",
        "semantic_bid",
        "parent_bid",
        "publicly_actionable_offscreen",
    }
)


def action_candidate_from_prompt_record_v6(
    record: dict[str, Any],
) -> ActionCandidateV4:
    """Rehydrate one frozen public inventory row without permissive coercions."""

    if set(record) != PROMPT_RECORD_KEYS_V6:
        raise ValueError("candidate record does not match the frozen v6 schema")
    for key in ("bid", "op", "role", "label", "semantic_bid"):
        if not isinstance(record[key], str):
            raise ValueError(f"candidate {key} must be a JSON string")
    for key in ("enable_autocomplete_menu", "publicly_actionable_offscreen"):
        if not isinstance(record[key], bool):
            raise ValueError(f"candidate {key} must be Boolean")
    if record["transaction_kind"] is not None and not isinstance(
        record["transaction_kind"], str
    ):
        raise ValueError("candidate transaction_kind must be a string or null")
    if record["parent_bid"] is not None and not isinstance(record["parent_bid"], str):
        raise ValueError("candidate parent_bid must be a string or null")
    if not isinstance(record["state"], dict) or any(
        not isinstance(key, str) for key in record["state"]
    ):
        raise ValueError("candidate state must be a string-keyed JSON object")
    argument = record["arg"]
    if isinstance(argument, list):
        if any(not isinstance(value, str) for value in argument):
            raise ValueError("candidate list argument must contain only strings")
        argument = tuple(argument)
    elif argument is not None and not isinstance(argument, str):
        raise ValueError("candidate argument must be a string, string list, or null")
    action = ContractActionV4(
        record["op"],
        record["bid"],
        argument,
        record["enable_autocomplete_menu"],
    )
    return ActionCandidateV4(
        bid=record["bid"],
        action=action,
        role=record["role"],
        label=record["label"],
        state=tuple(sorted(record["state"].items())),
        transaction_kind=record["transaction_kind"],
        semantic_bid=record["semantic_bid"],
        parent_bid=record["parent_bid"],
        publicly_actionable_offscreen=record["publicly_actionable_offscreen"],
    )


def compact_goal_contract_record(contract: Any) -> dict[str, Any]:
    record = contract.record() if hasattr(contract, "record") else dict(contract)
    return {
        "exact_constraint": record.get("exact_constraint"),
        "field_assignments": [
            {"bid": row["bid"], "label": row["label"], "value": row["value"]}
            for row in record.get("field_assignments", [])
        ],
        "date_anchor": record.get("date_anchor"),
        "option_selections": [
            {"bid": row["bid"], "values": row["values"]}
            for row in record.get("option_selections", [])
        ],
        "role_anchor": record.get("role_anchor"),
        "terminal_intent": record.get("terminal_intent"),
        "objective_anchor": record.get("objective_anchor"),
        "widget_kind_anchor": record.get("widget_kind_anchor"),
    }


def planner_messages_v6(
    *,
    goal: str,
    goal_contract: Any,
    candidates: Iterable[ActionCandidateV4],
    active_transactions: Iterable[dict[str, Any]] = (),
    completed_transactions: Iterable[dict[str, Any]] = (),
) -> list[dict[str, str]]:
    rows = tuple(candidates)
    active = tuple(active_transactions)
    completed = tuple(completed_transactions)
    inventory = "\n".join(
        json.dumps(row.prompt_record(), ensure_ascii=False, sort_keys=True)
        for row in rows
    )
    user = (
        f"GOAL:\n{str(goal).strip()}\n\n"
        "STRUCTURED GOAL CONTRACT:\n"
        f"{json.dumps(compact_goal_contract_record(goal_contract), ensure_ascii=False, sort_keys=True)}\n\n"
        "ACTIVE TRANSACTIONS (do not repeat):\n"
        f"{json.dumps(active, ensure_ascii=False, sort_keys=True)}\n\n"
        "COMPLETED TRANSACTIONS (do not repeat):\n"
        f"{json.dumps(completed, ensure_ascii=False, sort_keys=True)}\n\n"
        f"PUBLIC ACTION INVENTORY ({len(rows)} rows):\n"
        f"{inventory if inventory else '<empty>'}"
    )
    return [
        {"role": "system", "content": PLANNER_SYSTEM_PROMPT_V6},
        {"role": "user", "content": user},
    ]


def _single_json_object(text: str) -> dict[str, Any]:
    stripped = str(text).strip()
    if stripped.startswith("```json"):
        stripped = stripped[len("```json") :]
        if stripped.endswith("```"):
            stripped = stripped[:-3]
        stripped = stripped.strip()
    decoder = json.JSONDecoder()
    value, end = decoder.raw_decode(stripped)
    if stripped[end:].strip():
        raise ValueError("planner output contains text after the JSON object")
    if not isinstance(value, dict):
        raise ValueError("planner output must be a JSON object")
    return value


def parse_planner_decision_v6(
    text: str,
    candidates: Iterable[ActionCandidateV4],
) -> PlannerDecisionV6:
    payload = _single_json_object(text)
    if set(payload) != {"decision", "bid"}:
        raise ValueError("planner output must contain exactly decision and bid")
    if not isinstance(payload["decision"], str):
        raise ValueError("planner decision must be a JSON string")
    decision = payload["decision"]
    if decision not in {"transact", "commit", "abstain"}:
        raise ValueError("planner decision must be transact, commit, or abstain")
    raw_bid = payload["bid"]
    if raw_bid is not None and not isinstance(raw_bid, str):
        raise ValueError("planner bid must be a JSON string or null")
    bid = raw_bid
    candidate_rows = tuple(candidates)
    lookup = {candidate.bid: candidate for candidate in candidate_rows}
    if len(lookup) != len(candidate_rows):
        raise ValueError("planner inventory contains duplicate BIDs")
    if decision == "abstain":
        if bid is not None:
            raise ValueError("abstain must use a null bid")
        return PlannerDecisionV6(decision, None, None)
    if bid is None or bid not in lookup:
        raise ValueError("planner bid is absent from the public inventory")
    candidate = lookup[bid]
    if decision == "transact" and candidate.transaction_kind is None:
        raise ValueError("transact requires a typed transaction row")
    if decision == "commit" and candidate.transaction_kind is not None:
        raise ValueError("commit requires a non-transaction row")
    return PlannerDecisionV6(decision, bid, candidate)


def canonical_planner_output_v6(decision: str, bid: str | None) -> str:
    return json.dumps(
        {"decision": decision, "bid": bid},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
