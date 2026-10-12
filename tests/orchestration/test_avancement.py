"""Witnesses for `P3` — the weighted ladle (`production/avancement.py` + `runtime/avancement_run.py`).

These witnesses cover FIVE surfaces, because a module in this repository has already survived
**19 green witnesses** with 6 live mutants: all 19 questioned the judge and the boundary, none read
the line that turns a verdict into a refusal, nor the published TEXT, nor the module's REAL values.

1. the JUDGE — :func:`poids_declare`, :func:`louche` (pure data);
2. the RC — the ``return 0`` / ``return 2`` line of ``main()``;
3. the published TEXT — :func:`rendre`, sentence by sentence, including the ``sans poids`` admission;
4. the PRODUCTION VALUE — the module's real constants, never injected;
5. the PASSING CASE — an explicit assertion that a legitimate ladle does NOT refuse.
"""

from __future__ import annotations

import pytest

from mnemosyne.production import avancement
from mnemosyne.production.avancement import (
    FAITS_PAR_DEFAUT,
    HORS_POPULATION_PAR_DEFAUT,
    Item,
    SansPopulation,
    louche,
    poids_declare,
    rendre,
)
from mnemosyne.runtime import avancement_run

# ─────────────────────────────── 1. THE JUDGE ───────────────────────────────


def test_un_segment_unique_nombre_plus_unite_rend_son_nombre() -> None:
    assert poids_declare("~27 lots") == 27
    assert poids_declare("1 mesure") == 1
    assert poids_declare("10 000 items") == 10000


def test_des_segments_de_MEME_unite_s_additionnent() -> None:
    assert poids_declare("3 fichiers · 2 fichiers") == 5


def test_des_unites_MELANGEES_ne_rendent_AUCUN_poids() -> None:
    # 4 + 400 = 404 would be a number decided entirely by "lines".
    assert poids_declare("4 documents · ~400 lignes") is None
    assert poids_declare("1 champ · 1 clause · 1 audit") is None


def test_un_segment_MUET_retire_le_poids_ENTIER_au_lieu_d_etre_ignore() -> None:
    # The real counter-example: reading "5" here would yield ONE THIRD of what the author wrote,
    # presented as the whole.
    assert poids_declare("5 commandes · quelques minutes · rien n'a été réécrit") is None


def test_le_PLUS_est_un_separateur_au_meme_titre_que_le_point_median() -> None:
    assert poids_declare("1 fonction + 1 point d'appel + 3 témoins") is None
    assert poids_declare("1 fonction + 2 fonctions") == 3


def test_une_virgule_n_est_PAS_un_separateur() -> None:
    # "1 pass, bounded" is ONE unit followed by an aside, not two segments whose second is mute.
    assert poids_declare("1 tour, borné") == 1


def test_un_champ_vide_ou_sans_nombre_ne_rend_AUCUN_poids() -> None:
    assert poids_declare("") is None
    assert poids_declare("   ") is None
    assert poids_declare("petit") is None


def test_la_louche_rend_les_DEUX_parts_et_elles_different_quand_les_poids_existent() -> None:
    mesure = louche(
        (
            Item("A", "fait", "1 mesure"),
            Item("B", "a_faire", "27 mesures"),
        )
    )
    assert mesure.part_par_compte == pytest.approx(0.5)
    assert mesure.part_ponderee == pytest.approx(1 / 28)
    assert mesure.sans_poids == 0
    assert mesure.degradee is False


def test_un_item_SANS_poids_prend_la_MEDIANE_des_poids_lus() -> None:
    mesure = louche(
        (
            Item("A", "fait", "1 mesure"),
            Item("B", "fait", "3 mesures"),
            Item("C", "a_faire", "1 champ · 1 clause"),  # no weight -> median = 2
        )
    )
    assert mesure.mediane == pytest.approx(2.0)
    assert mesure.sans_poids == 1
    assert mesure.part_ponderee == pytest.approx(4 / 6)


