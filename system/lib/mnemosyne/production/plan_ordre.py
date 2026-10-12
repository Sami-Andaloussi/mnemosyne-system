"""The ORDER of a plan — declared dependencies, named cycles, topological waves, reverse index.

**Mnémosyne had no notion of order at all** (`vague` · `topolog` · `prereq` · `ordonnan`: 0
occurrences in its 5 627 lines of machinery) while another project carries 11 004 lines that already
do the work. This module brings the graph HOME so that project can CALL it instead of owning it — the
pattern is already proven in the other direction, since that project's ``index_des_arcs.py`` calls
``plan_format.index_problems``. *One home, never a copy.*

Nothing here reads a file. It is a pure function over a :class:`~mnemosyne.production.plan_format.
PlanReading`, which is what lets the same code serve ``make plans``, a pre-commit gate, and a
project that folds its own plan.

 **A DEPENDENCY IS READ BY A RULE, NEVER BY A SCAN — and that decision is the whole module.**
The first version of this reading scanned the ``*Dépend de*`` value for any known identifier. It
looked right and it was wrong: ``*Dépend de* : A03-20 — son second membre exige que l'identité de
registre porte SON …`` also mentions other steps in its prose tail, and a scan claims every one of
them. Measured on that project's real plan: **68 links by scan against 28 by rule**, and the 40 extra were
identifiers merely CITED in a sentence. That is the very confusion item ``A1`` exists to end —
*a declaration is not a mention* — one level down.

 **THE GAP WITH THAT OTHER PROJECT IS THE RESULT, not a failure to reproduce.** That project's ``ligne.py`` reports
**234** links; it does not read the field but a *tranche* running to the next label, of which **26
items out of 99 exceed 800 characters**, and it hunts identifiers BY SHAPE inside it. Reproducing
234 would have meant copying that permissive rule — *building this module to reproduce the defect it
exists to replace*. So the gap is PUBLISHED, link by link, with its cause: it measures how many of
that project's "dependencies" are not ones.

 **AN UNREADABLE DEPENDENCY REFUSES; IT NEVER BECOMES A FREE STEP.** This is that project's own most
expensive lesson, written in `ligne.py`: a `& set(connus)` used to drop silently everything it did
not recognise, so *a badly written dependency did not become an error — it became a step with
nothing in front of it*, which is the worst of the two directions. Five sabotages passed green.

Code & docstrings English (D117). Operator-facing prose is French in the source, for the operator
who reads it directly (D33); translated to English throughout this mirror.
"""

from __future__ import annotations

import re
import statistics
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Final, Mapping

from .a_lire import charge_en_octets
from .plan_condition import est_une_commande
from .plan_format import ORDER_REFUSALS as _ORDER_REFUSALS
from .plan_format import PlanItem, PlanProblem, PlanReading, chemins_cites_par_produit

#: The refusals this judge raises. Declared apart, per producer, for the reason
#: :data:`~mnemosyne.production.plan_format.PREREQUISITE_REFUSALS` states: a single tuple mixing
#: producers gets emitted to every project as if one reader raised them all.
#: Re-exported from :mod:`plan_format`, which owns the union every gate reads. ONE home.
ORDER_REFUSALS: Final = _ORDER_REFUSALS

#: A free answer meaning "nothing comes before this". Both genders, because a plan writes
#: ``AUCUNE`` for a dependency and ``AUCUN`` for a prerequisite, and a reader that knew only one
#: would turn half the corpus into an unreadable list.
#: ``RIEN`` is there because the corpus writes it — **6 items from that project**, measured. This is not
#: about being generous: ``*Dépend de*`` has no closed vocabulary (unlike ``*Prérequis*``), so
#: refusing an unambiguous way to say "nothing" would have been a VOCABULARY complaint disguised
#: as a LIST refusal — the message would have accused a loss where there is nothing to lose.
_AUCUN: Final = ("AUCUN", "AUCUNE", "RIEN")

#: DECORATION around an identifier — what an author wraps a key in, on either side. Stripped from
#: the token, NEVER read as the end of the list.
#:
#: **THIS IS THE THIRD DRIFT OF THE SAME LINE, and the first one in the NARROW direction.** The
#: previous rule cut the value at the first ``*`` or `` ` ``, so a list written in bold or code —
#: ``*Dépend de* : **A10-1**, **A10-2**, **A10-3**`` — produced an EMPTY head, **zero refusals**, and
#: the item went straight into wave 1. Measured on that project: **17 declared links lost out of 45**, every
#: one of them pointing at a step that EXISTS. That is word for word the class this module puts in
#: capitals twice — *an unreadable dependency NEVER becomes a FREE step* — and it was silent,
#: which is why twenty witnesses missed it. Twice too wide, once too narrow: *close the CLASS.*
_DECORATION: Final = "*_`\"'«»‘’“”[]()<>"

#: Trailing punctuation that ends a token without ending the list: ``A03-9.`` is one dependency.
_PONCTUATION_FINALE: Final = ".,;:·!?"

#: A parenthesised GLOSS — ``A11-1 (sans lui rien), A10-12 (le catalogue)``. Removed before the walk.
#:
#: **THE FOURTH DRIFT OF THIS LINE, and the second silent one.** A gloss is prose, so the token
#: ``(sans`` ended the list — and everything after it, **including real declared steps, vanished
#: without a single refusal**. Measured on that project: **15 links across 10 items**, more than the third
#: drift cost. The plan's own door writes ``Depend de : A11-1, A10-12.`` for an item this module read
#: as depending on ``A11-1`` alone.
#:
#: Removing the gloss is a RULE, not a scan: whatever it contains is a MENTION by construction —
#: ``A1 (voir aussi A2)`` declares ``A1``, never ``A2``. That is the same doctrine one level down.
_GLOSE: Final = re.compile(r"\([^()]*\)")

