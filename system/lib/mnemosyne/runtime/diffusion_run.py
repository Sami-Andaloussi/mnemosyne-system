"""``make diffusion`` (G8) — the EDGE: it pulls the repo's identity and launches the emission surfaces.

The judge (:mod:`mnemosyne.production.diffusion`) launches nothing. Here, and only here, do we
call ``git`` and ``make``.

Three gestures, one file:

* ``--tampon`` — prints **THE** line every diffused contract must carry. This is the single home
  (D163): an emitter calls it, never retypes it.
* ``--verifier [FILE|-]`` — the **RECEIVER**'s gesture: refuses (``rc 1``) a contract with no
  stamp, or whose stamp names a commit absent from ITS OWN history. **This is the only half that
  refuses**, and it has a legitimate green today.
* no argument — **PUBLISHES** the state of the six ``*-emit`` surfaces that run without an
  argument. ``rc 0`` always: 0/6 carry the stamp, so refusing here would be a wall born red that
  nobody could ever turn green without rewriting six modules. *A wall gets worked around; an
  acknowledgement gets read.*

Prose EN (D117).
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import date
from pathlib import Path

from ..production.diffusion import (
    MODIFIE,
    PROPRE,
    Population,
    SansDiffusion,
    perimee,
    population_nommee,
    rendre,
    tampon,
    verdict,
)

#: The diffusion surfaces that run WITH NO ARGUMENT. A named SET, never a count: renaming a
#: target must turn RED (it fails and reports itself "not emitted"), never quietly drop out of
#: the sweep. ``distill-emit``, ``distill-emit-split``, ``finish-emit``, ``lot-emit`` and
#: ``cours-emit`` are NOT in it: they require a project / an arc / a book and refuse (``rc 2``)
#: without one — including them would produce five "no stamp" lines that measure the absence of
#: an argument, not the absence of a stamp.
#:
#: **``distill-emit-split`` WAS MISSING FROM THIS ADMISSION, and an isolated audit measured
#: it**: the repo carries **11** ``*-emit`` targets, this freeze named 6 and the admission 4 — the
#: eleventh was neither judged nor declared excluded. It lived in the blind spot between the two
#: lists. *A freeze checked in only one direction (declared → real) lets every NEW target slip
#: into the blind spot in silence*;
#: :func:`test_les_cibles_emit_REELLES_sont_TOUTES_jugees_ou_DECLAREES_exclues` closes the other
#: direction. The ``*-emit`` targets deliberately OUTSIDE the sweep, because they require an
#: argument.
#: This set is not decorative: it is half of the bijection that the REAL → DECLARED direction
#: witness compares against the Makefile. A new ``-emit`` target must land in one of the two
#: lists, never between them.
EXCLUES_CAR_PARAMETREES = (
    "distill-emit",
    "distill-emit-split",
    "finish-emit",
    "lot-emit",
    "cours-emit",
)

SURFACES = (
    "plan-emit",
    "skill-emit",
    "garde-emit",
    "plan-gate-emit",
    "rangement-emit",
    "public-mirror-emit",
)


def _racine() -> Path:
    depuis_env = os.environ.get("CLAUDE_PROJECT_DIR", "").strip()
    return Path(depuis_env) if depuis_env else Path(__file__).resolve().parents[4]


def _git(racine: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(racine), *arguments],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


def population_du_depot(racine: Path, *, aujourdhui: str | None = None) -> Population:
    """The identity of THIS repo, NOW — raises ``RuntimeError`` if git does not respond.

    **A GIT FAILURE RAISES, IT DOES NOT RETURN AN EMPTY COMMIT.** A stamp carrying an empty
    ``commit=`` would be worse than no stamp at all: it would look like traceability.
    """
    tete = _git(racine, "rev-parse", "HEAD")
    if tete.returncode != 0:
        raise RuntimeError(
            f"git rev-parse failed: {tete.stderr.strip() or 'no message'} — "
            "no population can be named"
        )
    etat = _git(racine, "status", "--porcelain")
    if etat.returncode != 0:
        raise RuntimeError(
            f"git status failed: {etat.stderr.strip() or 'no message'} — "
            "impossible to tell whether the tree is clean, hence impossible to stamp honestly"
        )
    return Population(
        racine=racine.name,
        commit=tete.stdout.strip(),
        arbre=PROPRE if not etat.stdout.strip() else MODIFIE,
        emis_le=aujourdhui or date.today().isoformat(),
    )


def commits_connus(racine: Path, *, borne: int = 5000) -> frozenset[str]:
    """The commits THIS repo has — roughly the ``git merge-base --is-ancestor`` question.

    ``borne`` exists because an unbounded history is a resource that keeps growing (inv. 16); at
    5,000 it covers this repo very comfortably, and going over reads as "unknown commit", i.e. on
    the REFUSAL side. *A bound that gets it wrong must get it wrong by refusing.*
    """
    sortie = _git(racine, "rev-list", f"--max-count={borne}", "HEAD")
    if sortie.returncode != 0:
        return frozenset()
    return frozenset(ligne.strip() for ligne in sortie.stdout.splitlines() if ligne.strip())


def emissions(racine: Path, cibles: tuple[str, ...] = SURFACES) -> dict[str, str]:
    """What each surface REALLY produces — we run it, we do not read its code.

    A target that fails enters the population with its error text: it did not emit a stamp, which
    is exactly the fact to publish. Making it disappear would give one surface fewer and a more
    flattering percentage.
    """
    produits: dict[str, str] = {}
    for cible in cibles:
        sortie = subprocess.run(
            ["make", "-C", str(racine), cible],
            capture_output=True,
            text=True,
            timeout=180,
            check=False,
        )
        produits[cible] = sortie.stdout + sortie.stderr
    return produits


def main(argv: list[str] | None = None) -> int:
    """``rc 0`` published or contract acceptable · ``rc 1`` contract refused · ``rc 2`` instrument failure."""
    analyseur = argparse.ArgumentParser(
        description="The population where a diffused rule was measured (G8)."
    )
    analyseur.add_argument("--tampon", action="store_true", help="print the line to carry")
    analyseur.add_argument(
        "--verifier",
        metavar="FILE",
        help="verify a received contract ('-' for standard input)",
    )
    arguments = analyseur.parse_args(sys.argv[1:] if argv is None else argv)
    racine = _racine()

    if arguments.tampon:
        try:
            print(tampon(population_du_depot(racine)))
        except (OSError, RuntimeError, subprocess.SubprocessError) as panne:
            print(f"REFUSED: {panne}", file=sys.stderr)
            return 2
        return 0

    if arguments.verifier:
        try:
            texte = (
                sys.stdin.read()
                if arguments.verifier == "-"
                else Path(arguments.verifier).read_text(encoding="utf-8")
            )
        except OSError as panne:
            print(f"REFUSED: unreadable contract — {panne}", file=sys.stderr)
            return 2
        nommee = population_nommee(texte)
        if nommee is None:
            print(
                "\U000026D4 This contract names NO population: it does not say where its rule was "
                "measured, so nothing says it is true on your side.\n"
                "Remedy, at the EMITTER: `make diffusion TAMPON=1`, then put the line on top."
            )
            return 1
        raison = perimee(nommee, connus=commits_connus(racine))
        if raison is not None:
            print(
                f"\U000026D4 Contract REFUSED — {raison}.\n   Stamp read: commit={nommee.commit} "
                f"arbre={nommee.arbre} emitted on {nommee.emis_le}."
            )
            return 1
        print(
            f"\U00002705 Contract acceptable: measured on {nommee.commit[:12]} (emitted on {nommee.emis_le}), "
            "and that commit is in your history."
        )
        return 0

    try:
        etat = verdict(emissions(racine))
    except (OSError, SansDiffusion, subprocess.SubprocessError) as panne:
        print(f"REFUSED: {panne}", file=sys.stderr)
        print("This is NOT « everything is stamped »: the instrument did not measure.", file=sys.stderr)
        return 2
    print(rendre(etat))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
