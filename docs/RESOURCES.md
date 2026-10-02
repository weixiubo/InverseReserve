# Resources and local configuration

Source, docs and tests live in `~/project/InverseReserve`; its `.venv` is disposable.
External data defaults to `~/research/data/InverseReserve`, models to
`~/research/models`, runs to `~/research/runs/InverseReserve`, and preserved history
to `~/research/data/<project>/evidence`. Nothing is created merely by importing the package.

Root precedence is command flags, explicit run-config paths, INVERSERESERVE_*_DIR
environment variables, user JSON, then defaults. Run-config relative paths are
relative to that config. User-config paths are relative to that user-config file.
User JSON is `$XDG_CONFIG_HOME/research/InverseReserve.json`, normally
`~/.config/research/InverseReserve.json`; INVERSERESERVE_LOCAL_CONFIG overrides it.

```json
{"paths":{"data":"/external/data","models":"/external/models","runs":"/external/runs"},
 "resources":{"miniwob-html":"{data}/miniwob/html"}}
```

Individual doctor catalogue entries also accept
INVERSERESERVE_RESOURCE_<UPPERCASE_ID_WITH_UNDERSCORES>. Experiment backend paths
are explicitly resolved from their `options` values; the catalogue is an inventory,
not a hidden mechanism for changing an experiment's inputs. `{data}`, `{models}`,
`{runs}` and `{evidence}` are the supported path placeholders.

An external replay uses `options.replay_file` and an exact corresponding
`required_files` entry `{ "path": "episode.json", "sha256": "<64 hex digits>" }`.
Missing files, invalid schemas and mismatched hashes fail before output creation.

The MiniWoB adapter requires the benchmark's `html/miniwob/<task>.html`, an explicitly
installed Chromium binary, browser extras and a local model. It records hashes of
all benchmark HTML resources before starting. The model directory requires a
`resource-manifest.json` object mapping every visible model file to its SHA256,
including `config.json` and weights. Restore the original manifest for historical
work. For a new snapshot, pin the revision, create a new manifest and a new run ID;
that creates a new experimental identity. Model loading uses local_files_only and
does not execute remote model code. No default GPU count is silently substituted
for an old registered runtime.

Resource catalogue entries distinguish present-but-unverified directories from
hash-verified files. Missing exact model/benchmark revisions and original runtime
audit remain recovery tasks. Historical virtual environments are investigation
material only; no binaries, site-package edits or machine launch scripts have been
reinstalled from them. No patch was required for the verified CPU feature set.

The browser pins (BrowserGym 0.14.3, Gymnasium 1.3.0, Playwright 1.44.0) come from
the preserved runtime metadata. The new lock resolves all declared extras; real
GPU/browser compatibility still requires an explicit integration run.

Resource sources/licenses: [MiniWoB MIT](https://raw.githubusercontent.com/Farama-Foundation/miniwob-plusplus/main/LICENSE),
[BrowserGym Apache-2.0](https://raw.githubusercontent.com/ServiceNow/BrowserGym/main/LICENSE),
[Qwen3.5-9B model card](https://huggingface.co/Qwen/Qwen3.5-9B).
Their resource licenses are independent of this package license.
