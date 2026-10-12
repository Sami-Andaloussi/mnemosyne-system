---
name: public-mirror
description: >
  Keeps the public, sanitized, English GitHub mirror of this repo
  (projects/mnemosyne/mnemosyne-github, pushed to github.com/Sami-Andaloussi/mnemosyne-system) in sync
  with the private engine, cheaply and incrementally. Use it whenever the private repo has moved
  on and the public mirror needs to catch up. Designed to be handed to ANY capable LLM with repo
  access and zero extra briefing (D174) — see `make public-mirror-emit`.
task_class: atomic
sensitivity_max: sensible
version: "1.2"
id: public-mirror
date: 2026-08-18
---

# Skill: public-mirror (D174 - any LLM host, zero extra briefing)

The operator wants to show Mnemosyne's engineering on their own GitHub without exposing anything
personal, and without re-explaining the job from scratch every time the private repo moves on. This
skill is the standing answer: a deterministic diff (never a full rescan), a fixed scope manifest, a
small bounded sanitization contract per changed file, and a fail-closed scan before anything is
committed - never a push, ever, without a human's explicit go-ahead each time.

## When to use it
The operator (or any LLM given access to the repo) wants to bring the public mirror up to date
after the private repo has moved on. Never automatic, never on a plain commit - an explicit
gesture ("update the public GitHub").

## How to invoke it
```bash
make public-mirror              # deterministic plan: what changed, in/out of scope
make public-mirror-verify       # secret + personal-identity scan on the export -- before any commit
make public-mirror-mark-synced  # after a successful local commit in the export: advances the marker
make public-mirror-emit         # prints the FULL, self-contained CONTRACT, for any LLM
```
The full contract (scope + the per-file sanitization checklist + the steps) lives **only** in the
code (`system/lib/mnemosyne/production/public_mirror.py`) and is emitted via
`make public-mirror-emit` - never copied here (D163: the address, never the copy).

## What it GUARANTEES - by construction, not by trust (D100)
- **Never an automatic push.** The skill prepares and commits locally in the export repo; the
  `git push` stays an explicit human gesture, every time - neither this skill nor an agent ever
  does it on its own.
- **Always from the committed state, never the raw disk.** `git show HEAD:<path>` / `git archive`
  - because some of this repo's config files carry personal local edits (skip-worktree) that a raw
  copy would leak.
- **Verification independent of production.** `public-mirror-verify` is a pure function
  (`scan_for_leaks`), separate from whatever model did the translation/sanitization - a secret or
  an identifying term that slips through a model call is still caught here.
- **A new file in a sensitive area (internal governance) is neither assumed included nor assumed
  excluded by a name pattern** - the scope is an explicit list, frozen at the last real
  measurement; a new file that is not on it is included by default and shows up in plain sight in
  the plan, for a human to see before it ever ships.
- **Coverage verified, not just content.** `public-mirror-verify` recomputes the plan and compares
  it to the export's working tree (`git status`): any in-scope path never touched is listed
  explicitly (`uncovered_in_scope_paths`) and blocks the commit just like a leak would. Lesson from
  the first real trial (2026-08-19): an agent processed 35 of 413 planned paths without ever
  flagging it - its own report ("verify clean, 13 tests pass") was true and still misleading,
  because nothing at the time checked COVERAGE, only the quality of whatever had been touched.
- **Scope verified in BOTH directions.** `unexpected_touched_paths` mirrors the coverage check: any
  touched path that is NOT in the plan also blocks the commit. Lesson from the second real trial
  (2026-08-19, same day): an agent swept an entire folder instead of the plan's exact list,
  writing 48 internal-governance files denylisted from the export (~7,850 lines, still in French)
  - zero match against the content scanner (no secret, no personal identity named), and entirely
  absent from its own final report.
- **The export must still IMPORT.** `export_import_smoke_test` attempts `import mnemosyne` against
  the export's current working tree and blocks the commit if it fails. Same trial (2026-08-19): a
  translation pass did something like a blind substring replacement ("colle" -> "adapter"), which
  also hit "collections" along the way, producing `adapterctions.abc` - syntactically valid, so
  invisible at compile time, but it broke the import of the WHOLE package and therefore all 78
  test files in the export at collection time.

