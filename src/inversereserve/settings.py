"""Validated experiment settings. Relative paths are resolved beside the config."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

from inversereserve.api import METHODS, Budgets, Method
from inversereserve.resources import ResourcePaths, resolve_paths, sha256_file


@dataclass(frozen=True)
class FileBinding:
    path: Path
    sha256: str

    def check(self) -> None:
        if not self.path.is_file():
            raise ValueError(f"Required file missing: {self.path}; restore the file declared in the config")
        if sha256_file(self.path) != self.sha256:
            raise ValueError(f"Checksum mismatch: {self.path}; restore the declared version")


@dataclass(frozen=True)
class RunConfig:
    run_id: str
    backend: str
    method: Method
    budgets: Budgets
    paths: ResourcePaths
    base: Path
    options: dict[str, Any] = field(default_factory=dict)
    required_files: tuple[FileBinding, ...] = ()

    @property
    def output(self) -> Path:
        return self.paths.runs / self.run_id


def read_config(path: Path, overrides: dict[str, str | None] | None = None) -> RunConfig:
    absolute = path.expanduser().resolve()
    data = json.loads(absolute.read_text(encoding="utf-8"))
    keys = {"schema", "run_id", "backend", "method", "budgets", "paths", "options", "required_files"}
    if not isinstance(data, dict) or set(data) - keys or data.get("schema") != 1:
        raise ValueError("Config must be a schema: 1 object with documented keys")
    run_id = data.get("run_id")
    if not isinstance(run_id, str) or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,95}", run_id) is None:
        raise ValueError("run_id must be a simple identifier, without directory components")
    backend = data.get("backend", "replay")
    method = data.get("method", "full")
    if not isinstance(backend, str) or backend not in {"replay", "miniwob"}:
        raise ValueError("Supported backends: replay, miniwob")
    if not isinstance(method, str) or method not in METHODS:
        raise ValueError(f"Supported methods: {sorted(METHODS)}")
    options = data.get("options", {})
    if not isinstance(options, dict):
        raise ValueError("options must be an object")
    paths = _paths(data.get("paths", {}), absolute.parent, overrides or {})
    raw_budgets = data.get("budgets", {})
    if not isinstance(raw_budgets, dict):
        raise ValueError("budgets must be an object")
    try:
        budgets = Budgets(**raw_budgets)
    except TypeError as error:
        raise ValueError(f"Invalid budgets: {error}") from error
    bindings = _bindings(data.get("required_files", []), paths, absolute.parent)
    return RunConfig(
        run_id, backend, cast(Method, method), budgets, paths, absolute.parent, options, bindings
    )


def _paths(raw: Any, base: Path, overrides: dict[str, str | None]) -> ResourcePaths:
    if not isinstance(raw, dict) or any(not isinstance(v, str) or not v for v in raw.values()):
        raise ValueError("paths must map root names to nonempty strings")
    values: dict[str, str | Path | None] = {k: base / Path(v).expanduser() for k, v in raw.items()}
    values.update({k: v for k, v in overrides.items() if v is not None})
    return resolve_paths(values)


def _bindings(raw: Any, paths: ResourcePaths, base: Path) -> tuple[FileBinding, ...]:
    if not isinstance(raw, list):
        raise ValueError("required_files must be a list of path/sha256 records")
    result = []
    for row in raw:
        if not isinstance(row, dict) or set(row) != {"path", "sha256"}:
            raise ValueError("Each required file must specify path and sha256")
        if not isinstance(row["path"], str) or not isinstance(row["sha256"], str):
            raise ValueError("Resource path and sha256 must be strings")
        if re.fullmatch(r"[0-9a-f]{64}", row["sha256"]) is None:
            raise ValueError("Resource sha256 must contain 64 lowercase hexadecimal digits")
        result.append(FileBinding(paths.expand(row["path"], base=base), row["sha256"]))
    return tuple(result)
