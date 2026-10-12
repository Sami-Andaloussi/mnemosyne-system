"""endorse_run (D156 / D137) — the human-gated door that makes library documents CITABLE.

D137 rests the entire citability of the corpus on one human gesture, and
:meth:`~mnemosyne.api.core_api.CoreApi.endorse_document` implemented it — but nothing could call
it, and it would not have worked if anything had. A project session filed the report; measuring it
showed the hole was deeper than "no target"::

    0 endorsed / 314 documents, and `make search` can never cite a source.

This is the surface, and the ledger behind it (:mod:`~mnemosyne.production.endorsements`) is what
makes the gesture SURVIVE the process::

    make endorse-queue                              # what is citable today, what is not
    make endorse SCOPE=Finance/Assets/commodities   # DRY-RUN: what WOULD become citable
    make endorse SCOPE=... CONFIRM=1                # the gesture

**The lot is the point.** Endorsing 314 books one at a time is not a human gesture — the filing
session said so. So the unit is a SCOPE: a shelf path prefix (``Finance/Assets/commodities``) or a
declared domain. The operator decides the LOT, which is exactly what D137 asks (a human decides,
not a routine), while staying something a person can actually do. Reading a whole shelf and judging
it worth citing is a real act; clicking 314 times is theatre.

**No terminal confirmation here, unlike ``declassify`` — deliberately.** Declassifying moves data
ACROSS the machine boundary (reach toward others, D147 / D74), so it demands a live ``OUI`` typed on
a TTY that a headless agent cannot fake. Endorsing changes how a document is CITED INSIDE the
system: nothing leaves, nothing is destroyed, and the tightening move (``--retract``) is free and
always available. Requiring a TTY here would be ritual, not safety — and would make the gesture
unusable at the only scale it matters. ``CONFIRM=1`` is the gesture; dry-run is the default.

Brick-free (no Qdrant, no model): it reads the library manifest and writes the ledger.

NOTE (public-mirror): the sentences in :func:`render_queue` that carry an asserted substring are
left in French ON PURPOSE and marked ``FROZEN`` below — ``tests/orchestration/test_endorsements.py``
matches them verbatim (``"1 document(s) CITABLES sur 3"``, ``"commodities — 1/2 citables"``,
``"Aucun document indexé"``). Translating one side alone would either redden that suite or, worse,
make an assertion true by construction. Producer and assertion move together, or neither moves."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ..ingest.library import BookStatus, LibraryManifest
from ..ports import DocRole
from ..production.endorsements import observed_actor, DEFAULT_ENDORSEMENTS_PATH, EndorsementLedger

#: Repo root from this module (``system/lib/mnemosyne/runtime/endorse_run.py`` → parents[4]).
_REPO_ROOT = Path(__file__).resolve().parents[4]
_DEFAULT_MANIFEST = _REPO_ROOT / "knowledge" / "library_manifest.json"


def _shelf_documents(manifest_path: Path) -> dict[str, tuple[str, str]]:
    """Every INDEXED book: ``doc id → (shelf path, domain)``. Non-DONE rows have no truth to cite."""
    manifest = LibraryManifest.load(manifest_path)
    return {
        key: (rec.rel, rec.domain)
        for key, rec in manifest.records.items()
        if rec.status is BookStatus.DONE
    }


def select(
    documents: dict[str, tuple[str, str]], *, scope: str | None, domain: str | None
) -> tuple[str, ...]:
    """The doc ids a scope / domain selects, sorted. Pure — the suite drives it directly.

    ``scope`` matches a SHELF PATH PREFIX, so ``Finance/Assets`` takes the whole branch and
    ``Finance/Assets/commodities/books/Storage`` takes one book: one flag covers both the lot and
    the single-document case, without a second code path to keep honest. Matching is
    case-insensitive because the shelf is typed by hand. Neither filter ⇒ everything (the caller
    decides whether that is allowed).
    """
    wanted_scope = (scope or "").strip().lower()
    wanted_domain = (domain or "").strip().lower()
    chosen = [
        doc
        for doc, (rel, dom) in documents.items()
        if (not wanted_scope or rel.lower().startswith(wanted_scope))
        and (not wanted_domain or dom.lower() == wanted_domain)
    ]
    return tuple(sorted(chosen))


def render_queue(
    documents: dict[str, tuple[str, str]], endorsed: frozenset[str], *, limit: int = 12
) -> str:
    """The read side the filing session asked for: what is citable, what is still working material.

    Grouped by DOMAIN rather than listed flat: the endorsement unit is a lot, so the view has to be
    the shape of the decision. Truncated per domain — this is an overview, not a dump.
    """
    if not documents:
        # FROZEN (test_endorsements.py): asserts "Aucun document indexé" verbatim.
        return "# Mnémosyne · endossement\n\nAucun document indexé (lance `make ingest`).\n"
    by_domain: dict[str, list[tuple[str, str]]] = {}
    for doc, (rel, domain) in sorted(documents.items(), key=lambda kv: kv[1][0]):
        by_domain.setdefault(domain, []).append((doc, rel))

    citable = len(endorsed & set(documents))
    lines = [
        "# Mnémosyne · endossement",
        "",
        # FROZEN (test_endorsements.py): asserts "1 document(s) CITABLES sur 3" verbatim.
        f"{citable} document(s) CITABLES sur {len(documents)} indexés "
        f"({len(documents) - citable} en matière-de-travail).",
        "",
        "An unendorsed document stays usable — it comes out of `make search` under "
        "« WORKING MATERIAL », never as a citable source (D137).",
        "",
    ]
    for domain in sorted(by_domain):
        entries = by_domain[domain]
        done = sum(1 for doc, _ in entries if doc in endorsed)
        # FROZEN (test_endorsements.py): asserts "commodities — 1/2 citables" verbatim.
        lines.append(f"## {domain} — {done}/{len(entries)} citables")
        for doc, rel in entries[:limit]:
            mark = "\U00002713" if doc in endorsed else "·"
            lines.append(f"  {mark} {rel}")
        if len(entries) > limit:
            lines.append(f"  … and {len(entries) - limit} more")
        lines.append("")
    lines += [
        "To endorse a lot: `make endorse SCOPE=<path prefix>` (DRY-RUN), then `CONFIRM=1`.",
        "To tighten back: `make endorse SCOPE=... RETRACT=1 CONFIRM=1` (always free).",
    ]
    return "\n".join(lines).rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:
    """Show the queue, or endorse / retract a lot. DRY-RUN unless ``--confirm``."""
    parser = argparse.ArgumentParser(
        prog="endorse",
        description=(
            "Endorse library documents as CITABLE sources (base-de-connaissances, D137). "
            "DRY-RUN by default; --confirm performs the gesture. Non-destructive: retracting is "
            "always free and the journal is append-only."
        ),
    )
    parser.add_argument(
        "--scope", default=None, help="shelf path prefix, e.g. Finance/Assets/commodities"
    )
    parser.add_argument("--domain", default=None, help="a declared domain, e.g. commodities")
    parser.add_argument("--retract", action="store_true", help="tighten back to matière-de-travail")
    parser.add_argument("--confirm", action="store_true", help="perform the gesture (else dry-run)")
    parser.add_argument("--queue", action="store_true", help="show what is citable and what is not")
    parser.add_argument("--manifest", default=str(_DEFAULT_MANIFEST), help=argparse.SUPPRESS)
    parser.add_argument("--ledger", default=str(DEFAULT_ENDORSEMENTS_PATH), help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    documents = _shelf_documents(Path(args.manifest))
    ledger = EndorsementLedger(Path(args.ledger))

    if args.queue or (not args.scope and not args.domain):
        print(render_queue(documents, ledger.endorsed()), end="")
        if not args.queue:
            print(
                "\nNo SCOPE nor DOMAIN given — nothing to endorse. Choose a lot.", file=sys.stderr
            )
            return 2
        return 0

    chosen = select(documents, scope=args.scope, domain=args.domain)
    role = DocRole.MATIERE_DE_TRAVAIL if args.retract else DocRole.BASE_DE_CONNAISSANCES
    verb = "tighten back to matière-de-travail" if args.retract else "endorse as a citable source"
    if not chosen:
        print(f"No document matches (SCOPE={args.scope!r} DOMAIN={args.domain!r}).")
        return 2

    if not args.confirm:
        print(f"[DRY-RUN] {len(chosen)} document(s) to {verb}:")
        for doc in chosen[:12]:
            print(f"  - {documents[doc][0]}")
        if len(chosen) > 12:
            print(f"  … and {len(chosen) - 12} more")
        print("\nNothing was written. Re-run with CONFIRM=1 to perform the gesture.")
        return 0

    author = observed_actor()
    for doc in chosen:
        ledger.record(doc, role, by=author)
    print(f"{len(chosen)} document(s): {verb} — gesture journaled ({ledger.path.name}).")
    print("The journal is append-only: nothing was erased, the history stays readable (inv. 2).")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
