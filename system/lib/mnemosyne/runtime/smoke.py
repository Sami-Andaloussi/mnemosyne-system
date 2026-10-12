"""Smoke test 1-click (D109 tier ④) — the "everything's fine" button, non-technical.

The top of the test pyramid (D109): below it are the hard invariants (tier ①), the golden
sets (②) and the three-store integration (③); this is the one-command end-to-end check a
NON-technical operator runs after any change — "ingest a doc → index → retrieve → answer" — and it
either goes green or points at the broken stage. It runs entirely LOCAL (the ``sensible`` is
never exported to be tested, D27 / D66); here it exercises the assembled runtime (D94) over the
in-memory stores, and the real bricks (Qdrant / Graphiti / MLX) slot in behind the same ports
at ③.

**Two layers, one of them non-blocking (D121-E4).**

* :func:`run_smoke_test` — the FUNCTIONAL pipeline: bootstrap → capture (classify + integrate)
  → index (idempotent replay) → retrieve (low-recall-aware, D65 / invariant 14) → answer (fuse
  context, then GENERATE through the grammar-bound Runner behind the Guard — D65 / D104 / D89).
  ``passed`` reflects THIS only.
* :func:`check_human_prerequisites` — the human, out-of-band setup the build CANNOT observe
  (ADP iCloud on, D97 · the Kopia off-site key kept out-of-band, D118 · the provider-side API
  ceiling, D112). These are **FLAGs, never failures**: an unconfirmed prerequisite is reported
  ``UNKNOWN`` so the operator sees it, without breaking the build (D121-E4). It is the honest edge of a
  local-first system — some barriers live in the world, not the code.

Decisions: D109 (pyramid tier ④, 1-click smoke) · D94 (bootstrap) · D65 (read fusion) · D27 /
D66 (tested local, never exported) · D97 / D118 / D112 (human prerequisites) · D121-E4
(smoke-that-FLAGs). Code & docstrings English (D117); the sensitivity tokens stay French.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum

from ..agents.loop import build_grant_source
from ..ingest.router import fuse
from ..ports import (
    Bubble,
    DocId,
    Effect,
    Envelope,
    EscalateToHuman,
    Fact,
    GovernanceLabel,
    Grant,
    GuardDenied,
    GuardRequest,
    IsolationTier,
    NodeId,
    RenderDestination,
    SandboxSpec,
    Sensitivity,
    Source,
)
from ..production import Fiche, FicheType, facts_to_fiches, note_fiche
from ..stores import Retriever
from .bootstrap import Runtime, bootstrap, real_runtime
from .local_first import watch_outbound_network
from .render import RenderUnavailable

#: The disposable bubble the smoke test works in — public, never touching real data.
_SMOKE_BUBBLE = Bubble("smoke")
_SMOKE_DOC = DocId("smoke-doc-1")
_SMOKE_TEXT = "mnemosyne smoke test document about local retrieval and memory"


def _answer_prompt(question: str, facts: tuple[Envelope[str], ...]) -> str:
    """Build a retrieval-augmented prompt: the recalled facts as context, then the question."""
    context = "\n".join(f"- {fact.payload}" for fact in facts) or "(no supporting memory)"
    return f"Context:\n{context}\n\nQuestion: {question}"


@dataclass(frozen=True, slots=True)
class SmokeStep:
    """One stage of the end-to-end pipeline, and whether it held (D109)."""

    name: str
    ok: bool
    detail: str


class PrerequisiteState(Enum):
    """State of a human, out-of-band prerequisite the build cannot enforce (D121-E4)."""

    CONFIRMED = "confirmed"  # observed / attested present
    UNKNOWN = "unknown"  # not observable by the build → FLAG (never a failure)
    MISSING = "missing"  # observed absent → FLAG loudly


@dataclass(frozen=True, slots=True)
class HumanPrerequisite:
    """A setup step that lives in the world, not the code — reported, never build-breaking."""

    name: str
    state: PrerequisiteState
    note: str

    @property
    def flagged(self) -> bool:
        """True when the operator should look — anything but ``CONFIRMED`` (D121-E4)."""
        return self.state is not PrerequisiteState.CONFIRMED


@dataclass(frozen=True, slots=True)
class SmokeReport:
    """Outcome of the 1-click smoke test (D109) + the non-blocking prerequisite FLAGs.

    ``passed`` is the FUNCTIONAL pipeline alone; ``prerequisites`` are human setup FLAGs that
    never affect ``passed`` (D121-E4). ``flags`` surfaces the prerequisites needing attention."""

    passed: bool
    steps: tuple[SmokeStep, ...]
    prerequisites: tuple[HumanPrerequisite, ...]

    @property
    def flags(self) -> tuple[HumanPrerequisite, ...]:
        """The prerequisites the operator should act on (unconfirmed) — informational, non-blocking."""
        return tuple(p for p in self.prerequisites if p.flagged)


def check_human_prerequisites(
    *,
    adp_confirmed: bool | None = None,
    kopia_key_confirmed: bool | None = None,
    api_ceiling_confirmed: bool | None = None,
) -> tuple[HumanPrerequisite, ...]:
    """Report the human, out-of-band prerequisites as FLAGs — never failures (D121-E4).

    Each argument is a human attestation the build cannot verify itself: ``None`` means "not
    observable" → ``UNKNOWN`` (a FLAG), ``True`` → ``CONFIRMED``, ``False`` → ``MISSING``. The
    default (all ``None``) is the honest build-time reality: the encrypted state is not
    constatable from here, so all three FLAG for the operator to confirm at install (D97 / D118 / D112)."""

    def state(confirmed: bool | None) -> PrerequisiteState:
        if confirmed is None:
            return PrerequisiteState.UNKNOWN
        return PrerequisiteState.CONFIRMED if confirmed else PrerequisiteState.MISSING

    return (
        HumanPrerequisite(
            name="icloud_adp",
            state=state(adp_confirmed),
            note="Advanced Data Protection must be ON so the off-site truth is E2E-encrypted "
            "(D97 / D27 / D66) — a human setup step, not observable by the build.",
        ),
        HumanPrerequisite(
            name="kopia_offsite_key",
            state=state(kopia_key_confirmed),
            note="the Kopia off-site repository key must be kept OUT-OF-BAND (losing it makes "
            "the off-site backup unrecoverable — D118 / D110).",
        ),
        HumanPrerequisite(
            name="api_cost_ceiling",
            state=state(api_ceiling_confirmed),
            note="a hard monthly ceiling set provider-side is the structural cost barrier "
            "(D112 / D86 / D100) — set on the dashboard, out of any agent's reach.",
        ),
    )


def run_smoke_test(runtime: Runtime | None = None) -> SmokeReport:
    """Run the 1-click end-to-end smoke test, entirely LOCAL (D109 tier ④).

    Bootstraps a runtime (or uses the one given — e.g. a restore target, D110), then drives one
    document through the whole pipeline: capture (classify + write-ahead integrate), index
    (idempotent replay), graph (record a fact in Moteur A), living (the ③-3c facts→fiches factory +
    the plan-B ``.md`` valve), retrieve (low-recall-aware), recall (fuse Moteur A's VALIDATED fiches
    ⊕ Moteur B docs, D65), answer (generate the reply from the fused context through the grammar-bound
    Runner behind the Guard). Returns a
    :class:`SmokeReport`; ``passed`` is the functional pipeline, with the human prerequisites
    attached as non-blocking FLAGs (D121-E4). Nothing is exported — the test lives on the local
    machine (D27 / D66)."""
    steps: list[SmokeStep] = []
    rt = runtime if runtime is not None else bootstrap()
    steps.append(SmokeStep("bootstrap", True, "runtime assembled, journal replayed (D94)"))

    # capture: classify (public, no PII → PUBLIC floor) and wrap in a travelling envelope (D101).
    classification = rt.classifier.classify(_SMOKE_TEXT, domain_signal=Sensitivity.PUBLIC)
    label = GovernanceLabel(sensitivity=classification.sensitivity, bubble=_SMOKE_BUBBLE)
    envelope = Envelope(payload=_SMOKE_TEXT, label=label)
    steps.append(
        SmokeStep("capture", True, f"classified {classification.sensitivity.token!r} (D101)")
    )

    # source (③-4): the SourceReader port turns raw bytes into text — the binary / voice entry
    # (D125-B5). Exercises the real Docling / WhisperKit brick at ignition (the utf-8 stub in CI); a
    # RAISE (a reader drift at ignition, like the tree-sitter colle) is a RED step, never a crashed
    # smoke. Fidelity of a real extraction is judged out-of-band by the golden-set (D125-B6), not here.
    source_raised = False
    try:
        extracted = rt.source_reader.read(
            Source(ref="smoke.txt", data=_SMOKE_TEXT.encode("utf-8"), mime="text/plain")
        )
    except Exception:  # noqa: BLE001 - a reader drift is a localized red step, never a crashed smoke
        extracted, source_raised = "", True
    source_ok = bool(extracted) and not source_raised
    steps.append(
        SmokeStep(
            "source",
            source_ok,
            f"SourceReader read {len(extracted)} char(s) from bytes"
            f"{' [READ RAISED]' if source_raised else ''} (③-4 / D125-B5)",
        )
    )

    # index: write-ahead integrate (truth first, then derived), then confirm the derived witness.
    rt.journal.integrate(_SMOKE_DOC, envelope)
    indexed = rt.vector.contains(_SMOKE_DOC)
    steps.append(SmokeStep("index", indexed, f"vector indexed={indexed} (D105 / invariant 24)"))

    # graph: write one fact into Moteur A (the living-memory graph) and read it back — this is where
    # the real LadybugDB brick is exercised at ignition (③-3a). A fact enters ONLY enveloped (Guard
    # passage, D89); invalidate would merely close it, never delete (non-destructive, D84).
    fact = Fact(NodeId("mnemosyne"), "runs", NodeId("local"), valid_from=datetime.now(timezone.utc))
    rt.graph.add_fact(Envelope(fact, label))
    graphed = any(f.obj == NodeId("local") for f in rt.graph.query(subject=NodeId("mnemosyne")))
    steps.append(SmokeStep("graph", graphed, "fact recorded & read back in Moteur A (D103 / D84)"))

    # living (③-3c): the last of Moteur A's net — the rich facts→fiches factory and the plan-B valve.
    # (1) FACTORY: an extracted fact folds into ONE per-subject fiche (D120), PROPOSED — inert until
    # validated (D100). (2) PLAN B: when extraction is not trusted, no graph is imposed — the content
    # lands as a readable `.md` NOTE for the operator instead (D58). Both land PROPOSED; neither reaches an
    # answer without the gesture. Deterministic on the stub AND the real bricks (the same colle).
    subject_fact = Fact(
        NodeId("operator"), "prefers", NodeId("concision"), valid_from=datetime.now(timezone.utc)
    )
    [rich] = facts_to_fiches(
        (subject_fact,), label, ftype=FicheType.PREFERENCE, current=rt.living_memory.current
    )
    rt.living_memory.propose(rich)
    note = rt.living_memory.propose(
        note_fiche("a raw note to triage by hand", label, doc=DocId("smoke-note"))
    )
    proposed_ids = {f.id for f in rt.living_memory.proposed()}
    # (3) PRE-PASS: the deterministic tree-sitter pre-pass parses a code snippet into structural facts
    # (D125-B9). This exercises the real brick at ignition (0 under the stub, ≥1 under tree-sitter). A
    # RAISE (e.g. a modern-API drift in the machine-only colle) is a RED step here, not a crashed
    # smoke; a legitimately empty parse (the stub) stays green — ``living_ok`` gates on that (D126).
    structural_raised = False
    try:
        structural = rt.structural_extractor.extract_structural(
            "def smoke(): return 1", language="python"
        )
    except Exception:  # noqa: BLE001 - a parser drift is a localized red step, never a crashed smoke
        structural, structural_raised = (), True
    living_ok = rich.id in proposed_ids and note.ftype == FicheType.NOTE and not structural_raised
    steps.append(
        SmokeStep(
            "living",
            living_ok,
            f"per-subject fiche + plan-B note (PROPOSED) + tree-sitter parsed {len(structural)} "
            f"structural fact(s){' [PARSE RAISED]' if structural_raised else ''} (③-3 / D120 / D58 / D125-B9)",
        )
    )

    # retrieve: hybrid (dense ⊕ keyword) recall within the public partition, low-recall-aware
    # (D65 / invariant 14). The top score is now an RRF rank score, so report hits, not cosine.
    retriever = Retriever.from_policy(rt.policy, rt.vector, rt.embedder, keyword=rt.keyword)
    result = retriever.retrieve(_SMOKE_TEXT, within=classification.sensitivity)
    found = not result.admitted_low_recall and any(h.doc == _SMOKE_DOC for h in result.hits)
    steps.append(
        SmokeStep(
            "retrieve",
            found,
            f"hybrid recall: {len(result.hits)} hit(s), found={found} (invariant 14)",
        )
    )

    # recall: the A⊕B read FUSION (③-3b / D65). A benign PUBLIC preference fiche is proposed and
    # VALIDATED (two-speed — a public preference may auto-apply, D59-5), then reinjected (bubble-
    # scoped) as the living frame; it fuses SIDE BY SIDE with the recalled document (Moteur B). The
    # D100 net is what this step proves live: ONLY a VALIDATED fiche reaches the frame.
    pref = Fiche(
        id="smoke-pref",
        ftype=FicheType.PREFERENCE,
        content=frozenset({"mnemosyne answers concisely"}),
        label=label,
    )
    rt.living_memory.propose(pref)
    rt.living_memory.validate(
        "smoke-pref", human_validated=False
    )  # benign public pref auto-applies
    frame = tuple(
        Envelope(payload=" ; ".join(sorted(f.content)), label=f.label)
        for f in rt.living_memory.reinject(_SMOKE_BUBBLE)
    )
    truth_env = rt.truth.read(_SMOKE_DOC)
    context = fuse(frame, (truth_env,), bubble=_SMOKE_BUBBLE)
    fused_ok = bool(context.frame) and bool(context.facts)  # A⊕B both present, kept side by side
    steps.append(
        SmokeStep(
            "recall",
            fused_ok,
            f"A⊕B fused: {len(context.frame)} living fiche(s) ⊕ {len(context.facts)} doc(s) "
            "(D65, bubble-scoped)",
        )
    )

    # answer: GENERATE the reply from the fused A⊕B context through the grammar-bound Runner behind
    # the Guard (D65 / D104 / D89): a MODEL_CALL grant is minted and REDEEMED (M1), and the reply's
    # label stays ≥ the prompt's (invariant 17). This is the ③-2c seam — the real MLX brick decodes
    # here at ignition.
    prompt = Envelope(
        payload=_answer_prompt(_SMOKE_TEXT, (*context.frame, *context.facts)), label=label
    )
    grant = rt.guard.grant(
        GuardRequest(effect=Effect.MODEL_CALL, subject=_SMOKE_BUBBLE, inputs=(label,))
    )
    reply = rt.runner.complete(prompt, grant=grant)
    answered = bool(reply.payload.strip())
    steps.append(
        SmokeStep(
            "answer",
            answered,
            f"generated {len(reply.payload)}-char reply from {len(context.frame)} fiche(s) ⊕ "
            f"{len(context.facts)} doc(s) via the Runner (D65 / D104)",
        )
    )

    # tools (③-5): the tool / sandbox execution governance, LIVE and fail-closed. (1) DENY-BY-DEFAULT —
    # a tool absent from the PROTECTED allow-list is refused by the Guard (D114-⑤ / D73): calling an
    # unlisted tool through the governed invoker must raise ``GuardDenied`` (the skeleton wires no tool —
    # the CONTENANT, not the CONTENU, D98). (2) SANDBOX FAIL-CLOSED — with no OS-isolation engine wired,
    # the RefusingSandbox REFUSES untrusted execution rather than run it unconfined (D99 / D126). Both
    # barriers green ⇒ the loop the invoker closes (grant → redeem → invoke → re-label the untrusted
    # return) is wired the right way round, and egress enforcement has its consumer (③-5 / D100).
    tool_denied = False
    invoker = rt.tool_invoker
    if invoker is not None:
        try:
            invoker.call(
                "smoke_unlisted_tool", Envelope(payload="args", label=label), subject=_SMOKE_BUBBLE
            )
        except GuardDenied:
            tool_denied = True  # deny-by-default barrier held (D114-⑤)
        except Exception:  # noqa: BLE001 - any other failure is a red step, never a crashed smoke
            tool_denied = False
    sandbox_result = rt.sandbox.run(
        SandboxSpec(tier=IsolationTier.MICROVM),
        "echo untrusted",
        grant=Grant(
            request=GuardRequest(
                effect=Effect.TOOL_CALL, subject=_SMOKE_BUBBLE, inputs=(label,), target="smoke"
            ),
            released_label=label,
        ),
    )
    sandbox_refused = sandbox_result.exit_code != 0 and bool(sandbox_result.violations)
    tools_ok = invoker is not None and tool_denied and sandbox_refused
    steps.append(
        SmokeStep(
            "tools",
            tools_ok,
            f"deny-by-default tool refused={tool_denied}, sandbox refused untrusted exec="
            f"{sandbox_refused} (③-5 / D114-⑤ / D99)",
        )
    )

    # agent (③-5b / D98): the governed multi-turn loop's CORE, live and fail-closed. Build the
    # per-turn grant lifecycle the Pydantic AI bridge needs (build_grant_source), mint ONE MODEL_CALL
    # grant, drive the grammar-bound Runner with it (behind the Guard), and prove the grant is
    # SINGLE-USE — re-redeeming the consumed grant must be refused (M1 / D100). Green on the stub
    # decoder (the modèle-doublure); at ignition the real agent (pydantic_ai + MLX) runs the full
    # tool→observe loop and ``smoke_agent_invokes_runner`` asserts RunnerModel.request actually fires.
    agent_label = GovernanceLabel(sensitivity=Sensitivity.SENSIBLE, bubble=_SMOKE_BUBBLE)
    agent_grant = build_grant_source(rt.guard, _SMOKE_BUBBLE)(agent_label)
    agent_reply = rt.runner.complete(Envelope("agent turn (smoke)", agent_label), grant=agent_grant)
    agent_single_use = False
    try:
        rt.guard.redeem(agent_grant)  # already consumed by the runner above → must be refused (M1)
    except GuardDenied:
        agent_single_use = True
    agent_ok = bool(agent_reply.payload.strip()) and agent_single_use
    steps.append(
        SmokeStep(
            "agent",
            agent_ok,
            f"D98 grant lifecycle: MODEL_CALL grant minted + redeemed, single-use={agent_single_use} "
            "(③-5b / D98 / M1)",
        )
    )

    # render (③-6): the governed document-output (sorties), LIVE — the mirror of ingestion. (1) EGRESS
    # DENY-BY-DEFAULT — a SHAREABLE render to a target absent from the egress allow-list is refused by the
    # Guard BEFORE the engine (inv. 21 / SE5); the protected zone ships an empty allow-list, so producing a
    # shareable artifact is refused (deny-by-default). (2) THE ENGINE NEVER FABRICATES — a LOCAL render is
    # interior (D71), so it passes governance and reaches whatever engine is wired: the REAL Typst engine
    # produces a valid PDF (non-empty bytes starting %PDF) at ignition, and the fail-closed stub
    # (RefusingRenderer) REFUSES honestly (RenderUnavailable) brick-free — never a fabricated artifact.
    # Both green ⇒ governance sits BEFORE the engine (egress gated) AND the engine either renders or
    # refuses, never invents (D66 / D100 / D108 / D126).
    render_denied = False
    pdf_ok = False
    engine_refused = False
    renderer = rt.renderer
    if renderer is not None:
        try:
            renderer.render(
                Envelope(payload="public agenda", label=label),
                fmt="pdf",
                subject=_SMOKE_BUBBLE,
                destination=RenderDestination.SHAREABLE,
                target="smoke.unlisted.host",
            )
        except (GuardDenied, EscalateToHuman):
            render_denied = (
                True  # egress deny-by-default / non-public escalation held (governed egress)
            )
        except Exception:  # noqa: BLE001 - any other failure is a red step, never a crashed smoke
            render_denied = False
        try:
            local = renderer.render(
                Envelope(payload="a local note", label=label),
                fmt="pdf",
                subject=_SMOKE_BUBBLE,
                destination=RenderDestination.LOCAL,
            )
            artifact = (
                local.payload
            )  # LOCAL is interior (D71): a wired engine (real Typst) emits the bytes
            pdf_ok = isinstance(artifact, (bytes, bytearray)) and bytes(artifact[:4]) == b"%PDF"
        except RenderUnavailable:
            engine_refused = True  # the fail-closed stub: no engine wired → honest refusal (D126)
        except Exception:  # noqa: BLE001 - any other failure is a red step, never a crashed smoke
            pdf_ok = False
    # the engine leg holds when the WIRED engine renders a valid PDF (real Typst, ignition) OR fail-closes
    # honestly (the stub, brick-free) — never a fabricated artifact (D108 / D126).
    engine_ok = pdf_ok or engine_refused
    render_ok = renderer is not None and render_denied and engine_ok
    steps.append(
        SmokeStep(
            "render",
            render_ok,
            f"egress deny-by-default={render_denied}, local Typst PDF valid={pdf_ok} "
            f"(engine refused fail-closed={engine_refused}) (③-6 / inv. 21 / D108)",
        )
    )

    passed = all(step.ok for step in steps)
    return SmokeReport(passed=passed, steps=tuple(steps), prerequisites=check_human_prerequisites())


def main() -> int:  # pragma: no cover - CLI over the REAL bricks (③ ignition, machine-only)
    """Run the 1-click smoke over the REAL installed bricks and print the report (``make smoke``).

    Uses :func:`~mnemosyne.runtime.bootstrap.real_runtime` so it exercises bge-m3 + Qdrant +
    tantivy + the MLX runner behind the ports (not the stubs), entirely LOCAL (D27 / D66). Returns
    a POSIX exit code (0 = green) so the shell / a hook can gate on it. Needs ``uv sync --extra
    bricks``, a running local Qdrant, and the MLX weights; the brick-free suite never runs this
    path (D126).

    The start is watched at the MACHINE's edge (field report, 2026-07-21: a cold start once slept 30
    minutes on a half-closed socket to the HF CDN with every weight already cached). Local-first is a
    claim until something counts what crossed the edge, and only this path has the REAL bricks to
    count — the brick-free suite can prove the mechanism, never that ``FlagEmbedding`` and ``mlx_lm``
    actually stay home. Observed, not refused: a legitimate first install still works, and the number
    is PRINTED either way (a start that went out says where)."""
    with watch_outbound_network() as outbound:
        runtime = real_runtime()
    report = run_smoke_test(runtime)
    if outbound:
        print(f"  [XX] local-first: {len(outbound)} network egress(es) AT STARTUP: {outbound[:5]}")
    else:
        print("  [ok] local-first: no network egress at startup (weights read from cache)")
    print("SMOKE:", "PASSED" if report.passed else "FAILED")
    for step in report.steps:
        print(f"  [{'ok' if step.ok else 'XX'}] {step.name}: {step.detail}")
    for prereq in report.flags:
        print(f"  FLAG {prereq.name}: {prereq.state.value} — {prereq.note}")
    return 0 if report.passed else 1


if __name__ == "__main__":  # pragma: no cover - machine-only entry
    import sys

    sys.exit(main())
