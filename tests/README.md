# tests/ - the test suite

**Mnemosyne's local gate**: `make check` (lint `ruff` + `pytest`) must be green
before any commit. The tests are filed by system **layer**.

## Layout
- **`ingest/`** - corpus acquisition & preparation (ingestion, chunking, library,
  taxonomy, triage).
- **`distillation/`** - the distillation arc (chapter parsing, distillation,
  finisher, judge, refinement).
- **`retrieval/`** - the RAG (stores, keyword / memory search, recall floor
  calibration).
- **`orchestration/`** - the orchestration engine and the soul (engine, production, proposer,
  agent loop, ops, runtime).
- **`identity/`** - the self-model and the skills (self-model, `describe`, skill and tool
  catalogues).
- **`platform/`** - the foundation (api/CoreApi, ports, adapters, secrets, human-layer
  journal).

At the **root** (cross-cutting, do not file away):
- **`test_invariants.py`** - the executable registry of the invariants described in
  [the architecture](../ARCHITECTURE.md).
- **`_invariants.py`** - the shared helper (exposes `REPO_ROOT` and the invariant
  utilities).

## Conventions
- Config in [`pyproject.toml`](../pyproject.toml): `pythonpath = ["system/lib",
  "tests"]` -> the `mnemosyne` package **and** `_invariants` are importable from
  any sub-folder.
- **No `__init__.py`**: test basenames are unique, the import happens by
  *prepend*.
- A test that must reach the repo root does so via **`REPO_ROOT`** (imported from
  `_invariants`), robust to depth - **never** via `Path(__file__).parent.parent`.

## Running
```sh
make check            # everything: lint + tests
uv run pytest tests/ingest      # a single layer
```
