# Validation

Use the commands in [DEVELOPMENT.md](DEVELOPMENT.md) for the offline suite
and distribution checks.

| Check | Coverage |
| --- | --- |
| Main suite | 773 CPU cases, including the original 593 cases |
| Search comparisons | 29 quotient-search and 20 local-search cases |
| Controller comparisons | 32 controller/WebArena executions, including event order, state, calls and budgets |
| Study analysis | 27 metric populations, matched-v10 analysis, holdout and transfer declarations |
| Public boundaries | Resource precedence, malformed inputs, finite rewards, hashes, replay, failure journaling and completed-result reuse |
| Engineering checks | Ruff, 11 strict type boundaries and 600/120/15 structure limits |

`TEST_MIGRATION.json` maps original assertions and `MODULE_LAYOUT.json` maps
implementation ownership. `STRUCTURE_EXCEPTIONS.json` identifies 28 reviewed
declarations and schemas with tests and AST hashes. The duplicate-coordinate
termination regression is documented in [BEHAVIOR_CHANGES.md](BEHAVIOR_CHANGES.md).

## Evidence verification

The original scientific producer
`30300a63d3d92d62da0384c214f4896e2116502c` supplies 821 files and 360 episodes.
Reproduction uses the registered 50,000-sample analysis and preserves the
success counts: `raw` 45, `typed` 6 and `full` 120. See
[reproduction](../reproduce/README.md) for the procedure and study design.

## Distribution verification

Wheel checks inspect licenses and resources, import installed modules and
execute diagnostics, examples, configured runs, completed-result reuse and
reproduction outside the source tree. The sdist check uses a fresh locked
environment, runs the complete suite and compares rebuilt wheel contents.
Source-export checks verify `PUBLIC_MANIFEST.json`.

## Artifact restoration checks

Ten artifact restoration tests cover Unicode paths, missing and corrupt parts,
repeat execution, modified-file protection, upstream assets, optional
models and independent Git history with reference and link protection. The suite counts above include these cases. The restoration and
research-material checks for the distributed archive edition are recorded in the
[research archive](https://github.com/weixiubo/InverseReserve/releases/tag/research-artifacts-2026-10-17-r2).
