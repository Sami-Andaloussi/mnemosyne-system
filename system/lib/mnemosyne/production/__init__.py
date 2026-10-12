"""Production & consequences (LOT 6) — the output fabric, gated by the human gesture.

This package is the "output / production / consequences" layer that sits atop the runtime
(LOT 5), the stores (LOT 4b) and the Guard (LOT 3). Its single spine is one rule made
structural everywhere: **a privileged transition — promoting, exposing, declassifying, merging
back — is gated by a human gesture and a DISTINCT verifier (D75 / D100-6), and the governance
label travels so the Guard (D89) can enforce compartmentalization and sensible-local at each
hop.**

Barriers realized (each replaces a pending invariant frame or a named seam, and each is
proven to bite under mutation by the lot's isolated audit — anti-hollow):

* **Canal B XL (D90 / D102) — invariant 19.** :mod:`.channels`: no XL copy without a
  confirmed return point AND a clean attestation by a distinct verifier; `sensible` never in
  an XL batch; a privileged merge needs a human validation; the return is untrusted data.
* **Production (D79 / D121-D1).** :mod:`.workflow`: promotion needs a distinct verifier and a
  human gesture; auto may draft, never promote.
* **Skills / projects (D36-D54).** :mod:`.skills` / :mod:`.projects`: declare-needs (never
  self-granted rights), human-validated activation, deny-by-default profiles, a hard anti-leak
  guarantee (an internet bubble sees only `public`), non-destructive lifecycle.
* **Living memory (D58-D60 / D120).** :mod:`.memory`: two-speed validation, bubble-scoped
  reinjection, no hard delete, A↔B reconciliation FLAG, aggregator that proposes / never
  imposes.
* **Router read-side fusion (D65).** Realized in :func:`mnemosyne.ingest.router.fuse` (the
  seam LOT 4a deferred): fuse A + B without silent overwrite, bubble-scoped.

**Scope boundary (container, not content — D98).** The concrete skills, projects, production
workflows and living target-documents are *content*, generated just-in-time at usage (D37 /
D98); LOT 6 codifies their *container* and its barriers. Canal A (automatic public egress) and
per-item canal B are already the Guard's egress ruling (LOT 3), reused, not reimplemented.
Code & docstrings English (D117); ``public`` / ``perso`` / ``sensible`` stay French (D33).
"""

from __future__ import annotations

