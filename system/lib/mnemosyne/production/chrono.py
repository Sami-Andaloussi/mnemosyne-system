"""``G7`` — the chrono invariant: **the budget starts AFTER the turn is obtained, never before**.

Harvested from a downstream project on 2026-09-08, item **G7**: *"otherwise **serialising would
make the gate MORE severe under contention**, not less"*. This is the canonical **wait vs service**
distinction; a budget that measures the **stay** (wait + service) is the recipe for a metastable
collapse — the more crowded it gets, the more everyone is refused, so the more everyone retries.

**WHAT THIS MODULE PROTECTED THE DAY IT WAS WRITTEN: NOTHING, AND THAT IS STATED.** Measured in
this repo before writing it:

    /usr/bin/grep -rn "LOCK_EX" --include='*.py' system/ scripts/ tests/ | grep -v LOCK_NB  ->  0

The repo's only lock (:mod:`mnemosyne.guard.heavy_lock`) is **non-blocking** (``LOCK_EX |
LOCK_NB``): it refuses right away, nobody ever waits their turn, so no budget straddles a wait.
**Zero sites.** This judge is therefore NOT a repair: it is the lesson engraved **before** the
defect is created — and the defect is born in the same batch, with
:mod:`mnemosyne.runtime.guetteur_commit` (item ``P5``), the first code in this repo to
**wait its turn**. This module is the judge that edge calls; without that edge, it would be a
barrier nothing calls, and it would have to be refused.

**The rule, in one line:** what gets judged is ``now - turn_obtained``. What gets **published**
without ever being judged is the stay ``now - request``. The wait has its **own** ceiling, which
is a scheduling decision, not a work budget.

**Two bounds, two natures — and confusing them is exactly ``G7``'s fault:**

- the **wait ceiling** says "I give up waiting" — it grows with contention, that is normal, and
  crossing it does not accuse the work;
- the **service budget** says "this particular piece of work costs too much" — it must owe
  **nothing** to contention. Measuring it in CPU time rather than wall time is the complementary
  half (:mod:`mnemosyne.production.budget_porte`, item ``G12``).

**PURE JUDGE**: no clock is read here, no disk, no ``os.environ``. The instants are
**injected** — they come from a **monotonic** clock (:func:`time.monotonic`), never from
``datetime.now``: a wall clock can go backwards (NTP, a time-zone change) and would produce a
negative service. *A judge that fetches its own time cannot be put to the test under contention.*

Code & docstrings English (D117). Decisions carried: D159 (a wall declares itself) · invariant 16
(a bound REFUSES).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

#: The turn was never obtained — the wait ate up its whole ceiling.
ATTENTE_DEPASSEE = "attente_depassee"
#: The WORK, once the turn was obtained, exceeded its budget. The only refusal that accuses the work.
SERVICE_DEPASSE = "service_depasse"
#: Instrument failure: the instants are not ordered (a clock going backwards, or two different
#: clocks mixed together). **This is neither a pass nor a work refusal** — it is an admission.
CHRONO_INCOHERENT = "chrono_incoherent"
#: Instrument failure: a zero or negative bound. A budget of ``0`` would refuse all work, a
#: negative budget makes no sense; both are a wiring error, never a verdict.
BORNE_ABSURDE = "borne_absurde"


@dataclass(frozen=True, slots=True)
class Chrono:
    """The three instants of one turn, on a **monotonic** clock, and the two bounds that judge them.

    ``tour_obtenu`` is ``None`` as long as the turn has not been obtained — and that is the case
    that matters: a watcher that gives up has no service to judge, only a wait.
    """

    #: Instant when the turn was REQUESTED (start of the wait queue).
    demande: float
    #: Instant when the turn was OBTAINED — ``None`` if it never was.
    tour_obtenu: float | None
    #: Instant of the measurement.
    maintenant: float
    #: How long we accept WAITING for our turn. Legitimately grows with contention.
    plafond_attente_s: float
    #: How much the WORK is allowed to cost, once the turn is obtained. Owes nothing to contention.
    budget_service_s: float


@dataclass(frozen=True, slots=True)
class Refus:
    """A named refusal, with the figure that produced it and the bound it crossed."""

    genre: str
    mesure_s: float
    borne_s: float


def attente_s(chrono: Chrono) -> float:
    """The time spent WAITING for one's turn.

    If the turn was never obtained, we are **still** waiting: the wait runs up to ``maintenant``.
    """
    fin = chrono.tour_obtenu if chrono.tour_obtenu is not None else chrono.maintenant
    return fin - chrono.demande


def service_s(chrono: Chrono) -> float | None:
    """**THE LINE THAT IS ``G7``** — the WORK time, counted from the turn OBTAINED.

    ``None`` when the turn was never obtained: there is then **nothing** to judge on the work side,
    and returning ``0.0`` would lie in the other direction (work never started would pass for
    instantaneous).

    The one-character mutant is ``chrono.maintenant - chrono.demande``: it compiles, it returns a
    plausible number, and it turns serialising into a hardening of the gate. It is frozen by
    ``test_chrono.py`` with a population where the wait dominates the service.
    """
    if chrono.tour_obtenu is None:
        return None
    return chrono.maintenant - chrono.tour_obtenu


def sejour_s(chrono: Chrono) -> float:
    """The total stay (wait + service) — **PUBLISHED, NEVER JUDGED**.

    This is the figure a human wants to see ("how long did that take?") and exactly the one no
    bound must read. It lives here so the edge does not have to recompute it and get the
    subtraction wrong while doing so.
    """
    return chrono.maintenant - chrono.demande


def verdict(chrono: Chrono) -> tuple[Refus, ...]:
    """The refusals, in order: inconsistency, absurd bound, wait, then service.

    **THE ORDER DECIDES WHAT GETS JUDGED.** A clock inconsistency placed first prevents
    publishing a "service exceeded" that would only be a measurement artefact — *the order of the
    checks decides the named cause*. And the two instrument failures come out ALONE: letting them
    coexist with a work refusal would suggest the work was judged when it was not.
    """
    if chrono.plafond_attente_s <= 0 or chrono.budget_service_s <= 0:
        borne = min(chrono.plafond_attente_s, chrono.budget_service_s)
        return (Refus(BORNE_ABSURDE, mesure_s=0.0, borne_s=borne),)
    fin_attente = chrono.tour_obtenu if chrono.tour_obtenu is not None else chrono.maintenant
    if fin_attente < chrono.demande or chrono.maintenant < fin_attente:
        return (Refus(CHRONO_INCOHERENT, mesure_s=sejour_s(chrono), borne_s=0.0),)

    refus: list[Refus] = []
    attendu = attente_s(chrono)
    if attendu > chrono.plafond_attente_s:
        refus.append(Refus(ATTENTE_DEPASSEE, mesure_s=attendu, borne_s=chrono.plafond_attente_s))
    servi = service_s(chrono)
    if servi is not None and servi > chrono.budget_service_s:
        refus.append(Refus(SERVICE_DEPASSE, mesure_s=servi, borne_s=chrono.budget_service_s))
    return tuple(refus)


def resume(chrono: Chrono, refus: Sequence[Refus]) -> str:
    """The published sentence — it ALWAYS separates the three figures, even when nothing is refused.

    **Why the stay is written even though it is never judged**: without it, a reader who sees
    "service 0.4 s, OK" on a command that took 40 seconds thinks there is a display bug and goes
    looking for the real duration elsewhere — that is, in a second source, free to diverge.
    """
    servi = service_s(chrono)
    tete = (
        f"wait {attente_s(chrono):.2f} s (ceiling {chrono.plafond_attente_s:.2f} s) · "
        + (
            f"service {servi:.2f} s (budget {chrono.budget_service_s:.2f} s)"
            if servi is not None
            else "service NOT STARTED (turn never obtained)"
        )
        + f" · stay {sejour_s(chrono):.2f} s (published, never judged)"
    )
    if not refus:
        return tete + "\nOK — the service budget only started at the turn obtained (G7)."
    lignes = [tete, "REFUSALS:"]
    for r in refus:
        if r.genre == ATTENTE_DEPASSEE:
            lignes.append(
                f"  - {r.genre}: {r.mesure_s:.2f} s of wait for a ceiling of "
                f"{r.borne_s:.2f} s — contention, never the work."
            )
        elif r.genre == SERVICE_DEPASSE:
            lignes.append(
                f"  - {r.genre}: {r.mesure_s:.2f} s of work for a budget of "
                f"{r.borne_s:.2f} s — counted from the turn obtained, the wait does not enter into it."
            )
        elif r.genre == CHRONO_INCOHERENT:
            lignes.append(
                f"  - {r.genre}: instants out of order (stay {r.mesure_s:.2f} s) — instrument "
                "failure, not a verdict on the work."
            )
        else:
            lignes.append(
                f"  - {r.genre}: bound at {r.borne_s:.2f} s — a zero or negative budget refuses "
                "everything; that is wiring to fix, not a verdict."
            )
    return "\n".join(lignes)
