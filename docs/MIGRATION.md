# Migration

| Previous entry | Maintained replacement |
|---|---|
| `rcrps.*` | `inversereserve.*`; MODULE_LAYOUT.json gives each owner |
| `python 运行.py`, installation through requirements-dev.lock | `uv sync --locked`, `inversereserve` |
| source-bound c*/version-number runner scripts | explicit named method and `run --config`; ENTRY_MIGRATION.json records each original and reason |
| local relative `runs/`, external sibling assets or old cache paths | configured research resource roots |
| offline `python reproduce/verify.py` | installed `inversereserve reproduce` (same original bytes/verifier) |

Twenty-one source-bound historical scripts and the old wrapper/requirements lock
were removed after preserving the complete baseline Git source snapshot under
`reproduce/maintainer-baseline/`. They are not interchangeable with current
experiments: old pre-registrations bind source digests and prior sealed outcomes.
To inspect or rerun a historical entry, verify SOURCE.json and extract the snapshot
into a separate archive work directory; supply its own pinned resources. Never
rewrite an old source digest to make new code pass a frozen protocol gate.

Current runs write protocol.json (new source identity and resources), result.json,
and complete.json (result hash). Failed startup retains failure.json. A complete
verified run can be reused with `--resume`; incomplete GUI runs require a new ID
and reset environment, preserving the old record for diagnosis.

The intentional duplicate-coordinate search termination fix is documented in
BEHAVIOR_CHANGES.md. All original test assertions remain, with namespace/owner
changes mapped in TEST_MIGRATION.json. Old source files and evidence remain byte
preserved rather than formatted or repaired during this refactor.

The standalone runtime-cost replication module has no maintained callers and loads an unpublished latency script from a source-tree path. Its original bytes remain in the maintainer baseline archive; see ARCHIVED_MODULES.json. New installation does not advertise that private protocol as executable.