#: A token made only of punctuation that OPENS prose — a lone dash, an ellipsis, an arrow. It ends
#: the list, which decoration never does.
_OUVRE_LA_PROSE: Final = frozenset({"—", "–", "--", "→", "\U000025B6", "…", ":"})

#: What SEPARATES two identifiers inside the list. A space is one, which is why the split below is
#: on whitespace and these marks together.
_SEPARATEURS: Final = re.compile(r"[\s,;·+&]+")

#: A word that is a separator spelled out. ``A1 et A2`` is a list in French.
_LIAISONS: Final = frozenset({"et", "and", "puis"})

#: The shape of an IDENTIFIER — letters, then at least one digit: ``A03-6``, ``F2``, ``P11``.
#:
#: **It is NOT the same pattern as** :data:`~mnemosyne.production.plan_format._IDENTITY_RE`, and
#: the comment that said so was false — measured, ``A03-6``, ``A1-2026-08-14`` and ``A1-a-b-c-9``
#: match here and not there (that one caps the suffix and the length). The two answer different
#: questions: that one decides whether a BULLET carries a key, this one whether a token in a list
#: could be one. Naming the divergence rather than claiming a kinship that does not exist.
#:
#: **THIS WAS FIRST WRITTEN AS "ANY WORD", AND THE MEASUREMENT KILLED IT IN ONE RUN.** With
#: ``[A-Za-z][A-Za-z0-9-]*`` the rule read ``*Dépend de* : A03-x pour savoir quels hotes repondent``
#: as SIX dependencies — ``pour``, ``savoir``, ``quels``, ``hotes``, ``repondent`` — and refused them
#: all as unknown. **14 items of that project produced a refusal made entirely of French prose.** A rule
#: that turns a sentence into a list is the same defect as a scan, one level up.
#:
#: **So there are TWO ways to be a dependency, and prose is neither**: a token that names a real
#: step (the POPULATION is the authority — this is what lets that project's ``PEUPLEMENT``, which no shape
#: can match, be a legitimate dependency), or a token SHAPED like an identifier and naming nothing,
#: which is REFUSED by name. Anything else simply ENDS the list: it is the sentence, and a sentence
#: is not a malformed dependency.
_IDENTIFIANT: Final = re.compile(r"[A-Za-z]{1,4}[0-9]+(?:-[A-Za-z0-9-]+)?$")


def lire_liste(valeur: str, connus: frozenset[str] = frozenset()) -> tuple[str, ...]:
    """The identifiers DECLARED at the head of a ``*Dépend de*`` value, in order, verbatim.

 The rule, and it is a grammar rather than a search: walk the tokens from the start; DECORATION
 is stripped off each one (``**A10-1**`` is ``A10-1``), a separator or a French liaison word
 continues the list, and the first token that is neither a known step nor identifier-shaped ENDS
 it. ``AUCUNE`` yields nothing and costs nothing.

 An empty result on a NON-empty value is not "no dependency": :func:`dependances` turns it
 into ``liste_illisible``. Losing it silently is what cost 17 real links.

 ``connus`` is the POPULATION, and passing it is what lets a real step whose name matches no
 shape (that project has one: ``PEUPLEMENT``) be read as the dependency it is. Left empty, only
 identifier-shaped tokens are read — the honest floor for a caller that has no population yet.

 Whether an identifier-shaped token names anything is :func:`dependances`' job, not this one:
 keeping the two apart is what lets an unknown be NAMED rather than vanish between a shape and a
 set intersection.
 """
    trouves: list[str] = []
    for brut in _SEPARATEURS.split(_GLOSE.sub(" ", valeur).strip()):
        if not brut:
            continue
        if brut in _OUVRE_LA_PROSE:
            break
        mot = brut.strip(_DECORATION).strip(_PONCTUATION_FINALE).strip(_DECORATION)
        if not mot:
            continue  # pure decoration between two entries
        if mot.lower() in _LIAISONS:
            continue
        if mot.upper() in _AUCUN:
            break
        if mot not in connus and _IDENTIFIANT.fullmatch(mot) is None:
            break  # a word of prose — the list is over, and a sentence is not a malformed dependency
        trouves.append(mot)
    return tuple(trouves)


def est_une_reponse_gratuite(valeur: str) -> bool:
    """Is this value the free answer — ``AUCUNE`` — however it is decorated?

 **ONE rule, read by BOTH sites, because there were TWO and they disagreed.** The list reader
 stripped decoration; the guard that decides whether to raise ``liste_illisible`` compared the raw
 first five characters. So ``**AUCUNE**`` — six of which the corpus already writes — was REFUSED
 for not declaring a list while saying exactly what the refusal asks for, and ``AUCUNEMENT une
 dépendance`` passed as if it were the free answer. *Two rules for one question, forty lines
 apart, is a contradiction waiting for its first user.*
 """
    for brut in _SEPARATEURS.split(_GLOSE.sub(" ", valeur).strip()):
        mot = brut.strip(_DECORATION).strip(_PONCTUATION_FINALE).strip(_DECORATION)
        if mot:
            return mot.upper() in _AUCUN
    return False


