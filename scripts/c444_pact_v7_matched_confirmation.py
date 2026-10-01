#!/usr/bin/env python3
"""Run and finalize the frozen C443 matched fresh-seed confirmation."""

from __future__ import annotations

import argparse
import json
import platform
import sqlite3
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT / "src", ROOT / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import c414_adaptive_semantic_risk_diagnostic as c414  # noqa: E402
import c416_qwen35_9b_capacity_diagnostic as c416  # noqa: E402
import c427_pact_live_development as c427  # noqa: E402
import c433_fresh_observation_preflight as c433  # noqa: E402
import c434_pact_v4_live_development_gate as c434  # noqa: E402
import c438_qwen_pact_v6_planner_capacity as c438  # noqa: E402
from rcrps.confirmation_agents_v7 import CONFIRMATION_DRIVERS_V7  # noqa: E402
from rcrps.confirmation_statistics_v7 import confirmation_comparisons  # noqa: E402
from rcrps.pact_statistics import restoration_summary, wilson_interval  # noqa: E402


DEFAULT_PROTOCOL = ROOT / "validation" / "c443_pact_v7_matched_confirmation_protocol.json"
OUTPUT_PATH = ROOT / "validation" / "c444_pact_v7_matched_confirmation.json"
RUN_DIRECTORY = ROOT / "runs" / "c444_pact_v7_matched_confirmation"
EPISODE_DIRECTORY = RUN_DIRECTORY / "episodes"
CLAIM_DIRECTORY = RUN_DIRECTORY / "claims"
MODEL_CACHE_PATH = RUN_DIRECTORY / "planner_cache.sqlite3"
MODEL_RUNTIME_PATH = RUN_DIRECTORY / "model_runtime.json"
C442_PARENT = ROOT / "validation" / "c442_pact_v7_live_integration_gate.json"
EXPECTED_C442_PARENT_SHA256 = (
    "ac5c6d55fe838e89eb4a307a3eaea1c1db9355ccce1e365236ef6de27c15f565"
)
C441_PARENT = ROOT / "validation" / "c441_qwen_action_envelope_capacity.json"
EXPECTED_C441_PARENT_SHA256 = (
    "cc9a415f69134ff9033e904190cd0e3924bcc64ad45f08df3f5c1b1b47e3e724"
)
C443_SMOKE = ROOT / "validation" / "c443_consumed_confirmation_runner_smoke.json"
EXPECTED_C443_SMOKE_SHA256 = (
    "644d1f6a92b18ac69142873c7575a34543ed0861830e19dfa684b920234694b3"
)
EXPECTED_C433_PROTOCOL_SHA256 = (
    "70f7cd945975bd53a88c481236fc716333f0d68441c51798fd58e78552ce1c78"
)
EXPECTED_REPOSITORIES = {
    "browsergym": "0a785fbed075224ae81ca9c1fe924f66050696fe",
    "miniwob_plusplus": "7fd85d71a4b60325c6585396ec4f48377d049838",
}
REPOSITORY_PATHS = {
    "browsergym": ROOT / "external" / "BrowserGym",
    "miniwob_plusplus": ROOT / "external" / "miniwob-plusplus",
}
DEFAULT_MODEL_PATH = Path(str(Path.home() / ".cache" / "inversereserve" / "Qwen3.5-9B"))
ARMS = ("raw_open_loop", "typed_no_certificate", "full_pact_v7")
FULL_METHOD = "full_pact_v7"
BASELINES = ("raw_open_loop", "typed_no_certificate")
MAX_NEW_TOKENS = 64


def sha256(path: Path) -> str:
    return c414.sha256(path)


def git_head() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()


def canonical_json(value: object) -> str:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )


def object_sha256(value: object) -> str:
    return c414.text_sha256(canonical_json(value))


def verify_clean_repository(path: Path, expected_head: str) -> dict[str, str]:
    if not path.is_dir():
        raise FileNotFoundError(f"frozen repository is absent: {path}")
    root = Path(
        subprocess.check_output(
            ["git", "-C", str(path), "rev-parse", "--show-toplevel"], text=True
        ).strip()
    ).resolve()
    if root != path.resolve():
        raise ValueError(f"unexpected repository root for {path}: {root}")
    head = subprocess.check_output(
        ["git", "-C", str(path), "rev-parse", "HEAD"], text=True
    ).strip()
    if head != expected_head:
        raise ValueError(f"frozen repository head changed: {path}: {head}")
    status = subprocess.check_output(
        ["git", "-C", str(path), "status", "--porcelain", "--untracked-files=all"],
        text=True,
    )
    if status:
        raise ValueError(f"frozen repository is dirty: {path}")
    try:
        label = str(path.resolve().relative_to(ROOT.resolve()))
    except ValueError:
        label = str(path.resolve())
    return {"path": label, "head": head, "status": "clean"}


