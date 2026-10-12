#!/usr/bin/env python3
"""Implementation behavior is covered by tests."""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Import the sibling module `distill_book`: REUSE its real code (chunking, mirror path, frontmatter,
# flag-fiche) instead of recopying a single line - recopying is exactly the drift this kills. The
# body of `distill_book` has no side effects (constants + defs, lazy mnemosyne imports), so it is
# safe to load.
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))
from distill_book import (  # noqa: E402
    HAIKU_MAX_RUN,
    HAIKU_TARGET_CHARS,
    _DISTILLED,
    _MAX_RUN,
    _RAW,
    _TARGET_CHARS,
    _clean_title,
    _distilled_path_for,
    _frontmatter,
    _section_md,
    _source_unusable_md,
    _toc_block,
    chunk_book,
    section_input,
)

_RULE = "=" * 88
_THIN = "-" * 88


class _Gabarit:
    """A PLACEHOLDER document: what `_section_md` renders when given blanks to fill in."""

    description = (
        "<P2 description of THIS section: what the source actually says, neutral and attributed "
        '("the author argues...") -- never a generic template>'
    )
    concepts = ("<concept 1>", "<concept 2>", "<concept 3>")
    passages = (
        "<passage 1: LITERAL copy, word for word, contiguous -- do not rephrase anything>",
        "<passage 2: same, separated from the previous one by ONE blank line>",
    )


def assembly_skeleton(n_sections: int) -> list[str]:
    """The assembly skeleton, RENDERED by the code that actually assembles fiches.

    This is the fix for the skill's internal contradiction (G4, differential trial of
    YYYY-MM-DD): the emission used to say "then assemble (SKILL.md)", while the SKILL states in bold
    that "the contract comes from the CODE, never from a copy." The assembly format - sentinels,
    column 0, a mandatory blank line before AND after the passages - existed ONLY in that prose, on
    the exact surface the skill itself describes as a trap ("without the blank line, a passage
    glued to a sentinel gets SWALLOWED").

    Here, nothing is described: `_section_md` and `_toc_block` - the functions `make distill` and
    `make distill-apply` use to write real fiches - RENDER the skeleton. An agent that copies it
    can no longer get a blank line wrong, and the day the format changes, the emission changes
    with it with nobody having to remember a piece of prose.
    """
    return [
        "ASSEMBLY SKELETON - rendered by `_section_md` / `_toc_block`, THE code that assembles",
        "fiches on the 3 other paths. This is not a description of the format: it IS the format.",
        f"Order: the FRONTMATTER above, then the `## Sommaire` block, then the {n_sections} chapters.",
        "Copy the lines exactly as they are (sentinels at COLUMN 0, blank lines included) and",
        "replace the <...>. The real numbers and titles are the ones in the prompts below.",
        _THIN,
        _toc_block(
            [(i, f"<actual title of section {i}>", _Gabarit.concepts) for i in (1, 2)]
        ).rstrip("\n"),
        f"- ... one line per section, up to {n_sections}",
        "",
        _section_md(1, "<actual title of section 1>", _Gabarit()).rstrip("\n"),
        _THIN,
        "",
    ]