def test_TOUS_sans_poids_rend_degradee_VRAI_et_les_deux_parts_EGALES() -> None:
    """The heart of the item: the weighting has no effect left, and the judge KNOWS it."""
    mesure = louche(
        (
            Item("A", "fait", "1 champ · 1 clause"),
            Item("B", "a_faire", "4 documents · 400 lignes"),
            Item("C", "a_faire", ""),
        )
    )
    assert mesure.degradee is True
    assert mesure.mediane is None
    assert mesure.part_ponderee == pytest.approx(mesure.part_par_compte)


def test_un_seul_item_sans_poids_ne_suffit_PAS_a_declarer_la_louche_degradee() -> None:
    mesure = louche((Item("A", "fait", "1 mesure"), Item("B", "a_faire", "")))
    assert mesure.sans_poids == 1
    assert mesure.degradee is False


def test_un_statut_CLOS_sort_de_la_population_et_est_COMPTE_a_part() -> None:
    mesure = louche(
        (
            Item("A", "fait", "1 mesure"),
            Item("B", "clos", "99 mesures"),
        )
    )
    assert mesure.total == 1
    assert mesure.hors_population == 1
    assert mesure.part_par_compte == pytest.approx(1.0)


def test_une_population_VIDE_LEVE_au_lieu_de_rendre_zero_pourcent() -> None:
    with pytest.raises(SansPopulation):
        louche(())


def test_une_population_entierement_CLOSE_leve_aussi() -> None:
    with pytest.raises(SansPopulation):
        louche((Item("A", "clos", "1 mesure"),))


# ─────────────────────────── 3. THE PUBLISHED TEXT ───────────────────────────


def test_le_texte_publie_porte_l_aveu_SANS_POIDS_dans_la_MEME_ligne_que_le_pourcentage() -> None:
    mesure = louche(
        (
            Item("A", "fait", "1 mesure"),
            Item("B", "a_faire", "1 champ · 1 clause"),
        )
    )
    texte = rendre(mesure)
    ligne_ponderee = next(ligne for ligne in texte.splitlines() if "weighted" in ligne)
    assert "without a readable weight: 1/2" in ligne_ponderee, texte


def test_le_texte_publie_DIT_que_la_ponderation_n_a_aucun_effet_quand_elle_n_en_a_aucun() -> None:
    mesure = louche((Item("A", "fait", "1 champ · 1 clause"), Item("B", "a_faire", "")))
    texte = rendre(mesure)
    assert "NO weight could be read" in texte, texte
    assert "not a second measurement" in texte, texte


def test_le_texte_publie_NOMME_les_items_hors_population() -> None:
    mesure = louche((Item("A", "fait", "1 mesure"), Item("B", "clos", "1 mesure")))
    assert "out of population" in rendre(mesure)


def test_le_texte_publie_porte_les_DEUX_pourcentages_et_le_compte_des_faits() -> None:
    mesure = louche((Item("A", "fait", "1 mesure"), Item("B", "a_faire", "1 mesure")))
    texte = rendre(mesure)
    assert "1/2 items done" in texte, texte
    assert "by plain count: 50,0 %" in texte, texte
    assert "weighted by declared size: 50,0 %" in texte, texte


def test_le_texte_publie_NOMME_les_statuts_comptes_faits() -> None:
    """A percentage whose "done" convention is unknown cannot be contested."""
    mesure = louche((Item("A", "fait", "1 mesure"),))
    assert "statuses counted as done: fait" in rendre(mesure)


# ─────────────────── 4. THE PRODUCTION VALUE (not injected) ───────────────────


def test_les_statuts_par_defaut_du_MODULE_sont_ceux_qu_on_croit() -> None:
    """Injecting everywhere elsewhere leaves the real value bare: here we judge the MODULE'S OWN."""
    assert FAITS_PAR_DEFAUT == frozenset({"fait"})
    assert HORS_POPULATION_PAR_DEFAUT == frozenset({"clos"})


def test_les_separateurs_reels_du_module_couvrent_les_trois_formes_du_corpus() -> None:
    assert avancement._SEPARATEURS.split("a·b;c+d") == ["a", "b", "c", "d"]


