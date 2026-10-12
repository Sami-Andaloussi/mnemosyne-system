"""C5 -- THE POOL: split the IN, and above all RECOVER the OUT without routing it through
the orchestrator (a private planning doc; not part of this public mirror).

The operator's question: *"we'd need 15 Haiku. How do we manage those 15 Haiku? […] how do
we manage the OUT, where does it store them, how without drifting, how do we make sure
their work gets put in place directly?"*

**THE PATTERN ALREADY EXISTS, PROVEN ON BOOKS** (`system/skills/distillateur/emit_prompts.py` +
`distill_apply.py`, `distill-emit-split` → N agents → `distill-apply`): a deterministic split,
N mandates, the OUT lands on DISK — never in the orchestrator's context — and a deterministic
assembler REQUIRES completeness. This module generalizes that pattern beyond books: the same
shape, with nothing that presupposes a book section.

**LEVEL 2 — an incomplete assembly REFUSES; it does not publish a partial .** `Assemblage.complet`
is `False` the moment a SINGLE batch is missing, and `manquants` NAMES it (the index, never counted
down to zero in silence) — *a missing item that stays silent is a missing item that never existed
for the next reader*.

**NO SURFACE OF ITS OWN, BY CONSTRUCTION.** This module shells out to nothing, opens no file:
`decouper` and `assembler` are PURE functions over whatever the caller hands them, the exact same
choice as `plan_derive.py` (D1) — *"it talks to neither git nor disk: the edge hands it data
already read"*. The edge that writes the mandates to disk and reads the responses back is
:mod:`~mnemosyne.production.lot_emit` (E4): IT calls this module, never the reverse — the item's
`*Produces*` field says so in plain words.

**REPLAYED END TO END ON A REAL BATCH, on 2026-08-16 09:5x** — the orchestrator's first
measurement ("`make lot-emit` refuses that adopter's plan") was WRONG (root queried one level too low,
`.../that adopter/plan` instead of `.../that adopter`); once fixed, that adopter's root plan
is readable, `0 produit_problems` across its 21 items. Real population chosen: its arc `F`, 8
items, read **read-only**, never written (`git status --porcelain -- projects/` empty afterward —
verified, not assumed).
`decouper(items_f, taille=3)` → 3 batches (3, 3, 2); each batch EMITTED as a real file on disk
(already-PUBLISHED fields only — ident, status, `*Produces*` — no injected reasoning); 3 agents
ACTUALLY dispatched (Haiku, a bounded task: read the mandate, write ONE line of acknowledgment,
explicit ban on writing under `projects/`); `assembler()` reads back the three real OUT files:
`emitted == assembled == 3`, `complet=True`. Sabotage on the SAME real batch (one OUT removed from
disk): `complet=False`, `manquants=(1,)` — the missing one is NAMED, not just counted. Restored,
complete again.
*Live proof logged in a private session journal (2026-08-16 09:5x; not part of this public
mirror); a permanent, deterministic witness against the same real population lives in
`tests/orchestration/test_parc.py` (redispatching on every `pytest` run would be slow and
non-deterministic — the agent proof lives once, live, never inside the automated suite).*

**WHAT STILL REMAINS TO DO, NAMED RATHER THAN HIDDEN**: this module is still not wired INTO
`lot_emit.py` itself (`E4`) — the proof above emitted/assembled directly from this module and an
ad hoc edge script, never through `make lot-emit`. Wiring up the real call is a separate gesture,
not yet measured.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")
S = TypeVar("S")


@dataclass(frozen=True, slots=True)
class Lot(Generic[T]):
    """ONE group of items meant for ONE agent -- the index is the position within the split,
    never an identifier the caller invents: `decouper` sets it, nobody else."""

    indice: int
    items: tuple[T, ...]


def decouper(items: Sequence[T], *, taille: int) -> tuple[Lot[T], ...]:
    """The deterministic split -- same input, same output, always, never chance.

    **`taille` BOUNDS THE TOP, NEVER THE BOTTOM**: the last batch can be smaller than `taille`
    (the remainder of the division), never empty as long as at least one item remains -- an empty
    batch would be a mandate for nothing. An empty sequence yields an empty tuple, never an error:
    splitting NOTHING is a valid answer, not a refusal."""
    if taille < 1:
        raise ValueError(f"taille must be >= 1, got {taille}")
    return tuple(
        Lot(indice=i // taille, items=tuple(items[i : i + taille]))
        for i in range(0, len(items), taille)
    )


@dataclass(frozen=True, slots=True)
class Assemblage(Generic[T]):
    """The result of an assembly -- COMPLETE, or refused while NAMING what is missing.

    **`manquants` CARRIES BATCH INDICES, NEVER A COUNT** -- *a missing item silently counted
    down to zero is indistinguishable from a success; a named missing item never is.* Same
    principle as `plan_derive.Immobilite`: freeze the identity, never just the cardinal."""

    complet: bool
    rendus: tuple[T, ...]
    manquants: tuple[int, ...]


def assembler(
    lots: tuple[Lot[S], ...], lire_sortie: Callable[[Lot[S]], T | None]
) -> Assemblage[T]:
    """Reads EACH batch back via `lire_sortie` -- never from a context already in memory -- and
    REFUSES (`complet=False`) the moment a SINGLE batch returns `None`.

    **`lire_sortie` IS THE ONLY POINT OF CONTACT WITH DISK, AND IT IS NOT HERE**: this module
    stays pure (no `open`, no `Path`) -- it is the edge (`lot_emit.py`, E4) that supplies a
    function reading one real file per batch and returning `None` when it is absent. *An
    assembler that goes and fetches its own population itself can find it empty and return a
    green* -- the same lesson as D1, applied here to the OUT rather than to git history.
    **`None` IS THE ONLY SIGNAL OF ABSENCE**: an output that is EMPTY but RETURNED (e.g. an
    agent that honestly answers "found nothing") is NOT a missing item -- `lire_sortie` tells the
    two apart, never this module. *An empty answer and an absent answer are not the same
    sentence.*"""
    rendus: list[T] = []
    manquants: list[int] = []
    for lot in lots:
        sortie = lire_sortie(lot)
        if sortie is None:
            manquants.append(lot.indice)
        else:
            rendus.append(sortie)
    return Assemblage(complet=not manquants, rendus=tuple(rendus), manquants=tuple(manquants))
