"""``make orchestration-borne`` (`E2`) — THE command that renders the number of chats, DERIVED.

The calculation (:mod:`mnemosyne.production.orchestration`) is PURE. It is HERE, at the edge, that
the plan is opened — and **through the SAME reader as `make carte`**: :func:`read_plan_tree` stays
the sole enumeration of arcs, no second disk walk is written here (same discipline as
`carte_run.py`).

Two return codes:

* ``rc 0`` — the ceiling is rendered.
* ``rc 1`` — the plan is **UNREADABLE**: WHY is NAMED and nothing is computed. *A ceiling computed
  on a stale source is an exact lie.*
* ``rc 2`` — the door is **not found**.

Usage::

    make orchestration-borne                              # this repo's plan
    make orchestration-borne POUR=projects/saas/<project>  # a project's plan

Read-only, no brick, no model, no network.
"""

from __future__ import annotations

import sys
from pathlib import Path

from ..production.carte import replier
from ..production.orchestration import (
    CAPACITE_ARBITRAGE_PAR_TOUR,
    borne_chats,
    largeur_vague_en_arcs,
)
from ..production.plan_format import DOOR_FILENAMES, ROLE_PLAN, is_readable, unreadable_reasons
from ..production.plan_registry import read_plan_tree

# IMPORT, NEVER RECOPY: `_racine` carries the `CLAUDE_PROJECT_DIR` fix -- recopying it
# would let a directory-dependent defect be reborn, same discipline as `carte_run.py`.
from .arsenal_run import _racine, pour_et_confusion

#: Same folder as `make carte` — THIS repo's plan door lives under `docs/`.
DOSSIER_DU_PLAN = "docs"


def main(argv: list[str] | None = None) -> int:
    """Render the ceiling. ``rc 0`` rendered · ``rc 1`` plan unreadable · ``rc 2`` door not found ·
    ``rc 2`` a command-line argument, never read, would have silently measured Mnémosyne instead.

    **SAME CLASS AS `carte_run.py`, FOUND IN THE SAME SWEEP — 2026-08-17.** This module reads
    ``POUR`` from the environment, never from ``argv``; a ``--pour "…"`` on the command line was
    swallowed in silence and rendered MNÉMOSYNE's own ceiling instead of the targeted project's —
    reproduced: *"plan measured: Mnémosyne"* when a real path had actually been typed. This exact
    tool is what published a false "1 chat" for a downstream project that night before being retracted with the
    right variable.
    """
    if argv:
        print(
            f"REFUSED: command-line argument(s) {argv!r} — this target reads NOTHING from "
            "argv, only POUR= from the environment (make orchestration-borne POUR=… exports it "
            "for you). A flag here would be swallowed in silence and would measure Mnémosyne "
            "instead of the targeted project.",
            file=sys.stderr,
        )
        return 2
    racine = _racine()
    pour, voisins = pour_et_confusion()
    if not pour and voisins:
        print(
            f"REFUSED: {', '.join(f'{nom}=' for nom in voisins)} defined, but this target reads "
            "ONLY POUR= — make silently ignores an unknown variable, and the ceiling would have "
            "been computed on Mnémosyne's own plan without a word. Rerun with POUR= instead.",
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

    if not any((dossier / nom_porte).is_file() for nom_porte in DOOR_FILENAMES):
        print(
            f"REFUSED: no plan door under {dossier} "
            f"(expected: {' / '.join(DOOR_FILENAMES)}).",
            file=sys.stderr,
        )
        return 2

    plans = read_plan_tree(dossier, nom)
    if not plans:
        print(f"REFUSED: no plan door under {dossier}.", file=sys.stderr)
        return 2

    porteur = plans[0]
    if porteur.reading is None or not is_readable(porteur.reading, role=ROLE_PLAN):
        print(f"REFUSED: {nom}'s plan is UNREADABLE — no ceiling will be computed.", file=sys.stderr)
        for raison in (
            unreadable_reasons(porteur.reading, role=ROLE_PLAN)
            if porteur.reading
            else ("unreadable door",)
        ):
            print(f"  - {raison}", file=sys.stderr)
        return 1

    lectures = [p.reading for p in plans if p.reading is not None and p.reading.items]
    reading, collisions = replier(lectures)
    if collisions:
        print(
            f"WARNING: {len(collisions)} identifier(s) carried by MULTIPLE plans: "
            f"{', '.join(collisions[:5])}{' …' if len(collisions) > 5 else ''} — the wave counts "
            "them only once.",
            file=sys.stderr,
        )

    largeur = largeur_vague_en_arcs(reading)
    borne = borne_chats(reading)
    # C8: what was missing was not a number, it was saying WHAT it was talking about — the first
    # thing a reader in a hurry must be able to check is the population, not only the result.
    print(f"plan measured: {nom}")
    print(f"wave width (startable arcs): {largeur}")
    print(f"arbitration capacity (frozen, measured 2026-08-15): {CAPACITE_ARBITRAGE_PAR_TOUR}")
    print(f"chats to launch: {borne}")
    # THIS CEILING IS NOT A NEED -- added 2026-08-17, on a REAL case.
    # Measurement that triggered it: three TRIVIAL plans (1 arc, 1 item each) born from
    # `make plan-nouveau`, on a project described by its owner as "one huge back-and-forth,
    # a single actor, on-and-off work, no need to delegate" -> the command rendered
    # "chats to launch: 3". The number is CORRECT (three arcs are startable)
    # and reading it as a prescription is WRONG: "to launch" reads like an instruction.
    # NOTE(public-mirror): the source repo keeps the phrase "chats a lancer" byte-for-byte
    # stable here because it is anchored, word for word, to a private planning document's own
    # closed item -- changing it there would break that anchor. That anchor is internal to the
    # private repo and has no counterpart in this public mirror, so this export translates the
    # phrase like any other user-facing string; the constraint that blocked rewording it does
    # not apply here. We ADD what the number does not say, rather than touching what it says.
    print(
        "  this number is a CEILING, never a need: it measures what the PLAN allows, "
        "and nothing of what the WORK demands. A sequential project led by a single actor "
        "is correctly served by ONE chat (the one you are in) — filling this ceiling with no "
        "need costs scaffolding that will have to be dismantled."
    )
    return 0


if __name__ == "__main__":
    # `main()` with NO argument never passed `sys.argv[1:]` -- the guard above was
    # dead before it was born, exactly like in `carte_run.py` before its own fix.
    raise SystemExit(main(sys.argv[1:]))
