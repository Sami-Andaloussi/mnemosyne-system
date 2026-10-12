"""The EDGE of D5 (`plan_recul_run.py`) — same doctrine as `test_plancher_run.py`: the judge is
tested by its values (`test_plan_recul.py`), the edge by what it does when the world does not
answer, AND by what it returns on the REAL POPULATION — it is this second witness that proves D5's
*Fini quand* ("it triggers at least by July 22"), not a fixture that answers what is expected."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mnemosyne.production.plan_derive import Tour
from mnemosyne.runtime import plan_recul_run as plan_recul_run_mod
from mnemosyne.runtime.derive_run import RACINE_PRODUIT, est_produit
from mnemosyne.runtime.plan_recul_run import (
    balayage_reecriture_sibling,
    balayage_reecriture_git_sibling,
    commits_type_ident,
    declenchements_plancher,
    main,
    reecriture,
    refus_repete_retrait,
    signal_plancher,
    temoins_dates_par_ident,
    temoins_fichiers,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_PROJECTS_GIT_ABSENT = not (_REPO_ROOT / "projects/.git").exists()
_RETRAITS_LEDGER_ABSENT = not (
    _REPO_ROOT / "system" / "state" / "retraits_requests.jsonl"
).exists()
_SIBLING_STATE_ABSENT = not (
    _REPO_ROOT / "projects" / RACINE_PRODUIT / "state" / "audits" / "faits"
).is_dir()
_SIBLING_GIT_ABSENT = not (_REPO_ROOT / "projects" / RACINE_PRODUIT / ".git").exists()


def test_depot_absent_rend_None_jamais_une_liste_devinee(tmp_path: Path) -> None:
    assert declenchements_plancher(tmp_path) is None
    signal = signal_plancher(tmp_path)
    assert signal.declenche is None
    assert "NON MESUR" in signal.preuve


def test_aucun_commit_rend_None(tmp_path: Path) -> None:
    depot = tmp_path / "projects" / ".git"
    depot.mkdir(parents=True)
    assert declenchements_plancher(tmp_path) is None


def test_aucune_declaration_PRODUIT_rend_None_le_VRAI_chemin_de_code(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Same D75 fix as `test_plancher_run.py`: REAL rounds are injected via `monkeypatch` so
    execution really reaches `predicat_produit(tmp_path)`, not just `lire_tours` on an empty
    repo."""
    tours = [Tour(sha="a", date="2026-01-01", chemins=("saas/Sibling Research/core/x.py",), lignes=(10,))]
    monkeypatch.setattr(plan_recul_run_mod, "lire_tours", lambda *a, **k: tours)
    assert declenchements_plancher(tmp_path) is None
    signal = signal_plancher(tmp_path)
    assert signal.declenche is None
    assert "PRODUIT.md" in signal.preuve


