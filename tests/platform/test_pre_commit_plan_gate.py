"""``.githooks/pre-commit`` must REFUSE an illisible plan — never print without a non-zero exit.

Why this file exists: a previous control AFFICHAIT the word "illisible" on stdout and exited 0
regardless (``python -c "print(...)"`` always exits 0, whatever it prints), so the ``&&`` chaining
it to the commit let the bad plan through. A control that prints without exiting non-zero is a
comment, not a barrier (measured, 2026-07-28) — this suite pins the two halves that make
``.githooks/pre-commit`` an actual barrier, hermetically:

1. **The shell layer** reacts ONLY to the door (``PLAN.md`` / ``PLAN_COURANT.md``) and to the arcs
   of a ``plan/`` folder, ANYWHERE and at any depth, whatever happened to them — it filters on the
   SHAPE of a staged path and never on its LOCATION (section 3bis: a hard-coded list of two roots is
   what let a NESTED plan through) nor on its diff status (section 6: filtering on statuses is what
   let ``git mv`` through). It exits 0 immediately without spawning anything when none match (a door
   slower than the wall is never used — this hook runs on EVERY commit in the repo), and forwards
   the judge's exit code verbatim when a plan IS staged. Proven by putting
   a FAKE ``uv`` on ``PATH`` — the hook's only external dependency once a plan is staged — so the
   assertion is "was the judge reached, and with what verdict propagated", never a real distillation
   environment. This also means these tests never touch the real repo's git index or its ``.venv``.
2. **The judgment rule** (``reading.readable and not reading.problems``) matches
   ``plan_registry.read_plan_file``'s own LISIBLE/ILLISIBLE policy on the exact sabotage this hook
   was built to catch: an item's status glyph replaced by one ``STATUS_BY_GLYPH`` does not know.
3. **The wiring between the two** — the embedded heredoc's OWN ``sys.exit`` calls, with the REAL
   ``uv``/``system/lib``, never a stand-in. Neither (1) nor (2) alone would catch the historical
   defect itself: (1) shims the judge away entirely, and (2) never runs the heredoc. Only a real
   ``git worktree`` off HEAD (never the live repo — another session may hold uncommitted edits in
   its working tree, and a worktree reads committed objects only, untouched by that) exercises the
   exact bytes this hook ships.
"""

from __future__ import annotations

import ast
import os
import shutil
import stat
import subprocess
from collections.abc import Iterator
from pathlib import Path

import pytest
from _invariants import REPO_ROOT

from mnemosyne.production.plan_format import ARCS_DIRNAME, DOOR_FILENAMES, read_plan
from mnemosyne.production.plan_registry import (
    ILLISIBLE,
    LIEN_SYMBOLIQUE,
    _read_text,
    read_plan_tree,
)

HOOK = REPO_ROOT / ".githooks" / "pre-commit"

#: Records that it was called, drains stdin so the real hook never blocks writing its heredoc into
#: a pipe nobody reads, then exits with whatever code the test asked for. This is a stand-in for
#: the ONLY external command the hook runs once it has decided a plan is staged.
_FAKE_UV = """#!/bin/sh
echo "called with: $*" >> "$FAKE_UV_LOG"
cat >/dev/null
exit "$FAKE_UV_EXIT"
"""


def _init_repo(path: Path) -> None:
    """A minimal, hermetic git repo — no relation to the real Mnemosyne clone or its index."""
    subprocess.run(["git", "init", "-q", "-b", "main", str(path)], check=True)
    subprocess.run(["git", "-C", str(path), "config", "user.email", "test@example.invalid"], check=True)
    subprocess.run(["git", "-C", str(path), "config", "user.name", "Test"], check=True)


def _stage(repo: Path, relative: str, content: str = "contenu") -> None:
    """Write ``relative`` under ``repo`` and stage it — never committed, only INDEXED."""
    target = repo / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "--", relative], check=True)


def _fake_uv(tmp_path: Path, *, exit_code: int) -> tuple[Path, Path]:
    """A ``PATH`` directory shadowing ``uv`` with a shim, plus the log file it writes to."""
    fakebin = tmp_path / "fakebin"
    fakebin.mkdir(exist_ok=True)
    shim = fakebin / "uv"
    shim.write_text(_FAKE_UV, encoding="utf-8")
    shim.chmod(0o755)
    log = tmp_path / "fake_uv.log"
    _ = exit_code  # the exit code travels via env at run time, not baked into the shim
    return fakebin, log


def _run_hook(repo: Path, *, fakebin: Path, log: Path, judge_exit: int) -> subprocess.CompletedProcess[str]:
    env = {
        **os.environ,
        "PATH": f"{fakebin}:{os.environ['PATH']}",
        "FAKE_UV_LOG": str(log),
        "FAKE_UV_EXIT": str(judge_exit),
    }
    return subprocess.run(
        [str(HOOK)], cwd=repo, capture_output=True, text=True, env=env, timeout=30, check=False
    )


def test_hook_file_is_executable() -> None:
    """The precondition every proof in the report depends on: without ``+x`` git silently skips it."""
    assert HOOK.is_file(), f"missing: {HOOK}"
    assert HOOK.stat().st_mode & stat.S_IXUSR, "the hook must be chmod +x or core.hooksPath skips it"


def test_no_plan_staged_exits_zero_and_never_reaches_the_judge(tmp_path: Path) -> None:
    """The door faster than the wall: nothing plan-shaped staged -> exit 0, ``uv`` never touched.

    Staged as ONE commit, which is the question this test asks and the parametrised
    :func:`test_the_prefilter_SELECTION_on_a_NAMED_list_of_paths` cannot: the whole batch must leave
    ``plans`` empty, so a single pattern loosened by one character spawns the judge on every commit
    of the repo. Which of them matched is that other test's job, path by path.
    """
    _init_repo(tmp_path)
    for near_miss in _NOT_SELECTED:
        _stage(tmp_path, near_miss)
    fakebin, log = _fake_uv(tmp_path, exit_code=0)
    done = _run_hook(tmp_path, fakebin=fakebin, log=log, judge_exit=0)
    assert done.returncode == 0, done.stderr
    assert not log.exists(), (
        "the judge (uv) was invoked although no in-scope plan was staged: "
        f"{log.read_text() if log.exists() else ''}"
    )


@pytest.mark.parametrize(
    ("relative", "judge_exit"),
    [
        ("docs/PLAN_COURANT.md", 0),
        ("docs/PLAN_COURANT.md", 1),
        # A real project in THIS repo is named with a space ("Acme Research") — the hook must
        # split staged paths on newlines only, never on IFS-default spaces, or this silently
        # never matches `projects/*/*/PLAN.md` and its plan is never judged.
        ("projects/saas/Acme Research/PLAN.md", 0),
        ("projects/saas/Acme Research/PLAN.md", 1),
    ],
)
def test_a_staged_plan_reaches_the_judge_and_its_verdict_is_forwarded(
    tmp_path: Path, relative: str, judge_exit: int
) -> None:
    """Every path shape the hook must recognise reaches the judge, and the verdict is not swallowed.

    Parametrised on BOTH exit codes: a hook that hardcoded ``exit 0`` after calling the judge would
    still show "called" here and only THIS half would catch it — exactly the defect this hook exists
    to close (a check that prints but exits 0 regardless of its own verdict).
    """
    _init_repo(tmp_path)
    _stage(tmp_path, relative, "# PLAN — x\n")
    fakebin, log = _fake_uv(tmp_path, exit_code=judge_exit)
    done = _run_hook(tmp_path, fakebin=fakebin, log=log, judge_exit=judge_exit)
    assert log.exists(), "the judge (uv) was never invoked for a staged in-scope plan path"
    assert done.returncode == judge_exit, (
        f"the hook must forward the judge's exit code verbatim (got {done.returncode}, expected "
        f"{judge_exit}): stderr={done.stderr!r}"
    )


# ---------------------------------------------------------------------------------------------
# 3bis. The prefilter asks a question of FORM, never of LOCATION — and the two named lists that
#       pin BOTH edges of it.
#
# Found by the third isolated audit, reproduced with a real commit in a throwaway clone before this
# list existed: a nested door plus an orphaned arc it never indexes -> exit 0, HEAD moves.
# `owning_plan` implements D166 clause 3 correctly ("a folder carrying a door IS a plan, at ANY
# level"); the hook's `case` knew exactly TWO hard-coded locations, this repo's real plan root and
# `projects/*/*/…`. A list of locations forgets one more location the same way a list of diff
# statuses forgets one more status — and nesting is not an edge case here, it is THE shape the scale
# targets (a hundred theories, each with its own strategies, ~150x today's volume).
#
# WHAT THE WIDENING COULD HAVE DUG, and the measure that says it did not: a location-free pattern
# refuses commits the old one waved through, so it can only be a floor if it kills nothing that was
# innocent. Both `case` bodies were run over EVERY path of this repo — 420 tracked, 64730 on disk
# including the gitignored `projects/` — and the two SELECTED SETS are identical, character for
# character (this repo's real plan door; plus `projects/mnemosyne/ui/PLAN.md` on disk). Zero paths
# carry a `plan/` segment today, so the widening costs nothing measurable and adds no refusal.
#
# TWO NEAR MISSES CHANGED SIDES ON PURPOSE, and that is a decision rather than a slip:
# `projects/x/PLAN.md` and `projects/x/plan/arc-c.md` used to be listed as innocent because they are
# one directory short of `projects/*/*/…`. They are not innocent: `owning_plan` claims ANY file
# named `PLAN.md`, wherever it sits, so a bubble-level door was a plan the reader judged and the
# barrier could not see. The prefilter is now a SUPERSET of what `owning_plan` can claim — (a) a
# basename in `DOOR_FILENAMES`, (b) a path under `<folder>/plan/` — restricted on (b) to `.md`,
# which is the one place the two still differ (see the module-level note on `plan/notes.txt`).
# ---------------------------------------------------------------------------------------------

#: REAL locations, named one by one. A plan is judged here or it is judged by nothing at all: this
#: is the list that would have caught the audit's commit, and it is written as ADDRESSES rather than
#: as a rule so that it cannot drift with the rule it checks.
_SELECTED = (
    # The door, under its two declared names, at the roots that exist today.
    "docs/PLAN.md",
    "docs/PLAN_COURANT.md",
    "projects/saas/Acme Research/PLAN.md",
    # An ARC of a plan that became a folder. THIS is what the hook was blind to before 2026-07-29:
    # none of these matched the old hard-coded pattern (this repo's real plan door, or
    # `projects/*/*/PLAN.md`), so `plans` stayed empty and the hook exited 0 — the barrier
    # disappeared without a word the day the form changed.
    "docs/plan/arc-c.md",
    "docs/plan/c/arc-1.md",
    "projects/saas/Acme Research/plan/arc-c.md",
    # NESTING, which is the whole of clause 3 and the whole of the intended scale. The first two are
    # the audit's exact commit; the next two are three levels of `plan/` inside `plan/`; the last two
    # are a door four levels down — the shape `projects/trading/example_lab/` already has on disk.
    "docs/gov/PLAN.md",
    "docs/gov/plan/orphelin.md",
    "docs/a/plan/b/plan/c/PLAN.md",
    "docs/a/plan/b/plan/c/plan/arc-a.md",
    "projects/trading/example_lab/theories/T001/PLAN.md",
    "projects/trading/example_lab/plan/theories/T001/PLAN.md",
    # A bubble-level door and a bubble-level `plan/`: one directory short of the OLD pattern, and
    # claimed by `owning_plan` all the same. Listed as innocent until 2026-07-29; they were not.
    "projects/x/PLAN.md",
    "projects/x/plan/arc-c.md",
    # The repo ROOT itself — `owning_plan` answers `""` for a door there, so the prefilter must too.
    "PLAN.md",
    "plan/arc-c.md",
    # A space and a `:` in the name: 1775 of the 8165 paths under `projects/` carry a space,
    # 9 carry a `:`.
    "projects/saas/Acme Research/plan/Vpilot-S:S et suite.md",
    # ACCENTS. Found by running the real hook against the real plan, not by reading it: `git diff
    # --cached --name-only` QUOTES any path outside plain ASCII (`"plan/arc oubli\303\251.md"`),
    # and the leading `"` matches no `case` pattern — so the file was never judged and the hook
    # exited 0. 80 paths of this repo carry accents. This hole predates the folder form; it was
    # simply unreachable while every plan path was ASCII.
    "docs/plan/arc économie.md",
    "projects/examples/Café Notes/PLAN.md",
)

