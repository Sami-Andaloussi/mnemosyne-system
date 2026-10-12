"""Library ingestion run (D140 / Étape 3) — the composition root for the scale-up.

Wires the REAL runtime (Docling + bge-m3 + Qdrant behind the ports, :func:`real_runtime`) to the pure,
audited :func:`~mnemosyne.ingest.library.ingest_library` driver and runs it over the hierarchical shelf
at ``knowledge/raw/<Famille>/<Groupe>/<domain>/<type>/``. Machine-only for the real path ([OPERATOR]
ignition, D126): the bricks import
lazily via ``real_runtime``, so this module is import-safe without them and only RUNS the real batch once
they are installed (``uv sync --extra bricks``) and Qdrant is up. The driver itself is fully unit-tested
brick-free; this root just supplies it the real reader + the policy's domain declaration and prints
progress — and it stays testable by INJECTING a stub runtime (so the wiring is not a blind spot).

``run_library_ingestion`` is the headless surface (callable from a notebook / another entry); ``main`` is
the CLI (``python -m mnemosyne.runtime.library_run [--limit N] [--retry-ocr]``). Both read the declared
domains for :data:`KNOWLEDGE_BUBBLE` straight from the protected policy zone and pass them to the driver,
so a book whose shelf domain the policy does not declare is refused VISIBLY (``UNDECLARED``), never
captured then silently withheld (the tag/declare lockstep, D72). Code & docstrings English (D117).
"""

from __future__ import annotations

from contextlib import AbstractContextManager, nullcontext
from pathlib import Path
from typing import TYPE_CHECKING

from ..config import Policy, load_policy
from ..ingest.library import KNOWLEDGE_BUBBLE, BookRecord, IngestReport, ingest_library

if TYPE_CHECKING:
    from . import Runtime

#: Repo root from this module (``system/lib/mnemosyne/runtime/library_run.py`` → parents[4] is the repo).
_REPO_ROOT = Path(__file__).resolve().parents[4]
#: The shared reference-library shelf (gitignored personal IP) and the resume manifest beside it.
DEFAULT_RAW_ROOT = _REPO_ROOT / "knowledge" / "raw"
DEFAULT_MANIFEST = _REPO_ROOT / "knowledge" / "library_manifest.json"


def _print_progress(rec: BookRecord) -> None:  # pragma: no cover - CLI side effect
    tail = f" — {rec.error}" if rec.error else f" ({rec.chars} chars)"
    print(f"  [{rec.status.value:>10}] {rec.rel}{tail}")


