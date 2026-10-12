"""plan-nouveau — make a plan that is a FOLDER be born CONFORMANT, rather than repaired later.

The repo already knew how to REPAIR (``plan_convert`` turns a monolith into a folder) and how to
JUDGE (the pre-commit barrier, ``make plans``). It did not know how to GIVE BIRTH: the only skeleton
that existed, :func:`~mnemosyne.production.plan_format.plan_skeleton`, returns a SINGLE FILE — the
very shape D166 replaced for a plan that grows. So every folder-shaped plan of this repo had to be
converted into existence, and a plan born by hand was born wrong.

A PURE module: it computes bytes and refusals, it opens nothing and writes nothing. The side effects
live in :mod:`~mnemosyne.runtime.plan_new_run`, exactly as ``plan_convert`` / ``plan_converter_run``
already split. Three properties are the whole design:

* **Nothing about the FORM is authored here.** The index line comes from
 :func:`~mnemosyne.production.plan_convert.index_entry`, the file name from
 :func:`~mnemosyne.production.plan_archive.slugify`, the statuses from
 :data:`~mnemosyne.production.plan_format.STATUS_LABEL`, the door / arc file names from
 ``PLAN_FILENAME`` / ``ARCS_DIRNAME``. D170 was paid for exactly this: the separator set had been
 DERIVED from what the tool writes, and scored twelve on twelve against the tool and two on ten
 against a human. A second expression of the entry shape would re-open that class the same day.
* **The reader gives the verdict, never this module.** :func:`verify_readability` folds the bytes
 that WOULD be written the way ``read_plan_tree`` and the pre-commit hook fold a real plan
 (``read_plan`` + ``merge_plan`` + ``index_problems`` + ``is_readable``) and raises. A producer that
 grades its own output is the failure this repo has already measured (D75); here the grading is
 simply delegated to the code that will judge the commit.
* **It refuses rather than overwrites** (inv. 2). Ten named refusals, each naming a gesture in
 :mod:`~mnemosyne.runtime.plan_new_run`. Birth is the one moment where "I'll fix it after" is
 cheapest and worst: the file that gets overwritten is the one somebody was working in.

 **A NESTED PLAN THAT NOBODY INDEXES IS BORN ORPHAN.** ``read_plan_tree`` hands the outer door
both its arcs AND its nested doors (``plan_entries``), so a sub-plan created under an existing
plan's ``plan/`` and not named by its parent is ``arc_hors_index`` — the barrier refuses the commit.
A birth that produces an orphan is a broken birth, so the parent's index entry is part of the SAME
planning, or the whole thing is refused (``porte_parente_illisible``).

 **A6 ADDS A SECOND KIND OF CONTENT, AND IT MUST NEVER JOIN THE FIRST.** Everything above is the
FORM — niveau 2, judged by :func:`verify_readability`, refusable. :data:`METHOD_QUESTIONS` and
:func:`method_skeleton` are the THINKING — niveau 1 (internal governance notes, not in this
mirror), printed by ``make plan-emit`` alongside the form but read by NOTHING in this module or in
the reader. A question that gained a refusal would be exactly the rigid template the user refused:
*"show what kind of thinking is needed, and NOT EXACTLY — otherwise it locks people in, boxes them
in, and suffocates them"*.

Code, docstrings and everything printed are English (D117); only the plan-format tokens the reader
parses (the field names, the prerequisite vocabulary) keep their canonical spelling.
"""

from __future__ import annotations

import re
import textwrap
from dataclasses import dataclass
from typing import Final

from .arsenal import TITRE_DECLARATION
from .plan_archive import slugify
from .plan_convert import index_entry
from .plan_registry import PROJECTS_DIRNAME
from . import livrables
from .plan_format import (
    ARCS_DIRNAME,
    DOOR_FILENAMES,
    PLAN_FILENAME,
    ROLE_PLAN,
    PlanReading,
    declared_paths,
    fold_plan,
    index_problems,
    is_readable,
    live_lines,
    read_plan,
    unreadable_reasons,
)

__all__ = [
    "DEFAULT_ARC_TITLE",
    "DEFAULT_CAP",
    "DEFAULT_ITEM",
    "METHOD_QUESTIONS",
    "PLAN_CONTRACT_TEMPLATE",
    "REFUSAL_LABEL",
    "ArcDraft",
    "MethodQuestion",
    "ParentDoorUnreadable",
    "ParentUpdate",
    "ScaffoldMismatch",
    "ScaffoldPlanning",
    "ScaffoldRefusal",
    "arc_ident",
    "arc_skeleton",
    "blinding_characters",
    "door_skeleton",
    "index_is_visible",
    "method_skeleton",
    "owning_parent",
    "plan_scaffold",
    "verify_readability",
]


#: The cap a scaffolded door carries when none is given — the SAME placeholder ``plan_skeleton``
#: hands a single-file plan, so the two doors of this repo speak with one voice. It is readable
#: (``**Cap** :`` is present), which is the point: a plan is born conformant, and naming the cap
#: for real is the first thing its author does, not a gate that stops the scaffold from existing.
DEFAULT_CAP: Final = "(what we are trying to obtain right now, in one line)"

#: The first arc's title when none is given. A plan with no arc at all would be a plan with no item,
#: which the reader calls UNREADABLE — so the floor of the folder form is one door plus one arc.
DEFAULT_ARC_TITLE: Final = "Foundation"

#: The first item of a scaffolded arc. An arc with zero items is not readable AS AN ARC
#: (``readable_as_arc``), so this placeholder is structural, not decorative.
DEFAULT_ITEM: Final = "(the first item)"

#: Longest slug kept for an arc file name — the same ceiling ``plan_archive.slugify`` already applies
#: to an archive name, reached through that function so there is one answer to "what is this file
#: called".
_MAX_ARCS: Final = 26 * 27  # A1 … Z1, AA1 … ZZ1 — the identity alphabet below, and nothing beyond


#: Every refusal this module can name, and what triggered it. Declared as a mapping for the same
#: reason ``plan_convert.REFUSAL_LABEL`` is: the runtime layer keys its GESTE table on these tokens,
#: so a refusal added here without a gesture raises a ``KeyError`` at the surface instead of printing
#: a problem nobody can act on. A refusal that names a problem without naming a gesture turns a tool
#: into an obstacle.
REFUSAL_LABEL: Final = {
    "chemin_manquant": "no path given — where a plan must be born is not guessed",
    "racine_du_depot": "the path designates the repo ROOT — a plan is not born there",
    "hors_depot": "the path leaves the repo root",
    "profondeur_projet": "the path is neither at a project's depth (`projects/<bubble>/"
    "<project>`) nor a recognised sub-plan — `scan_projects` will NEVER see it as a project",
    "chemin_occupe": "the path already exists and is not a folder",
    "dossier_des_arcs": "the path IS the `plan/` folder of an existing plan, not a sub-folder",
    "plan_existe": "a plan door already lives there — nothing is ever overwritten (inv. 2)",
    "arc_existe": "an arc file to be written already exists — nothing is ever overwritten (inv. 2)",
    "collision_de_nom": "two requested arcs give the same file name",
    "arc_sans_titre": "an arc was requested with no title",
    "nom_manquant": "the plan has no name, and the folder gives none",
    "texte_multiligne": "a given text spans several lines — a door is read line by line",
    "texte_declare_un_chemin": "a given text contains a `plan/….md` reference: the reader would"
    " read it as an index entry, and the entry would designate a file that does not exist",
    "porte_parente_illisible": "the parent plan cannot receive this sub-plan's index entry",
    "chemin_non_indexable": "the PATH carries a character the index reader cannot read:"
    " this sub-plan's entry in the parent door would be INVISIBLE",
    "squelette_illisible": "the reader REFUSES the bytes that were about to be written",
}


