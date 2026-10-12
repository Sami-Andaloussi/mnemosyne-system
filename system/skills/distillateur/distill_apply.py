#!/usr/bin/env python3
"""Apply distillation results using the local verification pipeline."""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))
from distill_book import (  # noqa: E402
    HAIKU_MAX_RUN,
    HAIKU_TARGET_CHARS,
    _MAX_RUN,
    _TARGET_CHARS,
    _clean_title,
    _distilled_path_for,
    _finalize_toc,
    _frontmatter,
    _section_md,
    chunk_book,
)


def _doc_from_json(obj: dict, source_text: str, title: str, doc_id: str):  # noqa: ANN202 - DistilledDoc (lazy)
    """Build ONE section's :class:`DistilledDoc` from the agent JSON, applying the verbatim floor (D143).

    ``passages`` are re-tested against ``source_text`` by :func:`keep_verbatim`: a paraphrased / invented
    citation is DROPPED here, in code - the agent's P3 can only ever be the source's own words. tags/concepts
    are bounded like the local decoder (8 / 12), so an over-eager agent cannot bloat the fiche."""
    from mnemosyne.production import DistilledDoc, DistilledType
    from mnemosyne.production.distillation import keep_verbatim

    raw_passages = obj.get("passages", [])
    if not isinstance(
        raw_passages, list
    ):  # a STRING here would iterate CHARACTERS - every letter is a
        raw_passages = []  # substring of the source, so single letters would pass as "verbatim" (audit)
    passages = tuple(str(p) for p in raw_passages if isinstance(p, str) and p.strip())
    kept, _dropped = keep_verbatim(passages, source_text)
    return DistilledDoc(
        source_doc_id=doc_id,
        dtype=DistilledType.BOOK,
        title=title[:200],
        summary=str(obj.get("summary", "")),
        tags=tuple(str(t) for t in obj.get("tags", []))[:8],
        description=str(obj.get("description", "")),
        concepts=tuple(str(c) for c in obj.get("concepts", []))[:12],
        passages=kept,
    )


def apply_book(
    path: Path, sections: list, *, model_tag: str = "frontier-agent-haiku", haiku: bool = False
):  # noqa: ANN201 - Path
    """Assemble the mirror fiche for ``path`` from the agent's ``sections`` (a list, one JSON obj per section).

    ``haiku`` picks the SAME chunk profile the emission used, so the sections line up 1:1. It defaults to the
    FINE profile because that is the one that works: the big "Haiku-sized" sections make a THIN fiche (D145
    rule 1). Raises if the count does not match (never a silent partial) - which is also what catches an
    emission/apply profile mismatch. Atomic write (``.tmp`` -> ``os.replace``) like ``distill_book``."""
    text = path.read_text(encoding="utf-8", errors="replace")
    title = _clean_title(path.stem)
    doc_id = f"library/{path.stem[:50]}"
    out = _distilled_path_for(path)
    out.parent.mkdir(parents=True, exist_ok=True)

    target_chars, max_run = (
        (HAIKU_TARGET_CHARS, HAIKU_MAX_RUN) if haiku else (_TARGET_CHARS, _MAX_RUN)
    )
    chunks = chunk_book(text, target_chars=target_chars, max_run=max_run)
    if len(sections) != len(
        chunks
    ):  # completeness EXIGED - an agent that skipped sections is refused
        raise SystemExit(
            f"REFUSED: the agent returned {len(sections)} section(s), {len(chunks)} expected "
            f"(same profile {'HAIKU' if haiku else 'GLM'}). Fiche not written - the agent must redo it."
        )

    tmp = out.with_name(out.name + ".tmp")
    tmp.write_text(
        _frontmatter(path, title, doc_id, len(chunks), model_tag, text), encoding="utf-8"
    )
    toc: list[tuple[int, str, tuple[str, ...]]] = []
    for i, ((sec_title, sec_text), obj) in enumerate(zip(chunks, sections), 1):
        if (
            not obj
        ):  # the agent flagged this section as not done -> L3 flag, raw stays the source (D85)
            with tmp.open("a", encoding="utf-8") as fh:
                fh.write(
                    f"\n## {i}. {sec_title}\n\n"
                    "> WARNING: _(section not distilled by the agent: needs reprocessing - the raw stays the source, D85)_\n"
                    f"<!-- mnemosyne:distill-failed chunk={i} -->\n"
                )
            print(f"  [{i}/{len(chunks)}] empty section -> L3 flag | {sec_title[:44]!r}", flush=True)
            continue
        doc = _doc_from_json(obj, sec_text, sec_title, doc_id)
        with tmp.open("a", encoding="utf-8") as fh:
            fh.write(_section_md(i, sec_title, doc))
        toc.append((i, sec_title, tuple(doc.concepts)))
        print(
            f"  [{i}/{len(chunks)}] {len(doc.passages):2} passages verbatim | {sec_title[:44]!r}",
            flush=True,
        )
    _finalize_toc(tmp, toc)
    os.replace(tmp, out)
    print(f"\nFiche assembled (in code, the verbatim floor applied): {out}", flush=True)
    return out


