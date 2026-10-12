"""Vision caption weaving (sujet 2) - brick-free tests for the figure-hole enrichment core.

Producer ≠ verifier (D75): an isolated audit checks this independently. These tests pin the
deterministic weave - marking, document order, fail-open on empty captions - with NO VLM installed
(D126), so the enrichment core is proven before any brick is wired (tests-before-code, D123).
"""

from __future__ import annotations

import types

from mnemosyne.ingest import (
    NullImageCaptioner,
    is_degenerate_caption,
    vision_captioner_if_enabled,
    weave_captions,
    weave_enrichments,
)
from mnemosyne.ingest.figure_extract import _KIND_HISTOGRAM
from mnemosyne.ingest.source_docling import _body_pictures, _enrich_figures
from mnemosyne.ports import ImageCaptioner
from mnemosyne.ports.vectorfigure import Bar, FigurePrimitives, Segment, TextSpan
from mnemosyne.provenance import FIGURE_CLOUD_MARK, FIGURE_DATA_MARK

PLACEHOLDER = "<!-- image -->"
MARK = "**[Figure described by a model]**"


def test_is_degenerate_caption_rejects_the_7b_fizzle() -> None:
    # the 7B's failure mode on abstract charts: a broken sentence start, then it stops - noise, worse than a hole
    assert is_degenerate_caption("The")
    assert is_degenerate_caption("The court")
    assert is_degenerate_caption("This figure")
    assert is_degenerate_caption("   ")
    assert is_degenerate_caption("")
    # a genuine caption survives (the router keeps it, never falls through to the frontier)
    assert not is_degenerate_caption("A histogram of monthly returns over ten years.")
    assert not is_degenerate_caption(
        "This figure illustrates the block structure of the Bitcoin blockchain."
    )


def test_weaves_caption_in_place_of_placeholder() -> None:
    out = weave_captions(f"Intro\n\n{PLACEHOLDER}\n\nOutro", ["A line chart."])
    assert PLACEHOLDER not in out
    assert f"> {MARK} A line chart." in out
    assert "Intro" in out and "Outro" in out


def test_captions_map_in_document_order() -> None:
    out = weave_captions(
        f"{PLACEHOLDER} A {PLACEHOLDER} B {PLACEHOLDER}", ["first", "second", "third"]
    )
    assert PLACEHOLDER not in out
    assert out.index("first") < out.index("second") < out.index("third")


def test_empty_caption_leaves_placeholder_untouched() -> None:
    # fail-open (D85): a per-figure failure - or the stub - must NOT drop the hole
    out = weave_captions(f"{PLACEHOLDER} middle {PLACEHOLDER}", ["", "described"])
    assert out.count(PLACEHOLDER) == 1  # first hole kept, second woven
    assert f"> {MARK} described" in out


def test_more_placeholders_than_captions_keeps_the_rest() -> None:
    out = weave_captions(f"{PLACEHOLDER} {PLACEHOLDER} {PLACEHOLDER}", ["only one"])
    assert out.count(PLACEHOLDER) == 2
    assert "only one" in out


def test_more_captions_than_placeholders_ignores_surplus() -> None:
    out = weave_captions(f"one hole {PLACEHOLDER}", ["used", "ignored", "also ignored"])
    assert "used" in out
    assert "ignored" not in out


def test_multiline_caption_collapsed_to_one_line() -> None:
    out = weave_captions(PLACEHOLDER, ["line one\nline two\n\nline three"])
    assert out == f"> {MARK} line one line two line three"
    assert "\n" not in out


def test_no_placeholder_returns_markdown_unchanged() -> None:
    md = "Pure prose with no figures."
    assert weave_captions(md, ["unused"]) == md


def test_null_captioner_returns_empty_and_satisfies_port() -> None:
    stub = NullImageCaptioner()
    assert stub.caption(b"\x89PNG...", context="anything") == ""
    assert isinstance(stub, ImageCaptioner)  # runtime_checkable Protocol conformance


