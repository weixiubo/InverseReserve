# InverseReserve

Typed GUI transactions with explicit recovery-capacity reservations and freshly
grounded commit certificates. The maintained package is `inversereserve`.

```sh
uv sync --locked                 # Python 3.12, basic development and CPU tests
uv run inversereserve doctor
uv run inversereserve demo
uv run inversereserve demo --scenario no-effect
uv run inversereserve run --config configs/demo.json
uv run inversereserve reproduce
```

The demo executes a small controller episode without a browser, model, service,
or download. A no-effect commit is quarantined rather than repeated. Configured
runs write below `~/research/runs/InverseReserve/<run_id>/` by default. Use a new
run ID for a new experiment. `--resume` only returns a completed, checksum-verified
result; an interrupted GUI session must start from a fresh environment.

For actual browser experiments, restore the explicit resources described in
[RESOURCES](docs/RESOURCES.md), install the separate extras, and check the config:

```sh
uv sync --locked --extra browser --extra inference
uv run python -m playwright install chromium   # explicit optional download
uv run inversereserve doctor --config configs/miniwob.json
uv run inversereserve run --config configs/miniwob.json
```

The maintained MiniWoB adapter is a development integration. Its real browser and
GPU behavior has not been verified in this restored CPU environment. The offline
tests exercise contracts, controller behavior, resource validation and failure
paths. Installation does not download browser binaries, models or benchmark data.

Research scopes are explicit. `full`, `raw`, and `typed` expose the matched
confirmation controllers. `stack-reserve`, `single-active`, and `top-cleanup`
expose a separate capacity/control study. `task-reserve-single` and
`task-reserve-cleanup` expose the goal-equivalent task-reserve successor. These
scopes are not interchangeable experimental arms; see [ARCHITECTURE](docs/ARCHITECTURE.md).

`reproduce` verifies the **original** 360-episode evidence and rebuilds the
50,000-sample registered analysis using its original frozen code. New runs carry
new source identities and cannot stand in for that evidence. Preserved historical
instructions in `reproduce/` describe the old environment; current paths and
commands are in this README and [MIGRATION](docs/MIGRATION.md).

See [DEVELOPMENT](docs/DEVELOPMENT.md), [CONTRIBUTING](CONTRIBUTING.md),
[VALIDATION](docs/VALIDATION.md), and [resource catalogue](src/inversereserve/resource_catalog.json).
License: Apache-2.0. Publishing this local repository is a separate action.
