"""Mnémosyne stores - the three-store memory layer (D123 LOT 4b).

Moteur B (documentary truth, ``.md``/git) + Moteur A (living-memory graph) + the dense
vector leg, with the integrity, retrieval, reconciliation and locking that bind them
into one consistent, crash-safe, non-destructive memory. Each concrete class is a light
in-memory stand-in implementing its LOT 1 port; the default OSS bricks
(git  -  LadybugDB  -  Qdrant  -  bge-m3, ``system/config/oss_registry.md``) swap in behind
the same ports without touching a caller (D98 / D113).

**Barriers realized here (D109 étage (1)).** Invariant 9 (merge-on-update, no duplicate
fiche - :mod:`.truth`), 10 (A<->B reconciliation FLAG - :mod:`.reconcile`), 14 (low-recall
admission - :mod:`.retrieval`), 20 (graph engine encapsulated - :mod:`.graph`, plus the
import-scan barrier in the suite), 24 (idempotent three-store replay - :mod:`.journal`),
25 (document-grain locks - :mod:`.locks`).

**Durability scope (D84 / D76 / D110).** The bi-temporal, non-destructive decay of D84
is realized here in :class:`~mnemosyne.stores.graph.InMemoryGraphStore` (invalidate =
close valid-time; ``as_of`` travel). Snapshot / off-site backup (D76 / D110 / D118,
Kopia) is orthogonal to these barriers and plugs in behind the existing Backup port
(LOT 1); it carries no LOT 4b invariant, so it stays a named seam rather than a hollow
adapter (lean scaffolding). Code & docstrings English (D117); ``public`` / ``perso`` /
``sensible`` keep their French tokens (D33 / D66).
"""

from __future__ import annotations

from .golden import (
    RETRIEVAL_SEED,
    FloorScore,
    RetrievalCase,
    load_retrieval_golden,
    sweep_floor,
)
from .graph import InMemoryGraphStore
from .graph_ladybug import LadybugGraphStore, connect_ladybug
from .journal import IntentJournal
from .keyword import InMemoryKeywordIndex
from .keyword_tantivy import TantivyKeywordIndex, connect_tantivy
from .locks import DocumentLocks, LockContended, LockHeldAcrossWaitError
from .raptor import (
    RAPTOR_SUMMARY_PREFIX,
    RaptorBackend,
    RaptorNode,
    RaptorStore,
    is_raptor_summary,
    raptor_doc_id,
)
from .reconcile import Reconciler, ReconciliationFlag
from .retrieval import Retriever, RetrievalResult
from .reranked_retriever import (
    RerankedRetriever,
    RetrieverLike,
    passage_resolver,
    wrap_reranked,
)
from .embedder_bge import BgeM3Embedder, load_bge_m3
from .reranker_bge import BgeReranker, load_bge_reranker
from .truth import Fiche, MarkdownTruthStore, content_hash
from .vector import InMemoryVectorIndex, StubEmbedder
from .vector_qdrant import QDRANT_URL, QdrantVectorIndex, connect_qdrant

__all__ = [
    # Moteur B - documentary truth (D105 / D56)
    "MarkdownTruthStore",
    "Fiche",
    "content_hash",
    # Moteur A - living-memory graph (D103 / D84) - stub + the real LadybugDB adapter ((3)-3a, injected/lazy)
    "InMemoryGraphStore",
    "LadybugGraphStore",
    "connect_ladybug",
    # vector leg (D68) - stub + the real bge-m3 adapter ((3), injected/lazy)
    "InMemoryVectorIndex",
    "StubEmbedder",
    "BgeM3Embedder",
    "load_bge_m3",
    "QdrantVectorIndex",
    "QDRANT_URL",
    "connect_qdrant",
    # keyword leg (D68) - BM25 stub + the real tantivy adapter ((3)-2b, injected/lazy)
    "InMemoryKeywordIndex",
    "TantivyKeywordIndex",
    "connect_tantivy",
    # integrity (D105)
    "IntentJournal",
    # retrieval (D65 / invariant 14)
    "Retriever",
    "RetrievalResult",
    # rerank leg (D68 / D61 stage 6 / LOT 5) - cross-encoder decorator ABOVE the base port
    "RerankedRetriever",
    "RetrieverLike",
    "wrap_reranked",
    "passage_resolver",
    "BgeReranker",
    "load_bge_reranker",
    # retrieval recall-floor golden-set ((3)-2a / D69) - the floor EARNED, not hand-set
    "RetrievalCase",
    "FloorScore",
    "sweep_floor",
    "load_retrieval_golden",
    "RETRIEVAL_SEED",
    # reconciliation (D60 / invariant 10)
    "Reconciler",
    "ReconciliationFlag",
    # locks (D106 / invariant 25)
    "DocumentLocks",
    "LockContended",
    "LockHeldAcrossWaitError",
    # RAPTOR summary tree (Ch.5 / D56 / D44) - content-addressed store, RAM default + on-disk backend
    "RaptorStore",
    "RaptorNode",
    "RaptorBackend",
    "raptor_doc_id",
    "is_raptor_summary",
    "RAPTOR_SUMMARY_PREFIX",
]
