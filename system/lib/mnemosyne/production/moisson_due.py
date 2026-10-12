"""``I2`` — the harvest TRIGGER: which closed arcs never returned anything to the system.

``make moisson`` exists, it is well designed, and **it has never been run a single time**. This
is the textbook case behind the remark from the operator that opened the whole `A2` arc: *the
pattern exists, nothing forces it.* This module is the missing half — not one more harvest, but
the **act of noticing** that an arc closed without returning anything.

**LEVEL 1, AND THAT IS A CHOICE WRITTEN INTO THE ITEM**: *"a forced harvest manufactures
candidates"*. This module **publishes**, it refuses nothing, it writes nothing, it launches no
agent. Raising it to level 2 (a gate that refuses a repo state) would make it harmful: it would
produce harvests run just to turn off an alarm, and a harvest that keeps everything has judged
nothing.

**WHY THIS MODULE NAMES WHERE ITS SEVEN SIBLINGS COUNT.** The proposer's sources
(`proposer.py`) publish a **count, never a name** — invariant 22 / D66, because a fiche's or a
signalement's title can carry a bubble's material. The `*Done when*` clause of `I2` instead
requires the tick to **NAME** the arcs. This is not a workaround, and the distinction is
mechanical: what gets named here is a **plan arc's identifier** (`example-project/plan/03-captation`), i.e.
the **path of a plan file** — the same metadata `make plans` already prints for the whole tree.
**No item title, no content, no line of the plan crosses over.** And the list is **bounded**
(:data:`NOMS_MAX`): a project with fifty closed arcs does not dump its plan's structure into a
Mnémosyne proposal, it shows three and says how many remain.

**THE POPULATION IS INJECTED, NEVER FETCHED.** The judging functions read no file: they
receive the arcs seen and the set of arcs already harvested. *A judge that goes looking for its
own population can find it empty and return a green.* The only disk access in this module is
:func:`arcs_moissonnes`, isolated at the bottom of the file, and it is the **edge** that calls it.

English prose in this public mirror (D117). Decisions: D24 / D37 (the harvest) · D92 (propose,
never impose) · inv. 22.
"""

from __future__ import annotations

import re
from collections.abc import Collection, Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

#: How many arcs the proposal NAMES at most — the rest is counted, never listed (inv. 22).
#: Three, because a proposal is a signal read in passing: beyond that, nobody reads it anymore.
NOMS_MAX = 3

#: The field that carries the IDENTITY of a filed harvest. Identity comes from this DECLARED
#: field, never from the file name: *identity by SHAPE can be impersonated by any copy*, and two
#: arcs from two projects can produce the same file slug.
_ARC_DECLARE = re.compile(r"^arc:[ \t]*[\"']?([^\"'\n]+?)[\"']?[ \t]*$", re.MULTILINE)

#: `I2-bis` — the two fields that carry a harvest's PROGRESS, not its existence.
#: **WHY DECLARED FIELDS RATHER THAN COUNTING THE PROSE.** Counting "retenus" by reading the
#: document's body would amount to judging a LAYOUT: a table, a bulleted list and a paragraph say
#: the same thing and count differently. *A TEXT detector counts citations.* The number is
#: therefore **declared by whoever harvested**, like `arc:`.
#: **A TRAILING END-OF-LINE COMMENT IS TOLERATED, AND THAT IS A PAID-FOR FIX.** The first draft
#: required the line to end right after the digit. An entry written `eprouves: 0   # no trial
#: run` was therefore read as **NOT DECLARED** — the tick still named it, but *for the wrong
#: reason*, and the message would have sent its reader to declare a field they had already
#: written. *A witness that passes for the wrong reason proves nothing.*
_RETENUS = re.compile(r"^retenus:[ \t]*(\d+)[ \t]*(?:#.*)?$", re.MULTILINE)
_EPROUVES = re.compile(r"^eprouves:[ \t]*(\d+)[ \t]*(?:#.*)?$", re.MULTILINE)


@dataclass(frozen=True, slots=True)
class ArcVu:
    """A plan arc as it was SEEN — its identifier, how many items, how many done.

    Deliberately poor: no titles, no prose, no detailed statuses. What does not enter here
    cannot leak further, and that is the only compartmentalization guarantee that depends on
    nobody.
    """

    identifiant: str
    total: int
    faits: int


