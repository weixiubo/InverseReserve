"""Shared one-open execution machinery for source-bound PACT-v10 gates."""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping


ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT / "src", ROOT / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import c414_adaptive_semantic_risk_diagnostic as c414  # noqa: E402
import c427_pact_live_development as c427  # noqa: E402
import c433_fresh_observation_preflight as c433  # noqa: E402
import c434_pact_v4_live_development_gate as c434  # noqa: E402
import c444_pact_v7_matched_confirmation as c444  # noqa: E402


DriverFactory = Callable[..., Any]


def activation_artifact(reference: dict[str, Any], *, role: str) -> Path:
    if set(reference) != {"path", "sha256"}:
        raise ValueError(f"{role} activation reference changed")
    relative = Path(str(reference["path"]))
    if relative.is_absolute():
        raise ValueError(f"{role} activation path must be repository-relative")
    path = (ROOT / relative).resolve()
    if path.parent != (ROOT / "validation").resolve():
        raise ValueError(f"{role} must be a top-level validation artifact")
    if not path.is_file():
        raise FileNotFoundError(f"{role} activation artifact is absent: {path}")
    actual = c444.sha256(path)
    if actual != reference["sha256"]:
        raise ValueError(f"{role} activation artifact changed: {actual}")
    return path


def verify_source_bound_protocol(
    protocol: dict[str, Any],
    *,
    required_source_paths: set[str],
) -> None:
    if protocol.get("repositories") != c444.EXPECTED_REPOSITORIES:
        raise ValueError("PACT-v10 repository pins changed")
    for name, expected_head in c444.EXPECTED_REPOSITORIES.items():
        c444.verify_clean_repository(c444.REPOSITORY_PATHS[name], expected_head)
    source_hashes = protocol.get("source_sha256", {})
    if not required_source_paths.issubset(source_hashes):
        missing = sorted(required_source_paths - set(source_hashes))
        raise ValueError(f"PACT-v10 protocol omits source bindings: {missing}")
    for relative, expected in source_hashes.items():
        source = (ROOT / relative).resolve()
        try:
            source.relative_to(ROOT.resolve())
        except ValueError as error:
            raise ValueError(f"source binding escapes repository: {relative}") from error
        if not source.is_file() or c444.sha256(source) != expected:
            raise ValueError(f"PACT-v10 source changed: {relative}")
    note = protocol.get("preregistration", {})
    if set(note) != {"path", "sha256"}:
        raise ValueError("PACT-v10 preregistration binding changed")
    note_path = (ROOT / str(note["path"])).resolve()
    notes_root = (ROOT / "paper" / "aaai27" / "notes").resolve()
    try:
        note_path.relative_to(notes_root)
    except ValueError as error:
        raise ValueError("PACT-v10 preregistration must live under paper notes") from error
    if not note_path.is_file() or c444.sha256(note_path) != note["sha256"]:
        raise ValueError("PACT-v10 preregistration changed")


def require_unopened(*, output_path: Path, directories: Iterable[Path], role: str) -> None:
    if output_path.exists():
        raise ValueError(f"{role} result already exists")
    for directory in directories:
        if directory.exists() and any(path.is_file() for path in directory.rglob("*")):
            raise ValueError(f"{role} has already been opened")


