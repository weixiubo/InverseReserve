"""Portable entry, missing-resource, recovery and public API regression scenarios."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from inversereserve.cli import main
from inversereserve.execution import demo, run
from inversereserve.model_runtime import require_inference, verify_model_manifest
from inversereserve.replay import ReplayEnvironment, builtin_record, decode_observation
from inversereserve.resources import sha256_file
from inversereserve.settings import read_config


def config_file(tmp_path, **changes):
    data = {"schema": 1, "run_id": "case", "backend": "replay", "paths": {"runs": "outputs"}}
    data.update(changes)
    path = tmp_path / "config.json"
    path.write_text(json.dumps(data))
    return path


@pytest.mark.parametrize(
    "scenario,success,effect_failures",
    [("commit", True, 0), ("no-effect", False, 1), ("action-error", False, 0)],
)
def test_demo_executes_bounded_real_controller(scenario, success, effect_failures):
    result = demo(scenario)
    assert result["success"] is success
    assert result["metrics"]["gui_actions"] == 1
    assert result["metrics"]["commit_effect_failures"] == effect_failures
    assert result["metrics"]["planner_calls"] == 0
    assert result["historical_evidence"] is False
    assert result["candidate"] == "inversereserve-maintained-episode-v1"


@pytest.mark.parametrize(
    "field,value",
    [
        ("run_id", "../escape"),
        ("schema", 2),
        ("backend", "unknown"),
        ("method", "unknown"),
        ("budgets", {"maximum_gui_actions": True}),
        ("budgets", {"maximum_planner_calls": -1}),
        ("budgets", {"maximum_wall_seconds": float("nan")}),
        ("budgets", {"unexpected": 4}),
        ("options", []),
        ("paths", {"wrong": "x"}),
        ("required_files", [{"path": "x", "sha256": "bad"}]),
    ],
)
def test_bad_configuration_fails_without_outputs(tmp_path, field, value):
    path = config_file(tmp_path, **{field: value})
    with pytest.raises(ValueError):
        read_config(path)
    assert not (tmp_path / "outputs").exists()


def test_config_relative_paths_do_not_depend_on_working_directory(tmp_path, monkeypatch):
    path = config_file(tmp_path)
    other = tmp_path / "elsewhere"
    other.mkdir()
    monkeypatch.chdir(other)
    assert read_config(path).output == tmp_path / "outputs/case"


def test_completed_resume_checks_result_identity_and_does_not_execute_again(tmp_path, monkeypatch):
    config = read_config(config_file(tmp_path))
    first = run(config)
    import inversereserve.execution as execution

    monkeypatch.setattr(
        execution, "_execute", lambda *_: pytest.fail("resumed complete result executed again")
    )
    second = run(config, resume=True)
    assert json.loads(json.dumps(first)) == second
    with pytest.raises(ValueError, match="already exists"):
        run(config)
    result = config.output / "result.json"
    result.write_text(result.read_text() + " ")
    with pytest.raises(ValueError, match="checksum"):
        run(config, resume=True)


def test_interrupted_run_requires_fresh_environment(tmp_path):
    config = read_config(config_file(tmp_path))
    config.output.mkdir(parents=True)
    with pytest.raises(ValueError, match="incomplete"):
        run(config, resume=True)
    assert list(config.output.iterdir()) == []


def test_exception_retains_failure_record(tmp_path, monkeypatch):
    import inversereserve.execution as execution

    config = read_config(config_file(tmp_path))

    def broken(*_):
        raise RuntimeError("injected backend failure")

    monkeypatch.setattr(execution, "_execute", broken)
    with pytest.raises(RuntimeError, match="injected"):
        run(config)
    assert json.loads((config.output / "failure.json").read_text())["type"] == "RuntimeError"
    assert (config.output / "protocol.json").is_file()
    assert not (config.output / "complete.json").exists()


@pytest.mark.parametrize("kind", ["missing", "checksum", "unbound", "malformed"])
def test_external_replay_fails_before_output_creation(tmp_path, kind):
    replay = tmp_path / "episode.json"
    if kind != "missing":
        replay.write_text("{}" if kind == "malformed" else json.dumps(builtin_record()))
    digest = sha256_file(replay) if replay.exists() else "0" * 64
    if kind == "checksum":
        digest = "0" * 64
    bindings = [] if kind == "unbound" else [{"path": "episode.json", "sha256": digest}]
    config = read_config(
        config_file(tmp_path, options={"replay_file": "episode.json"}, required_files=bindings)
    )
    with pytest.raises(ValueError):
        run(config)
    assert not config.output.exists()


def test_external_replay_is_bound_into_new_identity(tmp_path):
    episode = tmp_path / "episode.json"
    episode.write_text(json.dumps(builtin_record()))
    config = read_config(
        config_file(
            tmp_path,
            options={"replay_file": "episode.json"},
            required_files=[{"path": "episode.json", "sha256": sha256_file(episode)}],
        )
    )
    result = run(config)
    protocol = json.loads((config.output / "protocol.json").read_text())
    assert result["success"] is True
    assert protocol["resources"]["replay_file_sha256"] == sha256_file(episode)
    assert protocol["source"]["namespace"] == "inversereserve-0.2"


def test_replay_refuses_unrecorded_actions_and_missing_model_answers():
    replay = ReplayEnvironment(builtin_record())
    with pytest.raises(ValueError, match="diverged"):
        replay.step("click('wrong')")
    assert replay.calls == []
    with pytest.raises(ValueError, match="No prerecorded"):
        replay.generate([])
    replay.step("click('1')")
    with pytest.raises(ValueError, match="exhausted"):
        replay.step("click('1')")


@pytest.mark.parametrize("viewport", [[], [0, 10], [True, 10], [10, 100000]])
def test_replay_rejects_invalid_viewport_before_allocation(viewport):
    value = builtin_record()["initial"]
    value["viewport"] = viewport
    with pytest.raises(ValueError, match="viewport"):
        decode_observation(value)


def test_doctor_uses_configured_resource_roots(tmp_path, capsys):
    data = tmp_path / "data/miniwob/html"
    data.mkdir(parents=True)
    path = config_file(tmp_path, paths={"runs": "outputs", "data": "data"})
    assert main(["doctor", "--config", str(path)]) == 0
    report = json.loads(capsys.readouterr().out)
    html = next(r for r in report["resources"] if r["id"] == "miniwob-html")
    assert Path(html["path"]) == data
    assert html["status"] == "present_unverified"
    assert not (tmp_path / "outputs").exists()


def test_browser_resource_failure_precedes_environment_creation(tmp_path, capsys):
    path = config_file(tmp_path, backend="miniwob", options={"task": "click-widget", "html_root": "missing"})
    assert main(["run", "--config", str(path)]) == 2
    assert "MiniWoB task missing" in capsys.readouterr().err
    assert not (tmp_path / "outputs").exists()


def test_missing_optional_inference_is_diagnostic(monkeypatch):
    import inversereserve.model_runtime as model_runtime

    monkeypatch.setattr(model_runtime.importlib.util, "find_spec", lambda _: None)
    with pytest.raises(ValueError, match="uv sync --extra inference"):
        require_inference()


def test_model_manifest_binds_every_file_and_rejects_changes(tmp_path):
    root = tmp_path / "model"
    root.mkdir()
    (root / "config.json").write_text("{}")
    (root / "model.safetensors").write_bytes(b"fixture")
    manifest = root / "resource-manifest.json"
    record = {f.name: sha256_file(f) for f in root.iterdir()}
    manifest.write_text(json.dumps(record))
    assert verify_model_manifest(root, manifest) == record
    (root / "unbound.json").write_text("{}")
    with pytest.raises(ValueError, match="exact visible"):
        verify_model_manifest(root, manifest)
    (root / "config.json").write_text('{"changed": true}')
    with pytest.raises(ValueError, match="checksum"):
        verify_model_manifest(root, manifest)


def test_model_manifest_refuses_external_members(tmp_path):
    (tmp_path / "outside").write_text("external")
    root = tmp_path / "model"
    root.mkdir()
    (root / "config.json").write_text("{}")
    manifest = root / "resource-manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "config.json": sha256_file(root / "config.json"),
                "../outside": sha256_file(tmp_path / "outside"),
            }
        )
    )
    with pytest.raises(ValueError, match="invalid manifest"):
        verify_model_manifest(root, manifest)


@pytest.mark.parametrize(
    "method", ["stack-reserve", "single-active", "top-cleanup", "task-reserve-single", "task-reserve-cleanup"]
)
def test_successor_scopes_have_explicit_installed_entry(method):
    from inversereserve.api import Budgets, run_episode

    replay = ReplayEnvironment(builtin_record())
    result = run_episode(
        environment=replay,
        observation=replay.initial,
        planner=replay.generate,
        budgets=Budgets(4, 4, 30),
        method=method,
    )
    assert result["success"] is True
    assert result["metrics"]["gui_actions"] == 1
    assert result["metrics"]["runtime_halted"] is False
    assert result["historical_evidence"] is False
