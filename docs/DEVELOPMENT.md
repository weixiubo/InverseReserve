# Development

Use Python 3.12 and the repository's isolated `.venv`:

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
uv run python scripts/check_sdist.py
```

The core suite and CPU examples run offline after dependency installation.
Browser and inference dependencies are separate extras. Strict typing covers
resource resolution, configuration, episode interfaces, replay, artifact
recovery, admission, capacity and search state. Dynamic observation and
analysis records use explicit `Any` boundaries.

Maintained modules have a 600-line limit, functions a 120-line limit and McCabe
complexity a limit of 15. Named declaration exceptions include reasons,
test references and AST hashes in `STRUCTURE_EXCEPTIONS.json`.

Review and update `PUBLIC_MANIFEST.json` before running
`scripts/export_public.py --target PATH` with a new target directory. Release
checks execute installed wheels outside the source tree. The sdist check
installs a fresh locked environment, runs the full suite and compares rebuilt
wheel contents. Dependencies must be cached for offline distribution checks.
