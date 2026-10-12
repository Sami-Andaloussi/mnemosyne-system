"""Reranker (D68 / D61 stage 6) - the cross-encoder that re-scores retrieval candidates.

Hybrid retrieval (dense ⊕ BM25, RRF-fused by :class:`~mnemosyne.stores.retrieval.Retriever`)
produces a candidate shortlist ranked by a FAST signal. Stage 6 of the documentary pipeline
(D61) then re-orders that shortlist with a SLOW, precise signal: a cross-encoder that reads the
query and each candidate passage TOGETHER and scores their relevance - "retrieve wide, rerank
narrow". The frozen default brick is **bge-reranker-v2-m3** (BAAI, MIT), paired with the bge-m3
embedder (see ``system/config/oss_registry.md``, D68); the port keeps it swap-able.

**Governance - a pure LOCAL transform, not a Guard frontier.** The reranker only ever sees a
shortlist that :class:`~mnemosyne.stores.retrieval.Retriever` has ALREADY confined to one
sensitivity partition (invariant 1 / D54) and admitted (invariant 14 / D100). It reorders that
shortlist; it GENERATES nothing, STORES nothing, and CROSSES no frontier the retrieval has not
already cleared - so, exactly like the :class:`~mnemosyne.ports.embedder.Embedder` (and unlike
the RAPTOR summarizer, which mints derived content behind a ``MODEL_CALL`` grant), it is NOT a
guarded model call. It reads passage TEXT, so for ``sensible`` content it MUST run locally by
construction (invariant 1 / D66): an automatic process, therefore never a cloud path.

**Abstention (D126).** ``rerank`` may return ``None`` - "no opinion": the caller keeps the
upstream RRF order unchanged. This is how the seam stays inert and brick-free until the model is
installed at (3) ignition (:class:`NullReranker`), byte-identical to pre-LOT-5 retrieval.

Decisions: D68 (frozen swap-able default)  -  D61 (stage 6 of the documentary pipeline)  -  D98 (OSS
under our rules). Invariant carried: substrate of 1 (local ``sensible`` reranking). Code &
docstrings English (D117).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, runtime_checkable


@runtime_checkable
class Reranker(Protocol):
    """Re-scores (query, passage) relevance with a cross-encoder; the model stays swap-able (D68)."""

    @property
    def model_id(self) -> str:
        """Identity of the underlying model (frozen default: bge-reranker-v2-m3, D68)."""
        ...

    def rerank(self, query: str, passages: Sequence[str]) -> Sequence[float] | None:
        """Score each ``(query, passage)`` pair - one float per passage, higher = more relevant.

        The caller hands ONLY an already-authorized, in-partition shortlist (the reranker adds no
        frontier - see the module docstring); for ``sensible`` content this MUST run locally
        (invariant 1 / D66). Returns one score per input passage (same length, same order), or
        ``None`` to ABSTAIN - the caller then keeps the upstream RRF order (D126, brick-free)."""
        ...


class NullReranker:
    """A reranker that always abstains (D126) - the inert default until the model lands at (3).

    Wired-but-weightless: with no cross-encoder installed, the seam is real but expresses no
    opinion, so :class:`~mnemosyne.stores.reranked_retriever.RerankedRetriever` keeps the RRF
    order byte-identical to pre-LOT-5 retrieval. Mirrors the abstaining
    :class:`~mnemosyne.ingest.raptor_summarize.NullRaptorSummarizer` (Ch.5's other brick-free seam)."""

    __slots__ = ()

    @property
    def model_id(self) -> str:
        return "null-reranker"

    def rerank(self, query: str, passages: Sequence[str]) -> Sequence[float] | None:
        """Abstain unconditionally (``None``) - the RRF order stands (D126)."""
        return None