class ScaffoldMismatch(RuntimeError):
    """The reader refused the bytes this module was about to write. Nothing is written.

 Deliberately an exception rather than a returned refusal: it is the LAST gate, after every
 declared refusal has passed, and it means the scaffold and the reader have drifted apart. That is
 a defect in this module, not a mistake by the caller — the two must not be reported in the same
 voice.

 **AND THAT VOICE WAS LYING, on at least three ordinary inputs.** ``--arc "Foundation —
 plan/ghost.md"``, ``--nom "plan/other.md"`` and a multi-line ``--cap`` all reached this
 exception and were reported as *"a defect of Mnemosyne, not a mistake in your request"*, sending
 the caller to ``make signaler`` — a false report filed in the user's queue, and no plan — when one
 word of their own input was the whole problem. Everything a CALLER can put wrong is now a named
 refusal above, checked before the reader is ever asked. What is left here is what the name says:
 the scaffold and the reader have drifted, and nobody typed anything wrong.
 """


class ParentDoorUnreadable(ScaffoldMismatch):
    """The PARENT plan was already unreadable BEFORE this birth — repair it, then come back.

    Split out of :class:`ScaffoldMismatch` for the same reason as above, one level up: a parent door
    carrying an unclosed fence, an un-indexed arc or no cap makes the merged reading refuse, and
    blaming Mnemosyne for it is the same false accusation with a bigger blast radius. The
    discrimination is not a guess — the parent is folded TWICE, once in the state it is already in
    and once in the state this birth would leave it in. Already broken → this. Broken by the entry
    we add → :class:`ScaffoldMismatch`, and that one really is ours.
    """


@dataclass(frozen=True, slots=True)
class ScaffoldRefusal:
    """One named reason the scaffold will not happen — the token, and what it landed on."""

    reason: str
    detail: str

    @property
    def label(self) -> str:
        """The sentence for this token. Raises on an unknown token, rather than defaulting."""
        return REFUSAL_LABEL[self.reason]


@dataclass(frozen=True, slots=True)
class ArcDraft:
    """One arc file that would be written: where it sits, what it is called, and its bytes.

    ``member`` is relative to the DOOR's folder (``plan/foundation.md``) — the same namespace
    :attr:`~mnemosyne.production.plan_format.PlanItem.source` and ``merge_plan``'s ``parts`` use.
    Two namespaces for one path is how the reader and the barrier drifted apart once already.
    """

    member: str
    title: str
    ident: str
    text: str


@dataclass(frozen=True, slots=True)
class ParentUpdate:
    """The index entry a NESTED plan owes its parent — the door's path, its new bytes, the line.

    ``member`` is the nested door relative to the PARENT's folder (``plan/theories/PLAN.md``), which
    is exactly the string ``plan_entries`` returns as a nested door and ``index_problems`` demands to
    find named. Written as ONE string, threaded everywhere, for the reason ``merge_plan`` now
    enforces on arcs: two expressions of one path drift.
    """

    folder: str
    door_name: str
    member: str
    entry: str
    text: str
    #: The parent door's bytes BEFORE the entry — kept so the parent can be judged in the state it
    #: was ALREADY in. Without it "the parent is unreadable" and "we made the parent unreadable"
    #: are one verdict, and the first one is not our fault to confess.
    before: str = ""


@dataclass(frozen=True, slots=True)
class ScaffoldPlanning:
    """Everything the scaffold WOULD write, plus every reason it will not. Nothing is written yet.

    The dry run prints this object and the applied run replays it: one computation, two consumers,
    so what the user reads is what lands. ``blocked`` is checked BEFORE the proof in the runtime layer —
    printing a byte-for-byte preview of a scaffold that is refused buries the refusal under it.
    """

    folder: str
    project: str
    cap: str
    door_name: str
    door_text: str
    #: G1, half of NIVEAU 2: the `LIVRABLES.md` a NEW plan receives. On an EXISTING plan the clause
    #: publishes and never refuses (17 doors measured, a single list); at BIRTH there is nothing
    #: to punish, so the template is written in advance and the author STARTS with the list. A
    #: sub-plan does not get one: the command belongs to the PROJECT, not to one of its arcs.
    livrables_name: str = ""
    livrables_text: str = ""
    arcs: tuple[ArcDraft, ...] = ()
    parent: ParentUpdate | None = None
    refusals: tuple[ScaffoldRefusal, ...] = ()
    #: FOUND BY AN AUTONOMY PROBE (D75, 2026-08-17), NOT BY AN AUDIT: the `format_declare`
    #: RECEIVED, exactly as TYPED by the caller -- ``""`` if nothing was passed, EVEN when a
    #: sub-plan then INHERITS from the parent (:func:`plan_scaffold`). Distinct from what
    #: `door_text` ends up DECLARING: the inherited value and the explicit one can produce the
    #: SAME door text while being two different answers to "what did the caller actually receive?".
    #: Used SOLELY to reconstruct a faithful replay command (`plan_new_run.render`) -- replaying
    #: `""` lets the inheritance reproduce IDENTICALLY on the second call (same parent, same disk);
    #: replaying an explicit value FREEZES it, so an explicit choice is never silently overwritten
    #: by an inheritance at the moment of the REAL `APPLY=1`.
    format_arg: str = ""

    @property
    def blocked(self) -> bool:
        """Is anything refused? ONE refusal blocks the WHOLE scaffold — a birth is not partial."""
        return bool(self.refusals)

    @property
    def door_path(self) -> str:
        """The door's path from the repo root — ``""`` folder means the repo root itself."""
        return f"{self.folder}/{self.door_name}" if self.folder else self.door_name

    def arc_paths(self) -> tuple[str, ...]:
        """Every arc file's path from the repo root, in the order they would be written."""
        return tuple(
            f"{self.folder}/{arc.member}" if self.folder else arc.member for arc in self.arcs
        )


def arc_ident(index: int) -> str:
    """The identity of the FIRST item of the ``index``-th arc — ``A1``, ``B1``, … ``AA1``.

    One LETTER per arc rather than one number per arc, and that is not cosmetic: identities are
    unique across the whole plan FOLDER (``id_duplique``, D166 clause 5), so an author extending the
    second arc writes ``B2``, ``B3`` inside its own namespace and cannot collide with the third arc's
    ``C2``. Numbering the arcs ``A1``, ``A2``, ``A3`` instead would have handed every author a
    collision on their second item — a defect the scaffold would have CAUSED, on the edit right after
    the one it made easy.

    Stays inside :data:`~mnemosyne.production.plan_format._IDENTITY_RE`'s shape (one to four letters
    then digits), so the item is READ rather than refused as ``identite_illisible``.
    """
    if index < 0:
        raise ValueError(f"negative arc index: {index}")
    letters = ""
    count, remainder = divmod(index, 26)
    if count:
        letters += chr(ord("A") + count - 1)
    letters += chr(ord("A") + remainder)
    return f"{letters}1"


def _title_line(project: str) -> str:
    """The door's first line. ONE expression, because two lines must be judged with the SAME shape.

    :func:`door_skeleton` writes it and :func:`_text_refusals` judges what a caller puts INTO it. A
    second copy here would be the class D170 was paid for, one field smaller.
    """
    return f"# PLAN — {project}"


def _cap_line(cap: str) -> str:
    """The door's cap line — same reason as :func:`_title_line`: written once, judged once."""
    return f"> **Cap** : {cap}"


def _format_line(format_declare: str) -> str:
    """The door's optional Format line — same reason as :func:`_title_line`: written once, judged
    once. Empty ``format_declare`` never calls this: :func:`door_skeleton` omits the line entirely
    rather than writing ``> **Format** : `` (D176 — a plan that declines to declare owes nothing,
    not even an empty promise)."""
    return f"> **Format** : {format_declare}"


