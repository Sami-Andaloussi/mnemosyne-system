"""The Conseiller's decision models - calculation, never improvisation.

What these tests DEFEND:

1. **The arithmetic is exact, not approximate.** Every mathematical model is checked against
   a result computed BY HAND, not against "a plausible-looking number".
2. **Decision under uncertainty retrieves the CLASSIC verdicts from the textbook** (the umbrella
   problem) - if this test falls, this is no longer decision theory, it is something else.
3. **A malformed entry (from a local model that goes off the rails) never crashes the
   calculation** - it is ignored or counted as zero, never an exception that bubbles up to the
   conversation.
4. **The structured frameworks are FIXED**: the same steps on every call, no argument changes
   them - that is precisely what makes them "hardcoded" rather than invented by a model.
"""

from __future__ import annotations

from mnemosyne.runtime import decision


# -- A. The weighted matrix -----------------------------------------------------------------------


def test_matrice_ponderee_calcule_le_bon_score():
    resultat = decision.matrice_ponderee(
        options=["Offer A", "Offer B"],
        criteres=[{"nom": "salary", "poids": 3}, {"nom": "fulfillment", "poids": 5}],
        notes={
            "Offer A": {"salary": 8, "fulfillment": 6},
            "Offer B": {"salary": 6, "fulfillment": 9},
        },
    )
    # normalized weights: salary 3/8 = 0.375, fulfillment 5/8 = 0.625
    # A: 8*0.375 + 6*0.625 = 3.0 + 3.75 = 6.75
    # B: 6*0.375 + 9*0.625 = 2.25 + 5.625 = 7.875
    scores = {o["option"]: o["score"] for o in resultat["options"]}
    assert scores["Offer A"] == 6.75
    assert scores["Offer B"] == 7.875
    assert resultat["gagnant"] == "Offer B"


def test_matrice_ponderee_normalise_des_poids_qui_ne_somment_pas_a_un():
    """Relative weights are normalized; they are not a pre-calibrated budget."""
    a = decision.matrice_ponderee(["X"], [{"nom": "c", "poids": 10}], {"X": {"c": 7}})
    b = decision.matrice_ponderee(["X"], [{"nom": "c", "poids": 1}], {"X": {"c": 7}})
    assert a["options"][0]["score"] == b["options"][0]["score"] == 7.0


def test_matrice_ponderee_note_absente_compte_pour_zero_sans_planter():
    resultat = decision.matrice_ponderee(
        options=["Only option"],
        criteres=[{"nom": "a", "poids": 1}, {"nom": "b", "poids": 1}],
        notes={"Only option": {"a": 10}},  # "b" absent
    )
    assert resultat["options"][0]["score"] == 5.0  # (10 + 0) / 2


def test_matrice_ponderee_sans_options_ni_criteres_rend_une_erreur_pas_une_exception():
    resultat = decision.matrice_ponderee(options=[], criteres=[], notes={})
    assert resultat["options"] == []
    assert resultat["erreur"]


def test_matrice_ponderee_ignore_un_critere_au_poids_invalide():
    resultat = decision.matrice_ponderee(
        options=["X"],
        criteres=[{"nom": "good", "poids": 1}, {"nom": "broken", "poids": "not a number"}],
        notes={"X": {"good": 4}},
    )
    assert resultat["options"][0]["score"] == 4.0
    assert len(resultat["options"][0]["detail"]) == 1


# -- B. Decision under uncertainty -----------------------------------------------------------------


def test_decision_incertitude_retrouve_le_probleme_classique_du_parapluie():
    """Manual decision-theory case: umbrella or not, rain or not.

    Umbrella: Rain=20, NoRain=15 (dry but the object is a bit cumbersome)
    NoUmbrella: Rain=0, NoRain=25

    Expected results (by hand):
    - maximin (cautious): Umbrella (15 > 0)
    - maximax (optimistic): NoUmbrella (25 > 20)
    - laplace (equiprobable): Umbrella (17.5 > 12.5)
    - minimax regret: Umbrella (max regret 10 < max regret 20)
    """
    resultat = decision.decision_incertitude(
        options=["Umbrella", "NoUmbrella"],
        scenarios=[{"nom": "Rain"}, {"nom": "NoRain"}],
        valeurs={
            "Umbrella": {"Rain": 20, "NoRain": 15},
            "NoUmbrella": {"Rain": 0, "NoRain": 25},
        },
    )
    par_option = {o["option"]: o for o in resultat["options"]}
    assert par_option["Umbrella"]["maximin_pessimiste"] == 15
    assert par_option["NoUmbrella"]["maximin_pessimiste"] == 0
    assert par_option["Umbrella"]["maximax_optimiste"] == 20
    assert par_option["NoUmbrella"]["maximax_optimiste"] == 25
    assert par_option["Umbrella"]["laplace_equiprobable"] == 17.5
    assert par_option["NoUmbrella"]["laplace_equiprobable"] == 12.5
    assert par_option["Umbrella"]["regret_maximal"] == 10
    assert par_option["NoUmbrella"]["regret_maximal"] == 20

    assert resultat["verdicts"]["prudent_maximin"] == "Umbrella"
    assert resultat["verdicts"]["optimiste_maximax"] == "NoUmbrella"
    assert resultat["verdicts"]["indifference_laplace"] == "Umbrella"
    assert resultat["verdicts"]["moins_de_regret"] == "Umbrella"
    assert resultat["accord"] is False  # the criteria diverge, and that IS the information


