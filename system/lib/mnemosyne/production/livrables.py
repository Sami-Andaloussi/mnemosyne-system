"""G1 -- the DELIVERABLES list precedes the plan, with the requester's own CITATIONS.

THE FAULT THIS MODULE CLOSES, AND IT IS MEASURED. From an internal lesson dated 2026-07-28:
*"a plan is already a TRANSLATION; when I have it validated, the other person validates MY
UNDERSTANDING presented as a fact"*. The price: plan validated, **two rounds of audit**, and
**2 deliverables built out of 10 requested** -- one of which was a component of the other.
*The check was derived from the very thing it was supposed to check.*

A `LIVRABLES` file therefore carries **the requester's own words**, not my own rewording: it is
the one reference a plan cannot fabricate by itself. Same principle as the completeness clause
(`F3`), a different source.

**THIS MODULE DOES NOT IMPOSE A FORM: IT READS THE ONE THE POPULATION ALREADY WRITES.**
Measured BEFORE writing a line (an internal lesson: measure the population before imposing a
convention, or 3 plans out of 5 would have scored 0 against the format about to be imposed):

* **17 plan gates in this repo · only ONE** carries a deliverables list next to it
  (a `LIVRABLES_DEMANDES.md` file; the 17th is a worktree copy);
* and that one real instance writes **sections with block citations**, not "one line per
  deliverable". Imposing the line would have scored **0 out of 1/1** of the real population.

So: the accepted name is `LIVRABLES.md` **or** `LIVRABLES_DEMANDES.md`, and a deliverable is
**a heading that carries at least one block citation**. The form follows usage; it is usage that
decides, not me.

**AND PUBLISHING NEVER REFUSES OVER THE EXISTING POPULATION** (level 1): with 1 plan out of 16
conformant, a barrier would redden the entire repo for a convention nobody has been able to apply
yet. Level 2 is reserved for the BIRTH of a new plan, where the template is written in advance.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

#: The two accepted names. ``LIVRABLES_DEMANDES.md`` is the SOLE real instance in the repo:
#: removing it would drop the measured population's score from 100% to 0.
NOMS_LIVRABLES: tuple[str, ...] = ("LIVRABLES.md", "LIVRABLES_DEMANDES.md")

#: A deliverable = a level-2 or level-3 heading. Its NUMBER, when it carries one, is its citable
#: identifier (``## 1. THE HARVESTER`` -> ``1``); without a number it stays readable but not
#: citable, and is published as such rather than guessed.
#: All levels 2 to 6: bounded to `#{2,3}` used to make a `#### 2. DELIVERABLE` DISAPPEAR silently
#: -- exactly what this module's own docstring forbids ("published rather than ignored"). The
#: number tolerates a leading zero (`01.`) and reads as `1`, otherwise `## 01.` cited by
#: "deliverable 1" was declared NOT SERVED -- a false accusation.
_TITRE = re.compile(r"^(#{2,6})\s+(?:0*(\d{1,3})[.)]\s*)?(.+?)\s*$")

#: A non-empty blockquote line, NOT indented by four spaces (four spaces = code block, and a `>`
#: written inside one is not a citation).
_CITATION = re.compile(r"^ {0,3}>\s*\S")

#: AND THE CITATION MUST CARRY QUOTATION MARKS. An isolated audit showed that `^>\s*\S` does not
#: distinguish the requester's own words from an admonition I WROTE MYSELF
#: (`> **AGENT NOTE**`) -- and the ENTIRE value of this file rests on that distinction: *the one
#: thing a plan cannot fabricate*. This is not an imposed convention: measured on the repo's sole
#: real instance, **9 out of 9 cited deliverables** carry quotation marks. The population already
#: writes it that way.
#: And STRAIGHT quotation marks count too: measured across `docs/`, **19 blockquotes** carry
#: them -- the default key on every keyboard. Only recognising curly ones was a false accusation.
_GUILLEMETS = re.compile('[«»“”"]')

#: Opening / closing a code block: what it contains is neither a heading nor a citation. A
#: template shown as an example used to make 4 deliverables get read where there was only 1.
_FENCE = re.compile(r"^\s*(```|~~~)")

#: How an item SERVES a deliverable: it cites it by number. Deliberately strict, same lesson as
#: the completeness clause -- a keyword match would mark "served" a deliverable no item targets,
#: and would inflate the coverage this module exists to measure.
#: THE FRENCH PLURAL WAS A FALSE ACCUSATION: "les livrables 1 et 2" ("deliverables 1 and 2") --
#: the most natural phrasing in a French-speaking repo -- served ZERO deliverables, because the `s`
#: broke the match. `livrables?` accepts it, `#` and `n°` too, and a RANGE (`1 et 2`, `1, 2`) is
#: read in full. Leading zeros are folded as in `_TITRE`.
#:
#: **THIS PATTERN MATCHES THE FRENCH WORD "livrable(s)" ONLY, ON PURPOSE, AND IT MUST STAY
#: FRENCH — TODO(public-mirror): needs human review.** The private repo's real plan items write
#: their `*Sert*` ("*Serves*") field as literal French phrases such as `sert le livrable 1`
#: ("serves deliverable 1") or `idée à moi` ("my own idea", see `_IDEE_A_MOI_NORME` below) — this
#: regex, and that normalised constant, exist to recognise EXACTLY that real, French-language input.
#: Rewriting this pattern (or the fixtures/template text that exercise it below) into English would
#: silently stop it from matching the real plan data it is built for; that is a behaviour change
#: this sanitization pass must not make. So this pattern, `_IDEE_A_MOI_NORME`, every test fixture
#: string matched against it, and the worked "sert le livrable N" / "idée à moi" example inside
#: :func:`gabarit`'s emitted template all stay in their original French wording below, even where
#: the surrounding prose is translated to English.
_SERVI = re.compile(
    r"\blivrables?(?:\(s\))?\s*(?:n[°o]|#)?\s*"
    r"((?:0*\d{1,3})(?:\s*(?:,|et|&|à|a|-|–)\s*(?:n[°o]|#)?\s*0*\d{1,3})*)\b",
    re.IGNORECASE,
)
_NUMERO = re.compile(r"0*(\d{1,3})")


@dataclass(frozen=True, slots=True)
class Livrable:
    """A declared deliverable: its number (if it has one), its title, and whether it carries a citation."""

    numero: str
    titre: str
    ligne: int
    cite: bool


def lire_livrables(texte: str) -> tuple[Livrable, ...]:
    """The deliverables a ``LIVRABLES`` file declares.

    A heading **with no block citation at all** in its body is returned with ``cite=False`` rather
    than ignored: *a deliverable without the requester's own words is exactly the translation this
    file exists to prevent*, and staying silent about it would make it invisible."""
    # A Windows editor's BOM stuck to the first `#`, and the first deliverable DISAPPEARED IN
    # SILENCE (measured: 2 declared, 1 read). It does not raise, it LIES -- worse than the crash.
    lignes, ouvert = [], None
    for ligne in texte.lstrip("﻿").splitlines():
        if m := _FENCE.match(ligne):
            # A boolean toggle gets DESYNCHRONISED as soon as a `~~~` lives inside a ``` block: the
            # block's content became readable again, which REOPENED an already-closed defect. We
            # now remember the opening delimiter, and only the SAME one closes it.
            if ouvert is None:
                ouvert = m.group(1)
            elif m.group(1) == ouvert:
                ouvert = None
            lignes.append("")
            continue
        lignes.append("" if ouvert else ligne)
    entetes = [(n, m) for n, ligne in enumerate(lignes) if (m := _TITRE.match(ligne))]
    # THE DELIVERABLE'S LEVEL. Widening to `#{2,6}` opened a class: a `### Context` placed under
    # a `## 1. THE REAL ONE` STOLE its citation -- two false accusations at once (the parent
    # declared silent, the child declared not-citable) plus a phantom deliverable in the count. A
    # sub-heading belongs to its parent. The level kept is that of the FIRST NUMBERED heading; if
    # none, the highest one present.
    niveaux = [len(m.group(1)) for _, m in entetes]
    numerotes = [len(m.group(1)) for _, m in entetes if m.group(2)]
    if not entetes:
        return ()
    niveau = numerotes[0] if numerotes else min(niveaux)
    retenus = [(i, n, m) for i, (n, m) in enumerate(entetes) if len(m.group(1)) == niveau]
    out: list[Livrable] = []
    for i, n, m in retenus:
        fin = entetes[i + 1][0] if i + 1 < len(entetes) else len(lignes)
        # The body runs until the next heading OF THE SAME LEVEL: a sub-heading does not interrupt it.
        for j, (n2, m2) in enumerate(entetes[i + 1 :], start=i + 1):
            if len(m2.group(1)) <= niveau:
                fin = n2
                break
        else:
            fin = len(lignes)
        cite = any(
            _CITATION.match(ligne) and _GUILLEMETS.search(ligne) for ligne in lignes[n + 1 : fin]
        )
        # NEITHER A NUMBER NOR A CITATION MEANS PROSE, not a deliverable. Without this, `## The
        # framing` and `## Where things honestly stand` from the sole real file were counted as
        # deliverables and each got TWO warnings -- and the module contradicted itself: its
        # docstring says "a deliverable is a heading that carries a citation", its code said
        # "returned rather than ignored". The written condition and the code now name the SAME
        # population.
        if not m.group(2) and not cite:
            continue
        out.append(Livrable(numero=m.group(2) or "", titre=m.group(3), ligne=n + 1, cite=cite))
    return tuple(out)


def fichier_livrables(porte: Path) -> Path | None:
    """The ``LIVRABLES`` file sitting next to a plan gate, or ``None``."""
    for nom in NOMS_LIVRABLES:
        candidat = porte.parent / nom
        # `is_file()` FOLLOWS the link: a BROKEN symlink therefore reported "no LIVRABLES.md", and
        # the neighbouring reader's NAMED refusal ("broken link: the entry exists, the target is
        # not found") was lost. Its own docstring says why: *the report then tells the operator to
        # create the file, and the file is already there.* So we test the ENTRY, not its target.
        if candidat.is_file() or candidat.is_symlink():
            return candidat
    return None


def _hors_bloc(texte: str) -> str:
    """An item's text, its code blocks neutralised."""
    out, ouvert = [], None
    for ligne in texte.splitlines():
        if m := _FENCE.match(ligne):
            if ouvert is None:
                ouvert = m.group(1)
            elif m.group(1) == ouvert:
                ouvert = None
            continue
        out.append("" if ouvert else ligne)
    return "\n".join(out)


