"""Witnesses for `G8` — a diffused rule names the population where it was measured.

The FIVE surfaces:

1. the JUDGE — :func:`tampon`, :func:`population_nommee`, :func:`perimee`, :func:`verdict` (pure);
2. the RC — ``main()``: 0 published/acceptable · 1 contract refused · 2 instrument failure;
3. the published TEXT — the refusal that NAMES its reason and the fix, the acknowledgment that
   says it is not a refusal;
4. the PRODUCTION VALUE — the real SET of surfaces, and this repo's real identity;
5. the PASSING CASE — a contract stamped on a known commit is ACCEPTED, end to end.
"""

from __future__ import annotations

import pytest

from mnemosyne.production.diffusion import (
    ETIQUETTE,
    MODIFIE,
    PROPRE,
    Population,
    SansDiffusion,
    perimee,
    population_nommee,
    rendre,
    tampon,
    verdict,
)
from mnemosyne.runtime import diffusion_run as bord

UN_COMMIT = "a" * 40
AUTRE_COMMIT = "b" * 40


def une_population(**changements) -> Population:
    defauts = dict(racine="X", commit=UN_COMMIT, arbre=PROPRE, emis_le="2026-09-08")
    return Population(**{**defauts, **changements})


# ─────────────────────────────── 1. THE JUDGE ───────────────────────────────


def test_le_tampon_se_relit_lui_meme_sans_perte() -> None:
    origine = une_population()
    relue = population_nommee(f"contract text\n{tampon(origine)}\nmore contract text\n")
    assert relue == origine


def test_un_texte_SANS_tampon_rend_None_et_non_une_population_vide() -> None:
    assert population_nommee("a rule with no provenance\n") is None


def test_un_tampon_MALFORME_n_est_PAS_lu_comme_une_population() -> None:
    assert population_nommee(f"# {ETIQUETTE}: commit=zzz\n") is None
    assert population_nommee(f"# {ETIQUETTE}: racine=X commit={UN_COMMIT} arbre=propre\n") is None


def test_un_commit_ABSENT_de_l_histoire_du_receveur_est_REFUSE() -> None:
    raison = perimee(une_population(), connus={AUTRE_COMMIT})
    assert raison is not None and "not in your history" in raison


def test_un_arbre_MODIFIE_est_refuse_meme_si_le_commit_est_connu() -> None:
    """A contract emitted from a dirty tree names a population that exists in no commit."""
    raison = perimee(une_population(arbre=MODIFIE), connus={UN_COMMIT})
    assert raison is not None and MODIFIE in raison


def test_une_histoire_VIDE_chez_le_receveur_REFUSE_au_lieu_d_accepter() -> None:
    """The worst case — a repo that could read nothing — must not pass for the best one."""
    raison = perimee(une_population(), connus=frozenset())
    assert raison is not None and "NOTHING was verified" in raison


def test_un_commit_ABREGE_dans_le_tampon_reste_verifiable() -> None:
    assert perimee(une_population(commit=UN_COMMIT[:7]), connus={UN_COMMIT}) is None


def test_le_CAS_PASSANT_du_juge_un_contrat_tracable_et_connu_n_est_PAS_refuse() -> None:
    assert perimee(une_population(), connus={UN_COMMIT, AUTRE_COMMIT}) is None


def test_le_verdict_NOMME_chaque_surface_jamais_un_total() -> None:
    etat = verdict(
        {
            "a-emit": f"contract\n{tampon(une_population())}\n",
            "b-emit": "bare contract\n",
            "c-emit": "bare contract too\n",
        }
    )
    assert etat.tamponnees == ("a-emit",)
    assert etat.sans_tampon == ("b-emit", "c-emit")
    assert etat.total == 3


def test_un_ensemble_VIDE_de_surfaces_LEVE_au_lieu_de_rendre_tout_vert() -> None:
    with pytest.raises(SansDiffusion):
        verdict({})


# ─────────────────────────── 3. THE PUBLISHED TEXT ───────────────────────────


def test_l_accuse_DIT_qu_il_n_est_pas_un_refus() -> None:
    texte = rendre(verdict({"a-emit": "bare"}))
    assert "This is NOT a refusal" in texte, texte
    assert "\U000026D4 a-emit — names NONE" in texte, texte