def test_null_captioner_weave_is_identity_on_holes() -> None:
    # a book run through the stub keeps its holes: the pipeline behaves as before the vision stage
    md = f"{PLACEHOLDER} keep {PLACEHOLDER}"
    stub = NullImageCaptioner()
    captions = [stub.caption(b"", context="") for _ in range(2)]
    assert weave_captions(md, captions) == md


# --- _enrich_figures: figure routing + the alignment contract (caught audit finding #1) --------------


class _FakeImage:
    """Duck-typed PIL image: _caption_figures only calls ``save(buffer, format=...)``."""

    def save(self, buffer: object, **_kwargs: object) -> None:
        buffer.write(b"PNGBYTES")  # type: ignore[attr-defined]


def _picture(layer: str, *, image: object, caption: str = "") -> object:
    """A duck-typed Docling PictureItem: ``content_layer.name`` + ``get_image(doc)`` + ``caption_text(doc)`` +
    a ``prov`` (page_no + a top-left bbox) so the vector path can read a region."""
    return types.SimpleNamespace(
        content_layer=types.SimpleNamespace(name=layer),
        get_image=lambda _doc: image,
        caption_text=lambda _doc: caption,
        prov=[
            types.SimpleNamespace(
                page_no=1, bbox=types.SimpleNamespace(l=0.0, t=0.0, r=100.0, b=100.0)
            )
        ],
    )


def _desc(context: str) -> str:
    """A realistic, NON-degenerate stub caption - long enough to clear is_degenerate_caption's floor, so the
    router keeps it (a short 'desc[x]' would now be rejected as the 7B's fizzle, sujet F/G1)."""
    return f"A test figure described in several words, caption: {context or 'nolegend'}."


class _RecordingCaptioner:
    model_id = "recording"

    def __init__(self) -> None:
        self.contexts: list[str] = []

    def caption(self, _image: bytes, *, context: str = "") -> str:
        self.contexts.append(context)
        return _desc(context)


def _vector_reader(primitives: object) -> object:
    """A stub VectorFigureReader returning fixed primitives (or None) for any region."""
    return types.SimpleNamespace(figure_primitives=lambda _page, _bbox: primitives)


def _hist_primitives() -> FigurePrimitives:
    bars = tuple(
        Bar(cx - 4, 90 - h, cx + 4, 90)
        for cx, h in [(35, 20), (45, 40), (55, 60), (65, 40), (75, 20)]
    )
    ticks = (TextSpan("0", 37, 91, 43, 97), TextSpan("1", 77, 91, 83, 97))  # two aligned x-ticks
    return FigurePrimitives((0.0, 0.0, 100.0, 100.0), bars=bars, texts=ticks)


def test_enrich_figures_skips_furniture_to_keep_alignment() -> None:
    # audit #1: a FURNITURE picture (logo/header) emits NO markdown placeholder, so enriching it would shift
    # every following entry by one. _enrich_figures must skip non-BODY layers to stay aligned.
    cap = _RecordingCaptioner()
    img = _FakeImage()
    doc = types.SimpleNamespace(
        pictures=[
            _picture("FURNITURE", image=img, caption="logo"),
            _picture("BODY", image=img, caption="fig 1"),
            _picture("BODY", image=img, caption=""),
        ]
    )
    # vision only (no vector reader): every BODY figure falls to the VLM caption path
    assert _enrich_figures(_body_pictures(doc), None, cap, doc=doc) == [
        (MARK, _desc("fig 1")),
        (MARK, _desc("")),
    ]
    assert cap.contexts == ["fig 1", ""]  # the captioner never saw the furniture image


