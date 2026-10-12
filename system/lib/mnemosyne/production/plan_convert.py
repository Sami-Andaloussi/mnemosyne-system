"""Turn a plan that is one FILE into a plan that is a FOLDER — moving bytes, rewriting none.

D166, clause 4 of what the decision imposes: *"the conversion of existing plans moves bytes, it
never rewrites any."* The operator's own rule 1, word for word: *"strictly, you must never reword
what's written in the plans, you write it as is, exactly as is."* This module turns that sentence
into a barrier: every ``## `` section leaves the file as an exact slice, the door keeps one
INDEX ENTRY where the section stood, and :func:`verify_roundtrip` demands the original file back
character for character BEFORE anything reaches the disk.

**The index entry IS the pointer, and that is not a trick — it is the only shape that costs nothing.**
The archiver next door leaves a prose pointer where a closed arc used to be; here the line left behind
must ALSO satisfy clause 4 of D166 (*"the door's index is VERIFIED BY THE CODE"*). Writing two
lines — one to reconstruct with, one to be indexed by — would have created two things that can drift.
One line does both, and :func:`verify_readability` proves it by asking the READER, not by trusting
this module's idea of what an index looks like.

**Why the whole run refuses on any refusal, unlike the archiver.** Archiving moves a SUBSET and runs
again tomorrow; converting is a hinge that happens once. A half-converted plan is worse than an
unconverted one: the second run would meet its own ``plan/`` directory and refuse as ``deja_converti``,
leaving the human with a plan split by a rule nobody chose. So refusals are named per section and
block the run entire.

**What this module never decides.** Which sections stay in the door is a JUDGEMENT (D166 measured that
``À LA REPRISE`` — 213 lines, touched by 20 commits out of 53 — is already the door), and a tool that
guesses becomes the author of a layout nobody chose. It is declared, per run, by ``keep`` — and a
``keep`` matching no section is a REFUSAL, never a silent no-op.

Non-destructive (invariant 2): the source file is never deleted. It BECOMES the door, in place, under
its own name — ``PLAN_COURANT.md`` is a legal door name precisely so this conversion does not have to
be a rename as well (see :data:`~mnemosyne.production.plan_format.DOOR_FILENAMES`). Renaming a tracked
path is a separate, human gesture, and the report names it.

Code, docstrings and every refusal the operator reads are English (D117); only the plan-format
tokens the reader parses keep their canonical spelling.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from typing import Final

from .plan_archive import (
    VERBATIM_MARKER,
    ArchiveMismatch,
    VerbatimMove,
    _fence_trouble,
    has_identity,
    slugify,
    split_sections,
    title_head,
    verify_verbatim_roundtrip,
)
from .plan_format import (
    ARCS_DIRNAME,
    ROLE_PLAN,
    index_problems,
    is_readable,
    merge_plan,
    read_plan,
    unreadable_reasons,
)

#: The passation note the operator asked for — *"what was moved, where, and when"*. Beside the
#: door, NOT inside ``plan/``: a ``.md`` under ``plan/`` is an ARC to the reader, so a note dropped
#: there would have to be indexed like an arc, counted like an arc, and judged like an arc — three
#: ways for a passation record to break a plan. Beside the door it belongs to nothing and can break
#: nothing.
NOTE_PREFIX: Final = "plan-passation"

#: Every refusal this module can name, and its sentence. Declared in one place so the report,
#: the tests and the spec cannot drift apart — and so each one can be shown to be PRODUCIBLE: a name
#: is not a test, and a refusal no input can trigger is a promise nobody keeps.
REFUSAL_LABEL: Final = {
    "deja_converti": "this plan is ALREADY a folder — `plan/` exists and carries arcs",
    "plan_illisible": "the plan is not readable BEFORE conversion — a broken plan is not converted",
    "borne_incertaine": "a cut would land inside a code block (an odd number of ```)",
    "titre_sans_identite": "this title yields no file name — there is nothing to call the arc",
    "collision_de_nom": "two sections of this plan produce the same file name",
    "garder_introuvable": "no section carries what `GARDER=` designates",
    "note_existe": "the passation note already exists — nothing is ever overwritten (inv. 2)",
}

#: A refusal that is about the PLAN and not about one section. ``0`` rather than a real line for the
#: same reason ``PlanProblem.where`` prints "(the folder)": a number that looks like a location and is
#: not one is a refusal nobody can act on.
WHOLE_PLAN: Final = 0


@dataclass(frozen=True)
class ArcMove:
    """One ``## `` section that WOULD become a file: where it came from, and what replaces it."""

    title: str
    first_line: int
    last_line: int
    start: int
    end: int
    body: str
    #: The arc's name relative to ``plan/`` — ``arc-c-l-ui.md``. The namespace ``index_problems``
    #: speaks.
    filename: str
    #: The arc's path relative to the DOOR's folder — ``plan/arc-c-l-ui.md``. The namespace
    #: ``PlanItem.source`` and ``merge_plan`` speak, and ``merge_plan`` refuses a pair that disagrees.
    member: str
    #: The single line that stays in the door: the index entry AND the reconstruction marker.
    entry: str

    @property
    def lines(self) -> int:
        """How many lines leave the door — the number the operator actually feels."""
        return self.last_line - self.first_line + 1