def build_emission(
    text: str,
    title: str,
    doc_id: str,
    out: Path,
    max_chunks: int | None = None,
    *,
    force: bool = False,
    target_chars: int = _TARGET_CHARS,
    max_run: int = _MAX_RUN,
    sec_range: tuple[int, int] | None = None,
    source_path: Path | None = None,
) -> str:
    """Implementation behavior is covered by tests."""
    from mnemosyne.production import (
        DISTILL_SCHEMA,
        assess_source_quality,
        build_prompt,
    )

    # The identity card (Ch.2) needs the SOURCE path, not the mirror `out`: use `source_path` when the
    # caller threads it (main / _emit_split do), else reconstruct raw<-distilled (exact inverse of
    # _distilled_path_for for an on-shelf book). An off-shelf slug reconstructs to a path with no <type>
    # segment, which `_book_sensitivity` fails safe to `sensible` - never a spurious `public`.
    if source_path is not None:
        book_path = source_path
    else:
        try:
            book_path = _RAW / out.relative_to(_DISTILLED)
        except ValueError:
            book_path = out

    lines = [f"OUT (mirror path, derived from the raw): {out}", _RULE, ""]

    quality = assess_source_quality(text)
    if not quality.ok and not force:
        lines += [
            f"SOURCE-QUALITY GATE: NOT OK -> {quality.reason}",
            "Write THIS flag-fiche at the OUT path above, then STOP (no distillation):",
            _THIN,
            _source_unusable_md(title, doc_id, quality).rstrip("\n"),
            _THIN,
        ]
        return "\n".join(lines) + "\n"
    if not quality.ok:
        lines.append(
            f"SOURCE-QUALITY GATE: NOT OK ({quality.reason}) - FORCE -> emitting anyway"
        )
    else:
        lines.append(
            f"SOURCE-QUALITY GATE: OK (letters={quality.letters_ratio:.2f} "
            f"digits={quality.digit_ratio:.2f} prose={quality.prose_char_ratio:.2f})"
        )

    chunks = chunk_book(text, target_chars=target_chars, max_run=max_run)
    if max_chunks:
        chunks = chunks[:max_chunks]

    schema = json.dumps(json.loads(DISTILL_SCHEMA), indent=2)
    lines += ["", "JSON SCHEMA - every section response MUST conform to it:", schema, ""]
    lines += [
        f"Exact FRONTMATTER of the fiche ({len(chunks)} chapters) - copy it as-is at the top:",
        _THIN,
        _frontmatter(book_path, title, doc_id, len(chunks), "frontier", text).rstrip("\n"),
        _THIN,
        "",
    ]
    # SLICE (sec_range): a big book does not fit in ONE agent's context - a slice of sections is
    # emitted instead (GLOBAL numbering kept: `i/N`), one agent per slice, and `distill-apply --dir`
    # stitches it all back together, checking that no section is missing. Without a range: output
    # UNCHANGED (non-drifting).
    lo, hi = sec_range if sec_range else (1, len(chunks))
    lines += [
        (
            f"{len(chunks)} SECTION(S) total - SLICE EMITTED: sections {lo} to {hi}. "
            "Answer EVERY prompt below in JSON matching the schema."
            if sec_range
            else f"{len(chunks)} SECTION(S) - answer EVERY prompt in JSON matching the schema, then assemble:"
        ),
        "",
    ]
    # The skeleton is emitted only on the path where the agent assembles it ITSELF. A slice
    # (`sec_range`) and split mode are stitched back together by `distill-apply`: their agent must
    # not assemble anything, and bytes it cannot use would be duplicated on every slice.
    if sec_range is None:
        lines += assembly_skeleton(len(chunks))
    for i, (sec_title, sec_text) in enumerate(chunks, 1):
        if not (lo <= i <= hi):
            continue
        lines += [
            _RULE,
            f"### PROMPT SECTION {i}/{len(chunks)} - chapter: {sec_title!r}",
            _RULE,
            build_prompt(section_input(doc_id, sec_title, sec_text)).rstrip("\n"),
            "",
        ]
    return "\n".join(lines) + "\n"


SECTIONS_PER_AGENT = 5
"""Sections handed to ONE Haiku agent - the measured sweet spot (D145), not a guess.

Bigger slices are *worse*, twice over: an agent re-sends its whole accumulated context on every tool call, so
loading one agent costs far more than adding agents; and it starts skimping near the end of a long list. The
number of AGENTS scales with the book, the slice does not (user, YYYY-MM-DD)."""


