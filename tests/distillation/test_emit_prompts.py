"""The `distill-emit` seam (anti-drift) - the distillation contract comes from the CODE, never a copy.

THE property that matters (the lesson that cost the first frontier pass): the emission carries the REAL
`build_prompt` prompt - the one the local model receives - not a hand transcription that drifts. It is locked
two ways: (1) the emission contains EXACT fragments of the real template, precisely the ones the old
hand-copied SKILL.md had LOST; (2) every section prompt is byte-identical to `build_prompt`.
Also: the source-quality gate cuts off (flag + STOP) a rotten source, FORCE overrides it. Pure/offline (no
brick, no model). Brick-free."""

from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

from _invariants import REPO_ROOT
from mnemosyne.production import DistilledType, build_prompt
from mnemosyne.production.chapter_parsing import PLACEHOLDER_DESCRIPTION

_SCRIPT = REPO_ROOT / "system" / "skills" / "distillateur" / "emit_prompts.py"
_spec = importlib.util.spec_from_file_location("emit_prompts", _SCRIPT)
assert _spec is not None and _spec.loader is not None
emit_prompts = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(emit_prompts)

# A clean-prose raw that PASSES the source gate: two sentences (>= 5 words, >= 30 chars, mostly letters),
# repeated past the ~26k-char chunk target so the real chunk_book yields THREE sections - one with a heading
# > 60 chars, so section_input's title_hint[:60] truncation is really exercised end to end (minor audit 1).
_PROSE = (
    "Risk management is the disciplined core of every serious quantitative investing approach. "
    "A prudent investor diversifies broadly across many genuinely uncorrelated assets and ideas. "
)
_LONG_TITLE = "A Deliberately Very Long Chapter Heading That Exceeds Sixty Characters For The Test"
_RAW = (
    "# One\n\n"
    + _PROSE * 170
    + f"\n\n# {_LONG_TITLE}\n\n"
    + _PROSE * 170
    + "\n\n# Two\n\n"
    + _PROSE * 60
)
_OUT = Path("knowledge/distilled/quant/x.md")


def test_emission_carries_the_real_prompt_template_not_a_handcopy() -> None:
    out = emit_prompts.build_emission(_RAW, "T", "library/x", _OUT)
    # these EXACT fragments live in the code template (_PROMPT_TEMPLATE) and were MISSING from the old
    # hand-copied SKILL.md prompt - their presence proves the emission replays the code, so it cannot drift.
    assert "never drop or alter a verbatim passage below because of it" in out
    assert "--- SOURCE START ---" in out and "--- SOURCE END ---" in out


def test_emission_reproduces_build_prompt_byte_for_byte_per_section() -> None:
    out = emit_prompts.build_emission(_RAW, "T", "library/x", _OUT)
    chunks = emit_prompts.chunk_book(_RAW)
    # three headings (incl. one > 60 chars) really split the book, so the title_hint[:60] cut inside
    # section_input is exercised - both hosts route through section_input BY CONSTRUCTION, not by convention.
    assert len(chunks) >= 3 and any(len(title) > 60 for title, _ in chunks)
    for sec_title, sec_text in chunks:
        expected = build_prompt(emit_prompts.section_input("library/x", sec_title, sec_text))
        assert (
            expected.rstrip("\n") in out
        )  # the exact local-model prompt is what the agent receives


def test_emission_emits_one_prompt_block_per_section_plus_schema_and_out_path() -> None:
    out = emit_prompts.build_emission(_RAW, "T", "library/x", _OUT)
    n = len(emit_prompts.chunk_book(_RAW))
    assert out.count("### PROMPT SECTION ") == n
    assert (
        '"passages"' in out and '"maxItems"' in out
    )  # the JSON schema is emitted for the agent to match
    assert str(_OUT) in out  # the mirror out-path is emitted (derived from the raw, not hand-typed)


def test_emission_flags_and_stops_on_an_unusable_source() -> None:
    # a digit-soup raw (a broken extraction / all tables) fails the source gate -> flag + STOP, no prompts.
    garbage = "1234567890 " * 700  # ~7700 chars, ~90% digits -> digit_ratio well over the bar
    out = emit_prompts.build_emission(garbage, "T", "library/x", _OUT)
    assert "source-unusable" in out and "STOP" in out
    assert "### PROMPT SECTION" not in out  # nothing to distill - it never emits section prompts


