"""Parentheses (C8-c) - a detour opens beside a plan, and the RETURN is what is guaranteed.

The measured defect these tests exist against is NOT storage. Acme Research's parenthesis was already a file
with a status, it IS declared closed, and a decision it had taken never reached ``chantiers.yaml``.
So the cases that matter most below are the two refusals - an opening that does not declare what
must come back, and a closure that does not name AND locate what did - plus the third that would
have made both cosmetic: re-closing must not silently swallow a second return.

Brick-free, driven over ``tmp_path``. Every test here was proven to BITE by sabotaging the code it
covers and watching it go red (with a fresh ``PYTHONPYCACHEPREFIX``: a sabotage that preserves the
file's SIZE can otherwise let Python run a stale ``.pyc``, since invalidation is ``(mtime, size)``
to the second - a mutant read as "survived" that was never executed).
"""

from __future__ import annotations

import unicodedata
from datetime import date
from pathlib import Path

import pytest

from mnemosyne.production import parentheses as par
from mnemosyne.production.parentheses import ParentheseRefusee
from mnemosyne.production.plan_format import ARCS_DIRNAME, read_plan
from mnemosyne.production.plan_registry import read_plan_tree
from mnemosyne.production.proposer import ParentheseReview
from mnemosyne.runtime.parentheses import main, render_open
from mnemosyne.runtime.tick import run_tick

_PLAN = "\n".join(
    [
        "# PLAN - a project",
        "",
        "> **Cap** : prove the parenthesis protocol",
        "",
        "## To do",
        "",
        "- **A1** \U0001F504 the main workstream",
        "",
    ]
)


#: A plan in its D166 shape - a DOOR that names the cap and INDEXES its arcs, carrying no item of its
#: own. Deliberately item-free: that is what makes "read the door only" answer False about a plan
#: that points perfectly, and a fixture without that structure could not test the reader at all.
_DOOR = "\n".join(
    [
        "# PLAN - a project",
        "",
        "> **Cap** : prove the parenthesis protocol",
        "",
        "## The arcs",
        "",
        "- `plan/arc-c.md` - the current workstream",
        "",
    ]
)

_ARC = "\n".join(
    [
        "## Arc C - the current workstream",
        "",
        "- **C1** \U0001F504 the work under way",
        "",
    ]
)


def _tree(tmp_path: Path, plan_text: str = _PLAN) -> tuple[Path, Path]:
    """A repo-shaped temp tree: ``(repo_root, plan_path)`` - the plan really exists on disk."""
    plan = tmp_path / "docs" / "PLAN.md"
    plan.parent.mkdir(parents=True, exist_ok=True)
    plan.write_text(plan_text, encoding="utf-8")
    return tmp_path, plan


def _plan_folder(tmp_path: Path, arcs: dict[str, str], *, door: str = _DOOR) -> Path:
    """Turn the temp tree's plan into a FOLDER: the door, plus ``plan/<name>.md`` beside it.

    ``arcs`` maps a path relative to ``plan/`` to its bytes - a mapping rather than a list so one
    case can name a HOSTILE arc (a space, a ``:``, accents in NFD) without a second fixture.
    """
    door_path = tmp_path / "docs" / "PLAN.md"
    door_path.parent.mkdir(parents=True, exist_ok=True)
    door_path.write_text(door, encoding="utf-8")
    for relative, body in arcs.items():
        arc = door_path.parent / ARCS_DIRNAME / relative
        arc.parent.mkdir(parents=True, exist_ok=True)
        arc.write_text(body, encoding="utf-8")
    return door_path


def _opened(tmp_path: Path, *, titre: str = "the dependency field", **kwargs: str) -> Path:
    repo, _ = _tree(tmp_path)
    fields: dict[str, str] = {
        "plan": "docs/PLAN.md",
        "item": "C8",
        "pourquoi": "a question comes up",
        "retour_attendu": "a decision written into the plan",
    }
    fields.update(kwargs)
    return par.open_parenthese(
        titre, root=repo / "docs" / "parentheses", repo_root=repo, today=date(2026, 7, 28), **fields
    )


