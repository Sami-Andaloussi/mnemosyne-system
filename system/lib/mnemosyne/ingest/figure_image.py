"""Extracted-figure assets (arc D) — write the figure's OWN pixels next to the book, and link them.

The payload half of the figure campaign. :mod:`~mnemosyne.ingest.figure_enrich` already owns the hard
guarantees — non-destructive ``.prefig`` backup, atomic rewrite, per-book isolation (D140), and the
FAIL-CLOSED alignment check (hole count ≠ BODY-figure count ⇒ nothing spliced). None of that changes here.
What changes is WHAT lands in a hole: a ``![Figure 4](….png)`` link to the real chart instead of a
sentence describing it.

Two homes, matching the two guarantees:

* :func:`image_payload` — PURE composition (brick-free, D126): the markdown link, plus the deterministic
  vector read-out when one exists. Both, on one line, on purpose: **the image is for the operator, the
  read-out is for the index.** A PNG is invisible to ``make search`` — dropping the read-out to make room
  for the image would silently amputate the corpus's searchability, which is the exact failure the arc
  set out to undo.
* :class:`DirectoryImageSink` — the real writer: one ``<stem>.figures/`` directory per book, ``fig-NNN.png``
  named by the SAME ordinal the splice uses, written atomically and idempotently, FAIL-OPEN on any IO error
  (D85) so a full disk degrades one figure instead of aborting a 244-book campaign.

``.png`` is not a corpus extension (:mod:`~mnemosyne.ingest.library`), so these assets are never mistaken
for books by ``discover_books`` and never enter the index as documents. Code & docstrings English (D117);
the emitted alt text is French — it lands in the operator's ``.md`` (D33 / D117).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Final
from urllib.parse import quote

#: Per-book asset directory = the ``.md``'s stem + this suffix, so two books sharing a folder never collide
#: and the assets stay adjacent to the text they belong to (one gesture moves both).
ASSETS_DIR_SUFFIX: Final = ".figures"

#: Separator between the image link and the vector read-out on the woven line. NOT " — ": the read-out uses
#: that internally, and a line with three em-dashes reads as one run-on sentence.
_PAYLOAD_SEP: Final = " · "


def figure_asset_name(ordinal: int) -> str:
    """The file name for BODY figure ``ordinal`` (0-based) — zero-padded so a directory listing sorts right.

    Deterministic and ordinal-derived on purpose: the name is a CHECKABLE claim about which hole the asset
    fills, so a mis-splice is visible in the file system (``fig-003.png`` under the paragraph about figure 9),
    not just in the markdown. Beyond 1 000 figures the padding simply grows — no wrap, no collision."""
    return f"fig-{ordinal:03d}.png"


def image_payload(link: str, ordinal: int, readout: str = "") -> str:
    """Compose the ONE-LINE markdown that fills a figure hole: the image, then the read-out when there is one.

    Returns ``""`` when ``link`` is empty — the caller then falls back to the text paths, or leaves the hole
    (fail-open, D85). ``link`` is percent-ENCODED here rather than at the sink, because encoding is a
    property of the markdown, not of the file system: the sink returns a real relative path (with its spaces
    and accents intact) and this function makes it linkable. The alt text is ``Figure N`` (1-based — what a
    reader counts), never the PDF's caption: that caption is already prose in the ``.md`` a line below, and
    duplicating it would put author text inside a line the verbatim floor MASKS."""
    if not link:
        return ""
    alt = f"Figure {ordinal + 1}"
    encoded = quote(link, safe="/")
    line = f"![{alt}]({encoded})"
    readout = " ".join(readout.split())
    if readout:
        line = f"{line}{_PAYLOAD_SEP}{readout}"
    return line


@dataclass(frozen=True, slots=True)
class DryRunImageSink:
    """The sink a DRY RUN uses: computes the link it WOULD return, writes not one byte.

    Without it a ``--dry-run --images`` would run with no sink at all, take the text fallback, and report a
    tally that is NOT what the real run would produce — a diagnostic that lies about the very pass it is
    supposed to preview. Here the routing decision, the ordinal, and the link are identical to
    :class:`DirectoryImageSink`; only the ``write`` is absent. It reports on empty bytes exactly like the
    real sink does (``""``), so a figure Docling could not render is counted as unfilled in the preview too."""

    md_path: Path
    dir_suffix: str = ASSETS_DIR_SUFFIX

    def save(self, ordinal: int, png: bytes) -> str:
        if not png:
            return ""
        return f"{self.md_path.stem}{self.dir_suffix}/{figure_asset_name(ordinal)}"


@dataclass(frozen=True, slots=True)
class DirectoryImageSink:
    """Write one book's figure PNGs into ``<stem>.figures/`` beside its ``.md`` (the real
    :class:`~mnemosyne.ports.figure_image.FigureImageSink`).

    IDEMPOTENT: a re-run that produces identical bytes rewrites nothing (the campaign is resumable, and a
    second pass over 26 315 figures must not churn the disk). ATOMIC: a temp sibling + ``os.replace``, so a
    crash mid-write can never leave a truncated PNG that a reader would show as a grey box. FAIL-OPEN (D85):
    any ``OSError`` — full disk, read-only mount, a name the file system refuses — returns ``""``; that one
    figure degrades to its text read-out and the campaign lives on."""

    md_path: Path
    dir_suffix: str = ASSETS_DIR_SUFFIX

    @property
    def assets_dir(self) -> Path:
        """The book's asset directory (not created until something is actually written)."""
        return self.md_path.with_name(self.md_path.stem + self.dir_suffix)

    def save(self, ordinal: int, png: bytes) -> str:
        """Persist figure ``ordinal``'s PNG; return the ``.md``-relative link target, or ``""`` on any failure."""
        if not png:
            return ""
        name = figure_asset_name(ordinal)
        target = self.assets_dir / name
        rel = f"{self.assets_dir.name}/{name}"
        try:
            if target.exists() and target.read_bytes() == png:
                return rel  # already written, byte-identical — idempotent no-op
            self.assets_dir.mkdir(parents=True, exist_ok=True)
            tmp = target.with_name(f"{name}.{os.getpid()}.tmp")
            tmp.write_bytes(png)
            tmp.replace(target)
        except OSError:
            return (
                ""  # fail-open (D85): this figure keeps its text path; the campaign is not aborted
            )
        return rel
