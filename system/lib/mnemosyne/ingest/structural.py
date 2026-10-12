"""Structural pre-pass (D125-B9) - the tree-sitter seam behind the StructuralExtractor port.

Realizes :class:`~mnemosyne.ports.structural.StructuralExtractor` in two layers, mirroring the store
adapters (D126):

* :class:`NullStructuralExtractor` - the in-memory stub (default): abstains (no fact), so the suite
  runs with tree-sitter NOT installed. It is the test double the seam is proven against.
* :class:`TreeSitterStructuralExtractor` - the real port impl: it speaks to a small injected
  ``backend`` in PRIMITIVES (a list of ``(capture_name, text)`` query captures), never to tree-sitter
  types, so the capture->triple TRANSLATION (the whole logic) is unit-tested against a light double
  WITHOUT the brick. The brick itself is wrapped by
  :class:`~mnemosyne.ingest.structural_treesitter._TreeSitterBackend` (the SOLE importer, D103),
  exercised by the 1-click smoke at ignition, not the unit suite.

The triples are a deterministic syntactic fact of the source (``foo defined_as function``), so they
carry no model doubt and are filed WITHOUT the LLM golden-set gate ((3)-3c) - but reach an answer ONLY
through a VALIDATED fiche (D100). Code & docstrings English (D117).

Decisions: D125-B9 (tree-sitter pre-pass)  -  D103 (sole importer)  -  D126 (decoupled by a primitive
seam)  -  D100 (validatable)  -  D84 (bi-temporal).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Protocol

from ..ports import Fact, NodeId

#: Query-capture name -> the ``(predicate, object)`` of the structural triple it yields. A capture the
#: map does not name is ignored (fail-safe: an unknown node never invents a fact). Extensible (D58
#: "plancher, pas plafond"): calls / inheritance / references are added here as the query grows.
_TRIPLE_BY_CAPTURE: dict[str, tuple[str, str]] = {
    "function.name": ("defined_as", "function"),
    "class.name": ("defined_as", "class"),
    "import.name": ("used_as", "import"),
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class NullStructuralExtractor:
    """The abstaining stub (default, D126): no language is parsed, so no structural fact is produced.

    The seam is wired, the brick is not installed - exactly the fail-safe posture of the ``Null``
    stand-ins the classifier / fact extractor use until (3) ignition."""

    def extract_structural(self, content: str, *, language: str) -> tuple[Fact, ...]:
        return ()


class StructuralBackend(Protocol):
    """The primitive tree-sitter surface (D126): run a structural query, return naked captures."""

    def captures(self, content: str, language: str) -> list[tuple[str, str]]:
        """Return ``(capture_name, matched_text)`` for each structural node in ``content``.

        An unsupported ``language`` returns an empty list (never a raise). No tree-sitter type
        crosses this boundary - only primitives - so the translation above is testable without the
        brick."""
        ...


class TreeSitterStructuralExtractor:
    """Real structural pre-pass behind :class:`~mnemosyne.ports.structural.StructuralExtractor`.

    Pure translation over an injected :class:`StructuralBackend`: each named capture becomes a
    deterministic bi-temporal :class:`Fact`. An unknown capture is dropped (a syntactic node the map
    does not name never invents a fact), and a backend that yields nothing yields no fact - never a
    raise (a broken parse must not break a capture, D108-(2))."""

    __slots__ = ("_backend",)

    def __init__(self, backend: StructuralBackend) -> None:
        self._backend = backend

    def extract_structural(self, content: str, *, language: str) -> tuple[Fact, ...]:
        at = _utcnow()
        facts: list[Fact] = []
        for capture_name, text in self._backend.captures(content, language):
            triple = _TRIPLE_BY_CAPTURE.get(capture_name)
            if triple is None or not text:
                continue  # unnamed capture, or empty match - no fact invented (fail-safe)
            predicate, obj = triple
            facts.append(Fact(NodeId(text), predicate, NodeId(obj), valid_from=at))
        return tuple(facts)
