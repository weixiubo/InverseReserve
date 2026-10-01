"""Shared create-once execution mechanics for frozen MiniWob successors."""

from __future__ import annotations

import fcntl
import json
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any, Iterator

import c414_adaptive_semantic_risk_diagnostic as c414
import c427_pact_live_development as c427
import c433_fresh_observation_preflight as c433
import c434_pact_v4_live_development_gate as c434
import c444_pact_v7_matched_confirmation as c444
import inversereserve_single_gpu_runtime as single_gpu
from pact_v10_runner_common import OneOpenEpisodeStore


@dataclass(frozen=True)
class FrozenSuccessorRuntime:
    """Execute one immutable manifest and preserve every opened episode."""

    root: Path
    design: ModuleType
    run_root: Path
    result_path: Path
    episode_directory: Path
    claim_directory: Path
    model_cache_path: Path
    model_runtime_path: Path
    lock_path: Path
    store: OneOpenEpisodeStore

    @contextmanager
    def single_instance_lock(self) -> Iterator[None]:
        self.run_root.mkdir(parents=True, exist_ok=True)
        with self.lock_path.open("a+", encoding="utf-8") as stream:
            try:
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as error:
                raise RuntimeError("another successor process holds the lock") from error
            yield

    def run(
        self,
        protocol: dict[str, Any],
        protocol_sha256: str,
        model_path: Path,
    ) -> None:
        manifest = self.design.episode_manifest(protocol)
        pending = [
            episode
            for episode in manifest
            if not self.store.completed(episode, protocol_sha256)
        ]
        if not pending:
            print(f"{self.design.CANDIDATE} already complete", flush=True)
            return
        service = single_gpu.SingleGpuFrozenModelService(
            protocol=protocol,
            protocol_sha256=protocol_sha256,
            model_path=model_path,
            model_cache_path=self.model_cache_path,
            model_runtime_path=self.model_runtime_path,
        )
        environment_protocol = c414.load_json(c434.C433_PROTOCOL)
        self.episode_directory.mkdir(parents=True, exist_ok=True)
        self.claim_directory.mkdir(parents=True, exist_ok=True)
        try:
            with c427.MiniwobServer(c433.HTML_ROOT) as base_url:
                for episode in pending:
                    self.store.open(episode, protocol_sha256)
                    environment = None
                    try:
                        try:
                            environment = c427.make_environment(
                                episode["task"], base_url, environment_protocol
                            )
                            observation, _discarded_reset_info = environment.reset(
                                seed=episode["seed"]
                            )
                        except Exception as error:
                            result = c444.infrastructure_reset_failure(
                                episode, protocol_sha256, error
                            )
                        else:
                            budgets = {
                                **protocol["common_budgets"],
                                "maximum_gui_actions": episode[
                                    "maximum_gui_actions"
                                ],
                            }
                            driver = self.design.DRIVERS[episode["method"]](
                                environment=environment,
                                observation=observation,
                                budgets=budgets,
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
                        result["candidate"] = f"{self.design.CANDIDATE}-episode"
                    finally:
                        if environment is not None:
                            environment.close()
                    path = self.store.episode_path(episode)
                    c414.atomic_write_json(path, result)
                    self.store.complete(episode, protocol_sha256, path)
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
                            "successor stopped after sealing an infrastructure failure"
                        )
        finally:
            service.close()

    def load_completed(
        self, protocol: dict[str, Any], protocol_sha256: str
    ) -> tuple[list[dict[str, Any]], dict[str, str], dict[str, str]]:
        if not self.model_runtime_path.is_file() or not self.model_cache_path.is_file():
            raise FileNotFoundError("successor model runtime or cache is absent")
        rows = []
        claims = {}
        episodes = {}
        for episode in self.design.episode_manifest(protocol):
            if not self.store.completed(episode, protocol_sha256):
                raise RuntimeError(
                    f"incomplete successor episode: {episode['episode_id']}"
                )
            path = self.store.episode_path(episode)
            rows.append(c414.load_json(path))
            claims[episode["episode_id"]] = c444.sha256(
                self.store.claim_path(episode)
            )
            episodes[episode["episode_id"]] = c444.sha256(path)
        return rows, claims, episodes

    def summarize(
        self, protocol: dict[str, Any], protocol_sha256: str
    ) -> dict[str, Any]:
        if self.result_path.exists():
            raise FileExistsError(self.result_path)
        rows, claims, episodes = self.load_completed(protocol, protocol_sha256)
        analysis = self.design.analyze_rows(
            rows,
            protocol,
            all_claims_complete=(
                len(claims) == self.design.expected_episodes()
            ),
        )
        payload = {
            "candidate": self.design.CANDIDATE,
            "created_utc": c427.utc_now(),
            "status": "complete_passed" if analysis["passed"] else "complete_failed",
            "passed": analysis["passed"],
            "decision": (
                self.design.DECISION_RULE["on_pass"]
                if analysis["passed"]
                else self.design.DECISION_RULE["on_failure"]
            ),
            "protocol": str((self.run_root / "protocol.json").relative_to(self.root)),
            "protocol_sha256": protocol_sha256,
            "scientific_source_commit": protocol["scientific_source_commit"],
            "predecessor": protocol["predecessor"],
            "outcome_definitions": protocol["outcome_definitions"],
            "primary_comparison": protocol["primary_comparison"],
            "analysis": analysis,
            "claim_manifest": claims,
            "episode_manifest": episodes,
            "model_runtime": {
                "path": str(self.model_runtime_path.relative_to(self.root)),
                "sha256": c444.sha256(self.model_runtime_path),
            },
            "planner_cache": {
                "path": str(self.model_cache_path.relative_to(self.root)),
                "sha256": c444.sha256(self.model_cache_path),
            },
        }
        c414.atomic_write_json(self.result_path, payload)
        print(
            json.dumps(
                {
                    "result": str(self.result_path.relative_to(self.root)),
                    "result_sha256": c444.sha256(self.result_path),
                    "passed": payload["passed"],
                    "checks": analysis["checks"],
                    "metrics": analysis["metrics"],
                    "paired": analysis[
                        "paired_stack_vs_safe_task_success"
                    ],
                    "by_task_budget": analysis["by_task_budget"],
                },
                indent=2,
            )
        )
        return payload


__all__ = ["FrozenSuccessorRuntime"]
