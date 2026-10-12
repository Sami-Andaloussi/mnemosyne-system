#!/usr/bin/env python3
"""Frontier distillation CAMPAIGN - distil MANY public books via Claude Haiku, IN PARALLEL (D95 / D144).

**Why.** The local backend distils faithfully but serial processing can delay a large batch. A PUBLISHED
book is ``public`` by provenance (D107 / D144) -> its text may
leave to an allow-listed cloud host (``route_model`` -> canal A), and the Anthropic API parallelises across
books (network-bound, not RAM-bound). This is the REPEATABLE tool for future batches, not a one-off.

**The barrier is the Garde (D100), two independent locks - checked with NO key needed:**

* **PUBLIC-only by ROUTING (invariant 1).** Per book the campaign asks the Guard's OWN router,
  :meth:`route_model`; the frontier backend is used ONLY when the label routes to canal A - which happens
  ONLY when every input is ``public``. A non-public label forces LOCAL, so a ``sensible`` doc can never
  reach Haiku (structural, not disciplined).
* **Allow-listed host (invariant 21).** ``api.anthropic.com`` must be on the protected egress allow-list
  (a [OPERATOR] POLICY gesture). Checked ONCE up front; absent, the campaign fails CLOSED with the exact gesture
  to run - never a silent local fallback that would masquerade as success.

**Publicness = PROVENANCE, ASSUMED not verified (be honest about the barrier - audit YYYY-MM-DD).** The
campaign distils the LIBRARY SHELF (:func:`discover_books`): a shelf book is labelled ``public``
AUTHORITATIVELY by provenance (D107 - the PII floor false-positives on published text, an ISBN or an
author's email, so provenance overrides the floor, exactly as at ingest). This is an ASSUMPTION about the
shelf, NOT a per-file content check: the egress runs as a ``MODEL_CALL``, so the Guard's egress content
floor (M2) does NOT re-scan the payload. The per-book gate (:func:`_egress_cleared`) therefore re-checks
only the GLOBAL governance state (policy allows public auto-route + host allow-listed) - it does NOT verify
this book's content. Three mitigations stand in for the missing content net: (1) personal shelf families
are EXCLUDED by default (:data:`_EXCLUDED_FAMILIES`); (2) an advisory tripwire flags suspiciously small
selections (a session artifact, a stray note - :func:`_suspect_files`) for a human eyeball; (3) the empty
egress allow-list means NOTHING leaves until user adds the host by an explicit ``POLICY_WRITE`` - the
informed-consent point. A truly mis-filed non-public file under a ``books/`` folder would still egress; the
``--dry-run`` review + the tripwire are the operational guard, not a structural one.

**Same faithful pipeline.** Each book is distilled by :func:`distill_book.distill_one` - the ONE skill path
(D39-4), only the injected backend changes. Parallel across BOOKS with a governed API PER WORKER (the
runner's snapshot / usage state is per-instance and single-threaded, so threads never share it). Idempotent
(skips a book whose fiche exists, unless ``--force``) and resumable (distill_one's atomic .tmp->rename
protects a partial). Reports token usage -> an (approximate, overridable) cost estimate.

Decisions: D95  -  D144 / D107 (public-by-provenance)  -  D66 / inv 1 (route_model public-only)  -  inv 21
(egress allow-list)  -  D39-4 (single skill path)  -  D140 (per-book net). Code & docstrings English (D117).
"""

from __future__ import annotations

import argparse
import concurrent.futures as cf
import os
import sys
import threading
from pathlib import Path

# Same-dir sibling: the ONE per-book skill path (run as a script, this dir is on sys.path[0]).
from distill_book import _distilled_path_for, distill_one

from mnemosyne.ingest import taxonomy
from mnemosyne.runtime.runner_anthropic import HOST, _DEFAULT_MODEL

_RAW_ROOT = Path("knowledge/raw")
_DEFAULT_WORKERS = (
    6  # the API is network-bound -> parallelise across books; bounded to respect rate limits
)

