"""`make plan-convertir` — a plan-FILE becomes a plan-FOLDER by MOVING bytes.

What this suite guards, and why each guard exists:

1. **Byte-for-byte reconstruction.** The operator's rule 1, word for word: *"you write it as is,
   exactly as is."* It is proven by reassembling the door and the arcs ITSELF — never by trusting
   the producer's own verifier — and it must be able to BITE: a character that moves, a lost
   verbatim marker, a duplicated index entry.
2. **The index written is the one the READER expects.** Checked against `plan_format` (the real
   contract), never against a reading of the documentation: a conversion that produces a plan the
   pre-commit barrier refuses is worse than a conversion that never happened.
3. **Every refusal is NAMED, and it is THAT ONE that catches it.** A name is not a test: every
   refusal is produced by an input that targets it, and it is checked that no neighbour caught it
   instead.
4. **Non-destructive** (inv. 2): nothing is erased, nothing is overwritten, and the passation note
   never lives where the reader would mistake it for an arc.
"""

from __future__ import annotations

import dataclasses
import hashlib
from pathlib import Path

import pytest

from mnemosyne.production import plan_archive, plan_convert as convert_module
from mnemosyne.production.plan_archive import (
    VERBATIM_MARKER,
    ArchiveMismatch,
    has_identity,
    slugify,
)
from mnemosyne.production.plan_convert import (
    NOTE_PREFIX,
    REFUSAL_LABEL,
    ConvertPlanning,
    index_entry,
    plan_convert,
    verify_readability,
    verify_roundtrip,
)
from mnemosyne.production.plan_format import (
    ARCS_DIRNAME,
    DOOR_FILENAMES,
    ROLE_PLAN,
    STATUS_BY_GLYPH,
    index_problems,
    is_readable,
    merge_plan,
    read_plan,
)
from mnemosyne.production.plan_registry import plan_files
from mnemosyne.runtime.plan_converter_run import apply_planning, arcs_on_disk
from mnemosyne.runtime.plan_converter_run import main as converter_main

_REPO_ROOT = Path(__file__).resolve().parents[2]

_SECTIONS = """## ARC A — Le premier \U00002705

- **A1** \U00002705 fait
      un bloc indenté qui appartient à A1
\t     et une ligne indentée par une TABULATION

## ARC B — Le second \U0001F504

- **B1** \U00002B1C à faire
- **B2** \U0001F504 en cours

| colonne | valeur |
| --- | --- |
| une table | qui reste |
"""


def _plan(sections: str = _SECTIONS, *, newline: str = "\n") -> str:
    """A plan readable AS A PLAN (a cap and at least one item), with its sections appended."""
    head = f"# PLAN — essai{newline}{newline}> **Cap** : prouver que les octets ne bougent pas{newline}{newline}"
    return (head + sections).replace("\n", newline) if newline != "\n" else head + sections


def _planned(text: str, **kwargs) -> ConvertPlanning:
    kwargs.setdefault("source", "plan/PLAN_COURANT.md")
    kwargs.setdefault("today", "2026-07-29")
    kwargs.setdefault("commit", "abc1234")
    return plan_convert(text, **kwargs)


def _reassemble(planning: ConvertPlanning) -> str:
    """Rebuild the original from the artefacts AS THEY WOULD BE WRITTEN — independently of the tool.

    Deliberately not a call to :func:`verify_roundtrip`: that is the producer's own proof, and a
    proof one can only obtain by asking the producer is a claim. Here the door is read, each entry
    line is found, and the arc's body is recovered by cutting its file on the verbatim marker —
    exactly what a human would do with a text editor.
    """
    rebuilt = planning.door
    for move in planning.moves:
        body = planning.arc_text(move).split(VERBATIM_MARKER, 1)[1]
        rebuilt = rebuilt.replace(move.entry + "\n", body, 1)
    return rebuilt


# --------------------------------------------------------------------------------------------
# 1. Move bytes, rewrite NONE of them.
# --------------------------------------------------------------------------------------------


def test_la_reconstruction_redonne_le_fichier_d_origine_octet_pour_octet() -> None:
    """Door + reassembled arcs = the original file, hash included. The cardinal guarantee."""
    text = _plan()
    planning = _planned(text)
    verify_roundtrip(planning)

    assert len(planning.moves) == 2
    rebuilt = _reassemble(planning)
    assert hashlib.sha256(rebuilt.encode()).hexdigest() == hashlib.sha256(text.encode()).hexdigest()
    assert rebuilt == text


def test_le_corps_d_un_arc_est_la_TRANCHE_EXACTE_du_plan() -> None:
    """`body` is literally `text[start:end]` — not a line-by-line reconstruction."""
    text = _plan()
    planning = _planned(text)
    for move in planning.moves:
        assert move.body == text[move.start : move.end]