def index_is_visible(member: str, title: str) -> bool:
    """Would the READER see the index entry a door writes for ``member``? Asked of the judge itself.

 ``member`` is relative to the door (``plan/the-offer/PLAN.md``). The entry is built by the one
 expression that writes it (:func:`~.plan_convert.index_entry`) and handed to
 :func:`~.plan_format.index_problems`, i.e. literally the function the pre-commit barrier runs. A
 predicate written here as a character class would be a SECOND rule about what a path may contain,
 free to drift from the one that judges the commit — and drifting rules is what every audit of
 this arc has found.

 **THIS IS THE QUESTION NOBODY ASKED ABOUT THE PATH.** ``--nom``, ``--cap`` and ``--arc`` were
 filtered; ``CHEMIN`` — the value the user types most — went into the parent's index entry
 verbatim and was filtered by nothing. Three ordinary French folder names out of seven
 (``l'offre``, ``rapports (200)``, ``phase 2, data``) therefore reached the LAST gate and were
 reported as *"a defect of Mnemosyne, not a mistake in your request"*, with a report filed in
 the user's queue and no plan written.
 """
    relative = member[len(ARCS_DIRNAME) + 1 :] if member.startswith(f"{ARCS_DIRNAME}/") else member
    return not index_problems(index_entry(member, title), (relative,), folder_form=True)


def blinding_characters(member: str) -> tuple[str, ...]:
    """Which characters of ``member`` the reader cannot see through — ASKED, one probe per character.

 Each distinct character is put, alone, into a member the reader certainly reads
 (``a<char>b/PLAN.md``) and :func:`index_is_visible` is asked. No list of forbidden characters is
 written anywhere: the answer comes from the same regex and the same ``index_problems`` that will
 judge the commit, so it cannot age away from them. Measured this way today, twelve characters
 blind the reader — ``" ' ( ) , ; < > [ ] ` |`` — and every one of them is load-bearing in the
 judge (they are what TERMINATES a quoted, linked, celled or bracketed path in real markdown).

 **THE COST OF REFUSING THEM, MEASURED ON A POPULATION WRITTEN BEFORE THE RULE.** Over the 116
 distinct folder names this repo really carries outside ``projects/``, **3** are unindexable — and
 all three are ``.figures`` directories a tool fabricated from book titles, so that population is
 not a witness at all (it holds no free-form French name). Over 52 plausible French sub-plan names
 written by hand before measuring, **12 are refused (23 %), 6 of them by the plain apostrophe
 alone** — the commonest character of a French title. That is the price, and it is named here
 rather than discovered later. The alternative — widening the reader's reference class — was
 weighed and refused: those twelve characters are exactly what stops a path from swallowing the
 rest of a line, and D170 measured that admitting ``,`` costs +120 real lines and ``(`` +121.
 """

    def alone(char: str) -> str:
        """A member the reader certainly reads, carrying ``char`` and nothing else unusual."""
        return f"{ARCS_DIRNAME}/a{char}b/{PLAN_FILENAME}"

    return tuple(char for char in dict.fromkeys(member) if not index_is_visible(alone(char), "t"))


def door_skeleton(
    project: str, cap: str, entries: tuple[tuple[str, str], ...], format_declare: str = ""
) -> str:
    """The exact bytes of a conformant DOOR — the cap, the index, and the addresses. Nothing else.

 ``entries`` are ``(member, title)`` pairs, ``member`` relative to this door's folder
 (``plan/foundation.md``). Each becomes ONE line, through
 :func:`~mnemosyne.production.plan_convert.index_entry` — the single expression of that shape in
 this repo, and the one D170 pinned. The door carries NO item: items live in the arcs, and a door
 that carries them re-creates the monolith the folder form exists to end (measured: 1310 lines
 paid by every session that only needed one arc).

 Handed out rather than described, for the reason the whole format exists: an agent told to "write
 a plan in the imposed format" writes something slightly different every time. The suite parses
 this exact string through the reader that must accept it, so the two cannot drift.

 The trailing comment names ``make`` gestures and ``docs/…`` pages, never a ``plan/…md`` path:
 a path in ENTRY POSITION inside this block would be a DECLARATION (D167 / D168), and a door that
 declares an arc it does not own refuses its own first commit (``index_sans_fichier``).

 **D176 (2026-08-17) — A PLAN THAT DOES EXACTLY WHAT IT IS TOLD WAS BORN OWING NOTHING.**
 Measured on the real tool, before this fix: `champs_requis_pour` returns `()` for a door with
 no `**Format**` line, so a newborn plan's first item could skip all six fields and the barrier
 stayed silent — the user's own named failure mode, *"it wasn't mandatory, so it didn't happen"*,
 reproduced by the very command meant to prevent it. The naive fix (write `**Format**` by
 default) would IMPOSE adoption, breaking D176 the other way. This scaffold instead always
 prints the explanatory comment below — so the question is ENCOUNTERED at every birth — and
 writes the actual `**Format**` line only when ``format_declare`` is non-empty: never forced,
 never invisible.
 """
    index = [index_entry(member, title) for member, title in entries]
    format_block = [_format_line(format_declare)] if format_declare else []
    return "\n".join(
        [
            _title_line(project),
            "",
            _cap_line(cap),
            *format_block,
            "",
            "<!-- D176 — THE FORMAT YOU MAY REQUIRE OF EVERY ITEM OF THIS PLAN. A cold choice,",
            "     made once, revisable, and **optional**: declaring nothing is a valid answer,",
            "     nothing refuses you. This is not a form, it is an offer.",
            "",
            "     To declare: add `> **Format** : <fields>` right under **Cap**, with the",
            "     fields YOU want to make mandatory — among produit, fini_quand, depend_de,",
            "     prerequis, a_lire, taille — separated by commas. An item that does not fill in",
            "     a declared field is refused at commit time ; `AUCUN` is a valid and free answer",
            "     for a field that does not apply to that particular item.",
            "",
            "     \U000026D4 Once adopted, there is no drifting away from it: if you declare, install the",
            "     gate that makes it HOLD (`make plan-gate-emit`) too, otherwise the promise stays",
            "     written and never verified. Detail of each field: `docs/FORMAT_PLAN.md`. -->",
            "",
            "## The arcs",
            "",
            *index,
            "",
            f"## {TITRE_DECLARATION}",
            "",
            "_Nothing declared — this project takes what it wants, when it needs it._",
            "",
            "<!-- B4 — WHAT **THIS** PROJECT TAKES FROM `make arsenal`. A cold choice, made once,",
            "     revisable, and **optional**: leaving this sentence as it stands is a valid",
            "     answer, nothing refuses it. This is not a form, it is an offer.",
            "",
            "     To declare: replace the sentence with the lines of `make arsenal` you want,",
            "     PASTED as they are (retyping them by hand drifts: 12/12 against the tool,",
            "     2/10 by hand, D170). For example:",
            "       - `make verbatim-check` \U0001F6E1\U0000FE0F the verbatim floor replayed on ONE record",
            "     Then `make arsenal POUR=<this plan>` returns only YOUR weapons, and it NAMES",
            "     a declared target that does not exist — a typo stops being silent.",
            "",
            "     \U000026D4 The hard rules are neither declared nor waived: they live in `CLAUDE.md`.",
            "     Here it is the tooling — never the safety. -->",
            "",
            "<!-- This plan is a FOLDER (D166): this DOOR carries the cap and the index, the items",
            "     live in the arcs. The code verifies the index in BOTH directions — an arc this",
            "     door names nowhere is refused (arc_hors_index), and so is an entry naming a",
            "     file that is absent (index_sans_fichier). Write NO total by hand: the tool",
            "     computes them from the items.",
            "",
            "     Statuses: \U00002B1C to do · \U0001F504 in progress · \U00002705 done · \U0001F17F\U0000FE0F ready, awaiting a human gesture",
            "               \U000026D4 closed, will not be done · \U000023F8\U0000FE0F paused, resumption expected.",
            "",
            "     What Mnemosyne holds FOR YOU, outside this folder (D163 — the address, not the copy):",
            "     \U000026D4 From THIS folder, `make <target>` does not exist — `make` has no root here.",
            "        ALWAYS prefix, for example: `make -C <the Mnemosyne repo> describe`",
            "        (or `mnemo describe`, if the shell function is installed — J4).",
            "       make describe                what you have access to, before building anything",
            "       make plan-emit               the LITERAL structure of a plan — to apply, not to interpret",
            "       make plan-nouveau            an arc is getting too big? it becomes a SUB-PLAN, here",
            "       docs/FORMAT_PLAN.md          the form of THIS file",
            "       docs/signalements/README.md  Mnemosyne breaks? you REPORT it, you do not repair it (D153)",
            "       docs/parentheses/README.md   a detour opens? it lives BESIDE the plan, and it COMES BACK (C8-c) -->",
            "",
        ]
    )


