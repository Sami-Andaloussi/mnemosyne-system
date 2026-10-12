"""Extracted-figure assets (arc D) - the figure ITSELF lands in the hole, and the preview does not lie.

Brick-free (D126): no Docling, no PyMuPDF, no model - the payload composition and the sinks are pure Python
over a tmp_path. What these pin, in order of what would hurt most if it broke:

* the DRY sink returns the SAME link the real sink writes (a preview that reports a different tally than the
  run it previews is worse than no preview);
* the sink is IDEMPOTENT (a re-run over 26 315 figures must not churn the disk) and FAIL-OPEN (a full disk
  degrades one figure, never aborts a 244-book campaign);
* the payload keeps the vector read-out ALONGSIDE the image - a PNG is invisible to ``make search``, so
  dropping the read-out would silently amputate retrieval to gain a picture.
"""

from __future__ import annotations

import types
from pathlib import Path

from mnemosyne.ingest.figure_image import (
    DirectoryImageSink,
    DryRunImageSink,
    figure_asset_name,
    image_payload,
)
from mnemosyne.ingest.source_docling import _body_pictures, _enrich_figures
from mnemosyne.provenance import FIGURE_DATA_MARK, FIGURE_IMAGE_MARK

_PNG = b"\x89PNG\r\n\x1a\nfake-but-non-empty"


# --- the payload (pure) ----------------------------------------------------------------------------


def test_payload_carries_the_image_and_the_readout_on_one_line() -> None:
    out = image_payload("book.figures/fig-003.png", 3, "Curve(s) - X axis ∈ [0, 1]")
    assert out.startswith(
        "![Figure 4](book.figures/fig-003.png)"
    )  # alt is 1-based: what a reader counts
    assert (
        "Curve(s) - X axis ∈ [0, 1]" in out
    )  # the read-out SURVIVES: the index needs it, the eye doesn't


def test_payload_without_a_readout_is_just_the_image() -> None:
    assert image_payload("b.figures/fig-000.png", 0) == "![Figure 1](b.figures/fig-000.png)"


def test_payload_collapses_a_multiline_readout() -> None:
    # the weave writes ONE line ("> mark payload"); a newline would break the blockquote and orphan the tail
    out = image_payload("b.figures/fig-000.png", 0, "Histogram\n  profile: 1, 2")
    assert "\n" not in out and "Histogram profile: 1, 2" in out


def test_payload_percent_encodes_spaces_and_accents_in_the_path() -> None:
    # book stems carry spaces, accents and unicode dashes; a raw space breaks the link in every renderer
    out = image_payload("A Non-Random Walk - Lo.figures/fig-000.png", 0)
    assert " " not in out.split("](", 1)[1]
    assert "%20" in out and "/fig-000.png" in out  # the SLASH stays a separator, not %2F


def test_payload_is_empty_when_nothing_was_written() -> None:
    # fail-open (D85): no link => no payload => the caller falls back to the text paths or keeps the hole
    assert image_payload("", 3, "a read-out") == ""


def test_asset_names_sort_in_figure_order() -> None:
    assert figure_asset_name(3) == "fig-003.png"
    assert sorted([figure_asset_name(10), figure_asset_name(2)]) == ["fig-002.png", "fig-010.png"]


# --- the real sink ---------------------------------------------------------------------------------


def test_sink_writes_the_png_and_returns_the_md_relative_link(tmp_path: Path) -> None:
    md = tmp_path / "Some Book - 1999.md"
    md.write_text("x", encoding="utf-8")
    link = DirectoryImageSink(md).save(2, _PNG)
    assert link == "Some Book - 1999.figures/fig-002.png"
    assert (md.parent / link).read_bytes() == _PNG  # the link RESOLVES from the .md's directory


