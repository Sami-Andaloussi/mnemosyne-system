"""Exercise plan paths containing spaces, punctuation, and Unicode normalization variants."""

from __future__ import annotations

import unicodedata

from pathlib import Path

from mnemosyne.production.plan_format import (
    ARCS_DIRNAME,
    DOOR_FILENAMES,
    STATUS_BY_GLYPH,
    index_problems,
    owning_plan,
    plan_entries,
)
from mnemosyne.production.plan_registry import ILLISIBLE, LISIBLE, read_plan_tree

#: How the figures in this module's docstring were obtained - the COMMAND, so they can be re-run.
#: A register that publishes only its result rots without a sound.
_REPO_MEASUREMENT = (
    'python3 -c \'import pathlib,unicodedata; p=[str(x) for x in pathlib.Path("projects")'
    '.rglob("*")]; print(len(p), sum(" " in x for x in p), sum(":" in x for x in p),'
    ' sum(unicodedata.normalize("NFC",x)!=x for x in p))\''
)

#: Taken from the reader's own vocabulary rather than typed here: a glyph pasted into a test file is
#: one more copy that can drift, and this suite is about bytes nobody can see.
GLYPH_A_FAIRE = next(glyph for glyph, status in STATUS_BY_GLYPH.items() if status == "a_faire")

DOOR = DOOR_FILENAMES[0]


def _nfc(text: str) -> str:
    """The composed form - what an editor writes into a door."""
    return unicodedata.normalize("NFC", text)


def _nfd(text: str) -> str:
    """The decomposed form - what 80 paths under ``projects/`` are stored as."""
    return unicodedata.normalize("NFD", text)


