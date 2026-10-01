#!/usr/bin/env python3
"""Run one-open WebArena-Verified exact-mutation development or holdout.

The executable intentionally ships without an active protocol.  A protocol
must bind all four official site images, the offline evaluator, repositories,
task inventory, causal sources, and the exact partition before this runner can
start a container or reset a browser.  Development and holdout use the same
code; holdout additionally requires an immutable complete development parent.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT / "src", ROOT / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import c414_adaptive_semantic_risk_diagnostic as c414  # noqa: E402
import c427_pact_live_development as c427  # noqa: E402
import c444_pact_v7_matched_confirmation as c444  # noqa: E402
from rcrps.webarena_exact_mutation_agent_v1 import (  # noqa: E402
    ExactMutationTransferAgentV1,
)
from rcrps.webarena_exact_mutation_transfer_v1 import (  # noqa: E402
    EXPECTED_OFFICIAL_EVALUATOR,
    EXPECTED_REPOSITORIES,
    OFFICIAL_DATASET_SHA256,
    REQUIRED_SOURCE_PATHS,
    analyze_transfer_rows,
    episode_manifest,
    validate_protocol_shape,
)
from rcrps.webarena_verified_runtime_v1 import (  # noqa: E402
    FreshWebArenaContainerV1,
    exact_container_names_v1,
    make_webarena_environment_v1,
    public_site_base_v1,
    render_start_url_v1,
    run_command,
    sanitize_network_har_v1,
    validate_image_record_v1,
    validate_runtime_credentials_v1,
)


INVENTORY_PATH = (
    ROOT / "validation" / "webarena_verified_exact_mutation_inventory_v1.json"
)
DEVELOPMENT_OUTPUT = (
    ROOT / "validation" / "webarena_verified_exact_mutation_development_v1.json"
)
HOLDOUT_OUTPUT = (
    ROOT / "validation" / "webarena_verified_exact_mutation_holdout_v1.json"
)
RUN_ROOT = ROOT / "runs" / "webarena_verified_exact_mutation_transfer_v1"
DEFAULT_MODEL_PATH = Path(
    os.environ.get(
        "INVERSERESERVE_MODEL_PATH",
        ROOT / "models" / "Qwen3.5-9B",
    )
)
WEBARENA_REPOSITORY = ROOT / "external" / "webarena-verified"
REPOSITORY_PATHS = {
    "browsergym": ROOT / "external" / "BrowserGym",
    "webarena_verified": WEBARENA_REPOSITORY,
}
EVALUATOR_VERSION = str(EXPECTED_OFFICIAL_EVALUATOR["version"])
EVALUATOR_CHECKSUM = str(EXPECTED_OFFICIAL_EVALUATOR["evaluator_checksum"])
CREDENTIAL_ENV = {
    "reddit": ("WEBARENA_REDDIT_AUTOLOGIN",),
    "gitlab": ("WEBARENA_GITLAB_USERNAME", "WEBARENA_GITLAB_PASSWORD"),
    "shopping_admin": ("WEBARENA_SHOPPING_ADMIN_AUTOLOGIN",),
    "shopping": ("WEBARENA_SHOPPING_AUTOLOGIN",),
}
@dataclass(frozen=True)
class TransferPathsV1:
    partition: str
    run_directory: Path
    episode_directory: Path
    claim_directory: Path
    official_output_directory: Path
    evaluator_config_path: Path
    model_cache_path: Path
    model_runtime_path: Path
    output_path: Path


def transfer_paths(partition: str) -> TransferPathsV1:
    if partition not in {"adapter_development", "mechanism_holdout"}:
        raise ValueError("unknown exact-mutation transfer partition")
    base = RUN_ROOT / partition
    output = DEVELOPMENT_OUTPUT if partition == "adapter_development" else HOLDOUT_OUTPUT
    return TransferPathsV1(
        partition,
        base,
        base / "episodes",
        base / "claims",
        base / "official_output",
        base / "evaluator_config.json",
        base / "planner_cache.sqlite3",
        base / "model_runtime.json",
        output,
    )


def _artifact_path(reference: dict[str, Any], *, role: str) -> Path:
    if set(reference) != {"path", "sha256"}:
        raise ValueError(f"{role} activation reference changed")
    relative = Path(str(reference["path"]))
    if relative.is_absolute():
        raise ValueError(f"{role} activation path must be repository-relative")
    path = (ROOT / relative).resolve()
    if path.parent != (ROOT / "validation").resolve():
        raise ValueError(f"{role} activation must be a top-level validation artifact")
    if not path.is_file():
        raise FileNotFoundError(f"{role} activation artifact is absent: {path}")
    actual = c444.sha256(path)
    if actual != reference["sha256"]:
        raise ValueError(f"{role} activation artifact changed: {actual}")
    return path


def verify_development_activation(protocol: dict[str, Any]) -> dict[str, Any]:
    reference = protocol["activation"]["development_result"]
    path = _artifact_path(reference, role="exact-mutation development")
    if path != DEVELOPMENT_OUTPUT.resolve():
        raise ValueError("holdout must bind the canonical development result")
    result = c414.load_json(path)
    if not (
        result.get("candidate")
        == "WebArena-Verified-exact-mutation-development-v1"
        and result.get("status") == "development_complete"
        and result.get("passed") is True
        and result.get("development_states_opened") is True
        and result.get("holdout_states_opened") is False
        and result.get("metrics", {}).get("episodes") == 3
        and result.get("development_task_ids") == [399, 449, 488]
    ):
        raise ValueError("development artifact did not pass the unopened holdout gate")
    return result


def _inspect_loaded_image(record: dict[str, Any], *, role: str) -> None:
    validate_image_record_v1(record)
    inspected = json.loads(
        run_command(
            ["docker", "image", "inspect", record["loaded_image_tag"]],
            timeout=30,
        ).stdout
    )
    if len(inspected) != 1 or inspected[0].get("Id") != record["loaded_image_id"]:
        raise ValueError(f"{role} loaded image identity changed")


def verify_evaluator(protocol: dict[str, Any]) -> None:
    evaluator = protocol.get("official_evaluator", {})
    if evaluator != EXPECTED_OFFICIAL_EVALUATOR:
        raise ValueError("official evaluator identity changed")
    _inspect_loaded_image(evaluator["image"], role="official evaluator")


def _directory_has_files(path: Path) -> bool:
    return path.exists() and any(row.is_file() for row in path.rglob("*"))


def verify_information_state(protocol: dict[str, Any]) -> None:
    partition = protocol["partition"]
    current = transfer_paths(partition)
    if current.output_path.exists():
        raise ValueError("exact-mutation partition result already exists")
    holdout = transfer_paths("mechanism_holdout")
    if partition == "adapter_development" and (
        holdout.output_path.exists()
        or _directory_has_files(holdout.claim_directory)
        or _directory_has_files(holdout.episode_directory)
    ):
        raise ValueError("mechanism holdout was opened before development completed")


def verify_protocol(
    path: Path,
    expected_sha256: str,
) -> tuple[dict[str, Any], str, dict[str, Any] | None]:
    actual = c444.sha256(path)
    if actual != expected_sha256:
        raise ValueError(f"exact-mutation transfer protocol changed: {actual}")
    protocol = c414.load_json(path)
    partition = str(protocol.get("partition"))
    validate_protocol_shape(protocol, partition=partition)
    current_head = c444.git_head()
    c444.verify_clean_repository(ROOT, current_head)
    ancestor = subprocess.run(
        [
            "git",
            "-C",
            str(ROOT),
            "merge-base",
            "--is-ancestor",
            protocol["source_commit"],
            current_head,
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if ancestor.returncode != 0:
        raise ValueError("exact-mutation source commit is not an ancestor")
    development = (
        verify_development_activation(protocol)
        if partition == "mechanism_holdout"
        else None
    )
    if protocol.get("repositories") != EXPECTED_REPOSITORIES:
        raise ValueError("exact-mutation repository pins changed")
    for name, expected_head in EXPECTED_REPOSITORIES.items():
        c444.verify_clean_repository(REPOSITORY_PATHS[name], expected_head)
    if c444.sha256(INVENTORY_PATH) != protocol["official_source"][
        "offline_inventory_sha256"
    ]:
        raise ValueError("offline exact-mutation inventory changed")
    for site, image in protocol["official_images"].items():
        _inspect_loaded_image(image, role=f"official {site}")
    verify_evaluator(protocol)
    source_hashes = protocol.get("source_sha256", {})
    if not REQUIRED_SOURCE_PATHS.issubset(source_hashes):
        missing = sorted(REQUIRED_SOURCE_PATHS - set(source_hashes))
        raise ValueError(f"exact-mutation protocol omits source bindings: {missing}")
    for relative, expected in source_hashes.items():
        source = (ROOT / relative).resolve()
        try:
            source.relative_to(ROOT.resolve())
        except ValueError as error:
            raise ValueError(f"source binding escapes repository: {relative}") from error
        if not source.is_file() or c444.sha256(source) != expected:
            raise ValueError(f"exact-mutation source changed: {relative}")
    note = protocol.get("preregistration", {})
    if set(note) != {"path", "sha256"}:
        raise ValueError("exact-mutation preregistration binding changed")
    note_path = (ROOT / note["path"]).resolve()
    notes_root = (ROOT / "paper" / "aaai27" / "notes").resolve()
    try:
        note_path.relative_to(notes_root)
    except ValueError as error:
        raise ValueError("exact-mutation preregistration must live under paper notes") from error
    if not note_path.is_file() or c444.sha256(note_path) != note["sha256"]:
        raise ValueError("exact-mutation preregistration changed")
    verify_information_state(protocol)
    return protocol, actual, development


def claim_path(paths: TransferPathsV1, episode: dict[str, Any]) -> Path:
    return paths.claim_directory / f"{episode['episode_id']}.json"


def episode_path(paths: TransferPathsV1, episode: dict[str, Any]) -> Path:
    return paths.episode_directory / f"{episode['episode_id']}.json"


def completed_episode(
    paths: TransferPathsV1,
    episode: dict[str, Any],
    protocol_sha256: str,
) -> bool:
    claim = claim_path(paths, episode)
    result = episode_path(paths, episode)
    if not claim.exists() and not result.exists():
        return False
    if not claim.is_file() or not result.is_file():
        raise RuntimeError(
            f"exact-mutation episode has unmatched claim/result: {episode['episode_id']}"
        )
    claim_row = c414.load_json(claim)
    result_row = c414.load_json(result)
    if not (
        claim_row.get("status") == "complete"
        and claim_row.get("episode") == episode
        and claim_row.get("protocol_sha256") == protocol_sha256
        and claim_row.get("episode_sha256") == c444.sha256(result)
        and result_row.get("complete") is True
        and result_row.get("episode") == episode
        and result_row.get("protocol_sha256") == protocol_sha256
    ):
        raise RuntimeError(
            f"incompatible exact-mutation episode: {episode['episode_id']}"
        )
    return True


def open_claim(
    paths: TransferPathsV1,
    episode: dict[str, Any],
    protocol_sha256: str,
) -> None:
    path = claim_path(paths, episode)
    if path.exists() or episode_path(paths, episode).exists():
        raise FileExistsError(
            f"exact-mutation episode already opened: {episode['episode_id']}"
        )
    c414.atomic_write_json(
        path,
        {
            "candidate": "WebArena-exact-mutation-open-claim-v1",
            "created_utc": c427.utc_now(),
            "status": "claimed_before_container_start_and_reset",
            "protocol_sha256": protocol_sha256,
            "episode": episode,
        },
    )


def complete_claim(
    paths: TransferPathsV1,
    episode: dict[str, Any],
    protocol_sha256: str,
    result_path: Path,
) -> None:
    c414.atomic_write_json(
        claim_path(paths, episode),
        {
            "candidate": "WebArena-exact-mutation-open-claim-v1",
            "completed_utc": c427.utc_now(),
            "status": "complete",
            "protocol_sha256": protocol_sha256,
            "episode": episode,
            "episode_sha256": c444.sha256(result_path),
        },
    )


def evaluator_config(protocol: dict[str, Any]) -> dict[str, Any]:
    return {
        "environments": {
            "__REDDIT__": {
                "urls": [public_site_base_v1("reddit", 20999)]
            },
            "__GITLAB__": {
                "urls": [public_site_base_v1("gitlab", 22023)]
            },
            "__SHOPPING_ADMIN__": {
                "urls": [public_site_base_v1("shopping_admin", 22780)]
            },
            "__SHOPPING__": {
                "urls": [public_site_base_v1("shopping", 22770)]
            },
        }
    }


def ensure_evaluator_config(paths: TransferPathsV1, protocol: dict[str, Any]) -> None:
    expected = evaluator_config(protocol)
    if paths.evaluator_config_path.exists():
        if c414.load_json(paths.evaluator_config_path) != expected:
            raise ValueError("existing evaluator config changed")
    else:
        c414.atomic_write_json(paths.evaluator_config_path, expected)


def runtime_credentials(site: str) -> tuple[dict[str, str], tuple[str, ...]]:
    names = CREDENTIAL_ENV[site]
    values = tuple(os.environ.get(name, "") for name in names)
    if site == "gitlab":
        credentials = validate_runtime_credentials_v1(
            site,
            username=values[0],
            password=values[1],
        )
        secrets = (values[1],)
    else:
        credentials = validate_runtime_credentials_v1(
            site,
            autologin_value=values[0],
        )
        secrets = (values[0], values[0].split(":", 1)[1])
    return credentials, tuple(secret for secret in secrets if secret)


def _safe_error(error: object, secrets: tuple[str, ...]) -> str:
    value = str(error)
    for secret in sorted(set(secrets), key=len, reverse=True):
        value = value.replace(secret, "<redacted-harness-credential>")
    return value


def write_minimal_har(path: Path) -> None:
    if not path.exists():
        c414.atomic_write_json(
            path,
            {
                "log": {
                    "version": "1.2",
                    "creator": {"name": "PACT infrastructure fallback", "version": "1"},
                    "entries": [],
                }
            },
        )


def fallback_agent_result(goal: str, failure: str) -> dict[str, Any]:
    return {
        "candidate": "WebArena-exact-mutation-agent-v1-episode",
        "complete": True,
        "method_commit_effective": False,
        "typed_target_form_reached": False,
        "method_failure": failure,
        "infrastructure_failure": True,
        "infrastructure_error": failure,
        "method_input": {
            "goal": goal,
            "goal_sha256": c414.text_sha256(goal),
            "controller_arm": ExactMutationTransferAgentV1.method_id,
            "method_received_task_id": False,
            "method_received_seed": False,
            "method_received_reward": False,
            "method_received_evaluator_fields": False,
            "method_received_hidden_state": False,
            "method_received_site_specific_route": False,
        },
        "evaluation_audit": {
            "reward_observed_by_harness": False,
            "evaluator_info_observed_by_harness": False,
            "reward_or_info_forwarded_to_method": False,
            "official_evaluator_called_by_method": False,
        },
        "goal_compilation": None,
        "trace": [],
        "actions": [],
        "navigation_history": [],
        "navigation_effects": [],
        "restorations": [],
        "runtime_events": [],
        "active_transactions_at_stop": [],
        "completed_transactions_at_stop": [],
        "resolved_exact_transaction_bids": [],
        "effect_ledger_v8": [],
        "metrics": {
            "gui_actions": 0,
            "navigation_actions": 0,
            "navigation_effect_passes": 0,
            "navigation_effect_failures": 0,
            "quarantined_navigation_keys": 0,
            "planner_calls": 0,
            "planner_actual_calls": 0,
            "planner_cache_hits": 0,
            "planner_parse_failures": 0,
            "typed_transactions": 0,
            "certified_commits": 0,
            "uncertified_commits": 0,
            "restoration_attempts": 0,
            "restoration_passes": 0,
            "wrong_terminal_commits": 0,
            "terminal_transactions": 0,
            "action_errors": 0,
            "commit_effect_passes": 0,
            "commit_effect_failures": 0,
            "quarantined_commit_keys": 0,
            "resolved_transaction_bids": 0,
            "inverse_reservation_audits": 0,
            "inverse_reservation_stops": 0,
            "runtime_halted": False,
            "runtime_halt_reason": None,
            "wall_seconds": 0.0,
        },
    }


def write_agent_response(path: Path, agent_result: dict[str, Any]) -> None:
    success = agent_result.get("method_commit_effective") is True
    c414.atomic_write_json(
        path,
        {
            "task_type": "MUTATE",
            "status": "SUCCESS" if success else "UNKNOWN_ERROR",
            "retrieved_data": None,
            "error_details": None if success else agent_result.get("method_failure"),
        },
    )


def evaluate_official(
    *,
    protocol: dict[str, Any],
    paths: TransferPathsV1,
    episode: dict[str, Any],
    task_directory: Path,
) -> dict[str, Any]:
    call_claim = task_directory / "evaluation_call_claim.json"
    result_path = task_directory / "eval_result.json"
    if call_claim.exists() or result_path.exists():
        raise FileExistsError("official evaluator was already called for this episode")
    c414.atomic_write_json(
        call_claim,
        {
            "candidate": "WebArena-official-evaluator-call-claim-v1",
            "created_utc": c427.utc_now(),
            "status": "claimed_before_offline_evaluator_call",
            "task_id": episode["task_id"],
        },
    )
    evaluator = protocol["official_evaluator"]
    command = [
        "docker",
        "run",
        "--rm",
        "--network",
        "none",
        "-v",
        f"{paths.official_output_directory.resolve()}:/output",
        "-v",
        f"{paths.evaluator_config_path.resolve()}:/config.json:ro",
        evaluator["image"]["loaded_image_tag"],
        "eval-tasks",
        "--config",
        "/config.json",
        "--output-dir",
        "/output",
        "--task-ids",
        str(episode["task_id"]),
    ]
    completed = run_command(command, timeout=300, check=False)
    log_path = task_directory / "evaluator.log"
    log_path.write_text(
        completed.stdout + completed.stderr,
        encoding="utf-8",
    )
    if not result_path.is_file():
        c414.atomic_write_json(
            call_claim,
            {
                "candidate": "WebArena-official-evaluator-call-claim-v1",
                "completed_utc": c427.utc_now(),
                "status": "complete_without_result",
                "task_id": episode["task_id"],
                "returncode": completed.returncode,
                "log_sha256": c444.sha256(log_path),
            },
        )
        return {
            "calls": 1,
            "passed": False,
            "score": 0.0,
            "status": "evaluator_infrastructure_failure",
            "returncode": completed.returncode,
            "result_path": None,
            "result_sha256": None,
            "checksums_exact": False,
            "infrastructure_failure": True,
        }
    result = c414.load_json(result_path)
    checksums_exact = bool(
        result.get("task_id") == episode["task_id"]
        and result.get("webarena_verified_version") == EVALUATOR_VERSION
        and result.get("webarena_verified_evaluator_checksum")
        == EVALUATOR_CHECKSUM
        and result.get("webarena_verified_data_checksum")
        == OFFICIAL_DATASET_SHA256
    )
    passed = bool(
        checksums_exact
        and result.get("status") == "success"
        and float(result.get("score", 0.0)) == 1.0
    )
    c414.atomic_write_json(
        call_claim,
        {
            "candidate": "WebArena-official-evaluator-call-claim-v1",
            "completed_utc": c427.utc_now(),
            "status": "complete",
            "task_id": episode["task_id"],
            "returncode": completed.returncode,
            "result_sha256": c444.sha256(result_path),
            "log_sha256": c444.sha256(log_path),
        },
    )
    return {
        "calls": 1,
        "passed": passed,
        "score": float(result.get("score", 0.0)),
        "status": str(result.get("status", "")),
        "returncode": completed.returncode,
        "result_path": str(result_path.relative_to(ROOT)),
        "result_sha256": c444.sha256(result_path),
        "checksums_exact": checksums_exact,
        "infrastructure_failure": not checksums_exact,
    }


def execute_episode(
    *,
    protocol: dict[str, Any],
    protocol_sha256: str,
    paths: TransferPathsV1,
    episode: dict[str, Any],
    planner_generate: Any,
) -> dict[str, Any]:
    task_directory = paths.official_output_directory / str(episode["task_id"])
    if task_directory.exists() and _directory_has_files(task_directory):
        raise FileExistsError("official task output directory was already opened")
    task_directory.mkdir(parents=True, exist_ok=True)
    har_path = task_directory / "network.har"
    response_path = task_directory / "agent_response.json"
    credentials, secrets = runtime_credentials(episode["site"])
    container_record = None
    agent_result = None
    environment = None
    harness_failure = None
    reset_calls = 0
    try:
        with FreshWebArenaContainerV1(
            site=episode["site"],
            image_record=protocol["official_images"][episode["site"]],
            container_name=episode["container_name"],
            site_port=episode["site_port"],
            control_port=episode["control_port"],
            startup_timeout=float(
                protocol["runtime"]["container_startup_timeout_seconds"]
            ),
        ) as container_record:
            start_url = render_start_url_v1(
                episode["start_url_template"],
                site=episode["site"],
                host_port=episode["site_port"],
            )
            environment = make_webarena_environment_v1(
                site=episode["site"],
                start_url=start_url,
                goal=episode["intent"],
                credentials=credentials,
                har_path=har_path,
                pre_observation_delay=float(
                    protocol["runtime"]["pre_observation_delay_seconds"]
                ),
                timeout_ms=int(
                    protocol["runtime"]["browser_timeout_milliseconds"]
                ),
            )
            try:
                observation, _discarded_reset_info = environment.reset(
                    seed=episode["seed"]
                )
                reset_calls = 1
                agent = ExactMutationTransferAgentV1(
                    environment=environment,
                    observation=observation,
                    budgets=protocol["budgets"],
                    planner_generate=planner_generate,
                )
                try:
                    agent.run()
                except Exception as error:
                    harness_failure = _safe_error(
                        f"{type(error).__name__}: {error}", secrets
                    )
                agent_result = agent.result()
            finally:
                environment.close()
                environment = None
    except Exception as error:
        harness_failure = harness_failure or _safe_error(
            f"{type(error).__name__}: {error}", secrets
        )
    finally:
        if environment is not None:
            try:
                environment.close()
            except Exception as error:
                harness_failure = harness_failure or _safe_error(
                    f"environment close failed: {type(error).__name__}: {error}",
                    secrets,
                )
    container_removed = not exact_container_names_v1(episode["container_name"])
    if agent_result is None:
        agent_result = fallback_agent_result(
            episode["intent"],
            harness_failure or "episode failed before agent construction",
        )
    write_minimal_har(har_path)
    har_audit = sanitize_network_har_v1(har_path, forbidden_values=secrets)
    write_agent_response(response_path, agent_result)
    official = evaluate_official(
        protocol=protocol,
        paths=paths,
        episode=episode,
        task_directory=task_directory,
    )
    infrastructure_failure = bool(
        harness_failure
        or agent_result.get("infrastructure_failure")
        or official["infrastructure_failure"]
        or not container_removed
        or reset_calls != 1
    )
    if infrastructure_failure:
        agent_result["infrastructure_failure"] = True
        agent_result["infrastructure_error"] = harness_failure or agent_result.get(
            "infrastructure_error"
        ) or official["status"]
    runtime_integrity = {
        "protocol_sources_images_and_evaluator_verified": True,
        "fresh_container_started": container_record is not None,
        "fresh_container_removed": container_removed,
        "environment_reset_calls_exact": reset_calls == 1,
        "har_exists_and_sanitized": har_path.is_file()
        and har_audit["credential_material_remaining"] is False,
        "official_evaluator_checksums_exact": official["checksums_exact"],
    }
    runtime_integrity["passed"] = all(runtime_integrity.values())
    result = {
        **agent_result,
        "candidate": "WebArena-Verified-exact-mutation-episode-v1",
        "complete": True,
        "episode": episode,
        "protocol_sha256": protocol_sha256,
        "container": container_record,
        "container_removed": container_removed,
        "environment_reset_calls": reset_calls,
        "har_path": str(har_path.relative_to(ROOT)),
        "har_sha256": c444.sha256(har_path),
        "har_sanitization": har_audit,
        "agent_response_path": str(response_path.relative_to(ROOT)),
        "agent_response_sha256": c444.sha256(response_path),
        "official_evaluation": official,
        "runtime_integrity": runtime_integrity,
        "holdout_outcomes_opened": protocol["partition"] == "mechanism_holdout",
    }
    serialized = json.dumps(result, ensure_ascii=False, sort_keys=True)
    if any(secret in serialized for secret in secrets):
        raise RuntimeError("credential material entered the exact-mutation result")
    return result


def run_grid(
    *,
    protocol: dict[str, Any],
    protocol_sha256: str,
    model_path: Path,
) -> None:
    partition = protocol["partition"]
    paths = transfer_paths(partition)
    paths.episode_directory.mkdir(parents=True, exist_ok=True)
    paths.claim_directory.mkdir(parents=True, exist_ok=True)
    paths.official_output_directory.mkdir(parents=True, exist_ok=True)
    ensure_evaluator_config(paths, protocol)
    manifest = episode_manifest(partition)
    pending = [
        episode
        for episode in manifest
        if not completed_episode(paths, episode, protocol_sha256)
    ]
    if not pending:
        print(f"WebArena exact-mutation {partition} already complete", flush=True)
        return
    c444.MODEL_CACHE_PATH = paths.model_cache_path
    c444.MODEL_RUNTIME_PATH = paths.model_runtime_path
    service = c444.FrozenModelServiceV7(
        protocol=protocol,
        protocol_sha256=protocol_sha256,
        model_path=model_path,
    )
    try:
        for episode in pending:
            open_claim(paths, episode, protocol_sha256)
            result = execute_episode(
                protocol=protocol,
                protocol_sha256=protocol_sha256,
                paths=paths,
                episode=episode,
                planner_generate=service.generate,
            )
            path = episode_path(paths, episode)
            c414.atomic_write_json(path, result)
            complete_claim(paths, episode, protocol_sha256, path)
            print(
                json.dumps(
                    {
                        "complete": episode["episode_index"] + 1,
                        "total": len(manifest),
                        "episode_id": episode["episode_id"],
                        "official_success": result["official_evaluation"]["passed"],
                    }
                ),
                flush=True,
            )
            if result["infrastructure_failure"]:
                raise RuntimeError(
                    "exact-mutation grid stopped after sealing an infrastructure failure"
                )
    finally:
        service.close()


def finalize(
    protocol_path: Path,
    protocol: dict[str, Any],
    protocol_sha256: str,
) -> None:
    partition = protocol["partition"]
    paths = transfer_paths(partition)
    if paths.output_path.exists():
        raise FileExistsError(paths.output_path)
    if not paths.model_runtime_path.is_file() or not paths.model_cache_path.is_file():
        raise FileNotFoundError("exact-mutation model runtime or cache is absent")
    manifest = episode_manifest(partition)
    rows = []
    compact = []
    for episode in manifest:
        if not completed_episode(paths, episode, protocol_sha256):
            raise RuntimeError(
                f"incomplete exact-mutation episode: {episode['episode_id']}"
            )
        path = episode_path(paths, episode)
        row = c414.load_json(path)
        rows.append(row)
        compact.append(
            {
                "episode": episode,
                "artifact_sha256": c444.sha256(path),
                "official_success": row["official_evaluation"]["passed"],
                "method_commit_effective": row["method_commit_effective"],
                "method_failure": row["method_failure"],
                "infrastructure_failure": row["infrastructure_failure"],
                "metrics": row["metrics"],
            }
        )
    all_claims_complete = all(
        c414.load_json(claim_path(paths, episode)).get("status") == "complete"
        for episode in manifest
    )
    analysis = analyze_transfer_rows(
        rows,
        partition=partition,
        all_claims_complete=all_claims_complete,
    )
    claim_manifest = {
        episode["episode_id"]: c444.sha256(claim_path(paths, episode))
        for episode in manifest
    }
    passed = bool(analysis["passed"])
    development = partition == "adapter_development"
    payload = {
        "candidate": (
            "WebArena-Verified-exact-mutation-development-v1"
            if development
            else "WebArena-Verified-exact-mutation-holdout-v1"
        ),
        "created_utc": c427.utc_now(),
        "git_head": c444.git_head(),
        "status": "development_complete" if development else "holdout_complete",
        "protocol": str(protocol_path.resolve().relative_to(ROOT.resolve())),
        "protocol_sha256": protocol_sha256,
        "partition": partition,
        "development_states_opened": True,
        "holdout_states_opened": not development,
        "development_task_ids": [399, 449, 488],
        "holdout_task_ids": [400, 401, 418, 451, 489, 797],
        "model_runtime": str(paths.model_runtime_path.relative_to(ROOT)),
        "model_runtime_sha256": c444.sha256(paths.model_runtime_path),
        "planner_cache": str(paths.model_cache_path.relative_to(ROOT)),
        "planner_cache_sha256": c444.sha256(paths.model_cache_path),
        "evaluator_config": str(paths.evaluator_config_path.relative_to(ROOT)),
        "evaluator_config_sha256": c444.sha256(paths.evaluator_config_path),
        "claim_manifest": claim_manifest,
        "claim_manifest_sha256": c444.object_sha256(claim_manifest),
        "episode_rows": compact,
        **analysis,
        "next_step": protocol["decision_rule"][
            "on_pass" if passed else "on_failure"
        ],
    }
    c414.atomic_write_json(paths.output_path, payload)
    print(
        json.dumps(
            {
                "passed": passed,
                "partition": partition,
                "metrics": analysis["metrics"],
                "checks": analysis["checks"],
            },
            indent=2,
        )
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--stage", choices=("preflight", "run", "finalize"), required=True
    )
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--expected-protocol-sha256", required=True)
    parser.add_argument("--model-path", type=Path, default=DEFAULT_MODEL_PATH)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    protocol, protocol_sha256, _development = verify_protocol(
        args.protocol, args.expected_protocol_sha256
    )
    paths = transfer_paths(protocol["partition"])
    c444.MODEL_CACHE_PATH = paths.model_cache_path
    c444.MODEL_RUNTIME_PATH = paths.model_runtime_path
    if args.stage == "preflight":
        ensure_evaluator_config(paths, protocol)
        print(
            json.dumps(
                {
                    "protocol_sha256": protocol_sha256,
                    "partition": protocol["partition"],
                    "episodes": len(episode_manifest(protocol["partition"])),
                    "opened_claims": sum(
                        claim_path(paths, row).is_file()
                        for row in episode_manifest(protocol["partition"])
                    ),
                    "holdout_states_opened": False,
                },
                indent=2,
            )
        )
    elif args.stage == "run":
        run_grid(
            protocol=protocol,
            protocol_sha256=protocol_sha256,
            model_path=args.model_path,
        )
    else:
        finalize(args.protocol, protocol, protocol_sha256)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
