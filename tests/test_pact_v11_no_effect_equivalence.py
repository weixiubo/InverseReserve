from __future__ import annotations

from pathlib import Path

from inversereserve.studies.pact_v11_no_effect_equivalence import analyze_episode, analyze_population

ROOT = Path(__file__).resolve().parents[1]


def delta(*, changed: bool) -> dict[str, list[str]]:
    return {
        "added_visible_bids": [],
        "removed_visible_bids": [],
        "changed_visible_bids": ["field"] if changed else [],
        "newly_visible_text": [],
    }


def row(*, changed: bool, episode_id: str = "episode-1") -> dict:
    return {
        "complete": True,
        "episode": {
            "episode_id": episode_id,
            "task": "click-widget",
            "seed": 27501,
            "method": "full_pact_v10",
        },
        "runtime_events": [
            {"event_index": 0, "type": "action", "role": "typed_forward"},
            {
                "event_index": 1,
                "type": "postcondition",
                "context": "typed forward",
                "passed": False,
                "reason": "typed postcondition failed",
                "delta": delta(changed=changed),
            },
            {"event_index": 2, "type": "action", "role": "typed_inverse"},
        ],
    }


def test_v11_equivalence_rejects_v10_inverse_after_global_no_effect() -> None:
    audit = analyze_episode(row(changed=False), expected_method="full_pact_v10")
    assert audit["globally_unchanged_rejections"] == 1
    assert audit["v10_inverse_actions_after_unchanged_rejection"] == 1
    assert audit["incompatible_events"] == [
        {
            "event_index": 1,
            "context": "typed forward",
            "reason": "typed postcondition failed",
            "globally_unchanged": True,
            "next_action_role": "typed_inverse",
            "v10_static_inverse_reached": True,
        }
    ]
    assert not audit["v11_action_path_equivalent"]


def test_v11_equivalence_retains_changed_v10_static_restoration() -> None:
    audit = analyze_episode(row(changed=True), expected_method="full_pact_v10")
    assert audit["globally_unchanged_rejections"] == 0
    assert audit["v10_inverse_actions_after_unchanged_rejection"] == 0
    assert audit["v11_action_path_equivalent"]


def test_v11_equivalence_accepts_webarena_controller_arm_identity() -> None:
    webarena = row(changed=True)
    webarena["episode"].pop("method")
    webarena["method_input"] = {"controller_arm": "full_pact_v10_webarena_exact_mutation_v2"}
    audit = analyze_episode(webarena, expected_method="full_pact_v10_webarena_exact_mutation_v2")
    assert audit["checks"]["episode_uses_expected_full_method"]
    assert audit["v11_action_path_equivalent"]


def test_v11_equivalence_fails_closed_on_malformed_or_unindexed_events() -> None:
    malformed = row(changed=True)
    malformed["runtime_events"][1]["delta"].pop("changed_visible_bids")
    malformed["runtime_events"][2]["event_index"] = 7
    audit = analyze_episode(malformed, expected_method="full_pact_v10")
    assert not audit["checks"]["every_postcondition_has_a_boolean_decision_and_complete_delta"]
    assert not audit["checks"]["runtime_events_are_complete_and_indexed"]
    assert not audit["v11_action_path_equivalent"]


def test_v11_equivalence_requires_exact_event_container_and_scalar_types() -> None:
    wrong_container = row(changed=True)
    wrong_container["runtime_events"] = {}
    container_audit = analyze_episode(wrong_container, expected_method="full_pact_v10")
    assert not container_audit["checks"]["runtime_events_are_complete_and_indexed"]
    assert not container_audit["v11_action_path_equivalent"]
    wrong_scalars = row(changed=True)
    wrong_scalars["runtime_events"][1]["passed"] = 1
    wrong_scalars["runtime_events"][2]["role"] = 7
    scalar_audit = analyze_episode(wrong_scalars, expected_method="full_pact_v10")
    assert not scalar_audit["checks"]["every_action_has_a_string_role"]
    assert not scalar_audit["checks"]["every_postcondition_has_a_boolean_decision_and_complete_delta"]
    assert not scalar_audit["v11_action_path_equivalent"]


def test_v11_population_gate_requires_complete_unique_equivalent_rows() -> None:
    passed = analyze_population(
        [row(changed=True, episode_id="one"), row(changed=True, episode_id="two")],
        expected_method="full_pact_v10",
        expected_episodes=2,
    )
    assert passed["passed"]
    assert passed["v10_inverse_actions_after_unchanged_rejection"] == 0
    failed = analyze_population(
        [row(changed=True, episode_id="same"), row(changed=False, episode_id="same")],
        expected_method="full_pact_v10",
        expected_episodes=2,
    )
    assert not failed["checks"]["unique_nonempty_episode_identifiers"]
    assert not failed["checks"]["every_episode_is_v11_action_path_equivalent"]
    assert not failed["passed"]
