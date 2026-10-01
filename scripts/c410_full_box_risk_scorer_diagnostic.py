#!/usr/bin/env python3
"""Execute the preregistered C409 full-candidate-box scorer diagnostic."""

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
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from rcrps.click_preview import (  # noqa: E402
    CandidateProvenanceConfig,
    candidate_box_context_crop,
    candidate_provenance,
    label_symmetric_risk,
    restricted_binary_probability,
)


PROTOCOL_PATH = ROOT / "validation" / "c409_box_view_scorer_diagnostic_protocol.json"
C409A_PATH = ROOT / "validation" / "c409a_input_integrity_addendum.json"
C409B_PATH = ROOT / "validation" / "c409b_teacher_forcing_execution_addendum.json"
C406_PATH = ROOT / "validation" / "c406_state_provenance_risk_protocol.json"
C403_CACHE_PATH = ROOT / "runs" / "c403_click_preview_offline_development" / "ocr_cache.json"
OUTPUT_PATH = ROOT / "validation" / "c410_full_box_risk_scorer_diagnostic.json"
RUN_DIRECTORY = ROOT / "runs" / "c410_full_box_risk_scorer_diagnostic"
CACHE_PATH = RUN_DIRECTORY / "scores.json"

EXPECTED_PROTOCOL_SHA256 = "a7e35f4b0ffe821faafbbec61eb1bbe9684b73a104f3026e475d56627b4e0987"
EXPECTED_C409A_SHA256 = "046e64eed4c3d008a0beb6ae8c6afc60e94a5aee1b14a0762293b80f147c73a4"
EXPECTED_C409B_SHA256 = "d32d70b09f8dfa330af11ab2713e73ad9d5406d0d776217d6c45efb72bb37b4a"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def text_sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


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


def verify_inputs() -> tuple[dict[str, Any], dict[str, Any], dict[str, str]]:
    actual_protocol = sha256(PROTOCOL_PATH)
    if actual_protocol != EXPECTED_PROTOCOL_SHA256:
        raise ValueError(f"C409 protocol hash changed: {actual_protocol}")
    protocol = load_json(PROTOCOL_PATH)
    observed = {"c409_protocol": actual_protocol}
    actual_addendum = sha256(C409A_PATH)
    if actual_addendum != EXPECTED_C409A_SHA256:
        raise ValueError(f"C409A addendum hash changed: {actual_addendum}")
    addendum = load_json(C409A_PATH)
    if addendum["parent_protocol"]["sha256"] != actual_protocol:
        raise ValueError("C409A parent protocol mismatch")
    integrity = addendum["integrity_oracle"]
    if relative_file(integrity["path"]) != C403_CACHE_PATH:
        raise ValueError("C409A integrity oracle path changed")
    actual_integrity = sha256(C403_CACHE_PATH)
    if actual_integrity != integrity["sha256"]:
        raise ValueError("C409A integrity oracle hash changed")
    observed["c409a_addendum"] = actual_addendum
    observed["c403_image_integrity_oracle"] = actual_integrity
    actual_execution_addendum = sha256(C409B_PATH)
    if actual_execution_addendum != EXPECTED_C409B_SHA256:
        raise ValueError(
            f"C409B execution addendum hash changed: {actual_execution_addendum}"
        )
    execution_addendum = load_json(C409B_PATH)
    if execution_addendum["parent_protocol"]["sha256"] != actual_protocol:
        raise ValueError("C409B parent protocol mismatch")
    if execution_addendum["parent_integrity_addendum"]["sha256"] != actual_addendum:
        raise ValueError("C409B parent integrity addendum mismatch")
    observed["c409b_execution_addendum"] = actual_execution_addendum
    for name, record in protocol["frozen_inputs"].items():
        actual = sha256(relative_file(record["path"]))
        if actual != record["sha256"]:
            raise ValueError(f"frozen C409 input changed: {name}")
        observed[name] = actual
    c406 = load_json(C406_PATH)
    return protocol, c406, observed


def bbox_from_xywh(raw: dict[str, Any]) -> list[float]:
    return [
        float(raw["x"]),
        float(raw["y"]),
        float(raw["x"] + raw["w"]),
        float(raw["y"] + raw["h"]),
    ]


