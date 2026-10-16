# Research artifacts

The [research archive](https://github.com/weixiubo/InverseReserve/releases/tag/research-artifacts-2026-10-16)
contains recorded experiments, supporting inputs, manuscripts, figures and
source versions for InverseReserve. Maintained source and installation instructions
are available on the main branch.

## Download and verification

Use Git, Python 3.12 and uv on Linux or WSL. The destination must be on the
Linux filesystem. Use an empty destination when selecting a different archive
edition; repeated restoration of the same edition reuses verified files.

```sh
git clone https://github.com/weixiubo/InverseReserve.git
cd InverseReserve
python3 scripts/handoff.py restore --root "$PWD/../InverseReserve-materials"
python3 scripts/handoff.py verify --root "$PWD/../InverseReserve-materials"
source "../InverseReserve-materials/activate.sh"
uv sync --locked
uv run --no-sync inversereserve doctor
uv run --no-sync inversereserve demo
uv run --no-sync inversereserve reproduce
```

Downloads require no GitHub account. All material parts are required. The
client verifies each download before extraction, then checks paths, sizes,
SHA-256 identities, file permissions and symbolic links. Existing modified
files or source-history references cause an error. `--offline` uses a complete
set of previously verified downloads.

## Archive organization

| Location | Contents |
| --- | --- |
| `snapshot/data/` | Recorded research inputs and resource metadata |
| `snapshot/runs/` | Experiment records |
| `snapshot/archive-original*/` | Historical research materials and manuscript sources |
| `snapshot/source-snapshot/` | A recorded implementation snapshot |
| `snapshot/source-history/research/` | Research source history and revision correspondence |
| `snapshot/source-history/implementation/` | Maintained implementation history and revision correspondence |
| `resources.json`, `activate.sh` | Configuration for restored inputs and separate run outputs |

The file manifest contains 121,225 retained file entries.
Archive file identities are specified in `materials.json.gz`. The maintained
source export is specified separately in `PUBLIC_MANIFEST.json`.

## Source versions

Restoration creates independent bare repositories from the source bundles.
Each repository is checked for complete object storage, its recorded branch
and tag references, and its default branch. Source revision maps identify the
correspondence between recorded versions and the distributed source editions.

```sh
git clone ../InverseReserve-materials/snapshot/source-history/research/repository.git historical-source
```

The source bundles are independent of the machine on which the experiments
were recorded. [history-index.json](../handoff/history-index.json) lists the
repositories and revision maps. Recorded experiment inputs, measurements and
signed evidence retain their original bytes. The restored snapshot is read-only
research material; new experiments use separate source and output directories.

## Resource configuration and evidence

`resources.json` and `activate.sh` select restored inputs and a separate output
directory. [RESOURCES.md](RESOURCES.md) specifies additional model, browser,
emulator and service requirements. The reproduction command checks recorded
evidence and reconstructs the associated analysis; it does not rerun the full
GPU or live-service experiment matrix.

## Optional model and historical environment

The UI-Venus-1.5-2B weight is an unchanged public upstream model, pinned by
revision and SHA-256. It is omitted from the large material archive. To
restore and verify it in its historical location as well, run:

```sh
python3 scripts/handoff.py restore --root "$PWD/../InverseReserve-materials" --with-models
python3 scripts/handoff.py verify --root "$PWD/../InverseReserve-materials" --with-models
```

This optional download is approximately 4.9 GB and comes directly from
Hugging Face. The archived 8.3 GB installed-package tar is replaced by
`snapshot/environment-recovery/`: exact package metadata, per-file RECORD
checks and preserved modified or unrecorded files. Use the maintained uv
lock for development. The historical mixed CUDA installation is documented
separately to identify the original experiment environment.

## Verification scope

The release provides file-level integrity indexes and a verification record.
Software tests, source-history checks and evidence reproduction have distinct
purposes. Their outcomes do not change the recorded scientific conclusions.
Directory presence alone is reported as `present_unverified` by `doctor`;
the artifact verifier performs the complete file-level checks.

`snapshot/source-history/bundle-references.json` maps the recorded transfer-bundle
references to the standalone research history.