def arc_skeleton(title: str, ident: str, item: str = DEFAULT_ITEM) -> str:
    """The exact bytes of a conformant ARC — a heading, and at least one item. No cap: the door has it.

    An arc with zero items is unreadable AS AN ARC and drags the whole plan down with it, so the
    single item is the floor of the shape rather than a courtesy. The heading is a ``#`` title and
    not ``# PLAN — …``: a ``# PLAN — …`` line would make the reader read a PROJECT NAME out of an
    arc, and ``merge_plan`` gives the door's name the last word anyway — two names for one plan is a
    second source of truth, which is the defect this format exists to close.
    """
    return "\n".join(
        [
            f"# {title}",
            "",
            f"- **{ident}** \U00002B1C {item}",
            "",
        ]
    )


@dataclass(frozen=True, slots=True)
class MethodQuestion:
    """One of the SEVEN falsifiable properties of a plan, turned into a QUESTION -- never an answer.

    Source: an internal design document (not in this mirror), sec. 3 ("The engineering of the
    plan — SEVEN falsifiable properties"). ``sigle`` and ``nom`` are the SAME as that table; only
    the SHAPE changes, from a verdict already reached (an entry in a table, marked invented-and-paid
    or nowhere) to a question still open for whoever is writing THIS item. A2's design, one floor
    up: *the QUESTION is mandatory, never the ANSWER*, and "not applicable" is a valid, free
    answer.
    """

    sigle: str
    nom: str
    question: str


#: The seven properties, in the SAME order as that internal design document's sec. 3
#: table -- P1 first because completeness is asked before anything else can be asked about a single
#: item. Each question is traceable to that table's own justification column, reshaped from a
#: verdict into a question.
#:
#: NIVEAU 1 (internal governance notes, not in this mirror), NOT niveau 2: nothing in this
#: module, and nothing in :func:`verify_readability`, reads this tuple to judge a plan. The FORM is
#: niveau 2 (the reader); the THINKING never is -- "a method of thinking at niveau 2 would be
#: exactly the rigid template the user refused" (A6, an internal design note not in this mirror).
#: There is no ``methode_illisible`` refusal, and there
#: must never be one: a gate on these seven questions would be the exact failure this tuple exists
#: to avoid.
METHOD_QUESTIONS: Final[tuple[MethodQuestion, ...]] = (
    MethodQuestion(
        "P1",
        "COMPLETENESS",
        "What does the intent require that no item carries yet -- and does the list that answers "
        "that question come from anywhere other than this plan itself?",
    ),
    MethodQuestion(
        "P2",
        "SELF-SUFFICIENCY",
        "If this item left on its own, to an executor who knows nothing else about the project and "
        "will not come back to ask, would they know what to read, what to do, and how to recognise "
        "that they are finished?",
    ),
    MethodQuestion(
        "P3",
        "FALSIFIABILITY",
        "This item's `Fini quand` -- could somebody attack it and win, or is it only true if you "
        "take its word for it?",
    ),
    MethodQuestion(
        "P4",
        "SCHEDULABILITY",
        "What does this item really depend on in order to start -- and is that dependency written "
        "down somewhere, or only in the head of whoever conceived it?",
    ),
    MethodQuestion(
        "P5",
        "PROPORTIONALITY",
        "How much does this item cost, and what does it give the project in exchange -- and if the "
        "answer is vague, is it really the next one to do?",
    ),
    MethodQuestion(
        "P6",
        "REVISABILITY",
        "If reality contradicts this item tomorrow, does this plan know how to RETRACT -- or only "
        "how to grow?",
    ),
    MethodQuestion(
        "P7",
        "PORTABILITY",
        "What must have been READ to begin this item -- and is that list written in the item, or "
        "only in the head of whoever conceived it?",
    ),
)

#: The sequence that produced THIS very capability -- a TRACK, never an imposed order (niveau 1,
#: same as :data:`METHOD_QUESTIONS`). Static prose, like the rest of
#: :data:`PLAN_CONTRACT_TEMPLATE` it is folded into: no runtime function COMPUTES a "sequence" the
#: way :func:`door_skeleton` computes a door, so there is no second home for this text to drift
#: from -- unlike the arcs, the door or the index entry, which a real tool writes, and which are
#: therefore replayed from code rather than typed here (contract-single-source-emit).
_METHOD_SEQUENCE: Final = """\
   THE SEQUENCE that produced THIS very contract -- a track, never an imposed order:
     1. INVESTIGATE  -- what do we not yet know about this intent, and who might know it?
     2. AXES         -- out of that investigation, which broad zones emerge?
     3. ITEMS        -- within each axis, which self-sufficient leaves (P2)?
     4. GRANULARISE  -- as long as a file forces you to SEARCH to find what you came for, it is
                         not finished being cut up; when it reads in one go, it is."""

#: A9 -- born from a MEASUREMENT, not an idea: the A6 differential trial (isolated judge, blind,
#: 2026-08-15 20:55) recorded ``harms`` -- the arm that read this method produced a WORSE plan on
#: its two heaviest-consequence points. Named here VERBATIM from the judge's own verdict, and
#: nothing else: a broader rewrite of the seven questions would answer a measurement this module
#: does not have. Niveau 1, exactly like :data:`METHOD_QUESTIONS` -- two cautions, never a rule;
#: "non applicable" stays a free, valid answer to both.
_METHOD_MEASURED_TRAPS: Final = """\
   \U000026A0\U0000FE0F TWO TRAPS MEASURED ON THIS VERY PLAN (a real task, an isolated judge, 2026-08-15,
   verdict `harms`) -- neither is a rule, both are one more question to ask yourself:
     - A constraint you have JUST ASSERTED ("impossible without X") -- has it been VERIFIED, or
       only supposed? (measured: "no guarantee without a server" for a purely local assistant
       -- false, an OS-scheduled notification is the standard mechanism for that)
     - Privacy, security, risk: none of the seven questions above names them, so they are easy
       to forget ENTIRELY rather than to handle badly. (measured: a plan "usable by real users"
       without one line on the sensitivity of what it stores)"""


