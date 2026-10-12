"""The imposed plan format — read, refuse, and above all say what was NOT read.

Two families here. The first pins the grammar. The second is a REGRESSION AGAINST THE REAL CORPUS:
five plans written in this repo before the format existed, by different agents, in three different
projects. They are the non-derived reference — a format proven only against the file it was extracted
from proves nothing at all. One of them (``PLAN_INCARNATION.md``) already killed a candidate rule:
an earlier reader accused its 14 prose bullets of being malformed items. A catch rate without its
false-kill rate is a wall, so that document is now a permanent control.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from mnemosyne.production.plan_format import (
    DOOR_FILENAMES,
    _MISSING_SENTENCE,
    _field_declares,
    _field_key,
    _FIELD_BY_KEY,
    FIELD_MARKER_RE,
    ROLE_PLAN,
    is_readable,
    PLAN_FILENAME,
    STATUS_BY_GLYPH,
    STATUS_LABEL,
    PlanReading,
    _is_glyph_shaped,
    read_plan,
)

REPO = Path(__file__).resolve().parents[2]

#: Plans that predate the format. ``PLAN_INCARNATION`` / the sibling project's ``STATE.md`` are the CONTROL:
#: nothing in them tries to be an item, so any refusal raised on them is a false accusation, full
#: stop.
#: **`ROADMAP.md` REMOVED on 2026-08-15 (delegated audit, found on the margin of C2), NOT
#: REPLACED BY `PLAN.md` — an earlier correction had done that, and it was WRONG.** The sibling project moved to
#: the FOLDER form: `PLAN.md` is now the REAL gate of its REAL plan (`plan/`, ~160 indexed arcs),
#: no longer at all a prose document that "predates the format". Substituting it for `ROADMAP.md`
#: raised 160 `arc_hors_index` on the first real measurement — the very category this corpus
#: exists to exclude. `ROADMAP.md` has no successor in that role: the sibling project no longer has a
#: "before the format" document at that spot, it adopted the format. Corpus reduced to TWO, with
#: the reason written down rather than silence — *removing a dead member is not emptying it in
#: silence, it is naming that it no longer has a referent.*
CONTROL_PLANS = (
    "docs/governance/PLAN_INCARNATION.md",
    "projects/saas/Sibling Research/STATE.md",
)

#: THE FROZEN NAME of the control corpus — the same freeze ``GUILTY_NAMES`` and ``INNOCENT_NAMES``
#: carry, and the one table that did not have it. Measured: ``CONTROL_PLANS = ()`` left the suite
#: **GREEN** (2267 passed, three parametrisations fewer, zero failures). A corpus that can be emptied
#: without a word is not a control, it is a comment — and this one is the only non-derived reference
#: the format has, the five documents written BEFORE the format existed.
CONTROL_NAMES: frozenset[str] = frozenset(
    {
        "docs/governance/PLAN_INCARNATION.md",
        "projects/saas/Sibling Research/STATE.md",
    }
)

#: ``projects/`` is gitignored BY DESIGN (a separate git repo, personal content), so it is simply
#: absent from a fresh clone. Three tests here used to die with ``FileNotFoundError`` on such a
#: clone rather than skipping — which meant the control corpus only ever ran on ONE machine, and a
#: guarantee that runs on one machine is a guarantee nobody else inherits. Skipped, never silently
#: dropped: :data:`VERSIONED_WITNESSES` and :data:`PROJECT_WITNESSES` name what each half must still
#: contain, and the two tests beside them fail if either half stops being walked.
HAS_PROJECTS = (REPO / "projects").is_dir()
needs_projects = pytest.mark.skipif(
    not HAS_PROJECTS,
    reason="projects/ is gitignored by design — absent from a fresh clone (D166 / C20-5)",
)

#: ``HAS_PROJECTS`` asks whether the DIRECTORY is there, and ``projects/.gitkeep`` is TRACKED — so
#: the directory is present on every clone, personal content or not, and that predicate is True
#: EVERYWHERE. Measured in a worktree of ``HEAD``: ``projects/`` present, ``projects/**/*.md`` = 0.
#: The marker above therefore never fires; what makes this suite portable today is that each test
#: reading ``projects/`` re-checks its own file by hand, not the marker it wears.
#:
#: So the predicate for "this half of the corpus can contribute something" has to be about
#: DOCUMENTS. Anything asserting the ``projects/`` walk must hang off this one, or it fails on a
#: fresh clone for a reason that has nothing to do with what it is testing — which is how a suite
#: teaches people to delete it.
HAS_PROJECT_DOCS = HAS_PROJECTS and any((REPO / "projects").rglob("*.md"))
needs_project_docs = pytest.mark.skipif(
    not HAS_PROJECT_DOCS,
    reason="no document under projects/ — personal content, absent from a fresh clone (D166 / C20-5)",
)


def plan(*lines: str) -> str:
    return "\n".join(lines) + "\n"


HEAD = ("# PLAN — demo", "", "> **Cap** : prove the form", "")


# --- the grammar ------------------------------------------------------------------------------


def test_every_status_is_read_from_its_glyph_and_each_has_a_french_label():
    text = plan(
        *HEAD,
        "- **A1** \U00002B1C a",
        "- **A2** \U0001F504 b",
        "- **A3** \U00002705 c",
        "- **A4** \U0001F17F\U0000FE0F d",
        "- **A5** \U000026D4 e",
        "- **A6** \U000023F8\U0000FE0F f",
    )
    reading = read_plan(text)
    assert [item.status for item in reading.items] == [
        "a_faire",
        "en_cours",
        "fait",
        "pret",
        "clos",
        "en_pause",
    ]
    assert set(STATUS_LABEL) == set(STATUS_BY_GLYPH.values())
    assert all(item.label for item in reading.items)


def test_CLOSED_and_PAUSED_say_different_things_because_only_one_of_them_comes_back():
    """The two states the LIVING plan already wrote before the reader could hear them.

 They are a pair, and a pair whose labels blurred would be worse than not having them: ```` on
 a live plan marks a design deliberately abandoned ("kept: an erased design cannot be learned
 from"), ```` marks an arc the operator put on hold and expects back. An interface that shows
 both as "not done" tells him to re-decide something already decided, and hides the one thing
 actually waiting.
 """
    reading = read_plan(plan(*HEAD, "- **E2** \U000026D4 vetoed", "- **G1** \U000023F8\U0000FE0F paused"))
    assert [(item.status, item.label) for item in reading.items] == [
        ("clos", STATUS_LABEL["clos"]),
        ("en_pause", STATUS_LABEL["en_pause"]),
    ]
    assert STATUS_LABEL["clos"] != STATUS_LABEL["en_pause"]
    assert "pause" in STATUS_LABEL["en_pause"] and "pause" not in STATUS_LABEL["clos"]


def test_the_ready_glyph_reads_with_or_without_its_variation_selector():
    """```` and ```` differ by an invisible codepoint; one of them silently unread would show an
 empty plan on a project whose plan is written."""
    with_vs = read_plan(plan(*HEAD, "- **A1** \U0001F17F\U0000FE0F parked"))
    without_vs = read_plan(plan(*HEAD, "- **A1** \U0001F17F parked"))
    assert with_vs.items[0].status == without_vs.items[0].status == "pret"
    assert without_vs.items[0].title == with_vs.items[0].title == "parked"


def test_the_PAUSE_glyph_reads_with_or_without_its_variation_selector_too():
    """```` carries U+FE0F exactly like ````, and it is the form writers actually type.

 Adding a status whose composed form the cleaner did not absorb would ship the hole the cleaner
 exists to close, on the very glyph being added: the plan would look written and show nothing.
 The pair is asserted on BOTH forms because only one of them is what a keyboard produces.
 """
    with_vs = read_plan(plan(*HEAD, "- **G1** \U000023F8\U0000FE0F suspended"))
    without_vs = read_plan(plan(*HEAD, "- **G1** \U000023F8 suspended"))
    assert with_vs.items[0].status == without_vs.items[0].status == "en_pause"
    assert with_vs.items[0].title == without_vs.items[0].title == "suspended"


def test_every_status_glyph_is_GLYPH_SHAPED_so_the_net_is_never_narrower_than_the_vocabulary():
    """The link between the vocabulary and the rule that closes the silence, made structural.

    ``_is_glyph_shaped`` is what refuses-by-name a bullet declaring an UNKNOWN glyph. If a status
    were ever added whose glyph falls outside that net, the refusal branch would go blind to its own
    vocabulary — and blind exactly where this module promises it never is. Asserted over the mapping
    rather than over a hand-written list, so a seventh status is covered the day it is written.
    """
    assert all(_is_glyph_shaped(glyph) for glyph in STATUS_BY_GLYPH), sorted(STATUS_BY_GLYPH)


def test_plain_markdown_checkboxes_are_the_floor():
    reading = read_plan(plan(*HEAD, "- [ ] write the probe", "- [x] measure the corpus"))
    assert [(item.status, item.title) for item in reading.items] == [
        ("a_faire", "write the probe"),
        ("fait", "measure the corpus"),
    ]
    assert reading.untracked == 2, (
        "a checkbox item has no identity — that must be visible, not tolerated"
    )


def test_a_checkbox_may_still_carry_an_identity():
    reading = read_plan(plan(*HEAD, "- [x] **C1** the form"))
    assert (reading.items[0].ident, reading.items[0].status) == ("C1", "fait")
    assert reading.untracked == 0


def test_a_bold_WORD_opening_a_checkbox_stays_in_the_title_instead_of_becoming_a_key():
    """``- [ ] **Foundation** lay the floor`` must not yield ident ``Foundation`` — that invents a key nobody
    chose and eats the first words of what the item actually says."""
    reading = read_plan(plan(*HEAD, "- [ ] **Foundation** lay the floor"))
    assert reading.items[0].ident == ""
    assert reading.items[0].title == "**Foundation** lay the floor"


def test_the_cap_and_the_project_name_are_read_and_the_FIRST_of_each_wins():
    """Both firsts. A plan that quotes another plan's heading further down must not silently rename
    the project it belongs to."""
    reading = read_plan(
        plan(
            "# PLAN — Alpha",
            "",
            "**Cap** : the first",
            "# PLAN — something else",
            "**Cap** : the second",
            "- [ ] x",
        )
    )
    assert (reading.project, reading.cap) == ("Alpha", "the first")


def test_a_plan_without_a_cap_or_without_items_is_not_readable():
    assert not read_plan(plan("# PLAN — x", "- [ ] a")).readable
    assert not read_plan(plan(*HEAD, "just some prose")).readable
    assert read_plan(plan(*HEAD, "- [ ] a")).readable


def test_a_BLANK_cap_is_NOT_readable_BR1():
    """ AUDIT/ARBITRATION `BR1` (2026-08-16): `_CAP_RE` captures `(.+?)`, so `**Cap** : ` yields
 `' '` -- a space, TRUE for `bool()`. `.readable`/`.readable_as_door` compared through BARE
 `bool()` where `is_readable()`/`unreadable_reasons()` already apply `PlanItem._sans_contenu` --
 TWO different answers to the same question, one contract with two homes. This witness holds the
 home that was still open; the other is frozen further down in this file."""
    reading = read_plan(plan("# PLAN — x", "", "> **Cap** :   ", "", "- [ ] a"))
    assert reading.cap == " ", "the raw capture stays unchanged -- only the JUDGEMENT changes"
    assert not reading.readable, "a space is not a cap"
    assert not reading.readable_as_door, "same defect, same fix"
    assert not is_readable(reading), "is_readable() already closed this class -- it must stay closed"


def test_the_section_heading_travels_with_its_items():
    reading = read_plan(plan(*HEAD, "## Foundation", "- **A1** \U00002B1C a", "## Next", "- **B1** \U00002705 b"))
    assert [item.section for item in reading.items] == ["Foundation", "Next"]


# --- the refusals, each named -----------------------------------------------------------------


def test_a_line_carrying_both_notations_is_refused_rather_than_guessed():
    reading = read_plan(plan(*HEAD, "- [x] **A1** \U00002B1C contradictory"))
    assert reading.items == ()
    assert [problem.kind for problem in reading.problems] == ["double_notation"]


def test_a_glyph_opening_the_TEXT_of_a_checkbox_is_its_TITLE_not_a_second_notation():
    """Measured cost of growing the vocabulary — and the narrowing it forced, pinned.

 ``- [ ] Read **Ernie Chan "Quantitative Trading"**`` is a real line of
 ``example_research/ROADMAP.md``, written by another agent months before this format: phase 4 of a
 numbered list, put on hold. The day ```` entered the vocabulary, the double-notation rule ate
 it — a plan lost an item by ADDING a status. The rule now requires the glyph to sit where a
 glyph is read as a status (behind a bold token), which is the same place the non-checkbox branch
 demands: without a checkbox, ``- faire X`` is prose. The glyph stays visible in the title.
 """
    reading = read_plan(plan(*HEAD, '- [ ] \U000023F8 Read **Ernie Chan "Quantitative Trading"**'))
    assert reading.problems == (), [p.detail for p in reading.problems]
    assert len(reading.items) == 1 and reading.items[0].status == "a_faire"
    assert reading.items[0].title.startswith("\U000023F8 Read")


def test_an_unknown_glyph_is_refused_AND_quoted_verbatim():
    """Naming it is the point: ```` is a real marker in someone's head, and a reader that dropped
 the line would show a plan missing an item nobody can find.

 ```` used to be the example here and is now a status — which is precisely why the refusal must
 keep being tested with a glyph the vocabulary does NOT hold: a test whose "unknown" input has
 quietly become known stops exercising the branch it is named for.
 """
    reading = read_plan(plan(*HEAD, "- **H2** \U0001F195 new"))
    assert [problem.kind for problem in reading.problems] == ["statut_inconnu"]
    assert "H2" in reading.problems[0].detail and "\U0001F195" in reading.problems[0].detail


def test_an_identity_without_a_status_is_refused():
    reading = read_plan(plan(*HEAD, "- **A1** ", "- **A2**"))
    assert [problem.kind for problem in reading.problems] == ["statut_manquant", "statut_manquant"]


def test_a_duplicate_identity_is_refused_because_two_items_cannot_share_a_key():
    reading = read_plan(plan(*HEAD, "- **A1** \U00002B1C one", "- **A1** \U00002705 two"))
    assert len(reading.items) == 1
    assert reading.problems[0].kind == "id_duplique" and "A1" in reading.problems[0].detail


def test_a_bold_PROSE_bullet_is_never_accused_of_being_a_malformed_item():
    """The rule that ``PLAN_INCARNATION.md`` killed, pinned so it cannot come back."""
    reading = read_plan(
        plan(*HEAD, "- [ ] real", "- **Embodies** : « all tidied »", "- **Deliverables** : an airlock")
    )
    assert len(reading.items) == 1
    assert reading.problems == (), "a word is not an identity — refusing it accuses good prose"


def test_a_named_item_that_DOES_declare_a_status_is_read_even_without_a_digit():
    """The digit rule closes a false accusation; it must not silence a line that declared itself."""
    reading = read_plan(plan(*HEAD, "- **Foundation** \U00002B1C the floor"))
    assert (reading.items[0].ident, reading.items[0].status) == ("Foundation", "a_faire")


def test_sub_bullets_are_prose_so_an_item_may_be_detailed_without_becoming_four_items():
    reading = read_plan(plan(*HEAD, "- **A1** \U00002B1C a", "  - **A2** \U00002B1C detail", "    - [x] detail"))
    assert [item.ident for item in reading.items] == ["A1"]
    assert reading.problems == ()


# --- the detail an interface needs to be worth opening ----------------------------------------


def test_the_indented_block_under_an_item_travels_WITH_it():
    """The operator's reason for the format is that it be "easy to translate into something
 graphically pretty". A view showing only titles is a list: `` THE FULL RUN`` hides that it
 takes 9 hours."""
    reading = read_plan(
        plan(
            *HEAD,
            "- **A1** \U0001F17F\U0000FE0F the big run",
            "  9 a.m. to 6 p.m., **do not** chain a preview onto it.",
            "",
            "  - non destructive, resumable",
            "a paragraph that no longer belongs to A1",
            "- **A2** \U00002B1C the rest",
        )
    )
    assert reading.items[0].detail == (
        "  9 a.m. to 6 p.m., **do not** chain a preview onto it.",
        "  - non destructive, resumable",
    ), "verbatim: a renderer needs the bold and the nesting the author wrote"
    assert reading.items[1].detail == ()


def test_attached_detail_stays_counted_as_prose_and_never_becomes_a_second_bucket():
    """Attaching a line does not claim it. If it did, the residual would shrink and a plan would look
    more machine-read than it is — the exact self-flattery this reader exists to prevent."""
    reading = read_plan(plan(*HEAD, "- **A1** \U00002B1C a", "  some detail", "  more detail"))
    assert reading.attached_prose == 2
    assert reading.attached_prose <= reading.prose_lines


def test_on_the_real_plan_a_PARKED_item_carries_the_reason_it_is_parked():
    """The measure that matters for the UI: on the living plan, the parked heavy run must render with
    its duration and its warnings, not as a bare title.

    Read through :func:`_living_plan`, so it holds whether that plan is one file or a folder — the
    parked run keeps its detail when it moves into an arc, and a test that could only see it in a
    monolithic file was a test that forbade the move.
    """
    reading = _living_plan()
    parked = [item for item in reading.items if item.status == "pret"]
    assert parked, "the living plan carries parked runs — they are the reason \U0001F17F\U0000FE0F exists"
    assert any(len(item.detail) >= 3 for item in parked)
    assert 0 < reading.attached_prose <= reading.prose_lines


# --- the residual: what was NOT read ----------------------------------------------------------


def test_every_line_is_accounted_for_so_a_count_of_items_can_never_stand_alone():
    """items + refusals + flagged tables + prose == the whole file. Without this, "8 items" printed
    about a 500-line plan reads as success while 98 % of it was invisible."""
    text = plan(
        *HEAD,
        "## S",
        "- **A1** \U00002B1C a",
        "- **A2** \U0001F195 b",  # a glyph the vocabulary does NOT hold: a refusal, not an item
        "some prose",
        "- **Embodies** : a PROSE bullet, which claims nothing",  # must land in prose, not claimed
        "| x | \U00002705 |",
        "- [ ] c",
    )
    reading = read_plan(text)
    claimed = len(reading.items) + len(reading.problems)
    structural = 2  # the title line and the cap line
    headings = 1
    assert (
        claimed + structural + headings + len(reading.summary_tables) + reading.prose_lines
        == reading.total_lines
    )


def test_a_status_glyph_inside_a_TABLE_is_flagged_as_a_second_source_not_read_as_an_item():
    reading = read_plan(plan(*HEAD, "- [ ] a", "| run | \U0001F17F\U0000FE0F ready |"))
    assert len(reading.items) == 1
    assert len(reading.summary_tables) == 1, "a table of statuses can drift from the body — say so"


def test_counts_are_computed_and_every_status_is_present_even_at_zero():
    """A status missing from the mapping would silently vanish from any UI reading these counts."""
    counts = read_plan(plan(*HEAD, "- **A1** \U00002B1C a", "- **A2** \U00002B1C b", "- **A3** \U00002705 c")).by_status()
    assert counts == {
        "a_faire": 2,
        "en_cours": 0,
        "fait": 1,
        "pret": 0,
        "clos": 0,
        "en_pause": 0,
    }
    assert set(counts) == set(STATUS_LABEL), (
        "the zeros are the point — a missing key hides a column"
    )


def test_an_empty_file_yields_an_unreadable_plan_rather_than_an_exception():
    reading = read_plan("")
    assert not reading.readable and reading.total_lines == 0 and reading.problems == ()


# --- regression against the real, pre-existing corpus -----------------------------------------


@pytest.mark.parametrize("relative", CONTROL_PLANS)
def test_the_control_plans_raise_ZERO_false_accusations(relative: str):
    """These three carry no item at all — they are prose and tables. A reader that refuses anything
 here is accusing a document that never claimed to follow the format.

 It says ZERO false accusations and it now means BOTH readers. It used to call ``read_plan``
 only, so the folder-form check added by D166 clause 4 — the one that actually went on to accuse
 ten innocent documents — was never exercised by the test whose name promised it was. A name is
 not a test; the fix is to make the name true, not to rename it.
 """
    if not (REPO / relative).exists():
        pytest.skip(f"{relative} absent (projects/ is gitignored by design)")
    text = (REPO / relative).read_text(encoding="utf-8")
    reading = read_plan(text)
    assert reading.problems == (), f"{relative}: {[p.detail for p in reading.problems]}"
    from mnemosyne.production.plan_format import index_problems

    judged = index_problems(text, _arcs_beside(REPO / relative), folder_form=True)
    assert judged == (), f"{relative}: {[(p.line, p.kind, p.detail) for p in judged]}"


def test_the_CONTROL_corpus_cannot_be_EMPTIED_in_silence():
    """The freeze the control corpus never had — and emptying it was completely mute.

    The two shape tables of this file are each defended by a frozen set of NAMES, for a reason
    written out at length beside them: a reference derived from the thing it verifies certifies
    anything. ``CONTROL_PLANS`` is the *non-derived* half of the whole suite — five documents written
    before the format existed, one of which already killed a candidate rule — and it was the one
    table nothing watched. Setting it to ``()`` ran three tests fewer and reported zero failures.

    Two properties, and the second is what stops the freeze from being deleted alongside the list:
    the corpus must still be ANCHORED on a document a fresh clone really carries. ``projects/`` is
    gitignored by design, so a control corpus made only of the sibling project's files skips everywhere but this
    machine — a guarantee that runs on one machine is a guarantee nobody inherits.
    """
    assert len(CONTROL_PLANS) == len(set(CONTROL_PLANS)), (
        f"CONTROL_PLANS carries a duplicate: {sorted(CONTROL_PLANS)}"
    )
    assert set(CONTROL_PLANS) == CONTROL_NAMES, (
        f"frozen without a witness in the table (DEAD reference): "
        f"{sorted(CONTROL_NAMES - set(CONTROL_PLANS))} · "
        f"witnesses never frozen: {sorted(set(CONTROL_PLANS) - CONTROL_NAMES)}"
    )
    versioned = {relative for relative in CONTROL_PLANS if relative in VERSIONED_WITNESSES}
    assert versioned, (
        f"no CONTROL_PLANS witness is a VERSIONED document ({sorted(CONTROL_PLANS)}) — "
        "on a fresh clone they all skip, and the control corpus only ever runs on one machine"
    )
    present = [relative for relative in versioned if (REPO / relative).exists()]
    assert present, f"versioned witnesses absent from disk: {sorted(versioned)}"


#: The refusals the living plan is KNOWN to carry, named one by one rather than counted. Widening
#: the reader made one line visible that had been invisible since it was written — correcting it is
#: the operator's gesture on his own plan, not this suite's. A frozen NAMED list, asserted as a ceiling
#: (``<=``), stays green when the line is repaired and reddens the day an UNRELATED line stops being
#: readable; a count would have flipped red on the repair, which is the wrong direction to fail in.
LIVING_PLAN_KNOWN_REFUSALS = {"**E2-vetoé**"}


def test_the_repos_own_living_plan_is_read_and_is_MOSTLY_PROSE():
    """Both halves matter. It parses (the format was extracted from a real habit, not invented), and
    most of its lines are NOT items — so nobody may present its item count as "the plan".

    Read through :func:`_living_plan`: the property is about the PLAN, and a plan is a folder now.
    Its items do not stop existing when they move into an arc, and the refusals it is known to carry
    travel with them — so the same two assertions hold on both sides of the conversion, which is
    exactly what "the harness survives the gesture" has to mean.
    """
    reading = _living_plan()
    assert len(reading.items) >= 20, "the living plan must stay readable by the format it imposes"
    assert {p.detail for p in reading.problems} <= LIVING_PLAN_KNOWN_REFUSALS, [
        (p.line, p.kind, p.detail) for p in reading.problems
    ]
    assert reading.prose_lines > len(reading.items), "prose is where the reasoning lives — say it"


@needs_projects
def test_a_plan_written_in_plain_checkboxes_elsewhere_in_the_repo_is_readable_as_is():
    """``example_research/ROADMAP.md`` was written by another agent, for another project, months before this
    format existed, in nothing but markdown checkboxes. If the floor were higher than that, the
    format would be an imposition nobody applies."""
    roadmap = REPO / "projects/trading/example_research/ROADMAP.md"
    if not roadmap.exists():
        pytest.skip("projects/trading/example_research/ROADMAP.md absent from this clone")
    reading = read_plan(roadmap.read_text(encoding="utf-8"))
    assert len(reading.items) >= 5 and reading.problems == ()
    assert reading.untracked == len(reading.items)


# --- the FALSE-ACCUSATION RATE, over the whole population, and its indispensable counterpart -----
#
# The folder-form index check shipped as a WALL, and the number is the reason this section exists.
# BEFORE and AFTER are the SAME measure over the SAME population — the shipped rule was re-run from
# ``git show HEAD:`` rather than remembered, because "0 → 60" has already been announced in this repo
# when the true before was 5:
#
#     rule as shipped (HEAD) : 320 documents → 18 accusations, across 4 documents — 18 false, 0 true
#     after this section     : 320 documents →  0 accusation
#
# Where the 18 landed says why this is not a detail: ``docs/FORMAT_PLAN.md``, the page that SPECIFIES
# the check; the living plan, including the very paragraph documenting the defect; and Sibling Research
# — the project D166 names as the model — because ``state/audits/fin-de-plan/`` ends in "plan".
#
# A control with a 100 % false-accusation rate is not a floor of refusal, it is a wall. And the two
# numbers only mean something TOGETHER: a catch rate without its false-kill rate is a wall, and a
# false-kill rate without its catch rate is a sieve. So both live here, in the suite, never in a
# report — a report is a number nobody re-runs.

#: The NAIVE pattern the check shipped with — no left boundary, no notion of context. Kept here as an
#: INDEPENDENT instrument: it is what counts how many ``plan/…md`` occurrences the corpus actually
#: contains, so the "zero accusations" result can be shown to be a discrimination and not an empty
#: corpus. A mechanism that never bites proves nothing, and a reference derived from the rule it
#: checks proves less than nothing.
_NAIVE_ARC_REF = re.compile(r"plan/([^\s`()\[\]|\"'<>\n,;][^`()\[\]|\"'<>\n,;]*?\.md)")


def _arcs_beside(document: Path) -> tuple[str, ...]:
    """The arcs this document is ANSWERABLE for — the ones in ``plan/`` beside it, if it is a DOOR.

 Judging each document against its true neighbourhood is what makes every accusation counted below
 a genuinely FALSE one: the check is being handed the world as it is, and any refusal it returns is
 a defect it invented.

 **AND THAT IS WHY THE DOOR CONDITION IS HERE.** It used to hand the arcs of ``<dir>/plan/`` to
 EVERY document of ``<dir>/``, which is not the world as it is: ``arc_hors_index`` asks "is this
 arc named in ITS DOOR?", and a measure page or a README is not the door of anything. The day the
 repo's own plan is converted, ``docs/plan/`` holds twelve real arcs and every other ``docs/*.md``
 is suddenly asked to index them — **60 accusations over 53 documents, measured**, all of them
 invented by the harness and all of them counted as the rule's. The gesture this mechanism exists
 to permit would have broken its own proof, which means the proof was never about the after.
 ``owning_plan`` in the module has always said the same thing: only a door owns a ``plan/``.
 """
    if document.name not in DOOR_FILENAMES:
        return ()
    arcs_dir = document.parent / "plan"
    if not arcs_dir.is_dir():
        return ()
    return tuple(sorted(child.relative_to(arcs_dir).as_posix() for child in arcs_dir.rglob("*.md")))


def _living_plan() -> PlanReading:
    """The repo's OWN plan, read as a PLAN — door plus arcs — whatever shape it is in today.

 **The harness must survive the gesture the mechanism exists to permit.** Three tests here read
 ``docs/PLAN.md`` as a FILE and asserted things only a monolithic plan can carry (twenty
 items, a parked run with its detail). Convert the plan — the whole point of D166 — and the door
 is twenty-eight lines of index while the items live in ``docs/plan/*.md``: the tests fail, so the
 gesture stays forbidden, so the mechanism is unusable. A test that is only valid until the thing
 it guards is used proves nothing about the after.

 There is exactly ONE way to read a plan-as-a-folder in this repo and it is not written here:
 ``plan_registry.read_plan_tree`` walks the door and its arcs at any depth, threads one identity
 ledger through them, and returns the SAME ``PlanReading`` a single-file plan returns. A second
 implementation living in a test file is the drift this whole arc has been repairing.
 """
    from mnemosyne.production.plan_registry import read_plan_tree

    verdict = read_plan_tree(REPO / "docs", "mnémosyne")[0]
    assert verdict.reading is not None, f"this repo's plan is unreadable: {verdict.why}"
    return verdict.reading


def _living_plan_texts() -> list[tuple[str, str]]:
    """Every FILE the repo's own plan is made of — the door, then its arcs at any depth.

    The per-LINE properties below cannot be asked of a merged reading: they walk raw text. So they
    get the files, found rather than named, for the same reason as :func:`_living_plan` — the day
    the plan is converted, the door keeps twenty-eight lines of index and every bullet those
    properties exist to watch is in an arc. A test pointed at one path would then pass over an empty
    file and say nothing, which is worse than failing.

    The walk itself is ``plan_registry.plan_files``, not a ``rglob`` written here: three test modules
    needed it the day the plan became a folder and each had begun writing its own.
    """
    from mnemosyne.production.plan_registry import plan_files

    found = plan_files(REPO / "docs")
    assert found, f"no door ({' / '.join(DOOR_FILENAMES)}) in docs/"
    return [
        (str(path.relative_to(REPO)), path.read_text(encoding="utf-8"))
        for path in found
        if path.is_file()
    ]


def _population() -> list[Path]:
    """Every real markdown document this check could ever be pointed at, in this repo, today.

    ``docs/`` is walked WHOLE (``**``), not as a hand-listed set of sub-directories: a population
    enumerated by hand is a population that stops growing the day someone adds a directory, and the
    document that would have broken the rule is always the one nobody listed.
    """
    found = sorted((REPO / "docs").rglob("*.md"))
    if HAS_PROJECTS:  # gitignored by design — absent from a fresh clone, never a failure
        found += sorted((REPO / "projects").rglob("*.md"))
    return found


def _outside_d166_authority(document: Path) -> bool:
    """Is ``document`` outside D166's jurisdiction — walked for coverage, never judged for it?

 **ORCHESTRATOR ARBITRATION (2026-08-16), on a question raised rather than settled alone**
 by a producer: *"a declaration lives in a DOOR, and only there"* is a MNÉMOSYNE convention
 (D166) — never signed by a project nested under ``projects/``, which has its own process and
 its own internal conventions. Checking it that same day against a real accused file
 (``projects/saas/Sibling Research/state/audits/decisions/forme-du-produit-et-tag--
 atterrissage.md``) confirmed it: it REALLY carries bulleted lists of raw ``plan/…md`` paths —
 structurally identical to a D166 door index — without ever claiming to BE one. ``_declares()``
 is not malfunctioning; it is the rule's SCOPE that must stay narrow. *Nobody is judged against
 a convention they never signed.*

 **Always WALKED, never judged** — the distinction stays between THIS module and the
 population: the walk in :func:`_population` covers everything, or a sub-tree could disappear in
 silence (272 of the 320 documents, measured before ``projects/`` existed in the walk). What THIS
 function removes is only the right to be ACCUSED — never the right to be seen.

 **The only territory where D166 has authority: ``docs/``, nothing more.** Not even the
 ``plan/`` of a nested project that structurally RESEMBLES a D166 door (``PLAN.md`` + a
 neighbouring ``plan/`` folder) — resembling the shape is not adopting it, and other projects can
 converge on the same shape for reasons of their own. Verified: narrowing the scope to ``docs/``
 alone recovers EXACTLY the 3 documents the orchestrator names as "ours" (2
 ``docs/governance/**``, 1 ``docs/archive/**``) out of the 53 accused — no more, no less.

 **``docs/archive/`` EXEMPTED TOO, for a DIFFERENT reason — not "never signed", but
 "signed in the PAST"**, verified by reading the one accused file
 (``docs/archive/plan-2026-08-12-cap-readaptation.md``) rather than assumed: it carries the REAL
 and TRUE index of the door it was archived from, kept byte for byte (inv. 2 — nothing is
 rewritten on archiving). Judging it against TODAY's plan shape would amount to accusing a
 snapshot of the past of not resembling the present — exactly what the trace exists to prevent.
 *A declaration frozen in history is no longer an active one; it is the memory of having been
 one.*
 """
    try:
        relative = document.relative_to(REPO / "docs")
    except ValueError:
        return True
    return relative.parts[0] == "archive"


#: WHAT DEFENDS THE POPULATION, half by half — by NAME, because a count defends nothing.
#:
#: Measured before this list existed: neutralising the ``projects/`` walk above made **272 of the
#: 320 documents leave in complete silence** and not one test went red (122 passed, exactly as
#: before). The old guard asserted ``len(versioned) >= 8`` and named two files, both in the half
#: that was still being walked — so it could not see the other half go.
#:
#: Chosen to make the property "every BRANCH of the tree is walked", not "these files exist": one
#: witness at least per sub-directory of ``docs/`` (root, ``archive``, ``governance``, ``mesures``,
#: ``parentheses``, ``signalements``, ``veille``), so a walk that loses a sub-tree reddens by name.
#: Every one is tracked by git — the 8 markdown files of ``docs/`` that are gitignored (the
#: signalement reports, D153) are absent from a fresh clone, and a witness absent there would be a
#: reference that rots the moment somebody clones. All ASCII too: a name carrying an accent would
#: compare NFC against a macOS NFD path and fail for a reason that has nothing to do with the walk.
VERSIONED_WITNESSES: frozenset[str] = frozenset(
    {
        "docs/README.md",
        "docs/FORMAT_PLAN.md",
        "docs/PLAN.md",
        "docs/CONTRAT_UI.md",
        "docs/LIVRABLES_DEMANDES.md",
        "docs/BANC_MODELES.md",
        "docs/archive/CHANTIER.md",
        "docs/archive/RESTE_A_FAIRE.md",
        "docs/governance/AME.md",
        "docs/governance/ALLUMAGE.md",
        "docs/governance/TECHNIQUE.md",
        "docs/governance/PLAN_INCARNATION.md",
        "docs/mesures/2026-07-28-forme-des-plans-ecrits-par-les-frontieres.md",
        "docs/parentheses/README.md",
        "docs/signalements/README.md",
        # `P8` — the `docs/besoins/` branch was born on 2026-09-08, and THIS GUARD CAUGHT IT, by
        # its name, exactly in the direction its docstring promises ("add a sub-directory to
        # `docs/` and it reddens too"). The channel's contract is tracked by git and ASCII, so it
        # holds both conditions of this list. *A guard that bites on the very gesture it concerns
        # is a guard that is alive.*
        "docs/besoins/README.md",
        "docs/veille/README.md",
        # `miroir-public` — the `docs/miroir-public/` branch was born on 2026-09-08 (the mandates
        # for the public-mirror sync effort, placed OUTSIDE the plan tree because any `.md` under a
        # `plan/` folder is read as an ARC). THIS GUARD CAUGHT IT by its name, the same day, just as
        # it had caught `docs/besoins/`. Tracked by git and ASCII: both conditions of this list
        # hold.
        "docs/miroir-public/MANDATS.md",
        "docs/moissons/README.md",
        "docs/postes/README.md",
    }
)

#: The other half, and it deliberately introduces NO new named dependency: all three are files this
#: suite already names elsewhere (:data:`CONTROL_PLANS` for the first two,
#: :func:`test_a_plan_written_in_plain_checkboxes_elsewhere_in_the_repo_is_readable_as_is` for the
#: third). If one of them is ever renamed, this suite was already going to redden — so the freeze
#: costs no extra rot surface, it only makes an EXISTING dependency say what it is for.
#:
#: The fourth name was NOT chosen — it was FOUND, by the disk-anchored lower bound below, on the
#: day that bound was written: the ``mnemosyne`` bubble carries two documents and had no witness at
#: all, so that whole branch of the walk could disappear without a word. Three bubbles were watched
#: and four exist. A list that only ever grows by hand grows only where somebody looked.
#: **NAMED BY THE ORCHESTRATOR, 2026-08-15** : the ``personal`` bubble grew markdown on disk
#: (0 of 4 posts named it) and this exact lower bound caught it — the fifth name follows the
#: same discipline as the fourth: found by the walk, not invented.
#: **`ROADMAP.md` → `PLAN.md` CORRECTED on 2026-08-15 (delegated audit)**: the same correction as
#: :data:`CONTROL_PLANS` — the sibling project moved to the FOLDER form, the name frozen here no longer pointed at
#: anything. This witness alone would never have caught it (a string with the wrong name stays a
#: string).
PROJECT_WITNESSES: frozenset[str] = frozenset(
    {
        "projects/saas/Sibling Research/PLAN.md",
        "projects/saas/Sibling Research/STATE.md",
        "projects/trading/example_research/ROADMAP.md",
        "projects/mnemosyne/ui/PLAN.md",
        "projects/personal/course/Mnemosyne/README.md",
    }
)

#: **WRITTEN CHOICE, 2026-09-09 — option (b): the list stays HAND-WRITTEN, and it now DECLARES its
#: dependency on the private repository.** Option (a) — deriving the witnesses from the bubbles
#: actually present on disk — was measured and REJECTED, and here is why:
#: :func:`test_the_PROJECT_witnesses_cover_EVERY_bubble_that_really_carries_documents` compares
#: ``bubbles <= covered``. Deriving ``covered`` FROM ``bubbles`` makes that comparison true BY
#: CONSTRUCTION, therefore mute — and it is exactly that canary which found the 4th, 5th and 6th
#: names of this freeze, three separate times, without anyone having to look. A door that BITES is
#: not replaced by a door that proves itself.
#:
#: **TODO(public-mirror) — THE DEPENDENCY, NAMED.** Every path above lives under ``projects/``,
#: which is **gitignored by design** in the source repository (`.gitignore`: `projects/*`;
#: `git ls-files projects/` returns a single `.gitkeep` there). So **ZERO of these paths can exist
#: in ANY clone**, this distribution included — measured 2026-09-09: 0 of 5 on disk here, while the
#: private repository carries 6 of 6. The names shipped here are moreover SANITIZED stand-ins for
#: private project directories, so they name no file on any disk at all, the author's included.
#: This half of the corpus is therefore NOT judgeable outside the private repository: it SKIPS —
#: and the skip NAMES the absent files, never a silent one (a population excluded from judgment is
#: not a safe population).
PROJECT_WITNESSES_ON_DISK: frozenset[str] = frozenset(
    w for w in PROJECT_WITNESSES if (REPO / w).exists()
)

#: The predicate governing the ``projects/`` half must be THE WITNESSES, not the raw walk.
#: ``HAS_PROJECT_DOCS`` answers "some ``.md`` exists somewhere under ``projects/``" — TRUE in this
#: distribution because of its single ``projects/README.md``, while not one witness exists here. A
#: predicate that does not speak about what the test asserts leaves the test red for a reader who
#: has no gesture to answer it with.
needs_project_witnesses = pytest.mark.skipif(
    not PROJECT_WITNESSES_ON_DISK,
    reason=(
        "no frozen PROJECT_WITNESSES witness is on this disk: the "
        f"{len(PROJECT_WITNESSES)} paths live under `projects/`, gitignored by design "
        "(D166 / C20-5), hence absent from every fresh clone. Absent here: "
        f"{sorted(PROJECT_WITNESSES)}"
    ),
)


def test_the_index_check_accuses_ZERO_of_the_repos_REAL_documents():
    """N documents → M accusations. M must be 0, and the corpus must not be empty of the hard cases.

    Both halves are asserted, because either alone is a lie: "zero accusations" over a corpus with no
    ``plan/…md`` in it is the shape of a control that has never been asked a question.
    """
    from mnemosyne.production.plan_format import index_problems

    documents = _population()
    accusations: dict[str, list[tuple[int, str, str]]] = {}
    occurrences = 0
    out_of_scope = 0
    judged_count = 0
    for document in documents:
        try:
            text = document.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        occurrences += len(_NAIVE_ARC_REF.findall(text))
        if _outside_d166_authority(document):
            out_of_scope += 1
            continue
        judged_count += 1
        judged = index_problems(text, _arcs_beside(document), folder_form=True)
        if judged:
            accusations[str(document.relative_to(REPO))] = [
                (p.line, p.kind, p.detail) for p in judged
            ]
    # The vacuity guards run FIRST, on purpose: a red pass discards everything it measured, so a
    # guard placed after the verdict it protects only ever runs when it is no longer needed. Floors,
    # never equalities — the repo grows, and a rule that forbids growth is a ceiling.
    assert len(documents) >= 8, f"population too thin to conclude: {len(documents)}"
    assert occurrences >= 8, (
        f"{occurrences} `plan/…md` occurrences in the corpus — below this floor, "
        '"0 accusations" no longer proves a discrimination, only an empty corpus'
    )
    # PUBLISHED, never silent (orchestrator arbitration, 2026-08-16): an exclusion whose growth
    # goes unseen is the blind spot this test exists to prevent. The floor keeps the PREDICATE
    # honest — it cannot drift toward "excludes everything" or "excludes nothing anymore" without
    # reddening here first.
    assert out_of_scope >= 40, (
        f"only {out_of_scope} document(s) outside D166's scope (`docs/` exclusively) — "
        "has the predicate stopped excluding `projects/`?"
    )
    assert judged_count >= 8, f"only {judged_count} document(s) still judged — has the scope emptied out?"
    total = sum(len(v) for v in accusations.values())
    assert not accusations, (
        f"{judged_count} documents judged ({out_of_scope} outside D166's scope, never judged) → "
        f"{total} accusations among the judgeable ones, all FALSE: {accusations}"
    )


def test_the_VERSIONED_half_of_the_population_is_walked_and_it_is_named_not_counted():
    """The skip that makes this suite portable must never become the skip that empties it.

 ``projects/`` is absent from a fresh clone by design, so the tests that read it skip — and this
 one then carries the whole proof, alone, on the half that is versioned and therefore present on
 every machine. An excluded population is unjudged, not safe.

 It used to name TWO files and assert ``>= 8``, which is why it watched nothing: both names sat in
 the half that was still being walked, and 8 is a floor 48 documents clear without noticing that
 six of the seven sub-directories had stopped being visited. It now demands NAMES, one branch of
 the tree at a time. The floor stays, and stays a FLOOR — the repo grows, and a rule that forbids
 growth is a ceiling — but it is no longer alone and no longer the thing that would have to fail.

 The number is measured, not chosen: 48 markdown documents under ``docs/`` here, of which 40
 are tracked by git and thus present on a fresh clone. 30 is below that with room for files to be
 archived, and above every collapsed walk — ``glob`` instead of ``rglob`` leaves 6.
 """
    versioned = {d for d in _population() if not d.is_relative_to(REPO / "projects")}
    named = {str(d.relative_to(REPO)) for d in versioned}
    assert VERSIONED_WITNESSES <= named, (
        f"versioned documents fell out of the population: {sorted(VERSIONED_WITNESSES - named)} — "
        "either the docs/ walk no longer visits them, or they were renamed and the freeze above "
        "must be re-pointed BY HAND at the document that replaces them"
    )
    assert len(versioned) >= 30, (
        f"{len(versioned)} versioned documents — 40 are tracked by git today; "
        f"below this floor the portable half of the corpus has been amputated: {sorted(named)}"
    )


def _branch(relative: str) -> str:
    """The first directory under ``docs/`` (or under ``projects/``) — ``""`` at the root."""
    parts = relative.split("/")
    return parts[1] if len(parts) > 2 else ""


def _project_bubbles_on_disk() -> set[str]:
    """The bubbles of ``projects/`` that REALLY carry markdown — a bubble, never a loose file.

    A file sitting at the TOP of ``projects/`` is not a bubble. ``_branch`` renders ``""`` for it,
    and ``""`` can be covered by NO witness (every witness names a bubble) — so a single such file
    turns the bound below red forever. Measured 2026-09-09 on this distribution: it ships exactly
    one ``projects/README.md`` — a signpost saying where projects live, not a project — and that one
    file made this bound RED for every reader who cloned the showcase, with no gesture available to
    them. One source of truth (D163): the coverage bound AND the anti-emptying clause read THIS
    function, never two parallel walks that could drift apart.
    """
    return {
        bubble
        for d in _population()
        if d.is_relative_to(REPO / "projects")
        if (bubble := _branch(str(d.relative_to(REPO))))
    }


def test_a_witness_cannot_be_DELETED_in_silence_because_the_DISK_names_the_branches():
    """ The freezes above are asserted as CEILINGS (``<=``), and a one-sided rule guards one side.

 Measured: **removing a name from either witness set is completely mute** — ``VERSIONED_WITNESSES
 <= named`` and ``on_disk <= named`` both stay true when the left-hand side shrinks, so the list
 that defends 320 documents could be emptied one line at a time without a single red test. That
 is the same shape as the dead freezes beside the shape tables, one file over.

 The lower bound cannot come from this file — a number written here is edited with the list it
 bounds. It comes from the **disk**: every branch of the tree that really carries documents must
 carry at least one witness. Delete the only witness of ``docs/veille/`` and this reddens, naming
 the branch; add a sub-directory to ``docs/`` and it reddens too, which is the direction that
 catches a corpus growing past its guard.

 ``plan/`` is the one branch exempted, by the module's own name for it: those are the arcs of this
 repo's own plan, they do not exist until the plan is converted, and they are defended by the plan
 tests rather than by the population walk. A witness list the conversion would have to edit is a
 witness list that forbids the conversion.
 """
    from mnemosyne.production.plan_format import ARCS_DIRNAME

    versioned = {
        str(d.relative_to(REPO)) for d in _population() if not d.is_relative_to(REPO / "projects")
    }
    branches = {_branch(d) for d in versioned} - {ARCS_DIRNAME}
    covered = {_branch(w) for w in VERSIONED_WITNESSES}
    assert branches <= covered, (
        f"branches of docs/ with no witness at all: {sorted(branches - covered)} — either a witness "
        "was REMOVED from VERSIONED_WITNESSES (the `<=` ceiling cannot see it), or a sub-directory "
        "appeared and nobody is watching it"
    )


@needs_project_witnesses
def test_the_PROJECT_witnesses_cover_EVERY_bubble_that_really_carries_documents():
    """The same lower bound on the other half — and it is the half with the weaker guard today.

    ``on_disk <= named`` cannot see a name leave: with ``PROJECT_WITNESSES`` emptied, ``on_disk``
    is empty too and the only assertion that fires is the one saying so. The disk answers instead:
    every bubble of ``projects/`` that carries markdown must be named by at least one witness.

    **This marker can be NEUTRALISED by emptying the list** — emptying ``PROJECT_WITNESSES`` empties
    ``PROJECT_WITNESSES_ON_DISK``, and this test then SKIPS instead of reddening. That hole is closed
    OUTSIDE the marker, in
    :func:`test_the_skipif_cannot_be_used_to_EMPTY_the_corpus_while_the_disk_says_otherwise`, which
    refuses an empty list as soon as the disk carries a bubble. A freeze protects against forgetting,
    never against the author: that is where the guard against the author is placed.
    """
    bubbles = _project_bubbles_on_disk()
    covered = {_branch(w) for w in PROJECT_WITNESSES}
    assert bubbles <= covered, (
        f"bubbles of projects/ with no witness: {sorted(bubbles - covered)} — a witness removed from "
        "PROJECT_WITNESSES reddens nowhere else"
    )


def test_the_skipif_cannot_be_used_to_EMPTY_the_corpus_while_the_disk_says_otherwise():
    """``HAS_PROJECTS`` is what lets the half below be skipped. Nothing checked it said the truth.

    The guard against an empty corpus and the switch that empties it must not be the same statement
    read twice. Pinning ``HAS_PROJECTS`` to the disk is what stops "make the suite green" from being
    achievable by declaring the corpus absent: on a fresh clone both sides are False and this passes,
    on this machine both are True, and a hand-forced ``HAS_PROJECTS = False`` reddens HERE — outside
    the marker, where the skip cannot reach it.
    """
    assert HAS_PROJECTS == (REPO / "projects").is_dir(), (
        "HAS_PROJECTS does not say what the disk says — the projects/ half would be skipped even "
        "though it is there, and 272 documents would leave the population without a word"
    )
    # **REPEALED 2026-09-09** — the equality `HAS_PROJECT_DOCS == any(witness exists)` is REMOVED,
    # not forgotten. It claimed that "the walk found a `.md` under projects/" and "a frozen name
    # exists" are the SAME proposition. They are two different populations, and this very
    # distribution showed it: it ships exactly one `projects/README.md` — a signpost, not a project —
    # so the walk answers True while the 5 frozen (sanitized) names answer []. The equality was RED
    # for every reader of this showcase, ordering them to "re-point BY HAND" a list of paths no clone
    # can carry: an order nobody can execute is not a gate.
    #
    # What replaces it is ONE-SIDED and anchored to the DISK, hence true on both sides: a disk that
    # carries BUBBLES must carry at least one witness. An emptied list becomes loud again HERE —
    # exactly what the `needs_project_witnesses` marker cannot do, since emptying would switch it off.
    bubbles_here = _project_bubbles_on_disk()
    # A NEUTRALISED HELPER WOULD MAKE THE CLAUSE VACUOUSLY TRUE — `bubbles_here` empty, `not
    # bubbles_here` true, nothing refuses any more. So this test does not let itself be measured
    # through the accessor of the module it watches: it re-reads the disk ITSELF and demands they
    # agree. An excluded population is not a safe population, and a control that can no longer see
    # must redden, never shrug.
    from_the_disk = {
        rel.split("/")[1]
        for p in (REPO / "projects").rglob("*.md")
        for rel in (str(p.relative_to(REPO)),)
        if rel.count("/") >= 2
    }
    assert bubbles_here == from_the_disk, (
        f"_project_bubbles_on_disk() returns {sorted(bubbles_here)}, the disk returns "
        f"{sorted(from_the_disk)} — the projects/ walk no longer sees what is there"
    )
    assert not bubbles_here or PROJECT_WITNESSES_ON_DISK, (
        f"{len(bubbles_here)} bubble(s) of projects/ carry documents ({sorted(bubbles_here)}) and NO "
        f"frozen witness exists on this disk: {sorted(PROJECT_WITNESSES)} — the list has ROTTED, or "
        "it was emptied to switch off the projects/ half of the corpus"
    )
    # **THE PASSING CASE, ASSERTED** — a rule never seen to REFUSE is not a rule. On a disk that
    # carries bubbles, the list is emptied FOR REAL (locally, the freeze untouched) and the clause
    # above is required to refuse. On a fresh clone `bubbles_here` is empty, the clause is vacuously
    # true, and this block claims nothing: it does not run.
    if bubbles_here:
        assert not (not bubbles_here or frozenset(w for w in () if (REPO / w).exists())), (
            f"the disk carries {len(bubbles_here)} bubble(s) and the anti-emptying clause still "
            "accepts an EMPTY list — it protects nothing"
        )
    # **A SILENT SKIP IS FORBIDDEN**: the marker's reason must NAME what is missing, or the reader
    # sees an `s` and never learns which population left the judgment. Tested, not hoped for —
    # removing a name from the reason reddens here.
    #
    # CLAUSE CORRECTED AFTER SABOTAGE (2026-09-09): the first version demanded `"projects/" in
    # reason`. Sabotage fired, SURVIVED — every witness starts with `projects/`, so the clause was
    # true BY CONSTRUCTION as soon as the paths appeared in the reason. What it must demand instead
    # is what the path list does NOT say and the reader must know: WHY they cannot exist for them.
    reason = needs_project_witnesses.kwargs["reason"]
    assert "gitignor" in reason, (
        "the skip reason does not say WHY those files are missing — a reader who cloned this repo "
        "will read it as a fault of their machine and go 'repair' a freeze they cannot hold"
    )
    unnamed = sorted(w for w in PROJECT_WITNESSES if w not in reason)
    assert not unnamed, (
        f"the skip reason does not name these witnesses: {unnamed} — a skip that does not say what "
        "is missing is a silent skip"
    )


@needs_project_witnesses
def test_the_PROJECTS_half_of_the_population_is_walked_TOO_and_says_so_by_name():
    """The half that left in silence, and the test that now stands in the doorway.

 Measured on this repo: neutralising the ``projects/`` branch of :func:`_population` removed 272
 of 320 documents and the suite stayed at 122 passed. Every guard was watching ``docs/``. This one
 watches the other half — by name first, so the failure says which document went missing, and by
 a floor second, so losing the sub-trees nobody named still reddens.

 The floor is a FLOOR: 272 documents live under ``projects/`` today and 40 is well under it, low
 enough that archiving a whole project does not break a test that is not about that, high enough
 that a walk which collapsed to the top level (``glob`` instead of ``rglob``: **0** documents) or
 to a single project cannot pass. On a fresh clone this test does not run at all — which is why it
 is not the only thing defending the population.

 **CORRECTED 2026-09-09**: this test used to hang off :data:`HAS_PROJECT_DOCS`; it now hangs off
 :data:`PROJECT_WITNESSES_ON_DISK` (the ``needs_project_witnesses`` marker). ``HAS_PROJECT_DOCS``
 answers "some ``.md`` exists somewhere under ``projects/``" — a distribution shipping a single
 ``projects/README.md`` makes it TRUE while not one witness exists, and this test then reddens for a
 reader who has no gesture to answer it with. Measured on this distribution: that is exactly what
 was happening here.

 The ``HAS_PROJECT_DOCS`` vs ``HAS_PROJECTS`` distinction itself stays true and
 found by running this suite in a real worktree rather than by reasoning: ``projects/.gitkeep`` is
 tracked, so the directory exists on a fresh clone with nothing in it, and this test failed there
 — naming three documents that no clone can have. The skip that keeps the suite portable and the
 skip that would empty it are separated by
 :func:`test_the_skipif_cannot_be_used_to_EMPTY_the_corpus_while_the_disk_says_otherwise`, which
 pins both predicates to the disk so neither can be hand-forced to make this one disappear.
 """
    population = _population()
    from_projects = [d for d in population if d.is_relative_to(REPO / "projects")]
    named = {str(d.relative_to(REPO)) for d in from_projects}
    on_disk = {w for w in PROJECT_WITNESSES if (REPO / w).exists()}
    assert on_disk, f"no PROJECT_WITNESSES witness on this disk: {sorted(PROJECT_WITNESSES)}"
    assert on_disk <= named, (
        f"present on disk and absent from the population: {sorted(on_disk - named)} — "
        "the projects/ walk no longer visits them"
    )
    assert len(from_projects) >= 40, (
        f"{len(from_projects)} documents under projects/ in the population, out of "
        f"{len(list((REPO / 'projects').rglob('*.md')))} on disk"
    )


#: The GUILTY corpus: every shape a real index entry takes in this repo, each naming an arc that does
#: NOT exist, plus the two shapes of a forgotten arc. Nine entry forms because nine were measured on
#: how this repo writes paths — bare, in backticks (the dominant house style), bold, numbered,
#: nested, quoted, first and second table cell, markdown link. If the rule that kills the false
#: accusations also killed these, the repair would have traded a wall for a sieve.
GUILTY_DOORS: tuple[tuple[str, str, tuple[str, ...], str], ...] = (
    ("bare bullet", "- plan/arc-c.md — the reader", (), "index_sans_fichier"),
    # A door listing its arcs one per line, no bullet at all — the form the pre-commit suite's own
    # fixture was written in, so it is a form somebody in this repo really writes.
    ("bare paragraph", "plan/arc-c.md — the reader", (), "index_sans_fichier"),
    ("backticked bullet", "- `plan/arc-c.md` — the reader", (), "index_sans_fichier"),
    ("bold bullet", "- **plan/arc-c.md** — the reader", (), "index_sans_fichier"),
    ("numbered bullet", "1. plan/arc-c.md", (), "index_sans_fichier"),
    ("nested bullet", "  - plan/arc-c.md", (), "index_sans_fichier"),
    ("quoted bullet", "> - plan/arc-c.md", (), "index_sans_fichier"),
    ("1st cell", "| plan/arc-c.md | the reader |", (), "index_sans_fichier"),
    ("2nd cell", "| Arc C | plan/arc-c.md |", (), "index_sans_fichier"),
    ("markdown link", "- [Arc C](plan/arc-c.md)", (), "index_sans_fichier"),
    ("accented entry", "- plan/arc économie.md", (), "index_sans_fichier"),
    ("arc never named", "no mention of anything", ("arc-c.md",), "arc_hors_index"),
    # The substring hole clause 4 exists to close: the door NEVER indexes `plan/notes.md`, it merely
    # mentions another path that ENDS in the same file name. `base in door` certified the arc.
    ("name as substring", "see docs/mesures/notes.md", ("notes.md",), "arc_hors_index"),
    (
        "name as substring, bullet",
        "- docs/mesures/notes.md — the measurement",
        ("notes.md",),
        "arc_hors_index",
    ),
    # Two arcs sharing a base name: the bare-name fallback may not certify EITHER of them.
    ("ambiguous name", "see notes.md", ("a/notes.md", "b/notes.md"), "arc_hors_index"),
    # DELEGATED AUDIT OF 2026-08-15, measured by the orchestrator: `unique`'s deduplication
    # compared with RAW `==` where `cited()`, in the SAME function, compares with `_same_name`. Two
    # real, distinct arcs whose base name differs only by Unicode FORM (composed NFC vs. decomposed
    # NFD — exactly the drift `_same_name` exists to absorb, per its own docstring: macOS/APFS
    # renders the disk in NFD) escaped the collision: each counted `1` occurrence under `==`, so
    # BOTH entered `unique`, and one bare mention certified both files at once instead of neither.
    # Verified by sabotage: `==` returns `[]` on this line.
    # The two `\u...` escapes below are NOT decorative: an accented character typed directly
    # sometimes silently renormalises to NFC (measured on this very pass: two visually identical
    # keystrokes produced sometimes identical bytes, sometimes different ones), which would empty
    # this witness WITHOUT reddening it. The gap must stay READABLE in the diff, never hidden in a
    # byte no re-read would ever see.
    (
        "ambiguous name, NFC/NFD encodings",
        "see économie.md for the detail",
        ("folderA/e\u0301conomie.md", "folderB/\u00e9conomie.md"),
        "arc_hors_index",
    ),
    # THE LEFT BOUNDARY, and it is here rather than among the innocents for a reason FOUND BY
    # SABOTAGE: removing the lookbehind from `_ARC_REF_RE` left the whole suite green, because on
    # the ``index_sans_fichier`` side the entry rule already masks it — the ``plan/`` buried inside
    # ``fin-de-plan/`` never lands on an entry offset, so a neighbour was holding the behaviour and
    # the rule itself was proven by nothing. It is load-bearing on the CITATION side only: without
    # it, a door that merely mentions ``state/audits/fin-de-plan/audit-x.md`` — a real path in the
    # sibling project — CERTIFIES an arc called ``audit-x.md`` that it never indexed. A killed mutation does
    # not say what killed it; only pointing the sabotage at each rule separately does.
    (
        "neighbouring directory does not certify",
        "see state/audits/fin-de-plan/audit-x.md for the detail",
        ("audit-x.md",),
        "arc_hors_index",
    ),
    (
        "neighbouring directory, bullet",
        "- old-plan/arc-c.md — the old one",
        ("arc-c.md",),
        "arc_hors_index",
    ),
    # THE SYMMETRIC HOLE, and it is where the FIRST repair landed. Requiring a bare list marker
    # plus a fixed decoration set turned the wall around: over the 320 real documents the check saw
    # **0 declarations**, and it was blind to 20 of the 25 shapes a human writes — starting with the
    # three shapes ``read_plan`` reads as ITEMS, so the two halves of one module disagreed about what
    # a line is. Each of these was measured MUTE before this pass and caught after.
    ("ITEM identity + glyph", "- **ARC-C** \U00002B1C `plan/arc-c.md`", (), "index_sans_fichier"),
    ("ITEM empty checkbox", "- [ ] plan/arc-c.md", (), "index_sans_fichier"),
    ("ITEM ticked checkbox", "- [x] plan/arc-c.md", (), "index_sans_fichier"),
    ("ITEM checkbox + identity", "- [ ] **ARC-C** plan/arc-c.md", (), "index_sans_fichier"),
    ("status glyph alone", "- \U00002B1C plan/arc-c.md", (), "index_sans_fichier"),
    ("bold then separator", "- **Arc C** — plan/arc-c.md", (), "index_sans_fichier"),
    ("numbered then bold", "1. **Arc** — plan/arc-c.md", (), "index_sans_fichier"),
    # A label, a dash, the path, nothing after. The separator is the rule — see the innocent
    # « phrase finissant sur un file_path » just below, which ends on a path and declares nothing.
    ("path at end of bullet", "- Arc C — plan/arc-c.md", (), "index_sans_fichier"),
    ("late cell, in bold", "| a | b | **plan/arc-c.md** |", (), "index_sans_fichier"),
    ("HTML li", "<li>plan/arc-c.md</li>", (), "index_sans_fichier"),
    ("HTML td", "<td>plan/arc-c.md</td>", (), "index_sans_fichier"),
    # The HTML container is anchored at the START of the line, and the clause that lets OTHER tags
    # precede it is what this one holds alone — measured on a copy of the module: dropping the
    # ``(?:<…>)*`` prefix leaves ``<li>`` and ``<td>`` above still caught and only this form blind.
    # (``<li>plan/arc-c.md — the reader</li>`` was measured too and is NOT here: no sabotage tells it
    # apart from « li HTML », so it would add a case without adding a proof.)
    ("nested HTML li", "<ul><li>plan/arc-c.md</li></ul>", (), "index_sans_fichier"),
    ("heading", "## plan/arc-c.md", (), "index_sans_fichier"),
    # THE TITLE CONTAINER, PROVEN BY NOTHING until these two — found by sabotage on the module:
    # removing the ATX-heading alternative from ``_CONTAINER_RE`` left the whole suite GREEN. Both
    # heading shapes already listed are MASKED by neighbours — « titre » is caught by the rule « the
    # line IS the path », « titre, gras et séparateur » by the bold-token one — so the container was
    # certified by rules that would hold without it. A killed mutation does not say what killed it.
    # These two are the domain the heading container holds ALONE: a comment AFTER the path, and a
    # bare-word label before it.
    ("heading with a comment", "## plan/arc-c.md — the reader", (), "index_sans_fichier"),
    ("heading, bare-word label", "### Arc C — plan/arc-c.md", (), "index_sans_fichier"),
    ("heading, bold and separator", "#### **Arc C** — plan/arc-c.md", (), "index_sans_fichier"),
    ("reference link", "[arc-c]: plan/arc-c.md", (), "index_sans_fichier"),
    # THE PENDANT OF THE TAIL RULE, and it is the shape ``make plan-convertir`` really writes:
    # a backticked path, a dash, then the arc's whole title. Demanding a CLEAR tail — the obvious
    # way to close the prose hole below — would have made every line of every converted door a
    # mention, i.e. it would have turned the staleness check off on the only doors that will ever
    # have an index. The separator is what separates the two, on the right exactly as on the left.
    (
        "converted door entry",
        "- `plan/arc-i-reparer.md` — ARC I — Repair the `distillateur` \U00002B1C *(born of arc B)*",
        (),
        "index_sans_fichier",
    ),
    (
        "entry then description",
        "- plan/arc-c.md : the reader, which has disappeared",
        (),
        "index_sans_fichier",
    ),
    # An HTML attribute holds its path between quotes, so the quote IS its tail. Anchored at the
    # start of the line like the ``<li>`` container beside it — see the two innocents that quote it.
    ("href attribute", '- <a href="plan/arc-c.md">Arc C</a>', (), "index_sans_fichier"),
    ("href attribute, bare line", '<a href="plan/arc-c.md">Arc C</a>', (), "index_sans_fichier"),
    # THE FENCE PREDICATE, WRITTEN TWICE AND PROVEN BY NOTHING. CommonMark lets a LONGER run
    # close a block; weakening that one comparison left ``_outside_code`` treating everything after
    # such a block as example text — the staleness check off, in silence, because the SECOND copy of
    # the rule (``unclosed_fence_line``) still answered "all closed" and raised no ``bloc_non_ferme``.
    # This pair — an entry AFTER the block, and its innocent twin INSIDE it — is what makes the
    # single foyer load-bearing: sabotage the comparison and both go red, from opposite sides.
    (
        "after a longer closing run",
        "```\nexample\n`````\n- plan/arc-c.md",
        (),
        "index_sans_fichier",
    ),
    # The line that is NOTHING BUT the path. Column 0 stays strict for everything else: 40 lines of
    # real prose in this repo open on a backticked path, and none of them is only that.
    ("bare backticked line", "`plan/arc-c.md`", (), "index_sans_fichier"),
    ("bullet in quotation marks", '- "plan/arc-c.md"', (), "index_sans_fichier"),
    # THE POPULATION THE SEPARATOR SET IS ANSWERABLE TO, AND IT IS NOT THE TOOL'S OUTPUT. Every
    # shape above was written against what ``make plan-convertir`` emits — an em dash — so the set
    # scored twelve on twelve against the tool and **two on ten against the keys a human presses**.
    # The ASCII hyphen was the one that mattered: a person retyping the most edited line of the
    # system with the key on their keyboard DISARMED the staleness check on that line, silently.
    # One shape per separator the module declares, so removing a character from the set can no
    # longer be free — see
    # :func:`test_every_SEPARATOR_the_module_declares_is_the_LAST_PROOF_of_some_pinned_shape`.
    ("ASCII hyphen behind the path", "- `plan/arc-c.md` - ARC C", (), "index_sans_fichier"),
    ("ASCII hyphen in front of the path", "- ARC C - `plan/arc-c.md`", (), "index_sans_fichier"),
    ("double ASCII hyphen", "- ARC C -- plan/arc-c.md", (), "index_sans_fichier"),
    ("ASCII arrow", "- ARC C -> plan/arc-c.md", (), "index_sans_fichier"),
    ("colon", "- ARC C : plan/arc-c.md", (), "index_sans_fichier"),
    ("equals sign", "- ARC C = plan/arc-c.md", (), "index_sans_fichier"),
    ("table pipe", "| ARC C | plan/arc-c.md |", (), "index_sans_fichier"),
    ("en dash", "- ARC C – plan/arc-c.md", (), "index_sans_fichier"),
    ("Unicode minus sign", "- ARC C − plan/arc-c.md", (), "index_sans_fichier"),
    ("Unicode arrow", "- ARC C → plan/arc-c.md", (), "index_sans_fichier"),
    ("Unicode double arrow", "- ARC C ⇒ plan/arc-c.md", (), "index_sans_fichier"),
    ("Unicode long arrow", "- ARC C ⟶ plan/arc-c.md", (), "index_sans_fichier"),
    ("middle dot", "- ARC C · plan/arc-c.md", (), "index_sans_fichier"),
    ("bullet dot", "- ARC C • plan/arc-c.md", (), "index_sans_fichier"),
    ("closing guillemet", "- ARC C » plan/arc-c.md", (), "index_sans_fichier"),
)

#: THE FROZEN NAMED REFERENCE for the table above — written by hand, and deliberately NOT derived
#: from ``GUILTY_DOORS``. The verdict below used to read ``caught == len(GUILTY_DOORS)``, which
#: compares the number to ITSELF: deleting one shape of a real defect from the table left the suite
#: green (measured on this file: one shape removed → 121 passed, two removed → 120 passed, zero
#: failures — the count follows the table down and the assertion never notices). A reference derived
#: from the thing it verifies certifies anything.
#:
#: Frozen as a SET OF NAMES rather than a count, because the three ways this can rot each have to
#: redden: a shape DELETED from the table leaves a name nobody answers for; a shape ADDED without
#: being frozen here shows up as a name nobody declared; and a shape that silently STOPS BEING
#: CAUGHT is named — where a count would only say "34 instead of 35" and let the reader guess which.
#:
#: **THE CEILING OF THIS FREEZE, MEASURED ONE WITNESS AT A TIME AND WRITTEN HERE RATHER THAN
#: LEFT IMPLICIT.** A name and its shape live in the SAME file, so they leave in the same edit:
#: removing each of the 73 witnesses of the two tables together with its frozen name and re-running
#: the whole file gives **2 red and 69 mute** (2 unreachable by the script's own pattern). That is
#: irreducible for a table of witnesses, and it is not the defect it looks like: 69 of them are
#: REDUNDANT — the mechanism each proves stays proven by a neighbour, so losing them costs no
#: guarantee. What must never be silent is losing the LAST proof of a mechanism, and that is what
#: :func:`test_every_MECHANISM_of_the_rule_is_the_LAST_PROOF_of_some_pinned_witness` turns red, with
#: the module itself — not a list written here — as its reference.
#:
#: The same measurement on the population witnesses said **0 red out of 20** before the disk-anchored
#: lower bound beside them; it now says 4 on a fresh clone (the four that are the only witness of
#: their branch of ``docs/``) and 6 on a machine that carries ``projects/``.
GUILTY_NAMES: frozenset[str] = frozenset(
    {
        "bare bullet",
        "bare paragraph",
        "backticked bullet",
        "bold bullet",
        "numbered bullet",
        "nested bullet",
        "quoted bullet",
        "1st cell",
        "2nd cell",
        "markdown link",
        "accented entry",
        "arc never named",
        "name as substring",
        "name as substring, bullet",
        "ambiguous name",
        "ambiguous name, NFC/NFD encodings",
        "neighbouring directory does not certify",
        "neighbouring directory, bullet",
        "ITEM identity + glyph",
        "ITEM empty checkbox",
        "ITEM ticked checkbox",
        "ITEM checkbox + identity",
        "status glyph alone",
        "bold then separator",
        "numbered then bold",
        "path at end of bullet",
        "late cell, in bold",
        "HTML li",
        "HTML td",
        "nested HTML li",
        "heading",
        "heading with a comment",
        "heading, bare-word label",
        "heading, bold and separator",
        "reference link",
        "converted door entry",
        "entry then description",
        "href attribute",
        "href attribute, bare line",
        "after a longer closing run",
        "bare backticked line",
        "bullet in quotation marks",
        "ASCII hyphen behind the path",
        "ASCII hyphen in front of the path",
        "double ASCII hyphen",
        "ASCII arrow",
        "colon",
        "equals sign",
        "table pipe",
        "en dash",
        "Unicode minus sign",
        "Unicode arrow",
        "Unicode double arrow",
        "Unicode long arrow",
        "middle dot",
        "bullet dot",
        "closing guillemet",
    }
)


#: The INNOCENT corpus: the shapes measured in this repo that MENTION an arc path without declaring
#: anything. Each one produced a false accusation before the entry rule, or would have. Pinned beside
#: the guilty table rather than only inside the population scan, so the BOUNDARY between the two is
#: itself a test: a rule change that moves one line across it reddens here by name, where the
#: population scan would only say "one more accusation somewhere in 320 documents".
INNOCENT_LINES: tuple[tuple[str, str], ...] = (
    ("backticked prose", "a `C1` in `plan/arc-c.md` and a `C1` in `plan/arc-d.md`"),
    ("bare prose", "the arcs live in plan/arc-c.md according to the page"),
    ("re-wrapped line", "`plan/arc-d.md` **are a duplicate** and are refused."),
    ("code block", "```markdown\n- plan/arc-c.md — the reader\n```"),
    ("code block with no language", "```\n- plan/arc-c.md\n```"),
    ("tilde block", "~~~\n- plan/arc-c.md\n~~~"),
    ("neighbouring directory", "- state/audits/fin-de-plan/audit-x.md — the annex"),
    ("neighbouring directory quoted", "see (`audits/fin-de-plan/audit-x.md:355-390`)"),
    ("old-plan", "- old-plan/x.md"),
    ("myplan", "- myplan/x.md"),
    ("plural", "- plans/x.md"),
    # A shell pipeline quoted in a sentence is not a table row. Without the "the line must OPEN with
    # a pipe" guard, `ls | plan/x.md` presented itself as a second cell.
    ("shell pipe", "- the command `ls | plan/arc-c.md` fails"),
    # Four spaces IS an indented code block in markdown — an example, and the detail block of an
    # item besides. The bare-paragraph entry above is admitted at column 0 and nowhere else.
    ("indented block", "    plan/arc-c.md"),
    # THE PENDANT OF THE WIDENING JUST ABOVE. Widening the entry rule to the shapes humans really
    # write is exactly how one digs the hole back the other way, so every shape it could have swept
    # in is pinned HERE, by name, beside the culprits it must not be confused with.
    ("sentence ending on a path", "- a duplicate between plan/arc-c.md and plan/arc-d.md"),
    ("sentence ending on a path, no separator", "- The reader reads plan/arc-c.md"),
    ("sentence in a bullet", "- see plan/arc-c.md for the detail"),
    ("sentence in a heading", "## What plan/arc-c.md contains"),
    ("sentence in a numbered bullet", "1. The reader opens plan/arc-c.md then closes it"),
    ("sentence in a cell", "| Arc C | one must read plan/arc-c.md first |"),
    ("sentence behind a bold token", "- **Note** : the file plan/arc-c.md has disappeared"),
    # The twin of the residual the previous pass named and left open: a page wrapping a ``` example
    # inside a ``~~~`` block — which is what a page documenting this format MUST do — collected an
    # ``index_sans_fichier`` from its own illustration, because the fence tracker was a parity toggle
    # that never looked at the fence CHARACTER.
    (
        "``` block wrapped in ~~~",
        "~~~markdown\n```markdown\n- plan/arc-c.md — the reader\n```\n~~~",
    ),
    ("block closed by a shorter run", "````\n```\n- plan/arc-c.md\n````"),
    # THE HTML CONTAINER'S OWN PENDANT, and the same class as the fenced blocks above: a page that
    # EXPLAINS the accepted shapes must be able to quote them. Left unanchored, the ``<li>``
    # alternative read a sentence quoting the tag as a declaration — the format accusing the page
    # that documents it. These two are what makes the anchor load-bearing instead of decorative.
    ("HTML tag quoted in prose", "the tags `<li>plan/arc-c.md</li>` are accepted"),
    ("HTML tag quoted in a bullet", "- one writes `<li>plan/arc-c.md</li>` in HTML too"),
    # THE THIRD SYMMETRIC HOLE, and this line REFUSED A REAL COMMIT. "Inside a container, at its
    # content" never looked at what FOLLOWS the path, while the way beside it demanded a clear tail —
    # so any bullet where only notation preceded the path was a declaration whatever the sentence
    # behind it said. And it is not an exotic shape: it is what a door writes ABOUT ITS OWN HISTORY
    # once it is converted, so the first line saying "this arc is gone" blocked the commit.
    ("prose after the path", "- plan/arc-archive.md has been archived, it no longer exists"),
    # THE MEASURED COST OF THAT REPAIR, pinned instead of discovered later. This is the SAME shape
    # a door may write meaning it as an index line — and the pre-commit suite's own fixture did write
    # it, which is how the cost was found rather than reasoned. No structural rule can tell it from
    # the line above, so it is a mention: a word behind the path with only a space in front of it.
    # Completeness is untouched (``arc_hors_index`` still names an arc nobody mentions); what is lost
    # is STALENESS on doors written this way, and the separator is what buys it back.
    ("prose after the path, ambiguous index shape", "- plan/arc-c.md carries the rest"),
    ("prose after the path, column 0", "plan/arc-archive.md has been archived, it no longer exists"),
    ("prose after the path, in a heading", "## plan/arc-c.md has disappeared from the folder"),
    # The pendant of the ``href`` entry: a page that EXPLAINS the accepted shapes must be able to
    # quote them, which is why the attribute pattern is anchored at the start of the line.
    ("href attribute quoted in prose", 'one writes `<a href="plan/arc-c.md">` in HTML'),
    ("href attribute quoted in a bullet", '- one writes `<a href="plan/arc-c.md">` in HTML'),
    # The indented code block, with a BULLET in it — the half the four-space guard did not cover.
    # ``    plan/arc-c.md`` was correctly read as code and ``    - plan/arc-c.md`` was accused, so a
    # page showing an index by indenting it got refused by the check it was documenting.
    ("indented block carrying a bullet", "    - plan/arc-c.md"),
    ("indented block carrying a cell", "    | Arc C | plan/arc-c.md |"),
    # CommonMark closes a block with a run AT LEAST as long. The twin of the guilty « après une
    # clôture plus longue »: inside such a block, nothing is declared.
    ("block closed by a longer run", "```\n- plan/arc-c.md\n`````"),
    # THE MEASURED COST OF ADMITTING THE KEYS A HUMAN PRESSES, pinned key by key rather than
    # discovered by a later audit. Each of these is a shape HARVESTED from the repo (paths
    # transplanted), and each is the LAST PROOF that one refused ASCII key must stay refused — see
    # :func:`test_every_ASCII_KEY_the_module_REFUSES_is_refused_for_a_REASON_that_still_bites`.
    #
    # ``-``: the class D167 counted — 40 real lines of prose open on a BACKTICKED path at column 0
    # because an editor re-wrapped the paragraph. One of them really is
    # ``slot-universe-audit-2.md:332``, and its ``--`` is the very key being admitted. This is why
    # way 4 of ``_declares`` demands notation to the END of the line and not merely a separator.
    (
        "re-wrapped line at the double ASCII hyphen",
        "`plan/arc-c.md` -- cut at the 600-line limit",
    ),
    # ``,``: 77 real lines put a comma right behind a document name (``CLAUDE.md:76``,
    # another private planning document). Transplanted onto ``plan/…md`` they would all become declarations.
    ("sentence, comma behind the path", "- plan/arc-archive.md, it no longer exists"),
    # ``*``: the bold bullet IS an index form here (« puce en gras » sits in the guilty table), so
    # its prose twin is the exact shape ``*`` would sweep in — the same trap D169 named, in bold.
    ("bold path followed by a sentence", "- **plan/arc-archive.md** has been archived"),
    # ``(``: 164 real lines, and the shape is the ordinary markdown LINK in a sentence
    # (``docs/README.md:22``). Admitting the opening parenthesis turns every one of them into an
    # entry, which is how a repair digs the hole back the other way at scale.
    ("markdown link in prose", "- the truth lives in [`plan/arc-c.md`](plan/arc-c.md) ;"),
)

#: THE SAME FREEZE, on the false-kill side — and it was the more exposed of the two, because nothing
#: at all watched it: an innocent quietly deleted from the table above simply stopped being tested,
#: and the suite reported one test fewer with zero failures (measured: 121 passed). A shape that is
#: no longer protected looks exactly like a shape that was never at risk.
#:
#: The verdict below requires the set of innocents left UNACCUSED to be exactly this set, so the two
#: halves stay one measurement: a rule change that starts accusing one of these reddens by name, and
#: a rule change that "fixes" a false accusation by deleting its witness reddens too.
INNOCENT_NAMES: frozenset[str] = frozenset(
    {
        "backticked prose",
        "bare prose",
        "re-wrapped line",
        "code block",
        "code block with no language",
        "tilde block",
        "neighbouring directory",
        "neighbouring directory quoted",
        "old-plan",
        "myplan",
        "plural",
        "shell pipe",
        "indented block",
        "sentence ending on a path",
        "sentence ending on a path, no separator",
        "sentence in a bullet",
        "sentence in a heading",
        "sentence in a numbered bullet",
        "sentence in a cell",
        "sentence behind a bold token",
        "``` block wrapped in ~~~",
        "block closed by a shorter run",
        "HTML tag quoted in prose",
        "HTML tag quoted in a bullet",
        "prose after the path",
        "prose after the path, ambiguous index shape",
        "prose after the path, column 0",
        "prose after the path, in a heading",
        "href attribute quoted in prose",
        "href attribute quoted in a bullet",
        "indented block carrying a bullet",
        "indented block carrying a cell",
        "block closed by a longer run",
        "re-wrapped line at the double ASCII hyphen",
        "sentence, comma behind the path",
        "bold path followed by a sentence",
        "markdown link in prose",
    }
)


def test_the_frozen_names_and_the_two_tables_are_ONE_population():
    """The freeze must stay ALIVE: a named reference that stops matching its table is a DEAD one.

    Replacing a derived reference with a hand-written list buys nothing if the list is allowed to
    drift — it just moves the silence one file over. So both directions are required, on both
    tables: a name frozen with no shape behind it (a witness that was renamed or deleted and whose
    freeze nobody updated) and a shape present with no name frozen (a case added and never declared)
    are the SAME defect, and both fail here.

    The uniqueness clause is not decoration. ``{entry[0] for entry in TABLE}`` silently swallows a
    duplicate, so two shapes sharing one name would make the set equality below hold while one shape
    stopped being distinguishable — the loss lives exactly where the shape changes.
    """
    for table, frozen, label in (
        ([entry[0] for entry in GUILTY_DOORS], GUILTY_NAMES, "GUILTY_DOORS/GUILTY_NAMES"),
        ([entry[0] for entry in INNOCENT_LINES], INNOCENT_NAMES, "INNOCENT_LINES/INNOCENT_NAMES"),
    ):
        assert len(table) == len(set(table)), (
            f"{label}: two shapes share the same name — "
            f"{sorted({n for n in table if table.count(n) > 1})}"
        )
        assert set(table) == frozen, (
            f"{label}: frozen with no shape in the table (DEAD reference): "
            f"{sorted(frozen - set(table))} · shapes never frozen: {sorted(set(table) - frozen)}"
        )


@pytest.mark.parametrize(("why", "line"), INNOCENT_LINES, ids=[i[0] for i in INNOCENT_LINES])
def test_a_MENTION_is_never_read_as_a_declaration(why: str, line: str):
    """A page may name any path it likes. Only a declaration can be stale."""
    from mnemosyne.production.plan_format import index_problems

    door = plan("# PLAN — demo", "", "> **Cap** : prove", "", line)
    judged = index_problems(door, (), folder_form=True)
    assert judged == (), f"{why} : {[(p.line, p.kind, p.detail) for p in judged]}"


@pytest.mark.parametrize(
    ("why", "line", "arcs", "kind"), GUILTY_DOORS, ids=[g[0] for g in GUILTY_DOORS]
)
def test_every_TRUE_culprit_is_still_caught(why: str, line: str, arcs: tuple[str, ...], kind: str):
    """The pendant of the zero above, and it is asserted case by case rather than as a rate.

    A rate hides WHICH shape stopped being caught, and the shape that stops being caught is always
    the one nobody listed.
    """
    from mnemosyne.production.plan_format import index_problems

    door = plan("# PLAN — demo", "", "> **Cap** : prove", "", line)
    kinds = [p.kind for p in index_problems(door, arcs, folder_form=True)]
    assert kind in kinds, f"{why} : caught by nothing ({kinds})"


def _catches(line: str, arcs: tuple[str, ...] = ()) -> list[str]:
    """The refusal kinds this door line raises — one expression, read by every verdict below."""
    from mnemosyne.production.plan_format import index_problems

    door = plan("# PLAN — demo", "", "> **Cap** : prove", "", line)
    return [problem.kind for problem in index_problems(door, arcs, folder_form=True)]


#: A pattern that can never match anything — how a mechanism of the module is switched OFF below.
_MATCHES_NOTHING = re.compile(r"(?!x)x")

#: **EVERY MECHANISM OF THE RULE, AND HOW TO TURN IT OFF.** The reference is the MODULE — these
#: are its own objects, named here and switched off one at a time — so it cannot be edited from the
#: table it defends. Each one must be NEEDED by at least one pinned witness: turn it off, and some
#: guilty shape must stop being caught or some innocent must start being accused.
#:
#: This is the answer to a measured hole: the frozen name lists beside the two tables are edited in
#: the same file as the tables, so a shape and its name leave together in one edit and nothing goes
#: red — **69 of the 73 witnesses were removable in complete silence**, measured one by one. A name
#: cannot defend a shape; only something the shape is the last proof of can.
_MECHANISMS: tuple[tuple[str, str, object], ...] = (
    ("the containers", "_CONTAINER_RE", _MATCHES_NOTHING),
    ("the table cells", "_CELL_RE", _MATCHES_NOTHING),
    ("the HTML attribute (`href`)", "_ATTR_ENTRY_RE", _MATCHES_NOTHING),
    ("the code-block tracking", "_FENCE_RE", _MATCHES_NOTHING),
    ("the separator IN FRONT OF the path", "_notation_run_before", lambda raw, start: ""),
    ("the TAIL rule (what FOLLOWS the path)", "_tail_declares", lambda raw, end, **_: True),
    ("the INDENTED code block", "_CODE_INDENT", 10**6),
    # Way 4 of `_declares` takes only the TYPOGRAPHIC separators. Hand it the ASCII ones and a
    # re-wrapped paragraph opening on a backticked path becomes an entry again — the class D167
    # counted at 40 real lines, and the reason the ASCII widening stops at column 0.
    ("the TYPOGRAPHIC tail at column 0", "_TYPOGRAPHIC_SEPARATORS", "—–−→⇒⟶·•»-:=|"),
    ("the left boundary of `plan/`", "_ARC_REF_RE", _MATCHES_NOTHING),
)


@pytest.mark.parametrize(
    ("why", "attribute", "replacement"), _MECHANISMS, ids=[m[0] for m in _MECHANISMS]
)
def test_every_MECHANISM_of_the_rule_is_the_LAST_PROOF_of_some_pinned_witness(
    why: str, attribute: str, replacement: object, monkeypatch
):
    """Switch one mechanism off and SOMETHING pinned must move. Otherwise it is proven by nobody.

    *A killed mutation does not say what killed it* — so the instrument is pointed at each mechanism
    separately, and the verdict is not "the suite went red" but "which NAMED witness changed its
    answer". A mechanism no witness depends on is either dead code or a guarantee held by a
    neighbour, and both have already happened here: three of the four containers are masked by the
    « the whole line is notation then the path » way home, and the left boundary of ``plan/`` was
    load-bearing on the CITATION side only, which is why its witness is an ``arc_hors_index``.
    """
    from mnemosyne.production import plan_format

    before = (
        {name for name, line, arcs, kind in GUILTY_DOORS if kind in _catches(line, arcs)},
        {name for name, line in INNOCENT_LINES if not _catches(line)},
    )
    monkeypatch.setattr(plan_format, attribute, replacement)
    after = (
        {name for name, line, arcs, kind in GUILTY_DOORS if kind in _catches(line, arcs)},
        {name for name, line in INNOCENT_LINES if not _catches(line)},
    )
    moved = sorted((before[0] - after[0]) | (before[1] - after[1]))
    assert moved, (
        f"turning off « {why} » ({attribute}) moves NO frozen witness at all — this mechanism is "
        "proven by nobody: either it is dead, or a neighbour masks it, or the witness that carried "
        "it was removed from the tables"
    )


def test_every_CONTAINER_the_module_declares_is_needed_ALONE_by_some_guilty_shape(monkeypatch):
    """The second reference that lives OUTSIDE this file: the module's own table of containers.

 The freeze above is a NAME beside a shape, and both can be deleted in one edit. This one
 cannot: the reference is :data:`_CONTAINER_PATTERNS` in ``plan_format``, and the property is a
 small mutation run rather than a comparison — remove one alternative from the module and at
 least one guilty shape must STOP being caught. So a shape that is the sole witness of a
 container can no longer leave in silence, and an alternative added to the module with no shape
 behind it reddens the day it is written rather than the day it breaks.

 *A killed mutation does not say what killed it* — this is the same instrument, pointed at each
 rule separately. Three of the four alternatives were already masked by the « the whole line is
 notation then the path » way home; only a shape carrying a WORD as its label needs them.
 """
    from mnemosyne.production import plan_format

    full = {why for why, line, arcs, kind in GUILTY_DOORS if kind in _catches(line, arcs)}
    orphaned: list[str] = []
    for name, _ in plan_format._CONTAINER_PATTERNS:
        reduced = re.compile(
            "|".join(p for other, p in plan_format._CONTAINER_PATTERNS if other != name)
        )
        monkeypatch.setattr(plan_format, "_CONTAINER_RE", reduced)
        without = {why for why, line, arcs, kind in GUILTY_DOORS if kind in _catches(line, arcs)}
        monkeypatch.undo()
        if not full - without:
            orphaned.append(name)
    assert not orphaned, (
        f"module containers that NO guilty shape needs alone: {orphaned} — either "
        "the alternative is dead, or the shape that proved it was removed from GUILTY_DOORS"
    )


def test_every_SEPARATOR_the_module_declares_is_the_LAST_PROOF_of_some_pinned_shape(monkeypatch):
    """ WIDENING THE SEPARATOR SET MUST COST SOMETHING. Until now it cost NOTHING.

 Measured before this test existed: adding the ASCII hyphen to ``_SEPARATOR_CHARS`` — a real
 widening, changing what the barrier accepts on every door of this repo — left the WHOLE suite
 green. So did adding ``,``. Nothing anywhere measured the cost of a widening, which is how the
 set came to be exactly the twelve marks ``plan_convert.py`` emits: **a reference derived from the
 thing it verifies**. It scored twelve on twelve against the tool and two on ten against the keys
 a human presses.

 The property is a mutation, never a list: remove ONE character from the module's own set and
 some pinned shape must stop being caught. A character no shape needs is a character nobody asked
 for — exactly what an unjustified widening looks like the day it is written, rather than the day
 somebody notices the door stopped being checked.
 """
    from mnemosyne.production import plan_format

    full = {why for why, line, arcs, kind in GUILTY_DOORS if kind in _catches(line, arcs)}
    assert len(full) >= 10, f"the measurement does not bite: {len(full)} guilty shapes caught"
    orphaned: list[str] = []
    for char in sorted(plan_format._SEPARATOR_CHARS):
        monkeypatch.setattr(plan_format, "_SEPARATOR_CHARS", plan_format._SEPARATOR_CHARS - {char})
        without = {why for why, line, arcs, kind in GUILTY_DOORS if kind in _catches(line, arcs)}
        monkeypatch.undo()
        if not full - without:
            orphaned.append(char)
    assert not orphaned, (
        f"separators that NO pinned shape needs alone: "
        f"{[(c, f'U+{ord(c):04X}') for c in orphaned]} — either the character was added without "
        "anyone writing it, or the shape that proved it left GUILTY_DOORS"
    )


def test_every_ASCII_KEY_the_module_REFUSES_is_refused_for_a_REASON_that_still_bites(monkeypatch):
    """THE SYMMETRIC HOLE of the widening, measured rather than feared — key by key.

    Widening the entry rule to the keys a human presses is precisely how one digs the hole back the
    other way, so every key this module refuses carries its reason in
    :data:`~mnemosyne.production.plan_format.SEPARATOR_KEYS_REFUSED` — and the reason is asserted
    here as a COST, not read as prose: admit that key and some pinned innocent must start being
    accused. A refusal nothing would suffer from is a refusal nobody can argue with, and it ages
    into folklore; a refusal that bites can be revisited the day the shape it protects disappears.

    The numbers behind these four are harvested, not imagined: over the real corpus, transplanting
    the path onto the lines that really carry this shape gives ``-`` → +13 entries, ``,`` → +120 and
    ``(`` → +121, the last of them being every ordinary markdown link written in a sentence.
    """
    from mnemosyne.production import plan_format

    spared = {why for why, line in INNOCENT_LINES if not _catches(line)}
    assert len(spared) >= 20, f"the measurement does not bite: {len(spared)} innocents spared"
    free: list[str] = []
    for char in sorted(plan_format.SEPARATOR_KEYS_REFUSED):
        assert char not in plan_format._SEPARATOR_CHARS, f"« {char} » is refused AND admitted"
        monkeypatch.setattr(plan_format, "_SEPARATOR_CHARS", plan_format._SEPARATOR_CHARS | {char})
        after = {why for why, line in INNOCENT_LINES if not _catches(line)}
        monkeypatch.undo()
        if not spared - after:
            free.append(char)
    assert not free, (
        f"refused ASCII keys whose admission would accuse NO pinned innocent: {free} — "
        "their refusal is proven by nobody: either the reason written in the module stopped "
        "being true, or the shape that carried it left INNOCENT_LINES"
    )


def test_the_ASCII_KEY_of_every_TYPOGRAPHIC_separator_is_DECIDED_and_never_FORGOTTEN():
    """The CLASS, closed — and the class is the defect, not the character that was missing.

    ``—`` was admitted and ``-`` was not: the printer's dash recognised, the keyboard key ignored.
    A human retyping the most-edited line of the system DISARMED the staleness check on that line,
    and nothing told them so. Fixing the character would have left the class open — the next
    typographic mark admitted without its key would do the same thing again, in silence.

    So every typographic mark declares the key one presses for it, and that key is either a
    separator, or REFUSED with its reason. There is no third state: forgetting, which was the only
    state actually occupied, no longer exists.
    """
    from mnemosyne.production import plan_format

    typographic = {char for char in plan_format._SEPARATOR_CHARS if ord(char) > 127}
    assert typographic == set(plan_format.SEPARATOR_ASCII_KEY), (
        f"typographic marks with no declared key: "
        f"{sorted(typographic - set(plan_format.SEPARATOR_ASCII_KEY))} · "
        f"keys declared for a mark that is no longer a separator: "
        f"{sorted(set(plan_format.SEPARATOR_ASCII_KEY) - typographic)}"
    )
    undecided = {
        mark: key
        for mark, key in plan_format.SEPARATOR_ASCII_KEY.items()
        if key not in plan_format._SEPARATOR_CHARS and key not in plan_format.SEPARATOR_KEYS_REFUSED
    }
    assert not undecided, (
        f"keys neither admitted nor refused — the « forgotten » state, the one that produced the defect: "
        f"{undecided}"
    )
    assert all(plan_format.SEPARATOR_KEYS_REFUSED.values()), (
        "a refused key with no reason written: a refusal that does not say why is a wall"
    )


def _probe_at_title(raw: str, title: str) -> str | None:
    """``raw`` with its item TITLE replaced by an arc path — the same line, carrying an entry.

    Built from what :func:`read_plan` says the title IS, never from a prefix guessed here: that is
    what makes the test below a comparison of the two halves rather than a second opinion.
    """
    cut = raw.rfind(title) if title else len(raw.rstrip())
    return None if (title and cut < 0) else raw[:cut] + "plan/arc-sonde.md"


#: Item shapes, one per notation the reader accepts. The table is here so the property below still
#: bites on a machine with no corpus at all — a test that can only run against 320 files is a test a
#: fresh clone does not inherit.
#:
#: **THIS TABLE HAD NO FREEZE AT ALL**, and a freeze it can edit itself is not one: dropping a
#: shape simply removed a parametrized case and the suite reported one test fewer, zero failures.
#: Its reference now lives OUTSIDE this file and cannot be edited from here —
#: :data:`STATUS_BY_GLYPH`, in the module: every status the reader knows must appear on some shape
#: (see the test right below). Three glyphs were missing when that was written, which is the other
#: half of what a dead freeze hides: ````, ```` and ```` were read by the reader and probed by
#: nobody.
ITEM_SHAPES: tuple[str, ...] = (
    "- **A1** \U00002B1C the title",
    "- **A1** \U00002705 the title",
    "- **A1** \U0001F504 the title",
    "- **A1** \U000026D4 the title",
    "- **A1** \U000023F8\U0000FE0F the title",
    "- [ ] the title",
    "- [x] the title",
    "- [ ] **A1** the title",
    "- **B6-bis** \U0001F17F\U0000FE0F the title",
    # A named-but-digitless token that DOES declare a status is an item — the reader says so, so the
    # index check has to see it too. ``- **Arc C** …`` is deliberately NOT here: the reader refuses
    # it (``identite_illisible``), and probing a line the reader rejects would prove nothing.
    "- **Socle** \U00002B1C the title",
)


def test_the_ITEM_SHAPES_table_is_frozen_by_the_MODULE_and_not_by_itself():
    """The reference is :data:`STATUS_BY_GLYPH`, which lives one file away and cannot be edited here.

    That is the whole repair: every other freeze in this file is a hand-written list of names sitting
    beside the table it freezes, so a shape and its name leave together in one two-line edit and
    nothing reddens — **60 witnesses out of 60 measured as removable that way**. A reference is only
    a reference when the thing it checks cannot rewrite it.

    Both directions, because a vocabulary that grows silently is the same defect as one that shrinks:
    a status the reader learns and no shape probes fails here, and a shape carrying a glyph the
    reader does not know fails here too.
    """
    on_shapes = {glyph for glyph in STATUS_BY_GLYPH if any(glyph in raw for raw in ITEM_SHAPES)}
    assert on_shapes == set(STATUS_BY_GLYPH), (
        f"statuses never probed: {sorted(set(STATUS_BY_GLYPH) - on_shapes)} — the reader reads "
        "them, the index half is exercised on none of them"
    )
    # And the floor the module cannot state for us: the plain-checkbox notation, which is the FLOOR
    # of the format and carries no glyph at all, so the freeze above cannot see it.
    assert {"- [ ] the title", "- [x] the title"} <= set(ITEM_SHAPES)


@pytest.mark.parametrize("raw", ITEM_SHAPES, ids=ITEM_SHAPES)
def test_every_shape_the_READER_calls_an_item_is_a_shape_the_INDEX_CHECK_can_see(raw: str):
    """The two halves of this module must agree on what a LINE is — asserted, not hoped.

 They did not. ``read_plan`` read ``- **ARC-C** `plan/arc-c.md```, ``- [ ] plan/arc-c.md`` and
 ``- [x] …`` as items while ``index_problems`` was blind to all three, so the door could declare
 an arc in the format the spec page RECOMMENDS (*"write your index as bullets if you never want
 to think about it"*) and the staleness check would never look. Two definitions of "a line" in
 one module is a guarantee of drift; this is the test that reddens when they part company again.
 """
    from mnemosyne.production.plan_format import index_problems

    read = read_plan(plan(*HEAD, raw))
    assert read.items, f"the reader does not read {raw!r} as an item — the probe would prove nothing"
    probe = _probe_at_title(raw, read.items[0].title)
    assert probe is not None
    kinds = [p.kind for p in index_problems(plan(*HEAD, probe), (), folder_form=True)]
    assert "index_sans_fichier" in kinds, f"{probe!r} : seen by the reader, invisible to the index"


#: The sentence the probe below puts BEHIND the path — the exact line that refused a real commit,
#: taken from the audit's own reproduction rather than invented. Deliberately ASCII and deliberately
#: free of any separator: a space and a word, which is the whole boundary of the tail rule.
_PROSE_BEHIND = " has been archived, it no longer exists"


def test_the_two_halves_agree_on_the_REAL_lines_of_this_repo_and_BOTH_SIDES_are_stated():
    """THE CORPUS-SCALE NUMBER, and it is stated in BOTH directions because one direction is a wall.

 **WHAT THIS NUMBER IS, said plainly, because the last version of it was read as something
 else.** This repo carries **0 real index declarations** — see the test just below, which
 publishes that count. So the population cannot be asked "how many entries do you declare?"; it
 is asked "what would this rule see, on the shapes you really write?", by putting an arc path
 exactly where each real item carries its title. It measures the RULE against real material, not
 the material. And measured on one side only, it proves nothing about where the rule STOPS:

 rule as shipped (``git show HEAD:``) : 662 seen as an entry · **662 still seen with prose
 behind the path** — i.e. it stopped nowhere, and the door of a converted plan would
 have been refused by the first line that MENTIONED a deleted arc;
 after this repair : 662 seen as an entry · **0 with prose behind**.

 So the probe is fired twice on every line: once with the path ENDING it (must be seen — the
 widening) and once with an ordinary sentence behind the path (must be blind — the boundary). A
 rule that never bites proves nothing; a rule that never stops biting is the same wall turned
 around, and only the pair says which one this is.
 """
    from mnemosyne.production.plan_format import index_problems

    from mnemosyne.production.plan_format import _SEPARATOR_CHARS

    # The pendant can be switched off by emptying ONE constant, so the constant is checked against
    # the module's own vocabulary: a sentence, opened by a space and carrying no separator, is what
    # makes the second firing a real question. Blank, or carrying a dash, it would be a green test
    # measuring nothing — which is exactly the shape of the number this one replaces.
    assert _PROSE_BEHIND.startswith(" ") and _PROSE_BEHIND.strip()
    assert not set(_PROSE_BEHIND) & _SEPARATOR_CHARS, "a witness sentence carries NO separator at all"

    def declares(line: str) -> bool:
        judged = index_problems(plan(*HEAD, line), (), folder_form=True)
        return any(problem.kind == "index_sans_fichier" for problem in judged)

    blind: list[str] = []
    swallowed: list[str] = []
    seen = 0
    for document in _population():
        try:
            text = document.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        lines = text.splitlines()
        for item in read_plan(text).items:
            probe = _probe_at_title(lines[item.line - 1], item.title)
            if probe is None:
                continue
            where = f"{document.relative_to(REPO)}:{item.line}"
            if declares(probe):
                seen += 1
            else:
                blind.append(f"{where} {probe[:70]!r}")
            if declares(probe + _PROSE_BEHIND):
                swallowed.append(f"{where} {(probe + _PROSE_BEHIND)[:80]!r}")
    # The vacuity guard runs FIRST: a red pass discards everything it measured, and "0 blind" over an
    # empty corpus is the shape of a control nobody ever asked a question. A FLOOR, never an equality.
    assert seen + len(blind) >= 40, (
        f"corpus too thin to conclude: {seen + len(blind)} lines read as items"
    )
    assert not blind, f"{len(blind)}/{seen + len(blind)} real shapes invisible: {blind[:10]}"
    assert not swallowed, (
        f"{len(swallowed)}/{seen} lines remain a DECLARATION with a sentence behind the "
        f"path — the rule stops nowhere: {swallowed[:10]}"
    )


def test_how_many_DECLARATIONS_the_corpus_REALLY_carries_and_each_sits_in_a_DOOR():
    """ THE THIRD NUMBER — the one nobody writes, and the one that says whether this exists at all.

 "0 false accusations on 320 documents" is true and, alone, **without force**: a control that
 never fires has a perfect false-positive rate. The count of real FIRINGS is what turns that zero
 into a discrimination, so it is published here rather than left to a report — and today it is
 **0 declarations for 37 occurrences of ``plan/…md``** across the whole repo, which is exactly
 why the shape tables above, and not this scan, are what defend the rule.

 The property asserted is the one that survives the conversion and grows with it: **a declaration
 may only live in a DOOR.** Today it holds over an empty set; the day this repo's plan becomes a
 folder its door carries twelve of them and every one is still in a door, while a measure page or
 a README that starts declaring arcs reddens by name.
 """
    from mnemosyne.production.plan_format import _ARC_REF_RE, _declares, _outside_code

    occurrences = 0
    declarations: list[str] = []
    outside_a_door: list[str] = []
    out_of_scope = 0
    for document in _population():
        try:
            text = document.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if _outside_d166_authority(document):
            out_of_scope += 1
            continue
        for offset, raw, live in _outside_code(text.splitlines()):
            for match in _ARC_REF_RE.finditer(raw):
                occurrences += 1
                if not live or not _declares(raw, match.start(), match.end()):
                    continue
                where = f"{document.relative_to(REPO)}:{offset + 1}"
                declarations.append(where)
                if document.name not in DOOR_FILENAMES:
                    outside_a_door.append(f"{where} {raw.strip()[:70]!r}")
    assert occurrences >= 8, (
        f"{occurrences} `plan/…md` occurrences in the corpus — below this floor, no "
        "firing count means anything"
    )
    # PUBLISHED, never silent (orchestrator arbitration, 2026-08-16): see the docstring of
    # :func:`_outside_d166_authority`.
    assert out_of_scope >= 40, f"only {out_of_scope} document(s) outside D166's scope"
    assert not outside_a_door, (
        f"{occurrences} occurrences · {len(declarations)} DECLARATIONS · "
        f"{len(outside_a_door)} outside a door ({out_of_scope} document(s) outside D166's scope, "
        f"never counted in what precedes) : {outside_a_door[:10]}"
    )


def test_merge_plan_REFUSES_a_pair_whose_two_namespaces_disagree():
    """``parts`` and ``PlanItem.source`` must be the SAME string — checked, not documented.

    They drifted the moment they existed (``parts`` relative to ``plan/``, ``source`` relative to the
    door) while both docstrings claimed the same thing, and a consumer had to re-glue the prefix by
    hand. The guard that closed it was itself proven by nothing: deleting the ``raise`` left the whole
    repo green. A convention two callers must remember is a convention that has already broken; a
    guard no test can see disappear is a guard that will.
    """
    from mnemosyne.production.plan_format import merge_plan

    door = read_plan(plan(*HEAD))
    arc = read_plan(plan("- **C1** \U00002B1C an item"), origin="plan/arc-c.md")
    # The pair that AGREES folds without a word, and carries the path into ``parts``.
    merged = merge_plan(door, (("plan/arc-c.md", arc),))
    assert merged.parts == ("plan/arc-c.md",)
    assert {item.source for item in merged.items} == {"plan/arc-c.md"}
    # The pair that DISAGREES raises, and the message names both strings — a refusal that does not
    # say which two things diverged is one nobody can act on.
    with pytest.raises(ValueError) as raised:
        merge_plan(door, (("arc-c.md", arc),))
    assert "arc-c.md" in str(raised.value) and "plan/arc-c.md" in str(raised.value)
    # A refusal carried by an arc counts too — the check reads BOTH buckets, not just the items.
    only_refusal = read_plan(plan("- **A1** \U0001F195 unknown glyph"), origin="plan/arc-d.md")
    assert only_refusal.items == () and only_refusal.problems
    with pytest.raises(ValueError):
        merge_plan(door, (("plan/autre.md", only_refusal),))


def test_merge_plan_QUALIFIES_summary_tables_BY_SOURCE_like_items_and_problems_BR3():
    """ AUDIT/ARBITRATION `BR3` (2026-08-16), measured before fixing it, 186 real occurrences over
 the corpus (Mnémosyne included): `summary_tables` was `tuple[int, ...]`, the ONLY one of the
 three sibling collections (`items`, `problems`, `summary_tables`) that :func:`merge_plan` merged
 WITHOUT qualifying by file. On a folder-plan, a table on line 4 in the door and another on line 4
 in an arc became TWO indistinguishable `4`s. `docs/CONTRAT_UI.md` already states the general
 rule for `items`/`problems`: *"the pair (file, line) is the location; the line alone no longer
 is"* -- `summary_tables` was the exception to it, not the rule."""
    from mnemosyne.production.plan_format import merge_plan

    door = read_plan(plan(*HEAD, "| run | \U00002705 done |"))
    arc = read_plan("| run | \U00002705 done |\n- **C1** \U00002B1C an item\n", origin="plan/arc-c.md")
    merged = merge_plan(door, (("plan/arc-c.md", arc),))
    sources = {source for source, _ in merged.summary_tables}
    assert sources == {"", "plan/arc-c.md"}, (
        f"the door's table and the arc's table must stay DISTINGUISHABLE: {merged.summary_tables}"
    )


def test_the_two_numbers_are_stated_TOGETHER_and_neither_can_be_read_alone():
    """Capture AND false accusations, computed side by side — the pair is the verdict, never one half.

 This is the assertion the operator reads: the check catches every shape of a real defect that was
 measured, spares every shape of correct writing that was measured, and accuses none of the real
 documents of this repo. Any one of the three alone has already been used in this repo to declare
 a mechanism sound while it was a wall — so they stay in ONE assertion, which is the only form
 that cannot be quoted by halves.

 What changed here is the REFERENCE, not the property. It read
 ``(caught, accused) == (len(GUILTY_DOORS), 0)``: ``caught`` was counted by walking
 ``GUILTY_DOORS`` and compared to the length of that same table, so the number was measured
 against itself. Deleting a shape of a real defect took the reference down with it and the suite
 stayed green — one shape removed, 121 passed; two removed, 120 passed; zero failures either
 time. The reference is now the frozen NAMED sets above, and what is compared is the SET of
 names, never its size: "34 of 35" says a shape stopped being caught, ``{"HTML td"}`` says which.
 """
    from mnemosyne.production.plan_format import index_problems

    def judge(line: str, arcs: tuple[str, ...] = ()) -> list[str]:
        door = plan("# PLAN — demo", "", "> **Cap** : prove", "", line)
        return [p.kind for p in index_problems(door, arcs, folder_form=True)]

    caught = {why for why, line, arcs, kind in GUILTY_DOORS if kind in judge(line, arcs)}
    spared = {why for why, line in INNOCENT_LINES if not judge(line)}
    documents = _population()
    # PUBLISHED, never silent (orchestrator arbitration, 2026-08-16): see the docstring of
    # :func:`_outside_d166_authority` — outside D166's scope, never judged by this real third.
    judgeable = [d for d in documents if not _outside_d166_authority(d)]
    assert len(judgeable) >= 8, f"only {len(judgeable)} real judgeable document(s)"
    accused = sum(
        len(index_problems(d.read_text(encoding="utf-8"), _arcs_beside(d), folder_form=True))
        for d in judgeable
    )
    assert (caught, spared, accused) == (GUILTY_NAMES, INNOCENT_NAMES, 0), (
        f"guilty ones that slipped through: {sorted(GUILTY_NAMES - caught)} · "
        f"innocents accused: {sorted(INNOCENT_NAMES - spared)} · "
        f"names caught/spared never frozen: "
        f"{sorted((caught - GUILTY_NAMES) | (spared - INNOCENT_NAMES))} · "
        f"{accused} false accusations over {len(judgeable)} real judgeable documents "
        f"({len(documents) - len(judgeable)} outside D166's scope)"
    )


def _declared_refs(text: str) -> set[str]:
    """The paths this text DECLARES — read through the JUDGE's own accessors, never through a second parser.

    ``index_problems`` is the wrong instrument for this question: it answers "is anything WRONG?",
    and a door whose twelve entries all quietly became mentions is not wrong, it is unwatched. This
    reads the same three objects the judge reads (``_outside_code``, ``_ARC_REF_RE``, ``_declares``)
    and returns WHAT was declared, so the property below can be about the entries themselves.
    """
    import unicodedata

    from mnemosyne.production.plan_format import _ARC_REF_RE, _declares, _outside_code

    found: set[str] = set()
    for _offset, raw, live in _outside_code(unicodedata.normalize("NFC", text).splitlines()):
        for match in _ARC_REF_RE.finditer(raw):
            if live and _declares(raw, match.start(), match.end()):
                found.add(match.group(1).strip())
    return found


def _repo_door() -> Path | None:
    """The REAL door of this repo's plan, found through the single source — never through a hardcoded path.

    ``plan_files`` is what D169 made public precisely so three modules would stop each writing their
    own walk. Going through it means this witness survives the door being renamed, which is the next
    gesture on this plan and must not take the only test of the real index down with it.
    """
    from mnemosyne.production.plan_registry import plan_files

    files = plan_files(REPO / "docs")
    return files[0] if files else None


def test_the_REAL_door_of_this_repo_DECLARES_every_arc_it_owns_and_never_merely_MENTIONS_them():
    """ THE TWELVE REAL DECLARATIONS, HELD BY SOMEBODY. They were held by nobody.

 Measured before this test existed, on the real door: breaking its twelve entries by ONE
 character each (``- `plan/`` → ``- x`plan/``) gives a **fully GREEN suite (2268 passed, 0
 failed)**, ``make plans`` still announces " mnémosyne — 43 items", and ``git rm`` on a cited arc
 becomes ACCEPTED again. The twelve declarations had become twelve mentions and **all four
 surfaces were announcing good health** — because completeness (``arc_hors_index``) settles for a
 mention, and nothing ever asked whether the index was still an INDEX.

 This is why the property is not ``index_problems(...) == ()``: that verdict stays empty on a
 door entirely disarmed. It is a SET EQUALITY between what the disk carries and what the door
 DECLARES — two references neither of which derives from the other, and a NAMED set rather than a
 count, because a count never says WHICH ONE slipped.
 """
    door = _repo_door()
    assert door is not None, (
        "no door found under docs/ — plan_files no longer recognises the plan"
    )
    arcs = _arcs_beside(door)
    # The vacuity guard first: a RED pass discards everything it measured, so a guard
    # placed after the verdict it protects only ever runs when it is no longer useful.
    # NON-DEGENERACY, NOT SIZE — item A6, and the floor was 8 for 6 real arcs.
    # A floor drawn from PRODUCTION makes production unmodifiable: shrinking the plan from 12
    # arcs to 6 reddened this control **with no fault of its own to find in the new
    # plan**. The two obvious remedies were forbidden — lower it to 6 = buying green (to redo
    # at the next shrink); pad the plan up to 8 = building an artefact just to close a
    # door. The real remedy is to MOVE THE POPULATION: what must be proven at
    # a sufficient size is proven on a synthetic fixture
    # (`test_the_SYNTHETIC_door_catches_an_undeclared_arc`), and the living plan only has to
    # not be EMPTY — which is exactly what this guard existed to say.
    assert arcs, (
        f"no arc beside {door.name} — « the door declares them all » proves nothing about an empty folder"
    )
    declared = _declared_refs(door.read_text(encoding="utf-8"))
    import unicodedata

    normalise = {unicodedata.normalize("NFC", name) for name in arcs}
    assert declared == normalise, (
        f"arcs present on disk that the door does NOT DECLARE (merely mentioned at best, so "
        f"invisible to the staleness check): {sorted(normalise - declared)} · "
        f"declarations pointing elsewhere: {sorted(declared - normalise)}"
    )
    from mnemosyne.production.plan_format import index_problems

    judged = index_problems(door.read_text(encoding="utf-8"), arcs, folder_form=True)
    assert judged == (), f"{door}: {[(p.line, p.kind, p.detail) for p in judged]}"


def test_the_index_check_really_FIRES_on_this_repo_and_fires_ONLY_inside_a_DOOR():
    """THE THIRD NUMBER — the one nobody writes: how many times the control ACTUALLY FIRES.

    "0 false accusations on 320 documents" is true and without force as long as this number is
    ignored: a control that never fires has a perfect false-positive rate. The corpus carried
    **zero** the day D169 was cast in stone; it has carried twelve since the conversion, and that
    difference is the whole value of the mechanism.

    The second half is the counterpart, and it bounds the widening: a DECLARATION lives only in a
    DOOR. A measurement page, a README, the page that SPECIFIES this format may cite paths as much
    as they like; the day one of them starts declaring some, the rule has overflowed and this is
    where it reddens, before 320 documents start accusing one another.
    """
    judgeable = [d for d in _population() if not _outside_d166_authority(d)]
    # PUBLISHED, never silent (orchestrator arbitration, 2026-08-16): see the docstring of
    # :func:`_outside_d166_authority`.
    assert len(judgeable) >= 8, f"only {len(judgeable)} real judgeable document(s)"
    fired = {
        str(document.relative_to(REPO)): len(_declared_refs(document.read_text(encoding="utf-8")))
        for document in judgeable
    }
    total = sum(fired.values())
    assert total >= 8, (
        f"{total} declarations over the judgeable corpus — below this floor, « 0 false accusations » "
        "no longer measures a discrimination, only a mechanism that bites nowhere"
    )
    outside = {name: n for name, n in fired.items() if n and Path(name).name not in DOOR_FILENAMES}
    assert not outside, (
        f"documents that are NOT doors declare arcs: {outside} — a page has the "
        "right to cite any path it likes; only a door declares one"
    )


#: The scales at which the two tables are judged. **Measured before this was written**: sabotaging
#: ``index_problems`` with ``if len(arcs) > 3: return ()`` — a mechanism blind on ANY real plan —
#: left the whole suite GREEN, and ``git rm`` on a cited arc became ACCEPTED again. The 25 test
#: calls passed **at most 3 arcs**; this repo's door carries 12, and the scale the
#: owner names (D166: *"four or five times bigger than the sibling project"*, a hundred theories
#: each carrying its own strategies) is two orders of magnitude above that. The middle scale is READ
#: FROM DISK and not written here: a number written here would age away from the plan it claims to
#: measure.
def _repo_arc_count() -> int:
    door = _repo_door()
    return len(_arcs_beside(door)) if door is not None else 0


_SCALES: tuple[int, ...] = (1, _repo_arc_count(), 150)


@pytest.mark.parametrize("scale", _SCALES, ids=[f"{n} arcs" for n in _SCALES])
def test_the_index_check_answers_the_SAME_at_EVERY_SCALE(scale: int):
    """The verdict must not be a function of the NUMBER of arcs — and nothing held that.

    *A fixture must carry the size of the real thing.* Every fixture in this file fit inside
    three arcs, so the whole guarantee fit inside three arcs: a mechanism that dies out on the
    fourth would pass, and this repo's plan has carried twelve since the day it was converted.

    The filler is asserted SILENT and asserted to have LANDED before the verdict it carries: a
    scale test whose filler is itself accused, or whose filler never reaches the function,
    proves nothing about the scale. And the verdict stays PER SHAPE, never a rate — filler feeds
    the collective and masks the per-pair, which is exactly what it must not do here.
    """
    from mnemosyne.production.plan_format import index_problems

    assert scale >= 1, "the scale read from disk is zero — has the door lost its arcs?"
    filler_arcs = tuple(f"remplissage-{i}.md" for i in range(scale))
    filler_lines = [f"- `plan/{name}` — remplissage {i}" for i, name in enumerate(filler_arcs)]

    def judge(line: str, arcs: tuple[str, ...] = ()) -> list[str]:
        door = plan("# PLAN — demo", "", "> **Cap** : prove", "", *filler_lines, line)
        return [p.kind for p in index_problems(door, arcs + filler_arcs, folder_form=True)]

    assert len(filler_arcs) == scale, "the filler does not reach the function"
    assert judge("") == [], f"the filler itself is accused at scale {scale}: {judge('')}"
    caught = {why for why, line, arcs, kind in GUILTY_DOORS if kind in judge(line, arcs)}
    spared = {why for why, line in INNOCENT_LINES if not judge(line)}
    assert (caught, spared) == (GUILTY_NAMES, INNOCENT_NAMES), (
        f"at {scale} arcs — guilty ones that slipped through: {sorted(GUILTY_NAMES - caught)} · "
        f"innocents accused: {sorted(INNOCENT_NAMES - spared)}"
    )


def test_a_fence_is_closed_by_its_OWN_character_and_never_by_a_shorter_run():
    """The fence tracker reads the delimiter; a parity toggle carried BOTH defects at once.

    A page that wraps a ``` example inside a ``~~~`` block — which is exactly what a page documenting
    this format has to do to show what a fenced example looks like — had the inner ``` flip the
    toggle back to "outside": the example became live text and ``docs/FORMAT_PLAN.md``, the page that
    SPECIFIES this check, collected an ``index_sans_fichier`` from its own illustration.
    """
    from mnemosyne.production.plan_format import index_problems

    wrapped = plan(
        *HEAD, "~~~markdown", "```markdown", "- plan/arc-c.md — the reader", "```", "~~~"
    )
    assert index_problems(wrapped, (), folder_form=True) == ()
    # ... and the block does END where it says: an entry after the closing ``~~~`` is live again.
    after = wrapped + plan("- plan/arc-fantome.md — the real entry")
    assert [p.kind for p in index_problems(after, (), folder_form=True)] == ["index_sans_fichier"]
    # A run shorter than the one that opened does not close it (CommonMark, and the same rule).
    longer = plan(*HEAD, "````", "```", "- plan/arc-c.md", "````", "- plan/arc-fantome.md — real")
    assert [p.kind for p in index_problems(longer, (), folder_form=True)] == ["index_sans_fichier"]


def test_an_UNCLOSED_fence_is_NAMED_instead_of_switching_the_check_off_in_silence():
    """The residual the previous pass named and left open, closed — and closed by SPEAKING.

    One unclosed fence turned every remaining line of a door into "inside a block" and the staleness
    check went quiet with no refusal, no count, nothing. That is the worst shape a defect can take
    here: the plan looks judged and nothing was judged. It cannot be repaired by judging the tail
    anyway (markdown really does say the block runs to the end of the file), so it is repaired by
    refusing a door that has one — measured first: ZERO of the 320 real documents of this repo carry
    an unclosed fence, so this refuses a door mid-edit and no door anybody wrote.
    """
    from mnemosyne.production.plan_format import index_problems, unclosed_fence_line

    swallowed = plan(*HEAD, "```markdown", "- an example", "", "- plan/arc-fantome.md — the real one")
    assert unclosed_fence_line(swallowed) == 5
    kinds = [p.kind for p in index_problems(swallowed, (), folder_form=True)]
    assert "bloc_non_ferme" in kinds, kinds
    # Indented by three spaces, which markdown still reads as a fence — same silence, same refusal.
    indented = plan(*HEAD, "   ```", "- an example", "", "- plan/arc-fantome.md — the real one")
    assert [p.kind for p in index_problems(indented, (), folder_form=True)][0] == "bloc_non_ferme"
    # And a door whose fences are all closed says nothing, so the refusal is a discrimination.
    closed = plan(*HEAD, "```markdown", "- an example", "```")
    assert index_problems(closed, (), folder_form=True) == ()


def test_the_imposed_filename_is_a_single_constant():
    assert PLAN_FILENAME == "PLAN.md"


# --- the spec page cannot drift away from the reader -------------------------------------------

# RE-ANCHORED on 2026-09-09, once the sanitized docs/FORMAT_PLAN.md had landed: this section
# used to assert LITERAL FRENCH HEADINGS ("## La porte", "## Dire OUI") that the sanitized page no
# longer carries, and a TODO here said the two sides could not be compared yet. They can now, and
# they were: the page's PROSE is translated ("## The gate", "## Saying YES") while the plan
# vocabulary it documents stays French because the reader looks it up LITERALLY (`*Prérequis*`,
# `produits_resolus=N/N`). Both kinds appear below on purpose — a heading is prose, a field name
# is data.
SPEC = REPO / "docs/FORMAT_PLAN.md"


def test_the_30_seconds_promise_names_LINE_NUMBERS_that_still_point_at_D176():
    """Adoption probe, 2026-08-17: *"reads in 30 seconds"* covers the FORM, not what actually HOLDS
    D176 — a probe arriving via ``grep D176`` stopped halfway through the file without ever reading
    "La porte" or "Dire OUI". The pointer added at the top cites hardcoded LINE NUMBERS (not markdown
    anchors, fragile to compute and not clickable for an agent reading raw text) — so NOTHING keeps
    them up to date if the sections move, except this witness."""
    spec_lines = SPEC.read_text(encoding="utf-8").splitlines()
    header = "\n".join(spec_lines[:20])
    # REAL DRIFT, CAUGHT BY THIS WITNESS on 2026-08-18: `68f2d97` added 10 lines upstream
    # of these two sections without touching the header pointer. The two headings had slid from
    # 694→704 and 739→749, and the header sent the reader to an EMPTY line — which is
    # exactly the adoption failure this pointer exists to prevent. *The producer of the drift
    # never saw it; this witness did.*
    expected = {703: "## The gate", 744: "## Saying YES"}
    for number, heading_start in expected.items():
        assert f"line {number}" in header, f"the header pointer no longer cites « line {number} »"
        # 1-indexed in the prose, 0-indexed in the list
        actual = spec_lines[number - 1]
        assert actual.startswith(heading_start), (
            f"line {number} no longer points at « {heading_start} » (drift): {actual!r}"
        )


def test_produits_resolus_and_terrain_declare_are_EXPLAINED_and_told_apart_from_the_six_tokens():
    """Orchestrator probe, 2026-08-17: an earlier probe had read `produits_resolus` (published
    on every line of `make plans`) as a D176 compliance rate and chased a false drift for
    four steps running. Both numbers must be explained INSIDE the D176 section, and say
    explicitly that neither one is one of the six tokens."""
    raw_text = SPEC.read_text(encoding="utf-8")
    assert "## Saying YES" in raw_text, (
        "the D176 section has been renamed — this probe measures nothing"
    )
    section = raw_text.split("## Saying YES")[1].split("\n## ")[0]
    assert "produits_resolus=N/N" in section
    assert "terrain_declare=N/N" in section
    assert "Neither one is among the six tokens" in section


def test_the_hand_written_freeze_is_NAMED_in_the_D176_section():
    """A door born from `plan-nouveau FORMAT=...` does not enter
    `derives.PORTES_QUI_DECLARENT` on its own (written by hand) — the page must say so, or an
    adopter believes their new door is protected by `VERIFIER=1` from birth."""
    raw_text = SPEC.read_text(encoding="utf-8")
    assert "## Saying YES" in raw_text, (
        "the D176 section has been renamed — this probe measures nothing"
    )
    section = raw_text.split("## Saying YES")[1].split("\n## ")[0]
    assert "PORTES_QUI_DECLARENT" in section
    assert "HAND-WRITTEN" in section or "hand-written" in section.lower()


def test_DERIVE_md_rend_la_main_vers_les_VRAIES_commandes_de_derive_projet():
    """Orchestrator probe: `DERIVE.md` closes item D1 of Mnémosyne, not a PROJECT's own drift
    check — a probe once lost ten minutes there. The four header lines must redirect to
    REAL make targets, never invented names."""
    raw_text = (REPO / "docs/governance/DERIVE.md").read_text(encoding="utf-8")
    header = "\n".join(raw_text.splitlines()[:10])
    assert "make plans VERIFIER=1" in header
    assert "make plancher" in header
    makefile = (REPO / "Makefile").read_text(encoding="utf-8")
    for target in ("plans", "plancher"):
        assert re.search(rf"^{target}:", makefile, re.M), f"make {target} does not exist"


def spec_examples() -> list[str]:
    """Every ```markdown block of the spec — each one is something a frontier may copy."""
    blocks = re.findall(r"```markdown\n(.*?)```", SPEC.read_text(encoding="utf-8"), re.DOTALL)
    assert blocks, "the spec must show at least one copyable example"
    return blocks


def test_the_example_the_spec_tells_frontiers_to_COPY_actually_parses():
    """A format page whose own example does not parse teaches the wrong thing to everyone who obeys
    it — and it would be discovered by the first agent, not by us.

    Selected by NAME, never by position. It used to be ``spec_examples()[0]``, and the day the page
    grew a second copyable block ABOVE it (the index of a plan-folder, D166) that index silently
    started pointing at a different example — a reference derived from the layout of the very
    document it checks. The block is now the one that says which project it is.
    """
    named = [block for block in spec_examples() if "# PLAN — Example Project" in block]
    assert len(named) == 1, (
        f"exactly one full example must carry the project title, got {len(named)}"
    )
    reading = read_plan(named[0])
    assert reading.readable and reading.problems == (), [p.detail for p in reading.problems]
    assert reading.project == "Example Project" and reading.cap
    assert reading.by_status() == {
        "a_faire": 2,
        "en_cours": 1,
        "fait": 2,
        "pret": 1,
        "clos": 1,
        "en_pause": 1,
    }
    assert set(reading.by_status().values()) - {0} == {1, 2}, (
        "every status the page documents must appear at least once in the example it hands out — a "
        "status shown in the table and absent from the copyable block is one nobody ever writes"
    )
    assert reading.untracked == 2, "the example must also show the plain-checkbox floor"


def test_NO_example_in_the_spec_is_refused_by_the_reader():
    """Including the fragments. A snippet the page shows as correct and the reader refuses would teach
    a mistake to every agent that copies it."""
    for index, block in enumerate(spec_examples()):
        reading = read_plan(block)
        assert reading.problems == (), f"block {index}: {[p.detail for p in reading.problems]}"


def test_the_INDEX_the_spec_hands_out_is_accepted_by_the_index_check_it_describes():
    """The page shows a door indexing two arcs. That index is fed to the real check here.

    Same reason as the block above, one clause later: a page that hands out an index the code would
    refuse teaches the wrong thing to the first agent that copies it — and this clause is the one
    that bites hardest, since a refused index blocks a commit.
    """
    from mnemosyne.production.plan_format import index_problems

    # Selected by the HEADING it carries, not by "contains an arc path" — which stopped being a name
    # the day the page grew a SECOND block mentioning ``plan/arc-c.md`` (the fenced-example witness,
    # whose whole point is to sit inside another fence). A selector satisfied by two blocks is a
    # reference derived from the layout of the document it checks, and it silently picked the wrong
    # one: the same defect this file's neighbour above already names, one clause later.
    # BILINGUAL since 2026-09-09, and it is a lesson paid THREE TIMES on the same day: this
    # selector pinned the French literal "## Les arcs". This mirror, which must be entirely in
    # English, translated the heading -- and THIS test fell, while neither the spec nor the code
    # had any defect. A gate written in ONE language FORBIDS translating what it matches, in
    # silence. So it names BOTH spellings, and the `== 1` below still refuses a page carrying
    # two: broadening is not a blank check.
    doors = [block for block in spec_examples()
             if "## Les arcs" in block or "## The arcs" in block]
    assert len(doors) == 1, (
        f"exactly ONE example must be a door's index, {len(doors)} found"
    )
    door = doors[0]
    assert index_problems(door, ("arc-c.md", "arc-d.md")) == (), "the page's own index is refused"
    # And it BITES: the same door with a third arc on disk must name the one it forgot. A page whose
    # example passes a check that never refuses anything has demonstrated nothing.
    forgotten = index_problems(door, ("arc-c.md", "arc-d.md", "arc-e.md"))
    assert [p.kind for p in forgotten] == ["arc_hors_index"], forgotten
    assert "arc-e.md" in forgotten[0].detail


def test_the_ENTRY_SHAPES_the_spec_hands_out_are_EVERY_ONE_of_them_caught():
    """THE THIRD REFERENCE THAT LIVES OUTSIDE THIS FILE — and this one the operator reads.

    ``docs/FORMAT_PLAN.md`` shows a block of index shapes and tells frontiers to write them. Until
    this test, nothing checked that block against the check it describes: the shapes were also
    pinned in :data:`GUILTY_DOORS`, in this file, beside the frozen list of their own names — so a
    shape could leave the table with its name in one edit, and the page would go on teaching a form
    the code no longer sees. It caught a real one the day it was written: the page annotated each
    example with a comment separated by SPACES, and the tail rule reads a space as prose, so eleven
    of the twelve shapes the spec hands out had silently stopped being entries.

    The block is selected by what it CONTAINS (an arc path per line, inside the ``~~~`` fence that is
    not the fenced-example witness), never by position — a reference derived from the layout of the
    document it checks has already picked the wrong block twice in this file.
    """
    from mnemosyne.production.plan_format import index_problems

    blocks = re.findall(r"~~~markdown\n(.*?)~~~", SPEC.read_text(encoding="utf-8"), re.DOTALL)
    shapes = [
        line
        for block in blocks
        if "```" not in block  # the fenced-example witness shows a MENTION on purpose
        for line in block.splitlines()
        if "plan/" in line
    ]
    assert len(shapes) >= 10, f"the page no longer shows more than {len(shapes)} entry shapes: {shapes}"
    missed = [
        line
        for line in shapes
        if "index_sans_fichier"
        not in [p.kind for p in index_problems(plan(*HEAD, line), (), folder_form=True)]
    ]
    assert not missed, (
        f"{len(missed)}/{len(shapes)} shapes the page teaches that the check does NOT SEE: "
        f"{missed}"
    )


def test_the_spec_example_of_ATTACHED_DETAIL_really_attaches_and_really_stops():
    """The page claims the indented block belongs to the item and the unindented paragraph does not.
    That claim is checked here, not trusted."""
    # Bilingual for the same reason as the index witness above.
    detail_block = next(block for block in spec_examples()
                        if "n'est plus dans" in block or "is no longer in" in block)
    item = read_plan(detail_block).items[0]
    assert len(item.detail) == 2
    assert "9 à 18 h" in item.detail[0] or "9 to 18 h" in item.detail[0], item.detail[0]
    assert all("n'est plus dans" not in line for line in item.detail)


def test_the_spec_lists_EXACTLY_the_statuses_the_reader_knows():
    """A glyph documented but unread, or a known one dropped from the page, is the same defect in
    both directions: the page and the code stop being one source.

    Named for the PROPERTY, not for a count: the test used to say "the four statuses" and the number
    in its name was the first thing to rot when the vocabulary grew.
    """
    documented = set(re.findall("^\\| `(.)\U0000FE0F?` \\|", SPEC.read_text(encoding="utf-8"), re.MULTILINE))
    assert documented == set(STATUS_BY_GLYPH), (
        f"page={sorted(documented)} code={sorted(STATUS_BY_GLYPH)}"
    )


# --- the four holes an isolated audit measured on 2026-07-28 (arc C7) ----------------------------
# Each of these passed BEFORE the fix in the sense that nothing was red: the reader was silently
# wrong, which is the failure mode this module's own docstring says it does not have.


def test_a_bullet_that_DECLARES_a_status_is_never_silent_whatever_its_token_looks_like() -> None:
    """`_IDENT_RE` is ASCII-only, space-free, capped at 12 — French plans fell straight through.

    All four of these carry a real status glyph, so under the reader's own promise ("it never
    silences a line that declared a status") not one may end up as prose. They are REFUSED by name
    rather than read, because guessing an identity out of `**Étape 1**` would make the reader the
    author of a key nobody wrote.
    """
    reading = read_plan(
        "# PLAN — d\n> **Cap** : x\n"
        "- **Étape 1** \U00002B1C take stock\n"
        "- **Infrastructure** \U00002B1C le socle\n"
        "- **Arc C** \U00002705 le format\n"
        "- **1A** \U00002B1C premier\n"
    )
    assert [p.kind for p in reading.problems] == ["identite_illisible"] * 4
    assert reading.items == ()


def test_a_bullet_that_declares_NOTHING_stays_prose_no_new_false_accusation() -> None:
    """The other half, and the one that decides whether the rule above is usable at all.

    ``- **Embodies** :`` opens 14 prose bullets in a real archived document. A catch rate without its
    false-kill rate is a wall: the glyph is what separates an accusation from a false one.
    """
    reading = read_plan("# PLAN — d\n> **Cap** : x\n- **Embodies** : some prose, no status\n")
    assert reading.problems == ()
    assert reading.items == ()


def test_a_duplicate_identity_is_caught_in_BOTH_notations_not_just_the_glyph_one() -> None:
    """The ident is what an interface keys its list on; a collision renders ONE card for two items.

    The check used to live inside the glyph branch, so the checkbox form recorded the ident without
    ever consulting the register — and which line got refused depended on the ORDER of the two
    notations, not on the fact.
    """
    for second in ("- [x] **C1** two", "- **C1** \U00002705 two"):
        reading = read_plan(f"# PLAN — d\n> **Cap** : x\n- [ ] **C1** one\n{second}\n")
        assert [p.kind for p in reading.problems] == ["id_duplique"], second
        assert len(reading.items) == 1, second


def test_an_indented_status_table_cannot_land_in_BOTH_buckets() -> None:
    """``attached_prose`` is documented "a SUBSET of prose_lines, never a second bucket".

    An indented status table under an item was subtracted from the residual AND collected as detail,
    so the invariant inverted — while the two tests pinning it fed only inputs that cannot break it.
    """
    reading = read_plan(
        "# PLAN — d\n> **Cap** : x\n- **A1** \U00002B1C a\n  | run | \U00002705 done |\n  | r2 | \U00002705 done |\n"
    )
    assert reading.summary_tables == (("", 4), ("", 5))
    assert reading.attached_prose <= reading.prose_lines


def test_a_plan_written_in_NFD_keeps_its_accents_in_the_title() -> None:
    """The cleaner dropped EVERY combining mark, not the two variation selectors it is named for.

    A plan in decomposed form came back "Economies" in the title while the indented detail below
    kept its accents — four non-NFC markdown files already live under ``projects/``.
    """
    import unicodedata

    text = unicodedata.normalize("NFD", "# PLAN — d\n> **Cap** : x\n- **A1** \U00002B1C Économies\n")
    title = read_plan(text).items[0].title
    # Compared after NFC: the reader is a READER, it does not re-normalise what the author wrote, so
    # the title comes back decomposed exactly as the file holds it. The property under test is that
    # NOTHING WAS DROPPED — asserting against a composed literal would have measured normalisation
    # instead, and would fail on a correct reader.
    assert unicodedata.normalize("NFC", title) == "Économies"
    assert "Économies" in unicodedata.normalize("NFD", title)


def test_the_variation_selector_is_still_absorbed_so_a_status_is_never_lost() -> None:
    """The narrowing above must not undo what the cleaner exists for: and are one status.

 The TITLE is asserted too, and that is the whole bite: measured by mutation, deleting
 ``_VARIATION_SELECTORS`` entirely left the two ``.status`` assertions GREEN — ``clean[:1]`` keeps
 only the base codepoint, so the trailing U+FE0F never reached the lookup. The module comment
 already called that an equivalent mutant for the glyph; the test kept claiming to guard it. What
 the cleaner really protects is everything AFTER the glyph, where the selector becomes an
 invisible first character of what a human reads.
 """
    for text in ("- **A1** \U0001F17F\U0000FE0F ready", "- **A1** \U0001F17F ready"):
        item = read_plan(f"# PLAN — d\n> **Cap** : x\n{text}\n").items[0]
        assert item.status == "pret", text
        assert item.title == "ready", (text, [hex(ord(c)) for c in item.title])


# --- the LAST silence: an unknown glyph behind a token that cannot be read ------------------------
# The hole was the INTERSECTION of two rules that each looked closed. `_IDENT_RE` fails on a
# non-ASCII token, and the loose branch that catches that only fired when the glyph was already IN
# the vocabulary. Unknown glyph AND unreadable token matched nothing at all: no item, no refusal, no
# trace — on the repo's own plan, which called itself readable while hiding a line.


def test_an_unknown_glyph_behind_an_UNREADABLE_token_is_named_instead_of_vanishing() -> None:
    """The living defect, in its own shape: ``- **E2-vetoé** …`` was in neither bucket.

 Both halves are broken here — the token cannot be a key (``é``), the glyph is not a status — and
 that is exactly the combination nothing covered. The reader owes three outcomes per line and was
 returning a fourth: nothing.
 """
    for body in ("- **E2-vetoé** \U0001F195 kept", "- **Étape 1** \U0001F195 take stock", "- **Arc C** \U0001F195 x"):
        reading = read_plan(f"# PLAN — d\n> **Cap** : x\n{body}\n")
        assert [p.kind for p in reading.problems] == ["identite_illisible"], body
        assert reading.items == (), body


def test_an_unknown_glyph_behind_a_readable_WORD_is_named_instead_of_vanishing() -> None:
    """The other half of the same silence, and the reason the fix is in TWO branches.

 ``**Foundation**`` IS readable as a key — the reader accepts ``- **Foundation** x`` as an item. But with
 an unknown glyph it fell through the digit rule and vanished just as completely, because only an
 identity-SHAPED token (``A1``) could be refused for its status.
 """
    reading = read_plan("# PLAN — d\n> **Cap** : x\n- **Foundation** \U0001F195 the floor\n")
    assert [p.kind for p in reading.problems] == ["statut_inconnu"]
    assert reading.items == ()


def test_widening_the_net_accuses_NONE_of_the_characters_the_corpus_actually_writes() -> None:
    """The false-kill side, measured on the repo BEFORE the rule was written, then pinned here.

    Among every bold-token bullet the reader treats as prose, repo-wide, the character following the
    token is a pictograph exactly ONCE. These are the frequent ones — ``:`` 3 583 times, ``—``
    1 061, ``(`` 1 710, ``+`` 92, ``=`` 48, ``→`` 33, backtick 74. One Unicode category wider and
    the reader would have accused 194 good lines to catch one bad. A catch rate without its
    false-kill rate is a wall, so the wall is what this test measures.
    """
    heads = (":", "—", "(", "+", "=", "→", "`", "≥", "$", "“", "«", ",", "/", "*", "1", "d", "L")
    for head in heads:
        reading = read_plan(f"# PLAN — d\n> **Cap** : x\n- **Embodies** {head} some prose\n")
        assert reading.problems == (), f"{head!r}: {[p.detail for p in reading.problems]}"
        assert reading.items == (), head


def test_the_living_plan_keeps_NO_bullet_that_declares_a_glyph_and_ends_in_SILENCE() -> None:
    """The property, on the real file — not a line number, so it survives the line being fixed.

    ``docs/PLAN.md`` is the material that revealed the hole and it is the operator's file to
    correct, so the check is stated as the CLASS: every top-level bullet whose bold token is followed by a
    pictograph must come back as an item or as a named refusal. Counting refusals instead would go
    red the day the plan is repaired, which is the wrong direction for a test to fail in.
    """
    from mnemosyne.production.plan_format import (
        _BOLD_TOKEN_RE,
        _BULLET_RE,
        _despecify,
        _read_item,
    )

    silent: list[str] = []
    examined = 0
    for where, text in _living_plan_texts():
        for offset, raw in enumerate(text.splitlines()):
            bullet = _BULLET_RE.match(raw)
            if bullet is None or bullet.group(1):
                continue
            loose = _BOLD_TOKEN_RE.match(bullet.group(2))
            if loose is None or not _is_glyph_shaped(_despecify(loose.group(2).strip())[:1]):
                continue
            examined += 1
            item, problem, _ = _read_item(bullet.group(2), line_no=offset + 1)
            if item is None and problem is None:
                silent.append(f"{where} line {offset + 1}: {raw[:70]}")
    # The vacuity guard FIRST: a red pass discards everything it measured. Without it, this property
    # would have gone green-and-empty the moment the plan became a folder and the door stopped
    # carrying the bullets it exists to watch — 149 of them today, all in the material.
    # NON-DEGENERACY, NOT SIZE (A6): the floor was 40 for 24 real bullets, so it
    # forbade the plan from shrinking. The mechanism's bite is proven on a fixture
    # (`test_la_puce_SILENCIEUSE_est_attrapee_sur_une_fixture_de_taille_suffisante`); here it is enough
    # that the living corpus is not EMPTY. The count stays PUBLISHED — a report, plus a floor.
    assert examined, f"no glyph-bearing bullet examined ({examined}) — the corpus has been amputated"
    assert silent == [], silent


# --- the refusal VOCABULARY: declared, producible, and the same on the page ------------------------


def test_EVERY_declared_refusal_is_actually_PRODUCIBLE_by_some_input():
    """A name is not a test. A refusal kind no input can trigger is a promise nobody keeps — and it
    would read, on the spec page and in a report, exactly like one that bites.

    The fixtures come from the material, the REFERENCE is the frozen declared tuple, and EQUALITY is
    required in both directions: a kind declared and never produced fails here, and a kind produced
    and never declared fails here too. Asserting only "each fixture yields something" would have
    proved a sample.
    """
    from mnemosyne.production.plan_format import ALL_REFUSAL_KINDS, fold_plan, index_problems

    produced: set[str] = set()
    for text in (
        plan(*HEAD, "- **A1** \U0001F195 unknown glyph"),
        plan(*HEAD, "- **A1**"),
        plan(*HEAD, "- [x] **A1** \U00002B1C two notations"),
        plan(*HEAD, "- **A1** \U00002B1C un", "- **A1** \U00002B1C deux"),
        plan(*HEAD, "- **Étape 1** \U00002B1C unreadable token"),
        # `champ_duplique`: a FOLDED prose line whose marker lands at the head of a continuation
        # line is canonical too — this is how an item declaring `OWNER` used to come out
        # startable, the gate green. The reader now refuses instead of choosing.
        plan(
            *HEAD,
            "- **A1** \U00002B1C one",
            "  Narrative talking about the field «",
            "  *Prérequis* : OWNER » and running over.",
            "  *Prérequis* : AUCUN",
        ),
        # A7, second audit pass (H-a): a document-level region never closed used to swallow the
        # whole rest of the file WITHOUT raising a refusal — its twin (a fence) already did so elsewhere.
        plan(*HEAD, "~~~markdown", "- **A1** \U00002B1C never read, the fence never closes"),
        plan(*HEAD, "<!-- draft never closed", "- **A1** \U00002B1C never read either"),
    ):
        produced |= {problem.kind for problem in read_plan(text).problems}
    # The folder refusals are not line-shaped, so they come from the index check, not the reader.
    produced |= {p.kind for p in index_problems("nothing", ("arc-c.md",))}
    produced |= {p.kind for p in index_problems("- plan/fantome.md — an arc\n", ("arc-c.md",))}
    produced |= {p.kind for p in index_problems("```markdown\n- an example\n", ())}
    # The two `prerequis_*` come from their OWN judge, and that is the point rather than an
    # inconvenience: wired into `read_plan` they would refuse 168 of the sibling project's 168 items on day one.
    from mnemosyne.production.plan_format import prerequisite_problems, required_field_problems

    produced |= {
        p.kind
        for text in (
            plan(*HEAD, "- **A1** \U00002B1C no prerequisite declared"),
            plan(*HEAD, "- **A1** \U00002B1C t.", "  *Prérequis* : PEUT-ETRE"),
        )
        for p in prerequisite_problems(read_plan(text))
    }
    # The THIRD producer — prepared, with no caller yet, and all the more bound to prove it
    # can bite: a refusal kind no input triggers is a promise nobody
    # keeps, and this one has no door yet to betray it.
    produced |= {
        p.kind for p in required_field_problems(read_plan(plan(*HEAD, "- **A1** \U00002B1C a bare item")))
    }
    # The FOURTH producer — ordering. It lives in a module that imports this one, so the union
    # is declared HERE: an audit measured that a producer left OUT of the union escapes BOTH
    # gates at once — "every declared kind is producible" AND "the page names them all".
    from mnemosyne.production.plan_ordre import ordonner

    produced |= {
        p.kind
        for text in (
            plan(*HEAD, "- **A1** \U00002B1C x", "  *Dépend de* : A9"),
            plan(*HEAD, "- **A1** \U00002B1C x", "  *Dépend de* : A1"),
            plan(*HEAD, "- **A1** \U00002B1C x", "  *Dépend de* : a sentence with no list"),
            plan(
                *HEAD, "- **A1** \U00002B1C x", "  *Dépend de* : A2", "- **A2** \U00002B1C y", "  *Dépend de* : A1"
            ),
        )
        for p in ordonner(read_plan(text)).problems
    }
    # `arc_vide` is about a FILE, so only the fold can produce it: `index_problems` interrogates the
    # door and `read_plan` is handed text without knowing where it came from.
    produced |= {
        p.kind
        for p in fold_plan(
            plan(*HEAD, "- `plan/empty.md` — an arc"),
            ("plan/empty.md",),
            lambda _member: ("  \n", ""),
        ).problems
    }
    # `succede_a_hors_porte` (H4, Q3 of the 2026-08-16 audit): only `merge_plan` sees both
    # the door and the arc at once, so only the fold can compare the two and name the stray.
    produced |= {
        p.kind
        for p in fold_plan(
            plan(*HEAD, "- `plan/arc-c.md` — an arc"),
            ("plan/arc-c.md",),
            lambda _member: ("**Succède à** : archive/plan-v1.md\n- **A1** \U00002B1C x\n", ""),
        ).problems
    }
    # `arc_illisible` comes from the REGISTRY: an arc that exists on disk and refuses to open. It
    # is built from a CONSTANT, which had made it invisible to the literal-scan
    # written to close this class — see the class witness at the end of the file.
    from mnemosyne.production.plan_registry import ARC_ILLISIBLE

    produced |= {ARC_ILLISIBLE}

    # The FIFTH producer — C2, *Produit* that cites only a folder. Same discipline as the
    # FOURTH: a producer left out of the union would escape both gates at once.
    from mnemosyne.production.plan_format import produit_problems

    produced |= {
        p.kind
        for p in produit_problems(
            read_plan(plan(*HEAD, "- **A1** \U00002B1C x", "  *Produit* : `plan/retires/`"))
        )
    }

    # The SIXTH producer — H4, a promotion's lineage. Lives in `plan_archive`, a module
    # that imports this one (same reason as the FOURTH): the union is declared HERE.
    from mnemosyne.production.plan_archive import filiation_problems

    produced |= {
        p.kind
        for p in filiation_problems(
            read_plan(plan(*HEAD, "- **A1** \U00002B1C never taken up again")),
            read_plan(plan(*HEAD, "- **B1** \U00002B1C brand new")),
        )
    }

    assert produced == set(ALL_REFUSAL_KINDS), (
        f"declared and never produced: {sorted(set(ALL_REFUSAL_KINDS) - produced)} · "
        f"produced and never declared: {sorted(produced - set(ALL_REFUSAL_KINDS))}"
    )


def test_the_spec_page_names_EXACTLY_the_refusals_the_reader_can_raise():
    """The page's refusal table and the code's vocabulary, compared as SETS.

    Both of the folder-form refusals were added to that table BY HAND. Nothing checked it, which is
    the shape of every register that has rotted in this repo — including the one the sibling project wrote about
    itself. The page is the contract handed to frontier agents: a refusal it forgets is one nobody
    knows can block their commit, and one it invents is a rule nobody can trigger.
    """
    from mnemosyne.production.plan_format import ALL_REFUSAL_KINDS

    page = SPEC.read_text(encoding="utf-8")
    named = {kind for kind in ALL_REFUSAL_KINDS if f"`{kind}`" in page}
    assert named == set(ALL_REFUSAL_KINDS), (
        f"absent from docs/FORMAT_PLAN.md: {sorted(set(ALL_REFUSAL_KINDS) - named)}"
    )


def test_a_door_MENTIONING_the_arcs_directory_in_prose_is_not_accused_of_a_dangling_entry():
    """The space tolerance must not become a false accusation. Measured before it was written.

    `_ARC_REF_RE` deliberately lets a space through, because 1775 of the 8165 paths under
    ``projects/`` carry one — without that, an arc named ``my arc.md`` could never be seen at all.
    The cost is that an ordinary sentence mentioning the directory can run into the next
    ``.md`` on the line. A control that punishes correct use is a control people delete.
    """
    from mnemosyne.production.plan_format import index_problems

    prose = (
        "> The arcs live in plan/ and the complete form is FORMAT_PLAN.md.\n- plan/arc-c.md\n"
    )
    assert index_problems(prose, ("arc-c.md",)) == ()
    # And it still BITES on a real entry that carries a space and points at nothing.
    ghost = index_problems("- plan/my missing arc.md\n- plan/arc-c.md\n", ("arc-c.md",))
    assert [(p.kind, p.detail) for p in ghost] == [("index_sans_fichier", "plan/my missing arc.md")]


def test_the_THREE_roles_require_three_DIFFERENT_things_and_each_is_checked_here():
    """The truth table of the scission, in the module that owns it — not in a distant consumer.

    Measured, and it is why this test exists: sabotaging ``ROLE_PORTE`` to demand items as well left
    the ENTIRE plan-format, plan-registry and plan-folder suites green (91 passed). The only thing
    that reddened, over the whole repo, was one archiver test three modules away. A rule whose only
    proof lives in a consumer is a rule that survives its own module being rewritten — and the
    consumer's author has no reason to think they are guarding it.

    Asserted as a complete table rather than case by case: a role that silently required NOTHING
    would be a rubber stamp, and it would look exactly like a role that passes.
    """
    from mnemosyne.production.plan_format import (
        ROLE_ARC,
        ROLE_PLAN,
        ROLE_PORTE,
        unreadable_reasons,
    )

    door = read_plan(plan("# PLAN — x", "", "> **Cap** : make progress", "", "see plan/arc-c.md"))
    arc = read_plan(plan("## Arc C", "", "- **C1** \U00002B1C an item"))
    both = read_plan(plan(*HEAD, "- **C1** \U00002B1C an item"))
    empty = read_plan("")

    assert (bool(door.cap), bool(door.items)) == (True, False), "fixture: a door has no items"
    assert (bool(arc.cap), bool(arc.items)) == (False, True), "fixture: an arc has no cap"

    ok = {
        (ROLE_PORTE, "door"): door,
        (ROLE_ARC, "arc"): arc,
        (ROLE_PLAN, "plan"): both,
        (ROLE_PORTE, "plan-mono"): both,
        (ROLE_ARC, "plan-mono"): both,
    }
    for (role, why), reading in ok.items():
        assert unreadable_reasons(reading, role=role) == (), (role, why)

    refused = {
        (ROLE_PORTE, "arc"): arc,
        (ROLE_ARC, "door"): door,
        (ROLE_PLAN, "door"): door,
        (ROLE_PLAN, "arc"): arc,
        (ROLE_PORTE, "empty"): empty,
        (ROLE_ARC, "empty"): empty,
        (ROLE_PLAN, "empty"): empty,
    }
    for (role, why), reading in refused.items():
        assert unreadable_reasons(reading, role=role) != (), (role, why)
    # An unknown role must RAISE, never default to something permissive: a typo'd role meaning
    # "requires nothing" would turn the whole check into a rubber stamp, and it would look green.
    with pytest.raises(ValueError):
        unreadable_reasons(both, role="porte ")


def test_a_FOLDER_level_refusal_does_not_pretend_to_have_a_line():
    """``line 0`` reads like a location and is not one. An arc named nowhere has no line to point at.

    Not cosmetic: this is the string the pre-commit barrier prints back to whoever is being refused,
    and it was measured in the hook's real output before it was fixed —
    ``line 0 : arc_hors_index -- plan/forgotten arc.md``. A refusal that does not say WHERE is a
    refusal nobody can act on.
    """
    from mnemosyne.production.plan_format import index_problems

    (orphan,) = index_problems("no mention at all", ("arc-c.md",))
    assert orphan.line == 0 and "line 0" not in orphan.where, orphan.where
    assert "folder" in orphan.where
    # A line-level refusal still says its line, and its file when it has one.
    line_level = read_plan(plan(*HEAD, "- **A1** \U0001F195 x"), origin="plan/arc-c.md").problems[0]
    assert line_level.where == "plan/arc-c.md line 5", line_level.where


def test_a_MONO_FILE_plan_writing_about_arcs_in_prose_is_not_accused_of_a_dangling_entry():
    """A plan with no ``plan/`` directory has no index to verify. Measured by being bitten.

 This barrier refused the very commit that was documenting it: the plan quoted a fake arc path as
 EVIDENCE (``plan/arc oublié.md``, inside a sentence explaining a bug) and the check read the
 quotation as an index entry pointing nowhere. A control that punishes correct use is a control
 people delete — and this one had just refused its own author, on its own documentation.

 ``arc_hors_index`` is NOT suppressed by the same flag, and that asymmetry is the point: it needs
 a file that really exists on disk, so no amount of prose can trigger it.

 The prose half is now guarded TWICE, and this test pins both layers separately so neither can
 be removed under cover of the other. ``folder_form`` alone was never enough: it suppressed the
 refusal only for a plan that is one FILE, so the same paragraph, in the same document, became an
 accusation the day the plan grew a ``plan/`` directory — which is precisely what C20-4 measured
 and what would have blocked the conversion. The entry rule is the layer that makes prose
 incapable of declaring anything, in EITHER mode.
 """
    from mnemosyne.production.plan_format import index_problems

    prose = "The hook cited `plan/forgotten arc.md` and printed 0 — see plan/arc-fantome.md too.\n"
    for form in (True, False):
        assert index_problems(prose, (), folder_form=form) == (), form
    # And ``folder_form`` still governs a REAL entry — a bullet, which is a declaration, not a
    # mention. Suppressed on a one-file plan (no index to verify), refused once it is a folder.
    entry = "- plan/arc-fantome.md — an arc that does not exist\n"
    assert index_problems(entry, (), folder_form=False) == ()
    assert [p.kind for p in index_problems(entry, (), folder_form=True)] == ["index_sans_fichier"]
    # And the file-backed refusal bites in BOTH modes — prose can never fabricate it.
    for form in (True, False):
        orphan = index_problems("no mention at all", ("arc-c.md",), folder_form=form)
        assert [p.kind for p in orphan] == ["arc_hors_index"], form


# ── A6 · THE MOVED POPULATION: what a floor drawn from production held ──────────────────────────
# Three gates drew their size from the LIVING PLAN (arcs ≥ 8, bullets ≥ 40, glyphs outside the BMP
# ≥ 10) and reddened because it had SHRUNK — with no fault of its own to answer for. A control drawn
# from production makes production unmodifiable; the repo physically resisted its own
# replanning. The two witnesses below take the guarantee onto a size that is
# sufficient and GUARANTEED BY CONSTRUCTION, so the living plan becomes free to change shape again.


def test_the_SYNTHETIC_door_catches_an_undeclared_arc(tmp_path: Path) -> None:
    """ The property that the `arcs >= 8` floor protected, proven on TWELVE built arcs.

 The set equality between what the disk carries and what the door DECLARES must redden the moment
 ONE arc goes missing — and stay silent when they are all there. The first case is the bite,
 the second is the innocent: without it, an equality that always failed would pass the first.
 """
    arcs_dir = tmp_path / "plan"
    arcs_dir.mkdir()
    names = [f"arc-{i:02d}.md" for i in range(12)]
    for name in names:
        (arcs_dir / name).write_text(f"# {name}\n", encoding="utf-8")

    def door(declares: list[str]) -> Path:
        path = tmp_path / "PLAN.md"
        lines = ["# PLAN — demo", "", "> **Cap** : prove", ""]
        lines += [f"- `plan/{name}` — arc" for name in declares]
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return path

    complete = _declared_refs(door(names).read_text(encoding="utf-8"))
    assert complete == set(names), "the INNOCENT: twelve arcs declared, no fault found"

    amputated = _declared_refs(door(names[:-1]).read_text(encoding="utf-8"))
    assert set(names) - amputated == {names[-1]}, (
        "an arc present on disk and NOT declared must come out NAMED — a count would say "
        "« 11 of 12 » without ever saying which one slipped"
    )


def test_the_bullet_COUNTER_holds_at_real_size_on_a_fixture() -> None:
    """ What the `bullets >= 40` floor REALLY protected: that the walk does not collapse.

 The guard existed because the property "no bullet stays silent" would have gone GREEN-AND-EMPTY
 the day the plan became a folder and the door stopped carrying the bullets. So it was not the
 BITE it held, it was the COUNTER — and a counter is proven on a built population,
 never on the one that has the right to shrink.

 AND WHAT COULD NOT BE BUILT IS SAID HERE RATHER THAN KEPT QUIET: **nine shapes of silent
 bullet were tried, not one of them stays silent** — `_read_item` returns an item or a problem in
 all nine cases (a bare `- **A1** `, without bold, without a title, with italics, glyph stuck to
 the word…). That is information about the mechanism (it is robust), not a hidden gap: the "the
 silent one comes out" half of this property therefore stays UNTESTED, and saying so beats a
 witness that would fake it.
 """
    from mnemosyne.production.plan_format import (
        _BOLD_TOKEN_RE,
        _BULLET_RE,
        _despecify,
        _read_item,
    )

    bullets = [f"- **A{i}** \u2705 **A well-formed item.**" for i in range(1, 51)]
    text = "\n".join(["# PLAN \u2014 demo", "", "> **Cap** : prove", "", *bullets]) + "\n"

    examined, silent = 0, []
    for offset, raw in enumerate(text.splitlines()):
        bullet = _BULLET_RE.match(raw)
        if bullet is None or bullet.group(1):
            continue
        loose = _BOLD_TOKEN_RE.match(bullet.group(2))
        if loose is None or not _is_glyph_shaped(_despecify(loose.group(2).strip())[:1]):
            continue
        examined += 1
        item, problem, _ = _read_item(bullet.group(2), line_no=offset + 1)
        if item is None and problem is None:
            silent.append(raw)

    assert examined >= 40, (
        f"{examined} bullets seen out of 50 built — the walk collapsed, and this is "
        f"exactly the accident the floor drawn from the living plan existed to catch"
    )
    assert silent == [], silent


# --- THE SIX FIELDS (A1) -------------------------------------------------------------------------
#
# What item A1 asks for, word for word: "a test item carrying the six fields reads back field
# by field identically; an absent field is NAMED, never guessed". Both halves are here, and
# the second is the one a lenient reader fails silently.

#: THE REFERENCE, written by hand — never derived from the reader it judges. The witness plan is
#: built FROM it (the input derives from the reference, the reverse would be a tautology).
SIX_FIELDS: dict[str, str] = {
    "produit": "`plan_format.py` — the field reader",
    "fini_quand": "`make plans` stays green at every level",
    "depend_de": "AUCUNE",
    "prerequis": "AUCUN",
    "a_lire": "`docs/FORMAT_PLAN.md` · a real arc from the sibling project",
    "taille": "1 file · 1 measurement over the sibling project's 168 items",
}


def test_the_witness_covers_the_WHOLE_vocabulary_not_a_sample_of_it():
    """SETS, never counts — a seventh field cannot be born without its witness.

    ``len(SIX_FIELDS) == 6`` would have let one field added and another removed pass in the same
    edit. That is the lesson already paid for here: freeze the SET, never the COUNT.
    """
    from mnemosyne.production.plan_format import FIELD_NAMES

    from mnemosyne.production.plan_format import EXTRA_FIELD_NAMES, KNOWN_FIELDS

    assert set(KNOWN_FIELDS) == set(FIELD_NAMES) | set(EXTRA_FIELD_NAMES)
    assert not (set(FIELD_NAMES) & set(EXTRA_FIELD_NAMES)), "a field cannot be both"
    assert set(SIX_FIELDS) == set(FIELD_NAMES), (
        f"no witness: {sorted(set(FIELD_NAMES) - set(SIX_FIELDS))} · "
        f"witness with no field: {sorted(set(SIX_FIELDS) - set(FIELD_NAMES))}"
    )


def test_an_item_carrying_the_six_fields_reads_back_field_by_field_IDENTICALLY():
    """Half 1 of A1's `*Fini quand*` clause — and it reads back FIELD BY FIELD.

    Comparing all six at once would say "it differs" without saying which one; comparing field by
    field names the culprit. The declaration ORDER is checked in addition to the value: two fields
    whose values were swapped would pass a set comparison.
    """
    from mnemosyne.production.plan_format import FIELD_NAMES

    text = plan(
        *HEAD,
        "- **A1** \U00002B1C The foundation of the plan.",
        *(f"  *{FIELD_NAMES[token]}* : {value}" for token, value in SIX_FIELDS.items()),
    )
    (item,) = read_plan(text).items

    for token, expected in SIX_FIELDS.items():
        assert item.field(token) == expected, f"{token} : {item.field(token)!r} != {expected!r}"
    assert item.declared_fields == tuple(SIX_FIELDS)
    assert item.missing_fields == ()
    assert item.blank_fields == ()


def test_an_ABSENT_field_is_NAMED_and_never_guessed_into_an_empty_string():
    """Half 2, and it is the one holding up everything else.

 ``None`` (never declared) and ``""`` (declared, empty) are TWO answers. A reader that
 collapses them renders a question never asked indistinguishable from a question with no answer
 — *two absences of measurement compare equal* — and the plan looks complete. Both populations
 are therefore drawn from the SAME witness, or one would cover for the other.
 """
    text = plan(
        *HEAD,
        "- **A1** \U00002B1C An item declaring only two fields, one of them EMPTY.",
        "  *Produit* : the reader",
        "  *Taille* :",
    )
    (item,) = read_plan(text).items

    assert item.field("produit") == "the reader"
    assert item.field("taille") == "", "a field declared and empty is not an absent field"
    assert item.field("prerequis") is None, "a field never declared must return None, never ''"
    assert item.missing_fields == ("Fini quand", "Dépend de", "Prérequis", "À lire")
    assert item.blank_fields == ("Taille",)


def test_asking_for_a_field_that_does_not_exist_RAISES_instead_of_answering_absent():
    """A mistyped token that returned "absent" would let a caller check a field that does not exist
    and see green. The same reasoning as the unknown role of ``unreadable_reasons``."""
    text = plan(*HEAD, "- **A1** \U00002B1C x", "  *Produit* : y")
    (item,) = read_plan(text).items

    with pytest.raises(ValueError, match="unknown field"):
        # The example used to be `"obligation"` — it became a REAL field on 2026-08-15, and this
        # witness reddened on the spot. That is the right behaviour: an example token chosen
        # "because it doesn't exist" goes stale the day somebody makes it exist.
        item.field("champ_qui_n_existe_pas")


def test_the_field_NAME_is_read_with_its_accents_folded_and_the_VALUE_never_is():
    """`Depend de` beats `Dépend de` 65 to 46 in this repo — the NAME folds, the value NEVER does.

    This module already paid for a filter wider than its name: a plan written in NFD came back with
    its title stripped of its accents. The fold is therefore bounded to the NAME, and the accented
    value is asserted here so that widening it would redden.
    """
    text = plan(
        *HEAD,
        "- **A1** \U00002B1C x",
        "  *Depend de* : A2 — the declared precedence (préséance)",
        "  **Fini quand** : the command SUCCEEDS",
        "  _Taille_ : three elements",
    )
    (item,) = read_plan(text).items

    assert item.field("depend_de") == "A2 — the declared precedence (préséance)"
    assert item.field("fini_quand") == "the command SUCCEEDS", (
        "`**X**` is the shape of 2 real items"
    )
    assert item.field("taille") == "three elements"


def test_a_field_written_ON_THE_BULLET_LINE_is_read_and_the_title_is_NOT_shortened():
    """61 head bullets of this repo declare a field on the item's own line — the sibling project's shape.

    And the second assertion is the non-regression contract: ``title`` is read by 61 sites, so
    the reader ADDS the fields without REMOVING anything from the title. A reader that had
    "cleaned up" the title would have broken all 61 to gain nothing.
    """
    body = "**A07-3** \U00002B1C **What an algorithm returns.** *Produit* : a `Scenario`"
    text = plan(*HEAD, f"- {body}")
    (item,) = read_plan(text).items

    assert item.field("produit") == "a `Scenario`"
    assert item.title == "**What an algorithm returns.** *Produit* : a `Scenario`"


def test_a_value_stops_at_the_NEXT_field_and_never_swallows_its_neighbour():
    """70 lines of this repo carry two markers or more. A value that swallowed its neighbour would
 make the reader the author of a declaration nobody wrote.

 **The punctuation between the two is not decoration on the witness, it is the rule**: the
 second marker must carry a decoration in front of it, or it is a MENTION ("if the *Fini quand*
 is a command"). The shape written here is the sibling project's own, verbatim from `A07-3`: a sentence
 closed by a period, then the next field. Residual named: a field stuck right behind a bare word
 (``the reader *Fini quand* :``) reads as ABSENT — measured, this repo never writes it (the 10
 occurrences of that shape are all mentions).
 """
    text = plan(*HEAD, "- **A1** \U00002B1C t. *Produit* : the reader. *Fini quand* : green. *Taille* : 1")
    (item,) = read_plan(text).items

    assert item.field("produit") == "the reader."
    assert item.field("fini_quand") == "green."
    assert item.field("taille") == "1"


def test_a_value_wrapped_over_three_lines_reads_back_as_the_ONE_clause_it_is():
    """The line wrap is the editor's, not the author's: `*Fini quand*` runs
    three lines on arc A of this plan. The only normalisation applied, and it is here so that
    the read-back equality is not a fluke of layout."""
    text = plan(
        *HEAD,
        "- **A1** \U00002B1C t.",
        "  *Fini quand* : `make plans` stays green at every level **and** a test item carrying",
        "  the six fields reads back field by field identically ; an absent field is",
        "  **named**, never guessed",
        "  *Taille* : 1 file",
    )
    (item,) = read_plan(text).items

    assert item.field("fini_quand") == (
        "`make plans` stays green at every level **and** a test item carrying the six fields "
        "reads back field by field identically ; an absent field is **named**, never guessed"
    )
    assert item.field("taille") == "1 file"


#: The number of arcs `docs/plan/` carries, frozen here and **guarded by a meta-witness** below.
#:
#: **A floor written as a literal inside an assertion guards NOTHING**: lowering it to zero
#: reddens nobody, since nothing else looks at it — measured, the mutation survived the whole
#: suite. This repo already has the shape that works (`DETTE_SANS_BARRIERE`, frozen by
#: `test_memoire_cliquet.py`): a named constant, plus a witness that compares it to the real thing.
PLAN_ARCS_FLOOR = 12

#: The MENTIONS measured over the repo's 320 documents, one per real shape — the corpus of
#: FALSE accusations the colon rule must keep refusing. Named rather than
#: anonymous: a shape that is the ONLY witness of its alternative must not be able to disappear
#: in silence in a two-line edit.
FIELD_MENTIONS: tuple[tuple[str, str], ...] = (
    ("backtick", "the `*Fini quand*` field : it decides"),  # 174 times in the repo
    ("word in front", "`F3` says *Fini quand* : this"),  # 10 times, all mentions
    ("article in front", "has no token in the *Fini quand* : it is a wish"),
    ("dash", "the very heart of the *Produit* — has no value"),  # 3 false out of 9
    ("followed by a word", "if the *Fini quand* is a command"),  # 91 times
    ("comma", "the *Produit*, then the size"),  # 36 times
)


@pytest.mark.parametrize(("shape", "line"), FIELD_MENTIONS, ids=[s for s, _ in FIELD_MENTIONS])
def test_a_field_name_MENTIONED_in_a_sentence_never_becomes_a_declaration(shape: str, line: str):
    """*A catch rate without its false-accusation rate is a wall.*

    Each of these six shapes really exists in this repo, and each is PROSE. A reader
    that took them would publish fields nobody wrote — exactly what the
    "never guessed" clause forbids.
    """
    text = plan(*HEAD, "- **A1** \U00002B1C a title.", f"  {line}")
    (item,) = read_plan(text).items

    assert item.fields == (), f"shape « {shape} » read as a declaration: {item.fields}"


def test_the_MENTION_corpus_cannot_be_emptied_without_a_test_going_red():
    """The same freeze as ``CONTROL_NAMES``: 60 witnesses out of 60 have already left here with no red."""
    assert {shape for shape, _ in FIELD_MENTIONS} == {
        "backtick",
        "word in front",
        "article in front",
        "dash",
        "followed by a word",
        "comma",
    }


def test_the_six_fields_are_read_off_THIS_repos_own_arc_and_not_only_off_a_fixture():
    """The regression against the REAL corpus — versioned, so present on every clone.

    A grammar proven only against the fixture it was extracted from proves nothing. Arc A of
    this plan carries the six fields on its six items; it is the first arc written to the standard,
    and it is what A1 must be able to read back.
    """
    text = (REPO / "docs/plan/00-le-socle-du-plan.md").read_text(encoding="utf-8")
    reading = read_plan(text)

    # >= , not == : this arc grows (A7 arrived after this witness) — a strict equality is an
    # enumeration that goes stale on the very first extra item, for a test that checks nothing about THE COUNT.
    assert len(reading.items) >= 6, reading.items
    for item in reading.items:
        assert item.missing_fields == (), f"{item.ident} : missing fields {item.missing_fields}"
        assert item.blank_fields == (), f"{item.ident} : blank fields {item.blank_fields}"
    a1 = reading.items[0]
    assert a1.field("depend_de") == "AUCUNE"
    assert a1.field("prerequis") == "AUCUN"


@needs_project_docs
def test_the_reader_finds_the_FOUR_sibling_fields_and_names_the_TWO_that_are_missing_everywhere():
    """The measurement the `*Taille*` of A1 requires: the sibling project's 168 items, read back by this reader.

 **This is the number that settles the obligation debate, and it is measured, not feared**:
 ``Prérequis`` and ``À lire`` are declared by **0 items out of 168**. A gate requiring all six
 fields today would refuse **168 items out of 168** — exactly the wall arc A explicitly
 forbids (*"we publish, we do not punish what already exists"*). The reader NAMES; it does not refuse.
 """
    from mnemosyne.production.plan_format import FIELD_NAMES

    root = REPO / "projects/saas/Sibling Research"
    if not root.is_dir():
        pytest.skip("Sibling Research absent from this clone (projects/ is gitignored by design)")

    items = [
        item
        for md in sorted(root.rglob("*.md"))
        if "/plan/" in str(md) or md.name == PLAN_FILENAME
        for item in read_plan(md.read_text(encoding="utf-8")).items
    ]
    assert len(items) >= 150, f"{len(items)} items read — the walk collapsed"

    declared = {
        token: sum(1 for it in items if it.field(token) is not None) for token in FIELD_NAMES
    }
    assert declared["produit"] > len(items) // 2, f"Produit : {declared['produit']}/{len(items)}"
    assert declared["fini_quand"] > len(items) // 2, f"Fini quand : {declared['fini_quand']}"
    assert declared["prerequis"] == 0, "Prérequis has stopped being absent everywhere — remeasure A1"
    assert declared["a_lire"] == 0, "À lire has stopped being absent everywhere — remeasure A1"
    assert all("Prérequis" in it.missing_fields for it in items), "an absent one left unnamed"


# --- WHAT A THIRD-PARTY AUDIT FALSIFIED (A1, second pass) ---------------------------------------
#
# The 17 witnesses above let SIX mutations through. What each one taught is here, and
# each test names the mutation it kills. A witness that passes for the WRONG reason is a
# witness that holds nothing: the dash one used to redden thanks to the bare-word guard, never thanks to
# the colon rule it claimed to freeze.


def test_a_value_stops_at_a_BLANK_LINE_and_never_swallows_the_paragraph_below():
    """M-D1 · the severe defect the audit found: 235 values out of 665 exceeded 400 characters
    and one reached **15,015**, because an open field only closed at the next marker."""
    text = plan(
        *HEAD,
        "- **A1** \U00002B1C t.",
        "  *Produit* : the field reader",
        "",
        "  A paragraph talking about something else and belonging to no field.",
    )
    (item,) = read_plan(text).items

    assert item.field("produit") == "the field reader"


def test_a_value_stops_at_a_FENCE_and_the_fence_CONTENT_is_never_read_as_a_declaration():
    """M-D2 · an item that SHOWS the shape to write used to see its example published as a real field.

    This is the exact shape ``make plan-emit`` teaches frontier models: the page that specifies the
    format would have had its own examples read back as declarations.
    """
    text = plan(
        *HEAD,
        "- **A1** \U00002B1C an item that shows the shape.",
        "  *Produit* : the reader",
        "  ```markdown",
        "  - **X1** \U00002B1C title",
        "    *Fini quand* : WHAT NOBODY DECLARED HERE",
        "  ```",
    )
    (item,) = read_plan(text).items

    assert item.field("produit") == "the reader"
    assert item.field("fini_quand") is None, "an EXAMPLE field is not a declaration"


def test_a_value_stops_at_a_line_OPENING_on_a_pictograph_but_NOT_on_one_mid_line():
    """M-D1 (continued) · the boundary measured, AND its safeguard.

 A pictograph AT THE HEAD of a line opens a new block (`` **…**``): 6 cuts out of 6 sampled
 are correct. The same glyph in the MIDDLE of a line is ordinary emphasis — and it lives in the
 `*Fini quand*` of item `A6` of this very plan. Both populations in one witness, or
 one would cover for the other.
 """
    text = plan(
        *HEAD,
        "- **A1** \U00002B1C t.",
        "  *Produit* : the reader, judged **blind** by a",
        "  third party. \U000026D4 **A glyph mid-line stays emphasis** and closes nothing.",
        "  \U000026D4 **BUT AT THE HEAD OF A LINE it opens a block**, and that one is no longer the field.",
    )
    (item,) = read_plan(text).items

    assert item.field("produit") == (
        "the reader, judged **blind** by a third party. "
        "\U000026D4 **A glyph mid-line stays emphasis** and closes nothing."
    )


def test_a_wrapped_sentence_continuing_on_BOLD_is_NOT_cut_because_bold_is_not_a_boundary():
    """M-D1 (the REFUSED false positive) · admitting `**` at the head would have cut harder — and wrong.

    Measured: 2 cuts out of 5 sampled were false, on sentences the editor had
    simply wrapped. *A catch rate without its false-cut rate is a wall.*
    """
    text = plan(
        *HEAD,
        "- **A1** \U00002B1C t.",
        "  *Fini quand* : counting the term across the repo yields",
        "  **a single sense** (the rule of arc 00 `F2`), and nothing else",
    )
    (item,) = read_plan(text).items

    assert item.field("fini_quand") == (
        "counting the term across the repo yields **a single sense** (the rule of arc 00 `F2`), "
        "and nothing else"
    )


def test_the_DASH_form_really_is_refused_by_the_COLON_rule_and_not_by_its_neighbour():
    """M2 / M8 · the mutant that SURVIVED the first 17 witnesses.

 **The original "dash" witness passed for the wrong reason**: it reddened thanks to the
 bare-word guard in front, never thanks to the colon rule. Accepting the dash as a separator
 left the 17 green. Here the shape is the sibling project's own — `` *Fini quand* — **the command…** ``,
 6 real lines — a PICTOGRAPH in front, so the bare-word guard CANNOT catch it: only
 the colon rule refuses it.

 This test freezes an ACCEPTED RESIDUAL, not a victory: these 6 lines carry a real field and
 read as ABSENT. That is the measured price of refusing the dash (3 false declarations out of 9
 otherwise), and it is written here so it gets reversed knowingly, never by accident.
 """
    text = plan(
        *HEAD, "- **A1** \U00002B1C t.", "  \U000025B6 *Fini quand* — **the command carries its own arms**"
    )
    (item,) = read_plan(text).items

    assert item.field("fini_quand") is None, "the dash became a separator — 3 false out of 9"
    assert item.fields == ()


def test_a_field_declared_TWICE_keeps_the_FIRST_and_the_corpus_cannot_prove_it():
    """M7 · surviving mutant. The corpus counts **0** repetitions, so nothing could exercise it.

    A rule held only by a docstring is a wish: *a mechanism that never bites proves
    nothing*. The witness supplies the population reality does not have.
    """
    text = plan(
        *HEAD,
        "- **A1** \U00002B1C t.",
        "  *Produit* : THE FIRST ANSWER",
        "  *Produit* : the second, which must not overwrite the first",
    )
    (item,) = read_plan(text).items

    assert item.field("produit") == "THE FIRST ANSWER"
    assert item.declared_fields == ("produit",), "a duplicate does not create a second field"


def test_declaration_order_is_the_order_WRITTEN_and_not_the_order_of_the_vocabulary():
    """M17 · surviving mutant, and the cause is a DEGENERATE population.

    The first witness built its input from ``SIX_FIELDS``, whose keys carry exactly
    the order of ``FIELD_NAMES``: "order written" and "vocabulary order" were the same
    string there, so the assertion could distinguish nothing. Here the order written is deliberately
    the REVERSE — *test differentiation, never conformity.*
    """
    from mnemosyne.production.plan_format import FIELD_NAMES

    written = tuple(reversed(tuple(FIELD_NAMES)))
    text = plan(
        *HEAD,
        "- **A1** \U00002B1C t.",
        *(f"  *{FIELD_NAMES[token]}* : value of {token}" for token in written),
    )
    (item,) = read_plan(text).items

    assert item.declared_fields == written
    assert item.declared_fields != tuple(FIELD_NAMES), (
        "degenerate witness: both orders coincide"
    )


def test_no_field_NAME_can_outgrow_the_bound_that_reads_it():
    """M14 · the mutant survives because widening the bound changes NOTHING observable — a name outside
    the vocabulary is never a field. The real risk is the reverse, and that is what gets frozen:
    a SEVENTH field whose name exceeded the bound would be **silently unreadable**."""
    from mnemosyne.production.plan_format import FIELD_NAMES, FIELD_MARKER_RE

    longest = max(FIELD_NAMES.values(), key=len)
    assert FIELD_MARKER_RE.match(f"*{longest}* :"), f"« {longest} » exceeds the reader's bound"


@needs_project_docs
def test_no_value_of_the_REAL_corpus_runs_away_again():
    """The barrier against D1's return, set against the corpus that revealed it.

    Before the repair: **98 values above 2,000 characters, the worst at 15,015**. After:
    **7 and 3,812**, and the 7 are genuinely long clauses. The ceiling sits above the real
    measured value, not on top of it: it catches a leak, it does not punish a wordy author.
    """
    root = REPO / "projects"
    if not any(root.rglob("*.md")):
        pytest.skip("projects/ empty on this clone")

    longest = max(
        (
            (len(value), item.ident, token)
            for md in root.rglob("*.md")
            for item in read_plan(md.read_text(encoding="utf-8", errors="replace")).items
            for token, value in item.fields
        ),
        default=(0, "", ""),
    )
    assert longest[0] < 6000, f"a value leaked: {longest}"


def test_the_versioned_corpus_ALSO_pins_the_ceiling_so_the_guarantee_is_not_owner_only():
    """The audit named D8: the only wide witness only ran on the operator's machine.

    ``docs/plan/`` is versioned, so present on every clone. The ceiling's guarantee is
    replayed there — smaller, but inherited by everyone. *A guarantee that only runs on one
    machine is a guarantee nobody else inherits.*
    """
    values = [
        (len(value), item.ident, token)
        for md in sorted((REPO / "docs/plan").rglob("*.md"))
        for item in read_plan(md.read_text(encoding="utf-8")).items
        for token, value in item.fields
    ]
    assert len(values) >= 30, f"{len(values)} values — the versioned corpus emptied out"
    assert max(values)[0] < 1200, f"a value leaked into the versioned corpus: {max(values)}"


# --- A3 · THE `*Prérequis*` FIELD — external to the plan, NEVER frees itself on its own ---------


def test_the_four_tokens_of_the_closed_vocabulary_are_read_and_AUCUN_is_free():
    """The vocabulary is CLOSED, and `AUCUN` costs nothing — *the question is obliged, never the answer.*"""
    from mnemosyne.production.plan_format import PREREQUISITE_HOLDERS, prerequisite_problems

    text = plan(
        *HEAD,
        *(
            line
            for i, token in enumerate(PREREQUISITE_HOLDERS, start=1)
            for line in (f"- **A{i}** \U00002B1C t.", f"  *Prérequis* : {token} — the tail is free")
        ),
    )
    reading = read_plan(text)

    assert [item.prerequisite for item in reading.items] == list(PREREQUISITE_HOLDERS)
    assert prerequisite_problems(reading) == (), "a vocabulary token is never refused"
    assert [item.startable for item in reading.items] == [True, False, False, False]


def test_a_prerequisite_written_as_LIFTED_reads_AUCUN_because_that_is_how_A4_writes_it():
    """The REAL shape of item `A4` in this plan: ``*Prérequis* : **AUCUN — LIFTED on 2026-08-13.**``

    The bold and the dash are decoration; the token sits underneath. A reader that stumbled on the
    two asterisks would render NOT STARTABLE an item whose arbitration HAS been rendered — and the
    operator's queue would start lying in the most costly direction: demanding a gesture he already made.
    """
    text = plan(*HEAD, "- **A4** \U00002B1C t.", "  *Prérequis* : **AUCUN — LIFTED on 2026-08-13.**")
    (item,) = read_plan(text).items

    assert item.prerequisite == "AUCUN"
    assert item.startable is True
    assert item.blocked_by == ""


def test_OWNER_names_a_ROLE_and_never_a_person_because_two_other_projects_have_no_Owner():
    """The *three-way test* applied to this field: `OWNER` is "the human guardian of THIS project".

    Written as a name, the field would be unreadable at the factory and at Example Research. The output must
    therefore name a ROLE — and that is asserted, or the promise lives in a docstring nothing holds up.
    """
    from mnemosyne.production.plan_format import PREREQUISITE_HOLDERS

    text = plan(*HEAD, "- **A1** \U00002B1C t.", "  *Prérequis* : OWNER — he must type the word live")
    (item,) = read_plan(text).items

    assert item.startable is False
    # The CONSTANT, never a copy of its wording: what this witness holds is that the surface prints
    # the ROLE the table declares — so it survives the next pass over that sentence instead of
    # having to be retyped, and it still reddens the day the surface stops printing it at all.
    assert PREREQUISITE_HOLDERS["OWNER"] in item.blocked_by, "the output must name WHO can lift it"
    assert "Owner" not in PREREQUISITE_HOLDERS["OWNER"], "a hardcoded proper name would make the field local"


def test_an_ABSENT_prerequisite_is_REFUSED_and_the_refusal_names_the_way_out():
    """"an absent field is refused" — A3's clause, and the message carries its own way out.

    *The refusal message names the way out*: it lists the vocabulary and says `AUCUN` is free.
    A refusal that leaves you searching is a refusal people route around.
    """
    from mnemosyne.production.plan_format import prerequisite_problems

    text = plan(*HEAD, "- **A1** \U00002B1C an item that declares nothing.")
    (problem,) = prerequisite_problems(read_plan(text))

    assert problem.kind == "prerequis_manquant"
    assert "AUCUN" in problem.detail and "valid and free" in problem.detail
    assert "A1" in problem.detail, "a refusal that cannot be localised is almost a silence"


def test_a_token_OUTSIDE_the_vocabulary_is_named_and_not_confused_with_an_absence():
    """M · "unknown" and "absent" are TWO defects and TWO repairs.

    Collapsing them would render a typo indistinguishable from a silence — the same fault as ``None``
    versus ``""`` on fields, a population further below.
    """
    from mnemosyne.production.plan_format import prerequisite_problems

    text = plan(*HEAD, "- **A1** \U00002B1C t.", "  *Prérequis* : PEUT-ETRE — we shall see")
    reading = read_plan(text)
    (problem,) = prerequisite_problems(reading)

    assert reading.items[0].prerequisite == "PEUT-ETRE", "the faulty token reads back, so it can be named"
    assert problem.kind == "prerequis_inconnu"
    assert "PEUT-ETRE" in problem.detail


def test_silence_is_NOT_permission_to_start():
    """ The asymmetry that carries the whole field: an item that declares nothing is NOT startable.

 The opposite — silence counting as "go ahead" — is exactly *validating on a hypothesis*,
 the very thing this field exists to make impossible.
 """
    text = plan(*HEAD, "- **A1** \U00002B1C a mute item.")
    (item,) = read_plan(text).items

    assert item.prerequisite is None
    assert item.startable is False
    assert "prerequisite not declared" in item.blocked_by


def test_the_prerequisite_barrier_does_NOT_fire_from_read_plan_because_it_would_refuse_168_of_168():
    """ The measurement that DECIDES the design, and it is reproduced here rather than cited.

 Wired into the reader, the level-2 clause would refuse **168 items of the sibling project's 168** — zero of
 them declare a `*Prérequis*`. *A control that condemns everybody is the same wall as one that
 condemns nobody.* The reader stays PURE; the caller carries the scope.
 """
    text = plan(*HEAD, "- **A1** \U00002B1C no prerequisite declared anywhere")
    reading = read_plan(text)

    assert reading.problems == (), "the reader must refuse NOTHING over an absent prerequisite"
    assert reading.readable is True


def test_THIS_plans_own_arc_passes_the_level_2_barrier_it_invents():
    """*The plan that invents a rule is the one that submits to it.* The arcs, for real, on disk.

 **POPULATION FLOOR, and it was missing.** This witness's body — `prerequisite_problems(r)
 == ()` and `all(item.startable …)` — passes GREEN on **zero items**: `all()` over the empty set
 is true. An isolated audit played it against a door with no items and saw green. The day the arc
 changed shape and stopped producing items, the witness would have said nothing.
 And the population is widened to ALL of `docs/plan/`, not arc A alone: 1 file out of 11 was only
 measuring a tenth of the submission being claimed.
 """
    from mnemosyne.production.plan_format import prerequisite_problems

    seen, refused, files_seen = 0, [], set()
    for md in sorted((REPO / "docs/plan").rglob("*.md")):
        reading = read_plan(md.read_text(encoding="utf-8"))
        seen += len(reading.items)
        files_seen.add(md.name)
        refused += [(md.name, p.detail) for p in prerequisite_problems(reading)]

    # **A FLOOR ON A TOTAL ALWAYS LETS A SMALL ARC DISAPPEAR.** The 46 written here
    # was first BORROWED from a measurement of another file over a DIFFERENT population (47 counted /
    # 46 judged by another reader); applied to the 49 items here it left a margin of 3 —
    # that is, FOUR whole arcs that could evaporate in silence, including `prerequis.md`, the one that
    # carries the repo's only `OWNER` and the field this witness judges. *Freeze the SET, never the count.*
    assert files_seen >= {"prerequis.md", "00-le-socle-du-plan.md"}, sorted(files_seen)
    assert len(files_seen) >= PLAN_ARCS_FLOOR, f"{len(files_seen)} arcs read — an arc has disappeared"
    assert seen >= 46, (
        f"{seen} items read — the population collapsed, green means nothing"
    )
    assert refused == [], refused


def test_the_vocabulary_is_CLOSED_and_cannot_grow_without_a_witness():
    """Freeze the SET, never the count — a fifth token cannot enter in silence."""
    from mnemosyne.production.plan_format import PREREQUISITE_HOLDERS

    assert set(PREREQUISITE_HOLDERS) == {"AUCUN", "OWNER", "MONDE", "AUTRE-PROJET"}
    assert PREREQUISITE_HOLDERS["AUCUN"] == "", "`AUCUN` names nobody: it is free"


# --- A3, second pass: what a third-party audit falsified about the prerequisite -----------------

#: The GLUED shapes that all used to pass as `AUCUN`, `startable=True`, ZERO refusal. The vocabulary
#: was not closed: it was a PREFIX. Named one by one, never counted, so that none of
#: them could disappear in silence in a two-line edit.
GLUED_PREREQUISITES: tuple[tuple[str, str], ...] = (
    ("digit glued on", "AUCUN2"),
    ("underscore glued on", "AUCUN_UNLESS_THE_WORLD_MOVES"),
    ("wrong accent", "AUCÙN"),
    ("longer word", "AUCUNE idea"),
    # The FOUR that the lookahead `(?![A-Za-z0-9_])` let through — the class reopened by one
    # character. The dash because `[A-Za-z-]+` can BACK UP until it stops just before it; the final
    # accent because the lookahead's class was ASCII. *Close the class, not the case.*
    ("dash then underscore", "AUCUN-UNLESS_IF"),
    ("dash then digit", "AUCUN-BLOCKING2"),
    ("dash then date", "AUCUN-2026-08-13"),
    ("FINAL accent", "AUCUNÉ"),
)

#: The FREE tails that must keep passing — what follows a correct token is prose
#: for the human, by the item's own decision. The witness carries both populations, or
#: repairing the permissive side is paid for in false refusals with nothing reddening.
FREE_TAILED_PREREQUISITES: tuple[tuple[str, str, str], ...] = (
    ("lifted, the real shape of A4", "**AUCUN — LIFTED on 2026-08-13.**", "AUCUN"),
    ("dash", "AUTRE-PROJET — arc 03 will carry it", "AUTRE-PROJET"),
    ("parenthesis", "MONDE (as long as the API stays closed)", "MONDE"),
    ("period", "AUCUN.", "AUCUN"),
    ("pictograph in front", "\U000026D4 **OWNER** — he must type the word live", "OWNER"),
    ("lowercase", "aucun", "AUCUN"),
)


@pytest.mark.parametrize(
    ("shape", "value"), GLUED_PREREQUISITES, ids=[s for s, _ in GLUED_PREREQUISITES]
)
def test_a_token_GLUED_to_more_text_is_refused_and_never_read_as_the_word_it_starts_with(
    shape: str, value: str
):
    """ **THE HOLE WAS ON THE PERMISSIVE SIDE, the one that costs.**

 ``^[A-Za-z-]+`` with no lookahead is a prefix: ``AUCUN2`` used to return ``AUCUN``, ``startable``,
 zero refusal. A closed vocabulary that accepts anything STARTING WITH one of its words is
 free text wearing a schema's name — and here a typo used to become a LIFTED prerequisite.
 """
    from mnemosyne.production.plan_format import prerequisite_problems

    text = plan(*HEAD, "- **A1** \U00002B1C t.", f"  *Prérequis* : {value}")
    reading = read_plan(text)
    (item,) = reading.items

    assert item.startable is False, f"« {shape} » made an item STARTABLE"
    assert item.prerequisite != "AUCUN"
    assert [p.kind for p in prerequisite_problems(reading)] == ["prerequis_inconnu"]


@pytest.mark.parametrize(
    ("shape", "value", "token"),
    FREE_TAILED_PREREQUISITES,
    ids=[s for s, _, _ in FREE_TAILED_PREREQUISITES],
)
def test_a_correct_token_followed_by_FREE_PROSE_still_reads(shape: str, value: str, token: str):
    """The other half: closing the permissive side must not manufacture false refusals.

    Four of these shapes were REFUSED before the repair (typographic apostrophe, non-breaking
    space, zero-width space, pictograph up front) and the message accused nothing at all:
    ``A1 → '' outside the vocabulary``. *A control that punishes correct use is a control
    people delete.*
    """
    from mnemosyne.production.plan_format import prerequisite_problems

    text = plan(*HEAD, "- **A1** \U00002B1C t.", f"  *Prérequis* : {value}")
    reading = read_plan(text)
    (item,) = reading.items

    assert item.prerequisite == token, f"« {shape} » misread"
    assert prerequisite_problems(reading) == ()


def test_the_INVISIBLE_codepoints_do_not_break_a_legitimate_prerequisite():
    """An invisible codepoint is the worst kind of hole: the plan looks written and the reader refuses."""
    from mnemosyne.production.plan_format import prerequisite_problems

    for invisible in (" ", "​", "’"):
        text = plan(*HEAD, "- **A1** \U00002B1C t.", f"  *Prérequis* : {invisible}AUCUN")
        reading = read_plan(text)
        assert reading.items[0].prerequisite == "AUCUN", f"broken by U+{ord(invisible):04X}"
        assert prerequisite_problems(reading) == ()


def test_an_UNREADABLE_prerequisite_is_not_an_ABSENT_one_and_the_refusal_quotes_what_it_saw():
    """M12 · the mutant that survived: the third population was held up only by a docstring.

    ``None`` (never declared) · a token (readable, outside the vocabulary) · ``""`` (declared, nothing
    readable) are THREE answers. Collapsing the third into the first would render an empty field
    indistinguishable from an absent one — and the refusal literally said ``→ '' outside the
    vocabulary``, i.e. accused nothing.
    """
    from mnemosyne.production.plan_format import prerequisite_problems

    text = plan(*HEAD, "- **A1** \U00002B1C t.", "  *Prérequis* :", "  *Taille* : 1")
    reading = read_plan(text)
    (item,) = reading.items

    assert item.prerequisite == "", "an empty field is not an absent field"
    assert item.prerequisite is not None
    assert item.blank_fields == ("Prérequis",)
    (problem,) = prerequisite_problems(reading)
    assert problem.kind == "prerequis_inconnu"
    assert "nothing readable in" in problem.detail


def test_every_refusal_GLOSSES_the_vocabulary_so_a_project_without_an_Owner_can_read_it():
    """D7 · the promise "`OWNER` is a role" only lived in a label nobody prints.

    The TOKEN itself is the first name, and it used to go out as-is in EVERY refusal: at the factory
    and at Example Research, the message ordered writing a first name that means nothing to them. The witness
    now judges **what the refusal EMITS**, not what the table declares.
    """
    from mnemosyne.production.plan_format import PREREQUISITE_HOLDERS, prerequisite_problems

    (problem,) = prerequisite_problems(read_plan(plan(*HEAD, "- **A1** \U00002B1C mute.")))

    # The SHAPE is literal (`TOKEN (role)` — that is what "glossed" means here), the ROLE comes from
    # the table itself: a witness that retyped the sentence would close this ONE wording instead of
    # the class, and go stale the next time that sentence is touched.
    assert f"OWNER ({PREREQUISITE_HOLDERS['OWNER'].split(' — ')[0]})" in problem.detail
    assert "AUCUN" in problem.detail and "valid and free" in problem.detail


def test_the_prerequisite_barrier_is_REALLY_CALLED_by_make_plans_and_names_who_can_lift():
    """ **THE BARRIER THAT NOTHING CALLED.**

 ``prerequisite_problems`` shipped to production with a docstring saying "it is the CALLER
 that carries the scope" and, measured by an isolated audit, **zero callers** — neither the
 surface, nor the pre-commit gate. A barrier nothing calls is a wish, and this repo has already
 paid for that shape before. This witness holds the EDGE: the surface calls it, it NAMES, and it
 does not count an item already settled.
 """
    from mnemosyne.production.plan_format import PREREQUISITE_HOLDERS
    from mnemosyne.production.plan_registry import LISIBLE, PlanRegistry, ProjectPlan
    from mnemosyne.runtime.plans_run import _blocked_block, render_registry

    reading = read_plan(
        plan(
            *HEAD,
            "- **A1** \U00002B1C blocked.",
            "  *Prérequis* : OWNER — he must type the word",
            "- **A2** \U00002705 already done, its prerequisite was lifted the same day.",
            "  *Prérequis* : OWNER — lifted by doing it",
            "- **A3** \U00002B1C free.",
            "  *Prérequis* : AUCUN",
            "- **A4** \U00002B1C mute, it declares nothing.",
        )
    )
    lines = _blocked_block(reading)
    (line,) = [one for one in lines if "NOT STARTABLE" in one]

    assert "A1" in line and PREREQUISITE_HOLDERS["OWNER"] in line
    assert "A2" not in line, (
        "a \U00002705 item is no longer waiting to start — saying so kills the \U000026D4's credibility"
    )
    assert "A3" not in line and "A4" not in line
    # `A4` declares nothing: it is not BLOCKED, it is NOT JUDGED — and since the surface reads the
    # judge, this silence is published as a count instead of being swallowed.
    assert any("with no declared `*Prérequis*`" in one for one in lines)

    # **AND ABOVE ALL: THE SURFACE CALLS IT.** The witness above judges the FUNCTION; unplugging
    # its call in `render_registry` left it GREEN — meaning I had just rebuilt, one step
    # removed, the barrier that nothing calls. So what gets judged is what the surface PRINTS.
    registry = PlanRegistry(
        projects=(
            ProjectPlan(
                name="demo", plan_path=Path("demo/PLAN.md"), state=LISIBLE, reading=reading
            ),
        )
    )
    rendered = render_registry(registry, projects_root=Path("projects"))

    assert line in rendered, "the surface no longer calls the barrier — it becomes a wish again"


def test_produit_resolu_rapport_is_REALLY_called_by_make_plans() -> None:
    """ DELEGATED AUDIT OF 2026-08-15 (3rd pass, HELD with reservation): `produit_resolu_rapport`
 is wired into `plans_run.py`, but NOTHING guarded that wiring — removing the call line produced
 ZERO red out of 3931 witnesses. Exactly the class the witness just above already closes for
 `_blocked_block`, its own neighbour in the SAME function (`render_registry`): copying
 the CALL without copying the WITNESS that makes it irrevocable is half the gesture."""
    from mnemosyne.production.plan_registry import LISIBLE, PlanRegistry, ProjectPlan
    from mnemosyne.runtime.plans_run import render_registry

    reading = read_plan(plan(*HEAD, "- **A1** \U00002B1C x", "  *Produit* : `production/x.py`"))
    registry = PlanRegistry(
        projects=(
            ProjectPlan(
                name="demo", plan_path=Path("demo/PLAN.md"), state=LISIBLE, reading=reading
            ),
        )
    )
    rendered = render_registry(registry, projects_root=Path("projects"))

    assert "produits_resolus=1/1 terrain_declare=0/1" in rendered, (
        "the surface no longer calls produit_resolu_rapport — C2's report becomes a wish again"
    )


# --- A5's ATTACHMENT POINT — the grammar is ONE, the obligation stays A1's own -------------------


def test_a_KNOWN_field_is_read_but_NEVER_obliged():
    """ **The edge between grammar and obligation, and a test must hold it.**

 `*Test à trois*` is read by the reader and does NOT enter what `A1` obliges: merging the
 two lists would mean adding a field for ONE item would silently widen what ALL the others
 must answer. The witness holds both directions at once — readable, and never required.
 """
    from mnemosyne.production.plan_format import EXTRA_FIELD_NAMES

    text = plan(*HEAD, "- **A1** \U00002B1C t.", "  *Produit* : a reader")
    (item,) = read_plan(text).items

    for token, name in EXTRA_FIELD_NAMES.items():
        assert item.field(token) is None, f"{name} should be absent, not invented"
        assert name not in item.missing_fields, f"{name} is REQUIRED even though it is not obliged"
        assert name not in item.blank_fields

    # **THE `blank_fields` HALF WAS TAUTOLOGICAL.** Played against an item that does NOT DECLARE
    # the field, `field()` returns `None` and never `""`: the assertion could never fire, and the
    # mutation "`blank_fields` iterates over KNOWN_FIELDS" survived the whole suite. The missing
    # population is an item declaring the field and leaving it EMPTY.
    declared_empty = read_plan(
        plan(*HEAD, "- **A1** \U00002B1C t.", "  *Produit* : a reader", "  *Test à trois* :")
    ).items[0]
    assert declared_empty.field("test_a_trois") == "", "the field is declared and empty"
    assert declared_empty.blank_fields == (), (
        "a field NOT REQUIRED cannot be « blank » in the plan's sense"
    )


@pytest.mark.parametrize(
    ("shape", "line"),
    [
        ("double bold", "  **Test à trois** : \U00002705 all three"),
        ("underscore", "  _Test à trois_ : \U00002705 all three"),
        ("plain shape", "  *Test à trois* : \U00002705 all three"),
    ],
)
def test_the_ONE_grammar_reads_the_notations_a_SECOND_grammar_could_not(shape: str, line: str):
    """*A contract has a single source, or copies drift* — and this one was already drifting.

 A neighbouring chat's anti-overfit clause carried its own ``re.compile(r"^\\s*\\*Test à
 trois\\*\\s*:\\s*(.*)$")``. Measured before writing this witness: that regex is **MUTE** on
 ``**Test à trois**`` and on ``_Test à trois_``, both of which this reader reads. Two notations, not ten —
 the gain is modest and it is written as-is rather than inflated.

 **And what the single source does NOT repair is said here too**: a marker sitting behind a
 bare word (``… 1 fichier *Test à trois* : …``) is a MENTION for this reader, so BOTH
 grammars are blind to this shape. A lesson written half way would be worse than no lesson.
 """
    text = plan(*HEAD, "- **A1** \U00002B1C t.", line)
    (item,) = read_plan(text).items

    assert item.field("test_a_trois") == "\U00002705 all three", f"« {shape} » not read"


def test_a_marker_behind_a_BARE_WORD_is_blind_in_BOTH_grammars_and_that_is_written_down():
    """The attachment point's residual, frozen so it gets reversed knowingly."""
    text = plan(*HEAD, "- **A1** \U00002B1C t.", "  *Taille* : 1 file *Test à trois* : \U00002705 all three")
    (item,) = read_plan(text).items

    assert item.field("test_a_trois") is None
    assert item.field("taille") == "1 file *Test à trois* : \U00002705 all three"


def test_a_VARIATION_SELECTOR_does_not_break_a_legitimate_prerequisite():
    """D4 · the 5th decoration, and my previous witness was green **by the choice of its glyph**.

 ```` (U+26D4) carries no variation selector; ````, ````, ````, ```` carry
 one — U+FE0F, category ``Mn``, neither ``So`` nor in the `lstrip`. The loop that strips
 pictographs therefore stopped on it and returned a refusal **accusing nothing**. ```` lives in
 122 files of this repo. The module already carried ``_despecify`` for this exact class, written
 with the line "an invisible codepoint is the worst kind of hole" — and this site did not call it.
 """
    from mnemosyne.production.plan_format import prerequisite_problems

    for glyph in ("\U000026D4", "\U000026A0\U0000FE0F", "\U00002620\U0000FE0F", "\U0001F17F\U0000FE0F", "\U000023F8\U0000FE0F"):
        text = plan(*HEAD, "- **A1** \U00002B1C t.", f"  *Prérequis* : {glyph} **OWNER** — live")
        reading = read_plan(text)
        assert reading.items[0].prerequisite == "OWNER", f"broken by {glyph!r}"
        assert prerequisite_problems(reading) == ()


def test_the_refusal_quotes_the_WHOLE_word_the_author_wrote_not_a_prefix_of_it():
    """A refusal that accuses ``'AUTRE'`` in front of an ``AUTRE-PROJET2`` written sends the reader
    looking in the wrong place. The whole word is compared, so the whole word is quoted."""
    from mnemosyne.production.plan_format import prerequisite_problems

    text = plan(*HEAD, "- **A1** \U00002B1C t.", "  *Prérequis* : AUTRE-PROJET2")
    (problem,) = prerequisite_problems(read_plan(text))

    assert "'AUTRE-PROJET2'" in problem.detail


def test_the_surface_reads_the_JUDGE_and_not_a_second_grammar_of_its_own():
    """ **THE DEFECT MY OWN REPAIR HAD REBUILT.**

 The first version imported ``prerequisite_problems`` and then judged items with its own
 test (``prerequisite is None``): the import stayed unused (``ruff F401``, ``make lint``
 RED), and ``prerequis_manquant`` was emitted by **no executed path at all** — 1,060 items of the
 corpus declare nothing and the surface said not a word about it. *A contract has a single source*
 — a line I wrote ONE COMMIT later, about somebody else.

 The three populations are here in one witness, or one would cover for the others.
 """
    from mnemosyne.production.plan_format import PREREQUISITE_HOLDERS
    from mnemosyne.runtime.plans_run import _blocked_block

    lines = _blocked_block(
        read_plan(
            plan(
                *HEAD,
                "- **A1** \U00002B1C blocked.",
                "  *Prérequis* : OWNER — he must type the word",
                "- **A2** \U00002B1C unreadable.",
                "  *Prérequis* : PEUT-ETRE",
                "- **A3** \U00002B1C mute, it declares nothing.",
                "- **A4** \U00002B1C free.",
                "  *Prérequis* : AUCUN",
                "- **A5** \U00002705 settled, its prerequisite was lifted by doing it.",
                "  *Prérequis* : OWNER — lifted",
            )
        )
    )
    joined = "\n".join(lines)

    assert "A1" in joined and PREREQUISITE_HOLDERS["OWNER"] in joined
    assert "PEUT-ETRE" in joined, "the unreadable one must be NAMED by the surface"
    assert f"OWNER ({PREREQUISITE_HOLDERS['OWNER'].split(' — ')[0]})" in joined, (
        "the surface used to print « unreadable prerequisite: '' » — the defect repaired at the judge "
        "and left intact on the only path production takes"
    )
    assert "1 item(s) with no declared `*Prérequis*`" in joined, (
        "the absent one reached no real path"
    )
    assert "A4" not in joined and "A5" not in joined


def test_a_token_ENDING_on_a_hyphen_is_refused_and_a_dash_TAIL_still_passes():
    """ **THE REGRESSION MY OWN REPAIR HAD INTRODUCED.**

 An `rstrip("-")` had been placed here with a **measurably false** justification: `AUCUN --
 LIFTED` reads as `AUCUN` WITH or without it, because the walk stops on the SPACE. What it
 actually bought was that `AUCUN-`, `AUCUN--` and `AUCUN- (unless OWNER validates)` became
 **STARTABLE** — refused by the previous commit. *A repair that reopens the permissive side is
 worse than the defect it closes.* Both populations in one witness, or the next
 "simplification" reopens the hole.
 """
    from mnemosyne.production.plan_format import prerequisite_problems

    for glued in ("AUCUN-", "AUCUN--", "AUCUN- (unless OWNER validates)"):
        reading = read_plan(plan(*HEAD, "- **A1** \U00002B1C t.", f"  *Prérequis* : {glued}"))
        assert reading.items[0].startable is False, f"« {glued} » became startable again"
        assert [p.kind for p in prerequisite_problems(reading)] == ["prerequis_inconnu"]

    for spaced in ("AUCUN -- LIFTED.", "AUCUN — LIFTED on 2026-08-13.", "AUTRE-PROJET — arc 03"):
        reading = read_plan(plan(*HEAD, "- **A1** \U00002B1C t.", f"  *Prérequis* : {spaced}"))
        assert prerequisite_problems(reading) == (), f"« {spaced} » is a false refusal"


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("ZWJ (\U0001F468‍\U0001F469‍\U0001F466)", "\U0001F468‍\U0001F469‍\U0001F466 **OWNER** — live"),
        ("skin tone (\U0001F44D\U0001F3FD)", "\U0001F44D\U0001F3FD **OWNER** — live"),
        ("soft hyphen", "­**OWNER** — live"),
        ("word joiner", "⁠**OWNER** — live"),
        ("BOM", "﻿**OWNER** — live"),
        ("CGJ", "͏**OWNER** — live"),
        ("variation selector", "\U000026A0\U0000FE0F **OWNER** — live"),
    ],
)
def test_the_CLASS_of_invisible_openers_is_closed_not_a_list_of_cases(name: str, value: str):
    """D2 · **third time** this line leaks through a character no list contained.

 First `` worked and `` did not (U+FE0F). Then `_despecify` closed those two codepoints —
 and an audit walked in with EIGHT more. Two are not theoretical: over the `.md` files git
 tracks, the soft hyphen sits in 34 files and the keycap in 33.
 The remedy is no longer a list but a **Unicode CATEGORY** (`Cf` · `Mn` · `Me` · `Sk` ·
 `So`). *Close the class, not the case* — owed for the third time here.
 """
    from mnemosyne.production.plan_format import prerequisite_problems

    reading = read_plan(plan(*HEAD, "- **A1** \U00002B1C t.", f"  *Prérequis* : {value}"))

    assert reading.items[0].prerequisite == "OWNER", f"broken by {name}"
    assert prerequisite_problems(reading) == ()


def test_the_undeclared_majority_is_ONE_line_and_never_one_line_per_item():
    """D5 · the "COUNT rather than N lines" was a wish: nothing bounded the block's size.

    Rewriting one witness (`(line,) = …` replaced by a filter) had removed **the only
    constraint that existed on the number of lines**, and the mutation "name the undeclared ones one
    by one" survived the whole suite. On the real repo that is **169 items**: the block would go
    from 2 lines to 171 with no test reddening, and a report nobody reads to the end
    reports nothing.
    """
    from mnemosyne.runtime.plans_run import _blocked_block

    lines = _blocked_block(
        read_plan(plan(*HEAD, *(f"- **A{n}** \U00002B1C item muet numéro {n}." for n in range(1, 13))))
    )

    assert len(lines) == 1, f"12 silent items produced {len(lines)} lines: {lines}"
    assert "12 item(s) with no declared `*Prérequis*`" in lines[0]


def test_the_arc_floor_is_the_REAL_population_and_LOWERING_the_literal_reddens():
    """The meta-witness that makes `PLAN_ARCS_FLOOR` guardable — without it, the floor is decorative.

 Measured: lowering the literal to zero in the neighbouring assertion made **nobody
 redden**, because nothing else read it. A floor its own author can lower with no red is
 not a barrier, it is a comment. Here it is compared to the disk: lowering it reddens, and
 adding an arc reddens too — in which case the number is raised **knowingly**.
 """
    real_arcs = sorted(md.name for md in (REPO / "docs/plan").rglob("*.md"))

    assert PLAN_ARCS_FLOOR == len(real_arcs), (
        f"{len(real_arcs)} arcs on disk against a floor of {PLAN_ARCS_FLOOR} — "
        f"if intentional, raise the constant; otherwise an arc has disappeared: {real_arcs}"
    )


# --- WHAT AN AUDIT BY THE CONSUMERS found, where four audits of the grammar saw nothing ----------


def test_the_refusals_are_split_BY_PRODUCER_and_the_union_loses_nothing():
    """D2 · merged, they manufactured a lie that TRAVELS.

    ``make plan-emit`` prints the whole constant under the header "The READER, on the bytes": the
    two prerequisite refusals therefore travelled out to **every project** as if `read_plan` raised
    them — which `docs/FORMAT_PLAN.md` denies in so many words. *A false page is a defect; a false
    page that gets EMITTED is the copy that outlives its original.*

    The witness holds both directions: the partition is strict, and the union loses nothing —
    splitting a constant without keeping its union is how a control silently stops covering
    half of what it used to cover.
    """
    import itertools

    from mnemosyne.production.plan_format import (
        ALL_REFUSAL_KINDS,
        FILIATION_REFUSALS,
        ORDER_REFUSALS,
        PREREQUISITE_REFUSALS,
        PRODUIT_REFUSALS,
        READER_REFUSALS,
        REGISTRY_REFUSALS,
        REQUIRED_FIELD_REFUSALS,
    )

    # The producers in a TABLE, not in pairs: a seventh judge is declared here and the partition
    # judges it on its own. *An enumeration of pairs describes what existed the day it was written.*
    producers = (
        READER_REFUSALS,
        PREREQUISITE_REFUSALS,
        REQUIRED_FIELD_REFUSALS,
        ORDER_REFUSALS,
        REGISTRY_REFUSALS,
        PRODUIT_REFUSALS,
        FILIATION_REFUSALS,
    )

    assert set().union(*producers) == set(ALL_REFUSAL_KINDS)
    assert sum(map(len, producers)) == len(ALL_REFUSAL_KINDS), "a refusal has TWO producers"
    for left, right in itertools.combinations(producers, 2):
        assert not (set(left) & set(right)), f"overlap: {set(left) & set(right)}"
    assert set(PREREQUISITE_REFUSALS) == {"prerequis_manquant", "prerequis_inconnu"}
    assert set(REQUIRED_FIELD_REFUSALS) == {"champ_requis_manquant"}


def test_a_reader_refusal_really_comes_from_the_READER_and_a_prerequisite_one_never_does():
    """The partition is not declarative: it is checked against what each judge actually PRODUCES."""
    from mnemosyne.production.plan_format import (
        PREREQUISITE_REFUSALS,
        prerequisite_problems,
    )

    from_reader = {p.kind for p in read_plan(plan(*HEAD, "- **A1** \U0001F195 unknown glyph")).problems}
    from_judge = {p.kind for p in prerequisite_problems(read_plan(plan(*HEAD, "- **A1** \U00002B1C muet")))}

    assert from_reader and not (from_reader & set(PREREQUISITE_REFUSALS))
    assert from_judge <= set(PREREQUISITE_REFUSALS)


def test_the_statuses_that_can_still_START_partition_the_whole_vocabulary():
    """D4 · the implemented class was not the one its docstring named.

    It said "it has started, or it will never start" and only held `fait` and `clos`: over
    the real corpus, **16 `en cours`, 7 `prêt`, 5 `en pause`** were published as "nothing says
    they can start". A surface that says that about work IN PROGRESS is a surface people
    stop believing.

    The partition is asserted against the WHOLE vocabulary: a seventh status cannot fall on
    one side by accident, it reddens until somebody decides.
    """
    from mnemosyne.production.plan_format import STATUS_LABEL
    from mnemosyne.runtime.plans_run import _CAN_STILL_START

    assert _CAN_STILL_START <= set(STATUS_LABEL)
    assert _CAN_STILL_START == {"a_faire"}, (
        f"the partition moved: {sorted(_CAN_STILL_START)} can start, "
        f"{sorted(set(STATUS_LABEL) - _CAN_STILL_START)} cannot — is that intended?"
    )


def test_an_item_already_UNDER_WAY_is_never_announced_as_unable_to_start():
    """The five statuses "no longer in question", in one witness — or one would cover for the others."""
    from mnemosyne.runtime.plans_run import _blocked_block

    lines = _blocked_block(
        read_plan(
            plan(
                *HEAD,
                "- **A1** \U0001F504 en cours, personne n'attend qu'il démarre.",
                "- **A2** \U00002705 fait.",
                "- **A3** \U0001F17F prêt, il attend un geste.",
                "- **A4** \U000023F8 en pause.",
                "- **A5** \U000026D4 clos.",
                "- **A6** \U00002B1C celui-là, oui.",
            )
        )
    )

    assert lines == [
        "      \U000026A0\U0000FE0F 1 item(s) with no declared `*Prérequis*` — no way to know what"
        " blocks them, so nothing says they can start; `AUCUN` is free"
    ], lines


@pytest.mark.parametrize("cls_name", ["PlanItem", "PlanProblem", "PlanReading"])
def test_the_three_data_classes_stay_FROZEN(cls_name: str):
    """D7 · the three used to unfreeze without a single one of 3,273 tests reddening.

 An unfrozen `PlanItem` becomes **mutable AND unhashable**, and the same `PlanReading` is shared
 by `make plans`, `make ui-json`, `verify_readability` and the pre-commit gate: a consumer
 that wrote `item.status = "fait"` would make every other one see it. The module describes itself
 everywhere as "a PURE reader" — a purity nothing was holding up.
 """
    import dataclasses

    import mnemosyne.production.plan_format as pf

    cls = getattr(pf, cls_name)
    assert dataclasses.is_dataclass(cls)
    assert cls.__dataclass_params__.frozen, f"{cls_name} is no longer frozen"
    assert cls.__hash__ is not None, f"{cls_name} has stopped being hashable"

    instance = read_plan(plan(*HEAD, "- **A1** \U00002B1C t.", "  *Produit* : x")).items[0]
    if cls_name == "PlanItem":
        with pytest.raises(dataclasses.FrozenInstanceError):
            instance.status = "fait"


def test_the_field_marker_pattern_is_PUBLIC_because_a_closed_item_depends_on_it():
    """ Arbitration rendered: a neighbouring chat's **already-closed** clause read this pattern.

 It reached into a **private** name of this module, which had moved **three times** in one
 evening. *A closed item that depends on a private symbol being rewritten is a closure that can
 REOPEN without anybody deciding to* — and a closure silently undone is worse than an item never
 closed, because the plan keeps asserting that it is.

 The witness freezes what makes up the CONTRACT: the public name, and the TWO groups the caller
 reads. Making it public without freezing its shape would have shifted the problem one notch over.
 """
    import mnemosyne.production.plan_format as pf

    assert hasattr(pf, "FIELD_MARKER_RE"), "the pattern has gone private again"
    assert not hasattr(pf, "_FIELD_MARKER_RE"), "both names coexist — a copy will drift"

    found = pf.FIELD_MARKER_RE.match("**Fini quand** :")
    assert found is not None
    assert found.group(1) == "**", "group 1 = the emphasis run — a caller reads it"
    assert found.group(2) == "Fini quand", "group 2 = the field name — a caller reads it"


# --- `A1`'s LEVEL 2 — prepared, measured, and NOT armed ------------------------------------------


def test_the_required_field_judge_names_every_missing_field_in_ONE_refusal():
    """One refusal per ITEM, which NAMES every field that falls short — never six lines for one item.

    A refusal a reader cannot process in one read is a refusal they learn to skip.
    And `AUCUN` stays a valid and free answer: *the QUESTION is obliged, never the answer.*
    """
    from mnemosyne.production.plan_format import required_field_problems

    reading = read_plan(plan(*HEAD, "- **A1** \U00002B1C t.", "  *Produit* : a reader"))
    (problem,) = required_field_problems(reading)

    assert problem.kind == "champ_requis_manquant"
    assert "Produit" not in problem.detail, "a DECLARED field must not be required"
    for name in ("Fini quand", "Dépend de", "Prérequis", "À lire", "Taille"):
        assert name in problem.detail, f"{name} missing and not named"
    assert "valid and free" in problem.detail, "the refusal must name the way out"


def test_the_CALLER_decides_the_scope_which_is_how_level_2_stays_on_THIS_plan_only():
    """`required=()` obliges nothing: it is level 1 for other projects, in the same code.

    A5's precedent: a floor imposed on another project's plan would be a disguised ceiling.
    """
    from mnemosyne.production.plan_format import required_field_problems

    reading = read_plan(plan(*HEAD, "- **A1** \U00002B1C an item that declares nothing."))

    assert required_field_problems(reading, required=()) == ()
    assert len(required_field_problems(reading, required=("produit",))) == 1


def test_arming_the_barrier_COSTS_ZERO_on_this_repos_own_plan_and_the_day_it_stops_we_know():
    """ The number that makes the arbitration possible, **re-measured here** rather than cited.

 The orchestrator decided "we arm it" because the cost is zero. This witness is what keeps that
 line true tomorrow: the day an item of this plan stops declaring its six fields, it
 reddens **before** it gets armed, not after. *A count with no gate behind it is a memory.*
 """
    from mnemosyne.production.plan_format import required_field_problems

    refused = [
        (md.name, p.detail)
        for md in sorted((REPO / "docs/plan").rglob("*.md"))
        for p in required_field_problems(read_plan(md.read_text(encoding="utf-8")))
    ]

    assert refused == [], f"arming it would now cost {len(refused)} refusals: {refused[:3]}"


def test_the_level_2_barrier_is_ARMED_and_the_gate_really_READS_it():
    """ **THIS WITNESS REPLACES THE ONE THAT SAID "NOT ARMED YET", and it was meant to die when armed.**

 I had written it this way: *"the day it gets armed, this test reddens and gets deleted in the
 same gesture — that is exactly the intended friction: nobody arms it by accident."* The gesture
 happened, the witness died, and this one takes its place **in the same spirit**: it holds the
 reverse EDGE — the gate must never again stop calling the judge.

 **And it checks the KEY, not just the call**: a scope table whose key matches no real path
 arms a **dead** gate, which is the shape of defect this repo pays most dearly for. The key is
 therefore compared to the name the reader itself imposes.
 """
    hook = (REPO / ".githooks/pre-commit").read_text(encoding="utf-8")

    assert "required_field_problems" in hook, "the barrier has been DISARMED"
    assert f'"docs/{PLAN_FILENAME}"' in hook, (
        "the scope key no longer names this plan's door — a table whose key matches "
        "nothing arms a DEAD gate, and nothing would redden"
    )


def test_a_BOM_does_NOT_make_the_plans_NAME_disappear():
    """Real defect, routed by the orchestrator and measured before being believed.

 **It does not break reading: it steals the NAME, in silence.** A `\\ufeff` at the head sticks to
 the `#` of the title, `_TITLE_RE` no longer matches, and the plan comes back with no name — but
 `readable` stays **true** (it only requires the cap and one item), so `make plans` shows an
 anonymous project and **nothing reddens**. A BOM arrives on its own the moment a Windows editor
 or an export touches the file: *"nobody will write that" is a property of the moment, not of the
 code.*

 **And the remedy is here, not at the caller**: the TWO paths that turn plan bytes into
 text — `plan_registry._read_text` (the disk) and `.githooks/pre-commit` (the git index) —
 both decode as plain `utf-8` and both go through `read_plan`. A `utf-8-sig` on one would have
 left the other open. *Close the class, not the case.*
 """
    body = "# PLAN — demo\n\n> **Cap** : prove\n\n- **A1** \U00002B1C an item\n"
    with_bom = read_plan("﻿" + body)
    without_bom = read_plan(body)

    assert with_bom.project == "demo", "the BOM stole the plan's name"
    assert with_bom.project == without_bom.project
    assert with_bom.items == without_bom.items
    assert with_bom.cap == without_bom.cap


def test_the_TWO_paths_that_decode_a_plan_are_covered_by_the_SAME_remedy():
    """The witness for the CLASS: the disk and the git index, both exercised.

    Without it, the fix is true for the path that was looked at and mute on the other — and the
    next byte-reader would be born open.
    """
    import tempfile

    from mnemosyne.production.plan_registry import _read_text

    raw_bytes = ("﻿# PLAN — demo\n\n> **Cap** : prove\n\n- **A1** \U00002B1C an item\n").encode("utf-8")
    file_path = Path(tempfile.mkdtemp()) / PLAN_FILENAME
    file_path.write_bytes(raw_bytes)

    from_disk, _why = _read_text(file_path)
    # The second arm used to be an INLINE REWRITE of the decoding — so the same call twice, not
    # two paths. It now pulls the hook's line exactly as WRITTEN in the file:
    # if it changes, this witness sees it. *A witness that copies what it claims to test tests
    # only its own copy.*
    hook = (REPO / ".githooks/pre-commit").read_text(encoding="utf-8")
    assert 'decode("utf-8")' in hook, "the hook changed its decoding — remeasure this witness"
    from_index = raw_bytes.decode("utf-8")

    assert read_plan(from_disk or "").project == "demo", "DISK path"
    assert read_plan(from_index).project == "demo", "GIT INDEX path"

    # And the THIRD judge, the one the first fix had left out: an arc reduced to a
    # BOM must be refused as an empty arc, not pass through in silence.
    from mnemosyne.production.plan_format import fold_plan

    door = plan(*HEAD, "- `plan/a.md` — an arc")
    refusals = fold_plan(door, ("plan/a.md",), lambda _m: ("\ufeff", "")).problems
    assert [p.kind for p in refusals] == ["arc_vide"], [p.kind for p in refusals]


def test_NO_refusal_producer_escapes_the_union_even_when_built_from_a_CONSTANT():
    """ **MY OWN CONTROL CARRIED THE BLIND SPOT OF THE DEFECT IT WAS LOOKING FOR.**

 An audit had already found a producer outside the union; I had added it and written a
 scan to close the class. That scan only read the **literals** passed to ``PlanProblem`` —
 but ``arc_illisible`` is built from a **CONSTANT** (``ARC_ILLISIBLE``). So it
 confidently answered "none", and the next audit found the missing producer.
 *A control that searches for one shape never finds the class.*

 This witness resolves BOTH: the literal **and** the name that points at a module constant.
 """
    import ast

    from mnemosyne.production.plan_format import ALL_REFUSAL_KINDS

    production_dir = REPO / "system/lib/mnemosyne/production"
    found_kinds: set[str] = set()
    for source_file in sorted(production_dir.rglob("*.py")):
        tree = ast.parse(source_file.read_text(encoding="utf-8"))
        constants = {
            target.id: node.value.value
            for node in ast.walk(tree)
            if isinstance(node, ast.AnnAssign | ast.Assign)
            for target in ([node.target] if isinstance(node, ast.AnnAssign) else node.targets)
            if isinstance(target, ast.Name)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        }
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call) and getattr(node.func, "id", "") == "PlanProblem"):
                continue
            for argument in node.args[1:2]:
                if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
                    found_kinds.add(argument.value)
                elif isinstance(argument, ast.Name) and argument.id in constants:
                    found_kinds.add(constants[argument.id])

    assert found_kinds, "the scan no longer sees any producer — the instrument itself broke"
    assert found_kinds <= set(ALL_REFUSAL_KINDS), (
        f"produced and NEVER declared: {sorted(found_kinds - set(ALL_REFUSAL_KINDS))} — "
        "a producer outside the union is judged by neither gate"
    )


def test_the_BOM_falls_at_the_EDGE_of_the_bytes_AND_at_the_readers_own_home():
    """The belt and the suspenders, and the witness says which carries what.

 **The remedy that closes the defect is at the SINGLE SOURCE** (`_sans_bom`, read by the reader
 and its sibling judges): it is what covers the hook, which decodes the git index and never goes
 through the registry. `utf-8-sig` at the edge additionally protects a future consumer that
 would read these bytes without going through `read_plan`. Both are IDEMPOTENT — stripping a BOM
 twice gives the same byte — so these are not two rules that can drift apart.
 """
    import tempfile

    from mnemosyne.production.plan_registry import LISIBLE, _read_text, read_plan_file

    raw_bytes = "﻿# PLAN — demo\n\n> **Cap** : prove\n\n- **A1** \U00002B1C an item\n".encode()
    file_path = Path(tempfile.mkdtemp()) / PLAN_FILENAME
    file_path.write_bytes(raw_bytes)

    decoded, _ = _read_text(file_path)
    assert decoded is not None and not decoded.startswith("﻿"), "the BOM did not fall at the edge"

    project_plan = read_plan_file(file_path, "demo")
    assert project_plan.state == LISIBLE and project_plan.reading.project == "demo"
    # and the single source stays the sole owner of the path that does NOT go through here
    assert read_plan(raw_bytes.decode("utf-8")).project == "demo", "GIT INDEX path"


def test_the_SCOPE_of_level_2_is_a_PREDICATE_and_reaches_SUB_PLANS():
    """ **A LIST OF LOCATIONS ALWAYS FORGETS ONE MORE LOCATION.**

 Scope used to be a table indexed by door path (`{"docs/PLAN.md": …}`). But `owning_plan`
 applies *"the longest match wins"*: the moment a **sub-plan** is born under `docs/plan/`, its
 door becomes `docs/plan/<x>/PLAN.md`, the table returns `()`, and **the obligation disappears
 without a word**. Triggered with the repo's own sanctioned command: `make plan-nouveau` writes
 an item with **0 of the 6 fields**, and the commit was **ACCEPTED**.

 The witness holds BOTH edges: depth must not let anything slip through, and the scope must
 not overflow onto another project's plan — *a floor imposed on somebody else's plan is a
 disguised ceiling*.
 """
    from mnemosyne.production.plan_format import FIELD_NAMES, champs_requis_pour

    for inside in ("docs/PLAN.md", "docs/plan/zz/PLAN.md", "docs/plan/zz/plan/w/PLAN.md"):
        assert champs_requis_pour(inside) == tuple(FIELD_NAMES), f"{inside} escaped"
    for outside_scope in ("docs/veille/PLAN.md", "projects/saas/Sibling Research/PLAN.md", "PLAN.md"):
        assert champs_requis_pour(outside_scope) == (), f"{outside_scope} overflows the scope"


def test_champs_requis_pour_READS_a_DECLARATION_outside_Mnemosyne_D176():
    """D176 — a project that is not Mnémosyne could not ADOPT any field, no matter what it wrote:
    `champs_requis_pour` returned `()` unconditionally outside `docs/`. The TWO hard bounds of
    routing, measured here rather than assumed:

    (1) nothing declared -> nothing obliged (the "not imposed" half of D176, held before this
        commit too);
    (2) PARTIALLY declared -> held to EXACTLY what was taken, never more -- the sibling project's own precedent,
        2026-07-29 (`projects/saas/Sibling Research/state/decisions/format-de-plan-sibling.md`):
        "we keep its checker, not its structural prescriptions".
    """
    from mnemosyne.production.plan_format import FIELD_NAMES, champs_requis_pour

    outside_scope = "projects/saas/Sibling Research/PLAN.md"

    assert champs_requis_pour(outside_scope) == (), (
        "no declaration -- still nothing, behaviour intact"
    )
    assert champs_requis_pour(outside_scope, "") == (), "empty declaration -- same thing, explicit"

    assert champs_requis_pour(outside_scope, "produit, fini_quand") == ("produit", "fini_quand"), (
        "partially declared -- held to EXACTLY these two tokens"
    )
    assert "depend_de" not in champs_requis_pour(outside_scope, "produit"), (
        "never more than what was taken"
    )

    all_tokens = ", ".join(FIELD_NAMES)
    assert champs_requis_pour(outside_scope, all_tokens) == tuple(FIELD_NAMES), "all six, declared one by one"

    assert champs_requis_pour(outside_scope, "produit, ce-jeton-n-existe-pas") == ("produit",), (
        "an unknown token is ignored -- it obliges nothing, it refuses nothing either"
    )


def test_champs_requis_pour_for_Mnemosyne_IGNORES_every_declaration_D176():
    """ **MANDATORY NEGATIVE CONTROL (D176 routing)**: Mnémosyne's own floor stays
 UNCONDITIONAL -- it depends on no `**Format**` line at all, precisely so the existing
 negative control (0 refusals over 49 items, bites on a mutilated item) cannot be lost through an
 absent or badly written prose line."""
    from mnemosyne.production.plan_format import FIELD_NAMES, champs_requis_pour

    for inside in ("docs/PLAN.md", "docs/plan/zz/PLAN.md"):
        assert champs_requis_pour(inside) == tuple(FIELD_NAMES)
        assert champs_requis_pour(inside, "") == tuple(FIELD_NAMES)
        assert champs_requis_pour(inside, "produit") == tuple(FIELD_NAMES), (
            "a partial declaration cannot REDUCE Mnémosyne's own floor"
        )


def test_the_FORMAT_gate_field_is_READ_from_a_real_document_and_survives_the_fold():
    """End-to-end: `**Format** :` at the head of a door must reach `PlanReading.format_declare`
    on a plain document (`read_plan`) as much as on a folded plan (`fold_plan`, folder +
    arc) -- the same pattern as `succede_a`, which H4 already measured the fold does not lose."""
    from mnemosyne.production.plan_format import fold_plan

    doc = plan(
        "# PLAN — demo",
        "",
        "> **Cap** : prove the form",
        "> **Format** : produit, fini_quand",
        "",
        "- **Z1** \U00002B1C t.",
        "  *Produit* : p",
        "  *Fini quand* : f",
    )

    assert read_plan(doc).format_declare == "produit, fini_quand"

    folded = fold_plan(doc, (), lambda _m: (None, "absent"))
    assert folded.format_declare == "produit, fini_quand", "the fold must not lose it"


def test_a_field_DECLARED_EMPTY_is_refused_like_an_ABSENT_field():
    """ **THE BARRIER NOTHING CALLED, again: `blank_fields` had NO caller at all.**

 The judge only read `missing_fields`, so **six fields declared EMPTY used to pass the commit** —
 measured. `blank_fields`'s own docstring says it exists to prevent *"a plan looking complete
 because every title is present"*. *A question asked and left with no answer is not a question
 answered.*
 """
    from mnemosyne.production.plan_format import required_field_problems

    empty_fields = plan(
        *HEAD,
        "- **Z1** \U00002B1C t.",
        "  *Produit* :",
        "  *Fini quand* :",
        "  *Dépend de* :",
        "  *Prérequis* : AUCUN",
        "  *À lire* :",
        "  *Taille* :",
    )
    (problem_found,) = required_field_problems(read_plan(empty_fields))

    assert problem_found.kind == "champ_requis_manquant"
    for field_name in ("Produit", "Fini quand", "Dépend de", "À lire", "Taille"):
        assert field_name in problem_found.detail, f"{field_name} declared empty and not required"
    assert "Prérequis" not in problem_found.detail, "a field FILLED IN must not be required"


def test_the_gate_calls_the_PREDICATE_and_this_witness_confesses_its_limit():
    """The gate must read the rule, not a table frozen into the script.

 **CONFESSION, because it is free and beats a false barrier**: this stays a
 TEXT detector. An audit showed that a saboteur replacing the argument with `required=()`
 kept the two strings the previous version searched for, and **survived the whole
 suite**. Pinning the exact EXPRESSION narrows the window — it does not close it. What would
 close it is an end-to-end test that stages a plan under `docs/plan/` and pulls the real
 hook; it does not exist, and this says so rather than letting anyone believe otherwise.
 """
    hook = (REPO / ".githooks/pre-commit").read_text(encoding="utf-8")

    assert "champs_requis_pour(door_path, reading.format_declare)" in hook, (
        "the gate no longer calls the predicate"
    )
    assert "REQUIS_PAR_PORTE" not in hook, "the path table is back — it lets things leak"


def test_EVERY_declared_need_refuses_a_BLANK_value_and_the_population_comes_from_the_CODE() -> None:
    """ **The barrier a lesson paid for twice was still missing: the unrepaired neighbour.**

 I armed the gate for a non-empty TITLE and left `bool(reading.cap)` **on the very next line of
 the same dictionary** — yet it was the CAP the 2026-07-29 report named. The two regexes are
 twins (`(.+?)`), so `**Cap** :` followed by spaces returns `' '`, hence true. *I repair the
 defect's neighbour and publish "the gate is armed".*

 **This witness draws its population from `_MISSING_SENTENCE`, never from a list written
 here.** A need added tomorrow with no blank case makes the first `assert` REDDEN: a need can no
 longer be declared without saying what it looks like EMPTY. That is the barrier, not discipline.

 "Blank" reads the way a human sees it: spaces, invisible (`U+3164`, category ``Lo``),
 an HTML comment — the three shapes that used to pass.
 """
    blank_per_need = {
        "titre": lambda v: f"# PLAN — {v}\n\n> **Cap** : c\n\n- **Z1** \U00002B1C t.\n",
        "cap": lambda v: f"# PLAN — d\n\n> **Cap** : {v}\n\n- **Z1** \U00002B1C t.\n",
        "items": lambda v: f"# PLAN — d\n\n> **Cap** : c\n\n{v}\n",
    }
    assert set(blank_per_need) == set(_MISSING_SENTENCE), (
        "a need was declared with no BLANK case: this witness therefore does not judge it, "
        f"gap = {set(_MISSING_SENTENCE) ^ set(blank_per_need)}"
    )

    for need, render in blank_per_need.items():
        for label, value in (
            ("espaces", "   "),
            ("invisible", "ㅤ"),
            ("comment_block", "<!-- x -->"),
        ):
            raw_text = render(value)
            assert not is_readable(read_plan(raw_text), role=ROLE_PLAN), (
                f"need {need!r} accepts a blank value ({label}): "
                "an empty plan reads as a valid one"
            )

    healthy = "# PLAN — Mnémosyne\n\n> **Cap** : viser juste\n\n- **Z1** \U00002B1C t.\n"
    assert is_readable(read_plan(healthy), role=ROLE_PLAN), (
        "the HEALTHY case is refused: this witness is measuring its own harness, not the gate"
    )


def test_a_marker_QUOTED_in_prose_declares_NOTHING_in_BOTH_directions() -> None:
    """ **The defect lived in the repo while eight `-k prerequis` witnesses were GREEN.**

 Item `A3` declared ``*Prérequis* : AUCUN`` and the judge read **`OWNER`** — a NARRATIVE line
 seven lines above quoted ``*Prérequis* : OWNER`` inside backticks, and `field()` returns the
 FIRST one. `A3` was published NOT STARTABLE **by its own documentation**.

 **Both directions are drawn, and it is the second that is dangerous**: prose quoting
 ``AUCUN`` above a real `OWNER` used to make the item startable with the barrier GREEN. A
 witness that only drew the first direction would have left the escape open.

 The third case is the counter-proof that stops a "fix" from breaking everything: a
 decoration up front (``…panne.** *Produit* : …``) IS a declaration — 61 real bullets of this
 repo use it. Without it, removing every decorated declaration would pass this witness.
 """
    fields_block = (
        "  *Produit* : p\n  *Fini quand* : f\n  *Dépend de* : AUCUNE\n"
        "  *Prérequis* : %s\n  *À lire* : x\n  *Taille* : 1\n"
    )
    head_block = "# PLAN — d\n\n> **Cap** : c\n\n"

    cites_owner = (
        head_block + "- **Z1** \U00002B1C t.\n  Narrative : `*Prérequis* : OWNER` was blocking.\n" + fields_block % "AUCUN"
    )
    item = read_plan(cites_owner).items[0]
    assert item.field("prerequis") == "AUCUN", item.field("prerequis")
    assert item.startable, "a CITATION of OWNER blocked an item whose field says AUCUN"

    cites_aucun = (
        head_block + "- **Z2** \U00002B1C t.\n  Narrative : `*Prérequis* : AUCUN` was passing.\n" + fields_block % "OWNER"
    )
    item = read_plan(cites_aucun).items[0]
    assert item.field("prerequis") == "OWNER", item.field("prerequis")
    assert not item.startable, (
        "a CITATION of AUCUN made an item startable whose field says OWNER — "
        "the escape, and it passes the barrier GREEN"
    )

    cites_quotation_marks = (
        head_block
        + "- **Z4** \U00002B1C t.\n  Narrative : an item « *Prérequis* : OWNER » was getting out.\n"
        + fields_block % "AUCUN"
    )
    item = read_plan(cites_quotation_marks).items[0]
    assert item.field("prerequis") == "AUCUN", item.field("prerequis")
    assert item.startable, "a citation in QUOTATION MARKS blocked an item whose field says AUCUN"

    decorated = head_block + "- **Z3** \U00002B1C t.\n  **breakdown.** *Produit* : p\n" + fields_block % "AUCUN"
    assert len(read_plan(decorated).items[0].declared_fields) == 6, (
        "a declaration behind a decoration up front was lost: 61 real bullets "
        "of this repo use it"
    )

    # **THE CONFESSION WAS REFUTED, AND PINNING IT PAID OFF.** This witness used to assert that
    # the citation behind BOLD passed, with a comment: *"the day somebody closes this half, they
    # will have to decide it here, by reading it"*. A third party closed it by naming the signal
    # missed here: the premise (two shapes indistinguishable ON THE LINE) was true, the conclusion
    # false — the reader's question is about the ITEM. **Between two declarations of the same
    # field, the one that OPENS its line wins.** Cost re-measured here, whole corpus: **1172 items,
    # 0 reading changes**.
    # **THIRD STATE OF THIS DECISION, AND IT IS THE RIGHT ONE.** First the decorated citation used
    # to STEAL (pinned as a hole); then an arbiter "the canonical one wins" made it lose; a third
    # party showed that arbiter is **structurally inoperative** on declarations sitting on the
    # BULLET LINE (**47 items**) and on the **332 decorated declarations** — none of them can "open
    # its line". The reader now therefore **REFUSES** any second declaration instead of picking
    # one: *faced with two answers to the same question, nobody guesses* (the `id_duplique`
    # precedent).
    cites_bold = (
        head_block
        + "- **Z5** \U00002B1C t.\n  **Defect.** *Prérequis* : OWNER was read wrongly.\n"
        + fields_block % "AUCUN"
    )
    reading_result = read_plan(cites_bold)
    # **FOURTH STATE, AND THIS ONE IS A PINNED CONFESSION.** The decorated citation used to
    # STEAL, then LOSE against an arbiter, then get REFUSED — and that refusal was **withdrawn**: it
    # punished the very remedy `FORMAT_PLAN.md` orders people to write (**224 decorated declarations
    # over 149 items** one line from refusal), was not bounded, carried a false message, and did not
    # protect the output.
    # The theft is therefore **OPEN**, and this witness freezes it so it does not move in silence.
    assert reading_result.problems == (), reading_result.problems
    assert reading_result.items[0].field("prerequis").startswith("OWNER"), (
        "the decorated-citation theft has closed up — check that the remedy the format prescribes "
        "(adding the canonical declaration) stays ACCEPTED before removing this confession"
    )

    for label, prose in (
        ("double backtick", "``*Prérequis* : OWNER``"),
        ("straight quotes", '"*Prérequis* : OWNER"'),
        ("curly quotes", "“*Prérequis* : OWNER”"),
    ):
        raw_text = head_block + f"- **Z6** \U00002B1C t.\n  Narrative : {prose} was passing.\n" + fields_block % "AUCUN"
        assert read_plan(raw_text).items[0].field("prerequis") == "AUCUN", label

    # **WHAT FOLLOWS PINS THE REAL RESIDUAL, NOT A GUARANTEE.** When the item declares the field
    # NOWHERE, a prose citation **CREATES** it — the "the canonical one wins" arbiter has nothing to
    # arbitrate if there is only one declaration, quoted or not. A real commit proved that the
    # level-2 barrier then counts a field nobody declared. *Pinned so it does not move in
    # silence; closing this residual requires forbidding a decorated shape from CREATING a
    # field, which would break the corpus's 332 real decorated declarations.*
    without_declaration = (
        head_block + "- **Z7** \U00002B1C t.\n  **Defect (ASCII).** *Prérequis* : OWNER was read wrongly.\n"
        "  *Produit* : p\n  *Fini quand* : f\n  *Dépend de* : AUCUNE\n"
        "  *À lire* : a\n  *Taille* : t\n"
    )
    assert read_plan(without_declaration).items[0].field("prerequis") is not None, (
        "the residual has closed up — check that the corpus's 332 decorated declarations survive "
        "before removing this confession"
    )


def test_NO_real_item_declares_a_field_BEFORE_its_canonical_declaration() -> None:
    """ **THE PIN on `A3`'s `c1` clause, declared NOT HELD with its cost measured.**

 The reader returns the **first** marker: a decorated citation placed BEFORE the real
 declaration therefore steals its value. The three possible remedies were costed — changing
 nothing breaks **0**, "the last one wins" breaks **51 items** that declare on their bullet
 line, forbidding the decorated declaration breaks **224 over 149 items**. *A remedy that
 breaks 51 or 224 living declarations to close a hole with 0 occurrences costs more than it
 buys.*

 **This witness is what stops that decision from being a wish.** It counts, over the REAL
 corpus, items where the same field is declared **twice**, one of them **before** the canonical
 shape — and demands **0**. The day an occurrence appears, it reddens and the decision gets
 re-made **with a non-empty population**, instead of resting on a "0 today" that ages on its
 own.

 It draws the WHOLE corpus (`os.walk(followlinks=True)` — `rglob` does not traverse links, and
 `projects/` is one) and **asserts its own population**: a bench that runs on 0 items is
 green for the wrong reason.
 """
    import os

    walk_root = Path(__file__).resolve().parents[2]
    stolen: list[tuple[str, str]] = []
    items_read = 0
    for base, _dirs, filenames in os.walk(walk_root, followlinks=True):
        if "/.git" in base or "/.venv" in base:
            continue
        for nom in filenames:
            if not nom.endswith(".md"):
                continue
            file_path = Path(base) / nom
            try:
                raw_text = file_path.read_text(encoding="utf-8-sig")
            except (OSError, UnicodeDecodeError):
                continue
            for item in read_plan(raw_text).items:
                items_read += 1
                seen_tokens: set[str] = set()
                for text_line in (item.title, *item.detail):
                    for marker in FIELD_MARKER_RE.finditer(text_line):
                        token = _FIELD_BY_KEY.get(_field_key(marker.group(2)))
                        if token is None or not _field_declares(text_line, marker.start()):
                            continue
                        canonical = not text_line[: marker.start()].strip()
                        if token in seen_tokens and canonical:
                            stolen.append((str(file_path.relative_to(walk_root)), token))
                        seen_tokens.add(token)

    # THE NUMBER THAT USED TO BE WRITTEN HERE WAS DEAD, and the place made it undetectable. This
    # message said "the corpus carries 1173" — a hand-written literal appearing ONCE in the whole
    # file, never computed, never compared. In an EMPTY directory the sentence would still have
    # claimed "the corpus carries 1173".
    # AND THE REPLACEMENT NUMBER CARRIED THE SAME DEFECT: a walk that reads N item-occurrences
    # over a tree holding clones, worktrees and throwaway copies measures the COPIES, not the
    # population. Two true numbers measuring different things: publish BOTH, or neither.
    # The worst part is the PLACE. A frozen figure inside an ASSERTION message looks like PROOF,
    # and it is the last place anyone checks whether a number is still alive — it only ever prints
    # the day the gate falls, read in a hurry by someone looking for a cause.
    # The remedy is NOT to refresh it: that recreates the second source that just rotted. Both
    # numbers were one — `items_read` IS the size of the corpus walked — so the message now keeps
    # only what it actually knows: the floor, and what it read.
    assert items_read > 500, (
        f"degenerate population: {items_read} items read against a floor of 500. This floor is not "
        "a figure to be trusted on its own: it refuses a walk that found nothing, because the "
        "assertion that follows is trivially true on an empty population."
    )
    # THIS MESSAGE NEVER PUBLISHES A COUNT ALONE. Measured: it once announced 27 occurrences —
    # read one by one, a SINGLE document, replicated across clones, worktrees and `tmp*` folders of
    # the same project. A reader triaging on "27" believed in a live class where there is ONE line
    # to fix. And the obvious escape does not work: excluding HIDDEN folders removes only 9 of
    # the 27 — the remaining two thirds are perfectly VISIBLE clones. *A rule that targets
    # throwaway copies by judging their NAME only catches the ones whose author thought to hide
    # them.*
    # Hence the shape below — occurrences / paths / DISTINCT FILE NAMES. The last number is the
    # only one that says whether this is a class or a single document copied around.
    paths_seen = sorted({file_path for file_path, _ in stolen})
    documents_seen = sorted({file_path.rsplit("/", 1)[-1] for file_path, _ in stolen})
    assert stolen == [], (
        f"a field is declared BEFORE its canonical declaration: {len(stolen)} occurrence(s) spread "
        f"over {len(paths_seen)} path(s), but only {len(documents_seen)} distinct file name(s) — "
        f"{documents_seen}. \U000026D4 Compare these three numbers BEFORE triaging: this walk crosses clones "
        "and throwaway copies, so the occurrences count the COPIES; the last number says how many "
        "documents really need fixing. The hole the `c1` clause declares NOT HELD now has a LIVE "
        'occurrence; the "status quo + convention" decision rested on an EMPTY population — '
        f"re-make it with this one: {paths_seen}"
    )


def test_a_document_carrying_a_teaching_block_AND_a_commented_draft_yields_ZERO_item(
    tmp_path: Path,
) -> None:
    """ **`A7` — THE READER HAD NO NOTION OF CITATION AT THE DOCUMENT LEVEL.** `A1` had
 closed this class at the ITEM level (a marker quoted inside backticks is no longer a
 declaration); it remained WHOLLY OPEN one floor up, where the question is not "does this
 marker declare?" but "is this LINE a plan, or the citation of a plan?".

 Measured, live: `docs/FORMAT_PLAN.md` — the document that TEACHES this format — used to see its
 own teaching examples read as ten real items, and the commit gate refused the
 document that explains the format. *The same class bit a second, independent module two
 hours later (another chat's obligation registry).*

 This witness replays the EXACT reproduction the orchestrator measured before this fix.
 """
    head_block = "# PLAN — d\n\n> **Cap** : c\n\n"
    six_fields = "".join(
        f"  *{n}* : {v}\n"
        for n, v in (
            ("Produit", "p"),
            ("Fini quand", "f"),
            ("Dépend de", "AUCUNE"),
            ("Prérequis", "AUCUN"),
            ("À lire", "a"),
            ("Taille", "t"),
        )
    )
    before_block = head_block + "- **A0** \U00002B1C real item before.\n" + six_fields
    teaching_block = "\n```markdown\n- **X9** \U00002B1C teaching example.\n  *Produit* : p\n  *Fini quand* : f\n```\n"
    parked_draft = (
        "\n<!-- draft not ready :\n- **Z9** \U00002B1C idea.\n  *Produit* : p\n  *Fini quand* : f\n-->\n"
    )
    after_block = "- **A1** \U00002B1C real item after.\n" + six_fields

    from mnemosyne.production.plan_format import required_field_problems

    reading_result = read_plan(before_block + teaching_block + parked_draft + after_block)

    assert [i.ident for i in reading_result.items] == ["A0", "A1"], [i.ident for i in reading_result.items]
    assert (
        required_field_problems(
            reading_result,
            required=("produit", "fini_quand", "depend_de", "prerequis", "a_lire", "taille"),
        )
        == ()
    )

    # And the REAL items neighbouring these two shapes stay read IDENTICALLY, an explicit clause
    # of the Fini-quand: it is not enough to not capture X9/Z9, nothing around them must be
    # damaged either.
    without_the_citations = read_plan(before_block + after_block)
    assert reading_result.items[0].fields == without_the_citations.items[0].fields
    assert reading_result.items[1].fields == without_the_citations.items[1].fields


def test_an_INDENTED_code_block_under_a_real_item_keeps_working(tmp_path: Path) -> None:
    """ Counter-proof: the document-level guard must NOT swallow a fenced example that
 the item itself carries in its own block (a mechanism already handled by `read_item_fields`) —
 closing it must let through the field that FOLLOWS it in the same item."""
    raw_text = (
        "# PLAN — d\n\n> **Cap** : c\n\n"
        "- **A0** \U00002B1C item with an example in its block.\n"
        "  *Produit* : see the example\n"
        "  ```python\n"
        "  example = 1\n"
        "  ```\n"
        "  *Fini quand* : f\n"
        "  *Dépend de* : AUCUNE\n"
        "  *Prérequis* : AUCUN\n"
        "  *À lire* : a\n"
        "  *Taille* : t\n"
    )
    reading_result = read_plan(raw_text)
    assert [i.ident for i in reading_result.items] == ["A0"]
    assert reading_result.items[0].field("fini_quand") == "f"


def test_a_fence_NESTED_with_a_DIFFERENT_DELIMITER_stays_inside_the_outer_block(
    tmp_path: Path,
) -> None:
    """ **AUDIT DELEGATED ON 2026-08-15, INSIDE `A7`'S CLAUSE — first version NOT HELD.**

 The first version of the document-level guard was a plain boolean, flipped by ANY line
 resembling a fence, regardless of character or length. A ``` ```markdown ``` nested
 inside a ``` ~~~ ``` — the shape `docs/FORMAT_PLAN.md` MUST use to show a fence example
 without the Markdown renderer closing it prematurely — desynchronized that counter:
 a PROSE line merely mentioning a fence marker (not a real nested opening) flipped the
 state, and the teaching item that followed became a REAL item.

 The fix reuses `_fence_ferme` — the SAME predicate as `_scan_fences` — instead of a
 second, weaker toggle: only a closer of the SAME character, at least as long a run, with no
 info string, closes the open block. A line that *resembles* a fence but does not match
 stays CONTENT of the outer block, never a closer.
 """
    six = "".join(
        f"  *{n}* : {v}\n"
        for n, v in (
            ("Produit", "p"),
            ("Fini quand", "f"),
            ("Dépend de", "AUCUNE"),
            ("Prérequis", "AUCUN"),
            ("À lire", "a"),
            ("Taille", "t"),
        )
    )
    raw_text = (
        "# PLAN — d\n\n> **Cap** : c\n\n"
        "~~~markdown\n"
        "Here is what a fence marker alone on its line looks like :\n"
        "```\n"
        "Below, an example of a real item :\n"
        "- **X9** \U00002B1C teaching example.\n"
        "  *Produit* : p\n"
        "~~~\n\n"
        "- **A1** \U00002B1C real item that must survive.\n" + six
    )
    reading_result = read_plan(raw_text)
    assert [i.ident for i in reading_result.items] == ["A1"], [i.ident for i in reading_result.items]
    assert reading_result.problems == (), reading_result.problems


def test_A8_a_field_WAS_STOLEN_IN_SILENCE_by_its_own_example_ZERO_refusal() -> None:
    """A8 - `read_item_fields` carried ITS OWN copy of the naive toggle that A7 closed at the
 document level — a different function, same class, ZERO refusal (the worst form: nothing
 signals the theft).

 Reproduced on today's code (before this fix): ``produit`` held
 ``TEACHING_EXAMPLE`` — the example nested inside the item's block, never the real value
 written below — and ``reading_result.problems`` was empty. An item that SHOWS the shape of a nested
 example (a ``` nested inside a ~~~, the shape this format must be able to illustrate) had its
 real field overwritten by the example's value, with no gate saying so.

 **SECOND CORRECTION, BY AN ISOLATED AUDIT THIS TIME — my first characterisation
 ("EVEN = zero refusal, ODD = already refuses") WAS WRONG.** Parity governs NOTHING by
 itself: it neither steals nor refuses. **The real discriminant is where the item's REAL
 FIELDS fall relative to the desynchronisation** — and the desynchronisation itself exists as
 soon as A SINGLE nested fence of a different character appears, EVEN or ODD. If the
 real fields are written AFTER the desynchronised zone, they get swallowed too and
 ``missing_fields`` refuses. But if the teaching EXAMPLE already fills all six fields — the
 shape `docs/FORMAT_PLAN.md` ACTUALLY writes (a COMPLETE item example, not one isolated
 field) — nothing is missing, so nothing refuses, EVEN with a single nested fence (ODD).
 *`fence_complete` below steals all SIX fields, zero refusal, with ODD* — the exact opposite
 of what my first correction claimed, and the worst instance of the class the item exists to
 close.
 """
    from mnemosyne.production.plan_format import required_field_problems

    nested_pair = plan(
        *HEAD,
        "- **A1** \U00002B1C an item that shows a nested example.",
        "  Example :",
        "  ~~~markdown",
        "  ```",
        "  *Produit* : TEACHING_EXAMPLE",
        "  ```",
        "  ~~~",
        "  *Produit* : REAL_VALUE",
        "  *Fini quand* : f",
        "  *Dépend de* : AUCUNE",
        "  *Prérequis* : AUCUN",
        "  *À lire* : a",
        "  *Taille* : t",
    )
    reading_result = read_plan(nested_pair)
    assert [i.ident for i in reading_result.items] == ["A1"]
    assert reading_result.items[0].field("produit") == "REAL_VALUE"
    assert reading_result.problems == () and required_field_problems(reading_result) == ()

    fence_alone = plan(
        *HEAD,
        "- **A2** \U00002B1C an item that shows a nested fence on its own.",
        "  Example :",
        "  ~~~markdown",
        "  ```",
        "  *Produit* : TEACHING_EXAMPLE",
        "  ~~~",
        "  *Produit* : REAL_VALUE",
        "  *Fini quand* : f",
        "  *Dépend de* : AUCUNE",
        "  *Prérequis* : AUCUN",
        "  *À lire* : a",
        "  *Taille* : t",
    )
    reading2 = read_plan(fence_alone)
    assert [i.ident for i in reading2.items] == ["A2"]
    assert reading2.items[0].field("produit") == "REAL_VALUE"
    assert reading2.problems == () and required_field_problems(reading2) == ()

    # The REAL shape of docs/FORMAT_PLAN.md (l. 251-255): the nested example shows a COMPLETE
    # teaching item, all six fields included — on the code from BEFORE this fix, measured by the
    # isolated audit, all SIX were stolen and `required_field_problems` returned `()`: nothing was
    # missing since the example had already filled everything in. The worst instance, a single
    # fence (ODD).
    fence_complete = plan(
        *HEAD,
        "- **A3** \U00002B1C an item that shows a COMPLETE teaching example.",
        "  Example :",
        "  ~~~markdown",
        "  - **EXAMPLE** \U00002B1C teaching item",
        "    ```",
        "    *Produit* : TEACHING_EXAMPLE",
        "    *Fini quand* : TEACHING_EXAMPLE",
        "    *Dépend de* : TEACHING_EXAMPLE",
        "    *Prérequis* : TEACHING_EXAMPLE",
        "    *À lire* : TEACHING_EXAMPLE",
        "    *Taille* : TEACHING_EXAMPLE",
        "  ~~~",
        "  *Produit* : REAL_VALUE",
        "  *Fini quand* : REAL_VALUE",
        "  *Dépend de* : REAL_VALUE",
        "  *Prérequis* : REAL_VALUE",
        "  *À lire* : REAL_VALUE",
        "  *Taille* : REAL_VALUE",
    )
    reading3 = read_plan(fence_complete)
    assert [i.ident for i in reading3.items] == ["A3"]
    for field_token in ("produit", "fini_quand", "depend_de", "prerequis", "a_lire", "taille"):
        assert reading3.items[0].field(field_token) == "REAL_VALUE", (field_token, reading3.items[0].fields)
    assert reading3.problems == () and required_field_problems(reading3) == ()


def test_an_UNPAIRED_fence_in_a_commented_draft_does_NOT_EAT_the_rest_of_the_document(
    tmp_path: Path,
) -> None:
    """ **AUDIT DELEGATED ON 2026-08-15, INSIDE `A7`'S CLAUSE — first version NOT HELD.**

 The first version tested the fence BEFORE the comment state. An output excerpt pasted
 into a `<!-- -->` draft — mundane, a single unpaired ``` ``` ``` line — flipped
 `en_bloc_de_code` while STILL inside the comment; the real `-->` that followed then fell
 into the wrong `continue` and was NEVER seen. **Both regions stayed open until the end of the
 file**, swallowing every real item that followed — WITHOUT RAISING A SINGLE REFUSAL.

 The fix strictly prioritises the already-open block: as long as a comment is open, no
 line inside it opens or closes a fence — only a `-->` closes it, exactly like a real
 HTML comment block, which governs until ITS OWN closing.
 """
    six = "".join(
        f"  *{n}* : {v}\n"
        for n, v in (
            ("Produit", "p"),
            ("Fini quand", "f"),
            ("Dépend de", "AUCUNE"),
            ("Prérequis", "AUCUN"),
            ("À lire", "a"),
            ("Taille", "t"),
        )
    )
    raw_text = (
        "# PLAN — d\n\n> **Cap** : c\n\n"
        "<!-- draft\n"
        "pasted output excerpt :\n"
        "```\n"
        "an unpaired fence inside the comment\n"
        "more content\n"
        "-->\n\n"
        "- **A1** \U00002B1C real item that must survive.\n" + six
    )
    reading_result = read_plan(raw_text)
    assert [i.ident for i in reading_result.items] == ["A1"], [i.ident for i in reading_result.items]
    assert reading_result.problems == (), reading_result.problems


def test_A10_a_field_AFTER_a_NON_INDENTED_fence_is_now_READ(tmp_path: Path) -> None:
    """A10: `_item_block` used to stop at the FIRST non-indented fence, even one OPENING it — an
    item whose example is written in column 0 (legal, `FORMAT_PLAN.md` forbids it nowhere) lost
    everything that follows, and `*Dépend de*` is written almost always at the end of an item.
    Measured on the sibling project: 108/168 items (64%). Reproduced here on a pure fixture: the field after
    the fence MUST be read."""
    raw_text = (
        "# PLAN — d\n\n> **Cap** : c\n\n"
        "- **A1** \U00002B1C **item whose example is NOT indented.**\n"
        "  *Produit* : p\n"
        "```bash\n"
        "echo example at column 0, the way the sibling project writes it\n"
        "```\n"
        "  *Fini quand* : f\n"
        "  *Dépend de* : AUCUNE\n"
        "  *Prérequis* : AUCUN\n"
        "  *À lire* : a\n"
        "  *Taille* : t\n"
    )
    reading_result = read_plan(raw_text)
    assert [i.ident for i in reading_result.items] == ["A1"]
    item = reading_result.items[0]
    assert item.field("fini_quand") == "f", "the field AFTER the non-indented fence must be read"
    assert item.field("depend_de") == "AUCUNE"
    assert reading_result.problems == (), reading_result.problems


def test_A10_the_CONTENT_of_a_NON_INDENTED_fence_is_never_read_as_a_declaration(
    tmp_path: Path,
) -> None:
    """The negative counterpart of the previous test — crossing the fence must not read its
    CONTENT as a real field, exactly the guarantee already held for an indented fence."""
    raw_text = (
        "# PLAN — d\n\n> **Cap** : c\n\n"
        "- **A1** \U00002B1C **item that shows the shape, non-indented fence.**\n"
        "  *Produit* : the reader\n"
        "```markdown\n"
        "- **X1** \U00002B1C title\n"
        "  *Fini quand* : WHAT NOBODY DECLARED HERE\n"
        "```\n"
        "  *Fini quand* : the real value\n"
    )
    reading_result = read_plan(raw_text)
    (item,) = reading_result.items
    assert item.field("produit") == "the reader"
    assert item.field("fini_quand") == "the real value", (
        "the non-indented fence must close, not freeze the field on its content"
    )


def test_A10_a_NON_INDENTED_fence_NEVER_closed_is_covered_by_bloc_non_ferme_not_here(
    tmp_path: Path,
) -> None:
    """The healthy fallback: `_scan_fences` never closes an orphaned fence, so the block extends
    to the end of the file instead of re-deciding anything — `bloc_non_ferme` (a separate
    refusal, already carried by `read_plan`) stays the ONLY verdict on this class, never a
    second one here."""
    raw_text = (
        "# PLAN — d\n\n> **Cap** : c\n\n"
        "- **A1** \U00002B1C **item whose fence never closes.**\n"
        "  *Produit* : p\n"
        "```bash\n"
        "echo never closed\n"
        "  *Fini quand* : f\n"
    )
    reading_result = read_plan(raw_text)
    (item,) = reading_result.items
    # Depending on which floor sees it first, this class is already named either at the
    # DOCUMENT level (`bloc_document_non_ferme`, A7 — the case measured here: the fence opens
    # only one item, so nothing else closes it before the end of the file), or at the ARC level
    # (`bloc_non_ferme`) — never a third verdict posed here, in `_item_block`.
    assert any(p.kind in ("bloc_non_ferme", "bloc_document_non_ferme") for p in reading_result.problems), (
        reading_result.problems
    )
    # A field written AFTER the opener, inside the never-closed fence, is NOT a real
    # declaration — content, never a closer.
    assert item.field("fini_quand") is None


def test_the_FIRST_closer_ALWAYS_closes_even_quoted_in_backticks_CommonMark_without_exception(
    tmp_path: Path,
) -> None:
    """ **AUDIT DELEGATED ON 2026-08-15, INSIDE `A7`'S CLAUSE — THIRD ROUND, NOT HELD (C2):
 THE SECOND ROUND'S FIX (C1) HAD DRIFTED AWAY FROM THE REFERENCE.**

 The second round had added a notion of citation (`_hors_code`/`_hors_citation`) to the
 closing of a comment — to protect a comment from THIS very item, which quoted `` `-->` ``
 inside backticks to talk about it. But in HTML/CommonMark, a backtick has **no meaning**
 inside an already-open comment: it is the **FIRST** `-->`, without exception, that closes it.
 Remedy C1 therefore manufactured a FALSE NEGATIVE — a real `-->`, preceded on the same
 line by an unpaired backtick, stopped being recognised — and resurrected exactly the damage
 from `D2`: a clean `-->` further down the document closed TOO LATE, swallowing a real item
 between the two, WITHOUT A SINGLE REFUSAL.

 This witness replaces the old one (which wrongly expected the comment to stay open past the
 quoted marker): it fixes the REAL behaviour, matching the reference — writing `-->` inside
 a comment, even inside backticks, IS a PROSE trap, not a reader defect. The real lesson lies
 elsewhere: stop writing that trap (see `A7`'s own history, which had to rewrite its own prose
 to stop doing it).
 """
    six = "".join(
        f"  *{n}* : {v}\n"
        for n, v in (
            ("Produit", "p"),
            ("Fini quand", "f"),
            ("Dépend de", "AUCUNE"),
            ("Prérequis", "AUCUN"),
            ("À lire", "a"),
            ("Taille", "t"),
        )
    )
    raw_text = (
        "# PLAN — d\n\n> **Cap** : c\n\n"
        "<!-- draft explaining the `-->` marker inside backticks, the way this item does\n"
        "- **X9** \U00002B1C must not be read.\n"
        "  *Produit* : p\n"
        "-->\n\n"
        "- **A1** \U00002B1C real item that must survive.\n" + six
    )
    reading_result = read_plan(raw_text)
    # The comment closes at the FIRST `-->`, so X9 and the "intended" `-->` are outside the
    # comment — X9 becomes a real item (5 missing fields), and A1 is read normally.
    assert [i.ident for i in reading_result.items] == ["X9", "A1"], [i.ident for i in reading_result.items]


def test_a_CLEAN_closer_further_down_no_longer_closes_TOO_LATE_nor_swallows_a_real_item(
    tmp_path: Path,
) -> None:
    """ **AUDIT DELEGATED ON 2026-08-15, INSIDE `A7`'S CLAUSE — THIRD ROUND (C2-b), THE
 REGRESSION THAT FIX C1 HAD INTRODUCED.**

 A comment quotes `-->` inside backticks (a mundane mention, not an intent to open/
 close), THEN a second author comment, FURTHER DOWN, closes cleanly. With C1 (removed),
 the first comment stayed open until the second `-->` — swallowing a REAL item between the
 two, **without raising a single refusal**. The exact shape of `D2`, resurrected by remedy
 `C1`. With the real rule restored, the first comment closes at ITS first `-->` (inside
 the backticks), and the real item between the two becomes visible again.
 """
    six = "".join(
        f"  *{n}* : {v}\n"
        for n, v in (
            ("Produit", "p"),
            ("Fini quand", "f"),
            ("Dépend de", "AUCUNE"),
            ("Prérequis", "AUCUN"),
            ("À lire", "a"),
            ("Taille", "t"),
        )
    )
    raw_text = (
        "# PLAN — d\n\n> **Cap** : c\n\n"
        "<!-- passing note : the `-->` marker closes a comment\n"
        "- **Z9** \U00002B1C real item between the two comments.\n"
        + six
        + "\n<!-- a second author comment, independent, closes cleanly -->\n\n"
        "- **W9** \U00002B1C real item after.\n" + six
    )
    reading_result = read_plan(raw_text)
    assert [i.ident for i in reading_result.items] == ["Z9", "W9"], [i.ident for i in reading_result.items]
    assert reading_result.problems == (), reading_result.problems


def test_a_document_level_region_NEVER_CLOSED_is_REFUSED_not_swallowed_in_silence() -> None:
    """ **AUDIT DELEGATED ON 2026-08-15, OUTSIDE A7'S CLAUSE (H-a) — fixed anyway.**

 A document-level fence or comment that never closed used to swallow the rest of the file IN
 SILENCE, without raising a single refusal — its twin (a never-closed fence, elsewhere in this
 module) already says "a mechanism that goes quiet must be able to SAY it went quiet". Both
 shapes now get their own refusal, named and tested separately.
 """
    six = "".join(
        f"  *{n}* : {v}\n"
        for n, v in (
            ("Produit", "p"),
            ("Fini quand", "f"),
            ("Dépend de", "AUCUNE"),
            ("Prérequis", "AUCUN"),
            ("À lire", "a"),
            ("Taille", "t"),
        )
    )
    head_block = "# PLAN — d\n\n> **Cap** : c\n\n"

    fence = read_plan(head_block + "~~~markdown\n- **A1** \U00002B1C never read.\n" + six)
    assert fence.items == ()
    assert [p.kind for p in fence.problems] == ["bloc_document_non_ferme"]

    comment_block = read_plan(head_block + "<!-- draft never closed\n- **A1** \U00002B1C never read.\n" + six)
    assert comment_block.items == ()
    assert [p.kind for p in comment_block.problems] == ["commentaire_document_non_ferme"]


def test_an_EMPTY_HTML_comment_closes_on_ITS_OWN_line_not_two_lines_later() -> None:
    """ **AUDIT DELEGATED ON 2026-08-15, INSIDE A7'S CLAUSE — FOURTH ROUND (F1).**

 The guard asked the closing question at TWO places, on TWO different strings:
 `raw` on continuation, `raw[4:]` at opening. They diverge only on `<!-->` and `<!--->`
 — the two shapes of an EMPTY HTML comment, where the `-->` overlaps indices 0-3 that
 `raw[4:]` slices in two. `<!-->` therefore stayed open until the NEXT author comment,
 swallowing every real item in between — WITHOUT RAISING A SINGLE REFUSAL. The exact shape of
 `D2`/`C2`, a third time, born from a question asked twice on two strings instead of one.

 Independent reference (the stdlib's `html.parser`, and CommonMark HTML block type 2): both
 close `<!-->` on ITS OWN line. The reader must do the same.
 """
    six = "".join(
        f"  *{n}* : {v}\n"
        for n, v in (
            ("Produit", "p"),
            ("Fini quand", "f"),
            ("Dépend de", "AUCUNE"),
            ("Prérequis", "AUCUN"),
            ("À lire", "a"),
            ("Taille", "t"),
        )
    )
    head_block = "# PLAN — d\n\n> **Cap** : c\n\n"
    for empty_comment in ("<!-->", "<!--->"):
        raw_text = (
            head_block + empty_comment + "\n"
            "- **R1** \U00002B1C real item.\n"
            + six
            + "<!-- an author note, further down, that closes cleanly -->\n"
            "- **R2** \U00002B1C real item.\n" + six
        )
        reading_result = read_plan(raw_text)
        assert [i.ident for i in reading_result.items] == ["R1", "R2"], (
            empty_comment,
            [i.ident for i in reading_result.items],
        )
        assert reading_result.problems == (), (empty_comment, reading_result.problems)


def test_a_closing_line_CARRYING_an_info_string_does_NOT_close_the_region(
    tmp_path: Path,
) -> None:
    """ **AUDIT DELEGATED ON 2026-08-15, OUTSIDE A7'S CLAUSE (G2) — a real mechanism, no
 witness.**

 `_fence_ferme` refuses a closer carrying an info string (` ``` python ` after a bare ` ``` `)
 — that is the CommonMark rule, and the predicate already codes it (`not found.group(3)`). But
 NONE of the 293 existing witnesses exercised this precise clause: `D1` only exercises the
 character. Delegated sabotage: removing `not found.group(3)` **breaks no existing witness**
 (293/293 green) while disarming a real, reachable clause — on a page with two labelled fenced
 examples, the neighbouring real item disappears and a nested example gets promoted to a real
 item. The exact class this item exists to close.
 """
    six = "".join(
        f"  *{n}* : {v}\n"
        for n, v in (
            ("Produit", "p"),
            ("Fini quand", "f"),
            ("Dépend de", "AUCUNE"),
            ("Prérequis", "AUCUN"),
            ("À lire", "a"),
            ("Taille", "t"),
        )
    )
    raw_text = (
        "# PLAN — d\n\n> **Cap** : c\n\n"
        "~~~markdown\n"
        "- **X9** \U00002B1C teaching example.\n"
        "  *Produit* : p\n"
        "~~~python\n"
        "- **Y9** \U00002B1C must not be read either -- this is NOT a closer.\n"
        "  *Produit* : p\n"
        "~~~\n\n"
        "- **A1** \U00002B1C real item that must survive.\n" + six
    )
    reading_result = read_plan(raw_text)
    assert [i.ident for i in reading_result.items] == ["A1"], [i.ident for i in reading_result.items]
    assert reading_result.problems == (), reading_result.problems


def test_an_INDENTED_document_level_comment_no_longer_STEALS_a_real_items_ident(
    tmp_path: Path,
) -> None:
    """ **AUDIT DELEGATED ON 2026-08-15, OUTSIDE A7'S CLAUSE (G4) — fixed, cost measured at
 ZERO.**

 Opening a document-level comment required STRICT column 0 when the fence, one floor up,
 tolerates `[ \\t]{0,3}` like CommonMark. A draft whose OPENER is indented (its content
 staying in column 0) therefore escaped both mechanisms at once — neither the document's nor
 the item's (which only sees a bullet's own block) — and a bullet in column 0 inside it could
 **STEAL THE IDENT** of a real item, getting the latter refused by an `id_duplique` accusing
 the innocent line. Fixed with the same tolerance as the fence.
 """
    six = "".join(
        f"  *{n}* : {v}\n"
        for n, v in (
            ("Produit", "p"),
            ("Fini quand", "f"),
            ("Dépend de", "AUCUNE"),
            ("Prérequis", "AUCUN"),
            ("À lire", "a"),
            ("Taille", "t"),
        )
    )
    raw_text = (
        "# PLAN — d\n\n> **Cap** : c\n\n"
        " <!-- draft whose opener is indented\n"
        "- **A1** \U00002B1C ident potentially stolen.\n"
        "  *Produit* : draft\n"
        "-->\n\n"
        "- **A1** \U00002B1C real item that must survive.\n" + six
    )
    reading_result = read_plan(raw_text)
    assert [i.ident for i in reading_result.items] == ["A1"], [i.ident for i in reading_result.items]
    assert reading_result.items[0].field("produit") != "draft"


# --- C2: the deliverable names a FILE, never a folder -- and declares its ground --------------
#
# MEASURED BEFORE WRITING, on this repo's 55 real items: 30 (55%) cite NO path
# in *Produit* (conceptual prose, out of this clause's scope), 2 (4%) cite ONLY
# folders (`plan/retires/`, `projects/mnemosyne/ui/`) — this clause judges that one population
# alone. A clause that refused the absence of a path would condemn more than half the
# plan the day it is armed — the same wall `prerequisite_problems` already measured and refused.


def test_a_produit_citing_ONLY_a_folder_is_refused() -> None:
    from mnemosyne.production.plan_format import produit_problems

    text = plan(*HEAD, "- **A1** \U00002B1C x", "  *Produit* : `plan/retires/`")
    reading = read_plan(text)
    (problem,) = produit_problems(reading)
    assert problem.kind == "produit_est_un_dossier"
    assert "A1" in problem.detail and "plan/retires/" in problem.detail


def test_a_produit_citing_at_least_ONE_file_is_not_refused() -> None:
    """Even alongside a folder cited in addition — a single precise file is enough to leave the
    population this clause accuses."""
    from mnemosyne.production.plan_format import produit_problems

    text = plan(
        *HEAD,
        "- **A1** \U00002B1C x",
        "  *Produit* : `plan/retires/` and the module `production/plan_condition.py`",
    )
    reading = read_plan(text)
    assert produit_problems(reading) == ()


def test_a_produit_citing_a_FILE_WITH_NO_SLASH_counts_as_resolved() -> None:
    """ AUDIT DELEGATED ON 2026-08-15 (RE-AUDIT): half of the heuristic — recognising a
 token WITHOUT `/` but carrying a short extension (`plan_format.py`) as a path-shape — was
 guarded by NO witness at all. Measured by the auditor: removing this entire branch turns ZERO
 witnesses red out of 2943, even though it carries 5 of the 23 items counted under
 `produits_resolus` on the real corpus (22% of the published figure). Sabotage-verified:
 removing `_EXTENSION_COURTE_RE` from `_chemins_cites_par_produit`'s test turns precisely THIS
 witness red."""
    from mnemosyne.production.plan_format import produit_problems, produit_resolu_rapport

    text = plan(*HEAD, "- **A1** \U00002B1C x", "  *Produit* : `plan_format.py`")
    reading = read_plan(text)
    assert produit_problems(reading) == (), "a file with no / must never be accused"
    assert produit_resolu_rapport(reading) == "produits_resolus=1/1 terrain_declare=0/1"


def test_the_same_file_cited_at_TWO_different_LINES_is_the_SAME_deliverable() -> None:
    """ AUDIT DELEGATED ON 2026-08-15 (E1, a reservation on a clause that HELD) —
 `chemins_cites_par_produit` used to return the WHOLE token, line suffix included: on the sibling project's
 real plan, 15 pairs of items writing the SAME file (``fichier.py:143`` vs.
 ``fichier.py:57-60``) were seen as TWO distinct deliverables by `plan_ordre.lots()`, which
 filed them into the same batch believing they did not collide. *A path cited twice with two
 different anchors is not two paths.*"""
    from mnemosyne.production.plan_format import chemins_cites_par_produit

    assert chemins_cites_par_produit("`scripts/x.py:143`") == ("scripts/x.py",)
    assert chemins_cites_par_produit("`scripts/x.py:57-60`") == ("scripts/x.py",)
    assert chemins_cites_par_produit("`scripts/x.py:143`") == chemins_cites_par_produit(
        "`scripts/x.py:57-60`"
    )


def test_a_produit_with_command_line_ARGUMENTS_cites_only_the_FILE() -> None:
    """Same reservation, second symptom measured by the auditor: ``validate_plan.py`` and
    ``validate_plan.py --write-artifacts`` are the SAME script — arguments are not the
    path, only the token's first word is."""
    from mnemosyne.production.plan_format import chemins_cites_par_produit

    assert chemins_cites_par_produit("`validate_plan.py --write-artifacts`") == (
        "validate_plan.py",
    )


def test_a_produit_citing_NO_path_at_all_is_OUTSIDE_the_clause_not_a_defect() -> None:
    """ The majority population measured (30/55 real ones): conceptual prose, never at fault in
 itself. This clause does NOT judge "cites a path", it judges "WHEN a path is cited, is it
 a real one" — confusing it with the former would condemn the very plan carrying it."""
    from mnemosyne.production.plan_format import produit_problems

    text = plan(*HEAD, "- **A1** \U00002B1C x", "  *Produit* : the command that settles a disagreement")
    reading = read_plan(text)
    assert produit_problems(reading) == ()


def test_produit_resolu_rapport_prints_the_TWO_ratios_TOGETHER() -> None:
    """C2's *Fini quand*, word for word: a population is judged, the output prints both
 ratios — never one published without the other, a lesson this repo already paid for twice
 over numbers that measure different things and do not talk to each other.

 AUDIT DELEGATED ON 2026-08-15 (RE-AUDIT): the original fixture (1 file, 1 folder, 1
 path-free) was DEGENERATE — a file/folder swap flips A1 resolved→accused AND A2
 accused→resolved SIMULTANEOUSLY, and the COUNT stays `1/3` before and after, a whole
 sabotage invisible to the ratio alone. Fixed with TWO files (asymmetry: a swap changes the
 total, never just the names) AND a direct assertion on `produit_problems` (the WHOLE SET
 of the accused, not just their count) — the same discipline as
 [[freeze-the-set-not-the-count]] in personal memory."""
    from mnemosyne.production.plan_format import produit_problems, produit_resolu_rapport

    text = plan(
        *HEAD,
        "- **A1** \U00002B1C x",
        "  *Produit* : `production/x.py`",
        "  *État du terrain* : nothing occupies this role",
        "- **A2** \U00002B1C y",
        "  *Produit* : `plan/retires/`",
        "- **A3** \U00002B1C z",
        "  *Produit* : a conceptual clause, no path",
        "- **A4** \U00002B1C w",
        "  *Produit* : `production/w.py`",
    )
    reading = read_plan(text)
    accused = {p.line for p in produit_problems(reading)}
    assert accused == {reading.items[1].line}, "only A2 (the folder) must be accused"
    report = produit_resolu_rapport(reading)
    assert report == "produits_resolus=2/4 terrain_declare=1/4", report


def test_etat_du_terrain_DECLARED_counts_EVEN_when_it_says_nothing() -> None:
    """"Nothing occupies this role" is a VALID and REQUIRED answer (the same precedent as
    prerequisite's `AUCUN`) — it must count as DECLARED, never as absent. A field opened and left
    blank, by contrast, does not count — the same gap `blank_fields` draws for the six mandatory
    fields."""
    from mnemosyne.production.plan_format import produit_resolu_rapport

    text = plan(
        *HEAD,
        "- **A1** \U00002B1C a",
        "  *Produit* : p",
        "  *État du terrain* : nothing occupies this role today",
        "- **A2** \U00002B1C b",
        "  *Produit* : p",
        "  *État du terrain* :",
        "- **A3** \U00002B1C c",
        "  *Produit* : p",
    )
    reading = read_plan(text)
    assert produit_resolu_rapport(reading) == "produits_resolus=0/3 terrain_declare=1/3"


def test_produit_est_un_dossier_is_registered_in_the_refusal_register() -> None:
    """An undeclared kind of refusal escapes both gates (`make plan-emit` and the completeness
    check) — the lesson `REGISTRY_REFUSALS`/`PREREQUISITE_REFUSALS` already paid for."""
    from mnemosyne.production.plan_format import ALL_REFUSAL_KINDS, PRODUIT_REFUSALS

    assert "produit_est_un_dossier" in PRODUIT_REFUSALS
    assert "produit_est_un_dossier" in ALL_REFUSAL_KINDS


def test_EVERY_KNOWN_field_is_documented_on_the_spec_page() -> None:
    """ AUDIT DELEGATED ON 2026-08-15 (RE-AUDIT): one witness guards the whole set of REFUSALS
 against the page (`test_the_spec_page_names_EXACTLY_the_refusals_the_reader_can_raise`) — none
 guarded the set of FIELDS, so `*État du terrain*` could exist in the code without existing
 anywhere an agent writing a plan could learn about it. *A document nothing points to does not
 exist* — except here it was the reverse: a FIELD nothing documents."""
    from mnemosyne.production.plan_format import EXTRA_FIELD_NAMES

    page = SPEC.read_text(encoding="utf-8")
    absent = [name for name in EXTRA_FIELD_NAMES.values() if f"`*{name}*`" not in page]
    assert not absent, f"known fields missing from docs/FORMAT_PLAN.md: {absent}"


# --- H4 - `**Succède à**` — the GATE field that links a plan to its frozen predecessor ----------


def test_succede_a_is_READ_same_pattern_as_Cap_optional_never_required() -> None:
    """A plan WITHOUT a predecessor (the most frequent case — the first plan has no one to link
    to) does not carry the field, and that is not a defect: `AUCUN` is not even required, like
    `cap`."""
    without_field = read_plan(
        plan(
            *HEAD,
            "- **A1** \U00002B1C x",
            "  *Produit* : p",
            "  *Fini quand* : f",
            "  *Dépend de* : AUCUNE",
            "  *Prérequis* : AUCUN",
            "  *À lire* : a",
            "  *Taille* : t",
        )
    )
    assert without_field.succede_a == ""

    with_field = read_plan(
        "# PLAN — v2\n\n> **Cap** : v2\n> **Succède à** : archive/plan-v1.md\n\n"
        "- **A1** \U00002B1C x\n"
    )
    assert with_field.succede_a == "archive/plan-v1.md"


def test_succede_a_is_read_ONLY_ONCE_same_pattern_as_Cap() -> None:
    """A second `**Succède à** :` line further down the document (a citation, a mention
    inside an example) must not overwrite the first declaration — the same guard as
    `cap`/`project`."""
    raw_text = (
        "# PLAN — v2\n\n> **Cap** : v2\n> **Succède à** : archive/plan-v1.md\n\n"
        "- **A1** \U00002B1C an item that MENTIONS the marker : **Succède à** : archive/plan-faux.md\n"
    )
    reading_result = read_plan(raw_text)
    assert reading_result.succede_a == "archive/plan-v1.md"


def test_merge_plan_PRESERVES_succede_a_from_the_door_for_a_folder_plan() -> None:
    """A plan in FOLDER SHAPE (D166) carries `succede_a` on its GATE — `merge_plan` must carry
    it into the merged reading, not only into the gate's own reading."""
    from mnemosyne.production.plan_format import merge_plan

    door = read_plan("# PLAN — v2\n\n> **Cap** : v2\n> **Succède à** : archive/plan-v1.md\n\n")
    arc = read_plan("- **A1** \U00002B1C x\n", origin="plan/arc-a.md")
    merged = merge_plan(door, (("plan/arc-a.md", arc),))
    assert merged.succede_a == "archive/plan-v1.md"
    assert "succede_a_hors_porte" not in {p.kind for p in merged.problems}


def test_merge_plan_REFUSES_a_succede_a_declared_ON_AN_ARC_instead_of_the_door() -> None:
    """ AUDIT DELEGATED ON 2026-08-16 (H4, Q3): `**Succède à**` follows the same rule as
 `**Cap**` — only the gate counts, `merge_plan` discards the arc's value — but a stray
 `**Cap**` breaks nothing (the title is still read elsewhere) whereas a stray `**Succède à**`
 SILENTLY disarms the one barrier H4 exists to raise. Measured with a real commit in a
 throwaway worktree: RC=0, the lost item never accused. A kind of loss H4 is supposed to
 refuse, produced by H4 itself.

 The gate declares NOTHING; the ARC declares `**Succède à**`. `merged.succede_a` stays empty
 (the gate wins, as always) — but the discarded value is no longer silent: it is a NAMED
 refusal that cites the arc's file."""
    from mnemosyne.production.plan_format import merge_plan

    door = read_plan("# PLAN — v2\n\n> **Cap** : v2\n\n")
    arc = read_plan(
        "**Succède à** : archive/plan-v1.md\n\n- **A1** \U00002B1C x\n", origin="plan/arc-a.md"
    )
    merged = merge_plan(door, (("plan/arc-a.md", arc),))
    assert merged.succede_a == ""
    problems_found = [p for p in merged.problems if p.kind == "succede_a_hors_porte"]
    assert len(problems_found) == 1, merged.problems
    assert problems_found[0].source == "plan/arc-a.md"


# --- Audit D75 (2026-08-17, `derives.py`/`PORTES_QUI_DECLARENT`) -- reservation R1 ----------------


def test_a_DOOR_field_quoted_in_backticks_or_quotation_marks_NEVER_matches() -> None:
    """ Reservation R1 from an isolated audit delegated on a NEIGHBOURING mechanism (the D176
 adoption freeze, not this module): the four GATE fields (`_TITLE_RE`/`_CAP_RE`/
 `_SUCCEDE_A_RE`/`_FORMAT_RE`) do NOT call `_hors_citation`/`_hors_code`, unlike
 `_field_declares` for ITEM fields. Checked here rather than merely asserted: their ANCHOR
 (`^\\s*(?:>\\s*)?`) already closes this case on its own -- a citation inside backticks or
 quotation marks CANNOT match, since the first non-blank character must be `*`. This test
 locks that property in: if the anchor ever changes (for instance to admit a leading
 decoration, the way `_field_declares` does), this test turns red before a real gate accepts a
 citation as a declaration.

 What this test does NOT close, and what no syntax can close (the same confession as
 `_hors_citation`'s "leading BOLD"): a BARE prose sentence, with no backtick or quotation mark,
 that opens ITS OWN line with exactly `**Format** : …`. Not observed today across the sibling project's 14
 real gates (a single occurrence each) -- see the note above `_TITLE_RE`."""
    citations = (
        "`**Format** : quoted inside backticks`",
        "« **Format** : quoted inside French guillemets »",
        "“**Format** : quoted inside curly quotes”",
        '"**Format** : quoted inside straight quotes"',
    )
    for text_line in citations:
        reading_result = read_plan("# PLAN — demo\n\n> **Cap** : c\n\n" + text_line + "\n\n- **A1** \U00002B1C x\n")
        assert reading_result.format_declare == "", (text_line, reading_result.format_declare)


# ==================================================================================================
# THE SUITE'S OWN EXEMPTION REGISTER - frozen HERE, on purpose, in a different file from the one it
# freezes. `tests/conftest.py` carries two lists of checks this distribution skips; a register of
# exemptions rots exactly like any other register, and it had rotted twice at once when this gate was
# written (2026-09-09): its header said "15" over a list of **16**, and 5 of its 16 entries were
# labelled with a cause that was not theirs. A number written by hand beside a list it does not
# compute drifts from it in silence - so the number is not written beside the list any more.
# ==================================================================================================

#: The exempted set, frozen PER LIST - never its count, and never merged into one. "14 entries" is
#: satisfied by swapping one name for another; a single merged freeze is satisfied by MOVING a name
#: from one list to the other, which is exactly the defect this pass repaired: five entries carrying
#: a cause that was not theirs. So the label is frozen along with the name. Adding, removing or
#: RE-LABELLING an exemption is a reviewed act, and it now costs an edit in two files.
FROZEN_ABSENT_GOVERNANCE_DOCUMENT: tuple[str, ...] = (
    "tests/orchestration/test_plan_format.py::test_DERIVE_md_rend_la_main_vers_les_VRAIES_commandes_de_derive_projet",
    "tests/orchestration/test_plan_format.py::test_on_the_real_plan_a_PARKED_item_carries_the_reason_it_is_parked",
    "tests/orchestration/test_plan_format.py::test_the_CONTROL_corpus_cannot_be_EMPTIED_in_silence",
    "tests/orchestration/test_plan_format.py::test_the_repos_own_living_plan_is_read_and_is_MOSTLY_PROSE",
    "tests/orchestration/test_plan_format.py::test_the_six_fields_are_read_off_THIS_repos_own_arc_and_not_only_off_a_fixture",
    "tests/orchestration/test_plan_registry.py::test_scan_plans_SEES_the_repos_own_plan_which_can_never_live_under_projects",
    "tests/test_invariants.py::test_constitution_section_5_matches_the_registered_invariants",
)

FROZEN_DOCS_TREE_SUBSET: tuple[str, ...] = (
    "tests/orchestration/test_plan_format.py::test_the_VERSIONED_half_of_the_population_is_walked_and_it_is_named_not_counted",
    "tests/orchestration/test_plan_format.py::test_the_index_check_really_FIRES_on_this_repo_and_fires_ONLY_inside_a_DOOR",
    "tests/orchestration/test_plan_format.py::test_the_two_numbers_are_stated_TOGETHER_and_neither_can_be_read_alone",
    "tests/orchestration/test_ui_contract.py::test_qui_le_tient_survit_a_la_PROSE_REELLE_des_VRAIS_postes",
    "tests/platform/test_bilan.py::test_le_vrai_bilan_existe_et_porte_ses_deux_bornes",
    "tests/platform/test_bilan.py::test_verifier_ne_touche_a_rien",
    "tests/platform/test_documents.py::test_liens_le_juge_MORD_sur_le_depot_REEL_sinon_le_vert_ne_prouve_rien",
)


def _exemption_sets() -> "dict[str, tuple[frozenset[str], str]]":
    """Read the two lists out of ``tests/conftest.py`` WITHOUT importing it.

    Parsed, never imported: `conftest.py` is already loaded by pytest as a plugin, and importing it a
    second time under its own name gives a SECOND module object whose constants can drift from the
    ones actually governing collection. The file on disk is the thing being frozen, so the file on
    disk is what is read.
    """
    import ast

    source = (REPO / "tests" / "conftest.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    out: dict[str, tuple[frozenset[str], str]] = {}
    for node in ast.walk(tree):
        target = None
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
            target = node.targets[0].id
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            target = node.target.id
        if target in ("_ABSENT_GOVERNANCE_DOCUMENT", "_DOCS_TREE_SUBSET"):
            segment = ast.get_source_segment(source, node.value) or ""
            out[target] = (frozenset(ast.literal_eval(node.value.args[0])), segment)
    return out


def test_the_suites_own_EXEMPTION_lists_are_FROZEN_and_every_name_still_EXISTS():
    """Four ways an exemption register rots, and all four are refused here.

    1. **It grows or shrinks unseen** - the SET is frozen above, in another file.
    2. **It names a test that no longer exists** - a renamed check keeps its exemption, silently,
       while the check itself is judged again under its new name and nobody notices either way.
    3. **The same check sits in both lists** - two causes claimed for one failure, so neither can be
       re-measured on its own trigger.
    4. **An entry carries no stated reason** - which is how five entries came to be labelled with a
       cause that was not theirs: the label was inherited from the block they were pasted into, not
       read off their own failure.

    This gate does NOT re-run the exempted checks: that is the `-p degel` measurement named in
    `tests/conftest.py`, and it belongs to a human re-measuring the register, not to every commit.
    What this gate buys is that the register cannot drift between two of those measurements.
    """
    # It FAILS on an absent conftest rather than skipping, and that is deliberate twice over. A
    # control that can no longer see its target must redden, never shrug - and `tests/conftest.py` is
    # TRACKED, so it is present in every clone; a skip here would be a branch that never fires while
    # adding an un-frozen skip site to this repo's own battery gate (`SAUTS_GELES`).
    conftest = REPO / "tests" / "conftest.py"
    assert conftest.is_file(), (
        f"{conftest} is gone — this freeze is watching nothing. Restore the file, or delete this "
        "check rather than leaving a gate whose target has disappeared"
    )
    sets = _exemption_sets()
    assert set(sets) == {"_ABSENT_GOVERNANCE_DOCUMENT", "_DOCS_TREE_SUBSET"}, (
        f"tests/conftest.py no longer declares the two exemption lists: found {sorted(sets)} — "
        "a list that changed name is a list this freeze stopped watching"
    )
    governance, subset = sets["_ABSENT_GOVERNANCE_DOCUMENT"][0], sets["_DOCS_TREE_SUBSET"][0]

    # (1) the SET, never the count - and PER LIST, so a re-label cannot hide inside the union
    for list_name, live_set, frozen_set in (
        ("_ABSENT_GOVERNANCE_DOCUMENT", governance, FROZEN_ABSENT_GOVERNANCE_DOCUMENT),
        ("_DOCS_TREE_SUBSET", subset, FROZEN_DOCS_TREE_SUBSET),
    ):
        assert tuple(sorted(live_set)) == frozen_set, (
            f"{list_name} moved: added={sorted(live_set - set(frozen_set))} "
            f"removed={sorted(set(frozen_set) - live_set)} — re-measure with `-p degel`, then move the "
            "freeze here in the same gesture"
        )
    # (3) one failure, one cause
    assert not (governance & subset), (
        f"exempted TWICE, under two different causes: {sorted(governance & subset)}"
    )
    # (2) every name still designates a real check
    for nodeid in FROZEN_ABSENT_GOVERNANCE_DOCUMENT + FROZEN_DOCS_TREE_SUBSET:
        file_part, _, func_name = nodeid.partition("::")
        target_file = REPO / file_part
        assert target_file.is_file(), f"{nodeid}: {file_part} no longer exists — dead exemption"
        assert f"def {func_name}(" in target_file.read_text(encoding="utf-8"), (
            f"{nodeid}: {file_part} no longer defines {func_name} — the check was renamed or deleted and "
            "its exemption survived it"
        )
    # (4) every entry states its own reason, beside itself
    for list_name, (_, segment) in sets.items():
        block: list[str] = []
        silent_entries = 0
        for text_line in segment.splitlines():
            block.append(text_line)
            if text_line.rstrip().endswith('",'):
                if not any(block_line.lstrip().startswith("#") for block_line in block):
                    silent_entries += 1
                block = []
        assert silent_entries == 0, (
            f"{list_name}: {silent_entries} entry/entries carry NO comment saying why they are exempt — an "
            "entry with no stated reason inherits the label of whatever block it was pasted into"
        )
