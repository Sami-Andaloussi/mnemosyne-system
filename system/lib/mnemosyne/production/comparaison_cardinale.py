"""AN EQUALITY OVER ZERO PAIRS IS TRUE BY CONSTRUCTION (candidate P7 from another project's harvest).

> *"the number of pairs is the only thing that says whether the comparison TOOK PLACE"* —
> `_divergences()`.

## THE MEASUREMENT, RE-TAKEN HERE (2026-09-08), NOT BORROWED

```
>>> index_problems('# empty gate', ())                                ->  ()
>>> index_problems('- [x] plan/arc-c.md — an arc\\n', ('arc-c.md',))  ->  ()
>>> both are IDENTICAL                                                ->  True
```

A gate that compares **nothing** and a gate that compares **and wins** render the same object, at
the same spot, with the same return code. The commit gate prints refusals; it never printed **how
many** it judged. *A green does not say how many.*

## The TWO cardinals, because there are TWO directions

:func:`~mnemosyne.production.plan_format.index_problems` asks two **opposite** questions, and its
own docstring insists on it: completeness ("is this arc named?") is GENEROUS, staleness ("does this
declared path exist?") is STRUCTURAL. Publishing a single number would hide one of them: a gate with
three arcs and zero declarations compares **3** on one side and **0** on the other, and it is that
zero that lies.

**BOTH CARDINALS ARE READ THROUGH THE JUDGE'S OWN ACCESSOR, never through a second rule**:
:func:`~mnemosyne.production.plan_format.declared_paths` is *"the JUDGE's question, not the
regex's"*, written in its own docstring. Counting declarations with a pattern of my own would give a
second opinion, hence two truths about what was compared.

## THIS MODULE REFUSES NOTHING THE JUDGE WOULD NOT HAVE REFUSED

It **wraps**, it does not duplicate: the problems it renders are exactly the judge's, untouched.
What it adds is the cardinal and one word — :attr:`Comparaison.vacante` — so the calling site can say
*"I compared zero pairs"* instead of saying *"everything is fine"*.

**Where it must live**: *"publish the compared cardinal INSIDE the gate itself, never beside it"*
(verdict D7 of the registry). A measurement placed beside the gate would be one more barrier that
nothing calls — the class closed three times on the day this verdict was written.

## What remains MOOT here, and that is verified rather than assumed

The original shape of `_divergences()` — comparing the **STATUS** of an item between **two views** —
does not find its second view here. Verified, rather than taken from the registry: the only
committed derived table in this repository is this repository's own end-of-session status block,
and :func:`~mnemosyne.production.bilan.rendre_l_etat` shows that it carries **measurements**
(`what | value | command`), never item statuses. There is therefore nothing to confront — and
`status_mismatch` appears nowhere in the code (2 occurrences, both inside the harvest's own
documents). *What rises is the cardinal; the other half awaits a population.*

PURE judge: no disk access. Prose in English (D117).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from .plan_format import PlanProblem, declared_paths, index_problems


@dataclass(frozen=True, slots=True)
class Comparaison:
    """The judge's verdict, AND how many pairs it was rendered over.

    ``arcs_compares`` is the number of arcs confronted against the gate (completeness sense);
    ``chemins_compares`` the number of paths the gate DECLARES and that were fetched from the
    disk (staleness sense). The two, never their sum: *an absence in one direction is never offset
    by a presence in the other*."""

    problemes: tuple[PlanProblem, ...]
    arcs_compares: int
    chemins_compares: int

    @property
    def paires(self) -> int:
        """The total of confrontations actually performed — the only number safe to publish alone."""
        return self.arcs_compares + self.chemins_compares

    @property
    def vacante(self) -> bool:
        """TRUE when nothing was compared. A vacant verdict is **not** a clean verdict:
        it is ``()`` obtained without ever having looked, and it reads exactly like a success."""
        return self.paires == 0

    @property
    def tient(self) -> bool:
        """The judge has nothing to say — **and** the comparison took place. Both, never just one."""
        return not self.problemes and not self.vacante


def comparer(
    porte: str,
    arcs: Sequence[str],
    *,
    folder_form: bool = True,
    juge: Callable[..., tuple[PlanProblem, ...]] = index_problems,
    lecteur_de_declarations: Callable[[str], tuple[str, ...]] = declared_paths,
) -> Comparaison:
    """The repository's judge, **wrapped** with its cardinal. The problems rendered are ITS OWN.

    ``juge`` and ``lecteur_de_declarations`` are injectable for witnesses only: their default IS
    the production pair, and a separate witness judges that default itself — *injecting everywhere
    would leave the real value untested*.

    ``folder_form=False`` (a plan with NO ``plan/`` folder at all) removes the staleness sense
    at the judge itself; the cardinal follows suit, otherwise it would announce confrontations that
    never took place — *a count that overshoots what the judge actually did is an exact lie*."""
    problemes = tuple(juge(porte, tuple(arcs), folder_form=folder_form))
    return Comparaison(
        problemes=problemes,
        arcs_compares=len(tuple(arcs)),
        chemins_compares=len(lecteur_de_declarations(porte)) if folder_form else 0,
    )


def rendre(c: Comparaison, *, ou: str = "") -> str:
    """The published line. It ALWAYS carries the cardinal, including when everything is fine.

    *The cardinal travels WITH the verdict, never beside it*: this is the only form a hurried
    reader cannot separate from the number that qualifies it."""
    lieu = f"{ou}: " if ou else ""
    if c.vacante:
        return (
            f"\U000026A0\U0000FE0F {lieu}VACANT COMPARISON — 0 pairs. No arc to confront, no path declared: "
            "this verdict is true by construction, it says NOTHING about the gate. A gate that "
            "compares nothing and a gate that compares and wins render the same object."
        )
    detail = f"{c.arcs_compares} arc(s) · {c.chemins_compares} declared path(s)"
    if not c.problemes:
        return f"{lieu}index verified over {c.paires} pair(s) ({detail}) — no discrepancy."
    causes = ", ".join(sorted({p.kind for p in c.problemes}))
    return (
        f"\U000026D4 {lieu}{len(c.problemes)} discrepancy(ies) on {c.paires} pair(s) compared "
        f"({detail}) — {causes}."
    )