@dataclass(frozen=True)
class ConvertRefusal:
    """One reason the conversion will not happen, named — with the section when there is one."""

    title: str
    first_line: int
    reason: str
    detail: str

    @property
    def label(self) -> str:
        """The reason in words — the only place a refusal token becomes a sentence."""
        return REFUSAL_LABEL[self.reason]


@dataclass(frozen=True)
class ConvertPlanning:
    """What one run WOULD do — computed whole, proven whole, and only then written."""

    source: str
    today: str
    commit: str
    dirty: bool
    original: str
    #: The bytes the door would carry: the original, with each moved slice replaced by its entry.
    door: str
    moves: tuple[ArcMove, ...]
    refusals: tuple[ConvertRefusal, ...]
    #: Titles of the sections deliberately left in the door by ``keep``. Published, never counted:
    #: "2 sections kept" cannot tell the operator WHICH, and that is the one thing they have to
    #: check.
    kept: tuple[str, ...]
    sections: int
    total_lines: int
    note_filename: str

    @property
    def blocked(self) -> bool:
        """Any refusal at all stops the WHOLE conversion — a half-converted plan is not a plan."""
        return bool(self.refusals)

    @property
    def moved_lines(self) -> int:
        """Total lines that would leave the door."""
        return sum(move.lines for move in self.moves)

    @property
    def door_lines(self) -> int:
        """What a session would read to see the cap and the index — the whole point of D166."""
        return len(self.door.splitlines())

    def arc_text(self, move: ArcMove) -> str:
        """The EXACT bytes that would land in ``plan/<name>`` — header, marker, then the body.

        The verifier reads the body back out of THIS string, not out of ``move.body``: the thing
        proven must be the thing written.
        """
        etat = f"`{self.commit}`"
        if self.dirty:
            etat += " *(working tree modified at that moment — the SHA does not describe it all)*"
        header = "\n".join(
            [
                f"# Arc — {move.title}",
                "",
                f"> Moved from `{self.source}` — lines {move.first_line} to {move.last_line},",
                f"> on {self.today}, repo at {etat}.",
                ">",
                "> The body below is **the original text, byte for byte**: nothing has been",
                "> reworded, renumbered or re-indented — not even the indentation. This header is the",
                "> ONLY thing `make plan-convertir` wrote. The door keeps a one-line index entry",
                "> pointing here.",
                "",
                "",
            ]
        )
        return header + VERBATIM_MARKER + move.body

    def note_text(self) -> str:
        """The passation note — *"what was moved, where, and when"* (the operator's rule 3).

        Prose and bullets, never a table: a section title may carry a ``|`` and would silently split
        a row into cells. It is written BESIDE the door, so nothing here is ever read as part of the
        plan — which is why it may name paths freely.
        """
        etat = f"`{self.commit}`" + (" *(working tree modified)*" if self.dirty else "")
        lines = [
            "# Passation — this plan has become a FOLDER",
            "",
            f"> On {self.today}, `{self.source}` became the **door** of a folder-shaped plan: the cap",
            f"> and the index stay there, every `##` section left for `{ARCS_DIRNAME}/`. Repo at"
            f" {etat}.",
            ">",
            "> **Not one byte was rewritten.** The reconstruction — door + arcs reassembled — gives",
            "> the original file back character for character, and it was verified BEFORE the first",
            "> write: otherwise `make plan-convertir` refuses and writes nothing.",
            "",
            f"## What was moved — {len(self.moves)} arc(s), {self.moved_lines} lines",
            "",
        ]
        for move in self.moves:
            lines += [
                f"- **{move.title}**",
                f"      lines {move.first_line} to {move.last_line} of the original "
                f"({move.lines} lines) → `{move.member}`",
            ]
        lines += ["", "## What stayed in the door", ""]
        if self.kept:
            lines += [f"- {title}" for title in self.kept]
        else:
            lines.append("- (no section — the door keeps only its title, its cap and the index)")
        lines += [
            "",
            f"The door goes from {self.total_lines} to {self.door_lines} lines.",
            "",
            "## What is left to do, and what the tool does not do",
            "",
            "- Renaming the door to `PLAN.md` if it still carries a legacy name (D166, clause 1) is",
            "  a path move tracked by git — so **a human gesture**, never a tool's:",
            "  `git mv <door> PLAN.md`.",
            "- This note is part of no plan: it lives BESIDE the door, never inside",
            f"  `{ARCS_DIRNAME}/`, where the reader would take it for an arc.",
            "",
        ]
        return "\n".join(lines).rstrip() + "\n"


