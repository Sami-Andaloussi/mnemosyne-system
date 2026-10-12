"""Adapter tests ((3)) - the real OSS bricks behind their ports, checked against light
doubles WITHOUT the installed brick (D126 decoupling).

Each (3) adapter wraps a real brick (bge-m3 / Qdrant / tantivy / MLX) behind a LOT 1 port.
The brick is injected, so the translation the adapter does (port <-> brick API) is exercised
here against a double; the real bricks themselves are validated by the 1-click smoke at
ignition, never in this suite (which stays green with nothing installed). Code English (D117).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace
from datetime import datetime, timezone

import pytest

from mnemosyne.ports import (
    Bubble,
    DocId,
    Domain,
    Embedder,
    Embedding,
    Envelope,
    Fact,
    FactId,
    GovernanceLabel,
    GraphStore,
    KeywordIndex,
    NodeId,
    SearchHit,
    Sensitivity,
    StructuralExtractor,
    VectorIndex,
    is_indexable_vector,
)
from mnemosyne.ingest import (
    MimeDispatchSourceReader,
    NullStructuralExtractor,
    PlainTextSourceReader,
    TreeSitterStructuralExtractor,
)
from mnemosyne.ports import Source
from mnemosyne.stores import (
    BgeM3Embedder,
    InMemoryGraphStore,
    InMemoryKeywordIndex,
    InMemoryVectorIndex,
    LadybugGraphStore,
    QdrantVectorIndex,
    Retriever,
    StubEmbedder,
    TantivyKeywordIndex,
)
from mnemosyne.stores.embedder_bge import _ENCODE_BATCH


def _fake_encoder(dimension: int = 1024):
    """A double for bge-m3: a deterministic ``dimension``-wide vector per text."""

    def encode(texts: Sequence[str]) -> list[list[float]]:
        return [[float(len(t) + i) for i in range(dimension)] for t in texts]

    return encode


def test_bge_m3_embedder_satisfies_the_embedder_port() -> None:
    emb = BgeM3Embedder(_fake_encoder())
    assert isinstance(emb, Embedder)  # runtime_checkable Protocol surface (D68)
    assert emb.model_id == "bge-m3"
    assert emb.dimension == 1024
    assert emb.max_tokens == 8192


def test_bge_m3_embedder_tags_each_vector_with_the_model_identity() -> None:
    # D68: every vector carries the model identity so a swap drives a targeted re-index (D63).
    emb = BgeM3Embedder(_fake_encoder())
    out = emb.embed(["alpha", "beta"])
    assert len(out) == 2
    assert all(isinstance(e, Embedding) for e in out)
    assert all(e.model_id == "bge-m3" and e.dimension == 1024 and e.version == "0" for e in out)
    assert all(len(e.vector) == 1024 for e in out)


def test_bge_m3_embedder_refuses_a_wrong_dimension() -> None:
    # A brick returning the wrong width is a structural error, never a silent bad index.
    emb = BgeM3Embedder(_fake_encoder(dimension=512))
    with pytest.raises(ValueError):
        emb.embed(["x"])


def test_bge_m3_embedder_refuses_a_vector_count_mismatch() -> None:
    def bad_encode(texts: Sequence[str]) -> list[list[float]]:
        return [[0.0] * 1024]  # one vector for however many texts

    emb = BgeM3Embedder(bad_encode)
    with pytest.raises(ValueError):
        emb.embed(["a", "b"])


def test_bge_m3_embedder_sub_batches_a_large_document() -> None:
    # A document may contain many passages; encoding all at once scales attention memory with batch
    # size and can abort the process outside Python's exception handling. `embed()` must cap batches.
    calls: list[int] = []

    def counting_encode(texts: Sequence[str]) -> list[list[float]]:
        calls.append(len(texts))
        return [[float(i)] * 1024 for i in range(len(texts))]

    emb = BgeM3Embedder(counting_encode)
    total = _ENCODE_BATCH * 3 + 5  # deliberately not a multiple of the batch size
    out = emb.embed([f"passage {i}" for i in range(total)])

    assert len(out) == total
    assert calls == [_ENCODE_BATCH, _ENCODE_BATCH, _ENCODE_BATCH, 5]


def test_bge_m3_embedder_declares_its_recall_floor() -> None:
    # The recall floor (invariant 14) is a property of bge-m3's cosine distribution, so it travels
    # WITH the embedder - EARNED at (3)-2b from a corpus golden (answers 0.535+ vs distractors 0.529- -> 0.53).
    assert BgeM3Embedder(_fake_encoder()).recall_floor == 0.53


def test_retriever_takes_its_low_recall_floor_from_the_embedder() -> None:
    # D65 / invariant 14: the Retriever defaults its gate to the embedder's declared floor
    # (bge-m3 -> 0.53), falls back to the stub default when none is declared, and still honours
    # an explicit override - so swapping the encoder swaps the floor with it (D68 / D113).
    idx = InMemoryVectorIndex()
    assert Retriever(idx, BgeM3Embedder(_fake_encoder())).min_score == 0.53
    assert Retriever(idx, StubEmbedder()).min_score == 0.3  # stub declares 0.3 on the port
    assert Retriever(idx, BgeM3Embedder(_fake_encoder()), min_score=0.8).min_score == 0.8


# --------------------------------------------------------------------------- #
# QdrantVectorIndex - partition-by-sensitivity routing (invariant 1), checked   #
# against a light in-memory backend double (no Qdrant server needed, D126).     #
# --------------------------------------------------------------------------- #
class _FakeBackend:
    """In-memory stand-in for the primitive VectorBackend surface, per collection."""

    def __init__(self) -> None:
        self.collections: dict[str, dict[str, tuple[tuple[float, ...], dict]]] = {}

    def ensure_collection(self, collection, *, dimension):
        self.collections.setdefault(collection, {})

    def upsert(self, collection, doc_id, vector, payload):
        self.collections.setdefault(collection, {})[doc_id] = (tuple(vector), payload)

    def search(self, collection, vector, domains, top_k):
        best: dict[str, dict] = {}  # GROUP by doc (mirrors query_points_groups) - one row per doc
        for _point_id, (_vec, payload) in self.collections.get(collection, {}).items():
            if domains and not (set(domains) & set(payload.get("domains", ()))):
                continue
            best.setdefault(payload["doc"], payload)  # fixed score => first passage seen is "best"
        return [(1.0, payload) for payload in list(best.values())[:top_k]]  # top_k DISTINCT docs

    def delete_by_doc(self, collection, doc):
        col = self.collections.get(collection, {})
        for point_id in [pid for pid, (_v, pl) in col.items() if pl["doc"] == doc]:
            del col[point_id]

    def docs(self, collection):
        return {pl["doc"] for _v, pl in self.collections.get(collection, {}).values()}

    def has_doc(self, collection, doc):
        return doc in self.docs(collection)


def _vec(dim: int = 1024) -> Embedding:
    return BgeM3Embedder(_fake_encoder(dim)).embed(["x"])[0]


def test_qdrant_satisfies_the_vectorindex_port() -> None:
    assert isinstance(QdrantVectorIndex(_FakeBackend()), VectorIndex)


def test_qdrant_isolates_sensible_in_its_own_partition() -> None:
    # invariant 1: a sensible datum lands ONLY in the isolated sensible collection, and a
    # search never crosses partitions - the security-critical property of the port.
    backend = _FakeBackend()
    idx = QdrantVectorIndex(backend)
    v = _vec()
    idx.upsert(DocId("d-pub"), [v], GovernanceLabel(Sensitivity.PUBLIC, Bubble("b")))
    idx.upsert(DocId("d-sen"), [v], GovernanceLabel(Sensitivity.SENSIBLE, Bubble("b")))
    assert "d-sen" in backend.docs("mnemosyne_sensible")
    assert "d-sen" not in backend.docs("mnemosyne_public")
    assert {h.doc for h in idx.search(v, within=Sensitivity.PUBLIC)} == {DocId("d-pub")}
    assert {h.doc for h in idx.search(v, within=Sensitivity.SENSIBLE)} == {DocId("d-sen")}


def test_qdrant_search_is_narrowed_by_domain() -> None:
    # D72 cloisonnement by domain, within a single partition.
    backend = _FakeBackend()
    idx = QdrantVectorIndex(backend)
    v = _vec()
    idx.upsert(
        DocId("fin"),
        [v],
        GovernanceLabel(Sensitivity.PERSO, Bubble("b"), frozenset({Domain("finance")})),
    )
    idx.upsert(
        DocId("hea"),
        [v],
        GovernanceLabel(Sensitivity.PERSO, Bubble("b"), frozenset({Domain("health")})),
    )
    hits = idx.search(v, within=Sensitivity.PERSO, domains=frozenset({Domain("finance")}))
    assert {h.doc for h in hits} == {DocId("fin")}


def test_qdrant_invalidate_purges_every_partition() -> None:
    backend = _FakeBackend()
    idx = QdrantVectorIndex(backend)
    v = _vec()
    idx.upsert(DocId("d"), [v], GovernanceLabel(Sensitivity.SENSIBLE, Bubble("b")))
    assert idx.contains(DocId("d"))
    idx.invalidate(DocId("d"))
    assert not idx.contains(DocId("d"))


def test_qdrant_rebuilds_the_governance_label_from_the_payload() -> None:
    backend = _FakeBackend()
    idx = QdrantVectorIndex(backend)
    v = _vec()
    label = GovernanceLabel(Sensitivity.PERSO, Bubble("bulle"), frozenset({Domain("work")}))
    idx.upsert(DocId("d"), [v], label)
    hit = idx.search(v, within=Sensitivity.PERSO)[0]
    assert hit.label.sensitivity is Sensitivity.PERSO
    assert hit.label.bubble == Bubble("bulle")
    assert hit.label.domains == frozenset({Domain("work")})
    assert hit.chunk == 0  # D136: the matched passage's ordinal rides back from the payload


def test_qdrant_search_groups_by_doc_so_a_long_doc_never_starves() -> None:
    # D135 audit A-2: a doc with many passages must NOT crowd out other docs - search groups by
    # doc (best passage each) and returns top_k DISTINCT docs, not top_k passages of one doc. The
    # in-memory stub scanned every doc and could not model this divergence; the backend now groups.
    backend = _FakeBackend()
    idx = QdrantVectorIndex(backend)
    v = _vec()
    idx.upsert(DocId("big"), [v] * 20, GovernanceLabel(Sensitivity.PUBLIC, Bubble("b")))
    for n in range(5):
        idx.upsert(DocId(f"small-{n}"), [v], GovernanceLabel(Sensitivity.PUBLIC, Bubble("b")))
    docs = {hit.doc for hit in idx.search(v, within=Sensitivity.PUBLIC, top_k=10)}
    assert DocId("big") in docs and len(docs) == 6  # the 20-passage doc counts ONCE; all 6 surface


def test_qdrant_chunk_from_payload_is_zero_trust() -> None:
    # audit m-3: the matched-passage ordinal from a Qdrant payload is ZERO-TRUST (D100-3) - a non-int
    # (corrupt point, third-party writer, a stored "0" string) is treated as absent, never crashing
    # the recall downstream in select_passage.
    f = QdrantVectorIndex._chunk_from_payload
    assert f({"chunk": 3}) == 3
    assert f({"chunk": "3"}) is None  # a string ordinal is not trusted
    assert f({"chunk": True}) is None  # a bool is an int subclass but never an ordinal
    assert f({"chunk": 1.5}) is None  # a float is not an ordinal
    assert f({}) is None  # absent


def test_is_indexable_vector_rejects_non_finite_and_zero() -> None:
    # the shared predicate behind the (3) scale-up guard: cosine is undefined for a zero-norm vector and
    # Qdrant rejects both it and a non-finite one ("did not match any variant of untagged enum
    # VectorStruct"), so neither may be indexed (D68 / invariant 14).
    assert is_indexable_vector((0.1, 0.2, 0.3))
    assert not is_indexable_vector((0.0, 0.0, 0.0))  # zero-norm
    assert not is_indexable_vector((float("nan"), 1.0))  # fp16 overflow -> NaN
    assert not is_indexable_vector((float("inf"), 1.0))
    assert not is_indexable_vector(())  # empty


def test_qdrant_drops_a_non_indexable_passage_keeping_ordinals() -> None:
    # the 400 fix: a non-finite (bge-m3 fp16) passage vector is NEVER sent to Qdrant - a single one makes
    # the server reject the WHOLE upsert (VectorStruct 400), failing the book at scale-up. It is dropped;
    # the surviving passages keep their ordinal so select_passage still aligns at read (D136).
    backend = _FakeBackend()
    idx = QdrantVectorIndex(backend)
    good0, good2 = _vec(), _vec()
    nan1 = replace(good0, vector=(float("nan"),) * 1024)
    idx.upsert(DocId("d"), [good0, nan1, good2], GovernanceLabel(Sensitivity.PUBLIC, Bubble("b")))
    assert set(backend.collections["mnemosyne_public"]) == {
        "d#0",
        "d#2",
    }  # #1 dropped, #2 kept its ordinal
    assert idx.contains(DocId("d"))


def test_qdrant_contains_is_doc_level_when_passage_zero_is_dropped() -> None:
    # the witness is doc-level (has_doc), not exists(doc#0): a doc whose FIRST passage was dropped is
    # still 'contained' via a survivor - else the marker would wrongly read not-indexed (invariant 24).
    backend = _FakeBackend()
    idx = QdrantVectorIndex(backend)
    nan0, good1 = replace(_vec(), vector=(float("nan"),) * 1024), _vec()
    idx.upsert(DocId("d"), [nan0, good1], GovernanceLabel(Sensitivity.PUBLIC, Bubble("b")))
    assert "d#0" not in backend.collections["mnemosyne_public"]  # first passage dropped
    assert idx.contains(DocId("d"))  # yet the doc IS contained (survivor d#1)


def test_qdrant_doc_with_only_non_indexable_passages_is_absent() -> None:
    backend = _FakeBackend()
    idx = QdrantVectorIndex(backend)
    nan = replace(_vec(), vector=(float("nan"),) * 1024)
    idx.upsert(DocId("d"), [nan], GovernanceLabel(Sensitivity.PUBLIC, Bubble("b")))
    assert not idx.contains(DocId("d"))  # nothing indexable => honestly absent (D100)


# --------------------------------------------------------------------------- #
# KeywordIndex - the BM25 leg ((3)-2b): tantivy adapter routing checked against a  #
# light double, the in-memory stub, and RRF hybrid fusion in the Retriever.      #
# --------------------------------------------------------------------------- #
class _FakeKeywordBackend:
    """In-memory stand-in for the primitive KeywordBackend surface, per index."""

    def __init__(self) -> None:
        self.indexes: dict[str, dict[str, tuple[str, dict]]] = {}

    def ensure_index(self, index):
        self.indexes.setdefault(index, {})

    def index_doc(self, index, doc_id, text, payload):
        self.indexes.setdefault(index, {})[doc_id] = (text, payload)

    def search(self, index, query, domains, top_k):
        query_terms = set(query.lower().split())
        rows = []
        for _doc_id, (text, payload) in self.indexes.get(index, {}).items():
            if domains and not (set(domains) & set(payload.get("domains", ()))):
                continue
            score = float(sum(1 for term in text.lower().split() if term in query_terms))
            if score > 0.0:
                rows.append((score, payload))
        rows.sort(key=lambda row: row[0], reverse=True)
        return rows[:top_k]

    def delete(self, index, doc_id):
        self.indexes.get(index, {}).pop(doc_id, None)

    def exists(self, index, doc_id):
        return doc_id in self.indexes.get(index, {})


def test_tantivy_satisfies_the_keywordindex_port() -> None:
    assert isinstance(TantivyKeywordIndex(_FakeKeywordBackend()), KeywordIndex)


def test_inmemory_keyword_satisfies_the_port_and_scores_by_term_overlap() -> None:
    kw = InMemoryKeywordIndex()
    assert isinstance(kw, KeywordIndex)  # runtime_checkable Protocol surface (D68)
    label = GovernanceLabel(Sensitivity.PUBLIC, Bubble("b"))
    kw.index(DocId("a"), "the quick brown fox", label)
    kw.index(DocId("b"), "lazy dog sleeps", label)
    hits = kw.search("quick fox", within=Sensitivity.PUBLIC)
    assert hits and hits[0].doc == DocId("a")  # two shared terms -> top hit
    assert all(h.doc != DocId("b") for h in hits)  # no shared term -> not a hit


def test_tantivy_isolates_sensible_in_its_own_partition() -> None:
    # invariant 1: the keyword leg physically isolates sensible, exactly like the dense leg.
    backend = _FakeKeywordBackend()
    idx = TantivyKeywordIndex(backend)
    idx.index(DocId("d-pub"), "a shared note", GovernanceLabel(Sensitivity.PUBLIC, Bubble("b")))
    idx.index(DocId("d-sen"), "a shared note", GovernanceLabel(Sensitivity.SENSIBLE, Bubble("b")))
    assert "d-sen" in backend.indexes["mnemosyne_sensible"]
    assert "d-sen" not in backend.indexes.get("mnemosyne_public", {})
    assert {h.doc for h in idx.search("note", within=Sensitivity.PUBLIC)} == {DocId("d-pub")}
    assert {h.doc for h in idx.search("note", within=Sensitivity.SENSIBLE)} == {DocId("d-sen")}


def test_tantivy_search_is_narrowed_by_domain() -> None:
    backend = _FakeKeywordBackend()
    idx = TantivyKeywordIndex(backend)
    idx.index(
        DocId("fin"),
        "quarterly report",
        GovernanceLabel(Sensitivity.PERSO, Bubble("b"), frozenset({Domain("finance")})),
    )
    idx.index(
        DocId("hea"),
        "quarterly checkup",
        GovernanceLabel(Sensitivity.PERSO, Bubble("b"), frozenset({Domain("health")})),
    )
    hits = idx.search("quarterly", within=Sensitivity.PERSO, domains=frozenset({Domain("finance")}))
    assert {h.doc for h in hits} == {DocId("fin")}


def test_tantivy_invalidate_purges_every_partition() -> None:
    backend = _FakeKeywordBackend()
    idx = TantivyKeywordIndex(backend)
    idx.index(DocId("d"), "some text", GovernanceLabel(Sensitivity.SENSIBLE, Bubble("b")))
    assert idx.contains(DocId("d"))
    idx.invalidate(DocId("d"))
    assert not idx.contains(DocId("d"))


def test_tantivy_rebuilds_the_governance_label_from_the_payload() -> None:
    backend = _FakeKeywordBackend()
    idx = TantivyKeywordIndex(backend)
    idx.index(
        DocId("d"),
        "work note",
        GovernanceLabel(Sensitivity.PERSO, Bubble("bulle"), frozenset({Domain("work")})),
    )
    hit = idx.search("work", within=Sensitivity.PERSO)[0]
    assert hit.label.sensitivity is Sensitivity.PERSO
    assert hit.label.bubble == Bubble("bulle")
    assert hit.label.domains == frozenset({Domain("work")})


# --- RRF hybrid fusion in the Retriever (dense ⊕ keyword) ------------------- #
def _hybrid(vector: InMemoryVectorIndex, keyword: InMemoryKeywordIndex) -> Retriever:
    return Retriever(vector, StubEmbedder(), keyword=keyword)


def test_hybrid_fuses_dense_and_keyword_by_rrf() -> None:
    # A doc found by BOTH legs outranks one found by a single leg (RRF, D68).
    vector, keyword, emb = InMemoryVectorIndex(), InMemoryKeywordIndex(), StubEmbedder()
    label = GovernanceLabel(Sensitivity.PUBLIC, Bubble("b"))
    text = "alpha beta gamma delta"
    vector.upsert(DocId("both"), emb.embed([text]), label)  # dense + keyword
    keyword.index(DocId("both"), text, label)
    keyword.index(DocId("kw-only"), text, label)  # keyword only
    result = _hybrid(vector, keyword).retrieve(text, within=Sensitivity.PUBLIC)
    assert not result.admitted_low_recall
    docs = [h.doc for h in result.hits]
    assert docs[0] == DocId("both")  # in both legs -> fused first
    assert DocId("kw-only") in docs


def test_hybrid_returns_a_keyword_only_match_dense_missed() -> None:
    # A lexical (BM25) hit is a legitimate confidence signal even when dense finds nothing.
    vector, keyword = InMemoryVectorIndex(), InMemoryKeywordIndex()
    label = GovernanceLabel(Sensitivity.PUBLIC, Bubble("b"))
    keyword.index(DocId("kw"), "exact lexical terms here", label)  # dense index left empty
    result = _hybrid(vector, keyword).retrieve("exact lexical terms", within=Sensitivity.PUBLIC)
    assert not result.admitted_low_recall
    assert DocId("kw") in {h.doc for h in result.hits}


def test_hybrid_admits_low_recall_when_neither_leg_matches() -> None:
    # invariant 14 under hybrid: no dense confidence AND no keyword hit => "I don't know".
    result = _hybrid(InMemoryVectorIndex(), InMemoryKeywordIndex()).retrieve(
        "utterly unindexed query", within=Sensitivity.PUBLIC
    )
    assert result.admitted_low_recall
    assert result.hits == ()


class _FixedHits:
    """A retrieval-leg double returning a fixed hit list - lets a test set exact dense / BM25
    scores the hashing stub can't dial in, to pin the per-doc admission ((3)-2b / F1)."""

    def __init__(self, hits: list[SearchHit]) -> None:
        self._hits = hits

    def search(self, _query, *, within, domains=frozenset(), top_k=10) -> list[SearchHit]:
        return list(self._hits)


