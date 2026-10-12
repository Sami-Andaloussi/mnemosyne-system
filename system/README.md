# system/ - the engine

**Everything that runs the system**: configuration, code, skills, logs, state. Distinct from
`knowledge/` (the material - sources and distillations) and from the top-level docs. Full layout in
the [root README](../README.md).

## Map
- [`config/`](config/README.md) - centralized declarative configuration: taxonomy, domains,
  policy, skill/tool registries, the OSS registry.
- [`lib/`](lib/README.md) - the code: the `mnemosyne` Python package, the engine.
- [`skills/`](skills/README.md) - skills = roles + executable methods.
- [`workflows/`](workflows/README.md) - orchestration skills that compose several skills;
  empty for now.
- `logs/` - generated append-only logs; its contents are ignored by Git.
- `state/` - persistent runtime state; empty by default and ignored by Git.
- [`golden/`](golden/README.md) - the quality-calibration golden set (RAG, fidelity, extraction).

## See also
[Root README](../README.md) . [`ARCHITECTURE.md`](../ARCHITECTURE.md) . [agent hooks](../.claude/hooks/README.md)
