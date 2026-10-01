#!/usr/bin/env python3
"""Run the sealed two-stage InverseReserve WebArena final suite."""

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
import webarena_exact_mutation_transfer_v1 as legacy  # noqa: E402
import webarena_exact_mutation_transfer_v2 as v2  # noqa: E402
import webarena_exact_mutation_transfer_v13 as v13  # noqa: E402
from rcrps import inversereserve_webarena_final_v1 as design  # noqa: E402


DEFAULT_PROTOCOL = (
    ROOT / "validation" / "inversereserve_webarena_final_protocol_v1.json"
)
RUN_ROOT = ROOT / design.RUN_ROOT_RELATIVE
DEVELOPMENT_OUTPUT = ROOT / design.DEVELOPMENT_RESULT_RELATIVE
HOLDOUT_OUTPUT = ROOT / design.HOLDOUT_RESULT_RELATIVE
DEFAULT_MODEL_PATH = Path(str(Path.home() / ".cache" / "inversereserve" / "Qwen3.5-9B"))
REPOSITORY_PATHS = {
    "browsergym": ROOT / "external" / "BrowserGym",
    "webarena_verified": ROOT / "external" / "webarena-verified",
}
CONFIG_PATH = (
    REPOSITORY_PATHS["webarena_verified"]
    / "examples"
    / "configs"
    / "config.example.json"
)
OCR_CACHE_PATH = (
    ROOT / "runs" / "c412_candidate_text_consensus_diagnostic" / "ocr_cache.json"
)


def git(*args: str) -> str:
    return subprocess.check_output(
        ["git", *args], cwd=ROOT, text=True
    ).strip()


def inside(path: Path) -> Path:
    resolved = Path(path).resolve()
    resolved.relative_to(ROOT.resolve())
    return resolved


def configure_harness() -> None:
    """Use the frozen V13 mechanism and new create-once suite paths."""

    v13.configure_legacy_for_v13()
    legacy.DEVELOPMENT_OUTPUT = DEVELOPMENT_OUTPUT
    legacy.HOLDOUT_OUTPUT = HOLDOUT_OUTPUT
    legacy.RUN_ROOT = RUN_ROOT


def verify_repository(path: Path, expected_head: str) -> None:
    if git_at(path, "rev-parse", "HEAD") != expected_head:
        raise ValueError(f"external repository head changed: {path}")
    if git_at(path, "status", "--porcelain", "--untracked-files=all"):
        raise ValueError(f"external repository is dirty: {path}")


def git_at(path: Path, *args: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(path), *args], text=True
    ).strip()


def verify_protocol(
    path: Path, expected_sha256: str
) -> tuple[dict[str, Any], str]:
    path = inside(path)
    if path != DEFAULT_PROTOCOL.resolve():
        raise ValueError("InverseReserve WebArena protocol path changed")
    if re.fullmatch(r"[0-9a-f]{64}", expected_sha256) is None:
        raise ValueError("expected WebArena protocol hash is malformed")
    actual = c444.sha256(path)
    if actual != expected_sha256:
        raise ValueError(f"InverseReserve WebArena protocol changed: {actual}")
    protocol = c414.load_json(path)
    design.validate_protocol_shape(protocol)

    source_commit = str(protocol["scientific_source_commit"])
    subprocess.run(
        ["git", "cat-file", "-e", f"{source_commit}^{{commit}}"],
        cwd=ROOT,
        check=True,
    )
    ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", source_commit, "HEAD"],
        cwd=ROOT,
        check=False,
    )
    if ancestor.returncode != 0:
        raise ValueError("WebArena scientific source is not an ancestor")
    for relative, expected in protocol["source_sha256"].items():
        source = inside(ROOT / relative)
        if not source.is_file() or c444.sha256(source) != expected:
            raise ValueError(f"WebArena causal source changed: {relative}")

    for role, reference in {
        "primary result": protocol["activation"]["primary_result"],
        "pre-open audit": protocol["preopen_audit"],
    }.items():
        artifact = inside(ROOT / reference["path"])
        if not artifact.is_file() or c444.sha256(artifact) != reference["sha256"]:
            raise ValueError(f"WebArena {role} changed")
    primary = c414.load_json(ROOT / design.PRIMARY_RESULT_RELATIVE)
    if not (
        primary.get("candidate") == "InverseReserve-final-v1-result"
        and primary.get("status") == "final_matched_grid_complete"
        and primary.get("passed") is True
        and isinstance(primary.get("checks"), dict)
        and all(value is True for value in primary["checks"].values())
    ):
        raise ValueError("WebArena suite lost its independent primary activation")

    for name, expected_head in protocol["repositories"].items():
        verify_repository(REPOSITORY_PATHS[name], expected_head)
    if c444.sha256(legacy.INVENTORY_PATH) != protocol["official_source"][
        "offline_inventory_sha256"
    ]:
        raise ValueError("WebArena offline inventory changed")
    if c444.sha256(CONFIG_PATH) != protocol["external_config_sha256"]:
        raise ValueError("WebArena external configuration changed")
    if not OCR_CACHE_PATH.is_file() or c444.sha256(OCR_CACHE_PATH) != protocol[
        "ocr_cache_sha256"
    ]:
        raise ValueError("WebArena frozen OCR cache is absent or changed")
    for site, record in protocol["official_images"].items():
        legacy._inspect_loaded_image(record, role=f"official {site}")
    legacy.verify_evaluator(protocol)
    return protocol, actual


