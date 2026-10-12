"""Did a detected lesson ever get DEPOSITED? — the yield of the learning loop (I6).

``review_signals`` detects, ``render_review`` prints, and there the chain stops. An agent that reads
the block and deposits nothing leaves **exactly the trace of an agent that received nothing**. So
the one question that says whether any of it is worth its attention — *how many detected lessons
were lost?* — had no answer, only opinions.

**It has one now, and it was measurable all along.** Same lesson as its sibling ``delegations``,
learnt twice the same day: the premise said *"nothing records this"*; three minutes of measurement
said the host writes the injected block into the transcript, and the deposit side is a git history.
Nothing to build, something to READ.

**A yield without its CONTROL is a wall, and the API makes the wall impossible.** 80% of signals
followed by a deposit within a day proves nothing on its own: deposits are frequent, so almost any
moment is "followed by a deposit". :func:`mesurer` therefore takes BOTH populations and returns
both rates — there is no call that yields one without the other. *That is the barrier this module
owes to the rule it was written under; the rule alone would have been a vow.*

The control is the honest one: **task-ends where the hook fired its ritual but detected NO signal.**
Same boundary, same instant, same kind of moment — the single difference is the signal. First shot,
2026-08-14, over every transcript on this machine (55 task-ends with a signal, 1,892 without,
122 deposits):

===========  ======================  ======================  ==========
window       with signal             control                 gap
===========  ======================  ======================  ==========
15 min       **36.4%** (20/55)       8.4% (158/1892)          **+28.0**
60 min       47.3% (26/55)           15.7% (297/1892)         +31.6
4 h          60.0% (33/55)           27.1% (513/1892)         +32.9
24 h         80.0% (44/55)           62.3% (1178/1892)        +17.7
===========  ======================  ======================  ==========

Two readings, and both matter. **The detector works**: it more than quadruples the deposit rate at
the fifteen-minute scale, which is the first evidence that D155 buys anything at all. **And the loss
is real**: at one hour, **29 of 55 signals produced nothing** — that is what I6 exists to name.

**THE LOSS FIGURE IS AN UPPER BOUND, NOT A LOSS — and this is a declared hole, not an oversight.**
*"29 of 55 signals produced nothing"* conflates two things this module cannot tell apart: a lesson
genuinely lost, and **a task where the agent looked and there was correctly nothing to keep**. The
second is a legitimate outcome — the block says so in as many words — but **nothing traces it**, so
it lands in the same bucket as the first. Two contributors are already measured: the detector's own
false-positive rate (2 of 30 read firings) and every honest *"rien de durable"*.

Closing it means a task that concludes *"nothing to keep"* leaving a trace as valid as a deposit —
the second half of I6's own finish condition, **which is not built**. It was closed on the printed
sentence, not on a mechanism, and saying otherwise would be the exact over-declaration this whole
arc exists to undo. *The GAP against the control survives it* (the control population carries the
same conflation), which is why the gap is the number worth reading and the raw loss is not.

**What this is NOT.** An association, never a cause: a deposit that follows a signal was not
necessarily caused by it. The control is what makes the number worth reading, and the shrinking gap
at 24 h — where everything ends up near a deposit — is the shape that confirms the method rather
than a result to quote. And it must never become a target: *a deposits/signals ratio is trivially
maximised by depositing rubbish*, which is why nothing here refuses, blocks, or scores an agent.
Obligation level 1: it CONSTATES.

Decisions: D155 · D92 (propose, never impose — a hook that demanded an entry would manufacture
entries) · invariant 1 (transcripts are read locally, nothing is sent anywhere) · invariant 2
(read-only) · D126 (stdlib).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Final

#: The windows the first shot published. Several on purpose: a single window is a threshold, and a
#: threshold picked by its author is picked to flatter. Publishing the curve shows the shape — here,
#: a gap that peaks at four hours and collapses at a day, which is what an honest association does.
FENETRES: Final = (
    timedelta(minutes=15),
    timedelta(hours=1),
    timedelta(hours=4),
    timedelta(days=1),
)


@dataclass(frozen=True, slots=True)
class Taux:
    """One rate: how many of ``total`` moments were followed by a deposit."""

    suivis: int
    total: int

    @property
    def part(self) -> float:
        """The rate in percent — ``0.0`` on an empty population rather than a division error.

        An empty population is a real state (a machine that has never fired a signal), and it must
        read as "nothing measured", never crash the caller that prints it.
        """
        return 100.0 * self.suivis / self.total if self.total else 0.0

    @property
    def perdus(self) -> int:
        """Those that produced NOTHING — the number I6 exists to make sayable."""
        return self.total - self.suivis


@dataclass(frozen=True, slots=True)
class Rendement:
    """One window, both populations. Never one without the other."""

    fenetre: timedelta
    avec_signal: Taux
    temoin: Taux

    @property
    def comparable(self) -> bool:
        """True only when BOTH populations have members. A rate over nothing is not zero.

        **Found by an isolated audit, and it fabricated a verdict.** With an empty signal
        population and a full control, :attr:`ecart` returned **−98.0 points** — read as *"the
        detector is catastrophically counter-productive"*, from an ABSENCE of measurement. And it
        was reachable without malice: a fresh machine where the ritual fired but nothing was ever
        detected, or a reworded block header, both give ``avec_signal`` = 0 against ~1,900 controls.
        *Two absences of measurement compare equal* — this module says so and did the opposite.
        """
        return bool(self.avec_signal.total and self.temoin.total)

    @property
    def ecart(self) -> float | None:
        """Percentage points bought by the signal, or ``None`` when it cannot be computed.

        **This is the only number worth reading**, and it cannot exist without the control — which
        is why it lives here and not on :class:`Taux`. It returns ``None`` rather than ``0.0`` on an
        incomparable pair: a zero would be a measurement, and there isn't one.
        """
        if not self.comparable:
            return None
        return self.avec_signal.part - self.temoin.part


def _suivis(moments: Sequence[datetime], depots: Sequence[datetime], fenetre: timedelta) -> int:
    """How many moments have at least one deposit in ``[moment, moment + fenêtre]``.

    Bounds are CLOSED on both sides: a deposit written in the same second as the block was injected
    is the strongest possible case, and a half-open interval would drop it. Measured shape, not a
    guess — ``make remember`` runs seconds after the block is read.
    """
    return sum(1 for moment in moments if any(moment <= d <= moment + fenetre for d in depots))


def mesurer(
    avec_signal: Sequence[datetime],
    temoin: Sequence[datetime],
    depots: Sequence[datetime],
    *,
    fenetres: Sequence[timedelta] = FENETRES,
) -> tuple[Rendement, ...]:
    """The yield of the loop, one :class:`Rendement` per window.

    **Both populations are REQUIRED positional arguments, and that is the barrier.** The rule
    *"a capture rate without its false-accusation rate is a wall"* is written in three places in
    this repo and was violated the day after being written. Here it cannot be: there is no call
    that returns the with-signal rate alone. A rule enforced by a signature outlives a rule
    enforced by a docstring.

    ``avec_signal`` — task-ends where the hook DETECTED something.
    ``temoin`` — task-ends where it fired its ritual and detected nothing. Same boundary, same
    instant, same kind of moment: the only difference is the signal, which is what makes the gap
    attributable to the signal rather than to the hour of the day.
    ``depots`` — when a lesson actually landed (a memory commit, a ``make remember`` entry).
    """
    return tuple(
        Rendement(
            fenetre=fenetre,
            avec_signal=Taux(_suivis(avec_signal, depots, fenetre), len(avec_signal)),
            temoin=Taux(_suivis(temoin, depots, fenetre), len(temoin)),
        )
        for fenetre in fenetres
    )


def _duree(fenetre: timedelta) -> str:
    """A window in the shortest honest unit. (English in this public mirror; the private deployment
    prints it in French for its operator.)"""
    minutes = int(fenetre.total_seconds() // 60)
    if minutes % 1440 == 0:
        return f"{minutes // 1440} d"
    if minutes % 60 == 0:
        return f"{minutes // 60} h"
    return f"{minutes} min"


def rendre(rendements: Sequence[Rendement]) -> str:
    """The published table. Empty string when nothing was measured — never a table of zeros.

    A table full of ``0/0`` reads as a measured result and is the opposite: it is the absence of a
    measurement. Two absences of measurement compare equal, and that is how a mechanism that never
    bites passes for a mechanism that holds.
    """
    if not rendements or not any(r.avec_signal.total or r.temoin.total for r in rendements):
        return ""
    lignes = [
        "[Mnemosyne · loop yield] How many DETECTED lessons led to a DEPOSIT — "
        "and the same count on task-ends where nothing was detected (without this control, "
        "the first number means nothing):",
        "",
        f"  {'window':>8} | {'with signal':>19} | {'control':>19} | gap",
    ]
    for r in rendements:
        a, t = r.avec_signal, r.temoin
        # An incomparable pair does NOT print a number. A `+0.0` or a `-98.0` drawn from an
        # empty population reads as a result; it is an absence. We SAY so.
        ecart = f"{r.ecart:+6.1f} pts" if r.ecart is not None else "NOT MEASURABLE"
        lignes.append(
            f"  {_duree(r.fenetre):>8} | {a.suivis:>4}/{a.total:<4} {a.part:5.1f}% "
            f"| {t.suivis:>4}/{t.total:<4} {t.part:5.1f}% | {ecart}"
        )
    lignes.append("")
    if any(not r.comparable for r in rendements):
        lignes.append(
            "\U000026D4 One of the two populations is EMPTY: the gap does not exist, it is not zero. "
            "Most likely cause — the marker being searched for in the transcripts no longer "
            "matches, NOT \"the loop no longer detects anything\". Both read the same on a table."
        )
        lignes.append("")
    reference = rendements[min(1, len(rendements) - 1)]
    lignes.append(
        f"At {_duree(reference.fenetre)}, {reference.avec_signal.perdus} signal(s) out of "
        f"{reference.avec_signal.total} produced NOTHING. This is a statement of fact, never a "
        "reproach: a task where there was nothing worth keeping MUST end without a deposit, and a "
        "rate someone tried to push up would fill with hollow entries."
    )
    # The upper bound is printed WITH the number, never only in the source. A reader of the
    # command does not read the module's docstring: leaving them "45 lost" without its limit lets
    # them believe a measured loss where there is only a ceiling. *The trap is published next to
    # the number it could corrupt, not in a neighboring file.*
    lignes.append(
        f"\U000026D4 And this {reference.avec_signal.perdus} is an UPPER BOUND, never the loss: nothing "
        "here distinguishes a lost lesson from a task where the agent looked and there was "
        "correctly nothing to keep. Both fall into the same bucket, and the second is a GOOD "
        "outcome. It is the GAP against the control that should be cited — it survives this "
        "confusion, since the control carries it too."
    )
    return "\n".join(lignes)
