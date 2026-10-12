"""Retriever (D65) — hybrid retrieval with an explicit low-recall admission.

Reads over the two retrieval legs and fuses them: the dense
:class:`~mnemosyne.ports.vectorindex.VectorIndex` (meaning) and the lexical
:class:`~mnemosyne.ports.keywordindex.KeywordIndex` (BM25 terms), combined by Reciprocal
Rank Fusion (RRF, D68). The keyword leg is OPTIONAL: with none wired the Retriever is
dense-only (its original LOT 4b behaviour); wired, it is hybrid (③-2b).

The barrier this fixes is invariant 14: an insufficient retrieval ADMITS ("I don't know")
rather than inventing a confident answer (D100). The admission is decided on the CONFIDENCE
signals — the dense score clearing a recall floor (``min_score``), or, in hybrid mode, a
lexical (BM25) match — NOT on the fused RRF score (a rank score, not a similarity). When
neither leg is confident the result carries no hits and ``admitted_low_recall`` is True.

**Per-domain floor (D139).** ``min_score`` (the embedder-declared default, D68) is the floor
EVERY domain uses until it earns its own — bge-m3's 0.53 was calibrated on a finance-only
golden set (③-2b) and does not generalise across domains as the corpus diversifies (D140). A
domain's calibrated floor lives in the protected policy zone (:attr:`~mnemosyne.config.Policy.
recall_floor_by_domain`, keyed there so it stays a config concern, never a hard-coded dict in
this module) and is resolved PER CALL from ``retrieve``'s own ``domains`` argument — never at
construction, since one ``Retriever`` instance serves every query domain over its lifetime. A
query naming zero or several domains resolves to the ``min_score`` default (D139 keys the floor
on a FACT of the query, never a guess at which of several domains should win); an LLM
sufficiency backstop below the floor is a design-noted seam, materialised just-in-time (D126)
— not built here, since no domain has a calibrated floor yet to make it reachable.

Retrieval stays within a single sensitivity partition (invariant 1 / D54). The reranker leg
plugs in above this port (LOT 5). Code & docstrings English (D117).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from ..config import Policy
from ..ports import (
    DocId,
    Domain,
    Embedder,
    GovernanceLabel,
    KeywordIndex,
    SearchHit,
    Sensitivity,
    VectorIndex,
)


@dataclass(frozen=True, slots=True)
class RetrievalResult:
    """A retrieval outcome: confident hits, or an explicit low-recall admission.

    ``admitted_low_recall`` True ⇒ the retrieval was insufficient and ``hits`` is
    empty — Mnémosyne says "I don't know" instead of inventing (invariant 14)."""

    hits: tuple[SearchHit, ...]
    admitted_low_recall: bool
    reason: str


#: RRF damping constant (D68). The standard 60: a doc's fused score is Σ 1/(k + rank) over the
#: legs it appears in, so top ranks dominate while lower ranks still contribute.
_RRF_K = 60


class Retriever:
    """Hybrid (dense ⊕ keyword) retrieval with a low-recall admission gate (invariant 14).

    Dense-only when no keyword leg is wired (``keyword=None``); hybrid when one is (③-2b)."""

    __slots__ = ("_vector", "_embedder", "_keyword", "_min_score", "_floor_by_domain")

    def __init__(
        self,
        vector: VectorIndex,
        embedder: Embedder,
        *,
        keyword: KeywordIndex | None = None,
        min_score: float | None = None,
        recall_floor_by_domain: Mapping[Domain, float] | None = None,
    ) -> None:
        # The floor is a property of the embedder's score distribution (invariant 14): take the
        # embedder's declared recall_floor unless a caller overrides it. recall_floor is a REQUIRED
        # part of the Embedder port (D68), so a new encoder can never silently inherit a wrong floor.
        # This is the DEFAULT every domain falls back to (D139) — see _floor_for.
        floor = min_score if min_score is not None else embedder.recall_floor
        if not 0.0 <= floor <= 1.0:
            raise ValueError(f"min_score must be in [0, 1], got {floor}")
        self._vector = vector
        self._embedder = embedder
        self._keyword = keyword
        self._min_score = floor
        # D139 — per-domain recalibration, resolved PER CALL in retrieve() (never fixed here at
        # construction: one instance serves every query domain). Empty by default ⇒ every domain
        # falls back to _min_score, the pre-D139 shape (retro-compatible).
        self._floor_by_domain = (
            MappingProxyType(dict(recall_floor_by_domain))
            if recall_floor_by_domain is not None
            else MappingProxyType({})
        )

    @classmethod
    def from_policy(
        cls,
        policy: Policy,
        vector: VectorIndex,
        embedder: Embedder,
        *,
        keyword: KeywordIndex | None = None,
    ) -> Retriever:
        """Build a Retriever whose per-domain recall floor is read from the protected zone
        (D139, SE4) — the calibrated table is *configured*, not hard-coded in this module. The
        embedder's declared ``recall_floor`` stays the default every un-calibrated domain (and
        the whole policy's empty-by-default zone, D126) falls back to (retro-compatible)."""
        return cls(
            vector,
            embedder,
            keyword=keyword,
            recall_floor_by_domain=policy.recall_floor_by_domain,
        )

    @property
    def min_score(self) -> float:
        """The DEFAULT recall floor (invariant 14): what an un-calibrated domain — or a query
        naming zero / several domains — resolves to. A single calibrated domain in a
        ``retrieve`` call may resolve to a DIFFERENT floor (D139); this property reports only
        the default, unchanged from the pre-D139 embedder-declared shape."""
        return self._min_score

    def retrieve(
        self,
        query: str,
        *,
        within: Sensitivity,
        domains: frozenset[Domain] = frozenset(),
        top_k: int = 10,
    ) -> RetrievalResult:
        """Retrieve within one sensitivity partition, ADMITTING low recall rather than
        returning a confident hit where there is none (invariant 14).

        Dense-only: every returned hit clears the floor; if none does, "I don't know".
        Hybrid: the dense floor OR a lexical (BM25) match makes it confident, and the two legs
        are fused by RRF; if neither is confident, "I don't know". Searches only ``within``
        (partitions are never crossed, invariant 1 / D54). The floor itself is resolved PER
        CALL from ``domains`` (D139, see :meth:`_floor_for`) — a calibrated single domain can
        gate this call stricter or laxer than :attr:`min_score` without touching another call."""
        floor = self._floor_for(domains)
        embedding = self._embedder.embed([query])[0]
        dense = self._vector.search(embedding, within=within, domains=domains, top_k=top_k)
        if self._keyword is None:
            return self._admit_dense_only(dense, floor=floor)
        keyword = self._keyword.search(query, within=within, domains=domains, top_k=top_k)
        return self._admit_hybrid(dense, keyword, top_k=top_k, floor=floor)

    def _floor_for(self, domains: frozenset[Domain]) -> float:
        """Resolve the recall floor for THIS call (D139, invariant 14): a query naming EXACTLY
        one domain that has an earned entry in :attr:`_floor_by_domain` uses it; a query naming
        zero domains, several, or one with no calibrated entry, uses :attr:`min_score` (the
        embedder-declared default) — the identical, retro-compatible behaviour of every domain
        before D139. Several domains never average or pick a winner: the floor keys on a FACT of
        the query (which single domain it names), never a guess among ambiguous candidates."""
        if len(domains) != 1:
            return self._min_score
        (only,) = domains
        return self._floor_by_domain.get(only, self._min_score)

    def _admit_dense_only(self, dense: list[SearchHit], *, floor: float) -> RetrievalResult:
        """Dense-only admission (invariant 14): return the hits clearing ``floor``, else 'I
        don't know'. Preserves the original LOT 4b contract."""
        cleared = tuple(hit for hit in dense if hit.score >= floor)
        if not cleared:
            best = dense[0].score if dense else 0.0
            return RetrievalResult(
                hits=(),
                admitted_low_recall=True,
                reason=(
                    f"best recall {best:.3f} < floor {floor:.3f} — "
                    "no confident memory (invariant 14)"
                ),
            )
        return RetrievalResult(
            hits=cleared, admitted_low_recall=False, reason="recall cleared the floor"
        )

    def _admit_hybrid(
        self, dense: list[SearchHit], keyword: list[SearchHit], *, top_k: int, floor: float
    ) -> RetrievalResult:
        """Hybrid admission + RRF fusion (D68), decided PER-DOC (invariant 14). A doc is admitted
        iff it ITSELF cleared ``floor`` (dense) or matched the lexical leg; the admitted docs are
        then fused by RRF. Opening the gate on one confident doc never drags sub-floor dense noise
        (a doc that cleared neither) into the context — that noise is dropped, never fed to
        generation (D100). If no doc is admissible, admit low recall — never invent. The
        keyword-match signal is provisional (a golden set tunes precision at ②)."""
        dense_cleared = tuple(hit for hit in dense if hit.score >= floor)
        if not dense_cleared and not keyword:
            best = dense[0].score if dense else 0.0
            return RetrievalResult(
                hits=(),
                admitted_low_recall=True,
                reason=(
                    f"best dense recall {best:.3f} < floor {floor:.3f} and no keyword "
                    "match — no confident memory (invariant 14)"
                ),
            )
        # Per-doc admission (invariant 14): cleared-the-floor (dense) OR matched (keyword). RRF ranks
        # this set; a sub-floor dense hit with no lexical match is NOT admitted even with the gate open.
        admitted = {hit.doc for hit in dense_cleared} | {hit.doc for hit in keyword}
        # A passage ordinal is trustworthy ONLY from a dense hit that CLEARED the floor (audit M-1a):
        # a sub-floor dense hit is noise the gate drops (invariant 14), so its argmax passage must not
        # steer the evidence. A doc admitted by the lexical leg alone (or a sub-floor dense doc) carries
        # NO ordinal here ⇒ its passage is resolved lexically at read (select_passage), aligned with the
        # very signal that admitted it — never sub-floor dense noise.
        trusted_chunks = {hit.doc: hit.chunk for hit in dense_cleared}
        fused = _rrf_fuse(dense, keyword, admit=admitted, chunks=trusted_chunks, top_k=top_k)
        return RetrievalResult(
            hits=fused,
            admitted_low_recall=False,
            reason=f"hybrid recall — {len(admitted)} admitted (dense floor ⊕ lexical), RRF-ranked",
        )


