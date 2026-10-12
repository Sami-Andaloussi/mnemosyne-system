"""The BANC plan generator — so that two measurements talk about the same population.

**THIS FILE EXISTS BECAUSE TWO CHAT SESSIONS MEASURED "THE SAME" FIXTURE AND GOT 25s VERSUS
0.049s.** `B6`'s clause said *"the fixture of 10,000 items × 100 waves"* — **numbers, with no
command that produces them**. So each one generated its own shape, under a single name.
*Two figures about two populations don't contradict each other: they don't speak to each other.*

The fix is not a more precise number in the clause, it's a **shared generator**: a cost
measurement is only worth something if the other session can **replay the exact same** population.

**And it ASSERTS its own size before returning anything.** Measured three times in the same
session: a banc whose generator produces a population the reader refuses runs **fast**, a diff on
zero elements is **empty**, a gate on zero items is **green** — and the only signal is an ABSURD
count, never a red. So the contract lives in the signature: it returns the text **and** the number
of items it must contain, and the caller cannot read one without the other.
"""

from __future__ import annotations

from typing import Final, NamedTuple

#: The six required fields, written in the canonical form — marker at the start of the line. It's
#: the only form the format guarantees against theft by neighboring prose, and a banc that wrote
#: its items any other way would be measuring the citation reader rather than the scheduler.
_CHAMPS: Final = (
    "  *Produit* : p",
    "  *Fini quand* : f",
    "  *Prérequis* : AUCUN",
    "  *À lire* : a",
    "  *Taille* : t",
)


class Banc(NamedTuple):
    """The plan text AND the size its reading MUST return.

    The two travel together because a banc that returns text alone lets the caller publish a
    timing on a population it never verified.
    """

    texte: str
    items: int
    vagues: int

    def verifie(self, lus: int) -> None:
        """Refuse — loudly — if the reading doesn't return the announced population."""
        if lus != self.items:
            raise AssertionError(
                f"the banc announces {self.items} items and the reader returns {lus}: "
                "the population is degenerate, no number drawn from it means anything"
            )