def test_decision_incertitude_calcule_l_esperance_si_toutes_les_probabilites_sont_donnees():
    resultat = decision.decision_incertitude(
        options=["A"],
        scenarios=[{"nom": "s1", "probabilite": 0.5}, {"nom": "s2", "probabilite": 0.5}],
        valeurs={"A": {"s1": 10, "s2": 20}},
    )
    assert resultat["options"][0]["esperance"] == 15.0
    assert resultat["verdicts"]["esperance_maximale"] == "A"


def test_decision_incertitude_omet_l_esperance_si_une_seule_probabilite_manque():
    """An expectation computed on half-invented probabilities is worth less than its absence."""
    resultat = decision.decision_incertitude(
        options=["A"],
        scenarios=[{"nom": "s1", "probabilite": 0.5}, {"nom": "s2"}],  # s2 without a probability
        valeurs={"A": {"s1": 10, "s2": 20}},
    )
    assert "esperance" not in resultat["options"][0]
    assert "esperance_maximale" not in resultat["verdicts"]


def test_decision_incertitude_case_non_chiffree_compte_pour_zero():
    resultat = decision.decision_incertitude(
        options=["A", "B"],
        scenarios=[{"nom": "s1"}],
        valeurs={"A": {"s1": 5}},  # B has nothing for s1
    )
    par_option = {o["option"]: o for o in resultat["options"]}
    assert par_option["B"]["maximin_pessimiste"] == 0


def test_decision_incertitude_sans_options_rend_une_erreur():
    resultat = decision.decision_incertitude(options=[], scenarios=[{"nom": "s"}], valeurs={})
    assert resultat["options"] == []
    assert resultat["erreur"]


# -- C-E. The structured frameworks - fixed, sourced ------------------------------------------------


def test_cadre_wrap_a_ses_quatre_lettres_dans_l_ordre():
    resultat = decision.cadre_wrap()
    assert [e["lettre"] for e in resultat["etapes"]] == ["W", "R", "A", "P"]
    assert resultat["source"]
    # every step carries at least one question - never a title empty of content
    assert all(e["questions"] for e in resultat["etapes"])


def test_cadre_wrap_est_identique_a_chaque_appel():
    """Fixed = deterministic. A framework that varied from one call to the next would no longer be
    "hardcoded", it would be a model improvising under cover of a serious-sounding name."""
    assert decision.cadre_wrap() == decision.cadre_wrap()


def test_cadre_premortem_a_ses_trois_etapes_sourcees():
    resultat = decision.cadre_premortem()
    assert [e["titre"] for e in resultat["etapes"]] == ["List", "Spot", "Act"]
    assert "Klein" in resultat["source"]


def test_cadre_10_10_10_a_ses_trois_horizons():
    resultat = decision.cadre_10_10_10()
    assert [q["horizon"] for q in resultat["questions"]] == ["10 minutes", "10 months", "10 years"]


# -- F. The Eisenhower matrix -----------------------------------------------------------------------


def test_matrice_eisenhower_trie_dans_les_quatre_quadrants():
    resultat = decision.matrice_eisenhower(
        [
            {"nom": "fire", "urgent": True, "important": True},
            {"nom": "exercise", "urgent": False, "important": True},
            {"nom": "notification", "urgent": True, "important": False},
            {"nom": "scrolling", "urgent": False, "important": False},
        ]
    )
    quadrants = resultat["quadrants"]
    assert [i["nom"] for i in quadrants["Q1 — Do now"]] == ["fire"]
    assert [i["nom"] for i in quadrants["Q2 — Plan"]] == ["exercise"]
    assert [i["nom"] for i in quadrants["Q3 — Delegate or shorten"]] == ["notification"]
    assert [i["nom"] for i in quadrants["Q4 — Eliminate or defer"]] == ["scrolling"]


def test_matrice_eisenhower_ignore_un_item_sans_nom():
    resultat = decision.matrice_eisenhower([{"urgent": True, "important": True}])
    assert all(items == [] for items in resultat["quadrants"].values())


def test_matrice_eisenhower_sur_liste_vide_ne_plante_pas():
    resultat = decision.matrice_eisenhower([])
    assert all(items == [] for items in resultat["quadrants"].values())
    resultat_none = decision.matrice_eisenhower(None)
    assert all(items == [] for items in resultat_none["quadrants"].values())