def index_entry(member: str, title: str) -> str:
    """The ONE line that stays in the door where a section used to be — index entry AND marker.

    Its shape is not a preference, it is what the reader :mod:`~mnemosyne.production.plan_format`
    actually requires, and each clause pays for itself:

    * it opens with ``- `` then a BACKTICK, so ``read_plan`` sees prose — no bold token opens it, so
      it can be neither an item nor a refused item, whatever the title behind it says;
    * the path sits in ENTRY POSITION (right after the list marker, backtick being admitted
      decoration), which is what makes it a DECLARATION rather than a mention for the staleness check
      ``index_sans_fichier`` (D167);
    * the path is written whole (``plan/…md``), which is what the completeness check
      ``arc_hors_index`` looks for.

    The title travels VERBATIM behind it — glyphs, backticks, accents and all — so the door reads as a
    table of contents rather than a list of file names. That the shape is right is not asserted here:
    :func:`verify_readability` asks the reader itself, on the bytes that would be written.
    """
    return f"- `{member}` — {title}"


def _matches(needle: str, title: str) -> bool:
    """Does ``needle`` designate this section? Substring of its NAME, NFC, case-folded.

 Substring rather than equality because the titles of this repo run to 90 characters and carry
 glyphs, markdown and parentheticals — an exact match is a rule nobody can type. NFC because macOS
 stores 80 of this repo's paths decomposed, and a title typed in an editor is composed: without it
 ``GARDER="À LA REPRISE"`` would match nothing and the tool would refuse a request that is correct.

 **Of its NAME, and that word was measured.** Matching the whole title made ``GARDER="ARC B"``
 keep THREE sections of the living plan instead of two — the third being ``ARC I — Repair the
 `distiller` *(born of arc B …)*``, designated by prose inside its own parenthetical. So the
 comparison runs against :func:`~.plan_archive.title_head`, the very fragment ``slugify`` names
 the arc's file from: what designates a section for keeping and what names its file are then the
 same string, and a designation can no longer reach into commentary.

 Residual, named rather than hidden: a needle matching SEVERAL sections keeps them all, and that
 is deliberate (keeping is the conservative side). It is never silent — the report NAMES every
 kept section, which is the only reason the over-match above was found at all.
 """
    return (
        unicodedata.normalize("NFC", needle).casefold()
        in unicodedata.normalize("NFC", title_head(title)).casefold()
    )


