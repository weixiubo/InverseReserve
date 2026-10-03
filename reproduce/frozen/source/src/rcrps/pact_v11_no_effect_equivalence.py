"""Zero-reset PACT-v11 compatibility audit over sealed v9/v10 episodes."""

from __future__ import annotations

from typing import Any, Iterable


POSTCONDITION_EVENT = "postcondition"
ACTION_EVENT = "action"
INVERSE_ROLE = "typed_inverse"
REJECTED_CONTEXTS = frozenset({"typed forward", "typed retry"})
DELTA_FIELDS = (
    "added_visible_bids",
    "removed_visible_bids",
    "changed_visible_bids",
    "newly_visible_text",
)


def _events(row: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    value = row.get("runtime_events")
    if not isinstance(value, list):
        return ()
    return tuple(event for event in value if isinstance(event, dict))


def _indexed(events: tuple[dict[str, Any], ...]) -> bool:
    return all(event.get("event_index") == index for index, event in enumerate(events))


def _delta_is_well_formed(delta: object) -> bool:
    return isinstance(delta, dict) and all(
        isinstance(delta.get(field), list) for field in DELTA_FIELDS
    )


def _delta_is_globally_unchanged(delta: dict[str, Any]) -> bool:
    return not any(delta[field] for field in DELTA_FIELDS[:3])


def _next_action_role(
    events: tuple[dict[str, Any], ...],
    start: int,
) -> str | None:
    for event in events[start + 1 :]:
        if event.get("type") == ACTION_EVENT:
            role = event.get("role")
            return role if isinstance(role, str) else None
        if event.get("type") == POSTCONDITION_EVENT:
            return None
    return None


def analyze_episode(
    row: dict[str, Any],
    *,
    expected_method: str,
) -> dict[str, Any]:
    """Check whether v11 changes any consumed inverse action in one episode."""

    raw_events = row.get("runtime_events")
    events = _events(row)
    episode = row.get("episode")
    episode = episode if isinstance(episode, dict) else {}
    method_input = row.get("method_input")
    method_input = method_input if isinstance(method_input, dict) else {}
    observed_method = episode.get("method") or method_input.get("controller_arm")
    postconditions = tuple(
        (index, event)
        for index, event in enumerate(events)
        if event.get("type") == POSTCONDITION_EVENT
    )
    malformed = [
        index
        for index, event in postconditions
        if type(event.get("passed")) is not bool
        or not _delta_is_well_formed(event.get("delta"))
    ]

    rejected = []
    incompatible = []
    for index, event in postconditions:
        if index in malformed or event.get("passed") is not False:
            continue
        context = event.get("context")
        if context not in REJECTED_CONTEXTS:
            continue
        delta = event["delta"]
        next_role = _next_action_role(events, index)
        globally_unchanged = _delta_is_globally_unchanged(delta)
        audit = {
            "event_index": index,
            "context": context,
            "reason": event.get("reason"),
            "globally_unchanged": globally_unchanged,
            "next_action_role": next_role,
            "v10_static_inverse_reached": next_role == INVERSE_ROLE,
        }
        rejected.append(audit)
        if globally_unchanged and next_role == INVERSE_ROLE:
            incompatible.append(audit)

    checks = {
        "episode_is_complete": row.get("complete") is True,
        "episode_uses_expected_full_method": observed_method == expected_method,
        "runtime_events_are_complete_and_indexed": isinstance(raw_events, list)
        and len(events) == len(raw_events)
        and _indexed(events),
        "every_action_has_a_string_role": all(
            isinstance(event.get("role"), str)
            for event in events
            if event.get("type") == ACTION_EVENT
        ),
        "every_postcondition_has_a_boolean_decision_and_complete_delta": not malformed,
        "no_v10_inverse_follows_a_globally_unchanged_rejection": not incompatible,
    }
    return {
        "episode_id": episode.get("episode_id"),
        "task": episode.get("task"),
        "seed": episode.get("seed"),
        "postconditions": len(postconditions),
        "rejected_postconditions": len(rejected),
        "globally_unchanged_rejections": sum(
            item["globally_unchanged"] for item in rejected
        ),
        "v10_inverse_actions_after_unchanged_rejection": len(incompatible),
        "incompatible_events": incompatible,
        "checks": checks,
        "v11_action_path_equivalent": all(checks.values()),
    }


def analyze_population(
    rows: Iterable[dict[str, Any]],
    *,
    expected_method: str,
    expected_episodes: int,
) -> dict[str, Any]:
    """Apply the preregistered no-effect gate to a complete population."""

    episodes = tuple(
        analyze_episode(row, expected_method=expected_method) for row in rows
    )
    identifiers = [row.get("episode_id") for row in episodes]
    checks = {
        "complete_registered_episode_population": len(episodes) == expected_episodes,
        "unique_nonempty_episode_identifiers": len(set(identifiers))
        == len(identifiers)
        and all(isinstance(identifier, str) and identifier for identifier in identifiers),
        "every_episode_is_v11_action_path_equivalent": all(
            row["v11_action_path_equivalent"] for row in episodes
        ),
    }
    return {
        "episodes": len(episodes),
        "postconditions": sum(row["postconditions"] for row in episodes),
        "rejected_postconditions": sum(
            row["rejected_postconditions"] for row in episodes
        ),
        "globally_unchanged_rejections": sum(
            row["globally_unchanged_rejections"] for row in episodes
        ),
        "v10_inverse_actions_after_unchanged_rejection": sum(
            row["v10_inverse_actions_after_unchanged_rejection"]
            for row in episodes
        ),
        "failed_episode_ids": [
            row["episode_id"]
            for row in episodes
            if not row["v11_action_path_equivalent"]
        ],
        "episode_audits": list(episodes),
        "checks": checks,
        "passed": all(checks.values()),
    }
