"""``make arsenal`` (track 1 · B2 + B3) — the surface that renders the OFFER, and NAMES its gaps.

The judge (:mod:`mnemosyne.production.arsenal`) is PURE: it fetches no population itself. It is
HERE, at the edge, that the Makefile gets read — and this is the only place on the path that
touches a file. The lesson from A2: *a judge that discovers its own population can find it empty
and return a pass*. Here, an unreadable or empty Makefile does not render "all clear": it returns a
command that REFUSES, naming its cause (``rc 2``), because "no target found" and "no target
missing" must never read the same.

**The offer ALWAYS prints, even when the bijection is broken.** This is a reading page before it is
a gate: a filing gap must not deprive an agent of the arsenal. The order is therefore deliberate —
the offer first, the gaps next, and the exit code last (``rc 1``).

Usage::

    make arsenal              # the 30-second page
    make arsenal DETAIL=1     # + what makes each weapon non-portable

Read-only, no brick, no model, no network. Code & docstrings English (D117).
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from typing import Final

from ..production.arsenal import (
    ARSENAL,
    TITRE_DECLARATION,
    armes_declarees,
    lire_la_declaration,
    rendre,
    rendre_le_verdict,
    verdict,
)

#: A **documented** Makefile target: a name at the start of a line, then a ``##``. This is exactly
#: the population ``make help`` displays — hence exactly the one this page replaces. A target
#: without ``##`` is internal and is not an offer: it does not enter the classification.
_CIBLE_DOCUMENTEE = re.compile(r"^([a-zA-Z0-9_-]+):.*?##", re.MULTILINE)


#: The repo root, deduced from this file's own location
#: (``system/lib/mnemosyne/runtime/arsenal_run.py`` -> ``parents[4]``). ``CLAUDE_PROJECT_DIR`` wins
#: when it is set: a default that depends on the current directory never turns red for its own author.
def _racine() -> Path:
    depuis_env = os.environ.get("CLAUDE_PROJECT_DIR", "").strip()
    return Path(depuis_env) if depuis_env else Path(__file__).resolve().parents[4]


#: C8/C9 — ALL the names REALLY measured in use in this Makefile for a plan or project path,
#: never an invented list. **`RACINE` was once part of this list and did NOT exist ANYWHERE
#: in the Makefile — found by an isolated audit (D75, C8), removed.** The measurement that
#: disqualified it was already written, in the same pass, in the log and the item itself
#: ("absent from the real Makefile") — and wired in here anyway. *A measurement published next to
#: the code it is supposed to govern does not govern it.* `grep` the Makefile before adding a name
#: here.
NOMS_DE_CHEMIN_CONNUS: Final = ("POUR", "PLAN", "CHEMIN")


def confusion_de_chemin(nom_attendu: str) -> tuple[str, ...]:
    """The OTHER known path names (C8/C9), present in the environment, while
    `nom_attendu` — the one THIS target actually reads — is not yet read by the caller.

    `make` automatically exports every variable assigned on the command line into the
    environment of the process it launches, WHETHER THE RECIPE INTERPOLATES `$(VAR)` OR NOT (C9:
    wired into a `--flag` by the Makefile, like `PLAN=` for `lot-emit`, or read directly by the
    script via `os.environ`, like `POUR=` for `carte`/`orchestration-borne`/`arsenal` — both
    mechanisms leave the SAME trace in the environment). So a name typed for ONE target stays
    visible, and silently ignored, to another that does not read it. Never inferred from a
    heuristic on the name: this TRIGGERS the refusal on the caller's side, which names precisely
    what was typed and ignored."""
    return tuple(
        nom
        for nom in NOMS_DE_CHEMIN_CONNUS
        if nom != nom_attendu and os.environ.get(nom, "").strip()
    )


def pour_et_confusion() -> tuple[str, tuple[str, ...]]:
    """``(POUR read, neighbors present but IGNORED)`` — the dedicated form that the three targets
    reading ``POUR=`` (``carte``, ``orchestration-borne``, ``arsenal``) have called since C8; C9
    generalizes the computation itself in :func:`confusion_de_chemin`, for any ``nom_attendu``
    — ``lot-emit`` (which expects ``PLAN=``) calls it directly."""
    pour = os.environ.get("POUR", "").strip()
    return pour, confusion_de_chemin("POUR")


def cibles_documentees(texte: str) -> tuple[str, ...]:
    """The targets ``make help`` would display, in file order, without duplicates."""
    return tuple(dict.fromkeys(_CIBLE_DOCUMENTEE.findall(texte)))


def _pour_un_projet(chemin: str, detail: bool) -> int:
    """B4 — render only the weapons THIS plan gate declares it takes.

    A gate that declares nothing is not a fault: the command SAYS so and points back to the full
    arsenal. A declared target that does not exist is NAMED (``rc 1``) — that is the only refusal
    on this path, and it catches a typo, never a choice."""
    porte = Path(chemin)
    try:
        texte = porte.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"REFUSED: unreadable plan gate ({porte}) — {exc}.", file=sys.stderr)
        return 2

    declarees = lire_la_declaration(texte)
    if not declarees:
        print(f"# The arsenal for «{porte}»\n")
        print(
            f"This plan declares nothing — and that is a valid answer: it takes what it wants, when\n"
            f"it needs it. To choose deliberately, paste lines from `make arsenal` under a\n"
            f"`## {TITRE_DECLARATION}` section in its gate."
        )
        return 0

    retenues, inconnues = armes_declarees(declarees, ARSENAL)
    print(rendre(retenues, detail=detail), end="")
    print(f"\n---\n{len(retenues)} weapon(s) declared by {porte}, out of {len(ARSENAL)} offered.")
    if not inconnues:
        return 0
    print(
        f"\n\U000026D4 {len(inconnues)} declaration(s) name NO target at all: {', '.join(inconnues)}.\n"
        "This is not a choice being refused, it is a typo being named — "
        "`make arsenal` lists the exact names."
    )
    return 1


def main(argv: list[str] | None = None) -> int:
    """Print the offer, then the gaps. ``rc 0`` healthy · ``rc 1`` broken bijection · ``rc 2`` read failure."""
    detail = os.environ.get("DETAIL", "").strip() == "1" or "--detail" in (argv or sys.argv[1:])
    pour, voisins = pour_et_confusion()
    if not pour and voisins:
        print(
            f"REFUSED: {', '.join(f'{nom}=' for nom in voisins)} set, but this target only "
            "reads POUR= — make silently ignores an unknown variable, and the general offer "
            "would have been rendered without a word. Replay with POUR= instead.",
            file=sys.stderr,
        )
        return 2
    if pour:
        return _pour_un_projet(pour, detail)
    makefile = _racine() / "Makefile"
    try:
        texte = makefile.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"REFUSED: the Makefile is unreadable ({makefile}) — {exc}.", file=sys.stderr)
        print(
            "This is NOT \"no target to classify\": without the real population, the bijection "
            "means nothing. Replay from the repo root, or set CLAUDE_PROJECT_DIR.",
            file=sys.stderr,
        )
        return 2

    cibles = cibles_documentees(texte)
    if not cibles:
        print(f"REFUSED: no documented target (`## `) found in {makefile}.", file=sys.stderr)
        print(
            "An EMPTY population and a HEALTHY population must not read the same: "
            "the classification cannot assert anything against nothing.",
            file=sys.stderr,
        )
        return 2

    print(rendre(ARSENAL, detail=detail), end="")

    v = verdict(cibles, ARSENAL)
    print(
        f"\n---\n{len(cibles)} documented targets in the Makefile · {len(ARSENAL)} classified here."
    )
    if v.sain:
        print(
            "Bijection VERIFIED in both directions: nothing is offered without saying what it buys."
        )
        return 0
    print("\n\U000026D4 The bijection is BROKEN — every cause is named:\n")
    print(rendre_le_verdict(v))
    print(
        "\nFix: classify the target in `system/lib/mnemosyne/production/arsenal.py` "
        "(rayon + what it buys + nature), or remove the phantom entry."
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
