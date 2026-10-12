"""The archiver moves bytes and never rewrites one - proven, not promised.

Every test here was written against a SABOTAGE first: the code was broken, the test was seen RED,
the code was restored, the test was seen GREEN. A test green before and after a change tests
nothing, and this module's single guarantee (the user's rule 1 - *"you must never reword what is
written in the plans"*) is exactly the kind that dies quietly while its name stays alive.

The byte-level cases are not imagined: a file with no final newline, two sections separated by
``---``, a line of nothing but spaces, an NFD accent, CRLF endings. Each one is a real way an equality
of bytes breaks while every visible character looks identical.
"""

from __future__ import annotations

import dataclasses
import unicodedata
from pathlib import Path

import pytest

from mnemosyne.production.plan_archive import (
    CLOSED_STATUSES,
    OPEN_STATUSES,
    VERBATIM_MARKER,
    ArcFile,
    ArchiveMismatch,
    archive_filename,
    filiation_problems,
    index_entries,
    plan_archive,
    slugify,
    split_sections,
    verify_readability,
    verify_roundtrip,
)
from mnemosyne.production.plan_format import (
    ARCS_DIRNAME,
    ROLE_ARC,
    ROLE_PLAN,
    ROLE_PORTE,
    STATUS_BY_GLYPH,
    STATUS_LABEL,
    read_plan,
    unreadable_reasons,
)
from mnemosyne.production.plan_registry import plan_files
from mnemosyne.runtime import plan_archiver_run

_REPO_ROOT = Path(__file__).resolve().parents[2]

_HEAD = "# PLAN — test\n\n> **Cap** : measure before building\n\n"
_OPEN = "## ARC Y — what is left \U00002B1C\n\n- **Y1** \U00002B1C to do\n"


def _archive(text: str, **kwargs):
    """Plan the move with fixed date/commit, so no test depends on the day it runs."""
    options = {"source": "plan/PLAN.md", "today": "2026-07-28", "commit": "abc1234"}
    options.update(kwargs)
    return plan_archive(text, **options)


def _proven(text: str, **kwargs):
    """Plan it, demand the round-trip, and demand the ADVERTISED range match the MOVED bytes.

    The second assertion exists because a sabotage survived without it: shifting every section's
    ``last_line`` one line down left the whole suite green, since no item ever sits on a ``## `` line.
    The range is not decoration - it is what the archive header claims about where the bytes came
    from, and a header that misstates its origin is exactly the rot this command exists to stop.
    """
    planning = _archive(text, **kwargs)
    verify_roundtrip(planning)
    for move in planning.moves:
        assert move.lines == len(move.body.splitlines()), move.title
    return planning


# --------------------------------------------------------------------------------------------
# 1. An arc that lies is never archived - the case that exists in this repo's own plan today.
# --------------------------------------------------------------------------------------------


def test_un_arc_qui_ment_est_refuse_et_ses_items_sont_nommes() -> None:
    """Title over items : refused, named, and NOT moved (the ARC A shape, verbatim in spirit)."""
    text = (
        _HEAD
        + "## ARC A — Ergonomics: measure before building \U00002705 *(2026-07-27)*\n"
        "\n"
        "- **A1** \U00002B1C Time the surfaces\n"
        "- **A2** \U00002B1C Measure the fixed cost\n"
        "- **A3** \U00002705 Deliver the verdict\n"
        "\n" + _OPEN
    )
    planning = _proven(text)

    assert planning.moves == ()
    assert [refusal.reason for refusal in planning.refusals] == ["arc_ment"]
    detail = planning.refusals[0].detail
    assert "A1" in detail and "A2" in detail
    # The one that IS done must not be accused: a catch rate without its false-kill rate is a wall.
    assert "A3" not in detail
    assert planning.remaining == text


def test_un_arc_dont_tous_les_items_sont_faits_ou_clos_part() -> None:
    """``fait`` and ``clos`` both authorise the move - ARC E carries a ```` item and is archivable."""
    text = (
        _HEAD + "## ARC E — The Guard \U00002705\n\n- **E1** \U00002705 measured\n- **E2-veto** \U000026D4 vetoed\n\n" + _OPEN
    )
    planning = _proven(text)

    assert [move.title for move in planning.moves] == ["ARC E — The Guard \U00002705"]
    assert planning.refusals == ()
    assert planning.moves[0].idents == ("E1", "E2-veto")


def test_un_titre_ambigu_est_refuse_sans_accuser_ses_items() -> None:
    """```` AND ```` in one title (the ARC C shape): the arc never claimed to be over."""
    text = _HEAD + "## ARC C — L'UI \U0001F504 *(C1 \U00002705 ; C2 hors de mes mains)*\n\n- **C1** \U00002705 fait\n\n" + _OPEN
    planning = _proven(text)

    assert planning.moves == ()
    assert [refusal.reason for refusal in planning.refusals] == ["titre_ambigu"]
    assert STATUS_LABEL["en_cours"] in planning.refusals[0].detail


def test_une_section_sans_glyphe_de_cloture_n_est_pas_candidate_mais_est_comptee() -> None:
    """Third outcome: neither moved nor refused - and published, so nothing is invisible."""
    text = _HEAD + "## Contexte en une ligne\n\ndu texte\n\n" + _OPEN
    planning = _proven(text)

    assert (planning.moves, planning.refusals) == ((), ())
    assert planning.sections == 2
    assert planning.not_candidates == 2


# --------------------------------------------------------------------------------------------
# 2. The byte-for-byte guarantee, one test per way an equality of bytes dies silently.
# --------------------------------------------------------------------------------------------


def _closed_plan(body: str) -> str:
    return _HEAD + "## ARC E — done \U00002705\n\n- **E1** \U00002705 done\n" + body + _OPEN


def test_roundtrip_fichier_sans_saut_de_ligne_final() -> None:
    """The archived section is the LAST thing in a file that does not end with a newline."""
    text = _HEAD + _OPEN + "\n## ARC E — done \U00002705\n\n- **E1** \U00002705 done"
    assert not text.endswith("\n")
    planning = _proven(text)

    assert len(planning.moves) == 1
    assert planning.moves[0].body == "## ARC E — done \U00002705\n\n- **E1** \U00002705 done"


def test_roundtrip_sections_separees_par_un_tiret_horizontal() -> None:
    """``---`` between two sections belongs to the one above it, and travels with it."""
    text = _closed_plan("\n---\n\n")
    planning = _proven(text)

    assert planning.moves[0].body.endswith("\n---\n\n")
    assert "---" not in planning.remaining


def test_roundtrip_ligne_de_seuls_espaces_et_espaces_de_fin() -> None:
    """Trailing whitespace is invisible on screen and fatal to an equality of bytes."""
    text = _closed_plan("   \n- **E2** \U00002705 fait   \n\t\n")
    planning = _proven(text)

    assert "   \n" in planning.moves[0].body
    assert "fait   \n" in planning.moves[0].body


def test_roundtrip_accent_en_nfd() -> None:
    """A plan written in NFD (``é`` = ``e`` + U+0301) comes back in NFD, not normalised."""
    decomposed = unicodedata.normalize("NFD", "réparé")
    text = _closed_plan(f"\nUn mot {decomposed} dans la prose.\n\n")
    assert decomposed not in unicodedata.normalize("NFC", text)
    planning = _proven(text)

    assert decomposed in planning.moves[0].body
    assert unicodedata.normalize("NFC", planning.moves[0].body) != planning.moves[0].body


def test_roundtrip_fins_de_ligne_crlf() -> None:
    """A plan with Windows endings keeps them - ``\\r\\n`` must not collapse to ``\\n``."""
    text = _closed_plan("\n").replace("\n", "\r\n")
    planning = _proven(text)

    assert "\r\n" in planning.moves[0].body
    assert "\n" not in planning.moves[0].body.replace("\r\n", "")


def test_roundtrip_deux_arcs_archives_dans_la_meme_passe() -> None:
    """Two moves at once: cutting from the end keeps every offset valid."""
    text = _HEAD + "## ARC E — done \U00002705\n\n- **E1** \U00002705 ok\n\n## ARC F — also done \U00002705\n\n- **F1** \U00002705 ok\n\n" + _OPEN
    planning = _proven(text)

    assert len(planning.moves) == 2
    assert planning.moves[0].body.startswith("## ARC E")
    assert planning.moves[1].body.startswith("## ARC F")


