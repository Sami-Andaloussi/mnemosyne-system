---
name: skill-creator
description: >
  Creates a NEW repo skill (or audits/scaffolds an existing one) following the 5-layer anatomy
  already in place (distillateur / finisseur / juge): home in the CODE, thin adapter,
  dedicated make target, -emit seam, verification-in-code, lock-test - never a prompt
  hand-copied. To be used as soon as a real need calls for a new skill (make skill-new),
  or to verify IN CODE that a candidate skill respects the anatomy and carries no prompt
  that has drifted from its source code (make skill-audit). The contract is EMITTED from skills.py
  (make skill-emit): this skill applies to itself the anti-drift rule it imposes on the others.
task_class: atomic
sensitivity_max: sensible
version: "1.0"
id: skill-creator
date: YYYY-MM-DD
---

# Skill: skill-creator (D37 / D39-7 "generateur-de-skills" / D75)

The seed skill `SEED_SKILLS['generateur-de-skills']`: "fabricate new skills conformant to the
anatomy". The distillateur -> finisseur -> juge arc learned the SAME lesson the hard way three times
(a hand-made copy of the prompt drifted from the code and silently broke a host) before it became
structural (`contract-single-source-emit`, commit `241e525`). This skill ENGRAVES that lesson (and
five others from the same arc) so that a future skill does not rediscover them a fourth time.

## When to use it
- A real need calls for a new skill (never by anticipation - D39, just-in-time).
- To verify that a skill (yours, or an existing one) does respect the repo anatomy, BEFORE
  proposing it to a distinct auditor (D39-6).

## How to invoke it
- **Scaffold a DRAFT**:
  ```bash
  make skill-new NEED="what the skill must accomplish" [NAME=kebab-name]
  ```
  Creates the REAL skeleton (not a README): a home stub in `production/`, a thin adapter
  in `system/skills/<nom>/`, a `make <nom>` target in the root Makefile, a lock-test in
  `tests/`. The stub raises `NotImplementedError` - loud if ever invoked before being filled in
  (D100: never a silent failure). The generated SKILL.md carries `TODO(skill-creator)` markers:
  they are part of the contract (see `audit_skill.py` below), to be replaced by the real work.
- **Emit the contract** (before filling in a DRAFT by hand or via a frontier agent):
  ```bash
  make skill-emit
  ```
  Prints, EMITTED from the CODE (never hand-copied here): the 5-layer anatomy + the 6 lessons of
  the distillateur/finisseur/juge arc. This is the ONLY authoritative version - see "For a FRONTIER
  agent" below.
- **Audit a candidate**:
  ```bash
  make skill-audit DIR="system/skills/<nom>"
  ```
  The judge-analog: verifies IN CODE (no trust) that a skill folder respects the anatomy -
  see "What it GUARANTEES". Writes nothing; prints a report and exits with an error if `ok` is false.

## What it GUARANTEES - by construction, not by trust (D100)
`make skill-audit` puts a candidate through MECHANICAL checks (never a read by eye).
**Four can flip `ok`** (`-emit` seam, anti-drift, frontmatter, unreadable files);
**two SEPARATE axes** never touch it: `scaffold_only` and the **D36 anatomy** (`anatomy_gaps` -
frontmatter fields and six mandatory body sections; informational, so that a skill built before this
axis is reported honestly rather than retroactively failed). The two separate axes print
**only if there is something to say**: no line = zero gap, not "not checked".
- **`-emit` seam present - IF the skill has a model contract** - an `-emit` target in the
  Makefile and/or an `*_emit.py` file in the skill's folder. Required only when the skill
  has a contract constant (`*_PROMPT` / `*_TEMPLATE` / `*_SCHEMA`) that a frontier host must follow:
  without a seam, nothing guarantees it receives the same contract as the local host. A skill WITHOUT
  a model (the `juge`: pure verification, nothing to emit) does not need one - the absence is then
  reported INFORMATIONALLY, never a failure (the gate does not crash a healthy model-less skill).
- **Anti-drift (THE central lesson)** - the SKILL.md must contain NO long, literal extract
  of a `*_PROMPT` / `*_TEMPLATE` / `*_SCHEMA` constant from the code (`production/*.py`): a hand-copy,
  even partial, is detected (60-character sliding window). This is exactly the error that
  broke the distillateur's first frontier pass.