def dependances(reading: PlanReading) -> tuple[dict[str, frozenset[str]], tuple[PlanProblem, ...]]:
    """``({ident: what it waits for}, refusals)`` — the declared graph, and what could not be read.

    Every item gets a key, including one that declares nothing: *two absences of measurement compare
    equal*, and a caller must be able to tell "waits for nobody" from "was never read".

    An identifier that names no item of this plan raises ``dependance_inconnue``. It is not dropped,
    and the reason is measured in that project: dropping made a mistyped dependency into a step with
    nothing in front of it, and five sabotages shipped green behind that silence.
    """
    connus = {item.ident for item in reading.items if item.ident}
    graphe: dict[str, frozenset[str]] = {}
    refus: list[PlanProblem] = []
    for item in reading.items:
        if not item.ident:
            continue  # an item with no identity cannot be waited on, nor wait — `untracked` names it
        valeur = item.field("depend_de") or ""
        declares = lire_liste(valeur, frozenset(connus))
        if item.ident in declares:
            refus.append(
                PlanProblem(
                    item.line,
                    "dependance_sur_soi",
                    f"{item.ident} declares itself dependent on ITSELF — unsatisfiable by"
                    " construction, and erasing it silently would make it a FREE step",
                    item.source,
                )
            )
        if valeur.strip() and not declares and not est_une_reponse_gratuite(valeur):
            # A WRITTEN value from which no list can be drawn is not "no dependency": the head is
            # a sentence. The silence here is exactly what cost 17 links — the item left in wave 1
            # as if it waited on nobody. We NAME it, we do not guess, and above all we do not
            # re-scan the prose to fish identifiers out of it.
            refus.append(
                PlanProblem(
                    item.line,
                    "liste_illisible",
                    f"{item.ident} → « {valeur[:48]} » does not start with a readable list;"
                    " write the identifiers up front, or `AUCUNE`",
                    item.source,
                )
            )
        inconnus = [nom for nom in declares if nom not in connus and nom != item.ident]
        if inconnus:
            refus.append(
                PlanProblem(
                    item.line,
                    "dependance_inconnue",
                    f"{item.ident} → {' · '.join(inconnus)} does not name any step of this plan;"
                    " an unreadable dependency would become a FREE step, which is worse",
                    item.source,
                )
            )
        graphe[item.ident] = frozenset(n for n in declares if n in connus and n != item.ident)
    return graphe, tuple(refus)


@dataclass(frozen=True)
class PlanOrdre:
    """The order of a plan: its waves, what each step unblocks, and what could not be ordered."""

    #: One tuple per wave — everything inside a wave is doable IN PARALLEL. Topological order.
    vagues: tuple[tuple[str, ...], ...]
    #: ``(ident, how many steps it unblocks)`` — the REVERSE index, every ident present.
    deblocages: tuple[tuple[str, int], ...]
    #: The steps that can never be reached, sorted. Empty when the graph is a DAG.
    cycle: tuple[str, ...]
    #: Refusals: unreadable dependencies, and the cycle itself.
    problems: tuple[PlanProblem, ...]

    @property
    def ordonnable(self) -> bool:
        """Is every step reachable? A cycle makes the line unfollowable, so it is never silent."""
        return not self.cycle

    def debloque(self, ident: str) -> int:
        """How many steps ``ident`` unblocks — 0 for one nobody waits on, KeyError for an unknown."""
        return dict(self.deblocages)[ident]


def ordonner(reading: PlanReading) -> PlanOrdre:
    """The waves of a plan, its reverse index, and its cycle if it has one. PURE.

    A wave is what can be worked in parallel: everything whose dependencies are all outside what
    remains. The loop stops when nothing is free, and what remains IS the cycle — **named, never
    raised**. Raising would have made a plan with one bad edge produce no order at all, and a
    surface that shows nothing is indistinguishable from a surface that found nothing.

    ``deblocages`` seeds every identifier at zero on purpose: without the key laid down in advance a
    step nobody waits on would be ABSENT, and a caller would read "no measurement" as "not measured".
    """
    graphe, refus = dependances(reading)
    restant = dict(graphe)
    vagues: list[tuple[str, ...]] = []
    while restant:
        # **THE SET OF REMAINING ITEMS WAS REBUILT FOR EACH ITEM, ON EVERY WAVE** — 76% of the
        # total profiled time (0.097 s of 0.128 s, 1040 calls for 1000 items). The keys view is
        # already SET-shaped: the intersection has the same semantics, without the copy.
        # B6's clause FREEZES the output order: we touch the COST, never the RESULT — the proof
        # is a SET EQUALITY wave by wave, never a timer alone.
        encore = restant.keys()
        libres = tuple(sorted(i for i, d in restant.items() if not (d & encore)))
        if not libres:
            break
        vagues.append(libres)
        for ident in libres:
            restant.pop(ident)

    compte = dict.fromkeys(graphe, 0)
    for attentes in graphe.values():
        for cible in attentes:
            compte[cible] += 1

    cycle = tuple(sorted(restant))
    if cycle:
        refus = refus + (
            PlanProblem(
                0,
                "cycle_de_dependances",
                f"{len(cycle)} step(s) can NEVER be reached — the line does not exist: "
                f"{' · '.join(cycle[:12])}{' …' if len(cycle) > 12 else ''}",
            ),
        )
    return PlanOrdre(
        vagues=tuple(vagues),
        deblocages=tuple(sorted(compte.items())),
        cycle=cycle,
        problems=refus,
    )


