"""Witnesses for `P6` — a computed number's agreement with its copies in prose.

The FIVE surfaces (one module in this repository already survived 19 green witnesses with 6
surviving mutations, because none of them read the rc or the published text):

1. the JUDGE — :func:`portee`, :func:`verdict` on pure data;
2. the RC — ``main()``: 0 agreed · 1 disagreement · 2 instrument failure;
3. the published TEXT — the refusal that NAMES each address, and the sentence that spares the dated ones;
4. the PRODUCTION VALUE — the REAL reference and the real SET of live documents;
5. the PASSING CASE — today's repository agrees, and it says so.
"""

from __future__ import annotations

import subprocess

import pytest

from mnemosyne.production.accord_chiffre import (
    DATEE,
    REGISTRES_DATES,
    VIVE,
    Recopie,
    SansRecopie,
    portee,
    rendre,
    verdict,
)
from mnemosyne.runtime import accord_chiffre_run as bord

# ─────────────────────────────── 1. THE JUDGE ───────────────────────────────


def test_un_segment_ARCHIVE_entier_date_le_document() -> None:
    assert portee("notes/archive/inventory.md") == DATEE


def test_un_segment_qui_CONTIENT_archive_ne_date_RIEN() -> None:
    """The segment boundary: without it, `archivistes/` would silently fall outside judgment."""
    assert portee("notes/archivists/note.md") == VIVE
    assert portee("notes/my-archive-notes.md") == VIVE


def test_un_nom_de_fichier_qui_ouvre_sur_une_DATE_ISO_est_date() -> None:
    assert portee("notes/log/2026-08-09-example-entry.md") == DATEE


def test_une_date_AU_MILIEU_du_nom_ne_date_PAS_le_document() -> None:
    assert portee("notes/REPORT_2026-07-09.md") == VIVE


def test_un_JOURNAL_est_un_registre_d_entrees_datees() -> None:
    assert portee("notes/log/journal-session-3.md") == DATEE
    assert portee("notes/log/session-3.md") == VIVE


def test_un_document_de_l_ENSEMBLE_des_registres_est_date() -> None:
    assert portee("registry.md", registres={"registry.md"}) == DATEE


def test_un_document_INCONNU_est_VIF_par_defaut() -> None:
    """The sensible default: what we failed to recognize gets JUDGED, never spared."""
    assert portee("a/path/never/seen.md") == VIVE
    assert portee("") == VIVE


def test_le_verdict_NOMME_chaque_site_vif_en_desaccord_jamais_un_total() -> None:
    resultat = verdict(
        27,
        (
            Recopie("README.md", 30, 27),
            Recopie("OVERVIEW.md", 30, 28),
            Recopie("GUIDE.md", 23, 26),
        ),
    )
    assert resultat.accorde is False
    assert [d.recopie.adresse for d in resultat.desaccords] == [
        "OVERVIEW.md:30",
        "GUIDE.md:23",
    ]


def test_DEUX_erreurs_OPPOSEES_ne_se_compensent_PAS() -> None:
    """The real case a total would turn green: 28 and 26 average to 27."""
    resultat = verdict(27, (Recopie("a.md", 1, 28), Recopie("b.md", 1, 26)))
    assert len(resultat.desaccords) == 2


def test_un_enregistrement_DATE_n_est_JAMAIS_accuse_mais_il_est_RENDU() -> None:
    resultat = verdict(27, (Recopie("notes/archive/old.md", 5, 12), Recopie("README.md", 1, 27)))
    assert resultat.accorde is True
    assert resultat.vifs == 1
    assert [r.adresse for r in resultat.dates] == ["notes/archive/old.md:5"]


def test_le_cardinal_des_paires_COMPAREES_est_publie_avec_le_verdict() -> None:
    """An equality over zero pairs is true by construction; the cardinal is what tells us so."""
    resultat = verdict(27, (Recopie("notes/archive/a.md", 1, 99),))
    assert resultat.accorde is True
    assert resultat.vifs == 0, "no live site: the agreement PROVES NOTHING, and the number says so"


def test_une_liste_VIDE_de_recopies_LEVE_au_lieu_de_rendre_un_accord() -> None:
    with pytest.raises(SansRecopie):
        verdict(27, ())


def test_l_ensemble_des_registres_dates_est_injectable() -> None:
    site = (Recopie("MON_REGISTRE.md", 1, 99),)
    assert verdict(27, site).accorde is False
    assert verdict(27, site, registres={"MON_REGISTRE.md"}).accorde is True


# ─────────────────────────── 3. THE PUBLISHED TEXT ───────────────────────────


def test_le_refus_publie_CHAQUE_adresse_et_son_verbatim() -> None:
    resultat = verdict(27, (Recopie("OVERVIEW.md", 30, 28, "the 28 invariants"),))
    texte = rendre(resultat, quoi="the invariant count", commande="make x")
    assert "OVERVIEW.md:30 wrote 28, computed 27" in texte, texte
    assert "the 28 invariants" in texte, texte