- **Clean frontmatter** - `name` in kebab-case, `description` present and bounded (<=1024
  characters, no angle brackets), and EXACTLY one `SKILL.md` in the folder (taken from Anthropic's
  `quick_validate` lint, bounded to what this repo actually checks).
- **Unreadable files** - a skill file the audit cannot decode (`unparseable_files`,
  `skills.py:505-506`) makes `ok` fail: we do not bless what we could not read (D100).
- **scaffold_only axis, SEPARATE** - an unfilled skeleton (remaining `TODO(skill-creator)`
  markers, or a body that is too short) is REPORTED, never silently crashed nor whitewashed into
  `ok` (lesson 6: an agent that scripts a template onto a large generative task must be caught
  by a separate axis, like `n_templated` at the juge - never merged into the fidelity verdict).

> WARNING: **What this audit does NOT cover** (it is mechanical, it does not read MEANING): that the
> SKILL.md **tells the truth about what the code does**. A skill can pass the 4 checks and promise a
> guarantee its code does not offer - that happened at the distillateur ("its output goes back through
> the floor", false on `distill-emit`) and to **this very file** ("imported, never retyped", when the code
> was retyping). Hence the D37/D39-6 ritual: **generate -> audit by a DISTINCT verifier -> activate**.
> `make skill-audit` is the 1st step, never the last.

> **Layer 1, "mandatory", is not really so**: `audit_skill` **does not check** that the code home
> lives at `production/<nom>.py` - the `veilleur` does not follow that rule (its home is
> `system/skills/veilleur/veille.py`) and passes the audit. A second-order effect worth knowing: anti-drift
> scans only `production/` (`audit_skill.py:186`), so **it is blind to any live contract outside it**.

What `make skill-audit` does NOT guarantee: that the skill is WELL DESIGNED, that its logic is
correct, or that it deserves activation. That is the job of a DISTINCT human auditor
(D39-6 / D75) - `make skill-audit` is its mechanical PREREQUISITE, not its replacement.

## The mandatory architecture - the 5 couches (layers), always in this order
| # | Layer | Where | Example |
|---|--------|-----|---------|
| 1 | Home in the code | `system/lib/mnemosyne/production/<nom>.py` | `finisher.py` (`FINISH_PROMPT`, `chapter_numbers_ok`) |
| 2 | Thin adapter | `system/skills/<nom>/<nom>_*.py` | `finish_book.py` |
| 3 | Make target | `make <nom>` in the root `Makefile` | `finish:` |
| 4 | `-emit` seam | `system/skills/<nom>/<nom>_emit.py` + `make <nom>-emit` | `finish_emit.py` |
| 5 | Verification-in-code | pure function in the home, normalized verdict | `judge_fiche` |

Plus the lock: a test in `tests/` proving that the emission carries a REAL fragment of the
code constant (never a paraphrase). Two exemplars to imitate, never reinvent:
`keep_verbatim` (P3 sacred, whenever a skill restructures a source of truth) and
`chapter_numbers_ok` (fail-closed guard: ambiguity refuses, it never guesses).

## For a FRONTIER agent (Codex / ChatGPT with repo access) - YOU ARE THE MODEL
**The contract comes from the CODE, never from a copy.** Same lesson as the distillateur: prose
hand-copied here would DRIFT from the code (`skills.py`) and would lie - which is precisely what
this skill's own `make skill-audit` on itself is meant to catch.
1. Run `make skill-emit`. It prints, EMITTED from `SKILL_ANATOMY_TEMPLATE` (the single home):
   the 5-layer anatomy and the 6 lessons of the arc - the EXACT text to follow, byte for byte.
2. Understand the real need (never by anticipation, D39) and run `make skill-new NEED="..."`
   to lay down the REAL skeleton (not a README describing an imaginary skill).
3. Fill in the code home FIRST (the logic + any model contract), then the thin
   adapter, then the `-emit` seam that REPLAYS the code (never prose written separately), then the
   test lock.
4. Write the SKILL.md: describe the anatomy and the lessons IN YOUR OWN WORDS (like this one) -
   NEVER paste a long extract of the emission or of a `*_PROMPT`/`*_TEMPLATE` constant: that
   would be exactly the drift this skill exists to stop.
