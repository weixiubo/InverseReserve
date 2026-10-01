#!/usr/bin/env python3
"""Run full PACT on consumed MiniWoB development tasks with a frozen planner."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import re
import socket
import sqlite3
import subprocess
import sys
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT / "src", ROOT / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import c414_adaptive_semantic_risk_diagnostic as c414  # noqa: E402
import c416_qwen35_9b_capacity_diagnostic as c416  # noqa: E402
import c424_qwen_structured_planner_capacity as c424  # noqa: E402
from rcrps.pact_controller import (  # noqa: E402
    ActiveTransaction,
    admit_commit,
    exploration_is_nested,
    ground_commit,
)
from rcrps.structured_planner import (  # noqa: E402
    ActionCandidate,
    action_candidates,
    parse_planner_decision,
    planner_messages,
)
from rcrps.typed_observation import (  # noqa: E402
    check_postcondition,
    check_restoration,
    infer_preview_contract,
    semantic_snapshot,
)


DEFAULT_PROTOCOL = ROOT / "validation" / "c427_pact_live_development_protocol.json"
DEFAULT_MODEL_PATH = c424.DEFAULT_MODEL_PATH
RUN_DIRECTORY = ROOT / "runs" / "c427_pact_live_development"
EPISODE_DIRECTORY = RUN_DIRECTORY / "episodes"
MODEL_CACHE_PATH = RUN_DIRECTORY / "planner_cache.sqlite3"
OUTPUT_PATH = ROOT / "validation" / "c427_pact_live_development.json"
HTML_ROOT = ROOT / "external" / "miniwob-plusplus" / "miniwob" / "html"
EXPECTED_PLANNER_GATE_SHA256 = (
    "2120ba5079fa74c1c45a6766364a547e5bea1c810b9d58acdeb8f399945f2669"
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def object_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def atomic_write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def git_head() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()


class MiniwobServer:
    def __init__(self, html_root: Path) -> None:
        self.html_root = html_root
        self.process: subprocess.Popen[str] | None = None
        self.port: int | None = None

    def __enter__(self) -> str:
        with socket.socket() as handle:
            handle.bind(("127.0.0.1", 0))
            self.port = int(handle.getsockname()[1])
        self.process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "http.server",
                str(self.port),
                "--bind",
                "127.0.0.1",
                "--directory",
                str(self.html_root),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        deadline = time.monotonic() + 15.0
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                raise RuntimeError("MiniWoB source server exited during startup")
            with socket.socket() as probe:
                probe.settimeout(0.2)
                if probe.connect_ex(("127.0.0.1", self.port)) == 0:
                    return f"http://127.0.0.1:{self.port}/miniwob/"
            time.sleep(0.05)
        raise TimeoutError("MiniWoB source server did not become ready")

    def __exit__(self, *_args: Any) -> None:
        if self.process is None:
            return
        self.process.terminate()
        try:
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=5)


def verify_protocol(path: Path, expected_sha256: str) -> tuple[dict[str, Any], str]:
    actual = sha256(path)
    if actual != expected_sha256:
        raise ValueError(f"C427 protocol changed: {actual}")
    protocol = json.loads(path.read_text(encoding="utf-8"))
    if protocol.get("candidate") != "C427-PACT-live-development-protocol":
        raise ValueError("unexpected C427 protocol candidate")
    if sha256(ROOT / protocol["planner_gate"]["path"]) != EXPECTED_PLANNER_GATE_SHA256:
        raise ValueError("frozen C426 planner gate changed")
    for relative, expected in protocol["source_sha256"].items():
        if sha256(ROOT / relative) != expected:
            raise ValueError(f"C427 source changed: {relative}")
    return protocol, actual


def episode_manifest(protocol: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for task_index, task in enumerate(protocol["tasks"]):
        for seed in task["seeds"]:
            rows.append(
                {
                    "episode_index": len(rows),
                    "task_index": task_index,
                    "task": str(task["task_id"]),
                    "seed": int(seed),
                    "method": "full_pact",
                    "episode_id": f"{task['task_id']}__seed{int(seed)}__full_pact",
                }
            )
    return rows


def snapshot(observation: dict[str, Any]):
    return semantic_snapshot(
        observation["axtree_object"],
        observation["dom_object"],
        observation["extra_element_properties"],
    )


def action_code(operation: str, bid: str | None, observation: dict[str, Any]) -> str:
    if operation in {"click", "hover"}:
        if bid is None or not re.fullmatch(r"[A-Za-z0-9]+", bid):
            raise ValueError(f"unsafe BrowserGym bid: {bid!r}")
        return f"{operation}({bid!r})"
    if operation == "move_to_neutral_region":
        height, width = observation["screenshot"].shape[:2]
        return f"mouse_move({max(1, width - 5)}, {max(1, height - 5)})"
    raise ValueError(f"unsupported operation: {operation}")


def make_environment(task: str, base_url: str, protocol: dict[str, Any]):
    import gymnasium as gym
    import browsergym.miniwob  # noqa: F401
    from browsergym.core.action.highlevel import HighLevelActionSet

    browser = protocol["browser"]
    action_set = HighLevelActionSet(
        subsets=list(browser["action_subsets"]),
        multiaction=False,
        strict=True,
        demo_mode="off",
    )
    delay = (
        float(browser["menu_pre_observation_delay_seconds"])
        if task == "click-menu"
        else float(browser["pre_observation_delay_seconds"])
    )
    return gym.make(
        f"browsergym/miniwob.{task}",
        headless=True,
        action_mapping=action_set.to_python_code,
        pre_observation_delay=delay,
        task_kwargs={
            "base_url": base_url,
            "episode_max_time": int(browser["episode_max_time_milliseconds"]),
            "remove_human_display": True,
        },
    )


class FrozenPlanner:
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

        planner_gate = json.loads(
            (ROOT / protocol["planner_gate"]["path"]).read_text(encoding="utf-8")
        )
        runtime = planner_gate["runtime"]
        if torch.__version__ != runtime["torch"]:
            raise ValueError(f"Torch changed: {torch.__version__}")
        if transformers.__version__ != runtime["transformers"]:
            raise ValueError(f"Transformers changed: {transformers.__version__}")
        c415 = c416.verify_inputs(model_path)
        self.model_hashes = c415[-1]
        if self.model_hashes != planner_gate["model_file_sha256"]:
            raise ValueError("C427 model snapshot differs from C426")
        if torch.cuda.device_count() != 2:
            raise ValueError(f"C427 requires exactly two GPUs, got {torch.cuda.device_count()}")
        self.processor = AutoProcessor.from_pretrained(model_path)
        self.template_audit = c416.validate_nonthinking_template(self.processor)
        if self.template_audit != planner_gate["template_audit"]:
            raise ValueError("C427 nonthinking template differs from C426")
        self.model = AutoModelForMultimodalLM.from_pretrained(
            model_path,
            dtype=torch.bfloat16,
            device_map=str(runtime["device_map"]),
        )
        self.model.eval()
        self.protocol_sha256 = protocol_sha256
        self.connection = self._open_cache()
        self.cache_hits = 0
        self.actual_calls = 0

    def _open_cache(self) -> sqlite3.Connection:
        MODEL_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(MODEL_CACHE_PATH)
        connection.execute("PRAGMA journal_mode=DELETE")
        connection.execute("PRAGMA synchronous=FULL")
        connection.execute(
            "CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value_json TEXT NOT NULL)"
        )
        connection.execute(
            "CREATE TABLE IF NOT EXISTS entries ("
            "cache_key TEXT PRIMARY KEY, key_payload_json TEXT NOT NULL, "
            "raw_output TEXT NOT NULL, input_tokens INTEGER NOT NULL, "
            "generated_tokens INTEGER NOT NULL)"
        )
        expected = {
            "candidate": "C427-planner-cache",
            "protocol_sha256": self.protocol_sha256,
            "model_file_sha256": self.model_hashes,
            "template_audit": self.template_audit,
        }
        observed = {
            key: json.loads(value)
            for key, value in connection.execute("SELECT key, value_json FROM metadata")
        }
        if observed and observed != expected:
            connection.close()
            raise ValueError("incompatible C427 planner cache")
        if not observed:
            connection.executemany(
                "INSERT INTO metadata(key, value_json) VALUES (?, ?)",
                [(key, canonical_json(value)) for key, value in expected.items()],
            )
            connection.commit()
        return connection

    def close(self) -> None:
        self.connection.commit()
        self.connection.close()

    def decide(
        self,
        *,
        goal: str,
        candidates: tuple[ActionCandidate, ...],
        completed: list[dict[str, Any]],
        active: list[ActiveTransaction],
    ) -> tuple[Any, dict[str, Any]]:
        messages = planner_messages(
            goal=goal,
            candidates=candidates,
            completed_explorations=completed,
            active_transactions=(transaction.planner_record() for transaction in active),
        )
        key_payload = {"messages": messages}
        key = object_sha256(key_payload)
        cached = self.connection.execute(
            "SELECT key_payload_json, raw_output, input_tokens, generated_tokens "
            "FROM entries WHERE cache_key = ?",
            (key,),
        ).fetchone()
        if cached is None:
            row = c424.generate_one(
                model=self.model,
                processor=self.processor,
                case={"case_id": key, "messages": messages},
                device="cuda:0",
            )
            raw_output = str(row["raw_output"])
            input_tokens = int(row["input_tokens"])
            generated_tokens = int(row["generated_tokens"])
            self.connection.execute(
                "INSERT INTO entries(cache_key, key_payload_json, raw_output, "
                "input_tokens, generated_tokens) VALUES (?, ?, ?, ?, ?)",
                (
                    key,
                    canonical_json(key_payload),
                    raw_output,
                    input_tokens,
                    generated_tokens,
                ),
            )
            self.connection.commit()
            self.actual_calls += 1
            cache_hit = False
        else:
            payload_json, raw_output, input_tokens, generated_tokens = cached
            if json.loads(payload_json) != key_payload:
                raise ValueError("C427 planner cache key collision")
            self.cache_hits += 1
            cache_hit = True
        decision = parse_planner_decision(raw_output, candidates)
        return decision, {
            "cache_key": key,
            "cache_hit": cache_hit,
            "input_tokens": int(input_tokens),
            "generated_tokens": int(generated_tokens),
            "raw_output": raw_output,
        }


class EpisodeDriver:
    def __init__(
        self,
        *,
        environment: Any,
        observation: dict[str, Any],
        episode: dict[str, Any],
        protocol: dict[str, Any],
        planner: FrozenPlanner,
    ) -> None:
        self.environment = environment
        self.observation = observation
        self.episode = episode
        self.protocol = protocol
        self.planner = planner
        self.goal = str(observation["goal"])
        self.active: list[ActiveTransaction] = []
        self.completed: list[dict[str, Any]] = []
        self.trace: list[dict[str, Any]] = []
        self.done = False
        self.success = False
        self.terminated = False
        self.truncated = False
        self.gui_actions = 0
        self.planner_calls = 0
        self.preview_transactions = 0
        self.restoration_attempts = 0
        self.restoration_passes = 0
        self.terminal_previews = 0
        self.wrong_terminal_commits = 0
        self.parse_failures = 0
        self.started = time.monotonic()

    @property
    def budgets(self) -> dict[str, Any]:
        return self.protocol["budgets"]

    def audit(self, event: dict[str, Any]) -> None:
        self.trace.append({"event_index": len(self.trace), **event})

    def execute(self, code: str, role: str) -> dict[str, Any]:
        if self.gui_actions >= int(self.budgets["maximum_gui_actions"]):
            raise RuntimeError("GUI action budget exhausted")
        prior_error = str(self.observation.get("last_action_error", ""))
        observation, reward, terminated, truncated, info = self.environment.step(code)
        self.gui_actions += 1
        self.observation = observation
        self.terminated = bool(terminated)
        self.truncated = bool(truncated)
        self.done = self.terminated or self.truncated
        self.success = self.success or float(reward) > 0.0
        event = {
            "type": "action",
            "role": role,
            "action": code,
            "reward": float(reward),
            "terminated": self.terminated,
            "truncated": self.truncated,
            "last_action_error_before": prior_error,
            "last_action_error_after": str(observation.get("last_action_error", "")),
            "info_reason": str(info.get("message", info.get("reason", ""))),
        }
        self.audit(event)
        return event

    def rollback_top(self, reason: str) -> bool:
        if not self.active or self.done:
            return False
        transaction = self.active.pop()
        inverse = action_code(
            transaction.contract.inverse_operation,
            transaction.contract.inverse_bid,
            self.observation,
        )
        self.restoration_attempts += 1
        event = self.execute(inverse, "typed_inverse")
        if self.done:
            self.audit({"type": "restoration", "passed": False, "reason": "inverse terminated"})
            return False
        check = check_restoration(transaction.before, snapshot(self.observation))
        if check.passed:
            self.restoration_passes += 1
        self.completed.append(transaction.completed_record(target_found=False))
        self.audit(
            {
                "type": "restoration",
                "trigger": reason,
                "passed": check.passed,
                "check_reason": check.reason,
                "delta": asdict(check.delta),
                "inverse_action": event["action"],
            }
        )
        return check.passed

    def cleanup(self, reason: str) -> None:
        while self.active and not self.done and self.gui_actions < int(
            self.budgets["maximum_gui_actions"]
        ):
            if not self.rollback_top(reason):
                break

    def run(self) -> None:
        maximum_calls = int(self.budgets["maximum_planner_calls"])
        maximum_wall = float(self.budgets["maximum_wall_seconds"])
        while not self.done and self.planner_calls < maximum_calls:
            if time.monotonic() - self.started > maximum_wall:
                self.audit({"type": "abstain", "reason": "wall budget exhausted"})
                break
            current = snapshot(self.observation)
            candidates = action_candidates(current)
            try:
                decision, model_audit = self.planner.decide(
                    goal=self.goal,
                    candidates=candidates,
                    completed=self.completed,
                    active=self.active,
                )
            except Exception as error:
                self.parse_failures += 1
                self.audit(
                    {
                        "type": "planner_failure",
                        "error": f"{type(error).__name__}: {error}",
                    }
                )
                break
            self.planner_calls += 1
            self.audit(
                {
                    "type": "planner",
                    "decision": decision.decision,
                    "bid": decision.bid,
                    "candidate": asdict(decision.candidate) if decision.candidate else None,
                    "active_depth": len(self.active),
                    "completed_count": len(self.completed),
                    **model_audit,
                }
            )

            if decision.decision == "abstain":
                if self.active:
                    self.rollback_top("planner abstained in active transaction")
                    continue
                break

            assert decision.candidate is not None
            candidate = decision.candidate
            if decision.decision == "commit":
                grounding = ground_commit(self.goal, candidate)
                self.audit({"type": "commit_grounding", **asdict(grounding)})
                if not grounding.allowed:
                    if self.active:
                        self.rollback_top("commit label failed exact grounding")
                        continue
                    break
                admission = admit_commit(
                    goal=self.goal,
                    current=current,
                    candidate=candidate,
                    active_transactions=tuple(self.active),
                )
                self.audit({"type": "commit_admission", **asdict(admission)})
                if not admission.allowed:
                    if self.active:
                        self.rollback_top("commit outside transaction scope")
                        continue
                    break
                event = self.execute(
                    action_code(candidate.operation, candidate.bid, self.observation),
                    "commit",
                )
                if self.done and not self.success:
                    self.wrong_terminal_commits += 1
                if self.done:
                    break
                self.audit(
                    {
                        "type": "nonterminal_declared_commit",
                        "action": event["action"],
                    }
                )
                continue

            if self.preview_transactions >= int(
                self.budgets["maximum_preview_transactions"]
            ):
                self.audit({"type": "abstain", "reason": "preview budget exhausted"})
                break
            if len(self.active) >= int(self.budgets["maximum_transaction_depth"]):
                self.audit({"type": "abstain", "reason": "transaction depth exhausted"})
                break
            if self.active and not exploration_is_nested(current, candidate, self.active[-1]):
                self.rollback_top("switch to non-nested exploration")
                continue
            contract_decision = infer_preview_contract(current, candidate.bid)
            if not contract_decision.allowed or contract_decision.contract is None:
                self.audit(
                    {
                        "type": "abstain",
                        "reason": contract_decision.reason,
                        "bid": candidate.bid,
                    }
                )
                break
            contract = contract_decision.contract
            before = current
            event = self.execute(
                action_code(contract.operation, contract.action_bid, self.observation),
                "typed_preview",
            )
            self.preview_transactions += 1
            if self.done:
                self.terminal_previews += 1
                break
            after = snapshot(self.observation)
            postcondition = check_postcondition(before, after, contract)
            self.audit(
                {
                    "type": "postcondition",
                    "contract": asdict(contract),
                    "passed": postcondition.passed,
                    "reason": postcondition.reason,
                    "delta": asdict(postcondition.delta),
                    "preview_action": event["action"],
                }
            )
            if not postcondition.passed:
                temporary = ActiveTransaction(
                    contract=contract,
                    candidate_label=candidate.label,
                    before=before,
                    after=after,
                    delta=postcondition.delta,
                )
                self.active.append(temporary)
                self.rollback_top("postcondition failed")
                continue
            self.active.append(
                ActiveTransaction(
                    contract=contract,
                    candidate_label=candidate.label,
                    before=before,
                    after=after,
                    delta=postcondition.delta,
                )
            )
        if not self.done:
            self.cleanup("episode ended without commit")

    def result(self) -> dict[str, Any]:
        return {
            "candidate": "C427-episode",
            "created_utc": utc_now(),
            "episode": self.episode,
            "method_input": {
                "goal": self.goal,
                "method_received_evaluator_fields": False,
            },
            "complete": True,
            "success": self.success,
            "terminated": self.terminated,
            "truncated": self.truncated,
            "active_transactions_at_end": len(self.active),
            "completed_explorations": self.completed,
            "metrics": {
                "gui_actions": self.gui_actions,
                "planner_calls": self.planner_calls,
                "preview_transactions": self.preview_transactions,
                "restoration_attempts": self.restoration_attempts,
                "restoration_passes": self.restoration_passes,
                "terminal_previews": self.terminal_previews,
                "wrong_terminal_commits": self.wrong_terminal_commits,
                "planner_parse_failures": self.parse_failures,
                "wall_seconds": time.monotonic() - self.started,
            },
            "method_trace": self.trace,
        }


def run_episode(
    *,
    protocol: dict[str, Any],
    episode: dict[str, Any],
    base_url: str,
    planner: FrozenPlanner,
) -> dict[str, Any]:
    environment = make_environment(episode["task"], base_url, protocol)
    try:
        observation, _ = environment.reset(seed=episode["seed"])
        driver = EpisodeDriver(
            environment=environment,
            observation=observation,
            episode=episode,
            protocol=protocol,
            planner=planner,
        )
        try:
            driver.run()
        except Exception as error:
            driver.audit(
                {
                    "type": "driver_error",
                    "error": f"{type(error).__name__}: {error}",
                }
            )
            driver.cleanup("driver error")
        return driver.result()
    finally:
        environment.close()


def run(protocol: dict[str, Any], protocol_sha256: str, model_path: Path) -> None:
    manifest = episode_manifest(protocol)
    EPISODE_DIRECTORY.mkdir(parents=True, exist_ok=True)
    planner = FrozenPlanner(
        protocol=protocol,
        protocol_sha256=protocol_sha256,
        model_path=model_path,
    )
    try:
        with MiniwobServer(HTML_ROOT) as base_url:
            for index, episode in enumerate(manifest, start=1):
                path = EPISODE_DIRECTORY / f"{episode['episode_id']}.json"
                if path.is_file() and json.loads(path.read_text(encoding="utf-8")).get(
                    "complete"
                ):
                    continue
                result = run_episode(
                    protocol=protocol,
                    episode=episode,
                    base_url=base_url,
                    planner=planner,
                )
                atomic_write_json(path, result)
                print(
                    json.dumps(
                        {
                            "complete": index,
                            "total": len(manifest),
                            "episode_id": episode["episode_id"],
                            "success": result["success"],
                            "planner_actual_calls": planner.actual_calls,
                            "planner_cache_hits": planner.cache_hits,
                        }
                    ),
                    flush=True,
                )
    finally:
        planner.close()


def finalize(protocol: dict[str, Any], protocol_sha256: str) -> None:
    if OUTPUT_PATH.exists():
        raise FileExistsError(OUTPUT_PATH)
    rows = []
    for episode in episode_manifest(protocol):
        path = EPISODE_DIRECTORY / f"{episode['episode_id']}.json"
        if not path.is_file():
            raise FileNotFoundError(path)
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not payload.get("complete") or payload.get("episode") != episode:
            raise ValueError(f"incomplete or mismatched episode: {episode['episode_id']}")
        rows.append(payload)
    by_family = {}
    for task in [row["task_id"] for row in protocol["tasks"]]:
        subset = [row for row in rows if row["episode"]["task"] == task]
        by_family[task] = {
            "success": sum(row["success"] for row in subset),
            "episodes": len(subset),
            "success_rate": sum(row["success"] for row in subset) / len(subset),
        }
    metrics = {
        "success": sum(row["success"] for row in rows),
        "episodes": len(rows),
        "macro_success": sum(item["success_rate"] for item in by_family.values())
        / len(by_family),
        "minimum_family_success": min(
            item["success_rate"] for item in by_family.values()
        ),
        "terminal_previews": sum(
            row["metrics"]["terminal_previews"] for row in rows
        ),
        "wrong_terminal_commits": sum(
            row["metrics"]["wrong_terminal_commits"] for row in rows
        ),
        "restoration_attempts": sum(
            row["metrics"]["restoration_attempts"] for row in rows
        ),
        "restoration_passes": sum(
            row["metrics"]["restoration_passes"] for row in rows
        ),
        "planner_parse_failures": sum(
            row["metrics"]["planner_parse_failures"] for row in rows
        ),
        "by_family": by_family,
    }
    metrics["verified_restoration_rate"] = (
        metrics["restoration_passes"] / metrics["restoration_attempts"]
        if metrics["restoration_attempts"]
        else 1.0
    )
    gates = protocol["pass_gates"]
    checks = {
        "macro_success": metrics["macro_success"] >= gates["minimum_macro_success"],
        "minimum_family_success": metrics["minimum_family_success"]
        >= gates["minimum_each_family_success"],
        "zero_terminal_previews": metrics["terminal_previews"] == 0,
        "zero_wrong_terminal_commits": metrics["wrong_terminal_commits"] == 0,
        "restoration_rate": metrics["verified_restoration_rate"]
        >= gates["minimum_verified_restoration_rate"],
        "zero_planner_parse_failures": metrics["planner_parse_failures"] == 0,
    }
    output = {
        "candidate": "C427-PACT-live-development",
        "created_utc": utc_now(),
        "git_head": git_head(),
        "protocol": str(DEFAULT_PROTOCOL.relative_to(ROOT)),
        "protocol_sha256": protocol_sha256,
        "status": "development_only_consumed_tasks",
        "episode_rows": rows,
        "metrics": metrics,
        "checks": checks,
        "passed": all(checks.values()),
        "next_step": (
            protocol["decision_rule"]["on_pass"]
            if all(checks.values())
            else protocol["decision_rule"]["on_failure"]
        ),
    }
    atomic_write_json(OUTPUT_PATH, output)
    print(json.dumps({"passed": output["passed"], "metrics": metrics, "checks": checks}, indent=2))


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
        run(protocol, protocol_sha256, args.model_path)
    else:
        finalize(protocol, protocol_sha256)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
