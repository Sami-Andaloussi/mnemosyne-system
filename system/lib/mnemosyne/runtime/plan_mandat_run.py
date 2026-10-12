"""``make plan-mandat`` — H6 finally CALLED: publishes the derived mandate, alongside the manual one.

This repo's ``*-emit`` pattern: resolves the root, reads the plan with the production accessor
(:func:`~mnemosyne.production.plan_registry.scan_plans`), delegates the computation to
:mod:`~mnemosyne.production.plan_mandat` (:func:`mandat_derive`, :func:`rendre_mandat`) and
writes nothing — the mandate goes out on ``stdout``, like ``lot-emit`` (E4).

**WHAT THIS MODULE DOES NOT DO, AND IT IS DELIBERATE (H6)**: it does not compare against the
manual post, it does not judge the gap, it refuses no closing. ``plan_mandat.rendre_mandat`` stays
POOR (identifier, rank, status, mechanical reason, a load COUNT) precisely so the `diff` against a
hand-written post shows, with no varnish, everything the hand adds that the machine ignores —
enriching THIS module with PROSE to make it resemble the manual one would hide exactly the gap
`H6`'s clause asks to be published; publishing plan facts already read or already proven elsewhere
(status, load) is not that (measured by two non-producers, 12:5x). Publishing is not judging (D75):
this module publishes, a third party judges.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ..production.plan_mandat import mandat_derive, rendre_mandat
from ..production.plan_registry import scan_plans

_REPO_ROOT = Path(__file__).resolve().parents[4]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Publish the derived mandate (H6), alongside the manual one."
    )
    parser.add_argument("--plan", default="docs", help="The plan's folder (default: docs)")
    parser.add_argument(
        "--n", type=int, default=5, help="Number of queue heads published (default: 5)"
    )
    args = parser.parse_args(argv)

    plan_folder = _REPO_ROOT / args.plan
    projet = next(
        (p for p in scan_plans(_REPO_ROOT).projects if p.plan_path.parent == plan_folder), None
    )
    if projet is None or projet.reading is None:
        print(
            f"REFUSED: `{plan_folder}` is not a readable plan from {_REPO_ROOT}.",
            file=sys.stderr,
        )
        return 2

    mandat = mandat_derive(projet.reading, racine=_REPO_ROOT, n=args.n)
    for ligne in rendre_mandat(mandat):
        print(ligne)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
