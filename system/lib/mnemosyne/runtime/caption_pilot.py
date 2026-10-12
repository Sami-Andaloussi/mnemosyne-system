"""Run a bounded captioning sample for configuration review."""

from __future__ import annotations

import mimetypes
import os
import sys
from pathlib import Path

from ..ingest.caption import _IMAGE_PLACEHOLDER
from ..ports import ImageCaptioner
from ..provenance import FIGURE_CAPTION_MARK  # single source of the mark (anti-drift)


class _FirstN:
    """Cap the pilot to the first ``n`` DESCRIBED figures for a FAST eyeball (and a quick confront of the
    mlx-vlm API): after ``n`` successful captions, every further figure gets an empty caption, so the weave
    leaves it as a hole - exactly like a per-figure failure (D85). Pilot-only, so the local VLM runs at most
    ``n`` times instead of once per figure in a 500-page book. Satisfies :class:`ImageCaptioner`."""

    def __init__(self, inner: ImageCaptioner, n: int) -> None:
        self._inner = inner
        self._n = n
        self._done = 0

    @property
    def model_id(self) -> str:
        return self._inner.model_id

    def caption(self, image: bytes, *, context: str = "") -> str:
        if self._done >= self._n:
            return ""
        self._done += 1
        return self._inner.caption(image, context=context)


class _DebugCaptioner:  # pragma: no cover - diagnostic wrapper, machine-only (env CAPTION_DEBUG=1)
    """Diagnostic wrapper: per figure, dump the size / mode / pixel stats of the image the VLM ACTUALLY
    receives + the injected context + the produced caption, and save that exact image to ``/tmp`` - so a dud
    caption ("La" + stop) can be traced to a blank / tiny / mis-rasterised figure vs a genuine model miss.
    Off unless ``CAPTION_DEBUG`` is set; wraps the real captioner without changing its output."""

    def __init__(self, inner: ImageCaptioner) -> None:
        self._inner = inner
        self._n = 0

    @property
    def model_id(self) -> str:
        return self._inner.model_id

    def caption(self, image: bytes, *, context: str = "") -> str:
        from io import BytesIO

        from PIL import Image

        self._n += 1
        img = Image.open(BytesIO(image))
        px = list(img.convert("L").getdata())
        lo, hi, mean = min(px), max(px), sum(px) / len(px)
        out = f"/tmp/caption_debug_fig{self._n}.png"
        img.convert("RGB").save(out)
        result = self._inner.caption(image, context=context)
        print(
            f"[debug] fig{self._n}: size={img.size} mode={img.mode} bytes={len(image)} "
            f"pixels[min={lo} max={hi} mean={mean:.0f}] ctx={context[:50]!r} "
            f"-> caption={result[:60]!r} (saved {out})"
        )
        return result


def run_caption_pilot(
    pdf: Path, *, max_figures: int | None = None
) -> Path:  # pragma: no cover - needs the bricks ([OPERATOR] ignition)
    """Convert ONE document with the vision stage on and write ``<stem>.vision.md`` beside it.

    Returns the output path and prints a one-line tally (figures described / holes left) so user can eyeball
    the quality at a glance before deploying over a collection. ``max_figures`` caps the run to the first N
    figures (:class:`_FirstN`) for a fast first pilot; ``None`` describes them all. Fail-open lives per figure
    inside the adapter (D85): an unreadable figure just stays a hole, never aborts the book."""
    # enforce_local_first FIRST (invariant 1 / D27): this loads BOTH Docling and a multi-GB VLM, and the
    # offline posture is read once, at import. Added when widening the structural test's population from
    # "functions that open Qdrant" to "functions that load weights" - this pilot had never been judged.
    from .local_first import enforce_local_first

    enforce_local_first()

    from ..ingest import connect_docling, connect_mlx_vlm
    from ..ports import Source

    captioner: ImageCaptioner = connect_mlx_vlm()
    if os.environ.get("CAPTION_DEBUG"):
        captioner = _DebugCaptioner(captioner)  # dump what the VLM actually receives, per figure
    if max_figures is not None:
        captioner = _FirstN(captioner, max_figures)
    reader = connect_docling(captioner=captioner)
    mime = (
        mimetypes.guess_type(pdf.name)[0] or "application/octet-stream"
    )  # Docling keys on ref anyway
    markdown = reader.read(Source(ref=pdf.name, data=pdf.read_bytes(), mime=mime))
    out = pdf.with_suffix(".vision.md")
    out.write_text(markdown, encoding="utf-8")
    described = markdown.count(FIGURE_CAPTION_MARK)
    holes = markdown.count(_IMAGE_PLACEHOLDER)
    print(
        f"[caption-pilot] {pdf.name}: {described} figure(s) decrite(s), {holes} trou(s) restant(s)"
    )
    print(f"[caption-pilot] ecrit -> {out}")
    return out


def main() -> None:  # pragma: no cover - CLI
    if len(sys.argv) not in (2, 3):
        print(
            "usage: python -m mnemosyne.runtime.caption_pilot <book.(pdf|epub|docx|...)> [max_figures]",
            file=sys.stderr,
        )
        raise SystemExit(2)
    max_figures = int(sys.argv[2]) if len(sys.argv) == 3 else None
    run_caption_pilot(Path(sys.argv[1]), max_figures=max_figures)


if __name__ == "__main__":  # pragma: no cover
    main()