# ---- the opening refusal: what must come back is declared, or nothing opens -----------
def test_opening_without_a_declared_return_is_refused(tmp_path: Path) -> None:
    """THE central barrier. Acme Research's parenthesis closed cleanly and left a decision unexecuted; the
    only moment at which nobody yet has an interest in "what comes back" being vague is the opening.
    Refused in CODE, not discouraged in a template (D100 / inv. 17)."""
    repo, _ = _tree(tmp_path)
    with pytest.raises(ParentheseRefusee) as refusal:
        par.open_parenthese(
            "a detour",
            plan="docs/PLAN.md",
            item="C8",
            pourquoi="because",
            retour_attendu="   ",  # whitespace is not a declaration
            root=repo / "docs" / "parentheses",
            repo_root=repo,
        )
    assert "RETOUR_ATTENDU=" in str(refusal.value)  # the message names the GESTE, not a function
    assert not (repo / "docs" / "parentheses").exists()  # refused => nothing was written at all


def test_opening_against_a_plan_that_does_not_exist_is_refused(tmp_path: Path) -> None:
    """A parenthesis pointing at a missing plan is orphaned at birth: it can never return anywhere.
    Checked rather than trusted - a typo'd path yields a perfectly well-formed, useless file."""
    repo, _ = _tree(tmp_path)
    with pytest.raises(ParentheseRefusee) as refusal:
        par.open_parenthese(
            "a detour",
            plan="docs/A_PLAN_THAT_DOES_NOT_EXIST.md",
            item="C8",
            pourquoi="because",
            retour_attendu="something",
            root=repo / "docs" / "parentheses",
            repo_root=repo,
        )
    assert "does not exist" in str(refusal.value)


def test_an_opened_parenthese_carries_its_debt_in_its_frontmatter(tmp_path: Path) -> None:
    """The state is the file's own frontmatter - one file, one truth, nothing to drift out of sync.
    The declared return in particular must be MACHINE-readable, not buried in the prose a human is
    free to rewrite."""
    path = _opened(tmp_path)
    assert path.name == "2026-07-28-the-dependency-field.md"  # dated => chronological on disk
    read = par.read_parenthese(path)
    assert read.status == par.OPEN
    assert read.retour_attendu == "a decision written into the plan"
    assert read.plan == "docs/PLAN.md" and read.item == "C8"


def test_a_hostile_title_survives_the_frontmatter_round_trip(tmp_path: Path) -> None:
    """A title carrying quotes and a newline must not break the block that every reader parses."""
    path = _opened(tmp_path, titre='he says "ok"\nand jumps')
    assert par.read_parenthese(path).titre == 'he says "ok" and jumps'
    assert par.read_parenthese(path).status == par.OPEN


# ---- the closing refusals: named AND located ------------------------------------------
def test_closing_without_naming_the_return_is_refused(tmp_path: Path) -> None:
    """The second half of the guarantee: a detour that goes quiet without saying what came back is
    the file-shaped version of the "Backlog UI" section - 16 bullets, no verifiable return."""
    path = _opened(tmp_path)
    with pytest.raises(ParentheseRefusee) as refusal:
        par.close_parenthese(path, retour="", dans="docs/PLAN.md", repo_root=tmp_path)
    assert "RETOUR=" in str(refusal.value)
    assert par.read_parenthese(path).status == par.OPEN  # refused => still open, nothing flipped


def test_closing_without_locating_the_return_is_refused(tmp_path: Path) -> None:
    """Naming alone would have let Acme Research's defect through VERBATIM: "the dependency field was
    decided" is a name, and the field still never reached ``chantiers.yaml``."""
    path = _opened(tmp_path)
    with pytest.raises(ParentheseRefusee) as refusal:
        par.close_parenthese(path, retour="the field has been decided", dans="", repo_root=tmp_path)
    assert "DANS=" in str(refusal.value)
    assert par.read_parenthese(path).status == par.OPEN


