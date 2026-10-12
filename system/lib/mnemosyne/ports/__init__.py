"""Public protocol definitions for Mnemosyne System."""

from __future__ import annotations

from .backup import Backup, BackupClass, RestoreReport, SnapshotId
from .classifier import Classification, Classifier
from .core import (
    DEFAULT_SENSITIVITY,
    UNLABELED_BUBBLE,
    Bubble,
    CloisonnementError,
    Domain,
    Envelope,
    ErrorCode,
    EscalateToHuman,
    GovernanceLabel,
    GuardDenied,
    MnemosyneError,
    MonotonicityError,
    Provenance,
    ResourceBoundError,
    Sensitivity,
    TraceId,
    UnlabeledDataError,
)
from .embedder import Embedder, Embedding, Vector, is_indexable_vector
from .graphstore import Fact, FactId, GraphStore, NodeId
from .guard import (
    Channel,
    Decision,
    Effect,
    Grant,
    GrantToken,
    Guard,
    GuardRequest,
    HumanTier,
    Ruling,
)
from .iocontract import Skill
from .observability import HealthReport, HealthState, Observability
from .renderer import Redactor, Renderer, RenderDestination, RenderRequest, RenderResult
from .routing import RoutingClass  # model routing taxonomy (D7 - capability class per model call)
from .runner import GrammarConstraint, Runner
from .sandbox import IsolationTier, Sandbox, SandboxResult, SandboxSpec
from .scheduler import Scheduler, TriggerKind, WorkId, WorkItem, WorkState
from .store import (
    ConsistencyMarker,
    DEFAULT_ROLE,
    DocId,
    DocRole,
    IntentId,
    IntentKind,
    IntentLog,
    Intent,
    TruthStore,
)
from .tools import (
    DataEgress,
    ToolBackend,
    ToolCatalog,
    ToolEffect,
    ToolManifest,
    ToolPlugin,
)
from .keywordindex import KeywordIndex
from .reranker import NullReranker, Reranker  # cross-encoder rerank leg (D68 / D61 stage 6)
from .vectorindex import SearchHit, VectorIndex
from .structural import StructuralExtractor  # deterministic pre-pass (D125-B9, (3)-3)
from .source import Source, SourceReader  # source ingestion prise (D125-B5, (3)-4)
from .captioner import ImageCaptioner  # vision caption prise (sujet 2 - enriches Docling figures)
from .transcript import (  # YouTube transcript prise (sujet 3 - voice/video = a source of more)
    FetchedTranscript,
    TranscriptCue,
    TranscriptFetcher,
)

#: The engine/contract ports (the swap-able prises), in registry order - 13 at LOT 1 (D123)
#: plus KeywordIndex, the BM25 leg added at (3)-2b (D68).
PORTS: tuple[type, ...] = (
    Guard,
    Skill,
    Classifier,
    IntentLog,
    TruthStore,
    GraphStore,
    Embedder,
    VectorIndex,
    KeywordIndex,
    Reranker,
    Runner,
    Sandbox,
    ToolPlugin,
    ToolCatalog,
    Backup,
    Observability,
    Renderer,
    Scheduler,
)

__all__ = [
    # spine - governed-data algebra (core)
    "Sensitivity",
    "DEFAULT_SENSITIVITY",
    "Bubble",
    "Domain",
    "TraceId",
    "UNLABELED_BUBBLE",
    "Provenance",
    "GovernanceLabel",
    "Envelope",
    "ErrorCode",
    "MnemosyneError",
    "GuardDenied",
    "EscalateToHuman",
    "UnlabeledDataError",
    "CloisonnementError",
    "MonotonicityError",
    "ResourceBoundError",
    # Guard (D89)
    "Guard",
    "GuardRequest",
    "Ruling",
    "Decision",
    "Grant",
    "GrantToken",
    "HumanTier",
    "Effect",
    "Channel",
    # model routing (D7 - capability class per model call)
    "RoutingClass",
    # Skill I/O contract (D108)
    "Skill",
    # Classifier (D101)
    "Classifier",
    "Classification",
    # Store / IntentLog (D105)
    "TruthStore",
    "IntentLog",
    "Intent",
    "IntentKind",
    "ConsistencyMarker",
    "DocId",
    "DocRole",
    "DEFAULT_ROLE",
    "IntentId",
    # GraphStore (D103)
    "GraphStore",
    "Fact",
    "NodeId",
    "FactId",
    # Embedder (D68)
    "Embedder",
    "Embedding",
    "Vector",
    "is_indexable_vector",
    # VectorIndex (D68)
    "VectorIndex",
    "SearchHit",
    # KeywordIndex (D68) - BM25 leg added at (3)-2b
    "KeywordIndex",
    # Reranker (D68 / D61 stage 6) - cross-encoder rerank leg added at LOT 5
    "Reranker",
    "NullReranker",
    # StructuralExtractor (D125-B9) - deterministic tree-sitter pre-pass added at (3)-3
    "StructuralExtractor",
    # SourceReader (D125-B5) - the binary/voice ingestion prise added at (3)-4
    "Source",
    "SourceReader",
    # ImageCaptioner (sujet 2) - vision caption prise enriching Docling figures
    "ImageCaptioner",
    # TranscriptFetcher (sujet 3) - YouTube transcript prise (outbound, Guard-mediated)
    "TranscriptFetcher",
    "FetchedTranscript",
    "TranscriptCue",
    # Runner (D104)
    "Runner",
    "GrammarConstraint",
    # Sandbox (D99)
    "Sandbox",
    "SandboxSpec",
    "SandboxResult",
    "IsolationTier",
    # Tools / MCP (D114)
    "ToolPlugin",
    "ToolCatalog",
    "ToolManifest",
    "ToolBackend",
    "DataEgress",
    "ToolEffect",
    # Backup (D110 / D118)
    "Backup",
    "BackupClass",
    "SnapshotId",
    "RestoreReport",
    # Observability (D111)
    "Observability",
    "HealthReport",
    "HealthState",
    # Renderer (D108 / D66) - the governed document-output prise added at (3)-6
    "Renderer",
    "Redactor",
    "RenderDestination",
    "RenderRequest",
    "RenderResult",
    # Scheduler (D93 / D96)
    "Scheduler",
    "WorkItem",
    "WorkId",
    "WorkState",
    "TriggerKind",
    # the collected ports
    "PORTS",
]
