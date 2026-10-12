"""Vector-figure data extraction (topic E) — turn a chart's OWN primitives into a structured read-out.

Docling drops every figure to an ``<!-- image -->`` hole (D140). For a RASTER figure the pixels are all there
is, so the vision VLM (topic 2) guesses at them. But a huge share of book charts are VECTOR: the histogram
bars, scatter dots and curve polylines are thousands of drawing ops in the PDF — the data is literally present
(measured: one Aronson histogram = 7 478 line ops, ZERO pixels). This BRICK-FREE, deterministic core reads that
data. Given a :class:`~mnemosyne.ports.vectorfigure.FigurePrimitives` snapshot of ONE figure region it returns
a ONE-LINE structured read-out — figure kind, axis ranges (the PDF's own tick labels, verbatim), inner
annotations, and, for a bar chart, the height profile (the shape) — with NO model, so NO hallucination is
possible (D100 holds trivially; the only invented word would be our own generic labels, which is why the whole
line is masked from the verbatim floor via :data:`~mnemosyne.provenance.FIGURE_DATA_MARK`, C2/E).

Two seams keep it honest: the primitives come from a swap-able :class:`~mnemosyne.ports.vectorfigure.VectorFigureReader`
(real adapter = PyMuPDF, sole importer, ③ ignition), and this core is pure — unit-tested with SYNTHETIC
primitives, nothing installed (D126). Heuristics are PRUDENT and fail-soft: an unrecognised figure degrades to
"Vector figure" + whatever axes/annotations were found, and a region with nothing usable returns ``""``
(fail-open, D85: the hole simply stays). :func:`is_raster_figure` is the routing switch — a region that is
mostly a raster image, or almost devoid of vector content, is sent BACK to the VLM path instead.

Decisions: D140 (.md-first enrichment) · D43 (enriches Docling) · D100 (deterministic ⇒ nothing to mediate) ·
D85 (fail-open per figure) · D126 (brick-free, testable core) · restructure-not-reformulate (masked, never P3).
Code, docstrings and the emitted read-out are English (D117) — the read-out lands in the user's ``.md`` (D33).
"""

from __future__ import annotations

import os
import re
from collections.abc import Callable

from ..ports.vectorfigure import Bar, FigurePrimitives, Segment, TextSpan, VectorFigureReader

# --- tunables (prudent thresholds; a miss degrades to a poorer label, never to a false datum) --------
_MIN_BARS = 4  # fewer rectangles than this ⇒ not a bar chart
_MIN_DOTS = 10  # tiny isolated filled paths ⇒ scatter
_MIN_CURVE_ITEMS = 8  # bezier draw items ⇒ smooth curve(s)
_MIN_DIAGONAL_SEGS = 20  # many non-H/V strokes ⇒ curve(s) drawn as polylines
_RASTER_COVERAGE = 0.5  # ≥ half the bbox is a raster image ⇒ treat as raster (route to the VLM)
_MIN_VECTOR_SIGNAL = (
    8  # below this much vector content, there is nothing to extract ⇒ treat as raster
)
_MIN_AXIS_TICKS = (
    2  # an axis needs ≥2 ticks; a lone numeric near a border (a page number) is not an axis
)
_MAX_ANNOTATIONS = 8  # cap the read-out: a real chart has a handful of callouts, not a paragraph

_KIND_HISTOGRAM = "Histogram / bar chart"
_KIND_SCATTER = "Scatter plot"
_KIND_CURVE = "Curve(s)"
_KIND_GENERIC = "Vector figure"

_NUMBER_RE = re.compile(r"^[+\-−]?\d{1,4}(?:[.,]\d+)?\s*%?$")


def _parse_number(text: str) -> float | None:
    """Parse an axis tick label to a float, or ``None`` if it is not a plain number (⇒ it is an annotation).

    Accepts a leading sign (ASCII ``-`` or the Unicode minus ``−``), one decimal separator (``.`` or ``,``)
    and a trailing ``%`` — the shapes axis ticks take (``0.12``, ``-0.15``, ``50%``). Anything else (a legend,
    ``p-value``, ``TT-4-91``) returns ``None`` so the caller files it as an inner annotation."""
    stripped = text.strip()
    if not _NUMBER_RE.match(stripped):
        return None
    cleaned = stripped.replace("−", "-").rstrip("%").strip().replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:  # pragma: no cover - regex already gates the shape
        return None


def _dedup_keep_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for it in items:
        s = it.strip()
        if s and s not in seen:
            seen.add(s)
            out.append(s)
    return out


