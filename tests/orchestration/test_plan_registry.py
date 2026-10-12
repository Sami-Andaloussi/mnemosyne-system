"""The verifiable half of the imposed format — three states per project, and what the rule cannot see.

The state that matters is the third one: a ``PLAN.md`` that EXISTS and cannot be read. Reported as
"present" it would pass for done while an interface showed an empty project; reported as "absent" it
would send someone to create a file that is already there. Both are wrong in a way nobody notices.
"""

from __future__ import annotations

import os
import re

from pathlib import Path

from _invariants import REPO_ROOT

from mnemosyne.production.plan_format import (
    ARCS_DIRNAME,
    DOOR_FILENAMES,
    PLAN_FILENAME,
    STATUS_BY_GLYPH,
    plan_skeleton,
    read_plan,
)
from mnemosyne.production.plan_registry import (
    ABSENT,
    ARC_ILLISIBLE,
    ILLISIBLE,
    LISIBLE,
    PROJECTS_DIRNAME,
    ROOT_NAMES,
    arc_par_item,
    scan_plans,
    scan_projects,
)
from mnemosyne.runtime.plans_run import render_registry

GOOD = "# PLAN — x\n\n> **Cap** : avancer\n\n- **A1** \U00002B1C faire\n"


def tree(root: Path, layout: dict[str, str | None]) -> Path:
    """Build ``projects/<bubble>/<project>/PLAN.md``; a ``None`` body means no plan at all."""
    projects = root / "projects"
    for name, body in layout.items():
        home = projects / name
        home.mkdir(parents=True, exist_ok=True)
        if body is not None:
            (home / PLAN_FILENAME).write_text(body, encoding="utf-8")
    return projects


# --- the three states --------------------------------------------------------------------------


def test_a_project_with_a_readable_plan_is_readable(tmp_path: Path):
    registry = scan_projects(tree(tmp_path, {"saas/alpha": GOOD}))
    assert [(p.name, p.state) for p in registry.projects] == [("saas/alpha", LISIBLE)]
    assert registry.projects[0].reading is not None
    assert registry.projects[0].bubble == "saas"


def test_a_project_with_no_plan_is_ABSENT(tmp_path: Path):
    registry = scan_projects(tree(tmp_path, {"saas/alpha": None}))
    assert registry.named(ABSENT) == ("saas/alpha",)


def test_a_plan_that_EXISTS_and_cannot_be_read_is_its_OWN_state_with_the_reason_named(
    tmp_path: Path,
):
    """Neither 'absent' nor 'readable'. Folding it into either one hides a project an interface would
    render empty."""
    registry = scan_projects(tree(tmp_path, {"saas/alpha": "# PLAN — x\n\n- **A1** \U00002B1C faire\n"}))
    broken = registry.projects[0]
    assert broken.state == ILLISIBLE
    assert "Cap" in broken.why
    assert registry.named(ABSENT) == () and registry.named(LISIBLE) == ()


def test_a_plan_whose_lines_are_REFUSED_is_unreadable_even_though_it_has_a_cap_and_items(
    tmp_path: Path,
):
    registry = scan_projects(
        # and not : WAS this fixture's "outside the vocabulary" glyph until the format
        # gained it as `clos`, and the fixture then proved nothing while still reading as if it
        # did. A fixture that names a vocabulary must pick a glyph the vocabulary will not adopt.
        tree(tmp_path, {"saas/alpha": GOOD + "- **A2** \U00002753 hors vocabulaire\n"})
    )
    assert registry.projects[0].state == ILLISIBLE
    assert "statut_inconnu" in registry.projects[0].why


def test_states_are_named_not_counted(tmp_path: Path):
    """A count cannot say WHICH project slipped — every register that rotted here published a ratio."""
    registry = scan_projects(tree(tmp_path, {"a/one": GOOD, "a/two": None, "b/three": None}))
    assert registry.named(ABSENT) == ("a/two", "b/three")
    assert registry.named(LISIBLE) == ("a/one",)


# --- what the depth rule CANNOT see --------------------------------------------------------------


def test_markdown_at_a_BUBBLE_root_is_flagged_because_a_project_there_would_be_invisible(
    tmp_path: Path,
):
    projects = tree(tmp_path, {"saas/alpha": GOOD})
    (projects / "saas" / "README.md").write_text("a project written too high up", encoding="utf-8")
    registry = scan_projects(projects)
    assert registry.misplaced == ("saas",)
    assert registry.named(LISIBLE) == ("saas/alpha",), "the real project is still seen"


def test_dotted_directories_are_tooling_not_projects(tmp_path: Path):
    projects = tree(tmp_path, {"saas/alpha": GOOD})
    (projects / ".git" / "objects").mkdir(parents=True)
    (projects / "saas" / ".obsidian").mkdir()
    registry = scan_projects(projects)
    assert [p.name for p in registry.projects] == ["saas/alpha"]
    assert registry.misplaced == ()


# --- a hostile tree never raises -----------------------------------------------------------------


def test_a_missing_projects_directory_is_an_empty_registry_not_a_crash(tmp_path: Path):
    """``projects/`` is gitignored by design: on a fresh clone it simply does not exist."""
    registry = scan_projects(tmp_path / "projects")
    assert registry.projects == () and registry.root_exists is False


def test_a_plan_that_is_not_utf8_becomes_a_NAMED_state(tmp_path: Path):
    projects = tree(tmp_path, {"saas/alpha": None})
    (projects / "saas/alpha" / PLAN_FILENAME).write_bytes(b"\xff\xfe\x00PLAN")
    registry = scan_projects(projects)
    assert registry.projects[0].state == ILLISIBLE
    assert "unreadable" in registry.projects[0].why


# --- the skeleton must be accepted by the reader that demands it ---------------------------------


def test_the_skeleton_handed_to_a_new_project_is_ALREADY_readable():
    """Handing out a skeleton the reader would refuse teaches the mistake at the one moment the
    project is being created."""
    reading = read_plan(plan_skeleton("Horizon Research"))
    assert reading.readable and reading.problems == ()
    assert reading.project == "Horizon Research" and reading.cap
    assert [item.ident for item in reading.items] == ["A1"]


