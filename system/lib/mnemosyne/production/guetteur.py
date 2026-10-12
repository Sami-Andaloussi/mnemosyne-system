"""``P5`` — the watcher's PURE judges: what is a calm window, and **has ``HEAD`` moved?**

Another project's harvest of 2026-09-08, item **P5** (``guetteur_commit.py``): *"wait for a calm
window, **WITH A CEILING**, and check that **``HEAD`` has moved** (never a pipe's exit code)"*.
Signature of the need, picked up by the harvest: *"built THREE TIMES the same evening, separately
(chat-1, x-e6, chat-2) — three independent reinventions in one evening is the signature of a
generic need **with no home**"*.

## Why ``HEAD`` and not the exit code — the fault is mechanical, not hypothetical

In ``sh``, ``git commit -m … | tee journal.log`` returns the status of **``tee``**. ``git commit``
can refuse (hook, nothing to commit, locked index) and the ``$?`` variable still reads ``0``. The
only fact that cannot lie is **the identity of ``HEAD`` before and after**. This is the same class
of defect this repo has already paid for twice and recorded: *"a check that PRINTS without EXITING
WITH A NON-ZERO CODE is not a barrier"* (``.githooks/pre-commit``, header) and *"a SUCCESSFUL
commit can still lose its message"*.

**AND SYMMETRY MATTERS.** The judgment is not only "``HEAD`` unmoved while ``rc == 0``": the
other direction — ``HEAD`` moved while ``rc != 0`` — is **also** a lie, and staying silent about it
would let a commit that actually succeeded be treated as a failure, and therefore replayed. Both
have their own name (:data:`HEAD_IMMOBILE`, :data:`RC_MENTEUR`).

## The population that justifies this module, measured in THIS repo

D175 puts **every** session on ``main`` — *"that's how they see each other"*. Sampled over 30 days:

.. code-block:: text

    commits on main                      1716
    consecutive gaps <=  2 s                26
    consecutive gaps <= 15 s               140
    consecutive gaps <= 60 s               655  / 1715
    median gap                              90 s

Twenty-six times in thirty days, two commits landed less than two seconds apart on a single index.
This is not a hypothesis about contention: it is contention.

**PURE JUDGE**: nothing is read here — no disk, no ``.git``, no clock, no ``os.environ``. What is
**present** and what ``HEAD`` **is worth** are injected by the edge
(:mod:`mnemosyne.runtime.guetteur_commit`).

**The wait ceiling does not live here**: it belongs to :mod:`mnemosyne.production.chrono`
(``G7``), because that is where the rule that keeps waiting from eating into the work budget
lives. *One contract = one single home.*

English prose for this mirror (D117). Decisions: D175 (everyone on ``main``) · invariant 16 (a
bound REFUSES).
"""

from __future__ import annotations

from collections.abc import Collection, Sequence
from dataclasses import dataclass

#: The ``.git`` states that say "this is NOT a calm window," by path name relative to ``.git``.
#: **This is a FROZEN SET, never a count**: a swap (``MERGE_HEAD`` removed, ``BISECT_LOG`` added)
#: would leave ``5 = 5`` and the gate would stay silent.
#:
#: ``index.lock`` is the only one that signals a peer writing *right now*; the other four signal a
#: half-finished operation, where committing on top produces a state nobody wanted. None of them is
#: present during normal operation — measured here: ``0`` merges, ``0`` rebases, ``0`` stashes over
#: 2,020 reflog entries.
VERROUS_QUI_BLOQUENT: frozenset[str] = frozenset(
    {"index.lock", "MERGE_HEAD", "CHERRY_PICK_HEAD", "rebase-merge", "rebase-apply"}
)

#: ``HEAD`` has not moved: nothing was committed, whatever the exit code claims.
HEAD_IMMOBILE = "head_immobile"
#: ``HEAD`` moved but the exit code screamed failure — replaying it would create a duplicate.
RC_MENTEUR = "rc_menteur"
#: Instrument failure: an unreadable ``HEAD`` (repo with no commit, ``git`` absent). Never a
#: green light: without both ``HEAD``s, the question "did it move?" was never asked.
HEAD_ILLISIBLE = "head_illisible"


