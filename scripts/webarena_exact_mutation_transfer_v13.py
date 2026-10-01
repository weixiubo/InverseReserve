#!/usr/bin/env python3
"""Re-execute a passing-parent activated WebArena V2 stage under PACT-v13."""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT / "src", ROOT / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import pact_v13_reexecution_common as common  # noqa: E402
import webarena_exact_mutation_transfer_v1 as legacy  # noqa: E402
import webarena_exact_mutation_transfer_v2 as v2  # noqa: E402
from rcrps.webarena_exact_mutation_agent_v13 import (  # noqa: E402
    ExactMutationTransferAgentV13,
)


DEVELOPMENT_OUTPUT_V13 = (
    ROOT
    / common.template_runner.EXPECTED_STAGES["webarena_development"][
        "replacement_result"
    ]
)
HOLDOUT_OUTPUT_V13 = (
    ROOT
    / common.template_runner.EXPECTED_STAGES["webarena_holdout"][
        "replacement_result"
    ]
)
RUN_ROOT_V13 = ROOT / "runs" / "webarena_verified_exact_mutation_transfer_v13"
_ANALYZE_V2 = v2.analyze_transfer_rows_v2
METHOD_V10 = "full_pact_v10_webarena_exact_mutation_v2"
METHOD_V13 = "full_pact_v13_webarena_exact_mutation_v2"


def configure_legacy_for_v13() -> None:
    """Preserve the V2 harness and replace only paths and transaction agent."""

    v2.configure_legacy_for_v2()
    legacy.ExactMutationTransferAgentV1 = ExactMutationTransferAgentV13
    legacy.DEVELOPMENT_OUTPUT = DEVELOPMENT_OUTPUT_V13
    legacy.HOLDOUT_OUTPUT = HOLDOUT_OUTPUT_V13
    legacy.RUN_ROOT = RUN_ROOT_V13


def stage_name_for_partition(partition: str) -> str:
    if partition == "adapter_development":
        return "webarena_development"
    if partition == "mechanism_holdout":
        return "webarena_holdout"
    raise ValueError(f"unknown WebArena v13 partition: {partition}")


def partition_for_stage(stage_name: str) -> str:
    if stage_name == "webarena_development":
        return "adapter_development"
    if stage_name == "webarena_holdout":
        return "mechanism_holdout"
    raise ValueError(f"unknown WebArena v13 stage: {stage_name}")


def verify_inputs(
    *,
    stage_name: str,
    activation_path: Path,
    expected_activation_sha256: str,
) -> tuple[dict[str, Any], dict[str, Any], str, list[dict[str, Any]]]:
    activation, parent_protocol, activation_sha256 = (
        common.verify_activation_protocol(
            activation_path,
            expected_activation_sha256,
            stage_name=stage_name,
        )
    )
    parent_path = ROOT / activation["parent_protocol"]["path"]
    verified, parent_sha256, _development = v2.verify_protocol_v2(
        parent_path,
        activation["parent_protocol"]["sha256"],
    )
    if verified != parent_protocol or parent_sha256 != activation[
        "parent_protocol"
    ]["sha256"]:
        raise ValueError("WebArena V2 parent protocol changed during verification")
    partition = partition_for_stage(stage_name)
    if parent_protocol.get("partition") != partition:
        raise ValueError("WebArena v13 stage differs from its parent partition")
    configure_legacy_for_v13()
    manifest = legacy.episode_manifest(partition)
    expected = common.template_runner.EXPECTED_STAGES[stage_name]["episodes"]
    if len(manifest) != expected:
        raise ValueError("WebArena v13 complete population changed")
    return activation, parent_protocol, activation_sha256, manifest


