"""A4  -  NO CEILING WITHOUT "WHAT BREAKS WITHOUT IT" - the ratchet on the code's named bounds.

THE D165 TEST, CARVED ON OPERATOR'S OBJECTION: *a ceiling on a generated output does not bound, it
DRIVES.* The proof is on file, measured against Acme Research's 400-line ceiling: the distribution
of files decays normally up to 26 (300-349), then **climbs back up to 61 files stuck at the ceiling,
15 of them exactly at 400/400**. A ceiling does not just draw content toward it, it **fragments by
arithmetic instead of by meaning**.

THIS RATCHET DOES NOT JUDGE THE VALUE OF THE BOUNDS - IT JUDGES THEIR SILENCE. Census as of 2026-08-09:
**54 named bounds** in `system/lib`, of which **9 write NOTHING**: neither what they bound, nor what
breaks without them. A silent bound is indefensible by construction - nobody can tell whether
it bounds or whether it drives, and that very doubt is what this ratchet forbids from growing.

WHAT IT DOES NOT JUDGE, AND THIS MUST BE READ BEFORE TRUSTING IT. It checks that an explanation EXISTS,
never that it truly names what breaks - *a name is not a test*. Measured in practice while
writing this file: `runner_mlx._DEFAULT_MAX_TOKENS = 512` was counted as "explained"
even though the six comment lines above it discuss a **different** decision (the retirement of a
default model branch). The proxy OVER-counts: the real reading stays human, and this ratchet
only keeps total silence from growing.
"""

from __future__ import annotations

import re
from pathlib import Path

_RACINE = Path(__file__).resolve().parents[2]
_LIB = _RACINE / "system" / "lib"

#: Constants that DECLARE themselves as bounds by their name.
_BORNE = re.compile(
    r"^([A-Z_]*(?:MAX|MIN|LIMIT|CAP|PLAFOND|BORNE|SEUIL|TAILLE|FLOOR|BUDGET|QUOTA|TOP_?K)[A-Z_]*)"
    r"\s*[:=]\s*[0-9_.]+"
)

#: THE FROZEN DEBT, AND IT IS A RATCHET THAT CAN ONLY DECREASE (same shape as A2).
#: Measured 2026-08-09: 9 silent bounds out of 54. What breaks without this freeze: nothing would stop
#: the 10th silent bound, and "no ceiling without what breaks without it" would stay a mere intention.
#: This number is never RAISED to let one more bound in - the line gets written instead.
BORNES_MUETTES_GELEES = 9


def _muettes() -> list[str]:
    """Bounds without a single line of explanation - neither at end of line, nor just above."""
    trouvees: list[str] = []
    for source in sorted(_LIB.rglob("*.py")):
        lignes = source.read_text(encoding="utf-8").splitlines()
        for i, ligne in enumerate(lignes):
            trouve = _BORNE.match(ligne)
            if not trouve:
                continue
            if "#" in ligne.split("=", 1)[-1]:
                continue
            if i and lignes[i - 1].lstrip().startswith("#"):
                continue
            trouvees.append(f"{source.relative_to(_RACINE)}:{i + 1}:{trouve.group(1)}")
    return trouvees


def test_le_recensement_TROUVE_des_bornes_sinon_il_ne_mesure_rien() -> None:
    """THE INNOCENT CASE, AND IT IS INDISPENSABLE HERE. A broken pattern would yield ZERO silent
    bounds, hence a GREEN - the ratchet would pass having stopped being exercised. *A measurement can
    stop being taken without turning red.* Hence the requirement that the TOTAL population stay substantial."""
    total = sum(
        1
        for source in _LIB.rglob("*.py")
        for ligne in source.read_text(encoding="utf-8").splitlines()
        if _BORNE.match(ligne)
    )
    assert total >= 40, f"only {total} bounds seen - the pattern no longer bites, it measures nothing"


def test_aucune_borne_MUETTE_de_plus_que_la_dette_gelee() -> None:
    """A silent bound is indefensible: nobody can tell whether it bounds or whether it DRIVES."""
    muettes = _muettes()
    assert len(muettes) <= BORNES_MUETTES_GELEES, (
        f"{len(muettes)} silent bounds for a debt frozen at {BORNES_MUETTES_GELEES}. "
        f"New ones: {muettes[-3:]}. Write what the bound prevents, and above all WHAT BREAKS WITHOUT "
        f"IT (D165) - the freeze is never raised to let one more bound in."
    )


def test_la_dette_qui_BAISSE_exige_qu_on_RESSERRE_le_gel() -> None:
    """*A ratchet the corpus floats above is just waiting to be destroyed*: with slack in it, a
    new silent bound gets in for free. The message names the number to write."""
    muettes = _muettes()
    assert len(muettes) >= BORNES_MUETTES_GELEES, (
        f"the debt has DROPPED: {len(muettes)} silent bounds for a freeze at "
        f"{BORNES_MUETTES_GELEES} - write BORNES_MUETTES_GELEES = {len(muettes)} in this file."
    )


def test_les_bornes_de_SORTIE_des_deux_runners_REFUSENT_au_lieu_de_couper() -> None:
    """THE D165 CLASS FAULT THIS EFFORT CLOSED, AND IT LIVED ON BOTH PATHS.

    A ceiling on what a model WRITES is precisely the shape D165 refuses. You cannot
    generate without a bound (an endless generation blocks the machine) - the legitimate shape is
    therefore that it **says so** when it bites, the way the ENTRY ceiling (D136) refuses instead of
    cutting. This witness checks that both refusal functions EXIST and are REACHED from the real
    path: *the barrier that nothing calls* guards nothing.
    """
    import inspect

    from mnemosyne.runtime import runner_anthropic, runner_mlx

    assert "refuser_si_tronque(" in inspect.getsource(runner_anthropic.AnthropicBackend._create)
    assert "refuser_si_tronque(" in inspect.getsource(runner_mlx._MlxBackend._run)
