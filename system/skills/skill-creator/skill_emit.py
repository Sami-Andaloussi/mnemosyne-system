#!/usr/bin/env python3
"""Seam `skill-emit` - EMITS the skill-creator's anatomy contract from the ONE source of
truth: the code (`SKILL_ANATOMY_TEMPLATE`, `mnemosyne.production.skills`).

Same anti-drift lesson as the distiller and the finisher (contract-single-source-emit, commit
241e525): an agent building a NEW skill must receive the 5-layer anatomy and the arc's 6
lessons EXACTLY as the code defines them, never a hand-copied prose in this skill-creator's own
SKILL.md (a copy drifts and lies - precisely the lesson this skill exists to engrave). Unlike
`distill-emit` / `finish-emit`, this contract is NOT specific to a file: there is nothing to
split by book/fiche, so no argument.

Print-only, no model/brick required (like the other `-emit` seams).

Usage: make skill-emit
"""

from __future__ import annotations

import sys

_RULE = "=" * 88


def build_emission() -> str:
    """Assemble the emission from the ONE code home - returned as text; ``main`` prints it.

    Pure and offline: ``SKILL_ANATOMY_TEMPLATE`` is a plain string constant, so this cannot drift
    from what ``mnemosyne.production.skills`` actually defines - the whole point (anti-drift,
    lesson 1, applied reflexively to the skill that teaches it)."""
    from mnemosyne.production import SKILL_ANATOMY_TEMPLATE

    lines = [
        "CONTRACT skill-creator (EMITTED from the code, mnemosyne.production.skills - never copied):",
        _RULE,
        "",
        SKILL_ANATOMY_TEMPLATE.rstrip("\n"),
        "",
        _RULE,
        'Build from THIS text (make skill-new NEED="..."), describe it in YOUR OWN',
        "WORDS in the SKILL.md of the skill you are building (never a long excerpt pasted verbatim -",
        'make skill-audit DIR=... would catch it), then check: make skill-audit DIR="system/skills/<name>".',
    ]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    _ = sys.argv[1:] if argv is None else argv  # no arguments used - the contract is not per-file
    print(build_emission(), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
