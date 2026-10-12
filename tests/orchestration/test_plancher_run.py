"""The RUNTIME EDGE of D3 (`plancher_run.py`) — the judge is tested by its values, the edge by what
it does when the world does not answer (the same doctrine as `test_derive_run.py`).

 **CORRECTION (D75 audit, 2026-08-15)**: two witnesses in the first version were not testing
what they claimed to. `test_les_tours_binaires_sont_EXCLUS…` re-implemented the filter in its own
body instead of calling `etat_plancher`/`resume` — it still passed with the production filter
removed. `test_aucune_declaration_PRODUIT_rend_None…` stopped at `lire_tours` returning `None`
(empty repo) before even reaching the `predicat_produit` branch it claimed to exercise. Both are
redone below to exercise the REAL code path, via `monkeypatch`.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import mnemosyne.runtime.plancher_run as pr
from mnemosyne.production.plan_derive import Tour
from mnemosyne.runtime import plancher_run as plancher_run_mod
from mnemosyne.runtime.derive_run import RACINE_PRODUIT, est_produit
from mnemosyne.runtime.plancher_run import DEPOT, etat_plancher, peut, resume


def test_depot_absent_rend_None_jamais_un_plancher_devine(tmp_path: Path) -> None:
    assert etat_plancher(tmp_path) is None
    assert peut("ouvrir_blindage", tmp_path) is None
    assert "NOT MEASURED" in resume(tmp_path, aujourdhui="2026-08-01")


def test_aucun_commit_rend_None_pas_un_plancher_devine(tmp_path: Path) -> None:
    depot = tmp_path / "projects" / ".git"
    depot.mkdir(parents=True)  # repo present but no commit -- lire_tours already returns None here
    assert etat_plancher(tmp_path) is None


def test_aucune_declaration_PRODUIT_rend_None_le_VRAI_chemin_de_code(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ Redone after the D75 audit: the first version stopped at `lire_tours` (empty repo)
 BEFORE reaching `predicat_produit` — it proved nothing about this specific branch. Here
 `lire_tours` is monkeypatched to return REAL turns (non-empty), so execution actually
 reaches `predicat_produit(tmp_path)` — which must return `None` since
 `tmp_path/projects/saas/reference-project/PRODUIT.md` does not exist."""
    tours = [Tour(sha="a", date="2026-01-01", chemins=("saas/reference-project/core/x.py",), lignes=(10,))]
    monkeypatch.setattr(plancher_run_mod, "lire_tours", lambda *a, **k: tours)
    assert etat_plancher(tmp_path) is None
    page = resume(tmp_path, aujourdhui="2026-08-01")
    assert "FLOOR NOT MEASURED" in page
    assert "PRODUIT.md" in page


@pytest.mark.skipif(
    not (Path(__file__).resolve().parents[2] / "projects/.git").exists(),
    reason="the real population is not present on this host",
)
def test_le_resume_NOMME_la_population_DISPARUE_plutot_que_deviner_un_checkbox() -> None:
    """ On the REAL repo: the sibling project migrated to its own repo on 2026-07-29 ("one project, one
 repo") -- `projects/.git` no longer carries ANY file under its root. This test originally
 tested "no PRODUIT.md declaration"; the sibling project HAS one today (external drift, logged), so the
 REAL reason `resume()` says NOT MEASURED has changed -- and it is more serious:
 `population_disparue` cuts BEFORE even reaching the PRODUIT.md question."""
    racine = Path(__file__).resolve().parents[2]
    page = resume(racine, aujourdhui="2026-07-29")
    assert "FLOOR NOT MEASURED" in page
    assert "moved away" in page
    assert str(racine / DEPOT) in page


