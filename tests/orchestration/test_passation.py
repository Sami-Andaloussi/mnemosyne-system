"""G10 -- the witnesses for the HANDOFF of a session that dies (a third party MEASURES, never relays).

The FIVE surfaces: 1. the JUDGE · 2. the RC (`main`) · 3. the published TEXT · 4. the PRODUCTION
VALUE (the real root, the real seats, the real `git status`) · 5. the PASSING CASE.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mnemosyne.production.passation import (
    DEMENTI_DURABILITE,
    DEMENTI_TRAVAIL,
    ETAT_EN_COURS,
    ETAT_RIEN,
    ETATS,
    GENRES,
    MESURE_ABSENTE,
    SOURCE_MESURE,
    SOURCE_PAROLE,
    SOURCES,
    SUR_PAROLE,
    Declaration,
    Mesure,
    juger,
    passation,
    resume,
)
from mnemosyne.runtime import passation_run as bord


def _d(etat: str = ETAT_RIEN, source: str = SOURCE_MESURE, pair: str = "chat-3") -> Declaration:
    return Declaration(pair=pair, etat=etat, source=source)


# ─────────────────────────────  1. THE JUDGE  ─────────────────────────────


def test_une_declaration_SUR_PAROLE_est_refusee_MEME_si_elle_est_VRAIE():
    """The rule is about the way of knowing, not the fact known: judging the contradiction first
    would let every exact word-of-mouth statement through — and it is exactly those that teach
    people to trust word of mouth."""
    mesure = Mesure(pair="chat-3")  # nothing open, nothing non-durable: the word of mouth was TRUE
    trouves = juger(_d(source=SOURCE_PAROLE), mesure)
    assert [v.genre for v in trouves] == [SUR_PAROLE]


def test_une_MESURE_ABSENTE_ou_IMPOSSIBLE_refuse_et_court_circuite_les_dementis():
    """An impossible measurement and an empty measurement are two different statements."""
    assert [v.genre for v in juger(_d(), None)] == [MESURE_ABSENTE]
    assert [v.genre for v in juger(_d(), Mesure(pair="chat-3", prise=False))] == [MESURE_ABSENTE]
    assert [v.genre for v in juger(_d(source=SOURCE_PAROLE), None)] == [SUR_PAROLE, MESURE_ABSENTE]


def test_les_DEUX_dementis_sont_INDEPENDANTS_le_CHEMIN_et_la_DURABILITE():
    """*True of the PATH, false of the DURABILITY* — another project's exact error, and only the second half
    would have caught it."""
    chemin_seul = Mesure(pair="chat-3", items_ouverts=("H5",))
    durabilite_seule = Mesure(pair="chat-3", non_durables=("a.py",))
    assert [v.genre for v in juger(_d(), chemin_seul)] == [DEMENTI_TRAVAIL]
    assert [v.genre for v in juger(_d(), durabilite_seule)] == [DEMENTI_DURABILITE]
    les_deux = Mesure(pair="chat-3", items_ouverts=("H5",), non_durables=("a.py",))
    assert [v.genre for v in juger(_d(), les_deux)] == [DEMENTI_DURABILITE, DEMENTI_TRAVAIL]


def test_les_dementis_ne_visent_QUE_l_etat_RIEN_A_TRAITER():
    """Declaring "in progress" with open items is the truth, not a gap."""
    mesure = Mesure(pair="chat-3", items_ouverts=("H5",), non_durables=("a.py",))
    assert juger(_d(etat=ETAT_EN_COURS), mesure) == ()


def test_passation_juge_TOUTES_les_declarations_dans_leur_ordre():
    declarations = (_d(pair="chat-1"), _d(pair="chat-2", source=SOURCE_PAROLE))
    mesures = {"chat-1": Mesure("chat-1", non_durables=("x",)), "chat-2": Mesure("chat-2")}
    trouves = passation(declarations, mesures)
    assert [(v.pair, v.genre) for v in trouves] == [
        ("chat-1", DEMENTI_DURABILITE),
        ("chat-2", SUR_PAROLE),
    ]


def test_les_vocabulaires_sont_geles_en_ENSEMBLE_jamais_en_COMPTE():
    assert ETATS == frozenset({"rien_a_traiter", "en_cours", "bloque"})
    assert SOURCES == frozenset({"parole", "mesure"})
    assert GENRES == frozenset(
        {"sur_parole", "mesure_absente", "dementi_durabilite", "dementi_travail"}
    ), "swapping two labels would leave the count identical and silent"


# ─────────────────────────  5. THE PASSING CASE  ─────────────────────────


def test_une_passation_FONDEE_ne_rougit_PAS():
    """Without it, all we measure is its ability to refuse everything."""
    assert juger(_d(), Mesure(pair="chat-3")) == ()
    assert passation((_d(),), {"chat-3": Mesure(pair="chat-3")}) == ()
    assert resume((), declarations=3).startswith("\U00002705")


# ─────────────────────────  3. THE PUBLISHED TEXT  ─────────────────────────


def test_le_texte_porte_TOUJOURS_le_nombre_de_declarations_jugees():
    """"handoff sound" on zero declarations would read like "handoff sound" on three."""
    assert "3 peer declaration(s) judged" in resume((), declarations=3)
    assert "1 peer declaration(s) judged" in resume(
        juger(_d(), Mesure("chat-3", non_durables=("a",))), declarations=1
    )


def test_les_QUATRE_phrases_sont_DISTINCTES_et_portent_leur_PREUVE():
    mesure = Mesure("chat-3", items_ouverts=("H5", "H6"), non_durables=("a.py", "b.py", "c.py"))
    phrases = {v.genre: v.phrase for v in juger(_d(source=SOURCE_PAROLE), mesure)}
    assert set(phrases) == {SUR_PAROLE, DEMENTI_DURABILITE, DEMENTI_TRAVAIL}
    assert len(set(phrases.values())) == 3
    assert "a third party does not relay, they RE-MEASURE" in phrases[SUR_PAROLE]
    assert "3 path(s)" in phrases[DEMENTI_DURABILITE] and "a.py" in phrases[DEMENTI_DURABILITE]
    assert "2 item(s)" in phrases[DEMENTI_TRAVAIL] and "H5" in phrases[DEMENTI_TRAVAIL]
    assert "dated rumour" in juger(_d(), None)[0].phrase


def test_la_citation_des_preuves_est_TRONQUEE_mais_le_COMPTE_ne_l_est_pas():
    """A count that followed the truncation would lie about the scale."""
    mesure = Mesure("chat-3", non_durables=tuple(f"f{i}.py" for i in range(9)))
    phrase = juger(_d(), mesure)[0].phrase
    assert "9 path(s)" in phrase
    assert phrase.count(".py") == 4 and "…" in phrase


# ────────────────  4. THE PRODUCTION VALUE  ────────────────


def test_la_RACINE_de_production_designe_le_DEPOT_pas_system():
    assert (bord.RACINE / ".git").exists(), bord.RACINE
    assert (bord.RACINE / "CLAUDE.md").is_file(), bord.RACINE


def test_la_mesure_se_PREND_vraiment_sur_le_depot_REEL():
    """`prise=False` here would mean the instrument measures nothing in production."""
    mesure = bord.mesurer(bord.RACINE, "chat-3")
    assert mesure.prise, mesure
    assert mesure.pair == "chat-3"


def test_un_pair_INCONNU_du_registre_n_herite_d_AUCUN_item():
    """Open items are derived from the arcs the peer DECLARES holding, never from the whole plan —
    a peer holding nothing must not inherit its neighbours' items."""
    assert bord.mesurer(bord.RACINE, "chat-inexistant").items_ouverts == ()


