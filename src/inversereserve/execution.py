"""Experiment preparation, execution, and result publication are separate phases."""

from __future__ import annotations

from dataclasses import asdict
from importlib.metadata import PackageNotFoundError, version
from typing import Any

from inversereserve.api import Budgets, run_episode
from inversereserve.artifacts import completed_run, source_identity, write_record
from inversereserve.replay import ReplayEnvironment, load_replay
from inversereserve.resources import sha256_file
from inversereserve.settings import RunConfig


def prepare(config: RunConfig) -> tuple[dict[str, Any], ReplayEnvironment | None]:
    for binding in config.required_files:
        binding.check()
    resources: dict[str, Any] = {str(binding.path): binding.sha256 for binding in config.required_files}
    replay = None
    if config.backend == "replay":
        if set(config.options) - {"replay_file", "scenario"}:
            raise ValueError("Replay options are replay_file or scenario")
        value = config.options.get("replay_file")
        path = config.paths.expand(str(value), base=config.base) if value else None
        if path is not None:
            if not any(binding.path == path for binding in config.required_files):
                raise ValueError("External replay_file requires an exact required_files SHA256 binding")
            resources["replay_file_sha256"] = sha256_file(path)
        replay = load_replay(path, str(config.options.get("scenario", "commit")))
    else:
        from inversereserve.browser_runtime import preflight_browser

        resources["browser"] = preflight_browser(config)
    identity = {
        "schema": 1,
        "kind": "maintained_experiment",
        "historical_evidence": False,
        "run_id": config.run_id,
        "backend": config.backend,
        "method": config.method,
        "budgets": asdict(config.budgets),
        "options": config.options,
        "resources": resources,
        "source": source_identity(),
        "runtime": runtime_versions(),
    }
    return identity, replay


def runtime_versions() -> dict[str, str]:
    result = {}
    for name in (
        "inversereserve",
        "numpy",
        "browsergym-core",
        "browsergym-miniwob",
        "playwright",
        "torch",
        "transformers",
    ):
        try:
            result[name] = version(name)
        except PackageNotFoundError:
            continue
    return result


def _execute(config: RunConfig, replay: ReplayEnvironment | None) -> dict[str, Any]:
    if replay is not None:
        return run_episode(
            environment=replay,
            observation=replay.initial,
            planner=replay.generate,
            budgets=config.budgets,
            method=config.method,
        )
    from inversereserve.browser_runtime import miniwob_session

    with miniwob_session(config) as (environment, observation, planner):
        return run_episode(
            environment=environment,
            observation=observation,
            planner=planner,
            budgets=config.budgets,
            method=config.method,
        )


def run(config: RunConfig, *, resume: bool = False) -> dict[str, Any]:
    identity, replay = prepare(config)
    output = config.output
    if output.exists():
        if resume:
            return completed_run(output, identity)
        raise ValueError(
            f"Run already exists: {output}; choose a new run_id or --resume for a completed result"
        )
    output.mkdir(parents=True, exist_ok=False)
    write_record(output / "protocol.json", identity)
    try:
        result = {
            "kind": "maintained_experiment",
            "historical_evidence": False,
            "source_sha256": identity["source"]["sha256"],
            **_execute(config, replay),
        }
        write_record(output / "result.json", result)
        write_record(output / "complete.json", {"result_sha256": sha256_file(output / "result.json")})
    except Exception as error:
        write_record(
            output / "failure.json",
            {
                "type": type(error).__name__,
                "message": str(error),
                "recovery": "Inspect this run and use a fresh run_id; no GUI state is assumed recoverable.",
            },
        )
        raise
    return result


def demo(scenario: str = "commit") -> dict[str, Any]:
    replay = load_replay(None, scenario)
    result = run_episode(
        environment=replay,
        observation=replay.initial,
        planner=replay.generate,
        budgets=Budgets(maximum_gui_actions=4, maximum_planner_calls=4, maximum_wall_seconds=30),
    )
    return {
        "kind": "offline_demo",
        "scenario": scenario,
        "historical_evidence": False,
        "actions": replay.calls,
        **result,
    }
