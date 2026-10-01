#!/usr/bin/env python3
"""Execute the preregistered C413 adaptive semantic risk diagnostic."""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import io
import json
import math
import os
import platform
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import c410_full_box_risk_scorer_diagnostic as c410  # noqa: E402
from rcrps.candidate_semantics import adaptive_candidate_context_crop  # noqa: E402
from rcrps.click_preview import (  # noqa: E402
    CandidateProvenanceConfig,
    candidate_provenance,
    label_symmetric_risk,
)


PROTOCOL_PATH = ROOT / "validation" / "c413_adaptive_semantic_risk_protocol.json"
OUTPUT_PATH = ROOT / "validation" / "c414_adaptive_semantic_risk_diagnostic.json"
RUN_DIRECTORY = ROOT / "runs" / "c414_adaptive_semantic_risk_diagnostic"
CACHE_PATH = RUN_DIRECTORY / "scores.json"

EXPECTED_PROTOCOL_SHA256 = "aa5d4e13b3529eec3d8b6989d08ae82fbfb2831d963ee717419edb83f93884af"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def image_sha256(image: Any) -> str:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return hashlib.sha256(buffer.getvalue()).hexdigest()


def text_sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def relative_file(raw: str) -> Path:
    path = ROOT / raw
    if not path.is_file():
        raise FileNotFoundError(path)
    return path


def utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def git_head() -> str:
    process = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    return process.stdout.strip() if process.returncode == 0 else "unavailable"


def atomic_write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    )
    temporary = Path(handle.name)
    try:
        with handle:
            json.dump(value, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def verify_inputs() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, str]]:
    actual_protocol = sha256(PROTOCOL_PATH)
    if actual_protocol != EXPECTED_PROTOCOL_SHA256:
        raise ValueError(f"C413 protocol hash changed: {actual_protocol}")
    protocol = load_json(PROTOCOL_PATH)
    observed = {"c413_protocol": actual_protocol}
    for name, record in protocol["frozen_inputs"].items():
        actual = sha256(relative_file(record["path"]))
        if actual != record["sha256"]:
            raise ValueError(f"frozen C413 input changed: {name}")
        observed[name] = actual
    c406 = load_json(relative_file(protocol["frozen_inputs"]["c406_protocol"]["path"]))
    c409 = load_json(relative_file(protocol["frozen_inputs"]["c409_protocol"]["path"]))
    return protocol, c406, c409, observed


def build_examples(c409: dict[str, Any]) -> list[dict[str, Any]]:
    examples = c410.build_examples(c409)
    c410.verify_example_images(examples)
    if len(examples) != 84 or len({row["example_id"] for row in examples}) != 84:
        raise ValueError("C413 sample identity changed")
    return examples


def load_ocr_rows(protocol: dict[str, Any], example_count: int) -> list[dict[str, Any]]:
    cache = load_json(relative_file(protocol["frozen_inputs"]["c412_method_cache"]["path"]))
    rows = sorted(cache["rows"], key=lambda row: int(row["method_index"]))
    if [int(row["method_index"]) for row in rows] != list(range(example_count)):
        raise ValueError("C412 method-only cache order changed")
    if any(row["method_received_evaluator_fields"] for row in rows):
        raise ValueError("C412 cache reports evaluator leakage")
    return rows


def method_input_for(
    example: dict[str, Any],
    ocr_row: dict[str, Any],
) -> dict[str, Any]:
    """Build the frozen method input audit without evaluator fields."""

    reference_path = relative_file(example["reference"])
    current_path = relative_file(example["current"])
    expected_ocr_input = {
        "current_sha256": sha256(current_path),
        "candidate_bbox_xyxy": [
            float(value) for value in example["candidate_bbox_xyxy"]
        ],
    }
    if ocr_row["method_input"] != expected_ocr_input:
        raise ValueError("C412 OCR method input changed")
    return {
        "reference_sha256": sha256(reference_path),
        "current_sha256": sha256(current_path),
        "instruction_sha256": text_sha256(example["instruction"]),
        "candidate_bbox_xyxy": expected_ocr_input["candidate_bbox_xyxy"],
        "ocr_views": [
            {
                "psm": int(view["psm"]),
                "scale": int(view["scale"]),
                "normalized_text": str(view["normalized_text"]),
            }
            for view in ocr_row["extraction"]["views"]
        ],
    }