def test_the_skeleton_carries_the_ADDRESSES_of_what_lives_outside_the_project(tmp_path):
    """D163 — the consumer is pointed at what the emitter holds for it, in the file it opens first.

    A project agent is RIGHT not to walk Mnémosyne's directories: reading every doc to find the two
    that concern it burns its context for nothing. So a document nobody points at is a document
    nobody reads — and the plan skeleton is the only artefact that actually LANDS in a project
    folder, which makes it the one place where the pointer is structural instead of disciplinary.

    Each address is asserted to EXIST on disk, because a pointer to a moved file is worse than none:
    it reads as a live map while sending the agent nowhere."""
    from pathlib import Path

    from _invariants import REPO_ROOT

    import re

    skeleton = plan_skeleton("alpha")

    # The POPULATION comes from the material, the REFERENCE stays a frozen named list. Asserting a
    # hand-written tuple only proved a SAMPLE: a fourth, dead address added to the skeleton passed
    # this test untouched (measured). Deriving the set and requiring EQUALITY makes a new address
    # redden here — which is the moment to check it exists — instead of shipping silent.
    documents = set(re.findall(r"docs/[\w./-]+\.md", skeleton))
    targets = set(re.findall(r"make [a-z][a-z-]+", skeleton))
    assert documents == {
        "docs/FORMAT_PLAN.md",
        "docs/signalements/README.md",
        # C8-c. Added the day the parenthesis protocol shipped, and this assertion is what MADE it
        # get added: the skeleton grew a third address and this line went red, which is the whole
        # point of freezing a NAMED list instead of a count.
        "docs/parentheses/README.md",
    }, documents
    assert targets == {
        "make describe",
        # The two gestures that make a plan be BORN in the folder form (D166 · C20-13). They live
        # HERE for the same reason the three documents do: the skeleton is the only artefact that
        # LANDS in a project folder, and measured the day they were built, no file of any project
        # carried their address. Without this line the capability existed and nothing pointed at it.
        "make plan-emit",
        "make plan-nouveau",
    }, targets

    for address in sorted(documents):
        assert Path(REPO_ROOT, address).is_file(), f"{address} is pointed at but does not exist"
    makefile = Path(REPO_ROOT, "Makefile").read_text(encoding="utf-8")
    for target in sorted(targets):
        # A dead `make` target is the same lie as a moved document, and nothing checked it: the
        # target existed by luck, not by control.
        name = target.removeprefix("make ")
        assert re.search(rf"^{re.escape(name)}:", makefile, re.M), f"{target} does not exist"

    # `make plans` hands the SAME string — one source, never a second copy that could drift.
    from mnemosyne.production.plan_registry import scan_projects
    from mnemosyne.runtime.plans_run import render_registry

    (tmp_path / "bulle" / "sans-plan").mkdir(parents=True)
    printed = render_registry(scan_projects(tmp_path), projects_root=tmp_path)
    assert "docs/signalements/README.md" in printed
    # The SECOND place the address is posted, and it is the one an agent actually reaches: this
    # branch renders precisely when the plan it was asked for does not exist. The skeleton alone
    # answers "what does a plan look like" and said nothing about "what do I run when it will grow".
    #
    # THE SKELETON IS SUBTRACTED FIRST, and that subtraction is the whole assertion. Written as a
    # plain `"make plan-nouveau" in printed` it went GREEN with this branch DELETED — found by
    # sabotage, never by a run: `render_registry` embeds the skeleton, which carries the same words,
    # so the check was satisfied by the source it was not measuring. A control that another source
    # can satisfy measures that other source.
    reste = printed.replace(plan_skeleton("<nom du projet>").rstrip(), "")
    assert "make plan-nouveau CHEMIN=" in reste, reste
    assert "make plan-emit" in reste, reste


def test_the_skeleton_is_what_project_new_hands_over():
    from mnemosyne.production import ProjectGenerator
    from mnemosyne.ports import Bubble
    from mnemosyne.runtime.project_new import render_proposal

    draft = ProjectGenerator().propose(name="alpha", goal="essai", bubble=Bubble("alpha"))
    rendered = render_proposal(draft)
    assert plan_skeleton("alpha").rstrip() in rendered
    assert PLAN_FILENAME in rendered


# --- the report names every project ---------------------------------------------------------------


def test_the_report_names_every_project_in_every_state(tmp_path: Path):
    projects = tree(tmp_path, {"a/one": GOOD, "a/two": None, "b/three": "# PLAN — x\n- [ ] a\n"})
    text = render_registry(scan_projects(projects), projects_root=projects)
    for name in ("a/one", "a/two", "b/three"):
        assert name in text, f"{name} vanished from the report"
    assert "no `PLAN.md`" in text and "UNREADABLE" in text
    assert "```markdown" in text, "a project without a plan must be handed the bytes, not a lecture"
    # The summary line, separately. A body that lists b/three while the line above it counts only
    # a/two is the exact defect measured twice in this repo: the summary lies, the body tells the
    # truth, and everyone reads the summary.
    summary = next(line for line in text.splitlines() if "with no readable plan" in line)
    assert "a/two" in summary and "b/three" in summary, summary
    assert summary.startswith("**2 project(s)"), summary


def test_the_report_of_a_healthy_tree_says_so_and_shows_no_skeleton(tmp_path: Path):
    text = render_registry(
        scan_projects(tree(tmp_path, {"a/one": GOOD})), projects_root=tmp_path / "projects"
    )
    assert "Every project has a readable plan" in text
    assert "```markdown" not in text


def test_the_report_publishes_the_prose_residual_next_to_the_item_count(tmp_path: Path):
    """A count of items alone reads as success. The report must carry what it did not read."""
    body = GOOD + "  du détail rattaché\n\nun paragraphe libre\n"
    text = render_registry(
        scan_projects(tree(tmp_path, {"a/one": body})), projects_root=tmp_path / "projects"
    )
    assert "prose lines," in text and "attached to an item" in text


def test_the_report_accounts_for_EVERY_status_the_format_knows_so_none_can_go_missing(
    tmp_path: Path,
):
    """The per-status detail must sum to the item count — for the vocabulary of TODAY, not of 2026-07.

    Measured why: ``_french`` held a hardcoded ``("fait", "en_cours", "a_faire", "pret")``. The day
    the format gained ``clos`` and ``en_pause``, that copy dropped both WITHOUT a word — a plan of
    six items printed "6 items (1 fait · 1 en cours · 1 à faire · 1 prêt)" and the detail summed to
    FOUR. Nothing was red; the report simply stopped saying two of its own truths.

    The glyphs are derived from the reader's vocabulary on purpose. A frozen list here would go
    stale on exactly the event this test exists to catch, and would do it silently — the same
    failure, moved one file over.
    """
    glyphs = list(STATUS_BY_GLYPH)
    body = "# PLAN — x\n> **Cap** : c\n" + "".join(
        f"- **A{i}** {glyph} item\n" for i, glyph in enumerate(glyphs, 1)
    )
    projects = _tree(tmp_path, **{"saas|alpha": body})
    printed = render_registry(scan_projects(projects), projects_root=projects)

    counts = [int(n) for n in re.findall(r"(\d+) ", printed.split("items (", 1)[1].split(")", 1)[0])]
    assert sum(counts) == len(glyphs), printed
    assert len(counts) == len(glyphs), printed


def test_an_absent_projects_tree_is_reported_as_normal_not_as_a_failure(tmp_path: Path):
    text = render_registry(
        scan_projects(tmp_path / "projects"), projects_root=tmp_path / "projects"
    )
    assert "folder — no PROJECT is examined below" in text and "gitignored" in text


# --- what an isolated audit found MISSING on the report itself (arc C7) --------------------------


def _tree(root: Path, **plans: str) -> Path:
    projects = root / "projects"
    for relative, body in plans.items():
        path = projects / relative.replace("|", "/") / "PLAN.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
    projects.mkdir(parents=True, exist_ok=True)
    return projects


_GOOD = "# PLAN — alpha\n> **Cap** : avancer\n- **A1** \U00002B1C premier\n"


