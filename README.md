# InverseReserve

InverseReserve implements typed GUI transactions with explicit recovery
capacity and freshly grounded commit certificates. The `inversereserve`
package separates action contracts, transaction state, capacity accounting,
controllers and environment adapters.

## Installation and examples

Use Python 3.12 and the repository's uv environment:

```sh
uv sync --locked
uv run inversereserve doctor
uv run inversereserve demo
uv run inversereserve demo --scenario no-effect
uv run inversereserve run --config configs/demo.json
uv run inversereserve reproduce
```

The demo executes a deterministic controller episode. The `no-effect` scenario
demonstrates quarantine of a commit without an observed effect. Configured
runs write to `~/research/runs/InverseReserve/<run_id>/` by default.

## Browser experiments

Supply the benchmark and model resources described in
[RESOURCES.md](docs/RESOURCES.md), then install the browser and inference extras:

```sh
uv sync --locked --extra browser --extra inference
uv run python -m playwright install chromium
uv run inversereserve doctor --config configs/miniwob.json
uv run inversereserve run --config configs/miniwob.json
```

The MiniWoB adapter uses explicit task HTML, a Chromium installation and a
local model checkpoint with a file manifest. `doctor --config` checks these
inputs before execution. Assign a distinct run ID to each experiment.
`--resume` reads a completed result after verifying its identity and checksum;
an interrupted GUI session starts with a new run ID and a fresh environment.

## Research scope

| Methods | Study |
| --- | --- |
| `full`, `raw`, `typed` | Matched confirmation controllers |
| `stack-reserve`, `single-active`, `top-cleanup` | Capacity and control |
| `task-reserve-single`, `task-reserve-cleanup` | Goal-equivalent task reservation |

Each study has its own protocol, budget and controller identity. See
[architecture](docs/ARCHITECTURE.md) for their relationships.

`reproduce` verifies the original 360-episode confirmation evidence and
reconstructs its registered 50,000-sample analysis with the original producer
code. The [reproduction guide](reproduce/README.md) specifies the inputs and
verification procedure. New experiments record their own source identities.

## Documentation

- [Development](docs/DEVELOPMENT.md) and [contributing](CONTRIBUTING.md)
- [Migration](docs/MIGRATION.md) and [behavior changes](docs/BEHAVIOR_CHANGES.md)
- [Validation](docs/VALIDATION.md), [repository layout](docs/MATERIALS.md) and [third-party notices](THIRD_PARTY.md)

Project code is licensed under Apache-2.0.
