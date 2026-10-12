"""(3)-5b live - the tantivy query sanitizer, proven brick-free (D68 / D126).

The lexical leg's ``parse_query`` reads a query as SYNTAX (operators ``/ : ( ) " ~ *`` ...), so a real
natural-language question raised a ``Syntax Error`` at the first agentic live. :func:`_sanitize_query`
reduces a query to plain terms; it is pure stdlib, so it is tested with tantivy NOT installed (D126).
"""

from __future__ import annotations

from mnemosyne.stores.keyword_tantivy import _sanitize_query


def test_sanitize_query_strips_tantivy_operators() -> None:
    # the exact live failure: a French question with '/', ':', '(', "'" broke parse_query.
    out = _sanitize_query("principes de gestion / ML: retrieval, l'incertitude (seuils)")
    for op in "/:()'":
        assert op not in out
    assert "retrieval" in out and "incertitude" in out and "seuils" in out


def test_sanitize_query_keeps_accented_letters() -> None:
    # Unicode letters (accents) are alphanumeric - kept, so French terms still match the index.
    assert "critère" in _sanitize_query("critère de Kelly")


def test_sanitize_query_lowercases_and_collapses_whitespace() -> None:
    assert _sanitize_query("  Kelly   CRITERION  ") == "kelly criterion"


def test_sanitize_query_empty_when_only_punctuation() -> None:
    # a query of only operators reduces to nothing - the caller then skips the lexical leg (dense carries).
    assert _sanitize_query("/// :: () ~*") == ""