def test_l_accuse_ne_porte_PAS_la_phrase_d_avertissement_quand_tout_est_tamponne() -> None:
    texte = rendre(verdict({"a-emit": tampon(une_population())}))
    assert "This is NOT a refusal" not in texte, texte
    assert "1/1 surface(s)" in texte, texte


def test_le_refus_d_un_contrat_NU_nomme_le_remede_chez_l_EMETTEUR(tmp_path, capsys) -> None:
    contrat = tmp_path / "contrat.txt"
    contrat.write_text("a rule with no provenance\n", encoding="utf-8")
    assert bord.main(["--verifier", str(contrat)]) == 1
    sortie = capsys.readouterr().out
    assert "names NO population" in sortie, sortie
    assert "at the EMITTER" in sortie, sortie


def test_le_refus_d_un_contrat_PERIME_montre_le_TAMPON_LU(tmp_path, capsys) -> None:
    contrat = tmp_path / "contrat.txt"
    contrat.write_text(tampon(une_population()) + "\n", encoding="utf-8")
    assert bord.main(["--verifier", str(contrat)]) == 1
    sortie = capsys.readouterr().out
    assert "Stamp read" in sortie and UN_COMMIT in sortie, sortie


# ─────────────────── 4. THE PRODUCTION VALUE (not injected) ───────────────────


def test_l_ENSEMBLE_reel_des_surfaces_de_diffusion_est_gele() -> None:
    """A SET, never a count: a swap would leave "6" identical and mute."""
    assert bord.SURFACES == (
        "plan-emit",
        "skill-emit",
        "garde-emit",
        "plan-gate-emit",
        "rangement-emit",
        "public-mirror-emit",
    )


def test_les_surfaces_gelees_EXISTENT_TOUTES_dans_le_Makefile_reel() -> None:
    """Without this witness, a renamed target would drop out of the sweep with nothing turning red."""
    texte = (bord._racine() / "Makefile").read_text(encoding="utf-8")
    absentes = [cible for cible in bord.SURFACES if f"\n{cible}:" not in texte]
    assert not absentes, f"surfaces declared but absent from the Makefile: {absentes}"


def test_la_population_REELLE_de_ce_depot_porte_un_commit_de_40_caracteres() -> None:
    population = bord.population_du_depot(bord._racine())
    assert len(population.commit) == 40
    assert population.arbre in (PROPRE, MODIFIE)
    assert population.racine


def test_les_commits_connus_du_depot_REEL_contiennent_sa_propre_TETE() -> None:
    racine = bord._racine()
    connus = bord.commits_connus(racine)
    assert bord.population_du_depot(racine).commit in connus


def test_la_borne_de_l_histoire_se_trompe_du_cote_du_REFUS() -> None:
    """A bound of 1 knows only one commit: everything else becomes unknown, hence refused."""
    racine = bord._racine()
    connus = bord.commits_connus(racine, borne=1)
    assert len(connus) == 1
    assert perimee(une_population(commit=AUTRE_COMMIT), connus=connus) is not None


# ──────────────────── 2. THE RC + 5. THE PASSING CASE ────────────────────


def test_le_CAS_PASSANT_bout_en_bout_le_tampon_de_CE_depot_est_ACCEPTE(
    tmp_path, capsys, monkeypatch
) -> None:
    """Emit then verify: the refusing half does have a legitimate pass today."""
    racine = bord._racine()
    reelle = bord.population_du_depot(racine)
    # The working tree can be dirty; we are testing the COMMIT clause, so we stamp it clean.
    contrat = tmp_path / "contrat.txt"
    contrat.write_text(
        tampon(Population(reelle.racine, reelle.commit, PROPRE, reelle.emis_le)) + "\n",
        encoding="utf-8",
    )
    assert bord.main(["--verifier", str(contrat)]) == 0
    assert "Contract acceptable" in capsys.readouterr().out


def test_le_geste_TAMPON_imprime_une_ligne_relisible_et_rend_rc_0(capsys) -> None:
    assert bord.main(["--tampon"]) == 0
    ligne = capsys.readouterr().out
    relue = population_nommee(ligne)
    assert relue is not None and len(relue.commit) == 40


def test_un_contrat_ILLISIBLE_rend_rc_2_et_non_rc_1(tmp_path, capsys) -> None:
    """A missing file is an instrument failure, never "the contract is bad"."""
    assert bord.main(["--verifier", str(tmp_path / "never-written.txt")]) == 2
    assert "unreadable" in capsys.readouterr().err


