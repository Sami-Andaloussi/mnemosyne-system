# Architecture - the thin-adapter / code-home / emit-seam map

This document expands the table in `SKILL.md`. Read it when you are building a skill and want to
know WHERE to put each piece, with two real specimens to imitate rather than reinvent.

## The 5 layers, in the order you build them

1. **Home in the code** - `system/lib/mnemosyne/production/<nom>.py`. The REAL logic lives here,
   and NOTHING but here: every constant addressed to a model (`FINISH_PROMPT`, `DISTILL_SCHEMA`,
   `_PROMPT_TEMPLATE`) is defined ONCE, in this file. Everything else - adapter, `-emit` seam,
   SKILL.md - READS it, never RECOPIES it.
2. **Thin adapter** - `system/skills/<nom>/<nom>_*.py` (e.g. `finish_book.py`, `distill_book.py`).
   Orchestration only: walk files, call the home, write the result.
   No business rule here - if you write a rule in the adapter, it is in the wrong place.
3. **Make target** - one line in the root `Makefile`, `make <nom>: ... ## description`. This is THE
   only invocation path (never a hand-launched script nobody else remembers).
4. **`-emit` seam** - `system/skills/<nom>/<nom>_emit.py` + `make <nom>-emit`. REPLAYS the
   home's real functions (never a prose written on the side) to print, to a frontier host, the
   EXACT contract the local host receives. Print-only: no model, no brick required to
   run the emission itself.
5. **Verification-in-code** - a PURE function in the home that returns a normalised verdict from
   text already read (never globbing/IO inside - that is the job of the orchestrator that
   calls it). `judge_fiche(fiche_text, raw_text) -> FicheVerdict` is the specimen: no
   trust in the producer, human or model.

Plus the lock: a test proving that the emission (layer 4) contains a REAL fragment of the
home's constant (layer 1) - never a paraphrase of the test itself. See
`tests/distillation/test_finish_emit.py` / `tests/distillation/test_emit_prompts.py` for the exact shape.

## Two specimens to imitate, never reinvent

**`keep_verbatim`** (`mnemosyne.production.distillation`) - as soon as a skill RESTRUCTURES a
source of truth (a book, a transcript, a chat), the restructured content must stay faithful
word for word to the source: a passage is kept only if it is a literal substring (after
whitespace normalisation) of the source. Reuse this function, or its exact pattern, every time
a new skill risks letting a model paraphrase what must be copied.

**`chapter_numbers_ok`** (`mnemosyne.production.finisher`) - the shape of a FAIL-CLOSED guard:
a boolean function, evaluated BEFORE the skill acts, which refuses at the slightest
ambiguity rather than guessing. The skill that calls it SKIPS the ambiguous case (the finisher) and
another skill FLAGS it behind (the judge) - two angles that overlap, never a single verifier
trusted by default.

## What `make skill-audit` verifies of this architecture

`audit_skill(...)` (the code) + `system/skills/skill-creator/audit_skill.py` (the orchestrator that
reads the disk) verify MECHANICALLY that layers 3-4 exist (`-emit` target and/or `*_emit.py`
file) and that the SKILL.md does not betray layer 1 (see `anti-drift.md`). Layers 1, 2
and 5 - whether the LOGIC is correct - remain the work of a DISTINCT human auditor
(D39-6): no mechanical tool can judge that a skill's home does the right thing, only
that it exists and that it has not been short-circuited.
