"""``make besoin`` / ``make besoins`` / ``make besoin-trancher`` (P8) — the EDGE of the needs channel.

The judge (:mod:`mnemosyne.production.besoins`) neither reads nor writes anything. Here, and only
here, do we touch disk — through the format's shared home
(:mod:`mnemosyne.production.frontmatter_status`), never through a second frontmatter reader:
*a contract with two homes drifts*, and this repo has already paid for one.

Three gestures:

* ``--deposer`` — writes ONE file per need (never a single multi-author queue: that is the hot
  spot measured on the research project, 4 conflict causes out of 5) then **hands back control right away**.
* with no argument — publishes what is waiting, with the **pivot** of each.
* ``--trancher CHEMIN --decision "..."`` — flips the status AND writes the decision into the body.
  **Deletes nothing** (inv. 2).

**THIS CHANNEL IS TRACKED BY GIT**, unlike ``docs/signalements/`` which is gitignored by
design. This is deliberate and is its whole point — a sibling chat only sees what git carries
(D175) — but it means **the `.gitignore` barrier that protects field reports does not exist
here**: nothing stops a need from naming a personal source. The contract says so; no code
enforces it.

French prose (D117).
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import date
from pathlib import Path

from ..production.besoins import (
    TRANCHE,
    TYPES,
    Besoin,
    RefusDeDeposer,
    RefusDeTrancher,
    SansCanal,
    gabarit,
    probleme_a_trancher,
    probleme_au_depot,
    rendre,
    verdict,
)
from ..production.frontmatter_status import (
    create_dated_entry,
    field_of,
    read_text,
    set_status,
    status_of,
    today_stamp,
)

#: Where needs live. One folder, **one file per need** — see the docstring.
DOSSIER = Path("docs") / "besoins"

#: What is NOT a need in this folder: the contract itself.
PAS_UN_BESOIN = frozenset({"README.md"})


def _racine() -> Path:
    depuis_env = os.environ.get("CLAUDE_PROJECT_DIR", "").strip()
    return Path(depuis_env) if depuis_env else Path(__file__).resolve().parents[4]


def lire(dossier: Path) -> tuple[Besoin, ...]:
    """The needs on the channel — raises :class:`SansCanal` if the FOLDER does not exist.

    **A MISSING FOLDER IS NOT AN EMPTY CHANNEL.** The latter says "everything has been
    decided" (a good state); the former says "no one has ever been able to file anything" (a
    breakage). Confusing the two would render "nothing is waiting" on a channel that does not
    even exist.
    """
    if not dossier.is_dir():
        raise SansCanal(
            f"{dossier} does not exist — this is NOT « no need is waiting », it is an "
            "absent channel: no one has ever been able to file anything there"
        )
    trouves: list[Besoin] = []
    for chemin in sorted(dossier.rglob("*.md")):
        if chemin.name in PAS_UN_BESOIN:
            continue
        trouves.append(
            Besoin(
                adresse=str(chemin.relative_to(dossier.parent.parent)),
                type_=field_of(chemin, "type"),
                statut=status_of(chemin) or "",
                emetteur=field_of(chemin, "emetteur"),
                destinataire=field_of(chemin, "destinataire"),
                pivot=field_of(chemin, "pivot"),
                titre=field_of(chemin, "titre"),
            )
        )
    return tuple(trouves)


def deposer(
    dossier: Path,
    *,
    type_: str,
    titre: str,
    question: str,
    pivot: str,
    emetteur: str,
    destinataire: str = "",
    quand: str | None = None,
) -> Path:
    """Writes ONE need and returns its path — raises :class:`RefusDeDeposer` if the judge refuses.

    The judge is consulted **before** any write: a file written and then judged bad would leave
    an unreadable entry in a channel that is never cleaned up (inv. 2).
    """
    refus = probleme_au_depot(
        type_=type_, titre=titre, question=question, pivot=pivot, destinataire=destinataire
    )
    if refus is not None:
        raise RefusDeDeposer(refus)
    stamp = quand or today_stamp()
    return create_dated_entry(
        dossier,
        stamp=stamp,
        title=titre,
        body=gabarit(
            type_=type_,
            titre=titre,
            question=question,
            pivot=pivot,
            emetteur=emetteur,
            destinataire=destinataire,
            depose_le=stamp,
        ),
    )


def trancher(chemin: Path, decision: str, *, dossier: Path, quand: str | None = None) -> Path:
    """Flips the status AND records the decision — raises :class:`RefusDeTrancher` if the judge refuses.

    **THE DECISION IS WRITTEN INTO THE BODY, NEVER ONLY INTO THE STATUS.** A channel where
    *what was decided* can no longer be read back is a channel that has only served once.
    """
    besoin = Besoin(
        adresse=str(chemin),
        type_=field_of(chemin, "type"),
        statut=status_of(chemin) or "",
        pivot=field_of(chemin, "pivot"),
        titre=field_of(chemin, "titre"),
    )
    refus = probleme_a_trancher(besoin, decision)
    if refus is not None:
        raise RefusDeTrancher(refus)
    stamp = quand or date.today().isoformat()
    texte = read_text(chemin)
    marqueur = "## La décision"
    if marqueur not in texte:
        raise RefusDeTrancher(
            f"{chemin} does not carry a « {marqueur} » section — refusing to invent a "
            "structure inside a file a human wrote"
        )
    tete, _, queue = texte.partition(marqueur)
    chemin.write_text(
        f"{tete}{marqueur}\n\n**Decided on {stamp}.** {decision.strip()}\n"
        f"\n<!-- previous section below, kept (inv. 2) -->\n{queue.lstrip()}",
        encoding="utf-8",
    )
    return set_status(chemin, TRANCHE, extra_lines=(f"tranche_le: {stamp}",))


def besoins_ouverts(racine: Path) -> int:
    """How many needs are waiting — **for the tick**. ``0`` if the channel does not exist yet.

    **The fail-open lives here and NOWHERE ELSE, and it is deliberate**: the tick asks
    this question at every session start, including on a fresh clone where the folder does not
    exist. Letting it raise would block the session. The surfaces a human reads (:func:`lire`) do
    refuse, however.
    """
    try:
        return len(verdict(lire(racine / DOSSIER)).ouverts)
    except SansCanal:
        return 0


def main(argv: list[str] | None = None) -> int:
    """``rc 0`` published/filed/decided · ``rc 1`` judge refusal · ``rc 2`` instrument failure."""
    analyseur = argparse.ArgumentParser(description="The needs channel (P8).")
    analyseur.add_argument("--deposer", action="store_true")
    analyseur.add_argument("--type", default="", choices=("", *TYPES))
    analyseur.add_argument("--titre", default="")
    analyseur.add_argument("--question", default="")
    analyseur.add_argument("--pivot", default="")
    analyseur.add_argument("--emetteur", default="")
    analyseur.add_argument("--destinataire", default="")
    analyseur.add_argument("--trancher", metavar="CHEMIN", default="")
    analyseur.add_argument("--decision", default="")
    arguments = analyseur.parse_args(sys.argv[1:] if argv is None else argv)
    racine = _racine()
    dossier = racine / DOSSIER

    if arguments.deposer:
        try:
            ecrit = deposer(
                dossier,
                type_=arguments.type,
                titre=arguments.titre,
                question=arguments.question,
                pivot=arguments.pivot,
                emetteur=arguments.emetteur,
                destinataire=arguments.destinataire,
            )
        except RefusDeDeposer as refus:
            print(f"REFUSED: {refus}.", file=sys.stderr)
            return 1
        except OSError as panne:
            print(f"REFUSED: the need could not be written — {panne}.", file=sys.stderr)
            return 2
        print(f"Need filed: {ecrit.relative_to(racine)}")
        print("PIVOT NOW. This channel is asynchronous: do not wait on it.")
        return 0

    if arguments.trancher:
        chemin = Path(arguments.trancher)
        if not chemin.is_absolute():
            chemin = racine / chemin
        try:
            trancher(chemin, arguments.decision, dossier=dossier)
        except RefusDeTrancher as refus:
            print(f"REFUSED: {refus}.", file=sys.stderr)
            return 1
        except (OSError, ValueError) as panne:
            print(f"REFUSED: {panne}.", file=sys.stderr)
            return 2
        print(f"Decided: {chemin.name} — the decision is in the file, it is not deleted.")
        return 0

    try:
        etat = verdict(lire(dossier))
    except SansCanal as panne:
        print(f"REFUSED: {panne}.", file=sys.stderr)
        return 2
    print(rendre(etat))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