def test_closing_into_a_destination_that_does_not_exist_is_refused(tmp_path: Path) -> None:
    """A return "landed" in a file that is not there is not landed. This is what makes ``dans`` a
    check rather than a second free-text field nobody verifies."""
    path = _opened(tmp_path)
    with pytest.raises(ParentheseRefusee) as refusal:
        par.close_parenthese(path, retour="decided", dans="docs/NOWHERE.md", repo_root=tmp_path)
    assert "does not exist" in str(refusal.value)
    assert par.read_parenthese(path).status == par.OPEN


def test_a_parenthese_cannot_be_its_own_destination(tmp_path: Path) -> None:
    """The obvious way around the check, closed: a return that stays in the parenthesis never came
    back to the plan. Closing a case is not closing the class - this is the class's other door."""
    path = _opened(tmp_path)
    with pytest.raises(ParentheseRefusee) as refusal:
        par.close_parenthese(
            path, retour="it is written right here", dans=str(path), repo_root=tmp_path
        )
    assert "its own destination" in str(refusal.value)
    assert par.read_parenthese(path).status == par.OPEN


def test_closing_records_the_return_and_never_deletes(tmp_path: Path) -> None:
    """Invariant 2: the status flips, the file stays, and the return is written INTO it - so the
    closed parenthesis is itself the evidence that its debt was paid."""
    path = _opened(tmp_path)
    closed = par.close_parenthese(
        path,
        retour="no dependency field, the order is enough",
        dans="docs/PLAN.md",
        repo_root=tmp_path,
        today=date(2026, 7, 29),
    )
    assert path.exists() and closed.status == par.CLOSED
    text = path.read_text(encoding="utf-8")
    assert 'retour: "no dependency field, the order is enough"' in text
    assert 'retour_dans: "docs/PLAN.md"' in text and 'ferme_le: "2026-07-29"' in text
    assert par.open_parentheses(path.parent) == ()  # the queue goes quiet on its own


def test_reclosing_is_refused_rather_than_silently_ignored(tmp_path: Path) -> None:
    """Its siblings (``mark_handled``, ``mark_reviewed``) are idempotent; here that would be a SILENT
    LOSS - a second closure carrying a DIFFERENT return would report success and record nothing,
    which is the exact shape of the defect this module exists to prevent."""
    path = _opened(tmp_path)
    par.close_parenthese(path, retour="first return", dans="docs/PLAN.md", repo_root=tmp_path)
    with pytest.raises(ParentheseRefusee) as refusal:
        par.close_parenthese(
            path, retour="a SECOND, completely different return", dans="docs/PLAN.md", repo_root=tmp_path
        )
    assert "closed twice" in str(refusal.value)
    assert "a SECOND" not in path.read_text(encoding="utf-8")  # nothing was overwritten


# ---- the pointer: one line, and it must not break the plan ----------------------------
def test_the_pointer_is_a_readable_plan_item(tmp_path: Path) -> None:
    """The line we hand a human to paste must be one their plan can ACCEPT. An unreadable plan is a
    refused commit (the ``pre-commit`` barrier), for a line we supplied."""
    path = _opened(tmp_path)
    line = par.pointer_line(par.read_parenthese(path), plan_text=_PLAN, repo_root=tmp_path)
    reading = read_plan(_PLAN + line + "\n")
    assert reading.readable and reading.problems == ()
    (pointer,) = [item for item in reading.items if item.ident.startswith("P")]
    assert pointer.status == "en_cours" and path.name in pointer.title


