"""Vector-figure extraction core (sujet E) - brick-free tests on SYNTHETIC primitives (D126).

These pin the deterministic contract of :func:`describe_vector_figure` and the routing switch
:func:`is_raster_figure` without PyMuPDF: the core reads a :class:`FigurePrimitives` snapshot (bars, segments,
axis text, scatter/curve counts) and returns a one-line structured read-out. No model, so the tests assert the
EXACT reconstruction - kind, axis ranges read off the ticks, capped annotations, the bar profile - and the
fail-open empties. The real primitives come from the PyMuPDF adapter ((3) ignition, smoke-tested)."""

from __future__ import annotations

from mnemosyne.ingest.figure_extract import (
    _KIND_CURVE,
    _KIND_GENERIC,
    _KIND_HISTOGRAM,
    _KIND_SCATTER,
    _parse_number,
    describe_vector_figure,
    is_raster_figure,
)
from mnemosyne.ports.vectorfigure import Bar, FigurePrimitives, Segment, TextSpan

_BBOX = (0.0, 0.0, 100.0, 100.0)  # y grows DOWN: bottom is y=100, left is x=0


def _bar(cx: float, height: float, *, baseline: float = 90.0, w: float = 8.0) -> Bar:
    return Bar(cx - w / 2, baseline - height, cx + w / 2, baseline)


def _txt(text: str, cx: float, cy: float, *, w: float = 6.0, h: float = 5.0) -> TextSpan:
    return TextSpan(text, cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)


# --- the happy path: a full histogram is reconstructed exactly ---------------------------------------


def test_histogram_reads_kind_axes_annotation_and_profile() -> None:
    bars = tuple(_bar(cx, h) for cx, h in [(35, 20), (45, 40), (55, 60), (65, 40), (75, 20)])
    x_ticks = (
        _txt("0", 40, 93),
        _txt("0.5", 60, 93),
        _txt("1.0", 80, 93),
    )  # aligned on the axis row
    y_ticks = (
        _txt("0", 3, 85),
        _txt("50", 3, 50),
        _txt("100", 3, 15),
    )  # aligned on the axis column
    annotation = (_txt("peak", 55, 40),)  # a non-numeric callout in the middle
    out = describe_vector_figure(
        FigurePrimitives(_BBOX, bars=bars, texts=x_ticks + y_ticks + annotation)
    )
    assert _KIND_HISTOGRAM in out
    assert "X axis ∈ [0, 1.0]" in out  # ends of the sorted ticks, verbatim
    assert "Y axis ∈ [0, 100]" in out
    assert '"peak"' in out
    assert "height profile (0-100): " in out


def test_bars_are_deduplicated_outline_plus_fill() -> None:
    # a PDF strokes each bar twice (outline + fill) at the same x -> the profile must count it ONCE
    pairs: list[Bar] = []
    for cx, h in [(30, 20), (40, 50), (50, 80), (60, 50), (70, 20)]:
        pairs += [_bar(cx, h), _bar(cx, h)]
    out = describe_vector_figure(FigurePrimitives(_BBOX, bars=tuple(pairs)))
    profile = out.split("height profile (0-100): ")[1]
    assert len([v for v in profile.split(",")]) == 5  # five bars, not ten


# --- the kind heuristics -----------------------------------------------------------------------------


def test_scatter_detected_by_dot_paths() -> None:
    prims = FigurePrimitives(_BBOX, dot_paths=40, texts=(_txt("0", 50, 93), _txt("10", 80, 93)))
    out = describe_vector_figure(prims)
    assert _KIND_SCATTER in out and "40" in out


def test_curve_detected_by_curve_items() -> None:
    prims = FigurePrimitives(_BBOX, curve_items=12, texts=(_txt("0", 50, 93), _txt("5", 80, 93)))
    assert _KIND_CURVE in describe_vector_figure(prims)