def test_le_checkbox_RESTE_quand_la_population_est_VIVANTE(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ The branch opposite to the corrected defect (poste, 21:5x): if the repo read STILL
 carries the project, `population_disparue` must return `False` and the checkbox must keep
 displaying normally — a fix that switched the ratchet off EVERYWHERE would be worse than the
 defect."""
    tours = [
        Tour(sha=f"a{i}", date="2026-07-20", chemins=(f"{RACINE_PRODUIT}core/x{i}.py",), lignes=(10,))
        for i in range(5)
    ]
    monkeypatch.setattr(plancher_run_mod, "lire_tours", lambda *a, **k: tours)
    monkeypatch.setattr(plancher_run_mod, "population_disparue", lambda *a, **k: False)
    page = resume(tmp_path, aujourdhui="2026-07-20", est_produit=lambda chemin: True)
    assert "FLOOR NOT MEASURED" not in page
    assert "moved away" not in page
    assert "X=" in page and "N=" in page
    assert "day(s) measured" in page


@pytest.mark.skipif(
    not (Path(__file__).resolve().parents[2] / "projects/.git").exists(),
    reason="the real D1/D3 population is not present on this host",
)
def test_sur_la_POPULATION_REELLE_le_plancher_EST_franchi() -> None:
    """The full edge (git -> Day -> Floor), over the real 15-29 July window: the
    floor X=30%/N=1 must come out BREACHED, exactly as the corrected sweep established
    (22 July — see the audit correction in plancher.py for the full account)."""
    racine = Path(__file__).resolve().parents[2]
    plancher = etat_plancher(racine, est_produit=est_produit)
    assert plancher is not None, "the real population must be measured, not stay silent"
    assert plancher.franchi is True
    assert peut("ouvrir_blindage", racine, est_produit=est_produit) is False
    assert peut("ouvrir_produit", racine, est_produit=est_produit) is True
    assert peut("fermer", racine, est_produit=est_produit) is True


@pytest.mark.skipif(
    not (Path(__file__).resolve().parents[2] / "projects/.git").exists(),
    reason="the real D1/D3 population is not present on this host",
)
def test_le_DENOMINATEUR_BORNE_reproduit_le_79_8_pourcent_publie_du_15_juillet() -> None:
    """ THE WITNESS FOR THE AUDIT CORRECTION ITSELF: 15 July is an initial import of
 ALL of `projects/` (a single commit, 291,679 lines, of which 49,980 under the sibling project). A
 denominator not bounded to the project would read it at 13.7% (the artefact that misled the
 first derivation of N); the bounded denominator must read it at 79.8%, matching this
 repository's own design note on project lifecycles. If `borne_au_projet` disappears or
 breaks, THIS witness must be the first to turn red."""
    racine = Path(__file__).resolve().parents[2]
    plancher = etat_plancher(racine, est_produit=est_produit, x=30.0, n=11)  # n=11: the WHOLE window
    assert plancher is not None
    assert plancher.recentes[0] == pytest.approx(79.8, abs=0.1), (
        f"15 July must read ~79.8% (bounded denominator), not ~13.7% (artefact): "
        f"{plancher.recentes[0]}"
    )


@pytest.mark.skipif(
    not (Path(__file__).resolve().parents[2] / "projects/.git").exists(),
    reason="the real population is not present on this host",
)
def test_le_resume_sur_LE_PROJET_dit_NON_MESURE_MEME_avec_le_predicat_historique_INJECTE() -> None:
    """ This test used to assert that `resume()` published `X=30`/`N=1`/`BREACHED` on the sibling project's
 REAL population, historical predicate `(c1)` injected. Since the sibling project's migration (2026-07-29,
 INSIDE the frozen window), this is exactly the behaviour that poste (21:5x) closed:
 `population_disparue` cuts the publication of a checkbox, EVEN with an injected predicate —
 the fate of the repo read, not that of the predicate, decides. The proof that the raw
 calculation (X=30/N=1/BREACHED) stays correct and replayable lives in
 `test_sur_la_POPULATION_REELLE_le_plancher_EST_franchi`, which calls `etat_plancher`
 DIRECTLY — the `resume()` surface and the `etat_plancher` judge are no longer held to the
 same verdict, by construction (D3 stays true, D75: the page no longer lies)."""
    racine = Path(__file__).resolve().parents[2]
    page = resume(racine, aujourdhui="2026-07-29", est_produit=est_produit)
    assert "FLOOR NOT MEASURED" in page
    assert "moved away" in page
    assert "X=30" not in page, "a checkbox frozen forever must never display again"


def test_les_tours_binaires_sont_EXCLUS_par_le_VRAI_chemin_de_code(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ Redone after the D75 audit: the first version re-implemented the filter inside its own
 test body (a list comprehension identical to the production one) instead of calling
 `etat_plancher`/`resume` — it still passed if the PRODUCTION filter was removed. Here, a
 binary turn is injected via a monkeypatched `lire_tours`, and it is `etat_plancher` itself
 that must exclude it: if the production filter disappears, this test must turn red."""
    produit = "saas/Sibling Research/core/x.py"
    binaire = "saas/Sibling Research/core/y.png"
    tours = [
        Tour(sha="a", date="2026-01-01", chemins=(produit,), lignes=(100,)),
        # binary: lignes EMPTY while chemins is not -- must disappear from the series
        Tour(sha="b", date="2026-01-02", chemins=(binaire,), lignes=()),
    ]
    monkeypatch.setattr(plancher_run_mod, "lire_tours", lambda *a, **k: tours)
    plancher = etat_plancher(tmp_path, est_produit=est_produit, x=30.0, n=1)
    assert plancher is not None
    # only one measurable day (01-01, 100% product) -- the binary 01-02 produced NO Day,
    # neither at 0% (which would skew the floor) nor at all.
    assert plancher.recentes == (100.0,)


