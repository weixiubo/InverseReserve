# Validation — 2026-10-02

## Executed successfully

- 763 CPU tests pass. All 593 baseline cases remain, represented by 520 original
  test functions before parametrization. Every original assert expression is
  unchanged. TEST_MIGRATION.json records the mapping; imports follow MODULE_LAYOUT.
- Original/current deterministic comparisons: 29 quotient searches, 20 local
  searches, 32 controller/WebArena executions, 27 study metric populations and
  matched-v10 analysis, plus holdout and transfer declaration/analysis checks.
  Controller comparisons include exact event ordering, state, calls, and budgets.
  A duplicate-coordinate search termination defect has a regression test and is
  explicitly described in BEHAVIOR_CHANGES.md.
- Resource precedence, invalid input and nonfinite rewards, missing/checksum-wrong
  resources, missing optional backends, bounded replay, partial-run refusal,
  completed-run reuse, failure journaling and tampered results are covered.
- Ruff lint/format, strict mypy on 11 boundaries and 600/120/15 structure checks.
  28 named declaration/schema exceptions are hash-bound and tied to tests;
  ordinary runtime orchestration has no blanket exception.
- Wheel and sdist license/resources checked. A separate basic environment imports
  every installed module and executes doctor/demo/run/resume/reproduce from an
  unrelated directory, with no optional model/browser dependency. No caller or
  user resource directories are created until explicit run.
- A manifest-controlled public export installs from uv.lock into a fresh .venv
  and runs the complete test suite. Public files, reference implementation fixtures,
  and proposed Git history are scanned for credential patterns. This bounded
  pattern scan is not proof that every possible private datum is detectable.

## Historical frozen results

The original scientific source 30300a63d3d92d62da0384c214f4896e2116502c verifies
821 original files and 360 episodes with 50,000 bootstrap samples. Success counts
remain raw 45, typed 6, full 120. All original reproduce/ bytes are unchanged.
The required original producer modules are regression fixtures with per-file SHA256 checks. New runs
use the maintained source identity and explicitly mark historical_evidence false.

## Resource-dependent checks outstanding

Real browser state, Chromium integration, GPU inference/model numerics, complete
external datasets, private WebArena/container studies and new sealed primary
experiments have not run here. Dependency resolution is not integration proof.
The runtime-cost replication module has no maintained callers and depends on an
unpublished script/private preregistration; it is removed from the current working tree,
not advertised as an installed study. ARCHIVED_MODULES.json records that decision.
No large resource was downloaded and no paid or remote experiment service was used.

The material-cleanup checks and current retained source list are documented in
MATERIALS.md and tests/reference/MANIFEST.json. Whole-source bundles are no longer
part of the current distribution. Scientific evidence identities are unchanged.

## Final distribution audit — 2026-10-03

The current suite passed 763 collected cases. The source distribution was unpacked into a new directory and installed in its own new locked environment.
All required test fixtures and helper files were present. The rebuilt wheel
payload matched the wheel built from the maintained checkout. Installed commands
ran outside the source directory with their declared resource and optional
dependency checks. Lint, formatting, types, structural limits and lock consistency
passed. CI now includes `check_sdist.py` after the ordinary build.

This verifies the maintained offline software and distribution boundaries.
The resource-dependent experiments listed above remain unverified; the test
result does not imply a new GPU experiment or a changed scientific conclusion.