def test_a_misplaced_project_is_named_even_when_the_scan_found_NOTHING_else(tmp_path: Path) -> None:
    """The one tree where the warning is the ONLY signal was the one tree that never printed it.

    A project written one level too high — `projects/monprojet/PLAN.md`, the natural placement for
    anyone who has not read the depth rule — yields zero projects, so the render returned early and
    the block written expressly for this case sat below the return, unreachable.
    """
    projects = tmp_path / "projects" / "monprojet"
    projects.mkdir(parents=True)
    (projects / "PLAN.md").write_text(_GOOD, encoding="utf-8")
    printed = render_registry(scan_projects(tmp_path / "projects"), projects_root=tmp_path / "projects")
    assert "holds no project" in printed
    assert "monprojet" in printed, "the only available signal must not be thrown away"


def test_the_completeness_claim_never_stands_above_a_project_it_may_not_have_seen(tmp_path: Path) -> None:
    """"Every project has a readable plan" three lines above a possibly-invisible one."""
    projects = _tree(tmp_path, **{"saas|alpha": _GOOD})
    (projects / "monprojet").mkdir()
    (projects / "monprojet" / "PLAN.md").write_text(_GOOD, encoding="utf-8")
    printed = render_registry(scan_projects(projects), projects_root=projects)
    assert "**Every project has a readable plan.**" not in printed
    assert "SEEN" in printed and "monprojet" in printed


def test_a_broken_symlink_is_ILLISIBLE_not_ABSENT(tmp_path: Path) -> None:
    """The third state degrading into the first: the report then says "create the file" — it exists.

    `read_text` raises `FileNotFoundError` for a dangling link exactly as it does for nothing at all,
    so the branch answered ABSENT without ever asking whether the ENTRY was there.
    """
    projects = _tree(tmp_path, **{"saas|alpha": _GOOD})
    plan = projects / "saas" / "alpha" / "PLAN.md"
    plan.unlink()
    plan.symlink_to(tmp_path / "nulle-part" / "PLAN.md")
    project = scan_projects(projects).projects[0]
    assert project.state == ILLISIBLE, project
    assert "broken link" in (project.why or "")


def test_an_unreadable_plan_says_WHERE_not_only_WHAT_CLASS(tmp_path: Path) -> None:
    """"1 refused line(s): statut_inconnu" on a long plan is a wall — the line number is held."""
    projects = _tree(tmp_path, **{"saas|alpha": "# PLAN — alpha\n> **Cap** : x\n- **A1** \U00002753 abandonné\n"})
    printed = render_registry(scan_projects(projects), projects_root=projects)
    assert "UNREADABLE" in printed
    assert "line 3:" in printed, printed


# --- a plan is a FOLDER (D166 / C20-3) ---------------------------------------------------------
#
# Everything below goes through the DISK reader, never through strings alone: the pure helpers can
# be right about paths while `rglob`, symlinks and NFC all disagree with them one layer down.

_DOOR = "# PLAN — alpha\n\n> **Cap** : avancer\n\n## Arcs\n\n- plan/arc-c.md\n- plan/arc-d.md\n"


def _folder_plan(tmp_path: Path, door: str, arcs: dict[str, str]) -> Path:
    """A project whose plan is a door plus a ``plan/`` directory — the shape D166 retained."""
    home = tmp_path / "projects" / "saas" / "alpha"
    (home / "plan").mkdir(parents=True, exist_ok=True)
    (home / PLAN_FILENAME).write_text(door, encoding="utf-8")
    for name, body in arcs.items():
        target = home / "plan" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body, encoding="utf-8")
    return tmp_path / "projects"


def test_a_door_with_no_items_and_arcs_with_no_cap_make_ONE_readable_plan(tmp_path: Path) -> None:
    """The scission of ``readable``, end to end on the disk. Under the single old rule the door
    (cap, no item) and each arc (items, no cap) were BOTH unreadable, so this plan could not exist —
    which is precisely the mono-file assumption D166 clause 6 removes."""
    projects = _folder_plan(
        tmp_path,
        _DOOR,
        {"arc-c.md": "# arc C\n\n- **C1** \U00002B1C un item\n", "arc-d.md": "- **D1** \U00002705 un autre\n"},
    )
    plan = scan_projects(projects).projects[0]
    assert plan.state == LISIBLE, plan.why
    assert plan.reading is not None
    assert [item.ident for item in plan.reading.items] == ["C1", "D1"]
    # The arcs are NAMED in the reading, not counted: "2 arcs" cannot say which one is missing.
    # Door-relative, the SAME namespace as `PlanItem.source` — asserted together on purpose, because
    # the two drifted apart (`arc-c.md` against `plan/arc-c.md`) while both docstrings claimed one.
    assert plan.reading.parts == ("plan/arc-c.md", "plan/arc-d.md")
    # And each item still knows which file it came from — `line` alone stopped being a location.
    assert {item.source for item in plan.reading.items} == set(plan.reading.parts)


def test_an_arc_the_door_never_names_is_REFUSED_by_name(tmp_path: Path) -> None:
    """D166 clause 4, the central one. Measured: on a real project — 1 orphan in 28, the best-kept corpus of
    the repo — the most recent plan file declares ``lire_en_premier: true`` and the door written
    three hours earlier does not know it exists. A hand-held index rots in HOURS."""
    projects = _folder_plan(
        tmp_path,
        _DOOR,
        {
            "arc-c.md": "- **C1** \U00002B1C x\n",
            "arc-d.md": "- **D1** \U00002B1C y\n",
            "arc-oublie.md": "- **Z1** \U00002B1C personne ne me nomme\n",
        },
    )
    plan = scan_projects(projects).projects[0]
    assert plan.state == ILLISIBLE
    assert plan.reading is not None
    kinds = [problem.kind for problem in plan.reading.problems]
    assert kinds == ["arc_hors_index"], plan.reading.problems
    assert "arc-oublie.md" in plan.reading.problems[0].detail


def test_an_index_entry_with_NO_file_behind_it_is_REFUSED_by_name(tmp_path: Path) -> None:
    """The mirror refusal. Without it the check would only ever punish writing a file and never
    punish writing a promise — and a door that points nowhere is exactly what 25 orphan plan files
    out of 25 look like from the inside."""
    projects = _folder_plan(tmp_path, _DOOR, {"arc-c.md": "- **C1** \U00002B1C x\n"})
    plan = scan_projects(projects).projects[0]
    assert plan.state == ILLISIBLE
    assert plan.reading is not None
    assert [p.kind for p in plan.reading.problems] == ["index_sans_fichier"]
    assert "arc-d.md" in plan.reading.problems[0].detail


def test_the_SAME_identity_in_two_arcs_is_a_duplicate_because_the_scope_is_the_FOLDER(
    tmp_path: Path,
) -> None:
    """D166 clause 5. ``ident_seen`` used to be created inside ``read_plan``, so this collision was
    invisible file by file — cutting a plan into arcs would have silenced every cross-arc duplicate
    on the very edit that creates the arcs."""
    projects = _folder_plan(
        tmp_path,
        _DOOR,
        {"arc-c.md": "- **C1** \U00002B1C x\n", "arc-d.md": "- **C1** \U00002B1C le meme\n"},
    )
    plan = scan_projects(projects).projects[0]
    assert plan.state == ILLISIBLE
    assert plan.reading is not None
    assert [p.kind for p in plan.reading.problems] == ["id_duplique"]
    # The refusal names BOTH sides, with their files — "already line 1" would point at five places.
    problem = plan.reading.problems[0]
    assert problem.source == "plan/arc-d.md" and "plan/arc-c.md" in problem.detail


