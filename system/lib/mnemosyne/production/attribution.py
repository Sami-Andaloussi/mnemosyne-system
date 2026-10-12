"""P2 -- WHO HOLDS WHICH ARC: the registry at the EMITTER, and the refusal of collisions.

Follow-up from the flagship project's harvest (item `P2`: `poste_emit.py` + `R2-bis`). **THIS REPO
ALREADY NAMED THE GAP WITHOUT OFFERING A PLACE TO WRITE IT DOWN**: this repo's own orchestration
notes list verbatim what `make lot-emit` **does not provide** -- *"**ownership** (which chat holds
what), the **priority order** between chats, the **producer/judge separation** (D75), and
**cross-routing**"* -- concluding *"those four remain a human judgment call."* This module picks
up **one** of them: ownership, and only its mechanizable half -- **refusing an assignment that
collides.**

## The population, measured TODAY by this repo's own accessors (2026-09-08)

```
arcs in the plan (carte_par_arc)                            : 11
arcs declared held (ui_contract._qui_tient_par_arc)         :  6
   of which IN COLLISION -- two chats on the same arc       :  1   <- arc H: chat-2 AND chat-3
   of which the hold is STALE (the arc is done)             :  4   <- C, D, E, G
arcs declared that do not exist in the plan                 :  0
```

**The collision is REAL, it is there right now, and nothing in this repo names it.**
`make ui-json` publishes `qui_le_tient: ["chat-2", "chat-3"]` as a fact, without a word -- *a
dashboard that reads a declaration can never be more accurate than the declaration itself*, and
nobody ever asked it whether two names on one line was an anomaly.

## The two halves, and why only one REFUSES

- **COLLISION and UNKNOWN ARC refuse.** Two chats on one arc is exactly the write overlap that
  `E4`/`recouvrement` exists to prevent, one level up; an arc claimed that is not in the plan is a
  claim on nothing.
- **STALE HOLD publishes, it does not refuse -- and the number says why**: 4 of the 6 real holds
  are stale. A gate that refused on this would refuse two-thirds of the registry on day one, for a
  fact that hurts nobody (a finished arc someone still believes they hold blocks no work).
  *Publishing what is missing is not the same as refusing* -- the same doctrine as
  `fermeture_isolee.py`, and for the same measured reason.

**ADMISSION: THIS MECHANISM SERIALIZES NOTHING.** The defect named in the flagship project's harvest --
*"`_deja_pris` reads **without a lock**"* -- is **NOT** fixed here, and claiming otherwise would
fabricate a false barrier. Two simultaneous emissions would read the same registry and grant the
same arc. A lock exists in this repo (`guard/heavy_lock.py`) but its "queue" mode is **parked**
(duplicate of `D6` from the same harvest: *"building the queue now would mean building tooling for
a workflow this repo hasn't adopted yet"*). > This judge guards against an orchestrator FORGETTING,
never against a RACE between two of them.

**SECOND ADMISSION, measured on the flagship project and worth keeping**: *"I told 3 chats to edit
`chat-N.md` by hand [...] **all three undid each other's edit**"* -- **a correction made to a
GENERATED file is lost without warning.** This module writes NOTHING: it reads the posts the
chats write themselves and renders a verdict. That is deliberate -- generating the posts here
would recreate exactly the generated file that manual corrections keep losing.

PURE judge: population injected, no disk access, no `git`. English throughout for this mirror;
decision codes such as D75 / D6 refer to this project's own internal decision log.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

#: The three kinds of verdict, frozen as a SET -- swapping two labels would leave the count
#: identical and silent.
COLLISION: Final = "collision"
ARC_INCONNU: Final = "arc_inconnu"
TENUE_PERIMEE: Final = "tenue_perimee"
GENRES: Final[frozenset[str]] = frozenset({COLLISION, ARC_INCONNU, TENUE_PERIMEE})

#: The two kinds that REFUSE. The third only publishes -- see the header, and the number behind it.
GENRES_QUI_REFUSENT: Final[frozenset[str]] = frozenset({COLLISION, ARC_INCONNU})


@dataclass(frozen=True, slots=True)
class Verdict:
    """A fact named against the registry. ``tenants`` is always carried, even for a single name: a
    refusal that does not say WHO already holds the arc is not actionable."""

    genre: str
    arc: str
    tenants: tuple[str, ...]

    @property
    def refuse(self) -> bool:
        return self.genre in GENRES_QUI_REFUSENT

    @property
    def phrase(self) -> str:
        who = ", ".join(self.tenants) or "nobody"
        if self.genre == COLLISION:
            return (
                f"arc {self.arc}: TWO holders declared ({who}) — only one chat holds an arc "
                "(E2). Withdraw the extra claim BEFORE emitting"
            )
        if self.genre == ARC_INCONNU:
            return (
                f"arc {self.arc}: claimed by {who}, ABSENT from the plan — a claim on "
                "nothing. Check the label, or the plan you meant"
            )
        return (
            f"arc {self.arc}: held by {who} while the arc is DONE — a stale hold, "
            "it blocks nobody but it makes `qui_le_tient` lie"
        )


def verdicts(
    tenants: dict[str, tuple[str, ...]],
    *,
    arcs_du_plan: frozenset[str],
    arcs_finis: frozenset[str],
) -> tuple[Verdict, ...]:
    """The registry's full state, in a reproducible order (by kind, then by arc).

    **THE ORDER OF KINDS DECIDES WHAT GETS READ FIRST**, and it is deliberate: collision
    first (it refuses, and it costs lost work), unknown arc next (it also refuses), stale hold
    last (it does not refuse). *A false refusal placed first has already masked three real
    causes elsewhere in this repo.*"""
    trouves = [
        Verdict(COLLISION, arc, noms) for arc, noms in sorted(tenants.items()) if len(noms) > 1
    ]
    trouves += [
        Verdict(ARC_INCONNU, arc, noms)
        for arc, noms in sorted(tenants.items())
        if arc not in arcs_du_plan
    ]
    trouves += [
        Verdict(TENUE_PERIMEE, arc, noms)
        for arc, noms in sorted(tenants.items())
        if arc in arcs_finis
    ]
    return tuple(trouves)


def deja_pris(arc: str, tenants: dict[str, tuple[str, ...]], *, a_qui: str) -> tuple[str, ...]:
    """Who already holds ``arc``, EXCLUDING ``a_qui`` -- empty when the arc is free or already
    theirs.

    **`a_qui` IS EXCLUDED, AND THAT IS HALF THE MECHANISM.** Without this exclusion, re-issuing
    the mandate of the chat that already holds the arc -- an orchestrator's most common move --
    would be refused. *A door slower than the wall is never taken.*"""
    return tuple(nom for nom in tenants.get(arc, ()) if nom != a_qui)


def peut_attribuer(
    arc: str,
    *,
    a_qui: str,
    tenants: dict[str, tuple[str, ...]],
    arcs_du_plan: frozenset[str],
) -> Verdict | None:
    """The EMITTER's gesture: can ``arc`` be given to ``a_qui``? ``None`` = yes.

    This is where, and nowhere else, ownership becomes a GATE: `lot-emit` composes a mandate's
    content, never its ownership -- the orchestrator calling this answers the question `lot-emit`
    declares it cannot answer."""
    if arc not in arcs_du_plan:
        return Verdict(ARC_INCONNU, arc, (a_qui,))
    autres = deja_pris(arc, tenants, a_qui=a_qui)
    if autres:
        return Verdict(COLLISION, arc, (*autres, a_qui))
    return None


def resume(trouves: tuple[Verdict, ...], *, arcs: int, tenus: int) -> str:
    """The published text. It ALWAYS carries its two headline counts: a "healthy registry" read
    off zero arcs would look exactly like a "healthy registry" read off eleven."""
    entete = f"arc attribution: {arcs} arc(s) in the plan, {tenus} declared held"
    if not trouves:
        return f"\U00002705 {entete} — no collision, no stale hold.\n"
    refus = sum(1 for v in trouves if v.refuse)
    lignes = [f"\U000026D4 {entete} — {len(trouves)} fact(s), {refus} of which REFUSE(S):"]
    lignes += [f"   {'\U000026D4' if v.refuse else '\U0001F4E3'} {v.phrase}" for v in trouves]
    return "\n".join(lignes) + "\n"