def test_enrich_figures_fail_open_per_figure() -> None:
    # D85: a raising get_image OR a None image degrades to None (kept as a hole), never aborts the book
    cap = _RecordingCaptioner()

    def _boom(_doc: object) -> object:
        raise RuntimeError("corrupt image")

    raising = types.SimpleNamespace(
        content_layer=types.SimpleNamespace(name="BODY"),
        get_image=_boom,
        caption_text=lambda _doc: "",
        prov=[],
    )
    none_image = _picture("BODY", image=None, caption="")
    assert _enrich_figures([raising, none_image], None, cap, doc=None) == [None, None]


def test_enrich_prefers_vector_extraction_and_never_calls_the_vlm() -> None:
    # sujet E: a VECTOR figure is data-extracted locally; the slow VLM is NOT spent on it
    cap = _RecordingCaptioner()
    doc = types.SimpleNamespace(pictures=[_picture("BODY", image=_FakeImage(), caption="fig")])
    out = _enrich_figures(_body_pictures(doc), _vector_reader(_hist_primitives()), cap, doc=doc)
    assert len(out) == 1 and out[0] is not None
    mark, text = out[0]
    assert mark == FIGURE_DATA_MARK and _KIND_HISTOGRAM in text and "X axis" in text
    assert cap.contexts == []  # extraction won - the VLM was never asked


def test_enrich_falls_back_to_vlm_on_a_raster_figure() -> None:
    # a genuinely RASTER figure (an image covers the region) routes to the VLM caption (sujet 2 fallback)
    cap = _RecordingCaptioner()
    raster = FigurePrimitives((0.0, 0.0, 100.0, 100.0), raster_coverage=0.9)
    doc = types.SimpleNamespace(pictures=[_picture("BODY", image=_FakeImage(), caption="chart")])
    assert _enrich_figures(_body_pictures(doc), _vector_reader(raster), cap, doc=doc) == [
        (MARK, _desc("chart"))
    ]
    assert cap.contexts == ["chart"]  # the VLM WAS asked


def test_enrich_falls_back_to_vlm_when_extraction_is_empty() -> None:
    # a vector region the extractor cannot read (no axes/annotations/profile) -> "" -> VLM fallback
    cap = _RecordingCaptioner()
    barren = FigurePrimitives((0.0, 0.0, 100.0, 100.0), segments=(Segment(0, 0, 50, 50),) * 10)
    doc = types.SimpleNamespace(pictures=[_picture("BODY", image=_FakeImage(), caption="x")])
    assert _enrich_figures(_body_pictures(doc), _vector_reader(barren), cap, doc=doc) == [
        (MARK, _desc("x"))
    ]


# --- niveau 3 (sujet G): the frontier is the LAST resort, only when both locals fail ----------------


class _DegenerateCaptioner:
    """A local VLM that FIZZLES - returns the 7B's "La" degenerate caption on every figure (sujet G1). Counts
    its calls so a test can prove the frontier is reached only AFTER the local was actually asked and failed."""

    model_id = "fizzle-7b"

    def __init__(self) -> None:
        self.calls = 0

    def caption(self, _image: bytes, *, context: str = "") -> str:
        self.calls += 1
        return "La"  # degenerate - is_degenerate_caption rejects it, so the router moves on


def test_enrich_routes_to_the_frontier_only_when_the_local_vlm_fizzles() -> None:
    # niveau 3: the local 7B returns a DEGENERATE "La" -> the frontier is asked, and its caption is marked
    # FIGURE_CLOUD_MARK (distinct from the local mark). Both were asked, local FIRST (cost order).
    local = _DegenerateCaptioner()
    cloud = _RecordingCaptioner()
    doc = types.SimpleNamespace(pictures=[_picture("BODY", image=_FakeImage(), caption="abstract")])
    assert _enrich_figures(_body_pictures(doc), None, local, cloud, doc=doc) == [
        (FIGURE_CLOUD_MARK, _desc("abstract"))
    ]
    assert local.calls == 1 and cloud.contexts == ["abstract"]  # local tried, then the frontier


