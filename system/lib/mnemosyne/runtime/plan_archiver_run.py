"""plan-archiver — sort the memory of what is DONE out of a living plan, into a dated archive beside it.

The input/output half of :mod:`mnemosyne.production.plan_archive`, which holds every decision as pure
functions. This module owns exactly four side effects: read the plan, ask git for the repo's state,
print, and — only under ``--apply`` — write.

**Dry-run by default**, like ``make rangement``: it SAYS what it would do and writes nothing (D92 —
propose, never impose). Archiving is a move the operator must be able to see before it happens,
since it changes the file they steer by.

**Nothing is written until the reconstruction is proven.** Both verifiers run in dry-run too, so the
proof is the run itself rather than a claim about a run: if archive + remaining plan do not give the
original file back character for character, the command exits non-zero and no file is touched.

Order of writes under ``--apply``: archives FIRST, plan LAST. If the second half fails, the content
exists in two places and none is lost — the failure mode of a non-destructive tool must be
duplication, never a hole (invariant 2).

Run::

    make plan-archiver                       # dry run, on this repo's plan
    make plan-archiver PLAN="projects/example-project/PLAN.md"
    make plan-archiver APPLY=1               # writes

Brick-free, no model, no network. Code, docstrings and everything printed are English
(D117 / D33)."""

from __future__ import annotations

import argparse
import os
import subprocess
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from ..production.plan_archive import (
    ARCHIVE_DIRNAME,
    ArchiveMismatch,
    ArchivePlanning,
    ArcFile,
    plan_archive,
    verify_readability,
    verify_roundtrip,
)
from ..production.plan_format import (
    ARCS_DIRNAME,
    DOOR_FILENAMES,
    ROLE_ARC,
    ROLE_PLAN,
    ROLE_PORTE,
    owning_plan,
    plan_entries,
)
from ..production.plan_registry import plan_files

#: Repo root from this module (``system/lib/mnemosyne/runtime/plan_archiver_run.py`` → parents[4]).
_REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_PLAN = _REPO_ROOT / "docs" / "PLAN.md"

#: What to DO about each refusal. Attached to the reason rather than left to the reader: a refusal
#: that names a problem without naming a gesture turns a tool into an obstacle, and this one refuses
#: precisely where a human must decide something the machine may not decide for him.
_GESTE: dict[str, str] = {
    "titre_ambigu": (
        "The gesture: leave in the title only the arc's REAL state. As long as it declares two, "
        "the archiver does not guess which one wins."
    ),
    "borne_incertaine": (
        "The gesture: close this section's code block. The cut would fall inside it, so the "
        "bytes moved would not be the arc's."
    ),
    "arc_ment": (
        "The gesture: fix the status of the items, or of the title. Archiving would bury lines "
        "that declare themselves to-do — the archiver does not decide in your place."
    ),
    "ligne_illisible": (
        "The gesture: make the line readable (`make plans` names it), then run again. An arc one "
        "of whose lines could not be read is never archived."
    ),
    "archive_existe": (
        "The gesture: nothing. An arc of that name is already archived at that date — we never "
        "overwrite (inv. 2). Rename the arc if it really is a different one."
    ),
    "collision_de_nom": (
        "The gesture: tell the two titles apart. Two arcs of this plan produce the same file "
        "name, and the second would overwrite the first."
    ),
    "index_incertain": (
        "The gesture: give this arc ONE index entry in the door, and one only — the shape "
        "`- `plan/<arc>.md` — <title>`. The archiver replaces THAT line with the pointer; it does "
        "not guess which one, and it does not let the door name a file that has left."
    ),
}


@dataclass(frozen=True)
class PlanSite:
    """WHERE a file sits inside a plan (D166), and the three things that follow from it.

    A plan stopped being a file: it is a door (``PLAN.md`` / ``PLAN_COURANT.md``) plus a ``plan/``
    directory of arcs beside it. So one command now runs against three kinds of file that do not
    answer "readable" the same way, and the difference is not a preference — it is measured. Before
    this, archiving out of an arc left a text with no cap and the command refused a perfectly healthy
    arc; archiving out of a door whose items live in its arcs was refused for having no item.
    """

    #: What the reader must require of what stays behind — see ``plan_format.unreadable_reasons``.
    role: str
    #: Where the archives land: beside the PLAN, never inside ``plan/``. An archive written under
    #: ``plan/`` is a ``.md`` under ``plan/``, which the folder reader picks up as an ARC on the next
    #: pass — every line the archiver took OUT would come back in as items, plus an
    #: ``arc_hors_index`` refusal, which the pre-commit barrier turns into a blocked commit.
    archive_root: Path
    #: The pointer's link, relative to the file that KEEPS the pointer (``archive``, ``../archive``).
    link_dir: str


