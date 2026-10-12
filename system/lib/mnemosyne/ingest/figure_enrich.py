"""Coordinate deterministic figure enrichment before optional model assistance."""

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from ..ports.figure_enrich import FigureEnrichOutcome, FigureEnrichStats
from ..provenance import (
    FIGURE_CAPTION_MARK,
    FIGURE_CLOUD_MARK,
    FIGURE_DATA_MARK,
    FIGURE_IMAGE_MARK,
)
from .caption import Enrichment, count_image_holes, weave_enrichments
from .figure_image import DirectoryImageSink, DryRunImageSink

if TYPE_CHECKING:
    from ..ports.figure_enrich import FigureEnricher
    from .library import BookRef

#: Default backup extension: the ORIGINAL ``.md`` is copied to ``<name>.md.prefig`` before the first
#: rewrite (non-destructive, D85/D74 - operator can always diff or revert). Not a corpus ext, so
#: :func:`discover_books` never mistakes it for a book, and ``knowledge/raw`` is gitignored anyway.
_BACKUP_SUFFIX = ".prefig"


def enrich_outcome(existing_md: str, enrichments: list[Enrichment | None]) -> FigureEnrichOutcome:
    """Splice ``enrichments`` into ``existing_md``'s holes IF aligned, and tally the result (pure, subject F).

    ``enrichments`` is one entry per BODY figure in document order (what
    :func:`~mnemosyne.ingest.source_docling._enrich_figures` produces), so ``len(enrichments)`` is the
    PDF's BODY-picture count. The ordinal splice (:func:`weave_enrichments`) is only sound when that count
    equals the ``.md``'s hole count - so this is FAIL-CLOSED: on a mismatch nothing is spliced and
    ``aligned=False`` is reported for review (an OCR pass or a miscounted furniture image desynced them; a
    read-out on the wrong figure would corrupt fidelity, invariant 1). When aligned, each filled hole is
    counted by its MARK - :data:`FIGURE_DATA_MARK` = exact vector extraction, :data:`FIGURE_CAPTION_MARK` =
    the local VLM guess, :data:`FIGURE_CLOUD_MARK` = the frontier captioner (level 3) - so the campaign can
    tell operator how far the LOCAL got, how many holes NEEDED the cloud, and how it fell short (F7). Brick-free
    and deterministic (D126)."""
    holes = count_image_holes(existing_md)
    body = len(enrichments)

    def _filled(mark: str) -> int:
        return sum(1 for e in enrichments if e is not None and e[0] == mark and e[1].strip())

    # Counted BEFORE the alignment branch, and that placement IS the fix: the sink already wrote
    # these pixels while the adapter produced the enrichments, so a REFUSED book must still say
    # Deployment-specific measurement omitted; the behavior is covered by tests.
    assets_written = _filled(FIGURE_IMAGE_MARK)

    if holes != body:
        stats = FigureEnrichStats(
            holes=holes,
            body_pictures=body,
            aligned=False,
            remaining_holes=holes,
            assets_written=assets_written,
        )
        return FigureEnrichOutcome(markdown=existing_md, stats=stats, changed=False)

    filled_image = assets_written  # arc D - the figure ITSELF, not a description of it
    filled_vector = _filled(FIGURE_DATA_MARK)
    filled_vlm = _filled(FIGURE_CAPTION_MARK)
    filled_cloud = _filled(
        FIGURE_CLOUD_MARK
    )  # level 3 (subject G) - counted apart from the local paths
    markdown = weave_enrichments(existing_md, enrichments)
    stats = FigureEnrichStats(
        holes=holes,
        body_pictures=body,
        aligned=True,
        filled_vector=filled_vector,
        filled_vlm=filled_vlm,
        filled_cloud=filled_cloud,
        filled_image=filled_image,
        remaining_holes=holes - filled_image - filled_vector - filled_vlm - filled_cloud,
        assets_written=assets_written,
    )
    return FigureEnrichOutcome(markdown=markdown, stats=stats, changed=markdown != existing_md)


