#!/usr/bin/env python3
"""Body of the `juge` skill: checks ALL of knowledge/distilled/ against knowledge/raw/.

For each .md in raw/, looks at its MIRROR fiche in distilled/: absent -> needs distilling; present ->
`judge_fiche` (verbatim floor + source gate, NO trust given to the model that produced it, Codex included).
Produces a readable summary + a machine report `system/logs/judge_report.md` listing the fiches to
re-process. Does NOT rewrite EITHER the raw OR the fiche (it observes and flags).

Usage : make judge   (or: PYTHONPATH=system/lib uv run python system/skills/juge/judge_library.py)
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

_RAW = Path("knowledge/raw")
_DISTILLED = Path("knowledge/distilled")
_REPORT = Path(
    "system/logs/judge_report.md"
)  # log sink, not the knowledge/ root itself
_MISSING = "missing"  # orchestrator status: raw with no mirror fiche (not yet distilled)
#: display order: good -> needs re-processing
_ORDER = [
    "ok",
    "flagged",
    _MISSING,
    "cut",
    "thin",
    "hollow",
    "paraphrased",
    "malformed",
    "raw_missing",
]
_TO_REDO = (
    "cut",  # completeness FLOOR: a citation cut off in the middle of a word
    "hollow",
    "thin",
    "paraphrased",
    "malformed",
)  # distilled but BAD/insufficient -> needs re-processing


def run_judge(
    raw_root: Path = _RAW, distilled_root: Path = _DISTILLED
) -> list[tuple[str, str, object]]:
    """(status, relative_path, verdict|None) for each .md in raw/. verdict=None if the fiche is missing."""
    from mnemosyne.ingest import taxonomy
    from mnemosyne.ingest.library import is_non_corpus
    from mnemosyne.production import judge_fiche

    rows: list[tuple[str, str, object]] = []
    for raw_path in sorted(raw_root.rglob("*.md")):
        rel = raw_path.relative_to(raw_root)
        if is_non_corpus(
            rel
        ):  # README* / _intake : housekeeping doc, not a book (same rule as discover_books)
            continue
        fiche = distilled_root / rel
        if not fiche.exists():
            # The watch (taxonomy family group "Tooling") is ALREADY a standalone synthesis, not a
            # raw source to distill: it is therefore not claimed as "missing" (it stays RAG-indexed
            # via discover_books). Any other raw with no mirror fiche is a real book to distill.
            _dom = taxonomy.domain_from_parts(rel.parts)
            _fg = taxonomy.family_group(_dom) if _dom else None
            if _fg is not None and _fg[1] == "Tooling":
                continue
            rows.append((_MISSING, str(rel), None))
            continue
        verdict = judge_fiche(
            fiche.read_text(encoding="utf-8", errors="replace"),
            raw_path.read_text(encoding="utf-8", errors="replace"),
        )
        rows.append((verdict.status, str(rel), verdict))
    return rows


def main(argv: list[str] | None = None) -> int:
    rows = run_judge()
    counts = Counter(status for status, _, _ in rows)
    total = len(rows)

    print(f"JUGE - {total} books in raw/\n", flush=True)
    for st in _ORDER:
        if counts.get(st):
            print(f"  {st:12} : {counts[st]}", flush=True)

    # P2 = axis SEPARATE from P3 fidelity: how many descriptions are a mechanical TEMPLATE (not synthesized).
    verdicts = [v for _, _, v in rows if v is not None]
    n_templ = sum(getattr(v, "n_templated", 0) for v in verdicts)
    n_desc = sum(getattr(v, "n_chapters", 0) for v in verdicts)
    fiches_templ = sum(1 for v in verdicts if getattr(v, "n_templated", 0) > 0)
    if n_templ:
        print(
            f"\n  P2 template  : {n_templ}/{n_desc} mechanical descriptions in {fiches_templ} fiche(s) "
            "(NOT synthesized - does not affect P3 fidelity, see finisher)",
            flush=True,
        )

    # P3 TRUNCATED = 3rd axis, and the only STRUCTURAL blind spot of the verbatim floor: a passage cut
    # off clean at the schema ceiling stays a LITERAL prefix of the source, so `keep_verbatim` blesses it.
    from mnemosyne.production import passage_cap

    n_cut = sum(getattr(v, "n_truncated", 0) for v in verdicts)
    fiches_cut = sum(1 for v in verdicts if getattr(v, "n_truncated", 0) > 0)
    if n_cut:
        print(
            f"\n  P3 truncated  : {n_cut} passage(s) cut short at {passage_cap()} characters in {fiches_cut} "
            "fiche(s) - the LENGTH ceiling that produced this cut was REMOVED from the schema on "
            "YYYY-MM-DD: this count is therefore ARCHAEOLOGY of the existing shelf, not a live rule. "
            "Invisible to the verbatim floor (a literal prefix stays literal), it affects "
            "NO verdict; only a re-distillation repairs it.",
            flush=True,
        )

    problems = [(st, rel, v) for st, rel, v in rows if st in _TO_REDO]
    if problems:
        print(
            f"\n{len(problems)} DISTILLED BUT BAD FICHE(S) -> need re-processing :",
            flush=True,
        )
        for st, rel, v in problems[:40]:
            print(f"  [{st}] {rel}  - {getattr(v, 'reason', '')}", flush=True)
        if len(problems) > 40:
            print(f"  ... +{len(problems) - 40} (see {_REPORT})", flush=True)

    # inverse blind spot: distilled/ fiches WITHOUT a raw mirror (orphans - e.g. a leftover test run)
    from mnemosyne.ingest.library import is_non_corpus

    raw_rels = {
        str(p.relative_to(_RAW))
        for p in _RAW.rglob("*.md")
        if not is_non_corpus(p.relative_to(_RAW))
    }
    orphans = sorted(
        str(p.relative_to(_DISTILLED))
        for p in _DISTILLED.rglob("*.md")
        if str(p.relative_to(_DISTILLED)) not in raw_rels
    )
    if orphans:
        print(f"\n{len(orphans)} ORPHAN FICHE(S) (distilled/ without a raw/ mirror) :", flush=True)
        for o in orphans[:10]:
            print(f"  {o}", flush=True)

    lines = [
        "# Judge report\n",
        f"{total} books - "
        + "  -  ".join(f"{k}={counts[k]}" for k in _ORDER if counts.get(k))
        + "\n",
        f"P2 template (not synthesized, axis separate from P3 fidelity) : {n_templ}/{n_desc} descriptions in "
        f"{fiches_templ} fiche(s).\n",
        f"P3 truncated (cut short at {passage_cap()} characters by a ceiling REMOVED on YYYY-MM-DD - "
        f"archaeology of the shelf, invisible to the verbatim floor) : {n_cut} passage(s) in {fiches_cut} fiche(s).\n",
        "Fiches to process (`ok`/`flagged` are omitted) :\n",
    ]
    for st, rel, v in rows:
        if st in ("ok", "flagged"):
            continue
        detail = getattr(v, "reason", "fiche absent - needs distilling")
        lines.append(f"- **{st}** - `{rel}` - {detail}")
    _REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nMachine report -> {_REPORT}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
