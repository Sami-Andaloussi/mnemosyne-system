"""D3 -- the production floor, proven on the REAL curve and on the three opposed gestures.

**CORRECTION (D75 audit, 2026-08-15)**: the first version of this file froze a curve with a
denominator NOT bounded to the project (July 15 read 13.7%, a measurement artifact -- see
`production/plancher.py`). The values below are the CORRECTED curve (bounded denominator),
identical to the one published in the project's internal lifecycle notes, to one decimal place.
"""

from __future__ import annotations

from mnemosyne.production.plan_derive import Jour
from mnemosyne.production.plancher import (
    N_PLANCHER,
    X_PLANCHER,
    Plancher,
    decision,
    lire_plancher,
)

#: The real curve (PAR_LIGNE, denominator BOUNDED to the project, projects/.git, July 15-29,
#: 2026), reproduced live via `mnemosyne.runtime.plancher_run.etat_plancher` -- never copied from
#: a document. Frozen here as percentages so this file does not depend on git history at the
#: moment the suite runs (the same choice D1's own witnesses make about their own tipping point).
_COURBE_REELLE = (
    Jour("2026-07-15", produit=39909, total=49980),  # 79.8% -- initial import, HEALTHY once bounded
    Jour("2026-07-20", produit=94983, total=115044),  # 82.6%
    Jour("2026-07-21", produit=11005, total=34674),  # 31.7% -- the tipping point, still above 30
    Jour("2026-07-22", produit=2673, total=46240),  # 5.8% -- the day the repo was waiting for
    Jour("2026-07-23", produit=2220, total=11082),  # 20.0%
    Jour("2026-07-24", produit=0, total=1250),  # 0.0%
    Jour("2026-07-25", produit=258, total=6312),  # 4.1%
    Jour("2026-07-26", produit=0, total=20056),  # 0.0%
    Jour("2026-07-27", produit=63, total=11020),  # 0.6%
    Jour("2026-07-28", produit=524, total=14548),  # 3.6%
    Jour("2026-07-29", produit=0, total=73),  # 0.0%
)


def _jusqua(date: str) -> tuple[Jour, ...]:
    """Chronological prefix of the real curve, up to and INCLUDING ``date``."""
    idx = [j.date for j in _COURBE_REELLE].index(date)
    return _COURBE_REELLE[: idx + 1]


def test_les_constantes_publiees_sont_celles_derivees_de_la_courbe() -> None:
    assert X_PLANCHER == 30.0
    assert N_PLANCHER == 1


# --------------------------------------------------------------------------------------------
# (c1) THE THREE GESTURES OF *Done when* -- ouvrir_blindage refused, ouvrir_produit AND fermer
# accepted, in the SAME state. A gate that refuses everything passes the first shot alone.
# --------------------------------------------------------------------------------------------


def test_OUVRIR_BLINDAGE_est_REFUSE_sous_le_plancher_franchi() -> None:
    """July 22, on the corrected real curve: first day below 30% -- crossed (N=1)."""
    plancher = lire_plancher(_jusqua("2026-07-22"))
    assert plancher.franchi is True
    assert decision("ouvrir_blindage", plancher) is False


def test_FERMER_reste_ACCEPTE_dans_le_MEME_etat_franchi() -> None:
    """The exact same state as the test above (July 22, floor crossed) -- fermer passes."""
    plancher = lire_plancher(_jusqua("2026-07-22"))
    assert plancher.franchi is True  # same state, not assumed -- re-checked explicitly
    assert decision("fermer", plancher) is True


def test_OUVRIR_PRODUIT_reste_ACCEPTE_dans_le_MEME_etat_franchi() -> None:
    """Third shot, same state: opening a PRODUCT workstream is never what the floor wants to
    prevent -- it is exactly what should be encouraged when the product share is low."""
    plancher = lire_plancher(_jusqua("2026-07-22"))
    assert plancher.franchi is True
    assert decision("ouvrir_produit", plancher) is True


def test_FERMER_et_OUVRIR_PRODUIT_restent_toujours_accepte_meme_construit_a_la_main_franchi() -> None:
    """Independent of any real curve: neither fermer nor ouvrir_produit look at the state."""
    plancher_franchi = Plancher(franchi=True, x=30.0, n=1, recentes=(0.0,))
    assert decision("fermer", plancher_franchi) is True
    assert decision("ouvrir_produit", plancher_franchi) is True


def test_geste_inconnu_leve_plutot_que_de_deviner() -> None:
    plancher = Plancher(franchi=False, x=30.0, n=1, recentes=(50.0,))
    try:
        decision("ouvrir", plancher)  # type: ignore[arg-type]  # old 2-way gesture, retired
    except ValueError as exc:
        assert "ouvrir" in str(exc)
    else:
        raise AssertionError("a gesture outside {ouvrir_blindage, ouvrir_produit, fermer} must raise")


