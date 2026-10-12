#!/usr/bin/env python3
"""Distill an ENTIRE BOOK into ONE chaptered fiche (production brick 3; D28 / D143 verbatim).

A book (500k-2M chars) exceeds the runner's cap (48k chars/call): it gets SPLIT into sections
(at markdown heading boundaries, chunks <= ~26k chars - robust to OCR noise: sized on
length + a heading), each section is distilled via the distiller through the real governed stack,
and re-ASSEMBLED into ONE chaptered fiche (operator rule: 1 fiche/book, chapters inside -> a single
tag set, chapter info stays findable). P3 stays VERBATIM per section (the `keep_verbatim` barrier,
D143); P2 (description/concepts) is a free synthesis. The verbatim block is SELF-DELIMITED (the
`verbatim-begin/end` sentinels, `mnemosyne.production.chapter_parsing`): a `## N.` line QUOTED from an
OCR source can live inside it without being mistaken for a chapter heading by the judge / the
finisher (D143) - P3 stays intact.

Default model = GLM-4-9B (the distillation pick: the fastest AND most faithful on the real
`bench_distillation` bench). Mirror output path: `knowledge/distilled/<...>` reuses the tree and
name of `knowledge/raw/<...>` (`raw/`->`distilled/`, DERIVED, never hand-typed - operator rule,
campaign-wide). ATOMIC write: the fiche is built in a `.tmp` file then swapped in with `os.replace`
at the end, so an interrupted re-run does NOT destroy the previous fiche. A 3-level robustness net
per section (D85): (1) the decoder REPAIRS a near-miss JSON (a governed barrier + `close_json`, safe
thanks to the verbatim floor); (2) else the section gets SUB-CHUNKED (cut in half, each half
distilled, then merged); (3) else a visible FLAG plus a machine marker flags the section for
reprocessing (the raw stays the source of truth).
Entirely LOCAL (a personal book, D27/D66).

Body of the `distillateur` skill (SEED_SKILLS['distillateur'], D39-4): see the SKILL.md next to it.
It is THE single path (local agent, frontier agent, tests all invoke it identically). Local
invocation:
    make distill BOOK="knowledge/raw/<domain>/<book>.md" [CHUNKS=N]
"""

from __future__ import annotations

import os
import re
import sys
import time
from pathlib import Path

_MODEL = "mlx-community/GLM-4-9B-0414-4bit"
# WARNING: `_TARGET_CHARS` is CALIBRATED FOR THIS MODEL: changing the model changes the chunking
# assumption, and nobody has re-measured it for another one.
_TARGET_CHARS = 26_000  # target/chunk: < the runner's 48k cap (template+schema margin) + a size where GLM stays fast
_MAX_RUN = 44_000  # hard cut if no heading shows up before this (stays under the 48k cap)
# HAIKU profile (frontier) - Claude Haiku 4.5 has a ~200k-token context and understands far better than
# the local 9B-4bit model: sections are sized for ITS scale instead (the way _TARGET_CHARS was sized for
# GLM, D-operator YYYY-MM-DD), so bigger -> one section = one real chapter never cut in two, fewer calls,
# richer context per section. Used by the frontier path via the emission (agent: no runner cap there).
# The backend-API path stays bounded by the runner cap until it is raised for Haiku ((3)) - hence a
# profile, not a constant.
HAIKU_TARGET_CHARS = 60_000
HAIKU_MAX_RUN = 120_000
_RAW = Path("knowledge/raw")
_DISTILLED = Path("knowledge/distilled")
_HEADING = re.compile(r"^#{1,4} \S")
_SUBCHUNK_MIN = (
    3_000  # below this size a split no longer helps the decoder -> flag it (D85 level 3)
)
_SUBCHUNK_MAX_DEPTH = (
    2  # a failing section is cut in half at most twice (chunk -> 4 pieces max)
)


