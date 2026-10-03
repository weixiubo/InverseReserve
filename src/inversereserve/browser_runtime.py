"""Explicit MiniWoB session lifecycle. All optional resources are checked before reset."""

from __future__ import annotations

import importlib.util
import re
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from inversereserve.api import Environment, Planner
from inversereserve.model_runtime import LocalPlanner, require_inference, verify_model_manifest
from inversereserve.resources import sha256_file
from inversereserve.settings import RunConfig


def browser_paths(config: RunConfig) -> tuple[Path, Path, Path]:
    paths = config.paths
    options = config.options
    return (
        paths.expand(str(options.get("html_root", "{data}/miniwob/html")), base=config.base),
        paths.expand(str(options.get("model_path", "{models}/Qwen3.5-9B")), base=config.base),
        paths.expand(
            str(options.get("model_manifest", "{models}/Qwen3.5-9B/resource-manifest.json")), base=config.base
        ),
    )


def preflight_browser(config: RunConfig) -> dict[str, Any]:
    allowed = {"html_root", "model_path", "model_manifest", "task", "seed", "device_map", "max_new_tokens"}
    if set(config.options) - allowed:
        raise ValueError(f"Unknown miniwob options: {sorted(set(config.options) - allowed)}")
    task = config.options.get("task")
    seed = config.options.get("seed", 0)
    if not isinstance(task, str) or re.fullmatch(r"[a-z0-9-]+", task) is None or type(seed) is not int:
        raise ValueError("miniwob requires an explicit task identifier and integer seed")
    maximum = config.options.get("max_new_tokens", 64)
    if type(maximum) is not int or not 1 <= maximum <= 4096:
        raise ValueError("max_new_tokens must be an integer in [1, 4096]")
    html, model, manifest = browser_paths(config)
    task_file = html / "miniwob" / f"{task}.html"
    if not task_file.is_file():
        raise ValueError(
            f"MiniWoB task missing: {task_file}; restore the benchmark HTML revision, then set options.html_root"
        )
    if not model.is_dir() or not manifest.is_file():
        raise ValueError(
            f"Local model or manifest missing: {model}; restore the model and its resource-manifest.json; no download is automatic"
        )
    hashes = verify_model_manifest(model, manifest)
    for module in ("gymnasium", "browsergym", "playwright"):
        if importlib.util.find_spec(module) is None:
            raise ValueError(f"Optional browser dependency {module} missing; run uv sync --extra browser")
    require_inference()
    from playwright.sync_api import sync_playwright

    with sync_playwright() as engine:
        if not Path(engine.chromium.executable_path).is_file():
            raise ValueError("Chromium missing; explicitly run python -m playwright install chromium")
    return {
        "html_root": str(html),
        "html_sha256": {
            str(f.relative_to(html)): sha256_file(f) for f in sorted(html.rglob("*")) if f.is_file()
        },
        "model_manifest": hashes,
        "task": task,
        "seed": seed,
    }


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, _format: str, *args: Any) -> None:
        pass


@contextmanager
def miniwob_session(config: RunConfig) -> Iterator[tuple[Environment, dict[str, Any], Planner]]:
    import browsergym.miniwob  # noqa: F401 - registers benchmark environments
    import gymnasium as gym
    from browsergym.core.action.highlevel import HighLevelActionSet

    html, model, _manifest = browser_paths(config)
    planner = LocalPlanner(
        model,
        device_map=str(config.options.get("device_map", "auto")),
        max_new_tokens=int(config.options.get("max_new_tokens", 64)),
    )
    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(QuietHandler, directory=str(html)))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    environment = None
    try:
        actions = HighLevelActionSet(
            subsets=["bid", "coord"], multiaction=False, strict=True, demo_mode="off"
        )
        environment = gym.make(
            f"browsergym/miniwob.{config.options['task']}",
            headless=True,
            action_mapping=actions.to_python_code,
            pre_observation_delay=0.5,
            task_kwargs={
                "base_url": f"http://127.0.0.1:{server.server_port}/miniwob/",
                "episode_max_time": int(config.budgets.maximum_wall_seconds * 1000),
                "remove_human_display": True,
            },
        )
        observation, _info = environment.reset(seed=int(config.options.get("seed", 0)))
        yield environment, observation, planner.generate
    finally:
        try:
            if environment is not None:
                environment.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)
