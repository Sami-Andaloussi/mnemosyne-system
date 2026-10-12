---
name: rangement
description: >
  Tidies the repo: detects CLEAR cruft (OS .DS_Store, stale manifest backups, old logs, stray
  outputs) and puts it in reversible QUARANTINE (knowledge/_quarantine/), non-destructively -- NEVER
  delete (operator gesture, D74), propose-never-impose (D92). The deterministic core lives in code;
  the FRONTIER version = the EMITTED contract (make rangement-emit) = a prompt, with no bespoke .py.
  To be used when the repo gets dirty, or when the autonomy nerve signals a recurring tidying chore
  (repo-navigability).
task_class: atomic
sensitivity_max: sensible
version: "1.0"
id: rangement
date: YYYY-MM-DD
---

# Skill: rangement (item 7 / D74 / D92)

Keeps the repo **navigable** (`repo-navigability`) by putting derived cruft into **reversible
quarantine**, never by deleting it. This skill is the archetype of two things the operator wants
anchored: the **autonomy nerve** (whatever is repetitive and automatable becomes a skill, item 3)
and the **multi-version doctrine** (item 5) -- its **frontier version is a plain PROMPT** (the
emitted contract), with no dedicated `.py` to execute.

The division of labour follows the anatomy (deterministic = CODE, judgement = agent):
- **The CODE** (`mnemosyne.production.rangement`) only detects **CLEAR** cruft (`classify` is
  deny-by-default: an unrecognised file is **never** a candidate, never guessed), plans a
  **REVERSIBLE** move to `knowledge/_quarantine/rangement-<stamp>/` (relative path preserved, a
  manifest written), and **refuses fail-closed** to touch a protected path
  (`no_protected_path_touched`).
- **The FRONTIER** (via `make rangement-emit`) does the judging the code cannot: validate the plan,
  then **scan** the less obvious mess (a stale doc, a duplicate, an orphaned output) and **PROPOSE**
  it to the operator -- never move it.

## When to use it
- The repo has got dirty (stale backups, old logs, `.DS_Store`, stray outputs at the root).
- The proactive nerve ((5)) signals a recurring tidying chore (item 3, once wired).
- On request. Never in an unsupervised loop: one pass is **bounded** (a single scan) and
  **non-destructive**; the quarantine waits for the operator's gesture.

## How to invoke it -- THE ONE path
```bash
make rangement            # DRY-RUN: prints the plan, moves NOTHING (least surprise)
make rangement APPLY=1    # applies the reversible moves + writes MANIFEST.json
make rangement-emit       # prints the CONTRACT for a frontier agent (the plan + the judging pass)
```
No model, no brick: everything DERIVES from the code (`rangement.py`) -- the detection, the plan,
the contract.

