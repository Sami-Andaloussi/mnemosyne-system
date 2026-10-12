"""CoreApi (D119) — the headless facade; every frontier goes through the Guard, fail-closed.

The client-facing surface of Mnémosyne's core. It federates the subsystems built in LOT 3-6
(the Guard, ingestion, stores, runtime, production) behind seven thin surfaces (D119 a-g) and
enforces ONE structural rule: **a frontier is only ever crossed through the Guard** (D89). The
single mediation point is :meth:`CoreApi._guarded`, which mints a
:class:`~mnemosyne.ports.guard.Grant` or fails closed (``GuardDenied`` / ``EscalateToHuman``);
the only outbound methods — :meth:`export` (canal A/B) and :meth:`register_tool` (wiring a tool /
MCP server) — route through it, so the facade cannot exfiltrate or self-wire behind the Guard's
back. Everything else is intra-bubble read/orchestration that never leaves the machine.

The methods are HOOKS, not finished screens (D119: pose the API at 100 %, render later at Phase 1
bis). Concrete projects, proposals and tools are ``contenu`` created just-in-time at usage (D98);
what this lot graves is the ``contenant`` — the surface and its Guard-mediation.

Decisions: D119 (surfaces, headless, talk-to-the-Guard) · D89 (Guard mediation) · D101 (capture
classifies) · D65 (search routing / fusion) · D79 (promotion gate) · D80 (kill-switch) · D86
(costs) · D114 / D102 (tool wiring is a privileged human act) · D92 / D100 (propose, never
impose). Code & docstrings English (D117); ``public`` / ``perso`` / ``sensible`` stay French.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass

from ..ingest.benne import Benne, DuplicateFlag
from ..ingest.router import ContentNature, Engine, QueryKind, fuse, route_ingest, route_read
from ..ingest.youtube import parse_youtube_ref, transcript_to_markdown
from ..ports import (
    Bubble,
    CloisonnementError,
    DocId,
    DocRole,
    Domain,
    Effect,
    Envelope,
    EscalateToHuman,
    Fact,
    GovernanceLabel,
    GrammarConstraint,
    Grant,
    GuardDenied,
    GuardRequest,
    HealthReport,
    MonotonicityError,
    RenderDestination,
    RestoreReport,
    SearchHit,
    Sensitivity,
    Source,
    TraceId,
    TriggerKind,
    WorkId,
    WorkItem,
)
from ..production import (
    MNEMOSYNE_IDENTITY,
    ActiveSkillsSource,
    AgentSurfacesSource,
    AuthorizedToolsSource,
    AutonomousProposer,
    Declassification,
    DeclassificationAudit,
    Deliverable,
    Distillateur,
    DistillationInput,
    DistilledDoc,
    Draft,
    Fiche,
    FicheType,
    IntakeBacklogReview,
    LivingQueueReview,
    ProductionWorkflow,
    CandidatSansPanneReview,
    MoissonEnAttenteReview,
    AccordChiffreReview,
    BesoinsOuvertsReview,
    SitesDeSortieReview,
    DeriveReview,
    MoissonDueReview,
    ParentheseReview,
    ProposalSource,
    ReceptacleSink,
    RefinementResult,
    DocumentsOrphelinsReview,
    RepoTidyReview,
    Rubric,
    RunnerCritic,
    RunnerGenerator,
    SelfModel,
    ProposalQueueReview,
    SignalementReview,
    VeilleReview,
    facts_to_fiches,
    learning_fiche,
    note_fiche,
    refine,
)
from ..runtime import (
    CalibrationReport,
    DrainReport,
    HealthMonitor,
    KopiaBackup,
    OrchestrationEngine,
    Runtime,
    calibrate_floor_runtime,
    calibrate_runtime,
)
from ..stores import FloorScore, Retriever, is_raptor_summary, wrap_reranked
from ..stores.governed_read import READ_POOL, may_read, pack_passage, pack_summary

#: The bubble the human operator (at the UI) acts from — subject of privileged acts.
_OPERATOR = Bubble("operator")

#: The canonical YouTube host declared as the egress ``target`` of a :meth:`CoreApi.capture_youtube` fetch.
#: The Guard rules its ``EXTERNAL_OUTPUT`` grant against the policy allow-list (deny-by-default, inv. 5/21):
#: this host must be allow-listed in ``policy.toml`` for a fetch to be authorized — the switch is the operator's.
_YOUTUBE_EGRESS_HOST = "www.youtube.com"

#: The descriptors naming the real background workflows (D93) in the engine's registry: the managed
#: hygiene job that proves the backup restores (D110), and the autonomous proposer (soul ⑤) that
#: deposits unbidden proposals in the meta receptacle (D119-f). More are registered here as real
#: background needs arrive.
_WF_VERIFY_RESTORE = "verify_restore"
_WF_AUTONOMOUS_PROPOSER = "autonomous_proposer"

#: The protected-zone DEPTH ceiling a governed model LOOP may not exceed (D100 structural, anti-runaway
#: D78 / invariant 16). ``produce``'s generator↔critic loop shares the agent loop's depth bound for now —
#: a caller's ``max_rounds`` is CLAMPED to it, so no caller can buy more model rounds than SE4 allows; a
#: dedicated ``refine_max_rounds`` is a later policy addition (when the config zone is next opened).
_REFINE_DEPTH_BOUND = "agent_max_turns"

#: The protected-zone BREADTH ceiling on how many proposals ONE autonomous pass may deposit (soul ⑤,
#: anti-noise / anti-runaway, D78 / invariant 16).
#:
#: **TWO NAMES, AND THE ORDER IS THE DOCTRINE.** This module long BORROWED ``agent_fanout``,
#: itself writing that a dedicated key would come *"when the config zone is next opened"*. An
#: isolated adversarial review (D75/D159) measured what the borrowing costs: ``agent_fanout`` carries the
#: name and the comment of an ANTI-RUNAWAY guard (inv. 7), and raising it to widen a
#: DISPLAY value **pre-authorizes a real agent fan-out** the day someone wires the bound to its own
#: name. *A value shared by two masters cannot be tuned for just one.*
_PROPOSER_FANOUT_BOUND = "proposer_fanout"

#: The historical borrowing, kept as a DECLARED FALLBACK — never as a silent default.
#: It exists so this code runs BEFORE as well as AFTER the dedicated key is written into the
#: protected zone: a fix that requires a human gesture just to avoid breaking is a fix that breaks.
#: :meth:`Policy.bound`'s fail-closed is INTACT — if NEITHER key exists, the second call
#: raises, and *an unbounded resource stays a bug, never a silent defect*.
_PROPOSER_FANOUT_REPLI = "agent_fanout"


def _plafond_du_proposeur(policy: object) -> tuple[int, str]:
    """One pass's ceiling, **and the NAME of the key actually read**.

    **THE NAME TRAVELS WITH THE VALUE, AND THIS IS NOT DECORATIVE.** An isolated adversarial
    review measured that the truncation notice published `agent_fanout` **hardcoded**: with
    `proposer_fanout = 4` in effect, the tick said *"the `agent_fanout` (4) bound stopped this
    pass"* — **the wrong key AND a value that key does not carry**. This is the one sentence
    whose written role is to name the wall to move; it sent the reader to the wrong line of

    Returning a **pair** rather than an integer is not a style detail: it is what makes it
    impossible for a caller to read the value without knowing where it came from. A
    `policy.bound("…")` hardcoded back at the call site no longer compiles against this signature."""
    try:
        return policy.bound(_PROPOSER_FANOUT_BOUND), _PROPOSER_FANOUT_BOUND  # type: ignore[attr-defined]
    except KeyError:
        return policy.bound(_PROPOSER_FANOUT_REPLI), _PROPOSER_FANOUT_REPLI  # type: ignore[attr-defined]


#: The write nature (D57) a captured living fact carries → the fiche type it is proposed as (D58).
#: Only the two living natures reach here (a DOCUMENT routes to Moteur B, never to a fiche); the
#: fail-closed default is FACT, which always needs an explicit human validation (D59-5).
_FTYPE_FOR_NATURE = {
    ContentNature.BEHAVIOUR: FicheType.PREFERENCE,
    ContentNature.OPINION: FicheType.OPINION,
}


def _fiche_frame(fiche: Fiche) -> Envelope[str]:
    """Render a VALIDATED living fiche as a fusion frame (D65) — its statements, its own label.

    The frame carries the fiche's governance label (bubble + sensitivity), so the bubble-scoped,
    sensible-local guarantees of :func:`~mnemosyne.ingest.router.fuse` bite on it exactly as on a
    documentary fact. Statements are joined in a stable order so the frame is deterministic."""
    return Envelope(payload=" ; ".join(sorted(fiche.content)), label=fiche.label)


def _living_capture_suffix(
    *, routed: bool, trusted: bool, model_facts: int, structural: int, failed: bool, proposed: int
) -> str:
    """The honest Moteur A tail of a capture receipt (F3): how the living side was handled (③-3).

    Composes two parts. The DETERMINISTIC structural pre-pass (tree-sitter) is named whenever it
    produced facts — it is always filed, independent of route/trust (D125-B9). The LLM leg is named
    only on a living route: plan-B note on failure or below the golden-set bar (no graph imposed,
    D58), the filed facts when trusted (D120), or an honest abstention when the stub produced
    nothing. With neither (a pure DOCUMENT capture, no structural), the tail is empty."""
    parts: list[str] = []
    if structural:
        parts.append(f"{structural} deterministic structural fact(s) (tree-sitter, always filed)")
    if routed:
        if failed:
            parts.append("LLM extraction FAILED — datum saved to Moteur B, plan-B `.md` note")
        elif not trusted:
            parts.append(
                "LLM extraction below the golden-set bar — plan-B `.md` note, no graph imposed"
            )
        elif model_facts:
            parts.append(f"{model_facts} LLM fact(s) filed")
        else:
            parts.append("LLM extraction routed but the model abstained (0 fact)")
    if not parts:
        return ""
    return (
        f" — Moteur A: {'; '.join(parts)} → {proposed} fiche(s) awaiting your validation "
        "in pending_fiches() (③-3 / D100 / D59)"
    )


def _source_capture_note(
    *, ref: str, chars: int, trusted: bool, failed: bool, dup: DuplicateFlag | None
) -> str:
    """The honest source-ingestion tail of a capture receipt (F3): how a raw source was read (③-4).

    Names the reader's fidelity disposition — a FAILED extraction (the reader raised; raw preserved
    for re-extraction), a below-the-golden-set-bar LOW-FIDELITY flag (D125-B6, never silently
    trusted), or a clean extraction — plus a non-destructive near-duplicate FLAG the human arbitrates
    (D85). The raw source is ALWAYS preserved in the benne (truth-first for binary), so no reading
    outcome is ever a lost datum."""
    if failed:
        fidelity = "extraction FAILED (reader raised)"
    elif not trusted:
        fidelity = "LOW-FIDELITY (below the ingestion golden-set bar, D125-B6)"
    else:
        fidelity = "fidelity OK"
    parts = [
        f"source {ref!r} → {chars} char(s) extracted, {fidelity}; raw preserved in benne (D85)"
    ]
    if dup is not None:
        parts.append(
            f"near-duplicate of {dup.similar_to!r} (similarity {dup.similarity:.0%}) — FLAGGED "
            "non-destructively, you arbitrate (D85)"
        )
    return " — " + "; ".join(parts)


# --------------------------------------------------------------------------- #
# DTOs — the hooks return plain, immutable views (headless: no rendering here) #
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class CaptureReceipt:
    """What a capture produced: the doc id, its classified sensitivity, the engine(s) routed."""

    doc: DocId
    sensitivity: Sensitivity
    engines: tuple[str, ...]
    reason: str


@dataclass(frozen=True, slots=True)
class YouTubeCaptureReceipt:
    """What a YouTube capture produced (sujet 3 / D119-a): the memory receipt + the video's provenance.

    ``capture`` is the underlying :class:`CaptureReceipt` when a transcript was memorized, or ``None`` when
    the video had no usable subtitles (nothing worth memorizing — honest emptiness, F3, never a blank
    datum). The provenance fields describe the source either way; ``auto_generated`` flags a YouTube ASR
    transcript (non-verbatim, marked in the ``.md`` and stripped from the verbatim floor at distillation, C2)."""

    capture: CaptureReceipt | None
    video_id: str
    title: str
    language: str
    auto_generated: bool


@dataclass(frozen=True, slots=True)
class SearchView:
    """A search result surface: the hits (or a low-recall admission) and the read routing (D65)."""

    hits: tuple[tuple[DocId, float], ...]
    admitted_low_recall: bool
    engines: tuple[str, ...]
    reason: str


@dataclass(frozen=True, slots=True)
class RecallView:
    """A read-FUSION surface (D65 / D137): Moteur A living ⊕ Moteur B (endorsed ⊕ working), side by side.

    Three buckets kept SEPARATE — A never overwrites B (D65 / D60), and Moteur B is split by epistemic
    role (D137): ``facts`` are ENDORSED sources (base-de-connaissances) that may be cited as truth,
    ``working_material`` is the operator's own unverified production (matière-de-travail) — returned so they can
    enumerate it, but NEVER presented as a source of truth. All are bubble-scoped (a foreign-bubble
    item never fuses, invariant 3), and ``sensitivity`` is the max over all three (sensible-local
    carried downstream, D27). Two structural guarantees: nothing from the graph reaches ``frame``
    unless projected into a fiche AND VALIDATED (the D100 net); and nothing reaches ``facts`` unless a
    document was explicitly ENDORSED (the D137 net) — so neither an unvalidated extraction nor an
    unendorsed draft can ever surface as authority."""

    frame: tuple[Envelope[str], ...]  # Moteur A — VALIDATED living fiches (bubble-scoped)
    facts: tuple[Envelope[str], ...]  # Moteur B — ENDORSED sources (base-de-connaissances), citable
    working_material: tuple[
        Envelope[str], ...
    ]  # Moteur B — matière-de-travail: unverified, never a source
    sensitivity: Sensitivity
    engines: tuple[str, ...]
    admitted_low_recall: bool
    reason: str


@dataclass(frozen=True, slots=True)
class GovernanceView:
    """A read-only view of the protected zone (SE4): bubbles, egress, bounds, quotas (D112/D86)."""

    profile: str
    bubbles: tuple[Bubble, ...]
    egress_allowlist: tuple[str, ...]
    bounds: Mapping[str, int]
    quotas: Mapping[str, float]


@dataclass(frozen=True, slots=True)
class Proposal:
    """A meta/transverse proposal landing in the receptacle (D119-f) — PROPOSED, never imposed.

    Emitted by an already-decided behaviour (aggregator → living docs, living-memory lesson,
    "Ré-évaluation continue"); it carries NO authority until the operator reviews it (D92 / D100)."""

    id: str
    source: str
    summary: str
    reviewed: bool = False
    accepted: bool = False
    comment: str = ""


# --------------------------------------------------------------------------- #
# The facade                                                                   #
# --------------------------------------------------------------------------- #
class CoreApi:
    """The headless core facade (D119): seven surfaces, every frontier through the Guard (D89).

    Construct over an assembled :class:`~mnemosyne.runtime.Runtime` (D94). Holds only what the
    surfaces need — the Guard, a retriever, the production workflow, a health monitor, a backup,
    and the meta inbox — and never a direct handle a UI could use to bypass the Guard on a
    frontier."""

    __slots__ = (
        "_rt",
        "_guard",
        "_retriever",
        "_memory",
        "_benne",
        "_workflow",
        "_health",
        "_backup",
        "_engine",
        "_operator",
        "_inbox",
        "_seq",
        "_intake_backlog_count",
        "_unsurveyed_count",
        "_repo_cruft_count",
        "_signalement_count",
        "_oldest_signalement_age_days",
        "_proposal_count",
        "_parenthese_count",
        "_documents_orphelins_count",
        "_candidats_sans_panne_resume",
        "_moissons_en_attente_resume",
        "_sites_de_sortie_resume",
        "_accord_chiffre_compte",
        "_besoins_ouverts_compte",
        "_derive_resume",
        "_moisson_due_resume",
    )

    def __init__(
        self,
        runtime: Runtime,
        *,
        operator: Bubble = _OPERATOR,
        intake_backlog_count: Callable[[], int] | None = None,
        unsurveyed_count: Callable[[], int] | None = None,
        repo_cruft_count: Callable[[], int] | None = None,
        documents_orphelins_count: Callable[[], int] | None = None,
        signalement_count: Callable[[], int] | None = None,
        oldest_signalement_age_days: Callable[[], int | None] | None = None,
        proposal_count: Callable[[], int] | None = None,
        parenthese_count: Callable[[], int] | None = None,
        moisson_due_resume: Callable[[], str | None] | None = None,
        candidats_sans_panne_resume: Callable[[], str | None] | None = None,
        moissons_en_attente_resume: Callable[[], str | None] | None = None,
        sites_de_sortie_resume: Callable[[], str | None] | None = None,
        accord_chiffre_compte: Callable[[], int | None] | None = None,
        besoins_ouverts_compte: Callable[[], int | None] | None = None,
        derive_resume: Callable[[], str | None] | None = None,
    ) -> None:
        self._rt = runtime
        self._guard = runtime.guard
        # Q2 autonomy (optional, D111-style): a count of un-homed sources in the raw-intake sas. Wired
        # at the real composition root (which knows knowledge/); left None here, the proposer runs with
        # only the living-queue source, exactly as before (zero regression). See ingest.intake_backlog_count.
        self._intake_backlog_count = intake_backlog_count
        # Q5 autonomy (optional, D111-style): a count of distilled fiches NOT yet surveyed by a veille
        # pass. Wired at the real composition root (which knows knowledge/distilled + the ledger); left
        # None here, the proposer skips the veille source (zero regression). See production.veille_ledger.
        self._unsurveyed_count = unsurveyed_count
        # Item 3 (propose-to-automate nerve): a count of CLEAR repo cruft the rangement skill automates.
        # Wired at the real composition root (which knows the repo root); left None here, the proposer skips
        # the repo-tidy source (zero regression). A COUNT, never a path. See production.rangement.clear_cruft_count.
        self._repo_cruft_count = repo_cruft_count
        # A3: a count of tracked documents NOTHING cites any more. Wired at the real composition
        # root (which knows the repo root); left None here, the proposer skips the source (zero
        # regression). A COUNT, never a path. See production.documents.compte_orphelins.
        self._documents_orphelins_count = documents_orphelins_count
        # The field-report channel: a count of signalements a PROJECT session filed against Mnemosyne
        # and that no Mnemosyne session has drained yet. Wired at the real composition root (which knows
        # docs/signalements); left None here, the proposer skips the source (zero regression). A COUNT,
        # never a title nor a path. See production.signalements.open_signalement_count.
        self._signalement_count = signalement_count
        # The AGE of the oldest report, alongside the count. Measured on 2026-09-08: the count ALONE
        # was already published at every startup and 12 reports had stayed open for 27 days --
        # a count states the SIZE of a queue, never its STASIS. Optional: if absent, the line
        # degrades to its earlier form rather than staying silent.
        self._oldest_signalement_age_days = oldest_signalement_age_days
        # The RETURN path of the `proposals` surface: a count of inert drafts the veille / an agent
        # deposited and that nobody has reviewed. Wired at the real composition root (which knows
        # knowledge/proposals); left None here, the proposer skips the source (zero regression). A
        # COUNT, never a title nor a path — and here that matters most: a draft's body is mined from
        # the operator's own library. See production.proposals.open_proposal_count.
        self._proposal_count = proposal_count
        # C8-c: a count of parentheses still OPEN beside a plan — detours that still owe it a return.
        # Wired at the real composition root (which knows docs/parentheses); left None here, the
        # proposer skips the source (zero regression). A COUNT, never a title nor the plan it departs
        # from — a detour is opened from inside whatever was being worked, and its title can name it.
        # See production.parentheses.open_parenthese_count.
        self._parenthese_count = parenthese_count
        # I2 — the ONE source that NAMES instead of counting, and the reason is mechanical: what
        # crosses is a plan-arc IDENTIFIER (a plan file path, the same meta `make plans` already
        # prints), never an item title, and the list is BOUNDED at three names + a count. Wired at
        # the real composition root (which knows the plan trees); left None here, the proposer
        # skips the source (zero regression). See production.moisson_due.
        self._moisson_due_resume = moisson_due_resume
        self._candidats_sans_panne_resume = candidats_sans_panne_resume
        self._moissons_en_attente_resume = moissons_en_attente_resume
        self._sites_de_sortie_resume = sites_de_sortie_resume
        self._accord_chiffre_compte = accord_chiffre_compte
        self._besoins_ouverts_compte = besoins_ouverts_compte
        self._derive_resume = derive_resume
        # D139 — the per-domain recall floor is read from the protected policy zone; empty by
        # default (no domain calibrated yet), which resolves every domain to the SAME embedder
        # floor as before D139 (retro-compatible).
        # The base hybrid retriever (dense ⊕ BM25, RRF) with its per-domain recall floor (D139).
        base_retriever = Retriever.from_policy(
            runtime.policy, runtime.vector, runtime.embedder, keyword=runtime.keyword
        )
        # Rerank leg (LOT 5 / D68 / D61 stage 6): compose the cross-encoder OVER the base when one is
        # wired (real_runtime), else use the base bare — byte-identical to pre-LOT-5 (zero regression,
        # D126). ONE composer (wrap_reranked, single-source), so search() and recall() read the SAME
        # reranked surface with no call-site change. The resolver reads passage / synopsis text LOCALLY
        # for SCORING only (invariant 1, text never leaves); the rerank reorders an already-admitted,
        # in-partition shortlist — it never re-opens invariant 14, nor widens what may_read admits
        # (the bubble / domain frontiers, invariants 3 / 4, stay downstream, unchanged).
        self._retriever = wrap_reranked(
            base_retriever, runtime.reranker, truth=runtime.truth, raptor=runtime.raptor
        )
        self._memory = (
            runtime.living_memory
        )  # Moteur A's fiche pipeline (D58-D60), read at recall()
        # The raw-intake benne (D85): bounded (invariant 16) + non-destructive dedup FLAG. It is the
        # truth-first landing zone for BINARY sources (③-4) — a poor / failed OCR keeps its raw source
        # here, re-extractable, exactly as Moteur B preserves the datum for the LLM extractor.
        self._benne = Benne.from_policy(runtime.policy)
        self._workflow = ProductionWorkflow()
        # health (D111): the real hardware probe (disk/RAM/thermal) comes from the runtime when wired at
        # ③-6b (real_runtime); a hand-built / skeleton Runtime leaves it None → HealthMonitor's healthy stub.
        self._health = HealthMonitor(
            observability=runtime.observability, hardware=runtime.hardware_probe
        )
        # the backup is assembled in bootstrap (D110 / ③-6) so real_runtime can inject the real Kopia
        # engine behind the off-site barrier; a hand-built Runtime falls back to a stub-engine backup.
        self._backup = runtime.backup if runtime.backup is not None else KopiaBackup()
        # the orchestration engine (D93): the loop that DRIVES the scheduler substrate — submit a
        # background workflow, dispatch it under the bound (invariants 16 / 26), run it, react by
        # gravity (complete / suspend / fail). The registry is fixed here; the FIRST real workflow is
        # verify_restore (D110), run as MANAGED background work rather than a blocking call — the
        # canary run_agent stays a direct interactive run, the engine only handles background work.
        # D111: the engine reads this health probe once per drain tick and DEFERS work fail-safe when
        # the signal degrades (a full disk defers everything; a downed local runner would defer the
        # non-public, never clouding it). ``self._health.report`` senses the real disk (hardware probe
        # above); the runner-liveness / stores-reachability signals ride with the supervision daemon
        # (D93-④), so the disk-critical branch is LIVE now and the rest is wired-and-tested-ready.
        self._engine = OrchestrationEngine(
            runtime.scheduler,
            workflows={
                _WF_VERIFY_RESTORE: self._workflow_verify_restore,
                _WF_AUTONOMOUS_PROPOSER: self._workflow_autonomous_proposer,
            },
            health=self._health.report,
        )
        self._operator = operator
        self._inbox: list[Proposal] = []
        self._seq = 0

    # -- the single frontier mediation point (D89 / D119) -----------------------------
    def _guarded(
        self,
        effect: Effect,
        *,
        subject: Bubble,
        inputs: tuple[GovernanceLabel, ...],
        target: str | None,
        descriptor: str,
        payload: str | None = None,
    ) -> Grant:
        """Mint a Guard capability for one frontier effect, or fail closed (D89).

        The ONLY way the facade crosses a frontier: it builds a
        :class:`~mnemosyne.ports.guard.GuardRequest` and asks the Guard to grant it — raising
        ``GuardDenied`` on refusal and ``EscalateToHuman`` when a human gesture is required
        (canal B, a life-action, a policy write). No API method reaches egress, a tool, or a
        model any other way — so the UI structurally cannot bypass the Guard (D119)."""
        request = GuardRequest(
            effect=effect,
            subject=subject,
            inputs=inputs,
            target=target,
            descriptor=descriptor,
            payload=payload,
        )
        return self._guard.grant(request)

    # -- (a) capture / intake (D119-a / D101) -----------------------------------------
    def capture(
        self,
        text: str | None = None,
        *,
        source: Source | None = None,
        bubble: Bubble,
        domain_signal: Sensitivity | None = None,
        public_provenance: bool = False,
        nature: ContentNature = ContentNature.DOCUMENT,
        doc: DocId | None = None,
        language: str | None = None,
        domains: frozenset[Domain] = frozenset(),
    ) -> CaptureReceipt:
        """Capture into ``bubble`` — from a raw ``source`` (③-4) or already-extracted ``text``.

        Exactly ONE of ``text`` / ``source`` is given (else ``ValueError`` — never a silent guess,
        D55 single door). A raw source (document / image / voice, D125-B5) is first turned into text
        by the :class:`~mnemosyne.ports.source.SourceReader` prise (Docling / WhisperKit behind it,
        ③-4b), LOCAL and zero-trust (its bytes and MIME are untrusted data, D100-3); the raw source is
        PRESERVED in the benne (D85), bounded fail-closed (invariant 16), so a poor or failed OCR is
        never a lost datum — re-extractable later by a better engine. From there the path is identical
        to a text capture: the sensitivity is the classifier's MAX verdict (a model can only raise it,
        D100); the datum is written truth-first through the journal (D105); living facts are filed
        under the D100 net. Local end to end — an intra-bubble ingest, not a frontier, so it needs no
        egress grant; the semantic pass and the extractor are already Guard-mediated (D89). When the
        caller declares a source ``language`` (code ingestion), the deterministic tree-sitter pre-pass
        (D125-B9) also files structural facts, upstream of the LLM extractor (③-3). Honest receipt
        (F3): the fidelity of a source extraction, its near-duplicate flag, and Moteur A's disposition.

        Optional topical ``domains`` (D72 / invariant 4) are stamped onto the datum's label — the shelf
        domain of a source (finance / computer-science / machine-learning), so BOTH a per-domain recall
        floor (D139) and the domain cloisonnement frontier key on a FACT of the datum, never a guess.
        Empty by default (a domain-less datum skips the domain frontier — unchanged behaviour); a
        NON-empty domain is readable ONLY by a bubble that DECLARES it in the policy zone (D72), so
        tagging and declaring move in lockstep — an undeclared domain WITHHOLDS the hit, never leaks it
        (fail-closed, the D100 net at the domain grain).

        ``public_provenance`` (default ``False``) is the standing human declassification (D100-2 / D107)
        for public-source zones: set ONLY by the two provenance doors — the library-book ingest and
        :meth:`capture_youtube` — it labels the datum ``public`` authoritatively, bypassing the PII floor
        that false-positives on published text. No other caller sets it, so distilled fiches, chats and
        personal data keep the fail-safe ``sensible`` default."""
        if (text is None) == (source is None):
            raise ValueError("capture needs exactly one of `text` or `source` (D55 single door)")
        target_doc = doc if doc is not None else self._next_doc("capture")
        # (③-4) A raw source becomes text through the reader prise, NETTED: a raising reader degrades
        # to an empty extraction, never a crash — the raw bytes are preserved in the benne just below,
        # so the datum survives to be re-extracted by a better engine (D85, truth-first for binary).
        source_failed = False
        duplicate: DuplicateFlag | None = None
        if source is not None:
            try:
                text = self._rt.source_reader.read(source)
            except Exception:  # noqa: BLE001 - a raising reader is degraded; raw preserved, never lost
                text, source_failed = "", True
            if not isinstance(
                text, str
            ):  # a reader returning None / bytes VIOLATES the port contract
                text, source_failed = (
                    "",
                    True,
                )  # — degrade (raw preserved), never crash classify() (③-4b)
        classification = self._rt.classifier.classify(
            text, domain_signal=domain_signal, public_provenance=public_provenance
        )
        label = GovernanceLabel(
            sensitivity=classification.sensitivity, bubble=bubble, domains=domains
        )
        envelope = Envelope(payload=text, label=label)
        if source is not None:
            # Preserve the raw source truth-first (D85): bounded intake fail-closed (invariant 16 — a
            # big medium cannot swamp the queue) + a non-destructive near-duplicate FLAG (never an
            # auto-drop; the operator arbitrates). Dedup keys on the extracted text, so two scans of the same
            # document are flagged even when their bytes differ.
            _, duplicate = self._benne.intake(target_doc, envelope, source=source)
        route = route_ingest(label, nature=nature)
        # Moteur A pre-pass (③-3 / D125-B9): DETERMINISTIC structural facts from code (tree-sitter),
        # upstream of and complementing the LLM extractor. They are a syntactic fact of the source, not
        # a model opinion, so — unlike the LLM's — they carry NO golden-set gate and are ALWAYS filed;
        # like every fact they reach an answer ONLY through a VALIDATED fiche (D100). Fires only when
        # the caller declares a source ``language`` (code ingestion); generic text capture passes none,
        # so the pre-pass is inert. With the stub no fact is produced (D126). UNDER THE SAME NET as the
        # LLM leg: ANY raise from the parser degrades to zero structural fact, never a lost datum (the
        # real tree-sitter colle is machine-only, confronted with the API only at ignition — the 3a
        # debt is closed on THIS leg too, not just the LLM's).
        structural: tuple[Fact, ...] = ()
        if language is not None:
            try:
                structural = self._rt.structural_extractor.extract_structural(
                    text, language=language
                )
            except Exception:  # noqa: BLE001 - a raising parser is degraded, never a lost datum
                structural = ()
        # Moteur A (③-3c): the LLM fact extractor, UNDER A NET. It runs BEFORE integration, so (1) ANY
        # raise is caught here and the datum still lands truth-first in Moteur B (the 3a debt); and (2)
        # the graph is AUTO-imposed only when extraction is TRUSTED (golden-set F1 ≥ bar) — below the
        # bar, or on failure, plan B applies (no graph, a readable ``.md`` note; D58 "no auto-imposed
        # graph"). With the stub the extractor ABSTAINS (no fact, no raise).
        model_facts: tuple[Fact, ...] = ()
        extraction_failed = False
        if Engine.LIVING in route.engines:
            try:
                model_facts = self._rt.fact_extractor.extract(envelope)
            except Exception:  # noqa: BLE001 - ANY extractor failure degrades to plan B, never
                extraction_failed = True  # loses the datum: it still lands truth-first in Moteur B
        trusted = self._rt.graph_extraction_trusted and not extraction_failed
        # Truth-first (D105): integrate ALWAYS — deterministic structural facts + the model facts only
        # when trusted (else the model side is withheld from the graph, plan B).
        model_graph = model_facts if trusted else ()
        self._rt.journal.integrate(target_doc, envelope, facts=(*structural, *model_graph))
        # Project to the D100 gate: structural facts → FACT fiches (deterministic, always); the living
        # model facts → their nature's fiche type when trusted, else a single plan-B ``.md`` NOTE. All
        # land PROPOSED, inert until validated (:meth:`validate_fiche`) — NOTHING reaches an answer
        # without the gesture (D59 / D100); the store's monotone, bubble-safe :meth:`~LivingMemory.propose`
        # is the backstop (a projection that would DECLASSIFY or CROSS bubbles is refused, never a crash).
        # Structural facts get the DISJOINT ``"structural"`` id namespace (a code identifier can never
        # collide with — nor clobber — the personal/LLM fiche of the same subject); the LLM leg keeps
        # the default ``"subject"`` space. So the two sources are always distinct fiches (D120).
        ftype = _FTYPE_FOR_NATURE.get(nature, FicheType.FACT)
        candidates: list[Fiche] = list(
            facts_to_fiches(
                structural,
                envelope.label,
                ftype=FicheType.FACT,
                current=self._memory.current,
                kind="structural",
            )
        )
        if Engine.LIVING in route.engines:
            if trusted:
                candidates += facts_to_fiches(
                    model_facts, envelope.label, ftype=ftype, current=self._memory.current
                )
            else:
                candidates.append(note_fiche(text, envelope.label, doc=target_doc))
        for fiche in candidates:
            try:
                self._memory.propose(fiche)
            except (MonotonicityError, CloisonnementError):
                pass  # the store's barrier held (D100-2 / invariant 3) — never crash a capture
        # Honest count (F3): only DISTINCT fiches ACTUALLY awaiting validation — a re-capture that
        # stayed VALIDATED (identity fusion) or hit a closed id is not "awaiting", and a shared id
        # counts once (a set intersection, never a per-candidate double-count).
        pending_ids = {f.id for f in self._memory.proposed()}
        proposed = len({f.id for f in candidates} & pending_ids)
        # Honesty (D119 / F3): B always; A when ANY fact (structural or trusted model) reached the graph.
        written = {Engine.DOCUMENTARY}
        if structural or model_graph:
            written.add(Engine.LIVING)
        source_note = ""
        if source is not None:
            source_note = _source_capture_note(
                ref=source.ref,
                chars=len(text),
                trusted=self._rt.source_extraction_trusted and not source_failed,
                failed=source_failed,
                dup=duplicate,
            )
        reason = (
            route.reason
            + source_note
            + _living_capture_suffix(
                routed=Engine.LIVING in route.engines,
                trusted=trusted,
                model_facts=len(model_facts),
                structural=len(structural),
                failed=extraction_failed,
                proposed=proposed,
            )
        )
        return CaptureReceipt(
            doc=target_doc,
            sensitivity=classification.sensitivity,
            engines=tuple(sorted(e.value for e in written)),
            reason=reason,
        )

    def capture_youtube(
        self,
        url: str,
        *,
        bubble: Bubble,
        domains: frozenset[Domain] = frozenset(),
    ) -> YouTubeCaptureReceipt:
        """Capture a YouTube video's TRANSCRIPT into ``bubble`` (sujet 3 / D119-a) — the OUTBOUND sibling of
        :meth:`capture`, the ONE door that pulls a video's subtitles into memory.

        The ORDER is the safety (invariant 5 / 21 · D100 — structural, not merely disciplined):

        1. resolve the ref to a video id LOCALLY — a non-YouTube url raises ``ValueError`` at the door, before
           any network (D55 single door, fail-loud);
        2. refuse fail-closed if no fetcher is wired (the optional yt-dlp brick is absent — no fetcher, no
           fetch, D126);
        3. ask the Guard for an ``EXTERNAL_OUTPUT`` grant BEFORE touching the network — a host off the egress
           allow-list is refused (``GuardDenied``, deny-by-default), and only a PUBLIC url leaves (the M2
           re-floor refuses a mislabeled leak; nothing ``sensible`` is exfiltrated, invariant 1);
        4. only THEN fetch — the returned subtitles are UNTRUSTED third-party DATA (D100-3), never obeyed;
        5. restructure them verbatim (:func:`transcript_to_markdown`, restructure-not-reformulate) and hand
           the ``.md`` to :meth:`capture` as a PUBLIC-provenance source (``public_provenance=True``, D107 —
           a video's public transcript is public by provenance), which memorizes it like any document (a
           YouTube ASR transcript is marked non-verbatim and stripped from the verbatim floor at distillation, C2).

        A video with no usable subtitles memorizes NOTHING (``capture`` is ``None`` in the receipt — honest
        emptiness, F3), leaving room for a LOCAL ASR fallback later (AV1). The declared egress ``target`` is
        the canonical YouTube host: the grant AUTHORIZES the fetch operation (deny-by-default at the Guard);
        per-socket network confinement would be the sandbox's job (a later hardening, not wired here)."""
        video_id = parse_youtube_ref(
            url
        )  # local, fail-loud on a non-YouTube ref — before any egress (D55)
        # The id-only canonical url — DECLARED to the Guard AND the one actually fetched, so "declared ==
        # fetched" holds at the DOOR, not left to the adapter (defense in depth): no surplus query params, no
        # divergence between what the Guard cleared and what leaves.
        canonical = f"https://{_YOUTUBE_EGRESS_HOST}/watch?v={video_id}"
        fetcher = self._rt.transcript_fetcher
        if fetcher is None:
            raise GuardDenied(
                "no youtube fetcher wired — transcript fetch refused fail-closed (③-4c / D126)"
            )
        # Deny-by-default OUTBOUND (inv. 5/21): the Guard refuses unless the host is allow-listed; only a
        # PUBLIC url leaves (M2 re-floor). Raises GuardDenied / EscalateToHuman on refusal — BEFORE the fetch.
        self._guarded(
            Effect.EXTERNAL_OUTPUT,
            subject=bubble,
            inputs=(GovernanceLabel(sensitivity=Sensitivity.PUBLIC, bubble=bubble),),
            target=_YOUTUBE_EGRESS_HOST,
            descriptor=f"fetch youtube transcript {video_id}",
            payload=canonical,
        )
        transcript = fetcher.fetch(
            canonical
        )  # authorized outbound; the subtitles are untrusted DATA (D100-3)
        if not transcript.cues:  # no usable subtitles → memorize nothing (honest emptiness, F3)
            return YouTubeCaptureReceipt(
                None, video_id, transcript.title, transcript.language, transcript.auto_generated
            )
        receipt = self.capture(
            text=transcript_to_markdown(transcript),
            bubble=bubble,
            public_provenance=True,  # a YouTube transcript is a PUBLIC source (D107) — public by provenance
            nature=ContentNature.DOCUMENT,
            domains=domains,
        )
        return YouTubeCaptureReceipt(
            receipt, video_id, transcript.title, transcript.language, transcript.auto_generated
        )

    def remember(
        self,
        learning: str,
        *,
        subject: Bubble,
        within: Sensitivity = Sensitivity.SENSIBLE,
        ftype: str = FicheType.LEARNING,
    ) -> Fiche:
        """Capture a concise LEARNING into living memory, INERT — "apprendre en utilisant" (item 2 / D115-AV3).

        The low-friction door for the "learn while using" nerve the operator insisted on. Where :meth:`capture`
        ingests a whole SOURCE through the extraction pipeline, THIS deposits a single durable learning — a
        stable fact the operator states, a work preference, a correction — that a frontier RECOGNISED while working.
        It is the ACTIVE half of the show→propose→correct loop (D115-AV3): the frontier proposes what it
        learned; the operator validates or corrects it.

        Automatic, but never imposing (D92 / D100). The learning lands PROPOSED in the living-memory
        validation queue (:meth:`proposed` / :meth:`validate_fiche`) — INERT, reinjecting into no answer
        until the operator's gesture; a ``LEARNING`` is never the benign PUBLIC PREFERENCE that may auto-apply, so it
        ALWAYS awaits validation. What makes it "automatic" is the essence memo (item 6) reminding a frontier
        to do it each time it finishes a task, NOT any silent write here. Anti-noise by construction: the
        fiche id is scoped by the CONTENT (:func:`~mnemosyne.production.learning_fiche`), so re-proposing the
        same learning is idempotent and a learning the operator dismissed stays closed (never resurfaced, D60-2).

        Governed like any living-memory write: the learning is labelled ``within`` (fail-safe ``sensible`` —
        it stays local, invariant 1) in ``subject``'s bubble, and the store's monotone, bubble-safe
        :meth:`~mnemosyne.production.memory.LivingMemory.propose` is the backstop (a re-proposition can never
        declassify or cross bubbles, D100-2 / invariant 3). Stored WHOLE: a learning has no documentary
        backup, so an over-long one is REFUSED (``ValueError``), never truncated — capture a document through
        :meth:`capture` instead. Returns the PROPOSED :class:`Fiche` (its ``state`` is ``proposed``, an honest
        receipt that it awaits the gesture)."""
        label = GovernanceLabel(sensitivity=within, bubble=subject)
        fiche = learning_fiche(learning, label, ftype=ftype)
        # durable=True: a captured learning is NON-rebuildable (no documentary backup, nothing re-proposes
        # it) — it must survive the short-lived `remember` process via the proposals ledger, not evaporate
        # with RAM (item 2 / D82). The extractor path leaves durable False (it rebuilds from raw/, D44).
        return self._memory.propose(fiche, durable=True)

    # -- (b) search / consultation (D119-b / D65) ----------------------------------
    def search(
        self,
        query: str,
        *,
        within: Sensitivity,
        subject: Bubble,
        kind: QueryKind = QueryKind.GENERAL,
        domains: frozenset[Domain] = frozenset(),
        top_k: int = 10,
    ) -> SearchView:
        """Search ``within`` one sensitivity partition, on behalf of bubble ``subject`` (D65).

        Three barriers, all centralized in the Guard (D119: cloisonnement lives in the Guard, not
        the UI): (1) retrieval stays inside the ``within`` partition (never crossing sensitivities,
        invariant 1) and ADMITS "I don't know" rather than inventing (invariant 14); (2) a hit
        carrying a DOMAIN ``subject`` does not declare is withheld (invariant 4 / D72); (3) a hit
        owned by a DIFFERENT bubble is returned only through a Guard-validated cross-bubble
        contract (invariant 3 / D54) — a same-bubble hit in a declared domain is an intra-bubble
        read (not a frontier, D89). Both (2) and (3) go through :meth:`_may_read`. Deny-by-default:
        a partition with no readable hit yields a low-recall admission, never a cloisonnement
        leak."""
        route = route_read(kind)
        # MAJEUR-2: over-fetch a WIDE pool, clear the cloisonnement frontier, THEN truncate to top_k —
        # a to-be-withheld hit ranked high no longer evicts a readable one from the top_k. The admission
        # (invariant 14) is floor-based, independent of the fetch width, so widening never re-opens it.
        result = self._retriever.retrieve(
            query, within=within, domains=domains, top_k=max(top_k, READ_POOL)
        )
        readable_all = tuple(h for h in result.hits if self._may_read(subject, h.label))
        readable = readable_all[:top_k]
        withheld = len(result.hits) - len(readable_all)
        low_recall = result.admitted_low_recall or (bool(result.hits) and not readable_all)
        reason = result.reason
        if withheld and not readable:
            reason = (
                f"{withheld} hit(s) withheld — none readable from {subject!r} "
                "(cloisonnement domaine/bulle, invariant 4 / 3 / D72 / D54)"
            )
        # Honesty (D119): search() is the Moteur B document-retrieval surface — it reports the
        # engine it ACTUALLY reads (B). The A⊕B living fusion (Moteur A's VALIDATED fiches ⊕ these
        # documents) is now assembled at :meth:`recall` (③-3b / D65), no longer deferred — search
        # points there rather than claiming a living leg it does not read.
        read_real = frozenset({Engine.DOCUMENTARY})
        if Engine.LIVING in route.engines:
            reason += (
                " — Moteur A (living) fuses at recall(), not in search (③-3b / D65 read fusion)"
            )
        return SearchView(
            hits=tuple((h.doc, h.score) for h in readable),
            admitted_low_recall=low_recall,
            engines=tuple(sorted(e.value for e in read_real)),
            reason=reason,
        )

    def _may_read(self, subject: Bubble, label: GovernanceLabel) -> bool:
        """Whether ``subject`` may read a hit labelled ``label`` — the DOMAIN then BUBBLE frontiers
        (deny-by-default, Guard-mediated). Delegates to the shared
        :func:`~mnemosyne.stores.governed_read.may_read`, so the SAME frontier governs both this
        facade and the agent's ``search_memory`` tool — one definition, never two (D119 / D89)."""
        return may_read(self._guard, subject, label)

    def _pack_passage(self, hit: SearchHit, query: str) -> Envelope[str]:
        """Pack the RELEVANT passage of a recall hit, never the whole document (D136). Delegates to
        the shared :func:`~mnemosyne.stores.governed_read.pack_passage` (one packer, D136 / D108-⑤)."""
        return pack_passage(self._rt.truth, hit, query)

    def _pack_summary(self, hit: SearchHit, subject: Bubble) -> Envelope[str] | None:
        """Resolve a RAPTOR summary hit from the RaptorStore (Ch.5), never truth — delegating to the
        shared :func:`~mnemosyne.stores.governed_read.pack_summary` so this facade and the agent's
        ``search_memory`` tool apply the ONE governed summary read (staleness M2 + stored-label re-gate
        m1), never two copies that could drift into a leak (D119 / consolidate-crosscutting-rules). The
        ordinary leaf-document path (:meth:`_pack_passage`) stays byte-for-byte unchanged. Degrades to
        ``None`` when no :class:`~mnemosyne.stores.raptor.RaptorStore` is wired (a hand-built Runtime,
        D126) or the node was swept meanwhile — the caller drops it silently, never a crash."""
        if self._rt.raptor is None:
            return None
        return pack_summary(self._rt.raptor, self._rt.truth, self._guard, subject, hit)

    def recall(
        self,
        query: str,
        *,
        within: Sensitivity,
        subject: Bubble,
        kind: QueryKind = QueryKind.GENERAL,
        domains: frozenset[Domain] = frozenset(),
        top_k: int = 10,
    ) -> RecallView:
        """The A⊕B read FUSION (D65): validated living fiches ⊕ same-bubble documents, side by side.

        Route-faithful (D65): a PERSONAL query reads Moteur A (living), a FACTUAL one Moteur B
        (documentary), a GENERAL / doubtful one BOTH. The legs are kept SEPARATE and bubble-scoped
        (:func:`~mnemosyne.ingest.router.fuse`): A never overwrites B, and a foreign-bubble item
        never fuses (invariant 3 / D54-8). The D100 net is STRUCTURAL here — the living frame comes
        ONLY from :meth:`~mnemosyne.production.memory.LivingMemory.reinject` (VALIDATED, bubble-scoped
        fiches), never the raw graph, so no unvalidated extraction can surface in an answer. The
        documentary leg clears the same DOMAIN / BUBBLE Guard frontiers as :meth:`search`
        (:meth:`_may_read`), then is narrowed to the subject's own bubble because the fusion is
        single-bubble (a cross-bubble contract hit stays a :meth:`search` result — it is never
        auto-fused into the living answer, D65). Admits low recall (invariant 14) when BOTH legs are
        empty, rather than inventing."""
        route = route_read(kind)
        engines_read: set[Engine] = set()
        # Moteur B (documentary): retrieve, clear the Guard frontiers, keep the SAME-bubble content
        # (the fusion is bubble-scoped, D65). Each hit packs its MATCHED PASSAGE, not the whole doc
        # (D136): the truth's governance label rides along unchanged, but the payload an answer reads
        # stays bounded, so the fail-closed runner bound never fires on the normal recall path.
        facts: tuple[Envelope[str], ...] = ()
        working: tuple[Envelope[str], ...] = ()
        low_recall = False
        if Engine.DOCUMENTARY in route.engines:
            # MAJEUR-2: over-fetch a WIDE pool, clear the frontiers, THEN truncate the surfaced
            # (same-bubble) grain to top_k — a foreign-bubble/undeclared hit ranked high no longer
            # evicts a readable same-bubble one from the top_k (readable recall preserved; never a leak,
            # the foreigner stays withheld). Admission (inv. 14) is floor-based, unaffected by the width.
            result = self._retriever.retrieve(
                query, within=within, domains=domains, top_k=max(top_k, READ_POOL)
            )
            readable = tuple(h for h in result.hits if self._may_read(subject, h.label))
            same_bubble = tuple(h for h in readable if h.label.bubble == subject)[:top_k]
            # Ch.5 (RAPTOR): a summary hit is DERIVED, never a Moteur B document (D56) — it carries no
            # truth-store fiche, so `truth.is_valid` / `truth.role` below do not apply to it. Split it
            # off BEFORE that leaf path, which stays byte-identical for every ordinary document.
            summary_hits = tuple(h for h in same_bubble if is_raptor_summary(h.doc))
            leaf_hits = tuple(h for h in same_bubble if not is_raptor_summary(h.doc))
            # Defense in depth (D137 / D60 / audit finding 1): an ARCHIVED (invalidated) document is
            # never surfaced as answer content — least of all cited as a source once endorsed. The truth
            # store is the arbiter (D56), so a derived-index entry that outlived an archival is dropped
            # here, fail-closed, before the role split.
            live = tuple(h for h in leaf_hits if self._rt.truth.is_valid(h.doc))
            # D137: split live Moteur B by epistemic ROLE (the 6th identity-card axis, D33). An ENDORSED
            # document (base-de-connaissances) is an authoritative, citable source; a matière-de-travail
            # document is the operator's own unverified production — packed and surfaced SEPARATELY, so they can
            # enumerate it, but never conflated with a source of truth. The role is read from the truth
            # store (the arbiter, D56), never the derived index; fail-closed, the default is
            # matière-de-travail, so an unendorsed draft can never land among the citable ``facts``.
            authority_hits: list[SearchHit] = []
            material_hits: list[SearchHit] = []
            for h in live:
                target = (
                    authority_hits
                    if self._rt.truth.role(h.doc) is DocRole.BASE_DE_CONNAISSANCES
                    else material_hits
                )
                target.append(h)
            facts = tuple(self._pack_passage(h, query) for h in authority_hits)
            # Ch.5: a RAPTOR synopsis is model-produced and abstractive — never explicitly endorsed by
            # the operator (D137 has no document for them to endorse), so it can ONLY ever surface as working
            # material, never a citable fact. Unresolvable hits (no RaptorStore wired, or a node swept
            # between the search and this read) are silently dropped, never a crash (D126 / D100).
            summaries = tuple(
                env
                for env in (self._pack_summary(h, subject) for h in summary_hits)
                if env is not None
            )
            working = tuple(self._pack_passage(h, query) for h in material_hits) + summaries
            low_recall = result.admitted_low_recall or (
                bool(result.hits) and not (facts or working)
            )
            engines_read.add(Engine.DOCUMENTARY)
        # Moteur A (living): the VALIDATED, bubble-scoped fiches ONLY — the D100 gate, never the graph.
        frame: tuple[Envelope[str], ...] = ()
        if Engine.LIVING in route.engines:
            # Two cloisonnement gates on the living leg, symmetric with the documentary leg:
            # (1) partition isolation (invariant 1 / D54) — the frame stays inside the SAME
            # sensitivity partition as the read (a ``sensible`` fiche never leaks into a ``perso`` /
            # ``public`` recall), exact-match fail-closed, mirroring the vector index (D68); and
            # (2) the DOMAIN frontier (invariant 4 / D72) via :meth:`_may_read` — a fiche carrying an
            # undeclared domain is withheld exactly as an equivalent Moteur B hit would be.
            frame = tuple(
                _fiche_frame(f)
                for f in self._memory.reinject(subject)
                if f.label.sensitivity == within and self._may_read(subject, f.label)
            )
            engines_read.add(Engine.LIVING)
        # Side by side, bubble-scoped re-check (defense): frame ⊕ endorsed facts ⊕ working material.
        fused = fuse(frame, facts, bubble=subject, working_material=working)
        low_recall = (
            low_recall
            or not (  # admit "I don't know" when ALL three buckets are empty (14)
                fused.frame or fused.facts or fused.working_material
            )
        )
        # Honesty (F3): name only the engine(s) actually consulted (a FACTUAL read never touches A),
        # and keep the two Moteur B roles distinct so the caller never cites working material as truth.
        parts: list[str] = []
        if Engine.LIVING in route.engines:
            parts.append(f"Moteur A: {len(fused.frame)} validated fiche(s)")
        if Engine.DOCUMENTARY in route.engines:
            parts.append(
                f"Moteur B: {len(fused.facts)} endorsed source(s) ⊕ "
                f"{len(fused.working_material)} working-material doc(s)"
            )
        reason = (
            f"{route.reason} — {' ⊕ '.join(parts)}, side by side "
            "(D65 / D137; A never overwrites B, working material is never a source)"
        )
        return RecallView(
            frame=fused.frame,
            facts=fused.facts,
            working_material=fused.working_material,
            sensitivity=fused.sensitivity,
            engines=tuple(sorted(e.value for e in engines_read)),
            admitted_low_recall=low_recall,
            reason=reason,
        )

    def pending_fiches(self) -> tuple[Fiche, ...]:
        """The living-memory validation queue (D59-4): fiches PROPOSED, awaiting the operator's gesture.

        These are the answer-facing projections of extracted facts (③-3b) — inert until validated:
        none reinjects into a :meth:`recall` answer yet (the D100 net, D59-5)."""
        return self._memory.proposed()

    def validate_fiche(self, fiche_id: str, *, human_validated: bool) -> Fiche:
        """Two-speed validation of a living fiche (D59-5) — the human gesture the D100 net requires.

        Delegates to :meth:`~mnemosyne.production.memory.LivingMemory.validate`: a ``perso`` /
        ``sensible`` fiche, or any opinion / fact, needs ``human_validated`` — else
        ``EscalateToHuman`` (never auto-validated, D54-3 / D27); only a benign PUBLIC preference may
        auto-apply (notified, revocable, D92). Once VALIDATED a fiche reinjects (bubble-scoped) into
        :meth:`recall` — this gesture is the ONLY door from an extracted fact to an answer (D100)."""
        return self._memory.validate(fiche_id, human_validated=human_validated)

    def invalidate_fiche(self, fiche_id: str) -> None:
        """Dismiss (close, bi-temporal) a proposed living fiche — the REJECT half of the D59 gate (D60-2).

        Delegates to :meth:`~mnemosyne.production.memory.LivingMemory.invalidate`: the fiche is CLOSED
        (never deleted — still consultable, D53), journaled to the human layer (D82) before RAM, and never
        resurrected by a later re-proposition (D60-2). The dismiss counterpart of :meth:`validate_fiche`,
        for the ``make memory-validate --dismiss`` gesture."""
        self._memory.invalidate(fiche_id)

    def document_role(self, doc: DocId) -> DocRole:
        """The epistemic role of a Moteur B document (D137) — read side of the endorsement gate.

        ``matière-de-travail`` (the operator's own unverified production, the fail-closed default) or
        ``base-de-connaissances`` (an endorsed source of truth). An unknown id raises ``KeyError``."""
        return self._rt.truth.role(doc)

    def endorse_document(self, doc: DocId, *, human_validated: bool) -> DocRole:
        """Endorse a document as a source of truth (base-de-connaissances) — the D137 promotion gate.

        The documentary twin of :meth:`validate_fiche` (Moteur A's D59 gate) for Moteur B: promoting a
        document to an authoritative, citable source is ALWAYS an explicit human gesture — an automatic
        routine may PROPOSE it (surface f, D119-f), never endorse it (D92 / D100). Without
        ``human_validated`` it ESCALATES (``EscalateToHuman``, never auto-endorsed, D59-5); with it the
        document becomes base-de-connaissances and its recalled passages may be cited as sources — until
        a CHANGED re-write reverts it to working material (D137 / D58). Fail-closed: everything stays
        matière-de-travail until this gesture, so a raw draft is never presented as truth. The gesture is
        checked FIRST, so a missing one escalates even for an unknown id (never leaking whether it
        exists); only once it clears does an unknown id raise ``KeyError`` (from ``set_role``).

        The gesture is JOURNALED FIRST when a durable ledger is wired (D156), then applied. Two
        reasons, both measured rather than assumed: the truth store is an in-memory stand-in, so a
        role set here dies with the process; and a library book is not in that store at all, so
        ``set_role`` used to raise ``KeyError`` on all 314 of them. Write-ahead and fail-CLOSED — an
        I/O error propagates, so a gesture that could not be recorded never appears to have been
        made. With no ledger wired (a stub, a unit test) the behaviour is the pre-D156 in-memory one.
        """
        if not human_validated:
            raise EscalateToHuman(
                f"endorsing {doc!r} as a source of truth (base-de-connaissances) is always an "
                "explicit human gesture — never auto-endorsed (D137 / D59-5 / D100)"
            )
        return self._set_role(doc, DocRole.BASE_DE_CONNAISSANCES)

    def retract_document(self, doc: DocId) -> DocRole:
        """Retract a document's endorsement back to matière-de-travail (D137) — the tightening move.

        Always allowed without a gesture: reverting to the fail-closed default is never dangerous
        (mirrors monotonic prudence — declassifying UP is a gesture, tightening DOWN is free). After
        this the document is no longer citable as a source at :meth:`recall`. Unknown id ⇒ ``KeyError``.

        Journaled like its opposite (D156): retracting appends a NEW line rather than erasing the
        endorsement, so the history of what was trusted, and until when, stays readable (invariant 2)."""
        return self._set_role(doc, DocRole.MATIERE_DE_TRAVAIL)

    def _set_role(self, doc: DocId, role: DocRole) -> DocRole:
        """Journal the role gesture (durable, write-ahead) then apply it to the live store.

        Order matters and it is fail-CLOSED: the ledger write comes FIRST, so an I/O failure aborts
        before anything mutates. The in-memory update that follows is best-effort ON PURPOSE — a
        library book is served from its ``.md`` mirror and has no entry in the in-memory store, so
        ``set_role`` raises ``KeyError`` for it. With a ledger wired that is harmless (the durable
        record is what the next process replays); with NO ledger the error propagates, because then
        the in-memory write was the only thing that could have carried the gesture at all.
        """
        if self._rt.endorsements is not None:
            from ..production.endorsements import observed_actor

            self._rt.endorsements.record(doc, role, by=observed_actor())
        try:
            self._rt.truth.set_role(doc, role)
        except KeyError:
            if self._rt.endorsements is None:
                raise
        return role

    def forget(self, doc: DocId) -> None:
        """Purge a document's DERIVATIVE index entries (vector + keyword) — the truth is untouched (D56).

        Used when a book's CONTENT identity changes (an edit yields a NEW doc id, D-CI): the stale prior
        vectors / passages must be dropped, else recall returns BOTH the old and the corrected version
        (audit F3). A derivative-only purge — reconstructible from the truth (D56), never a data loss."""
        self._rt.vector.invalidate(doc)
        self._rt.keyword.invalidate(doc)

    # -- (c) supervision center (D119-c / D111 / D80 / D86 / D90) ------------------
    def health(self, *, runner_up: bool = True, stores_reachable: bool = True) -> HealthReport:
        """The health dashboard (D111): hardware + functional signals, fail-safe aggregation."""
        return self._health.report(runner_up=runner_up, stores_reachable=stores_reachable)

    def pending_validations(self) -> tuple[WorkId, ...]:
        """The human-validation queue (D74 / D91): work SUSPENDED awaiting a human gesture (D96).

        Reads the scheduler's suspended set — items that released their slot (invariant 26) and
        wait for the operator to validate a life-decision, a canal-B gesture, or a deferred index."""
        return self._rt.scheduler.suspended_ids()

    def kill_switch(self) -> None:
        """Global pause / kill-switch (D80): suspend all in-flight work non-destructively.

        Delegates to the scheduler's ``pause_all`` — every running / queued item suspends and
        frees its slot; nothing is dropped, each resumes when cleared (invariant 26)."""
        self._rt.scheduler.pause_all()

    def schedule_work(
        self,
        descriptor: str,
        *,
        label: GovernanceLabel,
        trigger: TriggerKind = TriggerKind.PERIODIC,
    ) -> WorkId:
        """Enqueue a background workflow for the orchestration engine (D93), or refuse fail-closed.

        The ``descriptor`` MUST name a workflow the engine knows (registered at wiring) — an unknown
        one is refused (``KeyError``), never queued (deny-by-default, D100); a full queue is refused
        by the scheduler (invariant 16). ``label`` is the governance label of the data the work
        touches (routed by the Guard when the workflow acts). ``trigger`` defaults to ``PERIODIC`` (a
        background pass) — pass ``MANUAL`` only for interactive work that must PREEMPT background
        (D106); the real cron / watcher that submits PERIODIC / EVENT work on its own is just-in-time
        (D67), today a caller submits. Returns the queued work's id; :meth:`run_background` advances it."""
        self._seq += 1
        work = WorkItem(
            id=WorkId(f"{descriptor}#{self._seq}"),
            trigger=trigger,
            descriptor=descriptor,
            label=label,
        )
        return self._engine.submit(work)

    def run_background(self) -> DrainReport:
        """Advance ready background work one synchronous tick (D93) — the MANUAL trigger of today.

        Dispatches queued work under the concurrency bound and runs it, reacting by gravity
        (complete / suspend-awaiting-human / fail); returns the :class:`DrainReport` of what ran.
        The interactive path (:func:`~mnemosyne.agents.loop.run_agent`) is untouched — this only
        drains BACKGROUND work. A real cron / watcher will call this on a cadence at ignition; today
        a caller (a CLI tick / a test) drives it, the same governed path (D93 / D126)."""
        return self._engine.run_ready()

    def _workflow_verify_restore(self) -> None:
        """The first real background workflow (D93 / D110): prove the backup restores, or FAIL hard.

        Runs the SAME restore-into-a-disposable + smoke check as :meth:`verify_backup`, but as
        MANAGED work: a smoke that does not pass RAISES, so the engine marks the job FAILED
        (fail-closed, D80) and surfaces it in the drain report — a backup that never restores is not
        a backup (D110), never a silent "all good". Takes and returns nothing (a
        :data:`~mnemosyne.runtime.engine.WorkflowFn`)."""
        report = self._backup.verify_restore()
        if not report.smoke_test_passed:
            raise RuntimeError(
                f"backup restore verification failed (D110): snapshot {report.snapshot} did not "
                "pass the smoke test"
            )

    def _workflow_autonomous_proposer(self) -> None:
        """Soul ⑤ — the proactive nerve, run as managed background work (D93 / D119-f / D92).

        One pass of the :class:`~mnemosyne.production.proposer.AutonomousProposer`: it INSPECTS the
        system's state through its sources and DEPOSITS unbidden proposals into the meta receptacle
        (surface f) — the system coming to the operator of its own accord, not only answering when asked. The
        first real source is :class:`~mnemosyne.production.proposer.LivingQueueReview`, the proactive
        bridge from the PASSIVE validation queue to the ACTIVE receptacle; it is handed a COUNT
        (``len(self._memory.proposed())``), never a fiche, so no content crosses the cloisonnement
        (invariant 22 / D66). The deposit sink is a NARROW
        :class:`~mnemosyne.production.proposer.ReceptacleSink` over this facade's ``submit_proposal`` /
        ``inbox`` — never the facade itself — so the pass has no runtime handle to ``review`` /
        ``promote`` (``AttributeError``): it structurally PROPOSES, never promotes (D92 / D100), every
        proposal inert until the operator's :meth:`review`. Bounded to :data:`_PROPOSER_FANOUT_BOUND` deposits
        per pass (anti-noise / anti-runaway, D78), and non-repeating (a signal already awaiting review
        is not re-filed). A SECOND source, :class:`~mnemosyne.production.proposer.IntakeBacklogReview`
        (Q2 autonomy), is added when the composition root wired a raw-intake counter — it reports the
        intake sas DEPTH (a count, never a source's content) and proposes ``make domain-new`` (D46). A
        THIRD, :class:`~mnemosyne.production.proposer.VeilleReview` (Q5 autonomy), is added when a
        distilled-corpus counter is wired — it reports how many fiches await a veille pass (a count,
        never a fiche's id / content) and proposes ``make veille`` (the rich mining is a frontier agent's
        governed act, not this scan). A FOURTH, :class:`~mnemosyne.production.proposer.RepoTidyReview`
        (item 3, the propose-to-automate nerve), is added when a repo-cruft counter is wired — it reports
        how much CLEAR cruft the rangement skill could quarantine (a count, never a path) and proposes
        ``make rangement`` (non-destructive + reversible, D74 / D92). A FIFTH,
        :class:`~mnemosyne.production.proposer.SignalementReview`, is added when a signalement counter is
        wired — it reports how many field reports a PROJECT session filed against Mnemosyne (a count,
        never a title) and proposes ``make signalements``, so the queue reaches the operator without them relaying
        anything by hand. Takes and returns nothing (a
        :data:`~mnemosyne.runtime.engine.WorkflowFn`); richer sources (aggregator D120, the D115-AV3
        usage loop) are later impls of the same source port."""
        sources: list[ProposalSource] = [LivingQueueReview(lambda: len(self._memory.proposed()))]
        # Q2 autonomy: when the composition root wired a raw-intake counter, the proposer ALSO watches
        # the intake sas DEPTH and proposes `make domain-new` (D46) to give un-homed sources a taxonomy
        # home — a COUNT, never a source's name / content (invariant 22 / D66). Absent (None) ⇒ only the
        # living-queue source runs, exactly as before (zero regression).
        if self._intake_backlog_count is not None:
            sources.append(IntakeBacklogReview(self._intake_backlog_count))
        # Q5 autonomy: when the composition root wired a distilled-corpus counter, the proposer ALSO
        # watches how many fiches await a veille pass and proposes `make veille` — a COUNT, never a
        # fiche's id / content (invariant 22 / D66). The rich mining is a frontier agent's governed act,
        # not this scan (cohabitation doctrine). Absent (None) ⇒ the veille source is skipped (zero regression).
        if self._unsurveyed_count is not None:
            sources.append(VeilleReview(self._unsurveyed_count))
        # Item 3 (propose-to-automate): when the composition root wired a repo-cruft counter, the proposer
        # ALSO watches how much CLEAR cruft the rangement skill could quarantine and proposes `make rangement`
        # — a COUNT, never a path (invariant 22 / D66). The rangement pass is non-destructive + reversible and
        # dry-run by default (D74 / D92); the nerve only nudges. Absent (None) ⇒ skipped (zero regression).
        if self._repo_cruft_count is not None:
            sources.append(RepoTidyReview(self._repo_cruft_count))
        # A3: same shape, other tsunami — documents nothing points at. The remedy it names is
        # READ-ONLY (it moves nothing). Absent (None) ⇒ skipped (zero regression).
        if self._documents_orphelins_count is not None:
            sources.append(DocumentsOrphelinsReview(self._documents_orphelins_count))
        # Field reports: when the composition root wired a signalement counter, the proposer ALSO watches
        # what a PROJECT session filed against Mnemosyne itself and proposes `make signalements` — a COUNT,
        # never a title / path (invariant 22 / D66), which matters here because the filing session sits in
        # another project's context. Repairing is a Mnemosyne session's act, never the project's (the two
        # contexts stay separate by design). Absent (None) ⇒ skipped (zero regression).
        if self._signalement_count is not None:
            sources.append(
                SignalementReview(self._signalement_count, self._oldest_signalement_age_days)
            )
        # Inert proposals: the deposit half of the `proposals` surface always worked; this is the
        # RETURN half. Eight drafts sat correctly filed and permanently invisible until a project
        # session filed a signalement about it — a queue nobody drains is a queue nobody filled.
        # Absent (None) ⇒ skipped (zero regression).
        if self._proposal_count is not None:
            sources.append(ProposalQueueReview(self._proposal_count))
        # Open parentheses (C8-c): a detour running beside a plan that nobody remembers is the exact
        # "waste / debt that lingers" the operator named. The OTHER half of that rot — closing cleanly while
        # leaving the debt behind — is refused in `close_parenthese`, not surfaced here: a nudge
        # cannot catch a queue that has already gone quiet. Absent (None) ⇒ skipped (zero regression).
        if self._parenthese_count is not None:
            sources.append(ParentheseReview(self._parenthese_count))
        # I2: `make moisson` existed, was well designed, and had NEVER been pulled once -- the
        # textbook case of "the pattern exists, nothing obliges it". Level 1 BY CHOICE, and the
        # item says why: a forced harvest manufactures candidates. It publishes, never refuses.
        # Absent (None) => skipped (zero regression).
        if self._moisson_due_resume is not None:
            sources.append(MoissonDueReview(self._moisson_due_resume))
        if self._candidats_sans_panne_resume is not None:
            sources.append(CandidatSansPanneReview(self._candidats_sans_panne_resume))
        if self._moissons_en_attente_resume is not None:
            sources.append(MoissonEnAttenteReview(self._moissons_en_attente_resume))
        if self._sites_de_sortie_resume is not None:
            sources.append(SitesDeSortieReview(self._sites_de_sortie_resume))
        if self._accord_chiffre_compte is not None:
            sources.append(AccordChiffreReview(self._accord_chiffre_compte))
        if self._besoins_ouverts_compte is not None:
            sources.append(BesoinsOuvertsReview(self._besoins_ouverts_compte))
        if self._derive_resume is not None:
            sources.append(DeriveReview(self._derive_resume))
        proposer = AutonomousProposer(*sources)
        plafond, nom_de_la_borne = _plafond_du_proposeur(self._rt.policy)
        proposer.run(
            ReceptacleSink(self.submit_proposal, self.inbox),
            max_proposals=plafond,
            nom_de_la_borne=nom_de_la_borne,
        )

    def costs(self) -> Mapping[str, float]:
        """The cost / token quotas from the protected zone (D86) — the dashboard's budget view."""
        return self._rt.policy.quotas

    def export(self, envelope: Envelope[str], *, to_host: str) -> Grant:
        """Attempt an external output — canal A (public auto) or canal B (human gesture) (D90).

        The one outbound path, routed through the Guard as ``EXTERNAL_OUTPUT``: a host off the
        allow-list is refused (``GuardDenied``, invariant 21 / SE5); a ``perso`` / ``sensible``
        flow is ESCALATED for a canal-B human gesture (``EscalateToHuman``, D66 / D90) — never an
        automatic leak; only allow-listed ``public`` returns a grant (canal A). The facade cannot
        exfiltrate any other way (D119)."""
        return self._guarded(
            Effect.EXTERNAL_OUTPUT,
            subject=envelope.label.bubble,
            inputs=(envelope.label,),
            target=to_host,
            descriptor=f"export to {to_host}",
            payload=envelope.payload,
        )

    def verify_backup(self) -> RestoreReport:
        """Prove the backup by restoring the latest precious snapshot + smoke test (D110 / D109).

        The supervision hook for "is the backup real?": delegates to the Kopia adapter's
        restore-into-a-disposable-bubble-then-smoke check — a backup never restored is not a
        backup (D110)."""
        return self._backup.verify_restore()

    def calibrate(self) -> CalibrationReport:
        """Measure the calibration verdict against the runtime's real bricks (D69 / ③-7 / D148).

        The closure instrument for "are the extraction gates trustworthy?": scores the configured
        fact extractor for groundedness (entities-anchored-in-the-passage — the ACTUAL
        ``graph_extraction_trusted`` decision, D148) and the source reader for fidelity
        (text-from-source token-F1 — ``source_extraction_trusted``). The old extraction triple-F1 is
        still measured and carried on the report (informative only, never gating — D148: it compared
        against a hand-labelled golden's one arbitrary triple framing). Both flags stay fail-closed
        (plan-B ``.md`` / low-fidelity flag) until :attr:`CalibrationReport.all_clear`. Brick-free: a
        stub extractor abstains (ungrounded), exactly as the real MLX / Docling bricks are measured
        (F3 / D126)."""
        return calibrate_runtime(self._rt)

    def calibrate_floor(self) -> FloorScore:
        """Earn the retrieval recall floor from the golden set against the runtime's embedder (D69 / ③-2a).

        The third provisional number (with :meth:`calibrate`'s fidelity gate + groundedness anchor): a
        ``(query, passage)`` cosine sweep over :data:`~mnemosyne.stores.golden.RETRIEVAL_SEED` returns
        the floor that maximises retrieval F1 — the number the operator adopts over the embedder's DECLARED
        ``recall_floor`` at ignition (bge-m3's hand-set 0.55 was over-strict, dropping a relevant
        passage at 0.526). Unlike the gates it is a RECOMMENDATION, never auto-applied (D100). Brick-free:
        the stub hashing encoder separates the seed exactly as real bge-m3 will (F3 / D126)."""
        return calibrate_floor_runtime(self._rt)

    # -- (d) production / projects (D119-d / D79) --------------------------------------
    def projects(self) -> tuple[str, ...]:
        """The production/projects hook (D79). Empty in the skeleton — concrete projects are
        ``contenu`` fabricated just-in-time at usage (D98); the surface + :meth:`promote` gate
        are the ``contenant``."""
        return ()

    def produce(
        self,
        brief: str,
        *,
        rubric: Rubric,
        subject: Bubble,
        within: Sensitivity = Sensitivity.SENSIBLE,
        max_rounds: int,
    ) -> RefinementResult:
        """Run the generator↔critic loop (④) to produce a graded draft — never promote it (D79 / D75).

        The *plancher* nerve, wired. Assembles a :class:`~mnemosyne.production.refiners.RunnerGenerator`
        and a DISTINCT :class:`~mnemosyne.production.refiners.RunnerCritic` over the runtime's Runner,
        each minting its OWN ``MODEL_CALL`` grant through the single frontier mediation point
        (:meth:`_model_grant_source` → :meth:`_guarded`) — so every model leg is Guard-mediated (D89 /
        D100). The two roles carry DISTINCT identities (so :func:`~mnemosyne.production.refinement.refine`
        refuses a self-audit fail-closed, D75) and distinct grant descriptors on the audit trail (a
        future provider aiguilleur COULD key a distinct critic model off them; today the Guard routes by
        label only, so both legs run on the same Runner — the substantive separation is identity +
        prompt isolation, the critic sees only the draft). Then runs
        :func:`~mnemosyne.production.refinement.refine`: produce → grade on the ``rubric`` → refine on the
        feedback, keeping the BEST attempt (non-destructive, invariant 2).

        BOUNDED (anti-runaway, D78 / invariant 16): ``max_rounds`` is CLAMPED to SE4's protected DEPTH
        ceiling (:data:`_REFINE_DEPTH_BOUND`) — a caller cannot buy more model rounds than the protected
        zone allows (D100 structural), exactly as ``run_agent`` clamps its turn ceiling. The draft is
        produced inside ``subject``'s bubble at the ``within`` partition (fail-safe ``sensible``) and is
        returned as a BARE str: matière-de-travail, intra-bubble by construction — this surface does not
        itself label the draft; its governance is re-established at the Guard when it is promoted /
        exported (the M2 content re-floor).

        Returns the :class:`RefinementResult` — a DRAFT that passed the bar (or the best attempt with
        ``reached=False``, a FLAG for the operator). It is NOT a deliverable: promotion to a validated output
        stays the human gesture through :meth:`promote` (a distinct verifier + the operator's sign-off, D79 / D96
        — the automation produces, it does not publish). Raises ``GuardDenied`` / ``EscalateToHuman`` on a
        refused model call, ``RefinementRefused`` on a self-audit (D75), and ``CritiqueMalformed`` on a
        critic output that is not the agreed shape (never a silent 0/N, D108-②)."""
        label = GovernanceLabel(sensitivity=within, bubble=subject)
        generator = RunnerGenerator(
            self._rt.runner,
            self._model_grant_source(subject, descriptor="refine: generate (D79)"),
            identity="refine-generator",
            label=label,
        )
        critic = RunnerCritic(
            self._rt.runner,
            self._model_grant_source(subject, descriptor="refine: critique (D75)"),
            identity="refine-critic",
            label=label,
        )
        rounds = min(max_rounds, self._rt.policy.bound(_REFINE_DEPTH_BOUND))
        return refine(generator, critic, brief=brief, rubric=rubric, max_rounds=rounds)

    def promote(self, draft: Draft, *, verifier: str, human_validated: bool) -> Deliverable:
        """Promote a draft to a validated deliverable — distinct verifier + human gesture (D79).

        Delegates to the production workflow, which fails closed on a self-audit
        (``PromotionRefused``) and escalates on a missing human gesture (``EscalateToHuman``): an
        automatic routine may draft, never promote (D79 / D96). Output afterwards is a
        Guard-mediated :meth:`export`."""
        return self._workflow.promote(draft, verifier=verifier, human_validated=human_validated)

    def audit_declassify(
        self, content: Envelope[str], *, producer: str, verifier: str
    ) -> DeclassificationAudit:
        """Attest — by a DISTINCT verifier — that a `sensible` deliverable is clean to declassify (D107).

        The FIRST of D107's two gates, made REACHABLE (D147: the mechanism lived in
        :mod:`~mnemosyne.production.channels` but was wired to nothing — absent from this facade). Delegates
        to :meth:`~mnemosyne.production.channels.Declassification.audit_declassify`, which fails closed on a
        self-audit (``producer == verifier`` → ``CanalBXLRefused``, D100-6). Local by default: the
        still-`sensible` draft never leaves to be audited (invariant 1). Honest scope: this attests the
        STRUCTURAL gate — that an identity DISTINCT from the producer ran an audit — never the SEMANTIC one
        (did the verifier truly find no residual `sensible` trace); the actual clean read is contenu the
        verifier performs (D98), delegable to an isolated auditor (Opus, D75). Its attestation is exactly
        what :meth:`declassify` requires — there is no declassification without it."""
        return Declassification().audit_declassify(content, producer=producer, verifier=verifier)

    def declassify(
        self, content: Envelope[str], *, audit: DeclassificationAudit, human_validated: bool
    ) -> Envelope[str]:
        """Produce a `public` COPY of a `sensible` deliverable under the operator's explicit gesture — original intact (D107).

        D107's SECOND gate and the ONE human-gated exception to upward-only labelling (D100-2), now
        reachable (D147 — "wire the gesture" rather than weaken invariant 1). Delegates to
        :meth:`~mnemosyne.production.channels.Declassification.declassify`, fail-closed three ways: the
        ``audit`` must be PRESENT and DISTINCT (a distinct attestation object exists, producer ≠ verifier,
        re-checked here for defence in depth — NOT proof the semantic audit truly ran, which is contenu the
        verifier performs, D98), and ``human_validated`` must be the operator's explicit gesture — else the content stays `sensible`
        (``EscalateToHuman``: the audit proposes, the operator declassifies, D107 / D66 / D74). The result is a FRESH
        envelope labelled `public`, provenance chained source → audit → declassify; the original is never
        mutated (D44 / D56, non-destructive). This gesture is the UPSTREAM of egress — a `public` copy may
        then leave by canal A — so it stays the operator's alone, never a frontier's: it IS the « REACH TOWARD OTHERS »
        D147 names as the real danger, kept human by construction (D74)."""
        return Declassification().declassify(content, audit=audit, human_validated=human_validated)

    def distill(
        self,
        inp: DistillationInput,
        *,
        subject: Bubble,
        within: Sensitivity = Sensitivity.SENSIBLE,
        trace: TraceId | None = None,
    ) -> DistilledDoc:
        """Distill ONE document into its three-part fiche (D39-4 / D28 / D108) — MODEL_CALL via the Guard.

        The production-side model workload (fills ``knowledge/distilled/``): it builds the
        :class:`~mnemosyne.production.distillation.Distillateur` over the runtime's Runner and a grant source
        that mints a FRESH single-use ``MODEL_CALL`` capability per call (route → grant → the Runner redeems
        it, M1) — so the model leg is Guard-mediated exactly like an agent turn, never a self-granted call
        (D89 / D100). The document is distilled inside ``subject``'s bubble at the ``within`` partition
        (fail-safe ``sensible``); the returned fiche wears that same label (invariant 17). P3 is verbatim by
        construction (the source's own words, :func:`~mnemosyne.production.distillation.keep_verbatim`).
        Raises ``GuardDenied`` / ``EscalateToHuman`` on a refused model call and ``DistillationMalformed`` on
        a bad model output (never a bare crash, D108-②)."""
        label = GovernanceLabel(sensitivity=within, bubble=subject)
        skill = Distillateur(self._rt.runner, self._model_grant_source(subject))
        result = skill.run(
            Envelope(payload=inp, label=label),
            trace=trace if trace is not None else TraceId(f"distill:{inp.doc_id}"),
        )
        return result.payload

    def _model_grant_source(
        self, subject: Bubble, *, descriptor: str = "distillation (D39-4)"
    ) -> Callable[[GovernanceLabel], Grant]:
        """The per-call ``MODEL_CALL`` grant lifecycle a skill's Runner needs (D89 / D100 / M1).

        Returns a callback that mints EXACTLY one fresh single-use grant per model call through the single
        frontier mediation point (:meth:`_guarded`) — the skill never mints its own capability (that would
        be the bypass D100 forbids). Mirrors the agent loop's ``build_grant_source``: one grant-minting
        definition per governed model consumer, always through the Guard. The ``descriptor`` names the
        model leg on the grant's AUDIT trail (the Guard's signer excludes it from the capability, and
        routing is by label today); a future provider aiguilleur COULD key a distinct model off it — e.g.
        a producer vs. its adversarial critic — but that routing does not exist yet."""

        def _mint(label: GovernanceLabel) -> Grant:
            return self._guarded(
                Effect.MODEL_CALL,
                subject=subject,
                inputs=(label,),
                target=None,
                descriptor=descriptor,
            )

        return _mint

    def run_local(
        self,
        prompt: str,
        *,
        subject: Bubble,
        within: Sensitivity = Sensitivity.SENSIBLE,
        schema: str | None = None,
    ) -> str:
        """Dispatch ONE bounded task to the LOCAL model and return its completion (item 1 / D7 / cohabitation).

        The WRITE-analog of :meth:`recall` / ``make search``: where that lets a FRONTIER host READ Mnémosyne's
        memory, this lets a frontier DELEGATE a unit of mechanical decode to the local MLX brain — the master
        (frontier) reasons and orchestrates; the local executor abates the volume
        (``production-delegation-doctrine`` / ``context-minimization``). Free (no token cost) and private
        (local, no egress), so a frontier hands off the repeated / mechanical / cheap work and keeps its own
        budget for the fine reasoning.

        THE RULE this surface exists to serve (the operator, item 1): a local model is far more limited than a
        frontier, so a caller must be aware of its CONTEXT and CAPABILITIES and hand it a task PRECISE and
        granular enough to get a correct answer. One bounded task per call; the frontier chains them. The D136
        input ceiling enforces the "bounded" half structurally (an over-large prompt+schema is REFUSED, never
        truncated); the "precise + granular" half is the caller's craft (the essence memo, item 6, reminds a
        frontier of it).

        Fully governed, exactly like a distillation or an agent turn (D89 / D100): it mints a FRESH single-use
        ``MODEL_CALL`` grant through the single frontier mediation point (:meth:`_model_grant_source` →
        :meth:`_guarded`) — never a self-granted call — and decodes through the runtime's Runner, which redeems
        the grant (M1), snapshots the call for replay, and emits a redacted trace (invariant 12). The decode is
        LOCAL (the runtime's default backend is the MLX brain); no egress, so ``within`` safely defaults to the
        fail-safe ``sensible`` — a frontier can dispatch even personal work to the local model without it ever
        leaving the machine (invariant 1). The output is matière-de-travail (labelled ``within`` in
        ``subject``'s bubble, invariant 17), NEVER an endorsed fact — governance re-establishes at the Guard if
        it is later captured / exported.

        When ``schema`` is given (a JSON schema), the call is STRUCTURED: the decoder is bound to the grammar
        so a malformed object is structurally impossible (invariant 27, the runner's :func:`enforce_grammar`
        barrier) — the way to get schema-valid JSON out of the local model for a mechanical extract / classify
        task. Without it, a free-form completion. Raises ``GuardDenied`` / ``EscalateToHuman`` on a refused
        model call, ``ResourceBoundError`` on an over-large prompt (D136), and ``MalformedOutput`` on a
        structured output the grammar rejects (never a silent wrong answer, D100)."""
        label = GovernanceLabel(sensitivity=within, bubble=subject)
        grant = self._model_grant_source(subject, descriptor="local dispatch (item 1)")(label)
        envelope = Envelope(payload=prompt, label=label)
        if schema is not None:
            constraint = GrammarConstraint(schema=schema, kind="json_schema")
            out = self._rt.runner.complete_structured(envelope, grant=grant, constraint=constraint)
        else:
            out = self._rt.runner.complete(envelope, grant=grant)
        return out.payload

    # -- (e) governance / settings (D119-e / D114 / D112) ----------------------------
    def governance(self) -> GovernanceView:
        """A read-only view of the protected policy zone (SE4): bubbles, egress, bounds, quotas.

        The zone is frozen (D100: a handle cannot mutate a barrier); changing it is the privileged
        act mediated by :meth:`register_tool` and the Guard's ``POLICY_WRITE`` (D102)."""
        policy = self._rt.policy
        return GovernanceView(
            profile=policy.profile,
            bubbles=tuple(policy.declared_domains.keys()),
            egress_allowlist=tuple(sorted(policy.egress_allowlist)),
            bounds=policy.bounds,
            quotas=policy.quotas,
        )

    def describe_self(self) -> SelfModel:
        """A read-only model of what Mnemosyne is and can do — the self-aware nerve (⑥ / D114-TO2).

        Assembled from three truthful sources of the SAME model, in reading order MAP → invokables:
        Mnemosyne's own agent-facing surfaces (the D119 a-f facade — the orienting map of what it can
        do), the Guard's OWN authorized-tool allow-list (D114-⑤), and the protected active-skill
        registry (``skills.toml`` / D37) — so it can only advertise what the reference monitor would
        authorize and what the operator has sanctioned ACTIVE, never more (truthful by construction). A fresh
        agent reads this to take its bearings and use Mnemosyne (D25). Like :meth:`governance` it is a
        pure read: it crosses no frontier and wires nothing — adding a tool / activating a skill stays a
        privileged human act (``POLICY_WRITE`` / D102). It carries only manifest metadata: no secret, no
        fiche content (invariant 22). The skill catalogue is honestly EMPTY until the operator's activation
        gesture; the surfaces map is HONEST about privilege (a human-gated surface says so). This read is
        what a ``describe`` command renders and what an MCP-server surface (D114-TO2) would later wrap."""
        return SelfModel.assemble(
            MNEMOSYNE_IDENTITY,
            AgentSurfacesSource(),
            AuthorizedToolsSource(self._guard.authorized_tools),
            ActiveSkillsSource(self._rt.skill_catalog.active),
        )

    def register_tool(self, name: str) -> Grant:
        """Wire a new tool / MCP server — a PRIVILEGED human act, never agent-auto (D114-⑤).

        Routed through the Guard as ``POLICY_WRITE`` (mutating the protected catalogue, D102 /
        SE4): it always ESCALATES (``EscalateToHuman``) — a running agent can never connect to an
        arbitrary MCP server on its own; only the operator adds to the allow-list."""
        return self._guarded(
            Effect.POLICY_WRITE,
            subject=self._operator,
            inputs=(),
            target=name,
            descriptor=f"register tool/MCP {name!r}",
        )

    def authorize_tool_call(
        self,
        tool: str,
        *,
        subject: Bubble,
        inputs: tuple[GovernanceLabel, ...] = (),
        descriptor: str = "",
    ) -> Grant:
        """Ask the Guard to clear a call to an allow-listed tool — the 8th effect (D114-③).

        The Guard reads the tool's manifest from the PROTECTED catalog, never the caller's word
        (D100), and rules fail-closed: an unlisted tool is denied (``GuardDenied``); a life-action
        tool and a tool that leaves the machine carrying non-public data both escalate
        (``EscalateToHuman`` — sensible-local, D66 / D74). Returns the ``Grant`` the caller hands
        to the tool at invocation (run under the sandbox in ③-5); the tool RESULT is untrusted,
        re-labelled by the maximum when it returns (D101 / D100). This is INVOCATION — wiring a new
        tool is the separate privileged act :meth:`register_tool`."""
        return self._guarded(
            Effect.TOOL_CALL,
            subject=subject,
            inputs=inputs,
            target=tool,
            descriptor=descriptor or f"tool call {tool!r}",
        )

    def call_tool(
        self,
        tool: str,
        arguments: Envelope[object],
        *,
        subject: Bubble,
        inputs: tuple[GovernanceLabel, ...] = (),
    ) -> Envelope[object]:
        """Call an allow-listed tool end-to-end through the Guard (D114-③ / ③-5) — the governed executor.

        Where :meth:`authorize_tool_call` only MINTS a grant for a caller to redeem, this runs the whole
        loop through :class:`~mnemosyne.tools.GovernedToolInvoker`: the Guard grants (reading the PROTECTED
        catalog, never the caller's word — D100), the single-use grant is REDEEMED (M1 — the non-local
        consumer that makes egress enforcement structural, not a dangling seal), the allow-listed plugin
        runs, and its UNTRUSTED return is re-labelled by the maximum (D101 / D100 — it can only raise
        prudence, never lower a barrier nor act alone). Raises ``GuardDenied`` for an unlisted / unwired
        tool or a forged grant, and ``EscalateToHuman`` for a life-action or non-public data leaving the
        machine (canal B). Deny-by-default: with no plugin wired (the skeleton), every call fails closed."""
        invoker = self._rt.tool_invoker
        if invoker is None:
            raise GuardDenied(
                "no tool invoker wired — tool calls are refused fail-closed (③-5 / D126)"
            )
        return invoker.call(tool, arguments, subject=subject, inputs=inputs)

    def render(
        self,
        content: Envelope[object],
        *,
        fmt: str,
        subject: Bubble,
        destination: RenderDestination = RenderDestination.SHAREABLE,
        target: str | None = None,
        title: str = "",
        redact: bool = False,
    ) -> Envelope[bytes]:
        """Render a document through the governed output consumer (sorties, D66 / ③-6) — egress's mirror.

        A LOCAL render emits any label (interior persistence on the operator's own machine, D71); a SHAREABLE
        render is egress-governed by the Guard (allow-list inv. 21 + the M2 content re-floor — a
        ``sensible`` body mislabeled ``public`` cannot slip out), redeeming a single-use grant (M1).
        ``destination`` defaults to the stricter SHAREABLE — a caller who forgets is governed as egress,
        never the reverse. Raises ``GuardDenied`` for an unlisted target, ``EscalateToHuman`` when
        non-public content needs a canal-B gesture, and ``RenderUnavailable`` when no rendering engine is
        wired (fail-closed, D126). Optional ``redact`` yields a public-safe copy only if the deterministic
        re-floor agrees (D100 — the floor is the barrier, not the redactor; Presidio lands at ③-6b)."""
        renderer = self._rt.renderer
        if renderer is None:
            raise GuardDenied(
                "no renderer wired — document output refused fail-closed (③-6 / D126)"
            )
        return renderer.render(
            content,
            fmt=fmt,
            subject=subject,
            destination=destination,
            target=target,
            title=title,
            redact=redact,
        )

    # -- (f) meta / transverse output receptacle (D119-f / D92 / D100) ----------
    def submit_proposal(self, *, source: str, summary: str) -> Proposal:
        """Deposit a meta/transverse proposal into the receptacle (D119-f). PROPOSE, never impose.

        Called by an already-decided behaviour (aggregator, living memory, "Ré-évaluation
        continue"); the proposal is inert until :meth:`review` — no auto-application (D92 / D100).
        Pure routing of a consequence to one visible home; creates no artefact (D119-f)."""
        self._seq += 1
        proposal = Proposal(id=f"p{self._seq}", source=source, summary=summary)
        self._inbox.append(proposal)
        return proposal

    def inbox(self) -> tuple[Proposal, ...]:
        """The meta/transverse receptacle: proposals awaiting the operator's review (D119-f)."""
        return tuple(p for p in self._inbox if not p.reviewed)

    def review(self, proposal_id: str, *, accept: bool, comment: str = "") -> Proposal:
        """The operator's human return on a proposal (D119-f): validate / refuse / comment (D92 / D100).

        The proposal is only ever applied by this explicit human gesture — nothing was applied
        while it waited. Unknown ids raise ``KeyError`` (never a guess)."""
        for i, proposal in enumerate(self._inbox):
            if proposal.id == proposal_id:
                reviewed = Proposal(
                    id=proposal.id,
                    source=proposal.source,
                    summary=proposal.summary,
                    reviewed=True,
                    accepted=accept,
                    comment=comment,
                )
                self._inbox[i] = reviewed
                return reviewed
        raise KeyError(f"unknown proposal {proposal_id!r}")

    # -- (g) generic create / extend route (D119-g; later) -------------
    def create(self, kind: str, *, into: Bubble) -> str:
        """Generic create/extend hook (D119-g, "operator addition, later").

        The extensibility route to CREATE and ATTACH a new element (project, tool, feature) to a
        bubble. A named hook only in Phase 1 (the flow is Phase 1 bis / product); it records the
        intent without side effect, so the surface exists and stays "ready to accueillir" (D98)."""
        return f"create({kind!r} → {into!r}) — hook only (D119-g, Phase 1 bis)"

    # -- internals --------------------------------------------------------------------
    def _next_doc(self, prefix: str) -> DocId:
        self._seq += 1
        return DocId(f"{prefix}-{self._seq}")
