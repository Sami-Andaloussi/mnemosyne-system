"""InMemoryKeywordIndex (D68) - lexical retrieval, PARTITIONED BY SENSITIVITY.

A light in-memory stand-in for the keyword leg (default brick: **tantivy**, D68),
implementing :class:`~mnemosyne.ports.keywordindex.KeywordIndex`. Like the dense
:class:`~mnemosyne.stores.vector.InMemoryVectorIndex`, the security-critical property
carries over from the port: the index is **partitioned by sensitivity**, and a
``sensible`` search stays entirely in its own isolated partition (invariant 1 / D68);
partitions are never crossed implicitly (cloisonnement, D54).

Scoring is a deterministic term-frequency stand-in for BM25: a document scores by the
count of the query's terms it contains, so shared vocabulary ranks high and disjoint
content scores 0 (no spurious hit) - enough gradient for RRF fusion and the hybrid
low-recall gate (invariant 14) without pulling in the real engine. The real tantivy
index swaps in behind the same port (D68 / D113). Code & docstrings English (D117).
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass

from ..ports import DocId, Domain, GovernanceLabel, SearchHit, Sensitivity

_WORD = re.compile(r"\w+", re.UNICODE)


def _tokens(text: str) -> Counter[str]:
    """Lowercased word-token multiset (deterministic, no engine)."""
    return Counter(m.group(0) for m in _WORD.finditer(text.lower()))


@dataclass(frozen=True, slots=True)
class _Entry:
    tokens: Counter[str]
    label: GovernanceLabel


class InMemoryKeywordIndex:
    """In-memory tantivy stand-in, PARTITIONED BY SENSITIVITY (invariant 1 / D68).

    Each sensitivity owns a separate partition; ``sensible`` is its own physically isolated
    store, and a search is scoped to ONE partition via ``within`` - partitions are never
    crossed implicitly (cloisonnement, D54). Satisfies :class:`KeywordIndex`."""

    __slots__ = ("_partitions",)

    def __init__(self) -> None:
        self._partitions: dict[Sensitivity, dict[DocId, _Entry]] = {s: {} for s in Sensitivity}

    def index(self, doc: DocId, text: str, label: GovernanceLabel) -> None:
        """Index ``doc``'s text into the partition implied by ``label.sensitivity`` - and ONLY
        there (invariant 1). Keyed by ``doc`` => a re-index is idempotent (invariant 24)."""
        self._partitions[label.sensitivity][doc] = _Entry(tokens=_tokens(text), label=label)

    def search(
        self,
        query: str,
        *,
        within: Sensitivity,
        domains: frozenset[Domain] = frozenset(),
        top_k: int = 10,
    ) -> list[SearchHit]:
        """Search a SINGLE partition (``within``), optionally narrowed to ``domains`` (D72).

        A document scores by the term-frequency of the query's terms it contains; a zero
        score is no hit. A search ``within`` ``sensible`` stays entirely local (invariant 1)."""
        query_terms = set(_tokens(query))
        hits: list[SearchHit] = []
        for doc, entry in self._partitions[within].items():
            if domains and not (domains & entry.label.domains):
                continue
            score = float(sum(entry.tokens[term] for term in query_terms))
            if score > 0.0:
                hits.append(SearchHit(doc=doc, score=score, label=entry.label))
        hits.sort(key=lambda hit: hit.score, reverse=True)
        return hits[:top_k]

    def invalidate(self, doc: DocId) -> None:
        """Purge a document's terms from every partition - a derivative purge; the truth is
        untouched and the index rebuilds from it (D56)."""
        for partition in self._partitions.values():
            partition.pop(doc, None)

    def contains(self, doc: DocId) -> bool:
        """Whether ``doc`` is indexed in any partition (the integration witness, inv. 24)."""
        return any(doc in partition for partition in self._partitions.values())