def test_force_emits_prompts_despite_a_bad_source() -> None:
    # FORCE=1 parity with distill_book: recover a false-positive by emitting the prompts anyway.
    out = emit_prompts.build_emission("1234567890 " * 700, "T", "library/x", _OUT, force=True)
    assert "FORCE" in out and "### PROMPT SECTION" in out


def test_split_dir_emits_one_file_per_section_plus_the_agent_plan(tmp_path, capsys) -> None:
    # The replayable agent lane: one prompt file per section, each one a clean single Read for an agent.
    book = tmp_path / "b.md"
    # NB: chunk_book walks LINES - one giant line yields a single chunk, so the body must be multi-line.
    book.write_text("# A\n" + ("alpha beta gamma delta.\n" * 9000), encoding="utf-8")
    emit_prompts.main([str(book), "--split-dir", str(tmp_path / "emis")])
    files = sorted((tmp_path / "emis").glob("sec_*.md"))
    assert len(files) >= 2 and files[0].name == "sec_001.md"
    out = capsys.readouterr().out
    assert (
        "PLAN:" in out and "HAIKU agents" in out
    )  # the dispatch plan is printed, never re-derived by hand
    assert "AGENT_BRIEF.md" in out  # and it points at the versioned brief, not a scratchpad copy


def test_agent_slices_cover_1_to_n_with_no_hole_and_no_overlap() -> None:
    # The invariant, at every size: a hole silently drops a section, an overlap distills one twice.
    for n in range(1, 201):
        slices = emit_prompts.agent_slices(n)
        covered: list[int] = []
        for lo, hi in slices:
            covered.extend(range(lo, hi + 1))
        assert covered == list(range(1, n + 1)), f"n={n}"
        assert all(hi - lo + 1 <= emit_prompts.SECTIONS_PER_AGENT for lo, hi in slices), f"n={n}"


def test_agent_slices_spread_the_remainder_instead_of_leaving_a_crumb() -> None:
    # naive ceil-then-fill gave the last agent 1 section (n=36 -> ...,5,1): a whole agent booted for nothing
    sizes = [hi - lo + 1 for lo, hi in emit_prompts.agent_slices(36)]
    assert sizes == [5, 5, 5, 5, 4, 4, 4, 4] and sum(sizes) == 36
    assert min(sizes) > 1  # the real property: no crumb slice


def test_split_dir_slices_cover_every_section_exactly_once(tmp_path, capsys) -> None:
    # A hole or an overlap in the plan = a section silently lost or done twice. Pin the arithmetic.
    import re

    book = tmp_path / "b.md"
    book.write_text("# A\n" + ("alpha beta gamma delta.\n" * 40000), encoding="utf-8")
    emit_prompts.main([str(book), "--split-dir", str(tmp_path / "emis")])
    out = capsys.readouterr().out
    n = len(list((tmp_path / "emis").glob("sec_*.md")))
    assert (
        n > emit_prompts.SECTIONS_PER_AGENT
    )  # else the plan is one slice and this test proves nothing
    covered: list[int] = []
    for lo, hi in re.findall(r"sections (\d+)-(\d+)", out):
        covered.extend(range(int(lo), int(hi) + 1))
    assert covered == list(range(1, n + 1))  # every section, once, in order


def test_section_input_pins_what_a_section_feeds_the_model() -> None:
    # section_input is the ONE place local + frontier agree on a section's model input (dtype, title cut) -
    # both _distill_section (local) and build_emission (frontier) route through it, so parity is structural.
    inp = emit_prompts.section_input("library/x", "T" * 90, "body text")
    assert inp.dtype == DistilledType.BOOK
    assert inp.title_hint == "T" * 60  # truncated to 60 - shared by both hosts by construction
    assert inp.source_text == "body text" and inp.doc_id == "library/x"


# --- the MAP of a book, and aiming at a chapter by NAME (arc I, I1) ------------------------------
# Measured on 2026-07-28: discovering WHICH section held a chapter cost 1,008,988 bytes of stdout,
# because the only way to see the chunking was to emit the whole contract. The calculation existed
# all along (`chunk_book` returns titles); nothing printed it.

_OCR_RAW = (
    "# A CKNOWLEDGMENTS\n\n"  # the REAL title that cost the measurement: OCR split the first letter
    + _PROSE * 170
    + "\n\n# Bounding  Principle\n\n"  # and the doubled inner space OCR leaves everywhere
    + _PROSE * 170
    + "\n\n# Optimal Stopping\n\n"
    + _PROSE * 60
)


