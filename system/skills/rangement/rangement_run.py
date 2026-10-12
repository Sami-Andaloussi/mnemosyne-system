#!/usr/bin/env python3
"""Couture `rangement` (make rangement) - RUN the deterministic quarantine pass over the real repo.

Orchestration only (the anatomy's thin adapter): it globs the repo through the code home's
:func:`~mnemosyne.production.rangement.scan`, VERIFIES the plan fail-closed
(:func:`~mnemosyne.production.rangement.no_protected_path_touched` +
:func:`~mnemosyne.production.rangement.plan_is_reversible`) BEFORE touching disk, and - only with an
explicit ``--apply`` - MOVES each clear-cruft file into a dated quarantine folder, writing a manifest so
the whole pass is reversible with a plain ``mv`` back. It re-implements none of the logic; it calls the
code home.

DRY-RUN by default (least surprise / propose-never-impose, D92): ``make rangement`` only PREVIEWS the
plan; ``make rangement APPLY=1`` performs the reversible moves. It NEVER deletes - emptying the
quarantine is user's gesture (D74). Code & docstrings English (D117).

Usage: make rangement [APPLY=1]
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

from mnemosyne.production.rangement import (
    no_protected_path_touched,
    pass_stamp,
    plan_is_reversible,
    plan_quarantine,
    scan,
)

#: Repo root from this file (`system/skills/rangement/rangement_run.py` -> parents[3] = repo root).
_ROOT = Path(__file__).resolve().parents[3]


def main(argv: list[str] | None = None) -> int:  # pragma: no cover - CLI over the real repo tree
    parser = argparse.ArgumentParser(
        prog="make rangement",
        description="Quarantine clear repo cruft (non-destructive, reversible). Dry-run unless --apply.",
    )
    parser.add_argument(
        "--apply", action="store_true", help="perform the moves (default: dry-run preview)"
    )
    parser.add_argument("--root", default=str(_ROOT), help="repo root to scan (default: this repo)")
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    root = Path(args.root).resolve()

    candidates = scan(str(root))
    stamp = pass_stamp()
    moves = plan_quarantine(candidates, stamp)

    if not candidates:
        print("[rangement] no clear cruft found - the repo is clean at the deterministic grain.")
        return 0

    # Fail-closed (verify-in-code): refuse the whole pass if the plan would touch a protected path or is
    # not losslessly reversible - trusting no producer, the plan builder included (D75 / D100).
    if not no_protected_path_touched(moves) or not plan_is_reversible(moves):
        print(
            "[rangement] REFUSED fail-closed: the plan touches a protected path or is not reversible. "
            "Nothing moved.",
            file=sys.stderr,
        )
        return 1

    print(
        f"[rangement] {len(moves)} clear-cruft file(s) {'to quarantine' if args.apply else 'WOULD move'}:"
    )
    for mv in moves:
        print(f"  [{mv.cls.value}] {mv.src}\n      -> {mv.dst}")

    if not args.apply:
        print(
            "\n[rangement] DRY-RUN - nothing moved. Re-run with APPLY=1 to perform the reversible moves."
        )
        return 0

    dest_root = root / f"knowledge/_quarantine/rangement-{stamp}"
    dest_root.mkdir(parents=True, exist_ok=True)
    applied: list[dict[str, str]] = []
    for mv in moves:
        src_abs = root / mv.src
        if (
            not src_abs.exists()
        ):  # vanished between scan and move (race) - skip, never fail the pass
            continue
        dst_abs = root / mv.dst
        dst_abs.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src_abs), str(dst_abs))
        applied.append({"from": mv.src, "to": mv.dst, "class": mv.cls.value})

    manifest = {
        "stamp": stamp,
        "moves": applied,
        "reverse_hint": "restore = move each 'to' back to its 'from' (nothing was deleted).",
    }
    (dest_root / "MANIFEST.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), "utf-8"
    )
    print(
        f"\n[rangement] moved {len(applied)} file(s) into {dest_root.relative_to(root)}/ "
        f"(reversible - see its MANIFEST.json). Nothing deleted (D74)."
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
