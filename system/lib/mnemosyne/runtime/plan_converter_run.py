"""plan-convertir — a plan that is a FILE becomes a plan that is a FOLDER (D166 · C20-4).

The input/output half of :mod:`mnemosyne.production.plan_convert`, which holds every decision as pure
functions. This module owns exactly four side effects: read the plan, ask git for the repo's state,
print, and — only under ``--apply`` — write.

**Dry-run by default**, like ``make plan-archiver`` and ``make rangement``: it SAYS what it would do
and writes nothing (D92 — propose, never impose). Conversion is a HINGE, not a routine: it changes
the shape of the one file the user steers by, so they must be able to see it whole before it happens.

**Nothing is written until the reconstruction is proven.** Both verifiers run in dry-run too, so the
proof is the run itself rather than a claim about a run: if door + arcs reassembled do not give the
original file back character for character, or if the reader would refuse the result, the command
exits non-zero and no file is touched.

Order of writes under ``--apply``: arcs FIRST, note, door LAST. If a later step fails, the content
exists in two places and none is lost — the failure mode of a non-destructive tool must be
duplication, never a hole (invariant 2).

**What this command will not do**: erase or rename the source file. It BECOMES the door, in place,
under its own name — ``PLAN_COURANT.md`` is a legal door name for exactly that reason. Renaming a
tracked path to ``PLAN.md`` (D166, clause 1) is a git move and therefore a human gesture; the report
and the handover note both name it.

Run::

    make plan-convertir                                     # dry, on this repo's own plan
    make plan-convertir GARDER="RESUME HERE"                # this section stays in the door
    make plan-convertir PLAN="projects/example-project/PLAN.md"
    make plan-convertir APPLY=1                             # writes

Brick-free, no model, no network. Code & docstrings English (D117)."""

from __future__ import annotations

import argparse
import os
from datetime import date
from pathlib import Path

from ..production.plan_archive import ArchiveMismatch
from ..production.plan_convert import (
    NOTE_PREFIX,
    ConvertPlanning,
    plan_convert,
    verify_readability,
    verify_roundtrip,
)
from ..production.plan_format import ARCS_DIRNAME, DOOR_FILENAMES, PLAN_FILENAME
from .plan_archiver_run import repo_state

#: Repo root from this module (``system/lib/mnemosyne/runtime/plan_converter_run.py`` → parents[4]).
_REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_PLAN = _REPO_ROOT / "docs" / "PLAN.md"

#: What to DO about each refusal. Attached to the reason rather than left to the reader: a refusal
#: that names a problem without naming a gesture turns a tool into an obstacle — and every one of
#: these refuses precisely where a human must decide something a tool may not decide for him.
_GESTE: dict[str, str] = {
    "deja_converti": (
        "The gesture: none. This plan is already a folder — the conversion happens only once, and "
        "re-running it would overwrite arcs that were never written by us (inv. 2)."
    ),
    "plan_illisible": (
        "The gesture: make the plan readable first (`make plans` names it, the pre-commit hook "
        "refuses it). Converting a broken plan scatters the breakage across five files."
    ),
    "borne_incertaine": (
        "The gesture: close the code block. A `## ` inside a block is read as a "
        "section, so its NEIGHBORS' boundaries are wrong too — nothing gets cut here."
    ),
    "titre_sans_identite": (
        "The gesture: give this title at least one word made of letters. Without it, the tool would "
        "have to INVENT a file name — and two silent titles would end up carrying the same one."
    ),
    "collision_de_nom": (
        "The gesture: distinguish the two titles. Two sections produce the same file name, "
        "and the second would overwrite the first."
    ),
    "garder_introuvable": (
        "The gesture: fix `GARDER=`. No section carries it, so the request would have kept "
        "nothing — and would have done so in silence."
    ),
    "note_existe": (
        "The gesture: none, on this date. A handover note for today already exists — so a "
        "conversion has already happened, or was already attempted (inv. 2: nothing is ever overwritten)."
    ),
}


def arcs_on_disk(folder: Path) -> tuple[str, ...]:
    """Every ``.md`` already sitting under ``<folder>/plan/`` — what makes a plan ALREADY converted.

    Asked of the disk rather than of the door's text: a ``plan/`` directory that exists and holds
    arcs is the fact, whatever the door happens to say about it. Sorted, so a refusal reads the same
    from one run to the next.
    """
    arcs = folder / ARCS_DIRNAME
    if not arcs.is_dir():
        return ()
    try:
        return tuple(
            sorted(c.relative_to(arcs).as_posix() for c in arcs.rglob("*.md") if c.is_file())
        )
    except OSError:  # pragma: no cover - a tree that vanishes mid-walk
        return ()


