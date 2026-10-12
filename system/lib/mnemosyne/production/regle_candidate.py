"""I3(a) - a rule invented by a project NAMES the MEASURED failure it prevents.

**WHAT THE ITEM FIXES**: the three levels of room left to a project (IMPOSED / OFFERED /
INVENTED) only make sense if the third one has an exit door. Without a clause, an invented rule
stands on its good looks alone - and the safeguard comes from the operator's own memory:
*"I recited the rule without being able to name the failure it prevented."* Otherwise the research
project's **11,004 lines** reproduce themselves in every project.

**THE FORM IS NOT INVENTED, IT IS REUSED.** The repo already expresses this idea one notch
lower: a memory LESSON declares its barrier under the literal form ``**Barriere :**``, judged by
`runtime/memoire.py` (`_DECLARATION_DE_BARRIERE`), with a published debt. Inventing a second
form for the same idea would be the duplication the doctrine forbids. A candidate RULE therefore
declares its failure under the sister form ``**Panne :**``.

**AND THE ADMISSION IS A VALID, FREE ANSWER**, exactly as for barriers (A2):
``**Panne :** AUCUNE MESUREE`` **passes**. That is what stops the clause from MANUFACTURING failures -
*a quota per record manufactures content*. A rule that admits it measured no failure is
honest; a rule that invents one is worse than one that says nothing.

**THE POPULATION, MEASURED BEFORE WRITING A LINE** (`knowledge/proposals/`, 2026-08-15):

* **13 records** in total, of which **7 harvested books** - out of scope for the clause, they are
  not rules;
* **6 candidate rules**, and **0 declares a measured failure**;
* **all 6 are `status: draft`** - none is currently up for promotion.

**AND "6 CANDIDATE RULES" WAS A FALSE LABEL**: three of the six are not rules (two deferred
actions, one investigation, one leftover from OSS pillaging). The real population of candidate
rules is **3**. The COUNT of 6 files was correct; its NAME was not - *a heading that lies
fabricates the wrong cut*.

Hence the exact point where the clause bites: **PROMOTION, never the filing of a draft.** A gate
that refused every draft would refuse **6 records out of 6** - *a catch rate with no false
refusal is a wall*.

**WHAT WAS TRUE UNTIL 2026-08-15 21:0x, KEPT FOR THE RECORD**: nothing called this
clause - no `make` target, no hook, no production call site - so, per the rule that
*"a level is that of its CALLER, never of its own code,"* the module was at level
ZERO, weaker than a level 1 that at least prints.
**FIXED**: `runtime/regle_promouvoir_run.py` (hookup (b) of `I3`) now calls
`exiger_panne_declaree` for real, and `make regle-promouvoir` (chat 2, `96a05f1`) gives it a
real call site. **BUT NOT LEVEL 2** - a second, isolated audit measured it and
the orchestrator fixed it itself: the gate REFUSES when called (that proves it
works), but **nothing REQUIRES calling it** - `make skill-new` / `make skill-eprouver` remain
accessible without ever going through it. This is a **level 1 (REAL gate, OPTIONAL caller)**,
today's exact wording of the project's obligation-level taxonomy and of `I3`'s `*Obligation*` field.
*A gate that refuses when called proves it works; it does not prove anyone is
required to go through it - that is the same fault as promotion's fictional level 3, one notch
lower, and it took a third audit to catch it.*
**Corollary, still true**: *"at promotion time it refuses 0 today"* was NOT a
merit of the design before the hookup - it refused 0 because nobody called it. **A
clause with no caller looks exactly like a satisfied clause.** With the hookup, the
refusal count is still 0 in practice (no real record is promotable yet without an admission) but for
an honest reason this time: nobody has tried yet, not nobody can call it.

**THE BOUNDARY OF THE ANALOGY, measured**: replayed against the **91** sister declarations
(`**Barriere :**`) in the memory corpus, the clause accepts **71** and refuses **20**. Those 20 are
NOT false refusals: they are barriers that name **CODE** (`tests/test_x.py`) where a
failure must name a **NUMBER**. The two requirements are not the same, and pushing that rate to
zero would dissolve the item. The admission remains the free way out for those cases.
**HARDENED (2026-08-16, D75): THIS PARAGRAPH WAS A QUOTE, NOT A WITNESS.** Three
frozen strings copied by hand stood in for a replay - no test actually re-read the 91
declarations. Fixed: `tests/orchestration/test_regle_candidate.py
::test_eprouve_sur_les_declarations_SOEURS_reelles_de_la_memoire` re-reads the REAL memory folder
(not a frozen excerpt) and replays each declaration through the real public entry point (`lire()`).
Re-measured: **90** declarations today (a living population, not frozen), **69 accepted / 21
refused** - the same shape as the original measurement, this time verified by actually running it.

**WHAT THIS CLAUSE CANNOT DO, spelled out rather than assumed**: it checks that the failure is
**WRITTEN** and that it **CARRIES A NUMBER**. It does not check that the number is TRUE, or that it
measures the announced failure - no lexical detector knows that. A candidate that writes
``**Panne :** ca casse 3 fois sur 4`` having made it up **passes**. The only thing the clause
buys is that an author can no longer propose a rule **without asking themselves the question**, and
that the reader immediately sees whether the answer is a number or an admission.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

#: The declaration, in the form SISTER to the one used by lessons (`**Barriere :**` in `memoire.py`).
#: The colon may be glued to the word or spaced, the accent is optional - measured against the
#: repo's real records, which write it both ways.
_DECLARATION_DE_PANNE = re.compile(r"\*\*Pannes?\s*:", re.IGNORECASE)

#: ITS FORM WAS INVENTED, AND THE POPULATION WRITES A DIFFERENT ONE. I required `AUCUNE MESUREE`;
#: the real corpus of sister declarations writes *« aucune, et dite comme telle »*, *« aucune cote
#: Mnemosyne »*, *« partielle, et dite comme telle »*. Measured: across **91** real declarations, my
#: form + my measurement pattern refused **81, i.e. 89%**. So the word is read as
#: WRITTEN. *Reusing a form means reusing what is written, not what one would have written.*
_AVEU = re.compile(r"\*\*\s*Pannes?\s*:\*{0,2}\s*(?:aucune|partielle)\b", re.IGNORECASE)

#: The GRAMMATICAL words that follow a number without turning it into a measurement: *"le cas 2 DU
#: dossier"* ("case 2 OF the file"). These are excluded rather than enumerating units - a list of
#: units is always too short, a list of stopwords is closed by the language.
_MOTS_VIDES = r"(?:du|de|des|d['’]|le|la|les|un|une|et|ou|au|aux|dans|avec|pour|par|en|ce|cette|qui|que|a|à)\b"

#: A NUMBER that MEASURES: a factor (`x8`), a share (`9,7 %`), a ratio (`2 sur 7`, `3/4`), or
#: a number followed by its UNIT (`11 004 lignes`, `20 passes`, `23 temoins`).
#: MY FIRST VERSION ENUMERATED THE UNITS, AND THE LIST WAS TOO SHORT: an isolated audit
#: measured **29 false refusals out of 84**, and my own re-measurement **81 out of 91**. Worse, the
#: comment cited `x8` **AS PROOF** that the form was covered - it was not.
#: *An example cited as proof must be PULLED, never assumed.*
#: After the fix, across the **91** real declarations: **69 accepted, 22 refused** - and those
#: 22 are NOT false refusals (see the boundary of the analogy, at the top of the module).
_MESURE = re.compile(
    r"[x×]\s?\d"
    r"|\d[\d   ]*[.,]?\d*\s*(?:%|/\s*\d|sur\s+\d)"
    r"|\d[\d   ]*[.,]?\d*\s+(?!" + _MOTS_VIDES + r")[a-zà-ÿ]+",
    re.IGNORECASE,
)

#: HTML comments, stripped BEFORE any judgment - exactly what `memoire.py` does for
#: barriers (`_COMMENTAIRE`). Without this, a COMMENTED-OUT, hence inert, declaration would let the
#: gate pass: *reusing a form without reusing its PIPELINE is only half a reuse.*
_COMMENTAIRE = re.compile(r"<!--.*?-->", re.DOTALL)

#: The body of a declaration runs until the blank line or the next heading: a failure is declared
#: in one paragraph, not over the rest of the document.
_FIN_DE_BLOC = re.compile(r"^\s*$|^#{1,6}\s")


class ReglePromotionRefusee(Exception):
    """The refusal WHEN CALLED: the failure must be declared for THIS gate to let something
    through. "Impossible" would be a level-3 word about PROMOTION - and that would be false:
    nothing requires going through this gate, `make skill-new`/`make skill-eprouver` remain
    accessible without ever calling it (level 1, optional caller - fixed after an audit measured
    that the declared level 2 was built on the same reasoning as the already-dismantled level 3)."""


@dataclass(frozen=True, slots=True)
class Candidature:
    """What a candidate-rule record declares - read, never assumed."""

    source: str
    declaree: bool
    avouee: bool
    mesuree: bool
    texte_panne: str

    @property
    def promouvable(self) -> bool:
        """Promotable if the failure is declared AND (measured OR admitted with no measurement).

        Both branches are answers: a number, or an admission. It is the absence of a
        declaration that refuses, never the absence of a number."""
        return self.declaree and (self.mesuree or self.avouee)


def lire(texte: str, *, source: str) -> Candidature:
    """What the record declares. Refuses nothing - the refusal is `exiger_panne_declaree`."""
    texte = _COMMENTAIRE.sub("", texte)
    m = _DECLARATION_DE_PANNE.search(texte)
    if m is None:
        return Candidature(
            source=source, declaree=False, avouee=False, mesuree=False, texte_panne=""
        )
    lignes = texte[m.start() :].splitlines()
    corps = [lignes[0]]
    for ligne in lignes[1:]:
        if _FIN_DE_BLOC.match(ligne):
            break
        corps.append(ligne)
    bloc = "\n".join(corps)
    return Candidature(
        source=source,
        declaree=True,
        avouee=bool(_AVEU.search(bloc)),
        mesuree=bool(_MESURE.search(bloc)),
        texte_panne=bloc.strip(),
    )


def exiger_panne_declaree(candidature: Candidature) -> None:
    """THE MECHANISM (level 1, OPTIONAL caller - see the module docstring): raises if the
    rule cannot be promoted THROUGH THIS GATE. Does not make promotion impossible elsewhere:
    `make skill-new` remains accessible without ever calling this function.

    The message NAMES the way out - *the refusal message names the way out*, and both ways out
    are cited, including the admission, which is free."""
    if candidature.promouvable:
        return
    if not candidature.declaree:
        raise ReglePromotionRefusee(
            f"{candidature.source}: no failure declaration. A rule invented by a project "
            f"NAMES the MEASURED failure it prevents. Write `**Panne :** <what breaks, with its "
            f"figure>` -- or, if you measured nothing, `**Panne :** AUCUNE MESUREE`, which is a "
            f"valid and free answer."
        )
    raise ReglePromotionRefusee(
        f"{candidature.source}: the failure is declared but carries NO FIGURE "
        f"(« {candidature.texte_panne[:70]} »). Add the measurement, or write `**Panne :** AUCUNE "
        f"MESUREE` -- admitting you did not measure is an answer, inventing one is not."
    )


def lire_fiche(chemin: Path) -> Candidature:
    """The same read, from a file. An unreadable one does NOT raise: it returns a non-declared
    candidature, which the gate will refuse with its message - *a clause that kills its own
    surface is worse than no clause*."""
    try:
        texte = chemin.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        texte = ""
    return lire(texte, source=chemin.name)
