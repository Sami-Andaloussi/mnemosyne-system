"""IS THE OFFER TO PROJECTS ACTUALLY REACHABLE? - the barrier against drifting toward the crutch.

**WHY THIS MODULE EXISTS, AND THE OPERATOR DEMANDED IT (2026-08-18), verbatim**:

> *"What I don't want is for us to start using crutches when we already have the main tool. [...]
> We built project engineering, so let's make sure only project engineering can be used, and make
> sure it works the way it's supposed to work."*

**The mistake the operator named TWICE IN TWO DAYS, and that the repo never caught on its own:**

```
2026-08-17  docs/signalements/README.md told a PROJECT session to run `make signaler TITRE=...`
            -- the one gesture it could not type (make has no root outside the repo). The command
            was NAMED, never REACHABLE.
2026-08-18  a private governance document said "it WRITES the mandate for every chat" and
            never named `make lot-emit` ANYWHERE -- 0 occurrences. The tool existed, the
            document taught the manual path.
```

**Both times, it was the operator who found it - once on a hunch, once on a complaint. No gate
was watching.** *A reader cannot prefer the tool nobody names for them: their choice isn't "crutch
or tool", it's "crutch or nothing".*

**WHAT THIS MODULE JUDGES, and nothing else** - two questions, over the documents a project that
ADOPTS the system actually reads:

*(a)* **is every OFFERED capability named somewhere?** A capability nothing points to does not
exist for its recipient (D177);
*(b)* **does every document name the REACHABLE form AT LEAST ONCE** (`make -C <root>` or
`mnemo`)? A project session that reads `make plans` types it and gets `No rule to make target`.
**Once per document, never per citation** - it is the ADDRESS that is required (D163), not a
repetition on every line.

**WHAT IT DELIBERATELY DOES NOT JUDGE**: style, the presence of a manual verb ("it writes"), or
how well-phrased the prose is. *Detecting a manual verb would require understanding the sentence;
this module only measures verifiable facts - a string is there, or it isn't.* **The verb stays the
cheapest tell for a HUMAN proofreader, not a rule of code.**

**NEITHER THE POPULATION NOR THE OFFER SELF-DISCOVERS**: both are DECLARED below. Deriving the
offer from `make help` would pull in every internal target in the repo and drown the refusal in
noise; deriving the population from a scan would judge documents nobody ever sends to projects.
*A barrier whose population moves on its own never bites the same thing twice.*
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Final

#: The documents a project that ADOPTS the system actually reads - DECLARED, measured against the
#: addresses `CLAUDE.md` and the `SessionStart` hook publish, plus the contract that TRAVELS with
#: every mandate (`lot_emit.CONTRAT_DES_POSTES`) and the one `docs/signalements/README.md`
#: prescribes by name.
#: TODO(public-mirror): trimmed for this export - two of the private repo's six paths
#: (a governance document and a posts-contract document) sit outside this mirror's docs/
#: allow-list and do not exist on disk in this export, so the tests that read every declared path
#: (tests/platform/test_offre_aux_projets.py) would error against this export tree if they stayed
#: declared. Removed rather than left dangling: the private repo's own copy of this module still
#: carries all six.
DOCUMENTS_LUS_PAR_UN_PROJET: Final = (
    "CLAUDE.md",
    "docs/FORMAT_PLAN.md",
    "docs/parentheses/README.md",
    "docs/signalements/README.md",
)

#: **WIDENED ON 2026-08-18, A FEW HOURS AFTER IT WAS FIRST WRITTEN - AN ISOLATED AUDITOR MEASURED
#: THAT IT HAD BEEN CHOSEN TO BE GREEN.** The first version carried FOUR, and its verdict was
#: `0 missing` - because the documents that still carried the mistake were left out:
#: ```
#: CLAUDE.md                 cibles=16  atteignable=False   <- and its line 147 told a PROJECT
#:                                                              session to run `make signaler`:
#:                                                              THE 2026-08-17 mistake, the very
#:                                                              one this module exists for
#: docs/parentheses/README.md cibles=3  atteignable=False
#: ```
#: **Worse than an oversight: `CLAUDE.md` had served as the SOURCE for establishing the
#: population, and had never been JUDGED by it.** *A population derived from a document exempts
#: that document - and that is exactly where the mistake was sleeping.*
#: **The test that would have caught it, and that holds for any hand-written population**:
#: *"have I checked the barrier against the documents that were used to build it?"*

#: The capabilities OFFERED to a project (D176: offered, never imposed) - the ones an adopter
#: needs in order to be born, run, be judged, and file a report. Not every Makefile target:
#: only the ones addressed to a PROJECT.
CAPACITES_OFFERTES: Final = (
    "carte",
    "describe",
    "gel-inscrire",
    "lot-emit",
    "parenthese-fermer",
    "parenthese-ouvrir",
    "parentheses",
    "plan-emit",
    "plan-gate-emit",
    "plan-nouveau",
    "plans",
    "signaler",
)
#: **COMPLETED ON 2026-08-18 with what the SCAFFOLD already offers** - `plan_scaffold.py` writes
#: `make describe`, `make plan-emit`, `make plan-nouveau` and the address of the parentheses
#: **INTO the adopter's own `PLAN.md`**. *Five capabilities were being offered by the artefact
#: that physically lands in the adopter's repo, without appearing in this list - so never judged.*

#: A `make` target cited, in any form (`make X` or `make -C <root> X`).
_CIBLE_CITEE: Final = re.compile(r"make\s+(?:-C\s+\S+\s+)?([a-z][a-z0-9-]{2,})")

#: The REACHABLE form from a project folder - `make -C <root> <target>`, or the `mnemo` shell
#: function `J4` set up. It is the ONLY form a project session can type.
_FORME_ATTEIGNABLE: Final = re.compile(r"make\s+-C\s+\S+\s+[a-z]|mnemo\s+[a-z]")


def cibles_citees(texte: str) -> frozenset[str]:
    """The `make` targets this text names - in any form."""
    return frozenset(_CIBLE_CITEE.findall(texte))


def nomme_la_forme_atteignable(texte: str) -> bool:
    """Does this text teach, at least once, how to invoke a target FROM a project?"""
    return bool(_FORME_ATTEIGNABLE.search(texte))


def capacites_non_adressees(
    documents: Mapping[str, str], *, offertes: tuple[str, ...] = CAPACITES_OFFERTES
) -> tuple[str, ...]:
    """The offered capabilities that NO document read by a project names (D177).

    *A capability not addressed from what the recipient actually reads is not a capability: it's
    a note to self.* Sorted, so two runs name the same gap in the same order."""
    tout = "\n".join(documents.values())
    citees = cibles_citees(tout)
    return tuple(sorted(c for c in offertes if c not in citees))


def documents_sans_forme_atteignable(documents: Mapping[str, str]) -> tuple[str, ...]:
    """The documents that cite at least one `make` target without ever showing how to invoke it
    from a project. A document that cites NO target at all is not at fault -- it promises
    nothing; it's the one citing a target without its address that sends its reader into the wall."""
    return tuple(
        sorted(
            chemin
            for chemin, texte in documents.items()
            if cibles_citees(texte) and not nomme_la_forme_atteignable(texte)
        )
    )


