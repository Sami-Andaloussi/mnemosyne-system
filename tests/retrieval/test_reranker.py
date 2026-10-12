"""Reranker tests (D68 / D61 stage 6 / LOT 5) - the cross-encoder rerank leg that REORDERS an
already-retrieved, already-in-partition, already-admitted shortlist by (query, passage) relevance
("retrieve WIDE, rerank NARROW"), checked against light doubles WITHOUT the installed brick (D126
decoupling): the Reranker port conformance (NullReranker / BgeReranker), the BgeReranker adapter's
pairing / sub-batching / count validation, the RerankedRetriever decorator's wide-pool / reorder /
passthrough / abstention behaviour, wrap_reranked's single-source composition (D119), passage_
resolver's leaf / summary / never-raises resolution, and the CoreApi integration proving stage 6 is
live on the facade while cloisonnement and invariant 14 stay unchanged. Producer ≠ verifier (D75):
an isolated audit checks this independently. Code & docstrings English (D117).
"""

from __future__ import annotations

from collections.abc import Sequence

import pytest

from mnemosyne.api import CoreApi
from mnemosyne.config import Policy
from mnemosyne.ingest.chunk import select_passage
from mnemosyne.ingest.router import QueryKind
from mnemosyne.ports import (
    Bubble,
    DocId,
    Domain,
    Envelope,
    GovernanceLabel,
    NullReranker,
    Reranker,
    Sensitivity,
    SearchHit,
)
from mnemosyne.runtime import bootstrap
from mnemosyne.stores import (
    BgeReranker,
    InMemoryVectorIndex,
    MarkdownTruthStore,
    RaptorNode,
    RaptorStore,
    RerankedRetriever,
    Retriever,
    RetrievalResult,
    RetrieverLike,
    StubEmbedder,
    passage_resolver,
    raptor_doc_id,
    wrap_reranked,
)
from mnemosyne.stores.governed_read import READ_POOL
from mnemosyne.stores.reranked_retriever import _RERANK_POOL

# --------------------------------------------------------------------------- #
# Shared builders (mirrors tests/retrieval/test_stores.py's own light doubles)  #
# --------------------------------------------------------------------------- #


def _label(sensitivity: Sensitivity = Sensitivity.PUBLIC, bubble: str = "b") -> GovernanceLabel:
    return GovernanceLabel(sensitivity=sensitivity, bubble=Bubble(bubble))


def _hit(doc: str, score: float = 1.0, *, chunk: int | None = None) -> SearchHit:
    return SearchHit(DocId(doc), score, _label(), chunk)


def _result(
    hits: Sequence[SearchHit] = (),
    *,
    admitted_low_recall: bool = False,
    reason: str = "base reason",
) -> RetrievalResult:
    return RetrievalResult(hits=tuple(hits), admitted_low_recall=admitted_low_recall, reason=reason)


def _doc_text(hit: SearchHit, query: str) -> str:
    """A trivial ``resolve_text`` double: the passage IS the doc id - lets a fake reranker's score
    table key directly on which hit it was handed, no truth store needed for decorator-only tests."""
    return str(hit.doc)


def _fake_score(pairs: Sequence[tuple[str, str]]) -> Sequence[float]:
    return [float(len(passage)) for _query, passage in pairs]


class _FakeBase:
    """A retriever double (D126): returns a CANNED :class:`RetrievalResult` and records every
    call's arguments, so the decorator's WIDE-pool request can be spied without a real vector index
    - mirrors ``tests/retrieval/test_stores.py``'s own ``_FixedHits`` double."""

    def __init__(self, result: RetrievalResult) -> None:
        self._result = result
        self.calls: list[dict[str, object]] = []

    def retrieve(
        self,
        query: str,
        *,
        within: Sensitivity,
        domains: frozenset[Domain] = frozenset(),
        top_k: int = 10,
    ) -> RetrievalResult:
        self.calls.append({"query": query, "within": within, "domains": domains, "top_k": top_k})
        return self._result


