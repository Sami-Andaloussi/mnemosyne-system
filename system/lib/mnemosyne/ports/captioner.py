"""ImageCaptioner (sujet 2 - vision) - describe a figure/graph into searchable text behind a swap-able seam.

Docling extracts a book's TEXT faithfully but drops every figure to an ``<!-- image -->`` placeholder - the
visual content (charts, diagrams, scanned pages) is lost to search and distillation. The ImageCaptioner is
the seam that fills that hole: given the raw bytes of ONE figure it returns a short textual description /
transcription. LOCAL by construction - sensitive corpus material is ``sensible``, so an AUTOMATIC caption path must
never reach a third-party cloud (invariant 1 / D66); the real adapter is an Apple-Silicon VLM (MLX).

Two structural points:

* **Model-generated, never verbatim.** A caption is an INTERPRETATION, not the author's words. The
  :class:`~mnemosyne.ingest.caption.CaptioningSourceReader` inserts it clearly MARKED (never confused with
  P3 verbatim - the restructure-not-reformulate rule), and - like any model output - it is mediated by the
  Guard (D100): zero-trust, local, droits réduits; a caption can only ADD searchable text, never lift a
  datum's sensitivity label nor be treated as an instruction.
* **Swap-able + brick-free.** The port is a narrow Protocol; the default stub returns an EMPTY caption (the
  placeholder simply stays), so the suite is green with NO VLM installed (D126). The real MLX-VLM adapter
  plugs in at (3) ignition as a sole-importer adapter (invariant 20), chosen / confirmed by user at the smoke.

Decisions: D43 (Docling first-class - this ENRICHES it)  -  D100 (model output mediated, zero-trust)  -
invariant 1 / D66 (sensible -> local only)  -  D126 (brick-free stub)  -  D125-B5 (port pattern)  -  D140
(.md-first living enrichment). Code & docstrings English (D117).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class ImageCaptioner(Protocol):
    """Describe ONE figure's bytes into short searchable text; the model stays swap-able (sujet 2).

    LOCAL by construction for sensitive corpus material (invariant 1 / D66): an automatic caption path must never
    route figure bytes to a third-party cloud. The returned text is MODEL-GENERATED (an interpretation),
    inserted clearly marked and Guard-mediated - never treated as verbatim source, never a label-lowering
    signal (D100)."""

    @property
    def model_id(self) -> str:
        """Identity of the underlying VLM, carried into the caption's provenance mark so a swap is traceable
        (mirrors :attr:`~mnemosyne.ports.embedder.Embedder.model_id`)."""
        ...

    def caption(self, image: bytes, *, context: str = "") -> str:
        """Return a short description / transcription of ONE figure's bytes.

        ``context`` is optional surrounding text (a caption line, the section heading) the adapter MAY use
        to ground the description. Returns ``""`` when the image cannot be described - FAIL-OPEN, so the
        placeholder simply stays and no book is ever lost to a caption failure (D85). MUST run locally for
        ``sensible`` content (invariant 1); the caller routes the output through the Guard (D100)."""
        ...