def test_two_DIFFERENT_plans_may_each_carry_the_same_identity(tmp_path: Path) -> None:
    """The other half of clause 5, and the one that would be easy to over-tighten: at the scale this
    format is built for, a hundred theories will each name a strategy ``S02``. Each theory is a plan
    of its own, so the scope stops at the folder — a shared key across plans is NORMAL."""
    projects = tree(tmp_path, {"saas/alpha": GOOD, "saas/beta": GOOD})
    states = {plan.name: plan.state for plan in scan_projects(projects).projects}
    assert states == {"saas/alpha": LISIBLE, "saas/beta": LISIBLE}


def test_a_NESTED_plan_gets_its_own_line_instead_of_hiding_behind_its_parent(tmp_path: Path) -> None:
    """Clause 3: a folder carrying a door IS a plan, at every level. Reported separately on purpose —
    a nested plan has its own cap and its own identity scope, so a broken one must be nameable. If it
    were folded into its parent, a project could be green while a plan inside it was unreadable."""
    projects = _folder_plan(
        tmp_path,
        "# PLAN — alpha\n\n> **Cap** : avancer\n\n- plan/arc-c.md\n- plan/theories/PLAN.md\n",
        {
            "arc-c.md": "- **C1** \U00002B1C x\n",
            "theories/PLAN.md": "# PLAN — T001\n\n> **Cap** : la theorie\n\n- **C1** \U00002B1C meme clef\n",
        },
    )
    found = {plan.name: plan.state for plan in scan_projects(projects).projects}
    assert found == {"saas/alpha": LISIBLE, "saas/alpha/plan/theories": LISIBLE}, found


def test_C7_a_NESTED_plans_ROOT_line_carries_the_TOTAL_across_its_sous_plans(
    tmp_path: Path,
) -> None:
    """C7: the very first line of a plan with sub-plans used to show the count of its DOOR alone
    (1 here), never the real sum (3, door + sub-plan) — exactly the line a reader in a hurry
    reads as THE answer. The total now lives ON that same line, never a new line
    (constant size, bound 2)."""
    projects = _folder_plan(
        tmp_path,
        "# PLAN — alpha\n\n> **Cap** : avancer\n\n- plan/arc-c.md\n- plan/theories/PLAN.md\n",
        {
            "arc-c.md": "- **C1** \U00002B1C x\n",
            "theories/PLAN.md": (
                "# PLAN — T001\n\n> **Cap** : la theorie\n\n- **T1** \U00002B1C y\n- **T2** \U00002B1C z\n"
            ),
        },
    )
    rendu = render_registry(scan_projects(projects), projects_root=projects)
    lignes = [ligne for ligne in rendu.splitlines() if ligne.startswith("- ")]
    assert len(lignes) == 2, lignes
    racine, enfant = lignes
    assert racine.startswith("- \U00002705 **saas/alpha** — 1 items")
    assert "**3 total across 1 sub-plan(s)**" in racine, racine
    # The CHILD's line never carries this suffix — it would be false at its own scale.
    assert "total across" not in enfant, enfant


def test_C7_a_FLAT_plan_pays_ZERO_bytes_for_the_total_suffix(tmp_path: Path) -> None:
    """Constant size (bound 2): a plan WITHOUT a sub-plan (the majority of the corpus, measured)
    does not see a single extra byte — the suffix exists ONLY when there is something to sum."""
    projects = _folder_plan(
        tmp_path,
        _DOOR,
        {"arc-c.md": "- **C1** \U00002B1C un item\n", "arc-d.md": "- **D1** \U00002705 un autre\n"},
    )
    rendu = render_registry(scan_projects(projects), projects_root=projects)
    assert "total across" not in rendu, rendu


def test_C7_an_UNREADABLE_sous_plan_is_NAMED_rather_than_silently_counted_as_zero(
    tmp_path: Path,
) -> None:
    """An unreadable sub-plan has no reliable count — hiding it in the sum would file it as
    "zero item", the same absence of measurement as a line reading zero. So it is named SEPARATELY."""
    projects = _folder_plan(
        tmp_path,
        "# PLAN — alpha\n\n> **Cap** : avancer\n\n- plan/arc-c.md\n- plan/theories/PLAN.md\n",
        {
            "arc-c.md": "- **C1** \U00002B1C x\n",
            # Sub-plan door with NO index at all (`plan/` absent): the read yields a plan that is
            # unreadable for lack of an index, never an exception -- same class as the other tests
            # in this file that refuse by name rather than by crash.
            "theories/PLAN.md": "# PLAN — T001\n\n> **Cap** : la theorie\n\n- **T1** \U00002B1C y\n",
        },
    )
    # Breaks the sub-plan's door AFTER the fact, with non-UTF-8 bytes -- unreadable in the reader's
    # sense, never an exception (`_read_text`, `utf-8-sig` then `OSError`/`UnicodeDecodeError`).
    (projects / "saas" / "alpha" / "plan" / "theories" / PLAN_FILENAME).write_bytes(
        b"\xff\xfe" + "# PLAN — T001".encode("utf-16-le")
    )
    rendu = render_registry(scan_projects(projects), projects_root=projects)
    racine = next(ligne for ligne in rendu.splitlines() if ligne.startswith("- \U00002705 **saas/alpha**"))
    assert "**1 total across 1 sub-plan(s)** (1 unreadable, not counted)" in racine, racine


def test_a_NESTED_plan_survives_when_its_PARENT_door_is_unreadable(tmp_path: Path) -> None:
    """ AUDIT DELEGATED ON 2026-08-15 (via ``J1``, measured by the orchestrator): ``read_plan_tree``
 returned on the ROOT door's own read failure before ever calling ``arc_tree`` — so a nested
 sub-plan, with its own cap and its own identity scope (the test just above), vanished ENTIRELY
 whenever the PARENT alone could not be read, even though nothing in the child's own subtree was
 at fault. ``make plans``, ``make lot-emit`` and ``make plan-gate-emit`` all lost the judgment of
 a whole subtree — including a real defect living inside it — behind a root door that reads as
 "nothing to report" instead of "I never looked here". Same class as the arc-level fix this
 docstring already tells above :func:`~mnemosyne.production.plan_registry.read_plan_tree`, one
 floor higher: a population EXCLUDED is a population UNJUDGED, never a population at rest.
 """
    projects = _folder_plan(
        tmp_path,
        "# PLAN — alpha\n\n> **Cap** : avancer\n\n- plan/theories/PLAN.md\n",
        {"theories/PLAN.md": "# PLAN — T001\n\n> **Cap** : la theorie\n\n- **C1** \U00002B1C x\n"},
    )
    door = projects / "saas" / "alpha" / PLAN_FILENAME
    door.unlink()
    door.symlink_to(tmp_path / "nulle-part" / "PLAN.md")
    found = {plan.name: plan.state for plan in scan_projects(projects).projects}
    assert found == {"saas/alpha": ILLISIBLE, "saas/alpha/plan/theories": LISIBLE}, found