def _clean_title(stem: str) -> str:
    """Readable title from the OCR filename ("... -- Author -- 2015 --" -> "... - Author")."""
    parts = [
        p.strip() for p in stem.split(" -- ") if p.strip() and not re.fullmatch(r"\d{4}", p.strip())
    ]
    return " - ".join(parts[:2]) if parts else stem.strip()


def _distilled_path_for(src: Path) -> Path:
    """MIRROR path of the fiche: the raw path with `raw/` -> `distilled/` (same tree + same name).

    operator rule (campaign-wide): whatever changes under `raw` (moving, reclassifying, renaming),
    `distilled` moves IDENTICALLY. The path is DERIVED from the raw, never hand-typed. Fallback = a
    flat file (a slug) when the input is NOT under `knowledge/raw/` (e.g. an off-shelf test `.md`)."""
    try:
        rel = src.resolve().relative_to(_RAW.resolve())
    except ValueError:
        slug = re.sub(r"[^\w]+", "-", _clean_title(src.stem)).strip("-")[:60] or "untitled"
        return _DISTILLED / f"{slug}.md"
    return _DISTILLED / rel


def chunk_book(
    text: str, *, target_chars: int = _TARGET_CHARS, max_run: int = _MAX_RUN
) -> list[tuple[str, str]]:
    """Split into (section_title, text): chunks <= ``target_chars``, cut at a heading boundary.

    The thresholds are PARAMETERS (default = the local GLM profile) so the split can be tuned to the
    target model's capacity: the frontier path passes the HAIKU profile (bigger - :data:`HAIKU_TARGET_CHARS`
    / :data:`HAIKU_MAX_RUN`), the way 26k was calibrated for GLM. ``max_run`` = a hard cut if no heading
    shows up before it (bounds the section)."""
    chunks: list[tuple[str, str]] = []
    cur: list[str] = []
    cur_len = 0
    title: str | None = None
    for line in text.split("\n"):
        is_head = bool(_HEADING.match(line))
        if (
            cur_len >= target_chars and is_head
        ):  # big enough AND we're at a new heading -> cut here
            chunks.append((title or "(section)", "\n".join(cur)))
            cur, cur_len, title = [], 0, None
        if is_head and title is None:
            title = line.lstrip("# ").strip()
        cur.append(line)
        cur_len += len(line) + 1
        if cur_len >= max_run:  # no heading showed up -> hard cut by size
            chunks.append((title or "(section)", "\n".join(cur)))
            cur, cur_len, title = [], 0, None
    if any(s.strip() for s in cur):
        chunks.append((title or "(section)", "\n".join(cur)))
    return chunks


def _local_backend(model_id: str):  # noqa: ANN202 - GenerationBackend, lazy import (brick)
    """The default LOCAL decode backend (MLX + Outlines grammar). Wrapped in Outlines when available so
    structured decode is grammar-constrained; the runner re-checks either way (invariant 27)."""
    from mnemosyne.runtime.runner_mlx import load_mlx_backend

    backend = load_mlx_backend(
        model_id=model_id, max_tokens=4096
    )  # margin > the schema's max output (else the JSON gets truncated)
    try:
        from mnemosyne.runtime.runner_outlines import connect_outlines

        backend = connect_outlines(backend)
    except Exception as exc:  # noqa: BLE001
        print(f"  (Outlines unavailable: {exc!r} -> raw backend)", flush=True)
    return backend


def _make_api(backend: object):  # noqa: ANN202 - CoreApi, lazy import (brick)
    """Wrap a GenerationBackend in the full governed CoreApi (same lean bootstrap for local OR frontier).

    The backend is the ONLY thing that changes between the local campaign (MLX/GLM) and the frontier one
    (Haiku): the whole faithful pipeline below is backend-agnostic, so a book distils identically either
    way - only faster in parallel over the network (D95)."""
    from mnemosyne.api import CoreApi
    from mnemosyne.runtime.bootstrap import bootstrap

    return CoreApi(bootstrap(generation_backend=backend))


