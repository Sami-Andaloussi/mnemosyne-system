"""QdrantVectorIndex (D68) — the real dense index behind the VectorIndex port,
PARTITIONED BY SENSITIVITY (invariant 1).

Wraps **Qdrant in server mode, local** (Apache-2.0), the default (D68 / D121-B2 — server,
not embedded: embedded caps ~20k points and forbids concurrency). The security-critical
property is the partition: each sensitivity owns its OWN Qdrant collection, so a
``sensible`` document lives in a physically separate collection and a search is scoped to
ONE collection — partitions are never crossed implicitly (invariant 1 / D54).

**Decoupling (D126).** The adapter talks to a small injected ``backend`` in PRIMITIVES
(collection name, id, vector, payload dict), never to Qdrant types — so the partition
ROUTING (the security surface) is unit-tested against a light double WITHOUT Qdrant
installed. The real client is wrapped by :func:`connect_qdrant` at ③ ignition; that thin
translation layer (:class:`_QdrantBackend`, the SOLE importer of the brick, D103) is
exercised by the 1-click smoke, not the unit suite. Code & docstrings English (D117); the
sensitivity tokens stay French (D33 / D66).
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Protocol

from ..ports import (
    Bubble,
    DocId,
    Domain,
    Embedding,
    GovernanceLabel,
    SearchHit,
    Sensitivity,
    is_indexable_vector,
)

_COLLECTION_PREFIX = "mnemosyne"
#: Reverse of :attr:`Sensitivity.token`, to rebuild the enum from a stored payload.
_SENSITIVITY_BY_TOKEN = {s.token: s for s in Sensitivity}

#: Where the local Qdrant server listens — the SINGLE source of that fact. The start's dependency
#: preflight (``RUNTIME_SERVICES`` in :mod:`~mnemosyne.runtime.bootstrap`) DERIVES its host and port
#: from this constant instead of restating them, so a moved port cannot leave the check probing the
#: old one while the connection goes elsewhere. A second copy would drift in silence.
QDRANT_URL = "http://localhost:6333"


class VectorBackend(Protocol):
    """The primitive surface :class:`QdrantVectorIndex` needs from a vector store.

    Deliberately expressed in primitives (no Qdrant types) so a light double can stand in
    for the brick in tests (D126). :func:`connect_qdrant` supplies the real one. ``search``
    GROUPS passage points by ``doc`` and returns one ``(score, payload)`` row per doc — each
    doc's BEST passage, top_k DISTINCT docs (D135 / audit A-2); the doc id is in the payload."""

    def ensure_collection(self, collection: str, *, dimension: int) -> None: ...
    def upsert(
        self, collection: str, doc_id: str, vector: Sequence[float], payload: dict
    ) -> None: ...
    def search(
        self, collection: str, vector: Sequence[float], domains: tuple[str, ...], top_k: int
    ) -> list[tuple[float, dict]]: ...
    def delete_by_doc(self, collection: str, doc: str) -> None: ...
    def has_doc(self, collection: str, doc: str) -> bool: ...