def center(box: list[float]) -> list[float]:
    return [(box[0] + box[2]) / 2.0, (box[1] + box[3]) / 2.0]


def build_examples(
    protocol: dict[str, Any],
) -> list[dict[str, Any]]:
    manifest = load_json(
        relative_file(
            protocol["frozen_inputs"]["c408_synthetic_manifest"]["path"]
        )
    )
    sample = protocol["sample"]
    synthetic_spec = sample["synthetic"]
    synthetic = [
        {
            **row,
            "label": int(row["label"]),
        }
        for row in manifest["examples"]
        if row["family"] in set(synthetic_spec["families"])
        and int(row["seed"]) in set(synthetic_spec["seeds"])
        and row["class"] in set(synthetic_spec["classes"])
    ]
    if len(synthetic) != int(synthetic_spec["examples"]):
        raise ValueError(f"synthetic diagnostic sample changed: {len(synthetic)}")

    c209 = load_json(
        relative_file(protocol["frozen_inputs"]["c209_reactflow"]["path"])
    )
    c403 = load_json(C403_CACHE_PATH)
    c403_by_task = {row["task_id"]: row for row in c403["rows"]}
    reactflow = []
    for row in c209["tasks"]:
        result = row["result"]
        task_id = (
            f"c209_{row['scenario']}_task"
            f"{int(row['scenario_task_index']):02d}"
        )
        if task_id not in c403_by_task:
            raise ValueError(f"missing ReactFlow image hashes for {task_id}")
        image_hashes = c403_by_task[task_id]
        for class_name, label, current, box, expected in (
            (
                "safe_disclosure",
                0,
                result["screenshots"]["initial"],
                bbox_from_xywh(result["node_bbox"]),
                "old",
            ),
            (
                "dangerous_commit",
                1,
                result["screenshots"]["preview"],
                bbox_from_xywh(result["action_bbox"]),
                "novel",
            ),
        ):
            reactflow.append(
                {
                    "example_id": f"reactflow:{task_id}:{class_name}",
                    "dataset": "reactflow",
                    "family": "reactflow",
                    "scenario_id": task_id,
                    "instruction": row["instruction"],
                    "reference": result["screenshots"]["initial"],
                    "current": current,
                    "candidate_bbox_xyxy": box,
                    "candidate_point": center(box),
                    "class": class_name,
                    "label": label,
                    "expected_provenance": expected,
                    "reference_sha256": image_hashes["initial_sha256"],
                    "current_sha256": image_hashes[
                        "initial_sha256"
                        if class_name == "safe_disclosure"
                        else "preview_sha256"
                    ],
                }
            )
    if len(reactflow) != int(sample["reactflow"]["examples"]):
        raise ValueError(f"ReactFlow diagnostic sample changed: {len(reactflow)}")
    examples = [*synthetic, *reactflow]
    if len(examples) != int(sample["total_examples"]):
        raise ValueError("C409 diagnostic total changed")
    return examples


def verify_example_images(examples: list[dict[str, Any]]) -> None:
    """Verify bytes against hashes frozen before C410 scoring."""

    for example in examples:
        for field in ("reference", "current"):
            actual = sha256(relative_file(example[field]))
            expected = example[f"{field}_sha256"]
            if actual != expected:
                raise ValueError(
                    f"image changed for {example['example_id']} {field}: {actual}"
                )


def verify_model_snapshot(c406: dict[str, Any]) -> dict[str, str]:
    record = c406["qwen35_2b"]
    root = Path(record["local_snapshot"])
    observed = {}
    for expected in record["snapshot_files"]:
        path = root / expected["name"]
        if not path.is_file() or path.stat().st_size != int(expected["bytes"]):
            raise ValueError(f"model file missing or changed size: {path}")
        actual = sha256(path)
        if actual != expected["sha256"]:
            raise ValueError(f"model file hash changed: {expected['name']}")
        observed[expected["name"]] = actual
    return observed


def image_sha256(image: Any) -> str:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return sha256_bytes(buffer.getvalue())


def full_view(image: Any) -> Any:
    from PIL import Image

    output = image.convert("RGB").copy()
    if output.width > 960 or output.height > 640:
        output.thumbnail((960, 640), Image.Resampling.LANCZOS)
    return output


