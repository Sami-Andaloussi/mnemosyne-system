"""Lock-test for the skill-creator scaffolder (system/skills/skill-creator/new_skill.py).

The scaffolder is the skill-creator's OWN fail-closed guard (lesson 3, D100): it writes a DRAFT
all-or-nothing and REFUSES rather than half-scaffold or overwrite. A skill that preaches fail-closed
discipline must exercise its own -- so these tests pin slugify's name-lint contract and the
all-or-nothing write. Brick-free (pure filesystem in a tmp repo)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

from _invariants import REPO_ROOT
from mnemosyne.production.skills import _NAME_RE, SCAFFOLD_MARKERS, _scaffold_verdict

_SCRIPT = REPO_ROOT / "system" / "skills" / "skill-creator" / "new_skill.py"
_spec = importlib.util.spec_from_file_location("new_skill_script", _SCRIPT)
assert _spec and _spec.loader
new_skill = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(new_skill)


def test_slugify_is_deterministic_kebab_that_passes_the_name_lint() -> None:
    # accents folded, punctuation/space -> single hyphens, no leading/trailing/doubled hyphen.
    assert new_skill.slugify("Resume d'un Livre !") == "resume-d-un-livre"
    assert new_skill.slugify("  C++ & F#  ") == "c-f"  # symbol runs collapse to a hyphen, then trim
    assert new_skill.slugify("") == "nouveau-skill"  # empty -> stable fallback, never ""
    capped = new_skill.slugify("a" * 100, max_len=40)
    assert len(capped) <= 40 and not capped.endswith("-")
    # THE contract: whatever slugify emits passes the frontmatter name lint BY CONSTRUCTION.
    for text in ("Blurb Generator", "Resume!!", "  ---  ", "MiXeD Case 123", "eaea" * 30):
        assert _NAME_RE.match(new_skill.slugify(text))


def _make_tmp_repo(tmp_path: Path) -> None:
    (tmp_path / "system" / "skills").mkdir(parents=True)
    (tmp_path / "system" / "lib" / "mnemosyne" / "production").mkdir(parents=True)
    (tmp_path / "tests").mkdir(parents=True)
    (tmp_path / "Makefile").write_text(".PHONY: foo\n\nfoo:\n\techo hi\n", encoding="utf-8")


def test_scaffold_writes_all_four_files_and_the_makefile_target(tmp_path, monkeypatch) -> None:
    _make_tmp_repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    need = "generate a short plain-language blurb for a book"
    assert new_skill.main([need]) == 0
    name = new_skill.slugify(need)
    mod = name.replace("-", "_")
    assert (tmp_path / "system" / "skills" / name / "SKILL.md").exists()
    assert (tmp_path / "system" / "skills" / name / f"{name}_run.py").exists()
    assert (tmp_path / "system" / "lib" / "mnemosyne" / "production" / f"{mod}.py").exists()
    assert (tmp_path / "tests" / f"test_{mod}.py").exists()
    makefile = (tmp_path / "Makefile").read_text(encoding="utf-8")
    assert f"\n{name}:" in makefile  # a target block was appended
    assert name in makefile.splitlines()[0]  # and the name was added to the .PHONY line


def test_scaffold_is_fail_closed_all_or_nothing(tmp_path, monkeypatch) -> None:
    _make_tmp_repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    need = "another skill idea"
    name = new_skill.slugify(need)
    mod = name.replace("-", "_")
    # ONE of the four targets already exists (the code home) -> the scaffolder must write NOTHING.
    home = tmp_path / "system" / "lib" / "mnemosyne" / "production" / f"{mod}.py"
    home.write_text("# pre-existing\n", encoding="utf-8")
    makefile_before = (tmp_path / "Makefile").read_text(encoding="utf-8")
    assert new_skill.main([need]) == 1
    assert not (tmp_path / "system" / "skills" / name).exists()  # skill dir NOT created
    assert not (tmp_path / "tests" / f"test_{mod}.py").exists()  # test NOT created
    assert home.read_text(encoding="utf-8") == "# pre-existing\n"  # untouched
    assert (tmp_path / "Makefile").read_text(
        encoding="utf-8"
    ) == makefile_before  # Makefile untouched


def test_scaffold_refuses_a_rerun_and_writes_nothing(tmp_path, monkeypatch) -> None:
    # the most common fail-closed case: re-running the SAME scaffold. The skill dir now exists ->
    # REFUSE, exit non-zero, and change nothing (no duplicated Makefile target, no clobber).
    _make_tmp_repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    assert new_skill.main(["some need", "dup-skill"]) == 0
    makefile_after_first = (tmp_path / "Makefile").read_text(encoding="utf-8")
    assert new_skill.main(["some need", "dup-skill"]) != 0
    assert (tmp_path / "Makefile").read_text(
        encoding="utf-8"
    ) == makefile_after_first  # no 2nd target


def test_scaffold_refuses_a_preexisting_makefile_target_and_writes_nothing(
    tmp_path, monkeypatch
) -> None:
    # a Makefile target of the same name already present (even with no skill dir / home / test yet)
    # must abort BEFORE any write - the new target text is computed pre-write, so the guard holds.
    _make_tmp_repo(tmp_path)
    (tmp_path / "Makefile").write_text(
        ".PHONY: foo clash\n\nfoo:\n\techo hi\n\nclash:\n\techo existing\n", encoding="utf-8"
    )
    makefile_before = (tmp_path / "Makefile").read_text(encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    assert new_skill.main(["some need", "clash"]) != 0
    assert not (tmp_path / "system" / "skills" / "clash").exists()  # nothing written
    assert not (tmp_path / "system" / "lib" / "mnemosyne" / "production" / "clash.py").exists()
    assert not (tmp_path / "tests" / "test_clash.py").exists()
    assert (tmp_path / "Makefile").read_text(encoding="utf-8") == makefile_before  # untouched


def test_main_reports_usage_with_no_need_and_no_name() -> None:
    assert new_skill.main([""]) == 1


def test_scaffold_markers_are_never_retyped_in_the_scaffolder_source() -> None:
    # LESSON 1, applied to the scaffolder itself. These 3 strings are what `_scaffold_verdict` greps
    # for to answer "is this still a bare scaffold?". The scaffolder USED to retype them under a
    # comment claiming it imported them -- a rename in skills.py would then have made a WHOLLY EMPTY
    # skeleton report scaffold_only=False ("not a scaffold"), silently: the body-length fallback does
    # not catch it (a bare stub's SKILL.md is ~1126 chars, 3.75x the 300 floor).
    #
    # This asserts the property DIRECTLY -- the literals do not appear in the source -- rather than
    # `_MARKER_DESCRIBE is SCAFFOLD_MARKERS[0]`, which reads like a lock but is TAUTOLOGICAL: the
    # unpack DEFINES that identity, so it can never fail. (It would also have rested on CPython not
    # interning these strings: rename a marker to `TODO_skill_creator_decrire` -- all name chars --
    # and a retyped copy would be interned to the same object, turning that assert silently green on
    # the very drift it guards.) Source-level, so no interning or import order can fool it.
    source = _SCRIPT.read_text(encoding="utf-8")
    body = "\n".join(
        line
        for line in source.splitlines()
        if "from mnemosyne.production.skills import" not in line
    )
    for marker in SCAFFOLD_MARKERS:
        assert marker not in body, f"marker retyped in new_skill.py instead of imported: {marker!r}"
    # the unpack is positional: a change to the tuple's LENGTH must break the import loudly.
    assert len(SCAFFOLD_MARKERS) == 3


def test_a_bare_scaffold_is_still_detected_as_a_scaffold_end_to_end(tmp_path, monkeypatch) -> None:
    # The end-to-end consequence of the test above: what the scaffolder WRITES, the detector must
    # still call a scaffold. This is what silently broke when the two homes could drift.
    _make_tmp_repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    assert new_skill.main(["a need that is never implemented", "barebones"]) == 0
    skill_md = (tmp_path / "system" / "skills" / "barebones" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    home = (tmp_path / "system" / "lib" / "mnemosyne" / "production" / "barebones.py").read_text(
        encoding="utf-8"
    )
    only, why = _scaffold_verdict(skill_md, impl_texts={"barebones.py": home})
    assert only is True, why  # a freshly-scaffolded DRAFT is, by definition, scaffold-only