def test_the_map_is_the_SAME_chunking_the_emission_uses() -> None:
    """A map that chunks differently from the emission sends you to the wrong section, confidently."""
    toc = emit_prompts.book_toc(_RAW)
    chunks = emit_prompts.chunk_book(_RAW)
    assert [(title, size) for _, title, size in toc] == [(t, len(b)) for t, b in chunks]
    assert [i for i, _, _ in toc] == list(range(1, len(chunks) + 1))  # 1-based, like the prompts


def test_a_chapter_is_found_THROUGH_the_ocr_damage_that_made_this_needed() -> None:
    """`ACKNOWLEDGMENTS` must find `A CKNOWLEDGMENTS`; `bounding principle` must find two spaces.

    This is the whole point of matching on what SURVIVES OCR rather than on what a title should look
    like: a naive substring search fails on the exact case that motivated the feature.
    """
    toc = emit_prompts.book_toc(_OCR_RAW)
    assert [i for i, _, _ in emit_prompts.resolve_chapter(toc, "acknowledgments")] == [1]
    assert [i for i, _, _ in emit_prompts.resolve_chapter(toc, "bounding principle")] == [2]
    assert emit_prompts.resolve_chapter(toc, "nowhere in this book") == []


def test_an_ambiguous_name_is_REFUSED_and_names_its_candidates(tmp_path, capsys) -> None:
    """Picking the first match silently would be the worst outcome: you aimed, you missed, quietly."""
    book = tmp_path / "b.md"
    book.write_text(_OCR_RAW, encoding="utf-8")
    assert (
        emit_prompts.main([str(book), "--chapter", "in"]) == 1
    )  # matches 'BoundING', 'StoppINg'...
    err = capsys.readouterr().err
    assert "match(es)" in err
    # The selection must not wear the whole book's clothes: rendering a filtered list under the
    # default label would announce "2 SECTION(S)" and a total that is not the book's.
    assert "MATCHING CHAPTER(S)" in err
    assert "SECTION(S) - index" not in err


def test_an_unknown_name_is_refused_and_shows_the_whole_map(tmp_path, capsys) -> None:
    book = tmp_path / "b.md"
    book.write_text(_OCR_RAW, encoding="utf-8")
    assert emit_prompts.main([str(book), "--chapter", "zzz-absent"]) == 1
    err = capsys.readouterr().err
    assert "no chapter" in err
    assert "A CKNOWLEDGMENTS" in err  # the map, so the next attempt is informed


def test_a_named_chapter_emits_THAT_section_and_only_it(tmp_path, capsys) -> None:
    book = tmp_path / "b.md"
    book.write_text(_OCR_RAW, encoding="utf-8")
    assert emit_prompts.main([str(book), "--chapter", "bounding principle"]) == 0
    out = capsys.readouterr().out
    assert "### PROMPT SECTION 2/3" in out
    assert "### PROMPT SECTION 1/3" not in out and "### PROMPT SECTION 3/3" not in out


def test_range_and_chapter_together_are_refused_rather_than_silently_ranked(
    tmp_path, capsys
) -> None:
    book = tmp_path / "b.md"
    book.write_text(_OCR_RAW, encoding="utf-8")
    assert emit_prompts.main([str(book), "--chapter", "optimal", "--range", "1:1"]) == 1
    assert "ambigu" in capsys.readouterr().err


