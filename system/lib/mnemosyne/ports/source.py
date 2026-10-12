"""SourceReader (D125-B5) - the swap-able prise that turns a raw binary source into text.

Promoted from ``ingest.benne`` at (3)-4: the ONE entry a document (PDF / office / image -> OCR) or a
voice note (audio -> text) crosses to become the ``text`` the classify->route->produce pipeline already
handles. "Voice is just one more source" (AV1): documents and audio are the SAME port - the concrete
engine (Docling first-class, PaddleOCR-VL / MinerU fallbacks, WhisperKit for voice, ``oss_registry.md``)
dispatches on the declared MIME behind the prise ((3)-4b). The pipeline speaks only this port, so
PDF / office / OCR / voice extraction is swap-able without touching :meth:`~mnemosyne.api.CoreApi.capture`.

**Zero-trust (D100-3 / D81).** BOTH the bytes and the MIME are UNTRUSTED: ``data`` is adversarial
content, ``ref`` and ``mime`` are hints a caller supplies, never a barrier. A real reader runs LOCAL
in the reduced-rights ``ingest`` bubble, and the sensitivity is decided by classifying the EXTRACTED
text by the MAX (D101), never by trusting the MIME - the source can only raise prudence. A reader that
cannot read a source SHOULD abstain (return ``""``), but a raise is not catastrophic: the caller nets
it and the raw source is preserved in the benne (D85), so a failed extraction is never a lost datum.

Decisions: D125-B5 (promote SourceReader, binary/MIME entry)  -  D43 (Docling default)  -  AV1 (voice as
a source)  -  D100-3 / D81 (content-as-data, reduced-rights)  -  D101 (re-classify the extracted text)  -
D85 (raw preserved on failure). Code & docstrings English (D117).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class Source:
    """A raw binary source to extract text from - the file / binary / MIME entry (D125-B5).

    ``ref`` is provenance (a filename / uri, for the receipt and the benne key), ``data`` the raw
    bytes, ``mime`` the declared type the reader dispatches on. ALL THREE are untrusted: ``data`` is
    adversarial content (D100-3), ``ref`` and ``mime`` are caller hints, never a barrier - the
    sensitivity is decided by classifying the EXTRACTED text (D101), not by trusting the MIME."""

    ref: str
    data: bytes
    mime: str


@runtime_checkable
class SourceReader(Protocol):
    """Extract text from a raw :class:`Source` (D125-B5). Default brick = **Docling** for documents,
    **WhisperKit** for audio (``oss_registry.md``, D43 / AV1); PaddleOCR-VL / MinerU are fallbacks
    behind the SAME port. A real reader plugs in as a sole-importer adapter ((3)-4b, invariant 20); the
    stub :class:`~mnemosyne.ingest.source.PlainTextSourceReader` decodes utf-8 so the suite runs with
    no OCR / ASR brick installed (D126). Fidelity is judged out-of-band by the ingestion golden-set
    (:mod:`~mnemosyne.ingest.golden`, D125-B6), not per call - below the bar, the extraction is flagged
    low-fidelity, never silently trusted (F3)."""

    def read(self, source: Source) -> str: ...