#: The other edge, and it is the one a location-free pattern makes fragile: every entry here sits
#: ONE character away from a match. A catch rate with no false-kill rate is a wall — and this hook
#: runs on EVERY commit of the repo, so a pattern loose enough to catch these judges files it was
#: never asked to gate, forever.
_NOT_SELECTED = (
    "README.md",
    # Not the imposed filename — and `myPLAN.md` is the one that proves `*/PLAN.md` demands a real
    # `/` before the name rather than merely ENDING with it.
    "docs/PLAN_ANCIEN.md",
    "docs/myPLAN.md",
    "PLAN_ANCIEN.md",
    # The `plan` segment, on both edges: plural, a longer segment to the right, a longer one to the
    # left, and a FILE named plan.md rather than a directory.
    "docs/plans/arc-c.md",
    "docs/plan-b/arc-c.md",
    "docs/replan/arc-c.md",
    "docs/plan.md",
    # Under `plan/` and not an arc. The one place the prefilter is NARROWER than `owning_plan`,
    # deliberately: judging every image and every `.txt` of a plan folder on every commit buys
    # nothing (a non-markdown file changes no verdict — `plan_entries` only merges `.md`).
    "docs/plan/notes.txt",
)


@pytest.mark.parametrize("relative", _SELECTED)
def test_the_prefilter_SELECTION_on_a_NAMED_list_of_paths(tmp_path: Path, relative: str) -> None:
    """Every REAL address a plan can have must REACH the judge — silence here is the whole defect.

    One agent per path rather than one batch: "the judge was reached" is a single bit, so a batch
    that matched on ONE path would go green while every other address stayed invisible. That is
    exactly how the nested plan survived — this repo's real plan door matched, so the filter looked alive.

    Named ADDRESSES and not a re-derivation of the patterns: a reference computed from the thing it
    verifies proves only that the thing equals itself. This list is also what keeps the end-to-end
    fixtures free to live at a neutral root (section 5bis) without the real locations going unproven.
    """
    _init_repo(tmp_path)
    _stage(tmp_path, relative, "# PLAN — x\n")
    fakebin, log = _fake_uv(tmp_path, exit_code=0)
    _run_hook(tmp_path, fakebin=fakebin, log=log, judge_exit=0)
    assert log.exists(), f"the judge was never invoked for the staged plan path {relative!r}"


@pytest.mark.parametrize("relative", _NOT_SELECTED)
def test_the_prefilter_leaves_the_NAMED_near_misses_OUTSIDE(tmp_path: Path, relative: str) -> None:
    """The false-kill half, path by path — which one leaked is the whole information here."""
    _init_repo(tmp_path)
    _stage(tmp_path, relative, "# PLAN — x\n")
    fakebin, log = _fake_uv(tmp_path, exit_code=0)
    done = _run_hook(tmp_path, fakebin=fakebin, log=log, judge_exit=0)
    assert done.returncode == 0, done.stderr
    assert not log.exists(), (
        f"{relative!r} is not a plan and the judge was spawned for it — this hook runs on EVERY "
        "commit of the repo"
    )


def _case_patterns() -> tuple[str, ...]:
    """Every pattern of the hook's own ``case "$f" in`` block, read out of the shipping bytes.

    Parsed from the shell rather than re-declared here: the point of the test below is that the two
    files hold ONE contract, so the second copy must be the hook's real one and not a transcription.
    """
    text = HOOK.read_text(encoding="utf-8")
    start = text.index('case "$f" in')
    body = text[start : text.index("esac", start)]
    patterns: list[str] = []
    for raw in body.splitlines():
        line = raw.strip()
        if line.startswith("#") or not line.endswith(")"):
            continue
        patterns.extend(p.strip() for p in line[:-1].split("|"))
    return tuple(p for p in patterns if p)


def test_the_hooks_case_is_DERIVED_from_the_readers_constants_and_names_no_location() -> None:
    """The shell now COPIES ``DOOR_FILENAMES`` and ``ARCS_DIRNAME``, and a copy drifts.

    The prefilter must stay a SUPERSET of what ``owning_plan`` can claim, and ``owning_plan`` claims
    exactly two things: a file whose basename is in ``DOOR_FILENAMES``, and a path under
    ``<folder>/plan/``. Adding a third door name to the reader while forgetting the shell would not
    break a single other test — it would make plans carrying that name invisible to the barrier, in
    silence, which is the same failure the hard-coded locations caused.

    The expected set is DERIVED from the Python constants (the single source) and compared to the
    hook's real bytes (the copy), so the two can only agree by actually agreeing. It also pins the
    absence of any LOCATION: no pattern may mention ``docs`` or ``projects``, because a pattern that
    names a place is the defect this section exists to close, and it would come back looking like a
    tightening rather than a regression.
    """
    expected = {name for name in DOOR_FILENAMES} | {f"*/{name}" for name in DOOR_FILENAMES}
    expected |= {f"{ARCS_DIRNAME}/*.md", f"*/{ARCS_DIRNAME}/*.md"}
    assert set(_case_patterns()) == expected, (
        "the hook's `case` and the reader's constants have drifted apart:\n"
        f"  hook     : {sorted(_case_patterns())}\n"
        f"  attendu  : {sorted(expected)}"
    )


def test_the_readability_rule_catches_the_exact_sabotage_this_hook_was_built_for() -> None:
    """``reading.readable and not reading.problems`` — the hook's whole verdict, on real bytes.

    Mirrors the manual worktree proof in the report: an item's status glyph replaced by an unknown
    one must flip a LISIBLE plan to refused, named ``statut_inconnu`` — never silently accepted.
    """
    good = "# PLAN — x\n\n> **Cap** : y\n\n- **A1** \U00002B1C Chronométrer les surfaces\n"
    reading = read_plan(good)
    assert reading.readable and not reading.problems, "a valid plan must be judged LISIBLE"

    sabotaged = good.replace("\U00002B1C", "\U00002753")
    reading = read_plan(sabotaged)
    assert not (reading.readable and not reading.problems), "the unknown glyph must flip the verdict"
    assert any(p.kind == "statut_inconnu" for p in reading.problems), reading.problems


def test_a_plan_with_no_cap_or_no_items_is_illisible_even_with_zero_named_problems() -> None:
    """The structural half of ILLISIBLE: ``reading.problems`` can be empty and the plan still fails.

    ``plan_registry.read_plan_file`` ORs two conditions (``not reading.readable OR
    reading.problems``); a hook that only checked ``problems`` would silently accept a plan with no
    cap and no items — the two ways a plan can carry zero refused lines and still be unreadable.
    """
    no_cap = "# PLAN — x\n\n- **A1** \U00002B1C un item\n"
    reading = read_plan(no_cap)
    assert not reading.problems, "this fixture must not ALSO trip a named refusal"
    assert not (reading.readable and not reading.problems)

    no_items = "# PLAN — x\n\n> **Cap** : y\n\nrien que de la prose.\n"
    reading = read_plan(no_items)
    assert not reading.problems
    assert not (reading.readable and not reading.problems)


#: The library the hook's heredoc and ``plan-nouveau`` both run out of. Overlaid from the WORKING
#: TREE onto the throwaway worktree, because a ``git worktree`` checks out committed objects only:
#: without it an end-to-end test runs today's hook against yesterday's reader and either explodes on
#: an import or — far worse — goes green on a rule that is not the one shipping.
#:
#: **THE WHOLE PACKAGE, never a list of modules, and that is D169's lesson paid a second time.**
#: Two hand-kept lists stood here (one for the hook, one for the scaffold, three files between them)
#: and they were exactly as durable as any list of places: the day the birth command started calling
#: the barrier's own walk — the repair that stopped a second sibling sub-plan being refused — three
#: end-to-end tests died on ``ImportError`` for a module nobody had thought to add. A superset
#: computed from the tree cannot forget a module; a list forgets one more every time.
_LIB = "system/lib/mnemosyne"


