"""C4 -- the `*To read*` field (already readable by `plan_format.py`): its LOAD and its TEMPLATE.

**THIS MODULE DOES NOT TOUCH `plan_format.py`**: the `a_lire` field is **already** a known
field there (`_FIELD_BY_KEY`, `KNOWN_FIELDS`), verified against the 53 items of the real plan
before writing a line -- 0 missing field. `plan_format.py` is another chat's lot. This module
CONSUMES `item.fields`; it does not produce it.

*Deliverable* of the item (the project plan, item C4): **(a)** computing an item's load in bytes
**without opening it**; **(b)** the mandate template that uses it.

**THE FORM IS NOT INVENTED, IT IS MEASURED** -- third time tonight, **re-verified by an isolated
audit down to the exact figure**. Over the 53 real `*To read*` fields: 117 tokens between
backticks, 65 contain a `/`, **58 resolve** against three roots (the repo, `system/lib/mnemosyne/`,
`projects/saas/flagship/`). The remaining 7, checked one by one against real data: 4
FOLDERS, 2 `*` patterns, and **1 relative path that is simply incomplete** (missing its leading
directory) -- a third category the enumeration did not name, with no code consequence: still
correctly left unresolved. **A bare filename without `/` is NEVER resolved**: the repo carries
several files with the same name in different places (297 `__init__.py` measured) -- guessing from
the name alone would risk attributing the load to the WRONG file. *An ambiguous path is not
resolved; it is named unresolved.*

**WHAT `C4` READS BEFORE WRITING THE TEMPLATE** (its own `*To read*`): two internal lessons about
mandate bias --

* three paying clauses out of eight tested: label beliefs as beliefs, a two-branch exit clause,
  state what is ALREADY covered;
* an unlabelled fact gets confirmed; a labelled fact gets measured.

The template below applies them: it asserts nothing as a fact, it **cites** the published field.

**NO PRODUCER REASONING**: the same promise as `lot_emit.rendre()` (E4) -- composed only of
`ident`, `title`, and the `a_lire` field itself (never `detail`, never a `fields` entry other than
`a_lire`). *Two witnesses of the same promise diverging means the second one is lying* -- so the
same predicate, not a second one invented.
**Fixed after an isolated audit**: this sentence used to also cite `status` -- `rendre_gabarit`
never reads it (`lot_emit.rendre()` already shows it in its own item list, before calling this
template). A harmless overclaim, but an inaccurate admission is still an admission to fix.

**LEVEL 2** -- required field, `NONE` a valid and free answer (C4, `*Obligation*`). An item
without `a_lire` returns a `None` load: this is not an absent measurement, it is the measurement of
an absence.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from .plan_format import PlanItem

#: A token between backticks in the `*To read*` field text -- the form the population writes.
_TOKEN = re.compile(r"`([^`]+)`")

#: The three roots measured against the real plan -- not guessed. `system/lib/mnemosyne/` covers
#: production paths written WITHOUT their full prefix (`production/plan_format.py`, not
#: `system/lib/mnemosyne/production/plan_format.py`); `projects/saas/flagship/` covers the
#: flagship project's own paths, written relative to its own root.
_RACINES: Final = ("", "system/lib/mnemosyne", "projects/saas/flagship")

#: **`projects/saas/flagship` ABOVE IS A FIX THAT ABSORBED ITS OWN MEASURED POPULATION
#: (2026-08-18).** It was written when the flagship project was the ONLY adopter: the capability "a
#: project cites its files relative to ITS OWN root" has therefore existed from the start -- but by
#: name, for a single project. **The second adopter paid for it immediately** (`make lot-emit`)
#: returned `9 unresolved references, total load 0 bytes`, and had to prefix EACH of its citations
#: with `projects/personal/second-project/` to be read -- its own files, addressed relative to
#: Mnemosyne.
#: *The second adopter is its OWN git repo: these paths make no sense inside it, and all break the
#: day it is cloned alone or moved.*
#:
#: **The fix is the `base_projet` parameter below: the caller, who KNOWS which plan it is
#: reading, passes THIS project's root.** General by construction -- no project is named in it.
#: **Why NOT "add every `projects/` bubble to the roots"**, the solution that looked simplest:
#: two projects can carry the same relative path (`plan/socle.md`), and a multi-project resolution
#: would then attribute one project's bytes to the other's item, IN SILENCE -- exactly what the
#: refusal of slash-free tokens already exists to prevent, two lines below. *Only one extra base,
#: the one that owns the plan, can never be confused.*
#: **The flagship entry stays**: it is now redundant for any caller that passes `base_projet`, but
#: removing it would break any caller that does not yet pass it. *A fix that has become redundant
#: is retired by a measurement, never by deduction.*


@dataclass(frozen=True, slots=True)
class Charge:
    """An item's load -- what was resolved, and what was NOT, never conflated."""

    octets: int
    references_resolues: tuple[str, ...]
    references_non_resolues: tuple[str, ...]

    @property
    def complete(self) -> bool:
        """True if EVERY cited reference was resolved -- otherwise the load is a FLOOR."""
        return not self.references_non_resolues