def test_sink_is_idempotent_and_does_not_rewrite_identical_bytes(tmp_path: Path) -> None:
    md = tmp_path / "b.md"
    md.write_text("x", encoding="utf-8")
    sink = DirectoryImageSink(md)
    assert sink.save(0, _PNG) == "b.figures/fig-000.png"
    target = md.parent / "b.figures" / "fig-000.png"
    stamp = target.stat().st_mtime_ns
    assert sink.save(0, _PNG) == "b.figures/fig-000.png"  # same link...
    assert (
        target.stat().st_mtime_ns == stamp
    )  # ...and the file was NOT touched (no disk churn on a re-run)
    assert list(target.parent.iterdir()) == [target]  # no temp sibling left behind


def test_sink_updates_the_asset_when_the_bytes_differ(tmp_path: Path) -> None:
    # idempotence must not become staleness: a re-render with different pixels REPLACES the old asset
    md = tmp_path / "b.md"
    md.write_text("x", encoding="utf-8")
    sink = DirectoryImageSink(md)
    sink.save(0, _PNG)
    sink.save(0, _PNG + b"different")
    assert (md.parent / "b.figures" / "fig-000.png").read_bytes() == _PNG + b"different"


def test_sink_fails_open_when_the_directory_cannot_be_created(tmp_path: Path) -> None:
    # a FILE where the assets dir should go => mkdir raises; the sink must return "" and let the figure
    # degrade to its text read-out (D85), never propagate and abort a 244-book campaign
    md = tmp_path / "b.md"
    md.write_text("x", encoding="utf-8")
    (tmp_path / "b.figures").write_text("I am a file, not a directory", encoding="utf-8")
    assert DirectoryImageSink(md).save(0, _PNG) == ""


def test_sink_refuses_empty_bytes(tmp_path: Path) -> None:
    # Docling could not render this figure => nothing to keep; writing a 0-byte PNG would show a grey box
    md = tmp_path / "b.md"
    md.write_text("x", encoding="utf-8")
    assert DirectoryImageSink(md).save(0, b"") == ""
    assert not (tmp_path / "b.figures").exists()


# --- the preview must not lie ----------------------------------------------------------------------


def test_dry_sink_returns_exactly_the_link_the_real_sink_writes(tmp_path: Path) -> None:
    # THE test of this file. --dry-run --images exists to preview the real pass; if the dry sink returned a
    # different link (or ""), the preview would take a different branch and report a tally that is NOT what
    # the run produces. Same book, same ordinal, same bytes => byte-identical answers.
    md = tmp_path / "Some Book - 1999.md"
    md.write_text("x", encoding="utf-8")
    for ordinal in (0, 7, 123):
        assert DryRunImageSink(md).save(ordinal, _PNG) == DirectoryImageSink(md).save(ordinal, _PNG)


def test_dry_sink_writes_nothing_at_all(tmp_path: Path) -> None:
    md = tmp_path / "b.md"
    md.write_text("x", encoding="utf-8")
    assert DryRunImageSink(md).save(0, _PNG) == "b.figures/fig-000.png"
    assert not (
        tmp_path / "b.figures"
    ).exists()  # a diagnostic pass touches user's disk with ZERO bytes


def test_dry_sink_reports_an_unrenderable_figure_as_unfilled_too(tmp_path: Path) -> None:
    # symmetry with the real sink on the OTHER branch: a figure Docling cannot render counts as a hole in
    # the preview as well, so the previewed "left as holes" is the number the run will really leave
    md = tmp_path / "b.md"
    md.write_text("x", encoding="utf-8")
    assert DryRunImageSink(md).save(0, b"") == DirectoryImageSink(md).save(0, b"") == ""


# --- the summary is a CENSUS, not a count ----------------------------------------------------------


