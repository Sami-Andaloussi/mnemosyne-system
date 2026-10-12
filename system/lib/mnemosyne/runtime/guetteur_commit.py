"""``P5`` — the watcher's EDGE: wait for a calm window WITH A CEILING, then prove the gesture.

The judges are pure and live elsewhere — :mod:`mnemosyne.production.guetteur` (calm window,
``HEAD`` moved), :mod:`mnemosyne.production.chrono` (``G7``, when the budget starts),
:mod:`mnemosyne.production.budget_porte` (``G12``, what it is counted in). Here, and only here, do
we read ``.git``, the clock, and the CPU counter.

## The three items of this batch meet in a single function

:func:`sous_garde` does ``G7`` literally: it **waits** (a clean, capped wait), and the work budget
only starts on the ``tour_obtenu`` line. **Without this separation, serialising would make the
gate MORE severe under contention**: two chats crossing paths would each see their wait charged to
their work, hence refused, hence replayed — the exact metastable collapse ``G7`` names.

## Three bounds, three natures — and none of them is a generic "timeout"

.. code-block:: text

    PLAFOND_ATTENTE_S    30 s   WALL    "I give up queuing"        -> this is NOT the work
    GARDE_FOU_SERVICE_S 300 s   WALL    "this gesture is HUNG"     -> a stall detector
    BUDGET_CPU_GESTE_S   10 s   CPU     "this gesture costs too much" -> the ONLY cost judgment

**The wall-clock safety net is NOT a cost judgment, and writing it here keeps a future reader
from ever promoting it to a budget.** A wall-clock budget is precisely what ``G12`` forbids:
measured on this repo's own gate, 10 paired samples, the wall clock inflates ×1.80 under
contention against ×1.28 for CPU. At 300 s — **~400× the real measured work (0.37 s wall)** — the
safety net can only bite on a genuine hang, never on a loaded machine.

**Where the three numbers come from** (none of them carried over from another project):

* ``PLAFOND_ATTENTE_S = 30`` — the **median** interval between two commits on this repo is **90 s**
  (1,716 commits / 30 days). Waiting up to a third of that interval converges; beyond that, you are
  no longer queuing behind one peer, you are queuing behind several, and it is better to **say so**
  than to keep waiting.
* ``BUDGET_CPU_GESTE_S = 10`` — **13×** the worst CPU ever measured on the current gate (0.77 s
  under 20 burners): it does not bite on today's work, it bites on a regression. And it is **~11%**
  of the 90 s median interval: beyond that, the gate becomes a visible tax and ``--no-verify``
  becomes rational again — *a gate slower than the wall is never used*.
* ``GARDE_FOU_SERVICE_S = 300`` — see above.

## ``HEAD``, never ``$?``

``git commit -m … | tee journal.log`` returns ``tee``'s status. The one fact that cannot lie is the
identity of ``HEAD`` before and after; it is
:func:`~mnemosyne.production.guetteur.verdict_du_geste` that decides, in **both**
directions (unmoved despite ``rc == 0``; moved despite ``rc != 0``).

## Exit codes

.. code-block:: text

    0  turn obtained, gesture done, HEAD moved, within bounds
    1  REFUSED: capped wait, CPU budget exceeded, HEAD unmoved, or a lying rc
    2  INSTRUMENT FAILURE: HEAD unreadable, or an empty population on the budget side

**Everything is injectable** (``sonde``, ``maintenant``, ``dormir``, ``cpu``, ``git``, ``geste``):
the suite exercises contention, the wait ceiling, and a lying pipe **without** a real repo, without
real sleep, and without a real commit (D126). *A module that fetches its own time cannot be put to
the test under contention.*

English prose for this mirror (D117). Decisions: D175 (everyone on ``main``) · invariant 16 (a
bound REFUSES) · D126.
"""

from __future__ import annotations

import subprocess
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from ..production import budget_porte
from ..production.chrono import Chrono, resume as resume_chrono, verdict as verdict_chrono
from ..production.guetteur import (
    HEAD_ILLISIBLE,
    VERROUS_QUI_BLOQUENT,
    fenetre_calme,
    raison_dattente,
    resume_geste,
    verdict_du_geste,
)

#: How long we accept queuing (WALL). See the header for the derivation.
PLAFOND_ATTENTE_S = 30.0
#: Stall detector (WALL) — never a cost judgment, see the header.
GARDE_FOU_SERVICE_S = 300.0
#: The ONLY cost judgment: CPU time, PER UNIT of gesture (``G12``).
BUDGET_CPU_GESTE_S = 10.0
#: Interval between two probes of ``.git`` — one ``stat`` per loop turn, nothing more.
INTERVALLE_SONDE_S = 0.2

