"""E4 -- THE ARC MANDATE IS EMITTED, never hand-written (this repo's own parallelism notes).

**THE BOUNDARY WITH `C4`, WRITTEN HERE SO IT SURVIVES THE SESSION THAT DECIDED IT.** `C4`
(myself, `production/a_lire.py`, NOT `plan_format.py`) produces the CONTENT and the MANDATE
TEMPLATE -- the SHAPE of the text. This module produces the EMITTER: it ASSEMBLES and PUBLISHES,
it never invents the shape. Two items were producing the SAME thing seen from two sides -- if this
module wrote the mandate's shape, two homes would carry the same deliverable, exactly what this
repo fights against. *One home, emitted, never recopied* (D163).

**`C4` IS BUILT** (`production/a_lire.py`): `rendre()` CONSUMES its template
(:func:`~mnemosyne.production.a_lire.rendre_gabarit`) -- it does not replace it. The admission
:data:`A_LIRE_EN_ATTENTE` stays written as a record of what the boundary used to be before, and
because *publishing what is missing is not the same as refusing* also holds for a gap that just
closed.

**LEVEL 1 -- it PUBLISHES.** The refusal (two mandates that overlap, or an incomplete batch
assembly) is a separate gate -- :func:`recouvrement` / :func:`assembler_mandat` render the FACT,
never a `sys.exit`: it is the edge (`lot_emit_run.py`) that REFUSES, the same doctrine everywhere
in this module.

**NO ORCHESTRATOR REASONING**: the mandate only composes fields ALREADY PUBLISHED in the plan
(`ident`, `title`, `status`) -- never a comment, a justification, a piece of arbitration prose.
That is the item's closing condition, word for word: *"the mandate carries no orchestrator
reasoning."*

**C5 WIRED HERE, on 2026-08-16** -- the closing audit of `C5` (D75) measured that
`parc.decouper`/`parc.assembler` were PROVEN (twice: once on a real batch dispatched to real
agents, and once by a replayable sabotage) but **never consumed**: *"returning a boolean is not
refusing,"* and this module was specifically named as the ONLY place that could act on
`Assemblage.complet=False`. `decouper_mandat`/`rendre_lot`/`assembler_mandat` below are that
wiring -- DIRECT calls into `parc`, never a second split or a second assembler.
**WHAT THIS WIRING DOES NOT PROVE (YET)**: condition (b) of the item requires *"exercised on a
real session dispatch"* -- this module makes the refusal REAL and testable (see the "THE EDGE"
section of `tests/orchestration/test_lot_emit.py`), but no session has been dispatched THROUGH
this exact path. *Publishing what is missing is not the same as refusing*: named, not staged.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import TypeVar

from .a_lire import rendre_gabarit
from .parc import Assemblage, Lot, assembler, decouper
from .perimetre import lettre_d_arc
from .plan_format import PlanItem, PlanReading, STATUS_LABEL, chemins_cites_par_produit
from .precedence import CLAUSE as CLAUSE_DE_PRECEDENCE

_T = TypeVar("_T")

#: The HISTORICAL admission, kept as a record of what the boundary used to say before `C4` existed
#: -- exactly the move this repo's own governance established this same day for a pointer that is
#: missing: name it, do not invent, do not stay silent. `rendre()` no longer prints it (`C4` is
#: built); it stays exported for any code that still imports it.
A_LIRE_EN_ATTENTE = "AWAITING C4 -- the mandate template does not exist yet"

#: The ADDRESS of the posts contract, never its copy (D163, D162) -- the same path regardless of
#: which repo the mandate is issued from: a project that adopts the posts convention does not keep
#: its own copy, it reads Mnémosyne's. A string, not a `Path`: `rendre()` never opens this file, it
#: only NAMES it.
CONTRAT_DES_POSTES = "docs/postes/README.md"


@dataclass(frozen=True, slots=True)
class Mandat:
    """One arc-chat's mandate -- door, items, and NOTHING beyond what the plan already publishes."""

    arc: str
    porte: str
    items: tuple[PlanItem, ...]

    @property
    def ouverts(self) -> tuple[PlanItem, ...]:
        """The items still to do -- neither `fait` (done) nor `clos` (closed)."""
        return tuple(i for i in self.items if i.status not in ("fait", "clos"))

    @property
    def fichiers(self) -> frozenset[str]:
        """The REAL paths that the OPEN items' `*Produit*` field cites -- the unit that
 :func:`recouvrement` protects, in the literal sense of `E4`'s closing clause.

 **THE ADMITTED GAP, NOW CLOSED: `C2` built `chemins_cites_par_produit`
 (`plan_format.py`) while this module was waiting.** Before, for lack of a `*Produit*`
 reader, the item's IDENTIFIER served as a proxy -- published as such, never mistaken for a
 real path. `E1` (`plan_ordre.lots()`) asks EXACTLY the same question over the same
 population to judge write overlap between two steps of a wave: *one home, never a second
 answer to "which paths does this `*Produit*` cite?"* -- same reader, same absence of a
 folder filter (`lots()` applies none; `produit_problems`, a DIFFERENT question, applies one
 to refuse a `*Produit*` that cites ONLY a folder).

 **`self.ouverts`, NOT `self.items` — measured against the real plan, never assumed.**
 The first pass of this fix compared ALL items and found one of this repo's own governance
 files "in overlap" between arc A and arc C: `A2` and `C3`.

 **CORRECTED AFTER THE ISOLATED AUDIT OF `E4`: BOTH were already , not "`C3` open"**
 **as this note said before verification.** The audit measured a specific historical
 commit; re-checked here a second time, independently, before correcting the text: the
 commit that precedes this module already shows `A2` and `C3` both ``. *A file already
 written by TWO CLOSED items is a fortiori not a collision risk between two chats working
 TODAY* -- `plan_ordre.lots()` never asks the question any other way, in fact: it only
 receives the startable idents from `file_d_attente`, never the closed facts. Same
 population, consistent with this question's only other caller.
 """
        chemins: set[str] = set()
        for item in self.ouverts:
            chemins.update(chemins_cites_par_produit(item.field("produit") or ""))
        return frozenset(chemins)


