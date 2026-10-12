"""G9 — the EDGE of precedence. It verifies that a mandate CARRIES the clause, and that its addresses are ALIVE.

```
python -m mnemosyne.runtime.precedence_run --mandat path/to/mandate.md
python -m mnemosyne.runtime.precedence_run           # judges the mandate that `rendre()` produces HERE
```

## Return codes

```
0  the mandate carries the clause, and all five addresses exist
1  REFUSED: clause absent, an address not cited, or an address DEAD on disk
2  NOT MEASURED: the designated mandate file is unreadable
```

**WHAT THIS EDGE ACTUALLY HOLDS.** It reads **no session prompt** — a mandate lives in
the harness, not in the repo, and pretending to judge it would be lying about scope. It judges the
**text this repo EMITS** (`lot_emit.rendre`): it is the only mandate Mnemosyne manufactures, so
the only one whose content it can guarantee. A mandate hand-written in a chat window
escapes this gate entirely, and that is already why the project's own orchestration doctrine engraves
*"THE MANDATE IS EMITTED, IT IS NEVER HAND-WRITTEN."*

**WIRING STATE AS OF 2026-09-08, MEASURED**: `make precedence` exists **and lives inside
`make portes`, hence inside `make check`** — the only gate in lot 2 that is both green and wired
onto the local gate. It bites: removing an address from the freeze, or its file from disk, turns it red.
The underlying admission still stands: it verifies that the mandate **CARRIES** the clause and that its
addresses **EXIST**; it detects **no contradiction whatsoever** (a matter of meaning, not of form).
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Final

from ..production.lot_emit import Mandat, rendre
from ..production.precedence import ADRESSES_QUI_PRIMENT, resume, verdicts

#: ``parents[4]`` — the repo root. ``parents[3]`` (``system/``) would carry NONE of the
#: five addresses: all five would be declared DEAD, which is a false RED. A separate test
#: judges THIS value specifically — and it checks the meaning of the false result, not merely that one exists.
RACINE: Final = Path(__file__).resolve().parents[4]


def adresses_vivantes(racine: Path) -> frozenset[str]:
    """Those of :data:`ADRESSES_QUI_PRIMENT` that actually exist under ``racine``."""
    return frozenset(a for a in ADRESSES_QUI_PRIMENT if (racine / a).is_file())


def mandat_emis_ici(racine: Path) -> str:
    """The text this repo actually emits for an empty mandate — the PRODUCTION VALUE.

    A mandate **with no item at all** is deliberate: the precedence clause depends on no item,
    so judging it on an empty mandate proves it travels ALWAYS, and not only when the
    plan has the right shape. *A guarantee that depends on its content is not a guarantee.*"""
    return rendre(Mandat(arc="", porte="", items=()), racine)


def main(argv: list[str] | None = None, *, racine: Path | None = None) -> int:
    """``racine`` is injectable FOR TESTS, never for production."""
    args = list(sys.argv[1:] if argv is None else argv)
    chemin: Path | None = None
    while args:
        jeton = args.pop(0)
        if jeton == "--mandat" and args:
            chemin = Path(args.pop(0))
    r = RACINE if racine is None else racine

    if chemin is not None:
        try:
            texte = chemin.read_text(encoding="utf-8", errors="replace")
        except OSError:
            print(
                f"\U000026A0\U0000FE0F precedence: NOT MEASURED — {chemin} unreadable. Zero mandate read is not a "
                "conforming mandate: it is an instrument failure.",
                file=sys.stderr,
            )
            return 2
    else:
        texte = mandat_emis_ici(r)

    trouves = verdicts(texte, adresses_vivantes=adresses_vivantes(r))
    print(resume(trouves, adresses=len(ADRESSES_QUI_PRIMENT)), end="")
    return 1 if trouves else 0


if __name__ == "__main__":  # pragma: no cover - [OPERATOR] surface
    raise SystemExit(main())
