"""Vision caption weaving (sujet 2) - turn Docling's ``<!-- image -->`` holes into marked, searchable text.

Docling emits an ``<!-- image -->`` placeholder for every figure it cannot read as text (D140). This module
holds the BRICK-FREE, deterministic core that fills those holes: given the extracted markdown and one caption
per figure (in document order), :func:`weave_captions` replaces the Nth placeholder with the Nth caption,
CLEARLY MARKED as model-generated so it is never confused with the author's verbatim (P3 / the
restructure-not-reformulate rule). An empty caption - the brick-free :class:`NullImageCaptioner`, or a VLM
that failed on that one figure - leaves the placeholder untouched (fail-open, no book lost, D85).

The real image bytes come from Docling (its sole importer, ``source_docling.py``, invariant 20); this module
never imports a brick, so the weave logic and the null stub are unit-tested with nothing installed (D126).
A captioner's output is model-generated and must be Guard-mediated by the caller (D100). Code & docstrings
English (D117); the inserted MARK is French - it lands in the operator's French ``.md`` (D117, output).

Decisions: D140 (.md-first living enrichment) - D43 (enriches Docling) - D100 (model output mediated) -
D126 (brick-free stub + testable core) - D85 (fail-open, placeholder stays).
"""

from __future__ import annotations

import os
import re
from collections.abc import Sequence
from typing import TYPE_CHECKING, Final

from ..provenance import FIGURE_CAPTION_MARK

if TYPE_CHECKING:
    from ..ports import ImageCaptioner

#: Docling's figure placeholder (mirrors :data:`~mnemosyne.ingest.library._HTML_COMMENT`'s target).
_IMAGE_PLACEHOLDER: Final = "<!-- image -->"

#: The visible French mark prefixing every model caption (:data:`~mnemosyne.provenance.FIGURE_CAPTION_MARK`,
#: the single source). It is no longer VISUAL only: :func:`~mnemosyne.production.keep_verbatim` now STRIPS a
#: marked line before the verbatim test (C2), so a model caption can never be promoted to the author's P3.


class NullImageCaptioner:
    """Brick-free stub captioner: describes nothing (D126), keeping the suite green with no VLM installed.

    Its empty caption makes :func:`weave_captions` leave every placeholder untouched, so the pipeline
    behaves EXACTLY as before the vision stage - the enrichment is purely additive and opt-in (the real
    MLX-VLM adapter is injected only at (3) ignition)."""

    model_id: Final = "null-captioner"

    def caption(self, image: bytes, *, context: str = "") -> str:  # noqa: ARG002 - stub ignores its input
        return ""


#: One woven figure enrichment: the visible provenance MARK + the one-line text to insert in a figure hole.
Enrichment = tuple[str, str]


def weave_enrichments(markdown: str, enrichments: Sequence[Enrichment | None]) -> str:
    """Replace each ``<!-- image -->`` placeholder with its enrichment (document order), clearly MARKED.

    The ONE insertion home (anti-drift, [[consolidate-crosscutting-rules]]): the Nth placeholder becomes the
    Nth enrichment ``(mark, text)`` as a one-line blockquote ``> {mark} {text}``, or stays a hole when the
    entry is ``None`` or its text is empty (fail-open, D85). Extra placeholders beyond ``enrichments`` stay
    untouched; extra entries are ignored. BOTH figure paths flow through here - the vision VLM caption
    (:data:`~mnemosyne.provenance.FIGURE_CAPTION_MARK`, sujet 2) and the vector-figure read-out
    (:data:`~mnemosyne.provenance.FIGURE_DATA_MARK`, sujet E) - so the collapse-to-one-line rule serves both,
    and the verbatim floor strips either mark (C2/E). Pure and deterministic (brick-free, D126)."""
    entries = iter(enrichments)

    def _replace(_match: re.Match[str]) -> str:
        entry = next(entries, None)
        if not entry:
            return _IMAGE_PLACEHOLDER  # fail-open: no enrichment => the hole simply stays a hole
        mark, text = entry
        one_line = " ".join(
            text.split()
        )  # collapse newlines so the mark stays attached to its text
        if not one_line or not mark:
            return _IMAGE_PLACEHOLDER  # empty text (a per-figure failure) => the hole stays (D85)
        return f"> {mark} {one_line}"

    return re.sub(re.escape(_IMAGE_PLACEHOLDER), _replace, markdown)


