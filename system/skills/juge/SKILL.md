---
name: juge
description: >
  Verifies ALL of knowledge/distilled/ against knowledge/raw/ WITHOUT trusting the model that produced
  the fiches (local or frontier/Codex). Replays every fiche through the repo's barriers (verbatim floor
  + source-quality gate) and returns a tally: which fiches are OK, which ones are empty templates /
  paraphrased / malformed and to be re-distilled, which books are still missing. To be run after a
  distillation pass (a Codex pass above all) to catch the garbage before relying on it.
task_class: atomic
sensitivity_max: sensible
version: "1.0"
id: juge
date: YYYY-MM-DD
---

# Skill : juge (D75 / D100 / D85 - producer != verifier)

The net that embodies **"we trust NO model, Codex included"**. A fiche can come out of the local
model (already floor-filtered) OR of a frontier agent that has **no** barrier at production - it
can return an **empty template** (every chapter `(section)`, generic descriptions, zero verbatim) or
**paraphrase** P3 while believing it is doing the right thing. The juge replays every fiche through the SAME repo
barriers and returns a standardized verdict. It **writes nothing** (neither raw nor fiche): it observes and flags (D85).

## How to invoke it - two forms, a single scale
```bash
make judge                                                       # the BATCH: the whole shelf
make verbatim-check FICHE="knowledge/distilled/<dom>/<book>.md"  # ONE fiche, print-only
```
`make judge` walks `knowledge/raw/`, looks at the MIRROR fiche of each book in `knowledge/distilled/`,
judges it, prints a tally, and writes `system/logs/judge_report.md` (the machine list of the fiches to re-process).

**`make verbatim-check` is the same juge, targeted.** It calls `judge_fiche` - not a second scale - and it
writes **nothing** (verified by fingerprinting the whole repo, `tests/distillation/test_verbatim_check.py`). It
exists because the batch cannot answer "does the fiche I have just written hold?". A fiche
`ok` or `flagged` appears neither on screen nor in the report. And on top of that it prints what the juge
computes then **throws away**: the passages the floor rejected, in the clear, to be re-copied from the source.
Output: `VERDICT: PASSED` / `VERDICT: REJECTED` ; exit code 0 = passed, anything else = must not enter.

Two departures from the "all of `raw/`", which are NOT of the same nature:
- **The non-corpus** (`README*` / `_intake` - `is_non_corpus`, `judge_library.py:42-43`) are **really
  skipped**: they are housekeeping docs, never judged.
- **The Tooling family** (`:45-52`) is **not** excluded from the walk: it is only **exempted from the
  `missing` verdict** (the veille is already a standalone synthesis, not a source to distil). A Tooling raw
  **that has a fiche is very much judged** and comes out in the tally with a real verdict.

So: a "missing" in the tally is never a non-corpus nor a Tooling - but "Tooling" is not
a synonym for "invisible to the juge".

## What `ok` means (and does NOT mean)
`ok` = **P3 FAITHFUL and the book is COVERED** (the passages are the source's real words, spread over
enough chapters). The juge judges **NEITHER** the P2 synthesis prose **NOR** the finesse of the chapter
split - that one is the finisseur's job. `ok` = "it can be relied on for substance", not "it is perfect".

## The verdicts (per fiche)
- **ok** - P3 faithful + covered (see above).
- **hollow** - empty template: placeholder titles/content, no passage produced at all (the FORM, not the substance).
  *The failure mode of the 1st Codex pass.*
- **thin** - under-distilled: faithful but a STUB (too little verbatim, or most chapters empty -
  e.g. a book reduced to its copyright page, or failed chunks).
- **paraphrased** - the fiche claims passages, but < 80% survive the floor (P3 paraphrased/invented).
- **malformed** - escaped `\n`, no frontmatter, no chapter: invalid fiche markdown.
- **flagged** - the fiche IS a `source-unusable` flag (expected if the source really is rotten; the juge
  re-tests the source and reports a possible false positive -> `make distill ... FORCE=1`).
- **missing** - the raw book does not have a fiche yet (to be distilled).
- **raw_missing** - fiche with no mirror raw (impossible to verify). The juge also lists the ORPHAN
  fiches (in distilled/ with no mirror raw/).

**+ an axis SEPARATE from the verdicts, printed in the tally: "P2 template"** (`n_templated`) - how many
descriptions are a **mechanical template** (not synthesized). It is **not** a verdict and it does **not
affect** `ok`: P3 fidelity can be perfect with a lazy P2 layer. It is the finisseur that answers
that one, not a re-distillation.

## Under the hood (the body governs - D70)
- Verdict of ONE fiche: `mnemosyne.production.judge_fiche(fiche_text, raw_text) -> FicheVerdict` (pure,
  reuses `keep_verbatim` + `assess_source_quality` - the guarantee is in the code, not in trust).
- Library orchestration (this folder): `judge_library.py` - mirror walk + tally + report.
- Tests: `tests/distillation/test_juge.py`.

## Status (activation cycle D37)
Built + tested + audited. Formal activation DRAFT -> AUDITED -> ACTIVE = distinct auditor (D39-6) +
operator gesture (D37).

## D36 anatomy (standard floor - six sections)

### Role
The agent becomes **the juge**: a verifier that trusts NO producer (local model
or frontier agent) and returns a standardized verdict, without ever writing or correcting anything itself.

### Method
Replays, fiche by fiche, the SAME deterministic barriers as production (`keep_verbatim`,
`assess_source_quality`) via `judge_fiche` (pure CODE, no model judgement); aggregates into a
library tally (CODE, `judge_library.py`). Detail in "How to invoke it" above.

### Inputs -> Outputs
Input: the WHOLE mirror library `knowledge/raw/` <-> `knowledge/distilled/`. Output: a
printed tally + `system/logs/judge_report.md` (the machine list of the fiches to re-process). The juge
NEVER writes into `raw/` nor into `distilled/` - it observes and flags (D85).

### When to FLAG
The juge never blocks by itself (observation skill, D85): every verdict other than `ok`
(hollow / thin / paraphrased / malformed / flagged / missing / raw_missing) IS the escalation
mechanism towards operator, via the report - it is up to operator to decide what follows (re-distil, force,
ignore).

### Validation
The juge IS the validator of the pipeline's other skills. Who validates the juge itself: its own
tests (`tests/distillation/test_juge.py`) which pin `judge_fiche` against known cases, and a
human/Opus re-reading of its verdicts - **no distinct meta-juge to this day** (assumed doubt, to be settled
if this skill itself becomes a critical point of failure).

### Logs
No `CoreApi` surface is wired for this skill to this day - the `judge_report.md` report is
a file, not an append-only JSONL event. **Assumed gap** (D36 demands Logs in the
D6/D33 sense; to be closed if `make judge` must become a production path).
