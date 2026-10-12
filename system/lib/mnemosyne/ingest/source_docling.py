"""_DoclingBackend — the SOLE importer of Docling (D43 / D103 / invariant 20).

Docling is the FIRST-CLASS document reader (D43: it beats MinerU / PaddleOCR on M4; ``oss_registry.md``):
PDF / office / html / images → clean markdown, all LOCAL. This is the one module allowed to touch the
brick — it wraps ``docling`` behind :class:`~mnemosyne.ports.source.SourceReader`, so the pipeline speaks
only the port and the suite stays green with Docling NOT installed (D126). Everything BRICK is
``# pragma: no cover``: it runs only at ③ ignition (``uv sync --extra bricks``), where the 1-click smoke
confronts this colle with the real Docling API. A drift is non-catastrophic — the ③-4a benne net (D85)
preserves the raw source and re-extracts, so a broken read degrades to a low-fidelity flag, never a lost datum.

Figure enrichment (two OPT-IN paths that fill Docling's ``<!-- image -->`` holes, D140). Per BODY figure, in
document order, the backend picks ONE:

* **vector extraction (sujet E)** FIRST — fast, exact, LOCAL: if a :class:`VectorFigureReader` is wired
  (``MNEMOSYNE_FIGURES``), read the figure's own primitives and, when it is a vector chart, emit a structured
  read-out marked :data:`~mnemosyne.provenance.FIGURE_DATA_MARK`;
* **vision caption (sujet 2)** as the FALLBACK — a genuinely RASTER figure, or one the extractor could not
  read: if an :class:`ImageCaptioner` is wired (``MNEMOSYNE_VISION``), ask the local VLM and emit a caption
  marked :data:`~mnemosyne.provenance.FIGURE_CAPTION_MARK`.

Both marks are stripped from the verbatim floor (C2/E), so neither an extraction nor a VLM guess is ever
promoted to the author's P3. With BOTH switches off (default) the backend returns Docling's markdown
byte-for-byte — zero regression. The pure figure logic (:mod:`.figure_extract`) is unit-tested; only the
Docling/fitz translation is uncovered, and per-figure fail-open (D85) keeps a hole rather than abort a book.

Decisions: D43 (Docling default) · D103 (sole importer) · D125-B5 (SourceReader) · D126 (import-safe) ·
D100-3 (bytes untrusted, runs local) · D85 (raw preserved on failure) · D140 (.md-first enrichment).
Code & docstrings English (D117).
"""

from __future__ import annotations

from collections.abc import Callable
from io import BytesIO

from ..ports import ImageCaptioner, Source, SourceReader
from ..ports.figure_enrich import FigureEnricher, FigureEnrichOutcome
from ..ports.figure_image import FigureImageSink
from ..ports.vectorfigure import FigurePrimitives, VectorFigureReader
from ..provenance import (
    FIGURE_CAPTION_MARK,
    FIGURE_CLOUD_MARK,
    FIGURE_DATA_MARK,
    FIGURE_IMAGE_MARK,
)
from .caption import Enrichment, count_image_holes, is_degenerate_caption, weave_enrichments
from .figure_enrich import enrich_outcome
from .figure_extract import describe_vector_figure, is_raster_figure
from .figure_image import image_payload

#: Build a document-bound vector reader from PDF bytes (the sole-importer adapter ``connect_pymupdf_reader``).
VectorReaderFactory = Callable[[bytes], VectorFigureReader]


