# system/config/ - centralized declarative configuration

**One source of truth per subject.** Everything that governs Mnemosyne is declared here, never
hard-coded in the code; nothing executes here, everything is read here.

## Contents
- [`taxonomy.toml`](taxonomy.toml) - library shelving: source of truth for the
  `domaine -> (Famille, Groupe)` mapping. Adding a domain = one line here, and nowhere else.
- [`domains.toml`](domains.toml) - human vocabulary of the domains (labels, FR/EN aliases, MOC
  groups); **subordinate** to `policy.toml`, the only authority for RAG access (D72).
- [`policy.toml`](policy.toml) - the policies: authorized `knowledge` domains, `recall_floor`,
  resource bounds. Protected zone read by the Guard, read-only for any agent (D89).
- [`skills.toml`](skills.toml) - the skills registry: only the `ACTIVE` state may run.
  Adding/activating an entry is a privileged human gesture (D37/D102).
- [`tools.toml`](tools.toml) - allow-list of the tools/MCP authorized by the Guard, deny-by-default
  (D73).
- [`models.toml`](models.toml) - the **basket of LOCAL models** (C9): the single written answer to
  "which models do I have?". **There is no default model, and that is deliberate** - a decoding that
  names none REFUSES and prints the basket (`MODELE=<id>`, `MODELE_VISION=<id>` for the eye).
  Declaration **checked against disk in both directions** on every call: declared-absent,
  present-undeclared and derived weight are three named refusals. To see it: `make modeles`.
  WARNING: No quality or speed field is written there until a bench has measured it.
- [`oss_registry.md`](oss_registry.md) - Mnemosyne's own OSS building blocks (≠ the dev tooling):
  one line per swap-able socket, license, reuse mode, wiring point.

## Cross-references
[`system/README.md`](../README.md)  -  [root README](../../README.md)
