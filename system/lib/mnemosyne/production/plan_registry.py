"""Which projects carry a readable ``PLAN.md``, and which do not — the verifiable half of the format.

A format nobody can check is a suggestion. This walks the projects tree and answers, per project, one
of THREE things: its plan is readable · there is no plan · there is a plan and it cannot be read (with
the reason named). The third state is the one that matters — a ``PLAN.md`` that exists but yields no
item would otherwise pass for "done" while an interface showed an empty project.

**Where a project lives, measured rather than decided.** Under ``projects/``, depth 1 is the bubble
(``saas``, ``trading``, ``mnemosyne``, ``personal``) and depth 2 is the project (``saas/<a project
name>``, ``trading/example_research``, …). That is what the tree actually contains, so that is the rule.
Because a rule about a depth cannot see what sits at the WRONG depth, ``misplaced`` names any bubble
directory carrying markdown at its own root: a control that only sees what IS cannot see what is
missing, and a project one level too high would simply never appear.

Never raises on a hostile tree: a missing ``projects/`` (a fresh clone — the directory is gitignored
by design) yields an empty registry, and an unreadable file becomes a NAMED state, not a traceback.

Code & docstrings English (D117). Decisions: D92 (this reports, it never writes or blocks) ·
invariant 2 (a pure read).
"""

from __future__ import annotations

import os

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from .plan_format import (
    ARCS_DIRNAME,
    DOOR_FILENAMES,
    PLAN_FILENAME,
    ROLE_PLAN,
    PlanProblem,
    PlanReading,
    fold_plan,
    is_readable,
    plan_entries,
    read_plan,
    unreadable_reasons,
)

#: The projects tree, relative to the repo root.
PROJECTS_DIRNAME: Final = "projects"

#: The plan roots that are NOT projects — declared, never special-cased. There is exactly one and it
#: is Mnemosyne's own: the repo is not *in* ``projects/``, it *is* the repo, which is the sole reason
#: ``make plans`` never saw its plan and a whole second barrier had to be written for it (D166).
#: A declaration is what turns that exception into a line one can read; the alternative — a second
#: mechanism — is what this repo already tried, and it graded its own plan more kindly than the
#: projects it grades.
PLAN_ROOTS: Final = ("docs",)

#: The name that root answers to in a report. The operator reads these (D33).
ROOT_NAMES: Final = {"docs": "mnémosyne"}

#: The marker a NESTED plan's own :attr:`ProjectPlan.name` carries after its top-level project —
#: see :func:`read_plan_tree` / its ``nested_plans()`` closure, the ONE place this shape is built.
_NESTED_MARKER: Final = f"/{ARCS_DIRNAME}/"


def top_name(name: str) -> str:
    """The top-level project a (possibly nested) :attr:`ProjectPlan.name` belongs to — itself, if
    it already is one (no ``/plan/`` segment).

    C9 — promoted here from a private copy in ``plans_run.py`` (C7) the day a SECOND consumer
    (``lot_emit_run.py``) needed the same grouping and would otherwise have re-derived it: the
    naming CONVENTION lives with the code that BUILDS it (``nested_plans()``, just below), so its
    inverse belongs in the same module rather than in whichever edge happened to need it first.
    """
    return name.split(_NESTED_MARKER, 1)[0]


def arc_par_item(membres: Sequence[ProjectPlan]) -> dict[str, str] | None:
    """``{item.ident: name of the sub-plan that carries it}`` — the REAL identity of an arc in
 folder-plans (D166 clause 3), or ``None`` on a FLAT plan where there is nothing to distinguish.

 **C9: AN ARC'S IDENTITY IS NEITHER AN IDENTIFIER PREFIX NOR A `source` FILE — IT IS
 THE SUB-PLAN THAT CARRIES IT.** Measured (`production/carte.py::_arc_de`, on that project's real plan):
 an identifier's letter-prefix (`A01-1` → `A`) melts 14 real sub-plans into 3 letters — a
 mandate of 147 items for "arc A" is not the mandate of one chat on ONE arc, it is the mandate
 of one chat on the WHOLE project, the exact inverse of what the project's own orchestration
 doctrine ("one chat per ARC") requires. An item's `source` (its FILE) over-splits the other way:
 149 leaf files for 14 real arcs — a file is not an arc, a SUB-PLAN is (D166 clause 3: "any
 folder carrying a door is a plan, at any level").

 **Promoted here from a construction that used to live INLINE in `carte_run.py`** (the first
 caller to have needed this identity, before `lot_emit_run.py`) — never recopied: the
 two readers now share the same computation, rather than two copies that could have
 diverged. **`carte_run.py` still carries ITS OWN inline construction, not migrated to
 this one** — named rather than hidden: `production/carte.py`/`runtime/carte_run.py` are not
 in this lot (C9), and migrating them without the gesture that owns them would recopy the very
 risk this function exists to close. The two computations are, as of today, VERIFIED IDENTICAL in
 shape (same filter: readable and non-empty; same key: the ident; same value: the plan's name).

 Keeps only READABLE and NON-EMPTY members — an unreadable sub-plan has nothing to offer
 this map, and counting it would empty out the question rather than answer it. ``None`` when
 there is at most ONE member thus retained (the flat case, the large majority): that is the
 signal the caller already uses for its own fallback (identifier prefix on a plan with no
 sub-plans) rather than injecting a single-entry map that would never distinguish anything.
 """
    lisibles = [p for p in membres if p.reading is not None and p.reading.items]
    if len(lisibles) <= 1:
        return None
    return {item.ident: plan.name for plan in lisibles for item in plan.reading.items}

