#!/usr/bin/env python3
"""Run the independent, source-bound InverseReserve final matched grid."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT / "src", ROOT / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import c414_adaptive_semantic_risk_diagnostic as c414  # noqa: E402
import c427_pact_live_development as c427  # noqa: E402
import c444_pact_v7_matched_confirmation as c444  # noqa: E402
from pact_v10_runner_common import (  # noqa: E402
    OneOpenEpisodeStore,
    load_completed_grid,
    run_one_open_grid,
)
from rcrps.confirmation_ablation_agents_v13 import (  # noqa: E402
    MATCHED_CONFIRMATION_DRIVERS_V13,
)
from rcrps import inversereserve_final_v1 as design  # noqa: E402


DEFAULT_PROTOCOL = ROOT / "validation" / "inversereserve_final_protocol_v1.json"
OUTPUT_PATH = ROOT / "validation" / "inversereserve_final_result_v1.json"
RUN_DIRECTORY = ROOT / "runs" / "inversereserve_final_v1"
EPISODE_DIRECTORY = RUN_DIRECTORY / "episodes"
CLAIM_DIRECTORY = RUN_DIRECTORY / "claims"
MODEL_CACHE_PATH = RUN_DIRECTORY / "planner_cache.sqlite3"
MODEL_RUNTIME_PATH = RUN_DIRECTORY / "model_runtime.json"
DEFAULT_MODEL_PATH = Path(str(Path.home() / ".cache" / "inversereserve" / "Qwen3.5-9B"))
PREREGISTRATION_PATH = (
    ROOT
    / "paper"
    / "aaai27"
    / "notes"
    / "2026-07-17_inversereserve_final_v1_preregistration.md"
)
DIAGNOSIS_PATH = ROOT / "reports" / "2026-07-17_c458_gate_failure_diagnosis.md"
REQUIRED_SOURCE_PATHS = {
    "scripts/inversereserve_final_v1.py",
    "src/rcrps/inversereserve_final_v1.py",
    "scripts/pact_v10_runner_common.py",
    "src/rcrps/confirmation_ablation_agents_v13.py",
    "src/rcrps/confirmation_agents_v13.py",
    "src/rcrps/pact_controller_v13.py",
    "src/rcrps/matched_confirmation_v10.py",
    "src/rcrps/matched_confirmation_v9.py",
    "src/rcrps/confirmation_statistics_v7.py",
    "src/rcrps/pact_statistics.py",
}
STORE = OneOpenEpisodeStore(
    EPISODE_DIRECTORY,
    CLAIM_DIRECTORY,
    "InverseReserve-final-v1-open-claim",
)


def _git(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _inside(path: Path, root: Path = ROOT) -> Path:
    resolved = Path(path).resolve()
    resolved.relative_to(root.resolve())
    return resolved


def verify_protocol(
    path: Path,
    expected_sha256: str,
) -> tuple[dict[str, Any], str]:
    path = _inside(path)
    if path != DEFAULT_PROTOCOL.resolve():
        raise ValueError("InverseReserve final protocol path changed")
    if re.fullmatch(r"[0-9a-f]{64}", expected_sha256) is None:
        raise ValueError("expected final protocol hash is malformed")
    actual = c444.sha256(path)
    if actual != expected_sha256:
        raise ValueError(f"InverseReserve final protocol changed: {actual}")
    protocol = c414.load_json(path)
    design.validate_protocol_shape(protocol)

    source_commit = str(protocol["scientific_source_commit"])
    if re.fullmatch(r"[0-9a-f]{40}", source_commit) is None:
        raise ValueError("scientific source commit is malformed")
    _git("cat-file", "-e", f"{source_commit}^{{commit}}")
    changed_science = _git(
        "diff", "--name-only", f"{source_commit}..HEAD", "--", "src", "scripts"
    )
    if changed_science:
        raise ValueError(
            f"scientific source changed after freeze: {changed_science}"
        )
    dirty_science = _git(
        "status", "--porcelain", "--untracked-files=all", "--", "src", "scripts"
    )
    if dirty_science:
        raise ValueError(f"scientific source worktree is dirty: {dirty_science}")

    bindings = protocol["source_sha256"]
    if set(bindings) != REQUIRED_SOURCE_PATHS:
        raise ValueError("InverseReserve final source inventory changed")
    for relative, expected in bindings.items():
        source = _inside(ROOT / relative)
        if not source.is_file() or c444.sha256(source) != expected:
            raise ValueError(f"InverseReserve final source changed: {relative}")

    preregistration = protocol["preregistration"]
    if preregistration != {
        "path": str(PREREGISTRATION_PATH.relative_to(ROOT)),
        "sha256": c444.sha256(PREREGISTRATION_PATH),
    }:
        raise ValueError("InverseReserve final preregistration changed")
    diagnosis = protocol["development_context"].get("diagnosis")
    if diagnosis != {
        "path": str(DIAGNOSIS_PATH.relative_to(ROOT)),
        "sha256": c444.sha256(DIAGNOSIS_PATH),
    }:
        raise ValueError("C458 diagnosis binding changed")
    return protocol, actual


def run(
    *,
    protocol: dict[str, Any],
    protocol_sha256: str,
    model_path: Path,
) -> None:
    run_one_open_grid(
        manifest=design.episode_manifest(protocol),
        protocol=protocol,
        protocol_sha256=protocol_sha256,
        store=STORE,
        driver_registry=MATCHED_CONFIRMATION_DRIVERS_V13,
        episode_candidate="InverseReserve-final-v1-episode",
        model_path=model_path,
        model_cache_path=MODEL_CACHE_PATH,
        model_runtime_path=MODEL_RUNTIME_PATH,
        progress_label="InverseReserve final v1 matched grid",
    )


def finalize(
    *,
    protocol_path: Path,
    protocol: dict[str, Any],
    protocol_sha256: str,
) -> dict[str, Any]:
    if OUTPUT_PATH.exists():
        raise FileExistsError(OUTPUT_PATH)
    manifest = design.episode_manifest(protocol)
    rows, compact, claim_manifest = load_completed_grid(
        manifest=manifest,
        protocol_sha256=protocol_sha256,
        store=STORE,
        model_cache_path=MODEL_CACHE_PATH,
        model_runtime_path=MODEL_RUNTIME_PATH,
    )
    all_claims_complete = all(
        c414.load_json(STORE.claim_path(episode)).get("status") == "complete"
        for episode in manifest
    )
    analysis = design.analyze_final_rows(
        rows,
        protocol,
        all_claims_complete=all_claims_complete,
    )
    passed = bool(analysis["passed"])
    payload = {
        "candidate": "InverseReserve-final-v1-result",
        "created_utc": c427.utc_now(),
        "git_head": c444.git_head(),
        "status": "final_matched_grid_complete",
        "passed": passed,
        "protocol": str(protocol_path.resolve().relative_to(ROOT)),
        "protocol_sha256": protocol_sha256,
        "scientific_source_commit": protocol["scientific_source_commit"],
        "development_context": protocol["development_context"],
        "final_seeds": list(design.FINAL_SEEDS),
        "complete_grid": True,
        "environment_resets": len(manifest),
        "partial_reexecution_allowed": False,
        "outcome_based_exclusion_allowed": False,
        "c458_descendant": False,
        "arm_order_counts": design.arm_order_counts(protocol),
        "model_runtime": str(MODEL_RUNTIME_PATH.relative_to(ROOT)),
        "model_runtime_sha256": c444.sha256(MODEL_RUNTIME_PATH),
        "planner_cache": str(MODEL_CACHE_PATH.relative_to(ROOT)),
        "planner_cache_sha256": c444.sha256(MODEL_CACHE_PATH),
        "claim_manifest": claim_manifest,
        "claim_manifest_sha256": c444.object_sha256(claim_manifest),
        "episode_rows": compact,
        **analysis,
        "next_step": protocol["decision_rule"][
            "on_pass" if passed else "on_failure"
        ],
    }
    c414.atomic_write_json(OUTPUT_PATH, payload)
    print(
        json.dumps(
            {
                "passed": passed,
                "metrics": payload["metrics"],
                "statistics": payload["statistics"],
                "terminal_ledger_audit": payload["terminal_ledger_audit"],
                "complete_commit_audit": payload["complete_commit_audit"],
                "checks": payload["checks"],
            },
            indent=2,
        ),
        flush=True,
    )
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--stage", choices=("preflight", "run", "finalize"), required=True
    )
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--expected-protocol-sha256", required=True)
    parser.add_argument("--model-path", type=Path, default=DEFAULT_MODEL_PATH)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    protocol, protocol_sha256 = verify_protocol(
        args.protocol,
        args.expected_protocol_sha256,
    )
    manifest = design.episode_manifest(protocol)
    if args.stage == "preflight":
        print(
            json.dumps(
                {
                    "protocol_sha256": protocol_sha256,
                    "scientific_source_commit": protocol[
                        "scientific_source_commit"
                    ],
                    "episodes": len(manifest),
                    "opened_claims": sum(
                        STORE.claim_path(episode).is_file()
                        for episode in manifest
                    ),
                    "opened_episode_results": sum(
                        STORE.episode_path(episode).is_file()
                        for episode in manifest
                    ),
                    "result_exists": OUTPUT_PATH.exists(),
                    "arm_order_counts": design.arm_order_counts(protocol),
                    "old_embargoed_partitions_opened": False,
                    "c458_descendant": False,
                },
                indent=2,
            )
        )
    elif args.stage == "run":
        run(
            protocol=protocol,
            protocol_sha256=protocol_sha256,
            model_path=args.model_path,
        )
    else:
        finalize(
            protocol_path=args.protocol,
            protocol=protocol,
            protocol_sha256=protocol_sha256,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
