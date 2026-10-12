"""``P8`` — THE CHANNEL FOR A NEED A CHAT CANNOT DECIDE ALONE, **AND IT PIVOTS ANYWAY**.

Two kinds of need, one single channel, because they share the same mechanics and the same failure
mode:

* **``humain``** — what only the operator can decide or execute (the three walls: MONEY ·
  ``system/config/`` · deleting his own data; or a substantive judgment call);
* **``inter-arc``** — what one arc must ask of another. **This does NOT violate the standing ban
  on a direct discussion channel between chats**: that ban refuses the **DIRECT** channel, because
  two chats talking to each other create a second source of truth that nobody arbitrates. Here the
  repository itself IS the channel, the orchestrator arbitrates, and the need is **written, dated,
  tracked by git**. *The ban was right to refuse the direct channel; it proposed nothing in its
  place, and this is the gap being filled.*

**MEASURED ON THIS REPOSITORY BEFORE WRITING A SINGLE LINE**, on the ``.md`` files **git
tracks**, on the pattern "waiting on your/a/the gesture · the operator's gesture · for the operator
to decide · the operator's judgment call": **48 files**, of which **43 outside
``docs/archive/``**, so still alive — with no status, no filing date, no drain, and often with
nobody aware it is waiting.
**The count depends on the pattern, and saying so is part of the count**: a broader pattern
(adding "the operator must/decides/rules on") returns **51**. It is the NARROW pattern that is
quoted here, because only it measures a WAIT rather than a mere mention. The channel had even
already been **reinvented by hand twice in the SAME folder**, under two different names, with no
shared address.
And the archive names the exact cost: *"a gesture falsely attributed to the operator never gets
done, and **nobody knows it is waiting**"*.

**THE CLAUSE THAT MAKES THE WHOLE CHANNEL WORK: ``pivot`` IS MANDATORY, AND EMPTY IT REFUSES.**
A need with no declared pivot isn't an asynchronous channel: it's a **stalled** chat that wrote a
file. The operator's own mandate is *"no stopping, no pausing"* — so the one moment nobody benefits
from vagueness is FILING, and that is where it is required (the same shape as ``RETOUR_ATTENDU``
for parentheses).

**WHAT THIS MODULE DOES NOT PROTECT, AND IT HAS TO BE SAID.** ``docs/signalements/`` is
**gitignored** by design: a report written from a project's own context can name a personal
source, and the barrier is the ``.gitignore``, not a house rule. **THIS channel is TRACKED by
git** — that is its whole point (a sibling chat sees only what git carries, D175) — so **that
barrier does not exist here**. Nothing in this code stops a need from naming a personal source: the
contract says so, **no code enforces it**. *An admission beats a false barrier.*

**THE POPULATION IS INJECTED**: nothing here reads a file or ``os.environ``. The edge is
:mod:`mnemosyne.runtime.besoins_run`.

Prose is French in the private repository (D117), translated to English here for the public
mirror. Neighbors: ``signalements.py`` (project→system, tool failure, D153) ·
``parentheses.py`` (a detour that must COME BACK) · ``frontmatter_status.py`` (the format's single
home).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

#: The two kinds of need. A NAMED SET: an unknown kind REFUSES at filing rather than being
#: accepted and then vanishing from a filter later on.
TYPES: Final = ("humain", "inter-arc")

#: The two statuses. **Deciding never DELETES** (inv. 2): the file stays, its status flips,
#: and the decision is written inside it.
OUVERT: Final = "ouvert"
TRANCHE: Final = "tranche"
STATUTS: Final = (OUVERT, TRANCHE)


class RefusDeDeposer(ValueError):
    """Filing is refused — the reason is in the message, and it names the missing field."""


class RefusDeTrancher(ValueError):
    """Closing is refused — *a closure nobody can verify is not a closure*."""


class SansCanal(RuntimeError):
    """The needs folder does not exist — **an instrument failure, never "zero needs"**.

    An absent channel and an empty channel both render the same "nothing is waiting." The first
    means *nobody was ever able to file anything*; the second, *everything has been decided*. They
    call for opposite gestures.
    """


@dataclass(frozen=True, slots=True)
class Besoin:
    """A need as the judge receives it — what the frontmatter declares, and nothing more.

    ``adresse`` is the file's relative path: it's what a sibling chat opens, and the only thing
    that makes a need actionable. ``statut`` is rendered **exactly as written**, even if unknown:
    a status outside the vocabulary must be NAMED, never vanish from a filter — that's the defect
    measured in ``signalements.py`` (*"an unknown status disappears in silence"*).
    """

    adresse: str
    type_: str = ""
    statut: str = ""
    emetteur: str = ""
    destinataire: str = ""
    pivot: str = ""
    titre: str = ""

    @property
    def lisible(self) -> bool:
        return self.statut in STATUTS and self.type_ in TYPES


def probleme_au_depot(
    *, type_: str, titre: str, question: str, pivot: str, destinataire: str = ""
) -> str | None:
    """Why this need CANNOT be filed — ``None`` when it can.

    Four refusals, and each one closes a measured failure mode:

    1. **unknown type** — a need no reader will ever filter for;
    2. **empty title** — the title becomes the permanent filename, hence the address;
    3. **empty question** — a need that asks nothing never gets decided;
    4. **empty pivot** — *the* refusal this module exists for: without it, a file gets written
       and the chat simply stops;
    5. **``inter-arc`` with no recipient** — a need addressed to nobody is a message in a bottle.
    """
    if type_ not in TYPES:
        return f"unknown type: {type_!r} — expected one of {', '.join(TYPES)}"
    if not titre.strip():
        return "empty title — it's the need's permanent address, a sibling chat opens it by that"
    if not question.strip():
        return "empty question — a need that asks nothing cannot be decided"
    if not pivot.strip():
        return (
            "PIVOT empty — say what you are doing IN THE MEANTIME. A need with no pivot isn't an "
            "asynchronous channel, it's a stalled chat that wrote a file; the mandate is 'no "
            "stopping, no pausing'"
        )
    if type_ == "inter-arc" and not destinataire.strip():
        return "inter-arc need with no recipient — a need addressed to nobody is read by nobody"
    return None


def probleme_a_trancher(besoin: Besoin, decision: str) -> str | None:
    """Why this need CANNOT be decided — ``None`` when it can.

    **The decision is MANDATORY, and it's the half that's missing everywhere else.** A status
    that flips without carrying the decision produces a clean queue and a repository that has
    forgotten *what was decided* — the exact opposite of what this channel exists to hold.
    """
    if besoin.statut == TRANCHE:
        return f"{besoin.adresse} is already decided — don't re-decide it, file a new need instead"
    if besoin.statut != OUVERT:
        return (
            f"{besoin.adresse} carries status {besoin.statut!r}, outside the vocabulary "
            f"({', '.join(STATUTS)}) — repair the file rather than deciding it blind"
        )
    if not decision.strip():
        return (
            "empty decision — a closure nobody can verify is not a closure; "
            "write what was decided, not just that a decision was made"
        )
    return None


@dataclass(frozen=True, slots=True)
class Etat:
    """What's waiting, NAMED; what's decided, counted; what's unreadable, NAMED too."""

    ouverts: tuple[Besoin, ...]
    tranches: int
    #: The needs whose status or type falls outside the vocabulary. **NAMED, never just
    #: counted**: a file no filter catches is invisible forever, and that's the exact failure mode
    #: this field exists to make impossible.
    illisibles: tuple[Besoin, ...]

    @property
    def total(self) -> int:
        return len(self.ouverts) + self.tranches + len(self.illisibles)