from .channels import (
    CanalBXL,
    CanalBXLRefused,
    Declassification,
    DeclassificationAudit,
    ExpurgationAttestation,
    MergeResult,
    ReturnedDiff,
    ReturnPoint,
    WorkCopy,
)
from .chapter_parsing import (
    VERBATIM_BEGIN,
    VERBATIM_END,
    mask_fenced_verbatim,
)
from .distillation import (
    DistillationInput,
    DistillationMalformed,
    Distillateur,
    DistilledDoc,
    DistilledType,
    GrantSource,
    SourceQuality,
    DISTILL_SCHEMA,
    assess_source_quality,
    build_prompt,
    keep_verbatim,
)
from .frontmatter import (
    FIELDS_BY_NAME,
    FRONTMATTER_FIELDS,
    LANG_TOKENS,
    OPTIONAL_FIELD_NAMES,
    REQUIRED_FIELD_NAMES,
    SENSITIVITY_TOKENS,
    FieldError,
    FrontmatterField,
    FrontmatterValidation,
    validate_frontmatter,
)
from .finisher import (
    FINISH_PROMPT,
    Chapter,
    chapter_numbers_ok,
    curate_concepts,
    finish_fiche,
    is_bad_title,
    is_templated_description,
    parse_fiche,
    render_fiche,
)
from .juge import (
    FicheVerdict,
    JudgeStatus,
    judge_fiche,
    passage_cap,
    truncated_passages,
    verbatim_split,
)
from .golden import (
    GOLDEN_SEED,
    MIN_EXTRACTION_F1,
    MIN_GROUNDEDNESS,
    MIN_YIELD,
    ExtractionScore,
    GoldenCase,
    GroundednessScore,
    Triple,
    load_extraction_golden,
    score_extraction,
    score_groundedness,
)
from .human_journal import HumanLayerJournal
from .proposals_ledger import ProposalsLedger
from .memory import (
    AggregationProposal,
    Aggregator,
    Fiche,
    FicheType,
    LivingMemory,
    ReconciliationFlag,
    ValidationState,
    facts_to_fiches,
    learning_fiche,
    note_fiche,
)
from .projects import (
    ExposedOutput,
    Project,
    ProjectActivationRefused,
    ProjectGenerator,
    ProjectManifest,
    ProjectState,
    SecuritySheet,
)
from .skills import (
    SCAFFOLD_MARKERS,
    SEED_SKILLS,
    SKILL_ANATOMY_TEMPLATE,
    ActivationState,
    SkillActivationRefused,
    SkillAudit,
    SkillGenerator,
    SkillManifest,
    SkillNeeds,
    TaskClass,
    audit_skill,
)
from .refinement import (
    Evaluator,
    Generator,
    RefinementRefused,
    RefinementResult,
    Rubric,
    Score,
    refine,
)
from .refiners import CritiqueMalformed, RunnerCritic, RunnerGenerator
from .proposer import (
    AutonomousProposer,
    IntakeBacklogReview,
    LivingQueueReview,
    CandidatSansPanneReview,
    MoissonEnAttenteReview,
    AccordChiffreReview,
    BesoinsOuvertsReview,
    SitesDeSortieReview,
    DeriveReview,
    MoissonDueReview,
    ParentheseReview,
    PendingProposal,
    ProposalDraft,
    ProposalSink,
    ProposalSource,
    ProposalQueueReview,
    ReceptacleSink,
    DocumentsOrphelinsReview,
    RepoTidyReview,
    SignalementReview,
    VeilleReview,
)
from .parentheses import (
    DEFAULT_PARENTHESES_DIR,
    Parenthese,
    ParentheseRefusee,
    close_parenthese,
    open_parenthese,
    open_parenthese_count,
    open_parentheses,
)
from .endorsements import DEFAULT_ENDORSEMENTS_PATH, EndorsementLedger
from .proposals import (
    DEFAULT_PROPOSALS_DIR,
    mark_reviewed,
    open_proposal_count,
    open_proposals,
)
from .review_signals import DO_NOT_CAPTURE, Signal, detect, render_review
from .sessions import DEFAULT_INDEX_PATH, Hit, Recall, SessionIndex, SessionRow
from .spend import (
    DEFAULT_SPEND_PATH,
    CanonicalUsage,
    Charge,
    CostStatus,
    DaySpend,
    SpendLedger,
    price,
    render_spend,
)
from .signalements import (
    DEFAULT_SIGNALEMENTS_DIR,
    file_signalement,
    mark_handled,
    open_signalement_count,
    open_signalements,
)
from .veille_ledger import (
    DEFAULT_LEDGER_PATH,
    fiche_id,
    mark_surveyed,
    surveyed_ids,
    unsurveyed_fiche_count,
    unsurveyed_fiches,
)
from .self_model import (
    AGENT_SURFACES,
    MNEMOSYNE_IDENTITY,
    ActiveSkillsSource,
    AgentSurfacesSource,
    AuthorizedToolsSource,
    CapabilityCard,
    CapabilitySource,
    SelfModel,
)
from .model_catalog import (
    BASKET_PREFIX,
    DEFAULT_MODELS_PATH,
    ENV_TEXT_MODEL,
    ENV_VISION_MODEL,
    CatalogRefusal,
    DiskModel,
    ModelCard,
    ModelCatalog,
    ModelRefused,
    Reconciliation,
    basket_report,
    emit_declaration,
    hub_root,
    reconcile,
    resolve_model_id,
    scan_hub,
)
from .skill_catalog import ConfigSkillCatalog
from .verifier import require_distinct
from .workflow import Deliverable, Draft, ProductionWorkflow, PromotionRefused
from .public_mirror import (
    DOCS_ALLOWLIST,
    EXCLUDE_SCRIPTS,
    EXCLUDE_SKILL_FOLDERS,
    EXPORT_RELATIVE_PATH,
    INCLUDE_ROOTS,
    MAKEFILE_DROPPED_TARGETS,
    PERSONAL_DENYLIST_PATTERNS,
    PRIVATE_DOC_REFERENCE_PATTERNS,
    SANITIZE_CHECKLIST,
    EXCLUDE_CLAUDE,
    STATIC_EXPORT_ONLY_PATHS,
    SyncMarkerUnknownHere,
    SyncPlan,
    changed_paths_since,
    classify_changed_paths,
    export_import_smoke_test,
    is_in_scope,
    mark_synced,
    parse_git_status_paths,
    purge_bytecode_caches,
    paths_not_yet_touched,
    paths_outside_scope,
    read_last_synced_commit,
    scan_for_leaks,
    uncovered_in_scope_paths,
    unexpected_touched_paths,
    verify_export,
)