def paths_for(partition: str) -> legacy.TransferPathsV1:
    configure_harness()
    return legacy.transfer_paths(partition)


def directory_has_files(path: Path) -> bool:
    return path.exists() and any(row.is_file() for row in path.rglob("*"))


def stage_counts(partition: str) -> dict[str, Any]:
    paths = paths_for(partition)
    manifest = design.stage_manifest(partition)
    return {
        "claims": sum(legacy.claim_path(paths, row).is_file() for row in manifest),
        "episodes": sum(
            legacy.episode_path(paths, row).is_file() for row in manifest
        ),
        "result_exists": paths.output_path.is_file(),
        "expected": len(manifest),
    }


def verify_holdout_unopened() -> None:
    paths = paths_for(design.HOLDOUT)
    if (
        paths.output_path.exists()
        or directory_has_files(paths.claim_directory)
        or directory_has_files(paths.episode_directory)
        or directory_has_files(paths.official_output_directory)
        or paths.model_cache_path.exists()
        or paths.model_runtime_path.exists()
    ):
        raise ValueError("same-suite holdout was opened before development passed")


def development_activation(protocol_sha256: str) -> dict[str, str]:
    if not DEVELOPMENT_OUTPUT.is_file():
        raise FileNotFoundError("same-suite development result is absent")
    result = c414.load_json(DEVELOPMENT_OUTPUT)
    if not design.development_authorizes_holdout(
        result, protocol_sha256=protocol_sha256
    ):
        raise ValueError("same-suite development result does not authorize holdout")
    return {
        "path": DEVELOPMENT_OUTPUT.relative_to(ROOT).as_posix(),
        "sha256": c444.sha256(DEVELOPMENT_OUTPUT),
    }


def ensure_evaluator_config(
    protocol: dict[str, Any], partition: str
) -> dict[str, Any]:
    configure_harness()
    paths = legacy.transfer_paths(partition)
    execution = design.execution_protocol(protocol, partition)
    legacy.ensure_evaluator_config(paths, execution)
    observed = c414.load_json(paths.evaluator_config_path)
    expected = v2.evaluator_config_v2(execution)
    if observed != expected:
        raise ValueError("WebArena evaluator origins changed")
    return observed


def run_stage(
    *,
    protocol: dict[str, Any],
    protocol_sha256: str,
    partition: str,
    model_path: Path,
) -> None:
    configure_harness()
    paths = legacy.transfer_paths(partition)
    if paths.output_path.exists():
        raise FileExistsError(paths.output_path)
    if partition == design.DEVELOPMENT:
        verify_holdout_unopened()
    else:
        development_activation(protocol_sha256)
    execution = design.execution_protocol(protocol, partition)
    legacy.run_grid(
        protocol=execution,
        protocol_sha256=protocol_sha256,
        model_path=model_path,
    )