def verdict(besoins: Sequence[Besoin]) -> Etat:
    """The channel's state — an EMPTY population is legitimate here, unlike an ABSENT channel.

    **The distinction is real and it is carried by the edge**: zero open needs means *everything
    has been decided*, which is a good state. It's the FOLDER being absent that's a failure, and
    only the edge can see it (:class:`SansCanal`).
    """
    ouverts = tuple(b for b in besoins if b.lisible and b.statut == OUVERT)
    tranches = sum(1 for b in besoins if b.lisible and b.statut == TRANCHE)
    return Etat(
        ouverts=ouverts,
        tranches=tranches,
        illisibles=tuple(b for b in besoins if not b.lisible),
    )


def rendre(etat: Etat) -> str:
    """The state IN WORDS — each open need on its own line, with its pivot.

    The **pivot** is published next to the question: it's what tells the arbiter that this need
    hasn't blocked anyone, so it can be decided **calmly**. Without it, every queue of needs reads
    like an emergency-room queue.
    """
    lignes = [f"NEEDS — {len(etat.ouverts)} open, {etat.tranches} decided."]
    for besoin in etat.ouverts:
        vers = f" → {besoin.destinataire}" if besoin.destinataire else ""
        lignes.append(f"  \U000023F3 [{besoin.type_}] {besoin.titre or besoin.adresse}{vers}")
        lignes.append(f"     {besoin.adresse}")
        lignes.append(f"     pivot: {besoin.pivot or '(not declared)'}")
    if etat.illisibles:
        lignes.append(
            f"\U000026D4 {len(etat.illisibles)} need(s) outside the vocabulary — NAMED here because no "
            "filter will catch them anywhere else:"
        )
        lignes.extend(
            f"   {besoin.adresse} (type={besoin.type_!r} status={besoin.statut!r})"
            for besoin in etat.illisibles
        )
    if not etat.ouverts and not etat.illisibles:
        lignes.append("\U00002705 Nothing is waiting on a gesture: everything filed has been decided.")
    return "\n".join(lignes)