def livrables_non_servis(
    livrables: tuple[Livrable, ...], textes_items: tuple[str, ...]
) -> tuple[Livrable, ...]:
    """The deliverables **no item serves**, by strict citation of their number.

    A deliverable **without a number** can be served by no one: it is returned here, and the
    caller must say WHY (no number) rather than implying no item wants it."""
    # FIXED ASYMMETRY: code blocks were neutralised on the DELIVERABLES side and not on the
    # ITEM side -- the same fault on both sides. `rendre(livrable 2)` inside a code example
    # declared deliverable 2 SERVED.
    servis = {
        num.group(1)
        for texte in (_hors_bloc(x) for x in textes_items)
        for m in _SERVI.finditer(texte)
        for num in _NUMERO.finditer(m.group(1))
    }
    return tuple(liv for liv in livrables if not liv.numero or liv.numero not in servis)


def rendre(
    porte: Path, livrables: tuple[Livrable, ...] | None, non_servis: tuple[Livrable, ...]
) -> tuple[str, ...]:
    """The lines ``make plans`` prints for one plan. **Publishes, NEVER refuses** (level 1).

    Returning lines rather than printing them: the caller decides where they go, and the module
    stays pure -- so it is testable without capturing output."""
    if livrables is not None and not livrables:
        # `touch LIVRABLES.md` USED TO SILENCE THE WARNING and replace it with "0 · 0 · 0" --
        # three zeros that read like a HEALTHY report. The clause promised to name every plan
        # without a LIST; it only named those without a FILE. *An empty file is not a list.*
        return (
            f"      \U000026A0\U0000FE0F {porte.parent.name}/{'LIVRABLES'} exists but declares NO deliverable — "
            "an empty file is not a list, and the plan stays a TRANSLATION that nothing checks "
            "against the requester's own words (G1, level 1)",
        )
    if livrables is None:
        return (
            f"      \U000026A0\U0000FE0F no {' or '.join(NOMS_LIVRABLES)} next to {porte.name} — "
            "the plan is a TRANSLATION that nothing checks against the requester's own words (G1, level 1)",
        )
    doublons = sorted(
        {
            x.numero
            for x in livrables
            if x.numero and [y.numero for y in livrables].count(x.numero) > 1
        }
    )
    lignes = [
        f"      DELIVERABLES: {len(livrables)} declared · "
        f"{sum(1 for x in livrables if x.cite)} carry a citation from the requester · "
        f"{len(non_servis)} that no item serves"
    ]
    for liv in non_servis:
        pourquoi = "no number, so not citable" if not liv.numero else "no item cites it"
        lignes.append(f"        · {liv.numero or '—':>3} {liv.titre[:64]} ({pourquoi})")
    if doublons:
        # The number is declared "its identity": two deliverables under the same number used to be
        # SERVED AT ONCE by a single citation, and nothing said so.
        lignes.append(
            f"        \U000026A0\U0000FE0F number(s) carried by SEVERAL deliverables: {', '.join(doublons)} — "
            "a single citation serves them all at once"
        )
    muets = [x for x in livrables if not x.cite]
    for liv in muets:
        lignes.append(
            f"        \U000026A0\U0000FE0F {liv.numero or '—':>3} {liv.titre[:64]} — NO citation from the requester"
        )
    return tuple(lignes)