# Shelf families never sent to a third-party model by default: personal-interest published
# books + any misfiled perso material live under `General/`. Pro domains (Economics, Finance, Software, ...)
# are unaffected. Overridable with --include-personal (a conscious choice). SINGLE SOURCE (D149): the SAME
# intimate-family set also labels their fiches `sensible` (distill_book._book_sensitivity) - one home so
# egress-protection and label-protection can never drift apart.
_EXCLUDED_FAMILIES = taxonomy.PERSONAL_FAMILIES

# A selected source is flagged (advisory) as "probably not a real book" if it is NOT a converted `.md`
# (the shelf is `.md`-first, so a stray `.txt` is usually an artifact - the two known parasites
# ORGANIZATION_SUMMARY.txt / COMPLETION_REPORT.txt are `.txt`) OR it is TINY. Kept sharp so the warning is
# actionable, not 69 legit-but-short `.md` guides drowning the two real parasites (audit MAJEUR-1).
_MIN_BOOK_BYTES = 8_000

# Approximate Claude Haiku 4.5 pricing (USD per MILLION tokens) - VERIFY current rates before a big run;
# overridable via env so the estimate tracks reality with no code change. The token COUNTS printed are
# AUTHORITATIVE (from the API usage) - only the dollar estimate depends on these two knobs.
_USD_PER_MTOK_IN = float(os.environ.get("HAIKU_USD_PER_MTOK_IN", "1.0"))
_USD_PER_MTOK_OUT = float(os.environ.get("HAIKU_USD_PER_MTOK_OUT", "5.0"))


def _public_label(domain: object):  # noqa: ANN202 - GovernanceLabel (import paresseux)
    """The PUBLIC label a shelf book carries - public by PROVENANCE (D107 / D144), same as at ingest."""
    from mnemosyne.ingest.library import KNOWLEDGE_BUBBLE
    from mnemosyne.ports import GovernanceLabel, Sensitivity

    return GovernanceLabel(
        sensitivity=Sensitivity.PUBLIC, bubble=KNOWLEDGE_BUBBLE, domains=frozenset({domain})
    )


def _egress_cleared(rt: object, label: object) -> tuple[bool, str]:
    """Whether the Garde clears a frontier (cloud) egress for ``label`` to :data:`HOST` - the TWO locks.

    (1) the host on the egress allow-list (invariant 21); (2) ``route_model`` -> canal A (public-only,
    invariant 1). BOTH must hold. Returns ``(ok, reason)`` so the caller fails CLOSED loudly with the
    exact gesture - never a silent degrade. Needs no API key (policy + router only)."""
    from mnemosyne.ports import Channel

    if not rt.policy.egress_allowed(HOST):  # type: ignore[attr-defined]
        return False, (
            f"{HOST!r} is not on the egress allow-list -- [OPERATOR] POLICY: add it to "
            "system/config/policy.toml before the frontier campaign (invariant 21, deny-by-default)."
        )
    if rt.guard.route_model((label,)) is not Channel.CANAL_A_PUBLIC_AUTO:  # type: ignore[attr-defined]
        return False, (
            "route_model does not route this book to channel A (cloud): the label is not `public`, or "
            "the zone forbids public auto-routing (invariant 1). This book must stay on LOCAL distillation."
        )
    return True, ""


def _select_books(
    raw_root: Path,
    *,
    domain: str | None,
    force: bool,
    limit: int | None,
    include_personal: bool = False,
) -> list:
    """The corpus books to distil: the library shelf (:func:`discover_books`), MINUS the personal families
    (:data:`_EXCLUDED_FAMILIES`, unless ``include_personal``), filtered to a domain, skipping those already
    distilled (unless ``force``), capped by ``limit``. Deterministic order. (Publicness is by provenance -
    see the module docstring; the personal exclude + the tripwire stand in for the missing content net.)"""
    from mnemosyne.ingest.library import discover_books

    books = discover_books(raw_root)
    if not include_personal:
        books = [b for b in books if b.rel.parts[0] not in _EXCLUDED_FAMILIES]
    if domain:
        books = [b for b in books if str(b.domain) == domain]
    todo = [b for b in books if force or not _distilled_path_for(b.mirror).exists()]
    return todo[:limit] if limit else todo