#: State tokens. French because they are printed to the operator (D33); the code around them stays English.
LISIBLE: Final = "lisible"
ABSENT: Final = "absent"
ILLISIBLE: Final = "illisible"

#: The refusal kind for an ARC that exists and whose bytes cannot be read. It lives here rather than
#: in ``plan_format`` because that module is a PURE reader — it is handed text and never opens a
#: file, so it cannot name a class of failure it structurally cannot meet.
ARC_ILLISIBLE: Final = "arc_illisible"

#: A SYMLINK IS TWO DIFFERENT FILES AT ONCE, and these two sentences are why it is refused rather
#: than followed. Git stores the LINK (a blob holding the target path); the disk hands the TARGET's
#: bytes. So ``make plans`` and the pre-commit barrier — which reads the INDEX, on purpose, and must —
#: cannot be made to agree on what such an arc says: measured, a broken link under ``plan/`` gave
#: ILLISIBLE on disk and ``exit 0`` at the barrier, and a VALID one diverges the other way. Naming it
#: on BOTH sides is the only shape where the four surfaces answer the same thing.
#:
#: **Public, and that is the whole point.** The barrier says the SAME sentence, by importing this —
#: never by carrying its own copy. A wording copied into the hook is a second expression of one rule,
#: free to drift the day either side is edited, which is the class every audit of this arc has found.
#: Cost measured before it was written: ZERO symlinks anywhere in this repo outside ``.git``.
#:
#: Two sentences rather than one, because BROKEN and RESOLVING need different gestures: *"the target
#: cannot be found"* for one, *"replace the link with a real file"* for the other. A single
#: wording for two causes is how a refusal stops naming what to do.
LIEN_CASSE: Final = "broken link (the entry exists, the target cannot be found)"
LIEN_SYMBOLIQUE: Final = (
    "symbolic link — the git index carries the LINK, the disk carries its target: two files for one"
    " path, hence two verdicts. Replace it with a real file"
)


@dataclass(frozen=True)
class ProjectPlan:
    """One project and the state of its plan — never a boolean, always one of three states."""

    name: str
    plan_path: Path
    state: str
    reading: PlanReading | None = None
    why: str = ""

    @property
    def bubble(self) -> str:
        """The bubble this project belongs to — the first segment of its name."""
        return self.name.split("/", 1)[0]


@dataclass(frozen=True)
class PlanRegistry:
    """Every project, plus what the depth rule could not see."""

    projects: tuple[ProjectPlan, ...]
    misplaced: tuple[str, ...] = ()
    root_exists: bool = True

    def named(self, state: str) -> tuple[str, ...]:
        """The NAMES of the projects in one state.

        Names, never a count: a frozen number cannot tell you WHICH project slipped, and "3 of 4" has
        already been the shape of every register that rotted in this repo.
        """
        return tuple(project.name for project in self.projects if project.state == state)


def _why_unreadable(
    reading: PlanReading, *, role: str = ROLE_PLAN, leading: tuple[str, ...] = ()
) -> str:
    """Name what is missing, in the operator's language — a refusal that does not say what to do is a wall.

    ``leading`` comes FIRST because it is the ACTIONABLE half. The tally built below names KINDS
    (``1 refused line(s): arc_illisible``), and a kind is not a geste: it tells the operator a class
    and leaves them to find which of thirteen files carries it. Sentences passed here name the FILE.
    """
    reasons = [*leading, *unreadable_reasons(reading, role=role)]
    if reading.problems:
        kinds = sorted({problem.kind for problem in reading.problems})
        reasons.append(f"{len(reading.problems)} refused line(s): {', '.join(kinds)}")
    return " · ".join(reasons)