# ============================================================================================
# G2 -- corollary of G1: each ITEM points at its deliverable, or declares itself "my own idea".
#
# BLOCKED ON `plan_format.py`, NOT MY LOT (3rd arbitration, never settled): G2's *Deliverable*
# needs a `*Serves*` field on the item -- an entry in `FIELD_NAMES`/`EXTRA_FIELD_NAMES`, which live
# in `plan_format.py` (another chat's lot). WHAT FOLLOWS READS NO REAL FIELD: `juger_rattachements`
# takes `valeur` as a parameter, supplied by the caller -- today a test fixture, tomorrow (once the
# field exists) `item.field("sert")`. Same pattern as `E4` consuming `C4`'s future template: the
# emitter is built, it waits for its input, it does not invent it.
#
# WHAT WAS MEASURED BEFORE WRITING WHAT FOLLOWS (same discipline as G1 above): a workaround
# hypothesis -- reusing `_SERVI` on free text FROM THE ITEM SIDE rather than waiting for the field
# -- was tested and DISCARDED. Over the 61 real items of the project plan, only ONE already matches
# `_SERVI` (`G1` itself, a likely false positive: it TELLS a history, it does not SERVE anything).
# Unlike `LIVRABLES_DEMANDES.md` (the requester's FREE words, where imposing a form would break the
# measurement), a plan item is ALREADY a vocabulary controlled by `plan_format.py`'s grammar -- a
# structured field is the right choice there, not a workaround duplicating a mechanism outside the
# grammar that nothing blesses.
#
# LEVEL 2 ONLY BITES ON A NON-EXISTENT TARGET, never on an absent value -- same reasoning G1
# already wrote and proved for ITS OWN birth (`rendre()` above, level 1 on the existing population):
# refusing right away on "nothing declared yet" would redden the entire population that does not
# have the field yet, for a convention nobody could apply. Citing a number that does NOT exist, on
# the other hand, is an error at any stage of adoption -- it is the only thing
# `rendre_rattachements` names as a refusal. AND `make plans` ITSELF NEVER REFUSES (see `main()` in
# `plans_run.py`, an unconditional `return 0`): like G3's dead pointer, this item's real level 2
# lives in a FROZEN WITNESS over the real population (`tests/orchestration/test_livrables.py`),
# never in the exit code of a report that only publishes.
# ============================================================================================


