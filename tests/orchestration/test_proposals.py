"""D155 - the RETURN path of the ``proposals`` surface, and the alarm that can be cleared.

``make describe`` advertised "receive non-solicited proposals and review them". The deposit half
worked; the return half did not exist, so eight inert drafts sat correctly filed and permanently
invisible until a project session filed a signalement about it. These tests hold three things:

* the queue COUNTS and LISTS what awaits, and goes silent when nothing does;
* the review gesture CLEARS the alarm - a counter with no way to clear it becomes a perpetual
  false alarm, the failure ``veille_ledger`` already documents in its own docstring;
* reviewing never deletes, never promotes, and never touches a byte of the body - a draft is
  hand-mined matter quoting operator-managed sources (invariant 2 / D92).

The shared frontmatter mechanics are tested through BOTH consumers on purpose: the bounded-block
regex exists because an unbounded one once rewrote a report's body, and that lesson must not be
re-learned in the copy.
"""

from __future__ import annotations

from pathlib import Path

from pytest import raises

from mnemosyne.production.frontmatter_status import set_status, status_of
from mnemosyne.production.proposals import (
    DRAFT,
    REVIEWED,
    mark_reviewed,
    open_proposal_count,
    open_proposals,
)
from mnemosyne.production.proposer import ProposalQueueReview
from mnemosyne.runtime.proposals import main, render_open

#: The body carries a ``status:`` line AT THE START OF A LINE - the exact shape that made an
#: unbounded regex rewrite a document's prose (the audit's MAJEUR on the signalements queue).
#: A first version of this fixture buried it mid-JSON, where ``^status:`` cannot match: the test
#: passed while proving nothing, and a mutation to un-bound the WRITE broke no test at all.
_BODY = """# Watch - a book

## Finding 1

The watcher quotes a record's frontmatter here, as a block:

status: draft
kind: hypothesis

This line belongs to the BODY and must never be rewritten.
"""


def _draft(root: Path, name: str, *, status: str = DRAFT, body: str = _BODY) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    path = root / name
    path.write_text(
        f'---\nsource: "a-book.md"\ndate: "2026-07-20"\nstatus: {status}\n---\n\n{body}'
    )
    return path


# --- the queue ----------------------------------------------------------------------------
def test_an_empty_or_absent_queue_is_silent(tmp_path: Path) -> None:
    assert open_proposals(tmp_path / "nowhere") == ()
    assert open_proposal_count(tmp_path / "nowhere") == 0
    assert ProposalQueueReview(lambda: 0).scan() == ()  # silence, not a nudge


def test_drafts_are_counted_across_sub_queues(tmp_path: Path) -> None:
    _draft(tmp_path / "veille", "a.md")
    _draft(tmp_path / "veille", "b.md")
    _draft(tmp_path / "autre", "c.md")
    assert open_proposal_count(tmp_path) == 3


def test_reviewed_drafts_leave_the_queue(tmp_path: Path) -> None:
    kept = _draft(tmp_path / "veille", "a.md")
    _draft(tmp_path / "veille", "b.md", status=REVIEWED)
    assert open_proposals(tmp_path) == (kept,)


def test_navigation_files_are_not_proposals(tmp_path: Path) -> None:
    _draft(tmp_path / "veille", "README.md")
    assert open_proposal_count(tmp_path) == 0


# --- the nudge ----------------------------------------------------------------------------
def test_the_nerve_reports_how_many_and_never_the_content(tmp_path: Path) -> None:
    """Invariant 22, and it bites hardest here: a draft's body is mined from operator-managed library."""
    path = _draft(tmp_path / "veille", "secret-book.md", body="# A very personal title\n")
    drafts = ProposalQueueReview(lambda: open_proposal_count(tmp_path)).scan()

    assert len(drafts) == 1
    summary = drafts[0].summary
    assert "1 inert proposal awaits" in summary
    assert "make proposals" in summary
    assert "secret-book" not in summary and "personal" not in summary
    assert str(path) not in summary


def test_the_nudge_can_actually_be_cleared(tmp_path: Path) -> None:
    """A counter with no way to clear it is a perpetual false alarm - the failure veille_ledger
    documents. Reviewing must make the nerve go quiet, or the whole source is noise."""
    path = _draft(tmp_path / "veille", "a.md")
    count = lambda: open_proposal_count(tmp_path)  # noqa: E731 - a one-line probe reads better inline
    assert ProposalQueueReview(count).scan() != ()

    mark_reviewed(path)
    assert ProposalQueueReview(count).scan() == ()


