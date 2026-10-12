"""Frontmatter schema + validator (D33 / D121-C2) - the P1 identity-card contract, in code.

Exercises :mod:`mnemosyne.production.frontmatter`: a complete card passes; a missing required
field surfaces as its own NAMED error; absent optional fields are tolerated (D33 §optionnels); a
wrong type (scalar or inside a list) is rejected; the two closed value sets ``sensitivity``
(reused from :class:`~mnemosyne.ports.Sensitivity`, never hand-copied) and ``lang`` are enforced;
a present-but-blank REQUIRED value is rejected same as an absent one. Additive only - this suite
does not touch, and does not assert anything about, the current (narrower) real emitters in
``system/skills/distillateur/distill_book.py`` or :mod:`mnemosyne.production.distillation`. Code
& docstrings English (D117); the frontmatter tokens stay French where D33 fixed them
(``perso`` / ``sensible``).
"""

from __future__ import annotations

from mnemosyne.ports import Sensitivity
from mnemosyne.production import (
    FIELDS_BY_NAME,
    FRONTMATTER_FIELDS,
    OPTIONAL_FIELD_NAMES,
    REQUIRED_FIELD_NAMES,
    SENSITIVITY_TOKENS,
    validate_frontmatter,
)

# A complete, correctly-typed P1 card - every field D33 / D121-C2 names, required AND optional.
_COMPLETE: dict[str, object] = {
    "title": "A Non-Random Walk Down Wall Street",
    "source": "Andrew W. Lo & A. Craig MacKinlay",
    "lang": "en",
    "domain": ["quant", "finance"],
    "format": "book",
    "content_type": "theorie",
    "sensitivity": "perso",
    "status": "distille",
    "id": "a1b2c3d4",
    "ingested_at": "2026-07-15T10:00:00Z",
    "source_path": "knowledge/raw/quant/non-random-walk.md",
    "template": "book-generic-v1",
    "origin_date": "1999",
    "tags": ["random-walk", "efficient-markets"],
    "version": "1",
    "read_status": "lu",
}


def _without(*names: str) -> dict[str, object]:
    """A copy of :data:`_COMPLETE` with ``names`` removed - for missing/absent-field tests."""
    return {k: v for k, v in _COMPLETE.items() if k not in names}


# --------------------------------------------------------------------------- #
# Schema shape - sanity on the field count / split (12 required + 4 optional) #
# --------------------------------------------------------------------------- #
def test_schema_has_16_fields_split_12_required_4_optional() -> None:
    assert len(FRONTMATTER_FIELDS) == 16
    assert len(REQUIRED_FIELD_NAMES) == 12
    assert len(OPTIONAL_FIELD_NAMES) == 4
    assert REQUIRED_FIELD_NAMES.isdisjoint(OPTIONAL_FIELD_NAMES)
    assert REQUIRED_FIELD_NAMES | OPTIONAL_FIELD_NAMES == set(FIELDS_BY_NAME)
    # the fixture above is itself a genuine, complete instance of the schema (no drift between
    # the test data and the schema this module ships)
    assert set(_COMPLETE) == set(FIELDS_BY_NAME)


def test_sensitivity_tokens_reuse_the_engine_enum_not_a_hand_copy() -> None:
    # Single source of truth (D66 / D101) - frontmatter.py must not hand-maintain a second list.
    assert set(SENSITIVITY_TOKENS) == {s.token for s in Sensitivity}
    assert set(SENSITIVITY_TOKENS) == {"public", "perso", "sensible"}


# --------------------------------------------------------------------------- #
# The 4 asked-for behaviours                                                   #
# --------------------------------------------------------------------------- #
def test_a_complete_valid_frontmatter_passes() -> None:
    result = validate_frontmatter(_COMPLETE)
    assert result.ok is True
    assert result.errors == ()


def test_a_missing_required_field_fails_with_the_named_error() -> None:
    result = validate_frontmatter(_without("title"))
    assert result.ok is False
    matches = [e for e in result.errors if e.field == "title" and e.code == "missing"]
    assert len(matches) == 1, result.errors