def prepare_method_inputs(
    *,
    protocol: dict[str, Any],
    c406: dict[str, Any],
    reference_path: Path,
    current_path: Path,
    instruction: str,
    candidate_bbox_xyxy: tuple[float, float, float, float],
) -> tuple[Any, Any, str, dict[str, str], dict[str, Any]]:
    """Prepare only method-visible inputs; no evaluator fields are accepted."""

    from PIL import Image

    reference = Image.open(reference_path).convert("RGB")
    current = Image.open(current_path).convert("RGB")
    provenance_spec = c406["method_interface"]["provenance"]
    provenance = candidate_provenance(
        reference,
        current,
        candidate_bbox_xyxy,
        CandidateProvenanceConfig(
            pixel_threshold=int(provenance_spec["pixel_threshold"]),
            minimum_changed_pixels=int(
                provenance_spec["minimum_changed_pixels"]
            ),
            minimum_changed_fraction=float(
                provenance_spec["minimum_changed_fraction"]
            ),
        ),
    )
    view1 = full_view(current)
    view_spec = protocol["views"]["local_view"]
    view2 = candidate_box_context_crop(
        current,
        candidate_bbox_xyxy,
        padding=int(view_spec["padding"]),
        maximum_size=tuple(int(value) for value in view_spec["maximum_size"]),
        maximum_upscale=float(view_spec["maximum_upscale"]),
        bracket_offset=int(view_spec["bracket_offset"]),
        bracket_length=int(view_spec["bracket_length"]),
        bracket_width=int(view_spec["bracket_width"]),
    )
    old_or_novel = "novel" if provenance.novel else "old"
    scorer = protocol["candidate_scorers"]
    natural = scorer["box_natural_hypothesis_likelihood"]
    suffix = natural["assessment_suffix"].format(
        instruction=instruction,
        old_or_novel=old_or_novel,
    )
    common = protocol["common_prompt"]
    first = scorer["box_label_symmetric_first_token"]
    prompts = {
        "first_ab": f"{common}\n{first['orientation_safe_A_risky_B']}\n{suffix}",
        "first_ba": f"{common}\n{first['orientation_risky_A_safe_B']}\n{suffix}",
        "hypothesis": f"{common}\n{suffix}",
    }
    audit = {
        "reference_sha256": sha256(reference_path),
        "current_sha256": sha256(current_path),
        "full_view_sha256": image_sha256(view1),
        "local_view_sha256": image_sha256(view2),
        "instruction_sha256": text_sha256(instruction),
        "candidate_bbox_xyxy": list(candidate_bbox_xyxy),
        "provenance": dataclasses.asdict(provenance),
        "prompt_sha256": {
            name: text_sha256(prompt) for name, prompt in prompts.items()
        },
    }
    audit["method_input_sha256"] = text_sha256(canonical_json(audit))
    return view1, view2, old_or_novel, prompts, audit


def processor_inputs(
    processor: Any,
    full_image: Any,
    local_image: Any,
    prompt: str,
) -> Any:
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
    )