5. `make skill-audit DIR="system/skills/<nom>"` MUST be green (`ok`), and `scaffold_only` must
   be FALSE once the real work is done (a `scaffold_only=true` that persists = you left a
   `TODO(skill-creator)` or a body that is too short).

## Testing - the prod path, under real conditions
A skill is only proven by a FRESH, UNBIASED agent, plugged into its natural `make` entry
point, with repo access and WITHOUT being handed the answer - never an example already known
to work. See `references/testing.md` for the recipe (mirror of the distillateur's validation
on Carver, and of the GUARD-SAFE Opus audit of this skill-creator itself).

## Under the hood (the body governs - D70)
- Contract + audit: `mnemosyne.production.skills` - `SKILL_ANATOMY_TEMPLATE` (the single home, never
  hand-copied), `SCAFFOLD_MARKERS`, `SkillAudit`, `audit_skill(...)` (pure: verdict from texts
  already read, like `judge_fiche`). Re-exported by `mnemosyne.production`.
- Orchestration (this folder): `skill_emit.py` (`make skill-emit`, prints the contract, no
  brick); `audit_skill.py` (`make skill-audit DIR=...`, scans the Makefile + `production/*.py`
  via `ast` for the `*_PROMPT`/`*_TEMPLATE`/`*_SCHEMA` constants, calls the pure verdict, prints);
  `new_skill.py` (`make skill-new NEED=...`, DRAFT scaffold: home stub, adapter, Makefile
  target, lock-test).
- References: `references/architecture.md` (the thin-adapter/home/emit-seam map, with
  `keep_verbatim` and `chapter_numbers_ok` as exemplars), `references/anti-drift.md` (the WHY
  - the copy that drifted and broke the arc), `references/testing.md` (the prod-path recipe).
- Locks: `tests/identity/test_skill_emit.py` (the emission carries the REAL `SKILL_ANATOMY_TEMPLATE`, not a
  paraphrase); `tests/identity/test_audit_skill.py` (the 4 checks + the separate `scaffold_only` axis,
  and the anti-drift lint that BITES on a planted extract).

## State (D37 activation cycle)
Seed skill `SEED_SKILLS['generateur-de-skills']`. Body + `-emit` seam + audit-in-code:
built, tested. The formal activation DRAFT -> AUDITED -> ACTIVE (`SkillGenerator`, `skills.py`)
requires a **distinct** auditor (D39-6 / `require_distinct`) + the **operator's gesture** (D37) - like
every skill in this repo, this one never runs on the sole trust it would grant
itself (dogfood all the way: the skill generator follows its own rule).

## Anatomie D36 (normalized floor - six sections)

### Role
The agent becomes **the skill generator** (D39-7): it scaffolds/emits/verifies the ANATOMY of a
candidate skill (the container), never its content nor its judgment quality - that stays D39-6.

### Method
`make skill-new` scaffolds an all-or-nothing DRAFT (CODE, fail-closed); `make skill-emit` replays and
prints the contract from `SKILL_ANATOMY_TEMPLATE` (CODE, never prose written separately);
`make skill-audit` verifies IN CODE a candidate against that contract. Detail in "How to
invoke it" and "The mandatory architecture" above.

### Inputs -> Outputs
Input: a described need (`make skill-new NEED=...`) or a candidate skill folder (`make
skill-audit DIR=...`). Output: either a DRAFT scaffold (4 files + Makefile target), or a
printed audit report (nothing is written by `skill-audit` nor `skill-emit`).

### When to FLAG
`make skill-new` REFUSES (nothing is written) if one of the 4 target locations already exists - never a
half-scaffold nor an overwrite (D100). A `make skill-audit` returning `ok=false` IS the stop signal
before any distinct human auditor (D39-6): the skill must not move on toward activation.

### Validation
`make skill-audit` is the MECHANICAL verifier of the anatomy (-emit seam, anti-drift,
frontmatter, scaffold_only, and now the `anatomy_gaps` D36 axis - informational). It does NOT
guarantee the quality nor the merit of activation: that stays a **distinct** human auditor
(D39-6 / D75), as already spelled out in "What it GUARANTEES" above.

### Logs
No `CoreApi` surface is wired for this skill to date - `skill-new`/`skill-emit`/
`skill-audit` are CLI development tools, not Guard-mediated calls. **Accepted gap**
(D36 requires Logs; to be closed if this skill becomes an automated production path).
