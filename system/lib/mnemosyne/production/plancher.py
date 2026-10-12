"""THE PRODUCTION FLOOR (D3) -- an INVERTED ratchet, the only one that refuses EXCESS rigor.

Every other ratchet in this repo refuses REGRESSION. This one refuses EXCESS RIGOR:
*"while we're busy hardening, we stop moving on everything else"* (the project's owner). This is
the mechanism that would have screamed on July 21-22, 2026, when the project swung into an
adversarial audit regime and never came back out -- twenty days, without a single check ever
turning red.

 **Its shape is what keeps it from being punitive**: below the floor, you can no longer OPEN a
new HARDENING workstream; OPENING a PRODUCT workstream stays always allowed (exactly what you
want to encourage when the product share is low); CLOSING whatever is already open stays ALWAYS
allowed. *You are never stopped from finishing, nor from producing; you are only stopped from
opening ONE MORE of what is not the product.*

## OPENING is DECLARED, never CLASSIFIED (D75 audit, corrected here)

An early version of this module refused ANY opening below the floor, hardening or product alike --
broader than what the clause asks for (the project's internal planning notes, D3: *"a hardening
workstream is refused"*, never *"any workstream"*). Building a classifier that INSPECTS a
workstream to guess its nature would have been the exact fault `D2` already forbids elsewhere in
this repo: *the product is DECLARED BY THE PROJECT, it is never guessed*. The same doctrine
applies here, applied to the GESTURE rather than the path: the caller opening a workstream
DECLARES which of the two it is opening (`ouvrir_blindage` or `ouvrir_produit`); this module
classifies nothing, it trusts the declaration -- exactly as `human_gate.py` (I7) trusts the
mechanism the caller says it observed rather than guessing it itself.

## X and N are not invented (A4 / the D165 test)

No ceiling without "what breaks without it". The real curve (PAR_LIGNE, denominator BOUNDED to
the measured project -- see ``mnemosyne.runtime.plancher_run``, and the correction below -- on
`projects/.git`, 2026-07-15 through 29, reproduced live, not copied from a document):

 Jul 15 79.8% Jul 20 82.6% Jul 21 31.7% Jul 22 5.8% Jul 23 20.0%
 Jul 24 0.0% Jul 25 4.1% Jul 26 0.0% Jul 27 0.6% Jul 28 3.6%
 Jul 29 0.0%

 **CORRECTION (D75 audit, 2026-08-15) -- this module's first derivation rested on a
MEASUREMENT ARTIFACT, not a real drift.** `PAR_LIGNE` (`plan_derive.py`) sums the lines of ALL
paths touched in a turn into the denominator, without bounding them to the measured project. July
15 carries only one commit: the initial bulk import of ALL of `projects/` (`746972a`, 291,679
lines, one sub-project alone accounting for 49,980 of them). Unbounded denominator: **13.7%** -- an early
version of this module read that number as "July 15 is not a drift, and that is the proof that N
must be >= 2". **That was a misreading: the number itself was wrong.** Denominator bounded to the
project (what `plancher_run.py` now computes BEFORE calling `PAR_LIGNE`, without touching
`PAR_LIGNE` itself -- a function shared from D1, outside this batch): **79.8%** -- identical to
the figure published in the project's internal lifecycle notes. July 15 is NOT a low day: it is a
HEALTHY day, mismeasured by a function that was never designed for a turn touching several
projects at once.

Corrected, the curve no longer carries ANY false positive, for ANY X in the sweep -- **N=1 is
legitimate**. And the repo says so itself, three times, before this module ever existed: *"the
production floor... the signal that would have screamed on July 22"* (the project's internal
planning notes, D5, and the lifecycle-notes doc, section 6). **X=30, N=1**: July 21 (31.7%) stays
above the floor (first day of the audit, still ambiguous); July 22 (5.8%) crosses it immediately
-- exactly the day the repo had been waiting for since before this module was written. Full sweep
published in the project's internal governance notes.

## This module is a PURE judge

It reads neither git nor the disk: the edge (``runtime/plancher_run.py``) hands it the series of
:class:`~mnemosyne.production.plan_derive.Jour` already built by D1/D2, denominator already
bounded to the measured project. *A judge that goes and fetches its own population can find it
empty and return a green.*

 **LEVEL 2 -- the only thing that refuses in this arc, and it is deliberate** (*Obligation* of
D3). Refusing a HARDENING OPENING below the floor is the gesture; refusing a PRODUCT OPENING or a
CLOSING is never a gesture this module can make.

Decisions: D1 (the two ratchets) - D2 (the product declared by the project, applied here to the
gesture) - A4/D165 (no ceiling without what breaks without it) - inv. 2 (non-destructive -- a
refused opening is PUBLISHED, never erased). French prose (D117).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from .plan_derive import Jour

#: Derived from the real curve, denominator bounded to the project (see the module docstring and
#: the audit correction) -- never picked by eyeballing it. X=30 cleanly separates the healthy
#: floor (79.8/82.6%) from the audit regime (<=31.7% on day one, <=20% after).
X_PLANCHER: float = 30.0
#: N=1: legitimate since the denominator correction (see docstring) -- no more false positives
#: across the 8 sampled X values (the project's internal governance notes), and it makes the gate
#: scream exactly on the day the repo had been waiting for (July 22), not one day late.
N_PLANCHER: int = 1

#: The three gestures this module knows how to judge. OPENING is DECLARED (hardening or product),
#: never GUESSED -- see the "OPENING is DECLARED" section of the module docstring. Any other
#: value is a caller inventing a fourth gesture this gate never promised to know.
Geste = Literal["ouvrir_blindage", "ouvrir_produit", "fermer"]


@dataclass(frozen=True, slots=True)
class Plancher:
    """The floor's state at instant T -- never a bare boolean, it carries what produced it."""

    franchi: bool
    x: float
    n: int
    #: The last ``n`` shares (%), in chronological order -- what a publication must show so a
    #: reader can re-verify the verdict without re-running the computation.
    recentes: tuple[float, ...]