def count_image_holes(markdown: str) -> int:
    """Count the ``<!-- image -->`` figure placeholders in ``markdown`` (sujet F alignment + diagnostic).

    The ONE place that knows the placeholder string besides :func:`weave_enrichments`, so the incremental
    enricher and its stats agree with the weave on what a 'hole' IS (anti-drift,
    [[consolidate-crosscutting-rules]]). Pure and brick-free (D126)."""
    return markdown.count(_IMAGE_PLACEHOLDER)


#: A VLM caption shorter than this many words / non-space characters is DEGENERATE - the local 7B's failure
#: mode on an abstract chart (it emits "La", "La cour", "Cette figure") then stops. Generous enough to keep a
#: genuine short caption ("Un histogramme des rendements mensuels" = 6 words / 39 chars). Tuned from the pilots.
_MIN_CAPTION_WORDS: Final = 5
_MIN_CAPTION_CHARS: Final = 25


def is_degenerate_caption(text: str) -> bool:
    """Whether a VLM caption FIZZLED - too short/truncated to carry meaning (sujet F, the 7B failure mode).

    On an ABSTRACT chart (a price curve, a scatter bitmap) the local 7B often emits a broken sentence start
    ("La", "La cour", "Cette figure") then stops. That is NOISE in the ``.md`` / RAG - strictly WORSE than a
    hole - so the figure router treats a degenerate caption as a FAILURE: it fails open to a hole (D85), or
    falls through to the frontier captioner (niveau 3). Degenerate iff fewer than :data:`_MIN_CAPTION_WORDS`
    words OR fewer than :data:`_MIN_CAPTION_CHARS` non-space characters. Pure and brick-free (D126)."""
    stripped = text.strip()
    return len(stripped) < _MIN_CAPTION_CHARS or len(stripped.split()) < _MIN_CAPTION_WORDS


def weave_captions(markdown: str, captions: Sequence[str]) -> str:
    """Replace each ``<!-- image -->`` with its VISION caption, clearly MARKED (sujet 2).

    A thin wrapper over :func:`weave_enrichments`: each non-empty caption becomes a
    :data:`~mnemosyne.provenance.FIGURE_CAPTION_MARK` enrichment; an empty caption (the stub, or a per-figure
    VLM failure) leaves the placeholder in place (fail-open, D85). Extra placeholders stay untouched, extra
    captions are ignored. Kept as the sujet-2 seam so its callers and tests are unchanged; the anti-drift,
    collapse-to-one-line logic lives in the one home. Pure and deterministic (brick-free, D126)."""
    return weave_enrichments(
        markdown, [(FIGURE_CAPTION_MARK, c) if c and c.strip() else None for c in captions]
    )


#: Opt-in switch for the vision stage in REAL ingestion. The operator sets it for a run (``MNEMOSYNE_VISION=1 ...``);
#: unset (default) => ingestion behaves EXACTLY as before the vision stage - zero regression.
_VISION_ENV_VAR: Final = "MNEMOSYNE_VISION"


def vision_captioner_if_enabled() -> ImageCaptioner | None:
    """The SINGLE opt-in switch for the vision stage in PRODUCTION (``real_runtime`` and ``library_run`` both
    call it - anti-drift, one place decides): return a LIVE local captioner iff :data:`_VISION_ENV_VAR` is
    set, else ``None`` so ``connect_docling(captioner=None)`` is exactly the pre-vision default (zero
    regression, D126). OFF by default because captioning is LOCAL but SLOW (one VLM inference per BODY figure)
    and needs the mlx-vlm brick - the operator turns it on for a run when they want figures enriched (invariant 1 / D66
    local, D85 fail-open per figure). The brick imports LAZILY, only when the switch is ON, so an ingestion
    with the switch OFF never touches mlx-vlm (the brick-free suite stays green)."""
    if not os.environ.get(_VISION_ENV_VAR):
        return None
    from .caption_mlx import connect_mlx_vlm  # lazy brick import - only when the switch is ON

    return connect_mlx_vlm()