def plan_convert(
    text: str,
    *,
    source: str,
    today: str,
    commit: str,
    dirty: bool = False,
    arcs_present: tuple[str, ...] = (),
    keep: tuple[str, ...] = (),
    note_taken: bool = False,
) -> ConvertPlanning:
    """Decide what would move, what is refused, and what the door would look like. Writes nothing.

    ``arcs_present`` and ``note_taken`` are the disk's answers, passed IN rather than read, so the
    whole decision stays testable without a filesystem — the same discipline the archiver next door
    keeps for ``taken``.

    **The ORDER of the checks is deliberate, because the first one to bite becomes the cause the
    operator reads.** Already-a-folder first: on a converted plan every later question is about the
    wrong world. Then unreadable-before: converting a broken plan would scatter the breakage across
    five files and make it harder to find, not easier. Then the fences, because a ``## `` inside a
    code block makes every section boundary after it a lie — and that one is refused for the WHOLE
    file, not for the section, since a wrong boundary corrupts its neighbours too. Then ``keep``,
    which is about what the human asked for. Only then the per-section names, which are the fixable
    ones.
    """
    sections = split_sections(text)
    total_lines = len(text.splitlines())

    def nothing(refusals: list[ConvertRefusal]) -> ConvertPlanning:
        return ConvertPlanning(
            source=source,
            today=today,
            commit=commit,
            dirty=dirty,
            original=text,
            door=text,
            moves=(),
            refusals=tuple(refusals),
            kept=tuple(section.title for section in sections),
            sections=len(sections),
            total_lines=total_lines,
            note_filename=f"{NOTE_PREFIX}-{today}.md",
        )

    if arcs_present:
        return nothing(
            [
                ConvertRefusal(
                    source, WHOLE_PLAN, "deja_converti", ", ".join(sorted(arcs_present)[:5])
                )
            ]
        )
    reading = read_plan(text)
    if not is_readable(reading, role=ROLE_PLAN):
        why = list(unreadable_reasons(reading, role=ROLE_PLAN))
        why += [
            f"{problem.where} : {problem.kind} — {problem.detail}" for problem in reading.problems
        ]
        return nothing([ConvertRefusal(source, WHOLE_PLAN, "plan_illisible", " · ".join(why))])
    if note_taken:
        return nothing(
            [ConvertRefusal(source, WHOLE_PLAN, "note_existe", f"{NOTE_PREFIX}-{today}.md")]
        )

    fences = [
        ConvertRefusal(section.title, section.first_line, "borne_incertaine", trouble)
        for section in sections
        if (trouble := _fence_trouble(text, section))
    ]
    if fences:
        # The WHOLE file, not the section: a `## ` heading inside a fence is read as a section here
        # AND truncates the real section around it, so the bytes of its neighbours are already wrong.
        # Refusing only the fake one would move a real arc cut at a boundary nobody wrote.
        return nothing(fences)

    unknown = [
        ConvertRefusal(needle, WHOLE_PLAN, "garder_introuvable", needle)
        for needle in keep
        if not any(_matches(needle, section.title) for section in sections)
    ]
    if unknown:
        return nothing(unknown)

    refusals: list[ConvertRefusal] = []
    moves: list[ArcMove] = []
    kept: list[str] = []
    planned: dict[str, str] = {}
    for section in sections:
        if any(_matches(needle, section.title) for needle in keep):
            kept.append(section.title)
            continue
        if not has_identity(section.title):
            # `slugify` would fall back to the literal "section" here, which is a NAME the tool
            # invented — and two such titles would then silently collide. An identity this module
            # made up is exactly the guess it must refuse to make. The condition is ASKED of
            # `plan_archive`, which owns the fallback: a guard written in different words from the
            # namer it guards is a guard that stops matching it.
            refusals.append(
                ConvertRefusal(
                    section.title,
                    section.first_line,
                    "titre_sans_identite",
                    "no ASCII letter or digit to draw from it, even with the accents unfolded",
                )
            )
            continue
        filename = f"{slugify(section.title)}.md"
        if filename in planned:
            refusals.append(
                ConvertRefusal(
                    section.title,
                    section.first_line,
                    "collision_de_nom",
                    f"`{ARCS_DIRNAME}/{filename}` — already produced by \"{planned[filename]}\"",
                )
            )
            continue
        planned[filename] = section.title
        member = f"{ARCS_DIRNAME}/{filename}"
        moves.append(
            ArcMove(
                title=section.title,
                first_line=section.first_line,
                last_line=section.last_line,
                start=section.start,
                end=section.end,
                body=section.body,
                filename=filename,
                member=member,
                entry=index_entry(member, section.title),
            )
        )

    # Cut from the END so the offsets of the sections still to cut stay valid — computing fresh
    # offsets after each edit would put arithmetic between the bytes and their proof.
    door = text
    for move in sorted(moves, key=lambda move: move.start, reverse=True):
        door = door[: move.start] + move.entry + "\n" + door[move.end :]

    return ConvertPlanning(
        source=source,
        today=today,
        commit=commit,
        dirty=dirty,
        original=text,
        door=door,
        moves=tuple(moves),
        refusals=tuple(refusals),
        kept=tuple(kept),
        sections=len(sections),
        total_lines=total_lines,
        note_filename=f"{NOTE_PREFIX}-{today}.md",
    )


