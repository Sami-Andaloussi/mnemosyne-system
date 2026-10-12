#!/usr/bin/env python3
"""The `veille` seam (make veille) -- EMITS the exact veille contract from the SINGLE source of
truth: the code (`veille.py`, the sibling module).

Same anti-drift lesson as `distill-emit` / `finish-emit` (contract-single-source-emit): the rich
extraction work (reading a distilled fiche and pulling principles / skills / hypotheses out of it)
is a FRONTIER agent's act (the cohabitation's master, see ARCHITECTURE.md) -- this file calls NO
model, NO brick; it PRINTS the contract that `veille.py` assembles, byte for byte, for the agent to
apply. Nothing is hand-copied anywhere.

What it prints is ENTIRELY derived from the code: the WORKLIST (the unsurveyed fiches, capped to
BATCH via the `system/state/veille_ledger.jsonl` ledger), the JSON SCHEMA for each finding, and the
output instructions (where to write each inert draft, how to mark a fiche as surveyed). NO model /
NO brick required here.

Code & docstrings are English (D117); user-facing labels are normally kept in the operator's own
language internally (D33) -- this mirror's emitted contract has been translated to English to match.

Usage: make veille [BATCH=N]
"""

from __future__ import annotations

import sys
from pathlib import Path

# Import the sibling module `veille`: REUSE its real code (schema, worklist, contract) instead of
# recopying a line -- recopying is exactly the drift this file exists to kill. The body of `veille`
# has no side effects beyond the (lazy) import of `mnemosyne.production.veille_ledger`, itself
# pure/brick-free, so it is safe to load.
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))
import veille  # noqa: E402

#: Repo root from this file (`system/skills/veilleur/emit_veille.py` -> parents[3] = repo root).
_DISTILLED_ROOT = Path(__file__).resolve().parents[3] / "knowledge" / "distilled"


def main(argv: list[str] | None = None) -> int:  # pragma: no cover - CLI over the reference corpus
    args = sys.argv[1:] if argv is None else argv
    batch = int(args[0]) if args else veille.DEFAULT_BATCH
    worklist = veille.build_worklist(_DISTILLED_ROOT, batch=batch)
    print(veille.build_contract(worklist, distilled_root=_DISTILLED_ROOT), end="")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
