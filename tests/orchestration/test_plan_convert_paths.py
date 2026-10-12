"""Convert a plan into a folder through hostile but synthetic path forms.

Fixtures cover spaces, colons, and decomposed Unicode accents. The accented title is built from an
explicit ``\\u0301`` escape so an editor cannot silently recompose it; the associated test verifies
that the fixture remains genuinely NFD instead of ASCII disguised as Unicode.

**The reconstruction proof here is INDEPENDENT of the module's own verifier.** ``verify_roundtrip``
is the producer's proof; every test below also reassembles door + arcs by hand (splitting each arc
on :data:`~mnemosyne.production.plan_archive.VERBATIM_MARKER`) and compares two ``sha256`` digests.
Nothing closes on the producer's word - and
:func:`test_le_hachage_MORD_quand_un_seul_caractere_bouge_dans_la_porte` shows that second proof can
actually fail, because a comparison that cannot go red is decoration.
"""

from __future__ import annotations

import dataclasses
import hashlib
import unicodedata
from pathlib import Path

import pytest

from mnemosyne.production.plan_archive import VERBATIM_MARKER, ArchiveMismatch, slugify
from mnemosyne.production.plan_convert import (
    ConvertPlanning,
    index_entry,
    plan_convert,
    verify_readability,
    verify_roundtrip,
)
from mnemosyne.production.plan_format import ARCS_DIRNAME, DOOR_FILENAMES, read_plan
from mnemosyne.production.plan_registry import LISIBLE, read_plan_tree

#: How the figures in this module's docstring were obtained - the COMMAND, so they can be re-run.
#: A register that publishes only its result rots without a sound.
_REPO_MEASUREMENT = (
    'python3 -c \'import pathlib,unicodedata; p=[str(x) for x in pathlib.Path("projects")'
    '.rglob("*")]; print(len(p), sum(" " in x for x in p), sum(":" in x for x in p),'
    ' sum(unicodedata.normalize("NFC",x)!=x for x in p))\''
)

#: ``E`` + COMBINING ACUTE ACCENT, written as an ESCAPE on purpose. A pasted ``É`` is one editor
#: normalisation away from being ASCII-with-an-accent instead of the decomposed pair 80 paths of
#: this repo are stored as - and the file would still look right. It cannot be recomposed by an
#: editor, and the first test below proves it was not.
E_NFD = "E\u0301"  # E + U+0301, ecrit en echappement : un caractere colle se recompose

#: The three hostile forms, as strings, so no test hand-types them twice.
TITRE_NFD = f"ARC {E_NFD} - {E_NFD}conomies"
TITRE_NFC = unicodedata.normalize("NFC", TITRE_NFD)
TITRE_DEUX_POINTS = "ARC S:S - ExamplePilot"
TITRE_SANS_IDENTITE = "日本語 - 章"
SOURCE_AVEC_ESPACE = "projects/saas/Acme Research/PLAN.md"

_HEAD = "# PLAN - Acme Research\n\n> **Cap** : measure before building\n\n"


def _section(title: str, ident: str) -> str:
    """One ``## `` section carrying exactly one readable item - the smallest convertible arc."""
    return f"## {title}\n\n- **{ident}** \U00002B1C hold the measurement\n\n"


PLAN_NFD = _HEAD + _section(TITRE_NFD, "A1")
PLAN_NFC_ET_NFD = _HEAD + _section(TITRE_NFC, "A1") + _section(TITRE_NFD, "B2")
PLAN_DEUX_POINTS = _HEAD + _section(TITRE_DEUX_POINTS, "S1")
PLAN_SANS_IDENTITE = _HEAD + _section(TITRE_SANS_IDENTITE, "Z1")
PLAN_CRLF = (_HEAD + _section(TITRE_NFD, "A1")).replace("\n", "\r\n")

