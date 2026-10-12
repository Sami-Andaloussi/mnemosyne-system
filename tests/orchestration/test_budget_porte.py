"""Witnesses for ``G12`` — a gate's budget is counted in CPU, never in WALL-CLOCK, and PER UNIT.

Surface 1 (the judge) · surface 3 (the published text) · surface 5 (the passing case): here.
Surfaces 2 (rc) and 4 (production value): ``test_guetteur_commit.py``, where they live.
"""

from __future__ import annotations

from mnemosyne.production.budget_porte import (
    MESURE_ABSURDE,
    POPULATION_VIDE,
    UNITE_DEPASSE,
    Unite,
    resume,
    unites_depassantes,
    verdict,
)

#: A realistic population, modeled on this repo's own paired measurement: under contention, the
#: wall-clock time inflates ×1.80 while CPU inflates ×1.28. Here, `lente_mais_pas_chere` is
#: exactly the case a wall-clock budget would wrongly refuse.
POPULATION = (
    Unite(nom="plans", cpu_s=0.45, mural_s=0.50),
    Unite(nom="lente_mais_pas_chere", cpu_s=0.77, mural_s=9.90),
    Unite(nom="bilan", cpu_s=0.10, mural_s=0.11),
)


# ── surface 1: THE JUDGE ─────────────────────────────────────────────────────────────────────


def test_le_MURAL_ne_juge_JAMAIS_meme_quand_il_explose():
    """ THE line of G12. 9.90 s wall-clock for 0.77 s CPU under a 1 s budget: it PASSES.

 The ``u.mural_s > budget`` mutant would refuse — i.e. would refuse cheap work just because
 the machine was under load: a sibling project's defect (207-322 s refuse, 119-158 s pass).
 """
    assert verdict(POPULATION, 1.0) == ()


def test_le_budget_est_PAR_UNITE_jamais_le_TOTAL():
    """Total = 1.32 s CPU for a 1 s budget: a total budget would refuse. No single unit exceeds it."""
    total = sum(u.cpu_s for u in POPULATION)
    assert total > 1.0, (
        "the fixture must have a total ABOVE the budget, otherwise it tests nothing"
    )
    assert verdict(POPULATION, 1.0) == ()


def test_un_budget_total_resterait_faux_quand_la_POPULATION_grandit():
    """The property that makes "per unit" superior: duplicating the population changes nothing.

    This is what a total budget cannot hold — and why it keeps getting loosened until it no
    longer bounds anything.
    """
    for facteur in (1, 3, 10, 50):
        assert verdict(POPULATION * facteur, 1.0) == (), (
            f"x{facteur} made the verdict depend on the size"
        )


def test_l_unite_qui_depasse_est_NOMMEE_et_elle_seule():
    refus = verdict(POPULATION, 0.5)
    assert [r.genre for r in refus] == [UNITE_DEPASSE]
    assert unites_depassantes(refus) == frozenset({"lente_mais_pas_chere"})


def test_le_gel_porte_sur_l_ENSEMBLE_car_un_ECHANGE_laisse_le_COMPTE_identique():
    """Two units swapping costs: same refusal count, DIFFERENT set."""
    a = (Unite("alpha", 9.0, 9.0), Unite("beta", 0.1, 0.1))
    b = (Unite("alpha", 0.1, 0.1), Unite("beta", 9.0, 9.0))
    assert len(verdict(a, 1.0)) == len(verdict(b, 1.0)) == 1
    assert unites_depassantes(verdict(a, 1.0)) != unites_depassantes(verdict(b, 1.0))


def test_une_POPULATION_VIDE_n_est_JAMAIS_un_vert():
    refus = verdict((), 1.0)
    assert [r.genre for r in refus] == [POPULATION_VIDE]
    assert refus != ()


def test_un_budget_nul_ou_negatif_est_une_panne_d_instrument():
    assert [r.genre for r in verdict(POPULATION, 0.0)] == [MESURE_ABSURDE]
    assert [r.genre for r in verdict(POPULATION, -1.0)] == [MESURE_ABSURDE]


def test_un_compteur_CPU_negatif_est_une_panne_pas_un_vert():
    """``getrusage`` subtracting in the wrong direction: the result is negative, hence "under
    budget"."""
    mauvais = (Unite("geste", cpu_s=-0.5, mural_s=0.5),)
    assert [r.genre for r in verdict(mauvais, 1.0)] == [MESURE_ABSURDE]


def test_la_borne_est_STRICTE_une_unite_EXACTEMENT_au_budget_passe():
    """A rule expressed as an inequality only bounds one side: we pin down which."""
    assert verdict((Unite("pile", 1.0, 1.0),), 1.0) == ()
    assert [r.genre for r in verdict((Unite("juste_au_dessus", 1.001, 1.0),), 1.0)] == [
        UNITE_DEPASSE
    ]


# ── surface 3: THE PUBLISHED TEXT ────────────────────────────────────────────────────────────


def test_le_texte_publie_les_DEUX_temps_pour_que_l_ecart_soit_VU():
    texte = resume(POPULATION, (), 1.0)
    assert "cpu 0.77 s / wall 9.90 s" in texte
    assert "PER UNIT" in texte and "never the wall-clock" in texte


def test_le_texte_du_refus_rappelle_que_le_MURAL_n_a_pas_juge():
    """Neutralizing this half must turn the test red: it is what stops the next hand from going
    back to wall-clock time."""
    texte = resume(POPULATION, verdict(POPULATION, 0.5), 0.5)
    assert "lente_mais_pas_chere cost 0.77 s CPU" in texte
    assert "WALL-CLOCK time did not judge" in texte


def test_le_texte_d_une_population_vide_DIT_qu_elle_n_a_rien_juge():
    texte = resume((), verdict((), 1.0), 1.0)
    assert "INSTRUMENT FAILURE" in texte
    assert "would turn GREEN without having looked at anything" in texte


def test_le_texte_d_une_mesure_absurde_nomme_l_unite_fautive():
    mauvais = (Unite("geste", cpu_s=-0.5, mural_s=0.5),)
    texte = resume(mauvais, verdict(mauvais, 1.0), 1.0)
    assert "INSTRUMENT FAILURE" in texte and "geste" in texte


# ── surface 5: THE PASSING CASE ──────────────────────────────────────────────────────────────


def test_LE_CAS_LEGITIME_NE_ROUGIT_PAS():
    """The real cost measured on this repo's own gate (0.33 to 0.77 s CPU) under the production
    budget."""
    reelles = (Unite("porte_pre_commit", cpu_s=0.77, mural_s=1.32),)
    assert verdict(reelles, 10.0) == ()
    assert "OK" in resume(reelles, (), 10.0)
