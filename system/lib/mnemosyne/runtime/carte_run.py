"""``make carte`` ("plans" workstream · B3) — THE single surface for "where things stand".

The computation (:mod:`mnemosyne.production.carte`) is PURE: it reads no file. It is HERE, at the
edge, that the plan gets opened — and **through the same reader everyone else uses**:
:func:`read_plan_tree` is the sole enumeration of a plan's arcs. *A second walk of the disk has
already refused the second sub-plan of a plan while the gate accepted it* — we do not write a third.

**WHY THIS TARGET EXISTS, and the item writes it in black and white**: the map is pushed by the
``SessionStart`` hook, **which is fail-open** — if it breaks, it stays silent, and nobody knows. The
map must therefore stay **pullable by hand**. Without this command, the item has **no** surface at
all.

**AND THERE IS ONLY ONE.** The ``*Deliverable*`` says *"`make carte`, THE single surface"*: no
second command, no "short" variant. A second proposal surface would be exactly the duplication the
integration map forbids.

Three return codes, and they do not say the same thing:

* ``rc 0`` — the map was rendered.
* ``rc 1`` — the plan is **UNREADABLE**: we NAME why and draw nothing. *An accurate view of a stale
  source is an exact lie* — drawing a map over a broken plan would be worse than drawing nothing.
* ``rc 2`` — the door is **not found**: "no plan here" and "broken plan" are two different
  statements, and conflating them would send someone hunting for a defect where there is none.

Usage::

    make carte                                   # this repo's plan
    make carte POUR=projects/saas/<project>      # a project's plan

Read-only, brick-free, model-free, network-free. English prose in this public mirror (D117).
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

from ..production.carte import lire, lire_peremption, rendre, replier
from ..production.plan_format import DOOR_FILENAMES, ROLE_PLAN, is_readable, unreadable_reasons
from ..production.plan_registry import read_plan_tree

# IMPORTED, NEVER RECOPIED: `_racine` carries the `CLAUDE_PROJECT_DIR` fix, and recopying it
# would resurrect a defect that depends on the current working directory — the class of defect that
# NEVER reddens for its own author (measured: 7/11 for a third party, 0/11 for the author).
from .arsenal_run import _racine, pour_et_confusion
from .derive_run import resume as derive_resume
from .routage_journal_run import resume as routage_resume

#: The folder that carries this repo's own plan door. The door itself is called ``PLAN.md``
#: (D176) — so it is not named here, only its folder: `read_plan_tree` is the one that knows the
#: door names, and there is only one place where they live.
DOSSIER_DU_PLAN = "docs"

#: The file where a plan DECLARES what is expiring, next to its door. Data, never code:
#: importing a project's own harness just to read its table would cross a bubble.
NOM_DE_LA_PEREMPTION = "PEREMPTION.md"


def main(argv: list[str] | None = None) -> int:
    """Render the map. ``rc 0`` rendered · ``rc 1`` plan unreadable · ``rc 2`` door not found ·
    ``rc 2`` a command-line argument, never read, would have drawn Mnémosyne silently.

    **FOUND AGAINST A DOWNSTREAM PROJECT, 2026-08-17 — THE SAME TRAP AS `POUR=`/`PLAN=`, ONE NOTCH LOWER.**
    ``argv`` existed in the signature as a promise never kept: nothing here ever read a
    ``--pour``. The research project's orchestrator invoked ``carte_run --pour "…"`` directly (outside the
    documented ``make carte POUR=…``, where it is `make` that exports `POUR` into the environment)
    — the flag was silently swallowed, no ``POUR`` ever reached :func:`pour_et_confusion`, and
    MNÉMOSYNE's map came out, labeled, plausible, for the wrong project. *A reader that accepts
    arguments it never reads is not permissive: it is blind with a smile.* Refusing a non-empty
    ``argv`` instead of staying silent about it closes the class without having to write a parser
    — the only interface that works remains ``POUR=`` through the environment.
    """
    if argv:
        print(
            f"REFUSED: command-line argument(s) {argv!r} — this target reads NOTHING from "
            "argv, only POUR= from the environment (make carte POUR=… exports it for you). "
            "A flag here would be silently swallowed and would draw Mnémosyne instead of the "
            "intended project.",
            file=sys.stderr,
        )
        return 2
    racine = _racine()
    pour, voisins = pour_et_confusion()
    if not pour and voisins:
        print(
            f"REFUSED: {', '.join(f'{nom}=' for nom in voisins)} defined, but this target reads "
            "ONLY POUR= — make silently ignores an unknown variable, and Mnémosyne's plan map "
            "would have been drawn without a word. Replay with POUR= instead.",
            file=sys.stderr,
        )
        return 2
    dossier = Path(pour) if pour else racine / DOSSIER_DU_PLAN
    if not dossier.is_absolute():
        dossier = racine / dossier
    nom = pour or "Mnémosyne"

    if not dossier.is_dir():
        print(f"REFUSED: {dossier} is not a folder — no door to read.", file=sys.stderr)
        return 2

    # THE DOOR IS LOOKED UP BY ITS NAME, not by the reader's verdict: `read_plan_tree` returns
    # an UNREADABLE plan even when NO door exists at all, so relying on it conflated "no plan
    # here" with "broken plan". Door names come from `plan_format`, never recopied.
    if not any((dossier / nom_porte).is_file() for nom_porte in DOOR_FILENAMES):
        print(
            f"REFUSED: no plan door under {dossier} "
            f"(expected: {' / '.join(DOOR_FILENAMES)}).\n"
            "\"No plan here\" and \"broken plan\" are two different statements: this is the "
            "former. Add a door, or point at another folder with POUR=.",
            file=sys.stderr,
        )
        return 2

    plans = read_plan_tree(dossier, nom)
    if not plans:
        print(
            f"REFUSED: no plan door under {dossier}.\n"
            "\"No plan here\" and \"broken plan\" are two different statements: this is the "
            "former. Add a door, or point at another folder with POUR=.",
            file=sys.stderr,
        )
        return 2

    # **THE WHOLE TREE, NOT `plans[0]`.** The edge kept the door and discarded the sub-plans: on
    # the research project, the map drew **21 steps out of 168**, `rc 0`, without a word -- so the item's clause
    # ("the map rendered on the research project's plan, 168 steps") had **no left-hand side** at all.
    # Invisible here because Mnemosyne's own plan is FLAT (`plans[0]` is 49/49 there) while the research project's
    # is a TREE. *An accurate view of a TRUNCATED source is an exact lie.*
    porteur = plans[0]
    if porteur.reading is None or not is_readable(porteur.reading, role=ROLE_PLAN):
        print(f"REFUSED: {nom}'s plan is UNREADABLE — no map will be drawn.", file=sys.stderr)
        for raison in (
            unreadable_reasons(porteur.reading, role=ROLE_PLAN)
            if porteur.reading
            else ("unreadable door",)
        ):
            print(f"  - {raison}", file=sys.stderr)
        print(
            "\nAn ACCURATE view of a STALE source is an exact lie: we do not draw a map over a "
            "broken plan. `make plans` says what needs fixing.",
            file=sys.stderr,
        )
        return 1

    # **WHAT FALLS OUT OF THE FOLD MUST BE NAMED — and it was NOT.** The filter below silently
    # discards any sub-plan that is unreadable or empty. Measured by the second audit: a single
    # invalid byte in ONE item of ONE of the research project's sub-plans, and the command returned `rc 0`,
    # "14 plans folded · **167** steps" -- **without a word**, for 168. The refusal existed, named,
    # inside `reading.problems`, and **nobody read it**. *A guarantee dies at the caller that
    # discards its result* -- and that is the class this module declares itself to close, reopened
    # one level down, under a count line that looks like a status report.
    # We NAME it and draw anyway: refusing outright would blind us on 167 healthy items because of
    # a single broken one. The map is a proposal nerve, not a gate -- but a count that stays silent
    # about what it lost is worse than a refusal.
    ecartes = tuple(
        p.name for p in plans if p.reading is None or not p.reading.items
    )
    if len(plans) > 1 and ecartes:
        print(
            f"\U000026A0\U0000FE0F {len(ecartes)} sub-plan(s) DROPPED from the count — unreadable or itemless: "
            f"{', '.join(ecartes[:5])}{' …' if len(ecartes) > 5 else ''}.\n"
            "The numbers below DO NOT COUNT THEM. `make plans` says what needs fixing.",
            file=sys.stderr,
        )

    lectures = [p.reading for p in plans if p.reading is not None and p.reading.items]
    # **THE ARC IS THE SUB-PLAN, and this is where we know it.** After `replier`, the items'
    # origin is lost: the judge can only GUESS it from then on, and it guesses differently
    # depending on the plan's shape. Measured: the identifier prefix scores **11/11** on Mnemosyne
    # (FLAT plan) and **3 out of 14** on the research project (TREE plan) -- `A01-1`, `A03-5`, `A11-2` all collapse
    # onto "A". That is, exactly where I had tested it, WRONG where the clause matters.
    # Only the edge walked the tree, so it is the one that NAMES the arcs. `plan.name` is the name
    # the plan gives itself ("ARC 11 — …"), never a reconstructed prefix.
    # **AND ONLY WHEN THERE ARE SUB-PLANS.** My first injection also set them on a FLAT plan --
    # where the tree renders only ONE door -- so every item received the same arc and Mnemosyne
    # announced "1 arcs" for 11. *A fix that repairs the TREE shape by breaking the FLAT shape did
    # not fix anything, it just moved the defect.* On a flat plan, the arc IS the item's `source`
    # file (measured: 11 sources for 11 arcs), and that is the fold the judge applies on its own.
    arcs = (
        {
            item.ident: plan.name
            for plan in plans
            if plan.reading is not None and plan.reading.items
            for item in plan.reading.items
        }
        if len(lectures) > 1
        else None
    )
    reading, collisions = replier(lectures)
    if collisions:
        # NAMED, never swallowed: two plans carrying the same identifier would make a dependency
        # point at the wrong item, and the order would be wrong SILENTLY. We draw anyway (the map
        # proposes, it does not refuse) but the reader knows what they are reading.
        print(
            f"\U000026A0\U0000FE0F {len(collisions)} identifier(s) carried by MULTIPLE plans: "
            f"{', '.join(collisions[:5])}{' …' if len(collisions) > 5 else ''} — the order "
            "confuses them, `make plans` shows where.",
            file=sys.stderr,
        )
    # "WHAT IS EXPIRING" — the population is DECLARED BY THE PROJECT, next to its door, never
    # inferred here: an expiry is a JUDGMENT ("does what we lose by waiting ever get caught up?"),
    # not a computable fact. A plan that declares none has none, and that is a TRUE answer — not a
    # silence. A missing or unreadable file => no expiry, never an exception: the map is a proposal
    # nerve, and *a per-item guarantee that raises kills the batch*.
    declaration = dossier / NOM_DE_LA_PEREMPTION
    try:
        perissables = lire_peremption(declaration.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError):
        perissables = {}
    inconnus = sorted(set(perissables) - {item.ident for item in reading.items})
    if inconnus:
        # NAMED, never swallowed: an expiry on an identifier absent from the plan is a STALE
        # declaration, and it would disappear without a sound — `file_d_attente` ignores what it
        # does not know.
        print(
            f"\U000026A0\U0000FE0F {len(inconnus)} expiry(ies) declared on an identifier ABSENT from the plan: "
            f"{', '.join(inconnus[:5])}{' …' if len(inconnus) > 5 else ''} — "
            f"{declaration.name} is stale on these lines.",
            file=sys.stderr,
        )

    if len(lectures) > 1:
        print(f"({len(lectures)} plans folded · {len(reading.items)} steps)")
    print(rendre(lire(reading, arcs=arcs, perissables=perissables or None), projet=nom), end="")

    # **THE WIRING OF `D1`, AND IT MISSED EIGHTEEN COMMITS.** `plan_derive` produced both
    # ratchets with NO caller existing anywhere in `system/` — *the barrier nothing calls*, the
    # fifth occurrence of the class in one day, this one on its own author's module.
    # `D1`'s `*Deliverable*` says in so many words *"NO new surface: they ship through
    # `make tick` AND through `make carte`"*: so the cost is paid HERE rather than inventing a
    # target that would contradict the item. **MEASURED COST, and it is real**: `make carte`
    # goes from **0.15 s to ~0.6 s** — a `git log --numstat` over 255 commits (5,228 lines)
    # computed on every call, including at session startup. *A door slower than the wall is never
    # used*: if this quadrupling becomes a problem, the answer is to declare the window closed and
    # freeze it, not to silently withdraw the output.
    # **Fail-open, like everything bordering the map**: an unreadable drift measurement must not
    # take the map down with it, since the map is the main surface. The edge already PUBLISHES its
    # own inability to measure.
    #
    # **2026-08-17, FOUND BY AN AUTONOMY PROBE, IN REAL USE: THESE TWO SECTIONS WERE
    # PUBLISHING MNEMOSYNE'S OWN NUMBERS UNDER ANOTHER PROJECT'S MAP, WITHOUT A WORD.** On a
    # another project's plan barely 30 seconds old, `make carte POUR=…` rendered "share done 24.1%" and
    # "31 item(s) closed" -- Mnemosyne's EXACT numbers, identical to `make carte` WITHOUT `POUR=`.
    # This was not a wiring oversight: `derive_resume` validates a FROZEN historical window that is
    # Mnemosyne-specific (`DEPOT = "projects/.git"`, `DEPUIS`/`JUSQUA` fixed, `D1`), and
    # `routage_resume` looks for a plan under `<racine>/docs` (this repo's own convention). Neither
    # one knows how to measure ANYTHING but Mnemosyne -- retargeting them at `dossier` would produce
    # a "NOT MEASURED" that names an internal path (`projects/.git`), not a readable explanation.
    # **The right answer is therefore explicit silence when `POUR=` targets ANOTHER project** --
    # never an empty histogram that would look like a measurement, never Mnemosyne's own numbers
    # recycled silently.
    if pour:
        print()
        print(
            "drift (D1) and routing journal (C6): NOT RENDERED for "
            f"{nom} — these two measurements only know how to read Mnémosyne's own history and "
            "conventions (frozen D1 window, plan under `docs/` for C6), never another project's. "
            "Publishing Mnémosyne's numbers here would be an exact lie."
        )
    else:
        try:
            print()
            # THE REPO ROOT, never `dossier` — which is `docs/`: my first wiring passed it the
            # PLAN's folder, and `projects/.git` does not exist under `docs/`. The page SHOUTED
            # "DRIFT NOT MEASURED" instead of staying silent, and that is what caught the bug in
            # its first minute. *An edge that publishes its own inability to measure debugs itself.*
            # `aujourdhui` INJECTED HERE, AT THE EDGE — 2026-08-17: the page did not read the
            # clock and so never stated the AGE of its last measured day (see age_et_depot).
            print(derive_resume(_racine(), aujourdhui=date.today().isoformat()), end="")
        except Exception as exc:  # noqa: BLE001 — the map comes first: we NAME it and continue
            print(f"\U000026A0\U0000FE0F drift not rendered ({exc.__class__.__name__}) — the map itself is complete.")

        # C6: *"no new surface"* -- the same gesture as D1 just above, for the same reason: the
        # item's `*Deliverable*` names `make carte` as the ONLY edge, so the cost is paid here,
        # never through a new target that would contradict the item. Always THIS repo's plan (never
        # `POUR=`'s, excluded above): Mnémosyne's velocity is measured on ITS OWN history, not on
        # the project being looked at in the same pass.
        try:
            print()
            print(routage_resume(_racine()), end="")
        except Exception as exc:  # noqa: BLE001 — the map comes first: we NAME it and continue
            print(
                f"\U000026A0\U0000FE0F routing journal not rendered ({exc.__class__.__name__}) — the map itself "
                "is complete."
            )
    return 0


if __name__ == "__main__":
    # THIS USED TO BE `main()` WITH NO ARGUMENT — so my first fix for this defect (the
    # `if argv:` inside `main`) was DEAD ON ARRIVAL: nothing here ever passed `sys.argv[1:]`
    # through, so `argv` was always `None` no matter what was typed on the command line. The
    # provocation that found it: replay `--pour "…"` after the first fix and watch it still not
    # bite.
    raise SystemExit(main(sys.argv[1:]))