#: Every hostile fixture, named - so the batch proof below can run over the WHOLE population rather
#: than over whichever one a per-case test happened to reach. Green per item is not green per batch.
HOSTILES: dict[str, tuple[str, dict[str, object]]] = {
    "accented title in NFD": (PLAN_NFD, {}),
    "the same title in NFC and in NFD": (PLAN_NFC_ET_NFD, {}),
    "a space in the source": (PLAN_NFD, {"source": SOURCE_AVEC_ESPACE}),
    "a `:` in the title": (PLAN_DEUX_POINTS, {}),
    "a title with no ASCII identity": (PLAN_SANS_IDENTITE, {}),
    "CRLF line endings": (PLAN_CRLF, {}),
}


def _digest(text: str) -> str:
    """The bytes of ``text``, hashed - the comparison a human can re-run outside this suite."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _convertit(text: str, **kwargs) -> ConvertPlanning:
    """Plan the conversion with a fixed date/commit, so no test depends on the day it runs."""
    options: dict[str, object] = {
        "source": "docs/PLAN_COURANT.md",
        "today": "2026-07-29",
        "commit": "9e15d1f",
    }
    options.update(kwargs)
    return plan_convert(text, **options)  # type: ignore[arg-type]


def _reassemble(planning: ConvertPlanning) -> str:
    """Rebuild the original from the door and the arcs BY HAND - the second, independent proof.

    Deliberately does not call the module: each arc's body is recovered by splitting the exact bytes
    that would be written on ``VERBATIM_MARKER``, and spliced back where its index entry sits, found
    by SEARCHING for it. A producer that verifies itself proves only that it agrees with itself.
    """
    rebuilt = planning.door
    for move in planning.moves:
        marker = move.entry + "\n"
        assert rebuilt.count(marker) == 1, f"{move.title} : {rebuilt.count(marker)} entries"
        parts = planning.arc_text(move).split(VERBATIM_MARKER, 1)
        assert len(parts) == 2, move.title
        rebuilt = rebuilt.replace(marker, parts[1], 1)
    return rebuilt


def _prouve(text: str, **kwargs) -> ConvertPlanning:
    """Plan it, then demand BOTH proofs: the module's round-trip and an independent ``sha256``.

    The advertised line range is checked too. In the archiver next door a sabotage shifting every
    ``last_line`` by one survived the whole suite, because no item ever sits on a ``## `` line - and
    that range is what the arc's header CLAIMS about where its bytes came from.
    """
    planning = _convertit(text, **kwargs)
    verify_roundtrip(planning)
    assert _digest(_reassemble(planning)) == _digest(text)
    for move in planning.moves:
        assert move.lines == len(move.body.splitlines()), move.title
    return planning


# --------------------------------------------------------------------------------------------
# 0. The fixture itself, before anything is judged through it.
# --------------------------------------------------------------------------------------------


def test_la_fixture_accentuee_est_REELLEMENT_en_NFD_et_pas_de_l_ASCII_deguise() -> None:
    """The one test that keeps this file honest: the accented fixture must be DECOMPOSED.

    C20-3's exact defect, made structural. A title recomposed by an editor - or written in ASCII
    while the docstring says NFD - leaves every other test below green and testing nothing about the
    80 decomposed paths of this repo. Four clauses, because each one alone can be satisfied by a
    string that is not the trap.
    """
    assert "\u0301" in TITRE_NFD, "the combining mark itself has disappeared"
    assert not TITRE_NFD.isascii(), "an ASCII fixture tests no decomposition at all"
    assert unicodedata.normalize("NFC", TITRE_NFD) != TITRE_NFD, "recomposed: this is no longer NFD"
    assert unicodedata.normalize("NFD", TITRE_NFD) == TITRE_NFD
    # And the pair really is the SAME title seen twice, which is what makes the collision case a
    # collision rather than two unrelated names.
    assert TITRE_NFC != TITRE_NFD
    assert unicodedata.normalize("NFC", TITRE_NFD) == TITRE_NFC


# --------------------------------------------------------------------------------------------
# 1. NFD - the form macOS stores, invisible in a source file.
# --------------------------------------------------------------------------------------------


def test_un_titre_accentue_en_NFD_donne_un_nom_de_fichier_ASCII_et_garde_ses_octets() -> None:
    """A decomposed title converts, names an ASCII file, and its bytes travel UNCHANGED.

    Two guarantees that pull in opposite directions and must both hold: the FILE NAME is folded to
    ASCII (a name carrying a combining mark is a link nobody can type, and macOS would hand it back
    in a form ``==`` does not match), while the TITLE keeps its exact codepoints everywhere it is
    reproduced - the index entry, the arc's OWN heading, the moved body.

    Those three are asserted SEPARATELY, and that is not zeal. ``TITRE_NFD in arc_text(move)`` was
    the whole check here until a sabotage normalising ``ArcMove.title`` survived the suite: the
    moved body carries the ``## `` line verbatim, so the substring was found in the BODY while the
    heading above it had been rewritten. A clause nobody is the subject of is the one that rots.
    """
    planning = _prouve(PLAN_NFD)

    assert planning.refusals == ()
    (move,) = planning.moves
    assert move.filename == "arc-e-economies.md"
    assert move.filename.isascii() and "\u0301" not in move.filename
    assert move.member == f"{ARCS_DIRNAME}/arc-e-economies.md"
    # 1. the index entry left in the door  -  2. the arc's OWN heading  -  3. the bytes that moved.
    assert TITRE_NFD in move.entry and TITRE_NFD in planning.door
    assert planning.arc_text(move).startswith(f"# Arc — {TITRE_NFD}\n")
    assert move.body.startswith(f"## {TITRE_NFD}\n")
    assert unicodedata.normalize("NFC", move.body) != move.body


def test_GARDER_ecrit_en_NFC_retient_bien_une_section_dont_le_titre_est_en_NFD() -> None:
    """``GARDER=`` is typed in an editor (NFC) and must find a title stored decomposed (NFD).

    Without the NFC fold inside ``_matches``, the needle matches nothing and the tool answers
    ``garder_introuvable`` to a request that is correct.
    """
    text = PLAN_NFD + _section("ARC B - deux", "B2")
    planning = _prouve(text, keep=(unicodedata.normalize("NFC", f"{E_NFD}conomies"),))

    assert planning.refusals == ()
    assert planning.kept == (TITRE_NFD,)
    assert [move.filename for move in planning.moves] == ["arc-b-deux.md"]


# --------------------------------------------------------------------------------------------
# 2. NFC and NFD of ONE title - measured: they produce ONE file name, and only one thing stops it.
# --------------------------------------------------------------------------------------------


def test_le_meme_titre_en_NFC_et_en_NFD_produit_UN_SEUL_nom_donc_une_collision_de_nom() -> None:
    """Two sections, TWO different strings, ONE file name - refused, and the whole run blocked.

    Measured, not assumed: ``slugify`` folds through NFKD and drops combining marks, so the composed
    and the decomposed spelling of the same title both slug to ``arc-e-economies`` - 2 titles, 1
    name. Without this refusal the second arc would be written OVER the first (invariant 2), and the
    plan would come back one arc short with nothing said.
    """
    assert slugify(TITRE_NFC) == slugify(TITRE_NFD) == "arc-e-economies"

    planning = _prouve(PLAN_NFC_ET_NFD)

    assert planning.blocked
    assert [refusal.reason for refusal in planning.refusals] == ["collision_de_nom"]
    assert planning.refusals[0].title == TITRE_NFD
    assert planning.refusals[0].label, "a refusal without a French sentence is not a refusal"
    assert f"{ARCS_DIRNAME}/arc-e-economies.md" in planning.refusals[0].detail
    assert len(planning.moves) == 1


def test_la_collision_NFC_NFD_est_le_SEUL_garde_le_roundtrip_ne_la_verrait_pas() -> None:
    """The round-trip cannot catch this one, so the named refusal is what stands - measured.

    ``verify_verbatim_roundtrip`` catches a duplicate by demanding each marker appear EXACTLY ONCE
    in the door. Here the two index entries carry the two titles verbatim, so they are DIFFERENT
    strings and each appears once: the uniqueness check passes while both arcs claim the same path.
    Knowing WHICH rule catches a sabotage is the difference between a guarantee and a coincidence.
    """
    member = f"{ARCS_DIRNAME}/{slugify(TITRE_NFC)}.md"
    assert index_entry(member, TITRE_NFC) != index_entry(member, TITRE_NFD)

    # Same file name on both sides of that inequality - the collision the markers cannot show.
    assert slugify(TITRE_NFC) == slugify(TITRE_NFD)
    # And the round-trip is indeed green on the blocked planning: it is not what refuses.
    verify_roundtrip(_convertit(PLAN_NFC_ET_NFD))


# --------------------------------------------------------------------------------------------
# 3. A space in the source path.
# --------------------------------------------------------------------------------------------


def test_une_espace_dans_le_source_ressort_VERBATIM_dans_l_en_tete_et_dans_la_note() -> None:
    """``projects/saas/Acme Research/PLAN.md`` is cited whole - never split, quoted or escaped.

    The passation note is *what was moved, where, and when*; a path truncated at its space
    names a file that does not exist, and the note is the only trace of where the bytes came from.
    """
    planning = _prouve(PLAN_NFD, source=SOURCE_AVEC_ESPACE)

    (move,) = planning.moves
    assert planning.source == SOURCE_AVEC_ESPACE
    # Backticks on both sides: proof the path was carried as ONE token, space included.
    assert f"`{SOURCE_AVEC_ESPACE}`" in planning.arc_text(move)
    assert f"`{SOURCE_AVEC_ESPACE}`" in planning.note_text()
    assert f"lines {move.first_line} to {move.last_line}" in planning.arc_text(move)
    assert move.member in planning.note_text()
    # The header line carrying that path must stay PROSE to the reader - an arc is judged on it.
    assert read_plan(planning.arc_text(move), origin=move.member).problems == ()


# --------------------------------------------------------------------------------------------
# 4. A `:` in a title.
# --------------------------------------------------------------------------------------------


def test_un_deux_points_reste_dans_le_titre_et_ne_passe_jamais_dans_le_nom_de_fichier() -> None:
    """The name folds to ``arc-s-s-examplepilot``; the ``:`` survives only where it is read - the title.

    Both halves matter. A ``:`` in a file name is legal on APFS and hostile everywhere else (it is
    the classic Mac path separator, and it breaks a markdown link); a ``:`` LOST from the title
    would be the one thing this module promises never to do - rewrite what a human wrote.
    """
    planning = _prouve(PLAN_DEUX_POINTS)

    assert planning.refusals == ()
    (move,) = planning.moves
    assert move.filename == "arc-s-s-examplepilot.md"
    assert ":" not in move.filename and move.filename.isascii()
    assert " " not in move.filename
    assert move.entry == f"- `{ARCS_DIRNAME}/arc-s-s-examplepilot.md` — {TITRE_DEUX_POINTS}"
    verify_readability(planning)


def test_le_plan_converti_reste_accepte_par_le_LECTEUR_sur_chaque_forme_hostile() -> None:
    """Every hostile fixture that converts must leave a plan the reader itself still accepts.

    Asked of ``verify_readability`` rather than asserted here: the index entry is BOTH the pointer
    and the line the completeness check reads, so a title carrying a ``:``, a space or a combining
    mark must not be able to turn a door's index into an index of nothing.
    """
    for name, (text, options) in HOSTILES.items():
        planning = _convertit(text, **options)
        verify_readability(planning)  # raises ArchiveMismatch, which is the failure
        assert planning.door.count("**Cap**") == 1, name


def test_verify_readability_MORD_quand_la_porte_perd_son_cap() -> None:
    """The guard above must be able to REFUSE, or its green says nothing.

    The cap written INSIDE an arc leaves, with that arc, a door that names nothing - a plan the
    pre-commit barrier would reject on the one commit where the human has no original to compare
    against. Same NFD title as everywhere else, so the case stays inside the hostile population.
    """
    text = f"# PLAN - Acme Research\n\n## {TITRE_NFD}\n\n> **Cap** : x\n\n- **A1** \U00002B1C un\n\n"
    planning = _prouve(text)

    assert len(planning.moves) == 1
    with pytest.raises(ArchiveMismatch) as refus:
        verify_readability(planning)
    assert "would no longer be readable" in str(refus.value)


# --------------------------------------------------------------------------------------------
# 5. A title with no ASCII identity at all - the refusal must be the RIGHT one.
# --------------------------------------------------------------------------------------------


def test_un_titre_sans_identite_ASCII_est_refuse_PAR_CE_refus_pas_par_un_voisin() -> None:
    """No ASCII fragment, no file name - and the refusal names THAT, not a neighbouring cause.

    Which rule catches decides what user is told to fix. ``slugify`` would fall back to the literal
    ``"section"`` here - a name the tool invented, which two such titles would then silently share
    - so the module refuses to guess. Pinned against its neighbours: ``collision_de_nom`` (one
    section only), ``borne_incertaine`` (no fence) and ``garder_introuvable`` (no ``keep``) must
    all stay absent.
    """
    planning = _prouve(PLAN_SANS_IDENTITE)

    assert [refusal.reason for refusal in planning.refusals] == ["titre_sans_identite"]
    assert planning.refusals[0].title == TITRE_SANS_IDENTITE
    assert planning.refusals[0].label, "a refusal without a French sentence is not a refusal"
    assert planning.blocked and planning.moves == ()
    # No file is named at all - not even the fallback one.
    assert "section.md" not in planning.door
    assert planning.door == planning.original


def test_le_meme_plan_avec_un_titre_identifiable_ne_refuse_RIEN() -> None:
    """The differential half: change ONLY the title and the refusal disappears.

    Without this, "``titre_sans_identite`` fired" is compatible with a fixture that was broken for
    some other reason entirely - a refusal every plan would collect proves nothing about titles.
    """
    planning = _prouve(_HEAD + _section(f"ARC Z - {E_NFD}conomies", "Z1"))

    assert planning.refusals == ()
    assert [move.filename for move in planning.moves] == ["arc-z-economies.md"]


# --------------------------------------------------------------------------------------------
# 6. The digest, over the WHOLE hostile population - and the proof that it can fail.
# --------------------------------------------------------------------------------------------


def test_chaque_forme_hostile_se_reconstruit_octet_pour_octet_sha256_a_sha256() -> None:
    """Door + arcs, reassembled by hand, hash to the original - on all six fixtures at once.

    Per-item green is not per-batch green: each case above proves its own form, and a rule can hold
    on five of them while a sixth quietly loses a byte. The digest is computed on the encoded bytes,
    so a normalisation that keeps every visible character identical still shows up.
    """
    for name, (text, options) in HOSTILES.items():
        planning = _convertit(text, **options)
        assert _digest(_reassemble(planning)) == _digest(text), name
        assert planning.original == text, name


def test_le_hachage_MORD_quand_un_seul_caractere_bouge_dans_la_porte() -> None:
    """One lost character and BOTH proofs refuse - the independent one and the module's own.

    A comparison that cannot go red is decoration. This is also what makes the two proofs worth
    having separately: they are asserted to agree on a case where the answer is known to be NO.
    """
    planning = _prouve(PLAN_NFD)
    sabotaged = dataclasses.replace(planning, door=planning.door.replace("measure", "measur", 1))

    assert _digest(_reassemble(sabotaged)) != _digest(sabotaged.original)
    with pytest.raises(ArchiveMismatch) as refus:
        verify_roundtrip(sabotaged)
    assert "divergence at character" in str(refus.value)


# --------------------------------------------------------------------------------------------
# 7. Line endings - CRLF survives the move, and what it costs is MEASURED, not assumed.
# --------------------------------------------------------------------------------------------


def test_un_plan_en_CRLF_se_reconstruit_octet_pour_octet() -> None:
    """Windows endings travel with the bytes: no ``\\r\\n`` may collapse in a moved body."""
    planning = _prouve(PLAN_CRLF)

    (move,) = planning.moves
    assert "\r\n" in move.body
    assert "\n" not in move.body.replace("\r\n", ""), "a \\r\\n collapsed into \\n"
    assert "\r\n" in planning.arc_text(move).split(VERBATIM_MARKER, 1)[1]


def test_la_porte_d_un_plan_CRLF_repart_avec_des_fins_de_ligne_MELANGEES() -> None:
    """A measured RESIDUAL, pinned so it is visible - not an endorsement of it.

    The index entry is spliced in with a bare ``"\\n"``, and the arc header is built with
    ``"\\n".join``, so converting a CRLF plan writes files whose line endings are mixed. The
    round-trip still holds - the marker carries the very same ``"\\n"`` - but the byte-for-byte
    guarantee then depends on nothing ever normalising those files afterwards, and a plan is exactly
    the kind of file an editor or a ``.gitattributes`` rule offers to normalise. If this ever goes
    red because the splice learned the file's own ending, that is a fix: re-baseline it, do not
    restore it.
    """
    planning = _prouve(PLAN_CRLF)

    lone_lf_door = planning.door.count("\n") - planning.door.count("\r\n")
    assert planning.door.count("\r\n") >= 1 and lone_lf_door == 1
    arc = planning.arc_text(planning.moves[0])
    assert arc.count("\n") - arc.count("\r\n") == 12  # the header this module writes, in LF


# --------------------------------------------------------------------------------------------
# 8. The filesystem: a hostile root, concrete files, and the registry's own verdict.
# --------------------------------------------------------------------------------------------


def test_la_conversion_ECRITE_sous_une_racine_hostile_est_relue_LISIBLE(tmp_path: Path) -> None:
    """End to end through files: a root carrying all three forms, read back by the registry.

    The plan root is ``projects/sample/Example Project/sample-plan-S:S/Économies`` - a space, a ``:``
    and an NFD accent. Filesystem behavior matters because macOS can hand a decomposed name back,
    making bytewise ``==`` comparisons fail. The verdict comes from
    ``read_plan_tree``, the same reader the pre-commit barrier uses - not from this file's idea of
    what an index looks like.
    """
    planning = _prouve(
        _HEAD + _section(TITRE_NFD, "A1") + _section(TITRE_DEUX_POINTS, "B2"),
        source=SOURCE_AVEC_ESPACE,
    )
    root = (
        tmp_path / "projects" / "saas" / "Acme Research" / "ExamplePilot-S:S" / f"{E_NFD}conomies"
    )
    (root / ARCS_DIRNAME).mkdir(parents=True)
    (root / DOOR_FILENAMES[0]).write_text(planning.door, encoding="utf-8")
    for move in planning.moves:
        (root / move.member).write_text(planning.arc_text(move), encoding="utf-8")
    (root / planning.note_filename).write_text(planning.note_text(), encoding="utf-8")

    on_disk = sorted(p.name for p in (root / ARCS_DIRNAME).iterdir())
    assert on_disk == sorted(move.filename for move in planning.moves)
    assert all(name.isascii() for name in on_disk), on_disk

    (plan,) = read_plan_tree(root, "Acme Research")
    assert plan.state == LISIBLE, plan.why
    assert plan.reading is not None
    assert plan.reading.problems == ()
    assert {item.ident for item in plan.reading.items} == {"A1", "B2"}
    assert {item.source for item in plan.reading.items} == {move.member for move in planning.moves}
