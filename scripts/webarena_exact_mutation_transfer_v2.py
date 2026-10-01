#!/usr/bin/env python3
"""Run the source-versioned exact-mutation transfer successor.

The development stage reuses only the already-open development task IDs.  A
passing, source-bound V2 development artifact is then the sole parent that can
authorize the still-unopened mechanism holdout.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT / "src", ROOT / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import webarena_exact_mutation_transfer_v1 as legacy  # noqa: E402
from rcrps.webarena_exact_mutation_agent_v2 import (  # noqa: E402
    ExactMutationTransferAgentV2,
)
from rcrps.webarena_exact_mutation_transfer_v2 import (  # noqa: E402
    DEVELOPMENT_RESULT_V2_RELATIVE,
    PACT_V10_EQUIVALENCE_RELATIVE,
    PREDECESSOR_PROTOCOL_RELATIVE,
    PREDECESSOR_RESULT_RELATIVE,
    REQUIRED_SOURCE_PATHS_V2,
    analyze_transfer_rows_v2,
    evaluator_config_v2,
    official_component_audit_v2,
    successor_audit_path,
    validate_protocol_shape_v2,
)


DEVELOPMENT_OUTPUT_V2 = ROOT / DEVELOPMENT_RESULT_V2_RELATIVE
HOLDOUT_OUTPUT_V2 = (
    ROOT / "validation" / "webarena_verified_exact_mutation_holdout_v2.json"
)
RUN_ROOT_V2 = ROOT / "runs" / "webarena_verified_exact_mutation_transfer_v2"
_LEGACY_EVALUATE_OFFICIAL = legacy.evaluate_official


def evaluate_official_v2(
    *,
    protocol: dict[str, Any],
    paths: legacy.TransferPathsV1,
    episode: dict[str, Any],
    task_directory: Path,
) -> dict[str, Any]:
    """Require both a clean evaluator process and exact official components."""

    summary = _LEGACY_EVALUATE_OFFICIAL(
        protocol=protocol,
        paths=paths,
        episode=episode,
        task_directory=task_directory,
    )
    result_path = task_directory / "eval_result.json"
    raw = legacy.c414.load_json(result_path) if result_path.is_file() else None
    components = official_component_audit_v2(raw)
    process_ok = summary.get("returncode") == 0
    component_integrity = bool(
        components["identity_exact"]
        and components["top_level_consistent"]
        and components["error_count"] == 0
    )
    summary.update(
        {
            "process_returncode_zero": process_ok,
            "component_identity_exact": components["identity_exact"],
            "component_all_passed": components["all_passed"],
            "component_top_level_consistent": components[
                "top_level_consistent"
            ],
            "component_error_count": components["error_count"],
            "component_results": components["components"],
        }
    )
    summary["passed"] = bool(
        summary.get("passed") and process_ok and component_integrity
    )
    summary["infrastructure_failure"] = bool(
        summary.get("infrastructure_failure")
        or not process_ok
        or not component_integrity
    )
    return summary


def _exact_reference(
    reference: dict[str, Any],
    *,
    expected_relative: str,
    role: str,
) -> tuple[Path, dict[str, Any]]:
    path = legacy._artifact_path(reference, role=role)
    expected = (ROOT / expected_relative).resolve()
    if path != expected:
        raise ValueError(f"{role} must bind {expected_relative}")
    return path, legacy.c414.load_json(path)


def verify_v2_development_activation(protocol: dict[str, Any]) -> dict[str, Any]:
    """Authorize holdout only from the passing V2 development successor."""

    reference = protocol["activation"]["development_result"]
    _path, result = _exact_reference(
        reference,
        expected_relative=DEVELOPMENT_RESULT_V2_RELATIVE,
        role="V2 exact-mutation development",
    )
    if not (
        result.get("candidate")
        == "WebArena-Verified-exact-mutation-development-v2"
        and result.get("status") == "development_complete"
        and result.get("passed") is True
        and result.get("development_states_opened") is True
        and result.get("holdout_states_opened") is False
        and result.get("metrics", {}).get("episodes") == 3
        and result.get("development_task_ids") == [399, 449, 488]
        and isinstance(result.get("checks"), dict)
        and all(value is True for value in result["checks"].values())
    ):
        raise ValueError("V2 development result does not authorize holdout")
    return result


def verify_v1_predecessor_completion(protocol: dict[str, Any]) -> None:
    """Retain the full V1 diagnostic outcome before any V2 development run."""

    activation = protocol["activation"]
    _protocol_path, predecessor_protocol = _exact_reference(
        activation["predecessor_protocol"],
        expected_relative=PREDECESSOR_PROTOCOL_RELATIVE,
        role="V1 development protocol",
    )
    if not (
        predecessor_protocol.get("candidate")
        == "WebArena-Verified-exact-mutation-development-protocol-v1"
        and predecessor_protocol.get("partition") == "adapter_development"
        and predecessor_protocol.get("status")
        == "sealed_before_development_states_opened"
    ):
        raise ValueError("V1 predecessor protocol is invalid")
    _result_path, result = _exact_reference(
        activation["predecessor_result"],
        expected_relative=PREDECESSOR_RESULT_RELATIVE,
        role="V1 development result",
    )
    rows = result.get("episode_rows")
    if not (
        result.get("candidate")
        == "WebArena-Verified-exact-mutation-development-v1"
        and result.get("status") == "development_complete"
        and result.get("development_states_opened") is True
        and result.get("holdout_states_opened") is False
        and result.get("metrics", {}).get("episodes") == 3
        and result.get("development_task_ids") == [399, 449, 488]
        and isinstance(rows, list)
        and len(rows) == 3
    ):
        raise ValueError("V1 predecessor result is not a complete diagnostic")


def verify_pact_v10_trace_equivalence(protocol: dict[str, Any]) -> None:
    """Bind WebArena V2 to the same passing recovery-solvent source lineage."""

    _path, result = _exact_reference(
        protocol["activation"]["pact_v10_trace_equivalence"],
        expected_relative=PACT_V10_EQUIVALENCE_RELATIVE,
        role="PACT-v10 trace equivalence",
    )
    if not (
        result.get("candidate") == "C453-PACT-v10-trace-equivalence"
        and result.get("status") == "trace_equivalence_derivation_complete"
        and result.get("derivation_only") is True
        and result.get("environment_resets") == 0
        and result.get("passed") is True
        and result.get("repair_holdout_opened") is False
        and result.get("final_confirmation_opened") is False
        and result.get("metrics", {}).get("episodes") == 120
        and result.get("metrics", {}).get("interrupt_repairs", 0) >= 1
    ):
        raise ValueError("C453 does not authorize PACT-v10 WebArena V2")


def configure_legacy_for_v2() -> None:
    """Patch the reusable runner namespace without editing V1 source."""

    legacy.ExactMutationTransferAgentV1 = ExactMutationTransferAgentV2
    legacy.analyze_transfer_rows = analyze_transfer_rows_v2
    legacy.validate_protocol_shape = validate_protocol_shape_v2
    legacy.REQUIRED_SOURCE_PATHS = REQUIRED_SOURCE_PATHS_V2
    legacy.DEVELOPMENT_OUTPUT = DEVELOPMENT_OUTPUT_V2
    legacy.HOLDOUT_OUTPUT = HOLDOUT_OUTPUT_V2
    legacy.RUN_ROOT = RUN_ROOT_V2
    legacy.evaluator_config = evaluator_config_v2
    legacy.evaluate_official = evaluate_official_v2
    legacy.verify_development_activation = verify_v2_development_activation


def verify_protocol_v2(
    path: Path,
    expected_sha256: str,
) -> tuple[dict[str, Any], str, dict[str, Any] | None]:
    configure_legacy_for_v2()
    protocol, protocol_sha256, development = legacy.verify_protocol(
        path,
        expected_sha256,
    )
    audit = protocol["successor_audit"]
    audit_path = successor_audit_path(ROOT)
    if not audit_path.is_file() or legacy.c444.sha256(audit_path) != audit["sha256"]:
        raise ValueError("V2 successor audit changed")
    verify_pact_v10_trace_equivalence(protocol)
    if protocol["partition"] == "adapter_development":
        verify_v1_predecessor_completion(protocol)
    elif protocol["partition"] != "mechanism_holdout":
        raise ValueError("V2 runner received an unknown partition")
    return protocol, protocol_sha256, development


def finalize_v2(
    protocol_path: Path,
    protocol: dict[str, Any],
    protocol_sha256: str,
) -> None:
    partition = protocol["partition"]
    paths = legacy.transfer_paths(partition)
    if paths.output_path.exists():
        raise FileExistsError(paths.output_path)
    if not paths.model_runtime_path.is_file() or not paths.model_cache_path.is_file():
        raise FileNotFoundError("exact-mutation model runtime or cache is absent")
    manifest = legacy.episode_manifest(partition)
    rows = []
    compact = []
    for episode in manifest:
        if not legacy.completed_episode(paths, episode, protocol_sha256):
            raise RuntimeError(
                f"incomplete exact-mutation episode: {episode['episode_id']}"
            )
        episode_path = legacy.episode_path(paths, episode)
        row = legacy.c414.load_json(episode_path)
        rows.append(row)
        unresolved_failed = bool(
            row.get("method_commit_effective") is not True
            and row.get("active_transactions_at_stop")
        )
        official = row["official_evaluation"]
        compact.append(
            {
                "episode": episode,
                "artifact_sha256": legacy.c444.sha256(episode_path),
                "official_success": official["passed"],
                "official_evaluator": {
                    "result_sha256": official["result_sha256"],
                    "returncode": official["returncode"],
                    "process_returncode_zero": official[
                        "process_returncode_zero"
                    ],
                    "component_identity_exact": official[
                        "component_identity_exact"
                    ],
                    "component_all_passed": official["component_all_passed"],
                    "component_top_level_consistent": official[
                        "component_top_level_consistent"
                    ],
                    "component_error_count": official["component_error_count"],
                    "component_results": official["component_results"],
                },
                "method_commit_effective": row["method_commit_effective"],
                "typed_target_form_reached": row["typed_target_form_reached"],
                "controller_arm": row["method_input"]["controller_arm"],
                "unresolved_failed_transaction": unresolved_failed,
                "method_failure": row["method_failure"],
                "infrastructure_failure": row["infrastructure_failure"],
                "metrics": row["metrics"],
            }
        )
    all_claims_complete = all(
        legacy.c414.load_json(legacy.claim_path(paths, episode)).get("status")
        == "complete"
        for episode in manifest
    )
    analysis = analyze_transfer_rows_v2(
        rows,
        partition=partition,
        all_claims_complete=all_claims_complete,
    )
    claim_manifest = {
        episode["episode_id"]: legacy.c444.sha256(
            legacy.claim_path(paths, episode)
        )
        for episode in manifest
    }
    development = partition == "adapter_development"
    passed = bool(analysis["passed"])
    payload = {
        "candidate": (
            "WebArena-Verified-exact-mutation-development-v2"
            if development
            else "WebArena-Verified-exact-mutation-holdout-v2"
        ),
        "created_utc": legacy.c427.utc_now(),
        "git_head": legacy.c444.git_head(),
        "status": "development_complete" if development else "holdout_complete",
        "protocol": str(protocol_path.resolve().relative_to(ROOT.resolve())),
        "protocol_sha256": protocol_sha256,
        "partition": partition,
        "development_states_opened": True,
        "holdout_states_opened": not development,
        "development_task_ids": [399, 449, 488],
        "holdout_task_ids": [400, 401, 418, 451, 489, 797],
        "activation": protocol["activation"],
        "state_boundary": protocol["state_boundary"],
        "successor_audit": protocol["successor_audit"],
        "successor_changes": protocol["successor_changes"],
        "model_runtime": str(paths.model_runtime_path.relative_to(ROOT)),
        "model_runtime_sha256": legacy.c444.sha256(paths.model_runtime_path),
        "planner_cache": str(paths.model_cache_path.relative_to(ROOT)),
        "planner_cache_sha256": legacy.c444.sha256(paths.model_cache_path),
        "evaluator_config": str(paths.evaluator_config_path.relative_to(ROOT)),
        "evaluator_config_sha256": legacy.c444.sha256(
            paths.evaluator_config_path
        ),
        "claim_manifest": claim_manifest,
        "claim_manifest_sha256": legacy.c444.object_sha256(claim_manifest),
        "episode_rows": compact,
        **analysis,
        "next_step": protocol["decision_rule"][
            "on_pass" if passed else "on_failure"
        ],
    }
    legacy.c414.atomic_write_json(paths.output_path, payload)
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
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--expected-protocol-sha256", required=True)
    parser.add_argument(
        "--stage", choices=("preflight", "run", "finalize"), required=True
    )
    parser.add_argument("--model-path", type=Path, default=legacy.DEFAULT_MODEL_PATH)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    protocol, protocol_sha256, _development = verify_protocol_v2(
        args.protocol,
        args.expected_protocol_sha256,
    )
    paths = legacy.transfer_paths(protocol["partition"])
    legacy.c444.MODEL_CACHE_PATH = paths.model_cache_path
    legacy.c444.MODEL_RUNTIME_PATH = paths.model_runtime_path
    if args.stage == "preflight":
        expected_config = evaluator_config_v2(protocol)
        legacy.ensure_evaluator_config(paths, protocol)
        actual_config = legacy.c414.load_json(paths.evaluator_config_path)
        if actual_config != expected_config:
            raise ValueError("V2 evaluator config changed during preflight")
        print(
            json.dumps(
                {
                    "protocol_sha256": protocol_sha256,
                    "partition": protocol["partition"],
                    "episodes": len(
                        legacy.episode_manifest(protocol["partition"])
                    ),
                    "opened_claims": sum(
                        legacy.claim_path(paths, row).is_file()
                        for row in legacy.episode_manifest(protocol["partition"])
                    ),
                    "holdout_states_opened": False,
                    "evaluator_origins": actual_config["environments"],
                },
                indent=2,
            )
        )
    elif args.stage == "run":
        legacy.run_grid(
            protocol=protocol,
            protocol_sha256=protocol_sha256,
            model_path=args.model_path,
        )
    else:
        finalize_v2(args.protocol, protocol, protocol_sha256)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
