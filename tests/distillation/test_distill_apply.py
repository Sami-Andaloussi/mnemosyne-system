"""distill-apply - the CODE assembler for the agent path: verbatim floor + completeness, proven.

The agent fills per-section JSON; THIS code (not the agent) applies the verbatim floor (a paraphrase is
dropped) and DEMANDS every section (an agent that skipped some is refused, never a silent partial fiche).
Pure assembly - no model, no brick. Imported by path like the sibling distillateur tests.
"""

from __future__ import annotations

import json
import sys

import pytest

from _invariants import REPO_ROOT

_SKILL = REPO_ROOT / "system" / "skills" / "distillateur"
if str(_SKILL) not in sys.path:
    sys.path.insert(0, str(_SKILL))

import distill_apply as da  # noqa: E402
import distill_book as db  # noqa: E402


def test_doc_from_json_drops_paraphrase_keeps_verbatim() -> None:
    source = "The quick brown fox jumps over the lazy dog."
    obj = {
        "passages": ["quick brown fox", "an invented line not in the source"],
        "description": "d",
        "concepts": ["c1"],
        "tags": ["t1"],
        "summary": "s",
    }
    doc = da._doc_from_json(obj, source, "T", "library/x")
    assert doc.passages == (
        "quick brown fox",
    )  # the paraphrase is dropped by the verbatim floor
    assert doc.concepts == ("c1",) and doc.description == "d"


def test_doc_from_json_bounds_tags_and_concepts() -> None:
    obj = {
        "passages": [],
        "tags": [str(i) for i in range(20)],
        "concepts": [str(i) for i in range(20)],
    }
    doc = da._doc_from_json(obj, "src", "T", "library/x")
    assert (
        len(doc.tags) == 8 and len(doc.concepts) == 12
    )  # an over-eager agent cannot bloat the fiche


def test_apply_book_refuses_incomplete(tmp_path) -> None:
    book = tmp_path / "b.md"
    book.write_text("# A\nalpha content here\n# B\nbeta content here\n", encoding="utf-8")
    with pytest.raises(SystemExit):
        da.apply_book(book, [], haiku=False)  # 0 sections vs 1 chunk -> refused, no fiche written


def test_sections_from_dir_stitches_slices_in_order(tmp_path) -> None:
    # agents write one section_<globalIndex>.json each; the code stitches them back in order
    for i, desc in ((1, "one"), (2, "two"), (3, "three")):
        (tmp_path / f"section_{i:03d}.json").write_text(
            f'{{"description": "{desc}"}}', encoding="utf-8"
        )
    got = da.sections_from_dir(tmp_path, 3)
    assert [s["description"] for s in got] == ["one", "two", "three"]


def test_sections_from_dir_names_the_missing_slices(tmp_path) -> None:
    # an agent slice that never landed is a NAMED hole - never a silently short fiche
    (tmp_path / "section_001.json").write_text('{"description": "one"}', encoding="utf-8")
    (tmp_path / "section_004.json").write_text('{"description": "four"}', encoding="utf-8")
    with pytest.raises(SystemExit, match=r"\[2, 3\]"):
        da.sections_from_dir(tmp_path, 4)


def test_loads_agent_json_repairs_unescaped_inner_quotes(tmp_path) -> None:
    # measured on real agents: they copy the source's own quotes (as instructed) and forget to escape them
    f = tmp_path / "section_001.json"
    f.write_text(
        '{"title": "t", "summary": "s", "tags": [], "concepts": [], "passages": [],'
        ' "description": "the thinking that "this time is different" proved wrong"}',
        encoding="utf-8",
    )
    got = da._loads_agent_json(f)
    assert got["description"] == 'the thinking that "this time is different" proved wrong'


def test_loads_agent_json_leaves_valid_json_untouched(tmp_path) -> None:
    # the strict parse wins before any repair runs - a valid answer is never rewritten, whatever it contains
    f = tmp_path / "section_001.json"
    f.write_text(_full(description='he said "hi"', concepts=["a:b", "c,d"]), encoding="utf-8")
    got = da._loads_agent_json(f)
    assert got["description"] == 'he said "hi"' and got["concepts"] == ["a:b", "c,d"]


