"""Structural tests for LOT 4b - the three-store memory layer.

This is NOT the 27-invariant ledger (that is ``test_invariants.py``, which promotes
invariants 9, 10, 14, 20, 24, 25 against these components). Here we exercise the LOT 4b
stores directly: the ``.md``/git truth (merge-on-update, non-destructive - D105 / D58),
the bi-temporal graph behind its seam (D103 / D84), the sensitivity-partitioned vector
leg + hashing embedder (D68), the write-ahead journal's idempotent replay (D105), hybrid
retrieval's low-recall admission (D65), A<->B reconciliation (D60), and document-grain
locks (D106). Producer ≠ verifier (D75): an isolated audit checks this independently.
"""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import pytest

from mnemosyne.config import Policy
from mnemosyne.ports import (
    Bubble,
    ConsistencyMarker,
    DEFAULT_ROLE,
    DocId,
    DocRole,
    Domain,
    Embedder,
    Envelope,
    Fact,
    GovernanceLabel,
    GraphStore,
    IntentLog,
    NodeId,
    ResourceBoundError,
    Sensitivity,
    TruthStore,
    VectorIndex,
)
from mnemosyne.stores import (
    RETRIEVAL_SEED,
    DocumentLocks,
    Fiche,
    FloorScore,
    InMemoryGraphStore,
    InMemoryKeywordIndex,
    InMemoryVectorIndex,
    IntentJournal,
    LockContended,
    LockHeldAcrossWaitError,
    MarkdownTruthStore,
    Reconciler,
    ReconciliationFlag,
    RetrievalCase,
    Retriever,
    StubEmbedder,
    content_hash,
    load_retrieval_golden,
    sweep_floor,
)

# --- builders -------------------------------------------------------------------------

_T0 = datetime(2020, 1, 1, tzinfo=timezone.utc)
_T1 = datetime(2021, 1, 1, tzinfo=timezone.utc)
_T2 = datetime(2022, 1, 1, tzinfo=timezone.utc)


def _label(level: Sensitivity, bubble: str = "b", domains: tuple[str, ...] = ()) -> GovernanceLabel:
    return GovernanceLabel(
        sensitivity=level,
        bubble=Bubble(bubble),
        domains=frozenset(Domain(d) for d in domains),
    )


def _env(text: str, level: Sensitivity = Sensitivity.PUBLIC, **kw: object) -> Envelope[str]:
    return Envelope(payload=text, label=_label(level, **kw))  # type: ignore[arg-type]


def _fact(subject: str, predicate: str, obj: str, valid_from: datetime = _T0) -> Fact:
    return Fact(NodeId(subject), predicate, NodeId(obj), valid_from=valid_from)


def _index(
    index: InMemoryVectorIndex,
    embedder: StubEmbedder,
    doc: str,
    text: str,
    *,
    domains: tuple[str, ...] = (),
) -> None:
    index.upsert(DocId(doc), embedder.embed([text]), _label(Sensitivity.PUBLIC, domains=domains))


def _journal() -> IntentJournal:
    return IntentJournal(
        truth=MarkdownTruthStore(),
        vector=InMemoryVectorIndex(),
        keyword=InMemoryKeywordIndex(),
        graph=InMemoryGraphStore(),
        embedder=StubEmbedder(),
    )


def test_journal_reindex_across_partitions_leaves_no_stale_hit() -> None:
    # D135 audit A-1: a re-ingest that RE-CLASSIFIES a doc must leave NO stale hit in the old
    # partition (invariant 1 / 24). The classifier's semantic pass is a MODEL, so the same doc
    # can route to a different partition across ingests - the derived stores must purge first.
    vector, embedder = InMemoryVectorIndex(), StubEmbedder()
    journal = IntentJournal(
        truth=MarkdownTruthStore(),
        vector=vector,
        keyword=InMemoryKeywordIndex(),
        graph=InMemoryGraphStore(),
        embedder=embedder,
    )
    doc = DocId("d")
    journal.integrate(doc, _env("medical secret", Sensitivity.PUBLIC))
    journal.integrate(doc, _env("medical secret", Sensitivity.SENSIBLE))  # re-classified upward
    (query,) = embedder.embed(["medical secret"])
    assert vector.search(query, within=Sensitivity.PUBLIC) == []  # no stale public hit remains
    assert [h.doc for h in vector.search(query, within=Sensitivity.SENSIBLE)] == [doc]


# ============================ MarkdownTruthStore (D105 / D58) ========================= #


def test_truth_store_conforms_to_the_port() -> None:
    assert isinstance(MarkdownTruthStore(), TruthStore)


def test_truth_write_returns_a_reconstructible_marker() -> None:
    store = MarkdownTruthStore()
    marker = store.write(DocId("d"), _env("hello"))
    assert isinstance(marker, ConsistencyMarker)
    assert marker.content_hash == content_hash("hello")  # a pure function of the text (D105-(2))
    assert marker.indexed_vector is False and marker.indexed_graph is False  # derived not yet done