def verify_protocol(path: Path, expected_sha256: str) -> tuple[dict[str, Any], str]:
    actual = sha256(path)
    if actual != expected_sha256:
        raise ValueError(f"C443 protocol changed: {actual}")
    protocol = c414.load_json(path)
    if protocol.get("candidate") != "C443-PACT-v7-matched-confirmation-protocol":
        raise ValueError("unexpected C443 protocol candidate")
    if tuple(protocol["arms"]) != ARMS:
        raise ValueError("C443 arm order changed")
    if sha256(C442_PARENT) != EXPECTED_C442_PARENT_SHA256 or c414.load_json(
        C442_PARENT
    ).get("passed") is not True:
        raise ValueError("C442 live parent changed")
    if sha256(C441_PARENT) != EXPECTED_C441_PARENT_SHA256 or c414.load_json(
        C441_PARENT
    ).get("passed") is not True:
        raise ValueError("C441 model parent changed")
    if sha256(C443_SMOKE) != EXPECTED_C443_SMOKE_SHA256 or c414.load_json(
        C443_SMOKE
    ).get("passed") is not True:
        raise ValueError("C443 consumed runner smoke changed")
    if protocol["activation"] != {
        "live_integration_parent": str(C442_PARENT.relative_to(ROOT)),
        "live_integration_parent_sha256": EXPECTED_C442_PARENT_SHA256,
        "live_integration_parent_passed": True,
        "model_capacity_parent": str(C441_PARENT.relative_to(ROOT)),
        "model_capacity_parent_sha256": EXPECTED_C441_PARENT_SHA256,
        "model_capacity_parent_passed": True,
        "consumed_runner_smoke": str(C443_SMOKE.relative_to(ROOT)),
        "consumed_runner_smoke_sha256": EXPECTED_C443_SMOKE_SHA256,
        "consumed_runner_smoke_passed": True,
    }:
        raise ValueError("unexpected C443 activation binding")
    expected_seeds = list(range(27301, 27321))
    if protocol["confirmation_seeds"] != expected_seeds:
        raise ValueError("C443 confirmation seed grid changed")
    if sha256(c434.C433_PROTOCOL) != EXPECTED_C433_PROTOCOL_SHA256:
        raise ValueError("C433 seed-partition protocol changed")
    c433_protocol = c414.load_json(c434.C433_PROTOCOL)
    if c433_protocol["seed_partitions"]["confirmation_embargoed"] != expected_seeds:
        raise ValueError("C443 seeds differ from the C433 embargoed partition")
    if protocol["repositories"] != EXPECTED_REPOSITORIES:
        raise ValueError("C443 repository pins changed")
    for name, expected_head in EXPECTED_REPOSITORIES.items():
        verify_clean_repository(REPOSITORY_PATHS[name], expected_head)
    if protocol["expected_task_seed_cells"] != 120:
        raise ValueError("C443 expected paired cells changed")
    if protocol["expected_episodes"] != 360:
        raise ValueError("C443 expected episode grid changed")
    if protocol["generation"] != {
        "enable_thinking": False,
        "do_sample": False,
        "max_new_tokens": MAX_NEW_TOKENS,
    }:
        raise ValueError("C443 generation settings changed")
    if protocol["information_boundary"]["confirmation_partition_opened"] is not False:
        raise ValueError("C443 must be frozen before confirmation opens")
    note = protocol["preregistration"]
    if sha256(ROOT / note["path"]) != note["sha256"]:
        raise ValueError("C443 preregistration changed")
    for relative, expected in protocol["source_sha256"].items():
        observed = sha256(ROOT / relative)
        if observed != expected:
            raise ValueError(f"C443 source changed: {relative}: {observed}")
    return protocol, actual


