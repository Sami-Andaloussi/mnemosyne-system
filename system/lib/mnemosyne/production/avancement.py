"""``P3`` — THE PROGRESS LADLE, AND WHAT IT ADMITS BY PUBLISHING ITSELF.

The operator asks for this progress ladle at the end of every work arc. The plain-COUNT percentage
is a polite liar: it gives the same weight to *"1 measurement"* and to *"~27 batches"*, so it climbs
fast when small items close and stalls when a big one is being worked. The ladle WEIGHTED by the
size each item declares fixes that — **provided the weights actually exist**.

**THE DEFECT THIS MODULE EXISTS TO MAKE IMPOSSIBLE: A WEIGHTED LADLE WHOSE WEIGHTS ARE MISSING
DEGRADES INTO A PLAIN COUNT *WITHOUT SAYING SO*.** Every item without a weight takes the median; if
*every* item is without a weight, they all take the same value and the weighted average **equals
exactly** the plain-count percentage — two identical numbers, presented as two independent
measurements that confirm each other. This is the most expensive shape of false green: *two absences
of measurement compare equal*. So :func:`rendre` publishes **`sans_poids=N/N` in the same sentence**
as the figure, and :attr:`Louche.degradee` states in plain words when the weighting no longer has any
arithmetic effect. **The figure's limitation travels WITH the figure.**

**MEASURED ON THIS REPOSITORY, BY THE JUDGE'S OWN ACCESSOR, AND RE-TAKEN AFTER EVERY READER FIX**
(across this repository's own planning documents, via ``plan_format.PlanItem.field("taille")``):
**86 items ALL declare a `*Size*`**, and only **6** yield a readable weight — **five equal 1, one
equals 27**, median **1**. *A corpus that declares its size 100% of the time and its magnitude 7% of
the time is exactly the corpus where a silent weighted ladle lies best.*
**These two numbers were WRONG here while this was being written** ("16" / "70"): they dated from
an earlier reader, from before ``+`` became a separator and plurals got folded. *A number copied from
a measurement taken before the fix is a number you DECIDED, not the one the command returned.*

**THIS FILE IS NOT A GATE AND MUST NEVER BECOME ONE.** It publishes; it refuses no commit, no
item, no plan. A ladle that refused would push people to fabricate `*Size*` fields just to silence
an alarm — and an invented size is worse than a missing one, because it carries weight.
The ONLY non-null output it knows is an instrument failure (:class:`SansPopulation`).

**THE POPULATION IS INJECTED, NEVER FETCHED**: no function here reads a file, or touches
``os.environ`` or the disk. The boundary is :mod:`mnemosyne.runtime.avancement_run`.

Siblings: ``plan_format`` (the field reader) · ``plan_derive`` (the frozen counter).
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from statistics import median
from typing import Final

#: Statuses that count as DONE. A named, injectable SET, never a literal buried inline: the
#: question "does `clos` count as done?" is a judgment call, and a judgment call hidden inside a
#: bare `==` cannot be contested.
FAITS_PAR_DEFAUT: Final = frozenset({"fait"})

#: Statuses REMOVED from the population — neither done nor remaining. `clos` = "will not be done,
#: and that is decided": counting it in the denominator would make progress drop with every item
#: given up on.
#: **Removed, but NEVER silent**: :attr:`Louche.hors_population` counts them and :func:`rendre`
#: publishes them — *an excluded population is a population that was NEVER JUDGED, not a population
#: at rest.*
HORS_POPULATION_PAR_DEFAUT: Final = frozenset({"clos"})

#: What separates two UNITS declared inside a `*Size*`. Drawn from this repository's real values
#: ("1 field · 1 clause · 1 delegated audit", "1 function + 1 call site + 3 witnesses"), never
#: guessed. The comma is NOT one of these: "1 pass, bounded" is ONE unit plus an aside.
_SEPARATEURS: Final = re.compile(r"[·;+]")

#: A segment that OPENS on a number followed by a unit word. `~` and the French `environ` ("about")
#: are accepted — an author who writes "~27 batches" is still declaring 27; denying it on the
#: grounds that they hedged would demand a precision the field never promises. Thin and
#: non-breaking spaces are accepted inside the number ("10 000 items") because that is how the
#: corpus writes them.
_TETE_DE_SEGMENT: Final = re.compile(
    r"^\s*(?:~|environ\s+)?(\d+(?:[   ]\d{3})*)\s+([A-Za-zÀ-ÿ'’-]+)"
)


class SansPopulation(RuntimeError):
    """No item was submitted to the judge — **an instrument failure, never a 0% progress reading**.

    Returning ``0%`` over zero items would be the worst green in the corpus: it reads as "the
    work hasn't started" when it actually means "I couldn't read anything." The two call for
    opposite responses (get to work · fix the reader), so they must never share a return value.
    """


def poids_declare(taille: str) -> int | None:
    """The weight this ``*Size*`` declares — ``None`` when it declares **no readable weight at all**.

    **WHAT THIS FUNCTION REFUSES TO DO, AND THAT IS ITS WHOLE POINT: MANUFACTURE A MAGNITUDE.**
    Three rules, each paid for by a REAL counter-example from this repository:

    1. **Every segment must open on a number.** ``5 commands · a few minutes · nothing was
       rewritten`` used to yield ``5`` on a first pass, because only the first segment carried a
       digit: the weight read **one third** of what the author had written and presented it as the
       whole. A mute segment withdraws the ENTIRE weight — it does not let itself be ignored.
    2. **All units must be the SAME one.** ``4 documents · ~400 lines`` would sum to 404, a number
       decided entirely by "lines" — *a rate measured on the wrong population kills a good design*.
       Mixed units do not add up: they yield ``None``.
    3. **Nothing is guessed.** No "one file is worth three lines" table, no fallback to the segment
       count: counting segments would give **3** to ``1 field · 1 clause · 1 delegated audit`` and
       **2** to ``95 files · ~10 batches``, i.e. exactly the reverse of the true order.

    The cost is accepted: on this repository, **80 items out of 86** yield ``None``. That is a
    measurement of the corpus, not a weakness of the reader — and it is exactly what :func:`rendre`
    publishes.
    """
    segments = [morceau for morceau in _SEPARATEURS.split(taille) if morceau.strip()]
    if not segments:
        return None
    lus: list[tuple[int, str]] = []
    for segment in segments:
        trouve = _TETE_DE_SEGMENT.match(segment)
        if trouve is None:
            return None
        brut = trouve.group(1)
        for espace in (" ", " ", " "):
            brut = brut.replace(espace, "")
        lus.append((int(brut), _unite_repliee(trouve.group(2))))
    if len({unite for _, unite in lus}) != 1:
        return None
    return sum(nombre for nombre, _ in lus)


def _unite_repliee(mot: str) -> str:
    """The unit word, lowercased, with **its plural folded away** — ``functions`` and ``function``
    are ONE.

    **Found by a red witness, not guessed**: ``1 function + 2 functions`` used to yield ``None``
    because two spellings of the SAME unit counted as two different units. Refusing a weight over a
    plural marker judges the author's grammar, not their item's magnitude.

    **The residue, named rather than silenced**: a word whose singular already ends in ``s``
    (French ``cours``, ``processus``) folds onto a form that does not exist. This has no effect —
    both segments fold the same way — and the only possible drift would be that a ``1 cour · 2
    cours``-shaped typo would pass as homogeneous. So the fold can only ever MANUFACTURE a weight on
    an absurd declaration, **never produce a `None` on a sound one**: the error sits on the safe
    side.
    """
    minuscule = mot.lower()
    return minuscule[:-1] if len(minuscule) > 2 and minuscule.endswith("s") else minuscule


@dataclass(frozen=True, slots=True)
class Item:
    """A plan item as the judge receives it — three fields, and nothing else.

    Deliberately spare: no title, no prose, no source file. What does not enter here cannot leak
    into a ladle the operator pastes into a conversation.

    ``taille`` is the VERBATIM content of the ``*Size*`` field, ``""`` when the item does not
    declare one. The judge does not distinguish "field absent" from "field empty" — neither carries
    any weight, and that is the only question it asks this field; NAMING the difference is the job
    of :attr:`~mnemosyne.production.plan_format.PlanItem.missing_fields`, which already does it.
    """

    ident: str
    statut: str
    taille: str = ""


@dataclass(frozen=True, slots=True)
class Louche:
    """The two percentages, **side by side**, and everything needed not to trust them too much.

    The two figures live in the SAME object on purpose: a caller cannot publish the weighted one
    without having the plain one at hand, nor either one without :attr:`sans_poids`.
    """

    #: Items judged — excluding :data:`HORS_POPULATION_PAR_DEFAUT`.
    total: int
    #: Judged items whose status is among the "done" statuses.
    faits: int
    #: Items removed from the population before any computation (status: closed). Published, never
    #: silenced.
    hors_population: int
    #: Judged items whose ``*Size*`` yields NO readable weight — they take the median.
    sans_poids: int
    #: The median of the weights ACTUALLY READ, served to the items without a weight. ``None`` when
    #: no weight at all was read: there is then no median to speak of, and the judge says so instead
    #: of inventing a ``1`` that would look like a measurement.
    mediane: float | None
    #: Share done, counting each item as 1 (0.0 → 1.0).
    part_par_compte: float
    #: Share done, weighted by the declared weight (0.0 → 1.0).
    part_ponderee: float

    @property
    def degradee(self) -> bool:
        """True when the weighting has **no arithmetic effect whatsoever** on the result.

        **THIS PREDICATE IS THE HEART OF THE ITEM.** It does not compare the two percentages —
        two figures can coincide by accident on a given population without the weighting being
        dead, and that would then be a false alarm. It judges the CAUSE: when no item carries its
        own weight, they all receive the same median, and the weighted average **is**, by
        construction, the plain average. The weighted ladle then adds **nothing** — and that is the
        sentence that must be published, not a percentage.
        """
        return self.total > 0 and self.sans_poids == self.total


def louche(
    items: Iterable[Item],
    *,
    faits: Iterable[str] = FAITS_PAR_DEFAUT,
    hors_population: Iterable[str] = HORS_POPULATION_PAR_DEFAUT,
) -> Louche:
    """The two shares, over an INJECTED population — raises :class:`SansPopulation` if it is empty.

    **`faits` and `hors_population` are parameters, and their default is a written-down judgment
    call** (see :data:`FAITS_PAR_DEFAUT` / :data:`HORS_POPULATION_PAR_DEFAUT`). A judge that buries
    its status vocabulary inside its own body forces you to read it before you can contest it.
    """
    faits_set = frozenset(faits)
    hors_set = frozenset(hors_population)
    tous = tuple(items)
    juges = tuple(item for item in tous if item.statut not in hors_set)
    if not juges:
        raise SansPopulation(
            f"no item to judge ({len(tous)} received, {len(tous) - len(juges)} out of population) — "
            "this is an instrument failure, not 0% progress"
        )

    poids = tuple(poids_declare(item.taille) for item in juges)
    lus = tuple(valeur for valeur in poids if valeur is not None)
    milieu = median(lus) if lus else None
    # The median serves items WITHOUT a weight; when there are none at all, every item weighs 1
    # — that is the plain count, and `degradee` is then TRUE, so the published sentence will say so.
    # Silently setting `1` here would be exactly the silent degradation this module exists to
    # prevent.
    defaut = milieu if milieu is not None else 1.0
    effectifs = tuple(defaut if valeur is None else float(valeur) for valeur in poids)

    masse = sum(effectifs)
    masse_faite = sum(
        poids_item for item, poids_item in zip(juges, effectifs) if item.statut in faits_set
    )
    nombre_faits = sum(1 for item in juges if item.statut in faits_set)
    return Louche(
        total=len(juges),
        faits=nombre_faits,
        hors_population=len(tous) - len(juges),
        sans_poids=sum(1 for valeur in poids if valeur is None),
        mediane=milieu,
        part_par_compte=nombre_faits / len(juges),
        # `masse` cannot be zero: every effective weight is at least the median of a weight that was
        # read, and a weight that was read is at least 1 (`_TETE_DE_SEGMENT` requires `\d+`, and
        # "0 files" — weight 0 — cannot be alone of its kind without another segment carrying a
        # number). The guard below is written anyway: a division by zero would return `nan`, which
        # formats as "nan %" and reads like a real figure.
        part_ponderee=(masse_faite / masse) if masse else 0.0,
    )


def _pourcent(part: float) -> str:
    return f"{part * 100:.1f} %".replace(".", ",")


def rendre(mesure: Louche, *, statuts_faits: Sequence[str] = ("fait",)) -> str:
    """The ladle IN WORDS — the two figures, then whatever bounds them, in the same block.

    **NO LINE HERE IS DECORATIVE.** The ``sans_poids=N/N`` admission sits in the same sentence as
    the weighted percentage because a reader copies **one number**, never a report: put in a
    separate paragraph, it would not travel with it.
    """
    lignes = [
        f"LADLE — {mesure.faits}/{mesure.total} items done "
        f"(statuses counted as done: {', '.join(statuts_faits)}).",
        f"  by plain count: {_pourcent(mesure.part_par_compte)}",
        f"  weighted by declared size: {_pourcent(mesure.part_ponderee)}"
        f"   [without a readable weight: {mesure.sans_poids}/{mesure.total}]",
    ]
    if mesure.mediane is None:
        lignes.append(
            "\U000026D4 NO weight could be read: there is no median, every item weighs 1. "
            "The weighted figure above IS the plain count — it is not a second measurement."
        )
    elif mesure.degradee:
        lignes.append(
            f"\U000026D4 NO item carries its own weight: all of them receive the median ({mesure.mediane:g}), "
            "so the weighting has NO effect. The two figures above are the SAME one, "
            "shown twice — do not read them as two measurements confirming each other."
        )
    else:
        lignes.append(
            f"  median served to the {mesure.sans_poids} items without a weight: {mesure.mediane:g}"
        )
    if mesure.hors_population:
        lignes.append(
            f"  out of population (closed status): {mesure.hors_population} item(s) — "
            "neither done nor remaining, and removed from both denominators."
        )
    return "\n".join(lignes)