def test_the_pointer_identity_never_collides_with_one_the_plan_already_uses(tmp_path: Path) -> None:
    """Computed off the plan's own reader, never a fixed ``P1``: a duplicate identity is refused as
    ``id_duplique``, so a fixed one would make the SECOND parenthesis break the plan."""
    path = _opened(tmp_path)
    busy = _PLAN + "- **P1** \U00002B1C a parenthesis already pointed at\n- **P7** \U00002705 another one\n"
    line = par.pointer_line(par.read_parenthese(path), plan_text=busy, repo_root=tmp_path)
    assert line.startswith("- **P8**")
    assert read_plan(busy + line + "\n").problems == ()


def test_the_pointer_carries_the_address_not_the_content(tmp_path: Path) -> None:
    """What keeps the plan clean: the line says a detour runs, what it is about, and where it lives -
    and deliberately NOT the expected return, whose hand-copied second copy is the rot ``plan_format``
    was built against."""
    path = _opened(tmp_path, retour_attendu="A VERY SPECIFIC SENTENCE")
    line = par.pointer_line(par.read_parenthese(path), plan_text=_PLAN, repo_root=tmp_path)
    assert "A VERY SPECIFIC SENTENCE" not in line
    assert len(line.splitlines()) == 1  # one line, always


# ---- the orphan flag: an open detour nothing points at --------------------------------
def test_a_parenthese_the_plan_does_not_mention_is_flagged(tmp_path: Path) -> None:
    """An open detour nothing designates is invisible from the plan - the waste user named. Reported,
    never blocked: pasting the pointer is a human gesture, and a tool that refused work over a
    missing paste would be a door slower than the wall."""
    path = _opened(tmp_path)
    assert par.plan_points_at(par.read_parenthese(path), repo_root=tmp_path) is False
    out = render_open((path,), repo_root=tmp_path)
    assert "the plan does not point at it" in out


def test_a_parenthese_the_plan_points_at_is_not_flagged(tmp_path: Path) -> None:
    """The other side of the same measurement - without it, the flag could be a constant ``False``."""
    path = _opened(tmp_path)
    plan = tmp_path / "docs" / "PLAN.md"
    plan.write_text(
        plan.read_text(encoding="utf-8")
        + par.pointer_line(par.read_parenthese(path), plan_text=_PLAN, repo_root=tmp_path)
        + "\n",
        encoding="utf-8",
    )
    assert par.plan_points_at(par.read_parenthese(path), repo_root=tmp_path) is True
    assert "does not point at it" not in render_open((path,), repo_root=tmp_path)


def test_an_unreadable_plan_is_a_third_outcome_not_an_accusation(tmp_path: Path) -> None:
    """Three outcomes, never two. Saying ``False`` for a plan that vanished would accuse a parenthesis
    for someone else's missing file, and an accusation nobody can act on is worse than a silence
    somebody can measure."""
    path = _opened(tmp_path)
    (tmp_path / "docs" / "PLAN.md").unlink()
    assert par.plan_points_at(par.read_parenthese(path), repo_root=tmp_path) is None
    assert "plan unreadable or not found" in render_open((path,), repo_root=tmp_path)


# ---- the plan is a FOLDER now (D166): door + plan/<arc>.md ----------------------------
def test_a_pointer_that_lives_in_an_ARC_is_not_a_missing_pointer(tmp_path: Path) -> None:
    """THE rupture this arc closes. A plan is a folder - a door plus one file per arc - and the
    pointer of a parenthesis is pasted where the WORK sits, which is an arc, never the door. Reading
    the door alone answers "the plan does not point at it" about a
    plan that points at it perfectly: a false accusation manufactured by the format's own shape, on
    every plan that adopts it. It is also the accusation nobody can act on - the paste is already
    there."""
    path = _opened(tmp_path)
    parenthese = par.read_parenthese(path)
    line = par.pointer_line(parenthese, plan_text=_DOOR, repo_root=tmp_path)
    _plan_folder(tmp_path, {"arc-c.md": _ARC + line + "\n"})
    assert par.plan_points_at(parenthese, repo_root=tmp_path) is True
    assert "does not point at it" not in render_open((path,), repo_root=tmp_path)


