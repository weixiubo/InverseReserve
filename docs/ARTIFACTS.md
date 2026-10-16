# Research artifacts

This repository contains the maintained InverseReserve implementation. Its public
[research archive](https://github.com/weixiubo/InverseReserve/releases/tag/handoff-2026-10-15) contains the
research materials and their file-level checksums. The archive includes
recorded experiments, supporting inputs and historical source versions.

## Restore and use

Use Linux or WSL, with the checkout and material directory on the Linux
filesystem. Install Git, Python 3.12 and uv, then run:

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
uv run --no-sync pytest -q
```

No GitHub account is required. Every release part is required; the script
checks downloads before extraction and verifies restored paths, SHA-256,
permissions and symbolic links. Repeating restoration reuses verified files
and refuses to overwrite local modifications. `--offline` uses existing
verified downloads. Keep new work outside the immutable `snapshot/` tree.

`resources.json` and `activate.sh` bind the restored inputs and a fresh run
output directory. Resource prerequisites for new experiments remain listed
in [RESOURCES.md](RESOURCES.md). Frozen evidence verification reconstructs
recorded results; it does not rerun GPU inference or live platform studies.

## Material organization

- Git: maintained source, tests, dependency lock and development branch.
- `snapshot/`: retained datasets, original experiment records, databases,
  checkpoints, papers and historical source snapshots.
- `snapshot/historical-git/`, when present: standalone historical Git stores,
  original-to-public commit maps, branch identities and otherwise unreferenced
  source blobs. `handoff/history-index.json` identifies each store.
- `handoff/material-disposition.json`: resource sources and explicit content
  transformations. Separately collected third-party literature PDFs are excluded;
  project papers, references and bibliography metadata remain.

Historical stores that contained excluded full texts have new commit IDs.
Their commit maps preserve the correspondence to original scientific source
identities. Retained source blobs are unchanged. Clone the selected
`repository.git` into a separate directory to work on a historical version;
keep the snapshot itself unchanged. Original branch, index and tag metadata
are retained for provenance. Existing partial upstream vendor repositories
remain identified as such and can use their recorded public origins.

```sh
git clone /path/to/materials/snapshot/historical-git/git-NN/repository.git historical-work
```

Caches, virtual environments and rebuildable distributions are omitted.
Identical payloads are stored once in the release; historical paths that are
needed to interpret records remain represented in the file manifest. The
manifest contains 127,516 retained file entries.

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

## Verification records and archive scope

The release includes `verification.json`, `material-notes.json` and
`history-equivalence.json`. These record the checks performed on 2026-10-15,
source-version mappings and limitations of the historical inputs. Historical
shallow boundaries, normalized remote-reference names and reconstruction
commands are recorded in `history-equivalence.json`.
Directory resources may still be labelled `present_unverified` by `doctor`;
use the artifact verification command and the project's original evidence verifier
for their complete file-level checks.

`handoff/local-state/vendor-git-metadata.json` maps three original vendor
reflogs to their exact Git-backed copies under
`handoff/local-state/pre-diagnostic-vendor-metadata/`. These preserve the
pre-inspection metadata as well as the verified vendor snapshot.