def test_racine_produit_pointe_bien_le_sibling() -> None:
    """Non-regression guard-rail: if `derive_run.RACINE_PRODUIT` changes one day, this module must
    follow automatically (direct import, no constant recopied here)."""
    assert RACINE_PRODUIT == "saas/Sibling Research/"


# ---- THE POPULATION THAT MOVED AWAY -- third cause of None, added 2026-09-08 -----------------


class TestPopulationDemenagee:
    """ THE TWO READERS OF THE SAME STATE CONTRADICTED EACH OTHER, AND IT WAS THE JUDGE THAT
 WAS WRONG.

 As measured on 2026-09-08: ``make plancher`` published **"FLOOR NOT MEASURED: the project
 has moved away"** while ``etat_plancher`` returned ``Plancher(franchi=False,
 recentes=(47.9,))`` — a figure drawn from a window whose current state is EMPTY. The
 ``Makefile`` nonetheless invites you to wire the refusal to :func:`peut`, which goes through
 ``etat_plancher`` and NEVER through ``resume``: *a caller that had followed the invitation
 would have wired a refusal to a dead measurement.* The guard existed, written and proven — it
 was placed on the reader that PUBLISHES, not on the one that JUDGES.
 """

    def test_l_etat_COURANT_se_TAIT_quand_la_population_a_demenage(self, monkeypatch) -> None:
        monkeypatch.setattr(pr, "population_disparue", lambda root: True)
        assert pr.etat_plancher(Path(".")) is None

    def test_peut_rend_None_donc_JAMAIS_un_faux_verdict(self, monkeypatch) -> None:
        """``None`` is not a refusal: it is "I don't know". The module says so itself, and
        it is the only honest answer over a population that has moved away."""
        monkeypatch.setattr(pr, "population_disparue", lambda root: True)
        for geste in ("ouvrir_blindage", "ouvrir_produit", "fermer"):
            assert pr.peut(geste, Path(".")) is None

    def test_le_REJEU_HISTORIQUE_n_est_PAS_bloque_par_l_etat_courant(self, monkeypatch) -> None:
        """ THE GUARD'S BOUNDARY, AND TWO WITNESSES FORCED IT. The first version ALSO blocked
 the replay of the historical validation `(c1)` -- but *a historical verdict is replayed on
 ITS OWN population, never on what the disk carries today*. The two replay witnesses fell,
 and they were right: the guard only holds for the CURRENT state."""
        monkeypatch.setattr(pr, "population_disparue", lambda root: True)
        racine = Path(__file__).resolve().parents[2]
        if not (racine / "projects/.git").exists():
            pytest.skip("the real D1/D3 population is not present on this host")
        assert pr.etat_plancher(racine, est_produit=est_produit) is not None

    def test_le_cas_PASSANT_une_population_PRESENTE_se_mesure(self, monkeypatch) -> None:
        """ Without it, a guard that ALWAYS returned None would pass the three witnesses above
 and the entire floor would go silent — *never assert only the refusing case.*"""
        monkeypatch.setattr(pr, "population_disparue", lambda root: False)
        racine = Path(__file__).resolve().parents[2]
        if not (racine / "projects/.git").exists():
            pytest.skip("the real D1/D3 population is not present on this host")
        assert pr.etat_plancher(racine, est_produit=est_produit) is not None
