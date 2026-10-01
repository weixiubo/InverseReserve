#!/usr/bin/env python3
"""Execute the preregistered C415 Qwen3.5-9B capacity diagnostic."""

from __future__ import annotations

import argparse
import dataclasses
import json
import math
import platform
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import c414_adaptive_semantic_risk_diagnostic as c414  # noqa: E402
from rcrps.candidate_semantics import adaptive_candidate_context_crop  # noqa: E402
from rcrps.click_preview import (  # noqa: E402
    CandidateProvenanceConfig,
    candidate_provenance,
    label_symmetric_risk,
)


PROTOCOL_PATH = ROOT / "validation" / "c415_qwen35_9b_capacity_protocol.json"
OUTPUT_PATH = ROOT / "validation" / "c416_qwen35_9b_capacity_diagnostic.json"
RUN_DIRECTORY = ROOT / "runs" / "c416_qwen35_9b_capacity_diagnostic"
CACHE_PATH = RUN_DIRECTORY / "scores.json"

EXPECTED_PROTOCOL_SHA256 = "cc7e227dba021e290dc47b04192090d45f56baf3d3c190e727141d01b2235e2c"
DEFAULT_MODEL_PATH = Path(
    str(Path.home() / ".cache" / "inversereserve" / "Qwen3.5-9B")
)


def verify_model_snapshot(
    protocol: dict[str, Any],
    model_path: Path,
) -> dict[str, str]:
    model = protocol["qwen35_9b"]
    observed = {}
    expected_names = {row["name"] for row in model["snapshot_files"]}
    actual_names = {
        path.name for path in model_path.iterdir() if path.is_file()
    }
    if actual_names != expected_names:
        raise ValueError(
            f"9B snapshot file set changed: "
            f"missing={sorted(expected_names - actual_names)}, "
            f"extra={sorted(actual_names - expected_names)}"
        )
    for expected in model["snapshot_files"]:
        path = model_path / expected["name"]
        if path.stat().st_size != int(expected["bytes"]):
            raise ValueError(f"9B model file size changed: {expected['name']}")
        actual = c414.sha256(path)
        if actual != expected["sha256"]:
            raise ValueError(f"9B model file hash changed: {expected['name']}")
        observed[expected["name"]] = actual
    return observed


def verify_inputs(
    model_path: Path,
) -> tuple[
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
    dict[str, str],
    dict[str, str],
]:
    actual_protocol = c414.sha256(PROTOCOL_PATH)
    if actual_protocol != EXPECTED_PROTOCOL_SHA256:
        raise ValueError(f"C415 protocol hash changed: {actual_protocol}")
    protocol = c414.load_json(PROTOCOL_PATH)
    observed = {"c415_protocol": actual_protocol}
    for name, record in protocol["frozen_method_inputs"].items():
        actual = c414.sha256(c414.relative_file(record["path"]))
        if actual != record["sha256"]:
            raise ValueError(f"frozen C415 method input changed: {name}")
        observed[name] = actual
    c413, c406, c409, c413_hashes = c414.verify_inputs()
    if c413_hashes["c413_protocol"] != protocol["frozen_method_inputs"][
        "c413_protocol"
    ]["sha256"]:
        raise ValueError("active C413 protocol does not match C415")
    observed.update({f"c413:{key}": value for key, value in c413_hashes.items()})
    model_hashes = verify_model_snapshot(protocol, model_path)
    return protocol, c413, c406, c409, observed, model_hashes


def processor_inputs_nonthinking_method_only(
    processor: Any,
    full_image: Any,
    local_image: Any,
    prompt: str,
) -> Any:
    """Render the frozen direct-answer prefix explicitly."""

    messages = [
        {
            "role": "user",
            "content": [
                {"type": "image", "image": full_image},
                {"type": "image", "image": local_image},
                {"type": "text", "text": prompt},
            ],
        }
    ]
    return processor.apply_chat_template(
        messages,
        add_generation_prompt=True,
        tokenize=True,
        return_dict=True,
        return_tensors="pt",
        enable_thinking=False,
    )


