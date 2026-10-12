"""J1 -- the BOUNDARY of the emitted plan-gate barrier: reads the disk, judges, refuses or lets
through.

**DISK, NOT THE STAGED GIT INDEX** — decision written in `production/plan_gate_shell.py`: this
is the same duality that `make plans` (disk) vs `.githooks/pre-commit` (staged index) already
carries for THIS repo, never a third form invented.

**FAIL-OPEN EVERYWHERE EXCEPT THE REFUSAL, HERE, IN THIS MODULE** — incorrect usage, an absent
folder, a plan unreadable for ANY OTHER reason do not block a commit: this module (`main()`/
`juger()`) only ever returns 0 or 2. Only the 12 kinds that `.githooks/pre-commit` (Mnemosyne)
already judges via `is_readable()` (:data:`~mnemosyne.production.plan_format.READER_REFUSALS` --
the door is not STRUCTURALLY readable) or an item missing a field the door ITSELF declared
required (`champ_requis_manquant`, D176) exit with 2. **"SAME PRINCIPLE AS `garde_shell.py`"
IS NO LONGER TRUE FURTHER DOWN THE CHAIN (R3/R4, 2026-08-17)**: this module stays fail-open as
always, but the SHELL WRAPPER that invokes it (`production/plan_gate_shell.py`) no longer is for
an INVOCATION failure -- see its doctrine, spelled out there.

**"ADOPTING" ONLY BOUGHT A THIRD OF THE SURFACE, AND IT WAS WRITTEN NOWHERE (2026-08-17).**
`plan_format` produces **16 kinds** of refusal in total, in four declared families:
:data:`~mnemosyne.production.plan_format.READER_REFUSALS` (12, what `read_plan`/`index_problems`/
`fold_plan` raise from the bytes -- STRUCTURAL, level 1) · :data:`~mnemosyne.production.
plan_format.PREREQUISITE_REFUSALS` (2, level 2, scope left to the CALLER) · :data:`~mnemosyne.
production.plan_format.REQUIRED_FIELD_REFUSALS` (1, D176, opt-in level 2) · :data:`~mnemosyne.
production.plan_format.PRODUIT_REFUSALS` (1, level 2, **deliberately NOT wired even in
Mnemosyne's own hook** -- its own docstring says so). Before this day, this module filtered ONLY
2 of the 12 `READER_REFUSALS` (`arc_hors_index`/`index_sans_fichier`, D166 clause 4) plus the sole
`REQUIRED_FIELD_REFUSALS` -- 3 kinds out of 16, measured by an isolated auditor on a real case:
`is_readable(reading) -> False` on Mnemosyne's own repo (some `statut_inconnu`), `plan_gate_run ->
rc 0` on the adopter, the SAME defect.
**Fixed by WIDENING to the whole of `READER_REFUSALS` (12, instead of 2)**.
**`PREREQUISITE_REFUSALS` and `PRODUIT_REFUSALS` remain DELIBERATELY unwired**: `.githooks/
pre-commit` does not call them either (`prerequisite_problems`/`produit_problems` never appear
there) -- wiring them in HERE would therefore be STRICTER than what Mnemosyne imposes on itself,
the very definition of "a floor set on another project's plan [that] is a disguised ceiling"
(A5, cited by `champs_requis_pour`). *The avowal is enough to close them: a gate emitted lighter
than Mnemosyne's own native hook, on clauses Mnemosyne itself leaves to the CALLER, is the same
choice already written for `PRODUIT_REFUSALS`, not an oversight.*

**GAP FOUND BY A 2ND ISOLATED AUDIT (D75, 2026-08-17), FIXED ON THE SPOT: "NO MORE, NO LESS"
WAS FALSE ON ITS OWN TERMS.** `is_readable()` IS A CONJUNCTION OF TWO HALVES --
`not unreadable_reasons(reading, role) and not reading.problems` -- and the widening above had
wired only the SECOND. Measured by the auditor, a healthy witness against three mutations: a plan
with an EMPTY cap, an EMPTY title, or NO ITEM AT ALL is refused by `.githooks/pre-commit`
(`is_readable() -> False`) and yet returned `0 refusals` here -- the same failure mode, WORD FOR
WORD, as the original D176 defect ("the judge is perfect, it is just not wired here").
**Fixed: `juger()` now also calls `unreadable_reasons(reading, role=ROLE_PLAN)`** -- the OTHER
half of `is_readable()`, not a new rule: completing an already partially wired conjunction widens
nothing beyond what Mnemosyne already imposes on itself, it closes the gap between the CLAIM and
the CODE. Cost measured BEFORE wiring, on the same two references: the sibling project (14 doors) and Mnemosyne
itself (1 door) -- **0 reasons found on either**.
**WHAT "SAME RULE AS MNEMOSYNE" DOES NOT MEAN, AND MUST NEVER BE WRITTEN THAT WAY AGAIN**:
`.githooks/pre-commit` ALSO judges dependency order (`plan_ordre.ordonner`, 4 kinds), lineage
(`plan_archive.filiation_problems`, 1 kind) and `ARC_ILLISIBLE` (`plan_registry`, 1 kind) -- THREE
entirely DIFFERENT sources, never wired here, never mentioned before this note. "No more, no
less" claimed TOTAL parity with the hook; the real promise, the ONLY true one, is parity with
`is_readable()` SPECIFICALLY (the 12 `READER_REFUSALS`) plus D176. A sentence that claims more
than it measures is the exact defect this fragment corrects a second time -- it is not repeated
here again, and the EMITTED text (`plan_gate_shell.py`) carries the same correction.

**D176 (2026-08-17) — THE INSTALLED GATE DID NOT HOLD THE OBLIGATION IT PROMISES.**
`.githooks/pre-commit` (Mnemosyne) has long called `required_field_problems`; THIS module — what
an ADOPTING project installs — never called it. Triggered on a plan born from the REAL
`make plan-nouveau`, `**Format** : produit, fini_quand` set by hand in the door, one item left
without either: the direct judge (`required_field_problems`) returns 1 named refusal, this module
returned `rc=0`. **The judge was perfect, it was just not wired here.** Fixed: `juger()` now
calls `champs_requis_pour(..., reading.format_declare)` on EVERY door of the tree (root and
sub-plans, each its own declaration), the same pattern as Mnemosyne's hook — never a second rule
invented.
**Cost measured BEFORE arming, on the only real adopter**: the sibling project, 14 doors declaring
`**Format** : produit`, 168 items — **0 refusals**. Direct level 2, as for Mnemosyne itself (49
items, 0 refusals): the precedent that justified arming THERE justifies arming HERE, at the same
measured cost. If this cost ever stops being zero, this comment is the first to fix.

**REGRESSION FOUND BY THE ISOLATED AUDIT (D75), FIXED ON THE SPOT: `porte` WAS NEVER PASSED TO
`champs_requis_pour`.** The first draft passed `porte = str(projet.plan_path)` — a path relative
to whatever the CALLER typed. `champs_requis_pour` unconditionally requires all SIX fields when
this path RESEMBLES Mnemosyne's own plan door — and GESTURE 2 of this module literally suggests
`"docs"` as an example folder name. An adopter whose plan folder happens to be named `docs`
(nothing exotic) would therefore see SIX fields required despite having declared nothing, and an
explicit one-field declaration silently overridden by the six. See :data:`_JAMAIS_MNEMOSYNE`.

**KILLED ON THE FIRST REAL RUN AGAINST THE SIBLING PROJECT, FOUND BY ACTUALLY INSTALLING IT — not by an
audit.** The first version composed `arc_tree(dossier)` (EVERY `.md` under `plan/`, AT ANY DEPTH,
"nested doors come back as arcs here" — its own docstring says so) directly with
`index_problems`, which requires arcs relative to *this* door. On the sibling project (13 arcs, **each a
SUB-PLAN with its OWN door**), the result: **155 false accusations, rc=2 on an honest state** —
every item of a sub-plan read as though the ROOT door had to cite it.
**Fixed**: :func:`~mnemosyne.production.plan_registry.read_plan_tree` (the same accessor
`scan_plans`/`make plans` use) correctly FOLDS each plan at its own level — a sub-plan is a
separate entry, never flattened into the parent. Verified against the real sibling project: the door alone,
**0 problems**, 14 entries (door + 13 sub-plans).
*My 12 previous witnesses never caught it because their fixture was STRUCTURALLY DEGENERATE
(flat, one level) compared to the real population they claimed to cover.*
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Final

from ..production.plan_format import (
    READER_REFUSALS,
    ROLE_PLAN,
    champs_requis_pour,
    required_field_problems,
    unreadable_reasons,
)
from ..production.plan_registry import read_plan_tree

#: REGRESSION FOUND BY THE ISOLATED AUDIT (D75, 2026-08-17), FIXED HERE. `champs_requis_pour`
#: unconditionally requires all SIX fields when its `door_path` IS Mnemosyne's own plan door --
#: correct for `.githooks/pre-commit`, which judges ONLY this repo's plan. This module NEVER
#: judges Mnemosyne's own plan (that is the hook's job, a separate home): it judges an ADOPTING
#: PROJECT's plan, whose door is `str(projet.plan_path)` -- a path relative to WHATEVER THE
#: CALLER TYPED on the command line, never guaranteed to differ from Mnemosyne's own folder name.
#: Worse: the text EMITTED by this same module (GESTURE 2, `plan_gate_shell.py`) LITERALLY
#: suggests a folder name that collides with it. Measured by the audit: an adopting door landing
#: on that same name, with NO `**Format**` declared, saw all six fields required (`rc=2` on an
#: item that had never promised anything) -- and an EXPLICIT one-field declaration was silently
#: overridden by the six. *A floor set on another project's plan is a disguised ceiling* (the risk
#: `champs_requis_pour` names in its own docstring, D176). This sentinel CANNOT resemble
#: Mnemosyne's own plan door, so it can never match the Mnemosyne case, whatever the adopter's
#: real folder name is.
_JAMAIS_MNEMOSYNE: Final = "<door of an adopting project, never Mnemosyne's own>"


def juger(dossier: Path) -> tuple[str, ...]:
    """The refusals of THIS barrier for the plan rooted at `dossier`, AT EVERY LEVEL -- empty if
    all is well OR if nothing could be judged (fail-open, see the module). Two rules, never
    conflated: structural READABILITY (`is_readable()` in full -- `READER_REFUSALS` (12 kinds,
    D166 clause 4 is a subset of it) AND `unreadable_reasons` (empty title/cap/items), the TWO
    halves of the same conjunction, never just one) and D176 (the obligation of fields THE DOOR
    ITSELF DECLARED).

    Goes through `read_plan_tree`, NOT a manual composition of `arc_tree` + `index_problems`:
    a plan-of-plans (the sibling project) has sub-plans with their OWN door, and flattening everything under
    one door accuses every sub-plan of not citing itself.
    **AND THE DOOR ALONE IS NOT ENOUGH**: `read_plan_tree` returns one entry per sub-plan
    (`plans[1:]`), each with ITS OWN problems -- an orphan INSIDE a sub-plan never bubbles up
    into `plans[0].reading.problems`. Judging only the door would let a real readability defect
    through at every level except the first.

    **D176: EVERY DOOR OF THE TREE DECLARES ITS OWN `**Format**`**, never inherited from a
    parent -- the same accessor as `.githooks/pre-commit` (`champs_requis_pour`), never a second
    rule. A door that declares nothing stays at `requis=()`: today's behavior, unchanged (D176,
    adoption is a CHOICE). **But never the REAL Mnemosyne path as the argument** — see
    :data:`_JAMAIS_MNEMOSYNE`: this module NEVER judges Mnemosyne's own plan."""
    plans = read_plan_tree(dossier, dossier.name)
    refus: list[str] = []
    for projet in plans:
        if projet.reading is None:
            continue  # unreadable for ANOTHER reason -- fail-open, not this barrier's mandate
        porte = str(projet.plan_path)
        refus += [
            f"{porte} -- {p.where} : {p.kind} -- {p.detail}"
            for p in projet.reading.problems
            if p.kind in READER_REFUSALS
        ]
        # The OTHER half of `is_readable()` -- same format as `.githooks/pre-commit` (D163, never
        # a second form): these reasons have no `p.kind`/`p.detail` (not a `PlanProblem`, a
        # sentence about the WHOLE document, not a precise line).
        refus += [
            f"{porte} -- line -   : {raison}"
            for raison in unreadable_reasons(projet.reading, role=ROLE_PLAN)
        ]
        requis = champs_requis_pour(_JAMAIS_MNEMOSYNE, projet.reading.format_declare)
        refus += [
            f"{porte} -- {p.where} : {p.kind} -- {p.detail}"
            for p in required_field_problems(projet.reading, required=requis)
        ]
    return tuple(refus)