def test_la_DURABILITE_reelle_ecarte_les_chemins_PARQUES():
    """The filter comes from `non_committe.est_parque` (the Stop hook's own judge), never from a
    second list written here — CLAUDE.md parks `system/config/` and `scripts/perso/`."""
    from mnemosyne.production.non_committe import est_parque

    mesure = bord.mesurer(bord.RACINE, "chat-3")
    assert not any(est_parque(c) for c in mesure.non_durables), mesure.non_durables


# ─────────────────────────  2. THE RC / THE DECISION  ─────────────────────────


def test_rc_1_SUR_PAROLE_sur_le_depot_REEL(capsys: pytest.CaptureFixture[str]):
    rc = bord.main(
        ["--pair", "chat-3", "--etat", ETAT_RIEN, "--source", SOURCE_PAROLE], racine=bord.RACINE
    )
    assert rc == 1, "a hardcoded `return 0` would pass here"
    assert "WORD OF MOUTH" in capsys.readouterr().out


def test_rc_0_sur_une_declaration_FONDEE(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    monkeypatch.setattr(bord, "mesurer", lambda _r, pair: Mesure(pair=pair))
    rc = bord.main(
        ["--pair", "chat-3", "--etat", ETAT_RIEN, "--source", SOURCE_MESURE], racine=bord.RACINE
    )
    assert rc == 0, "the legitimate case must not turn red"
    assert capsys.readouterr().out.startswith("\U00002705")


def test_rc_1_quand_la_mesure_DEMENT(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    monkeypatch.setattr(bord, "mesurer", lambda _r, pair: Mesure(pair=pair, non_durables=("a.py",)))
    rc = bord.main(
        ["--pair", "chat-3", "--etat", ETAT_RIEN, "--source", SOURCE_MESURE], racine=bord.RACINE
    )
    assert rc == 1
    assert "CONTRADICTED by DURABILITY" in capsys.readouterr().out


def test_rc_2_quand_la_mesure_n_a_PAS_PU_etre_prise(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    """Zero measurement is NEVER a green — and it is not an ordinary refusal either."""
    monkeypatch.setattr(bord, "mesurer", lambda _r, pair: Mesure(pair=pair, prise=False))
    rc = bord.main(
        ["--pair", "chat-3", "--etat", ETAT_RIEN, "--source", SOURCE_MESURE], racine=bord.RACINE
    )
    assert rc == 2
    assert "dated rumour" in capsys.readouterr().err


def test_rc_2_quand_AUCUN_pair_n_est_nomme(capsys: pytest.CaptureFixture[str]):
    # The sentence is hardcoded in `passation_run.py`'s own `main()`, not derived from
    # `passation.py`'s `resume()`/`Verdict.phrase`. Producer and assertion were translated in
    # the SAME pass, which is what keeps this pairing honest rather than green by construction.
    assert bord.main([], racine=bord.RACINE) == 2
    assert "no pair named" in capsys.readouterr().err


def test_la_mesure_est_IMPOSSIBLE_hors_depot(tmp_path: Path):
    """A missing half invalidates the WHOLE measurement: returning open items with a silent
    `git status` would give a handoff confirmed by only the half we could read."""
    assert bord.mesurer(tmp_path, "chat-3").prise is False


def test_la_mesure_est_IMPOSSIBLE_quand_GIT_SEUL_est_muet(monkeypatch: pytest.MonkeyPatch):
    """ **This witness closes a SURVIVING sabotage.** Outside the repo, both the plan AND `git`
 are missing: the measurement falls back to `prise=False` through the other half of the test,
 and removing `porcelain is None` left 20 witnesses GREEN. So it takes a READABLE plan and a
 MUTE `git` to turn the cut red — the missing half must invalidate the WHOLE measurement."""
    monkeypatch.setattr(bord, "_porcelain", lambda _r: None)
    mesure = bord.mesurer(bord.RACINE, "chat-3")
    assert mesure.prise is False, mesure
    assert mesure.items_ouverts == (), "a half-measurement must publish nothing at all"


def test_le_filtre_des_PARQUES_est_celui_du_hook_Stop_sur_une_population_FABRIQUEE(
    monkeypatch: pytest.MonkeyPatch,
):
    """The production witness above depends on the real tree's state; this one depends on nothing
    and keeps its bite even the day the tree is clean."""
    porcelain = (
        " M system/config/policy.toml\n"
        "?? scripts/perso/mon_script.sh\n"
        " M system/lib/mnemosyne/production/passation.py\n"
    )
    monkeypatch.setattr(bord, "_porcelain", lambda _r: porcelain)
    mesure = bord.mesurer(bord.RACINE, "chat-3")
    assert mesure.non_durables == ("system/lib/mnemosyne/production/passation.py",), mesure