def test_l_indentation_et_les_tabulations_traversent_intactes() -> None:
    """"No reformulation, not even the indentation": the tab in A1's block survives unchanged."""
    planning = _planned(_plan())
    arc_a = planning.arc_text(planning.moves[0]).split(VERBATIM_MARKER, 1)[1]
    assert "\t     et une ligne indentée par une TABULATION" in arc_a


def test_les_fins_de_ligne_CRLF_se_reconstruisent_octet_pour_octet() -> None:
    """A plan written on another machine does not lose its `\\r` — hence `newline=""` everywhere."""
    text = _plan(newline="\r\n")
    planning = _planned(text)
    verify_roundtrip(planning)
    assert "\r\n" in text
    assert _reassemble(planning) == text


#: The floors below which this test REFUSES to run. Measured on BOTH sides of the D166 conversion
#: (`make plan-convertir`), and identical by construction (the conversion MOVES bytes and rewrites
#: none of them) — but NOT frozen: `docs/` thins out as archiving proceeds (`make plan-archiver`
#: has moved dozens of closed arcs into the archive folder since the first measurement), so what
#: "identical on both sides" compares changes over time, never an absolute figure that could be
#: frozen once and for all. The choice of the floors themselves:
#:
#: * SIX sections rather than the real measured count, because an equality against the real count
#:   would be a disguised equality — `make plan-archiver` already moved that count in ONE commit
#:   (`cf8684b`);
#: * TWENTY THOUSAND characters, **77 times** this module's `_SECTIONS` fixture (257 characters):
#:   the threshold that makes the word "real" checkable instead of a label.
#: **RE-MEASURED on 2026-08-16** (the "12 reds" mandate): the real `##` material of `docs/`,
#: once the REPEATED titles are deduplicated (`## Ce que cet arc ne porte PAS`, 10 independent
#: occurrences — see the docstring of the test below), weighs **22,398 characters across 12
#: sections** — sha256 of the deduplicated multiset of bodies, sorted: `a382b729e781…`. The margin
#: under `_MIN_CORPUS` went from 84% to ~11%: if `docs/` keeps thinning out, this floor will
#: legitimately turn red one day — that will be an `(a)`, not a regression.
_MIN_ARCS = 6
_MIN_CORPUS = 20_000


def _plan_bytes(path: Path) -> str:
    """The file's BYTES — `newline=""` like the command, or `\\r\\n` would be translated away."""
    with path.open(encoding="utf-8", newline="") as handle:
        return handle.read()


