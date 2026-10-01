#!/usr/bin/env python3
"""Score Qwen3.5-9B on the fixed C423 structured planner cases."""

from __future__ import annotations

import argparse
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT / "src", ROOT / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import c414_adaptive_semantic_risk_diagnostic as c414  # noqa: E402
import c416_qwen35_9b_capacity_diagnostic as c416  # noqa: E402
from rcrps.structured_planner import (  # noqa: E402
    ActionCandidate,
    parse_planner_decision,
)


CASES_PATH = ROOT / "validation" / "c423_structured_planner_development_cases.json"
EXPECTED_CASES_SHA256 = "539ce84deeff4be3525bdc60c7e4fd24603e6253bac414ea9580298eff537b35"
OUTPUT_PATH = ROOT / "validation" / "c424_qwen_structured_planner_capacity.json"
RUN_DIRECTORY = ROOT / "runs" / "c424_qwen_structured_planner_capacity"
CACHE_PATH = RUN_DIRECTORY / "scores.json"
DEFAULT_MODEL_PATH = Path(str(Path.home() / ".cache" / "inversereserve" / "Qwen3.5-9B"))
MAX_NEW_TOKENS = 64


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def git_head() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()


def load_cases() -> dict[str, Any]:
    actual = c414.sha256(CASES_PATH)
    if actual != EXPECTED_CASES_SHA256:
        raise ValueError(f"C423 planner cases changed: {actual}")
    payload = c414.load_json(CASES_PATH)
    if payload.get("case_count") != 13 or len(payload.get("cases", [])) != 13:
        raise ValueError("C423 planner case count changed")
    if any(case.get("method_received_evaluator_fields") is not False for case in payload["cases"]):
        raise ValueError("C423 case reports evaluator leakage")
    return payload


def candidate_from_record(record: dict[str, Any]) -> ActionCandidate:
    return ActionCandidate(
        bid=str(record["bid"]),
        operation=str(record["op"]),
        role=str(record["role"]),
        label=str(record["label"]),
        state=tuple(sorted(record.get("state", {}).items())),
        preview_kind=record.get("preview_kind"),
        semantic_bid=str(record["semantic_bid"]),
        parent_bid=record.get("parent_bid"),
    )


def processor_messages(case: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "role": str(message["role"]),
            "content": [{"type": "text", "text": str(message["content"])}],
        }
        for message in case["messages"]
    ]


def generate_one(
    *, model: Any, processor: Any, case: dict[str, Any], device: str
) -> dict[str, Any]:
    import torch

    messages = processor_messages(case)
    inputs = processor.apply_chat_template(
        messages,
        add_generation_prompt=True,
        tokenize=True,
        return_dict=True,
        return_tensors="pt",
        enable_thinking=False,
    ).to(device)
    input_tokens = int(inputs.input_ids.shape[1])
    with torch.inference_mode():
        generated = model.generate(
            **inputs,
            max_new_tokens=MAX_NEW_TOKENS,
            do_sample=False,
            use_cache=True,
        )
    generated_ids = generated[0, input_tokens:]
    text = processor.tokenizer.decode(generated_ids, skip_special_tokens=True).strip()
    row = {
        "case_id": case["case_id"],
        "method_received_evaluator_fields": False,
        "messages_sha256": c414.text_sha256(
            json.dumps(case["messages"], ensure_ascii=False, sort_keys=True)
        ),
        "input_tokens": input_tokens,
        "generated_tokens": int(generated_ids.shape[0]),
        "raw_output": text,
    }
    del inputs, generated, generated_ids
    return row