# --- the review gesture -------------------------------------------------------------------
def test_reviewing_preserves_the_body_byte_for_byte(tmp_path: Path) -> None:
    """The body quotes operator's sources and contains a literal ``status:`` line inside a JSON block -
    the exact shape that once made an unbounded regex rewrite a document's prose."""
    path = _draft(tmp_path / "veille", "a.md")
    before = path.read_text().split("---\n", 2)[2]

    mark_reviewed(path)

    assert status_of(path) == REVIEWED
    assert path.read_text().split("---\n", 2)[2] == before
    assert "status: draft\nkind: hypothesis" in path.read_text()  # body line untouched


def test_reviewing_is_idempotent_and_never_deletes(tmp_path: Path) -> None:
    path = _draft(tmp_path / "veille", "a.md")
    mark_reviewed(path)
    mark_reviewed(path)  # second pass must not raise nor re-stamp
    assert path.is_file()
    assert path.read_text().count("status:") == 2  # the field + the one quoted in the body


def test_a_destroyed_frontmatter_goes_silent_rather_than_crashing(tmp_path: Path) -> None:
    """Fail-OPEN: draining a queue must never be the thing that breaks a session."""
    broken = tmp_path / "veille" / "a.md"
    broken.parent.mkdir(parents=True)
    broken.write_text("no frontmatter at all\nstatus: draft\n")

    assert open_proposal_count(tmp_path) == 0
    assert mark_reviewed(broken) == broken  # returns, does not raise


def test_set_status_refuses_to_invent_structure(tmp_path: Path) -> None:
    """The shared helper is loud where the queue is quiet: silently adding a frontmatter block to a
    human's file would be inventing structure nobody wrote."""
    orphan = tmp_path / "a.md"
    orphan.write_text("just plain text\n")
    with raises(ValueError):
        set_status(orphan, REVIEWED)


# --- the CLI ------------------------------------------------------------------------------
def test_render_lists_paths_grouped_never_a_digest(tmp_path: Path) -> None:
    _draft(tmp_path / "veille", "a.md", body="# A very specific hypothesis\n")
    out = render_open(open_proposals(tmp_path))

    assert "veille/" in out and "a.md" in out
    assert "very specific hypothesis" not in out  # a digest would become the thing being judged
    assert "NEVER 'promoted'" in out


def test_render_is_honest_when_empty(tmp_path: Path) -> None:
    assert "No proposal is awaiting review" in render_open(open_proposals(tmp_path))


def test_cli_marks_one_reviewed(tmp_path: Path) -> None:
    path = _draft(tmp_path / "veille", "a.md")
    assert main(["--revu", str(path)], root=tmp_path) == 0
    assert status_of(path) == REVIEWED


def test_cli_refuses_a_missing_file_rather_than_doing_nothing(tmp_path: Path) -> None:
    assert main(["--revu", str(tmp_path / "absent.md")], root=tmp_path) == 2
    assert main(["--revu"], root=tmp_path) == 2


# --- the WIRING, not just the module ------------------------------------------------------
def test_run_tick_actually_surfaces_the_queue(tmp_path: Path) -> None:
    """The lesson of the previous audit (MAJEUR-1): testing a module while leaving its WIRING
    uncovered means a mutation to the identity breaks nothing. The tick derives the queue path
    from ``knowledge_root`` on purpose - a hardcoded default would count the REAL repo's drafts
    from inside this tmp_path."""
    from mnemosyne.runtime.tick import run_tick

    before = run_tick(knowledge_root=tmp_path, repo_root=tmp_path)
    assert not any("inert proposal" in p.summary for p in before)

    _draft(tmp_path / "proposals" / "veille", "a.md")
    after = run_tick(knowledge_root=tmp_path, repo_root=tmp_path)

    surfaced = [p for p in after if "inert proposal" in p.summary]
    assert len(surfaced) == 1
    assert "1 inert proposal awaits" in surfaced[0].summary
    assert surfaced[0].reviewed is False  # inert until operator reviews it (propose, never impose)