@dataclass(frozen=True, slots=True)
class BookEnrichResult:
    """One book's campaign outcome: its shelf path + verdict. ``stats`` is ``None`` iff the book ERRORED."""

    rel: str
    changed: bool
    stats: FigureEnrichStats | None = None
    error: str = ""


@dataclass(frozen=True, slots=True)
class CampaignReport:
    """What an enrichment campaign touched - the aggregate that becomes operator's LOCAL-FIRST diagnostic (F7)."""

    results: tuple[BookEnrichResult, ...]
    skipped_large: int = 0  # books skipped for exceeding max_holes (scan-dominant - not figures)

    def _stats(self) -> tuple[FigureEnrichStats, ...]:
        return tuple(r.stats for r in self.results if r.stats is not None)

    @property
    def books(self) -> int:
        return len(self.results)

    @property
    def changed_books(self) -> int:
        return sum(1 for r in self.results if r.changed)

    @property
    def misaligned_books(self) -> int:
        return sum(1 for s in self._stats() if not s.aligned)

    @property
    def errored_books(self) -> int:
        return sum(1 for r in self.results if r.stats is None)

    @property
    def holes(self) -> int:
        return sum(s.holes for s in self._stats())

    @property
    def filled_image(self) -> int:
        """Holes that got the FIGURE ITSELF (arc D) - the only path that costs no model and invents nothing."""
        return sum(s.filled_image for s in self._stats())

    @property
    def filled_vector(self) -> int:
        return sum(s.filled_vector for s in self._stats())

    @property
    def filled_vlm(self) -> int:
        return sum(s.filled_vlm for s in self._stats())

    @property
    def filled_cloud(self) -> int:
        """Holes that NEEDED the niveau-3 frontier (sujet G) - how much left the machine, for operator to weigh."""
        return sum(s.filled_cloud for s in self._stats())

    @property
    def orphan_assets(self) -> int:
        """Pixels written to disk for books whose splice was REFUSED - files nothing points at.

        WARNING: read this next to ``misaligned_books``: fail-closed means nothing was WOVEN, never that
        nothing HAPPENED. Deleting them is operator's gesture (D74) - this only makes them visible."""
        return sum(s.assets_written for s in self._stats() if not s.aligned)

    @property
    def remaining_holes(self) -> int:
        """Holes the LOCAL left untouched IN ALIGNED books - the hard remainder operator weighs for the frontier.

        Misaligned books are excluded: their holes were not attempted (fail-closed), so counting them as
        'remaining' would slander the local's actual reach. They are surfaced separately."""
        return sum(s.remaining_holes for s in self._stats() if s.aligned)

    def summary(self) -> str:
        aligned_holes = self.holes - sum(s.holes for s in self._stats() if not s.aligned)
        lines = [
            f"Figure enrichment: {self.books} books touched "
            f"({self.changed_books} rewritten, {self.misaligned_books} misaligned, "
            f"{self.errored_books} errored)",
            f"  holes in aligned books : {aligned_holes:>6}",
            f"  filled - IMAGE (the PDF): {self.filled_image:>6}",
            f"  filled - vector (exact): {self.filled_vector:>6}",
            f"  filled - VLM (local)   : {self.filled_vlm:>6}",
            f"  filled - cloud (front.): {self.filled_cloud:>6}",
            f"  left as holes (hard)   : {self.remaining_holes:>6}",
        ]
        if self.orphan_assets:
            lines.append(
                f"  WARNING: images WRITTEN in REFUSED books: {self.orphan_assets} "
                f'- files nothing points at. "Nothing was woven" does not mean '
                f'"nothing happened": the sink writes the pixels BEFORE the alignment '
                f"decides. Deleting them is the operator's gesture (D74)."
            )
        if self.skipped_large:
            lines.append(f"  skipped (scan-heavy)   : {self.skipped_large:>6}")
        # A count is not a census. After a 9-hour run the per-book lines are far up the scrollback, so the
        # summary NAMES every refused book - that named list IS the deliverable of a first pass (which books
        # carry a stale .md), and a count could never be acted on. Never truncated: a silent "and 37 more"
        # would read as coverage it does not have.
        refused = [
            (r.rel, r.stats) for r in self.results if r.stats is not None and not r.stats.aligned
        ]
        if refused:
            lines.append(f"\n  REFUSES par l'alignement ({len(refused)}) - their .md is stale:")
            lines += [
                f"    {holes.holes:>4} trous vs {holes.body_pictures:>4} figures  {rel}"
                for rel, holes in refused
            ]
        errored = [(r.rel, r.error) for r in self.results if r.stats is None]
        if errored:
            lines.append(f"\n  EN ERREUR ({len(errored)}) :")
            lines += [f"    {rel} - {err}" for rel, err in errored]
        if aligned_holes:
            local_pct = (
                100.0 * (self.filled_image + self.filled_vector + self.filled_vlm) / aligned_holes
            )
            lines.append(f"  local fill rate        : {local_pct:>5.1f}%")
            if self.filled_cloud:
                total_pct = (
                    100.0
                    * (self.filled_image + self.filled_vector + self.filled_vlm + self.filled_cloud)
                    / aligned_holes
                )
                lines.append(f"  + frontier fill rate   : {total_pct:>5.1f}%")
        return "\n".join(lines)