def test_truth_update_merges_into_the_same_fiche() -> None:
    store = MarkdownTruthStore()
    store.write(DocId("e1"), _env("v1"))
    store.write(DocId("e1"), _env("v2"))
    assert store.count() == 1  # one fiche, merged - never duplicated (invariant 9 / D58)
    assert store.read(DocId("e1")).payload == "v2"  # latest wins


def test_truth_keeps_full_version_history_non_destructively() -> None:
    store = MarkdownTruthStore()
    store.write(DocId("e1"), _env("v1"))
    store.write(DocId("e1"), _env("v2"))
    payloads = [env.payload for env in store.versions(DocId("e1"))]
    assert payloads == ["v1", "v2"]  # prior version kept (non-destructive, invariant 2)


def test_truth_invalidate_is_archival_not_a_hard_delete() -> None:
    store = MarkdownTruthStore()
    store.write(DocId("d"), _env("keep"))
    assert store.is_valid(DocId("d")) is True
    store.invalidate(DocId("d"), reason="obsolete")
    assert store.is_valid(DocId("d")) is False  # validity closed...
    assert store.read(DocId("d")).payload == "keep"  # ...but the content survives (inv. 2)


def test_truth_rewrite_reopens_validity() -> None:
    store = MarkdownTruthStore()
    store.write(DocId("d"), _env("v1"))
    store.invalidate(DocId("d"), reason="x")
    store.write(DocId("d"), _env("v2"))
    assert store.is_valid(DocId("d")) is True  # a fresh assertion supersedes the archival


def test_truth_read_unknown_raises() -> None:
    with pytest.raises(KeyError):
        MarkdownTruthStore().read(DocId("nope"))


def test_fiche_current_is_the_latest_version() -> None:
    fiche = Fiche(doc=DocId("d"), versions=(_env("a"), _env("b")))
    assert fiche.current.payload == "b"


# --- D137: the epistemic ROLE axis on the documentary truth store --------------------- #


def test_truth_document_defaults_to_working_material_fail_closed() -> None:
    # D137: a written document is working material until endorsed - nothing is a source of truth by
    # default (mirrors DEFAULT_SENSITIVITY = SENSIBLE: the safe default, never the permissive one).
    store = MarkdownTruthStore()
    store.write(DocId("d"), _env("draft"))
    assert store.role(DocId("d")) is DocRole.MATIERE_DE_TRAVAIL
    assert DEFAULT_ROLE is DocRole.MATIERE_DE_TRAVAIL


def test_truth_set_role_endorses_and_is_read_back() -> None:
    store = MarkdownTruthStore()
    store.write(DocId("d"), _env("body"))
    store.set_role(DocId("d"), DocRole.BASE_DE_CONNAISSANCES)
    assert store.role(DocId("d")) is DocRole.BASE_DE_CONNAISSANCES


def test_truth_role_of_unknown_document_raises() -> None:
    with pytest.raises(KeyError):
        MarkdownTruthStore().role(DocId("nope"))
    with pytest.raises(KeyError):
        MarkdownTruthStore().set_role(DocId("nope"), DocRole.BASE_DE_CONNAISSANCES)


def test_truth_changed_rewrite_reverts_an_endorsement_but_identical_keeps_it() -> None:
    # D137 / D58: a new VERSION of an endorsed source re-opens the gesture (fail-closed, like living
    # memory's update->PROPOSED); an identical re-write (same content hash) keeps the endorsement.
    store = MarkdownTruthStore()
    store.write(DocId("d"), _env("v1"))
    store.set_role(DocId("d"), DocRole.BASE_DE_CONNAISSANCES)
    store.write(DocId("d"), _env("v1"))  # identical content => endorsement survives
    assert store.role(DocId("d")) is DocRole.BASE_DE_CONNAISSANCES
    store.write(DocId("d"), _env("v2 changed"))  # changed content => back to working material
    assert store.role(DocId("d")) is DocRole.MATIERE_DE_TRAVAIL


# ============================ InMemoryGraphStore (D103 / D84) ========================= #


def test_graph_store_conforms_to_the_port() -> None:
    assert isinstance(InMemoryGraphStore(), GraphStore)


def test_graph_add_fact_requires_an_envelope() -> None:
    graph = InMemoryGraphStore()
    with pytest.raises(TypeError):
        graph.add_fact(_fact("s", "p", "o"))  # type: ignore[arg-type]  # naked fact refused


def test_graph_add_is_idempotent_on_identical_facts() -> None:
    graph = InMemoryGraphStore()
    first = graph.add_fact(Envelope(_fact("s", "p", "o"), _label(Sensitivity.PUBLIC)))
    second = graph.add_fact(Envelope(_fact("s", "p", "o"), _label(Sensitivity.PUBLIC)))
    assert first == second  # same content-addressed id - no duplicate (invariant 24 substrate)
    assert len(graph.query(subject=NodeId("s"))) == 1