def provenance_config(c406: dict[str, Any]) -> CandidateProvenanceConfig:
    spec = c406["method_interface"]["provenance"]
    return CandidateProvenanceConfig(
        pixel_threshold=int(spec["pixel_threshold"]),
        minimum_changed_pixels=int(spec["minimum_changed_pixels"]),
        minimum_changed_fraction=float(spec["minimum_changed_fraction"]),
    )


def local_view_config(protocol: dict[str, Any]) -> dict[str, Any]:
    spec = protocol["joint_method"]["adaptive_local_view"]
    return {
        "minimum_context_size": tuple(int(value) for value in spec["minimum_context_size"]),
        "candidate_padding": int(spec["candidate_padding"]),
        "maximum_output_size": tuple(int(value) for value in spec["maximum_output_size"]),
        "maximum_upscale": float(spec["maximum_upscale"]),
        "bracket_offset": 4,
        "bracket_length": 12,
        "bracket_width": 3,
    }


def ocr_lines_method_only(ocr_views: list[dict[str, Any]]) -> str:
    """Format only pixel-derived OCR observations."""

    lines = []
    for index, view in enumerate(ocr_views, 1):
        value = str(view["normalized_text"] or "<empty>")
        lines.append(
            f"OCR reading {index} (PSM {int(view['psm'])}, "
            f"scale {int(view['scale'])}): {value}"
        )
    return "\n".join(lines)


def joint_semantic_risk_method_only(
    *,
    model: Any,
    processor: Any,
    reference_image: Any,
    current_image: Any,
    instruction: str,
    candidate_bbox_xyxy: tuple[float, float, float, float],
    ocr_views: list[dict[str, Any]],
    provenance_parameters: CandidateProvenanceConfig,
    adaptive_view_parameters: dict[str, Any],
    prompt_parameters: dict[str, str],
    token_a: int,
    token_b: int,
    device: str,
) -> dict[str, Any]:
    """Apply provenance before a label-symmetric method-only VLM score."""

    provenance = candidate_provenance(
        reference_image,
        current_image,
        candidate_bbox_xyxy,
        provenance_parameters,
    )
    if provenance.novel:
        return {
            "provenance": dataclasses.asdict(provenance),
            "hard_blocked_novel": True,
            "semantic_model_called": False,
            "joint_risk": 1.0,
        }
    full_image = c410.full_view(current_image)
    local_image = adaptive_candidate_context_crop(
        current_image,
        candidate_bbox_xyxy,
        **adaptive_view_parameters,
    )
    evidence = ocr_lines_method_only(ocr_views)
    suffix = prompt_parameters["assessment_suffix"].format(
        instruction=instruction,
        ocr_lines=evidence,
    )
    prompt_ab = "\n".join(
        (
            prompt_parameters["common"],
            suffix,
            prompt_parameters["orientation_safe_A_risky_B"],
        )
    )
    prompt_ba = "\n".join(
        (
            prompt_parameters["common"],
            suffix,
            prompt_parameters["orientation_risky_A_safe_B"],
        )
    )
    score_ab = c410.first_token_method_only(
        model=model,
        processor=processor,
        full_image=full_image,
        local_image=local_image,
        prompt=prompt_ab,
        token_a=token_a,
        token_b=token_b,
        device=device,
    )
    score_ba = c410.first_token_method_only(
        model=model,
        processor=processor,
        full_image=full_image,
        local_image=local_image,
        prompt=prompt_ba,
        token_a=token_a,
        token_b=token_b,
        device=device,
    )
    risk = label_symmetric_risk(
        safe_a_risky_b_logits=(score_ab["logit_a"], score_ab["logit_b"]),
        risky_a_safe_b_logits=(score_ba["logit_a"], score_ba["logit_b"]),
    )
    return {
        "provenance": dataclasses.asdict(provenance),
        "hard_blocked_novel": False,
        "semantic_model_called": True,
        "full_view_sha256": image_sha256(full_image),
        "adaptive_local_view_sha256": image_sha256(local_image),
        "adaptive_local_view_size": list(local_image.size),
        "ocr_evidence": evidence,
        "prompt_sha256": {
            "safe_A_risky_B": text_sha256(prompt_ab),
            "risky_A_safe_B": text_sha256(prompt_ba),
        },
        "orientation_safe_A_risky_B": score_ab,
        "orientation_risky_A_safe_B": score_ba,
        "semantic_risk": risk,
        "joint_risk": risk,
    }