@dataclass(frozen=True, slots=True)
class Rattachement:
    """The verdict for ONE item: does it serve a declared deliverable, does it declare itself
    "my own idea", or has it said nothing yet?

    ``valeur`` is the (future) raw text of the ``*Serves*`` field -- ``None`` if the item has not
    declared it yet, which is a NORMAL state, not a fault, during adoption (see the comment block
    above). ``numero`` is the deliverable number extracted from ``valeur``, when ``valeur`` cites a
    readable one. ``cible_existe`` is ``None`` when the question does not arise (``idee_a_moi``,
    ``valeur`` absent or unreadable) -- never ``False`` by default, so as not to manufacture a
    refusal where no target was cited at all."""

    ident: str
    valeur: str | None
    numero: str | None
    idee_a_moi: bool
    cible_existe: bool | None


def _normalise(texte: str) -> str:
    """Case and accents stripped -- the same tolerance `_SERVI` already applies to its French
    keywords, to compare a declared value against a constant without tripping on a missing accent."""
    sans_accents = "".join(
        c for c in unicodedata.normalize("NFD", texte) if unicodedata.category(c) != "Mn"
    )
    return sans_accents.strip().casefold()


#: The valid and free answer (same precedent as `NONE` for `*Prerequisites*`): an item that matches
#: no requester citation announces this rather than manufacturing an attachment.
#: TODO(public-mirror) — see the note above `_SERVI`: this is the literal French phrase real
#: plan items write ("idée à moi" = "my own idea") to signal exactly this state, matched via
#: `_normalise()`. It stays in French so the match keeps working against real plan data; only the
#: surrounding prose is translated.
_IDEE_A_MOI_NORME = "idee a moi"


