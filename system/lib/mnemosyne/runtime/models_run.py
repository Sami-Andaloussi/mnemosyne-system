"""modeles (C9) — the ONE written answer to "what models do I have?", checked against the disk.

The reason this surface exists is measured, not supposed: an agent of this repo looked for local
models, found no declaration, concluded *"no model installed"* and CARVED that into a plan — with
103 GiB of MLX weights on the disk. The next agent would have repeated it. So the basket is declared
(``system/config/models.toml``) and this prints it, side by side with what the disk actually holds::

    make modeles                       # the basket, and what the disk says about it
    make modeles EMETTRE=1             # emit the [[modeles]] block the disk justifies, to paste

**It reports; it never writes.** ``models.toml`` sits in the protected zone (SE4): adding a line is
the operator's gesture, so ``EMETTRE=1`` hands them the exact bytes the way ``domain-new`` hands its
policy line. Emitted from the SAME scan the check reads, never re-typed — a copy drifts.

**Exit code is 0 even when the reconciliation refuses.** This is a STATUS surface like
``make qdrant`` / ``make plans``, and its job is to SHOW the drift, not to block on it. The gate lives
where a model is actually chosen (:func:`~mnemosyne.production.model_catalog.resolve_model_id`, which
raises), so a red basket here is read, while a red basket there stops the decode. Two different jobs;
conflating them would make ``make modeles`` unusable in exactly the state it exists to describe.

Brick-free, read-only, no model loaded. Code & docstrings English (D117); this public mirror prints
in English too (the private original prints French, D33)."""

from __future__ import annotations

import argparse
import json

from ..production.model_catalog import (
    RAM_BYTES,
    ModelCatalog,
    basket_report,
    emit_declaration,
    reconcile,
    scan_hub,
)

__all__ = ["as_json", "main", "render"]


def as_json(catalog: ModelCatalog, verdict: object) -> str:
    """The SAME basket as :func:`render`, for a reader that is not a human (arc C3 / G8).

    An interface that wants to offer a choice of local model needs the weights, not a paragraph. It
    could scrape :func:`render`, and that copy would drift the first time a sentence changes — so
    the machine-readable form is emitted from the SAME catalogue and the SAME reconciliation, in the
    same process, never re-derived.

    Two things travel that a caller cannot compute alone, and both exist to stop an invention:

    * ``ram_octets`` — the RAM this machine holds. A share of memory means nothing without its
      denominator, and an interface that hard-codes 32 GB lies on any other Mac.
    * ``utilisable`` per model — declared AND whole on disk. A picker that offers a model the
      reconciliation refuses sends its user into :func:`resolve_model_id`'s refusal for no reason.

    No quality, speed or aptitude field: same reason as ``models.toml`` itself — nothing of the sort
    has been measured here, and an invented field is read as a fact by whoever comes next."""
    from ..production.model_catalog import Reconciliation

    assert isinstance(verdict, Reconciliation)  # noqa: S101 - narrow the duck for the type reader
    usable = set(verdict.usable)
    return json.dumps(
        {
            "panier": str(catalog.source),
            "mesure_le": catalog.measured_on,
            "ram_octets": RAM_BYTES,
            "verifie_ms": round(verdict.milliseconds, 2),
            "ok": verdict.ok,
            "modeles": [
                {"id": card.id, "octets": card.octets, "utilisable": card.id in usable}
                for card in catalog.cards()
            ],
            # Refusals TRAVEL WITH IT. A basket rendered without them reads as a healthy basket,
            # and the interface would display twelve choices, some of which will never load.
            "refus": [
                {"genre": r.reason, "detail": r.detail, "phrase": r.label} for r in verdict.refusals
            ],
            # The EXCLUDED population is named, not silently filtered (same rule as `make modeles`).
            "hors_panier": list(verdict.out_of_scope),
        },
        ensure_ascii=False,
    )


def render(catalog: ModelCatalog, verdict: object) -> str:
    """The report: the basket, the verdict, the excluded population, and the COST of the check."""
    from ..production.model_catalog import Reconciliation

    assert isinstance(verdict, Reconciliation)  # noqa: S101 - narrow the duck for the type reader
    total = sum(card.octets for card in catalog.cards())
    lines = [
        "# Mnémosyne · the basket of LOCAL models",
        "",
        basket_report(catalog, verdict),
        "",
        f"Total declared weight: {total / 1024**3:.2f} GiB — RAM is "
        f"{RAM_BYTES / 1024**3:.0f} GB, ONE big model at a time (D95).",
        f"Declaration ↔ disk check, both ways, **disk scan INCLUDED**:"
        f" **{verdict.milliseconds:.2f} ms** — the door stays cheaper than the wall.",
        "",
    ]
    if verdict.ok:
        lines.append("**The basket and the disk agree, both ways.**")
    else:
        lines += [
            f"**{len(verdict.refusals)} refusal(s)** above. The gesture, if a model on disk is missing"
            " from the basket — the zone is protected (SE4), it's YOUR gesture, never mine:",
            "",
            "```bash",
            "make modeles EMETTRE=1     # the exact lines to paste into system/config/models.toml",
            "```",
        ]
    return "\n".join(lines).rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:  # pragma: no cover - CLI side effect
    parser = argparse.ArgumentParser(
        prog="make modeles",
        description="The declared basket of local models, verified against the disk (C9).",
    )
    parser.add_argument(
        "--emettre",
        action="store_true",
        help="print the [[modeles]] block the disk justifies, to paste (writes nothing)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="render the basket as JSON, for an interface (the same one, never re-derived)",
    )
    args = parser.parse_args(argv)
    if args.emettre:
        print(emit_declaration(scan_hub()), end="")
        return 0
    catalog = ModelCatalog.load()
    if args.as_json:
        print(as_json(catalog, reconcile(catalog)))
        return 0
    # ``reconcile(catalog)`` — NOT ``reconcile(catalog, scan_hub())``. Passing a pre-scanned disk
    # leaves the scan OUTSIDE the timer, and the surface then printed **0.02 ms** for a check whose
    # dominant term is the 0.87 ms scan: a cost that hides its own biggest part is the number that
    # makes a slow door look free. The scan happens inside, so the millisecond figure is the whole
    # thing a caller actually pays.
    print(render(catalog, reconcile(catalog)), end="")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