def _pdf_converter(
    *, ocr: bool, force_full_page: bool, want_picture_images: bool
):  # pragma: no cover - needs the brick (③ ignition)
    """Build Docling's PDF converter + its ``DocumentStream`` ctor — the ONE home of the Docling API colle.

    Shared by BOTH PDF seams (:func:`connect_docling`, the plain reader, and
    :func:`connect_docling_figure_enricher`, the in-place figure mode), so the pipeline knobs and the
    ALLUMAGE NOTE below live in ONE place (anti-drift, [[consolidate-crosscutting-rules]]). ``ocr`` /
    ``force_full_page`` are the OCR knobs documented on :func:`connect_docling`; ``want_picture_images``
    keeps each figure's rendered image (a captioner / the VLM needs the pixels), off otherwise so the plain
    run is byte-for-byte unchanged. Returns ``(converter, DocumentStream)`` — the caller wraps the bytes in
    the stream (an in-memory source needs the stream form, not a Path).

    ALLUMAGE NOTE (API confirmed against the installed Docling at ③ dogfood 2026-07-06):
    ``DocumentConverter(format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=
    PdfPipelineOptions(do_ocr=...))})`` ; ``.convert(DocumentStream(name=..., stream=BytesIO(bytes)))``
    returns a ``ConversionResult`` whose ``.document`` exports markdown / holds ``.pictures``."""
    from docling.datamodel.base_models import DocumentStream, InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    from docling.document_converter import DocumentConverter, PdfFormatOption

    pipeline = PdfPipelineOptions(do_ocr=ocr or force_full_page)
    if ocr or force_full_page:
        # macOS-native Vision OCR (ocrmac) for the needs_ocr / ligature-repair pass; pinned so the engine
        # is deterministic. force_full_page re-reads every page visually (past a broken text layer) — prose-only.
        from docling.datamodel.pipeline_options import OcrMacOptions

        pipeline.ocr_options = OcrMacOptions(force_full_page_ocr=force_full_page)
    if want_picture_images:
        pipeline.generate_picture_images = True
        pipeline.images_scale = 2.0
    converter = DocumentConverter(
        format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline)}
    )
    return converter, DocumentStream


def connect_docling(
    *,
    ocr: bool = False,
    force_full_page: bool = False,
    captioner: ImageCaptioner | None = None,
    vector_reader_factory: VectorReaderFactory | None = None,
) -> SourceReader:  # pragma: no cover - needs the brick (③ ignition)
    """Wrap the installed Docling as a :class:`SourceReader` (the ``[OPERATOR]`` allumage seam, D43).

    Imports ``docling`` LAZILY, so this module is import-safe without it (D126); wired by
    :func:`~mnemosyne.runtime.bootstrap.real_runtime` for documents. As with every
    ``pragma: no cover`` adapter, the 1-click smoke confronts this colle with the real API at
    ignition; a drift degrades to a low-fidelity flag (raw preserved, D85), never a lost datum.

    **OCR off by default (③-4b dogfood, D69/D85).** Docling's default PDF pipeline runs FULL-PAGE OCR
    (RapidOCR) on every page — 30-150 s/PDF and pure waste on a text-layer PDF (measured on the operator's
    alpha corpus: a 380 KB paper took 143 s with OCR vs 16.6 s without, same clean text). Personal corpora are
    overwhelmingly text-layer (papers, books, notes), so ``do_ocr=False`` is the right DEFAULT: fast, and
    it uses the embedded text. A genuinely SCANNED (image-only) PDF then yields little text ⇒ the fidelity
    golden flags it low-fidelity and the benne preserves the raw bytes (D85), re-extractable with
    ``connect_docling(ocr=True)`` later — never a lost datum, never a silent bad read (F3). OCR stays a
    one-line opt-in, not the tax on every document.

    **``force_full_page=True`` — the ligature-repair pass (prose-only).** A text-layer PDF whose font
    drops the fi/ff/Th ligatures from its ToUnicode map extracts *silently corrupted* text
    (``profitable`` → ``protable``, ``first`` → ``rst``); ``ocr=True`` alone does NOT fix it — Docling only
    OCRs pages it deems scanned, never one that already holds (wrong) text. ``force_full_page`` re-reads
    EVERY page visually, past the broken glyph map. It repairs the ligatures BUT destroys mathematics
    (Apple Vision OCR wipes Greek/operators and hallucinates terms, measured), so it is ONLY for
    prose-heavy corrupted books, NEVER equation-dense ones. Which book gets it is a campaign-layer
    decision, not this seam's.

    **``captioner`` (sujet 2) and ``vector_reader_factory`` (sujet E) are the two figure-enrichment seams.**
    Both default to ``None`` (off) so the ordinary run is byte-for-byte unchanged. A captioner needs the
    figure image, so it flips ``generate_picture_images``; the vector reader re-reads the PDF bytes itself.

    ALLUMAGE NOTE (API confirmed against the installed Docling at ③ dogfood 2026-07-06):
    ``DocumentConverter(format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=
    PdfPipelineOptions(do_ocr=ocr))}).convert(source)`` where ``source`` is a ``DocumentStream(name=...,
    stream=BytesIO(bytes))`` (an in-memory source needs the stream form, not a Path), returning a
    ``ConversionResult`` whose ``.document.export_to_markdown()`` yields the text. The ``name`` carries the
    ``ref`` so the converter keys on the extension."""
    converter, document_stream = _pdf_converter(
        ocr=ocr, force_full_page=force_full_page, want_picture_images=captioner is not None
    )
    return _DoclingBackend(converter, document_stream, BytesIO, captioner, vector_reader_factory)


