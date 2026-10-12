"""The Conseiller's store - milestones, threads, notebook, sandbox.

What these tests DEFEND:

1. **A bubble SEPARATE from the Intendant** - same ``tmp_path``, two different roots, never a
   leak from one store to the other.
2. **Nothing is ever erased** (invariant 2) - removing a milestone takes it out of READING, never
   out of the journal.
3. **The status is FREE, never a closed case** - no validation on it, unlike
   ``horizon``/``genre`` on the Intendant's side.
4. **Sorting is by deadline, never manual** - no `reordonner` here (design assumed, see conseiller.py).
5. **The notebook is append-only and bounded on read.**
6. **`executer_code` stays in its sandbox, respects a timeout, never crashes the calling turn.**
7. **`socle`/`lire_appel` refuse a tool outside the catalogue - the same guard as on the Intendant's side.**
"""

from __future__ import annotations

import time

import pytest

from mnemosyne.runtime import conseiller


@pytest.fixture(autouse=True)
def magasin_neuf(tmp_path, monkeypatch):
    monkeypatch.setenv("MNEMO_CONSEILLER_RACINE", str(tmp_path / "conseiller"))
    monkeypatch.setenv("MNEMO_INTENDANT_RACINE", str(tmp_path / "intendant"))
    return tmp_path


# -- Milestones ----------------------------------------------------------------------------------


def test_deposer_puis_lire_rend_le_jalon():
    jalon = conseiller.deposer_jalon("find an internship", echeance="2026-09-01", statut="in progress")
    relus = conseiller.lire_jalons()
    assert [j["id"] for j in relus] == [jalon["id"]]
    assert relus[0]["titre"] == "find an internship"
    assert relus[0]["statut"] == "in progress"
    assert relus[0]["etat"] == "vive"


def test_deposer_refuse_le_vide():
    with pytest.raises(ValueError):
        conseiller.deposer_jalon("   ")


def test_deposer_sans_echeance_ni_statut_reussit():
    """user can post a milestone without yet knowing either the date or where it stands."""
    jalon = conseiller.deposer_jalon("think about changing banks")
    assert jalon["echeance"] == ""
    assert jalon["statut"] == ""


def test_statut_est_libre_aucune_case_fermee():
    """Unlike `horizon` on the Intendant's side, no closed list: the status is plain text."""
    conseiller.deposer_jalon("x", statut="not found yet, still thinking about Berlin")
    assert conseiller.lire_jalons()[0]["statut"] == "not found yet, still thinking about Berlin"


def test_marquer_retiree_sort_de_la_lecture_mais_reste_au_journal():
    jalon = conseiller.deposer_jalon("a milestone to remove")
    conseiller.marquer_jalon(jalon["id"], "retiree")
    assert conseiller.lire_jalons() == []
    tous = conseiller.lire_jalons(tous=True)
    assert len(tous) == 1
    assert tous[0]["etat"] == "retiree"
    # the raw journal still carries BOTH lines - nothing vanished from the file
    lignes = conseiller._journal().read_text(encoding="utf-8").splitlines()
    assert len(lignes) == 2


def test_marquer_etat_inconnu_leve():
    jalon = conseiller.deposer_jalon("x")
    with pytest.raises(ValueError):
        conseiller.marquer_jalon(jalon["id"], "done")  # not a Conseiller state


def test_ranger_jalon_ecrit_une_ligne_de_plus_jamais_une_reecriture():
    jalon = conseiller.deposer_jalon("x", statut="first status")
    conseiller.ranger_jalon(jalon["id"], statut="status updated")
    releve = conseiller.lire_jalons()[0]
    assert releve["statut"] == "status updated"
    lignes = conseiller._journal().read_text(encoding="utf-8").splitlines()
    assert len(lignes) == 2  # deposit + change, never a rewrite