def _champ_a_lire(item: PlanItem) -> str | None:
    for cle, valeur in item.fields:
        if cle == "a_lire":
            return valeur
    return None


def references(item: PlanItem) -> tuple[str, ...]:
    """The raw tokens between backticks of the `*To read*` field -- unresolved, just extracted."""
    champ = _champ_a_lire(item)
    if champ is None:
        return ()
    return tuple(_TOKEN.findall(champ))


def _resoudre(token: str, racine: Path, base_projet: str | None = None) -> Path | None:
    """An EXPLICIT path (contains `/`) resolved against the three measured roots.

    A token WITHOUT `/` is never resolved -- `ligne.py` exists in several places in the repo, and
    guessing which one would attribute one file's load to another, in silence.

    **CONTAINMENT GAP, FOUND BY AN ISOLATED AUDIT (D75)**: ``pathlib`` DROPS the left side of a
    ``/`` when the right-hand operand is absolute (`racine / "/etc/hosts"` equals `/etc/hosts`) --
    not a ``pathlib`` bug, a documented behaviour `_resoudre` was not guarding against. And
    `is_file()` never normalises `..`: `racine / "../../../etc/hosts"` escapes the three declared
    roots to any file readable by the process. Reproduced by the audit, confirmed by me:
    ``_resoudre('/etc/hosts', racine)`` returned `/etc/hosts`; ``_resoudre('../../../../../../etc/
    hosts', racine)`` returned the same file, outside the repo. *"Without opening it" stayed true
    (only `stat().st_size` is read) -- but an item's load could count bytes from a file that
    NOTHING in the three roots justifies.*
    **Measured before fixing, never triggered in production so far**: none of the plan's 117 real
    tokens starts with `/` or `../` -- a real hole, dormant, not active."""
    chemin = token.split(":")[0].strip()
    if chemin.startswith("/"):
        return None
    if "/" not in chemin:
        # THE BARE NAME STAYS REFUSED EVERYWHERE -- EXCEPT UNDER `base_projet`, AND THE REASON
        # FOR THE REFUSAL SAYS WHY ITSELF (2026-08-18). The rule exists because "`ligne.py` exists
        # in several places in the repo, and guessing which one would attribute one file's load to
        # another, in silence": it is a rule against AMBIGUITY, never against bare names as such.
        # Under ONE project root DECLARED by the caller, the ambiguity does not exist: there is
        # a single `faits.md` at `<base_projet>/faits.md`, or there is none. Nothing is guessed.
        # MEASUREMENT that made this necessary: the second adopter cites its own root files as
        # `faits.md`, `contraintes.md` -- the most natural form for a project talking about itself.
        # Without this branch it had to write `projects/personal/second-project/faits.md`, paths
        # that make no sense inside its own git repo.
        # Only ONE base is tried here, NEVER `_RACINES`: widening the bare name to the whole
        # repo would be exactly the fault the original rule closes.
        if not base_projet:
            return None
        candidat = racine / base_projet / chemin
        try:
            resolu = candidat.resolve()
        except OSError:  # pragma: no cover - resolution that fails (symlink loop)
            return None
        if resolu.is_file() and resolu.is_relative_to(racine.resolve()):
            return resolu
        return None
    racine_resolue = racine.resolve()
    # `base_projet` FIRST: for a project's own plan, ITS files win over a namesake elsewhere in the
    # repo. The containment check below applies to it just as to the others.
    for sous_racine in ((base_projet,) if base_projet else ()) + _RACINES:
        candidat = (racine / sous_racine / chemin) if sous_racine else (racine / chemin)
        try:
            resolu = candidat.resolve()
        except OSError:  # pragma: no cover - a path whose resolution fails (symlink loop)
            continue
        # THE CONTAINMENT: a `..` can escape ITS sub-root (`system/lib/mnemosyne/../..`) without
        # escaping the REPO -- that is legitimate, one of the three roots can contain another. What
        # is NEVER legitimate is escaping the whole repo: that is the only boundary checked.
        if resolu.is_file() and resolu.is_relative_to(racine_resolue):
            return resolu
    return None