def mandat_pour_arc(
    reading: PlanReading, *, porte: str, arc: str, arcs: dict[str, str] | None = None
) -> Mandat:
    """The mandate for arc `arc`, drawn from the reading -- never hand-built.

    Derived from :func:`~mnemosyne.production.perimetre.lettre_d_arc`, the same accessor this
    repo's own perimeter-scope gate uses to judge negative scope -- *one home*, not a third regex
    of the same pattern in a third file.

    **C9: THIS FALLBACK IS WRONG ON A PLAN WITH SUB-PLAN FOLDERS (D166 clause 3), AND THAT IS
    THE ONLY CASE WHERE `arcs` WINS.** Measured on the first adopter project: the letter-prefix fallback melts 14 real
    sub-plans into 3 letters — `lettre_d_arc("A01-1") == lettre_d_arc("A03-5") == "A"`, with NO
    relation to the 14 arcs the plan ITSELF declares. When the caller has walked the tree and knows
    each item's TRUE identity (:func:`~.plan_registry.arc_par_item`), it injects it through `arcs`
    and this module no longer guesses anything; on a FLAT plan (`arcs=None`, most of the corpus,
    where the prefix already coincides with the arc file), the fallback stays exactly what it
    always was — unchanged behavior, zero regression on the already-correct case.

    **REGRESSION FOUND BY THE ISOLATED AUDIT (D75), FIXED HERE: an ember (`BR1`..`BR5`,
    D4/I1) DROPPED IN THE SAME SUB-PLAN FILE AS A REAL ITEM WAS ENTERING THAT ARC'S MANDATE.**
    `arc_par_item` maps EVERY readable item to its sub-plan, embers included — which is exactly
    right for the question it answers ("which sub-plan carries this item?"), but wrong for THIS
    function, which promises above that *"an ember never enters any real arc mandate."* On the
    flat fallback this was never an issue: `lettre_d_arc("BR1") == "BR"` never coincides with any
    real arc letter. On a plan with sub-plans, nothing played that role — excluded here, by the
    shape of the IDENT (stable, independent of whichever identity mechanism is chosen), never by
    the sub-plan that hosts it."""
    if arcs is not None:
        from .signalements import _PREFIXE_BRAISE

        items = tuple(
            i
            for i in reading.items
            if arcs.get(i.ident) == arc and lettre_d_arc(i.ident) != _PREFIXE_BRAISE
        )
    else:
        items = tuple(i for i in reading.items if lettre_d_arc(i.ident) == arc)
    return Mandat(arc=arc, porte=porte, items=items)


