"""The EDGE of :mod:`mnemosyne.production.plan_ordre` (D6) -- this is WHERE ``git`` gets opened.

**Nothing in ``plan_ordre`` reads a disk or shells out** (D6: "it derives itself, it does not
declare itself") -- ``duree_par_etape``/``duree_par_vague`` are PURE functions over dates already
resolved. This file is the ONLY place that reads ``git log`` to produce them, exactly the same
pattern as :mod:`mnemosyne.runtime.derive_run` for ``plan_derive`` (D1).

**NOT YET CALLED BY ``make carte``, and this is a named choice, not an oversight.** ``production/
carte.py`` is chat 2's batch; the wiring (one line that imports :func:`duree_du_plan` and displays
it) is ITS gesture, written once this measurement exists and has been proven -- routed, not taken.
Level 1 (D6): a published thermometer, never a gate that refuses.

**ISOLATED AUDIT OF 2026-08-16 -- NOT HELD on the clause itself, fixed here.** The first
version dated 9 of a downstream project's 18 items at ``jours=0.0`` -- all of them shared their opening AND their
closing on that project's ROOT commit (``socle: DEPOT NEUF après la perte d'objets``). One item
(``F7``) itself carries "CLOSED on 2026-07-29", NINE DAYS before the visible history even
begins, yet it still came out at exactly zero days. *An absence of measurement had compared EQUAL
to a real measurement, on the most flattering side* -- exactly what the clause forbids. See
:func:`_est_commit_racine`.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from ..production.plan_format import PlanReading, chemins_cites_par_produit, read_plan
from ..production.plan_ordre import DureeEtape, duree_par_etape

#: Statuses that count as CLOSED for D6 -- the same set as
#: :data:`~mnemosyne.production.plan_archive.CLOSED_STATUSES`, copied here rather than imported to
#: avoid the cycle ``plan_archive`` -> ``plan_format`` -> (nothing that comes back here): both
#: values are the same glyphs frozen in ``STATUS_BY_GLYPH``, so the duplication is a name, not a
#: second rule.
_FERMES: frozenset[str] = frozenset({"fait", "clos"})


def _relatif(repo_root: Path, chemin: str) -> str:
    """Brings an ABSOLUTE path back under ``repo_root``, unchanged otherwise.

    **TWO GIT SUBCOMMANDS, TWO CONVENTIONS -- measured, not assumed.** ``git log -- <chemin>``
    accepts an absolute path; ``git show <sha>:<chemin>`` REFUSES it (``fatal: path '...' exists on
    disk, but not in '<sha>'``) because it expects a path relative to the tree root. A function that
    receives ``item.source`` (often absolute, see :func:`~mnemosyne.production.
    plan_format.read_plan` called with ``origin=str(md)``) cannot guess which of the two
    conventions its caller followed -- it normalises, once, here.

    **Residual named by the 2026-08-16 audit, NOT closed here**: this function only judges the
    absolute/relative dichotomy -- an un-expanded ``~``, a ``..``, or an absolute path OUTSIDE
    ``repo_root`` (a root reached through an alias/symlink, e.g. ``/tmp`` vs ``/private/tmp`` on
    macOS) pass through unchanged. Neither case occurred on the real measured corpus; named so as
    not to claim coverage this function does not have.
    """
    p = Path(chemin)
    if p.is_absolute():
        try:
            return str(p.relative_to(repo_root))
        except ValueError:
            return chemin  # outside repo_root -- leave as-is, git will refuse cleanly
    return chemin


def _est_commit_racine(repo_root: Path, sha: str) -> bool:
    """True if ``sha`` has NO parent -- the first commit the VISIBLE history carries.

    A date resolved on this commit says nothing about WHEN the work actually started: it only
    says "at the earliest, we cannot see further back." *A recreated repo, a ``squash``, a shallow
    clone (``--depth``) all produce the same signature* -- this function does not guess WHICH ONE,
    it only names that the question cannot be answered by ``git log`` alone.
    """
    try:
        sortie = subprocess.run(  # noqa: S603, S607
            ["git", "log", "--format=%P", "-1", sha],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return sortie.returncode == 0 and not sortie.stdout.strip()


def date_ouverture(repo_root: Path, chemins: tuple[str, ...]) -> str | None:
    """The ISO 8601 date of the FIRST commit that touches one of the ``chemins`` -- ``None`` if
    none does, or if the only commit found is the ROOT commit (:func:`_est_commit_racine`).

    Each path is tried separately (``--follow`` only follows ONE file name at a time) and the
    OLDEST commit found, across all paths, wins: an item whose ``*Produit*`` cites several files
    opens on the first of the two, never the last.

    **BASENAME fallback when the direct path returns nothing** (2026-08-16 audit, Q1/Q3):
    ``chemins_cites_par_produit`` resolves nothing on disk by design -- an item citing
    ``` `pret_a_executer.py` ``` while the real file lives under ``validation/plan/
    pret_a_executer.py`` made ``git log -- pret_a_executer.py`` come back EMPTY (path does not
    exist at the root), and the item was counted as "opening not datable" even though a REAL path,
    just incomplete, existed. The ``**/<basename>`` fallback finds the file wherever it lives.
    """
    candidats: list[tuple[str, str]] = []  # (date, sha) -- to judge the root AFTER the min()
    for chemin_brut in chemins:
        chemin = _relatif(repo_root, chemin_brut)
        for cible in (chemin, f"**/{Path(chemin).name}"):
            try:
                sortie = subprocess.run(  # noqa: S603, S607
                    ["git", "log", "--follow", "--format=%aI%x09%H", "--", cible],
                    cwd=repo_root,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
            except (OSError, subprocess.SubprocessError):
                continue
            if sortie.returncode != 0:
                continue
            lignes = [ligne for ligne in sortie.stdout.splitlines() if ligne.strip()]
            if lignes:
                # `git log` returns the most RECENT first; the LAST in the list is the OLDEST.
                date, _, sha = lignes[-1].partition("\t")
                candidats.append((date, sha))
                break  # the direct path returned something -- the glob fallback is unneeded here
    if not candidats:
        return None
    date, sha = min(candidats, key=lambda c: c[0])
    if _est_commit_racine(repo_root, sha):
        return None
    return date


def date_fermeture(repo_root: Path, chemin_plan: str, ident: str) -> str | None:
    """The ISO 8601 date of the LAST transition to ``fait``/``clos`` in ``chemin_plan`` --
    ``None`` if the item never closes, or if its very first appearance is already closed on the
    ROOT commit (:func:`_est_commit_racine`).

    Replays HISTORY rather than guessing from a diff: every commit touching ``chemin_plan``, in
    chronological order, is re-read via ``git show`` then :func:`read_plan` -- the SAME reader
    used everywhere else in this repo, never a second grammar that would drift from the real one.

    **THE LAST TRANSITION, NOT THE FIRST (2026-08-16 audit, Q4).** The original version
    returned the FIRST closing seen -- on a constructed case (opening, closing at D+2, reopening,
    re-closing at D+19), it published 2 days for a real cost of 19, i.e. 89 % of the step's cost
    lost. *A reopening is precisely the signal that a step cost more than expected; publishing it
    as if it had closed on the first try lies in the most flattering direction.* This version
    follows EVERY open→closed transition and keeps the LAST one, consistent with the ``fait``/
    ``clos`` state the calling read has already established today.
    """
    chemin_plan = _relatif(repo_root, chemin_plan)
    try:
        sortie = subprocess.run(  # noqa: S603, S607
            ["git", "log", "--reverse", "--format=%H%x09%aI", "--", chemin_plan],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if sortie.returncode != 0:
        return None
    derniere_fermeture: str | None = None
    sha_derniere_fermeture: str | None = None
    etait_ferme = False
    for ligne in sortie.stdout.splitlines():
        if not ligne.strip():
            continue
        sha, _, quand = ligne.partition("\t")
        try:
            contenu = subprocess.run(  # noqa: S603, S607
                ["git", "show", f"{sha}:{chemin_plan}"],
                cwd=repo_root,
                capture_output=True,
                text=True,
                timeout=30,
            )
        except (OSError, subprocess.SubprocessError):
            continue
        if contenu.returncode != 0:
            continue
        lecture = read_plan(contenu.stdout, origin=chemin_plan)
        item = next((i for i in lecture.items if i.ident == ident), None)
        ferme_maintenant = item is not None and item.status in _FERMES
        if ferme_maintenant and not etait_ferme:
            derniere_fermeture, sha_derniere_fermeture = quand, sha
        etait_ferme = ferme_maintenant
    if derniere_fermeture is None:
        return None
    if _est_commit_racine(repo_root, sha_derniere_fermeture):
        return None
    return derniere_fermeture


def duree_du_plan(repo_root: Path, reading: PlanReading, chemin_porte: str) -> tuple[DureeEtape, ...]:
    """End to end: the CLOSED items of ``reading``, dated via ``git log`` in ``repo_root``, then
    passed to :func:`~mnemosyne.production.plan_ordre.duree_par_etape` -- the function ``make
    carte`` (chat 2) will call once wired in (see the warning at the top of this module).

    ``item.source`` carries the REAL file each item lives in (the gate for ``""``, an arc
    otherwise) -- a folder-shaped plan has its closings written across different files, never all
    in ``chemin_porte``.
    """
    fermes = tuple(item for item in reading.items if item.ident and item.status in _FERMES)
    ouvertures: dict[str, str | None] = {}
    fermetures: dict[str, str | None] = {}
    for item in fermes:
        chemins = chemins_cites_par_produit(item.field("produit") or "")
        ouvertures[item.ident] = date_ouverture(repo_root, chemins) if chemins else None
        fermetures[item.ident] = date_fermeture(repo_root, item.source or chemin_porte, item.ident)
    return duree_par_etape(tuple(item.ident for item in fermes), ouvertures, fermetures)