def _split_axis_texts(
    primitives: FigurePrimitives,
) -> tuple[list[TextSpan], list[TextSpan], list[str]]:
    """Sort the figure's text spans into (x-axis labels, y-axis labels, inner annotations).

    A numeric span near the BOTTOM border is an x tick; near the LEFT border, a y tick; a numeric span in the
    middle (a ``p-value 0.069`` callout) and every non-numeric span are annotations. Axis labels come back
    sorted by value so the caller reads the range off the ends. Robust to a degenerate bbox (everything then
    files as an annotation)."""
    x0, y0, x1, y1 = primitives.bbox
    width, height = x1 - x0, y1 - y0
    x_ticks: list[tuple[float, TextSpan]] = []
    y_ticks: list[tuple[float, TextSpan]] = []
    annotations: list[str] = []
    for span in primitives.texts:
        value = _parse_number(span.text)
        if value is None or width <= 0 or height <= 0:
            annotations.append(span.text)
            continue
        cx, cy = (span.x0 + span.x1) / 2, (span.y0 + span.y1) / 2
        near_bottom = cy >= y0 + 0.66 * height
        near_left = cx <= x0 + 0.30 * width
        if near_left:
            y_ticks.append((value, span))
        elif near_bottom:
            x_ticks.append((value, span))
        else:
            annotations.append(span.text)  # a numeric inner annotation, not an axis tick
    # an axis is the LARGEST cluster of ticks sharing an alignment line (cy for X, cx for Y); this drops a
    # stray numeric near a border — a page number, a "5.14" bleeding in from a caption — that would else skew
    # the reported range. A cluster below _MIN_AXIS_TICKS is no axis at all.
    x_axis = _largest_aligned(x_ticks, axis="x")
    y_axis = _largest_aligned(y_ticks, axis="y")
    x_axis.sort(key=lambda vt: vt[0])
    y_axis.sort(key=lambda vt: vt[0])
    return [s for _, s in x_axis], [s for _, s in y_axis], _dedup_keep_order(annotations)


def _largest_aligned(
    candidates: list[tuple[float, TextSpan]], *, axis: str
) -> list[tuple[float, TextSpan]]:
    """Return the largest group of tick candidates sharing an alignment line, or ``[]`` below the minimum.

    Axis ticks line up: x ticks share a ``y`` (the axis row), y ticks share an ``x`` (the axis column).
    Bucketing by that coordinate (±~4 pt) keeps the real, regularly-spaced axis and drops the outliers — a
    caption number, one mis-placed label — that a naive min/max over all near-border numbers would swallow."""
    if len(candidates) < _MIN_AXIS_TICKS:
        return []
    buckets: dict[int, list[tuple[float, TextSpan]]] = {}
    for value, span in candidates:
        coord = (span.y0 + span.y1) / 2 if axis == "x" else (span.x0 + span.x1) / 2
        buckets.setdefault(round(coord / 4.0), []).append((value, span))
    best = max(buckets.values(), key=len)
    return best if len(best) >= _MIN_AXIS_TICKS else []


def _bar_profile(bars: tuple[Bar, ...]) -> list[int]:
    """Read a bar chart's height profile, normalized 0-100 (the SHAPE), or ``[]`` if it is not a bar chart.

    Bars are de-duplicated by rounded x-centre (a PDF strokes each bar twice — outline + fill), heights are
    measured from the common baseline (the largest ``y``, since ``y`` grows down), then scaled to the tallest
    bar. The relative profile conveys the distribution's shape without inventing a y-unit (the true y-RANGE is
    reported separately from the axis ticks)."""
    if len(bars) < _MIN_BARS:
        return []
    baseline = max(b.y1 for b in bars)
    groups: dict[int, list[float]] = {}
    for b in bars:
        groups.setdefault(round((b.x0 + b.x1) / 2), []).append(baseline - b.y0)
    heights = [max(hs) for _, hs in sorted(groups.items())]
    if len(heights) < _MIN_BARS:
        return []
    tallest = max(heights)
    if tallest <= 0:
        return []
    return [
        max(0, round(100 * h / tallest)) for h in heights
    ]  # clamp a degenerate (y0 > baseline) bar to 0


def _count_diagonals(segments: tuple[Segment, ...]) -> int:
    return sum(1 for s in segments if abs(s.x1 - s.x0) > 1 and abs(s.y1 - s.y0) > 1)


def _figure_kind_and_profile(primitives: FigurePrimitives) -> tuple[str, list[int]]:
    """Classify the figure (prudently) and, for a bar chart, return its height profile."""
    profile = _bar_profile(primitives.bars)
    if profile:
        return f"{_KIND_HISTOGRAM} (~{len(profile)} bins)", profile
    if primitives.dot_paths >= _MIN_DOTS:
        return f"{_KIND_SCATTER} (~{primitives.dot_paths} points)", []
    if (
        primitives.curve_items >= _MIN_CURVE_ITEMS
        or _count_diagonals(primitives.segments) >= _MIN_DIAGONAL_SEGS
    ):
        return _KIND_CURVE, []
    return _KIND_GENERIC, []