def test_hybrid_admission_is_per_doc_and_drops_subfloor_noise() -> None:
    # F1 ((3)-2 closure): opening the gate on ONE confident signal must not drag sub-floor dense
    # noise into the fused context. A doc rides in only if it itself cleared the dense floor OR
    # matched lexically (invariant 14 per-doc, D100) - else it is dropped, never fed to generation.
    label = GovernanceLabel(Sensitivity.PUBLIC, Bubble("b"))
    dense = [SearchHit(DocId("confident"), 0.90, label), SearchHit(DocId("noise"), 0.05, label)]
    keyword = [SearchHit(DocId("lexical"), 3.0, label)]
    retriever = Retriever(_FixedHits(dense), StubEmbedder(), keyword=_FixedHits(keyword))
    result = retriever.retrieve("q", within=Sensitivity.PUBLIC)
    docs = {h.doc for h in result.hits}
    assert not result.admitted_low_recall
    assert DocId("confident") in docs  # cleared the dense floor (0.90 ≥ 0.3)
    assert DocId("lexical") in docs  # matched the lexical leg
    assert DocId("noise") not in docs  # sub-floor (0.05) and no lexical match => dropped (F1)


def test_hybrid_does_not_borrow_a_subfloor_dense_passage_ordinal() -> None:
    # audit M-1a: a doc admitted by the LEXICAL leg (its dense hit was sub-floor noise the gate drops)
    # must NOT inherit that noise's argmax passage ordinal - its passage is resolved lexically at read
    # (chunk=None). Only a doc that itself cleared the dense floor carries a trusted ordinal.
    label = GovernanceLabel(Sensitivity.PUBLIC, Bubble("b"))
    dense = [
        SearchHit(DocId("cleared"), 0.90, label, chunk=4),
        SearchHit(DocId("lex"), 0.05, label, chunk=9),  # sub-floor: its chunk must be dropped
    ]
    keyword = [SearchHit(DocId("lex"), 3.0, label, chunk=None)]  # admits "lex" lexically
    retriever = Retriever(_FixedHits(dense), StubEmbedder(), keyword=_FixedHits(keyword))
    by_doc = {h.doc: h for h in retriever.retrieve("q", within=Sensitivity.PUBLIC).hits}
    assert by_doc[DocId("cleared")].chunk == 4  # cleared the floor => trusted ordinal kept
    assert by_doc[DocId("lex")].chunk is None  # sub-floor ordinal NOT borrowed => lexical at read