def test_ranger_jalon_n_ecrase_que_ce_qui_est_fourni():
    jalon = conseiller.deposer_jalon("original title", echeance="2026-09-01")
    conseiller.ranger_jalon(jalon["id"], statut="new status")
    releve = conseiller.lire_jalons()[0]
    assert releve["titre"] == "original title"
    assert releve["echeance"] == "2026-09-01"


def test_ranger_jalon_rejette_une_echeance_illisible():
    jalon = conseiller.deposer_jalon("x", echeance="2026-09-01")
    conseiller.ranger_jalon(jalon["id"], echeance="not a date")
    assert conseiller.lire_jalons()[0]["echeance"] == "2026-09-01"


# -- Sorting ---------------------------------------------------------------------------------


def test_trier_par_echeance_les_dates_d_abord_croissantes():
    conseiller.deposer_jalon("the latest", echeance="2026-12-01")
    conseiller.deposer_jalon("the earliest", echeance="2026-09-01")
    conseiller.deposer_jalon("no date")
    ordre = [j["titre"] for j in conseiller.trier_par_echeance()]
    assert ordre == ["the earliest", "the latest", "no date"]


def test_jalons_proches_ignore_ceux_sans_echeance():
    conseiller.deposer_jalon("with date", echeance="2026-09-01")
    conseiller.deposer_jalon("no date")
    proches = conseiller.jalons_proches()
    assert [j["titre"] for j in proches] == ["with date"]


# -- Resolution by title -----------------------------------------------------------------------


def test_jalons_par_titre_ignore_accents_et_casse():
    conseiller.deposer_jalon("Find An Internship")
    trouves = conseiller.jalons_par_titre("find an internship")
    assert len(trouves) == 1


def test_jalons_par_titre_absent_rend_liste_vide():
    assert conseiller.jalons_par_titre("does not exist") == []


def test_jalons_par_titre_ignore_un_jalon_retire():
    jalon = conseiller.deposer_jalon("to remove")
    conseiller.marquer_jalon(jalon["id"], "retiree")
    assert conseiller.jalons_par_titre("to remove") == []


def test_chercher_jalons_pese_le_titre_plus_que_le_statut():
    conseiller.deposer_jalon("internship in Paris", statut="nothing new")
    conseiller.deposer_jalon("something else", statut="still waiting on an internship")
    resultats = conseiller.chercher_jalons("internship")
    assert resultats[0]["titre"] == "internship in Paris"


# -- Threads - persisted, like the Intendant ------------------------------------------------


def test_fil_neuf_puis_ajouter_survit_a_une_relecture():
    fil = conseiller.fil_neuf(modele="test-modele")
    conseiller.fil_ajouter(fil["id"], "a question", "an answer", secondes=1.5)
    relu = conseiller.fil_lire(fil["id"])
    assert [t["texte"] for t in relu["tours"]] == ["a question", "an answer"]
    assert relu["tours"][1]["secondes"] == 1.5


def test_fil_dernier_rend_le_plus_recemment_touche():
    premier = conseiller.fil_neuf()
    time.sleep(0.01)
    second = conseiller.fil_neuf()
    assert conseiller.fil_dernier()["id"] == second["id"]
    conseiller.fil_ajouter(premier["id"], "q", "r")
    assert conseiller.fil_dernier()["id"] == premier["id"]


def test_le_conseiller_et_l_intendant_ne_partagent_aucun_fichier(tmp_path):
    """The cloisonnement guarantee itself: two roots, two distinct journals."""
    from mnemosyne.runtime import intendant

    conseiller.deposer_jalon("the Conseiller's milestone")
    intendant.deposer("the Intendant's note")
    assert conseiller.racine() != intendant.racine()
    assert [j["titre"] for j in conseiller.lire_jalons()] == ["the Conseiller's milestone"]
    assert [n["texte"] for n in intendant.lire()] == ["the Intendant's note"]


# -- The notebook -----------------------------------------------------------------------------