def _ingest_runtime(
    policy: Policy, *, ocr: bool = False
) -> Runtime:  # pragma: no cover - needs the bricks ([OPERATOR] ignition)
    """Cold-start a LEAN runtime carrying only what DOCUMENT ingestion needs: Docling (convert) + bge-m3
    (embed) + Qdrant (store) + tantivy (keyword), behind the ports. A DOCUMENT routes to Moteur B only —
    no graph extraction, no model call — so the graph / MLX / sandbox / outputs / secrets legs stay
    STUBBED (inert here) rather than paying a full :func:`real_runtime` boot (a 4 GB model load and every
    other brick) just to index books. The trust flags mirror the real fail-closed ignition posture; they
    are moot on this path anyway, since the driver captures already-extracted ``text`` (capture's source /
    fidelity leg is never touched). Bricks import lazily, so this stays out of the brick-free suite."""
    from ..ingest import vector_reader_factory_if_enabled, vision_captioner_if_enabled
    from ..ingest.source import MimeDispatchSourceReader, PlainTextSourceReader
    from .bootstrap import (
        RUNTIME_SERVICES,
        bootstrap,
        connect_docling,
        connect_qdrant,
        connect_tantivy,
        load_bge_m3,
    )
    from .local_first import enforce_local_first, require_services

    # The two start guards, in order, before Docling and bge-m3 — and the SECOND one is here because
    # a first audit found this function unguarded while the refusal printed to the operator claimed
    # `make ingest` stopped there too (a guarantee false for one path in four is worse than none: they
    # cannot check it, so they believe it). A SECOND audit then found that fixing that had closed the
    # CASE and not the CLASS: `enforce_local_first` is the twin guard, in the same module, and it had
    # not been propagated — so `make ingest` still opened SIX connections to huggingface.co at start,
    # against invariant 1 / D27, on the very path a commit had just claimed to bring to zero. The
    # structural test now enumerates every Runtime assembler and demands BOTH, in this order.
    enforce_local_first()
    require_services(RUNTIME_SERVICES)

    # OCR on ONLY for the needs_ocr re-extract pass (retry_ocr); off/fast otherwise (D69/D85). Figure
    # enrichment is OPT-IN (both off by default ⇒ zero regression): MNEMOSYNE_FIGURES = vector extraction
    # (sujet E, tried first), MNEMOSYNE_VISION = the LOCAL VLM caption (sujet 2, raster fallback).
    docling = connect_docling(
        ocr=ocr,
        captioner=vision_captioner_if_enabled(),
        vector_reader_factory=vector_reader_factory_if_enabled(),
    )
    # Plain-text families are already decodable text and route to the utf-8 reader, NOT Docling: a bare
    # ``.txt`` on the shelf makes Docling raise (it has no text pipeline, treats it as a failed image —
    # the ③-7 ``bm25_ranking.txt`` symptom). ``text/html`` stays on Docling (falls through to ``default``).
    plain_text = PlainTextSourceReader()
    reader = MimeDispatchSourceReader(
        {
            "text/plain": plain_text,
            "text/markdown": plain_text,
            "text/csv": plain_text,
            "application/pdf": docling,
            "application/vnd.openxmlformats-officedocument": docling,  # docx / pptx
            "application/epub+zip": docling,
            "image/": docling,  # scans → Docling (needs OCR on to yield text; flagged needs_ocr otherwise)
        },
        default=docling,
    )
    return bootstrap(
        policy=policy,
        embedder=load_bge_m3(),
        vector=connect_qdrant(),
        keyword=connect_tantivy(),
        source_reader=reader,
        graph_extraction_trusted=False,
        source_extraction_trusted=False,
    )


def run_library_ingestion(
    *,
    raw_root: Path | str = DEFAULT_RAW_ROOT,
    manifest_path: Path | str = DEFAULT_MANIFEST,
    limit: int | None = None,
    retry_ocr: bool = False,
    policy: Policy | None = None,
    runtime: Runtime | None = None,
    progress: bool = True,
    gate: AbstractContextManager[object] = nullcontext(),
) -> IngestReport:
    """Compose the runtime + reader + policy and ingest the shelf (D140) — the scale-up run.

    Reads the declared domains for :data:`KNOWLEDGE_BUBBLE` from the policy zone and passes them to the
    driver, so tagging and declaration stay in lockstep (D72). ``limit`` caps NEW work (the small real
    batch before the full ~11 h run); ``retry_ocr`` re-attempts the scanned books with the OCR reader.
    ``runtime`` is injectable (a stub in the suite); left ``None`` it cold-starts the REAL bricks.

    ``gate`` (Q1) wraps the heavy section — the runtime cold-start AND the ingest — so the CLI can pass a
    :func:`~mnemosyne.runtime.heavy.guarded_heavy_run` (one heavy run at a time + a health pre-flight). It
    defaults to :func:`~contextlib.nullcontext` (no coordination), so headless / test callers are unchanged
    (zero regression); a :class:`~mnemosyne.guard.heavy_lock.HeavyRunBusy` from a held lock propagates to
    the caller, refusing BEFORE any model is loaded."""
    from ..api import CoreApi  # lazy — avoid any import cycle through the api package

    pol = policy if policy is not None else load_policy()
    with gate:  # Q1: hold the heavy-run lock across the model cold-start + the batch (nullcontext by default)
        rt = runtime if runtime is not None else _ingest_runtime(pol, ocr=retry_ocr)
        api = CoreApi(rt)
        declared = frozenset(pol.declared_domains.get(KNOWLEDGE_BUBBLE, frozenset()))
        return ingest_library(
            api,
            rt.source_reader,
            raw_root,
            manifest_path,
            bubble=KNOWLEDGE_BUBBLE,
            declared_domains=declared,
            limit=limit,
            retry_ocr=retry_ocr,
            on_book=_print_progress if progress else None,
        )