class _FakeGenerationBackend:
    """A double for the MLX brick behind the runner's decode seam ((3)-2c) - barriers stay in the
    runner, so this only needs to echo tokens and carry an id (D126)."""

    model_id = "mlx-double"

    def generate(self, prompt: str) -> str:
        return f"<<{prompt}>>"

    def generate_structured(self, prompt: str, schema: str, kind: str) -> str:
        return "{}"


# --------------------------------------------------------------------------- #
# LadybugGraphStore - Moteur A behind the GraphStore port ((3)-3a): non-destructive,
# bi-temporal, checked against a light in-memory backend double (no engine, D126).
# --------------------------------------------------------------------------- #
class _FakeGraphBackend:
    """In-memory double for the GraphBackend surface (no engine, D126). It stores primitive rows
    and offers ONLY upsert / close / rows - there is NO delete verb, mirroring the real interface's
    structural non-destructiveness (invariant 2 / D84): the store cannot hard-delete a fact."""

    def __init__(self) -> None:
        self._rows: dict[str, tuple[str, str, str, str, str | None]] = {}

    def upsert(self, fid: str, subject: str, predicate: str, obj: str, valid_from: str) -> None:
        self._rows.setdefault(fid, (subject, predicate, obj, valid_from, None))  # idempotent

    def close(self, fid: str, valid_to: str) -> None:
        row = self._rows.get(fid)
        if row is not None:  # unknown id => NO-OP, mirroring the real engine ((3)-3c, 3a debt)
            s, p, o, vf, _ = row
            self._rows[fid] = (s, p, o, vf, valid_to)  # archival - the row is NEVER removed

    def rows(
        self, subject: str | None, predicate: str | None
    ) -> list[tuple[str, str, str, str, str | None]]:
        return [
            row
            for row in self._rows.values()
            if (subject is None or row[0] == subject) and (predicate is None or row[1] == predicate)
        ]