class QdrantVectorIndex:
    """Real Qdrant index behind :class:`~mnemosyne.ports.vectorindex.VectorIndex` (D68).

    Partition = one collection per sensitivity (``mnemosyne_public`` / ``_perso`` /
    ``_sensible``); the collection is derived ONLY from the datum's sensitivity, so
    ``sensible`` is physically isolated (invariant 1). The backend is injected (D126)."""

    __slots__ = ("_backend", "_prefix", "_dimension")

    def __init__(
        self,
        backend: VectorBackend,
        *,
        prefix: str = _COLLECTION_PREFIX,
        dimension: int = 1024,
    ) -> None:
        self._backend = backend
        self._prefix = prefix
        self._dimension = dimension

    def _collection(self, sensitivity: Sensitivity) -> str:
        """The collection for a sensitivity — the partition boundary (invariant 1)."""
        return f"{self._prefix}_{sensitivity.token}"

    def upsert(self, doc: DocId, passages: Sequence[Embedding], label: GovernanceLabel) -> None:
        """Index ``doc``'s passage vectors into the partition of ``label.sensitivity`` — and
        ONLY there (D135).

        The collection is a pure function of ``label.sensitivity``: a ``sensible`` datum can
        only land in the isolated ``sensible`` collection (invariant 1). Each passage is a point
        ``doc#ordinal`` carrying ``doc`` in its payload; the doc's prior passages are cleared
        first, so a re-index REPLACES them wholesale ⇒ idempotent (invariant 24), even if the
        passage count shrank. A non-indexable passage vector is DROPPED (see the loop); empty
        ``passages``, or a doc with no indexable passage, leave the doc unindexed."""
        collection = self._collection(label.sensitivity)
        self._backend.ensure_collection(collection, dimension=self._dimension)
        self._backend.delete_by_doc(collection, str(doc))
        for ordinal, passage in enumerate(passages):
            if not is_indexable_vector(passage.vector):
                # A non-indexable passage vector — non-finite (bge-m3's fp16 path can overflow a
                # coordinate to NaN / ±inf) or zero-norm (a figures-only page tokenises to nothing) —
                # is DROPPED, never sent to Qdrant: a SINGLE such vector makes the server reject the
                # whole upsert ("did not match any variant of untagged enum VectorStruct"), which would
                # fail the entire book at the ③ scale-up. The raw text stays in the truth (D56 / D85)
                # and the SURVIVING passages keep their ordinal, so select_passage still aligns at read
                # (D136). Fail-safe (D100), never a crash — one bad page cannot sink a document.
                continue
            payload = {
                "doc": str(doc),
                "chunk": ordinal,
                "sensitivity": label.sensitivity.token,
                "bubble": str(label.bubble),
                "domains": sorted(str(d) for d in label.domains),
            }
            self._backend.upsert(collection, f"{doc}#{ordinal}", passage.vector, payload)

    def search(
        self,
        query: Embedding,
        *,
        within: Sensitivity,
        domains: frozenset[Domain] = frozenset(),
        top_k: int = 10,
    ) -> list[SearchHit]:
        """Search the SINGLE partition ``within`` (never any other), optionally narrowed to
        ``domains`` (D72). The backend GROUPS passage points by ``doc`` and returns each doc's
        BEST passage (D135 / audit A-2) — so a long doc owning many top passages can never starve
        the result of distinct docs; the collection queried is a pure function of ``within``
        (invariant 1 / D54). ``chunk`` carries that best passage's ordinal from the payload (D136),
        so ``recall`` packs the matched passage rather than the whole document."""
        collection = self._collection(within)
        self._backend.ensure_collection(collection, dimension=self._dimension)
        rows = self._backend.search(
            collection, query.vector, tuple(sorted(str(d) for d in domains)), top_k
        )
        return [
            SearchHit(
                doc=DocId(payload["doc"]),
                score=score,
                label=self._label_from_payload(payload),
                chunk=self._chunk_from_payload(payload),
            )
            for score, payload in rows
        ]

    @staticmethod
    def _chunk_from_payload(payload: dict) -> int | None:
        """The passage ordinal from a payload, ZERO-TRUST (D100-3 / audit m-3).

        A non-int ``chunk`` — from a corrupt point, a third-party writer, or a stored ``"0"`` string —
        is treated as ABSENT (``None`` ⇒ the passage is resolved lexically at read), never fed on to
        ``select_passage`` where a ``str``/``bool`` would crash the whole recall. A ``bool`` is
        excluded (it is an ``int`` subclass but never a valid ordinal)."""
        chunk = payload.get("chunk")
        return chunk if isinstance(chunk, int) and not isinstance(chunk, bool) else None

    def invalidate(self, doc: DocId) -> None:
        """Purge ``doc``'s passages from EVERY partition (a derivative purge; truth
        untouched, D56)."""
        for sensitivity in Sensitivity:
            self._backend.delete_by_doc(self._collection(sensitivity), str(doc))

    def contains(self, doc: DocId) -> bool:
        """Whether ``doc`` has ANY indexed passage in any partition (the integration witness, inv. 24).

        Doc-level, NOT the ``doc#0`` point: a document whose first passage was non-indexable and
        dropped (:func:`~mnemosyne.ports.is_indexable_vector`) is still 'contained' via its surviving
        passages, so the witness stays truthful even when a degenerate page is skipped (D136)."""
        return any(self._backend.has_doc(self._collection(s), str(doc)) for s in Sensitivity)

    @staticmethod
    def _label_from_payload(payload: dict) -> GovernanceLabel:
        """Rebuild the governance label from the stored payload (D108-⑤).

        The vector index is a reconstructible derivative (D56): it carries the sensitivity,
        bubble and domains the Guard reads, but NOT the full provenance chain (that lives in
        the truth store), so ``provenance`` is left ``None`` on a recalled hit."""
        return GovernanceLabel(
            sensitivity=_SENSITIVITY_BY_TOKEN[payload["sensitivity"]],
            bubble=Bubble(payload["bubble"]),
            domains=frozenset(Domain(d) for d in payload.get("domains", ())),
        )