def _rrf_fuse(
    dense: list[SearchHit],
    keyword: list[SearchHit],
    *,
    admit: set[DocId],
    chunks: dict[DocId, int | None],
    top_k: int,
) -> tuple[SearchHit, ...]:
    """Reciprocal Rank Fusion of the two ranked legs (D68 hybrid retrieval), restricted to the
    ADMITTED docs (invariant 14 per-doc, see :meth:`Retriever._admit_hybrid`).

    Each doc's fused score is Σ 1/(``_RRF_K`` + rank) over the legs it appears in (rank 1-based),
    so agreement across legs ranks a doc high while either leg alone still contributes. A doc keeps
    its true rank within a leg (non-admitted docs still occupy a rank), but only ADMITTED docs are
    emitted. The fused score REPLACES the per-leg score (dense cosine / BM25); the low-recall
    admission is decided separately (never on this fused score). Each fused hit carries the passage
    ordinal supplied in ``chunks`` — populated ONLY from dense hits that cleared the floor (audit
    M-1a); a doc admitted by the lexical leg alone carries ``None`` and resolves its passage lexically
    at read (D136), so the packed passage always comes from the signal that admitted the doc, never
    sub-floor dense noise. ``recall`` thus packs a passage, never the whole document."""
    scores: dict[DocId, float] = {}
    labels: dict[DocId, GovernanceLabel] = {}
    for ranked in (dense, keyword):
        for rank, hit in enumerate(ranked, start=1):
            scores[hit.doc] = scores.get(hit.doc, 0.0) + 1.0 / (_RRF_K + rank)
            labels.setdefault(hit.doc, hit.label)
    fused = [
        SearchHit(doc=doc, score=score, label=labels[doc], chunk=chunks.get(doc))
        for doc, score in scores.items()
        if doc in admit
    ]
    fused.sort(key=lambda hit: hit.score, reverse=True)
    return tuple(fused[:top_k])