_T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
_T1 = datetime(2026, 6, 1, tzinfo=timezone.utc)
_T2 = datetime(2026, 12, 1, tzinfo=timezone.utc)


def _fact(subject: str, predicate: str, obj: str, valid_from: datetime = _T0) -> Fact:
    return Fact(NodeId(subject), predicate, NodeId(obj), valid_from=valid_from)


def _enveloped(fact: Fact) -> Envelope[Fact]:
    return Envelope(fact, GovernanceLabel(sensitivity=Sensitivity.PUBLIC, bubble=Bubble("perso")))


def test_ladybug_graph_store_satisfies_the_graphstore_port() -> None:
    assert isinstance(LadybugGraphStore(_FakeGraphBackend()), GraphStore)


def test_ladybug_add_fact_requires_an_envelope() -> None:
    # invariant 20 / D89: a naked fact (not enveloped) never enters the graph - engine output
    # carries its governance label or it is refused.
    graph = LadybugGraphStore(_FakeGraphBackend())
    with pytest.raises(TypeError):
        graph.add_fact(_fact("s", "p", "o"))  # type: ignore[arg-type]


def test_ladybug_add_fact_is_idempotent() -> None:
    # invariant 24: an identical fact keeps its id - re-adding does not duplicate (the substrate
    # of the journal's idempotent replay).
    graph = LadybugGraphStore(_FakeGraphBackend())
    first = graph.add_fact(_enveloped(_fact("s", "p", "o")))
    second = graph.add_fact(_enveloped(_fact("s", "p", "o")))
    assert first == second
    assert len(graph.query(subject=NodeId("s"))) == 1