def agent_slices(n: int, per: int = SECTIONS_PER_AGENT) -> list[tuple[int, int]]:
    """Split sections ``1..n`` into agent slices of AT MOST ``per``, spreading the remainder EVENLY.

    Even matters: naive ceil-then-fill leaves the last agent a 1-section crumb (n=36 -> 5,5,5,5,5,5,5,1), which
    wastes a whole agent's startup on nothing. Balancing gives 5,5,5,5,4,4,4,4. Total coverage of 1..n with no
    hole and no overlap is the invariant - a hole silently drops a section, an overlap distills it twice."""
    n_agents = max(1, -(-n // per))
    base, extra = divmod(n, n_agents)
    out: list[tuple[int, int]] = []
    lo = 1
    for a in range(n_agents):
        size = base + (1 if a < extra else 0)
        out.append((lo, lo + size - 1))
        lo += size
    return out


def book_toc(
    text: str, *, target_chars: int = _TARGET_CHARS, max_run: int = _MAX_RUN
) -> list[tuple[int, str, int]]:
    """Implementation behavior is covered by tests."""
    chunks = chunk_book(text, target_chars=target_chars, max_run=max_run)
    return [(i, title, len(body)) for i, (title, body) in enumerate(chunks, 1)]


def render_toc(toc: list[tuple[int, str, int]], *, quoi: str = "SECTION(S)") -> str:
    """The map, printable. Carries its own total so nobody ever has to add it up by hand.

    ``quoi`` names what is being looked at, because this function ALSO renders a SELECTION (the
    chapters that match a ``--chapter``). Rendered with the default label, a 2-line selection would
    announce "2 SECTION(S)" and a total of 59,500 characters: the reader would think they were
    looking at the whole book. A summary that lies while the body tells the truth - the class is
    closed here by naming the population, never by assuming the whole thing is always rendered.

    The index width is taken from the LARGEST index, not the NUMBER of lines: on a selection, two
    entries where one carries index 13 would fit a width of 1 and go misaligned. Formatting derived
    from the wrong number is the same defect, just smaller.
    """
    width = max((len(str(i)) for i, _, _ in toc), default=1)
    lines = [f"{len(toc)} {quoi} - index | title | characters", _RULE]
    lines += [f"{i:>{width}} | {title} | {size}" for i, title, size in toc]
    lines += [_RULE, f"total: {sum(size for _, _, size in toc)} characters"]
    return "\n".join(lines) + "\n"


def _match_key(value: str) -> str:
    """Matching key for a title: lowercase, everything that is not alphanumeric stripped out.

    Not cosmetic - it is the heart of the fix. The real title that cost the original measurement
    reads ``'A CKNOWLEDGMENTS'``: the OCR inserted a space after the first letter. A naive substring
    search for ``ACKNOWLEDGMENTS`` does NOT find it, and the tool would have answered "no chapter by
    that name" on the exact case that motivated it. The corpus is OCR text: matching has to run on
    what SURVIVES OCR, not on what a title should look like.
    """
    return "".join(char for char in value.lower() if char.isalnum())


def resolve_chapter(toc: list[tuple[int, str, int]], needle: str) -> list[tuple[int, str, int]]:
    """The sections whose title CONTAINS ``needle``, matched via :func:`_match_key`. Can be empty."""
    key = _match_key(needle)
    return [entry for entry in toc if key and key in _match_key(entry[1])]


def _emit_split(
    directory: Path,
    book: Path,
    text: str,
    title: str,
    doc_id: str,
    out: Path,
    max_chunks: int | None,
    *,
    force: bool,
    target_chars: int,
    max_run: int,
) -> int:
    """Implementation behavior is covered by tests."""
    n = len(chunk_book(text, target_chars=target_chars, max_run=max_run))
    if max_chunks is not None:
        n = min(
            n, max_chunks
        )  # else files WITHOUT a prompt would be emitted (build_emission truncates, we don't)
    directory.mkdir(parents=True, exist_ok=True)
    for i in range(1, n + 1):
        emission = build_emission(
            text,
            title,
            doc_id,
            out,
            max_chunks,
            force=force,
            target_chars=target_chars,
            max_run=max_run,
            sec_range=(i, i),
            source_path=book,
        )
        (directory / f"sec_{i:03d}.md").write_text(emission, encoding="utf-8")
    (directory / "BOOK_PATH.txt").write_text(str(book), encoding="utf-8")  # the BOOK, not the fiche

    slices = agent_slices(n)
    print(f"{n} sections emitted -> {directory}")
    print(
        f"\nPLAN: {len(slices)} HAIKU agents (<= {SECTIONS_PER_AGENT} sections each) - HAIKU ONLY (user rule)."
    )
    print(f"Brief to hand to EACH agent: {_HERE / 'AGENT_BRIEF.md'}")
    for a, (lo, hi) in enumerate(slices, 1):
        print(f"  agent {a:2}: sections {lo}-{hi}")
    print("\nThen, once the agents have written their section_<i>.json files:")
    print(f'  make distill-apply BOOK="{book}" SECTIONS="<folder of json files>"')
    return 0


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    force = "--force" in args
    haiku = "--haiku" in args  # Haiku-sized section profile (the frontier agent path)
    split_dir = None
    if (
        "--split-dir" in args
    ):  # `--split-dir <dir>`: ONE prompt file per section + the agent plan
        i = args.index("--split-dir")
        if i + 1 < len(args):
            split_dir = Path(args[i + 1])
            del args[i : i + 2]  # consume the flag AND its value
    sommaire = "--sommaire" in args  # print the MAP (index|title|size) and nothing else
    sec_range = None
    if (
        "--range" in args
    ):  # `--range A:B`: emit only sections A..B (a SLICE for ONE agent)
        i = args.index("--range")
        if i + 1 < len(args):
            lo_s, _, hi_s = args[i + 1].partition(":")
            sec_range = (int(lo_s), int(hi_s))
            del args[
                i : i + 2
            ]  # consume the flag AND its value (else it would pass through as positional)
    chapter = None
    if "--chapter" in args:  # `--chapter "TITLE"`: target a section by its NAME, not its rank
        i = args.index("--chapter")
        if i + 1 < len(args):
            chapter = args[i + 1]
            del args[i : i + 2]
    positional = [a for a in args if a not in ("--force", "--haiku", "--sommaire")]
    if not positional:
        print(
            'Usage: make distill-emit BOOK="<path.md>" [CHUNKS=N] [FORCE=1] [HAIKU=1] '
            '[RANGE=A:B] [CHAPTER="title"]   |   make distill-sommaire BOOK="<path.md>"'
        )
        return 1
    if chapter is not None and sec_range is not None:
        print("RANGE and CHAPTER together: ambiguous. Choose one or the other.", file=sys.stderr)
        return 1
    path = Path(positional[0])
    max_chunks = int(positional[1]) if len(positional) > 1 else None
    text = path.read_text(encoding="utf-8", errors="replace")
    title = _clean_title(path.stem)
    doc_id = f"library/{path.stem[:50]}"
    out = _distilled_path_for(
        path
    )  # MIRROR path of the raw (raw/ -> distilled/), derived, never hand-typed
    target_chars = HAIKU_TARGET_CHARS if haiku else _TARGET_CHARS
    max_run = HAIKU_MAX_RUN if haiku else _MAX_RUN
    if sommaire or chapter is not None:
        toc = book_toc(text, target_chars=target_chars, max_run=max_run)
        if max_chunks:
            toc = toc[
                :max_chunks
            ]  # same truncation as the emission, else the map lies about what comes out
        if sommaire:
            print(render_toc(toc), end="")
            return 0
        found = resolve_chapter(toc, chapter or "")
        if len(found) != 1:
            # Zero or several: REFUSE and name the gesture. Silently taking the first would be a
            # silent loss - the caller would believe it targeted what it named.
            why = "no chapter" if not found else f"{len(found)} chapters"
            print(
                f'CHAPTER="{chapter}" -> {why} match(es). Be more specific, or target with RANGE.',
                file=sys.stderr,
            )
            print(
                render_toc(found, quoi="MATCHING CHAPTER(S)")
                if found
                else render_toc(toc),
                end="",
                file=sys.stderr,
            )
            return 1
        sec_range = (found[0][0], found[0][0])
    if split_dir is not None:
        return _emit_split(
            split_dir,
            path,
            text,
            title,
            doc_id,
            out,
            max_chunks,
            force=force,
            target_chars=target_chars,
            max_run=max_run,
        )
    print(
        build_emission(
            text,
            title,
            doc_id,
            out,
            max_chunks,
            force=force,
            target_chars=target_chars,
            max_run=max_run,
            sec_range=sec_range,
            source_path=path,
        ),
        end="",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