def _detect_lang(text: str) -> str:
    """Implementation behavior is covered by tests."""
    sample = text[:20_000].lower()
    # The words below are DATA, not prose: a cheap fr/en stop-word count over a French-language
    # corpus. Do not translate them - swapping them for English would silently break detection.
    fr = sum(
        sample.count(w)
        for w in (
            " le ",
            " la ",
            " les ",
            " des ",
            " une ",
            " est ",
            " dans ",
            " que ",
            " qui ",
            " pour ",
            " avec ",
            " sur ",
        )
    )
    en = sum(
        sample.count(w)
        for w in (
            " the ",
            " and ",
            " of ",
            " to ",
            " in ",
            " is ",
            " that ",
            " for ",
            " with ",
            " was ",
            " it ",
        )
    )
    return "fr" if fr > en else "en"


def _shelf_rel(path: Path) -> tuple[str, ...] | None:
    """The book's path parts RELATIVE to the ``knowledge/raw`` shelf, or ``None`` when the source is
    OFF-shelf (an ad-hoc / test ``.md``). ONE place decides "on the shelf?" so ``domain`` and
    ``sensitivity`` below stay mutually consistent (both degrade together off-shelf)."""
    try:
        return path.resolve().relative_to(_RAW.resolve()).parts
    except ValueError:
        return None


#: Shelf ``<type>`` segments whose PROVENANCE is public - a published book or a YouTube transcript, the two
#: ingest routes that pass ``public_provenance=True`` (D144). EVERY other type (``chats``, personal captures)
#: is NOT declassified and fail-safes to ``sensible`` (D101). This encodes the SAME public/sensible split the
#: ingest makes by WHICH route runs; it is the distiller's local, type-aware reading of that rule, not a
#: shared foyer with the ingest routing (a later lot could consolidate them) - so keep it honest, not
#: over-claimed.
_PUBLIC_PROVENANCE_TYPES = frozenset({"books", "youtube"})


def _book_sensitivity(path: Path) -> str:
    """Implementation behavior is covered by tests."""
    from mnemosyne.ingest import taxonomy
    from mnemosyne.ports import Sensitivity

    rel = _shelf_rel(path)
    if rel is None:
        return Sensitivity.SENSIBLE.token  # off-shelf -> fail-safe (D101)
    if (
        rel[0] in taxonomy.PERSONAL_FAMILIES
    ):  # intimate family -> sensible, whatever the type (D149)
        return Sensitivity.SENSIBLE.token
    for seg in rel:  # else the FIRST recognised <type> segment decides (mirrors domain_from_parts)
        if seg in (taxonomy.TYPES or frozenset()):
            return (
                Sensitivity.PUBLIC.token
                if seg in _PUBLIC_PROVENANCE_TYPES
                else Sensitivity.SENSIBLE.token
            )
    return Sensitivity.SENSIBLE.token  # no recognised <type> -> fail-safe (D101)


def _ingested_at(path: Path) -> str:
    """ISO-8601 UTC timestamp for the D33 "date d'ajout" - the raw file's mtime, a BEST-EFFORT proxy: it is
    the last-MODIFICATION time, so a later re-OCR / vision enrichment of the raw moves it forward (it is not
    a persisted ingest date). Stable per file otherwise; falls back to now() if the file has no stat, so it
    never blocks a distillation."""
    from datetime import datetime, timezone

    try:
        dt = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    except OSError:
        dt = datetime.now(timezone.utc)
    return dt.isoformat()