def test_ladybug_query_filters_subject_and_predicate() -> None:
    graph = LadybugGraphStore(_FakeGraphBackend())
    graph.add_fact(_enveloped(_fact("s", "ville", "Paris")))
    graph.add_fact(_enveloped(_fact("s", "age", "30")))
    graph.add_fact(_enveloped(_fact("t", "ville", "Lyon")))
    assert len(graph.query(subject=NodeId("s"))) == 2
    assert len(graph.query(predicate="ville")) == 2
    hits = graph.query(subject=NodeId("s"), predicate="ville")
    assert len(hits) == 1 and hits[0].obj == NodeId("Paris")


def test_ladybug_invalidate_is_non_destructive_and_bitemporal() -> None:
    # invariant 2 / D84: invalidate CLOSES valid-time (archival), never deletes. A past-instant
    # query still sees the fact; a query "now" or after closure does not.
    backend = _FakeGraphBackend()
    graph = LadybugGraphStore(backend)
    fid = graph.add_fact(_enveloped(_fact("s", "p", "o", _T0)))
    graph.invalidate(fid, at=_T1)
    assert graph.query(subject=NodeId("s")) == []  # closed as of now (archived)
    assert graph.query(subject=NodeId("s"), as_of=_T0)  # visible in the past (not erased, D84)
    assert graph.query(subject=NodeId("s"), as_of=_T2) == []  # after closure: gone
    assert str(fid) in backend._rows  # noqa: SLF001 - the row STAYS, closed not deleted (inv. 2)


