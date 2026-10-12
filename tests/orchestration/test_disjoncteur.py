"""G2 -- witnesses for the CIRCUIT BREAKER (3rd negative verdict -> ANNOUNCE, 4th -> SPLIT).

The FIVE surfaces: 1. the JUDGE · 2. the RC (`main`) · 3. the published TEXT · 4. the PRODUCTION
VALUE (the real root, the real plan, the real `git log`) · 5. the PASSING CASE.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mnemosyne.production.disjoncteur import (
    GESTE_ANNONCER,
    GESTE_DECOUPER,
    GESTE_RIEN,
    GESTES,
    SEUIL_ANNONCE,
    SEUIL_DECOUPE,
    Etat,
    a_decouper,
    disjoncteur,
    geste_pour,
    ouverts,
    resume,
    serie_negative,
)
from mnemosyne.production.plan_format import PlanItem
from mnemosyne.production.routage_journal import Commit
from mnemosyne.runtime import disjoncteur_run as bord


def _c(*types: str) -> tuple[Commit, ...]:
    return tuple(Commit(type=t, modele="Claude Opus 5") for t in types)


def _item(ident: str, status: str = "a_faire") -> PlanItem:
    return PlanItem(ident, status, f"item {ident}", "", 1)


# ─────────────────────────────  1. THE JUDGE  ─────────────────────────────


def test_la_serie_est_celle_EN_COURS_jamais_le_MAXIMUM_historique():
    """A circuit breaker speaks about the present: `fix,fix,fix,feat` is NOT a streak of 3."""
    assert serie_negative(_c("fix", "fix", "fix", "feat")) == 0
    assert serie_negative(_c("feat", "fix", "fix", "fix")) == 3


def test_feat_et_test_REMETTENT_A_ZERO_docs_plan_orch_sont_TRANSPARENTS():
    assert serie_negative(_c("fix", "fix", "test", "fix")) == 1, "a fresh test resets it to zero"
    assert serie_negative(_c("fix", "fix", "orch", "docs", "plan", "fix")) == 3, (
        "an orchestrator narrating isn't an attempt: it doesn't break the streak"
    )


def test_les_deux_seuils_sont_lus_dans_le_BON_ORDRE():
    """Testing `SEUIL_ANNONCE` first would return "announce" for a streak of 7."""
    assert geste_pour(0) == GESTE_RIEN
    assert geste_pour(SEUIL_ANNONCE - 1) == GESTE_RIEN
    assert geste_pour(SEUIL_ANNONCE) == GESTE_ANNONCER
    assert geste_pour(SEUIL_DECOUPE) == GESTE_DECOUPER
    assert geste_pour(7) == GESTE_DECOUPER


def test_les_SEUILS_sont_ecrits_d_AVANCE_et_geles():
    """Half the mechanism: a threshold chosen at the moment it bites isn't a threshold."""
    assert (SEUIL_ANNONCE, SEUIL_DECOUPE) == (3, 4)
    assert SEUIL_ANNONCE < SEUIL_DECOUPE, "announcing must precede splitting"
    assert GESTES == frozenset({"rien", "annoncer", "decouper"}), (
        "frozen as a SET: swapping two labels would leave the count identical"
    )


def test_un_item_FERME_ne_declenche_JAMAIS():
    commits = {"H5": _c("feat", "fix", "fix", "fix", "fix", "fix")}
    assert disjoncteur((_item("H5", "fait"),), commits) == ()
    assert disjoncteur((_item("H5", "clos"),), commits) == ()
    assert disjoncteur((_item("H5", "a_faire"),), commits) == (Etat("H5", 5, 6, GESTE_DECOUPER),), (
        "the same item OPEN triggers: it's the status that decides, not the streak"
    )


def test_un_item_SANS_commit_connu_n_est_pas_un_ZERO_declenchant():
    assert disjoncteur((_item("ZZ9"),), {}) == ()


def test_a_decouper_ne_retient_QUE_le_second_seuil():
    etats = (Etat("A1", 3, 3, GESTE_ANNONCER), Etat("A2", 4, 4, GESTE_DECOUPER))
    assert a_decouper(etats) == (Etat("A2", 4, 4, GESTE_DECOUPER),)


def test_ouverts_compte_le_DENOMINATEUR_reellement_examine():
    items = (_item("A1"), _item("A2", "fait"), _item("A3", "en_cours"), _item("", "a_faire"))
    assert ouverts(items) == 2, "a closed item and an item with no key are not examined"


# ─────────────────────────  5. THE PASSING CASE  ─────────────────────────


def test_le_cas_LEGITIME_ne_declenche_PAS():
    """Without it, we would only be measuring its ability to refuse everything."""
    commits = {"A1": _c("feat", "fix", "feat", "fix"), "A2": _c("feat", "fix", "fix")}
    assert disjoncteur((_item("A1"), _item("A2")), commits) == ()
    assert resume((), juges=2).startswith("\U00002705")


# ─────────────────────────  3. THE PUBLISHED TEXT  ─────────────────────────


def test_le_texte_publie_TOUJOURS_le_denominateur_et_les_seuils():
    """"No trigger" on zero items reads exactly like "no trigger" on sixty."""
    texte = resume((), juges=21)
    assert "21 open item(s) examined" in texte
    assert "thresholds 3/4" in texte