def test_the_pointer_identity_never_collides_with_one_living_in_an_ARC(tmp_path: Path) -> None:
    """Its sibling above proves this against the door; the folder form REOPENED it, in silence. The
    ``P<n>`` of every past parenthesis sits in an arc, and the caller holding the plan holds ONE path
    - so an identity computed on the door alone is free of the door and free of nothing else.
    ``read_plan_tree`` threads one ``ident_seen`` through door AND arcs, so the collision is a real
    ``id_duplique``: a plan the reader calls unreadable, and a refused commit for a line WE handed
    out. The consequence is asserted, not just the number."""
    path = _opened(tmp_path)
    door = _plan_folder(
        tmp_path,
        {
            "arc-c.md": _ARC
            + "- **P1** \U00002705 Parenthesis closed - a detour returned  -  `docs/parentheses/old.md`\n"
            + "- **P4** \U0001F504 Parenthesis - a detour under way  -  `docs/parentheses/other.md`\n"
        },
    )
    line = par.pointer_line(
        par.read_parenthese(path), plan_text=door.read_text(encoding="utf-8"), repo_root=tmp_path
    )
    assert line.startswith("- **P5**")
    door.write_text(door.read_text(encoding="utf-8") + line + "\n", encoding="utf-8")
    (whole,) = read_plan_tree(tmp_path / "docs", "witness")
    assert whole.reading is not None and whole.reading.problems == ()


def test_an_arc_whose_NAME_is_hostile_is_read_like_any_other(tmp_path: Path) -> None:
    """Synthetic paths can carry a space and a ``:``; macOS hands filenames back
    DECOMPOSED, so ``économie`` typed by an editor is not the ``économie`` the filesystem returns. An
    arc the walker cannot open is an arc whose pointer does not exist and whose identities are free -
    the false accusation AND the collision, from one invisible codepoint. Both are asserted here, on
    the same hostile name, because both new rules walk the same tree."""
    hostile = unicodedata.normalize("NFD", "arc D: économie & compagnie.md")
    path = _opened(tmp_path)
    parenthese = par.read_parenthese(path)
    body = (
        _ARC + f"- **P9** \U0001F504 Parenthesis - a detour  -  `docs/parentheses/{path.name}`\n"
    )
    _plan_folder(tmp_path, {hostile: body})
    assert par.plan_points_at(parenthese, repo_root=tmp_path) is True
    line = par.pointer_line(parenthese, plan_text=_DOOR, repo_root=tmp_path)
    assert line.startswith("- **P10**")


def test_a_plan_declared_as_a_FOLDER_is_read_through_its_door(tmp_path: Path) -> None:
    """``plan: docs`` is a shape a hand-edited frontmatter now legitimately carries - since D166 the
    plan IS the folder. ``read_text`` on a directory raises ``IsADirectoryError``, an ``OSError``, so
    the blanket catch switched the whole control OFF and answered "I do not know" about a plan
    sitting right there. Three outcomes, and each must be DECIDED: a folder with no door is the one
    that is genuinely unknowable, and it keeps ``None``."""
    path = _opened(tmp_path)
    _plan_folder(
        tmp_path, {"arc-c.md": _ARC + f"- **P1** \U0001F504 Parenthesis - `{path.name}`\n"}
    )
    dossier = par.Parenthese(
        path=path, titre="t", plan="docs", item="", retour_attendu="r", status=par.OPEN
    )
    assert par.plan_points_at(dossier, repo_root=tmp_path) is True
    (tmp_path / "no-door").mkdir()
    nowhere = par.Parenthese(
        path=path, titre="t", plan="no-door", item="", retour_attendu="r", status=par.OPEN
    )
    assert par.plan_points_at(nowhere, repo_root=tmp_path) is None