def verify_cache(
    cache: dict[str, Any], cases: dict[str, Any], model_hashes: dict[str, str]
) -> dict[str, dict[str, Any]]:
    if cache.get("candidate") != "C424-score-cache":
        raise ValueError("unexpected C424 cache candidate")
    if cache.get("cases_sha256") != EXPECTED_CASES_SHA256:
        raise ValueError("C424 cache case input changed")
    if cache.get("model_file_sha256") != model_hashes:
        raise ValueError("C424 cache model snapshot changed")
    expected_ids = {case["case_id"] for case in cases["cases"]}
    rows = cache.get("rows", [])
    observed_ids = [row["case_id"] for row in rows]
    if len(observed_ids) != len(set(observed_ids)) or not set(observed_ids) <= expected_ids:
        raise ValueError("C424 cache case IDs are invalid")
    if any(row.get("method_received_evaluator_fields") is not False for row in rows):
        raise ValueError("C424 cache reports evaluator leakage")
    return {str(row["case_id"]): row for row in rows}


def score(model_path: Path) -> None:
    import torch
    import transformers
    from transformers import AutoModelForMultimodalLM, AutoProcessor

    cases = load_cases()
    verified_inputs = c416.verify_inputs(model_path)
    c415 = verified_inputs[0]
    model_hashes = verified_inputs[-1]
    runtime = c415["runtime"]
    if torch.__version__ != runtime["torch"]:
        raise ValueError(f"Torch changed: {torch.__version__}")
    if transformers.__version__ != runtime["transformers"]:
        raise ValueError(f"Transformers changed: {transformers.__version__}")
    if torch.cuda.device_count() != 2:
        raise ValueError(f"C424 requires exactly two visible GPUs, got {torch.cuda.device_count()}")
    processor = AutoProcessor.from_pretrained(model_path)
    template_audit = c416.validate_nonthinking_template(processor)
    model = AutoModelForMultimodalLM.from_pretrained(
        model_path,
        dtype=torch.bfloat16,
        device_map=str(runtime["device_map"]),
    )
    model.eval()

    prior_rows: dict[str, dict[str, Any]] = {}
    if CACHE_PATH.is_file():
        prior_rows = verify_cache(c414.load_json(CACHE_PATH), cases, model_hashes)
    ordered_rows = []
    for index, case in enumerate(cases["cases"]):
        case_id = str(case["case_id"])
        row = prior_rows.get(case_id)
        if row is None:
            row = generate_one(
                model=model,
                processor=processor,
                case=case,
                device="cuda:0",
            )
            prior_rows[case_id] = row
        ordered_rows.append(row)
        cache = {
            "candidate": "C424-score-cache",
            "updated_utc": utc_now(),
            "git_head": git_head(),
            "cases_sha256": EXPECTED_CASES_SHA256,
            "model_file_sha256": model_hashes,
            "template_audit": template_audit,
            "runtime": {
                "python": sys.version,
                "platform": platform.platform(),
                "torch": torch.__version__,
                "transformers": transformers.__version__,
                "cuda_devices": [
                    torch.cuda.get_device_name(device)
                    for device in range(torch.cuda.device_count())
                ],
                "device_map": runtime["device_map"],
            },
            "rows": ordered_rows
            + [
                prior_rows[str(later["case_id"])]
                for later in cases["cases"][index + 1 :]
                if str(later["case_id"]) in prior_rows
            ],
        }
        c414.atomic_write_json(CACHE_PATH, cache)
        print(f"C424 scored {index + 1}/{len(cases['cases'])}: {case_id}", flush=True)