def _overlay_library(worktree: Path) -> Path:
    """Copy the working tree's ``mnemosyne`` package over the worktree's — every module, no list."""
    for source in sorted((REPO_ROOT / _LIB).rglob("*.py")):
        if "__pycache__" in source.parts:
            continue
        target = worktree / source.relative_to(REPO_ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    return worktree


def _worktree(tmp_path: Path) -> Path:
    """A detached worktree off HEAD carrying the WORKING-TREE hook and the library it imports.

    ``git worktree add`` reads committed objects only — it never touches the main repo's working
    tree or index, so this is safe while another session holds uncommitted edits there.
    """
    worktree = tmp_path / "wt"
    subprocess.run(
        ["git", "worktree", "add", "--detach", "--quiet", str(worktree), "HEAD"],
        cwd=REPO_ROOT,
        check=True,
    )
    hook = worktree / ".githooks" / "pre-commit"
    hook.write_text(HOOK.read_text(encoding="utf-8"), encoding="utf-8")
    hook.chmod(0o755)
    return _overlay_library(worktree)


def _run_real(worktree: Path, *, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    """Run the real hook on whatever is staged — the shipping bytes, the real ``uv``, real index."""
    return subprocess.run(
        [str(worktree / ".githooks" / "pre-commit")],
        cwd=worktree,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
        env=env,
    )


def _add(worktree: Path, *paths: str) -> None:
    """Stage ``paths``. ``-f`` because ``projects/*`` is gitignored in THIS repo (``.gitignore:40``),
    and ``projects/`` is the only root where a plan folder can be built with no door above it."""
    subprocess.run(["git", "-C", str(worktree), "add", "-f", "--", *paths], check=True)


def _erase(worktree: Path, *paths: str) -> None:
    """``git rm`` — a STAGED DELETION, the whole point: the path leaves the index and the disk."""
    subprocess.run(["git", "-C", str(worktree), "rm", "-q", "--", *paths], check=True)


def _commit_staged(worktree: Path, message: str) -> None:
    """Commit what is staged, hooks OFF — this is the FIXTURE, never the thing under test.

    ``core.hooksPath`` is repo-wide, so a worktree commit would otherwise run the very barrier being
    measured and the fixture would depend on its verdict. Detached HEAD: no branch of the real clone
    moves, and the commit is unreferenced the moment the worktree is removed.
    """
    subprocess.run(
        ["git", "-C", str(worktree), "-c", "core.hooksPath=/dev/null", "commit", "-q",
         "-m", message, "--no-verify"],
        check=True,
    )


def _commit_and_run(worktree: Path, paths: list[str]) -> subprocess.CompletedProcess[str]:
    """Stage ``paths`` and run the real hook — its verdict, on the real bytes, in the real index."""
    subprocess.run(["git", "-C", str(worktree), "add", "--", *paths], check=True)
    return _run_real(worktree)


def _write(worktree: Path, relative: str, text: str) -> None:
    target = worktree / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


# ---------------------------------------------------------------------------------------------
# 5bis. WHERE the end-to-end fixtures live — and why it is no longer this repo's real plan root.
#
# THE CLASS: a proof harness must survive THE VERY GESTURE the mechanism exists to permit. These
# tests used to write their fixtures at the REAL addresses of this repo's own plan door and one of
# its real arcs. Measured by the third isolated audit, in a clone: `make plan-convertir APPLY=1`
# succeeds (12 arcs, a 28-line door), the barrier accepts the result — and `pytest tests/` goes from
# 0 failures to 6, because a fixture door indexing ONE arc lands on top of twelve real ones and every
# real arc comes back `arc_hors_index`. A harness that is only valid until the plan is converted
# proves nothing about the day after, and it makes the conversion itself unaffordable.
#
# Now that the prefilter asks about FORM and not LOCATION (section 3bis), a plan is judged wherever
# it sits, so the fixtures move to a root that belongs to nobody. `epreuve/` is not gitignored, is
# not the address of any real plan, and only ever exists inside a throwaway worktree.
#
# THE HOLE THIS DIGS, and where it is closed: leaving the real plan's own address out of the fixtures
# means these tests stop proving that the REAL addresses are selected at all. That question is
# answered — by name, address by address, including this repo's own plan root,
# `projects/<bubble>/<project>/` and the nested forms — by
# `_SELECTED` / `test_the_prefilter_SELECTION_on_a_NAMED_list_of_paths` in section 3bis, which
# writes nothing anywhere near a real plan.
# ---------------------------------------------------------------------------------------------

#: The neutral root every end-to-end fixture below is anchored at. One constant, so the day a real
#: plan is ever born here the collision is fixed in ONE place instead of eight.
_EPREUVE = "epreuve"

#: A door and one arc — the smallest plan that is a FOLDER. The door names its cap and indexes its
#: arc; the arc carries the items. Neither file would be readable alone under the old single rule.
#:
#: The index entry is a BULLET, and that is not cosmetic: ``index_problems`` only counts a
#: ``plan/…md`` sitting in ENTRY POSITION of a bullet or a table row, outside a code block. A bare
#: paragraph (what this fixture used to write) is prose, and prose reading as an index entry is the
#: false accusation that refused the very commit documenting this barrier.
_DOOR = "# PLAN — demo\n\n> **Cap** : prouver la forme\n\n## Arcs\n\n- plan/arc-c.md — le lecteur\n"
_ARC = "# arc C\n\n- **C1** \U00002B1C un item\n"


def test_end_to_end_a_plan_that_is_a_FOLDER_is_accepted_by_the_real_heredoc(tmp_path: Path) -> None:
    """Door (cap, no item) + arc (items, no cap) = a readable plan. The scission of ``readable``,
    proven where it ships: under the old rule BOTH files were unreadable and this commit was
    impossible."""
    worktree = _worktree(tmp_path)
    try:
        _write(worktree, f"{_EPREUVE}/PLAN.md", _DOOR)
        _write(worktree, f"{_EPREUVE}/plan/arc-c.md", _ARC)
        done = _commit_and_run(worktree, [f"{_EPREUVE}/PLAN.md", f"{_EPREUVE}/plan/arc-c.md"])
        assert done.returncode == 0, f"a valid folder plan must pass: {done.stderr}"
    finally:
        subprocess.run(
            ["git", "worktree", "remove", "--force", str(worktree)], cwd=REPO_ROOT, check=False
        )


@pytest.mark.parametrize(
    ("door", "arcs", "expected"),
    [
        # An arc on the disk that the door's index does not name. THE central clause (D166 #4):
        # measured on Acme Research, the most recent plan file declares `lire_en_premier: true` and the
        # door written 3 h earlier does not know it exists. A hand-held index rots in hours.
        (_DOOR, {"arc-c.md": _ARC, "arc-d.md": "- **D1** \U00002B1C x\n"}, "arc_hors_index"),
        # The mirror: an index entry with no file behind it. In BULLET form — a bare paragraph is
        # prose since `index_problems` was hardened, and prose no longer indexes anything.
        (_DOOR + "\n- plan/arc-disparu.md — un arc disparu\n", {"arc-c.md": _ARC}, "index_sans_fichier"),
        # The identity scope is the FOLDER, not the file: without that, cutting a plan into arcs
        # makes every cross-arc collision invisible, in silence, on the very edit that creates them.
        (
            _DOOR + "\n- plan/arc-d.md — le second\n",
            {"arc-c.md": _ARC, "arc-d.md": "- **C1** \U00002B1C le meme identifiant\n"},
            "id_duplique",
        ),
        # And nothing of arc C8 is lost: an unknown glyph inside an ARC is still refused by name.
        (_DOOR, {"arc-c.md": _ARC.replace("\U00002B1C", "\U00002753")}, "statut_inconnu"),
    ],
)
def test_end_to_end_the_real_heredoc_REFUSES_a_folder_plan_that_lies(
    tmp_path: Path, door: str, arcs: dict[str, str], expected: str
) -> None:
    """Four refusals, each proven through the shipping bytes — never through the library alone.

    The barrier reads the INDEX, so these also prove the folder walk works on ``git ls-files``
    output and not merely on a directory listing.
    """
    worktree = _worktree(tmp_path)
    try:
        _write(worktree, f"{_EPREUVE}/PLAN.md", door)
        for name, text in arcs.items():
            _write(worktree, f"{_EPREUVE}/plan/{name}", text)
        done = _commit_and_run(
            worktree, [f"{_EPREUVE}/PLAN.md", *(f"{_EPREUVE}/plan/{name}" for name in arcs)]
        )
        assert done.returncode != 0, f"the barrier must refuse: {done.stdout}{done.stderr}"
        assert expected in done.stderr, done.stderr
        assert "git commit --no-verify" in done.stderr
    finally:
        subprocess.run(
            ["git", "worktree", "remove", "--force", str(worktree)], cwd=REPO_ROOT, check=False
        )


def test_end_to_end_the_real_heredoc_refuses_then_accepts_in_a_throwaway_worktree(
    tmp_path: Path,
) -> None:
    """The one test that runs the REAL ``uv``/``read_plan`` inside the hook, not a stand-in.

    ``git worktree add`` checks out committed OBJECTS only — it never reads or touches the main
    repo's working tree or index, so this is safe to run even while another session holds
    uncommitted edits there (verified manually before this test was written: the concurrent
    session's unstaged changes to ``plan_format.py`` were untouched after a full worktree
    add/commit/remove cycle). The plan content is written fresh at the neutral root rather than
    sabotaging this repo's real plan-door bytes: that file is live, edited by other sessions,
    and about to become a FOLDER of twelve arcs — a fixture sitting on its address is a fixture that
    dies the day the conversion this whole barrier exists to allow actually happens (section 5bis).
    """
    worktree = _worktree(tmp_path)
    try:
        hook = worktree / ".githooks" / "pre-commit"
        plan = worktree / _EPREUVE / "PLAN.md"
        plan.parent.mkdir(parents=True, exist_ok=True)
        good = "# PLAN — x\n\n> **Cap** : y\n\n- **A1** \U00002B1C un item\n"
        plan.write_text(good, encoding="utf-8")
        subprocess.run(["git", "-C", str(worktree), "add", f"{_EPREUVE}/PLAN.md"], check=True)
        done = subprocess.run(
            [str(hook)], cwd=worktree, capture_output=True, text=True, timeout=120, check=False
        )
        assert done.returncode == 0, f"a valid plan must pass: {done.stderr}"

        sabotaged = good.replace("\U00002B1C", "\U00002753")
        plan.write_text(sabotaged, encoding="utf-8")
        subprocess.run(["git", "-C", str(worktree), "add", f"{_EPREUVE}/PLAN.md"], check=True)
        done = subprocess.run(
            [str(hook)], cwd=worktree, capture_output=True, text=True, timeout=120, check=False
        )
        assert done.returncode != 0, "the REAL heredoc must refuse the unknown-glyph sabotage"
        assert f"{_EPREUVE}/PLAN.md" in done.stderr
        assert "illisible" in done.stderr
        assert "statut_inconnu" in done.stderr
        assert "git commit --no-verify" in done.stderr, (
            "a barrier that does not name its own override is a barrier nobody can use in an "
            f"emergency and everybody ends up uninstalling instead: {done.stderr!r}"
        )
    finally:
        subprocess.run(
            ["git", "worktree", "remove", "--force", str(worktree)],
            cwd=REPO_ROOT,
            check=False,
        )


#: Six fields, in canonical order — an item that `champs_requis_pour` (level 2 on a DOOR)
#: lets through, so the test TRULY isolates H4's clause rather than going red on A1.
_SIX_CHAMPS = (
    "  *Produit* : p\n  *Fini quand* : f\n  *Dépend de* : AUCUNE\n  *Prérequis* : AUCUN\n"
    "  *À lire* : a\n  *Taille* : t\n"
)


def test_end_to_end_H4_une_promotion_qui_perd_un_item_est_REFUSEE_puis_ACCEPTEE(
    tmp_path: Path,
) -> None:
    """`H4`, `*Fini quand*`, on the REAL HEREDOC — the filiation clause was a barrier that
    nothing called (measured by the orchestrator: a single call site outside its own definition,
    a docstring). This test IS the invocation site, on the real
    `uv`/`read_plan`/`filiation_problems`, in a throwaway worktree — never a stand-in.
    """
    worktree = _worktree(tmp_path)
    try:
        hook = worktree / ".githooks" / "pre-commit"
        predecesseur = worktree / _EPREUVE / "archive" / "plan-v1.md"
        predecesseur.parent.mkdir(parents=True, exist_ok=True)
        predecesseur.write_text(
            "# PLAN — v1\n\n> **Cap** : v1\n\n"
            "- **A1** \U00002B1C jamais repris, jamais retiré — DOIT être accusé.\n"
            "- **A2** \U00002705 déjà fait — ne doit JAMAIS être accusé.\n",
            encoding="utf-8",
        )
        successeur = worktree / _EPREUVE / "PLAN.md"
        successeur.write_text(
            f"# PLAN — v2\n\n> **Cap** : v2\n> **Succède à** : {_EPREUVE}/archive/plan-v1.md\n\n"
            f"- **B1** \U00002B1C neuf.\n{_SIX_CHAMPS}",
            encoding="utf-8",
        )
        subprocess.run(
            ["git", "-C", str(worktree), "add", f"{_EPREUVE}/archive/plan-v1.md", f"{_EPREUVE}/PLAN.md"],
            check=True,
        )
        refuse = subprocess.run(
            [str(hook)], cwd=worktree, capture_output=True, text=True, timeout=120, check=False
        )
        assert refuse.returncode != 0, f"A1 is silently lost: {refuse.stdout}"
        assert "item_perdu_a_la_promotion" in refuse.stderr, refuse.stderr
        assert "A1" in refuse.stderr, refuse.stderr
        assert "A2" not in refuse.stderr, "A2 is DONE — it must never be accused"
        assert "git commit --no-verify" in refuse.stderr

        # The fix: A1 picked back up BY NAME in the successor plan.
        successeur.write_text(
            f"# PLAN — v2\n\n> **Cap** : v2\n> **Succède à** : {_EPREUVE}/archive/plan-v1.md\n\n"
            f"- **A1** \U00002B1C repris ici, tel quel.\n{_SIX_CHAMPS}"
            f"- **B1** \U00002B1C neuf.\n{_SIX_CHAMPS}",
            encoding="utf-8",
        )
        subprocess.run(["git", "-C", str(worktree), "add", f"{_EPREUVE}/PLAN.md"], check=True)
        accepte = subprocess.run(
            [str(hook)], cwd=worktree, capture_output=True, text=True, timeout=120, check=False
        )
        assert accepte.returncode == 0, f"A1 is picked back up — the promotion must pass: {accepte.stderr}"
    finally:
        subprocess.run(
            ["git", "worktree", "remove", "--force", str(worktree)],
            cwd=REPO_ROOT,
            check=False,
        )


def test_end_to_end_H4_un_predecesseur_ILLISIBLE_refuse_plutot_que_de_se_taire(
    tmp_path: Path,
) -> None:
    """A `**Succède à**` that cites a path absent from the INDEX must REFUSE, never pass in
    silence — filiation that cannot be verified is not filiation honored."""
    worktree = _worktree(tmp_path)
    try:
        hook = worktree / ".githooks" / "pre-commit"
        successeur = worktree / _EPREUVE / "PLAN.md"
        successeur.parent.mkdir(parents=True, exist_ok=True)
        successeur.write_text(
            f"# PLAN — v2\n\n> **Cap** : v2\n> **Succède à** : {_EPREUVE}/archive/introuvable.md\n\n"
            f"- **B1** \U00002B1C neuf.\n{_SIX_CHAMPS}",
            encoding="utf-8",
        )
        subprocess.run(["git", "-C", str(worktree), "add", f"{_EPREUVE}/PLAN.md"], check=True)
        refuse = subprocess.run(
            [str(hook)], cwd=worktree, capture_output=True, text=True, timeout=120, check=False
        )
        assert refuse.returncode != 0, f"an unfindable predecessor must refuse: {refuse.stdout}"
        assert "introuvable.md" in refuse.stderr, refuse.stderr
    finally:
        subprocess.run(
            ["git", "worktree", "remove", "--force", str(worktree)],
            cwd=REPO_ROOT,
            check=False,
        )


@pytest.fixture
def worktree(tmp_path: Path) -> Iterator[Path]:
    """A throwaway worktree off HEAD, always removed — the shape every end-to-end test below needs.

    Written as a fixture rather than copied into each test: a ``try/finally`` recopied eight times
    is eight chances to leave a worktree pinned in the real clone's ``.git/worktrees``.
    """
    tree = _worktree(tmp_path)
    try:
        yield tree
    finally:
        subprocess.run(
            ["git", "worktree", "remove", "--force", str(tree)], cwd=REPO_ROOT, check=False
        )


# ---------------------------------------------------------------------------------------------
# 4. ERASING is a way in — the class the `--diff-filter=ACM` filter could not see.
#
# Found by the isolated audit of C20-5, reproduced by hand before this suite existed: `git rm` on a
# staged arc put NOTHING in the hook's `plans` list, so the hook exited 0 and the door kept citing a
# file that no longer exists. `index_sans_fichier` — the refusal written for exactly that lie — was
# never evaluated. The tests below pin the CLASS, which is four different commits and not one:
# erasing an arc, erasing the LAST arc (where `folder_form` used to silently reopen the hole),
# erasing a whole plan (must PASS: nothing left to lie), erasing the door alone (must REFUSE: the
# arcs are stranded).
# ---------------------------------------------------------------------------------------------

#: Everything here lives under `projects/`, and that is the point: this repo's real plan root
#: carries a real `PLAN.md` at HEAD, so a worktree can never show that root WITHOUT a door — and
#: "the door is erased" is precisely half of this class. `projects/*` is gitignored (hence `_add`'s
#: `-f`) and holds exactly one tracked file, so nothing here can collide with the operator's own work.
_ERASE_ROOT = "projects/saas/demo"
_ERASE_DOOR = (
    "# PLAN — effacer\n\n> **Cap** : eprouver la voie effacer\n\n## Arcs\n\n"
    "- plan/arc-c.md — le lecteur\n"
    "- plan/arc-d.md — le second\n"
)
_ERASE_DOOR_ONE = (
    "# PLAN — effacer\n\n> **Cap** : eprouver la voie effacer\n\n## Arcs\n\n"
    "- plan/arc-c.md — le lecteur\n"
)


def _plant_two_arc_plan(tree: Path) -> None:
    """A COMMITTED folder plan: a door indexing two arcs, and the two arcs. The baseline to erase."""
    _write(tree, f"{_ERASE_ROOT}/PLAN.md", _ERASE_DOOR)
    _write(tree, f"{_ERASE_ROOT}/plan/arc-c.md", "# arc C\n\n- **C1** \U00002B1C un item\n")
    _write(tree, f"{_ERASE_ROOT}/plan/arc-d.md", "# arc D\n\n- **D1** \U00002B1C un item\n")
    _add(
        tree,
        f"{_ERASE_ROOT}/PLAN.md",
        f"{_ERASE_ROOT}/plan/arc-c.md",
        f"{_ERASE_ROOT}/plan/arc-d.md",
    )
    _commit_staged(tree, "un plan-dossier a effacer")


def test_end_to_end_CYCLE_une_dependance_circulaire_est_REFUSEE_puis_ACCEPTEE(
    tmp_path: Path,
) -> None:
    """`plan_ordre.ordonner()` already computes `PlanOrdre.ordonnable` (`not cycle`) -- a cycle
    already REFUSES, in the CALCULATION -- but nothing called that field as a refusal (found by
    an isolated audit, D75, reproduced before writing a line of this test: `make plans`/`make
    carte` PRINT the cycle and still exit 0). On the REAL HEREDOC, never a stand-in — same
    discipline as the `H4` tests right above."""
    worktree = _worktree(tmp_path)
    try:
        texte_cycle = (
            "# PLAN — cycle\n\n> **Cap** : cycle\n\n"
            "- **A1** \U00002B1C premier.\n"
            "  *Produit* : p\n  *Fini quand* : f\n  *Dépend de* : A2\n  *Prérequis* : AUCUN\n"
            "  *À lire* : a\n  *Taille* : t\n"
            "- **A2** \U00002B1C second.\n"
            "  *Produit* : p\n  *Fini quand* : f\n  *Dépend de* : A1\n  *Prérequis* : AUCUN\n"
            "  *À lire* : a\n  *Taille* : t\n"
        )
        _write(worktree, f"{_EPREUVE}/PLAN.md", texte_cycle)
        refuse = _commit_and_run(worktree, [f"{_EPREUVE}/PLAN.md"])
        assert refuse.returncode != 0, f"A1<->A2 is a real cycle: {refuse.stdout}"
        assert "cycle_de_dependances" in refuse.stderr, refuse.stderr
        assert "A1" in refuse.stderr and "A2" in refuse.stderr, refuse.stderr
        assert "git commit --no-verify" in refuse.stderr

        # The fix: A1 no longer depends on anything -- the cycle is broken, the line exists.
        texte_sain = texte_cycle.replace(
            "  *Dépend de* : A2\n", "  *Dépend de* : AUCUNE\n", 1
        )
        _write(worktree, f"{_EPREUVE}/PLAN.md", texte_sain)
        accepte = _commit_and_run(worktree, [f"{_EPREUVE}/PLAN.md"])
        assert accepte.returncode == 0, f"the cycle is broken -- must pass: {accepte.stderr}"
    finally:
        subprocess.run(
            ["git", "worktree", "remove", "--force", str(worktree)],
            cwd=REPO_ROOT,
            check=False,
        )


def test_end_to_end_CYCLE_un_plan_sain_REEL_du_depot_n_est_jamais_refuse(
    tmp_path: Path,
) -> None:
    """Negative control, on this repo's real plan -- not the fixture above: a door
    that refuses everything is not a door, it is a wall (explicit routing instruction)."""
    worktree = _worktree(tmp_path)
    try:
        porte = worktree / "docs" / "PLAN.md"
        texte = porte.read_text(encoding="utf-8")
        porte.write_text(texte + "\n", encoding="utf-8")
        resultat = _commit_and_run(worktree, ["docs/PLAN.md"])
        assert resultat.returncode == 0, (
            f"this repo's real plan is HEALTHY -- it must never be refused by the "
            f"cycle door: {resultat.stderr}"
        )
        assert "cycle_de_dependances" not in resultat.stderr, resultat.stderr
    finally:
        subprocess.run(
            ["git", "worktree", "remove", "--force", str(worktree)],
            cwd=REPO_ROOT,
            check=False,
        )


def test_end_to_end_D176_le_VRAI_plan_de_Mnemosyne_est_INCHANGE_par_la_declaration(
    tmp_path: Path,
) -> None:
    """MANDATORY NEGATIVE CONTROL for D176 routing: `champs_requis_pour` now reads a
    declaration (`**Format** :`) to open adoption to a project that is not Mnemosyne -- Mnemosyne's
    OWN floor, though, stays UNCONDITIONAL (see its docstring). This witness measures it on
    the REAL repo rather than assuming it: the root door + a real arc, unchanged, commit
    -- then a real item's first required field, emptied, refuses -- exactly as before this
    routing. Both edges, on the same bytes."""
    worktree = _worktree(tmp_path)
    try:
        sain = _commit_and_run(worktree, ["docs/PLAN.md", "docs/plan/00-le-socle-du-plan.md"])
        assert sain.returncode == 0, (
            f"Mnemosyne's real plan, unchanged, must always pass: {sain.stderr}"
        )

        import re as _re

        arc = worktree / "docs" / "plan" / "00-le-socle-du-plan.md"
        texte = arc.read_text(encoding="utf-8")
        vide, n = _re.subn(r"^(\s*\*Produit\*\s*:).*$", r"\1", texte, count=1, flags=_re.MULTILINE)
        assert n == 1, "no `*Produit* :` line found -- the file's shape has changed"
        arc.write_text(vide, encoding="utf-8")

        mutile = _commit_and_run(worktree, ["docs/plan/00-le-socle-du-plan.md"])
        assert mutile.returncode != 0, "a mutilated item of the REAL plan must always be refused"
        assert "champ_requis_manquant" in mutile.stderr, mutile.stderr
        assert "Produit" in mutile.stderr, mutile.stderr
    finally:
        subprocess.run(
            ["git", "worktree", "remove", "--force", str(worktree)],
            cwd=REPO_ROOT,
            check=False,
        )


def test_end_to_end_D176_un_projet_HORS_Mnemosyne_peut_ADOPTER_un_sous_ensemble(
    tmp_path: Path,
) -> None:
    """The gesture D176 opens: a door outside this repo's own plan root could not ADOPT any field,
    no matter what it wrote -- `champs_requis_pour` returned `()` unconditionally. Here, on the real
    hook, an `epreuve/` door that declares `**Format** : produit` is held to THIS ONE field:
    empty, it refuses; filled in, it passes -- without ever demanding the other five."""
    worktree = _worktree(tmp_path)
    try:
        tete = (
            "# PLAN — demo hors Mnemosyne\n\n"
            "> **Cap** : prouver l'adoption partielle\n"
            "> **Format** : produit\n\n"
        )
        item_vide = tete + "- **A1** \U00002B1C t.\n  *Produit* :\n"
        _write(worktree, f"{_EPREUVE}/PLAN.md", item_vide)
        refuse = _commit_and_run(worktree, [f"{_EPREUVE}/PLAN.md"])
        assert refuse.returncode != 0, "declares produit -- empty, must refuse"
        assert "champ_requis_manquant" in refuse.stderr, refuse.stderr
        assert "Produit" in refuse.stderr, refuse.stderr
        assert "Fini quand" not in refuse.stderr, "never more than what is declared"

        item_rempli = tete + "- **A1** \U00002B1C t.\n  *Produit* : p\n"
        _write(worktree, f"{_EPREUVE}/PLAN.md", item_rempli)
        accepte = _commit_and_run(worktree, [f"{_EPREUVE}/PLAN.md"])
        assert accepte.returncode == 0, f"declared and filled in -- must pass: {accepte.stderr}"
    finally:
        subprocess.run(
            ["git", "worktree", "remove", "--force", str(worktree)],
            cwd=REPO_ROOT,
            check=False,
        )


@pytest.mark.parametrize(
    ("erased", "orphaned_entries"),
    [
        # One arc of two. The door still names it; the file is gone from the index.
        (["plan/arc-d.md"], ["plan/arc-d.md"]),
        # BOTH arcs — the sub-case that reopened the hole on its own worst commit. Erasing the LAST
        # arc empties `<folder>/plan/` from the index, so `folder_form` (computed from the index
        # alone) fell back to False and SUPPRESSED `index_sans_fichier`, by the clause written for
        # single-file plans. The door is then left citing two files that do not exist, silently.
        (["plan/arc-c.md", "plan/arc-d.md"], ["plan/arc-c.md", "plan/arc-d.md"]),
    ],
)
def test_ERASING_an_arc_the_door_still_indexes_is_REFUSED(
    worktree: Path, erased: list[str], orphaned_entries: list[str]
) -> None:
    """``git rm`` of an indexed arc must refuse — the door would keep pointing at nothing."""
    _plant_two_arc_plan(worktree)
    _erase(worktree, *(f"{_ERASE_ROOT}/{rel}" for rel in erased))
    done = _run_real(worktree)
    assert done.returncode != 0, (
        f"erasing {erased} left the door citing a file that no longer exists, and the barrier "
        f"exited 0: {done.stdout}{done.stderr}"
    )
    assert "index_sans_fichier" in done.stderr, done.stderr
    for entry in orphaned_entries:
        assert entry in done.stderr, (entry, done.stderr)


def test_ERASING_the_DOOR_alone_strands_its_arcs_and_is_REFUSED(worktree: Path) -> None:
    """The symmetric lie: the arcs survive in the index and now belong to no plan at all.

    This is also the ONLY input that reaches ``judge``'s own "aucune porte" refusal — every other
    path into ``judge`` comes from ``owning_plan``, which by construction found a door. A refusal no
    input can reach is a promise nobody keeps, so it is reached here, by name.
    """
    _plant_two_arc_plan(worktree)
    _erase(worktree, f"{_ERASE_ROOT}/PLAN.md")
    done = _run_real(worktree)
    assert done.returncode != 0, (
        f"the door was erased and two arcs stayed in the index, judged by nothing: "
        f"{done.stdout}{done.stderr}"
    )
    assert "un arc sans porte n'appartient a aucun plan" in done.stderr, done.stderr
    assert f"{_ERASE_ROOT}/PLAN.md" in done.stderr, done.stderr


@pytest.mark.parametrize("erase_the_door", [True, False])
def test_ERASING_leaves_no_friction_when_nothing_is_left_to_lie(
    worktree: Path, erase_the_door: bool
) -> None:
    """The other half of the class, and the one a catch-rate alone would never show.

    Two commits that erase and are perfectly honest: dropping a WHOLE plan (door and arcs in the
    same commit — nothing survives that could point at nothing), and dropping an arc TOGETHER with
    its index entry. A barrier that refused these would be met by everyone who ever retires a plan,
    and a barrier people meet when they are right is a barrier people uninstall.
    """
    _plant_two_arc_plan(worktree)
    if erase_the_door:
        _erase(
            worktree,
            f"{_ERASE_ROOT}/PLAN.md",
            f"{_ERASE_ROOT}/plan/arc-c.md",
            f"{_ERASE_ROOT}/plan/arc-d.md",
        )
    else:
        _erase(worktree, f"{_ERASE_ROOT}/plan/arc-d.md")
        _write(worktree, f"{_ERASE_ROOT}/PLAN.md", _ERASE_DOOR_ONE)
        _add(worktree, f"{_ERASE_ROOT}/PLAN.md")
    done = _run_real(worktree)
    assert done.returncode == 0, f"an honest erasure must pass: {done.stdout}{done.stderr}"


@pytest.mark.parametrize(
    "relative",
    [
        "docs/plan/arc-c.md",
        "docs/PLAN.md",
        "projects/saas/Acme Research/PLAN.md",
        "projects/saas/Acme Research/plan/arc-c.md",
    ],
)
def test_the_shell_layer_SEES_an_ERASED_plan_path(tmp_path: Path, relative: str) -> None:
    """The filter itself, without any Python environment: a DELETED plan path must reach the judge.

    Split from the end-to-end tests on purpose — this is the one question the ``--diff-filter=ACM``
    answered wrongly, and answering it needs neither a reader nor a plan that means anything. With
    ``ACM``, ``plans`` stayed empty and ``uv`` was never spawned; the log file below is the proof.
    """
    _init_repo(tmp_path)
    _stage(tmp_path, relative, "# PLAN — x\n")
    _commit_staged(tmp_path, "base")
    subprocess.run(["git", "-C", str(tmp_path), "rm", "-q", "--", relative], check=True)
    fakebin, log = _fake_uv(tmp_path, exit_code=1)
    done = _run_hook(tmp_path, fakebin=fakebin, log=log, judge_exit=1)
    assert log.exists(), f"the judge was never invoked for the ERASED plan path {relative!r}"
    assert done.returncode == 1, (
        f"the hook must forward the judge's verdict on an erasure too: {done.stderr!r}"
    )


# ---------------------------------------------------------------------------------------------
# 5. The four rules that SURVIVED their own sabotage (C20-5). Each one below is the witness that
#    kills one of them; without these, the hook could stop reading the index, stop refusing an
#    orphan arc, or print an empty refusal, and the whole suite stayed green.
# ---------------------------------------------------------------------------------------------

_GOOD_PLAN = "# PLAN — x\n\n> **Cap** : y\n\n- **A1** \U00002B1C un item\n"
_BAD_PLAN = _GOOD_PLAN.replace("\U00002B1C", "\U00002753")


@pytest.mark.parametrize(
    ("indexed", "on_disk", "must_refuse"),
    [
        (_BAD_PLAN, _GOOD_PLAN, True),
        (_GOOD_PLAN, _BAD_PLAN, False),
    ],
)
def test_the_hook_judges_the_INDEX_and_NEVER_the_working_tree(
    worktree: Path, indexed: str, on_disk: str, must_refuse: bool
) -> None:
    """``git show :<path>`` and not ``cat <path>`` — the hook's own comment calls this "PIEGE EVITE".

    It was a comment and nothing else: replacing ``index_text`` with a read of the file on disk
    turned NO test red. The witness is a PARTIAL STAGING, which is the only state where the two
    disagree, and it needs both directions — one alone is satisfiable by a hook that always refuses
    or always accepts.

    Direction 1 (index bad, disk good) is what a commit actually is: git will commit the INDEX, so
    a hook blessing the working tree blesses bytes nobody is about to commit. Direction 2 (index
    good, disk bad) is the false accusation that would follow — refusing a perfectly good commit
    because of an edit still in progress on disk is friction on the most ordinary way of working.
    """
    _write(worktree, f"{_EPREUVE}/PLAN.md", indexed)
    _add(worktree, f"{_EPREUVE}/PLAN.md")
    _write(worktree, f"{_EPREUVE}/PLAN.md", on_disk)  # diverge AFTER staging, never before
    done = _run_real(worktree)
    assert (done.returncode != 0) is must_refuse, (
        "the hook judged the working tree instead of the index (staged bytes "
        f"{'ILLISIBLE' if must_refuse else 'LISIBLE'}, disk the opposite, exit "
        f"{done.returncode}): {done.stdout}{done.stderr}"
    )


def test_an_ARC_that_NO_door_anywhere_claims_is_REFUSED(worktree: Path) -> None:
    """An arc under a ``plan/`` with no door above it — judged by nothing unless it is refused here.

    Replacing that refusal with ``pass`` turned no test red. Planted under ``projects/`` and not
    this repo's own plan root, and that is forced rather than chosen: this repo's real plan door
    exists at HEAD, so in any worktree anything nested beneath that root HAS a door above it and the
    fixture would prove the opposite of what it claims — silently green.
    """
    _write(worktree, f"{_ERASE_ROOT}/plan/arc-x.md", "# arc X\n\n- **X1** \U00002B1C un item\n")
    _add(worktree, f"{_ERASE_ROOT}/plan/arc-x.md")
    done = _run_real(worktree)
    assert done.returncode != 0, (
        f"an orphan arc was staged and the barrier exited 0: {done.stdout}{done.stderr}"
    )
    assert "aucune porte au-dessus de ce fichier" in done.stderr, done.stderr
    assert f"{_ERASE_ROOT}/plan/arc-x.md" in done.stderr, done.stderr


#: The refusal report, character for character. Both lines it contains were deletable with NO test
#: turning red: the summary line (`[pre-commit] …`) and the per-plan line (`  <path> -- etat : …`).
#: An `in` check on either would have kept passing while the other vanished, so the whole block is
#: compared at once.
_EXACT_DOOR = (
    "# PLAN — demo\n\n> **Cap** : prouver la forme\n\n## Arcs\n\n- plan/arc-c.md — le lecteur\n"
)
_EXACT_ARC = "# arc C\n\n- **C1** \U00002B1C un item\n- **C2** \U00002753 un autre\n"
_EXACT_REPORT = (
    "[pre-commit] plan illisible mis en scene -- commit refuse.\n"
    "\n"
    f"  {_EPREUVE}/PLAN.md -- etat : illisible\n"
    "    plan/arc-c.md ligne 4 : statut_inconnu -- C2 → '\U00002753 un autre'\n"
    "\n"
    "Urgence (a n'utiliser qu'en cas de reel besoin) : git commit --no-verify\n"
)


def _describe_refusal(done: subprocess.CompletedProcess[str]) -> str:
    """The hook's own words, from its summary line on — ``uv``'s venv preamble stripped."""
    marker = "[pre-commit] "
    return done.stderr[done.stderr.index(marker) :] if marker in done.stderr else done.stderr


def test_the_refusal_REPORT_is_EXACTLY_these_lines(worktree: Path) -> None:
    """Every line the human is shown, compared whole — not a substring, which is what let two go.

    The fixture is built so the report has exactly ONE cause: the arc carries a valid item (so the
    plan is not ALSO refused for having none) and a second one whose glyph is unknown, and the door
    indexes the arc as a BULLET (so no ``arc_hors_index`` / ``index_sans_fichier`` joins in). Any
    line added, removed or reworded fails here, which is the price of pinning an exact string and
    is the point: these two lines are the entire user interface of the barrier.

    ``uv`` writes its own preamble on this same stderr the first time it builds the worktree's venv
    (``Using CPython…``, ``Installed 7 packages…``), which is not the hook's output and not stable.
    The comparison therefore starts at the marker — and if the marker itself is deleted, there is
    nothing to start at and this fails first.
    """
    _write(worktree, f"{_EPREUVE}/PLAN.md", _EXACT_DOOR)
    _write(worktree, f"{_EPREUVE}/plan/arc-c.md", _EXACT_ARC)
    done = _commit_and_run(worktree, [f"{_EPREUVE}/PLAN.md", f"{_EPREUVE}/plan/arc-c.md"])
    assert done.returncode != 0, f"this plan must be refused: {done.stdout}{done.stderr}"
    marker = "[pre-commit] "
    assert marker in done.stderr, (
        f"the refusal printed no summary line at all — a barrier that refuses without saying so is "
        f"a barrier nobody can act on: {done.stderr!r}"
    )
    assert done.stderr[done.stderr.index(marker) :] == _EXACT_REPORT, done.stderr


# ---------------------------------------------------------------------------------------------
# 6. RENAMING is the same way in — and the CLASS is neither ``D`` nor ``R``, it is JUDGING THE
#    GESTURE INSTEAD OF THE RESULTING STATE.
#
# Measured 2026-07-29 (git 2.53.0, ``diff.renames`` unset — hence TRUE by default since git 2.9),
# after ``git mv plan/arc-c.md plan/arc-d.md``::
#
#     git diff --cached --name-only --diff-filter=ACMD  ->  (EMPTY)
#     git diff --cached --name-only                     ->  plan/arc-d.md  (destination ONLY)
#     git diff --cached --name-status                   ->  R100  arc-c.md  arc-d.md
#     git diff --cached --name-only --no-renames        ->  arc-c.md AND arc-d.md
#
# Consequence, proven with real commits in a throwaway clone: ``git rm`` of an arc the door still
# cites -> exit 1, HEAD frozen; ``git mv`` of the SAME arc -> exit 0, HEAD moves, and the door now
# cites a file that does not exist. Same resulting state, two gestures, two verdicts.
#
# Closing ``R`` the way ``D`` was closed would have been closing the CASE. The class is that a
# filter over diff STATUSES always forgets one more status (``R``, ``C``, ``T``, and whatever git
# adds next). So the question the hook asks no longer mentions any status: EVERY staged path comes
# down (no ``--diff-filter``), a rename is un-paired into a deletion plus an addition
# (``--no-renames``) so BOTH paths are judged, and "erased" is read off the RESULTING INDEX
# (``git ls-files``, already read) rather than off a ``--diff-filter=D``.
#
# ``test_the_verdict_does_not_depend_on_whether_git_PAIRS_the_two_paths`` below is the one that
# defends the CLASS rather than these four cases: it runs the SAME staged state twice, once with
# ``diff.renames=true`` and once with ``false``, and demands the two refusals be identical
# character for character. Any filter over statuses makes them diverge.
# ---------------------------------------------------------------------------------------------

_MOVE_ROOT2 = "projects/saas/demo2"


def _move(worktree: Path, source: str, destination: str) -> None:
    """``git mv`` — the exact gesture that walked through the barrier, not a re-staged imitation."""
    (worktree / destination).parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "-C", str(worktree), "mv", "--", source, destination], check=True)


