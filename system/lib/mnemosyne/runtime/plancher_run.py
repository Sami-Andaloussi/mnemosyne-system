"""The RUNTIME EDGE of :mod:`mnemosyne.production.plancher` (D3) — this is where ``git`` and disk
access happen.

Fully reuses the D1/D2 edge (:mod:`mnemosyne.runtime.derive_run`): same repo (``projects/.git``),
same window, same ``PRODUIT.md`` declaration. The floor does not build a second disk access —
*a shared guard is repaired at its one home, never client by client* (the same rule I7 carved
for `human_gate`, applied here to reading the product).

 **THE UNIT IS `PAR_LIGNE` (BY LINE), NOT `PAR_FICHIER` (BY FILE) — AND IT IS DELIBERATE, NOT AN
OMISSION.** `X_PLANCHER` and `N_PLANCHER` are derived (see ``production/plancher.py``) from the
`PAR_LIGNE` curve, the one behind the published historical figure (recorded in this repository's
own planning document). Mixing the measurement unit and the derivation unit would reproduce exactly
the mistake D1 already paid for once (*"two honest readers, two different swings, on the SAME
clause that never fixed its unit"*) — except here the floor's clause has only ONE unit; it must not
be lost on the first caller.

 **CORRECTION (D75 audit, 2026-08-15) — THE DENOMINATOR IS BOUNDED TO THE MEASURED PROJECT,
HERE, NOT INSIDE `PAR_LIGNE`.** `PAR_LIGNE` (`plan_derive.py`) sums the lines of ALL the paths in a
turn, regardless of project — correct for D1 (only one project measured at a time, `lire_tours`
reads ONLY the 15-29 July window for the sibling project), WRONG for a turn that touches SEVERAL projects at once
(the initial import of `projects/`, a single commit, 291,679 lines of which only 49,980 under
the sibling project). A first version of this edge called `PAR_LIGNE` directly on the raw turns — the denominator
was then polluted, reading July 15 at 13.7% instead of 79.8%, and the derivation of N built on that
figure was wrong (see `production/plancher.py` for the full account). `borne_au_projet` here
filters each `Tour` down to only its paths under `RACINE_PRODUIT` BEFORE calling `PAR_LIGNE` — D1's
shared function stays UNCHANGED (outside this batch, and other callers may be relying on its
unbounded denominator).

 **MADE PUBLIC (D5, 2026-08-16, rule 4: ownerless, picked up and declared)** — a second caller
needs the SAME bounded series (`runtime/plan_recul_run.py`, the day-by-day replay of the floor).
No behaviour change, only visibility: *one single home, never a third copy of the same filter* —
the lesson already paid for on `_fence_ferme` (A7), applied here before a copy can drift.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from ..production.plan_derive import PAR_LIGNE, Tour, part_produit
from ..production.plancher import N_PLANCHER, X_PLANCHER, Geste, Plancher, decision, lire_plancher
from .derive_run import (
    DEPOT,
    DEPUIS,
    JUSQUA,
    NOM_PRODUIT,
    RACINE_PRODUIT,
    age_et_depot,
    lire_tours,
    population_disparue,
    predicat_produit,
)


def borne_au_projet(tour: Tour, racine: str) -> Tour:
    """A new :class:`Tour`, its ``chemins``/``lignes`` filtered to only those under ``racine``.

 Necessary so that `PAR_LIGNE` measures "the share of the work ON THIS PROJECT that goes to
 the product", not "the share of all `projects/` touched ON THAT DAY that goes to the sibling project's
 product" — two different questions, and only the first is the one the clause asks. A turn that
 does NOT touch ``racine`` at all returns a `Tour` with empty paths; `part_produit` then
 aggregates it with ``total=0`` for that day, which does not count toward a drop (the same
 filter as :func:`~mnemosyne.production.plan_derive.plus_grande_chute` on ``j.total``).
 """
    paires = tuple((c, ln) for c, ln in zip(tour.chemins, tour.lignes, strict=True) if c.startswith(racine))
    return Tour(
        sha=tour.sha,
        date=tour.date,
        chemins=tuple(c for c, _ in paires),
        faits=tour.faits,
        lignes=tuple(ln for _, ln in paires),
    )


def etat_plancher(
    repo_root: Path,
    *,
    x: float = X_PLANCHER,
    n: int = N_PLANCHER,
    est_produit: Callable[[str], bool] | None = None,
) -> Plancher | None:
    """The floor's state for the monitored project, or ``None`` if the measurement could not be taken.

 **``None`` covers TWO distinct causes, and the caller that displays it must name them
 separately** (the same rule as :func:`~mnemosyne.runtime.derive_run.resume`): the repo is
 unreadable, OR no ``PRODUIT.md`` declaration exists. This function does not conflate the two;
 it just refuses to return a `Plancher` when either occurs — it is :func:`resume` that carries
 the message distinguishing them.

 **INJECTED ``est_produit`` replays the HISTORICAL validation (D1's `(c1)`) — without it,
 the predicate is read from ``PRODUIT.md`` (D2), the CURRENT measurement.** Same distinction,
 same reason as :func:`~mnemosyne.runtime.derive_run.resume`: a historical verdict is replayed
 on ITS population, never on what the disk carries today — and today, the sibling project has NOT declared a
 ``PRODUIT.md``, so without injection the real population always returns ``None``.

 **THIRD CAUSE OF ``None``, ADDED 2026-09-08: THE POPULATION HAS MOVED AWAY.** It was
 missing, and the gap was exactly the one the `Makefile` invites you to dig into — it announces
 that *"the refusal lives in `peut()`, called by whoever actually performs an opening gesture"*.
 But :func:`peut` goes through HERE, never through :func:`resume`. As measured on the day, the
 two readers of the same state contradicted each other: ``make plancher`` published **"FLOOR NOT
 MEASURED: the project has moved away"** while ``etat_plancher`` returned
 ``Plancher(franchi=False, recentes=(47.9,))`` — a figure drawn from a window whose current state
 is empty. **A caller that had followed the Makefile's invitation would have wired a refusal to
 a dead measurement.** The guard (:func:`population_disparue`) already existed, written and
 proven; it was just placed on the reader that PUBLISHES and not on the one that JUDGES. *A gate
 weaker than the writing that announces it.*

 **Turns whose lines are not measurable (a binary file) are EXCLUDED from the series**, never
 counted as zero — :data:`~mnemosyne.production.plan_derive.PAR_LIGNE` would otherwise raise on
 the first binary turn encountered, and an exception bubbling up to here would kill the ENTIRE
 measurement for one unreadable day. *A day that cannot be measured in lines is not a
 zero-line day* — it is absent from the series, the way a day with no commit would be.
 """
    if est_produit is None and population_disparue(repo_root):
        # ONLY when measuring the CURRENT state. A HISTORICAL replay (injected `est_produit`)
        # is judged on ITS OWN frozen population, never on what the disk carries today -- the
        # distinction this module already makes, and which the first version of this guard
        # OVERWROTE: two replay witnesses fell, and they were right.
        return None
    tours = lire_tours(repo_root, depuis=DEPUIS, jusqua=JUSQUA)
    if not tours:
        return None
    predicat = est_produit
    if predicat is None:
        predicat, _motifs = predicat_produit(repo_root)
        if predicat is None:
            return None
    mesurables = [t for t in tours if len(t.lignes) == len(t.chemins)]
    bornes = [borne_au_projet(t, RACINE_PRODUIT) for t in mesurables]
    jours = part_produit(bornes, predicat, unite=PAR_LIGNE)
    return lire_plancher(jours, x=x, n=n)


def resume(
    repo_root: Path,
    *,
    aujourdhui: str,
    x: float = X_PLANCHER,
    n: int = N_PLANCHER,
    est_produit: Callable[[str], bool] | None = None,
) -> str:
    """D3's page, ready to print — it NAMES what it could not measure, never hides it.

    ``aujourdhui`` (today) is INJECTED (see :func:`~mnemosyne.runtime.derive_run.age_et_depot`,
    the same closed default here: the `DEPUIS`/`JUSQUA` window is a FROZEN bench, but the green it
    published never said its own age or which repo it read -- 2026-08-17)."""
    tours = lire_tours(repo_root, depuis=DEPUIS, jusqua=JUSQUA)
    if tours is None:
        return (
            f"\U000026A0\U0000FE0F FLOOR NOT MEASURED: `{DEPOT}` unreadable or absent from {repo_root}. "
            '"no drift" and "I could not look" do not read the same.'
        )
    if not tours:
        return (
            f"\U000026A0\U0000FE0F FLOOR NOT MEASURED: no commit between {DEPUIS} and {JUSQUA} in "
            f"`{DEPOT}` — the window declared by the clause is empty."
        )
    # 2026-08-17 -- FOUND BY AN ORCHESTRATOR PROBE: A CHECKBOX THAT CAN NEVER REFRESH AGAIN.
    # The sibling project moved to its own repo on 2026-07-29 (INSIDE the frozen window) -- the window's history
    # stays REAL (the turns above carry real paths from that project), but `population_disparue` checks the
    # CURRENT state of the repo READ (`git ls-files`), never its history. Zero files remaining =>
    # this checkbox is FROZEN FOREVER, and a ``/`` reads as a LIVE PERMISSION -- worse than a
    # stale figure (see age_et_depot just above, which NAMES the age but blocks nothing). `make
    # carte` already has the right reflex on a neighbouring gap (POUR= outside Mnemosyne) -- the
    # same discipline adopted here (D163), a distinct reason named.
    # DO NOT UNFREEZE THE WINDOW -- a design decision (c1), not this edge.
    if population_disparue(repo_root):
        return (
            f"\U000026A0\U0000FE0F FLOOR NOT MEASURED: the repo read (`{repo_root / DEPOT}`) no longer carries ANY "
            f"file under `{RACINE_PRODUIT}` -- the project has moved away, and this measurement can "
            "never refresh at this location again. Publishing a checkbox here would be a FROZEN "
            "PERMISSION, never a live state."
        )
    predicat = est_produit
    if predicat is None:
        predicat, _motifs = predicat_produit(repo_root)
        if predicat is None:
            return (
                f"\U000026A0\U0000FE0F FLOOR NOT MEASURED: no `{NOM_PRODUIT}` declaration next to the gate "
                f"of the monitored project (`projects/{RACINE_PRODUIT}`). \"no drift\" and \"the "
                "project declares nothing\" do not read the same -- D2: the product is DECLARED, it "
                "is never guessed (see this repository's own note on the pattern for a declaration "
                "next to a plan's gate)."
            )
    mesurables = [t for t in tours if len(t.lignes) == len(t.chemins)]
    exclus = len(tours) - len(mesurables)
    bornes = [borne_au_projet(t, RACINE_PRODUIT) for t in mesurables]
    jours = part_produit(bornes, predicat, unite=PAR_LIGNE)
    plancher = lire_plancher(jours, x=x, n=n)
    lignes = [
        f"# PRODUCTION FLOOR — X={plancher.x:.0f}% over N={plancher.n} consecutive day(s)",
        "",
        age_et_depot(tours, repo_root, aujourdhui),
        "",
        f"state: {'\U000026D4 BREACHED — no shielding OPENING possible' if plancher.franchi else '\U00002705 not breached'}",
        f"last {plancher.n} day(s) measured: "
        + ", ".join(f"{p:.1f}%" for p in plancher.recentes),
        f"unit: PAR_LIGNE, denominator bounded to the project · window: {DEPUIS} → {JUSQUA} · "
        f"{len(jours)} day(s) total",
    ]
    if exclus:
        lignes.append(
            f"\U000026A0\U0000FE0F {exclus} turn(s) excluded from the series (unmeasurable lines — a binary file "
            "present) — never counted as zero."
        )
    return "\n".join(lignes)


def peut(
    geste: Geste,
    repo_root: Path,
    *,
    x: float = X_PLANCHER,
    n: int = N_PLANCHER,
    est_produit: Callable[[str], bool] | None = None,
) -> bool | None:
    """``True``/``False`` = the gesture is judged; ``None`` = not enough data to judge.

 **``None`` is NOT a refusal.** A caller that treated ``None`` as ``False`` would invent a
 refusal where the true answer is "I don't know" — the same fault this module itself refuses to
 commit on missing data (see :func:`etat_plancher`)."""
    plancher = etat_plancher(repo_root, x=x, n=n, est_produit=est_produit)
    if plancher is None:
        return None
    return decision(geste, plancher)


def main(argv: list[str] | None = None) -> int:  # pragma: no cover - CLI on the REAL bricks
    """CLI: ``make plancher`` — publishes the state, level 1, never refuses (the refusal lives in
    :func:`peut`, called by whoever actually performs an opening gesture)."""
    from datetime import date

    print(resume(Path.cwd(), aujourdhui=date.today().isoformat()))
    return 0


if __name__ == "__main__":  # pragma: no cover
    import sys

    sys.exit(main(sys.argv[1:]))