# --------------------------------------------------------------------------------------------
# OUVRIR_BLINDAGE stays accepted BEFORE the tipping point -- the positive pole; without it,
# "refuses everything" would pass.
# --------------------------------------------------------------------------------------------


def test_OUVRIR_BLINDAGE_reste_ACCEPTE_avant_la_bascule() -> None:
    """July 21 (31.7%): still above the floor -- opening a hardening workstream is legitimate."""
    plancher = lire_plancher(_jusqua("2026-07-21"))
    assert plancher.franchi is False
    assert decision("ouvrir_blindage", plancher) is True


# --------------------------------------------------------------------------------------------
# THE EXACT BOUNDARY -- the day the repo had been waiting for, published BEFORE this module
# existed.
# --------------------------------------------------------------------------------------------


def test_le_21_juillet_ne_franchit_pas_encore_premier_jour_de_l_audit_encore_ambigu() -> None:
    plancher = lire_plancher(_jusqua("2026-07-21"))
    assert plancher.franchi is False  # 31.7% > 30% -- the floor leaves one day of margin


def test_le_22_juillet_est_le_premier_jour_franchi_exactement_celui_attendu() -> None:
    """The project's internal planning notes (D5) and its internal lifecycle notes (section 6)
    both say, BEFORE this module ever existed, that the signal should have screamed on July 22."""
    avant = lire_plancher(_jusqua("2026-07-21"))
    apres = lire_plancher(_jusqua("2026-07-22"))
    assert avant.franchi is False
    assert apres.franchi is True


def test_le_plancher_se_referme_PAS_tout_seul_apres_avoir_ete_franchi() -> None:
    """July 29 stays below 30% (0.0%) -- the floor, once crossed on the 22nd, stays crossed
    through the end of the measured window: no day in the period climbs back above 20% after."""
    plancher = lire_plancher(_COURBE_REELLE)  # the full series, through July 29
    assert plancher.franchi is True


# --------------------------------------------------------------------------------------------
# N=1 IS LEGITIMATE ONCE THE DENOMINATOR IS BOUNDED -- no more false positives across the whole
# curve.
# --------------------------------------------------------------------------------------------


def test_N_EGAL_1_NE_FAUT_PLUS_POSITIF_sur_le_jour_de_l_import_initial_une_fois_borne() -> None:
    """July 15, N=1, CORRECTED curve: 79.8% >= 30% -- no more false positive. It was the
    unbounded denominator (see plancher.py) that produced the false positive, not N=1 itself."""
    plancher = lire_plancher(_jusqua("2026-07-15"), x=X_PLANCHER, n=1)
    assert plancher.franchi is False


# --------------------------------------------------------------------------------------------
# ABSENCE OF DATA != CROSSED -- a series too short must never read as a refusal.
# --------------------------------------------------------------------------------------------


def test_moins_de_N_jours_mesures_n_est_JAMAIS_franchi() -> None:
    # N=1 is now the default: this test keeps N=2 explicit to prove the general case
    # ("fewer than N days"), not just the current default.
    un_seul_jour_tres_bas = (Jour("2026-01-01", produit=0, total=100),)  # 0.0%, but ALONE
    plancher = lire_plancher(un_seul_jour_tres_bas, x=30.0, n=2)
    assert plancher.franchi is False
    assert plancher.recentes == (0.0,)


def test_serie_vide_n_est_pas_franchi() -> None:
    plancher = lire_plancher((), x=30.0, n=2)
    assert plancher.franchi is False
    assert plancher.recentes == ()


def test_n_sous_1_leve() -> None:
    try:
        lire_plancher(_COURBE_REELLE, n=0)
    except ValueError:
        pass
    else:
        raise AssertionError("n=0 judges nothing -- must raise, never return an always-true floor")


# --------------------------------------------------------------------------------------------
# BEHAVIOR AT N=2 STAYS CORRECT (the default changed, the mechanism at any N did not).
# --------------------------------------------------------------------------------------------


def test_a_N_egal_2_il_faut_deux_jours_consecutifs_pas_un_seul() -> None:
    """Even on the corrected curve, a larger N still requires several consecutive days: July 22
    alone (1 low day) is not enough for N=2, you have to wait for the 23rd."""
    apres_22 = lire_plancher(_jusqua("2026-07-22"), x=30.0, n=2)
    apres_23 = lire_plancher(_jusqua("2026-07-23"), x=30.0, n=2)
    assert apres_22.franchi is False  # one low day (22) after a high day (21) -- N=2 not reached
    assert apres_23.franchi is True
