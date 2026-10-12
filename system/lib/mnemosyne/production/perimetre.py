"""G3 -- the NEGATIVE PERIMETER: an exclusion names its recipient, or it is a hole.

**WHAT THIS ITEM FIXES**: the first adopter already writes *« ce que cet arc ne porte pas »* arc by arc, and
the format allows it -- **an arc with no item is a WARNING, never a refusal** (measured: 7 of the 12
real arcs in this repo carried none). What is missing is not the section, it is the
VERIFICATION: *an exclusion with no recipient is a hole; with a recipient, it is a ROUTING.*

**THE FORM IS NOT IMPOSED, IT IS MEASURED** -- third time this rule saves a
design in this arc (lesson `measure-the-population-before-imposing-a-convention`). Measured
BEFORE writing a line, on the 10 real arcs of this plan:

**AND THAT MEASUREMENT WAS WRONG TWICE, corrected on 2026-08-15 after two KILLs**:
it said *« 9 sur 10 »* and *« 2 sur 10 »* -- **11 out of 10** -- and its scope was a FOLDER,
not the repo. The numbers below are the **production path's**
(`python -m mnemosyne.runtime.plans_run`), the only one that does not lie:

* **47 exclusions** COUNTED, **45 routed**, **2 with no recipient**, **0 dead pointers**, across
  **15 printed blocks** for **16 readable plans** (a plan with no exclusion section prints nothing).
  **47 COUNTED for 30 UNIQUE** -- a 3rd isolated audit measured **17 duplicates**, and I do not
  correct them: the first adopter's 13 sub-plans are registered as FULL projects in their own right **and**
  read by their parent's `rglob`, so each one is reported twice. It is the report that repeats
  itself, not the clause that is wrong -- but **the headline figure is inflated by 57 %** and that
  needs to be known.
* Recipients are written in **THREE** forms, all measured: ``l'arc <LETTER>`` (at
  Mnemosyne), ``l'arc <NUMBER>`` (at the first adopter, where an arc is a FILE or a FOLDER), and a
  **cited item** in backticks (*« c'est `A03-12` »*) -- the form `G3`'s condition calls
  *« un autre plan »* (another plan), and which alone accounted for **6 false level-1 accusations**.
* The remaining **2** are not the same case: `04-le-parallelisme` says *« il les relie au plan, et
  rien d'autre »* (recipient genuinely absent); `09-l-emission` says *« ils illustrent, ils ne
  s'executent pas »*. **I long wrote that the second was a legitimate "JAMAIS": that is
  WRONG**, it does not write the word, so the clause classes it as orphaned -- and it is right to
  do so, it is the author who must write their own JAMAIS.

Hence the three verdicts, and the asymmetry the item imposes: **level 1** to name what has
no recipient, **level 2** for the DEAD pointer. *Publishing what is missing is not refusing;
pointing at an arc that does not exist, is.*

**WHERE LEVEL 2 ACTUALLY LIVES, said plainly**: `make plans` **REFUSES NOTHING** -- it
PRINTS the dead pointers, and a report that refuses is no longer read. The only thing that REFUSES a
repo state is the frozen witness `test_le_REEL_du_depot_est_gele` (`assert morts == ()`), which turns
red as soon as an exclusion points at a nonexistent arc. This is a LEVEL 2 barrier on the tracked plan tree
**and nothing else**: plans under `projects/` are gitignored, no test can freeze them --
today's measurement, taken from the production path: the first adopter's gate returns **19 exclusions, 19
routed, 0 with no recipient** -- and nobody will re-verify it tomorrow. I had written here
**"22 exclusions, 6 with no recipient"**: wrong, and wrong IN THE ADMISSION PARAGRAPH ITSELF, drawn
from a script of mine and not from the real command. *A false admission is worse than no admission
at all.* *A check that prints is not a barrier* -- here the barrier is the
witness, not the report.

**WHAT THIS CLAUSE CANNOT DO, said outright**: it verifies that a recipient is
NAMED, and -- **for an ARC only** -- that it exists. It does **not** verify the existence of a
**cited item**: that would require reading the whole corpus of items, which it does not do. And it
never verifies that the recipient is **the right one** -- no lexical detector can know that, and
claiming otherwise would fabricate a guarantee the measurement does not give.

**ITS UNIT IS THE SECTION, NOT THE EXCLUSION.** Measured by an isolated audit: the 30 unique
sections in the repo carry **147 bullet points**, of which **118 have no readable recipient** --
**ONE** router in the section is enough to mark it routed. The clause therefore says *"this section
routes at least once"*, never *"every one of its lines routes"*. **No barrier closes this today.**
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from .plan_format import PlanReading

#: The title of an exclusion section. Measured on the repo: the 10 arcs write « Ce que cet arc
#: ne porte PAS » and the plan's own gate writes « Ce qui n'est PAS dans ce plan ». Both are
#: accepted, without imposing a third form nobody writes.
_TITRE_EXCLUSION = re.compile(
    r"^#{1,6}\s+.*\bne\s+porte\s+pas\b|^#{1,6}\s+.*\bn'est\s+pas\s+dans\s+ce\s+plan\b",
    re.IGNORECASE,
)

#: Any heading at all -- it bounds the section.
_TITRE = re.compile(r"^#{1,6}\s")

#: THE RECIPIENT, AND MY FIRST MEASUREMENT WAS AN UNDECLARED SAMPLE. I had measured
#: "9 arcs out of 10 write `l'arc <LETTRE>`" -- on the 10 arcs of THIS plan. The repo carries
#: **33**, and an isolated audit showed the MAJORITY (16) write `l'arc <NUMERO>` (`l'arc 09`,
#: `l'arc 10`), the first adopter's form where an arc is a numbered FOLDER. Production measurement before
#: the fix: on the first adopter, **19 exclusions, 18 accused, 14 FALSE accusations**.
#: *Measuring the population protects nothing if the measured population is itself a
#: sample whose scope is not declared.* BOTH forms are read.
#: AND MY FIRST WIDENING MADE IT WORSE: `[A-Za-z]{1,4}` reads FRENCH PROSE --
#: « l'arc **ne** porte pas », « l'arc **de** », « l'arc **dont** », « l'arc **rend** ». Measured on
#: the first adopter: **57 false DEAD pointers**, against 0 before. Case settles it: the population writes its
#: letter in UPPERCASE (`l'arc C`, `l'arc E`, `l'arc **A**`), prose in lowercase.
_DESTINATAIRE = re.compile(r"\barcs?\s+([A-Z]{1,4}|\d{1,3})\b")


def _cle(nom: str) -> str:
    """`07` and `7` are the SAME arc. Without this, `l'arc 7` accuses a perfectly alive arc `07`."""
    return nom.lstrip("0") or "0" if nom.isdigit() else nom


#: An assumed « JAMAIS »: the exclusion declares that no arc will ever pick it back up. A VALID
#: and free answer -- without it, the arc that says « ils illustrent, ils ne s'executent pas » would
#: be accused of a hole it does not have.
_JAMAIS = re.compile(r"\bJAMAIS\b")

#: A RECIPIENT IS NOT ALWAYS AN ARC, and `G3`'s condition says so in plain words:
#: *« un autre arc, UN AUTRE PLAN, ou JAMAIS »*. Production measurement: 6 of the 9 exclusions
#: accused of being orphaned actually routed to a named ITEM (`« c'est A03-12 »`, `« H3 ferme la
#: classe »`) or a workstream. They DO route; accusing them was a FALSE level-1 accusation.
#: A cited item is NOT subject to level 2: verifying that an item exists would require reading the
#: whole corpus of items, which this clause does not do -- and claiming otherwise would be a false
#: guarantee.
_ITEM_CITE = re.compile(r"`([A-Za-z]{1,4}\d+(?:-[A-Za-z0-9-]+)?)`")

#: Opening / closing a code block: an example is not an exclusion. Same class of bug as the
#: one closed three times in arc F -- a text detector counts citations as instances.
_FENCE = re.compile(r"^\s*(```|~~~)")

#: An item's identity, in the READER's own grammar (`plan_format._IDENTITY_RE`): 1 to 4 letters
#: then a number. Both halves are possible arc names -- letter at Mnemosyne
#: (`C1` -> arc C), number at the first adopter (`A09-3` -> arc 09).
_PREFIXE = re.compile(r"^([A-Za-z]{1,4})\d+")

#: An arc NAMED BY THE FILE TREE: `09-bordereau-et-rendu.md`, `10-ordonnancement-et-lot/`.
#: This is the first adopter's form, and the only true source of its arc names.
_ARC_NOMME = re.compile(r"^(\d{1,3})[-_]")


def lettre_d_arc(ident: str) -> str | None:
    """The arc letter of an identifier (`C4` -> `C`), or `None` if the shape does not match.

    **PUBLIC, DELIBERATELY**: `lot_emit.py` (E4) needs it to partition items by arc,
    and *a single home, never recopied* — a second, identical regex in a second file would be
    exactly the duplication this repo paid for three times last night on this very pattern."""
    m = _PREFIXE.match(ident)
    return m.group(1) if m else None


@dataclass(frozen=True, slots=True)
class Exclusion:
    """One exclusion as read: where it comes from, what it says, and who it routes to."""

    source: str
    titre: str
    ligne: int
    destinataires: tuple[str, ...]
    jamais: bool
    items: tuple[str, ...] = ()

    @property
    def routee(self) -> bool:
        """ROUTED if it names an arc, **an item**, or if it assumes a JAMAIS -- the three forms
        `G3`'s condition allows, measured in the real corpus."""
        return bool(self.destinataires) or bool(self.items) or self.jamais