def first_token_method_only(
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
    """Score only method-visible inputs at the first assistant token."""

    import torch

    inputs = processor_inputs(processor, full_image, local_image, prompt).to(device)
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


def mean_hypothesis_log_probability_method_only(
    *,
    model: Any,
    processor: Any,
    full_image: Any,
    local_image: Any,
    prompt: str,
    hypothesis: str,
    device: str,
) -> dict[str, Any]:
    """Teacher-force one natural hypothesis without accepting an evaluator label."""

    import torch

    prefix = processor_inputs(processor, full_image, local_image, prompt).to(device)
    token_ids = processor.tokenizer.encode(
        hypothesis,
        add_special_tokens=False,
    )
    if not token_ids:
        raise ValueError("hypothesis tokenization is empty")
    continuation = torch.tensor(
        [token_ids],
        dtype=prefix.input_ids.dtype,
        device=prefix.input_ids.device,
    )
    prefix_length = int(prefix.input_ids.shape[1])
    model_inputs = dict(prefix)
    model_inputs["input_ids"] = torch.cat(
        [prefix.input_ids, continuation],
        dim=1,
    )
    model_inputs["attention_mask"] = torch.cat(
        [
            prefix.attention_mask,
            torch.ones_like(continuation, dtype=prefix.attention_mask.dtype),
        ],
        dim=1,
    )
    if "mm_token_type_ids" not in prefix:
        raise ValueError("frozen Qwen3.5 processor omitted mm_token_type_ids")
    model_inputs["mm_token_type_ids"] = torch.cat(
        [
            prefix.mm_token_type_ids,
            torch.zeros_like(
                continuation,
                dtype=prefix.mm_token_type_ids.dtype,
            ),
        ],
        dim=1,
    )
    expected_length = prefix_length + len(token_ids)
    for field in ("input_ids", "attention_mask", "mm_token_type_ids"):
        if int(model_inputs[field].shape[1]) != expected_length:
            raise ValueError(f"teacher-forced {field} length changed")
    with torch.inference_mode():
        output = model(**model_inputs, use_cache=False)
        prediction_logits = output.logits[
            0,
            prefix_length - 1 : prefix_length + len(token_ids) - 1,
            :,
        ].float()
        log_probabilities = torch.log_softmax(prediction_logits, dim=-1)
        selected = log_probabilities.gather(
            1,
            continuation[0].unsqueeze(1),
        ).squeeze(1)
    result = {
        "hypothesis": hypothesis,
        "token_ids": token_ids,
        "token_count": len(token_ids),
        "sum_log_probability": float(selected.sum().item()),
        "mean_log_probability": float(selected.mean().item()),
    }
    del prefix, continuation, model_inputs, output, prediction_logits
    del log_probabilities, selected
    return result


def run_scores(
    protocol: dict[str, Any],
    c406: dict[str, Any],
    input_hashes: dict[str, str],
) -> None:
    import torch
    import transformers
    from transformers import AutoModelForMultimodalLM, AutoProcessor

    examples = build_examples(protocol)
    verify_example_images(examples)
    model_hashes = verify_model_snapshot(c406)
    expected_ids = [example["example_id"] for example in examples]
    prior_rows: dict[str, dict[str, Any]] = {}
    if CACHE_PATH.exists():
        prior = load_json(CACHE_PATH)
        if prior.get("protocol_sha256") != EXPECTED_PROTOCOL_SHA256:
            raise ValueError("incompatible pre-existing C410 cache")
        if prior.get("frozen_input_sha256") != input_hashes:
            raise ValueError("C410 cache frozen inputs changed")
        if prior.get("model_file_sha256") != model_hashes:
            raise ValueError("C410 cache model snapshot changed")
        cached_ids = [row["example_id"] for row in prior["rows"]]
        if len(cached_ids) != len(set(cached_ids)):
            raise ValueError("duplicate example ID in C410 cache")
        if not set(cached_ids).issubset(expected_ids):
            raise ValueError("unexpected example ID in C410 cache")
        prior_rows = {row["example_id"]: row for row in prior["rows"]}
        if set(prior_rows) == set(expected_ids):
            print("C410 score cache already complete", flush=True)
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
    natural = protocol["candidate_scorers"]["box_natural_hypothesis_likelihood"]

    ordered_rows = []
    for index, example in enumerate(examples, 1):
        view1, view2, observed_provenance, prompts, audit = prepare_method_inputs(
            protocol=protocol,
            c406=c406,
            reference_path=relative_file(example["reference"]),
            current_path=relative_file(example["current"]),
            instruction=example["instruction"],
            candidate_bbox_xyxy=tuple(
                float(value) for value in example["candidate_bbox_xyxy"]
            ),
        )
        if observed_provenance != example["expected_provenance"]:
            raise ValueError(
                f"provenance changed for {example['example_id']}: "
                f"{observed_provenance}"
            )
        cached = prior_rows.get(example["example_id"])
        if cached is not None:
            if cached["method_inputs"] != audit:
                raise ValueError(
                    f"method inputs changed for {example['example_id']}"
                )
            row = cached
        else:
            first_ab = first_token_method_only(
                model=model,
                processor=processor,
                full_image=view1,
                local_image=view2,
                prompt=prompts["first_ab"],
                token_a=token_a,
                token_b=token_b,
                device=str(model_spec["device"]),
            )
            first_ba = first_token_method_only(
                model=model,
                processor=processor,
                full_image=view1,
                local_image=view2,
                prompt=prompts["first_ba"],
                token_a=token_a,
                token_b=token_b,
                device=str(model_spec["device"]),
            )
            first_risk = label_symmetric_risk(
                safe_a_risky_b_logits=(
                    first_ab["logit_a"],
                    first_ab["logit_b"],
                ),
                risky_a_safe_b_logits=(
                    first_ba["logit_a"],
                    first_ba["logit_b"],
                ),
            )
            safe_hypothesis = mean_hypothesis_log_probability_method_only(
                model=model,
                processor=processor,
                full_image=view1,
                local_image=view2,
                prompt=prompts["hypothesis"],
                hypothesis=natural["safe_hypothesis"],
                device=str(model_spec["device"]),
            )
            risky_hypothesis = mean_hypothesis_log_probability_method_only(
                model=model,
                processor=processor,
                full_image=view1,
                local_image=view2,
                prompt=prompts["hypothesis"],
                hypothesis=natural["risky_hypothesis"],
                device=str(model_spec["device"]),
            )
            hypothesis_risk = restricted_binary_probability(
                safe_hypothesis["mean_log_probability"],
                risky_hypothesis["mean_log_probability"],
            )
            row = {
                "example_id": example["example_id"],
                "dataset": example["dataset"],
                "family_merged_after_scoring": example["family"],
                "scenario_merged_after_scoring": example["scenario_id"],
                "class_merged_after_scoring": example["class"],
                "label_merged_after_scoring": int(example["label"]),
                "method_received_evaluator_fields": False,
                "method_inputs": audit,
                "scores": {
                    "box_label_symmetric_first_token": {
                        "orientation_safe_A_risky_B": first_ab,
                        "orientation_risky_A_safe_B": first_ba,
                        "risk": first_risk,
                    },
                    "box_natural_hypothesis_likelihood": {
                        "safe": safe_hypothesis,
                        "risky": risky_hypothesis,
                        "risk": hypothesis_risk,
                    },
                },
            }
            prior_rows[example["example_id"]] = row
        ordered_rows.append(row)
        payload = {
            "candidate": "C410-score-cache",
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
                prior_rows[remaining["example_id"]]
                for remaining in examples[index:]
                if remaining["example_id"] in prior_rows
            ],
        }
        atomic_write_json(CACHE_PATH, payload)
        if index % 5 == 0 or index == len(examples):
            print(f"C410 scored {index}/{len(examples)}", flush=True)
    print(f"Wrote {CACHE_PATH.relative_to(ROOT)}", flush=True)


