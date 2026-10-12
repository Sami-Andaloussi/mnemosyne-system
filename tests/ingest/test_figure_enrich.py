"""Incremental figure enrichment (sujet F) - brick-free tests for the in-place enricher.

Producer ≠ verifier (D75): an isolated Opus audit checks this independently. These tests pin the pure
alignment+stats+splice (:func:`enrich_outcome`) and the campaign driver (:func:`enrich_figures_campaign`)
with NO Docling / PyMuPDF / VLM installed (D126) - a fake :class:`FigureEnricher` drives the walk. The two
guarantees under test: FAIL-CLOSED alignment (a hole count ≠ BODY-picture count splices NOTHING) and
NON-DESTRUCTIVE rewrite (the original ``.md`` is backed up once before it is changed).
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path

from mnemosyne.ingest import (
    BookEnrichResult,
    CampaignReport,
    count_image_holes,
    enrich_figures_campaign,
    enrich_outcome,
)
from mnemosyne.ports.figure_enrich import FigureEnrichOutcome, FigureEnrichStats
from mnemosyne.production import keep_verbatim
from mnemosyne.provenance import (
    FIGURE_CAPTION_MARK,
    FIGURE_CLOUD_MARK,
    FIGURE_DATA_MARK,
    FIGURE_IMAGE_MARK,
)

PLACEHOLDER = "<!-- image -->"


# --------------------------------------------------------------------------- enrich_outcome (pure core)


def test_aligned_counts_vector_vlm_and_remaining() -> None:
    md = f"a\n{PLACEHOLDER}\nb\n{PLACEHOLDER}\nc\n{PLACEHOLDER}\nd"
    enr = [(FIGURE_DATA_MARK, "bars 10 20"), None, (FIGURE_CAPTION_MARK, "a diagram")]
    out = enrich_outcome(md, enr)
    assert out.stats.aligned
    assert out.stats.filled_vector == 1
    assert out.stats.filled_vlm == 1
    assert out.stats.remaining_holes == 1  # the None keeps its hole (fail-open, D85)
    assert out.stats.filled == 2
    assert out.changed
    assert out.markdown.count(PLACEHOLDER) == 1  # only the un-enriched hole survives


def test_aligned_counts_the_frontier_apart_from_the_local() -> None:
    # niveau 3 (sujet G): a FIGURE_CLOUD_MARK hole IS filled, but counted APART (filled_cloud) so the
    # diagnostic separates what the LOCAL reached from what NEEDED the cloud - and it is NOT left as remaining.
    md = f"a\n{PLACEHOLDER}\nb\n{PLACEHOLDER}\nc\n{PLACEHOLDER}\nd\n{PLACEHOLDER}\ne"
    enr = [
        (FIGURE_DATA_MARK, "bars 10 20"),
        (FIGURE_CAPTION_MARK, "a local diagram"),
        (FIGURE_CLOUD_MARK, "a frontier reading of an abstract chart"),
        None,
    ]
    out = enrich_outcome(md, enr)
    assert (
        out.stats.filled_vector == 1 and out.stats.filled_vlm == 1 and out.stats.filled_cloud == 1
    )
    assert out.stats.filled == 3  # all three paths count as filled
    assert (
        out.stats.remaining_holes == 1
    )  # only the None hole remains - the cloud one is NOT "remaining"


def test_all_none_is_a_noop() -> None:
    # every figure fail-opened => nothing spliced, byte-for-byte unchanged (D85)
    md = f"x {PLACEHOLDER} y {PLACEHOLDER} z"
    out = enrich_outcome(md, [None, None])
    assert out.stats.aligned
    assert not out.changed
    assert out.markdown == md
    assert out.stats.remaining_holes == 2


def test_misaligned_more_pictures_fails_closed() -> None:
    # 1 hole, 3 BODY pictures => desynced (an OCR pass changed the .md): splice NOTHING (invariant 1)
    md = f"only\n{PLACEHOLDER}\none"
    enr = [(FIGURE_DATA_MARK, "a"), (FIGURE_DATA_MARK, "b"), (FIGURE_DATA_MARK, "c")]
    out = enrich_outcome(md, enr)
    assert not out.stats.aligned
    assert not out.changed
    assert out.markdown == md
    assert out.stats.remaining_holes == 1  # the hole is untouched, not counted as filled


def test_misaligned_fewer_pictures_fails_closed() -> None:
    md = f"{PLACEHOLDER} {PLACEHOLDER} {PLACEHOLDER}"
    out = enrich_outcome(md, [(FIGURE_DATA_MARK, "only one")])
    assert not out.stats.aligned
    assert not out.changed
    assert out.markdown == md


def test_zero_holes_zero_pictures_is_aligned_noop() -> None:
    md = "clean prose, no figures"
    out = enrich_outcome(md, [])
    assert out.stats.aligned
    assert out.stats.holes == 0
    assert not out.changed
    assert out.markdown == md


def test_spliced_readout_is_stripped_from_the_verbatim_floor() -> None:
    # fidelity (invariant 1 / C2-E): a figure read-out carries a mark that keep_verbatim strips from the
    # SOURCE before the substring test, so a passage quoting it is DROPPED - it can never be promoted to the
    # author's P3, even a coordinate-mislocated read-out is inert to the floor. End-to-end through sujet F.
    md = f"chapter\n{PLACEHOLDER}\nend"
    readout = "invented axis 0 to 100"
    out = enrich_outcome(md, [(FIGURE_DATA_MARK, readout)])
    assert out.changed
    assert readout in out.markdown  # it IS in the .md (searchable)
    kept, dropped = keep_verbatim(
        (readout,), out.markdown
    )  # try to promote the read-out as verbatim P3
    assert kept == ()  # refused: the marked line is stripped from source, so nothing matches
    assert dropped == (readout,)


def test_empty_text_enrichment_leaves_hole() -> None:
    # a mark with empty text is treated as a per-figure failure (weave_enrichments contract) => hole stays
    md = f"{PLACEHOLDER}"
    out = enrich_outcome(md, [(FIGURE_DATA_MARK, "   ")])
    assert not out.changed
    assert out.markdown == md
    assert out.stats.filled_vector == 0
    assert out.stats.remaining_holes == 1


# --------------------------------------------------------------------------- campaign driver (fake enricher)


class _FakeEnricher:
    """A brick-free :class:`FigureEnricher` whose per-book behaviour is a supplied function (D126)."""

    def __init__(self, fn: Callable[[str], FigureEnrichOutcome]) -> None:
        self._fn = fn
        self.seen: list[str] = []
        #: The sink the driver handed us per book (arc D) - ``None`` when images are off. Recorded so a
        #: test can assert WHICH sink the campaign chose (real vs dry) instead of trusting the flag.
        self.sinks: list[object] = []

    def enrich_markdown(
        self, existing_md: str, pdf: bytes, *, assets: object = None
    ) -> FigureEnrichOutcome:
        assert isinstance(pdf, bytes) and pdf  # the driver handed us the real PDF bytes
        self.seen.append(existing_md)
        self.sinks.append(assets)
        return self._fn(existing_md)


def _fill(md: str) -> FigureEnrichOutcome:
    """Simulate a successful local pass: every hole filled by vector extraction."""
    n = count_image_holes(md)
    woven = md.replace(PLACEHOLDER, f"> {FIGURE_DATA_MARK} data")
    return FigureEnrichOutcome(
        woven,
        FigureEnrichStats(n, n, aligned=True, filled_vector=n, remaining_holes=0),
        changed=True,
    )


def _noop(md: str) -> FigureEnrichOutcome:
    n = count_image_holes(md)
    return FigureEnrichOutcome(
        md, FigureEnrichStats(n, n, aligned=True, remaining_holes=n), changed=False
    )


def _fill_cloud(md: str) -> FigureEnrichOutcome:
    """Simulate a niveau-3 pass: every hole filled by the FRONTIER (cloud mark)."""
    n = count_image_holes(md)
    woven = md.replace(PLACEHOLDER, f"> {FIGURE_CLOUD_MARK} frontier read-out")
    return FigureEnrichOutcome(
        woven,
        FigureEnrichStats(n, n, aligned=True, filled_cloud=n, remaining_holes=0),
        changed=True,
    )


def _book(root: Path, rel: str, text: str, *, with_pdf: bool = True) -> Path:
    """Write a shelf book: a ``.md`` mirror and (optionally) a sibling ``.pdf``."""
    md = root / rel
    md.parent.mkdir(parents=True, exist_ok=True)
    md.write_text(text, encoding="utf-8")
    if with_pdf:
        md.with_suffix(".pdf").write_bytes(b"%PDF-1.4 fake bytes")
    return md


_SHELF = "Nonfiction/Reference/sample-shelf/books"


def test_campaign_rewrites_and_backs_up_once(tmp_path: Path) -> None:
    original = f"Intro\n{PLACEHOLDER}\nMiddle\n{PLACEHOLDER}\nEnd"
    md = _book(tmp_path, f"{_SHELF}/alpha.md", original)
    report = enrich_figures_campaign(_FakeEnricher(_fill), tmp_path)
    # the .md was rewritten in place, holes filled
    assert PLACEHOLDER not in md.read_text(encoding="utf-8")
    assert f"> {FIGURE_DATA_MARK} data" in md.read_text(encoding="utf-8")
    # non-destructive: the ORIGINAL is preserved beside it, once
    backup = md.with_name(md.name + ".prefig")
    assert backup.exists()
    assert backup.read_text(encoding="utf-8") == original
    assert report.changed_books == 1
    assert report.filled_vector == 2


def test_campaign_tallies_and_reports_the_frontier_fills(tmp_path: Path) -> None:
    # niveau 3 end-to-end: the report aggregates filled_cloud, and the summary surfaces the frontier line +
    # a distinct frontier fill-rate - so operator sees exactly how much left the machine (F7).
    _book(tmp_path, f"{_SHELF}/gamma.md", f"Intro\n{PLACEHOLDER}\nMiddle\n{PLACEHOLDER}\nEnd")
    report = enrich_figures_campaign(_FakeEnricher(_fill_cloud), tmp_path)
    assert report.filled_cloud == 2 and report.filled_vector == 0 and report.remaining_holes == 0
    summary = report.summary()
    assert "cloud (front.)" in summary and "frontier fill rate" in summary


def test_campaign_backup_never_overwritten(tmp_path: Path) -> None:
    md = _book(tmp_path, f"{_SHELF}/beta.md", f"{PLACEHOLDER}")
    backup = md.with_name(md.name + ".prefig")
    backup.write_text("A SACRED EARLIER ORIGINAL", encoding="utf-8")
    enrich_figures_campaign(_FakeEnricher(_fill), tmp_path)
    assert (
        backup.read_text(encoding="utf-8") == "A SACRED EARLIER ORIGINAL"
    )  # first backup wins (D85)


def test_campaign_skips_md_without_pdf(tmp_path: Path) -> None:
    _book(tmp_path, f"{_SHELF}/no_pdf.md", f"{PLACEHOLDER}", with_pdf=False)
    fake = _FakeEnricher(_fill)
    report = enrich_figures_campaign(fake, tmp_path)
    assert fake.seen == []  # never opened (no PDF to read figures from)
    assert report.books == 0


def test_campaign_skips_md_without_holes(tmp_path: Path) -> None:
    _book(tmp_path, f"{_SHELF}/clean.md", "prose with no figures at all")
    fake = _FakeEnricher(_fill)
    report = enrich_figures_campaign(fake, tmp_path)
    assert fake.seen == []
    assert report.books == 0


def test_campaign_unchanged_book_not_rewritten_no_backup(tmp_path: Path) -> None:
    original = f"kept {PLACEHOLDER} verbatim"
    md = _book(tmp_path, f"{_SHELF}/gamma.md", original)
    report = enrich_figures_campaign(_FakeEnricher(_noop), tmp_path)
    assert md.read_text(encoding="utf-8") == original  # untouched
    assert not md.with_name(md.name + ".prefig").exists()  # no backup when nothing changed
    assert report.books == 1
    assert report.changed_books == 0


def test_campaign_isolates_a_raising_enricher(tmp_path: Path) -> None:
    _book(tmp_path, f"{_SHELF}/boom.md", f"{PLACEHOLDER}")
    _book(tmp_path, f"{_SHELF}/ok.md", f"{PLACEHOLDER}")

    def fn(md: str) -> FigureEnrichOutcome:
        if "boom" in md:
            raise RuntimeError("simulated Docling explosion")
        return _fill(md)

    # seed the marker so the raising branch can detect its book by content
    (tmp_path / _SHELF / "boom.md").write_text(f"boom {PLACEHOLDER}", encoding="utf-8")
    report = enrich_figures_campaign(_FakeEnricher(fn), tmp_path)
    assert report.books == 2  # both recorded, the campaign did not abort
    assert report.errored_books == 1
    errored = [r for r in report.results if r.stats is None]
    assert errored and "simulated Docling explosion" in errored[0].error


def test_campaign_isolates_write_failure_and_preserves_original(
    tmp_path: Path, monkeypatch: object
) -> None:
    # non-destructive (invariant 2): if the atomic write raises (disk full), the ORIGINAL stays intact,
    # the book is recorded errored, and the campaign continues to the healthy book (invariant 3 / D140).
    import mnemosyne.ingest.figure_enrich as fe

    original = f"kept {PLACEHOLDER} safe and whole"
    boom = _book(tmp_path, f"{_SHELF}/boom.md", original)
    ok = _book(tmp_path, f"{_SHELF}/ok.md", f"other {PLACEHOLDER}")
    real = fe._atomic_write

    def flaky(path: Path, text: str) -> None:
        if "boom" in path.name:
            raise OSError("simulated disk full")
        real(path, text)

    monkeypatch.setattr(fe, "_atomic_write", flaky)
    report = enrich_figures_campaign(_FakeEnricher(_fill), tmp_path)
    assert (
        boom.read_text(encoding="utf-8") == original
    )  # NEVER truncated, backup never clobbered it
    assert not boom.with_name(
        boom.name + ".prefig"
    ).exists()  # backup write also failed => no half-state
    assert PLACEHOLDER not in ok.read_text(encoding="utf-8")  # the healthy book WAS still enriched
    errored = [r for r in report.results if r.stats is None]
    assert (
        len(errored) == 1 and "boom" in errored[0].rel and "simulated disk full" in errored[0].error
    )


def test_campaign_survives_a_raising_progress_hook(tmp_path: Path) -> None:
    _book(tmp_path, f"{_SHELF}/hook.md", f"{PLACEHOLDER}")

    def boom_hook(_result: BookEnrichResult) -> None:
        raise RuntimeError("progress hook exploded")

    report = enrich_figures_campaign(_FakeEnricher(_fill), tmp_path, on_book=boom_hook)
    assert report.books == 1  # a misbehaving progress hook never breaks the campaign


def test_campaign_limit_caps_processing(tmp_path: Path) -> None:
    for i in range(5):
        _book(tmp_path, f"{_SHELF}/book{i}.md", f"{PLACEHOLDER}")
    fake = _FakeEnricher(_fill)
    report = enrich_figures_campaign(fake, tmp_path, limit=2)
    assert len(fake.seen) == 2
    assert report.books == 2


def test_campaign_dry_run_measures_without_writing(tmp_path: Path) -> None:
    original = f"Intro\n{PLACEHOLDER}\nEnd"
    md = _book(tmp_path, f"{_SHELF}/delta.md", original)
    report = enrich_figures_campaign(_FakeEnricher(_fill), tmp_path, dry_run=True)
    # measured as changed, but the file on disk is UNTOUCHED and no backup written (the operator's diagnostic pass)
    assert md.read_text(encoding="utf-8") == original
    assert not md.with_name(md.name + ".prefig").exists()
    assert report.changed_books == 1  # the stats still say it WOULD change
    assert report.filled_vector == 1


def test_campaign_max_holes_skips_scan_dominant(tmp_path: Path) -> None:
    _book(tmp_path, f"{_SHELF}/small.md", f"{PLACEHOLDER} {PLACEHOLDER}")  # 2 holes
    _book(tmp_path, f"{_SHELF}/scan.md", f"{PLACEHOLDER} " * 300)  # 300 holes - a scan
    fake = _FakeEnricher(_fill)
    report = enrich_figures_campaign(fake, tmp_path, max_holes=50)
    assert report.books == 1  # only the small one processed
    assert report.skipped_large == 1
    assert len(fake.seen) == 1
    assert "scan-heavy" in report.summary()


def test_campaign_select_filters(tmp_path: Path) -> None:
    _book(tmp_path, f"{_SHELF}/keep.md", f"{PLACEHOLDER}")
    _book(tmp_path, f"{_SHELF}/drop.md", f"{PLACEHOLDER}")
    fake = _FakeEnricher(_fill)
    report = enrich_figures_campaign(fake, tmp_path, select=lambda book: "keep" in book.mirror.name)
    assert report.books == 1
    assert "keep.md" in report.results[0].rel


def test_campaign_skips_readme_and_intake(tmp_path: Path) -> None:
    # is_non_corpus (reused from discover_books): shelf documentation is never taken for a book
    _book(tmp_path, f"{_SHELF}/README.md", f"{PLACEHOLDER}")
    _book(tmp_path, "_intake/dropped.md", f"{PLACEHOLDER}")
    fake = _FakeEnricher(_fill)
    report = enrich_figures_campaign(fake, tmp_path)
    assert report.books == 0
    assert fake.seen == []


# --------------------------------------------------------------------------- CampaignReport aggregation


def test_run_figures_enrichment_injects_a_fake_enricher(tmp_path: Path) -> None:
    # the composition root (runtime) stays testable brick-free by injecting the enricher (library_run pattern)
    from mnemosyne.runtime.figures_enrich_run import run_figures_enrichment

    _book(tmp_path, f"{_SHELF}/root.md", f"{PLACEHOLDER}")
    report = run_figures_enrichment(
        raw_root=tmp_path, enricher=_FakeEnricher(_fill), progress=False
    )
    assert report.changed_books == 1
    assert report.filled_vector == 1


def test_run_figures_enrichment_enters_and_exits_the_gate_around_the_campaign(
    tmp_path: Path,
) -> None:
    # Q1 wiring (zero-regression seam): the gate wraps the enricher cold-start + the campaign walk,
    # mirroring library_run's same seam - a caller's guarded_heavy_run is genuinely entered/exited.
    from mnemosyne.runtime.figures_enrich_run import run_figures_enrichment

    _book(tmp_path, f"{_SHELF}/root.md", f"{PLACEHOLDER}")
    events: list[str] = []

    @contextmanager
    def recording_gate() -> Iterator[None]:
        events.append("enter")
        try:
            yield
        finally:
            events.append("exit")

    report = run_figures_enrichment(
        raw_root=tmp_path,
        enricher=_FakeEnricher(_fill),
        progress=False,
        gate=recording_gate(),
    )
    assert events == ["enter", "exit"]
    assert report.changed_books == 1  # the gate does not break the campaign


def test_run_figures_enrichment_default_gate_is_an_unchanged_noop(tmp_path: Path) -> None:
    # backward-compatible: calling without gate= behaves exactly as before (nullcontext, no coordination)
    from mnemosyne.runtime.figures_enrich_run import run_figures_enrichment

    _book(tmp_path, f"{_SHELF}/root.md", f"{PLACEHOLDER}")
    report = run_figures_enrichment(
        raw_root=tmp_path, enricher=_FakeEnricher(_fill), progress=False
    )
    assert report.changed_books == 1


def test_report_summary_excludes_misaligned_from_remaining() -> None:
    aligned = BookEnrichResult(
        "a.md",
        True,
        FigureEnrichStats(10, 10, aligned=True, filled_vector=6, filled_vlm=1, remaining_holes=3),
    )
    misaligned = BookEnrichResult(
        "b.md", False, FigureEnrichStats(40, 41, aligned=False, remaining_holes=40)
    )
    errored = BookEnrichResult("c.md", False, None, error="boom")
    report = CampaignReport((aligned, misaligned, errored))
    assert report.books == 3
    assert report.filled_vector == 6
    assert report.filled_vlm == 1
    assert report.misaligned_books == 1
    assert report.errored_books == 1
    # remaining counts ONLY aligned books - the 40 misaligned holes were never attempted (fail-closed)
    assert report.remaining_holes == 3
    text = report.summary()
    assert "misaligned" in text
    assert "40.0%" not in text  # rate is over aligned holes (10), not the misaligned book's 40


# --- arc D: WHICH sink the campaign picks (the wiring that nothing held) ------------------------------


def test_campaign_wires_no_sink_when_images_are_off(tmp_path: Path) -> None:
    # polarity: without IMAGES=1, arc D is entirely absent from the path (zero regression)
    _book(tmp_path, f"{_SHELF}/alpha.md", f"Intro\n{PLACEHOLDER}\nEnd")
    enricher = _FakeEnricher(_fill)
    enrich_figures_campaign(enricher, tmp_path)
    assert enricher.sinks == [None]


def test_campaign_wires_the_REAL_sink_when_images_are_on(tmp_path: Path) -> None:
    from mnemosyne.ingest.figure_image import DirectoryImageSink

    md = _book(tmp_path, f"{_SHELF}/alpha.md", f"Intro\n{PLACEHOLDER}\nEnd")
    enricher = _FakeEnricher(_fill)
    enrich_figures_campaign(enricher, tmp_path, images=True)
    assert isinstance(enricher.sinks[0], DirectoryImageSink)
    assert enricher.sinks[0].md_path == md  # and it targets THIS book, not another one


def test_a_dry_run_wires_the_DRY_sink_never_the_real_one(tmp_path: Path) -> None:
    # without this test, wiring the dry-run to the real sink would go unnoticed: the preview would
    # write megabytes of PNG to the operator's disk while claiming to touch nothing.
    from mnemosyne.ingest.figure_image import DirectoryImageSink, DryRunImageSink

    _book(tmp_path, f"{_SHELF}/alpha.md", f"Intro\n{PLACEHOLDER}\nEnd")
    enricher = _FakeEnricher(_fill)
    enrich_figures_campaign(enricher, tmp_path, images=True, dry_run=True)
    assert isinstance(enricher.sinks[0], DryRunImageSink)
    assert not isinstance(enricher.sinks[0], DirectoryImageSink)


def test_only_narrows_the_pool_to_the_named_book(tmp_path: Path) -> None:
    # `--only` exists to PROVE on one book. If it is ignored, the proof gesture processes the whole
    # corpus - the exact opposite of its intent, and on the operator's own machine.
    from mnemosyne.runtime.figures_enrich_run import run_figures_enrichment

    _book(tmp_path, f"{_SHELF}/alpha.md", f"a\n{PLACEHOLDER}\n")
    _book(tmp_path, f"{_SHELF}/beta.md", f"b\n{PLACEHOLDER}\n")
    enricher = _FakeEnricher(_fill)
    report = run_figures_enrichment(
        raw_root=tmp_path, enricher=enricher, only="beta", dry_run=True, progress=False
    )
    assert [r.rel.name if hasattr(r.rel, "name") else str(r.rel) for r in report.results] == [
        f"{_SHELF}/beta.md".split("/")[-1]
    ] or all("beta" in str(r.rel) for r in report.results)
    assert report.books == 1


# ------------------------------------ THE RESIDUE OF A REFUSAL
#
# A refused enrichment can still leave generated figure files on disk because the adapter writes
# pixels before the pure core decides whether to weave them into the document. The refusal is valid;
# its report must still name those files.


def test_un_livre_REFUSE_publie_les_images_qu_il_a_QUAND_MEME_ecrites() -> None:
    md = f"a\n{PLACEHOLDER}\nb"  # 1 hole
    enr = [  # 3 figures: misaligned, so nothing will be woven
        (FIGURE_IMAGE_MARK, "![f1](x.figures/001.png)"),
        (FIGURE_IMAGE_MARK, "![f2](x.figures/002.png)"),
        (FIGURE_DATA_MARK, "bars 10 20"),
    ]
    out = enrich_outcome(md, enr)
    assert not out.stats.aligned
    assert not out.changed
    assert out.markdown == md, "fail-closed: the markdown does NOT move"
    assert out.stats.assets_written == 2, "the 2 PNGs written must be PUBLISHED"
    assert out.stats.filled_image == 0, "written to disk is NOT woven"


def test_un_livre_ALIGNE_compte_ses_actifs_ET_ses_trous_combles() -> None:
    md = f"a\n{PLACEHOLDER}\nb\n{PLACEHOLDER}\nc"
    enr = [(FIGURE_IMAGE_MARK, "![f1](x.figures/001.png)"), (FIGURE_DATA_MARK, "bars")]
    out = enrich_outcome(md, enr)
    assert out.stats.aligned
    assert out.stats.assets_written == 1 and out.stats.filled_image == 1


def test_sans_sink_aucun_actif_n_est_declare() -> None:
    """THE INNOCENT: a campaign WITHOUT `IMAGES=1` must not invent any residue."""
    md = f"a\n{PLACEHOLDER}\nb"
    for enr in ([(FIGURE_DATA_MARK, "bars")], [(FIGURE_CAPTION_MARK, "a diagram")], [None]):
        assert enrich_outcome(md, enr).stats.assets_written == 0


def test_un_sink_qui_ECHOUE_ne_compte_pas_un_actif_qui_n_existe_pas() -> None:
    """The sink returns "" on OSError, so the payload is empty: nothing was written."""
    md = f"a\n{PLACEHOLDER}\nb"
    assert enrich_outcome(md, [(FIGURE_IMAGE_MARK, "")]).stats.assets_written == 0


def test_le_rapport_de_campagne_AGREGE_le_residu_et_NOMME_le_geste_de_Operator() -> None:
    from mnemosyne.ingest.figure_enrich import BookEnrichResult, CampaignReport

    refuse = FigureEnrichStats(holes=1, body_pictures=3, aligned=False, assets_written=83)
    aligne = FigureEnrichStats(
        holes=2, body_pictures=2, aligned=True, filled_image=2, assets_written=2
    )
    rapport = CampaignReport(
        results=(
            BookEnrichResult(rel="a.md", changed=False, stats=refuse),
            BookEnrichResult(rel="b.md", changed=True, stats=aligne),
        )
    )
    assert rapport.orphan_assets == 83, "ONLY refused books leave orphans behind"
    dit = rapport.summary()
    assert "83" in dit and "REFUS" in dit.upper()
    assert "operator's gesture" in dit, "the residue is THEIR gesture (D74), not mine"


def test_le_rapport_reste_MUET_quand_aucun_livre_n_a_ete_refuse() -> None:
    """A permanent refusal line would become noise that stops being read."""
    from mnemosyne.ingest.figure_enrich import BookEnrichResult, CampaignReport

    aligne = FigureEnrichStats(
        holes=1, body_pictures=1, aligned=True, filled_image=1, assets_written=1
    )
    rapport = CampaignReport(results=(BookEnrichResult(rel="b.md", changed=True, stats=aligne),))
    assert rapport.orphan_assets == 0
    assert "operator's gesture" not in rapport.summary()