## What it GUARANTEES -- by construction, not by trust (D100)
- **NON-DESTRUCTIVE (D74 / invariant 2)**: this skill only **MOVES** a file into quarantine. It
  NEVER deletes. Emptying the quarantine (a real deletion of the operator's bytes) is THEIR gesture,
  never this skill's.
- **PROPOSE, NEVER IMPOSE (D92)**: the deterministic pass acts only on the cruft it can **name with
  certainty**; anything ambiguous is left to the frontier to **propose** and to the operator to
  decide. And `make rangement` is **dry-run by default** -- nothing moves without `APPLY=1`.
- **Fail-closed on protected paths**: the living state (`system/state`, `.snapshotstore`), the
  separate nested repos (`projects/*`), the sources of truth (`knowledge/raw` + `distilled` +
  `golden`) and the derived memory (`maps` / `proposals`), the VCS/toolchain trees (`.git` /
  `.venv` / caches) are **NEVER** touched, whatever a file may be named (`NEVER_TOUCH_*`, checked by
  `no_protected_path_touched` BEFORE any disk mutation). The **living** library manifest
  (`library_manifest.json`) is protected; only its **backups** are candidates.
- **Reversible**: every pass writes `knowledge/_quarantine/rangement-<stamp>/MANIFEST.json`
  (from -> to); restoring = moving each `to` back to its `from`. Nothing has been lost.
- **Contract EMITTED, never recopied** (anti-drift): the hard rules come from ONE home
  (`RANGEMENT_RULES`), replayed by `rangement_emit.py`. Lock: `tests/orchestration/test_rangement.py`.

## For a FRONTIER agent (Claude Code) -- YOU DO THE JUDGING
The code has already done the mechanical part (detect + plan the clear cruft). **Your** job is what
the code cannot do:
1. Run `make rangement-emit`: it prints the deterministic plan (worklist + destination of each file)
   and the hard rules.
2. **Validate** the plan (nothing surprising; otherwise report it to the operator, do not force it).
3. **Apply** it with `make rangement APPLY=1` (the code moves the files + writes the reversible
   manifest).
4. **Scan** the less obvious mess the classifier cannot know about -- a stale doc, a duplicate, an
   orphaned output -- and **FILE a proposal** for the operator (propose, never impose, D92). Never
   move an ambiguous file yourself: certainty belongs to the code, judgement is a proposal.

## Under the hood (the body governs -- D70)
- Single-source contract: `mnemosyne/production/rangement.py` -- `CruftClass` (the recognised cruft
  classes), `classify` (deny-by-default), `in_scope` + `NEVER_TOUCH_*` (the guard), `scan`,
  `plan_quarantine`, `no_protected_path_touched` + `plan_is_reversible` (verify-in-code
  fail-closed), `RANGEMENT_RULES`, `build_rangement_contract`. Pure: no model, no brick.
- Adapters: `rangement_run.py` (`make rangement`) applies the plan; `rangement_emit.py`
  (`make rangement-emit`) prints the contract. Orchestration only -- they import the code home.
- Anti-drift + logic lock: `tests/orchestration/test_rangement.py`.

## State (D37 activation cycle)
Skill in DRAFT state (`ActivationState.DRAFT`): like every generated skill, it requires a
**distinct** auditor and then a validation gesture before `ACTIVE`. Its tidying plan is reversible
and can be reviewed before any application.

## D36 anatomy (normed floor -- six sections)

### Role
The agent becomes the **tidier**: it never deletes (D74), never touches a protected path, acts only
on the cruft it can name with certainty, and **proposes** everything else without ever imposing it
(D92).

### Method
Detection of clear cruft (CODE, deterministic: `scan` + `classify` deny-by-default), fail-closed
verification of the plan (CODE: `no_protected_path_touched` + `plan_is_reversible`), then a
reversible move to quarantine + manifest (CODE, `--apply` only) -- and on top of that, the frontier's
**judging** pass (proposing the non-mechanisable mess). The exact detail lives in "How to invoke it"
and "For a FRONTIER agent" above; this section only names the steps.

### Inputs -> Outputs
Input: the repo tree (paths only -- never the CONTENT of a truth file; the sources are
`NEVER_TOUCH`). Output: the cruft files moved under `knowledge/_quarantine/rangement-<stamp>/`
(path preserved) + one reversible `MANIFEST.json` per pass. Nothing outside the quarantine, nothing
deleted.

### When to FLAG
Repo already clean at the deterministic grain -> not a flag, an honest fact ("no clear cruft found"),
the pass stops there. A plan that would touch a protected path, or would not be reversible ->
**fail-closed REFUSAL**, nothing is moved (the code refuses before any mutation). An ambiguous file ->
never moved: the frontier **PROPOSES** it to the operator, who decides.

### Validation
The verifiable mechanical floor is in code: `no_protected_path_touched` (no protected / non-cruft
path touched) + `plan_is_reversible` (no collision, no loss), exercised by `tests/orchestration/
test_rangement.py` (including an integration scan over a fake tree proving that the sources of truth
and the living state are never picked up). The real validator of the **judgement** (the ambiguous
mess) remains the operator's review of the proposals. Producer != verifier: the audit of the skill
itself is delegated (Opus 4.8), never delivered by its author.

### Logs
No `CoreApi` / Guard call here: the scan and the emission are pure reads of the tree (like
`make judge` / `make veille`, no brick). The durable trace of an applied pass is its
`MANIFEST.json` (from -> to) -- each line IS the log of what moved, and the means of undoing it.
Gap accepted, identical to the one already noted by the watcher for a pure seam outside a traced
Guard call.