def lire_plancher(
    jours: Sequence[Jour], *, x: float = X_PLANCHER, n: int = N_PLANCHER
) -> Plancher:
    """Is the floor crossed RIGHT NOW -- the last ``n`` :class:`Jour`, ALL below ``x``%.

 **Fewer than ``n`` measured days: never crossed.** A series too short to judge is not proof
 of excess rigor -- it is an absence of data, and an absence of data must never read as a
 refusal (same rule as :func:`~mnemosyne.production.plan_derive.plus_grande_chute` on
 ``j.total``, or an UNMEASURED population elsewhere in this repo).

 ``jours`` must already be in CHRONOLOGICAL order (that is what
 :func:`~mnemosyne.production.plan_derive.part_produit` returns) -- this judge does not sort,
 it reads.

 **``jours`` must already carry a denominator BOUNDED TO THE measured project** -- this
 judge does not know that and cannot verify it; it is up to the edge
 (:mod:`~mnemosyne.runtime.plancher_run`) to guarantee it before calling this function (see the
 audit correction in the module docstring).
 """
    if n < 1:
        raise ValueError(f"n must be >= 1, got {n!r} -- a floor over zero days judges nothing")
    if len(jours) < n:
        return Plancher(franchi=False, x=x, n=n, recentes=tuple(j.part * 100 for j in jours))
    derniers = jours[-n:]
    recentes = tuple(j.part * 100 for j in derniers)
    return Plancher(franchi=all(p < x for p in recentes), x=x, n=n, recentes=recentes)


def decision(geste: Geste, plancher: Plancher) -> bool:
    """``True`` = the gesture is ALLOWED. The only possible refusal: OPENING A HARDENING
 workstream while the floor is crossed.

 **``ouvrir_produit`` and ``fermer`` ALWAYS return ``True``, whatever the floor's state --
 non-negotiable.** This is the clause that keeps this ratchet non-punitive AND that stops it
 from refusing exactly what it should be encouraging: *you are never stopped from finishing,
 nor from producing*. A floor that also refused product work or closings would no longer be an
 inverted ratchet, it would be a total block -- the shape the project's owner explicitly ruled
 out (*"without it becoming punitive"*), and one that would delay the very return to production
 the floor exists to provoke.
 """
    if geste in ("fermer", "ouvrir_produit"):
        return True
    if geste == "ouvrir_blindage":
        return not plancher.franchi
    raise ValueError(
        f"unknown gesture: {geste!r} -- this gate only knows "
        "'ouvrir_blindage'/'ouvrir_produit'/'fermer'"
    )