def _normalize_controller_for_v2(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    output = copy.deepcopy(list(rows))
    for row in output:
        method_input = row.get("method_input")
        if not isinstance(method_input, dict):
            raise ValueError("WebArena v13 row omits method input")
        if method_input.get("controller_arm") != METHOD_V13:
            raise ValueError("WebArena v13 row has an unexpected controller arm")
        method_input["controller_arm"] = METHOD_V10
    return output


def _v13_runtime_audit(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    rows = tuple(rows)
    accounting_rows = []
    for row in rows:
        events = row.get("runtime_events", [])
        metrics = row.get("metrics", {})
        event_checks = sum(
            event.get("type") == "complete_public_observation_check_v12"
            for event in events
        )
        event_skips = sum(
            event.get("type") == "complete_public_no_effect_certificate_v12"
            and event.get("passed") is True
            and event.get("inverse_skipped") is True
            for event in events
        )
        restoration_skips = sum(
            event.get("type") == "restoration"
            and event.get("inverse_skipped") is True
            and event.get("certificate_scope") == "complete_public_snapshot"
            for event in events
        )
        commit_checks = sum(
            event.get("type") == "complete_public_commit_observation_check_v13"
            for event in events
        )
        commit_passes = sum(
            event.get("type") == "complete_public_commit_observation_check_v13"
            and event.get("passed") is True
            for event in events
        )
        commit_rejections = sum(
            event.get("type") == "complete_public_commit_observation_check_v13"
            and event.get("passed") is False
            for event in events
        )
        metric_checks = metrics.get("complete_public_observation_checks_v12")
        metric_skips = metrics.get("complete_public_inverse_skips_v12")
        metric_commit_checks = metrics.get("complete_public_commit_checks_v13")
        metric_commit_passes = metrics.get("complete_public_commit_passes_v13")
        metric_commit_rejections = metrics.get(
            "complete_public_commit_rejections_v13"
        )
        accounting_rows.append(
            {
                "metric_checks": metric_checks,
                "metric_skips": metric_skips,
                "metric_commit_checks": metric_commit_checks,
                "metric_commit_passes": metric_commit_passes,
                "metric_commit_rejections": metric_commit_rejections,
                "exact": (
                    isinstance(metric_checks, int)
                    and metric_checks >= 0
                    and isinstance(metric_skips, int)
                    and metric_skips >= 0
                    and metric_checks == event_checks
                    and metric_skips == event_skips == restoration_skips
                    and metric_skips <= metric_checks
                    and isinstance(metric_commit_checks, int)
                    and metric_commit_checks >= 0
                    and isinstance(metric_commit_passes, int)
                    and metric_commit_passes >= 0
                    and isinstance(metric_commit_rejections, int)
                    and metric_commit_rejections >= 0
                    and metric_commit_checks == commit_checks
                    and metric_commit_passes == commit_passes
                    and metric_commit_rejections == commit_rejections
                    and metric_commit_checks
                    == metric_commit_passes + metric_commit_rejections
                ),
            }
        )
    accounting = bool(rows) and all(item["exact"] for item in accounting_rows)
    total_commit_checks = (
        sum(int(item["metric_commit_checks"]) for item in accounting_rows)
        if accounting
        else None
    )
    checks = {
        "controller_is_pact_v13": bool(rows)
        and all(
            row.get("method_input", {}).get("controller_arm") == METHOD_V13
            for row in rows
        ),
        "all_rows_report_complete_observation_guard": bool(rows)
        and all(
            isinstance(item["metric_checks"], int)
            and isinstance(item["metric_skips"], int)
            for item in accounting_rows
        ),
        "complete_observation_metrics_match_runtime_events": accounting,
        "all_rows_report_complete_commit_freshness": bool(rows)
        and all(
            isinstance(item["metric_commit_checks"], int)
            and isinstance(item["metric_commit_passes"], int)
            and isinstance(item["metric_commit_rejections"], int)
            for item in accounting_rows
        ),
        "complete_commit_metrics_match_runtime_events": accounting,
        "complete_commit_guard_is_exercised": (
            isinstance(total_commit_checks, int) and total_commit_checks > 0
        ),
    }
    return {
        "protected_rows": len(rows),
        "complete_public_observation_checks": (
            sum(int(item["metric_checks"]) for item in accounting_rows)
            if accounting
            else None
        ),
        "complete_public_inverse_skips": (
            sum(int(item["metric_skips"]) for item in accounting_rows)
            if accounting
            else None
        ),
        "complete_public_commit_checks": total_commit_checks,
        "complete_public_commit_passes": (
            sum(int(item["metric_commit_passes"]) for item in accounting_rows)
            if accounting
            else None
        ),
        "complete_public_commit_rejections": (
            sum(
                int(item["metric_commit_rejections"])
                for item in accounting_rows
            )
            if accounting
            else None
        ),
        "checks": checks,
        "passed": all(checks.values()),
    }


def analyze_transfer_rows_v13(
    rows: Iterable[dict[str, Any]],
    *,
    partition: str,
    all_claims_complete: bool,
) -> dict[str, Any]:
    rows = tuple(rows)
    normalized = _normalize_controller_for_v2(rows)
    analysis = _ANALYZE_V2(
        normalized,
        partition=partition,
        all_claims_complete=all_claims_complete,
    )
    analysis = common.remap_exact_labels(analysis, {METHOD_V10: METHOD_V13})
    v13_audit = _v13_runtime_audit(rows)
    checks = dict(analysis["checks"])
    if checks.pop("controller_is_pact_v10", None) is not True:
        raise ValueError("WebArena V2 parent analyzer lost its controller gate")
    checks.update(v13_audit["checks"])
    analysis["checks"] = checks
    analysis["metrics"] = {
        **analysis["metrics"],
        "v13_runtime_protected_rows": v13_audit["protected_rows"],
        "complete_public_observation_checks_v12": v13_audit[
            "complete_public_observation_checks"
        ],
        "complete_public_inverse_skips_v12": v13_audit[
            "complete_public_inverse_skips"
        ],
        "complete_public_commit_checks_v13": v13_audit[
            "complete_public_commit_checks"
        ],
        "complete_public_commit_passes_v13": v13_audit[
            "complete_public_commit_passes"
        ],
        "complete_public_commit_rejections_v13": v13_audit[
            "complete_public_commit_rejections"
        ],
    }
    analysis["v13_runtime_audit"] = v13_audit
    analysis["passed"] = bool(analysis["passed"] and v13_audit["passed"])
    return analysis


def run(
    *,
    parent_protocol: dict[str, Any],
    activation_sha256: str,
    model_path: Path,
) -> None:
    configure_legacy_for_v13()
    legacy.run_grid(
        protocol=parent_protocol,
        protocol_sha256=activation_sha256,
        model_path=model_path,
    )


def finalize(
    *,
    stage_name: str,
    activation_path: Path,
    activation: dict[str, Any],
    parent_protocol: dict[str, Any],
    activation_sha256: str,
) -> dict[str, Any]:
    configure_legacy_for_v13()
    partition = partition_for_stage(stage_name)
    paths = legacy.transfer_paths(partition)
    if paths.output_path.exists():
        raise FileExistsError(paths.output_path)
    captured: list[dict[str, Any]] = []
    original_writer = legacy.c414.atomic_write_json
    original_analyzer = v2.analyze_transfer_rows_v2

    def capture(path: Path, payload: dict[str, Any]) -> None:
        if Path(path).resolve() != paths.output_path.resolve() or captured:
            raise RuntimeError("WebArena v13 finalizer attempted an unexpected write")
        captured.append(payload)

    try:
        legacy.c414.atomic_write_json = capture
        v2.analyze_transfer_rows_v2 = analyze_transfer_rows_v13
        v2.finalize_v2(
            activation_path,
            parent_protocol,
            activation_sha256,
        )
    finally:
        v2.analyze_transfer_rows_v2 = original_analyzer
        legacy.c414.atomic_write_json = original_writer
    if len(captured) != 1:
        raise RuntimeError("WebArena v13 finalizer did not produce one payload")
    payload = captured[0]
    passed = bool(payload["passed"])
    parent_activation = payload["activation"]
    parent_successor_changes = payload["successor_changes"]
    if not isinstance(parent_successor_changes, dict):
        raise ValueError("WebArena V2 successor-change record changed")
    payload.update(
        {
            "candidate": (
                "WebArena-Verified-exact-mutation-development-v13"
                if partition == "adapter_development"
                else "WebArena-Verified-exact-mutation-holdout-v13"
            ),
            "stage": stage_name,
            "activation": {
                "path": str(activation_path.resolve().relative_to(ROOT.resolve())),
                "sha256": activation_sha256,
            },
            "parent_protocol_activation": parent_activation,
            "correction_protocol": activation["correction_protocol"],
            "superseded_parent_result": activation["parent_result"],
            "parent_protocol": activation["parent_protocol"],
            "method_mapping": activation["frozen_reexecution"]["method_mapping"],
            "complete_stage_reexecution": True,
            "environment_resets": activation["environment_resets"],
            "partial_reexecution_allowed": False,
            "failed_scientific_gate_opens_descendants": False,
            "successor_changes": {
                **parent_successor_changes,
                "pact_v12_complete_public_no_effect_guard": True,
                "pact_v13_complete_public_terminal_freshness": True,
            },
            "next_step": (
                parent_protocol["decision_rule"]["on_pass"]
                if passed
                else (
                    "stop, preserve the complete failed WebArena PACT-v13 "
                    "re-execution, and do not open or reuse descendants"
                )
            ),
        }
    )
    original_writer(paths.output_path, payload)
    print(
        json.dumps(
            {
                "stage": stage_name,
                "partition": partition,
                "passed": passed,
                "metrics": payload["metrics"],
                "checks": payload["checks"],
            },
            indent=2,
        )
    )
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reexecution-stage", choices=common.WEB_STAGES, required=True)
    parser.add_argument("--activation-protocol", type=Path, required=True)
    parser.add_argument("--expected-activation-sha256", required=True)
    parser.add_argument(
        "--stage", choices=("preflight", "run", "finalize"), required=True
    )
    parser.add_argument("--model-path", type=Path, default=legacy.DEFAULT_MODEL_PATH)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    activation, parent_protocol, activation_sha256, manifest = verify_inputs(
        stage_name=args.reexecution_stage,
        activation_path=args.activation_protocol,
        expected_activation_sha256=args.expected_activation_sha256,
    )
    partition = partition_for_stage(args.reexecution_stage)
    configure_legacy_for_v13()
    paths = legacy.transfer_paths(partition)
    legacy.c444.MODEL_CACHE_PATH = paths.model_cache_path
    legacy.c444.MODEL_RUNTIME_PATH = paths.model_runtime_path
    if args.stage == "preflight":
        expected_config = v2.evaluator_config_v2(parent_protocol)
        legacy.ensure_evaluator_config(paths, parent_protocol)
        actual_config = legacy.c414.load_json(paths.evaluator_config_path)
        if actual_config != expected_config:
            raise ValueError("WebArena v13 evaluator config changed during preflight")
        print(
            json.dumps(
                {
                    "stage": args.reexecution_stage,
                    "partition": partition,
                    "activation_sha256": activation_sha256,
                    "episodes": len(manifest),
                    "opened_claims": sum(
                        legacy.claim_path(paths, episode).is_file()
                        for episode in manifest
                    ),
                    "replacement_result_exists": paths.output_path.exists(),
                    "evaluator_origins": actual_config["environments"],
                },
                indent=2,
            )
        )
    elif args.stage == "run":
        run(
            parent_protocol=parent_protocol,
            activation_sha256=activation_sha256,
            model_path=args.model_path,
        )
    else:
        finalize(
            stage_name=args.reexecution_stage,
            activation_path=args.activation_protocol,
            activation=activation,
            parent_protocol=parent_protocol,
            activation_sha256=activation_sha256,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
