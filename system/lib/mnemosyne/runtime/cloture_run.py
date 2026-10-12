"""``make clotures`` — the EDGE of the signalement-closure judge (P1).

The only module of the pair that touches disk: it reads the frontmatter of each report under
`docs/signalements/` and **hands** the population to :func:`mnemosyne.production.cloture.verdict`.
No judging happens here.

**READERS ARE IMPORTED, NEVER RECOPIED.** ``status_of`` / ``field_of`` come from
:mod:`~mnemosyne.production.frontmatter_status` — *the* home of the format, the one the proposal
queue already uses. A second reader would give two truths about "what is this report's status",
and an audit already showed here that a second copy of a status pattern rewrote the BODY of a
report that merely cited `status:` in its prose.

## Three return codes

* ``rc 0`` — measurement taken, no closure is unattributable outside the ratchet.
* ``rc 1`` — refusal: a closure with no author outside the ratchet, a stale ratchet entry, a status
  outside the vocabulary, or an accepted defect with no stated cost.
* ``rc 2`` — measurement **impossible**: the folder is absent, or no report is readable. *Two
  absences of measurement never compare equal to a green.*

**WHAT THIS COMMAND IS NOT**: until the orchestrator wires it in, no gate calls it — so it is
**level 1**. Desired wiring: `make clotures`, plus a `tick` line on the same channel as
`make signalements`.

Read-only, no brick, no model, no network. (English here for the public mirror; the private
original's human-facing prose is French, D117.)
"""

from __future__ import annotations

import sys
from collections.abc import Iterable
from pathlib import Path

from ..production.cloture import Defaut, HERITAGE_SANS_AUTEUR, message, verdict
from ..production.frontmatter_status import field_of, status_of

#: ``parents[4]`` — `parents[3]` names `system/`, and a reader pointed at
#: `system/docs/signalements` finds NOTHING, hence "zero closures with no author", hence a green.
#: `test_la_RACINE_de_production_designe_le_DEPOT` judges THIS value specifically, apart from the
#: tests that inject their own: *injecting everywhere leaves the real value naked.*
RACINE = Path(__file__).resolve().parents[4]

DOSSIER = Path("docs") / "signalements"

#: The README is not a signalement. Copied from `signalements._NOT_A_SIGNALEMENT`, which is
#: private: the duplication is named here rather than left silent, and a test pins it.
PAS_UN_SIGNALEMENT = frozenset({"README.md"})

#: The accepted field names for a closure's AUTHOR, from the most canonical to the most tolerated.
#: None exists today (measured: 0/34) — it's the gesture the refusal asks for.
CHAMPS_AUTEUR: tuple[str, ...] = ("par", "traite_par", "clos_par", "by")

#: Same, for the COST of an accepted defect.
CHAMPS_COUT: tuple[str, ...] = ("cout", "cost", "prix")


def _premier_champ(chemin: Path, noms: Iterable[str]) -> str:
    """The first non-empty value among ``noms`` — ``""`` if none.

    A missing, empty, or unreadable field all render as ``""``: the edge does not claim to tell
    apart three causes the format itself doesn't distinguish."""
    for nom in noms:
        valeur = field_of(chemin, nom).strip()
        if valeur:
            return valeur
    return ""


def recenser(dossier: Path) -> tuple[Defaut, ...]:
    """The EDGE — the only disk access. It reads; it does not judge.

    **A REPORT WITH NO READABLE STATUS IS NOT SKIPPED** — it enters with ``statut=""`` and comes
    back out under :attr:`~mnemosyne.production.cloture.Verdict.inconnus`. Skipping it would be
    exactly the silent loss this pair exists to close — which is what `signalements._status_of`
    does, fail-open by design because it feeds the `tick`, which must never block."""
    if not dossier.is_dir():
        return ()
    defauts: list[Defaut] = []
    for chemin in sorted(dossier.glob("*.md")):
        if chemin.name in PAS_UN_SIGNALEMENT:
            continue
        defauts.append(
            Defaut(
                identifiant=chemin.stem,
                statut=status_of(chemin) or "",
                auteur=_premier_champ(chemin, CHAMPS_AUTEUR),
                cout=_premier_champ(chemin, CHAMPS_COUT),
            )
        )
    return tuple(defauts)


def main(
    argv: list[str] | None = None,
    *,
    racine: Path | None = None,
    heritage: frozenset[str] | None = None,
) -> int:
    """``racine`` and ``heritage`` are injectable FOR TESTS ONLY, never for production."""
    r = RACINE if racine is None else racine
    h = HERITAGE_SANS_AUTEUR if heritage is None else heritage
    v = verdict(recenser(r / DOSSIER), heritage=h)
    print(message(v))
    if v.non_mesure:
        return 2  # not measured: distinct from a refusal, and distinct from a green
    return 1 if v.refuse else 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main(sys.argv[1:]))