def test_le_VRAI_plan_du_depot_se_reconstruit_octet_pour_octet() -> None:
    # TODO(public-mirror): needs human review — this test reads the REAL `docs/` tree of this
    # repo (via `plan_files`) and requires at least `_MIN_ARCS` sections / `_MIN_CORPUS`
    # characters of real plan content. The public mirror's `docs/` only carries the allow-listed
    # subset (FORMAT_PLAN.md, parentheses/README.md, signalements/README.md), so this test is
    # unlikely to find enough material and may fail once this file runs inside the mirror repo.
    """The proof on the repo's real material, not on a fixture — and without writing anything.

 A three-section fixture does not carry the structure of the real thing (1443 lines, code
 blocks, accents, glyphs, tables). So this test looks for it where it actually IS, on both
 sides of the hinge this module exists to allow.

 **What was repaired, and why it is the class and not the case.** The test used to read
 the plan's door file as a single MONOLITHIC file. The day `make plan-convertir` actually
 ran, the door dropped to 28 lines with not a single `##` section: `planning.moves` became
 empty and the converter's cardinal proof no longer bore on anything — a harness that only
 holds as long as nobody uses the mechanism it guards. The material is now ASSEMBLED from
 what `docs/` actually carries: the door's head (its title, its cap, its prose) plus the body
 of every `##` section found, in the door as much as in the arcs.

 **RE-MEASURED on 2026-08-16 (the "12 reds" mandate)**: the character count DROPS over
 time, and that is not test drift — `docs/` has lost most of its living volume since the
 first measurement (`make plan-archiver` moved dozens of closed arcs into the archive folder over
 successive passes), so "before" and "after" no longer carry the same bytes as the day
 "123,091" was written: comparing that figure to today would violate
 `same-measure-before-and-after`. Today: **22,398 characters, 12 section bodies** — and
 **12** is the constant that survived, because 12 is the REAL number of DISTINCT titles, not
 a coincidence with the number of arc files.
 **FIXED IN THE SAME PASS**: 10 of this repo's 12 arcs EACH carry their own
 `## Ce que cet arc ne porte PAS` section, added independently across different passes — a
 title REPEATED 10 times in the corpus rebuilt here, which welds them all into a SINGLE
 fictitious file. `plan_convert.py` is NEVER invoked on more than one door at a time
 (`plan_converter_run.main()` takes only a single `plan`): these ten identical titles NEVER
 coexisted in one real file before conversion, and welding them back together here makes them
 collide on re-slugifying — an artefact of THIS test's reconstruction, not a defect of the
 conversion itself. Only the FIRST occurrence of each title is kept (see the code below),
 which restores exactly the "12 section bodies" already documented.

 The head lines that NAME an arc (`plan/…md`) are discarded, for a mechanical reason, not an
 aesthetic one: after conversion they are the door's index entries, so putting them back in
 front of the sections they index would turn each one into a DUPLICATE entry — the refusal
 `verify_roundtrip` rightly raises. This filter discards 0 lines before conversion and 12
 after (one per kept section), and leaves, in both cases, the same 1,401-character head
 (re-measured on 2026-08-16; was 949).

 **What this corpus does NOT carry, measured instead of assumed**: ZERO ``` delimiter in
 column ≤ 3 (the living plan's six occurrences are inline spans indented by six spaces, which
 `_FENCE_RE` does not see), zero tab, zero CRLF, zero trailing space. These four forms remain
 proven by this module's own fixtures, and claiming them here would be a "measured" label
 stuck on a clause nobody measures. Found BY a sabotage: replacing `if inside % 2` with
 `if inside` in `_fence_trouble` survives this entire file, because the real material has not
 a single code block for the rule to look at.
 """
    files = plan_files(_REPO_ROOT / "docs")
    texts = {path: _plan_bytes(path) for path in files}
    door = files[0]  # `plan_files` returns the door first, then the arcs (D166, clause 2).
    assert door.name in DOOR_FILENAMES, f"{door} is not a door ({'/'.join(DOOR_FILENAMES)})"

    door_sections = plan_archive.split_sections(texts[door])
    cut = door_sections[0].start if door_sections else len(texts[door])
    head = "".join(
        line
        for line in texts[door][:cut].splitlines(keepends=True)
        if f"{ARCS_DIRNAME}/" not in line
    )
    # A section title can legitimately repeat ACROSS several already-separate arcs (10 of this
    # repo's 12 arcs each carry their own "Ce que cet arc ne porte PAS" section, added
    # independently across different passes) — but `plan_convert.py` is NEVER invoked on more
    # than one door at a time (`plan_converter_run.main()` takes only a single `plan`), so these
    # ten identical titles never coexisted in one real file before conversion. Welding them back
    # together here would make them collide on re-slugifying — an artefact of THIS test, not a
    # defect of the conversion. Only the FIRST occurrence of each title is kept, in the
    # door-then-arcs order `plan_files` already returns deterministically.
    seen_titles: set[str] = set()
    bodies = []
    for text in texts.values():
        for section in plan_archive.split_sections(text):
            if section.title in seen_titles:
                continue
            seen_titles.add(section.title)
            bodies.append(section.body)
    corpus = head + "".join(bodies)

    # Emptiness guards BEFORE the verdict they protect: a red pass discards everything it
    # measured, so a guard placed after only runs once it is no longer of any use.
    assert len(bodies) >= _MIN_ARCS, f"{len(bodies)} sections across {len(files)} plan file(s)"
    assert len(corpus) >= _MIN_CORPUS, f"{len(corpus)} characters — a fixture, not the real thing"
    assert all(body.endswith("\n") for body in bodies), "a body with no trailing newline would merge two `##`"
    reading = read_plan(corpus)
    assert reading.cap and reading.items, "the assembled material must be a PLAN (cap + items)"
    # And "rich" is MEASURED, never asserted: these are exactly the shapes where a byte equality
    # dies silently. The figures are the SAME on both sides of the conversion -- RE-MEASURED on
    # 2026-08-16 (the living corpus has thinned since the first measurement, see the test's
    # docstring): 536 non-ASCII letters, 29 status glyphs (occurrences), 9 variation selectors, 5
    # characters outside the BMP, 18 table lines, 13 indented lines -- and the floors stay well
    # under those.
    lines = corpus.splitlines()
    assert sum(1 for char in corpus if ord(char) > 127 and char.isalpha()) >= 500
    # PRESENCE, NOT QUANTITY (A6). This floor used to be 10 for 7 real glyphs: it forbade the
    # living plan from thinning out, even though it had done nothing wrong. What it protects —
    # that a byte equality does not die silently on a surrogate pair — is now proven on a corpus
    # BUILT to carry it (`test_la_reconstruction_survit_a_un_corpus_riche_en_glyphes_LARGES`),
    # where the size is guaranteed by construction. Here it is enough that some exist.
    assert sum(1 for char in corpus if ord(char) > 0xFFFF) >= 1, "no glyph outside the BMP"
    assert any(glyph in corpus for glyph in STATUS_BY_GLYPH), "no status glyph"
    assert sum(1 for line in lines if line.startswith("|")) >= 4, "no table"
    # PRESENCE, NOT QUANTITY (A6) — 29 real indented lines against a floor of 100. A leading
    # indent is the second shape where a byte equality dies silently (it gets normalised away
    # unseen); the large fixture below carries some, at a guaranteed size.
    assert sum(1 for line in lines if line.startswith("    ") and line.strip()) >= 1

    planning = _planned(corpus, source=f"docs/{door.name}")

    assert _reasons(planning) == [], f"refused before proving anything at all: {planning.refusals}"
    assert planning.moves, "the real plan carries `##` sections — if it no longer does, this test is lying"
    assert len(planning.moves) >= _MIN_ARCS
    # The material is REAL, and that is checked rather than labelled: every moved byte is found
    # unchanged in an actual plan file of the repo. Without this line, "real" is only a word in
    # the title.
    for move in planning.moves:
        assert any(move.body in text for text in texts.values()), move.title

    verify_roundtrip(planning)
    verify_readability(planning)
    assert _reassemble(planning) == corpus


