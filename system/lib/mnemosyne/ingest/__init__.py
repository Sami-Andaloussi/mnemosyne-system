"""Ingestion + classification (D123 LOT 4a) - the front door of the pipeline.

Three pieces sit between a raw source and the stores (LOT 4b):

* the sensitivity **classifier** (D101, invariant 18) - a label = ``MAX`` of signals,
  over a deterministic floor no model can pull under (:mod:`.classifier`);
* the deterministic **aiguilleur** (D57 write / D65 read routing), with the bubble-scoped
  A<->B read fusion realized in LOT 6 (:mod:`.router`);
* the **benne** raw-intake realities (D85) - lifecycle, non-destructive dedup FLAG,
  bounded queue (:mod:`.benne`).

Code & docstrings English (D117); sensitivity tokens stay French (D33 / D66).
"""

from __future__ import annotations

from .benne import (
    INTAKE_BOUND,
    INTAKE_SOURCE_BYTES_BOUND,
    Benne,
    BenneItem,
    DuplicateFlag,
    LifecycleState,
)
from .classifier import (
    DEFAULT_PII_RULES,
    CompositeSemanticSensor,
    DeterministicClassifier,
    NullSemanticSensor,
    PiiRule,
    SemanticSensor,
)
from .golden import (
    FIDELITY_SEED,
    MIN_INGEST_FIDELITY,
    FidelityCase,
    FidelityScore,
    load_fidelity_golden,
    score_fidelity,
)
from .router import (
    ContentNature,
    Engine,
    FusedAnswer,
    QueryKind,
    Route,
    fuse,
    route_ingest,
    route_read,
)
from .source import MimeDispatchSourceReader, PlainTextSourceReader
from .source_docling import connect_docling, connect_docling_figure_enricher
from .source_ocr import connect_mineru, connect_paddleocr
from .source_whisper import connect_whisperkit
from .caption import (
    NullImageCaptioner,
    count_image_holes,
    is_degenerate_caption,
    vision_captioner_if_enabled,
    weave_captions,
    weave_enrichments,
)
from .caption_mlx import connect_mlx_vlm
from .caption_anthropic import AnthropicVisionCaptioner, connect_anthropic_vision
from .figure_extract import (
    describe_vector_figure,
    is_raster_figure,
    vector_reader_factory_if_enabled,
)
from .figure_enrich import (
    BookEnrichResult,
    CampaignReport,
    enrich_figures_campaign,
    enrich_outcome,
)
from .vector_pymupdf import connect_pymupdf_reader
from .youtube import (
    parse_timedtext_json3,
    parse_youtube_ref,
    transcript_to_markdown,
    youtube_fetcher_if_available,
)
from .youtube_ytdlp import connect_ytdlp
from .structural import (
    NullStructuralExtractor,
    StructuralBackend,
    TreeSitterStructuralExtractor,
)
from .structural_treesitter import connect_treesitter
from .domain_lifecycle import (
    DomainLifecycleError,
    DomainPlan,
    create_domain,
    insert_taxonomy_line,
    plan_new_domain,
)
from .library import (
    KNOWLEDGE_BUBBLE,
    BookRecord,
    BookRef,
    BookStatus,
    IngestReport,
    LibraryManifest,
    OrphanReport,
    OrphanRow,
    RealignReport,
    detect_orphan_vectors,
    discover_books,
    domains_on_shelf,
    ingest_book,
    ingest_library,
    purge_orphan_vectors,
    realign_manifest_paths,
)
from .triage import (
    Disposition,
    ExecReport,
    Move,
    TriageEntry,
    TriagePlan,
    execute_plan,
    intake_backlog_count,
    plan_many,
    plan_triage,
    resolve_moves,
)
from .raptor_summarize import NullRaptorSummarizer, RaptorSummarizer, RunnerRaptorSummarizer
from .raptor_build import RaptorBuildReport, build_raptor_tree

