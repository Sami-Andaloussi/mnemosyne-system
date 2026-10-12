"""Source readers (D125-B5) — the stub, the MIME dispatcher, and the real-brick seam.

The default :class:`PlainTextSourceReader` treats a source's bytes as already-decodable text (utf-8),
so the suite runs with NO OCR / ASR brick installed (D126). The real readers — Docling (documents,
first-class), PaddleOCR-VL / MinerU (fallbacks), WhisperKit (voice) — plug in behind
:class:`~mnemosyne.ports.source.SourceReader` as sole-importer adapters at ③-4b (invariant 20). The
:class:`MimeDispatchSourceReader` is THE SEAM that routes each source to the right reader on its
declared MIME (documents → Docling, ``audio/`` → WhisperKit, ``image/`` → an OCR fallback), with a
default reader as the catch-all. The pipeline speaks only the port, so swapping the engine — or the
whole dispatch table — never touches :meth:`~mnemosyne.api.CoreApi.capture`.

Decisions: D125-B5 (the socket) · D126 (stub seam, brick-free suite) · D43 (Docling) · AV1 (voice as
a source) · D100-3 (bytes AND mime are untrusted — the dispatch is a switch, never a barrier).
Code & docstrings English (D117).
"""

from __future__ import annotations

from ..ports import Source, SourceReader


class PlainTextSourceReader:
    """Fail-safe stub reader: decodes a source's bytes as utf-8, never raising (D126).

    The seam a real OCR / ASR brick swaps into without touching ``capture`` (skeleton = plumbing).
    Decodes with ``errors="replace"`` so adversarial or non-utf-8 bytes yield replacement chars, not
    a crash (D100-3). Faithful on its INTENDED input (already-decodable utf-8 text), so the default
    ``Runtime.source_extraction_trusted`` is vacuously correct under D126. Fidelity is NOT judged per
    call: whether an extraction is trusted is that runtime FLAG, set out-of-band from a golden-set
    measurement of the reader (:mod:`.golden`, D125-B6) — the honest bar a real Docling / WhisperKit
    clears (or not) at ignition, mirroring the graph's ``graph_extraction_trusted`` gate. MIME-agnostic:
    the stub reads any bytes as text; MIME dispatch is the real adapters' job (③-4b)."""

    def read(self, source: Source) -> str:
        return source.data.decode("utf-8", errors="replace")


class MimeDispatchSourceReader:
    """Route a source to a sub-reader by its declared MIME (③-4b, the SEAM) — D125-B5 / AV1.

    Built on an ordered ``mime_prefix -> SourceReader`` table plus a ``default`` catch-all: ``read``
    picks the sub-reader whose prefix is the LONGEST one that is a prefix of ``source.mime`` (a longest
    match, so ``application/vnd.openxmlformats`` may override a broader ``application/`` entry), and
    falls back to ``default`` when no prefix matches. This is how "voice is one more source" (AV1)
    becomes concrete: documents, audio and images are the SAME port, split only at this switch —
    ``text/`` / ``application/pdf`` → Docling, ``audio/`` → WhisperKit, ``image/`` → an OCR fallback.

    **Zero-trust (D100-3).** ``mime`` is UNTRUSTED caller-supplied data, so this dispatch is a routing
    hint ONLY, never a security barrier: choosing the wrong reader can at worst mis-extract (caught by
    the fidelity flag, D125-B6), never lower a datum's sensitivity — that is decided downstream by
    CLASSIFYING the extracted text over the deterministic floor (D101), independent of the MIME. A
    hostile MIME is thus a fidelity concern, not a leak. Note this reader adds NO try/except around a
    sub-reader: a reader that raises or returns a non-``str`` is netted ONCE by ``capture`` (the ③-4a
    intake-bin net, D85) — the raw source is preserved and re-extractable — so duplicating that net
    here would only hide the failure from the single place that records it.

    Decisions: D125-B5 (SourceReader) · AV1 (voice as a source) · D100-3 (mime untrusted, a switch
    not a barrier) · D85 (raise netted by capture, raw preserved) · D126 (default keeps the suite green)."""

    __slots__ = ("_table", "_default")

    def __init__(self, table: dict[str, SourceReader], *, default: SourceReader) -> None:
        # Sort longest-prefix-first ONCE at construction, so ``read`` is a cheap linear scan that
        # returns the most-specific match first (``application/vnd…`` before ``application/``).
        self._table: tuple[tuple[str, SourceReader], ...] = tuple(
            sorted(table.items(), key=lambda item: len(item[0]), reverse=True)
        )
        self._default = default

    def read(self, source: Source) -> str:
        """Dispatch to the sub-reader whose prefix best matches ``source.mime``, else ``default``.

        Longest-matching prefix wins (the table is pre-sorted longest-first); no match ⇒ ``default``.
        A sub-reader that raises is NOT caught here — that is ``capture``'s single intake-bin net (D85)."""
        for prefix, reader in self._table:
            if source.mime.startswith(prefix):
                return reader.read(source)
        return self._default.read(source)