def _above_arcs(target: Path) -> str | None:
    """The directory a ``plan/`` hangs from, for a file no door claims — ``None`` when there is none.

    The narrow fallback for an arc whose door is missing. That arc is still an arc: the missing door
    is a DIFFERENT defect, and one already named by ``make plans`` and by the pre-commit hook.
    Judging it as a whole plan would refuse it for lacking a cap it must not carry — the exact false
    refusal this whole change removes.
    """
    return next((f.parent.as_posix() for f in target.parents if f.name == ARCS_DIRNAME), None)


def plan_site(plan_path: Path) -> PlanSite:
    """Read the role and the archive location OFF the path — nothing for the operator to type or remember.

    ``owning_plan`` answers "which plan owns this file", and it is ASKED rather than re-implemented:
    the registry, the barrier and this command disagreeing about what belongs to what is the one
    failure a format cannot afford — a file judged by neither is a file that ships unread. It also
    brings the tie-break for free (longest door wins), so a nested plan and an arc four directories
    deep both land where they should.

    Resolved to absolute first, and that is not cosmetic: ``owning_plan`` compares a file's directory
    against a door's as strings, and for ``PLAN.md`` handed in relative form those are ``""`` and
    ``"."`` — the same directory for the filesystem, two different strings here, and the door would
    read as an arc of itself.

    Known limit, named rather than guessed at: for a plan NESTED inside another's ``plan/``, "beside
    the plan" and "outside ``plan/``" cannot both hold, and this keeps "beside". No such plan exists
    in this repo today (measured: zero).
    """
    target = plan_path.resolve()
    here = target.parent
    doors = tuple(
        (folder / name).as_posix()
        for folder in target.parents
        for name in DOOR_FILENAMES
        if (folder / name).is_file()
    )
    owner = owning_plan(target.as_posix(), doors + (target.as_posix(),))
    root = owner if owner is not None else _above_arcs(target)

    if root is not None and root != here.as_posix():
        role, base = ROLE_ARC, Path(root)
    elif target.name in DOOR_FILENAMES and (here / ARCS_DIRNAME).is_dir():
        role, base = ROLE_PORTE, here
    else:
        # A plan that is ONE file is not a degraded case, it is the floor — judged exactly as before.
        role, base = ROLE_PLAN, here
    archive_root = base / ARCHIVE_DIRNAME
    return PlanSite(role, archive_root, Path(os.path.relpath(archive_root, here)).as_posix())


def _bytes_of(path: Path) -> str:
    """A file's EXACT bytes — ``newline=""``, because they may travel into an archive untouched.

    ``.open(newline="")`` rather than ``read_text``: the keyword only reaches ``Path`` in 3.13 and
    this repo targets 3.12. Universal newlines would collapse ``\\r\\n`` on read and the byte-for-byte
    guarantee would become a claim about Python's translation layer.
    """
    with path.open(encoding="utf-8", newline="") as handle:
        return handle.read()