def juger_rattachements(
    livrables: tuple[Livrable, ...], items: tuple[tuple[str, str | None], ...]
) -> tuple[Rattachement, ...]:
    """The verdict for each item, in the order supplied. Pure: reads neither disk nor a real field."""
    numeros_valides = {liv.numero for liv in livrables if liv.numero}
    out: list[Rattachement] = []
    for ident, valeur in items:
        if valeur is None:
            out.append(Rattachement(ident, None, None, False, None))
            continue
        if _normalise(valeur) == _IDEE_A_MOI_NORME:
            out.append(Rattachement(ident, valeur, None, True, None))
            continue
        m = _NUMERO.search(valeur)
        if m is None:
            out.append(Rattachement(ident, valeur, None, False, None))
            continue
        numero = m.group(1)
        out.append(Rattachement(ident, valeur, numero, False, numero in numeros_valides))
    return tuple(out)


def rendre_rattachements(jugements: tuple[Rattachement, ...]) -> tuple[str, ...]:
    """The lines `make plans` prints for G2. Publishes what is not declared yet (level 1, same
    reasoning as `rendre()` above); NAMES every citation of a deliverable that does not exist --
    the only real refusal, and it lives here in PROSE, not in an exit code (see the comment block
    at the top of this section for why)."""
    total = len(jugements)
    rattaches = tuple(j for j in jugements if j.numero is not None and j.cible_existe)
    idee_a_moi = tuple(j for j in jugements if j.idee_a_moi)
    orphelins = tuple(j for j in jugements if j.numero is not None and j.cible_existe is False)
    illisibles = tuple(
        j for j in jugements if j.valeur is not None and not j.idee_a_moi and j.numero is None
    )

    lignes = [f"      items_attached={len(rattaches)}/{total}"]
    if idee_a_moi:
        lignes.append(f"      own idea, no deliverable ({len(idee_a_moi)}): " + ", ".join(j.ident for j in idee_a_moi))
    for j in orphelins:
        lignes.append(
            f"      \U000026D4 REFUSED — {j.ident} serves deliverable {j.numero}, which does not exist"
        )
    if illisibles:
        lignes.append(
            f"      unreadable value, neither a number nor 'my own idea' ({len(illisibles)}): "
            + ", ".join(j.ident for j in illisibles)
        )
    return tuple(lignes)


#: The name a NEW plan receives. `LIVRABLES_DEMANDES.md` is still read (it is the repo's sole real
#: instance), but a newly BORN plan takes the short name: we read what exists, we write what follows.
NOM_A_LA_NAISSANCE = NOMS_LIVRABLES[0]


def gabarit(projet: str) -> str:
    """The `LIVRABLES.md` a NEW plan receives -- the LEVEL 2 half of the item.

    **Level 2 lives HERE and nowhere else.** On the existing population, the clause PUBLISHES and
    never refuses (17 gates measured, only one list): a barrier would redden the entire repo for a
    convention nobody could yet apply. At BIRTH, there is nothing to punish -- the template is
    written in advance, so the author starts with the list instead of owing it.

    **And it teaches the form the READER accepts**, not the one the item spells out. The item
    says "one line per deliverable"; the measurement says the sole real instance writes SECTIONS
    with block citations, and the reader followed the measurement. A template that taught the line
    would teach the author a form the clause cannot read.
    """
    return f"""# What {projet} must deliver — the REQUEST, not my own translation of it

> \U000026D4 **This file precedes the PLAN, and is NEVER derived from it.** A plan is already a
> TRANSLATION: having it validated gets MY UNDERSTANDING validated as if it were a fact. Measured
> on 2026-07-28, before this safeguard existed: plan validated, two rounds of audit, **2
> deliverables built out of 10 requested** -- and one of the two was a component of the other.
>
> \U00002B50 **The one thing a plan cannot fabricate is the REQUESTER'S OWN WORDS.** That is why every
> deliverable carries a VERBATIM citation, in quotation marks. A deliverable without a citation is
> flagged by `make plans` -- that is exactly the translation-drift this file exists to prevent.
>
> \U000026A0\U0000FE0F Nothing here is refused: `make plans` PUBLISHES what is missing. *That work remains is a
> fact, not a fault.*

## 1. <THE FIRST DELIVERABLE, in one sentence>

> « <the requester's EXACT words, copied verbatim, never reworded> » *(<date>)*

**What I understand from this**: <my own reading -- and THIS is what can be wrong, not the citation>

**Status**: \U00002B1C not started

## 2. <THE SECOND ONE>

> « <their words> » *(<date>)*

**What I understand from this**: <…>

**Status**: \U00002B1C not started

<!-- A plan item SERVES a deliverable by citing its number: « … sert le livrable 1 »
     (« … serves deliverable 1 »; keep this exact French phrasing, `make plans` parses it).
     `make plans` names the ones no item serves. -->
"""
