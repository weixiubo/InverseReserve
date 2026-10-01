# Reproduction

`python reproduce/verify.py` runs offline. It verifies the registered protocol,
the original final-result hash, all 360 claim-to-episode bindings, and the frozen
source from scientific commit `30300a63d3d92d62da0384c214f4896e2116502c`.
It then rebuilds every final-grid analysis field, including the registered
50,000-sample seed-cluster bootstrap and Holm comparisons, using that frozen
source. Floating-point comparisons allow only 1e-12 rounding differences.

The immutable files live in `frozen/`, separately from maintained `src/`.
`frozen_manifest.json` records original and restored hashes. Where backup text
transport changed BOM/newlines, bytes are restored only when they exactly match
the existing recorded digest. Original backups are preserved privately. No old
source or evidence manifest is rewritten to refer to this refactor.

The final grid uses Qwen3.5-9B, six task families, 20 seeds and three registered
arms. Full reruns need its exact model snapshot, MiniWoB/browser dependencies,
the original runtime audit and frozen runner. Those are external resources;
the local backup's `PROJECT_ASSETS.json` and runtime audit are preserved privately
as historical records. The current lightweight lock supports offline analysis
and unit tests, not an assertion that the old GPU runtime has been recreated.

Later v18-v22 capacity/control studies retain separate protocol identities.
Historical RPS, private author/submission records and obsolete remote operation
scripts are outside this public release. Required older contract/controller
modules stay until their actual consumers are migrated.

The hash-bound original launch script contains a private server model path and
is retained in the private archive (its digest appears in external_frozen_sources).
All frozen analysis modules needed by the offline verifier are included.
Current launchers accept --model-path; their portable fallback is
~/.cache/inversereserve/Qwen3.5-9B. Supply the actual downloaded snapshot explicitly.
No model download or GPU experiment is part of this cleanup.
