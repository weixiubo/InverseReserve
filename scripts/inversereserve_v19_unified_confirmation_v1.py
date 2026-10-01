#!/usr/bin/env python3
"""Prepare, execute, seal, and validate the frozen PACT-v19 confirmation."""

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
from inversereserve_successor_runner_common import (  # noqa: E402
    FrozenSuccessorRuntime,
)
from pact_v10_runner_common import OneOpenEpisodeStore  # noqa: E402
from rcrps import inversereserve_v19_unified_confirmation_v1 as design  # noqa: E402


RUN_ROOT = ROOT / "runs" / "inversereserve_v19_unified_confirmation_v1"
PROTOCOL_PATH = RUN_ROOT / "protocol.json"
FROZEN_PROTOCOL_PATH = (
    ROOT / "validation" / "inversereserve_v19_unified_confirmation_v1_protocol.json"
)
RESULT_PATH = (
    ROOT / "validation" / "inversereserve_v19_unified_confirmation_v1_result.json"
)
AUDIT_PATH = (
    ROOT / "validation" / "inversereserve_v19_unified_confirmation_v1_validation.json"
)
BINDING_PATH = (
    ROOT
    / "validation"
    / "inversereserve_v19_unified_confirmation_v1_paper_binding.json"
)
EPISODE_DIRECTORY = RUN_ROOT / "episodes"
CLAIM_DIRECTORY = RUN_ROOT / "claims"
MODEL_CACHE_PATH = RUN_ROOT / "planner_cache.sqlite3"
MODEL_RUNTIME_PATH = RUN_ROOT / "model_runtime.json"
LOCK_PATH = RUN_ROOT / "resource_gate.lock"
DEVELOPMENT_PROTOCOL = (
    ROOT / "validation" / "inversereserve_v19_unified_development_v1_protocol.json"
)
DEVELOPMENT_RESULT = (
    ROOT / "validation" / "inversereserve_v19_unified_development_v1_summary.json"
)
PREREGISTRATION = ROOT / design.PREREGISTRATION["path"]
NEW_SOURCE_PATHS = {
    "scripts/inversereserve_v19_unified_confirmation_v1.py",
    "scripts/run_inversereserve_v19_unified_confirmation_v1_resource_gate.sh",
    "src/rcrps/inversereserve_v19_unified_confirmation_v1.py",
    "tests/test_inversereserve_v19_unified_confirmation_v1.py",
    "tests/test_inversereserve_v19_unified_confirmation_v1_runner.py",
}
STORE = OneOpenEpisodeStore(
    EPISODE_DIRECTORY,
    CLAIM_DIRECTORY,
    "InverseReserve-v19-unified-confirmation-v1-open-claim",
)
RUNTIME = FrozenSuccessorRuntime(
    root=ROOT,
    design=design,
    run_root=RUN_ROOT,
    result_path=RESULT_PATH,
    episode_directory=EPISODE_DIRECTORY,
    claim_directory=CLAIM_DIRECTORY,
    model_cache_path=MODEL_CACHE_PATH,
    model_runtime_path=MODEL_RUNTIME_PATH,
    lock_path=LOCK_PATH,
    store=STORE,
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


def _require_sha256(value: str, label: str) -> str:
    if re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise ValueError(f"{label} SHA-256 is malformed")
    return value


def _development_predecessor(
    protocol_sha256: str, result_sha256: str
) -> dict[str, Any]:
    protocol_sha256 = _require_sha256(
        protocol_sha256, "PACT-v19 development protocol"
    )
    result_sha256 = _require_sha256(result_sha256, "PACT-v19 development result")
    expected = {
        DEVELOPMENT_PROTOCOL: protocol_sha256,
        DEVELOPMENT_RESULT: result_sha256,
    }
    for path, digest in expected.items():
        if not path.is_file() or c444.sha256(path) != digest:
            raise ValueError(f"PACT-v19 development evidence changed: {path}")
    protocol = c414.load_json(DEVELOPMENT_PROTOCOL)
    result = c414.load_json(DEVELOPMENT_RESULT)
    analysis = result.get("analysis", {})
    checks = analysis.get("checks", {})
    claims = result.get("claim_manifest", {})
    episodes = result.get("episode_manifest", {})
    if (
        protocol.get("candidate") != "InverseReserve-v19-unified-development-v1"
        or protocol.get("status")
        != "development_only_frozen_before_any_35001_or_35002_reset"
        or protocol.get("expected_episodes") != 108
        or protocol.get("purpose", {}).get("claim_status")
        != "development_only_no_submission_claim"
        or result.get("candidate") != protocol.get("candidate")
        or result.get("status") != "complete_passed"
        or result.get("passed") is not True
        or result.get("protocol_sha256") != protocol_sha256
        or result.get("scientific_source_commit")
        != protocol.get("scientific_source_commit")
        or analysis.get("exact_manifest") is not True
        or analysis.get("all_claims_complete") is not True
        or analysis.get("passed") is not True
        or not checks
        or not all(value is True for value in checks.values())
        or len(claims) != 108
        or len(episodes) != 108
    ):
        raise ValueError("PACT-v19 development did not pass the frozen activation gate")
    if not all(
        re.fullmatch(r"[0-9a-f]{64}", str(value))
        for value in (*claims.values(), *episodes.values())
    ):
        raise ValueError("PACT-v19 development evidence manifest is malformed")
    return {
        "passing_v19_unified_development": {
            "protocol": str(DEVELOPMENT_PROTOCOL.relative_to(ROOT)),
            "protocol_sha256": protocol_sha256,
            "result": str(DEVELOPMENT_RESULT.relative_to(ROOT)),
            "result_sha256": result_sha256,
            "scientific_source_commit": protocol["scientific_source_commit"],
            "passed": True,
            "episode_count": 108,
            "claim_count": 108,
            "all_frozen_checks_passed": True,
        },
        "confirmation_seed_range": [min(design.SEEDS), max(design.SEEDS)],
        "development_rows_in_confirmation": 0,
    }


def required_source_paths() -> set[str]:
    development = c414.load_json(DEVELOPMENT_PROTOCOL)
    source = development.get("source_sha256")
    if not isinstance(source, dict):
        raise ValueError("PACT-v19 development source closure is absent")
    return set(source) | NEW_SOURCE_PATHS


def _verify_preregistration() -> None:
    if (
        not PREREGISTRATION.is_file()
        or c444.sha256(PREREGISTRATION) != design.PREREGISTRATION["sha256"]
    ):
        raise ValueError("PACT-v19 confirmation preregistration changed")


def prepare(
    development_protocol_sha256: str,
    development_result_sha256: str,
) -> dict[str, Any]:
    if any(
        path.exists()
        for path in (
            RUN_ROOT,
            FROZEN_PROTOCOL_PATH,
            RESULT_PATH,
            AUDIT_PATH,
            BINDING_PATH,
        )
    ):
        raise RuntimeError("PACT-v19 confirmation create-once state already exists")
    dirty = _git("status", "--porcelain", "--untracked-files=all")
    if dirty:
        raise ValueError(f"commit the PACT-v19 confirmation runner first:\n{dirty}")
    _verify_preregistration()
    predecessor = _development_predecessor(
        development_protocol_sha256, development_result_sha256
    )
    paths = required_source_paths()
    missing = sorted(relative for relative in paths if not (ROOT / relative).is_file())
    if missing:
        raise FileNotFoundError(f"PACT-v19 confirmation source closure is incomplete: {missing}")
    protocol = design.build_protocol(
        scientific_source_commit=_git("rev-parse", "HEAD"),
        source_sha256={
            relative: c444.sha256(ROOT / relative) for relative in sorted(paths)
        },
        predecessor=predecessor,
        repositories=c444.EXPECTED_REPOSITORIES,
        created_utc=c427.utc_now(),
    )
    c414.atomic_write_json(PROTOCOL_PATH, protocol)
    payload = {
        "protocol": str(PROTOCOL_PATH.relative_to(ROOT)),
        "protocol_sha256": c444.sha256(PROTOCOL_PATH),
        "scientific_source_commit": protocol["scientific_source_commit"],
        "episodes": protocol["expected_episodes"],
        "confirmation_seed_range": [min(design.SEEDS), max(design.SEEDS)],
        "claim_status": protocol["purpose"]["claim_status"],
    }
    print(json.dumps(payload, indent=2))
    return payload


def verify_protocol(expected_sha256: str) -> tuple[dict[str, Any], str]:
    expected_sha256 = _require_sha256(
        expected_sha256, "PACT-v19 confirmation protocol"
    )
    actual = c444.sha256(PROTOCOL_PATH)
    if actual != expected_sha256:
        raise ValueError(f"PACT-v19 confirmation protocol changed: {actual}")
    protocol = c414.load_json(PROTOCOL_PATH)
    design.validate_protocol(protocol)
    passing = protocol.get("predecessor", {}).get(
        "passing_v19_unified_development", {}
    )
    predecessor = _development_predecessor(
        str(passing.get("protocol_sha256", "")),
        str(passing.get("result_sha256", "")),
    )
    if protocol.get("predecessor") != predecessor:
        raise ValueError("PACT-v19 confirmation predecessor binding changed")
    _verify_preregistration()
    source_commit = str(protocol["scientific_source_commit"])
    if re.fullmatch(r"[0-9a-f]{40}", source_commit) is None:
        raise ValueError("PACT-v19 confirmation source commit is malformed")
    _git("cat-file", "-e", f"{source_commit}^{{commit}}")
    changed = _git(
        "diff",
        "--name-only",
        f"{source_commit}..HEAD",
        "--",
        "src",
        "scripts",
        "tests",
        design.PREREGISTRATION["path"],
    )
    if changed:
        raise ValueError(f"PACT-v19 confirmation scientific source changed: {changed}")
    dirty = _git(
        "status",
        "--porcelain",
        "--untracked-files=all",
        "--",
        "src",
        "scripts",
        "tests",
        design.PREREGISTRATION["path"],
    )
    if dirty:
        raise ValueError(f"PACT-v19 confirmation scientific source is dirty: {dirty}")
    if set(protocol["source_sha256"]) != required_source_paths():
        raise ValueError("PACT-v19 confirmation source inventory changed")
    for relative, expected in protocol["source_sha256"].items():
        path = ROOT / relative
        if not path.is_file() or c444.sha256(path) != expected:
            raise ValueError(f"PACT-v19 confirmation scientific source changed: {relative}")
    if protocol.get("repositories") != c444.EXPECTED_REPOSITORIES:
        raise ValueError("PACT-v19 confirmation repository pins changed")
    for name, head in c444.EXPECTED_REPOSITORIES.items():
        c444.verify_clean_repository(c444.REPOSITORY_PATHS[name], head)
    return protocol, actual


def summarize(protocol: dict[str, Any], protocol_sha256: str) -> dict[str, Any]:
    if RESULT_PATH.exists():
        raise FileExistsError(RESULT_PATH)
    rows, claims, episodes = RUNTIME.load_completed(protocol, protocol_sha256)
    analysis = design.analyze_rows(
        rows,
        protocol,
        all_claims_complete=len(claims) == design.expected_episodes(),
    )
    payload = {
        "candidate": design.CANDIDATE,
        "created_utc": c427.utc_now(),
        "status": "complete_passed" if analysis["passed"] else "complete_failed",
        "passed": analysis["passed"],
        "decision": (
            design.DECISION_RULE["on_pass"]
            if analysis["passed"]
            else design.DECISION_RULE["on_failure"]
        ),
        "protocol": str(FROZEN_PROTOCOL_PATH.relative_to(ROOT)),
        "protocol_sha256": protocol_sha256,
        "scientific_source_commit": protocol["scientific_source_commit"],
        "predecessor": protocol["predecessor"],
        "outcome_definitions": protocol["outcome_definitions"],
        "primary_analysis": protocol["primary_analysis"],
        "confirmation_gates": protocol["confirmation_gates"],
        "analysis": analysis,
        "claim_manifest": claims,
        "episode_manifest": episodes,
        "model_runtime": {
            "path": str(MODEL_RUNTIME_PATH.relative_to(ROOT)),
            "sha256": c444.sha256(MODEL_RUNTIME_PATH),
        },
        "planner_cache": {
            "path": str(MODEL_CACHE_PATH.relative_to(ROOT)),
            "sha256": c444.sha256(MODEL_CACHE_PATH),
        },
    }
    c414.atomic_write_json(RESULT_PATH, payload)
    print(
        json.dumps(
            {
                "result": str(RESULT_PATH.relative_to(ROOT)),
                "result_sha256": c444.sha256(RESULT_PATH),
                "passed": payload["passed"],
                "checks": analysis["checks"],
                "primary_comparison": analysis["primary_comparison"],
                "family_closed_successes": analysis["family_closed_successes"],
                "metrics": analysis["metrics"],
            },
            indent=2,
        )
    )
    return payload


def validate_result(
    protocol: dict[str, Any],
    protocol_sha256: str,
    expected_result_sha256: str,
) -> dict[str, Any]:
    if AUDIT_PATH.exists():
        raise FileExistsError(AUDIT_PATH)
    if (
        not FROZEN_PROTOCOL_PATH.is_file()
        or c444.sha256(FROZEN_PROTOCOL_PATH) != protocol_sha256
    ):
        raise ValueError("PACT-v19 frozen confirmation protocol changed")
    expected_result_sha256 = _require_sha256(
        expected_result_sha256, "PACT-v19 confirmation result"
    )
    if not RESULT_PATH.is_file() or c444.sha256(RESULT_PATH) != expected_result_sha256:
        raise ValueError("PACT-v19 confirmation result changed")
    result = c414.load_json(RESULT_PATH)
    rows, claims, episodes = RUNTIME.load_completed(protocol, protocol_sha256)
    recomputed = design.analyze_rows(
        rows,
        protocol,
        all_claims_complete=len(claims) == design.expected_episodes(),
    )
    expected_status = "complete_passed" if recomputed["passed"] else "complete_failed"
    expected_decision = (
        design.DECISION_RULE["on_pass"]
        if recomputed["passed"]
        else design.DECISION_RULE["on_failure"]
    )
    if (
        result.get("candidate") != design.CANDIDATE
        or result.get("protocol") != str(FROZEN_PROTOCOL_PATH.relative_to(ROOT))
        or result.get("protocol_sha256") != protocol_sha256
        or result.get("scientific_source_commit")
        != protocol.get("scientific_source_commit")
        or result.get("predecessor") != protocol.get("predecessor")
        or result.get("outcome_definitions") != protocol.get("outcome_definitions")
        or result.get("primary_analysis") != protocol.get("primary_analysis")
        or result.get("confirmation_gates") != protocol.get("confirmation_gates")
        or result.get("analysis") != recomputed
        or result.get("passed") is not recomputed["passed"]
        or result.get("status") != expected_status
        or result.get("decision") != expected_decision
        or result.get("claim_manifest") != claims
        or result.get("episode_manifest") != episodes
        or len(claims) != design.expected_episodes()
        or len(episodes) != design.expected_episodes()
        or result.get("model_runtime")
        != {
            "path": str(MODEL_RUNTIME_PATH.relative_to(ROOT)),
            "sha256": c444.sha256(MODEL_RUNTIME_PATH),
        }
        or result.get("planner_cache")
        != {
            "path": str(MODEL_CACHE_PATH.relative_to(ROOT)),
            "sha256": c444.sha256(MODEL_CACHE_PATH),
        }
    ):
        raise ValueError("PACT-v19 confirmation result failed integrity validation")
    audit = {
        "candidate": f"{design.CANDIDATE}-validation",
        "created_utc": c427.utc_now(),
        "integrity_passed": True,
        "confirmation_passed": recomputed["passed"],
        "protocol_sha256": protocol_sha256,
        "result_sha256": expected_result_sha256,
        "claim_count": len(claims),
        "episode_count": len(episodes),
        "failed_scientific_checks": sorted(
            key for key, value in recomputed["checks"].items() if value is not True
        ),
    }
    c414.atomic_write_json(AUDIT_PATH, audit)
    print(json.dumps(audit, indent=2))
    return audit


def seal_paper_binding(
    protocol_sha256: str,
    result_sha256: str,
    audit_sha256: str,
) -> dict[str, Any]:
    """Bind validated raw evidence without converting a failed result to a pass."""

    if BINDING_PATH.exists():
        raise FileExistsError(BINDING_PATH)
    protocol_sha256 = _require_sha256(
        protocol_sha256, "PACT-v19 confirmation protocol"
    )
    result_sha256 = _require_sha256(
        result_sha256, "PACT-v19 confirmation result"
    )
    audit_sha256 = _require_sha256(
        audit_sha256, "PACT-v19 confirmation validation"
    )
    expected = {
        FROZEN_PROTOCOL_PATH: protocol_sha256,
        RESULT_PATH: result_sha256,
        AUDIT_PATH: audit_sha256,
    }
    for path, digest in expected.items():
        if not path.is_file() or c444.sha256(path) != digest:
            raise ValueError(f"PACT-v19 confirmation evidence changed: {path}")
    protocol = c414.load_json(FROZEN_PROTOCOL_PATH)
    result = c414.load_json(RESULT_PATH)
    audit = c414.load_json(AUDIT_PATH)
    design.validate_protocol(protocol)
    passed = result.get("passed") is True
    expected_status = "complete_passed" if passed else "complete_failed"
    checks = result.get("analysis", {}).get("checks", {})
    failed_checks = sorted(
        key for key, value in checks.items() if value is not True
    ) if isinstance(checks, dict) else None
    if (
        result.get("candidate") != design.CANDIDATE
        or result.get("status") != expected_status
        or result.get("protocol_sha256") != protocol_sha256
        or result.get("scientific_source_commit")
        != protocol.get("scientific_source_commit")
        or result.get("analysis", {}).get("passed") is not passed
        or len(result.get("claim_manifest", {})) != design.expected_episodes()
        or len(result.get("episode_manifest", {})) != design.expected_episodes()
        or audit.get("candidate") != f"{design.CANDIDATE}-validation"
        or audit.get("integrity_passed") is not True
        or audit.get("confirmation_passed") is not passed
        or audit.get("protocol_sha256") != protocol_sha256
        or audit.get("result_sha256") != result_sha256
        or audit.get("claim_count") != design.expected_episodes()
        or audit.get("episode_count") != design.expected_episodes()
        or audit.get("failed_scientific_checks") != failed_checks
    ):
        raise ValueError("PACT-v19 confirmation cannot be bound for paper use")
    if not EPISODE_DIRECTORY.is_dir() or not CLAIM_DIRECTORY.is_dir():
        raise FileNotFoundError("PACT-v19 confirmation raw evidence is absent")
    binding = {
        "artifact": "InverseReserve v19 unified confirmation paper binding",
        "created_utc": c427.utc_now(),
        "status": (
            "sealed_complete_passed" if passed else "sealed_complete_failed"
        ),
        "scientific_passed": passed,
        "integrity_passed": True,
        "expected_episodes": design.expected_episodes(),
        "inputs": {
            "protocol": {
                "path": str(FROZEN_PROTOCOL_PATH.relative_to(ROOT)),
                "sha256": protocol_sha256,
            },
            "result": {
                "path": str(RESULT_PATH.relative_to(ROOT)),
                "sha256": result_sha256,
            },
            "integrity_audit": {
                "path": str(AUDIT_PATH.relative_to(ROOT)),
                "sha256": audit_sha256,
            },
        },
        "episodes_directory": str(EPISODE_DIRECTORY.relative_to(ROOT)),
        "claims_directory": str(CLAIM_DIRECTORY.relative_to(ROOT)),
    }
    c414.atomic_write_json(BINDING_PATH, binding)
    print(
        json.dumps(
            {
                "binding": str(BINDING_PATH.relative_to(ROOT)),
                "binding_sha256": c444.sha256(BINDING_PATH),
                "scientific_passed": passed,
                "integrity_passed": True,
            },
            indent=2,
        )
    )
    return binding


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare_parser = subparsers.add_parser("prepare")
    prepare_parser.add_argument("--development-protocol-sha256", required=True)
    prepare_parser.add_argument("--development-result-sha256", required=True)
    for command in (
        "run",
        "summarize",
        "verify",
        "validate-result",
        "seal-paper-binding",
    ):
        subparser = subparsers.add_parser(command)
        subparser.add_argument("--protocol-sha256", required=True)
        if command == "run":
            subparser.add_argument(
                "--model-path", type=Path, default=c444.DEFAULT_MODEL_PATH
            )
        if command == "validate-result":
            subparser.add_argument("--result-sha256", required=True)
        if command == "seal-paper-binding":
            subparser.add_argument("--result-sha256", required=True)
            subparser.add_argument("--audit-sha256", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.command == "prepare":
        prepare(
            args.development_protocol_sha256,
            args.development_result_sha256,
        )
        return 0
    protocol, protocol_sha256 = verify_protocol(args.protocol_sha256)
    if args.command == "verify":
        print(
            json.dumps(
                {
                    "passed": True,
                    "protocol_sha256": protocol_sha256,
                    "claim_status": protocol["purpose"]["claim_status"],
                },
                indent=2,
            )
        )
        return 0
    with RUNTIME.single_instance_lock():
        if args.command == "run":
            RUNTIME.run(protocol, protocol_sha256, args.model_path)
        elif args.command == "summarize":
            summarize(protocol, protocol_sha256)
        elif args.command == "validate-result":
            validate_result(protocol, protocol_sha256, args.result_sha256)
        elif args.command == "seal-paper-binding":
            seal_paper_binding(
                protocol_sha256,
                args.result_sha256,
                args.audit_sha256,
            )
        else:
            raise AssertionError(args.command)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
