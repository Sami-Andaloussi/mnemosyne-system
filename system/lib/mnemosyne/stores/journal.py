"""IntentJournal (D105) — write-ahead three-store integrity with idempotent replay.

The light glue (D105 / D98 — NOT a distributed-transaction manager) that keeps the
three stores consistent without ever corrupting or losing. Implements
:class:`~mnemosyne.ports.store.IntentLog` and coordinates the truth (arbiter),
vector and graph stores through four standard moves:

1. **Write-ahead** — :meth:`~IntentJournal.plan` records the intent AND writes the
   truth (``.md``/git, the arbiter) BEFORE any derived store is touched (D105-①).
2. **Idempotent replay** — :meth:`~IntentJournal.replay` finishes (or rolls back)
   every uncommitted intent by REBUILDING the derived stores from the truth; replaying
   twice yields the same final state (invariant 24). Truth is read as the sole arbiter
   — a derived store is never treated as a source (D56).
3. **Per-document marker** — :meth:`~IntentJournal.mark_committed` records a
   reconstructible :class:`~mnemosyne.ports.store.ConsistencyMarker` (never a 4th
   truth, D105-②).
4. **Roll forward or back** — a crash between the truth write and the derived writes
   is finished by the next replay; a crash before the truth write leaves nothing
   durable, so the intent rolls back (fail-safe, D100).

Idempotency rests on idempotent derived writes: the vector upsert is keyed by
document, and an identical graph fact keeps its id (no duplicate). Fact EXTRACTION
from content (a model output that transits the Guard, D89) lands in LOT 5; here facts
are integrated as given. Code & docstrings English (D117).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from ..ingest.chunk import chunk_text
from ..ports import (
    ConsistencyMarker,
    DocId,
    Embedder,
    Envelope,
    Fact,
    GraphStore,
    Intent,
    IntentId,
    IntentKind,
    KeywordIndex,
    TruthStore,
    VectorIndex,
)
from .truth import content_hash


@dataclass(frozen=True, slots=True)
class _Work:
    """A planned integration awaiting its derived-store writes (the write-ahead tail)."""

    intent_id: IntentId
    doc: DocId
    facts: tuple[Fact, ...]


class IntentJournal:
    """Write-ahead journal coordinating truth + vector + keyword + graph, idempotent replay.

    Realizes :class:`~mnemosyne.ports.store.IntentLog`; :meth:`plan` / :meth:`integrate`
    add the higher-level, crash-safe integration over the stores (invariant 24). The dense
    (vector) and lexical (keyword) indexes are both derived, both rebuilt from the truth on
    replay (D56); the graph holds facts."""

    __slots__ = (
        "_truth",
        "_vector",
        "_keyword",
        "_graph",
        "_embedder",
        "_pending",
        "_markers",
        "_seq",
    )

    def __init__(
        self,
        *,
        truth: TruthStore,
        vector: VectorIndex,
        keyword: KeywordIndex,
        graph: GraphStore,
        embedder: Embedder,
    ) -> None:
        self._truth = truth
        self._vector = vector
        self._keyword = keyword
        self._graph = graph
        self._embedder = embedder
        self._pending: dict[IntentId, _Work] = {}
        self._markers: dict[DocId, ConsistencyMarker] = {}
        self._seq = 0

    # --- IntentLog protocol -------------------------------------------------
    def record(self, intent: Intent) -> IntentId:
        """Append an intent to the write-ahead log BEFORE the derived stores change
        (D105-①); a later :meth:`replay` finishes it or rolls it back. Returns its id.

        This is the raw protocol move (no content); :meth:`plan` builds on it by also
        writing the truth and attaching the derived work."""
        self._seq += 1
        intent_id = IntentId(f"i{self._seq}")
        self._pending[intent_id] = _Work(intent_id=intent_id, doc=intent.doc, facts=())
        return intent_id

    def replay(self) -> None:
        """Finish or roll back every uncommitted intent, IDEMPOTENTLY (invariant 24).

        Each pending intent is finished by rebuilding the derived stores FROM THE TRUTH
        (the arbiter, D56); if the truth has no such document (a crash before the truth
        write) the intent is rolled back. A second replay finds nothing pending — a
        no-op that leaves the state identical."""
        for work in list(self._pending.values()):
            try:
                envelope = self._truth.read(work.doc)  # rebuild from the arbiter (D56)
            except KeyError:
                del self._pending[work.intent_id]  # nothing durable ⇒ roll back
                continue
            self._apply_derived(work.doc, envelope, work.facts)
            # The vector witness is the ACTUAL index state (A-5): an empty doc yields no passage
            # and is deliberately NOT indexed, so the marker must not claim it was.
            self.mark_committed(work.doc, vector=self._vector.contains(work.doc), graph=True)
            del self._pending[work.intent_id]

    def mark_committed(self, doc: DocId, *, vector: bool, graph: bool) -> ConsistencyMarker:
        """Record that ``doc`` reached the derived stores (D105-②).

        The marker is a reconstructible cache — its hash recomputes from the truth and
        its flags re-verify by querying the indexes — never a fourth source of truth."""
        envelope = self._truth.read(doc)
        marker = ConsistencyMarker(
            doc=doc,
            content_hash=content_hash(envelope.payload),
            indexed_vector=vector,
            indexed_graph=graph,
        )
        self._markers[doc] = marker
        return marker

    # --- higher-level, crash-safe integration -------------------------------
    def plan(self, doc: DocId, content: Envelope[str], *, facts: tuple[Fact, ...] = ()) -> IntentId:
        """Write-ahead an integration (D105-①): record the intent and write the truth
        (the arbiter) FIRST, then stash the derived work for :meth:`replay`.

        Between this call and the next replay the document is durable in the truth but
        not yet in the derived stores — exactly the state a crash leaves, which replay
        then finishes."""
        intent_id = self.record(Intent(kind=IntentKind.INTEGRATE, doc=doc, label=content.label))
        self._truth.write(doc, content)  # arbiter written first (D56 / D105-①)
        self._markers.setdefault(
            doc,
            ConsistencyMarker(
                doc=doc,
                content_hash=content_hash(content.payload),
                indexed_vector=False,
                indexed_graph=False,
            ),
        )
        self._pending[intent_id] = _Work(intent_id=intent_id, doc=doc, facts=facts)
        return intent_id

    def integrate(
        self, doc: DocId, content: Envelope[str], *, facts: tuple[Fact, ...] = ()
    ) -> None:
        """Full crash-free integration: :meth:`plan` then :meth:`replay`."""
        self.plan(doc, content, facts=facts)
        self.replay()

    def marker(self, doc: DocId) -> ConsistencyMarker:
        """The per-document consistency marker (a reconstructible cache, D105-②)."""
        return self._markers[doc]

    def fingerprint(self) -> str:
        """A deterministic digest of the whole truth + derived state — the idempotency
        witness (invariant 24): an idempotent replay leaves it unchanged, a duplicated
        write or fact changes it."""
        parts: list[str] = []
        for doc in sorted(self._markers, key=str):
            marker = self._markers[doc]
            parts.append(
                f"m:{doc}:{marker.content_hash}:{marker.indexed_vector}:{marker.indexed_graph}"
            )
            parts.append(f"v:{doc}:{self._vector.contains(doc)}")
            parts.append(f"k:{doc}:{self._keyword.contains(doc)}")
        for fact in sorted(
            self._graph.query(),
            key=lambda f: (str(f.subject), f.predicate, str(f.obj), f.valid_from.isoformat()),
        ):
            stamp = fact.valid_from.isoformat()
            parts.append(f"g:{fact.subject}:{fact.predicate}:{fact.obj}:{stamp}")
        return hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()

    def _apply_derived(self, doc: DocId, envelope: Envelope[str], facts: tuple[Fact, ...]) -> None:
        """Rebuild the derived stores from the truth envelope — idempotently (inv. 24).

        The document is split into PASSAGES (D135). Every partition is purged FIRST
        (``invalidate``) so a re-index replaces wholesale AND a re-classification that moved the
        doc's sensitivity leaves NO stale hit in the old partition (invariant 1 / D135 audit A-1 —
        the classifier's semantic pass is a MODEL, so the same doc can re-route on re-ingest);
        then each passage is embedded and upserted, and an identical graph fact keeps its id, so
        applying the same work twice yields the same state."""
        self._vector.invalidate(doc)  # purge EVERY partition before re-indexing (A-1: no cross-
        self._keyword.invalidate(doc)  # partition stale hit when a re-classification moves the doc)
        passages = chunk_text(envelope.payload)
        embeddings = (
            self._embedder.embed([passage.text for passage in passages]) if passages else []
        )
        self._vector.upsert(doc, embeddings, envelope.label)
        self._keyword.index(doc, envelope.payload, envelope.label)  # lexical leg (D68 / ③-2b)
        for fact in facts:
            self._graph.add_fact(Envelope(fact, envelope.label))
