---
name: veilleur
description: >
  Mines the ALREADY-DISTILLED corpus (knowledge/distilled/) to draw principles / skills /
  hypotheses from it, deposited as INERT drafts (knowledge/proposals/veille/) for the operator's
  review -- proposes, never imposes (D92). To be used when `make tick` reports that N fiches are
  waiting for a veille pass (Q5), or on demand. NO local model here: the skill EMITS the exact
  contract (worklist + schema) that a FRONTIER agent (Claude Code) applies by genuinely reading
  each fiche.
task_class: atomic
sensitivity_max: sensible
version: "1.0"
id: veilleur
date: YYYY-MM-DD
---

# Skill: veilleur (Q5 / D92)

Mines the **already-distilled understanding** (`knowledge/distilled/`) to draw **principles**,
**skills** and **hypotheses** from it -- the richest source of the soul's proactive nerve ((5),
`mnemosyne.production.proposer.VeilleReview`). The nerve ONLY nudges ("N fiches are waiting for a
veille pass"); the close reading that genuinely extracts something from them remains the act of the
**frontier master** (the cohabitation doctrine, `ARCHITECTURE.md`) -- never a local model, never
automatic. Every finding is deposited as an **INERT draft** on disk: nothing is applied, nothing is
promoted, nothing joins the living memory or an active skill without the operator's review gesture.

## When to use it
- `make tick` (soul (5)'s wake-up) reports "N distilled fiches are waiting for a veille pass" --
  `VeilleReview` reads the same ledger as this skill.
- On demand, to mine a batch of the corpus even without a nudge.
- Never in an unsupervised loop: a pass is **bounded** (`DEFAULT_BATCH`) and its drafts **wait** for
  review -- this is not an automatic ingestion pipeline.

## How to invoke it -- THE ONE path
```bash
make veille              # emits the contract for the DEFAULT_BATCH (20) first unsurveyed fiches
make veille BATCH=5      # caps this pass at 5 fiches (quick trial)
```
Nothing else. NO local model, NO brick runs: the target prints, everything DERIVES from the code
(`veille.py`) -- the **worklist** (unsurveyed fiches, capped), the **JSON schema** of each finding,
and the **output instructions** (where to write each draft, how to mark a fiche surveyed). The agent
that answers the contract IS the extractor -- there is no bespoke prompt to rewrite elsewhere.

## What it GUARANTEES -- by construction, not by trust (D100)
- **Worklist = the ledger, never a re-reading**: `unsurveyed_fiches` (already built,
  `mnemosyne.production.veille_ledger`) computes {fiches on the shelf} - {already surveyed}; this
  skill only BOUNDS it to `DEFAULT_BATCH` -- a pass stays tractable, never a full sweep of the
  corpus in one go (spirit of invariant 16).
- **Contract EMITTED, never hand-copied** (anti-drift): the JSON schema and the instructions come
  from ONE single code home (`veille.py`); `emit_veille.py` replays them byte for byte. Lock:
  `tests/orchestration/test_veille_emit.py`.
- **Proposes, NEVER imposes (D92)**: a draft is one more `.md` file in
  `knowledge/proposals/veille/` (`status: draft`) -- no mechanism here applies it, promotes it, or
  makes it enter the living memory or an active skill. Only the operator's review promotes.
- **Non-repeating (D44)**: a fiche whose draft has been written is marked `mark_surveyed` -- append
  only, never rewritten -- so that the proactive nerve stops re-reporting it. A fiche the operator
  has not yet read stays on the shelf; nothing is lost if a pass stops mid-batch.
- **Correct silence**: corpus already entirely covered -> "Nothing to veiller" (no error, no finding
  invented in order to have "something to say").

## For a FRONTIER agent (Claude Code) -- YOU ARE THE EXTRACTOR
Here, a skill = **the real veille work executed IN A LOOP** over the emitted worklist: the close
READING that the proactive nerve never does itself (it only ever sees a count, never the matter,
compartmentalization / invariant 22). You are not "filling in a template": a generic finding, one
that could apply to any fiche without having genuinely read this one, is a FAILURE -- exactly the
lesson of distillation's first frontier pass.

**The contract comes from the CODE, never from a copy.** Run `make veille` (or `make veille
BATCH=N`): it prints the worklist (fiche + path to read + path to write), the exact JSON schema, and
the completion reminder. Then, for EACH listed fiche:
1. **Read it IN FULL** at the `lire` path indicated -- not an excerpt, not the file name alone.
2. **Extract** what genuinely deserves to carry across (zero to several findings; zero is honest if
   the fiche offers nothing reusable -- never invented to fill up). Each finding: `kind`
   (`principle` / `skill` / `hypothesis`), `statement` (concise), `rationale` (what, IN THE FICHE,
   supports it), `source` (the fiche's id), `proposed_test` (how a FUTURE pass could validate it --
   the operator's "propose + test").
3. **Write** an inert draft at the `ecrire` path indicated (frontmatter `source` / `date` / `status:
   draft`, then the list of findings).
4. **Mark the fiche surveyed** -- only AFTER having written its draft, never before. **The exact
   reference is PRINTED by the contract** (`make veille` derives it from the real symbol,
   `veille.py:40`): take it from there, do not copy it from here. A hand copy in this file would
   become a dead reference at the first module move -- exactly what the derivation avoids
   (contract-single-source-emit).

## Under the hood (the body governs -- D70)
- Single-source contract: `veille.py` -- `VEILLE_SCHEMA` (the schema of a finding), `DEFAULT_BATCH`
  (the per-pass cap), `STAGING_DIR` (`knowledge/proposals/veille`, never created by this skill --
  the applier creates it on use), `build_worklist` (bounds `unsurveyed_fiches`), `build_contract`
  (assembles the printed text). Pure: no model, no brick.
- Emission: `emit_veille.py` (target `make veille`) -- replays `veille.build_worklist` +
  `veille.build_contract` over the REAL shelf (`knowledge/distilled/`) and the real ledger
  (`system/state/veille_ledger.jsonl`, gitignored -- D82 barrier).
- The proactive nerve: `mnemosyne.production.proposer.VeilleReview` reads the SAME
  `unsurveyed_fiche_count` and deposits a meta-only nudge (a count, never the matter) into the
  receptacle (surface f) -- wired into `make tick`.
- Ledger: `mnemosyne.production.veille_ledger` (already built) -- append-only (D44), fail-open on
  read (a corrupted line re-reports a fiche, never crashes the pass).
- Anti-drift lock: `tests/orchestration/test_veille_emit.py`.

## State (D37 activation cycle)
BRAND-NEW skill, built to wire autonomy's Q5 nerve (the remaining work (5) figures / veille). The
ledger and the proactive nudge (`VeilleReview`) were already built; this skill adds the CONTRACT
side (`veille.py` + `emit_veille.py`) that `make tick` points to. State DRAFT
(`ActivationState.DRAFT`) -- like every generated skill, it requires a DISTINCT auditor (D39-6,
`SkillGenerator.audit`, run on Opus 4.8 by doctrine) then the operator's validation gesture before
`ACTIVE` (D37); it never runs on trust alone.

<!-- NOTE (public-mirror): the six D36 body-section headings below ("Role", "Methode",
     "Entrees -> Sorties", "Quand FLAG", "Validation", "Logs") are left UNTRANSLATED on purpose --
     they are matched verbatim (accents optional, wording is not) by
     `mnemosyne.production.skills._D36_BODY_SECTIONS`. Writing the English gloss ("Method",
     "Inputs -> Outputs", "When to FLAG") in their place would silently make this file stop being
     D36-conformant, without any test turning red (`anatomy_gaps` is informational and never flips
     `ok`). -->

## D36 anatomy (standard floor -- six sections)

### Role
The agent becomes the **veilleur**: a reader of the ALREADY-distilled understanding, who never
invents a finding the fiche does not carry (D25), and who never speaks in their own name to say that
a finding is "true" -- they propose it, attributed to its source, never imposed (D92).

### Method
Bounding of the worklist (CODE, deterministic: `unsurveyed_fiches` minus the ledger, capped at
`DEFAULT_BATCH`) then extraction fiche by fiche (JUDGMENT, the frontier agent ALONE -- never a local
model, the cohabitation doctrine) then deposit of ONE inert draft per fiche + `mark_surveyed`
marking (CODE, append-only). The exact detail lives in "How to invoke it" and "For a FRONTIER agent"
above -- this section only names the three steps, never rewrites them elsewhere.

### Inputs -> Outputs
Input: the fiches of `knowledge/distilled/<domain>/` listed by the worklist (never the raw, never an
already-surveyed fiche). Output: one draft per fiche at `knowledge/proposals/veille/<slug>.md`
(inert, `status: draft`) + one append-only line in `system/state/veille_ledger.jsonl` per processed
fiche (`mark_surveyed`).

### When to FLAG
Corpus already entirely covered -> not a flag, an honest fact ("Nothing to veiller"), the pass stops
there. A fiche that offers no reusable finding (`source-unusable` flag-fiche, content too short or
too generic) -> honest draft with ZERO findings (never a generic finding invented to "have
something"), then `mark_surveyed` all the same (non-repeating: never re-report a fiche already
looked at, even if it offered nothing). A pass interrupted mid-batch -> without consequence: the
already-marked fiches stay surveyed, the others fall back into the next pass's worklist.

### Validation
No automatic judge of CONTENT exists here (by construction, D92: the substance of a principle is a
human judgment, not mechanizable like distillation's verbatim). The verifiable mechanical floor is
CONFORMITY to the schema (the five fields present, `kind` within the enum) -- not the quality of the
content. The real validator is **the operator's review** over `knowledge/proposals/veille/`: reading
each draft and deciding, fiche by fiche, what deserves to be promoted (living memory,
`ARCHITECTURE.md`, a skill) -- promotion always remains a human gesture, never this skill.

### Logs
No `CoreApi` / Guard call here: the emission (`make veille`) is a pure read of the ledger and the
shelf (like `make judge` / `make skill-audit`, no brick). The extraction itself (the frontier agent
that reads a fiche and writes a draft) is an act of the master operating directly in the repo,
outside a traced Guard call -- like the distillateur's frontier loop. The durable trace of progress
is the ledger itself (`system/state/veille_ledger.jsonl`, append-only): each line IS the journal of
what has been surveyed. Accepted gap, like the one already noted by the distillateur for its direct
CLI entry (D36 requires Logs; to be closed if this path is to become the production route).
