"""Unit tests for the library taxonomy (D140 / Étape 3) - the ONE source of the shelf mapping.

Pins the two derivations the rest of ingestion leans on: reading a book's DOMAIN back off its shelf path
(the folder just above the ``<type>`` segment - robust to family/group depth AND to the
``information-retrieval`` nested case) and computing WHERE a new book is shelved (``shelf_rel`` via
``taxonomy.toml``), plus the LAZY load (the toml is read on first USE, not at import, and a missing file
fails there loudly). Producer ≠ verifier (D75): the mapping is graven once in the toml; these tests read
it, they do not re-encode it. Code & tests English (D117)."""

from __future__ import annotations

from pathlib import Path

import pytest

from mnemosyne.ingest import taxonomy


def test_domain_derived_from_a_standard_shelf_path() -> None:
    # the domain is the folder JUST ABOVE the <type> ('books'), whatever family/group sits above it.
    parts = ("Finance", "Trading", "quant-trading", "books", "Some Book.pdf")
    assert taxonomy.domain_from_parts(parts) == "quant-trading"


def test_domain_derived_from_the_information_retrieval_nested_case() -> None:
    # IR has a sub-structure INSIDE books/ - the domain is still the dir above the FIRST <type> segment.
    parts = (
        "Software",
        "Information-Retrieval",
        "information-retrieval",
        "books",
        "Machine_Learning",
        "lecture.pdf",
    )
    assert taxonomy.domain_from_parts(parts) == "information-retrieval"


def test_domain_is_none_when_no_type_segment_is_present() -> None:
    # a path with no <type> (a stray, or a README beside a domain) is NOT a shelved book -> no domain.
    assert taxonomy.domain_from_parts(("Finance", "Trading", "quant-trading", "stray.pdf")) is None
    assert taxonomy.domain_from_parts(("_intake", "arrival.pdf")) is None
    assert taxonomy.domain_from_parts(()) is None


def test_domain_is_none_when_type_is_the_first_segment() -> None:
    # a <type> at index 0 has no domain segment before it -> None (never a negative-index wraparound
    # onto the filename): the guard is `parts[i - 1] if i >= 1 else None`.
    assert taxonomy.domain_from_parts(("books", "loose.pdf")) is None
    assert taxonomy.domain_from_parts(("books",)) is None


def test_shelf_rel_known_domain_builds_the_hierarchical_path() -> None:
    # a mapped domain -> <Famille>/<Groupe>/<domain>/<type>, defaulting to the 'books' type.
    assert (
        taxonomy.shelf_rel("quant-trading")
        == Path("Finance") / "Trading" / "quant-trading" / "books"
    )
    assert (
        taxonomy.shelf_rel("information-retrieval")
        == Path("Software") / "Information-Retrieval" / "information-retrieval" / "books"
    )
    # an explicit type is honoured (the shelf mirrors the arbo for web/youtube/chats too).
    assert taxonomy.shelf_rel("crypto", "web") == Path("Finance") / "Assets" / "crypto" / "web"


def test_shelf_rel_unknown_domain_is_none() -> None:
    # a domain OUTSIDE the taxonomy has no shelf - the caller (triage) routes it to the _intake sas.
    assert taxonomy.shelf_rel("finance") is None  # 'finance' was dissolved into fine domains
    assert taxonomy.shelf_rel("not-a-domain") is None


def test_types_default_and_family_group_come_from_the_zone() -> None:
    assert "books" in taxonomy.TYPES and taxonomy.DEFAULT_TYPE == "books"
    assert taxonomy.family_group("misc") == ("General", "Misc")
    assert taxonomy.family_group("not-a-domain") is None


def test_domain_derivation_round_trips_with_shelf_rel() -> None:
    # what shelf_rel writes, domain_from_parts reads back - the two halves of the mapping agree.
    for domain in ("quant-trading", "information-retrieval", "misc", "statistics"):
        shelf = taxonomy.shelf_rel(domain)
        assert shelf is not None
        assert taxonomy.domain_from_parts((*shelf.parts, "a-book.pdf")) == domain


def test_taxonomy_is_loaded_lazily_and_fails_explicitly_on_a_missing_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # The map is read on FIRST USE, not at import (so importing any ingest module never depends on the
    # toml - the whole `mnemosyne.ingest` package imports fine here without touching it). Point the path
    # at a missing file and clear the cache: USE - not import - raises a clear error naming the file.
    monkeypatch.setattr(taxonomy, "_TAXONOMY_PATH", tmp_path / "absent.toml")
    monkeypatch.setattr(taxonomy, "_FAMILY_GROUP", None)
    monkeypatch.setattr(taxonomy, "_TYPES", None)
    monkeypatch.setattr(taxonomy, "_DEFAULT_TYPE", None)
    with pytest.raises(RuntimeError, match="taxonomy"):
        taxonomy.domain_from_parts(("Finance", "Trading", "quant-trading", "books", "x.pdf"))
    with pytest.raises(RuntimeError, match="taxonomy"):
        taxonomy.shelf_rel("quant-trading")
    with pytest.raises(RuntimeError, match="taxonomy"):
        _ = taxonomy.TYPES  # the lazy PEP 562 accessor loads on access too