def test_la_reconstruction_MORD_quand_un_seul_caractere_a_bouge() -> None:
    """The proof must be able to FAIL: lose one character and the command refuses, naming the offset."""
    planning = _planned(_plan())
    saboted = dataclasses.replace(planning, door=planning.door.replace("prouver", "prouve", 1))

    with pytest.raises(ArchiveMismatch) as refus:
        verify_roundtrip(saboted)
    assert "divergence at character" in str(refus.value)


def test_la_reconstruction_MORD_quand_l_EN_TETE_de_l_arc_contient_la_marque() -> None:
    """A header that contains the marker cuts the body at the wrong spot — refused, never written.

    The refusal lands on the DIVERGENCE and not on "marker absent", and that is the right order:
    the marker really is there, it is the body read back that is no longer the right one. The
    "no marker at all" case is proven separately, on the shared function that carries it.
    """
    planning = _planned(_plan())
    broken = dataclasses.replace(planning, commit=f"abc{VERBATIM_MARKER}")

    with pytest.raises(ArchiveMismatch) as refus:
        verify_roundtrip(broken)
    assert "divergence at character" in str(refus.value)


def test_la_reconstruction_MORD_quand_l_arc_n_a_AUCUNE_marque_de_verbatim() -> None:
    """With no marker, the body cannot be read back — so the move cannot be PROVEN."""
    with pytest.raises(ArchiveMismatch) as refus:
        plan_archive.verify_verbatim_roundtrip(
            "avant\n- `plan/x.md` — X\naprès\n",
            (plan_archive.VerbatimMove("X", "- `plan/x.md` — X\n", "no mark here"),),
            "avant\ncorps\naprès\n",
            marker_name="the index entry",
            container_name="the door",
            written_name="the arc",
        )
    assert "verbatim mark" in str(refus.value)


def test_une_entree_d_index_en_DOUBLE_est_refusee() -> None:
    """An entry present twice is no longer a landmark: there would be no way to know which to glue back."""
    planning = _planned(_plan())
    doubled = dataclasses.replace(planning, door=planning.door + planning.moves[0].entry + "\n")

    with pytest.raises(ArchiveMismatch) as refus:
        verify_roundtrip(doubled)
    assert "2 times" in str(refus.value)


def test_la_preuve_de_reconstruction_a_UN_SEUL_foyer_partage_avec_l_archiveur() -> None:
    """The converter DELEGATES the proof to `plan_archive.verify_verbatim_roundtrip` — no copy.

    A recopied contract drifts. The delegation is checked by replacing the shared function: if the
    converter carried its own loop, the replacement would never be seen.
    """
    called: list[str] = []

    def spy(container, moves, original, **words):  # noqa: ANN001, ANN003
        called.append(words["container_name"])

    original = convert_module.verify_verbatim_roundtrip
    convert_module.verify_verbatim_roundtrip = spy
    try:
        verify_roundtrip(_planned(_plan()))
    finally:
        convert_module.verify_verbatim_roundtrip = original
    assert called == ["the door"]
    assert convert_module.verify_verbatim_roundtrip is plan_archive.verify_verbatim_roundtrip


# --------------------------------------------------------------------------------------------
# 2. The index written is the one the READER expects — checked against `plan_format`.
# --------------------------------------------------------------------------------------------


def test_l_index_ecrit_ne_laisse_AUCUN_refus_au_lecteur() -> None:
    """The real contract, queried: neither `arc_hors_index` nor `index_sans_fichier` on the produced door."""
    planning = _planned(_plan())
    problems = index_problems(
        planning.door, tuple(move.filename for move in planning.moves), folder_form=True
    )
    assert problems == ()


