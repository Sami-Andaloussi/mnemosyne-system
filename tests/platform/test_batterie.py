"""Witnesses for the test battery that cannot melt away (G4).

The FIVE surfaces, separately: the pure judge · the rc · the published text · the PRODUCTION
value (the two freezes and the `RACINE`, judged against the REAL repo) · the passing case.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mnemosyne.production.batterie import (
    MUETS_GELES,
    SAUTS_GELES,
    Rapport,
    message,
    sites_de_saut,
    temoins_muets,
    verdict,
)
from mnemosyne.runtime import batterie_run

_GEL_VIDE: frozenset[str] = frozenset()


def _juger(rapport: Rapport, sauts: frozenset[str] = _GEL_VIDE, muets: frozenset[str] = _GEL_VIDE):
    return verdict(rapport, sauts_geles=sauts, muets_geles=muets)


# --------------------------------------------------------------------------------------------
# 1. THE JUDGE — the four conditions, purely.
# --------------------------------------------------------------------------------------------


def test_le_CAS_PASSANT_une_batterie_pleine_et_conforme_ne_refuse_RIEN() -> None:
    """Without this witness, we only measure its ability to refuse everything."""
    v = _juger(
        Rapport(collectes=12, sites_de_saut=("a.py::test_x",), muets=("b.py::test_y",)),
        sauts=frozenset({"a.py::test_x"}),
        muets=frozenset({"b.py::test_y"}),
    )
    assert v.refuse is False and v.non_mesure is False
    assert v.tenus == ("a.py::test_x", "b.py::test_y")


def test_un_ECHEC_refuse_et_l_erreur_est_une_case_DISTINCTE() -> None:
    assert _juger(Rapport(collectes=3, echecs=("t::a",))).refuse is True
    v = _juger(Rapport(collectes=3, erreurs=("t::b",)))
    assert v.refuse is True and v.echecs == () and v.erreurs == ("t::b",)


def test_une_batterie_VIDE_est_une_NON_MESURE_jamais_un_vert() -> None:
    """*An `OK` on an empty battery is the falsest green there is.*"""
    v = _juger(Rapport(collectes=0))
    assert v.non_mesure is True
    assert v.refuse is False, "non_mesure and refuse are two DISTINCT states, never conflated"


def test_un_SAUT_NEUF_refuse_et_un_saut_GELE_passe() -> None:
    gel = frozenset({"a.py::test_connu"})
    assert (
        _juger(Rapport(collectes=2, sites_de_saut=("a.py::test_connu",)), sauts=gel).refuse is False
    )
    neuf = _juger(
        Rapport(collectes=2, sites_de_saut=("a.py::test_connu", "b.py::test_neuf")), sauts=gel
    )
    assert neuf.sauts_neufs == ("b.py::test_neuf",) and neuf.refuse is True


def test_le_cliquet_des_SAUTS_refuse_AUSSI_dans_l_autre_sens() -> None:
    """*A loosened ratchet no longer clicks*: the gain must be banked, not lost again."""
    v = _juger(Rapport(collectes=2, sites_de_saut=()), sauts=frozenset({"a.py::test_connu"}))
    assert v.sauts_disparus == ("a.py::test_connu",) and v.refuse is True


def test_un_ECHANGE_de_sauts_laisse_le_COMPTE_identique_et_le_gel_le_NOMME() -> None:
    """1 = 1, silent — if the freeze were about a COUNT. It is about the SET."""
    v = _juger(
        Rapport(collectes=2, sites_de_saut=("b.py::neuf",)), sauts=frozenset({"a.py::vieux"})
    )
    assert v.sauts_neufs == ("b.py::neuf",) and v.sauts_disparus == ("a.py::vieux",)


def test_un_MUET_NEUF_refuse_et_le_cliquet_des_muets_refuse_dans_les_deux_sens() -> None:
    gel = frozenset({"a.py::test_innocent"})
    assert _juger(Rapport(collectes=2, muets=("a.py::test_innocent",)), muets=gel).refuse is False
    assert _juger(Rapport(collectes=2, muets=("z.py::test_neuf",)), muets=gel).muets_neufs == (
        "z.py::test_neuf",
    )
    assert _juger(Rapport(collectes=2, muets=()), muets=gel).muets_disparus == (
        "a.py::test_innocent",
    )


# --------------------------------------------------------------------------------------------
# 2. THE TWO STATIC READERS — pure, over text.
# --------------------------------------------------------------------------------------------


def test_temoins_muets_voit_le_test_sans_assertion_et_EPARGNE_les_formes_reelles() -> None:
    source = (
        "import pytest\n"
        "def test_muet():\n    faire()\n"
        "def test_assert():\n    assert 1\n"
        "def test_raises():\n"
        "    with pytest.raises(ValueError):\n        casser()\n"
        "def pas_un_test():\n    faire()\n"
    )
    assert temoins_muets(source, "t.py") == ("t.py::test_muet",)


def test_sites_de_saut_voit_le_MARQUEUR_et_l_APPEL_et_rien_d_autre() -> None:
    source = (
        "import pytest\n"
        "@pytest.mark.skipif(True, reason='x')\n"
        "def test_marque():\n    assert 1\n"
        "def test_appel():\n"
        "    if True:\n        pytest.skip('x')\n    assert 1\n"
        "def test_ordinaire():\n    assert 1\n"
    )
    assert sites_de_saut(source, "t.py") == ("t.py::test_marque", "t.py::test_appel")


def test_un_marqueur_de_saut_NU_sans_parentheses_est_vu_lui_aussi() -> None:
    """**SABOTAGE FIX.** Turning off the decorator clause SURVIVED: `ast.walk` on a function
    also traverses its `decorator_list`, so the second clause was catching for the first — but
    only for the CALLED form (`@pytest.mark.skipif(...)`). The BARE form (`@pytest.mark.skip`,
    no parentheses) is not a `Call`: it is seen ONLY by the decorator clause. *Two clauses where
    one covers the other leave the first untestable.*"""
    source = "import pytest\n@pytest.mark.skip\ndef test_nu():\n    assert 1\n"
    assert sites_de_saut(source, "t.py") == ("t.py::test_nu",)


# --------------------------------------------------------------------------------------------
# 3. THE PUBLISHED TEXT — the sentence, not just the data.
# --------------------------------------------------------------------------------------------


def test_le_texte_de_NON_MESURE_ne_se_lit_pas_comme_un_vert() -> None:
    texte = message(_juger(Rapport(collectes=0)))
    assert "NOT MEASURED" in texte and "the falsest green" in texte


def test_le_texte_publie_TOUJOURS_le_cardinal_meme_quand_tout_va_bien() -> None:
    """*A green does not say by how much* — except here."""
    texte = message(_juger(Rapport(collectes=4657)))
    assert "4657 test(s) collected" in texte


def test_le_texte_nomme_TOUTES_les_causes_jamais_la_premiere_seule() -> None:
    texte = message(
        _juger(
            Rapport(collectes=3, echecs=("t::a",), sites_de_saut=("s::b",), muets=("m::c",)),
        )
    )
    assert "FAILING" in texte and "SKIP" in texte and "SILENT" in texte


def test_le_message_de_refus_nomme_le_GESTE_pas_seulement_la_faute() -> None:
    """*The refusal message names the way out* — without that, the reader loosens the judge."""
    texte = message(_juger(Rapport(collectes=3, muets=("m::c",))))
    assert "MUETS_GELES" in texte and "batterie.py" in texte


# --------------------------------------------------------------------------------------------
# 4. THE RC — the line that turns a verdict into a refusal.
# --------------------------------------------------------------------------------------------


#: BOTH FREEZES ARE EMPTIED IN THESE WITNESSES, AND THAT IS DELIBERATE: a fixture repo carries
#: none of the 56 frozen sites of the real repo, so the PRODUCTION freezes would always refuse
#: there — and the measured rc would no longer be that of the clause under test.
#: The production value itself is judged separately, in section 5.
_SANS_GEL = {"sauts_geles": frozenset(), "muets_geles": frozenset()}


def _faux_depot(tmp_path: Path, fichiers: dict[str, str]) -> Path:
    (tmp_path / "tests").mkdir()
    for nom, contenu in fichiers.items():
        (tmp_path / "tests" / nom).write_text(contenu, encoding="utf-8")
    return tmp_path


def test_le_rc_vaut_0_sur_une_batterie_conforme(tmp_path: Path) -> None:
    racine = _faux_depot(tmp_path, {"test_a.py": "def test_ok():\n    assert 1\n"})
    assert batterie_run.main(racine=racine, compter=lambda _: 9, **_SANS_GEL) == 0


def test_le_rc_vaut_1_sur_un_MUET_hors_du_gel(tmp_path: Path) -> None:
    racine = _faux_depot(tmp_path, {"test_a.py": "def test_muet():\n    pass\n"})
    assert batterie_run.main(racine=racine, compter=lambda _: 9, **_SANS_GEL) == 1


def test_le_rc_vaut_2_quand_ZERO_test_est_collecte_pas_0_ni_1(tmp_path: Path) -> None:
    racine = _faux_depot(tmp_path, {"test_a.py": "def test_ok():\n    assert 1\n"})
    assert batterie_run.main(racine=racine, compter=lambda _: 0, **_SANS_GEL) == 2


def test_le_rc_vaut_2_quand_le_dossier_des_temoins_est_ABSENT(tmp_path: Path) -> None:
    assert batterie_run.main(racine=tmp_path, compter=lambda _: 9, **_SANS_GEL) == 2


def test_le_rc_vaut_1_sur_un_ECHEC_lu_dans_un_vrai_rapport_JUnit(tmp_path: Path) -> None:
    racine = _faux_depot(tmp_path, {"test_a.py": "def test_ok():\n    assert 1\n"})
    rapport = tmp_path / "junit.xml"
    rapport.write_text(
        '<testsuite><testcase classname="t" name="ok"/>'
        '<testcase classname="t" name="ko"><failure>boum</failure></testcase></testsuite>',
        encoding="utf-8",
    )
    assert batterie_run.main(["--rapport", str(rapport)], racine=racine, **_SANS_GEL) == 1


def test_un_rapport_JUnit_ILLISIBLE_rend_2_jamais_0(tmp_path: Path) -> None:
    """A broken report must not read like a healthy battery."""
    racine = _faux_depot(tmp_path, {"test_a.py": "def test_ok():\n    assert 1\n"})
    assert (
        batterie_run.main(["--rapport", str(tmp_path / "absent.xml")], racine=racine, **_SANS_GEL)
        == 2
    )


def test_sans_rapport_la_page_AVOUE_que_rien_n_a_tourne(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    """*An admission spelled out in full is a valid answer; silence is not one.*"""
    racine = _faux_depot(tmp_path, {"test_a.py": "def test_ok():\n    assert 1\n"})
    batterie_run.main(racine=racine, compter=lambda _: 9, **_SANS_GEL)
    assert "NO RUN REPORT" in capsys.readouterr().out


def test_le_drapeau_gel_IMPRIME_les_deux_gels_prets_a_coller_et_n_ECRIT_RIEN(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    """*A freeze that rewrites itself always yields "nothing moved".* `--gel` PRINTS."""
    racine = _faux_depot(tmp_path, {"test_a.py": "def test_muet():\n    pass\n"})
    empreinte = (racine / "tests" / "test_a.py").read_bytes()
    assert batterie_run.main(["--gel"], racine=racine, **_SANS_GEL) == 0
    sortie = capsys.readouterr().out
    assert "MUETS_GELES" in sortie and "SAUTS_GELES" in sortie
    assert '"tests/test_a.py::test_muet",' in sortie
    assert (racine / "tests" / "test_a.py").read_bytes() == empreinte
    source = Path(batterie_run.__file__).read_text(encoding="utf-8")
    assert "write_text" not in source, "the edge must not WRITE anywhere"


# --------------------------------------------------------------------------------------------
# 5. THE PRODUCTION VALUE — judged against the REAL repo, never injected.
# --------------------------------------------------------------------------------------------


def test_la_RACINE_de_production_designe_le_DEPOT_et_ses_temoins() -> None:
    assert (batterie_run.RACINE / batterie_run.DOSSIER / "conftest.py").is_file()


def test_le_CAS_PASSANT_de_PRODUCTION_les_DEUX_gels_tiennent_sur_le_depot_REEL() -> None:
    """No injection: the real freezes, the real tree. This is the witness that will turn red
    the day someone adds a skip or a silent witness without saying so."""
    muets, sauts = batterie_run.lire_les_formes(batterie_run.RACINE)
    v = verdict(
        Rapport(collectes=1, sites_de_saut=sauts, muets=muets),
        sauts_geles=SAUTS_GELES,
        muets_geles=MUETS_GELES,
    )
    assert v.refuse is False, message(v)


def test_les_gels_de_production_ne_sont_PAS_VIDES() -> None:
    """An empty freeze is doubly inert (empty set, nothing to compare against) — the exact fault
    an adversarial audit found on `PORTES_QUI_DECLARENT` on 2026-08-17."""
    assert len(MUETS_GELES) == 16
    assert len(SAUTS_GELES) == 46


def test_chaque_entree_des_gels_designe_un_FICHIER_qui_existe() -> None:
    """A freeze that names a vanished file protects a past — and never turns red on its own."""
    for entree in sorted(MUETS_GELES | SAUTS_GELES):
        chemin, _, _nom = entree.partition("::")
        assert (batterie_run.RACINE / chemin).is_file(), entree


def test_le_compteur_REEL_de_collectes_rend_un_nombre_PLAUSIBLE() -> None:
    """The real `compter_les_collectes`, not the injected one: *injecting everywhere leaves the
    real value naked*, and that is how a `parents[4]` reset to `parents[3]` survives nineteen
    witnesses."""
    combien = batterie_run.compter_les_collectes(batterie_run.RACINE)
    assert combien > 1000, f"pytest's output was not read: {combien}"


# --------------------------------------------------------------------------------------------
# THE PUBLISHED TEXT — written after an isolated audit found 3 of the 6 causes SILENT.
# --------------------------------------------------------------------------------------------
#
# The six causes live in a tuple walked by a loop. The original witnesses built a `Verdict`
# with THREE causes and asserted only `"FAILING"`, `"SKIP"`, `"SILENT"` — so neutralizing
# `erreurs`, `sauts_disparus`, or `muets_disparus` left 27 witnesses green.
# *A witness that only arms half the population measures its own silence on the other half.*
def test_les_SIX_causes_sont_TOUTES_nommees_dans_la_phrase() -> None:
    """COMPLETE population: every populated cause must appear, each with ITS OWN label."""
    from mnemosyne.production.batterie import Verdict, message

    texte = message(
        Verdict(
            echecs=("t_echec",),
            erreurs=("t_erreur",),
            sauts_neufs=("t_saut_neuf",),
            sauts_disparus=("t_saut_parti",),
            muets_neufs=("t_muet_neuf",),
            muets_disparus=("t_muet_parti",),
            collectes=6,
        )
    )
    for nom in (
        "t_echec",
        "t_erreur",
        "t_saut_neuf",
        "t_saut_parti",
        "t_muet_neuf",
        "t_muet_parti",
    ):
        assert nom in texte, f"the cause carrying {nom} is silent in the message"
    # …and the six labels are DISTINCT: without that, one alone would satisfy all six.
    for libelle in (
        "FAILING",
        "in ERROR",
        "SKIP site(s) outside",
        "no longer are",
        "SILENT witness(es) outside",
        "now assert",
    ):
        assert libelle in texte, f"missing label: {libelle}"


def test_une_cause_VIDE_ne_produit_AUCUNE_ligne() -> None:
    """The counter-proof: without it, the witness above would only measure my ability to say everything."""
    from mnemosyne.production.batterie import Verdict, message

    texte = message(Verdict(echecs=("seul",), collectes=1))
    assert "seul" in texte
    for absent in ("ERROR", "SKIP", "SILENT"):
        assert absent not in texte, f"{absent} is named even though its cause is empty"


def test_chaque_cause_porte_son_REMEDE_propre() -> None:
    """A message that names the defect without naming the action turns the gate into a reproach."""
    from mnemosyne.production.batterie import Verdict, message

    assert "SAUTS_GELES" in message(Verdict(sauts_neufs=("x",), collectes=1))
    assert "MUETS_GELES" in message(Verdict(muets_neufs=("x",), collectes=1))
    assert "REMOVE" in message(Verdict(sauts_disparus=("x",), collectes=1))
    assert "REMOVE" in message(Verdict(muets_disparus=("x",), collectes=1))
