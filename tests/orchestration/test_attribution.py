"""P2 -- witnesses for the arc-attribution registry (who holds which arc, at the EMITTER).

The FIVE surfaces: 1. the JUDGE · 2. the return code (`main`) · 3. the published TEXT · 4. the
PRODUCTION VALUE (real root, real plan, real posts) · 5. the PASSING CASE.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mnemosyne.production.attribution import (
    ARC_INCONNU,
    COLLISION,
    GENRES,
    GENRES_QUI_REFUSENT,
    TENUE_PERIMEE,
    Verdict,
    deja_pris,
    peut_attribuer,
    resume,
    verdicts,
)
from mnemosyne.runtime import attribution_run as bord

_PLAN = frozenset({"A", "B", "C"})
_FINIS = frozenset({"C"})


# ─────────────────────────────  1. THE JUDGE  ─────────────────────────────


def test_une_COLLISION_est_nommee_avec_LES_DEUX_tenants():
    trouves = verdicts({"A": ("chat-2", "chat-3")}, arcs_du_plan=_PLAN, arcs_finis=_FINIS)
    assert trouves == (Verdict(COLLISION, "A", ("chat-2", "chat-3")),)
    assert trouves[0].refuse


def test_un_ARC_INCONNU_est_une_revendication_sur_rien():
    trouves = verdicts({"ZZ": ("chat-9",)}, arcs_du_plan=_PLAN, arcs_finis=_FINIS)
    assert [(v.genre, v.arc) for v in trouves] == [(ARC_INCONNU, "ZZ")]
    assert trouves[0].refuse


def test_une_TENUE_PERIMEE_PUBLIE_et_ne_refuse_PAS():
    """4 of the 6 real holds are stale: refusing on this would refuse two-thirds of the
    registry on day one, for a fact that blocks nobody."""
    trouves = verdicts({"C": ("chat-1",)}, arcs_du_plan=_PLAN, arcs_finis=_FINIS)
    assert [(v.genre, v.arc) for v in trouves] == [(TENUE_PERIMEE, "C")]
    assert not trouves[0].refuse


def test_l_ORDRE_des_genres_met_les_REFUS_en_tete():
    trouves = verdicts(
        {"C": ("chat-1", "chat-2"), "ZZ": ("chat-9",)}, arcs_du_plan=_PLAN, arcs_finis=_FINIS
    )
    assert [v.genre for v in trouves] == [COLLISION, ARC_INCONNU, TENUE_PERIMEE], (
        "a false refusal placed first has already masked three real causes elsewhere in this repo"
    )


def test_deja_pris_EXCLUT_le_demandeur():
    """Without this exclusion, re-issuing the mandate of the chat that already holds the arc
    would be refused — an orchestrator's MOST common move."""
    assert deja_pris("A", {"A": ("chat-2",)}, a_qui="chat-2") == ()
    assert deja_pris("A", {"A": ("chat-2",)}, a_qui="chat-3") == ("chat-2",)
    assert deja_pris("B", {"A": ("chat-2",)}, a_qui="chat-3") == ()


def test_peut_attribuer_refuse_la_COLLISION_et_l_ARC_ABSENT():
    assert peut_attribuer(
        "A", a_qui="chat-3", tenants={"A": ("chat-2",)}, arcs_du_plan=_PLAN
    ) == Verdict(COLLISION, "A", ("chat-2", "chat-3"))
    assert peut_attribuer("ZZ", a_qui="chat-3", tenants={}, arcs_du_plan=_PLAN) == Verdict(
        ARC_INCONNU, "ZZ", ("chat-3",)
    )


def test_les_GENRES_sont_geles_en_ENSEMBLE_jamais_en_COMPTE():
    assert GENRES == frozenset({"collision", "arc_inconnu", "tenue_perimee"})
    assert GENRES_QUI_REFUSENT == frozenset({"collision", "arc_inconnu"}), (
        "a SWAP (stale-hold refuses / collision publishes) would leave the count identical "
        "and silent"
    )
    assert GENRES_QUI_REFUSENT < GENRES


# ─────────────────────────  5. THE PASSING CASE  ─────────────────────────


def test_un_registre_SAIN_ne_rougit_PAS():
    assert (
        verdicts({"A": ("chat-1",), "B": ("chat-2",)}, arcs_du_plan=_PLAN, arcs_finis=frozenset())
        == ()
    )
    assert (
        peut_attribuer("B", a_qui="chat-4", tenants={"A": ("chat-1",)}, arcs_du_plan=_PLAN) is None
    )
    assert (
        peut_attribuer("A", a_qui="chat-1", tenants={"A": ("chat-1",)}, arcs_du_plan=_PLAN) is None
    )
    assert resume((), arcs=11, tenus=2).startswith("\U00002705")


# ─────────────────────────  3. THE PUBLISHED TEXT  ─────────────────────────


def test_le_texte_porte_TOUJOURS_ses_DEUX_cardinaux():
    """A "healthy registry" read off zero arcs would look like a "healthy registry" read off
    eleven."""
    for texte in (
        resume((), arcs=11, tenus=6),
        resume((Verdict(COLLISION, "H", ("a", "b")),), arcs=11, tenus=6),
    ):
        assert "11 arc(s) in the plan" in texte and "6 declared held" in texte


