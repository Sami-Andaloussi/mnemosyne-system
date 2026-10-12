"""H5 (line 5) -- a closure (``→``) that nothing in the repo distinguishes from a SOLITARY
gesture (per the private plan item that names it).

**WHAT LINE 5 ASKS FOR, AND WHAT A GATE CAN ACTUALLY HOLD**: "two proofs -- the `*Done
when*` clause actually RUN, and a NON-PRODUCER verdict (D75)". **A gate cannot verify that**: a
`*Done when*` clause having actually been run is a matter of JUDGMENT (was the right command
REALLY launched, was its output honestly read?), not of FORM -- no diff distinguishes it from a
bare claim. And "non-producer" runs into a MEASURED limit of this repo: the three chats all run
on the SAME model (`Claude Sonnet 5`), so the only signal git carries -- the `Co-Authored-By`
trailer -- CANNOT distinguish "chat 2 audited chat 3" from "chat 2 audited itself". *
`runtime/orphelins_run.py` already names this for a different question; the same limit applies
here, verbatim.*

**WHAT A GATE CAN ACTUALLY HOLD, MEASURED BEFORE WRITING A LINE**: has AT LEAST ONE DISTINCT
`Co-Authored-By` identity ever touched this ident, beyond the one that closes it? Measured
against the real repo (`git log`, not assumed): `B2` -- five commits, ALL `Claude Opus 5`, zero
second model -- is a REAL case in this repo that such a signal would have named. *This is not
proof of independence (D75); it is the FLOOR below which independence is STRUCTURALLY
impossible -- a closure that no second identity has ever touched cannot have been audited by a
third party, whatever meaning one gives to "third party".*

**WHY LEVEL 1 (publishes), NEVER LEVEL 2 (refuses) -- measured, not assumed.** Among items
marked CLOSED, 122 real commits in this repo are `Claude Sonnet 5` -- so a chat sometimes CLOSES
an item it produced itself, including after a REAL audit by ANOTHER chat running on the SAME
model. **A refusal built on this signal alone would block exactly this legitimate form** -- the
most common one in this repo (cross-chat audit) -- by confusing it with the true solo case it is
looking for. *Publishing what is missing is not refusing* -- the signal is real, bounded, honest:
it names a FLOOR (no second identity seen), never a PROOF (a genuinely independent audit).
"""

from __future__ import annotations

from dataclasses import dataclass

from .plan_format import PlanItem
from .routage_journal import Commit, STATUTS_FERMES


@dataclass(frozen=True, slots=True)
class FermetureSolitaire:
    """A CLOSED item whose known history carries NO second named identity.

    ``modele`` is the sole identity seen (``Co-Authored-By``), or ``None`` when NO known commit
    carried one -- the two cases are counted together (no second identity), but stay distinct in
    this field so the reader can see WHICH of the two they are looking at."""

    ident: str
    modele: str | None


def identites_vues(commits: tuple[Commit, ...]) -> frozenset[str]:
    """The NAMED `Co-Authored-By` identities of a series of commits -- a commit with no trailer
    (``modele == ""``) adds none: an absent trailer is neither an identity nor proof of
    solitude, it is just an absence, as elsewhere in this repo."""
    return frozenset(c.modele for c in commits if c.modele)


def fermetures_solitaires(
    items: tuple[PlanItem, ...], commits_par_ident: dict[str, tuple[Commit, ...]]
) -> tuple[FermetureSolitaire, ...]:
    """The CLOSED items (:data:`~mnemosyne.production.routage_journal.STATUTS_FERMES`) whose
    known history does not carry TWO distinct identities -- in plan order, never sorted: the
    plan's own order is already the one every other reader of this repo knows."""
    solitaires: list[FermetureSolitaire] = []
    for item in items:
        if item.status not in STATUTS_FERMES:
            continue
        identites = identites_vues(commits_par_ident.get(item.ident, ()))
        if len(identites) <= 1:
            solitaires.append(
                FermetureSolitaire(ident=item.ident, modele=next(iter(identites), None))
            )
    return tuple(solitaires)