def test_an_arc_nobody_can_decode_is_a_silence_never_an_accusation(tmp_path: Path) -> None:
    """``UnicodeDecodeError`` is a ``ValueError``, which ``except OSError`` never caught: one arc of
    invalid bytes under ``plan/`` takes the tick down. Once caught, the answer must be ``None`` - the
    pointer may be sitting in exactly the file nobody could read, and an accusation nobody can act on
    is worse than a silence somebody can measure. FOUND still beats blind: a mention that IS there is
    not made less true by a file beside it that is not."""
    path = _opened(tmp_path)
    _plan_folder(tmp_path, {"arc-c.md": _ARC})
    (tmp_path / "docs" / ARCS_DIRNAME / "broken-arc.md").write_bytes(b"\xff\xfe\x00 not utf-8")
    assert par.plan_points_at(par.read_parenthese(path), repo_root=tmp_path) is None
    door = tmp_path / "docs" / "PLAN.md"
    door.write_text(
        door.read_text(encoding="utf-8") + f"- **P1** \U0001F504 `{path.name}`\n", "utf-8"
    )
    assert par.plan_points_at(par.read_parenthese(path), repo_root=tmp_path) is True


def test_a_plan_that_is_a_folder_is_still_refused_at_the_OPENING(tmp_path: Path) -> None:
    """The READER now understands a folder; the WRITER still refuses one, on purpose. The fourth
    refusal of ``open_parenthese`` guards a runtime that reads ``plan`` with ``read_text`` and falls
    back to ``plan_text=""`` - which hands out ``P1`` unconditionally. Widening the refusal here
    would open that hole in a module this change may not touch, so the refusal stands and this pins
    it: being more generous when READING than when WRITING is the choice, not an oversight."""
    repo, _ = _tree(tmp_path)
    _plan_folder(tmp_path, {"arc-c.md": _ARC})
    with pytest.raises(ParentheseRefusee) as refusal:
        par.open_parenthese(
            "a detour",
            plan="docs",
            item="C8",
            pourquoi="because",
            retour_attendu="a decision",
            root=repo / "docs" / "parentheses",
            repo_root=repo,
        )
    assert "does not exist" in str(refusal.value)


# ---- the listing (what a session actually reads) --------------------------------------
def test_the_listing_shows_the_outstanding_debt_of_each_open_detour(tmp_path: Path) -> None:
    """Unlike its siblings this render does NOT stop at paths: the declared debt is one line, and
    hiding it behind "open the file" is how 16 bullets came to have no verifiable return at all."""
    path = _opened(tmp_path, retour_attendu="the yes/no decision, written into the plan")
    out = render_open((path,), repo_root=tmp_path)
    assert "must return: the yes/no decision, written into the plan" in out
    assert "starts from: `docs/PLAN.md` · item C8" in out


def test_the_listing_is_honest_when_nothing_is_open() -> None:
    assert "No open parenthesis — nothing is lying around beside a plan." in render_open(())


def test_the_contract_doc_is_not_counted_as_a_parenthese(tmp_path: Path) -> None:
    """The README living beside them is not a detour - and a directory that never existed is simply
    empty, never an error (the tick asks this at every session start, including on a fresh clone)."""
    root = tmp_path / "docs" / "parentheses"
    root.mkdir(parents=True)
    (root / "README.md").write_text("---\nstatus: ouverte\n---\n", encoding="utf-8")
    assert par.open_parenthese_count(root) == 0
    assert par.open_parenthese_count(tmp_path / "never-used") == 0


# ---- the proposer source (how it reaches user) ----------------------------------------
def test_source_is_silent_when_no_detour_is_running() -> None:
    assert ParentheseReview(lambda: 0).scan() == ()  # silence is correct - the normal state


def test_source_reports_a_count_never_a_title() -> None:
    """Invariant 22 / D66: a detour is opened from inside whatever was being worked, and its title
    can name it. The count and the remedy cross; nothing else does."""
    (draft,) = ParentheseReview(lambda: 3).scan()
    assert "3 parenthèses are still open" in draft.summary
    assert "make parentheses" in draft.summary