class _DoclingBackend:  # pragma: no cover - real Docling translation (③-4b ignition, smoke-tested)
    """Thin translation from :class:`SourceReader` to Docling's converter (D43 / D103).

    Holds the brick's converter + the ``DocumentStream`` / ``BytesIO`` constructors (injected so this
    class never imports at module scope) + the two figure-enrichment seams. ``read`` wraps the raw bytes in
    an in-memory stream, converts, and exports markdown — running LOCAL on untrusted content (D100-3). It
    does NOT swallow a failure: a Docling raise propagates to the single ③-4a benne net (D85), which
    preserves the raw source; the fidelity golden-set (D125-B6) decides trust out-of-band, never this call."""

    __slots__ = (
        "_converter",
        "_document_stream",
        "_bytes_io",
        "_captioner",
        "_vector_reader_factory",
    )

    def __init__(
        self,
        converter: object,
        document_stream: object,
        bytes_io: object,
        captioner: ImageCaptioner | None = None,
        vector_reader_factory: VectorReaderFactory | None = None,
    ) -> None:
        self._converter = converter
        self._document_stream = document_stream
        self._bytes_io = bytes_io
        self._captioner = captioner
        self._vector_reader_factory = vector_reader_factory

    def read(self, source: Source) -> str:
        stream = self._document_stream(name=source.ref, stream=self._bytes_io(source.data))
        result = self._converter.convert(stream)
        doc = result.document
        markdown = doc.export_to_markdown()
        if self._captioner is None and self._vector_reader_factory is None:
            return (
                markdown  # ordinary path: figures stay <!-- image --> holes (unchanged behaviour)
            )
        # Figure enrichment (sujet E vector-first, sujet 2 vision fallback) — per-figure fail-open (D85).
        # The reader is built per-DOCUMENT (it imports+opens fitz), ABOVE the per-figure loop, so its
        # construction is wrapped too: a missing brick or an unreadable PDF degrades to no extraction (holes
        # stay / VLM takes over), never a whole-book ERROR (D85 to the letter, symmetry with the captioner).
        try:
            vector_reader = (
                self._vector_reader_factory(source.data)
                if self._vector_reader_factory is not None
                else None
            )
        except Exception:  # noqa: BLE001 - D85: fitz absent / PDF unreadable ⇒ keep the holes, never ERROR the book
            vector_reader = None
        enrichments = _enrich_figures(_body_pictures(doc), vector_reader, self._captioner, doc=doc)
        return weave_enrichments(markdown, enrichments)


def connect_docling_figure_enricher(
    *,
    ocr: bool = False,
    captioner: ImageCaptioner | None = None,
    cloud_captioner: ImageCaptioner | None = None,
    vector_reader_factory: VectorReaderFactory | None = None,
    images: bool = False,
) -> FigureEnricher:  # pragma: no cover - needs the brick (③ ignition)
    """Wrap Docling as a :class:`FigureEnricher` (sujet F) — enrich an EXISTING ``.md`` from its PDF, in place.

    The seam the incremental campaign speaks to. Unlike :func:`connect_docling` (which converts a PDF into
    fresh markdown), this re-opens ONLY the PDF to find its FIGURES and splices their read-outs into the
    markdown the caller already holds — the operator's cached, OCR-polished ``.md`` — so their text of
    record is never re-derived. ``ocr=False`` on purpose: figure detection does not need the text layer, so
    this stays fast even on a scanned book. THREE figure seams, tried cheapest-first
    (:func:`_enrich_one_figure`): ``vector_reader_factory`` (MNEMOSYNE_FIGURES — exact vector extraction),
    ``captioner`` (MNEMOSYNE_VISION — the local VLM, raster fallback), and ``cloud_captioner`` (sujet G /
    niveau 3 — a Guard-mediated FRONTIER captioner, reached ONLY for the abstract charts both locals fail,
    and ONLY here in the incremental mode, never in the plain full ingestion). Sole Docling importer (D103 /
    invariant 20); confirmed at the smoke.

    ``images=True`` (arc D) turns on Docling's picture rendering so ``enrich_markdown(..., assets=sink)`` can
    KEEP each figure's pixels instead of only describing them. It is a separate flag from the sink itself
    because the pipeline option is fixed when the converter is built, while the sink is per-book: without it
    Docling attaches no image and every figure would silently fall back to the text paths."""
    converter, document_stream = _pdf_converter(
        ocr=ocr,
        force_full_page=False,
        want_picture_images=images or captioner is not None or cloud_captioner is not None,
    )
    return _DoclingFigureEnricher(
        converter, document_stream, BytesIO, captioner, vector_reader_factory, cloud_captioner
    )