def test_graph_query_filters_by_subject_and_predicate() -> None:
    graph = InMemoryGraphStore()
    graph.add_fact(Envelope(_fact("s", "city", "Paris"), _label(Sensitivity.PUBLIC)))
    graph.add_fact(Envelope(_fact("s", "age", "30"), _label(Sensitivity.PUBLIC)))
    graph.add_fact(Envelope(_fact("t", "city", "Lyon"), _label(Sensitivity.PUBLIC)))
    assert len(graph.query(subject=NodeId("s"))) == 2
    assert len(graph.query(predicate="city")) == 2
    hits = graph.query(subject=NodeId("s"), predicate="city")
    assert len(hits) == 1 and str(hits[0].obj) == "Paris"


def test_graph_invalidate_closes_valid_time_bitemporally() -> None:
    graph = InMemoryGraphStore()
    fid = graph.add_fact(Envelope(_fact("s", "p", "o", _T0), _label(Sensitivity.PUBLIC)))
    graph.invalidate(fid, at=_T1)
    assert graph.query(subject=NodeId("s")) == []  # closed as of now (archived)
    assert graph.query(subject=NodeId("s"), as_of=_T0)  # visible in the past (not erased, D84)
    assert graph.query(subject=NodeId("s"), as_of=_T2) == []  # after closure: gone


def test_graph_as_of_excludes_facts_not_yet_valid() -> None:
    graph = InMemoryGraphStore()
    graph.add_fact(Envelope(_fact("s", "p", "o", _T1), _label(Sensitivity.PUBLIC)))
    assert graph.query(subject=NodeId("s"), as_of=_T0) == []  # before valid_from => not yet true
    assert graph.query(subject=NodeId("s"), as_of=_T2)  # after valid_from => visible


# ==================== StubEmbedder + InMemoryVectorIndex (D68) ======================== #


def test_embedder_conforms_and_tags_its_vectors() -> None:
    embedder = StubEmbedder()
    assert isinstance(embedder, Embedder)
    (embedding,) = embedder.embed(["hello world"])
    assert embedding.model_id == embedder.model_id
    assert embedding.dimension == embedder.dimension == len(embedding.vector)


def test_embedder_is_deterministic() -> None:
    embedder = StubEmbedder()
    assert embedder.embed(["same text"])[0].vector == embedder.embed(["same text"])[0].vector


def test_vector_index_conforms_to_the_port() -> None:
    assert isinstance(InMemoryVectorIndex(), VectorIndex)


def test_vector_partitions_isolate_sensible_from_public() -> None:
    index = InMemoryVectorIndex()
    embedder = StubEmbedder()
    (vec,) = embedder.embed(["medical secret"])
    index.upsert(DocId("s1"), [vec], _label(Sensitivity.SENSIBLE))
    # a `public` search never sees the `sensible` doc - partitions are isolated (inv. 1).
    assert index.search(vec, within=Sensitivity.PUBLIC) == []
    assert [h.doc for h in index.search(vec, within=Sensitivity.SENSIBLE)] == [DocId("s1")]


def test_vector_upsert_is_idempotent_by_doc() -> None:
    index = InMemoryVectorIndex()
    (vec,) = StubEmbedder().embed(["x"])
    index.upsert(DocId("d"), [vec], _label(Sensitivity.PUBLIC))
    index.upsert(DocId("d"), [vec], _label(Sensitivity.PUBLIC))
    assert len(index.search(vec, within=Sensitivity.PUBLIC)) == 1  # one doc => no duplicate


def test_vector_search_orders_by_score_and_honours_domains() -> None:
    index = InMemoryVectorIndex()
    embedder = StubEmbedder()
    _index(index, embedder, "d1", "cat black cat", domains=("a",))
    _index(index, embedder, "d2", "white dog", domains=("b",))
    (query,) = embedder.embed(["cat"])
    ranked = index.search(query, within=Sensitivity.PUBLIC)
    assert ranked[0].doc == DocId("d1")  # the cat doc scores higher for a cat query
    scoped = index.search(query, within=Sensitivity.PUBLIC, domains=frozenset({Domain("a")}))
    assert [hit.doc for hit in scoped] == [DocId("d1")]  # domain filter narrows the partition


def test_vector_search_returns_the_best_passage_ordinal() -> None:
    # D136: a doc is indexed as passages; search returns the ordinal (chunk) of the BEST-matching
    # passage, so recall packs THAT passage and never the whole doc (the runner bound would refuse a
    # whole long doc). The in-memory index is the stub the real Qdrant grouping mirrors.
    index = InMemoryVectorIndex()
    embedder = StubEmbedder()
    passages = embedder.embed(["white dog", "the black cat sleeps", "red car"])
    index.upsert(DocId("d"), passages, _label(Sensitivity.PUBLIC))
    (query,) = embedder.embed(["cat"])
    hit = index.search(query, within=Sensitivity.PUBLIC)[0]
    assert hit.chunk == 1  # the middle passage matched the "cat" query - its ordinal is carried


def test_vector_invalidate_purges_the_derivative() -> None:
    index = InMemoryVectorIndex()
    (vec,) = StubEmbedder().embed(["x"])
    index.upsert(DocId("d"), [vec], _label(Sensitivity.PUBLIC))
    assert index.contains(DocId("d")) is True
    index.invalidate(DocId("d"))
    assert index.contains(DocId("d")) is False  # derivative purge (the truth is untouched, D56)


