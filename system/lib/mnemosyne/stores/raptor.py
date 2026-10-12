"""RaptorStore (Ch.5 / RAG niveau 2 / D56 / D44) - a hierarchy of abstractive summaries.

RAPTOR's essence (retrieve across a TREE of summaries, not just leaf passages) grounded on the
corpus's OWN hierarchy - not unsupervised soft-clustering. A 2-level tree over the library shelf:

* **level "book"** - one synopsis per book, whose members are that ONE book's own passages
  (:mod:`~mnemosyne.ingest.raptor_build` builds it from the book's re-chunked truth text);
* **level "domain"** - one synopsis per ``(sensitivity, bubble, domain)``, whose members are the
  BOOK synopses sharing that exact triple (cloisonnement never crosses a partition, invariant 1/3).

**Content-addressed identity (D56 / D44 / invariant 24).** :func:`raptor_doc_id` is a pure
function of ``(level, sorted member DocIds)`` - the SAME two moves ``ingest.library._content_doc``
already makes for a book: unchanged members => identical id => idempotent re-``put``; changed members
=> a NEW id, so a rebuild leaves the OLD id stale for a sweep to invalidate (never edited in place,
D74). A book's own doc id is itself content-hashed over its full text, so a book synopsis's id
changes automatically the moment the book's content does - no separate content hash is needed here.

**Namespaced OUT of the book-orphan domain.** Every id lives under :data:`RAPTOR_SUMMARY_PREFIX`
(``library/summary/...``), which is NEVER a manifest key
(:func:`~mnemosyne.ingest.library.detect_orphan_vectors` scans only ``manifest.records``) - so that
check structurally ignores a summary doc; :mod:`~mnemosyne.ingest.raptor_build` owns its OWN
reconciliation (the sweep) instead.

**Derived, reconstructible (D56).** A node is NOT truth: it lives in this store, gitignored,
content-addressed. Like :class:`~mnemosyne.runtime.snapshots.SnapshotStore`, ``base_path=None`` (the
default) keeps it in RAM (D126 - a brick-free build never touches disk); a path swaps in a
JSONL-backed on-disk backend under ``system/state/`` (the ``human_layer.jsonl`` convention, already
gitignored by ``system/state/*.jsonl`` - D71). Unlike the snapshot store, there is no capture ORDER
to preserve here (only content-addressed membership), so no separate index file is needed.

Code & docstrings English (D117); sensitivity tokens stay French (D33 / D66).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal, Protocol

from ..ports import Bubble, DocId, Domain, GovernanceLabel, Sensitivity

#: Namespace every RAPTOR summary DocId lives under - keeps summaries OUT of the manifest-keyed
#: book-orphan domain (:func:`~mnemosyne.ingest.library.detect_orphan_vectors` never sees one).
RAPTOR_SUMMARY_PREFIX: Final = "library/summary/"

#: The 2-level tree this Ch.5 build realizes (book synopsis > domain synopsis). A plain ``str`` at
#: runtime (matching the build contract's ``level: str``); the ``Literal`` is a static-typing aid.
type RaptorLevel = Literal["book", "domain"]


def is_raptor_summary(doc: DocId) -> bool:
    """Whether ``doc`` names a RAPTOR summary node (Ch.5) - never a manifest / leaf document.

    Used by the retrieval read-path (:meth:`~mnemosyne.api.core_api.CoreApi._pack_summary`) to
    branch a ``SearchHit`` to the RaptorStore instead of the truth store, and (structurally, by
    construction - no check needed there) by
    :func:`~mnemosyne.ingest.library.detect_orphan_vectors`, which never iterates a doc under this
    prefix because it is never a manifest key."""
    return str(doc).startswith(RAPTOR_SUMMARY_PREFIX)


def raptor_doc_id(
    level: RaptorLevel, member_ids: Sequence[DocId], *, discriminator: str = ""
) -> DocId:
    """Content-addressed identity for a RAPTOR node: ``library/summary/<level>/<blake2b(...)>``.

    Mirrors :func:`~mnemosyne.ingest.library._content_doc` (blake2b, ``digest_size=8``, no RNG, no
    security use): the digest is over ``level`` + ``discriminator`` + the member ids SORTED, so member
    ORDER never matters (a cluster is a SET). Every field is LENGTH-PREFIXED - the injective framing
    the Guard's ``_canon`` uses (``guard/monitor.py``) - so no value holding a separator (a ``\n`` or
    ``:`` in a domain / bubble token) can be read as another: the id is a TOTAL, collision-free
    function of ``(level, discriminator, member SET)`` (audit NIT-1).

    ``discriminator`` distinguishes nodes that share a member SET but not their grouping CONTEXT
    (audit M1): a **domain** node folds its full ``(sensitivity, bubble, domain)`` key here, so two
    domain clusters built over the same single member - one book living in TWO domains - can never
    collide onto one id (which would silently drop one synopsis and pin the other past the sweep). A
    **book** node needs none: its one, already content-hashed member id is unique on its own.

    Unchanged members (and discriminator) => identical id => idempotent re-``put`` (invariant 24);
    changed members => a different id (the old one is left stale for the corpus pass's sweep, D74)."""
    # Length-prefixed framing (injective, like the Guard's _canon, guard/monitor.py): a separator
    # inside a field (a `\n` / `:` in a domain or bubble token) can never forge a collision (NIT-1).
    parts = bytearray()
    for field in (level, discriminator, *sorted(str(m) for m in member_ids)):
        raw = field.encode("utf-8")
        parts += f"{len(raw)}:".encode("ascii") + raw
    digest = hashlib.blake2b(bytes(parts), digest_size=8).hexdigest()
    return DocId(f"{RAPTOR_SUMMARY_PREFIX}{level}/{digest}")


@dataclass(frozen=True, slots=True)
class RaptorNode:
    """One node of the RAPTOR tree - a book synopsis or a domain synopsis (Ch.5).

    ``doc`` is content-addressed (:func:`raptor_doc_id`); ``member_ids`` names exactly what was
    clustered (a book's own doc id for a "book" node, the member book-synopsis ids for a "domain"
    node) - the SAME tuple that ``doc`` was hashed from, so an id can always be re-derived from a
    node's own members as a consistency check. ``label`` carries the cluster's governance: sensitivity
    is the MAX of its members (raise-only, invariant 17/18), bubble is the members' SHARED bubble
    (cloisonnement never crosses one, invariant 1/3), domains is the members' domain(s) - a book
    synopsis inherits its book's single domain; :mod:`~mnemosyne.ingest.raptor_build` computes this.
    Never edited in place: a changed cluster gets a NEW node under a NEW id (non-destructive, D74) -
    the OLD id is left for the corpus pass's sweep to invalidate."""

    doc: DocId
    level: RaptorLevel
    member_ids: tuple[DocId, ...]
    text: str
    label: GovernanceLabel


# --------------------------------------------------------------------------- #
# Primitive de/serialization - sensitivity/bubble/domains ONLY (D56)           #
# --------------------------------------------------------------------------- #
#: Reverse of :attr:`Sensitivity.token`, to rebuild the enum from a stored payload.
_SENSITIVITY_BY_TOKEN = {s.token: s for s in Sensitivity}


def _label_to_primitive(label: GovernanceLabel) -> dict:
    """Flatten a label to JSON-safe primitives - sensitivity/bubble/domains ONLY.

    A RaptorNode is a DERIVED, reconstructible summary (D56), like a vector-index payload
    (:meth:`~mnemosyne.stores.vector_qdrant.QdrantVectorIndex._label_from_payload`), NOT the
    precious replay store (:class:`~mnemosyne.runtime.snapshots.SnapshotStore`): the full
    provenance chain is not carried across a reload - only what the Guard reads travels."""
    return {
        "sensitivity": label.sensitivity.token,
        "bubble": str(label.bubble),
        "domains": sorted(str(d) for d in label.domains),
    }


def _label_from_primitive(raw: dict) -> GovernanceLabel:
    """Inverse of :func:`_label_to_primitive`."""
    return GovernanceLabel(
        sensitivity=_SENSITIVITY_BY_TOKEN[raw["sensitivity"]],
        bubble=Bubble(raw["bubble"]),
        domains=frozenset(Domain(d) for d in raw.get("domains", ())),
    )


def _node_to_primitive(node: RaptorNode) -> dict:
    """Flatten a :class:`RaptorNode` to a JSON-safe dict (the on-disk row)."""
    return {
        "doc": str(node.doc),
        "level": node.level,
        "member_ids": [str(m) for m in node.member_ids],
        "text": node.text,
        "label": _label_to_primitive(node.label),
    }


def _node_from_primitive(raw: dict) -> RaptorNode:
    """Inverse of :func:`_node_to_primitive`."""
    return RaptorNode(
        doc=DocId(raw["doc"]),
        level=raw["level"],
        member_ids=tuple(DocId(m) for m in raw["member_ids"]),
        text=raw["text"],
        label=_label_from_primitive(raw["label"]),
    )


# --------------------------------------------------------------------------- #
# Backends - RAM default (D126) + a single-file JSONL on-disk backend         #
# --------------------------------------------------------------------------- #
class RaptorBackend(Protocol):
    """The primitive surface :class:`RaptorStore` needs from a backend (D126 decoupling).

    Mirrors :class:`~mnemosyne.runtime.snapshots.SnapshotBackend`: a small seam so the store's
    put/get/contains/invalidate/iter shape is unit-tested against either backend the same way."""

    def put(self, node: RaptorNode) -> None: ...
    def get(self, doc: DocId) -> RaptorNode: ...
    def contains(self, doc: DocId) -> bool: ...
    def invalidate(self, doc: DocId) -> None: ...
    def all_ids(self) -> tuple[DocId, ...]: ...


class _InMemoryRaptorBackend:
    """The RAM backend (D126 default) - a plain dict, exactly what a brick-free build needs."""

    __slots__ = ("_nodes",)

    def __init__(self) -> None:
        self._nodes: dict[DocId, RaptorNode] = {}

    def put(self, node: RaptorNode) -> None:
        self._nodes[node.doc] = node

    def get(self, doc: DocId) -> RaptorNode:
        return self._nodes[doc]

    def contains(self, doc: DocId) -> bool:
        return doc in self._nodes

    def invalidate(self, doc: DocId) -> None:
        self._nodes.pop(doc, None)

    def all_ids(self) -> tuple[DocId, ...]:
        return tuple(self._nodes)


class _DiskRaptorBackend:
    """A single JSONL file (one node per line), rewritten atomically (temp + replace) on every
    mutation - the ``system/state/`` convention (gitignored by the existing ``*.jsonl`` rule, D71).

    The tree is small (one node per book + one per domain, at most a few hundred at this corpus's
    scale), so a full read + rewrite per ``put`` / ``invalidate`` is cheap and keeps the format
    trivially inspectable (``grep`` / ``jq``-able). Unlike
    :class:`~mnemosyne.runtime.snapshots._DiskSnapshotBackend`, no separate order index is needed:
    a RAPTOR store has no capture ORDER to preserve, only content-addressed membership."""

    __slots__ = ("_path",)

    def __init__(self, path: Path) -> None:
        self._path = path
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def _read_all(self) -> dict[str, dict]:
        if not self._path.exists():
            return {}
        rows: dict[str, dict] = {}
        for line in self._path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue  # a corrupt line is skipped, never a crash (fail-safe, D100)
            if isinstance(row, dict) and isinstance(row.get("doc"), str):
                rows[row["doc"]] = row
        return rows

    def _write_all(self, rows: dict[str, dict]) -> None:
        tmp = self._path.with_name(f"{self._path.name}.tmp")
        with tmp.open("w", encoding="utf-8") as fh:
            for doc in sorted(rows):
                fh.write(json.dumps(rows[doc], ensure_ascii=False))
                fh.write("\n")
        tmp.replace(self._path)

    def put(self, node: RaptorNode) -> None:
        rows = self._read_all()
        rows[str(node.doc)] = _node_to_primitive(node)
        self._write_all(rows)

    def get(self, doc: DocId) -> RaptorNode:
        rows = self._read_all()
        try:
            row = rows[str(doc)]
        except KeyError:
            raise KeyError(doc) from None
        return _node_from_primitive(row)

    def contains(self, doc: DocId) -> bool:
        return str(doc) in self._read_all()

    def invalidate(self, doc: DocId) -> None:
        rows = self._read_all()
        if rows.pop(str(doc), None) is not None:
            self._write_all(rows)

    def all_ids(self) -> tuple[DocId, ...]:
        return tuple(DocId(d) for d in self._read_all())


class RaptorStore:
    """The RAPTOR summary store (Ch.5) - content-addressed put/get/contains/invalidate/iter.

    ``base_path=None`` (default) is the in-memory backend (D126: a brick-free build creates no
    on-disk state). A path swaps in the JSONL on-disk backend, conventionally
    ``system/state/raptor_store.jsonl`` (gitignored - see :mod:`~mnemosyne.runtime.bootstrap`'s
    ``real_runtime``). Idempotent: ``put``-ting a node under an id already present REPLACES it with
    an identical shape when the content is unchanged (same members => same id => same node, invariant
    24); :meth:`invalidate` is a derivative purge (D56) - the corpus TRUTH (the book's own ``.md``)
    is never touched by anything in this module."""

    __slots__ = ("_backend",)

    def __init__(self, *, base_path: str | Path | None = None) -> None:
        self._backend: RaptorBackend = (
            _InMemoryRaptorBackend() if base_path is None else _DiskRaptorBackend(Path(base_path))
        )

    def put(self, node: RaptorNode) -> None:
        """Store ``node``, content-addressed (idempotent re-``put`` under an unchanged id)."""
        self._backend.put(node)

    def get(self, doc: DocId) -> RaptorNode:
        """The full node; an unknown id raises ``KeyError`` (never a guess, D100)."""
        return self._backend.get(doc)

    def contains(self, doc: DocId) -> bool:
        """Whether ``doc`` currently holds a node - the REUSE check the corpus pass makes first,
        before ever calling the summarizer (skip a model call for an unchanged cluster)."""
        return self._backend.contains(doc)

    def invalidate(self, doc: DocId) -> None:
        """Drop a stale summary node - a derivative purge (D56), never the corpus truth."""
        self._backend.invalidate(doc)

    def iter_ids(self) -> tuple[DocId, ...]:
        """Every summary id currently held - what the corpus pass's sweep diffs against the
        freshly-computed valid-id set to find what must be invalidated (staleness, D74)."""
        return self._backend.all_ids()