# ---- the CLI + the wiring (and its hermeticity) ---------------------------------------
def test_cli_refuses_to_open_without_a_declared_return(tmp_path: Path, capsys, monkeypatch) -> None:
    """The refusal must reach the SHELL as a non-zero code: a control that prints without exiting
    non-zero is a comment, not a barrier (measured in this repo - a ``print`` returned 0 and the
    ``&&`` behind it let the commit through)."""
    repo, _ = _tree(tmp_path)
    monkeypatch.setenv("MNEMO_P_TITRE", "a detour")
    monkeypatch.setenv("MNEMO_P_PLAN", "docs/PLAN.md")
    monkeypatch.delenv("MNEMO_P_RETOUR_ATTENDU", raising=False)
    assert main(["--ouvrir"], root=repo / "docs" / "parentheses", repo_root=repo) == 2
    assert "RETOUR_ATTENDU=" in capsys.readouterr().err


def test_cli_opens_from_the_environment_not_the_shell(tmp_path: Path, capsys, monkeypatch) -> None:
    """``make parenthese-ouvrir`` passes free text through ``MNEMO_P_*`` so backticks or ``$(...)``
    in a title are never interpolated into a shell recipe."""
    repo, _ = _tree(tmp_path)
    monkeypatch.setenv("MNEMO_P_TITRE", "`echo pwned` a detour")
    monkeypatch.setenv("MNEMO_P_PLAN", "docs/PLAN.md")
    monkeypatch.setenv("MNEMO_P_RETOUR_ATTENDU", "a decision")
    assert main(["--ouvrir"], root=repo / "docs" / "parentheses", repo_root=repo) == 0
    out = capsys.readouterr().out
    assert (
        "Parenthesis opened:" in out and "- **P1** \U0001F504" in out
    )  # the line to paste is printed
    (filed,) = par.open_parentheses(repo / "docs" / "parentheses")
    assert "echo-pwned" in filed.name  # inert text in a filename, never a command


def test_cli_refuses_to_close_without_the_return(tmp_path: Path, capsys, monkeypatch) -> None:
    path = _opened(tmp_path)
    monkeypatch.setenv("MNEMO_P_FICHIER", str(path))
    monkeypatch.setenv("MNEMO_P_DANS", "docs/PLAN.md")
    monkeypatch.delenv("MNEMO_P_RETOUR", raising=False)
    assert main(["--fermer"], root=path.parent, repo_root=tmp_path) == 2
    assert "RETOUR=" in capsys.readouterr().err
    assert par.read_parenthese(path).status == par.OPEN


def test_cli_closes_and_hands_back_the_line_the_plan_should_now_carry(
    tmp_path: Path, capsys, monkeypatch
) -> None:
    """A plan still showing for a closed parenthesis lies at exactly the moment the protocol claims
 to have worked - so the closure hands back the replacement line."""
    path = _opened(tmp_path)
    monkeypatch.setenv("MNEMO_P_FICHIER", str(path))
    monkeypatch.setenv("MNEMO_P_RETOUR", "decision: no field needed")
    monkeypatch.setenv("MNEMO_P_DANS", "docs/PLAN.md")
    assert main(["--fermer"], root=path.parent, repo_root=tmp_path) == 0
    out = capsys.readouterr().out
    assert "Parenthesis closed:" in out and "\U00002705 Parenthesis closed" in out
    assert "decision: no field needed" in out


def test_tick_surfaces_an_open_parenthese_from_the_injected_tree(tmp_path: Path) -> None:
    """The tick derives the directory from ``repo_root``, so a test that isolates the tree isolates
    this source too - a hardcoded default would count the REAL repo's detours from inside tmp_path."""
    assert not any(
        "parenthèse" in p.summary for p in run_tick(knowledge_root=tmp_path, repo_root=tmp_path)
    )
    _opened(tmp_path)
    proposals = run_tick(knowledge_root=tmp_path, repo_root=tmp_path)
    assert any("1 parenthèse is still open" in p.summary for p in proposals)
