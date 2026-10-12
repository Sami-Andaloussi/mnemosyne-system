"""LibraryTruthStore (D144 / D56) - the ``.md``-backed truth makes the indexed library readable cross-process.

The in-memory truth stand-in starts EMPTY in a fresh process, so raptor + recall saw nothing for a book an
earlier ingest had captured (its vectors persist in Qdrant, its text did not). This store falls back to the
book's ``.md`` MIRROR on a read miss, under its PUBLIC-by-provenance label - proven here brick-free with a
tiny on-disk shelf + manifest. Byte-identity is the point: the mirror IS the captured text (D-CI), so recall
re-chunks to the SAME ordinals the vectors were built on (D136).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mnemosyne.ingest.library import (
    KNOWLEDGE_BUBBLE,
    BookRecord,
    BookStatus,
    LibraryManifest,
)
from mnemosyne.ingest.library_truth import LibraryTruthStore
from mnemosyne.ports import DEFAULT_ROLE, DocId, Domain, Envelope, GovernanceLabel, Sensitivity

_BOOK_TEXT = "momentum factor equities backtest sharpe drawdown portfolio rebalancing.\n" * 20


def _shelf(
    tmp_path: Path,
    *,
    doc: str,
    rel: str = "Finance/Trading/quant-trading/books/alpha.md",
    domain: str = "quant-trading",
    status: BookStatus = BookStatus.DONE,
    text: str = _BOOK_TEXT,
) -> LibraryTruthStore:
    """A one-book on-disk shelf + manifest, returned as a wired LibraryTruthStore."""
    raw = tmp_path / "raw"
    (raw / rel).parent.mkdir(parents=True, exist_ok=True)
    (raw / rel).write_text(text, encoding="utf-8")
    manifest = LibraryManifest(path=tmp_path / "m.json")
    manifest.record(
        BookRecord(rel=rel, domain=domain, doc=doc, status=status, chars=len(text), at="2026-07-16")
    )
    manifest.save()
    return LibraryTruthStore(manifest_path=manifest.path, raw_root=raw)


def test_read_falls_back_to_the_md_mirror_under_the_public_provenance_label(tmp_path: Path) -> None:
    doc = "library/deadbeefdeadbeef"
    store = _shelf(tmp_path, doc=doc)
    env = store.read(DocId(doc))
    assert env.payload == _BOOK_TEXT  # byte-identical to the mirror -> ordinals stay aligned (D136)
    assert (
        env.label.sensitivity is Sensitivity.PUBLIC
    )  # a published book is public by provenance (D144)
    assert env.label.bubble == KNOWLEDGE_BUBBLE
    assert env.label.domains == frozenset(
        {Domain("quant-trading")}
    )  # its shelf domain, tagged as at ingest


def test_a_doc_written_in_process_wins_over_the_md_fallback(tmp_path: Path) -> None:
    doc = "library/deadbeefdeadbeef"
    store = _shelf(tmp_path, doc=doc)
    fresher = Envelope(
        "a fresher in-process version",
        GovernanceLabel(
            sensitivity=Sensitivity.SENSIBLE, bubble=KNOWLEDGE_BUBBLE, domains=frozenset()
        ),
    )
    store.write(DocId(doc), fresher)
    assert (
        store.read(DocId(doc)).payload == "a fresher in-process version"
    )  # the in-memory truth wins


def test_a_non_library_miss_raises_keyerror(tmp_path: Path) -> None:
    store = _shelf(tmp_path, doc="library/deadbeefdeadbeef")
    with pytest.raises(KeyError):
        store.read(DocId("not-a-book"))  # unknown, not a book -> KeyError like the base store


def test_only_done_books_are_served(tmp_path: Path) -> None:
    # a NEEDS_OCR book has no indexed truth -> not served, even if a .md happens to sit on disk
    doc = "library/needsocr0000000"
    store = _shelf(tmp_path, doc=doc, status=BookStatus.NEEDS_OCR)
    with pytest.raises(KeyError):
        store.read(DocId(doc))
    assert store.is_valid(DocId(doc)) is False


def test_is_valid_and_role_for_a_done_book(tmp_path: Path) -> None:
    doc = "library/okokokokokokokok"
    store = _shelf(tmp_path, doc=doc)
    assert store.is_valid(DocId(doc)) is True  # a DONE book on disk is present-and-valid (D56)
    assert (
        store.role(DocId(doc)) is DEFAULT_ROLE
    )  # matière-de-travail until a human endorses it (D137)


def test_never_serves_a_perso_or_non_done_doc(tmp_path: Path) -> None:
    # Locks the security contract beyond "not-a-book": a perso capture id and non-DONE books must NEVER be
    # served (they'd otherwise surface under a PUBLIC / knowledge label - a cloisonnement leak).
    raw = tmp_path / "raw"
    book = raw / "Finance/Trading/quant-trading/books/ok.md"
    book.parent.mkdir(parents=True, exist_ok=True)
    book.write_text(_BOOK_TEXT, encoding="utf-8")
    manifest = LibraryManifest(path=tmp_path / "m.json")
    manifest.record(
        BookRecord(
            rel="Finance/Trading/quant-trading/books/ok.md",
            domain="quant-trading",
            doc="library/donedonedonedon0",
            status=BookStatus.DONE,
            chars=len(_BOOK_TEXT),
            at="t",
        )
    )
    manifest.record(
        BookRecord(
            rel="Finance/Trading/quant-trading/books/nd.md",
            domain="macro",
            doc="library/undeclared00000",
            status=BookStatus.UNDECLARED,
            chars=0,
            at="t",
        )
    )
    manifest.record(
        BookRecord(
            rel="Finance/Trading/quant-trading/books/er.md",
            domain="quant-trading",
            doc="library/error0000000000",
            status=BookStatus.ERROR,
            chars=0,
            at="t",
        )
    )
    manifest.save()
    store = LibraryTruthStore(manifest_path=manifest.path, raw_root=raw)
    assert (
        store.read(DocId("library/donedonedonedon0")).label.sensitivity is Sensitivity.PUBLIC
    )  # served
    # a perso capture id (chats / distilled / youtube all use `capture-N`) and non-DONE books are NEVER served
    for hidden in ("capture-5", "library/undeclared00000", "library/error0000000000"):
        with pytest.raises(KeyError):
            store.read(DocId(hidden))


def test_a_manifest_rel_escaping_the_shelf_is_refused(tmp_path: Path) -> None:
    # Defense-in-depth (a tampered manifest): a `rel` that climbs OUT of raw_root must not read an out-of-tree
    # file and serve it as PUBLIC/knowledge. The book is DONE, but the traversal guard refuses it (KeyError).
    raw = tmp_path / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    (tmp_path / "secret.md").write_text("OUT OF SHELF", encoding="utf-8")
    manifest = LibraryManifest(path=tmp_path / "m.json")
    manifest.record(
        BookRecord(
            rel="../secret.md",
            domain="quant-trading",
            doc="library/tamperedtampere",
            status=BookStatus.DONE,
            chars=12,
            at="t",
        )
    )
    manifest.save()
    store = LibraryTruthStore(manifest_path=manifest.path, raw_root=raw)
    with pytest.raises(KeyError):
        store.read(DocId("library/tamperedtampere"))