def _staged_status(worktree: Path, *, env: dict[str, str] | None = None) -> str:
    return subprocess.run(
        ["git", "-C", str(worktree), "diff", "--cached", "--name-status"],
        capture_output=True,
        text=True,
        check=True,
        env=env,
    ).stdout


def _renames(setting: str) -> dict[str, str]:
    """An environment that forces ``diff.renames`` for git AND for everything git spawns.

    NOT ``git config``: a worktree shares ``.git/config`` with the clone it hangs off, so writing
    the setting there leaks out of the test — measured, it survived the run, poisoned every later
    fixture's rename detection, and reached the real repo's own config. ``GIT_CONFIG_COUNT`` (git
    ≥ 2.31) applies to the process and its children — which is what the hook is — and dies with it.
    """
    return {
        **os.environ,
        "GIT_CONFIG_COUNT": "1",
        "GIT_CONFIG_KEY_0": "diff.renames",
        "GIT_CONFIG_VALUE_0": setting,
    }


def _assert_git_PAIRED_them(worktree: Path) -> None:
    """The fixture self-check without which every test in this section can go green proving NOTHING.

    A rename only escapes ``--diff-filter=ACMD`` when git PAIRS the two paths into one ``R`` entry,
    and git only pairs them above a similarity threshold. Change an arc fixture enough and the same
    ``git mv`` stages a plain ``D`` + ``A`` — which the OLD filter already caught. The test would
    then pass against the very code it exists to kill. So the shape is asserted, not assumed.
    """
    status = _staged_status(worktree)
    assert any(line.startswith("R") for line in status.splitlines()), (
        "this fixture stages no rename git PAIRS (no R status), so it cannot bite a status filter:\n"
        f"{status}"
    )