class _RankedRetriever:
    """A retriever double holding a FULL ranked shortlist and returning ``ranked[:top_k]`` - it
    HONORS ``top_k`` exactly as the real base does (truncating a wider pool), so a facade test can
    prove the MAJEUR-2 over-fetch actually reaches hits ranked past a small ``top_k``. Records the
    ``top_k`` it was asked for."""

    def __init__(self, ranked: Sequence[SearchHit]) -> None:
        self._ranked = tuple(ranked)
        self.calls: list[int] = []

    def retrieve(
        self,
        query: str,  # noqa: ARG002 - the double is order-fixed, query-independent
        *,
        within: Sensitivity,  # noqa: ARG002
        domains: frozenset[Domain] = frozenset(),  # noqa: ARG002
        top_k: int = 10,
    ) -> RetrievalResult:
        self.calls.append(top_k)
        return RetrievalResult(
            hits=self._ranked[:top_k], admitted_low_recall=False, reason="ranked double"
        )


class _ScoringReranker:
    """A reranker double: scores each passage by a fixed lookup table, records every call
    (query, passages) for inspection, and can be told to ABSTAIN (``None``, mirrors NullReranker)."""

    def __init__(
        self,
        scores: dict[str, float] | None = None,
        *,
        abstain: bool = False,
        model_id: str = "fake-cross-encoder",
    ) -> None:
        self._scores = scores or {}
        self._abstain = abstain
        self.model_id = model_id
        self.calls: list[tuple[str, tuple[str, ...]]] = []

    def rerank(self, query: str, passages: Sequence[str]) -> Sequence[float] | None:
        self.calls.append((query, tuple(passages)))
        if self._abstain:
            return None
        return [self._scores.get(p, 0.0) for p in passages]


class _ReversingReranker:
    """A content-blind reranker double that always REVERSES the incoming shortlist - deterministic,
    so a CoreApi integration test can prove stage 6 actually reorders the facade's output regardless
    of what the base retriever's own order happened to be."""

    model_id = "reversing-fake"

    def rerank(self, query: str, passages: Sequence[str]) -> Sequence[float] | None:
        # position 0 gets the LOWEST score, the last position the HIGHEST => sorting descending by
        # score exactly reverses the incoming order, with no ties (strictly increasing scores).
        return [float(i) for i in range(len(passages))]


class _RaisingReranker:
    """A reranker double that RAISES - models a real cross-encoder blowing up (OOM / device / NaN, or
    BgeReranker's own ValueError on a count mismatch). The decorator must net it and degrade to
    no-rerank, never let it crash the read path (audit MAJEUR-1)."""

    model_id = "raising-fake"

    def rerank(self, query: str, passages: Sequence[str]) -> Sequence[float] | None:
        raise RuntimeError("cross-encoder blew up (OOM / device / NaN)")


def _policy(declared_domains: dict[Bubble, frozenset[Domain]] | None = None) -> Policy:
    """A minimal, deny-by-default test policy (mirrors ``tests/platform/test_api.py``'s own helper)
    - only ``declared_domains`` varies across the CoreApi integration tests below."""
    return Policy(
        profile="test",
        canal_a_auto=frozenset(),
        egress_allowlist=frozenset(),
        contracts=(),
        declared_domains=declared_domains or {},
        bounds={
            "queue_capacity": 8,
            "concurrency": 1,
            "intake_capacity": 8,
            "intake_source_bytes": 268435456,
        },
        quotas={},
    )


# ==================================== 1. Port conformance =============================== #


def test_bge_reranker_and_null_reranker_satisfy_the_reranker_port() -> None:
    assert isinstance(BgeReranker(_fake_score), Reranker)  # runtime_checkable Protocol surface
    assert isinstance(NullReranker(), Reranker)
    assert NullReranker().model_id == "null-reranker"
    assert NullReranker().rerank("q", ["a", "b"]) is None  # D126: wired but weightless, no opinion


# ================= 2. BgeReranker adapter (against a double, no brick, D126) ============ #