def est_ferme(arc: ArcVu) -> bool:
    """Is the arc closed — all its items done, **and at least one item**.

    **``total > 0`` IS NOT A DECORATIVE PRECAUTION.** Without it, an EMPTY arc would be "all
    its items done" by vacuity, and the trigger would demand a harvest on an arc that never
    produced anything. This is the most banal defect class in this repo — *an excluded
    population is not judged, and an empty population returns a green* — turned around here: an
    empty population would return a manufactured RED."""
    return arc.total > 0 and arc.faits == arc.total


def arcs_a_moissonner(
    arcs: Iterable[ArcVu], moissonnes: Collection[str] = ()
) -> tuple[str, ...]:
    """The identifiers of CLOSED arcs for which no harvest has been filed, sorted.

    ``moissonnes`` is the set of arcs that have already returned something
    (:func:`arcs_moissonnes` reads it at the edge). It is **injected**: this judge fetches
    nothing on its own.

    **Why a register exists instead of deducing the harvest from its retained candidates**: an
    honest harvest may retain NONE — the contract says so itself, *"a low rejection rate is an
    alarm signal"*. Deducing "no candidate ⇒ no harvest" would forever count as not-run a
    harvest that correctly rejected everything, and would manufacture the alarm nobody can ever
    turn off. *Two absences of measurement compare equal.*"""
    already = frozenset(moissonnes)
    return tuple(
        sorted(a.identifiant for a in arcs if est_ferme(a) and a.identifiant not in already)
    )


def resume(manquants: Sequence[str], *, noms_max: int = NOMS_MAX) -> str | None:
    """The sentence the tick publishes — ``None`` when there is nothing to say.

    The silence is correct: no closed arc without a harvest is the normal state of a plan in
    progress, and a source that speaks into a void manufactures noise nobody reads anymore.

    **It names at most ``noms_max`` arcs and COUNTS the rest** — the bound is what makes the
    naming compatible with invariant 22: three plan paths are a pointer, fifty are a project's
    structure."""
    if not manquants:
        return None
    montres = list(manquants[:noms_max])
    reste = len(manquants) - len(montres)
    liste = " · ".join(montres) + (f" (and {reste} other{'s' if reste > 1 else ''})" if reste else "")
    arc = "closed arc has" if len(manquants) == 1 else "closed arcs have"
    return (
        f"{len(manquants)} {arc} returned no harvest to the system: {liste} — "
        "`make moisson PROJET=...` issues the contract (it RECRUITS domain experts and rules "
        "generic / parameterizable / duplicate / specific). *A project that closes without "
        "returning anything leaves Mnémosyne exactly where it found it.*"
    )


@dataclass(frozen=True, slots=True)
class SuiviMoisson:
    """The PROGRESS declared by a harvest — how many candidates retained, how many trialed.

    ``None`` means **not declared**, never zero: the two do not read the same way, and that is
    this type's entire reason to exist. Deliberately poor, like :class:`ArcVu`: two integers and
    a file name, no candidate title, no content (inv. 22)."""

    source: str
    retenus: int | None
    eprouves: int | None


def moissons_en_attente(suivis: Iterable[SuiviMoisson]) -> tuple[str, ...]:
    """`I2-bis` — the harvests whose RETAINED candidates were never trialed, sorted.

    **THE FAILURE THIS JUDGE CLOSES, AND IT COST A TOOL.** The trigger :func:`resume`
    listens for the **EXISTENCE** of an entry: it falls silent as soon as an arc has one,
    *"not a queue to drain"*, and that is a good choice for what it measures. But it makes
    **two silences** indistinguishable: *nothing to report* and *something written that nobody
    will ever re-read*. Measured on 2026-09-08: the candidate retained on 2026-08-17 — logged
    with its measurement, described as an absence on both sides — was never re-read, and **another
    project rebuilt it alone 16 days later** (`epreuve_deux_processus.py`) while Mnémosyne still did not
    have it. *The very mechanism meant to make the item visible was making it invisible forever.*

    **A HARVEST THAT DECLARES NOTHING IS NAMED, NEVER SILENT** — the same reason as
    everywhere else here: *"no candidate pending" and "I could not look" do not read the same
    way.* This is the only case where this judge speaks on an absence of data, and it does so on
    purpose.

    **``retenus == 0`` IS A LEGITIMATE SILENCE**, and this is not a tolerance: the harvest's
    contract says *an honest harvest may retain nothing* — treating that as a gap would
    manufacture the alarm nobody can ever turn off, exactly what :func:`arcs_a_moissonner` was
    written to avoid.

    **WHAT THIS JUDGE DOES NOT JUDGE, and I write it down rather than let it be believed
    judged**: ``eprouves > retenus`` (an inconsistent declaration) reads here as a silence.
    Closing it would require deciding whether the excess is a typo or a trial run against a
    candidate from another harvest — *a gate placed on an assumed site is the very fault it
    claims to close*. No barrier catches it today.

    The population is **INJECTED** (:func:`suivi_des_moissons` reads it at the edge). This judge
    opens no file — *a judge that goes looking for its own population can find it empty and
    return a green.*"""
    attente: list[str] = []
    for s in suivis:
        if s.retenus is None:
            attente.append(s.source)
        elif s.retenus > 0 and (s.eprouves is None or s.eprouves < s.retenus):
            attente.append(s.source)
    return tuple(sorted(attente))