def test_le_refus_publie_DIT_que_les_enregistrements_dates_ne_sont_pas_accuses() -> None:
    resultat = verdict(27, (Recopie("OVERVIEW.md", 30, 28), Recopie("notes/archive/v.md", 1, 12)))
    texte = rendre(resultat, quoi="the invariant count", commande="make x")
    assert "are NOT" in texte and "falsify" in texte, texte


def test_le_texte_publie_NOMME_la_commande_qui_recalcule_la_reference() -> None:
    resultat = verdict(27, (Recopie("README.md", 1, 27),))
    texte = rendre(resultat, quoi="the invariant count", commande="my-command")
    assert "computed 27 by `my-command`" in texte, texte


def test_le_texte_publie_porte_le_cardinal_compare_ET_le_nombre_d_epargnes() -> None:
    resultat = verdict(27, (Recopie("README.md", 1, 27), Recopie("notes/archive/v.md", 1, 12)))
    texte = rendre(resultat, quoi="x", commande="y")
    assert "1 live occurrence(s) confronted" in texte, texte
    assert "1 dated record(s) spared" in texte, texte


# ─────────────────── 4. THE PRODUCTION VALUE (not injected) ───────────────────


def test_l_ensemble_des_registres_dates_du_MODULE_est_celui_qu_on_croit() -> None:
    # Freeze the SET, never the count — and here the set is EMPTY, which is a claim, not an
    # absence: this distribution ships no append-only log whose copies of the number are dated
    # inside their own entries. Adding a name is a deliberate gesture that must be measured first
    # (see the comment on REGISTRES_DATES). The injectable path is exercised by the two witnesses
    # that pass `registres=` explicitly, so rule 4 of `portee` is not left untested.
    assert REGISTRES_DATES == frozenset()


def test_la_reference_est_RECALCULEE_depuis_le_registre_reel_de_CONSTITUTION() -> None:
    """What the module REALLY counts — no number is hard-coded in the boundary."""
    racine = bord._racine()
    texte = (racine / bord.SOURCE).read_text(encoding="utf-8")
    assert bord.reference_invariants(texte) == 5


def test_une_section_INTROUVABLE_LEVE_au_lieu_de_rendre_zero() -> None:
    with pytest.raises(ValueError, match="not found"):
        bord.reference_invariants("# a document without a registry\n\nsome text.\n")


def test_une_section_SANS_ENTREE_LEVE_au_lieu_de_rendre_zero() -> None:
    with pytest.raises(ValueError, match="NO numbered entry"):
        bord.reference_invariants(f"{bord.SECTION} 5 couches\n\nsome text.\n\n## 6. other\n")


def test_l_ENSEMBLE_reel_des_documents_VIFS_de_ce_depot_est_gele() -> None:
    """A SET, never a count: a swap would leave the count identical and mute.

 This freeze forbids nothing — it **forces a pass through here** to add one more live claim
 about the layer count. That is the conscious price of one more copy.

 The set is read off the documents this repository actually TRACKS, so it is a measurement of
 the real corpus and not a fixture: the guide that teaches the architecture and the reference
 that defines it are the two documents that state the count in prose.
 """
    racine = bord._racine()
    sites = bord.recopies(racine, bord.documents_suivis(racine))
    vifs = {site.document for site in sites if portee(site.document) == VIVE}
    assert vifs == {
        "system/skills/skill-creator/SKILL.md",
        "system/skills/skill-creator/references/architecture.md",
    }


def test_la_population_reelle_porte_des_enregistrements_DATES_qu_on_epargne() -> None:
    """Without them, the live/dated distinction would be a theory: here it has a measured object."""
    racine = bord._racine()
    sites = bord.recopies(racine, bord.documents_suivis(racine))
    dates = [site for site in sites if portee(site.document) == DATEE]
    assert len(dates) > 20
    assert any(site.valeur != 27 for site in dates), (
        "no dated record carries a DIFFERENT value: the sparing clause "
        "is proven by nothing on the real population"
    )


# ──────────────────── 2. THE RC + 5. THE PASSING CASE ────────────────────


def test_le_compteur_pour_le_tick_est_FAIL_OPEN_hors_d_un_depot(tmp_path) -> None:
    """The tick asks the question on every startup: making it raise would block the session."""
    assert bord.desaccords_ouverts(tmp_path) == 0


def test_le_compteur_pour_le_tick_voit_le_depot_REEL_et_le_trouve_accorde() -> None:
    assert bord.desaccords_ouverts(bord._racine()) == 0


