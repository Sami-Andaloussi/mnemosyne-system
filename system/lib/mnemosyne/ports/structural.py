"""StructuralExtractor (D125-B9 / D100) - deterministic structural facts, behind a swap-able seam.

A *pre-pass* to the living-memory graph: parse code with **tree-sitter** (a deterministic parser,
no model) into structural triples - ``foo defined_as function``, ``os used_as import`` - UPSTREAM of
and complementing the LLM fact extractor (D103). Two properties matter:

* **Deterministic** - the triples are a syntactic fact of the source, not a model opinion, so they
  carry no hallucination risk; they are filed WITHOUT the golden-set trust gate the LLM extractor
  needs ((3)-3c). Like every fact they still reach an answer ONLY through a VALIDATED fiche (D100).
* **Encapsulated** (invariant 20 / D103) - the rest of Mnémosyne speaks ONLY to this port; no module
  imports tree-sitter outside the single adapter (:mod:`~mnemosyne.ingest.structural_treesitter`).

The pre-pass fires only when the caller DECLARES a source ``language`` (code ingestion), so generic
text capture never runs it. Default brick: **tree-sitter** (MIT); the in-memory stub
(:class:`~mnemosyne.ingest.structural.NullStructuralExtractor`) abstains, so the suite runs with
nothing installed (D126). Code & docstrings English (D117).

Decisions: D125-B9 (tree-sitter pre-pass)  -  D103 (adoption, sole importer)  -  D100 (extraction in the
loop, validatable)  -  D55 / D84 (bi-temporal facts).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from .graphstore import Fact


@runtime_checkable
class StructuralExtractor(Protocol):
    """The sole interface to the deterministic structural pre-pass (invariant 20)."""

    def extract_structural(self, content: str, *, language: str) -> tuple[Fact, ...]:
        """Parse ``content`` (source in ``language``) into deterministic structural facts.

        Returns bi-temporal :class:`Fact` triples (``valid_from`` = now). An unsupported language,
        or content that yields no structural node, returns an empty tuple - never a raise (a broken
        parse must never break a capture, D108-(2)). The facts are NAKED; the caller envelopes them
        with the content's label (raise-only: a syntactic fact can never declassify)."""
        ...