def test_vector_drops_a_non_indexable_passage_keeping_ordinals() -> None:
    # (3) scale-up hardening: a passage whose vector is non-finite (bge-m3 fp16 overflow) or zero-norm
    # (a figures-only page) is DROPPED at upsert while the SURVIVORS keep their original ordinals, so a
    # later select_passage still aligns with the read-time re-chunk (D136) - the drop never renumbers.
    index = InMemoryVectorIndex()
    embedder = StubEmbedder()
    good0, good2 = embedder.embed(["the black cat", "red car"])
    nan1 = replace(good0, vector=(float("nan"),) * embedder.dimension)
    index.upsert(DocId("d"), [good0, nan1, good2], _label(Sensitivity.PUBLIC))
    (query,) = embedder.embed(["car"])
    hit = index.search(query, within=Sensitivity.PUBLIC)[0]
    assert (
        hit.chunk == 2
    )  # the 3rd passage survived and KEPT ordinal 2 (the dropped NaN did not shift it)


def test_vector_drops_a_zero_norm_passage() -> None:
    # a chunk that tokenises to nothing embeds to a zero vector (cosine undefined) - also non-indexable.
    index = InMemoryVectorIndex()
    embedder = StubEmbedder()
    (good,) = embedder.embed(["the black cat"])
    zero = replace(good, vector=(0.0,) * embedder.dimension)
    index.upsert(DocId("d"), [zero, good], _label(Sensitivity.PUBLIC))
    (query,) = embedder.embed(["cat"])
    hit = index.search(query, within=Sensitivity.PUBLIC)[0]
    assert hit.chunk == 1  # the zero-norm first passage dropped; the real one KEPT ordinal 1


def test_vector_doc_with_only_non_indexable_passages_is_not_indexed() -> None:
    index = InMemoryVectorIndex()
    embedder = StubEmbedder()
    (good,) = embedder.embed(["x"])
    nan = replace(good, vector=(float("nan"),) * embedder.dimension)
    zero = replace(good, vector=(0.0,) * embedder.dimension)
    index.upsert(DocId("d"), [nan, zero], _label(Sensitivity.PUBLIC))
    assert (
        index.contains(DocId("d")) is False
    )  # nothing indexable => the doc is honestly absent (D100)


def test_journal_integrates_a_fully_degenerate_document_without_crashing() -> None:
    # (3) scale-up: the shape of the Qdrant-400 bug - every passage embeds to a non-finite vector. The
    # write-ahead path must NOT crash: the datum lands truth-first (D105) and is simply absent from the
    # dense index (honest, D100), its raw text preserved (D56 / D85).
    class _AllNaN(StubEmbedder):
        def embed(self, texts):  # type: ignore[override]
            return [
                replace(e, vector=(float("nan"),) * self.dimension)
                for e in super().embed(list(texts))
            ]

    journal = IntentJournal(
        truth=MarkdownTruthStore(),
        vector=InMemoryVectorIndex(),
        keyword=InMemoryKeywordIndex(),
        graph=InMemoryGraphStore(),
        embedder=_AllNaN(),
    )
    doc = DocId("d")
    journal.integrate(doc, _env("white dog and black cat"))  # must not raise
    assert (
        journal.marker(doc).indexed_vector is False
    )  # honestly not vector-indexed (all passages dropped)


# ============================== IntentJournal (D105) ================================== #


def test_journal_conforms_to_the_intentlog_port() -> None:
    assert isinstance(_journal(), IntentLog)


def test_journal_integrate_wires_all_three_stores() -> None:
    journal = _journal()
    truth, vector, graph = journal._truth, journal._vector, journal._graph  # noqa: SLF001
    journal.integrate(DocId("d"), _env("hello world"), facts=(_fact("d", "kind", "note"),))
    assert truth.read(DocId("d")).payload == "hello world"  # Moteur B
    assert vector.contains(DocId("d")) is True  # dense leg
    assert len(graph.query(subject=NodeId("d"))) == 1  # Moteur A
    marker = journal.marker(DocId("d"))
    assert marker.indexed_vector is True and marker.indexed_graph is True


def test_journal_replay_is_idempotent() -> None:
    journal = _journal()
    journal.integrate(DocId("d"), _env("hello"), facts=(_fact("d", "k", "v"),))
    before = journal.fingerprint()
    journal.replay()
    journal.replay()
    assert journal.fingerprint() == before  # replaying changes nothing (invariant 24)


def test_journal_plan_then_replay_recovers_a_crash() -> None:
    journal = _journal()
    journal.plan(DocId("d"), _env("bonjour"))
    assert journal.marker(DocId("d")).indexed_vector is False  # derived pending after plan
    assert not journal._vector.contains(DocId("d"))  # noqa: SLF001 - truly absent, not just flagged
    assert journal._truth.read(DocId("d")).payload == "bonjour"  # noqa: SLF001 - arbiter first
    journal.replay()
    assert journal.marker(DocId("d")).indexed_vector is True  # replay finished the derived leg
    assert journal._vector.contains(DocId("d"))  # noqa: SLF001 - the leg was rebuilt, not faked