def test_la_verification_MORD_quand_un_seul_caractere_a_bouge() -> None:
    """The proof must be able to FAIL: one lost space and the command refuses, naming the offset."""
    planning = _proven(_closed_plan("\n"))
    # THE NEEDLE IS A WORD OF `_HEAD`'s CAP LINE, which survives into `remaining`. Rename that cap
    # and `.replace()` silently becomes a no-op: no sabotage is applied, nothing raises, and the one
    # test whose job is to prove the check BITES is left proving nothing. It is a matched pair --
    # measured, not supposed: this needle read "mesurer" until the cap was translated, and the
    # failure it produced was `DID NOT RAISE`, not a diff. Change the cap, change this word.
    saboted = dataclasses.replace(planning, remaining=planning.remaining.replace("measure", "measur", 1))

    with pytest.raises(ArchiveMismatch) as refus:
        verify_roundtrip(saboted)
    assert "divergence at character" in str(refus.value)


def test_la_verification_MORD_quand_l_archive_perd_sa_marque_de_verbatim() -> None:
    """A header that swallows the marker makes the body unrecoverable - refused, not written."""
    planning = _proven(_closed_plan("\n"))
    broken = dataclasses.replace(planning, commit=f"abc{VERBATIM_MARKER}")

    with pytest.raises(ArchiveMismatch):
        verify_roundtrip(broken)


def test_la_verification_MORD_quand_un_pointeur_n_est_pas_unique() -> None:
    """A pointer that appears twice is a marker nobody can splice back - refused."""
    planning = _proven(_closed_plan("\n"))
    doubled = dataclasses.replace(
        planning, remaining=planning.remaining + planning.moves[0].pointer + "\n"
    )

    with pytest.raises(ArchiveMismatch) as refus:
        verify_roundtrip(doubled)
    assert "2 times" in str(refus.value)


# --------------------------------------------------------------------------------------------
# 3. Non-destructive, and never a second source of state.
# --------------------------------------------------------------------------------------------


def test_une_archive_deja_presente_est_un_refus_jamais_un_ecrasement() -> None:
    """Invariant 2, at the planning level: the name is taken, so the arc stays in the plan."""
    text = _closed_plan("\n")
    name = archive_filename("2026-07-28", "ARC E — done \U00002705")
    planning = _proven(text, taken=frozenset({name}))

    assert planning.moves == ()
    assert [refusal.reason for refusal in planning.refusals] == ["archive_existe"]


def test_deux_arcs_de_meme_nom_de_fichier_le_second_est_refuse() -> None:
    """Same slug twice in one pass: the second would overwrite the first inside the same run."""
    text = (
        _HEAD
        + "## ARC E — done \U00002705 *(yesterday)*\n\n- **E1** \U00002705 ok\n\n"
        "## ARC E — done \U00002705 *(today)*\n\n- **E2** \U00002705 ok\n\n" + _OPEN
    )
    planning = _proven(text)

    assert len(planning.moves) == 1
    assert [refusal.reason for refusal in planning.refusals] == ["collision_de_nom"]


def test_le_pointeur_reste_de_la_PROSE_pour_le_lecteur_de_plans() -> None:
    """One line, the title verbatim, and NOT an item: no second place where a state is declared."""
    text = _closed_plan("\n")
    planning = _proven(text)
    before, after = read_plan(text), read_plan(planning.remaining)

    assert planning.moves[0].pointer.count("\n") == 0
    assert "ARC E — done \U00002705" in planning.moves[0].pointer
    assert planning.moves[0].link in planning.moves[0].pointer
    # The pointer adds no item, no refusal and no section to what the reader sees.
    assert len(after.items) == len(before.items) - 1  # only E1 left with the section
    assert after.problems == before.problems
    assert {item.section for item in after.items} == {"ARC Y — what is left \U00002B1C"}


def test_une_borne_incertaine_bloc_de_code_ouvert_est_refusee() -> None:
    """A ``## `` inside an unclosed fence is a false boundary - the cut would take the wrong bytes.

    BOTH halves of the class, in one fixture. The real arc closes no fence it opened; the sample
    heading inside the fence is not a section at all. An earlier version checked only the first and
    happily archived the second - the wrong bytes, under a title that is a code sample.
    """
    text = _HEAD + "## ARC E — done \U00002705\n\n- **E1** \U00002705 ok\n\n```markdown\n## ARC fake \U00002705\n\n" + _OPEN
    planning = _proven(text)

    assert planning.moves == ()
    assert [refusal.title for refusal in planning.refusals] == ["ARC E — done \U00002705", "ARC fake \U00002705"]
    assert {refusal.reason for refusal in planning.refusals} == {"borne_incertaine"}
    assert "INSIDE a code block" in planning.refusals[1].detail


def test_une_ligne_illisible_dans_l_arc_empeche_son_archivage() -> None:
    """An arc holding a line the reader refused cannot be certified done."""
    text = _HEAD + "## ARC E — done \U00002705\n\n- **E1** \U00002705 ok\n- **E2** \U0001F195 invented status\n\n" + _OPEN
    planning = _proven(text)

    assert planning.moves == ()
    assert [refusal.reason for refusal in planning.refusals] == ["ligne_illisible"]
    assert "statut_inconnu" in planning.refusals[0].detail


def test_verify_readability_MORD_si_le_plan_perd_son_dernier_item() -> None:
    """The pre-commit barrier's own rule, applied BEFORE the write instead of after it."""
    text = _HEAD + "## ARC E — done \U00002705\n\n- **E1** \U00002705 ok\n"
    planning = _proven(text)

    assert len(planning.moves) == 1
    with pytest.raises(ArchiveMismatch) as refus:
        verify_readability(planning)
    assert "no longer be readable" in str(refus.value)


# --------------------------------------------------------------------------------------------
# 4. The vocabulary is IMPORTED, never copied - and closure is fail-closed over it.
# --------------------------------------------------------------------------------------------


def test_le_vocabulaire_est_partitionne_et_un_statut_nouveau_serait_OUVERT() -> None:
    """Derived from ``STATUS_LABEL``, so a 7th status cannot land on the "done" side by omission.

    ``make plans`` hard-copied this same vocabulary, silently omitted ``clos`` and ``en_pause``, and
    printed a per-status detail that summed to four on a six-item plan. One copy is one drift.
    """
    assert CLOSED_STATUSES | OPEN_STATUSES == set(STATUS_LABEL)
    assert not (CLOSED_STATUSES & OPEN_STATUSES)
    assert CLOSED_STATUSES < set(STATUS_LABEL)
    assert set(STATUS_BY_GLYPH.values()) == set(STATUS_LABEL)


def test_un_selecteur_de_variation_ne_cache_pas_le_glyphe_du_titre() -> None:
    """```` (glyph + U+FE0F) is the same status as ```` - writers emit it inconsistently.

 A behaviour pin, and honest about WHY it holds: detection is character-wise membership, so the
 trailing selector is never looked at. Cleaning the title first was tried and removed - deleting
 the call left every test green, i.e. it guaranteed nothing. Rewrite detection as a substring
 search over the whole title and this test is what will go red.
 """
    text = _HEAD + "## ARC E — done \U00002705\U0000FE0F\n\n- **E1** \U00002705 ok\n\n" + _OPEN
    planning = _proven(text)

    assert len(planning.moves) == 1


def test_le_slug_s_arrete_au_glyphe_et_retombe_sur_le_titre_entier_sinon() -> None:
    """The name stops where the writers stop naming - unless that would leave nothing at all."""
    assert slugify("ARC F — Les dettes nommées \U00002705 *(2026-07-28, commit `9e15d1f`)*") == (
        "arc-f-les-dettes-nommees"
    )
    # Glyph FIRST (`## ARC G — EN PAUSE…`): cutting there leaves nothing, so the title stands.
    assert slugify("\U000023F8\U0000FE0F ARC G — EN PAUSE, décidé par user") == "arc-g-en-pause-decide-par-user"
    assert slugify("\U00002705") == "section"
    assert archive_filename("2026-07-28", "ARC H — Rendre la recherche utilisable \U00002705") == (
        "plan-2026-07-28-arc-h-rendre-la-recherche-utilisable.md"
    )


