"""Resumable library ingestion (D140 / Étape 3) - the .md-first, unbreakable scale-up driver.

Proves the three guarantees for an unattended batch: .md-first (convert once, reuse cached markdown),
UNBREAKABLE (no single book aborts the batch),
RESUMABLE (a stable manifest skips settled books). Plus the security seam the driver rests on: a book
tagged with its shelf domain is readable ONLY by a bubble that DECLARES that domain (D72 / invariant 4),
so tagging and the policy declaration move in lockstep. Brick-free (D126): a fake SourceReader stands in
for Docling, so the whole pipeline runs with nothing installed.

The shelf is HIERARCHICAL (``<Famille>/<Groupe>/<domain>/<type>/`` - the library reorg): the domain is
derived as the folder just above the ``<type>`` segment (:func:`taxonomy.domain_from_parts`), so the
fixtures place each book at its real taxonomy path via the ``_qt`` / ``_cs`` helpers.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from types import MappingProxyType

from mnemosyne.api import CoreApi, RecallView
from mnemosyne.config import Policy
from mnemosyne.ingest import (
    KNOWLEDGE_BUBBLE,
    BookStatus,
    LibraryManifest,
    OrphanReport,
    OrphanRow,
    detect_orphan_vectors,
    discover_books,
    domains_on_shelf,
    ingest_library,
    purge_orphan_vectors,
    realign_manifest_paths,
)
from mnemosyne.ingest.library import BookRecord
from mnemosyne.ingest.router import QueryKind
from mnemosyne.ports import Bubble, DocId, Domain, Sensitivity, Source
from mnemosyne.runtime import bootstrap
from mnemosyne.runtime.library_run import run_library_ingestion

_FIXED_CLOCK = lambda: datetime(2026, 7, 6, 12, 0, tzinfo=timezone.utc)  # noqa: E731 - a deterministic clock

# A dense, distinctive markdown "book": > 200 non-whitespace chars, high self-cosine for the stub encoder.
_BOOK_MD = "momentum factor equities backtest sharpe drawdown portfolio rebalancing " * 8

# Two real taxonomy shelves (arbo <Famille>/<Groupe>/<domain>/<type>/) - the domain is derived as the dir
# just above <type>, so a fixture placed here tags as its <domain>. See system/config/taxonomy.toml.
_QT = "Finance/Trading/quant-trading/books"  # domain = quant-trading
_CS = "Software/Foundations/computer-science/books"  # domain = computer-science


def _qt(name: str) -> str:
    """A file on the quant-trading shelf (``Finance/Trading/quant-trading/books/<name>``)."""
    return f"{_QT}/{name}"


def _cs(name: str) -> str:
    """A file on the computer-science shelf (``Software/Foundations/computer-science/books/<name>``)."""
    return f"{_CS}/{name}"


class _FakeReader:
    """A stub :class:`SourceReader` (Docling stand-in, D126): canned markdown per source ``ref``, with
    optional raising / non-``str`` returns to exercise the per-book net. Records every call for spying."""

    def __init__(
        self,
        texts: dict[str, str] | None = None,
        *,
        raise_on: frozenset[str] = frozenset(),
        broken_on: frozenset[str] = frozenset(),
        default: str = _BOOK_MD,
    ) -> None:
        self._texts = dict(texts or {})
        self._raise_on = set(raise_on)
        self._broken_on = set(broken_on)
        self._default = default
        self.calls: list[str] = []

    def read(self, source: Source) -> str:
        self.calls.append(source.ref)
        if source.ref in self._raise_on:
            raise RuntimeError(f"reader boom on {source.ref}")
        if source.ref in self._broken_on:
            return None  # type: ignore[return-value]  # a port-contract violation the driver must net
        return self._texts.get(source.ref, self._default)


def _policy(declared: dict[str, frozenset[str]]) -> Policy:
    """A test policy declaring the given ``bubble -> domains`` visibility (D72), else empty/permissive."""
    return Policy(
        profile="test",
        canal_a_auto=frozenset({Sensitivity.PUBLIC}),
        egress_allowlist=frozenset(),
        contracts=(),
        declared_domains=MappingProxyType(
            {Bubble(b): frozenset(Domain(d) for d in ds) for b, ds in declared.items()}
        ),
        bounds=MappingProxyType(
            {
                "queue_capacity": 64,
                "concurrency": 1,
                "intake_capacity": 64,
                "intake_source_bytes": 268435456,
            }
        ),
        quotas=MappingProxyType({"monthly_api_eur": 20.0}),
    )


def _api(declared: dict[str, frozenset[str]]) -> CoreApi:
    return CoreApi(bootstrap(policy=_policy(declared)))


def _shelf(tmp_path: Path, files: dict[str, bytes]) -> Path:
    """Materialise a raw shelf (keys are raw-relative paths) under a temp root and return the root."""
    root = tmp_path / "raw"
    for rel, data in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
    return root


# --- discovery ----------------------------------------------------------------------------------


def test_discover_groups_by_domain_and_dedups_the_md_mirror(tmp_path: Path) -> None:
    # A generated/edited .md mirror is NOT a second book (the binary + its .md collapse to one, the
    # text winning as the authoritative source); a standalone .md note IS a book; the domain is derived
    # from the shelf path (the dir just above <type>), robust to the family/group layers above it.
    root = _shelf(
        tmp_path,
        {
            _qt("a.pdf"): b"%PDF-1",
            _qt("a.md"): _BOOK_MD.encode(),  # a pre-existing mirror of a.pdf
            _qt("notes.md"): b"# my own note",  # a standalone text source
            _cs("b.pdf"): b"%PDF-1",
        },
    )
    books = {str(b.rel): b for b in discover_books(root)}
    assert set(books) == {_qt("a.md"), _qt("notes.md"), _cs("b.md")}  # a.pdf folded in
    a = books[_qt("a.md")]
    assert (
        a.source.name == "a.md" and not a.needs_conversion
    )  # the .md wins -> used as-is (.md-first)
    b = books[_cs("b.md")]
    assert b.source.name == "b.pdf" and b.needs_conversion  # only a binary -> converts into b.md
    assert a.domain == Domain("quant-trading") and b.domain == Domain("computer-science")
    assert domains_on_shelf(root) == frozenset(
        {Domain("quant-trading"), Domain("computer-science")}
    )


def test_discover_ignores_readmes_and_the_intake_sas(tmp_path: Path) -> None:
    # A README is documentation, not a book (it would mis-tag as ``unshelved``); the ``_intake`` sas holds
    # raw arrivals not yet shelved by domain. Neither is ever taken for a book by discovery. The rule
    # matches the ``readme`` prefix, so a bundled repo's ``README_DIS.md`` is skipped too (not just an
    # exact ``README.md``).
    root = _shelf(
        tmp_path,
        {
            _qt("real.pdf"): b"%PDF-1",
            _qt("README.md"): b"# shelf docs",  # a README beside books -> ignored
            _qt(
                "README_DIS.md"
            ): b"# bundled repo docs",  # README* prefix, not exactly readme.md -> ignored
            "Finance/Trading/quant-trading/README.md": b"# domain docs",  # domain-level README -> ignored
            "_intake/arrival.pdf": b"%PDF-1",  # not yet shelved -> ignored
            "_intake/nested/other.pdf": b"%PDF-1",  # _intake at any depth -> ignored
        },
    )
    rels = {str(b.rel) for b in discover_books(root)}
    assert rels == {_qt("real.md")}  # only the real book; READMEs + _intake excluded
    assert domains_on_shelf(root) == frozenset(
        {Domain("quant-trading")}
    )  # no ``unshelved`` leaked in


def test_content_identity_is_stable_across_a_shelf_move(tmp_path: Path) -> None:
    # Identity is the CONTENT of the markdown mirror, NOT the path (D-CI): moving a book to another
    # domain shelf keeps the SAME doc, so a reclass is a retag - never a re-embed. A binary not yet
    # converted has no content id yet (a path-based provisional until ingest extracts the text).
    root = _shelf(tmp_path, {_qt("a.pdf"): b"%PDF-1"})
    [pdf_only] = discover_books(root)
    provisional = pdf_only.identity()  # path-based provisional (no .md mirror yet)
    (root / _QT / "a.md").write_text(_BOOK_MD, encoding="utf-8")
    [quant_book] = discover_books(root)
    content_id = quant_book.identity()
    assert content_id != provisional and str(content_id).startswith("library/")  # now CONTENT-based
    # reshelve to the computer-science shelf (a different Famille/Groupe/domain) - content unchanged.
    (root / _CS).mkdir(parents=True)
    for name in ("a.md", "a.pdf"):
        (root / _QT / name).rename(root / _CS / name)
    [moved] = discover_books(root)
    assert moved.domain == Domain("computer-science")  # reclassed to another shelf
    assert (
        moved.identity() == content_id
    )  # SAME identity (content, not path) => retag, not re-embed


# --- the domain-tag security seam (D72 / invariant 4) -------------------------------------------


def test_captured_domain_tag_is_gated_by_the_policy_declaration(tmp_path: Path) -> None:
    # THE cloisonnement proof: a book tagged `quant-trading` is recallable ONLY from a bubble that
    # DECLARES it. Same capture, two policies - declared surfaces it, undeclared withholds it (fail-closed).
    root = _shelf(tmp_path, {_qt("alpha.pdf"): b"%PDF-1"})

    def _run(tag: str, declared: dict[str, frozenset[str]]) -> RecallView:
        api = _api(
            declared
        )  # a fresh store + its own manifest, so each run truly re-captures the book
        ingest_library(api, _FakeReader(), root, tmp_path / f"m_{tag}.json", clock=_FIXED_CLOCK)
        return api.recall(
            _BOOK_MD, within=Sensitivity.PUBLIC, subject=KNOWLEDGE_BUBBLE, kind=QueryKind.GENERAL
        )

    declared = _run("declared", {"knowledge": frozenset({"quant-trading"})})
    assert (
        declared.working_material and declared.facts == ()
    )  # searchable-first (D137): retrievable, not cited
    withheld = _run("undeclared", {"knowledge": frozenset()})  # tag present, declaration absent
    assert withheld.working_material == ()  # the domain frontier withholds it (D72)


# --- the driver end to end ----------------------------------------------------------------------


def test_ingest_library_captures_recallable_books_and_writes_the_obsidian_mirror(
    tmp_path: Path,
) -> None:
    root = _shelf(tmp_path, {_qt("alpha.pdf"): b"%PDF-1", _cs("beta.pdf"): b"%PDF-1"})
    reader = _FakeReader({"alpha.pdf": _BOOK_MD, "beta.pdf": _BOOK_MD})
    api = _api({"knowledge": frozenset({"quant-trading", "computer-science"})})
    report = ingest_library(api, reader, root, tmp_path / "m.json", clock=_FIXED_CLOCK)
    assert report.total == 2 and report.count(BookStatus.DONE) == 2 and report.skipped == 0
    # the cached markdown mirror is written next to each source (the Obsidian view + the .md-first cache)
    assert (root / _QT / "alpha.md").read_text(encoding="utf-8") == _BOOK_MD
    # a published book is PUBLIC by provenance (D107) - it lands in the PUBLIC partition, not sensible
    view = api.recall(_BOOK_MD, within=Sensitivity.PUBLIC, subject=KNOWLEDGE_BUBBLE)
    assert view.working_material and view.facts == () and not view.admitted_low_recall


# --- resumability -------------------------------------------------------------------------------


def test_ingest_library_resumes_skipping_settled_books(tmp_path: Path) -> None:
    root = _shelf(tmp_path, {_qt("a.pdf"): b"%PDF-1", _qt("b.pdf"): b"%PDF-1"})
    reader = _FakeReader(
        texts={"a.pdf": _BOOK_MD + " alpha", "b.pdf": _BOOK_MD + " beta"}
    )  # distinct content => distinct id
    api = _api({"knowledge": frozenset({"quant-trading"})})
    manifest = tmp_path / "m.json"
    first = ingest_library(
        api, reader, root, manifest, limit=1, clock=_FIXED_CLOCK
    )  # small batch first
    assert len(first.touched) == 1 and first.skipped == 0
    second = ingest_library(api, reader, root, manifest, clock=_FIXED_CLOCK)  # resume the rest
    assert len(second.touched) == 1 and second.skipped == 1  # the DONE book is skipped, not re-read
    assert sorted(reader.calls) == [
        "a.pdf",
        "b.pdf",
    ]  # each book converted exactly once across runs
    loaded = LibraryManifest.load(manifest).records
    assert {r.rel for r in loaded.values()} == {
        _qt("a.md"),
        _qt("b.md"),
    }  # both books, keyed by content id
    assert all(k == r.doc and str(k).startswith("library/") for k, r in loaded.items())


# --- unbreakable per-book isolation -------------------------------------------------------------


def test_a_failing_book_is_isolated_and_the_batch_continues(tmp_path: Path) -> None:
    # The unbreakable guarantee: a reader that RAISES (and one that breaks the port contract) become
    # Recorded errors; the healthy book still lands. No single document can abort the batch.
    root = _shelf(
        tmp_path,
        {_qt("good.pdf"): b"%PDF-1", _qt("boom.pdf"): b"%PDF-1", _qt("bad.pdf"): b"%PDF-1"},
    )
    reader = _FakeReader(raise_on=frozenset({"boom.pdf"}), broken_on=frozenset({"bad.pdf"}))
    api = _api({"knowledge": frozenset({"quant-trading"})})
    report = ingest_library(api, reader, root, tmp_path / "m.json", clock=_FIXED_CLOCK)
    assert report.count(BookStatus.DONE) == 1 and report.count(BookStatus.ERROR) == 2
    assert (
        "ERROR" in report.summary() and "bad.md" in report.summary()
    )  # the summary names a failure sample
    records = LibraryManifest.load(tmp_path / "m.json").records
    by_rel = {
        r.rel: r for r in records.values()
    }  # manifest is keyed by content id now (D-CI); look up by path
    assert by_rel[_qt("boom.md")].status is BookStatus.ERROR and by_rel[_qt("boom.md")].error
    # the healthy book is fully ingested despite its neighbours failing
    view = api.recall(_BOOK_MD, within=Sensitivity.PUBLIC, subject=KNOWLEDGE_BUBBLE)
    assert view.working_material


def test_a_non_utf8_mirror_does_not_abort_the_run(tmp_path: Path) -> None:
    # Audit F2: identity() reads the mirror at the skip-check, OUTSIDE ingest_book's net. A single
    # non-utf8 / corrupt .md must NOT abort the batch - it falls back to a path id and is RECORDED, the
    # healthy neighbour still lands. (Regression: the strict read used to escape the loop and abort.)
    root = _shelf(
        tmp_path, {_qt("bad.md"): b"\xff\xfe not valid utf-8 \xff", _qt("ok.md"): _BOOK_MD.encode()}
    )
    api = _api({"knowledge": frozenset({"quant-trading"})})
    report = ingest_library(
        api, _FakeReader(), root, tmp_path / "m.json", clock=_FIXED_CLOCK
    )  # must not raise
    assert (
        report.count(BookStatus.DONE) >= 1
    )  # the healthy book lands despite the corrupt neighbour
    by_rel = {r.rel: r for r in LibraryManifest.load(tmp_path / "m.json").records.values()}
    assert (
        by_rel[_qt("bad.md")].status is BookStatus.ERROR
    )  # the corrupt one is recorded, not a crash


def test_an_unexpected_raise_in_ingest_book_is_isolated(tmp_path: Path, monkeypatch) -> None:
    # Audit F1: the belt-and-braces handler must not itself crash. It referenced the removed `book.doc`;
    # force ingest_book to raise unexpectedly and assert the batch RECORDS the error and survives.
    from mnemosyne.ingest import library as lib

    root = _shelf(
        tmp_path, {_qt("a.md"): _BOOK_MD.encode(), _qt("b.md"): (_BOOK_MD + " beta").encode()}
    )

    def boom(*args, **kwargs):
        raise RuntimeError("unexpected boom")

    monkeypatch.setattr(lib, "ingest_book", boom)
    api = _api({"knowledge": frozenset({"quant-trading"})})
    report = lib.ingest_library(
        api, _FakeReader(), root, tmp_path / "m.json", clock=_FIXED_CLOCK
    )  # must not raise
    assert report.count(BookStatus.ERROR) == 2 and all(
        "unexpected" in r.error for r in report.touched
    )


def test_editing_a_book_purges_the_stale_prior_version(tmp_path: Path) -> None:
    # Audit F3: editing a .md yields a NEW content id (D-CI); the OLD vectors + manifest row must be
    # purged, else recall surfaces BOTH the stale and the corrected version. Real bootstrap store.
    root = _shelf(tmp_path, {_qt("a.md"): _BOOK_MD.encode()})
    api = _api({"knowledge": frozenset({"quant-trading"})})
    manifest = tmp_path / "m.json"
    ingest_library(api, _FakeReader(), root, manifest, clock=_FIXED_CLOCK)
    first = LibraryManifest.load(manifest).records
    assert len(first) == 1
    old_doc = next(iter(first))
    (root / _QT / "a.md").write_text(
        _BOOK_MD + " a distinct NEW edit alpha", encoding="utf-8"
    )  # operator edits it
    ingest_library(api, _FakeReader(), root, manifest, clock=_FIXED_CLOCK)
    after = LibraryManifest.load(manifest).records
    assert len(after) == 1 and old_doc not in after  # ONE version, the stale row is gone
    assert not api._rt.vector.contains(
        DocId(old_doc)
    )  # the stale vectors are purged (no silent duplicate)


# --- scanned -> needs_ocr (D85) ------------------------------------------------------------------


def test_a_scanned_pdf_is_flagged_needs_ocr_not_indexed_then_skipped(tmp_path: Path) -> None:
    root = _shelf(tmp_path, {_qt("scan.pdf"): b"%PDF-1"})
    reader = _FakeReader({"scan.pdf": "   \n  \t "})  # a scanned page tokenises to whitespace
    api = _api({"knowledge": frozenset({"quant-trading"})})
    manifest = tmp_path / "m.json"
    report = ingest_library(api, reader, root, manifest, clock=_FIXED_CLOCK)
    assert report.count(BookStatus.NEEDS_OCR) == 1 and report.count(BookStatus.DONE) == 0
    # not indexed (an empty doc pollutes nothing) - recall admits it knows nothing rather than inventing
    view = api.recall("momentum factor", within=Sensitivity.PUBLIC, subject=KNOWLEDGE_BUBBLE)
    assert view.working_material == () and view.facts == ()
    again = ingest_library(api, reader, root, manifest, clock=_FIXED_CLOCK)  # normal re-run
    assert (
        again.touched == () and again.skipped == 1
    )  # a scanned book waits, not re-converted every run
    # an explicit OCR retry with a reader that now sees text promotes it to DONE
    ocr_reader = _FakeReader({"scan.pdf": _BOOK_MD})
    retried = ingest_library(api, ocr_reader, root, manifest, retry_ocr=True, clock=_FIXED_CLOCK)
    assert retried.count(BookStatus.DONE) == 1


# --- .md-first: convert once ---------------------------------------------------------------------


def test_md_first_reuses_the_cached_markdown_without_reconverting(tmp_path: Path) -> None:
    # The cost-saving heart of D140: once a book is converted, its .md is the source - a later run reads
    # the cache and NEVER re-invokes the (170 s) reader, even with a fresh manifest that would re-process.
    root = _shelf(tmp_path, {_qt("a.pdf"): b"%PDF-1"})
    reader = _FakeReader()
    api = _api({"knowledge": frozenset({"quant-trading"})})
    ingest_library(api, reader, root, tmp_path / "m1.json", clock=_FIXED_CLOCK)
    assert reader.calls == ["a.pdf"] and (root / _QT / "a.md").exists()
    ingest_library(
        api, reader, root, tmp_path / "m2.json", clock=_FIXED_CLOCK
    )  # fresh manifest, cache hit
    assert reader.calls == ["a.pdf"]  # NOT called again - the cached .md is reused


# --- unbreakable manifest -----------------------------------------------------------------------


def test_a_corrupt_manifest_never_blocks_the_run(tmp_path: Path) -> None:
    manifest = tmp_path / "m.json"
    manifest.write_text("{ this is not valid json ::::", encoding="utf-8")
    root = _shelf(tmp_path, {_qt("a.pdf"): b"%PDF-1"})
    api = _api({"knowledge": frozenset({"quant-trading"})})
    report = ingest_library(
        api, _FakeReader(), root, manifest, clock=_FIXED_CLOCK
    )  # must not raise
    assert report.count(BookStatus.DONE) == 1
    assert json.loads(manifest.read_text(encoding="utf-8"))["records"]  # rewritten as valid JSON


def test_ingest_library_indexes_a_standalone_markdown_note(tmp_path: Path) -> None:
    # A text source (operator-managed .md note) is used AS-IS - never converted (.md-first) - and indexed even
    # when short: only a SCANNED binary is gated by min_chars. Covers the no-conversion extract path.
    root = _shelf(tmp_path, {_qt("note.md"): _BOOK_MD.encode()})
    reader = _FakeReader()
    api = _api({"knowledge": frozenset({"quant-trading"})})
    report = ingest_library(api, reader, root, tmp_path / "m.json", clock=_FIXED_CLOCK)
    assert (
        report.count(BookStatus.DONE) == 1 and reader.calls == []
    )  # read directly, reader never touched
    assert api.recall(
        _BOOK_MD, within=Sensitivity.PUBLIC, subject=KNOWLEDGE_BUBBLE
    ).working_material


def test_report_summary_and_a_noisy_progress_hook_are_robust(tmp_path: Path) -> None:
    root = _shelf(tmp_path, {_qt("a.pdf"): b"%PDF-1", _qt("b.pdf"): b"%PDF-1"})
    api = _api({"knowledge": frozenset({"quant-trading"})})
    seen: list[str] = []

    def _hook(rec: object) -> None:
        seen.append(rec.rel)  # type: ignore[attr-defined]
        raise RuntimeError("a noisy progress hook must never break the run")

    report = ingest_library(
        api, _FakeReader(), root, tmp_path / "m.json", on_book=_hook
    )  # real clock
    assert sorted(seen) == [_qt("a.md"), _qt("b.md")]  # fired per book, its raise swallowed
    assert all(
        r.at for r in report.touched
    )  # the default clock stamped an ISO timestamp on each verdict
    assert "DONE" in report.summary() and "processed" in report.summary()


def test_a_short_scan_is_not_cached_so_the_ocr_retry_re_extracts(tmp_path: Path) -> None:
    # Finding 1 (D75): a scanned PDF whose text layer yields only a SLIVER (< min_chars but non-empty)
    # must be flagged NEEDS_OCR and NOT cached - else the sliver .md shadows the binary and is promoted
    # to DONE on retry, silently defeating OCR. No mirror is left, so the retry truly re-extracts.
    root = _shelf(tmp_path, {_qt("scan.pdf"): b"%PDF-1"})
    reader = _FakeReader(
        {"scan.pdf": "Cover Title Only"}
    )  # 14 non-whitespace chars, well under 200
    api = _api({"knowledge": frozenset({"quant-trading"})})
    manifest = tmp_path / "m.json"
    report = ingest_library(api, reader, root, manifest, clock=_FIXED_CLOCK)
    assert report.count(BookStatus.NEEDS_OCR) == 1
    assert not (root / _QT / "scan.md").exists()  # the sliver is NOT cached (no poisoned mirror)
    ocr_reader = _FakeReader({"scan.pdf": _BOOK_MD})
    retried = ingest_library(api, ocr_reader, root, manifest, retry_ocr=True, clock=_FIXED_CLOCK)
    assert retried.count(BookStatus.DONE) == 1 and ocr_reader.calls == [
        "scan.pdf"
    ]  # genuinely re-extracted
    assert api.recall(
        _BOOK_MD, within=Sensitivity.PUBLIC, subject=KNOWLEDGE_BUBBLE
    ).working_material


def test_an_image_only_scan_is_flagged_needs_ocr_not_ingested_empty(tmp_path: Path) -> None:
    # A scanned / image-only PDF yields only ``<!-- image -->`` placeholders: enough non-whitespace
    # for a naive character count, but no usable text. It must be marked NEEDS_OCR and not cached.
    image_only = "<!-- image -->\n" * 40  # ~480 non-whitespace chars, but 0 real text
    root = _shelf(tmp_path, {_qt("scan.pdf"): b"%PDF-1"})
    reader = _FakeReader({"scan.pdf": image_only})
    api = _api({"knowledge": frozenset({"quant-trading"})})
    report = ingest_library(api, reader, root, tmp_path / "m.json", clock=_FIXED_CLOCK)
    assert report.count(BookStatus.NEEDS_OCR) == 1 and report.count(BookStatus.DONE) == 0
    assert not (root / _QT / "scan.md").exists()  # the empty placeholder .md is NOT cached


def test_an_unshelvable_book_is_surfaced_undeclared_not_a_silent_black_hole(tmp_path: Path) -> None:
    # Finding 2 (D75): a book with no shelf domain (raw-root stray) or a domain the policy does NOT
    # declare would be captured yet forever withheld from recall (fail-closed D72) and never retried - a
    # silent black hole. It is refused up front as UNDECLARED: visible, not captured, retried.
    root = _shelf(
        tmp_path,
        {"loose.pdf": b"%PDF-1", _cs("cell.pdf"): b"%PDF-1", _qt("ok.pdf"): b"%PDF-1"},
    )
    reader = _FakeReader()
    api = _api({"knowledge": frozenset({"quant-trading"})})
    report = ingest_library(
        api,
        reader,
        root,
        tmp_path / "m.json",
        declared_domains=frozenset({Domain("quant-trading")}),
        clock=_FIXED_CLOCK,
    )
    # loose.pdf -> no <type> => unshelved; cell.pdf -> computer-science, a real domain the policy omits.
    assert report.count(BookStatus.UNDECLARED) == 2 and report.count(BookStatus.DONE) == 1
    assert reader.calls == [
        "ok.pdf"
    ]  # the two un-declarable books are refused BEFORE any costly convert
    assert "UNDECLARED" in report.summary()
    manifest = LibraryManifest.load(tmp_path / "m.json").records
    by_rel = {
        r.rel: r for r in manifest.values()
    }  # keyed by content id now (D-CI); look up by path
    assert by_rel["loose.md"].status is BookStatus.UNDECLARED  # the raw-root stray, always refused
    assert api.recall(
        _BOOK_MD, within=Sensitivity.PUBLIC, subject=KNOWLEDGE_BUBBLE
    ).working_material


def test_the_run_survives_a_manifest_write_failure(tmp_path: Path) -> None:
    # Finding 3 (D75): "unbreakable" covers the manifest WRITE too. A save that raises OSError (here the
    # manifest's parent is a FILE, so mkdir/write fails) degrades to a counted failure - the book is
    # still ingested and the batch completes; it is simply re-processed on the next resume.
    (tmp_path / "blocker").write_text("i am a file, not a dir", encoding="utf-8")
    manifest = tmp_path / "blocker" / "m.json"  # parent is a file => save() raises OSError
    root = _shelf(tmp_path, {_qt("a.pdf"): b"%PDF-1"})
    api = _api({"knowledge": frozenset({"quant-trading"})})
    report = ingest_library(
        api, _FakeReader(), root, manifest, clock=_FIXED_CLOCK
    )  # must not raise
    assert report.count(BookStatus.DONE) == 1 and report.manifest_write_failures == 1
    assert not manifest.exists() and "manifest write" in report.summary()
    assert api.recall(
        _BOOK_MD, within=Sensitivity.PUBLIC, subject=KNOWLEDGE_BUBBLE
    ).working_material  # still ingested


def test_run_library_ingestion_wires_the_policy_declaration_and_shelf(tmp_path: Path) -> None:
    # The composition root, brick-free (inject a stub runtime whose reader decodes the utf-8 "pdf"
    # bytes as text): it reads declared_domains for KNOWLEDGE_BUBBLE from the policy and drives the
    # shelf. A declared book lands DONE + recallable; an undeclared one is refused UNDECLARED - proving
    # the harness threads the tag/declare lockstep through, not just the driver in isolation.
    root = _shelf(tmp_path, {_qt("book.pdf"): _BOOK_MD.encode(), _cs("x.pdf"): _BOOK_MD.encode()})
    pol = _policy({"knowledge": frozenset({"quant-trading"})})
    rt = bootstrap(policy=pol)
    report = run_library_ingestion(
        raw_root=root,
        manifest_path=tmp_path / "m.json",
        policy=pol,
        runtime=rt,
        progress=False,
    )
    assert report.count(BookStatus.DONE) == 1 and report.count(BookStatus.UNDECLARED) == 1
    view = CoreApi(rt).recall(_BOOK_MD, within=Sensitivity.PUBLIC, subject=KNOWLEDGE_BUBBLE)
    assert (
        view.working_material
    )  # the declared book is searchable through the real composition path


def test_run_library_ingestion_enters_and_exits_the_gate_around_the_ingest(tmp_path: Path) -> None:
    # Q1 wiring (zero-regression seam): the gate wraps the runtime cold-start + the ingest, so a caller's
    # guarded_heavy_run is genuinely entered/exited around the heavy section, not silently bypassed.
    root = _shelf(tmp_path, {_qt("book.pdf"): _BOOK_MD.encode()})
    pol = _policy({"knowledge": frozenset({"quant-trading"})})
    rt = bootstrap(policy=pol)
    events: list[str] = []

    @contextmanager
    def recording_gate() -> Iterator[None]:
        events.append("enter")
        try:
            yield
        finally:
            events.append("exit")

    report = run_library_ingestion(
        raw_root=root,
        manifest_path=tmp_path / "m.json",
        policy=pol,
        runtime=rt,
        progress=False,
        gate=recording_gate(),
    )
    assert events == ["enter", "exit"]
    assert report.count(BookStatus.DONE) == 1  # the gate does not break the run


def test_run_library_ingestion_default_gate_is_an_unchanged_noop(tmp_path: Path) -> None:
    # backward-compatible: calling without gate= behaves exactly as before (nullcontext, no coordination)
    root = _shelf(tmp_path, {_qt("book.pdf"): _BOOK_MD.encode()})
    pol = _policy({"knowledge": frozenset({"quant-trading"})})
    rt = bootstrap(policy=pol)
    report = run_library_ingestion(
        raw_root=root,
        manifest_path=tmp_path / "m.json",
        policy=pol,
        runtime=rt,
        progress=False,
    )
    assert report.count(BookStatus.DONE) == 1


def test_manifest_survives_a_malformed_row(tmp_path: Path) -> None:
    manifest = tmp_path / "m.json"
    manifest.write_text(
        json.dumps({"version": 1, "records": {_qt("a.md"): {"status": "not_a_status"}}}),
        encoding="utf-8",
    )
    loaded = LibraryManifest.load(manifest)
    assert loaded.records == {}  # the malformed row is dropped, the load does not crash


# --- G5: manifest path re-alignment (post-reorg, before enrichment) ---------------------------------


def _manifest_with(tmp_path: Path, rows: dict[str, BookRecord]) -> Path:
    path = tmp_path / "library_manifest.json"
    man = LibraryManifest.load(path)  # empty (absent) -> then we seed rows and persist
    man.records.update(rows)
    man.save()
    return path


def test_realign_moves_stale_paths_to_current_and_leaves_off_shelf_rows(tmp_path: Path) -> None:
    # post-reorg: the .md sits at a NEW shelf path, its CONTENT (hence content-id) unchanged, but the
    # manifest row still holds the OLD rel. realign moves rel onto the current path (matched by content-id)
    # so the next edit's rel-keyed stale-vector purge finds the prior version. An off-shelf row is left.
    root = _shelf(tmp_path, {_qt("book.md"): _BOOK_MD.encode()})
    [book] = discover_books(root)
    doc, cur_rel = str(book.identity()), str(book.rel)
    manifest_path = _manifest_with(
        tmp_path,
        {
            doc: BookRecord("old/place/book.md", "quant-trading", doc, BookStatus.DONE, 300, "t0"),
            "deadbeef00": BookRecord(
                "gone/removed.md", "x", "deadbeef00", BookStatus.DONE, 100, "t0"
            ),
        },
    )

    rep = realign_manifest_paths(manifest_path, root)
    assert rep.realigned == 1 and rep.already_ok == 0 and rep.unmatched == 1 and rep.wrote

    reloaded = LibraryManifest.load(manifest_path)
    assert reloaded.records[doc].rel == cur_rel  # moved to the current path
    assert (
        reloaded.records[doc].doc == doc and reloaded.records[doc].status is BookStatus.DONE
    )  # non-destructive
    assert (
        reloaded.records["deadbeef00"].rel == "gone/removed.md"
    )  # off-shelf row untouched (run purges it)
    assert (
        len(list(tmp_path.glob("library_manifest.pre-realign.*.json"))) == 1
    )  # backed up once before writing


def test_realign_is_idempotent(tmp_path: Path) -> None:
    root = _shelf(tmp_path, {_qt("book.md"): _BOOK_MD.encode()})
    [book] = discover_books(root)
    doc = str(book.identity())
    manifest_path = _manifest_with(
        tmp_path, {doc: BookRecord("old/book.md", "quant-trading", doc, BookStatus.DONE, 300, "t0")}
    )
    assert realign_manifest_paths(manifest_path, root).realigned == 1  # first pass moves it
    second = realign_manifest_paths(manifest_path, root)  # second finds it already aligned
    assert second.realigned == 0 and second.already_ok == 1 and not second.wrote


def test_realign_dry_run_measures_without_writing(tmp_path: Path) -> None:
    root = _shelf(tmp_path, {_qt("book.md"): _BOOK_MD.encode()})
    [book] = discover_books(root)
    doc = str(book.identity())
    manifest_path = _manifest_with(
        tmp_path, {doc: BookRecord("old/book.md", "quant-trading", doc, BookStatus.DONE, 300, "t0")}
    )
    rep = realign_manifest_paths(manifest_path, root, dry_run=True)
    assert rep.realigned == 1 and not rep.wrote  # measured, not written
    assert (
        LibraryManifest.load(manifest_path).records[doc].rel == "old/book.md"
    )  # unchanged on disk
    assert not list(tmp_path.glob("*.pre-realign.*"))  # no backup on a dry-run


# --------------------------------------------------------------------------- #
# Orphan vectors - a manifest DONE id whose content left the shelf, still indexed (G6 / D44).  #
# --------------------------------------------------------------------------- #
class _FakeVector:
    """A dict-backed VectorIndex stand-in: tracks which docs are indexed (contains / invalidate)."""

    def __init__(self, docs: set[str]) -> None:
        self._docs = set(docs)

    def contains(self, doc: DocId) -> bool:
        return str(doc) in self._docs

    def invalidate(self, doc: DocId) -> None:
        self._docs.discard(str(doc))


class _FakeKeyword:
    """A dict-backed KeywordIndex stand-in: tracks invalidations for the purge tests."""

    def __init__(self, docs: set[str]) -> None:
        self._docs = set(docs)

    def invalidate(self, doc: DocId) -> None:
        self._docs.discard(str(doc))


def test_detect_orphan_vectors_flags_a_done_id_gone_from_the_shelf(tmp_path: Path) -> None:
    # a live book + a manifest DONE row for a book that VANISHED from the shelf, both indexed.
    root = _shelf(tmp_path, {_qt("book.md"): _BOOK_MD.encode()})
    [book] = discover_books(root)
    live = str(book.identity())
    manifest_path = _manifest_with(
        tmp_path,
        {
            live: BookRecord(str(book.rel), "quant-trading", live, BookStatus.DONE, 300, "t0"),
            "deadbeef00": BookRecord(
                "gone/removed.md", "quant-trading", "deadbeef00", BookStatus.DONE, 100, "t0"
            ),
        },
    )
    vector = _FakeVector({live, "deadbeef00"})

    report = detect_orphan_vectors(manifest_path, root, vector=vector)

    assert (
        report.checked == 1
    )  # only the off-shelf id is a candidate (the live one is on the shelf)
    assert [r.doc for r in report.orphans] == ["deadbeef00"]
    assert report.orphans[0].rel == "gone/removed.md"
    assert vector.contains(DocId("deadbeef00"))  # READ-ONLY: detection purged nothing


def test_detect_ignores_a_moved_book_same_content(tmp_path: Path) -> None:
    # a book whose CONTENT is unchanged but whose manifest rel is an old path (reorg) is NOT an orphan:
    # identity is content-based, so the live shelf id matches the manifest key.
    root = _shelf(tmp_path, {_qt("book.md"): _BOOK_MD.encode()})
    [book] = discover_books(root)
    live = str(book.identity())
    manifest_path = _manifest_with(
        tmp_path,
        {live: BookRecord("old/path/book.md", "quant-trading", live, BookStatus.DONE, 300, "t0")},
    )
    report = detect_orphan_vectors(manifest_path, root, vector=_FakeVector({live}))
    assert report.orphans == () and report.checked == 0


def test_detect_skips_an_off_shelf_id_never_actually_indexed(tmp_path: Path) -> None:
    # an off-shelf DONE id whose vectors are NOT in the index is not a confirmed orphan (no false positive).
    root = _shelf(tmp_path, {_qt("book.md"): _BOOK_MD.encode()})
    manifest_path = _manifest_with(
        tmp_path,
        {
            "deadbeef00": BookRecord(
                "gone.md", "quant-trading", "deadbeef00", BookStatus.DONE, 100, "t0"
            )
        },
    )
    report = detect_orphan_vectors(manifest_path, root, vector=_FakeVector(set()))
    assert (
        report.checked == 1 and report.orphans == ()
    )  # probed, absent from the index => not reported


def test_purge_orphan_vectors_drops_derivatives_and_manifest_row(tmp_path: Path) -> None:
    root = _shelf(tmp_path, {_qt("book.md"): _BOOK_MD.encode()})
    [book] = discover_books(root)
    live = str(book.identity())
    manifest_path = _manifest_with(
        tmp_path,
        {
            live: BookRecord(str(book.rel), "quant-trading", live, BookStatus.DONE, 300, "t0"),
            "deadbeef00": BookRecord(
                "gone.md", "quant-trading", "deadbeef00", BookStatus.DONE, 100, "t0"
            ),
        },
    )
    vector, keyword = _FakeVector({live, "deadbeef00"}), _FakeKeyword({live, "deadbeef00"})
    report = detect_orphan_vectors(manifest_path, root, vector=vector)

    n = purge_orphan_vectors(report, manifest_path, root, vector=vector, keyword=keyword)

    assert n == 1
    assert not vector.contains(DocId("deadbeef00"))  # the orphan's vectors are gone
    assert vector.contains(DocId(live))  # the live book's vectors are untouched
    reloaded = LibraryManifest.load(manifest_path)
    assert (
        "deadbeef00" not in reloaded.records and live in reloaded.records
    )  # only the orphan row dropped
    assert (
        len(list(tmp_path.glob("library_manifest.pre-orphan-purge.*.json"))) == 1
    )  # backed up once


def test_purge_is_idempotent(tmp_path: Path) -> None:
    root = _shelf(tmp_path, {_qt("book.md"): _BOOK_MD.encode()})
    [book] = discover_books(root)
    live = str(book.identity())
    manifest_path = _manifest_with(
        tmp_path,
        {
            live: BookRecord(str(book.rel), "quant-trading", live, BookStatus.DONE, 300, "t0"),
            "deadbeef00": BookRecord(
                "gone.md", "quant-trading", "deadbeef00", BookStatus.DONE, 100, "t0"
            ),
        },
    )
    vector, keyword = _FakeVector({live, "deadbeef00"}), _FakeKeyword({live, "deadbeef00"})
    report = detect_orphan_vectors(manifest_path, root, vector=vector)
    assert purge_orphan_vectors(report, manifest_path, root, vector=vector, keyword=keyword) == 1
    # a second purge over the SAME (now stale) report: rows already gone => no-op, no second backup.
    assert purge_orphan_vectors(report, manifest_path, root, vector=vector, keyword=keyword) == 0
    assert len(list(tmp_path.glob("library_manifest.pre-orphan-purge.*.json"))) == 1


def test_purge_spares_a_source_that_reappeared_since_the_report(tmp_path: Path) -> None:
    # a STALE report lists a doc that is NOW back on the shelf (content id live): the delete-path re-check
    # must spare it - a reappeared source is never purged (belt-and-suspenders, non-destructive).
    root = _shelf(tmp_path, {_qt("book.md"): _BOOK_MD.encode()})
    [book] = discover_books(root)
    live = str(book.identity())
    manifest_path = _manifest_with(
        tmp_path,
        {live: BookRecord(str(book.rel), "quant-trading", live, BookStatus.DONE, 300, "t0")},
    )
    vector, keyword = _FakeVector({live}), _FakeKeyword({live})
    stale = OrphanReport(
        orphans=(OrphanRow(doc=live, rel="old.md", domain="quant-trading"),), checked=1
    )

    assert purge_orphan_vectors(stale, manifest_path, root, vector=vector, keyword=keyword) == 0
    assert vector.contains(DocId(live))  # NOT deleted - it is on the shelf now
    assert live in LibraryManifest.load(manifest_path).records


def test_detect_and_purge_spare_a_present_but_unreadable_mirror(tmp_path: Path) -> None:
    # operator's real hazard: he re-saves a book's .md in non-utf8 (French accents in Latin-1) -> it is
    # PRESENT but unreadable, so identity() falls back to a path id and its old content-id row looks
    # off-shelf. The file-presence guard must SPARE it - never purge a live source's derivatives.
    root = _shelf(tmp_path, {_qt("book.md"): b"r\xe9sum\xe9 en latin-1 \xe8\xe0 non-utf8 \x80\xff"})
    [book] = discover_books(root)
    rel = str(book.rel)
    manifest_path = _manifest_with(
        tmp_path,
        {"cafe00": BookRecord(rel, "quant-trading", "cafe00", BookStatus.DONE, 300, "t0")},
    )
    vector, keyword = _FakeVector({"cafe00"}), _FakeKeyword({"cafe00"})

    report = detect_orphan_vectors(manifest_path, root, vector=vector)
    assert report.orphans == () and report.checked == 0  # spared by file presence, never probed

    # a stale report that names it must also be spared by the purge re-check (defense in depth).
    stale = OrphanReport(orphans=(OrphanRow("cafe00", rel, "quant-trading"),), checked=1)
    assert purge_orphan_vectors(stale, manifest_path, root, vector=vector, keyword=keyword) == 0
    assert vector.contains(DocId("cafe00"))  # the present-but-unreadable book's vectors survive
    assert "cafe00" in LibraryManifest.load(manifest_path).records  # its manifest row survives
