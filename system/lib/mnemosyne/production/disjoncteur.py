"""G2 -- THE CIRCUIT BREAKER: on the 3rd consecutive negative verdict we ANNOUNCE, on the 4th we SPLIT.

Brought back from a 2026-09-08 harvest on another project (item `G2`, tested **twice** there). **What it
closes is the class D75 leaves open**: `D75` says **WHO** judges (never the producer); **nothing
said WHEN TO STOP REPAIRING.** An item repaired indefinitely doesn't have a defect, it has a SIZE.

Three properties set it apart from an ordinary circuit breaker, and all three live in the code:

1. **The threshold is written in ADVANCE** (:data:`SEUIL_ANNONCE`, :data:`SEUIL_DECOUPE`) -- so it
   is not negotiable under the pressure of the moment it bites. A threshold computed on the current
   population (as `routage_journal.taux_de_reprise` deliberately does, for a different question)
   would drift together with the very failure it is supposed to name.
2. **The trigger is a RE-SPLIT, not an abandonment** -- the law of small batches, not a veto.
3. **Closure is BOUNDED**: three attempts, then the shape of the problem changes.

**WHAT "NEGATIVE VERDICT" MEANS HERE, AND THE ADMISSION THAT GOES WITH IT.** This repository has
**NO structured verdict registry**: audit verdicts live in PROSE, in commit messages and station
logs. This module therefore does not claim to read them. It reads the **substitute** the repository
has already frozen for a different measurement: a `fix(IDENT)` commit **is** the material trace of a
negative verdict -- it exists only because something came back negative. Only the three TURN types
(:data:`~.routage_journal.TYPES_DE_TOUR`) are counted; `docs`/`plan`/`orch` are TRANSPARENT (they
neither accumulate nor reset: an orchestrator narrating isn't an attempt), and `feat`/`test` RESET TO
ZERO (a fresh build isn't a repair).

**The limitation, spelled out**: an item repaired three times WITHOUT A COMMIT (within a single
session) is invisible here, and a `fix` that corrects a typo counts exactly as much as a `fix` that
answers an audit. *Neither perfect nor hidden* -- exactly the stance `routage_journal` already takes
on the same data.

## The population, measured through THE REPOSITORY'S OWN ACCESSOR (2026-09-08, `commits_par_ident`)

```
idents seen by the accessor                                  : 89
   with a CURRENT negative streak >= 3 (we ANNOUNCE)          :  9
   with a CURRENT negative streak >= 4 (we SPLIT)              :  4
```

`H5` leads with **9 consecutive repairs** over 10 turns -- and it's the item whose history carries
`retractation(H5): the isolated audit finds it NOT UPHELD, and it is right`. *The circuit breaker
would have named H5 on its 3rd turn; it took six more turns and a retraction to reach the same
place.*

**A CLOSED ITEM NEVER TRIGGERS.** The circuit breaker speaks about work IN PROGRESS; naming an
already-closed item would create permanent noise and turn a gate into a complaint. That's why this
judge takes ITEMS and not just commits.

PURE judge: injected population, no disk, no `git`, no `os.environ`. Prose is French in the private
repository (D117); translated to English here for the public mirror.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from .plan_format import PlanItem
from .routage_journal import Commit, STATUTS_FERMES, TYPES_DE_TOUR

#: **WRITTEN IN ADVANCE, AND THAT'S HALF THE MECHANISM.** A threshold chosen at the moment it
#: bites isn't a threshold. These two numbers come from another project, where the rule was proven twice
#: (`GATE-P1`, code proven to bite 58/58 -- *it was the PROSE that fell short*; `A02-11`, 47/47).
SEUIL_ANNONCE: Final = 3
#: The 4th consecutive negative verdict no longer asks for a repair: it asks for a RE-SPLIT.
SEUIL_DECOUPE: Final = 4

#: The three gestures, frozen as a SET -- swapping two labels would leave the count identical.
GESTE_RIEN: Final = "rien"
GESTE_ANNONCER: Final = "annoncer"
GESTE_DECOUPER: Final = "decouper"
GESTES: Final[frozenset[str]] = frozenset({GESTE_RIEN, GESTE_ANNONCER, GESTE_DECOUPER})


@dataclass(frozen=True, slots=True)
class Etat:
    """The circuit breaker's state for ONE item: its current negative streak and the gesture it calls for.

    ``tours`` is the total number of TURNS seen (`feat`/`fix`/`test`), published next to the streak
    because a streak of 3 out of 3 turns and a streak of 3 out of 23 turns don't tell the same
    story -- *a rate without its population kills a good design*."""

    ident: str
    serie: int
    tours: int
    geste: str


def serie_negative(commits: tuple[Commit, ...]) -> int:
    """The **CURRENT** negative-verdict streak -- the tail, never the historical maximum.

    **A CIRCUIT BREAKER SPEAKS ABOUT THE PRESENT.** The historical maximum would say "this item
    suffered once"; the current streak says "it is suffering now, and here is for how many turns."
    A `feat` or a `test` resets it because those are FRESH attempts; the three types outside
    :data:`~.routage_journal.TYPES_DE_TOUR` are transparent and don't touch it."""
    serie = 0
    for commit in commits:
        if commit.type not in TYPES_DE_TOUR:
            continue
        serie = serie + 1 if commit.type == "fix" else 0
    return serie