def test_every_required_field_is_individually_load_bearing() -> None:
    # Drop each required field ONE at a time - each must surface as its OWN named "missing" error,
    # and dropping it must not spuriously flag any other field.
    for name in REQUIRED_FIELD_NAMES:
        result = validate_frontmatter(_without(name))
        assert result.ok is False, f"dropping {name!r} should invalidate the card"
        missing = {e.field for e in result.errors if e.code == "missing"}
        assert missing == {name}, f"dropping {name!r} reported missing={missing}"


def test_absent_optional_fields_are_tolerated() -> None:
    required_only = _without(*OPTIONAL_FIELD_NAMES)
    result = validate_frontmatter(required_only)
    assert result.ok is True
    assert result.errors == ()


def test_a_wrong_list_type_is_rejected() -> None:
    bad = dict(
        _COMPLETE, domain="quant"
    )  # a bare string, not a list - the classic frontmatter typo
    result = validate_frontmatter(bad)
    assert result.ok is False
    assert any(e.field == "domain" and e.code == "wrong_type" for e in result.errors)


def test_a_wrong_scalar_type_is_rejected() -> None:
    bad = dict(_COMPLETE, title=42)
    result = validate_frontmatter(bad)
    assert result.ok is False
    assert any(e.field == "title" and e.code == "wrong_type" for e in result.errors)


def test_a_wrong_item_type_inside_a_list_is_rejected() -> None:
    bad = dict(_COMPLETE, domain=["quant", 7])
    result = validate_frontmatter(bad)
    assert result.ok is False
    assert any(e.field == "domain" and e.code == "wrong_type" for e in result.errors)


# --------------------------------------------------------------------------- #
# Closed value sets - enforced ONLY where D33 / D121-C2 actually pin one      #
# --------------------------------------------------------------------------- #
def test_sensitivity_accepts_all_3_closed_tokens() -> None:
    for token in ("public", "perso", "sensible"):
        result = validate_frontmatter(dict(_COMPLETE, sensitivity=token))
        assert result.ok is True, f"{token!r} should be a valid sensitivity ({result.errors})"


def test_sensitivity_rejects_an_unknown_token() -> None:
    result = validate_frontmatter(dict(_COMPLETE, sensitivity="confidentiel"))
    assert result.ok is False
    assert any(e.field == "sensitivity" and e.code == "invalid_value" for e in result.errors)


def test_lang_rejects_an_unknown_token() -> None:
    result = validate_frontmatter(dict(_COMPLETE, lang="fr-FR"))
    assert result.ok is False
    assert any(e.field == "lang" and e.code == "invalid_value" for e in result.errors)


# --------------------------------------------------------------------------- #
# Required emptiness - a present-but-blank required value is as bad as absent #
# --------------------------------------------------------------------------- #
def test_a_blank_required_string_is_rejected() -> None:
    result = validate_frontmatter(dict(_COMPLETE, title="   "))
    assert result.ok is False
    assert any(e.field == "title" and e.code == "empty_value" for e in result.errors)


def test_an_empty_required_list_is_rejected() -> None:
    result = validate_frontmatter(dict(_COMPLETE, domain=[]))
    assert result.ok is False
    assert any(e.field == "domain" and e.code == "empty_value" for e in result.errors)


def test_a_blank_string_inside_a_required_list_is_rejected() -> None:
    # `domain=["quant", "  "]` is a hole hiding in a non-empty list: a blank element would mis-tag
    # the fiche just as `[]` would, so a REQUIRED multi rejects it (an optional multi stays lenient).
    result = validate_frontmatter(dict(_COMPLETE, domain=["quant", "  "]))
    assert result.ok is False
    assert any(e.field == "domain" and e.code == "empty_value" for e in result.errors)


def test_an_empty_optional_list_is_tolerated() -> None:
    # tags is optional and its documented default is an empty list (D33: bonus libre).
    result = validate_frontmatter(dict(_COMPLETE, tags=[]))
    assert result.ok is True


def test_an_unknown_extra_key_is_ignored() -> None:
    # This module checks the D33/D121-C2 contract, not whether a real (legacy-named) fiche has
    # extra keys - see the module docstring's scope note.
    result = validate_frontmatter(dict(_COMPLETE, distilled_by="distillateur/0.1.0"))
    assert result.ok is True