# --------------------------------------------------------------------------------------------
# 5. Agreement with the reader next door, on the REAL plan - and the end-to-end write.
# --------------------------------------------------------------------------------------------


#: The floors below which this test REFUSES to run - a guard against becoming mute, never a
#: description of the plan. Measured on BOTH sides of the D166 conversion, which is the whole point:
#: before ``make plan-convertir``, ``docs/`` holds ONE plan file (1443 lines) carrying 12 sections
#: and 43 items; after it, THIRTEEN (a 28-line door plus 12 arcs) carrying the SAME 12 sections and
#: the SAME 43 items. Only a floor that holds on both sides may be written here, and the measurements
#: are what pick each number:
#:
#: * ONE file, because a plan that is a single file is the FLOOR of the format and not a degraded
#:   case (D166) - the "before" side measures exactly 1, so no higher number could be honest;
#: * SIX sections rather than the 12 measured on both sides, because 12 would be an equality in
#:   disguise: ``make plan-archiver`` took this very plan from 16 sections to 12 in ONE commit
#:   (``cf8684b``), so a floor at 12 goes red on the next legitimate archiving. Six still refuses a
#:   discovery that has silently collapsed to a single file, which is what this guard is FOR - cut
#:   the arc walk after conversion and the corpus falls to the section-less door, i.e. zero;
#: * TWELVE items - one per section - because the attribution loop below is the whole point of this
#:   test, and a corpus carrying no items runs it zero times while every other assertion stays green.
_MIN_PLAN_FILES = 1
_MIN_SECTIONS = 6
_MIN_ITEMS = 12


def _plan_bytes(path: Path) -> str:
    """The file's BYTES - ``newline=""`` like the command, so ``\\r\\n`` is not translated away."""
    with path.open(encoding="utf-8", newline="") as handle:
        return handle.read()


def test_les_bornes_de_section_sont_celles_du_lecteur_de_plans() -> None:
    """Every item lands in the section whose line span holds it - on EVERY real plan file of ``docs/``.

    The archiver cuts on section boundaries while the reader attributes items to sections; if the
    two ever disagreed, an arc would be certified on items that are not inside it. Run against real
    files rather than a fixture, because a fixture cannot carry the shapes this plan invented.

    **It is a property of a plan FILE, and that is the repair.** It used to be a property of
    the plan's door file read as one monolith - pinned, therefore, on the very shape D166 exists
    to end: the day ``make plan-convertir`` ran, the door kept 28 lines and no ``## `` at all, the 12
    sections moved into their own arc files, and this test went red on a repo that had done exactly
    what it was built to do. A harness that only holds until the mechanism it guards is USED proves
    nothing about the world on the other side. It now walks whatever ``docs/`` actually holds -
    one file or thirteen - and the floors above are what stop "walks whatever it holds" from
    degrading into "walks nothing".
    """
    files = plan_files(_REPO_ROOT / "docs")
    corpus = []
    for path in files:
        text = _plan_bytes(path)
        corpus.append((path, text, split_sections(text), read_plan(text)))
    sections_total = sum(len(sections) for _, _, sections, _ in corpus)
    items_total = sum(len(reading.items) for _, _, _, reading in corpus)

    # The vacuity guards come FIRST, before the verdict they protect. A red pass throws away
    # everything it measured, so a floor asserted after the loops below would only ever run in the
    # case where it has nothing left to save.
    assert len(files) >= _MIN_PLAN_FILES, f"no plan file under docs/: {files}"
    assert sections_total >= _MIN_SECTIONS, f"{sections_total} sections over {len(files)} file(s)"
    assert items_total >= _MIN_ITEMS, f"{items_total} items over {len(files)} file(s)"

    # And the real material RE-ASSEMBLED, because after the conversion nothing else carries two
    # ADJACENT sections: each arc holds exactly one and the door holds none, so the abutment half of
    # the property - the half that catches an off-by-one between two sections - would be walked zero
    # times and stay green forever. Found by sabotage: shifting `last_line` by one line survives this
    # test on a converted repo and kills it on an unconverted one. The bytes are the same real bytes;
    # only the boundaries between them are put back within reach.
    joined = "".join(section.body for _, _, sections, _ in corpus for section in sections)
    corpus.append((Path("<reassembled sections>"), joined, split_sections(joined), read_plan(joined)))
    assert max(len(sections) for _, _, sections, _ in corpus) >= 2, "no section ADJACENT to another"

    for path, text, sections, reading in corpus:
        # The spans tile the file exactly: no gap (bytes nobody would archive) and no overlap (bytes
        # two arcs would both claim). Asserted here because the item-attribution check below cannot
        # see it - an off-by-one at the boundary only ever touches a `## ` line, where no item lives.
        for above, below in zip(sections, sections[1:]):
            assert above.last_line == below.first_line - 1, path
            assert above.end == below.start, path
        if sections:
            # A door whose arcs hold every section carries none itself, and that is not a defect -
            # it is the converted shape. What it may never do is carry an item CLAIMED BY a section
            # (``item.section != ""``) outside that section's own span, and the loop below is what
            # refuses that, here as everywhere else.
            assert sections[-1].last_line == len(text.splitlines()), path
            assert sections[-1].end == len(text), path
        for item in reading.items:
            holding = [s for s in sections if s.first_line <= item.line <= s.last_line]
            if item.section == "":
                # An item read BEFORE the first ``## `` heading of the file - legitimate, the same
                # "arc with no sections of its own" shape named above, just reached from an item
                # that sits ABOVE a later section rather than a file with none at all (found on
                # another project's real plan: a preamble of un-sectioned items, THEN one ``## `` section).
                assert holding == [], (path, item)
            else:
                assert len(holding) == 1, (path, item)
                assert holding[0].title == item.section, (path, item)


def test_le_disque_rend_exactement_ce_qui_a_ete_prouve(tmp_path: Path) -> None:
    """End to end, through real files: apply, read both back, reconstruct, compare byte for byte."""
    text = _closed_plan("\nUne ligne d'espaces suit.\n   \n---\n\n")
    plan = tmp_path / "PLAN.md"
    with plan.open("w", encoding="utf-8", newline="") as handle:
        handle.write(text)

    assert plan_archiver_run.main([str(plan), "--today", "2026-07-28"]) == 0
    assert not (tmp_path / "archive").exists(), "the dry run must write NOTHING"

    assert plan_archiver_run.main([str(plan), "--today", "2026-07-28", "--apply"]) == 0
    archives = sorted((tmp_path / "archive").glob("*.md"))
    assert len(archives) == 1

    with archives[0].open(encoding="utf-8", newline="") as handle:
        archived = handle.read()
    with plan.open(encoding="utf-8", newline="") as handle:
        left = handle.read()
    body = archived.split(VERBATIM_MARKER, 1)[1]
    pointer = next(line for line in left.splitlines() if "Archived on" in line)
    assert left.replace(pointer + "\n", body, 1) == text
    assert "lines 5 to 12" in archived and "PLAN.md" in archived


def test_le_disque_a_le_DERNIER_mot_sur_l_ecrasement(tmp_path: Path) -> None:
    """``"x"`` mode, tested where it is the ONLY thing standing - the planner having said yes.

    Written after a sabotage survived: turning ``"x"`` into ``"w"`` broke nothing, because the pure
    planner refuses a taken name long before the write and no test ever reached the mode. A barrier
    nothing calls is not a barrier. Here the name is taken AFTER planning, exactly the race the mode
    exists for - and the write order is proven with it: archives first, so a refusal leaves the plan
    untouched and the content in one piece rather than in a hole (invariant 2).
    """
    text = _closed_plan("\n")
    plan = tmp_path / "PLAN.md"
    with plan.open("w", encoding="utf-8", newline="") as handle:
        handle.write(text)
    planning = _proven(text)
    archive_root = tmp_path / "archive"
    archive_root.mkdir()
    squatter = archive_root / planning.moves[0].filename
    squatter.write_text("already there, written by someone else", encoding="utf-8")
    with pytest.raises(FileExistsError):
        plan_archiver_run.apply_planning(planning, plan_path=plan, archive_root=archive_root)

    assert squatter.read_text(encoding="utf-8") == "already there, written by someone else"
    with plan.open(encoding="utf-8", newline="") as handle:
        assert handle.read() == text