def evaluate_rows(
    cases: dict[str, Any], rows: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    case_by_id = {str(case["case_id"]): case for case in cases["cases"]}
    evaluations = []
    for row in rows:
        case = case_by_id[str(row["case_id"])]
        candidates = tuple(candidate_from_record(record) for record in case["inventory"])
        parsed = None
        parse_error = None
        try:
            decision = parse_planner_decision(str(row["raw_output"]), candidates)
            parsed = {"decision": decision.decision, "bid": decision.bid}
        except Exception as error:  # exact error is part of the development audit
            parse_error = f"{type(error).__name__}: {error}"
        valid = parsed in case["valid_outputs"] if parsed is not None else False
        expected_decision = {item["decision"] for item in case["valid_outputs"]}
        if len(expected_decision) != 1:
            raise ValueError(f"mixed expected decisions: {case['case_id']}")
        evaluations.append(
            {
                "case_id": case["case_id"],
                "expected_decision": next(iter(expected_decision)),
                "valid_outputs": case["valid_outputs"],
                "raw_output": row["raw_output"],
                "parsed": parsed,
                "parse_error": parse_error,
                "correct": valid,
                "input_tokens": row["input_tokens"],
                "generated_tokens": row["generated_tokens"],
            }
        )
    decision_counts = {}
    for decision_type in ("commit", "explore"):
        subset = [row for row in evaluations if row["expected_decision"] == decision_type]
        decision_counts[decision_type] = {
            "correct": sum(row["correct"] for row in subset),
            "cases": len(subset),
        }
    metrics = {
        "correct": sum(row["correct"] for row in evaluations),
        "cases": len(evaluations),
        "parse_successes": sum(row["parse_error"] is None for row in evaluations),
        "by_expected_decision": decision_counts,
        "maximum_input_tokens": max(row["input_tokens"] for row in evaluations),
        "maximum_generated_tokens": max(row["generated_tokens"] for row in evaluations),
    }
    return evaluations, metrics


def finalize(model_path: Path) -> None:
    cases = load_cases()
    verified_inputs = c416.verify_inputs(model_path)
    model_hashes = verified_inputs[-1]
    if not CACHE_PATH.is_file():
        raise FileNotFoundError(CACHE_PATH)
    cache = c414.load_json(CACHE_PATH)
    cached = verify_cache(cache, cases, model_hashes)
    expected_order = [str(case["case_id"]) for case in cases["cases"]]
    if set(cached) != set(expected_order):
        raise ValueError("C424 score cache is incomplete")
    rows = [cached[case_id] for case_id in expected_order]
    evaluations, metrics = evaluate_rows(cases, rows)
    checks = {
        "all_outputs_parse": metrics["parse_successes"] == metrics["cases"],
        "all_cases_correct": metrics["correct"] == metrics["cases"],
        "all_commit_cases_correct": metrics["by_expected_decision"]["commit"]["correct"]
        == metrics["by_expected_decision"]["commit"]["cases"],
        "all_explore_cases_correct": metrics["by_expected_decision"]["explore"]["correct"]
        == metrics["by_expected_decision"]["explore"]["cases"],
    }
    payload = {
        "candidate": "C424-Qwen3.5-9B-structured-planner-capacity",
        "created_utc": utc_now(),
        "git_head": git_head(),
        "status": "development_only_consumed_tasks",
        "cases": str(CASES_PATH.relative_to(ROOT)),
        "cases_sha256": EXPECTED_CASES_SHA256,
        "score_cache_sha256": c414.sha256(CACHE_PATH),
        "model_file_sha256": model_hashes,
        "template_audit": cache["template_audit"],
        "runtime": cache["runtime"],
        "generation": {
            "enable_thinking": False,
            "do_sample": False,
            "max_new_tokens": MAX_NEW_TOKENS,
        },
        "method_information_boundary": cases["method_information_boundary"],
        "evaluations": evaluations,
        "metrics": metrics,
        "checks": checks,
        "passed": all(checks.values()),
        "next_step": (
            "Integrate the frozen structured planner with matched development agents."
            if all(checks.values())
            else "Revise or factorize the planner only on these consumed development cases; do not open fresh heldout tasks."
        ),
    }
    c414.atomic_write_json(OUTPUT_PATH, payload)
    print(json.dumps({"passed": payload["passed"], "metrics": metrics, "checks": checks}, indent=2))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", choices=("score", "finalize"), required=True)
    parser.add_argument("--model-path", type=Path, default=DEFAULT_MODEL_PATH)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.stage == "score":
        score(args.model_path)
    else:
        finalize(args.model_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