def test_a_MONO_FILE_plan_stays_legal_and_untouched(tmp_path: Path) -> None:
    """Recursion is PERMITTED, never imposed. A real project keeps 26 plan files flat and is the healthiest
    planning corpus measured in this repo — a format that called that a defect would be wrong about
    its own best example."""
    projects = tree(tmp_path, {"saas/alpha": GOOD})
    plan = scan_projects(projects).projects[0]
    assert plan.state == LISIBLE and plan.reading is not None
    assert plan.reading.parts == (), "a single-file plan must not claim arcs it does not have"


# --- clause 1 of D166: the plan roots that are NOT projects (C20-5) ------------------------------
#
# `scan_projects` walks `projects/` and can therefore never see the one plan that cannot live there:
# Mnémosyne's own. `PLAN_ROOTS` is the LINE that turns that exception into a declaration — before it,
# `make plans` did not know the repo had a plan and a whole second barrier had to be written for it,
# so the repo graded its own plan by a mechanism it wrote for itself. An isolated audit found the
# declaration held by NOTHING: emptying `PLAN_ROOTS` left every test green (no test called
# `scan_plans` at all), which is the state the two tests below close.

#: Where Mnémosyne's own plan lives, written out rather than read from `PLAN_ROOTS`. Deriving it
#: would make the sabotage satisfy its own test — zero root declared, zero root expected, green on
#: `PLAN_ROOTS = ()`, which is exactly the hole being closed. The literal is not free-floating
#: either: the test right below asserts the LIVING repo really carries a plan door there, so the day
#: that plan moves this line goes red instead of quietly checking nothing.
MNEMOSYNE_PLAN_DIR = "docs"


def test_scan_plans_SEES_the_repos_own_plan_which_can_never_live_under_projects() -> None:
    """The surface that judges plans must judge Mnémosyne's own, by the SAME reader as the projects.

    Run against the living repo on purpose: the fact this test rests on — "the repo's plan sits in
    ``docs/`` and not under ``projects/``" — is a fact about the disk, not about the constant being
    guarded. State is deliberately NOT asserted: whether today's own plan door is readable
    is the pre-commit barrier's job (``tests/platform/test_pre_commit_plan_gate.py``), and pinning it
    here would make this test red for someone else's edit instead of for the guarantee it holds.
    """
    home = REPO_ROOT / MNEMOSYNE_PLAN_DIR
    door = next((home / name for name in DOOR_FILENAMES if os.path.lexists(home / name)), None)
    assert door is not None, (
        f"{home} no longer carries any plan door ({', '.join(DOOR_FILENAMES)}): the declared "
        f"root {MNEMOSYNE_PLAN_DIR!r} points into the void, this test no longer verifies anything"
    )
    registry = scan_plans(REPO_ROOT)
    found = {plan.plan_path: plan for plan in registry.projects}
    assert door in found, (
        f"scan_plans does not see Mnémosyne's own plan ({door}) — the surface that judges plans is "
        f"blind to its own. Seen: {sorted(plan.name for plan in registry.projects)}"
    )
    # NAMED, and in the operator's words (D33): a root reported as `docs` would be a directory, not a plan.
    assert found[door].name == ROOT_NAMES[MNEMOSYNE_PLAN_DIR], found[door].name
    # And it is precisely what the projects walk cannot reach — the reason the declaration exists.
    # Portable: `projects/` is gitignored by design and simply absent from a fresh clone.
    walked = {plan.plan_path for plan in scan_projects(REPO_ROOT / PROJECTS_DIRNAME).projects}
    assert door not in walked, "if `projects/` already saw it, the declaration would be a duplicate"


def test_a_DECLARED_root_and_the_projects_come_back_from_ONE_scan(tmp_path: Path) -> None:
    """The hermetic half: one scan, one list of roots, one vocabulary — never a parallel code path.

    Equality on the whole mapping rather than a membership test, because the failure this closes is
    an ABSENCE: "the root plan is missing" and "the projects are missing" are the same green under
    any assertion that only looks at what it expects to find.
    """
    root = tmp_path / MNEMOSYNE_PLAN_DIR
    root.mkdir()
    (root / PLAN_FILENAME).write_text(GOOD, encoding="utf-8")
    tree(tmp_path, {"saas/alpha": GOOD})

    states = {plan.name: plan.state for plan in scan_plans(tmp_path).projects}
    assert states == {ROOT_NAMES[MNEMOSYNE_PLAN_DIR]: LISIBLE, "saas/alpha": LISIBLE}, states
    assert [plan.name for plan in scan_projects(tmp_path / PROJECTS_DIRNAME).projects] == [
        "saas/alpha"
    ], "the projects walk alone must still see exactly the projects — no root folded into it"


# --- the mono-file plan is the FLOOR, not a degraded folder (C20-5) ------------------------------


def test_a_MONO_FILE_plan_may_NAME_a_plan_path_that_does_not_exist(tmp_path: Path) -> None:
    """``folder_form`` is READ OFF THE DISK by ``read_plan_tree``, and forcing it True is silent.

    A plan that is one file has no index to verify: nothing under ``plan/`` can be missing when there
    is no ``plan/``. So a door naming ``plan/…md`` — a plan writing about the form it has not adopted
    yet, which is exactly what this repo's own plan does today — must stay READABLE. With
    ``folder_form=True`` hardcoded at the call site, that same plan becomes ILLISIBLE for an arc it
    never claimed to own, and its author is refused for a sentence.

    Both halves are asserted from the SAME door bytes, so the only variable is the ``plan/``
    directory itself: with one, the entry is an index entry and the refusal is right; without one,
    the refusal is friction on the floor of the format. An empty ``plan/`` is used deliberately —
    putting a real arc in it would ALSO fire ``arc_hors_index`` and the test would no longer isolate
    ``folder_form``.

    Written as a real BULLET in entry position: a mention buried in prose, in backticks or inside a
    fenced block is not an index entry, so a fixture built on one would pass whatever this flag does.
    """
    door = (
        "# PLAN — alpha\n\n> **Cap** : avancer\n\n"
        "- **A1** \U00002B1C un item\n"
        "- plan/arc-c.md — un arc qui n'existe pas\n"
    )
    mono = scan_projects(tree(tmp_path / "mono", {"saas/alpha": door})).projects[0]
    assert mono.state == LISIBLE, (
        "a SINGLE-file plan has no index to verify — refusing it for a "
        f"`{ARCS_DIRNAME}/…md` reference it does not claim to own makes the floor form unusable: "
        f"{mono.why}"
    )

    projects = tree(tmp_path / "dossier", {"saas/alpha": door})
    (projects / "saas" / "alpha" / ARCS_DIRNAME).mkdir()
    folder = scan_projects(projects).projects[0]
    assert folder.state == ILLISIBLE, "same bytes + a plan/ folder: the index is verified"
    assert folder.reading is not None
    kinds = [problem.kind for problem in folder.reading.problems]
    assert kinds == ["index_sans_fichier"], folder.reading.problems


# --- the ONE walk over a plan's own files (C20-10) ------------------------------------------------


