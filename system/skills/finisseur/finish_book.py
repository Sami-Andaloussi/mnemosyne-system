#!/usr/bin/env python3
"""Body of the `finisseur` skill: polishes the readability of distilled/ records WITHOUT touching P3 (D143).

DETERMINISTIC pass (no model): for each record that has CLEARLY bad chapter titles (a "(section)"
placeholder, OCR gibberish) OR a noisy concept list (`formula-not-decoded`, stray punctuation,
duplicates - see `curate_concepts`), rebuilds the titles from the chapter's (curated) concepts, cleans
the concepts, and rebuilds the table of contents; the P3 verbatim is copied through as-is (guaranteed
by `finish_fiche`: the Content block is never re-rendered). source-unusable flags are left untouched.
Atomic write. The REAL model-based polishing (titles + P2 prose) is the frontier path (see SKILL.md).
Always re-validate afterwards with `make judge` (P3 must stay intact - no finisher is trusted blindly
either).

Usage: make finish   (or: PYTHONPATH=system/lib uv run python system/skills/finisseur/finish_book.py)
"""

from __future__ import annotations

import os
from pathlib import Path

_DISTILLED = Path("knowledge/distilled")


def main() -> int:
    from mnemosyne.production import (
        chapter_numbers_ok,
        curate_concepts,
        finish_fiche,
        is_bad_title,
        parse_fiche,
    )

    n_fiches = 0
    n_titles = 0
    n_concept_lists = 0
    n_skip = 0
    for path in sorted(_DISTILLED.rglob("*.md")):
        text = path.read_text(encoding="utf-8", errors="replace")
        if "status: source-unusable" in text:  # a flag is not a record to polish
            continue
        if not chapter_numbers_ok(
            text
        ):  # fail-closed (D143): a non-sequential "## N." -> we do NOT touch it
            n_skip += 1
            print(
                f"  [SKIP ambiguous] {path.relative_to(_DISTILLED)} - a '## N.' inside a passage? (the judge will flag it)",
                flush=True,
            )
            continue
        _header, chapters = parse_fiche(text)
        bad = sum(1 for ch in chapters if is_bad_title(ch.title))
        noisy = sum(1 for ch in chapters if curate_concepts(list(ch.concepts)) != list(ch.concepts))
        if bad == 0 and noisy == 0:  # already readable AND already clean -> no point reformatting
            continue
        finished = finish_fiche(text)  # deterministic; P3 copied through as-is
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(finished, encoding="utf-8")
        os.replace(tmp, path)  # atomic swap
        n_fiches += 1
        n_titles += bad
        n_concept_lists += noisy
        print(
            f"  {path.relative_to(_DISTILLED)} - {bad} title(s) rebuilt, "
            f"{noisy} concept list(s) cleaned",
            flush=True,
        )

    print(
        f"\nFINISSEUR (deterministic pass): {n_fiches} record(s) touched, {n_titles} title(s) "
        f"rebuilt, {n_concept_lists} concept list(s) cleaned, {n_skip} skip(s) (ambiguous, untouched).",
        flush=True,
    )
    print(
        "Re-validate P3 with `make judge`. Fine polishing (P2 prose) is the frontier path (SKILL.md).",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
