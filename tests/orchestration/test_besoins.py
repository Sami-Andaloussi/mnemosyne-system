"""Witnesses for `P8` — the needs channel (`production/besoins.py` + `runtime/besoins_run.py`).

The FIVE surfaces:

1. the JUDGE — :func:`probleme_au_depot`, :func:`probleme_a_trancher`, :func:`verdict` (pure);
2. the RC — ``main()``: 0 done · 1 judge refusal · 2 instrument failure;
3. the published TEXT — the queue with the pivots, the PIVOT order, the unreadable-items line;
4. the PRODUCTION VALUE — the real folder, the real template, the repository's REAL need;
5. the PASSING CASE — filing then deciding a legitimate need refuses NOTHING.
"""

from __future__ import annotations

import pytest

from mnemosyne.production.besoins import (
    OUVERT,
    STATUTS,
    TRANCHE,
    TYPES,
    Besoin,
    RefusDeDeposer,
    RefusDeTrancher,
    SansCanal,
    gabarit,
    probleme_a_trancher,
    probleme_au_depot,
    rendre,
    verdict,
)
from mnemosyne.production.frontmatter_status import field_of, status_of
from mnemosyne.runtime import besoins_run as bord

DEPOT_VALIDE = dict(
    type_="humain", titre="a title", question="a question", pivot="doing something else"
)


# ─────────────────────────────── 1. THE JUDGE ───────────────────────────────


def test_le_CAS_PASSANT_du_juge_un_depot_complet_ne_refuse_RIEN() -> None:
    assert probleme_au_depot(**DEPOT_VALIDE) is None


def test_un_PIVOT_vide_REFUSE_et_le_message_dit_pourquoi() -> None:
    refus = probleme_au_depot(**{**DEPOT_VALIDE, "pivot": "   "})
    assert refus is not None
    assert "PIVOT empty" in refus and "no stopping, no pausing" in refus


def test_un_TYPE_inconnu_REFUSE_en_nommant_le_vocabulaire() -> None:
    refus = probleme_au_depot(**{**DEPOT_VALIDE, "type_": "urgent"})
    assert refus is not None and "humain" in refus and "inter-arc" in refus


def test_un_TITRE_vide_REFUSE_parce_qu_il_est_l_adresse_permanente() -> None:
    refus = probleme_au_depot(**{**DEPOT_VALIDE, "titre": ""})
    assert refus is not None and "permanent address" in refus


def test_une_QUESTION_vide_REFUSE() -> None:
    assert probleme_au_depot(**{**DEPOT_VALIDE, "question": ""}) is not None


def test_un_besoin_INTER_ARC_sans_destinataire_REFUSE() -> None:
    refus = probleme_au_depot(**{**DEPOT_VALIDE, "type_": "inter-arc"})
    assert refus is not None and "addressed to nobody" in refus
    assert (
        probleme_au_depot(**{**DEPOT_VALIDE, "type_": "inter-arc", "destinataire": "arc B"}) is None
    )


def test_trancher_SANS_decision_REFUSE() -> None:
    ouvert = Besoin("d.md", type_="humain", statut=OUVERT)
    refus = probleme_a_trancher(ouvert, "  ")
    assert refus is not None and "is not a closure" in refus


def test_trancher_un_besoin_DEJA_tranche_REFUSE() -> None:
    refus = probleme_a_trancher(Besoin("d.md", type_="humain", statut=TRANCHE), "we're doing X")
    assert refus is not None and "already decided" in refus


def test_trancher_un_statut_HORS_VOCABULAIRE_REFUSE_au_lieu_de_basculer_a_l_aveugle() -> None:
    refus = probleme_a_trancher(Besoin("d.md", type_="humain", statut="en_cours"), "we're doing X")
    assert refus is not None and "outside the vocabulary" in refus


def test_le_CAS_PASSANT_du_juge_trancher_un_ouvert_avec_une_decision_ne_refuse_RIEN() -> None:
    assert probleme_a_trancher(Besoin("d.md", type_="humain", statut=OUVERT), "we're doing X") is None


def test_un_statut_INCONNU_est_NOMME_et_ne_disparait_PAS_du_verdict() -> None:
    """The defect measured in `signalements.py`: an unknown status disappears in silence."""
    etat = verdict(
        (
            Besoin("a.md", type_="humain", statut=OUVERT),
            Besoin("b.md", type_="humain", statut="mystere"),
            Besoin("c.md", type_="inconnu", statut=OUVERT),
        )
    )
    assert [b.adresse for b in etat.ouverts] == ["a.md"]
    assert [b.adresse for b in etat.illisibles] == ["b.md", "c.md"]
    assert etat.total == 3