def resume_attente(sources: Sequence[str], *, noms_max: int = NOMS_MAX) -> str | None:
    """The tick's sentence for `I2-bis` — ``None`` when no retained candidate is dormant.

    Bounded like its sisters (inv. 22): what crosses is a **harvest file name**, never a
    candidate's title. The message NAMES the gesture that turns it off — *the refusal message
    names the way out* — and reminds that declaring a candidate discarded is a valid, free
    answer."""
    if not sources:
        return None
    montres = list(sources[:noms_max])
    reste = len(sources) - len(montres)
    liste = " · ".join(montres) + (f" (and {reste} other{'s' if reste > 1 else ''})" if reste else "")
    verbe = "harvest carries" if len(sources) == 1 else "harvests carry"
    return (
        f"{len(sources)} {verbe} RETAINED candidates that nothing has trialed: {liste} — a "
        "candidate retained and never revisited gets rebuilt elsewhere (measured: 16 days). "
        "Trial it (`make skill-eprouver`) then declare `eprouves: <n>` in the entry — or "
        "`retenus: 0` if the harvest ultimately kept nothing, which is a valid, free answer. "
        "*A register that falls silent as soon as it has an entry no longer recalls what it "
        "contains.*"
    )


# ------------------------------------------------------------------------------------------------
# THE EDGE OF THIS MODULE — the only disk access, called by the runtime, never by the judges above
# ------------------------------------------------------------------------------------------------


def _lister_moissons(dossier: Path) -> list[Path] | None:
    """The harvest files in the register, or ``None`` if the folder is there but UNREADABLE.

    **``Path.glob`` DOES NOT RAISE ON A FOLDER WITHOUT PERMISSION — measured on 2026-09-08,
    and this is what made the three readers' guard decorative.** On a `chmod 000`: ``glob``
    returns **0 entries without raising**, while ``iterdir`` and ``os.listdir`` both raise
    ``PermissionError``. An ``except OSError`` around a ``glob`` is therefore a **dead branch**
    for the most likely failure mode, and the tick fell silent exactly where its docstring
    claimed in bold that it never does. *A guard that names the right exception at the wrong
    spot is a guard that does not exist.*

    ``None`` = *I could not look*; ``[]`` = *I looked, there is nothing* — an ABSENT folder
    returns ``[]``, because a register that does not exist yet is a normal state, not a failure.
    **The README is excluded here, once for all three readers**: without that, the example it
    gives (`arc: "example-project/plan/03-captation"`) counted as a harvest genuinely filed and TURNED OFF
    the alarm for a real arc bearing that name — measured."""
    try:
        entrees = list(dossier.iterdir())
    except FileNotFoundError:
        return []  # no register yet: a normal state, not a failure
    except OSError:
        return None  # it is there and unreadable: this is NOT "nothing to report"
    return sorted(
        c for c in entrees if c.suffix == ".md" and c.name != "README.md" and c.is_file()
    )