def test_le_dossier_par_defaut_du_BORD_est_le_plan_de_Mnemosyne() -> None:
    assert avancement_run.DOSSIER_PAR_DEFAUT == "docs"


def test_le_plan_REEL_de_ce_depot_se_lit_et_declare_une_MAJORITE_d_items_sans_poids() -> None:
    """The production value, drawn from the real population — not a fixture.

    This witness freezes NO progress figure (it would move with every closed item): it freezes the
    one structural property that motivated the item — *this corpus declares its size 100% of the
    time and its magnitude for a minority*, so the weighted ladle here is mostly carried by the
    median.
    """
    items = avancement_run.items_du_plan(avancement_run._racine() / "docs")
    assert len(items) > 50, "this repository's plan no longer reads — instrument failure"
    assert all(item.taille for item in items), "a plan item lost its `*Size*` field"
    mesure = louche(items)
    assert mesure.sans_poids > mesure.total / 2


# ──────────────────── 2. THE RC + 5. THE PASSING CASE ────────────────────


def test_le_CAS_PASSANT_le_plan_reel_rend_rc_0_et_imprime_la_louche(capsys) -> None:
    assert avancement_run.main([]) == 0
    sortie = capsys.readouterr().out
    assert "LADLE —" in sortie
    assert "by plain count" in sortie
    assert "without a readable weight" in sortie


def test_un_dossier_INEXISTANT_rend_rc_2_et_dit_que_ce_n_est_PAS_zero_pourcent(
    tmp_path, capsys, monkeypatch
) -> None:
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    monkeypatch.delenv("DOSSIER", raising=False)
    assert avancement_run.main(["dossier-qui-n-existe-pas"]) == 2
    assert "Ce n'est pas « 0 % fait »" in capsys.readouterr().err


def test_un_dossier_SANS_PLAN_rend_rc_2_et_nomme_la_panne_d_instrument(
    tmp_path, capsys, monkeypatch
) -> None:
    (tmp_path / "vide").mkdir()
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    monkeypatch.delenv("DOSSIER", raising=False)
    assert avancement_run.main(["vide"]) == 2
    erreur = capsys.readouterr().err
    assert "instrument failure" in erreur
    assert "make plans" in erreur


def test_la_variable_DOSSIER_est_lue_par_le_bord(tmp_path, capsys, monkeypatch) -> None:
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    monkeypatch.setenv("DOSSIER", "absent")
    assert avancement_run.main([]) == 2
    assert "absent" in capsys.readouterr().err


# --------------------------------------------------------------------------------------------
# THE PUBLISHED TEXT — after an isolated audit: the `degradee` branch was MUTE.
# --------------------------------------------------------------------------------------------
#
# This is the branch that matters most in this whole module: it says that a weighted ladle has
# STOPPED carrying weight without ever stopping to display two figures. Without it, a reader
# compares a number to itself while believing they are reading a second measurement.
def test_la_branche_DEGRADEE_a_sa_propre_phrase_dans_le_texte() -> None:
    """Mutation `elif mesure.degradee:` -> `elif False:`: SURVIVED before this witness."""
    from mnemosyne.production.avancement import Louche, rendre

    texte = rendre(
        Louche(
            total=4,
            faits=2,
            hors_population=0,
            sans_poids=4,  # ALL without their own weight: the weighting has no effect left
            mediane=1.0,
            part_par_compte=0.5,
            part_ponderee=0.5,
        )
    )
    assert "NO effect" in texte or "SAME" in texte, "the degradation is published in silence"
    assert "4" in texte  # the number of items without a weight travels WITH the percentage


def test_une_louche_NON_degradee_ne_crie_PAS_a_la_degradation() -> None:
    """The counter-proof: without it, this witness would only measure my tendency to always alarm."""
    from mnemosyne.production.avancement import Louche, rendre

    texte = rendre(
        Louche(
            total=4,
            faits=2,
            hors_population=0,
            sans_poids=1,  # only one without a weight: the weighting still carries something
            mediane=2.0,
            part_par_compte=0.5,
            part_ponderee=0.5556,
        )
    )
    assert "NO effect" not in texte
