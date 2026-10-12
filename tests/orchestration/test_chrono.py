"""Witnesses for ``G7`` — the budget starts AFTER the turn is obtained.

The contract's five surfaces are covered here and in ``test_guetteur_commit.py`` (which carries the
**rc** and the **production value**, because that is where they live — this module has neither,
and pretending otherwise would be a witness that passes for the wrong reason).

Surface 1 (the judge) · surface 3 (the published text) · surface 5 (the passing case): here.
"""

from __future__ import annotations

from mnemosyne.production.chrono import (
    ATTENTE_DEPASSEE,
    BORNE_ABSURDE,
    CHRONO_INCOHERENT,
    SERVICE_DEPASSE,
    Chrono,
    attente_s,
    resume,
    sejour_s,
    service_s,
    verdict,
)


def _chrono(demande=0.0, tour=1.0, maintenant=2.0, plafond=10.0, budget=5.0) -> Chrono:
    return Chrono(
        demande=demande,
        tour_obtenu=tour,
        maintenant=maintenant,
        plafond_attente_s=plafond,
        budget_service_s=budget,
    )


# ── surface 1: THE JUDGE ──────────────────────────────────────────────────────────────────────


def test_le_service_se_compte_depuis_le_tour_obtenu_jamais_depuis_la_demande():
    """THE line of G7. 100 s of wait, 2 s of work, budget of 5 s: the work PASSES.

    The ``maintenant - demande`` mutant would return 102 s and refuse — that is, it would refuse
    fast work **because a peer was working before it**.
    """
    c = _chrono(demande=0.0, tour=100.0, maintenant=102.0, plafond=1000.0, budget=5.0)
    assert service_s(c) == 2.0
    assert attente_s(c) == 100.0
    assert not [r for r in verdict(c) if r.genre == SERVICE_DEPASSE]


def test_allonger_UNIQUEMENT_l_attente_ne_change_JAMAIS_le_verdict_de_service():
    """The property, not the case: the service verdict is INVARIANT under translation of the wait.

    This is the formulation that kills the mutant over a whole class of instants, not one triplet.
    """
    for attente in (0.0, 1.0, 10.0, 1_000.0, 86_400.0):
        c = _chrono(demande=0.0, tour=attente, maintenant=attente + 3.0, plafond=1e9, budget=5.0)
        assert service_s(c) == 3.0
        assert verdict(c) == (), f"attente={attente} contaminated the service verdict"


def test_le_service_seul_est_refuse_quand_c_est_le_TRAVAIL_qui_deborde():
    c = _chrono(demande=0.0, tour=1.0, maintenant=100.0, plafond=1000.0, budget=5.0)
    genres = [r.genre for r in verdict(c)]
    assert genres == [SERVICE_DEPASSE]
    (refus,) = verdict(c)
    assert refus.mesure_s == 99.0 and refus.borne_s == 5.0


def test_l_attente_a_son_PROPRE_plafond_et_le_franchir_n_accuse_pas_le_travail():
    c = _chrono(demande=0.0, tour=50.0, maintenant=51.0, plafond=10.0, budget=5.0)
    genres = [r.genre for r in verdict(c)]
    assert genres == [ATTENTE_DEPASSEE]


def test_les_DEUX_bornes_peuvent_etre_franchies_et_les_deux_sont_nommees():
    """A check placed first adds a cause, it never removes one: no early return here."""
    c = _chrono(demande=0.0, tour=50.0, maintenant=100.0, plafond=10.0, budget=5.0)
    assert [r.genre for r in verdict(c)] == [ATTENTE_DEPASSEE, SERVICE_DEPASSE]


def test_le_tour_JAMAIS_obtenu_n_a_pas_de_service_a_juger():
    """``None``, not ``0.0``: work never started is not instantaneous work."""
    c = Chrono(
        demande=0.0, tour_obtenu=None, maintenant=40.0, plafond_attente_s=10.0, budget_service_s=5.0
    )
    assert service_s(c) is None
    assert attente_s(c) == 40.0
    assert [r.genre for r in verdict(c)] == [ATTENTE_DEPASSEE]


def test_une_horloge_qui_RECULE_est_une_panne_d_instrument_pas_un_verdict():
    c = _chrono(demande=10.0, tour=5.0, maintenant=20.0)
    assert [r.genre for r in verdict(c)] == [CHRONO_INCOHERENT]


def test_une_borne_nulle_ou_negative_est_une_panne_d_instrument_et_sort_SEULE():
    """A budget of 0 would refuse everything: that is wiring to fix, never a judgement."""
    assert [r.genre for r in verdict(_chrono(budget=0.0))] == [BORNE_ABSURDE]
    assert [r.genre for r in verdict(_chrono(plafond=-1.0))] == [BORNE_ABSURDE]


def test_le_sejour_est_publie_mais_n_entre_dans_AUCUN_verdict():
    """Stay of 1 000 s, wait of 999 s, service of 1 s, budget of 5 s — and yet GREEN."""
    c = _chrono(demande=0.0, tour=999.0, maintenant=1000.0, plafond=1e9, budget=5.0)
    assert sejour_s(c) == 1000.0
    assert verdict(c) == ()


# ── surface 3: THE PUBLISHED TEXT ─────────────────────────────────────────────────────────────


def test_le_texte_separe_TOUJOURS_les_trois_chiffres_meme_au_vert():
    texte = resume(_chrono(), ())
    assert "wait" in texte and "service" in texte and "stay" in texte
    assert "never judged" in texte
    assert "OK" in texte


def test_le_texte_du_refus_de_service_dit_que_l_attente_n_y_entre_pas():
    """Neutralising this half of the sentence must turn the test red: it is the half that teaches the rule."""
    c = _chrono(demande=0.0, tour=1.0, maintenant=100.0, plafond=1000.0, budget=5.0)
    texte = resume(c, verdict(c))
    assert "the wait does not enter into it" in texte
    assert "99.00 s of work" in texte


def test_le_texte_du_refus_d_attente_dit_que_ce_n_est_PAS_le_travail():
    c = _chrono(demande=0.0, tour=50.0, maintenant=51.0, plafond=10.0, budget=5.0)
    texte = resume(c, verdict(c))
    assert "contention, never the work" in texte


def test_le_texte_d_une_panne_d_instrument_refuse_de_juger_le_travail():
    c = _chrono(demande=10.0, tour=5.0, maintenant=20.0)
    texte = resume(c, verdict(c))
    assert "instrument failure" in texte.lower()
    assert "not a verdict on the work" in texte


def test_le_texte_dit_que_le_service_n_a_pas_commence_quand_le_tour_est_perdu():
    c = Chrono(
        demande=0.0, tour_obtenu=None, maintenant=40.0, plafond_attente_s=10.0, budget_service_s=5.0
    )
    assert "service NOT STARTED" in resume(c, verdict(c))


# ── surface 5: THE PASSING CASE ───────────────────────────────────────────────────────────────


def test_LE_CAS_LEGITIME_NE_ROUGIT_PAS():
    """Without this witness, we would only be measuring its ability to refuse everything."""
    c = _chrono(demande=0.0, tour=0.4, maintenant=0.8, plafond=30.0, budget=300.0)
    assert verdict(c) == ()
    assert "OK" in resume(c, ())
