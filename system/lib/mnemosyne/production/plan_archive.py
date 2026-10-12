"""Move the memory of what is DONE out of a living plan - without rewriting one byte of it.

The user's decision, 2026-07-28, in his own words: *"the memory of what is done leaves into a
dated archive beside it"* - not a plans folder, not a display fold (*"if I lose the UI tomorrow, do
I lose everything?"*: legibility must not live in a screen). And his rule 1, which this module turns
from a promise into a barrier: *"strictly, you must never reformulate what is written in the plans,
you write it as-is, exactly as-is"*.

**Why a plan needs this at all - measured, not supposed.** This repository's own top-level plan
document went from 191 to 1231 lines in TWO days (46 commits, ~134 lines/hour), and **26,1 %** of its
lines sit under the title of an arc that is already closed. The plan carries two roles that fight
each other: *memory of what was* and *list of what remains*. A dedicated archive folder already
existed to hold the first - 6 files, 2693
lines, **100 % deposited by hand**, zero script, zero ``make`` target writing there, untouched since
2026-07-20. A folder with no mechanism is not used; that hole is what this closes.

**The guarantee that decides everything: byte-for-byte reconstruction.** Before anything reaches the
disk, :func:`verify_roundtrip` re-reads the body back OUT of the archive text that will actually be
written, splices it back where the pointer sits, and demands the ORIGINAL file back character for
character. It goes through the written artefacts on purpose - checking the slice arithmetic against
itself would be a tautology, and a proof one can print is not a proof. What it catches is real:
a header that normalises, a body/header boundary that is ambiguous, a pointer that is not uniquely
locatable, a file that does not end in a newline, a line of spaces, an NFD accent.

**Two UNITS, because a plan stopped being a file (D166).** A plan that is ONE file archives its ``## ``
sections - that is the floor and it is unchanged. A plan that is a FOLDER archives whole ARCS: the
door carries an index and no ``## `` at all, and each arc file carries exactly one, so "archive the
section of an arc" would empty the file and "archive a section of the door" would find none. Measured
on this repo the day ``make plan-convertir`` ran: the door went from 12 sections to **0**, each of the
12 arcs to **1**, and ``make plan-archiver`` answered *"nothing to archive"* - a confident zero, the
worst shape a command can take. Archiving an arc moves the FILE, and the door keeps the same one-line
prose pointer where its index entry stood.

**Three outcomes per unit, never two** - same rule the reader next door lives by. A section or an arc
is MOVED, REFUSED with a named reason, or simply not a candidate; the residual is published so nobody
can print "3 arcs archived" about a 16-unit plan while 12 were invisible.

**An arc that lies is never archived.** The case is not hypothetical, it is in the file today:
``## ARC A - Ergonomics: measure before building `` carries ``A1`` ``A2`` ``A3`` ``A4``, all
````. Archiving it would bury four lines that declare themselves to-do. The refusal names the arc
AND the offending identities, because a refusal that does not say where is a refusal nobody can act
on. The archiver never arbitrates between a title and its items - that is the user's call, not a tool's.

**Closure is fail-closed over the vocabulary.** :data:`CLOSED_STATUSES` is the small explicit set;
:data:`OPEN_STATUSES` is everything else the format holds, DERIVED from
:data:`~mnemosyne.production.plan_format.STATUS_LABEL`. So a seventh status invented tomorrow lands
on the OPEN side by construction and blocks archiving until someone decides - the opposite polarity
would let an unknown state be silently classified as done. This repo just paid for the other
pattern: ``make plans`` hard-copied the same vocabulary, omitted ``clos`` and ``en_pause`` without a
word, and printed a per-status detail that summed to four on a six-item plan.

Non-destructive (invariant 2): nothing is ever deleted. Content is MOVED, the plan keeps a one-line
prose pointer, and an existing archive file is a REFUSAL, never an overwrite. Dry-run is the default
in the runtime (D92 - propose, never impose).

Code, docstrings and everything the user reads are English (D117 / D33).
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from dataclasses import dataclass
from typing import Final

from .plan_format import (
    _SECTION_RE,  # ONE definition of "what is a section" - a copy here would drift from the reader
    # The index-entry rule, imported for the same reason `_SECTION_RE` is: locating the line a moved
    # arc leaves behind means answering "is this line a DECLARATION of that arc?", and that question
    # already has ONE answer in this repo - the one `index_problems` and the pre-commit barrier ask.
    # A second statement of it here would be a second thing to keep in step, and the day the two
    # disagreed the archiver would remove a line the barrier still counts (or leave one it refuses).
    _ARC_REF_RE,
    _declares,
    _outside_code,
    _same_name,
    ARCS_DIRNAME,
    ROLE_PLAN,
    STATUS_BY_GLYPH,
    STATUS_LABEL,
    FILIATION_REFUSALS as _FILIATION_REFUSALS,
    PlanProblem,
    PlanReading,
    index_problems,
    read_plan,
    unreadable_reasons,
)

#: Re-exported from :mod:`plan_format`, which owns the union every gate reads - same pattern as
#: :data:`~mnemosyne.production.plan_ordre.ORDER_REFUSALS`. ONE home.
FILIATION_REFUSALS: Final = _FILIATION_REFUSALS

#: The statuses that authorise archiving. Deliberately written out rather than derived: deciding
#: that ``fait`` and ``clos`` are "over" is a JUDGEMENT, and a judgement must be visible. What is
#: derived is its complement, so the judgement can never become partial.
CLOSED_STATUSES: Final = frozenset({"fait", "clos"})
#: Everything else the format can express - computed, so a status added tomorrow is OPEN by default
#: and blocks archiving instead of slipping through as done.
OPEN_STATUSES: Final = frozenset(STATUS_LABEL) - CLOSED_STATUSES

#: Where archives land, beside the plan they came from (a plan under ``<folder>/`` archives into
#: ``<folder>/archive/``). Beside, and
#: not in a central store, because a project's memory belongs to the project.
ARCHIVE_DIRNAME: Final = "archive"

#: The boundary between the only lines this module WRITES and the bytes it MOVES. It is a real
#: separator, not a decoration: :func:`verify_roundtrip` recovers the body by splitting the archive
#: on it, so the header can never silently eat or gain a character without the check failing.
VERBATIM_MARKER: Final = "<!-- ↓ everything below is VERBATIM, byte for byte ↓ -->\n\n"

#: A fenced-code delimiter at the start of a line (CommonMark allows up to three spaces of indent).
#: Only the backtick form: over the 68 markdown files of ``docs/``, ``system/`` and the repo root,
#: ``~~~`` appears in ZERO of them, and adding a form nobody writes only widens a net that REFUSES.
#: The same sweep found ZERO files with an odd fence count - so this guard costs no false refusal on
#: the corpus it will actually run against. A catch rate without its false-kill rate is a wall.
_FENCE_RE: Final = re.compile(r"^[ \t]{0,3}```", re.M)

#: Slug length cap. Titles in this repo run to 90 characters (``## ARC C - The UI *(C1-C3 + C7 ;
#: C4-C6 out of my hands)* *(redefined by the user...)*``); a file name that long is unusable in a link.
_SLUG_MAX: Final = 60

#: Refusal reasons, keyed by token. The gesture is part of the message: a refusal that does
#: not say what to DO turns a tool into an obstacle.
REFUSAL_LABEL: Final = {
    "titre_ambigu": "the title declares BOTH a closed state and an open one",
    "borne_incertaine": "the cut would fall inside a code block (an odd number of ```)",
    "arc_ment": "the arc declares itself closed and carries items that are not",
    "ligne_illisible": "the arc holds a line that tried to be an item and could not be read",
    "archive_existe": "the archive file already exists — we never overwrite (inv. 2)",
    "collision_de_nom": "two arcs of this plan produce the same file name",
    "index_incertain": "the door does not designate this arc by ONE index entry and one only",
}


class ArchiveMismatch(RuntimeError):
    """The move is not byte-exact, or would leave the plan unreadable. Nothing may be written.

    Raised, never returned: a caller that can forget to look at a boolean has no barrier. The message
    LOCATES the divergence (offset, line, the two characters) - "the files differ" on a 106 000
    character file is a wall, not a diagnosis.
    """


@dataclass(frozen=True)
class Section:
    """One ``## `` section, with the EXACT slice of the plan it occupies.

    ``start``/``end`` are character offsets into the original text and ``body`` is literally
    ``text[start:end]`` - everything from the ``## `` line up to (not including) the next ``## ``
    line, or the end of the file. Trailing blank lines and a trailing ``---`` belong to the section
    that precedes them; that rule is arbitrary but TOTAL, which is what byte-exactness needs.
    """

    title: str
    first_line: int
    last_line: int
    start: int
    end: int
    body: str


def arc_name(member: str) -> str:
    """``plan/c/arc-1.md`` -> ``c/arc-1.md`` - the namespace the door's index really speaks.

    ``index_problems`` names arcs relative to ``plan/`` and ``PlanItem.source`` names them relative to
    the DOOR; the two are one prefix apart and the pair has already drifted once in this repo (see
    ``merge_plan``, which now refuses a mismatched pair outright). One conversion, in one place.
    """
    prefix = f"{ARCS_DIRNAME}/"
    return member[len(prefix) :] if member.startswith(prefix) else member


@dataclass(frozen=True)
class ArcFile:
    """One file of ``plan/``, as it sits on the disk - the unit a FOLDER-shaped plan archives.

    ``text`` is the file's EXACT bytes (read with newline translation off), because they travel into
    the archive untouched: for an arc there is no slicing at all, which is why the byte guarantee here
    rests on the door's line and on the archive's own marker rather than on offset arithmetic.
    """

    #: The arc's path relative to the DOOR's folder - ``plan/arc-c.md``.
    member: str
    text: str

    @property
    def name(self) -> str:
        """The arc's name relative to ``plan/`` - what the door's index entry points at."""
        return arc_name(self.member)

    @property
    def stem(self) -> str:
        """The file name without ``.md`` - where the archive's own name comes from.

        The arc already HAS a name, chosen when it was created and pointed at by the door; deriving a
        second one from its title would give two names for one file and no reason to prefer either.
        """
        return self.name.rsplit("/", 1)[-1].removesuffix(".md")


def index_entries(door: str, name: str) -> tuple[tuple[int, int, int], ...]:
    """Every line of ``door`` that DECLARES the arc ``name`` - ``(line, start, end)`` char offsets.

    ``end`` includes the line's ending, so ``door[start:end]`` is the whole line and replacing that
    slice needs no arithmetic about where a newline sits.

    Declaration, not mention, and the distinction is :func:`~.plan_format._declares` itself rather
    than a rule written again here: a door may MENTION any path it likes in prose (``- see
    plan/arc-c.md for the details``), and removing a sentence because it names a file would be exactly
    the rewrite this module exists to prevent. What must be replaced is the line the staleness check
    would turn into an ``index_sans_fichier`` the moment the file leaves - i.e. a declaration, no more
    and no less. Fenced examples are skipped for the same reason and by the same walk.
    """
    bare = door.splitlines()
    keep = door.splitlines(keepends=True)
    live = [alive for _, _, alive in _outside_code(bare)]
    found: list[tuple[int, int, int]] = []
    offset = 0
    for index, raw in enumerate(keep):
        line = bare[index]
        if live[index]:
            for match in _ARC_REF_RE.finditer(line):
                if _same_name(match.group(1).strip(), name) and _declares(
                    line, match.start(), match.end()
                ):
                    found.append((index + 1, offset, offset + len(raw)))
                    break
        offset += len(raw)
    return tuple(found)


@dataclass(frozen=True)
class ArchiveMove:
    """One unit that WOULD move: where it came from, where it goes, and what replaces it.

    ``start``/``end`` always point into the file handed to :func:`plan_archive` - the slice the
    pointer replaces. For a SECTION that slice is the section itself and ``body`` is those same bytes;
    for an ARC it is the door's one-line index entry, and ``body`` is the arc FILE's bytes, which
    never appeared in the door at all. ``origin`` is what tells the two apart, and it is the arc's
    path rather than a flag so it can also say WHICH file to move.
    """

    title: str
    first_line: int
    last_line: int
    start: int
    end: int
    body: str
    filename: str
    link: str
    pointer: str
    idents: tuple[str, ...]
    #: The arc this came from (``plan/arc-c.md``), or ``""`` when the bytes came from the plan itself.
    origin: str = ""
    #: The EXACT index-entry line the pointer replaces, ending included - ``""`` for a section.
    entry: str = ""

    @property
    def lines(self) -> int:
        """How many lines leave the plan - the number the user actually feels."""
        return self.last_line - self.first_line + 1

    @property
    def where(self) -> str:
        """Where the bytes come from, in the words that fit the UNIT - a span, or a whole file.

        One sentence, two callers: the report the user reads and the archive's own header. Written
        twice, the header would keep claiming "lines 1 to 96" of a door that never held those lines.
        """
        if self.origin:
            return f"the arc `{self.origin}` in full · {self.lines} lines"
        return f"lines {self.first_line} to {self.last_line} · {self.lines} lines"


@dataclass(frozen=True)
class ArchiveRefusal:
    """One unit that declares itself closed and will NOT be moved, with the reason named."""

    title: str
    first_line: int
    reason: str
    detail: str
    #: The arc the refused unit lives in - ``""`` when it is a section of the file handed in. Same
    #: reason as ``PlanProblem.source``: "ligne 12" stopped being a location once a plan spans files.
    source: str = ""

    @property
    def label(self) -> str:
        """The reason in words - the only place a refusal token becomes a sentence."""
        return REFUSAL_LABEL[self.reason]

    @property
    def where(self) -> str:
        """Where to go and look - the file when there is one, and always the line."""
        return (
            f"`{self.source}` ligne {self.first_line}"
            if self.source
            else f"ligne {self.first_line}"
        )


@dataclass(frozen=True)
class ArchivePlanning:
    """What one run WOULD do - computed whole, verified whole, and only then written.

    ``sections`` and ``total_lines`` are here for the same reason ``PlanReading`` publishes its prose
    residual: a report that says "3 arcs" about a 16-section file looks like success while 13 were
    never accounted for.
    """

    source: str
    today: str
    commit: str
    dirty: bool
    original: str
    remaining: str
    moves: tuple[ArchiveMove, ...]
    refusals: tuple[ArchiveRefusal, ...]
    sections: int
    total_lines: int
    #: The arc files this run examined - empty for a plan that is one file.
    arcs: tuple[ArcFile, ...] = ()
    #: Every name under ``plan/`` the door's index must account for (arcs AND nested doors), relative
    #: to ``plan/``. Nested doors are in here and never in ``arcs``: they are plans of their own, so
    #: they must stay indexed and must never be archived as if they were arcs of this one.
    indexed: tuple[str, ...] = ()

    @property
    def moved_lines(self) -> int:
        """Total lines of plan material that would move - the number the user actually feels."""
        return sum(move.lines for move in self.moves)

    @property
    def moved_from_file(self) -> int:
        """Lines that leave THIS file - sections only. An arc's lines were never in the door.

        The two numbers were one, and the one was wrong the first time a door archived an arc: the
        report announced *"108 lines (385.7 % of the file)"* about a 28-line door, because the arc's
        length was being divided by the length of a file that never held it. The same class was
        already paid for once here (*"62.5 % of the plan"* about one arc among several), which is why it
        is a second FIELD and not a second formula at the call site: a ratio whose numerator and
        denominator come from different files is a number nobody can check.
        """
        return sum(move.lines for move in self.moves if not move.origin)

    @property
    def units(self) -> int:
        """How many things could possibly move - the sections of this file, plus its arcs."""
        return self.sections + len(self.arcs)

    @property
    def not_candidates(self) -> int:
        """Units that never claimed to be closed - the published residual."""
        return self.units - len(self.moves) - len(self.refusals)

    @property
    def reference(self) -> str:
        """The bytes the reconstruction must give back: this file, each moved ARC inlined in it.

 **Built from what was READ, never from what the run produced**, and that is the whole
 reason it is computed here rather than carried as a field. For a section the reference is
 simply the original file. For an arc there are TWO files, so the thing to prove is "the door
 lost exactly its index entry AND the archive holds exactly the arc's bytes" - which is one
 equality once the arc's own bytes are put back where its entry sits.

 The bodies come from :attr:`arcs` (the disk) and not from ``move.body`` (this module's copy):
 derive the reference from the artefact it checks and a corrupted body cancels itself out on
 both sides. The place is found by SEARCHING for the entry line, not by reusing the offsets
 ``remaining`` was cut with, for the same reason - offsets that are wrong in the same way twice
 agree with each other. What the search cannot promise on its own (that the line found is
 really this arc's entry) is what :func:`verify_roundtrip` re-derives from the reader.
 """
        bodies = {arc.member: arc.text for arc in self.arcs}
        text = self.original
        for move in self.moves:
            if move.origin:
                text = text.replace(move.entry, bodies[move.origin], 1)
        return text

    def archive_text(self, move: ArchiveMove) -> str:
        """The EXACT bytes that would land in ``move.filename`` - header, marker, then the body.

        The verifier reads the body back out of THIS string, not out of ``move.body``: the thing
        proven must be the thing written.
        """
        etat = f"`{self.commit}`"
        if self.dirty:
            etat += " *(working tree dirty at that moment — the SHA does not describe everything)*"
        header = "\n".join(
            [
                f"# Archive — {move.title}",
                "",
                f"> Moved out of `{self.source}` — {move.where},",
                f"> on {self.today}, repo at {etat}.",
                ">",
                "> The body below is **the original text, byte for byte**: nothing has been",
                "> reformulated, reordered or recompacted. This header is the ONLY thing",
                "> `make plan-archiver` wrote. The plan keeps a one-line pointer to here.",
                "",
                "",
            ]
        )
        return header + VERBATIM_MARKER + move.body


def split_sections(text: str) -> tuple[Section, ...]:
    """Cut the plan into its ``## `` sections, by character offset, losing nothing.

    ``splitlines(keepends=True)`` rather than a multiline regex: the parts concatenate back to the
    original string exactly, including ``\\r\\n``, a final line without a newline, and the exotic
    breaks ``str.splitlines`` recognises. Offsets computed by summing those parts are therefore
    exact by construction - which is the only reason a slice can be trusted as "the same bytes".

    Line numbers agree with :func:`~mnemosyne.production.plan_format.read_plan` because both split
    the same way and both use ``_SECTION_RE``, imported rather than copied. Both share the same
    blindness too: a ``## `` line inside a fenced code block looks like a section here as well. That
    is not repaired here (it would make the two disagree, which is worse); it is REFUSED downstream
    by the odd-fence check, so a wrong boundary can never reach the disk.
    """
    lines = text.splitlines(keepends=True)
    heads: list[tuple[int, int, str]] = []
    offset = 0
    for index, raw in enumerate(lines):
        found = _SECTION_RE.match(raw)
        if found is not None:
            heads.append((index + 1, offset, found.group(1)))
        offset += len(raw)

    sections: list[Section] = []
    for position, (line_no, start, title) in enumerate(heads):
        if position + 1 < len(heads):
            next_line, end, _ = heads[position + 1]
            last_line = next_line - 1
        else:
            end, last_line = len(text), len(lines)
        sections.append(Section(title, line_no, last_line, start, end, text[start:end]))
    return tuple(sections)


def title_statuses(title: str) -> tuple[frozenset[str], frozenset[str]]:
    """The closed and open statuses a section title declares, as ``(closed, open)``.

 A title is not a bullet, so the reader next door assigns it no status at all - but the writers of
 this repo put the state THERE (``## ARC F - The named debts ``, ``## ARC G - PAUSED``).
 Every status glyph in the title counts, wherever it sits, because that is how they write.

 Which makes the AMBIGUOUS case real rather than theoretical, and it is in the file today:
 ``## ARC C - The UI *(C1-C3 + C7 ; C4-C6 out of my hands)*`` carries both. A naive "contains
 " rule makes an arc in progress a candidate for archiving. Returning both sets lets the caller
 refuse by name instead of guessing which glyph wins - guessing would make this module the author
 of a state nobody wrote.

 No variation-selector cleaning here, and that is a MEASURED removal, not an oversight. This
 first called ``_despecify`` - until a sabotage that deleted the call left every test green: the
 test is character-wise membership, and ```` is ```` followed by U+FE0F, so the selector is
 simply never looked at. A dead guarantee wearing a live name is worse than none, because a reader
 believes the case is handled. It is handled - by the shape of the test, which is what
 :func:`test_un_selecteur_de_variation_ne_cache_pas_le_glyphe_du_titre` now pins. Rewrite this as
 a substring search over the whole title and the cleaning becomes necessary again.
 """
    found = {STATUS_BY_GLYPH[char] for char in title if char in STATUS_BY_GLYPH}
    return frozenset(found & CLOSED_STATUSES), frozenset(found & OPEN_STATUSES)


def _fold(title: str) -> str:
    """One title -> one ASCII, lower-case, hyphen-joined fragment. No truncation, no fallback."""
    folded = unicodedata.normalize("NFKD", title)
    stripped = "".join(char for char in folded if not unicodedata.combining(char))
    ascii_only = stripped.encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"[^a-z0-9]+", "-", ascii_only).strip("-")


def title_head(title: str) -> str:
    """The part of a ``## `` title that NAMES it - everything before the first status glyph.

    Measured on the 14 glyph-bearing titles of this repository's own top-level plan document: in 12
    of them everything after the glyph is metadata, not name - a date, a commit, a parenthetical. Public because two
    different tools need the same answer and a second split would be a second rule: :func:`slugify`
    names a file from it, and ``plan_convert`` matches ``GARDER=`` against it. That second caller is
    why it was extracted rather than left inline - matching the WHOLE title made ``GARDER="ARC B"``
    keep three sections instead of two, the third being an ``ARC I`` whose parenthetical happens to
    read *"born of arc B"*. A designation that reaches into prose designates the wrong thing.
    """
    return re.split(f"[{''.join(STATUS_BY_GLYPH)}]", title, maxsplit=1)[0]


def has_identity(title: str) -> bool:
    """Does this title yield a file name at all, or would :func:`slugify` INVENT one?

    The guard and the namer must read the same thing, and they were written differently: a caller
    refusing on ``_fold(title)`` while ``slugify`` names from ``_fold(title_head(title))``. The two
    are in fact equivalent - a head is a PREFIX of its title, so an empty title fold forces an empty
    head fold - but an equivalence nobody states is an equivalence that stops holding on the next
    edit. Stated here, once, next to the fallback it describes.

    Named residual, since this returns True for it: ``## 日本語 2`` folds to ``2`` and gives an arc
    called ``2.md``. That is a POOR name, not an invented one; refusing it would refuse a title that
    really does carry an ASCII identity, and this module does not arbitrate what a good name is.
    """
    return bool(_fold(title_head(title)) or _fold(title))


def slugify(title: str) -> str:
    """An ASCII file-name fragment from a French title full of accents, glyphs and markdown.

 NFKD then drop combining marks: ``"Réparer le `distillateur`"`` must not become a file nobody
 can type. The fold is for the FILE NAME only - the title itself travels verbatim into the pointer
 and into the archive's own heading, accents, glyphs, backticks and all.

 **The name stops at the status glyph, because that is where the writers stop naming.** Measured
 on the 14 glyph-bearing ``## `` titles of this repository's own top-level plan document: in 12 of them everything
 after the glyph is metadata, not name - a date, a commit, a parenthetical - and keeping it gives
 ``plan-2026-07-28-arc-f-les-dettes-nommees-2026-07-28-commit-9e15d1f.md``, which repeats the date
 the prefix already carries. The other 2 open ON the glyph (``## ARC G - PAUSED...``,
 ``## Heavy runs...``) and cutting there would leave nothing at all, so the rule falls back to
 the whole title rather than to a placeholder: the cut is an improvement, never a floor lowered.
 """
    slug = _fold(title_head(title)) or _fold(title)
    # A title made only of glyphs would slug to "" and produce `plan-2026-07-28-.md`: a name that
    # collides with the next such title and says nothing. Named, rather than empty.
    return slug[:_SLUG_MAX].strip("-") or "section"


def archive_filename(today: str, title: str) -> str:
    """``plan-<AAAA-MM-JJ>-<slug>.md`` - the date first, so ``ls`` sorts the memory by when."""
    return f"plan-{today}-{slugify(title)}.md"


def pointer_line(title: str, link: str, *, today: str) -> str:
    """The ONE line that stays in the plan where a section used to be - prose, never an item.

    Prose on purpose. An item would need a key and a status, i.e. a SECOND place where the arc's
    state is declared, and a second source of a state is exactly the defect this whole arc exists to
    remove. Prose is also what keeps it invisible to the reader next door: it is neither a bullet nor
    a heading, so it adds no item, no refusal, and no section.

    The title is reproduced VERBATIM - glyph included. The archive is one click away and its path is
    the link's own text, because a link whose destination is hidden is a link nobody audits.

    ONE shape for both units, and the residual is named rather than repaired: in a DOOR this line
    lands between two ``- `` index entries, so a renderer shows the list split in two around it. That
    is cosmetic - the reader counts it as prose, the index check never sees it, and the
    reconstruction depends on its exact bytes. A second, bullet-shaped pointer written just for doors
    would be a second statement of "what the trace looks like", i.e. a second thing that must stay in
    step with the marker :func:`verify_verbatim_roundtrip` searches for. This repo has paid for that
    trade before; the cost of one ugly line is smaller than the cost of two shapes.
    """
    return f"> **Archived on {today}** · {title} → [{link}]({link})"


def _difference(expected: str, produced: str) -> str:
    """Where two strings first diverge - offset, line, and the two characters, named."""
    limit = min(len(expected), len(produced))
    index = next((i for i in range(limit) if expected[i] != produced[i]), limit)
    if index == limit:
        return (
            f"different lengths: original {len(expected)} characters, "
            f"reconstruction {len(produced)} — identical up to character {index}"
        )
    line = expected.count("\n", 0, index) + 1
    return (
        f"divergence at character {index} (line {line} of the original): "
        f"original {expected[index]!r}, reconstruction {produced[index]!r}"
    )


def _fence_trouble(text: str, section: Section) -> str:
    """Why this section's boundaries cannot be trusted - ``""`` when they can.

 TWO conditions, and the second one is the whole point. Checking only the section's own body
 closed exactly HALF the class: on ``...\\n```markdown\\n## ARC faux \\n...`` the real arc was
 refused (odd count in its body) while the fake heading INSIDE the fence became its own section,
 counted zero fences, and was archived - the wrong bytes moved, under a title that is a code
 sample. A cut is safe only if the heading opens outside any fence AND the section closes every
 fence it opens.
 """
    before = len(_FENCE_RE.findall(text[: section.start]))
    inside = len(_FENCE_RE.findall(section.body))
    if before % 2:
        return "its `## ` title is INSIDE a code block — this is not a section"
    if inside % 2:
        return f"{inside} ``` delimiter(s) in the section: it ends inside an open block"
    return ""


def _lying_items(reading, section: Section) -> list[str]:
    """Identities inside ``section`` whose status is not a closed one, with their status label."""
    return [
        f"{item.ident or '(no identity)'} line {item.line} → {item.label}"
        for item in reading.items
        if section.first_line <= item.line <= section.last_line
        and item.status not in CLOSED_STATUSES
    ]


def plan_archive(
    text: str,
    *,
    source: str,
    today: str,
    commit: str,
    dirty: bool = False,
    taken: frozenset[str] | set[str] = frozenset(),
    link_dir: str = ARCHIVE_DIRNAME,
    arcs: tuple[ArcFile, ...] = (),
    indexed: tuple[str, ...] = (),
) -> ArchivePlanning:
    """Decide what would move, what is refused, and what the plan would look like. Writes nothing.

    ``taken`` is the set of archive file names that already exist on disk, and ``arcs``/``indexed``
    are what lies in ``plan/`` - all passed in rather than read, so the whole decision stays testable
    without a filesystem. ``arcs`` empty is the mono-file plan, judged exactly as before.

    **The ORDER of the checks is deliberate, because the first one to bite becomes the cause the user
    reads.** Ambiguity first: an arc whose title declares two states never claimed to be closed, and
    listing its open items as "a lie" would accuse it of the wrong thing. Then the fence check: a cut
    that fell inside a code block makes every later judgement rest on the wrong bytes. Then the lie,
    which is the substantive refusal. Then unreadable lines, then the mechanical name conflicts -
    last, because a name is fixable and a lie is not. The arc pass below runs the SAME sequence over
    the same predicates, so widening the unit could not quietly widen what passes.
    """
    reading = read_plan(text)
    sections = split_sections(text)
    moves: list[ArchiveMove] = []
    refusals: list[ArchiveRefusal] = []
    planned: set[str] = set()

    for section in sections:
        closed, opened = title_statuses(section.title)
        if not closed:
            continue  # never claimed to be over - counted in the residual, not refused

        if opened:
            both = " + ".join(sorted(STATUS_LABEL[token] for token in closed | opened))
            refusals.append(
                ArchiveRefusal(
                    section.title, section.first_line, "titre_ambigu", f"it declares: {both}"
                )
            )
            continue
        if trouble := _fence_trouble(text, section):
            refusals.append(
                ArchiveRefusal(section.title, section.first_line, "borne_incertaine", trouble)
            )
            continue
        lying = _lying_items(reading, section)
        if lying:
            refusals.append(
                ArchiveRefusal(section.title, section.first_line, "arc_ment", " · ".join(lying))
            )
            continue
        unreadable = [
            f"line {problem.line}: {problem.kind} — {problem.detail}"
            for problem in reading.problems
            if section.first_line <= problem.line <= section.last_line
        ]
        if unreadable:
            refusals.append(
                ArchiveRefusal(
                    section.title, section.first_line, "ligne_illisible", " · ".join(unreadable)
                )
            )
            continue
        filename = archive_filename(today, section.title)
        if filename in taken:
            refusals.append(
                ArchiveRefusal(section.title, section.first_line, "archive_existe", filename)
            )
            continue
        if filename in planned:
            refusals.append(
                ArchiveRefusal(section.title, section.first_line, "collision_de_nom", filename)
            )
            continue
        planned.add(filename)
        link = f"{link_dir}/{filename}" if link_dir else filename
        moves.append(
            ArchiveMove(
                title=section.title,
                first_line=section.first_line,
                last_line=section.last_line,
                start=section.start,
                end=section.end,
                body=section.body,
                filename=filename,
                link=link,
                pointer=pointer_line(section.title, link, today=today),
                idents=tuple(
                    item.ident
                    for item in reading.items
                    if section.first_line <= item.line <= section.last_line
                ),
            )
        )

    for arc in arcs:
        arc_sections = split_sections(arc.text)
        arc_reading = read_plan(arc.text)
        # The arc as ONE unit, so the very predicates the section pass uses read it whole: a lying
        # item anywhere in the file is a lying item of the arc, and the formatting of a refusal has
        # one home. Widening the unit must not widen what a refusal is allowed to miss.
        whole = Section(arc.member, 1, len(arc.text.splitlines()), 0, len(arc.text), arc.text)
        closed: set[str] = set()
        opened: set[str] = set()
        for section in arc_sections:
            shut, open_ = title_statuses(section.title)
            closed |= shut
            opened |= open_
        if not closed:
            continue  # never claimed to be over - counted in the residual, not refused

        title = arc_sections[0].title
        entries = index_entries(text, arc.name)
        # ASYMMETRIC ON PURPOSE, and this is the guard against the hole the wider unit digs. The
        # door carries a COPY of each arc's title in its index entry, and a copy rots (this repo's
        # own measure: a hand-copied number ages in three days). So the door may VETO - a `` there
        # over a `` in the arc is two declarations disagreeing, and this module never arbitrates
        # between two declarations of one state - but it may never AUTHORISE: only the arc's own
        # `## ` title can make it a candidate at all, so a stale door can never archive a live arc.
        for _, start, end in entries:
            opened |= title_statuses(text[start:end])[1]

        if opened:
            both = " + ".join(sorted(STATUS_LABEL[token] for token in closed | opened))
            refusals.append(
                ArchiveRefusal(title, 1, "titre_ambigu", f"it declares: {both}", arc.member)
            )
            continue
        trouble = ""
        for section in arc_sections:
            if trouble := _fence_trouble(arc.text, section):
                break
        if trouble:
            refusals.append(ArchiveRefusal(title, 1, "borne_incertaine", trouble, arc.member))
            continue
        lying = _lying_items(arc_reading, whole)
        if lying:
            refusals.append(ArchiveRefusal(title, 1, "arc_ment", " · ".join(lying), arc.member))
            continue
        unreadable = [
            f"line {problem.line}: {problem.kind} — {problem.detail}"
            for problem in arc_reading.problems
        ]
        if unreadable:
            refusals.append(
                ArchiveRefusal(title, 1, "ligne_illisible", " · ".join(unreadable), arc.member)
            )
            continue
        # The door must designate this arc by exactly ONE entry, and that entry's bytes must occur
        # exactly once in the door. Both halves matter and neither implies the other: zero entries
        # means the pointer would replace nothing (and the arc's memory would leave no trace at all),
        # two entries means the second becomes an `index_sans_fichier` the moment the file goes, and
        # a line whose TEXT repeats elsewhere makes "put the arc back where its entry was" ambiguous
        # - which is the reconstruction this whole command rests on.
        occurrences = text.count(text[entries[0][1] : entries[0][2]]) if entries else 0
        if len(entries) != 1 or occurrences != 1:
            refusals.append(
                ArchiveRefusal(
                    title,
                    entries[0][0] if entries else 0,
                    "index_incertain",
                    f"{len(entries)} index entr(y/ies) for `{arc.member}` in the door"
                    + (
                        f", and that line appears there {occurrences} times" if occurrences > 1 else ""
                    ),
                    arc.member,
                )
            )
            continue
        filename = archive_filename(today, arc.stem)
        if filename in taken:
            refusals.append(ArchiveRefusal(title, 1, "archive_existe", filename, arc.member))
            continue
        if filename in planned:
            refusals.append(ArchiveRefusal(title, 1, "collision_de_nom", filename, arc.member))
            continue
        planned.add(filename)
        link = f"{link_dir}/{filename}" if link_dir else filename
        _, start, end = entries[0]
        moves.append(
            ArchiveMove(
                title=title,
                first_line=1,
                last_line=whole.last_line,
                start=start,
                end=end,
                body=arc.text,
                filename=filename,
                link=link,
                pointer=pointer_line(title, link, today=today),
                idents=tuple(item.ident for item in arc_reading.items),
                origin=arc.member,
                entry=text[start:end],
            )
        )

    # Cut from the END so the offsets of the sections still to cut stay valid - computing fresh
    # offsets after each edit would put arithmetic between the bytes and their proof.
    remaining = text
    for move in sorted(moves, key=lambda move: move.start, reverse=True):
        remaining = remaining[: move.start] + move.pointer + "\n" + remaining[move.end :]

    return ArchivePlanning(
        source=source,
        today=today,
        commit=commit,
        dirty=dirty,
        original=text,
        remaining=remaining,
        moves=tuple(moves),
        refusals=tuple(refusals),
        sections=len(sections),
        total_lines=len(text.splitlines()),
        arcs=tuple(arcs),
        indexed=tuple(indexed),
    )


@dataclass(frozen=True)
class VerbatimMove:
    """One block that LEFT a text: what marks its place, and the file that now holds its bytes.

    The neutral shape of "moved, not rewritten" - deliberately naming neither an archive nor an arc,
    because :func:`verify_verbatim_roundtrip` is the single proof both of them rest on.
    """

    #: What the refusal will name, so a human knows WHICH block failed.
    title: str
    #: The exact block left behind in the container, newline included. Must appear there exactly once.
    marker: str
    #: The exact bytes of the file that receives the body - the thing PROVEN is the thing WRITTEN.
    written: str


def verify_verbatim_roundtrip(
    container: str,
    moves: tuple[VerbatimMove, ...],
    original: str,
    *,
    marker_name: str,
    container_name: str,
    written_name: str,
) -> None:
    """Prove a verbatim move loses NOTHING, or raise. The one guarantee everything else rests on.

    The proof runs backwards through the artefacts that will actually be written: recover each body
    out of the file that will hold it by splitting on :data:`VERBATIM_MARKER`, put it back where its
    marker sits - located by SEARCHING for that block, never by remembering an index - and demand the
    original file back, character for character.

    Searching rather than remembering is what makes this bite instead of confirming itself. It also
    forces a property worth having: a marker must appear exactly ONCE in the container, so two
    identical titles cannot leave an ambiguous placeholder behind.

    **One home, two callers, and that is the point.** Archiving (a closed arc leaves a prose pointer
    and its bytes go to ``archive/``) and converting a plan into a folder (a section leaves an index
    entry and its bytes go to ``plan/``) are the SAME move over different nouns. A second copy of this
    loop is a second thing that can drift away from the guarantee - and this guarantee is the only
    reason the user's rule 1 (*"you write it as-is, exactly as-is"*) is a barrier rather than
    a promise. Only the three NOUNS differ, so only the three nouns are passed in.
    """
    rebuilt = container
    for move in moves:
        seen = rebuilt.count(move.marker)
        if seen != 1:
            raise ArchiveMismatch(
                f'{marker_name} of "{move.title}" appears {seen} times in {container_name} '
                "(it must be there exactly once) — nothing was written."
            )
        parts = move.written.split(VERBATIM_MARKER, 1)
        if len(parts) != 2:
            raise ArchiveMismatch(
                f'{written_name} of "{move.title}" does not carry its verbatim mark - '
                "the body cannot be read back, so the move cannot be proven."
            )
        rebuilt = rebuilt.replace(move.marker, parts[1], 1)

    if rebuilt != original:
        raise ArchiveMismatch(
            "the reconstruction does not give the original plan back — nothing was written. "
            + _difference(original, rebuilt)
        )


def verify_roundtrip(planning: ArchivePlanning) -> None:
    """Prove the archiving move loses NOTHING, or raise - :func:`verify_verbatim_roundtrip` on it.

    One extra question for an ARC, and it is the one the reconstruction cannot ask itself: the line
    the pointer replaces must really be that arc's index entry. The reconstruction alone cannot see
    it - it puts the arc's bytes back wherever the pointer sits, and a pointer sitting on the WRONG
    line is put back just as happily. So the removed line is handed BACK to the reader
    (:func:`index_entries` over those bytes alone), which is a derivation independent of the offsets
    the cut was made with. Fail-closed: nothing is written on a doubt.
    """
    for move in planning.moves:
        if move.origin and not index_entries(move.entry, arc_name(move.origin)):
            raise ArchiveMismatch(
                f'the line the pointer of "{move.title}" would replace does not declare '
                f"`{move.origin}` — the door would lose a line that is not its index entry. "
                f"Line aimed at: {move.entry.strip()!r} — nothing was written."
            )
    verify_verbatim_roundtrip(
        planning.remaining,
        tuple(
            VerbatimMove(move.title, move.pointer + "\n", planning.archive_text(move))
            for move in planning.moves
        ),
        planning.reference,
        marker_name="the pointer",
        container_name="the remaining plan",
        written_name="the archive",
    )


def verify_readability(planning: ArchivePlanning, *, role: str = ROLE_PLAN) -> None:
    """What is left behind must still be readable IN ITS ROLE, and gain no new refusal.

    This is the ``pre-commit`` barrier's own rule (``.githooks/pre-commit``), applied BEFORE the
    write rather than after it: a command that leaves the user with a plan his next commit will
    reject has not helped him. Refusals are compared as a multiset of ``(kind, detail)`` and not by
    count or by line, because every archived section shifts every later line number - comparing
    lines would report a change on every run and comparing counts would hide one refusal replacing
    another.

    ``role`` is what a plan being a FOLDER costs this check (D166). This function used to hand-write
    its own two-branch version of "readable" - the FOURTH copy of a rule the reader next door owns -
    and that copy required a cap AND an item of every text it saw. Measured consequence: archiving a
    closed section out of an ARC left a text with no cap (an arc has none, the door holds it), so the
    command refused a perfectly sane file; the same for a DOOR whose items all live in its arcs. One
    rule, one home: :func:`~.plan_format.unreadable_reasons` says what is missing AND says it in the
    words the user will read in ``make plans`` and in the hook.

    ``unreadable_reasons`` and not ``is_readable``: the latter folds in "carries no refusal at all",
    which would reject a plan that ALREADY carried one before the archiver ran, and would lose the
    delta below - the only thing that can name WHICH refusal the move created.
    """
    after = read_plan(planning.remaining)
    if reasons := unreadable_reasons(after, role=role):
        raise ArchiveMismatch(
            f"after archiving, this file would no longer be readable as a {role} "
            f"({' · '.join(reasons)}) — nothing was written."
        )
    before_kinds = Counter(
        (problem.kind, problem.detail) for problem in read_plan(planning.original).problems
    )
    new = Counter((problem.kind, problem.detail) for problem in after.problems) - before_kinds
    if new:
        detail = " · ".join(f"{kind} — {text}" for (kind, text), _ in sorted(new.items()))
        raise ArchiveMismatch(
            f"archiving would create {sum(new.values())} new reading refusal(s): {detail} "
            "— nothing was written."
        )
    verify_index(planning)


def verify_index(planning: ArchivePlanning) -> None:
    """A door that archived an arc must still INDEX exactly what remains in ``plan/``, or raise.

    The half of the barrier the reader of ONE file cannot see, and the one an archiver that moves
    whole files can break in both directions: leave the entry behind and the door names a file that
    is gone (``index_sans_fichier``); remove one entry too many and a live arc is named nowhere
    (``arc_hors_index``). Either one is a blocked commit at the pre-commit hook - i.e. the command
    would hand the user a plan his next commit refuses, which is the exact failure
    ``verify_readability`` exists to make impossible.

    Asked of :func:`~.plan_format.index_problems`, the very function the barrier calls, and compared
    as a multiset of ``(kind, detail)`` BEFORE and AFTER: a door that already carried a defect keeps
    it (this command is not an index fixer), and only what the run would CREATE is refused. Silent
    for a plan that is one file, which has no index to check.
    """
    if not planning.indexed:
        return
    gone = {arc_name(move.origin) for move in planning.moves if move.origin}
    before = Counter(
        (problem.kind, problem.detail)
        for problem in index_problems(planning.original, planning.indexed)
    )
    after = Counter(
        (problem.kind, problem.detail)
        for problem in index_problems(
            planning.remaining, tuple(name for name in planning.indexed if name not in gone)
        )
    )
    if new := after - before:
        detail = " · ".join(f"{kind} — {text}" for (kind, text), _ in sorted(new.items()))
        raise ArchiveMismatch(
            f"after archiving, the door's index would carry {sum(new.values())} new "
            f"refusal(s): {detail} — nothing was written."
        )


def filiation_problems(
    predecesseur: PlanReading,
    reading: PlanReading,
    *,
    retires: frozenset[str] = frozenset(),
) -> tuple[PlanProblem, ...]:
    """H4 - *"a promotion refuses until every unfinished item of the frozen plan is either picked
    back up, withdrawn by H1, or declared out of scope"*, word for word.

    ``predecesseur`` is the FROZEN plan (typically read from this repository's own dated archive
    folder - the file that
    ``reading.succede_a`` names, resolved by the caller, never by this function: it touches no disk
    at all, like every pure function in this module). ``reading`` is the plan that EXTENDS it.
    ``retires`` is the set of identifiers formally withdrawn - typically
    ``{ident for etat in RetraitLedger(...).all_states() if etat.applied for ident in etat.items}``
    (H1, ``plan_retrait.py``): an item withdrawn by the dedicated mechanism does not need to be cited
    a second time here.

    Three ways to be COUNTED, never two:

    * **``fait`` or ``clos``** (:data:`CLOSED_STATUSES`) - a ``clos`` item already carries, in its
      own status, the declaration *"will not be done, and that is decided"* (:data:`STATUS_LABEL`):
      that is exactly the shape "declared out of scope" takes in this format, with no need for a
      second field to say it again;
    * **picked back up by name** - its identifier is that of an item in the plan that SUCCEEDS it. An
      IDENTITY, never a mention: the same principle `A1` applies to a field, carried here at the
      level of the whole plan - an identifier CITED in another item's prose does not pick it back up;
    * **withdrawn by H1** - its identifier is in ``retires``.

    Any item of the predecessor that falls into NONE of the three is named, with its original line
    - *"a promotion that loses work in silence is a disguised deletion"*.
    """
    repris = {item.ident for item in reading.items if item.ident}
    found: list[PlanProblem] = []
    for item in predecesseur.items:
        if not item.ident or item.status in CLOSED_STATUSES:
            continue
        if item.ident in repris or item.ident in retires:
            continue
        found.append(
            PlanProblem(
                item.line,
                "item_perdu_a_la_promotion",
                f"{item.ident} ({STATUS_LABEL.get(item.status, item.status)}) — neither picked back "
                "up in the succeeding plan, nor withdrawn (H1), nor closed: a promotion that "
                "stays silent about it loses it",
                item.source,
            )
        )
    return tuple(found)