def method_skeleton() -> str:
    """The exact bytes of the METHOD section handed out by ``make plan-emit``.

    SEVEN questions rendered from :data:`METHOD_QUESTIONS` -- the single tuple they live in, so a
    question edited there is edited in the only place it exists -- plus :data:`_METHOD_SEQUENCE`
    and :data:`_METHOD_MEASURED_TRAPS` (A9: two cautions a real trial found missing, and only
    those two -- a correction that widened the seven questions would answer a measurement this
    module does not have).

    Pure text, and that is the whole point: no reader parses it, nothing here can raise a
    :class:`ScaffoldRefusal`, and :func:`verify_readability` never sees it. Niveau 1
    (internal governance notes, not in this mirror) is not a promise kept by discipline -- it is a
    promise kept by this function having no failure path to exercise.
    """
    blocks = [
        f"   {q.sigle} {q.nom}\n"
        + textwrap.fill(q.question, width=88, initial_indent="      ", subsequent_indent="      ")
        for q in METHOD_QUESTIONS
    ]
    return "\n\n".join([*blocks, _METHOD_SEQUENCE, _METHOD_MEASURED_TRAPS])


def _clean_folder(folder: str) -> str:
    """A repo-relative POSIX folder, with no leading or trailing ``/`` — ``""`` for the repo root.

    ``.`` and ``./`` normalise to ``""`` as well, and that is a REFUSAL being made reachable rather
    than a nicety: ``CHEMIN="."`` used to survive as the literal folder ``"."``, so the command
    proposed a plan named ``.`` with its door at ``./PLAN.md`` — i.e. ``PLAN.md`` and ``plan/`` **at
    the repo root**, which ``CLAUDE.md`` forbids without an explicit test, and the commit was
    accepted. One normalisation, and the empty folder the refusals already knew how to name.
    """
    stripped = folder.strip("/")
    return "" if stripped == "." else stripped[2:] if stripped.startswith("./") else stripped


def _member_of(folder: str, arcs_relative: str) -> str:
    """``plan/<relative>`` — a path relative to the DOOR, which is the namespace the reader uses."""
    return f"{ARCS_DIRNAME}/{arcs_relative}" if arcs_relative else ARCS_DIRNAME


def _arcs_dir_of(parent: str) -> str:
    """``<parent>/plan`` — the arcs directory of a plan rooted at ``parent`` (``plan`` at the root)."""
    return f"{parent}/{ARCS_DIRNAME}" if parent else ARCS_DIRNAME


def owning_parent(folder: str, existing: tuple[str, ...]) -> tuple[str, str, str] | None:
    """Which existing plan will OWN this new folder — ``(parent folder, door name, member)``.

    A new plan nests when its folder sits under some ``<parent>/plan/``. The parent is the LONGEST
    such folder that really carries a door, which is exactly ``owning_plan``'s tie-break and is not
    re-derived here for a cheaper one: with a door at ``teams/x/PLAN.md`` and another at
    ``teams/x/plan/t/PLAN.md``, a plan born at ``teams/x/plan/t/plan/s`` belongs to the INNER one, and
    telling the outer one about it would post the entry on a door that is not asked for it.

    Public because the runtime layer needs the SAME answer to know whose door to read, and it had
    written its own copy of this walk. Two expressions of "who owns this folder" is the class this
    whole repair is about, one question smaller.
    """
    doors = {
        path.rsplit("/", 1)[0] if "/" in path else "": path.rsplit("/", 1)[-1]
        for path in existing
        if path.rsplit("/", 1)[-1] in DOOR_FILENAMES
    }
    owners = [parent for parent in doors if folder.startswith(f"{_arcs_dir_of(parent)}/")]
    if not owners:
        return None
    parent = max(owners, key=len)
    prefix = f"{_arcs_dir_of(parent)}/"
    return parent, doors[parent], f"{ARCS_DIRNAME}/{folder[len(prefix) :]}/{PLAN_FILENAME}"


def _is_arcs_dir_of_a_plan(folder: str, existing: tuple[str, ...]) -> str:
    """The plan whose ``plan/`` directory ``folder`` IS, or ``""`` — a birth that must not happen.

 **A very plausible typo, and it broke the plan ABOVE while reporting success**: pointing at
 ``<projet>/plan`` instead of ``<projet>``. The door lands at ``<projet>/plan/PLAN.md`` — directly
 IN the parent's arcs directory, not in a sub-directory of it — and ``plan_entries`` then reads
 that door and its own arc as two ARCS of the parent, neither of them indexed. Measured: birth
 exit 0, ``git commit`` exit 0, then ``make plans`` says *"PLAN.md present but UNREADABLE"* with
 two ``arc_hors_index`` and an ``id_duplique``. ``owning_parent`` could not see it because it asks
 for a ``<parent>/plan/`` PREFIX, and ``<parent>/plan`` is not a prefix of itself.

 One directory deeper is perfectly legal and stays so: ``<projet>/plan/t1`` is a sub-plan. This
 refuses the exact string that is the arcs directory itself, at any level.
 """
    doors = {
        path.rsplit("/", 1)[0] if "/" in path else ""
        for path in existing
        if path.rsplit("/", 1)[-1] in DOOR_FILENAMES
    }
    return next((parent for parent in doors if folder == _arcs_dir_of(parent)), "")


#: BR2(a) (a signalements field report on this scaffold, 2026-07-29 — see
#: ``docs/signalements/README.md`` for the mechanism):
#: the FIRST shape of this pattern matched any live line MENTIONING a `plan/…md` path, prose
#: included — a door whose closing paragraph explains why a path stays indexed (`` `plan/README.md`
#: existe parce que… ``) got the new entry planted mid-sentence, splitting it in two. Measured on the
#: real failure: a door with such a paragraph after its index list landed the entry inside the prose,
#: every time.
#:
#: Anchored on the exact shape :func:`~.plan_convert.index_entry` itself writes — `` - `path` —
#: title `` — rather than "any line naming a path": the list marker and the OPENING backtick must sit
#: right where the entry starts, in ENTRY POSITION, not merely appear somewhere on the line. A
#: sentence that quotes the same path stays prose because nothing at the start of that line puts the
#: backtick where an entry would.
_DECLARING_LINE: Final = re.compile(
    rf"^[ \t]*(?:>[ \t]*)*[-*+][ \t]+`{ARCS_DIRNAME}/[^\s`]*\.md`"
)

#: The first line ending a document uses. Read, never chosen: see :func:`_post_entry`.
_EOL_RE: Final = re.compile(r"\r\n|\r|\n")


def _line_ending(text: str) -> str:
    """The line ending this document ALREADY uses — ``\\n`` only when it uses none."""
    found = _EOL_RE.search(text)
    return found.group(0) if found else "\n"


