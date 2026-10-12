"""G10 -- the EDGE of the handover. It pulls the INDEPENDENT MEASUREMENT; the judge stays pure.

```
python -m mnemosyne.runtime.passation_run --pair chat-3 --etat rien_a_traiter --source mesure
```

**THIS EDGE TAKES THE MEASUREMENT IN PLACE OF THE DECLARANT, AND THAT IS THE POINT.** A third
party who writes "chat-3 has nothing left to handle" has nothing to copy out by hand: they run this
command, it re-pulls both halves (the PATH and the DURABILITY) and **refuses** if either one says
otherwise.

The two halves, and where they come from -- **no second reader**:

* the **PATH**: the arcs the pair declares it holds (`ui_contract._qui_tient_par_arc`, the reader
  behind `make ui-json`) crossed with the plan's still-open items (`read_plan_tree` + `carte`).
* the **DURABILITY**: `git status --porcelain`, read by `non_committe.lire` and filtered by
  `non_committe.est_parque` -- the judge from the `Stop` hook, reused, never recopied.

## The return codes

```
0  handover FOUNDED    -- source = measurement, and the measurement confirms it
1  REFUSED             -- taken on faith, or contradicted by the measurement
2  NOT MEASURED        -- `git` silent or plan unreadable: the measurement could NOT be taken
```

**STATE OF THE WIRING AS OF 2026-09-08, MEASURED**: `make passation` exists. It is **NOT** in
`make portes` / `make check`, **and that is not a gap** — it is a GESTURE, taken at the moment
someone writes about a pair, never a periodic watch. It stays **VOLUNTARY**: nothing forces a
third party to call it before writing a sentence about a pair. **EXPLICIT ADMISSION: the rule
"never declare a pair on faith" has NO barrier that makes it impossible to violate.** This module
makes the gesture *available and capable of refusing*; it does not make the gesture *mandatory*.
The only place that could make it mandatory is the commit gate, and putting a judge there on
free-form prose would be a text detector, not a barrier.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Final

from ..production.carte import carte_par_arc
from ..production.non_committe import est_parque, lire as lire_porcelain
from ..production.passation import (
    Declaration,
    Mesure,
    juger,
    resume,
)
from ..production.plan_registry import read_plan_tree
from ..production.routage_journal import STATUTS_FERMES
from ..production.ui_contract import _qui_tient_par_arc

#: ``parents[4]`` -- the repository root. ``parents[3]`` (``system/``) would yield an empty
#: plan, empty stations, and a `git status` outside the repo: a handover "confirmed" by nothing.
RACINE: Final = Path(__file__).resolve().parents[4]

_DOSSIER_DU_PLAN: Final = "docs"
_DOSSIER_DES_POSTES: Final = "docs/postes"


def _porcelain(racine: Path) -> str | None:
    """`git status --porcelain`, or ``None`` when the measurement CANNOT be taken."""
    try:
        sortie = subprocess.run(  # noqa: S603, S607
            ["git", "-C", str(racine), "status", "--porcelain"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return sortie.stdout if sortie.returncode == 0 else None


def mesurer(racine: Path, pair: str) -> Mesure:
    """The INDEPENDENT measurement of ``pair``'s state. ``prise=False`` when it could not be taken.

    **ONE MISSING HALF INVALIDATES THE WHOLE MEASUREMENT.** Returning the open items with a
    silent `git status` would give a half-true measurement, and a handover confirmed by the half
    that could be read -- exactly a downstream project's mistake, turned back on itself."""
    porcelain = _porcelain(racine)
    plans = read_plan_tree(racine / _DOSSIER_DU_PLAN, "Mnémosyne")
    lectures = [p.reading for p in plans if p.reading is not None]
    if porcelain is None or not lectures:
        return Mesure(pair=pair, prise=False)

    tenants, degrade = _qui_tient_par_arc(racine / _DOSSIER_DES_POSTES)
    if degrade:
        return Mesure(pair=pair, prise=False)
    siens = frozenset(arc for arc, noms in tenants.items() if pair in noms)

    ouverts: list[str] = []
    for lecture in lectures:
        for arc in carte_par_arc(lecture):
            if arc.etiquette not in siens:
                continue
            ouverts += [
                item.ident
                for item in lecture.items
                if item.ident.startswith(arc.etiquette) and item.status not in STATUTS_FERMES
            ]

    depot = lire_porcelain(pair, porcelain)
    non_durables = tuple(c for c in depot.chemins if not est_parque(c))
    return Mesure(
        pair=pair,
        items_ouverts=tuple(sorted(set(ouverts))),
        non_durables=non_durables,
    )


def main(argv: list[str] | None = None, *, racine: Path | None = None) -> int:
    """``racine`` injectable FOR WITNESSES, never for production."""
    args = list(sys.argv[1:] if argv is None else argv)
    pair = ""
    etat = ""
    source = ""
    while args:
        jeton = args.pop(0)
        if jeton == "--pair" and args:
            pair = args.pop(0)
        elif jeton == "--etat" and args:
            etat = args.pop(0)
        elif jeton == "--source" and args:
            source = args.pop(0)
    r = RACINE if racine is None else racine

    if not pair:
        print(
            "handover: NOT MEASURED — no pair named. "
            "Usage: --pair chat-N --etat rien_a_traiter|en_cours|bloque --source mesure|parole",
            file=sys.stderr,
        )
        return 2

    declaration = Declaration(pair=pair, etat=etat, source=source)
    mesure = mesurer(r, pair)
    trouves = juger(declaration, mesure)
    if not mesure.prise:
        print(resume(trouves, declarations=1), end="", file=sys.stderr)
        return 2
    print(resume(trouves, declarations=1), end="")
    return 1 if trouves else 0


if __name__ == "__main__":  # pragma: no cover - operator-facing surface
    raise SystemExit(main())