def test_le_plan_converti_reste_LISIBLE_comme_le_lecteur_l_assemble() -> None:
    """Same folding as `plan_registry` and the hook: `merge_plan` + `index_problems` + role PLAN."""
    planning = _planned(_plan())
    seen: dict[str, str] = {}
    door = read_plan(planning.door, ident_seen=seen)
    arcs = tuple(
        (m.member, read_plan(planning.arc_text(m), origin=m.member, ident_seen=seen))
        for m in planning.moves
    )
    merged = merge_plan(
        door,
        arcs,
        extra=index_problems(
            planning.door, tuple(m.filename for m in planning.moves), folder_form=True
        ),
    )
    assert is_readable(merged, role=ROLE_PLAN)
    assert {item.ident for item in merged.items} == {"A1", "B1", "B2"}
    assert {item.source for item in merged.items} == {f"{ARCS_DIRNAME}/arc-a-le-premier.md",
                                                      f"{ARCS_DIRNAME}/arc-b-le-second.md"}


def test_la_verification_de_lisibilite_MORD_quand_un_arc_sort_de_l_index() -> None:
    """An arc the door no longer names is `arc_hors_index` — and the conversion refuses BEFORE writing."""
    planning = _planned(_plan())
    orphaned = dataclasses.replace(
        planning, door=planning.door.replace(planning.moves[0].member, "ailleurs/rien.md", 1)
    )

    with pytest.raises(ArchiveMismatch) as refus:
        verify_readability(orphaned)
    assert "arc_hors_index" in str(refus.value)


def test_une_entree_d_index_n_est_JAMAIS_lue_comme_un_ITEM() -> None:
    """The most hostile title there is — a bold token followed by a glyph — stays PROSE.

 This is the trap the entry's shape exists to close: `- **D8** …` IS an item to the reader.
 The entry opens on a backtick, so no bold token opens it, and the title can be recopied
 verbatim behind it without ever manufacturing an item nobody wrote.
 """
    text = _plan("## **D8** \U0001F17F\U0000FE0F LE RUN COMPLET\n\n- **Z1** \U00002B1C le seul item\n")
    planning = _planned(text)
    door = read_plan(planning.door)

    assert planning.moves, "the section must be gone, otherwise the test proves nothing"
    assert door.items == (), f"the door manufactured an item: {door.items}"
    assert door.problems == (), f"the door manufactured a refusal: {door.problems}"
    assert "**D8** \U0001F17F\U0000FE0F LE RUN COMPLET" in planning.door  # the title really is there, verbatim


def test_l_entree_d_index_porte_le_titre_VERBATIM() -> None:
    """The title travels character for character — accents, glyphs, backticks and markdown included."""
    titre = "ARC I — Réparer le `distillateur` \U00002B1C *(né de l'arc B)*"
    assert index_entry(f"{ARCS_DIRNAME}/x.md", titre) == f"- `{ARCS_DIRNAME}/x.md` — {titre}"


# --------------------------------------------------------------------------------------------
# 3. Refuse rather than guess — every refusal named, and it is THAT ONE that catches it.
# --------------------------------------------------------------------------------------------


def _reasons(planning: ConvertPlanning) -> list[str]:
    return [refusal.reason for refusal in planning.refusals]


def test_refus_deja_converti() -> None:
    """A plan that is already a folder does not get reconverted: re-running would overwrite arcs we did not write."""
    planning = _planned(_plan(), arcs_present=("arc-a-le-premier.md",))
    assert _reasons(planning) == ["deja_converti"]
    assert planning.moves == () and planning.blocked


def test_refus_plan_illisible() -> None:
    """A broken plan does not get converted: that would scatter the breakage across five files."""
    planning = _planned(_plan("## ARC A\n\n- **A1** \U0001F195 statut que personne n'a défini\n"))
    assert _reasons(planning) == ["plan_illisible"]
    assert "statut_inconnu" in planning.refusals[0].detail


def test_refus_plan_illisible_quand_le_cap_manque() -> None:
    """The other half of the same rule: without `**Cap** :` there is no plan to convert."""
    planning = _planned("# PLAN — essai\n\n## ARC A\n\n- **A1** \U00002B1C x\n")
    assert _reasons(planning) == ["plan_illisible"]
    assert "Cap" in planning.refusals[0].detail


def test_refus_borne_incertaine_bloque_TOUT_le_fichier() -> None:
    """A `## ` inside a code block throws off its NEIGHBOURS' bounds: nothing at all gets cut."""
    text = _plan("## ARC A \U00002705\n\n- **A1** \U00002705 fait\n\n```markdown\n## ARC FAUX \U00002705\n```\n")
    planning = _planned(text)
    assert set(_reasons(planning)) == {"borne_incertaine"}
    assert planning.moves == () and planning.blocked


