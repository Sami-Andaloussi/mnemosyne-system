"""THE TWO DRIFT RATCHETS (the "plans" workstream · D1) — and they are read TOGETHER.

> *"This must be arranged so this drift NEVER happens again. What happened is that you got lost in
> the plan."* — the operator, 2026-08-05.

Two measurements, and **neither one is worth anything alone**:

* **(a) THE PRODUCT SHARE** — what fraction of the work goes to the PRODUCT rather than the tooling
 that serves to build it. It's the one that would have screamed on July 21st, and it didn't exist.
* **(b) THE IMMOBILE COUNTER** — the set of DONE steps that no longer moves. Another project paid for this:
 *"`faites=9` hadn't moved in eleven turns"*, and *"the set of `` was IDENTICAL after 299
 commits"*.

 **WHY TOGETHER: EACH ONE ALONE LIES.** Producing a lot on a single step leaves (a) green and (b)
red; closing out machinery steps does exactly the opposite. A plan that's really moving MUST move on
both — and it's the pair, never either one alone, that says "this is drifting."

## THREE CONSTRUCTION RULES, each paid for elsewhere in this repo

1. **NOTHING IS CALIBRATED ON THE ANSWER.** No date, no threshold: the sought-after turning point is
 the **largest drop** in the series, a property of the data. *A detector calibrated on the answer
 detects nothing* — that is D1's exit condition, word for word.
2. **WE FREEZE THE SET, NEVER THE COUNT.** (b) compares **sets of identifiers**, not their
 cardinality: *a count can be satisfied by a silent EXCHANGE* — one item closes, another reopens,
 and the number doesn't move even though the plan itself has moved.
3. **THE CLASSIFICATION IS INJECTED**, never written here. This module doesn't know what "the
 product" is: the predicate is handed to it. It's D2 that will make the PROJECT itself declare
 that boundary — and that project's version, which hardcoded it as prefixes, got its own lesson thrown
 back at it: *a guard that classifies by PREFIX judges the NAME of the path, not the SUBSTANCE of
 the file* (its `scripts/pre_commit.py` counted as product when it actually IS the tooling).

## This module is a PURE JUDGE

It talks to neither ``git`` nor the disk: the edge hands it the commits already read. *A judge that
goes fetching its own population can find it empty and return a green* — and here green would mean
"no drift," the exact false statement an absent ``git`` would produce on its own.

 **LEVEL 1 — it PUBLISHES, it refuses nothing.** What refuses is D3, and only D3.

Decisions: D1 · D2 (the product declared by the project) · inv. 2. Translated from French prose
(D117) for the public mirror.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from .obligation import hors_blocs


@dataclass(frozen=True, slots=True)
class Tour:
    """One commit, as the EDGE read it — this module reads none itself.

 ``faits`` is the set of ```` step identifiers **after** this commit. It's a SET, not a count,
 and that's half of rule 2.
 """

    sha: str
    date: str
    chemins: tuple[str, ...]
    #: **``None`` = UNKNOWN, ``frozenset()`` = MEASURED EMPTY — and the difference is everything.**
    #: Before 2026-08-15 the default was ``frozenset()``, so an edge that read NO done-item at all
    #: would return a population where nothing ever moves — and the page would publish *"N commits
    #: without a SINGLE identifier changing,"* i.e. **that other project's exact failure, starting from ZERO
    #: data**. *A value that serves TWO masters cannot be normalized once.*
    faits: frozenset[str] | None = None
    #: **WRITTEN LINES, ALIGNED WITH ``chemins`` — added 2026-08-15 by amendment.**
    #: The clause required reproducing a figure the project had published **in LINES** ("share of
    #: WRITTEN LINES going to that project's product | 85.8%") with a unit that counts FILES. And the
    #: paradox named the fault: the proxy reproduced it to **0.2 points** where the true unit
    #: diverges by **3-4 points**. *A proxy that beats the true unit is not luck: it's the signature
    #: of a unit chosen BECAUSE it reproduced.* The reference must never derive from what it verifies.
    #: **Empty = UNKNOWN, never zero.** A tour with no line data isn't a tour at zero lines, and
    #: :data:`PAR_LIGNE` REFUSES rather than return an invented count.
    lignes: tuple[int, ...] = ()

    @classmethod
    def depuis_paires(
        cls,
        sha: str,
        date: str,
        paires: "Sequence[tuple[str, int]]",
        faits: frozenset[str] = frozenset(),
    ) -> "Tour":
        """Build a tour from ``(path, lines)`` pairs — **the only safe path**.

 **THE PERMUTATION IS UNDETECTABLE FROM THE DATA, and I reproduced it**: two tours with the
 same paths, one of which has its lines permuted, return ``(90, 100)`` and ``(10, 100)`` —
 **no refusal, two plausible counts**. :data:`PAR_LIGNE`'s guard compares LENGTHS; it catches
 truncation, never the swap. *No after-the-fact check can tell a correct alignment from a
 wrong one when both have the same shape.*

 **So we don't verify: we make the error UNCONSTRUCTABLE.** The two tuples are born from a
 single source, in a single gesture. An edge that reads ``git log --numstat`` has exactly
 this shape — one line = one path AND its count.

 **ADMISSION: the direct constructor stays open**, and nothing forces going through here.
 It's a SAFE convenience, not a barrier — a frozen dataclass can't forbid its own ``__init__``.
 *What CAN be done is making the safe path the shortest one.*"""
        return cls(
            sha=sha,
            date=date,
            chemins=tuple(chemin for chemin, _ in paires),
            faits=faits,
            lignes=tuple(compte for _, compte in paires),
        )


@dataclass(frozen=True, slots=True)
class Jour:
    """One day's product share: what makes it up, never a bare ratio."""

    date: str
    produit: int
    total: int

    @property
    def part(self) -> float:
        """The fraction going to product. An EMPTY day returns 0.0 and flags itself via ``total == 0``."""
        return self.produit / self.total if self.total else 0.0


