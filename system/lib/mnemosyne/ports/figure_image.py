"""FigureImageSink (arc D) — where a figure's OWN pixels are written, so the ``.md`` can point at them.

The operator's verdict on the enrichment that shipped before this port: *"we're working with image
descriptions, that's ridiculous"*. He is right, and the measurement showed the fix was already half-built: the
figure-enrichment chain ALREADY renders every figure to PNG bytes in memory
(``picture.get_image(doc)`` → ``image.save(buffer, format="PNG")`` in
:mod:`~mnemosyne.ingest.source_docling`), hands them to a model to obtain *words*, and then lets the buffer
die. Nothing in the whole library wrote an image to disk — measured: zero image files under ``knowledge/``.

This port is the missing half-line: a SINK that takes those bytes and returns the link the markdown should
carry. Keeping it a port (not a bare ``open()``) buys the two things the campaign needs: the brick-free
suite can drive the enricher with an in-memory fake (D126), and the real writer's policy — where assets
live, how they are named, what happens on an IO error — lives in ONE place
(:mod:`~mnemosyne.ingest.figure_image`) instead of being smeared through the Docling adapter.

FAIL-OPEN by contract (D85): a sink that cannot write returns ``""`` and the figure degrades to the
existing text read-out (or stays a hole) — a full disk must never abort a 244-book campaign. Code &
docstrings English (D117).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class FigureImageSink(Protocol):
    """Persist ONE figure's PNG bytes and return how the markdown should link to it.

    ``ordinal`` is the figure's 0-based index in the document's BODY-figure order — the SAME ordinal the
    hole splice uses (:func:`~mnemosyne.ingest.caption.weave_enrichments`), so an asset's name is a
    verifiable claim about which hole it fills, not a counter that drifts.

    Returns a markdown link TARGET (relative to the ``.md``), or ``""`` when nothing was written — the
    caller then falls back to the text paths (fail-open, D85). Implementations MUST be idempotent: the same
    ``(ordinal, png)`` written twice leaves one file, so a re-run of the campaign never duplicates assets."""

    def save(self, ordinal: int, png: bytes) -> str: ...