def test_bge_reranker_returns_one_score_per_passage_in_order() -> None:
    def score(pairs: Sequence[tuple[str, str]]) -> Sequence[float]:
        return [float(len(passage)) for _query, passage in pairs]

    out = BgeReranker(score).rerank("q", ["a", "bb", "ccc"])
    assert out == [1.0, 2.0, 3.0]  # one float per passage, same order as the input


def test_bge_reranker_empty_passages_returns_empty_without_calling_score() -> None:
    calls: list[Sequence[tuple[str, str]]] = []

    def score(pairs: Sequence[tuple[str, str]]) -> Sequence[float]:
        calls.append(pairs)
        return [0.0] * len(pairs)

    assert BgeReranker(score).rerank("q", []) == ()
    assert calls == []  # an empty shortlist never even reaches the injected brick


def test_bge_reranker_a_wrong_score_count_raises_value_error() -> None:
    def bad_score(pairs: Sequence[tuple[str, str]]) -> Sequence[float]:
        return [0.0]  # always one score, however many pairs were handed

    with pytest.raises(ValueError):
        BgeReranker(bad_score).rerank("q", ["a", "b"])


def test_bge_reranker_sub_batches_at_most_16_pairs_per_score_call() -> None:
    calls: list[int] = []

    def counting_score(pairs: Sequence[tuple[str, str]]) -> Sequence[float]:
        calls.append(len(pairs))
        return [float(i) for i in range(len(pairs))]

    total = 16 * 3 + 5  # deliberately not a multiple of the sub-batch size
    out = BgeReranker(counting_score).rerank("q", [f"passage {i}" for i in range(total)])
    assert len(out) == total
    assert calls == [16, 16, 16, 5]
    assert all(n <= 16 for n in calls)  # a rerank pool never hands the brick more than 16 pairs


def test_bge_reranker_carries_its_model_id() -> None:
    assert BgeReranker(_fake_score).model_id == "bge-reranker-v2-m3"  # the frozen default (D68)
    assert (
        BgeReranker(_fake_score, model_id="custom-cross-encoder").model_id == "custom-cross-encoder"
    )


# ==================================== 3. RerankedRetriever decorator ===================== #


def test_reranked_retriever_asks_the_base_for_the_wide_pool_by_default() -> None:
    # "retrieve WIDE, rerank NARROW" (D68): the base always sees max(top_k, pool); the default pool
    # is the module's own frozen constant, never a re-hard-coded magic number in this test.
    assert _RERANK_POOL == 40
    narrow = _FakeBase(_result([_hit("a")]))
    RerankedRetriever(narrow, _ScoringReranker(), resolve_text=_doc_text).retrieve(
        "q", within=Sensitivity.PUBLIC, top_k=5
    )
    assert narrow.calls[0]["top_k"] == _RERANK_POOL  # the pool dominates a small top_k

    wide = _FakeBase(_result([_hit("a")]))
    RerankedRetriever(wide, _ScoringReranker(), resolve_text=_doc_text).retrieve(
        "q", within=Sensitivity.PUBLIC, top_k=100
    )
    assert wide.calls[0]["top_k"] == 100  # a top_k exceeding the pool dominates instead


def test_reranked_retriever_reorders_by_descending_score_and_truncates_to_top_k() -> None:
    hits = [_hit("a"), _hit("b"), _hit("c")]
    base = _FakeBase(_result(hits))
    reranker = _ScoringReranker({"a": 0.1, "b": 0.9, "c": 0.5})
    result = RerankedRetriever(base, reranker, resolve_text=_doc_text).retrieve(
        "the query", within=Sensitivity.PUBLIC, top_k=2
    )
    assert [h.doc for h in result.hits] == [DocId("b"), DocId("c")]  # descending score, truncated
    # the resolved passages were scored in the hits' own order - one rerank() call, D68's shape.
    assert reranker.calls == [("the query", ("a", "b", "c"))]