def test_un_canal_VIDE_est_un_etat_legitime_contrairement_a_un_canal_ABSENT() -> None:
    etat = verdict(())
    assert etat.ouverts == () and etat.illisibles == () and etat.total == 0


def test_le_pivot_est_APLATI_pour_survivre_au_frontmatter() -> None:
    texte = gabarit(
        type_="humain",
        titre="t",
        question="q",
        pivot="line one\nline two",
        emetteur="chat-1",
        depose_le="2026-09-08",
    )
    assert 'pivot: "line one line two"' in texte, texte


def test_le_gabarit_ouvre_sur_le_statut_OUVERT_et_porte_la_section_decision() -> None:
    texte = gabarit(
        type_="humain", titre="t", question="q", pivot="p", emetteur="e", depose_le="2026-09-08"
    )
    assert f"status: {OUVERT}" in texte, texte
    # NOTE: the body's section heading stays in its original French form here — it is a
    # structural anchor the runtime edge's close-out gesture searches for; see the mirror note in
    # `besoins.gabarit`'s own source.
    assert "## La décision" in texte, texte


# ─────────────────────────── 3. THE PUBLISHED TEXT ───────────────────────────


def test_la_file_publie_le_PIVOT_de_chaque_besoin_ouvert() -> None:
    texte = rendre(
        verdict((Besoin("a.md", type_="humain", statut=OUVERT, pivot="doing B", titre="T"),))
    )
    assert "pivot: doing B" in texte, texte
    assert "a.md" in texte, texte


def test_un_pivot_ABSENT_est_dit_NON_DECLARE_jamais_laisse_blanc() -> None:
    texte = rendre(verdict((Besoin("a.md", type_="humain", statut=OUVERT, titre="T"),)))
    assert "(not declared)" in texte, texte


def test_la_file_NOMME_les_besoins_hors_vocabulaire_avec_leurs_valeurs() -> None:
    texte = rendre(verdict((Besoin("b.md", type_="humain", statut="mystere"),)))
    assert "outside the vocabulary" in texte and "status='mystere'" in texte, texte


def test_une_file_VIDE_dit_que_tout_a_ete_tranche() -> None:
    assert "everything filed has been decided" in rendre(verdict(()))


def test_un_besoin_INTER_ARC_publie_son_DESTINATAIRE() -> None:
    texte = rendre(
        verdict(
            (Besoin("a.md", type_="inter-arc", statut=OUVERT, destinataire="arc B", titre="T"),)
        )
    )
    assert "→ arc B" in texte, texte


# ─────────────────── 4. THE PRODUCTION VALUE (not injected) ───────────────────


def test_le_vocabulaire_reel_du_module_est_celui_qu_on_croit() -> None:
    assert TYPES == ("humain", "inter-arc")
    assert STATUTS == (OUVERT, TRANCHE)
    assert (OUVERT, TRANCHE) == ("ouvert", "tranche")


def test_le_dossier_reel_du_canal_est_docs_besoins() -> None:
    assert str(bord.DOSSIER) == "docs/besoins"


def test_le_canal_REEL_de_ce_depot_existe_et_porte_son_contrat() -> None:
    """A channel with no readable contract is just a folder; the README is what makes it a channel."""
    dossier = bord._racine() / bord.DOSSIER
    assert dossier.is_dir()
    assert (dossier / "README.md").is_file()


def test_le_canal_REEL_porte_au_moins_UN_besoin_et_il_est_LISIBLE() -> None:
    """An instrument that has never seen anything go through proves nothing.

    The very first need ever filed came back **outside the vocabulary** because the template used
    to write `statut:` while the shared home reads `status:` — found by real use, never by an
    audit. This witness freezes the one thing that would have caught it: that what the command
    WRITES, the production reader RE-READS.
    """
    trouves = bord.lire(bord._racine() / bord.DOSSIER)
    assert trouves, "the real channel is empty: the `status:` clause is proven by nothing"
    assert all(besoin.lisible for besoin in trouves), [
        (b.adresse, b.type_, b.statut) for b in trouves if not b.lisible
    ]


def test_le_compteur_pour_le_tick_est_FAIL_OPEN_sur_un_canal_absent(tmp_path) -> None:
    """The tick asks the question on every startup, including on a fresh clone."""
    assert bord.besoins_ouverts(tmp_path) == 0