def run_scores(
    protocol: dict[str, Any],
    c406: dict[str, Any],
    c409: dict[str, Any],
    input_hashes: dict[str, str],
) -> None:
    import torch
    import transformers
    from PIL import Image
    from transformers import AutoModelForMultimodalLM, AutoProcessor

    examples = build_examples(c409)
    ocr_rows = load_ocr_rows(protocol, len(examples))
    model_hashes = c410.verify_model_snapshot(c406)
    prior_rows: dict[int, dict[str, Any]] = {}
    if CACHE_PATH.exists():
        prior = load_json(CACHE_PATH)
        if prior.get("protocol_sha256") != EXPECTED_PROTOCOL_SHA256:
            raise ValueError("incompatible C414 cache protocol")
        if prior.get("frozen_input_sha256") != input_hashes:
            raise ValueError("incompatible C414 cache inputs")
        if prior.get("model_file_sha256") != model_hashes:
            raise ValueError("incompatible C414 model snapshot")
        indices = [int(row["method_index"]) for row in prior["rows"]]
        if len(indices) != len(set(indices)):
            raise ValueError("duplicate C414 method index")
        if any(index < 0 or index >= len(examples) for index in indices):
            raise ValueError("unexpected C414 method index")
        prior_rows = {int(row["method_index"]): row for row in prior["rows"]}
        for index, row in prior_rows.items():
            if row["method_received_evaluator_fields"]:
                raise ValueError("C414 cache reports evaluator leakage")
            expected_input = method_input_for(examples[index], ocr_rows[index])
            if row["method_input"] != expected_input:
                raise ValueError(f"C414 cached method input changed at {index}")
        if set(prior_rows) == set(range(len(examples))):
            print("C414 score cache already complete", flush=True)
            return

    model_spec = c406["qwen35_2b"]
    processor = AutoProcessor.from_pretrained(model_spec["local_snapshot"])
    token_a = int(model_spec["token_A"]["id"])
    token_b = int(model_spec["token_B"]["id"])
    if processor.tokenizer.encode("A", add_special_tokens=False) != [token_a]:
        raise ValueError("Qwen A token changed")
    if processor.tokenizer.encode("B", add_special_tokens=False) != [token_b]:
        raise ValueError("Qwen B token changed")
    model = AutoModelForMultimodalLM.from_pretrained(
        model_spec["local_snapshot"],
        dtype=torch.bfloat16,
        device_map="auto",
    )
    model.eval()
    config_provenance = provenance_config(c406)
    config_view = local_view_config(protocol)
    prompt = protocol["prompt"]

    ordered_rows = []
    for index, (example, ocr_row) in enumerate(zip(examples, ocr_rows)):
        reference_path = relative_file(example["reference"])
        current_path = relative_file(example["current"])
        reference = Image.open(reference_path).convert("RGB")
        current = Image.open(current_path).convert("RGB")
        method_input = method_input_for(example, ocr_row)
        cached = prior_rows.get(index)
        if cached is not None:
            if cached["method_input"] != method_input:
                raise ValueError(f"C414 method input changed at index {index}")
            row = cached
        else:
            result = joint_semantic_risk_method_only(
                model=model,
                processor=processor,
                reference_image=reference,
                current_image=current,
                instruction=example["instruction"],
                candidate_bbox_xyxy=tuple(
                    float(value) for value in example["candidate_bbox_xyxy"]
                ),
                ocr_views=method_input["ocr_views"],
                provenance_parameters=config_provenance,
                adaptive_view_parameters=config_view,
                prompt_parameters=prompt,
                token_a=token_a,
                token_b=token_b,
                device=str(model_spec["device"]),
            )
            row = {
                "method_index": index,
                "method_received_evaluator_fields": False,
                "method_input": method_input,
                "method": result,
            }
            prior_rows[index] = row
        ordered_rows.append(row)
        payload = {
            "candidate": "C414-score-cache",
            "updated_utc": utc_now(),
            "protocol_sha256": EXPECTED_PROTOCOL_SHA256,
            "frozen_input_sha256": input_hashes,
            "model_file_sha256": model_hashes,
            "runtime": {
                "python": sys.version,
                "platform": platform.platform(),
                "torch": torch.__version__,
                "transformers": transformers.__version__,
                "cuda_device": (
                    torch.cuda.get_device_name(0)
                    if torch.cuda.is_available()
                    else None
                ),
            },
            "rows": ordered_rows
            + [
                prior_rows[remaining]
                for remaining in range(index + 1, len(examples))
                if remaining in prior_rows
            ],
        }
        atomic_write_json(CACHE_PATH, payload)
        if (index + 1) % 5 == 0 or index + 1 == len(examples):
            print(f"C414 scored {index + 1}/{len(examples)}", flush=True)
    print(f"Wrote {CACHE_PATH.relative_to(ROOT)}", flush=True)


