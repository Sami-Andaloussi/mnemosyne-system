"""``make lot-emit`` — the EDGE of E4: reads the plan, assembles the mandate, publishes it.

This repo's `*-emit` pattern: this module resolves the root, reads the plan with the production
accessor (:func:`~mnemosyne.production.plan_registry.scan_plans`, the FOLDED reading — never
`read_plan` on the door alone, which returns an empty population), and delegates everything else
to :mod:`~mnemosyne.production.lot_emit`. The default mode writes nothing (`stdout` only);
``--emettre-lots``/``--assembler-lots`` (C5) write/read lot files in ``--dossier``
— it is HERE, and nowhere in `lot_emit.py`, that `Assemblage.complet=False` becomes a real
REFUSAL (code 2), never a boolean left to fall through in silence.

**WHAT `--assembler-lots` ASSUMES, WRITTEN DOWN RATHER THAN HIDDEN**: it re-splits the mandate
with the SAME `TAILLE` as the emission to recover the same lots (deterministic, `decouper`
guarantees it for equal input) — if the arc's set of open items changed between the two calls (an
item closed in the meantime, for instance), the lots will no longer match the `IN` files already
written. Not a hidden bug: this repo's `*-emit` pattern does no coordination I/O beyond this, and
a lot already emitted assumes its mandate is stable until assembly.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ..production import lot_emit
from ..production.carte import replier
from ..production.parc import Lot
from ..production.orchestration import borne_chats
from ..production.plan_format import PlanItem
from ..production.plan_registry import (
    ABSENT,
    PLAN_ROOTS,
    PROJECTS_DIRNAME,
    ProjectPlan,
    arc_par_item,
    scan_plans,
    top_name,
)
from .arsenal_run import confusion_de_chemin

_REPO_ROOT = Path(__file__).resolve().parents[4]


def _cause_et_geste(dossier_plan: Path, projet: ProjectPlan | None) -> tuple[str, str]:
    """The precise cause why `dossier_plan` was not read, and the gesture that closes it.

    Three genuinely different failures used to produce the same wording: a path outside the
    perimeter `scan_plans` covers (neither a declared root, nor `projects/<bubble>/<project>`), a
    folder that simply does not exist, and a plan whose `PLAN.md` exists but is refused by the
    reader (the ABSENT/UNREADABLE vocabulary + its named reason, already carried by `ProjectPlan`).
    Receives `projet` already computed by the caller -- a second `scan_plans` would be the third
    enumeration this repo refuses elsewhere (see `.githooks/pre-commit`, `judge()`)."""
    if not dossier_plan.is_relative_to(_REPO_ROOT):
        return (
            "the path is outside the repo's root",
            "give a path UNDER the repo's root -- nothing outside it is judged by the barrier "
            "nor read by this command",
        )
    rel = dossier_plan.relative_to(_REPO_ROOT)
    a_la_bonne_profondeur = str(rel) in PLAN_ROOTS or (
        len(rel.parts) == 3 and rel.parts[0] == PROJECTS_DIRNAME
    )
    if not a_la_bonne_profondeur:
        return (
            "the path is neither a declared plan root nor at a project's depth "
            f"(`{PROJECTS_DIRNAME}/<bubble>/<project>`) -- `scan_plans` never sees it",
            f"target `{PROJECTS_DIRNAME}/<bubble>/<project>` (two levels), or a declared root "
            f"({', '.join(PLAN_ROOTS)})",
        )
    if projet is None:
        return (
            "the path does not exist on disk",
            "create the folder and its PLAN.md, or fix the path",
        )
    if projet.state == ABSENT:
        return (
            "the folder exists but carries no PLAN.md / PLAN_COURANT.md",
            "create the plan's door at this location",
        )
    return (
        f"the plan exists but is unreadable: {projet.why}",
        "fix the reason named above, then re-run",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Emits the mandate for one arc's chat.")
    parser.add_argument(
        "ARC",
        help="The arc identifier -- a letter (e.g. B) on a flat plan, the sub-plan's PATH "
        "(e.g. bubble/project/plan/01-first) on a plan with folder-sub-plans (D166 clause 3, C9)",
    )
    parser.add_argument(
        "--plan", default=None, help="The plan's folder (default: docs)"
    )
    parser.add_argument(
        "--emettre-lots",
        type=int,
        metavar="TAILLE",
        default=None,
        help="Splits the mandate into dispatchable lots of TAILLE items (C5) instead of printing "
        "the full mandate -- writes lot_N_IN.md per lot into --dossier.",
    )
    parser.add_argument(
        "--assembler-lots",
        type=int,
        metavar="TAILLE",
        default=None,
        help="Reads lot_N_OUT.md back from --dossier for the SAME split (same TAILLE, same arc) "
        "and REFUSES (code 2) if a lot is missing.",
    )
    parser.add_argument(
        "--dossier", type=Path, default=None, help="Folder for the lot files (C5)."
    )
    args = parser.parse_args(argv)

    # C9: `--plan` comes from a Makefile interpolation ($(if $(PLAN),--plan "$(PLAN)",)), not a
    # direct environment read -- but `make` still exports every command-line variable to this
    # process, read or not. `make POUR="..." lot-emit` (the wrong name) therefore NEVER passes
    # `--plan`, and used to fall through silently to `docs` -- a COMPLETE, plausible MANDATE, for
    # the wrong project (worse than C8: not a figure, a document an agent would act on).
    voisins = confusion_de_chemin("PLAN")
    if args.plan is None and voisins:
        print(
            f"REFUSED: {', '.join(f'{nom}=' for nom in voisins)} defined, but this target only "
            "reads --plan=/PLAN= -- make silently ignores an unknown variable, and the mandate "
            "would have been emitted for Mnémosyne's own plan without a word. Re-run with PLAN= "
            "instead.",
            file=sys.stderr,
        )
        return 2
    plan_arg = args.plan if args.plan is not None else "docs"

    dossier_plan = _REPO_ROOT / plan_arg
    registre = scan_plans(_REPO_ROOT).projects
    projet = next((p for p in registre if p.plan_path.parent == dossier_plan), None)
    if projet is None or projet.reading is None:
        cause, geste = _cause_et_geste(dossier_plan, projet)
        print(
            f"REFUSED: `{dossier_plan}` is not a plan readable from {_REPO_ROOT} -- {cause}.\n"
            f"  The gesture: {geste}.",
            file=sys.stderr,
        )
        return 2

    # C9: `scan_plans` returns each D166-clause-3 sub-plan (a NUMBERED folder carrying its OWN
    # door) as a separate SIBLING `ProjectPlan`, never folded into `projet.reading` -- the same
    # fair, documented choice `read_plan_tree` makes so a broken sub-plan stays nameable (see
    # `plan_registry.py`). The unintended consequence: a reader that takes only `projet.reading`
    # alone sees ONLY the root door's items, never the sub-plans -- which just blocked a real
    # project orchestrator (`carte` saw 14, `lot-emit` saw 2). `make carte`/`make
    # orchestration-borne` already close this gap by folding the WHOLE tree with `carte.replier`
    # (same single source, never a second implementation) -- `lot-emit` adopts it here.
    membres = [
        p for p in registre if top_name(p.name) == projet.name and p.reading is not None and p.reading.items
    ]
    lecture, collisions = replier([m.reading for m in membres])
    if collisions:
        print(
            f"WARNING: {len(collisions)} identifier(s) carried by MULTIPLE plans: "
            f"{', '.join(collisions[:5])}{' …' if len(collisions) > 5 else ''} -- counted once "
            "each.",
            file=sys.stderr,
        )

    # C9 (reopened): on a plan with D166-clause-3 sub-plans, an arc's REAL identity is the
    # sub-plan that carries it, never the ident's letter prefix (measured on a real multi-sub-plan
    # project: 14 actual arcs against 3 by prefix -- see `plan_registry.arc_par_item`). `membres`
    # already carries this mapping; `None` on a flat plan falls `lot_emit` back to
    # `lettre_d_arc`, unchanged.
    arc_map = arc_par_item(membres)

    arcs = lot_emit.arcs_du_plan(lecture, arcs=arc_map)
    if args.ARC not in arcs:
        print(
            f"REFUSED: arc `{args.ARC}` does not exist in this plan. Real arcs: "
            f"{', '.join(sorted(arcs))}.",
            file=sys.stderr,
        )
        return 2

    mandat = lot_emit.mandat_pour_arc(
        lecture,
        porte=str(projet.plan_path.relative_to(_REPO_ROOT)),
        arc=args.ARC,
        arcs=arc_map,
    )

    if args.emettre_lots is not None:
        if args.dossier is None:
            print("REFUSED: --emettre-lots requires --dossier.", file=sys.stderr)
            return 2
        lots = lot_emit.decouper_mandat(mandat, taille=args.emettre_lots)
        args.dossier.mkdir(parents=True, exist_ok=True)
        for lot in lots:
            (args.dossier / f"lot_{lot.indice}_IN.md").write_text(lot_emit.rendre_lot(lot))
        print(f"{len(lots)} lot(s) emitted into {args.dossier}")
        return 0

    if args.assembler_lots is not None:
        if args.dossier is None:
            print("REFUSED: --assembler-lots requires --dossier.", file=sys.stderr)
            return 2
        lots = lot_emit.decouper_mandat(mandat, taille=args.assembler_lots)

        def lire_sortie(lot: Lot[PlanItem]) -> str | None:
            fichier = args.dossier / f"lot_{lot.indice}_OUT.md"
            return fichier.read_text() if fichier.exists() else None

        assemblage = lot_emit.assembler_mandat(lots, lire_sortie)
        if not assemblage.complet:
            print(
                f"REFUSED: {len(assemblage.manquants)} lot(s) missing: {assemblage.manquants}.",
                file=sys.stderr,
            )
            return 2
        print(f"{len(assemblage.rendus)} lot(s) assembled, complete.")
        return 0

    # THE PROJECT'S ROOT, PASSED EXPLICITLY (2026-08-18) — the defect the SECOND adopter paid
    # for. `a_lire` already knew how to resolve a project's paths relative to ITS OWN root, but the
    # only one it knew was hard-coded to the FIRST adopter's project, written in when that was the
    # only one. The second adopter got back "9 unresolved references, total payload 0 bytes" and
    # had to prefix every one of its citations with its own project folder -- its own files,
    # addressed relative to Mnémosyne, so broken the day its repo is cloned on its own.
    # Here, the caller KNOWS which plan it is reading: it passes THIS project's root, never a
    # list.
    # For Mnémosyne's own plan, that is worth `docs` -- one MORE base, never one less: everything
    # that used to resolve still resolves, this argument can only ADD.
    # FIXED ON 2026-08-18, FOUND BY AN ISOLATED AUDITOR A FEW MINUTES AFTER THE FIRST DRAFT: this
    # computation returned the PLAN's folder, not the PROJECT's root. The auditor's measurement on
    # the real registry: 13 of 26 plans -- every SUB-PLAN of the first adopter's project -- received
    # `…/<first project>/plan/01-production-base` instead of `…/<first project>`.
    # A third adopter organised into sub-plans would have fallen into EXACTLY the second
    # adopter's defect; the first adopter escaped it only through the HARD-CODED `_RACINES` entry
    # my own comment declared "now redundant". *The general fix was not general yet.*
    # `None` for Mnémosyne's own plan: its root IS the repo's own root, already covered by `""`
    # in `_RACINES` -- passing it `docs` would add a base nothing justifies.
    _rel = projet.plan_path.parent.relative_to(_REPO_ROOT)
    base_projet = (
        "/".join(_rel.parts[:3])
        if len(_rel.parts) >= 3 and _rel.parts[0] == PROJECTS_DIRNAME
        else None
    )
    # The ceiling travels WITH the mandate: it is the only text the chat being born is certain
    # to read. `lecture` is the SAME folded reading that produced its items, so the bound cannot
    # diverge from what `make orchestration-borne` returns on this plan.
    print(
        lot_emit.rendre(mandat, _REPO_ROOT, base_projet, borne=borne_chats(lecture)),
        end="",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