def test_RENAMING_an_arc_the_door_still_indexes_is_REFUSED(worktree: Path) -> None:
    """Scenario 1. The door keeps citing ``plan/arc-d.md``; the file is now ``plan/arc-e.md``."""
    _plant_two_arc_plan(worktree)
    _move(worktree, f"{_ERASE_ROOT}/plan/arc-d.md", f"{_ERASE_ROOT}/plan/arc-e.md")
    _assert_git_PAIRED_them(worktree)
    done = _run_real(worktree)
    assert done.returncode != 0, f"a renamed arc walked through: {done.stdout}{done.stderr}"
    assert "index_sans_fichier" in done.stderr and "plan/arc-d.md" in done.stderr, done.stderr
    assert "arc_hors_index" in done.stderr and "plan/arc-e.md" in done.stderr, done.stderr


def test_RENAMING_the_DOOR_makes_it_EVAPORATE_and_is_REFUSED(worktree: Path) -> None:
    """Scenario 2. The nastiest of the four: the door leaves under a name no pattern matches, so
    NOTHING is left to notice that two arcs now belong to no plan. The destination is invisible to
    the hook by design — only the vanished SOURCE can raise the alarm, and only if it comes down."""
    _plant_two_arc_plan(worktree)
    _move(worktree, f"{_ERASE_ROOT}/PLAN.md", f"{_ERASE_ROOT}/PLAN_ARCHIVE.md")
    _assert_git_PAIRED_them(worktree)
    done = _run_real(worktree)
    assert done.returncode != 0, f"the door evaporated silently: {done.stdout}{done.stderr}"
    assert "un arc sans porte n'appartient a aucun plan" in done.stderr, done.stderr


def test_RENAMING_any_file_INTO_a_plan_folder_is_REFUSED(worktree: Path) -> None:
    """Scenario 3. Nothing about the source is plan-shaped; the DESTINATION makes it an arc, and an
    arc no door indexes. Under the old filter the paired rename showed neither path."""
    _plant_two_arc_plan(worktree)
    _write(worktree, f"{_ERASE_ROOT}/notes.md", "# notes\n\ndes notes libres, hors de tout plan.\n")
    _add(worktree, f"{_ERASE_ROOT}/notes.md")
    _commit_staged(worktree, "un fichier quelconque, hors plan")
    _move(worktree, f"{_ERASE_ROOT}/notes.md", f"{_ERASE_ROOT}/plan/arc-e.md")
    _assert_git_PAIRED_them(worktree)
    done = _run_real(worktree)
    assert done.returncode != 0, f"a file walked INTO plan/ unnoticed: {done.stdout}{done.stderr}"
    assert "arc_hors_index" in done.stderr and "plan/arc-e.md" in done.stderr, done.stderr