def test_reranked_retriever_keeps_the_base_order_when_the_reranker_abstains() -> None:
    hits = [_hit("a"), _hit("b"), _hit("c")]
    base = _FakeBase(_result(hits, reason="hybrid recall"))
    result = RerankedRetriever(
        base, _ScoringReranker(abstain=True), resolve_text=_doc_text
    ).retrieve("q", within=Sensitivity.PUBLIC, top_k=2)
    assert [h.doc for h in result.hits] == [DocId("a"), DocId("b")]  # RRF order kept, just narrowed
    assert result.reason == "hybrid recall"  # unchanged - D126: no opinion, no rewritten reason


def test_reranked_retriever_degrades_to_no_rerank_when_the_reranker_raises() -> None:
    # audit MAJEUR-1 - a cross-encoder that BLOWS UP must not crash search()/recall(); the decorator
    # nets ANY failure and degrades to the RRF order (fail-safe, D100), like every other model seam.
    hits = [_hit("a"), _hit("b"), _hit("c")]
    base = _FakeBase(_result(hits, reason="hybrid recall"))
    result = RerankedRetriever(base, _RaisingReranker(), resolve_text=_doc_text).retrieve(
        "q", within=Sensitivity.PUBLIC, top_k=2
    )
    assert [h.doc for h in result.hits] == [DocId("a"), DocId("b")]  # RRF order kept, just narrowed
    assert result.reason == "hybrid recall"  # no crash, no rewritten reason


def test_reranked_retriever_passes_through_an_admitted_low_recall_result_untouched() -> None:
    low_recall = _result((), admitted_low_recall=True, reason="I don't know")
    base = _FakeBase(low_recall)
    reranker = _ScoringReranker()
    result = RerankedRetriever(base, reranker, resolve_text=_doc_text).retrieve(
        "q", within=Sensitivity.PUBLIC
    )
    assert result is low_recall  # untouched - invariant 14 is never re-opened here
    assert result.admitted_low_recall is True and result.hits == ()
    assert reranker.calls == []  # never even asked to score


def test_reranked_retriever_passes_through_an_empty_hits_result() -> None:
    empty = _result((), admitted_low_recall=False, reason="nothing indexed yet")
    base = _FakeBase(empty)
    reranker = _ScoringReranker()
    result = RerankedRetriever(base, reranker, resolve_text=_doc_text).retrieve(
        "q", within=Sensitivity.PUBLIC
    )
    assert result is empty
    assert reranker.calls == []


def test_reranked_retriever_appends_the_reason_only_on_a_real_rerank() -> None:
    hits = [_hit("a"), _hit("b")]
    base = _FakeBase(_result(hits, reason="hybrid recall"))
    reranker = _ScoringReranker({"a": 0.1, "b": 0.9}, model_id="my-cross-encoder")
    result = RerankedRetriever(base, reranker, resolve_text=_doc_text).retrieve(
        "q", within=Sensitivity.PUBLIC
    )
    assert result.reason == "hybrid recall — reranked (cross-encoder my-cross-encoder, D68)"


# ==================================== 4. wrap_reranked =================================== #


def test_wrap_reranked_with_no_reranker_returns_the_same_base_object() -> None:
    base = _FakeBase(_result([_hit("a")]))
    wrapped = wrap_reranked(base, None, truth=MarkdownTruthStore(), raptor=None)
    assert wrapped is base  # identity - zero regression, no wrapper at all (D126)


def test_wrap_reranked_with_a_reranker_returns_a_reranked_retriever_that_reorders() -> None:
    base = _FakeBase(_result([_hit("a"), _hit("b")]))
    truth = MarkdownTruthStore()
    truth.write(DocId("a"), Envelope(payload="a", label=_label()))
    truth.write(DocId("b"), Envelope(payload="b", label=_label()))
    wrapped = wrap_reranked(base, _ScoringReranker({"a": 0.1, "b": 0.9}), truth=truth, raptor=None)
    assert isinstance(wrapped, RerankedRetriever)
    result = wrapped.retrieve("q", within=Sensitivity.PUBLIC)
    assert result.hits[0].doc == DocId("b")  # reordered by the wired reranker, via passage_resolver