def evaluate_candidate(
    rows: list[dict[str, Any]],
    name: str,
    protocol: dict[str, Any],
) -> dict[str, Any]:
    from sklearn.metrics import roc_auc_score

    values = [
        {
            "example_id": row["example_id"],
            "dataset": row["dataset"],
            "family": row["family_merged_after_scoring"],
            "class": row["class_merged_after_scoring"],
            "label": int(row["label_merged_after_scoring"]),
            "risk": float(row["scores"][name]["risk"]),
        }
        for row in rows
    ]
    synthetic = [row for row in values if row["dataset"] == "synthetic"]
    reactflow = [row for row in values if row["dataset"] == "reactflow"]
    synthetic_auc = float(
        roc_auc_score(
            [row["label"] for row in synthetic],
            [row["risk"] for row in synthetic],
        )
    )
    reactflow_auc = float(
        roc_auc_score(
            [row["label"] for row in reactflow],
            [row["risk"] for row in reactflow],
        )
    )
    family_margins = {}
    for family in sorted({row["family"] for row in synthetic}):
        safe = [
            row["risk"]
            for row in synthetic
            if row["family"] == family and row["label"] == 0
        ]
        dangerous = [
            row["risk"]
            for row in synthetic
            if row["family"] == family and row["label"] == 1
        ]
        family_margins[family] = {
            "safe_mean": sum(safe) / len(safe),
            "dangerous_mean": sum(dangerous) / len(dangerous),
            "dangerous_minus_safe": (
                sum(dangerous) / len(dangerous) - sum(safe) / len(safe)
            ),
        }
    gates = protocol["evaluation"]["candidate_pass"]
    checks = {
        "synthetic_auc": (
            synthetic_auc + 1e-12 >= float(gates["synthetic_auc_minimum"])
        ),
        "reactflow_auc": (
            reactflow_auc + 1e-12 >= float(gates["reactflow_auc_minimum"])
        ),
        "all_family_margins_positive": all(
            row["dangerous_minus_safe"] > 0.0
            for row in family_margins.values()
        ),
    }
    return {
        "name": name,
        "synthetic_auc": synthetic_auc,
        "reactflow_auc": reactflow_auc,
        "minimum_domain_auc": min(synthetic_auc, reactflow_auc),
        "mean_domain_auc": (synthetic_auc + reactflow_auc) / 2.0,
        "family_margins": family_margins,
        "checks": checks,
        "passed": all(checks.values()),
        "predictions": values,
    }


