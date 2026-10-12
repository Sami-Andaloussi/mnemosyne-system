"""Figure enrichment run (sujet F) — the composition root for the incremental, in-place figure campaign.

Wires the REAL local bricks — Docling (find each figure), PyMuPDF (read its vector primitives), and
OPTIONALLY the local VLM (caption a genuinely raster figure) — behind
:class:`~mnemosyne.ports.figure_enrich.FigureEnricher`, and runs the audited, brick-free
:func:`~mnemosyne.ingest.figure_enrich.enrich_figures_campaign` over the shelf. It fills the
``<!-- image -->`` holes that are still in the operator's cached ``.md`` WITHOUT re-converting anything: only the
PDF is re-opened, only its figures are read, and only the changed ``.md`` files then need re-indexing
(``ingest_library`` sees the new content hash and re-embeds just those — D-CI). LOCAL FIRST: vector
extraction is ALWAYS on (free, exact); the VLM is opt-in (``--vision``) because it is slow, so a first pass
measures how far the deterministic local gets before any model is spent.

Machine-only for the real path ([OPERATOR] ignition, D126): the bricks import lazily via
:func:`_figure_enricher`, so this module is import-safe without them and only RUNS once
``uv sync --extra bricks`` (Docling + PyMuPDF, and mlx-vlm for ``--vision``) is done.
:func:`run_figures_enrichment` is the headless surface and stays testable by INJECTING a fake enricher;
:func:`main` is the CLI (``python -m mnemosyne.runtime.figures_enrich_run``). Code & docstrings English (D117).
"""

from __future__ import annotations

from contextlib import AbstractContextManager, nullcontext
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING

from ..ingest.figure_enrich import BookEnrichResult, CampaignReport, enrich_figures_campaign
from .human_gate import read_live_confirmation

if TYPE_CHECKING:
    from ..ports.figure_enrich import FigureEnricher

#: Repo root from this module (``system/lib/mnemosyne/runtime/figures_enrich_run.py`` → parents[4]).
_REPO_ROOT = Path(__file__).resolve().parents[4]
#: The shared reference-library shelf (gitignored personal IP) — same root as library ingestion.
DEFAULT_RAW_ROOT = _REPO_ROOT / "knowledge" / "raw"


def _figure_enricher(
    *, vision: bool, frontier: bool = False, images: bool = False
) -> FigureEnricher:  # pragma: no cover - needs the bricks ([OPERATOR])
    """Build the REAL in-place enricher: Docling + PyMuPDF (vector, ALWAYS on) + optional local VLM + optional frontier.

    Vector extraction is unconditional here — the whole point of the figure campaign — so
    ``connect_pymupdf_reader`` is wired directly, not via the ingestion opt-in switch. The local VLM is
    added only for ``--vision`` (it loads a multi-GB model and runs one inference per raster figure — slow),
    so the deterministic local pass can be measured first. The niveau-3 FRONTIER captioner is added only for
    ``frontier=True`` — which :func:`main` sets ONLY after the operator's interactive confirmation (the canal-B human
    gesture, D90). It egresses each abstract figure through the Guard: the Guard loads the PROTECTED policy,
    so ``api.anthropic.com`` must ALSO be on its egress allow-list ([OPERATOR] POLICY_WRITE) or every figure is
    DENIED and stays a hole (the two barriers, gesture + allow-list, both required). Bricks import lazily.

    **``enforce_local_first()`` FIRST, before the lazy imports** (invariant 1 / D27). An isolated audit
    found this entry point unguarded while its twin ``make ingest`` had been repaired twice for exactly
    this — the structural test's population was "functions that open Qdrant", and this one loads Docling
    WITHOUT Qdrant, so it was excluded, therefore unjudged, not safe. Widening that population then found
    the hole was FOUR times bigger (``calibration``, ``caption_pilot`` too). The posture is read once, at
    import, so it must be set before the brick is imported — hence here, not in ``main``."""
    from .local_first import enforce_local_first

    enforce_local_first()

    from ..ingest import connect_docling_figure_enricher, connect_pymupdf_reader

    captioner = None
    if vision:
        from ..ingest import connect_mlx_vlm

        captioner = connect_mlx_vlm()
    cloud_captioner = None
    if frontier:
        from ..guard.monitor import DeterministicGuard
        from ..ingest import connect_anthropic_vision
        from ..ingest.library import KNOWLEDGE_BUBBLE
        from ..ports import HumanTier

        # frontier=True ENCODES the operator's interactive confirmation (main's [OPERATOR] gate) → the canal-B gesture.
        # The Guard mediates every figure egress; a bare DeterministicGuard() loads the protected policy zone.
        cloud_captioner = connect_anthropic_vision(
            guard=DeterministicGuard(),
            subject=KNOWLEDGE_BUBBLE,
            human_gesture=HumanTier.FLAG_ROUTINE,
        )
    return connect_docling_figure_enricher(
        captioner=captioner,
        cloud_captioner=cloud_captioner,
        vector_reader_factory=connect_pymupdf_reader,
        images=images,
    )