def test_loads_agent_json_repairs_over_escaped_closing_quote(tmp_path) -> None:
    # the mirror failure, also measured: the agent escapes the quote that CLOSES the string
    f = tmp_path / "section_015.json"
    f.write_text(
        '{"title": "t", "summary": "s", "tags": [], "passages": [],'
        ' "description": "wages are reduced.\\", "concepts": ["a"]}',
        encoding="utf-8",
    )
    got = da._loads_agent_json(f)
    assert got["description"] == "wages are reduced." and got["concepts"] == ["a"]


def _full(**over) -> str:
    obj = {
        "title": "t",
        "summary": "s",
        "tags": [],
        "description": "d",
        "concepts": [],
        "passages": [],
    }
    obj.update(over)
    return json.dumps(obj)


def test_loads_agent_json_refuses_a_repair_that_fabricates_a_key(tmp_path) -> None:
    # A repair that splits a scalar must make the tail read as `"K": V` - i.e. invent a key. Demanding the
    # exact schema keys turns silent truncation of a synthesis field into a loud refusal (audit YYYY-MM-DD).
    f = tmp_path / "section_003.json"
    f.write_text(
        '{"title": "t", "summary": "s", "tags": [], "concepts": [], "passages": [],'
        ' "description": "he cited "X", "Y": "Z" here"}',
        encoding="utf-8",
    )
    with pytest.raises(
        SystemExit, match="section_003.json"
    ):  # would have parsed, with description truncated
        da._loads_agent_json(f)


def test_loads_agent_json_strips_a_json_fence(tmp_path) -> None:
    # the likeliest agent slip, and pure envelope - no reason to make a human re-run an agent for it
    f = tmp_path / "section_001.json"
    f.write_text("```json\n" + _full(description="ok") + "\n```", encoding="utf-8")
    assert da._loads_agent_json(f)["description"] == "ok"


def test_doc_from_json_ignores_passages_that_are_not_a_list(tmp_path) -> None:
    # a STRING would iterate CHARACTERS - every letter is a substring of the source, so single letters would
    # sail through the verbatim floor as "passages" (audit YYYY-MM-DD)
    doc = da._doc_from_json({"passages": "The cat sat."}, "The cat sat.", "T", "library/x")
    assert doc.passages == ()


def test_loads_agent_json_names_the_file_it_cannot_repair(tmp_path) -> None:
    f = tmp_path / "section_007.json"
    f.write_text("{ this is not json at all", encoding="utf-8")
    with pytest.raises(SystemExit, match="section_007.json"):  # NAMED, never silently skipped
        da._loads_agent_json(f)


def test_apply_book_writes_fiche_with_floor_applied(tmp_path, monkeypatch) -> None:
    book = tmp_path / "b.md"
    book.write_text("# Chapter One\nThe cat sat on the mat.\n", encoding="utf-8")
    out = tmp_path / "out.md"
    monkeypatch.setattr(da, "_distilled_path_for", lambda p: out)
    sections = [
        {
            "summary": "s",
            "tags": ["x"],
            "description": "About a cat.",
            "concepts": ["cats"],
            "passages": ["The cat sat on the mat.", "PARAPHRASE not in the source"],
        }
    ]
    da.apply_book(book, sections, haiku=False)
    text = out.read_text(encoding="utf-8")
    assert "The cat sat on the mat." in text  # verbatim kept
    assert "PARAPHRASE not in the source" not in text  # paraphrase dropped in CODE, not trusted
    assert (
        'format: "book"' in text
    )  # canonical FORM axis - replaces the old conflated `type`
    assert (
        'sensitivity: "sensible"' in text
    )  # off-shelf source fail-safes to sensible, never public
    assert "## 1. Chapter One" in text  # section assembled