def read_arcs(door_path: Path) -> tuple[tuple[ArcFile, ...], tuple[str, ...]]:
    """The arcs of a folder-shaped plan with their bytes, and every name its index must account for.

    Discovery is ``plan_files`` then ``plan_entries`` — the SAME pair ``plan_registry.read_plan_tree``
    and the pre-commit barrier walk, asked rather than re-implemented. A second walk is a second
    opinion about what belongs to this plan, and the day the two disagreed the archiver would move a
    file the barrier still judges (or judge one it no longer sees).

    Nested doors come back in the second tuple and NEVER in the first: a directory under ``plan/``
    carrying its own door is a plan of its own (its own cap, its own identity scope), so it must stay
    named in the index and must never be archived as though it were an arc of its parent.

    Raises :class:`ArchiveMismatch` when an arc cannot be read: a plan whose files cannot all be read
    is a plan whose reconstruction cannot be proven, and skipping the unreadable one would archive
    around a hole in silence.
    """
    folder = door_path.parent
    tree = tuple(path.relative_to(folder).as_posix() for path in plan_files(folder)[1:])
    members, nested = plan_entries("", tree)
    arcs: list[ArcFile] = []
    for name in members:
        try:
            arcs.append(ArcFile(f"{ARCS_DIRNAME}/{name}", _bytes_of(folder / ARCS_DIRNAME / name)))
        except (OSError, UnicodeDecodeError) as unreadable:
            raise ArchiveMismatch(
                f"the arc `{ARCS_DIRNAME}/{name}` could not be read ({unreadable}) — the "
                "reconstruction of a plan one of whose files is unreadable cannot be proven. "
                "Nothing was read any further, nothing was written."
            ) from unreadable
    return tuple(arcs), members + nested


def missing_plan_message(plan_path: Path) -> str:
    """What to say when the path handed in is not a file — and the gesture that fixes it.

    A plan IS a folder now, so a folder is the most natural thing to hand this command; answering
    "no plan" while the door sits right inside it is a refusal that lies about the world and names
    nothing to do. The archiver still works on ONE file at a time and does not pick for him: the door
    and each arc are different bytes with different memories, and choosing would be the tool
    arbitrating something only the operator can (D92).
    """
    if not plan_path.is_dir():
        return f"No plan at `{plan_path}` — nothing to archive."
    door = next((name for name in DOOR_FILENAMES if (plan_path / name).is_file()), None)
    if door is None:
        return (
            f"`{plan_path}` is a folder with no door (`{'` / `'.join(DOOR_FILENAMES)}`) — "
            "it carries no plan. The gesture: name the file to archive."
        )
    arcs = (
        sorted(child.name for child in (plan_path / ARCS_DIRNAME).glob("*.md"))
        if (plan_path / ARCS_DIRNAME).is_dir()
        else []
    )
    arc_hint = f" · an arc: {', '.join(f'{ARCS_DIRNAME}/{name}' for name in arcs)}" if arcs else ""
    return (
        f"`{plan_path}` is a FOLDER: that is the whole plan, and archiving acts on ONE file. "
        f'The gesture: `make plan-archiver PLAN="{plan_path}/{door}"` (the door){arc_hint}.'
    )