def _identity_card(
    path: Path, title: str, doc_id: str, n_chunks: int, model_id: str, text: str, dtype: str
) -> dict[str, object]:
    """Assemble the P1 identity card (D33 / D121-C2 canonical names, encoded in
    :data:`~mnemosyne.production.frontmatter.FRONTMATTER_FIELDS`) from what the distiller holds at write
    time - closing Chantier 2 (a fiche carried only 5 of the ~12 decided fields). Every value is DERIVED
    deterministically from the source path / text / distiller identity, never invented:

    * ``domain`` / ``source_path`` from the shelf path (reusing :func:`taxonomy.domain_from_parts`, the
      single source), and ``sensitivity`` from a FAMILY-and-TYPE-aware reading (:func:`_book_sensitivity`:
      intimate families and non-published types -> ``sensible``, published ``books`` / ``youtube`` -> ``public``);
    * ``lang`` from a cheap fr/en heuristic (:func:`_detect_lang`);
    * ``template`` / ``version`` from the distiller identity, so a regen can tell a fiche is STALE - the
      one concrete functional gap Ch.2 named (idempotent regen had no ``template`` to compare against);
    * ``content_type`` (the D30 GENRE axis) is the ONE field no deterministic signal fills: emitted as the
      honest COARSE default ``reference`` - a distilled book fiche IS a reference artifact - because
      per-book genre is model judgement not yet computed. NAMED residual, not a fake-precise guess
      ([[honest-docstrings-not-flattering]]).

    Off-shelf sources (ad-hoc / test ``.md``) honestly OMIT ``domain`` (no shelf => no shelf-domain): the
    card is then knowingly incomplete and :func:`validate_frontmatter` reports it - correct, not a silent
    fill. ``distilled_by`` / ``chapters`` are kept as bonus fields (the validator ignores unknown keys; the
    juge reads ``chapters``)."""
    from mnemosyne.ingest import taxonomy
    from mnemosyne.production import Distillateur

    rel = _shelf_rel(path)
    ident = f"{Distillateur.name}/{Distillateur.version}"  # single source: never re-type "distillateur/0.1.0"
    card: dict[str, object] = {"title": title, "source": title, "lang": _detect_lang(text)}
    domain = taxonomy.domain_from_parts(rel) if rel is not None else None
    if domain:  # off-shelf => absent, honestly (a required field the validator will flag - not a fake value)
        card["domain"] = [str(domain)]
    card["format"] = dtype  # FORME axis (D30) - reuses the DistilledType token, no second literal
    card["content_type"] = (
        "reference"  # GENRE axis (D30) - coarse honest default; per-book genre = future model work
    )
    card["sensitivity"] = _book_sensitivity(path)
    card["status"] = (
        "distille"  # this artifact IS a distilled fiche (D33 pipeline stage; open set, non-empty)
    )
    card["id"] = doc_id
    card["ingested_at"] = _ingested_at(path)
    card["source_path"] = str(path)
    card["template"] = (
        f"{Distillateur.name}/{dtype}/{Distillateur.version}"  # skill/type/version -> regen staleness
    )
    card["version"] = Distillateur.version
    card["distilled_by"] = (
        f"{ident} ({model_id.split('/')[-1]})"  # bonus: which real backend produced it
    )
    card["chapters"] = n_chunks  # bonus: the chapter count the juge / finisher read back
    return card


def _frontmatter(
    path: Path,
    title: str,
    doc_id: str,
    n_chunks: int,
    model_id: str,
    text: str,
    *,
    dtype: str = "book",
) -> str:
    """Render the fiche's P1 identity card (YAML) + the source-critique banner. The card now carries the
    canonical D33 / D121-C2 fields (Ch.2, via :func:`_identity_card`); the banner and atomic write are
    unchanged. ONE home, emitted to all THREE book voies (backend / emit / agent-apply) so no copy drifts
    ([[contract-single-source-emit]]). ``dtype`` defaults to ``book`` - the only type these voies distil."""
    from mnemosyne.production.distillation import _yaml_scalar

    def _render(value: object) -> str:
        if isinstance(value, list):
            return "[" + ", ".join(_yaml_scalar(str(v)) for v in value) + "]"
        if isinstance(value, int):
            return str(value)
        return _yaml_scalar(str(value))

    card = _identity_card(path, title, doc_id, n_chunks, model_id, text, dtype)
    body = "\n".join(["---", *(f"{k}: {_render(v)}" for k, v in card.items()), "---", ""])
    return (
        body + f"\n# {title}\n\n"
        "> WARNING: **These notes come FROM THE BOOK.** They lay out the author's thesis and claims - "
        "read them critically; this is **not** an established truth, nor an opinion held "
        "by Mnemosyne.\n"
        ">\n"
        "> Distilled chapter by chapter. P3 (Content) = **verbatim** (D143); "
        "Description/Concepts = synthesis. A \"you\" layer is planned (companion, (5)).\n"
    )