def test_ladybug_query_before_valid_from_is_empty() -> None:
    graph = LadybugGraphStore(_FakeGraphBackend())
    graph.add_fact(_enveloped(_fact("s", "p", "o", _T1)))
    assert graph.query(subject=NodeId("s"), as_of=_T0) == []  # before valid_from => not yet true
    assert graph.query(subject=NodeId("s"), as_of=_T2)  # after valid_from => visible


def test_ladybug_and_stub_assign_the_same_fact_id() -> None:
    # D103: a fact keeps its identity across a brick swap - the real adapter and the in-memory
    # double content-address a fact to the SAME id, so no fact changes identity when the engine
    # swaps (this LOCKS the duplicated _fact_id in lieu of factoring it).
    fact = _enveloped(_fact("alice", "ville", "Paris"))
    a = LadybugGraphStore(_FakeGraphBackend()).add_fact(fact)
    b = InMemoryGraphStore().add_fact(fact)
    assert a == b


def test_invalidating_an_unknown_fact_is_a_noop_on_both_bricks() -> None:
    # (3)-3c (3a debt): the stub and the real adapter AGREE on the WHOLE port - closing an unknown
    # fact id is an idempotent NO-OP (never a KeyError), matching the real LadybugDB engine. Locks
    # the last stub<->brick divergence the (3)-3a audit traced.
    unknown = FactId("does-not-exist")
    for graph in (InMemoryGraphStore(), LadybugGraphStore(_FakeGraphBackend())):
        graph.invalidate(unknown, at=_T1)  # no raise
        assert graph.query() == []  # nothing created, nothing changed


# --------------------------------------------------------------------------- #
# StructuralExtractor - the deterministic tree-sitter pre-pass ((3)-3 / D125-B9), #
# checked against a backend double (no tree-sitter installed, D126).           #
# --------------------------------------------------------------------------- #
class _FakeStructuralBackend:
    """A StructuralBackend double (no tree-sitter, D126): returns canned ``(capture, text)`` per
    language, so the adapter's capture->triple TRANSLATION is unit-tested without the brick."""

    def __init__(self, captures: dict[str, list[tuple[str, str]]]) -> None:
        self._captures = captures

    def captures(self, content: str, language: str) -> list[tuple[str, str]]:
        return list(self._captures.get(language, []))


