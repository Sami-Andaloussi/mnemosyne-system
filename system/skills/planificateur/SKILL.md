---
name: planificateur
description: >
  How a CONFORMANT plan is born (D166) — a plan is a FOLDER: a door with an imposed name that carries
  the heading and the index, a folder of arcs next to it, one file per arc. The skill does not describe
  the shape, it EMITS its bytes (make plan-emit), replayed from the code (plan_scaffold / plan_convert /
  plan_format) and never copied by hand; and if the agent would rather have the code write it in its
  place, make plan-nouveau refuses rather than overwrite. The SAME command also emits the METHOD (A6):
  seven falsifiable questions (from the project's own planning-methodology notes) about HOW ONE THINKS
  when building a plan, never a template -- level 1, "not applicable" is a valid, free answer. Use it
  as soon as a project, a workstream, or a sub-arc needs a plan that the pre-commit gate will accept on
  the first try, with no conversion, AND a compass for thinking it through well.
task_class: atomic
sensitivity_max: perso
version: "1.0"
id: planificateur
date: 2026-07-29
---

# Skill : planificateur (D166 / D170 / D163)

A plan exists to **let anyone see, continuously, where a piece of work stands**, even when that work
is done by an agent who will never come back. For that to hold, the shape must be the same everywhere:
an interface does not go hunting for a file name everyone picks differently, and a single reader can
only read what is written in exactly one way. This skill is the **birth** of that shape — where
`plan-convertir` only knew how to **repair** a plan already written crooked.

## When to use it

- A project starts, a workstream opens, an arc grows too big and earns its own plan.
- An agent (frontier or local) has to write a plan and does not know the imposed shape.
- A plan already exists but it is unclear whether it will pass the pre-commit gate: `make plans`
  says so, and this contract says what is missing.

## How to invoke it -- the TWO paths, and they do not compete

    make plan-emit [NOM="my project"]      # RECEIVE the structure: the exact bytes, ready to apply
    make plan-nouveau CHEMIN="..." APPLY=1 # let the CODE write it: it refuses rather than overwrite

The first is the path for an agent that drafts the plan itself (it holds the pen, it inherits the
shape). The second is the path of the safe gesture: named refusals — the list lives in the code and
`make plan-emit` renders it, it is not copied here — a single reason blocks the whole birth, and
nothing is written until the reader has accepted the bytes. **They share the same home of code**, so
they cannot say two different things.

## What it GUARANTEES -- by construction, not by trust (D100)

- **The READER judges the bytes BEFORE any write.** `verify_readability` replays exactly the
  pre-commit hook's chain (`read_plan` + `merge_plan` + `index_problems` + `is_readable`) on the
  strings about to be laid down. A plan can therefore never be born in a state the gate will
  refuse: that would mean learning of the fault at the exact moment the plan is created.
- **The index entry comes from a SINGLE home** (`plan_convert.index_entry`). A second expression of
  that shape would reopen the class D170 paid for: the rule had been calibrated on the tool's own
  output, and it scored twelve for twelve against the tool and two for ten against hand-typed text.
- **The emitted contract is REPLAYED, never copied by hand.** Statuses, accepted and refused
  separators, named refusals, tree, door, arc: every piece is computed by calling the code. A
  hand-made copy loses a clause on the first change, and nobody sees it.
- **The suite parses what the emitter renders** (`tests/orchestration/test_plan_emit.py`): the
  emitted bytes are pulled back out of the text and handed to the reader itself. The day the emitter
  and the reader diverge, it turns red — not on a project's next commit, here.

## The thinking method (A6) — level 1, and it never will be anything else

`make plan-emit` renders a SECOND thing, alongside the shape: seven falsifiable questions about HOW
TO THINK a plan through (from the project's own planning-methodology notes — COMPLETENESS,
SELF-SUFFICIENCY, FALSIFIABILITY, SEQUENCEABILITY, PROPORTIONALITY, REVISABILITY, PORTABILITY), plus
the sequence that produced this very skill: INVESTIGATE -> AXES -> ITEMS -> GRANULARIZE (as long as
a file forces you to GO LOOK for something, it is not done being broken down).

**This is NOT an eighth guarantee.** Everything above is level 2 (the reader judges, refuses,
blocks). The method is level 1 (an optional layer of guidance, per the project's own governance
conventions): "not applicable" is a valid, free answer to each of the seven questions, nothing
requires it, nothing reads it to judge anything at all — `verify_readability` does not even see it,
and `ScaffoldPlanning` (what `make plan-nouveau` ACTUALLY writes to disk) carries no field for it.
This is deliberate: *"show what kind of thinking is needed, not exactly what to think — otherwise it
locks people in, frames them, and suffocates them"* (the user). A template to fill in would have
manufactured the content it demands; this invites, and nothing more.

Home: `mnemosyne.production.plan_scaffold.METHOD_QUESTIONS` / `method_skeleton`. Replayed by
`plan_emit.build_emission`, never copied by hand — the SAME rule as for the shape, a second time.

## Recursion is allowed, it is never imposed

Any folder that carries a door is a plan, at any level: an arc that has grown huge becomes a
sub-folder with its own heading and its own scope of identities. But **a plan made of a single file
remains perfectly valid** — it is the floor of the shape, never a degraded case, and half the plans in
this repo need nothing more. One single constraint holds the two together: a sub-plan must be
**named in its parent's index**, or it is born orphaned and the commit is refused (`arc_hors_index`).
That is why `plan-nouveau` updates the parent door **in the same gesture** — a birth that produces an
orphan is a broken birth.

**Target the PROJECT's folder, never its `plan/`.** `CHEMIN="<project>/plan"` is a very plausible
typo and it is refused (`dossier_des_arcs`): written there, the new plan would become two ARCS of the
plan above it, which the door above does not index — the parent plan would stop being readable while
the command announced success. A SUB-plan is born one notch lower:
`CHEMIN="<project>/plan/<the-sub-plan>"`.

**Breadth as much as depth.** Several SIBLING sub-plans under the same door is the normal shape at
the scale this targets, not an edge case — and that is precisely what was broken: the SECOND sibling
was refused for an `id_duplique` that existed in no plan, because the internal check walked the disk
differently than the judge did. There is now a single enumeration (`fold_plan`), the same one the
gate uses.

## Under the hood (the body governs -- D70)

- `system/lib/mnemosyne/production/plan_scaffold.py` — the PURE home: the bytes, the refusals, the
  verification by the reader. It opens nothing and writes nothing.
- `system/lib/mnemosyne/runtime/plan_new_run.py` — the side effects and the proposed gestures.
- `system/lib/mnemosyne/production/plan_format.py` — the READER: it has the final word.
- `system/skills/planificateur/plan_emit.py` — the emission seam (print-only, no model).

## Status (activation cycle D37)

`DRAFT`. The `make` target already works and the suite is green; the move to `ACTIVE` awaits the
DISTINCT auditor (D75 / D39-6) and the user's gesture.

## D36 Anatomy (the standard floor -- six sections)

### Role

The agent becomes **the planificateur**: it gives birth to, or grows, a plan that is a conformant
folder — never inventing the shape, and never hand-writing a total.

### Method

Receive the structure (`make plan-emit`, a contract replayed from the code) or have the code write
it (`make plan-nouveau`, DRY by default, `APPLY=1` to lay the files down). Either way the
verification is the same and it comes from elsewhere: the reader, then `make plans`, then the
pre-commit gate. The skill holds **no judgment of its own** about a plan's conformance. `make
plan-emit` also renders the thinking METHOD (seven questions, see the dedicated section above) — IT
has, and will always have, no verification: reading it or ignoring it are two equally valid uses of
the skill.

### Inputs -> Outputs

Input: a folder path, and optionally a name, a heading, arc titles. Output: either a text contract
on standard output (nothing is written), or a `PLAN.md` door, a folder of arcs and a first arc — plus,
when the plan is nested, the index entry laid on the parent door in the same gesture.

### When to FLAG

A single reason is enough to block the whole birth, and each one is named: missing path, repo root,
outside the repo, a path that is an existing plan's `plan/` folder, door already present, arc file
already present, file-name collision, arc with no title, missing name, multi-line text, text
containing a `plan/….md`, unreadable parent door. Each one fires ALONE (the suite requires it: a
refusal that cannot be the sole cause makes the reader read its neighbor's refusal instead).

The terminal refusal — `squelette_illisible` — means the emitter and the reader have diverged: that
is a defect in the code, not a caller error. **It used to claim this wrongly on at least three
ordinary inputs** (`--arc "Socle — plan/fantome.md"`, `--nom "plan/autre.md"`, a multi-line
`--cap`), and the agent would then file a FALSE signalement into the user's queue before leaving
without a plan. What a caller can get wrong is now a refusal that accuses the INPUT, naming the
offending word; an already-broken parent door is `porte_parente_illisible`, not a Mnemosyne failure.
**We refuse, we never overwrite** (inv. 2).

### Validation

The validator is not this skill: it is the reader (`plan_format`), replayed before any write, then
`make plans` (readable? with how many items?) and the pre-commit gate that judges the staged plan, at
every level. The anti-drift suite `tests/orchestration/test_plan_emit.py` locks the link between the
two: it makes the reader PARSE what the emitter renders.

### Logs

No event logged today: both surfaces are local, model-free, network-free, and have no access to
`knowledge/` — `plan-emit` does not even open a single file. **Acknowledged gap** (D36 calls for
Logs): to close if a plan's birth ever needs to be traced as a production.

## Cross-references

`docs/FORMAT_PLAN.md` (the shape) · `system/skills/README.md` (the skill index) ·
`system/config/skills.toml` (the protected registry) · `Makefile` (`plan-emit`, `plan-nouveau`, `plans`)