def test_journal_record_then_replay_rolls_back_without_durable_truth() -> None:
    from mnemosyne.ports import Intent, IntentKind

    journal = _journal()
    # the raw IntentLog path: an intent recorded but whose truth never landed (a crash
    # before the arbiter write) has nothing durable to finish => replay rolls it back.
    journal.record(Intent(IntentKind.INTEGRATE, DocId("ghost"), _label(Sensitivity.PUBLIC)))
    journal.replay()  # rolled back - no crash, no invented state
    with pytest.raises(KeyError):
        journal.marker(DocId("ghost"))


def test_journal_marker_is_a_pure_function_of_the_truth() -> None:
    journal = _journal()
    journal.integrate(DocId("d"), _env("hello"))
    assert journal.marker(DocId("d")).content_hash == content_hash("hello")


# =============================== Retriever (D65 / inv. 14) ============================ #


def test_retriever_admits_low_recall_on_an_empty_index() -> None:
    retriever = Retriever(InMemoryVectorIndex(), StubEmbedder(), min_score=0.3)
    result = retriever.retrieve("anything at all", within=Sensitivity.PUBLIC)
    assert result.admitted_low_recall is True and result.hits == ()


def test_retriever_returns_confident_hits_above_the_floor() -> None:
    index, embedder = InMemoryVectorIndex(), StubEmbedder()
    _index(index, embedder, "d1", "Paris capital of France")
    result = Retriever(index, embedder, min_score=0.3).retrieve(
        "Paris capital", within=Sensitivity.PUBLIC
    )
    assert result.admitted_low_recall is False and result.hits[0].doc == DocId("d1")


def test_retriever_floor_withholds_a_too_weak_hit() -> None:
    index, embedder = InMemoryVectorIndex(), StubEmbedder()
    _index(index, embedder, "d1", "Paris capital of France")
    strict = Retriever(index, embedder, min_score=0.999)
    assert strict.retrieve("Paris capital", within=Sensitivity.PUBLIC).admitted_low_recall is True


@pytest.mark.parametrize("bad", [-0.1, 1.5])
def test_retriever_rejects_an_out_of_range_floor(bad: float) -> None:
    with pytest.raises(ValueError, match="min_score"):
        Retriever(InMemoryVectorIndex(), StubEmbedder(), min_score=bad)


# ===================== Retriever - per-domain recall floor (D139) ===================== #


def _policy(recall_floor_by_domain: dict[str, float] | None = None) -> Policy:
    """A minimal, deny-by-default test policy - only the field D139 needs varies."""
    return Policy(
        profile="test",
        canal_a_auto=frozenset(),
        egress_allowlist=frozenset(),
        contracts=(),
        declared_domains={},
        bounds={},
        quotas={},
        recall_floor_by_domain={
            Domain(d): floor for d, floor in (recall_floor_by_domain or {}).items()
        },
    )


def test_retriever_uses_the_calibrated_floor_for_a_known_domain() -> None:
    # D139: a domain WITH an earned entry in the per-domain table gates on ITS OWN floor, not the
    # embedder-declared default (min_score) - here made stricter than the hit's score so a doc that
    # would otherwise clear the default is withheld.
    index, embedder = InMemoryVectorIndex(), StubEmbedder()
    _index(index, embedder, "d1", "Paris capital of France", domains=("geo",))
    retriever = Retriever(
        index, embedder, min_score=0.3, recall_floor_by_domain={Domain("geo"): 0.999}
    )
    result = retriever.retrieve(
        "Paris capital", within=Sensitivity.PUBLIC, domains=frozenset({Domain("geo")})
    )
    assert result.admitted_low_recall is True


def test_retriever_falls_back_to_the_default_for_an_uncalibrated_domain() -> None:
    # D139: a domain ABSENT from the per-domain table (never calibrated) resolves to min_score,
    # exactly the pre-D139 shape - no KeyError, no silent 0.0, the conformant default.
    index, embedder = InMemoryVectorIndex(), StubEmbedder()
    _index(index, embedder, "d1", "Paris capital of France", domains=("geo",))
    retriever = Retriever(
        index, embedder, min_score=0.3, recall_floor_by_domain={Domain("finance"): 0.999}
    )
    result = retriever.retrieve(
        "Paris capital", within=Sensitivity.PUBLIC, domains=frozenset({Domain("geo")})
    )
    assert result.admitted_low_recall is False and result.hits[0].doc == DocId("d1")


def test_retriever_falls_back_to_the_default_when_several_domains_are_named() -> None:
    # D139: several domains in one call never average or pick a winner between two calibrated
    # floors - the floor keys on a FACT of the query (a single named domain), never a guess.
    index, embedder = InMemoryVectorIndex(), StubEmbedder()
    _index(index, embedder, "d1", "Paris capital of France", domains=("geo", "history"))
    retriever = Retriever(
        index,
        embedder,
        min_score=0.3,
        recall_floor_by_domain={Domain("geo"): 0.999, Domain("history"): 0.999},
    )
    result = retriever.retrieve(
        "Paris capital",
        within=Sensitivity.PUBLIC,
        domains=frozenset({Domain("geo"), Domain("history")}),
    )
    assert result.admitted_low_recall is False and result.hits[0].doc == DocId("d1")


