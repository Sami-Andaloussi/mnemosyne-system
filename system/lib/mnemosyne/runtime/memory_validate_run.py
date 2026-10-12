"""memory_validate_run (item 2 / D115-AV3) — the operator's gesture on ONE queued learning: validate or dismiss.

The ACT half of the "correct" side (counterpart of ``make memory-queue``): validating a proposed learning lets
it reinject (bubble-scoped) into answers (D59-5 / D100); dismissing it CLOSES it for good (D60-2 — never
deleted, never resurfaced). Both are journaled to the human layer BEFORE RAM (D82). Brain-free
(``real_runtime(load_brain=False)``).

    make memory-validate ID=<fiche id>            # validate — an explicit human gesture (D59-5)
    make memory-validate ID=<fiche id> DISMISS=1  # dismiss (invalidate, D60-2)

Validating over this CLI IS the explicit human gesture the D100 net requires (the operator ran the command), so it
clears even a ``perso`` / ``sensible`` learning (``human_validated=True``). An unknown or already-closed id is
reported cleanly, not as a traceback. Code & docstrings English (D117); NOT run in CI (writes the journal)."""

from __future__ import annotations

import argparse
import sys


def main(
    argv: list[str] | None = None,
) -> int:  # pragma: no cover - [OPERATOR] writes the durable journal
    from ..api import CoreApi
    from ..ports import MnemosyneError
    from .bootstrap import real_runtime

    parser = argparse.ArgumentParser(
        prog="make memory-validate",
        description="Validate or dismiss ONE queued living-memory learning by id (item 2).",
    )
    parser.add_argument("fiche_id", help="the id of the learning (see `make memory-queue`)")
    parser.add_argument(
        "--dismiss",
        action="store_true",
        help="reject the learning (invalidate / close, D60-2) instead of validating it",
    )
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    runtime = real_runtime(load_brain=False)
    api = CoreApi(runtime)
    try:
        if args.dismiss:
            api.invalidate_fiche(args.fiche_id)
            print(
                f"[memory-validate] DISMISSED {args.fiche_id!r} — closed (D60-2), never resurfaced."
            )
            return 0
        fiche = api.validate_fiche(args.fiche_id, human_validated=True)
    except MnemosyneError as exc:
        print(f"[memory-validate] refused: {exc}")
        return 1
    print(
        f"[memory-validate] VALIDATED {fiche.id!r} (state={fiche.state}) — it may now reinject into "
        "answers, bubble-scoped (D59-6)."
    )
    return 0


if __name__ == "__main__":  # pragma: no cover - [OPERATOR] entrypoint
    raise SystemExit(main())
