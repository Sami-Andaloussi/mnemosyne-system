"""VectorFigureReader (sujet E) - read a PDF figure's own VECTOR primitives behind a swap-able seam.

Where the :class:`~mnemosyne.ports.captioner.ImageCaptioner` (sujet 2) turns a figure's PIXELS into a model
GUESS, this port turns a figure's VECTOR primitives into EXACT data. Many book charts - histograms, scatter
plots, equity curves - are not images at all but thousands of drawing ops in the PDF (measured: one Aronson
histogram = 7 478 line ops, ZERO pixels): the data is literally there. The reader hands the brick-free core
(:func:`mnemosyne.ingest.figure_extract.describe_vector_figure`) a plain :class:`FigurePrimitives` snapshot of
ONE figure region, and the core reconstructs a structured read-out with NO model and NO possible hallucination
(D100 is trivially satisfied - nothing is *generated*, the axis labels are the PDF's real characters). LOCAL
and free (invariant 1 / D66): re-opening bytes already on disk, no inference.

Brick-free by construction: :class:`FigurePrimitives` is pure stdlib data, so the core is unit-tested with
SYNTHETIC primitives and NOTHING installed (D126). The real adapter (``ingest.vector_pymupdf``, the sole
importer of PyMuPDF, invariant 20) plugs in at (3) ignition, confirmed by user at the smoke.

Coordinate convention (pinned so the core and the adapter agree): all coordinates are PDF points in the
PyMuPDF frame - origin TOP-LEFT, ``y`` increasing DOWNWARD - so a figure's ``bbox`` has ``y0`` (top) < ``y1``
(bottom), and a bar's BASELINE is its largest ``y``. The adapter normalizes whatever frame the figure-enumerator
(Docling ``picture.prov``) uses into this one. Code & docstrings English (D117).

Decisions: D43 (enriches Docling - the figure the VLM would fail on)  -  D100 (deterministic => no model to
mediate)  -  invariant 1 / D66 (local, free)  -  D126 (brick-free pure types)  -  D125-B5 (port pattern)  -
invariant 20 (sole-importer adapter)  -  [[reuse-oss-aggressively]] (PyMuPDF for the primitives).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class Segment:
    """A straight stroke (an axis line, a grid line, a curve polyline edge), in page points (y grows down)."""

    x0: float
    y0: float
    x1: float
    y1: float


@dataclass(frozen=True)
class Bar:
    """A rectangle primitive - a histogram / bar-chart candidate. Its baseline (max ``y``) and top carry the
    datum (the bar's height); many PDFs stroke each bar twice (outline + fill), so the core de-duplicates by
    ``x`` before reading the profile."""

    x0: float
    y0: float
    x1: float
    y1: float


@dataclass(frozen=True)
class TextSpan:
    """A positioned text span INSIDE the figure region: an axis tick label (``0.12``), a legend, an
    annotation (``p-value 0.069``). Its position lets the core tell an axis label (near a border) from an
    inner annotation. The ``text`` is the PDF's OWN characters - genuine verbatim."""

    text: str
    x0: float
    y0: float
    x1: float
    y1: float


@dataclass(frozen=True)
class FigurePrimitives:
    """A pure, brick-free snapshot of ONE figure region's vector content - everything the core reads.

    ``bbox`` is the figure region ``(x0, y0, x1, y1)`` in page points (y grows down). ``raster_coverage`` is
    the 0..1 fraction of ``bbox`` covered by an embedded RASTER image: high => the figure is really pixels, so
    the classifier routes it to the vision VLM instead (:func:`~mnemosyne.ingest.figure_extract.is_raster_figure`).
    ``curve_items`` / ``dot_paths`` are cheap type signals the adapter counts once (bezier draw items; tiny
    isolated filled paths = scatter dots) so the core need not re-derive them."""

    bbox: tuple[float, float, float, float]
    segments: tuple[Segment, ...] = ()
    bars: tuple[Bar, ...] = ()
    texts: tuple[TextSpan, ...] = ()
    curve_items: int = 0
    dot_paths: int = 0
    raster_coverage: float = 0.0
    _unused: tuple[()] = field(
        default=(), repr=False
    )  # placeholder to keep kw-only extension cheap


@runtime_checkable
class VectorFigureReader(Protocol):
    """Read ONE figure region's vector primitives from a document, so the core can extract its data (sujet E).

    A reader is bound to ONE document (built from its PDF bytes by the adapter, ``connect_pymupdf_reader``).
    LOCAL and deterministic - it only reads primitives already in the file (invariant 1); nothing is
    generated, so unlike a captioner its output needs no Guard mediation."""

    def figure_primitives(
        self, page_no: int, bbox: tuple[float, float, float, float]
    ) -> FigurePrimitives | None:
        """Return the vector primitives inside ``bbox`` on page ``page_no`` (0-based), or ``None`` when the
        region cannot be read - FAIL-OPEN (D85): the caller keeps the figure hole (or falls back to the VLM)
        rather than losing the book. ``bbox`` is in the enumerator's frame; the adapter maps it to page
        points (the convention pinned in this module's docstring)."""
        ...


class NullVectorFigureReader:
    """Brick-free stub reader: reads NOTHING (D126), so the suite is green with no PyMuPDF installed.

    Returns ``None`` for every region, so the figure-enrichment pipeline behaves EXACTLY as before the vector
    stage (purely additive, opt-in - the real PyMuPDF adapter is injected only at (3) ignition)."""

    def figure_primitives(
        self, page_no: int, bbox: tuple[float, float, float, float]
    ) -> FigurePrimitives | None:  # noqa: ARG002 - stub ignores its input
        return None
