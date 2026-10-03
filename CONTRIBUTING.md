# Contributing

Follow the environment and validation commands in
[DEVELOPMENT.md](docs/DEVELOPMENT.md). Keep contracts and capacity arithmetic
independent of CLI parsing, model loading and filesystem configuration.
Changes to state, budgets, recovery or evidence handling should include a
regression scenario and preserve existing valid assertions.

Research changes specify their protocol and receive a distinct experiment
identity. Original populations, outcomes and evidence hashes remain attached
to their producer. Optional integrations validate their dependencies and
resource identities before execution.

`STRUCTURE_EXCEPTIONS.json` identifies reviewed protocol declarations and
their tests. Reassess the corresponding protocol and tests when changing an
exception. Reference implementations and scientific evidence are checked
against their original hashes.

Before export, review the public file set and update `PUBLIC_MANIFEST.json`.
Distribution checks inspect wheel contents, run installed commands and test
a source distribution in a fresh locked environment. Cache development
dependencies before running these offline checks.