def _sans_gras(texte: str) -> str:
    """`l'arc **A**` -> `l'arc A`, and ``l'arc `11` `` -> `l'arc 11`.

    The BACKTICK was found by a 3rd isolated audit: the first adopter's gate writes *« Son DESTINATAIRE
    est l'arc `11` »* -- **inside the very section that cites G3's own doctrine** -- and the clause
    declared it recipient-less. A false level-1 accusation, **3 real occurrences**, saved
    only because the same section also writes an arc in plain form.
    The cited item (`_ITEM_CITE`) is read BEFORE this cleanup: it needs its backticks."""
    return unicodedata.normalize("NFKC", texte).replace("*", "").replace("_", "").replace("`", "")


def lire_exclusions(texte: str, *, source: str) -> tuple[Exclusion, ...]:
    """The exclusions of an arc file (or a plan's own gate).

    A section's body runs until the next heading of EQUAL OR HIGHER level: a
    sub-section belongs to its exclusion. Code blocks are neutralised."""
    lignes, ouvert = [], None
    for ligne in texte.splitlines():
        if m := _FENCE.match(ligne):
            ouvert = m.group(1) if ouvert is None else (None if m.group(1) == ouvert else ouvert)
            lignes.append("")
            continue
        lignes.append("" if ouvert else ligne)

    entetes = [(n, ligne) for n, ligne in enumerate(lignes) if _TITRE.match(ligne)]
    out: list[Exclusion] = []
    for i, (n, ligne) in enumerate(entetes):
        if not _TITRE_EXCLUSION.match(ligne):
            continue
        niveau = len(ligne) - len(ligne.lstrip("#"))
        fin = next(
            (
                n2
                for n2, titre in entetes[i + 1 :]
                if (len(titre) - len(titre.lstrip("#"))) <= niveau
            ),
            len(lignes),
        )
        corps = _sans_gras("\n".join(lignes[n + 1 : fin]))
        out.append(
            Exclusion(
                source=source,
                titre=ligne.lstrip("# ").strip(),
                ligne=n + 1,
                destinataires=tuple(sorted(set(_DESTINATAIRE.findall(corps)))),
                jamais=bool(_JAMAIS.search(corps)),
                items=tuple(sorted(set(_ITEM_CITE.findall("\n".join(lignes[n + 1 : fin]))))),
            )
        )
    return tuple(out)