#: **AN "UNRESOLVED" COUNTER WAS AGGREGATING THREE REALITIES THAT CALL FOR OPPOSITE MOVES** --
#: found on 2026-08-16 by a second chat (analysis supplied, verified by me against the real
#: population, never taken on faith without re-measuring). Over the plan's real 59 unresolved bare
#: (no `/`) tokens: **23 really exist** (blocked by the caution above, DELIBERATELY -- "fixing"
#: them would break it), **35 are not files AT ALL** (memory notes, function names, `make` targets,
#: item ids -- `an-immobile-count-names-a-class`, `read_plan`, `make depense`, `A6`), and **only 1
#: is genuinely unfindable** (a file the plan cites but that does not exist). *The word "unresolved"
#: is reserved for that last one -- the other two are legitimate answers, not debts.*
RAISON_INTROUVABLE: Final = "not_found"
RAISON_CHEMIN_COURT: Final = "short path, not counted out of caution"
RAISON_HORS_PERIMETRE: Final = "outside the repo's scope"

#: Folders never useful to a plan citation -- pruned so indexing stays fast (measured: an
#: un-pruned `rglob` from the repo root took 13.6s for 59 tokens; pruned, 0.3s -- 45x, on the SAME
#: population, SAME result).
_ELAGUES: Final = frozenset(
    {".git", ".venv", ".venv-flagship", "node_modules", "knowledge", "__pycache__", ".mypy_cache",
     ".ruff_cache", ".pytest_cache"}
)


def _index_bases(racine: Path, base_projet: str | None = None) -> frozenset[str]:
    """Every filename reachable from the three declared roots -- a single walk.

    Built ONCE per call to :func:`rendre_gabarit`, never per token: walking the tree once then
    looking it up in a ``set`` beats walking the tree once PER token, measured 45x slower on the
    real population for the same result. `projects/` is NOT walked from the repo root:
    `projects/saas/flagship` already has its own entry in `_RACINES`, and letting the walk
    from the root descend into it would search the OTHER bubbles (`trading/`, `personal/`) that
    nothing declares as a resolution root."""
    vus: set[str] = set()
    racine_resolue = racine.resolve()
    for sous_racine in ((base_projet,) if base_projet else ()) + _RACINES:
        base = (racine / sous_racine) if sous_racine else racine
        if not base.is_dir():
            continue
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = [d for d in dirnames if d not in _ELAGUES and not d.startswith(".")]
            if Path(dirpath) == racine_resolue or Path(dirpath) == racine:
                dirnames[:] = [d for d in dirnames if d != "projects"]
            vus.update(filenames)
    return frozenset(vus)


def _raison_bare(chemin: str, index: frozenset[str]) -> str:
    """Why THIS bare (no `/`) token is not in `references_resolues` -- never a generic word for
    three opposite realities (see :data:`RAISON_INTROUVABLE` and its siblings)."""
    if chemin in index:
        return RAISON_CHEMIN_COURT
    if "." not in chemin:
        return RAISON_HORS_PERIMETRE
    return RAISON_INTROUVABLE