def candidats_sans_panne(fiches: Iterable[tuple[str, str]]) -> tuple[str, ...]:
    """`I3(b)` — the harvests that propose a rule WITHOUT declaring the failure it avoids.

    **THIS IS THE CALLER THAT `regle_candidate.py` DID NOT HAVE.** Its author (chat 3) wrote
    this AT THE TOP of their own audit mandate rather than wait to be caught: *"as it stands,
    `regle_candidate.py` refuses nothing to nobody. It refuses IF CALLED, and nothing calls it.
    A clause with no caller has exactly the appearance of a satisfied clause."* Sixth occurrence
    of this class in one day in this repo.

    **THE POPULATION IS INJECTED** — ``(source, text)`` pairs, never a folder. The edge
    :func:`moissons_sans_panne` opens the disk; this judge reads nothing. *A judge that goes
    looking for its own population can find it empty and return a green.*

    **LEVEL 1 HERE, AND IT IS THE SAME DECISION AS FOR THIS WHOLE MODULE**: we NAME, we do
    not refuse. `regle_candidate` carries two halves —
    :func:`~mnemosyne.production.regle_candidate.lire` (which observes) and
    ``exiger_panne_declaree`` (which RAISES). **Only the first is called here**, because raising
    this module to level 2 would manufacture exactly what `I2` forbids: harvests written to turn
    off an alarm.

    **AND I ADMIT THE HALF THAT STILL HAS NO CALL SITE, rather than invent one for it.**
    ``exiger_panne_declaree`` — the level-2 that `I3` requires — **still has no caller**, and
    three measurements say why rather than an intuition:

    * the harvest register contains **no real harvest** (a README) — measured by chat 3;
    * the trial chain (``make skill-eprouver``) takes a **skill name**, not a fiche: nothing in
      it links a candidate to the harvest that proposed it;
    * building that link would require inventing a field inside **chat 3's own format**, their
      home ground.

    *A measured admission is a valid, free answer; a gate placed on an assumed site is the very
    fault it is in the process of closing.*
    """
    from .regle_candidate import lire  # local: the I3(a) judge lives in chat 3's home ground

    without_failure: list[str] = []
    for source, texte in fiches:
        if not lire(texte, source=source).declaree:
            without_failure.append(source)
    return tuple(sorted(without_failure))


def resume_candidats(sources: Sequence[str], *, noms_max: int = NOMS_MAX) -> str | None:
    """The tick's sentence for `I3(b)` — ``None`` when every harvest declares its failure.

    Bounded like its sister :func:`resume` (inv. 22): what crosses is a **harvest file name**,
    never its content."""
    if not sources:
        return None
    montres = list(sources[:noms_max])
    reste = len(sources) - len(montres)
    liste = " · ".join(montres) + (f" (and {reste} other{'s' if reste > 1 else ''})" if reste else "")
    verbe = "harvest declares" if len(sources) == 1 else "harvests declare"
    # TODO(public-mirror): the `**Panne :**` marker below is left UNTRANSLATED on purpose — it is
    # the literal field `regle_candidate.lire()` parses (that module is outside this batch), and
    # translating only the instruction text while the parser still matches the French marker
    # would silently break the pairing between what a harvest author is told to write and what
    # actually gets read. Revisit once `regle_candidate.py` itself is sanitized for this mirror.
    return (
        f"{len(sources)} {verbe} NO failure: {liste} — a rule invented by a project names the "
        "MEASURED failure it avoids, or another project's 11,004 lines get reproduced in every project. "
        "Write `**Panne :** <what breaks, with its number>` — or `**Panne :** aucune`, which is "
        "a valid, free answer."
    )


def moissons_sans_panne(dossier: Path) -> tuple[str, ...]:
    """The EDGE of :func:`candidats_sans_panne` — it reads, it does not judge.

    Same robustness contract as :func:`arcs_moissonnes`, and for the same reason: *a per-item
    guarantee that raises kills the batch*, and this batch is the whole `tick`."""
    fichiers = _lister_moissons(dossier) or []
    paires: list[tuple[str, str]] = []
    for chemin in fichiers:
        try:
            paires.append((chemin.name, chemin.read_text(encoding="utf-8")))
        except (OSError, UnicodeDecodeError):
            continue
    return candidats_sans_panne(paires)


def _entier(m: "re.Match[str] | None") -> int | None:
    """The integer from a capture, or ``None`` — **it never RAISES**.

    **DEFECT FOUND BY AN ISOLATED AUDIT, 2026-09-08.** ``int()`` was not guarded: CPython
    refuses to convert a literal longer than 4,300 digits (``ValueError: Exceeds the limit``). A
    single file carrying ``retenus: 999…`` therefore made **the whole edge raise**, and *the
    HEALTHY neighbour was lost along with it* — measured, while the sister
    :func:`arcs_moissonnes` returned its arc without flinching on the same folder. The docstring
    nonetheless claimed the "same robustness contract": *two demonstrably different contracts
    under a sentence that calls them equal.*"""
    if m is None:
        return None
    try:
        return int(m.group(1))
    except ValueError:
        return None  # a number that cannot be read is not a declared number