def first_token_nonthinking_method_only(
    *,
    model: Any,
    processor: Any,
    full_image: Any,
    local_image: Any,
    prompt: str,
    token_a: int,
    token_b: int,
    device: str,
) -> dict[str, float]:
    """Score A/B at the explicit non-thinking direct-answer position."""

    import torch

    inputs = processor_inputs_nonthinking_method_only(
        processor,
        full_image,
        local_image,
        prompt,
    ).to(device)
    with torch.inference_mode():
        output = model(**inputs, use_cache=False)
        logits = output.logits[0, -1, [token_a, token_b]].float()
        probability = torch.softmax(logits, dim=0)
    result = {
        "logit_a": float(logits[0].item()),
        "logit_b": float(logits[1].item()),
        "probability_a": float(probability[0].item()),
        "probability_b": float(probability[1].item()),
    }
    del inputs, output, logits, probability
    return result


def joint_semantic_risk_9b_method_only(
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
    """Keep the C414 method fixed while replacing only model capacity."""

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
    full_image = c414.c410.full_view(current_image)
    local_image = adaptive_candidate_context_crop(
        current_image,
        candidate_bbox_xyxy,
        **adaptive_view_parameters,
    )
    evidence = c414.ocr_lines_method_only(ocr_views)
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
    score_ab = first_token_nonthinking_method_only(
        model=model,
        processor=processor,
        full_image=full_image,
        local_image=local_image,
        prompt=prompt_ab,
        token_a=token_a,
        token_b=token_b,
        device=device,
    )
    score_ba = first_token_nonthinking_method_only(
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
        "full_view_sha256": c414.image_sha256(full_image),
        "adaptive_local_view_sha256": c414.image_sha256(local_image),
        "adaptive_local_view_size": list(local_image.size),
        "ocr_evidence": evidence,
        "prompt_sha256": {
            "safe_A_risky_B": c414.text_sha256(prompt_ab),
            "risky_A_safe_B": c414.text_sha256(prompt_ba),
        },
        "orientation_safe_A_risky_B": score_ab,
        "orientation_risky_A_safe_B": score_ba,
        "semantic_risk": risk,
        "joint_risk": risk,
    }


def validate_nonthinking_template(processor: Any) -> dict[str, Any]:
    messages = [
        {
            "role": "user",
            "content": [{"type": "text", "text": "Output exactly one letter: A or B."}],
        }
    ]
    inputs = processor.apply_chat_template(
        messages,
        add_generation_prompt=True,
        tokenize=True,
        return_dict=True,
        return_tensors="pt",
        enable_thinking=False,
    )
    decoded = processor.tokenizer.decode(inputs.input_ids[0].tolist())
    expected_suffix = "<|im_start|>assistant\n<think>\n\n</think>\n\n"
    if not decoded.endswith(expected_suffix):
        raise ValueError("Qwen3.5-9B non-thinking prefix changed")
    return {
        "token_count": int(inputs.input_ids.shape[1]),
        "decoded_sha256": c414.text_sha256(decoded),
        "expected_suffix": expected_suffix,
    }


def run_scores(
    protocol: dict[str, Any],
    c413: dict[str, Any],
    c406: dict[str, Any],
    c409: dict[str, Any],
    input_hashes: dict[str, str],
    model_hashes: dict[str, str],
    model_path: Path,
) -> None:
    import torch
    import transformers
    from PIL import Image
    from transformers import AutoModelForMultimodalLM, AutoProcessor

    runtime = protocol["runtime"]
    if transformers.__version__ != runtime["transformers"]:
        raise ValueError(f"transformers version changed: {transformers.__version__}")
    if torch.__version__ != runtime["torch"]:
        raise ValueError(f"torch version changed: {torch.__version__}")
    examples = c414.build_examples(c409)
    ocr_rows = c414.load_ocr_rows(c413, len(examples))
    prior_rows: dict[int, dict[str, Any]] = {}
    if CACHE_PATH.exists():
        prior = c414.load_json(CACHE_PATH)
        if prior.get("protocol_sha256") != EXPECTED_PROTOCOL_SHA256:
            raise ValueError("incompatible C416 cache protocol")
        if prior.get("frozen_input_sha256") != input_hashes:
            raise ValueError("incompatible C416 cache inputs")
        if prior.get("model_file_sha256") != model_hashes:
            raise ValueError("incompatible C416 model snapshot")
        indices = [int(row["method_index"]) for row in prior["rows"]]
        if len(indices) != len(set(indices)):
            raise ValueError("duplicate C416 method index")
        if any(index < 0 or index >= len(examples) for index in indices):
            raise ValueError("unexpected C416 method index")
        prior_rows = {int(row["method_index"]): row for row in prior["rows"]}
        for index, row in prior_rows.items():
            if row["method_received_evaluator_fields"]:
                raise ValueError("C416 cache reports evaluator leakage")
            expected_input = c414.method_input_for(examples[index], ocr_rows[index])
            if row["method_input"] != expected_input:
                raise ValueError(f"C416 cached method input changed at {index}")
        if set(prior_rows) == set(range(len(examples))):
            print("C416 score cache already complete", flush=True)
            return

    processor = AutoProcessor.from_pretrained(model_path)
    template_audit = validate_nonthinking_template(processor)
    token_a = int(protocol["qwen35_9b"]["token_A"]["id"])
    token_b = int(protocol["qwen35_9b"]["token_B"]["id"])
    if processor.tokenizer.encode("A", add_special_tokens=False) != [token_a]:
        raise ValueError("Qwen3.5-9B A token changed")
    if processor.tokenizer.encode("B", add_special_tokens=False) != [token_b]:
        raise ValueError("Qwen3.5-9B B token changed")
    if torch.cuda.device_count() != 2:
        raise ValueError(f"C416 requires exactly two visible GPUs, got {torch.cuda.device_count()}")
    model = AutoModelForMultimodalLM.from_pretrained(
        model_path,
        dtype=torch.bfloat16,
        device_map=str(runtime["device_map"]),
    )
    model.eval()
    config_provenance = c414.provenance_config(c406)
    config_view = c414.local_view_config(c413)
    prompt = c413["prompt"]

    ordered_rows = []
    for index, (example, ocr_row) in enumerate(zip(examples, ocr_rows)):
        reference_path = c414.relative_file(example["reference"])
        current_path = c414.relative_file(example["current"])
        reference = Image.open(reference_path).convert("RGB")
        current = Image.open(current_path).convert("RGB")
        method_input = c414.method_input_for(example, ocr_row)
        cached = prior_rows.get(index)
        if cached is not None:
            row = cached
        else:
            result = joint_semantic_risk_9b_method_only(
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
                device="cuda:0",
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
            "candidate": "C416-score-cache",
            "updated_utc": c414.utc_now(),
            "protocol_sha256": EXPECTED_PROTOCOL_SHA256,
            "frozen_input_sha256": input_hashes,
            "model_file_sha256": model_hashes,
            "template_audit": template_audit,
            "runtime": {
                "python": sys.version,
                "platform": platform.platform(),
                "torch": torch.__version__,
                "transformers": transformers.__version__,
                "cuda_devices": [
                    torch.cuda.get_device_name(index)
                    for index in range(torch.cuda.device_count())
                ],
                "device_map": runtime["device_map"],
            },
            "rows": ordered_rows
            + [
                prior_rows[remaining]
                for remaining in range(index + 1, len(examples))
                if remaining in prior_rows
            ],
        }
        c414.atomic_write_json(CACHE_PATH, payload)
        if (index + 1) % 5 == 0 or index + 1 == len(examples):
            print(f"C416 scored {index + 1}/{len(examples)}", flush=True)
    print(f"Wrote {CACHE_PATH.relative_to(ROOT)}", flush=True)


def evaluate(
    rows: list[dict[str, Any]],
    examples: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    from sklearn.metrics import roc_auc_score

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
    metrics = {
        "synthetic_old_auc": float(
            roc_auc_score(
                [row["label_merged_after_scoring"] for row in synthetic],
                [row["risk"] for row in synthetic],
            )
        ),
        "pooled_old_auc": float(
            roc_auc_score(
                [row["label_merged_after_scoring"] for row in old],
                [row["risk"] for row in old],
            )
        ),
        "reactflow_joint_auc": float(
            roc_auc_score(
                [row["label_merged_after_scoring"] for row in reactflow],
                [row["risk"] for row in reactflow],
            )
        ),
    }
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
    metrics["synthetic_family_margins"] = family_margins
    minimum_danger = min(
        row["risk"] for row in synthetic if row["label_merged_after_scoring"] == 1
    )
    threshold = math.nextafter(minimum_danger, -math.inf)
    metrics["diagnostic_zero_false_safe_threshold"] = threshold
    retention = {}
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
        retained = sum(row["risk"] <= threshold for row in subset)
        retention[name] = {
            "retained": retained,
            "total": len(subset),
            "rate": retained / len(subset),
        }
    metrics["diagnostic_safe_retention"] = retention
    return evaluations, metrics


def finalize(
    protocol: dict[str, Any],
    c409: dict[str, Any],
    input_hashes: dict[str, str],
    model_hashes: dict[str, str],
) -> None:
    if OUTPUT_PATH.exists():
        raise FileExistsError(OUTPUT_PATH)
    cache = c414.load_json(CACHE_PATH)
    if cache["protocol_sha256"] != EXPECTED_PROTOCOL_SHA256:
        raise ValueError("C416 cache protocol changed")
    if cache["frozen_input_sha256"] != input_hashes:
        raise ValueError("C416 cache inputs changed")
    if cache["model_file_sha256"] != model_hashes:
        raise ValueError("C416 cache model snapshot changed")
    examples = c414.build_examples(c409)
    rows = sorted(cache["rows"], key=lambda row: int(row["method_index"]))
    if [int(row["method_index"]) for row in rows] != list(range(len(examples))):
        raise ValueError("C416 cache incomplete")
    evaluations, metrics = evaluate(rows, examples)
    gates = protocol["evaluation"]["pass_gates"]
    novel_calls = sum(
        row["method"]["semantic_model_called"]
        for row in rows
        if row["method"]["provenance"]["novel"]
    )
    checks = {
        "synthetic_old_auc": metrics["synthetic_old_auc"] + 1e-12
        >= float(gates["synthetic_old_auc_minimum"]),
        "pooled_old_auc": metrics["pooled_old_auc"] + 1e-12
        >= float(gates["pooled_old_auc_minimum"]),
        "all_synthetic_family_margins_positive": all(
            row["dangerous_minus_safe"] > 0.0
            for row in metrics["synthetic_family_margins"].values()
        ),
        "reactflow_joint_auc": metrics["reactflow_joint_auc"] + 1e-12
        >= float(gates["reactflow_joint_auc_minimum"]),
        "novel_semantic_model_calls": novel_calls
        == int(gates["novel_semantic_model_calls"]),
    }
    passed = all(checks.values())
    payload = {
        "candidate": "C416",
        "title": "Capacity-only Qwen3.5-9B semantic risk diagnostic",
        "created_utc": c414.utc_now(),
        "git_head": c414.git_head(),
        "protocol": str(PROTOCOL_PATH.relative_to(ROOT)),
        "protocol_sha256": EXPECTED_PROTOCOL_SHA256,
        "frozen_input_sha256": input_hashes,
        "model_file_sha256": model_hashes,
        "score_cache_sha256": c414.sha256(CACHE_PATH),
        "template_audit": cache["template_audit"],
        "runtime": cache["runtime"],
        "method_rows_before_evaluator_merge": rows,
        "evaluations_after_method_cache_complete": evaluations,
        "metrics": metrics,
        "checks": checks,
        "method_received_no_evaluator_fields": not any(
            row["method_received_evaluator_fields"] for row in rows
        ),
        "novel_semantic_model_calls": novel_calls,
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
    c414.atomic_write_json(OUTPUT_PATH, payload)
    print(
        json.dumps(
            {
                "passed": passed,
                "synthetic_old_auc": metrics["synthetic_old_auc"],
                "pooled_old_auc": metrics["pooled_old_auc"],
                "reactflow_joint_auc": metrics["reactflow_joint_auc"],
                "minimum_family_margin": min(
                    row["dangerous_minus_safe"]
                    for row in metrics["synthetic_family_margins"].values()
                ),
                "diagnostic_safe_retention": metrics[
                    "diagnostic_safe_retention"
                ],
                "checks": checks,
                "novel_semantic_model_calls": novel_calls,
            },
            indent=2,
            ensure_ascii=False,
        ),
        flush=True,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", required=True, choices=("score", "finalize"))
    parser.add_argument("--model-path", type=Path, default=DEFAULT_MODEL_PATH)
    args = parser.parse_args()
    protocol, c413, c406, c409, input_hashes, model_hashes = verify_inputs(
        args.model_path
    )
    if args.stage == "score":
        run_scores(
            protocol,
            c413,
            c406,
            c409,
            input_hashes,
            model_hashes,
            args.model_path,
        )
    else:
        finalize(protocol, c409, input_hashes, model_hashes)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
