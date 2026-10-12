"""I6 — can the loop say how many detected lessons were LOST, or only how many were found?

The dangerous failure here is not a wrong number, it is a number that reads as a measurement while
being an artefact of how often deposits happen. So the tests hold three things shut:

* the control cannot be skipped — the signature forbids it, and a test proves the signature bites;
* an empty population renders NOTHING rather than a table of zeros;
* the window is closed on both ends, because a deposit written in the same second as the block is
  the strongest case there is.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from mnemosyne.production.rendement import Rendement, Taux, mesurer, rendre


def t(minute: int) -> datetime:
    """A stamp, ``minute`` minutes after a fixed origin — no clock, so the tests never flake."""
    return datetime(2026, 8, 14, 12, 0, tzinfo=timezone.utc) + timedelta(minutes=minute)


UNE_HEURE = (timedelta(hours=1),)


# --- the number it exists to produce -----------------------------------------------------------
def test_a_signal_followed_by_a_deposit_counts_and_one_that_is_not_is_LOST() -> None:
    (r,) = mesurer([t(0), t(100)], [], [t(30)], fenetres=UNE_HEURE)

    assert r.avec_signal == Taux(suivis=1, total=2)
    assert r.avec_signal.perdus == 1  # the number I6 exists to make sayable
    assert r.avec_signal.part == 50.0


def test_the_gap_against_the_control_is_what_the_signal_BUYS() -> None:
    """Shaped like the first real shot: signals convert far better than ordinary task-ends."""
    signaux = [t(0), t(10), t(20), t(1000)]  # 3 of 4 near a deposit
    temoins = [t(500), t(600), t(700), t(800)]  # 0 of 4
    depots = [t(5), t(15), t(25)]

    (r,) = mesurer(signaux, temoins, depots, fenetres=UNE_HEURE)

    assert r.avec_signal.part == 75.0
    assert r.temoin.part == 0.0
    assert r.ecart == 75.0


def test_a_deposit_that_PRECEDES_the_signal_does_not_count() -> None:
    """Otherwise the loop credits itself with a lesson written before it said anything — and the
    yield would rise every time an unrelated fiche happened to land just before a task ended."""
    (r,) = mesurer([t(60)], [], [t(0)], fenetres=UNE_HEURE)

    assert r.avec_signal.suivis == 0


def test_the_window_is_CLOSED_on_both_ends() -> None:
    """A deposit in the same second as the block is the strongest possible case; a half-open
    interval would silently drop it, and `make remember` really does run seconds later."""
    (immediat,) = mesurer([t(0)], [], [t(0)], fenetres=UNE_HEURE)
    (pile,) = mesurer([t(0)], [], [t(60)], fenetres=UNE_HEURE)
    (trop_tard,) = mesurer([t(0)], [], [t(61)], fenetres=UNE_HEURE)

    assert immediat.avec_signal.suivis == 1
    assert pile.avec_signal.suivis == 1
    assert trop_tard.avec_signal.suivis == 0


# --- the control cannot be skipped: the barrier is the SIGNATURE -------------------------------
def test_the_control_population_is_impossible_to_omit() -> None:
    """The rule *"a rate without its control is a wall"* is written in three places in this repo
    and was violated the day after being written. Here it is enforced by the signature, not by
    prose: there is NO call that returns the with-signal rate alone.

    A rule that lives only in a docstring is a vow. This test is what makes it a barrier — remove
    the required argument and it goes red.
    """
    with pytest.raises(TypeError):
        mesurer([t(0)], depots=[t(1)])  # type: ignore[call-arg]


def test_the_gap_lives_on_the_pair_never_on_a_single_rate() -> None:
    """``ecart`` deliberately has no home on :class:`Taux`: a lone rate must not be able to
    pretend it means something."""
    assert not hasattr(Taux(1, 2), "ecart")
    assert hasattr(Rendement(timedelta(hours=1), Taux(1, 2), Taux(1, 4)), "ecart")


# --- an absence of measurement must not look like a measurement --------------------------------
def test_nothing_measured_renders_NOTHING_not_a_table_of_zeros() -> None:
    """A table of ``0/0`` reads as a result and is its opposite. Two absences of measurement compare
    equal — that is how a mechanism which never bites passes for one that holds."""
    assert rendre(mesurer([], [], [])) == ""
    assert rendre(()) == ""


def test_an_empty_population_does_not_divide_by_zero() -> None:
    assert Taux(0, 0).part == 0.0
    assert Taux(0, 0).perdus == 0


# --- what gets printed -------------------------------------------------------------------------
def test_the_block_prints_BOTH_populations_and_names_the_loss() -> None:
    bloc = rendre(mesurer([t(0), t(500)], [t(900), t(910)], [t(10)], fenetres=UNE_HEURE))

    assert "with signal" in bloc and "control" in bloc  # never one without the other
    assert "1/2" in bloc and "0/2" in bloc
    assert "produced NOTHING" in bloc  # the loss is named, not buried
    assert "never a reproach" in bloc  # obligation level 1: it constates
    assert "hollow entries" in bloc  # the trap is printed WITH the number it could corrupt


def test_the_LOST_count_carries_its_limit_IN_THE_BLOCK_not_in_the_source() -> None:
    """A reader of the command does not read the module's docstring.

    The "lost" count conflates a genuinely lost lesson with a task where the agent looked and there
    was correctly nothing to keep — the second being a GOOD outcome. Writing that in the source and
    not in the output would leave the only reader who sees the number mistake it for a measured
    loss. *The trap is published next to the number it could corrupt, never in a neighboring file.*
    """
    bloc = rendre(mesurer([t(0), t(500)], [t(900)], [t(10)], fenetres=UNE_HEURE))

    assert "UPPER BOUND" in bloc
    assert "correctly nothing to keep" in bloc  # the other half of the bucket is NAMED
    assert "GAP" in bloc  # and it says which number to cite instead


def test_the_published_curve_carries_several_windows_not_one_threshold() -> None:
    """A single window is a threshold, and a threshold picked by its author is picked to flatter.
    The curve is what shows the shape — including the gap collapsing at a day, which is the honest
    sign that this is an association and not a proof."""
    from mnemosyne.production.rendement import FENETRES

    assert len(FENETRES) >= 3
    assert len(mesurer([t(0)], [t(1)], [t(2)])) == len(FENETRES)


# --- the gate that covered only one case out of two ---------------------------------------------
def test_an_EMPTY_population_against_a_FULL_one_does_NOT_fabricate_a_gap() -> None:
    """The defect found by an isolated audit, and it FABRICATED a verdict.

    "With signal" population empty, control full: the gap came out at **−98.0 pts** — read as
    *"the detector is catastrophically counter-productive"*, from an ABSENCE of measurement.
    Reachable without malice: a fresh machine where the ritual fired without a single signal ever
    being detected gives exactly this shape.

    *Two absences of measurement compare equal* — this module said so and did the opposite.
    """
    (r,) = mesurer([], [t(0), t(10)], [t(5), t(15)], fenetres=UNE_HEURE)

    assert not r.comparable
    assert r.ecart is None  # not 0.0: a zero would be a measurement, and there isn't one
    assert r.temoin.part == 100.0  # the control, itself, is measured just fine


def test_the_block_says_NOT_MEASURABLE_instead_of_printing_a_number() -> None:
    """A `-98.0` drawn from nothing reads as a result. The block must refuse to write it."""
    bloc = rendre(mesurer([], [t(0), t(10)], [t(5)], fenetres=UNE_HEURE))

    assert "NOT MEASURABLE" in bloc
    assert "pts" not in bloc.split("is EMPTY")[0].split("|")[-1]  # no gap figure at all
    assert "it is not zero" in bloc  # and it says WHY
    assert "marker" in bloc  # and names the most likely cause


def test_the_gap_EXISTS_when_both_populations_are_populated() -> None:
    """The passing case, asserted: without it, a gate that refused EVERYTHING would still pass this
    file."""
    (r,) = mesurer([t(0)], [t(100)], [t(5)], fenetres=UNE_HEURE)

    assert r.comparable
    assert r.ecart == 100.0