def test_le_compteur_pour_le_tick_voit_le_canal_REEL() -> None:
    assert bord.besoins_ouverts(bord._racine()) >= 1


# ──────────────────── 2. THE RC + 5. THE PASSING CASE ────────────────────


def test_le_CAS_PASSANT_deposer_puis_trancher_rend_rc_0_deux_fois(
    tmp_path, capsys, monkeypatch
) -> None:
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    (tmp_path / "docs" / "besoins").mkdir(parents=True)

    assert (
        bord.main(
            [
                "--deposer",
                "--type",
                "humain",
                "--titre",
                "an arbitration call",
                "--question",
                "should we go with X or Y",
                "--pivot",
                "I'll do Z in the meantime",
                "--emetteur",
                "chat-1",
            ]
        )
        == 0
    )
    sortie = capsys.readouterr().out
    assert "PIVOT NOW" in sortie, sortie

    ecrit = next((tmp_path / "docs" / "besoins").glob("*.md"))
    assert status_of(ecrit) == OUVERT
    assert field_of(ecrit, "pivot") == "I'll do Z in the meantime"

    assert bord.main(["--trancher", str(ecrit), "--decision", "we're going with X"]) == 0
    assert status_of(ecrit) == TRANCHE
    texte = ecrit.read_text(encoding="utf-8")
    assert "we're going with X" in texte, "the decision must be RECORDED in the body"
    assert "tranche_le:" in texte
    assert ecrit.is_file(), "deciding never deletes (inv. 2)"


def test_un_depot_SANS_PIVOT_rend_rc_1_et_non_rc_0(tmp_path, capsys, monkeypatch) -> None:
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    (tmp_path / "docs" / "besoins").mkdir(parents=True)
    assert (
        bord.main(
            ["--deposer", "--type", "humain", "--titre", "t", "--question", "q", "--pivot", ""]
        )
        == 1
    )
    assert "PIVOT empty" in capsys.readouterr().err


def test_trancher_SANS_decision_rend_rc_1(tmp_path, capsys, monkeypatch) -> None:
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    dossier = tmp_path / "docs" / "besoins"
    dossier.mkdir(parents=True)
    ecrit = bord.deposer(dossier, emetteur="chat-1", **DEPOT_VALIDE)
    assert bord.main(["--trancher", str(ecrit), "--decision", ""]) == 1
    assert "is not a closure" in capsys.readouterr().err
    assert status_of(ecrit) == OUVERT, "a refusal must not have flipped ANYTHING"


def test_un_canal_ABSENT_rend_rc_2_et_non_une_file_vide(tmp_path, capsys, monkeypatch) -> None:
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    assert bord.main([]) == 2
    erreur = capsys.readouterr().err
    assert "does not exist" in erreur
    assert "this is NOT « no need is waiting »" in erreur, erreur


def test_lire_LEVE_sur_un_canal_absent(tmp_path) -> None:
    with pytest.raises(SansCanal):
        bord.lire(tmp_path / "never")


def test_le_README_du_canal_n_est_PAS_lu_comme_un_besoin(tmp_path) -> None:
    dossier = tmp_path / "besoins"
    dossier.mkdir()
    (dossier / "README.md").write_text("---\nstatus: ouvert\n---\ncontract\n", encoding="utf-8")
    assert bord.lire(dossier) == ()


def test_deposer_LEVE_le_refus_du_juge_AVANT_d_ecrire_quoi_que_ce_soit(tmp_path) -> None:
    dossier = tmp_path / "besoins"
    with pytest.raises(RefusDeDeposer):
        bord.deposer(dossier, emetteur="chat-1", **{**DEPOT_VALIDE, "pivot": ""})
    assert not dossier.exists(), "a refused filing must leave NO file behind"


def test_trancher_LEVE_sur_un_fichier_sans_section_decision(tmp_path) -> None:
    chemin = tmp_path / "faux.md"
    chemin.write_text("---\ntype: humain\nstatus: ouvert\n---\n\nnothing\n", encoding="utf-8")
    # NOTE: `match` stays in its original French form — it mirrors the exact section heading the
    # runtime edge's close-out gesture searches for (kept untranslated in `besoins.gabarit`'s own
    # output; see the mirror note there).
    with pytest.raises(RefusDeTrancher, match="La décision"):
        bord.trancher(chemin, "we're doing X", dossier=tmp_path)
