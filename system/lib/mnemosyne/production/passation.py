"""G10 -- THE HANDOFF OF A SESSION THAT DIES: a third party declares a peer's state BY MEASUREMENT.

Carried over from a harvest on another project, 2026-09-08 (the harvest report, `G10`).
Verbatim from that project: *« THE REAL STATE OF chat-2's WORKTREE, **declared by me because its session
no longer has the context to do it** […] its session concluded "nothing to handle". **Verified:
true of the PATH, false of the DURABILITY** »*.

**This is the MULTI-AGENT variant of invariant 15.** *Persist before compacting* covers **one**
session: the one about to compact. **Nothing covers a session DYING while others keep
working** -- and that is precisely the moment nobody has the context left to say what it was
leaving behind.

## The population, measured in THIS repo (2026-09-08)

```
commits where a chat DECLARES A PEER'S STATE in its subject line       : 21
   (`journal(chat-2): tour 18:56 -- a vide, chat 1 ferme R1`, etc.)
"handoff" / "dead session" in the orchestration governance document    :  0
"handoff" / "dead session" in the seat-roster document                 :  0
```

**Twenty-one declarations about a peer, and zero lines of doctrine on how to ground them.**
Every one of these 21 is made *on word of mouth*: the chat reads its neighbour's journal and
copies it.

## What this judge REFUSES, and why these three

1. **`sur_parole`** (`on word of mouth`) -- a declaration whose source is the peer itself. **This
   is the heart of G10**, and it is a property of FORM, so genuinely enforceable in code: *"declared
   by me because its session no longer has the context"* only holds value if "by me" means "I
   re-measured it", not "I copied it".
2. **`mesure_absente`** (`measurement absent`) -- a declaration for which NO measurement was taken.
   Distinct from the previous one: one lies about its source, the other has none. *Two absences of
   measurement do not compare equal when one of them is named.*
3. **`dementi_durabilite`** (`durability contradicts it`) -- "nothing to handle" while work is
   **not durable**. This is that project's exact case, and the only one of the three that would have
   caught the real error.
4. **`dementi_travail`** (`work contradicts it`) -- "nothing to handle" while the peer's own arcs
   still carry open items. The "PATH" half of that project's own sentence.

**AN ADMISSION, AND A BIG ONE: DURABILITY IS NOT ATTRIBUTABLE TO A SPECIFIC PEER HERE.** This
repo has every chat work in **a single tree** (a standing decision: *"they commit by green
fragment, on `main` -- that is how they see each other"*); a worktree per chat is **rejected**.
So `git status` returns what is not durable **for the whole repo**, never a named peer's own.
Consequence, stated rather than discovered: a `dementi_durabilite` CAN be **caused by a third
party's own work**. The judge still refuses, and that is the sound side to err on: a handoff
written over a dirty tree is false for someone, even if not for the one we assumed. **The day the
branching model changes, this measurement becomes attributable; until then, it is not, and no
line of this module claims otherwise.**

Pure judge: population injected, no disk, no `git`. English code & docstrings (D117).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

#: What a third party can declare about a peer. Frozen as a SET: swapping two labels would leave
#: the count identical and silent.
ETAT_RIEN: Final = "rien_a_traiter"
ETAT_EN_COURS: Final = "en_cours"
ETAT_BLOQUE: Final = "bloque"
ETATS: Final[frozenset[str]] = frozenset({ETAT_RIEN, ETAT_EN_COURS, ETAT_BLOQUE})

#: Where the declaration comes from. **`parole` IS NOT AN INVALID SOURCE BY ACCIDENT**: it is the
#: source of 21 out of 21 real declarations in this repo. Naming it is what makes it refusable.
SOURCE_PAROLE: Final = "parole"
SOURCE_MESURE: Final = "mesure"
SOURCES: Final[frozenset[str]] = frozenset({SOURCE_PAROLE, SOURCE_MESURE})

SUR_PAROLE: Final = "sur_parole"
MESURE_ABSENTE: Final = "mesure_absente"
DEMENTI_DURABILITE: Final = "dementi_durabilite"
DEMENTI_TRAVAIL: Final = "dementi_travail"
GENRES: Final[frozenset[str]] = frozenset(
    {SUR_PAROLE, MESURE_ABSENTE, DEMENTI_DURABILITE, DEMENTI_TRAVAIL}
)


@dataclass(frozen=True, slots=True)
class Declaration:
    """What a THIRD PARTY writes about a peer's state, and where they got it from."""

    pair: str
    etat: str
    source: str