def _atomic_write(path: Path, text: str) -> None:
    """Write ``text`` to ``path`` DURABLY: a per-process temp sibling + ``os.replace`` (atomic), so a crash
    or a full disk mid-write leaves the DESTINATION intact - never a truncated file. Mirrors
    :meth:`~mnemosyne.ingest.library.LibraryManifest.save`. Raises ``OSError`` on any failure."""
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def _rewrite_in_place(md_path: Path, original: str, enriched: str, backup_suffix: str) -> None:
    """Back up the ORIGINAL ``.md`` once, then atomically overwrite it with the ENRICHED text - never losing data.

    Non-destructive (invariant 2 / D74/D85) against the ``.md`` that is operator's OCR-polished text of record:
    it is IRREPLACEABLE (Docling cannot regenerate his manual corrections) AND gitignored (no git history to
    recover from), so a partial write would be a permanent loss. Hence: (1) the backup ``<name><suffix>`` is
    written FIRST, atomically, and only if it does not already exist (the very first pre-enrichment version
    wins; later re-runs never clobber it); if that backup write fails we RAISE and do NOT overwrite - the
    original stays intact. (2) The overwrite itself is atomic (temp sibling + ``os.replace``), so a crash /
    ENOSPC mid-write can never truncate the original (the weave is purely additive: ``enriched`` ⊇ every
    author line of ``original``). Any ``OSError`` propagates to the per-book net in
    :func:`enrich_figures_campaign` - that book is recorded errored, the campaign lives."""
    backup = md_path.with_name(md_path.name + backup_suffix)
    if not backup.exists():
        _atomic_write(
            backup, original
        )  # raises on failure => we never reach the overwrite (original safe)
    _atomic_write(md_path, enriched)


def _safe_call(hook: Callable[[BookEnrichResult], None], result: BookEnrichResult) -> None:
    try:
        hook(result)
    except Exception:  # noqa: BLE001 - a misbehaving progress hook never breaks the campaign
        pass


