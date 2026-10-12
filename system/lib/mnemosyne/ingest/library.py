"""Resumable library ingestion (D140 / Stage 3) — walk the shelf, ingest each book, NEVER break.

The scale-up driver for the operator's reference library: the ~240 sources triaged onto the hierarchical
shelf (:mod:`.triage` → ``knowledge/raw/<Famille>/<Groupe>/<domain>/<type>/``) are turned into searchable
memory, one book at a time, under three guarantees that make an ~11 h unattended run safe to leave alone:

* **``.md``-first (D140).** A binary source (PDF / EPUB …) is converted to markdown ONCE, cached as a
  sibling ``<stem>.md``, and that markdown becomes THE source of record — re-runs read the cached
  ``.md``, never re-convert (Docling is the run's whole cost, ~170 s/book). The cached ``.md`` is also
  the Obsidian-openable mirror (``knowledge/raw`` IS the vault) that the operator reads and CORRECTS at
  will; an edited ``.md`` is authoritative and is never clobbered by a reconversion (the enrichment
  vision). The binary original stays in place as the archive (non-destructive, D85).
* **Unbreakable, per-book isolation (D140).** NO single document — long, huge, empty, scanned, or one
  that poisons its own vectors — can abort the run. Each book is processed under its own net: a raising
  reader, a raising capture, an unreadable file, even a corrupt manifest degrade to a RECORDED failure
  and the loop moves on. This complements the core's non-indexable-vector guard (``0dce267``): that
  stops a degenerate page from reaching Qdrant; this stops anything else from stopping the batch.
* **Resumable (D140).** A stable per-book manifest (atomic write after EVERY book) lets a crashed or
  interrupted run pick up exactly where it stopped — already-ingested books are skipped, scanned books
  wait for a later OCR pass, failures are retried.

**Domain tagging + the cloisonnement it triggers (D72 / invariant 4).** Each book is captured tagged
with its shelf domain (``quant-trading`` / ``computer-science`` / ``machine-learning`` — the folder above
the ``<type>``, not the family), so a per-domain recall floor (D139) and the domain frontier both key on a
FACT of the datum. That tag is a Guard frontier: a tagged datum is readable ONLY by a bubble that DECLARES
the domain (policy zone). The whole library lives in ONE shared bubble — :data:`KNOWLEDGE_BUBBLE` — which
declares exactly those domains, so the KB is fully searchable from within itself while a project that later
CONSUMES it still needs an explicit cross-bubble + domain grant (the discipline of D137's asymmetry).
Tagging and declaring move in lockstep: shelve a book under ``knowledge/raw/Finance/Trading/quant-trading/
books/`` WITHOUT ``knowledge = ["quant-trading", …]`` in ``policy.toml`` and every book is silently
withheld from recall — so this module and that policy line are one change.

**Searchable-first (D140).** A capture defaults to matière-de-travail (D137, fail-closed): the 240 books
are RETRIEVABLE but never citable as a source of truth until the operator endorses one — they have not
read them, so they are search fodder, promoted to authority only by the human gesture
(:meth:`endorse_document`).

Brick-free and headless (D126 / [[ui-backlog]]): the driver depends on the :class:`SourceReader` PORT
(the real Docling injected at ignition, a stub in the suite) and a duck-typed capture surface, so the
whole pipeline is unit-testable with nothing installed. Code & docstrings English (D117); the shelf /
domain / governance tokens stay French where they are governance vocabulary (D33 / D66).

Decisions: D140 (living KB, .md-first, unbreakable) · D137 (role, searchable-first) · D72 / inv. 4
(domain cloisonnement) · D139 (per-domain floor) · D85 (raw preserved, scanned→re-extractable) · D126
(brick-free) · D136 / ``0dce267`` (the core's non-indexable-vector guard this leans on).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Final

from . import taxonomy
from ..ports import Bubble, DocId, Domain, Source, SourceReader

if (
    TYPE_CHECKING
):  # annotation-only — never imported at runtime, so ingest never depends on api (no cycle)
    from ..api.core_api import CoreApi
    from ..ports.keywordindex import KeywordIndex
    from ..ports.vectorindex import VectorIndex

#: The one shared bubble that holds the reference library (D137 asymmetry: a source of truth is
#: cross-project, so it lives in its own bubble, not nested in a project). It must DECLARE its shelf
#: domains in the policy zone or every tagged book is withheld from recall (D72 / invariant 4).
KNOWLEDGE_BUBBLE: Final = Bubble("knowledge")

#: Shelf domain assigned to a source that sits directly under the raw root with no domain folder — rare
#: (the triage always shelves by domain), fail-safe so an unshelved stray still gets a declarable tag.
_UNSHELVED: Final = Domain("unshelved")

#: Binary / structured sources that must be CONVERTED to markdown (via the SourceReader) before capture.
_CONVERT_EXTS: Final = frozenset(
    {".pdf", ".epub", ".mobi", ".azw", ".azw3", ".djvu", ".fb2", ".html", ".htm", ".docx", ".pptx"}
)
#: Sources that are ALREADY markdown/text — used as-is (an edited ``.md`` is authoritative, .md-first).
_TEXT_EXTS: Final = frozenset({".md", ".markdown", ".txt", ".rst", ".org"})

#: Best-effort MIME per extension — a HINT for the reader's dispatch, never a barrier (D100-3); Docling
#: keys on the source ``ref`` extension anyway, so an unknown type falls to a harmless default.
_MIME_BY_EXT: Final[dict[str, str]] = {
    ".pdf": "application/pdf",
    ".epub": "application/epub+zip",
    ".mobi": "application/x-mobipocket-ebook",
    ".azw": "application/vnd.amazon.ebook",
    ".azw3": "application/vnd.amazon.ebook",
    ".djvu": "image/vnd.djvu",
    ".fb2": "application/x-fictionbook+xml",
    ".html": "text/html",
    ".htm": "text/html",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".md": "text/markdown",
    ".markdown": "text/markdown",
    ".txt": "text/plain",
    ".rst": "text/x-rst",
    ".org": "text/plain",
}

#: Below this many NON-whitespace characters, a CONVERTED source is treated as scanned/image-only —
#: little or no text layer under ``ocr=False`` (D85). It is flagged ``needs_ocr`` and NOT indexed (an
#: empty doc pollutes nothing), re-extractable later with an OCR reader — never a silent bad read (F3).
_MIN_MARKDOWN_CHARS: Final = 200


def _mime_for(path: Path) -> str:
    """A best-effort MIME hint for a source path (routing hint only, D100-3)."""
    return _MIME_BY_EXT.get(path.suffix.lower(), "application/octet-stream")


def _non_whitespace(text: str) -> int:
    """Count of non-whitespace characters — a primitive. The fidelity signal is
    :func:`_markdown_fidelity`, which first discounts Docling's image placeholders."""
    return sum(1 for c in text if not c.isspace())


