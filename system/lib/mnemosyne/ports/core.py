"""Governed-data algebra - the shared vocabulary every port speaks.

This module is the spine of LOT 1. It defines the *value types* that travel
with every datum crossing a port boundary, plus the small, total, side-effect
free algebra over them. These types ARE the contract: the governance metadata
of D108-(5) ("the label travels, the Guard reads it, it blocks"), the sensitivity
taxonomy of D101 / D33 / D66, the compartmentation (*cloisonnement*) of
D54 / D72, and the provenance of D19 / D54.

Unlike the engine ports (Guard, Runner, GraphStore, ...), which are abstract
``Protocol`` s with no implementation, these value types carry their minimal
algebra - ordering, most-restrictive merge, fail-safe default, upward-only
relabel - because that algebra is the *meaning* of the contract, not an engine
to be swapped. The 27 invariants (LOT 2) test these behaviours at the system
boundary; the algebra here is what makes that testable.

Decisions: D108-(5) (governance metadata travels)  -  D101 / D33 / D66
(sensitivity)  -  D54 / D72 (cloisonnement)  -  D19 / D54 (provenance)  -  D100
(non-derivation / monotonic prudence).
Invariants carried: 17, 18, 23 (substrate of 1, 3, 4).
Language: code & docstrings English (D117); sensitivity *values* keep their
canonical French tokens (D33 / D66: ``public`` / ``perso`` / ``sensible``).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from enum import Enum, IntEnum
from typing import Final, NewType


def _utcnow() -> datetime:
    """Timezone-aware UTC now (D84: time is explicit, never naive)."""
    return datetime.now(timezone.utc)


# --------------------------------------------------------------------------- #
# Normalized error model (D108 part (2) - "never a silent crash")             #
# --------------------------------------------------------------------------- #
class ErrorCode(Enum):
    """Normalized error codes so the orchestrator (D93) always knows what to do
    - retry, escalate, or FLAG - instead of meeting a silent crash (D108-(2))."""

    DENIED = "denied"  # Guard refusal, fail-closed (D89 / invariant 5)
    ESCALATE_HUMAN = "escalate_human"  # needs a human gesture (D74 grid)
    UNLABELED = "unlabeled"  # datum without governance metadata (invariant 23)
    CLOISONNEMENT = "cloisonnement"  # cross-bubble / cross-domain breach (inv. 3 / 4)
    MONOTONICITY = "monotonicity"  # attempt to lower a label / right (invariant 17)
    RESOURCE_BOUND = "resource_bound"  # a configured bound was hit (invariant 16)
    UNAVAILABLE = "unavailable"  # backend down -> degrade gracefully (D111)
    MALFORMED = "malformed"  # schema / grammar violation (invariant 27, D104 / D108-(1))
    INTERNAL = "internal"


class MnemosyneError(Exception):
    """Base error carrying a normalized :class:`ErrorCode` (D108 volet (2))."""

    code: ErrorCode = ErrorCode.INTERNAL


class GuardDenied(MnemosyneError):
    """The Guard refused the action (fail-closed, deny-by-default - D89)."""

    code = ErrorCode.DENIED


class EscalateToHuman(MnemosyneError):
    """The action needs an explicit human gesture before any effect (D74)."""

    code = ErrorCode.ESCALATE_HUMAN


class UnlabeledDataError(MnemosyneError):
    """A datum reached a boundary without a governance label (invariant 23)."""

    code = ErrorCode.UNLABELED


class CloisonnementError(MnemosyneError):
    """A cross-bubble / cross-domain flow lacked a validated contract (inv. 3 / 4)."""

    code = ErrorCode.CLOISONNEMENT


class MonotonicityError(MnemosyneError):
    """An automatic step tried to lower a label or widen a right (invariant 17).

    Loosening is never automatic: only an explicit, audited human gesture may
    declassify (D100-2, canal B - D66 / D107)."""

    code = ErrorCode.MONOTONICITY


class ResourceBoundError(MnemosyneError):
    """A configured resource bound was reached (invariant 16, D78)."""

    code = ErrorCode.RESOURCE_BOUND


# --------------------------------------------------------------------------- #
# Sensitivity (D101 / D33 / D66)                                              #
# --------------------------------------------------------------------------- #
class Sensitivity(IntEnum):
    """The label that decides whether a datum may ever leave the machine.

    Ordered ``PUBLIC < PERSO < SENSIBLE`` so that D101's "label = MAXIMUM
    of 3 signals" is plain :func:`max`, and "raise prudence, never
    declassify" (D100-2, invariant 17) is monotonicity in this order. Canal A
    (automatic third-party cloud) is reserved for ``PUBLIC`` alone (D66,
    invariant 1); ``PERSO`` / ``SENSIBLE`` leave only by an explicit human
    gesture through canal B.

    The member ``name`` lowercased is the canonical French data token
    (D33 / D66): ``public`` / ``perso`` / ``sensible``.
    """

    PUBLIC = 0
    PERSO = 1
    SENSIBLE = 2

    @property
    def token(self) -> str:
        """Canonical French data token carried in frontmatter (D33 / D66)."""
        return self.name.lower()

    def may_use_automatic_cloud(self) -> bool:
        """Whether canal A (automatic third-party cloud) is allowed (invariant 1).

        Only ``PUBLIC`` may. This is the single structural gate behind the
        sensible-local invariant; everything else stays local or waits for a
        canal-B human gesture (D66).
        """
        return self is Sensitivity.PUBLIC


#: Fail-safe sensitivity for any datum that lacks one (D101 / D108-(5) / invariant 23).
DEFAULT_SENSITIVITY: Final = Sensitivity.SENSIBLE


# --------------------------------------------------------------------------- #
# Compartmentation identifiers (D49 / D54 / D72)                              #
# --------------------------------------------------------------------------- #
#: An isolation compartment - the unit of cloisonnement (D49 / D54).
Bubble = NewType("Bubble", str)
#: A declared domain within a bubble (D72); multi-valued per datum (D17).
Domain = NewType("Domain", str)

#: Reserved bubble holding data that arrived without a label (invariant 23).
UNLABELED_BUBBLE: Final = Bubble("__unlabeled__")

#: A handle threading one operation through the trace layer (D108-(4) / D19 / D111).
TraceId = NewType("TraceId", str)


# --------------------------------------------------------------------------- #
# Provenance (D19 / D54 transitive taint  -  D76 replayability)                 #
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class Provenance:
    """Where a datum came from, and the chain it was derived through.

    Carries the transitive taint of D54 ("teinte transitive") and the
    replayability anchor of D19 / D76: every derivation *extends* the chain
    rather than erasing it (non-destructive - invariant 2 / 12).
    """

    origin: str  # source: document id, tool name, skill, or "human"
    produced_by: str  # the skill / agent / operation that emitted the datum
    at: datetime  # UTC timestamp (D84 valid/transaction-time substrate)
    parents: tuple[Provenance, ...] = ()

    def derive(
        self,
        produced_by: str,
        *,
        origin: str | None = None,
        at: datetime | None = None,
    ) -> Provenance:
        """Return a child provenance keeping ``self`` as a parent (taint chain)."""
        return Provenance(
            origin=origin if origin is not None else self.origin,
            produced_by=produced_by,
            at=at if at is not None else _utcnow(),
            parents=(self,),
        )


def _merge_provenance(a: Provenance | None, b: Provenance | None) -> Provenance | None:
    """Combine two provenance chains, keeping both as parents (non-destructive)."""
    if a is None:
        return b
    if b is None:
        return a
    if a == b:
        return a
    return Provenance(origin="merge", produced_by="merge", at=_utcnow(), parents=(a, b))


# --------------------------------------------------------------------------- #
# GovernanceLabel - the metadata that TRAVELS (D108-(5) / invariant 23)         #
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class GovernanceLabel:
    """The metadata that travels with every datum (D108-(5), invariant 23).

    Bundles the three signals the Guard (D89) reads at every boundary to
    enforce sensible-local (D27 / D66) and cloisonnement (D54 / D72):
    sensitivity, owning bubble + declared domains, and provenance.

    Two structural rules are encoded here, not left to discipline:

    * **Fail-safe** - data without a label is treated as ``sensible``
      (deny-by-default, invariant 23); see :meth:`unlabeled`.
    * **Monotonic prudence** - combining or re-labelling is upward-only
      (invariant 17, D100-2): an automatic step can only raise restriction,
      never lower it. Lowering is an explicit human gesture handled elsewhere
      (canal B - D66 / D107).
    """

    sensitivity: Sensitivity
    bubble: Bubble
    domains: frozenset[Domain] = frozenset()
    provenance: Provenance | None = None

    @classmethod
    def unlabeled(cls, *, observed_at: datetime | None = None) -> GovernanceLabel:
        """Fail-safe label for data that arrived without one (invariant 23).

        Sensitivity defaults to ``SENSIBLE`` and the datum is quarantined in the
        reserved :data:`UNLABELED_BUBBLE` until the Guard or a human reclassifies
        it (upward-only - D101).
        """
        return cls(
            sensitivity=DEFAULT_SENSITIVITY,
            bubble=UNLABELED_BUBBLE,
            domains=frozenset(),
            provenance=Provenance(
                origin="unlabeled",
                produced_by="system",
                at=observed_at if observed_at is not None else _utcnow(),
            ),
        )

    def merge(self, other: GovernanceLabel) -> GovernanceLabel:
        """Most-restrictive combination of two labels (invariants 17 / 23).

        Sensitivity is the max (D101); domains are unioned (a combined datum
        belongs to every contributing domain); provenance keeps both chains.

        Merging is refused across bubbles: a cross-bubble flow requires a
        Guard-validated output contract (invariant 3), so it must go through
        :class:`~mnemosyne.ports.guard.Guard`, which mints a fresh label in the
        target bubble - never a silent merge here.
        """
        if self.bubble != other.bubble:
            raise CloisonnementError(
                f"cannot merge data across bubbles {self.bubble!r} and "
                f"{other.bubble!r} without a Guard-validated output contract "
                "(invariant 3)"
            )
        return replace(
            self,
            sensitivity=max(self.sensitivity, other.sensitivity),
            domains=self.domains | other.domains,
            provenance=_merge_provenance(self.provenance, other.provenance),
        )

    def raised_to(self, level: Sensitivity) -> GovernanceLabel:
        """Return a label raised to at least ``level`` (upward-only, invariant 17).

        Raising or keeping is allowed; *lowering* raises :class:`MonotonicityError`
        - declassification is never automatic (D100-2), only an explicit human
        gesture through canal B (D66 / D107).
        """
        if level < self.sensitivity:
            raise MonotonicityError(
                f"cannot lower sensitivity {self.sensitivity.token!r} to "
                f"{level.token!r} automatically; declassification is an explicit "
                "human gesture (D100-2, canal B)"
            )
        if level == self.sensitivity:
            return self
        return replace(self, sensitivity=level)

    def may_use_automatic_cloud(self) -> bool:
        """Delegate to :meth:`Sensitivity.may_use_automatic_cloud` (invariant 1)."""
        return self.sensitivity.may_use_automatic_cloud()


# --------------------------------------------------------------------------- #
# Envelope - the unit that crosses every port boundary (D108-(5))               #
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class Envelope[T]:
    """A payload plus the governance label that travels with it (D108-(5)).

    Every value crossing a port boundary is an ``Envelope``: ``payload`` is
    opaque data, ``label`` is the governance metadata the Guard reads. The
    payload can change shape (:meth:`map`) but the label travels with it, and
    re-labelling is upward-only (:meth:`relabel`) - invariant 17.
    """

    payload: T
    label: GovernanceLabel

    def relabel(self, label: GovernanceLabel) -> Envelope[T]:
        """Replace the label, refusing any downgrade (invariant 17, D100-2) or a silent
        cross-bubble move (invariant 3, D54): a bubble change is not a relabel - it needs
        a validated cross-bubble contract through the Guard, never a quiet swap here."""
        if label.bubble != self.label.bubble:
            raise CloisonnementError(
                f"cannot relabel across bubbles {self.label.bubble!r}->{label.bubble!r}: a "
                "cross-bubble move needs a validated contract through the Guard (invariant 3)"
            )
        if label.sensitivity < self.label.sensitivity:
            raise MonotonicityError(
                f"cannot relabel from {self.label.sensitivity.token!r} down to "
                f"{label.sensitivity.token!r} (declassification is a human gesture)"
            )
        return replace(self, label=label)

    def map[U](self, fn: Callable[[T], U]) -> Envelope[U]:
        """Transform the payload, carrying the SAME label forward (taint kept)."""
        return Envelope(payload=fn(self.payload), label=self.label)