__all__ = [
    # classifier (D101, invariant 18)
    "DeterministicClassifier",
    "SemanticSensor",
    "NullSemanticSensor",
    "CompositeSemanticSensor",
    "PiiRule",
    "DEFAULT_PII_RULES",
    # aiguilleur (D57 / D65)
    "route_ingest",
    "route_read",
    "fuse",
    "FusedAnswer",
    "Route",
    "Engine",
    "ContentNature",
    "QueryKind",
    # benne (D85)
    "Benne",
    "BenneItem",
    "DuplicateFlag",
    "LifecycleState",
    "INTAKE_BOUND",
    "INTAKE_SOURCE_BYTES_BOUND",
    # source ingestion (D125-B5, (3)-4) - the stub + the MIME dispatcher behind the SourceReader prise
    "PlainTextSourceReader",
    "MimeDispatchSourceReader",
    # source ingestion real bricks ((3)-4b) - sole-importer adapters (invariant 20), pragma: no cover
    "connect_docling",  # documents, first-class (D43)
    "connect_whisperkit",  # voice -> text, local OpenAI-compatible server (AV1 / D115)
    "connect_paddleocr",  # OCR repli (D43)
    "connect_mineru",  # OCR / document repli (D43)
    # vision caption weaving (sujet 2) - turn Docling figure holes into marked, searchable text (brick-free)
    "NullImageCaptioner",
    "weave_captions",
    "weave_enrichments",  # the one figure-hole insertion home (vision caption AND vector read-out)
    "is_degenerate_caption",  # reject the 7B's fizzled captions ("La") so the frontier / a hole takes over
    "vision_captioner_if_enabled",  # opt-in switch (MNEMOSYNE_VISION) wiring the stage into real ingestion
    "connect_mlx_vlm",  # sole-importer MLX-VLM adapter ((3)-4b, pragma: no cover)
    "AnthropicVisionCaptioner",  # Guard-mediated frontier captioner core (niveau 3, canal-B gesture)
    "connect_anthropic_vision",  # sole-importer Anthropic-vision adapter (sujet G, pragma: no cover)
    # vector-figure extraction (sujet E) - read a chart's own primitives into a structured read-out (brick-free)
    "describe_vector_figure",
    "is_raster_figure",
    "vector_reader_factory_if_enabled",  # opt-in switch (MNEMOSYNE_FIGURES) wiring extraction into ingestion
    "connect_pymupdf_reader",  # sole-importer PyMuPDF adapter ((3)-4b, pragma: no cover)
    # incremental figure enrichment (sujet F) - fill an EXISTING .md's holes from its PDF, re-index only those
    "count_image_holes",  # the one hole-counter besides weave_enrichments (anti-drift)
    "enrich_outcome",  # pure align-check + stats + splice (brick-free)
    "enrich_figures_campaign",  # walk the shelf, enrich in place, non-destructive backup, per-book isolation
    "CampaignReport",
    "BookEnrichResult",
    "connect_docling_figure_enricher",  # sole-importer Docling adapter for the in-place mode (pragma: no cover)
    # YouTube transcript (sujet 3) - brick-free core + sole-importer yt-dlp adapter
    "parse_youtube_ref",
    "parse_timedtext_json3",
    "transcript_to_markdown",
    "youtube_fetcher_if_available",  # best-effort wiring for real_runtime (None without the brick, D126)
    "connect_ytdlp",  # sole-importer yt-dlp adapter ((3) ignition, pragma: no cover, outbound)
    # ingestion fidelity golden-set (D125-B6, (3)-4)
    "score_fidelity",
    "load_fidelity_golden",
    "FidelityCase",
    "FidelityScore",
    "MIN_INGEST_FIDELITY",
    "FIDELITY_SEED",
    # structural pre-pass (D125-B9, (3)-3) - deterministic tree-sitter facts
    "NullStructuralExtractor",
    "StructuralBackend",
    "TreeSitterStructuralExtractor",
    "connect_treesitter",
    # pre-ingestion triage (D137 / D85, Étape 3) - sort a raw project folder before capture
    "plan_triage",
    "plan_many",
    "execute_plan",
    "resolve_moves",
    "TriagePlan",
    "TriageEntry",
    "Disposition",
    "Move",
    "ExecReport",
    "intake_backlog_count",  # Q2 autonomy: the raw-intake sas depth (meta signal for the proposer)
    # resumable library ingestion (D140, Étape 3) - the .md-first, unbreakable scale-up driver
    "ingest_library",
    "ingest_book",
    "discover_books",
    "domains_on_shelf",
    "realign_manifest_paths",  # G5: re-align manifest display paths post-réorg (avoids Qdrant duplicates)
    "RealignReport",
    "detect_orphan_vectors",  # G6: find vectors whose source left the shelf (post-réorg orphans)
    "purge_orphan_vectors",  # G6: governed, explicit, non-destructive-by-default purge of confirmed orphans
    "OrphanReport",
    "OrphanRow",
    "LibraryManifest",
    "IngestReport",
    "BookRef",
    "BookRecord",
    "BookStatus",
    "KNOWLEDGE_BUBBLE",
    # domain lifecycle (D46) - create a new domain: shelf + taxonomy line, EMIT the policy gesture for user
    "plan_new_domain",
    "create_domain",
    "insert_taxonomy_line",
    "DomainPlan",
    "DomainLifecycleError",
    # RAPTOR summarizer seam (Ch.5) - abstains brick-free (D126); the real prise mirrors RunnerGenerator
    "RaptorSummarizer",
    "NullRaptorSummarizer",
    "RunnerRaptorSummarizer",
    # RAPTOR tree build (Ch.5) - the corpus pass: book synopses -> domain synopses, self-reconciling
    "build_raptor_tree",
    "RaptorBuildReport",
]
