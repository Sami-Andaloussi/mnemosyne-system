"""``P4`` — the line-count ceiling **AS A GATE**, which forces **NON-DESTRUCTIVE** rotation.

Another project's harvest of 2026-09-08, item **P4**: *"a non-destructive invariant holds by making
the destructive gesture **more costly than archiving**, never by forbidding it in writing."*
 **That project's own number (400) stays with that project** — it is the SHAPE that transfers, and the harvest
itself classes it ``SPECIFIC`` (``S1``: *"61 files stuck at the ceiling, 15 exactly at 400/400"*).

## What breaks without it — A4, measured, never assumed

This repository's own operating rules **require** that a compacted chat **RE-READ** its journal
(*"a compacted chat re-reads all three"*), and that this same journal be **APPEND-ONLY**. Two
rules that, together, guarantee that a file grows without end while a protocol requires that it be
re-read. Measured in this repo:

.. code-block:: text

 journal (chat 1) 6874 lines 466 283 o 207 commits
 journal (chat 2) 7199 lines 508 472 o 252 commits
 journal (chat 3) 7040 lines 509 429 o 217 commits
 observations log 6038 lines 391 629 o 152 commits

**The prescribed re-reading became impossible, silently, within four days.** And the call was left
OPEN: this repo's own end-of-session log raised it **three times**, the first time flagging
*"chat-1.md and chat-2.md are over 500 lines,"* itself noting the trap —
*"a ceiling that refuses stops all three chats at once."* Nobody decided; the files grew **×14**.
That is exactly the failure the harvest describes: *nobody remembered it, the gate would have.*

## The ceiling does not STEER, because the way out is FREE

This repo's own governance rules forbid any ceiling that does not name what breaks without it, and
recall D165: *"a ceiling on generated output does not bound, it STEERS."* Here it steers nothing,
and the reason is mechanical: **nobody is ever asked to write less**, they are asked to
**turn the page**. The refusal names the archive path to create; archiving is a partial ``git mv``
that loses not one byte (inv. 2).

 **AND THIS IS THE HALF THAT MATTERS.** A ceiling ALONE teaches the wrong way out: under refusal,
the cheapest move is to **cut the start of the file**. That is why the second clause,
:data:`COUPE_SANS_ARCHIVE`, refuses any shrink whose removed lines are not found in an archive from
the **same** commit. The destructive gesture then becomes **more expensive** than archiving — what
the harvest asked for, taken literally.

## The ceiling sweep — it is not invented (``PLANCHER.md`` method)

Replayed over the real life of the four files (828 versions), "how many rotations would this
ceiling have forced?":

.. code-block:: text

 ceiling 400 500 800 1000 1500 2000 2500 3000 4000 5000
 rotations 66 53 31 26 16 12 8 8 4 4

**2000** is chosen: each journal rotates **3 times** over the 4 measured days — roughly one
rotation every ~69 journal commits, the order of magnitude of "once a day." At 400 (that project's
own number) that is 66 rotations, ~16 a day: pure friction, and exactly the regime ``S1`` condemns. At
4000, a journal reaches ~276 KB before rotating even once — the prescribed re-reading stays
impossible, so the ceiling no longer holds what breaks without it.

## The cut tolerance is derived too

Of the **828** commits that touched these four files: **818** delete **nothing**, 7 delete 1 line,
2 delete 2, 1 deletes 4. **Maximum observed: 4.** :data:`TOLERANCE_COUPE_LIGNES` is ``10`` — 2.5×
the worst legitimate case ever seen, and three orders of magnitude under a rotation (thousands of
lines). *A tolerance drawn from the population, not from a guess.*

 **PURE JUDGE**: the population is **injected** (path, indexed lines, lines in ``HEAD``, lines
gained by archives in the same commit). No disk access, no ``os.environ``, no call to git — all of
that lives at the edge (:mod:`mnemosyne.runtime.plafond_rotation_run`).

 **WHAT THIS MODULE DOES NOT COVER, AND WHY** — an undeclared scope is a false scope:

* The running decisions log (addition share 0.989) — **knowingly excluded**: its decisions are
 ADDRESSES cited throughout the corpus (e.g. "D175"). Turning the page there would move citation
 targets, and the cost of archiving would stop being free — the reasoning above would collapse.
* This repo's own end-of-session state file (addition share **0.827**: +2071/−432 over 30 days) —
 this is not a journal, it is **current state** that gets rewritten in place. Archiving it would
 lose the state, not history.
* The plan-document tree — already governed by ``plan_format`` and the ``pre-commit`` gate. Two gates on
 the same file eventually contradict each other.
* ``CLAUDE.md`` and this repo's own onboarding notes — read at every startup, so already under the
 opposite pressure.

English throughout for this mirror. Decisions: inv. 2 (non-destructive) · D74 (deletion is the
operator's own gesture) · A4 / D165 (a ceiling names what breaks without it).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

#: The production ceiling, in lines, for the APPEND-ONLY per-chat journal files (see :data:`PREFIXE_COUVERT`).
#: Derived from the sweep above, never copied from the other project (whose 400 is classed ``SPECIFIC``).
PLAFOND_LIGNES = 2000

#: How many lines a covered file can lose without it counting as a rotation. Derived from the
#: worst legitimate case ever observed (4 lines in one commit, out of 828 commits), ×2.5.
TOLERANCE_COUPE_LIGNES = 10

#: The covered paths, **by name pattern**, exactly as this repository's own operating rules
#: declare them APPEND-ONLY ("The shape of a journal (written by the chat, APPEND-ONLY)").
#: This is a list of PATTERNS, not files: ``journal-chat-4.md`` will be born covered the day a
#: fourth chat exists — *a list of files always forgets one more file.*
PREFIXE_COUVERT = "docs/postes/"
NOMS_COUVERTS: tuple[str, ...] = ("journal-chat-", "OBSERVATIONS.md")

#: Where rotations land. An archive is **never** covered by the ceiling: it is closed by
#: construction, and applying the ceiling to it would loop the rotation forever.
DOSSIER_ARCHIVE = "docs/postes/archive/"

#: The file is over the ceiling — the refusal NAMES the archiving gesture to perform.
PLAFOND_DEPASSE = "plafond_depasse"
#: The file shrank without an archive in the same commit collecting the lines it lost.
COUPE_SANS_ARCHIVE = "coupe_sans_archive"
#: Instrument failure: no covered file in the population. Never a green.
POPULATION_VIDE = "population_vide"


@dataclass(frozen=True, slots=True)
class Fichier:
    """A covered file, exactly as the edge read it from the **INDEX** (never from disk).

    ``lignes_avant`` is ``None`` for a file born in this commit — it could not have lost anything
    yet, and confusing that with ``0`` would fabricate a false cut on every creation.
    """

    chemin: str
    lignes: int
    lignes_avant: int | None
    #: Lines ADDED to the archives in the SAME commit — the edge sums them over all of
    #: :data:`DOSSIER_ARCHIVE`, never per single file: a rotation can land in several pieces,
    #: and requiring one archive per journal would invent a convention.
    lignes_archivees: int


@dataclass(frozen=True, slots=True)
class Refus:
    """A named refusal, with the number and, for an overshoot, the proposed archive path."""

    genre: str
    chemin: str
    lignes: int
    borne: int
    archive_proposee: str = ""


def est_couvert(chemin: str) -> bool:
    """The scope predicate — **a question of FORM, never a table of paths**.

 The pattern is looked for on the **BASE NAME**, at any depth under :data:`PREFIXE_COUVERT`: a
 file such as ``<year>/journal-chat-9.md`` nested under it is morally a journal and must be
 covered. *A list of
 locations always forgets one more location.*

 **This is THE choice that makes the archive clause load-bearing.** A first draft compared
 the pattern against the relative path (``archive/journal-chat-1-….md``), which starts with no
 pattern at all: the ``DOSSIER_ARCHIVE`` guard was then a **dead branch** — a saboteur removed
 it and the 92 witnesses stayed green. Now the base name of an archive **matches**
 ``journal-chat-``, and only this line stops the rotation from refusing itself.
 """
    if chemin.startswith(DOSSIER_ARCHIVE):
        return False
    if not chemin.startswith(PREFIXE_COUVERT):
        return False
    nom = chemin.rsplit("/", 1)[-1]
    return any(nom.startswith(motif) or nom == motif for motif in NOMS_COUVERTS)


def archive_proposee(chemin: str, jour: str) -> str:
    """The archive path that the refusal NAMES — *the refusal message names the way out*.

    ``jour`` is injected (``YYYY-MM-DD``): a judge that read the clock would no longer be pure,
    and its witness would turn false the next day.
    """
    nom = chemin.rsplit("/", 1)[-1].removesuffix(".md")
    return f"{DOSSIER_ARCHIVE}{nom}-{jour}.md"


def verdict(
    fichiers: Sequence[Fichier],
    *,
    plafond: int = PLAFOND_LIGNES,
    tolerance: int = TOLERANCE_COUPE_LIGNES,
    jour: str = "YYYY-MM-DD",
) -> tuple[Refus, ...]:
    """The refusals, **cumulative** — one file can be judged on both clauses.

 **NO EARLY RETURN between the two clauses**, and that is deliberate: *a check placed first
 adds a cause, it never removes one*. A first draft that returned the cut alone would have
 silenced the neighbor's overshoot in the same commit.

 ``POPULATION_VIDE`` comes out ALONE: a gate that saw no covered file judged nothing, and
 ``()`` would let it pass for green.
 """
    couverts = tuple(f for f in fichiers if est_couvert(f.chemin))
    if not couverts:
        return (Refus(POPULATION_VIDE, chemin="", lignes=0, borne=plafond),)

    refus: list[Refus] = []
    for f in sorted(couverts, key=lambda x: x.chemin):
        if f.lignes_avant is not None:
            perdues = f.lignes_avant - f.lignes
            if perdues > tolerance and f.lignes_archivees < perdues:
                refus.append(
                    Refus(
                        COUPE_SANS_ARCHIVE,
                        chemin=f.chemin,
                        lignes=perdues,
                        borne=f.lignes_archivees,
                    )
                )
        if f.lignes > plafond:
            refus.append(
                Refus(
                    PLAFOND_DEPASSE,
                    chemin=f.chemin,
                    lignes=f.lignes,
                    borne=plafond,
                    archive_proposee=archive_proposee(f.chemin, jour),
                )
            )
    return tuple(refus)


def chemins_refuses(refus: Sequence[Refus]) -> frozenset[str]:
    """The **SET** of refused paths, never their count (a swap would leave ``2 = 2``)."""
    return frozenset(r.chemin for r in refus if r.chemin)


def resume(
    fichiers: Sequence[Fichier], refus: Sequence[Refus], *, plafond: int = PLAFOND_LIGNES
) -> str:
    """The published sentence. Each refusal carries **the gesture that lifts it**, never just the
    complaint."""
    if any(r.genre == POPULATION_VIDE for r in refus):
        return (
            "INSTRUMENT FAILURE — no covered file in the measured population. "
            f"Covered: {PREFIXE_COUVERT}{{{', '.join(NOMS_COUVERTS)}}} outside {DOSSIER_ARCHIVE}. "
            "A ceiling over an empty population would pass GREEN without having looked at anything."
        )
    couverts = [f for f in fichiers if est_couvert(f.chemin)]
    tete = f"{len(couverts)} file(s) covered, ceiling {plafond} lines — " + " · ".join(
        f"{f.chemin.rsplit('/', 1)[-1]} {f.lignes} ln."
        for f in sorted(couverts, key=lambda x: x.chemin)
    )
    if not refus:
        return tete + "\nOK — under the ceiling, and no un-archived cut."
    lignes = [tete, "REFUSALS:"]
    for r in refus:
        if r.genre == PLAFOND_DEPASSE:
            lignes.append(
                f"  - {r.genre}: {r.chemin} is {r.lignes} lines for a ceiling of {r.borne}. "
                f"TURN THE PAGE (never erase, inv. 2): move the start to "
                f"{r.archive_proposee}, in THIS commit."
            )
        else:
            lignes.append(
                f"  - {r.genre}: {r.chemin} loses {r.lignes} lines and this commit's archives "
                f"only gain {r.borne}. A rotation MOVES, it does not cut — "
                f"put the removed lines under {DOSSIER_ARCHIVE} in the SAME commit."
            )
    return "\n".join(lignes)