def test_summary_names_every_refused_book_not_just_how_many() -> None:
    # In a long batch, per-book lines can be far up the scrollback; the named stale-file list is the
    # actionable deliverable. A count alone cannot be acted on and must never be truncated.
    from mnemosyne.ingest.figure_enrich import BookEnrichResult, CampaignReport
    from mnemosyne.ports.figure_enrich import FigureEnrichStats

    refused = tuple(
        BookEnrichResult(
            rel=f"dom/book-{i}.md",
            changed=False,
            stats=FigureEnrichStats(holes=11, body_pictures=35, aligned=False, remaining_holes=11),
        )
        for i in range(7)
    )
    ok = BookEnrichResult(
        rel="dom/aligned.md",
        changed=True,
        stats=FigureEnrichStats(4, 4, aligned=True, filled_image=4),
    )
    out = CampaignReport(results=(ok, *refused)).summary()
    assert "REFUSES par l'alignement (7)" in out
    for i in range(7):
        assert f"dom/book-{i}.md" in out  # ALL of them, never an "and N more"
    assert "11 trous vs   35 figures" in out  # with the two numbers that say WHY it was refused


def test_summary_names_errored_books_too() -> None:
    from mnemosyne.ingest.figure_enrich import BookEnrichResult, CampaignReport

    out = CampaignReport(
        results=(
            BookEnrichResult(rel="dom/broken.md", changed=False, stats=None, error="enrich: boom"),
        )
    ).summary()
    assert "EN ERREUR (1)" in out and "dom/broken.md" in out and "boom" in out


def test_summary_stays_silent_when_nothing_was_refused() -> None:
    from mnemosyne.ingest.figure_enrich import BookEnrichResult, CampaignReport
    from mnemosyne.ports.figure_enrich import FigureEnrichStats

    out = CampaignReport(
        results=(
            BookEnrichResult(
                "dom/a.md", True, FigureEnrichStats(2, 2, aligned=True, filled_image=2)
            ),
        )
    ).summary()
    assert "REFUSES" not in out and "EN ERREUR" not in out  # no empty ceremony on a clean run


# --- THE WIRING (what an isolated audit found held by NOTHING) --------------------------------------
#
# 10 sabotages out of 36 survived my suite, and ALL of them concerned the WIRING, not the PARTS:
# `--images` that wires no sink, `--dry-run` wired to the REAL sink, the splice's ordinal dropped
# to 0 (every figure pointing at fig-000.png), the image no longer outranking the text, the
# vector read-out discarded, `--only` ignored. The parts were proven; nothing proved they were
# WIRED. This is the exact fault that 3b91a45 claimed to have closed - it reopened
# elsewhere, because I had closed it as a single CASE.


class _RecordingSink:
    """A sink that records what it is asked - the ordinal is the question, not the content."""

    def __init__(self, *, fails: bool = False) -> None:
        self.calls: list[tuple[int, int]] = []  # (ordinal, byte size)
        self._fails = fails

    def save(self, ordinal: int, png: bytes) -> str:
        self.calls.append((ordinal, len(png)))
        return "" if self._fails else f"b.figures/{figure_asset_name(ordinal)}"


class _Img:
    def save(self, buffer: object, **_k: object) -> None:
        buffer.write(b"PNGBYTES")  # type: ignore[attr-defined]


def _pic(layer: str = "BODY", *, image: object | None = None) -> object:
    return types.SimpleNamespace(
        content_layer=types.SimpleNamespace(name=layer),
        get_image=lambda _doc: image,
        caption_text=lambda _doc: "",
        prov=[
            types.SimpleNamespace(page_no=1, bbox=types.SimpleNamespace(l=0.0, t=0.0, r=9.0, b=9.0))
        ],
    )


def test_each_figure_gets_ITS_OWN_ordinal_not_a_frozen_one() -> None:
    # the port promises that an asset's name is a VERIFIABLE CLAIM about the hole it fills.
    # Without this test, the ordinal can fall to 0 and all 26,000 figures point at fig-000.png: the
    # .md stays well-formed, the links resolve, and every figure is the wrong one.
    sink = _RecordingSink()
    pictures = [_pic(image=_Img()) for _ in range(4)]
    out = _enrich_figures(pictures, None, None, None, sink, doc=None)
    assert [ordinal for ordinal, _ in sink.calls] == [0, 1, 2, 3]
    assert [e[1].split("fig-")[1][:3] for e in out] == ["000", "001", "002", "003"]