@dataclass(frozen=True)
class OneOpenEpisodeStore:
    episode_directory: Path
    claim_directory: Path
    claim_candidate: str

    def claim_path(self, episode: dict[str, Any]) -> Path:
        return self.claim_directory / f"{episode['episode_id']}.json"

    def episode_path(self, episode: dict[str, Any]) -> Path:
        return self.episode_directory / f"{episode['episode_id']}.json"

    def completed(self, episode: dict[str, Any], protocol_sha256: str) -> bool:
        claim = self.claim_path(episode)
        result = self.episode_path(episode)
        if not claim.exists() and not result.exists():
            return False
        if not claim.is_file() or not result.is_file():
            raise RuntimeError(
                f"one-open episode has unmatched claim/result: {episode['episode_id']}"
            )
        claim_row = c414.load_json(claim)
        result_row = c414.load_json(result)
        if not (
            claim_row.get("candidate") == self.claim_candidate
            and claim_row.get("status") == "complete"
            and claim_row.get("episode") == episode
            and claim_row.get("protocol_sha256") == protocol_sha256
            and claim_row.get("episode_sha256") == c444.sha256(result)
            and result_row.get("complete") is True
            and result_row.get("episode") == episode
            and result_row.get("protocol_sha256") == protocol_sha256
        ):
            raise RuntimeError(f"incompatible one-open episode: {episode['episode_id']}")
        return True

    def open(self, episode: dict[str, Any], protocol_sha256: str) -> None:
        claim = self.claim_path(episode)
        if claim.exists() or self.episode_path(episode).exists():
            raise FileExistsError(
                f"one-open episode already opened: {episode['episode_id']}"
            )
        c414.atomic_write_json(
            claim,
            {
                "candidate": self.claim_candidate,
                "created_utc": c427.utc_now(),
                "status": "claimed_before_reset",
                "protocol_sha256": protocol_sha256,
                "episode": episode,
            },
        )

    def complete(
        self,
        episode: dict[str, Any],
        protocol_sha256: str,
        result_path: Path,
    ) -> None:
        c414.atomic_write_json(
            self.claim_path(episode),
            {
                "candidate": self.claim_candidate,
                "completed_utc": c427.utc_now(),
                "status": "complete",
                "protocol_sha256": protocol_sha256,
                "episode": episode,
                "episode_sha256": c444.sha256(result_path),
            },
        )


def run_one_open_grid(
    *,
    manifest: list[dict[str, Any]],
    protocol: dict[str, Any],
    protocol_sha256: str,
    store: OneOpenEpisodeStore,
    driver_registry: Mapping[str, DriverFactory],
    episode_candidate: str,
    model_path: Path,
    model_cache_path: Path,
    model_runtime_path: Path,
    progress_label: str,
) -> None:
    store.episode_directory.mkdir(parents=True, exist_ok=True)
    store.claim_directory.mkdir(parents=True, exist_ok=True)
    pending = [
        episode
        for episode in manifest
        if not store.completed(episode, protocol_sha256)
    ]
    if not pending:
        print(f"{progress_label} already complete", flush=True)
        return
    c444.MODEL_CACHE_PATH = model_cache_path
    c444.MODEL_RUNTIME_PATH = model_runtime_path
    service = c444.FrozenModelServiceV7(
        protocol=protocol,
        protocol_sha256=protocol_sha256,
        model_path=model_path,
    )
    parent_protocol = c414.load_json(c434.C433_PROTOCOL)
    try:
        with c427.MiniwobServer(c433.HTML_ROOT) as base_url:
            for episode in pending:
                store.open(episode, protocol_sha256)
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
                        driver = driver_registry[episode["method"]](
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
                    result["candidate"] = episode_candidate
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
                        f"{progress_label} stopped after sealing an infrastructure failure"
                    )
    finally:
        service.close()


def load_completed_grid(
    *,
    manifest: list[dict[str, Any]],
    protocol_sha256: str,
    store: OneOpenEpisodeStore,
    model_cache_path: Path,
    model_runtime_path: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, str]]:
    if not model_runtime_path.is_file() or not model_cache_path.is_file():
        raise FileNotFoundError("model runtime or planner cache is absent")
    rows = []
    compact = []
    for episode in manifest:
        if not store.completed(episode, protocol_sha256):
            raise RuntimeError(f"incomplete one-open episode: {episode['episode_id']}")
        path = store.episode_path(episode)
        row = c414.load_json(path)
        rows.append(row)
        compact.append(c444.compact_episode(row, path))
    claims = {
        episode["episode_id"]: c444.sha256(store.claim_path(episode))
        for episode in manifest
    }
    return rows, compact, claims
