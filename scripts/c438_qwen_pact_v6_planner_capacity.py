#!/usr/bin/env python3
"""Score pinned Qwen3.5-9B on the frozen C437 PACT-v6 planner cases."""

from __future__ import annotations

import argparse
import json
import platform
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT / "src", ROOT / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import c414_adaptive_semantic_risk_diagnostic as c414  # noqa: E402
import c416_qwen35_9b_capacity_diagnostic as c416  # noqa: E402
from rcrps.model_planner_v6 import (  # noqa: E402
    action_candidate_from_prompt_record_v6,
    parse_planner_decision_v6,
)


DEFAULT_PROTOCOL = ROOT / "validation" / "c437_pact_v6_planner_capacity_protocol.json"
CASES_PATH = ROOT / "validation" / "c437_pact_v6_planner_capacity_cases.json"
EXPECTED_CASES_SHA256 = (
    "1a00374f77ce257df48645b84600b515911bf69d83455670e63d4a0e807f7319"
)
OUTPUT_PATH = ROOT / "validation" / "c438_qwen_pact_v6_planner_capacity.json"
RUN_DIRECTORY = ROOT / "runs" / "c438_qwen_pact_v6_planner_capacity"
CACHE_PATH = RUN_DIRECTORY / "scores.json"
DEFAULT_MODEL_PATH = Path(str(Path.home() / ".cache" / "inversereserve" / "Qwen3.5-9B"))
MAX_NEW_TOKENS = 64
EXPECTED_CASE_COUNT = 148
PARENT_PATH = ROOT / "validation" / "c436_pact_v6_live_development_gate.json"
EXPECTED_PARENT_SHA256 = (
    "1823874416212f693c966c308bf652e39e509ca7de1e0e99819500052cabcc7c"
)
MODEL_CAPACITY_PARENT = ROOT / "validation" / "c416_qwen35_9b_capacity_diagnostic.json"
EXPECTED_MODEL_CAPACITY_PARENT_SHA256 = (
    "d7ef6157210f690a8a61e73eda2c584e558857e53e07a8f9e64c9215c0e8b719"
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def git_head() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()


def verify_protocol(path: Path, expected_sha256: str) -> tuple[dict[str, Any], str]:
    actual = c414.sha256(path)
    if actual != expected_sha256:
        raise ValueError(f"C437 protocol changed: {actual}")
    protocol = c414.load_json(path)
    if protocol.get("candidate") != "C437-PACT-v6-planner-capacity-protocol":
        raise ValueError("unexpected C437 protocol candidate")
    if protocol.get("cases_sha256") != EXPECTED_CASES_SHA256:
        raise ValueError("C437 protocol changed the frozen case binding")
    if protocol.get("expected_case_count") != EXPECTED_CASE_COUNT:
        raise ValueError("C437 protocol changed the expected case count")
    if protocol.get("activation", {}).get("parent_sha256") != EXPECTED_PARENT_SHA256:
        raise ValueError("C437 protocol changed the C436 parent binding")
    if c414.sha256(PARENT_PATH) != EXPECTED_PARENT_SHA256:
        raise ValueError("C436 parent artifact changed")
    parent = c414.load_json(PARENT_PATH)
    if parent.get("passed") is not True or parent.get(
        "information_boundary", {}
    ).get("confirmation_partition_opened") is not False:
        raise ValueError("C436 no longer authorizes the capacity gate")
    model_binding = protocol.get("model_binding", {})
    if (
        model_binding.get("capacity_parent_sha256")
        != EXPECTED_MODEL_CAPACITY_PARENT_SHA256
        or c414.sha256(MODEL_CAPACITY_PARENT)
        != EXPECTED_MODEL_CAPACITY_PARENT_SHA256
        or c414.load_json(MODEL_CAPACITY_PARENT).get("passed") is not True
    ):
        raise ValueError("C416 model-capacity parent changed")
    if protocol.get("generation") != {
        "enable_thinking": False,
        "do_sample": False,
        "max_new_tokens": MAX_NEW_TOKENS,
    }:
        raise ValueError("C437 generation settings changed")
    if protocol.get("information_boundary", {}).get(
        "confirmation_partition_opened"
    ) is not False:
        raise ValueError("C437 protocol reports an opened confirmation partition")
    note = protocol.get("design_note", {})
    if c414.sha256(ROOT / note["path"]) != note["sha256"]:
        raise ValueError("C437 design note changed")
    for relative, expected in protocol["source_sha256"].items():
        observed = c414.sha256(ROOT / relative)
        if observed != expected:
            raise ValueError(f"C437 source changed: {relative}: {observed}")
    return protocol, actual


def load_cases(protocol: dict[str, Any]) -> dict[str, Any]:
    actual = c414.sha256(CASES_PATH)
    if actual != EXPECTED_CASES_SHA256:
        raise ValueError(f"C437 planner cases changed: {actual}")
    cases = c414.load_json(CASES_PATH)
    if cases.get("candidate") != "C437-PACT-v6-shared-planner-capacity-cases":
        raise ValueError("unexpected C437 cases candidate")
    rows = list(cases.get("cases", []))
    if cases.get("case_count") != EXPECTED_CASE_COUNT or len(rows) != EXPECTED_CASE_COUNT:
        raise ValueError("C437 case count changed")
    expected_ids = [str(case["case_id"]) for case in rows]
    if len(expected_ids) != len(set(expected_ids)):
        raise ValueError("C437 case IDs are not unique")
    if any(
        case.get("method_received_task_id") is not False
        or case.get("method_received_seed") is not False
        or case.get("method_received_evaluator_fields") is not False
        or case.get("method_received_reward") is not False
        for case in rows
    ):
        raise ValueError("C437 cases report forbidden model inputs")
    if cases["counts_by_decision"] != protocol["expected_counts_by_decision"]:
        raise ValueError("C437 decision counts changed")
    if cases["counts_by_stratum"] != protocol["expected_counts_by_stratum"]:
        raise ValueError("C437 stratum counts changed")
    return cases


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
    raw_output = processor.tokenizer.decode(
        generated_ids, skip_special_tokens=True
    ).strip()
    row = {
        "case_id": case["case_id"],
        "method_received_task_id": False,
        "method_received_seed": False,
        "method_received_evaluator_fields": False,
        "method_received_reward": False,
        "messages_sha256": c414.text_sha256(
            json.dumps(case["messages"], ensure_ascii=False, sort_keys=True)
        ),
        "input_tokens": input_tokens,
        "generated_tokens": int(generated_ids.shape[0]),
        "raw_output": raw_output,
    }
    del inputs, generated, generated_ids
    return row


def verify_cache(
    cache: dict[str, Any],
    *,
    cases: dict[str, Any],
    protocol_sha256: str,
    model_hashes: dict[str, str],
) -> dict[str, dict[str, Any]]:
    if cache.get("candidate") != "C438-score-cache":
        raise ValueError("unexpected C438 cache candidate")
    if cache.get("protocol_sha256") != protocol_sha256:
        raise ValueError("C438 cache protocol changed")
    if cache.get("cases_sha256") != EXPECTED_CASES_SHA256:
        raise ValueError("C438 cache cases changed")
    if cache.get("model_file_sha256") != model_hashes:
        raise ValueError("C438 cache model snapshot changed")
    expected = {str(case["case_id"]) for case in cases["cases"]}
    rows = list(cache.get("rows", []))
    observed = [str(row["case_id"]) for row in rows]
    if len(observed) != len(set(observed)) or not set(observed) <= expected:
        raise ValueError("C438 cache case IDs are invalid")
    if any(
        row.get("method_received_task_id") is not False
        or row.get("method_received_seed") is not False
        or row.get("method_received_evaluator_fields") is not False
        or row.get("method_received_reward") is not False
        for row in rows
    ):
        raise ValueError("C438 cache reports forbidden model inputs")
    return {str(row["case_id"]): row for row in rows}


def score(
    *, protocol: dict[str, Any], protocol_sha256: str, model_path: Path
) -> None:
    import torch
    import transformers
    from transformers import AutoModelForMultimodalLM, AutoProcessor

    cases = load_cases(protocol)
    verified_inputs = c416.verify_inputs(model_path)
    c415 = verified_inputs[0]
    model_hashes = verified_inputs[-1]
    runtime = c415["runtime"]
    if torch.__version__ != runtime["torch"]:
        raise ValueError(f"Torch changed: {torch.__version__}")
    if transformers.__version__ != runtime["transformers"]:
        raise ValueError(f"Transformers changed: {transformers.__version__}")
    if torch.cuda.device_count() != 2:
        raise ValueError(
            f"C438 requires exactly two visible GPUs, got {torch.cuda.device_count()}"
        )
    processor = AutoProcessor.from_pretrained(model_path)
    template_audit = c416.validate_nonthinking_template(processor)
    model = AutoModelForMultimodalLM.from_pretrained(
        model_path,
        dtype=torch.bfloat16,
        device_map=str(runtime["device_map"]),
    )
    model.eval()

    prior: dict[str, dict[str, Any]] = {}
    if CACHE_PATH.is_file():
        prior = verify_cache(
            c414.load_json(CACHE_PATH),
            cases=cases,
            protocol_sha256=protocol_sha256,
            model_hashes=model_hashes,
        )
    ordered = []
    for index, case in enumerate(cases["cases"]):
        case_id = str(case["case_id"])
        row = prior.get(case_id)
        if row is None:
            row = generate_one(
                model=model,
                processor=processor,
                case=case,
                device="cuda:0",
            )
            prior[case_id] = row
        ordered.append(row)
        cache = {
            "candidate": "C438-score-cache",
            "updated_utc": utc_now(),
            "git_head": git_head(),
            "protocol_sha256": protocol_sha256,
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
            "rows": ordered
            + [
                prior[str(later["case_id"])]
                for later in cases["cases"][index + 1 :]
                if str(later["case_id"]) in prior
            ],
        }
        c414.atomic_write_json(CACHE_PATH, cache)
        print(
            f"C438 scored {index + 1}/{len(cases['cases'])}: {case_id}",
            flush=True,
        )


def evaluate_rows(
    cases: dict[str, Any], rows: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    case_by_id = {str(case["case_id"]): case for case in cases["cases"]}
    evaluations = []
    for row in rows:
        case = case_by_id[str(row["case_id"])]
        candidates = tuple(
            action_candidate_from_prompt_record_v6(record)
            for record in case["inventory"]
        )
        parsed = None
        parse_error = None
        try:
            decision = parse_planner_decision_v6(str(row["raw_output"]), candidates)
            parsed = {"decision": decision.decision, "bid": decision.bid}
        except Exception as error:  # exact failure is part of the sealed audit
            parse_error = f"{type(error).__name__}: {error}"
        correct = parsed in case["valid_outputs"] if parsed is not None else False
        expected_decisions = {
            output["decision"] for output in case["valid_outputs"]
        }
        if len(expected_decisions) != 1:
            raise ValueError(f"mixed expected decisions: {case['case_id']}")
        evaluations.append(
            {
                "case_id": case["case_id"],
                "stratum": case["stratum"],
                "origin": case["origin"],
                "expected_decision": next(iter(expected_decisions)),
                "valid_outputs": case["valid_outputs"],
                "raw_output": row["raw_output"],
                "parsed": parsed,
                "parse_error": parse_error,
                "correct": correct,
                "input_tokens": row["input_tokens"],
                "generated_tokens": row["generated_tokens"],
            }
        )

    def grouped(key: str) -> dict[str, dict[str, int]]:
        values = sorted({str(row[key]) for row in evaluations})
        return {
            value: {
                "correct": sum(
                    bool(row["correct"])
                    for row in evaluations
                    if str(row[key]) == value
                ),
                "cases": sum(str(row[key]) == value for row in evaluations),
            }
            for value in values
        }

    metrics = {
        "correct": sum(bool(row["correct"]) for row in evaluations),
        "cases": len(evaluations),
        "parse_successes": sum(row["parse_error"] is None for row in evaluations),
        "by_expected_decision": grouped("expected_decision"),
        "by_stratum": grouped("stratum"),
        "by_origin": grouped("origin"),
        "maximum_input_tokens": max(row["input_tokens"] for row in evaluations),
        "maximum_generated_tokens": max(
            row["generated_tokens"] for row in evaluations
        ),
        "raw_output_counts": dict(
            sorted(Counter(row["raw_output"] for row in evaluations).items())
        ),
    }
    return evaluations, metrics


def finalize(
    *, protocol: dict[str, Any], protocol_sha256: str, model_path: Path
) -> None:
    if OUTPUT_PATH.exists():
        raise FileExistsError(OUTPUT_PATH)
    cases = load_cases(protocol)
    verified_inputs = c416.verify_inputs(model_path)
    model_hashes = verified_inputs[-1]
    if not CACHE_PATH.is_file():
        raise FileNotFoundError(CACHE_PATH)
    cache = c414.load_json(CACHE_PATH)
    cached = verify_cache(
        cache,
        cases=cases,
        protocol_sha256=protocol_sha256,
        model_hashes=model_hashes,
    )
    expected_order = [str(case["case_id"]) for case in cases["cases"]]
    if set(cached) != set(expected_order):
        raise ValueError("C438 score cache is incomplete")
    rows = [cached[case_id] for case_id in expected_order]
    evaluations, metrics = evaluate_rows(cases, rows)
    checks = {
        "complete_frozen_grid": metrics["cases"] == EXPECTED_CASE_COUNT,
        "all_outputs_parse": metrics["parse_successes"] == metrics["cases"],
        "all_cases_correct": metrics["correct"] == metrics["cases"],
        "all_decision_strata_correct": all(
            value["correct"] == value["cases"]
            for value in metrics["by_expected_decision"].values()
        ),
        "all_semantic_strata_correct": all(
            value["correct"] == value["cases"]
            for value in metrics["by_stratum"].values()
        ),
        "all_origins_correct": all(
            value["correct"] == value["cases"]
            for value in metrics["by_origin"].values()
        ),
        "zero_forbidden_model_inputs": all(
            row.get("method_received_task_id") is False
            and row.get("method_received_seed") is False
            and row.get("method_received_evaluator_fields") is False
            and row.get("method_received_reward") is False
            for row in rows
        ),
    }
    passed = all(checks.values())
    payload = {
        "candidate": "C438-Qwen3.5-9B-PACT-v6-planner-capacity",
        "created_utc": utc_now(),
        "git_head": git_head(),
        "status": "outcome_free_consumed_and_synthetic_capacity",
        "protocol": str(DEFAULT_PROTOCOL.relative_to(ROOT)),
        "protocol_sha256": protocol_sha256,
        "cases": str(CASES_PATH.relative_to(ROOT)),
        "cases_sha256": EXPECTED_CASES_SHA256,
        "score_cache_sha256": c414.sha256(CACHE_PATH),
        "model_file_sha256": model_hashes,
        "template_audit": cache["template_audit"],
        "runtime": cache["runtime"],
        "generation": protocol["generation"],
        "information_boundary": protocol["information_boundary"],
        "evaluations": evaluations,
        "metrics": metrics,
        "checks": checks,
        "passed": passed,
        "next_step": protocol["decision_rule"]["on_pass" if passed else "on_failure"],
    }
    c414.atomic_write_json(OUTPUT_PATH, payload)
    print(
        json.dumps(
            {"passed": passed, "metrics": metrics, "checks": checks}, indent=2
        )
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", choices=("score", "finalize"), required=True)
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--expected-protocol-sha256", required=True)
    parser.add_argument("--model-path", type=Path, default=DEFAULT_MODEL_PATH)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    protocol, protocol_sha256 = verify_protocol(
        args.protocol, args.expected_protocol_sha256
    )
    if args.stage == "score":
        score(
            protocol=protocol,
            protocol_sha256=protocol_sha256,
            model_path=args.model_path,
        )
    else:
        finalize(
            protocol=protocol,
            protocol_sha256=protocol_sha256,
            model_path=args.model_path,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