def test_plan_files_gives_the_DOOR_first_then_every_arc_at_any_depth(tmp_path: Path) -> None:
    """Published so three test modules stop each writing their own — a copy of a walk drifts.

    Two properties, and both are load-bearing for the callers: the DOOR comes first (they read the
    plan's own material starting from it), and an arc nested under ``plan/c/`` is material too.
    """
    from mnemosyne.production.plan_registry import plan_files

    folder = tmp_path / "projet"
    (folder / ARCS_DIRNAME / "c").mkdir(parents=True)
    (folder / PLAN_FILENAME).write_text("# PLAN — p\n\n> **Cap** : c\n", encoding="utf-8")
    (folder / ARCS_DIRNAME / "arc-c.md").write_text("- **A1** \U00002B1C x\n", encoding="utf-8")
    (folder / ARCS_DIRNAME / "c" / "arc-1.md").write_text("- **A2** \U00002B1C y\n", encoding="utf-8")

    found = plan_files(folder)
    assert found[0] == folder / PLAN_FILENAME, "the door is no longer first"
    assert set(found[1:]) == {
        folder / ARCS_DIRNAME / "arc-c.md",
        folder / ARCS_DIRNAME / "c" / "arc-1.md",
    }


def test_plan_files_answers_NOTHING_where_no_door_stands(tmp_path: Path) -> None:
    """A directory without a door is not a plan, at any level (D166, clause 3) — and a ``plan/``
    full of markdown does not make one. Returning its files would hand a caller a corpus that
    belongs to nobody."""
    from mnemosyne.production.plan_registry import plan_files

    orphan = tmp_path / "pas-un-plan"
    (orphan / ARCS_DIRNAME).mkdir(parents=True)
    (orphan / ARCS_DIRNAME / "arc-c.md").write_text("- **A1** \U00002B1C x\n", encoding="utf-8")
    assert plan_files(orphan) == ()


def test_plan_files_still_answers_when_the_door_CANNOT_be_read(tmp_path: Path) -> None:
    """It reads the DISK, not a reading — a corpus that vanishes because one file broke is the
    silence, not the safety. The caller then sees the broken file instead of an empty walk."""
    from mnemosyne.production.plan_registry import plan_files

    folder = tmp_path / "projet"
    (folder / ARCS_DIRNAME).mkdir(parents=True)
    (folder / PLAN_FILENAME).write_bytes(b"\xff\xfe pas de l'utf-8")
    (folder / ARCS_DIRNAME / "arc-c.md").write_text("- **A1** \U00002B1C x\n", encoding="utf-8")
    assert plan_files(folder) == (folder / PLAN_FILENAME, folder / ARCS_DIRNAME / "arc-c.md")


# --- ONE broken arc must not erase THIRTEEN files (le rayon de souffle) ---------------------------
#
# Measured on the real plan the day it became a folder, through `scan_plans` — the surface, not a
# reading of my own: `\xff\xfe` appended to ONE of twelve arcs took `docs/` from **43 items to 0**,
# and `make plans`, `make ui-json` and the parked-runs queue went blank together. Before the folder
# form a broken plan was one broken FILE; after it, one broken file was thirteen. Every test below
# holds one half of the repair, and the halves pull in OPPOSITE directions on purpose: keeping the
# items (1, 5) is what makes it tempting to also call the plan readable, and (2) is what forbids it.

_DOOR_3 = (
    "# PLAN — alpha\n\n> **Cap** : avancer\n\n## Arcs\n\n"
    "- plan/arc-c.md\n- plan/arc-d.md\n- plan/arc-e.md\n"
)
_ARCS_3 = {
    "arc-c.md": "- **C1** \U00002B1C un item\n",
    "arc-d.md": "- **D1** \U00002B1C un autre\n- **D2** \U00002705 et encore\n",
    "arc-e.md": "- **E1** \U00002B1C le dernier\n",
}


def _with_one_broken_arc(tmp_path: Path, broken: str = "arc-d.md") -> Path:
    """Three arcs, one of them bytes nobody can decode — the exact shape reproduced on the real plan."""
    projects = _folder_plan(tmp_path, _DOOR_3, _ARCS_3)
    (projects / "saas" / "alpha" / ARCS_DIRNAME / broken).write_bytes(b"\xff\xfe pas de l'utf-8")
    return projects


def test_ONE_unreadable_arc_no_longer_erases_the_ITEMS_OF_THE_OTHERS(tmp_path: Path) -> None:
    """The blast radius, pinned as a LIST of identities rather than a count.

    A count would go green on the day the reader returns three items that are not these three; the
    identities say WHICH survived, and the two that vanish are exactly the two the broken file holds.
    """
    plan = scan_projects(_with_one_broken_arc(tmp_path)).projects[0]
    assert plan.reading is not None, "a broken arc again wiped out the ENTIRE plan reading"
    assert [entry.ident for entry in plan.reading.items] == ["C1", "E1"]
    # And the arcs that WERE read are still named: `parts` is what a report prints to say what it
    # walked, and a reading that keeps the items while forgetting where they came from is half a fix.
    assert plan.reading.parts == ("plan/arc-c.md", "plan/arc-e.md")


def test_a_plan_with_an_unreadable_arc_is_STILL_illisible(tmp_path: Path) -> None:
    """THE SYMMETRIC HOLE, and the reason it cannot open: degrading locally is one edit away from
    letting a broken plan PASS. It cannot, because the loss is a named ``PlanProblem`` and
    ``is_readable`` refuses ANY reading that carries one — the verdict is untouched, only its blast
    radius shrinks. Asserted on the STATE, which is what every surface and the pre-commit gate read.
    """
    plan = scan_projects(_with_one_broken_arc(tmp_path)).projects[0]
    assert plan.state == ILLISIBLE, "a plan with an unreadable arc passed as readable"


def test_the_unreadable_arc_is_NAMED_where_the_operator_reads_and_says_the_count_is_SHORT(
    tmp_path: Path,
) -> None:
    """A refusal that does not say what to do is a wall — and this one has a second duty.

    Keeping the items makes the report PLAUSIBLE: 43 items screaming zero is impossible to miss, 41
    items is not. So the refusal must name the file (the geste) AND say that the count above it is
    short (the honesty). Checked on ``render_registry``, the bytes ``make plans`` really prints.
    """
    registry = scan_projects(_with_one_broken_arc(tmp_path))
    plan = registry.projects[0]
    assert "plan/arc-d.md" in plan.why, plan.why
    assert plan.reading is not None
    assert ARC_ILLISIBLE in [problem.kind for problem in plan.reading.problems]
    printed = render_registry(registry, projects_root=tmp_path / "projects")
    assert "plan/arc-d.md" in printed, printed
    assert "MISSING" in printed, printed


def test_an_unreadable_arc_gets_its_OWN_line_so_a_READING_LESS_consumer_still_sees_the_loss(
    tmp_path: Path,
) -> None:
    """The third track, and it is not decoration — it is the hole the first two would have opened.

    ``ui_contract._read_runs_parques`` names a loss on ``reading is None`` and says NOTHING when a
    reading is present. Handing it a populated reading and nothing else would have turned « ses runs
    parqués sont invisibles ici » into an EMPTY reason on a queue that is short — a queue that is
    silently short reads as good news. The arc therefore answers on its own line, in the shape every
    consumer already branches on, carrying its OWN path so the card points at the file to repair.
    """
    projects = _with_one_broken_arc(tmp_path)
    found = {plan.name: plan for plan in scan_projects(projects).projects}
    assert set(found) == {"saas/alpha", "saas/alpha/plan/arc-d.md"}, sorted(found)
    orphan = found["saas/alpha/plan/arc-d.md"]
    assert orphan.state == ILLISIBLE
    assert orphan.reading is None, "the arc's line must be the one a reading-less consumer relies on"
    assert orphan.plan_path == projects / "saas" / "alpha" / ARCS_DIRNAME / "arc-d.md"
    assert orphan.why, "a named line with no reason is a wall"