class _DoclingFigureEnricher:  # pragma: no cover - real Docling translation (③ ignition, smoke-tested)
    """Translate a :class:`FigureEnricher` call to Docling: convert the PDF, route each BODY figure, splice.

    Mirrors :class:`_DoclingBackend`, but for the IN-PLACE mode: it weaves onto the caller's EXISTING
    markdown via :func:`~mnemosyne.ingest.figure_enrich.enrich_outcome` (which FAIL-CLOSES on a
    hole/BODY-picture count mismatch — a read-out on the wrong figure is worse than a hole) instead of
    Docling's own export, and returns a :class:`FigureEnrichOutcome` (markdown + stats) rather than a bare
    string. The vector reader is built per-document and its construction is wrapped (D85: a missing brick or
    an unreadable PDF degrades to no extraction — holes stay / the VLM takes over — never a whole-book raise)."""

    __slots__ = (
        "_converter",
        "_document_stream",
        "_bytes_io",
        "_captioner",
        "_vector_reader_factory",
        "_cloud_captioner",
    )

    def __init__(
        self,
        converter: object,
        document_stream: object,
        bytes_io: object,
        captioner: ImageCaptioner | None,
        vector_reader_factory: VectorReaderFactory | None,
        cloud_captioner: ImageCaptioner | None = None,
    ) -> None:
        self._converter = converter
        self._document_stream = document_stream
        self._bytes_io = bytes_io
        self._captioner = captioner
        self._vector_reader_factory = vector_reader_factory
        self._cloud_captioner = cloud_captioner

    def enrich_markdown(
        self, existing_md: str, pdf: bytes, *, assets: FigureImageSink | None = None
    ) -> FigureEnrichOutcome:
        stream = self._document_stream(name="figure-enrich.pdf", stream=self._bytes_io(pdf))
        doc = self._converter.convert(stream).document
        try:
            vector_reader = (
                self._vector_reader_factory(pdf)
                if self._vector_reader_factory is not None
                else None
            )
        except Exception:  # noqa: BLE001 - D85: fitz absent / PDF unreadable ⇒ no extraction, never raise
            vector_reader = None
        # DECIDE ALIGNMENT BEFORE MATERIALIZING ANYTHING. An isolated audit measured the cost of doing
        # it after: on three books the campaign REFUSED (fail-closed on the .md, correctly) it had
        # already written 191 PNG / 6,53 Mo of assets no markdown will ever link — while the report said
        # "non modifié". The fail-closed gate protected the text and not the disk. Counting BODY pictures
        # is free (no pixels rendered, no vector read); only past this point does anything get made.
        pictures = _body_pictures(doc)
        if len(pictures) != count_image_holes(existing_md):
            return enrich_outcome(
                existing_md, [None] * len(pictures)
            )  # same verdict, zero bytes made
        enrichments = _enrich_figures(
            pictures, vector_reader, self._captioner, self._cloud_captioner, assets, doc=doc
        )
        return enrich_outcome(existing_md, enrichments)


def _body_pictures(doc: object) -> list[object]:
    """The BODY figures, in Docling's export order — the population the hole splice aligns against.

    The markdown carries one ``<!-- image -->`` per BODY picture, but ``doc.pictures`` ALSO holds FURNITURE
    images (logos, running headers/footers) that the serializer EXCLUDES. Keeping those would shift every
    following enrichment by one and drop the last, so any picture whose ``content_layer`` is not ``BODY`` is
    skipped — compared by NAME to avoid importing the Docling enum (keeps this brick-free and unit-testable,
    the alignment contract pinned in tests). Split out from :func:`_enrich_figures` so the caller can COUNT
    before anything is materialized: a refused book must cost zero rendered pixels and zero written bytes."""
    return [
        picture
        for picture in getattr(doc, "pictures", ())
        if getattr(getattr(picture, "content_layer", None), "name", "BODY") == "BODY"
    ]


