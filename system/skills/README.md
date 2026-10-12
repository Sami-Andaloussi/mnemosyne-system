# system/skills/ - skills = roles + executable methods

**A skill = a bounded role with its method**, invoked through a dedicated `make` target - never a
prompt rewritten by hand for each agent (local or frontier). Distinct from
[`system/workflows/`](../workflows/README.md), which will orchestrate several skills together.

## Skills present
- [`distillateur/`](distillateur/SKILL.md) - distills a document into a 3-part record (identity
  P1, neutral description P2, verbatim content P3) in `knowledge/distilled/` (`make distill`).
- [`finisseur/`](finisseur/SKILL.md) - polishes the readability of an already distilled record
  (titles, P2 prose) without ever touching the P3 verbatim (`make finish`).
- [`juge/`](juge/SKILL.md) - verifies all of `knowledge/distilled/` against `knowledge/raw/`
  without trusting the producer of the records (`make judge`).
- [`skill-creator/`](skill-creator/SKILL.md) - creates/audits a new skill according to the common
  anatomy (`make skill-new`, `skill-audit`, `skill-emit`).
- [`planificateur/`](planificateur/SKILL.md) - makes a already-conformant plan **be born** (a
  FOLDER: door + arcs, D166) and **emits** its literal structure to a host agent, replayed from the
  code and never hand-copied (`make plan-nouveau`, `make plan-emit`).

## Anatomy of a skill
- `SKILL.md` - frontmatter (`name`, `description`) + the role in prose, what the skill guarantees.
- an orchestration script (e.g. `distill_book.py`) - a **thin** adapter; the real body (the
  logic) lives in `system/lib/mnemosyne/` (e.g. `production.distillation.Distillateur`).
- a `*_emit.py` seam (e.g. `emit_prompts.py`) - prints the EXACT contract (prompt + schema)
  from that same code, so that a frontier host (Codex...) applies byte for byte the same
  work as the local model; never a hand copy (anti-drift).
- `skill-creator/` additionally has [`references/`](skill-creator/references) (anatomy, anti-drift,
  tests) - material for creating a new skill.

## Life cycle
`DRAFT -> AUDITED -> ACTIVE`: only `ACTIVE` may run, and the corresponding entry lives in
[`system/config/skills.toml`](../config/skills.toml) (protected registry, deny-by-default).

## Cross-references
[`skills.toml`](../config/skills.toml)  -  [`system/workflows/README.md`](../workflows/README.md)  -
[`Makefile`](../../Makefile)