def test_MOVING_an_arc_from_one_plan_to_ANOTHER_makes_BOTH_doors_lie_and_is_REFUSED(
    worktree: Path,
) -> None:
    """Scenario 4, and the reason the unit judged is the PLAN and not the file: one staged path,
    TWO plans wrong, and each is wrong in its own direction. Both must be named."""
    _plant_two_arc_plan(worktree)
    _write(
        worktree,
        f"{_MOVE_ROOT2}/PLAN.md",
        "# PLAN — second\n\n> **Cap** : le plan voisin\n\n## Arcs\n\n- plan/arc-z.md — le sien\n",
    )
    _write(worktree, f"{_MOVE_ROOT2}/plan/arc-z.md", "# arc Z\n\n- **Z1** \U00002B1C un item\n")
    _add(worktree, f"{_MOVE_ROOT2}/PLAN.md", f"{_MOVE_ROOT2}/plan/arc-z.md")
    _commit_staged(worktree, "un second plan, voisin du premier")
    _move(worktree, f"{_ERASE_ROOT}/plan/arc-d.md", f"{_MOVE_ROOT2}/plan/arc-d.md")
    _assert_git_PAIRED_them(worktree)
    done = _run_real(worktree)
    assert done.returncode != 0, f"an arc changed plan silently: {done.stdout}{done.stderr}"
    assert f"{_ERASE_ROOT}/PLAN.md" in done.stderr, done.stderr
    assert f"{_MOVE_ROOT2}/PLAN.md" in done.stderr, done.stderr
    assert "index_sans_fichier" in done.stderr, done.stderr
    assert "arc_hors_index" in done.stderr, done.stderr


def test_a_LEGITIMATE_rename_PASSES_when_the_index_moves_in_the_SAME_commit(worktree: Path) -> None:
    """The counterweight, without which the four tests above are a WALL and not a floor.

    A catch rate with no false-kill rate says nothing: refusing every ``git mv`` would score 4/4
    above and be uninstalled the first time anyone tidies a plan. Renaming an arc AND updating the
    door's index in the same commit is the CORRECT way to do it, it is what the barrier is asking
    for, and it must cost nothing.
    """
    _plant_two_arc_plan(worktree)
    _move(worktree, f"{_ERASE_ROOT}/plan/arc-d.md", f"{_ERASE_ROOT}/plan/arc-e.md")
    _write(
        worktree,
        f"{_ERASE_ROOT}/PLAN.md",
        _ERASE_DOOR.replace("- plan/arc-d.md — le second\n", "- plan/arc-e.md — le second, renomme\n"),
    )
    _add(worktree, f"{_ERASE_ROOT}/PLAN.md")
    _assert_git_PAIRED_them(worktree)
    done = _run_real(worktree)
    assert done.returncode == 0, (
        f"an honest rename was refused — this is the false accusation that gets a barrier "
        f"uninstalled: {done.stdout}{done.stderr}"
    )


def test_MOVING_a_WHOLE_plan_PASSES_because_nothing_is_left_to_lie(worktree: Path) -> None:
    """The door and its arcs move together: the index entries are RELATIVE to the folder, so the
    plan is exactly as true at its new address as at its old one, and the old address holds nothing
    at all. Symmetric with erasing a whole plan, and it lands on the same tie-break: the refusal for
    a vanished door only fires when arcs are LEFT BEHIND in the resulting index.

    Stated rather than discovered: this is what a plan being re-homed looks like, and a barrier that
    refused it would be met by everyone who ever reorganises ``projects/``.
    """
    _plant_two_arc_plan(worktree)
    _move(worktree, _ERASE_ROOT, _MOVE_ROOT2)
    _assert_git_PAIRED_them(worktree)
    done = _run_real(worktree)
    assert done.returncode == 0, (
        f"re-homing a whole plan must pass — nothing survives that could point at nothing: "
        f"{done.stdout}{done.stderr}"
    )


@pytest.mark.parametrize("renames", ["true", "false"])
def test_the_verdict_does_not_depend_on_whether_git_PAIRS_the_two_paths(
    worktree: Path, renames: str
) -> None:
    """THE CLASS, defended without naming a single status. Same staged state, two diff engines.

    ``diff.renames`` decides whether git reports one ``R`` line or a ``D`` line plus an ``A`` line
    for the very same index. Nothing about the commit changes — only how git chooses to DESCRIBE it.
    A barrier that reads the resulting state cannot notice the difference; a barrier that filters on
    statuses answers ``exit 0`` on one and ``exit 1`` on the other, which is exactly the defect that
    shipped. The refusal is therefore pinned character for character, ONE expected text for both
    settings, so any filter over statuses turns this red on the ``true`` half.

    THE FIXTURE IS THE DOOR, and that is measured rather than chosen. Renaming an ARC is also caught
    by the destination path alone (``plan/arc-e.md`` is plan-shaped), so dropping ``--no-renames``
    while dropping the filter leaves that case green — it discriminates nothing. Renaming the DOOR
    puts the destination OUTSIDE every pattern: the vanished SOURCE is the only witness there is, so
    this fixture reddens both halves of the rule, the missing filter and the missing un-pairing.

    ``diff.renames`` is left UNSET in this repo, so ``true`` is the setting that really runs.
    """
    env = _renames(renames)
    _plant_two_arc_plan(worktree)
    _move(worktree, f"{_ERASE_ROOT}/PLAN.md", f"{_ERASE_ROOT}/PLAN_ARCHIVE.md")
    paired = any(line.startswith("R") for line in _staged_status(worktree, env=env).splitlines())
    assert paired is (renames == "true"), (
        f"the fixture did not exercise the two descriptions of the same state (diff.renames="
        f"{renames}, paired={paired}):\n{_staged_status(worktree, env=env)}"
    )
    done = _run_real(worktree, env=env)
    assert _describe_refusal(done) == (
        "[pre-commit] plan illisible mis en scene -- commit refuse.\n"
        "\n"
        f"  {_ERASE_ROOT}/PLAN.md -- etat : illisible\n"
        "    ligne -   : aucune porte (`PLAN.md` / `PLAN_COURANT.md`) dans "
        f"`{_ERASE_ROOT}` -- un arc sans porte n'appartient a aucun plan\n"
        "\n"
        "Urgence (a n'utiliser qu'en cas de reel besoin) : git commit --no-verify\n"
    ), done.stderr
    assert done.returncode != 0, done.stderr


#: A ``git`` that refuses exactly the call the hook uses to read the resulting index, and forwards
#: every other one to the real binary. Not a blanket failure: the hook shells out to git before the
#: judge ever starts, and ``uv`` builds the package in between.
#: THE SHIM MATCHED THE FLAGS, AND THE FLAGS MOVED. It used to test ``"$1 $2" = "ls-files -z"``,
#: so the day the hook started asking for modes as well (``git ls-files -s -z``, the one call that
#: now also answers "is this arc a symlink?") the shim stopped matching, the real ``git`` answered,
#: and this test went GREEN while proving nothing at all. A harness pinned to an argument LIST is a
#: harness that stops biting on the first flag anybody adds. It now matches the SUBCOMMAND, which is
#: the thing this test is actually about — every ``ls-files``, whatever it is asked for.
_FAKE_GIT = """#!/bin/sh
if [ "$1" = "ls-files" ]; then exit 128; fi
exec {real} "$@"
"""


def test_an_UNREADABLE_index_REFUSES_instead_of_reporting_a_clean_plan(worktree: Path) -> None:
    """The hole the state formulation could have dug, closed where it is dug.

    Since "erased" MEANS "absent from ``git ls-files``", an EMPTY answer from ``git ls-files`` reads
    as "every staged path was erased" — and an erased path no door claims is skipped by construction.
    A single failed call would therefore have turned the whole barrier into ``exit 0``, silently, on
    a plan that lies. ``indexed_tree`` used to ``return ()`` there, which was harmless only while the
    deleted list came from its own ``git diff``. It now exits 1 and says so.
    """
    real_git = shutil.which("git")
    assert real_git, "git must be on PATH for this test to shim it"
    fakebin = worktree.parent / "fakegit"
    fakebin.mkdir(exist_ok=True)
    (fakebin / "git").write_text(_FAKE_GIT.format(real=real_git), encoding="utf-8")
    (fakebin / "git").chmod(0o755)

    _write(worktree, f"{_EPREUVE}/PLAN.md", _DOOR)
    _write(worktree, f"{_EPREUVE}/plan/arc-c.md", _ARC)
    subprocess.run(
        ["git", "-C", str(worktree), "add", "--", f"{_EPREUVE}/PLAN.md", f"{_EPREUVE}/plan/arc-c.md"],
        check=True,
    )
    done = _run_real(worktree, env={**os.environ, "PATH": f"{fakebin}:{os.environ['PATH']}"})
    assert done.returncode != 0, (
        f"the resulting index could not be read and the barrier blessed the commit anyway: "
        f"{done.stdout}{done.stderr}"
    )
    assert "ls-files" in done.stderr, done.stderr


def test_a_NON_MARKDOWN_file_leaving_plan_still_says_the_plan_WAS_a_folder(worktree: Path) -> None:
    """The domain the shape filter does not cover, and the reason the judge gets EVERY staged path.

    ``folder_form`` asks about ``<folder>/plan/`` — a DIRECTORY — and not about a file name. Its
    second half ("did one exist BEFORE this commit?") reads the erased paths, and the only erasures
    that half needs are the ones the plan-shaped patterns THROW AWAY: a ``.txt``, an image, anything
    that is not an arc. Here ``plan/`` holds one such file and nothing else, so erasing it empties
    the directory from the resulting index; if that erasure did not come down, ``folder_form`` falls
    back to False and ``index_sans_fichier`` — the door citing an arc that does not exist — is
    suppressed by the clause written for single-file plans. Restricting the list to plan-shaped
    paths would look like a harmless tidy-up and would re-open the hole on this exact commit.
    """
    _write(worktree, f"{_ERASE_ROOT}/PLAN.md", _ERASE_DOOR_ONE)
    _write(worktree, f"{_ERASE_ROOT}/plan/notes.txt", "des notes, pas un arc\n")
    _add(worktree, f"{_ERASE_ROOT}/PLAN.md", f"{_ERASE_ROOT}/plan/notes.txt")
    _commit_staged(worktree, "un plan-dossier dont le dossier ne porte pas d'arc")

    _erase(worktree, f"{_ERASE_ROOT}/plan/notes.txt")
    _write(worktree, f"{_ERASE_ROOT}/PLAN.md", _ERASE_DOOR_ONE + "\n(une retouche quelconque)\n")
    _add(worktree, f"{_ERASE_ROOT}/PLAN.md")
    assert not any(
        p.startswith(f"{_ERASE_ROOT}/plan/")
        for p in subprocess.run(
            ["git", "-C", str(worktree), "ls-files", "-z"], capture_output=True, text=True, check=True
        ).stdout.split("\0")
    ), "the fixture must leave plan/ EMPTY in the resulting index, or folder_form is true anyway"
    done = _run_real(worktree)
    assert done.returncode != 0, (
        f"plan/ emptied of its last file and the door still cites an arc — accepted: "
        f"{done.stdout}{done.stderr}"
    )
    assert "index_sans_fichier" in done.stderr and "plan/arc-c.md" in done.stderr, done.stderr


# ---------------------------------------------------------------------------------------------
# 8. BIRTH — a SCAFFOLDED plan passes the barrier on the FIRST TRY (D166 · C20-13).
#
# The arc's mechanical criterion, and it is only valid END TO END: `make plan-nouveau APPLY=1`,
# then the REAL heredoc, in a throwaway worktree, on the real index. The unit tests in
# `tests/orchestration/test_plan_scaffold.py` ask the READER what it thinks of the bytes; here
# we ask the BARRIER what it does with the commit — these are not the same question, and it is
# the second one the operator pays for when they commit.
#
# The new modules are copied from the WORKING TREE, exactly like `_HOOK_DEPENDENCY`:
# a `git worktree` only shows COMMITTED objects, so without this we would be testing yesterday's
# scaffolding against today's hook — or worse, we would be green on a rule that does not ship.
# ---------------------------------------------------------------------------------------------

def _with_scaffold(worktree: Path) -> Path:
    """The worktree already carries the working tree's library — `_overlay_library` put it there.

    Kept as a NAME, no longer as a LIST: the scaffold's module list was the second hand-kept
    inventory in this file, and it forgot a module the day the birth command started calling
    the barrier's own walk. See `_LIB`.
    """
    return _overlay_library(worktree)


def _naitre(worktree: Path, chemin: str, *args: str) -> subprocess.CompletedProcess[str]:
    """`make plan-nouveau … APPLY=1`, through the module the Makefile target launches, in the worktree.

    THE FLOOR IS ASSERTED **BEFORE** THE VERDICT IT PROTECTS, and this is not ceremony:
    found by SABOTAGE, never by a green run. These tests are born at an address in the worktree,
    and the worktree comes off HEAD — so the day someone commits a plan at that address, the
    command answers `plan_existe` (rightly: it never overwrites) and the test goes red accusing
    the MECHANISM. This is exactly the class section 5bis of this file already paid for: a
    harness valid only for as long as nobody uses what it guards. Here the occupied address is
    named for what it is — a FIXTURE defect — instead of being read as a defect of the barrier.
    """
    assert not (worktree / chemin).exists(), (
        f"« {chemin} » already exists in the worktree (so in HEAD): the FIXTURE is stale, "
        "it is not the scaffolding that failed. Choose a free address."
    )
    return subprocess.run(
        ["uv", "run", "python", "-m", "mnemosyne.runtime.plan_new_run", chemin, "--apply", *args],
        cwd=worktree,
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
        env={**os.environ, "PYTHONPATH": "system/lib"},
    )