def repo_state(where: Path) -> tuple[str, bool]:
    """``(short sha, dirty tree?)`` for the repo holding ``where`` — read-only, always tolerant.

    Both halves are recorded in the archive header. The SHA alone would be a half-truth: a plan
    archived from a dirty tree does not correspond to that commit, and an archive is a permanent
    record — the one place where "roughly" is not acceptable.

    Never raises. A plan outside any git repo is a legitimate case (a project folder is its own repo,
    or none at all), and refusing to archive it because git is absent would be a rule nobody asked
    for.
    """
    try:
        head = subprocess.run(
            ["git", "-C", str(where), "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
        )
        if head.returncode != 0:
            return "(outside a git repo)", False
        status = subprocess.run(
            ["git", "-C", str(where), "status", "--porcelain"],
            capture_output=True,
            text=True,
            check=False,
        )
        return head.stdout.strip(), bool(status.stdout.strip())
    except OSError:  # pragma: no cover - git absent from the machine
        return "(git unavailable)", False


def _percent(part: int, whole: int) -> str:
    """``part`` as a percentage of ``whole``, French decimal comma, never dividing by zero.

    The comma is BEHAVIOUR, not prose: it is the exact string a caller renders and a test can pin,
    so translating the report around it does not move it. Named here rather than silently changed."""
    return "0,0" if not whole else f"{100 * part / whole:.1f}".replace(".", ",")


def render(planning: ArchivePlanning, *, archive_dir: str, applied: bool) -> str:
    """The report the operator reads — what would move, what is refused and WHY, and what was left out.

    What is DONE folds, what REMAINS shows: refusals carry their offending identities and their
    gesture in full, while the sections that never claimed to be closed are a single counted line.
    Counted, not dropped — a report that names three arcs out of sixteen sections without saying what
    became of the thirteen others is the same silence this whole arc exists to close.
    """
    # The unit is named because it CHANGED with the shape of the plan (D166): a door has no `## ` at
    # all and archives whole arcs. A report that kept saying "12 sections" about a 28-line door
    # carrying zero would be the same confident zero this command was found dead on.
    inventory = f"{planning.sections} `##` sections"
    if planning.arcs:
        inventory += f", {len(planning.arcs)} arc(s) in `{ARCS_DIRNAME}/`"
    lines = [
        "# Mnémosyne · plan archiving",
        "",
        f"`{planning.source}` — {planning.total_lines} lines, {inventory}. "
        f"Repo at `{planning.commit}`" + (" *(dirty tree)*" if planning.dirty else "") + ".",
        "",
    ]

    if planning.moves:
        verb = "ARCHIVED" if applied else "What would leave"
        # "of the file", not "of the plan": since D166 the file handed in is often ONE arc of a plan
        # that spans a folder, and the percentage's denominator is the file named two lines
        # above — never the plan. Found by running the command on a real folder-shaped plan,
        # where it announced "62,5 % of the plan" about five lines of one arc among several.
        #
        # And the numerator is what left THIS file, which is not what moved: a door archiving an arc
        # loses ONE line and the arc's 108 were never in it. Printed as one ratio, that read
        # "385,7 % of the file" — found the first time the repaired command ran for real.
        heading = f"## {verb} — {len(planning.moves)} arc(s), {planning.moved_lines} lines"
        if planning.moved_from_file:
            heading += f" ({_percent(planning.moved_from_file, planning.total_lines)} % of the file)"
        lines += [heading, ""]
        for move in planning.moves:
            idents = ", ".join(ident for ident in move.idents if ident) or "no item"
            lines += [
                f"- **{move.title}**",
                f"      {move.where} · {len(move.idents)} item(s): {idents}",
                f"      → `{archive_dir}/{move.filename}`",
                f"      the plan keeps: `{move.pointer}`",
            ]
        lines.append("")
    else:
        lines += ["## Nothing to archive", "", "No arc declares itself closed and ready to leave.", ""]

    if planning.refusals:
        lines += [f"## REFUSED — {len(planning.refusals)} arc(s)", ""]
        for refusal in planning.refusals:
            lines += [
                f"- **{refusal.title}** — {refusal.where}",
                f"      {refusal.label}",
                f"      {refusal.detail}",
                f"      {_GESTE[refusal.reason]}",
            ]
        lines.append("")

    lines += [
        f"*{planning.not_candidates} section(s)/arc(s) declare themselves closed by neither `\U00002705` "
        "nor `\U000026D4` — not candidates, untouched.*",
        "",
    ]

    if applied:
        reste = len(planning.remaining.splitlines())
        partis = sum(1 for move in planning.moves if move.origin)
        lines += [
            f"**APPLIED** — {len(planning.moves)} file(s) written into `{archive_dir}/`, "
            f"plan rewritten ({planning.total_lines} → {reste} lines)"
            + (
                f", {partis} arc file(s) moved out of `{ARCS_DIRNAME}/`."
                if partis
                else "."
            ),
            "",
            "Reconstruction verified **before** any write: archive + remaining plan give the "
            "original file back, character for character"
            + (" — and for an arc, its whole bytes, as they are." if partis else "."),
            "",
        ]
    else:
        lines += [
            "**DRY RUN — nothing was written.** The byte-for-byte reconstruction has already been "
            "verified on what precedes.",
            "",
            "To apply it: `make plan-archiver APPLY=1`",
            "",
        ]
    return "\n".join(lines).rstrip() + "\n"


def apply_planning(planning: ArchivePlanning, *, plan_path: Path, archive_root: Path) -> None:
    """Write the archives, then the plan, then let the moved arcs go. Only after BOTH verifiers pass.

    ``"x"`` mode, not ``"w"``: the existence check in the pure planner happens before the report is
    even printed, and a file can appear in between. The last word on "never overwrite" belongs to the
    filesystem, not to a set computed earlier (invariant 2).

    ``newline=""`` on every handle, in both directions: Python's default translates ``\\n`` to
    ``os.linesep`` on write and collapses ``\\r\\n`` on read. Either one silently breaks the
    byte-for-byte guarantee this whole command is built on, on the first plan written on another
    machine.

    **The arc files go LAST, and that ordering is the whole of invariant 2 here.** An arc's bytes are
    already inside its archive, character for character, and that equality was PROVEN before the first
    write; releasing the file is the second half of a move, not a deletion of anything. Ordered last
    so every failure mode is duplication — the content in two places — and never a hole: crash after
    the archive and the arc is still there (the next run refuses on ``archive_existe``); crash after
    the door and the arc is an ``arc_hors_index`` the barrier shouts about. Both are loud, neither
    loses a byte.
    """
    archive_root.mkdir(parents=True, exist_ok=True)
    for move in planning.moves:
        with (archive_root / move.filename).open("x", encoding="utf-8", newline="") as handle:
            handle.write(planning.archive_text(move))
    tmp = plan_path.with_name(f"{plan_path.name}.tmp{os.getpid()}")
    with tmp.open("w", encoding="utf-8", newline="") as handle:
        handle.write(planning.remaining)
    tmp.replace(plan_path)
    for move in planning.moves:
        if move.origin:
            (plan_path.parent / move.origin).unlink()


def main(argv: list[str] | None = None) -> int:  # pragma: no cover - CLI side effect
    """Plan, prove, report — and write only under ``--apply``. Non-zero only when the proof fails."""
    parser = argparse.ArgumentParser(
        description="Archive the memory of what is done, out of a living plan (C8)."
    )
    parser.add_argument("plan", nargs="?", default=str(DEFAULT_PLAN))
    parser.add_argument("--apply", action="store_true", help="write (default: dry run)")
    parser.add_argument("--today", default=date.today().isoformat())
    args = parser.parse_args(argv)

    plan_path = Path(args.plan).expanduser()
    if not plan_path.is_file():
        print(missing_plan_message(plan_path))
        return 1

    text = _bytes_of(plan_path)
    site = plan_site(plan_path)
    archive_root = site.archive_root
    taken = {entry.name for entry in archive_root.glob("*.md")} if archive_root.is_dir() else set()
    commit, dirty = repo_state(plan_path.parent)

    # ONLY a door archives arcs, and the role is read off the path rather than typed. An ARC handed
    # in directly still archives its own `## ` sections, and so does a plan that is one FILE: the
    # unit widened for the shape that needed it, and no shape lost the unit it had.
    arcs: tuple[ArcFile, ...] = ()
    indexed: tuple[str, ...] = ()
    if site.role == ROLE_PORTE:
        try:
            arcs, indexed = read_arcs(plan_path)
        except ArchiveMismatch as refus:
            print(f"Archiving REFUSED — {refus}")
            return 1

    try:
        source = str(plan_path.relative_to(_REPO_ROOT))
    except ValueError:
        source = str(plan_path)

    planning = plan_archive(
        text,
        source=source,
        today=args.today,
        commit=commit,
        dirty=dirty,
        taken=frozenset(taken),
        link_dir=site.link_dir,
        arcs=arcs,
        indexed=indexed,
    )
    try:
        verify_roundtrip(planning)
        verify_readability(planning, role=site.role)
    except ArchiveMismatch as refus:
        print(f"Archiving REFUSED — {refus}")
        return 1

    written = args.apply and bool(planning.moves)
    if written:
        try:
            apply_planning(planning, plan_path=plan_path, archive_root=archive_root)
        except FileExistsError as squatter:
            # The name was free when the plan was computed and taken by the time we wrote. A
            # traceback is not a refusal: it names a Python class where the operator needs a gesture.
            print(
                f"Archiving INTERRUPTED — `{Path(squatter.filename).name}` appeared between the "
                "examination and the write. Nothing was overwritten, the plan was not rewritten."
            )
            return 1
    # The report shows the SAME place the files actually went (repo-relative when it can be): an
    # absolute `/Users/…` here would say a different thing than the file it describes — and
    # `<plan>/../archive` would name the wrong directory outright for an arc, whose memory lands
    # one level up, beside the plan.
    try:
        where = str(archive_root.relative_to(_REPO_ROOT))
    except ValueError:
        where = str(archive_root)
    print(render(planning, archive_dir=where, applied=written), end="")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