def suivi_des_moissons(dossier: Path) -> tuple[SuiviMoisson, ...] | None:
    """The EDGE of :func:`moissons_en_attente` — it reads, it does not judge.

    **``None`` AND ``()`` DO NOT READ THE SAME WAY, AND IT TOOK AN ISOLATED AUDIT TO IMPOSE
    THAT.** ``()`` = *I looked, nothing is dormant*; ``None`` = *I could not look*. The first
    version returned ``()`` in both cases: a ``chmod 000`` on the register therefore **silenced
    the tick**, while its edge's own docstring claimed in bold that it never falls silent.
    Measured before/after: *"1 harvest carries RETAINED candidates"* → **SILENCE**. *A guard
    placed after its own read site guards nothing*: the tick's ``except Exception`` was dead for
    the most likely failure mode, because the edge swallowed the ``OSError`` before it got there.

    An unreadable file stays SKIPPED (*a per-item guarantee that raises kills the batch*); it is
    the unreadable FOLDER that propagates up, because then the entire measurement never took
    place."""
    fichiers = _lister_moissons(dossier)
    if fichiers is None:
        return None  # the register is there but unreadable: this is NOT "nothing to report"
    suivis: list[SuiviMoisson] = []
    for chemin in fichiers:
        try:
            texte = chemin.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        suivis.append(
            SuiviMoisson(
                source=chemin.name,
                retenus=_entier(_RETENUS.search(texte)),
                eprouves=_entier(_EPROUVES.search(texte)),
            )
        )
    return tuple(suivis)


def arcs_moissonnes(dossier: Path) -> frozenset[str]:
    """The arcs declared in the harvest register — identity comes from the ``arc:``
    field.

    Level 1 all the way through: *this module publishes, it never refuses*. A missed harvest is
    caught on the next pass; an exception here would kill the whole `tick` — *a per-item
    guarantee that raises kills the batch*.

    **TWO FIXES PAID FOR BY SABOTAGE, and the first is a real defect.**

    1. ``UnicodeDecodeError`` **is not an ``OSError``**. The first draft only caught ``OSError``
       — a single mojibake file dropped here would have killed the tick, i.e. exactly what the
       docstring promised had been closed. *A guard that names the wrong error class is a guard
       that does not exist.*
    2. It also carried an ``if not dossier.is_dir(): return frozenset()`` — a **DEAD branch**:
       ``Path.glob`` on an absent folder does not raise, it returns nothing (measured). The
       "absent folder" witness therefore passed **for the wrong reason**, and the sabotage that
       removed the guard survived. It has been removed; what actually protects is named here —
       ``glob`` itself.

    **AND I ADMIT THE BELT THAT REMAINS UNTESTED, rather than declare it a barrier.** The
    ``except OSError`` around the ``glob`` covers the case where ``dossier`` names a FILE. **No
    witness arms it on this platform**: measured here (CPython 3.12, macOS), ``glob`` on a file
    path also does not raise — it returns nothing, and the sabotage that removes this ``try``
    **survives**. I am keeping it anyway: it is three lines against a behaviour that is not
    guaranteed everywhere, and the price of an exception here would be the whole `tick`. But
    this is an **admitted belt, not a measured barrier** — *a lesson with no barrier is a wish,
    and saying so is the free answer that keeps one from manufacturing a false one.*"""
    # WHY THIS ONE RETURNS AN EMPTY SET ON AN UNREADABLE REGISTER, WHERE ITS SISTER
    # `suivi_des_moissons` PROPAGATES `None` — and this is not an inconsistency, it is the
    # DIRECTION of the bias that differs. Here, "no arc known as harvested" makes ALL closed arcs
    # get named: the refusal is LOUD, never silent. Over there, "no harvest read" returned
    # SILENCE, so an unreadable register read as "nothing is dormant". *A fail-safe is judged by
    # the direction of its failure, never by the uniformity of its shape.*
    fichiers = _lister_moissons(dossier) or []
    vus: set[str] = set()
    for chemin in fichiers:
        try:
            texte = chemin.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        vus.update(m.group(1).strip() for m in _ARC_DECLARE.finditer(texte) if m.group(1).strip())
    return frozenset(vus)
