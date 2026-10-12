"""Split source text into deterministic retrieval chunks."""

from __future__ import annotations

import re
from dataclasses import dataclass

#: Coarsest->finest boundaries. Markdown structure first (a blank line is a block), then
#: line, sentence, word, and a hard character slice as the last resort (a very long token).
_SEPARATORS: tuple[str, ...] = ("\n\n", "\n", ". ", " ", "")

#: Defaults, in characters. ~1500 sits well under bge-m3's window so a passage is never
#: truncated; 200 chars of overlap keep continuity across a boundary.
_TARGET = 1500
_OVERLAP = 200


@dataclass(frozen=True, slots=True)
class Passage:
    """One passage of a document - its ordinal position and its text (D135)."""

    ordinal: int
    text: str


def chunk_text(text: str, *, target: int = _TARGET, overlap: int = _OVERLAP) -> list[Passage]:
    """Split ``text`` into overlapping passages, coarsest boundary first (D135).

    Empty / whitespace-only text yields no passage (nothing to retrieve - honest, and
    ``VectorIndex.contains`` stays False for an empty doc). Deterministic: the same input
    yields the same passages (invariant 24). Each passage is ≤ ``target`` + ``overlap`` chars so
    the encoder never truncates one; ``overlap`` chars of the previous passage's tail head the
    next."""
    if not text.strip():
        return []
    if not 0 <= overlap < target:
        raise ValueError(f"overlap {overlap} must be in [0, target={target})")
    atoms = _split(text, _SEPARATORS, target)
    windows = _pack(atoms, target=target, overlap=overlap)
    return [Passage(ordinal=i, text=window) for i, window in enumerate(windows)]


def _split(text: str, separators: tuple[str, ...], target: int) -> list[str]:
    """Recursively break ``text`` into atoms each ≤ ``target`` chars, on the coarsest
    separator that helps; the empty separator is a hard character slice (last resort,
    for a single token longer than ``target``). Loss-less: separators are kept."""
    if len(text) <= target:
        return [text] if text else []
    separator, *rest = separators
    if separator == "":  # hard cut - a single unbreakable token longer than target
        return [text[i : i + target] for i in range(0, len(text), target)]
    parts = text.split(separator)
    atoms: list[str] = []
    for index, part in enumerate(parts):
        piece = part + separator if index < len(parts) - 1 else part  # re-attach the separator
        if not piece:
            continue
        if len(piece) <= target:
            atoms.append(piece)
        else:
            atoms.extend(_split(piece, tuple(rest), target))
    return atoms


def _pack(atoms: list[str], *, target: int, overlap: int) -> list[str]:
    """Greedily merge adjacent atoms up to ``target`` chars, carrying ``overlap`` chars of
    the previous window's tail into the next one (context continuity across a boundary)."""
    windows: list[str] = []
    current = ""
    for atom in atoms:
        if current and len(current) + len(atom) > target:
            windows.append(current)
            current = (current[-overlap:] if overlap else "") + atom
        else:
            current += atom
    if current.strip():
        windows.append(current)
    return windows


#: Word tokens for the lexical fallback (same grain as the keyword leg, ``stores/keyword.py``).
_WORD = re.compile(r"\w+", re.UNICODE)


def select_passage(text: str, query: str, *, ordinal: int | None = None) -> str:
    """Resolve ONE passage of ``text`` for a recall hit (D136) - what a model may read, never the
    whole document.

    ``ordinal`` (the dense index's matched passage, carried on
    :class:`~mnemosyne.ports.vectorindex.SearchHit`) selects that passage directly. When it is
    ``None`` - a keyword-only hit has no passage granularity - or out of range, the passage with the
    best lexical overlap with ``query`` is chosen (mirroring the keyword leg's own term signal, ties
    -> earliest). Deterministic and brick-free (D126): re-chunking ``text`` with the SAME defaults
    reproduces the passages the index was built from, so ``ordinal`` aligns. Empty / whitespace
    ``text`` => returned unchanged (nothing to pack). This is why the fail-closed runner bound (D136)
    is never hit on the normal recall path: a passage is ≤ ``target`` + ``overlap`` chars, far under
    the ceiling, so packing top-k passages stays small."""
    passages = chunk_text(text)
    if not passages:
        return text
    if ordinal is not None and 0 <= ordinal < len(passages):
        return passages[ordinal].text
    return _best_by_terms(passages, query).text


def _best_by_terms(passages: list[Passage], query: str) -> Passage:
    """The passage matching the most DISTINCT query terms (lexical overlap; ties -> earliest ordinal).

    A model-free, deterministic fallback for a hit with no trusted passage ordinal (a lexical-leg
    admission): it counts how many DISTINCT query terms a passage contains - NOT their raw frequency
    - so a boilerplate passage repeating one common term many times cannot outrank a passage that
    actually covers the query (audit M-1b). Stop-words appear in every passage and so contribute
    uniformly, self-cancelling without a language-specific list (kept brick-free, multilingual). It
    is a lexical overlap signal, close in spirit to the keyword leg but NOT its exact score (the real
    leg is BM25 / IDF-weighted, F3). ``max`` is stable => the earliest ordinal wins a tie (an empty
    query keeps the first passage)."""
    terms = {m.group(0) for m in _WORD.finditer(query.lower())}
    if not terms:
        return passages[0]

    def distinct_overlap(passage: Passage) -> int:
        tokens = {m.group(0) for m in _WORD.finditer(passage.text.lower())}
        return sum(1 for term in terms if term in tokens)

    return max(passages, key=distinct_overlap)