#: Docling emits HTML-comment placeholders — ``<!-- image -->`` for a figure with no text layer — that
#: are non-whitespace yet carry NO content. A scanned / image-only page is almost ALL such placeholders,
#: so counting them lets it inflate past ``_MIN_MARKDOWN_CHARS`` and slip the needs_ocr gate — ingested
#: EMPTY with noise vectors (the 2026-07-09 corpus bug). Strip them before measuring the fidelity signal.
_HTML_COMMENT: Final = re.compile(r"<!--.*?-->", re.DOTALL)


def _markdown_fidelity(text: str) -> int:
    """Non-whitespace count of the REAL extracted text — Docling's ``<!-- image -->`` (and any other
    HTML-comment) placeholders removed first (F3). The signal a converted source must clear to be kept
    and indexed rather than flagged ``needs_ocr``: :func:`_non_whitespace` alone counts those markers,
    letting an image-only scan masquerade as text and be ingested empty."""
    return _non_whitespace(_HTML_COMMENT.sub("", text))


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class BookStatus(Enum):
    """What became of one book on the shelf (Stage 3 / D140) — the manifest's per-book verdict."""

    DONE = "done"  # extracted, captured, indexed (or legitimately empty) — skip on resume
    NEEDS_OCR = "needs_ocr"  # converted but (near-)empty ⇒ scanned; awaits an OCR pass, not indexed
    ERROR = (
        "error"  # an ISOLATED failure (reader/capture/io) — recorded, the run continued, retried
    )
    UNDECLARED = (
        "undeclared"  # shelf domain not declarable for the bubble ⇒ NOT captured (would be a
    )
    #                            silently-withheld black hole); surfaced for the human to shelf/declare


def _content_doc(text: str) -> DocId:
    """Content identity (D-CI): ``blake2b`` of the extracted markdown TEXT — NOT the path. Stable across
    a shelf MOVE / rename (content unchanged) ⇒ a reclass is a retag, never a re-embed; a genuine content
    EDIT yields a new id (its vectors are legitimately stale, so re-embed is CORRECT); two byte-identical
    sources collapse to one doc (idempotent, D56). No RNG, no security use."""
    digest = hashlib.blake2b(text.encode("utf-8"), digest_size=8).hexdigest()
    return DocId(f"library/{digest}")