def finalize_stage(
    *,
    protocol_path: Path,
    protocol: dict[str, Any],
    protocol_sha256: str,
    partition: str,
) -> dict[str, Any]:
    configure_harness()
    paths = legacy.transfer_paths(partition)
    if paths.output_path.exists():
        raise FileExistsError(paths.output_path)
    if partition == design.DEVELOPMENT:
        verify_holdout_unopened()
        activation = None
    else:
        activation = development_activation(protocol_sha256)
    execution = design.execution_protocol(protocol, partition)
    captured: list[dict[str, Any]] = []
    original_writer = legacy.c414.atomic_write_json
    original_analyzer = legacy.analyze_transfer_rows

    def capture(path: Path, payload: dict[str, Any]) -> None:
        if Path(path).resolve() != paths.output_path.resolve() or captured:
            raise RuntimeError("WebArena finalizer attempted an unexpected write")
        captured.append(payload)

    try:
        legacy.c414.atomic_write_json = capture
        legacy.analyze_transfer_rows = v13.analyze_transfer_rows_v13
        legacy.finalize(protocol_path, execution, protocol_sha256)
    finally:
        legacy.analyze_transfer_rows = original_analyzer
        legacy.c414.atomic_write_json = original_writer
    if len(captured) != 1:
        raise RuntimeError("WebArena finalizer did not produce exactly one result")
    payload = captured[0]
    development = partition == design.DEVELOPMENT
    payload.update(
        {
            "candidate": (
                "InverseReserve-WebArena-final-development-v1"
                if development
                else "InverseReserve-WebArena-final-holdout-v1"
            ),
            "created_utc": c427.utc_now(),
            "status": "development_complete" if development else "holdout_complete",
            "stage": partition,
            "protocol": protocol_path.resolve().relative_to(ROOT.resolve()).as_posix(),
            "protocol_sha256": protocol_sha256,
            "execution_view_sha256": c444.object_sha256(execution),
            "scientific_source_commit": protocol["scientific_source_commit"],
            "method_identity": protocol["method_identity"],
            "primary_activation": protocol["activation"]["primary_result"],
            "development_activation": activation,
            "complete_stage": True,
            "partial_reexecution_allowed": False,
            "outcome_based_exclusion_allowed": False,
            "next_step": protocol["stages"][partition]["decision_rule"][
                "on_pass" if payload["passed"] else "on_failure"
            ],
        }
    )
    original_writer(paths.output_path, payload)
    print(
        json.dumps(
            {
                "stage": partition,
                "passed": payload["passed"],
                "metrics": payload["metrics"],
                "checks": payload["checks"],
                "result_sha256": c444.sha256(paths.output_path),
            },
            indent=2,
        ),
        flush=True,
    )
    return payload


def validate_result(partition: str, protocol_sha256: str) -> dict[str, Any]:
    path = ROOT / design.result_relative(partition)
    if not path.is_file():
        raise FileNotFoundError(path)
    result = c414.load_json(path)
    candidate = (
        "InverseReserve-WebArena-final-development-v1"
        if partition == design.DEVELOPMENT
        else "InverseReserve-WebArena-final-holdout-v1"
    )
    expected = len(design.stage_manifest(partition))
    if not (
        result.get("candidate") == candidate
        and result.get("stage") == partition
        and result.get("protocol_sha256") == protocol_sha256
        and result.get("metrics", {}).get("episodes") == expected
        and result.get("complete_stage") is True
        and result.get("partial_reexecution_allowed") is False
        and result.get("outcome_based_exclusion_allowed") is False
        and isinstance(result.get("checks"), dict)
        and len(result.get("episode_rows", [])) == expected
        and len(result.get("claim_manifest", {})) == expected
    ):
        raise ValueError(f"WebArena {partition} result is incompatible")
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--stage",
        choices=(
            "preflight",
            "development-run",
            "development-finalize",
            "development-validate",
            "holdout-run",
            "holdout-finalize",
            "holdout-validate",
        ),
        required=True,
    )
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--expected-protocol-sha256", required=True)
    parser.add_argument("--model-path", type=Path, default=DEFAULT_MODEL_PATH)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    protocol, protocol_sha256 = verify_protocol(
        args.protocol, args.expected_protocol_sha256
    )
    if args.stage == "preflight":
        verify_holdout_unopened()
        configs = {
            stage: ensure_evaluator_config(protocol, stage)["environments"]
            for stage in design.STAGES
        }
        print(
            json.dumps(
                {
                    "protocol_sha256": protocol_sha256,
                    "scientific_source_commit": protocol[
                        "scientific_source_commit"
                    ],
                    "development": stage_counts(design.DEVELOPMENT),
                    "holdout": stage_counts(design.HOLDOUT),
                    "evaluator_origins": configs,
                    "selected_states_opened_by_preflight": False,
                },
                indent=2,
            )
        )
        return 0
    partition = (
        design.DEVELOPMENT
        if args.stage.startswith("development-")
        else design.HOLDOUT
    )
    action = args.stage.split("-", 1)[1]
    if action == "run":
        run_stage(
            protocol=protocol,
            protocol_sha256=protocol_sha256,
            partition=partition,
            model_path=args.model_path,
        )
    elif action == "finalize":
        finalize_stage(
            protocol_path=args.protocol,
            protocol=protocol,
            protocol_sha256=protocol_sha256,
            partition=partition,
        )
    else:
        result = validate_result(partition, protocol_sha256)
        print(
            json.dumps(
                {
                    "stage": partition,
                    "passed": result["passed"],
                    "result_sha256": c444.sha256(
                        ROOT / design.result_relative(partition)
                    ),
                },
                indent=2,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