def plan_de_banc(
    vagues: int,
    largeur: int,
    *,
    arcs: int = 1,
    faits: int = 0,
    en_cours: int = 0,
    aretes_refusees: int = 0,
    taux_dep: float | None = None,
) -> Banc:
    """A plan of ``vagues`` waves of ``largeur`` items, each wave depending ENTIRELY on the previous one.

    It's the shape that makes the scheduler actually work: the number of edges grows as
    ``vagues × largeur²``, where a chain (``largeur = 1``) only measures depth.
    Publishing **both axes** is the minimum for a measurement gap to be interpretable.

    The identifiers are of the form ``Z<n>`` — no underscore: the identifier grammar refuses
    ``Z0_0``, and a first version of the banc ran on **0 items** with no red to say so.

    **``arcs`` / ``faits`` / ``en_cours`` — added 2026-08-15, and the BOUND is narrow.**
    A clause required comparing a REAL plan's map to that of a 10,000-step fixture.
    Measured: **6.5%** with one fixture, **22.6%** with this one — *same code, same clause, two
    fixtures, two verdicts.* The cause wasn't the map: it's that the real thing carries **3 arcs,
    18 done, 7 in-progress** while the fixture carried **1 arc and no state at all**. *It had the
    SIZE of the real thing, not its SHAPE.*

    **Only the three gaps the measurement NAMED were added.** A fixture that gains useless
    parameters becomes, once again, a population nobody knows how to replay — and the whole point
    of a banc is precisely that two measurements talk about the SAME population.

    ``arcs`` distributes items across that many identifier prefixes (``Za1``, ``Zb1``, …): that's
    what the plan reader calls an arc. ``faits`` and ``en_cours`` are ITEM COUNTS, taken in order —
    an item can't be both. ``aretes_refusees`` makes that many items point at a NONEXISTENT
    dependency: the scheduler refuses it and the map announces it.

    **``taux_dep`` — added 2026-08-15 when the clause gained a DOMAIN.** The clause didn't say
    *which* 10,000-step fixture: the free parameter was **the control population itself**, and two
    honest readers got **6.5%** and **22.6%** on the same code.
    So the arbitration wrote a **domain drawn from the real thing** — ``≥ 4 arcs``, dependencies in
    ``[23%, 86%]``, all three statuses — and the verdict must hold **everywhere inside it**.
    *It favors no one: the orchestrator's fixture had 1 arc, mine had 14% dependencies. Neither
    one qualified.* ``taux_dep`` is the share of eligible items that receive a dependency —
    ``None`` keeps the original behavior (every wave depends on the previous one).

    **THE THIRD ONE WAS THE DECISIVE ONE, and I hadn't seen it.** The measurement named three
    gaps (arcs · states · **refused edges**); I had implemented two, and the gap stayed at
    **22.6%** — identical to the poor fixture. *Implementing two causes out of three does not
    shrink the gap by two-thirds: the missing cause can carry the whole thing.*
    """
    if vagues < 1 or largeur < 1:
        raise ValueError(f"vagues and largeur must be at least 1 (received {vagues}, {largeur})")
    if arcs < 1:
        raise ValueError(f"arcs must be at least 1 (received {arcs})")
    if aretes_refusees < 0 or aretes_refusees > vagues * largeur:
        raise ValueError(
            f"aretes_refusees ({aretes_refusees}) exceeds the banc's {vagues * largeur} items"
        )
    total = vagues * largeur
    if faits < 0 or en_cours < 0 or faits + en_cours > total:
        raise ValueError(
            f"faits + en_cours ({faits} + {en_cours}) exceeds the banc's {total} items — "
            "an item can't be both done AND in-progress, and an impossible count isn't truncated"
        )
    # States are assigned BEFORE the loop, by rank, so the same call always returns the
    # same plan: a banc whose shape depends on iteration order isn't a banc.
    if taux_dep is not None:
        if not 0.0 <= taux_dep <= 1.0:
            raise ValueError(f"taux_dep is a SHARE, between 0 and 1 (received {taux_dep})")
        # **THE RATE APPLIES TO THE TOTAL, NOT TO THE ELIGIBLE ITEMS — and my 1st version
        # returned HALF of what was asked** (23% asked -> 12% obtained), because only the 2nd wave
        # and later ones can depend on anything. A generator that silently under-delivers
        # fabricates an out-of-domain population that nobody verifies: *silent loss lives where
        # the shape changes*. It now REFUSES, and its message names the fix.
        vises = round(taux_dep * total)
        if vises > total - largeur:
            raise ValueError(
                f"taux_dep={taux_dep:.0%} asks for {vises} dependent items out of {total}, but only "
                f"{total - largeur} can be (the 1st wave depends on nothing). "
                f"Increase `vagues`: {vagues} wave(s) cap out at "
                f"{(total - largeur) / total:.0%}"
            )
    etats = ["\U00002705"] * faits + ["\U0001F504"] * en_cours + ["\U00002B1C"] * (total - faits - en_cours)
    lettres = "abcdefghijklmnopqrstuvwxyz"
    lignes = ["# PLAN — banc", "", "> **Cap** : measure, not convince", ""]
    numero = 0
    precedente: tuple[str, ...] = ()
    for _ in range(vagues):
        courante: list[str] = []
        for _ in range(largeur):
            numero += 1
            # The prefix carries the arc: `Za1`, `Zb1`, … — that's what the plan reader reads
            # as an arc, and the map aggregates over it.
            ident = f"Z{lettres[(numero - 1) % arcs]}{numero}"
            courante.append(ident)
            # The refused edges target an identifier that does NOT exist: that's what
            # `plan_ordre` refuses and what the map publishes under "ORDRE AMPUTÉ". They're taken
            # from the LAST ranks so as not to decapitate the queue — a banc whose head is refused
            # no longer measures the scheduler, it measures the refusal.
            if numero > total - aretes_refusees:
                depend = f"ZINEXISTANT{numero}"
            elif not precedente:
                depend = "AUCUNE"
            elif taux_dep is None:
                depend = " · ".join(precedente)
            else:
                # The rate is computed over the ABSOLUTE rank, not per wave: a per-wave draw
                # would produce a global rate that depends on the shape, and the domain is stated
                # over the GLOBAL rate.
                # Deterministic (a rank, not a random draw) — a banc that changes between two
                # calls no longer lets two measurements talk about the same population.
                depend = (
                    " · ".join(precedente)
                    if numero - largeur <= round(taux_dep * total)
                    else "AUCUNE"
                )
            lignes.append(f"- **{ident}** {etats[numero - 1]} a banc item.")
            lignes.append(f"  *Dépend de* : {depend}")
            lignes.extend(_CHAMPS)
        precedente = tuple(courante)
    return Banc("\n".join(lignes) + "\n", vagues * largeur, vagues)
