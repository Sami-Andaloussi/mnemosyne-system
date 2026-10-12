"""agent loop (D98 / D93) — the governed multi-turn run, built ON the Pydantic AI bridge.

The orchestration ENGINE (bounded queue / concurrency, :mod:`..guard.bounds`) and the SEAM to a
typed agent (:mod:`.pydantic_bridge`) are already ours; this module supplies the ONE joint the
seam left open (③-5b report) and the governed entrypoint that runs an agent to completion.

:class:`~mnemosyne.agents.pydantic_bridge.RunnerModel` bridges every agent turn to OUR Runner, but
it takes a ``grant_source`` callback it never fills itself — minting a Guard capability from inside
the bridge would BE the bypass D100 forbids. :func:`build_grant_source` IS that callback: each turn
it asks the Guard to route + mint a FRESH single-use ``MODEL_CALL`` grant (the Runner redeems it,
M1); no grant ⇒ no model (fail-closed). :func:`run_agent` assembles the agent over it and runs the
tool→observe loop — Pydantic AI's engine, which we do NOT reimplement (``oss_registry.md``) — under
a hard per-run turn ceiling (anti-runaway DEPTH, invariant 16 / D78), returning the answer enveloped
at the run's floor (≥ the prompt, invariant 17; raise-only, D100).

Only the parts that DRIVE Pydantic AI need the installed brick (:func:`run_agent` /
:func:`smoke_agent_invokes_runner`, ``# pragma: no cover`` — exercised at ③ ignition, ``[OPERATOR]``);
the governed CORE — the grant lifecycle and the ceiling — is pure OUR-code, proven brick-free
against the stub decoder (the *modèle-doublure*) in ``tests/test_agent_loop.py`` (D126).

Decisions: D98 (the agent loop) · D93 (multi-agent engine) · D100 (no Guard bypass) · D89 (behind
the Guard) · D78 (bounds) · D104 (grammar-bound Runner). Code & docstrings English (D117).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..ports import (
    Bubble,
    Effect,
    Envelope,
    GovernanceLabel,
    Grant,
    Guard,
    GuardDenied,
    GuardRequest,
    ResourceBoundError,
    Sensitivity,
)
from .pydantic_bridge import GrantSource, connect_pydantic_agent, drive_agent

if TYPE_CHECKING:
    from ..runtime.bootstrap import Runtime

#: The protected-zone bound (``system/config/policy.toml``) for the per-run turn ceiling — the
#: anti-runaway DEPTH of one agent conversation (distinct from ``agent_fanout``, the BREADTH of
#: concurrent agents). Missing ⇒ ``KeyError`` (an unbounded loop is a bug, never a silent default).
_TURN_BOUND = "agent_max_turns"

#: The exception classes that MEAN "the turn limit has been reached". A list of NAMES rather than
#: an import: this module must not become an importer of the brick (D103).
_NOMS_DE_LIMITE: frozenset[str] = frozenset({"UsageLimitExceeded", "UsageLimitError"})

#: The fail-safe floor a bridged agent turn (and its answer) wears: ``sensible`` until proven (D101
#: default in doubt), so the Guard routes conservatively LOCAL and the answer is never silently
#: declassified (raise-only, D100). Mirrors the bridge's ``_prompt_floor`` — one posture, one place.
#: This is the ANSWER floor, DECOUPLED (item 12) from the agent's search READ CLEARANCE: the
#: ``search_memory`` tool is wired ``search_within=PUBLIC`` at bootstrap so the agent reads its public
#: reference library while its answer stays ``sensible`` — the label posture here is unchanged.
_AGENT_FLOOR = Sensitivity.SENSIBLE


def build_grant_source(guard: Guard, subject: Bubble) -> GrantSource:
    """Return the per-turn grant lifecycle :class:`RunnerModel` needs (D98 / D100 / M1).

    The joint the bridge left open: every agent turn must obtain a FRESH single-use ``MODEL_CALL``
    grant from the Guard (route → grant → the Runner redeems it, M1). The returned callback mints
    EXACTLY that and nothing else — it never runs a model and never mints its own capability (that
    would bypass the Guard, D100). The Guard routes the call (LOCAL for ``sensible``, never canal A
    automatically — invariant 1) and seals the grant with a nonce+HMAC the Runner authenticates. A
    denied turn (:class:`GuardDenied` / :class:`~mnemosyne.ports.core.EscalateToHuman`) PROPAGATES:
    no grant ⇒ no model (fail-closed, the safe default — the bridge already fails closed absent a
    source, this makes the *present* source fail closed on a refusal too)."""

    def _mint(label: GovernanceLabel) -> Grant:
        return guard.grant(
            GuardRequest(
                effect=Effect.MODEL_CALL,
                subject=subject,
                inputs=(label,),
                descriptor="agent turn (D98)",
            )
        )

    return _mint


def _resolve_turn_ceiling(runtime: Runtime, override: int | None) -> int:
    """The hard per-run turn ceiling (anti-runaway depth, invariant 16 / D78).

    Read from the protected zone (``agent_max_turns``); an ``override`` may only LOWER it, never
    raise it above the configured cap — a caller cannot buy itself more turns than SE4 allows
    (D100, structural). Clamped to at least 1 (a run gets at least one turn). A missing bound raises
    ``KeyError`` — fail-closed: an unbounded agent loop is a bug, never a silent default."""
    ceiling = runtime.policy.bound(_TURN_BOUND)
    if override is None:
        return ceiling
    return max(1, min(override, ceiling))


def traduire_le_mur_de_tours(exc: BaseException, plafond: int) -> None:
    """Re-raise a REACHED turn limit as a named MNEMOSYNE bound (A5 / A4).

    WHY THIS FUNCTION EXISTS. `make murs` said *"no refusal recorded"* — not because
    `agent_max_turns` had never bitten, but because **biting was never attributed anywhere**: the
    loop passed the library's error through as-is, and a `UsageLimitExceeded` reads as a tool
    failure, never as *"YOUR bound, at 16, just cut you off."* *Zero refusals can mean the rule is
    being bypassed.* Without this translation, the bound's value stays undecidable forever: you
    cannot measure what is never attributed.

    DETECTION IS DONE BY CLASS NAME, AND THAT IS DELIBERATE: importing `pydantic_ai` here would
    make this module an importer of the brick (D103 — the adapter is the only one). The name is a
    weaker contract than an `isinstance` check, and that is stated plainly: a version that renamed
    its class would make the bite anonymous again, without breaking anything else.

    AND WHATEVER IS NOT A TURN LIMIT PASSES THROUGH UNCHANGED: relabeling an unrelated failure as
    "bound reached" would send someone to raise a ceiling for a defect that has nothing to do with
    it.
    """
    if type(exc).__name__ not in _NOMS_DE_LIMITE:
        return
    raise ResourceBoundError(
        f"the bound `{_TURN_BOUND}` BIT at {plafond} turns: the agent was cut off before it could "
        f"finish. This is not a tool failure, it is a Mnemosyne bound — it is raised by "
        f"`make policy-demander` (type `bound`), never by editing the protected zone."
    ) from exc


def run_agent(  # pragma: no cover - needs pydantic_ai (③ ignition, [OPERATOR])
    runtime: Runtime,
    user_prompt: str,
    *,
    subject: Bubble,
    tool_names: tuple[str, ...] = (),
    instructions: str = "",
    max_turns: int | None = None,
) -> Envelope[str]:
    """Run one governed Pydantic AI agent to completion, behind the Guard (D98 / D100).

    Assembles the agent (:func:`connect_pydantic_agent`: a :class:`RunnerModel` over
    :func:`build_grant_source` + :class:`GovernedToolBridge` tools) and runs Pydantic AI's
    tool→observe loop under a hard turn ceiling (:func:`_resolve_turn_ceiling`, invariant 16),
    returning the final answer enveloped at the run's floor (``sensible``, ≥ the prompt —
    invariant 17; never declassified without a classifier pass, D100). Fail-closed: no governed
    tool invoker ⇒ no run (D100). The Pydantic AI RUN surface is touched only in the adapter
    (:func:`drive_agent`, invariant 20 / D103), so this loop never imports the brick; exercised at
    ignition, the brick-free suite proves the governed core (grant lifecycle, ceiling) below (D126)."""
    if runtime.tool_invoker is None:
        raise GuardDenied("agent run needs a governed tool invoker — no invoker, no tools (D100)")
    ceiling = _resolve_turn_ceiling(runtime, max_turns)
    agent = connect_pydantic_agent(
        runner=runtime.runner,
        invoker=runtime.tool_invoker,
        grant_source=build_grant_source(runtime.guard, subject),
        subject=subject,
        tool_names=tool_names,
        instructions=instructions,
    )
    try:
        answer = drive_agent(agent, user_prompt, request_limit=ceiling)
    except Exception as exc:  # noqa: BLE001 - TRANSLATE then relay, never swallow
        traduire_le_mur_de_tours(exc, ceiling)
        raise
    label = GovernanceLabel(sensitivity=_AGENT_FLOOR, bubble=subject)
    return Envelope(payload=answer, label=label)


def smoke_agent_invokes_runner(  # pragma: no cover - needs pydantic_ai + a model (③ ignition)
    runtime: Runtime, *, subject: Bubble
) -> bool:
    """Assert a REAL Pydantic AI agent reaches the model ONLY through our Runner (D98 / D100).

    THE ignition check the ③-5b report demanded: a version drift could let Pydantic AI fall back to
    its own provider client instead of :meth:`RunnerModel.request`, so we PROVE the override fires.
    A minted grant is the witness — ``RunnerModel.request`` calls ``grant_source`` on every turn
    BEFORE reaching the Runner, so wrapping the source and running a 1-turn agent tells us the seam
    held: if Pydantic AI used its own client instead, the spy would never fire (no Mnémosyne grant).
    Runs at ignition (``[OPERATOR]``), when pydantic_ai + a model are installed; brick-free, the grant
    lifecycle + single-use are already proven below. Returns True iff the override was invoked."""
    if runtime.tool_invoker is None:
        raise GuardDenied("agent run needs a governed tool invoker — no invoker, no tools (D100)")
    minted: list[Grant] = []
    base = build_grant_source(runtime.guard, subject)

    def _spy(label: GovernanceLabel) -> Grant:
        grant = base(label)
        minted.append(grant)  # the witness: the override reached our grant lifecycle
        return grant

    agent = connect_pydantic_agent(
        runner=runtime.runner,
        invoker=runtime.tool_invoker,
        grant_source=_spy,
        subject=subject,
        tool_names=(),
        instructions="",
    )
    drive_agent(agent, "ping", request_limit=1)
    return bool(minted)
