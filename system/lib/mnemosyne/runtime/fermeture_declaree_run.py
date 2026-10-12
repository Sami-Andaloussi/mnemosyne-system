"""P9 -- the BOUNDARY of the "declared closure <-> flipped glyph" barrier. It alone touches `git`.

Two modes, one judge (:mod:`~mnemosyne.production.fermeture_declaree`):

```
python -m mnemosyne.runtime.fermeture_declaree_run --message-file .git/COMMIT_EDITMSG
python -m mnemosyne.runtime.fermeture_declaree_run --rev 8dd7505f
```

**THE RIGHT HOOK IS `commit-msg`, AND IT DOES NOT EXIST YET IN THIS REPO** (`.githooks/`
only carries `pre-commit` and `pre-push`, verified). `pre-commit` CANNOT hold this barrier: the
message is not yet written when it runs, so the "declared" half of the arrow is not readable
there. *Saying so is the opposite of a detail: a gate wired where its left half does not exist
would render a permanent green.*

**STATE OF THE WIRING AS OF 2026-09-08, MEASURED**: the `make fermeture-glyphe` target
exists. It is **NOT** in `make portes` / `make check`, and that is a measured choice, not an
oversight: run against this repo it **REFUSES today** (5 historical closures declared with no
flipped glyph).
*A gate that is born red does not get wired in* -- it would block every commit, which is
WORSE than doing nothing. It stays at **level 1** until its population turns green. And its
real home -- a `commit-msg` hook, the only place the message exists -- **still does not exist**
in `.githooks/`.

## The return codes, and what they SEPARATE

```
0  agreement         -- the message and the diff say the same thing
1  REFUSED           -- at least one named gap
2  NOT MEASURED       -- `git` did not respond, or the message could not be found
```

`2` is **never** a green: a mute instrument and a healthy repo do not compare. The
distinction does not survive `make` (a recipe that returns 1 and one that returns 2 both exit
with 2, measured elsewhere in this repo): it lives in the TEXT, and that is what must be read.
"""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Final

from ..production.fermeture_declaree import Bascule, bascules, ecarts, resume, statuts
from ..production.plan_format import ARCS_DIRNAME, DOOR_FILENAMES

#: Mnemosyne's own plan folder. Copied from `plan_format._DOSSIER_DU_PLAN` **because that
#: name is private**; the OTHER two halves of the scope (:data:`DOOR_FILENAMES`,
#: :data:`ARCS_DIRNAME`) are imported, never rewritten -- *a scope always leaks through
#: enumeration*, and this module adds only one token to it instead of four.
_DOSSIER_DU_PLAN: Final = "docs"


def dans_le_plan(chemin: str) -> bool:
    """Does this path carry items from MNEMOSYNE's OWN plan?

    Same derivation as `plan_format.champs_requis_pour` (doors come from :data:`DOOR_FILENAMES`,
    the arcs folder from :data:`ARCS_DIRNAME`), but not the same call: that function answers
    *"which FIELDS are required,"* this one *"is this file a plan"* -- two different questions,
    and conflating them would make one barrier's scope depend on another's.

    **Scope NAMED, not forgotten**: a PROJECT's own plan is not covered. Precedent `A5` -- a
    floor set on another project's plan is a disguised ceiling. A project that adopts this
    barrier passes its own predicate to :func:`mesurer`; it does not need to modify this one."""
    if not chemin.endswith(".md"):
        return False
    portes = {f"{_DOSSIER_DU_PLAN}/{nom}" for nom in DOOR_FILENAMES}
    return chemin in portes or chemin.startswith(f"{_DOSSIER_DU_PLAN}/{ARCS_DIRNAME}/")