def finalize(
    protocol: dict[str, Any],
    c409: dict[str, Any],
    input_hashes: dict[str, str],
) -> None:
    from sklearn.metrics import roc_auc_score

    if OUTPUT_PATH.exists():
        raise FileExistsError(OUTPUT_PATH)
    cache = load_json(CACHE_PATH)
    if cache["protocol_sha256"] != EXPECTED_PROTOCOL_SHA256:
        raise ValueError("C414 cache protocol changed")
    if cache["frozen_input_sha256"] != input_hashes:
        raise ValueError("C414 cache inputs changed")
    examples = build_examples(c409)
    rows = sorted(cache["rows"], key=lambda row: int(row["method_index"]))
    if [int(row["method_index"]) for row in rows] != list(range(len(examples))):
        raise ValueError("C414 cache incomplete")
    evaluations = []
    for method_row, example in zip(rows, examples):
        method = method_row["method"]
        evaluations.append(
            {
                "method_index": method_row["method_index"],
                "example_id_merged_after_scoring": example["example_id"],
                "dataset_merged_after_scoring": example["dataset"],
                "family_merged_after_scoring": example["family"],
                "class_merged_after_scoring": example["class"],
                "label_merged_after_scoring": int(example["label"]),
                "provenance": "novel" if method["provenance"]["novel"] else "old",
                "semantic_model_called": bool(method["semantic_model_called"]),
                "risk": float(method["joint_risk"]),
            }
        )
    synthetic = [
        row for row in evaluations if row["dataset_merged_after_scoring"] == "synthetic"
    ]
    old = [row for row in evaluations if row["provenance"] == "old"]
    reactflow = [
        row for row in evaluations if row["dataset_merged_after_scoring"] == "reactflow"
    ]
    synthetic_auc = float(
        roc_auc_score(
            [row["label_merged_after_scoring"] for row in synthetic],
            [row["risk"] for row in synthetic],
        )
    )
    pooled_old_auc = float(
        roc_auc_score(
            [row["label_merged_after_scoring"] for row in old],
            [row["risk"] for row in old],
        )
    )
    reactflow_auc = float(
        roc_auc_score(
            [row["label_merged_after_scoring"] for row in reactflow],
            [row["risk"] for row in reactflow],
        )
    )
    family_margins = {}
    for family in sorted({row["family_merged_after_scoring"] for row in synthetic}):
        safe = [
            row["risk"]
            for row in synthetic
            if row["family_merged_after_scoring"] == family
            and row["label_merged_after_scoring"] == 0
        ]
        danger = [
            row["risk"]
            for row in synthetic
            if row["family_merged_after_scoring"] == family
            and row["label_merged_after_scoring"] == 1
        ]
        family_margins[family] = {
            "safe_mean": sum(safe) / len(safe),
            "dangerous_mean": sum(danger) / len(danger),
            "dangerous_minus_safe": sum(danger) / len(danger)
            - sum(safe) / len(safe),
        }
    minimum_danger = min(
        row["risk"]
        for row in synthetic
        if row["label_merged_after_scoring"] == 1
    )
    descriptive_threshold = math.nextafter(minimum_danger, -math.inf)
    safe_retention = {}
    for name, subset in (
        (
            "synthetic",
            [row for row in synthetic if row["label_merged_after_scoring"] == 0],
        ),
        (
            "reactflow",
            [row for row in reactflow if row["label_merged_after_scoring"] == 0],
        ),
    ):
        retained = sum(row["risk"] <= descriptive_threshold for row in subset)
        safe_retention[name] = {
            "retained": retained,
            "total": len(subset),
            "rate": retained / len(subset),
        }
    gates = protocol["evaluation"]["pass_gates"]
    checks = {
        "synthetic_old_auc": synthetic_auc + 1e-12
        >= float(gates["synthetic_old_auc_minimum"]),
        "pooled_old_auc": pooled_old_auc + 1e-12
        >= float(gates["pooled_old_auc_minimum"]),
        "all_synthetic_family_margins_positive": all(
            row["dangerous_minus_safe"] > 0.0 for row in family_margins.values()
        ),
        "reactflow_joint_auc": reactflow_auc + 1e-12
        >= float(gates["reactflow_joint_auc_minimum"]),
    }
    passed = all(checks.values())
    payload = {
        "candidate": "C414",
        "title": "Adaptive-context OCR-assisted semantic risk diagnostic",
        "created_utc": utc_now(),
        "git_head": git_head(),
        "protocol": str(PROTOCOL_PATH.relative_to(ROOT)),
        "protocol_sha256": EXPECTED_PROTOCOL_SHA256,
        "frozen_input_sha256": input_hashes,
        "score_cache_sha256": sha256(CACHE_PATH),
        "model_file_sha256": cache["model_file_sha256"],
        "method_rows_before_evaluator_merge": rows,
        "evaluations_after_method_cache_complete": evaluations,
        "metrics": {
            "synthetic_old_auc": synthetic_auc,
            "pooled_old_auc": pooled_old_auc,
            "reactflow_joint_auc": reactflow_auc,
            "synthetic_family_margins": family_margins,
            "diagnostic_zero_false_safe_threshold": descriptive_threshold,
            "diagnostic_safe_retention": safe_retention,
        },
        "checks": checks,
        "method_received_no_evaluator_fields": not any(
            row["method_received_evaluator_fields"] for row in rows
        ),
        "novel_semantic_model_calls": sum(
            row["method"]["semantic_model_called"]
            for row in rows
            if row["method"]["provenance"]["novel"]
        ),
        "external_boundary": {
            "browsergym_or_miniwob_episode_rendered": False,
            "external_task_reset": False,
            "external_reward_or_outcome_observed": False,
        },
        "passed": passed,
        "next_step": (
            protocol["scientific_boundary"]["on_pass"]
            if passed
            else protocol["scientific_boundary"]["on_failure"]
        ),
    }
    atomic_write_json(OUTPUT_PATH, payload)
    print(
        json.dumps(
            {
                "passed": passed,
                "synthetic_old_auc": synthetic_auc,
                "pooled_old_auc": pooled_old_auc,
                "reactflow_joint_auc": reactflow_auc,
                "minimum_family_margin": min(
                    row["dangerous_minus_safe"] for row in family_margins.values()
                ),
                "diagnostic_safe_retention": safe_retention,
                "checks": checks,
                "novel_semantic_model_calls": payload[
                    "novel_semantic_model_calls"
                ],
            },
            indent=2,
            ensure_ascii=False,
        ),
        flush=True,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", required=True, choices=("score", "finalize"))
    args = parser.parse_args()
    protocol, c406, c409, input_hashes = verify_inputs()
    if args.stage == "score":
        run_scores(protocol, c406, c409, input_hashes)
    else:
        finalize(protocol, c409, input_hashes)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