def charge_en_octets(
    item: PlanItem, racine: Path, base_projet: str | None = None
) -> Charge | None:
    """An item's load, WITHOUT opening it -- `*Done when*` of `C4`, word for word.

    ``None`` when the item does not carry a `*To read*` field at all: that is `NONE`, a valid and
    free answer (C4 level 2) -- never an invented zero for an item that said nothing.

    ``base_projet`` (a path RELATIVE to ``racine``, e.g. ``projects/personal/second-project``) lets a
    project's plan cite ITS OWN files relative to ITS OWN root -- see the note under
    :data:`_RACINES`. Absent, behaviour is exactly as before.

    **"STRICTLY ADDITIVE" WAS FALSE, AND AN ISOLATED AUDITOR MEASURED IT (2026-08-18).** No
    resolution is LOST -- verified diffed over 139 real tokens + 20 synthetic ones, ``0``
    divergence without ``base_projet``. **But the base is tried FIRST**, so the same token can now
    resolve to a **DIFFERENT file**, without ``complete`` moving: ``sous/x.py`` was worth 10 bytes
    at the root, it is now worth 999 under the base. **This is INTENTIONAL** -- for a project's
    own plan, its own files must win over a namesake elsewhere in the repo -- *but it is a change of
    MEANING, not only of reach, and calling it "additive" implied the opposite.* Frozen by a
    dedicated witness so this is a decision, not an accident. Measured on the real population the
    day of the fix: ``0`` token changes file.
    """
    toks = references(item)
    if not toks:
        return None
    resolues: list[str] = []
    non_resolues: list[str] = []
    octets = 0
    for tok in toks:
        chemin = _resoudre(tok, racine, base_projet)
        if chemin is None:
            non_resolues.append(tok)
        else:
            resolues.append(tok)
            octets += chemin.stat().st_size
    return Charge(
        octets=octets,
        references_resolues=tuple(resolues),
        references_non_resolues=tuple(non_resolues),
    )


def rendre_gabarit(
    items: tuple[PlanItem, ...],
    racine: Path,
    *,
    deja_couvert: tuple[str, ...] = (),
    base_projet: str | None = None,
) -> str:
    """The mandate template -- assembled from PUBLISHED fields, never from reasoning.

    Applies the three clauses from the mandate-bias lessons: beliefs are CITED (never asserted),
    the exit has two branches, what is already covered is named separately from the new angle --
    so the Nth reader does not redo the first reader's work."""
    lignes = ["## Mandate context — assembled, not drafted", ""]
    index = _index_bases(racine, base_projet)
    total_octets = 0
    total_introuvables: list[str] = []
    total_chemin_court: list[str] = []
    for item in items:
        charge = charge_en_octets(item, racine, base_projet)
        lignes.append(f"### {item.ident} — {item.title}")
        if charge is None:
            lignes.append("  *To read*: NONE (the item cites no reading)")
            continue
        for tok in charge.references_resolues:
            lignes.append(f"  - `{tok}`")
        for tok in charge.references_non_resolues:
            chemin = tok.split(":")[0].strip()
            if "/" in chemin:
                lignes.append(f"  - `{tok}` (reference NOT resolved — ambiguous path or folder)")
                total_introuvables.append(tok)
                continue
            raison = _raison_bare(chemin, index)
            if raison == RAISON_CHEMIN_COURT:
                lignes.append(
                    f"  - `{tok}` (short path, not counted out of caution — the file exists, "
                    "a bare name would stay ambiguous)"
                )
                total_chemin_court.append(tok)
            elif raison == RAISON_HORS_PERIMETRE:
                lignes.append(
                    f"  - `{tok}` (outside the repo's scope — not a file to load: "
                    "memory note, function, item, command…)"
                )
            else:
                lignes.append(f"  - `{tok}` (reference NOT resolved — not found)")
                total_introuvables.append(tok)
        total_octets += charge.octets
    morceaux = []
    if total_introuvables:
        morceaux.append(f"{len(total_introuvables)} unresolved reference(s)")
    if total_chemin_court:
        morceaux.append(f"{len(total_chemin_court)} short path(s) not counted out of caution")
    lignes += [
        "",
        f"total load: {total_octets} bytes"
        + (f" (FLOOR — {', '.join(morceaux)})" if morceaux else ""),
        "",
        "## What is ALREADY covered — don't redo it",
        (
            "\n".join(f"  - {c}" for c in deja_couvert)
            if deja_couvert
            else "  (nothing: you are the first on this angle)"
        ),
        "",
        "## The exit clause, in TWO branches",
        "  1. If you find a fix that these criteria forbid, do NOT apply it — "
        "report it with its MEASURED COST.",
        "  2. If you identify a failure mode BEFORE writing it, state the failure mode and do NOT "
        "PUT A NUMBER ON IT.",
        "",
        "\U000026A0\U0000FE0F Every fact above comes from a PUBLISHED field of the plan, never from the producer's "
        "own reasoning. If it is wrong, say so and measure it — do not just confirm it.",
    ]
    return "\n".join(lignes) + "\n"
