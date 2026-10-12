"""Library taxonomy (D140 / Étape 3) - the ONE source of the shelf mapping, read from the zone.

The reference library lives on a HIERARCHICAL shelf,
``knowledge/raw/<Family>/<Group>/<domain>/<type>/`` (``distilled/`` mirrors it). The ``<domain>``
stays the fine RAG tag; ``<Family>`` / ``<Group>`` are only navigation layers; ``<type>`` in
{books, web, youtube, chats} is ALWAYS the file's direct parent. So the domain is derived - robustly to
family/group depth and to the ``information-retrieval`` nested case - as the folder JUST ABOVE the first
``<type>`` segment, never the pre-taxonomy ``parts[0]`` (which is now the top FAMILY, not the domain).

This module loads ``system/config/taxonomy.toml`` (the graven source of truth) and is the SOLE home of
that mapping in the code: :mod:`.library` (domain derivation on READ) and :mod:`.triage` (where to shelve
a new book on WRITE) both call in here - neither recopies the mapping, so adding a domain stays a one-line
edit to the toml (single source, [[contract-single-source-emit]]).

Loading is LAZY: the toml is read and cached on the FIRST real use of the map (:func:`family_group` /
:func:`shelf_rel` / :func:`domain_from_parts` / the ``TYPES`` / ``DEFAULT_TYPE`` accessors), NOT at import.
So merely importing any :mod:`~mnemosyne.ingest` module (``benne``, ``classifier`` ..., which pull this one
in transitively) never touches the file - only code that actually derives or shelves a domain depends on
it, and a missing / malformed toml fails THERE, loudly and explicitly, instead of breaking unrelated
imports. Read by the standard-library ``tomllib`` - no dependency, so it holds before the toolchain lands
(D116). The toml path is resolved from THIS module's home, never the CWD, so it is correct whatever
directory the process runs from. Code & docstrings English (D117); the shelf / domain / type tokens stay
as they are graven in the toml.
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Final

#: The taxonomy zone: ``<repo>/system/config/taxonomy.toml``, resolved from this module's home
#: (``system/lib/mnemosyne/ingest/taxonomy.py`` -> ``parents[3]`` is ``system``), NOT the CWD.
_TAXONOMY_PATH: Final[Path] = Path(__file__).resolve().parents[3] / "config" / "taxonomy.toml"

#: Shelf FAMILIES whose content is personal / intimate (D149) - the SINGLE source of "which family is
#: private". A source under one of these is protected on BOTH axes: it is never sent to a frontier model at
#: egress (:data:`distill_campaign._EXCLUDED_FAMILIES` points here) AND its distilled fiche is labelled
#: ``sensible`` rather than ``public`` whatever its published type (``distill_book._book_sensitivity``). One
#: home so egress-protection and label-protection can never drift apart. Hardcoded (not in the toml) so a
#: mis-edit of the shelf config can never silently declassify intimate content.
PERSONAL_FAMILIES: Final[frozenset[str]] = frozenset({"General"})

# Lazy caches - populated on first use by :func:`_ensure_loaded`, never at import (see module docstring).
_TYPES: frozenset[str] | None = None
_DEFAULT_TYPE: str | None = None
_FAMILY_GROUP: dict[str, tuple[str, str]] | None = (
    None  # domain -> (Family, Group); the only copy
)


def _ensure_loaded() -> None:
    """Read + cache the taxonomy on first use; a no-op once cached. A missing / unreadable file raises a
    RuntimeError naming the expected path (explicit, never a silent empty map that would mis-shelve)."""
    global _TYPES, _DEFAULT_TYPE, _FAMILY_GROUP
    if _FAMILY_GROUP is not None:
        return
    try:
        text = _TAXONOMY_PATH.read_text(encoding="utf-8")
    except OSError as exc:
        raise RuntimeError(
            f"library taxonomy unreadable at {_TAXONOMY_PATH} - the shelf mapping "
            "(system/config/taxonomy.toml) is required to derive or shelve a domain"
        ) from exc
    data = tomllib.loads(text)
    types_raw = data.get("types", {})
    _TYPES = frozenset(str(t) for t in types_raw.get("allowed", ()))
    _DEFAULT_TYPE = str(types_raw.get("default", "books"))
    _FAMILY_GROUP = {
        str(domain): (str(pair[0]), str(pair[1]))
        for domain, pair in data.get("domains", {}).items()
    }


def family_group(domain: str) -> tuple[str, str] | None:
    """The ``(Family, Group)`` navigation layers for ``domain``, or ``None`` if it is not mapped."""
    _ensure_loaded()
    assert _FAMILY_GROUP is not None  # set by _ensure_loaded
    return _FAMILY_GROUP.get(domain)


def all_domains() -> frozenset[str]:
    """Every domain the taxonomy maps - the full shelf-tag set, read from the single source. Used by the
    domain lifecycle (D46) to stay idempotent (skip a domain already mapped)."""
    _ensure_loaded()
    assert _FAMILY_GROUP is not None  # set by _ensure_loaded
    return frozenset(_FAMILY_GROUP)


def shelf_rel(domain: str, type_: str | None = None) -> Path | None:
    """The shelf path RELATIVE to the raw/distilled root for ``domain``: ``<Fam>/<Grp>/<domain>/<type>``.

    ``None`` for a domain OUTSIDE the taxonomy - the caller decides where an unmapped source goes
    (:mod:`.triage` routes it to the ``_intake`` sas rather than guess a shelf, D85). ``type_`` defaults
    to :data:`DEFAULT_TYPE` (resolved lazily, so the default is not evaluated at import); it is a pure
    mapping helper, so the type is not re-validated against :data:`TYPES` here (a caller shelving a new
    book always passes an allowed type)."""
    _ensure_loaded()
    assert _FAMILY_GROUP is not None and _DEFAULT_TYPE is not None  # set by _ensure_loaded
    fg = _FAMILY_GROUP.get(domain)
    if fg is None:
        return None
    fam, grp = fg
    return Path(fam) / grp / domain / (type_ if type_ is not None else _DEFAULT_TYPE)


def domain_from_parts(parts: tuple[str, ...]) -> str | None:
    """Derive the shelf domain from a raw-relative path's ``parts`` - the segment JUST ABOVE the first
    ``<type>`` segment, robust to family/group depth and to the ``information-retrieval`` nested case.

    ``None`` when NO ``<type>`` segment is present (the path is not a shelved book - a stray under the raw
    root, or a README beside a domain), so the caller treats it as unshelved rather than mis-tagging on
    the top family folder. A ``<type>`` at position 0 also yields ``None`` (no domain segment precedes it,
    never a negative-index wraparound). The FIRST ``<type>`` wins, so a deeper folder that happens to
    share a type name can never shadow the real domain."""
    _ensure_loaded()
    assert _TYPES is not None  # set by _ensure_loaded
    for i, seg in enumerate(parts):
        if seg in _TYPES:
            return parts[i - 1] if i >= 1 else None
    return None


def __getattr__(name: str) -> object:
    """PEP 562 lazy module attributes: ``taxonomy.TYPES`` / ``taxonomy.DEFAULT_TYPE`` load the toml on
    first access rather than at import, so consuming them as constants stays as cheap-looking as before
    while keeping import free of the file dependency."""
    if name == "TYPES":
        _ensure_loaded()
        return _TYPES
    if name == "DEFAULT_TYPE":
        _ensure_loaded()
        return _DEFAULT_TYPE
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
