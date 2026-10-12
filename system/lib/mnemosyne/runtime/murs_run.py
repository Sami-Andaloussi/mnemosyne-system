"""``make murs`` (D159) — every wall the Guard has raised, made visible.

    make murs

Reads the wall log (:class:`~mnemosyne.guard.walls.WallLedger`) and renders what got refused,
grouped by effect — the read side of "hitting a wall stops being silent". This is where an
agent looks BEFORE filing a ``make policy-demander`` request: a wall here is exactly the signal
that a legitimate need may exist.

Brick-free and read-only; it does not itself decide whether a wall was legitimate — that is the
demander/examiner/approuver pipeline's job (:mod:`~mnemosyne.runtime.policy_run`). Code English
(D117); the report is English throughout this public mirror -- except the empty-ledger sentence
below, which `tests/platform/test_walls.py` matches on literally (``"Aucun refus"``): a producer
and its assertion move in the same gesture or neither moves, and that test is out of scope here.
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter

from ..guard.walls import WallLedger


def render_walls(entries: tuple[dict[str, str], ...], *, limit: int = 10) -> str:
    if not entries:
        return "# Mnemosyne \u00b7 murs\n\nAucun refus enregistre. Rien n'a encore bute.\n"
    by_effect: Counter[str] = Counter(e.get("effect", "?") for e in entries)
    lines = [
        "# Mnemosyne \u00b7 murs",
        "",
        f"{len(entries)} refusal(s) recorded, by effect:",
    ]
    for effect, count in by_effect.most_common():
        lines.append(f"  {effect}: {count}")
    lines.append("")
    lines.append(f"The {min(limit, len(entries))} most recent:")
    for entry in entries[-limit:][::-1]:
        lines.append(
            f"  [{entry.get('at', '?')}] {entry.get('effect', '?')} "
            f"({entry.get('decision', '?')}) — {entry.get('reason', '')}"
        )
    lines.append("")
    lines.append("A legitimate wall? `make policy-demander` to file a request (D159).")
    return "\n".join(lines).rstrip() + "\n"


def main(
    argv: list[str] | None = None,
) -> int:  # pragma: no cover - [OPERATOR] surface (reads the ledger)
    parser = argparse.ArgumentParser(
        prog="make murs",
        description="Show every refusal the Guard has raised since the beginning (D159).",
    )
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    print(render_walls(WallLedger().read_all(), limit=args.limit))
    return 0


if __name__ == "__main__":  # pragma: no cover - [OPERATOR] surface
    raise SystemExit(main())
