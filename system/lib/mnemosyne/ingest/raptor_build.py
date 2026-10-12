"""RAPTOR tree build (Ch.5 / RAG niveau 2) — the corpus pass over the library shelf.

:func:`build_raptor_tree` grows / refreshes the 2-level summary tree
(:mod:`~mnemosyne.stores.raptor`) from the SAME manifest :func:`~mnemosyne.ingest.library.
detect_orphan_vectors` reads: for every ``DONE`` book, re-chunk its truth text
(mirrors :meth:`~mnemosyne.stores.journal.IntentJournal._apply_derived`) and summarize its passages
into a **book** synopsis; group the resulting book synopses by ``(sensitivity, bubble, domain)``
(cloisonnement, invariant 1/3) and summarize EACH group into a **domain** synopsis. Every new node
is embedded and upserted into the SAME vector index the leaves live in (collapsed-tree retrieval,
D68) — REUSING the runtime's own embedder/vector instances, never a second one.

**Identity carries the reuse (D56 / D44 / invariant 24).** A book's own doc id is already a content
hash of its FULL text (:func:`~mnemosyne.ingest.library._content_doc`), so
:func:`~mnemosyne.stores.raptor.raptor_doc_id` (a pure function of a node's member ids) changes
automatically the moment a book's content does. This build ALWAYS checks the store for an existing
id BEFORE calling the summarizer — REUSE is checked first, so an unchanged cluster never spends a
model call twice, and idempotence (build twice ⇒ 0 new nodes) falls out for free.

**Self-reconciling sweep (staleness, D74 / D100).** After (re)building, any node CURRENTLY in the
store/vector whose id is no longer among the ids the CURRENT manifest would produce is INVALIDATED
(:meth:`~mnemosyne.stores.raptor.RaptorStore.invalidate` +
:meth:`~mnemosyne.ports.vectorindex.VectorIndex.invalidate`) — a derivative purge, never touching a
book's own truth ``.md``. A changed book therefore leaves its OLD book-synopsis id (and every
domain-synopsis id that rolled it up) stale, and this same pass sweeps them.

**Unbreakable, per-cluster isolation (mirrors D140).** A raising summarizer, or a book whose truth
entry vanished despite a ``DONE`` manifest row, degrades to an ABSTENTION / skip for that ONE
cluster — never aborts the whole walk (the same net :func:`~mnemosyne.ingest.library.ingest_book`
throws around one book).

Code & docstrings English (D117).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..ports import (
    Bubble,
    DocId,
    Domain,
    Embedder,
    GovernanceLabel,
    Sensitivity,
    TruthStore,
    VectorIndex,
)
from ..stores.raptor import RaptorNode, RaptorStore, raptor_doc_id
from .chunk import chunk_text
from .library import BookStatus, LibraryManifest
from .raptor_summarize import RaptorSummarizer


@dataclass(frozen=True, slots=True)
class RaptorBuildReport:
    """The outcome of one :func:`build_raptor_tree` pass (Ch.5) — counts only, never content (F3).

    Under ``dry_run=True`` (the CLI's ``--report`` view), ``books_summarized`` /
    ``domains_summarized`` / ``swept`` are an HONEST PREVIEW of what a real build would attempt —
    computed without ever calling the summarizer, embedding, or mutating the store/vector (so they
    cannot promise a live summarizer would not itself abstain on a genuinely new cluster)."""

    books_summarized: int = (
        0  # NEW book-synopsis nodes built (or, dry_run: would attempt) this pass
    )
    domains_summarized: int = 0  # NEW domain-synopsis nodes built (or, dry_run: would attempt)
    reused: int = 0  # nodes (book + domain) already valid in the store — no model call spent
    swept: int = 0  # stale nodes invalidated (or, dry_run: would be invalidated) this pass
    abstained: int = 0  # clusters the summarizer declined (None) — no node created

    def summary(self) -> str:
        return (
            f"RAPTOR build: {self.books_summarized} book synopsis(es), "
            f"{self.domains_summarized} domain synopsis(es) — {self.reused} reused, "
            f"{self.swept} stale node(s) swept, {self.abstained} abstained"
        )


def build_raptor_tree(
    manifest_path: Path | str,
    *,
    truth: TruthStore,
    embedder: Embedder,
    vector: VectorIndex,
    raptor: RaptorStore,
    summarizer: RaptorSummarizer,
    dry_run: bool = False,
) -> RaptorBuildReport:
    """Grow / refresh the RAPTOR tree over every ``DONE`` book in ``manifest_path`` (Ch.5).

    Reads the :class:`~mnemosyne.ingest.library.LibraryManifest` exactly as
    :func:`~mnemosyne.ingest.library.detect_orphan_vectors` does (``DONE`` rows only); for each,
    re-reads its TRUTH envelope (never the manifest's cached ``chars`` — the manifest carries no
    text) and :func:`~mnemosyne.ingest.chunk.chunk_text`\\ s it to get the passage texts. A book
    whose id is ALREADY a valid node in ``raptor`` is REUSED (no summarizer call); otherwise the
    summarizer is asked for a synopsis — ``None`` (abstain) skips the node entirely (brick-free
    posture, :class:`~mnemosyne.ingest.raptor_summarize.NullRaptorSummarizer` creates zero nodes).
    Every new node's label is the BOOK'S OWN truth-read label (its real sensitivity / bubble /
    domain — never a hard-coded guess): the library corpus happens to be captured at a uniform
    ``SENSIBLE`` floor today (:data:`~mnemosyne.ingest.library.KNOWLEDGE_BUBBLE`), but reading it
    per book is both simpler and correct if that ever changes.

    Book synopses are then grouped by ``(sensitivity, bubble, domain)`` — read straight off each
    kept node's own label, so the grouping key is a FACT of the data, never assumed — and each group
    is rolled up into ONE domain synopsis (label sensitivity = MAX over the group, raise-only;
    bubble = the group's shared bubble; domains = the single grouping domain — never the union of a
    multi-domain book's OTHER domains, which would leak an unrelated domain into this rollup).

    Every newly-built node (either level) is embedded once and ``upsert``-ed into ``vector`` under
    the SAME sensitivity partition its label implies (collapsed-tree retrieval, D68) — reusing the
    injected ``embedder`` / ``vector``, never a second instance.

    Finally, self-reconciles (D74 / D100): any id currently in ``raptor`` that is NOT among the ids
    the current manifest would produce (a book's content changed, or it left the manifest entirely)
    is invalidated from BOTH ``raptor`` and ``vector`` — a derivative purge; no book's own ``.md``
    truth is ever touched here.

    ``dry_run=True`` computes every count above WITHOUT calling the summarizer, embedding a vector,
    writing a node, or invalidating anything — a free, instant, read-only preview."""
    manifest = LibraryManifest.load(manifest_path)
    done_docs = tuple(
        DocId(key) for key, rec in manifest.records.items() if rec.status is BookStatus.DONE
    )
    # The book-level ids the CURRENT manifest implies — a PURE function of each book's own (already
    # content-hashed) doc id, computable up front, independent of whether its truth is even
    # readable right now (a transient read glitch must not sweep away a perfectly good EXISTING
    # summary built from that same, unchanged content — fail-safe toward NOT destroying, D100/D74).
    valid_book_ids = frozenset(raptor_doc_id("book", (doc,)) for doc in done_docs)

    books_summarized = reused = abstained = 0
    book_nodes: dict[DocId, RaptorNode] = {}
    for doc in sorted(done_docs, key=str):
        try:
            envelope = truth.read(doc)
        except KeyError:
            continue  # vanished from truth despite a DONE manifest row — netted, never crash (D140)
        passages = chunk_text(envelope.payload)
        if not passages:
            continue  # nothing to summarize — honest emptiness (F3)
        book_id = raptor_doc_id("book", (doc,))
        if raptor.contains(book_id):
            node = raptor.get(book_id)
            book_nodes[book_id] = node
            reused += 1
            # m2 (audit) — reuse the summary TEXT (no model call), but if the vector index was rebuilt
            # independently (leaves repopulated, summaries not) re-embed so the node stays RETRIEVABLE:
            # a rebuild thus self-heals summary vectors (D44), never silently drops them.
            if not dry_run and not vector.contains(book_id):
                (embedding,) = embedder.embed([node.text])
                vector.upsert(node.doc, [embedding], node.label)
            continue
        if dry_run:
            books_summarized += 1  # an honest PREVIEW count (the real call might still abstain)
            book_nodes[book_id] = RaptorNode(
                doc=book_id, level="book", member_ids=(doc,), text="", label=envelope.label
            )
            continue
        try:
            text = summarizer.summarize([p.text for p in passages], label=envelope.label)
        except Exception:  # noqa: BLE001 - a raising summarizer degrades to an abstention for THIS
            text = None  # cluster only, never aborts the walk (mirrors ingest_book, D140)
        if text is None:
            abstained += 1
            continue
        node = RaptorNode(
            doc=book_id, level="book", member_ids=(doc,), text=text, label=envelope.label
        )
        raptor.put(node)
        (embedding,) = embedder.embed([text])
        vector.upsert(node.doc, [embedding], node.label)
        book_nodes[book_id] = node
        books_summarized += 1

    # Group the book synopses that EXIST after the pass above (reused ∪ newly built) by their own
    # label's (sensitivity, bubble, domain) — cloisonnement (invariant 1/3): a cluster never crosses
    # a partition because the GROUPING KEY itself is that exact triple, read from real data.
    groups: dict[tuple[Sensitivity, Bubble, Domain], list[tuple[DocId, RaptorNode]]] = {}
    for book_id, node in book_nodes.items():
        for domain in node.label.domains:
            groups.setdefault((node.label.sensitivity, node.label.bubble, domain), []).append(
                (book_id, node)
            )

    domains_summarized = 0
    valid_domain_ids: set[DocId] = set()
    for key in sorted(groups, key=str):
        members = sorted(groups[key], key=lambda pair: str(pair[0]))
        sensitivity, bubble, domain = key
        member_ids = tuple(book_id for book_id, _ in members)
        # M1 (audit) — fold the FULL grouping key into the id: two domain clusters over the SAME
        # member set (one book living in two domains ⇒ its single synopsis is a member of BOTH) must
        # NOT collide onto one node, else one synopsis silently overwrites the other and the sweep
        # pins the stale one. The key's sensitivity == the members' shared (and MAX) sensitivity.
        domain_id = raptor_doc_id(
            "domain", member_ids, discriminator=f"{sensitivity.token}|{bubble}|{domain}"
        )
        valid_domain_ids.add(domain_id)
        if raptor.contains(domain_id):
            reused += 1
            if not dry_run and not vector.contains(
                domain_id
            ):  # m2 — self-heal the vector (see book pass)
                healed = raptor.get(domain_id)
                (embedding,) = embedder.embed([healed.text])
                vector.upsert(healed.doc, [embedding], healed.label)
            continue
        if dry_run:
            domains_summarized += 1
            continue
        label = GovernanceLabel(
            sensitivity=max(n.label.sensitivity for _, n in members),  # MAX, raise-only (inv 17/18)
            bubble=bubble,
            domains=frozenset({domain}),  # THIS cluster's domain only — never a member's other ones
        )
        try:
            text = summarizer.summarize([n.text for _, n in members], label=label)
        except Exception:  # noqa: BLE001 - netted, same per-cluster isolation as the book pass above
            text = None
        if text is None:
            abstained += 1
            continue
        node = RaptorNode(
            doc=domain_id, level="domain", member_ids=member_ids, text=text, label=label
        )
        raptor.put(node)
        (embedding,) = embedder.embed([text])
        vector.upsert(node.doc, [embedding], node.label)
        domains_summarized += 1

    # Self-reconciling sweep (staleness, D74 / D100): every id CURRENTLY in the store that is NOT
    # among the ids the current manifest implies is invalidated — derivative-only, never the truth.
    valid_ids = valid_book_ids | valid_domain_ids
    swept = 0
    for doc in raptor.iter_ids():
        if doc in valid_ids:
            continue
        if not dry_run:
            raptor.invalidate(doc)
            vector.invalidate(doc)
        swept += 1

    return RaptorBuildReport(
        books_summarized=books_summarized,
        domains_summarized=domains_summarized,
        reused=reused,
        swept=swept,
        abstained=abstained,
    )