@dataclass(frozen=True, slots=True)
class Chute:
    """The largest drop in the series — DERIVED, never a threshold."""

    depuis: str
    vers: str
    avant: float
    apres: float

    @property
    def ampleur(self) -> float:
        return self.avant - self.apres


@dataclass(frozen=True, slots=True)
class Immobilite:
    """The longest run of commits where the SET of done items hasn't moved."""

    depuis: str
    jusqua: str
    commits: int
    ensemble: frozenset[str]

    # (A property `echange_masque` used to live here, with a docstring claiming it was "raised" by
    # `immobilite`. That was STRUCTURALLY IMPOSSIBLE — a `property` cannot be written on a
    # frozen+slots dataclass — and nothing called it: an isolated audit measured it, one single
    # occurrence in the whole repo, its own definition. The swaps are returned by :func:`immobilite`
    # in its second member, where they actually exist. *A dead property whose docstring describes a
    # mechanism that doesn't exist is worse than an absence: it gets cited.*)


@dataclass(frozen=True, slots=True)
class Derive:
    """THE READING OF BOTH, and the only object the edge must print."""

    jours: tuple[Jour, ...]
    chute: Chute | None
    immobilite: Immobilite | None
    echanges: tuple[str, ...]
    #: **THE TWO-UNIT SENTENCE, AND IT TRAVELS ALL THE WAY TO THE PAGE.** The amended clause says
    #: *"PUBLISH its share in BOTH units … with their GAP named"* — and my first delivery was called
    #: **by nothing**: `ecart_des_unites` existed only for its own witnesses.
    #: *That's the barrier that nothing calls, committed one hour after writing it down.* The clause's
    #: verb is **publish**: a correct function that nothing prints doesn't publish anything.
    unites: str = ""
    #: **THE SERIES' OWN UNIT, and its absence made the page publish THREE figures for ONE
    #: question.** Measured on a real page: the header said **100%**, the units line said
    #: **50% / 50%**, and nothing said the series was counted in COMMITS while the other two were in
    #: lines and files. *A reader cannot know which one answers their question* — and the first
    #: figure, the biggest one, is the one they'll remember.
    #: It's the same fault as "a correct figure in the wrong unit reads as its opposite," one
    #: level up: here all three are correct, and it's their SILENT PROXIMITY that lies.
    #: **False when NO tour carries done-items — and that is NOT "nothing moved."**
    #: *Two absences of measurement compare EQUAL*: without this flag the page wrote the same
    #: sentence for "the window is empty" and for "the edge read no done-item at all."
    faits_connus: bool = False
    unite_serie: str = "COMMITS"

    @property
    def part_globale(self) -> float:
        produit = sum(j.produit for j in self.jours)
        total = sum(j.total for j in self.jours)
        return produit / total if total else 0.0


