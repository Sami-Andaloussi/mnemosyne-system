#!/usr/bin/env python3
"""Couture `rangement-emit` (make rangement-emit) - EMIT the rangement contract for a FRONTIER host.

The skill's FRONTIER version is this contract: a PROMPT the frontier applies in the folder it has access
to, no bespoke ``.py`` (user's multi-version archetype, item 5). Same anti-drift lesson as the other
emit seams (contract-single-source-emit): it re-implements nothing and hand-copies no rule - it replays
the code home's real :func:`~mnemosyne.production.rangement.scan` +
:func:`~mnemosyne.production.rangement.build_rangement_contract` over the REAL repo tree and prints what
they assemble. No model, no brick.

Usage: make rangement-emit
"""

from __future__ import annotations

from pathlib import Path

from mnemosyne.production.rangement import build_rangement_contract, pass_stamp, scan

#: Repo root from this file (`system/skills/rangement/rangement_emit.py` -> parents[3] = repo root).
_ROOT = Path(__file__).resolve().parents[3]


def main(argv: list[str] | None = None) -> int:  # pragma: no cover - CLI over the real repo tree
    root = str(_ROOT)
    candidates = scan(root)
    print(build_rangement_contract(candidates, root, pass_stamp()), end="")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