def test_retriever_without_a_per_domain_table_behaves_exactly_as_before_d139() -> None:
    # Retro-compatibility (D139): a Retriever built with NO recall_floor_by_domain at all (the
    # pre-D139 constructor call) resolves every domain to min_score, unchanged.
    index, embedder = InMemoryVectorIndex(), StubEmbedder()
    _index(index, embedder, "d1", "Paris capital of France", domains=("geo",))
    retriever = Retriever(index, embedder, min_score=0.3)
    result = retriever.retrieve(
        "Paris capital", within=Sensitivity.PUBLIC, domains=frozenset({Domain("geo")})
    )
    assert result.admitted_low_recall is False and result.hits[0].doc == DocId("d1")


def test_retriever_from_policy_reads_the_calibrated_table_from_the_protected_zone() -> None:
    # D139: the per-domain table is a CONFIG concern (the protected policy zone), never a
    # hard-coded dict in the retrieval module - from_policy is the wiring that reads it.
    index, embedder = InMemoryVectorIndex(), StubEmbedder()
    _index(index, embedder, "d1", "Paris capital of France", domains=("geo",))
    policy = _policy({"geo": 0.999})
    retriever = Retriever.from_policy(policy, index, embedder)
    result = retriever.retrieve(
        "Paris capital", within=Sensitivity.PUBLIC, domains=frozenset({Domain("geo")})
    )
    assert result.admitted_low_recall is True


def test_retriever_from_policy_with_an_empty_zone_matches_the_pre_d139_default() -> None:
    # Retro-compatibility (D139): an empty policy zone (no domain calibrated yet, the shipped
    # default in policy.toml) reproduces the identical pre-D139 outcome for every domain.
    index, embedder = InMemoryVectorIndex(), StubEmbedder()
    _index(index, embedder, "d1", "Paris capital of France", domains=("geo",))
    retriever = Retriever.from_policy(_policy(), index, embedder, keyword=None)
    result = retriever.retrieve(
        "Paris capital", within=Sensitivity.PUBLIC, domains=frozenset({Domain("geo")})
    )
    assert result.admitted_low_recall is False and result.hits[0].doc == DocId("d1")


def test_retriever_per_domain_floor_also_gates_the_hybrid_leg() -> None:
    # D139 x D68: the per-domain floor resolution must reach BOTH admission paths - dense-only
    # AND hybrid (a keyword leg wired) - since _admit_hybrid gates its dense_cleared set on the
    # same per-call floor, not the instance default.
    index, embedder = InMemoryVectorIndex(), StubEmbedder()
    keyword = InMemoryKeywordIndex()
    _index(index, embedder, "d1", "Paris capital of France", domains=("geo",))
    keyword.index(
        DocId("d1"), "Paris capital of France", _label(Sensitivity.PUBLIC, domains=("geo",))
    )
    retriever = Retriever(
        index,
        embedder,
        keyword=keyword,
        min_score=0.3,
        recall_floor_by_domain={Domain("geo"): 0.999},
    )
    result = retriever.retrieve(
        "Paris capital", within=Sensitivity.PUBLIC, domains=frozenset({Domain("geo")})
    )
    # the dense leg is withheld by the stricter calibrated floor, but the keyword leg still
    # matches lexically - admission stays open (D65 hybrid: dense floor OR lexical match).
    assert result.admitted_low_recall is False and result.hits[0].doc == DocId("d1")


# =============================== Reconciler (D60 / inv. 10) =========================== #


def test_reconciler_flags_a_contradiction_non_destructively() -> None:
    truth, graph = MarkdownTruthStore(), InMemoryGraphStore()
    truth.write(DocId("alice"), _env("Lyon"))
    graph.add_fact(Envelope(_fact("alice", "city", "Paris"), _label(Sensitivity.PUBLIC)))
    flag = Reconciler(truth, graph).reconcile(NodeId("alice"), "city")
    assert isinstance(flag, ReconciliationFlag)
    assert flag.living_value == "Paris" and flag.documentary_value == "Lyon"
    assert truth.read(DocId("alice")).payload == "Lyon"  # untouched (non-destructive, D82)


def test_reconciler_returns_none_on_agreement() -> None:
    truth, graph = MarkdownTruthStore(), InMemoryGraphStore()
    truth.write(DocId("bob"), _env("Nice"))
    graph.add_fact(Envelope(_fact("bob", "city", "Nice"), _label(Sensitivity.PUBLIC)))
    assert Reconciler(truth, graph).reconcile(NodeId("bob"), "city") is None


def test_reconciler_returns_none_when_a_side_is_absent() -> None:
    truth, graph = MarkdownTruthStore(), InMemoryGraphStore()
    graph.add_fact(Envelope(_fact("x", "city", "Paris"), _label(Sensitivity.PUBLIC)))
    assert Reconciler(truth, graph).reconcile(NodeId("x"), "city") is None  # no documentary side
    assert Reconciler(truth, graph).reconcile(NodeId("y"), "city") is None  # no living side


# =============================== DocumentLocks (D106 / inv. 25) ======================= #


