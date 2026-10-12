"""``make passes`` — the EDGE of the commit-gate pass census (G3 + G5).

The only module in this pair that touches the world: it reads `.githooks/pre-commit`, extracts the
python block, and **hands** the two sets to the two pure judges
(:mod:`~mnemosyne.production.recensement_des_passes` and
:mod:`~mnemosyne.production.barriere_gelee`). No judgement happens here.

## THE FREEZE IS READ BY IMPORTING THE OBJECT, NEVER BY `grep`

``PASSES_GELEES`` is **imported**. That is the property G5 promises, and it has a reason: a freeze
re-read by a text pattern disarms itself at the module's first reformat — *silently*, since a
pattern that no longer matches yields an empty set, hence "nothing to compare", hence a green.
:func:`~mnemosyne.production.barriere_gelee.VerdictGel.non_mesure` is the second belt: even an
emptied freeze can no longer read as a green.

## Three return codes, and they do NOT say the same thing

* ``rc 0`` — measurement taken, freeze held (passes outside the freeze are **published**, never
  refused).
* ``rc 1`` — the freeze is **broken**: a frozen pass has disappeared from the gate, or is no
  longer reachable there. This is a refusal.
* ``rc 2`` — the measurement is **impossible**: unreadable hook, heredoc not found or unparsable,
  zero refusal site recorded. *Two absences of measurement never compare equal to a green.*

**WHAT THIS COMMAND IS NOT**, and staying silent about it would manufacture exactly the
over-claiming `A2` fights: as long as the orchestrator has not wired it in, it is called by **no**
gate at all — so it is itself **level 1** (per the capability-obligation registry). Desired wiring, in
order of value: (1) a block inside `.githooks/pre-commit` — the gate then guards itself on every
commit, which is a downstream project's own shape; (2) failing that, `make passes` + a line in `tick`.

Read-only, brick-free, model-free, network-free. French prose (D117).
"""

from __future__ import annotations

import sys
from collections.abc import Iterable
from pathlib import Path

from ..production.barriere_gelee import message, verdict
from ..production.recensement_des_passes import (
    PASSES,
    PASSES_GELEES,
    PasseDeclaree,
    extraire_le_python,
    recenser,
    rendre,
)

#: ``parents[4]`` — and this cost has already been paid once in this repo: `parents[3]`
#: designates `system/`, and a census pointed at `system/.githooks` finds nothing, hence "no
#: passes", hence five refusals. `test_le_CHEMIN_de_production_designe_le_hook_REEL` judges this
#: exact value, separately from the witnesses that inject their own: *injecting everywhere leaves
#: the real value untested.*
RACINE = Path(__file__).resolve().parents[4]

#: The only automatic judge in this repo (measured: `git remote -v` → 0 lines, so `pre-push` never
#: fires; `/usr/bin/grep -cE "pytest|ruff|make test" .githooks/pre-commit` → 0).
CHEMIN_PORTE = Path(".githooks") / "pre-commit"


def main(
    argv: list[str] | None = None,
    *,
    racine: Path | None = None,
    declarees: tuple[PasseDeclaree, ...] | None = None,
    gelees: Iterable[str] | None = None,
) -> int:
    """``racine``, ``declarees`` and ``gelees`` are injectable FOR WITNESSES, never for
    production. Their default of ``None`` — rather than ``RACINE`` / ``PASSES`` as the default
    value — is deliberate: a default value is evaluated at import time and stops tracking the
    module.

    **THE TABLE AND THE FREEZE ARE INJECTED TOGETHER, AND THIS IS A WITNESS FIX.** The
    first version only took ``gelees``: the census kept searching for the five REAL markers in a
    fixture gate, and returned "5 frozen passes missing" on a perfectly healthy harness. *Two
    halves of the same population, injectable separately, diverge on the very first shot.*
    ``gelees`` remains distinct for exactly one reason: it must be able to be a strict SUBSET of
    ``declarees``, without which G5's FLOOR (a pass alive outside the freeze, published and never
    refused) is provable nowhere."""
    r = RACINE if racine is None else racine
    d = PASSES if declarees is None else declarees
    if gelees is not None:
        g = frozenset(gelees)
    elif declarees is None:
        g = PASSES_GELEES
    else:
        g = frozenset(p.identifiant for p in d)
    chemin = r / CHEMIN_PORTE
    try:
        source = chemin.read_text(encoding="utf-8")
    except OSError as erreur:
        print(f"UNREADABLE GATE: {chemin} — {erreur}. Nothing could be measured.")
        return 2
    python = extraire_le_python(source)
    if python is None:
        print(
            f"PYTHON BLOCK NOT FOUND in {chemin}: the `PYEOF` heredoc does not appear "
            "exactly once there. The gate changed shape — fix `_HEREDOC` in "
            "`production/recensement_des_passes.py` BEFORE trusting this silence."
        )
        return 2
    try:
        recensement = recenser(python, d)
    except SyntaxError as erreur:
        print(f"PYTHON BLOCK NOT PARSABLE ({erreur}). No census took place.")
        return 2

    print(rendre(recensement, g))
    v = verdict(recensement.vivantes, g)
    print(message(v))
    if recensement.sites == 0 or v.non_mesure:
        return 2  # not measured: distinct from a refusal, and distinct from a green
    return 1 if v.refuse else 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main(sys.argv[1:]))