def test_le_compteur_pour_le_tick_COMPTE_un_desaccord_reel(tmp_path) -> None:
    """ **Written after a SURVIVING sabotage.**

 The neighboring witness only asserted ``== 0`` against the real repository, **which agrees
 today**: replacing the counter's whole body with ``return 0`` therefore stayed GREEN. *A
 counter that never counts anything passes for correct as long as the world is healthy.* A SICK
 world is required.
 """
    (tmp_path / bord.SOURCE).parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / bord.SOURCE).write_text(
        f"{bord.SECTION} 2 couches\n\n1. one\n2. two\n\n## 6. other\n", encoding="utf-8"
    )
    (tmp_path / "README.md").write_text("this repository has 9 couches\n", encoding="utf-8")
    (tmp_path / "AUTRE.md").write_text("and also 5 couches\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    assert bord.desaccords_ouverts(tmp_path) == 2


def test_le_CAS_PASSANT_le_depot_d_aujourd_hui_s_accorde_et_rend_rc_0(capsys) -> None:
    assert bord.main([]) == 0
    sortie = capsys.readouterr().out
    assert "All live claims agree" in sortie


def test_un_DESACCORD_reel_rend_rc_1_et_nomme_le_site(tmp_path, capsys, monkeypatch) -> None:
    """The rc bites: a toy repository where a live claim lies must exit with 1."""
    (tmp_path / bord.SOURCE).parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / bord.SOURCE).write_text(
        f"{bord.SECTION} 2 couches\n\n1. one\n2. two\n\n## 6. other\n", encoding="utf-8"
    )
    (tmp_path / "README.md").write_text("this repository has 9 couches\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))

    assert bord.main([]) == 1
    sortie = capsys.readouterr().out
    assert "README.md:1 wrote 9, computed 2" in sortie, sortie
    assert f"{bord.SOURCE}:1 wrote 2" not in sortie, (
        "the section heading agrees, it is not accused"
    )


def test_un_depot_SANS_source_rend_rc_2_et_refuse_de_dire_accorde(
    tmp_path, capsys, monkeypatch
) -> None:
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    assert bord.main([]) == 2
    erreur = capsys.readouterr().err
    assert "This is NOT" in erreur and "the instrument did not measure" in erreur


def test_un_depot_SANS_AUCUNE_recopie_rend_rc_2_jamais_un_accord(
    tmp_path, capsys, monkeypatch
) -> None:
    (tmp_path / bord.SOURCE).parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / bord.SOURCE).write_text(
        f"{bord.SECTION} two rules\n\n1. one\n2. two\n\n## 6. other\n", encoding="utf-8"
    )
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    assert bord.main([]) == 2
    assert "instrument failure" in capsys.readouterr().err


def test_git_indisponible_rend_rc_2_et_non_un_balayage_vide(tmp_path, capsys, monkeypatch) -> None:
    (tmp_path / bord.SOURCE).parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / bord.SOURCE).write_text(
        f"{bord.SECTION} 1 couche\n\n1. one\n\n## 6. other\n", encoding="utf-8"
    )
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))  # not a git repository
    assert bord.main([]) == 2
    erreur = capsys.readouterr().err
    assert "the instrument did not measure" in erreur
    # **WHAT THIS WITNESS COST, AND WHY IT IS WRITTEN THIS WAY.** Its first form only
    # asserted the `rc 2` — and a sabotage that replaced `documents_suivis`'s `raise` with
    # `return ()` SURVIVED: the population became empty, `SansRecopie` raised further down, and
    # the same `rc 2` came out. *Two different failures produced identical code.* The rc therefore
    # does NOT distinguish a broken git from an empty corpus; only the SENTENCE does, and that is
    # what we pin down.
    assert "git ls-files" in erreur, (
        "a broken git must accuse ITSELF: without this phrase, it reads as "
        "\"no copy found\", which sends the reader to repair the wrong organ"
    )


def test_le_motif_de_recopie_du_module_lit_le_SINGULIER_pour_pouvoir_l_epargner() -> None:
    """A singular copy is still a copy: excluding it from the pattern would be a silent decision."""
    assert accord_chiffre_motif("0 couche remains") == [("0")]


def accord_chiffre_motif(ligne: str) -> list[str]:
    return [trouve.group(1) for trouve in bord._RECOPIE.finditer(ligne)]


def test_le_titre_de_SECTION_est_trouve_dans_les_DEUX_langues_et_un_titre_MUET_est_REFUSE() -> None:
    """2026-09-09. ``SECTION`` was the French literal ``"## Les"``. On the day the public mirror
    translated the title to ``## The 5 layers, ...``, the gate no longer found its section and THREE
    witnesses failed -- loudly, because here a missing section RAISES instead of returning 0. This
    design choice made the failure visible rather than silent.

    This witness holds the broadening in both directions: both languages are found, and a heading
    that opens NO numbered registry is always REFUSED -- broadening did not transform the gate into
    a pass-all.
    """
    for titre in ("## Les 5 couches, dans l'ordre", "## The 5 layers, in the order"):
        texte = f"{titre}\n\n1. one\n2. two\n3. three\n\n## next\n"
        assert bord.reference_invariants(texte) == 3, f"section non trouvee pour {titre!r}"

    # ... and the refusal holds: a recognised title that opens NO numbered entry RAISES.
    with pytest.raises(ValueError, match="NO numbered entry|AUCUNE entree"):
        bord.reference_invariants("## The rules\n\nplain prose, no registry.\n\n## next\n")
    # ... as does a text whose title does not exist at all.
    with pytest.raises(ValueError, match="not found|introuvable"):
        bord.reference_invariants("## Something else\n\n1. one\n\n## next\n")
