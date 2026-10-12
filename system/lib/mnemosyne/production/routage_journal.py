"""C6 -- ROUTING IS VERIFIED AFTER THE FACT (per the project's own plan arc on self-sufficiency and routing).

`C3` (:mod:`.plan_ordre`, :func:`~mnemosyne.production.plan_ordre.router`) DECIDES who executes an
item -- the two-axis table, four cases. Nothing measured whether the decision was good. This module
closes the loop: for every item ACTUALLY CLOSED, it compares the case `router` would have chosen
against what the git history actually reports -- how many rounds it took, and by whom.

**THE JUDGE ALREADY EXISTS, FOR FREE (literally, straight from the item)**: a closed item
closes through ITS OWN command -- the question reduces to a measurable fact, never a new gate.
*Level 1: publish, never refuse* -- a gate here would punish bold routing, exactly what we want to
try.

**A "ROUND", DEFINED AND MEASURED, NEVER GUESSED**: this repo writes `type(IDENT): …` without
exception in its commit subjects (`feat`/`fix`/`test`/`docs`/`plan`/`orch`). `orch`/`plan`/`docs` are
the orchestrator or the log -- never an attempt by the producer to satisfy the closing condition.
`feat`/`fix`/`test` ARE: building, fixing after a defect was found, or arming a witness after a
reservation. **A round = a commit of one of these three types referencing the ident.** An item
closed on its first commit scores `tours=1`; every correction adds one. *Neither perfect nor hidden:
the definition lives here, measurable, and its bias (it cannot see uncommitted attempts) is named,
not buried.*

Nothing here reads a file or shells out -- pure over data the runtime edge fetches once (:mod:`
~mnemosyne.runtime.routage_journal_run`), the same split as every ``*_run.py`` sibling in this repo.

Code & docstrings English is the house style (D117) elsewhere; in the source repository this
module keeps its prose in French throughout, because its own subject matter -- the routing case
names themselves -- would make an English wrapping read as a translation layer that adds nothing
(the same reason `plan_ordre.py` mixes English prose with French field names). Translated here for
the public mirror; the underlying case identifiers (e.g. `sous_agent`, `le_parc`) are left exactly
as the code uses them.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Final

from .plan_format import PlanItem
from .plan_ordre import CASES, router

#: The three commit types that count as an ATTEMPT by the producer -- never `orch` (the orchestrator
#: routes or arbitrates, it does not satisfy the condition), never `docs`/`plan` (the journal and the
#: official closure DESCRIBE a round, they are not one).
TYPES_DE_TOUR: Final[frozenset[str]] = frozenset({"feat", "fix", "test"})

#: The statuses that count as "actually executed" -- the vocabulary the plan already carved in
#: (:mod:`.lot_emit`, ``Mandat.ouverts``), never reinvented here.
STATUTS_FERMES: Final[frozenset[str]] = frozenset({"fait", "clos"})


@dataclass(frozen=True, slots=True)
class Commit:
    """ONE commit referencing an ident, reduced to what this module judges: its type and its model.

    ``modele`` is the `Co-Authored-By` string (e.g. ``"Claude Sonnet 5"``), or ``""`` when the
    commit carries none -- never guessed, never an optimistic default."""

    type: str
    modele: str


@dataclass(frozen=True, slots=True)
class EntreeJournal:
    """One line of the routing journal -- a CLOSED item, its case, its model, its rounds."""

    ident: str
    case: str
    modele: str
    tours: int
    verdict: str


def construire_entree(
    item: PlanItem, racine: Path, commits: tuple[Commit, ...]
) -> EntreeJournal | None:
    """An entry for ``item``, or ``None`` when the measurement CANNOT be taken.

    **THREE ABSTENTIONS, NEVER A DEFAULT**: ``item.status`` outside :data:`STATUTS_FERMES`
    (nothing to measure, not closed yet); ``router`` returns ``case=None`` (cognition abstains, C3
    itself has no answer -- publishing a case here would invent what `router` refuses to guess);
    ``tours == 0`` (no `feat`/`fix`/`test` commit found -- the item exists but this module never saw
    it get built, an absence of evidence, never evidence of zero rounds)."""
    if item.status not in STATUTS_FERMES:
        return None
    routage = router(item, racine)
    if routage.case is None:
        return None
    tours = sum(1 for c in commits if c.type in TYPES_DE_TOUR)
    if tours == 0:
        return None
    modeles_nommes = [c.modele for c in commits if c.modele]
    modele = modeles_nommes[-1] if modeles_nommes else "inconnu"
    return EntreeJournal(
        ident=item.ident, case=routage.case, modele=modele, tours=tours, verdict=item.status
    )


def journal(
    items: tuple[PlanItem, ...], racine: Path, commits_par_ident: dict[str, tuple[Commit, ...]]
) -> tuple[EntreeJournal, ...]:
    """The full journal -- one entry per closed, measurable item, in plan order."""
    entrees = []
    for item in items:
        entree = construire_entree(item, racine, commits_par_ident.get(item.ident, ()))
        if entree is not None:
            entrees.append(entree)
    return tuple(entrees)


@dataclass(frozen=True, slots=True)
class RepriseParCase:
    """The rework rate of ONE case -- ``tours_moyen`` is ``None`` when ``n == 0``: a case that was
    never used does not have a rate of zero, it has NO rate at all -- not the same statement."""

    case: str
    n: int
    tours_moyen: float | None
    cout_excessif: bool


def taux_de_reprise(entrees: tuple[EntreeJournal, ...]) -> tuple[RepriseParCase, ...]:
    """The rework rate per case, all FOUR cases always present (same principle as
    :func:`~mnemosyne.production.plan_ordre.repartition`: a missing case would read as "never
    measured", not as "zero" -- so it is published with ``n=0`` rather than omitted).

    **``cout_excessif`` COMPARES, IT DOES NOT THRESHOLD**: a case costs "more than it saves"
    when its average rounds exceeds the GLOBAL average of rounds -- compared against the real
    population, never against a number picked in advance. *Measure the population before imposing a
    convention.* A case with ``n == 0`` can never be ``cout_excessif``: the absence of data is not a
    verdict."""
    par_case: dict[str, list[int]] = {c: [] for c in CASES.values()}
    for e in entrees:
        par_case.setdefault(e.case, []).append(e.tours)

    tous_les_tours = [e.tours for e in entrees]
    moyenne_globale = sum(tous_les_tours) / len(tous_les_tours) if tous_les_tours else None

    resultats = []
    for case in CASES.values():
        tours = par_case.get(case, [])
        n = len(tours)
        tours_moyen = sum(tours) / n if n else None
        cout_excessif = (
            tours_moyen is not None and moyenne_globale is not None and tours_moyen > moyenne_globale
        )
        resultats.append(
            RepriseParCase(case=case, n=n, tours_moyen=tours_moyen, cout_excessif=cout_excessif)
        )
    return tuple(resultats)