def _post_entry(door_text: str, entry: str) -> str:
    """Put ``entry`` in the parent door — right after its LAST LIVE index line, else at the end.

 Beside its siblings rather than at the bottom, because an index is READ as a block: an entry
 exiled below a page of prose is an entry the next author edits around. Falls back to appending
 when the door names nothing yet (a door whose ``plan/`` is still empty is legal — that is a plan
 of one file, and this is the edit that makes it a folder).

 **LIVE, and that word is the repair.** The search used to run over raw lines, so a door
 carrying a ```` ```markdown ```` example of an index — which is what a door that documents its
 own format writes — got the entry planted INSIDE the example. Nothing said a word: completeness
 counts a mention anywhere, fenced examples included, ON PURPOSE (D167), so birth was exit 0 and
 the commit was exit 0 while the sub-plan was invisible in the rendered index. The generosity
 that is right for the JUDGE is a trap for the WRITER, so the writer asks
 :func:`~.plan_format.live_lines` — the judge's own fence walk, no second opinion.

 **AND LIVE WAS NOT ENOUGH — a live line of PROSE is still not an entry (BR2(a)).** A door
 that explains, in its closing paragraph, why a path stays indexed (`` `plan/README.md` existe
 parce que… ``) is a live line naming that path — and the first shape of :data:`_DECLARING_LINE`
 matched any live mention, so the new entry landed mid-sentence, splitting a paragraph in two.
 Measured on the exact door this broke. The pattern is now anchored on the shape
 :func:`~.plan_convert.index_entry` itself writes — list marker, then the OPENING backtick in
 ENTRY POSITION — so a sentence that merely quotes the same path stays prose: nothing at the
 START of that line puts a backtick where an entry's would be.

 **AND IT MOVES BYTES, IT DOES NOT REWRITE THEM.** The parent door is the ONLY pre-existing
 file this whole capability touches. ``splitlines()`` + ``"\\n".join()`` silently converted a
 CRLF door to LF — measured: 24 carriage returns in, **0** out — a diff nobody asked for, in a
 file somebody else is working in. The document's own line ending is read and reused, including
 for a door that ends without a final newline.

 Nothing here asserts the result is valid: :func:`verify_readability` asks the reader, on the
 bytes. A helper that graded its own insertion would be the co-domiciled guard this repo has
 already measured as no guard at all.
 """
    lines = door_text.splitlines(keepends=True)
    live = live_lines(door_text)
    last = max(
        (n for n, raw in enumerate(lines) if live[n] and _DECLARING_LINE.search(raw)),
        default=None,
    )
    eol = _line_ending(door_text)
    if last is None:
        double = eol + eol
        tail = "" if door_text.endswith(double) else (eol if door_text.endswith(eol) else double)
        return f"{door_text}{tail}{entry}{eol}"
    body = lines[last].rstrip("\r\n")
    own = lines[last][len(body) :]
    # `own` is empty only when that line is the last of a door with no final newline: give it the
    # document's ending and let the new entry carry none, so the door still ends the way it ended.
    lines[last] = body + (own or eol)
    lines.insert(last + 1, entry + own)
    return "".join(lines)


def _text_refusals(
    field: str, value: str, line: str, owns: str = ""
) -> tuple[ScaffoldRefusal, ...]:
    """What is wrong with a string the CALLER handed us — named, with the offending word.

 ``line`` is the LINE that value really lands in, built by the very function that writes it
 (:func:`_title_line`, :func:`_cap_line`, :func:`~.plan_convert.index_entry`). It is passed rather
 than reconstructed because the second half of this check is POSITIONAL, and a value judged out of
 its line is judged by a rule the reader does not have. ``owns`` is the one path that line is
 ENTITLED to declare — an index entry declares its own arc, that is its whole job — so what is
 refused is the declaration the caller's value ADDED.

 A project name, a cap and an arc title are dropped verbatim into lines the reader parses
 (``# PLAN — <nom>``, ``> **Cap** : <cap>``, ``# <titre>``, and the index entry). Two things a
 caller can put in them change how those lines PARSE, and both were reported as a defect of
 Mnemosyne sending the caller to ``make signaler``:

 * a NEWLINE — the value becomes several lines, and a fenced block opened there switches the
 whole staleness check off (``bloc_non_ferme``). Measured: ``--cap $'un cap\\n```'``;
 * a ``plan/….md`` reference — the reader reads an index ENTRY where a title was meant, pointing
 at a file nobody will ever write (``index_sans_fichier``). Measured: ``--arc "Foundation —
 plan/ghost.md"`` and ``--nom "plan/other.md"``.

 The newline is checked FIRST and the two never fire together, on purpose. A value carrying
 both would otherwise name the path as the cause when the line break is what the caller must fix
 — and *the order of my checks decides the cause named*. There is deliberately NO separate refusal
 for a code fence: a fence only opens at the start of a line, so a fence in a value ALWAYS needs a
 newline to become one, and a refusal that can never fire alone is a gesture pointing at the wrong
 thing (the defect ``nom_manquant`` carried).

 **AND THE SECOND ONE ACCUSED A CLASS THE READER WAVES THROUGH.** It asked
 a bare regex over the VALUE — *"does this text contain a path?"* — while the judge asks
 :func:`~.plan_format.declared_paths` over the LINE — *"would the reader read this path as an
 ENTRY?"*. A title merely MENTIONING ``plan/arc-c.md`` mid-line was refused, and the
 justification printed (*"it would demand a file nobody will ever write"*) was FALSE for it:
 ``index_problems`` on the resulting door returns nothing at all. Measured: **1 false refusal out
 of 30 fabricated titles, 0 out of the 571 real titles of this repo** — small, and a refusal whose
 stated reason is untrue for its own class is a refusal nobody can argue with. The two predicates
 now come from the same walk, so the accusation is exactly the judge's.
 """
    if _EOL_RE.search(value):
        return (ScaffoldRefusal("texte_multiligne", f"{field}: {value.splitlines()[0]!r} …"),)
    added = [path for path in declared_paths(line) if path != owns]
    if added:
        return (ScaffoldRefusal("texte_declare_un_chemin", f'{field}: "{added[0]}"'),)
    return ()


