"""G9 -- PRECEDENCE: a REPOSITORY PROCEDURE takes priority over the PROMPT OF A MANDATE.

Surfaced from the 2026-09-08 harvest of another project (tagged `G9`):
*« FUSION.md takes priority over the mandate in case of contradiction — that is what let the agent
catch its principal's error »*.

 **The first half is banal, the second is rare.** That the delegated agent INSPECTS and the
orchestrator WRITES — everyone does that. But **most agent systems make the prompt the supreme
authority**: a false mandate produces false work, and the subordinate has no recourse that does not
go through negotiation. **This is the only mechanism in the corpus that lets an ISOLATED
subordinate correct its principal WITHOUT NEGOTIATING.** Orthogonal to `D75` (which separates
producer and judge; here it is inspector and writer).

## The population, measured in THIS repository (2026-09-08)

```
precedence written down anywhere already (docs/, CLAUDE.md, or this repo's own policy files) : 0
commits whose subject names an error / a false premise IN A MANDATE : 17
```

This repository already carries the MIRROR face of this lesson in the user's own persistent memory
(measured at **5 h**) -- *a false mandate biases the auditor toward its principal's error.* **What
was missing is the RECIPIENT face: the permission, written in advance, to disobey the mandate when
the repository says otherwise.** A lesson that lives only in the ISSUER's memory protects no
isolated agent.

## THE ADMISSION, IN SO MANY WORDS: NO BARRIER DETECTS A CONTRADICTION

*A lesson with no barrier is a wish* (A2), so here is exactly what is held and what is not:

* **HELD (a real barrier)**: every mandate issued CARRIES the precedence clause and the ADDRESS of
 the procedures that take priority, and **each of those addresses must exist on disk**. A dead
 address makes it red. *A document nothing points to does not exist — and a pointer to nothing is
 worse, because it looks like a pointer.*
* **NOT HELD, and no line claims it is**: **nothing detects that a prompt CONTRADICTS a
 procedure.** That is a question of meaning, not of form; a judge that claimed to settle it would
 be a text detector dressed up as a gate. And **nothing obliges an agent to obey the precedence**
 once it has read it. This module guarantees it was RECEIVED, never that it is USED.

Pure judge: population injected, no disk access. (Source prose is French, D117; translated here.)
"""

from __future__ import annotations

from typing import Final

#: The documents of THIS repository that take priority over a mandate's prompt, **frozen as a SET**:
#: swapping two addresses would leave the count identical and silent.
#:
#: **WHY THESE FIVE, AND NOT "ALL OF `docs/`"**: a procedure only takes priority if it is
#: OPPOSABLE — written, versioned, and read by both parties. These five are: the first two hold by
#: construction (`CLAUDE.md` is loaded every session, `ARCHITECTURE.md` carries the design rules
#: every module is built on), the other three are the procedures this repository imposes on the
#: sessions that work on it — how a change is sent (`CONTRIBUTING.md`), the shape a long piece of
#: work takes (`docs/FORMAT_PLAN.md`), and what a session does when the system breaks underneath it
#: (`docs/signalements/README.md`). A working document or a dated measurement takes priority over
#: nothing: it merely informs.
#:
#: **EVERY ADDRESS HERE IS A DOCUMENT THIS REPOSITORY ACTUALLY SHIPS**, and that is the whole
#: point of the disk check below: an address naming a document that lives somewhere else would be
#: dead on arrival, and the gate would be red forever. *A pointer to nothing is worse than no
#: pointer: it looks like a pointer.*
ADRESSES_QUI_PRIMENT: Final[tuple[str, ...]] = (
    "CLAUDE.md",
    "ARCHITECTURE.md",
    "CONTRIBUTING.md",
    "docs/FORMAT_PLAN.md",
    "docs/signalements/README.md",
)

#: The clause itself — **A SINGLE SOURCE**, consumed by `lot_emit.rendre()` and checked by the
#: runtime edge. Copying it into a document would let the two drift apart (D163: the address, never
#: the copy).
CLAUSE: Final = (
    "precedence: a REPOSITORY PROCEDURE takes priority over THIS MANDATE in case of contradiction. "
    "If this text contradicts one of the documents below, the document wins — you SAY so and you "
    "follow the document; you do not negotiate and you do not obey the mandate. "
    "\U000026D4 Nothing DETECTS a contradiction: it is your own reading that finds it, and it is the only "
    "recourse an isolated agent has against its principal's error. The documents that take "
    "priority: " + " · ".join(ADRESSES_QUI_PRIMENT) + "."
)

CLAUSE_ABSENTE: Final = "clause_absente"
ADRESSE_ABSENTE: Final = "adresse_absente"
ADRESSE_MORTE: Final = "adresse_morte"
GENRES: Final[frozenset[str]] = frozenset({CLAUSE_ABSENTE, ADRESSE_ABSENTE, ADRESSE_MORTE})


def adresses_manquantes(texte: str) -> tuple[str, ...]:
    """The addresses from :data:`ADRESSES_QUI_PRIMENT` that ``texte`` does not cite, in frozen order.

 **THE ORDER OF :data:`ADRESSES_QUI_PRIMENT`, NOT `sorted()`**: a refusal must read in the
 same order as the constant it is faulting, otherwise the reader hunts for the gap between two
 lists that only differ by their sort order."""
    return tuple(adresse for adresse in ADRESSES_QUI_PRIMENT if adresse not in texte)


def verdicts(texte: str, *, adresses_vivantes: frozenset[str]) -> tuple[tuple[str, str], ...]:
    """The gaps in a mandate, as ``(kind, detail)``.

 ``adresses_vivantes`` is **injected**: it is the runtime edge that knows which paths exist on
 disk, and a judge that went looking for them itself could find NONE and return a green —
 the green that would mean "no dead address", the exact wrong sentence.

 **THE ORDER: the clause first, the addresses after.** A mandate with no clause does not have
 an address problem: it has no precedence at all, and naming its missing addresses first would
 go looking for a detail where the whole thing is missing."""
    trouves: list[tuple[str, str]] = []
    if CLAUSE not in texte:
        trouves.append((CLAUSE_ABSENTE, "the mandate does not carry the precedence clause"))
    trouves += [(ADRESSE_ABSENTE, a) for a in adresses_manquantes(texte)]
    trouves += [(ADRESSE_MORTE, a) for a in ADRESSES_QUI_PRIMENT if a not in adresses_vivantes]
    return tuple(trouves)


def resume(trouves: tuple[tuple[str, str], ...], *, adresses: int) -> str:
    """The published text — it ALWAYS carries the number of addresses verified: "precedence
    carried" on zero addresses would read exactly like "precedence carried" on five."""
    entete = f"precedence: {adresses} address(es) that take priority, verified"
    if not trouves:
        return f"\U00002705 {entete} — the mandate carries the clause, and every address exists.\n"
    lignes = [f"\U000026D4 {entete} — {len(trouves)} gap(s):"]
    for genre, detail in trouves:
        if genre == CLAUSE_ABSENTE:
            lignes.append(
                "   · CLAUSE ABSENT — a mandate with no precedence leaves its recipient with no "
                "recourse against its principal's error. Add `precedence.CLAUSE`"
            )
        elif genre == ADRESSE_ABSENTE:
            lignes.append(
                f"   · ADDRESS NOT CITED — {detail}: the mandate does not say it takes priority"
            )
        else:
            lignes.append(
                f"   · DEAD ADDRESS — {detail} does not exist on disk. A pointer to nothing "
                "is worse than no pointer: it looks like a pointer"
            )
    return "\n".join(lignes) + "\n"