def test_enrich_never_reaches_the_frontier_when_the_local_succeeds() -> None:
    # cost + minimisation: a good LOCAL caption wins; the frontier egress is NEVER spent on it.
    local = _RecordingCaptioner()  # returns a good, non-degenerate _desc
    cloud = _RecordingCaptioner()
    doc = types.SimpleNamespace(pictures=[_picture("BODY", image=_FakeImage(), caption="fig")])
    assert _enrich_figures(_body_pictures(doc), None, local, cloud, doc=doc) == [
        (MARK, _desc("fig"))
    ]
    assert cloud.contexts == []  # the frontier was never asked - the local handled it


def test_enrich_reaches_the_frontier_after_vector_and_vlm_both_fail() -> None:
    # the full ladder (sujet E -> 2 -> G): a raster figure the vector reader can't read + a fizzled local
    # caption -> the frontier, marked cloud. Vector never yields, the 7B fizzles, the frontier describes.
    local = _DegenerateCaptioner()
    cloud = _RecordingCaptioner()
    raster = FigurePrimitives((0.0, 0.0, 100.0, 100.0), raster_coverage=0.9)
    doc = types.SimpleNamespace(pictures=[_picture("BODY", image=_FakeImage(), caption="chart")])
    assert _enrich_figures(_body_pictures(doc), _vector_reader(raster), local, cloud, doc=doc) == [
        (FIGURE_CLOUD_MARK, _desc("chart"))
    ]
    assert local.calls == 1 and cloud.contexts == ["chart"]


def test_a_degenerate_frontier_reply_still_leaves_the_hole() -> None:
    # symmetry with the 7B (fail-open, D85): a frontier reply that is empty/too short is not woven - the hole
    # stays rather than a useless line. Here both the local AND the frontier fizzle -> None (a kept hole).
    doc = types.SimpleNamespace(pictures=[_picture("BODY", image=_FakeImage(), caption="x")])
    assert _enrich_figures(
        _body_pictures(doc), None, _DegenerateCaptioner(), _DegenerateCaptioner(), doc=doc
    ) == [None]


def test_a_frontier_captioner_alone_can_fill_a_hole() -> None:
    # niveau 3 works even with NO local VLM wired (cloud only): a hole the vector reader can't read goes
    # straight to the frontier. (In the real run the local is on; this pins the seam is independent.)
    cloud = _RecordingCaptioner()
    doc = types.SimpleNamespace(pictures=[_picture("BODY", image=_FakeImage(), caption="c")])
    assert _enrich_figures(_body_pictures(doc), None, None, cloud, doc=doc) == [
        (FIGURE_CLOUD_MARK, _desc("c"))
    ]


def test_weave_caption_is_zero_trust_one_line() -> None:
    # D100: model text can only ADD a single blockquote line - no newline breakout, no regex backref (\1)
    out = weave_captions(PLACEHOLDER, ["evil \\1 line\n\n# Injected Heading\n---"])
    assert out == r"> **[Figure described by a model]** evil \1 line # Injected Heading ---"
    assert "\n" not in out


def test_first_n_caps_the_vlm_calls_then_holes() -> None:
    # the pilot's fast-eyeball cap: the local VLM runs at most N times; further figures fall back to "" (holes)
    from mnemosyne.runtime.caption_pilot import _FirstN

    inner = _RecordingCaptioner()
    capped = _FirstN(inner, 2)
    assert isinstance(capped, ImageCaptioner)  # still a valid captioner
    assert capped.model_id == "recording"  # identity is forwarded (provenance stays truthful)
    assert capped.caption(b"a", context="x") == _desc("x")
    assert capped.caption(b"b", context="y") == _desc("y")
    assert (
        capped.caption(b"c", context="z") == ""
    )  # beyond N -> empty caption, weave keeps the hole
    assert inner.contexts == ["x", "y"]  # the inner VLM is never called a 3rd time