def test_structural_extractors_satisfy_the_port() -> None:
    assert isinstance(
        TreeSitterStructuralExtractor(_FakeStructuralBackend({})), StructuralExtractor
    )
    assert isinstance(NullStructuralExtractor(), StructuralExtractor)


def test_null_structural_extractor_abstains() -> None:
    # the default stub produces NO fact - the seam is wired, tree-sitter is not installed (D126).
    assert NullStructuralExtractor().extract_structural("def f(): pass", language="python") == ()


def test_tree_sitter_extractor_translates_captures_to_deterministic_triples() -> None:
    # (3)-3 / D125-B9: each NAMED capture becomes a deterministic triple - subject = matched text,
    # (predicate, object) fixed by the capture name. This is the whole logic, tested brick-free.
    backend = _FakeStructuralBackend(
        {
            "python": [
                ("function.name", "foo"),
                ("class.name", "Bar"),
                ("import.name", "os"),
            ]
        }
    )
    facts = TreeSitterStructuralExtractor(backend).extract_structural("<src>", language="python")
    triples = {(str(f.subject), f.predicate, str(f.obj)) for f in facts}
    assert triples == {
        ("foo", "defined_as", "function"),
        ("Bar", "defined_as", "class"),
        ("os", "used_as", "import"),
    }


def test_tree_sitter_extractor_drops_unknown_and_empty_captures() -> None:
    # fail-safe: a capture the triple map does not name, or an empty match, invents NO fact; an
    # unsupported language yields nothing - a broken parse never fabricates or raises (D108-(2)).
    backend = _FakeStructuralBackend({"python": [("mystery.node", "x"), ("function.name", "")]})
    extractor = TreeSitterStructuralExtractor(backend)
    assert extractor.extract_structural("<src>", language="python") == ()
    assert extractor.extract_structural("<src>", language="klingon") == ()  # unsupported => empty


# --------------------------------------------------------------------------- #
# MimeDispatchSourceReader - the (3)-4b COUTURE: route a source to a sub-reader by  #
# its MIME (documents / audio / image), checked against light readers (no brick). #
# --------------------------------------------------------------------------- #
class _MarkerReader:
    """A SourceReader double that returns a fixed marker - lets a test assert WHICH sub-reader the
    dispatcher chose, without any real brick (D126)."""

    def __init__(self, marker: str) -> None:
        self._marker = marker

    def read(self, source: Source) -> str:  # noqa: ARG002 - the routing, not the content, is asserted
        return self._marker


def _src(mime: str) -> Source:
    return Source(ref="x", data=b"", mime=mime)


def test_mime_dispatch_routes_each_family_to_its_reader() -> None:
    # (3)-4b: the COUTURE dispatches on the declared MIME - documents -> Docling-slot, audio -> WhisperKit-
    # slot, image -> OCR-slot - exactly as real_runtime wires it, proved brick-free against markers.
    reader = MimeDispatchSourceReader(
        {
            "text/": _MarkerReader("doc"),
            "audio/": _MarkerReader("voice"),
            "image/": _MarkerReader("ocr"),
        },
        default=_MarkerReader("default"),
    )
    assert reader.read(_src("text/plain")) == "doc"
    assert reader.read(_src("audio/mpeg")) == "voice"  # voice = one more source (AV1)
    assert reader.read(_src("image/png")) == "ocr"


def test_mime_dispatch_falls_back_to_default_on_an_unknown_mime() -> None:
    # An unmatched MIME (or the fail-safe empty MIME) routes to the default reader - the catch-all
    # real_runtime sets to Docling, so an unknown-but-document-ish source still gets extracted.
    reader = MimeDispatchSourceReader(
        {"audio/": _MarkerReader("voice")}, default=_MarkerReader("default")
    )
    assert reader.read(_src("application/x-unknown")) == "default"
    assert reader.read(_src("")) == "default"  # empty MIME => default, never a crash


def test_mime_dispatch_prefers_the_longest_matching_prefix() -> None:
    # The dispatch is a LONGEST-prefix match: a specific office subtype overrides a broad
    # "application/" entry, regardless of the table's insertion order (sorted longest-first).
    reader = MimeDispatchSourceReader(
        {
            "application/": _MarkerReader("broad"),
            "application/vnd.openxmlformats-officedocument": _MarkerReader("office"),
        },
        default=_MarkerReader("default"),
    )
    docx = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    assert reader.read(_src(docx)) == "office"  # longest prefix wins, not first-inserted
    assert reader.read(_src("application/pdf")) == "broad"  # only the broad prefix matches


def test_mime_dispatch_routes_plain_text_families_off_the_document_reader() -> None:
    # (3)-7 fix B: real_runtime routes decodable text families (text/plain notes, text/markdown, text/csv)
    # to the utf-8 PlainTextSourceReader, NOT to Docling - a bare .txt makes Docling raise (no text
    # pipeline, treats it as a failed image conversion: the bm25_ranking.txt symptom). This proves the
    # dispatch decision brick-free with markers: plain-text families reach "plain", everything else "doc".
    reader = MimeDispatchSourceReader(
        {
            "text/plain": _MarkerReader("plain"),
            "text/markdown": _MarkerReader("plain"),
            "text/csv": _MarkerReader("plain"),
            "application/pdf": _MarkerReader("doc"),
            "image/": _MarkerReader("doc"),
        },
        default=_MarkerReader("doc"),
    )
    assert reader.read(_src("text/plain")) == "plain"  # .txt no longer crashes the document reader
    assert reader.read(_src("text/markdown")) == "plain"
    assert reader.read(_src("text/csv")) == "plain"
    assert (
        reader.read(_src("text/html")) == "doc"
    )  # html is markup => still Docling (renders to markdown)
    assert (
        reader.read(_src("application/pdf")) == "doc"
    )  # real documents keep the first-class reader
    assert reader.read(_src("image/png")) == "doc"


