"""G2 — the EDGE of the circuit breaker. It opens the plan and queries `git`; the judge stays pure.

```
python -m mnemosyne.runtime.disjoncteur_run                       # this repo's plan
python -m mnemosyne.runtime.disjoncteur_run --pour projects/…     # a project's plan
```

**NO SECOND WALK OF THE DISK, NO SECOND `git log`.** The plan is read through
:func:`~mnemosyne.production.plan_registry.read_plan_tree` (the same reader as `make carte`, the
same one the commit gate uses) and the commits through
:func:`~mnemosyne.runtime.routage_journal_run.commits_par_ident` (the same accessor as `C6`, with
its ident pattern already measured against both real repos). *A second enumeration would drift from the
first, and that is exactly what D163 names.*

## Return codes, and what they SEPARATE

```
0  nothing to do, or only ANNOUNCEMENTS — published, never blocking
1  REFUSED: at least one item crossed the SECOND threshold and must be SPLIT
2  NOT MEASURED: plan unreadable/absent, or `git` silent
```

**WHY `annoncer` DOES NOT REFUSE, AND THAT IS THE MECHANISM ITSELF.** *"On the 3rd, ANNOUNCE; on the
4th, SPLIT"* — refusing on the 3rd would remove the announcement, which is precisely the turn that still
gives repair one more chance. Making both thresholds refuse would collapse them into a single one,
and the circuit breaker would be nothing more than a ceiling.

**WIRING STATE AS OF 2026-09-08, MEASURED**: the `make disjoncteur` target exists. It is
**NOT** in `make portes` / `make check`: run against the real plan it **REFUSES** (3 triggers,
one of them an item with 9 repairs in a row). *A gate that is born red is pulled by hand until
its population turns green* — wiring it in would block every commit.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Final

from ..production.disjoncteur import a_decouper, disjoncteur, ouverts, resume
from ..production.plan_format import PlanItem
from ..production.plan_registry import read_plan_tree
from .routage_journal_run import commits_par_ident

#: ``parents[4]`` — ``.../runtime/disjoncteur_run.py`` climbs back up to the repo root;
#: ``parents[3]`` would point to ``system/`` and would make the plan unreachable + `git log` empty,
#: i.e. a false GREEN. A separate test judges THIS value specifically.
RACINE: Final = Path(__file__).resolve().parents[4]

#: The folder that carries this repo's plan gate — the same choice as `carte_run`: name the
#: FOLDER, never the file; it is `read_plan_tree` that knows the gate names.
_DOSSIER_DU_PLAN: Final = "docs"


def items_du_plan(dossier: Path, nom: str) -> tuple[PlanItem, ...]:
    """All the items of the plan rooted at ``dossier`` — an EMPTY tuple when the plan is unreadable,
    absent, or has no item at all.

    **A SINGLE EMPTY RETURN, NOT TWO.** A ``None`` sentinel distinct from the empty tuple would
    look richer: the single caller treats them the same way (both are "NOT MEASURED"), so the
    distinction would be a DEAD guarantee wearing a living name — and a sabotage that swapped
    the two would survive the whole battery without changing a single observable behavior.

    **THE WHOLE TREE, never ``plans[0]``**: keeping only the top gate and discarding the sub-plans
    already made a downstream project draw *21 steps out of 168*, `rc 0`, without a word."""
    plans = read_plan_tree(dossier, nom)
    collectes: list[PlanItem] = []
    for plan in plans:
        if plan.reading is not None:
            collectes.extend(plan.reading.items)
    return tuple(collectes)


def main(argv: list[str] | None = None, *, racine: Path | None = None) -> int:
    """``racine`` is injectable FOR TESTS, never for production: its ``None`` default
    avoids freezing a value evaluated at import time, and lets a separate test judge the
    REAL value (:data:`RACINE`)."""
    args = list(sys.argv[1:] if argv is None else argv)
    pour = ""
    while args:
        jeton = args.pop(0)
        if jeton == "--pour" and args:
            pour = args.pop(0)
    r = RACINE if racine is None else racine
    dossier = (r / pour) if pour else (r / _DOSSIER_DU_PLAN)
    nom = pour or "Mnémosyne"

    items = items_du_plan(dossier, nom)
    # **AN EMPTY POPULATION AND AN ABSENT POPULATION EXIT THROUGH THE SAME GATE, AND THAT IS INTENTIONAL.**
    # A readable plan that yields NO item at all would give "0 item examined — no trigger",
    # i.e. the falsest green there is. Closing both with a single test closes the CLASS;
    # closing only one would leave a live sabotage (`return ()` instead of `return None`).
    if not items:
        print(
            f"\U000026A0\U0000FE0F circuit breaker: NOT MEASURED — no readable plan item under {dossier}. "
            "Zero item examined is not a green: it is an instrument failure.",
            file=sys.stderr,
        )
        return 2

    par_ident = commits_par_ident(r)
    if par_ident is None:
        print(
            "\U000026A0\U0000FE0F circuit breaker: NOT MEASURED — `git log` did not answer. "
            "A silent history would yield null series, i.e. a false green.",
            file=sys.stderr,
        )
        return 2

    etats = disjoncteur(items, par_ident)
    print(resume(etats, juges=ouverts(items)), end="")
    return 1 if a_decouper(etats) else 0


if __name__ == "__main__":  # pragma: no cover - [OPERATOR] surface
    raise SystemExit(main())
