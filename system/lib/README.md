# system/lib/ - the code: the `mnemosyne` package

**The Mnemosyne engine**, in ports/adapters (hexagonal) architecture: the rest of the
system talks to a **port** (abstract contract), never to a concrete engine; every OSS brick
plugs in behind its port without touching the callers (D7/D26/D98, D113). Package entry
point: `mnemosyne/__init__.py`.

## Real sub-packages
- [`ports/`](mnemosyne/ports) - the swappable contracts ("sockets"): Guard, GraphStore,
  Embedder, VectorIndex, Runner, Sandbox, ToolPlugin, Store, Backup, Observability,
  Classifier, Scheduler, Skill I/O (LOT 1).
- [`guard/`](mnemosyne/guard) - the Guard: deterministic reference monitor, judge agent (it
  can only RAISE caution, never lower it), secrets broker, fail-closed resource bounds
  (D89/D73, D91/D100).
- [`ingest/`](mnemosyne/ingest) - the entry door: sensitivity classifier (D101), write/read
  router, benne, triage, sources (docling/OCR/whisper).
- [`stores/`](mnemosyne/stores) - the 3 memory stores (documentary truth `.md`/git,
  living graph, vector index) + integrity, reconciliation, locks.
- [`runtime/`](mnemosyne/runtime) - the engine room: local model runner, engine,
  snapshots, compaction, `describe`, rendering.
- [`agents/`](mnemosyne/agents) - multi-agent glue (Pydantic AI) that can **never**
  reach a model or a tool by bypassing the Guard (D93/D100).
- [`tools/`](mnemosyne/tools) - governed tool execution + OS sandbox (Seatbelt / microVM),
  deny-by-default allow-list (D114-(5)).
- [`production/`](mnemosyne/production) - the output layer: distillation, judge, finisher,
  skills, memory, proposer, projects - every privileged transition goes through a human gesture
  + a distinct verifier (D75/D100-6).
- [`api/`](mnemosyne/api) - `CoreApi`, the single headless facade: every caller (UI included)
  only ever talks to the Guard, never directly to the models or the stores (D89, D119).
- [`config.py`](mnemosyne/config.py) - loader turning `policy.toml` into a frozen `Policy`
  (frozen dataclass), read by the Guard at every boundary.

## See also
[`oss_registry.md`](../config/oss_registry.md) (default OSS brick behind each port)  -
[`system/skills/README.md`](../skills/README.md) (the skills call this code)  -
[`tests/`](../../tests) (the locks)
