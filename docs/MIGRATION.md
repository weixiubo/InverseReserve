# Migration

| Previous entry | Maintained replacement |
|---|---|
| `rcrps.*` | `inversereserve.*`; MODULE_LAYOUT.json gives each owner |
| `python 运行.py`, installation through requirements-dev.lock | `uv sync --locked`, `inversereserve` |
| source-bound c*/version-number runner scripts | explicit named method and `run --config`; ENTRY_MIGRATION.json records each original and reason |
| local relative `runs/`, external sibling assets or old cache paths | configured research resource roots |
| offline `python reproduce/verify.py` | installed `inversereserve reproduce` (same original bytes/verifier) |

Unused source-bound runner scripts, obsolete wrappers and the standalone
runtime-cost module with an unpublished private caller are removed from the
working tree. `ENTRY_MIGRATION.json` records supported replacements.
Regression tests compare maintained search/controller/protocol behavior with
only the required producer modules in `tests/reference`.

Current runs write protocol.json, result.json and complete.json; failed startup
retains failure.json. Verified completed runs support `--resume`. Incomplete GUI
runs require a fresh run ID and environment reset.

The intentional duplicate-coordinate termination fix is documented in
BEHAVIOR_CHANGES.md. TEST_MIGRATION.json records namespace and ownership changes;
all original valid assertions remain. The immutable scientific evidence keeps
its original source identities, independently of current implementations.

See [MATERIALS.md](MATERIALS.md) for material ownership and deletion rules.
