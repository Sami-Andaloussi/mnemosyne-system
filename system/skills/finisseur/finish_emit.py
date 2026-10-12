#!/usr/bin/env python3
"""The `finish-emit` seam - EMITS the finisseur's polish contract from the ONE source of truth: the code.

Same anti-drift lesson as the distillateur (contract-single-source-emit, commit 241e525): a FRONTIER agent
(Codex) that polishes a record IS the model; it needs the SAME contract as the code, not prose hand-copied
into SKILL.md (a copy drifts and lies). This seam prints, everything DERIVED from the code:
  1. the record's path (rewrite IN PLACE);
  2. a fail-closed safety LOCK: if `chapter_numbers_ok` is false (a `## N.` probably lives INSIDE a
     verbatim passage -> splitting would truncate the P3) or if the record is a source-unusable flag, it
     says DO NOT TOUCH, STOP (exactly what the deterministic pass SKIPS and the judge FLAGS);
  3. the exact polish contract (`FINISH_PROMPT`);
  4. the state of each chapter (current title, [TITLE TO REDO] if bad, concepts) to help retitle it.

The agent applies the contract, COPIES the P3 verbatim byte-for-byte, rewrites the record at the same
path; then `make judge` checks that the P3 has not moved. NO model / NO brick required here.

Code & docstrings are English (D117); in the original system user-facing labels are shown to the user in
French (D33) - translated to English here for this public mirror, emitted markers included. Those markers
are asserted on, character for character, by tests/distillation/test_finish_emit.py: change one here and
you change it there in the same gesture, or the pairing breaks in silence.

Usage: make finish-emit FICHE="knowledge/distilled/<domain>/<book>.md"
"""

from __future__ import annotations

import sys
from pathlib import Path

_RULE = "=" * 88
_THIN = "-" * 88


def build_emission(text: str, out: Path) -> str:
    """Assemble the finisseur polish contract from the ONE code home - returned as text; ``main`` prints it.

    Pure and offline (no model, no brick): the fail-closed safety verdict (``chapter_numbers_ok``), the parse
    and the contract template all come from the code, so a frontier host applies EXACTLY the code's polish
    contract - never a hand-copy that could drift."""
    from mnemosyne.production import FINISH_PROMPT, chapter_numbers_ok, is_bad_title, parse_fiche

    lines = [f"OUT (record to rewrite IN PLACE): {out}", _RULE, ""]

    if "status: source-unusable" in text:
        lines += [
            "This record is a source-unusable FLAG (not a record to polish) -> DO NOT TOUCH, STOP.",
            _RULE,
        ]
        return "\n".join(lines) + "\n"
    if not chapter_numbers_ok(text):
        lines += [
            "FAIL-CLOSED LOCK (D143): AMBIGUOUS chapter split - a `## N.` probably lives INSIDE a",
            "verbatim passage (the finisseur SKIPS it, the judge FLAGS it). -> DO NOT TOUCH THIS RECORD, STOP.",
            "(better an unfinished record than a truncated verbatim.)",
            _RULE,
        ]
        return "\n".join(lines) + "\n"

    _header, chapters = parse_fiche(text)
    lines += [
        "POLISH CONTRACT (the real one, EMITTED from the code - apply it, do not copy it):",
        _THIN,
        FINISH_PROMPT.rstrip("\n"),
        _THIN,
        "",
        f"{len(chapters)} CHAPTER(S) - for each: a good DESCRIPTIVE title + clear P2, verbatim UNCHANGED:",
        "",
    ]
    for i, ch in enumerate(chapters, 1):
        flag = "   [TITLE TO REDO]" if is_bad_title(ch.title) else ""
        gloss = ", ".join(ch.concepts[:5]) or "(none)"
        lines += [f"  {i}. current title: {ch.title!r}{flag}", f"     concepts: {gloss}"]
    lines += [
        "",
        "Read the record at OUT, rewrite it polished at the SAME path (verbatim byte-for-byte, SAME number",
        "of chapters). Then `make judge` MUST stay green (P3 unchanged) - if you touched the verbatim that is a FAIL.",
    ]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if not args:
        print('Usage: make finish-emit FICHE="knowledge/distilled/<domain>/<book>.md"')
        return 1
    path = Path(args[0])
    text = path.read_text(encoding="utf-8", errors="replace")
    print(build_emission(text, path), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
