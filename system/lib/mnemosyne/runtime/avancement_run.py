"""``make avancement`` (P3) — the EDGE: it reads the plan, the judge returns the `louche` (weighted
progress reading).

The judge (:mod:`mnemosyne.production.avancement`) reads nothing itself. Here, and only here, do we
touch disk: the plan is read through the PRODUCTION accessor (``plan_registry.read_plan_tree``),
never through a ``grep`` — *a figure pulled by a reader other than the format's own judge is not
the same figure*, and this repository has already paid for a parallel reading of the plan once.

**THIS IS NOT A GATE.** ``rc 0`` always, once the `louche` reading could be taken, whatever the
progress is — 3% and 97% both exit 0. The only non-zero exit is an **instrument failure**: an
unreadable plan (``rc 2``) or an empty population (``rc 2``). *Low progress is a fact, never a
fault; refusing it would manufacture `` marks.*

Operator-facing prose is French in the source (D117); translated to English throughout this mirror.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from ..production.avancement import Item, SansPopulation, louche, rendre
from ..production.plan_registry import read_plan_tree

#: The plan picked when nobody says which one: Mnemosyne's own. It does not live under
#: ``projects/`` (it is the only one in that case), and it is exactly the plan the operator asks
#: for the `louche` reading of.
DOSSIER_PAR_DEFAUT = "docs"


def _racine() -> Path:
    depuis_env = os.environ.get("CLAUDE_PROJECT_DIR", "").strip()
    return Path(depuis_env) if depuis_env else Path(__file__).resolve().parents[4]


def items_du_plan(dossier: Path) -> tuple[Item, ...]:
    """The items of the plan rooted at ``dossier``, flattened — **the module's only disk access**.

    The nested sub-plans returned by :func:`~mnemosyne.production.plan_registry.read_plan_tree`
    are **included**: they are part of the effort, and excluding them would produce a flattering
    `louche` reading over a population silently amputated. An unreadable plan has no reading
    (``reading is None``): it contributes no items, and the caller sees it as a total that is not
    what it expects — which is why the edge below **refuses** a zero total rather than publishing
    ``0%``.
    """
    trouves: list[Item] = []
    for plan in read_plan_tree(dossier, dossier.name):
        if plan.reading is None:
            continue
        for item in plan.reading.items:
            trouves.append(
                Item(
                    ident=item.ident,
                    statut=item.status,
                    taille=item.field("taille") or "",
                )
            )
    return tuple(trouves)


def main(argv: list[str] | None = None) -> int:
    """``rc 0`` the `louche` reading is published · ``rc 2`` instrument failure (unreadable or empty plan)."""
    arguments = sys.argv[1:] if argv is None else argv
    demande = os.environ.get("DOSSIER", "").strip() or (
        arguments[0] if arguments else DOSSIER_PAR_DEFAUT
    )
    dossier = Path(demande)
    if not dossier.is_absolute():
        dossier = _racine() / dossier

    if not dossier.is_dir():
        print(
            f"REFUSED: `{dossier}` is not a directory — there is no plan to read, "
            "so no `louche` reading. This is not '0% done'.",
            file=sys.stderr,
        )
        return 2

    try:
        mesure = louche(items_du_plan(dossier))
    except SansPopulation as panne:
        print(f"REFUSED: {panne}.", file=sys.stderr)
        print(
            "Remedy: `make plans` says which of the plan's files is unreadable. "
            "A `louche` reading over zero items is not a progress reading, it is a mute "
            "instrument.",
            file=sys.stderr,
        )
        return 2

    print(rendre(mesure))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