def plan_scaffold(
    *,
    folder: str,
    project: str = "",
    cap: str = "",
    arcs: tuple[str, ...] = (),
    existing: tuple[str, ...] = (),
    parent_door_text: str = "",
    folder_is_file: bool = False,
    inside_repo: bool = True,
    format_declare: str = "",
) -> ScaffoldPlanning:
    """Plan the birth of a folder-shaped plan at ``folder``. Computes bytes and refusals; writes nothing.

 ``existing`` is every path already present, relative to the repo root and ``/``-joined — the same
 namespace ``git ls-files`` and ``rglob`` both produce, so the question "does this already exist?"
 is asked of the same strings the barrier will judge. It is what makes ``plan_existe`` and
 ``arc_existe`` structural rather than a race against the disk.

 ``project`` defaults to the folder's own name, which is right far more often than it is wrong and
 costs one flag to override; ``cap`` defaults to :data:`DEFAULT_CAP`; ``arcs`` defaults to one arc
 called :data:`DEFAULT_ARC_TITLE`. Defaults rather than refusals on purpose: this scaffold's whole
 job is that the conformant shape is the CHEAP one. What it refuses is what it cannot do safely.

 ``format_declare`` (D176) defaults to ``""`` — a birth that says nothing about `**Format**`
 stays exactly as conformant as before this parameter existed. Passed VERBATIM, never parsed or
 filtered here: an unrecognised token is `champs_requis_pour`'s call to make, not this scaffold's
 — the same "one foyer" this repo already pays for elsewhere.

 **A SUB-PLAN INHERITS ITS PARENT'S `**Format**` when it declares none of its own.** A
 sub-plan is the SAME project continuing, never a fresh adoption decision — measured on a real
 deployment (an internal handoff note): a declaration on the root door alone holds 21 of 168
 items (12.5%), because every sub-plan born without this inheritance opted OUT silently, at
 exactly the moment ``CLAUDE.md`` itself prescribes ("an arc too big becomes a sub-plan").
 Explicit always wins: a caller-supplied ``format_declare`` is never overridden by the parent's.
 """
    raw_folder = folder.strip()
    folder = _clean_folder(folder)
    refusals: list[ScaffoldRefusal] = []
    owning = owning_parent(folder, existing) if folder else None

    # D176 — FOUND BY AN ADVERSARIAL AUDIT, NOT BY ME: the declaration does not inherit. A
    # sub-plan born under an ADOPTING parent (`**Format**` declared) used to be born NON-adopting --
    # and being born as a sub-plan is the NORMAL shape an arc that has grown too big takes
    # (CLAUDE.md itself says so). Measured on a real deployment (an internal handoff note): a
    # declaration on the root door alone holds only 21 items out of 168 (12.5%) -- adoption
    # evaporates exactly where the volume arrives. INHERIT, rather than REFUSE (the alternative
    # on offer): a sub-plan is the CONTINUATION of the same project, never a fresh adoption
    # decision -- refusing would force a repeated `--format` on every sub-plan, the very same
    # forgetting friction D176 exists to close, just moved from "never declared" to "forgotten this
    # time." EXPLICIT ALWAYS WINS: a sub-plan that supplies its own `format_declare` never inherits,
    # it is never stuck with the parent's choice. The SAME gesture, in the SAME place, as the
    # parent's index-entry stitch just below (same `parent_door_text`, same transaction).
    format_declare = format_declare.strip()
    # AUTONOMY PROBE (D75, 2026-08-17): the RECEIVED value must survive the inheritance, so the
    # replay command (`plan_new_run.render`) can freeze an explicit choice instead of letting
    # `plan-nouveau` propose a command that would erase it on the second call. See `ScaffoldPlanning.
    # format_arg`.
    format_arg = format_declare
    if not format_declare and owning is not None and parent_door_text:
        format_declare = read_plan(parent_door_text).format_declare
    if not folder:
        # The two are ONE question with two true answers, and telling them apart is the whole
        # difference between a gesture and a shrug: nothing was given, or the repo root was given.
        refusals.append(
            ScaffoldRefusal("chemin_manquant", "(vide)")
            if not raw_folder
            else ScaffoldRefusal("racine_du_depot", raw_folder)
        )
    if not inside_repo:
        refusals.append(ScaffoldRefusal("hors_depot", folder or raw_folder or "(vide)"))
    if folder_is_file:
        refusals.append(ScaffoldRefusal("chemin_occupe", folder))
    if folder and (owner := _is_arcs_dir_of_a_plan(folder, existing)):
        refusals.append(
            ScaffoldRefusal(
                "dossier_des_arcs", f"{folder} — the arcs folder of \"{owner or '.'}\""
            )
        )
    # `scan_projects` (plan_registry.py) walks EXACTLY two levels under `projects/` — bubble
    # (depth 1), project (depth 2) — and nothing deeper is even WALKED (neither read, nor flagged
    # `misplaced`): measured by reading its loop, not assumed. A `projects/…` path that is neither
    # at depth 2 nor a recognised sub-plan (`owning`, a separate and already-proven mechanism) would
    # be born with `RC 0` and will never be a project for anyone who reads it afterwards.
    if folder and owning is None and folder.startswith(f"{PROJECTS_DIRNAME}/"):
        if folder.count("/") != 2:
            refusals.append(ScaffoldRefusal("profondeur_projet", folder))

    # `.strip()` on the folder-derived name too: without it a folder whose last segment is blank
    # handed `# PLAN — ` to the reader, which reads NO project — and `nom_manquant`, the refusal
    # written for exactly that, could never fire on its own (an empty folder always tripped
    # `chemin_manquant` first). A refusal that cannot fire alone prints a gesture for a cause that
    # is not the one that stopped you.
    name = project.strip() or (folder.rsplit("/", 1)[-1].strip() if folder else "")
    if not name:
        refusals.append(ScaffoldRefusal("nom_manquant", folder or "(vide)"))
    refusals.extend(_text_refusals("the name", name, _title_line(name)))
    refusals.extend(_text_refusals("the cap", cap.strip(), _cap_line(cap.strip())))
    refusals.extend(
        _text_refusals("the format", format_declare.strip(), _format_line(format_declare.strip()))
    )

    titles = tuple(arcs) or (DEFAULT_ARC_TITLE,)
    if len(titles) > _MAX_ARCS:
        raise ValueError(
            f"{len(titles)} arcs requested — the identity alphabet stops at {_MAX_ARCS}"
        )
    drafts: list[ArcDraft] = []
    seen: dict[str, str] = {}
    for position, title in enumerate(titles):
        if not title.strip():
            refusals.append(ScaffoldRefusal("arc_sans_titre", f"arc no. {position + 1}"))
            continue
        member = _member_of(folder, f"{slugify(title)}.md")
        # The title's line is its INDEX ENTRY, not its own `# <title>` heading: `index_problems`
        # interrogates the DOOR and nothing else, so a path in an arc's heading is judged by nobody
        # while the same path behind the entry's separator is a declaration. Judge the line that is
        # judged.
        refusals.extend(
            _text_refusals(
                f"arc no. {position + 1}", title.strip(), index_entry(member, title.strip()), member
            )
        )
        if member in seen:
            refusals.append(
                ScaffoldRefusal("collision_de_nom", f'"{seen[member]}" and "{title}" → {member}')
            )
            continue
        seen[member] = title
        ident = arc_ident(len(drafts))
        drafts.append(ArcDraft(member, title.strip(), ident, arc_skeleton(title.strip(), ident)))

    present = set(existing)
    for door_name in DOOR_FILENAMES:
        candidate = f"{folder}/{door_name}" if folder else door_name
        if candidate in present:
            refusals.append(ScaffoldRefusal("plan_existe", candidate))
    for draft in drafts:
        candidate = f"{folder}/{draft.member}" if folder else draft.member
        if candidate in present:
            refusals.append(ScaffoldRefusal("arc_existe", candidate))

    parent: ParentUpdate | None = None
    if owning is not None:
        parent_folder, parent_door, member = owning
        entry = index_entry(member, name or member)
        # THE PATH IS A VALUE THAT LANDS IN A DOCUMENT, so it goes through the caller filter like
        # the other three. It is asked of the READER (`index_is_visible`), never of a character list,
        # and it fires ONLY here — a plan born at the top level never writes its folder anywhere, so
        # refusing `docs/<plan-name>` there would be the symmetric hole, dug the day this one was closed.
        if not index_is_visible(member, name or member):
            blinders = blinding_characters(member)
            refusals.append(
                ScaffoldRefusal(
                    "chemin_non_indexable",
                    f"{folder} — character(s) unreadable for the index: "
                    + " ".join(f'"{char}"' for char in blinders),
                )
            )
        if not parent_door_text:
            refusals.append(
                ScaffoldRefusal(
                    "porte_parente_illisible",
                    f"{parent_folder}/{parent_door} — parent door text not supplied",
                )
            )
        else:
            parent = ParentUpdate(
                folder=parent_folder,
                door_name=parent_door,
                member=member,
                entry=entry,
                text=_post_entry(parent_door_text, entry),
                before=parent_door_text,
            )

    _sous_plan = owning_parent(folder, existing) is not None
    return ScaffoldPlanning(
        folder=folder,
        project=name,
        cap=cap.strip() or DEFAULT_CAP,
        door_name=PLAN_FILENAME,
        door_text=door_skeleton(
            name,
            cap.strip() or DEFAULT_CAP,
            tuple((d.member, d.title) for d in drafts),
            format_declare.strip(),
        ),
        arcs=tuple(drafts),
        # A SUB-plan (it has a parent) does not get its own command: the requester's words apply
        # to the project, not to one of its arcs. Giving it one would manufacture a second source.
        # `owning_parent`, NOT `parent`: the latter is only populated if the parent door is
        # READABLE. On a sub-plan whose parent is unreadable, `parent is None` -- and the
        # sub-plan then used to receive its own command, i.e. a SECOND source of truth.
        # Measured: `essai/plan/T1` returned `parent=False` and `owning_parent=('essai', ...)`.
        livrables_name="" if _sous_plan else livrables.NOM_A_LA_NAISSANCE,
        livrables_text="" if _sous_plan else livrables.gabarit(name),
        parent=parent,
        refusals=tuple(refusals),
        format_arg=format_arg,
    )