# --------------------------------------------------------------------------------------------
# 6. A plan is a FOLDER (D166): the same archiver, three roles, one rule - and no second copy.
# --------------------------------------------------------------------------------------------


def _folder_plan(tmp_path: Path) -> Path:
    """A plan in its D166 shape on disk - a door that names its cap and indexes one arc beside it.

    Returns the ARC, because that is the file every case here starts from. Written through
    ``newline=""`` like the command itself: universal newlines would collapse ``\\r\\n`` and the
    byte-for-byte assertions would be testing Python's translation, not the archiver.
    """
    with (tmp_path / "PLAN.md").open("w", encoding="utf-8", newline="") as handle:
        handle.write(_HEAD + "## The arcs\n\nArc E lives in `plan/arc-e.md`.\n")
    arcs = tmp_path / ARCS_DIRNAME
    arcs.mkdir()
    arc = arcs / "arc-e.md"
    with arc.open("w", encoding="utf-8", newline="") as handle:
        handle.write("## ARC E — done \U00002705\n\n- **E1** \U00002705 ok\n\n" + _OPEN)
    return arc


def test_le_role_se_deduit_du_chemin_jamais_d_un_drapeau(tmp_path: Path) -> None:
    """Which of D166's three roles a file plays is READ OFF its path - the user has nothing to remember.

    A flag would have to be typed right every time on a command whose whole point is that it runs
    unattended; and a flag typed wrong is silent - it makes the archiver judge an arc by the door's
    rule, which is exactly the refusal this arc removes.
    """
    arc = _folder_plan(tmp_path)
    door = tmp_path / "PLAN.md"

    assert plan_archiver_run.plan_site(arc).role == ROLE_ARC
    assert plan_archiver_run.plan_site(door).role == ROLE_PORTE

    # A plan that is ONE file is not a degraded case, it is the floor: judged exactly as before.
    seul = tmp_path / "ailleurs"
    seul.mkdir()
    (seul / "PLAN.md").write_text(_HEAD + _OPEN, encoding="utf-8")
    assert plan_archiver_run.plan_site(seul / "PLAN.md").role == ROLE_PLAN

    # An arc whose door is missing is STILL an arc. The missing door is a different defect, named
    # by `make plans` and by the pre-commit hook; judging it as a whole plan would refuse it for
    # lacking a cap it must not carry.
    orphelin = tmp_path / "orphelin" / "plan"
    orphelin.mkdir(parents=True)
    (orphelin / "arc-z.md").write_text(_OPEN, encoding="utf-8")
    assert plan_archiver_run.plan_site(orphelin / "arc-z.md").role == ROLE_ARC


def test_l_archive_d_un_arc_ne_tombe_JAMAIS_dans_le_dossier_plan(tmp_path: Path) -> None:
    """The memory goes beside the PLAN, never inside ``plan/`` - where it would come back as an arc.

    Measured consequence of the naive placement (``<fichier>/../archive``): ``plan/archive/plan-….md``
    is a ``.md`` under ``plan/``, so the folder reader (``rglob("*.md")``) reads it as an ARC on the
    next pass. Every line the archiver took OUT of the plan would return as items, with an
    ``arc_hors_index`` refusal on top - which the pre-commit barrier turns into a blocked commit.
    """
    arc = _folder_plan(tmp_path)
    site = plan_archiver_run.plan_site(arc)

    assert site.archive_root == (tmp_path / "archive").resolve()
    assert site.link_dir == "../archive"
    assert plan_archiver_run.plan_site(tmp_path / "PLAN.md").link_dir == "archive"