@dataclass(frozen=True, slots=True)
class BookRef:
    """One resolved shelf source: the file to read + its canonical markdown mirror + shelf domain.

    ``source`` is the file actually read (a binary to convert, OR an authoritative ``.md`` used as-is);
    ``mirror`` is the canonical markdown path (Obsidian-openable; equal to ``source`` when the source is
    already text). ``rel`` — the MIRROR relative to the raw root — is the display / provenance path;
    IDENTITY is the CONTENT of the mirror (:meth:`content_doc`), so a book keeps ONE doc across a shelf
    MOVE and the pdf→md transition (same content), while a genuine content edit yields a new doc
    (idempotent BY CONTENT, D56 / D-CI) — decoupling identity from PATH so a reclass never re-embeds."""

    source: Path
    mirror: Path
    domain: Domain
    rel: Path

    @property
    def needs_conversion(self) -> bool:
        """Whether ``source`` is a binary that must pass through the reader (else it IS the markdown)."""
        return self.source != self.mirror

    def identity(self) -> DocId:
        """This book's identity. CONTENT-based (``_content_doc`` of the markdown mirror) once the mirror
        exists — the source of record — so a shelf MOVE keeps ONE id (a reclass is a retag, never a
        re-embed, D-CI). Before that (a binary not yet converted, or a scanned book with no cached
        markdown) it is a PATH-based provisional id, so a not-yet-readable book stays skip-stable across
        runs by its path; it becomes content-based the moment its markdown is cached."""
        try:
            if self.mirror.exists():
                return _content_doc(self.mirror.read_text(encoding="utf-8"))
        except (
            OSError,
            ValueError,
        ):  # unreadable / non-utf8 mirror ⇒ fall back to a PATH id, NEVER abort the
            pass  # run (audit F2); ingest_book's own read then records the real ERROR verdict
        digest = hashlib.blake2b(str(self.rel).encode("utf-8"), digest_size=8).hexdigest()
        return DocId(f"library/{digest}")


def is_non_corpus(rel: Path) -> bool:
    """Whether a shelf-relative path is NOT rangeable corpus and must be skipped by discovery (and by
    the juge, which reuses this same rule): any ``README*`` file (domain / shelf / repo documentation —
    would otherwise be taken for a book; matched case-insensitively on the ``readme`` prefix, so
    ``readme.md``, ``Readme.md`` and a bundled repo's ``README_DIS.md`` are all caught), anything inside
    the ``_intake`` sas (raw arrivals not yet shelved by domain), or a pilot eyeball artifact
    (``*.vision.md`` from sujet 2, ``*.youtube.md`` from sujet 3 — local diagnostics, never a book).
    Everything else under the raw root is a candidate book."""
    return (
        rel.name.lower().startswith("readme")
        or "_intake" in rel.parts
        or rel.name.lower().endswith((".vision.md", ".youtube.md"))
    )


def discover_books(
    raw_root: Path | str,
    *,
    convert_exts: frozenset[str] = _CONVERT_EXTS,
    text_exts: frozenset[str] = _TEXT_EXTS,
) -> list[BookRef]:
    """Walk ``raw_root`` and resolve every shelf source to ONE :class:`BookRef`, deduped by its markdown.

    Sources are grouped by their canonical markdown path (a text file IS its own markdown; a binary maps
    to a sibling ``<stem>.md``). Per group, the ``.md``-first rule picks the source: an EXISTING text
    file wins (the operator may have edited it — authoritative, never reconverted), else the
    (deterministically first, sorted) binary is converted into that markdown. So a generated ``.md``
    mirror is never mistaken for a second book, two FORMATS of one title collapse to one, and the domain
    is derived from the shelf path (:func:`taxonomy.domain_from_parts` — the folder just above the
    ``<type>`` segment, robust to family/group depth) — all pure and deterministic (no file is touched
    here). README files and the ``_intake`` sas are skipped (:func:`is_non_corpus`), so shelf
    documentation is never taken for a book. Caveat: two GENUINELY DIFFERENT sources that happen to
    share a dir+stem (e.g. ``a.pdf`` and an unrelated ``a.epub``) also collapse — the sorted-first wins,
    the sibling is folded — but this is vanishingly rare on a content-deduped shelf (:mod:`.triage`
    already dropped byte-duplicates). Order is stable (sorted) for a reproducible manifest."""
    root = Path(raw_root)
    all_exts = convert_exts | text_exts
    files = sorted(
        p
        for p in root.rglob("*")
        if p.is_file() and p.suffix.lower() in all_exts and not is_non_corpus(p.relative_to(root))
    )
    by_mirror: dict[Path, list[Path]] = {}
    for p in files:
        mirror = p if p.suffix.lower() in text_exts else p.with_suffix(".md")
        by_mirror.setdefault(mirror, []).append(p)
    books: list[BookRef] = []
    for mirror, group in sorted(by_mirror.items()):
        text_here = [p for p in group if p.suffix.lower() in text_exts]
        source = text_here[0] if text_here else group[0]
        rel = mirror.relative_to(root)
        derived = taxonomy.domain_from_parts(rel.parts)  # dir above <type>, any family/group depth
        domain = Domain(derived) if derived is not None else _UNSHELVED
        books.append(BookRef(source=source, mirror=mirror, domain=domain, rel=rel))
    return books