# --------------------------------------------------------------------------------------------
# D2 — "THE PRODUCT" IS DECLARED BY THE PROJECT, NEVER HARDCODED. The PURE reader of a `produit:`
# declaration — the edge (`runtime/derive_run.py`) finds the file on disk, this function only reads
# the TEXT. Same doctrine, same pattern as `carte.lire_peremption`: a population JUDGED BY THE
# PROJECT lives BESIDE its plan door, never inside the code that measures it.
# --------------------------------------------------------------------------------------------

#: One pattern per line: ``- <pattern>``, the pattern optionally between backticks — same tolerance
#: as :data:`mnemosyne.production.carte._PEREMPTION`. No second member: a path pattern, unlike an
#: expiry, carries no reason.
_PRODUIT = re.compile(r"^[ \t]*-[ \t]+`?(\S[^\n`]*?)`?[ \t]*$", re.MULTILINE)


def lire_produit(texte: str) -> tuple[str, ...]:
    """The path patterns a ``produit:`` declaration carries. PURE, no file read here.

 **Returns an EMPTY tuple if the text declares NO pattern at all — and that is NOT the same
 thing as "no file exists."** This function never sees absence: it's up to the EDGE to
 distinguish "file absent" (nothing was declared, the measurement switches off) from "file
 present, zero patterns" (the project explicitly declares that nothing is product — a valid,
 if unusual, answer). *Two absences of measurement must never compare equal* — the same rule as
 :class:`Tour`.``faits`` (``None`` vs ``frozenset()``), applied here to the file-absent vs
 file-empty boundary.

 Closed blocks are stripped BEFORE reading (the same trap :func:`~mnemosyne.production.carte.
 lire_peremption` already paid for: a pedagogical example inside documentation must not become
 a declaration)."""
    return tuple(m.group(1).strip() for m in _PRODUIT.finditer(hors_blocs(texte)))


#: The default unit: **the COMMIT**. A tour counts toward product as soon as **at least one** of
#: its paths does — the question is *"did this tour move the product forward?"* A commit with no
#: path at all (an empty merge) counts toward the total and not toward product.
def PAR_COMMIT(tour: "Tour", est_produit: Callable[[str], bool]) -> tuple[int, int]:
    return (1 if any(est_produit(c) for c in tour.chemins) else 0, 1)


#: The PLAN's unit: **the FILE touched** — the proxy for the lines that the published series uses
#: (the project's own published figure: *"share of WRITTEN LINES going to product"*).
def PAR_FICHIER(tour: "Tour", est_produit: Callable[[str], bool]) -> tuple[int, int]:
    return (sum(1 for c in tour.chemins if est_produit(c)), len(tour.chemins))


