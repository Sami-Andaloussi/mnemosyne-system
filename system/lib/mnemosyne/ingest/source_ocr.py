"""OCR fallback readers - PaddleOCR-VL / MinerU behind the SAME SourceReader port (D43 replis / D103).

Docling is the FIRST-CLASS document reader (D43); PaddleOCR-VL and MinerU are REPLIS behind the same
:class:`~mnemosyne.ports.source.SourceReader` prise (``oss_registry.md``), reached for image-heavy or
scanned sources Docling handles less well. Each is a SOLE-importer adapter (D103 / invariant 20): the one
module allowed to touch its brick, so the pipeline speaks only the port and the suite stays green with
NO OCR brick installed (D126). Everything here is ``# pragma: no cover``: it runs only at (3) ignition
(``uv sync --extra bricks``), where the 1-click smoke confronts these colles with the real APIs. A drift
is non-catastrophic - the (3)-4a benne net (D85) preserves the raw source and re-extracts, so a broken read
degrades to a low-fidelity flag, never a lost datum. All LOCAL (D27 / D66). Code & docstrings English (D117).

**Honesty (F3).** PaddleOCR-VL and MinerU expose file-path / pipeline APIs whose exact bytes->markdown
call is less settled than Docling's; these adapters spool the bytes to a temp file and take a best-guess
call, each with an explicit ALLUMAGE NOTE. They are minimal-but-honest seams to be confirmed at the smoke
``[OPERATOR]`` - not invented certainty. Docling remains the default; a repli is wired only if user chooses it.

Decisions: D43 (Docling default, these are replis)  -  D103 (sole importer)  -  D125-B5 (SourceReader)  -
D126 (import-safe, brick-free suite)  -  D100-3 (bytes untrusted, local)  -  D85 (raw preserved on failure).
"""

from __future__ import annotations

from ..ports import Source, SourceReader


def connect_paddleocr() -> SourceReader:  # pragma: no cover - needs the brick ((3) ignition)
    """Wrap the installed PaddleOCR-VL as a :class:`SourceReader` repli (``[OPERATOR]`` allumage seam).

    Imports ``paddleocr`` LAZILY, so this module is import-safe without it (D126); wired by
    :func:`~mnemosyne.runtime.bootstrap.real_runtime` as an ``image/`` fallback if chosen. The 1-click
    smoke confronts this colle with the real API at ignition; a drift degrades to a low-fidelity flag
    (raw preserved, D85), never a lost datum.

    ALLUMAGE NOTE (best-guess API, confronted to real PaddleOCR-VL at the smoke ``[OPERATOR]``):
    ``from paddleocr import PaddleOCRVL`` -> ``pipeline = PaddleOCRVL()`` -> ``pipeline.predict(path)``
    yields an iterable of result objects, each with ``.save_to_markdown(save_path=...)`` (no direct
    string accessor observed). The best-guess ``_paddle_predict`` writes the source to a temp file (the
    pipeline is path-oriented), runs ``predict``, and concatenates the markdown the results expose.
    Confirm at ignition: the exact class name (``PaddleOCRVL`` vs a ``PaddleOCR`` pipeline flag), whether
    a result exposes markdown as a STRING (``res.markdown`` / ``res.json``) rather than only
    ``save_to_markdown`` to a path, and the input types ``predict`` accepts (path vs ndarray vs bytes)."""
    from paddleocr import PaddleOCRVL  # the SOLE import of the brick (D103 / invariant 20)

    return _PaddleOcrBackend(PaddleOCRVL())


