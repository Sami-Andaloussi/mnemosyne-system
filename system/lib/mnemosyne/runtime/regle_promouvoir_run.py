"""I3(b) -- the connector that gives `exiger_panne_declaree` a REAL CALLER.

 **WHAT THIS MODULE CLOSES.** `production/regle_candidate.py` builds a level-2 judge --
`exiger_panne_declaree` RAISES if a candidate rule does not declare its failure -- but an isolated
audit measured that NOTHING called it: no `make` target, no hook, no production site.
the project's governance note on obligation levels settles it: *"the level is that of its CALLER,
never that of its code."* This module IS that caller: it reads a candidate-rule fiche, requires its declared
failure, and REFUSES (`rc 1`) otherwise -- a refusal that whoever invokes it must consume before
moving on to the differential trial.

 **WHAT IT DOES NOT DO, and it is deliberately narrow.** It launches NO trial itself.
`make skill-eprouver` requires an ALREADY-BUILT skill (`system/skills/<name>/SKILL.md`) -- a fiche
from `knowledge/proposals/` is not one until it has been scaffolded (`make skill-new`). This
module therefore stops AT THE GATE: it refuses if the declared failure is missing, and on success
it NAMES the exact chain to follow -- it never executes it in the operator's place. *A gate placed
on an assumed call site is the fault this module closes, not a fault to reproduce anew.*

 **LEVEL 1, NOT 2 -- corrected after a third audit, and the mistake was worth naming.** An
earlier version of this docstring wrote *"level 2, actually exercised as soon as a candidate
crosses it"* -- circular: nothing OBLIGES a candidate to cross this gate, `make skill-new` and
`make skill-eprouver` remain reachable without ever calling it. The gate REFUSES when called (that
proves it works); it does not prove one is obliged to go through it. Same reasoning as the
fictitious level 3 on promotion, one notch down -- dismantled there, left standing on this module.
The same governance note now says it in so many words: *"the level stays 1, not 2."*
`make regle-promouvoir` (chat 2, `96a05f1`) gives this module a REAL invocation site -- that is
what moves it out of the registry's "unverifiable" population -- but an optional invocation site
is still a level 1, not a level 2.

Code & docstrings English (D117). Decisions: D75, D92, D100.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from ..production.regle_candidate import ReglePromotionRefusee, exiger_panne_declaree, lire_fiche

#: Prefixes stripped from the file name to derive a readable skill name -- a DATE (a fiche's
#: deposit identity, never a skill's) and the word that just says "it's a draft", already carried
#: by the fiche's own `status:` field.
_PREFIXES_A_RETIRER = (
    r"^\d{4}-\d{2}-\d{2}-",
    r"^proposition-",
)


def nom_de_skill(chemin: Path) -> str:
    """A skill name PROPOSED from the file name -- never guaranteed stable: it is a starting point
    the operator corrects with `NAME=` if they keep it. This module does not PROMISE a name,
    it NAMES one so the next gesture has something to type."""
    nom = chemin.stem
    for motif in _PREFIXES_A_RETIRER:
        nom = re.sub(motif, "", nom)
    return nom or chemin.stem


def _chaine_suivante(chemin: Path, skill: str) -> str:
    return (
        f"PROMOTABLE -- {chemin.name} declares its failure. Next gesture, IN THIS ORDER "
        "(nothing below is launched by this module):\n"
        f"  1. if system/skills/{skill}/SKILL.md does not exist yet:\n"
        f"       make skill-new NEED=\"<what the skill must do>\" NAME={skill}\n"
        f"  2. make skill-eprouver SKILL={skill} TACHE=\"...\" OUT=/tmp/epreuve-{skill}\n"
        "  3. run the TWO emitted mandates, each by a FRESH and ISOLATED agent (one arm must\n"
        "     know nothing of the other)\n"
        f"  4. make skill-juger EPREUVE=/tmp/epreuve-{skill} AVEC=<output-1> SANS=<output-2>\n"
        "  5. the judge's mandate goes to a THIRD isolated agent, blind to which arm is which\n"
        f"  6. make skill-verdict EPREUVE=/tmp/epreuve-{skill} SKILL={skill} ... VERDICT=<...>\n"
        "The trial journal (`make skill-epreuves`) then carries this candidate with its verdict,\n"
        "including when the verdict is `ne_differencie_pas` -- that is a result, not a failure."
    )


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        print(
            "usage: python -m mnemosyne.runtime.regle_promouvoir_run <fiche.md>", file=sys.stderr
        )
        return 2
    chemin = Path(args[0])
    candidature = lire_fiche(chemin)
    try:
        exiger_panne_declaree(candidature)
    except ReglePromotionRefusee as refus:
        print(f"REFUSED -- {refus}", file=sys.stderr)
        return 1
    print(_chaine_suivante(chemin, nom_de_skill(chemin)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