def test_retriever_and_reranked_retriever_both_satisfy_retrieverlike() -> None:
    base_retriever = Retriever(InMemoryVectorIndex(), StubEmbedder())
    assert isinstance(base_retriever, RetrieverLike)
    wrapped = RerankedRetriever(base_retriever, _ScoringReranker(), resolve_text=_doc_text)
    assert isinstance(
        wrapped, RetrieverLike
    )  # the decorator substitutes with zero call-site change


# ==================================== 5. passage_resolver ================================ #


def test_passage_resolver_leaf_hit_resolves_to_the_matched_passage_by_ordinal() -> None:
    first_half = "alpha bravo charlie delta echo foxtrot golf hotel india " * 20
    second_half = "zones prix trading strategy discussed at length here " * 20
    text = first_half + "\n\n" + second_half
    truth = MarkdownTruthStore()
    truth.write(DocId("library/book"), Envelope(payload=text, label=_label()))
    resolve = passage_resolver(truth, raptor=None)
    hit = _hit("library/book", chunk=1)  # the trusted ordinal of the on-topic passage (D136)
    resolved = resolve(hit, "zones prix trading")
    assert resolved == select_passage(text, "zones prix trading", ordinal=1)  # defers, verbatim
    assert "zones prix trading" in resolved
    assert len(resolved) < len(text)  # a PASSAGE, never the whole document


def test_passage_resolver_summary_hit_resolves_to_its_synopsis_text() -> None:
    raptor = RaptorStore()
    member = DocId("library/book")
    node = RaptorNode(
        doc=raptor_doc_id("book", (member,)),
        level="book",
        member_ids=(member,),
        text="a faithful synopsis of the book",
        label=_label(),
    )
    raptor.put(node)
    resolve = passage_resolver(MarkdownTruthStore(), raptor)
    assert resolve(_hit(str(node.doc)), "any query") == "a faithful synopsis of the book"


def test_passage_resolver_degrades_to_empty_on_any_unresolvable_hit_never_raises() -> None:
    # D126 / D100: ANY failure to resolve - no RaptorStore wired, a summary swept from the store, or
    # an unknown leaf doc - degrades to an EMPTY passage (scored low by the cross-encoder), never a
    # crash out of the retrieval path.
    no_store_summary = raptor_doc_id("book", (DocId("library/gone"),))
    resolve_no_store = passage_resolver(MarkdownTruthStore(), raptor=None)
    assert resolve_no_store(_hit(str(no_store_summary)), "q") == ""

    swept_summary = raptor_doc_id("book", (DocId("library/swept"),))
    resolve_empty_store = passage_resolver(MarkdownTruthStore(), RaptorStore())
    assert resolve_empty_store(_hit(str(swept_summary)), "q") == ""  # raptor.get raises, netted

    resolve_leaf = passage_resolver(MarkdownTruthStore(), raptor=None)
    assert resolve_leaf(_hit("library/never-written"), "q") == ""  # truth.read raises, netted


# ==================== 6. CoreApi integration (the honest close, D119) =================== #


def test_core_api_reranker_changes_the_order_of_search_hits() -> None:
    policy = _policy()
    plain = CoreApi(bootstrap(policy=policy))
    reranked = CoreApi(bootstrap(policy=policy, reranker=_ReversingReranker()))
    for api in (plain, reranked):
        api.capture(
            "zones prix trading " * 30 + "alpha bravo charlie",
            bubble=Bubble("perso"),
            domain_signal=Sensitivity.PERSO,
        )
        api.capture(
            "zones prix trading " * 30 + "delta echo foxtrot",
            bubble=Bubble("perso"),
            domain_signal=Sensitivity.PERSO,
        )
    before = plain.search("zones prix trading", within=Sensitivity.PERSO, subject=Bubble("perso"))
    after = reranked.search("zones prix trading", within=Sensitivity.PERSO, subject=Bubble("perso"))
    before_docs = [doc for doc, _score in before.hits]
    after_docs = [doc for doc, _score in after.hits]
    assert len(before_docs) >= 2  # both captures cleared the floor and were admitted
    assert after_docs == list(reversed(before_docs))  # stage 6 is LIVE on the facade
    assert before_docs != after_docs  # a genuinely different order, not a no-op


