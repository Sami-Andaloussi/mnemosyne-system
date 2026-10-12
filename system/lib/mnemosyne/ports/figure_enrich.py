"""Port contract for enriching extracted figures."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from .figure_image import FigureImageSink


@dataclass(frozen=True, slots=True)
class FigureEnrichStats:
    """One book's enrichment tally - the raw material of user's local-first DIAGNOSTIC (F7).

    ``holes`` is the ``<!-- image -->`` count in the existing ``.md``; ``body_pictures`` is the number of
    BODY figures Docling found in the PDF (the count the ordinal splice aligns against). ``aligned`` is
    ``holes == body_pictures`` - only then is anything spliced. The filled holes split by WHICH path
    succeeded: ``filled_image`` (arc D - the figure's OWN pixels, kept as a ``.png`` the markdown links; no
    model, no description, so it outranks the rest), then the description paths cheapest-first,
    ``filled_vector`` (exact vector extraction, sujet E), ``filled_vlm`` (the LOCAL VLM guess, sujet 2),
    ``filled_cloud`` (the FRONTIER captioner, sujet G / niveau 3 - a Guard-mediated egress, counted apart so
    user sees exactly how many holes NEEDED the cloud and weighs its cost). ``remaining_holes`` is what NONE
    of them filled - the true hard remainder."""

    holes: int
    body_pictures: int
    aligned: bool
    filled_vector: int = 0
    filled_vlm: int = 0
    filled_cloud: int = 0
    filled_image: int = 0
    remaining_holes: int = 0
    #: THE BYTES THE SINK HAS ALREADY WRITTEN TO DISK, ALIGNED OR NOT (E1, YYYY-MM-DD).
    #: `aligned=False` means "nothing was WOVEN" - and it used to read as "nothing happened".
    # Deployment-specific measurement omitted; the behavior is covered by tests.
    #: (83 + 73 + 35), because the ADAPTER writes the pixels while producing the enrichments
    #: while the PURE CORE then decides not to weave anything. The residue is therefore
    #: counted HERE and published, or else a refusal stays silent about what it left behind.
    assets_written: int = 0

    @property
    def filled(self) -> int:
        """Holes filled by ANY path this pass (the image itself + local vector + local VLM + frontier)."""
        return self.filled_image + self.filled_vector + self.filled_vlm + self.filled_cloud


@dataclass(frozen=True, slots=True)
class FigureEnrichOutcome:
    """The result of enriching ONE ``.md``: the (possibly) spliced markdown + its stats + whether it changed.

    ``markdown`` equals the input byte-for-byte when nothing was spliced (misaligned, or every figure
    fail-open); ``changed`` is the cheap signal the campaign uses to decide whether to rewrite the file (and
    back it up first, non-destructively)."""

    markdown: str
    stats: FigureEnrichStats
    changed: bool


@runtime_checkable
class FigureEnricher(Protocol):
    """Fill an existing ``.md``'s figure holes from its PDF bytes, in document order (sujet F).

    Bound to nothing - each call is one book. LOCAL by default (invariant 1): it re-reads figures already in
    the PDF and, at most, runs a local VLM. A niveau-3 FRONTIER captioner (sujet G) is optional and, when
    wired, egresses each figure ONLY through the Guard under a canal-B human gesture (D90) - never automatic,
    never a bypass of invariant 1. The adapter is the sole Docling importer; a fake implements this in the
    brick-free suite (D126)."""

    def enrich_markdown(
        self, existing_md: str, pdf: bytes, *, assets: FigureImageSink | None = None
    ) -> FigureEnrichOutcome:
        """Return ``existing_md`` with its ``<!-- image -->`` holes spliced from the PDF's figures, + stats.

        ``assets`` (arc D) is THIS book's image sink: given one, each figure's own PNG is written through it
        and the hole gets a link to the picture instead of a sentence about it. It is per-CALL, not per-
        enricher, because the destination is per-book while the enricher is bound to nothing. Left ``None``
        the behaviour is byte-for-byte what it was before the arc (zero regression).

        FAIL-CLOSED on alignment (hole count ≠ BODY-picture count => nothing spliced, ``aligned=False``) and
        FAIL-OPEN per figure (an unreadable region keeps its hole, never aborts the book, D85)."""
        ...
