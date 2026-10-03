"""Explicit local-only planner loading and content-bound model resources."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

from inversereserve.artifacts import canonical_hash
from inversereserve.resources import sha256_file


def verify_model_manifest(root: Path, manifest: Path) -> dict[str, str]:
    records = json.loads(manifest.read_text(encoding="utf-8"))
    if not isinstance(records, dict) or not records or "config.json" not in records:
        raise ValueError("Model manifest must map every local model file to SHA256, including config.json")
    root = root.resolve()
    for name, expected in records.items():
        target = (root / name).resolve()
        if not target.is_relative_to(root) or not target.is_file():
            raise ValueError(f"Missing or invalid manifest member: {name}")
        if sha256_file(target) != expected:
            raise ValueError(f"Model checksum mismatch: {name}")
    actual = visible_model_files(root, manifest)
    if actual != set(records):
        raise ValueError("Model manifest does not cover the exact visible model file tree")
    if not any((name.endswith((".safetensors", ".bin")) for name in records)):
        raise ValueError("Model manifest contains no weights")
    return dict(records)


def require_inference() -> None:
    for module in ("torch", "transformers", "accelerate"):
        if importlib.util.find_spec(module) is None:
            raise ValueError(f"Optional inference dependency {module} missing; run uv sync --extra inference")


class LocalPlanner:
    def __init__(self, model: Path, *, device_map: str = "auto", max_new_tokens: int = 64) -> None:
        import torch
        from transformers import AutoModelForMultimodalLM, AutoProcessor

        self.torch = torch
        self.processor = AutoProcessor.from_pretrained(model, local_files_only=True, trust_remote_code=False)
        self.model = AutoModelForMultimodalLM.from_pretrained(
            model, dtype=torch.bfloat16, device_map=device_map, local_files_only=True, trust_remote_code=False
        )
        self.model.eval()
        self.max_new_tokens = max_new_tokens

    def generate(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        text = self.processor.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True, enable_thinking=False
        )
        inputs = self.processor(text=[text], return_tensors="pt").to(self.model.device)
        size = int(inputs["input_ids"].shape[-1])
        with self.torch.inference_mode():
            tokens = self.model.generate(**inputs, do_sample=False, max_new_tokens=self.max_new_tokens)
        continuation = tokens[0, size:]
        return {
            "cache_key": canonical_hash(messages),
            "cache_hit": False,
            "raw_output": self.processor.decode(continuation, skip_special_tokens=True),
            "input_tokens": size,
            "generated_tokens": int(continuation.shape[-1]),
        }


def visible_model_files(root: Path, manifest: Path) -> set[str]:
    return {
        str(f.relative_to(root))
        for f in root.rglob("*")
        if f.is_file()
        and (not any((part.startswith(".") for part in f.relative_to(root).parts)))
        and (f.resolve() != manifest.resolve())
    }