def test_real_text_plain_source_is_read_not_raised() -> None:
    # the actual utf-8 reader recovers a plain-text source's bytes (the fidelity the dispatch now grants a
    # .txt): a real .txt is read faithfully instead of exploding in Docling ((3)-7 fix B, end-to-end).
    out = PlainTextSourceReader().read(
        Source("bm25_ranking.txt", b"query\tscore\ndoc1\t0.9", "text/plain")
    )
    assert "doc1" in out and "0.9" in out


def test_mime_dispatch_does_not_catch_a_sub_reader_raise() -> None:
    # Zero-trust seam (D100-3 / D85): the dispatcher is a pure aiguillage - it does NOT net a
    # sub-reader's raise (that is capture's single (3)-4a benne net). A raising reader propagates, so
    # the failure is recorded ONCE where the raw source is preserved, never swallowed here.
    class _Boom:
        def read(self, source: Source) -> str:  # noqa: ARG002
            raise RuntimeError("extraction failed")

    reader = MimeDispatchSourceReader({"audio/": _Boom()}, default=PlainTextSourceReader())
    with pytest.raises(RuntimeError):
        reader.read(_src("audio/wav"))
    # a NON-matching MIME still reaches the (fail-safe) default, unaffected by the raising slot.
    assert reader.read(Source(ref="n", data=b"hi", mime="text/plain")) == "hi"


def test_whisper_multipart_boundary_is_random_and_unforgeable() -> None:
    # (3)-4b audit MINEUR-1 (D100-3): audio bytes are UNTRUSTED, so a crafted payload must NOT forge a
    # part delimiter. The per-request RANDOM boundary (RFC 7578) is absent from the untrusted payload -
    # an embedded fake boundary is inert file content, not a new part - and differs call to call.
    from mnemosyne.ingest.source_whisper import _multipart

    attack = (
        b"\r\n------MnemosyneWhisperKitBoundary\r\n"
        b'Content-Disposition: form-data; name="model"\r\n\r\nINJECTED\r\n'
    )
    body, content_type = _multipart(
        file_field="file", filename="a.wav", file_bytes=attack, fields={"model": "real"}
    )
    boundary = content_type.split("boundary=")[1].encode("utf-8")
    assert (
        boundary not in attack
    )  # the real delimiter is random => cannot be embedded by the payload
    assert body.count(b"--" + boundary) >= 2  # the real parts ARE delimited by the random boundary
    _, content_type2 = _multipart(
        file_field="file", filename="a.wav", file_bytes=b"x", fields={"model": "m"}
    )
    assert content_type != content_type2  # per-request randomness (not a fixed constant)


def test_bootstrap_wires_injected_adapters_and_defaults_to_stubs() -> None:
    # D126 decoupling: bootstrap uses the injected real adapters when given, else the stubs - so
    # the suite runs with nothing installed, and real_runtime() swaps all five (embedder / vector /
    # keyword / graph / generation backend) in at ignition.
    from mnemosyne.runtime.bootstrap import bootstrap

    emb = BgeM3Embedder(_fake_encoder())
    idx = QdrantVectorIndex(_FakeBackend())
    kw = TantivyKeywordIndex(_FakeKeywordBackend())
    graphdb = LadybugGraphStore(_FakeGraphBackend())
    struct = TreeSitterStructuralExtractor(_FakeStructuralBackend({}))
    reader = PlainTextSourceReader()
    gen = _FakeGenerationBackend()
    wired = bootstrap(
        embedder=emb,
        vector=idx,
        keyword=kw,
        graph=graphdb,
        structural_extractor=struct,
        source_reader=reader,
        generation_backend=gen,
    )
    assert wired.embedder is emb
    assert wired.vector is idx
    assert wired.keyword is kw
    assert wired.graph is graphdb  # Moteur A injectable like the other bricks ((3)-3a)
    assert (
        wired.structural_extractor is struct
    )  # tree-sitter pre-pass injectable (6th brick, (3)-3)
    assert (
        wired.source_reader is reader
    )  # source reader injectable (Docling / WhisperKit at (3)-4b)
    assert wired.runner.model_id == "mlx-double"  # the injected MLX decode seam is wired ((3)-2c)

    default = bootstrap()
    assert isinstance(default.embedder, StubEmbedder)
    assert isinstance(default.vector, InMemoryVectorIndex)
    assert isinstance(default.keyword, InMemoryKeywordIndex)
    assert isinstance(default.graph, InMemoryGraphStore)  # graph defaults to the stub (D126)
    assert isinstance(default.structural_extractor, NullStructuralExtractor)  # abstains by default
    assert isinstance(default.source_reader, PlainTextSourceReader)  # utf-8 stub by default (D126)
    assert (
        default.source_extraction_trusted is True
    )  # the stub is faithful => vacuously trusted (D126)
    assert default.runner.model_id == "stub-runner-v0"  # no backend -> the stub decoder (D126)
