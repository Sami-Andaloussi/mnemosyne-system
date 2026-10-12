"""LibraryTruthStore (D144 / D56 / D105) — the ``.md``-backed truth for the persisted library.

Mnémosyne's truth store is an in-memory stand-in (:class:`~mnemosyne.stores.truth.MarkdownTruthStore`):
it holds what a process CAPTURED, but a fresh process (a separate ``raptor-build``, the search tool)
starts empty — so a book indexed by an EARLIER ingest run has its vectors in Qdrant yet no readable
text here, and every ``truth.read`` for it raises ``KeyError`` (raptor summarises nothing; recall's
``pack_passage`` crashes). This store closes that gap for the LIBRARY without waiting for the full
git-backed truth adapter: it subclasses the in-memory store and, on a read MISS, reads the book's
``.md`` MIRROR from disk. The mirror IS the captured text (content identity, D-CI / D142), so
re-chunking it yields the SAME passage ordinals the vectors were built on — the byte-identity the read
contract requires (D136).

The label is the book's PROVENANCE label — ``public`` / :data:`~mnemosyne.ingest.library.KNOWLEDGE_BUBBLE`
/ its shelf ``domain`` — because a published book is PUBLIC by provenance (D144), matching the partition
the migrated vectors live in. A doc written IN-PROCESS still wins (the in-memory version is the fresher
truth); a non-library miss raises ``KeyError`` exactly like the base store. This store never WRITES a
book — a book's truth is its ``.md`` (D56, the .md/git layer stays the sole arbiter); it only makes that
truth readable across processes. Code & docstrings English (D117)."""

from __future__ import annotations

from pathlib import Path

from ..ports import (
    DEFAULT_ROLE,
    DocId,
    DocRole,
    Domain,
    Envelope,
    GovernanceLabel,
    Sensitivity,
)
from ..stores.truth import MarkdownTruthStore
from .library import KNOWLEDGE_BUBBLE, BookStatus, LibraryManifest

# The fixed repo-relative truth locations (mirror of library_run's DEFAULT_*): this file lives at
# system/lib/mnemosyne/ingest/library_truth.py, so parents[4] is the repo root. Kept local to avoid an
# import cycle (library_run imports the runtime that imports this).
_REPO_ROOT = Path(__file__).resolve().parents[4]
_DEFAULT_RAW_ROOT = _REPO_ROOT / "knowledge" / "raw"
_DEFAULT_MANIFEST = _REPO_ROOT / "knowledge" / "library_manifest.json"


class LibraryTruthStore(MarkdownTruthStore):
    """In-memory truth (fresh captures) PLUS a lazy ``.md``-mirror fallback for the indexed library.

    Subclasses :class:`~mnemosyne.stores.truth.MarkdownTruthStore` so it drops in behind the
    ``TruthStore`` port unchanged; only the three read-side methods that a cross-process recall needs
    (:meth:`read`, :meth:`is_valid`, :meth:`role`) fall back to the on-disk library. Writes and
    archival stay the in-memory base's job (a book is never written here — its ``.md`` is the truth)."""

    __slots__ = ("_roots", "_books", "_endorsed")

    def __init__(
        self,
        *,
        manifest_path: Path | str = _DEFAULT_MANIFEST,
        raw_root: Path | str = _DEFAULT_RAW_ROOT,
        endorsed: frozenset[str] = frozenset(),
        shelves: tuple[tuple[Path | str, Path | str], ...] = (),
    ) -> None:
        super().__init__()
        # D156: which books the operator has endorsed as citable sources, replayed from the durable ledger
        # at composition time. Empty by default — the fail-closed posture is unchanged for any caller
        # that wires nothing (every book stays working material, exactly as before).
        self._endorsed = endorsed
        # D157 — SEVERAL shelves, each with its OWN root: raw books AND distilled fiches now both live
        # in the index, and a doc id resolves against the root it was ingested from. One root could not
        # serve both, and indexing a layer this store cannot READ is worse than not indexing it: a hit
        # on it raises KeyError inside `pack_passage`, i.e. a crashed recall (measured, not feared).
        pairs = ((manifest_path, raw_root), *shelves)
        self._roots: tuple[Path, ...] = tuple(Path(root).resolve() for _, root in pairs)
        # Every DONE book: doc id -> (rel, domain, index of its root). NEEDS_OCR / UNDECLARED / ERROR
        # rows are excluded — they have no indexed truth to serve.
        self._books: dict[str, tuple[str, str, int]] = {}
        for slot, (manifest_source, _) in enumerate(pairs):
            for key, rec in LibraryManifest.load(manifest_source).records.items():
                if rec.status is BookStatus.DONE:
                    # first shelf wins on a collision: the raw book is the primary truth for its id
                    self._books.setdefault(key, (rec.rel, rec.domain, slot))

    def _library_envelope(self, doc: DocId) -> Envelope[str] | None:
        """The book's ``.md`` mirror under its provenance label, or ``None`` if it is not a readable book."""
        entry = self._books.get(str(doc))
        if entry is None:
            return None
        rel, domain, slot = entry
        root = self._roots[slot]
        path = (root / rel).resolve()
        # Defense-in-depth: a corrupted / hand-edited manifest ``rel`` must NOT escape the shelf and be
        # served as PUBLIC/knowledge. ``discover_books`` only ever emits clean ``relative_to`` paths, so
        # this rejects a TAMPERED manifest, never a real book.
        if not path.is_relative_to(root):
            return None
        try:
            # Byte-exact: the mirror IS the captured text (D-CI), so ordinals still align at recall (D136).
            text = path.read_text(encoding="utf-8")
        except OSError:
            return None  # a vanished / unreadable mirror -> read() re-raises KeyError, never a crash (D140)
        label = GovernanceLabel(
            sensitivity=Sensitivity.PUBLIC,  # a published book is PUBLIC by provenance (D144)
            bubble=KNOWLEDGE_BUBBLE,
            domains=frozenset({Domain(domain)}),
        )
        return Envelope(text, label)

    def read(self, doc: DocId) -> Envelope[str]:
        try:
            return super().read(doc)  # a doc captured THIS process is the fresher truth (wins)
        except KeyError:
            envelope = self._library_envelope(doc)
            if envelope is None:
                raise  # not a library book either -> KeyError, same as the base store
            return envelope

    def is_valid(self, doc: DocId) -> bool:
        # A DONE book present on disk is present-and-valid (D56); the base store only knows in-process docs.
        return super().is_valid(doc) or str(doc) in self._books

    def role(self, doc: DocId) -> DocRole:
        """The book's epistemic role — from the ENDORSEMENT LEDGER, not a hard-coded default (D156).

        This method used to return :data:`DEFAULT_ROLE` unconditionally for every library book, which
        made D137 unreachable rather than merely unwired: a book is not in the in-memory base store at
        all, so ``set_role`` raised ``KeyError`` on all 314 of them, and a success would have died with
        the process anyway. The ledger is the durable half of the gesture; this is the read side.

        An in-process write still wins (the base store is the fresher truth), then the ledger, then the
        fail-closed default — so an unendorsed book is still never citable."""
        try:
            return super().role(doc)
        except KeyError:
            key = str(doc)
            if key in self._endorsed:
                return DocRole.BASE_DE_CONNAISSANCES
            if key in self._books:
                return (
                    DEFAULT_ROLE  # a raw library book is working material until endorsed (D137)
                )
            raise
