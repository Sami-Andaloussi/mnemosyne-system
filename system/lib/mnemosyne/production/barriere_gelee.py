"""THE BARRIER THAT PROTECTS THE BARRIER (G5 candidate from the flagship project's harvest).

> *"the classic defect is the door that nothing calls. Here the door is called on every
> commit, and **it's THE FREEZE GUARDING IT that lives outside**"*.

**PURE** judge: two sets of strings go in, a verdict comes out. No disk access, no
`os.environ`, **nothing from the flagship project inside** — the population is INJECTED by the edge.

## A FLOOR, NEVER AN EQUALITY — and that is what sets it apart from its two neighbors

The repo already carries **two set-freezes**, and naming them is a debt, not a nicety
(D163: the address, never the copy):

* :func:`mnemosyne.production.sites_de_sortie.verdict` — double difference, **refuses in both
  directions** (`apparus` **and** `disparus`). Just for imports, where every new export must be
  declared before it exists.
* :func:`mnemosyne.production.derives.verdict_adoption` — same shape, on plan doors.

**This module does not copy them, it changes POLICY**, and for a measured reason: those two
guard populations that are meant to stay **closed**, whereas a NEW validation pass is
**progress**. An equality would refuse the commit that adds a pass — and *a wall installed full
gets bypassed the same day* (`--no-verify`). So:

* a **frozen pass that has disappeared** ⇒ **REFUSAL**, named;
* a **living pass outside the freeze** ⇒ **PUBLISHED**, never refused (the canary, the same role
  as :func:`~mnemosyne.production.derives.ecart_adoption`).

## THE SET, NEVER THE COUNT

*A SWAP would leave the count identical*: one pass removed, another added, and a judge that
compares `5 == 5` stays **silent**. Here the two movements are named separately.

## THE FREEZE IS READ BY IMPORTING THE OBJECT, NEVER BY `grep`

That property does not live in this file — it lives at the **edge**
(:mod:`mnemosyne.runtime.passes_run`), which imports :data:`~.recensement_des_passes.PASSES_GELEES`
instead of re-reading the module's text. It is written here because this is where it is promised,
and it is **held by a witness** that turns red the moment the edge starts reading text instead: a
freeze re-read by pattern disarms itself at the first reformat, and it disarms **silently**.

English prose for this mirror (D117).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class VerdictGel:
    """The two movements, kept separate — and the compared CARDINAL, published with them.

    ``comparees`` exists because it is the only field that says whether the comparison **actually
    took place**: *an equality over zero pairs is true by construction*. A verdict over an empty
    population is therefore not a green light, it is :attr:`non_mesure`."""

    #: Frozen entries that no living pass covers — the only grounds for REFUSAL.
    disparues: tuple[str, ...]
    #: Living entries outside the freeze — published, never refused (the floor).
    neuves: tuple[str, ...]
    #: Frozen entries actually found alive.
    tenues: tuple[str, ...]
    comparees: int

    @property
    def non_mesure(self) -> bool:
        """True when nothing could be compared — an instrument failure, distinct from a refusal."""
        return self.comparees == 0

    @property
    def refuse(self) -> bool:
        """The refusal is based on DISPARUES alone. ``neuves`` plays no part in it: that is the
        "floor" half of this module, and adding it in would make it identical to its two neighbors."""
        return bool(self.disparues)


def verdict(vivantes: Iterable[str], gelees: Iterable[str]) -> VerdictGel:
    """The judge: every frozen entry must be found among the living ones. ``gelees ⊆ vivantes``.

    ``comparees`` counts the **living** entries, not the frozen ones: that is the population
    that was actually fetched from the world. Counting the frozen entries would produce a constant
    cardinal, true even when the instrument read nothing at all — exactly the false green light
    this is meant to make impossible."""
    vues = frozenset(vivantes)
    attendues = frozenset(gelees)
    return VerdictGel(
        disparues=tuple(sorted(attendues - vues)),
        neuves=tuple(sorted(vues - attendues)),
        tenues=tuple(sorted(attendues & vues)),
        comparees=len(vues),
    )


def message(v: VerdictGel, *, quoi: str = "passe") -> str:
    """The published sentence. It NAMES what is missing, and it **always** says how much it judged.

    *The refusal message names the way OUT*: without the gesture to make, the next reader
    loosens the judge instead of satisfying it."""
    if v.non_mesure:
        return (
            f"\U000026A0\U0000FE0F GEL DES {quoi.upper()}S NON MESURE : zero {quoi} vivante comparee. « aucune "
            f"{quoi} perdue » et « je n'ai pas pu regarder » ne se lisent pas pareil — une "
            "comparaison sur zero paire est vraie par construction."
        )
    if v.refuse:
        return (
            f"\U000026D4 GEL ROMPU ({v.comparees} {quoi}(s) vivante(s) comparee(s)) : "
            f"{len(v.disparues)} {quoi}(s) gelee(s) ne sont plus la — "
            + ", ".join(v.disparues)
            + ". Une passe gelee qui disparait emporte son refus AVEC elle, et le depot reste "
            "vert. RETABLIS-LA, ou retire-la du gel DANS LE MEME COMMIT en disant ce que sa "
            "disparition permet desormais."
        )
    ligne = f"gel tenu : {len(v.tenues)}/{len(v.tenues) + len(v.disparues)} {quoi}(s) gelee(s) "
    ligne += f"toujours vivante(s), sur {v.comparees} comparee(s)."
    if v.neuves:
        ligne += (
            f"\n\U000025B6 {len(v.neuves)} {quoi}(s) vivante(s) HORS du gel — publiee(s), jamais "
            "refusee(s) : " + " · ".join(v.neuves) + "."
        )
    return ligne