def _source_unusable_md(title: str, doc_id: str, quality: object) -> str:
    """Flag-fiche for when the source-quality gate refuses the raw (D85): don't distill mush.

    The raw stays the source of truth (never touched); the distilled slot carries a visible flag plus
    a machine-readable marker `<!-- mnemosyne:source-unusable -->` that the judge / the campaign
    (task 8) greps for to route the book back to re-extraction before any distillation."""
    reason = getattr(quality, "reason", "")
    lr = getattr(quality, "letters_ratio", 0.0)
    dr = getattr(quality, "digit_ratio", 0.0)
    pr = getattr(quality, "prose_char_ratio", 0.0)
    safe_title = title.replace("\\", "\\\\").replace('"', '\\"')  # don't break the YAML (M2 audit)
    return (
        "---\n"
        f'title: "{safe_title}"\n'
        'format: "book"\n'
        f'source: "{doc_id}"\n'
        'distilled_by: "distillateur/0.1.0 (source-gate)"\n'
        "status: source-unusable\n"
        "---\n\n"
        f"# {title}\n\n"
        "> WARNING: **SOURCE NOT USABLE - no distillation.**\n"
        f"> The source `.md` is not distillable prose: {reason}.\n"
        "> (broken extraction / math / tables / code). The raw stays the source of truth (D85) -\n"
        "> it needs a proper re-extraction (an OCR campaign) before distilling.\n"
        f"<!-- mnemosyne:source-unusable letters={lr:.2f} digits={dr:.2f} prose={pr:.2f} -->\n"
    )


def _section_md(idx: int, title: str, doc: object) -> str:
    # Lazy import: the module body stays free of mnemosyne (emit_prompts + tests load it by path, D126).
    from mnemosyne.production.chapter_parsing import (
        PLACEHOLDER_DESCRIPTION,
        PLACEHOLDER_NO_PASSAGE,
        VERBATIM_BEGIN,
        VERBATIM_END,
    )

    concepts = "\n".join(f"- {c}" for c in getattr(doc, "concepts", ()))  # type: ignore[attr-defined]
    passages = "\n\n".join(getattr(doc, "passages", ()))  # type: ignore[attr-defined]
    body = getattr(doc, "description", "").strip()  # type: ignore[attr-defined]
    parts = [f"\n## {idx}. {title}\n", body or PLACEHOLDER_DESCRIPTION]
    if concepts:
        parts.append("\n**Concepts** :\n" + concepts)
    verbatim = passages if passages else PLACEHOLDER_NO_PASSAGE
    # SELF-DELIMITED verbatim block (D143): the fence lets a `## N.` line QUOTED from an OCR source live
    # inside a passage without being mistaken for a chapter boundary by the judge / the finisher.
    # Sentinels sit on their own line, separated by a blank line (the judge counts passages, not
    # markers). P3 stays intact: the fence surrounds the passages, it doesn't touch them (the quoted
    # bytes stay exact substrings of the raw).
    parts.append(f"\n### Contenu (verbatim)\n\n{VERBATIM_BEGIN}\n\n{verbatim}\n\n{VERBATIM_END}")
    return "\n".join(parts) + "\n"


