# Development

Use Python 3.12 and this repository's isolated `.venv`:

```sh
uv sync --locked
uv run ruff check src tests scripts examples
uv run ruff format --check src tests scripts examples
uv run mypy
uv run python scripts/check_structure.py
uv run pytest -q
uv run inversereserve reproduce
uv build
uv run python scripts/check_release.py
```

After initial dependency acquisition, sync/tests/CPU examples operate offline.
Browser and inference extras are explicit; ordinary checks never call a paid model
or remote service. Critical boundaries (resource resolution, config, episode API,
replay, artifact recovery, envelope admission, capacity and search state) receive
strict type checking. Existing research-specific JSON records retain explicit Any
at the untyped observation/analysis boundary.

Maintain module <=600, ordinary function <=120 lines and branch complexity <=15.
The few fixed metric/gate/schema declarations in STRUCTURE_EXCEPTIONS.json have
named reasons, test references and exact AST hashes. Editing one requires renewed
review; the checker does not grant a whole module or legacy directory exemption.

Run `scripts/export_public.py --target <new-directory>` only after updating and
reviewing PUBLIC_MANIFEST.json. Release checks install the wheel into a clean
environment and execute commands from outside the source directory. The manifest
is the reviewed public file set; local environments, full data, credentials and
private archives are not publication material.