def PAR_LIGNE(tour: "Tour", est_produit: Callable[[str], bool]) -> tuple[int, int]:
    """The unit of the PUBLISHED figure: **lines written**, not files touched.

 **IT REFUSES when the data is missing**, instead of returning `(0, 0)`. A tour with no lines
 would otherwise be a day at `total == 0`, which :func:`part_produit` DROPS — and the series
 would lose days **silently**, on the very surface where the clause demands a figure. *Silent
 loss lives where the shape changes*, and here it would change between a measured tour and one
 that isn't. The edge that builds `Tour`s fills `lignes`; one that can't must learn about it
 through an exception, never through a lower figure.

 ``lignes`` is **aligned with ``chemins``**: same length, same order. A misalignment would
 attribute one file's lines to another, and the count would stay plausible.
 """
    if len(tour.lignes) != len(tour.chemins):
        raise ValueError(
            f"tour {tour.sha}: {len(tour.lignes)} line count(s) for "
            f"{len(tour.chemins)} path(s) — the PAR_LIGNE unit cannot measure this tour, "
            "and an invented zero would be worse than a refusal"
        )
    produit = sum(n for c, n in zip(tour.chemins, tour.lignes, strict=True) if est_produit(c))
    return produit, sum(tour.lignes)


def part_produit(
    tours: Sequence[Tour],
    est_produit: Callable[[str], bool],
    *,
    unite: Callable[["Tour", Callable[[str], bool]], tuple[int, int]] = PAR_COMMIT,
) -> tuple[Jour, ...]:
    """(a) — the share of work going to PRODUCT, day by day, in order.

 **THE UNIT IS INJECTED, like the classification — and this is a fix to the condition, not to
 the code.** Two honest readers found TWO different turning points on the same history: one
 counted **files touched** (`2026-07-20 → 2026-07-21`), the other **commits**
 (`2026-07-15 → 2026-07-20`). **Neither one was wrong**: the condition didn't say which unit to
 measure in. *A condition that doesn't fix its unit isn't falsifiable — it's only verifiable by
 whoever chose the unit.*

 The series the plan publishes is **in written lines**; :data:`PAR_FICHIER` is its proxy, and
 it's the one that reproduces the 85.8% figure from July 20th. :data:`PAR_COMMIT` stays the
 default: it answers *"how many TOURS moved the product forward,"* another, equally legitimate
 question.
 """
    par_jour: dict[str, list[int]] = {}
    for tour in tours:
        produit, total = unite(tour, est_produit)
        compte = par_jour.setdefault(tour.date, [0, 0])
        compte[0] += produit
        compte[1] += total
    return tuple(
        Jour(date=date, produit=p, total=t) for date, (p, t) in sorted(par_jour.items())
    )


def plus_grande_chute(jours: Sequence[Jour]) -> Chute | None:
    """The largest drop from one day to the next — **derived from the data, never thresholded**.

 This is the clause that makes D1 falsifiable: the condition requires finding a turning point
 *"without being handed one."* A threshold ("under 30%"), a date, or a chosen window would be
 three ways of handing it one. Here we return the maximum of a series: if the turning point
 exists, it comes out; if it doesn't, the largest drop is small and says so.

 **THE ``j.total`` FILTER IS ALIVE, AND I HAD DECLARED IT DEAD.** This docstring long claimed
 *"no emitted Jour ever has total == 0,"* on the strength of an isolated audit whose sabotage
 survived. That was true — **back when this module had only ONE unit**. Under :data:`PAR_FICHIER`,
 a commit that touches **no** file (a merge, an empty commit) returns ``total == 0``, and without
 this filter the series would show **90% → 0% → 90%**: a collapse invented by a division by
 nothing.

 *A borrowed verdict expires in silence* — and it's **my own work** that aged it out, by
 adding the units that make the guard reachable. An admission of death doesn't get copied from
 one version to the next: it gets **re-measured** every time the population changes.
 """
    pleins = [j for j in jours if j.total]
    if len(pleins) < 2:
        return None
    pire = max(
        (Chute(a.date, b.date, a.part, b.part) for a, b in zip(pleins, pleins[1:], strict=False)),
        key=lambda c: c.ampleur,
        default=None,
    )
    return pire if pire and pire.ampleur > 0 else None