@dataclass(frozen=True)
class Lots:
    """One wave SPLIT into subsets that a fan-out can launch without a write collision."""

    #: Each lot is a sorted tuple of identifiers, DISJOINT from the others — no pair WITHIN the same
    #: lot collides. The union of all lots exactly reconstructs the wave received.
    lots: tuple[tuple[str, ...], ...]
    #: ``(a, b, path)`` — EACH pair separated because of a path shared by their ``*Produit*``, one
    #: canonical couple (``a < b``) per shared path. *A lot without its list of exclusions is a lot
    #: nobody can contest* (E1, word for word): contestability wants precision, so a path shared by
    #: two distinct pairs makes TWO lines, never one catch-all string.
    separees: tuple[tuple[str, str, str], ...]


def lots(reading: PlanReading, vague: tuple[str, ...]) -> Lots:
    """Split ``vague`` — a set of identifiers SUPPLIED by the caller, typically the startable ones
 from :func:`file_d_attente` — into DISJOINT subsets a fan-out can launch IN PARALLEL without a
 write collision, plus the pairs that had to be separated and their cause.

 ``vague`` is not derived here — :func:`ordonner` deliberately ignores status (a topological wave
 includes steps already ``done``), and :func:`file_d_attente` already knows how to answer "what
 is startable right now?". A third answer to that question would be the same class of defect as
 the two-home fence ``A7``/``A8`` closed: ``lots`` answers a single question — given THESE
 identifiers, how do we partition them? — and leaves the choice of the wave to the caller, who
 already has it.

 Two steps collide when their ``*Produit*`` cite at least one path in common —
 :func:`~mnemosyne.production.plan_format.chemins_cites_par_produit`, the SAME reader C2 uses to
 judge a ``*Produit*`` (one home, never a second answer to "which paths does this field cite?").
 That is very precisely a "write collision", measured on that project's plan at this arc's opening:
 **17 pairs out of 820 = 2%**.

 **Derived, never declared** (E1, citing that project's own experience): nothing here persists — every
 call re-reads each item's current ``*Produit*``, so a lot never becomes a graveyard someone
 forgets to refresh after a ``*Produit*`` changes.

 A set of lots' rendezvous point has no value of its own worth publishing: it is ALWAYS the end
 of the WHOLE wave, because the next wave may depend on ANY of this one's lots — ``lots``
 partitions for the fan-out, it does not reorder the dependencies already settled by
 :func:`ordonner`.

 **``reading`` bounds what can collide — measured on that project's plan (14 gates, one per arc, NEVER
 merged by :func:`~mnemosyne.production.plan_registry.scan_plans`).** Called gate by gate, this
 module sees 3.3 times fewer collisions than merging the 14 into a single population (78
 separated out of 564 pairs vs 199 out of 6105, comparable rate — **3.3% ≈ 2.2%**): these are not
 different populations diverging, it is that an item from arc 04 and an item from arc 06 are
 NEVER compared if they live in two separate calls. *Two items that do not share a ``reading`` can
 never collide with each other, even if their ``*Produit*`` cite the same file.* To judge a plan
 across its arcs, merge FIRST (``items=tuple(i for porte in portes for i in porte.reading.items)``,
 the same pattern as :func:`merge_plan` one level up) — ``lots`` stays pure and does not do it
 itself, exactly as :func:`dependances` does not merge either.

 **Honest scope, written rather than hidden**: this closes condition **(b)** of the item — the
 overlap of PRODUCTS — the only one derivable from the current format. Condition **(c)**, a
 "serialized home" shared in PRODUCTION (that project's example: ~30 barriers freezing their signature
 into a single ``SITE_CENSUS``, invisible to any reading of the six fields), has NO signal in this
 plan today — no field declares it. *An empty slot is information, not a hole*: it is not
 forgotten, it is named here rather than simulated by a heuristic that would invent a signal that
 does not exist.
 """
    idents = tuple(sorted(set(vague)))
    par_ident = {item.ident: item for item in reading.items if item.ident}
    chemins = {
        ident: frozenset(chemins_cites_par_produit(par_ident[ident].field("produit") or ""))
        for ident in idents
    }

    separees: list[tuple[str, str, str]] = []
    for position, a in enumerate(idents):
        for b in idents[position + 1 :]:
            for chemin in sorted(chemins[a] & chemins[b]):
                separees.append((a, b, chemin))

    collisionne_avec: dict[str, set[str]] = {ident: set() for ident in idents}
    for a, b, _ in separees:
        collisionne_avec[a].add(b)
        collisionne_avec[b].add(a)

    groupes: list[list[str]] = []
    for ident in idents:
        for groupe in groupes:
            if collisionne_avec[ident].isdisjoint(groupe):
                groupe.append(ident)
                break
        else:
            groupes.append([ident])

    resultat = Lots(lots=tuple(tuple(g) for g in groupes), separees=tuple(separees))
    # The PARTITION is verified here, not only in a test — the same discipline as
    # file_d_attente: every identifier of the received wave is in EXACTLY one lot.
    reunion = [i for groupe in resultat.lots for i in groupe]
    assert sorted(reunion) == list(idents), (reunion, idents)
    assert len(set(reunion)) == len(reunion), "an identifier in two lots at once"
    return resultat


#: Why a link exists in one reading and not the other. Written out rather than derived, because each
#: one is a JUDGEMENT about a real difference of rule, and a judgement must be visible.
ECART_CAUSES: Final = {
    "cite_en_prose": "cited in the tranche's prose, never declared as a dependency",
    "hors_champ": "outside the `*Dépend de*` field — the other reader reads a wider tranche",
    "declare_seulement_ici": "declared in the field, invisible to the other reader",
}