def test_vision_switch_off_by_default_returns_none(monkeypatch) -> None:
    # opt-in OFF (default) => None => connect_docling(captioner=None) is EXACTLY the pre-vision reader (D126)
    monkeypatch.delenv("MNEMOSYNE_VISION", raising=False)
    assert vision_captioner_if_enabled() is None


def test_vision_switch_on_wires_the_local_captioner(monkeypatch) -> None:
    # opt-in ON => builds the local captioner via the sole-importer adapter (mocked here so no brick needed)
    monkeypatch.setenv("MNEMOSYNE_VISION", "1")
    sentinel = object()
    monkeypatch.setattr("mnemosyne.ingest.caption_mlx.connect_mlx_vlm", lambda: sentinel)
    assert vision_captioner_if_enabled() is sentinel


def test_figures_switch_off_by_default_returns_none(monkeypatch) -> None:
    # opt-in OFF (default) => None => connect_docling(vector_reader_factory=None) is EXACTLY the pre-extraction
    # reader (zero regression, D126) - the twin of the vision switch (sujet E / audit mineur 2)
    from mnemosyne.ingest import vector_reader_factory_if_enabled

    monkeypatch.delenv("MNEMOSYNE_FIGURES", raising=False)
    assert vector_reader_factory_if_enabled() is None


def test_figures_switch_on_wires_the_pymupdf_reader_factory(monkeypatch) -> None:
    # opt-in ON => returns the PyMuPDF reader FACTORY via the sole-importer adapter (import-safe, no brick)
    from mnemosyne.ingest import connect_pymupdf_reader, vector_reader_factory_if_enabled

    monkeypatch.setenv("MNEMOSYNE_FIGURES", "1")
    assert vector_reader_factory_if_enabled() is connect_pymupdf_reader


def test_clean_caption_strips_stray_tokens_and_collapses() -> None:
    # pilot 1: a 4-bit VLM can leak chat special-tokens into the text - they must never reach the corpus
    from mnemosyne.ingest.caption_mlx import _clean_caption

    assert _clean_caption("  A graph <|endoftext|> in\n\ncurves  ") == "A graph in curves"
    assert _clean_caption("<|im_start|>vide<|im_end|>") == "vide"
    assert _clean_caption("") == ""  # empty stays empty (fail-open feeds the weave, keeps the hole)


# --- weave_enrichments: the ONE insertion home carries BOTH figure paths (sujet E) -------------------

DATA_MARK = FIGURE_DATA_MARK


def test_weave_enrichments_marks_each_path_and_keeps_document_order() -> None:
    md = f"{PLACEHOLDER} a {PLACEHOLDER} b {PLACEHOLDER}"
    out = weave_enrichments(
        md, [(MARK, "vision caption"), None, (DATA_MARK, "Histogramme - axe X ∈ [0, 1]")]
    )
    assert f"> {MARK} vision caption" in out  # the sujet-2 path, marked
    assert f"> {DATA_MARK} Histogramme - axe X ∈ [0, 1]" in out  # the sujet-E path, marked
    assert out.count(PLACEHOLDER) == 1  # the None entry left its hole (fail-open)
    assert out.index("vision caption") < out.index("Histogramme")  # document order preserved


def test_weave_enrichments_collapses_to_one_line() -> None:
    # the verbatim-floor mask is line-scoped, so a read-out is collapsed to one line (C2/E)
    out = weave_enrichments(PLACEHOLDER, [(DATA_MARK, "line\n\ntwo")])
    assert out == f"> {DATA_MARK} line two" and "\n" not in out


def test_weave_enrichments_empty_text_or_mark_keeps_the_hole() -> None:
    assert (
        weave_enrichments(PLACEHOLDER, [(DATA_MARK, "   ")]) == PLACEHOLDER
    )  # empty text => hole (D85)
    assert weave_enrichments(PLACEHOLDER, [("", "text")]) == PLACEHOLDER  # empty mark => hole
