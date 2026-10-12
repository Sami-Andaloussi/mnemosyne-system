"""``P4`` — the **EDGE** of the rotation cap: it reads git, the judge decides.

The judge is :mod:`mnemosyne.production.plafond_rotation` (pure, population injected). Here, and
only here, do we touch the world: ``git`` is called, and it is **injectable** so the rest of the
suite stays brick-free (D126).

**TWO MODES, AND BOTH HAVE A CALLER** — a mode with no caller would be dead code:

* ``--mis-en-scene``: the **COMMIT-GATE** mode. It reads the INDEX (``git show :<path>``), never
  the disk — *a partial staging makes the two diverge, and judging the disk would bless a commit
  nobody has read*. **Zero cost when empty**: if no covered file is staged, it exits ``0``
  **before** any further call to git. This is the same discipline ``.githooks/pre-commit`` holds
  itself to ("its cost when empty must stay zero"), and it is what keeps the gate fast enough to
  actually be taken (*a gate slower than the wall is never used*).
* **repo** mode (default): it judges the covered files **tracked by git**, as they stand. This is
  the mode where :data:`~mnemosyne.production.plafond_rotation.POPULATION_VIDE` really bites: the
  day the journals get renamed, the commit gate silently goes blind and **nothing** would turn red;
  here, zero covered files exits ``2`` and says so.

**Three exit codes, three natures** (and the ``2`` is what the contract requires of an empty
population):

.. code-block:: text

    0  nothing to say (or, in gate mode, nothing covered is staged)
    1  REFUSED: a cap exceeded, or a cut with no archive
    2  INSTRUMENT FAILURE: no covered file found where there should have been one

Prose EN (D117). Neighbour: ``.githooks/pre-commit``, which already carries the plan barrier — it
is the orchestrator's call whether to graft this edge onto it or make it a separate ``make`` target.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable, Sequence

from ..production.plafond_rotation import (
    DOSSIER_ARCHIVE,
    PLAFOND_LIGNES,
    POPULATION_VIDE,
    TOLERANCE_COUPE_LIGNES,
    Fichier,
    est_couvert,
    resume,
    verdict,
)

#: A git call: receives the arguments, returns ``(code, output)``. Injectable — the suite never
#: needs a real repo, and the module never needs a fake one.
Git = Callable[[Sequence[str]], "tuple[int, str]"]


def git_reel(args: Sequence[str]) -> tuple[int, str]:  # pragma: no cover - the real git
    """The production git call. ``capture_output``: a git error must not pollute the refusal."""
    fini = subprocess.run(["git", *args], capture_output=True, text=True)
    return fini.returncode, fini.stdout


#: ``git show :<path>`` (EMPTY revision) designates the **INDEX** blob — it is the same read
#: that ``.githooks/pre-commit`` performs, and the only one that judges what will actually be committed.
INDEX = ""


def _lignes(git: Git, revision: str, chemin: str) -> int | None:
    """The number of lines of ``chemin`` at ``revision`` — ``None`` if the file is not there.

    ``revision=INDEX`` (empty string) reads the index; ``revision="HEAD"`` reads the last commit.

    ``None`` is not ``0``: a file that is BORN in this commit has lost nothing, and conflating
    the two would manufacture a false cut on every creation.
    """
    code, sortie = git(["show", f"{revision}:{chemin}"])
    if code != 0:
        return None
    return len(sortie.splitlines())


def _lignes_archivees(git: Git) -> int:
    """The lines ADDED under ``docs/postes/archive/`` by the staged commit.

    Summed over the whole folder, never file by file: a rotation can land in several pieces, and
    requiring one archive per journal would invent a convention nothing enforces.
    """
    code, sortie = git(["diff", "--cached", "--numstat", "--no-renames", "--", DOSSIER_ARCHIVE])
    if code != 0:
        return 0
    total = 0
    for ligne in sortie.splitlines():
        colonnes = ligne.split("\t")
        if len(colonnes) >= 3 and colonnes[0].isdigit():
            total += int(colonnes[0])
    return total


def population_mise_en_scene(git: Git) -> tuple[Fichier, ...]:
    """The covered files **staged**, read from the INDEX.

    Returns ``()`` — not a noisy empty population — when nothing covered is staged: this is the
    ordinary case for 4 commits out of 5, and the edge exits ``0`` without calling git even once more.
    """
    code, sortie = git(["diff", "--cached", "--name-only", "--no-renames"])
    if code != 0:
        return ()
    chemins = tuple(c for c in sortie.splitlines() if c and est_couvert(c))
    if not chemins:
        return ()
    archivees = _lignes_archivees(git)
    fichiers = []
    for chemin in chemins:
        indexees = _lignes(git, INDEX, chemin)
        if indexees is None:  # removed from the index: nothing left to judge on this path
            continue
        fichiers.append(
            Fichier(
                chemin=chemin,
                lignes=indexees,
                lignes_avant=_lignes(git, "HEAD", chemin),
                lignes_archivees=archivees,
            )
        )
    return tuple(fichiers)


def population_du_depot(git: Git) -> tuple[Fichier, ...]:
    """The covered files **tracked by git**, judged on ``HEAD``.

    ``lignes_avant`` is deliberately ``None`` here: outside a commit there is no "before", so
    the cut clause does not apply — judging it against an invented difference would produce a
    refusal that no gesture could ever lift.
    """
    code, sortie = git(["ls-files", "--", "docs/postes"])
    if code != 0:
        return ()
    chemins = tuple(c for c in sortie.splitlines() if c and est_couvert(c))
    fichiers = []
    for chemin in chemins:
        n = _lignes(git, "HEAD", chemin)
        if n is None:
            continue
        fichiers.append(Fichier(chemin=chemin, lignes=n, lignes_avant=None, lignes_archivees=0))
    return tuple(fichiers)


def juger(
    fichiers: Sequence[Fichier],
    *,
    jour: str,
    plafond: int = PLAFOND_LIGNES,
    tolerance: int = TOLERANCE_COUPE_LIGNES,
) -> tuple[int, str]:
    """``(code, texte)`` — **the line that turns a verdict into a refusal**, and it alone.

    Three outcomes, never two: ``2`` for the instrument failure, ``1`` for the refusal, ``0``
    otherwise. Collapsing the ``2`` onto the ``1`` would destroy the distinction the judge built;
    hardcoding ``return 0`` would pass everyone. ``test_plafond_rotation.py`` freezes all three.
    """
    refuse = verdict(fichiers, plafond=plafond, tolerance=tolerance, jour=jour)
    texte = resume(fichiers, refuse, plafond=plafond)
    if any(r.genre == POPULATION_VIDE for r in refuse):
        return 2, texte
    return (1 if refuse else 0), texte


def main(
    argv: Sequence[str] | None = None, *, git: Git | None = None, jour: str | None = None
) -> int:
    """CLI. ``--mis-en-scene`` = commit gate; no argument = repo audit."""
    from datetime import date

    args = list(argv or ())
    appel: Git = git if git is not None else git_reel
    quand = jour if jour is not None else date.today().isoformat()

    if "--mis-en-scene" in args:
        fichiers = population_mise_en_scene(appel)
        if not fichiers:
            print("plafond-rotation: no covered file staged — nothing to judge.")
            return 0
    else:
        fichiers = population_du_depot(appel)

    code, texte = juger(fichiers, jour=quand)
    print(texte)
    return code


if __name__ == "__main__":  # pragma: no cover
    import sys

    sys.exit(main(sys.argv[1:]))
