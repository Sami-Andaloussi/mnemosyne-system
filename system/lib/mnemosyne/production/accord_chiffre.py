"""``P6`` — A COMPUTED NUMBER COPIED INTO PROSE VISITS **EVERY SITE**, NEVER A TOTAL.

A number that a command can recompute, and that prose copies elsewhere, drifts **far from its
source**. The naive fix — count the copies and compare the total — is **exactly the real case that
passes green**: *a total that agrees on one side and is wrong on the other*. Two documents saying
`28` and `26` average to 27; one document that lost one and another that gained one produce the
same count. **So this module never returns a total: it returns a list of ADDRESSES**
``document:line``, and it refuses as soon as a single one disagrees.

**THE TRAP THIS MODULE EXISTS TO AVOID, WRITTEN BEFORE THE CODE: A NUMBER IN A DOCUMENT IS NOT
A PREDICATE — IT HIDES THREE.**

* a **LIVE CLAIM** — "this repository has 27 invariants": true today or false today;
* a **DATED RECORD** — "on 2026-07-02, the suite reported 27 green invariants": true forever, and
  correcting it would **falsify an archive** (inv. 2);
* a **TARGET** — "we want 30 invariants": neither true nor false, an intention.

A gate that conflates them has only two outcomes, both bad: it **rewrites dated records** to stay
green, or it **requires nothing** so as not to touch them. Here the distinction is **STRUCTURAL —
carried by the document's PATH, never by the line's text** (:func:`portee`): a text detector would
count citations, a mistake this repository has already paid for six times.

**MEASURED ON THIS REPOSITORY BEFORE WRITING A LINE** — the invariant count, computable from the
project's own invariant registry, **copied 41 times across 30 files tracked by git**. The
docstring of :mod:`mnemosyne.production.derives` already admitted it outright: *"WHAT IT DOES NOT
JUDGE, AND MUST BE SAID: the count of 27 invariants, copied into some twenty files. […] No gate
here covers it."* **This is that gate.**

**THE POPULATION IS INJECTED, NEVER DISCOVERED**: nothing here reads a file or ``os.environ``.
The boundary is :mod:`mnemosyne.runtime.accord_chiffre_run`.

Source prose was originally written in French (repository convention D117) and is translated to
English for this public mirror. Neighbors: ``derives.py`` (the derivatives of the decision corpus)
· ``bilan.py`` (a derived block that recomputes itself and names the FIRST diverging line).
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Final

#: A claim about TODAY: it must agree with the recomputed number.
VIVE: Final = "vive"
#: A DATED record: it states what was true THEN. **Never flagged, never corrected** —
#: published so the number's history can be seen without rewriting it.
DATEE: Final = "datee"

#: A filename that OPENS with an ISO date — the form this repository uses for anything that
#: dates a moment (``mesures/``, ``moissons/``, ``docs/signalements/``).
_NOM_DATE: Final = re.compile(r"^\d{4}-\d{2}-\d{2}[-.]")

#: A LOG: a file whose name opens with ``journal-``. A log is, by definition, a sequence of dated
#: entries — ``postes/journal-chat-3.md`` copies the number three times, and all three
#: recount a past work session.
_NOM_JOURNAL: Final = re.compile(r"^journal-")

#: The path segment that declares an archive. **A WHOLE SEGMENT, never a substring**: without
#: this boundary, ``archivistes/`` or ``mon-archive-vivante.md`` would silently fall outside
#: judgment — the exact class this repository already paid for on the word ``plan`` (D167).
_SEGMENT_ARCHIVE: Final = "archive"

#: Documents that are ENTIRELY registries of dated entries, and that no path rule can recognize.
#: A NAMED SET, never a count: renaming one must turn it RED (it becomes live again and its lines
#: get flagged), not silently drop it out of judgment.
#:
#: **This set is not a convenience — each entry is a MEASURED correction, not a guess**, which is
#: exactly why it is EMPTY here: this distribution ships no append-only log whose every copy of the
#: number is dated inside its own entry, so there is nothing to spare and nothing to declare.
#: Naming a document just to keep the set non-empty would be the opposite of the rule — it would
#: spare a document nobody measured.
#:
#: The class it exists for is real and stays reachable: being a registry is a property of the
#: DOCUMENT, not of each line, and no path rule can see it. A deployment that has such a document
#: declares it by INJECTING it — :func:`portee` and :func:`verdict` both take ``registres``, and
#: two witnesses exercise that path — rather than by widening a rule that would then spare
#: innocents wholesale. *A check that convicts the innocent is not a floor, it is a wall, and a
#: wall gets routed around.*
REGISTRES_DATES: Final = frozenset()


class SansRecopie(RuntimeError):
    """No copy was found — **an instrument failure, never an agreement**.

    Returning "0 disagreements" over 0 sites is the purest false green there is: *two absences
    of measurement compare equal*. A broken search pattern, a badly rooted repository, and a
    genuinely consistent corpus would all three return the same green.
    """


def portee(document: str, *, registres: Iterable[str] = REGISTRES_DATES) -> str:
    """:data:`VIVE` or :data:`DATEE` — decided by the document's PATH, never by the line's text.

    Four rules, in this order, each with a real counter-example in this repository:

    1. a path segment **exactly** ``archive`` → dated (``archive/INVENTAIRE.md``);
    2. a filename that opens with an ISO date → dated
       (``mesures/2026-08-09-d3-les-27-invariants-relus…md``);
    3. a filename that opens with ``journal-`` → dated (``postes/journal-chat-3.md``);
    4. a document named in ``registres`` → dated (see :data:`REGISTRES_DATES`).

    Everything else is **LIVE**: that is the default, and it is the sensible default — a document
    this function failed to recognize as an archive must be **judged**, never silently spared.
    *An excluded population is an UNJUDGED population, not a population at rest.*
    """
    normalise = document.replace("\\", "/")
    segments = [morceau for morceau in normalise.split("/") if morceau]
    if not segments:
        return VIVE
    if _SEGMENT_ARCHIVE in segments[:-1]:
        return DATEE
    nom = segments[-1]
    if _NOM_DATE.match(nom) or _NOM_JOURNAL.match(nom):
        return DATEE
    if normalise in frozenset(registres):
        return DATEE
    return VIVE


@dataclass(frozen=True, slots=True)
class Recopie:
    """A single site where the number is copied — its address, its value, and its line's verbatim text.

    ``extrait`` exists so the refusal ACCUSES something concrete: a message that says
    ``README.md:30`` without showing the sentence sends its reader off to open the file, and *a
    refusal you obey without reading is a refusal that teaches nothing*.
    """

    document: str
    ligne: int
    valeur: int
    extrait: str = ""

    @property
    def adresse(self) -> str:
        """``document:ligne`` — the form an editor knows how to open."""
        return f"{self.document}:{self.ligne}"


@dataclass(frozen=True, slots=True)
class Desaccord:
    """A LIVE copy that no longer says what the command computes."""

    recopie: Recopie
    reference: int

    def __str__(self) -> str:
        extrait = f" — « {self.recopie.extrait.strip()} »" if self.recopie.extrait else ""
        return (
            f"{self.recopie.adresse} wrote {self.recopie.valeur}, computed {self.reference}{extrait}"
        )


@dataclass(frozen=True, slots=True)
class Accord:
    """The full verdict — the disagreements NAMED, and what was spared, counted separately."""

    reference: int
    #: The LIVE sites in disagreement, in reading order. Empty = agreement.
    desaccords: tuple[Desaccord, ...]
    #: How many LIVE sites were confronted. Published alongside the verdict: *an equality over
    #: zero pairs is true by construction*, and the compared cardinal is the only thing that says
    #: whether the comparison actually TOOK PLACE.
    vifs: int
    #: The DATED sites, spared — counted and returned, never accused nor corrected.
    dates: tuple[Recopie, ...]

    @property
    def accorde(self) -> bool:
        return not self.desaccords


def verdict(
    reference: int,
    recopies: Sequence[Recopie],
    *,
    registres: Iterable[str] = REGISTRES_DATES,
) -> Accord:
    """Confronts EVERY live site against ``reference`` — raises :class:`SansRecopie` if the list is empty.

    **NO TOTAL IS COMPUTED ANYWHERE IN THIS FUNCTION**, and that is the whole point: a sum, an
    average, or a count of copies would let two opposite errors cancel out. The only number
    published alongside the verdict is the **cardinal of compared pairs**, which can compensate for
    nothing because it says nothing about the content.
    """
    if not recopies:
        raise SansRecopie(
            "no copy of the number was found — this is an instrument failure "
            "(pattern, root, or population), never an agreement"
        )
    classees = tuple((site, portee(site.document, registres=registres)) for site in recopies)
    vifs = tuple(site for site, ou in classees if ou == VIVE)
    return Accord(
        reference=reference,
        desaccords=tuple(Desaccord(site, reference) for site in vifs if site.valeur != reference),
        vifs=len(vifs),
        dates=tuple(site for site, ou in classees if ou == DATEE),
    )


def rendre(accord: Accord, *, quoi: str, commande: str) -> str:
    """The verdict IN WORDS — each disagreement on its own line, and the compared cardinal on its own.

    ``quoi`` names the number ("the invariant count") and ``commande`` says how to recompute it: *a
    refusal that does not name the command for its own reference forces the reader to just trust it.*
    """
    tete = (
        f"{quoi}: computed {accord.reference} by `{commande}` — "
        f"{accord.vifs} live occurrence(s) confronted, "
        f"{len(accord.dates)} dated record(s) spared."
    )
    if accord.accorde:
        return tete + "\n\U00002705 All live claims agree."
    lignes = [
        tete,
        f"\U000026D4 {len(accord.desaccords)} live claim(s) no longer say what the command "
        "computes — each at its own address, never a total:",
    ]
    lignes.extend(f"   {desaccord}" for desaccord in accord.desaccords)
    lignes.append(
        "Dated records (archives, measurements, logs, named registries) are NOT accused: they "
        "state what was true then, and correcting them would falsify history (inv. 2)."
    )
    return "\n".join(lignes)
