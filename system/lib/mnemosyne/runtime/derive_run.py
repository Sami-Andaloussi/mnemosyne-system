"""The EDGE of :mod:`mnemosyne.production.plan_derive` — this is WHERE ``git`` gets opened.

**THIS FILE EXISTS BECAUSE THE JUDGE HAD NO CALLER.** `plan_derive` has produced `D1`'s two
ratchets for eighteen commits, and **nothing in `system/` imported it**: not `make tick`,
not `make carte`, no output anywhere. *The barrier that nothing calls* — the fifth occurrence of
this class in one day in this repository, and this one on its own author's module. A judge with no
edge is a clause that looks EXACTLY like a satisfied clause.

**THE JUDGE READS NOTHING, IT RECEIVES ITS POPULATION.** The whole disk lives here. *A judge that
goes and fetches its own population can find it empty and render a green.*

**THE THREE PARAMETERS ARE DECLARED IN THE CLAUSE, NOT CHOSEN HERE.** `D1` cost three honest
readers finding **three different tipping points** on the same history (07-15, 07-20, 07-26) because
its condition named neither its repository, nor its unit, nor its predicate. Each of the three
constants below therefore carries **the line that declares it**, and none is chosen here:
*a clause with a free parameter is verifiable only by whoever chose it.*
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path

from ..production.plan_derive import PAR_FICHIER, Tour, lire, lire_produit, rendre

#: The repository, the unit and the window — this repository's own plan, clause `(c1)`:
#: *"replay over `projects/.git` (the history from July 15 to 29), with the `PAR_FICHIER` unit"*.
DEPOT = "projects/.git"
DEPUIS = "2026-07-15"
JUSQUA = "2026-07-30"  # git's `--until` is EXCLUSIVE on the date: the 29th is the last day included

#: The root of the WATCHED project — the one whose window `(c1)` freezes. **Six, not five or
#: seven** stays true for :data:`DOSSIERS_PRODUIT` below, but since `D2` this root only fixes the
#: PERIMETER where a declaration is looked for: it no longer alone decides what counts as product.
RACINE_PRODUIT = "saas/Sibling Research/"

#: **D2 — THIS PREDICATE NO LONGER DRIVES THE MEASUREMENT IN PROGRESS.** It remains EXACT and
#: UNCHANGED: it is the population that validated `(c1)` (the July 21 tipping point,
#: `test_sur_la_POPULATION_REELLE_…`), and that historical validation is never silently re-measured
#: — it is INJECTED, explicitly, into the witnesses that replay it. **THE MEASUREMENT IN PROGRESS**
#: (`resume`/`resume_recent`, called WITHOUT a predicate injected by `tick.py`/`carte_run.py`) now
#: reads :func:`predicat_produit`, which goes and looks for a `PRODUIT.md` declaration beside the
#: watched project's gate — and NOTHING, if the project has declared nothing. *The product is
#: declared BY THE PROJECT, never hardcoded here* — even where this very module was once the
#: counter-example: a guard that classifies by PREFIX judges the NAME of the path, never frozen
#: except to PROVE that it once worked.
DOSSIERS_PRODUIT = ("sibling/", "core/", "engine/", "coverage/", "methods/", "productions/")


def est_produit(chemin: str) -> bool:
    """The FROZEN predicate over the six folders — `(c1)`'s REFERENCE POPULATION, not the live
    measurement.

    **Do not call this thinking it measures the research project today**: since `D2`,
    `resume()`/`resume_recent()` without an injected predicate read :func:`predicat_produit`. This
    function remains so that witnesses replaying `(c1)` can inject it explicitly — a historical
    verdict is never re-measured over a population that has since moved under it."""
    if not chemin.startswith(RACINE_PRODUIT):
        return False
    reste = chemin[len(RACINE_PRODUIT) :]
    return reste.startswith(DOSSIERS_PRODUIT)


#: The declaration file's name — **beside the plan's gate**, the same convention documented
#: elsewhere in this repository's own governance docs (*"the file lives beside the plan's gate …
#: the project's root for a project"*). Never INSIDE `PLAN.md`: the `*Produit*` field there is
#: already reserved at the ITEM scale (`plan_format.FIELD_NAMES`) — a second sense of the same word,
#: at the DOCUMENT level, would be a vocabulary collision, not a convenience.
NOM_PRODUIT = "PRODUIT.md"


def predicat_produit(repo_root: Path) -> tuple[Callable[[str], bool] | None, tuple[str, ...]]:
    """`D2` — the predicate IN PROGRESS, derived from what the watched project has DECLARED.

    Renders ``(predicat, motifs)`` — or ``(None, ())`` when **nothing is declared**. ``None`` is
    NOT a predicate that refuses everything: it is the ABSENCE of measurement itself, and the
    caller must NAME it rather than confuse it with "0% product", which would be a FALSE number
    rather than an absence of one. *A project that declares nothing receives the measurement
    disabled and NAMED, never a false green* — `D2`'s clause, word for word.

    **An absent file AND a file that is present-but-empty are TWO DIFFERENT states**, and only
    one of the two is the absence: a ``PRODUIT.md`` that exists but declares no pattern is an
    EXPLICIT declaration — "nothing, here, is product" — not a silence. Only the ABSENT file
    disables the measurement."""
    chemin = repo_root / "projects" / RACINE_PRODUIT / NOM_PRODUIT
    try:
        texte = chemin.read_text(encoding="utf-8")
    except OSError:
        return None, ()
    motifs = lire_produit(texte)

    def _est_produit_declare(chemin_git: str) -> bool:
        if not chemin_git.startswith(RACINE_PRODUIT):
            return False
        reste = chemin_git[len(RACINE_PRODUIT) :]
        return bool(motifs) and reste.startswith(motifs)

    return _est_produit_declare, motifs


def _degnome(chemin: str) -> str:
    """``git`` wraps any path with a special character in quotes — this renders the bare path.

    Measured on the real population: **65 paths out of 4,448** come out quoted (the ones
    carrying a space after a comma, under `trading/`). Without this stripping, none of them would
    be recognized by :func:`est_produit` — they would all fall on the "machinery" side **in
    silence**, and the product share would be published too low with no error ever appearing.
    """
    if len(chemin) >= 2 and chemin[0] == '"' and chemin[-1] == '"':
        return chemin[1:-1]
    return chemin


def lire_tours(repo_root: Path, *, depuis: str = DEPUIS, jusqua: str = JUSQUA) -> list[Tour] | None:
    """The turns of the declared window, or ``None`` when the measurement could NOT be taken.

    ``None`` is not an empty list, and the difference is everything: *two absences of
    measurement compare equal*. A window with no commit and an unreadable repository must read
    differently.

    ``lignes`` stays **empty** as soon as a single file in the commit is binary (``git`` renders
    ``-`` for its line counts): `PAR_LIGNE` then refuses this turn, and :func:`ecart_des_unites`
    NAMES it instead of inventing a zero. *A turn that cannot be measured in lines never wrote zero
    lines.*
    """
    depot = repo_root / DEPOT
    if not depot.exists():
        return None
    try:
        sortie = subprocess.run(  # noqa: S603
            [
                "git",
                "-c",
                "core.quotepath=false",  # otherwise accented characters come out in octal and match nothing
                f"--git-dir={depot}",
                "log",
                # D-B, THIRD PASS (chat 3, 2nd re-run): `--all -m` DOUBLE-COUNTED any
                # branch content brought in by a CLEAN merge (no conflict). Repro: a file
                # committed on a branch, then merged with no conflict, appeared in TWO turns
                # -- once via the original commit (seen by `--all`), once via the merge's diff
                # against the parent that DID NOT HAVE IT (seen by `-m`). *A population counted
                # twice is no longer a population, it is a bias.*
                # `--first-parent` replaces `--all`: we walk the MAIN line of history (what
                # actually landed in the project), not every abandoned branch. Verified on the
                # REAL population: 255 commits, unchanged (only one ref exists in
                # `projects/.git`). And combined with `-m`, every commit -- merge or not --
                # produces only ONE SINGLE diff (against its first parent), so the original D-B
                # case (a file existing ONLY in a merge's resolution, `resolution.py`) stays
                # visible: the merged parent's content AND the merge's own resolution come out
                # TOGETHER, in the same block, exactly once.
                "--first-parent",
                f"--since={depuis}",
                f"--until={jusqua}",
                "-m",
                "--numstat",
                "--format=%x01%H%x09%ad",
                "--date=short",
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if sortie.returncode != 0:
        return None

    # sha -> (date, {path: lines_added|None}, first-appearance order)
    # A dict PER PATH, now more of a SAFETY NET than an active mechanism since `--first-parent`:
    # each sha now produces only ONE SINGLE numstat block (only one parent diffed). Still keeps the
    # union BY KEY rather than a list: *a guard that no longer bites is still a guard, not a risk.*
    par_sha: dict[str, tuple[str, dict[str, int | None]]] = {}
    ordre: list[str] = []
    for bloc in sortie.stdout.split("\x01"):
        if not bloc.strip():
            continue
        entete, _, corps = bloc.partition("\n")
        sha, _, date = entete.partition("\t")
        if sha not in par_sha:
            par_sha[sha] = (date.strip(), {})
            ordre.append(sha)
        _, chemins_du_sha = par_sha[sha]
        for ligne in corps.splitlines():
            champs = ligne.split("\t")
            if len(champs) != 3:
                continue
            ajouts, retraits, chemin_brut = champs
            chemin = _degnome(chemin_brut)
            binaire = ajouts == "-" or retraits == "-"
            # ACKNOWLEDGED LIMIT: if the TWO parents of a merge carry different versions of the
            # same path, the last diff encountered is kept -- an exact fidelity of the line count
            # across parents is not guaranteed; the path's PRESENCE, however, is.
            chemins_du_sha[chemin] = None if binaire else int(ajouts)

    tours: list[Tour] = []
    for sha in ordre:
        date, chemins_du_sha = par_sha[sha]
        if not chemins_du_sha:
            continue  # an empty commit does not enter the population: it writes nothing
        binaire_present = any(v is None for v in chemins_du_sha.values())
        tours.append(
            Tour(
                sha=sha,
                date=date,
                chemins=tuple(chemins_du_sha),
                # `faits` stays `None` = UNKNOWN. `git` knows NOTHING about the plan's steps,
                # and `frozenset()` would publish "N commits without a SINGLE identifier changing" —
                # the research project's exact failure, written from zero data.
                faits=None,
                lignes=() if binaire_present else tuple(chemins_du_sha.values()),
            )
        )
    tours.reverse()  # `git log` renders most-recent-first; the series is read in time order
    return tours


def age_et_depot(tours: list[Tour], repo_root: Path, aujourdhui: str) -> str:
    """A line that NAMES the age of the last measured day and the repository ACTUALLY read.

    **2026-08-17, FOUND BY AN ORCHESTRATOR PROBE: A GREEN THAT DOES NOT STATE ITS AGE.** The
    `DEPUIS`/`JUSQUA` window is a FROZEN and DELIBERATE acceptance bench (`(c1)`) -- it is NOT the
    default, and this function does not unfreeze it. The measured defect is that the page that
    PUBLISHES the number never stated its AGE nor WHICH repository it had read: `derive_resume` read
    `projects/.git` (the repository that WRAPS `projects/`, never a project's NESTED repository),
    frozen at the last commit touching the research project in THIS repository -- `fecad52`, 2026-07-29 -- while
    the research project's own NESTED repository already carried 299 commits, the
    last one TODAY. Zero of those 299 commits was visible to the measurement. *A CORRECT view of a
    STALE source is an exact lie* -- already written for readability, never applied to a window's
    age.

    ``aujourdhui`` is INJECTED, same rule as :func:`resume_recent`: this module does not read the
    clock itself, or its witnesses would depend on the day they are run.
    """
    from datetime import date

    dernier_jour = max(t.date for t in tours)
    age = (date.fromisoformat(aujourdhui) - date.fromisoformat(dernier_jour)).days
    return (
        f"last measured day: {dernier_jour} ({age} day(s) ago) — "
        f"repository read: `{repo_root / DEPOT}`"
    )


def population_disparue(repo_root: Path, *, depot: str = DEPOT, racine: str = RACINE_PRODUIT) -> bool:
    """TRUE if the repository READ no longer carries ANY file under `racine` — the project has
 moved, and the measurement can NEVER refresh itself here again, no matter which day it is run.

 **FOUND BY AN ORCHESTRATOR PROBE, 2026-08-17 — THE MORE SERIOUS COUSIN OF AGE.** `age_et_
 depot` publishes that a number is old; this publishes that a number can NEVER get fresher again.
 The research project migrated to its own nested repository on 2026-07-29 ("one project, one repository") —
 INSIDE the frozen window `(c1)` (July 15-29), so that window's history remains REAL (the turns
 still carry real research-project paths, `47.9%` is not fabricated). But `git --git-dir=projects/
 .git ls-files` under the watched project's root now renders ZERO lines — frozen forever, the window
 will never see a single further commit from it. A ``/`` published on this basis **reads as a
 LIVING PERMISSION**, worse than an old number: a number can be argued with, a checkbox is
 believed.

 **DOES NOT UNFREEZE THE WINDOW** — a design decision (`(c1)`), not this module. This only
 changes what the green STATES, never what it measures.

 Returns ``False`` (never "vanished") on any git invocation error — an execution uncertainty
 must not disguise itself as a verdict, same rule as :func:`lire_tours`.
 """
    chemin_depot = repo_root / depot
    try:
        sortie = subprocess.run(  # noqa: S603
            ["git", "--git-dir", str(chemin_depot), "ls-files", "--", racine],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    if sortie.returncode != 0:
        return False
    return not sortie.stdout.strip()


def resume(
    repo_root: Path, *, aujourdhui: str, est_produit: Callable[[str], bool] | None = None
) -> str:
    """`D1`'s page, ready to print — **it NAMES, it refuses nothing** (level 1).

    **It does NOT stay silent when it could not measure.** Same reason as `_moisson_due` in the
    tick: the output IS the surface, so a silence would read "no drift" and "I could not look" the
    same way.

    **`D2` — WITHOUT AN INJECTED `est_produit`, THE PREDICATE IS READ FROM THE PROJECT'S OWN
    DECLARATION.** A caller replaying a historical validation (`(c1)`) injects the FROZEN predicate
    of the time (`derive_run.est_produit`, the module-level one, not this parameter); a caller
    measuring the CURRENT STATE (`tick.py`, `carte_run.py`) injects nothing and receives
    :func:`predicat_produit` — so, today, a measurement DISABLED and NAMED as long as no
    `PRODUIT.md` exists.

    ``aujourdhui`` is INJECTED (see :func:`age_et_depot`) — this module does not read the clock."""
    tours = lire_tours(repo_root)
    if tours is None:
        return (
            f"\U000026A0\U0000FE0F DRIFT NOT MEASURED: `{DEPOT}` unreadable or absent from {repo_root}. "
            '"no drift" and "could not look" do not read the same.'
        )
    if not tours:
        return (
            f"\U000026A0\U0000FE0F DRIFT NOT MEASURED: no commit between {DEPUIS} and {JUSQUA} in "
            f"`{DEPOT}` — the window declared by the clause is empty."
        )
    predicat = est_produit
    if predicat is None:
        predicat, _motifs = predicat_produit(repo_root)
        if predicat is None:
            return (
                f"\U000026A0\U0000FE0F PRODUCT SHARE NOT MEASURED: no `{NOM_PRODUIT}` declaration beside the "
                f"watched project's gate (`projects/{RACINE_PRODUIT}`). \"no drift\" and "
                '"the project declares nothing" do not read the same — D2: the product is '
                "DECLARED, it is never guessed (the pattern for declaring something beside a "
                "plan gate is documented separately in this repository)."
            )
    entete = age_et_depot(tours, repo_root, aujourdhui)
    return f"{entete}\n\n{rendre(lire(tours, predicat, unite=PAR_FICHIER))}"


#: The window the TICK watches — the last 14 days, not the frozen window of `(c1)`.
#: **WHY TWO WINDOWS, AND IT IS A DECISION, NOT AN OVERSIGHT.** `(c1)` validates the DETECTOR
#: on a known tipping point: its window (July 15-29) is **closed forever**, so republishing it
#: at every tick would manufacture *an alarm nobody can silence* — the exact defect `moisson_due`
#: was designed to avoid, and that `ProposalQueueReview` flags. The tick, for its part, watches
#: what MOVES; the historical validation stays where it is useful, in `make carte`.
#: *The same judge, two populations* — this is precisely what a judge with an INJECTED population
#: makes possible, and the reason it reads nothing itself.
JOURS_SURVEILLES = 14


def resume_recent(
    repo_root: Path,
    *,
    aujourdhui: str,
    jours: int = JOURS_SURVEILLES,
    est_produit: Callable[[str], bool] | None = None,
) -> str | None:
    """The tick's sentence — ``None`` when the recent window carries NO commit.

    **SILENCE HERE IS A STATE, NOT A DEFECT — and the distinction has just been paid for in
    this repository.** *A clause with no caller looks like a satisfied clause; a clause with no
    population looks like a clause that is asleep.* The first is a defect, the second a fact. This
    edge IS called at every tick; it stays silent because the watched repository has committed
    nothing since 2026-07-29, and it will speak again the day it resumes.

    **NO THRESHOLD** — it publishes the largest drop the series carries, whatever it is.
    `D1` forbids a date or a threshold living inside the detector, and this sentence only
    RESTATES what it renders. *A detector calibrated on the answer detects nothing.*

    ``aujourdhui`` is **injected**: this module does not read the clock, or its witnesses would
    depend on the day they are run.

    **`D2`, same rule as** :func:`resume` **: without an injected `est_produit`, the tick reads**
    :func:`predicat_produit`. ``None`` coming out of it (nothing declared) silences this sentence
    EXACTLY like an empty window — the tick has only one channel, and a disabled measurement has
    nothing more to report than a window with no commit: BOTH render ``None`` here, but `resume()`
    (the map) remains the place where the difference is NAMED.
    """
    from datetime import date, timedelta

    fin = date.fromisoformat(aujourdhui)
    tours = lire_tours(
        repo_root,
        depuis=(fin - timedelta(days=jours)).isoformat(),
        jusqua=(fin + timedelta(days=1)).isoformat(),
    )
    if not tours:
        return None  # unreadable repository OR empty window — either way, nothing to report to the tick
    predicat = est_produit
    if predicat is None:
        predicat, _motifs = predicat_produit(repo_root)
        if predicat is None:
            return None  # nothing declared: the tick stays silent, `resume()` (the map) NAMES the absence
    lecture = lire(tours, predicat, unite=PAR_FICHIER)
    if lecture.chute is None:
        return None  # the product share dropped on no day: nothing to report, and that is an answer
    c = lecture.chute
    # **D-A, SECOND PASS — THE FIRST FIX MOVED A THRESHOLD, IT DID NOT CLOSE THE
    # CLASS.** `.0f` -> `.1f` reduced the gap by a factor of 10; a magnitude of 0.040 point
    # still displayed as *"0.0 point(s) (100.0% -> 100.0%)"*. *A fix that moves a threshold closes
    # the CASE and leaves the CLASS open* -- the cause is not the chosen precision, it is the
    # DISAGREEMENT between the condition that produces the object (`ampleur > 0`, strictly) and a
    # FIXED display precision, whatever it is. As long as the two are not tied together, any
    # rounding leaves a window beneath it -- and *this is the hardest shape to see*: every fix works
    # on every case it is shown, until someone looks BELOW the new threshold.
    # The fix TIES the two together: precision GROWS until it renders a non-zero value. Since
    # `ampleur > 0` is guaranteed by the caller (`plus_grande_chute`), the loop always
    # terminates -- a strictly positive float has a non-zero decimal representation at
    # sufficient precision.
    points = _texte_non_nul((c.avant - c.apres) * 100)
    avant_txt, apres_txt = _pourcentages_distincts(c.avant, c.apres)
    return (
        f"the research project's product share dropped by {points} point(s) "
        f"({avant_txt} → {apres_txt}) from {c.depuis} to {c.vers}, over the last {jours} days "
        f"— `make carte` publishes the full series and BOTH units. *A plan drifting toward its "
        f"own machinery never says so by itself.*"
    )


def _texte_non_nul(valeur: float, *, max_decimales: int = 12) -> str:
    """Formats ``valeur`` (> 0, guaranteed by the caller) by growing the precision until the
    rendered text no longer rounds to zero. *Precision follows the CONDITION, never a chosen
    number.*"""
    for decimales in range(1, max_decimales + 1):
        texte = f"{valeur:.{decimales}f}"
        if float(texte) != 0:
            return texte
    return f"{valeur:.{max_decimales}f}"  # safety net: never reached, valeur > 0 guarantees it


def _pourcentages_distincts(avant: float, apres: float, *, max_decimales: int = 12) -> tuple[str, str]:
    """The two percentages, at the shortest precision that renders them READABLY distinct.

    Same defect, same class: two percentages identical on display beside a sentence announcing
    a drop say "nothing changed" even though `avant > apres` is guaranteed by
    :func:`plus_grande_chute`. Precision is grown until BOTH texts differ."""
    for decimales in range(1, max_decimales + 1):
        a, b = f"{avant:.{decimales}%}", f"{apres:.{decimales}%}"
        if a != b:
            return a, b
    return f"{avant:.{max_decimales}%}", f"{apres:.{max_decimales}%}"