def _extract_markdown(reader: SourceReader, book: BookRef, *, min_chars: int) -> str:
    """Return ``book``'s markdown — from the authoritative text source or a fresh, cached conversion.

    A source that is ALREADY markdown/text is read directly — and this is ALSO the ``.md``-first
    cache-hit: once a binary is converted, :func:`discover_books` picks the written ``.md`` as the source
    on the next run, so a re-run never re-Doclings (no separate cache-reuse branch is needed here). A
    binary is converted ONCE and cached as its mirror, but ONLY when the conversion CLEARS the fidelity
    bar (``min_chars`` non-whitespace, the exact ``needs_ocr`` threshold): a scanned/thin result is
    returned (flagged ``needs_ocr`` upstream, D85) and NOT written, so its mirror can never SHADOW the
    binary at the next discovery and silently promote a sliver to DONE — defeating the OCR retry.
    Leaving no mirror keeps the binary the sole source, so a retry truly re-extracts. Runs LOCAL on
    untrusted bytes (D100-3); a raising reader propagates to the per-book net in :func:`ingest_book`."""
    if not book.needs_conversion:
        return book.mirror.read_text(encoding="utf-8")
    source = Source(
        ref=book.source.name, data=book.source.read_bytes(), mime=_mime_for(book.source)
    )
    text = reader.read(source)
    if not isinstance(
        text, str
    ):  # a reader breaking the port contract is a failed extraction, not a crash
        raise TypeError(
            f"reader returned {type(text).__name__}, expected str (SourceReader contract)"
        )
    if (
        _markdown_fidelity(text) >= min_chars
    ):  # cache ONLY a conversion good enough to keep (see above)
        book.mirror.parent.mkdir(parents=True, exist_ok=True)
        book.mirror.write_text(text, encoding="utf-8")
    return text


@dataclass(frozen=True, slots=True)
class BookRecord:
    """One book's manifest entry — its verdict + provenance, enough to resume and to audit (F3)."""

    rel: str  # the mirror path relative to the raw root (provenance / display — NOT the manifest key)
    domain: str
    doc: str  # the manifest KEY = content identity (D-CI)
    status: BookStatus
    chars: int  # non-whitespace chars of the extracted markdown — the honest fidelity signal
    at: str  # ISO-8601 UTC timestamp of this verdict
    error: str = ""  # the isolated failure message when status is ERROR (empty otherwise)

    def as_json(self) -> dict[str, object]:
        return {
            "rel": self.rel,
            "domain": self.domain,
            "status": self.status.value,
            "chars": self.chars,
            "at": self.at,
            "error": self.error,
        }


