# Resources and local configuration

Source and the project environment reside in the checkout. Data defaults to
`~/research/data/InverseReserve`, models to `~/research/models`, outputs to
`~/research/runs/InverseReserve` and external evidence to
`~/research/data/InverseReserve/evidence`.

Resolution precedence is command-line options, explicit run-config paths,
`INVERSERESERVE_*_DIR` environment variables, user JSON, then defaults.
Relative paths resolve from the configuration file that declares them.
User configuration uses `$XDG_CONFIG_HOME/research/InverseReserve.json`,
normally `~/.config/research/InverseReserve.json`;
`INVERSERESERVE_LOCAL_CONFIG` selects another file.

```json
{
  "paths": {"data": "/external/data", "models": "/external/models", "runs": "/external/runs"},
  "resources": {"miniwob-html": "{data}/miniwob/html"}
}
```

Catalog paths also accept `INVERSERESERVE_RESOURCE_<ID>`, with uppercase
letters and underscores replacing hyphens. Backend execution resolves the
explicit `options` values in the experiment configuration. Supported path
placeholders are `{data}`, `{models}`, `{runs}` and `{evidence}`.

## Replay inputs

External replay specifies `options.replay_file` and a matching `required_files`
entry, such as `{"path": "episode.json", "sha256": "<64 hex digits>"}`.
Preflight checks file presence, schemas and checksums before output creation.

## MiniWoB and local models

Browser execution requires `html/miniwob/<task>.html`, Chromium, browser
dependencies and a local model. The adapter records hashes of benchmark HTML
resources before starting. Browser dependency pins are BrowserGym 0.14.3,
Gymnasium 1.3.0 and Playwright 1.44.0.

The model's `resource-manifest.json` maps every visible model-relative file
to SHA-256, including `config.json` and weights. Use the recorded manifest
for an original snapshot; create a new manifest and run identity for a new
revision. Loading is local-only and keeps remote model code disabled.

The [resource catalog](../src/inversereserve/resource_catalog.json) records
sources, versions, locations and acquisition instructions. Directory presence
and checksum-verified identity are reported separately by `doctor`.

Resource terms: [MiniWoB](https://raw.githubusercontent.com/Farama-Foundation/miniwob-plusplus/main/LICENSE),
[BrowserGym](https://raw.githubusercontent.com/ServiceNow/BrowserGym/main/LICENSE)
and [Qwen3.5-9B](https://huggingface.co/Qwen/Qwen3.5-9B).
Original study execution uses its recorded model snapshot, runtime metadata
and protocol, described in the [reproduction guide](../reproduce/README.md).