def test_end_to_end_un_plan_ECHAFAUDE_passe_la_barriere_du_PREMIER_coup(worktree: Path) -> None:
    """The mandate's criterion. Birth, staging, REAL hook: `exit 0`, no conversion."""
    _with_scaffold(worktree)
    ne = _naitre(worktree, f"{_EPREUVE}/naissance", "--cap", "prouver la naissance")
    assert ne.returncode == 0, f"{ne.stdout}{ne.stderr}"
    porte = worktree / _EPREUVE / "naissance" / "PLAN.md"
    arc = worktree / _EPREUVE / "naissance" / ARCS_DIRNAME / "socle.md"
    assert porte.is_file() and arc.is_file(), ne.stdout

    _add(worktree, f"{_EPREUVE}/naissance/PLAN.md", f"{_EPREUVE}/naissance/{ARCS_DIRNAME}/socle.md")
    done = _run_real(worktree)
    assert done.returncode == 0, (
        "a plan BORN conformant is refused by the barrier — the ability to create is worthless: "
        f"{done.stdout}{done.stderr}"
    )


def test_end_to_end_la_barriere_REFUSE_toujours_un_plan_ECRIT_A_LA_MAIN_qui_ment(worktree: Path) -> None:
    """The counterpart, without which the first proves nothing: the barrier was not disarmed
    along the way.

    Same folder, same commit as the birth: the ONLY thing that changes is that the arc was
    written by hand without being indexed. If this test went green, "the scaffolded plan passes"
    would say nothing anymore — a control that accepts everything has a perfect false-accusation
    rate.
    """
    _with_scaffold(worktree)
    assert _naitre(worktree, f"{_EPREUVE}/pendant").returncode == 0
    _write(worktree, f"{_EPREUVE}/pendant/{ARCS_DIRNAME}/orphelin.md", "# orphelin\n\n- **Z9** \U00002B1C jamais indexé\n")
    _add(
        worktree,
        f"{_EPREUVE}/pendant/PLAN.md",
        f"{_EPREUVE}/pendant/{ARCS_DIRNAME}/socle.md",
        f"{_EPREUVE}/pendant/{ARCS_DIRNAME}/orphelin.md",
    )
    done = _run_real(worktree)
    assert done.returncode != 0, f"an arc the door names nowhere is accepted: {done.stdout}"
    assert "arc_hors_index" in done.stderr and "orphelin.md" in done.stderr, done.stderr


def test_end_to_end_TROIS_niveaux_naissent_et_la_barriere_les_juge_TOUS(worktree: Path) -> None:
    """Recursion, on REAL commits — and judged at every level, including the deepest.

    Three levels and not two: a child has no descendant, so a scope bug only shows at the third
    level — which is what once made it render EIGHT verdicts for FOUR plans.
    """
    _with_scaffold(worktree)
    racine = f"{_EPREUVE}/recursion"
    t1 = f"{racine}/{ARCS_DIRNAME}/t1"
    s1 = f"{t1}/{ARCS_DIRNAME}/s1"
    for chemin in (racine, t1, s1):
        fait = _naitre(worktree, chemin)
        assert fait.returncode == 0, f"{chemin} : {fait.stdout}{fait.stderr}"

    _add(worktree, racine)
    accepte = _run_real(worktree)
    assert accepte.returncode == 0, f"three levels born conformant, refused: {accepte.stderr}"
    _commit_staged(worktree, "trois niveaux nes conformes")

    # Is the DEEPEST level really judged? We add an orphan to it and demand the refusal.
    _write(worktree, f"{s1}/{ARCS_DIRNAME}/orphelin.md", "# orphelin\n\n- **Y9** \U00002B1C jamais indexé\n")
    _add(worktree, f"{s1}/{ARCS_DIRNAME}/orphelin.md")
    refuse = _run_real(worktree)
    assert refuse.returncode != 0, (
        f"an orphan at the THIRD level passes — the barrier does not go all the way down: "
        f"{refuse.stdout}{refuse.stderr}"
    )
    assert "arc_hors_index" in refuse.stderr and "orphelin.md" in refuse.stderr, refuse.stderr


def test_end_to_end_TROIS_FRERES_et_un_PETIT_FILS_naissent_et_la_barriere_les_accepte(
    worktree: Path,
) -> None:
    """THE NEW CRITERION, and the round's lesson: DEPTH was proven, WIDTH was not.

    The test above births three levels in a LINE — a parent, a child, a grandchild — and it
    was green while the SECOND sibling sub-plan of the same parent was refused, with a
    false cause (`id_duplique` on a collision that exists in no plan). Two siblings
    are enough to show it; there were none anywhere. At the scale D166 targets — a hundred
    theories under the same plan — this is the NORMAL shape, not an edge case.

    Proof that the two verdicts really were opposed, and that is what this test locks in: by
    disarming the internal check, the second sibling was born AND the commit passed. So the
    barrier said yes to what the command refused.
    """
    _with_scaffold(worktree)
    racine = f"{_EPREUVE}/fratrie"
    freres = [f"{racine}/{ARCS_DIRNAME}/t{n}" for n in (1, 2, 3)]
    petit_fils = f"{freres[1]}/{ARCS_DIRNAME}/s1"
    for chemin in (racine, *freres, petit_fils):
        fait = _naitre(worktree, chemin)
        assert fait.returncode == 0, f"{chemin} : {fait.stdout}{fait.stderr}"

    porte = (worktree / racine / "PLAN.md").read_text(encoding="utf-8")
    for frere in ("t1", "t2", "t3"):
        assert f"{ARCS_DIRNAME}/{frere}/PLAN.md" in porte, f"{frere} absent from the index: {porte}"

    _add(worktree, racine)
    accepte = _run_real(worktree)
    assert accepte.returncode == 0, (
        f"three siblings and a grandchild born conformant, refused by the barrier: {accepte.stderr}"
    )
    _commit_staged(worktree, "trois freres et un petit-fils")

    # The counterpart, at the same spot: the barrier was not disarmed along the way.
    _write(worktree, f"{freres[2]}/{ARCS_DIRNAME}/orphelin.md", "# orphelin\n\n- **X9** \U00002B1C jamais indexé\n")
    _add(worktree, f"{freres[2]}/{ARCS_DIRNAME}/orphelin.md")
    refuse = _run_real(worktree)
    assert refuse.returncode != 0, f"an orphan at the 3rd sibling passes: {refuse.stdout}"
    assert "arc_hors_index" in refuse.stderr and "orphelin.md" in refuse.stderr, refuse.stderr


# ---------------------------------------------------------------------------------------------
# 9. THE BARRIER GOES THROUGH `fold_plan` — the ONE enumeration of a plan (C20 · D170).
#
# `judge()` used to fold a plan INLINE (`read_plan` + `plan_entries` + `merge_plan` +
# `index_problems`): a THIRD enumeration, while `plan_new_run.render()` was printing to
# the operator *"it's the same code as the pre-commit barrier."* That promise was false, and
# TWO OPPOSING VERDICTS were measured under it, in throwaway repos:
#
#   1. a BROKEN symlink under `plan/`, indexed   -> registry UNREADABLE, barrier `exit 0`;
#   2. an EMPTY `plan/` directory on disk        -> registry UNREADABLE, barrier `exit 0`.
#
# (1) is closed on BOTH SIDES. (2) CANNOT be — git does not track empty directories —
# so it is DECLARED in the hook and FROZEN here (the section's last test).
#
# WHAT THIS SECTION MEASURES IS NOT "fold_plan is called": it is what the traversal
# REPORTS. `arc_vide` and `bloc_non_ferme` are two PER-ARC refusals the inline copy did NOT
# have; a second enumeration sneaking back in would lose them, and these tests
# would go red. The import check just below is the INVENTORY that goes with them, named
# for what it is: it catches the copy's return BEFORE any behavior diverges.
# ---------------------------------------------------------------------------------------------

#: The four names whose assembly IS the fold. The hook importing even ONE of them means it
#: has started counting arcs itself again.
_FOLD_PARTS = ("read_plan", "plan_entries", "merge_plan", "index_problems")


def _hook_heredoc() -> str:
    """The PYTHON the hook embeds, extracted from its bytes — the only place it lives."""
    text = HOOK.read_text(encoding="utf-8")
    return text.split("<<'PYEOF'\n", 1)[1].split("\nPYEOF", 1)[0]


def _hook_imports() -> set[str]:
    """The names the hook's heredoc really imports, read with `ast` — never with a `grep`.

    THE FIRST VERSION OF THIS FUNCTION SPLIT STRINGS, and it lied twice: it rendered
    "which reads the index, on purpose, and must" as an imported name (a piece of COMMENT), and
    it LOST `ARC_ILLISIBLE`, imported without parentheses. A check that gets its population
    wrong can be green for the wrong reason: it would have taken only one of the four forbidden
    names appearing in a comment for it to accuse the documentation, and an import sitting on
    one line for it to miss it. `ast` answers exactly.

    A `grep` over the whole file would be wrong the other way: `_FOLD_PARTS` appears in the
    hook's COMMENTS, which recount the failure. Recounting the fault is not committing it.
    """
    names: set[str] = set()
    for node in ast.walk(ast.parse(_hook_heredoc())):
        if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("mnemosyne."):
            names |= {alias.asname or alias.name for alias in node.names}
    return names


def test_the_hooks_embedded_python_PARSES() -> None:
    """The floor everything below stands on: no linter in this repo checks the heredoc.

    ``ruff check .githooks`` answers ``All checks passed!`` and read NO file at all — the hook
    has no ``.py`` extension, so ruff never picks it up (``--show-files`` says so: *No Python
    files found*). Green on an empty population is a wall. Here the green bears on real bytes.
    """
    assert _hook_heredoc().strip(), "the hook's `PYEOF` heredoc is missing or empty"
    ast.parse(_hook_heredoc())  # raises SyntaxError, which is the verdict being sought


def test_the_barrier_imports_the_FOLD_and_not_the_pieces_it_is_made_of() -> None:
    """The barrier can no longer own its own walk: it imports nothing to rebuild it from.

    `grep`-able, so level 1. Putting a second enumeration back requires re-importing at least
    one of these four names — and this test says so the instant it is written, not at the next
    audit.
    """
    imported = _hook_imports()
    assert "fold_plan" in imported, (
        "the barrier no longer imports `fold_plan`: it has stopped traversing a plan's one "
        f"enumeration. Imported: {sorted(imported)}"
    )
    revenus = sorted(set(_FOLD_PARTS) & imported)
    assert not revenus, (
        f"the barrier re-imports {revenus} — the fold's own pieces. A THIRD enumeration of a "
        "plan is creeping back in, and it is the one that rendered two opposing verdicts to "
        "`make plans` on a broken link and on an empty `plan/` directory."
    )


#: A two-arc folder plan, whose second arc is what each test below breaks in its own way.
_FOLD_DOOR = (
    "# PLAN — pliage\n\n> **Cap** : éprouver la traversée\n\n## Arcs\n\n"
    "- plan/arc-c.md — le vrai\n"
    "- plan/arc-second.md — celui qu'on abîme\n"
)
_FOLD_ARC = "# arc C\n\n- **C1** \U00002B1C un item\n"


def _plant_fold_plan(worktree: Path, second: str | None) -> list[str]:
    """The door, the healthy arc, and the damaged arc — written and staged. Returns the staged paths.

    ``second is None`` leaves `plan/arc-second.md` to the caller's care (a symlink, which
    `Path.write_text` cannot write).
    """
    _write(worktree, f"{_EPREUVE}/PLAN.md", _FOLD_DOOR)
    _write(worktree, f"{_EPREUVE}/{ARCS_DIRNAME}/arc-c.md", _FOLD_ARC)
    if second is not None:
        _write(worktree, f"{_EPREUVE}/{ARCS_DIRNAME}/arc-second.md", second)
    return [
        f"{_EPREUVE}/PLAN.md",
        f"{_EPREUVE}/{ARCS_DIRNAME}/arc-c.md",
        f"{_EPREUVE}/{ARCS_DIRNAME}/arc-second.md",
    ]


@pytest.mark.parametrize(
    ("second", "attendu"),
    [
        # A BLANK arc file. Measured before being written: 0 of this repo's 12 real arcs is
        # blank, while SEVEN of them have no item at all — which is why the refusal targets
        # the empty file and not the item-less arc. Emptying `plan/collecte.md` by hand
        # silently moved a plan from " 3 items" to " 2 items", without a word.
        ("\n", "arc_vide"),
        # A ``` fence never closed: it swallows every item that follows, exactly the same way
        # it snuffs out the freshness check in a door.
        (
            "# arc second\n\n- **S1** \U00002B1C un item\n\n```python\ndu code jamais referme\n",
            "bloc_non_ferme",
        ),
    ],
)
def test_the_barrier_INHERITS_the_two_per_ARC_refusals_of_the_fold(
    worktree: Path, second: str, attendu: str
) -> None:
    """The two refusals the inline copy did NOT have — so the two witnesses of the traversal.

    They are not decorative: each names an arc that looks fine and whose items have vanished
    from the displayed count. A check only sees what IS, never what is MISSING.
    """
    chemins = _plant_fold_plan(worktree, second)
    done = _commit_and_run(worktree, chemins)
    assert done.returncode != 0, (
        f"the barrier accepts an arc « {attendu} »: it does not traverse the fold "
        f"({done.stdout}{done.stderr})"
    )
    assert attendu in done.stderr, done.stderr
    assert "arc-second.md" in done.stderr, done.stderr