def test_core_api_reranker_changes_the_order_of_recall_working_material() -> None:
    policy = _policy()
    plain = CoreApi(bootstrap(policy=policy))
    reranked = CoreApi(bootstrap(policy=policy, reranker=_ReversingReranker()))
    for api in (plain, reranked):
        api.capture(
            "zones prix trading " * 30 + "alpha bravo charlie",
            bubble=Bubble("perso"),
            domain_signal=Sensitivity.PERSO,
        )
        api.capture(
            "zones prix trading " * 30 + "delta echo foxtrot",
            bubble=Bubble("perso"),
            domain_signal=Sensitivity.PERSO,
        )
    before = plain.recall(
        "zones prix trading",
        within=Sensitivity.PERSO,
        subject=Bubble("perso"),
        kind=QueryKind.FACTUAL,
    )
    after = reranked.recall(
        "zones prix trading",
        within=Sensitivity.PERSO,
        subject=Bubble("perso"),
        kind=QueryKind.FACTUAL,
    )
    # D137: neither document was endorsed => both surface as working material, never as citable facts.
    before_texts = [env.payload for env in before.working_material]
    after_texts = [env.payload for env in after.working_material]
    assert len(before_texts) >= 2
    assert after_texts == list(reversed(before_texts))


def test_core_api_reranker_never_relaxes_domain_cloisonnement() -> None:
    # rerank only REORDERS an already-retrieved shortlist; it must never widen WHO may read it
    # (invariant 4 / D72). No domain filter narrows the candidate pool itself, so BOTH docs are
    # retrieved and freely reordered by the reversing reranker - yet the undeclared-domain doc is
    # STILL withheld by the Guard's per-hit domain gate, exactly as with no reranker wired.
    policy = _policy({Bubble("projet"): frozenset({Domain("sante")})})
    rt = bootstrap(policy=policy, reranker=_ReversingReranker())
    api = CoreApi(rt)
    shared = "shared confidential business note mentioning "
    fin_label = GovernanceLabel(
        sensitivity=Sensitivity.SENSIBLE,
        bubble=Bubble("projet"),
        domains=frozenset({Domain("finances")}),
    )
    sante_label = GovernanceLabel(
        sensitivity=Sensitivity.SENSIBLE,
        bubble=Bubble("projet"),
        domains=frozenset({Domain("sante")}),
    )
    rt.journal.integrate(
        DocId("fin-1"),
        Envelope(payload=shared + "finances alpha bravo charlie delta", label=fin_label),
    )
    rt.journal.integrate(
        DocId("sante-1"),
        Envelope(payload=shared + "sante echo foxtrot golf hotel", label=sante_label),
    )
    view = api.search(shared.strip(), within=Sensitivity.SENSIBLE, subject=Bubble("projet"))
    docs = {doc for doc, _score in view.hits}
    assert docs == {
        DocId("sante-1")
    }  # fin-1 withheld regardless of how the reranker ordered the pair


def test_core_api_low_recall_still_admits_i_dont_know_with_a_reranker_wired() -> None:
    api = CoreApi(bootstrap(policy=_policy(), reranker=_ReversingReranker()))
    view = api.search("nothing indexed at all", within=Sensitivity.PERSO, subject=Bubble("perso"))
    assert (
        view.admitted_low_recall is True and view.hits == ()
    )  # invariant 14 holds, reranker or not


# ==================== 6b. MAJEUR-2 - over-fetch past may_read (readable recall) ============ #


#: Foreign hits ranked ABOVE the readable ones: MORE than the small top_k the tests use (so pre-fix
#: a top_k retrieve would be ALL-foreign) yet within ``READ_POOL`` (so the over-fetch reaches the
#: readable docs below them). ``READ_POOL`` is 40, top_k in the tests is 3 - 10 sits cleanly between.
_MAJEUR2_FOREIGN = 10


