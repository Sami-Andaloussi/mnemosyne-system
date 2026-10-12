"""THE OBLIGATION SCALE (workstream "plans" · A2) — how much a capability OBLIGES.

> *"The pattern already exists… but it's not hardcoded. There's a bunch of stuff we've only
> discussed […] we don't oblige it. We need to start obliging things."* — the operator, 2026-08-12.

**A capability without obligation is a wish.** The repo is full of them, and these are
measurements, not impressions: ``make moisson`` never pulled · ``debloque=`` publishes but does
not sort · ``COUT_DU_DELAI`` publishes but does not sort · the rule "three meta rounds in a row
means we go back to the product" written down, and the number got WORSE afterward. This module
gives the **vocabulary** that is missing to talk about it, and the **judge** that says where it is
missing.

## The three levels, and what separates them

* :data:`PUSH` (1) — arrives unsolicited, **refuses nothing**, fail-open.
* :data:`BARRIER` (2) — **refuses** a repo state.
* :data:`INCAPACITY` (3) — we **cannot**.

## THE LEVEL IS THE CALLER'S, NEVER THE CODE'S

This is the central rule of this module, and it is **measured on this repo**:

* ``make memoire`` exits with a nonzero code on a dead link. Its own docstring says the rest:
  *"Wired into the SessionStart hook — where its rc is discarded (fail-open), so there it only
  PRINTS."* An ``rc 1`` that **nobody consumes** refuses nothing: it is a **level 1**.
* ``make test`` is called by ``.githooks/pre-push``, which has the exact shape of a barrier — but
  the repo **has no remote**, so ``git push`` never runs and the hook **never fires**.
  *The net that is never pulled has exactly the appearance of a net.*

So a level **2 or 3 declaration MUST name its mechanism AND its caller**, and :func:`verdict`
refuses one that does not (:attr:`Registre.sans_mecanisme`). This is the deliberate asymmetry, the
same one as in :mod:`mnemosyne.production.arsenal`: **we harden what CLAIMS something**, never
what stays humble. A level 1 has nothing to prove — it already admits it does not bite.

## THIS JUDGE PUBLISHES, IT DOES NOT REFUSE — and it is written in item A2

*"The list is PUBLISHED, never refused (we do not punish what already exists)."* A target
**with no level** is therefore **not** a defect: it comes out in :attr:`Registre.sans_niveau` and
the return code stays **0**. A registry that refused outright would block **almost all** targets
on the day it was born, and a wall installed already full gets bypassed the same day
(``--no-verify``). *The exact count is never written anywhere by hand — it is read in the
output, and it moves with every target added.*

**What IS a defect is a registry that lies to itself**: an entry that names a target that does
not exist (a typo), a level outside the scale, a level 2/3 with no mechanism, a duplicate. Those
are NAMED (``rc 1``) — they block no capability, they fix a table.

## The bijection is the barrier (inherited from ``arsenal``)

The population of targets is **INJECTED** by the caller (:mod:`mnemosyne.runtime.obligation_run`
reads the ``Makefile`` at the edge), never discovered here: *a judge that fetches its own
population can find it empty and return a green.* Here an empty population makes ``fantomes``
full, and the edge refuses (``rc 2``) — "no target" and "no target without a level" must never
read the same.

Decisions: A2 (the scale) · D163 (the address, never the copy) · D92/D100 (propose, never impose)
· invariant 2 (non-destructive). English prose for this mirror (D117); code names stay English.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass

#: The three levels, in increasing order of bite: ``(value, name, what it is)``.
#: Three, not four: one more level is a code edit, hence a review — that is what bounds their
#: number, not an invented ceiling.
NIVEAUX: tuple[tuple[str, str, str], ...] = (
    ("1", "PUSH", "arrives unsolicited, refuses nothing, fail-open"),
    ("2", "BARRIER", "refuses a repo state"),
    ("3", "INCAPACITY", "we CANNOT"),
)

#: The levels that CLAIM something, hence the only ones that must justify themselves. A level 1
#: that explains nothing stays true; a level 2 that explains nothing is unverifiable.
REVENDIQUENT = frozenset({"2", "3"})

#: One line of the obligations registry:
#: ``| `make <target>` | <level> | <mechanism and caller> |``. Emphasis ``*`` marks around the
#: level are tolerated (the table is read by humans BEFORE it is read by this code), and a leading
#: indentation of up to THREE spaces (see below).
#:
#: **NO `\s` IN THIS PATTERN, AND IT IS THE MOST EXPENSIVE FIX OF ITS SHORT LIFE.** `\s`
#: crosses the NEWLINE. With the optional group, a line with two columns no longer disappeared —
#: it **SWALLOWED ITS NEIGHBOUR**: the next line, perfectly well written, dropped out of the
#: registry **without a word**, on an ``rc 0`` with empty ``stderr``. Measured by a second isolated
#: audit, on the REAL registry, a single column removed from `make murs` republished by
#: `make signalements` as "declares no level".
#: **AND THE FIRST AUDIT MISDIAGNOSED IT** ("the 2-column line matched nothing"): I fixed the
#: DESCRIBED CASE and the mechanism stayed intact, with a different victim. *A fix written on
#: someone else's diagnosis must be re-measured against the MECHANISM, not the case.*
#:
#: **THE INDENTATION IS BOUNDED AT 3 SPACES, and that is Markdown's own rule**: from 4 on, it is
#: a CODE BLOCK. My previous tolerance (`[ \t]*`) reopened exactly what :func:`hors_blocs` closes —
#: an indented pedagogical example became a declaration again. *Two clauses of the same fix were
#: forbidding each other.* What falls under this bound is not lost: it is NAMED by
#: :data:`_LIGNE_SUSPECTE`, deliberately wider than this reader.
#:
#: **THE THIRD COLUMN IS OPTIONAL IN THE REGEX, AND THAT IS AN AUDIT FIX.** It used to be
#: mandatory: a line with TWO columns — the most likely mistake for a human filling in a
#: three-column table — matched nothing and **disappeared without a word**, the target then
#: reading as "not declared". Yet that is exactly the shape :attr:`Registre.sans_mecanisme` exists
#: to refuse: the guarantee the document SELLS only bit if the column existed AND was empty.
#: *A silent loss is worse than a loud refusal.* The line is therefore read, with an empty
#: mechanism, and the judge refuses it loudly.
_LIGNE = re.compile(
    r"^ {0,3}\|[ \t]*`make ([a-zA-Z0-9_-]+)`[ \t]*\|[ \t]*\**[ \t]*([^|*\n]*?)[ \t]*\**[ \t]*"
    r"\|(?:[ \t]*([^\n]*?)[ \t]*\|)?",
    re.MULTILINE,
)

#: Any table line that TALKS ABOUT a ``make`` target — the superset of :data:`_LIGNE`.
#:
#: **THIS CLOSES THE CLASS, not a case.** The audit probed nine forms a human naturally writes
#: here; three were silently lost (missing column, indented line, target as a markdown link
#: ``[`make x`](…)``). Two are fixed in :data:`_LIGNE`; the third, and every one nobody has
#: imagined yet, is caught here: a line that LOOKS like a declaration without being one is
#: **NAMED** (:attr:`Registre.illisibles`) instead of being dropped. *You cannot list every form a
#: human will invent; you can refuse to silently lose the ones you do not know how to read.*
#: **WIDER THAN THE READER, ON PURPOSE**: anything with the shape of a table line that mentions
#: a `make` target — including under a `>` blockquote (this very document uses one starting at
#: paragraph 3) and under any indentation. The reader is STRICT, the net is WIDE: that asymmetry
#: is what guarantees an unread form is NAMED rather than lost.
_LIGNE_SUSPECTE = re.compile(
    # Leading HTML tags are tolerated: a line wrapped in a `<table><tr><td>` slipped through the
    # net and was lost IN SILENCE — found by PULLING on the fidelity clause, not by rereading it.
    # The anchor is NOT relaxed for that: requiring a leading `|` (after a quote, indentation, or
    # tags) is what spares ordinary prose, measured unharmed.
    r"^[ \t>]*(?:<[^>\n]+>[ \t]*)*\|.*\bmake\s+([a-zA-Z0-9_-]+)\b",
    re.MULTILINE,
)

#: The OPENING of a closed block: three backticks or tildes (or more), possibly indented. A closed
#: block is stripped BEFORE any reading — this document already carries a ```` ```make ```` block,
#: and a pedagogical example of a table line in it would become a ghost declaration. *An
#: instruction manual must not read like an order.*
_OUVRE_BLOC = re.compile(r"^[ \t]*(`{3,}|~{3,})")


@dataclass(frozen=True, slots=True)
class Declaration:
    """What one capability declares: its level, and — if it claims something — what obliges it.

    ``mecanisme`` is only read for the levels in :data:`REVENDIQUENT`, where it is **mandatory**:
    it names the mechanism **and its caller** ("hook X consumes its rc"). For a level 1 it stays
    free: we do not ask a humble label to defend itself.

    ``niveau`` is kept as **plain text**, never coerced to an integer: ``2 (soon)`` must turn red
    like an unknown level, never silently become a ``2``."""

    cible: str
    niveau: str
    mecanisme: str = ""


@dataclass(frozen=True, slots=True)
class Registre:
    """What the table and the real population owe each other. Everything is NAMED.

    ``sans_niveau`` does NOT enter :attr:`coherent`, and that is A2's own decision: a target
    that declares nothing is **published**, never refused."""

    sans_niveau: tuple[str, ...]
    fantomes: tuple[str, ...]
    niveaux_inconnus: tuple[str, ...]
    sans_mecanisme: tuple[str, ...]
    doublons: tuple[str, ...]
    par_niveau: tuple[tuple[str, tuple[str, ...]], ...]
    illisibles: tuple[str, ...] = ()

    @property
    def coherent(self) -> bool:
        """True when the registry does not lie to itself — indifferent to targets with no level."""
        return not (
            self.fantomes
            or self.niveaux_inconnus
            or self.sans_mecanisme
            or self.doublons
            or self.illisibles
        )

    @property
    def declarees(self) -> int:
        """How many targets carry a VALID level — the only figure that progresses."""
        return sum(len(cibles) for _, cibles in self.par_niveau)


def lire_le_registre(texte: str) -> tuple[Declaration, ...]:
    """The declarations carried by ``OBLIGATION.md``, in the order of the file.

    A PURE function of a text: the document is the **truth** (``.md`` + git, D44), and the code is
    only its reader. No duplicate is dropped here — that is what :func:`verdict` NAMES, because a
    silent deduplication would make the very defect we want to see disappear."""
    return tuple(
        Declaration(cible=cible, niveau=niveau.strip(), mecanisme=(mecanisme or "").strip())
        for cible, niveau, mecanisme in _LIGNE.findall(hors_blocs(texte))
    )


def hors_blocs(texte: str) -> str:
    """The document WITHOUT its closed blocks — a pedagogical example is not a declaration.

    **WALKED LINE BY LINE RATHER THAN BY REGEX, AND THAT IS AN AUDIT FIX.** The regex version
    closed on a **backreference**, so it required a closing fence of EXACTLY equal length.
    CommonMark says no such thing, and the measurement named three cases where the block was NOT
    stripped: a longer closer (``` opens, ```` closes), a 4-backtick fence closed by 5, and a fence
    **never closed**. In all three, the pedagogical example became a **REAL declaration**,
    ``rc 0``, without a word — and :func:`lignes_illisibles` could not catch it, since the line
    IS readable.

    *This was the last place this document could lie in silence, and it lied in the OPPOSITE
    direction from the first defect: it MANUFACTURED a declaration instead of losing one.*

    The rule applied is CommonMark's: the closer uses the same character and is **at least as
    long** as the opener; an unclosed fence runs to the end of the document.
    """
    dehors: list[str] = []
    fence = ""
    for ligne in texte.splitlines():
        ouverture = _OUVRE_BLOC.match(ligne)
        if not fence:
            if ouverture:
                fence = ouverture.group(1)
            else:
                dehors.append(ligne)
        elif (
            ouverture
            and ouverture.group(1)[0] == fence[0]
            and len(ouverture.group(1)) >= len(fence)
        ):
            fence = ""
    return "\n".join(dehors) + "\n"


def lignes_illisibles(texte: str) -> tuple[str, ...]:
    """The lines that TALK ABOUT a ``make`` target without being readable as a declaration.

    This is the silent-loss safety net: the difference between what a human believes they
    declared and what :func:`lire_le_registre` actually managed to read. Returns the lines
    THEMSELVES, not their count — a line gets fixed, a count does not.
    """
    propre = hors_blocs(texte)
    lues = {ligne.strip() for ligne in propre.splitlines() if _LIGNE.match(ligne)}
    return tuple(
        ligne.strip()
        for ligne in propre.splitlines()
        if _LIGNE_SUSPECTE.match(ligne) and ligne.strip() not in lues
    )


def verdict(
    cibles: Iterable[str],
    declarations: Iterable[Declaration],
    illisibles: Iterable[str] = (),
) -> Registre:
    """PURE judge — the population of targets is INJECTED, never discovered here."""
    reelles = frozenset(cibles)
    table = tuple(declarations)
    noms = [d.cible for d in table]
    connus = frozenset(noms)
    echelle = frozenset(valeur for valeur, _, _ in NIVEAUX)
    return Registre(
        sans_niveau=tuple(sorted(reelles - connus)),
        fantomes=tuple(sorted(connus - reelles)),
        niveaux_inconnus=tuple(sorted({d.cible for d in table if d.niveau not in echelle})),
        sans_mecanisme=tuple(
            sorted({d.cible for d in table if d.niveau in REVENDIQUENT and not d.mecanisme})
        ),
        doublons=tuple(sorted(nom for nom, combien in Counter(noms).items() if combien > 1)),
        illisibles=tuple(illisibles),
        par_niveau=tuple(
            (
                valeur,
                tuple(
                    sorted({d.cible for d in table if d.niveau == valeur and d.cible in reelles})
                ),
            )
            for valeur, _, _ in NIVEAUX
        ),
    )


def rendre(r: Registre, total: int) -> str:
    """The page: what is declared, then — by name — what is not.

    The order is deliberate: **the levels first** (what the repo TRULY obliges today), **the
    no-level targets after**. The reverse would make the long list of undeclared targets read as
    a reproach, when it is really the assumed starting state.
    *No count here: the "90" that lived in this sentence survived a commit that claimed to have
    purged every hand-written count — found by a second isolated audit. The real value was
    **77 as of 2026-08-14, 10pm** — and 78 a few hours later, one target having been added in the
    meantime. A number inside prose never re-measures itself: it gets DATED, or it does not get
    written — the sentence that removed the counts had just written a new one, already stale.*"""
    lignes: list[str] = ["# The obligation scale — what each capability truly OBLIGES", ""]
    for valeur, nom, quoi in NIVEAUX:
        portees = dict(r.par_niveau).get(valeur, ())
        lignes.append(f"## Level {valeur} · {nom} — {quoi}")
        lignes.append(
            "  " + ", ".join(f"`make {c}`" for c in portees) if portees else "  (none declared)"
        )
        lignes.append("")
    lignes.append(
        f"{r.declarees} target(s) declare a level out of {total} documented in the Makefile."
    )
    if not r.sans_niveau:
        lignes.append("No target without a level: the population is entirely declared.")
        return "\n".join(lignes) + "\n"
    lignes += [
        "",
        f"## \U000025B6 {len(r.sans_niveau)} target(s) declare NO level at all — published, never refused",
        "",
        "  " + ", ".join(f"`{c}`" for c in r.sans_niveau),
        "",
        "This is not a fault: it is the starting state. Declaring a level happens in the registry",
        "in the obligations registry — and a level 2 or 3 must NAME its mechanism AND its",
        "caller there, or it is refused.",
    ]
    return "\n".join(lignes) + "\n"


# --------------------------------------------------------------------------------------------
# `G4` — THE SAME QUESTION, ASKED OF A DIFFERENT POPULATION: plan items, not `make` targets.
# --------------------------------------------------------------------------------------------
#
# **DO NOT CREATE A SECOND HOME, NOTHING JUSTIFIES IT** — `C1` just closed with
# `plan_condition.py`
# declaring "level 2" while carrying **zero** callers outside witnesses, while this very registry
# published "none declared" without ever having looked at the ITEM population. The rule that was
# missing is already written above, word for word, since `A2`: *"the level is the CALLER's,
# never the code's"*. What was missing was not a new rule, it was a SECOND POPULATION to apply it
# to — hence the same LEVELS, the same doctrine, a second (Declaration, verdict) pair because the
# SHAPE of the two populations differs (a `make` target carries a name and a table line; a plan
# item carries an `*Obligation*` field in free prose and a `*Produit*` field that does not always
# identify a single Python module).


@dataclass(frozen=True, slots=True)
class DeclarationItem:
    """What one PLAN item declares, and what the edge has already measured for it.

    **``module`` AND ``appelants`` ARE INJECTED, NOT RECOMPUTED HERE** — same doctrine as the
    rest of the module: *a judge that fetches its own population can find it empty and return a
    green.* Extracting the module from the free-text `*Produit*` field, and the AST count of real
    callers, both live at the edge (``runtime/obligation_run.py``), which touches disk.

    ``module is None`` is a third state, not a refusal: the `*Produit*` field does not always name
    a single, unambiguous `.py` file (measured on the real population: **4 items out of 29**
    level-2 ones do — the other 25 describe a document, a field, a hook, a container).
    *A mechanism that forces a verdict on what it could not identify manufactures an answer.*
    """

    ident: str
    niveau_2_ou_plus: bool
    module: str | None = None
    appelants: int | None = None
    #: **AUDIT DEFECT (D5b): "NAMES NO MODULE" WAS FALSE FOR AN ITEM THAT NAMES ONE CLEARLY,
    #: NOT YET BUILT.** `C5` cites `` `production/parc.py` `` unambiguously — the file simply does
    #: not exist yet. Conflating it with an item that names NOTHING (a document, a field, a hook)
    #: manufactures a false sentence: this one NAMED its target, that one named nothing.
    #: `module_non_construit` carries the cited name when `module` is `None` BECAUSE the file does
    #: not exist yet — the two causes no longer share a single bucket.
    module_non_construit: str | None = None


@dataclass(frozen=True, slots=True)
class RegistreItems:
    """The verdict over the item population — same doctrine as :class:`Registre`: everything is
    NAMED, nothing is counted without the list that composes it staying readable."""

    cablees: tuple[str, ...]
    sans_appelant: tuple[str, ...]
    non_verifiables: tuple[str, ...]
    hors_scope: tuple[str, ...]
    #: Audit D5b: distinct from ``non_verifiables`` — this item NAMED an unambiguous `.py`
    #: module, it simply does not exist on disk yet. ``(ident, module_cite)``.
    non_construits: tuple[tuple[str, str], ...] = ()

    @property
    def coherent(self) -> bool:
        """True when NO item declares a barrier that nothing calls.

        ``non_verifiables`` does **not** enter this property — the same choice A2 made for
        ``sans_niveau``: an item whose module cannot be identified has not LIED, it described a
        product this mechanism cannot yet read. Naming it is enough; refusing it would build a
        wall on a READING limit, not a factual gap."""
        return not self.sans_appelant

    @property
    def total_juge(self) -> int:
        return (
            len(self.cablees)
            + len(self.sans_appelant)
            + len(self.non_verifiables)
            + len(self.non_construits)
        )


def verdict_items(items: Iterable[DeclarationItem]) -> RegistreItems:
    """PURE judge — items, modules, and caller counts are all INJECTED."""
    cablees, sans_appelant, non_verifiables, hors_scope = [], [], [], []
    non_construits: list[tuple[str, str]] = []
    for it in items:
        if not it.niveau_2_ou_plus:
            hors_scope.append(it.ident)
        elif it.module is not None:
            if (it.appelants or 0) >= 1:
                cablees.append(it.ident)
            else:
                sans_appelant.append(it.ident)
        elif it.module_non_construit is not None:
            non_construits.append((it.ident, it.module_non_construit))
        else:
            non_verifiables.append(it.ident)
    return RegistreItems(
        cablees=tuple(sorted(cablees)),
        sans_appelant=tuple(sorted(sans_appelant)),
        non_verifiables=tuple(sorted(non_verifiables)),
        hors_scope=tuple(sorted(hors_scope)),
        non_construits=tuple(sorted(non_construits)),
    )


def rendre_items(r: RegistreItems) -> str:
    """`G4`'s page: what is wired, then — named, never counted alone — what is not.

    *No count is hand-written in the prose*: `total_juge`, like `declarees` for the other
    registry, is read off the object, never written twice."""
    lignes = [
        f"obligations_cablees={len(r.cablees)}/{r.total_juge} "
        f"(level >= 2 with an identified module and >= 1 real caller outside witnesses)",
    ]
    if r.cablees:
        lignes.append("  " + ", ".join(r.cablees))
    if r.sans_appelant:
        lignes += [
            "",
            f"\U000026D4 {len(r.sans_appelant)} item(s) declare level >= 2 with NO real caller AT ALL — "
            "barrier announced, nothing bites:",
            "  " + ", ".join(r.sans_appelant),
        ]
    if r.non_construits:
        lignes += [
            "",
            f"\U000023F3 {len(r.non_construits)} item(s) NAME a `.py` module that does not exist yet "
            "— not 'unverifiable', simply not yet BUILT:",
            "  " + ", ".join(f"{i} ({m})" for i, m in r.non_construits),
        ]
    if r.non_verifiables:
        lignes += [
            "",
            f"\U000026A0\U0000FE0F {len(r.non_verifiables)} item(s) at level >= 2 whose *Produit* names no "
            "identifiable `.py` module — NOT VERIFIABLE, not assumed good:",
            "  " + ", ".join(r.non_verifiables),
        ]
    if r.hors_scope:
        lignes.append(f"\n{len(r.hors_scope)} item(s) below level 2 — outside what is judged here.")
    return "\n".join(lignes) + "\n"


def rendre_les_incoherences(r: Registre) -> str:
    """The only things this judge REFUSES: a registry that lies to itself. Each cause named."""
    causes = (
        (r.fantomes, "entry(ies) naming a target that does not exist (a typo)"),
        (
            r.niveaux_inconnus,
            f"level(s) outside the scale (expected: {', '.join(v for v, _, _ in NIVEAUX)})",
        ),
        (r.sans_mecanisme, "level 2/3 that NAMES neither mechanism nor caller — unverifiable"),
        (r.doublons, "target(s) declared twice"),
        (
            # THE LABEL NO LONGER ASSERTS A LOSS THAT DOES NOT HAPPEN. It used to say "they
            # would be LOST IN SILENCE" — but they are RIGHT HERE, named. The audit named the most
            # likely victim: the table of the three LEVELS, which cites `make tick` as an example
            # and declares nothing. The refusal sent people to fix a CORRECT line. *A refusal
            # whose label is false for its own victim is the first step toward an `rc 1` people
            # learn to ignore.*
            r.illisibles,
            "table line(s) that talk about a target without being readable as a DECLARATION — "
            "nothing is lost, they are named right here: fix the shape, or take the line out of "
            "a table if it declares nothing",
        ),
    )
    # ALL present causes are rendered, never the first alone: a registry with two faults where
    # only one is named sends people to fix, come back, and find red again. Each cause is on its
    # own line, PRECEDED BY ITS LABEL — an audit showed that a test asserting only the target's
    # name let the labels swap without any test turning red.
    return "\n".join(
        f"  - {quoi} : {', '.join(f'`{c}`' for c in cibles)}" for cibles, quoi in causes if cibles
    )