def arcs_existants(reading: PlanReading) -> frozenset[str]:
    """The arc letters the plan REALLY carries, drawn from its items' own identifiers.

    Derived from the READER, never from a hand-written list: a copied list ages, and
    a new arc would then be declared NONEXISTENT by a clause that refuses. *The right source is
    the judge's own accessor* -- a lesson paid for last night on a tuple whose shape I had guessed."""
    # `ident[0]` WAS WRONG: `_IDENTITY_RE` allows a 1-to-4-LETTER prefix, so it returned
    # `{'A'}` where the arc is actually called `AB` -- breaking both ways on 13 of the 16 plans.
    # AND MY 1st FIX PULLED THE NUMBER OUT OF THE IDENT: a COINCIDENCE, not an arc. The first adopter's
    # gate carries items `P0..P13`; their numbers happened to resemble its arcs `00..13` with
    # NO link at all. Measured by an isolated audit: the entire level-2 check hinged on the
    # existence of an item named `P10`. *A zero obtained by numbering coincidence is not a zero.*
    # The NUMBER is no longer read here: it is read from the FILE TREE (`arcs_de_l_arborescence`).
    return frozenset(
        lettre for item in reading.items if (lettre := lettre_d_arc(item.ident)) is not None
    )


def arcs_de_l_arborescence(chemins: Iterable[Path]) -> frozenset[str]:
    """The NUMBERED arcs of a plan: **its files and folders**, not its items' identifiers.

    This is the only true source of the first adopter's form, where an arc IS a file
    (`plan/09-bordereau-et-rendu.md`) or a folder (`plan/10-ordonnancement-et-lot/`). Measured by an
    isolated audit before this fix: `make plans` printed **73 refusals « pointe l'arc N, qui
    n'existe pas »**, and **73 of 73 were WRONG** -- all 14 folders exist on disk.
    The cause was not the reading: it was that the universe of arcs was drawn from a DIFFERENT
    source than the exclusion population. *The universe and the population are drawn from the same
    place.*"""
    return frozenset(m.group(1) for c in chemins if (m := _ARC_NOMME.match(c.name)) is not None)


