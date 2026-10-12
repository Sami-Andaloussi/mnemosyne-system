"""`make rendement` — how many DETECTED lessons actually produced a commit (item I6).

The "detect" half of the loop is wired into the `Stop` hook; this one is **not**, and that is a
measured choice: the measurement covers **the machine's entire history**, not one task. Printing
it at every task end would repeat the same global table indefinitely — *exactly how a block
turns into furniture*, the defect D155 exists to prevent. It is **pulled** on demand.

Both populations already existed, written by no one on purpose:

* the **signals** — the host copies the hook's block into the transcript, so every task end where
  something was detected is timestamped there;
* the **commits** — the memory repo's git history, plus ``make remember``'s own ledger.

**THE CONTROL WITNESS IS NOT OPTIONAL**: these are the task ends where the hook fired its ritual
and detected **nothing**. Same boundary, same instant, the only difference is the signal. Without
it, "80% of signals are followed by a commit" means nothing — commits are frequent, so almost any
instant is "followed by a commit". :func:`~..production.rendement.mesurer` returns both or
neither, by its own signature.

**THIS COMMAND ALWAYS SAYS WHAT IT SEARCHED**, like ``make lecons``: it reads transcripts
looking for the header the hook prints, and if that header ever changes, the measurement would
silently drop to zero and read as "the loop no longer detects anything". The signal's header is
therefore **derived from the module itself** (never copied), and an empty population **refuses**
instead of printing a table of zeros. *Two absences of measurement compare equal.*

No model, no network, no cost: everything is local and in the standard library (D126). Nothing
leaves the machine (invariant 1) and nothing is written (invariant 2). Code in English (D117);
what the operator reads is French.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path
from typing import Final

from ..production.rendement import mesurer, rendre
from ..production.review_signals import Signal, render_review
from ..production.sessions import DEFAULT_TRANSCRIPT_ROOT, default_project_dir

_REPO_ROOT: Final = Path(__file__).resolve().parents[4]

#: The generic ritual, which every consequential task-end carries. It is the CONTROL population's
#: marker, and unlike the signal header it cannot be derived — it is written inline in the hook.
#: So it is checked rather than trusted: zero matches means the wording moved, and the command says
#: so instead of publishing an empty measurement.
#: THIS NEEDLE MUST MATCH WHAT THE HOOK ACTUALLY EMITS, and it did not: the hook says
#: `[Mnemosyne - essence ritual]` while this constant still looked for the pre-translation label.
#: `populations()` therefore returned `with=0 without=0` on a REAL transcript and `main()` took the
#: refusal branch -- silently, because the test built its own fixture around the OLD label and so
#: fabricated the world it expected. Measured 2026-09-09; found by a sibling chat, not by any gate.
#: NO migration window is needed HERE, and the reason is specific to this repository: a fresh
#: clone has no historical transcript carrying the old label, so searching two forms would guard
#: against a past that does not exist on this side. A repository that DOES hold old transcripts
#: must search both forms until none of them is alive -- that is a data migration, not a rename.
_RITUEL: Final = "essence ritual"

#: Where ``make remember`` files what it captured, and where the memory repo lives relative to the
#: transcripts. Both are read, never written.
_PROPOSALS: Final = _REPO_ROOT / "system" / "state" / "proposals.jsonl"
_MEMOIRE: Final = "memory"


def _entete_du_signal() -> str:
    """The signal block's own header, DERIVED from the renderer rather than copied.

    A constant copied from the hook's output is a second source that drifts silently: the day the
    wording changes, this command measures zero and reads as *"the loop detects nothing any more"*.
    Asking the renderer removes the second source entirely.
    """
    rendu = render_review((Signal(kind="correction", quote="x", advice="y"),))
    return rendu.split("]", 1)[0].split("·", 1)[-1].strip()


def _horodatage(brut: object) -> datetime | None:
    try:
        return datetime.fromisoformat(str(brut).replace("Z", "+00:00")).astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def _textes(chemin: Path) -> Iterator[tuple[str, datetime | None]]:
    """Every text of a transcript with its stamp — tolerant, a torn line costs only itself.

    **DO NOT replace with ``sessions._message_text``, and this comment is the only thing
    protecting this function.** The neighboring module ``production/delegations.py`` states the
    opposite rule in so many words — *"borrowed from sessions rather than reimplemented: two
    parsers of the same format drift apart"* — and a well-meaning cleanup will apply that rule
    here.

    **It would lose the measurement.** ``_message_text`` strips the blocks the HOST INJECTS
    (``<system-reminder>`` and friends) — and **the block this command looks for IS an injected
    block**. Measured by an isolated audit over 41 transcripts, **340,311 events**: a single
    divergence between the two extractions, and it runs in this direction — ``_message_text``
    does not see the marker, this one does. *A justified duplication whose justification is
    written nowhere is a deletion waiting for its own tidier.*
    """
    try:
        handle = chemin.open("r", encoding="utf-8", errors="replace")
    except OSError:
        return
    with handle:
        for ligne in handle:
            depouillee = ligne.strip()
            if not depouillee:
                continue
            try:
                evenement = json.loads(depouillee)
            except json.JSONDecodeError:
                continue
            if not isinstance(evenement, dict):
                continue
            contenu = (evenement.get("message") or {}).get("content")
            if isinstance(contenu, str):
                texte = contenu
            elif isinstance(contenu, list):
                texte = "".join(
                    bloc.get("text", "") for bloc in contenu if isinstance(bloc, dict)
                )
            else:
                continue
            if texte:
                yield texte, _horodatage(evenement.get("timestamp"))


def populations(dossier: Path) -> tuple[list[datetime], list[datetime]]:
    """``(task ends WITH a signal, task ends WITHOUT)`` — deduplicated by (file, instant).

    Deduplication is not caution for its own sake: the host **replays** the block in the context
    of later turns, so counting occurrences would inflate the population by a factor that has
    nothing to do with the number of task ends. Measured: 73 occurrences for **55** distinct
    instants.
    """
    entete = _entete_du_signal()
    avec: set[tuple[str, datetime]] = set()
    sans: set[tuple[str, datetime]] = set()
    for chemin in sorted(dossier.glob("*.jsonl")):
        for texte, instant in _textes(chemin):
            if instant is None or _RITUEL not in texte:
                continue
            (avec if entete in texte else sans).add((chemin.name, instant))
    return sorted(t for _, t in avec), sorted(t for _, t in sans)


def depots(dossier_memoire: Path) -> list[datetime]:
    """When a lesson actually landed: a memory commit, or a `make remember`."""
    trouves: list[datetime] = []
    try:
        journal = subprocess.run(
            ["git", "-C", str(dossier_memoire), "log", "--format=%aI"],
            capture_output=True,
            text=True,
            timeout=30,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        journal = ""
    trouves += [t for t in (_horodatage(x) for x in journal.split()) if t]
    if _PROPOSALS.exists():
        for ligne in _PROPOSALS.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                entree = json.loads(ligne)
            except json.JSONDecodeError:
                continue
            instant = _horodatage(entree.get("at") or entree.get("ts") or "")
            if instant:
                trouves.append(instant)
    return sorted(trouves)


def main(argv: list[str] | None = None) -> int:
    analyseur = argparse.ArgumentParser(description=__doc__)
    analyseur.add_argument("--projet", default=None, help="the transcripts folder to read")
    args = analyseur.parse_args(argv)

    dossier = DEFAULT_TRANSCRIPT_ROOT / (args.projet or default_project_dir())
    if not dossier.is_dir():
        print(f"\U000026D4 No transcript under {dossier} — nothing to measure.", file=sys.stderr)
        return 1

    avec, sans = populations(dossier)
    # REFUSE rather than publish an empty table. A null population does not mean "the loop
    # detects nothing": it probably means the header being searched for has moved. Both read the
    # same on a table of zeros, and that is how a measurement stops being taken without anything
    # turning red.
    #
    # `or`, NOT `and` — fixed after an isolated audit. The `and` version only refused when
    # BOTH were empty; a single empty population passed the gate and produced **-98.0 pts**, a
    # catastrophic verdict manufactured from an ABSENCE. And it was reachable without any malice:
    # a fresh machine where the ritual fired without a single signal ever being detected produces
    # exactly this shape. *Three documents published the guarantee "refuses on an empty
    # population"; the code only held half of it.*
    if not avec or not sans:
        print(
            f"\U000026D4 No task end found in {len(list(dossier.glob('*.jsonl')))} transcript(s).\n"
            "   This is NOT « the loop detects nothing » — it means the marker being searched for "
            "no longer matches.\n"
            f"   Searched: « {_RITUEL} » (the ritual) and « {_entete_du_signal()} » (the signal).",
            file=sys.stderr,
        )
        return 1

    # Computed ONCE: calling it twice would rerun a full `git log` plus a re-read of
    # `proposals.jsonl` (84 KB) on every shot — 71 ms wasted, measured by the audit.
    deposes = depots(dossier / _MEMOIRE)
    tableau = rendre(mesurer(avec, sans, deposes))
    print(tableau)
    print()
    print(
        f"Searched: {len(list(dossier.glob('*.jsonl')))} transcript(s) · "
        f"{len(avec)} task end(s) with a signal · {len(sans)} without · "
        f"{len(deposes)} deposit(s). "
        "A command that does not say what it searched lets an empty index pass for a "
        "library."
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