def test_un_bloc_de_code_REFERME_ne_refuse_RIEN() -> None:
    """The other half of `borne_incertaine`: a capture rate without its false-positive rate.

    Found BY a sabotage that survived: replacing `if inside % 2` with `if inside` in
    `plan_archive._fence_trouble` — i.e. refusing every section that contains a code block,
    closed or not — did not turn a single test in this file red. The reason is measured: this
    repo's living plan does not carry a single ``` in column ≤ 3 (its six occurrences are inline
    spans indented by six spaces), and the two tests that exercise fences give them an ODD count,
    which both versions of the rule catch just the same. So `% 2` is the ONLY thing covering this
    case here — and a tool that refuses an arc because it shows a code example is a tool nobody
    ever runs again.
    """
    text = _plan("## ARC A \U00002705\n\n- **A1** \U00002705 fait\n\n```python\nprint('ok')\n```\n\nsuite.\n")
    planning = _planned(text)

    assert _reasons(planning) == [], f"a CLOSED code block was refused: {planning.refusals}"
    assert [move.title for move in planning.moves] == ["ARC A \U00002705"]
    assert "```python\nprint('ok')\n```" in planning.moves[0].body
    verify_roundtrip(planning)


def test_refus_titre_sans_identite() -> None:
    """A title without a single ASCII letter gives no filename — the tool does not invent one."""
    planning = _planned(_plan("## \U0001F525\U0001F525\U0001F525\n\n- **Z1** \U00002B1C un item\n"))
    assert _reasons(planning) == ["titre_sans_identite"]
    assert planning.blocked
    assert planning.refusals[0].detail, "this is THE refusal where the human must rename something: it has to say what"


def test_le_GARDE_de_l_identite_et_le_NOMMEUR_lisent_la_MEME_chose() -> None:
    """A guard written in different words than the namer it guards is a guard that stops matching it.

    Found by the delegated agent: the refusal read `_fold(the whole title)` while `slugify` names
    from the title's HEAD. The two are equivalent — a head is a PREFIX — but an equivalence
    nobody states stops holding at the next change. The guard now queries
    `plan_archive.has_identity`, which lives beside the fallback it describes.
    """
    assert not has_identity("\U0001F525\U0001F525\U0001F525") and slugify("\U0001F525\U0001F525\U0001F525") == "section"
    # The residue, named: a CJK title carrying a digit IS an identity — poor, not invented.
    assert has_identity("日本語 2") and slugify("日本語 2") == "2"
    assert _reasons(_planned(_plan("## 日本語 2\n\n- **Z1** \U00002B1C x\n"))) == []


def test_refus_collision_de_nom() -> None:
    """Two sections, one filename: the second would overwrite the first. Measured on the real
    plan, which carries TWO sections named `ARC G`."""
    text = _plan("## ARC G — EN PAUSE \U00002705\n\n- **G1** \U00002705 x\n\n## ARC G — EN PAUSE \U00002B1C\n\n- **G2** \U00002B1C y\n")
    planning = _planned(text)
    assert _reasons(planning) == ["collision_de_nom"]
    assert "arc-g-en-pause" in planning.refusals[0].detail
    assert planning.blocked


def test_refus_garder_introuvable() -> None:
    """A `GARDER=` that designates nothing would have kept nothing — and done so silently."""
    planning = _planned(_plan(), keep=("ARC ZZZ",))
    assert _reasons(planning) == ["garder_introuvable"]


def test_refus_note_existe() -> None:
    """A same-day passation note is the proof that a conversion has already taken place (inv. 2)."""
    planning = _planned(_plan(), note_taken=True)
    assert _reasons(planning) == ["note_existe"]


def test_toute_raison_de_refus_DECLAREE_est_productible() -> None:
    """A name is not a test: every key of `REFUSAL_LABEL` must be reachable by some input.

    A reason that no input ever triggers is a promise nobody keeps — and a check that never bites
    proves nothing.
    """
    produced = set()
    for planning in (
        _planned(_plan(), arcs_present=("x.md",)),
        _planned(_plan("## ARC A\n\n- **A1** \U0001F195 x\n")),
        _planned(_plan("## ARC A \U00002705\n\n- **A1** \U00002705 x\n\n```md\n## FAUX \U00002705\n```\n")),
        _planned(_plan("## \U0001F525\U0001F525\U0001F525\n\n- **Z1** \U00002B1C x\n")),
        _planned(_plan("## G \U00002705\n\n- **G1** \U00002705 x\n\n## G \U00002B1C\n\n- **G2** \U00002B1C y\n")),
        _planned(_plan(), keep=("introuvable",)),
        _planned(_plan(), note_taken=True),
    ):
        produced.update(_reasons(planning))
    assert produced == set(REFUSAL_LABEL), f"never produced: {set(REFUSAL_LABEL) - produced}"