def test_locks_are_document_grained() -> None:
    locks = DocumentLocks()
    with locks.write(DocId("A")):
        with locks.write(DocId("B")):  # a different doc is free - no global lock
            pass
        with pytest.raises(LockContended):
            with locks.write(DocId("A")):  # the same doc is contended
                pass


def test_locks_never_block_a_read() -> None:
    locks = DocumentLocks()
    with locks.write(DocId("A")):
        assert locks.read_blocked(DocId("A")) is False


def test_locks_forbid_holding_across_an_external_wait() -> None:
    locks = DocumentLocks()
    with locks.write(DocId("A")):
        with pytest.raises(LockHeldAcrossWaitError):
            locks.external_wait()
    locks.external_wait()  # released => fine


def test_lock_errors_are_normalized_resource_bounds() -> None:
    assert issubclass(LockContended, ResourceBoundError)
    assert issubclass(LockHeldAcrossWaitError, ResourceBoundError)


def test_locks_release_on_exception() -> None:
    locks = DocumentLocks()
    with pytest.raises(RuntimeError):
        with locks.write(DocId("A")):
            raise RuntimeError("boom")
    with locks.write(DocId("A")):  # the lock was released by the context manager
        pass


# --- retrieval recall-floor sweep ((3)-2a / D69) - the floor EARNED from a golden set, not hand-set ---
# Producer ≠ verifier (D75): an isolated audit checks this independently. The point is D69 + honesty
# (F3 / D100): a separating similarity earns a clean floor, a blind one only a poor F1 (never fabricated),
# a golden that proves nothing NEVER relaxes the floor, and an F1 tie leans prudent (invariant 14).

_SEED_RELEVANT = frozenset(passage for case in RETRIEVAL_SEED for passage in case.relevant)


def _perfect_similarity(_query: str, passage: str) -> float:
    """An oracle separator: a seed-relevant passage scores 1.0, anything else 0.0 (cleanly separable)."""
    return 1.0 if passage in _SEED_RELEVANT else 0.0


def test_sweep_earns_a_clean_floor_when_the_similarity_separates() -> None:
    # a separating similarity earns F1 1.0 at a positive floor - the mechanism the real bge-m3 exercises.
    result = sweep_floor(_perfect_similarity, RETRIEVAL_SEED)
    assert isinstance(result, FloorScore)
    assert result.f1 == 1.0 and result.precision == 1.0 and result.recall == 1.0
    assert (
        result.floor == 1.0
    )  # a perfect oracle => the highest floor still clearing every relevant
    assert result.cases == len(RETRIEVAL_SEED)


def test_sweep_reports_a_poor_f1_when_the_similarity_cannot_separate() -> None:
    # a blind embedder (constant score) cannot separate relevant from distractor: the sweep reports the
    # HONEST poor F1 (never fabricates a clean floor, F3), so the recommendation is visibly not adoptable.
    result = sweep_floor(lambda _q, _p: 0.5, RETRIEVAL_SEED)
    assert result.floor == 0.5  # the only observed score
    assert result.f1 < 1.0 and result.recall == 1.0 and result.precision == 0.5


def test_sweep_of_an_empty_golden_fails_closed_to_the_max_floor() -> None:
    # a golden that proves nothing may NEVER relax the floor - it returns the maximal, fail-safe floor
    # (invariant 14 / D100), exactly as an empty extraction / fidelity golden scores untrusted (D69).
    result = sweep_floor(lambda _q, _p: 0.9, ())
    assert result.floor == 1.0 and result.f1 == 0.0


def test_sweep_of_an_all_distractor_golden_fails_closed() -> None:
    # no relevant passage anywhere => nothing to recover => the floor may not be lowered (fail-closed).
    case = RetrievalCase(query="q", relevant=frozenset(), distractors=frozenset({"x", "y"}))
    result = sweep_floor(lambda _q, _p: 0.9, (case,))
    assert result.floor == 1.0 and result.f1 == 0.0


def test_sweep_breaks_an_f1_tie_toward_the_higher_more_prudent_floor() -> None:
    # a high floor (few, precise) and a low floor (all, noisy) tie on F1 0.5 here; the sweep keeps the
    # HIGHER, more prudent floor - admit "I don't know" more readily than admit a distractor (inv. 14).
    case = RetrievalCase(
        query="q",
        relevant=frozenset({"clears-high", "mid-1", "mid-2"}),
        distractors=frozenset(f"noise-{i}" for i in range(6)),
    )
    scores = {"clears-high": 0.9}  # every other passage scores 0.5
    result = sweep_floor(lambda _q, passage: scores.get(passage, 0.5), (case,))
    assert result.f1 == 0.5  # both the 0.9 floor and the 0.5 floor reach F1 0.5
    assert result.floor == 0.9  # the tie breaks to the higher floor


def test_sweep_nets_a_raising_similarity_as_recall_loss_never_crashes() -> None:
    # a raising similarity is a FAILED match (recall loss), not an aborted run - every pair scores below
    # every finite floor => no candidate => fail-safe floor, never a crash (F3), like the other goldens.
    def boom(_query: str, _passage: str) -> float:
        raise RuntimeError("brick fell over")

    result = sweep_floor(boom, RETRIEVAL_SEED)
    assert result.floor == 1.0 and result.f1 == 0.0


