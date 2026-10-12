"""P9 -- the witnesses of the "declared closure <-> glyph flipped in the SAME commit" barrier.

The FIVE surfaces, and they are named because an isolated audit just measured that a battery of 19
green witnesses left 6 mutants alive: all of them interrogated the judge and the edge, **none read
the line that turns a verdict into a refusal**.

1. the JUDGE (pure verdicts) · 2. the RC (`main`) · 3. the PUBLISHED TEXT · 4. the PRODUCTION VALUE
(the real root, the real scope, the real commits) · 5. the PASSING CASE.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mnemosyne.production.fermeture_declaree import (
    VERBES_DE_FERMETURE,
    Bascule,
    bascules,
    ecarts,
    idents_declares,
    nomme,
    resume,
    statuts,
)
from mnemosyne.runtime import fermeture_declaree_run as bord

#: A REAL commit from this repo that declares `cloture(H5)` without flipping the glyph (`H5` stays
#: ``, verified against the bytes of `8dd7505f^`) -- the victim is drawn from PRODUCTION, never
#: fabricated.
REV_DECLARE_SANS_BASCULE = "8dd7505f"
#: A REAL commit that flips `B7` to `` without ever naming `B7` in its message.
REV_BASCULE_SANS_DECLARATION = "0f155dbc"
#: A REAL commit where both halves agree: `close(H5)` AND the glyph that flips.
REV_ACCORD = "9e99c4dd"


# ─────────────────────────────  1. THE JUDGE  ─────────────────────────────


def test_statuts_lit_les_puces_de_PREMIER_NIVEAU_et_ignore_la_prose():
    lignes = (
        "- **A1** \U00002705 a closed item",
        "  - **A2** \U00002B1C nested: not a first-level bullet",
        "- \U000026D4 my figure was wrong — this is PROSE, not an item",
        "- **B3** \U0001F504 in progress",
    )
    assert statuts(lignes) == {"A1": "fait", "B3": "en_cours"}


def test_bascules_ne_voit_QUE_les_idents_presents_DES_DEUX_cotes():
    avant = {"A1": "a_faire", "A2": "fait", "A3": "en_cours"}
    apres = {"A1": "fait", "A2": "fait", "A4": "fait"}
    assert bascules(avant, apres) == (Bascule("A1", "a_faire", "fait"),), (
        "A2 did not move, A3 disappeared (a removal), A4 appeared (no prior closed work)"
    )


def test_vers_ferme_distingue_une_FERMETURE_d_un_mouvement_quelconque():
    assert Bascule("A1", "a_faire", "fait").vers_ferme
    assert Bascule("A1", "en_cours", "clos").vers_ferme
    assert not Bascule("A1", "a_faire", "en_cours").vers_ferme, "no closed status"
    assert not Bascule("A1", "fait", "clos").vers_ferme, "already closed — this is not a closure"
    assert not Bascule("A1", "clos", "en_cours").vers_ferme, "reopening, judged elsewhere"


def test_idents_declares_ne_retient_QUE_les_verbes_de_fermeture():
    message = "close(H5): the review passes\n\nfeat(A1): something else\nCLOTURE(B6-bis) too"
    assert idents_declares(message) == frozenset({"H5", "B6-bis"})
    assert idents_declares("feat(A1): nothing to wrap up here") == frozenset()


def test_nomme_ne_confond_PAS_un_ident_avec_le_PREFIXE_de_son_voisin():
    assert nomme("closing B6-bis today", "B6-bis")
    assert not nomme("closing B6-bis today", "B6"), (
        "with \\b, B6 would match INSIDE B6-bis, and a flip of B6 would pass on its neighbor's "
        "mention"
    )
    assert nomme("close(B6): done", "B6")


def test_les_DEUX_sens_de_la_fleche_sont_juges():
    declaree = ecarts("cloture(H5): and the plan does not move", ())
    assert [(e.genre, e.ident) for e in declaree] == [("fermeture_declaree_sans_bascule", "H5")]

    basculee = ecarts("measurement: first real verdict", (Bascule("B7", "a_faire", "fait"),))
    assert [(e.genre, e.ident) for e in basculee] == [("bascule_sans_declaration", "B7")]


def test_l_ordre_des_ecarts_met_la_fermeture_DECLAREE_en_tete():
    trouves = ecarts(
        "cloture(H5) — and nothing here names the other item", (Bascule("B7", "a_faire", "fait"),)
    )
    assert [e.genre for e in trouves] == [
        "fermeture_declaree_sans_bascule",
        "bascule_sans_declaration",
    ]


def test_VERBES_DE_FERMETURE_est_gele_en_ENSEMBLE_jamais_en_COMPTE():
    assert VERBES_DE_FERMETURE == frozenset(
        {"close", "clos", "clot", "cloture", "clôture", "ferme", "fermeture"}
    ), "a SWAP of two verbs would leave the count identical and silent"


# ─────────────────────────  5. THE PASSING CASE  ─────────────────────────


def test_le_cas_LEGITIME_ne_rougit_PAS():
    """Without it, we only measure its capacity to refuse everything."""
    assert ecarts("close(H5): the review passes", (Bascule("H5", "a_faire", "fait"),)) == ()
    assert ecarts("docs: a commit that touches no plan", ()) == ()
    assert ecarts("plan: A1 moves to in-progress", (Bascule("A1", "a_faire", "en_cours"),)) == (), (
        "a movement that does not CLOSE has nothing to declare"
    )


# ─────────────────────────  3. THE PUBLISHED TEXT  ─────────────────────────


def test_le_texte_NOMME_TOUJOURS_la_population_comparee():
    """*An equality over zero pairs is true by construction* — a "no gap" without its cardinal
    number would be exactly that green."""
    texte = resume((Bascule("A1", "a_faire", "fait"), Bascule("A2", "a_faire", "en_cours")), ())
    assert "2 status movement(s)" in texte and "1 of them to a CLOSED status" in texte
    assert texte.startswith("\U00002705")


def test_le_texte_de_REFUS_nomme_l_ident_ET_le_geste_de_sortie():
    texte = resume(
        (Bascule("B7", "a_faire", "fait"),),
        ecarts("nothing", (Bascule("B7", "a_faire", "fait"),)),
    )
    assert texte.startswith("\U000026D4")
    assert "B7" in texte, "a refusal you cannot locate is barely better than silence"
    assert "name it in THIS commit's message" in texte, "the refusal must name the way out"
    assert "1 gap(s)" in texte


def test_les_DEUX_phrases_de_refus_sont_DISTINCTES():
    """Neutralizing half the message must turn red: the two kinds must not be confused, or a
    reader would not know which of the two meanings broke."""
    a = ecarts("cloture(H5)", ())[0].phrase
    b = ecarts("nothing", (Bascule("B7", "a_faire", "fait"),))[0].phrase
    assert a != b
    assert "DECLARES the closure" in a and "the plan does not carry it" in a
    assert "FLIPS to closed" in b and "the message does not name the item" in b


# ────────────────  4. THE PRODUCTION VALUE (real root, real commits)  ────────────────


def test_la_RACINE_de_production_designe_le_DEPOT_pas_system():
    """`parents[3]` would point to `system/`: that cost has already been paid twice elsewhere."""
    assert (bord.RACINE / ".git").exists(), bord.RACINE
    assert (bord.RACINE / "CLAUDE.md").is_file(), bord.RACINE


# TODO(public-mirror): needs human review — this test's fixtures assert against real
# docs/PLAN.md, docs/PLAN_COURANT.md and docs/plan/*.md paths, which are private-only planning
# documents not shipped in this mirror (checklist rule 2). The exact scope boundary these
# fixtures exercise is defined in `fermeture_declaree_run.dans_le_plan` (outside this
# sanitization batch), so a substitute path cannot be safely invented here without risking a
# silently wrong assertion.
def test_la_PORTEE_de_production_couvre_le_plan_REEL_et_rien_d_autre():
    assert bord.dans_le_plan("docs/plan/04-le-parallelisme.md")
    assert bord.dans_le_plan("docs/PLAN.md")
    assert bord.dans_le_plan("docs/PLAN_COURANT.md")
    assert not bord.dans_le_plan("docs/FORMAT_PLAN.md"), "documentation, not a plan"
    assert not bord.dans_le_plan("docs/plan/04-le-parallelisme.txt")
    assert not bord.dans_le_plan("system/lib/mnemosyne/production/plan_format.py")


def test_mesurer_lit_un_VRAI_commit_du_depot():
    mouvements = bord.mesurer(bord.RACINE, rev=REV_BASCULE_SANS_DECLARATION)
    assert mouvements is not None, "silent instrument"
    assert [(b.ident, b.avant, b.apres) for b in mouvements if b.vers_ferme] == [
        ("B7", "a_faire", "fait")
    ]


# ─────────────────────────  2. THE RC / THE DECISION  ─────────────────────────


def test_rc_1_sur_le_VRAI_commit_qui_DECLARE_sans_basculer(capsys: pytest.CaptureFixture[str]):
    rc = bord.main(["--rev", REV_DECLARE_SANS_BASCULE], racine=bord.RACINE)
    assert rc == 1, "a hardcoded `return 0` would pass here without turning red elsewhere"
    assert "H5" in capsys.readouterr().out


def test_rc_1_sur_le_VRAI_commit_qui_BASCULE_sans_declarer(capsys: pytest.CaptureFixture[str]):
    rc = bord.main(["--rev", REV_BASCULE_SANS_DECLARATION], racine=bord.RACINE)
    assert rc == 1
    assert "B7" in capsys.readouterr().out


def test_rc_0_sur_le_VRAI_commit_ou_les_deux_moities_s_ACCORDENT(
    capsys: pytest.CaptureFixture[str],
):
    rc = bord.main(["--rev", REV_ACCORD], racine=bord.RACINE)
    assert rc == 0, "the legitimate case must not turn red"
    assert capsys.readouterr().out.startswith("\U00002705")


def test_rc_2_quand_le_MESSAGE_est_introuvable(capsys: pytest.CaptureFixture[str]):
    """Zero measurement is NEVER a green: a silent instrument has its own code and its own
    sentence."""
    rc = bord.main([], racine=bord.RACINE)
    assert rc == 2
    assert "NOT MEASURED" in capsys.readouterr().out


def test_rc_2_quand_GIT_ne_repond_pas(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    msg = tmp_path / "COMMIT_EDITMSG"
    msg.write_text("close(A1): a readable message in a folder that is not a repo\n")
    rc = bord.main(["--message-file", str(msg)], racine=tmp_path)
    assert rc == 2, "a silent git ≠ a refusal ≠ a green"
    assert "`git` did not respond" in capsys.readouterr().out


def test_main_lit_le_MESSAGE_FILE_que_commit_msg_passe_en_dollar_1(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    """The real mode of the `commit-msg` hook: message taken from the file, diff taken from the
    INDEX."""
    msg = tmp_path / "COMMIT_EDITMSG"
    msg.write_text("cloture(ZZ9): nothing like that in the index\n")
    rc = bord.main(["--message-file", str(msg)], racine=bord.RACINE)
    assert rc == 1
    assert "ZZ9" in capsys.readouterr().out