@dataclass
class LibraryManifest:
    """The resumable, crash-safe record of what has been ingested (D140).

    Keyed by each book's stable CONTENT id (``doc``, D-CI). Persisted as JSON with an ATOMIC write (temp + ``replace``)
    after every book, so an interrupted ~11 h run never corrupts the manifest and always resumes from
    the last committed book. Load is fail-open toward safety: a corrupt or unreadable manifest, or a
    malformed row, degrades to starting fresh / skipping the row rather than crashing the run."""

    path: Path
    records: dict[str, BookRecord] = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path | str) -> LibraryManifest:
        """Load the manifest, or an empty one if absent/corrupt (unbreakable resume)."""
        path = Path(path)
        if not path.exists():
            return cls(path=path, records={})
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeDecodeError):
            return cls(
                path=path, records={}
            )  # a corrupt manifest never blocks the run — start fresh
        records: dict[str, BookRecord] = {}
        for key, row in (raw.get("records", {}) if isinstance(raw, dict) else {}).items():
            try:
                records[str(key)] = BookRecord(
                    rel=str(row.get("rel", "")),
                    domain=str(row["domain"]),
                    doc=str(key),
                    status=BookStatus(row["status"]),
                    chars=int(row.get("chars", 0)),
                    at=str(row.get("at", "")),
                    error=str(row.get("error", "")),
                )
            except (KeyError, ValueError, TypeError):
                continue  # a malformed row is skipped, never a crash (the book is simply re-processed)
        return cls(path=path, records=records)

    def save(self) -> None:
        """Persist atomically (temp file + ``os.replace``) — a crash mid-write leaves the old file intact.
        The temp name is per-process (pid) so two runs never race the same temp before the replace."""
        payload = {
            "version": 1,
            "records": {k: self.records[k].as_json() for k in sorted(self.records)},
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_name(f"{self.path.name}.{os.getpid()}.tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.path)

    def record(self, rec: BookRecord) -> bool:
        """Commit one book's verdict and flush; return whether the flush SUCCEEDED.

        The in-memory record is always kept. A transient write failure (full disk, a locked file)
        degrades to ``False`` rather than raising, so the unattended ~11 h batch SURVIVES it — that book
        is simply re-processed on the next resume (idempotent, D56), the run does not die. Honours the
        'never corrupt' guarantee via the atomic :meth:`save` (a failed write leaves the old file intact)."""
        self.records[rec.doc] = rec
        try:
            self.save()
        except OSError:
            return False
        return True


def ingest_book(
    api: CoreApi,
    reader: SourceReader,
    book: BookRef,
    *,
    bubble: Bubble,
    min_chars: int,
    now: str,
    declared_domains: frozenset[Domain] | None = None,
) -> BookRecord:
    """Ingest ONE book, staged and netted (D140) — the unit that can fail without touching the batch.

    Staged verdicts, each RECORDED instead of raising: an un-declarable shelf domain ⇒ ``UNDECLARED``
    (checked FIRST, before any conversion); then conversion (a raising reader / unreadable file ⇒
    ``ERROR``); then a fidelity check (a converted source with too little text ⇒ ``NEEDS_OCR``, not
    indexed — D85); then capture into ``bubble`` TAGGED with the shelf domain (a raising capture ⇒
    ``ERROR``). The domain tag makes the datum readable only by a bubble that declares it (D72); the
    sensitivity floor keeps the whole library in one partition (searchable coherently), and a stable doc
    id makes a re-ingest idempotent (D56). Never raises for an ordinary content failure."""
    rel, domain = str(book.rel), str(book.domain)
    doc = str(
        book.identity()
    )  # path-based provisional until the markdown is cached, then content-based
    # A book whose shelf domain is not declarable for ``bubble`` would be captured yet SILENTLY withheld
    # from every recall (fail-closed domain frontier, D72) and, being DONE, never retried — a black hole.
    # Refuse it up front with a VISIBLE verdict: an unshelved stray (no domain folder) always, and any
    # domain the caller's policy does not declare when that set is supplied (tag/declare lockstep).
    if book.domain == _UNSHELVED or (
        declared_domains is not None and book.domain not in declared_domains
    ):
        shelf = taxonomy.shelf_rel(
            domain
        )  # the concrete hierarchical shelf when the domain is mapped
        where = (
            f"knowledge/raw/{shelf}/"
            if shelf is not None
            else "knowledge/raw/<Family>/<Group>/<domain>/<type>/ (see system/config/taxonomy.toml)"
        )
        return BookRecord(
            rel,
            domain,
            doc,
            BookStatus.UNDECLARED,
            0,
            now,
            f"shelf domain not declarable for the target bubble — file it under {where} "
            "or declare the domain in policy.toml [domains] (D72)",
        )
    try:
        text = _extract_markdown(reader, book, min_chars=min_chars)
    except Exception as exc:  # noqa: BLE001 - a raising reader / IO failure is isolated per book (D140)
        return BookRecord(rel, domain, doc, BookStatus.ERROR, 0, now, f"convert: {exc!r}")
    chars = _markdown_fidelity(text)
    # A converted source that tokenised to (almost) nothing is scanned/image-only ⇒ flag, don't index
    # (D85); an empty text source likewise waits for content. Real text of any length proceeds.
    if chars == 0 or (book.needs_conversion and chars < min_chars):
        return BookRecord(
            rel, domain, doc, BookStatus.NEEDS_OCR, chars, now
        )  # no cached md ⇒ keep path id
    doc = str(
        _content_doc(text)
    )  # DONE: the markdown is now the source of record ⇒ CONTENT identity (D-CI)
    try:
        api.capture(
            text=text,
            bubble=bubble,
            doc=DocId(doc),
            # A published book is PUBLIC by provenance (D107 / D144) — EXCEPT on the operator's intimate
            # shelf. D152 already made the distilled fiche of such a book `sensible` on their explicit
            # choice; indexing its source (or that very fiche) as `public` would contradict the
            # decision through the other door. FAMILY-aware, reading the SAME single home the
            # distiller reads (`taxonomy.PERSONAL_FAMILIES`), so the two can never drift apart.
            public_provenance=rel.split("/", 1)[0] not in taxonomy.PERSONAL_FAMILIES,
            domains=frozenset({book.domain}),
        )
    except Exception as exc:  # noqa: BLE001 - a raising capture is isolated per book, never aborts the run
        return BookRecord(rel, domain, doc, BookStatus.ERROR, chars, now, f"capture: {exc!r}")
    return BookRecord(rel, domain, doc, BookStatus.DONE, chars, now)


@dataclass(frozen=True, slots=True)
class IngestReport:
    """The outcome of an :func:`ingest_library` pass — what was touched, skipped, and how it broke down."""

    touched: tuple[BookRecord, ...]  # the books processed THIS run (skipped ones excluded)
    total: int  # books discovered on the shelf
    skipped: int  # books already settled in the manifest (not re-processed this run)
    manifest_write_failures: int = (
        0  # books whose verdict could not be flushed (run survived, resume degraded)
    )

    def count(self, status: BookStatus) -> int:
        return sum(1 for r in self.touched if r.status is status)

    def summary(self) -> str:
        done, ocr, err, undeclared = (
            self.count(BookStatus.DONE),
            self.count(BookStatus.NEEDS_OCR),
            self.count(BookStatus.ERROR),
            self.count(BookStatus.UNDECLARED),
        )
        lines = [
            f"Library ingest: {self.total} on shelf — {len(self.touched)} processed, {self.skipped} skipped",
            f"  DONE       : {done:>5}",
            f"  NEEDS_OCR  : {ocr:>5}  (scanned/empty — re-run with an OCR reader)",
            f"  UNDECLARED : {undeclared:>5}  (no declared shelf domain — shelf/declare then retry)",
            f"  ERROR      : {err:>5}  (isolated failures — see the manifest, retried next run)",
        ]
        if err:
            sample = next((r for r in self.touched if r.status is BookStatus.ERROR), None)
            if sample is not None:
                lines.append(f"    e.g. {sample.rel}: {sample.error}")
        if self.manifest_write_failures:
            lines.append(
                f"  \U000026A0 {self.manifest_write_failures} manifest write(s) failed — run survived, "
                "those books will be re-processed on resume"
            )
        return "\n".join(lines)


def ingest_library(
    api: CoreApi,
    reader: SourceReader,
    raw_root: Path | str,
    manifest_path: Path | str,
    *,
    bubble: Bubble = KNOWLEDGE_BUBBLE,
    declared_domains: frozenset[Domain] | None = None,
    min_chars: int = _MIN_MARKDOWN_CHARS,
    limit: int | None = None,
    retry_ocr: bool = False,
    clock: Callable[[], datetime] = _utcnow,
    on_book: Callable[[BookRecord], None] | None = None,
) -> IngestReport:
    """Ingest the whole shelf under ``raw_root``, resumably and unbreakably (D140) — the scale-up run.

    Discovers every book (:func:`discover_books`), skips those already settled in the manifest (``DONE``
    always; ``NEEDS_OCR`` unless ``retry_ocr``; ``ERROR`` / ``UNDECLARED`` are always retried), and
    ingests the rest ONE at a time, committing each verdict to the manifest before the next (crash-safe
    resume; a manifest write that fails degrades to a re-process on resume, it does not abort the run).
    ``limit`` caps NEW work for a small real batch before the full run; ``on_book`` is an optional
    progress hook. An unexpected raise from :func:`ingest_book` itself is caught here too (belt-and-braces
    isolation), so NO book — and no bug in handling one — can abort the batch. Captures into
    :data:`KNOWLEDGE_BUBBLE` as PUBLIC by provenance (``public_provenance=True`` — a published book is a
    public source, D107; the standing human declassification), so the shelf lands in one coherent PUBLIC
    partition instead of tripping the PII floor's false positives. Pass ``declared_domains`` (the target
    bubble's ``policy.toml`` declaration) to REFUSE — visibly, as
    ``UNDECLARED`` — any book whose domain the policy does not declare, rather than capture a book that
    would then be silently withheld from recall (tag/declare lockstep, D72); an unshelved stray is always
    refused this way even without it."""
    manifest = LibraryManifest.load(manifest_path)
    books = discover_books(raw_root)
    skip_states = {BookStatus.DONE} if retry_ocr else {BookStatus.DONE, BookStatus.NEEDS_OCR}
    rel_index = {
        r.rel: d for d, r in manifest.records.items() if r.rel
    }  # shelf path -> its recorded content id
    touched: list[BookRecord] = []
    skipped = 0
    write_failures = 0
    for book in books:
        doc = (
            book.identity()
        )  # content id (mirror exists) or a path-based provisional (not yet converted)
        existing = manifest.records.get(str(doc))
        if existing is not None and existing.status in skip_states:
            skipped += 1
            continue
        if limit is not None and len(touched) >= limit:
            break
        now = clock().isoformat()
        try:
            rec = ingest_book(
                api,
                reader,
                book,
                bubble=bubble,
                min_chars=min_chars,
                now=now,
                declared_domains=declared_domains,
            )
        except Exception as exc:  # noqa: BLE001 - unbreakable: even an unexpected raise is isolated per book
            rec = BookRecord(
                str(book.rel),
                str(book.domain),
                str(doc),  # `doc` (identity), not the removed `book.doc` (audit F1)
                BookStatus.ERROR,
                0,
                now,
                f"unexpected: {exc!r}",
            )
        prior = rel_index.get(rec.rel)
        if prior is not None and prior != rec.doc and rec.status is BookStatus.DONE:
            # same shelf path, a DIFFERENT content id ⇒ the book was EDITED: purge the stale prior version's
            # vectors and its manifest row, else recall would surface BOTH the old and the new (audit F3 / D-CI).
            api.forget(DocId(prior))
            manifest.records.pop(prior, None)
        if rec.rel:
            rel_index[rec.rel] = rec.doc
        if not manifest.record(
            rec
        ):  # a failed flush must not abort the batch (resume degrades, run lives)
            write_failures += 1
        touched.append(rec)
        if on_book is not None:
            try:
                on_book(rec)
            except Exception:  # noqa: BLE001 - a misbehaving progress hook never breaks the run
                pass
    return IngestReport(
        touched=tuple(touched),
        total=len(books),
        skipped=skipped,
        manifest_write_failures=write_failures,
    )


def domains_on_shelf(raw_root: Path | str) -> frozenset[Domain]:
    """The set of shelf domains present under ``raw_root`` — the exact ``knowledge = [...]`` a coherent
    policy must declare (D72). A convenience so tagging and declaring can be checked in lockstep."""
    return frozenset(book.domain for book in discover_books(raw_root))


@dataclass(frozen=True, slots=True)
class RealignReport:
    """What a manifest path re-alignment touched (G5). Non-destructive: only display ``rel`` fields move."""

    realigned: int  # records whose rel was moved to the current shelf path (matched by content id)
    already_ok: int  # records whose rel already matched the current path (idempotent no-op)
    unmatched: (
        int  # records whose content id is no longer on the shelf (edited/removed — left untouched)
    )
    wrote: bool  # whether the manifest was actually rewritten (False on dry-run or nothing to move)

    def summary(self) -> str:
        verb = (
            "re-aligned" if self.wrote else "would re-align" if self.realigned else "nothing to do"
        )
        return (
            f"Manifest path re-alignment ({verb}): {self.realigned} moved, "
            f"{self.already_ok} already ok, {self.unmatched} unmatched (content id off-shelf)"
        )


def realign_manifest_paths(
    manifest_path: Path | str,
    raw_root: Path | str,
    *,
    dry_run: bool = False,
    backup: bool = True,
) -> RealignReport:
    """Move each manifest row's display ``rel`` onto the book's CURRENT shelf path, matched by content id (G5).

    Why (post-reorg): the manifest is keyed by CONTENT id (D-CI), so a moved-but-unchanged book still skips
    correctly on re-index — but its recorded ``rel`` is the OLD path. The edit-detection in
    :func:`ingest_library` purges a book's stale vectors via a ``rel``-keyed index (``rel_index``), so if a
    later pass EDITS a book (e.g. figure enrichment splices its ``.md`` → a NEW content id), the purge looks
    up the NEW path, misses the OLD-path row, and leaves the prior vectors → a DUPLICATE in recall. Re-aligning
    the rows to the current paths FIRST closes that: the next edit's purge finds the prior version and forgets
    it. NON-DESTRUCTIVE (invariant 2): only ``rel`` moves — content ids, statuses and vectors are untouched;
    a content id no longer on the shelf (a re-distilled / removed book) is LEFT for the run itself to purge.
    Idempotent (a second call moves nothing). Backs the manifest up once before writing (reconstructible, D44,
    but cheap insurance). ``dry_run`` measures without writing (the diagnostic)."""
    manifest = LibraryManifest.load(manifest_path)
    # content id -> current shelf path, for books whose .md mirror exists right now
    current: dict[str, str] = {}
    for book in discover_books(raw_root):
        if not book.mirror.exists():
            continue
        try:
            current[str(book.identity())] = str(book.rel)
        except OSError:
            continue  # an unreadable mirror is skipped, never a crash (D85)
    moves: list[tuple[str, str]] = []
    already_ok = 0
    for doc, rec in manifest.records.items():
        cur = current.get(doc)
        if cur is None:
            continue  # content id off-shelf (edited/removed) — not ours to move; the run purges it
        if cur == rec.rel:
            already_ok += 1
        else:
            moves.append((doc, cur))
    unmatched = len(manifest.records) - len(moves) - already_ok
    wrote = False
    if moves and not dry_run:
        if backup:
            _backup_manifest(Path(manifest_path))
        for doc, cur in moves:
            manifest.records[doc] = replace(manifest.records[doc], rel=cur)
        manifest.save()
        wrote = True
    return RealignReport(
        realigned=len(moves), already_ok=already_ok, unmatched=unmatched, wrote=wrote
    )


def _backup_manifest(manifest_path: Path, *, tag: str = "realign") -> None:
    """Copy the manifest beside itself once before a mutating pass, timestamped (non-destructive
    insurance, D44). ``tag`` names the pass (``realign`` / ``orphan-purge``) in the backup filename."""
    if not manifest_path.exists():
        return
    stamp = _utcnow().strftime("%Y%m%dT%H%M%SZ")
    backup = manifest_path.with_name(
        f"{manifest_path.stem}.pre-{tag}.{stamp}{manifest_path.suffix}"
    )
    backup.write_text(manifest_path.read_text(encoding="utf-8"), encoding="utf-8")


def _live_shelf(raw_root: Path | str) -> tuple[set[str], set[str]]:
    """The live shelf as two membership sets — content ids AND display paths of books whose ``.md``
    mirror EXISTS right now. The path set is the key guard for a book PRESENT-BUT-UNREADABLE (a non-utf8
    re-save): its ``identity()`` falls back to a path id, so the content-id set alone would miss it, but
    its ``rel`` still resolves to a live file — the orphan check spares anything matching EITHER set, so
    a live-but-unreadable source is never mistaken for off-shelf (the delete-path safety, D56 / inv. 2)."""
    ids: set[str] = set()
    rels: set[str] = set()
    for book in discover_books(raw_root):
        if book.mirror.exists():
            ids.add(str(book.identity()))
            rels.add(str(book.rel))
    return ids, rels


@dataclass(frozen=True, slots=True)
class OrphanRow:
    """One orphaned document: a manifest ``DONE`` id whose content has left the shelf, still indexed."""

    doc: str  # the content id = manifest key = the vector doc id
    rel: str  # its last-known display path (provenance, for a human-readable report)
    domain: str


@dataclass(frozen=True, slots=True)
class OrphanReport:
    """Vectors whose source content is gone from the current shelf — a derivative-integrity check (D44).

    Producing it touches NOTHING (read-only). ``orphans`` are CONFIRMED (manifest ``DONE``, absent from
    the live shelf by content id AND by file path, AND present in the vector index); ``checked`` counts
    the off-shelf candidates probed against the index (a candidate never indexed is not reported)."""

    orphans: tuple[OrphanRow, ...]
    checked: int

    def summary(self) -> str:
        return (
            f"Orphan vectors: {len(self.orphans)} confirmed (indexed but off-shelf) of "
            f"{self.checked} off-shelf DONE candidate(s) probed"
        )


def detect_orphan_vectors(
    manifest_path: Path | str, raw_root: Path | str, *, vector: VectorIndex
) -> OrphanReport:
    """Find ``DONE`` documents whose content has left the shelf yet still hold vectors (D44 / audit F3).

    READ-ONLY. Identity is CONTENT-based (D-CI), so a mere shelf MOVE keeps the same id and is NOT an
    orphan; a real orphan is a manifest ``DONE`` id absent from the live shelf ids — a book REMOVED, or
    CONTENT-edited (re-OCR / figure splice) so its OLD id was left behind — whose vectors are STILL in
    the index. Each off-shelf candidate is confirmed via :meth:`~mnemosyne.ports.VectorIndex.contains`
    before it is reported, so an id that was never actually indexed is not a false positive. The purge is
    a separate, explicit step (:func:`purge_orphan_vectors`) — this never mutates anything.

    Why it is NOT redundant with a re-index: ``ingest_library`` only purges a stale id when a CURRENT
    book re-uses the same display ``rel`` (edit detection); a book that simply vanished from the shelf is
    never re-visited, so its vectors linger forever. This is the reconciliation that closes that gap."""
    manifest = LibraryManifest.load(manifest_path)
    live_ids, live_rels = _live_shelf(raw_root)
    rows: list[OrphanRow] = []
    checked = 0
    for doc, rec in manifest.records.items():
        # off-shelf ONLY if BOTH its content id has left the live shelf AND its recorded path no longer
        # resolves to a live file. The path guard spares a book PRESENT-BUT-UNREADABLE (a .md the
        # operator re-saved non-utf8 → its identity() falls back to a path id, absent from the
        # content-id set): a live source's derivatives are never purged (realign keeps the row's rel on
        # the current path).
        if rec.status is not BookStatus.DONE or doc in live_ids or rec.rel in live_rels:
            continue
        checked += 1
        if vector.contains(DocId(doc)):
            rows.append(OrphanRow(doc=doc, rel=rec.rel, domain=rec.domain))
    return OrphanReport(orphans=tuple(rows), checked=checked)


def purge_orphan_vectors(
    report: OrphanReport,
    manifest_path: Path | str,
    raw_root: Path | str,
    *,
    vector: VectorIndex,
    keyword: KeywordIndex,
    backup: bool = True,
) -> int:
    """Drop the CONFIRMED orphans' derivative entries and their manifest rows — governed, explicit (D44).

    NEVER called by :func:`ingest_library`; a human runs it (the ``--purge-orphans`` CLI), like
    ``--realign-only``. For each orphan the report confirmed off-shelf: RE-CHECK it is STILL off the
    live shelf and STILL a manifest row (a source that reappeared, or a row already purged, between the
    report and now, is left alone — belt-and-suspenders on a delete path), then purge its vector +
    keyword entries (the same derivative-only double as :meth:`~mnemosyne.api.core_api.CoreApi.forget` —
    reconstructible from the truth, never a data loss, D56) and drop its manifest row. The manifest is
    backed up once before the write (D44 insurance). Returns the count purged. Idempotent: a re-run over
    the same report finds the rows already gone and does nothing (no second backup, no re-save)."""
    manifest = LibraryManifest.load(manifest_path)
    live_ids, live_rels = _live_shelf(raw_root)
    # spare anything whose content id OR whose recorded path is still live (a reappeared source, or a
    # book present-but-unreadable), and anything already gone from the manifest — never delete a live one.
    to_purge = [
        row
        for row in report.orphans
        if row.doc not in live_ids and row.rel not in live_rels and row.doc in manifest.records
    ]
    if to_purge and backup:
        _backup_manifest(Path(manifest_path), tag="orphan-purge")
    for row in to_purge:
        vector.invalidate(DocId(row.doc))
        keyword.invalidate(DocId(row.doc))
        manifest.records.pop(row.doc, None)
    if to_purge:
        manifest.save()
    return len(to_purge)