def test_le_texte_SEPARE_ce_qui_refuse_de_ce_qui_publie():
    texte = resume(
        (Verdict(COLLISION, "H", ("chat-2", "chat-3")), Verdict(TENUE_PERIMEE, "C", ("chat-1",))),
        arcs=11,
        tenus=6,
    )
    assert "2 fact(s), 1 of which REFUSE(S)" in texte, "conflating the two would kill the distinction"
    assert "TWO holders declared (chat-2, chat-3)" in texte
    assert "stale hold" in texte


def test_les_TROIS_phrases_sont_DISTINCTES():
    phrases = {
        Verdict(g, "X", ("chat-1", "chat-2")).phrase
        for g in (COLLISION, ARC_INCONNU, TENUE_PERIMEE)
    }
    assert len(phrases) == 3
    assert all("chat-1, chat-2" in p for p in phrases), "a refusal must say WHO already holds the arc"


# ────────────────  4. THE PRODUCTION VALUE  ────────────────


def test_la_RACINE_de_production_designe_le_DEPOT_pas_system():
    assert (bord.RACINE / ".git").exists(), bord.RACINE
    assert (bord.RACINE / "CLAUDE.md").is_file(), bord.RACINE


def test_le_VRAI_plan_rend_des_arcs_et_des_arcs_FINIS():
    etat = bord.etat_du_plan(bord.RACINE)
    assert etat is not None, "zero arcs would be an instrument failure, never a green"
    arcs, finis = etat
    assert "A" in arcs and "B" in arcs, sorted(arcs)
    assert finis <= arcs, "a finished arc that is not an arc of the plan would be inconsistent"
    assert finis, "no finished arc: the stale-hold witness would have no real population to test"


def test_les_VRAIS_postes_se_lisent_SANS_degradation(capsys: pytest.CaptureFixture[str]):
    """Does the instrument really measure in production? `rc == 2` would mean it does not."""
    rc = bord.main([], racine=bord.RACINE)
    assert rc in (0, 1), capsys.readouterr()
    assert "arc(s) in the plan" in capsys.readouterr().out


# ─────────────────────────  2. THE RETURN CODE / THE DECISION  ─────────────────────────


def test_rc_1_sur_une_COLLISION_et_rc_0_sur_une_TENUE_PERIMEE(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    """The line `return 1 if any(v.refuse ...) else 0` is a surface of its own: a hard-coded
    `return 0`, or a refusal keyed on `trouves` instead of `v.refuse`, must turn this red."""
    monkeypatch.setattr(bord, "etat_du_plan", lambda _r: (frozenset({"A", "C"}), frozenset({"C"})))

    monkeypatch.setattr(bord, "_qui_tient_par_arc", lambda _d: ({"C": ("chat-1",)}, False))
    assert bord.main([], racine=bord.RACINE) == 0, "a stale hold PUBLISHES, it does not block"
    assert "stale hold" in capsys.readouterr().out

    monkeypatch.setattr(bord, "_qui_tient_par_arc", lambda _d: ({"A": ("x", "y")}, False))
    assert bord.main([], racine=bord.RACINE) == 1
    assert "TWO holders" in capsys.readouterr().out

    monkeypatch.setattr(bord, "_qui_tient_par_arc", lambda _d: ({"A": ("x",)}, False))
    assert bord.main([], racine=bord.RACINE) == 0, "the passing case, through the return code"


def test_rc_de_LA_PORTE_de_l_emetteur(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    monkeypatch.setattr(bord, "etat_du_plan", lambda _r: (frozenset({"A", "B"}), frozenset()))
    monkeypatch.setattr(bord, "_qui_tient_par_arc", lambda _d: ({"A": ("chat-2",)}, False))

    assert bord.main(["--arc", "A", "--pour", "chat-3"], racine=bord.RACINE) == 1
    assert "TWO holders" in capsys.readouterr().err

    assert bord.main(["--arc", "A", "--pour", "chat-2"], racine=bord.RACINE) == 0, "already theirs"
    assert bord.main(["--arc", "B", "--pour", "chat-3"], racine=bord.RACINE) == 0, "free"
    assert bord.main(["--arc", "ZZ", "--pour", "chat-3"], racine=bord.RACINE) == 1
    assert "ABSENT from the plan" in capsys.readouterr().err


def test_rc_2_quand_le_PLAN_est_introuvable(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    assert bord.main([], racine=tmp_path) == 2
    assert "NOT MEASURED" in capsys.readouterr().err


def test_rc_2_quand_UN_POSTE_est_ILLISIBLE(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    """A DEGRADED read is not a healthy registry: the arcs of the unreadable post are invisible,
    so a collision could exist without being seen."""
    monkeypatch.setattr(bord, "etat_du_plan", lambda _r: (frozenset({"A"}), frozenset()))
    monkeypatch.setattr(bord, "_qui_tient_par_arc", lambda _d: ({}, True))
    assert bord.main([], racine=bord.RACINE) == 2
    assert "UNREADABLE" in capsys.readouterr().err