def _suspect_files(books: list) -> list:
    """Advisory tripwire (audit MAJEUR-1): selected sources that don't look like a real book - a non-``.md``
    source (the shelf is ``.md``-first, so a stray ``.txt`` is usually a session artifact) OR a tiny one -
    surfaced for a human eyeball BEFORE any cloud egress. NOT a block: publicness is by provenance, and a
    real book trips the PII floor anyway (ISBN), so `is-it-a-book` (extension/size), not content, is the
    clean signal. Kept sharp on purpose (a short legit ``.md`` guide is NOT flagged)."""
    suspects = []
    for book in books:
        try:
            size = book.mirror.stat().st_size
        except OSError:
            size = 0
        if book.mirror.suffix.lower() != ".md" or size < _MIN_BOOK_BYTES:
            suspects.append((book, size))
    return suspects


class _WorkerApis:
    """One governed (backend, api) per worker THREAD - the runner's snapshot/usage state is per-instance
    and single-threaded, so threads must not share it. Built lazily on a thread's first book and reused;
    every backend is kept so token usage sums at the end (cost)."""

    def __init__(self, model: str) -> None:
        self._model = model
        self._local = threading.local()
        self._all: list[object] = []
        self._lock = threading.Lock()

    def api(self) -> object:
        pair = getattr(self._local, "pair", None)
        if pair is None:
            from mnemosyne.api import CoreApi
            from mnemosyne.runtime.bootstrap import bootstrap
            from mnemosyne.runtime.runner_anthropic import load_anthropic_backend

            backend = load_anthropic_backend(
                model=self._model
            )  # raises loud if ANTHROPIC_API_KEY absent
            pair = (backend, CoreApi(bootstrap(generation_backend=backend)))
            self._local.pair = pair
            with self._lock:
                self._all.append(backend)
        return pair[1]

    def total_usage(self) -> dict[str, int]:
        total = {"input_tokens": 0, "output_tokens": 0, "requests": 0}
        with self._lock:
            backends = list(self._all)
        for backend in backends:
            for key, val in backend.usage.items():  # type: ignore[attr-defined]
                total[key] += val
        return total


def _print_cost(model: str, usage: dict[str, int]) -> None:
    cost = (
        usage["input_tokens"] / 1e6 * _USD_PER_MTOK_IN
        + usage["output_tokens"] / 1e6 * _USD_PER_MTOK_OUT
    )
    print(
        f"\nUsage {model}: {usage['requests']} request(s) | "
        f"{usage['input_tokens']:,} tokens in | {usage['output_tokens']:,} tokens out\n"
        f"Estimated cost: ~${cost:.2f} "
        f"(at ${_USD_PER_MTOK_IN:.2f}/M in, ${_USD_PER_MTOK_OUT:.2f}/M out -- APPROX, check current pricing)."
    )


