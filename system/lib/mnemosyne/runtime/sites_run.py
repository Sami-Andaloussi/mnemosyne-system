"""``make sites-de-sortie`` — the EDGE of the egress-sites freeze (harvest candidate G1).

**TWO LEVELS, AND THAT IS THE PATTERN OF `make memoire`.** Run by hand or from a script, this
command **REFUSES** (`rc=1`) when the freeze no longer holds: there, it is a gate. Published by
`tick`, it NAMES without refusing anything — and *a check that prints is not a gate* — so its `rc`
is discarded there. Written here so no one reads the publication as a guarantee.

**IT DOES NOT STAY SILENT WHEN IT COULD NOT MEASURE**: a census that finds zero sites is an
instrument failure (the path is wrong, the tree is empty), never a pass — *two absences of
measurement compare equal*, and that is how a detector dies without turning red.

**WHAT THIS MODULE COVERS, AND WHAT IT DOES NOT.** It scans `system/lib` — exactly the zone
`CLAUDE.md` already says *"No backdoor inside `system/lib/mnemosyne/`"* about. It **VERIFIES that
promise**; it does not close the "outside" that the same sentence declares open (project engine,
personal script). v1 claimed the opposite in bold in three documents; that was false, and an
isolated audit caught it. *A scope does not grow wider just because it is described badly.*

**THE TWO LEVELS ARE NOT DISTINGUISHED BY THE `rc` UNDER `make`**: measured — a recipe that
returns `rc=1` and one that returns `rc=2` both make `make` exit with **2**. The refusal /
non-measurement distinction therefore lives in the published TEXT (`resume`), and that is what
must be read.
"""

from __future__ import annotations

import sys
from collections.abc import Collection
from pathlib import Path

from ..production.sites_de_sortie import SITES_GELES, recenser, resume, verdict

#: parents[4], and the cost was PAID TWICE: `parents[3]` names `system/`, so `recenser` found
#: NO files at all. The `compares == 0` guard bit on the first try — then an isolated audit showed
#: that **nothing recorded that bite**: putting `parents[3]` back left the 19 tests green.
#: `test_sites_run.py` now holds it. *A gate proven to bite BY HAND can be reintroduced without
#: turning red.*
RACINE = Path(__file__).resolve().parents[4]


def main(
    argv: list[str] | None = None,
    *,
    racine: Path | None = None,
    geles: Collection[str] | None = None,
) -> int:
    """`racine` and `geles` are injectable FOR TESTS, never for production.

    Their `None` default — rather than `RACINE` / `SITES_GELES` as the default value — is
    deliberate: a default value evaluated at import time freezes and stops following the module.
    Above all, *testing a gate by injecting its population does not test the production
    population*: `test_la_RACINE_de_production_designe_le_DEPOT` judges that separately.
    """
    r = RACINE if racine is None else racine
    g = SITES_GELES if geles is None else geles
    v = verdict(recenser(r / "system" / "lib"), g)
    print(resume(v))
    if v.compares == 0:
        return 2  # not measured: distinct from a refusal, and distinct from a pass
    return 0 if v.tient else 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main(sys.argv[1:]))
