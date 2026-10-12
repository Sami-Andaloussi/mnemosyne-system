"""Permanent workstream -- "make orphelins": does a file under `system/lib/` have a DECLARED
owner, and WHICH one does the measurement show as the real producer?

**BORN FROM A ONE-OFF CENSUS THAT WAS FAIR BUT INCOMPLETE (chat 3, 2026-08-16)**: 166 files
swept, 125 "UNDECLARED" -- except the population model only carried THREE parties
(chat-1, chat-2, chat-3). **The orchestrator does not have a `mon_lot:` in the same sense** the
census had in mind, even though it DOES have one, written and structured, in its own role
document (not part of this mirror) -- and a file it declares (``production/delegations.py``)
came out "orphan" forever, no matter what got written, because the question asked could not see
its own answer. *A census whose model omits one actor reports that actor's work as ownerless --
indefinitely, and without ever turning red.*

**LEVEL 1 (publishes), never level 2 (refuses).** A check that refused on 125 files on day one
would be disarmed on day one -- measure first; whether to arm it is decided from the published
number, never in advance.

**"ZERO GAP" MUST BE A REACHABLE RESULT, AND THIS IS VERIFIED, NOT ASSUMED** -- if the four
`mon_lot:` declarations ended up naming every file exactly once, `orphelins` would return `()`
and so would `collisions`: nothing here manufactures a floor that can never reach zero.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

#: The FOUR parties that can declare a file -- the three chats AND the orchestrator, each with
#: its own `mon_lot:`, structured the same way, in its own role document.
PARTIES: tuple[str, ...] = ("chat-1", "chat-2", "chat-3", "orchestrateur")


@dataclass(frozen=True, slots=True)
class Fichier:
    """One real file under `system/lib/`, and what the TWO sources say about it."""

    chemin: str
    #: Subset of :data:`PARTIES`, sorted -- empty if nobody declares it.
    declare_par: tuple[str, ...]
    #: Distinct CO-AUTHORED-BY models seen in its git history, sorted -- empty if it was
    #: never committed (measured, not assumed: see :attr:`jamais_committe`).
    modeles_mesures: tuple[str, ...]

    @property
    def orphelin(self) -> bool:
        """None of the four parties declares it -- the gap this module exists to name."""
        return not self.declare_par

    @property
    def jamais_committe(self) -> bool:
        """Distinct from `orphelin`: a file can be declared without ever having been committed
        (just created), or committed without being declared (the classic orphan)."""
        return not self.modeles_mesures


@dataclass(frozen=True, slots=True)
class Recensement:
    """The complete verdict -- everything is NAMED, nothing is counted without the list that
    makes it up staying readable (same doctrine as :mod:`obligation`)."""

    fichiers: tuple[Fichier, ...]

    @property
    def declares(self) -> tuple[Fichier, ...]:
        return tuple(f for f in self.fichiers if not f.orphelin)

    @property
    def orphelins(self) -> tuple[Fichier, ...]:
        return tuple(f for f in self.fichiers if f.orphelin)

    @property
    def collisions(self) -> tuple[Fichier, ...]:
        """A file declared by TWO OR MORE parties at once -- the class that "one file, one
        owner" forbids. This isn't supposed to happen; naming it rather than silently picking a
        winner is the same choice :func:`obligation.verdict` makes for its own duplicates."""
        return tuple(f for f in self.fichiers if len(f.declare_par) > 1)


def recenser(
    fichiers_reels: Iterable[str],
    declarations: Mapping[str, frozenset[str]],
    modeles: Mapping[str, tuple[str, ...]],
) -> Recensement:
    """PURE judge -- real files, declarations, and measured models are all INJECTED, never
    discovered here. *A judge that goes and fetches its own population can find it empty and
    return a green* -- the edge (``runtime/orphelins_run.py``) reads the disk and parses the
    role documents; this module only compares what it is handed.

    ``declarations``: party (one of :data:`PARTIES`'s values) -> the set of paths it declares,
    ALREADY resolved (a glob from the source role document, not part of this mirror, becomes,
    here, all the real paths it covers -- resolving the glob is the edge's problem, never this
    judge's)."""
    fiches = []
    for chemin in sorted(set(fichiers_reels)):
        declare_par = tuple(
            sorted(partie for partie, chemins in declarations.items() if chemin in chemins)
        )
        fiches.append(
            Fichier(
                chemin=chemin,
                declare_par=declare_par,
                modeles_mesures=tuple(modeles.get(chemin, ())),
            )
        )
    return Recensement(fichiers=tuple(fiches))


def rendre(r: Recensement, *, profondeur: int = 10) -> str:
    """The text `make orphelins` prints -- LEVEL 1, it publishes, it never refuses.

    Every bounded list says how much it hides -- same discipline as `carte.py` (B3): *a
    summary says HOW MUCH it hides, an excerpt does not.*"""
    lignes = [
        "ORPHANS -- DECLARED owner (the FOUR mon_lot:) against MEASURED producer (git)",
        f"{len(r.fichiers)} real file(s) · {len(r.declares)} declared · "
        f"{len(r.orphelins)} orphan(s) · {len(r.collisions)} collision(s)",
    ]
    if r.collisions:
        lignes.append("")
        lignes.append(f"\U000026D4\U000026D4 {len(r.collisions)} file(s) declared by SEVERAL parties at once:")
        for f in r.collisions[:profondeur]:
            lignes.append(f"  {f.chemin} -- {', '.join(f.declare_par)}")
        if len(r.collisions) > profondeur:
            lignes.append(f"  … and {len(r.collisions) - profondeur} more")
    if r.orphelins:
        lignes.append("")
        lignes.append(f"\U000025B6 {len(r.orphelins)} orphan(s), NONE of the four parties declares them:")
        for f in r.orphelins[:profondeur]:
            modeles = ", ".join(f.modeles_mesures) if f.modeles_mesures else "never committed"
            lignes.append(f"  {f.chemin} -- measured: {modeles}")
        if len(r.orphelins) > profondeur:
            lignes.append(f"  … and {len(r.orphelins) - profondeur} more")
    else:
        lignes.append("")
        lignes.append("No orphan: the four mon_lot: cover the entire population.")
    return "\n".join(lignes) + "\n"