def _split_half(text: str) -> tuple[str, str]:
    """Cut the text near the middle, at a line boundary (content-agnostic: no assumptions made)."""
    mid = len(text) // 2
    nl = text.find("\n", mid)
    if (
        nl == -1 or nl > len(text) - 500
    ):  # no clean boundary after the middle -> look before it instead
        nl = text.rfind("\n", 0, mid)
    if nl <= 0:
        nl = mid  # no line at all: hard cut at the middle (last resort)
    return text[:nl], text[nl:]


def _merge_docs(docs: list, title: str):  # noqa: ANN201 - DistilledDoc (lazy import)
    """Merge the sub-distillates of a sub-chunked section back into ONE doc (D85 level 2).

    Concatenates descriptions + passages (all VERBATIM, already filtered by `keep_verbatim` on their
    sub-piece), dedupes tags and concepts while keeping order (bounded the same as at decode time: 8
    and 12). Passages are NOT re-bounded to 10: they are already-validated source quotations, not a
    model output to re-constrain - a recovered section can therefore carry more of them. The section
    stays ONE section."""
    from mnemosyne.production import DistilledDoc

    def _dedup(seq: list[str]) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for x in seq:
            if x not in seen:
                seen.add(x)
                out.append(x)
        return out

    first = docs[0]
    tags = _dedup([t for d in docs for t in d.tags])[:8]
    concepts = _dedup([c for d in docs for c in d.concepts])[:12]
    passages = tuple(p for d in docs for p in d.passages)
    description = "\n\n".join(d.description.strip() for d in docs if d.description.strip())
    summary = next((d.summary for d in docs if d.summary.strip()), first.summary)
    return DistilledDoc(
        source_doc_id=first.source_doc_id,
        dtype=first.dtype,
        title=title[:200],
        summary=summary,
        tags=tuple(tags),
        description=description,
        concepts=tuple(concepts),
        passages=passages,
    )


def section_input(doc_id: str, title: str, text: str):  # noqa: ANN201 - DistillationInput (lazy import)
    """The DistillationInput for ONE section - the SINGLE source of what a section feeds the model (host parity).

    The LOCAL path (`_distill_section`) AND the frontier emitter (`emit_prompts.build_emission`) both
    build their input HERE: both hosts distill each section identically BY CONSTRUCTION (dtype, title
    truncated to 60), not by a convention that two files would each have to remember to keep in sync -
    the very drift that was killed for the prompt and the chunking, closed here too for the input."""
    from mnemosyne.production import DistillationInput, DistilledType

    return DistillationInput(
        doc_id=doc_id, source_text=text, dtype=DistilledType.BOOK, title_hint=title[:60]
    )


def _distill_section(  # noqa: ANN201
    api: object, doc_id: str, title: str, text: str, *, depth: int = 0, within: object = None
):
    """Distill ONE section, RECOVERING via sub-chunking on failure (D85 level 2). Returns the doc or None.

    Level 1 (deterministic JSON repair) lives in the governed decoder (the `enforce_grammar` +
    `close_json` barrier, safe thanks to the verbatim floor). Here is level 2: if distillation still
    fails (an unrepairable JSON shape, a section too heavy), it is cut in half and each half is
    distilled - a smaller input decodes more reliably - then merged. Content-agnostic: works for
    any doc. Exhausted (max depth, or a piece too small) -> None -> level 3 flags it (never lost
    silently: the raw stays the source, D85).

    ``within`` (a ``Sensitivity`` or None) is the sensitivity floor passed to ``api.distill``: the
    frontier path passes ``PUBLIC`` (a published book - the grant's sealed channel then HONESTLY
    reports channel A, consistent with the real cloud egress, invariant 12); local leaves the default
    (None -> not passed)."""
    from mnemosyne.ports import Bubble

    inp = section_input(doc_id, title, text)
    extra = (
        {"within": within} if within is not None else {}
    )  # local: CoreApi default; frontier: an honest PUBLIC
    try:
        return api.distill(
            inp, subject=Bubble("distill-book"), **extra
        )  # CoreApi.distill returns the DistilledDoc
    except Exception as exc:  # noqa: BLE001 - a failing section doesn't kill the whole book (D85)
        if depth >= _SUBCHUNK_MAX_DEPTH or len(text) < _SUBCHUNK_MIN:
            print(f"      (unrecoverable @depth{depth}: {type(exc).__name__})", flush=True)
            return None
        left, right = _split_half(text)
        print(
            f"      (failed -> sub-chunk @depth{depth}: {len(left)}+{len(right)} chars)", flush=True
        )
        pieces = [
            d
            for d in (
                _distill_section(api, doc_id, title, left, depth=depth + 1, within=within),
                _distill_section(api, doc_id, title, right, depth=depth + 1, within=within),
            )
            if d is not None
        ]
        return _merge_docs(pieces, title) if pieces else None