def _majeur2_ranked(rt) -> tuple[Bubble, Sensitivity, list[SearchHit]]:
    """A ranked shortlist whose top ``_MAJEUR2_FOREIGN`` hits are FOREIGN (unreadable), with the
    readable same-bubble docs ranked just BELOW them - the exact shape MAJEUR-2 addresses. Seeds the
    readable docs into truth so recall can pack + validate them."""
    assert (
        _MAJEUR2_FOREIGN + 3 <= READ_POOL
    )  # the readable docs must fall INSIDE the over-fetch pool
    subject, within = Bubble("perso"), Sensitivity.SENSIBLE
    foreign_label = GovernanceLabel(
        sensitivity=within, bubble=Bubble("foreign"), domains=frozenset()
    )
    read_label = GovernanceLabel(sensitivity=within, bubble=subject, domains=frozenset())
    # foreign hits ranked first - pre-fix they would fill any small top_k and evict readable recall.
    ranked = [
        SearchHit(DocId(f"foreign-{i}"), 0.99 - i * 0.001, foreign_label)
        for i in range(_MAJEUR2_FOREIGN)
    ]
    for i in range(3):
        doc = DocId(f"read-{i}")
        rt.truth.write(doc, Envelope(f"kelly criterion sizing passage {i}", read_label))
        ranked.append(SearchHit(doc, 0.50 - i * 0.001, read_label))
    return subject, within, ranked


def test_core_api_recall_over_fetches_so_foreign_hits_do_not_evict_readable_recall() -> None:
    # MAJEUR-2: the readable same-bubble docs rank BELOW READ_POOL foreign hits. Pre-fix, recall
    # retrieved only top_k and may_read left NOTHING readable (all foreign) - readable recall was lost.
    # Post-fix it over-fetches the wide pool, so the readable docs survive to the top_k after may_read.
    rt = bootstrap(policy=_policy())
    api = CoreApi(rt)
    subject, within, ranked = _majeur2_ranked(rt)
    api._retriever = _RankedRetriever(ranked)  # noqa: SLF001 - inject a controllable ranked shortlist

    view = api.recall("kelly", within=within, subject=subject, kind=QueryKind.FACTUAL, top_k=3)

    texts = [env.payload for env in view.working_material]
    assert (
        len(texts) == 3
    )  # the 3 readable docs surfaced - never evicted by the foreign top-of-pool
    assert all("kelly criterion sizing passage" in t for t in texts)
    assert not view.admitted_low_recall
    assert api._retriever.calls[-1] == max(3, READ_POOL)  # noqa: SLF001 - it OVER-FETCHED the wide pool


def test_core_api_search_over_fetches_then_truncates_readable_to_top_k() -> None:
    # search surfaces the readable hits (its own grain) - the over-fetch means the 3 readable docs are
    # returned though they ranked past a small top_k behind foreign hits; the foreigners stay withheld.
    rt = bootstrap(policy=_policy())
    api = CoreApi(rt)
    subject, within, ranked = _majeur2_ranked(rt)
    api._retriever = _RankedRetriever(ranked)  # noqa: SLF001

    view = api.search("kelly", within=within, subject=subject, top_k=3)

    docs = {str(doc) for doc, _score in view.hits}
    assert docs == {"read-0", "read-1", "read-2"}  # readable recall preserved; foreigners withheld
    assert api._retriever.calls[-1] == max(3, READ_POOL)  # noqa: SLF001 - over-fetched before may_read


# ==================================== 7. Zero-regression (D126) ========================== #


def test_bootstrap_default_reranker_is_none() -> None:
    assert bootstrap().reranker is None  # no wrapper composed unless one is explicitly injected


def test_core_api_with_no_reranker_wires_the_bare_retriever_not_a_reranked_one() -> None:
    api = CoreApi(bootstrap())
    assert isinstance(api._retriever, Retriever)  # noqa: SLF001 - structural proof of zero regression
    assert not isinstance(api._retriever, RerankedRetriever)  # noqa: SLF001