def test_un_seul_refus_bloque_TOUTE_la_conversion() -> None:
    """A hinge does not happen halfway: the sound section stays in the door alongside the guilty one.

    A half-converted plan would run into its own `plan/` on the next run (`deja_converti`), and
    would leave the split to a rule nobody chose.
    """
    text = _plan(_SECTIONS + "\n## \U0001F525\U0001F525\U0001F525\n\n- **Z1** \U00002B1C x\n")
    planning = _planned(text)
    assert planning.blocked
    assert _reasons(planning) == ["titre_sans_identite"]
    assert len(planning.moves) == 2, "the other sections stay CALCULATED, but nothing will be written"


# --------------------------------------------------------------------------------------------
# 4. `GARDER=` — what the tool does not decide.
# --------------------------------------------------------------------------------------------


def test_GARDER_laisse_la_section_dans_la_porte_et_la_NOMME() -> None:
    """Which section is the door is a JUDGEMENT (D166) — declared by the human, never guessed."""
    planning = _planned(_plan(), keep=("le premier",))
    assert planning.kept == ("ARC A — Le premier \U00002705",)
    assert [move.title for move in planning.moves] == ["ARC B — Le second \U0001F504"]
    assert "## ARC A — Le premier \U00002705" in planning.door
    verify_roundtrip(planning)
    assert _reassemble(planning) == planning.original


def test_GARDER_designe_le_NOM_de_la_section_jamais_sa_prose() -> None:
    """Measured on the real plan: `GARDER="ARC B"` used to keep THREE sections instead of two.

 The third was `ARC I — Réparer le `distillateur` *(né de l'arc B …)*`, designated by the
 prose of its own parenthetical. So the comparison runs against `title_head` — the very
 fragment `slugify` draws the filename from: what designates a section and what names it are
 the same string, and a designation can no longer reach into a comment.
 """
    text = _plan(
        "## ARC B — Les skills \U0001F504\n\n- **B1** \U00002B1C x\n\n"
        "## ARC I — Réparer le distillateur \U00002B1C *(né de l'arc B — 8 trous)*\n\n- **I1** \U00002B1C y\n"
    )
    planning = _planned(text, keep=("ARC B",))

    assert planning.kept == ("ARC B — Les skills \U0001F504",)
    assert [move.title for move in planning.moves] == [
        "ARC I — Réparer le distillateur \U00002B1C *(né de l'arc B — 8 trous)*"
    ]


# --------------------------------------------------------------------------------------------
# 5. Non-destructive (inv. 2), and the passation note.
# --------------------------------------------------------------------------------------------


def test_apply_ecrit_les_arcs_la_note_et_la_porte_sans_rien_effacer(tmp_path: Path) -> None:
    """The original file is not erased: it BECOMES the door, in place, under its own name."""
    text = _plan()
    door_path = tmp_path / "PLAN_COURANT.md"
    door_path.write_text(text, encoding="utf-8")
    planning = _planned(text)
    verify_roundtrip(planning)
    verify_readability(planning)

    apply_planning(planning, plan_path=door_path)

    assert door_path.is_file(), "the door has vanished — a non-destructive tool erases nothing"
    assert sorted(p.name for p in (tmp_path / ARCS_DIRNAME).glob("*.md")) == [
        "arc-a-le-premier.md",
        "arc-b-le-second.md",
    ]
    assert (tmp_path / f"{NOTE_PREFIX}-2026-07-29.md").is_file()

    # And the hardest proof: read back what is ON DISK and recover the original.
    rebuilt = door_path.read_text(encoding="utf-8")
    for move in planning.moves:
        body = (tmp_path / move.member).read_text(encoding="utf-8").split(VERBATIM_MARKER, 1)[1]
        rebuilt = rebuilt.replace(move.entry + "\n", body, 1)
    assert rebuilt == text


def test_un_arc_deja_present_n_est_JAMAIS_ecrase(tmp_path: Path) -> None:
    """The last word on "we never overwrite" belongs to the filesystem, not to a calculation."""
    text = _plan()
    door_path = tmp_path / "PLAN_COURANT.md"
    door_path.write_text(text, encoding="utf-8")
    (tmp_path / ARCS_DIRNAME).mkdir()
    squatter = tmp_path / ARCS_DIRNAME / "arc-a-le-premier.md"
    squatter.write_text("I was here first", encoding="utf-8")

    with pytest.raises(FileExistsError):
        apply_planning(_planned(text), plan_path=door_path)
    assert squatter.read_text(encoding="utf-8") == "I was here first"
    assert door_path.read_text(encoding="utf-8") == text, "the door is only rewritten LAST"


