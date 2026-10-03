# Migration

| Previous entry | Current entry |
| --- | --- |
| `rcrps.*` | `inversereserve.*`; see `MODULE_LAYOUT.json` |
| `python 运行.py`, `requirements-dev.lock` | `uv sync --locked` and `inversereserve` |
| Version-specific study runners | Named methods with `run --config`; see `ENTRY_MIGRATION.json` |
| Source-local runs, sibling assets and fixed cache paths | Configured resource roots |
| `python reproduce/verify.py` | `inversereserve reproduce` |

Configured runs write `protocol.json`, `result.json` and `complete.json`;
failed startup records `failure.json`. `--resume` verifies completed results.
Interrupted GUI experiments require a fresh run ID and environment reset.

`TEST_MIGRATION.json` records test namespace and ownership changes.
`BEHAVIOR_CHANGES.md` describes duplicate-coordinate termination in preview
search. Original research evidence retains its producer identities, while
current runs record the source and inputs used for execution.
