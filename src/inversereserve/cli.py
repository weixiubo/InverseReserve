"""Portable installed commands; resource lookup occurs only after explicit invocation."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from importlib.resources import files
from pathlib import Path
from typing import Any

from inversereserve.execution import demo, prepare, run
from inversereserve.resources import resolve_paths, resource_report
from inversereserve.settings import read_config


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="inversereserve")
    commands = root.add_subparsers(dest="command", required=True)
    doctor = commands.add_parser("doctor", help="check basic environment and external resource locations")
    doctor.add_argument("--config", type=Path)
    example = commands.add_parser("demo", help="run a small offline controller episode")
    example.add_argument("--scenario", choices=["commit", "no-effect", "action-error"], default="commit")
    experiment = commands.add_parser("run", help="run a configured experiment under a new source identity")
    experiment.add_argument("--config", type=Path, required=True)
    experiment.add_argument("--resume", action="store_true", help="reuse only a complete verified result")
    commands.add_parser("reproduce", help="verify original evidence and rebuild its frozen analysis")
    for command in (doctor, experiment):
        for name in ("data", "models", "runs", "evidence"):
            command.add_argument(f"--{name}-dir")
    return root


def dispatch(args: argparse.Namespace) -> dict[str, Any]:
    if args.command == "demo":
        return demo(args.scenario)
    if args.command == "reproduce":
        from inversereserve.reproduction import reproduce

        return reproduce()
    overrides = {kind: getattr(args, f"{kind}_dir") for kind in ("data", "models", "runs", "evidence")}
    if args.command == "run":
        return run(read_config(args.config, overrides), resume=args.resume)
    catalog = json.loads(files("inversereserve").joinpath("resource_catalog.json").read_text())
    paths = resolve_paths(overrides)
    result: dict[str, Any] = {
        "python": sys.version.split()[0],
        "paths": paths.as_strings(),
        "offline_commands_ready": sys.version_info[:2] == (3, 12),
        "resources": resource_report(catalog, paths),
    }
    if args.config:
        config = read_config(args.config, overrides)
        result["resources"] = resource_report(catalog, config.paths)
        identity, _replay = prepare(config)
        result.update(
            {"configured_run_ready": True, "paths": config.paths.as_strings(), "identity": identity}
        )
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        result = dispatch(args)
    except (OSError, ValueError, RuntimeError, ImportError, subprocess.SubprocessError) as error:
        print(json.dumps({"status": "failed", "error": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0