@dataclass(frozen=True, slots=True)
class Refus:
    """A named refusal, with the two ``HEAD``s that produced it and the exit code observed."""

    genre: str
    head_avant: str
    head_apres: str
    code_retour: int


def verrous_presents(presents: Collection[str]) -> tuple[str, ...]:
    """The blockers actually present, sorted — ``()`` means "calm window."

    We **intersect** with :data:`VERROUS_QUI_BLOQUENT` rather than trusting whatever the edge
    listed: an edge that returned the whole content of ``.git`` would refuse permanently, and an
    edge that returned nothing would pass permanently. The judge decides, not the edge.
    """
    return tuple(sorted(set(presents) & VERROUS_QUI_BLOQUENT))


def fenetre_calme(presents: Collection[str]) -> bool:
    """``True`` if no blocker is present. This is the condition for the **turn granted** (``G7``)."""
    return not verrous_presents(presents)


def raison_dattente(presents: Collection[str]) -> str:
    """The sentence that NAMES what is blocking — *the refusal message names the way out*."""
    bloqueurs = verrous_presents(presents)
    if not bloqueurs:
        return "fenetre calme"
    return "occupe par : " + ", ".join(bloqueurs)


def verdict_du_geste(head_avant: str, head_apres: str, code_retour: int) -> tuple[Refus, ...]:
    """**``P5``'s CORE LINE** — did the gesture really take place?

    The reference fact is ``head_avant != head_apres``. ``code_retour`` is **never** the judge: it
    is only used to name which of the two inconsistencies is being looked at.

    The one-word mutant is ``if code_retour != 0: return (Refus(...),)`` placed first — it turns
    green the moment a ``| tee`` swallows the failure, which is exactly the defect. It is frozen by
    ``test_guetteur.py`` with an unmoved ``HEAD`` AND ``rc == 0``.
    """
    if not head_avant or not head_apres:
        return (
            Refus(
                HEAD_ILLISIBLE,
                head_avant=head_avant,
                head_apres=head_apres,
                code_retour=code_retour,
            ),
        )
    if head_avant == head_apres:
        return (
            Refus(
                HEAD_IMMOBILE, head_avant=head_avant, head_apres=head_apres, code_retour=code_retour
            ),
        )
    if code_retour != 0:
        return (
            Refus(
                RC_MENTEUR, head_avant=head_avant, head_apres=head_apres, code_retour=code_retour
            ),
        )
    return ()


def resume_geste(refus: Sequence[Refus]) -> str:
    """The published sentence. Each refusal says **what the reader must do**, never just the complaint."""
    if not refus:
        return "OK — HEAD a bouge : le geste a eu lieu (le code de sortie n'a pas juge)."
    lignes = []
    for r in refus:
        if r.genre == HEAD_IMMOBILE:
            lignes.append(
                f"REFUS {r.genre} : HEAD est reste sur {r.head_avant[:12]} — RIEN n'a ete commite, "
                f"malgre un code de sortie {r.code_retour}. Un pipe ('| tee', '| head') rend le "
                "statut du DERNIER maillon : ne le crois jamais, relis HEAD."
            )
        elif r.genre == RC_MENTEUR:
            lignes.append(
                f"REFUS {r.genre} : HEAD est passe de {r.head_avant[:12]} a {r.head_apres[:12]} — "
                f"le geste a EU LIEU, malgre un code de sortie {r.code_retour}. "
                "\U000026D4 NE LE REJOUE PAS : tu ferais un doublon."
            )
        else:
            lignes.append(
                f"PANNE D'INSTRUMENT {r.genre} : HEAD illisible (avant={r.head_avant or 'vide'}, "
                f"apres={r.head_apres or 'vide'}). La question « HEAD a-t-il bouge ? » n'a pas ete "
                "posee — ce n'est ni un succes ni un echec du geste."
            )
    return "\n".join(lignes)