def verify_roundtrip(planning: ConvertPlanning) -> None:
    """Prove the conversion loses NOTHING, or raise — door + arcs must give the original file back.

    Declined from :func:`~mnemosyne.production.plan_archive.verify_verbatim_roundtrip`, which is the
    ONE implementation of "moved, not rewritten" in this repo. Only the nouns differ here: the marker
    left behind is an index entry, the container is the door, the file written is an arc.
    """
    verify_verbatim_roundtrip(
        planning.door,
        tuple(
            VerbatimMove(move.title, move.entry + "\n", planning.arc_text(move))
            for move in planning.moves
        ),
        planning.original,
        marker_name="the index entry",
        container_name="the door",
        written_name="the arc",
    )


def verify_readability(planning: ConvertPlanning) -> None:
    """The plan the conversion would leave must be readable BY THE READER ITSELF, or raise.

    **Asked of ``plan_format``, never asserted from this module's idea of an index.** The door, the
    arcs and the index check are folded exactly the way ``plan_registry.read_plan_tree`` and the
    pre-commit hook fold them — one ``ident_seen`` threaded through every file, ``merge_plan`` over
    ``(member, reading)`` pairs, ``index_problems`` over the arc names, ``ROLE_PLAN``. If those three
    ever disagreed, the conversion would produce a plan the barrier refuses, on the one commit where
    the human has nothing left to compare against.

    Run in dry-run too, so the proof is the run itself rather than a claim about a run.
    """
    seen: dict[str, str] = {}
    door = read_plan(planning.door, ident_seen=seen)
    arcs = tuple(
        (move.member, read_plan(planning.arc_text(move), origin=move.member, ident_seen=seen))
        for move in planning.moves
    )
    merged = merge_plan(
        door,
        arcs,
        extra=index_problems(
            planning.door, tuple(move.filename for move in planning.moves), folder_form=True
        ),
    )
    if reasons := unreadable_reasons(merged, role=ROLE_PLAN):
        raise ArchiveMismatch(
            f"after conversion this plan would no longer be readable ({' · '.join(reasons)}) — "
            "nothing was written."
        )
    if merged.problems:
        detail = " · ".join(
            f"{problem.where} : {problem.kind} — {problem.detail}" for problem in merged.problems
        )
        raise ArchiveMismatch(
            f"the converted plan would carry {len(merged.problems)} reading refusal(s) the original "
            f"did not have: {detail} — nothing was written."
        )
