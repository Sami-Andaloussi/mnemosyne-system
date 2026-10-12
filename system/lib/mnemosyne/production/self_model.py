"""⑥ — the self-model: Mnemosyne describes what it is and what it can do (D114-TO2 / D25).

The soul's *self-aware* nerve. A fresh LLM that loads Mnemosyne must be able to ask "what are you,
what can you do?" and get a TRUTHFUL, read-only answer — the first breath of the model-of-self
(D114-TO2, already P1-bis) before the MCP-server surface is stood up. This module is the mechanism:
a :class:`SelfModel` (an immutable, headless view, D119) assembled from injectable
:class:`CapabilitySource` ports. The first real source reports Mnemosyne's OWN authorized-tool
surface — the allow-list the Guard actually rules from (D114-⑤) — so the self-description is truthful
BY CONSTRUCTION: it can only say what the reference monitor would in fact authorize, never more.

Four structural properties hold, mirroring the tool catalog they read (D100):

* it is READ-ONLY — a source hands out immutable :class:`CapabilityCard`s; nothing here can wire,
  activate, or mutate a capability (adding a tool / skill stays a privileged human act,
  ``POLICY_WRITE`` / D102, out of any agent's reach);
* a card carries only GOVERNANCE-SAFE metadata — a manifest projection (name / io-schema / effect /
  reach), never a secret and never a fiche's content (invariant 22 / cloisonnement);
* it is deny-by-default — no source, or a source with nothing to report, yields an EMPTY model, never
  an error and never an invented capability (D73 / D89);
* each capability KIND is a separate source of the SAME model — the authorized tools and the active
  skills (a ``ConfigSkillCatalog`` over the protected registry) today, the governance posture later,
  each an impl of :class:`CapabilitySource`, never a rewrite of the assembler.

Brick-free (D126): a source wraps a plain callable over already-built state; deterministic, nothing
installed. Code & docstrings English (D117). Decisions: D114-TO2 (Mnemosyne as an MCP server exposing
its capabilities) · D25 (a blank agent loads a skill and embarks) · D114-⑤ / D102 (the protected
allow-list, human-wired) · D100 (structural incapacity) · invariant 22 (zero secret).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from ..ports import ToolManifest
from .skills import SkillManifest, SkillNeeds

#: A one-line, drift-proof self-statement: it names only the GOVERNANCE POSTURE (structurally
#: enforced invariants, not features that come and go), so it can never quietly become untrue.
MNEMOSYNE_IDENTITY = (
    "Mnemosyne — a personal environment for building XXL LLM-driven projects, with a memory "
    "and a library. AGNOSTIC to which model runs it: "
    "frontier and local entrances both exist and neither is the proclaimed default (D174). "
    "Every frontier is mediated by a deny-by-default reference monitor (the Guard), "
    "and the system proposes, never imposes."
)


@dataclass(frozen=True, slots=True)
class CapabilityCard:
    """One governance-safe capability the system can truthfully advertise about itself.

    A projection of a manifest — ``name`` + how to call it (``summary`` = the D108 io-schema or role)
    + its governed posture (``effect`` reads/acts, ``reach`` stays-local/leaves) — and NOTHING a
    surveilled reader must not see: no secret, no fiche content, no bubble datum (invariant 22)."""

    kind: str  # "tool" today; "skill", "governance" as later sources plug the same port
    name: str
    summary: str
    effect: str
    reach: str


class CapabilitySource(Protocol):
    """A source of capability cards — one KIND of thing Mnemosyne can say about itself.

    Every source is READ-ONLY over already-built state; it can describe a capability, never wire or
    activate one (D100 / D102)."""

    def cards(self) -> tuple[CapabilityCard, ...]:
        """The capabilities this source advertises, or ``()`` when it has nothing to report."""
        ...


@dataclass(frozen=True, slots=True)
class SelfModel:
    """What Mnemosyne is and what it can do — an immutable, headless view (D119).

    ``identity`` is the drift-proof governance posture; ``capabilities`` are the deduplicated cards
    every source contributed, in source order. It is a plain value: reading it wires nothing and
    crosses no frontier — a fresh LLM takes its bearings from it (D25 / D114-TO2)."""

    identity: str
    capabilities: tuple[CapabilityCard, ...]

    @classmethod
    def assemble(cls, identity: str, *sources: CapabilitySource) -> SelfModel:
        """Assemble the self-model from every source, in order, de-duplicated by ``(kind, name)``.

        Dedup is structural, not trust (D100): two sources can never make the model advertise the
        same capability twice — an "improbable" collision is refused by construction, not bet against
        (enforce-collisions-structurally)."""
        seen: set[tuple[str, str]] = set()
        cards: list[CapabilityCard] = []
        for source in sources:
            for card in source.cards():
                key = (card.kind, card.name)
                if key in seen:
                    continue
                seen.add(key)
                cards.append(card)
        return cls(identity=identity, capabilities=tuple(cards))


@dataclass(frozen=True, slots=True)
class AuthorizedToolsSource:
    """The first real source: Mnemosyne's OWN authorized-tool surface (D114-⑤).

    It reads the allow-list the Guard actually rules from — passed as a plain callable so the source
    stays brick-free and can reach nothing but the manifests (never the Guard's mint key, never a
    mutable catalog handle, D100). Frozen like every value object here (incapacity > trust): the
    callable cannot be swapped after construction. Each :class:`~mnemosyne.ports.tools.ToolManifest`
    becomes a governance-safe card; the self-description is therefore truthful BY CONSTRUCTION — it can
    only advertise what the reference monitor would in fact authorize. A life-action or externally-
    reaching tool is reported HONESTLY (its ``effect`` / ``reach`` say so); describing it is not
    invoking it — the invocation stays gated by the Guard (D74 / D114-③)."""

    list_manifests: Callable[[], tuple[ToolManifest, ...]]

    def cards(self) -> tuple[CapabilityCard, ...]:
        return tuple(
            CapabilityCard(
                kind="tool",
                name=manifest.name,
                summary=manifest.io_schema,
                effect=manifest.effect.value,
                reach=manifest.egress.value,
            )
            for manifest in self.list_manifests()
        )


def _skill_reach(needs: SkillNeeds) -> str:
    """A skill's reach, mirroring a tool's egress: does it DECLARE a need for the network (D38)?

    A declared need, not a granted right — the policy decides whether it is honoured (D38 / D89)."""
    return "needs_network" if needs.network else "stays_local"


@dataclass(frozen=True, slots=True)
class ActiveSkillsSource:
    """The second real source: the skills the operator has sanctioned ACTIVE (D37 / D114-TO2).

    It reads the active-skill registry — passed as a plain callable so the source stays brick-free and
    can reach nothing but the manifests (never a mutable catalog handle, D100). Frozen like every value
    object here (incapacity > trust): the callable cannot be swapped after construction. Each ACTIVE
    :class:`~mnemosyne.production.skills.SkillManifest` becomes a governance-safe card projecting its
    role (``summary``), task class (``effect`` — atomic vs orchestration, mirroring a tool's effect)
    and declared network reach (``reach``). The Guard-enforced sensitivity ceiling (D54-9) and the
    skill's domains stay a plafond, NOT advertised — a card carries only what a fresh LLM needs to
    embark (D25), never a secret or a bubble datum (invariant 22). Describing a skill is not running
    it: this source advertises; it activates and executes NOTHING (D102 / D37)."""

    list_active: Callable[[], tuple[SkillManifest, ...]]

    def cards(self) -> tuple[CapabilityCard, ...]:
        return tuple(
            CapabilityCard(
                kind="skill",
                name=manifest.name,
                summary=manifest.role,
                effect=manifest.needs.task_class,
                reach=_skill_reach(manifest.needs),
            )
            for manifest in self.list_active()
        )


#: Mnemosyne's high-level agent-facing surfaces — the D119 a-g facade sections, as the ORIENTING MAP a
#: fresh agent reads to grasp "the whole of what I can do", above the individual tools/skills (D25 / a
#: blank agent takes its bearings). Curated and STABLE (the seven surfaces are architectural, a numbered
#: decision D119), governance-safe (a name + a one-line role + an honest posture), and HONEST about
#: privilege: a surface that is human-gated or privileged SAYS so in its ``effect``, so the map can
#: never imply an agent may cross a frontier it cannot (D102 / D89). It is a MAP, not an invocation
#: handle: reading it wires and runs nothing. Kept beside the model it feeds; if a D119 section is
#: renamed the map is updated with it (the facade owns the truth — this mirrors it deliberately).
AGENT_SURFACES: tuple[CapabilityCard, ...] = (
    CapabilityCard(
        kind="surface",
        name="capture",
        summary="ingest a source into memory; the floor classifies its sensitivity (D119-a / D101)",
        effect="writes_memory",
        reach="stays_local",
    ),
    CapabilityCard(
        kind="surface",
        name="search",
        summary="search & recall — the corpus via `make search` (hybrid retrieval, cloisonnee by "
        "bubble, D119-b / D65) AND our own past conversations via `make rappel` (full-text, no "
        "model, no cost, D155); both are PULLED, nothing is injected at startup",
        effect="read_only",
        reach="stays_local",
    ),
    CapabilityCard(
        kind="surface",
        name="supervision",
        summary="health, backup-check and the kill-switch (D119-c / D80 / D111); `make depense` "
        "MEASURES what Mnemosyne's own code spent (D155/D86) and blocks nothing — a ceiling that "
        "refuses is the operator's gesture to switch on, never a default",
        effect="read_and_control",
        reach="stays_local",
    ),
    CapabilityCard(
        kind="surface",
        name="production",
        summary="produce & refine deliverables; promotion stays a human gate (D119-d / D79)",
        effect="produces_drafts_human_gated",
        reach="stays_local",
    ),
    CapabilityCard(
        kind="surface",
        name="governance",
        summary="read the protected policy posture; wiring a tool is a privileged human act (D119-e / "
        "D114). Widening policy.toml itself now has a door (D159): `make policy-demander` files a "
        "structured request, `make policy-examiner` gets it narrowed by an isolated agent (never "
        "widened — a structural incapacity), and only the operator's own live `/dev/tty` word on `make "
        "policy-approuver`/`policy-refuser` decides — an agent can neither type it nor forge it. "
        "`make murs` shows every wall the Guard has raised, so hitting one stops being silent.",
        effect="read_and_privileged",
        reach="stays_local",
    ),
    CapabilityCard(
        kind="surface",
        name="proposals",
        summary="receive non-solicited proposals and review them — propose, never impose (D119-f / D92)",
        effect="read_and_review",
        reach="stays_local",
    ),
    # C9 — a capability nothing points at is a capability nobody uses, and this one exists BECAUSE
    # an agent could not answer "which models do I have?": it looked, found no declaration, and
    # wrote "no model installed" into a plan with 103 GiB on the disk. So it is advertised in the
    # self-model a fresh agent reads first, not only in the Makefile it has no reason to open.
    CapabilityCard(
        kind="surface",
        name="modeles",
        summary="WHICH local models this machine holds — `make modeles` prints the declared basket "
        "(`system/config/models.toml`) VERIFIED against the disk both ways (declared-but-absent, "
        "present-but-undeclared, drifted weight are three named refusals; 2 ms). There is NO default "
        "model, deliberately (C9): a decode that names none REFUSES and prints the basket — name it "
        "with `MODELE=<id>` (`MODELE_VISION=<id>` for the eye). Read-only; `models.toml` is the "
        "protected zone, so `EMETTRE=1` hands the operator the exact lines to paste.",
        effect="read_only",
        reach="stays_local",
    ),
    # The operator asked, 2026-08-16: "for high-token-output tasks, do we actually have standards,
    # or not really?" — measured: the only written rule on model choice was the AUDIT one (D75:
    # "the most capable available, never weaker than the producer"). Its inverse —
    # descend for high-volume, low-per-item-judgment PRODUCTION — ran in real production (D145,
    # distillation) but had NO address: a fresh agent reading the rules would conclude "always the
    # most capable", a cost defect by construction, invisible because the result stays right, only
    # expensive. Addressed rather than copied (D163): the rule itself lives in this repository's own
    # governance documentation, derived from the one real precedent that exists — not a
    # general policy beyond it.
    CapabilityCard(
        kind="surface",
        name="choix_du_modele",
        summary="WHICH model tier a task should run on — the rule, not the roster `modeles` reads. "
        "AUDIT stays on the most capable available, never weaker than the producer (D75) — "
        "descending there would destroy D75 outright. High-volume, low-per-item-"
        "judgment PRODUCTION descends to the cheapest tier that holds the contract, under two "
        "structural conditions that must hold or descending becomes cutting corners cheaper: the "
        "split is CALCULATED by code, never left to the agent, and reassembly REFUSES an "
        "incomplete result rather than gluing back what comes in — never trust in the agent's own "
        "report. Default is UP when the task's judgment demand is unknown. The rule itself is "
        "documented separately and is never copied here (D163).",
        effect="cost_tiered",
        reach="stays_local",
    ),
    # The operator, 2026-08-16, verbatim: this had to become something a fresh agent finds without
    # being told, "not imperative like the Guard" — measured before this card existed: `make
    # describe` carried ZERO mention of the plan standard (`grep -ic plan`, 0). The posture is
    # D176's own words, addressed rather than copied: the standard itself lives in this
    # repository's own planning documentation, so this card names the entry commands and points,
    # it does not restate the contract.
    CapabilityCard(
        kind="surface",
        name="plan",
        summary="build, read and retract a project's plan (`make plan-nouveau` births one "
        "conforming from birth; `make plans`/`make carte` read state at constant size; "
        "`make item-retirer` retracts an item as a GATED gesture — demand/examine/approve, never "
        "a text edit) — the standard itself is documented separately, never copied here (D163). "
        "OFFERED, never imposed (D176): a project ADOPTS the standard or does not — but once "
        "adopted, it is never derogated.",
        effect="offered_never_imposed",
        reach="stays_local",
    ),
    # The operator, 2026-08-16, verbatim, same night as `plan` above, and graded serious rather
    # than optional: "everything we just built needs to be visible, accessible, usable [...]
    # it's very serious — otherwise we build things that end up dead". Measured before this
    # card existed: `make describe` carried the string "orchestration" exactly once, and it was
    # `cours`'s unrelated `task_class` tag — genuinely ZERO mentions of this doctrine itself, and
    # `lot-emit` (the mandate a chat actually runs on) was UNKNOWN too — named the most severe gap.
    CapabilityCard(
        kind="surface",
        name="execution",
        summary="how parallel work on a project's plan actually runs — one chat per ARC (never "
        "item nor project), its mandate published by `make lot-emit ARC=<letter>` from fields "
        "already public in the plan (never an orchestrator's own reasoning), three hard limits "
        "(the orchestrator takes no product item itself, no sub-sub-agent, no direct "
        "chat-to-chat channel), and a chat-count bound DERIVED from the real plan, never "
        "hand-written (`make orchestration-borne`). The doctrine itself is documented "
        "separately, never copied here (D163). OFFERED, never imposed (D176): a project "
        "ADOPTS it or does not — but once adopted, it is never derogated.",
        effect="offered_never_imposed",
        reach="stays_local",
    ),
    # `signaler` was the SECOND gap named most severe: "this is the channel a project uses to
    # report a breakage back to the system". Not D176 — this is a built-in CHANNEL, not a standard a
    # project opts into; postured like `proposals` above (read, review, never auto-repair).
    CapabilityCard(
        kind="surface",
        name="signalement",
        summary="the channel a PROJECT session uses to report a suspected Mnemosyne defect "
        "without repairing it itself (D153) — `make signaler` files the report and hands "
        "control straight back to the project; `make signalements` is how a Mnemosyne session "
        "reads what has not been drained yet. A filed report is never deleted (invariant 2).",
        effect="read_and_review",
        reach="stays_local",
    ),
)


@dataclass(frozen=True, slots=True)
class AgentSurfacesSource:
    """The third source: Mnemosyne's own high-level surfaces (D119-a…f) — the map a fresh agent needs.

    A static, governance-safe orienting map (default :data:`AGENT_SURFACES`), injectable for tests.
    Unlike the tool / skill sources it wraps no live state: the surfaces are architectural (D119), so
    the map is a curated constant — HONEST about privilege (a human-gated surface says so) and a MAP,
    not a handle (reading it wires and runs nothing, D100). It advertises the AGENT-facing surfaces;
    it does not restate the privileged operator methods as "capabilities" (exposing ``register_tool``
    = ``POLICY_WRITE`` as a capability would mislead, D102 / D114-⑤ — a deliberate scope, per ⑥-1)."""

    surfaces: tuple[CapabilityCard, ...] = AGENT_SURFACES

    def cards(self) -> tuple[CapabilityCard, ...]:
        return self.surfaces
