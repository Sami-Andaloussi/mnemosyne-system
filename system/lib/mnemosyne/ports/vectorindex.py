"""VectorIndex (D68) - dense index PARTITIONED BY SENSITIVITY.

The vector base, separate from the fact memory (GraphStore). One default
multilingual embedder feeds it; retrieval is hybrid (dense + BM25 + reranker)
above this port. The partition is the security-critical part:

* **Partition by sensitivity** (D68 / invariant 1) - the ``sensible`` subset
  has its index **100 % local and PHYSICALLY isolated**, making the
  cloisonnement *physical*, not merely logical. ``public`` / ``perso`` subsets
  may share an index. Every search is scoped to a partition via ``within``.
* **Filter by metadata** - strong metadata filtering serves cloisonnement
  (D54 / D72): a search may be narrowed to declared domains.

Default OSS brick: **Qdrant in SERVER mode, local** (NOT embedded - embedded
caps ~20k points and forbids concurrent access, blocking at the 2500+ docs
scale, D121-B2) - see ``system/config/oss_registry.md`` (D68). The index is a
reconstructible derivative (D44 / D56), gitignored (``.vectorstore/``).

Decisions: D68 (architecture + Qdrant-server)  -  D121-B2 (server, not embedded)
 -  D54 / D72 (metadata filtering = cloisonnement)  -  D44 / D56 (reconstructible).
Invariant carried: 1 (physical isolation of `sensible`).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from .core import Domain, GovernanceLabel, Sensitivity
from .embedder import Embedding
from .store import DocId


@dataclass(frozen=True, slots=True)
class SearchHit:
    """One retrieved document, carrying its governance label (D108-(5)) and the matched passage.

    ``chunk`` is the ordinal of the passage that scored the hit (D135 / D136), so ``recall`` can
    pack the RELEVANT passage instead of the whole document (the fail-closed runner bound would
    refuse a whole long document, D136). ``None`` means no passage granularity - a lexical
    (keyword-only) hit matches the whole document, so the passage is resolved by re-chunking at
    read time (:func:`~mnemosyne.ingest.chunk.select_passage`)."""

    doc: DocId
    score: float
    label: GovernanceLabel
    chunk: int | None = None


@runtime_checkable
class VectorIndex(Protocol):
    """A dense index whose partitions are isolated by sensitivity (invariant 1)."""

    def upsert(self, doc: DocId, passages: Sequence[Embedding], label: GovernanceLabel) -> None:
        """Index ``doc``'s PASSAGES into the partition implied by ``label.sensitivity`` (D135).

        A document is indexed as a sequence of passage vectors (one per chunk, ordinal =
        position), not a single whole-document vector: ``search`` scores every passage and
        keeps the best per doc, so a query matching one passage of a long document still
        surfaces it (the Étape-3 pilot showed a single diffuse whole-doc vector misses).
        Re-``upsert`` REPLACES the doc's passages wholesale => idempotent for the journal's
        replay (invariant 24). Empty ``passages`` (an empty extraction) => the doc is not
        indexed. A ``sensible`` document lands ONLY in the physically isolated local
        partition (invariant 1 / D68); it is never written to a shared index.
        """
        ...

    def search(
        self,
        query: Embedding,
        *,
        within: Sensitivity,
        domains: frozenset[Domain] = frozenset(),
        top_k: int = 10,
    ) -> list[SearchHit]:
        """Search a SINGLE sensitivity partition (``within``), optionally filtered
        to ``domains`` (D72). A search ``within`` ``sensible`` stays entirely
        local; partitions are never crossed implicitly (cloisonnement, D54)."""
        ...

    def invalidate(self, doc: DocId) -> None:
        """Drop a document's vectors (a derivative purge; the truth is untouched, D56)."""
        ...

    def contains(self, doc: DocId) -> bool:
        """Whether ``doc`` currently holds vectors in the index (any sensitivity partition).

        Read-only membership - no partition crossing, no write. Lets a caller CONFIRM a document is
        really indexed before acting on it: a reconciliation must act only on vectors PROVEN present,
        never on a guess (D44 / invariant 2). Already provided by the concrete indexes (and used by the
        journal's consistency marker); declared here so callers may depend on it through the port."""
        ...
