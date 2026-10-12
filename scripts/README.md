# scripts/ - one-off utility scripts

**Dev tools and benchmarks, not engine building blocks** - to be told apart from
[`system/skills/`](../system/skills/README.md) (the executable production roles). Run
directly (`uv run python scripts/<script>.py`), never through a `Makefile` target.

## Contents
- `bench_context.py` - how far a model holds up in long context (needle-in-haystack) on the
  machine, without degrading quality.
- `bench_distillation.py` - compares several local models on the **same** distiller skill
  (record quality + speed), through the real governed stack.
- `bench_local_models.py` - lightweight comparison of local MLX models (load speed,
  tokens/s, raw output).
- `bench_tool_calling.py` - which local model can drive Mnemosyne's real agent loop
  (scored against the real tool-call parser).
- `migrate_to_content_identity.py` - one-shot migration to content identity (id = hash
  of the `.md`) ; reuses the existing vectors, dry-run by default.

## Cross-references
[`system/lib/README.md`](../system/lib/README.md)  -
[`oss_registry.md`](../system/config/oss_registry.md)