def _print_progress(
    result: BookEnrichResult, *, dry_run: bool = False
) -> None:  # pragma: no cover - CLI side effect
    stats = result.stats
    if stats is None:
        print(f"  [   ERROR] {result.rel} — {result.error}")
    elif not stats.aligned:
        print(
            f"  [MISALIGN] {result.rel} — {stats.holes} holes vs {stats.body_pictures} pictures (skipped)"
        )
    else:
        # honest tag (F3): in a dry-run NOTHING is written to disk, so never say "written" — say what WOULD
        # happen. "changed" ⇒ would-fill (dry) / written (real); unchanged ⇒ no-op either way.
        tag = ("would-fill" if dry_run else "  written") if result.changed else "    no-op"
        print(
            f"  [{tag}] {result.rel} — img {stats.filled_image}, vec {stats.filled_vector}, "
            f"vlm {stats.filled_vlm}, cloud {stats.filled_cloud}, left {stats.remaining_holes}"
        )


def run_figures_enrichment(
    *,
    raw_root: Path | str = DEFAULT_RAW_ROOT,
    limit: int | None = None,
    max_holes: int | None = None,
    vision: bool = False,
    frontier: bool = False,
    images: bool = False,
    only: str | None = None,
    dry_run: bool = False,
    enricher: FigureEnricher | None = None,
    progress: bool = True,
    gate: AbstractContextManager[object] = nullcontext(),
) -> CampaignReport:
    """Compose the enricher and run the in-place figure campaign over the shelf (the sujet F run).

    ``enricher`` is injectable (a fake in the suite, so the wiring is not a blind spot); left ``None`` it
    cold-starts the REAL bricks (:func:`_figure_enricher`). ``dry_run`` measures without writing (the
    diagnostic pass); ``max_holes`` skips scan-dominant books; ``limit`` caps a pilot batch. ``frontier``
    enables niveau 3 — the caller (``main`` after the operator's confirmation) asserts the canal-B gesture; the Guard
    still enforces the allow-list, so a bare ``frontier=True`` without an allow-listed host leaks nothing.

    ``gate`` (Q1) wraps the enricher cold-start AND the campaign — the CLI passes a
    :func:`~mnemosyne.runtime.heavy.guarded_heavy_run` so this heavy pass and a concurrent ``make ingest``
    can never both load big models at once. Defaults to :func:`~contextlib.nullcontext` (zero regression for
    headless / test callers); a :class:`~mnemosyne.guard.heavy_lock.HeavyRunBusy` propagates to the caller."""
    with gate:  # Q1: one heavy run at a time (nullcontext by default — headless callers unchanged)
        enr = (
            enricher
            if enricher is not None
            else _figure_enricher(vision=vision, frontier=frontier, images=images)
        )
        return enrich_figures_campaign(
            enr,
            raw_root,
            # ``only`` narrows the pool to the books whose shelf path CONTAINS it (case-folded) — the
            # gesture a proof needs: run on ONE named book, look at the result, before any batch.
            select=(lambda b: only.casefold() in str(b.rel).casefold()) if only else None,
            limit=limit,
            max_holes=max_holes,
            images=images,
            dry_run=dry_run,
            on_book=partial(_print_progress, dry_run=dry_run) if progress else None,
        )


_FRONTIER_HOST = "api.anthropic.com"


