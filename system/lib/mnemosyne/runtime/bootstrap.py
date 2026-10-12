"""Bootstrap (D94) — the cold start that assembles the runtime and wires the model seams.

The stores are gitignored (D71), so they are ABSENT at clone: the repo holds only the
versioned truth, never the derivatives. :func:`bootstrap` is the first launch — it creates
the three stores + config, assembles the Guard, scheduler, runner, snapshots and
observability, and runs the first indexing by replaying the journal (rebuild the derived
stores FROM the truth, the arbiter — D56 / FL3).

It is also where the **real local models plug into the seams** LOT 4a / 4b deferred: the
classifier's semantic pass (:class:`~mnemosyne.runtime.models.ModelSemanticSensor`) and the
graph's fact extractor (:class:`~mnemosyne.runtime.models.ModelFactExtractor`), both behind
the Guard (D89), content-as-data, raise-only (D100). With the stub runner they abstain — the
wiring is real, the weights arrive at ③.

**Idempotent / non-destructive (D94 / D44 / D63).** Re-running is safe: first indexing is the
journal's idempotent replay (invariant 24), so a second cold start reaches the same state and
overwrites nothing. On disk (③) a missing store is (re)created and an existing one is kept;
here (in-memory skeleton) that idempotence is carried by the replay. Code & docstrings
English (D117).

Decisions: D94 (cold start) · D71 (gitignored stores) · D56 / FL3 (rebuild derived from
truth) · D44 / D63 (idempotent, non-destructive) · D89 / D100 (model seams behind the Guard).
Invariant carried: substrate of 24 (idempotent replay is the first indexing).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from ..config import Policy, load_policy
from ..guard import (
    BoundedScheduler,
    DeterministicGuard,
    SecretDecryptor,
    WallLedger,
    load_secret_broker,
)
from ..guard.secrets_sops import connect_sops_age
from ..ingest import (
    CompositeSemanticSensor,
    DeterministicClassifier,
    MimeDispatchSourceReader,
    NullRaptorSummarizer,
    NullStructuralExtractor,
    PlainTextSourceReader,
    RaptorSummarizer,
    RunnerRaptorSummarizer,
    SemanticSensor,
    connect_docling,
    connect_treesitter,
    connect_whisperkit,
    vector_reader_factory_if_enabled,
    vision_captioner_if_enabled,
    youtube_fetcher_if_available,
)
from ..ingest.pii_presidio import connect_presidio_redactor, connect_presidio_sensor
from ..ports import (
    Bubble,
    Embedder,
    GovernanceLabel,
    Grant,
    GraphStore,
    KeywordIndex,
    Redactor,
    Renderer,
    Reranker,
    RoutingClass,
    Sandbox,
    Sensitivity,
    SourceReader,
    StructuralExtractor,
    ToolPlugin,
    TranscriptFetcher,
    VectorIndex,
)
from ..production import (
    ConfigSkillCatalog,
    EndorsementLedger,
    HumanLayerJournal,
    LivingMemory,
    ProposalsLedger,
    resolve_model_id,
)
from ..tools import (
    ConfigToolCatalog,
    GovernedToolInvoker,
    RefusingSandbox,
    connect_sandbox_runtime,
)
from ..stores import (
    QDRANT_URL,
    InMemoryGraphStore,
    InMemoryKeywordIndex,
    InMemoryVectorIndex,
    IntentJournal,
    MarkdownTruthStore,
    RaptorStore,
    Retriever,
    StubEmbedder,
    connect_ladybug,
    connect_qdrant,
    connect_tantivy,
    load_bge_m3,
    load_bge_reranker,
)
from .backup import BackupEngine, KopiaBackup
from .backup_kopia import connect_kopia
from .health import HardwareProbe
from .health_probe import SystemHardwareProbe, psutil_ram_reader
from .local_first import ServiceDependency, StartupReporter, enforce_local_first, require_services
from .memory_search import SEARCH_MEMORY, build_search_memory_tool
from .models import ModelFactExtractor, ModelSemanticSensor, _model_call_request
from .observability import LocalObservability, TraceSink, fan_out
from .observability_jsonl import open_jsonl_sink
from .observability_langfuse import connect_langfuse
from .render import GovernedRenderer, RefusingRenderer
from .render_typst import connect_typst
from .backend_registry import BackendRegistry
from .model_router import ModelRouter
from .runner import GenerationBackend, LocalRunner
from .runner_mlx import load_mlx_backend
from .runner_outlines import connect_outlines
from .snapshots import SnapshotStore

#: The reduced-rights bubble ingestion / extraction models run in (zero-trust, D81).
_INGEST_BUBBLE = Bubble("ingest")


@dataclass(frozen=True, slots=True)
class Runtime:
    """The assembled runtime (D94) — every component wired, the model seams filled.

    Holds the three stores + their integrity journal, the Guard and its scheduler, the
    grammar-bound runner with its protected snapshot store and clean observability, and the
    classifier + fact extractor whose local-model seams are wired behind the Guard."""

    policy: Policy
    truth: MarkdownTruthStore
    vector: VectorIndex
    keyword: KeywordIndex
    graph: GraphStore
    embedder: Embedder
    journal: IntentJournal
    guard: DeterministicGuard
    scheduler: BoundedScheduler
    snapshots: SnapshotStore
    observability: LocalObservability
    runner: LocalRunner
    classifier: DeterministicClassifier
    fact_extractor: ModelFactExtractor
    living_memory: LivingMemory
    #: D156 — the durable endorsement journal (which documents the operator made citable). Optional: a raw
    #: ``Runtime`` (stub / unit test) has none, and endorsing then stays an in-memory act, exactly as
    #: before. ``real_runtime`` wires the on-disk one, which is what makes the gesture SURVIVE.
    endorsements: EndorsementLedger | None = None
    #: Whether extracted facts are auto-filed to the graph (③-3c plan-B gate). **Default False —
    #: fail-closed BY TYPE** (audit ③-7 M2 / D100): a raw ``Runtime`` never inherits trust; only an
    #: explicit measurement raises it. ``bootstrap()`` passes True for the STUB (vacuous — the stub
    #: extractor abstains); ``real_runtime`` passes False until a golden-set measurement of the REAL
    #: extractor (:mod:`~mnemosyne.production.golden`) clears the bar (traced debt at ignition, D69).
    graph_extraction_trusted: bool = False
    #: Deterministic structural pre-pass (tree-sitter, D125-B9 / ③-3) — the 6th brick, injectable;
    #: default is the abstaining stub, so the suite runs with tree-sitter NOT installed (D126).
    structural_extractor: StructuralExtractor = field(default_factory=NullStructuralExtractor)
    #: Source reader (D125-B5 / ③-4) — the binary/voice ingestion prise, injectable; default is the
    #: utf-8 stub, so the suite runs with NO OCR / ASR brick installed (D126). real_runtime wires
    #: Docling (documents) + WhisperKit (voice) behind it at ③-4b.
    source_reader: SourceReader = field(default_factory=PlainTextSourceReader)
    #: Whether an extraction from a raw source is auto-trusted (③-4 fidelity gate). **Default False —
    #: fail-closed BY TYPE** (audit ③-7 M2 / D100): a raw ``Runtime`` never inherits trust. ``bootstrap()``
    #: passes True for the STUB (vacuous — the utf-8 stub is faithful); ``real_runtime`` passes False until
    #: a fidelity golden-set measurement of the REAL reader (:mod:`~mnemosyne.ingest.golden`) clears the
    #: bar — below it an extraction is FLAGGED low-fidelity, raw preserved in the benne (traced debt, D69).
    source_extraction_trusted: bool = False
    #: The OUTBOUND transcript prise (sujet 3 / ③-4c) — a YouTube URL → verbatim subtitles, injectable;
    #: default ``None`` so the suite and a bricks-less runtime stay green (D126). real_runtime wires the
    #: yt-dlp adapter when the OPTIONAL brick is installed. It opens NOTHING on its own: the ONLY door is
    #: :meth:`CoreApi.capture_youtube`, which asks the Guard for an ``EXTERNAL_OUTPUT`` grant FIRST, so an
    #: unset egress allow-list refuses every fetch (deny-by-default, invariant 5 / 21). ``None`` ⇒
    #: capture_youtube fails closed (no fetcher, no fetch).
    transcript_fetcher: TranscriptFetcher | None = None
    #: The OS-isolation seam (D99 / ③-5) — the last line for a tool that runs untrusted code, injectable;
    #: default is the fail-closed :class:`~mnemosyne.tools.RefusingSandbox`, so the suite runs with NO
    #: sandbox engine (D126). real_runtime wires the two-tier Seatbelt + micro-VM engines at ③-5b.
    sandbox: Sandbox = field(default_factory=RefusingSandbox)
    #: The governed tool-call executor (D114-③ / ③-5) — grant → redeem → invoke → re-label the untrusted
    #: return by the max. Built in :func:`bootstrap` from the Guard, deny-by-default (no plugin wired);
    #: real_runtime wires the MCP / local back-ends at ③-5b. ``None`` only in a hand-built Runtime that
    #: never calls a tool (:meth:`CoreApi.call_tool` then fails closed — no invoker, no tool).
    tool_invoker: GovernedToolInvoker | None = None
    #: The governed document-output consumer (sorties, D66 / ③-6) — a LOCAL render emits any label
    #: (interior, D71), a SHAREABLE render is egress-governed (allow-list + M2 content re-floor). Built
    #: in :func:`bootstrap` from the Guard + floor classifier around the rendering engine; the engine
    #: defaults to the fail-closed :class:`~mnemosyne.runtime.render.RefusingRenderer` (so the suite runs
    #: with NO Typst brick, D126), and the Presidio redactor stays unwired until ③-6b. ``None`` only in a
    #: hand-built Runtime that never renders (:meth:`CoreApi.render` then fails closed — no renderer).
    renderer: GovernedRenderer | None = None
    #: The asymmetric encrypted backup (D110 / D118 / ③-6) — the barrier logic (off-site zero-knowledge
    #: refusal, asymmetry) is couture; the snapshot/restore I/O is a ``BackupEngine`` that defaults to the
    #: in-process stub (D126) and is injected with the real Kopia engine by real_runtime at ③-6b. ``None``
    #: only in a hand-built Runtime (:meth:`CoreApi.verify_restore` then falls back to a stub backup).
    backup: KopiaBackup | None = None
    #: The real hardware probe (disk / RAM / thermal, D111 / ③-6) read by :class:`CoreApi`'s health
    #: monitor. Default ``None`` ⇒ the healthy stub (D126 — deterministic tests); real_runtime injects
    #: :class:`~mnemosyne.runtime.health_probe.SystemHardwareProbe` (real disk via stdlib, RAM via psutil)
    #: at ③-6b.
    hardware_probe: HardwareProbe | None = None
    #: The protected skill registry (⑥ / D114-TO2 / D37) — the active-skill allow-list that
    #: :meth:`CoreApi.describe_self` advertises as its 2nd source, sibling of the tool catalog. Default
    #: is an EMPTY catalog (D126 / deny-by-default: a hand-built Runtime advertises no skill);
    #: ``bootstrap()`` loads the protected ``skills.toml`` (empty until the operator's activation gesture, D102).
    #: Read-only — it activates nothing (D100 / D102).
    skill_catalog: ConfigSkillCatalog = field(default_factory=ConfigSkillCatalog)
    #: The RAPTOR summary-tree store (Ch.5 / RAG niveau 2 / D56 / D44) — book + domain synopses over
    #: the corpus, content-addressed and DERIVED (never truth). Default ``None``: a hand-built
    #: Runtime (bypassing :func:`bootstrap`) carries no RAPTOR store, so the summary read-path
    #: (:meth:`~mnemosyne.api.core_api.CoreApi._pack_summary`) degrades safely — skip, never crash
    #: (D126). ``bootstrap()`` always wires a RAM-backed store by default; ``real_runtime`` wires the
    #: on-disk one under ``system/state/``.
    raptor: RaptorStore | None = None
    #: The abstractive summarizer behind the guarded runner (Ch.5) feeding ``raptor`` — ``None``
    #: mirrors ``raptor`` (no store wired, no summarizer needed). ``bootstrap()`` wires the
    #: abstaining :class:`~mnemosyne.ingest.raptor_summarize.NullRaptorSummarizer` by default (a
    #: brick-free build creates zero summary nodes); ``real_runtime`` wires
    #: :class:`~mnemosyne.ingest.raptor_summarize.RunnerRaptorSummarizer` over the SAME guarded
    #: runner the other model seams use.
    raptor_summarizer: RaptorSummarizer | None = None
    #: The cross-encoder rerank leg (LOT 5 / D68 / D61 stage 6) — bge-reranker-v2-m3 behind the
    #: :class:`~mnemosyne.ports.reranker.Reranker` port. Default ``None`` ⇒ NO rerank wrapper, so
    #: retrieval is byte-identical to pre-LOT-5 (zero regression, D126). ``real_runtime`` wires the
    #: real cross-encoder (paired with bge-m3); :class:`~mnemosyne.api.core_api.CoreApi` composes it
    #: over the base retriever with :func:`~mnemosyne.stores.reranked_retriever.wrap_reranked`.
    reranker: Reranker | None = None

    def first_index(self) -> None:
        """Run (or re-run) the first indexing: replay the journal to rebuild the derived
        stores FROM the truth (D56 / D94). Idempotent — a second call is a no-op (inv. 24)."""
        self.journal.replay()


def bootstrap(
    *,
    policy: Policy | None = None,
    truth: MarkdownTruthStore | None = None,
    embedder: Embedder | None = None,
    vector: VectorIndex | None = None,
    keyword: KeywordIndex | None = None,
    graph: GraphStore | None = None,
    structural_extractor: StructuralExtractor | None = None,
    source_reader: SourceReader | None = None,
    transcript_fetcher: TranscriptFetcher | None = None,
    generation_backend: GenerationBackend | None = None,
    backends: BackendRegistry | None = None,
    sandbox: Sandbox | None = None,
    plugins: Mapping[str, ToolPlugin] | None = None,
    renderer: Renderer | None = None,
    redactor: Redactor | None = None,
    secret_vault: Path | None = None,
    secret_decryptor: SecretDecryptor | None = None,
    backup_engine: BackupEngine | None = None,
    trace_sink: TraceSink | None = None,
    pii_sensor: SemanticSensor | None = None,
    hardware_probe: HardwareProbe | None = None,
    skill_catalog: ConfigSkillCatalog | None = None,
    graph_extraction_trusted: bool = True,
    source_extraction_trusted: bool = True,
    human_journal: HumanLayerJournal | None = None,
    proposals_ledger: ProposalsLedger | None = None,
    endorsements: EndorsementLedger | None = None,
    walls: WallLedger | None = None,
    snapshot_base_path: Path | None = None,
    raptor: RaptorStore | None = None,
    enable_raptor_summarizer: bool = False,
    reranker: Reranker | None = None,
) -> Runtime:
    """Cold-start Mnémosyne: create the stores, assemble the runtime, wire the model seams.

    Idempotent and non-destructive (D94): the first indexing is the journal's idempotent
    replay, so re-running reaches the same state. The classifier's semantic pass and the fact
    extractor are wired to the local runner BEHIND the Guard (D89 / D100); with the stub decoder
    they abstain until a real model is installed at ③. ``embedder`` / ``vector`` / ``keyword`` /
    ``graph`` / ``generation_backend`` may be injected — the real bge-m3 / Qdrant / tantivy /
    LadybugDB / MLX bricks at ③ ignition (see :func:`real_runtime`); by default the in-memory stubs
    are used, so the suite runs with nothing installed (D126).

    ``raptor`` (Ch.5 / RAG niveau 2) injects a :class:`~mnemosyne.stores.raptor.RaptorStore`; left
    ``None`` a fresh RAM-backed one is created (never disk, D126). ``enable_raptor_summarizer``
    switches the summarizer wired behind it: ``False`` (default) wires the abstaining
    :class:`~mnemosyne.ingest.raptor_summarize.NullRaptorSummarizer` (a brick-free build creates
    zero summary nodes — the stub decoder would otherwise ECHO prompt junk as a "synopsis"); ``True``
    wires :class:`~mnemosyne.ingest.raptor_summarize.RunnerRaptorSummarizer` over THIS call's own
    ``runner`` + ``guard`` (mirroring how the OTHER model seams below are always built from the
    SAME internal instances, never a second one)."""
    resolved = policy if policy is not None else load_policy()

    # the three stores (D105) + the derived retrieval indexes + their integrity journal —
    # gitignored, created fresh (D71 / D94). embedder / vector / keyword may be injected (the real
    # bricks at ③, via real_runtime); else stubs (D126).
    truth = truth if truth is not None else MarkdownTruthStore()
    vector = vector if vector is not None else InMemoryVectorIndex()
    keyword = keyword if keyword is not None else InMemoryKeywordIndex()
    graph = graph if graph is not None else InMemoryGraphStore()
    embedder = embedder if embedder is not None else StubEmbedder()
    journal = IntentJournal(
        truth=truth, vector=vector, keyword=keyword, graph=graph, embedder=embedder
    )

    # the Guard (D89) + its bounded scheduler (D93), both keyed on the protected zone (SE4). The Guard
    # reads the PROTECTED tool allow-list (D114-⑤) so `TOOL_CALL` is governed from the manifest, never
    # the caller's word; deny-by-default — the skeleton ships no tool wired (D98). One pure-code floor
    # classifier (no model, D100) serves both the egress PII floor and the untrusted tool-return floor.
    # observability (D111): local tracing whose greppable log is redacted by construction. ``trace_sink``
    # (default None ⇒ in-memory only, D126) forwards each ALREADY-redacted line to a LOCAL Langfuse/OTel
    # export at ③-6b — the sink never sees `sensible` content (the redaction is upstream, inv. 12 / 22).
    observability = LocalObservability(sink=trace_sink)
    floor_classifier = DeterministicClassifier()
    # the secret vault (D81 / ③-6): the encrypted-at-rest store decrypted at cold start into a
    # last-instant broker. Fail-closed (inv. 22): with no decryptor / vault wired (the skeleton), the
    # broker is EMPTY → every SECRET_USE is denied. real_runtime injects the SOPS+age decryptor at ③-6b.
    secrets = load_secret_broker(vault_path=secret_vault, decrypt=secret_decryptor)
    guard = DeterministicGuard(
        policy=resolved,
        observability=observability,
        classifier=floor_classifier,
        catalog=ConfigToolCatalog.load(),
        secrets=secrets,
        # D159 — every non-ALLOW verdict is deposited (fail-open, never a security boundary):
        # absent by default (None ⇒ no-op inside the Guard), so every existing caller is
        # byte-identical; real_runtime wires a REAL, disk-backed ledger below.
        walls=walls,
    )
    scheduler = BoundedScheduler.from_policy(resolved)
    # RAPTOR summary store (Ch.5) resolved HERE — before the search_memory wiring below — so the agent
    # tool AND the corpus build share the ONE store: a RAM default (D126), or the on-disk store
    # real_runtime injects. Its summarizer (Null vs Runner) is swapped further down, with the runner.
    raptor = raptor if raptor is not None else RaptorStore()
    # the governed tool-call executor (③-5): grant → redeem (the non-local consumer that closes the ③-1
    # egress-seal debt) → invoke → re-label the untrusted return by the max (D101 / D100). The agent's
    # FIRST tool — search_memory (③-5b / D65) — is ALWAYS wired here, reading Mnémosyne's own memory
    # through the same hybrid retrieval + cloisonnement frontier as the facade (governed_read). It stays
    # deny-by-default: the Guard refuses it until the operator sanctions its manifest in the protected catalog
    # (tools.toml, D114-⑤), back-end present or not. Injected ``plugins`` merge on top by name
    # (real_runtime / an [OPERATOR] allow-list gesture wires the real MCP / local back-ends at ③-5b).
    wired_plugins: dict[str, ToolPlugin] = {
        SEARCH_MEMORY: build_search_memory_tool(
            retriever=Retriever.from_policy(resolved, vector, embedder, keyword=keyword),
            guard=guard,
            truth=truth,
            summaries=raptor,  # so a RAPTOR summary hit is read from the store, not KeyErrored on truth
            # Item 12 — the agent's READ CLEARANCE is DECOUPLED from its answer floor: it runs under a
            # conservative `sensible` answer label (D101) but must READ its `public` reference library
            # (the 2026-07-16 "books = public by provenance" migration — 235k chunks in mnemosyne_public,
            # where `make search` reads). Without this it would search the near-empty `sensible` partition
            # and miss the whole library. One explicit partition (still invariant 1), re-floored up on
            # return (D100-3) — never a declassification.
            search_within=Sensitivity.PUBLIC,
        )
    }
    if plugins is not None:
        # a built-in tool name must not be silently shadowed by an injected plugin (audit ③-5b M-1;
        # enforce-collisions-structurally): refuse a clash fail-closed rather than overwrite the wiring.
        clash = set(plugins) & set(wired_plugins)
        if clash:
            raise ValueError(
                f"injected plugin(s) {sorted(clash)} shadow a built-in tool — refused "
                "(enforce-collisions-structurally: a name collision is a bug, not a silent override)"
            )
        wired_plugins.update(plugins)
    tool_invoker = GovernedToolInvoker(
        guard=guard, plugins=wired_plugins, classifier=floor_classifier
    )
    # the governed document-output consumer (sorties, ③-6): a SHAREABLE render is egress-governed by the
    # SAME Guard + floor classifier (allow-list inv. 21 + M2 content re-floor), a LOCAL render is interior
    # (D71). The rendering engine defaults to the fail-closed RefusingRenderer (no Typst brick → refuse,
    # never a fabricated artifact, D126); real_runtime wires connect_typst + a Presidio redactor at ③-6b.
    governed_renderer = GovernedRenderer(
        renderer=renderer if renderer is not None else RefusingRenderer(),
        guard=guard,
        classifier=floor_classifier,
        redactor=redactor,  # None until Presidio is wired at ③-6b (non-public share then escalates, D100)
        observability=observability,
    )
    # the asymmetric encrypted backup (D110 / ③-6): the off-site zero-knowledge barrier is couture; the
    # snapshot/restore I/O is a BackupEngine defaulting to the in-process stub (D126). real_runtime injects
    # the real Kopia engine at ③-6b. Local-only by default (D71 — the repo versions the sensible).
    backup = KopiaBackup(engine=backup_engine)

    # the grammar-bound runner (D104) with its protected replay store + clean logs (inv. 12);
    # wired to the Guard so it authenticates each grant's token before running (M1 / D89 / D100).
    # Its decode backend may be injected (the real MLX brick at ③, via real_runtime); else the
    # weightless stub decoder, so the suite runs with nothing installed (D126).
    # replayable model-call snapshots (D76 / invariant 12): base_path=None ⇒ the RAM store (D126 — the
    # suite runs with no disk I/O); a path persists them, bounded by the protected retention
    # (``snapshot_retain_last``, D78) read from the policy via from_policy. real_runtime wires the disk
    # path so PRODUCTION keeps its replay history across a crash (D76 "nothing lives in the model").
    snapshots = (
        SnapshotStore.from_policy(resolved, base_path=snapshot_base_path)
        if snapshot_base_path is not None
        else SnapshotStore()
    )
    runner = LocalRunner(
        snapshots=snapshots,
        observability=observability,
        backend=generation_backend,
        backends=backends,
        guard=guard,
        # D136 / audit m-2 — the input ceiling lives in the D78 named place (policy.bounds); absent
        # ⇒ None ⇒ the runner's conservative default. ③ tunes it per installed model + corpus here.
        max_prompt_chars=resolved.bounds.get("max_prompt_chars"),
    )

    # the model seams (D100), behind the Guard: semantic pass (4a) + fact extractor (4b). The contextual
    # LLM sensor and the optional Presidio PII sensor (③-6b, ``pii_sensor``) share the ONE semantic slot
    # via a raise-only MAX composite — both can only push the verdict UP, never below the deterministic
    # floor (invariant 18). Absent a Presidio sensor (the skeleton), the LLM sensor stands alone (D126).
    # D7 — the task-class → model router (model-agnostic, from the loaded policy). The model
    # consumers below declare their capability class through it; today every class resolves to the
    # capable default (empty table), so the routed model is recorded for provenance and the physical
    # backend swap awaits the bench (D69). The CHANNEL stays the Guard's route_model (sensitivity).
    model_router = ModelRouter(resolved)
    model_semantic: SemanticSensor = ModelSemanticSensor(
        guard, runner, subject=_INGEST_BUBBLE, router=model_router
    )
    semantic: SemanticSensor = (
        model_semantic
        if pii_sensor is None
        else CompositeSemanticSensor((model_semantic, pii_sensor))
    )
    classifier = DeterministicClassifier(semantic=semantic)
    fact_extractor = ModelFactExtractor(guard, runner, subject=_INGEST_BUBBLE, router=model_router)

    # the deterministic structural pre-pass (tree-sitter, D125-B9 / ③-3) — injectable (the real brick
    # at ignition, via real_runtime); else the abstaining stub, so the suite runs brick-free (D126).
    structural_extractor = (
        structural_extractor if structural_extractor is not None else NullStructuralExtractor()
    )

    # the source reader (D125-B5 / ③-4) — injectable (Docling documents / WhisperKit voice at ignition,
    # via real_runtime); else the utf-8 stub, so the suite runs with no OCR / ASR brick (D126).
    source_reader = source_reader if source_reader is not None else PlainTextSourceReader()

    # RAPTOR summary tree (Ch.5 / RAG niveau 2, D56 / D44) — OPTIONAL, additive wiring (D126): the RAM
    # store default (never disk unless `raptor` is injected with a base_path, mirroring the snapshot
    # store's own RAM-default / on-disk-when-given-a-path shape) was resolved ABOVE, next to the
    # search_memory wiring that shares it. The summarizer behind it is the OTHER model-seam idiom in
    # this function (like model_semantic / fact_extractor just above): built HERE from THIS call's own
    # guard + runner, never a second instance — but unlike those two (always the SAME class, whose
    # behaviour naturally abstains against the stub), RAPTOR needs the CLASS itself swapped
    # (NullRaptorSummarizer vs RunnerRaptorSummarizer), because the stub decoder's free-form
    # `complete()` ECHOES its prompt rather than abstaining.

    def _raptor_grant_source(label: GovernanceLabel) -> Grant:
        """Mint a fresh ``MODEL_CALL`` grant for one summarization call (D89 / D100 / M1) — never
        self-granted; the ingestion-time reduced-rights bubble, like the other model seams here.

        Routed by task class (D7, audit N1): a synopsis is a REASONING task, so it flows through the
        SAME :func:`_model_call_request` the sensors use — the routed model (or the capable default)
        is recorded as ``target`` for provenance. The CHANNEL stays the Guard's own ``route_model``
        (sensitivity, invariant 1): a ``sensible`` cluster is summarized LOCAL regardless of model."""
        return guard.grant(
            _model_call_request(
                subject=_INGEST_BUBBLE,
                inputs=(label,),
                router=model_router,
                routing_class=RoutingClass.REASONING,
                action="raptor-summarize",
            )
        )

    raptor_summarizer: RaptorSummarizer = (
        # The runner's OWN resolved ceiling (not the raw policy value) — so the summarizer map-reduces
        # a big book into per-call groups that never trip the runner's fail-closed bound (D136 / Ch.5),
        # and the two ceilings are provably the SAME number, never two constants that could drift.
        RunnerRaptorSummarizer(
            runner, _raptor_grant_source, max_prompt_chars=runner.max_prompt_chars
        )
        if enable_raptor_summarizer
        else NullRaptorSummarizer()
    )

    # Moteur A's living-memory pipeline (D58-D60) — proposes, validates, reinjects bubble-scoped.
    # The human-layer journal (D82) is wired at ③ (real_runtime); once wired, replay rebuilds the operator's
    # validations from the durable net at cold start, BEFORE the runtime is assembled. Absent (stub /
    # unit tests) ⇒ pure in-memory, no persistence (D126).
    living_memory = LivingMemory(journal=human_journal, proposals_ledger=proposals_ledger)
    if human_journal is not None:
        human_journal.replay(living_memory)
    # the proposals ledger (item 2) replays AFTER the human journal, so a since-validated / since-dismissed
    # learning is not resurrected (closed stays closed, D60-2 — _restore_proposed drops already-decided ids).
    if proposals_ledger is not None:
        proposals_ledger.replay(living_memory)

    runtime = Runtime(
        policy=resolved,
        truth=truth,
        vector=vector,
        keyword=keyword,
        graph=graph,
        embedder=embedder,
        journal=journal,
        guard=guard,
        scheduler=scheduler,
        snapshots=snapshots,
        observability=observability,
        runner=runner,
        classifier=classifier,
        fact_extractor=fact_extractor,
        living_memory=living_memory,
        endorsements=endorsements,
        graph_extraction_trusted=graph_extraction_trusted,
        structural_extractor=structural_extractor,
        source_reader=source_reader,
        source_extraction_trusted=source_extraction_trusted,
        transcript_fetcher=transcript_fetcher,
        sandbox=sandbox if sandbox is not None else RefusingSandbox(),
        tool_invoker=tool_invoker,
        renderer=governed_renderer,
        backup=backup,
        hardware_probe=hardware_probe,
        # the active-skill registry describe_self advertises (⑥); the protected zone is read once at
        # boot, fail-fast on a malformed file, empty until the operator sanctions a skill ACTIVE (D102 / D37).
        skill_catalog=skill_catalog if skill_catalog is not None else ConfigSkillCatalog.load(),
        # RAPTOR summary tree (Ch.5) — RAM store + abstaining summarizer by default (D126); real_runtime
        # wires the on-disk store + the guarded RunnerRaptorSummarizer (see above).
        raptor=raptor,
        raptor_summarizer=raptor_summarizer,
        # rerank leg (LOT 5 / D68) — None by default ⇒ CoreApi wraps nothing (zero regression);
        # real_runtime wires the real cross-encoder (paired with bge-m3). See Runtime.reranker.
        reranker=reranker,
    )
    runtime.first_index()  # first indexing = idempotent replay from the truth (D56 / D94)
    return runtime


#: The SOPS-encrypted secret vault in the protected zone (SE4 / ③-6). Best-guess path, confirmed at
#: ignition ([OPERATOR]); ABSENT ⇒ ``load_secret_broker`` fail-closes to an EMPTY broker (every SECRET_USE
#: denied, inv. 22) — so a mis-located vault degrades safely, never a plaintext fallback (D100).
_SECRET_VAULT_PATH = Path(__file__).resolve().parents[3] / "config" / "secrets.enc.json"

#: The durable trace directory (``system/logs``) — the append-only JSONL trail (D6). One file per process
#: run (``trace_<UTC>.jsonl``, like the reshelve journal); gitignored (paths / operational metadata stay
#: local, D71). ``open_jsonl_sink`` creates it if absent and fail-safes on any I/O error (D111).
_TRACE_LOG_DIR = Path(__file__).resolve().parents[3] / "logs"

#: The DISTILLED shelf (D157): the verified reading layer — chapter-structured fiches in French,
#: judged (243/249) — indexed alongside the raw books it was distilled FROM.
_DISTILLED_MANIFEST = Path(__file__).resolve().parents[4] / "knowledge" / "distilled_manifest.json"
_DISTILLED_ROOT = Path(__file__).resolve().parents[4] / "knowledge" / "distilled"

#: The human-layer journal (``system/state/human_layer.jsonl``) — the replayable, fail-closed net under
#: Moteur A's HUMAN gestures (D82). LOCAL + gitignored in the code repo (it holds real fiche content,
#: possibly ``perso`` / ``sensible`` — a sensible-local barrier, D27 / D71) and protected by the encrypted
#: Kopia PRECIOUS snapshot (D110). Versioned in the dedicated private truth store when D98 is lit.
_HUMAN_LAYER_PATH = Path(__file__).resolve().parents[3] / "state" / "human_layer.jsonl"

#: The proposals ledger (``system/state/proposals.jsonl``) — the durable landing for NON-rebuildable
#: living-memory proposals (a ``make remember`` LEARNING), SEPARATE from the human-gesture journal above
#: (item 2 / audit ebf0846 MAJOR-1): the gesture journal rebuilds nothing, but a proposal mostly DOES (the
#: ③-3c extractor re-proposes from ``raw/``, D44) — so only the no-backup capture lands here. Same LOCAL,
#: gitignored (``system/state/*.jsonl``), Kopia-PRECIOUS convention as the human-layer journal above.
_PROPOSALS_PATH = Path(__file__).resolve().parents[3] / "state" / "proposals.jsonl"

#: The wall log (``system/state/walls.jsonl``, D159) — every refusal the Guard has returned in
#: THIS repo, fail-open (a lost line is tolerable; the Guard's verdict never depends on this
#: write succeeding, unlike the write-ahead journals above). Same LOCAL, gitignored convention.
_WALLS_PATH = Path(__file__).resolve().parents[3] / "state" / "walls.jsonl"

#: The RAPTOR summary-tree store (Ch.5 / RAG niveau 2, D56 / D44): book + domain synopses persist
#: under ``system/state/raptor_store.jsonl`` — the SAME convention (and the SAME gitignore rule,
#: ``system/state/*.jsonl``) as ``_HUMAN_LAYER_PATH`` just above. A derived, reconstructible index of
#: the corpus's own hierarchy (D56): losing it only means a re-``make raptor-build`` regenerates it.
_RAPTOR_STORE_PATH = Path(__file__).resolve().parents[3] / "state" / "raptor_store.jsonl"

#: The on-disk replay-snapshot store (D76 / CF3): model-call snapshots persist under
#: ``knowledge/.snapshotstore`` (gitignored, a reconstructible derivative like ``.vectorstore`` /
#: ``.graphstore``, D71) so the replay history survives a crash — "nothing lives in the model" (D76).
#: ``bootstrap`` keeps the RAM store by default (D126); real_runtime wires this path so PRODUCTION
#: persists (the balayage gap: ``SnapshotStore()`` was RAM even here, losing the history at a crash).
_SNAPSHOT_STORE_PATH = Path(__file__).resolve().parents[4] / "knowledge" / ".snapshotstore"

#: The LOCAL services a real start cannot work without — read BEFORE a single weight (D100: refuse,
#: never hang). ONE entry today, because ``bootstrap`` wires exactly one live service: every
#: ``real_runtime`` caller passes through ``connect_qdrant()``, so this check tightens nothing — it
#: only moves an inevitable failure 11 seconds earlier, onto a line that names the gesture. The
#: address is DERIVED from :data:`~mnemosyne.stores.QDRANT_URL`, the same constant the connection
#: uses, so the two cannot drift. Anything wired later that a start truly needs is added HERE, once.
RUNTIME_SERVICES: tuple[ServiceDependency, ...] = (
    ServiceDependency.at(
        QDRANT_URL,
        label="Qdrant — the vector index (the library: ~240,000 passages)",
        without_it="no search, no recall, no ingestion: `make search`, `make agent`,"
        " `make remember` and `make ingest` all stop here",
        remedy="make qdrant-up   (then `make qdrant` to check what it holds)",
    ),
)


def real_runtime(
    *, policy: Policy | None = None, load_brain: bool = True, max_tokens: int | None = None
) -> Runtime:  # pragma: no cover - needs the bricks
    """Cold-start with the REAL bricks wired behind the ports (③ ignition, D126 ``[OPERATOR]``).

    bge-m3 behind :class:`~mnemosyne.ports.embedder.Embedder`, Qdrant behind
    :class:`~mnemosyne.ports.vectorindex.VectorIndex`, tantivy behind
    :class:`~mnemosyne.ports.keywordindex.KeywordIndex` (the hybrid legs), LadybugDB behind
    :class:`~mnemosyne.ports.graphstore.GraphStore` (Moteur A, ③-3a), tree-sitter behind
    :class:`~mnemosyne.ports.structural.StructuralExtractor` (the deterministic pre-pass, ③-3), and
    MLX behind the runner's :class:`~mnemosyne.runtime.runner.GenerationBackend` seam (③-2c), and the
    binary/voice ingestion prise behind :class:`~mnemosyne.ports.source.SourceReader` — a
    :class:`~mnemosyne.ingest.source.MimeDispatchSourceReader` routing documents to Docling (first-class,
    D43), ``audio/`` to WhisperKit (voice, AV1 / D115) and ``image/`` to an OCR repli (③-4b). The
    factories import the installed bricks lazily, so this path is absent in CI and is what the real
    1-click smoke exercises at ignition (``run_smoke_test(real_runtime())``). Everything stays LOCAL
    (D27 / D66).

    ``load_brain`` (default ``True``) gates the generative MLX LLM load: a pure RETRIEVAL caller
    (``make search`` — the frontier read surface, D65) passes ``False`` so recall / search run on the
    embedder + Qdrant + BM25 + reranker alone, without loading the ~GB decoder weights. Every generative
    path leaves it ``True`` (zero regression).

    ``max_tokens`` (default ``None``) passes through to :func:`~.runner_mlx.load_mlx_backend` only
    when given — ``None`` changes NOTHING for a caller who doesn't ask, preserving
    ``runner_mlx._DEFAULT_MAX_TOKENS`` (512) for every existing path. Added 2026-08-08, measured: a
    caller whose generation must reproduce or enumerate a lot of the CONTENT it was given (the
    Intendant's breakdown, which copies verbatim excerpts into JSON — see `atelier.py`) hit that
    512-token ceiling mid-JSON, at 1757 characters, in a real conversation — silently truncated, no
    refusal, no signal. Same failure class already fixed once in ``distill_book.py`` (``max_tokens
    =4096``, *"margin > the schema's max output (otherwise JSON gets truncated)"*) — this is the second
    time the same 512 default has been too small for a JSON-shaped answer, so the override path is now
    a parameter here instead of a copy-pasted local fix per caller."""
    from ..ingest.library_truth import (
        LibraryTruthStore,
    )  # local import: cross-process .md-backed truth (D144)

    # FIRST, before a single brick is imported (field report, 2026-07-21): make the model cache
    # local-first, and SAY every step out loud. That start once sat 30 minutes asleep on a
    # half-closed socket to the HF CDN with every weight already cached, printing nothing — a
    # local-first system let an outbound dependency decide whether it starts, and gave no way to
    # see it. Order is load-bearing: the HF stack snapshots HF_HUB_OFFLINE at IMPORT, so this call
    # must precede the lazy brick imports below (see local_first.enforce_local_first).
    # 5 heavy steps, 4 when the brain is skipped (``make search``) — the total must match what will
    # actually run, or the last line reads "4/5" and a reader waits for a step that never comes.
    reporter = StartupReporter(total=5 if load_brain else 4)
    # On its own statement, not nested inside the reporter call: the structural test that demands
    # BOTH start guards in EVERY Runtime assembler only recognises an unconditional top-level call,
    # and buried in an argument it could not tell this apart from a guard that never runs.
    posture = enforce_local_first()
    reporter.posture(posture)
    # Then, still before the first weight (field report, 2026-07-27): the SAME defect one layer out.
    # ``make search`` spent 11.6 s loading bge-m3 and the reranker, then died on `Connection refused`
    # because a container was stopped — a thirty-line Python traceback for a service that needed one
    # word to restart. A local dependency is one loopback connect away (microseconds), so it is read
    # FIRST and the refusal names the gesture. Placement is the whole point: below the loads, this
    # would print the same truth eleven seconds too late, so a test asserts this call precedes them.
    require_services(RUNTIME_SERVICES, reporter=reporter)
    # C9 — WHICH model, resolved HERE, before the first weight, for exactly the reason the two guards
    # above sit where they do. There is no default any more: an unnamed decode used to silently become
    # Qwen2.5-7B, and now it REFUSES with the basket printed. Placement is load-bearing twice over —
    # below the loads it would refuse eleven seconds late, and inside the ``load_brain`` step it would
    # refuse after bge-m3 and the reranker. The retrieval-only entry (``make search``,
    # ``load_brain=False``) resolves NOTHING: it decodes nothing, so demanding a model there would be a
    # refusal with no cause, and *a false refusal is how a repaired gate earns its own error rate*.
    decode_model = resolve_model_id() if load_brain else None
    # The MIME dispatch table (③-4b): documents → Docling (first-class, D43), voice → WhisperKit (AV1),
    # images → Docling too (it handles images/scans). Zero-trust (D100-3): the MIME is a routing hint,
    # never a barrier — sensitivity is decided by classifying the EXTRACTED text (D101). Docling is also
    # the DEFAULT catch-all, so an unknown-but-document-ish MIME still reaches the first-class reader; a
    # raise from any reader is netted once by ``capture`` (③-4a benne, D85), never here.
    # Figure enrichment is OPT-IN — two switches, off by default (zero regression when both unset). Per BODY
    # figure Docling tries MNEMOSYNE_FIGURES first (vector data-extraction: fast, exact, LOCAL — sujet E),
    # then falls back to MNEMOSYNE_VISION (the LOCAL VLM caption for a genuinely raster figure — sujet 2).
    # Each switch is read in ONE place (figure_extract.py / caption.py).
    with reporter.step("document reader (Docling)"):
        docling = connect_docling(
            captioner=vision_captioner_if_enabled(),
            vector_reader_factory=vector_reader_factory_if_enabled(),
        )
    # Plain-text families (``text/plain`` notes, ``text/markdown``, ``text/csv``) are ALREADY decodable
    # text — routing them to Docling is both waste and a HAZARD: Docling has no text pipeline and treats a
    # bare ``.txt`` as a failed image conversion (ConversionError, the ③-7 diagnostic on ``bm25_ranking.txt``).
    # They go to the utf-8 :class:`PlainTextSourceReader` instead (tolerant, never raises). ``text/html`` is
    # NOT plain text — it still routes to Docling (its longer, un-listed prefix falls through to ``default``),
    # which renders the markup to clean markdown (D43).
    plain_text = PlainTextSourceReader()
    source_reader = MimeDispatchSourceReader(
        {
            "text/plain": plain_text,
            "text/markdown": plain_text,
            "text/csv": plain_text,
            "application/pdf": docling,
            "application/vnd.openxmlformats-officedocument": docling,  # docx / xlsx / pptx
            "application/msword": docling,
            "application/vnd.ms-": docling,  # legacy office (xls / ppt)
            "audio/": connect_whisperkit(),  # voice = one more source (AV1)
            "image/": docling,  # images/scans → Docling; PaddleOCR-VL repli (connect_paddleocr) stays an
            # un-wired seam until the operator measures it a better fit on real scans (③-4b, D43 replis)
        },
        default=docling,
    )
    # The durable trace log for THIS run (③-6b): one append-only JSONL file per process, named like the
    # reshelve journal (``trace_<UTC>.jsonl``) so runs never clobber each other and each is greppable on
    # its own (D6). Microsecond stamp so two ``real_runtime()`` in the same second never share a file.
    # ``open_jsonl_sink`` fail-safes on any I/O error (D111).
    trace_log = (
        _TRACE_LOG_DIR / f"trace_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')}.jsonl"
    )
    # γ (D7 / D98) — a lazy backend per NON-default routable model, so the router's model choice (D7)
    # finally SELECTS the decoder, one big model at a time (D95). Built from the SAME policy table the
    # router reads (``model_routing``); EMPTY today ⇒ a dormant no-op until the bench maps a class to a
    # bench model (a config act, D26) — that model then loads on first use with ZERO code change here.
    # Each bench backend gets the SAME Outlines wrapping as the default; the default model's own id is
    # served by the runner directly (never via the registry), so no second copy of it is ever loaded.
    resolved = policy if policy is not None else load_policy()
    _bench_ids = {mid for mid in resolved.model_routing.values() if mid}
    backends = (
        BackendRegistry(
            {
                mid: (lambda m=mid: connect_outlines(load_mlx_backend(model_id=m)))
                for mid in _bench_ids
            }
        )
        if _bench_ids
        else None
    )
    _endorsements = EndorsementLedger()
    # The three HEAVY loads, hoisted out of the call below for one reason: each is announced BEFORE
    # it starts, so a start that stalls says WHICH weight it stalled on (field report defect 2 — for
    # 30 minutes nothing distinguished "loading a big model" from "asleep on a socket"). The wiring
    # is unchanged; only the moment of evaluation is named. ``load_brain=False`` (the retrieval-only
    # entry, D65) still loads no brain — the step is skipped, not silently empty.
    with reporter.step("embedder bge-m3 (weights, local cache)"):
        embedder = load_bge_m3()
    with reporter.step("reranker bge-reranker-v2-m3 (weights, local cache)"):
        reranker = load_bge_reranker()
    brain: GenerationBackend | None = None
    if load_brain:
        # The step NAMES the model. It used to say "MLX brain" for whichever weight the hard-coded
        # default happened to be, so a 4 GB load and a 19 GB load printed the same line — and the plan
        # that recorded "no model installed" was written by an agent reading exactly that.
        with reporter.step(f"MLX brain {decode_model} (weights, local cache)"):
            backend_kwargs = {"model_id": decode_model}
            if max_tokens is not None:
                backend_kwargs["max_tokens"] = max_tokens
            brain = connect_outlines(load_mlx_backend(**backend_kwargs))
    else:
        reporter.say("MLX brain skipped (RECALL-only entry, load_brain=False)")
    with reporter.step("assembling the runtime + first index (replaying the journal)"):
        runtime = bootstrap(
            policy=resolved,
            backends=backends,
            # cross-process truth: the library's .md mirrors are readable in a FRESH process (raptor / search),
            # not only the ingest that captured them — the in-memory stand-in alone starts empty (D144 / D56).
            # D156 — endorsement is a GESTURE, not a derivation: nothing rebuilds it from raw/, so it
            # gets its own durable journal like Moteur A's human layer (D82). Replayed HERE, at
            # composition, so a fresh process reads the same citable set the operator left behind.
            truth=LibraryTruthStore(
                endorsed=_endorsements.endorsed(),
                # D157 — the DISTILLED layer is a second shelf, readable at recall like the raw one.
                # Wired unconditionally: LibraryManifest.load on a missing file yields an empty manifest,
                # so a repo that has never run `make ingest-distilled` simply sees no fiches (no error).
                shelves=((_DISTILLED_MANIFEST, _DISTILLED_ROOT),),
            ),
            endorsements=_endorsements,
            embedder=embedder,
            # the cross-encoder rerank leg (LOT 5 / D68 stage 6), PAIRED with bge-m3 — both are the frozen
            # BAAI defaults, installed together (ALLUMAGE Phase 2). CoreApi composes it over the base
            # retriever; retrieval stays LOCAL (invariant 1 — the cross-encoder reads passage text).
            reranker=reranker,
            vector=connect_qdrant(),
            keyword=connect_tantivy(),
            graph=connect_ladybug(),
            structural_extractor=connect_treesitter(),
            source_reader=source_reader,
            # OUTBOUND transcript prise (sujet 3): the yt-dlp adapter IF the optional brick is installed, else
            # None (degrade, D126). Wiring it opens nothing — capture_youtube stays deny-by-default at the Guard
            # until the operator allow-lists the host (invariant 5/21); the allow-list is the switch, not this line.
            transcript_fetcher=youtube_fetcher_if_available(),
            # the decode backend behind the Runner (③-2c) WRAPPED by Outlines (③-5b): free-form delegates to
            # MLX, structured decode is grammar-bound at the source (D104) — the runner's ``enforce_grammar``
            # still re-checks every candidate (D100, the code barrier is never delegated). Loaded ONLY when
            # ``load_brain`` (the default) — a pure RETRIEVAL entry (``make search``, the frontier read
            # surface) passes ``load_brain=False`` so the ~GB MLX LLM is never loaded: recall / search never
            # call generation, so that path stays lean (embedder + Qdrant + BM25 + reranker only) and needs no
            # generative weights. None ⇒ the weightless stub decoder (D126). Every generative path (agent,
            # smoke, calibrate, raptor, ingest extraction) keeps the default ⇒ zero regression.
            generation_backend=brain,
            # tier-1 OS isolation (③-5b): the Seatbelt sandbox is the default engine for a tool that runs
            # code (D99). The heavy micro-VM (connect_apple_container) is wired only where UNTRUSTED code runs.
            sandbox=connect_sandbox_runtime(),
            # ③-6b — the outputs / secrets / backup / observability bricks behind the ③-6a couture seams
            # (each sole-importer factory imports its brick lazily; the governance stays in the couture, D100):
            renderer=connect_typst(),  # Typst → the Renderer engine behind the GovernedRenderer (sorties)
            redactor=connect_presidio_redactor(),  # Presidio masking → the renderer's Redactor (re-floored, D100)
            secret_vault=_SECRET_VAULT_PATH,  # the SOPS-encrypted vault (protected zone); absent ⇒ empty broker
            secret_decryptor=connect_sops_age(),  # SOPS+age → the SecretDecryptor (RAISES → couture fail-closes)
            backup_engine=connect_kopia(),  # Kopia → the BackupEngine (off-site zero-knowledge barrier upstream)
            # observability export → BOTH legs (fan_out): the always-on durable JSONL trail (system/logs — the
            # primary greppable append-only log, D6) AND the optional local Langfuse dashboard mirror. Both
            # receive ONLY already-redacted lines (the redaction is upstream in the couture, inv. 12 / 22).
            trace_sink=fan_out(open_jsonl_sink(trace_log), connect_langfuse()),
            pii_sensor=connect_presidio_sensor(),  # Presidio detection → a raise-only semantic pass (MAX, inv. 18)
            hardware_probe=SystemHardwareProbe(
                ram_reader=psutil_ram_reader()
            ),  # real disk (stdlib) + RAM (psutil)
            # ``plugins`` stays deny-by-default (empty): a real MCP / API tool is a PRIVILEGED [OPERATOR] allow-list
            # gesture, never auto-wired — e.g. plugins={"web": connect_mcp_server(catalog.get("web"), cfg)} once
            # the operator sanctions it in the protected catalog (D114-⑤). An un-wired tool is refused fail-closed.
            # TRUSTED (the operator's gesture 2026-07-17, D148 / D69). `make calibrate` cleared the GROUNDEDNESS
            # bar over the real MLX extractor on the real corpus (grounded 1.000 vs 0.95, yield 1.933 vs
            # 1.00, 58 triples / 30 passages) — so its facts now auto-file to the graph rather than landing
            # as plan-B `.md` notes. The bar measures INVENTION, not agreement with a labeller's framing:
            # an entity absent from the passage is one the model brought from elsewhere (the failure the
            # un-prompted extractor showed — 6 recited triples vs 1 read). WHAT THIS DOES NOT PROVE (D148
            # residues, so the trust is eyes-open, not blind): groundedness is NECESSARY not sufficient — a
            # scramble of the passage's own entity-words stays grounded, and the PREDICATE is not anchored
            # at all, so a fabricated relation between two real entities would pass here (the real extractor
            # was separately measured faithful on its predicates; this gate does not re-prove it per-fact).
            # The deterministic structural pre-pass is unaffected (no golden gate). This is the meaningful
            # graph site: real_runtime wires BOTH the graph store and the MLX extractor. (library_run does
            # NOT wire the graph engine, so its own flag stays False — flipping it would declare a trust
            # that path cannot act on.)
            graph_extraction_trusted=True,
            # Source ingestion TRUSTED (③-4): the fidelity golden-set (:mod:`~mnemosyne.ingest.golden`)
            # cleared the bar (score_fidelity F1=0.996 vs 0.70, real corpus incl. OCR'd scans) and the
            # operator flipped this 2026-07-09. Extractions are no longer auto-flagged low-fidelity. Provisional:
            # the fidelity golden skews to clean text + scans; hard cases (tables/equations/dense PDFs)
            # are watched at real use — the D85 benne still preserves raw on any per-doc low-fidelity read.
            source_extraction_trusted=True,
            # the human-layer net (D82): the operator's validations / invalidations are journaled to durable disk
            # BEFORE they reach RAM and replayed at cold start — the one irreversible-loss window, closed.
            human_journal=HumanLayerJournal(_HUMAN_LAYER_PATH),
            # D159 — the real, disk-backed wall log: every refusal a production run hits becomes
            # visible via `make murs` instead of silently justifying a workaround.
            walls=WallLedger(_WALLS_PATH),
            # the proposals ledger (item 2): a `make remember` LEARNING is non-rebuildable, so it persists here
            # (write-ahead) to survive its short-lived process and rejoin the validation queue at cold start.
            proposals_ledger=ProposalsLedger(_PROPOSALS_PATH),
            # the replayable snapshot store persists on disk in PRODUCTION (D76): SnapshotStore() was RAM
            # even here, so a crash lost the replay history — now under knowledge/.snapshotstore, bounded by
            # the protected retention (snapshot_retain_last, D78 / from_policy).
            snapshot_base_path=_SNAPSHOT_STORE_PATH,
            # RAPTOR summary tree (Ch.5 / RAG niveau 2): the on-disk store (survives a crash, like the
            # human-layer journal / snapshot store above) + the REAL guarded summarizer — wired
            # unconditionally (no separate opt-in switch, unlike figure captioning's MNEMOSYNE_VISION):
            # the expensive part is running `make raptor-build` itself, a deliberate, separate act.
            raptor=RaptorStore(base_path=_RAPTOR_STORE_PATH),
            enable_raptor_summarizer=True,
        )
    return runtime
