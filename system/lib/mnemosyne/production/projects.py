"""Projects (D49-D54) - cloisonned bubbles, output contract, generator, non-destructive life.

A project is a goal-oriented, CLOISONNED workspace (a "bubble") that consumes knowledge by
its declared rights and keeps its deliverables at home (D49). This module graves the shape
(D50), the exchange mechanism (D51), the generator (D52), the lifecycle (D53) and the
post-audit reinforcements (D54) - with three structural barriers, not discipline:

* **Hard anti-leak (D49 / D54-1).** A bubble open to the outside (internet) sees ONLY
  ``public`` - never ``perso``, never ``sensible``. :class:`SecuritySheet` refuses to exist
  with ``internet=True`` and a ceiling above ``public`` (fail-closed at construction).
* **Deny-by-default + human-validated activation (D52 / D54-3).** The generator proposes the
  MOST RESTRICTIVE profile (no network, ``public`` ceiling, no domains); no project runs
  until a human validates its profile - "no project activated without a
  human-validated profile" (D54-3b). :meth:`ProjectGenerator.activate` refuses otherwise.
* **Re-validation on reactivation (D54-4).** An archived project's profile is re-passed
  against the CURRENT policy on reactivation, never reapplied blindly; a now-too-permissive
  profile escalates to a human (FLAG) instead of returning to ACTIVE silently.

Output crosses a bubble frontier ONLY through the Guard (Effect.CROSS_BUBBLE, invariant 3):
the exposed output declares format + sensitivity + scope (D51), and the Guard mints a fresh
label in the target bubble - never a silent merge (D89 / core.merge). Archiving is freeze +
keep, never delete (D53, non-destructive D44 / D56). Code & docstrings English (D117).

Decisions: D49 (definition + cloisonnement)  -  D50 (anatomy)  -  D51 (output contract)  -  D52
(generator)  -  D53 (lifecycle)  -  D54 (10 reinforcements)  -  D89 (Guard mediates the frontier).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace

from ..ports import Bubble, ErrorCode, EscalateToHuman, MnemosyneError, Sensitivity


class ProjectState:
    """A project's lifecycle state (D53). Non-destructive: archived keeps everything."""

    ACTIVE = "active"
    ARCHIVED = "archived"  # frozen + kept + consultable + reactivable (D53)
    PAUSED = "paused"  # optional intermediate (D53)


class ProjectActivationRefused(MnemosyneError):
    """A project was activated / reactivated without a human-validated, policy-fitting
    profile (D52 / D54-3 / D54-4). Fail-closed: no project runs on an unvetted profile."""

    code = ErrorCode.DENIED


@dataclass(frozen=True, slots=True)
class SecuritySheet:
    """The security profile the Guard reads and enforces PERMANENTLY (D50-1 / D89).

    Encodes the hard anti-leak of D49 at construction: a bubble open to internet may carry
    ``public`` only. This is the single fact that makes "internet bubble sees only public"
    a barrier rather than a hope (D49 / D54-1)."""

    bubble: Bubble
    ceiling: Sensitivity = Sensitivity.PUBLIC  # highest sensitivity the bubble may hold
    internet: bool = False
    domains: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        if self.internet and self.ceiling > Sensitivity.PUBLIC:
            raise ProjectActivationRefused(
                f"bubble {self.bubble!r} is open to internet but its ceiling is "
                f"{self.ceiling.token!r}: an outward bubble sees only `public` (D49 / D54-1)"
            )

    @classmethod
    def deny_by_default(cls, bubble: Bubble) -> SecuritySheet:
        """The MOST RESTRICTIVE profile (D54-3a): no network, ``public`` ceiling, no domains.

        The generator proposes this; a human explicitly grants anything beyond it (D54-3)."""
        return cls(bubble=bubble, ceiling=Sensitivity.PUBLIC, internet=False, domains=frozenset())


@dataclass(frozen=True, slots=True)
class ExposedOutput:
    """A declared output a project accepts to share (D51) - what + format + sensitivity + scope.

    A project never opens whole; it CHOOSES what to expose. Consumption crosses the frontier
    through the Guard (Effect.CROSS_BUBBLE, invariant 3): a `perso` / `sensible` output never
    reaches an outward bubble (anti-leak, D49 / D51)."""

    name: str
    fmt: str  # declared format: docx / python / csv / json / text ...
    sensitivity: Sensitivity
    version: str
    scope: frozenset[Bubble] = frozenset()  # empty => common journal; else named bubbles (D51)