def test_the_summary_is_what_the_SHELL_LINE_prints_not_just_the_function(tmp_path) -> None:
    """What is DELIVERED is `make distill-sommaire`, so that is what is tested.

    A test named after a command that spawns no command leaves the whole boundary unproven - the
    Makefile recipe, the flag plumbing, the exit code. That exact misnomer was found and fixed twice
    in this repo already.
    """
    book = tmp_path / "livre.md"
    book.write_text(_OCR_RAW, encoding="utf-8")
    done = subprocess.run(
        ["make", "distill-sommaire", f"BOOK={book}"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    assert done.returncode == 0, done.stderr
    assert "3 SECTION(S) - index | title | characters" in done.stdout
    assert "A CKNOWLEDGMENTS" in done.stdout
    assert "total:" in done.stdout
    assert "### PROMPT SECTION" not in done.stdout  # the MAP, not the emission - that is the point


# --------------------------------------------------------------------------------------------------
# G4 - the INTERNAL doctrinal contradiction (differential trial of YYYY-MM-DD)
# The emission used to say "then assemble (SKILL.md)", while this skill states in bold that the
# contract comes from the CODE and never from a copy. The assembly format - sentinels, column 0, a
# mandatory blank line before AND after - existed ONLY in that prose: the one surface the skill itself
# describes as a trap. These checks hold the fix in BOTH directions.
# --------------------------------------------------------------------------------------------------

_SKILL_DIR = REPO_ROOT / "system" / "skills" / "distillateur"
#: the assembly format, reduced to what makes it COPYABLE: the literal sentinels.
_MARQUEURS_DE_FORMAT = ("<!-- mnemosyne:verbatim-begin -->", "<!-- mnemosyne:verbatim-end -->")


def test_le_squelette_emis_est_BYTE_IDENTIQUE_a_ce_que_le_CODE_assemble() -> None:
    """The skeleton must COME OUT of `_section_md` / `_toc_block`, not describe them.

    This is the same property as for the prompts (byte-identical to `build_prompt`), carried over to
    the surface that was missing it: the assembly. The day the format changes, the emission changes
    with it - nobody has to remember a piece of prose.
    """
    out = emit_prompts.build_emission(_RAW, "T", "library/x", _OUT)
    chapitre = emit_prompts._section_md(
        1, "<actual title of section 1>", emit_prompts._Gabarit()
    ).rstrip("\n")
    sommaire = emit_prompts._toc_block(
        [(i, f"<actual title of section {i}>", emit_prompts._Gabarit.concepts) for i in (1, 2)]
    ).rstrip("\n")
    assert chapitre in out
    assert sommaire in out


def test_le_SKILL_ne_porte_AUCUNE_copie_du_format_et_l_emission_la_porte_VRAIMENT() -> None:
    """Both directions matter: without the second, DELETING the skeleton would make this check pass.

    Absence alone is satisfied by a skill that no longer says anything AND an emission that no longer
    emits anything - the agent would be left with no format at all. So we require that the format has
    MOVED, not merely vanished.
    """
    out = emit_prompts.build_emission(_RAW, "T", "library/x", _OUT)
    for doc in sorted(_SKILL_DIR.glob("*.md")):
        texte = doc.read_text(encoding="utf-8")
        for marqueur in _MARQUEURS_DE_FORMAT:
            assert marqueur not in texte, f"{doc.name} re-acquired a copy of the format: {marqueur}"
    for marqueur in _MARQUEURS_DE_FORMAT:
        assert marqueur in out, f"the emission no longer teaches the format: {marqueur} missing"


def test_une_TRANCHE_n_emet_PAS_le_squelette_car_son_agent_n_assemble_rien() -> None:
    """A slice (and split mode, which passes `sec_range=(i, i)`) is stitched back together by `distill-apply`.

    Emitting the skeleton there would be two mistakes: bytes the agent cannot use, and a duplication
    per slice - the same trap as the sommaire, already ruled out.
    """
    entier = emit_prompts.build_emission(_RAW, "T", "library/x", _OUT)
    tranche = emit_prompts.build_emission(_RAW, "T", "library/x", _OUT, sec_range=(1, 1))
    assert "ASSEMBLY SKELETON" in entier
    assert "ASSEMBLY SKELETON" not in tranche


def test_le_sommaire_reste_CLIQUABLE_et_sa_reference_n_est_PAS_derivee() -> None:
    """The `#` in `[[#N. title]]` is what makes it an ANCHOR link - without it, you point at an empty note.

    The reference is written here by hand: deriving it from `_toc_block` would make the control blind
    to a drift in `_toc_block`. The test protects the anchor marker directly.
    """
    assert emit_prompts._toc_block([(3, "A title", ("a", "b", "c"))]) == (
        "## Sommaire\n\n- [[#3. A title]] - a, b, c\n"
    )
    assert (
        emit_prompts._toc_block([(1, "No concepts", ())])
        == "## Sommaire\n\n- [[#1. No concepts]]\n"
    )


# ---- what an isolated audit found UNPROVEN: the format was FROZEN nowhere -------------------------
#
# The skeleton check used to compute the expected value with `_section_md`: it proved the ORIGIN
# (rendered, not copied), never the CORRECTNESS. But the SKILL repealed its prose - `_section_md` is now the ONLY
# source of the format for the frontier agent, so nothing can contradict it any more. Measured: removing the
# blank line AFTER `verbatim-begin` makes it see 1 passage instead of 2; removing it BEFORE `verbatim-end`
# makes it DROP one. Both survived the repo's 1899 tests.

#: THE FORMAT, FROZEN BY HAND. NEVER regenerate it from `_section_md`: this literal is the only
#: thing in the world that can contradict the code. Every blank line in it is load-bearing.
_CHAPITRE_GELE = (
    "\n## 1. Titre\n"
    "\n"
    "Description.\n"
    "\n"
    "**Concepts** :\n"
    "- a\n"
    "- b\n"
    "\n"
    "### Contenu (verbatim)\n"
    "\n"
    "<!-- mnemosyne:verbatim-begin -->\n"
    "\n"
    "Premier passage.\n"
    "\n"
    "Second passage.\n"
    "\n"
    "<!-- mnemosyne:verbatim-end -->\n"
)
_SOMMAIRE_GELE = "## Sommaire\n\n- [[#1. Un]] - a, b, c\n- [[#2. Deux]] - d\n"


class _Doc:
    description = "Description."
    concepts = ("a", "b")
    passages = ("Premier passage.", "Second passage.")


def test_le_format_d_un_CHAPITRE_est_GELE_octet_pour_octet() -> None:
    assert emit_prompts._section_md(1, "Titre", _Doc()) == _CHAPITRE_GELE


def test_le_format_du_SOMMAIRE_est_GELE_sur_PLUSIEURS_entrees() -> None:
    """Freezing on a SINGLE entry left the loop body free: `for ... in toc[:1]` used to survive.

    Effect of the surviving mutation: on both `make distill` AND `make distill-apply`, every fiche
    lost all its sommaire chapters except the first - the operator's explicit ask.
    """
    assert (
        emit_prompts._toc_block([(1, "Un", ("a", "b", "c")), (2, "Deux", ("d",))]) == _SOMMAIRE_GELE
    )


def test_le_GABARIT_du_squelette_ne_peut_pas_enseigner_un_placeholder() -> None:
    """`_Gabarit` is a second derived variable: the test reused it, so nothing pinned it down.

    An empty description makes `_section_md` fall back to ``PLACEHOLDER_DESCRIPTION`` - the skeleton
    would then teach the agent to write, in EVERY chapter, what the SKILL declares to be a failure.
    And a single passage would stop showing the blank line BETWEEN two passages.
    """
    assert emit_prompts._Gabarit.description.strip()
    assert PLACEHOLDER_DESCRIPTION not in emit_prompts.assembly_skeleton(3)[-3]
    assert len(emit_prompts._Gabarit.passages) >= 2


def test_le_squelette_emet_le_SOMMAIRE_AVANT_le_chapitre() -> None:
    """Two independent `in` checks say nothing about ORDER - yet order is named in the threat model."""
    out = emit_prompts.build_emission(_RAW, "T", "library/x", _OUT)
    assert out.index("## Sommaire") < out.index("## 1. <actual title of section 1>")


def test_le_squelette_annonce_le_VRAI_nombre_de_sections() -> None:
    out = emit_prompts.build_emission(_RAW, "T", "library/x", _OUT)
    n = len(emit_prompts.chunk_book(_RAW))
    assert f"then the {n} chapters" in out


def test_ni_le_SPLIT_ni_une_TRANCHE_MULTI_sections_n_emettent_le_squelette(tmp_path: Path) -> None:
    """The property used to be judged only on `sec_range=(1,1)` - neither split nor a multi `RANGE=a:b`.

    Split is LITERALLY the case cited as justification: on an 86-section book, 86 copies.
    """
    multi = emit_prompts.build_emission(_RAW, "T", "library/x", _OUT, sec_range=(1, 2))
    assert "ASSEMBLY SKELETON" not in multi
    book = tmp_path / "livre.md"
    book.write_text(_RAW, encoding="utf-8")
    emit_prompts.main([str(book), "--split-dir", str(tmp_path / "out")])
    fichiers = sorted((tmp_path / "out").glob("sec_*.md"))
    assert fichiers, "the split emitted nothing - the check would be vacuous"
    assert not [f for f in fichiers if "ASSEMBLY SKELETON" in f.read_text(encoding="utf-8")]
