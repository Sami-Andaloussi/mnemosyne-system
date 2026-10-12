"""`make gel-inscrire` — register an adopting door in the freeze, by a GESTURE rather than by hand.

**THE DEFECT THIS MODULE CLOSES, AND IT WAS PAID FOR BY THE SECOND ADOPTER (2026-08-18).**
`make plans` has published the adoption gap since 2026-08-17: a door that declares a format without
being in :data:`~mnemosyne.production.derives.PORTES_QUI_DECLARENT` **is held by nothing**. The
message named the gesture — *"as long as no gesture registers it"* — but that gesture was **editing
a tuple by hand in a production module**, hence: a Mnemosyne session, an editor, and a human who does
not mistype a comma. **A manual step per adopting project.**

**The second sibling project lived it**: it read *"this adoption is held by NOTHING"* and rightly answered,
*"from a project session, I report, I do not fix."* It was right — and that is exactly the symptom
of a gesture living on the wrong side of the boundary.

**WHAT THIS COMPOSES WITH `J4`**: `make -C ~/mnemosyne gel-inscrire …` (or `mnemo gel-inscrire`)
works **from a project folder**. The gesture stays a git-tracked change in the Mnemosyne repo —
judged by pre-commit, never a bypass — but it stops requiring opening an editor on code.

**WHAT THIS MODULE DOES NOT DO, AND THAT IS DELIBERATE**: it auto-discovers NOTHING. Populating
the freeze from disk would make it inert — *"a door that was never adopted and a door that just LOST
its adoption render exactly the same empty state,"* the exact defect this freeze exists to close and
which had already been remanufactured once, one layer up. **A door is registered because someone
asks for it, never because a scan saw it.**

Decisions: D163 (the address, never the copy) · D176 (project engineering is OFFERED) · D161 (a
write that is never re-read afterward is an intention, not an application). Dry by default,
`APPLY=1` writes.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Final

from ..production import derives
from ..production.plan_format import read_plan

_REPO_ROOT: Final = Path(__file__).resolve().parents[4]
_SOURCE_DU_GEL: Final = _REPO_ROOT / "system" / "lib" / "mnemosyne" / "production" / "derives.py"


def _declaration_reelle(porte_abs: Path) -> str:
    """What the door ACTUALLY declares on disk — read by the production accessor, never by a
    `grep`: it is the same reader that will later decide whether the declaration has disappeared,
    and a freeze set by a reader other than its own judge proves nothing."""
    return read_plan(porte_abs.read_text(encoding="utf-8")).format_declare


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="gel-inscrire",
        description="Register a door that DECLARES a format in the freeze (D176).",
    )
    parser.add_argument(
        "porte",
        help="path to the door (`PLAN.md`), relative to the root of the Mnemosyne repo "
        "(e.g. projects/<bubble>/<project>/PLAN.md)",
    )
    parser.add_argument("--apply", action="store_true", help="actually write (otherwise: dry run)")
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    brut = args.porte.strip()
    # `lstrip("./")` REMOVED ANY LEADING `.` OR `/`, NOT A PREFIX: `.claude/x.md`
    # became `claude/x.md`, a SILENT corruption of a legitimate path (found by an
    # isolated auditor, 2026-08-18). `removeprefix` removes the exact prefix, and nothing else.
    while brut.startswith("./"):
        brut = brut.removeprefix("./")
    porte_abs = (_REPO_ROOT / brut).resolve()

    # THE CONTAINMENT, REOPENED BY ME IN A NEW MODULE AND FOUND BY AN ISOLATED AUDITOR
    # (2026-08-18). This is EXACTLY the class an earlier audit had already closed in
    # `a_lire._resoudre` (`is_relative_to(racine_resolue)`): a `..` in the MIDDLE of the path
    # (`projects/../../../../../private/tmp/…/PLAN.md`) leaves the repo without ever starting
    # with `..`. Measured before the fix: this path passed the DRY step and announced it would be
    # registered. And the refusal "declares no format" is NOT a containment: it refuses
    # `/etc/hosts` only because it has no `**Format**`, never because it is outside.
    # *An out-of-repo entry in the freeze would be a ghost `make plans` could never judge: green
    # as long as the file exists on THIS machine, red on every other clone.*
    if not porte_abs.is_relative_to(_REPO_ROOT):
        print(
            f"REFUSED: `{args.porte}` is outside the repo root ({_REPO_ROOT}).\n"
            "  The freeze can only hold doors TRACKED BY GIT here: an out-of-repo entry\n"
            "  would be green on this machine and unfindable everywhere else.",
            file=sys.stderr,
        )
        return 2

    # The RECANONICALIZED path (recomputed from the resolved absolute) is the one that enters
    # the freeze: `projects/./x/../x/PLAN.md` and `projects/x/PLAN.md` name the same file and must
    # give the SAME entry, or two registrations of the same project would coexist.
    porte = porte_abs.relative_to(_REPO_ROOT).as_posix()

    if not porte_abs.is_file():
        print(
            f"REFUSED: `{porte}` does not exist under {_REPO_ROOT}.\n"
            "  Give the door's path RELATIVE to the root of the Mnemosyne repo.",
            file=sys.stderr,
        )
        return 2

    # MEASURE BEFORE WRITING: the freeze certifies "this door DECLARED". Registering it without
    # having read the declaration would manufacture the very attestation it is meant to make
    # falsifiable.
    declare = _declaration_reelle(porte_abs)
    if not declare.strip():
        print(
            f"REFUSED: `{porte}` declares no format.\n"
            "  The freeze certifies that a door DECLARED; registering it without a declaration\n"
            "  would make its own refusal false the day it bites.\n"
            '  The missing gesture belongs to the PROJECT: post `> **Format** : <fields>` under Cap.',
            file=sys.stderr,
        )
        return 2

    source = _SOURCE_DU_GEL.read_text(encoding="utf-8")
    try:
        nouveau = derives.inscrire_porte(source, porte)
    except derives.GelError as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 2

    if not args.apply:
        print(
            f"DRY RUN — `{porte}` declares `{declare}` and would be registered in the freeze.\n"
            f"  Re-run with APPLY=1 to write to {_SOURCE_DU_GEL.relative_to(_REPO_ROOT)}."
        )
        return 0

    _SOURCE_DU_GEL.write_text(nouveau, encoding="utf-8")
    # D161: we RE-READ from disk, never trust the text we just produced. A `write_text` that
    # succeeds and a file that carries the line are two different facts.
    relu = _SOURCE_DU_GEL.read_text(encoding="utf-8")
    if f'    "{porte}",\n' not in relu:
        print(
            "FAILED: the file was written but does not carry the expected line after re-reading.",
            file=sys.stderr,
        )
        return 2

    print(
        f"Registered: `{porte}` (declares `{declare}`).\n"
        "  Next: `make plans VERIFIER=1` must now REFUSE if this door loses its\n"
        "  declaration — that is exactly what the freeze buys.\n"
        "  Then commit `system/lib/mnemosyne/production/derives.py`: the freeze is a truth\n"
        "  tracked by git, it is worth nothing until it is committed."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