Git = Callable[[Sequence[str]], "tuple[int, str]"]


def git_reel(args: Sequence[str]) -> tuple[int, str]:  # pragma: no cover - the real git
    fini = subprocess.run(["git", *args], capture_output=True, text=True)
    return fini.returncode, fini.stdout.strip()


def sonde_reelle(dot_git: Path) -> tuple[str, ...]:  # pragma: no cover - the real disk
    """Which blockers from :data:`VERROUS_QUI_BLOQUENT` exist in ``.git`` **right now**.

    One ``exists()`` per name, never a scan of the folder: ``.git`` holds thousands of entries and
    *a gate slower than the wall is never used*.
    """
    return tuple(nom for nom in sorted(VERROUS_QUI_BLOQUENT) if (dot_git / nom).exists())


def cpu_enfants_reel() -> float:  # pragma: no cover - system-dependent
    """The cumulative CPU of CHILD processes (``utime + stime``), in seconds.

    ``RUSAGE_CHILDREN`` and not ``RUSAGE_SELF``: the work to judge is the sub-process (git, the
    hook, the interpreter), not this watcher. Measuring it on ourselves would read ~0 and the
    budget would be decorative.
    """
    import resource

    r = resource.getrusage(resource.RUSAGE_CHILDREN)
    return r.ru_utime + r.ru_stime


def head(git: Git) -> str:
    """``HEAD`` resolved, or the empty string if it is unreadable (a new repo, git absent).

    The empty string is not ``"0000…"``: it propagates the ignorance up to the judge, which names
    it :data:`~mnemosyne.production.guetteur.HEAD_ILLISIBLE` — an instrument failure, not a verdict.
    """
    code, sortie = git(["rev-parse", "HEAD"])
    return sortie.strip() if code == 0 else ""


@dataclass(frozen=True, slots=True)
class Passage:
    """What one guarded pass produced — the figures AND the verdicts."""

    chrono: Chrono
    raison_finale: str
    head_avant: str
    head_apres: str
    code_retour: int
    cpu_s: float


def attendre_le_tour(
    *,
    sonde: Callable[[], Sequence[str]],
    maintenant: Callable[[], float],
    dormir: Callable[[float], None],
    plafond_attente_s: float = PLAFOND_ATTENTE_S,
    intervalle_s: float = INTERVALLE_SONDE_S,
) -> tuple[float, float | None, str]:
    """``(demande, tour_obtenu | None, raison)`` — the wait queue, **capped**.

    **The first probe happens BEFORE any sleep**: in the ordinary case (no active peer), the
    watcher costs one ``stat`` and returns. A loop that slept first would add ``intervalle_s`` to
    **every** commit in the repo for a case that almost never happens.

    The stopping condition is ``>=``, not ``>``: with ``>`` a ceiling of 0 s would still run one
    loop turn — *a one-sided rule only bounds one side*.
    """
    demande = maintenant()
    while True:
        presents = tuple(sonde())
        if fenetre_calme(presents):
            return demande, maintenant(), raison_dattente(presents)
        if maintenant() - demande >= plafond_attente_s:
            return demande, None, raison_dattente(presents)
        dormir(intervalle_s)


def sous_garde(
    geste: Callable[[], int],
    *,
    git: Git,
    sonde: Callable[[], Sequence[str]],
    maintenant: Callable[[], float] = time.monotonic,
    dormir: Callable[[float], None] = time.sleep,
    cpu: Callable[[], float] = cpu_enfants_reel,
    plafond_attente_s: float = PLAFOND_ATTENTE_S,
    garde_fou_service_s: float = GARDE_FOU_SERVICE_S,
) -> Passage:
    """Waits for the turn, then runs ``geste`` — **the budget only starts here** (``G7``).

    **``G7``'S LINE** is ``Chrono(demande=…, tour_obtenu=tour, …)``: the judge subtracts starting
    from ``tour_obtenu``. The one-word mutant is ``tour_obtenu=demande`` — it compiles, it returns
    plausible numbers, and it charges the wait to the work. It is frozen by
    ``test_guetteur_commit.py`` with a wait that dominates the service.

    When the turn is **never** obtained, the gesture is not launched and ``head_apres`` stays
    empty: inventing a "gesture not done, therefore succeeded" would be the falsest green in the
    module.
    """
    demande, tour, raison = attendre_le_tour(
        sonde=sonde, maintenant=maintenant, dormir=dormir, plafond_attente_s=plafond_attente_s
    )
    if tour is None:
        chrono = Chrono(
            demande=demande,
            tour_obtenu=None,
            maintenant=maintenant(),
            plafond_attente_s=plafond_attente_s,
            budget_service_s=garde_fou_service_s,
        )
        return Passage(chrono, raison, head_avant="", head_apres="", code_retour=0, cpu_s=0.0)

    avant = head(git)
    cpu_depart = cpu()
    code_retour = geste()
    cpu_s = cpu() - cpu_depart
    apres = head(git)
    chrono = Chrono(
        demande=demande,
        tour_obtenu=tour,
        maintenant=maintenant(),
        plafond_attente_s=plafond_attente_s,
        budget_service_s=garde_fou_service_s,
    )
    return Passage(
        chrono, raison, head_avant=avant, head_apres=apres, code_retour=code_retour, cpu_s=cpu_s
    )