def arcs_du_plan(reading: PlanReading, *, arcs: dict[str, str] | None = None) -> frozenset[str]:
    """The arcs this plan really carries -- the same accessor this repo's own perimeter-scope gate
    uses (`arcs_existants`), MINUS the embers (`D4`/`I1`) -- never an arc to issue a mandate to.

    **REGRESSION MEASURED BY CHECKING, NOT GUESSED**: the real plan carries 5 embers today
    (`BR1`..`BR5`, dropped inside real arc files), and `arcs_existants` (ident prefix, correct for
    ITS OWN use elsewhere) counts them as a 12th group, `"BR"`. `mandat_pour_arc` does not suffer
    from this -- `lettre_d_arc("BR1") != "B"`, an ember never enters any real arc mandate -- but
    listing `"BR"` as an arc assignable to a chat would fabricate a door to nowhere: no ember
    shares context with its neighbours, the opposite of what an `E2` `*Produit*` ("an arc shares
    its context") assumes. Filtered HERE, never in `perimetre.py`: `arcs_existants` serves other
    callers for whom "BR" counts.

    **C9: SAME FALLBACK, SAME CONDITION AS `mandat_pour_arc`.** When `arcs` is supplied,
    identity comes from the SUB-PLAN NAMES the caller has already resolved, never rebuilt here by
    prefix — no ember can slip in by accident (a sub-plan is never called `"BR"`), so the
    `_PREFIXE_BRAISE` filter below only applies to the fallback."""
    if arcs is not None:
        return frozenset(nom for nom in arcs.values())

    from .perimetre import arcs_existants
    from .signalements import _PREFIXE_BRAISE

    return frozenset(a for a in arcs_existants(reading) if a != _PREFIXE_BRAISE)


def recouvrement(
    a: Mandat, b: Mandat, *, fichiers_reels: frozenset[str] = frozenset()
) -> frozenset[str]:
    """The items BOTH mandates claim -- empty if `a` and `b` are disjoint.

    **THE ITEM'S LEVEL-2 WITNESS**: *"a mandate that overlaps another batch is refused at
    emission."* This function refuses nothing itself (level 1, this module) -- it renders the SET
    of shared identifiers, and it is up to the caller to refuse if it is not empty. *Publishing
    what is missing is not the same as refusing* also holds for an overlap: name it first.

    **FALSE NEGATIVE PROVEN BY THE ISOLATED AUDIT OF `E4`, FIXED HERE -- NOT IN
    `plan_format.py`.** On the real plan, `plan_format.py` is cited under 3 different spellings
    (bare filename, one folder up, and the full path from repo root) -- compared as-is, none of
    the 3 pairs collide even though it is the SAME file. `chemins_cites_par_produit` deliberately
    refuses to resolve (its own docstring: "neither resolved nor checked on disk") -- resolving is
    therefore the CALLER's responsibility, never the extractor's, exactly like `produit_problems`
    already applies ITS OWN folder filter on top of the same raw extraction. `fichiers_reels` (the
    `git ls-files` namespace, supplied by the caller -- never recomputed here, this module does no
    I/O) resolves each path to its unique match by SUFFIX before comparing; ambiguous or absent ->
    rendered as-is, never fabricated. **Empty by default**: a caller that supplies none gets back
    the exact previous literal behavior -- no existing witness breaks.

    **`plan_ordre.lots()` (E1, NOT my file) asks the SAME question over the same extraction,
    without this resolution -- an analogous gap, named here for the orchestrator, never fixed in a
    file that is not mine** ("one file, one author")."""
    if not fichiers_reels:
        return a.fichiers & b.fichiers
    ra = frozenset(_resoudre_chemin(c, fichiers_reels) for c in a.fichiers)
    rb = frozenset(_resoudre_chemin(c, fichiers_reels) for c in b.fichiers)
    return ra & rb


def _resoudre_chemin(chemin: str, fichiers_reels: frozenset[str]) -> str:
    """The same real file, whatever depth a `*Produit*` cites it at -- resolved by unique SUFFIX
    against `fichiers_reels` (the `git ls-files` namespace). Ambiguous (2+ candidates) or absent (0
    candidates) -> rendered AS-IS, never a fabricated path: a path that resolves nowhere stays
    comparable literally, at worst exactly as well as before this function existed."""
    if chemin in fichiers_reels:
        return chemin
    voulu = PurePosixPath(chemin).parts
    candidats = [f for f in fichiers_reels if PurePosixPath(f).parts[-len(voulu) :] == voulu]
    return candidats[0] if len(candidats) == 1 else chemin


