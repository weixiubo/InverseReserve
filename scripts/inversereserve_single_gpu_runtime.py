#!/usr/bin/env python3
"""Single-GPU deployment for the frozen InverseReserve Qwen planner.

This module leaves the historical two-GPU C444 implementation byte-identical.
It changes device placement only: the same model snapshot is loaded in BF16 on
the single visible RTX 4090 and the ordinary C444 generation/cache semantics
are inherited unchanged.
"""

from __future__ import annotations

import json
import os
import platform
import sqlite3
import sys
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
import c444_pact_v7_matched_confirmation as c444  # noqa: E402


SINGLE_GPU_DEPLOYMENT = {
    "model_weights_and_dtype_unchanged": True,
    "visible_cuda_devices": 1,
    "cuda_visible_devices": "0",
    "device_map": "auto",
}

FROZEN_TWO_GPU_DEVICE_MAP = "balanced"


def validate_single_gpu_deployment(protocol: dict[str, Any]) -> dict[str, Any]:
    deployment = protocol.get("runtime_deployment")
    if not isinstance(deployment, dict):
        raise ValueError("single-GPU runtime deployment changed")
    cuda_visible_devices = deployment.get("cuda_visible_devices")
    expected = dict(SINGLE_GPU_DEPLOYMENT)
    expected["cuda_visible_devices"] = cuda_visible_devices
    if cuda_visible_devices not in {"0", "1"} or deployment != expected:
        raise ValueError("single-GPU runtime deployment changed")
    return dict(deployment)


class SingleGpuFrozenModelService(c444.FrozenModelServiceV7):
    """C444-compatible planner service with one explicitly visible GPU."""

    def __init__(
        self,
        *,
        protocol: dict[str, Any],
        protocol_sha256: str,
        model_path: Path,
        model_cache_path: Path,
        model_runtime_path: Path,
    ) -> None:
        import torch
        import transformers
        from transformers import AutoModelForMultimodalLM, AutoProcessor

        deployment = validate_single_gpu_deployment(protocol)
        verified = c416.verify_inputs(model_path)
        c415 = verified[0]
        self.model_hashes = verified[-1]
        runtime = c415["runtime"]
        if torch.__version__ != runtime["torch"]:
            raise ValueError("single-GPU torch runtime changed")
        if transformers.__version__ != runtime["transformers"]:
            raise ValueError("single-GPU transformers runtime changed")
        if runtime["device_map"] != FROZEN_TWO_GPU_DEVICE_MAP:
            raise ValueError("frozen two-GPU model device map changed")
        if os.environ.get("CUDA_VISIBLE_DEVICES") != deployment[
            "cuda_visible_devices"
        ]:
            raise ValueError("single-GPU CUDA visibility changed")
        if torch.cuda.device_count() != deployment["visible_cuda_devices"]:
            raise ValueError(
                "single-GPU visible device count changed: "
                f"{torch.cuda.device_count()}"
            )

        self.processor = AutoProcessor.from_pretrained(model_path)
        self.template_audit = c416.validate_nonthinking_template(self.processor)
        self.model = AutoModelForMultimodalLM.from_pretrained(
            model_path,
            dtype=torch.bfloat16,
            device_map=str(deployment["device_map"]),
        )
        self.model.eval()
        self.protocol_sha256 = protocol_sha256
        self.actual_calls = 0
        self.cache_hits = 0

        model_cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(model_cache_path)
        self.connection.execute(
            "CREATE TABLE IF NOT EXISTS metadata "
            "(key TEXT PRIMARY KEY, value_json TEXT NOT NULL)"
        )
        self.connection.execute(
            "CREATE TABLE IF NOT EXISTS entries ("
            "cache_key TEXT PRIMARY KEY, messages_json TEXT NOT NULL, "
            "raw_output TEXT NOT NULL, input_tokens INTEGER NOT NULL, "
            "generated_tokens INTEGER NOT NULL)"
        )
        expected_metadata = {
            "candidate": "InverseReserve-single-gpu-planner-cache-v1",
            "protocol_sha256": protocol_sha256,
            "model_file_sha256": self.model_hashes,
            "template_audit": self.template_audit,
            "generation": protocol["generation"],
            "runtime_deployment": deployment,
        }
        observed = {
            key: json.loads(value)
            for key, value in self.connection.execute(
                "SELECT key, value_json FROM metadata"
            )
        }
        if observed and observed != expected_metadata:
            raise ValueError("incompatible single-GPU planner cache")
        if not observed:
            self.connection.executemany(
                "INSERT INTO metadata(key, value_json) VALUES (?, ?)",
                [
                    (key, c444.canonical_json(value))
                    for key, value in expected_metadata.items()
                ],
            )
            self.connection.commit()

        runtime_record = {
            "candidate": "InverseReserve-single-gpu-model-runtime-v1",
            "created_utc": c427.utc_now(),
            "git_head": c444.git_head(),
            "protocol_sha256": protocol_sha256,
            "model_file_sha256": self.model_hashes,
            "generation": protocol["generation"],
            "runtime_deployment": deployment,
            "runtime": {
                "python": sys.version,
                "platform": platform.platform(),
                "torch": torch.__version__,
                "transformers": transformers.__version__,
                "cuda_devices": [torch.cuda.get_device_name(0)],
                "cuda_visible_devices": os.environ["CUDA_VISIBLE_DEVICES"],
                "device_map": deployment["device_map"],
                "dtype": str(torch.bfloat16),
                "template_audit": self.template_audit,
            },
        }
        if model_runtime_path.exists():
            existing = c414.load_json(model_runtime_path)
            for key in (
                "protocol_sha256",
                "model_file_sha256",
                "generation",
                "runtime_deployment",
            ):
                if existing.get(key) != runtime_record[key]:
                    raise ValueError(f"single-GPU model runtime changed: {key}")
        else:
            c414.atomic_write_json(model_runtime_path, runtime_record)


def run_population(
    *,
    protocol: dict[str, Any],
    protocol_sha256: str,
    model_path: Path,
    design: Any,
    store: Any,
    episode_directory: Path,
    claim_directory: Path,
    model_cache_path: Path,
    model_runtime_path: Path,
) -> None:
    """Run a create-once capacity population using the single-GPU service."""

    manifest = design.episode_manifest(protocol)
    pending = [
        episode
        for episode in manifest
        if not store.completed(episode, protocol_sha256)
    ]
    if not pending:
        print("single-GPU capacity population already complete", flush=True)
        return

    service = SingleGpuFrozenModelService(
        protocol=protocol,
        protocol_sha256=protocol_sha256,
        model_path=model_path,
        model_cache_path=model_cache_path,
        model_runtime_path=model_runtime_path,
    )
    environment_protocol = c414.load_json(c434.C433_PROTOCOL)
    episode_directory.mkdir(parents=True, exist_ok=True)
    claim_directory.mkdir(parents=True, exist_ok=True)
    try:
        with c427.MiniwobServer(c433.HTML_ROOT) as base_url:
            for episode in pending:
                store.open(episode, protocol_sha256)
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
                            "maximum_gui_actions": episode["maximum_gui_actions"],
                        }
                        driver = design.DRIVERS[episode["method"]](
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
                    result["candidate"] = f"{design.CANDIDATE}-episode"
                finally:
                    if environment is not None:
                        environment.close()
                path = store.episode_path(episode)
                c414.atomic_write_json(path, result)
                store.complete(episode, protocol_sha256, path)
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
                        "single-GPU population stopped after sealing "
                        "an infrastructure failure"
                    )
    finally:
        service.close()
