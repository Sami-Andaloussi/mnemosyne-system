"""RAPTOR summary tree (Ch.5 / RAG niveau 2) - store mechanics, the summarizer seam, the corpus
pass, and the retrieval read-path, all brick-free (D126).

Faithful to RAPTOR's essence (retrieve across a TREE of summaries) grounded on the corpus's OWN
hierarchy: a **book** synopsis per DONE library book, rolled up into a **domain** synopsis per
``(sensitivity, bubble, domain)``. This file proves, against a DETERMINISTIC fake summarizer (never
a model): content-addressed identity, cloisonnement (a cluster never crosses a partition), label
inheritance (MAX, raise-only), idempotence, the self-reconciling staleness sweep, the brick-free
abstention posture, and that a summary surfaces at :meth:`~mnemosyne.api.core_api.CoreApi.recall`
as working material ONLY - never a citable fact, never disturbing the unchanged leaf-document path.
Producer ≠ verifier (D75): an isolated audit checks this independently.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path

import pytest

from mnemosyne.api import CoreApi
from mnemosyne.config import Policy
from mnemosyne.ingest.library import (
    KNOWLEDGE_BUBBLE,
    BookRecord,
    BookStatus,
    LibraryManifest,
    detect_orphan_vectors,
)
from mnemosyne.ingest.raptor_build import RaptorBuildReport, build_raptor_tree
from mnemosyne.ingest.raptor_summarize import (
    NullRaptorSummarizer,
    RaptorSummarizer,
    RunnerRaptorSummarizer,
)
from mnemosyne.ports import (
    Bubble,
    DocId,
    Domain,
    Effect,
    Envelope,
    GovernanceLabel,
    Grant,
    GrammarConstraint,
    GuardRequest,
    RoutingClass,
    Sensitivity,
)
from mnemosyne.runtime import ModelRouter, bootstrap
from mnemosyne.runtime.models import _model_call_request
from mnemosyne.stores import (
    InMemoryVectorIndex,
    MarkdownTruthStore,
    RaptorNode,
    RaptorStore,
    StubEmbedder,
    is_raptor_summary,
    raptor_doc_id,
)

_FINANCE = Domain("finance")
_MACRO = Domain("macro")


# --------------------------------------------------------------------------- #
# Shared builders                                                              #
# --------------------------------------------------------------------------- #
def _label(
    sensitivity: Sensitivity = Sensitivity.SENSIBLE,
    *,
    bubble: Bubble = KNOWLEDGE_BUBBLE,
    domain: Domain = _FINANCE,
) -> GovernanceLabel:
    return GovernanceLabel(sensitivity=sensitivity, bubble=bubble, domains=frozenset({domain}))


def _seed_book(
    truth: MarkdownTruthStore,
    manifest: LibraryManifest,
    *,
    doc: str,
    text: str,
    domain: str = "finance",
    sensitivity: Sensitivity = Sensitivity.SENSIBLE,
    bubble: Bubble = KNOWLEDGE_BUBBLE,
) -> DocId:
    """Seed one ``DONE`` book: a truth envelope + its manifest row - mirrors what
    ``ingest_library`` itself leaves behind after a real capture, the exact fixture
    :func:`~mnemosyne.ingest.raptor_build.build_raptor_tree` reads."""
    book_doc = DocId(doc)
    truth.write(book_doc, Envelope(text, _label(sensitivity, bubble=bubble, domain=Domain(domain))))
    manifest.records[doc] = BookRecord(
        rel=f"{domain}/{doc.rsplit('/', 1)[-1]}.md",
        domain=domain,
        doc=doc,
        status=BookStatus.DONE,
        chars=len(text),
        at="2026-01-01T00:00:00+00:00",
    )
    return book_doc


class _FakeSummarizer:
    """A deterministic fake (D126, no model): a synopsis naming its own (sorted) member texts, so
    a test can assert exactly which cluster was summarized without a model. Records every call for
    introspection; ``abstain_for`` / ``raise_for`` name member texts that should decline / blow up,
    proving the abstention and per-cluster-isolation paths without a real model ever misbehaving."""

    def __init__(
        self,
        *,
        abstain_for: frozenset[str] = frozenset(),
        raise_for: frozenset[str] = frozenset(),
    ) -> None:
        self.calls: list[tuple[tuple[str, ...], GovernanceLabel]] = []
        self._abstain_for = abstain_for
        self._raise_for = raise_for

    def summarize(self, member_texts: Sequence[str], *, label: GovernanceLabel) -> str | None:
        texts = tuple(member_texts)
        self.calls.append((texts, label))
        if any(t in self._raise_for for t in texts):
            raise RuntimeError("fake summarizer failure (netted per cluster)")
        if any(t in self._abstain_for for t in texts):
            return None
        return "synopsis of: " + " ".join(sorted(texts))


def _manifest(tmp_path: Path) -> tuple[LibraryManifest, Path]:
    path = tmp_path / "raptor_manifest.json"
    return LibraryManifest(path=path, records={}), path


# =========================== stores/raptor.py - store mechanics ======================= #


def test_raptor_doc_id_is_stable_regardless_of_member_order() -> None:
    a, b = DocId("library/a"), DocId("library/b")
    assert raptor_doc_id("book", (a, b)) == raptor_doc_id("book", (b, a))


def test_raptor_doc_id_changes_when_members_change() -> None:
    a, b, c = DocId("library/a"), DocId("library/b"), DocId("library/c")
    assert raptor_doc_id("book", (a, b)) != raptor_doc_id("book", (a, c))


def test_raptor_doc_id_differs_by_level_for_the_same_single_member() -> None:
    # a book node and a domain node must never collide even over the identical member set
    # (the level is baked into the hashed payload, not just the path prefix).
    a = DocId("library/a")
    assert raptor_doc_id("book", (a,)) != raptor_doc_id("domain", (a,))


def test_raptor_ids_are_namespaced_under_library_summary_prefix() -> None:
    node_id = raptor_doc_id("book", (DocId("library/a"),))
    assert is_raptor_summary(node_id) is True
    assert is_raptor_summary(DocId("library/a")) is False  # an ordinary leaf doc is NOT a summary


def test_raptor_store_ram_default_put_get_contains_invalidate() -> None:
    store = RaptorStore()
    node = RaptorNode(
        doc=raptor_doc_id("book", (DocId("library/a"),)),
        level="book",
        member_ids=(DocId("library/a"),),
        text="a synopsis",
        label=_label(),
    )
    assert store.contains(node.doc) is False
    store.put(node)
    assert store.contains(node.doc) is True
    assert store.get(node.doc) == node
    store.invalidate(node.doc)
    assert store.contains(node.doc) is False  # a derivative purge (D56), idempotent to call again
    store.invalidate(node.doc)


def test_raptor_store_get_of_unknown_id_raises_keyerror() -> None:
    with pytest.raises(KeyError):
        RaptorStore().get(DocId("library/summary/book/nope"))


def test_raptor_store_disk_backend_round_trips_across_instances(tmp_path: Path) -> None:
    path = tmp_path / "raptor_store.jsonl"
    node = RaptorNode(
        doc=raptor_doc_id("domain", (DocId("library/summary/book/aaa"),)),
        level="domain",
        member_ids=(DocId("library/summary/book/aaa"),),
        text="a domain synopsis",
        label=_label(Sensitivity.PERSO, bubble=Bubble("knowledge"), domain=_MACRO),
    )
    RaptorStore(base_path=path).put(node)
    # a FRESH instance over the SAME path sees it - proves the JSONL round-trips fully, including
    # the label's sensitivity / bubble / domains (D56: only these travel, never the provenance).
    reopened = RaptorStore(base_path=path)
    assert reopened.contains(node.doc) is True
    assert reopened.get(node.doc) == node
    assert reopened.iter_ids() == (node.doc,)


def test_raptor_store_disk_backend_invalidate_removes_the_row(tmp_path: Path) -> None:
    path = tmp_path / "raptor_store.jsonl"
    node = RaptorNode(
        doc=raptor_doc_id("book", (DocId("library/a"),)),
        level="book",
        member_ids=(DocId("library/a"),),
        text="text",
        label=_label(),
    )
    store = RaptorStore(base_path=path)
    store.put(node)
    store.invalidate(node.doc)
    assert RaptorStore(base_path=path).contains(node.doc) is False


def test_raptor_store_disk_backend_survives_a_corrupt_line(tmp_path: Path) -> None:
    # fail-safe (D100): one corrupt JSON line must not take down the whole store.
    path = tmp_path / "raptor_store.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("not json at all\n", encoding="utf-8")
    store = RaptorStore(base_path=path)
    assert store.iter_ids() == ()
    node = RaptorNode(
        doc=raptor_doc_id("book", (DocId("library/a"),)),
        level="book",
        member_ids=(DocId("library/a"),),
        text="text",
        label=_label(),
    )
    store.put(node)  # still writable afterwards
    assert store.contains(node.doc) is True


# ======================= RAPTOR summarizer seam (ingest/raptor_summarize.py) =========== #


def test_null_raptor_summarizer_always_abstains() -> None:
    assert NullRaptorSummarizer().summarize(["a passage"], label=_label()) is None


def test_null_raptor_summarizer_conforms_to_the_protocol() -> None:
    assert isinstance(NullRaptorSummarizer(), RaptorSummarizer)


def _bare_grant(label: GovernanceLabel) -> Grant:
    """A test-double grant (bare shape, no Guard token - the stub runner never redeems it)."""
    return Grant(
        request=GuardRequest(
            effect=Effect.MODEL_CALL,
            subject=label.bubble,
            inputs=(label,),
            descriptor="test raptor",
        ),
        released_label=label,
    )


class _StubRunner:
    """A weightless Runner double (D126): scripted completions on ``complete``; records every
    grant + prompt it was handed (mirrors ``tests/distillation/test_refiners.py``'s own double)."""

    def __init__(self, *, completions: list[str] | None = None) -> None:
        self._completions = completions
        self._i = 0
        self.prompts: list[str] = []
        self.grants: list[Grant] = []

    def complete(
        self, prompt: Envelope[str], *, grant: Grant, constraint: GrammarConstraint | None = None
    ) -> Envelope[str]:
        self.grants.append(grant)
        self.prompts.append(prompt.payload)
        text = (
            self._completions[self._i]
            if self._completions is not None
            else f"completion-{self._i + 1}"
        )
        self._i += 1
        return Envelope(payload=text, label=prompt.label)

    def complete_structured(
        self, prompt: Envelope[str], *, grant: Grant, constraint: GrammarConstraint
    ) -> Envelope[str]:  # pragma: no cover - unused by the summarizer
        raise NotImplementedError


def test_runner_raptor_summarizer_mints_a_grant_and_returns_the_completion() -> None:
    runner = _StubRunner(completions=["a faithful synopsis"])
    summarizer = RunnerRaptorSummarizer(runner, _bare_grant)

    result = summarizer.summarize(["passage one", "passage two"], label=_label())

    assert result == "a faithful synopsis"
    assert len(runner.grants) == 1  # one fresh MODEL_CALL grant, never self-granted (D100)
    assert runner.grants[0].request.effect is Effect.MODEL_CALL
    assert "passage one" in runner.prompts[0] and "passage two" in runner.prompts[0]


def test_runner_raptor_summarizer_abstains_on_an_empty_cluster_without_a_model_call() -> None:
    runner = _StubRunner(completions=["should never be reached"])
    summarizer = RunnerRaptorSummarizer(runner, _bare_grant)

    result = summarizer.summarize(["", "   "], label=_label())

    assert result is None
    assert runner.grants == []  # never spent a call for nothing


def test_runner_raptor_summarizer_map_reduces_a_cluster_that_overflows_one_prompt() -> None:
    # RAPTOR's essence: a cluster whose joined passages exceed ONE prompt is summarized
    # HIERARCHICALLY - a MAP over budget-sized groups then a REDUCE over the partials - never a
    # single over-budget prompt the runner would fail-close (D136). Pre-fix this abstained: 209/232
    # library books overflowed the ceiling and produced no synopsis at all.
    ceiling = 400
    runner = _StubRunner()  # default "completion-N" - one distinct output per call
    summarizer = RunnerRaptorSummarizer(runner, _bare_grant, max_prompt_chars=ceiling)
    passages = [f"passage number {i} with some filler words here" for i in range(24)]

    result = summarizer.summarize(passages, label=_label())

    assert result is not None
    assert len(runner.prompts) > 1  # map-reduce engaged - not one over-budget call
    assert all(
        len(p) <= ceiling for p in runner.prompts
    )  # every call stayed under the bound (D136)
    assert result == f"completion-{len(runner.prompts)}"  # the FINAL reduce call's synopsis wins
    assert len(runner.grants) == len(runner.prompts)  # one fresh MODEL_CALL grant per call (D100)


def test_runner_raptor_summarizer_splits_an_oversized_member_never_overflowing() -> None:
    # Defense-in-depth (D100): even a SINGLE member longer than the whole budget is split on passage
    # boundaries before summarizing, so no prompt can ever exceed the runner bound. Members are never
    # oversized in a real build (a book's passages are ~1.7k chars), but a corrupted cluster must not
    # resurrect the overflow that abstention hid.
    ceiling = 400
    runner = _StubRunner()
    summarizer = RunnerRaptorSummarizer(runner, _bare_grant, max_prompt_chars=ceiling)
    giant = "x" * 5000  # one member far over the per-call budget, no separators to break on

    result = summarizer.summarize([giant], label=_label())

    assert result is not None
    assert len(runner.prompts) > 1  # chunked into many bounded calls, never sent whole
    assert all(len(p) <= ceiling for p in runner.prompts)  # never over the runner bound (D136)


def test_runner_raptor_summarizer_small_cluster_is_still_exactly_one_call() -> None:
    # The base case is unchanged: a cluster that already fits one prompt costs exactly ONE call
    # (no needless map-reduce), byte-for-byte the pre-fix behaviour for the ~28 books small enough.
    runner = _StubRunner(completions=["one-shot synopsis"])
    summarizer = RunnerRaptorSummarizer(runner, _bare_grant)  # default ~48k budget

    result = summarizer.summarize(["a short passage", "another short passage"], label=_label())

    assert result == "one-shot synopsis"
    assert len(runner.prompts) == 1  # one call, no hierarchy needed


def test_runner_raptor_summarizer_rejects_a_ceiling_too_small_for_the_template() -> None:
    # A ceiling that cannot even fit the template overhead is a wiring error, refused at construction
    # (fail-closed) rather than silently producing prompts that can never be summarized.
    with pytest.raises(ValueError, match="template"):
        RunnerRaptorSummarizer(_StubRunner(), _bare_grant, max_prompt_chars=1)


# =========================== build_raptor_tree - the corpus pass ====================== #


def test_build_over_one_book_creates_one_book_and_one_domain_synopsis(tmp_path: Path) -> None:
    truth = MarkdownTruthStore()
    manifest, path = _manifest(tmp_path)
    vector, raptor, embedder = InMemoryVectorIndex(), RaptorStore(), StubEmbedder()
    fake = _FakeSummarizer()
    doc = _seed_book(truth, manifest, doc="library/book1", text="zones prix trading strategy")
    manifest.save()

    report = build_raptor_tree(
        path, truth=truth, embedder=embedder, vector=vector, raptor=raptor, summarizer=fake
    )

    assert report == RaptorBuildReport(
        books_summarized=1, domains_summarized=1, reused=0, swept=0, abstained=0
    )
    book_id = raptor_doc_id("book", (doc,))
    # M1 (audit): a domain node's id folds its full (sensitivity, bubble, domain) grouping key -
    # this book is SENSIBLE / KNOWLEDGE_BUBBLE / finance (the `_seed_book` defaults used above).
    domain_id = raptor_doc_id(
        "domain",
        (book_id,),
        discriminator=f"{Sensitivity.SENSIBLE.token}|{KNOWLEDGE_BUBBLE}|finance",
    )
    assert raptor.contains(book_id) and raptor.contains(domain_id)
    assert vector.contains(book_id) and vector.contains(domain_id)
    assert raptor.get(book_id).member_ids == (doc,)
    assert raptor.get(domain_id).member_ids == (book_id,)
    # both fake-summarizer calls happened (book pass, then domain pass over the book's own text)
    assert len(fake.calls) == 2


def test_build_is_idempotent_a_second_run_reuses_everything(tmp_path: Path) -> None:
    truth = MarkdownTruthStore()
    manifest, path = _manifest(tmp_path)
    vector, raptor, embedder = InMemoryVectorIndex(), RaptorStore(), StubEmbedder()
    fake = _FakeSummarizer()
    _seed_book(truth, manifest, doc="library/book1", text="zones prix trading strategy")
    manifest.save()

    first = build_raptor_tree(
        path, truth=truth, embedder=embedder, vector=vector, raptor=raptor, summarizer=fake
    )
    second = build_raptor_tree(
        path, truth=truth, embedder=embedder, vector=vector, raptor=raptor, summarizer=fake
    )

    assert first.books_summarized == 1 and first.domains_summarized == 1
    assert second.books_summarized == 0 and second.domains_summarized == 0  # 0 NEW nodes
    assert second.reused == 2  # the book synopsis AND the domain synopsis were both reused
    assert second.swept == 0
    assert len(fake.calls) == 2  # the second run never called the summarizer again


def test_build_m2_self_heals_a_vector_wiped_independently_without_a_new_summarizer_call(
    tmp_path: Path,
) -> None:
    # m2 (audit): an independent vector-index rebuild (e.g. Qdrant repopulated from the manifest's
    # leaves) can wipe a summary's vector entry while the RaptorStore itself is untouched - a second
    # build must self-heal the vector (re-embed + re-upsert) WITHOUT re-asking the summarizer, since
    # the node's TEXT is already valid and unchanged (reuse, D56 / D44).
    truth = MarkdownTruthStore()
    manifest, path = _manifest(tmp_path)
    vector, raptor, embedder = InMemoryVectorIndex(), RaptorStore(), StubEmbedder()
    fake = _FakeSummarizer()
    doc = _seed_book(truth, manifest, doc="library/book1", text="zones prix trading strategy")
    manifest.save()

    build_raptor_tree(
        path, truth=truth, embedder=embedder, vector=vector, raptor=raptor, summarizer=fake
    )
    book_id = raptor_doc_id("book", (doc,))
    domain_id = raptor_doc_id(
        "domain",
        (book_id,),
        discriminator=f"{Sensitivity.SENSIBLE.token}|{KNOWLEDGE_BUBBLE}|finance",
    )
    assert vector.contains(book_id) and vector.contains(domain_id)
    assert len(fake.calls) == 2  # book pass + domain pass

    # simulate an INDEPENDENT vector wipe (only the book summary's entry) - the RaptorStore keeps
    # the node untouched, so its TEXT survives for reuse.
    vector.invalidate(book_id)
    assert not vector.contains(book_id)
    assert raptor.contains(book_id)  # the RaptorStore itself was never touched

    report = build_raptor_tree(
        path, truth=truth, embedder=embedder, vector=vector, raptor=raptor, summarizer=fake
    )

    assert vector.contains(book_id) is True  # self-healed: re-embedded + re-upserted
    assert report == RaptorBuildReport(
        books_summarized=0, domains_summarized=0, reused=2, swept=0, abstained=0
    )
    assert len(fake.calls) == 2  # unchanged - healed via reuse, never a new summarizer call


def test_build_cloisonnement_never_merges_across_a_sensitivity_partition(tmp_path: Path) -> None:
    # two books share the SAME domain but DIFFERENT sensitivities - the domain rollup must NEVER
    # merge them into one cluster (invariant 1 / 3): two separate, single-member domain synopses.
    truth = MarkdownTruthStore()
    manifest, path = _manifest(tmp_path)
    vector, raptor, embedder = InMemoryVectorIndex(), RaptorStore(), StubEmbedder()
    fake = _FakeSummarizer()
    doc_public = _seed_book(
        truth,
        manifest,
        doc="library/pub",
        text="public markets note",
        sensitivity=Sensitivity.PUBLIC,
    )
    doc_perso = _seed_book(
        truth,
        manifest,
        doc="library/perso",
        text="perso trading journal",
        sensitivity=Sensitivity.PERSO,
    )
    manifest.save()

    report = build_raptor_tree(
        path, truth=truth, embedder=embedder, vector=vector, raptor=raptor, summarizer=fake
    )

    assert report.domains_summarized == 2  # NEVER merged into a single 2-member cluster
    book_public_id = raptor_doc_id("book", (doc_public,))
    book_perso_id = raptor_doc_id("book", (doc_perso,))
    # M1 (audit): each domain id folds THIS group's own (sensitivity, bubble, domain) - same
    # bubble/domain here, but the sensitivity differs, so the two ids must never collide.
    domain_public_id = raptor_doc_id(
        "domain",
        (book_public_id,),
        discriminator=f"{Sensitivity.PUBLIC.token}|{KNOWLEDGE_BUBBLE}|finance",
    )
    domain_perso_id = raptor_doc_id(
        "domain",
        (book_perso_id,),
        discriminator=f"{Sensitivity.PERSO.token}|{KNOWLEDGE_BUBBLE}|finance",
    )
    assert raptor.contains(domain_public_id) and raptor.contains(domain_perso_id)
    assert raptor.get(domain_public_id).member_ids == (book_public_id,)  # single member each
    assert raptor.get(domain_perso_id).member_ids == (book_perso_id,)
    assert raptor.get(domain_public_id).label.sensitivity is Sensitivity.PUBLIC
    assert raptor.get(domain_perso_id).label.sensitivity is Sensitivity.PERSO


def test_build_cloisonnement_never_merges_across_a_bubble(tmp_path: Path) -> None:
    truth = MarkdownTruthStore()
    manifest, path = _manifest(tmp_path)
    vector, raptor, embedder = InMemoryVectorIndex(), RaptorStore(), StubEmbedder()
    fake = _FakeSummarizer()
    doc_a = _seed_book(truth, manifest, doc="library/a", text="alpha", bubble=Bubble("knowledge"))
    doc_b = _seed_book(
        truth, manifest, doc="library/b", text="beta", bubble=Bubble("another-bubble")
    )
    manifest.save()

    report = build_raptor_tree(
        path, truth=truth, embedder=embedder, vector=vector, raptor=raptor, summarizer=fake
    )

    assert report.domains_summarized == 2  # a shared domain but different bubbles never merge
    book_a_id, book_b_id = raptor_doc_id("book", (doc_a,)), raptor_doc_id("book", (doc_b,))
    # M1 (audit): same sensitivity/domain, but the bubble differs - the discriminator carries it.
    domain_a_id = raptor_doc_id(
        "domain",
        (book_a_id,),
        discriminator=f"{Sensitivity.SENSIBLE.token}|{Bubble('knowledge')}|finance",
    )
    domain_b_id = raptor_doc_id(
        "domain",
        (book_b_id,),
        discriminator=f"{Sensitivity.SENSIBLE.token}|{Bubble('another-bubble')}|finance",
    )
    assert raptor.get(domain_a_id).label.bubble == Bubble("knowledge")
    assert raptor.get(domain_b_id).label.bubble == Bubble("another-bubble")


def test_build_m1_a_book_in_two_domains_produces_two_distinct_domain_synopses(
    tmp_path: Path,
) -> None:
    # M1 (audit): a book living in TWO domains is a member of TWO domain clusters that share the
    # exact SAME single member (this one book's own synopsis). Pre-fix, `raptor_doc_id("domain",
    # (book_id,))` carried no discriminator, so both clusters collided onto ONE id: one synopsis
    # silently overwrote the other - a whole domain's summary was lost, never surfaced, never even
    # swept as stale (the sweep only sees the id that WON the collision).
    truth = MarkdownTruthStore()
    manifest, path = _manifest(tmp_path)
    vector, raptor, embedder = InMemoryVectorIndex(), RaptorStore(), StubEmbedder()
    fake = _FakeSummarizer()
    doc = DocId("library/dual-domain-book")
    text = "a book that lives in both finance and macro at once"
    truth.write(
        doc,
        Envelope(
            text,
            GovernanceLabel(
                sensitivity=Sensitivity.SENSIBLE,
                bubble=KNOWLEDGE_BUBBLE,
                domains=frozenset({_FINANCE, _MACRO}),
            ),
        ),
    )
    manifest.records[str(doc)] = BookRecord(
        rel="finance/dual-domain-book.md",
        domain="finance",
        doc=str(doc),
        status=BookStatus.DONE,
        chars=len(text),
        at="2026-01-01T00:00:00+00:00",
    )
    manifest.save()

    report = build_raptor_tree(
        path, truth=truth, embedder=embedder, vector=vector, raptor=raptor, summarizer=fake
    )

    assert report.domains_summarized == 2  # never collapsed onto one node (M1)
    book_id = raptor_doc_id("book", (doc,))
    finance_id = raptor_doc_id(
        "domain",
        (book_id,),
        discriminator=f"{Sensitivity.SENSIBLE.token}|{KNOWLEDGE_BUBBLE}|finance",
    )
    macro_id = raptor_doc_id(
        "domain", (book_id,), discriminator=f"{Sensitivity.SENSIBLE.token}|{KNOWLEDGE_BUBBLE}|macro"
    )
    assert finance_id != macro_id  # the collision M1 closes
    assert raptor.contains(finance_id) and raptor.contains(macro_id)
    assert vector.contains(finance_id) and vector.contains(macro_id)
    assert raptor.get(finance_id).label.domains == frozenset({_FINANCE})
    assert raptor.get(macro_id).label.domains == frozenset({_MACRO})
    assert raptor.get(finance_id).member_ids == (book_id,)
    assert raptor.get(macro_id).member_ids == (
        book_id,
    )  # SAME member set, still two distinct nodes


def test_build_label_inheritance_book_reads_the_books_own_real_sensitivity(tmp_path: Path) -> None:
    # the book node's label is the book's OWN truth-read label - never a hard-coded SENSIBLE guess.
    truth = MarkdownTruthStore()
    manifest, path = _manifest(tmp_path)
    vector, raptor, embedder = InMemoryVectorIndex(), RaptorStore(), StubEmbedder()
    doc = _seed_book(
        truth, manifest, doc="library/pub", text="a public note", sensitivity=Sensitivity.PUBLIC
    )
    manifest.save()

    build_raptor_tree(
        path,
        truth=truth,
        embedder=embedder,
        vector=vector,
        raptor=raptor,
        summarizer=_FakeSummarizer(),
    )

    book_id = raptor_doc_id("book", (doc,))
    node = raptor.get(book_id)
    assert node.label.sensitivity is Sensitivity.PUBLIC  # NOT hard-coded SENSIBLE
    assert node.label.domains == frozenset({_FINANCE})


def test_build_label_inheritance_domain_is_max_over_its_members_never_lower(tmp_path: Path) -> None:
    # two books at the SAME (sensitivity, bubble, domain) key are grouped into ONE domain synopsis;
    # its label sensitivity must equal that shared value - never silently below either member's.
    truth = MarkdownTruthStore()
    manifest, path = _manifest(tmp_path)
    vector, raptor, embedder = InMemoryVectorIndex(), RaptorStore(), StubEmbedder()
    _seed_book(truth, manifest, doc="library/b1", text="book one", sensitivity=Sensitivity.SENSIBLE)
    _seed_book(truth, manifest, doc="library/b2", text="book two", sensitivity=Sensitivity.SENSIBLE)
    manifest.save()

    report = build_raptor_tree(
        path,
        truth=truth,
        embedder=embedder,
        vector=vector,
        raptor=raptor,
        summarizer=_FakeSummarizer(),
    )

    assert report.domains_summarized == 1  # merged: identical (sensitivity, bubble, domain)
    (domain_node,) = [raptor.get(d) for d in raptor.iter_ids() if raptor.get(d).level == "domain"]
    assert len(domain_node.member_ids) == 2
    assert domain_node.label.sensitivity is Sensitivity.SENSIBLE  # never lower than either member


def test_build_staleness_sweep_invalidates_the_old_ids_after_a_member_changes(
    tmp_path: Path,
) -> None:
    truth = MarkdownTruthStore()
    manifest, path = _manifest(tmp_path)
    vector, raptor, embedder = InMemoryVectorIndex(), RaptorStore(), StubEmbedder()
    fake = _FakeSummarizer()
    old_doc = _seed_book(truth, manifest, doc="library/book1", text="version one text")
    manifest.save()
    build_raptor_tree(
        path, truth=truth, embedder=embedder, vector=vector, raptor=raptor, summarizer=fake
    )
    old_book_id = raptor_doc_id("book", (old_doc,))
    old_domain_id = raptor_doc_id(
        "domain",
        (old_book_id,),
        discriminator=f"{Sensitivity.SENSIBLE.token}|{KNOWLEDGE_BUBBLE}|finance",
    )
    assert raptor.contains(old_book_id) and vector.contains(old_book_id)

    # simulate an EDIT (D-CI): the book's content changes => a NEW content-hash doc id, and
    # ingest_library's own edit-detection would have replaced the manifest row + purged the old
    # vectors - mirrored here by writing the new doc and swapping the manifest key.
    new_doc = _seed_book(truth, manifest, doc="library/book1-v2", text="version TWO, edited text")
    del manifest.records["library/book1"]
    manifest.save()

    report = build_raptor_tree(
        path, truth=truth, embedder=embedder, vector=vector, raptor=raptor, summarizer=fake
    )

    new_book_id = raptor_doc_id("book", (new_doc,))
    new_domain_id = raptor_doc_id(
        "domain",
        (new_book_id,),
        discriminator=f"{Sensitivity.SENSIBLE.token}|{KNOWLEDGE_BUBBLE}|finance",
    )
    assert (
        report.books_summarized == 1 and report.domains_summarized == 1
    )  # the new cluster, freshly built
    assert report.swept == 2  # the OLD book id AND the OLD domain id that rolled it up
    assert not raptor.contains(old_book_id) and not vector.contains(old_book_id)
    assert not raptor.contains(old_domain_id) and not vector.contains(old_domain_id)
    assert raptor.contains(new_book_id) and vector.contains(new_book_id)
    assert raptor.contains(new_domain_id) and vector.contains(new_domain_id)


def test_build_abstention_with_null_summarizer_creates_zero_nodes(tmp_path: Path) -> None:
    truth = MarkdownTruthStore()
    manifest, path = _manifest(tmp_path)
    vector, raptor, embedder = InMemoryVectorIndex(), RaptorStore(), StubEmbedder()
    _seed_book(truth, manifest, doc="library/book1", text="anything at all")
    manifest.save()

    report = build_raptor_tree(
        path,
        truth=truth,
        embedder=embedder,
        vector=vector,
        raptor=raptor,
        summarizer=NullRaptorSummarizer(),
    )

    assert report.books_summarized == 0 and report.domains_summarized == 0
    assert report.abstained == 1  # the one book; the (empty) domain group is never even attempted
    assert raptor.iter_ids() == ()
    assert vector.contains(DocId("library/book1")) is False  # nothing was ever indexed under any id


def test_build_dry_run_previews_without_mutating_anything(tmp_path: Path) -> None:
    truth = MarkdownTruthStore()
    manifest, path = _manifest(tmp_path)
    vector, raptor, embedder = InMemoryVectorIndex(), RaptorStore(), StubEmbedder()
    fake = _FakeSummarizer()
    _seed_book(truth, manifest, doc="library/book1", text="zones prix trading strategy")
    manifest.save()

    preview = build_raptor_tree(
        path,
        truth=truth,
        embedder=embedder,
        vector=vector,
        raptor=raptor,
        summarizer=fake,
        dry_run=True,
    )

    assert preview.books_summarized == 1 and preview.domains_summarized == 1  # an honest PREVIEW
    assert raptor.iter_ids() == ()  # nothing written
    assert fake.calls == []  # the summarizer was never actually called

    real = build_raptor_tree(
        path, truth=truth, embedder=embedder, vector=vector, raptor=raptor, summarizer=fake
    )
    assert (
        real.books_summarized == 1 and real.domains_summarized == 1
    )  # the dry run left no partial state
    assert len(raptor.iter_ids()) == 2


def test_build_dry_run_previews_a_sweep_without_invalidating_anything(tmp_path: Path) -> None:
    truth = MarkdownTruthStore()
    manifest, path = _manifest(tmp_path)
    vector, raptor, embedder = InMemoryVectorIndex(), RaptorStore(), StubEmbedder()
    fake = _FakeSummarizer()
    old_doc = _seed_book(truth, manifest, doc="library/book1", text="version one")
    manifest.save()
    build_raptor_tree(
        path, truth=truth, embedder=embedder, vector=vector, raptor=raptor, summarizer=fake
    )
    old_book_id = raptor_doc_id("book", (old_doc,))

    _seed_book(truth, manifest, doc="library/book1-v2", text="version two, changed")
    del manifest.records["library/book1"]
    manifest.save()

    preview = build_raptor_tree(
        path,
        truth=truth,
        embedder=embedder,
        vector=vector,
        raptor=raptor,
        summarizer=fake,
        dry_run=True,
    )
    assert preview.swept == 2  # would sweep the old book id + the domain id that rolled it up
    assert raptor.contains(old_book_id) is True  # but NOTHING was actually invalidated
    assert vector.contains(old_book_id) is True


def test_build_nets_a_book_whose_truth_vanished_despite_a_done_manifest_row(tmp_path: Path) -> None:
    truth = MarkdownTruthStore()
    manifest, path = _manifest(tmp_path)
    vector, raptor, embedder = InMemoryVectorIndex(), RaptorStore(), StubEmbedder()
    # a DONE row with NO matching truth entry (never written) - an inconsistency the corpus pass
    # must survive (mirrors ingest_book's own per-book isolation, D140), never crash.
    manifest.records["library/ghost"] = BookRecord(
        rel="finance/ghost.md",
        domain="finance",
        doc="library/ghost",
        status=BookStatus.DONE,
        chars=100,
        at="2026-01-01T00:00:00+00:00",
    )
    manifest.save()

    report = build_raptor_tree(
        path,
        truth=truth,
        embedder=embedder,
        vector=vector,
        raptor=raptor,
        summarizer=_FakeSummarizer(),
    )

    assert report == RaptorBuildReport(
        books_summarized=0, domains_summarized=0, reused=0, swept=0, abstained=0
    )


def test_build_nets_a_book_whose_text_is_blank(tmp_path: Path) -> None:
    truth = MarkdownTruthStore()
    manifest, path = _manifest(tmp_path)
    vector, raptor, embedder = InMemoryVectorIndex(), RaptorStore(), StubEmbedder()
    _seed_book(truth, manifest, doc="library/blank", text="   \n\n  ")  # whitespace only
    manifest.save()

    report = build_raptor_tree(
        path,
        truth=truth,
        embedder=embedder,
        vector=vector,
        raptor=raptor,
        summarizer=_FakeSummarizer(),
    )

    assert (
        report.books_summarized == 0 and report.abstained == 0
    )  # honest emptiness (F3), not an abstention


def test_build_nets_a_raising_summarizer_as_an_abstention_for_that_cluster_only(
    tmp_path: Path,
) -> None:
    truth = MarkdownTruthStore()
    manifest, path = _manifest(tmp_path)
    vector, raptor, embedder = InMemoryVectorIndex(), RaptorStore(), StubEmbedder()
    good_doc = _seed_book(truth, manifest, doc="library/good", text="a fine book", domain="macro")
    bad_doc = _seed_book(
        truth, manifest, doc="library/bad", text="poison pill text", domain="macro"
    )
    manifest.save()
    fake = _FakeSummarizer(raise_for=frozenset({"poison pill text"}))

    report = build_raptor_tree(
        path, truth=truth, embedder=embedder, vector=vector, raptor=raptor, summarizer=fake
    )

    good_id = raptor_doc_id("book", (good_doc,))
    bad_id = raptor_doc_id("book", (bad_doc,))
    assert (
        raptor.contains(good_id) is True
    )  # the OTHER book's cluster still built (isolation, D140)
    assert raptor.contains(bad_id) is False
    assert report.books_summarized == 1
    assert report.domains_summarized == 1  # the "macro" domain rolls up ONLY the surviving book
    assert report.abstained == 1  # exactly the raising book - never propagated to abort the walk


# =========================== retrieval read-path + orphan-safety ====================== #


def _test_policy(declared: dict[Bubble, frozenset[Domain]]) -> Policy:
    """A minimal, deny-by-default test policy carrying only the bounds ``bootstrap()`` needs
    internally (mirrors ``tests/platform/test_api.py``'s own ``_permissive_policy``)."""
    return Policy(
        profile="test",
        canal_a_auto=frozenset(),
        egress_allowlist=frozenset(),
        contracts=(),
        declared_domains=declared,
        bounds={
            "queue_capacity": 8,
            "concurrency": 1,
            "intake_capacity": 8,
            "intake_source_bytes": 268435456,
        },
        quotas={},
    )


def test_recall_surfaces_a_raptor_summary_as_working_material_never_a_fact() -> None:
    vector, embedder, raptor = InMemoryVectorIndex(), StubEmbedder(), RaptorStore()
    policy = _test_policy({KNOWLEDGE_BUBBLE: frozenset({_FINANCE})})
    rt = bootstrap(policy=policy, vector=vector, embedder=embedder, raptor=raptor)
    # M2 (audit): a summary surfaces ONLY while its member LEAF book is still valid truth - seed one
    # so `truth.is_valid` holds and the summary is not dropped by `_summary_is_current`.
    rt.truth.write(DocId("library/deadbeef"), Envelope("the underlying book's own text", _label()))
    api = CoreApi(rt)

    node = RaptorNode(
        doc=raptor_doc_id("book", (DocId("library/deadbeef"),)),
        level="book",
        member_ids=(DocId("library/deadbeef"),),
        text="synopsis about zones prix trading strategy",
        label=_label(),
    )
    raptor.put(node)
    (embedding,) = embedder.embed([node.text])
    vector.upsert(node.doc, [embedding], node.label)

    view = api.recall(
        "zones prix trading",
        within=Sensitivity.SENSIBLE,
        subject=KNOWLEDGE_BUBBLE,
        domains=frozenset({_FINANCE}),
    )

    assert (
        view.facts == ()
    )  # never a citable source - no document exists for user to endorse (D137)
    assert len(view.working_material) == 1
    assert view.working_material[0].payload == node.text  # resolved from the RaptorStore verbatim
    assert view.working_material[0].label == node.label
    assert not view.admitted_low_recall


def test_recall_leaf_document_path_is_unchanged_with_raptor_wired() -> None:
    # a RaptorStore is wired AND holds an unrelated summary - the ordinary document path must stay
    # byte-identical (still resolved from truth via pack_passage, D136).
    vector, embedder, raptor = InMemoryVectorIndex(), StubEmbedder(), RaptorStore()
    policy = _test_policy({KNOWLEDGE_BUBBLE: frozenset({_FINANCE})})
    rt = bootstrap(policy=policy, vector=vector, embedder=embedder, raptor=raptor)
    api = CoreApi(rt)

    unrelated = RaptorNode(
        doc=raptor_doc_id("book", (DocId("library/other"),)),
        level="book",
        member_ids=(DocId("library/other"),),
        text="a completely unrelated synopsis about zebras",
        label=_label(),
    )
    raptor.put(unrelated)
    (embedding,) = embedder.embed([unrelated.text])
    vector.upsert(unrelated.doc, [embedding], unrelated.label)

    api.capture(
        "quant trading desks watch zones prix signals for entries",
        bubble=KNOWLEDGE_BUBBLE,
        domain_signal=Sensitivity.SENSIBLE,
        domains=frozenset({_FINANCE}),
    )

    view = api.recall(
        "zones prix signals",
        within=Sensitivity.SENSIBLE,
        subject=KNOWLEDGE_BUBBLE,
        domains=frozenset({_FINANCE}),
    )

    assert len(view.working_material) == 1  # the captured doc - the unrelated summary never matched
    assert "zones prix signals" in view.working_material[0].payload
    assert "zebras" not in view.working_material[0].payload


def test_recall_m2_drops_a_book_summary_whose_leaf_book_is_archived() -> None:
    # M2 (audit): a summary surfaces only while its member LEAF book is still valid truth. Confirm
    # it surfaces first (sanity), then archive the leaf at the truth level (D60, non-destructive)
    # and confirm the summary is dropped - the exact repro the auditor found broken pre-fix (a
    # stale synopsis of an archived book kept surfacing as working material forever).
    vector, embedder, raptor = InMemoryVectorIndex(), StubEmbedder(), RaptorStore()
    policy = _test_policy({KNOWLEDGE_BUBBLE: frozenset({_FINANCE})})
    rt = bootstrap(policy=policy, vector=vector, embedder=embedder, raptor=raptor)
    api = CoreApi(rt)

    book_doc = DocId("library/archived-leaf")
    rt.truth.write(book_doc, Envelope("the leaf book's own text", _label()))
    node = RaptorNode(
        doc=raptor_doc_id("book", (book_doc,)),
        level="book",
        member_ids=(book_doc,),
        text="synopsis about zones prix trading strategy",
        label=_label(),
    )
    raptor.put(node)
    (embedding,) = embedder.embed([node.text])
    vector.upsert(node.doc, [embedding], node.label)

    before = api.recall(
        "zones prix trading",
        within=Sensitivity.SENSIBLE,
        subject=KNOWLEDGE_BUBBLE,
        domains=frozenset({_FINANCE}),
    )
    assert len(before.working_material) == 1  # valid leaf => surfaces

    rt.truth.invalidate(book_doc, reason="test archival")  # D60 - non-destructive archival

    after = api.recall(
        "zones prix trading",
        within=Sensitivity.SENSIBLE,
        subject=KNOWLEDGE_BUBBLE,
        domains=frozenset({_FINANCE}),
    )
    assert after.working_material == ()  # M2 - the archived leaf's summary is dropped, fail-closed
    assert after.facts == ()


def test_recall_m2_drops_a_domain_summary_whose_recursive_leaf_book_is_archived() -> None:
    # M2 recursion: a DOMAIN synopsis rolls up a BOOK synopsis, which in turn rolls up the leaf book
    # - archiving the leaf must propagate through BOTH levels of the rollup, dropping the domain
    # synopsis too, never just the book one.
    vector, embedder, raptor = InMemoryVectorIndex(), StubEmbedder(), RaptorStore()
    policy = _test_policy({KNOWLEDGE_BUBBLE: frozenset({_FINANCE})})
    rt = bootstrap(policy=policy, vector=vector, embedder=embedder, raptor=raptor)
    api = CoreApi(rt)

    leaf_doc = DocId("library/archived-leaf-under-domain")
    rt.truth.write(leaf_doc, Envelope("the leaf book's own text", _label()))
    book_node = RaptorNode(
        doc=raptor_doc_id("book", (leaf_doc,)),
        level="book",
        member_ids=(leaf_doc,),
        text="book synopsis of zones prix trading strategy",
        label=_label(),
    )
    raptor.put(book_node)  # NOT indexed in vector - only the domain rollup is searched here
    domain_node = RaptorNode(
        doc=raptor_doc_id(
            "domain",
            (book_node.doc,),
            discriminator=f"{Sensitivity.SENSIBLE.token}|{KNOWLEDGE_BUBBLE}|{_FINANCE}",
        ),
        level="domain",
        member_ids=(book_node.doc,),
        text="domain synopsis rolling up zones prix trading strategy",
        label=_label(),
    )
    raptor.put(domain_node)
    (embedding,) = embedder.embed([domain_node.text])
    vector.upsert(domain_node.doc, [embedding], domain_node.label)

    before = api.recall(
        "zones prix trading",
        within=Sensitivity.SENSIBLE,
        subject=KNOWLEDGE_BUBBLE,
        domains=frozenset({_FINANCE}),
    )
    assert len(before.working_material) == 1  # valid leaf => the domain rollup surfaces

    rt.truth.invalidate(leaf_doc, reason="test archival")

    after = api.recall(
        "zones prix trading",
        within=Sensitivity.SENSIBLE,
        subject=KNOWLEDGE_BUBBLE,
        domains=frozenset({_FINANCE}),
    )
    assert after.working_material == ()  # recursion: the domain rollup's leaf is stale, dropped too


def test_recall_m1_re_gates_a_summary_whose_stored_label_bubble_diverges_from_the_index() -> None:
    # m1 (audit): _pack_summary re-gates the STORED node.label, never merely the vector hit's own -
    # a store/index label divergence (the vector upsert carries one bubble, the RaptorStore's OWN
    # node.label another) must drop fail-closed rather than leak past the vector-side same-bubble
    # filter in `recall`. This never happens by construction in a real build (both are written from
    # the SAME label); the read-path must not blindly trust the index regardless.
    vector, embedder, raptor = InMemoryVectorIndex(), StubEmbedder(), RaptorStore()
    policy = _test_policy({KNOWLEDGE_BUBBLE: frozenset({_FINANCE})})
    rt = bootstrap(policy=policy, vector=vector, embedder=embedder, raptor=raptor)
    api = CoreApi(rt)

    leaf_doc = DocId("library/divergent-leaf")
    rt.truth.write(leaf_doc, Envelope("leaf text", _label()))
    foreign_label = _label(bubble=Bubble("another-bubble"))
    node = RaptorNode(
        doc=raptor_doc_id("book", (leaf_doc,)),
        level="book",
        member_ids=(leaf_doc,),
        text="synopsis about zones prix trading strategy",
        label=foreign_label,  # the RaptorStore's OWN stored label - a bubble the subject does NOT own
    )
    raptor.put(node)
    (embedding,) = embedder.embed([node.text])
    # the VECTOR index is upserted under the SUBJECT's own bubble - a divergence from the
    # RaptorStore's stored label, simulating exactly what `_pack_summary`'s re-gate must catch.
    vector.upsert(node.doc, [embedding], _label(bubble=KNOWLEDGE_BUBBLE))

    view = api.recall(
        "zones prix trading",
        within=Sensitivity.SENSIBLE,
        subject=KNOWLEDGE_BUBBLE,
        domains=frozenset({_FINANCE}),
    )

    assert view.working_material == ()  # m1 - the STORED label's bubble never matches, dropped
    assert view.facts == ()


def test_recall_degrades_safely_when_no_raptorstore_is_wired() -> None:
    # a hand-built Runtime that never got a RaptorStore (D126) must never crash on a summary-shaped
    # hit - it degrades to skipping it (never a guess, never an exception).
    vector, embedder = InMemoryVectorIndex(), StubEmbedder()
    policy = _test_policy({KNOWLEDGE_BUBBLE: frozenset({_FINANCE})})
    rt = replace(bootstrap(policy=policy, vector=vector, embedder=embedder), raptor=None)
    api = CoreApi(rt)

    summary_doc = raptor_doc_id("book", (DocId("library/orphaned"),))
    label = _label()
    (embedding,) = embedder.embed(["zones prix trading synopsis with no backing store"])
    vector.upsert(summary_doc, [embedding], label)  # indexed, but NO RaptorStore holds its text

    view = api.recall(
        "zones prix trading",
        within=Sensitivity.SENSIBLE,
        subject=KNOWLEDGE_BUBBLE,
        domains=frozenset({_FINANCE}),
    )

    assert view.working_material == () and view.facts == ()  # silently dropped, never a crash
    assert view.admitted_low_recall is True  # nothing else to answer with


def test_detect_orphan_vectors_never_flags_a_summary_doc(tmp_path: Path) -> None:
    # a summary id is NEVER a manifest key, so detect_orphan_vectors - which iterates ONLY
    # manifest.records - structurally cannot see it, regardless of what the vector index holds.
    manifest, path = _manifest(tmp_path)
    raw_root = tmp_path / "raw"
    raw_root.mkdir()  # empty shelf: every manifest DONE book is a live candidate
    vector, embedder = InMemoryVectorIndex(), StubEmbedder()

    real_book = DocId("library/off-shelf-book")
    manifest.records[str(real_book)] = BookRecord(
        rel="finance/off-shelf-book.md",
        domain="finance",
        doc=str(real_book),
        status=BookStatus.DONE,
        chars=42,
        at="2026-01-01T00:00:00+00:00",
    )
    manifest.save()
    (real_embedding,) = embedder.embed(["off shelf content"])
    vector.upsert(real_book, [real_embedding], _label())

    summary_doc = raptor_doc_id("book", (real_book,))
    (summary_embedding,) = embedder.embed(["a synopsis of the off-shelf book"])
    vector.upsert(summary_doc, [summary_embedding], _label())

    report = detect_orphan_vectors(path, raw_root, vector=vector)

    orphan_docs = {row.doc for row in report.orphans}
    assert real_book in {DocId(d) for d in orphan_docs}  # the REAL book is a genuine orphan
    assert (
        str(summary_doc) not in orphan_docs
    )  # the summary is structurally invisible to this check
    assert report.checked == 1  # only the ONE manifest-keyed candidate was ever considered


# =========================== N1 (audit) - RAPTOR routes through Ch.4 routing ============ #


def test_raptor_grant_source_routes_through_ch4_reasoning_class() -> None:
    # N1 (audit): mirrors runtime.bootstrap's own `_raptor_grant_source` closure exactly - a
    # summarization call is a REASONING-class task (D7), routed through `_model_call_request` the
    # SAME way the other model seams are, rather than a bare, untargeted grant. Ch.4's own
    # request-shape contract (router absent / empty / mapped) is already exhaustively covered by
    # tests/orchestration/test_model_routing.py; this proves RAPTOR is actually WIRED to it.
    class _CapturingGuard:
        def __init__(self) -> None:
            self.requests: list[GuardRequest] = []

        def grant(self, request: GuardRequest) -> Grant:
            self.requests.append(request)
            return Grant(request=request, released_label=request.inputs[0])

    guard = _CapturingGuard()
    router = ModelRouter(
        Policy(
            profile="test",
            canal_a_auto=frozenset(),
            egress_allowlist=frozenset(),
            contracts=(),
            declared_domains={},
            bounds={},
            quotas={},
            model_routing={"reasoning": "big-model"},
        )
    )

    def _grant_source(label: GovernanceLabel) -> Grant:
        return guard.grant(
            _model_call_request(
                subject=Bubble("ingest"),
                inputs=(label,),
                router=router,
                routing_class=RoutingClass.REASONING,
                action="raptor-summarize",
            )
        )

    runner = _StubRunner(completions=["a faithful synopsis"])
    summarizer = RunnerRaptorSummarizer(runner, _grant_source)

    result = summarizer.summarize(["passage one"], label=_label())

    assert result == "a faithful synopsis"
    assert len(guard.requests) == 1
    request = guard.requests[0]
    assert request.target == "big-model"  # routed - never a bare, untargeted grant
    assert "reasoning" in request.descriptor
    assert "raptor-summarize" in request.descriptor


# ============================ audit NITs - hardening ================================= #


def test_raptor_doc_id_nit1_length_prefixed_framing_is_injective() -> None:
    # NIT-1 (audit): a separator (newline) inside the discriminator must NOT forge a collision with a
    # DIFFERENT (discriminator, member-set) that a naive "\n".join would concatenate identically.
    # Length-prefixed framing (like the Guard's _canon) makes the id a total, injective function.
    forged = raptor_doc_id("domain", (DocId("BBBB"),), discriminator="macro\nAAAA")
    genuine = raptor_doc_id("domain", (DocId("AAAA"), DocId("BBBB")), discriminator="macro")
    assert forged != genuine  # pre-fix both hashed "domain\nmacro\nAAAA\nBBBB" => collision


def test_recall_nit2_a_cyclic_summary_graph_is_dropped_not_a_recursion_error() -> None:
    # NIT-2 (audit): a CORRUPTED store whose two domain synopses cite EACH OTHER must be treated as
    # stale (fail-closed), never a RecursionError propagating out of recall (D100). The retrieved node
    # matches the query so _pack_summary -> _summary_is_current is actually reached (else the test
    # would pass for the wrong reason). Pre-fix (no cycle guard) this recursion never terminates.
    vector, embedder, raptor = InMemoryVectorIndex(), StubEmbedder(), RaptorStore()
    policy = _test_policy({KNOWLEDGE_BUBBLE: frozenset({_FINANCE})})
    rt = bootstrap(policy=policy, vector=vector, embedder=embedder, raptor=raptor)
    api = CoreApi(rt)
    a_id = raptor_doc_id("domain", (DocId("library/summary/book/a"),), discriminator="a")
    b_id = raptor_doc_id("domain", (DocId("library/summary/book/b"),), discriminator="b")
    # forge the cycle: a's member is b, b's member is a - both under the summary namespace
    raptor.put(
        RaptorNode(
            doc=a_id,
            level="domain",
            member_ids=(b_id,),
            text="zones prix trading strategy",
            label=_label(),
        )
    )
    raptor.put(RaptorNode(doc=b_id, level="domain", member_ids=(a_id,), text="b", label=_label()))
    (embedding,) = embedder.embed(["zones prix trading strategy"])
    vector.upsert(a_id, [embedding], _label())

    view = api.recall(
        "zones prix trading",
        within=Sensitivity.SENSIBLE,
        subject=KNOWLEDGE_BUBBLE,
        domains=frozenset({_FINANCE}),
    )

    assert view.working_material == ()  # the cyclic (corrupted) synopsis is dropped, never a crash