def ecart(
    declares: dict[str, frozenset[str]],
    references: dict[str, frozenset[str]],
    items: dict[str, PlanItem],
) -> tuple[tuple[str, str, str], ...]:
    """The links the two readings disagree on — ``(source, cible, cause)``, LINK BY LINK.

 **This is the deliverable, not a diagnostic.** Item ``B1`` was amended the day a measurement
 showed its original condition rested on a false premise: it demanded this module reproduce
 that project's 234 links exactly, on the assumption those were 234 DECLARED dependencies. They are not.
 So the gap is the result — it counts how many of that project's "dependencies" are not ones — and it is
 published as a SET, never as a count, because two counts can match while naming different links.

 The cause is derived from the item's own text, not guessed: a link the other reader has and this
 one does not is ``cite_en_prose`` when the target really appears in the value's prose tail, and
 ``hors_champ`` when it does not appear in the field at all.
 """
    lignes: list[tuple[str, str, str]] = []
    for source in sorted(set(declares) | set(references)):
        mien = declares.get(source, frozenset())
        autre = references.get(source, frozenset())
        valeur = (items[source].field("depend_de") or "") if source in items else ""
        for cible in sorted(autre - mien):
            dans_le_champ = re.search(re.escape(cible) + r"(?![A-Za-z0-9_-])", valeur) is not None
            lignes.append((source, cible, "cite_en_prose" if dans_le_champ else "hors_champ"))
        for cible in sorted(mien - autre):
            lignes.append((source, cible, "declare_seulement_ici"))
    return tuple(lignes)

#: The components a rank COMPOSES from — and the one the format does not carry.
#:
#: **`peremption` is NOT derivable from the six fields**, and saying so is half the item: that project
#: declares it in a HAND-WRITTEN table (`ligne_declare.COUT_DU_DELAI`, 4 items, each with its
#: reason — *"every day without pulling this is a day of vintages no rerun ever rebuilds"*).
#: A plan cannot compute it: it says what the WORLD does while we wait.
#: It therefore enters through the CALLER, and when the caller gives none, :func:`file_d_attente`
#: **NAMES** it as ignored instead of filing it as if it were zero. *A component nobody remembers to
#: name becomes an invisible arbitration.*
COMPOSANTES: Final = ("faisable", "deblocage", "peremption")


@dataclass(frozen=True)
class Rang:
    """One queue head: its rank, and **the written reason** for that rank.

 ``raison`` is not an ornament: the item's ``*Obligation*`` puts it at **level 2** — *a rank
 with no written reason is an invisible arbitration*. A sort that does not say why it sorted asks
 to be trusted, and that is exactly what a plan must never ask.
 """

    ident: str
    rang: int
    raison: str
    debloque: int
    perissable: bool


@dataclass(frozen=True)
class File:
    """The queue, what it could not compose, and **everything it DISCARDED, with the reason**.

 **`ecartes` EXISTS BECAUSE THE FIRST VERSION THREW AWAY INFORMATION THREE TIMES, SILENTLY.**
 An isolated audit measured it on the real corpus:

 * it threw away the **refusals** from :func:`dependances` (``graphe, _refus = …``), so an item
 whose dependency is unreadable entered the queue **FREE**, with a confident reason — ``A06-9``
 at **rank 13 out of 113**. That is word for word the class this module puts in capitals twice
 (*an unreadable dependency NEVER becomes a free step*), reopened one floor up;
 * it threw away non-``a_faire`` statuses — **7 ``in progress`` items from that project**, dependencies
 satisfied, absent from the queue without a word, when ``ready`` is precisely what a human can
 unblock with one gesture;
 * it threw away the **cycle** computed by :func:`ordonner`, of which it used only the count.

 The rule is one, and it replaces the three patches: **nothing leaves the queue without being
 named.** A caller that only displays ``rangs`` will see the same thing as before; a caller who
 wants to know what is missing can read it, and can no longer ignore it by accident.
 """

    rangs: tuple[Rang, ...]
    #: The components no data allowed us to compose. Never empty on principle.
    ignorees: tuple[str, ...]
    #: ``(ident, why)`` — every plan item that is NOT in ``rangs``, and the reason.
    ecartes: tuple[tuple[str, str], ...]

    def __iter__(self):
        """``rangs, ignorees = file_d_attente(...)`` keeps working — the addition is not a break."""
        return iter((self.rangs, self.ignorees))