def _enrich_figures(
    pictures: list[object],
    vector_reader: VectorFigureReader | None,
    captioner: ImageCaptioner | None,
    cloud_captioner: ImageCaptioner | None = None,
    image_sink: FigureImageSink | None = None,
    doc: object = None,
) -> list[Enrichment | None]:
    """One enrichment per BODY figure, in order — routed by :func:`_enrich_one_figure`.

    ``pictures`` comes from :func:`_body_pictures` and is ALREADY filtered, so the index here IS the
    ordinal the splice uses. A ``None`` entry leaves its hole (fail-open, D85)."""
    return [
        _enrich_one_figure(
            picture, doc, vector_reader, captioner, cloud_captioner, image_sink, ordinal=index
        )
        for index, picture in enumerate(pictures)
    ]


def _enrich_one_figure(
    picture: object,
    doc: object,
    vector_reader: VectorFigureReader | None,
    captioner: ImageCaptioner | None,
    cloud_captioner: ImageCaptioner | None = None,
    image_sink: FigureImageSink | None = None,
    *,
    ordinal: int = 0,
) -> Enrichment | None:
    """Pick ONE enrichment for a figure — the FIGURE ITSELF when we can keep it, else a description of it.

    Four levels. (0) THE IMAGE (arc D): when an ``image_sink`` is wired, the figure's own PNG is written and
    the hole gets a ``![…](….png)`` link — it wins over every description because it is the figure, costs no
    model, and cannot hallucinate. It CARRIES the vector read-out on the same line when there is one, so the
    index keeps a searchable trace of a figure that is otherwise invisible to retrieval. Then, as fallbacks,
    the three description paths, cheapest-and-most-local first: (1) VECTOR data-extraction — fast, exact,
    local (sujet E); (2) the LOCAL VLM caption (sujet 2) — asked only THEN (it is slow), so no inference is
    spent on a figure already handled; (3) the FRONTIER captioner (sujet G / niveau 3) — a Guard-mediated
    cloud egress under a canal-B human gesture — asked ONLY when BOTH local paths failed. So the cloud (cost
    + an egress) is the last resort, and with the image path on it is never reached at all. Any per-figure
    failure degrades to the next path, then to ``None`` (fail-open, D85)."""
    readout = ""
    if vector_reader is not None:
        primitives = _figure_primitives(picture, doc, vector_reader)
        if primitives is not None and not is_raster_figure(primitives):
            readout = describe_vector_figure(primitives)
    if image_sink is not None:
        png = _figure_png(picture, doc)
        if png:
            # The figure IS renderable, so the only reason the sink can fail is the DESTINATION (full
            # disk, read-only mount, a name the file system refuses). Falling through to the text paths
            # there would be the worst outcome available: it writes exactly the descriptions this arc
            # exists to remove, it BURNS the one-shot .prefig backup (so a later corrective run finds no
            # holes and skips the book), and the tally reports a 100 % local fill rate with 0 errors. An
            # isolated audit measured that exact silent degradation. So: KEEP THE HOLE. A hole is honest,
            # costs nothing, and the next run fills it.
            return (
                (FIGURE_IMAGE_MARK, payload)
                if (payload := image_payload(image_sink.save(ordinal, png), ordinal, readout))
                else None
            )
        # png is empty ⇒ Docling could not render THIS figure (not a disk problem): the text paths below
        # are the legitimate fallback, and the .prefig is spent on something rather than nothing.
    if readout:
        return (FIGURE_DATA_MARK, readout)
    if captioner is not None:
        caption = _vlm_caption(picture, doc, captioner)
        if caption and not is_degenerate_caption(caption):
            return (FIGURE_CAPTION_MARK, caption)
    if cloud_captioner is not None:
        # niveau 3 (sujet G): both local paths gave up. The frontier captioner is Guard-mediated — it sends
        # NOTHING unless a canal-B gesture + an allow-listed host clear the egress (D90 / D100), so this line
        # is a no-op leak when unauthorized. A degenerate frontier reply (empty / too short) still leaves the
        # hole (symmetry with the 7B), rather than weaving a useless line.
        caption = _vlm_caption(picture, doc, cloud_captioner)
        if caption and not is_degenerate_caption(caption):
            return (FIGURE_CLOUD_MARK, caption)
    return None


