"""B3 -- THE MAP: where things stand, at a CONSTANT size.

**PROVENANCE, RECORDED HERE RATHER THAN IN A PLAN ITEM (2026-08-18).** `carte_par_arc()`,
`ArcEtat`, and the ``carte`` key of `make ui-json` were born under item **`B4`** ; `B3` carries the
rest of this module. Four living documents cite `B4` as their origin (a UI contract document,
twice, and two governance documents).
**An isolated examiner (D75) named the risk, and they were right**: a plan item can be
withdrawn, closed, or archived -- **so a piece of code's provenance must never live only inside
it**, or four documents end up one day pointing at a trash can. *What has SHIPPED stays shipped
regardless of the status of the item that commissioned it; the code is the one place that cannot
be depopulated.*

**ITS PROPERTY IS NOT TO BE SMALL, IT IS TO NOT GROW.** The operator explicitly lifted the
frugality constraint: *"if the context has to start at 12%, so be it."* The rule is therefore
**depth where we are working, a summary everywhere else** -- and the item names the trap this
avoids: *an EXCERPT is the worst of both worlds: too small to understand, big enough to believe
you've seen it.*

The difference between an excerpt and a summary comes down to one line: **a summary says HOW
MUCH it is hiding, an excerpt does not say so**. Every bounded list here therefore prints what it
did not show.

What the map carries, and the item names them one by one:
``where we stand`` · ``what's left`` · ``what blocks what`` · ``what's expiring`` · ``what's
parallelizable`` · **``what does NOT move``**.

**It carries `B2`'s ordering, it does not recompute it**: `ordonner()` and `file_d_attente()` are
the single home, and *"two commands for one single question is the defect we fix -- the flagship
project ships three."* The map therefore has **no second surface**.

**The `SessionStart` hook that pushes it is FAIL-OPEN** (*"always exits 0"*): if it breaks, it
stays silent. The map therefore remains **pullable by hand** -- a capability that only lives inside
a fail-open channel does not exist on the days it goes down.

Code & docstrings: the domain vocabulary here stays French (the map is read by the operator) — the
product layer of D117.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence

from .perimetre import _PREFIXE
from dataclasses import dataclass

from .obligation import hors_blocs
from .plan_format import PlanReading
from .plan_ordre import PlanOrdre, dependances, file_d_attente, lots, ordonner

#: THE PER-SECTION CEILING, AND IT IS WHAT MAKES THE SIZE CONSTANT. A 10,000-step plan must not
#: render a map 60 times longer than one for a 168-step plan: the map shows the SAME first
#: `PROFONDEUR` lines and says how many it is hiding.
PROFONDEUR = 5

#: The statuses that count as "still to do." Derived from the reader, never hand-copied.
_A_FAIRE = frozenset({"a_faire"})


@dataclass(frozen=True, slots=True)
class Carte:
    """What the map measured. Rendered separately from the text: *a correct view of a stale
    source is an exact lie*, so the computation and the display are each tested on their own."""

    total: int
    par_statut: tuple[tuple[str, int], ...]
    tete: tuple[object, ...]
    tete_cachee: int
    bloqueurs: tuple[tuple[str, int], ...]
    bloqueurs_caches: int
    parallelisable: int
    vagues: int
    immobile: tuple[str, ...]
    immobile_cache: int
    cycle: tuple[str, ...]
    #: **THE CYCLE'S FULL COUNT, AND IT WAS SEPARATE FROM THE BOUNDED LIST.** It was missing, and
    #: `rendre` printed `len(carte.cycle)` -- that is, the length of the tuple **ALREADY
    #: TRUNCATED**. The auditor's measurement: on 10,000 steps all caught in one cycle, the map
    #: announced **"5 unreachable steps."** It was the only section that truncated **without
    #: stating its remainder**, in a file whose docstring promises the opposite two lines above.
    cycle_total: int = 0
    #: **WHAT THE ORDER REFUSED, AND IT WAS NOWHERE.** `carte_run` only looked at
    #: `reading.problems` (the READING); `ordonner` has **its own refusals** (unknown dependency,
    #: self-dependency, cycle) and the map **never** read them. The auditor's measurement: three
    #: broken plans returned `rc 0`, and on an UNKNOWN-dependency the map announced
    #: "2 parallelizable" while the refused edge had been **dropped** -- the item entered as free
    #: "with a confident reason," word for word the class `plan_ordre` says it closed.
    #: The map remains a PROPOSAL organ: it **draws and DECLARES**, it does not refuse. *A wall
    #: is DECLARED, never worked around* -- and a confident number on an amputated graph is worse
    #: than a refusal.
    refus: tuple[str, ...] = ()
    refus_caches: int = 0
    #: **THE ARC LEVEL — the 3rd component of the `*Produces*`** (*"by level: project → ARC →
    #: wave"*). It existed in NO output whatsoever: `make carte` did not carry a single mention of
    #: an arc.
    #: **What it makes visible and the global count HIDES**: `17 done · 32 to do` reads a
    #: FINISHED arc exactly like a NEVER-OPENED one. The day's measurement: **11 arcs · 2 finished
    #: (F, K) · 3 never opened (C, D, J)**. This is "what does not move" one level up.
    arcs_total: int = 0
    arcs_finis: tuple[str, ...] = ()
    arcs_finis_caches: int = 0
    arcs_vierges: tuple[str, ...] = ()
    arcs_vierges_caches: int = 0
    #: **THE BOUND ACTUALLY APPLIED.** `rendre` announced "the first {PROFONDEUR}" by reading the
    #: CONSTANT while `lire` bounded with its PARAMETER: `lire(rd, profondeur=2)` rendered two
    #: lines under a header promising five. *A header that describes a constant instead of what
    #: was actually done is a title that lies, and a title is taken at its word.*
    profondeur: int = PROFONDEUR
    #: **`plan_ordre.lots()` (E1) EXISTED AND HAD NO CALLER IN PRODUCTION** -- the same shape as
    #: `plan_ordre.ordonner()` before `H6`, found while measuring `H5` (chat 1, named, not taken --
    #: `carte.py` was not its batch). `parallelisable` counts startable ITEMS; this field counts
    #: the COLLISION-FREE BATCHES they partition into -- two distinct numbers as soon as two
    #: startable items share a path in their `*Produces*`. *How many things can I run IN PARALLEL
    #: without them clobbering each other* is a question the raw count does not answer.
    parallelisable_lots: int = 0


#: **"WHAT'S EXPIRING" — the `*Produces*` component that shipped NOWHERE.**
#: `carte.lire` did pass `perissables` to `file_d_attente` (the wiring was correct), but **no
#: caller ever populated it**: the `PÉRISSABLE` branch of the reason and the line's `` were
#: **unreachable through `make carte`**. A component the `*Produces*` enumerates and that is never
#: rendered is not shipped, even when the completion clause -- which only bears on size -- passes.
#:
#: **AND THIS IS NOT ONE MORE SECTION.** The whole mechanism already lives in `B2`: an expiring
#: entry **moves to the front of the queue** (`libres.sort(key=…)`), carrying its `` and its
#: written reason. Populating the data is therefore enough to ship the component **without adding
#: a single line** -- which matters, because my last added section had pushed the flagship
#: project's real map from 28 to 33 lines and broken its own clause.
#:
#: **THE POPULATION IS DECLARED BY THE PROJECT, NEVER INVENTED HERE.** Expiry is a JUDGMENT on a
#: plan (*"does what we lose by waiting pay for itself?"*), not a fact a tool can infer. The
#: flagship project already carries it hard-coded in its own harness
#: (`validation/plan/ligne_declare.py:COUT_DU_DELAI`, 4 entries) -- it is not imported: *a tool
#: that imports a project's code crosses a bubble.* We read a **datum**, next to the plan's own
#: gate, and a plan that declares none has none. *A judge that fetches its own population can find
#: it empty and return a green* -- here the empty case is a TRUE answer, and it is read from the
#: file, not assumed.
_PEREMPTION = re.compile(r"^[ \t]*-[ \t]+`?([A-Za-z][A-Za-z0-9-]*)`?[ \t]*:[ \t]*(\S[^\n]*?)[ \t]*$", re.MULTILINE)


def lire_peremption(texte: str) -> dict[str, str]:
    """The ``ident -> raison`` entries of an expiry declaration. PURE, reads no file.

    **Every entry CARRIES ITS REASON, and an entry with no reason does not enter.** This is the
    rule the flagship project wrote above its own table: *"a list with no reason keeps growing on its own, and
    that is how a priority list turns into a junk drawer."* The pattern therefore requires a
    non-empty second member -- a line reading `- A03-1 :` is ignored, not accepted empty.

    **AND CLOSED BLOCKS ARE STRIPPED OUT — I had forgotten this, and the file I WROTE paid the
    price.** The expiry format's own documentation shows the shape inside a ```` ```markdown ```` block; its two
    example lines were read as **REAL declarations**. An isolated audit's measurement: the command
    announced "2 expiry declaration(s) on an ABSENT identifier," and on a plan where one of the two
    actually exists, the item **jumps to rank 1** on the one surface that says where to start --
    with a reason **manufactured from documentation prose**.

    **The worst part: the barrier already existed in this repository, written by me that very
    night.** :func:`~mnemosyne.production.obligation.hors_blocs` had been fixed a few hours earlier
    for this EXACT class -- its docstring says *"a pedagogical example was turning back into a
    declaration."* It is imported, not copied: *a copy drifts, and this one carries three audit
    fixes (a longer closing fence, a 4-backtick fence closed by 5, a fence never closed).*
    *Recording a lesson does not apply it -- and a lesson whose BARRIER is already built gets
    re-violated by not looking at what is already at hand.*"""
    return {m.group(1): m.group(2).strip() for m in _PEREMPTION.finditer(hors_blocs(texte))}


def replier(lectures: Sequence[PlanReading]) -> tuple[PlanReading, tuple[str, ...]]:
    """Fold a TREE of plans into ONE reading — and NAME any identifiers in collision.

    **AUDIT BLOCKER #1, AND IT INVALIDATED THE CLAUSE ITSELF.** The edge case kept only
    ``plans[0]`` and dropped the rest: on the flagship project, the map drew **21 steps out of
    168**, with ``rc 0`` and **not a word**. The `*Done when*` clause says *"the map rendered on
    the flagship project's plan (168 steps)"* -- **its left-hand side did not exist.**
    **Why nobody had seen it**: Mnémosyne's own plan is FLAT (one door, file arcs), so
    ``plans[0]`` is 49/49 there and everything looked right. The flagship project is a TREE of
    sub-plans. *A
    fixture with the SIZE of the real thing but not its SHAPE is green exactly where the defect
    lives.*

    **This is NOT a duplicate of** :func:`~mnemosyne.production.plan_format.merge_plan`, and the
    distinction is measured, not assumed: ``merge_plan`` folds **one door and its arc files**, and
    it **REFUSES** this kind of tree -- each sub-plan is a door in its own right whose items carry
    a ``source`` relative to **its own** door, not to the root (*"the arc's path and the origin
    passed to read_plan must be the SAME string"*). What happens here is the union of a TREE of
    doors; what ``merge_plan`` does is merge one door with its own parts.

    **COLLISIONS ARE RETURNED, NEVER SWALLOWED.** Two plans can carry the same identifier, and
    the order would then be wrong **silently**: `dependances` resolves by ident, so a collision
    would make a dependency point at the wrong item. 2026-08-15 measurement on the flagship project: **168 items,
    168 unique identifiers, ZERO collisions** -- but *a freeze protects against forgetting, never
    against its own author*, and it is the caller who must be able to say so.

    **What this fold does NOT change, backed by measurement**: of the flagship project's **39** items carrying a
    readable ``*Depends on*`` field, **NONE** targets an item in another plan. The folded graph is
    therefore the disjoint union of the per-plan graphs -- folding manufactures no new resolution,
    it only returns 168 items instead of 21."""
    if not lectures:
        raise ValueError("replier received no reading at all -- there is nothing to fold")
    premiere = lectures[0]
    items = tuple(item for lecture in lectures for item in lecture.items)
    vus: dict[str, int] = {}
    for item in items:
        vus[item.ident] = vus.get(item.ident, 0) + 1
    collisions = tuple(sorted(ident for ident, n in vus.items() if n > 1))
    return (
        PlanReading(
            project=premiere.project,
            cap=premiere.cap,
            items=items,
            problems=tuple(p for lecture in lectures for p in lecture.problems),
            prose_lines=sum(lecture.prose_lines for lecture in lectures),
            total_lines=sum(lecture.total_lines for lecture in lectures),
            summary_tables=tuple(t for lecture in lectures for t in lecture.summary_tables),
            parts=tuple(p for lecture in lectures for p in lecture.parts),
        ),
        collisions,
    )


def _prefixe_commun(idents: Sequence[str]) -> str:
    """The longest common prefix of the identifiers, cut before the last trailing DIGIT.

    ``C1 C2 C3`` -> ``C`` · ``A02-1 A02-10`` -> ``A02`` · a single item ``K1`` -> ``K``.

    **TWO SHAPES, TWO CUTS — and my first version only saw ONE.** It stripped trailing digits,
    which gives `C` at Mnémosyne (correct) and **`A`** at the flagship project, where items are named `A02-1`:
    the fourteen arcs all displayed as **`A, A, A, A, A`**. *Third time today I check a derivation
    on ONE shape and break it on the other.*
    The rule that holds for both: **if there is a separator, cut at the last one** (`A02-1` ->
    `A02`); **otherwise** strip the trailing digits (`K1` -> `K`).

    Returns ``""`` when the identifiers share nothing -- the caller then falls back to the path,
    which is ugly but TRUE. *An invented label would be worse than a long one.*"""
    if not idents:
        return ""
    commun = idents[0]
    for autre in idents[1:]:
        while commun and not autre.startswith(commun):
            commun = commun[:-1]
    # **THE ORDER OF THESE THREE LINES DECIDES THE RESULT, and I had it wrong.** I was stripping
    # the separator BEFORE looking for it: `A01-` became `A01`, no more `-`, so the digit-stripping
    # cut kicked in and returned **`A`** -- the flagship project's fourteen arcs all displayed as `A, A, A`.
    # *The order of the checks decides the verdict*, down to three lines of cleanup.
    if commun.endswith(("-", "_")):
        return commun[:-1]
    if "-" in commun:
        return commun.rsplit("-", 1)[0]
    return commun.rstrip("0123456789") or commun


def _etiquette_de_arc(idents: Sequence[str]) -> str:
    """An arc's label: the MAJORITY prefix among its items, not the prefix common to ALL of them.

    **`_prefixe_commun(idents)` breaks as soon as A SINGLE ident shares nothing with the
    others** -- measured on the REAL plan (2026-08-15): three arcs out of eleven (``A``, ``F``,
    ``J``) displayed their FILE PATH instead of their letter, because a single ember (``BR*``,
    D4/I1) slipped into the file is enough to empty the common prefix down to ``""``. *An invented
    label would be worse than a long one* still holds for a group that is TRULY heterogeneous --
    but a group of eight ``A*`` plus one ``BR1`` is not heterogeneous, it just has one guest.

    Each ident votes its OWN prefix (``_prefixe_commun`` applied to itself alone); the label is
    that of the largest voting group, ties broken alphabetically to stay deterministic. Identical
    to the old computation when the group is homogeneous (everyone votes the same) -- only the
    mixed case changes, and it changes toward the TRUTH rather than toward the path."""
    if not idents:
        return ""
    votes: dict[str, int] = {}
    for ident in idents:
        prefixe = _prefixe_commun((ident,))
        votes[prefixe] = votes.get(prefixe, 0) + 1
    return max(sorted(votes), key=votes.get)


def _arc_de(item: object, arcs: Mapping[str, str] | None) -> str | None:
    """An item's arc — **INJECTED when the caller knows it**, derived otherwise.

    **THREE READINGS GIVE THREE ANSWERS, MEASURED ON THE FLAGSHIP PROJECT'S PLAN:**

    ===================================== ======== ==========================================
    what is read                          flagship what it is worth
    ===================================== ======== ==========================================
    the identifier's LETTER prefix        **3**    WRONG: `A01-1`, `A03-5`, `A11-2` -> "A"
    the item's ``source`` file            149      WRONG: one file PER ITEM at leaf level
    **the sub-plans** (what the door      **14**   what the plan itself CALLS an arc
    lists)                                         ("# PLAN — ARC 11 — …")
    ===================================== ======== ==========================================

    **Only the caller who has walked the tree knows the right answer**: `lire` receives a FOLDED
    reading, where the items' origin is lost. Hence the injection. *A judge that guesses its own
    population guesses differently depending on the plan's shape* -- here the prefix gave 11/11 on
    Mnémosyne (a FLAT plan) and 3/14 on the flagship project (a TREE plan), that is, **right exactly where I
    tested it and wrong exactly where the clause applies**.

    **The fallback to ``source`` stays correct for a FLAT plan** -- an arc file carries all its
    items there (measured: Mnémosyne, 11 sources for 11 arcs). It is only used absent an
    injection.

    **THREE BRANCHES, AND THE THIRD IS THE ONE I NEARLY LOST**: a plan of a SINGLE file has no
    ``source`` (there is nothing to distinguish), and my fallback left it **with no arc at all**.
    The identifier prefix becomes the only structure left there -- it is wrong as a GENERAL rule
    (it collapses `A01`/`A03`/`A11` onto "A"), it remains correct as a LAST resort, where there is
    nothing else to read. *A fallback that returns `None` manufactures a "0 arcs" that looks like
    a measurement.*
    """
    if arcs is not None:
        return arcs.get(getattr(item, "ident", ""))
    source = getattr(item, "source", "") or ""
    if source:
        return source
    trouve = _PREFIXE.match(getattr(item, "ident", "") or "")
    return trouve.group(1) if trouve else None


def _borne(items: tuple, profondeur: int) -> tuple[tuple, int]:
    """The first ``profondeur`` items, and **HOW MANY are hidden**.

    The second member is not decorative: it is what separates a SUMMARY from an EXCERPT. A
    truncated list with no remainder reads like a complete list -- *big enough to believe you've
    seen it.*"""
    return items[:profondeur], max(0, len(items) - profondeur)


def lire(
    reading: PlanReading,
    *,
    arcs: Mapping[str, str] | None = None,
    faits: frozenset[str] | None = None,
    perissables: dict[str, str] | None = None,
    profondeur: int = PROFONDEUR,
) -> Carte:
    """Measure a plan's map. PURE: it reads no file and prints nothing.

 **It CALLS `B2`** (`ordonner`, `file_d_attente`): the ordering has a single home.
 Recomputing a rank here would manufacture a second truth that drifts -- the fault this
 repository measured six times in one night.

 **``faits=None`` DERIVES FROM THE PLAN, and that is the default because the other value was
 lying.** The first draft carried ``faits: frozenset[str] = frozenset()`` and **never
 populated it**: "WHERE TO START" was therefore computed as if NOTHING were done.
 `file_d_attente` NAMES this exact trap in its own docstring (*"an item marked but absent
 from `faits` blocks its dependents as if it were still to do […] staying silent about it would
 make it a trap"*) -- the map was staying silent about it.
 The auditor's measurement on this repository's own plan: **2 ranks instead of 7**, with
 `D1`, `B3`, `I2` startable and **absent** from the one surface that says where to start. The
 map has five slots and was only filling two.
 ``frozenset()`` remains passable **explicitly** ("assume nothing is done"): it was the
 DEFAULT that was wrong, not the possibility itself."""
    if faits is None:
        faits = frozenset(item.ident for item in reading.items if item.status == "fait")
    ordre: PlanOrdre = ordonner(reading)
    file, ignorees = file_d_attente(reading, faits=faits, perissables=perissables, a_faire=_A_FAIRE)

    compte: dict[str, int] = {}
    for item in reading.items:
        compte[item.status] = compte.get(item.status, 0) + 1

    tete, tete_cachee = _borne(tuple(file), profondeur)
    bloqueurs = tuple(
        (ident, n) for ident, n in sorted(ordre.deblocages, key=lambda x: (-x[1], x[0])) if n
    )
    bloqueurs_bornes, bloqueurs_caches = _borne(bloqueurs, profondeur)

    # "WHAT DOES NOT MOVE" -- the item sets it in bold, and it is the only section whose absence
    # reads as good news. An item that NOTHING unblocks and that unblocks NOTHING is not "done": it
    # is out of the current, and nobody ever notices it.
    # **THE CLAUSE WAS DEAD, AND THE AUDIT IS WHAT FOUND IT.** It read
    # `attendus = {d for _, d in ordre.deblocages}` -- but `deblocages` carries `(ident, COUNT)`, so
    # `d` was the **count**. The set held `int`s (`[0,1,2,3,4,5,9,16]`), and
    # `item.ident not in attendus` compared a `str` to integers: **always true**. Only the half
    # "nobody is waiting on it" remained; the half "it is not waiting on anyone" was **never
    # tested**. Measured on this repository's own plan: the section announced **18 items** of which
    # **17 were awaited by someone** -- 94% wrong, in the section the item sets in bold.
    # The right source is the graph itself, through the judge's own accessor (`dependances`),
    # never a byproduct whose shape is guessed. *Two values of different types compare without a
    # murmur, and that is the one class of defect that reddens nowhere.*
    graphe, _refus_deps = dependances(reading)
    declarants = frozenset(ident for ident, deps in graphe.items() if deps)
    immobiles = tuple(
        sorted(
            item.ident
            for item in reading.items
            if item.status in _A_FAIRE
            and not ordre.debloque(item.ident)
            and item.ident not in declarants
        )
    )
    immobile_borne, immobile_cache = _borne(immobiles, profondeur)

    # "PARALLELIZABLE" WAS COUNTING ITEMS ALREADY DONE: `ordonner` reads no status at all, so
    # the first wave contains the ones too. Measurement: "8 now" two lines above a queue of
    # **2**, and on a fixture with 9,999 done, **"10,000 parallelizable"** for a SINGLE remaining
    # item. *A count answering "how many right now" must exclude what is already behind us.*
    # The ORDER's own refusals, distinct from the READER's: a dropped edge does not make the plan
    # unreadable, it makes the order silently WRONG. They are named, bounded like their neighbors.
    refus_ordre = tuple(
        sorted({f"{p.kind} — {_ecourter(p.detail, 60)}" for p in ordre.problems if p.kind != "cycle_de_dependances"})
    )
    refus_bornes, refus_caches = _borne(refus_ordre, profondeur)

    # **AND MY FIRST FIX ONLY CORRECTED ONE DIRECTION.** The original draft counted
    # `ordre.vagues[0]` whole, so the items were in it ("8 now" above a queue of 2). I filtered
    # out the done items -- and the SECOND audit measured the SYMMETRIC defect that filter left
    # intact: `vagues[0]` only contains items with NO declared dependency at all, so an item whose
    # only dependency is is startable and **is not in it**. Measured on this repository's own
    # plan: "**1 now**" two lines above a queue of **15**.
    # The right source was not "add a filter," it was **already computed**: the QUEUE is exactly
    # "what can start right now" -- expiry, refusals, and done items already accounted for.
    # `vagues[0]` answers a DIFFERENT question (the first topological layer, statuses ignored).
    # *Two opposite-sign errors on the same number say the SOURCE is wrong, not that a filter is
    # missing* -- one more filter would have hidden the second error for one more round.
    # **THE ARC IS DERIVED THROUGH THE JUDGE'S OWN ACCESSOR, never by `ident[0]`.**
    # `perimetre._PREFIXE` carries THREE audit fixes a copy would lose: a prefix is 1 to 4 LETTERS
    # long (`ident[0]` returned `A` where the arc is actually called `AB` -- "breaking both ways on
    # 13 of 16 plans"), and the NUMBER is not read from it (a numbering coincidence flipped an
    # entire level-2 arc). *The right source is the judge's own accessor* -- and I paid for it this
    # very morning, having rewritten a function whose barrier already existed in this repository.
    par_arc: dict[str, dict[str, int]] = {}
    idents_par_arc: dict[str, list[str]] = {}
    for item in reading.items:
        arc = _arc_de(item, arcs)
        if arc:
            par_arc.setdefault(arc, {})
            par_arc[arc][item.status] = par_arc[arc].get(item.status, 0) + 1
            idents_par_arc.setdefault(arc, []).append(item.ident)
    # **THE LABEL IS NOT THE IDENTITY.** The arc is identified by its PATH (unique, stable); what
    # gets PRINTED must be what the reader recognizes. My previous fix replaced arc letters with
    # file names -- correct on the count alone, **unreadable** on the page, and the line went from
    # 1 to 3 lines while my clause is about SIZE.
    # *I fixed the count by breaking the names: the same class as "a fix that repairs one shape
    # by breaking the other," recorded two rounds earlier, wearing a different mask.*
    # The label is the MAJORITY PREFIX of the arc's identifiers (`_etiquette_de_arc`) -- measured:
    # `C` `D` `J` `K` at Mnémosyne (items `C1..C6`), `A02` `A03` at the flagship project (items `A02-1..`). *An
    # identifier the reader recognizes beats a path that merely describes it.*
    etiquettes = {arc: _etiquette_de_arc(ids) or arc for arc, ids in idents_par_arc.items()}
    finis = tuple(
        etiquettes[arc]
        for arc in sorted(par_arc)
        if par_arc[arc].get("fait", 0) == sum(par_arc[arc].values())
    )
    # "NEVER OPENED" = ALL its items are `a_faire`. A single `pret` or `en_cours` is enough to
    # take it out of that set -- the orchestrator had counted `H` among the untouched arcs, but
    # `H2` is `pret`. *An arc someone has already touched is not a never-opened arc, and confusing
    # the two would send someone onto work already taken.*
    vierges = tuple(
        etiquettes[arc]
        for arc in sorted(par_arc)
        if par_arc[arc].get("a_faire", 0) == sum(par_arc[arc].values())
    )
    finis_bornes, finis_caches = _borne(finis, profondeur)
    vierges_bornes, vierges_caches = _borne(vierges, profondeur)

    premiere_vague = tuple(rang.ident for rang in file)
    # `lots()` (E1) partitions EXACTLY the population `parallelisable` already counts -- never a
    # second answer to "what is startable right now," only a THIRD question asked of the same
    # answer: how to split it up without a write collision.
    #
    # **SCOPE, in TWO distinct halves -- never copied here, only pointed to.**
    # (1) CORRECTNESS -- what `lots()` can detect as a collision, and what it cannot: already
    # written, audited, and proven on the flagship project's REAL plan inside `plan_ordre.lots()`'s own docstring
    # (overlap of `*Produces*` paths, YES; a "serialized resource" no field of the plan declares,
    # NO). Read THAT scope, not a copy that would drift.
    # (2) COST, MEASURED HERE BECAUSE THIS IS THE CALL SITE THAT FIXES IT -- `lots()` is O(n²) in
    # the size of `premiere_vague`, never bounded by this call. On the real repository, `make
    # carte` still runs in 0.6s (measured, `time`). On the SYNTHETIC 10,000-step fixture (already
    # declared elsewhere as "the SIZE of the real thing, not its SHAPE"), several thousand
    # simultaneously-startable items push the test suite up by +130s -- a stress-test cost, not a
    # real-use cost. Named rather than fixed: a size bound would answer a problem that does not
    # exist yet on ANY real data -- the same over-engineering this repository refuses elsewhere.
    nb_lots = len(lots(reading, premiere_vague).lots)
    return Carte(
        total=len(reading.items),
        par_statut=tuple(sorted(compte.items(), key=lambda x: (-x[1], x[0]))),
        tete=tuple(tete),
        tete_cachee=tete_cachee,
        bloqueurs=bloqueurs_bornes,
        bloqueurs_caches=bloqueurs_caches,
        parallelisable=len(premiere_vague),
        parallelisable_lots=nb_lots,
        vagues=len(ordre.vagues),
        immobile=immobile_borne,
        immobile_cache=immobile_cache,
        cycle=ordre.cycle[:profondeur],
        cycle_total=len(ordre.cycle),
        refus=refus_bornes,
        refus_caches=refus_caches,
        profondeur=profondeur,
        arcs_total=len(par_arc),
        arcs_finis=finis_bornes,
        arcs_finis_caches=finis_caches,
        arcs_vierges=vierges_bornes,
        arcs_vierges_caches=vierges_caches,
    )


@dataclass(frozen=True, slots=True)
class ArcEtat:
    """One arc, its aggregated state, and what it is waiting on — NEVER truncated.

    **Why a second class instead of exposing the detail `lire` already computes (B4)**:
    `Carte` is bounded to `profondeur` by construction — that is EXACTLY what makes it a constant
    size for a session whose context is the scarce resource (`B3`). An interface (`make ui-json`)
    does not have that constraint: it scrolls, it consumes no session context. Truncating there
    would manufacture the same defect as an `EXCERPT` — *too small to understand, big enough to
    believe you've seen it* — on the ONE view `B4` builds specifically to be looked at in full."""

    etiquette: str
    fichier: str
    total: int
    fait: int
    en_cours: int
    a_faire: int
    #: ``"fini"`` (all ) · ``"vierge"`` (all , nobody has touched it) · ``"en_cours"`` (everything else).
    etat: str
    #: The DISTINCT reasons (already written by `B2`, never rephrased here) this arc's `a_faire`
    #: items are not yet startable. Empty means: done, or ready to take — never "I couldn't say."
    attend: tuple[str, ...]
    #: True if AT LEAST ONE item of this arc is, today, in `file_d_attente(...).rangs` — the arc is
    #: part of "the current wave" (E2). Never recomputed separately: derived from the same
    #: `file_d_attente` pass as `attend`, the same datum read twice rather than measured twice.
    demarrable: bool


def carte_par_arc(
    reading: PlanReading,
    *,
    arcs: Mapping[str, str] | None = None,
    faits: frozenset[str] | None = None,
) -> tuple[ArcEtat, ...]:
    """One `ArcEtat` per arc of the plan, sorted by label, NEVER truncated (see `ArcEtat`). PURE.

    **Reuses `file_d_attente` (`B2`) for "what an arc is waiting on" — recomputes nothing.** The
    reason a blocked item is blocked is already written, carefully, by the queue's own judge;
    reinventing it here would have opened a second home that drifts from the first (measured
    elsewhere in this module: two commands for one question is the defect we fix, not the one we
    reproduce).

    **`attend` deliberately ignores `en_cours` items**: `file_d_attente` sets them aside because
    "the question no longer applies," a true statement that says nothing about what an arc is
    WAITING ON — it says it has already been taken. Only items still `a_faire` and blocked count
    here."""
    if faits is None:
        faits = frozenset(item.ident for item in reading.items if item.status == "fait")
    file = file_d_attente(reading, faits=faits, a_faire=_A_FAIRE)
    raisons_ecart = dict(file.ecartes)
    idents_libres = frozenset(r.ident for r in file.rangs)

    items_par_arc: dict[str, list] = {}
    idents_par_arc: dict[str, list[str]] = {}
    fichier_par_arc: dict[str, str] = {}
    for item in reading.items:
        arc = _arc_de(item, arcs)
        if not arc:
            continue
        items_par_arc.setdefault(arc, []).append(item)
        idents_par_arc.setdefault(arc, []).append(item.ident)
        if item.source and arc not in fichier_par_arc:
            fichier_par_arc[arc] = item.source
    etiquettes = {arc: _etiquette_de_arc(ids) or arc for arc, ids in idents_par_arc.items()}

    resultat: list[ArcEtat] = []
    for arc in sorted(items_par_arc):
        items = items_par_arc[arc]
        total = len(items)
        fait = sum(1 for it in items if it.status == "fait")
        en_cours = sum(1 for it in items if it.status == "en_cours")
        a_faire = sum(1 for it in items if it.status in _A_FAIRE)
        if fait == total:
            etat = "fini"
        elif a_faire == total:
            etat = "vierge"
        else:
            etat = "en_cours"
        attend = tuple(
            sorted(
                {
                    raisons_ecart[it.ident]
                    for it in items
                    if it.status in _A_FAIRE and it.ident in raisons_ecart
                }
            )
        )
        resultat.append(
            ArcEtat(
                etiquette=etiquettes[arc],
                fichier=fichier_par_arc.get(arc, ""),
                total=total,
                fait=fait,
                en_cours=en_cours,
                a_faire=a_faire,
                etat=etat,
                attend=attend,
                demarrable=any(it.ident in idents_libres for it in items),
            )
        )
    return tuple(resultat)


#: **WHAT "AWAITED BY N" MEASURES, AND WHAT IT DOES NOT — measured 2026-08-15.**
#: It is the **out-degree**: how many items DECLARE this one as a dependency. It is **NOT** the
#: number of items that would actually become STARTABLE if it fell -- *lifting one dependency
#: only unblocks the items for which it was the LAST one.* On this repository's own plan:
#:
#: ===== ============== ==================
#: item  awaited by      makes startable
#: ===== ============== ==================
#: A1    16              **10**
#: B1    9               **0**
#: B2    3                **0**
#: ===== ============== ==================
#:
#: **The computation is not wrong — the out-degree is the RIGHT metric for ORDERING.** It was the
#: WORD that was lying ("unblocks 9" when the answer is zero), and an ambiguous word reads
#: correctly half the time: that is exactly what makes it durable.
#:
#: **WHY WE DON'T PUBLISH BOTH NUMBERS**: the effective count requires recomputing the queue
#: once per blocker. Measured on a 10,000-item fixture: **20s for five recomputations**, plus 3.7s
#: for the base queue. A surface pushed at the start of every session cannot afford that. *Renaming
#: costs zero and removes the lie; recomputing costs 24s and kills the surface.*
_RULE = "=" * 78

#: **`B2`'S OWN WORD, TRANSLATED ON MY SIDE, AND IT IS A CHOICE WRITTEN TO BE CONTESTED.**
#: `plan_ordre` composes its reasons with "débloque N étape(s)" / "LE plus déblocant." **The
#: number is correct** (the out-degree ORDERS correctly); it is the **word** that promises an
#: effective unblocking the number does not measure. On the map's own line it is, on top of that,
#: **redundant**: `attendu par N` is already printed **two columns earlier**, with the same N.
#: *The same number under two words, one true, one false, on the same line.*
#:
#: **Why fix it here and not at the source** — measured, not preference:
#: * `Rang.raison` has **A SINGLE consumer** in the entire repository: the line below. Translating
#:   it here therefore covers **100%** of its real scope today.
#: * the vocabulary is `B2`'s own, **frozen by three of its own witnesses** and explained in its
#:   own docstrings. Renaming it would be re-litigating another item's design from inside mine.
#: **This is not free and I am saying so**: the day a second consumer appears, it will read the
#: original word. *Fixing the copy does not fix the source* -- here the source stays intact ON
#: PURPOSE, and that is flagged rather than quietly patched.
#: The "reason" column's width. It was TRUNCATING SILENTLY, in a module whose docstring promises
#: the opposite two screens up -- and `plan_ordre`, to its credit, adds ` …` in the same case. The
#: measurement that surfaced it: an EXPIRY's reason, the one field the item requires spelled out in
#: full, was losing its date ("… closes on 2026-09-01" cut down to "closes"). *A silent cut eats,
#: first, whatever was written with the most care.*
LARGEUR_RAISON = 44
_ELLIPSE = " …"


def _ecourter(texte: str, largeur: int) -> str:
    """``texte`` bounded to ``largeur``, and **it SAYS it cut**. Same rule as its neighbors."""
    if len(texte) <= largeur:
        return texte
    return texte[: max(0, largeur - len(_ELLIPSE))].rstrip() + _ELLIPSE


_SEPARATEUR = " — "
_TETE_PERISSABLE = "PERISHABLE"
_SUFFIXE_REDONDANT = ", and unblocks "


def _raison_vraie(raison: str) -> str:
    """`B2`'s reason, stripped of what the line ALREADY says, and of the word that lies.

    **It does NOT remove the reason**: *a rank with no written reason is an invisible judgment
    call* (`B2`'s level-2 obligation). It strips the **HEAD**, which is the number already printed
    two columns earlier under a false word, and keeps the **TAIL**, which carries the only new
    information — "the MOST … among the startable remainder," "tied with K others," "the alphabet
    decides."

    **Except for `PERISHABLE`, where the head IS the information**: expiry is printed nowhere
    else on the line. It only loses its `, and unblocks N` suffix, redundant with the column for the
    same reason as the others.

    **A reason with no separator is returned AS-IS**: the day `B2` composes a new shape, it
    passes through whole instead of being cut at random. *A fix that assumes a grammar it does not
    control must degrade to silence, never to truncation.*"""
    if raison.startswith(_TETE_PERISSABLE):
        tete, _, _reste = raison.partition(_SUFFIXE_REDONDANT)
        return tete
    _avant, separe, queue = raison.partition(_SEPARATEUR)
    return (queue if separe else raison).replace("unblocking", "awaited")


def _ligne_des_arcs(carte: Carte) -> str:
    """The ARC level — **ONE line**, and it is the orchestrator's call, not mine.

    **Six components times three levels would TRIPLE the output**, while the completion clause
    demands a CONSTANT size: the item's two halves contradict each other if you read *"by level"*
    as *"three views."* The item names its own arbiter: *"depth where we're working, a summary
    everywhere else."* **The arc level is therefore a one-line SUMMARY**, bounded like its
    neighbors. *I already broke this clause once by adding a section; we're not doing it again.*

    **What it makes visible and the global count HIDES**: `17 done · 32 to do` reads a FINISHED
    arc exactly like a NEVER-OPENED one. Here both are named."""
    if not carte.arcs_total:
        return "PAR ARC : (aucun identifiant d'arc lisible dans ce plan)"
    morceaux = [f"{carte.arcs_total} arcs"]

    def _court(nom: str) -> str:
        """The SHORTENED arc name — only at render time, never in the computation.

        The arc is identified by its path (`plan/05-l-enquete.md`, `…/flagship/plan/07-…`):
        that is what makes it UNIQUE, and the judge must keep that identity. But a map line
        carrying five full paths is no longer a line — *the item's bound is in LINES, readability
        is in CHARACTERS, and both are lost at the same spot.*"""
        return nom.rsplit("/", 1)[-1].removesuffix(".md")
    for etiquette, noms, caches in (
        ("fini", carte.arcs_finis, carte.arcs_finis_caches),
        ("jamais ouvert", carte.arcs_vierges, carte.arcs_vierges_caches),
    ):
        total = len(noms) + caches
        if not total:
            continue
        liste = ", ".join(_court(n) for n in noms) + (f" +{caches}" if caches else "")
        morceaux.append(f"{total} {etiquette}{'s' if total > 1 else ''} ({liste})")
    reste = carte.arcs_total - len(carte.arcs_finis) - carte.arcs_finis_caches
    reste -= len(carte.arcs_vierges) + carte.arcs_vierges_caches
    if reste:
        morceaux.append(f"{reste} en cours")
    return "PAR ARC : " + " · ".join(morceaux)


def rendre(carte: Carte, *, projet: str) -> str:
    """The map's text -- **the same number of lines regardless of the plan's size**.

    Every section has a line count BOUNDED by ``PROFONDEUR``, and each one prints what it is
    hiding. This is the item's `*Done when*` clause, and it is measured by its witness on two
    populations: a real plan and a 10,000-step fixture."""
    statuts = " · ".join(f"{n} {s}" for s, n in carte.par_statut) or "aucun item"
    lignes = [
        f"CARTE — {projet}",
        _RULE,
        f"OÙ ON EN EST : {carte.total} items · {statuts}",
        f"CE QUI EST PARALLÉLISABLE : {carte.parallelisable} maintenant "
        f"({carte.parallelisable_lots} lot(s) sans collision), sur {carte.vagues} vague(s)",
        _ligne_des_arcs(carte),
        "",
        f"PAR OÙ COMMENCER (les {carte.profondeur} premiers, et la RAISON de chaque rang) :",
    ]
    lignes += [
        f"  {r.rang:>2}. {r.ident:<10} attendu par {r.debloque:<3} {'\U000023F3 ' if r.perissable else ''}{_ecourter(_raison_vraie(r.raison), LARGEUR_RAISON)}"
        for r in carte.tete
    ] or ["  (rien à commencer — tout est fait, bloqué, ou en cours)"]
    if carte.tete_cachee:
        lignes.append(
            f"  … et {carte.tete_cachee} autre(s) dans la file — `make plans` les donne tous"
        )

    lignes += ["", "CE QUI EST LE PLUS ATTENDU :"]
    lignes += [f"  {ident:<10} attendu par {n}" for ident, n in carte.bloqueurs] or [
        "  (aucun item n'en bloque un autre)"
    ]
    if carte.bloqueurs_caches:
        lignes.append(f"  … et {carte.bloqueurs_caches} autre(s) attendu(s) par au moins 1")

    lignes += ["", "\U000026D4 CE QUI NE BOUGE PAS — personne ne l'attend, il n'attend personne :"]
    lignes += [f"  {ident}" for ident in carte.immobile] or [
        "  (rien : tout item à faire est dans le courant)"
    ]
    if carte.immobile_cache:
        lignes.append(f"  … et {carte.immobile_cache} autre(s) hors du courant")

    if carte.refus:
        # **A SINGLE LINE, AND THE CLAUSE IS WHAT FORCED IT.** My first draft listed the refusals
        # like their neighbors (up to 7 lines): the flagship project's real map went from 28 to **33 lines**, a
        # **15.2%** gap -- past the 10% the clause tolerates. *A section that only appears on an
        # IRREGULAR population makes the map grow exactly where the property must hold.* The
        # declaration stays whole (count + one example + where to read the rest); it is its
        # FOOTPRINT that is cut down to the one thing that's necessary.
        total_refus = len(carte.refus) + carte.refus_caches
        lignes += [
            "",
            f"\U000026A0\U0000FE0F ORDRE AMPUTÉ — {total_refus} arête(s) refusée(s), les chiffres ci-dessus en "
            f"tiennent compte : {carte.refus[0]} — `make plans` les donne toutes",
        ]

    if carte.cycle:
        lignes += [
            "",
            f"\U000026D4 CYCLE — {carte.cycle_total} étape(s) inatteignables : {', '.join(carte.cycle)}"
            + (f" … et {carte.cycle_total - len(carte.cycle)} autre(s)"
               if carte.cycle_total > len(carte.cycle) else ""),
        ]
    return "\n".join(lignes) + "\n"