def missing_plan_message(plan_path: Path) -> str:
    """What to say when the path handed in is not a file — and the gesture that fixes it.

    A folder is the most natural thing to hand a command about plan folders, so answering "no
    plan" while the door sits right inside it would be a refusal that lies about the world.
    """
    if not plan_path.is_dir():
        return f"No plan at `{plan_path}` — nothing to convert."
    door = next((name for name in DOOR_FILENAMES if (plan_path / name).is_file()), None)
    if door is None:
        return (
            f"`{plan_path}` is a folder with no door (`{'` / `'.join(DOOR_FILENAMES)}`) — "
            "it carries no plan to convert."
        )
    return (
        f"`{plan_path}` is a FOLDER, and the conversion works on the monolithic FILE. "
        f'The gesture: `make plan-convertir PLAN="{plan_path}/{door}"`.'
    )


def render(planning: ConvertPlanning, *, applied: bool) -> str:
    """The report the user reads — what would leave, what stays, what is REFUSED and why.

    What is DONE folds, what REMAINS shows. The refused sections carry their gesture in full; the
    kept ones are NAMED and not counted, because "2 sections kept" cannot tell the user which.
    """
    lines = [
        "# Mnémosyne · converting the plan into a folder",
        "",
        f"`{planning.source}` — {planning.total_lines} lines, {planning.sections} `##` sections. "
        f"Repo at `{planning.commit}`" + (" *(tree modified)*" if planning.dirty else "") + ".",
        "",
    ]

    if planning.refusals:
        lines += [
            f"## REFUSED — the conversion WILL NOT HAPPEN ({len(planning.refusals)} reason(s))",
            "",
        ]
        for refusal in planning.refusals:
            ou = "" if refusal.first_line == 0 else f" — line {refusal.first_line}"
            lines += [f"- **{refusal.title}**{ou}", f"      {refusal.label}"]
            if refusal.detail:
                lines.append(f"      {refusal.detail}")
            lines.append(f"      {_GESTE[refusal.reason]}")
        lines += [
            "",
            "*A conversion is a hinge: it happens whole or not at all. A plan "
            "converted halfway would collide with its own `plan/` on the next run.*",
            "",
        ]

    if planning.moves:
        verbe = "CONVERTED" if applied else "What would leave"
        lines += [
            f"## {verbe} — {len(planning.moves)} arc(s), {planning.moved_lines} lines out of the door",
            "",
        ]
        for move in planning.moves:
            lines += [
                f"- **{move.title}**",
                f"      lines {move.first_line} to {move.last_line} · {move.lines} lines "
                f"→ `{move.member}`",
                f"      the door keeps: `{move.entry[:96]}`",
            ]
        lines.append("")
    elif not planning.refusals:
        lines += ["## Nothing to convert", "", "This plan carries no `##` section to move out.", ""]

    if planning.kept:
        lines += ["## What STAYS in the door (requested via `GARDER=`)", ""]
        lines += [f"- {title}" for title in planning.kept]
        lines.append("")

    if planning.moves:
        gain = 100 - round(100 * planning.door_lines / max(planning.total_lines, 1))
        lines += [
            f"*The door would go from {planning.total_lines} to {planning.door_lines} lines "
            f"(−{gain} %) — that is what 'LLM friendly' means: a session working on one "
            "arc no longer pays for the whole project.*",
            "",
        ]

    if applied:
        lines += [
            f"**APPLIED** — {len(planning.moves)} arc(s) written to `{ARCS_DIRNAME}/`, handover "
            f"note `{planning.note_filename}`, door rewritten.",
            "",
            "Reconstruction verified **before** any write: door + arcs reassembled give back "
            "the original file, character for character.",
            "",
            f"ONE human gesture remains, one the tool does not perform: if the door still carries an "
            f"inherited name, `git mv {planning.source} <…>/{PLAN_FILENAME}` (D166, clause 1).",
            "",
        ]
    elif not planning.refusals:
        lines += [
            "**DRY — nothing was written.** The byte-for-byte reconstruction and the re-read of the "
            "converted plan have already been verified above.",
            "",
            "To apply: `make plan-convertir APPLY=1`",
            "",
        ]
    return "\n".join(lines).rstrip() + "\n"