## Under the hood (the body governs - D70)
- Home: `mnemosyne.production.public_mirror` - the scope (`INCLUDE_ROOTS`, the `EXCLUDE_*`
  denylists, `DOCS_ALLOWLIST`), the sanitization contract (`SANITIZE_CHECKLIST`), the pure
  classification (`is_in_scope`, `classify_changed_paths`), the pure scan (`scan_for_leaks`, which
  reuses `mnemosyne.guard.redact.redact_sensitive_text` for secrets and adds a literal denylist
  for the operator's identity), and the orchestration (`run`, `verify_export`, `mark_synced`).
- Adapter: `system/skills/public-mirror/public-mirror_run.py` (dispatches `plan` / `verify` /
  `mark-synced`). Emission seam: `public-mirror_emit.py`. Lock-in test:
  `tests/test_public_mirror.py`.
- Sync state: `system/state/public_mirror_sync.json` (gitignored, like the rest of
  `system/state/`) - the last synced source commit; absent = first sync, the whole scope is
  considered new.

## State (activation cycle D37)
Body + adapter + `-emit` seam + test lock: built, tested (`make test` -> 23/23 on
`tests/test_public_mirror.py` ; `make skill-audit DIR="system/skills/public-mirror"` ->
`ok=True`). Hardened TWICE on 2026-08-19, each time after a real trial was rejected: (1)
anti-scanner-gaming + example/output pair consistency + mechanical coverage check
(`uncovered_in_scope_paths`); (2) after a SECOND trial still let 48 internal-governance files out
of scope through and broke the package import via a blind substring replacement - reverse scope
check (`unexpected_touched_paths`) + an import smoke test (`export_import_smoke_test`) + rule 9
against blind find-and-replace. Two real trials, two rejections, two separate hardening passes -
neither was ever committed. Formal activation DRAFT -> AUDITED -> ACTIVE: requires a **separate**
auditor (D39-6) and **the operator's own gesture** (D37), like every skill in this repo - not yet
crossed.

## D36 anatomy (standard floor - six sections)

### Role
The agent becomes **the public mirror's guardian**: it decides WHAT changed and WHAT to do with it
within the already-fixed scope (the manifest), never whether or WHEN to publish - that stays the
operator's gesture.

### Method
`make public-mirror` replays a `git diff` since the last marker and classifies each path (CODE,
deterministic, no model); for each in-scope path, a bounded model call follows
`SANITIZE_CHECKLIST` (translation + redaction, never a rewrite, never a scanner workaround - rule
7, never a blind substring replacement - rule 9) and writes the replacement into the export;
`make public-mirror-verify` replays FOUR checks independent of that model: `scan_for_leaks`
(secret / the operator's identity), `uncovered_in_scope_paths` (a plan path never touched),
`unexpected_touched_paths` (a touched path outside the plan - a whole denylisted folder swept),
and `export_import_smoke_test` (`import mnemosyne` fails against the working tree - a code
corruption that neither content nor coverage can see) - all four block the local commit;
`make public-mirror-mark-synced` advances the marker ONLY after a successful local commit. Detail
above under "How to invoke it" and "What it GUARANTEES".

### Inputs -> Outputs
Input: this repo's current state (HEAD) and the last sync marker. Output of `public-mirror`: a
printed plan (nothing written). Output of the sanitization work (outside this skill's own code,
done by the model that follows the emitted contract): files written into
`projects/mnemosyne/mnemosyne-github`. Output of `public-mirror-verify`: a list of findings
(empty = clean) and a non-zero exit code if not empty.

### When to FLAG
`public-mirror-verify` REFUSES (exit code 1, nothing committed) as soon as ONE of the four checks
finds something: a secret or an identifying term for the operator in the export tree; a plan path
with no change in the working tree (silently incomplete coverage); a touched path outside the plan
(scope overrun - a whole denylisted folder swept); or `import mnemosyne` failing against the
export (code corruption invisible to the other three checks). All four lessons come from the first
two real trials (2026-08-19) - see "What it GUARANTEES". A new path in a finely-denylisted area
(production/runtime/skills governance) that matches no known entry is included by default BUT
printed explicitly in the plan - the flag is visual, not an automatic block. No step in this skill
ever pushes to the public remote.

### Validation
`make test` (23 pure unit tests on `is_in_scope` / `classify_changed_paths` / `scan_for_leaks` /
`parse_git_status_paths` / `paths_not_yet_touched` / `paths_outside_scope` / the content of
`SANITIZE_CHECKLIST`, no dependency on the repo's current state) + `make skill-audit
DIR="system/skills/public-mirror"` (mechanical anatomy check). `export_import_smoke_test` is NOT
covered by these unit tests (impure, needs a real export on disk) - its only proof to date is the
real usage on 2026-08-19. Neither `make test` nor `skill-audit` judges the QUALITY of the
sanitization work produced by a model - that stays a separate human auditor (D39-6).

### Logs
No `CoreApi` surface wired to date - `public-mirror` / `public-mirror-verify` /
`public-mirror-emit` are CLI tools, like `skill-new`/`skill-emit`/`skill-audit`. **Accepted gap**
(D36 calls for Logs; to close if this skill becomes an automated production path).
