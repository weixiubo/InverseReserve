# InverseReserve

Stack-aware recovery-capacity enforcement for GUI agents. This repository keeps
the InverseReserve/PACT runtime, required predecessor contracts, matched controls
and scoped successor studies. The original `rcrps` imports remain supported.

```sh
uv venv --python 3.12
uv pip install -r requirements-dev.lock
uv pip install --no-deps -e .
.venv/bin/python examples/capacity_smoke.py
.venv/bin/python -m pytest -q
.venv/bin/python reproduce/verify.py
```

The example exercises reserve accounting without a model or browser. Offline
reproduction verifies immutable episode/claim hashes and rebuilds the recorded
final grid analysis. Full GUI/model reruns require the frozen source, protocol,
model and environment identified in `reproduce/README.md`. They are separate
from installation and do not reuse an adjacent project's interpreter.

See `docs/ARCHITECTURE.md` for module responsibilities. Public source is generated
from `PUBLIC_MANIFEST.json`; private submission/author facts, machine launchers,
original Git repositories and research notes live in the private archive.