def juger(
    exclusions: tuple[Exclusion, ...], arcs: frozenset[str]
) -> tuple[tuple[Exclusion, ...], tuple[tuple[Exclusion, str], ...]]:
    """``(the exclusions WITH NO recipient, the DEAD POINTERS)``.

    The asymmetry is the one the item imposes: the first member gets **published** (level 1), the
    second gets **refused** (level 2). *Publishing what is missing is not refusing; pointing at an
    arc that does not exist, is.*"""
    orphelines = tuple(x for x in exclusions if not x.routee)
    connus = {_cle(a) for a in arcs}
    morts = tuple(
        (x, lettre) for x in exclusions for lettre in x.destinataires if _cle(lettre) not in connus
    )
    return orphelines, morts


def rendre(
    exclusions: tuple[Exclusion, ...],
    orphelines: tuple[Exclusion, ...],
    morts: tuple[tuple[Exclusion, str], ...],
) -> tuple[str, ...]:
    """The lines `make plans` prints. **Publishes, never refuses here** -- refusing a dead
    pointer is a separate gate, because a report that refuses is no longer read."""
    if not exclusions:
        return ()
    lignes = [
        f"      NEGATIVE PERIMETER: {len(exclusions)} exclusion(s) · "
        f"{len(exclusions) - len(orphelines)} routed · {len(orphelines)} with no recipient"
    ]
    for x in orphelines:
        lignes.append(
            f"        · {x.source} — « {x.titre[:52]} » names neither an arc nor an assumed JAMAIS"
        )
    for x, lettre in morts:
        lignes.append(f"        \U000026D4 {x.source} — points at arc {lettre}, which does not exist")
    return tuple(lignes)
