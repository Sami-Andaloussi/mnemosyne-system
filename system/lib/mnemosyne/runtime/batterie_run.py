"""``make batterie`` — the EDGE of the test battery that cannot melt down (G4).

The only module of the pair that touches the world: it walks `tests/`, hands each source to the
two pure readers of :mod:`~mnemosyne.production.batterie`, counts the collected tests, and
**hands** all of it to the judge. No judgement happens here.

## WHY THE SKIP AXIS IS STATIC, AND THE COST THAT JUSTIFIES IT

A full run of the battery takes more than **40 minutes** on this machine (measured on
2026-09-08, ~4,700 witnesses, a machine shared with other agents). *A gate slower than the wall
never gets used*: the dynamic half (failures, errors) therefore waits for a report it is
**handed**, it does not produce one itself.

**AND THE STATIC HALF IS NOT FREE EITHER — MEASURED, NOT ASSUMED**:
:func:`lire_les_formes` over the whole of `tests/` costs **2.56 s** (~5,000 witnesses, 2026-09-08).
An earlier version of this docstring claimed "half a second"; that was an estimate, and an
estimate written as a measurement is an exact lie. Consequence: **this is not a pre-commit block**
as it stands — the hook demands a near-zero idle cost. Two workable wirings:
(a) `make batterie` + one line in `tick` (the "disappeared" sense needs the whole tree);
(b) on the commit path, judge only the test files that are STAGED (the "new" sense only, a few
milliseconds).

* without ``--rapport``: ``collectes`` comes from ``pytest --collect-only -q`` (~0.5 s), and the
  failure/error axes are **empty** — the page says so in plain words rather than letting anyone
  believe it saw something actually run.
* with ``--rapport <junit.xml>``: the real failures and errors are included too.
* with ``--gel``: both freezes are reprinted **ready to paste in**, and nothing is judged.

**WHY ``--gel`` EXISTS, AND IT IS NOT A CONVENIENCE.** Both freezes bear on the WHOLE of
`tests/`, so **any witness added by someone else** can make them stale. A refusal that can only be
repaired by hand-copying 56 lines is a refusal that eventually gets disarmed: *a gate pricier than
the fault it names does not get repaired, it gets bypassed*. Here the repair is a single command,
and re-reading it stays a human gesture — the freeze never rewrites itself.

## Three return codes

* ``rc 0`` — measurement taken, no new shape.
* ``rc 1`` — refusal: failure, error, new or vanished skip, new or vanished silent witness.
* ``rc 2`` — measurement **impossible**: `tests/` absent, or zero tests collected. *An `OK` on an
  empty battery is the falsest green there is.*

**WHAT THIS COMMAND IS NOT**: until the orchestrator has wired it in, it is called by no
barrier at all — so **level 1**. Desired wiring: `make batterie`, plus one line of `tick`; the
pre-commit block, for its part, is only justified in shape (b) above.

Read-only, no brick, no model, no network. Prose is French by design (D117).
"""

from __future__ import annotations

import subprocess
import sys
import xml.etree.ElementTree as ET
from collections.abc import Callable
from pathlib import Path

from ..production.batterie import (
    MUETS_GELES,
    SAUTS_GELES,
    Rapport,
    message,
    sites_de_saut,
    temoins_muets,
    verdict,
)

#: ``parents[4]`` — `parents[3]` designates `system/`, and a reader pointed at `system/tests`
#: finds no file, hence "no silent witness", hence a green. Checked separately by a witness that
#: injects nothing: *injecting everywhere leaves the real value naked*.
RACINE = Path(__file__).resolve().parents[4]

DOSSIER = Path("tests")


def lire_les_formes(racine: Path) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """``(muets, sites_de_saut)`` over the whole tree — this module's only disk walk.

    An unreadable or unparsable file is **skipped**, never guessed at: *a per-item guarantee that
    raises kills the batch*. And a skipped file is an **unseen** shape, not an absent one."""
    muets: list[str] = []
    sauts: list[str] = []
    dossier = racine / DOSSIER
    for chemin in sorted(dossier.rglob("*.py")):
        try:
            source = chemin.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        try:
            relatif = str(chemin.relative_to(racine))
            muets.extend(temoins_muets(source, relatif))
            sauts.extend(sites_de_saut(source, relatif))
        except SyntaxError:
            continue
    return tuple(muets), tuple(sauts)