def episode_manifest(protocol: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    tasks = protocol["tasks"]
    for seed_index, seed in enumerate(protocol["confirmation_seeds"]):
        for task_index, task in enumerate(tasks):
            rotation = (seed_index + task_index) % len(ARMS)
            order = ARMS[rotation:] + ARMS[:rotation]
            for arm_position, method in enumerate(order):
                task_id = str(task["task_id"])
                rows.append(
                    {
                        "episode_index": len(rows),
                        "task_index": task_index,
                        "seed_index": seed_index,
                        "arm_position": arm_position,
                        "task": task_id,
                        "family_group": str(task["family_group"]),
                        "seed": int(seed),
                        "method": method,
                        "episode_id": f"{task_id}__seed{int(seed)}__{method}",
                    }
                )
    if len(rows) != int(protocol["expected_episodes"]):
        raise ValueError("C443 episode manifest count changed")
    return rows


class FrozenModelServiceV7:
    def __init__(
        self,
        *,
        protocol: dict[str, Any],
        protocol_sha256: str,
        model_path: Path,
    ) -> None:
        import torch
        import transformers
        from transformers import AutoModelForMultimodalLM, AutoProcessor

        verified = c416.verify_inputs(model_path)
        c415 = verified[0]
        self.model_hashes = verified[-1]
        runtime = c415["runtime"]
        if torch.__version__ != runtime["torch"]:
            raise ValueError("C444 torch runtime changed")
        if transformers.__version__ != runtime["transformers"]:
            raise ValueError("C444 transformers runtime changed")
        if torch.cuda.device_count() != 2:
            raise ValueError(f"C444 requires two visible GPUs, got {torch.cuda.device_count()}")
        self.processor = AutoProcessor.from_pretrained(model_path)
        self.template_audit = c416.validate_nonthinking_template(self.processor)
        self.model = AutoModelForMultimodalLM.from_pretrained(
            model_path,
            dtype=torch.bfloat16,
            device_map=str(runtime["device_map"]),
        )
        self.model.eval()
        self.protocol_sha256 = protocol_sha256
        self.actual_calls = 0
        self.cache_hits = 0
        MODEL_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(MODEL_CACHE_PATH)
        self.connection.execute(
            "CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value_json TEXT NOT NULL)"
        )
        self.connection.execute(
            "CREATE TABLE IF NOT EXISTS entries ("
            "cache_key TEXT PRIMARY KEY, messages_json TEXT NOT NULL, "
            "raw_output TEXT NOT NULL, input_tokens INTEGER NOT NULL, "
            "generated_tokens INTEGER NOT NULL)"
        )
        expected_metadata = {
            "candidate": "C444-planner-cache",
            "protocol_sha256": protocol_sha256,
            "model_file_sha256": self.model_hashes,
            "template_audit": self.template_audit,
            "generation": protocol["generation"],
        }
        observed = {
            key: json.loads(value)
            for key, value in self.connection.execute(
                "SELECT key, value_json FROM metadata"
            )
        }
        if observed and observed != expected_metadata:
            raise ValueError("incompatible C444 planner cache")
        if not observed:
            self.connection.executemany(
                "INSERT INTO metadata(key, value_json) VALUES (?, ?)",
                [(key, canonical_json(value)) for key, value in expected_metadata.items()],
            )
            self.connection.commit()
        runtime_record = {
            "candidate": "C444-model-runtime",
            "created_utc": c427.utc_now(),
            "git_head": git_head(),
            "protocol_sha256": protocol_sha256,
            "model_file_sha256": self.model_hashes,
            "generation": protocol["generation"],
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
                "template_audit": self.template_audit,
            },
        }
        if MODEL_RUNTIME_PATH.exists():
            existing = c414.load_json(MODEL_RUNTIME_PATH)
            for key in ("protocol_sha256", "model_file_sha256", "generation"):
                if existing.get(key) != runtime_record[key]:
                    raise ValueError(f"C444 model runtime changed: {key}")
        else:
            c414.atomic_write_json(MODEL_RUNTIME_PATH, runtime_record)

    def generate(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        messages_json = canonical_json(messages)
        key = c414.text_sha256(messages_json)
        cached = self.connection.execute(
            "SELECT messages_json, raw_output, input_tokens, generated_tokens "
            "FROM entries WHERE cache_key = ?",
            (key,),
        ).fetchone()
        if cached is not None:
            stored_messages, raw_output, input_tokens, generated_tokens = cached
            if stored_messages != messages_json:
                raise ValueError("C444 planner cache key collision")
            self.cache_hits += 1
            return {
                "cache_key": key,
                "cache_hit": True,
                "raw_output": raw_output,
                "input_tokens": int(input_tokens),
                "generated_tokens": int(generated_tokens),
            }
        row = c438.generate_one(
            model=self.model,
            processor=self.processor,
            case={"case_id": key, "messages": messages},
            device="cuda:0",
        )
        self.connection.execute(
            "INSERT INTO entries(cache_key, messages_json, raw_output, input_tokens, "
            "generated_tokens) VALUES (?, ?, ?, ?, ?)",
            (
                key,
                messages_json,
                row["raw_output"],
                int(row["input_tokens"]),
                int(row["generated_tokens"]),
            ),
        )
        self.connection.commit()
        self.actual_calls += 1
        return {
            "cache_key": key,
            "cache_hit": False,
            "raw_output": row["raw_output"],
            "input_tokens": int(row["input_tokens"]),
            "generated_tokens": int(row["generated_tokens"]),
        }

    def close(self) -> None:
        self.connection.commit()
        self.connection.close()


def _claim_path(episode: dict[str, Any]) -> Path:
    return CLAIM_DIRECTORY / f"{episode['episode_id']}.json"


def _episode_path(episode: dict[str, Any]) -> Path:
    return EPISODE_DIRECTORY / f"{episode['episode_id']}.json"


def completed_episode(episode: dict[str, Any], protocol_sha256: str) -> bool:
    claim_path = _claim_path(episode)
    episode_path = _episode_path(episode)
    if not claim_path.exists() and not episode_path.exists():
        return False
    if not claim_path.is_file() or not episode_path.is_file():
        raise RuntimeError(f"C444 episode has an unmatched claim/result: {episode['episode_id']}")
    claim = c414.load_json(claim_path)
    result = c414.load_json(episode_path)
    if (
        claim.get("status") != "complete"
        or claim.get("episode") != episode
        or claim.get("protocol_sha256") != protocol_sha256
        or claim.get("episode_sha256") != sha256(episode_path)
        or result.get("complete") is not True
        or result.get("episode") != episode
        or result.get("protocol_sha256") != protocol_sha256
    ):
        raise RuntimeError(f"incompatible frozen C444 episode: {episode['episode_id']}")
    return True


def write_claim(episode: dict[str, Any], protocol_sha256: str) -> None:
    path = _claim_path(episode)
    if path.exists() or _episode_path(episode).exists():
        raise FileExistsError(f"C444 episode was already opened: {episode['episode_id']}")
    c414.atomic_write_json(
        path,
        {
            "candidate": "C444-confirmation-open-claim",
            "created_utc": c427.utc_now(),
            "status": "claimed_before_reset",
            "protocol_sha256": protocol_sha256,
            "episode": episode,
        },
    )


def complete_claim(
    episode: dict[str, Any], protocol_sha256: str, episode_path: Path
) -> None:
    c414.atomic_write_json(
        _claim_path(episode),
        {
            "candidate": "C444-confirmation-open-claim",
            "completed_utc": c427.utc_now(),
            "status": "complete",
            "protocol_sha256": protocol_sha256,
            "episode": episode,
            "episode_sha256": sha256(episode_path),
        },
    )


def infrastructure_reset_failure(
    episode: dict[str, Any], protocol_sha256: str, error: Exception
) -> dict[str, Any]:
    return {
        "candidate": "C444-matched-confirmation-episode",
        "protocol_sha256": protocol_sha256,
        "episode": episode,
        "complete": True,
        "success": False,
        "terminated": False,
        "truncated": False,
        "method_failure": None,
        "infrastructure_failure": True,
        "infrastructure_error": f"reset failed: {type(error).__name__}: {error}",
        "method_input": {
            "goal": None,
            "goal_sha256": None,
            "controller_arm": episode["method"],
            "method_received_task_id": False,
            "method_received_seed": False,
            "method_received_reward": False,
            "method_received_evaluator_fields": False,
        },
        "evaluation_audit": {
            "reward_observed_by_harness": False,
            "evaluator_info_observed_by_harness": False,
            "reward_or_info_forwarded_to_method": False,
            "confirmation_episode": True,
        },
        "trace": [],
        "actions": [],
        "restorations": [],
        "runtime_events": [],
        "metrics": {
            "gui_actions": 0,
            "planner_calls": 0,
            "planner_actual_calls": 0,
            "planner_cache_hits": 0,
            "planner_parse_failures": 0,
            "typed_transactions": 0,
            "certified_commits": 0,
            "uncertified_commits": 0,
            "restoration_attempts": 0,
            "restoration_passes": 0,
            "wrong_terminal_commits": 0,
            "terminal_transactions": 0,
            "action_errors": 0,
            "runtime_halted": False,
            "runtime_halt_reason": None,
            "wall_seconds": 0.0,
        },
    }


def run(
    *, protocol: dict[str, Any], protocol_sha256: str, model_path: Path
) -> None:
    manifest = episode_manifest(protocol)
    EPISODE_DIRECTORY.mkdir(parents=True, exist_ok=True)
    CLAIM_DIRECTORY.mkdir(parents=True, exist_ok=True)
    pending = [
        episode
        for episode in manifest
        if not completed_episode(episode, protocol_sha256)
    ]
    if not pending:
        print("C444 confirmation grid already complete", flush=True)
        return
    service = FrozenModelServiceV7(
        protocol=protocol,
        protocol_sha256=protocol_sha256,
        model_path=model_path,
    )
    parent_protocol = c414.load_json(c434.C433_PROTOCOL)
    try:
        with c427.MiniwobServer(c433.HTML_ROOT) as base_url:
            for episode in pending:
                write_claim(episode, protocol_sha256)
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
                        result = infrastructure_reset_failure(
                            episode, protocol_sha256, error
                        )
                    else:
                        driver_class = CONFIRMATION_DRIVERS_V7[episode["method"]]
                        driver = driver_class(
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
                episode_path = _episode_path(episode)
                c414.atomic_write_json(episode_path, result)
                complete_claim(episode, protocol_sha256, episode_path)
                print(
                    json.dumps(
                        {
                            "complete": episode["episode_index"] + 1,
                            "total": len(manifest),
                            "episode_id": episode["episode_id"],
                        }
                    ),
                    flush=True,
                )
                if result["infrastructure_failure"]:
                    raise RuntimeError(
                        "C444 stopped after sealing an infrastructure failure"
                    )
    finally:
        service.close()


def aggregate_arm(rows: list[dict[str, Any]], protocol: dict[str, Any]) -> dict[str, Any]:
    by_family = {}
    for task in protocol["tasks"]:
        task_id = task["task_id"]
        subset = [row for row in rows if row["episode"]["task"] == task_id]
        successes = sum(bool(row["success"]) for row in subset)
        interval = wilson_interval(successes, len(subset))
        by_family[task_id] = {
            "success": successes,
            "episodes": len(subset),
            "success_rate": successes / len(subset),
            "wilson_95_percent_interval": list(interval),
        }
    metric_names = (
        "gui_actions",
        "planner_calls",
        "planner_actual_calls",
        "planner_cache_hits",
        "planner_parse_failures",
        "typed_transactions",
        "certified_commits",
        "uncertified_commits",
        "restoration_attempts",
        "restoration_passes",
        "wrong_terminal_commits",
        "terminal_transactions",
        "action_errors",
    )
    success = sum(bool(row["success"]) for row in rows)
    postconditions = [
        event
        for row in rows
        for event in row.get("runtime_events", [])
        if event.get("type") == "postcondition"
    ]
    output = {
        "success": success,
        "episodes": len(rows),
        "success_rate": success / len(rows),
        "success_wilson_95_percent_interval": list(
            wilson_interval(success, len(rows))
        ),
        "macro_success": sum(item["success_rate"] for item in by_family.values())
        / len(by_family),
        "minimum_family_success": min(
            item["success_rate"] for item in by_family.values()
        ),
        "by_family": by_family,
        **{
            name: sum(int(row["metrics"][name]) for row in rows)
            for name in metric_names
        },
        "postcondition_passes": sum(event.get("passed") is True for event in postconditions),
        "postcondition_failures": sum(event.get("passed") is False for event in postconditions),
        "runtime_halts": sum(bool(row["metrics"]["runtime_halted"]) for row in rows),
        "method_failures": sum(row["method_failure"] is not None for row in rows),
        "infrastructure_failures": sum(row["infrastructure_failure"] for row in rows),
        "wall_seconds": sum(float(row["metrics"]["wall_seconds"]) for row in rows),
    }
    output["restoration"] = restoration_summary(
        [
            {
                "restoration_attempts": row["metrics"]["restoration_attempts"],
                "restoration_passes": row["metrics"]["restoration_passes"],
            }
            for row in rows
        ]
    )
    return output


def compact_episode(row: dict[str, Any], path: Path) -> dict[str, Any]:
    return {
        "episode": row["episode"],
        "artifact_sha256": sha256(path),
        "success": row["success"],
        "terminated": row["terminated"],
        "truncated": row["truncated"],
        "method_failure": row["method_failure"],
        "infrastructure_failure": row["infrastructure_failure"],
        "goal_sha256": row["method_input"]["goal_sha256"],
        "trace_sha256": object_sha256(row.get("trace", [])),
        "actions_sha256": object_sha256(row.get("actions", [])),
        "metrics": row["metrics"],
    }


def finalize(protocol: dict[str, Any], protocol_sha256: str) -> None:
    if OUTPUT_PATH.exists():
        raise FileExistsError(OUTPUT_PATH)
    if not MODEL_RUNTIME_PATH.is_file() or not MODEL_CACHE_PATH.is_file():
        raise FileNotFoundError("C444 model runtime or planner cache is absent")
    manifest = episode_manifest(protocol)
    rows = []
    compact = []
    for episode in manifest:
        if not completed_episode(episode, protocol_sha256):
            raise RuntimeError(f"incomplete C444 confirmation episode: {episode['episode_id']}")
        path = _episode_path(episode)
        row = c414.load_json(path)
        rows.append(row)
        compact.append(compact_episode(row, path))

    arm_rows = {
        arm: [row for row in rows if row["episode"]["method"] == arm]
        for arm in ARMS
    }
    metrics = {arm: aggregate_arm(arm_rows[arm], protocol) for arm in ARMS}
    paired_input = [
        {
            "method": row["episode"]["method"],
            "task": row["episode"]["task"],
            "seed": row["episode"]["seed"],
            "success": bool(row["success"]),
            "infrastructure_failure": bool(row["infrastructure_failure"]),
        }
        for row in rows
    ]
    statistics = confirmation_comparisons(
        paired_input,
        full_method=FULL_METHOD,
        baselines=BASELINES,
        bootstrap_samples=int(protocol["statistics"]["bootstrap_samples"]),
        bootstrap_seed=int(protocol["statistics"]["bootstrap_seed"]),
        alpha=float(protocol["statistics"]["familywise_alpha"]),
    )
    primary = statistics["comparisons"]["raw_open_loop"]
    secondary = statistics["comparisons"]["typed_no_certificate"]
    full = metrics[FULL_METHOD]
    gates = protocol["confirmation_gates"]
    goal_hashes_by_cell: dict[tuple[str, int], set[str]] = {}
    for row in rows:
        key = (row["episode"]["task"], int(row["episode"]["seed"]))
        goal_hashes_by_cell.setdefault(key, set()).add(
            str(row["method_input"]["goal_sha256"])
        )
    full_rows = arm_rows[FULL_METHOD]
    checks = {
        "complete_matched_grid": len(rows) == protocol["expected_episodes"]
        and all(len(arm_rows[arm]) == 120 for arm in ARMS),
        "all_claims_complete_and_single_open": all(
            c414.load_json(_claim_path(episode)).get("status") == "complete"
            for episode in manifest
        ),
        "zero_infrastructure_failures": all(
            not row["infrastructure_failure"] for row in rows
        ),
        "zero_forbidden_method_inputs": all(
            row["method_input"]["method_received_task_id"] is False
            and row["method_input"]["method_received_seed"] is False
            and row["method_input"]["method_received_reward"] is False
            and row["method_input"]["method_received_evaluator_fields"] is False
            and row["evaluation_audit"]["reward_or_info_forwarded_to_method"] is False
            for row in rows
        ),
        "no_action_after_reward_or_terminal_stop": all(
            not any(
                float(action["reward"]) > 0.0
                or bool(action["terminated"])
                or bool(action["truncated"])
                for action in row["actions"][:-1]
            )
            for row in rows
        ),
        "matched_goal_hashes_across_arms": all(
            len(values) == 1 for values in goal_hashes_by_cell.values()
        )
        and len(goal_hashes_by_cell) == protocol["expected_task_seed_cells"],
        "all_episode_budgets_respected": all(
            row["metrics"]["gui_actions"]
            <= protocol["budgets"]["maximum_gui_actions"]
            and row["metrics"]["planner_calls"]
            <= protocol["budgets"]["maximum_planner_calls"]
            and row["metrics"]["wall_seconds"]
            <= protocol["budgets"]["maximum_wall_seconds"]
            for row in rows
        ),
        "full_minimum_macro_success": full["macro_success"]
        >= gates["full_minimum_macro_success"],
        "full_minimum_each_family_success": full["minimum_family_success"]
        >= gates["full_minimum_each_family_success"],
        "full_zero_parse_failures": full["planner_parse_failures"] == 0,
        "full_zero_wrong_terminal_commits": full["wrong_terminal_commits"] == 0,
        "full_zero_terminal_transactions": full["terminal_transactions"] == 0,
        "full_zero_action_errors": full["action_errors"] == 0,
        "full_zero_runtime_halts": full["runtime_halts"] == 0,
        "full_zero_postcondition_failures": full["postcondition_failures"] == 0,
        "full_zero_method_failures": full["method_failures"] == 0,
        "full_zero_uncertified_commits": full["uncertified_commits"] == 0,
        "full_model_only_for_multirow_envelopes": all(
            (event.get("model") is not None)
            == (len(event["envelope"]["candidates"]) > 1)
            for row in full_rows
            for event in row["trace"]
            if event.get("type") == "envelope_decision"
            and event["envelope"]["decision"] != "abstain"
        ),
        "full_all_attempted_restorations_pass": full["restoration_passes"]
        == full["restoration_attempts"],
        "primary_minimum_effect": primary[
            "observed_task_weighted_success_difference"
        ]
        >= gates["primary_full_minus_raw_minimum"],
        "primary_positive_cluster_bootstrap_lower": primary[
            "bootstrap_95_percent_ci"
        ][0]
        > 0.0,
        "primary_holm_rejects": primary["holm"]["rejected"] is True,
        "safety_compilation_ablation_minimum_effect": secondary[
            "observed_task_weighted_success_difference"
        ]
        >= gates["secondary_full_minus_no_certificate_minimum"],
        "safety_compilation_ablation_positive_cluster_bootstrap_lower": secondary[
            "bootstrap_95_percent_ci"
        ][0]
        > 0.0,
        "safety_compilation_ablation_holm_rejects": secondary["holm"]["rejected"]
        is True,
    }
    passed = all(checks.values())
    claim_manifest = {
        episode["episode_id"]: sha256(_claim_path(episode)) for episode in manifest
    }
    payload = {
        "candidate": "C444-PACT-v7-matched-fresh-seed-confirmation",
        "created_utc": c427.utc_now(),
        "git_head": git_head(),
        "status": "fresh_confirmation_complete",
        "protocol": str(DEFAULT_PROTOCOL.relative_to(ROOT)),
        "protocol_sha256": protocol_sha256,
        "activation": protocol["activation"],
        "confirmation_partition_opened": True,
        "confirmation_open_policy": "each (task, seed, arm) episode claimed before its sole reset",
        "model_runtime": str(MODEL_RUNTIME_PATH.relative_to(ROOT)),
        "model_runtime_sha256": sha256(MODEL_RUNTIME_PATH),
        "planner_cache": str(MODEL_CACHE_PATH.relative_to(ROOT)),
        "planner_cache_sha256": sha256(MODEL_CACHE_PATH),
        "claim_manifest_sha256": object_sha256(claim_manifest),
        "claim_manifest": claim_manifest,
        "information_boundary": {
            **protocol["information_boundary"],
            "confirmation_partition_opened": True,
            "reward_and_evaluator_observed_by_harness_only": True,
        },
        "episode_rows": compact,
        "metrics": metrics,
        "statistics": statistics,
        "checks": checks,
        "passed": passed,
        "next_step": protocol["decision_rule"]["on_pass" if passed else "on_failure"],
    }
    c414.atomic_write_json(OUTPUT_PATH, payload)
    print(
        json.dumps(
            {
                "passed": passed,
                "metrics": metrics,
                "statistics": statistics,
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
    if args.stage == "run":
        run(
            protocol=protocol,
            protocol_sha256=protocol_sha256,
            model_path=args.model_path,
        )
    else:
        finalize(protocol, protocol_sha256)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