def gabarit(
    *,
    type_: str,
    titre: str,
    question: str,
    pivot: str,
    emetteur: str,
    destinataire: str = "",
    depose_le: str,
) -> str:
    """The file's text — **the single home of its form** (D163), never recopied elsewhere."""
    # **`pivot` LIVES IN THE FRONTMATTER, NOT IN THE BODY, AND THAT'S STRUCTURAL.** It is the
    # only field the ARBITER must see WITHOUT opening the file: a queue of needs where nobody can
    # tell which ones have blocked someone reads like an emergency-room queue. Putting it in the
    # body too would make it a copy, and *a copy drifts* (D163) — so the body carries the question
    # and the decision, which are prose, never a field.
    # **`status:` IN ENGLISH, AND THAT'S A CORRECTION PAID FOR BY REAL USE, NOT AN ANGLICISM.**
    # The first template wrote `statut:`. The very first need actually filed came back out of the
    # queue **"outside the vocabulary", `statut=''`**: the format's shared home
    # (`frontmatter_status.STATUS_RE`) reads `status:`, same as `signalements` and `parentheses`.
    # Writing a second reader for a second spelling would have made **two homes for one format**,
    # and *a contract with two homes drifts*. `set_status` and `entries_with_status` work as-is —
    # that is the whole benefit of the single home (D163).
    #
    # MIRROR NOTE: the frontmatter keys and the body's section headings below are kept in their
    # original French form on purpose. This text is written to disk and later RE-PARSED by this
    # repository's own tooling (the runtime edge's reader and its close-out gesture, which locates
    # the decision by its exact heading) — translating the shape here without translating that
    # reader in the very same gesture would silently break the round trip (rule 9 / rule 4 of the
    # sanitization contract). Only the surrounding comments and this docstring are translated.
    entete = [
        "---",
        f"type: {type_}",
        f"status: {OUVERT}",
        f'titre: "{titre}"',
        f"emetteur: {emetteur}",
        f"destinataire: {destinataire}",
        f'pivot: "{_sur_une_ligne(pivot)}"',
        f"depose_le: {depose_le}",
        "---",
    ]
    corps = [
        "",
        f"# BESOIN — {titre}",
        "",
        "## Ce que je ne peux pas trancher seul",
        "",
        question.strip(),
        "",
        "## La décision",
        "",
        "*(vide tant que ce besoin est ouvert — `make besoin-trancher` l'écrit ici et bascule le",
        "statut. On ne supprime jamais ce fichier : inv. 2.)*",
        "",
    ]
    return "\n".join(entete + corps)


def _sur_une_ligne(valeur: str) -> str:
    """The pivot, flattened and escaped — a scalar YAML field does not survive a line break.

    Without this flattening, a two-line pivot breaks the frontmatter of the file just written:
    the reader then returns ``statut=""``, the need becomes **unreadable**, and it enters no
    queue at all. *The filer would believe they had filed it.*
    """
    plat = " ".join(valeur.split())
    return plat.replace("\\", "\\\\").replace('"', '\\"')
