"""Aiguilleur — deterministic engine routing (D57 write · D65 read) + read fusion (D65).

Two engines, one door (D55): **Moteur A** (living memory / bi-temporal facts, D58-D60)
and **Moteur B** (documentary knowledge, D61-D64). This module realizes the DETERMINISTIC
routing *decision* — which engine(s) a write or a read touches — and the bubble-scoped
read *fusion* (:func:`fuse`, D65, added once the live stores existed); what is deferred is
the actual STORE WIRING behind the decision (filing into / reading the live engines), which
lands at ③ (D123 / D58).

* **Write (D57).** Rules from metadata, no LLM judgement. Prudent default = Moteur B
  only; a datum is NEVER filed as a living fact (A) until its bubble and sensitivity are
  fixed (an unclassified datum → B alone).
* **Read (D65).** Personal / opinion queries → A; factual / documentary → B; general or
  doubtful → BOTH. The read default (both) is the assumed asymmetry vs the write default
  (B): reading, one prefers not to miss living context; writing, one avoids misfiling.

Code & docstrings English (D117); the ``public`` / ``perso`` / ``sensible`` tokens the
governance layer carries stay French (D33 / D66).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from ..ports import (
    UNLABELED_BUBBLE,
    Bubble,
    CloisonnementError,
    Envelope,
    GovernanceLabel,
    Sensitivity,
)


class Engine(Enum):
    """The two retrieval / storage engines behind the single door (D55)."""

    LIVING = "A"  # Moteur A — living memory / bi-temporal facts (D58-D60)
    DOCUMENTARY = "B"  # Moteur B — documentary knowledge (D61-D64)


class ContentNature(Enum):
    """The write-time nature the sorter keys on (D57). The two 'living' sub-natures are
    behaviour preferences (procedural) and evolving opinions (declarative); the rest is a
    document."""

    DOCUMENT = "document"
    BEHAVIOUR = "behaviour"  # procedural preference — how to write / act for the user (D57)
    OPINION = "opinion"  # evolving declarative view, vs an objective fact (D57)


class QueryKind(Enum):
    """The read-time query class the router keys on (D65)."""

    FACTUAL = "factual"  # reference / document content → Moteur B
    PERSONAL = "personal"  # preferences / opinions / recent personal context → Moteur A
    GENERAL = "general"  # general or doubtful → both (D65 default)


@dataclass(frozen=True, slots=True)
class Route:
    """Which engine(s) a write or read touches, and why (D57 / D65).

    The decision only — the store calls and the A↔B fusion (with its contradiction
    FLAG) are deferred to LOT 4b / 6 (see :func:`fuse`)."""

    engines: frozenset[Engine]
    reason: str


_LIVING_NATURES = frozenset({ContentNature.BEHAVIOUR, ContentNature.OPINION})


def route_ingest(
    label: GovernanceLabel, *, nature: ContentNature = ContentNature.DOCUMENT
) -> Route:
    """Write routing (D57): deterministic, prudent default = Moteur B only.

    A datum whose bubble / sensitivity is not yet fixed (the fail-safe unlabeled bubble,
    invariant 23) is NEVER filed as a living fact — it goes to Moteur B alone until
    classified (D57). A declared living nature (behaviour / opinion) is filed in A; a
    document in B."""
    if label.bubble == UNLABELED_BUBBLE:
        return Route(
            frozenset({Engine.DOCUMENTARY}),
            "unclassified ⇒ Moteur B only, never living (D57)",
        )
    if nature in _LIVING_NATURES:
        return Route(
            frozenset({Engine.LIVING}),
            f"living nature {nature.value!r} ⇒ Moteur A (D57)",
        )
    return Route(frozenset({Engine.DOCUMENTARY}), "document ⇒ Moteur B (D57)")


def route_read(kind: QueryKind = QueryKind.GENERAL) -> Route:
    """Read routing (D65): personal → A, factual → B, general / doubt → BOTH.

    The read default is BOTH — the assumed asymmetry vs the write default of B (D65).
    Fusion of the two engines' answers is deferred to :func:`fuse`."""
    if kind is QueryKind.PERSONAL:
        return Route(frozenset({Engine.LIVING}), "personal / opinion query ⇒ Moteur A (D65)")
    if kind is QueryKind.FACTUAL:
        return Route(
            frozenset({Engine.DOCUMENTARY}),
            "factual / documentary query ⇒ Moteur B (D65)",
        )
    return Route(
        frozenset({Engine.LIVING, Engine.DOCUMENTARY}),
        "general / doubt ⇒ both (D65 default)",
    )