def test_sweep_fails_closed_when_no_relevant_passage_is_even_scorable() -> None:
    # audit (3)-2a finding 1 / D100: the fail-safe must key on a FINITE relevant score, not a relevant
    # LABEL. A golden whose relevant pairs are all unscorable (non-finite / raising) while a distractor
    # scores finite recovered NOTHING relevant, so it may not RELAX the floor below the fail-safe 1.0.
    case = RetrievalCase(query="q", relevant=frozenset({"r"}), distractors=frozenset({"d"}))
    nan_relevant = sweep_floor(lambda _q, passage: float("nan") if passage == "r" else 0.5, (case,))
    assert (
        nan_relevant.floor == 1.0 and nan_relevant.f1 == 0.0
    )  # before the fix this returned floor 0.5

    def raise_on_relevant(_query: str, passage: str) -> float:
        if passage == "r":
            raise RuntimeError("embedder choked on this text")
        return 0.42

    raised_relevant = sweep_floor(raise_on_relevant, (case,))
    assert (
        raised_relevant.floor == 1.0 and raised_relevant.f1 == 0.0
    )  # before the fix this returned 0.42


# --- loading a real corpus golden ((3)-2b) - the gitignored JSON that expands the seed at ignition -
# Fail-closed (F3 / D100): a malformed golden RAISES rather than silently yielding a laxer/empty set that
# could talk the floor down. The passages themselves live outside git (perso); tests use synthetic temp files.


def _write_golden(tmp_path: Path, payload: object) -> Path:
    path = tmp_path / "retrieval.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_load_retrieval_golden_parses_cases(tmp_path: Path) -> None:
    path = _write_golden(
        tmp_path,
        [
            {"query": "q1", "relevant": ["r1a", "r1b"], "distractors": ["d1"]},
            {"query": "q2", "relevant": ["r2"], "distractors": ["d2a", "d2b"]},
        ],
    )
    cases = load_retrieval_golden(path)
    assert isinstance(cases, tuple) and all(isinstance(c, RetrievalCase) for c in cases)
    assert cases[0].query == "q1"
    assert cases[0].relevant == frozenset({"r1a", "r1b"}) and cases[0].distractors == frozenset(
        {"d1"}
    )
    assert cases[1].relevant == frozenset({"r2"}) and cases[1].distractors == frozenset(
        {"d2a", "d2b"}
    )


def test_load_retrieval_golden_allows_optional_distractors_and_extra_keys(tmp_path: Path) -> None:
    # `distractors` is optional (a relevant-only case is valid, like RetrievalCase); unknown keys (e.g. an
    # inline `_note`) are ignored, never a parse failure.
    path = _write_golden(
        tmp_path, [{"query": "q", "relevant": ["r"], "_note": "documented inline"}]
    )
    cases = load_retrieval_golden(path)
    assert cases[0].relevant == frozenset({"r"}) and cases[0].distractors == frozenset()


def test_loaded_golden_feeds_the_sweep_end_to_end(tmp_path: Path) -> None:
    # the wiring the ignition run uses: a loaded golden sweeps exactly like the seed. A separating oracle
    # earns a clean floor over the loaded cases (F1 1.0), proving the load -> sweep seam (D69 / D126).
    path = _write_golden(
        tmp_path, [{"query": "q", "relevant": ["signal"], "distractors": ["noise-a", "noise-b"]}]
    )
    cases = load_retrieval_golden(path)
    result = sweep_floor(lambda _q, passage: 1.0 if passage == "signal" else 0.0, cases)
    assert result.f1 == 1.0 and result.floor == 1.0 and result.cases == 1


@pytest.mark.parametrize(
    "payload",
    [
        [],  # an empty golden proves nothing - a laxer set must never come from a blank file
        {"query": "q", "relevant": ["r"]},  # a bare object, not a list of cases
        [{"relevant": ["r"]}],  # a case with no query
        [{"query": "  ", "relevant": ["r"]}],  # a blank query
        [{"query": "q", "relevant": "r"}],  # relevant not a list
        [{"query": "q", "relevant": ["ok", ""]}],  # an empty-string passage
        [{"query": "q", "relevant": ["ok", 7]}],  # a non-string passage
        [
            {"query": "q", "relevant": ["dup"], "distractors": ["dup"]}
        ],  # answer == distractor (contradiction)
    ],
)
def test_load_retrieval_golden_fails_closed_on_a_malformed_file(
    tmp_path: Path, payload: object
) -> None:
    with pytest.raises(ValueError):
        load_retrieval_golden(_write_golden(tmp_path, payload))


def test_load_retrieval_golden_raises_on_non_json(tmp_path: Path) -> None:
    # a corrupt (non-JSON) file RAISES (JSONDecodeError is a ValueError) - never a silent empty fallback.
    path = tmp_path / "retrieval.json"
    path.write_text("this is not json {", encoding="utf-8")
    with pytest.raises(ValueError):
        load_retrieval_golden(path)