def run_campaign(
    *,
    raw_root: Path = _RAW_ROOT,
    domain: str | None = None,
    workers: int = _DEFAULT_WORKERS,
    limit: int | None = None,
    force: bool = False,
    max_chunks: int | None = None,
    model: str = _DEFAULT_MODEL,
    dry_run: bool = False,
    include_personal: bool = False,
) -> int:
    """Run the frontier distillation campaign. Returns 0 on full success, 1 on any book failure, 2 if the
    egress is not cleared / the key is missing (fail-closed, a [OPERATOR] gesture is needed). Personal shelf
    families are excluded unless ``include_personal``."""
    from mnemosyne.ports import Sensitivity

    todo = _select_books(
        raw_root, domain=domain, force=force, limit=limit, include_personal=include_personal
    )
    if not todo:
        print("Nothing to distil (every fiche already exists; --force to redo them).")
        return 0

    print(
        f"Haiku campaign: {len(todo)} book(s) to distil (model={model}, {workers} in parallel)."
    )
    if include_personal:
        print(
            "  /!\\ --include-personal: personal families (General/...) ARE included (a conscious choice)."
        )
    suspects = _suspect_files(todo)
    if suspects:  # advisory tripwire (audit MAJEUR-1) - surface for a human eyeball, never block
        print(
            f"\n  /!\\ {len(suspects)} suspect file(s) (too small for a real book) -- PLEASE CHECK:"
        )
        for book, size in suspects:
            print(f"      {size:>7,} B  {book.rel}")
        print(
            "      (likely artifacts / misfiled notes; remove them from the corpus if not real books)."
        )
    if dry_run:  # NO key, NO egress needed - just show the scope
        print()
        for book in todo:
            print(f"  [dry-run] {book.rel}")
        return 0

    # Egress gate FIRST, with a key-free stub runtime (policy + router only): tell user the exact gesture
    # BEFORE any key is needed, and never touch the cloud if it is not cleared (fail-closed, invariant 21).
    from mnemosyne.runtime.bootstrap import bootstrap

    gate_rt = bootstrap()
    ok, reason = _egress_cleared(gate_rt, _public_label(todo[0].domain))
    if not ok:
        print(f"\nFRONTIER CAMPAIGN REFUSED (fail-closed):\n  {reason}", file=sys.stderr)
        return 2
    if not os.environ.get(
        "ANTHROPIC_API_KEY"
    ):  # up-front, before N identical per-book failures (audit MINEUR-2)
        print(
            "\nFRONTIER CAMPAIGN REFUSED (fail-closed):\n  ANTHROPIC_API_KEY is missing -- [OPERATOR]: "
            "`export ANTHROPIC_API_KEY=...` before the campaign (the SDK reads it, the code never sees it).",
            file=sys.stderr,
        )
        return 2

    pool = _WorkerApis(model)
    done: list[object] = []
    failed: list[tuple[object, str]] = []
    lock = threading.Lock()

    def _one(book: object) -> None:
        # Re-check the GLOBAL egress state (policy + allow-list), NOT this book's content: the label is
        # forged `public` by provenance (audit MAJEUR-2 - honest), so this catches a mid-run policy change,
        # not a mislabelled book. The personal exclude + the size tripwire above are the per-file guard.
        cleared, why = _egress_cleared(gate_rt, _public_label(book.domain))  # type: ignore[attr-defined]
        if not cleared:
            with lock:
                failed.append((book, why))
            return
        try:
            distill_one(
                book.mirror,  # type: ignore[attr-defined]
                api=pool.api(),
                model_id=model,
                max_chunks=max_chunks,
                force=force,
                within=Sensitivity.PUBLIC,  # public book -> grant channel sealed as canal A, honest (inv 12)
            )
        except Exception as exc:  # noqa: BLE001 - a book failing never kills the batch (D140 per-book net)
            with lock:
                failed.append((book, f"{type(exc).__name__}: {exc}"))
            return
        with lock:
            done.append(book)

    with cf.ThreadPoolExecutor(max_workers=workers) as executor:
        list(executor.map(_one, todo))

    print(f"\n=== Campaign finished: {len(done)} OK, {len(failed)} failure(s) out of {len(todo)} ===")
    for book, why in failed:
        print(f"  FAILED {book.rel}: {why}")  # type: ignore[attr-defined]
    _print_cost(model, pool.total_usage())
    return 0 if not failed else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Frontier (Haiku) parallel distillation campaign.")
    parser.add_argument("--domain", default=None, help="restrict to one shelf domain (e.g. macro)")
    parser.add_argument("--workers", type=int, default=_DEFAULT_WORKERS, help="parallel books")
    parser.add_argument("--limit", type=int, default=None, help="cap the number of books (pilot)")
    parser.add_argument("--chunks", type=int, default=None, help="cap sections per book (pilot)")
    parser.add_argument("--model", default=_DEFAULT_MODEL, help="frontier model id")
    parser.add_argument("--force", action="store_true", help="re-distil even if a fiche exists")
    parser.add_argument(
        "--dry-run", action="store_true", help="list the books, touch nothing (no key)"
    )
    parser.add_argument("--raw-root", default=str(_RAW_ROOT), help="shelf root to walk")
    parser.add_argument(
        "--include-personal",
        action="store_true",
        help="include personal families (General/...) - a conscious choice; excluded by default",
    )
    args = parser.parse_args(argv)
    return run_campaign(
        raw_root=Path(args.raw_root),
        domain=args.domain,
        workers=args.workers,
        limit=args.limit,
        force=args.force,
        max_chunks=args.chunks,
        model=args.model,
        include_personal=args.include_personal,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    raise SystemExit(main())