@dataclass(frozen=True, slots=True)
class ProjectManifest:
    """The coquille normée of a project (D50): identity + security sheet + exposed outputs.

    Sub-projects are recursive (same anatomy, free depth, D49 / D50) but each is ÉTANCHE - a
    parent reads a child (or vice-versa) only through an exposed output + the Guard (D54-2)."""

    name: str
    goal: str
    security: SecuritySheet
    outputs: tuple[ExposedOutput, ...] = ()
    state: str = ProjectState.ACTIVE
    subprojects: tuple[ProjectManifest, ...] = ()  # recursive, ÉTANCHE anatomy (D50 / D54-2)

    @property
    def is_active(self) -> bool:
        return self.state == ProjectState.ACTIVE


class ProjectGenerator:
    """Creates a project from the template (D52) - itself a skill (D52 / D42).

    Proposes a deny-by-default profile (D54-3a) and refuses to activate any project whose
    profile a human has not validated (D54-3b). The same gate guards reactivation against the
    CURRENT policy (D54-4)."""

    __slots__ = ()

    def propose(self, *, name: str, goal: str, bubble: Bubble) -> ProjectManifest:
        """Emit a DRAFT project with the most restrictive profile (D52 / D54-3a).

        The project is not yet runnable: :meth:`activate` needs the human gesture."""
        return ProjectManifest(
            name=name,
            goal=goal,
            security=SecuritySheet.deny_by_default(bubble),
            state=ProjectState.PAUSED,
        )

    def propose_subproject(
        self, parent: ProjectManifest, *, name: str, goal: str, bubble: Bubble
    ) -> ProjectManifest:
        """Nest a DENY-BY-DEFAULT sub-project under ``parent`` (D50 / D54-2), returning the updated parent.

        A sub-project shares the anatomy but is ÉTANCHE: it gets its OWN deny-by-default profile (its own
        bubble, ``public`` ceiling, no network, no domains) and NEVER inherits the parent's rights - even a
        permissive parent yields a locked-down child. Parent and child read each other only through an
        exposed output crossing the Guard (D54-2); nesting here grants nothing and activates nothing (the
        child stays PAUSED until its own human-validated activation, D54-3b)."""
        child = self.propose(name=name, goal=goal, bubble=bubble)
        return replace(parent, subprojects=(*parent.subprojects, child))

    def activate(self, manifest: ProjectManifest, *, human_validated: bool) -> ProjectManifest:
        """Activate a project ONLY under a human-validated profile (D52 / D54-3b).

        Fail-closed: "no project activated without a human-validated rights profile". The
        automation clause of D52 may never auto-validate a profile granting internet or
        `perso` / `sensible` access (D54-3c) - so activation always takes the gesture here."""
        if not human_validated:
            raise ProjectActivationRefused(
                f"project {manifest.name!r} cannot be activated without a human-validated "
                "security profile (D52 / D54-3b)"
            )
        return replace(manifest, state=ProjectState.ACTIVE)


@dataclass(frozen=True, slots=True)
class Project:
    """A live project and its non-destructive lifecycle (D53).

    ``archive`` freezes and KEEPS (never deletes); ``reactivate`` re-passes the profile
    against the current policy (D54-4). Real deletion is exceptional, manual, confirmed -
    never here (D53 / D44)."""

    manifest: ProjectManifest

    def archive(self) -> Project:
        """Freeze + keep (D53): the project stops running but everything is retained and
        stays consultable / reactivable. Non-destructive (D44 / D56)."""
        return replace(self, manifest=replace(self.manifest, state=ProjectState.ARCHIVED))

    def reactivate(self, *, permits: Callable[[SecuritySheet], bool]) -> Project:
        """Return to ACTIVE only if the CURRENT policy still permits the archived profile.

        A profile now more permissive than policy allows escalates to a human (FLAG, D54-4)
        rather than silently returning to ACTIVE - the Guard re-checks against today's rules,
        never reapplies yesterday's blindly."""
        if self.manifest.state != ProjectState.ARCHIVED:
            return self
        if not permits(self.manifest.security):
            raise EscalateToHuman(
                f"reactivating {self.manifest.name!r}: its archived profile exceeds the "
                "current policy - human re-validation required (D54-4)"
            )
        return replace(self, manifest=replace(self.manifest, state=ProjectState.ACTIVE))