def _figure_primitives(
    picture: object, doc: object, vector_reader: VectorFigureReader
) -> FigurePrimitives | None:
    """Read a BODY figure's vector primitives via the reader, or ``None`` on any failure (fail-open, D85).

    Maps the figure's Docling provenance (``picture.prov[0]``: ``page_no`` + ``bbox``) into the reader's
    frame (:func:`_to_pymupdf_frame`) and asks the reader for the primitives inside that region."""
    try:
        prov = getattr(picture, "prov", None) or ()
        if not prov:
            return None
        frame = _to_pymupdf_frame(prov[0], doc)
        if frame is None:
            return None
        page_index, bbox = frame
        return vector_reader.figure_primitives(page_index, bbox)
    except Exception:  # noqa: BLE001 - fail-open per figure (D85): an unreadable region never aborts the book
        return None


def _to_pymupdf_frame(
    prov_item: object, doc: object
) -> tuple[int, tuple[float, float, float, float]] | None:
    """Map a Docling ``ProvenanceItem`` to ``(page_index_0based, bbox_top_left)`` for the vector reader.

    Docling numbers pages from 1 and MAY carry a bottom-left ``bbox``; the reader wants a 0-based page and a
    top-left region (the frame pinned in :mod:`~mnemosyne.ports.vectorfigure`). ALLUMAGE NOTE: the exact
    ``ProvenanceItem`` shape (``page_no``, ``bbox`` with ``to_top_left_origin(page_height)`` / ``.l .t .r
    .b``) is confirmed against the installed Docling at the smoke ([OPERATOR]); a drift fails the region open
    (D85)."""
    page_no = getattr(prov_item, "page_no", None)
    bbox = getattr(prov_item, "bbox", None)
    if page_no is None or bbox is None:
        return None
    to_top_left = getattr(bbox, "to_top_left_origin", None)
    if callable(to_top_left):  # pragma: no cover - real Docling BoundingBox (smoke-tested)
        page = doc.pages.get(page_no) if hasattr(doc, "pages") else None
        height = getattr(getattr(page, "size", None), "height", None)
        if height is not None:
            bbox = to_top_left(page_height=height)
    region = (float(bbox.l), float(bbox.t), float(bbox.r), float(bbox.b))
    return int(page_no) - 1, region


def _figure_png(picture: object, doc: object) -> bytes:
    """Render ONE BODY figure to PNG bytes, or ``b""`` on any failure (fail-open, D85).

    The SINGLE place the pixels are materialized (anti-drift): both consumers go through it — the VLM paths,
    which send them to a model and keep the words, and the image sink (arc D), which keeps the pixels. Needs
    ``generate_picture_images`` on in the pipeline options, else Docling attaches no image and this returns
    ``b""``. ALLUMAGE NOTE: ``picture.get_image(doc)`` confirmed against the installed Docling at the smoke."""
    try:
        image = picture.get_image(doc)
        if image is None:
            return b""
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        return buffer.getvalue()
    except Exception:  # noqa: BLE001 - fail-open per figure (D85): a bad image never aborts the book
        return b""


def _vlm_caption(picture: object, doc: object, captioner: ImageCaptioner) -> str:
    """Caption ONE BODY figure with the local VLM (sujet 2 fallback), or ``""`` on any failure (D85).

    Asks the injected captioner on the figure's PNG (:func:`_figure_png`), grounded by the figure's own
    caption line when present. FAIL-OPEN (D85): ANY failure yields ``""`` so the hole simply stays; the
    captioner output is model-generated and Guard-mediated upstream (D100). ALLUMAGE NOTE: confirm
    ``picture.caption_text(doc)`` against the installed Docling at the smoke."""
    png = _figure_png(picture, doc)
    if not png:
        return ""
    try:
        caption_text = getattr(picture, "caption_text", None)
        context = caption_text(doc) if callable(caption_text) else ""
        return captioner.caption(png, context=context or "")
    except Exception:  # noqa: BLE001 - fail-open per figure (D85): a bad image never aborts the book
        return ""