def enrich_figures_campaign(
    enricher: FigureEnricher,
    raw_root: Path | str,
    *,
    select: Callable[[BookRef], bool] | None = None,
    limit: int | None = None,
    max_holes: int | None = None,
    images: bool = False,
    dry_run: bool = False,
    backup_suffix: str = _BACKUP_SUFFIX,
    on_book: Callable[[BookEnrichResult], None] | None = None,
) -> CampaignReport:
    """Walk the shelf and enrich every candidate ``.md``'s figure holes in place (sujet F campaign driver).

    A CANDIDATE is a discovered book (:func:`discover_books`, so README / _intake / pilot artifacts are
    already skipped) whose canonical ``.md`` exists, has a sibling ``.pdf``, and holds at least one
    ``<!-- image -->`` hole. ``select`` further narrows the pool (the CLI uses it to target a pilot lot);
    ``max_holes`` skips a book with MORE holes than that - a scan-dominant book whose every page is one
    ``<!-- image -->`` is not a figure to describe, and running the VLM over hundreds of scanned pages is
    pure waste (counted in :attr:`CampaignReport.skipped_large`); ``limit`` caps how many are processed (a
    fast pilot before the full corpus). For each, the injected :class:`FigureEnricher` re-reads the PDF and
    returns the spliced markdown; when it CHANGED - and this is NOT a ``dry_run`` (the diagnostic pass that
    measures without touching operator's files) - the original is backed up once and the ``.md`` is rewritten
    ATOMICALLY in place (:func:`_rewrite_in_place`, never losing the irreplaceable original). Per-book
    isolation (D140): a raising enricher, an unreadable mirror, or an IO error on write is RECORDED and the
    walk continues - no book aborts the campaign. Returns the aggregate for the diagnostic (F7)."""
    from .library import discover_books  # lazy: keep enrich_outcome importable without the driver

    root = Path(raw_root)
    results: list[BookEnrichResult] = []
    processed = 0
    skipped_large = 0
    for book in discover_books(root):
        md_path = book.mirror
        pdf_path = md_path.with_suffix(".pdf")
        if not (md_path.exists() and pdf_path.exists()):
            continue  # only enrich an EXISTING .md that has a PDF to read figures from
        try:
            md = md_path.read_text(encoding="utf-8")
        except (
            OSError,
            ValueError,
        ) as exc:  # unreadable/non-utf8 mirror - RECORD it so the diagnostic is honest
            result = BookEnrichResult(
                rel=str(book.rel), changed=False, stats=None, error=f"read: {exc!r}"
            )
            results.append(result)
            if on_book is not None:
                _safe_call(on_book, result)
            continue
        holes = count_image_holes(md)
        if holes == 0:
            continue  # nothing to enrich
        if select is not None and not select(book):
            continue  # narrow out BEFORE the scan-heavy tally, so skipped_large counts only the targeted pool
        if max_holes is not None and holes > max_holes:
            skipped_large += 1  # scan-dominant book - not figures; don't spend the VLM on it
            continue
        if limit is not None and processed >= limit:
            break
        processed += 1
        try:
            # arc D: the sink is per-BOOK (assets live beside their own .md), so it is built here and passed
            # per call, never held by the enricher. A dry run gets the DRY sink, not None: it must take the
            # same routing decision the real pass would (else the preview reports the text fallback and
            # slanders the pass it previews) while writing nothing.
            assets = (
                (DryRunImageSink(md_path) if dry_run else DirectoryImageSink(md_path))
                if images
                else None
            )
            outcome = enricher.enrich_markdown(md, pdf_path.read_bytes(), assets=assets)
        except Exception as exc:  # noqa: BLE001 - per-book isolation (D140): never abort the campaign
            result = BookEnrichResult(
                rel=str(book.rel), changed=False, stats=None, error=f"enrich: {exc!r}"
            )
            results.append(result)
            if on_book is not None:
                _safe_call(on_book, result)
            continue
        if outcome.changed and not dry_run:
            try:
                _rewrite_in_place(md_path, md, outcome.markdown, backup_suffix)
            except Exception as exc:  # noqa: BLE001 - per-book isolation: original intact (atomic), campaign lives on
                result = BookEnrichResult(
                    rel=str(book.rel), changed=False, stats=None, error=f"write: {exc!r}"
                )
                results.append(result)
                if on_book is not None:
                    _safe_call(on_book, result)
                continue
        result = BookEnrichResult(rel=str(book.rel), changed=outcome.changed, stats=outcome.stats)
        results.append(result)
        if on_book is not None:
            _safe_call(on_book, result)
    return CampaignReport(results=tuple(results), skipped_large=skipped_large)