def _confirm_frontier_egress(host: str) -> bool:
    """The canal-B human gesture, read from the CONTROLLING TERMINAL (D90 / D74-b / D159).

    Niveau 3 SENDS the abstract figures the local cannot read to a third-party cloud — an egress that
    LEAVES the machine. We never assume it: we ask, and grant the gesture ONLY on an explicit yes.

    **This used to read ``input()``, and an isolated audit killed it on 2026-07-28**: a piped
    caller satisfied the gesture outright (``printf 'oui\\n' | …`` → ``True``), which is the exact
    class of the July incident where an agent typed a word meant for the operator. ``input()`` reads
    ``stdin``; ``stdin`` is whatever the parent process hands over. The gesture that lets personal
    data leave the machine now goes through the same unforgeable door as declassification and policy
    writes — :func:`~mnemosyne.runtime.human_gate.read_live_confirmation` — so no terminal means
    refusal, and the run stays local. The operator at a keyboard is unaffected; an agent cannot pass.
    """
    confirmed = read_live_confirmation(
        f"\n\U000026A0\U0000FE0F  Level 3 (frontier): the abstract figures the LOCAL cannot read will be SENT\n"
        f"    to {host} (a third party) — they LEAVE your machine. The Guard also requires this host to be\n"
        f"    allow-listed in the policy, or nothing goes out. Do you confirm this transfer for this batch? [yes/no] ",
        accepted=("oui", "o", "yes", "y"),
    )
    print(
        "    → gesture granted, level 3 active."
        if confirmed
        else "    → refused, LOCAL run only."
    )
    return confirmed


def main(
    argv: list[str] | None = None,
) -> int:  # pragma: no cover - CLI over the REAL bricks (machine-only)
    """CLI: ``python -m mnemosyne.runtime.figures_enrich_run [--limit N] [--max-holes M] [--vision] [--frontier] [--dry-run]``."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Incremental in-place figure enrichment (sujet F)."
    )
    parser.add_argument(
        "--limit", type=int, default=None, help="cap books processed (a fast pilot)"
    )
    parser.add_argument(
        "--max-holes", type=int, default=None, help="skip a book with more holes than this (scans)"
    )
    parser.add_argument(
        "--images",
        action="store_true",
        help="keep each figure's OWN pixels as a .png the .md links (arc D) — no model, deterministic",
    )
    parser.add_argument(
        "--only",
        default=None,
        help="only books whose shelf path contains this (case-insensitive) — prove on ONE book first",
    )
    parser.add_argument(
        "--vision",
        action="store_true",
        help="also run the local VLM on raster figures (slow, opt-in)",
    )
    parser.add_argument(
        "--frontier",
        action="store_true",
        help="niveau 3: send the figures the local fails to the frontier (asks for confirmation first)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="measure only; do NOT write any .md (diagnostic pass)",
    )
    parser.add_argument("--raw-root", type=Path, default=DEFAULT_RAW_ROOT)
    args = parser.parse_args(argv)

    # niveau 3 is gated on an interactive human confirmation (the canal-B gesture); --frontier only OFFERS it.
    frontier = args.frontier and _confirm_frontier_egress(_FRONTIER_HOST)

    print(
        f"Figure enrichment over {args.raw_root} (limit={args.limit}, max_holes={args.max_holes}, "
        f"images={args.images}, only={args.only!r}, vision={args.vision}, frontier={frontier}, "
        f"dry_run={args.dry_run}) …"
    )
    from ..guard.heavy_lock import HeavyRunBusy
    from .heavy import HeavyRunRefused, default_health_probe, guarded_heavy_run

    # Q1: one heavy run at a time (cross-process lock) + a health pre-flight — this figure pass never
    # collides with a concurrent `make ingest`, and refuses fail-closed rather than write to a full disk.
    gate = guarded_heavy_run("figures-enrich", health=default_health_probe(), on_notice=print)
    try:
        report = run_figures_enrichment(
            raw_root=args.raw_root,
            limit=args.limit,
            max_holes=args.max_holes,
            vision=args.vision,
            frontier=frontier,
            images=args.images,
            only=args.only,
            dry_run=args.dry_run,
            gate=gate,
        )
    except (HeavyRunBusy, HeavyRunRefused) as exc:
        print(f"REFUSED: {exc}")
        return 1
    print(report.summary())
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