def immobilite(tours: Sequence[Tour]) -> tuple[Immobilite | None, tuple[str, ...]]:
    """(b) — the longest run where the SET of done items hasn't moved, and the masked SWAPS.

    Returns ``(the longest immobility, the shas where a SWAP happened)``. A swap is a commit where
    the set changed **without its cardinality changing**: exactly what a counter would have missed.
    *A count can be satisfied by a silent swap.*
    """
    if not tours or all(t.faits is None for t in tours):
        return None, ()
    echanges: list[str] = []
    meilleure: Immobilite | None = None
    debut = 0
    for i in range(1, len(tours) + 1):
        fini = i == len(tours)
        change = not fini and tours[i].faits != tours[i - 1].faits
        connus = not fini and tours[i].faits is not None and tours[i - 1].faits is not None
        if change and connus and len(tours[i].faits) == len(tours[i - 1].faits):  # type: ignore[arg-type]
            echanges.append(tours[i].sha)
        if change or fini:
            longueur = i - debut
            if meilleure is None or longueur > meilleure.commits:
                meilleure = Immobilite(
                    depuis=tours[debut].sha,
                    jusqua=tours[i - 1].sha,
                    commits=longueur,
                    ensemble=tours[debut].faits or frozenset(),
                )
            debut = i
    return meilleure, tuple(echanges)


def ecart_des_unites(
    tours: "Sequence[Tour]", est_produit: Callable[[str], bool]
) -> tuple[float | None, float | None, str]:
    """The global share in BOTH units, and their **named** GAP.

 **THIS IS THE 2026-08-15 AMENDMENT, AND IT ADDS A REQUIREMENT.** The clause required
 reproducing a figure published **in LINES** with a unit that counts **FILES**. Keeping the
 proxy made the item pass; the orchestrator didn't do that — *an amendment that turns the item
 it amends green is a permission, not a decision.*

 **THE PARADOX NAMED THE FAULT**: the proxy reproduced the published figure to **0.2 points**
 where the TRUE unit diverges by **3 to 4 points**. *A proxy that beats the true unit is not
 luck: it's the signature of a unit chosen BECAUSE it reproduced.* The reference must never
 derive from what it verifies.

 So we no longer CHOOSE: **we publish both and NAME the gap**. Returns
 ``(share_lines, share_files, sentence)`` — ``share_lines`` is ``None`` when the tours don't
 carry the data, and the sentence SAYS so: *"not measurable"* is not *"no gap."*"""
    fichiers = part_produit(tours, est_produit, unite=PAR_FICHIER)
    p_fichiers = (
        sum(j.produit for j in fichiers) / sum(j.total for j in fichiers)
        if sum(j.total for j in fichiers)
        else None
    )
    # **THE REFUSAL WAS PER TOUR, THE LOSS WAS PER BATCH — measured: ONE tour without lines out
    # of 100 threw away the other 99.** `PAR_LIGNE` is right to refuse a tour it cannot measure (an
    # invented zero would be worse), but letting that refusal bubble all the way up here turned a
    # PUNCTUAL gap into a TOTAL absence. *A per-item guarantee that raises kills the batch* — the
    # same class this repo has already paid for, here in the sense that it destroys an almost
    # complete measurement.
    # We measure what's measurable AND we NAME what isn't. A share over 99 tours is not a share
    # over 100: the count of excluded tours travels with it, or the figure lies by omission —
    # *an excluded population is a population NOT JUDGED, not a population at rest.*
    mesurables = [t for t in tours if len(t.lignes) == len(t.chemins)]
    ecartes = len(tours) - len(mesurables)
    if not mesurables:
        return None, p_fichiers, (
            f"share in LINES: NOT MEASURABLE — none of the {len(tours)} tours carries written "
            "lines. \"not measurable\" and \"no gap\" don't read the same"
        )
    lignes_ = part_produit(mesurables, est_produit, unite=PAR_LIGNE)
    p_lignes = (
        sum(j.produit for j in lignes_) / sum(j.total for j in lignes_)
        if sum(j.total for j in lignes_)
        else None
    )
    if p_lignes is None or p_fichiers is None:
        return p_lignes, p_fichiers, "one of the two units has nothing to measure over this window"
    # **THE GAP WAS SUBTRACTING TWO DIFFERENT POPULATIONS.** `p_fichiers` covered the 100
    # tours, `p_lignes` the 99 measurable ones: their difference mixed the gap BETWEEN UNITS with
    # the gap BETWEEN POPULATIONS. Measured on the real window: **16.8 points fabricated** by this
    # one mix-up. And the caveat below, which DID name the population difference, prevented
    # nothing — *naming a hole doesn't plug it.*
    # The GAP is always taken over the COMMON population. The share in FILES over the WHOLE
    # window stays published — that's a correct fact — but it no longer serves as a term in the
    # subtraction. *"Before" and "after" must be THE SAME measurement.*
    f_communs = part_produit(mesurables, est_produit, unite=PAR_FICHIER)
    p_f_communs = (
        sum(j.produit for j in f_communs) / sum(j.total for j in f_communs)
        if sum(j.total for j in f_communs)
        else None
    )
    if p_f_communs is None:
        return p_lignes, p_fichiers, (
            f"share in LINES {p_lignes:.1%} · in FILES {p_fichiers:.1%} · GAP NOT COMPARABLE: "
            f"the {len(mesurables)} tours carrying lines count no file at all"
        )
    reserve = (
        f" \U000026A0\U0000FE0F GAP taken over the COMMON population ({len(mesurables)}/{len(tours)} tours; "
        f"{ecartes} without written lines) — in FILES it is {p_f_communs:.1%} versus "
        f"{p_fichiers:.1%} over the whole window"
        if ecartes
        else ""
    )
    return p_lignes, p_fichiers, (
        f"share in LINES {p_lignes:.1%} · in FILES {p_fichiers:.1%} · "
        # IN POINTS, NOT AS A FRACTION: `abs(0.90 - 0.50)` is 0.4 and used to print
        # "GAP 0.4 point" for a gap of FORTY points. A correct figure in the wrong unit reads as
        # a small gap — exactly the opposite of the fact.
        f"GAP {abs(p_lignes - p_f_communs) * 100:.1f} point(s){reserve}"
    )