def is_raster_figure(primitives: FigurePrimitives) -> bool:
    """Whether this figure region is really PIXELS (⇒ route to the vision VLM), not vector data to extract.

    Raster when an image covers at least half the region. Otherwise VECTOR when it holds clearly-structured
    content (a bar chart, a dense scatter, curves — extractable however few the total primitives) OR enough
    vector primitives to be worth reading; only a region with almost no vector content (a stray rule, a lone
    box) falls back to raster. This is the routing switch between the two figure-enrichment paths (topic E vs
    topic 2)."""
    if primitives.raster_coverage >= _RASTER_COVERAGE:
        return True
    if (
        len(primitives.bars) >= _MIN_BARS
        or primitives.dot_paths >= _MIN_DOTS
        or primitives.curve_items >= _MIN_CURVE_ITEMS
    ):
        return False  # clearly-structured vector content is always extractable, never raster
    vector_signal = (
        len(primitives.bars)
        + len(primitives.segments)
        + primitives.dot_paths
        + primitives.curve_items
    )
    return vector_signal < _MIN_VECTOR_SIGNAL


def describe_vector_figure(primitives: FigurePrimitives) -> str:
    """Reconstruct a ONE-LINE structured read-out of a vector figure, or ``""`` when nothing is usable.

    Composes: the figure kind, the axis RANGES (read verbatim off the PDF's own tick labels), the inner
    annotations, and — for a bar chart — the 0-100 height profile (the shape). Returns ``""`` (fail-open, D85)
    when the region yields no axes, no annotations and no profile, so the caller keeps the hole rather than
    inserting an empty mark. Pure and deterministic — the same primitives always give the same line, and no
    word is invented beyond the fixed kind labels (which is why the whole line is masked from the verbatim
    floor, C2/E). The caller prefixes :data:`~mnemosyne.provenance.FIGURE_DATA_MARK` and collapses to one
    line before weaving."""
    x_labels, y_labels, annotations = _split_axis_texts(primitives)
    kind, profile = _figure_kind_and_profile(primitives)

    if not x_labels and not y_labels and not annotations and not profile:
        return (
            ""  # fail-open: a vector region we could not read stays a hole (the VLM may still try)
        )

    parts: list[str] = [kind]
    axis_bits: list[str] = []
    if x_labels:
        axis_bits.append(f"X axis ∈ [{x_labels[0].text.strip()}, {x_labels[-1].text.strip()}]")
    if y_labels:
        axis_bits.append(f"Y axis ∈ [{y_labels[0].text.strip()}, {y_labels[-1].text.strip()}]")
    if axis_bits:
        parts.append(", ".join(axis_bits))
    if annotations:
        shown = annotations[:_MAX_ANNOTATIONS]
        more = "; …" if len(annotations) > _MAX_ANNOTATIONS else ""
        parts.append("annotations: " + "; ".join(f'"{a}"' for a in shown) + more)
    if profile:
        parts.append("height profile (0-100): " + ", ".join(str(v) for v in profile))
    # Collapse ANY stray whitespace so the read-out is genuinely one line at the source — the verbatim-floor
    # mask is line-scoped, and a PDF axis label can carry a newline (defense in depth; the weave collapses too).
    return " ".join(" — ".join(parts).split())


#: Opt-in switch for the vector-figure stage in REAL ingestion. The operator sets it for a run
#: (``MNEMOSYNE_FIGURES=1 …``); unset (default) ⇒ ingestion behaves EXACTLY as before this stage — no brick,
#: zero regression.
_FIGURES_ENV_VAR = "MNEMOSYNE_FIGURES"


def vector_reader_factory_if_enabled() -> Callable[[bytes], VectorFigureReader] | None:
    """The SINGLE opt-in switch for vector figure extraction in PRODUCTION (``real_runtime`` and
    ``library_run`` both call it — anti-drift, one place decides): return the PyMuPDF reader FACTORY iff
    :data:`_FIGURES_ENV_VAR` is set, else ``None`` so ``connect_docling(vector_reader_factory=None)`` is
    exactly the pre-extraction default (zero regression, D126). LOCAL and free (no model), but it needs the
    ``pymupdf`` brick, so it stays opt-in; the brick imports LAZILY, only when the switch is ON, so an
    ingestion with the switch OFF never touches ``fitz`` (the brick-free suite stays green). Complementary to
    ``MNEMOSYNE_VISION``: with both on, extraction wins on VECTOR figures and the VLM handles the RASTER ones
    (the routing in :func:`~mnemosyne.ingest.source_docling._enrich_one_figure`)."""
    if not os.environ.get(_FIGURES_ENV_VAR):
        return None
    from .vector_pymupdf import (
        connect_pymupdf_reader,
    )  # lazy brick import — only when the switch is ON

    return connect_pymupdf_reader
