"""Frozen population and analysis for bounded WebArena mechanism transfer.

The module performs no reset, action, model call, or evaluator call.  It fixes
the three development tasks, six mechanism-holdout tasks, one-open manifests,
budgets, information boundaries, and outcome rules selected offline from all
258 WebArena-Verified hard tasks.
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Any, Iterable

from inversereserve.adapters.webarena.webarena_verified_runtime_v1 import validate_image_record_v1
from inversereserve.studies.validation import require

OFFICIAL_REPOSITORY_HEAD = "6473f72db5dcefc97b5725b59e734504edc28a21"
OFFICIAL_REPOSITORY_TAG = "v1.2.3"
OFFICIAL_DATASET_SHA256 = "d65275660814663375028e9017e1f929e3c38321041b125795e2713b52243d30"
OFFICIAL_HARD_SUBSET_SHA256 = "3b0a4df231bb5a0c642215e521c3fa97701a384f52a734dc2db8f617ad0591a7"
OFFLINE_INVENTORY_SHA256 = "10798376cfa4637cc7ecbf1f3f0efff66277c0dc42f8815e636bc8798eb597ff"
EXPECTED_REPOSITORIES = {
    "browsergym": "0a785fbed075224ae81ca9c1fe924f66050696fe",
    "webarena_verified": OFFICIAL_REPOSITORY_HEAD,
}
EXPECTED_RUNTIME = {
    "container_startup_timeout_seconds": 900.0,
    "pre_observation_delay_seconds": 5.0,
    "browser_timeout_milliseconds": 30000,
}
EXPECTED_OFFICIAL_IMAGES = {
    "reddit": {
        "loaded_image_tag": "am1n3e/webarena-verified-reddit:aaai27-0594908",
        "loaded_image_id": "sha256:59a4863de0f2107ef275e4ee33d8ca37d76ccceeed8ec558cdda1a0c64939914",
        "distribution_digest": "sha256:0594908059a03e5f610005689440a95c05e776e734006197c7b1eba12734cb46",
        "archive_sha256": "9e774a7d370193255b57ac1cb70d16f6253a1c92cb19db26c595f898909b9912",
    },
    "gitlab": {
        "loaded_image_tag": "am1n3e/webarena-verified-gitlab:aaai27-673ba94",
        "loaded_image_id": "sha256:c253a07080e673463c3ecef46142cd696e30cd8259fca04f1a037ec57b59f09d",
        "distribution_digest": "sha256:673ba94d757c5b3f4bb55751ad8b745a33bad2b987349322403cbc41035a92e0",
        "archive_sha256": "11bed0ee4d532de4b5870aca07b3d845e13386c724adb7430341620ffa06c60c",
    },
    "shopping_admin": {
        "loaded_image_tag": "am1n3e/webarena-verified-shopping_admin:aaai27-d0531dd",
        "loaded_image_id": "sha256:b97846428776ac553c411507ad7cfd3b5409946eee0cee3bbdba65bb3de72d1d",
        "distribution_digest": "sha256:d0531dd27ed98d0c459ff9e88118bf2ed8b660b0ed99c38837db46c065a5be13",
        "archive_sha256": "ccc1755ecb5ffe7165f52558f56ed0333ee3066e2e2b4348aa4b6555994a62a7",
    },
    "shopping": {
        "loaded_image_tag": "am1n3e/webarena-verified-shopping:aaai27-3e8cb9b",
        "loaded_image_id": "sha256:a5b6fb47ee9f378ceca18e32261a92a8964f0ccfb9f1d3741ce3a0e2d990839d",
        "distribution_digest": "sha256:3e8cb9b945ea9b1c94ab26dba53e8d12dd0406abbf4bf686fd3bb2b6a5908feb",
        "archive_sha256": "7eaec962bff9dd02ffb02112276d308a767bb8a032f5a6ee1992137fdb5d86af",
    },
}
EXPECTED_OFFICIAL_EVALUATOR = {
    "version": "1.2.3",
    "evaluator_checksum": "35c3385b1db4b3378657589f95f50defd4234bd36e5b93d44733fd561b01db4e",
    "data_checksum": OFFICIAL_DATASET_SHA256,
    "image": {
        "loaded_image_tag": "ghcr.io/servicenow/webarena-verified:aaai27-1842ec6",
        "loaded_image_id": "sha256:d95346180e50dfb048860021d6a768df4f2059fa6042b09ae18aa8199c1042da",
        "distribution_digest": "sha256:1842ec6841e1d394b7220bb4cc19902b82b76abc71bccae70771e4d685093af3",
        "archive_sha256": "3f03bd0c0f7a54f2ea35fd9df2acd2c57323e637761ca30c6ee98d0475fcec02",
    },
}
REQUIRED_SOURCE_PATHS = {
    "scripts/webarena_exact_mutation_transfer_protocol_v1.py",
    "scripts/webarena_exact_mutation_transfer_v1.py",
    "scripts/webarena_verified_select_exact_mutations.py",
    "src/inversereserve/studies/webarena_exact_mutation_transfer_v1.py",
    "src/inversereserve/adapters/webarena/webarena_exact_mutation_agent_v1.py",
    "src/inversereserve/adapters/webarena/webarena_public_navigation_v1.py",
    "src/inversereserve/adapters/webarena/webarena_verified_runtime_v1.py",
    "src/inversereserve/adapters/webarena/webarena_exact_mutation_v1.py",
    "src/inversereserve/adapters/webarena/webarena_goal_adapter_v1.py",
    "src/inversereserve/adapters/webarena/webarena_executor_v1.py",
    "src/inversereserve/controllers/pact_controller_v9.py",
    "src/inversereserve/contracts/typed_contracts_v9.py",
    "src/inversereserve/controllers/pact_controller_v8.py",
    "src/inversereserve/contracts/pact_grounding_v8.py",
    "src/inversereserve/core/effect_ledger_v8.py",
    "src/inversereserve/controllers/confirmation_agents_v7.py",
    "src/inversereserve/controllers/pact_controller_v4.py",
    "src/inversereserve/contracts/typed_contracts_v4.py",
    "src/inversereserve/contracts/goal_contracts_v4.py",
    "src/inversereserve/models/structured_planner_v4.py",
    "src/inversereserve/observations/typed_observation.py",
    "src/inversereserve/contracts/transaction_actions_v4.py",
    "scripts/c444_pact_v7_matched_confirmation.py",
    "scripts/c438_qwen_pact_v6_planner_capacity.py",
    "scripts/c416_qwen35_9b_capacity_diagnostic.py",
    "scripts/c414_adaptive_semantic_risk_diagnostic.py",
}
DEVELOPMENT_TASKS = (
    (
        399,
        "reddit",
        6,
        "__REDDIT__",
        'Change my bio to "I am a robot" in the discussion forum',
        "d103c3018f8118e3962837a9a80033cce715c6362b3a3c78fbea59b27c1e3b42",
    ),
    (
        449,
        "gitlab",
        331,
        "__GITLAB__",
        "set the homepage URL on my GitLab profile to helloworld.xyz",
        "094fff701231bdb1cb9af7ecf0469a8c72f07f9fb6e255ee2acf67d7577cbcb1",
    ),
    (
        488,
        "shopping_admin",
        275,
        "__SHOPPING_ADMIN__",
        'Change the page title of "Home Page" page on my site to "This is the home page!! Leave here!!".',
        "2b741921dd763af131f25e144d46872796c2019bec9761a201ee1ebd99dff196",
    ),
)
HOLDOUT_TASKS = (
    (
        400,
        "reddit",
        6,
        "__REDDIT__",
        'Change my bio to "Pro Python Developer with 20 years of Experience" in the discussion forum',
        "88409de293e70b6222f1dc4edce4415fed268ce7aa35a45648cc7ae90cde179c",
    ),
    (
        401,
        "reddit",
        6,
        "__REDDIT__",
        'Change my bio to "Seeking SDE positions" in the discussion forum',
        "e31963f5949fd07188fe254f0b67e00187f33ac1d818fc7d32ff5b38ff625291",
    ),
    (
        418,
        "gitlab",
        361,
        "__GITLAB__",
        "Set my gitlab status as Busy.",
        "15819d1f940694b87c70f14247962d3f44844a43dd05f368922fdf661e797944",
    ),
    (
        451,
        "gitlab",
        331,
        "__GITLAB__",
        "set the homepage URL on my GitLab profile to www.byteblaze.com",
        "83349eb7c67d175c4d8f45243ae07937a29ca40313a3fc576886197c223a0afb",
    ),
    (
        489,
        "shopping_admin",
        275,
        "__SHOPPING_ADMIN__",
        'Change the page title of "Privacy Policy" page on my site to "No privacy policy is needed in this dystopian world".',
        "88c6987bc361d034dddfbf5491a10c219f70be58dfc2e00bc6015fd90b747cf0",
    ),
    (
        797,
        "shopping",
        191,
        "__SHOPPING__",
        "Change the delivery address for my first order ever to 3 Oxford St, Cambridge, MA.",
        "908c4f0ca06d28370593a60b7c7d256b325b310408511253de3b78d30d94aa20",
    ),
)
HOST_PORTS = {
    "reddit": {"site": 20999, "control": 20998},
    "gitlab": {"site": 8023, "control": 22024},
    "shopping_admin": {"site": 22780, "control": 22781},
    "shopping": {"site": 22770, "control": 22771},
}
EXPECTED_BUDGETS = {
    "maximum_gui_actions": 40,
    "maximum_planner_calls": 40,
    "maximum_wall_seconds": 900.0,
    "maximum_navigation_candidates": 64,
}
EXPECTED_GENERATION = {"enable_thinking": False, "do_sample": False, "max_new_tokens": 64}
EXPECTED_INFORMATION_BOUNDARY = {
    "method_receives_public_goal_ax_dom_screenshot_and_own_history": True,
    "task_id_harness_only": True,
    "reward_and_evaluator_harness_only": True,
    "hidden_database_and_reference_answer_forbidden": True,
    "site_specific_routes_and_css_forbidden": True,
    "one_fresh_container_and_one_reset_per_task": True,
    "holdout_states_unopened_before_holdout_protocol": True,
}
EXPECTED_HOLDOUT_GATES = {
    "minimum_official_successes": 5,
    "require_success_on_every_site": True,
    "require_typed_transaction_when_target_form_reached": True,
    "require_success_implies_effective_certified_commit": True,
    "require_zero_infrastructure_failures": True,
    "require_zero_forbidden_method_inputs": True,
    "require_all_budgets_respected": True,
    "require_zero_parser_failures": True,
    "require_zero_action_errors": True,
    "require_zero_runtime_halts": True,
    "require_zero_wrong_terminal_commits": True,
    "require_zero_terminal_transactions": True,
    "require_zero_uncertified_commits": True,
    "require_zero_commit_effect_failures": True,
    "require_zero_inverse_reservation_stops": True,
    "require_all_attempted_restorations_pass": True,
    "require_zero_repeated_effect_or_navigation_keys": True,
    "require_credential_safe_har": True,
}
EXPECTED_DECISION_RULES = {
    "adapter_development": {
        "on_pass": "retain all three development outcomes, freeze any public-only adapter changes, then seal a source-bound holdout protocol",
        "on_failure": "preserve the failed development artifact and keep all holdout states unopened",
    },
    "mechanism_holdout": {
        "on_pass": "report bounded exact-mutation transfer across the four frozen sites",
        "on_failure": "report the complete negative holdout result without replacement",
    },
}


def _task_rows(partition: str) -> tuple[tuple[Any, ...], ...]:
    if partition == "adapter_development":
        return DEVELOPMENT_TASKS
    if partition == "mechanism_holdout":
        return HOLDOUT_TASKS
    raise ValueError(f"unknown exact-mutation transfer partition: {partition}")


def episode_manifest(partition: str) -> list[dict[str, Any]]:
    output = []
    for index, row in enumerate(_task_rows(partition)):
        task_id, site, template_id, start_url, intent, projection_sha256 = row
        output.append(
            {
                "episode_index": index,
                "partition": partition,
                "task_id": int(task_id),
                "site": str(site),
                "intent_template_id": int(template_id),
                "start_url_template": str(start_url),
                "intent": str(intent),
                "public_projection_sha256": str(projection_sha256),
                "seed": 270000 + int(task_id),
                "container_name": f"rps-wa-{partition.replace('_', '-')}-{task_id}",
                "site_port": HOST_PORTS[str(site)]["site"],
                "control_port": HOST_PORTS[str(site)]["control"],
                "episode_id": f"webarena-{task_id}-{partition}",
            }
        )
    return output


def expected_official_source() -> dict[str, Any]:
    return {
        "repository_head": OFFICIAL_REPOSITORY_HEAD,
        "repository_tag": OFFICIAL_REPOSITORY_TAG,
        "dataset_sha256": OFFICIAL_DATASET_SHA256,
        "hard_subset_sha256": OFFICIAL_HARD_SUBSET_SHA256,
        "hard_subset_task_count": 258,
        "offline_inventory_sha256": OFFLINE_INVENTORY_SHA256,
    }


def validate_protocol_shape(protocol: dict[str, Any], *, partition: str) -> None:
    expected_candidate = (
        "WebArena-Verified-exact-mutation-development-protocol-v1"
        if partition == "adapter_development"
        else "WebArena-Verified-exact-mutation-holdout-protocol-v1"
    )
    expected_status = (
        "sealed_before_development_states_opened"
        if partition == "adapter_development"
        else "sealed_before_holdout_states_opened"
    )
    require(
        not protocol.get("candidate") != expected_candidate,
        "unexpected exact-mutation transfer protocol candidate",
    )
    require(
        not protocol.get("status") != expected_status,
        "exact-mutation transfer protocol was not sealed before opening",
    )
    require(not protocol.get("partition") != partition, "exact-mutation transfer partition changed")
    require(
        re.fullmatch("[0-9a-f]{40}", str(protocol.get("source_commit", ""))) is not None,
        "exact-mutation source commit is not immutable",
    )
    require(
        not protocol.get("episodes") != episode_manifest(partition),
        "exact-mutation one-open manifest changed",
    )
    require(
        not int(protocol.get("expected_episodes", -1)) != len(_task_rows(partition)),
        "exact-mutation episode count changed",
    )
    require(not protocol.get("budgets") != EXPECTED_BUDGETS, "exact-mutation equal budgets changed")
    require(
        not protocol.get("generation") != EXPECTED_GENERATION, "exact-mutation generation settings changed"
    )
    require(
        not protocol.get("information_boundary") != EXPECTED_INFORMATION_BOUNDARY,
        "exact-mutation information boundary changed",
    )
    require(not protocol.get("runtime") != EXPECTED_RUNTIME, "exact-mutation runtime settings changed")
    require(
        not protocol.get("official_source") != expected_official_source(),
        "official repository, dataset, or inventory changed",
    )
    require(
        not protocol.get("repositories") != EXPECTED_REPOSITORIES, "exact-mutation repository pins changed"
    )
    require(
        not protocol.get("decision_rule") != EXPECTED_DECISION_RULES[partition],
        "exact-mutation transfer decision rule changed",
    )
    require(
        not protocol.get("official_images") != EXPECTED_OFFICIAL_IMAGES, "official site image records changed"
    )
    for record in protocol["official_images"].values():
        validate_image_record_v1(record)
    require(
        not protocol.get("official_evaluator") != EXPECTED_OFFICIAL_EVALUATOR,
        "official evaluator record changed",
    )
    validate_image_record_v1(protocol["official_evaluator"]["image"])
    if partition == "adapter_development":
        if protocol.get("holdout_gates") is not None:
            raise ValueError("development protocol must not report a holdout decision")
        if protocol.get("activation") not in ({}, None):
            raise ValueError("development protocol cannot depend on opened outcomes")
    else:
        if protocol.get("holdout_gates") != EXPECTED_HOLDOUT_GATES:
            raise ValueError("exact-mutation holdout gates changed")
        if set(protocol.get("activation", {})) != {"development_result"}:
            raise ValueError("holdout must bind the complete development artifact")
        if set(protocol["activation"]["development_result"]) != {"path", "sha256"}:
            raise ValueError("holdout development activation reference changed")


def _metric(row: dict[str, Any], name: str) -> int:
    return int(row.get("metrics", {}).get(name, 0))


def _manifest_exact(rows: tuple[dict[str, Any], ...], partition: str) -> bool:
    expected = {row["episode_id"]: row for row in episode_manifest(partition)}
    observed_ids = [str(row.get("episode", {}).get("episode_id")) for row in rows]
    return bool(
        len(rows) == len(expected)
        and len(set(observed_ids)) == len(observed_ids)
        and (set(observed_ids) == set(expected))
        and all((row["episode"] == expected[row["episode"]["episode_id"]] for row in rows))
    )


def _forbidden_inputs_absent(row: dict[str, Any]) -> bool:
    method = row.get("method_input", {})
    evaluation = row.get("evaluation_audit", {})
    return bool(
        method.get("method_received_task_id") is False
        and method.get("method_received_seed") is False
        and (method.get("method_received_reward") is False)
        and (method.get("method_received_evaluator_fields") is False)
        and (method.get("method_received_hidden_state") is False)
        and (method.get("method_received_site_specific_route") is False)
        and (evaluation.get("reward_or_info_forwarded_to_method") is False)
        and (evaluation.get("official_evaluator_called_by_method") is False)
    )


def _key_repetitions(row: dict[str, Any]) -> dict[str, dict[str, int]]:
    effect_counts = Counter((str(record.get("key_sha256")) for record in row.get("effect_ledger_v8", [])))
    navigation_counts = Counter(
        (str(record.get("attempt_key")) for record in row.get("navigation_effects", []))
    )
    return {
        "commit": {key: count for key, count in effect_counts.items() if count > 1},
        "navigation": {key: count for key, count in navigation_counts.items() if count > 1},
    }


def analyze_transfer_rows(
    rows: Iterable[dict[str, Any]], *, partition: str, all_claims_complete: bool
) -> dict[str, Any]:
    rows = tuple(rows)
    manifest_exact = _manifest_exact(rows, partition)
    official_success = sum((row.get("official_evaluation", {}).get("passed") is True for row in rows))
    by_site = {}
    for site in sorted({episode[1] for episode in _task_rows(partition)}):
        subset = [row for row in rows if row.get("episode", {}).get("site") == site]
        by_site[site] = {
            "success": sum((row.get("official_evaluation", {}).get("passed") is True for row in subset)),
            "episodes": len(subset),
        }
    repetitions = {}
    for row in rows:
        repeated = _key_repetitions(row)
        if repeated["commit"] or repeated["navigation"]:
            repetitions[row["episode"]["episode_id"]] = repeated
    metrics = _analyze_transfer_rows_metrics(by_site=by_site, official_success=official_success, rows=rows)
    common_checks = _analyze_transfer_rows_common_checks(
        all_claims_complete=all_claims_complete,
        manifest_exact=manifest_exact,
        metrics=metrics,
        repetitions=repetitions,
        rows=rows,
    )
    if partition == "adapter_development":
        checks = {
            **common_checks,
            "all_three_development_outcomes_retained": len(rows) == len(DEVELOPMENT_TASKS),
            "holdout_outcomes_remain_unopened": all(
                (row.get("holdout_outcomes_opened") is False for row in rows)
            ),
        }
    else:
        checks = _analyze_transfer_rows_checks(
            by_site=by_site,
            common_checks=common_checks,
            metrics=metrics,
            official_success=official_success,
            rows=rows,
        )
    return {
        "partition": partition,
        "metrics": metrics,
        "repeated_keys": repetitions,
        "checks": checks,
        "passed": all(checks.values()),
    }


def _analyze_transfer_rows_metrics(*, by_site: Any, official_success: Any, rows: Any) -> dict[str, Any]:
    """Compute metrics from explicit study inputs."""
    return {
        "episodes": len(rows),
        "official_success": official_success,
        "official_success_rate": official_success / len(rows) if rows else 0.0,
        "by_site": by_site,
        "method_effective_commits": sum((row.get("method_commit_effective") is True for row in rows)),
        "target_forms_reached": sum((row.get("typed_target_form_reached") is True for row in rows)),
        "typed_transactions": sum((_metric(row, "typed_transactions") for row in rows)),
        "certified_commits": sum((_metric(row, "certified_commits") for row in rows)),
        "restoration_attempts": sum((_metric(row, "restoration_attempts") for row in rows)),
        "restoration_passes": sum((_metric(row, "restoration_passes") for row in rows)),
        "navigation_actions": sum((_metric(row, "navigation_actions") for row in rows)),
        "navigation_effect_failures": sum((_metric(row, "navigation_effect_failures") for row in rows)),
        "infrastructure_failures": sum((bool(row.get("infrastructure_failure")) for row in rows)),
        "method_failures": sum((row.get("method_failure") is not None for row in rows)),
    }


def _analyze_transfer_rows_common_checks(
    *, all_claims_complete: Any, manifest_exact: Any, metrics: Any, repetitions: Any, rows: Any
) -> dict[str, Any]:
    """Compute common checks from explicit study inputs."""
    return {
        "complete_one_open_manifest": manifest_exact,
        "all_claims_complete_and_single_open": bool(all_claims_complete),
        "all_rows_complete": all((row.get("complete") is True for row in rows)),
        "official_evaluator_called_once_per_episode": all(
            (row.get("official_evaluation", {}).get("calls") == 1 for row in rows)
        ),
        "zero_infrastructure_failures": metrics["infrastructure_failures"] == 0,
        "zero_forbidden_method_inputs": all((_forbidden_inputs_absent(row) for row in rows)),
        "all_episode_budgets_respected": all(
            (
                _metric(row, "gui_actions") <= EXPECTED_BUDGETS["maximum_gui_actions"]
                and _metric(row, "planner_calls") <= EXPECTED_BUDGETS["maximum_planner_calls"]
                and (
                    float(row.get("metrics", {}).get("wall_seconds", 0.0))
                    <= EXPECTED_BUDGETS["maximum_wall_seconds"]
                )
                for row in rows
            )
        ),
        "credential_safe_har": all(
            (row.get("har_sanitization", {}).get("credential_material_remaining") is False for row in rows)
        ),
        "runtime_images_sources_and_evaluator_exact": all(
            (row.get("runtime_integrity", {}).get("passed") is True for row in rows)
        ),
        "zero_repeated_effect_or_navigation_keys": not repetitions,
    }


def _analyze_transfer_rows_checks(
    *, by_site: Any, common_checks: Any, metrics: Any, official_success: Any, rows: Any
) -> dict[str, Any]:
    """Compute checks from explicit study inputs."""
    return {
        **common_checks,
        "minimum_five_of_six_official_successes": official_success
        >= EXPECTED_HOLDOUT_GATES["minimum_official_successes"],
        "success_on_every_site": all(
            (site["success"] >= 1 and site["episodes"] >= 1 for site in by_site.values())
        ),
        "typed_transaction_when_target_form_reached": all(
            (
                row.get("typed_target_form_reached") is not True or _metric(row, "typed_transactions") >= 1
                for row in rows
            )
        ),
        "official_success_implies_effective_certified_commit": all(
            (
                row.get("official_evaluation", {}).get("passed") is not True
                or (
                    row.get("method_commit_effective") is True
                    and _metric(row, "typed_transactions") >= 1
                    and (_metric(row, "certified_commits") == 1)
                    and (_metric(row, "commit_effect_passes") == 1)
                )
                for row in rows
            )
        ),
        "zero_parser_failures": all((_metric(row, "planner_parse_failures") == 0 for row in rows)),
        "zero_action_errors": all((_metric(row, "action_errors") == 0 for row in rows)),
        "zero_runtime_halts": all((not bool(row.get("metrics", {}).get("runtime_halted")) for row in rows)),
        "zero_wrong_terminal_commits": all((_metric(row, "wrong_terminal_commits") == 0 for row in rows)),
        "zero_terminal_transactions": all((_metric(row, "terminal_transactions") == 0 for row in rows)),
        "zero_uncertified_commits": all((_metric(row, "uncertified_commits") == 0 for row in rows)),
        "zero_commit_effect_failures": all((_metric(row, "commit_effect_failures") == 0 for row in rows)),
        "zero_inverse_reservation_stops": all(
            (_metric(row, "inverse_reservation_stops") == 0 for row in rows)
        ),
        "all_attempted_restorations_pass": metrics["restoration_attempts"] == metrics["restoration_passes"],
    }