def test_noter_carnet_puis_lire_retrouve_la_note():
    conseiller.noter_carnet("user prefers reversible options")
    assert "user prefers reversible options" in conseiller.lire_carnet()


def test_noter_carnet_ignore_le_vide():
    assert conseiller.noter_carnet("   ") == ""
    assert conseiller.lire_carnet() == ""


def test_lire_carnet_absent_rend_une_chaine_vide():
    assert conseiller.lire_carnet() == ""


def test_noter_carnet_ajoute_jamais_ne_reecrit():
    conseiller.noter_carnet("first note")
    conseiller.noter_carnet("second note")
    carnet = conseiller.lire_carnet()
    assert "first note" in carnet
    assert "second note" in carnet


def test_lire_carnet_est_borne(monkeypatch):
    monkeypatch.setattr(conseiller, "_CARNET_CAP_LECTURE", 50)
    conseiller.noter_carnet("x" * 200)
    assert len(conseiller.lire_carnet()) <= 50


# -- The sandbox --------------------------------------------------------------------------------


def test_executer_code_rend_la_sortie_standard():
    resultat = conseiller.executer_code("print(2 + 2)")
    assert resultat["ok"] is True
    assert resultat["stdout"].strip() == "4"


def test_executer_code_rend_l_erreur_sans_planter():
    resultat = conseiller.executer_code("1 / 0")
    assert resultat["ok"] is False
    assert resultat["code_retour"] != 0
    assert "ZeroDivisionError" in resultat["stderr"]


def test_executer_code_refuse_le_vide():
    resultat = conseiller.executer_code("   ")
    assert resultat["ok"] is False
    assert "erreur" in resultat


def test_executer_code_coupe_apres_le_timeout(monkeypatch):
    monkeypatch.setattr(conseiller, "_TIMEOUT_CODE_S", 1)
    depart = time.monotonic()
    resultat = conseiller.executer_code("import time; time.sleep(5)")
    duree = time.monotonic() - depart
    assert resultat["ok"] is False
    assert duree < 4  # killed well before the script's 5 seconds
    assert "exceeded" in resultat["erreur"]


def test_executer_code_ecrit_dans_le_bac_pas_ailleurs():
    resultat = conseiller.executer_code(
        "from pathlib import Path; Path('preuve.txt').write_text('ici')"
    )
    assert resultat["ok"] is True
    assert (conseiller._bac() / "preuve.txt").is_file()


# -- The tool catalogue ---------------------------------------------------------------------


def test_lire_appel_refuse_un_outil_hors_catalogue():
    assert conseiller.lire_appel('{"outil": "supprimer_tout", "args": {}}') is None


def test_lire_appel_accepte_un_outil_connu():
    appel = conseiller.lire_appel('{"outil": "poser_jalon", "args": {"titre": "x"}}')
    assert appel == ("poser_jalon", {"titre": "x"})


def test_lire_appel_rend_none_sur_une_reponse_sans_json():
    assert conseiller.lire_appel("Hello, how can I help you?") is None


def test_socle_liste_tous_les_outils_du_catalogue():
    texte = conseiller.socle()
    for nom in conseiller.OUTILS:
        assert f"{nom}(" in texte


def test_socle_sans_portrait_ni_jalons_reste_court():
    texte = conseiller.socle()
    assert "What you know about their life" not in texte
    assert "milestones coming up" not in texte


def test_socle_avec_jalons_proches_les_liste():
    proches = [
        {"titre": "internship in Paris", "echeance": "2026-09-01T00:00:00Z", "statut": "in progress"}
    ]
    texte = conseiller.socle(jalons_proches=proches)
    assert "internship in Paris" in texte
    assert "in progress" in texte


def test_socle_interdit_le_recap_complet_apres_une_ecriture():
    """The same concise-acknowledgement rule applies here as in the Intendant surface."""
    assert "ONE SHORT SENTENCE" in conseiller.socle()
    assert "generic closing formula" in conseiller.socle()
