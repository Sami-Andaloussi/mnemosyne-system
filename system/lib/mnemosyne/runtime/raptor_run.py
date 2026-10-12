"""RAPTOR build run (Ch.5 / RAG niveau 2) - the composition root for the summary-tree corpus pass.

Wires the REAL runtime (:func:`~mnemosyne.runtime.bootstrap.real_runtime` - bge-m3 + Qdrant + the
guarded MLX runner behind the ports) to the pure, audited
:func:`~mnemosyne.ingest.raptor_build.build_raptor_tree` driver and runs it over the SAME library
manifest :mod:`~mnemosyne.runtime.library_run` ingests. Machine-only for the real path ([OPERATOR]
ignition, D126): the bricks import lazily via ``real_runtime``, so this module is import-safe
without them.

``run_raptor_build`` is the headless surface (callable from a notebook / another entry, injectable
``runtime`` for the suite); ``main`` is the CLI (``make raptor-build`` / ``make raptor-report``).
This is a HEAVY run (many model calls, one big model at a time, D95) - SERIAL, never parallelized -
so ``main`` wraps it in :func:`~mnemosyne.runtime.heavy.guarded_heavy_run` exactly like
:mod:`~mnemosyne.runtime.library_run` / :mod:`~mnemosyne.runtime.figures_enrich_run` (same
gate/except shape). Code & docstrings English (D117).
"""

from __future__ import annotations

from contextlib import AbstractContextManager, nullcontext
from pathlib import Path
from typing import TYPE_CHECKING

from ..ingest.raptor_build import RaptorBuildReport, build_raptor_tree
from .library_run import DEFAULT_MANIFEST

if TYPE_CHECKING:
    from . import Runtime


def run_raptor_build(
    *,
    manifest_path: Path | str = DEFAULT_MANIFEST,
    runtime: Runtime | None = None,
    dry_run: bool = False,
    gate: AbstractContextManager[object] = nullcontext(),
) -> RaptorBuildReport:
    """Compose the runtime and grow / refresh the RAPTOR tree over ``manifest_path`` (Ch.5).

    ``runtime`` is injectable (a stub-wired one in the suite); left ``None`` it cold-starts the REAL
    bricks via :func:`~mnemosyne.runtime.bootstrap.real_runtime` (RAPTOR needs the guarded model
    RUNNER, unlike plain document ingestion - so this reuses the FULL composition root rather than
    :mod:`~mnemosyne.runtime.library_run`'s leaner document-only cold start).

    ``gate`` (Q1) wraps the runtime cold-start AND the build - the CLI passes a
    :func:`~mnemosyne.runtime.heavy.guarded_heavy_run` (one heavy run at a time + a health
    pre-flight). Defaults to :func:`~contextlib.nullcontext` (zero regression for headless / test
    callers); a :class:`~mnemosyne.guard.heavy_lock.HeavyRunBusy` from a held lock propagates.

    Raises ``RuntimeError`` if the composed runtime carries no
    :class:`~mnemosyne.stores.raptor.RaptorStore` (Ch.5 is OPTIONAL wiring, D126) - a clear refusal
    rather than a silent no-op build."""
    from ..ingest.raptor_summarize import NullRaptorSummarizer
    from .bootstrap import real_runtime

    with gate:  # Q1: hold the heavy-run lock across the model cold-start + the walk
        rt = runtime if runtime is not None else real_runtime()
        if rt.raptor is None:
            raise RuntimeError(
                "no RaptorStore wired on this runtime (Ch.5 is optional, D126) - build refused"
            )
        summarizer = (
            rt.raptor_summarizer if rt.raptor_summarizer is not None else NullRaptorSummarizer()
        )
        return build_raptor_tree(
            manifest_path,
            truth=rt.truth,
            embedder=rt.embedder,
            vector=rt.vector,
            raptor=rt.raptor,
            summarizer=summarizer,
            dry_run=dry_run,
        )


def main(
    argv: list[str] | None = None,
) -> int:  # pragma: no cover - CLI over the REAL bricks (machine-only)
    """CLI: ``python -m mnemosyne.runtime.raptor_run [--manifest PATH] [--report]``.

    ``--report`` is the dry view (``make raptor-report``): counts what a real build would do -
    reused / would-summarize / would-sweep - without calling the summarizer or writing anything."""
    import argparse

    parser = argparse.ArgumentParser(description="Build/refresh the RAPTOR summary tree (Ch.5).")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument(
        "--report", action="store_true", help="dry view: count what would happen, write nothing"
    )
    args = parser.parse_args(argv)

    print(f"RAPTOR build over {args.manifest} (report={args.report}) ...")
    from ..guard.heavy_lock import HeavyRunBusy
    from .heavy import HeavyRunRefused, default_health_probe, guarded_heavy_run

    # Q1: one heavy run at a time (cross-process lock) + a health pre-flight - this pass never
    # collides with a concurrent `make ingest` / `make figures-enrich`.
    gate = guarded_heavy_run("raptor-build", health=default_health_probe(), on_notice=print)
    try:
        report = run_raptor_build(manifest_path=args.manifest, dry_run=args.report, gate=gate)
    except (HeavyRunBusy, HeavyRunRefused) as exc:
        print(f"REFUSE : {exc}")
        return 1
    print(report.summary())
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