def apply_planning(planning: ConvertPlanning, *, plan_path: Path) -> None:
    """Write the arcs, then the note, then the door. Called only after BOTH verifiers have passed.

    ``"x"`` mode on everything new, not ``"w"``: the existence checks in the pure planner happen
    before the report is even printed, and a file can appear in between. The last word on "never
    overwrite" belongs to the filesystem, not to a set computed earlier (invariant 2).

    ``newline=""`` on every handle, in both directions: Python's default translates ``\\n`` to
    ``os.linesep`` on write and collapses ``\\r\\n`` on read. Either one silently breaks the
    byte-for-byte guarantee this whole command is built on, on the first plan written on another
    machine — which is exactly the plan a conversion is most likely to meet.
    """
    folder = plan_path.parent
    (folder / ARCS_DIRNAME).mkdir(parents=True, exist_ok=True)
    for move in planning.moves:
        target = folder / ARCS_DIRNAME / move.filename
        with target.open("x", encoding="utf-8", newline="") as handle:
            handle.write(planning.arc_text(move))
    with (folder / planning.note_filename).open("x", encoding="utf-8", newline="") as handle:
        handle.write(planning.note_text())
    # The door LAST, and through a temp file: until this line the original is still whole on disk, so
    # a crash anywhere above leaves duplication, never a hole.
    tmp = plan_path.with_name(f"{plan_path.name}.tmp{os.getpid()}")
    with tmp.open("w", encoding="utf-8", newline="") as handle:
        handle.write(planning.door)
    tmp.replace(plan_path)


def main(argv: list[str] | None = None) -> int:  # pragma: no cover - CLI side effect
    """Plan, prove, report — and write only under ``--apply``. Non-zero on any refusal or failed proof."""
    parser = argparse.ArgumentParser(
        description="Convert a plan-FILE into a plan-FOLDER: door + `plan/` (D166 · C20-4)."
    )
    parser.add_argument("plan", nargs="?", default=str(DEFAULT_PLAN))
    parser.add_argument("--apply", action="store_true", help="write (default: dry-run)")
    parser.add_argument("--today", default=date.today().isoformat())
    parser.add_argument(
        "--garder",
        action="append",
        default=[],
        help="title (or fragment) of a section to LEAVE in the door; repeatable",
    )
    args = parser.parse_args(argv)

    plan_path = Path(args.plan).expanduser()
    if not plan_path.is_file():
        print(missing_plan_message(plan_path))
        return 1

    # `.open(newline="")`, not `read_text(newline=...)`: the keyword only exists on Path from 3.13,
    # and this repo targets 3.12. Disabling newline translation is not optional here — universal
    # newlines would collapse `\r\n` on read and the "same bytes" guarantee would be a lie.
    with plan_path.open(encoding="utf-8", newline="") as handle:
        text = handle.read()
    commit, dirty = repo_state(plan_path.parent)
    try:
        source = str(plan_path.relative_to(_REPO_ROOT))
    except ValueError:
        source = str(plan_path)

    planning = plan_convert(
        text,
        source=source,
        today=args.today,
        commit=commit,
        dirty=dirty,
        arcs_present=arcs_on_disk(plan_path.parent),
        keep=tuple(args.garder),
        # ONE expression for the note's name, and it is the planner's — a second one here is how two
        # copies of a file name drift until the check guards a file nobody writes.
        note_taken=(plan_path.parent / f"{NOTE_PREFIX}-{args.today}.md").exists(),
    )
    # THE REFUSAL FIRST, THE PROOF SECOND — and the order is not a preference, it decides the CAUSE
    # the user reads. Found by running the real command on an already-converted plan, not by a test:
    # the verifiers ran first, `verify_readability` folded a door whose items all live in its arcs,
    # and answered "no readable item" — burying `deja_converti`, the one refusal that names a gesture.
    # A run that will write nothing has nothing to prove; proving properties of a conversion that
    # will not happen can only produce the wrong reason.
    if planning.blocked:
        print(render(planning, applied=False), end="")
        return 1
    try:
        verify_roundtrip(planning)
        verify_readability(planning)
    except ArchiveMismatch as refus:
        print(f"Conversion REFUSED — {refus}")
        return 1

    written = args.apply and bool(planning.moves)
    if written:
        try:
            apply_planning(planning, plan_path=plan_path)
        except FileExistsError as squatter:
            # A name was free when the plan was computed and taken by the time we wrote. A traceback
            # is not a refusal: it names a Python class where the user needs a gesture.
            print(
                f"Conversion INTERRUPTED — `{Path(squatter.filename).name}` appeared between "
                "the check and the write. Nothing was overwritten, the door was not rewritten."
            )
            return 1
    print(render(planning, applied=written), end="")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
