"""plan-nouveau — scaffold a plan that IS A FOLDER, compliant from birth (D166 · C20-13).

The repo could REPAIR a plan (``make plan-convertir``) and JUDGE one (the pre-commit barrier,
``make plans``). It could not make one be BORN: ``plan_skeleton`` hands a single FILE, and every
folder-shaped plan of this repo had to be converted into existence. The operator's own words: *"if
the point is that it be a conforming plan from the very start… then I have to tell the agent: here
is the structure you must respect"*.

This module owns exactly four side effects: read what already exists, ask git for the repo's state,
print, and — only under ``--apply`` — write. Everything about the FORM is computed by the pure
:mod:`~mnemosyne.production.plan_scaffold`, and the verdict on that form is given by the reader
itself (``verify_readability``) BEFORE a single byte is written. That ordering is the whole promise
of this command: a plan born here passes the pre-commit barrier on its FIRST commit, with no
conversion — or nothing is written at all.

DRY BY DEFAULT, like its two siblings. ``APPLY=1`` writes. Every file is opened in ``"x"`` mode
(create-or-fail), so a race with another process refuses instead of overwriting, and the PARENT
door — the only pre-existing file this command ever touches — is rewritten through a temporary file
and an atomic replace, last.

Run::

    make plan-nouveau CHEMIN="projects/saas/example-project"
    make plan-nouveau CHEMIN="projects/saas/example-project" NOM="Example Project" CAP="close arc 6" APPLY=1
    make plan-nouveau CHEMIN="projects/example-project/plan/theories/T001" ARC="Signals" APPLY=1   # a SUB-plan
    make plan-nouveau CHEMIN="projects/saas/example-project" FORMAT="produit, fini_quand" APPLY=1  # D176

Code, docstrings and everything printed are English (D117); only the plan-format tokens the reader
parses (here the ``FORMAT=`` field names) keep their canonical spelling.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from ..production.plan_format import read_plan
from ..production.plan_registry import arc_tree
from ..production.plan_scaffold import (
    DEFAULT_ARC_TITLE,
    ParentDoorUnreadable,
    ScaffoldMismatch,
    ScaffoldPlanning,
    owning_parent,
    plan_scaffold,
    verify_readability,
)
from .plan_archiver_run import repo_state

#: Repo root from this module (``system/lib/mnemosyne/runtime/plan_new_run.py`` → parents[4]).
_REPO_ROOT = Path(__file__).resolve().parents[4]

#: Directories never walked when listing what already exists. ``.git`` alone holds tens of thousands
#: of files and cannot contain a plan; ``.venv`` and the caches are the same answer. Without this the
#: existence scan is the slowest thing in the command, and a door slower than the wall is never used.
_SKIP_DIRS: frozenset[str] = frozenset(
    {".git", ".venv", "node_modules", "__pycache__", ".pytest_cache", ".ruff_cache"}
)

#: What to DO about each refusal. Keyed on the token :data:`~mnemosyne.production.plan_scaffold.
#: REFUSAL_LABEL` declares, so a refusal added there without a gesture here raises a ``KeyError`` at
#: the surface — loud — instead of printing a problem nobody can act on. Same coupling
#: ``plan_converter_run`` uses, and for the same measured reason.
_GESTE: dict[str, str] = {
    "chemin_manquant": (
        'The gesture: `make plan-nouveau CHEMIN="projects/<bubble>/<project>"`. A plan is born '
        "where the work lives — guessing it means putting it where nobody will look for it."
    ),
    "racine_du_depot": (
        'The gesture: name the folder of the work, `CHEMIN="projects/<bubble>/<project>"`. At the '
        "repo root, the door would be `PLAN.md` at the top of Mnemosyne: that is nobody's plan, "
        "and nothing is added at the root without a written reason (`CLAUDE.md`)."
    ),
    "hors_depot": (
        "The gesture: give a path UNDER the repo root. Writing outside would leave the perimeter "
        "this repo guarantees, and nothing outside is judged by the barrier."
    ),
    "profondeur_projet": (
        'The gesture: aim at exactly `projects/<bubble>/<project>` — two levels, neither one nor '
        "three. `scan_projects` walks ONLY that depth: a bubble (`saas`, `trading`…) then a "
        "project. Born elsewhere, this plan WOULD BE WRITTEN without error but would NEVER be read "
        "as a project by `make plans` nor `ui-json` — a silently invisible birth."
    ),
    "chemin_occupe": (
        "The gesture: choose another path, or move the file carrying that name. A plan is a "
        "FOLDER: it cannot be born where a file already occupies the place."
    ),
    "dossier_des_arcs": (
        "The gesture: aim at the PROJECT's folder (without `/plan`), or — if you really do want a "
        'SUB-plan — a folder INSIDE it: `CHEMIN="<project>/plan/<the-sub-plan>"`. Written where '
        "you asked for it, this plan would become two ARCS of the plan above, which its door does "
        "not index: the parent plan would stop being readable, and the command would have "
        "announced a success."
    ),
    "plan_existe": (
        "The gesture: nothing here. A plan already lives at this place — nothing is ever "
        "overwritten (inv. 2). To grow it: add an arc in its `plan/`, or give birth to a SUB-plan "
        "under this one."
    ),
    "arc_existe": (
        "The gesture: rename the requested arc, or aim at another folder. This file already exists "
        "and overwriting it would bury what somebody wrote in it (inv. 2)."
    ),
    "collision_de_nom": (
        "The gesture: tell the two arc titles apart. They produce the same file name, so the "
        "second would erase the first."
    ),
    "arc_sans_titre": (
        "The gesture: give this arc a title. Without one, the tool would have to INVENT a file "
        "name, and two mute arcs would carry the same one."
    ),
    "nom_manquant": (
        'The gesture: `NOM="<the project name>"`. The first line of a door is `# PLAN — <name>` ; '
        "with no name, this is not a plan the reader recognises."
    ),
    "texte_multiligne": (
        "The gesture: put this text back on ONE line (it is the first line that is quoted above). "
        "A door is read line by line: what follows the line break would land outside its field, "
        "and a code block opened there would switch off the verification of everything after it."
    ),
    "texte_declare_un_chemin": (
        "The gesture: remove that path from the text (the offending word is quoted above). A "
        "`plan/….md` in a title, a name, a cap or a format is read by the reader as an INDEX ENTRY "
        "— it would demand a file nobody will ever write (`index_sans_fichier`). An arc carries a "
        "title, not a path: the tool computes the file name from the title."
    ),
    "chemin_non_indexable": (
        "The gesture: rename the FOLDER without that character (or those characters) — `l'offre` → "
        "`l-offre`, `rapports (200)` → `rapports-200`. This is not a style preference: the parent "
        "door must NAME this sub-plan with a `plan/<folder>/PLAN.md` line, and the index reader — "
        "the very one that judges the commit — stops dead on those characters, because they are "
        "what TERMINATES a path quoted, linked or put in a cell in real markdown. Written as it "
        "stands, this sub-plan would be born an ORPHAN (`arc_hors_index`). A TOP-level plan accepts "
        "any name at all: its path enters no document, so this refusal does not target it."
    ),
    "porte_parente_illisible": (
        "The gesture: repair the parent plan's door first (`make plans` names it). A sub-plan its "
        "parent does not index is born an ORPHAN, and the pre-commit barrier refuses the commit."
    ),
    "squelette_illisible": (
        "The gesture: report the breakage (`make signaler`). This refusal says the scaffold and "
        "the reader have diverged — it is a defect of Mnemosyne, not a mistake in your request."
    ),
}


def existing_paths(root: Path) -> tuple[str, ...]:
    """Every file already present under ``root``, ``/``-joined and relative to it — sorted.

    The SAME namespace ``git ls-files`` and ``plan_registry``'s ``rglob`` produce, on purpose: the
    question "does this already exist?" must be asked of the strings the barrier will judge. Two path
    namespaces would be two rules, and the day they disagreed a file would be judged by neither.

    It reads the DISK rather than the git index, and that is the honest side for THIS question: a
    door somebody wrote and has not staged yet is a door that would be overwritten.
    """
    found: list[str] = []
    for parent, dirs, files in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d not in _SKIP_DIRS)
        base = Path(parent)
        found.extend((base / name).relative_to(root).as_posix() for name in files)
    return tuple(sorted(found))


def _parent_members(
    planning: ScaffoldPlanning, root: Path
) -> tuple[tuple[tuple[str, str], ...], tuple[str, ...]]:
    """The PARENT plan's tree in its RESULTING state — ``(readable members, unreadable members)``.

    The nested door is added by hand rather than read back, because it does not exist yet: verifying
    the parent against the tree it had BEFORE would be a check valid only in the state before the
    edit it guards — the harness defect this repo has already measured and named.

    **THE WALK IS ``arc_tree``'S, NOT THIS MODULE'S, and that is the repair.** This used to
    ``rglob`` the parent's ``plan/`` itself and hand every ``.md`` it found to the verifier as an arc
    of the parent — including the files of sub-plans already living there, which belong to a plan of
    their own. Measured: with one sub-plan present, a SECOND sibling was refused for
    ``id_duplique — A1``, a collision that exists in no plan; with the check disabled the same birth
    passed AND the commit passed, so the two verdicts really were opposite. The barrier's own walk
    now answers, and :func:`~.plan_format.fold_plan` decides which of those files are arcs.
    """
    parent = planning.parent
    if parent is None:
        return (), ()
    folder = root / parent.folder if parent.folder else root
    members: list[tuple[str, str]] = []
    lost: list[str] = []
    for relative in arc_tree(folder):
        try:
            members.append((relative, (folder / relative).read_text(encoding="utf-8")))
        except (OSError, UnicodeDecodeError):
            # An arc of the PARENT that exists and cannot be read is the parent's problem, named as
            # the parent's problem. Dropping it would hand the verifier a tree the disk does not
            # have, and the missing file would come back as a fault of this birth.
            lost.append(relative)
    return (*members, (parent.member, planning.door_text)), tuple(lost)


def render(planning: ScaffoldPlanning, *, applied: bool, commit: str, dirty: bool) -> str:
    """The report the operator reads: what is REFUSED and its gesture, then the exact bytes that
    would land.

    Refusals come FIRST and the preview is suppressed under them — printing a byte-for-byte preview
    of a scaffold that will not happen buries the refusal under the thing it refused, which is how a
    ``deja_converti`` got lost once already.
    """
    where = planning.folder or "."
    lines = [
        "# Mnemosyne · birth of a plan (D166)",
        "",
        f"`{where}` — plan **{planning.project or '(unnamed)'}**, "
        f"{len(planning.arcs)} arc(s). Repo at `{commit}`"
        + (" *(tree modified)*" if dirty else "")
        + ".",
        "",
    ]

    if planning.refusals:
        lines += [
            f"## REFUSED — nothing will be written ({len(planning.refusals)} reason(s))",
            "",
        ]
        for refusal in planning.refusals:
            lines += [
                f"- **{refusal.reason}** — `{refusal.detail}`",
                f"      {refusal.label}",
                f"      {_GESTE[refusal.reason]}",
            ]
        lines += [
            "",
            "*A birth happens whole or not at all: a half-written plan would be a plan the barrier "
            "refuses, and it would have to be repaired before anything else could be committed.*",
            "",
        ]
        return "\n".join(lines) + "\n"

    verbe = "WRITTEN" if applied else "What would be written"
    lines += [f"## {verbe}", ""]
    lines += [f"- `{planning.door_path}` — the DOOR: the cap, the index"]
    if planning.livrables_name:
        # The preview MUST show it: nobody approves a write they cannot see.
        chemin = (
            f"{planning.folder}/{planning.livrables_name}"
            if planning.folder
            else planning.livrables_name
        )
        lines.append(
            f"- `{chemin}` — the COMMAND (G1): the requester's words, VERBATIM. "
            "It precedes the plan and is never derived from it."
        )
    for arc in planning.arcs:
        path = f"{planning.folder}/{arc.member}" if planning.folder else arc.member
        lines.append(f"- `{path}` — an ARC: its items (`{arc.ident}`)")
    if planning.parent is not None:
        lines += [
            "",
            "### Sub-plan — the parent door receives its index entry",
            "",
            f"`{planning.parent.folder}/{planning.parent.door_name}` gains one line:",
            "",
            "```markdown",
            planning.parent.entry,
            "```",
            "",
            "*Without it the sub-plan would be born an ORPHAN (`arc_hors_index`) and the pre-commit "
            "barrier would refuse the commit. A birth that produces an orphan is a failed birth.*",
        ]
    lines += [
        "",
        "### The door, byte for byte",
        "",
        "```markdown",
        planning.door_text.rstrip("\n"),
        "```",
        "",
    ]
    for arc in planning.arcs:
        lines += [
            f"### `{arc.member}`, byte for byte",
            "",
            "```markdown",
            arc.text.rstrip("\n"),
            "```",
            "",
        ]

    lines += [
        "### What the reader says about it",
        "",
        "The plan reader (`plan_format`) judges these bytes **readable**: cap present, at least "
        "one item, index complete in both directions. It is IT that said so, not this command — "
        "and it is the same code as the pre-commit barrier.",
        "",
    ]
    # R3, ISOLATED AUDIT (D75): "readable" does NOT mean "passes the installed D176 barrier".
    # A declared `**Format**` (supplied or inherited from the parent) makes the first item — the
    # `(the first item)` skeleton — REFUSABLE as it stands, since it fills in none of the promised
    # fields. Silent about that, this page would let someone believe a formatted plan is ready to
    # commit.
    if read_plan(planning.door_text).format_declare:
        lines += [
            "**But `**Format**` is declared (supplied or inherited from the parent) — the "
            "skeleton FILLS IN none of the promised fields.** The D176 barrier, if it is installed "
            "(`make plan-gate-emit`), WILL REFUSE this first item as it stands. That is not a "
            "defect of this command: it is the D176 promise beginning to bite — fill in the "
            "declared fields, or `AUCUN` for those that do not apply.",
            "",
        ]
    if not applied:
        # FOUND BY AN AUTONOMY PROBE (D75, 2026-08-17), NOT BY AN AUDIT: this line used to
        # carry only CHEMIN=/NOM=/ARC= -- copy-pasting the proposed gesture silently lost any
        # `CAP=`/`FORMAT=` received on the first shot: the project believes it adopted, the door
        # that is born declares nothing, and everything stays green. It now replays ALL the
        # parameters this MAKE TARGET can express.
        # `planning.cap` is ALWAYS non-empty (the `DEFAULT_CAP` default if nothing was received) and
        # that default is stable from one call to the next -- replaying it explicitly never changes
        # the result, so there is never a risk in always including it. `planning.format_arg` is the
        # RAW value RECEIVED, before inheritance (`ScaffoldPlanning.format_arg`): empty, it is
        # omitted and the inheritance will reproduce identically on the second call (same parent,
        # same disk); non-empty (an explicit choice), it is pinned down so it can never be silently
        # overwritten by inheritance at the moment of the REAL APPLY=1.
        # `[:1]`, NOT the whole of `planning.arcs`: this MAKE TARGET itself only ever carries ONE
        # `ARC=` (the Makefile's own help text: "for several, call the module with several --arc").
        # `make ARC="x" ARC="y"` keeps ONLY the last assignment -- emitting several would produce a
        # command that LOOKS complete and silently loses `x` the moment it is replayed, exactly the
        # class of defect this fix closes. Nothing to fix here: the first arc is already everything
        # this target can ever receive.
        arcs_flag = "".join(f' ARC="{arc.title}"' for arc in planning.arcs[:1])
        format_flag = f' FORMAT="{planning.format_arg}"' if planning.format_arg else ""
        lines += [
            "---",
            "",
            "**Nothing was written.** The gesture:",
            "",
            "```bash",
            f'make plan-nouveau CHEMIN="{where}" NOM="{planning.project}" CAP="{planning.cap}"'
            f"{arcs_flag}{format_flag} APPLY=1",
            "```",
            "",
        ]
    return "\n".join(lines) + "\n"


def apply_planning(planning: ScaffoldPlanning, root: Path) -> None:
    """Write the scaffold. Arcs first, then the door, then the parent's index entry — last.

    ``"x"`` everywhere a file is NEW: create-or-fail, so a file that appeared between the existence
    scan and now refuses instead of being overwritten (inv. 2, defended by the syscall rather than by
    a check that has already run). ``newline=""`` so no line ending is translated on the way out.

    The order is the one that never leaves a lying state behind: the arcs exist before the door names
    them (so ``index_sans_fichier`` is never true on disk), and the parent names the sub-plan only
    once the sub-plan is complete (so ``arc_hors_index`` is never true either). An interrupted run
    leaves files nobody indexes yet, which the barrier names — never an index pointing at nothing.
    """
    folder = root / planning.folder if planning.folder else root
    for arc in planning.arcs:
        path = folder / arc.member
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "x", encoding="utf-8", newline="") as handle:
            handle.write(arc.text)
    door = folder / planning.door_name
    door.parent.mkdir(parents=True, exist_ok=True)
    with open(door, "x", encoding="utf-8", newline="") as handle:
        handle.write(planning.door_text)
    # G1: the COMMAND is born WITH the plan, never after. Same "x" mode as everything else -- a
    # LIVRABLES that already exists belongs to someone, and overwriting it would destroy the
    # requester's own words.
    if planning.livrables_name:
        with open(folder / planning.livrables_name, "x", encoding="utf-8", newline="") as handle:
            handle.write(planning.livrables_text)
    if planning.parent is None:
        return
    parent_folder = root / planning.parent.folder if planning.parent.folder else root
    parent_door = parent_folder / planning.parent.door_name
    tmp = parent_door.with_suffix(parent_door.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8", newline="") as handle:
        handle.write(planning.parent.text)
    tmp.replace(parent_door)


def _parent_door_text(folder: str, root: Path, existing: tuple[str, ...]) -> str:
    """The bytes of the door that will OWN this new plan — ``""`` when nothing owns it.

    Read here rather than inside the pure planner, which opens nothing. An unreadable parent comes
    back empty and the planner turns that into ``porte_parente_illisible``: a sub-plan whose parent
    cannot be updated would be born orphan, and the barrier refuses an orphan.

    WHICH door is ``owning_parent``'s answer, not a second copy of it. This function used to
    re-derive the ownership walk, so "whose door do I read" and "whose door do I edit" were two
    expressions of one rule, free to disagree without a word.
    """
    owning = owning_parent(folder, existing)
    if owning is None:
        return ""
    parent_folder, door_name, _member = owning
    door = f"{parent_folder}/{door_name}" if parent_folder else door_name
    try:
        return (root / door).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


def main(argv: list[str] | None = None) -> int:  # pragma: no cover - CLI side effect
    """Plan the birth, print it, and write it only under ``--apply``. Never raises at the surface."""
    parser = argparse.ArgumentParser(description="Scaffold a conforming FOLDER-shaped plan (D166).")
    parser.add_argument("chemin", nargs="?", default="", help="the folder where the plan must be born")
    parser.add_argument("--nom", default="", help="the project name (default: the folder's name)")
    parser.add_argument("--cap", default="", help="what we are trying to obtain right now")
    parser.add_argument("--arc", action="append", default=[], help="an arc (repeatable)")
    parser.add_argument(
        "--format",
        default="",
        dest="format_declare",
        help="D176, optional: the fields to make mandatory (e.g. 'produit, fini_quand') — "
        "passing nothing lets the plan be born with no obligation, the door explains the choice",
    )
    parser.add_argument("--apply", action="store_true", help="write (dry by default)")
    parser.add_argument("--repo-root", default=str(_REPO_ROOT), help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    root = Path(args.repo_root).resolve()
    raw = args.chemin.strip()
    inside = True
    folder = ""
    if raw:
        target = (root / raw).resolve() if not Path(raw).is_absolute() else Path(raw).resolve()
        try:
            folder = target.relative_to(root).as_posix()
        except ValueError:
            inside, folder = False, raw
    existing = existing_paths(root) if root.is_dir() else ()
    planning = plan_scaffold(
        folder=folder,
        project=args.nom,
        cap=args.cap,
        arcs=tuple(a for a in args.arc) or (DEFAULT_ARC_TITLE,),
        existing=existing,
        parent_door_text=_parent_door_text(folder, root, existing) if folder and inside else "",
        folder_is_file=bool(folder) and (root / folder).is_file(),
        inside_repo=inside,
        format_declare=args.format_declare,
    )
    commit, dirty = repo_state(root)

    if planning.blocked:
        print(render(planning, applied=False, commit=commit, dirty=dirty), end="")
        return 1
    members, lost = _parent_members(planning, root)
    try:
        verify_readability(planning, parent_members=members, parent_lost=lost)
    except ParentDoorUnreadable as refus:
        # A parent that was ALREADY broken is not a divergence of this code, and saying so sent the
        # caller to `make signaler` with a report nobody could act on.
        print(f"Birth REFUSED — porte_parente_illisible — {refus}")
        print(f"   {_GESTE['porte_parente_illisible']}")
        return 1
    except ScaffoldMismatch as refus:
        # The token is PRINTED, like the other refusals: it was the only one of them that could not
        # be found by `grep` in an output, so nothing could be pinned on it.
        print(f"Birth REFUSED — squelette_illisible — {refus}")
        print(f"   {_GESTE['squelette_illisible']}")
        return 1

    if args.apply:
        try:
            apply_planning(planning, root)
        except FileExistsError as squatter:
            # A traceback is not a refusal: it names a Python class where the operator needs a
            # gesture.
            print(f"Birth INTERRUPTED — `{squatter.filename}` appeared in the meantime.")
            print(f"   {_GESTE['arc_existe']}")
            return 1
    print(render(planning, applied=args.apply, commit=commit, dirty=dirty), end="")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