def lire(
    tours: Sequence[Tour],
    est_produit: Callable[[str], bool],
    *,
    unite: Callable[["Tour", Callable[[str], bool]], tuple[int, int]] = PAR_COMMIT,
) -> Derive:
    """BOTH TOGETHER — the one reading, because neither is worth anything alone."""
    jours = part_produit(tours, est_produit, unite=unite)
    immo, echanges = immobilite(tours)
    return Derive(
        jours=jours,
        chute=plus_grande_chute(jours),
        immobilite=immo,
        echanges=echanges,
        faits_connus=any(t.faits is not None for t in tours),
        unites=ecart_des_unites(tours, est_produit)[2],
        unite_serie=getattr(unite, "__name__", "?").removeprefix("PAR_") or "?",
    )


def rendre(d: Derive) -> str:
    """The published page. It NAMES, it doesn't refuse — D1 is level 1."""
    lignes: list[str] = ["# The two drift ratchets — read them TOGETHER", ""]
    if not d.jours:
        return (
            "REFUSED: no tour to read. \"no drift\" and \"nothing was measured\" must never read "
            "the same.\n"
        )
    lignes.append(
        f"## (a) The product share — {d.part_globale:.1%} over the whole window "
        f"(counted in {d.unite_serie})"
    )
    if d.unites:
        # The amended clause requires PUBLISHING both units with their gap. It lives HERE, in
        # the page, because "publish" is an OUTPUT verb: a correct function that nothing prints
        # doesn't publish anything.
        lignes.append(f"  \U00002696\U0000FE0F {d.unites}")
    lignes.append("")
    for j in d.jours:
        barre = "#" * round(j.part * 20)
        lignes.append(f"  {j.date}  {j.part:6.1%}  {barre:<20} ({j.produit}/{j.total})")
    lignes.append("")
    if d.chute:
        lignes.append(
            f"  \U000025B6 LARGEST DROP: {d.chute.depuis} → {d.chute.vers}, "
            f"{d.chute.avant:.1%} → {d.chute.apres:.1%} ({d.chute.ampleur:.1%} less)."
        )
        lignes.append(
            # Here used to live "no date, no threshold was ever handed to it." A third party
            # measured it: it SURVIVES three live sabotages — a page carries it just as well when
            # a date IS wired into the code. *A sentence that certifies its own page proves
            # nothing;* what proves it is a witness (`test_AUCUNE_date_ne_vit_dans_le_CODE...`),
            # not a line of output. So we say what the reader CAN verify: from where to where, by
            # how much.
            f"    Derived from the series in {d.unite_serie}, over {len(d.jours)} day(s) measured."
        )
    elif len([j for j in d.jours if j.total]) < 2:
        # A CLAIM ABOUT THE WORLD DRAWN FROM A POPULATION WHERE NOTHING WAS COMPARABLE. The
        # previous version printed here "the product share never decreases" with a SINGLE day —
        # this module already honored the rule on side (b) ("No measurement") and violated it ten
        # lines above. *An EXCLUDED population is a population NOT JUDGED, not a population at rest.*
        lignes.append(
            "  \U000025B6 No comparison possible: a single day carries tours. \"Nothing decreases\" and "
            "\"nothing could be compared\" don't read the same."
        )
    else:
        # **THE CLAIM WAS CATEGORICAL AND ONLY HOLDS IN ONE UNIT.** Measured: a page where the
        # series is counted in COMMITS printed "the product share never decreases" while in LINES
        # it fell from 90% to 10% — a collapse, published as stability. *A sentence without its
        # unit reads as universal*, and that's the more reassuring of the two readings a reader
        # will remember. The word "never" is what makes the fault expensive.
        lignes.append(
            f"  \U000025B6 No drop IN {d.unite_serie}: the product share does not decrease from one day to "
            f"the next in this unit. \U000026A0\U0000FE0F ANOTHER unit can drop on the same tours — the \U00002696\U0000FE0F line "
            "above gives both global shares."
        )
    lignes += ["", "## (b) The immobile counter — the SET of done items, never its count", ""]
    if d.immobilite:
        lignes.append(
            f"  \U000025B6 Longest immobility: {d.immobilite.commits} commit(s) without a SINGLE "
            f"identifier changing ({d.immobilite.depuis[:7]} → {d.immobilite.jusqua[:7]}, "
            f"{len(d.immobilite.ensemble)} frozen done-items)."
        )
    elif not d.faits_connus:
        lignes.append(
            "  \U000026A0\U0000FE0F NOT MEASURED: no tour carries done-items — the immobility is UNKNOWN, not zero. "
            "The edge read no \U00002705 identifier at all; publishing a commit count here \"without a "
            "single identifier changing\" would be that other project's failure written from ZERO data."
        )
    else:
        lignes.append("  \U000025B6 No measurement: the window carries no tour at all.")
    if d.echanges:
        lignes.append(
            f"  \U000026D4 {len(d.echanges)} SWAP(S) a COUNTER would have missed — the set changed "
            f"without its cardinality moving: {', '.join(s[:7] for s in d.echanges)}."
        )
    lignes += [
        "",
        "\U000026A0\U0000FE0F BOTH ARE READ TOGETHER: producing a lot on ONE single step leaves (a) green and",
        "(b) red; closing out machinery steps does the opposite. Neither one concludes alone.",
    ]
    return "\n".join(lignes) + "\n"