def test_un_ARC_s_archive_sans_qu_on_lui_reclame_un_cap(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """End to end on the D166 shape: a healthy arc has NO cap, and that must not refuse the move.

    The defect this closes, verbatim from the code it replaces: ``verify_readability`` demanded a cap
    AND an item of every text it saw, so archiving out of an arc left "un texte sans cap" and the
    command refused a perfectly sane file. The byte-for-byte guarantee is re-proven here through the
    new path rather than assumed to survive it.
    """
    arc = _folder_plan(tmp_path)
    with arc.open(encoding="utf-8", newline="") as handle:
        before = handle.read()

    assert plan_archiver_run.main([str(arc), "--today", "2026-07-28", "--apply"]) == 0

    assert not (tmp_path / "plan" / "archive").exists(), "an archive under plan/ becomes an arc again"
    archives = sorted((tmp_path / "archive").glob("*.md"))
    assert len(archives) == 1
    with archives[0].open(encoding="utf-8", newline="") as handle:
        body = handle.read().split(VERBATIM_MARKER, 1)[1]
    with arc.open(encoding="utf-8", newline="") as handle:
        left = handle.read()
    pointer = next(line for line in left.splitlines() if "Archived on" in line)
    assert "../archive/" in pointer
    assert left.replace(pointer + "\n", body, 1) == before

    # The percentage's denominator is the FILE named at the top of the report - one arc among
    # several - never "the plan". Caught by running the command for real on a folder-shaped plan,
    # where it announced "62,5 % du plan" about five lines of one arc.
    assert "% of the plan" not in capsys.readouterr().out


def test_une_PORTE_qui_n_a_plus_d_items_reste_lisible(tmp_path: Path) -> None:
    """The symmetric half: a door's items live in its arcs, so losing the last one is not a defect.

    Same single rule, other side. Judged by the mono-file rule, a door whose last closed section
    leaves would report "no readable item" and the move would be refused - on a plan whose arcs are
    full of items sitting one directory away.
    """
    _folder_plan(tmp_path)
    door = tmp_path / "PLAN.md"
    with door.open("w", encoding="utf-8", newline="") as handle:
        handle.write(_HEAD + "Arc E lives in `plan/arc-e.md`.\n\n## ARC E — done \U00002705\n\n- **E1** \U00002705 ok\n")

    assert plan_archiver_run.plan_site(door).role == ROLE_PORTE
    assert plan_archiver_run.main([str(door), "--today", "2026-07-28", "--apply"]) == 0
    with door.open(encoding="utf-8", newline="") as handle:
        assert read_plan(handle.read()).items == ()


def test_la_regle_de_role_MORD_encore_dans_chacun_de_ses_trois_roles() -> None:
    """Widened is not disabled: each role still REFUSES what it must. A rule that never bites proves
    nothing, so the three are exercised on the text that breaks each one.
    """
    # ARC: nothing left that is an item at all.
    orphelin = _proven("## ARC E — done \U00002705\n\n- **E1** \U00002705 ok\n")
    with pytest.raises(ArchiveMismatch) as refus:
        verify_readability(orphelin, role=ROLE_ARC)
    assert "no longer be readable" in str(refus.value)

    # PORTE: the cap itself sat inside the archived section.
    sans_cap = _proven("# PLAN — test\n\n## ARC E — done \U00002705\n\n> **Cap** : measure\n\n- **E1** \U00002705 ok\n")
    with pytest.raises(ArchiveMismatch):
        verify_readability(sans_cap, role=ROLE_PORTE)

    # PLAN (one file): unchanged - both are required, and the default role is still this one.
    with pytest.raises(ArchiveMismatch):
        verify_readability(orphelin)


def test_le_refus_de_lisibilite_CITE_la_phrase_du_lecteur_jamais_une_copie() -> None:
    """The sentence the user reads comes FROM the reader - a fourth hand-written copy is what this kills.

    The rule "what makes a plan readable" had four homes: the registry, the pre-commit hook, and
    here, where ``verify_readability`` re-typed its own two-branch version. This pins the delegation
    rather than the wording: re-type the sentence and the two drift apart the day the reader's grows
    a detail - which it already did (the item sentence now names both notations).
    """
    planning = _proven(_HEAD + "## ARC E — done \U00002705\n\n- **E1** \U00002705 ok\n")
    attendu = unreadable_reasons(read_plan(planning.remaining), role=ROLE_PLAN)

    with pytest.raises(ArchiveMismatch) as refus:
        verify_readability(planning, role=ROLE_PLAN)
    assert attendu
    assert all(phrase in str(refus.value) for phrase in attendu)


def test_un_DOSSIER_nomme_la_porte_au_lieu_de_dire_qu_il_n_y_a_pas_de_plan(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A plan IS a folder now, so a folder is the most natural thing to hand this command.

    Answering "No plan at `…`" when the door sits right inside it is a refusal that lies about the
    world and names no gesture - the shape this repo has already paid for elsewhere.
    """
    _folder_plan(tmp_path)

    assert plan_archiver_run.main([str(tmp_path), "--today", "2026-07-28"]) == 1
    printed = capsys.readouterr().out
    # The needle must be the wording `missing_plan_message` emits TODAY. It read "Aucun plan"
    # until production was translated, and a `not in` whose needle no longer exists anywhere is a
    # control that has silently stopped being taken: green, and blind to the defect it was written for.
    assert "No plan at" not in printed
    assert "PLAN.md" in printed and f"{ARCS_DIRNAME}/" in printed


# --------------------------------------------------------------------------------------------
# 7. The UNIT is the ARC when the plan is a folder - the capacity D166 killed in silence.
# --------------------------------------------------------------------------------------------
#
# Measured, not supposed: the day ``make plan-convertir`` ran on this repo, the plan's door file
# went from 12 ``## `` sections to ZERO (a 28-line door carrying an index) and each of the 12 arcs to
# exactly ONE - so archiving "the section" of an arc would have emptied its file, and ``make
# plan-archiver`` answered "nothing to archive" about a plan with twelve arcs in it. Every test below
# is on the folder shape; every test ABOVE stays on the mono-file shape, which is the floor and is
# untouched.

_ARC_E = "## ARC E — done \U00002705\n\n- **E1** \U00002705 ok\n- **E2-veto** \U000026D4 vetoed\n"


def _door(tmp_path: Path, arcs: dict[str, str], *, head: str = _HEAD, index: str = "") -> Path:
    """A door with a REAL index - the shape ``make plan-convertir`` writes - and its arcs beside it.

    Distinct from ``_folder_plan`` above, and the difference is the point: that fixture MENTIONS its
    arc in a sentence, which satisfies the generous completeness check and is not a declaration. The
    archiver replaces a DECLARATION, so a fixture that carries none would never exercise the move -
    and would have gone green on an archiver that could not find a single entry.
    """
    entries = index or "".join(
        # The title is NOT the file name: the fallback in `index_problems` vouches for an arc whose
        # bare name appears anywhere in the door, so a door indexing `arc-y.md` under the title
        # "arc-y.md" stays "cited" after its entry is deleted - and the arc_hors_index half of the
        # barrier would have been tested against a fixture that cannot produce it.
        f"- `{ARCS_DIRNAME}/{name}` — l'arc {name.removesuffix('.md')}\n" for name in sorted(arcs)
    )
    tmp_path.mkdir(parents=True, exist_ok=True)
    with (tmp_path / "PLAN.md").open("w", encoding="utf-8", newline="") as handle:
        handle.write(head + entries)
    folder = tmp_path / ARCS_DIRNAME
    folder.mkdir(exist_ok=True)
    for name, body in arcs.items():
        path = folder / name
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="") as handle:
            handle.write(body)
    return tmp_path / "PLAN.md"


def _plan_folder(door: Path, **kwargs):
    """Plan a run over a door and the arcs really sitting beside it - the runtime's own discovery."""
    arcs, indexed = plan_archiver_run.read_arcs(door)
    return _archive(_plan_bytes(door), arcs=arcs, indexed=indexed, **kwargs)


def test_la_decision_sur_un_ARC_reste_PURE_le_disque_est_passe_en_argument() -> None:
    """The arcs are handed IN, like ``taken`` - no filesystem inside the decision.

    And the reference the reconstruction is measured against is pinned here: this file, with the
    arc's own bytes put back where its index entry sits. Built from what was READ, so a corrupted
    body cannot cancel itself out on both sides of the equality.
    """
    entry = f"- `{ARCS_DIRNAME}/arc-e.md` — l'arc E\n"
    door = _HEAD + entry
    planning = _archive(
        door, arcs=(ArcFile(f"{ARCS_DIRNAME}/arc-e.md", _ARC_E),), indexed=("arc-e.md",)
    )
    verify_roundtrip(planning)

    assert [move.origin for move in planning.moves] == [f"{ARCS_DIRNAME}/arc-e.md"]
    assert planning.moves[0].body == _ARC_E and planning.moves[0].entry == entry
    assert planning.reference == _HEAD + _ARC_E
    assert planning.remaining == _HEAD + planning.moves[0].pointer + "\n"


def test_un_ARC_CLOS_part_EN_ENTIER_et_la_porte_garde_son_pointeur(tmp_path: Path) -> None:
    """End to end through real files: the arc's bytes are the archive's body, exactly.

    The reconstruction is redone HERE, by hand, out of the two files on disk - never by calling the
    command's own verifier. A proof one can print is not a proof: the assertion below would fail if
    ``verify_roundtrip`` were deleted outright, which is the only way to know it is doing anything.
    """
    door = _door(tmp_path, {"arc-e.md": _ARC_E, "arc-y.md": _OPEN})
    before_door, before_arc = _plan_bytes(door), _plan_bytes(tmp_path / ARCS_DIRNAME / "arc-e.md")

    assert plan_archiver_run.main([str(door), "--today", "2026-07-28"]) == 0
    assert not (tmp_path / "archive").exists(), "the dry run must write NOTHING"
    assert plan_archiver_run.main([str(door), "--today", "2026-07-28", "--apply"]) == 0

    archives = sorted((tmp_path / "archive").glob("*.md"))
    assert [path.name for path in archives] == ["plan-2026-07-28-arc-e.md"]
    body = _plan_bytes(archives[0]).split(VERBATIM_MARKER, 1)[1]
    assert body == before_arc, "the arc's bytes must travel exactly as they are"
    assert not (tmp_path / ARCS_DIRNAME / "arc-e.md").exists(), "the arc file must be gone"
    assert _plan_bytes(tmp_path / ARCS_DIRNAME / "arc-y.md") == _OPEN, "the neighbour does not move"

    left = _plan_bytes(door)
    pointer = next(line for line in left.splitlines() if "Archived on" in line)
    entry = next(line for line in before_door.splitlines() if "arc-e.md" in line)
    assert left.replace(pointer, entry, 1) == before_door, "the door loses only its own index entry"


def test_un_ARC_qui_MENT_est_refuse_et_l_arc_ET_ses_items_sont_nommes(tmp_path: Path) -> None:
    """Title over an item , one directory away: refused, and the FILE is named with the items.

 Naming the arc is not decoration once a plan spans thirteen files: "ligne 6" was a location when
 a plan was one file and is a riddle now, since every arc has a line 6.
 """
    door = _door(tmp_path, {"arc-e.md": "## ARC E — done \U00002705\n\n- **E1** \U00002705 ok\n- **E9** \U00002B1C not done\n"})
    planning = _plan_folder(door)
    verify_roundtrip(planning)

    assert planning.moves == ()
    assert [refusal.reason for refusal in planning.refusals] == ["arc_ment"]
    refusal = planning.refusals[0]
    assert refusal.source == f"{ARCS_DIRNAME}/arc-e.md"
    assert f"{ARCS_DIRNAME}/arc-e.md" in refusal.where
    assert "E9" in refusal.detail and "E1" not in refusal.detail
    assert planning.remaining == planning.original


def test_la_porte_peut_opposer_son_VETO_et_ne_peut_JAMAIS_autoriser(tmp_path: Path) -> None:
    """The symmetric hole a wider unit digs, closed in both directions and measured in both.

    The door carries a COPY of each arc's title in its index entry, and a copy rots - this repo's own
    measure. So the rule is deliberately asymmetric: the door may CONTRADICT (the arc says done, the
    index still says to-do -> two declarations of one state, and this module never arbitrates), and it
    may never AUTHORISE (only the arc's own ``## `` title makes it a candidate at all). Without the
    second half, a stale index entry alone could archive a live arc.
    """
    veto = _door(tmp_path / "veto", {"arc-e.md": _ARC_E})
    (tmp_path / "veto" / "PLAN.md").write_text(
        _HEAD + f"- `{ARCS_DIRNAME}/arc-e.md` — ARC E — done \U00002B1C\n", encoding="utf-8"
    )
    refused = _plan_folder(veto)
    assert refused.moves == ()
    assert [r.reason for r in refused.refusals] == ["titre_ambigu"]
    assert STATUS_LABEL["a_faire"] in refused.refusals[0].detail

    # And the other way: a door shouting over an arc that declares nothing archives NOTHING.
    muet = _door(tmp_path / "muet", {"arc-e.md": "## ARC E — no glyph\n\n- **E1** \U00002705 ok\n"})
    (tmp_path / "muet" / "PLAN.md").write_text(
        _HEAD + f"- `{ARCS_DIRNAME}/arc-e.md` — ARC E — done \U00002705\n", encoding="utf-8"
    )
    silent = _plan_folder(muet)
    assert (silent.moves, silent.refusals) == ((), ())
    assert silent.not_candidates == 1, "out of the running, and COUNTED - never invisible"


def test_une_entree_d_index_qui_n_est_pas_unique_est_un_refus(tmp_path: Path) -> None:
    """Zero entry, two entries, or one line whose text repeats: the arc stays. Three, one reason.

    Neither half implies the other. Zero means the pointer would replace nothing and the arc's memory
    would leave no trace in the door at all; two means the second becomes an ``index_sans_fichier``
    the moment the file goes; a repeated LINE makes "put the arc back where its entry was" ambiguous,
    which is the very reconstruction this command rests on.
    """
    absent = _door(
        tmp_path / "absent",
        {"arc-e.md": _ARC_E},
        index=f"L'arc E vit dans `{ARCS_DIRNAME}/arc-e.md`, en prose.\n",
    )
    planning = _plan_folder(absent)
    assert [r.reason for r in planning.refusals] == ["index_incertain"]
    assert "0 index entr(y/ies)" in planning.refusals[0].detail

    entry = f"- `{ARCS_DIRNAME}/arc-e.md` — ARC E\n"
    double = _door(tmp_path / "double", {"arc-e.md": _ARC_E}, index=entry + entry)
    planning = _plan_folder(double)
    assert [r.reason for r in planning.refusals] == ["index_incertain"]
    assert "2 index entr(y/ies)" in planning.refusals[0].detail
    assert planning.moves == ()

    # ONE declaration, and a line of identical TEXT somewhere it is not one - a fenced example. The
    # count of declarations says "fine"; the reconstruction puts the arc back by SEARCHING for that
    # text, and would put it in the example. Without this half the run does not write (the round-trip
    # catches it) but it refuses with "divergence at character 213" instead of a gesture - a wall.
    echo = _door(
        tmp_path / "echo",
        {"arc-e.md": _ARC_E},
        index=f"```markdown\n{entry}```\n{entry}",
    )
    planning = _plan_folder(echo)
    assert [r.reason for r in planning.refusals] == ["index_incertain"]
    assert "1 index entr(y/ies)" in planning.refusals[0].detail
    assert "2 times" in planning.refusals[0].detail
    assert planning.moves == ()


def test_la_reference_ne_se_DERIVE_pas_du_corps_qu_elle_verifie(tmp_path: Path) -> None:
    """A body corrupted between the read and the write must not cancel itself out on both sides.

    The reference is "this file, with the arc's bytes put back where its index entry was" - and the
    bytes it puts back come from the DISK, never from ``move.body``. Take them from ``move.body`` and
    the equality compares a corruption to itself: the whole suite stays green while a truncated arc
    goes to the archive. Measured - that mutation SURVIVED every other test here.
    """
    door = _door(tmp_path, {"arc-e.md": _ARC_E})
    planning = _plan_folder(door)
    verify_roundtrip(planning)

    tronque = dataclasses.replace(planning.moves[0], body=planning.moves[0].body[:-5])
    with pytest.raises(ArchiveMismatch) as refus:
        verify_roundtrip(dataclasses.replace(planning, moves=(tronque,)))
    assert "the reconstruction does not give the original plan back" in str(refus.value)
    assert "different lengths" in str(refus.value), "and it LOCATES the loss"


def test_un_glyphe_de_cloture_DANS_un_bloc_de_code_ne_ferme_pas_l_arc(tmp_path: Path) -> None:
    """A ``## … `` shown as an EXAMPLE inside a fence is a code sample, not a closure.

 Same guard as for a section, on the wider unit: without it, a page of the plan showing what a
 closed arc looks like would archive itself.
 """
    door = _door(
        tmp_path,
        {"arc-e.md": "## ARC E — in progress\n\n- **E1** \U00002705 ok\n\n```markdown\n## ARC fake \U00002705\n"},
    )
    planning = _plan_folder(door)

    assert planning.moves == ()
    assert [refusal.reason for refusal in planning.refusals] == ["borne_incertaine"]
    assert "```" in planning.refusals[0].detail
    assert planning.refusals[0].source == f"{ARCS_DIRNAME}/arc-e.md"


def test_une_archive_du_meme_nom_refuse_l_arc_sans_l_ecraser(tmp_path: Path) -> None:
    """Invariant 2 on the wider unit - and it is the arc's FILE NAME that names the archive."""
    door = _door(tmp_path, {"arc-e.md": _ARC_E})
    (tmp_path / "archive").mkdir()
    (tmp_path / "archive" / "plan-2026-07-28-arc-e.md").write_text("already there", encoding="utf-8")

    assert plan_archiver_run.main([str(door), "--today", "2026-07-28", "--apply"]) == 0
    assert (tmp_path / "archive" / "plan-2026-07-28-arc-e.md").read_text(encoding="utf-8") == "already there"
    assert (tmp_path / ARCS_DIRNAME / "arc-e.md").exists(), "refused = not moved"


def test_une_PORTE_archive_AUSSI_ses_propres_sections_dans_la_meme_passe(tmp_path: Path) -> None:
    """Widened is not replaced: a door that still carries a closed ``## `` section archives it too.

    D166 permits a half-converted plan and the mono-file plan IS the floor, so making the arc the
    ONLY unit would have removed a capacity that ships today (a door archiving its own section) to
    add one. Both units, one pass, one reconstruction.
    """
    door = _door(tmp_path, {"arc-e.md": _ARC_E, "arc-y.md": _OPEN})
    with door.open("a", encoding="utf-8", newline="") as handle:
        handle.write("\n## ARC F — also done \U00002705\n\n- **F1** \U00002705 ok\n")

    planning = _plan_folder(door)
    verify_roundtrip(planning)
    assert sorted(move.title for move in planning.moves) == [
        "ARC E — done \U00002705",
        "ARC F — also done \U00002705",
    ]
    assert [bool(move.origin) for move in planning.moves] == [False, True]
    assert planning.units == 1 + 2  # the door's own section, plus its two arcs
    # The percentage's numerator is what leaves THIS file. The arc's lines were never in the door:
    # printed as one ratio it read "385,7 % du fichier", found on the first real run.
    assert planning.moved_from_file == 3, "3 section lines really do leave the door"
    assert planning.moved_lines == 3 + 4, "and 4 more leave the plan, from the arc"


def test_seule_une_PORTE_archive_des_arcs_jamais_un_voisin_qui_les_cite(tmp_path: Path) -> None:
    """Widening the unit must not widen WHO may use it: only a door speaks for ``plan/``.

    The charge is a file that is not the door and sits beside it - a note, a spec, another plan -
    which happens to cite an arc. Drop the role guard and that file is handed the door's arcs: it
    would archive them and lose its own citing line, i.e. rewrite a file that is not a plan door.
    Found by sabotage: removing the guard left the whole suite green until this was written, because
    every other fixture hands in the door itself.
    """
    _door(tmp_path, {"arc-e.md": _ARC_E})
    voisin = tmp_path / "autre.md"
    citation = _HEAD + f"- `{ARCS_DIRNAME}/arc-e.md` — I CITE arc E, I do not carry it\n" + _OPEN
    with voisin.open("w", encoding="utf-8", newline="") as handle:
        handle.write(citation)

    assert plan_archiver_run.plan_site(voisin).role == ROLE_PLAN
    assert plan_archiver_run.main([str(voisin), "--today", "2026-07-28", "--apply"]) == 0

    assert _plan_bytes(voisin) == citation, "a neighbour that cites an arc is not rewritten"
    assert (tmp_path / ARCS_DIRNAME / "arc-e.md").exists(), "and the arc stays with its door"
    assert not (tmp_path / "archive").exists()


def test_un_sous_plan_reste_indexe_et_n_est_JAMAIS_archive(tmp_path: Path) -> None:
    """A door under ``plan/`` is a PLAN, not an arc - it has its own cap and its own identity scope.

    ``read_arcs`` asks ``plan_entries`` rather than globbing, which is what keeps this true without a
    rule of its own; the assertion pins that the answer is USED, on both sides.
    """
    nested = f"{_HEAD}- `{ARCS_DIRNAME}/interne.md` — interne\n"
    door = _door(tmp_path, {"arc-e.md": _ARC_E, "sous/PLAN.md": nested, "sous/plan/interne.md": _OPEN})
    arcs, indexed = plan_archiver_run.read_arcs(door)

    assert [arc.member for arc in arcs] == [f"{ARCS_DIRNAME}/arc-e.md"]
    assert "sous/PLAN.md" in indexed, "a sub-plan must stay among what the index has to name"


def test_les_octets_d_un_arc_ne_sont_JAMAIS_reecrits(tmp_path: Path) -> None:
    """CRLF, NFD accent, trailing spaces, no final newline - the four ways bytes die invisibly."""
    decomposed = unicodedata.normalize("NFD", "réparé")
    body = f"## ARC E — done \U00002705\r\n\r\n- **E1** \U00002705 {decomposed}   \r\n   \r\n- **E2** \U00002705 end"
    door = _door(tmp_path, {"arc-e.md": body})

    assert plan_archiver_run.main([str(door), "--today", "2026-07-28", "--apply"]) == 0
    archived = _plan_bytes(next((tmp_path / "archive").glob("*.md")))
    assert archived.split(VERBATIM_MARKER, 1)[1] == body
    assert not archived.endswith("\n") and decomposed in archived


def test_la_reconstruction_MORD_si_le_pointeur_remplace_la_MAUVAISE_ligne(tmp_path: Path) -> None:
    """The hole the round-trip cannot see on its own - and the check that does.

    The reconstruction puts the arc's bytes back wherever the pointer sits, so a pointer sitting on
    the WRONG line is put back just as happily: cut and reference would agree with each other and the
    door would silently lose a line that was not its index entry. So the removed line is handed BACK
    to the reader, which is a derivation independent of the offsets the cut was made with.
    """
    door = _door(tmp_path, {"arc-e.md": _ARC_E})
    planning = _plan_folder(door)
    verify_roundtrip(planning)

    cap = planning.original.index("**Cap**")
    line_end = planning.original.index("\n", cap) + 1
    move = dataclasses.replace(
        planning.moves[0],
        start=cap,
        end=line_end,
        entry=planning.original[cap:line_end],
    )
    with pytest.raises(ArchiveMismatch) as refus:
        verify_roundtrip(dataclasses.replace(planning, moves=(move,)))
    assert "does not declare" in str(refus.value)


def test_verify_index_MORD_si_la_porte_garde_une_entree_devenue_morte(tmp_path: Path) -> None:
    """The barrier's own index rule, applied BEFORE the write - both directions of it.

    An entry left behind names a file that is gone (``index_sans_fichier``); an entry removed too
    many leaves a live arc named nowhere (``arc_hors_index``). Either one is a commit the pre-commit
    hook blocks, i.e. a command that hands the user a plan his next commit refuses.
    """
    door = _door(tmp_path, {"arc-e.md": _ARC_E, "arc-y.md": _OPEN})
    planning = _plan_folder(door)
    verify_readability(planning, role=ROLE_PORTE)  # the honest run passes

    stale = dataclasses.replace(planning, remaining=planning.original)  # entry never replaced
    with pytest.raises(ArchiveMismatch) as refus:
        verify_readability(stale, role=ROLE_PORTE)
    assert "index_sans_fichier" in str(refus.value)

    lost = dataclasses.replace(
        planning,
        remaining=planning.remaining.replace(f"- `{ARCS_DIRNAME}/arc-y.md` — l'arc arc-y", "-"),
    )
    with pytest.raises(ArchiveMismatch) as refus:
        verify_readability(lost, role=ROLE_PORTE)
    assert "arc_hors_index" in str(refus.value)


def test_index_entries_lit_une_DECLARATION_jamais_une_mention() -> None:
    """What the archiver replaces is a declaration - asked of the reader, never re-stated here.

    A door may MENTION any path it likes in prose, and removing a sentence because it names a file
    would be exactly the rewrite this module exists to prevent. The pair below is the boundary: only
    the first line would become an ``index_sans_fichier`` once the file leaves.
    """
    door = (
        f"- `{ARCS_DIRNAME}/arc-e.md` — ARC E\n"
        f"Un doublon entre {ARCS_DIRNAME}/arc-e.md et ailleurs.\n"
        f"```markdown\n- `{ARCS_DIRNAME}/arc-e.md` — un exemple\n```\n"
    )
    found = index_entries(door, "arc-e.md")

    assert [line for line, _, _ in found] == [1]
    start, end = found[0][1], found[0][2]
    assert door[start:end] == f"- `{ARCS_DIRNAME}/arc-e.md` — ARC E\n"


def test_le_socle_MONO_FICHIER_ignore_totalement_les_arcs() -> None:
    """No arc, no change: the floor of the format is judged by exactly the code it was judged by.

    Pinned rather than assumed, because "I only added a branch" is what every widening says. An empty
    ``arcs`` must leave the reference, the residual and the moves identical to the pre-D166 answer.
    """
    text = _closed_plan("\n")
    planning = _proven(text)
    assert planning.reference == planning.original == text
    assert planning.units == planning.sections
    assert planning.arcs == () and planning.indexed == ()
    assert [move.origin for move in planning.moves] == [""]
    assert planning.moved_from_file == planning.moved_lines


def test_un_arc_illisible_est_un_REFUS_jamais_un_arc_sauté(tmp_path: Path) -> None:
    """A plan with a file that cannot be read cannot have its reconstruction proven - so it stops.

    Skipping it would archive AROUND a hole in silence, which is the failure this whole format
    exists to close: a file judged by nobody is a file that ships unread.
    """
    door = _door(tmp_path, {"arc-e.md": _ARC_E})
    (tmp_path / ARCS_DIRNAME / "casse.md").write_bytes(b"## ARC \xff\xfe pas de l'UTF-8 \xff\n")

    with pytest.raises(ArchiveMismatch) as refus:
        plan_archiver_run.read_arcs(door)
    assert "casse.md" in str(refus.value)
    assert plan_archiver_run.main([str(door), "--today", "2026-07-28", "--apply"]) == 1
    assert not (tmp_path / "archive").exists(), "a refusal writes nothing"


def test_appliquer_deux_fois_n_ecrase_jamais_la_premiere_archive(tmp_path: Path) -> None:
    """Invariant 2 at the filesystem: the second pass refuses by name and touches nothing."""
    plan = tmp_path / "PLAN.md"
    with plan.open("w", encoding="utf-8", newline="") as handle:
        handle.write(_closed_plan("\n"))
    assert plan_archiver_run.main([str(plan), "--today", "2026-07-28", "--apply"]) == 0
    archive = next((tmp_path / "archive").glob("*.md"))
    stamp = archive.stat().st_mtime_ns

    # Put the arc back, byte for byte, and archive again the same day.
    with plan.open("w", encoding="utf-8", newline="") as handle:
        handle.write(_closed_plan("\n"))
    assert plan_archiver_run.main([str(plan), "--today", "2026-07-28", "--apply"]) == 0

    assert archive.stat().st_mtime_ns == stamp
    with plan.open(encoding="utf-8", newline="") as handle:
        assert handle.read() == _closed_plan("\n")


# --------------------------------------------------------------------------------------------
# H4 - filiation_problems - a promotion refuses for as long as one item that is not done has
# neither been picked back up, nor withdrawn (H1), nor closed.
# --------------------------------------------------------------------------------------------

_PREDECESSEUR = (
    "# PLAN — v1\n\n> **Cap** : v1\n\n"
    "- **A1** \U00002B1C jamais repris, jamais retire.\n"
    "- **A2** \U00002705 deja fait.\n"
    "- **A3** \U000026D4 clos, decide.\n"
    "- **A4** \U00002B1C repris dans la suite.\n"
    "- **A5** \U0001F504 en cours, retire par H1.\n"
)


def test_un_item_NON_FAIT_ni_repris_ni_retire_ni_clos_est_NOMME() -> None:
    """`H4`, `*Fini quand*`, word for word: the only item that falls into none of the three paths -
    A4 is picked back up, A5 is withdrawn, only A1 has neither recourse."""
    ancien = read_plan(_PREDECESSEUR)
    nouveau = read_plan("# PLAN — v2\n\n> **Cap** : v2\n\n- **A4** \U00002B1C repris.\n- **B1** \U00002B1C neuf.\n")

    problemes = filiation_problems(ancien, nouveau, retires=frozenset({"A5"}))

    assert [p.detail.split()[0] for p in problemes] == ["A1"], problemes


def test_FAIT_et_CLOS_ne_sont_jamais_nommes_meme_absents_de_la_suite() -> None:
    """```` and ```` already carry their own answer - ``clos`` IS the shape "declared out of
 scope" takes in this format, with no second field."""
    ancien = read_plan(_PREDECESSEUR)
    nouveau = read_plan("# PLAN — v2\n\n> **Cap** : v2\n\n- **B1** \U00002B1C neuf.\n")

    problemes = filiation_problems(ancien, nouveau)

    accuses = {p.detail.split()[0] for p in problemes}
    assert "A2" not in accuses and "A3" not in accuses


def test_repris_NOMMEMENT_dans_la_suite_n_est_pas_accuse() -> None:
    """An IDENTITY, never a mention - the same principle as `A1` one level up."""
    ancien = read_plan(_PREDECESSEUR)
    nouveau = read_plan("# PLAN — v2\n\n> **Cap** : v2\n\n- **A4** \U00002B1C repris ici, tel quel.\n")

    problemes = filiation_problems(ancien, nouveau)

    assert "A4" not in {p.detail.split()[0] for p in problemes}


def test_une_CITATION_en_prose_ne_reprend_PAS_l_item_seule_une_identite_le_fait() -> None:
    """The exact defect this item exists to close, one level up: citing `A4` in the body of
    another item does not pick it back up - otherwise a promotion could mention everything it
    abandons and declare itself complete."""
    ancien = read_plan(_PREDECESSEUR)
    nouveau = read_plan(
        "# PLAN — v2\n\n> **Cap** : v2\n\n"
        "- **B1** \U00002B1C ce n'est pas A4 que je fais, c'est autre chose.\n"
    )

    problemes = filiation_problems(ancien, nouveau)

    assert "A4" in {p.detail.split()[0] for p in problemes}


def test_retire_par_H1_n_est_pas_accuse() -> None:
    """``retires`` comes from the real ledger (`plan_retrait.RetraitLedger`), never guessed here -
    this function touches no disk."""
    ancien = read_plan(_PREDECESSEUR)
    nouveau = read_plan("# PLAN — v2\n\n> **Cap** : v2\n\n- **A4** \U00002B1C repris.\n- **B1** \U00002B1C neuf.\n")

    problemes = filiation_problems(ancien, nouveau, retires=frozenset({"A5"}))

    assert "A5" not in {p.detail.split()[0] for p in problemes}
    # And A1 stays the only one named: withdrawing A5 from the blame must not make another vanish.
    assert {p.detail.split()[0] for p in problemes} == {"A1"}


def test_aucun_item_perdu_rend_ZERO_probleme_jamais_un_defaut_implicite() -> None:
    """The nominal case of a complete promotion - everything is either done, closed, picked back
    up, or withdrawn."""
    ancien = read_plan(_PREDECESSEUR)
    nouveau = read_plan("# PLAN — v2\n\n> **Cap** : v2\n\n- **A1** \U00002B1C repris.\n- **A4** \U00002B1C repris.\n")

    problemes = filiation_problems(ancien, nouveau, retires=frozenset({"A5"}))

    assert problemes == ()


# **HARDENING (2026-08-16), H4 stays CLOSED -- this does not reopen the case.**
#
# ORIGIN population, written before looking for a second population (the orchestrator's own
# protocol, documented in a chat-session log): `test_les_bornes_de_section_sont_celles_du_lecteur_
# de_plans` (higher up in this file) already replays this SAME property on real material -- but
# its "real" is `docs/` OF THIS REPO, the population that was used to write `split_sections`/
# `read_plan` and to make them converge. Reading "real" a second time on the SAME source would not
# be a second population -- exactly the trap the orchestrator names on `plancher_run.py` this
# round.
#
# Second population, GENUINELY different: External Research's plan (`projects/saas/External Research/
# plan/`), a nested repo, written by a different process, never consulted to build or validate
# `plan_archive.py`. It differs structurally, not just geographically: measured live,
# `plan_registry.plan_files` sees NO file there at all -- `DOOR_FILENAMES` (`PLAN.md` /
# `PLAN_COURANT.md`) does not exist under that folder, which uses `README.md` as its door and
# arc names spelled out in full, never this repo's D166 convention. This is a partial AVOWAL,
# written here rather than hidden: the witness cannot go through `plan_files`/`arc_tree`, it calls
# `split_sections`/`read_plan` directly on each file, the layer that requires no door.
def test_les_bornes_de_section_tiennent_HORS_POPULATION_sur_le_plan_REEL_externe() -> None:
    dossier = (
        Path(__file__).resolve().parents[2]
        / "projects"
        / "saas"
        / "External Research"
        / "plan"
    )
    if not dossier.is_dir():
        pytest.skip(
            "projects/saas/External Research/plan absent on this machine (outside git tracking, "
            "D163) -- no second population available here, not an absence of measurement taken "
            "elsewhere"
        )
    fichiers = sorted(dossier.glob("*.md"))
    assert fichiers, f"no .md file under {dossier} -- empty population, not measurable"

    total_sections = 0
    total_items = 0
    for chemin in fichiers:
        texte = chemin.read_text(encoding="utf-8")
        sections = split_sections(texte)
        lecture = read_plan(texte)
        total_sections += len(sections)
        total_items += len(lecture.items)

        # The spans tile the file exactly -- no gap, no overlap (the same invariant as the
        # Mnemosyne population, never copied onto a source it never saw).
        for au_dessus, en_dessous in zip(sections, sections[1:]):
            assert au_dessus.last_line == en_dessous.first_line - 1, chemin
            assert au_dessus.end == en_dessous.start, chemin
        if sections:
            assert sections[-1].last_line == len(texte.splitlines()), chemin
            assert sections[-1].end == len(texte), chemin

        # And every item from that project falls into EXACTLY one section -- unless it lives BEFORE the
        # file's first `## ` (`item.section == ""`, the same legitimate "arc with no section"
        # the sibling test documents on Mnemosyne) -- the property this module must hold to
        # archive an arc without ever cutting an item in two.
        for item in lecture.items:
            portees = [s for s in sections if s.first_line <= item.line <= s.last_line]
            if item.section == "":
                assert portees == [], (chemin, item)
            else:
                assert len(portees) == 1, (chemin, item)
                assert portees[0].title == item.section, (chemin, item)

    # Vacuity discarded first, never a verdict founded on a corpus that silently emptied itself.
    assert total_sections >= 1, "no section read across the whole external plan"
    assert total_items >= 1, "no item read across the whole external plan"