def file_d_attente(
    reading: PlanReading,
    *,
    faits: frozenset[str] = frozenset(),
    perissables: dict[str, str] | None = None,
    a_faire: frozenset[str] = frozenset({"a_faire"}),
) -> File:
    """The ranked queue, what could not be composed, and **what was discarded** — see :class:`File`.

 The bare topological sort answers "what is doable?". It does not answer "what should we start
 with?", and on that project's plan the gap is measurable: the head moves from ``A01-1`` (first
 alphabetically) to ``A10-12``, which was at **rank 100 of 113**.

 The composition, in this order, and it is motivated:

 1. **perishable first** — what is lost by waiting cannot be recovered; everything else can be.
 2. **then unblocking** — the only component the graph DERIVES.
 3. **then the identifier**, so that two runs of the same plan give the same order.

 **Honest scope of the composition, measured**: of that project's 113 doable items, **only 21** unblock
 something; the **other 92** are broken by the alphabet, i.e. by the same arbitrary sort as
 before. The function does not claim to rank all 113 items — it ranks the 21 the graph can break
 ties for, and says so in the reason given for each of the other 92.

 ``faits`` is passed by the caller rather than read off status, because a dependency can be
 satisfied in ways other than passing ````. **A contradiction between the two is NAMED** in
 ``ecartes``: a ```` item absent from ``faits`` blocks its dependents as if it still had to be
 done, and that is the DEFAULT behaviour of the signature — staying silent about it would make it
 a trap.
 """
    perissables = {} if perissables is None else perissables
    graphe, refus = dependances(reading)
    par_ident = {item.ident: item for item in reading.items if item.ident}
    ordre = ordonner(reading)
    compte = dict(ordre.deblocages)
    # The key is ``(source, line)``, NEVER the line alone: five arcs all have a line 12, and
    # matching by number alone excluded **142 items out of 168** on the first run — an innocent
    # item excluded because a line-number homonym, in an OTHER file, was refused. The absurd
    # figure is what caught it; a wrong key that excludes 3 items would have gone unnoticed.
    lignes_refusees = {(problem.source, problem.line) for problem in refus}

    ecartes: list[tuple[str, str]] = []
    libres: list[str] = []
    for ident, attentes in graphe.items():
        item = par_ident[ident]
        if (item.source, item.line) in lignes_refusees:
            # The core of the defect: WITHOUT this test, the item entered free with a confident
            # reason.
            ecartes.append((ident, "its dependency is REFUSED — it does not become a free step"))
        elif ident in ordre.cycle:
            ecartes.append((ident, "in a CYCLE — this step can never be reached"))
        elif item.status == "fait" and ident not in faits:
            # This reason comes BEFORE the status one, and the choice is motivated: both are
            # true, but this one is ACTIONABLE — it tells the caller that its `faits` is
            # incomplete, so dependents remain blocked for nothing. "The status no longer applies"
            # is accurate and makes nothing happen. *When two reasons are true, the queue publishes
            # the one that can be acted on.*
            ecartes.append((ident, "\U00002705 but absent from `faits` — its dependents remain blocked"))
        elif item.status not in a_faire:
            ecartes.append((ident, f"status « {item.label} » — the question \"can it start?\" no longer applies"))
        elif item.field("prerequis") is not None and not item.startable:
            # **THIRD TIME THIS FUNCTION THROWS AWAY A GUARANTEE FROM ONE FLOOR UP.**
            # `PlanItem` KNOWS that an item whose `*Prérequis*` is not lifted is not startable,
            # and `blocked_by` NAMES who can lift it — `make plans` uses it. The queue did not
            # consult it: measured, an item with `*Prérequis*: THE OPERATOR` came out
            # **startable**, and three items out of four were proposed at rank 1 when **nobody
            # here can start them**. *A queue that proposes what nobody can take costs every chat
            # that reads it a wasted turn, and it looks correct.*
            # The published reason is the item's own — **the judge speaks, not me** — two
            # sentences for the same refusal, and it is the weaker one that ends up read.
            # **AND THE CONDITION BEARS ON THE DECLARED FIELD, NOT ON `startable` ALONE.** First
            # run without this test: **10 tests red at once**, because `startable` is also FALSE
            # when the field is ABSENT — and that project's real corpus declares it nowhere (0 item out
            # of 168). Excluding non-declarers would have **emptied the queue**. This repository
            # had already settled the asymmetry in `plans_run`: *declared and not lifted* gets
            # NAMED, *not declared* gets COUNTED — an absent field is a DECLARATION defect, which
            # the level-2 barrier refuses elsewhere, not a reason to pull the item from the queue.
            ecartes.append((ident, f"prerequisite not lifted — {item.blocked_by}"))
        elif attentes - faits:
            ecartes.append((ident, f"waiting on {' · '.join(sorted(attentes - faits))}"))
        else:
            libres.append(ident)
    # **AN ITEM HAS ONLY ONE REASON TO BE DISCARDED.** Without this test, a ```` item received
    # TWO — "status done" then "absent from `faits`" — for a single situation: **75 entries for 57
    # items**. The count became unreconstructable (111 + 75 = 186 for 168 items), and I published
    # "75 discarded" as if they were items. *A duplicate in a list of reasons is not visible in the
    # list; it is visible in the SUM, and only if someone computes it.*

    libres.sort(key=lambda i: (i not in perissables, -compte[i], i))
    plus_haut = max((compte[i] for i in libres), default=0)
    exaequo = sum(1 for i in libres if compte[i] == plus_haut)

    file: list[Rang] = []
    for position, ident in enumerate(libres, start=1):
        debloque = compte[ident]
        if ident in perissables:
            suffixe = f", and unblocks {debloque}" if debloque else ""
            raison = f"PERISHABLE — {perissables[ident]}{suffixe}"
        elif debloque and debloque == plus_haut and exaequo == 1:
            raison = f"unblocks {debloque} step(s) — THE most unblocking of the remaining doable ones"
        elif debloque:
            raison = f"unblocks {debloque} step(s) — tied with {exaequo - 1} other(s)"
        else:
            raison = "doable, unblocks nothing — the graph cannot break the tie, the alphabet decides"
        file.append(Rang(ident, position, raison, debloque, ident in perissables))

    # SUBSTANCE, not truthiness: a table that names no item of the plan composes nothing.
    # Measured — that project's real table (4 items, none startable) fell exactly into this hole and
    # made the function say "peremption composed" for a strictly unchanged order.
    a_compose = any(r.perissable for r in file)
    ignorees = tuple(
        c for c in COMPOSANTES
        if c == "peremption" and not a_compose
    )
    resultat = File(tuple(file), ignorees, tuple(sorted(ecartes)))
    # The PARTITION is verified here, not only in a test: every plan item is either ranked or
    # discarded ONCE, never both nor twice. That is what makes `len(rangs) + len(ecartes) ==
    # len(items)` true — and therefore reconstructable by anyone who re-reads the figure.
    assert {r.ident for r in resultat.rangs}.isdisjoint(i for i, _ in resultat.ecartes)
    assert len(resultat.rangs) + len(resultat.ecartes) == len(graphe), (
        f"{len(resultat.rangs)} ranked + {len(resultat.ecartes)} discarded != {len(graphe)} items"
    )
    return resultat


