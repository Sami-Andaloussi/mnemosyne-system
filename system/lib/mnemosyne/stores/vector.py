"""StubEmbedder + InMemoryVectorIndex (D68) - dense retrieval, PARTITIONED BY SENSITIVITY.

Light in-memory stand-ins for the vector leg (default bricks: **bge-m3** embedder +
**Qdrant server**, D68), implementing :class:`~mnemosyne.ports.embedder.Embedder`
and :class:`~mnemosyne.ports.vectorindex.VectorIndex`. The security-critical property
carries over from the port: the index is **partitioned by sensitivity**, and a
``sensible`` search stays entirely in its own isolated partition (invariant 1 / D68);
partitions are never crossed implicitly (cloisonnement, D54).

:class:`StubEmbedder` is a deterministic hashing vectorizer - a cheap, reproducible
stand-in for the real multilingual model: it hashes word tokens into a fixed-width
dense vector (no model, no RNG, stable across runs). Retrieval similarity is cosine,
so shared vocabulary scores high and disjoint content scores ~0 - enough gradient for
the low-recall gate (invariant 14) without pretending to be a real embedding. The BM25
+ reranker legs of hybrid retrieval plug in above this same port (LOT 5). Code &
docstrings English (D117).
"""

from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Sequence
from dataclasses import dataclass

from ..ports import (
    DocId,
    Domain,
    Embedding,
    GovernanceLabel,
    SearchHit,
    Sensitivity,
    Vector,
    is_indexable_vector,
)

_STUB_MODEL_ID = "stub-hashing-v0"
_STUB_DIM = 1024
_WORD = re.compile(r"\w+", re.UNICODE)


def _coord(token: str) -> int:
    """Stable coordinate for a token (blake2b, deterministic across runs - no RNG)."""
    digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(digest, "big") % _STUB_DIM


class StubEmbedder:
    """Deterministic hashing embedder standing in for bge-m3 (D68).

    Identical text embeds identically and shared vocabulary yields a high cosine
    similarity, so retrieval has a real gradient without a model. The real encoder
    swaps in behind :class:`~mnemosyne.ports.embedder.Embedder` (D68 / D113)."""

    @property
    def model_id(self) -> str:
        return _STUB_MODEL_ID

    @property
    def dimension(self) -> int:
        return _STUB_DIM

    @property
    def max_tokens(self) -> int:
        return 8192

    @property
    def recall_floor(self) -> float:
        """Low-recall floor for this hashed-bag-of-tokens cosine (invariant 14): 0.3 fits the stub's
        score scale (the real bge-m3 declares its own 0.53, (3)-2b). Read by the Retriever's gate (D65)."""
        return 0.3

    def embed(self, texts: Sequence[str]) -> list[Embedding]:
        """Encode each text as a hashed bag-of-tokens dense vector (deterministic)."""
        out: list[Embedding] = []
        for text in texts:
            acc = [0.0] * _STUB_DIM
            for match in _WORD.finditer(text.lower()):
                acc[_coord(match.group(0))] += 1.0
            out.append(
                Embedding(
                    vector=tuple(acc),
                    model_id=_STUB_MODEL_ID,
                    dimension=_STUB_DIM,
                    version="0",
                )
            )
        return out


def _cosine(a: Vector, b: Vector) -> float:
    """Cosine similarity; zero for an empty vector (no spurious match)."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


@dataclass(frozen=True, slots=True)
class _Entry:
    """A document's indexed passages - each its ORDINAL and vector - and its governance label (D135).

    The ordinal is stored EXPLICITLY (not the tuple position) so that dropping a non-indexable passage
    at :meth:`InMemoryVectorIndex.upsert` leaves the survivors' ordinals aligned with the read-time
    re-chunk (D136): a search reports the true passage ordinal, never one renumbered by the drop."""

    passages: tuple[tuple[int, Embedding], ...]
    label: GovernanceLabel


class InMemoryVectorIndex:
    """In-memory Qdrant stand-in, PARTITIONED BY SENSITIVITY (invariant 1 / D68).

    Each sensitivity owns a separate partition; ``sensible`` is its own physically
    isolated store, and a search is scoped to ONE partition via ``within`` -
    partitions are never crossed implicitly (cloisonnement, D54). A document is stored as
    its sequence of PASSAGE vectors (D135); search keeps the best passage per doc."""

    __slots__ = ("_partitions",)

    def __init__(self) -> None:
        self._partitions: dict[Sensitivity, dict[DocId, _Entry]] = {s: {} for s in Sensitivity}

    def upsert(self, doc: DocId, passages: Sequence[Embedding], label: GovernanceLabel) -> None:
        """Index ``doc``'s passage vectors into the partition implied by
        ``label.sensitivity`` (D135).

        A ``sensible`` document lands ONLY in the isolated ``sensible`` partition
        (invariant 1); it is never written to a shared index. Re-``upsert`` REPLACES the
        doc's passages wholesale => a re-index is idempotent (the substrate of the journal's
        replay, invariant 24). A NON-INDEXABLE passage vector (non-finite or zero-norm,
        :func:`~mnemosyne.ports.is_indexable_vector`) is DROPPED - its surviving neighbours keep their
        original ordinals (D136) - so a degenerate page never poisons retrieval. Empty ``passages``, or
        passages that are ALL non-indexable => the doc is not indexed, and any prior entry is cleared."""
        indexed = tuple(
            (ordinal, embedding)
            for ordinal, embedding in enumerate(passages)
            if is_indexable_vector(embedding.vector)
        )
        if not indexed:
            self._partitions[label.sensitivity].pop(doc, None)
            return
        self._partitions[label.sensitivity][doc] = _Entry(passages=indexed, label=label)

    def search(
        self,
        query: Embedding,
        *,
        within: Sensitivity,
        domains: frozenset[Domain] = frozenset(),
        top_k: int = 10,
    ) -> list[SearchHit]:
        """Search a SINGLE sensitivity partition (``within``), optionally narrowed to
        ``domains`` (D72). A doc's score is its BEST passage's cosine and ``chunk`` carries that
        passage's ordinal (D135 / D136), so a query matching one passage of a long document still
        surfaces it AND ``recall`` can pack that passage, not the whole doc. A search ``within``
        ``sensible`` stays entirely local; partitions are never crossed (invariant 1 / D54)."""
        partition = self._partitions[within]
        hits: list[SearchHit] = []
        for doc, entry in partition.items():
            if domains and not (domains & entry.label.domains):
                continue
            # the best passage AND its TRUE ordinal (D136): recall packs THIS passage, never the whole
            # doc. The ordinal is the STORED one (it survives a dropped non-indexable neighbour), not
            # the tuple position, so it still aligns with the read-time re-chunk.
            ordinal, score = max(
                (
                    (ordinal, _cosine(query.vector, embedding.vector))
                    for ordinal, embedding in entry.passages
                ),
                key=lambda pair: pair[1],
            )
            hits.append(SearchHit(doc=doc, score=score, label=entry.label, chunk=ordinal))
        hits.sort(key=lambda hit: hit.score, reverse=True)
        return hits[:top_k]

    def invalidate(self, doc: DocId) -> None:
        """Purge a document's vectors from every partition - a derivative purge; the
        truth is untouched and the index rebuilds from it (D56)."""
        for partition in self._partitions.values():
            partition.pop(doc, None)

    def contains(self, doc: DocId) -> bool:
        """Whether ``doc`` is indexed in any partition (the integration witness, inv. 24)."""
        return any(doc in partition for partition in self._partitions.values())
