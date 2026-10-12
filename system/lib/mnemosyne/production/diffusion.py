"""``G8`` — EVERY DIFFUSED RULE NAMES THE POPULATION WHERE IT WAS MEASURED.

*"The corpus's costliest defect,"* and its measured case: a gate cleanly measured on `main`,
through the judge's own accessor, across four load points — then **diffused to four chats**. Three
branches out of four did not have the fix that made the rule true; they were *unable to hold the
rule no matter what they did*. Cost: **five hours for one chat**. The fix took two seconds:
``git merge-base --is-ancestor <fix> <recipient>`` **before** sending.

**OUR MEMORY CARRIES THE MIRROR IMAGE, NEVER THIS FACE OF IT.** It says *"a borrowed verdict
expires,"* *"an inherited measurement carries its own scope"* — all of them instructions to the
**RECEIVER**. The **SENDER** side — *do not diffuse a rule without saying where it was measured* —
existed nowhere.

**MEASURED ON THIS REPO BEFORE WRITING A LINE.** Diffusion, here, means the ``*-emit`` targets:
they produce a contract **to install on another host**. Six of them run with no argument
(``plan-emit``, ``skill-emit``, ``garde-emit``, ``plan-gate-emit``, ``rangement-emit``,
``public-mirror-emit``). **Zero out of six** carries a commit id or an emission date: a contract
installed on a project cannot say which version of Mnemosyne it came from, or whether that version
still exists. *A contract ages at its recipient's, and neither side can date it.*

**WHAT IS A GATE HERE, AND WHAT IS NOT ONE — STATED BEFORE YOU READ ON.**

* :func:`verdict` **PUBLISHES** the state of the emission surfaces. It refuses nothing, and that
  is a choice: 0/6 carry the stamp today, so a gate would be **red from birth** and no one could
  turn it green without rewriting six modules. *A wall gets bypassed; an acknowledgment just gets
  read.*
* :func:`population_nommee` + :func:`perimee` **REFUSE**, and that is the **RECEIVER**'s move: a
  contract with no stamp, or whose stamp names a commit this repo does not have, is refused. That
  half already has a legitimate pass **today** (emit the stamp, then verify it), so it bites for
  real.

**THE POPULATION IS INJECTED**: nothing here reads a file, runs ``git``, or touches
``os.environ``. The edge is :mod:`mnemosyne.runtime.diffusion_run`.

Prose French by this repo's own convention (D117), translated into English in this public mirror.
Decisions: D163 (the address, never the copy) · D157 (write the RULE, not a
number that expires) · inv. 24 (git is the arbiter).
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final

#: The stamp's label. A single line, greppable, stable — a contract installed three weeks ago
#: must stay readable by today's version.
ETIQUETTE: Final = "MNEMOSYNE-POPULATION"

#: The tree's state at emission time. **`modifie` IS NOT A DETAIL**: a contract emitted from a
#: dirty tree names a population **that exists in no commit** — the recipient can never track it
#: down, and the stamp would promise it a traceability it does not have.
PROPRE: Final = "propre"
MODIFIE: Final = "modifie"

_TAMPON = re.compile(
    rf"^#?\s*{ETIQUETTE}:\s*"
    r"racine=(?P<racine>\S+)\s+"
    r"commit=(?P<commit>[0-9a-f]{7,40})\s+"
    r"arbre=(?P<arbre>propre|modifie)\s+"
    r"emis_le=(?P<date>\d{4}-\d{2}-\d{2})\s*$",
    re.MULTILINE,
)


class SansDiffusion(RuntimeError):
    """No diffusion surface was submitted — **instrument failure, never an agreement**.

    A sweep that looked at nothing and a repo where every emission is stamped both return exactly
    the same "nothing to report." *Two absences of measurement compare equal.*
    """


@dataclass(frozen=True, slots=True)
class Population:
    """WHERE a rule was measured — the identity a diffused contract must carry with it.

    ``commit`` is the arbiter (inv. 24): it is the only one of the four values a recipient can
    **verify alone**, without trusting anyone. The other three help them understand; this one lets
    them refuse.
    """

    racine: str
    commit: str
    arbre: str = PROPRE
    emis_le: str = ""

    @property
    def tracable(self) -> bool:
        """True when the named population exists **in history**, and is therefore traceable.

        A tree modified at emission time makes the stamp **honest but not traceable**: it tells
        the truth ("this contract matches no commit"), which is worth infinitely more than a
        stamp that would claim otherwise. That is why :func:`tampon` writes it instead of
        refusing to emit: *a wall declares itself, it is not bypassed* — and refusing to emit from
        a working tree would block the repo's single most common gesture.
        """
        return self.arbre == PROPRE


def tampon(population: Population) -> str:
    """The LINE every diffused contract must carry — **the single source of its shape** (D163).

    A single line, as a ``#`` comment so it survives unchanged in a shell file, a ``.py`` file, or
    a markdown block. Copying it elsewhere would let it drift: this is the function to CALL, never
    its result to retype.
    """
    return (
        f"# {ETIQUETTE}: racine={population.racine} commit={population.commit} "
        f"arbre={population.arbre} emis_le={population.emis_le}"
    )


def population_nommee(texte: str) -> Population | None:
    """The population this diffused text NAMES — ``None`` when it names none.

    ``None`` and "an empty population" are not the same answer, and conflating them is the
    defect this whole module exists to close: *a text that does not say where it was measured*
    and *a text measured on nothing* call for two different responses.
    """
    trouve = _TAMPON.search(texte)
    if trouve is None:
        return None
    return Population(
        racine=trouve.group("racine"),
        commit=trouve.group("commit"),
        arbre=trouve.group("arbre"),
        emis_le=trouve.group("date"),
    )


def perimee(population: Population, *, connus: frozenset[str] | set[str]) -> str | None:
    """The reason to refuse this contract — ``None`` when it is acceptable.

    **THIS IS THE EXACT TRANSPOSITION OF THE TWO-SECOND FIX**: ``git merge-base --is-ancestor``
    asks *"does this recipient have the commit that makes the rule true?"*. Here, the recipient
    passes the set of commits it owns (``connus``, drawn from a ``git rev-list``) and the question
    is the same, in the other direction: *was the contract I received measured on a history I
    have?*

    **AN EMPTY ``connus`` REFUSES, AND THAT IS INTENTIONAL.** A recipient that failed to list
    its own history is not an up-to-date recipient: it **measured nothing**. Returning ``None``
    (acceptable) would pass off the worst case — a broken repo — as the best one.
    """
    if not connus:
        return (
            "no commit known to the recipient — the history could NOT be read, "
            "so NOTHING was verified (this is not « the contract is good »)"
        )
    if not population.tracable:
        return (
            f"the contract was emitted from a {MODIFIE} tree: the population it names "
            "exists in NO commit, so you cannot find it"
        )
    if not any(commit.startswith(population.commit) for commit in connus):
        return (
            f"commit {population.commit} is not in your history: the rule was "
            "measured on a population you do not have, it may be false on your side"
        )
    return None


@dataclass(frozen=True, slots=True)
class Emission:
    """The state of ONE diffusion surface: does what it emits carry a stamp, and which one."""

    cible: str
    population: Population | None

    @property
    def tamponnee(self) -> bool:
        return self.population is not None


@dataclass(frozen=True, slots=True)
class EtatDesEmissions:
    """The surfaces NAMED one by one, never summarized into a total.

    Same lesson as ``accord_chiffre``: *a total that is right on one side and wrong on the
    other passes green*. "4 out of 6" does not say which ones, and which ones is the only
    actionable information.
    """

    tamponnees: tuple[str, ...]
    sans_tampon: tuple[str, ...]

    @property
    def total(self) -> int:
        return len(self.tamponnees) + len(self.sans_tampon)


def verdict(emissions: Mapping[str, str]) -> EtatDesEmissions:
    """The state of the diffusion surfaces — raises :class:`SansDiffusion` if given none at all.

    ``emissions`` maps a surface's NAME to the TEXT it actually produced. The judge launches
    nothing itself: the text is handed to it, which makes this verdict replayable on a received
    text, an archived text, or a text about to be sent.
    """
    if not emissions:
        raise SansDiffusion(
            "no diffusion surface was submitted — a mute instrument, never « everything is "
            "stamped »"
        )
    etats = tuple(Emission(cible, population_nommee(texte)) for cible, texte in emissions.items())
    return EtatDesEmissions(
        tamponnees=tuple(etat.cible for etat in etats if etat.tamponnee),
        sans_tampon=tuple(etat.cible for etat in etats if not etat.tamponnee),
    )


def rendre(etat: EtatDesEmissions) -> str:
    """The state IN WORDS — each surface on its own line, with the rule restated under the count."""
    lignes = [
        f"DIFFUSION — {len(etat.tamponnees)}/{etat.total} surface(s) name the population "
        "their rule was measured on.",
    ]
    for cible in etat.tamponnees:
        lignes.append(f"  \U00002705 {cible}")
    for cible in etat.sans_tampon:
        lignes.append(f"  \U000026D4 {cible} — names NONE")
    if etat.sans_tampon:
        lignes.append(
            "This is NOT a refusal: a contract with no stamp stays installable. It is an "
            "acknowledgement — its recipient will be able neither to date it, nor to verify it "
            "holds the history the rule was measured on."
        )
    return "\n".join(lignes)