# ---------------------------------------------------------------------------------------------
# 9bis. THE SYMLINK — closed on BOTH sides, and it is the one shape where they meet.
#
# A link is TWO files at once: git stores the LINK (a blob carrying the target path), the
# disk renders the TARGET's bytes. `git show :<path>` therefore succeeds and returns "arc-c.md"
# as if it were the arc's text — a perfectly ordinary arc, with no item, that refuses nothing.
# Measured: a broken link under `plan/` -> `make plans` UNREADABLE, barrier `exit 0`.
# `plan_registry._read_text` refuses any link on the disk side; the `120000` mode from
# `git ls-files -s` is the only place the barrier can learn the same thing, and it is the SAME
# git call as before (this hook runs on EVERY commit — a door slower than the wall is never used).
# ---------------------------------------------------------------------------------------------


@pytest.mark.parametrize("cible", ["cible-absente.md", "arc-c.md"])
def test_a_SYMLINK_arc_is_refused_by_the_barrier_AND_by_the_registry(
    worktree: Path, cible: str
) -> None:
    """Both shapes — a BROKEN link (the measured case) and a VALID one (the mirror) — refused on
    both sides.

    The counterpart lives in the parameter: a valid link diverges in the OTHER direction (the disk
    would read a full arc, the index a path), so proving only the broken case would leave half
    the hole.
    """
    chemins = _plant_fold_plan(worktree, None)
    (worktree / _EPREUVE / ARCS_DIRNAME / "arc-second.md").symlink_to(cible)
    _add(worktree, *chemins)
    assert "120000" in subprocess.run(
        ["git", "-C", str(worktree), "ls-files", "-s", "--", chemins[2]],
        capture_output=True, text=True, check=True,
    ).stdout, "the FIXTURE did not index a link: git stored an ordinary file"

    done = _run_real(worktree)
    assert done.returncode != 0, (
        f"a symlink under `plan/` is accepted by the barrier while the registry refuses it — "
        f"the two surfaces render opposing verdicts: {done.stdout}{done.stderr}"
    )
    assert "arc_illisible" in done.stderr and "arc-second.md" in done.stderr, done.stderr

    etats = read_plan_tree(worktree / _EPREUVE, _EPREUVE)
    assert etats[0].state == ILLISIBLE, (
        f"the registry was already supposed to refuse this link; if it no longer does, IT is "
        f"what changed and the barrier is now the only one biting: {etats[0].why}"
    )


def test_the_barrier_says_the_REGISTRYS_OWN_sentence_about_a_symlink(
    worktree: Path, tmp_path: Path
) -> None:
    """ONE SINGLE HOME: the sentence is the registry's CONSTANT, imported — never retyped here.

    Three links, and all three are needed: (1) `plan_registry` DECLARES `LIEN_SYMBOLIQUE`; (2)
    its own disk reader renders it on a REAL link — queried through the judge's own accessor,
    never through a literal copied into this file; (3) the barrier PRINTS it. Freezing (1)=(3)
    without (2) would leave both sides agreeing on a sentence nobody says anymore.

    Residue, named: the registry distinguishes `LIEN_CASSE` from a link that resolves; the
    barrier cannot — in the git index a link has no resolvable target, and asking would mean
    reading the disk, which this hook must never do. So it says `LIEN_SYMBOLIQUE` in both cases.
    Both shapes are refused on both sides (test above), so the VERDICT agrees; the CAUSE's
    precision is simply not a fact git holds.
    """
    vrai = tmp_path / "cible.md"
    vrai.write_text("# une vraie cible\n", encoding="utf-8")
    lien = tmp_path / "lien.md"
    lien.symlink_to(vrai)
    texte, phrase = _read_text(lien)
    assert texte is None, (
        "the registry FOLLOWED a valid symlink instead of refusing it: there is no longer a "
        "shared sentence to freeze, and the divergence between the two surfaces is reopened"
    )
    assert phrase == LIEN_SYMBOLIQUE, (
        "the disk reader no longer returns the constant it declares — freezing the two "
        f"surfaces' agreement on it would no longer prove anything.\n  returned: {phrase!r}"
    )

    chemins = _plant_fold_plan(worktree, None)
    (worktree / _EPREUVE / ARCS_DIRNAME / "arc-second.md").symlink_to("arc-c.md")
    _add(worktree, *chemins)
    done = _run_real(worktree)
    assert LIEN_SYMBOLIQUE in done.stderr, (
        f"the barrier and the registry no longer say the same thing about a symlink.\n"
        f"  registry: {LIEN_SYMBOLIQUE!r}\n  barrier : {_describe_refusal(done)!r}"
    )


def test_the_barrier_does_not_RETYPE_the_symlink_sentence(tmp_path: Path) -> None:
    """The `grep`-able counterpart of the test above: the sentence is IMPORTED, not copied back in.

    Without it, putting the literal back into the hook leaves everything green — and reopens
    exactly the class this round closes, with two renderings of the same sentence free to drift
    apart. The proof bears on the heredoc's own bytes: the NAME must be imported there, and the
    sentence's first words must appear nowhere as text.
    """
    _ = tmp_path
    assert "LIEN_SYMBOLIQUE" in _hook_imports(), (
        "the barrier no longer imports `LIEN_SYMBOLIQUE` from `plan_registry`: either it "
        "stopped talking about links, or it copied the sentence back in."
    )
    # The needle is the DISTINCTIVE head of the sentence, taken AFTER the dash -- never the words
    # before it. In French `lien symbolique` was distinctive enough; in English `symbolic link` is
    # so ordinary that the hook's own explanatory comment contains it, and this witness accused an
    # innocent hook (it imports the constant at :190 and returns it at :245).
    # Measured out of tree, all three candidates against the real heredoc:
    #   `symbolic link`                  13 ch. -- FALSE POSITIVE today
    #   `the git index carries the LINK`  30 ch. -- clean, catches a verbatim AND a reworded retype
    #   the whole tail after the dash    132 ch. -- clean, but MISSES a reworded retype
    # Taking the whole tail is lengthening a `not in` needle, which WEAKENS it: the realistic drift
    # (someone retypes the sentence with two words changed) sails through. Shortening a `not in`
    # needle strengthens it -- the same operation runs in both directions depending on whether it
    # moves the target closer to reality or further from it.
    # And the needle stays DERIVED from the constant: a witness that hand-copies the sentence it
    # forbids hand-copying would be the very defect it hunts.
    debut = LIEN_SYMBOLIQUE.split(" — ", 1)[1].split(",", 1)[0]
    assert debut not in _hook_heredoc().replace("LIEN_SYMBOLIQUE", ""), (
        f"the hook retypes « …{debut}… » instead of importing the constant — two renderings of "
        "one sentence, so two sentences in six months."
    )


def test_ONE_lost_arc_does_NOT_erase_the_rest_of_the_plan(worktree: Path) -> None:
    """THE BLAST RADIUS — `on_loss` RETURNS a problem, it does not exit `judge`.

    The old loop did a `return` on the FIRST unreadable arc: the plan came back with that one
    line and everything else — the other lost arcs, and the real refusals of the readable arcs —
    vanished from the report. This is exactly the blast radius D170 reduced on the registry side
    (43 items dropping to 0 because ONE file out of thirteen had become unreadable). The verdict
    does not change, only its scope: three causes, three lines.

    Two lost arcs, not one: with only one, a premature `return` would render exactly the same
    output and this test would be green on the very fault it claims to kill.
    """
    _write(
        worktree,
        f"{_EPREUVE}/PLAN.md",
        "# PLAN — souffle\n\n> **Cap** : éprouver le rayon\n\n## Arcs\n\n"
        "- plan/arc-a.md — perdu\n- plan/arc-b.md — perdu aussi\n- plan/arc-c.md — lisible\n",
    )
    _write(worktree, f"{_EPREUVE}/{ARCS_DIRNAME}/arc-c.md", _FOLD_ARC + "- **C2** \U00002753 un autre\n")
    for perdu in ("arc-a.md", "arc-b.md"):
        (worktree / _EPREUVE / ARCS_DIRNAME / perdu).symlink_to("nulle-part.md")
    _add(
        worktree,
        f"{_EPREUVE}/PLAN.md",
        *(f"{_EPREUVE}/{ARCS_DIRNAME}/{nom}" for nom in ("arc-a.md", "arc-b.md", "arc-c.md")),
    )
    done = _run_real(worktree)
    assert done.returncode != 0, f"{done.stdout}{done.stderr}"
    rapport = _describe_refusal(done)
    for attendu in ("plan/arc-a.md", "plan/arc-b.md", "statut_inconnu"):
        assert attendu in rapport, (
            f"« {attendu} » is missing from the report: the barrier abandoned the plan at the "
            f"first lost arc instead of judging it whole.\n{rapport}"
        )


# ---------------------------------------------------------------------------------------------
# 9ter. THE DIVERGENCE THAT CANNOT BE CLOSED — and is therefore FROZEN.
# ---------------------------------------------------------------------------------------------


def test_an_EMPTY_plan_directory_is_the_ONE_state_where_the_two_SIDES_DIVERGE(
    worktree: Path,
) -> None:
    """GIT DOES NOT TRACK EMPTY DIRECTORIES, so the four surfaces cannot agree here.

    A plan whose `plan/` EXISTS on disk and holds NOTHING is, at the same instant:

    * FOLDER-shaped for `plan_registry`, which queries the disk — `(folder / "plan").is_dir()`
      is true, `index_sans_fichier` is evaluated, and every arc the door names is missing:
      UNREADABLE;
    * FILE-shaped for the barrier, which queries the index — no path can start with
      `<folder>/plan/`, no deletion is staged, so `folder_form` falls back to false,
      `index_sans_fichier` is SUPPRESSED by the clause written for single-file plans, `exit 0`.

    These are not two implementations of one question, they are two questions git GUARANTEES
    differ on this population. Neither side can close it: reading the disk here would bless
    bytes nobody is committing (the hook's own "TRAP AVOIDED"), and the registry does not see
    an index it never reads.

    This test FREEZES the divergence instead of leaving it to be rediscovered at the next audit.
    **The day git tracks empty directories — or the day one of the two sides changes its
    predicate — it will go red**, and that is the only warning anyone will get.

    Population: a `plan/` that exists and is EMPTY. No commit can create or preserve it; it
    exists only between two gestures of a person's editor. Every other state — `plan/` absent,
    `plan/` carrying at least one file, `plan/` emptied BY this commit (the `deleted` clause) —
    has the four surfaces in agreement, and that is what the rest of this file measures.
    """
    _write(
        worktree,
        f"{_EPREUVE}/PLAN.md",
        "# PLAN — vide\n\n> **Cap** : éprouver le dossier vide\n\n- **A1** \U00002B1C un item\n\n"
        "## Arcs\n\n- plan/arc-c.md — un arc qui n'existe pas\n",
    )
    (worktree / _EPREUVE / ARCS_DIRNAME).mkdir(parents=True, exist_ok=True)
    _add(worktree, f"{_EPREUVE}/PLAN.md")

    # The STRUCTURAL fact, asserted rather than assumed: the folder is there, the index does not see it.
    assert (worktree / _EPREUVE / ARCS_DIRNAME).is_dir()
    assert not [
        p
        for p in subprocess.run(
            ["git", "-C", str(worktree), "ls-files", "-z"],
            capture_output=True, text=True, check=True,
        ).stdout.split("\0")
        if p.startswith(f"{_EPREUVE}/{ARCS_DIRNAME}/")
    ], "the FIXTURE is no longer the described case: the index carries something under `plan/`"

    done = _run_real(worktree)
    assert done.returncode == 0, (
        "THE DIVERGENCE IS CLOSED — the barrier now refuses an empty `plan/`. Excellent news, "
        "and this test has done its job: check what changed (does git now track empty "
        f"directories?), then replace it with the agreement of both sides.\n{done.stderr}"
    )
    etats = read_plan_tree(worktree / _EPREUVE, _EPREUVE)
    assert etats[0].state == ILLISIBLE and "index_sans_fichier" in etats[0].why, (
        "THE DIVERGENCE IS CLOSED FROM THE OTHER SIDE — the registry no longer refuses an "
        "empty `plan/`. Both surfaces now agree on `exit 0`, which means a door citing an "
        f"absent arc no longer refuses ANYWHERE: {etats[0].state} / {etats[0].why}"
    )