def test_le_dossier_plan_deja_peuple_est_vu_avant_toute_ecriture(tmp_path: Path) -> None:
    """`arcs_on_disk` is what makes `deja_converti` reachable — the barrier reads the disk."""
    (tmp_path / ARCS_DIRNAME / "sous").mkdir(parents=True)
    (tmp_path / ARCS_DIRNAME / "sous" / "arc.md").write_text("x", encoding="utf-8")
    assert arcs_on_disk(tmp_path) == ("sous/arc.md",)
    assert arcs_on_disk(tmp_path / "nulle-part") == ()


def test_un_plan_DEJA_converti_est_refuse_PAR_SON_NOM_et_pas_par_un_VOISIN(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The ORDER of checks decides which CAUSE gets named — found by RUNNING the command, not by re-reading it.

    The verifiers used to run BEFORE the refusal: on an already-converted plan, `verify_readability`
    folded a door whose items all live in its arcs and answered "no item readable", burying
    `deja_converti` — the only refusal that names a real gesture. A run that will write nothing has
    nothing to prove; proving the properties of a conversion that will not happen can only name
    the wrong cause.
    """
    text = _plan()
    door = tmp_path / "PLAN_COURANT.md"
    door.write_text(text, encoding="utf-8")
    (tmp_path / ARCS_DIRNAME).mkdir()
    (tmp_path / ARCS_DIRNAME / "arc-a-le-premier.md").write_text("already here", encoding="utf-8")

    code = converter_main([str(door), "--apply", "--today", "2026-07-29"])
    printed = capsys.readouterr().out

    assert code == 1, "a check that prints without exiting with a non-zero code is a comment"
    assert REFUSAL_LABEL["deja_converti"] in printed
    assert "no readable item" not in printed, "the cause named is the NEIGHBOUR's"
    assert door.read_text(encoding="utf-8") == text, "nothing was written"


def test_la_note_de_passation_dit_CE_QUI_est_parti_OU_et_QUAND() -> None:
    """The operator's rule 3. A note that does not name the arcs is a receipt, not a passation."""
    planning = _planned(_plan(), keep=("le premier",))
    note = planning.note_text()
    assert "2026-07-29" in note and "abc1234" in note
    assert "ARC B — Le second \U0001F504" in note
    assert f"`{ARCS_DIRNAME}/arc-b-le-second.md`" in note
    assert "ARC A — Le premier \U00002705" in note  # what STAYED in the door is named too
    assert "git mv" in note  # the human gesture the tool does not perform


def test_la_note_ne_vit_PAS_dans_le_dossier_des_arcs() -> None:
    """A `.md` under `plan/` is an ARC to the reader: a note dropped there would have to be indexed."""
    planning = _planned(_plan())
    assert planning.note_filename.startswith(NOTE_PREFIX)
    assert not planning.note_filename.startswith(f"{ARCS_DIRNAME}/")
    # And the name cannot be read as an arc reference: there is no `plan/` inside it.
    assert f"{ARCS_DIRNAME}/" not in planning.note_filename


def test_la_reconstruction_survit_a_un_corpus_riche_en_glyphes_LARGES() -> None:
    """ WHAT THE `outside BMP >= 10` FLOOR USED TO HOLD, on a corpus BUILT to carry it.

 A character outside the basic multilingual plane occupies TWO UTF-16 units: that is exactly
 where an index-based cut dies silently — it returns a text that still looks readable, cut in
 the middle of a surrogate pair. The living plan carried 7 of them on the day the floor
 required 10; the property is proven here on **24 wide glyphs**, a size nothing can thin down.
 """
    larges = "\U0001F17F\U0000FE0F\U0001F504\U0001F9ED\U0001F6A7\U0001F3AF\U0001F9F1\U0001F573\U0000FE0F\U0001FA9C"
    sections = [
        f"## Arc {i} {larges}\n\n- **A{i}** \U00002B1C **Un item {larges} avec des glyphes larges.**\n"
        f"    une ligne INDENTÉE {larges}, l'autre forme où une égalité d'octets meurt en silence\n"
        f"    une seconde, pour que la population ne soit pas dégénérée\n"
        for i in range(1, 4)
    ]
    corpus = "# PLAN — démo\n\n> **Cap** : prouver\n\n" + "".join(sections)
    assert sum(1 for char in corpus if ord(char) > 0xFFFF) >= 24, "the fixture itself is too poor"
    indentees = [ligne for ligne in corpus.splitlines() if ligne.startswith("    ") and ligne.strip()]
    assert len(indentees) >= 6, f"the fixture only carries {len(indentees)} indented lines"

    decoupe = plan_archive.split_sections(corpus)
    reconstruit = corpus[: corpus.index("## Arc 1")] + "".join(s.body for s in decoupe)
    assert reconstruit == corpus, "the reconstruction is no longer byte-for-byte on wide glyphs"
    assert reconstruit.encode("utf-8") == corpus.encode("utf-8"), "BYTE equality, not text equality"