def selection_key(candidate: dict[str, Any]) -> tuple[Any, ...]:
    cost = (
        0
        if candidate["name"] == "box_label_symmetric_first_token"
        else 1
    )
    return (
        int(not candidate["passed"]),
        -candidate["minimum_domain_auc"],
        -candidate["mean_domain_auc"],
        cost,
        candidate["name"],
    )


def finalize(
    protocol: dict[str, Any],
    input_hashes: dict[str, str],
) -> None:
    if OUTPUT_PATH.exists():
        raise FileExistsError(OUTPUT_PATH)
    if not CACHE_PATH.is_file():
        raise FileNotFoundError(CACHE_PATH)
    cache = load_json(CACHE_PATH)
    if cache["protocol_sha256"] != EXPECTED_PROTOCOL_SHA256:
        raise ValueError("C410 cache protocol mismatch")
    if cache["frozen_input_sha256"] != input_hashes:
        raise ValueError("C410 cache input hash mismatch")
    if len(cache["rows"]) != int(protocol["sample"]["total_examples"]):
        raise ValueError("C410 cache incomplete")
    names = list(protocol["candidate_scorers"])
    candidates = [
        evaluate_candidate(cache["rows"], name, protocol) for name in names
    ]
    selected = min(candidates, key=selection_key)
    passed = bool(selected["passed"])
    payload = {
        "candidate": "C410",
        "title": "Full-candidate-box risk scorer diagnostic",
        "created_utc": utc_now(),
        "git_head": git_head(),
        "protocol": str(PROTOCOL_PATH.relative_to(ROOT)),
        "protocol_sha256": EXPECTED_PROTOCOL_SHA256,
        "frozen_input_sha256": input_hashes,
        "score_cache_sha256": sha256(CACHE_PATH),
        "model_file_sha256": cache["model_file_sha256"],
        "external_boundary": {
            "browsergym_or_miniwob_episode_rendered": False,
            "external_task_reset": False,
            "external_reward_or_outcome_observed": False,
        },
        "candidates": candidates,
        "selected": {
            key: value
            for key, value in selected.items()
            if key != "predictions"
        },
        "score_rows": cache["rows"],
        "method_received_no_evaluator_fields": not any(
            row["method_received_evaluator_fields"] for row in cache["rows"]
        ),
        "passed": passed,
        "interpretation": (
            f"C409 diagnostic passed and selected {selected['name']} for a "
            "separate full development protocol. No live or external evaluation "
            "is authorized."
            if passed
            else "Neither full-box scorer passed C409. Record failure and require "
            "a stronger model or different risk representation."
        ),
        "next_step": (
            "Preregister the full remaining-seed synthetic calibration and "
            "unrecalibrated legacy transfer with the selected scorer."
            if passed
            else protocol["scientific_boundary"]["failure_rule"]
        ),
    }
    atomic_write_json(OUTPUT_PATH, payload)
    print(
        json.dumps(
            {
                "passed": passed,
                "candidates": [
                    {
                        key: value
                        for key, value in candidate.items()
                        if key not in {"predictions", "family_margins"}
                    }
                    | {
                        "minimum_family_margin": min(
                            row["dangerous_minus_safe"]
                            for row in candidate["family_margins"].values()
                        )
                    }
                    for candidate in candidates
                ],
                "selected": payload["selected"],
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
    protocol, c406, input_hashes = verify_inputs()
    if args.stage == "score":
        run_scores(protocol, c406, input_hashes)
    else:
        finalize(protocol, input_hashes)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