def _toc_block(toc: list[tuple[int, str, tuple[str, ...]]]) -> str:
    """The `## Sommaire` block - rendered PURE, without touching disk.

    Extracted from `_finalize_toc` so `distill-emit` can EMIT the exact shape instead of having it
    hand-copied: on the path where the agent assembles it itself, the only description of the
    format used to live in the SKILL's prose - exactly the drift this skill declares it kills.
    """
    lines = ["## Sommaire\n"]
    for idx, title, keys in toc:
        gloss = ", ".join(k for k in list(keys)[:3])
        lines.append(f"- [[#{idx}. {title}]]" + (f" - {gloss}" if gloss else ""))
    return "\n".join(lines) + "\n"


def _finalize_toc(out: Path, toc: list[tuple[int, str, tuple[str, ...]]]) -> None:
    """Insert a generated table of contents after the document header."""
    if not toc:
        return
    block = _toc_block(toc)
    text = out.read_text(encoding="utf-8")
    marker = "\n## "  # first chapter
    i = text.find(marker)
    out.write_text(
        text[:i] + "\n" + block + text[i:] if i != -1 else text + "\n" + block, encoding="utf-8"
    )


def distill_one(  # noqa: ANN201 - Path | None; api is a CoreApi (lazy import)
    path: Path,
    *,
    api: object,
    model_id: str,
    max_chunks: int | None = None,
    force: bool = False,
    target_chars: int = _TARGET_CHARS,
    max_run: int = _MAX_RUN,
    within: object = None,
):
    """Distill ONE book into its mirror fiche via the ``api`` given (a LOCAL or FRONTIER backend).
    Returns the path of the fiche written, or ``None`` if the source-quality gate refuses the raw (a
    flag is written instead).

    ``model_id`` = the identity of the REAL backend (local GLM or Haiku), recorded in the frontmatter's
    ``distilled_by`` field for traceability. ``target_chars`` / ``max_run`` tune the chunking to the
    model's capacity (default GLM; the frontier path passes the bigger HAIKU profile). ``within`` = the
    sensitivity floor (frontier: ``PUBLIC`` for an honest channel). All the logic - the D85 gate,
    chunking, the verbatim floor, recovery, the summary, atomic write - is identical regardless of the
    backend: this is THE single path of the skill (D39-4), the frontier campaign only injects a
    different ``api`` into it."""
    from mnemosyne.production import assess_source_quality

    text = path.read_text(encoding="utf-8", errors="replace")
    title = _clean_title(path.stem)
    doc_id = f"library/{path.stem[:50]}"
    out = _distilled_path_for(
        path
    )  # MIRROR path of the raw (raw/ -> distilled/), derived, never hand-typed
    out.parent.mkdir(parents=True, exist_ok=True)

    # Source-quality GATE (D85 / D100): a rotten source (broken extraction, math/tables/code) would
    # distill nothing but mush, which the verbatim floor lets straight through (verbatim mush). So it
    # gets FLAGGED and routed to re-extraction (campaign, task 8) instead of a garbage-in-garbage-out
    # fiche. FORCE overrides this (to recover a false positive on clean prose that re-extraction
    # would not help anyway).
    quality = assess_source_quality(text)
    if not quality.ok and not force:
        tmp = out.with_name(out.name + ".tmp")  # ATOMIC write applies to the flag too (M1 audit)
        tmp.write_text(_source_unusable_md(title, doc_id, quality), encoding="utf-8")
        os.replace(tmp, out)
        print(
            f"SOURCE NOT USABLE -> flag, no distillation ({quality.reason})\n  {out}",
            flush=True,
        )
        return None
    if not quality.ok:
        print(
            f"Rotten SOURCE ({quality.reason}) but FORCE -> distilling anyway", flush=True
        )

    chunks = chunk_book(text, target_chars=target_chars, max_run=max_run)
    if max_chunks:
        chunks = chunks[:max_chunks]
    print(f"Book: {title}\n{len(chunks)} chunk(s) -> {out}", flush=True)

    # ATOMIC write: written into a .tmp file, then swapped in with `os.replace` at the end. An
    # interrupted re-run (kill, restart) no longer DESTROYS the previous fiche - it survives until
    # the rename.
    tmp = out.with_name(out.name + ".tmp")
    tmp.write_text(_frontmatter(path, title, doc_id, len(chunks), model_id, text), encoding="utf-8")
    toc: list[tuple[int, str, tuple[str, ...]]] = []
    for i, (sec_title, sec_text) in enumerate(chunks, 1):
        t0 = time.perf_counter()
        doc = _distill_section(
            api, doc_id, sec_title, sec_text, within=within
        )  # net levels 1-2 (repair + sub-chunk)
        if (
            doc is None
        ):  # level 3: never lost silently - a visible flag + a machine-readable marker (the judge)
            with tmp.open("a", encoding="utf-8") as fh:
                fh.write(
                    f"\n## {i}. {sec_title}\n\n"
                    "> WARNING: _(distillation failed: section needs reprocessing - the raw stays the source, D85)_\n"
                    f"<!-- mnemosyne:distill-failed chunk={i} -->\n"
                )
            print(f"  [{i}/{len(chunks)}] FAILED -> L3 flag | {sec_title[:44]!r}", flush=True)
            continue
        with tmp.open("a", encoding="utf-8") as fh:
            fh.write(_section_md(i, sec_title, doc))
        toc.append((i, sec_title, tuple(doc.concepts)))
        print(
            f"  [{i}/{len(chunks)}] {time.perf_counter() - t0:6.1f}s | {len(doc.passages):2} passages | {sec_title[:44]!r}",
            flush=True,
        )
    _finalize_toc(tmp, toc)
    os.replace(tmp, out)  # atomic swap: the complete fiche appears all at once
    print(f"\nFiche written: {out}", flush=True)
    return out


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if not args:
        print('Usage: make distill BOOK="<path.md>" [CHUNKS=N]')
        return 1
    force = (
        "--force" in args
    )  # FORCE=1: override the gate (to recover a false positive, M3 audit)
    positional = [a for a in args if a != "--force"]
    path = Path(positional[0])
    max_chunks = int(positional[1]) if len(positional) > 1 else None
    from mnemosyne.production.model_catalog import ENV_TEXT_MODEL, ModelRefused, resolve_model_id

    try:
        model_id = resolve_model_id(os.environ.get(ENV_TEXT_MODEL, "").strip() or _MODEL)
    except ModelRefused as refused:
        print(refused, file=sys.stderr)
        return 2
    api = _make_api(_local_backend(model_id))  # LOCAL; the frontier campaign injects Haiku instead
    distill_one(path, api=api, model_id=model_id, max_chunks=max_chunks, force=force)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
