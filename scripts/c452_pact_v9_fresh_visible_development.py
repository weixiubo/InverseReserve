#!/usr/bin/env python3
"""One-open fresh visible-development gate for PACT-v9."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT / "src", ROOT / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import c414_adaptive_semantic_risk_diagnostic as c414  # noqa: E402
import c427_pact_live_development as c427  # noqa: E402
import c433_fresh_observation_preflight as c433  # noqa: E402
import c434_pact_v4_live_development_gate as c434  # noqa: E402
import c444_pact_v7_matched_confirmation as c444  # noqa: E402
from rcrps.confirmation_agents_v9 import FullPactConfirmationDriverV9  # noqa: E402


DEFAULT_PROTOCOL = ROOT / "validation" / "c451_pact_v9_fresh_visible_protocol.json"
OUTPUT_PATH = ROOT / "validation" / "c452_pact_v9_fresh_visible_development.json"
RUN_DIRECTORY = ROOT / "runs" / "c452_pact_v9_fresh_visible_development"
EPISODE_DIRECTORY = RUN_DIRECTORY / "episodes"
CLAIM_DIRECTORY = RUN_DIRECTORY / "claims"
MODEL_CACHE_PATH = RUN_DIRECTORY / "planner_cache.sqlite3"
MODEL_RUNTIME_PATH = RUN_DIRECTORY / "model_runtime.json"
DEFAULT_MODEL_PATH = Path(
    os.environ.get(
        "INVERSERESERVE_MODEL_PATH",
        ROOT / "models" / "Qwen3.5-9B",
    )
)
PARENT_C450 = ROOT / "validation" / "c450_pact_v9_consumed_regression.json"
EXPECTED_PARENT_C450_SHA256 = (
    "04fe49a6ba54a1e3276a51755f89681330772c91cc8ee78de9d9878c79387bd4"
)
PARENT_C449 = ROOT / "validation" / "c449_c448_autocomplete_failure_diagnostic.json"
EXPECTED_PARENT_C449_SHA256 = (
    "871ee5730dcc4bf95b18973724826368b6979016cb4427b48f6f0adb66a785f4"
)
PARENT_C448 = ROOT / "validation" / "c448_pact_v8_fresh_repair_development.json"
EXPECTED_PARENT_C448_SHA256 = (
    "7795bd8b4e062ea6549e8d1fb176ddb165d54a794fd81710db8e3eb20c205162"
)
METHOD = "full_pact_v9"


def verify_protocol(path: Path, expected_sha256: str) -> tuple[dict[str, Any], str]:
    actual = c444.sha256(path)
    if actual != expected_sha256:
        raise ValueError(f"C451 protocol changed: {actual}")
    protocol = c414.load_json(path)
    if protocol.get("candidate") != "C451-PACT-v9-fresh-visible-protocol":
        raise ValueError("unexpected C451 protocol candidate")
    if (
        c444.sha256(PARENT_C450) != EXPECTED_PARENT_C450_SHA256
        or c414.load_json(PARENT_C450).get("passed") is not True
    ):
        raise ValueError("C450 consumed parent changed")
    if c444.sha256(PARENT_C449) != EXPECTED_PARENT_C449_SHA256:
        raise ValueError("C449 diagnostic parent changed")
    if (
        c444.sha256(PARENT_C448) != EXPECTED_PARENT_C448_SHA256
        or c414.load_json(PARENT_C448).get("passed") is not False
    ):
        raise ValueError("C448 failed parent changed")
    if protocol["activation"] != {
        "passing_consumed_regression": str(PARENT_C450.relative_to(ROOT)),
        "passing_consumed_regression_sha256": EXPECTED_PARENT_C450_SHA256,
        "passing_consumed_regression_passed": True,
        "sealed_repair_diagnosis": str(PARENT_C449.relative_to(ROOT)),
        "sealed_repair_diagnosis_sha256": EXPECTED_PARENT_C449_SHA256,
        "failed_prior_visible_development": str(PARENT_C448.relative_to(ROOT)),
        "failed_prior_visible_development_sha256": EXPECTED_PARENT_C448_SHA256,
        "failed_prior_visible_development_remains_immutable": True,
    }:
        raise ValueError("unexpected C451 activation")
    expected_partitions = {
        "fresh_visible_development": list(range(27421, 27441)),
        "repair_holdout_embargoed": list(range(27411, 27421)),
        "final_confirmation_embargoed": list(range(27501, 27521)),
    }
    if protocol["seed_partitions"] != expected_partitions:
        raise ValueError("C451 seed partitions changed")
    sets = [set(values) for values in expected_partitions.values()]
    if any(left & right for index, left in enumerate(sets) for right in sets[index + 1 :]):
        raise ValueError("C451 seed partitions overlap")
    if protocol["previously_opened_development_seeds"] != list(range(27401, 27411)):
        raise ValueError("C451 opened-seed history changed")
    if protocol["information_boundary"] != {
        "previous_visible_development_opened": True,
        "fresh_visible_development_opened": False,
        "repair_holdout_opened": False,
        "final_confirmation_opened": False,
        "task_seed_reward_and_evaluator_harness_only": True,
        "reward_or_evaluator_forwarded_to_method": False,
    }:
        raise ValueError("C451 information boundary changed")
    if protocol["repositories"] != c444.EXPECTED_REPOSITORIES:
        raise ValueError("C451 repository pins changed")
    for name, expected_head in c444.EXPECTED_REPOSITORIES.items():
        c444.verify_clean_repository(c444.REPOSITORY_PATHS[name], expected_head)
    for relative, expected in protocol["source_sha256"].items():
        if c444.sha256(ROOT / relative) != expected:
            raise ValueError(f"C451 source changed: {relative}")
    note = protocol["preregistration"]
    if c444.sha256(ROOT / note["path"]) != note["sha256"]:
        raise ValueError("C451 preregistration changed")
    return protocol, actual


def manifest(protocol: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for seed_index, seed in enumerate(
        protocol["seed_partitions"]["fresh_visible_development"]
    ):
        for task_index, task in enumerate(protocol["tasks"]):
            task_id = task["task_id"]
            rows.append(
                {
                    "episode_index": len(rows),
                    "task_index": task_index,
                    "seed_index": seed_index,
                    "arm_position": 0,
                    "task": task_id,
                    "family_group": task["family_group"],
                    "seed": int(seed),
                    "method": METHOD,
                    "episode_id": f"{task_id}__seed{int(seed)}__{METHOD}",
                }
            )
    if len(rows) != protocol["expected_fresh_visible_episodes"]:
        raise ValueError("C451 fresh visible grid changed")
    return rows


def claim_path(episode: dict[str, Any]) -> Path:
    return CLAIM_DIRECTORY / f"{episode['episode_id']}.json"


def episode_path(episode: dict[str, Any]) -> Path:
    return EPISODE_DIRECTORY / f"{episode['episode_id']}.json"


def completed(episode: dict[str, Any], protocol_sha256: str) -> bool:
    claim = claim_path(episode)
    result = episode_path(episode)
    if not claim.exists() and not result.exists():
        return False
    if not claim.is_file() or not result.is_file():
        raise RuntimeError(f"C452 unmatched claim/result: {episode['episode_id']}")
    claim_row = c414.load_json(claim)
    result_row = c414.load_json(result)
    if (
        claim_row.get("status") != "complete"
        or claim_row.get("episode") != episode
        or claim_row.get("protocol_sha256") != protocol_sha256
        or claim_row.get("episode_sha256") != c444.sha256(result)
        or result_row.get("complete") is not True
        or result_row.get("episode") != episode
        or result_row.get("protocol_sha256") != protocol_sha256
    ):
        raise RuntimeError(f"incompatible C452 episode: {episode['episode_id']}")
    return True


def open_claim(episode: dict[str, Any], protocol_sha256: str) -> None:
    path = claim_path(episode)
    if path.exists() or episode_path(episode).exists():
        raise FileExistsError(f"C452 episode already opened: {episode['episode_id']}")
    c414.atomic_write_json(
        path,
        {
            "candidate": "C452-fresh-visible-open-claim",
            "created_utc": c427.utc_now(),
            "status": "claimed_before_reset",
            "protocol_sha256": protocol_sha256,
            "episode": episode,
        },
    )


def close_claim(
    episode: dict[str, Any], protocol_sha256: str, result_path: Path
) -> None:
    c414.atomic_write_json(
        claim_path(episode),
        {
            "candidate": "C452-fresh-visible-open-claim",
            "completed_utc": c427.utc_now(),
            "status": "complete",
            "protocol_sha256": protocol_sha256,
            "episode": episode,
            "episode_sha256": c444.sha256(result_path),
        },
    )


def run(
    *, protocol: dict[str, Any], protocol_sha256: str, model_path: Path
) -> None:
    rows = manifest(protocol)
    EPISODE_DIRECTORY.mkdir(parents=True, exist_ok=True)
    CLAIM_DIRECTORY.mkdir(parents=True, exist_ok=True)
    pending = [episode for episode in rows if not completed(episode, protocol_sha256)]
    if not pending:
        print("C452 fresh visible grid already complete", flush=True)
        return
    c444.MODEL_CACHE_PATH = MODEL_CACHE_PATH
    c444.MODEL_RUNTIME_PATH = MODEL_RUNTIME_PATH
    service = c444.FrozenModelServiceV7(
        protocol=protocol,
        protocol_sha256=protocol_sha256,
        model_path=model_path,
    )
    parent_protocol = c414.load_json(c434.C433_PROTOCOL)
    try:
        with c427.MiniwobServer(c433.HTML_ROOT) as base_url:
            for episode in pending:
                open_claim(episode, protocol_sha256)
                environment = None
                try:
                    try:
                        environment = c427.make_environment(
                            episode["task"], base_url, parent_protocol
                        )
                        observation, _discarded_reset_info = environment.reset(
                            seed=episode["seed"]
                        )
                    except Exception as error:
                        result = c444.infrastructure_reset_failure(
                            episode, protocol_sha256, error
                        )
                    else:
                        driver = FullPactConfirmationDriverV9(
                            environment=environment,
                            observation=observation,
                            budgets=protocol["budgets"],
                            planner_generate=service.generate,
                        )
                        try:
                            driver.run()
                        except Exception:
                            if driver.executor.infrastructure_error is None:
                                raise
                        result = driver.result()
                        result["episode"] = episode
                        result["protocol_sha256"] = protocol_sha256
                finally:
                    if environment is not None:
                        environment.close()
                path = episode_path(episode)
                c414.atomic_write_json(path, result)
                close_claim(episode, protocol_sha256, path)
                print(
                    json.dumps(
                        {
                            "complete": episode["episode_index"] + 1,
                            "total": len(rows),
                            "episode_id": episode["episode_id"],
                        }
                    ),
                    flush=True,
                )
                if result["infrastructure_failure"]:
                    raise RuntimeError("C452 stopped after infrastructure failure")
    finally:
        service.close()


def recovery_for(events: list[dict[str, Any]], failed_index: int) -> str:
    later = [event for event in events if int(event["event_index"]) > failed_index]
    dynamic = any(
        event.get("type") == "restoration"
        and event.get("trigger") == "dynamic public compensation"
        and event.get("passed") is True
        for event in later
    ) and any(
        event.get("type") == "postcondition"
        and event.get("context") == "typed retry"
        and event.get("passed") is True
        for event in later
    )
    if dynamic:
        return "dynamic_compensation_restored_and_retry_passed"
    if any(
        event.get("type") == "restoration" and event.get("passed") is True
        for event in later
    ):
        return "static_restoration_passed"
    return "unrecovered"


def finalize(protocol: dict[str, Any], protocol_sha256: str) -> None:
    if OUTPUT_PATH.exists():
        raise FileExistsError(OUTPUT_PATH)
    rows = []
    compact = []
    for episode in manifest(protocol):
        if not completed(episode, protocol_sha256):
            raise RuntimeError(f"incomplete C452 episode: {episode['episode_id']}")
        path = episode_path(episode)
        row = c414.load_json(path)
        rows.append(row)
        compact.append(c444.compact_episode(row, path))

    postcondition_failures = []
    v9_autocomplete_checks = []
    for row in rows:
        events = row.get("runtime_events", [])
        for event in events:
            if (
                event.get("type") == "postcondition"
                and event.get("contract_kind") == "autocomplete_query"
            ):
                v9_autocomplete_checks.append(
                    {
                        "episode_id": row["episode"]["episode_id"],
                        "task": row["episode"]["task"],
                        "seed": row["episode"]["seed"],
                        "passed": event["passed"],
                        "reason": event["reason"],
                        "checker_version": event.get("checker_version"),
                    }
                )
            if event.get("type") == "postcondition" and event.get("passed") is False:
                postcondition_failures.append(
                    {
                        "episode_id": row["episode"]["episode_id"],
                        "task": row["episode"]["task"],
                        "seed": row["episode"]["seed"],
                        "kind": event.get("contract_kind"),
                        "reason": event.get("reason"),
                        "recovery": recovery_for(events, int(event["event_index"])),
                    }
                )
    population_fallback_passes = [
        row
        for row in v9_autocomplete_checks
        if row["passed"] and "newly populated suggestion rows" in row["reason"]
    ]
    repeated_effect_keys = {}
    for row in rows:
        counts = Counter(
            record["key_sha256"] for record in row.get("effect_ledger_v8", [])
        )
        repeated = {key: count for key, count in sorted(counts.items()) if count > 1}
        if repeated:
            repeated_effect_keys[row["episode"]["episode_id"]] = repeated
    by_task = {}
    for task in protocol["tasks"]:
        subset = [row for row in rows if row["episode"]["task"] == task["task_id"]]
        by_task[task["task_id"]] = {
            "success": sum(bool(row["success"]) for row in subset),
            "episodes": len(subset),
        }
    success = sum(bool(row["success"]) for row in rows)
    metric_names = (
        "gui_actions",
        "planner_calls",
        "planner_parse_failures",
        "typed_transactions",
        "certified_commits",
        "uncertified_commits",
        "restoration_attempts",
        "restoration_passes",
        "wrong_terminal_commits",
        "terminal_transactions",
        "action_errors",
        "commit_effect_passes",
        "commit_effect_failures",
        "quarantined_commit_keys",
        "resolved_transaction_bids",
        "inverse_reservation_stops",
    )
    metrics = {
        "success": success,
        "episodes": len(rows),
        **{
            name: sum(int(row["metrics"].get(name, 0)) for row in rows)
            for name in metric_names
        },
        "runtime_halts": sum(
            bool(row["metrics"]["runtime_halted"]) for row in rows
        ),
        "method_failures": sum(row["method_failure"] is not None for row in rows),
        "infrastructure_failures": sum(
            bool(row["infrastructure_failure"]) for row in rows
        ),
        "raw_postcondition_failures": len(postcondition_failures),
        "verified_postcondition_recoveries": sum(
            row["recovery"] != "unrecovered" for row in postcondition_failures
        ),
        "unrecovered_postcondition_failures": sum(
            row["recovery"] == "unrecovered" for row in postcondition_failures
        ),
        "v9_autocomplete_checks": len(v9_autocomplete_checks),
        "v9_population_fallback_passes": len(population_fallback_passes),
    }
    expected_per_family = len(
        protocol["seed_partitions"]["fresh_visible_development"]
    )
    checks = {
        "complete_one_open_grid": len(rows)
        == protocol["expected_fresh_visible_episodes"],
        "repair_holdout_remains_unopened": protocol["information_boundary"][
            "repair_holdout_opened"
        ]
        is False,
        "final_confirmation_remains_unopened": protocol["information_boundary"][
            "final_confirmation_opened"
        ]
        is False,
        "zero_infrastructure_failures": metrics["infrastructure_failures"] == 0,
        "zero_forbidden_method_inputs": all(
            row["method_input"]["method_received_task_id"] is False
            and row["method_input"]["method_received_seed"] is False
            and row["method_input"]["method_received_reward"] is False
            and row["method_input"]["method_received_evaluator_fields"] is False
            and row["evaluation_audit"]["reward_or_info_forwarded_to_method"] is False
            for row in rows
        ),
        "all_budgets_respected": all(
            row["metrics"]["gui_actions"]
            <= protocol["budgets"]["maximum_gui_actions"]
            and row["metrics"]["planner_calls"]
            <= protocol["budgets"]["maximum_planner_calls"]
            and row["metrics"]["wall_seconds"]
            <= protocol["budgets"]["maximum_wall_seconds"]
            for row in rows
        ),
        "all_fresh_visible_success": success
        == protocol["expected_fresh_visible_episodes"],
        "every_family_perfect": all(
            row == {"success": expected_per_family, "episodes": expected_per_family}
            for row in by_task.values()
        ),
        "all_autocomplete_checks_are_v9": bool(v9_autocomplete_checks)
        and all(
            row["checker_version"] == "PACT-v9-suggestion-population"
            for row in v9_autocomplete_checks
        ),
        "minimum_live_population_fallback_coverage": len(population_fallback_passes)
        >= protocol["fresh_visible_gates"][
            "minimum_live_population_fallback_passes"
        ],
        "zero_parser_failures": metrics["planner_parse_failures"] == 0,
        "zero_action_errors": metrics["action_errors"] == 0,
        "zero_runtime_halts": metrics["runtime_halts"] == 0,
        "zero_method_failures": metrics["method_failures"] == 0,
        "zero_uncertified_commits": metrics["uncertified_commits"] == 0,
        "zero_wrong_terminal_commits": metrics["wrong_terminal_commits"] == 0,
        "zero_terminal_transactions": metrics["terminal_transactions"] == 0,
        "zero_unrecovered_postconditions": metrics[
            "unrecovered_postcondition_failures"
        ]
        == 0,
        "all_raw_postconditions_recovered": metrics[
            "verified_postcondition_recoveries"
        ]
        == metrics["raw_postcondition_failures"],
        "all_cleanup_restorations_pass": metrics["restoration_attempts"]
        == metrics["restoration_passes"],
        "zero_repeated_effect_keys": not repeated_effect_keys,
        "zero_no_effect_commits": metrics["commit_effect_failures"] == 0,
        "zero_inverse_reservation_stops": metrics["inverse_reservation_stops"]
        == 0,
        "model_only_for_multirow_envelopes": all(
            (event.get("model") is not None)
            == (len(event["envelope"]["candidates"]) > 1)
            for row in rows
            for event in row["trace"]
            if event.get("type") == "envelope_decision_v8"
            and event["envelope"]["decision"] != "abstain"
        ),
    }
    passed = all(checks.values())
    payload = {
        "candidate": "C452-PACT-v9-fresh-visible-development",
        "created_utc": c427.utc_now(),
        "git_head": c444.git_head(),
        "status": "fresh_visible_development_complete",
        "protocol": str(DEFAULT_PROTOCOL.relative_to(ROOT)),
        "protocol_sha256": protocol_sha256,
        "previous_visible_development_opened": True,
        "fresh_visible_development_opened": True,
        "repair_holdout_opened": False,
        "final_confirmation_opened": False,
        "model_runtime": str(MODEL_RUNTIME_PATH.relative_to(ROOT)),
        "model_runtime_sha256": c444.sha256(MODEL_RUNTIME_PATH),
        "planner_cache": str(MODEL_CACHE_PATH.relative_to(ROOT)),
        "planner_cache_sha256": c444.sha256(MODEL_CACHE_PATH),
        "episode_rows": compact,
        "by_task": by_task,
        "metrics": metrics,
        "postcondition_failures": postcondition_failures,
        "v9_autocomplete_checks": v9_autocomplete_checks,
        "population_fallback_passes": population_fallback_passes,
        "repeated_effect_keys": repeated_effect_keys,
        "checks": checks,
        "passed": passed,
        "next_step": protocol["decision_rule"]["on_pass" if passed else "on_failure"],
    }
    c414.atomic_write_json(OUTPUT_PATH, payload)
    print(
        json.dumps(
            {
                "passed": passed,
                "by_task": by_task,
                "metrics": metrics,
                "postcondition_failures": postcondition_failures,
                "population_fallback_passes": population_fallback_passes,
                "checks": checks,
            },
            indent=2,
        )
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", choices=("run", "finalize"), required=True)
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--expected-protocol-sha256", required=True)
    parser.add_argument("--model-path", type=Path, default=DEFAULT_MODEL_PATH)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    protocol, protocol_sha256 = verify_protocol(
        args.protocol, args.expected_protocol_sha256
    )
    c444.MODEL_CACHE_PATH = MODEL_CACHE_PATH
    c444.MODEL_RUNTIME_PATH = MODEL_RUNTIME_PATH
    if args.stage == "run":
        run(protocol=protocol, protocol_sha256=protocol_sha256, model_path=args.model_path)
    else:
        finalize(protocol, protocol_sha256)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