def test_an_unreadable_arc_is_still_owed_by_the_DOOR_index(tmp_path: Path) -> None:
    """Being unreadable does not excuse being un-indexed: the file is still ON THE DISK.

    Dropping it from the list handed to ``index_problems`` would have made one defect quietly forgive
    another — break the arc the door forgot, and the orphan refusal disappears with it.
    """
    projects = _folder_plan(
        tmp_path, _DOOR_3, {**_ARCS_3, "arc-oublie.md": "- **Z1** \U00002B1C personne ne me nomme\n"}
    )
    (projects / "saas" / "alpha" / ARCS_DIRNAME / "arc-oublie.md").write_bytes(b"\xff\xfe")
    plan = scan_projects(projects).projects[0]
    assert plan.reading is not None
    kinds = sorted({problem.kind for problem in plan.reading.problems})
    # The LITERAL, like `arc_hors_index` beside it, never the constant: this token is PUBLISHED —
    # `make ui-json` ships it as `refus[].genre` and a UI switches on it. Asserting it through the
    # constant would let a rename sail through green and rename a public vocabulary in silence.
    assert kinds == ["arc_hors_index", "arc_illisible"], plan.reading.problems


def test_a_NESTED_plan_survives_a_BROKEN_SIBLING_arc(tmp_path: Path) -> None:
    """The early return also skipped the recursion, so one bad arc erased every plan NESTED below.

    That is the same defect one level down: a nested plan has its own cap, its own identity scope and
    its own verdict, and none of them depend on a sibling file being decodable.
    """
    projects = _folder_plan(
        tmp_path,
        _DOOR_3 + "- plan/theories/PLAN.md\n",
        {
            **_ARCS_3,
            "theories/PLAN.md": "# PLAN — T001\n\n> **Cap** : la théorie\n\n- **S1** \U00002B1C x\n",
        },
    )
    (projects / "saas" / "alpha" / ARCS_DIRNAME / "arc-d.md").write_bytes(b"\xff\xfe")
    found = {plan.name: plan.state for plan in scan_projects(projects).projects}
    assert found["saas/alpha/plan/theories"] == LISIBLE, found


def test_a_plan_whose_DOOR_cannot_be_read_stays_the_FLOOR_and_degrades_NOTHING(
    tmp_path: Path,
) -> None:
    """The line the repair must NOT cross. A door holds the cap, the index and the identity ledger:
    with it unreadable there is nothing left to degrade INTO, and inventing a reading from the arcs
    alone would publish a plan with no cap as though somebody had written one."""
    projects = _folder_plan(tmp_path, _DOOR_3, _ARCS_3)
    (projects / "saas" / "alpha" / PLAN_FILENAME).write_bytes(b"\xff\xfe")
    plans = scan_projects(projects).projects
    assert [(plan.name, plan.state) for plan in plans] == [("saas/alpha", ILLISIBLE)]
    assert plans[0].reading is None and plans[0].why


# --- what is MISSING in an arc: named, never silently subtracted from the total -----------------------


PORTE_3_ARCS = (
    "# PLAN — demo\n\n> **Cap** : avancer\n\n## Les arcs\n\n"
    f"- `{ARCS_DIRNAME}/socle.md` — Socle\n"
    f"- `{ARCS_DIRNAME}/collecte.md` — Collecte\n"
    f"- `{ARCS_DIRNAME}/rendu.md` — Rendu\n"
)


def _plan_dossier(root: Path, arcs: dict[str, str]) -> Path:
    """A three-arc plan, in FOLDER form, under ``projects/b/p``."""
    home = root / "projects" / "b" / "p"
    (home / ARCS_DIRNAME).mkdir(parents=True, exist_ok=True)
    (home / PLAN_FILENAME).write_text(PORTE_3_ARCS, encoding="utf-8")
    for name, body in arcs.items():
        (home / ARCS_DIRNAME / name).write_text(body, encoding="utf-8")
    return root / "projects"


ARC = "# Un arc\n\n- **{id}** \U00002B1C faire\n"


def test_un_arc_VIDE_est_NOMME_et_refuse_jamais_soustrait_du_total(tmp_path: Path):
    """ The defect that `make plans` — the ONLY surface that runs on a PROJECT plan — did not
 see: emptying `plan/collecte.md` by hand turned " 3 items" into " 2 items", with no
 refusal, no filename, state `lisible`. A control sees what IS, never what is MISSING.

 The refusal lives in `fold_plan`, the one fold, so all four surfaces carry it at once.
 """
    projects = _plan_dossier(
        tmp_path,
        {"socle.md": ARC.format(id="A1"), "collecte.md": "", "rendu.md": ARC.format(id="C1")},
    )
    projet = scan_projects(projects).projects[0]
    assert projet.state == ILLISIBLE, projet
    assert [p.kind for p in (projet.reading.problems if projet.reading else ())] == ["arc_vide"]
    rendu = render_registry(scan_projects(projects), projects_root=projects)
    assert f"{ARCS_DIRNAME}/collecte.md" in rendu, rendu


def test_un_arc_devenu_PROSE_n_est_pas_refuse_mais_son_ZERO_est_IMPRIME(tmp_path: Path):
    """ The symmetric hole, and the measurement that avoided it: refusing "an arc with no item" —
 the remedy the audit named — accuses **7 of this repo's 12 REAL arcs** (prose sections that
 became files at the conversion), so it would have made Mnémosyne's own plan UNREADABLE and
 blocked every commit. What remains is that the zero be VISIBLE: the count is PER ARC, never a
 total.
 """
    projects = _plan_dossier(
        tmp_path,
        {
            "socle.md": ARC.format(id="A1"),
            "collecte.md": "# Collecte\n\nDe la prose, aucun item.\n",
            "rendu.md": ARC.format(id="C1"),
        },
    )
    registry = scan_projects(projects)
    assert registry.projects[0].state == LISIBLE, registry.projects[0]
    rendu = render_registry(registry, projects_root=projects)
    assert f"{ARCS_DIRNAME}/collecte.md (0)" in rendu, rendu
    assert f"{ARCS_DIRNAME}/socle.md (1)" in rendu, rendu
    assert "with no item at all" in rendu and f"{ARCS_DIRNAME}/collecte.md" in rendu