@dataclass(frozen=True, slots=True)
class Mesure:
    """The INDEPENDENT measurement of a peer's state -- what the third party pulled themselves.

    ``items_ouverts``: the idents still open on the arcs the peer declares holding.
    ``non_durables``: the written, uncommitted paths (already filtered of parked classes by the
    edge, via `non_committe.est_parque` -- never a second parked-list here)."""

    pair: str
    items_ouverts: tuple[str, ...] = ()
    non_durables: tuple[str, ...] = ()
    #: ``False`` when the measurement could NOT be taken (`git` silent, plan unreadable). An
    #: impossible measurement and an empty measurement are two different statements, and conflating
    #: them would produce a false green: this is the field that keeps them apart.
    prise: bool = True


@dataclass(frozen=True, slots=True)
class Verdict:
    genre: str
    pair: str
    detail: tuple[str, ...] = ()

    @property
    def phrase(self) -> str:
        cite = ", ".join(self.detail[:4]) + ("…" if len(self.detail) > 4 else "")
        if self.genre == SUR_PAROLE:
            return (
                f"{self.pair}: state declared ON WORD OF MOUTH — a third party does not relay, "
                "they RE-MEASURE. Take the measurement yourself, then declare `source=mesure`"
            )
        if self.genre == MESURE_ABSENTE:
            return (
                f"{self.pair}: no independent measurement COULD be taken — a handoff without a "
                "measurement is not a handoff, it is a dated rumour"
            )
        if self.genre == DEMENTI_DURABILITE:
            return (
                f"{self.pair}: \"nothing to handle\" CONTRADICTED by DURABILITY — {len(self.detail)} "
                f"path(s) written and uncommitted ({cite}). *True of the path, false of the durability.*"
            )
        return (
            f"{self.pair}: \"nothing to handle\" CONTRADICTED by the WORK — {len(self.detail)} "
            f"item(s) still open on their arcs ({cite})"
        )


def juger(declaration: Declaration, mesure: Mesure | None) -> tuple[Verdict, ...]:
    """The gaps for ONE declaration, in order: the source first, the contradictions next.

    **THE SOURCE IS JUDGED BEFORE THE MEASUREMENT, AND THE ORDER IS THE MECHANISM.** A
    declaration made on word of mouth is refused *even if it happens to be true*: the rule is about
    the way of knowing, not the fact known. Judging the contradiction first would let every exact
    word-of-mouth statement through -- and it is exactly those that teach people to trust word of
    mouth."""
    trouves: list[Verdict] = []
    if declaration.source != SOURCE_MESURE:
        trouves.append(Verdict(SUR_PAROLE, declaration.pair))
    if mesure is None or not mesure.prise:
        trouves.append(Verdict(MESURE_ABSENTE, declaration.pair))
        return tuple(trouves)
    if declaration.etat == ETAT_RIEN:
        if mesure.non_durables:
            trouves.append(Verdict(DEMENTI_DURABILITE, declaration.pair, mesure.non_durables))
        if mesure.items_ouverts:
            trouves.append(Verdict(DEMENTI_TRAVAIL, declaration.pair, mesure.items_ouverts))
    return tuple(trouves)


def passation(
    declarations: tuple[Declaration, ...], mesures: dict[str, Mesure]
) -> tuple[Verdict, ...]:
    """The gaps across ALL declarations of one handoff, in the order the declarations were made."""
    return tuple(v for d in declarations for v in juger(d, mesures.get(d.pair)))


def resume(trouves: tuple[Verdict, ...], *, declarations: int) -> str:
    """The published text. It ALWAYS carries the number of declarations judged: "handoff sound" on
    zero declarations would read exactly like "handoff sound" on three."""
    entete = f"handoff: {declarations} peer declaration(s) judged"
    if not trouves:
        return f"\U00002705 {entete} — each one backed by an independent measurement that confirms it.\n"
    lignes = [f"\U000026D4 {entete} — {len(trouves)} gap(s):"]
    lignes += [f"   · {v.phrase}" for v in trouves]
    return "\n".join(lignes) + "\n"