@dataclass(frozen=True, slots=True)
class FusedAnswer:
    """Moteur A frame + Moteur B (endorsed facts ⊕ working material), kept SIDE BY SIDE (D65 / D137).

    The living engine supplies the frame (who the user is, preferences, recent state); the
    documentary engine supplies TWO buckets, split by epistemic role (D137): ``facts`` are ENDORSED
    sources (the knowledge base) that may be cited as truth, ``working_material`` is the user's own
    unverified production (working material) — surfaced but NEVER presented as a source. Keeping the
    three separate IS the "present both, never silently overwrite" of D65 / D60, extended
    so a raw draft is never conflated with an endorsed source. NB: which document is endorsed is decided
    UPSTREAM by the caller (:meth:`~mnemosyne.api.core_api.CoreApi.recall`, reading the truth store's
    role — the arbiter, D56); :func:`fuse` does not read roles, it faithfully PRESERVES the caller's
    bucketing. ``sensitivity`` is the max over ALL three, so the fused answer carries sensible-local
    downstream even from working material (D65 / D27)."""

    frame: tuple[Envelope[str], ...]  # Moteur A — living: preferences / opinions / recent state
    facts: tuple[Envelope[str], ...]  # Moteur B — ENDORSED sources (the knowledge base), citable
    working_material: tuple[
        Envelope[str], ...
    ]  # Moteur B — working material: unverified, never a source
    sensitivity: Sensitivity


def fuse(
    living: tuple[Envelope[str], ...],
    documentary: tuple[Envelope[str], ...],
    *,
    bubble: Bubble,
    working_material: tuple[Envelope[str], ...] = (),
) -> FusedAnswer:
    """Fuse Moteur A + Moteur B answers, bubble-scoped, without silent overwrite (D65 / D60 / D137).

    Three structural guarantees, not discipline: (1) **bubble-scoped** — every item (frame, endorsed
    ``documentary``, AND ``working_material``) must belong to ``bubble``; a foreign-bubble result is a
    cloisonnement breach (invariant 3 / D49 / D54-8), refused fail-closed, so a query never fuses
    across bubbles. (2) **no silent overwrite** — the buckets are kept side by side in
    :class:`FusedAnswer`; A never overwrites B, and the caller's endorsed ``documentary`` is never
    conflated with ``working_material`` (D137 — which document is endorsed is CLASSIFIED upstream by the
    caller from the truth store; :func:`fuse` does not read roles, it only preserves the separation). A
    genuine A↔B contradiction is FLAGged by
    :meth:`mnemosyne.production.memory.LivingMemory.reconcile` (D60-3), not resolved here.
    (3) **sensible-local over ALL** — sensitivity is the max over the three buckets, so working
    material carries its own sensitivity downstream exactly like an endorsed fact (D65 / D27)."""
    items = (*living, *documentary, *working_material)
    for env in items:
        if env.label.bubble != bubble:
            raise CloisonnementError(
                f"read fusion is bubble-scoped: a {env.label.bubble!r} result cannot fuse into "
                f"bubble {bubble!r} (invariant 3 / D65 / D54-8)"
            )
    sensitivity = max((env.label.sensitivity for env in items), default=Sensitivity.PUBLIC)
    return FusedAnswer(
        frame=tuple(living),
        facts=tuple(documentary),
        working_material=tuple(working_material),
        sensitivity=sensitivity,
    )
