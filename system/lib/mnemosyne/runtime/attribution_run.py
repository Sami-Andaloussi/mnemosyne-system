"""P2 - the EDGE of the arc attribution registry. It alone opens the disk.

```
python -m mnemosyne.runtime.attribution_run                        # audit the registry
python -m mnemosyne.runtime.attribution_run --arc H --pour chat-4  # THE DOOR for the emitter
```

**NO SECOND READER OF POSTS, NO SECOND WALK OF THE PLAN.** Claims are read via
:func:`~mnemosyne.production.ui_contract._qui_tient_par_arc` - **the reader `make ui-json`
already uses** - and arcs via `carte_par_arc` over `read_plan_tree`, like `make carte`.

**`_qui_tient_par_arc` IS PRIVATE, AND IMPORTING IT IS A DELIBERATE CHOICE.** The alternative
was to write a second parser for the `arcs:` field; it would have drifted from the first at the
first change of shape, and its own header already warns that *"the day the shape of the `arcs:`
field changes, this panel can start lying WITHOUT ANYONE KNOWING IT"*. **One single home read by
two callers beats two homes.** Gesture proposed to the orchestrator: promote this name to
public, one line, outside the scope of this batch.

## Return codes

```
0  healthy registry, or only STALE holds (published, never blocking)
1  REFUSED: collision, or a claim on an arc absent from the plan
2  NOT MEASURED: plan unreadable/absent, or post reading DEGRADED
```

**A DEGRADED READ IS NOT A HEALTHY REGISTRY.** If a post could not be read, the arcs it
claimed are invisible - so a collision can exist and go unseen. Returning `0` on that would be
asserting an absence that was never measured.

**WIRING STATE AS OF 2026-09-08, MEASURED**: the `make attribution` target exists. It is
**NOT** in `make portes` / `make check`: it **REFUSES today** on a REAL collision (arc `H`
claimed by two chats). Its place is **before `make lot-emit`**, not at the commit - an
attribution is judged at the moment it is granted.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Final

from ..production.attribution import peut_attribuer, resume, verdicts
from ..production.carte import carte_par_arc
from ..production.plan_registry import read_plan_tree
from ..production.ui_contract import _qui_tient_par_arc

#: ``parents[4]`` - the repo root. ``parents[3]`` would point at ``system/``: no plan, no
#: posts, hence an EMPTY registry, hence a green. A separate witness judges THIS value specifically.
RACINE: Final = Path(__file__).resolve().parents[4]

_DOSSIER_DU_PLAN: Final = "docs"
_DOSSIER_DES_POSTES: Final = "docs/postes"


def etat_du_plan(racine: Path) -> tuple[frozenset[str], frozenset[str]] | None:
    """``(all arcs, the FINISHED arcs)`` of this repo's plan - ``None`` if nothing is readable."""
    plans = read_plan_tree(racine / _DOSSIER_DU_PLAN, "Mnémosyne")
    lectures = [p.reading for p in plans if p.reading is not None]
    if not lectures:
        return None
    arcs = tuple(a for lecture in lectures for a in carte_par_arc(lecture))
    if not arcs:
        return None
    return frozenset(a.etiquette for a in arcs), frozenset(
        a.etiquette for a in arcs if a.etat == "fini"
    )


def main(argv: list[str] | None = None, *, racine: Path | None = None) -> int:
    """``racine`` injectable FOR WITNESSES/TESTS, never for production."""
    args = list(sys.argv[1:] if argv is None else argv)
    arc = ""
    pour = ""
    while args:
        jeton = args.pop(0)
        if jeton == "--arc" and args:
            arc = args.pop(0)
        elif jeton == "--pour" and args:
            pour = args.pop(0)
    r = RACINE if racine is None else racine

    etat = etat_du_plan(r)
    if etat is None:
        print(
            f"\U000026A0\U0000FE0F attribution: NOT MEASURED - no readable arc under {r / _DOSSIER_DU_PLAN}. "
            "Zero arcs is not a healthy registry: it is an instrument failure.",
            file=sys.stderr,
        )
        return 2
    arcs_du_plan, arcs_finis = etat

    tenants, degrade = _qui_tient_par_arc(r / _DOSSIER_DES_POSTES)
    if degrade:
        print(
            "\U000026A0\U0000FE0F attribution: NOT MEASURED - at least one post is UNREADABLE. The arcs it "
            "claimed are invisible, so a collision can exist without being seen.",
            file=sys.stderr,
        )
        return 2

    if arc:
        refus = peut_attribuer(arc, a_qui=pour, tenants=tenants, arcs_du_plan=arcs_du_plan)
        if refus is None:
            print(
                f"\U00002705 arc {arc} assignable to {pour or '(nobody named)'} - free, or already theirs."
            )
            return 0
        print(f"\U000026D4 {refus.phrase}", file=sys.stderr)
        return 1

    trouves = verdicts(tenants, arcs_du_plan=arcs_du_plan, arcs_finis=arcs_finis)
    print(resume(trouves, arcs=len(arcs_du_plan), tenus=len(tenants)), end="")
    return 1 if any(v.refuse for v in trouves) else 0


if __name__ == "__main__":  # pragma: no cover - [OPERATOR] surface
    raise SystemExit(main())