def test_un_depot_SANS_GIT_rend_rc_2_sur_le_tampon_et_nomme_git(
    tmp_path, capsys, monkeypatch
) -> None:
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    assert bord.main(["--tampon"]) == 2
    erreur = capsys.readouterr().err
    assert "git rev-parse" in erreur, erreur
    assert "no population can be named" in erreur, erreur


def test_un_receveur_SANS_GIT_refuse_un_contrat_tamponne_en_disant_qu_il_n_a_RIEN_verifie(
    tmp_path, capsys, monkeypatch
) -> None:
    """**Written after a SURVIVING sabotage**, and it names what that cost.

    Replacing :func:`commits_connus`'s ``return frozenset()`` (git failing) with a bogus non-empty
    set left the suite GREEN: the contract was refused anyway, but **for the wrong reason** —
    "this commit is not in your history" instead of "your history could not be read". *A refusal
    that is right by accident sends you to repair the wrong organ*, and ``rc`` alone cannot tell
    them apart. This witness therefore pins down the SENTENCE.
    """
    contrat = tmp_path / "contrat.txt"
    contrat.write_text(tampon(une_population()) + "\n", encoding="utf-8")
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))  # not a git repo
    assert bord.commits_connus(tmp_path) == frozenset()
    assert bord.main(["--verifier", str(contrat)]) == 1
    assert "NOTHING was verified" in capsys.readouterr().out


def test_le_mode_PUBLICATION_rend_rc_0_meme_quand_aucune_surface_n_est_tamponnee(
    monkeypatch, capsys
) -> None:
    """The written clause: publish, never refuse — otherwise the gate is born red and
    un-greenable."""
    monkeypatch.setattr(
        bord, "emissions", lambda racine, cibles=bord.SURFACES: {c: "bare" for c in cibles}
    )
    assert bord.main([]) == 0
    sortie = capsys.readouterr().out
    assert "0/6" in sortie, sortie
    assert "This is NOT a refusal" in sortie, sortie


def test_le_mode_PUBLICATION_rend_rc_2_quand_l_instrument_n_a_rien_lance(
    monkeypatch, capsys
) -> None:
    monkeypatch.setattr(bord, "emissions", lambda racine, cibles=bord.SURFACES: {})
    assert bord.main([]) == 2
    assert "the instrument did not measure" in capsys.readouterr().err


def test_l_etiquette_du_module_est_celle_qu_on_croit() -> None:
    assert ETIQUETTE == "MNEMOSYNE-POPULATION"


def test_les_cibles_emit_REELLES_sont_TOUTES_jugees_ou_DECLAREES_exclues() -> None:
    """THE DIRECTION THAT WAS MISSING — real → declared, written after an isolated audit.

    The freeze was checked in only one direction (every declared surface does exist in the
    Makefile). Measured: the repo carried **11** ``*-emit`` targets, the freeze named 6 and the
    exclusion list named 4 — ``distill-emit-split`` lived between the two, neither judged nor
    declared excluded.

    *A freeze checked in only one direction leaves every NEW entry in the blind spot, silently.*
    This witness now turns red at the birth of the next ``-emit`` target, forcing its author to
    choose: it gets swept in, or its exclusion gets written down."""
    import re

    from mnemosyne.runtime.diffusion_run import EXCLUES_CAR_PARAMETREES, SURFACES

    from mnemosyne.runtime import diffusion_run as bord

    makefile = (bord._racine() / "Makefile").read_text(encoding="utf-8")
    reelles = set(re.findall(r"^([a-z0-9-]*emit[a-z0-9-]*):", makefile, re.MULTILINE))

    assert reelles, "no -emit target found: the instrument is broken, not the repo"
    non_classees = reelles - set(SURFACES) - set(EXCLUES_CAR_PARAMETREES)
    assert not non_classees, (
        f"-emit target(s) neither swept nor declared excluded: {sorted(non_classees)}. "
        "Add it to SURFACES if it runs with no argument, otherwise to EXCLUES_CAR_PARAMETREES."
    )
    # ...and the converse check: neither list names a target that no longer exists.
    fantomes = (set(SURFACES) | set(EXCLUES_CAR_PARAMETREES)) - reelles
    assert not fantomes, f"declaration(s) with no real target: {sorted(fantomes)}"