def _read_text(path: Path) -> tuple[str | None, str]:
    """The bytes of ``path``, or ``(None, why)`` — never an exception, on any hostile tree."""
    # A symlink is refused rather than followed, and the barrier says the SAME sentence by importing
    # it — see :data:`LIEN_SYMBOLIQUE` for the measurement and for why there is no second copy.
    if path.is_symlink():
        return None, (LIEN_CASSE if not path.exists() else LIEN_SYMBOLIQUE)
    try:
        # `utf-8-sig`, NOT `utf-8`: a BOM at the head of a plan breaks the read, and a BOM shows
        # up on its own the moment a Windows editor or an export touches the file. "Nobody will
        # write that" is a property of the MOMENT, never of the code. `utf-8-sig` reads both: it
        # strips the BOM if it is there, and behaves like `utf-8` otherwise — no cost, no regression.
        return path.read_text(encoding="utf-8-sig"), ""
    except FileNotFoundError:
        # `FileNotFoundError` also fires for an entry that EXISTS and cannot be resolved — a broken
        # symlink. Answering ABSENT there is the third state degrading into the first: the report
        # then tells the operator to "create the file", and the file is already sitting right there.
        # The question "does the entry exist?" is `lexists`, never `exists`.
        if path.is_symlink() or os.path.lexists(path):
            return None, LIEN_CASSE
        return None, ""
    except (OSError, UnicodeDecodeError) as error:
        return None, f"unreadable file ({type(error).__name__})"


def read_plan_file(plan_path: Path, name: str, *, role: str = ROLE_PLAN) -> ProjectPlan:
    """State one plan FILE, whatever it is called — the same three-state verdict, one implementation.

    Public because it is the hinge between a path and a verdict, and because a plan that is a single
    file stays perfectly legal: recursion is PERMITTED, never imposed (that project keeps 26 plan files flat
    and is the healthiest planning corpus measured in this repo).

    ``role`` decides what "readable" requires — see :func:`~.plan_format.unreadable_reasons`. It
    defaults to the whole-plan rule, so an existing caller judging one self-contained file is
    unaffected.
    """
    text, why = _read_text(plan_path)
    if text is None:
        return (
            ProjectPlan(name, plan_path, ILLISIBLE, why=why)
            if why
            else ProjectPlan(name, plan_path, ABSENT)
        )
    reading = read_plan(text)
    if not is_readable(reading, role=role):
        return ProjectPlan(name, plan_path, ILLISIBLE, reading, _why_unreadable(reading, role=role))
    return ProjectPlan(name, plan_path, LISIBLE, reading)


def arc_tree(folder: Path) -> tuple[str, ...]:
    """Every ``.md`` under ``<folder>/plan/``, at any depth, relative to ``folder`` — sorted.

    Relative rather than absolute so the pure splitter in ``plan_format`` sees exactly the shape the
    pre-commit barrier hands it from ``git ls-files``. Two path namespaces would be two rules, and
    the day they disagreed a file would be judged by neither.

    Public, and that is the repair rather than a tidy-up: ``plan_new_run`` had written its own
    ``rglob`` over the same directory, and the two answers were not the same answer. This walk is
    what a plan's contents ARE; a caller that needs them asks here.
    """
    arcs_dir = folder / ARCS_DIRNAME
    if not arcs_dir.is_dir():
        return ()
    try:
        # ``not is_dir()`` rather than ``is_file()``, and the difference is a whole class of wrong
        # CAUSE. ``is_file()`` follows the link, so a BROKEN symlink under ``plan/`` simply vanished
        # from this walk — and the door still naming it was then accused of ``index_sans_fichier``,
        # i.e. the DOOR was blamed for a defect of the FILE, with a gesture ("remove the entry")
        # that destroys a real index line. ``git ls-files`` never dropped it, so the barrier and this
        # walk answered on two different corpora. What is judged is what EXISTS at the path; a
        # directory is excluded because git lists its contents instead of itself.
        found = [child for child in arcs_dir.rglob("*.md") if not child.is_dir()]
    except OSError:  # pragma: no cover - a tree that vanishes mid-walk
        return ()
    return tuple(sorted(child.relative_to(folder).as_posix() for child in found))