def message_offre(
    non_adressees: tuple[str, ...], sans_forme: tuple[str, ...]
) -> str:
    """Publish the two gaps - and NAME the gesture, never just the defect."""
    if not non_adressees and not sans_forme:
        return (
            "offer to projects: every offered capability is named, and every document shows "
            "the reachable form from a project."
        )
    lignes: list[str] = []
    if non_adressees:
        noms = ", ".join(f"`make {c}`" for c in non_adressees)
        lignes.append(
            f"\U000026D4 {len(non_adressees)} OFFERED CAPABILITY(IES) THAT NO DOCUMENT READ BY A PROJECT "
            f"NAMES: {noms}.\n"
            "   An adopter cannot prefer the tool nobody names for them: their choice isn't "
            "\"crutch or tool\", it's \"crutch or nothing\".\n"
            "   THE GESTURE: cite the capability in the document where its use comes up "
            f"(among {', '.join(DOCUMENTS_LUS_PAR_UN_PROJET)})."
        )
    if sans_forme:
        lignes.append(
            f"\U000026D4 {len(sans_forme)} DOCUMENT(S) CITING A `make` TARGET WITHOUT EVER SHOWING ITS "
            f"REACHABLE FORM: {', '.join(sans_forme)}.\n"
            "   From a project folder, `make <target>` returns `No rule to make target` - the "
            "reader thinks the tool is broken and falls back to doing it by hand.\n"
            "   THE GESTURE: name, ONCE in this document, "
            "`make -C ~/mnemosyne <target>` (or the `mnemo` function)."
        )
    return "\n".join(lignes)