def connect_mineru() -> SourceReader:  # pragma: no cover - needs the brick ((3) ignition)
    """Wrap the installed MinerU as a :class:`SourceReader` repli (``[OPERATOR]`` allumage seam).

    Imports MinerU LAZILY, so this module is import-safe without it (D126); wired by
    :func:`~mnemosyne.runtime.bootstrap.real_runtime` as a document/OCR fallback if chosen. The 1-click
    smoke confronts this colle with the real API at ignition; a drift degrades to a low-fidelity flag
    (raw preserved, D85), never a lost datum.

    ALLUMAGE NOTE (best-guess API, confronted to real MinerU at the smoke ``[OPERATOR]`` - the MOST uncertain
    of the four adapters): MinerU ships under TWO import names across versions - ``mineru`` (v2.x, the
    current VLM pipeline) and ``magic_pdf`` (v1.x). Its parsing is pipeline / CLI-oriented and file-path
    based (parse -> intermediate -> a markdown ``.md`` beside the output dir), with no settled single
    bytes->markdown call. The best-guess ``_mineru_convert`` therefore spools the source to a temp file
    and defers the actual pipeline call to ignition rather than inventing one: it raises a clear
    ``NotImplementedError`` naming what to wire, so the (3)-4a benne net preserves the raw source (D85) and
    user wires the confirmed call at the smoke. Confirm at ignition: which package is installed
    (``mineru`` vs ``magic_pdf``), and the exact parse call + where it writes the markdown to read back."""
    try:
        import mineru as _brick  # v2.x import name (the SOLE import of the brick, D103 / invariant 20)
    except ImportError:
        import magic_pdf as _brick  # v1.x import name (same brick, older releases)
    return _MineruBackend(_brick)


class _PaddleOcrBackend:  # pragma: no cover - real PaddleOCR-VL translation ((3)-4b ignition, smoke-tested)
    """Thin translation from :class:`SourceReader` to PaddleOCR-VL's pipeline (D43 repli / D103).

    Holds the injected pipeline (so this class never imports at module scope). ``read`` spools the bytes
    to a temp file (the pipeline is path-oriented), runs ``predict``, and gathers the markdown the
    results expose - running LOCAL on untrusted content (D100-3). It does NOT swallow a failure: a raise
    propagates to the single (3)-4a benne net (D85), and the fidelity golden-set (D125-B6) decides trust."""

    __slots__ = ("_pipeline",)

    def __init__(self, pipeline: object) -> None:
        self._pipeline = pipeline

    def read(self, source: Source) -> str:
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            src_path = Path(tmp) / (source.ref or "source")
            src_path.write_bytes(source.data)
            out_dir = Path(tmp) / "out"
            out_dir.mkdir()
            chunks: list[str] = []
            for result in self._pipeline.predict(str(src_path)):
                # Prefer a direct string accessor if the version exposes one; else render to a file and
                # read it back (confirmed at ignition - see the connect_paddleocr ALLUMAGE NOTE).
                markdown = getattr(result, "markdown", None)
                if isinstance(markdown, str):
                    chunks.append(markdown)
                    continue
                result.save_to_markdown(save_path=str(out_dir))
            if chunks:
                return "\n\n".join(chunks)
            return "\n\n".join(
                md.read_text(encoding="utf-8") for md in sorted(out_dir.rglob("*.md"))
            )


class _MineruBackend:  # pragma: no cover - real MinerU translation ((3)-4b ignition, smoke-tested)
    """Thin translation from :class:`SourceReader` to MinerU's parser (D43 repli / D103).

    Holds the injected MinerU module (so this class never imports at module scope). MinerU's parse API is
    pipeline / path-oriented and unsettled across the ``mineru`` (v2) / ``magic_pdf`` (v1) split, so
    ``read`` spools the bytes to a temp file and, rather than invent a call, raises a clear
    ``NotImplementedError`` naming exactly what to wire at the smoke ``[OPERATOR]`` (see the connect_mineru
    ALLUMAGE NOTE). The raise is caught by the single (3)-4a benne net (D85) - the raw source is preserved
    and re-extractable - so this honest seam is safe until user confirms the pipeline call at ignition."""

    __slots__ = ("_brick",)

    def __init__(self, brick: object) -> None:
        self._brick = brick

    def read(self, source: Source) -> str:
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            src_path = Path(tmp) / (source.ref or "source")
            src_path.write_bytes(source.data)
            # ALLUMAGE NOTE: wire the confirmed MinerU parse-to-markdown call HERE at the smoke [OPERATOR]
            # (mineru v2 pipeline vs magic_pdf v1). Until confirmed, fail honestly - the benne net (D85)
            # preserves the raw source, so no datum is lost and no invented API is trusted.
            raise NotImplementedError(
                "MinerU parse call to be wired at ignition ([OPERATOR]); "
                f"brick module = {getattr(self._brick, '__name__', self._brick)!r} "
                f"(source spooled to {src_path.name})"
            )
