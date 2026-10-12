"""``make bilan`` (workstream 1 - B5) - the EDGE: it takes the measurements, the judge records them.

The judge (:mod:`mnemosyne.production.bilan`) measures nothing. This is where the counters are
pulled - and **the pull is the SAME one the tick uses**, never a second implementation: two sources
for the same figure would diverge, and it is the reader who pays for it.

Three gestures, one file:

* ``make bilan`` - rewrites the state block in :data:`~mnemosyne.production.bilan.CHEMIN`.
* ``make bilan VERIFIER=1`` - touches nothing and **refuses** (``rc 1``) if the written state has drifted.
* the tick calls it in read mode at the start of the next session, so the drift is caught **at the
  exact moment one is about to trust the file**.

``DATE=`` is mandatory when writing outside a real run (tests): a made-up date in a resume file
is exactly the lie this is meant to prevent. Without it, today's date is used.
"""

from __future__ import annotations

import os
import sys
from datetime import date
from pathlib import Path

from ..production.bilan import (
    CHEMIN,
    BilanRefus,
    Mesure,
    premiere_ligne_qui_differe,
    remplacer_l_etat,
    rendre_l_etat,
)
from ..production.parentheses import open_parenthese_count
from ..production.proposals import open_proposal_count
from ..production.rangement import clear_cruft_count
from ..production.signalements import open_signalement_count


def _racine() -> Path:
    depuis_env = os.environ.get("CLAUDE_PROJECT_DIR", "").strip()
    return Path(depuis_env) if depuis_env else Path(__file__).resolve().parents[4]


def mesures(racine: Path) -> tuple[Mesure, ...]:
    """The counters, pulled RIGHT NOW. Each one carries the command that reproduces it.

    **WHAT IS NOT HERE IS SAID, NOT OMITTED.** The red-test count is not pulled here: `make test`
    takes five minutes, and a resume surface that took five minutes would never be run (*a door
    slower than the wall is never taken*). So it appears as a line, with its command and **no
    value** - a named hole, never a silence.

    **THE PATHS ARE THE TICK'S, TO THE LETTER.** These four counters do NOT take the same
    argument shape, and a first run passed all four of them the root: it reported **0 open
    report(s)** where the tick saw **5**. A counter that returns a plausible number for the wrong
    path never turns red on its own."""
    docs = racine / "docs"
    return (
        Mesure(
            "open field reports",
            str(open_signalement_count(docs / "signalements")),
            "make signalements",
        ),
        Mesure(
            "inert proposals pending",
            str(open_proposal_count(racine / "knowledge" / "proposals")),
            "make proposals",
        ),
        Mesure(
            "parentheses still open",
            str(open_parenthese_count(docs / "parentheses")),
            "make parentheses",
        ),
        Mesure(
            "clear cruft to quarantine",
            str(clear_cruft_count(str(racine))),
            "make rangement",
        ),
        Mesure("readable plans and their items", "-> pull it", "make plans"),
        Mesure("red tests", "NOT PULLED HERE (5 min)", "make test"),
        Mesure("the arsenal and its bijection", "-> pull it", "make arsenal"),
    )


def main(argv: list[str] | None = None) -> int:
    """``rc 0`` written or already conforming - ``rc 1`` has drifted (VERIFIER) - ``rc 2`` named refusal."""
    racine = _racine()
    fichier = racine / CHEMIN
    verifier = os.environ.get("VERIFIER", "").strip() == "1" or "--verifier" in (
        argv or sys.argv[1:]
    )
    quand = os.environ.get("DATE", "").strip() or date.today().isoformat()

    try:
        document = fichier.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"REFUSED: the summary is unreadable ({fichier}) - {exc}.", file=sys.stderr)
        print(
            "This is not « nothing to report »: with no file there is no stable address, "
            "and a summary that lives in the conversation is lost at the first compaction.",
            file=sys.stderr,
        )
        return 2

    try:
        bloc = rendre_l_etat(mesures(racine), mesure_le=quand)
        if verifier:
            ou = premiere_ligne_qui_differe(document, bloc)
            if ou is not None:
                print(
                    f"\U000026D4 The state block of {CHEMIN} has DRIFTED - it reads as up to date and is "
                    f"not.\n   First divergence: {ou}\n"
                    "Remedy: `make bilan`. (A stale resumption document is WORSE than none.)"
                )
                return 1
            print(f"{CHEMIN}: the state block is up to date ({quand}).")
            return 0
        fichier.write_text(remplacer_l_etat(document, bloc), encoding="utf-8")
    except BilanRefus as refus:
        print(f"REFUSED: {refus}", file=sys.stderr)
        return 2

    print(f"{CHEMIN}: state block rewritten ({quand}).")
    print("The PROSE was not touched - it is your judgement, not a measurement. Re-read it: the")
    print(
        "summary is the only document whose author writes the final version BEFORE the end of what it describes."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
