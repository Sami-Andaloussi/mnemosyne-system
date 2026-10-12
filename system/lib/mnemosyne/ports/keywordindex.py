"""KeywordIndex (D68) - lexical BM25 index PARTITIONED BY SENSITIVITY (invariant 1).

The keyword leg of hybrid retrieval (dense + BM25 + reranker, D68): where the dense
:class:`~mnemosyne.ports.vectorindex.VectorIndex` matches on MEANING, this matches on the
literal TERMS, and the :class:`~mnemosyne.stores.retrieval.Retriever` fuses the two by
Reciprocal Rank Fusion (RRF). The security-critical property is the SAME partition as the
dense leg:

* **Partition by sensitivity** (invariant 1 / D68) - the ``sensible`` subset has its index
  **100 % local and PHYSICALLY isolated**; every search is scoped to one partition via
  ``within``. ``public`` / ``perso`` may share an index.
* **Filter by metadata** - a search may be narrowed to declared ``domains`` (cloisonnement,
  D54 / D72).

Default OSS brick: **tantivy** (``tantivy-py``, MIT) - see ``system/config/oss_registry.md``
(D68). The index is a reconstructible derivative (D44 / D56), gitignored (``.keywordstore/``);
it reuses :class:`~mnemosyne.ports.vectorindex.SearchHit` so both legs speak one hit type.

Decisions: D68 (hybrid retrieval)  -  D54 / D72 (partition + domain filter)  -  D44 / D56
(reconstructible). Invariant carried: 1 (physical isolation of ``sensible``).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from .core import Domain, GovernanceLabel, Sensitivity
from .store import DocId
from .vectorindex import SearchHit


@runtime_checkable
class KeywordIndex(Protocol):
    """A lexical (BM25) index whose partitions are isolated by sensitivity (invariant 1)."""

    def index(self, doc: DocId, text: str, label: GovernanceLabel) -> None:
        """Index ``doc``'s text into the partition implied by ``label.sensitivity``.

        A ``sensible`` document lands ONLY in the physically isolated local partition
        (invariant 1 / D68); it is never written to a shared index. Keyed by ``doc`` so a
        re-index is idempotent (the journal's replay substrate, invariant 24)."""
        ...

    def search(
        self,
        query: str,
        *,
        within: Sensitivity,
        domains: frozenset[Domain] = frozenset(),
        top_k: int = 10,
    ) -> list[SearchHit]:
        """Search a SINGLE sensitivity partition (``within``), optionally filtered to
        ``domains`` (D72). A search ``within`` ``sensible`` stays entirely local; partitions
        are never crossed implicitly (cloisonnement, D54)."""
        ...

    def invalidate(self, doc: DocId) -> None:
        """Drop a document's terms (a derivative purge; the truth is untouched, D56)."""
        ...