def main(
    argv: list[str] | None = None,
) -> int:  # pragma: no cover - CLI over the REAL bricks (machine-only)
    """CLI: ``python -m mnemosyne.runtime.library_run [--limit N] [--retry-ocr]`` (the ``make ingest`` seam)."""
    import argparse

    parser = argparse.ArgumentParser(description="Ingest the reference-library shelf (D140).")
    parser.add_argument(
        "--limit", type=int, default=None, help="cap NEW books this run (small batch)"
    )
    parser.add_argument(
        "--retry-ocr", action="store_true", help="re-attempt scanned (needs_ocr) books"
    )
    parser.add_argument("--raw-root", type=Path, default=DEFAULT_RAW_ROOT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument(
        "--realign-only",
        action="store_true",
        help="G5: move manifest display paths onto current shelf paths (post-reorg), then EXIT — "
        "run this BEFORE figure enrichment so the later re-index purges stale vectors, no duplicates",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="with --realign-only: measure without writing the manifest",
    )
    parser.add_argument(
        "--report-orphans",
        action="store_true",
        help="G6: report vectors whose source book left the shelf (post-reorg orphans), then EXIT — read-only",
    )
    parser.add_argument(
        "--purge-orphans",
        action="store_true",
        help="G6: report AND purge confirmed orphans (governed, non-destructive: derivative-only), then EXIT",
    )
    args = parser.parse_args(argv)

    if args.realign_only:
        from ..ingest import realign_manifest_paths

        report = realign_manifest_paths(args.manifest, args.raw_root, dry_run=args.dry_run)
        print(report.summary())
        return 0

    if args.report_orphans or args.purge_orphans:
        from ..config import load_policy
        from ..ingest import detect_orphan_vectors, purge_orphan_vectors

        runtime = _ingest_runtime(load_policy())
        report = detect_orphan_vectors(args.manifest, args.raw_root, vector=runtime.vector)
        print(report.summary())
        for row in report.orphans:
            print(f"  orphan {row.doc}  [{row.domain}]  {row.rel}")
        if args.purge_orphans:
            purged = purge_orphan_vectors(
                report, args.manifest, args.raw_root, vector=runtime.vector, keyword=runtime.keyword
            )
            print(f"Purged {purged} orphan vector(s) + manifest row(s) (derivative-only, D56).")
        return 0

    from ..guard.heavy_lock import HeavyRunBusy
    from .heavy import HeavyRunRefused, default_health_probe, guarded_heavy_run

    print(f"Ingesting {args.raw_root} (limit={args.limit}, retry_ocr={args.retry_ocr}) …")
    # Q1: one heavy run at a time (cross-process lock) + a health pre-flight — refuse fail-closed rather
    # than pile a second multi-GB load onto the machine, or write to a full disk.
    gate = guarded_heavy_run("library-ingestion", health=default_health_probe(), on_notice=print)
    try:
        report = run_library_ingestion(
            raw_root=args.raw_root,
            manifest_path=args.manifest,
            limit=args.limit,
            retry_ocr=args.retry_ocr,
            gate=gate,
        )
    except (HeavyRunBusy, HeavyRunRefused) as exc:
        print(f"REFUSED: {exc}")
        return 1
    print(report.summary())
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