def test_generic_kind_when_no_type_signal_but_axes_present() -> None:
    prims = FigurePrimitives(
        _BBOX,
        segments=(Segment(0, 50, 100, 50), Segment(50, 0, 50, 100)),
        texts=(_txt("0", 40, 93), _txt("1", 80, 93)),
    )
    out = describe_vector_figure(prims)
    assert _KIND_GENERIC in out and "X axis" in out


# --- fail-open and the axis robustness ---------------------------------------------------------------


def test_empty_readout_when_nothing_usable() -> None:
    # no ticks, no annotations, no profile => "" (the hole stays; the VLM may still try) - D85
    assert describe_vector_figure(FigurePrimitives(_BBOX, segments=(Segment(0, 0, 10, 10),))) == ""


def test_a_single_tick_is_not_an_axis() -> None:
    bars = tuple(_bar(cx, h) for cx, h in [(40, 20), (50, 40), (60, 60), (45, 30)])
    out = describe_vector_figure(FigurePrimitives(_BBOX, bars=bars, texts=(_txt("0.5", 50, 93),)))
    assert "X axis" not in out  # one lone tick is not enough to claim an axis


def test_alignment_drops_a_stray_caption_number_from_the_axis() -> None:
    # three real y-ticks aligned on the axis column, plus a "5.14" from a caption at a different column
    y_ticks = (_txt("0", 3, 80), _txt("0.5", 3, 50), _txt("1.0", 3, 20))
    stray = _txt("5.14", 22, 95)  # near-left but off the axis column and row
    bars = tuple(_bar(cx, h) for cx, h in [(40, 20), (50, 40), (60, 20), (45, 30)])
    out = describe_vector_figure(FigurePrimitives(_BBOX, bars=bars, texts=y_ticks + (stray,)))
    assert "Y axis ∈ [0, 1.0]" in out  # the real range, uncorrupted
    assert "5.14" not in out  # the caption number is excluded, never widening the range


def test_annotations_are_capped() -> None:
    anns = tuple(_txt(f"note{i}", 55, 40.0 + i * 0.1) for i in range(12))  # 12 middle callouts
    bars = tuple(_bar(cx, h) for cx, h in [(40, 20), (50, 40), (60, 20), (45, 30)])
    out = describe_vector_figure(FigurePrimitives(_BBOX, bars=bars, texts=anns))
    assert "…" in out  # truncated
    assert out.count('"note') == 8  # only the first eight shown


def test_readout_is_a_single_line() -> None:
    # the verbatim-floor mask is line-scoped: the read-out MUST stay on one line (C2/E)
    bars = tuple(_bar(cx, h) for cx, h in [(40, 20), (50, 40), (60, 20), (45, 30)])
    texts = (_txt("0", 40, 93), _txt("1", 60, 93), _txt("peak", 50, 40))
    out = describe_vector_figure(FigurePrimitives(_BBOX, bars=bars, texts=texts))
    assert out and "\n" not in out


# --- the routing switch: raster vs vector ------------------------------------------------------------


def test_is_raster_true_when_an_image_covers_the_region() -> None:
    prims = FigurePrimitives(_BBOX, raster_coverage=0.8, segments=(Segment(0, 0, 100, 100),) * 20)
    assert is_raster_figure(prims) is True


def test_is_raster_true_when_almost_no_vector_content() -> None:
    assert is_raster_figure(FigurePrimitives(_BBOX, segments=(Segment(0, 0, 1, 1),) * 3)) is True


def test_is_raster_false_on_a_vector_chart() -> None:
    prims = FigurePrimitives(
        _BBOX,
        bars=tuple(_bar(c, 10) for c in range(10, 90, 10)),
        segments=(Segment(0, 0, 1, 1),) * 30,
    )
    assert is_raster_figure(prims) is False


# --- number parsing (axis tick vs annotation) --------------------------------------------------------


def test_parse_number_variants_and_non_numbers() -> None:
    assert _parse_number("-0.15") == -0.15
    assert _parse_number("+4.84%") == 4.84
    assert _parse_number("0") == 0.0
    assert _parse_number("1,5") == 1.5
    assert _parse_number("TT-4-91") is None  # an annotation, not a tick
    assert _parse_number("p-value") is None