def connect_qdrant(  # pragma: no cover - needs the brick + a running server (③ ignition)
    *,
    url: str = QDRANT_URL,
    prefix: str = _COLLECTION_PREFIX,
    dimension: int = 1024,
) -> QdrantVectorIndex:
    """Connect to the local Qdrant server and return a wired :class:`QdrantVectorIndex`.

    Lazy import: ``qdrant-client`` and a running server exist only on the machine at ③
    ignition (D126 ``[OPERATOR]``), never in CI. Validated by the real 1-click smoke, not the
    unit suite. This is the SOLE importer of the Qdrant brick (D103)."""
    from qdrant_client import QdrantClient

    return QdrantVectorIndex(
        _QdrantBackend(QdrantClient(url=url)), prefix=prefix, dimension=dimension
    )


_UUID_NS = uuid.UUID("6f4b2c9e-3a1d-4e5f-8b7a-0c1d2e3f4a5b")  # fixed namespace: DocId → point id


class _QdrantBackend:  # pragma: no cover - real Qdrant translation (③ ignition, smoke-tested)
    """Thin translation from the primitive :class:`VectorBackend` surface to the real Qdrant
    client API (PointStruct / Filter / Distance). The SOLE place Qdrant types are built
    (D103). Qdrant point ids must be uint/UUID, so a DocId string is mapped deterministically
    to a UUID (uuid5) and the original id travels in the payload. Never run by the unit suite."""

    def __init__(self, client: object) -> None:
        self._client = client

    @staticmethod
    def _pid(doc_id: str) -> str:
        return str(uuid.uuid5(_UUID_NS, doc_id))

    def ensure_collection(self, collection: str, *, dimension: int) -> None:
        from qdrant_client import models

        if not self._client.collection_exists(collection):
            self._client.create_collection(
                collection,
                vectors_config=models.VectorParams(size=dimension, distance=models.Distance.COSINE),
            )

    def upsert(self, collection: str, doc_id: str, vector: Sequence[float], payload: dict) -> None:
        from qdrant_client import models

        self._client.upsert(
            collection,
            points=[models.PointStruct(id=self._pid(doc_id), vector=list(vector), payload=payload)],
        )

    def search(
        self, collection: str, vector: Sequence[float], domains: tuple[str, ...], top_k: int
    ) -> list[tuple[float, dict]]:
        from qdrant_client import models

        query_filter = None
        if domains:
            query_filter = models.Filter(
                must=[
                    models.FieldCondition(key="domains", match=models.MatchAny(any=list(domains)))
                ]
            )
        # GROUP passage points by their `doc` payload (D135 / audit A-2): one group per document,
        # its single BEST passage (group_size=1), top_k DISTINCT docs — a long doc owning many top
        # passages can never crowd the others out. `query_points_groups` is Qdrant's server-side
        # grouping read (confirmed against the live server at ignition, ③).
        response = self._client.query_points_groups(
            collection_name=collection,
            query=list(vector),
            group_by="doc",
            limit=top_k,
            group_size=1,
            query_filter=query_filter,
            with_payload=True,
        )
        rows: list[tuple[float, dict]] = []
        for group in response.groups:
            best = group.hits[0]  # group_size=1 ⇒ the doc's best passage
            rows.append((float(best.score), dict(best.payload or {})))
        return rows

    def delete_by_doc(self, collection: str, doc: str) -> None:
        from qdrant_client import models

        if self._client.collection_exists(collection):
            self._client.delete(
                collection,
                points_selector=models.FilterSelector(
                    filter=models.Filter(
                        must=[models.FieldCondition(key="doc", match=models.MatchValue(value=doc))]
                    )
                ),
            )

    def has_doc(self, collection: str, doc: str) -> bool:
        from qdrant_client import models

        if not self._client.collection_exists(collection):
            return False
        points, _ = self._client.scroll(
            collection,
            scroll_filter=models.Filter(
                must=[models.FieldCondition(key="doc", match=models.MatchValue(value=doc))]
            ),
            limit=1,
            with_payload=False,
            with_vectors=False,
        )
        return bool(points)