def plan_files(folder: Path) -> tuple[Path, ...]:
    """Every FILE the plan rooted at ``folder`` is made of — its door first, then its arcs, sorted.

    ``()`` when there is no door: a directory without one is not a plan, at any level (D166, clause
    3). Nested doors come back as arcs here, because the question this answers is "which bytes are
    plan material?", not "how many plans are there" — :func:`read_plan_tree` answers that one.

    Public, and that is the whole point of it existing. Three callers needed this walk the day the
    plan became a folder — two test modules and a third — and each had written its own: a corpus
    discovered by a second rule is a corpus that can quietly disagree with the one this repo really
    judges, and the disagreement shows up as a suite grading files nobody grades. It reads the DISK
    rather than a reading, so it still answers on a plan whose door is broken; a corpus that
    disappears because a file became unreadable is the silence, not the safety.
    """
    door = next((folder / name for name in DOOR_FILENAMES if os.path.lexists(folder / name)), None)
    if door is None:
        return ()
    return (door, *(folder / relative for relative in arc_tree(folder)))


def read_plan_tree(folder: Path, name: str) -> tuple[ProjectPlan, ...]:
    """State the plan rooted at ``folder`` — its door, its arcs, and every plan nested inside it.

    Returns the folder's own verdict FIRST, then one verdict per ARC THAT COULD NOT BE READ, then
    one per nested plan (a directory under ``plan/`` carrying its own door — clause 3, same rule at
    every level). Nested plans are reported rather than folded in: they have their own cap and their
    own identity scope, so a broken one must be nameable on its own line. Folding them would have
    hidden it behind its parent's verdict.

    **ONE UNREADABLE ARC USED TO ERASE THE WHOLE PLAN, and that is what this walks back.** The loop
    below returned on the first arc it could not open, so the plan came back ILLISIBLE with NO
    reading at all: measured on the real plan the day it became a folder, ``\\xff\\xfe`` appended to
    ONE of thirteen files took ``scan_plans`` from 43 items to **0**, and every surface that reads
    this registry — ``make plans``, ``make ui-json``, the parked-runs queue — went blank together.
    Before the folder form a broken plan was one broken file; after it, a blast radius of thirteen.
    A population EXCLUDED is a population UNJUDGED, not a population at rest.

    So an unreadable arc now degrades ITSELF, on three tracks that each close a different silence:

    1. the plan keeps its door and its READABLE arcs, so 12 arcs no longer disappear behind 1;
    2. the loss is a named ``PlanProblem`` in the merged reading — :func:`~.plan_format.is_readable`
       refuses ANY reading carrying a problem, so the plan stays ILLISIBLE and nothing that used to
       be refused is now waved through. The verdict is unchanged; only its blast radius shrinks;
    3. the arc gets its OWN ``ProjectPlan`` line, ILLISIBLE, with ``reading=None`` and its own path.
       That third track is not decoration — it is the symmetric hole, measured: ``ui_contract``'s
       parked-runs queue names a loss on ``reading is None`` and says NOTHING otherwise, so handing
       it a populated reading would have turned "its parked runs are invisible here" into an empty
       ``why`` on a queue that is short. A queue that is silently short reads as good news.

    The DOOR keeps the hard return above: a plan whose door cannot be read has no cap, no index and
    no identity ledger — there is nothing left to degrade INTO. That is the floor, not the same case.

    A folder with no ``plan/`` directory yields exactly what :func:`read_plan_file` yielded before
    this arc — the mono-file plan is not a degraded case, it is the floor.
    """
    door_name = next(
        (candidate for candidate in DOOR_FILENAMES if os.path.lexists(folder / candidate)),
        None,
    )
    if door_name is None:
        return (read_plan_file(folder / PLAN_FILENAME, name),)
    door_path = folder / door_name

    # Walked BEFORE the door is even read: `arc_tree` is a pure filesystem walk under `plan/` and
    # never needs the door's own bytes, so nothing below depends on reaching this line — moving it
    # earlier changes nothing on the readable path and is what lets the branch just below fold
    # nested sub-plans in instead of discarding them.
    tree = arc_tree(folder)
    _, nested = plan_entries("", tree)

    def nested_plans() -> list[ProjectPlan]:
        found: list[ProjectPlan] = []
        for relative in nested:
            inner = (folder / ARCS_DIRNAME / relative).parent
            found.extend(
                read_plan_tree(inner, f"{name}/{ARCS_DIRNAME}/{relative.rsplit('/', 1)[0]}")
            )
        return found

    door_text, why = _read_text(door_path)
    if door_text is None:
        # AUDIT DELEGATED ON 2026-08-15 (via `J1`, measured by the orchestrator): this branch
        # used to return BEFORE reaching `arc_tree(folder)` — a sub-plan nested under `plan/`, with
        # its OWN door and its OWN identity (see above), disappeared WHOLE the moment the ROOT
        # door alone was unreadable, even though nothing in its own sub-tree was at fault.
        # `make plans`, `make lot-emit` and `make plan-gate-emit` lost the verdict of an
        # entire sub-tree — including a real defect living inside it — over an unreadable root
        # door that reads as "nothing to report" instead of "I did not look here".
        # Same class as the one named above for an isolated arc, one level up: an EXCLUDED
        # population is a population NOT JUDGED, never a population at rest.
        return (
            ProjectPlan(name, door_path, ILLISIBLE, why=why or "unreadable door"),
            *nested_plans(),
        )

    #: ``(path relative to the door, why it could not be read)`` — the arcs that are NOT folded in.
    unreadable: list[tuple[str, str]] = []

    def lost(member: str, why: str) -> PlanProblem:
        unreadable.append((member, why or "not found"))
        # `line=0` and no `source`: the same shape `index_problems` gives `arc_hors_index`, the
        # other refusal that is about a FILE and has no line to point at. The path travels in
        # the detail there, so it travels in the detail here — one wording for one question.
        return PlanProblem(
            0,
            ARC_ILLISIBLE,
            f"{member}: {why or 'not found'} — its items are MISSING from the displayed count;"
            " repair or restore this file",
        )

    # The fold is NOT written here. `fold_plan` owns the one enumeration of a plan's arcs, and the
    # birth command calls the same one: a second walk of the disk is what refused a plan's second
    # sibling sub-plan while the barrier accepted it.
    reading = fold_plan(
        door_text,
        tree,
        lambda member: _read_text(folder / member),
        folder_form=(folder / ARCS_DIRNAME).is_dir(),
        on_loss=lost,
    )
    mine = (
        ProjectPlan(name, door_path, LISIBLE, reading)
        if is_readable(reading, role=ROLE_PLAN)
        else ProjectPlan(
            name,
            door_path,
            ILLISIBLE,
            reading,
            _why_unreadable(
                reading, leading=tuple(f"{member}: {why}" for member, why in unreadable)
            ),
        )
    )
    found = [mine]
    # Each unreadable arc, on its OWN line, with `reading=None` — the shape every consumer already
    # branches on to say "this one was not read". See the docstring: without it the parked-runs
    # queue goes from a named loss to silence.
    found.extend(
        ProjectPlan(f"{name}/{member}", folder / member, ILLISIBLE, why=why)
        for member, why in unreadable
    )
    found.extend(nested_plans())
    return tuple(found)


