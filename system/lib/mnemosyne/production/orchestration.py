"""E2 -- ONE CHAT PER ARC: the number of chats to launch, DERIVED, never hand-written.

The operator: *"three different chats, or one chat that sends out three agents?"* The item's answer:
the unit of parallelisation is the ARC (an item takes 1 to 3 gestures, the arc shares its context,
and the arc is already the format's unit -- D166). This module carries the only CALCULABLE part of
the doctrine: the number of chats, `min(the wave's width IN ARCS, the orchestrator's arbitration
capacity)`.

**TWO TERMS, TWO NATURES, and confusing them would be the mistake.** The first is MEASURED, live,
against the real plan (:func:`largeur_vague_en_arcs`, which reuses `ArcEtat.demarrable` -- B4/carte.py
-- never a second calculation). The second is NOT measured live: it is a USAGE observation, over a
time window already closed, that nothing in this repo can replay after the fact (a stale
acknowledgement cannot be re-measured). It is therefore FROZEN here, cited with its exact source
(:data:`CAPACITE_ARBITRAGE_PAR_TOUR`), instead of being guessed or recomputed from a signal that no
longer exists -- the same doctrine as `D3`'s floor: *X and N are never invented, they are PULLED from
a measurement, published together with what it measured*.

Code & docstrings: the domain vocabulary here is French (the item is read by the operator).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final

from .carte import carte_par_arc
from .plan_format import PlanReading

#: **CITED, NOT RE-MEASURABLE -- the night of 2026-08-15, narrated in the planning history
#: (item `E2`), and replayed here verbatim, never recalculated** (the orchestrator measures its own
#: turn cadence; this module has no access to that, and the window is closed either way):
#:
#: - **25 turns** that night, average **10.4 min**, max **22 min** -- a turn handles 1 to 3
#:   arbitrations.
#: - **At 3 chats** (the REAL state of this session, chat 1/2/3): half the acknowledgements were
#:   already reading a STALE posting (14 acknowledgements that night, most against a version that
#:   had already been replaced). *This ceiling is therefore not comfortable -- it is the point
#:   where the setup still holds, degraded.*
#: - **At 5 chats** (never tried, extrapolated in the item): turns would have gone from ~10 to
#:   ~17 min, and NO posting would still have been read up to date.
#:
#: **This constant does not prove that 3 is comfortable -- it proves that 3 is the point where
#: we measured, and that 5 breaks.** A future session that re-measures a different night may revise
#: it; it must never be recomputed on the fly from a signal this module cannot read.
CAPACITE_ARBITRAGE_PAR_TOUR: Final = 3


def largeur_vague_en_arcs(
    reading: PlanReading,
    *,
    arcs: Mapping[str, str] | None = None,
    faits: frozenset[str] | None = None,
) -> int:
    """How many distinct arcs carry AT LEAST ONE startable item today. PURE.

    **Reuses `ArcEtat.demarrable` (`carte_par_arc`, `B4`) -- recomputes nothing.** The same
    question ("what is startable?") answered twice by two separate homes would drift exactly the
    way `make carte` and a second reader already drifted apart elsewhere in this repo."""
    return sum(1 for arc in carte_par_arc(reading, arcs=arcs, faits=faits) if arc.demarrable)


def borne_chats(
    reading: PlanReading,
    *,
    arcs: Mapping[str, str] | None = None,
    faits: frozenset[str] | None = None,
) -> int:
    """The number of chats to launch, DERIVED -- `E2`'s `*Fini quand*`, word for word.

    ``min(the wave's width IN ARCS, what the ORCHESTRATOR can arbitrate per turn)``: the first term
    measured live against ``reading`` (:func:`largeur_vague_en_arcs`), the second frozen
    (:data:`CAPACITE_ARBITRAGE_PAR_TOUR`) -- no value hand-written inside THIS function, in the
    sense the item means: the calculation never guesses, it composes two named measurements."""
    return min(largeur_vague_en_arcs(reading, arcs=arcs, faits=faits), CAPACITE_ARBITRAGE_PAR_TOUR)