__all__ = [
    # producer ≠ verifier gate (D75 / D100-6)
    "require_distinct",
    # skills (D36-D39 / D42)
    "TaskClass",
    "ActivationState",
    "SkillActivationRefused",
    "SkillNeeds",
    "SkillManifest",
    "SEED_SKILLS",
    "SkillGenerator",
    # skill-creator (D39-7) — the meta-skill's own contract + verify-in-code audit
    "SKILL_ANATOMY_TEMPLATE",
    "SCAFFOLD_MARKERS",
    "SkillAudit",
    "audit_skill",
    # distillateur — the first concrete Skill[I,O] (D39-4 / D28-D29 / D108)
    "DistilledType",
    "DistillationInput",
    "DistilledDoc",
    "Distillateur",
    "DistillationMalformed",
    "GrantSource",
    "keep_verbatim",
    "build_prompt",
    "DISTILL_SCHEMA",
    "SourceQuality",
    "assess_source_quality",
    # frontmatter schema + validator — the P1 identity card contract (D33 / D121-C2)
    "FrontmatterField",
    "FRONTMATTER_FIELDS",
    "FIELDS_BY_NAME",
    "REQUIRED_FIELD_NAMES",
    "OPTIONAL_FIELD_NAMES",
    "SENSITIVITY_TOKENS",
    "LANG_TOKENS",
    "FieldError",
    "FrontmatterValidation",
    "validate_frontmatter",
    "FicheVerdict",
    "JudgeStatus",
    "judge_fiche",
    "verbatim_split",
    "truncated_passages",
    "passage_cap",
    "Chapter",
    "chapter_numbers_ok",
    "curate_concepts",
    "finish_fiche",
    "is_bad_title",
    "is_templated_description",
    "parse_fiche",
    "render_fiche",
    "FINISH_PROMPT",
    # chapter grammar + self-delimited verbatim fence — the ONE home the 3 readers share (D143 / D100)
    "VERBATIM_BEGIN",
    "VERBATIM_END",
    "mask_fenced_verbatim",
    # projects (D49-D54)
    "ProjectState",
    "ProjectActivationRefused",
    "SecuritySheet",
    "ExposedOutput",
    "ProjectManifest",
    "ProjectGenerator",
    "Project",
    # production workflow (D79 / D121-D1)
    "PromotionRefused",
    "Draft",
    "Deliverable",
    "ProductionWorkflow",
    # generator↔critic loop on a rubric — the floor nerve (D79 / D75 / D39-⑥)
    "Rubric",
    "Score",
    "Generator",
    "Evaluator",
    "RefinementResult",
    "RefinementRefused",
    "refine",
    # the concrete Runner-backed sockets that incarnate the loop's ports (D104 / D89)
    "RunnerGenerator",
    "RunnerCritic",
    "CritiqueMalformed",
    # the autonomous proposer — the proactive nerve (⑤ / D119-f / D92 / D115-AV3)
    "ProposalDraft",
    "ProposalSource",
    "ProposalSink",
    "PendingProposal",
    "ReceptacleSink",
    "AutonomousProposer",
    "LivingQueueReview",
    "IntakeBacklogReview",
    "VeilleReview",
    "DocumentsOrphelinsReview",
    "RepoTidyReview",
    "DEFAULT_ENDORSEMENTS_PATH",
    "EndorsementLedger",
    "ProposalQueueReview",
    "SignalementReview",
    # parentheses (C8-c) — a detour opened beside a plan, refused unless it declares its RETURN
    "CandidatSansPanneReview",
    "MoissonEnAttenteReview",
    "AccordChiffreReview",
    "BesoinsOuvertsReview",
    "SitesDeSortieReview",
    "DeriveReview",
    "MoissonDueReview",
    "ParentheseReview",
    "DEFAULT_PARENTHESES_DIR",
    "Parenthese",
    "ParentheseRefusee",
    "close_parenthese",
    "open_parenthese",
    "open_parenthese_count",
    "open_parentheses",
    # the survey ledger (Q5) — the append-only memory of which fiches a frontier survey pass surveyed
    "DEFAULT_LEDGER_PATH",
    "fiche_id",
    "surveyed_ids",
    "mark_surveyed",
    "unsurveyed_fiches",
    "unsurveyed_fiche_count",
    # signalements — a PROJECT session files a Mnemosyne defect here; a Mnemosyne session drains it
    "DEFAULT_SIGNALEMENTS_DIR",
    "file_signalement",
    "mark_handled",
    "DEFAULT_PROPOSALS_DIR",
    "mark_reviewed",
    "open_proposal_count",
    "open_proposals",
    "open_signalement_count",
    "open_signalements",
    # the self-model — the self-aware nerve (⑥ / D114-TO2 / D25 / D100)
    "MNEMOSYNE_IDENTITY",
    "CapabilityCard",
    "CapabilitySource",
    "SelfModel",
    "AuthorizedToolsSource",
    "ActiveSkillsSource",
    "AgentSurfacesSource",
    "AGENT_SURFACES",
    # the protected skill registry — describe_self's 2nd source (⑥ / D37 / D102, mirror of tools.toml)
    "ConfigSkillCatalog",
    # the protected LOCAL model basket, verified against the disk both ways (C9 — no default, D95)
    "BASKET_PREFIX",
    "DEFAULT_MODELS_PATH",
    "ENV_TEXT_MODEL",
    "ENV_VISION_MODEL",
    "CatalogRefusal",
    "DiskModel",
    "ModelCard",
    "ModelCatalog",
    "ModelRefused",
    "Reconciliation",
    "basket_report",
    "emit_declaration",
    "hub_root",
    "reconcile",
    "resolve_model_id",
    "scan_hub",
    # living memory + aggregator (D58-D60 / D120)
    "FicheType",
    "learning_fiche",
    "ValidationState",
    "ReconciliationFlag",
    "Fiche",
    "facts_to_fiches",
    "note_fiche",
    "LivingMemory",
    "AggregationProposal",
    "Aggregator",
    # human-layer journal (D82) — the replayable, fail-closed net under the operator's validations
    "HumanLayerJournal",
    # proposals ledger (item 2 / D82) — durable landing for non-rebuildable proposals (make remember)
    "ProposalsLedger",
    # D155 — the three organs taken from hermes-agent's learning loop, under our rules:
    # the end-of-task signal detector, recall over our own past conversations, the spend counter.
    "DO_NOT_CAPTURE",
    "Signal",
    "detect",
    "render_review",
    "DEFAULT_INDEX_PATH",
    "Hit",
    "Recall",
    "SessionIndex",
    "SessionRow",
    "DEFAULT_SPEND_PATH",
    "CanonicalUsage",
    "Charge",
    "CostStatus",
    "DaySpend",
    "SpendLedger",
    "price",
    "render_spend",
    # extraction golden-set + plan-B trigger (③-3c / D69)
    "Triple",
    "GoldenCase",
    "ExtractionScore",
    "score_extraction",
    # D148 — the gate that measures INVENTION (mechanical, no golden, no judge) rather than
    # agreement with a labeller's arbitrary framing; see golden.py for why the F1 could not measure.
    "GroundednessScore",
    "score_groundedness",
    "MIN_GROUNDEDNESS",
    "MIN_YIELD",
    "load_extraction_golden",
    "GOLDEN_SEED",
    "MIN_EXTRACTION_F1",
    # canal B XL + declassification (D90 / D102 / D107) — invariant 19
    "CanalBXLRefused",
    "ReturnPoint",
    "ExpurgationAttestation",
    "WorkCopy",
    "ReturnedDiff",
    "MergeResult",
    "CanalBXL",
    "Declassification",
    "DeclassificationAudit",
    # public-mirror skill — sync projects/mnemosyne/mnemosyne-github, D174 applied to any LLM host
    "EXPORT_RELATIVE_PATH",
    "INCLUDE_ROOTS",
    "DOCS_ALLOWLIST",
    "EXCLUDE_SCRIPTS",
    "EXCLUDE_SKILL_FOLDERS",
    "MAKEFILE_DROPPED_TARGETS",
    "EXCLUDE_CLAUDE",
    "STATIC_EXPORT_ONLY_PATHS",
    "SANITIZE_CHECKLIST",
    "PERSONAL_DENYLIST_PATTERNS",
    "PRIVATE_DOC_REFERENCE_PATTERNS",
    "SyncPlan",
    "is_in_scope",
    "classify_changed_paths",
    "changed_paths_since",
    "scan_for_leaks",
    "verify_export",
    "export_import_smoke_test",
    "parse_git_status_paths",
    "paths_not_yet_touched",
    "paths_outside_scope",
    "uncovered_in_scope_paths",
    "unexpected_touched_paths",
    "read_last_synced_commit",
    "mark_synced",
]