def geste_pour(serie: int) -> str:
    """The gesture a streak calls for. Both thresholds are read with ``>=`` and in THIS order:
    testing ``SEUIL_ANNONCE`` first would return "announce" for a streak of 7."""
    if serie >= SEUIL_DECOUPE:
        return GESTE_DECOUPER
    if serie >= SEUIL_ANNONCE:
        return GESTE_ANNONCER
    return GESTE_RIEN


def disjoncteur(
    items: tuple[PlanItem, ...], commits_par_ident: dict[str, tuple[Commit, ...]]
) -> tuple[Etat, ...]:
    """The OPEN items for which the circuit breaker has tripped, in plan order.

    An item whose ``status`` is in :data:`~.routage_journal.STATUTS_FERMES` is **discarded before
    any calculation**: the circuit breaker judges work in progress. An item with no known commit is
    not a trigger either -- an absence of trace is an absence, never a zero."""
    declenches: list[Etat] = []
    for item in items:
        if not item.ident or item.status in STATUTS_FERMES:
            continue
        commits = commits_par_ident.get(item.ident, ())
        serie = serie_negative(commits)
        geste = geste_pour(serie)
        if geste == GESTE_RIEN:
            continue
        tours = sum(1 for c in commits if c.type in TYPES_DE_TOUR)
        declenches.append(Etat(ident=item.ident, serie=serie, tours=tours, geste=geste))
    return tuple(declenches)


def ouverts(items: tuple[PlanItem, ...]) -> int:
    """The number of items actually EXAMINED -- the denominator :func:`resume` publishes. It lives
    here, next to the filter it counts, so a filter change never leaves yesterday's denominator
    sitting next to today's numerator."""
    return sum(1 for item in items if item.ident and item.status not in STATUTS_FERMES)


def a_decouper(etats: tuple[Etat, ...]) -> tuple[Etat, ...]:
    """Those who crossed the SECOND threshold -- the only sub-population that justifies a REFUSAL."""
    return tuple(e for e in etats if e.geste == GESTE_DECOUPER)


def resume(etats: tuple[Etat, ...], *, juges: int) -> str:
    """The published text. ``juges`` is the number of OPEN items actually examined: without it,
    "no trigger" on zero items reads exactly like "no trigger" on sixty -- *an equality on an empty
    pair is true by construction*."""
    entete = (
        f"circuit breaker: {juges} open item(s) examined, thresholds {SEUIL_ANNONCE}/{SEUIL_DECOUPE}"
    )
    if not etats:
        return f"\U00002705 {entete} — no trigger.\n"
    lignes = [f"\U000026A0\U0000FE0F {entete} — {len(etats)} trigger(s):"]
    for e in etats:
        if e.geste == GESTE_DECOUPER:
            lignes.append(
                f"   \U000026D4 {e.ident}: {e.serie} negative verdicts in a row over {e.tours} turn(s) — "
                "SPLIT the item, stop repairing it (an item repaired 4 times has a SIZE, not a defect)"
            )
        else:
            lignes.append(
                f"   \U0001F4E3 {e.ident}: {e.serie} negative verdicts in a row over {e.tours} turn(s) — "
                "ANNOUNCE it now; next time, we split"
            )
    return "\n".join(lignes) + "\n"
