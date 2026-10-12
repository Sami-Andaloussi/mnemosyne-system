"""C6 -- the edge of the routing journal. `make carte` calls it; it has NO surface of its own (the
item's `*Produit*` says so: "ships through `make carte`, no new surface").

Same partition as the rest of the repo: :mod:`~mnemosyne.production.routage_journal` is pure, this
module opens the disk and shells out to `git`. **Always THIS repo's own plan, never the one
`POUR=` names** -- the same choice :func:`~mnemosyne.runtime.derive_run.resume` already makes,
already called unconditionally by `carte_run.py`: Mnemosyne's development velocity is measured on
ITS OWN history, not on that of whatever project is being looked at in the same turn.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from ..production.plan_registry import scan_plans
from ..production.routage_journal import Commit, journal, taux_de_reprise

#: `type(IDENT): subject` -- this repo's convention. The last three NEVER count as a turn
#: (:data:`~mnemosyne.production.routage_journal.TYPES_DE_TOUR`) but their commits still have to
#: be seen -- otherwise an item closed by A SINGLE `feat` followed by an `orch`/`docs` would lose
#: its only `feat` commit along with the noise.
#:
#: **REAL DEFECT, CONFIRMED ON 2026-08-16: THE ORIGINAL PATTERN MISSED EVERY HYPHENATED
#: IDENT.** Built and measured against Mnemosyne's own convention alone (`A1`, `BR5`, `P6`), used
#: on a sibling project's, which DOMINATES it in volume, without its scope ever being written down. Measured
#: against the REAL history of both repos (`git log`, not inferred):
#: ``Sibling``    : 288 `type(...)` commits - 174 idents recognised by THIS pattern - 150 (52%)
#:                  would have been invisible to the old pattern, purely from the hyphen
#:                  (``A01-1``, ``A04-2``, ``A03-20`` -- letters, digits, hyphen, digits).
#: ``Mnemosyne``  : the same shape found in ITS OWN history (``C20-1``..``C20-13`` etc.),
#:                  53 more commits recognised by this fixed pattern.
#: *This was not "C6 improperly closed"*: the mechanism did what it documented, on THE
#: population it had been measured against. The defect was that its scope was written down
#: nowhere -- a second caller (`plan_recul.py`, D5) that points `repo_root` somewhere other than
#: Mnemosyne silently inherits this same limit, without knowing it.
#:
#: **THIS PATTERN'S SCOPE, WRITTEN DOWN -- what the fix covers, and what it does NOT cover.**
#: Covered, checked against BOTH real repos: ``LETTERS(1-4) + DIGITS``, with an optional
#: ``-DIGITS`` suffix (``A1``, ``BR5``, ``A01-1``, ``C20-13``).
#: **NOT covered, NAMED rather than hidden** -- seen in this repo's real history, never
#: measured or fixed here: a LETTER suffix (``I3-a``, ``I3b``) and a SLASH-composed shape
#: (``A02-2/Q4``, ``D157/banc``). A caller that needs THESE shapes must measure them and extend
#: THIS pattern -- never write a second one that drifts.
_SUJET_RE = re.compile(r"^(feat|fix|test|docs|plan|orch)\(([A-Za-z]{1,4}\d+(?:-\d+)?)\):")

_COAUTHOR_RE = re.compile(r"^Co-Authored-By:\s*(.+?)\s*<", re.MULTILINE)

#: Separators outside any printable ASCII range a commit message could carry -- the same choice
#: as `derive_run.lire_tours` (`%x01`), one more byte to tell subject and body apart.
_SEP_ENREGISTREMENT = "\x01"
_SEP_CHAMP = "\x02"


@dataclass(frozen=True, slots=True)
class _Enregistrement:
    """One internal `type(IDENT):` commit, before projection into one of the two public views --
    NEVER exposed: it is the single hub that :func:`commits_par_ident` and
    :func:`commits_dates_par_ident` each project their own way, so that neither `git log` nor the
    regex is ever read twice."""

    ident: str
    type: str
    modele: str
    date: str


def _lire_commits(repo_root: Path) -> tuple[_Enregistrement, ...] | None:
    """A SINGLE `git log` call, a SINGLE reading of the subject -- ``None`` when the measurement
    CANNOT be taken (never confused with an absence of commits). Returns CHRONOLOGICAL order (git
    log returns the most recent first; the same reversal as `derive_run.lire_tours`)."""
    try:
        sortie = subprocess.run(  # noqa: S603, S607
            [
                "git",
                "-C",
                str(repo_root),
                "-c",
                "core.quotepath=false",
                "log",
                "--first-parent",
                f"--format={_SEP_ENREGISTREMENT}%aI{_SEP_CHAMP}%s{_SEP_CHAMP}%b",
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

    enregistrements: list[_Enregistrement] = []
    for bloc in sortie.stdout.split(_SEP_ENREGISTREMENT):
        if not bloc.strip():
            continue
        date, _, reste = bloc.partition(_SEP_CHAMP)
        sujet, _, corps = reste.partition(_SEP_CHAMP)
        trouve = _SUJET_RE.match(sujet)
        if not trouve:
            continue
        type_, ident = trouve.group(1), trouve.group(2)
        co_auteur = _COAUTHOR_RE.search(corps)
        modele = co_auteur.group(1) if co_auteur else ""
        enregistrements.append(_Enregistrement(ident=ident, type=type_, modele=modele, date=date))

    # Reversing the FLAT list before grouping produces EXACTLY the same per-ident order as
    # grouping first and then reversing each group -- the reversal commutes with filtering by
    # ident, checked before writing this comment, not assumed.
    return tuple(reversed(enregistrements))


def commits_par_ident(repo_root: Path) -> dict[str, tuple[Commit, ...]] | None:
    """Every commit in THIS repo whose subject references an ident, grouped by ident -- ``None``
 when the measurement CANNOT be taken (never confused with an absence of commits).

 **EXPOSED (2026-08-16), at the request of `production/plan_recul.py` (D5, signal 3, the
 "git-log" half)**: the `type(IDENT): subject` convention it reads is THIS REPO's, not some
 bespoke `C6` logic -- a second caller that counts the same commits by the same convention must
 read THIS function, never write a copy that drifts at the first regex change. `repo_root`
 stays an explicit parameter: nothing here assumes THIS repo over any other, only the caller
 chooses which history to count.

 **SCOPE, for whoever points `repo_root` somewhere other than Mnemosyne (D5, on a sibling project)**:
 read :data:`_SUJET_RE`'s docstring before trusting a LOW count on an unfamiliar population --
 a silent undercount is indistinguishable from a genuinely sparse population."""
    enregistrements = _lire_commits(repo_root)
    if enregistrements is None:
        return None
    par_ident: dict[str, list[Commit]] = {}
    for e in enregistrements:
        par_ident.setdefault(e.ident, []).append(Commit(type=e.type, modele=e.modele))
    return {ident: tuple(commits) for ident, commits in par_ident.items()}


def commits_dates_par_ident(repo_root: Path) -> dict[str, tuple[str, ...]] | None:
    """The EXACT sister of :func:`commits_par_ident` -- same commits, same grouping, same failure
 paths (``None`` if the measurement cannot be taken): only the PROJECTION changes, the ISO 8601
 date (``%aI``, with timezone) of each commit instead of its type and model.

 **EXPOSED (2026-08-16) for the same reason as its sister**: a second caller that needs the
 dates of a `type(IDENT):` series reads THIS function, never a second reading of `git log` with
 its own regex -- that is exactly the duplication `commits_par_ident` exists to prevent, and
 refusing to duplicate it is what made its first caller wait 73 minutes rather than reopen the
 class the hyphen fix had just closed. `Commit` (type + model) does not move; no existing
 caller of `commits_par_ident` is touched -- the two functions share :func:`_lire_commits`,
 never a second `git log`."""
    enregistrements = _lire_commits(repo_root)
    if enregistrements is None:
        return None
    par_ident: dict[str, list[str]] = {}
    for e in enregistrements:
        par_ident.setdefault(e.ident, []).append(e.date)
    return {ident: tuple(dates) for ident, dates in par_ident.items()}


def resume(racine: Path) -> str:
    """The routing journal's (C6) text render -- fail-open: a measurement that fails NAMES
    itself, it never takes the map down with it, since the map is the main surface (same
    discipline as :func:`~mnemosyne.runtime.derive_run.resume`, its neighbor in `carte_run.py`)."""
    dossier = racine / "docs"
    projet = next(
        (p for p in scan_plans(racine).projects if p.plan_path.parent == dossier), None
    )
    if projet is None or projet.reading is None:
        return "\U000026A0\U0000FE0F routing journal (C6) NOT MEASURED -- this repo's plan is not readable.\n"

    commits = commits_par_ident(racine)
    if commits is None:
        return "\U000026A0\U0000FE0F routing journal (C6) NOT MEASURED -- the git history could not be read.\n"

    entrees = journal(projet.reading.items, racine, commits)
    if not entrees:
        return (
            "routing journal (C6): 0 measurable item -- no closed item whose lane AND turns can "
            "both be derived.\n"
        )

    lignes = [f"routing journal (C6): {len(entrees)} closed item(s), measured"]
    for r in taux_de_reprise(entrees):
        if r.n == 0:
            lignes.append(f"  {r.case:<20s} n=0 (never taken)")
        else:
            marque = " <- COSTS MORE THAN IT SAVES" if r.cout_excessif else ""
            lignes.append(f"  {r.case:<20s} n={r.n:<3d} tours_moyen={r.tours_moyen:.1f}{marque}")
    if all(e.tours == 1 for e in entrees):
        lignes.append(
            "  \U000026A0\U0000FE0F zero rework anywhere -- the measurement does not bite yet, "
            "this is not proof of perfect routing (C6, word for word)."
        )
    return "\n".join(lignes) + "\n"