def test_un_arc_dont_la_CLOTURE_reste_ouverte_est_refuse_en_le_DISANT(tmp_path: Path):
    """The second, narrower blind spot: `unclosed_fence_line` used to be called on the DOOR only.
 A ``` fence never closed inside an ARC swallows its items without a word — exactly the silence
 the `bloc_non_ferme` refusal exists to make audible, one door lower.

 NAMED BY THE ORCHESTRATOR (2026-08-15, measured by SETS against last night): since A7,
 `bloc_document_non_ferme` (the guard AT DOCUMENT LEVEL, added that day) fires on the SAME
 fixture, in addition to `bloc_non_ferme` (the guard AT ARC LEVEL, what this test has been
 checking from the start). A legitimate consequence, not a defect: two independent mechanisms
 see the same missing closure, each at its own layer. The test now checks by SET of
 kinds (the order between the two was never a guarantee this test ever held) rather
 than by fixed index, which would have spuriously survived a THIRD kind added tomorrow.
 """
    projects = _plan_dossier(
        tmp_path,
        {
            "socle.md": ARC.format(id="A1"),
            "collecte.md": "# Collecte\n\n```markdown\n- **B1** \U00002B1C avalé\n",
            "rendu.md": ARC.format(id="C1"),
        },
    )
    projet = scan_projects(projects).projects[0]
    assert projet.state == ILLISIBLE, projet
    problemes = projet.reading.problems if projet.reading else ()
    assert {p.kind for p in problemes} == {"bloc_non_ferme", "bloc_document_non_ferme"}, problemes
    assert {p.source for p in problemes} == {f"{ARCS_DIRNAME}/collecte.md"}, problemes


# --- a SYMBOLIC LINK is TWO files: named, and the DOOR is no longer blamed in its place -------


def test_un_lien_CASSE_sous_plan_accuse_le_FICHIER_et_jamais_la_PORTE(tmp_path: Path):
    """ The named CAUSE was wrong, and its fix would have destroyed a real index line.

 `arc_tree` used to filter on `is_file()`, which FOLLOWS the link: a broken link therefore
 vanished from the disk walk, and the door that still names it was accused of
 `index_sans_fichier` — "remove this entry", on a perfectly correct entry. `git ls-files`, for
 its part, never dropped it: the barrier and this walk were answering on two different corpora.
 """
    projects = _plan_dossier(
        tmp_path, {"socle.md": ARC.format(id="A1"), "rendu.md": ARC.format(id="C1")}
    )
    lien = projects / "b" / "p" / ARCS_DIRNAME / "collecte.md"
    lien.symlink_to(tmp_path / "nulle-part.md")
    projet = scan_projects(projects).projects[0]
    assert projet.state == ILLISIBLE, projet
    kinds = [p.kind for p in (projet.reading.problems if projet.reading else ())]
    assert kinds == [ARC_ILLISIBLE], kinds
    assert "index_sans_fichier" not in kinds, "the DOOR is accused of a defect of the FILE"
    assert "broken link" in projet.why, projet.why


def test_un_lien_VALIDE_sous_plan_est_refuse_en_NOMMANT_la_divergence(tmp_path: Path):
    """The counterpart, and it is the one that closes the divergence: a link that RESOLVES reads
    perfectly on disk and is NOT the same object in the git index, which stores the link itself.
    Followed silently, it would make the registry say `lisible` and the barrier the opposite — or
    the reverse. Two files for one path, so it is NAMED. Measured: zero symbolic links in this repo."""
    projects = _plan_dossier(
        tmp_path, {"socle.md": ARC.format(id="A1"), "rendu.md": ARC.format(id="C1")}
    )
    cible = tmp_path / "ailleurs.md"
    cible.write_text(ARC.format(id="B1"), encoding="utf-8")
    (projects / "b" / "p" / ARCS_DIRNAME / "collecte.md").symlink_to(cible)
    projet = scan_projects(projects).projects[0]
    assert projet.state == ILLISIBLE, projet
    assert [p.kind for p in (projet.reading.problems if projet.reading else ())] == [ARC_ILLISIBLE]
    assert "symbolic link" in projet.why, projet.why


def test_un_depot_SANS_projects_montre_QUAND_MEME_les_racines_de_plan_declarees(tmp_path: Path):
    """ An early return throws away everything it had already measured.

 `render_registry` used to say "nothing to examine" and RETURN the moment `projects/` was
 missing — so on a freshly cloned repo, where this folder is gitignored BY DESIGN (the note says
 so itself), this surface hid Mnémosyne's own plan ENTIRELY. That is exactly the invisibility
 clause 1 of D166 exists to close, reopened one branch above the code that closes it. The
 absence becomes a NOTE, never an early exit."""
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / PLAN_FILENAME).write_text(GOOD, encoding="utf-8")
    registry = scan_plans(tmp_path)
    assert registry.root_exists is False
    rendu = render_registry(registry, projects_root=tmp_path / PROJECTS_DIRNAME)
    assert ROOT_NAMES["docs"] in rendu, rendu
    assert "no PROJECT is examined" in rendu, "the absence of `projects/` is no longer stated"


# --- C9 (re-ouvert) : `arc_par_item` --------------------------------------------------------------


def test_arc_par_item_EXCLUT_un_sibling_ILLISIBLE_meme_appele_sans_pre_filtrage(
    tmp_path: Path,
) -> None:
    """ HOLE FOUND BY THE ISOLATED AUDIT (D75): the only production caller
 (`lot_emit_run.py`) already pre-filters `membres` before calling `arc_par_item`, so its OWN
 internal filter ("readable and non-empty") was exercised by NO test — sabotage-proven:
 reducing it to `list(membres)` left the 32 existing tests all green. This function is
 PUBLIC (promoted to be reusable, `carte_run.py` is a second candidate caller); its contract
 must hold even when called WITHOUT the pre-filtering `lot_emit_run.py` already applies.

 Here: a caller that does NOT pre-filter -- raw `registry.projects`, unreadable sibling included.
 Without the filter, `plan.reading.items` on the unreadable sibling (`reading is None`) would raise."""
    racine = tmp_path / "projects" / "bulle" / "multi"
    (racine / "plan").mkdir(parents=True)
    (racine / "PLAN.md").write_text(
        "# PLAN — multi\n\n> **Cap** : x\n\n"
        "- plan/01-a/PLAN.md\n- plan/02-b/PLAN.md\n- **R1** \U00002B1C **racine.**\n",
        encoding="utf-8",
    )
    sous_a = racine / "plan" / "01-a"
    sous_a.mkdir()
    (sous_a / PLAN_FILENAME).write_text(
        "# PLAN — a\n\n> **Cap** : x\n\n- **A1** \U00002B1C **un.**\n", encoding="utf-8"
    )
    sous_b = racine / "plan" / "02-b"
    sous_b.mkdir()
    (sous_b / PLAN_FILENAME).write_text(
        "# PLAN — b\n\n> **Cap** : x\n\n- **B1** \U00002B1C **un.**\n", encoding="utf-8"
    )
    # Made unreadable AFTER the fact, same pattern as `test_C7_an_UNREADABLE_sous_plan_is_NAMED...`:
    # non-UTF-8 bytes, never an exception from the reader.
    (sous_b / PLAN_FILENAME).write_bytes(b"\xff\xfe" + "# PLAN — b".encode("utf-16-le"))

    registry = scan_plans(tmp_path)
    membres = [
        p
        for p in registry.projects
        if p.name == "bulle/multi" or p.name.startswith("bulle/multi/plan/")
    ]
    assert {p.name: p.state for p in membres} == {
        "bulle/multi": LISIBLE,
        "bulle/multi/plan/01-a": LISIBLE,
        "bulle/multi/plan/02-b": ILLISIBLE,
    }, "la fixture ne pose pas la forme attendue -- un sibling lisible, un illisible"

    resultat = arc_par_item(membres)  # membres NOT pre-filtered -- exactly `registry.projects`
    assert resultat is not None
    assert resultat == {"R1": "bulle/multi", "A1": "bulle/multi/plan/01-a"}