def juger(passage: Passage, *, budget_cpu_s: float = BUDGET_CPU_GESTE_S) -> tuple[int, str]:
    """``(code, texte)`` — **the one line that turns three verdicts into ONE refusal**.

    The ``2`` (instrument failure) does not get overwritten by the ``1`` (refusal): an unreadable
    ``HEAD`` means "the question was not asked", not "the gesture failed". A hardcoded ``return 0``
    here would turn the three judges into decoration; ``test_guetteur_commit.py`` freezes all three
    outcomes.
    """
    refus_chrono = verdict_chrono(passage.chrono)
    parties = [resume_chrono(passage.chrono, refus_chrono)]

    if passage.chrono.tour_obtenu is None:
        parties.append(
            f"Turn NEVER obtained — {passage.raison_finale}. The gesture was not launched: "
            "no conclusion about the work (this is contention, not the commit)."
        )
        return 1, "\n".join(parties)

    unite = budget_porte.Unite(
        nom="geste",
        cpu_s=passage.cpu_s,
        mural_s=passage.chrono.maintenant - passage.chrono.tour_obtenu,
    )
    refus_budget = budget_porte.verdict((unite,), budget_cpu_s)
    parties.append(budget_porte.resume((unite,), refus_budget, budget_cpu_s))

    refus_geste = verdict_du_geste(passage.head_avant, passage.head_apres, passage.code_retour)
    parties.append(resume_geste(refus_geste))

    texte = "\n".join(parties)
    panne = any(r.genre == HEAD_ILLISIBLE for r in refus_geste) or any(
        r.genre in (budget_porte.POPULATION_VIDE, budget_porte.MESURE_ABSURDE) for r in refus_budget
    )
    if panne:
        return 2, texte
    if refus_chrono or refus_budget or refus_geste:
        return 1, texte
    return 0, texte


def main(
    argv: Sequence[str] | None = None,
    *,
    git: Git | None = None,
    sonde: Callable[[], Sequence[str]] | None = None,
    lanceur: Callable[[Sequence[str]], int] | None = None,
) -> int:
    """CLI: ``guetteur_commit -- <command…>`` — waits for the window, runs, proves it via ``HEAD``.

    **The command is a LIST, never a string passed to a shell**: ``shell=True`` would reopen the
    pipe hole this module exists to close (and much worse).
    """
    args = list(argv or ())
    if "--" not in args:
        print(
            "usage: guetteur_commit -- <command...>\n"
            "  waits for a calm git window (ceiling "
            f"{PLAFOND_ATTENTE_S:.0f} s), runs the command, and PROVES the gesture via HEAD."
        )
        return 2
    commande = args[args.index("--") + 1 :]
    if not commande:
        print("REFUSED: no command after '--' — there is nothing to guard.")
        return 2

    appel_git: Git = git if git is not None else git_reel
    if sonde is None:
        code, racine = appel_git(["rev-parse", "--git-dir"])
        dot_git = Path(racine or ".git")
        sonde = lambda: sonde_reelle(dot_git)  # noqa: E731 - a single expression, readable this way
    lance = (
        lanceur
        if lanceur is not None
        else (
            lambda c: subprocess.run(list(c)).returncode  # pragma: no cover - the real launch
        )
    )

    passage = sous_garde(lambda: lance(commande), git=appel_git, sonde=sonde)
    code, texte = juger(passage)
    print(texte)
    return code


if __name__ == "__main__":  # pragma: no cover
    import sys

    sys.exit(main(sys.argv[1:]))
