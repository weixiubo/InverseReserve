# Confirmation evidence reproduction

```sh
uv run inversereserve reproduce
```

`python reproduce/verify.py` provides the repository entrypoint. The verifier
checks the registered protocol, original result hash, 360 claim-to-episode
bindings and scientific source from commit
`30300a63d3d92d62da0384c214f4896e2116502c`.

It reconstructs the final-grid analysis, including the registered
50,000-sample seed-cluster bootstrap and Holm comparisons, using the original
source. Floating-point comparisons allow a rounding tolerance of `1e-12`.
Verification operates offline on the supplied records.

## Evidence identity

`frozen/` contains the analysis inputs and producer modules.
`frozen_manifest.json` records their identities, including exact-byte
restoration records where backup transport changed text encoding or newlines.
Original recorded digests remain the verification reference.

## Study configuration

The final grid uses Qwen3.5-9B, six task families, 20 seeds and three
registered arms. Re-execution uses its recorded model snapshot, browser
dependencies, runtime audit and original runner. External source identities
are recorded in `external_frozen_sources`; all analysis modules required by
the offline verifier are included.

Current experiments use `inversereserve run --config` with explicit resource
paths. The capacity and goal-equivalent task-reserve studies have separate
protocol identities. See [architecture](../docs/ARCHITECTURE.md) and
[resources](../docs/RESOURCES.md) for those interfaces.

The current public edition omits recorded model-message bodies. Its integrity
indexes bind the published records; recorded statistical outcomes are retained.