def test_furniture_is_dropped_BEFORE_the_ordinal_is_handed_out() -> None:
    # a counted logo would shift every following figure by one slot - the silent drift
    doc = types.SimpleNamespace(pictures=[_pic("FURNITURE", image=_Img()), _pic(image=_Img())])
    sink = _RecordingSink()
    _enrich_figures(_body_pictures(doc), None, None, None, sink, doc=doc)
    assert [ordinal for ordinal, _ in sink.calls] == [0]  # the ONLY BODY figure is No. 0


def test_the_image_outranks_every_description() -> None:
    out = _enrich_figures([_pic(image=_Img())], None, None, None, _RecordingSink(), doc=None)
    assert out[0][0] == FIGURE_IMAGE_MARK  # never FIGURE_DATA_MARK / CAPTION when the image is there


def test_no_sink_means_the_arc_D_payload_never_appears() -> None:
    # polarity check: without a sink, the behavior is EXACTLY the old one (zero regression)
    out = _enrich_figures([_pic(image=_Img())], None, None, None, None, doc=None)
    assert out == [None]  # no vector reader, no VLM => the hole stays


def test_a_failing_sink_leaves_the_HOLE_and_never_falls_back_to_text() -> None:
    # THE test for D-2. When the sink can no longer write (disk full), falling back to the
    # description would be the worst available outcome: it rewrites what the arc removes, it BURNS
    # the one-shot .prefig backup - so a later corrective run finds no more hole and skips the
    # book - and the tally reports 100% success, 0 errors.
    class _Reader:
        def figure_primitives(self, *_a: object, **_k: object) -> object:
            from mnemosyne.ports.vectorfigure import FigurePrimitives, TextSpan

            return FigurePrimitives(
                bbox=(0.0, 0.0, 100.0, 100.0),
                texts=(TextSpan("0", 1.0, 90.0, 6.0, 96.0), TextSpan("50", 1.0, 50.0, 8.0, 56.0)),
                segments=(),
                bars=(),
                dot_paths=40,
                curve_items=0,
                raster_coverage=0.0,
            )

    reader = _Reader()
    # first, the proof that THIS setup does produce a non-empty vector read-out
    avec_texte = _enrich_figures([_pic(image=_Img())], reader, None, None, None, doc=None)
    assert avec_texte[0] is not None and avec_texte[0][0] == FIGURE_DATA_MARK
    # then, a failing sink: the hole STAYS, the description is NOT written
    out = _enrich_figures(
        [_pic(image=_Img())], reader, None, None, _RecordingSink(fails=True), doc=None
    )
    assert out == [None]


def test_an_unrenderable_figure_still_falls_back_to_text() -> None:
    # symmetry: a missing image (Docling rendered nothing) is NOT a disk problem - the
    # description stays the legitimate fallback, or we would lose what we already knew how to do
    class _Reader:
        def figure_primitives(self, *_a: object, **_k: object) -> object:
            from mnemosyne.ports.vectorfigure import FigurePrimitives, TextSpan

            return FigurePrimitives(
                bbox=(0.0, 0.0, 100.0, 100.0),
                texts=(TextSpan("0", 1.0, 90.0, 6.0, 96.0), TextSpan("50", 1.0, 50.0, 8.0, 56.0)),
                segments=(),
                bars=(),
                dot_paths=40,
                curve_items=0,
                raster_coverage=0.0,
            )

    out = _enrich_figures([_pic(image=None)], _Reader(), None, None, _RecordingSink(), doc=None)
    assert out[0] is not None and out[0][0] == FIGURE_DATA_MARK