def _git(racine: Path, *args: str) -> str | None:
    """A `git` output, or ``None`` when the measurement CANNOT be taken. Never `""` on
    failure: an empty string is an empty file, a `None` is a mute instrument."""
    try:
        sortie = subprocess.run(  # noqa: S603, S607
            ["git", "-C", str(racine), *args],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return sortie.stdout if sortie.returncode == 0 else None


def _contenu(racine: Path, reference: str, chemin: str) -> tuple[str, ...]:
    """The lines of ``chemin`` at ``reference`` -- empty when the file does not exist yet at
    that reference (a plan CREATED by this commit has no before, and that is a fact, not a
    failure: :func:`~mnemosyne.production.fermeture_declaree.bascules` already ignores newly
    appeared idents)."""
    brut = _git(racine, "show", f"{reference}:{chemin}")
    return tuple(brut.splitlines()) if brut is not None else ()


def mesurer(
    racine: Path,
    *,
    rev: str | None = None,
    portee: Callable[[str], bool] = dans_le_plan,
) -> tuple[Bascule, ...] | None:
    """The status transitions of the judged commit, or ``None`` if `git` did not respond.

    ``rev=None`` judges the INDEX (the commit being made: `HEAD` -> index); ``rev="<sha>"``
    judges a past commit (`<sha>^` -> `<sha>`). *Both paths exist because the barrier must be
    RE-RUNNABLE over history: a gate that cannot be replayed on the past cannot prove its
    refusal rate.*"""
    if rev is None:
        noms = _git(racine, "diff", "--cached", "--name-only", "-z")
        avant_ref, apres_ref = "HEAD", ""
    else:
        noms = _git(racine, "show", "--name-only", "--format=", "-z", rev)
        avant_ref, apres_ref = f"{rev}^", rev
    if noms is None:
        return None
    chemins = sorted({c for c in noms.split("\0") if c and portee(c)})
    avant: dict[str, str] = {}
    apres: dict[str, str] = {}
    for chemin in chemins:
        avant |= statuts(_contenu(racine, avant_ref, chemin))
        apres |= statuts(_contenu(racine, apres_ref, chemin))
    return bascules(avant, apres)


def _message(racine: Path, *, rev: str | None, fichier: Path | None) -> str | None:
    """The judged commit's message -- from the file `commit-msg` passes as `$1`, or from `git log`."""
    if rev is not None:
        return _git(racine, "log", "-1", "--format=%B", rev)
    if fichier is None:
        return None
    try:
        return fichier.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


#: ``parents[4]`` -- ``.../runtime/fermeture_declaree_run.py`` climbs up to the repo root.
#: ``parents[3]`` would name ``system/`` and would render a repo with no commits: this cost has
#: already been paid twice in `sites_run.py`, and a separate witness judges THIS value.
RACINE: Final = Path(__file__).resolve().parents[4]


def main(argv: list[str] | None = None, *, racine: Path | None = None) -> int:
    """``racine`` is injectable FOR WITNESSES, never for production -- its default of
    ``None`` (rather than :data:`RACINE` as the default value) is deliberate: a value evaluated
    at import time freezes, and *exercising a gate by injecting its population does not exercise
    the production population*."""
    args = list(sys.argv[1:] if argv is None else argv)
    rev: str | None = None
    fichier: Path | None = None
    while args:
        jeton = args.pop(0)
        if jeton == "--rev" and args:
            rev = args.pop(0)
        elif jeton == "--message-file" and args:
            fichier = Path(args.pop(0))
    r = RACINE if racine is None else racine

    message = _message(r, rev=rev, fichier=fichier)
    if message is None:
        print(
            "\U000026A0\U0000FE0F declared closure ↔ glyph: NOT MEASURED — no readable commit message "
            "(pass `--message-file <path>` or `--rev <sha>`).",
        )
        return 2
    mouvements = mesurer(r, rev=rev)
    if mouvements is None:
        print("\U000026A0\U0000FE0F declared closure ↔ glyph: NOT MEASURED — `git` did not respond.")
        return 2
    trouves = ecarts(message, mouvements)
    print(resume(mouvements, trouves), end="")
    return 1 if trouves else 0


if __name__ == "__main__":  # pragma: no cover - [OPERATOR] surface
    raise SystemExit(main())