def _read_one(project_dir: Path, name: str) -> tuple[ProjectPlan, ...]:
    return read_plan_tree(project_dir, name)


def _visible_dirs(parent: Path) -> list[Path]:
    """Sorted sub-directories, skipping dotted ones (``.git``, ``.obsidian``: tooling, not projects)."""
    return sorted(
        (child for child in parent.iterdir() if child.is_dir() and not child.name.startswith(".")),
        key=lambda child: child.name,
    )


def scan_projects(projects_root: Path) -> PlanRegistry:
    """Walk ``projects/`` and state, per project, whether its plan is readable, absent or broken."""
    if not projects_root.is_dir():
        return PlanRegistry(projects=(), root_exists=False)
    found: list[ProjectPlan] = []
    misplaced: list[str] = []
    for bubble in _visible_dirs(projects_root):
        if any(bubble.glob("*.md")):
            misplaced.append(bubble.name)
        for project in _visible_dirs(bubble):
            found.extend(_read_one(project, f"{bubble.name}/{project.name}"))
    return PlanRegistry(projects=tuple(found), misplaced=tuple(misplaced))


def scan_plans(repo_root: Path) -> PlanRegistry:
    """Every DECLARED plan root, plus every project — the one scan, over one list of roots.

    This is clause 1 of D166 doing its only job. Before it, ``make plans`` walked ``projects/`` and
    nothing else, so the single plan that could not live there — Mnemosyne's own — was invisible to
    the surface that judges plans, and had to be judged by a second mechanism written specially for
    it. One reader, one barrier, one vocabulary means the exception is a LINE in a list, not a
    parallel code path.
    """
    projects = scan_projects(repo_root / PROJECTS_DIRNAME)
    roots: list[ProjectPlan] = []
    for root in PLAN_ROOTS:
        folder = repo_root / root
        if folder.is_dir():
            roots.extend(read_plan_tree(folder, ROOT_NAMES.get(root, root)))
    return PlanRegistry(
        projects=tuple(roots) + projects.projects,
        misplaced=projects.misplaced,
        root_exists=projects.root_exists,
    )