def rendre(
    mandat: Mandat,
    racine: Path,
    base_projet: str | None = None,
    *,
    borne: int | None = None,
) -> str:
    """The mandate's text -- assembled, never drafted. Every line comes from an already-published
    field.

    ``racine`` is WHAT LETS `C4` resolve each item's `*To read*` field references -- the same
    repo the mandate is issued from, never guessed.

    ``base_projet`` (relative to ``racine``) is the PROJECT root this mandate comes from, so that a
    project's own plan can cite its own files relative to itself rather than to the Mnémosyne repo
    -- see the note under :data:`~mnemosyne.production.a_lire._RACINES`, and the defect measured at
    the SECOND adopter that made it necessary.

    ``borne`` — THE CHAT CEILING, AND WHY IT TRAVELS HERE RATHER THAN REFUSING ELSEWHERE.
    Measured on 2026-09-08: ``make orchestration-borne`` returned **3** for the first adopter project, which ran with
    **4 chats + one orchestrator** — and nothing said a word. The reflex ("make that command
    REFUSE") is wrong: it is read-only and **on the path of no gesture at all**. A chat is not born
    from it, it is born from a mandate -- that is to say, from HERE. A door nobody walks through
    guards nothing.
    The ceiling therefore stops being published ONCE to the orchestrator and is instead repeated
    at EVERY birth, in the one text the new chat is certain to read: its own.
    **WHAT THIS DOES NOT DO, STATED RATHER THAN DISCOVERED LATER (A2): this is NOT a barrier.**
    Mnémosyne cannot count LIVE chats — they live in the harness, not in the repo, and nothing here
    can see them. Emitting a 4th mandate under a ceiling of 3 stays entirely possible and is
    refused by nothing. What changes: the 4th chat can no longer ignore it without having read it.
    ``None`` (the default) omits the line -- an unknown ceiling is never invented."""
    lignes = [
        f"# MANDATE — arc {mandat.arc}",
        f"door: {mandat.porte}",
        "",
        f"## Items ({len(mandat.items)}, {len(mandat.ouverts)} open)",
    ]
    for item in mandat.items:
        lignes.append(
            f"  - {item.ident} [{STATUS_LABEL.get(item.status, item.status)}] {item.title}"
        )
    lignes += [
        "",
        rendre_gabarit(mandat.items, racine, base_projet=base_projet),
        "meeting point: the wave -- *\"the meeting point is the wave; the protocol is the "
        "commit\"* (E2, doctrine written into the plan).",
        f"posts contract: {CONTRAT_DES_POSTES} — one file one author · the post is re-read "
        "every turn · acknowledged by fingerprint · work only your own batch (E4, the "
        "contract travels with the mandate, it is never recopied here).",
        # G9 -- PRECEDENCE TRAVELS WITH THE MANDATE, for the SAME reason as the chat ceiling
        # below: an isolated agent reliably reads only ONE text, its own. A rule saying "the repo
        # outranks your prompt" that lives anywhere other than the prompt cannot be known by the
        # one it is meant to protect. ONE home (`production/precedence.py`), cited here, never
        # recopied -- and `runtime/precedence_run.py` refuses a mandate that does not carry it, or
        # that points at a dead address.
        CLAUSE_DE_PRECEDENCE,
    ]
    if borne is not None:
        lignes.append(
            f"chat ceiling for this plan: {borne} — DERIVED "
            "(`min(wave width in arcs, arbitration capacity)`), re-drawable with "
            "`make orchestration-borne POUR=<project>`. \U00002696\U0000FE0F This is a CEILING, never a "
            "requirement: filling a ceiling with no real need costs scaffolding that will have to "
            "be torn down, and coordination is paid for in commits. \U000026D4 Nothing here REFUSES "
            "one more chat — Mnémosyne cannot see live chats; going over is your call to make, "
            "and to write down."
        )
    return "\n".join(lignes) + "\n"


def decouper_mandat(mandat: Mandat, *, taille: int) -> tuple[Lot[PlanItem], ...]:
    """The mandate SPLIT into dispatchable sub-batches (C5) -- delegates to :func:`parc.decouper`,
    never a second split. Over :attr:`Mandat.ouverts` ONLY: an item already `fait`/`clos` has
    nothing left to dispatch to an agent."""
    return decouper(mandat.ouverts, taille=taille)


def rendre_lot(lot: Lot[PlanItem]) -> str:
    """The text of ONE batch -- same discipline as :func:`rendre` (assembled, never drafted,
    already-published fields only), just restricted to this batch's items. This is the text the
    edge writes to disk as an agent mandate (`lot_N_IN.md`)."""
    lignes = [f"# BATCH {lot.indice} ({len(lot.items)} item(s))", ""]
    for item in lot.items:
        lignes.append(f"  - {item.ident} [{STATUS_LABEL.get(item.status, item.status)}] {item.title}")
    return "\n".join(lignes) + "\n"


def assembler_mandat(
    lots: tuple[Lot[PlanItem], ...], lire_sortie: Callable[[Lot[PlanItem]], _T | None]
) -> Assemblage[_T]:
    """Re-reads each batch's OUT (C5) -- delegates to :func:`parc.assembler`, never a second
    completeness check.

    **LEVEL 1, same doctrine as** :func:`recouvrement` **: this function refuses NOTHING, it
    renders `Assemblage.complet` -- it is the edge (`lot_emit_run.py`) that turns
    `complet=False` into a real refusal (a non-zero exit code). *Returning a boolean is not
    refusing*: the lesson from `C5`'s closing audit, applied here rather than merely repeated."""
    return assembler(lots, lire_sortie)