def test_les_DEUX_phrases_de_declenchement_sont_DISTINCTES():
    texte = resume((Etat("A1", 3, 5, GESTE_ANNONCER), Etat("H5", 9, 10, GESTE_DECOUPER)), juges=21)
    assert "A1" in texte and "H5" in texte
    assert "ANNOUNCE it now" in texte, "the 'announce' half of the message"
    assert "SPLIT the item" in texte, "the 'split' half of the message"
    assert "9 negative verdicts in a row over 10 turn(s)" in texte, "the streak AND its population"
    assert "2 trigger(s)" in texte


# ────────────────  4. THE PRODUCTION VALUE  ────────────────


def test_la_RACINE_de_production_designe_le_DEPOT_pas_system():
    assert (bord.RACINE / ".git").exists(), bord.RACINE
    assert (bord.RACINE / "CLAUDE.md").is_file(), bord.RACINE


def test_le_VRAI_plan_de_ce_depot_est_lisible_et_NON_VIDE():
    items = bord.items_du_plan(bord.RACINE / "docs", "Mnémosyne")
    assert items, "reading zero items on the real plan would be an instrument failure, not a pass"
    assert ouverts(items) > 0, "a zero denominator would make everything pass by construction"


def test_le_disjoncteur_MORD_sur_le_VRAI_depot(capsys: pytest.CaptureFixture[str]):
    """Production, not a fixture: the real plan and the real `git log`. The repository today
    carries at least one open item in a negative streak — measured, not assumed."""
    rc = bord.main([], racine=bord.RACINE)
    assert rc in (0, 1), "2 would mean the instrument measures nothing in production"
    sortie = capsys.readouterr().out
    assert "open item(s) examined" in sortie
    assert "thresholds 3/4" in sortie


# ─────────────────────────  2. THE RC / THE DECISION  ─────────────────────────


def test_rc_2_quand_le_PLAN_est_introuvable(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    """Zero items examined is NEVER a pass."""
    rc = bord.main([], racine=tmp_path)
    assert rc == 2
    assert "NOT MEASURED" in capsys.readouterr().err


def test_rc_1_SEULEMENT_sur_le_second_seuil(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    """ The line `return 1 if a_decouper(...) else 0` is a surface in its own right: a hardcoded
 `return 0`, or a refusal keyed on `etats` instead of `a_decouper(etats)`, must turn red."""
    monkeypatch.setattr(bord, "items_du_plan", lambda *_a, **_k: (_item("A1"), _item("A2")))

    monkeypatch.setattr(
        bord, "commits_par_ident", lambda _r: {"A1": _c("feat", "fix", "fix", "fix")}
    )
    assert bord.main([], racine=bord.RACINE) == 0, (
        "an ANNOUNCE doesn't block — otherwise the 3rd and 4th thresholds would collapse into one"
    )
    assert "ANNOUNCE it now" in capsys.readouterr().out

    monkeypatch.setattr(
        bord, "commits_par_ident", lambda _r: {"A1": _c("feat", "fix", "fix", "fix", "fix")}
    )
    assert bord.main([], racine=bord.RACINE) == 1
    assert "SPLIT the item" in capsys.readouterr().out

    monkeypatch.setattr(bord, "commits_par_ident", lambda _r: {"A1": _c("feat", "fix")})
    assert bord.main([], racine=bord.RACINE) == 0, "the passing case, via the RC"


def test_rc_2_quand_GIT_est_muet(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    """A silent history would produce null streaks, i.e. a false pass."""
    monkeypatch.setattr(bord, "items_du_plan", lambda *_a, **_k: (_item("A1"),))
    monkeypatch.setattr(bord, "commits_par_ident", lambda _r: None)
    assert bord.main([], racine=bord.RACINE) == 2
    assert "NOT MEASURED" in capsys.readouterr().err


def test_items_du_plan_descend_dans_les_SOUS_PLANS(tmp_path: Path):
    """ **This witness closes a SURVIVING sabotage.** Replacing `plans` with `plans[:1]` in
 `items_du_plan` left the other 17 witnesses GREEN — because Mnémosyne's own plan is FLAT. On
 another project the same cut drew *21 steps out of 168*, `rc 0`, without a word; a TREE-shaped
 plan is therefore needed for the cut to turn red."""
    from mnemosyne.production.plan_format import plan_skeleton

    racine = tmp_path / "docs"
    (racine / "plan" / "sous").mkdir(parents=True)
    (racine / "PLAN.md").write_text(
        plan_skeleton("Door").replace("**A1**", "**A1**"), encoding="utf-8"
    )
    (racine / "plan" / "sous" / "PLAN.md").write_text(
        plan_skeleton("Sub").replace(
            "- **A1** \U00002B1C (le premier item)", "- **ZZ9** \U00002B1C sub-plan item"
        ),
        encoding="utf-8",
    )

    items = bord.items_du_plan(racine, "Trial")
    assert items is not None
    idents = {i.ident for i in items}
    assert "A1" in idents, "the door"
    assert "ZZ9" in idents, "the SUB-PLAN — keeping `plans[0]` would lose it silently"


def test_rc_2_quand_le_plan_est_LISIBLE_mais_VIDE(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    """ **This witness closes a CLASS, not a case.** A readable plan yielding zero items would
 publish "0 item(s) examined — no trigger": the falsest green there is. The `return ()` instead
 of `return None` sabotage in `items_du_plan` survived without it."""
    monkeypatch.setattr(bord, "items_du_plan", lambda *_a, **_k: ())
    assert bord.main([], racine=bord.RACINE) == 2
    assert "NOT MEASURED" in capsys.readouterr().err
