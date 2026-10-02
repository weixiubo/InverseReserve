# Contributing

Start with DEVELOPMENT.md. Keep core contracts and capacity logic independent of
CLI, model loading and machine paths. Add a regression scenario for changed state,
budget, recovery or evidence behavior and preserve existing effective assertions.

Research changes must name their scope and create a new experiment identity.
Retain failed outcomes and original evidence. Never relabel historical hashes,
replace a sealed population after observing results, or present a CPU fixture as
a verified live GPU/browser experiment. Optional integrations should fail with a
specific resource/dependency diagnosis before an experiment starts.

Changes to fixed research declarations require review of their corresponding
protocol and tests before updating STRUCTURE_EXCEPTIONS.json. Changes to maintained
source do not modify reproduce/frozen or the original baseline snapshot.

## Source distribution validation

After `uv build`, run `uv run --no-sync python scripts/check_sdist.py`.
It checks that the source distribution contains every declared test, fixture,
helper and example, creates a fresh environment from its own lock, runs the full
suite, and verifies that rebuilding its wheel preserves the distribution payload.
Dependencies must already be cached by the normal locked development setup;
this check runs offline and removes its temporary environment afterward.
