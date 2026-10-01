#!/usr/bin/env python3
"""Verify and activate the pre-result PACT-v13 full-rerun template."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CORRECTION_PROTOCOL = (
    ROOT / "validation" / "pact_v13_complete_public_commit_protocol.json"
)
DEFAULT_TEMPLATE = (
    ROOT / "validation" / "pact_v13_full_reexecution_template_protocol.json"
)
CORRECTION_PROTOCOL_SHA256 = (
    "85cec662de5401b3958725909d598b518777b4126b10d79b5426158a7f5b4961"
)
ANONYMOUS_REVIEW_HASH_ONLY_SOURCES = {
    "scripts/c452_pact_v9_fresh_visible_development.py",
    "scripts/webarena_exact_mutation_transfer_v1.py",
}
EXPECTED_STAGES = {
    "c452": {
        "parent_result": "validation/c452_pact_v9_fresh_visible_development.json",
        "parent_protocol": "validation/c451_pact_v9_fresh_visible_protocol.json",
        "activation_protocol": "validation/pact_v13_c452_full_reexecution_protocol.json",
        "replacement_result": "validation/pact_v13_c452_full_reexecution.json",
        "run_directory": "runs/pact_v13_c452_full_reexecution",
        "episodes": 120,
        "method_mapping": {"full_pact_v9": "full_pact_v13"},
    },
    "repair": {
        "parent_result": "validation/pact_v10_repair_holdout_confirmation.json",
        "parent_protocol": "validation/pact_v10_repair_holdout_protocol.json",
        "activation_protocol": "validation/pact_v13_repair_full_reexecution_protocol.json",
        "replacement_result": "validation/pact_v13_repair_full_reexecution.json",
        "run_directory": "runs/pact_v13_repair_full_reexecution",
        "episodes": 60,
        "method_mapping": {"full_pact_v10": "full_pact_v13"},
    },
    "final": {
        "parent_result": "validation/pact_v10_final_matched_confirmation.json",
        "parent_protocol": "validation/pact_v10_final_matched_protocol.json",
        "activation_protocol": "validation/pact_v13_final_full_reexecution_protocol.json",
        "replacement_result": "validation/pact_v13_final_matched_reexecution.json",
        "run_directory": "runs/pact_v13_final_matched_reexecution",
        "episodes": 360,
        "method_mapping": {
            "raw_open_loop_v10_matched": "raw_open_loop_v13_matched",
            "typed_no_certificate_v10": "typed_no_certificate_v13",
            "full_pact_v10": "full_pact_v13",
        },
    },
    "webarena_development": {
        "parent_result": "validation/webarena_verified_exact_mutation_development_v2.json",
        "parent_protocol": "validation/webarena_verified_exact_mutation_development_protocol_v6.json",
        "activation_protocol": "validation/pact_v13_webarena_development_full_reexecution_protocol.json",
        "replacement_result": "validation/webarena_verified_exact_mutation_development_v13.json",
        "run_directory": "runs/webarena_verified_exact_mutation_transfer_v13/adapter_development",
        "episodes": 3,
        "method_mapping": {
            "full_pact_v10_webarena_exact_mutation_v2": (
                "full_pact_v13_webarena_exact_mutation_v2"
            )
        },
    },
    "webarena_holdout": {
        "parent_result": "validation/webarena_verified_exact_mutation_holdout_v2.json",
        "parent_protocol": "validation/webarena_verified_exact_mutation_holdout_protocol_v2.json",
        "activation_protocol": "validation/pact_v13_webarena_holdout_full_reexecution_protocol.json",
        "replacement_result": "validation/webarena_verified_exact_mutation_holdout_v13.json",
        "run_directory": "runs/webarena_verified_exact_mutation_transfer_v13/mechanism_holdout",
        "episodes": 6,
        "method_mapping": {
            "full_pact_v10_webarena_exact_mutation_v2": (
                "full_pact_v13_webarena_exact_mutation_v2"
            )
        },
    },
}


def sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required: {path}")
    return value


def _inside(root: Path, relative: str) -> Path:
    if Path(relative).is_absolute():
        raise ValueError(f"v13 rerun path must be relative: {relative}")
    resolved = (root / relative).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as error:
        raise ValueError(f"v13 rerun path escapes repository: {relative}") from error
    return resolved


def exact_reference(root: Path, relative: str) -> dict[str, str]:
    path = _inside(root, relative)
    if not path.is_file():
        raise FileNotFoundError(path)
    return {"path": relative, "sha256": sha256(path)}


def verify_correction_protocol(
    path: Path = DEFAULT_CORRECTION_PROTOCOL,
    expected_sha256: str = CORRECTION_PROTOCOL_SHA256,
    *,
    root: Path = ROOT,
) -> tuple[dict[str, Any], str]:
    if path.resolve() != _inside(
        root, "validation/pact_v13_complete_public_commit_protocol.json"
    ):
        raise ValueError("PACT-v13 correction protocol path changed")
    actual = sha256(path)
    if actual != expected_sha256:
        raise ValueError(f"PACT-v13 correction protocol changed: {actual}")
    protocol = load_json(path)
    stages = {
        name: {
            "parent_result": stage["parent_result"],
            "parent_protocol": stage["parent_protocol"],
            "episodes": stage["episodes"],
            "method_mapping": stage["method_mapping"],
        }
        for name, stage in EXPECTED_STAGES.items()
    }
    if not (
        protocol.get("candidate")
        == "PACT-v13-complete-public-commit-protocol"
        and protocol.get("status") == "sealed_before_current_evidence_opened"
        and protocol.get("stages") == stages
        and protocol.get("evidence_decision")
        == {
            "zero_reset_inheritance_allowed": False,
            "reason": (
                "v9 through v12 terminal actions did not execute under the "
                "complete-public v13 certificate binding"
            ),
            "complete_stage_reexecution_required": True,
            "partial_reexecution_allowed": False,
            "failed_scientific_gate_opens_descendants": False,
        }
    ):
        raise ValueError("PACT-v13 correction protocol semantics changed")
    source_hashes = protocol.get("source_sha256")
    if not isinstance(source_hashes, dict) or not source_hashes:
        raise ValueError("PACT-v13 correction source binding is absent")
    for relative, expected in source_hashes.items():
        if sha256(_inside(root, relative)) != expected:
            raise ValueError(f"PACT-v13 correction source changed: {relative}")
    note = protocol.get("preregistration")
    if not isinstance(note, dict) or set(note) != {"path", "sha256"}:
        raise ValueError("PACT-v13 correction preregistration binding changed")
    if sha256(_inside(root, str(note["path"]))) != note["sha256"]:
        raise ValueError("PACT-v13 correction preregistration changed")
    return protocol, actual


def verify_template(
    path: Path,
    expected_sha256: str,
    *,
    root: Path = ROOT,
) -> tuple[dict[str, Any], str]:
    if path.resolve() != _inside(
        root, "validation/pact_v13_full_reexecution_template_protocol.json"
    ):
        raise ValueError("PACT-v13 full-rerun template path changed")
    actual = sha256(path)
    if actual != expected_sha256:
        raise ValueError(f"PACT-v13 full-rerun template changed: {actual}")
    template = load_json(path)
    if not (
        template.get("candidate") == "PACT-v13-full-reexecution-template"
        and template.get("status") == "sealed_before_current_evidence_opened"
        and template.get("correction_protocol_sha256")
        == CORRECTION_PROTOCOL_SHA256
        and template.get("unconditional_complete_reexecution") is True
        and template.get("stages") == EXPECTED_STAGES
        and template.get("partial_reexecution_allowed") is False
        and template.get("failed_scientific_gate_opens_descendants") is False
        and re.fullmatch(
            r"[0-9a-f]{40}", str(template.get("source_parent_commit"))
        )
    ):
        raise ValueError("PACT-v13 full-rerun template semantics changed")
    verify_correction_protocol(
        _inside(
            root,
            "validation/pact_v13_complete_public_commit_protocol.json",
        ),
        CORRECTION_PROTOCOL_SHA256,
        root=root,
    )
    source_hashes = template.get("source_sha256")
    if not isinstance(source_hashes, dict) or not source_hashes:
        raise ValueError("PACT-v13 full-rerun source binding is absent")
    for relative, expected in source_hashes.items():
        source = _inside(root, relative)
        if not source.is_file():
            if (
                relative in ANONYMOUS_REVIEW_HASH_ONLY_SOURCES
                and (root / "MANIFEST.json").is_file()
            ):
                continue
            raise ValueError(f"PACT-v13 full-rerun source is absent: {relative}")
        if sha256(source) != expected:
            raise ValueError(f"PACT-v13 full-rerun source changed: {relative}")
    note = template.get("preregistration")
    if not isinstance(note, dict) or set(note) != {"path", "sha256"}:
        raise ValueError("PACT-v13 full-rerun preregistration binding changed")
    if sha256(_inside(root, str(note["path"]))) != note["sha256"]:
        raise ValueError("PACT-v13 full-rerun preregistration changed")
    return template, actual


def _git_head(root: Path) -> str:
    return subprocess.run(
        ["git", "-c", "core.fsmonitor=false", "-C", str(root), "rev-parse", "HEAD"],
        check=True,
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
    ).stdout.strip()


def _atomic_create_json(path: Path, value: dict[str, Any]) -> None:
    if path.exists():
        raise FileExistsError(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    payload = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")
    try:
        with temporary.open("xb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.link(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def create_activation(
    *,
    template: dict[str, Any],
    template_path: Path,
    template_sha256: str,
    stage_name: str,
    expected_parent_sha256: str,
    root: Path = ROOT,
) -> dict[str, Any]:
    stage = template["stages"][stage_name]
    parent_reference = exact_reference(root, stage["parent_result"])
    if parent_reference["sha256"] != expected_parent_sha256:
        raise ValueError("PACT-v13 parent result changed")
    parent = load_json(_inside(root, stage["parent_result"]))
    parent_protocol = exact_reference(root, stage["parent_protocol"])
    if not (
        parent.get("passed") is True
        and parent.get("protocol") == parent_protocol["path"]
        and parent.get("protocol_sha256") == parent_protocol["sha256"]
    ):
        raise ValueError("PACT-v13 stage lacks an exact passing parent gate")
    output = _inside(root, stage["activation_protocol"])
    payload = {
        "candidate": "PACT-v13-full-reexecution-activation",
        "created_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "git_head": _git_head(root),
        "status": "sealed_after_passing_parent_before_first_v13_reset",
        "stage": stage_name,
        "correction_protocol": exact_reference(
            root, "validation/pact_v13_complete_public_commit_protocol.json"
        ),
        "template": {
            "path": str(template_path.resolve().relative_to(root.resolve())),
            "sha256": template_sha256,
        },
        "parent_result": parent_reference,
        "parent_protocol": parent_protocol,
        "frozen_reexecution": stage,
        "environment_resets": stage["episodes"],
        "partial_reexecution_allowed": False,
        "failed_scientific_gate_opens_descendants": False,
        "checks": {
            "passing_parent_is_exact": True,
            "parent_protocol_is_exact": True,
            "complete_population_is_required": True,
            "zero_reset_inheritance_is_forbidden": True,
        },
    }
    _atomic_create_json(output, payload)
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--template", type=Path, default=DEFAULT_TEMPLATE)
    parser.add_argument("--expected-template-sha256", required=True)
    parser.add_argument("--activate-stage", choices=tuple(EXPECTED_STAGES))
    parser.add_argument("--expected-parent-sha256")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if re.fullmatch(r"[0-9a-f]{64}", args.expected_template_sha256) is None:
        raise ValueError("expected template SHA-256 is malformed")
    template, actual = verify_template(args.template, args.expected_template_sha256)
    result: dict[str, Any] = {"template_sha256": actual, "verified": True}
    if args.activate_stage is not None:
        if (
            args.expected_parent_sha256 is None
            or re.fullmatch(r"[0-9a-f]{64}", args.expected_parent_sha256) is None
        ):
            raise ValueError("activation requires an exact parent SHA-256")
        result["activation"] = create_activation(
            template=template,
            template_path=args.template,
            template_sha256=actual,
            stage_name=args.activate_stage,
            expected_parent_sha256=args.expected_parent_sha256,
        )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
