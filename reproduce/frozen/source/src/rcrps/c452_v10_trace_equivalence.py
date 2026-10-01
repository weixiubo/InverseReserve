"""Counterfactual PACT-v10 action-path audit over consumed C452 traces.

PACT-v10 differs from v9 only at interrupt-repair admission.  The v9 driver
already records, immediately before every forward action, both the remaining
GUI-action budget and the complete active-plus-proposal inverse reserve.  A
successful v9 interrupt repair therefore takes the same action path under v10
iff its compensator is unique and two repair actions leave that reserve intact.
"""

from __future__ import annotations

from typing import Any, Iterable


INVERSE_RESERVATION_EVENT = "inverse_budget_reservation"
TRANSACTION_RESULT_EVENT = "typed_transaction_result_v8"
COMPENSATOR_GROUNDING_EVENT = "compensator_grounding"
REPAIR_ACTION_COST = 2


def _events(row: dict[str, Any], field: str) -> tuple[dict[str, Any], ...]:
    value = row.get(field, ())
    if not isinstance(value, list):
        return ()
    return tuple(event for event in value if isinstance(event, dict))


def _indexed(events: tuple[dict[str, Any], ...]) -> bool:
    return all(event.get("event_index") == index for index, event in enumerate(events))


def _integer(value: object, default: int = -1) -> int:
    if isinstance(value, bool):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def analyze_episode(row: dict[str, Any]) -> dict[str, Any]:
    """Determine whether v10 would execute the consumed v9 GUI action path."""

    trace = _events(row, "trace")
    runtime = _events(row, "runtime_events")
    reservations = tuple(
        event
        for event in trace
        if event.get("type") == INVERSE_RESERVATION_EVENT
        and event.get("decision") == "transact"
    )
    outcomes = tuple(
        event for event in trace if event.get("type") == TRANSACTION_RESULT_EVENT
    )
    groundings = tuple(
        event
        for event in runtime
        if event.get("type") == COMPENSATOR_GROUNDING_EVENT
    )

    transaction_rows = []
    for ordinal, (reservation, outcome) in enumerate(zip(reservations, outcomes)):
        repairs = _integer(outcome.get("interrupt_repairs"))
        remaining = _integer(reservation.get("remaining_after_action"))
        inverse_reserve = _integer(reservation.get("active_inverse_cost"))
        transaction_rows.append(
            {
                "transaction_ordinal": ordinal,
                "bid": reservation.get("bid"),
                "result_bid": outcome.get("bid"),
                "v9_allowed": reservation.get("allowed") is True,
                "v9_admitted": outcome.get("admitted") is True,
                "v9_halted": outcome.get("halted") is True,
                "interrupt_repairs": repairs,
                "remaining_after_forward": remaining,
                "registered_inverse_reserve": inverse_reserve,
                "v10_repair_action_cost": REPAIR_ACTION_COST if repairs == 1 else 0,
                "v10_slack_after_repair": (
                    remaining - REPAIR_ACTION_COST - inverse_reserve
                    if repairs == 1
                    else None
                ),
            }
        )

    repaired = tuple(
        item for item in transaction_rows if item["interrupt_repairs"] == 1
    )
    grounding_unique = all(
        event.get("allowed") is True
        and isinstance(event.get("candidate_bids"), list)
        and len(event["candidate_bids"]) == 1
        for event in groundings
    )
    metrics = row.get("metrics", {})
    episode = row.get("episode", {})
    checks = {
        "trace_is_complete_indexed_sequence": _indexed(trace),
        "runtime_is_complete_indexed_sequence": _indexed(runtime),
        "transaction_reservations_pair_one_to_one_with_results": len(reservations)
        == len(outcomes),
        "paired_transaction_bids_match": len(transaction_rows) == len(reservations)
        and all(item["bid"] == item["result_bid"] for item in transaction_rows),
        "typed_transaction_metric_matches_results": _integer(
            metrics.get("typed_transactions")
        )
        == len(outcomes),
        "all_v9_transaction_reservations_were_admitted": all(
            item["v9_allowed"] for item in transaction_rows
        ),
        "all_v9_transaction_results_were_admitted_without_halt": all(
            item["v9_admitted"] and not item["v9_halted"]
            for item in transaction_rows
        ),
        "interrupt_repair_count_is_binary": all(
            item["interrupt_repairs"] in {0, 1} for item in transaction_rows
        ),
        "each_interrupt_repair_has_one_unique_public_compensator": grounding_unique
        and len(groundings) == len(repaired),
        "every_v9_repair_preserves_the_complete_inverse_reserve_under_v10": all(
            _integer(item["v10_slack_after_repair"]) >= 0 for item in repaired
        ),
        "consumed_episode_succeeded_without_method_or_infrastructure_failure": row.get(
            "success"
        )
        is True
        and row.get("method_failure") is None
        and row.get("infrastructure_failure") is False
        and metrics.get("runtime_halted") is False,
        "episode_is_the_full_pact_v9_c452_arm": episode.get("method")
        == "full_pact_v9",
    }
    return {
        "episode_id": episode.get("episode_id"),
        "task": episode.get("task"),
        "seed": episode.get("seed"),
        "transactions": len(transaction_rows),
        "interrupt_repairs": len(repaired),
        "compensator_groundings": len(groundings),
        "minimum_v10_slack_after_repair": (
            min(_integer(item["v10_slack_after_repair"]) for item in repaired)
            if repaired
            else None
        ),
        "repair_transactions": list(repaired),
        "checks": checks,
        "v10_action_path_equivalent": all(checks.values()),
    }


def analyze_c452_rows(
    rows: Iterable[dict[str, Any]],
    *,
    expected_episodes: int,
    minimum_observed_repairs: int = 1,
) -> dict[str, Any]:
    """Aggregate the preregistered per-episode equivalence decision."""

    episodes = tuple(analyze_episode(row) for row in rows)
    identifiers = [str(row.get("episode_id")) for row in episodes]
    repair_margins = [
        int(row["minimum_v10_slack_after_repair"])
        for row in episodes
        if row["minimum_v10_slack_after_repair"] is not None
    ]
    total_repairs = sum(int(row["interrupt_repairs"]) for row in episodes)
    checks = {
        "complete_c452_episode_population": len(episodes) == expected_episodes,
        "unique_c452_episode_identifiers": len(set(identifiers)) == len(identifiers)
        and all(identifier not in {"", "None"} for identifier in identifiers),
        "changed_interrupt_repair_branch_was_observed": total_repairs
        >= minimum_observed_repairs,
        "every_episode_is_v10_action_path_equivalent": all(
            row["v10_action_path_equivalent"] for row in episodes
        ),
    }
    return {
        "episodes": len(episodes),
        "transactions": sum(int(row["transactions"]) for row in episodes),
        "interrupt_repairs": total_repairs,
        "compensator_groundings": sum(
            int(row["compensator_groundings"]) for row in episodes
        ),
        "minimum_v10_slack_after_repair": (
            min(repair_margins) if repair_margins else None
        ),
        "failed_episode_ids": [
            row["episode_id"]
            for row in episodes
            if not row["v10_action_path_equivalent"]
        ],
        "episode_audits": list(episodes),
        "checks": checks,
        "passed": all(checks.values()),
    }