# --- C3 · ROUTING — derived from the item, never declared on sight ------------------------------

#: The threshold separating LOW volume and HIGH volume, in bytes.
#:
#: **MEASURED, NOT INVENTED — and on the population that most sorely lacks measurement.**
#: Over that project's 168 REAL plan items, an item's own size (title + detail, the only load derivable
#: where ``*À lire*`` is declared NOWHERE — see below) ranges from 417 to 19 323 bytes, median
#: **2 894**. Rounded to 3 000 to stay a figure one can REMEMBER, not to dodge the measurement — the
#: median is published above so that whoever re-derives the figure sees it.
#: One single threshold serves both volume measures below (``*À lire*`` load OR own size):
#: distinguishing the two would have required a SECOND measurement no real item motivates today.
SEUIL_OCTETS: Final = 3000

#: ``niveau N`` in the ``*Obligation*`` field's text (KNOWN, not required — see plan_format.py).
_NIVEAU_RE: Final = re.compile(r"niveau\s*([123])", re.I)


def _niveau_obligation(item: PlanItem) -> int | None:
    """The level declared by ``*Obligation*`` — ``None`` when the field is absent or unreadable."""
    trouve = _NIVEAU_RE.search(item.field("obligation") or "")
    return int(trouve.group(1)) if trouve else None


def _cognition(item: PlanItem) -> str | None:
    """``"faible"`` / ``"elevee"`` / ``None`` (no evidence either way — abstention).

    C3's question 2 FIRST, and it OVERRIDES question 1 when it answers: an ``*Obligation*`` of
    level 2 or 3 IS, in this plan's already-engraved vocabulary, a barrier that refuses or an
    incapacity — *"changing a RULE"* in the most literal sense the format carries today. Question 1
    NEXT, only if 2 does not decide: :func:`~mnemosyne.production.plan_condition.est_une_commande`
    on ``*Fini quand*`` — the SAME reader as ``C1``, carried over from that project, not reinvented. No
    default: ``None`` when neither answers, rather than an optimistic default — *"no declaration on
    sight"* forbids a default that would decide in place of the absence of proof.
    """
    niveau = _niveau_obligation(item)
    if niveau is not None and niveau >= 2:
        return "elevee"
    if est_une_commande(item.field("fini_quand") or ""):
        return "faible"
    return None


def _volume(item: PlanItem, racine: Path) -> str:
    """``"faible"`` / ``"eleve"`` — the load, in UTF-8 bytes, against :data:`SEUIL_OCTETS`.

 **``*À lire*`` answers a narrower question than "volume": "what to open IN ADDITION to the
 item". Measured on that project: 0 of the 168 items declare it** — the field is an invention of THIS
 plan (C4), never carried over there. Routing would therefore refuse to classify that project's ENTIRE
 wave on this axis, silently, if nothing took over. The relay exists and is named: when
 ``*À lire*`` is absent, the item's OWN size (title + detail — what one MUST READ to execute the
 item ITSELF, a neighbouring but different question) serves as a FLOOR. *An answer to the wrong
 question, named, beats silence on the right one* — and the residue is written here rather than
 discovered: the two volumes do not measure exactly the same thing.

 **AUDIT DELEGATED ON 2026-08-15, TWO RESERVATIONS.** (1) This function NEVER returns ``None``
 — :func:`charge_en_octets` can, but the fallback covers every case where it does, so the VOLUME
 axis never abstains; only the COGNITION axis can make :func:`router` abstain. The signature now
 says so instead of promising a ``None`` the code does not return.
 (2) The two branches measured two UNITS: ``charge.octets`` counts real bytes
 (``stat().st_size``), the fallback counted Python characters (``len()``, CODE POINTS) —
 identical in ASCII, diverging as soon as an accent appears. Measured on that project: **1 item changes
 box** depending on the unit chosen. The fallback now encodes to UTF-8 before counting, to
 compare the same quantity on both sides of the ``if``.
 """
    charge = charge_en_octets(item, racine)
    octets = (
        charge.octets
        if charge is not None
        else len((item.title + "".join(item.detail)).encode("utf-8"))
    )
    return "eleve" if octets >= SEUIL_OCTETS else "faible"


#: The four cells of the two-axis table (decision P7) — published here in code. A duplicate prose
#: copy of this table may exist in this project's own governance docs, which are outside the scope
#: of this public mirror.
CASES: Final = {
    ("faible", "faible"): "sous_agent",
    ("faible", "eleve"): "le_parc",
    ("elevee", "faible"): "sous_agent_capable",
    ("elevee", "eleve"): "le_chat_d_arc",
}


@dataclass(frozen=True)
class Routage:
    """The routing for ONE item — the two axes, and the cell they compose (``None`` if either is missing).

 **Asymmetric, and it is written rather than assumed symmetric**: only ``cognition`` can be
 ``None`` (:func:`_cognition` abstains for lack of proof). ``volume`` never can —
 :func:`_volume` always has a fallback. ``case`` is therefore missing today exactly when
 ``cognition`` is missing, never for ``volume`` alone — audit delegated on 2026-08-15.
 """

    ident: str
    cognition: str | None
    volume: str
    case: str | None