def _write(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def _disk_paths(root: Path) -> tuple[str, ...]:
    """Every FILE under ``root``, relative and POSIX, as the FILESYSTEM spells it - sorted.

    The round trip is the point: a name is written once and read back in whatever form the volume
    kept, which is the only way a test can hold the NFD form its own source file cannot show.
    """
    return tuple(sorted(p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()))


def _arc(ident: str, title: str) -> str:
    return f"## {title}\n\n- **{ident}** {GLYPH_A_FAIRE} {title}\n"


def _door(project: str, index: tuple[str, ...]) -> str:
    """A door naming its cap and citing each entry of ``plan/`` as a bare path - Acme Research's
    own form.

    WARNING: **The dash is load-bearing, and it is the measured COST of the tail rule.** This fixture used
    to write ``- plan/x.md porte la suite``, and the day the entry rule started reading what FOLLOWS
    the path - because ``- plan/arc-archive.md a ete archive, il n existe plus`` was REFUSING a real
    commit - that form became a sentence: a word behind the path with nothing but a space in front
    of it is prose, and no structural rule can tell this fixture's intent from that one's. So the
    cost is real, it is named rather than hidden (``INNOCENT_LINES`` in ``test_plan_format.py`` pins
    the exact shape), and it is paid here by writing the separator this repo already writes.
    ``arc_hors_index`` was never affected: completeness stays generous, only staleness needs an
    entry.
    """
    lines = [f"# PLAN - {project}", "", "> **Cap** : hold the measurement", "", "## The arcs", ""]
    lines += [f"- {ARCS_DIRNAME}/{entry} - carries what follows" for entry in index]
    return "\n".join(lines) + "\n"


def _kinds(plan) -> list[str]:
    return sorted(problem.kind for problem in (plan.reading.problems if plan.reading else ()))


# --- the whole plan, read through hostile names ---------------------------------------------------


def test_a_plan_folder_of_arcs_with_spaces_colons_and_accents_is_read_WHOLE(tmp_path: Path) -> None:
    """Every item found, and NOT ONE refusal - the false-accusation test.

    The door is written NFC (what an editor emits) and the three arcs are created NFD, so door and
    disk spell the same names with
    different bytes. Compared with ``==``, each accented arc collects ``index_sans_fichier`` on the
    door's entry - and, once the second NFC guard inside ``cited`` falls too, ``arc_hors_index`` on
    the file itself: two refusals per arc, on a plan where nobody mistyped anything.

    The plan root carries a space as well, and one arc sits under an ``ExamplePilot-S:S`` directory
    to exercise a colon in a path component.
    """
    folder = tmp_path / "projects" / "saas" / "Acme Research"
    wanted = {
        _nfd("arc économie.md"): "A1",
        _nfd("ExamplePilot-S:S/arc é.md"): "B2",
        _nfd("notes de séance.md"): "C3",
    }
    for relative, ident in wanted.items():
        _write(folder / ARCS_DIRNAME / relative, _arc(ident, f"hold {ident}"))
    _write(folder / DOOR, _door("Acme Research", tuple(_nfc(name) for name in wanted)))

    (plan,) = read_plan_tree(folder, "saas/Acme Research")
    assert plan.state == LISIBLE, (plan.why, _kinds(plan))
    reading = plan.reading
    assert reading is not None
    assert reading.problems == (), [(p.kind, p.detail) for p in reading.problems]
    assert {item.ident for item in reading.items} == {"A1", "B2", "C3"}
    # The arcs are NAMED in the reading, in the form the disk gave - a count could not say which
    # one went missing, and the NFD spelling must survive all the way to the report. Door-relative,
    # the SAME namespace as `PlanItem.source`: the two drifted apart once and `merge_plan` now
    # refuses a pair whose key and whose lines disagree, so asserting the EQUALITY is the point.
    assert reading.parts == tuple(
        f"{ARCS_DIRNAME}/{name}" for name in _disk_paths(folder / ARCS_DIRNAME)
    )
    assert set(reading.parts) == {f"{ARCS_DIRNAME}/{name}" for name in wanted}
    assert {item.source for item in reading.items} == set(reading.parts)


def test_a_door_written_in_NFC_finds_the_arc_the_filesystem_stores_in_NFD(tmp_path: Path) -> None:
    """The crossing that actually happens: an editor writes the index, macOS stores the file.

    Both halves are asserted rather than assumed - that the volume really kept the decomposed form
    (if macOS renormalised, the message says so instead of the test quietly proving nothing), and
    that the two strings really differ, so a green here is not a tautology.
    """
    folder = tmp_path / "a project"
    on_disk = _nfd("arc économie.md")
    in_door = _nfc("arc économie.md")
    assert on_disk != in_door, "the two forms must differ or this test measures nothing"

    _write(folder / ARCS_DIRNAME / on_disk, _arc("A1", "hold A1"))
    _write(folder / DOOR, _door("a project", (in_door,)))

    stored = _disk_paths(folder / ARCS_DIRNAME)
    assert stored == (on_disk,), f"macOS renormalised what it was given: {stored!r} for {on_disk!r}"
    assert index_problems((folder / DOOR).read_text(encoding="utf-8"), stored) == ()

    (plan,) = read_plan_tree(folder, "a project")
    assert plan.state == LISIBLE, (plan.why, _kinds(plan))
    assert plan.reading is not None
    assert [item.ident for item in plan.reading.items] == ["A1"]


def test_a_door_written_in_NFD_finds_the_arc_the_filesystem_stores_in_NFC(tmp_path: Path) -> None:
    """The same crossing the other way - a door saved decomposed, a file created composed.

    Written because a normalisation that only runs on ONE side is a rule in inequality: it would
    hold this direction and drop the other, and both directions exist the moment two tools (an
    editor, a shell, Finder) touch the same plan.
    """
    folder = tmp_path / "a project"
    on_disk = _nfc("arc économie.md")
    in_door = _nfd("arc économie.md")
    assert on_disk != in_door

    _write(folder / ARCS_DIRNAME / on_disk, _arc("A1", "hold A1"))
    _write(folder / DOOR, _nfd(_door("a project", (in_door,))))

    stored = _disk_paths(folder / ARCS_DIRNAME)
    assert stored == (on_disk,), f"macOS renormalised what it was given: {stored!r} for {on_disk!r}"
    assert index_problems((folder / DOOR).read_text(encoding="utf-8"), stored) == ()

    (plan,) = read_plan_tree(folder, "a project")
    assert plan.state == LISIBLE, (plan.why, _kinds(plan))


def _bare_door(project: str, names: tuple[str, ...]) -> str:
    """A door indexing its arcs by BARE FILE NAME - 75 of Acme Research's 81 plan edges take this
    form.

    No ``plan/`` prefix, so ``_ARC_REF_RE`` extracts nothing at all and the completeness check rests
    ENTIRELY on the ``NFC(base) in door`` fallback. That isolates one guard from the other two, which
    is the only way to find out which one is actually holding: with a prefixed path in the door,
    three NFC comparisons overlap and killing any one of them changes nothing.
    """
    lines = [f"# PLAN - {project}", "", "> **Cap** : hold the measurement", "", "## The arcs", ""]
    lines += [f"- arc {name} carries what follows" for name in names]
    return "\n".join(lines) + "\n"


def test_a_BARE_name_index_still_finds_the_arc_the_disk_stores_in_NFD(tmp_path: Path) -> None:
    """The generous form of an index, crossed with the decomposition - one guard, on its own.

    Written after measuring that the suite could not tell three NFC comparisons apart: neutralising
    the fallback alone changed no verdict, because a ``plan/``-prefixed entry is also matched by
    ``_same_name``. A mechanism no test can single out is a mechanism nobody can remove safely.
    """
    folder = tmp_path / "a project"
    on_disk = _nfd("arc économie.md")
    _write(folder / ARCS_DIRNAME / on_disk, _arc("A1", "hold A1"))
    _write(folder / DOOR, _bare_door("a project", (_nfc("arc économie.md"),)))

    door_text = (folder / DOOR).read_text(encoding="utf-8")
    assert f"{ARCS_DIRNAME}/" not in door_text, "the prefixed form would hide the guard under test"
    assert _disk_paths(folder / ARCS_DIRNAME) == (on_disk,)
    assert index_problems(door_text, (on_disk,)) == ()

    (plan,) = read_plan_tree(folder, "a project")
    assert plan.state == LISIBLE, (plan.why, _kinds(plan))


def test_a_BARE_name_index_written_in_NFD_still_finds_the_arc_stored_in_NFC(tmp_path: Path) -> None:
    """The same guard, crossed the other way - and the only case where normalising the DOOR bites.

    With a ``plan/``-prefixed entry, ``_same_name`` normalises both sides and the door's own
    normalisation is dead weight; here nothing else runs, so a door saved decomposed against a file
    stored composed is refused unless the door text itself is composed first.
    """
    folder = tmp_path / "a project"
    on_disk = _nfc("arc économie.md")
    _write(folder / ARCS_DIRNAME / on_disk, _arc("A1", "hold A1"))
    _write(folder / DOOR, _nfd(_bare_door("a project", (_nfd("arc économie.md"),))))

    door_text = (folder / DOOR).read_text(encoding="utf-8")
    assert _disk_paths(folder / ARCS_DIRNAME) == (on_disk,)
    assert index_problems(door_text, (on_disk,)) == ()

    (plan,) = read_plan_tree(folder, "a project")
    assert plan.state == LISIBLE, (plan.why, _kinds(plan))


# --- the refusal must still BITE on a hostile name -------------------------------------------------


def test_an_UNINDEXED_arc_with_a_space_and_an_accent_is_still_REFUSED(tmp_path: Path) -> None:
    """Tolerating NFC must not become a hole: a mechanism that never bites proves nothing.

    One arc is indexed (and crosses NFC/NFD, so the tolerance is exercised in the same fixture) and
    one is not. Exactly one refusal is expected, of exactly one kind, naming the orphan - a suite
    asserting only ``problems != ()`` would pass just as well if the tolerance had started
    swallowing the indexed one and accusing something else.
    """
    folder = tmp_path / "a project"
    orphan = _nfd("arc é oublié.md")
    indexed = _nfd("arc économie.md")
    _write(folder / ARCS_DIRNAME / indexed, _arc("A1", "hold A1"))
    _write(folder / ARCS_DIRNAME / orphan, _arc("B2", "hold B2"))
    _write(folder / DOOR, _door("a project", (_nfc(indexed),)))

    (plan,) = read_plan_tree(folder, "a project")
    assert plan.state == ILLISIBLE, plan
    assert plan.reading is not None
    assert [(p.kind, p.detail) for p in plan.reading.problems] == [
        ("arc_hors_index", f"{ARCS_DIRNAME}/{orphan}")
    ]
    assert "arc_hors_index" in plan.why
    # Both items are still read: a refusal is not a crash, and the plan is not silently truncated.
    assert {item.ident for item in plan.reading.items} == {"A1", "B2"}


def test_an_index_entry_with_a_hostile_name_and_NO_file_is_still_REFUSED(tmp_path: Path) -> None:
    """The other half of the pair, on a name carrying a space, a ``:`` and an accent.

    ``_ARC_REF_RE`` deliberately lets a space and a ``:`` through the reference it extracts. That
    permissiveness is what makes this refusal possible at all: a stricter class would never even
    SEE the entry, and a door pointing at nothing would read as a door pointing at nothing wrong.
    """
    folder = tmp_path / "a project"
    real = _nfd("arc économie.md")
    ghost = _nfc("ExamplePilot-S:S/arc é disparu.md")
    _write(folder / ARCS_DIRNAME / real, _arc("A1", "hold A1"))
    _write(folder / DOOR, _door("a project", (_nfc(real), ghost)))

    (plan,) = read_plan_tree(folder, "a project")
    assert plan.state == ILLISIBLE, plan
    assert plan.reading is not None
    assert [(p.kind, p.detail) for p in plan.reading.problems] == [
        ("index_sans_fichier", f"{ARCS_DIRNAME}/{ghost}")
    ]


# --- the pure splitters, fed with paths the disk produced ------------------------------------------


def test_owning_plan_and_plan_entries_hold_a_path_carrying_a_COLON_and_a_SPACE(
    tmp_path: Path,
) -> None:
    """``projects/saas/Acme Research/plan/ExamplePilot-S:S/arc é.md`` belongs to Acme Research, not
    to its neighbour.

    The paths handed to these two pure functions come from ``rglob``, never from this file: they are
    the shape ``plan_registry`` really passes, decomposed accents included. A second project sits in
    the same bubble so a rule that answered "the only plan around" would be caught.
    """
    research = tmp_path / "projects" / "saas" / "Acme Research"
    hostile = _nfd("ExamplePilot-S:S/arc é.md")
    plain = _nfd("arc économie.md")
    for relative, ident in ((hostile, "A1"), (plain, "A2")):
        _write(research / ARCS_DIRNAME / relative, _arc(ident, f"hold {ident}"))
    _write(research / DOOR, _door("Acme Research", (_nfc(hostile), _nfc(plain))))
    other = tmp_path / "projects" / "saas" / "autre projet"
    _write(other / ARCS_DIRNAME / "lone arc.md", _arc("B1", "hold B1"))
    _write(other / DOOR, _door("autre projet", ("lone arc.md",)))

    paths = _disk_paths(tmp_path)
    root = "projects/saas/Acme Research"
    assert f"{root}/{ARCS_DIRNAME}/{hostile}" in paths
    assert owning_plan(f"{root}/{ARCS_DIRNAME}/{hostile}", paths) == root
    assert owning_plan(f"{root}/{DOOR}", paths) == root
    assert owning_plan("projects/saas/autre projet/plan/lone arc.md", paths) != root

    arcs, nested = plan_entries(root, paths)
    assert arcs == _disk_paths(research / ARCS_DIRNAME)
    assert set(arcs) == {hostile, plain} and nested == ()


def test_owning_plan_matches_by_BYTES_so_a_caller_must_pass_the_DISK_form(tmp_path: Path) -> None:
    """Where the NFC tolerance STOPS - named here rather than discovered in production.

    ``index_problems`` compares names in NFC; ``owning_plan`` and ``plan_entries`` do not - they are
    prefix tests over strings, and a folder typed NFC against a tree stored NFD matches NOTHING and
    says so with an empty tuple, not a refusal. That silence is safe today only because every caller
    passes the disk's own bytes (``plan_registry`` calls ``plan_entries("", ...)`` on ``rglob``
    output). This test freezes that contract: 78 of the 80 decomposed paths under ``projects/`` are
    decomposed in a DIRECTORY component, which is precisely the part being prefix-matched here.
    """
    folder_disk = _nfd("projets/économie")
    _write(tmp_path / folder_disk / ARCS_DIRNAME / "arc one.md", _arc("A1", "hold A1"))
    _write(tmp_path / folder_disk / DOOR, _door("économie", ("arc one.md",)))
    paths = _disk_paths(tmp_path)

    assert owning_plan(f"{folder_disk}/{ARCS_DIRNAME}/arc one.md", paths) == folder_disk
    assert plan_entries(folder_disk, paths) == (("arc one.md",), ())

    typed = _nfc("projets/économie")
    assert typed != folder_disk
    assert owning_plan(f"{typed}/{ARCS_DIRNAME}/arc one.md", paths) is None
    assert plan_entries(typed, paths) == ((), ())


LEVELS = ("my project", "sub plan un", "sub plan deux", "sub plan trois")
ARCS = ("arc one.md", "arc two.md", "arc three.md", "arc four.md")


def _nested_tree(tmp_path: Path) -> list[str]:
    """Four plans, each inside the ``plan/`` of the one above, every directory carrying a space.

    Returns the folder of each level, relative to ``tmp_path`` - the deepest is
    ``my project/plan/sub plan un/plan/sub plan deux/plan/sub plan trois``.
    """
    folders: list[str] = []
    here = ""
    for depth, level in enumerate(LEVELS):
        here = f"{here}/{ARCS_DIRNAME}/{level}" if here else level
        folders.append(here)
        index = [ARCS[depth]]
        if depth + 1 < len(LEVELS):
            index.append(f"{LEVELS[depth + 1]}/{DOOR}")
        _write(tmp_path / here / ARCS_DIRNAME / ARCS[depth], _arc(f"A{depth}", f"hold A{depth}"))
        _write(tmp_path / here / DOOR, _door(level, tuple(index)))
    return folders


def test_a_plan_nested_FOUR_levels_deep_with_a_SPACE_at_every_level_claims_its_OWN_arc(
    tmp_path: Path,
) -> None:
    """The longest match wins, four times over, on directory names that all carry a space.

    Recursion is permitted, never imposed - but the day it is used it will be used on names like
    ``sub plan un``, because 1775 of the 8165 paths under ``projects/`` contain a space. Each level
    must claim its OWN arc and name the level below as a nested door: a level that swallowed its
    child's arc would double the item, and one that dropped it would lose a file in silence.
    """
    folders = _nested_tree(tmp_path)
    paths = _disk_paths(tmp_path)

    for depth, folder in enumerate(folders):
        arc_path = f"{folder}/{ARCS_DIRNAME}/{ARCS[depth]}"
        assert owning_plan(arc_path, paths) == folder, arc_path
        found, nested = plan_entries(folder, paths)
        assert found == (ARCS[depth],), (folder, found)
        child = () if depth + 1 == len(LEVELS) else (f"{LEVELS[depth + 1]}/{DOOR}",)
        assert set(child) <= set(nested), (folder, nested)

    # The door of a level is the door of THAT level: no file is judged by two plans at once.
    for depth, folder in enumerate(folders):
        assert owning_plan(f"{folder}/{DOOR}", paths) == folder


def test_a_plan_THREE_levels_below_the_door_is_reported_EXACTLY_ONCE(tmp_path: Path) -> None:
    """A DEFECT found by this fixture on 2026-07-29, then closed - kept as its regression.

    ``plan_entries`` promises that a nested door "OWNS its own file and its own ``plan/`` subtree,
    and those are excluded here - counting them twice would double every item at every level of a
    recursive plan". That exclusion held for a nested plan's ARCS and not for its DOORS: the
    outermost call returned all THREE descendant doors instead of its one child, because
    ``owning_plan`` answers "its own directory" for a door wherever it sits.

    ``read_plan_tree`` then recursed into each of them AND into their own descendants, so four real
    plans came back as EIGHT verdicts - the deepest one four times over. Two nesting levels show
    nothing (a child has no descendant), which is why the shape only appears at THREE, and why it
    would have shipped. Only the outermost doors are a plan's business now.
    """
    folders = _nested_tree(tmp_path)
    paths = _disk_paths(tmp_path)

    _, nested = plan_entries(folders[0], paths)
    assert nested == (f"{LEVELS[1]}/{DOOR}",), nested

    plans = read_plan_tree(tmp_path / LEVELS[0], LEVELS[0])
    names = [plan.name for plan in plans]
    assert len(names) == len(set(names)) == 4, names
    assert [names.count(folder) for folder in folders] == [1, 1, 1, 1], names
    assert [plan.state for plan in plans] == [LISIBLE] * 4, [(p.name, p.why) for p in plans]
    for plan in plans:
        assert plan.reading is not None and len(plan.reading.items) == 1


def test_naming_ONE_nested_door_does_NOT_make_every_OTHER_nested_door_look_indexed(
    tmp_path: Path,
) -> None:
    """The bare-name fallback must not certify a file nobody wrote. Found as a DEFECT, then closed.

    ``cited`` falls back to "is the bare file name mentioned anywhere in the door", which is what
    lets Acme Research's 75 bare mentions count as an index. Every door, however, is called
    ``PLAN.md``, so a door naming ONE nested plan contained the string ``PLAN.md`` and thereby cited
    them ALL: the second sub-plan could be created, never indexed, and nothing was refused. Two arcs
    both called ``notes.md`` in different sub-directories collided the same way.

    The fallback is now allowed only for a base name carried by exactly ONE entry - measured both
    ways here so the claim is not one-sided: naming neither refuses both, naming one refuses the
    other, and naming both by their PATH refuses nothing.
    """
    folder = tmp_path / "a project"
    _write(folder / ARCS_DIRNAME / "arc one.md", _arc("A1", "hold A1"))
    for sub in ("sub plan a", "sub plan b"):
        _write(folder / ARCS_DIRNAME / sub / ARCS_DIRNAME / "arc.md", _arc(f"B{sub[-1]}", "hold"))
        _write(folder / ARCS_DIRNAME / sub / DOOR, _door(sub, ("arc.md",)))

    silent = _door("a project", ("arc one.md",))
    entries = ("arc one.md", f"sub plan a/{DOOR}", f"sub plan b/{DOOR}")
    assert [p.kind for p in index_problems(silent, entries)] == ["arc_hors_index"] * 2

    half = _door("a project", ("arc one.md", f"sub plan a/{DOOR}"))
    assert [(p.kind, p.detail) for p in index_problems(half, entries)] == [
        ("arc_hors_index", f"{ARCS_DIRNAME}/sub plan b/{DOOR}")
    ], "naming one nested door must not cite the other - they share a base name"

    _write(folder / DOOR, _door("a project", entries))
    assert index_problems((folder / DOOR).read_text(encoding="utf-8"), entries) == ()
    (plan, *_) = read_plan_tree(folder, "a project")
    assert plan.state == LISIBLE, (plan.why, _kinds(plan))


# --- the trap itself, measured on this machine -----------------------------------------------------


def test_the_NFD_trap_is_REAL_the_same_file_answers_to_two_different_strings(
    tmp_path: Path,
) -> None:
    """The same filesystem name may be represented in NFC or NFD; lookups normalize both forms."""
    composed = _nfc("arc économie.md")
    decomposed = _nfd("arc économie.md")
    assert composed != decomposed and len(decomposed) == len(composed) + 1

    _write(tmp_path / decomposed, "x")
    stored = _disk_paths(tmp_path)
    assert stored == (decomposed,), f"macOS renormalised: stored {stored!r}, created {decomposed!r}"

    # One file, both names - the filesystem resolves either form ...
    assert (tmp_path / decomposed).is_file() and (tmp_path / composed).is_file()
    assert (tmp_path / decomposed).stat().st_ino == (tmp_path / composed).stat().st_ino
    # ... and every string test a reader would naively write calls it missing.
    door_line = f"- {ARCS_DIRNAME}/{composed} carries what follows"
    assert stored[0] != composed
    assert composed not in door_line.replace(composed, decomposed)
    assert _nfc(stored[0]) == composed, "the one comparison that holds"