def expected_sections(path: Path, *, haiku: bool) -> int:
    """The number of sections the SAME `chunk_book` produces - the completeness reference."""
    text = path.read_text(encoding="utf-8", errors="replace")
    target_chars, max_run = (
        (HAIKU_TARGET_CHARS, HAIKU_MAX_RUN) if haiku else (_TARGET_CHARS, _MAX_RUN)
    )
    return len(chunk_book(text, target_chars=target_chars, max_run=max_run))


def _escape_inner_quotes(raw: str) -> str:
    """Implementation behavior is covered by tests."""
    out: list[str] = []
    in_string = False
    i, n = 0, len(raw)
    while i < n:
        c = raw[i]
        if not in_string:
            out.append(c)
            in_string = c == '"'
            i += 1
        elif c == "\\":  # already-escaped pair travels through untouched
            out.append(raw[i : i + 2])
            i += 2
        elif c == '"':
            j = i + 1
            while j < n and raw[j] in " \t\r\n":
                j += 1
            if j >= n or raw[j] in ",:}]":  # a real closing quote
                out.append(c)
                in_string = False
            else:
                out.append('\\"')  # content the agent forgot to escape
            i += 1
        else:
            out.append(c)
            i += 1
    return "".join(out)


def _unescape_over_escaped_closers(raw: str) -> str:
    """Implementation behavior is covered by tests."""
    return re.sub(r'\\"(\s*[,}\]])', r'"\1', raw)


def _strip_fence(raw: str) -> str:
    """Drop a ```json fence an agent wrapped its answer in - the likeliest slip, and pure envelope."""
    return re.sub(r"^\s*```(?:json)?\s*|\s*```\s*$", "", raw)


_REPAIRS = (
    _strip_fence,
    _escape_inner_quotes,
    _unescape_over_escaped_closers,
    lambda raw: _escape_inner_quotes(_unescape_over_escaped_closers(raw)),
    lambda raw: _escape_inner_quotes(_strip_fence(raw)),
)

_SCHEMA_KEYS = frozenset({"title", "summary", "tags", "description", "concepts", "passages"})


def _loads_agent_json(f: Path):  # noqa: ANN202 - parsed JSON
    """Implementation behavior is covered by tests."""
    raw = f.read_text(encoding="utf-8")
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        first = exc
    for repair in _REPAIRS:
        try:
            obj = json.loads(repair(raw))
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and set(obj) == _SCHEMA_KEYS:
            return obj
    raise SystemExit(
        f"REFUSED: {f.name} is not JSON repairable without risk ({first}).\n"
        f"  -> rerun an agent on THIS section (make distill-emit ... RANGE=n:n), then re-apply."
    ) from first


def sections_from_dir(directory: Path, expected: int) -> list:
    """Stitch the SLICES back together: read the `section_<i>.json` files (GLOBAL 1-based index)
    written by the agents, put them back in order, and REFUSE if any are missing - an agent slice
    that never landed is a NAMED hole, never a silently short fiche. The message says exactly which
    sections to rerun."""
    found: dict[int, object] = {}
    for f in sorted(directory.glob("section_*.json")):
        try:
            idx = int(f.stem.split("_", 1)[1])
        except (IndexError, ValueError):
            continue  # a file outside the naming convention is never taken for a section
        found[idx] = _loads_agent_json(f)
    missing = [i for i in range(1, expected + 1) if i not in found]
    if missing:
        raise SystemExit(
            f"REFUSED: {len(missing)} section(s) missing out of {expected} in {directory}: {missing}\n"
            "  -> rerun an agent on THESE sections (make distill-emit ... RANGE=a:b), then re-apply."
        )
    return [found[i] for i in range(1, expected + 1)]


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    haiku = "--haiku" in args
    positional = [a for a in args if a != "--haiku"]
    if len(positional) < 2:
        print(
            'Usage: make distill-apply BOOK="<path.md>" SECTIONS="<responses.json|folder/>" [HAIKU=1]'
        )
        return 1
    path = Path(positional[0])
    sections_path = Path(positional[1])
    if sections_path.is_dir():  # agent slices: one `section_<i>.json` per section
        payload = sections_from_dir(sections_path, expected_sections(path, haiku=haiku))
    else:
        payload = json.loads(sections_path.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            print(
                "SECTIONS must be a JSON ARRAY (one object per section, in order).",
                file=sys.stderr,
            )
            return 1
    apply_book(path, payload, haiku=haiku)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