def test_signal_calme_quand_mesure_mais_jamais_franchi(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tours = [Tour(sha="a", date="2026-01-01", chemins=("saas/Sibling Research/core/x.py",), lignes=(10,))]
    monkeypatch.setattr(plan_recul_run_mod, "lire_tours", lambda *a, **k: tours)
    signal = signal_plancher(tmp_path, est_produit=est_produit, x=30.0, n=1)
    assert signal.declenche is False
    assert signal.dates == ()


def test_signal_declenche_quand_le_rejeu_trouve_au_moins_un_jour_franc(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tours = [
        Tour(sha="a", date="2026-01-01", chemins=("saas/Sibling Research/core/x.py",), lignes=(1,)),
        Tour(sha="b", date="2026-01-02", chemins=("saas/Sibling Research/scripts/y.py",), lignes=(99,)),
    ]
    monkeypatch.setattr(plan_recul_run_mod, "lire_tours", lambda *a, **k: tours)
    signal = signal_plancher(tmp_path, est_produit=est_produit, x=30.0, n=1)
    assert signal.declenche is True
    assert signal.dates == ("2026-01-02",)


@pytest.mark.skipif(
    _PROJECTS_GIT_ABSENT, reason="the real D1/D3/D5 population is not present on this host"
)
def test_sur_la_POPULATION_REELLE_le_rejeu_declenche_AU_MOINS_au_22_juillet() -> None:
    """THE WITNESS FOR D5's *Fini quand* (signal 2): replayed over the sibling project's real history with
    validation `(c1)`'s FROZEN predicate, the list of clear-drop days must contain July 22 -- AND
    July 21 (31.7%, above the threshold) must NOT appear in it, or the detector triggers a day too
    early (or too often to say anything at all)."""
    resultats = declenchements_plancher(_REPO_ROOT, est_produit=est_produit)
    assert resultats is not None, "the real population must be measurable, not silent"
    dates = tuple(d.date for d in resultats)
    assert "2026-07-22" in dates, f"July 22 must trigger, replayed dates: {dates}"
    assert "2026-07-21" not in dates, f"July 21 (31.7%, above the threshold) must NOT trigger: {dates}"


@pytest.mark.skipif(
    _PROJECTS_GIT_ABSENT, reason="the real D1/D3/D5 population is not present on this host"
)
def test_signal_plancher_sur_la_POPULATION_REELLE_est_un_Signal_qui_declenche() -> None:
    signal = signal_plancher(_REPO_ROOT, est_produit=est_produit)
    assert signal.declenche is True
    assert "2026-07-22" in signal.dates


def test_main_publie_le_mandat_et_rend_zero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    rc = main([])
    assert rc == 0
    sortie = capsys.readouterr().out
    assert "MANDAT DE RECUL" in sortie
    assert "NON MESUR" in sortie  # no PRODUIT.md in tmp_path: the signal is named absent


# --------------------------------------------------------------------------------------------
# temoins_fichiers -- signal 3, witness-FILES HALF only
# --------------------------------------------------------------------------------------------


def test_temoins_fichiers_rend_None_quand_AUCUN_des_deux_dossiers_n_existe(tmp_path: Path) -> None:
    assert temoins_fichiers(tmp_path, "P6") is None


def test_temoins_fichiers_compte_sur_les_DEUX_dossiers_ENSEMBLE(tmp_path: Path) -> None:
    racine = tmp_path / "projects" / RACINE_PRODUIT / "state" / "audits"
    conditions = racine / "conditions"
    faits = racine / "faits"
    conditions.mkdir(parents=True)
    faits.mkdir(parents=True)
    (conditions / "X1--t1.md").write_text("a")
    (conditions / "X1--t2.md").write_text("a")
    (faits / "X1--t3.md").write_text("a")
    (faits / "AUTRE--t1.md").write_text("a")  # a different ident, must not count toward X1
    assert temoins_fichiers(tmp_path, "X1") == 3
    assert temoins_fichiers(tmp_path, "AUTRE") == 1


def test_temoins_fichiers_fonctionne_avec_UN_SEUL_des_deux_dossiers_present(tmp_path: Path) -> None:
    faits = tmp_path / "projects" / RACINE_PRODUIT / "state" / "audits" / "faits"
    faits.mkdir(parents=True)
    (faits / "X1--t1.md").write_text("a")
    assert temoins_fichiers(tmp_path, "X1") == 1


@pytest.mark.skipif(
    _SIBLING_STATE_ABSENT, reason="state/audits/faits from the real population is not present on this host"
)
def test_temoins_fichiers_sur_la_POPULATION_REELLE_rend_25_pour_P6() -> None:
    """THE FIGURE THE CORRECTED ITEM CITES (D5): 25 witness-files for `P6`, measured by hand
    with `ls` before writing this module -- this witness proves the CODE reproduces what the hand
    counted, not just that the code runs."""
    assert temoins_fichiers(_REPO_ROOT, "P6") == 25


# --------------------------------------------------------------------------------------------
# commits_type_ident / reecriture -- signal 3, the git-log proof (wired onto commits_par_ident,
# exposed by chat 2 -- this file CALLS it, it never reimplements it)
# --------------------------------------------------------------------------------------------


def test_commits_type_ident_rend_None_quand_le_depot_niche_est_illisible(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(plan_recul_run_mod, "commits_par_ident", lambda *a, **k: None)
    assert commits_type_ident(tmp_path, "P6") is None


def test_commits_type_ident_compte_les_commits_du_SEUL_ident_demande(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from mnemosyne.production.routage_journal import Commit

    faux = {
        "P6": (Commit(type="feat", modele="x"), Commit(type="fix", modele="x")),
        "AUTRE": (Commit(type="feat", modele="x"),),
    }
    monkeypatch.setattr(plan_recul_run_mod, "commits_par_ident", lambda *a, **k: faux)
    assert commits_type_ident(tmp_path, "P6") == 2
    assert commits_type_ident(tmp_path, "AUTRE") == 1


def test_commits_type_ident_rend_zero_pour_un_ident_ABSENT_du_dict_jamais_None(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The repo IS readable (`commits_par_ident` returns a real dict) but this ident never
    appears in it -- `0`, a real zero, never confused with `None` (unreadable repo)."""
    monkeypatch.setattr(plan_recul_run_mod, "commits_par_ident", lambda *a, **k: {})
    assert commits_type_ident(tmp_path, "JAMAIS_VU") == 0


def test_reecriture_publie_les_DEUX_preuves_SEPAREMENT_jamais_sommees(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from mnemosyne.production.routage_journal import Commit

    monkeypatch.setattr(
        plan_recul_run_mod, "commits_par_ident", lambda *a, **k: {"X1": (Commit("feat", "m"),)}
    )
    racine = tmp_path / "projects" / RACINE_PRODUIT / "state" / "audits" / "faits"
    racine.mkdir(parents=True)
    (racine / "X1--t1.md").write_text("a")
    (racine / "X1--t2.md").write_text("a")
    (racine / "X1--t3.md").write_text("a")
    r = reecriture(tmp_path, "X1")
    assert r.ident == "X1"
    assert r.commits == 1
    assert r.fichiers_temoins == 3
    assert r.commits != r.fichiers_temoins  # both populations stay distinct


def test_reecriture_chaque_preuve_est_None_INDEPENDAMMENT_de_l_autre(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The commit repo is unreadable AND no witness folder exists -- BOTH proofs must be `None`,
    each for ITS OWN reason, never merged into a single absence."""
    monkeypatch.setattr(plan_recul_run_mod, "commits_par_ident", lambda *a, **k: None)
    r = reecriture(tmp_path, "X1")
    assert r.commits is None
    assert r.fichiers_temoins is None


@pytest.mark.skipif(
    _PROJECTS_GIT_ABSENT, reason="the real D1/D3/D5 population is not present on this host"
)
def test_reecriture_sur_P6_REEL_confirme_ZERO_commits_et_25_temoins_JAMAIS_25_tout_court() -> None:
    """THE WITNESS THAT PROVES THE TWO PROOFS DO NOT SUBSTITUTE FOR EACH OTHER: on `P6`, the
    git-log proof is a REAL ZERO (no commit has ever named this item), not an absent measurement --
    and it coexists with 25 very real witness-files. A signal that summed the two would publish
    `25`, letting you believe part of it comes from commits that do not exist."""
    r = reecriture(_REPO_ROOT, "P6")
    assert r.commits == 0, f"P6 should have NO commit type(P6): -- measured: {r.commits}"
    assert r.fichiers_temoins == 25


# --------------------------------------------------------------------------------------------
# refus_repete_retrait -- signal 4, SCOPE = the withdrawal gate (H1) only, TWO proofs read via
# the REAL JSONL (never a reimplemented fold)
# --------------------------------------------------------------------------------------------


def _ecrire_ledger(chemin: Path, evenements: list[dict[str, object]]) -> None:
    chemin.parent.mkdir(parents=True, exist_ok=True)
    with chemin.open("w", encoding="utf-8") as f:
        for e in evenements:
            f.write(json.dumps(e) + "\n")


def _filed(id_: str, *, at: str = "2026-01-01T00:00:00+00:00") -> dict[str, object]:
    return {
        "v": 1, "kind": "filed", "id": id_, "items": ["Z1"], "motif": "test", "cout": "aucun",
        "requested_by": "test", "at": at,
    }


def _denied(id_: str, *, at: str = "2026-01-01T00:01:00+00:00") -> dict[str, object]:
    return {"v": 1, "kind": "denied", "id": id_, "at": at, "reason": "test", "by": "test"}


def _refused(id_: str, *, at: str = "2026-01-01T00:01:00+00:00") -> dict[str, object]:
    """The event from the NORMAL refusal GESTURE (`RetraitLedger.refuse()`) -- the one the old
    version of this signal did NOT count at all (chat-3 audit, 2026-08-16)."""
    return {"v": 1, "kind": "refused", "id": id_, "at": at, "reason": "test", "by": "test"}


def test_refus_repete_retrait_rend_None_quand_le_ledger_n_existe_pas_encore(tmp_path: Path) -> None:
    assert refus_repete_retrait(tmp_path) is None


def test_refus_repete_retrait_lit_le_VRAI_ledger_pour_denied_count(tmp_path: Path) -> None:
    """Builds a ledger with the EXACT event format `plan_retrait._replay` expects (not an
    invented fixture) -- this witness exercises the REAL read path (`RetraitLedger`), never a
    side reimplementation of the fold."""
    chemin = tmp_path / "system" / "state" / "retraits_requests.jsonl"
    _ecrire_ledger(
        chemin,
        [
            _filed("a"), _denied("a"),
            _filed("b"), _denied("b"), _denied("b"), _denied("b"), _denied("b"),
        ],
    )
    r = refus_repete_retrait(tmp_path)
    assert r is not None
    assert r.tentatives_bypass == 4
    assert r.cible_bypass == "b"


def test_refus_repete_retrait_ledger_existant_mais_VIDE_de_refus_rend_une_MESURE_pas_None(
    tmp_path: Path,
) -> None:
    chemin = tmp_path / "system" / "state" / "retraits_requests.jsonl"
    _ecrire_ledger(chemin, [_filed("a")])
    r = refus_repete_retrait(tmp_path)
    assert r is not None
    assert r.tentatives_bypass == 0
    assert r.cible_bypass == ""
    assert r.refus_geste == 0
    assert r.cible_refus == ""


def test_refus_repete_retrait_NE_CONFOND_JAMAIS_denied_ET_refused_SUR_LE_MEME_ID(
    tmp_path: Path,
) -> None:
    """A single id carries BOTH event types (2 `denied`, 3 `refused`) -- each count must stay
    EXACT, neither including the other. Without this witness, a read that merged them
    (```kind in ("denied", "refused")```) would still leave the OTHER TWO witnesses green (one
    uses only `denied`, the other only `refused`, never both on the same id) -- exactly the same
    trap as `mandat_de_recul`'s three-class partition (signal 2/3), fixed here before it bites in
    silence."""
    chemin = tmp_path / "system" / "state" / "retraits_requests.jsonl"
    _ecrire_ledger(
        chemin,
        [
            _filed("mixte"),
            _denied("mixte", at="2026-01-01T00:01:00+00:00"),
            _denied("mixte", at="2026-01-01T00:02:00+00:00"),
            _refused("mixte", at="2026-01-01T00:03:00+00:00"),
            _refused("mixte", at="2026-01-01T00:04:00+00:00"),
            _refused("mixte", at="2026-01-01T00:05:00+00:00"),
        ],
    )
    r = refus_repete_retrait(tmp_path)
    assert r is not None
    assert r.tentatives_bypass == 2, f"2 denied events, measured: {r.tentatives_bypass}"
    assert r.refus_geste == 3, f"3 refused events, measured: {r.refus_geste}"
    assert r.cible_bypass == "mixte"
    assert r.cible_refus == "mixte"


def test_refus_repete_retrait_REPRODUIT_LA_TROUVAILLE_DE_L_AUDIT_CHAT_3(tmp_path: Path) -> None:
    """THE WITNESS THAT PROVES THE FIX, by replaying EXACTLY the scenario the chat-3 audit
    ran: the same request refused 6 TIMES via the NORMAL gesture (`.refuse()`, never
    `.approuver_en_direct()`/`.appliquer_verifie()`, so NO `denied` event at all). The OLD version
    of this signal would have returned `fois=0, cible=""` -- indistinguishable from "never
    refused". The NEW one must name the 6 refusals on `refus_geste`, while confirming
    `tentatives_bypass=0` (no bypass attempt took place, and that is not the same question)."""
    chemin = tmp_path / "system" / "state" / "retraits_requests.jsonl"
    _ecrire_ledger(
        chemin,
        [_filed("six-refus"), *[_refused("six-refus", at=f"2026-01-01T00:0{n}:00+00:00") for n in range(6)]],
    )
    r = refus_repete_retrait(tmp_path)
    assert r is not None
    assert r.refus_geste == 6, f"6 refused events written, measured: {r.refus_geste}"
    assert r.cible_refus == "six-refus"
    assert r.tentatives_bypass == 0, "no denied event in this scenario -- not a bypass attempt"
    assert r.cible_bypass == ""


@pytest.mark.skipif(
    _RETRAITS_LEDGER_ABSENT, reason="the real withdrawal ledger is not present on this host"
)
def test_refus_repete_retrait_sur_la_POPULATION_REELLE_reproduit_le_denied_count_4() -> None:
    """THE FIGURE CITED (D5, field state) AND in `plan_recul.py`'s module docstring: a request
    refused 4 times (in the `denied_count` sense, a bypass attempt) during an H1 audit on
    2026-08-15 -- this witness proves the CODE reproduces what the real ledger carries, not just
    that it runs without raising."""
    r = refus_repete_retrait(_REPO_ROOT)
    assert r is not None
    assert r.tentatives_bypass == 4, (
        f"expected 4 (id da18c1b22975), measured: {r.tentatives_bypass} (target {r.cible_bypass!r})"
    )
    assert r.cible_bypass == "da18c1b22975"


# --------------------------------------------------------------------------------------------
# temoins_dates_par_ident / balayage_reecriture_sibling -- the sweep over K, settled by the
# orchestrator (2026-08-16): "you do not DECIDE the threshold, you DERIVE it"
# --------------------------------------------------------------------------------------------


def test_temoins_dates_par_ident_rend_None_quand_aucun_dossier_n_existe(tmp_path: Path) -> None:
    assert temoins_dates_par_ident(tmp_path) is None


def test_temoins_dates_par_ident_IGNORE_les_fichiers_SANS_champ_date(tmp_path: Path) -> None:
    """The real `state/audits/conditions/*.md` has NO `date:` field -- reproduced here: a file
    without this field is ABSENT from the result, never counted under an invented date."""
    dossier = tmp_path / "projects" / RACINE_PRODUIT / "state" / "audits" / "faits"
    dossier.mkdir(parents=True)
    (dossier / "X1--t1.md").write_text("---\nitem: X1\ntour: 1\nverdict: REFUTEE\n---\n")
    (dossier / "X1--t2.md").write_text("---\ndate: 2026-08-01\n---\n")
    par_ident = temoins_dates_par_ident(tmp_path)
    assert par_ident is not None
    assert par_ident["X1"] == ("2026-08-01",)  # t1 (no date) absent, t2 present


def test_temoins_dates_par_ident_accepte_les_DEUX_formats_de_date(tmp_path: Path) -> None:
    """A bare `date: 2026-08-04` AND a quoted `date: "2026-08-05"` -- the two real forms observed
    side by side on `state/audits/faits/P6--t*.md` before writing this module."""
    dossier = tmp_path / "projects" / RACINE_PRODUIT / "state" / "audits" / "faits"
    dossier.mkdir(parents=True)
    (dossier / "X1--t1.md").write_text("---\ndate: 2026-08-04\n---\n")
    (dossier / "X1--t2.md").write_text('---\ndate: "2026-08-05"\n---\n')
    par_ident = temoins_dates_par_ident(tmp_path)
    assert par_ident is not None
    assert sorted(par_ident["X1"]) == ["2026-08-04", "2026-08-05"]  # quotes stripped


def test_balayage_reecriture_sibling_rend_None_quand_aucun_dossier_n_existe(tmp_path: Path) -> None:
    assert balayage_reecriture_sibling(tmp_path) is None


@pytest.mark.skipif(
    _SIBLING_STATE_ABSENT, reason="state/audits/faits from the real population is not present on this host"
)
def test_balayage_reecriture_sibling_SEPARE_P6_du_RESTE_sur_la_POPULATION_REELLE() -> None:
    """THE WITNESS THAT ANSWERS THE ORCHESTRATOR'S RULING: "pick the value where the required
    case (P6) fires and the noise does not". Measured by hand before writing this module: P6
    carries 25 raw witnesses (~21 dateable), its closest rival (P13) only 5 -- this witness proves
    the CODE reproduces this separation on the REAL corpus, not an invented fixture."""
    balayage = balayage_reecriture_sibling(_REPO_ROOT)
    assert balayage is not None
    par_k = {b.k: b for b in balayage}
    # k=6: beyond the 2nd highest real count (P13=5) -- only P6 must fire, if its DATEABLE count
    # (faits/ only, conditions/ excluded) stays above 5.
    idents_a_6 = {d.ident for d in par_k[6].declenchements}
    assert "P6" in idents_a_6, f"P6 must trigger at k=6, triggers: {idents_a_6}"
    assert "P13" not in idents_a_6, f"P13 (5 witnesses) must NOT trigger at k=6: {idents_a_6}"


def test_balayage_reecriture_git_sibling_rend_None_quand_aucun_depot_n_existe(
    tmp_path: Path,
) -> None:
    assert balayage_reecriture_git_sibling(tmp_path) is None


@pytest.mark.skipif(
    _SIBLING_GIT_ABSENT, reason="the sibling project's nested repo is not present on this host"
)
def test_balayage_reecriture_git_sibling_SEPARE_le_PLUS_REECRIT_du_RESTE_sur_la_POPULATION_REELLE() -> (
    None
):
    """Answers the same ruling as the witness-files sweep, this time over the 119 REAL idents
    `commits_dates_par_ident` carries after the hyphen fix (C6, 2026-08-16) -- measured by hand
    before writing this witness: `A05-2` carries 20 commits, its closest rival (`A04-2`/`A10-4`)
    only 6-7. Signal 3's two halves each isolate THEIR OWN most-rewritten ident -- never the SAME
    one -- confirming they really do measure two different things, never summed."""
    balayage = balayage_reecriture_git_sibling(_REPO_ROOT)
    assert balayage is not None
    par_k = {b.k: b for b in balayage}
    idents_a_8 = {d.ident for d in par_k[8].declenchements}
    assert idents_a_8 == {"A05-2"}, f"A05-2 alone must trigger at k=8: {idents_a_8}"