def router(item: PlanItem, racine: Path) -> Routage:
    """Derives ``item``'s cell from its PUBLISHED fields — never a reading of its content.

 **No declaration on sight (C3, word for word)**: both axes are each read off ONE mechanical
 rule (:func:`_cognition`, :func:`_volume`), never off an impression of what the item seems to
 cost. A cell is missing as soon as one axis is missing — ``router`` NEVER guesses the cell from
 a single known axis, or half the table would be a bet disguised as a measurement.
 """
    cognition = _cognition(item)
    volume = _volume(item, racine)
    case = CASES.get((cognition, volume)) if cognition is not None else None
    return Routage(ident=item.ident, cognition=cognition, volume=volume, case=case)


def repartition(items: tuple[PlanItem, ...], racine: Path) -> tuple[dict[str, int], tuple[str, ...]]:
    """``({case: count}, abstentions)`` — C3's ``*Fini quand*``, word for word.

 *"it publishes the split across the four cells and names the items it cannot classify — a
 classification with no list of its abstentions is a classification that lies."* The four keys
 are ALWAYS present, at zero if nothing falls into them — the same principle as
 :attr:`PlanOrdre.deblocages`: a cell absent from the dict would read as "never measured", not
 as "zero".

 **AUDIT DELEGATED ON 2026-08-15 — an item WITHOUT an identifier disappeared from BOTH
 counts.** ``router()`` requires an ident (it has nothing else to publish as a key), but an item
 with no ident is still an item: skipping it silently made ``sum(counts) + len(abstentions) <
 len(items)`` true with no figure saying so — 0/168 on that project today (dormant), but *exactly* the
 class this function exists to close. Named by its line rather than omitted: the partition stays
 true even for the population that has no natural key.
 """
    comptes = dict.fromkeys(CASES.values(), 0)
    abstentions: list[str] = []
    for item in items:
        if not item.ident:
            abstentions.append(f"(no ident, line {item.line})")
            continue
        routage = router(item, racine)
        if routage.case is None:
            abstentions.append(item.ident)
        else:
            comptes[routage.case] += 1
    return comptes, tuple(sorted(abstentions))


@dataclass(frozen=True)
class DureeEtape:
    """The duration of ONE closed step -- or the NAMED reason it cannot be dated (D6).

 *"Two absences of measurement must never compare equal"* (D6, word for word): ``jours`` is
 ``None`` and never falls to ``0`` -- ``raison_absence`` then says PRECISELY which of the two
 dates is missing, never a generic "unknown" that would blur the two halves of the absence. Same
 doctrine as :attr:`Routage.case` and :func:`repartition`'s abstentions.
 """

    ident: str
    ouverture: str | None
    fermeture: str | None
    jours: float | None
    raison_absence: str = ""


def duree_par_etape(
    fermees: tuple[str, ...],
    ouvertures: Mapping[str, str | None],
    fermetures: Mapping[str, str | None],
) -> tuple[DureeEtape, ...]:
    """PURE -- combines ISO 8601 dates already resolved by the caller into durations, in days.

    This function touches NO disk and runs NO command: ``ouvertures`` (date of the first commit that
    touches the item's ``*Produit*``) and ``fermetures`` (date of the commit that closes it) are
    entirely INJECTED -- it is the caller who read ``git log`` (D6: "it is derived, it is not
    declared", the same split as :func:`router`, which also never reads disk).

    ``fermees`` carries the identifiers to date, in the order the result is returned -- the caller
    chooses the population (typically a reading's ``done``/``closed`` items), this function does not
    guess it.
    """
    resultat: list[DureeEtape] = []
    for ident in fermees:
        ouverture = ouvertures.get(ident)
        fermeture = fermetures.get(ident)
        if ouverture is None and fermeture is None:
            resultat.append(DureeEtape(ident, None, None, None, "neither opening nor closing is datable"))
        elif ouverture is None:
            resultat.append(DureeEtape(ident, None, fermeture, None, "opening not datable"))
        elif fermeture is None:
            resultat.append(DureeEtape(ident, ouverture, None, None, "closing not datable"))
        else:
            jours = (datetime.fromisoformat(fermeture) - datetime.fromisoformat(ouverture)).total_seconds() / 86400
            if jours < 0:
                resultat.append(
                    DureeEtape(
                        ident,
                        ouverture,
                        fermeture,
                        None,
                        f"closing ({fermeture}) precedes opening ({ouverture}) -- anomaly",
                    )
                )
            else:
                resultat.append(DureeEtape(ident, ouverture, fermeture, jours, ""))
    return tuple(resultat)


def duree_par_vague(
    vagues: tuple[tuple[str, ...], ...], etapes: tuple[DureeEtape, ...]
) -> tuple[tuple[int, float | None, tuple[str, ...]], ...]:
    """PURE -- ``(wave index, MEDIAN duration of its datable steps, NAMED non-datable ones)``.

    A wave with NO datable step at all returns ``None`` for its median, never ``0`` -- the same
    guard as at the step's own scale: zero days and no measurement must never read the same. An
    identifier from the wave absent from ``etapes`` (still open, so never closed) is neither counted
    nor named here: it is not an absence of measurement, it is a step D6 does not target yet.
    """
    par_ident = {e.ident: e for e in etapes}
    resultat: list[tuple[int, float | None, tuple[str, ...]]] = []
    for indice, vague in enumerate(vagues):
        mesurees = [par_ident[i] for i in vague if i in par_ident]
        datables = [e.jours for e in mesurees if e.jours is not None]
        non_datables = tuple(sorted(e.ident for e in mesurees if e.jours is None))
        mediane = statistics.median(datables) if datables else None
        resultat.append((indice, mediane, non_datables))
    return tuple(resultat)
