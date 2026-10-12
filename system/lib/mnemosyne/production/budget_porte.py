"""``G12`` — a gate's budget is measured in **CPU** time, never **WALL-CLOCK**, and bounded **PER
UNIT**, never as a total.

The flagship project's harvest, 2026-09-08, item **G12**. At the flagship project, the same gate on the **same content**
returned *"207-322 s REFUSE while 119-158 s pass"*: **the verdict was not a function of the
commit**, and the escape hatch was one word away (``--no-verify``). A gate whose verdict depends
on who else is working on the machine is not a gate, it's a die roll.

**I DID NOT REUSE THE FLAGSHIP PROJECT'S FIGURE — I RE-MEASURED IT HERE**, because a borrowed verdict expires
silently and because a timing measurement taken over three short windows says nothing about the
cumulative picture. Protocol, on **the population this module protects** (the body of the
``.githooks/pre-commit`` gate, lines 192-665, the only Python compute work on the commit path):

* **path population**: ``310`` commits out of ``1715`` (30 days) involve a plan or
  the end-of-session summary and therefore pay this cost — the other ``1405`` exit with ``exit 0``
  before any Python call runs;
* **protocol**: **10 INTERLEAVED pairs** — for each pair, one free run then the same run with
  **20 added CPU burners** (10-core machine, 1-minute load average from 5.7 to 18.6). Interleaving
  cancels out the background-load drift, which I do not control on this machine;
* **statistic reported**: the **median of the paired ratios** — no arbitrary threshold.

.. code-block:: text

    MEDIAN RATIO loaded/free :   WALL x1.80      CPU x1.28
    wall ratios sorted : 1.58 1.60 1.78 1.79 1.79 1.81 1.85 1.88 1.91 2.17
    cpu  ratios sorted : 1.13 1.18 1.20 1.21 1.27 1.29 1.30 1.31 1.32 1.52

**10 pairs out of 10** have a wall-clock ratio strictly higher than the CPU ratio: the direction
of the gap does not depend on any threshold. **And the half that must NOT be hidden: CPU is not
invariant either** (×1.28). Writing "CPU doesn't move" would be false here; what is measured is
that wall-clock is **~1.4× more sensitive to contention** than CPU on this gate. A CPU budget
therefore also needs margin — it is just much less noisy.

**PER UNIT, never as a total** — and that is the clause that survives growth. A TOTAL budget is a
ceiling on a population whose growth is the WHOLE POINT: the day the gate judges thirty plans
instead of three, the total explodes without a single unit having slowed down, and the total gets
loosened until it no longer bounds anything. A per-unit budget, by contrast, stays true at any
size.
*(This is lesson ``S1`` from the same harvest, taken from the other end: 400 hard-coded lines
produced "61 files stuck at the ceiling.")*

**PURE JUDGE**: the population of units is **injected**, no clock is read here, no disk, no
``os.environ``. The edge that actually measures CPU
(:func:`resource.getrusage` on ``RUSAGE_CHILDREN``) lives elsewhere
(:mod:`mnemosyne.runtime.guetteur_commit`).

**AN EMPTY POPULATION IS NEVER A PASS.** A gate that measured no unit judged nothing; returning
``()`` would make it look green. It returns :data:`POPULATION_VIDE`, which the edge surfaces with
its **own** exit code (``2``, instrument failure) — distinct from a work refusal (``1``).

French prose (D117). Neighbor: :mod:`mnemosyne.production.chrono` (``G7``) — one says **WHEN** the
budget starts, the other **WHAT UNIT** it is counted in.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

#: A unit exceeded its CPU budget. The only refusal that blames the work.
UNITE_DEPASSE = "unite_depasse"
#: Instrument failure: no unit was measured. Never a pass — see the header.
POPULATION_VIDE = "population_vide"
#: Instrument failure: budget zero or negative (would refuse every unit), or negative CPU (a
#: counter subtraction in the wrong direction, ``getrusage``'s classic bug).
MESURE_ABSURDE = "mesure_absurde"


@dataclass(frozen=True, slots=True)
class Unite:
    """One unit of the gate's work, with its TWO times.

    ``mural_s`` is carried **on purpose**: it is published next to the CPU time so a reader SEES
    the gap instead of assuming it. It enters **no** verdict — that is ``G12``'s clause, and
    it is the line a saboteur would replace with ``mural_s`` in a single keystroke.
    """

    nom: str
    cpu_s: float
    mural_s: float


@dataclass(frozen=True, slots=True)
class Refus:
    """A named refusal. ``unite`` is empty for instrument failures (they blame no one)."""

    genre: str
    unite: str
    cpu_s: float
    budget_s: float


def verdict(unites: Sequence[Unite], budget_cpu_par_unite_s: float) -> tuple[Refus, ...]:
    """The units that exceed their CPU budget — **one by one**, never their sum.

    Three one-word mutants live in this body, and all three are frozen by ``test_budget_porte.py``:

    * ``u.mural_s > budget`` instead of ``u.cpu_s`` — the flagship project's bug, a verdict decided by whatever
      the machine's load happened to be;
    * ``sum(u.cpu_s for u in unites) > budget`` — the total budget, which expires as the
      population grows;
    * ``if not unites: return ()`` — the falsest pass there is, the one from a gate that measured
      nothing.
    """
    if budget_cpu_par_unite_s <= 0:
        return (Refus(MESURE_ABSURDE, unite="", cpu_s=0.0, budget_s=budget_cpu_par_unite_s),)
    if not unites:
        return (Refus(POPULATION_VIDE, unite="", cpu_s=0.0, budget_s=budget_cpu_par_unite_s),)
    negatives = tuple(u for u in unites if u.cpu_s < 0 or u.mural_s < 0)
    if negatives:
        return tuple(
            Refus(MESURE_ABSURDE, unite=u.nom, cpu_s=u.cpu_s, budget_s=budget_cpu_par_unite_s)
            for u in negatives
        )
    return tuple(
        Refus(UNITE_DEPASSE, unite=u.nom, cpu_s=u.cpu_s, budget_s=budget_cpu_par_unite_s)
        for u in unites
        if u.cpu_s > budget_cpu_par_unite_s
    )


def unites_depassantes(refus: Sequence[Refus]) -> frozenset[str]:
    """The **SET** of refused units, never their count.

    A count stays silent on a SWAP: two units trading costs leave an identical "1 refusal" and
    the repo sees nothing. What the tests freeze is therefore this set.
    """
    return frozenset(r.unite for r in refus if r.genre == UNITE_DEPASSE)


def resume(unites: Sequence[Unite], refus: Sequence[Refus], budget_cpu_par_unite_s: float) -> str:
    """The published sentence — it names CPU **and** wall-clock, and says which one judged."""
    if any(r.genre == POPULATION_VIDE for r in refus):
        return (
            "INSTRUMENT FAILURE — no unit measured: the gate judged nothing. "
            "A budget over an empty population would turn GREEN without having looked at anything."
        )
    if any(r.genre == MESURE_ABSURDE for r in refus):
        noms = ", ".join(sorted(r.unite for r in refus if r.unite)) or "(budget)"
        return (
            f"INSTRUMENT FAILURE — absurd measurement or budget on: {noms}. "
            f"budget per unit = {budget_cpu_par_unite_s:.2f} s CPU. "
            "A negative counter is a subtraction in the wrong direction, never a verdict."
        )
    detail = " · ".join(f"{u.nom} cpu {u.cpu_s:.2f} s / wall {u.mural_s:.2f} s" for u in unites)
    tete = (
        f"{len(unites)} unit(s), budget {budget_cpu_par_unite_s:.2f} s CPU PER UNIT "
        f"(never the total, never the wall-clock) — {detail}"
    )
    if not refus:
        return tete + "\nOK — no unit above its CPU budget."
    lignes = [tete, "REFUSALS:"]
    for r in sorted(refus, key=lambda x: x.unite):
        lignes.append(
            f"  - {r.genre} : {r.unite} cost {r.cpu_s:.2f} s CPU for a budget of "
            f"{r.budget_s:.2f} s. WALL-CLOCK time did not judge (measured here: x1,80 under contention "
            "versus x1,28 for the CPU, 10 matched pairs)."
        )
    return "\n".join(lignes)