def main(argv: list[str] | None = None) -> int:
    """`rc=2` IS AN EXTERNAL CONTRACT, NOT AN INTERNAL DETAIL — `production/plan_gate_shell.py`
    emits a shell wrapper that treats EXACTLY `rc=2` as "the judge refuses" (BR5, fixed on
    2026-08-16 after a bare `exit $?` had blocked EVERY commit on a host with a different
    interpreter). This module (and everything `-m mnemosyne.runtime.plan_gate_run` transitively
    imports to run -- `mnemosyne/__init__.py`, `api`, `ingest`, and EVERY module of `runtime/`)
    must therefore NEVER raise `SystemExit(2)` or exit with 2 for ANY reason other than the
    refusal returned here -- **THIS INVARIANT MATTERS MORE THAN BEFORE** (R3/R4, 2026-08-17): the
    wrapper NO LONGER treats "everything else" as fail-open. `rc=0` (nothing to refuse) lets
    through; `rc=2` refuses for a REAL reason; ANY OTHER code (a stray `SystemExit(2)` INCLUDED,
    indistinguishable from a real refusal) now also blocks, but for the WRONG reason -- "broken
    invocation," never the REAL refusal this function returns. Verified (isolated audit,
    2026-08-16): only two `SystemExit(2)` exist elsewhere in `runtime/` (`youtube_pilot.py`,
    `caption_pilot.py`), both inside their own `__main__` guard, neither imported by
    `runtime/__init__.py` -- NO live collision today. But the invariant is verified by NO
    witness: before adding a `sys.exit(2)` anywhere in this import graph, re-read this comment."""
    args = sys.argv[1:] if argv is None else list(argv)
    if len(args) < 2:
        print(
            "usage: python -m mnemosyne.runtime.plan_gate_run <root> <plan_folder>",
            file=sys.stderr,
        )
        return 0  # incorrect usage -- fail-open, this is not a plan refusal
    dossier = Path(args[1])
    if not dossier.is_dir():
        return 0  # nothing to judge here -- fail-open
    refus = juger(dossier)
    if not refus:
        return 0
    # No fixed prefix ("D166 clause 4"): two distinct rules now live in
    # `refus` (structural readability, READER_REFUSALS, 12 kinds; the obligation of declared
    # fields, D176), and each `ligne` already NAMES its own rule via `p.kind` -- a single prefix
    # would lie about one of the two.
    for ligne in refus:
        print(f"REFUSED: {ligne}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