def compter_les_collectes(racine: Path) -> int:
    """How many tests `pytest` sees — ``0`` when it does not answer.

    ``0`` is NOT a green here: the judge turns it into
    :attr:`~..production.batterie.Verdict.non_mesure` and the edge turns it into an `rc 2`. *Two
    absences of measurement never compare equal.*"""
    try:
        sortie = subprocess.run(
            ["uv", "run", "pytest", "--collect-only", "-q"],
            cwd=racine,
            capture_output=True,
            text=True,
            timeout=300,
        )
    except (OSError, subprocess.SubprocessError):
        return 0
    for ligne in reversed(sortie.stdout.splitlines()):
        mots = ligne.split()
        if len(mots) >= 2 and mots[1] == "tests" and mots[0].isdigit():
            return int(mots[0])
    return 0


def lire_le_rapport(chemin: Path) -> tuple[tuple[str, ...], tuple[str, ...], int]:
    """``(echecs, erreurs, collectes)`` from a JUnit XML — ``((), (), 0)`` if it is unreadable.

    An unreadable report returns ``0`` collected: the edge will read that as a NON-MEASUREMENT,
    never as a healthy battery."""
    try:
        racine_xml = ET.parse(chemin).getroot()
    except (OSError, ET.ParseError):
        return (), (), 0
    echecs: list[str] = []
    erreurs: list[str] = []
    total = 0
    for cas in racine_xml.iter("testcase"):
        total += 1
        nom = f"{cas.get('classname', '')}::{cas.get('name', '')}"
        if cas.find("failure") is not None:
            echecs.append(nom)
        if cas.find("error") is not None:
            erreurs.append(nom)
    return tuple(echecs), tuple(erreurs), total


def main(
    argv: list[str] | None = None,
    *,
    racine: Path | None = None,
    sauts_geles: frozenset[str] | None = None,
    muets_geles: frozenset[str] | None = None,
    compter: Callable[[Path], int] | None = None,
) -> int:
    """Everything that is injectable is injectable FOR THE WITNESSES, never for production.

    ``compter`` is injectable because the only alternative would be to launch a real `pytest`
    inside every witness — *a harness that costs more than what it measures never gets used*.
    The real function is judged by its own witness, on this very repo."""
    arguments = list(argv or [])
    r = RACINE if racine is None else racine
    sg = SAUTS_GELES if sauts_geles is None else sauts_geles
    mg = MUETS_GELES if muets_geles is None else muets_geles

    if "--gel" in arguments:
        # PRINTS, DOES NOT WRITE. A freeze that rewrites itself always reports "nothing moved":
        # that is exactly the fault this module exists to close, remanufactured one level up.
        muets, sauts = lire_les_formes(r)
        for nom, valeurs in (("MUETS_GELES", muets), ("SAUTS_GELES", sauts)):
            print(f"{nom}: Final[frozenset[str]] = frozenset(\n    {{")
            for valeur in sorted(set(valeurs)):
                print(f'        "{valeur}",')
            print("    }\n)")
        return 0

    if not (r / DOSSIER).is_dir():
        print(f"\U000026A0\U0000FE0F BATTERY NOT FOUND: {r / DOSSIER} does not exist. Nothing could be measured.")
        return 2

    muets, sauts = lire_les_formes(r)
    echecs: tuple[str, ...] = ()
    erreurs: tuple[str, ...] = ()
    collectes = 0
    chemin_rapport = None
    if "--rapport" in arguments:
        index = arguments.index("--rapport")
        if index + 1 < len(arguments):
            chemin_rapport = Path(arguments[index + 1])
    if chemin_rapport is not None:
        echecs, erreurs, collectes = lire_le_rapport(chemin_rapport)
    else:
        collectes = (compter or compter_les_collectes)(r)
        print(
            "\U000026A0\U0000FE0F NO RUN REPORT: the FAILURE and ERROR axes saw NOTHING run "
            "(`--rapport <junit.xml>` feeds them). Only the STATIC shapes are judged."
        )

    v = verdict(
        Rapport(
            collectes=collectes,
            echecs=echecs,
            erreurs=erreurs,
            sites_de_saut=sauts,
            muets=muets,
        ),
        sauts_geles=sg,
        muets_geles=mg,
    )
    print(message(v))
    if v.non_mesure:
        return 2  # not measured: distinct from a refusal, and distinct from a green
    return 1 if v.refuse else 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main(sys.argv[1:]))
