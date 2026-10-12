"""H6 -- THE WIRING: `plan_ordre.file_d_attente()` PRODUCES a mandate, instead of being an engine
that nobody calls.

**LEVEL 1 ONLY, AND IT IS WRITTEN IN THE ITEM.** This module replaces NOTHING: it renders a
**derived** mandate, published ALONGSIDE the manual mandate an orchestrator still writes by hand.
*Level 2 (the manual rejected) only arms once the diff is judged, never before* -- nothing here
writes into a post, nothing refuses a closing.

**DELIBERATELY POOR, AND THAT IS THE POINT.** `file_d_attente` renders an identifier, a rank, a
mechanical reason -- never the personalized comment, the named warning, the lesson reminder a
human writes. *A generation enriched to resemble the manual it is compared against hides exactly
the gap the clause asks to be published.* This module therefore does NOT attempt to produce
comparable prose: it renders what the engine actually knows how to say, so the `diff` shows, with
no varnish, everything the hand adds that the machine ignores.

State of the ground, measured 2026-08-16: `plan_ordre.ordonner()`/`file_d_attente()` exist and are
proven (`B2`, closed) -- and until now, NOTHING called them to produce a post. Every post written
tonight was rewritten by hand, 8 to 9 sections stacked, zero derived from the engine.

**STATUS AND LOAD ADDED (2026-08-16, 12:5x) -- THIS IS NOT ENRICHING TOWARD THE MANUAL.** Two
distinct non-producers (chat 1, chat 2) measured that this module published `items` and nothing
else, while each item's status and its `À lire` load are FACTS OF THE PLAN, already read
(`item.status`) or already proven elsewhere (`a_lire.py`, C4) -- never prose this module would
invent. **Deliberate poverty protects against a fabricated comment, never against data the plan
already carries.** The output stays a COUNT (number of references, bytes), never the list of
references themselves -- listing each reference belongs to `a_lire.rendre_gabarit` (the full
mandate), not to this poor generator.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .a_lire import Charge, charge_en_octets
from .plan_format import PlanReading
from .plan_ordre import Rang, file_d_attente


@dataclass(frozen=True, slots=True)
class MandatDerive:
    """The top of the queue, as the engine computes it -- nothing more than facts already read."""

    rangs: tuple[Rang, ...]
    #: Total number of heads the queue managed to rank -- so the reader knows how much `rangs`
    #: leaves out, never a truncated list without saying so.
    total_range: int
    #: The status of each item in `rangs`, SAME INDEX -- `item.status`, already read by `mandat_derive`
    #: to compute `faits`, never exposed before this pass.
    statuts: tuple[str, ...]
    #: The `À lire` load of each item in `rangs`, SAME INDEX -- `None` when the item carries
    #: no `À lire` field (same convention as :func:`~mnemosyne.production.a_lire.charge_en_octets`).
    charges: tuple[Charge | None, ...]


def mandat_derive(
    reading: PlanReading, *, racine: Path, faits: frozenset[str] | None = None, n: int = 5
) -> MandatDerive:
    """The first `n` heads of the queue derived from the engine (`B2`), with their status and load
    -- facts already read or already proven elsewhere, NEVER an added comment.

    `racine` is MANDATORY, no silent default -- the load reads the disk (`a_lire.py`), and a
    default that omitted it would make the code guess a root, the same fault as `faits=frozenset()`
    documented right below.

    `faits` defaults to being derived from status, same rule as `carte.py`: an item marked `fait`
    counts as satisfied for its dependents, never guessed at zero (measured: the default value
    `frozenset()` had missed 5 ranks out of 7 on this very repo, `carte.py:312-321`)."""
    if faits is None:
        faits = frozenset(item.ident for item in reading.items if item.status == "fait")
    # `File` defines `__iter__` for a 2-tuple unpacking `(rangs, ignorees)` -- AFTER
    # unpacking, `rangs_tous` IS the tuple of `Rang`, never the `File` object: `.rangs` on it
    # would raise. Measured directly against `carte.py:333` (`tuple(file)` after the same
    # unpacking), not guessed from the variable's name.
    rangs_tous, _ignorees = file_d_attente(reading, faits=faits, a_faire=frozenset({"a_faire"}))
    rangs = tuple(rangs_tous)[:n]
    # Each `ident` in `rangs` comes from `file_d_attente(reading, ...)`, so it necessarily exists in
    # `reading.items` -- no extra guard, the population is the same on both sides.
    par_ident = {item.ident: item for item in reading.items}
    statuts = tuple(par_ident[r.ident].status for r in rangs)
    charges = tuple(charge_en_octets(par_ident[r.ident], racine) for r in rangs)
    return MandatDerive(rangs=rangs, total_range=len(rangs_tous), statuts=statuts, charges=charges)


def rendre_mandat(mandat: MandatDerive) -> tuple[str, ...]:
    """The lines published for `mandat` -- identifier, rank, status, MECHANICAL reason, and a
    load COUNT (never the list of references: see the module's docstring)."""
    if not mandat.rangs:
        return ("(empty queue -- nothing doable could be ranked)",)
    lignes = [f"derived mandate -- {mandat.total_range} head(s) ranked, top {len(mandat.rangs)}:"]
    for r, statut, charge in zip(mandat.rangs, mandat.statuts, mandat.charges, strict=True):
        peril = " PERISHABLE" if r.perissable else ""
        if charge is None:
            a_lire = " · to read: NONE"
        else:
            n_refs = len(charge.references_resolues) + len(charge.references_non_resolues)
            a_lire = f" · to read: {n_refs} ref. ({charge.octets} b)"
        lignes.append(
            f"  #{r.rang} {r.ident} [{statut}] (unblocks {r.debloque}{peril}){a_lire} -- {r.raison}"
        )
    return tuple(lignes)
