"""_PyMuPDFVectorReader — the SOLE importer of PyMuPDF / ``fitz`` (sujet E / D103 / invariant 20).

The default engine for :class:`~mnemosyne.ports.vectorfigure.VectorFigureReader`: it wraps **PyMuPDF**
(``fitz`` — AGPL, used here as a LOCAL, non-distributed dev brick; ``oss_registry.md``), whose ``get_drawings``
/ ``get_text`` expose a page's OWN vector primitives. SOLE-importer adapter (D103 / invariant 20): the one
module allowed to touch ``fitz``, imported LAZILY so the suite stays green with no brick installed (D126).
Everything here is ``# pragma: no cover`` — it runs only at ③ ignition (``uv add --optional bricks pymupdf``),
confronted to the real fitz API by the smoke, not by CI.

LOCAL, read-only, free (invariant 1 / D66): it re-opens PDF bytes already on disk and reads primitives — no
inference, no network, nothing leaves. The extracted read-out is DETERMINISTIC (not a model guess), so — unlike
a VLM caption — it needs no Guard mediation (D100 holds trivially; there is nothing generated to distrust).

Honesty (F3): the exact fitz API (``get_drawings`` item tuples ``("l"/"re"/"c", …)``, ``get_text("words",
clip=…)``, ``get_image_rects``) is taken from the documented format with an ALLUMAGE NOTE to confirm at the
smoke — the PURE reading of primitives into a read-out (:mod:`~mnemosyne.ingest.figure_extract`) is unit-tested;
only THIS translation is uncovered, and per-region fail-open (D85) keeps a hole rather than crash on any drift.
The Docling→PyMuPDF coordinate mapping is the CALLER's job (E5 holds the page height); this adapter clips in
the page-points, top-left frame the port pins.

Decisions: D43 (enriches Docling — the figure the VLM would fail) · D103 (sole importer) · D126 (import-safe) ·
invariant 1 / D66 (local, free) · D100 (deterministic ⇒ nothing to mediate) · D85 (fail-open per region).
Code & docstrings English (D117).
"""

from __future__ import annotations

from ..ports.vectorfigure import Bar, FigurePrimitives, Segment, TextSpan, VectorFigureReader

_DOT_MAX_SIDE = 6.0  # a drawing whose bbox is smaller than this on both sides ≈ a scatter dot


def connect_pymupdf_reader(
    pdf_bytes: bytes,
) -> VectorFigureReader:  # pragma: no cover - needs the brick
    """Open ``pdf_bytes`` with PyMuPDF and return a reader bound to that document (③ allumage seam)."""
    import fitz  # lazy: the sole import of the brick

    return _PyMuPDFVectorReader(fitz.open(stream=pdf_bytes, filetype="pdf"))


class _PyMuPDFVectorReader:  # pragma: no cover - real PyMuPDF translation (smoke-tested at ③)
    """Read ONE figure region's primitives from an open fitz document (D43 / D103), bound to that document."""

    __slots__ = ("_doc",)

    def __init__(self, doc: object) -> None:
        self._doc = doc

    def figure_primitives(
        self, page_no: int, bbox: tuple[float, float, float, float]
    ) -> FigurePrimitives | None:
        import fitz

        try:
            page = self._doc[page_no]
            clip = fitz.Rect(*bbox)
        except Exception:  # noqa: BLE001 - fail-open (D85): an unreadable region simply keeps its hole
            return None
        bars: list[Bar] = []
        segments: list[Segment] = []
        curves = 0
        dots = 0
        try:
            for drawing in page.get_drawings():
                rect = drawing["rect"]
                if (rect & clip).is_empty:
                    continue  # this drawing lies outside the figure region
                if rect.width < _DOT_MAX_SIDE and rect.height < _DOT_MAX_SIDE:
                    dots += 1  # a tiny isolated path ≈ a scatter dot
                for item in drawing["items"]:
                    kind = item[0]
                    if kind == "re":
                        r = item[1]
                        bars.append(Bar(r.x0, r.y0, r.x1, r.y1))
                    elif kind == "l":
                        a, b = item[1], item[2]
                        segments.append(Segment(a.x, a.y, b.x, b.y))
                    elif kind in ("c", "qu"):
                        curves += 1
            texts = tuple(
                TextSpan(w[4], w[0], w[1], w[2], w[3]) for w in page.get_text("words", clip=clip)
            )
            coverage = _raster_coverage(page, clip)
        except Exception:  # noqa: BLE001 - fail-open (D85): a fitz drift degrades to a kept hole, never a crash
            return None
        return FigurePrimitives(
            bbox=(clip.x0, clip.y0, clip.x1, clip.y1),
            segments=tuple(segments),
            bars=tuple(bars),
            texts=texts,
            curve_items=curves,
            dot_paths=dots,
            raster_coverage=coverage,
        )


def _raster_coverage(page: object, clip: object) -> float:  # pragma: no cover - needs the brick
    """Fraction (0..1) of ``clip`` covered by embedded RASTER images — high ⇒ route the figure to the VLM."""
    area = clip.get_area()
    if area <= 0:
        return 0.0
    covered = 0.0
    for image in page.get_images(full=True):
        for rect in page.get_image_rects(image[0]):
            inter = rect & clip
            if not inter.is_empty:
                covered += inter.get_area()
    return min(1.0, covered / area)