def test_book_writer_card_on_shelf_is_schema_valid(tmp_path, monkeypatch) -> None:
    """The real book writer assembles a P1 card that PASSES ``validate_frontmatter`` - every required
    field present and well-formed, DERIVED (never invented) from the shelf path (domain /
    sensitivity / source_path), the text (lang) and the distiller identity (template / version). Closes the
    writer<->schema loop ``frontmatter.py`` deliberately left open. An on-shelf book is PUBLIC by provenance,
    mirroring how :mod:`ingest.library` labels it at ingest."""
    from mnemosyne.ingest import taxonomy
    from mnemosyne.production import Distillateur, validate_frontmatter

    raw = tmp_path / "knowledge" / "raw"
    book = raw / "Finance" / "Grp" / "Economics" / str(taxonomy.DEFAULT_TYPE) / "Some Book.md"
    book.parent.mkdir(parents=True)
    book.write_text(
        "The market is the sum of its participants and their beliefs.\n" * 40, encoding="utf-8"
    )
    monkeypatch.setattr(db, "_RAW", raw)  # the shelf root, so this tmp path counts as on-shelf

    card = db._identity_card(
        book,
        "Some Book",
        "library/some-book",
        12,
        "mlx-community/GLM-4-9B",
        book.read_text(),
        "book",
    )
    res = validate_frontmatter(card)
    assert res.ok, res.errors  # the writer satisfies the schema - the loop is closed
    assert card["domain"] == [
        "Economics"
    ]  # taxonomy.domain_from_parts (reused single source, not re-parsed)
    assert (
        card["sensitivity"] == "public"
    )  # on-shelf => public by provenance, mirrors ingest storage
    assert card["id"] == "library/some-book" and card["lang"] == "en"
    assert (
        card["template"] == f"distillateur/book/{Distillateur.version}"
    )  # skill/type/version => regen staleness
    assert card["version"] == Distillateur.version


def test_book_writer_lang_heuristic_is_deterministic_fr_en() -> None:
    """The ``lang`` field (a closed set, fr/en) comes from a deterministic stopword heuristic: dominant
    French => ``fr``, dominant English => ``en`` (a tie falls to ``en``, documented in :func:`_detect_lang`)."""
    fr = "Le marche est la somme de ses participants et de leurs croyances dans la mesure ou " * 40
    en = "The market is the sum of its participants and of their beliefs to the extent that " * 40
    assert db._detect_lang(fr) == "fr"
    assert db._detect_lang(en) == "en"


def test_book_writer_sensitivity_is_type_aware(tmp_path, monkeypatch) -> None:
    """Minor audit finding 1: the ``sensitivity`` label is TYPE-AWARE, mirroring which ingest route runs - only
    the PUBLISHED shelf types (``books`` / ``youtube``) are ``public``; a ``chats`` source under the shelf
    keeps the fail-safe ``sensible``, never mislabelled public. An off-shelf source (no recognised
    ``<type>``) also fail-safes to ``sensible`` - which is what closes the emit reconstruction edge too."""
    from mnemosyne.ingest import taxonomy

    raw = tmp_path / "knowledge" / "raw"
    monkeypatch.setattr(db, "_RAW", raw)
    book = raw / "Finance" / "Grp" / "Economics" / "books" / "b.md"
    book.parent.mkdir(parents=True)
    book.write_text("x", encoding="utf-8")
    assert db._book_sensitivity(book) == "public"  # a published book => public by provenance
    if "chats" in (taxonomy.TYPES or frozenset()):  # a NON-published shelf type stays sensible
        chat = raw / "Finance" / "Grp" / "Economics" / "chats" / "conv.md"
        chat.parent.mkdir(parents=True)
        chat.write_text("a private conversation", encoding="utf-8")
        assert db._book_sensitivity(chat) == "sensible"  # NOT public - matches the ingest fail-safe
    # a PERSONAL family is sensible whatever the type -- intimate content is NEVER stamped public
    fam = sorted(taxonomy.PERSONAL_FAMILIES)[0]
    intimate = raw / fam / "Misc" / "misc" / "books" / "private.md"
    intimate.parent.mkdir(parents=True)
    intimate.write_text("intimate", encoding="utf-8")
    assert (
        db._book_sensitivity(intimate) == "sensible"
    )  # family beats the published `books` type
    assert (
        db._book_sensitivity(tmp_path / "loose.md") == "sensible"
    )  # off-shelf => no <type> => sensible