def _fold(door_text: str, members: tuple[tuple[str, str], ...]) -> PlanReading:
    """Read a whole plan the way ``read_plan_tree`` and the pre-commit hook do — ONE folding, shared.

    ``members`` are ``(path relative to the door, text)`` for every file under ``plan/``, nested
    plans included. Which of them are THIS plan's arcs is not decided here: it is
    :func:`~.plan_format.fold_plan` — literally the function ``read_plan_tree`` calls — and that is
    the repair. This used to fold every member handed to it, so a first sub-plan's own arc was read
    into the PARENT's identity ledger and a SECOND sibling sub-plan was refused for an ``id_duplique``
    that did not exist. A third way of folding a plan is a third opinion about what a plan says.
    """
    texts = dict(members)
    return fold_plan(door_text, tuple(texts), lambda member: (texts[member], ""))


def _why(reading: PlanReading) -> str:
    """Why the reader refused, in ONE sentence — the missing pieces AND the named refusals.

    Both halves, always: a message carrying only ``unreadable_reasons`` goes silent on the exact
    refusals (``arc_hors_index``, ``index_sans_fichier``) this capability exists to make impossible,
    and a refusal nobody can read is a refusal nobody acts on.
    """
    return " ; ".join(
        [
            *unreadable_reasons(reading, role=ROLE_PLAN),
            *(f"{p.where} : {p.kind} — {p.detail}" for p in reading.problems),
        ]
    )


def verify_readability(
    planning: ScaffoldPlanning,
    *,
    parent_members: tuple[tuple[str, str], ...] = (),
    parent_lost: tuple[str, ...] = (),
) -> None:
    """Ask THE READER whether the bytes about to be written form a readable plan. Raise if not.

 The last gate, and the one that cannot be a matter of opinion: it replays ``read_plan`` +
 ``merge_plan`` + ``index_problems`` + ``is_readable`` on the exact strings :func:`plan_scaffold`
 produced, so what is checked is the artefact and not an idea of it. Called BEFORE any write, so a
 scaffold that would be refused by the pre-commit barrier is refused here instead — the point of
 the whole capability is that a plan passes the door on its FIRST commit, with no conversion.

 ``parent_members`` is every file of the PARENT plan (relative to the parent's door), the new
 nested door INCLUDED, so the parent is re-judged in its resulting state. Without it the parent's
 index would be verified against the tree it had BEFORE — a check valid only in the state before
 the edit it is supposed to guard, which is the harness defect this repo has already measured.
 ``parent_lost`` names the parent's arcs that exist on the disk and could not be opened.

 **THE PARENT IS FOLDED TWICE, and the second fold is what makes the accusation true.** A
 parent door that was ALREADY unreadable — an unclosed fence, an un-indexed arc, no cap — made
 this raise, and the surface printed *"a defect of Mnemosyne"*. Folding the parent in the state
 it is already in separates the two: broken before → :class:`ParentDoorUnreadable` (repair the
 parent, the gesture ``porte_parente_illisible`` already carried); broken only after our entry →
 :class:`ScaffoldMismatch`, and that one is ours to confess.
 """
    reading = _fold(planning.door_text, tuple((arc.member, arc.text) for arc in planning.arcs))
    if not is_readable(reading, role=ROLE_PLAN):
        raise ScaffoldMismatch(
            f"the plan scaffolded at \"{planning.folder or '.'}\" is judged UNREADABLE by the reader: "
            + _why(reading)
        )
    if planning.parent is None:
        return
    door = f"{planning.parent.folder}/{planning.parent.door_name}"
    if parent_lost:
        raise ParentDoorUnreadable(
            f'the parent door "{door}" has arcs that are UNREADABLE on disk: '
            + ", ".join(parent_lost)
        )
    before = _fold(
        planning.parent.before,
        tuple((m, t) for m, t in parent_members if m != planning.parent.member),
    )
    if not is_readable(before, role=ROLE_PLAN):
        raise ParentDoorUnreadable(
            f'the parent door "{door}" was ALREADY unreadable before this birth: ' + _why(before)
        )
    parent_reading = _fold(planning.parent.text, parent_members)
    if not is_readable(parent_reading, role=ROLE_PLAN):
        raise ScaffoldMismatch(
            f'the parent door "{door}" would no longer be readable once the index entry is '
            "added: " + _why(parent_reading)
        )


#: The contract a FRONTIER host receives from ``make plan-emit`` — the FRAME only. Every slot below
#: is filled by replaying the real code (``door_skeleton``, ``arc_skeleton``, ``index_entry``,
#: ``STATUS_LABEL``, ``REFUSAL_KINDS``, ``SEPARATOR_ASCII_KEY``), never by a hand-written copy: the
#: whole reason this exists is that a hand-copied contract loses a clause and nobody sees it.
#:
#: It hands the agent the BYTES, not a description of the bytes. That distinction is the measured
#: one: an agent told "write a plan in the imposed format" writes something slightly different every
#: time, and a divergence is invisible until an interface shows the user nothing.
PLAN_CONTRACT_TEMPLATE: Final = """\
PLANNER CONTRACT (EMITTED from the code, mnemosyne.production.plan_scaffold — never hand-copied):
{rule}

YOU MUST PRODUCE A PLAN THAT IS A FOLDER. Here is the structure, LITERALLY.

1. THE TREE — the door has an imposed name; an interface does not search for a name each project
   gets to choose.

{tree}

2. THE DOOR — `{door_name}` at the root of the plan's folder. WRITE EXACTLY THIS:

{door}
3. AN ARC — one file per arc, inside `{arcs_dirname}/`. WRITE EXACTLY THIS:

{arc}
4. THE INDEX ENTRY — one line per arc in the door, and the code verifies it IN BOTH DIRECTIONS.
   The exact shape, as the tool writes it:

{entry}

   What matters: the path sits in ENTRY POSITION (nothing but notation between the bullet marker
   and it) and a SEPARATOR stands between it and its title. Separators admitted: {separators}
   REFUSED, and each one for a measured reason:
{refused}

5. THE STATUSES — there are no others:
{statuses}

   Two notations, never mixed on the same line:
     - **ID** <glyph> text        (every status; ID = the key, ASCII, no space, <= 12 chars)
     - [ ] text / - [x] text      (the FLOOR: two statuses, no ID, nothing to learn)

6. RECURSION — PERMITTED, NEVER IMPOSED. Any folder carrying a `{door_name}` is a plan, at every
   level: an arc that grew too big becomes a sub-folder with its own door, its own cap, its own
   identity scope. A plan of a SINGLE FILE stays perfectly legal — that is the floor, never a
   degraded case. A sub-plan must be NAMED in its parent's index, otherwise it would be born an
   orphan and the barrier refuses the commit.

7. WHAT THE READER REFUSES, AND NAMES:
{refusals}

8. THE ONE RULE NO CODE HOLDS: write NO total by hand. No "8 arcs out of 13", no status summary
   table — the tool computes them from the items. A computed number cannot rot; a copied one does
   it in three days.

{rule}
WHAT PRECEDES IS IMPOSED (level 2): the FORM. WHAT FOLLOWS IS NOT (level 1): THE THINKING.
"not applicable" is a VALID AND FREE answer to each of the seven questions below — nothing here
blocks, nothing demands a quantity. A template to fill in would manufacture the content it
demands (measured elsewhere in this repo: 5 invented clauses on a control of this kind, 2 of them
false) — this is not one. INVITE, never box in.

9. THE METHOD — SEVEN QUESTIONS, NEVER A TEMPLATE (internal design document, not carried in this mirror, sec. 3):

{method}

   End of the method — what follows returns to the FORM.

{rule}
DO NOT INTERPRET THIS CONTRACT, APPLY IT. Then verify, and do not take your own word for it:
    make plans                     is your plan READABLE, and with how many items?
    git commit                     the pre-commit barrier judges the staged plan, at every level.
And if you would rather the code wrote it for you (it refuses rather than overwriting):
    make plan-nouveau CHEMIN="<folder>" NOM="<name>" CAP="<the cap>" ARC="<first arc>" APPLY=1
"""
