"""RerankedRetriever (D68 / D61 stage 6 / LOT 5) — the cross-encoder rerank leg, ABOVE the port.

Stage 6 of the documentary pipeline (D61): a decorator that wraps the base
:class:`~mnemosyne.stores.retrieval.Retriever` (a pure dense ⊕ BM25 fusion primitive) and, when a
:class:`~mnemosyne.ports.reranker.Reranker` is wired, re-orders its shortlist by cross-encoder
relevance — "retrieve WIDE (a candidate pool), rerank NARROW (top_k)". It exposes the SAME
``retrieve`` surface as the base, so a consumer reranks transparently through ONE wrapping
(:func:`wrap_reranked`, single-source, D119) with ZERO call-site changes. This increment wires it
at the FACADE (:class:`~mnemosyne.api.core_api.CoreApi` — ``search`` and ``recall``); the agent's
``search_memory`` tool is deliberately left un-reranked for now (an orthogonal follow-up, though its
summary-hit read is now packed through the shared governed summary read, D65). With no reranker wired
the base is returned bare (no wrapper), so retrieval is byte-identical to pre-LOT-5 (zero regression, D126).

**Invariants preserved.** The decorator only ever REORDERS and TRUNCATES a shortlist the base
already produced: it never re-opens the invariant-14 admission (a low-recall result passes
straight through), never crosses a sensitivity partition (invariant 1 — it inherits the base's
``within`` confinement), and adds no bubble/domain frontier (invariant 3 / 4 stay with the
consumer's ``may_read``, applied AFTER, unchanged). It reads passage TEXT only to SCORE, locally
(invariant 1 / D66) — the text never leaves; the output contract is unchanged (only the order and
the ``reason`` differ). Code & docstrings English (D117).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from typing import Protocol, runtime_checkable

from ..ingest.chunk import select_passage
from ..ports import Domain, Reranker, SearchHit, Sensitivity
from .raptor import RaptorStore, is_raptor_summary
from .retrieval import RetrievalResult

#: The wide candidate pool retrieved before reranking (D68 stage 6). Meaningfully larger than a
#: typical ``top_k`` (facade 10, search_memory 6) so the cross-encoder can promote a genuinely
#: relevant passage the RRF ranked low — the whole point of "retrieve wide, rerank narrow". An
#: operational RAG constant, kept WITH the rerank leg (mirroring the embedder's ``_ENCODE_BATCH``),
#: not a Guard concern; overridable per construction if a run shows it too tight or too broad.
_RERANK_POOL = 40


@runtime_checkable
class RetrieverLike(Protocol):
    """The retrieval surface both the base :class:`~mnemosyne.stores.retrieval.Retriever` and
    :class:`RerankedRetriever` satisfy — so the reranked leg substitutes wherever a retriever is
    expected (``search`` / ``recall`` / ``search_memory``) without a call-site change."""

    def retrieve(
        self,
        query: str,
        *,
        within: Sensitivity,
        domains: frozenset[Domain] = frozenset(),
        top_k: int = 10,
    ) -> RetrievalResult: ...


class RerankedRetriever:
    """Wraps a retriever with a cross-encoder rerank leg (D61 stage 6 / D68); same ``retrieve`` surface.

    Retrieves a WIDE pool from the base, then the reranker re-orders it and it is narrowed to
    ``top_k``. Abstains gracefully (reranker returns ``None`` ⇒ the RRF order is kept, only
    truncated), and passes a low-recall admission straight through (invariant 14 is the base's to
    decide, never re-opened here)."""

    __slots__ = ("_base", "_reranker", "_resolve_text", "_pool")

    def __init__(
        self,
        base: RetrieverLike,
        reranker: Reranker,
        *,
        resolve_text: Callable[[SearchHit, str], str],
        pool: int = _RERANK_POOL,
    ) -> None:
        self._base = base
        self._reranker = reranker
        self._resolve_text = resolve_text
        self._pool = pool

    def retrieve(
        self,
        query: str,
        *,
        within: Sensitivity,
        domains: frozenset[Domain] = frozenset(),
        top_k: int = 10,
    ) -> RetrievalResult:
        """Retrieve a wide pool, rerank by (query, passage) relevance, return the top_k (D68).

        The base decides admission (invariant 14): a low-recall result — or an empty shortlist — is
        returned unchanged (nothing to reorder). Otherwise the reranker scores every candidate; on
        an abstention (``None``) the RRF order is kept and merely truncated to ``top_k``; on scores,
        the shortlist is reordered descending and truncated. Partition confinement (invariant 1) is
        the base's; the bubble/domain frontier (invariant 3 / 4) stays with the consumer, applied
        after — the rerank only changes WHICH admitted, in-partition hits fill ``top_k``, never
        whether one is readable."""
        pool = max(top_k, self._pool)
        result = self._base.retrieve(query, within=within, domains=domains, top_k=pool)
        if result.admitted_low_recall or not result.hits:
            return result  # invariant 14 admission stands; nothing to reorder
        passages = [self._resolve_text(hit, query) for hit in result.hits]
        try:
            scores = self._reranker.rerank(query, passages)
        except Exception:  # noqa: BLE001 - ANY cross-encoder failure degrades to no-rerank, never a crash
            scores = None
        # Abstention (NullReranker), a raised cross-encoder — OOM / device / NaN / a count mismatch,
        # netted just above — OR a malformed score vector (wrong length) ⇒ keep the RRF order, merely
        # narrowed to top_k (fail-safe, D100): a broken or opinion-less reranker degrades to no-rerank,
        # never an IndexError / mis-aligned reorder / crash. The SAME discipline every other model seam
        # follows (fact / structural / source / raptor are all netted at their call sites).
        if scores is None or len(scores) != len(result.hits):
            return replace(result, hits=result.hits[:top_k])
        order = sorted(range(len(result.hits)), key=lambda i: scores[i], reverse=True)
        # MAJEUR-2 (resolved): this decorator is subject-agnostic, so it only REORDERS the admitted
        # in-partition pool and narrows to the top_k it was ASKED for — it never runs may_read. The
        # readable-recall repair lives in the READ SURFACES (:data:`~mnemosyne.stores.governed_read.
        # READ_POOL`): the facade (search / recall) AND the agent's search_memory over-fetch a WIDE
        # top_k here, then truncate to the caller's real top_k AFTER may_read — so a to-be-withheld hit
        # the cross-encoder ranks high can no longer evict a readable one. Passed a wide top_k, this
        # returns the full reranked pool for the surface to filter; passed a small one, it narrows here
        # as before. Never a leak either way (the foreigner stays withheld); the cut is honest.
        reranked = tuple(result.hits[i] for i in order[:top_k])
        # NB the reranked hits keep their upstream fusion score (the ORDER reflects the cross-encoder,
        # the score field still reports RRF): no consumer re-sorts by score today (search / recall
        # preserve this order), so the two stay intentionally distinct rather than overwriting a
        # meaningful fusion score with a raw cross-encoder logit (audit NIT-1).
        return replace(
            result,
            hits=reranked,
            reason=result.reason + f" — reranked (cross-encoder {self._reranker.model_id}, D68)",
        )


def passage_resolver(truth: object, raptor: RaptorStore | None) -> Callable[[SearchHit, str], str]:
    """Build the ``resolve_text`` closure the reranker scores over — summary-aware, never crashes.

    A LEAF hit resolves to its matched passage (the SAME
    :func:`~mnemosyne.ingest.chunk.select_passage` the packer uses, D136 — one passage-selection
    rule); a RAPTOR summary hit (Ch.5, collapsed-tree: summaries share the index) resolves to its
    synopsis text from the store. Any unresolvable hit — a summary with no store wired, a node swept
    meanwhile, a truth read that raises — degrades to an EMPTY string (the cross-encoder simply
    scores it low), never a crash out of the retrieval path (D126 / D100). Reading passage text here
    is purely for SCORING and stays local (invariant 1); the text never leaves the process."""

    def resolve(hit: SearchHit, query: str) -> str:
        try:
            if is_raptor_summary(hit.doc):
                if raptor is None:
                    return ""
                return raptor.get(hit.doc).text
            whole = truth.read(hit.doc)  # type: ignore[attr-defined]  # a TruthReader (duck-typed)
            return select_passage(whole.payload, query, ordinal=hit.chunk)
        except (KeyError, LookupError, ValueError, OSError):
            return ""  # unresolvable ⇒ scored low, never a crash (D126)

    return resolve


def wrap_reranked(
    base: RetrieverLike,
    reranker: Reranker | None,
    *,
    truth: object,
    raptor: RaptorStore | None,
) -> RetrieverLike:
    """Wrap ``base`` with the rerank leg IF a reranker is wired, else return it bare (D126).

    The ONE composer of the rerank leg (single-source, D119) — a helper any retrieval site can wrap
    with, so the composition rule lives in exactly one place. This increment calls it at the facade
    (:class:`~mnemosyne.api.core_api.CoreApi`); the agent's ``search_memory`` tool is not wrapped yet
    (an orthogonal follow-up). ``None`` reranker ⇒ no wrapper ⇒ byte-identical to pre-LOT-5 (zero
    regression)."""
    if reranker is None:
        return base
    return RerankedRetriever(base, reranker, resolve_text=passage_resolver(truth, raptor))
