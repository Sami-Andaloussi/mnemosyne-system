"""H5 (line 5) -- the pure witnesses of :mod:`mnemosyne.production.fermeture_isolee`.

No edge (I/O, git) to test separately -- same split as `parc.py`/`orphelins.py`: the disk
belongs to `fermeture_isolee_run.py`, not here.
"""

from __future__ import annotations

from mnemosyne.production.fermeture_isolee import (
    FermetureSolitaire,
    fermetures_solitaires,
    identites_vues,
)
from mnemosyne.production.plan_format import PlanItem
from mnemosyne.production.routage_journal import Commit


def _item(ident: str, status: str) -> PlanItem:
    return PlanItem(ident=ident, status=status, title="x", section="", line=1)


def test_identites_vues_ignore_les_commits_SANS_trailer() -> None:
    commits = (Commit(type="feat", modele=""), Commit(type="fix", modele=""))
    assert identites_vues(commits) == frozenset()


def test_identites_vues_rend_l_ENSEMBLE_pas_un_compte() -> None:
    commits = (
        Commit(type="feat", modele="Claude Sonnet 5"),
        Commit(type="fix", modele="Claude Sonnet 5"),
        Commit(type="plan", modele="Claude Opus 5"),
    )
    assert identites_vues(commits) == frozenset({"Claude Sonnet 5", "Claude Opus 5"})


def test_fermetures_solitaires_ignore_les_items_OUVERTS() -> None:
    items = (_item("B1", "a_faire"), _item("B2", "en_cours"))
    assert fermetures_solitaires(items, {}) == ()


def test_fermetures_solitaires_NOMME_un_item_ferme_SANS_deuxieme_identite() -> None:
    items = (_item("B2", "fait"),)
    commits = {
        "B2": (
            Commit(type="feat", modele="Claude Opus 5"),
            Commit(type="feat", modele="Claude Opus 5"),
        )
    }
    resultat = fermetures_solitaires(items, commits)
    assert resultat == (FermetureSolitaire(ident="B2", modele="Claude Opus 5"),)


def test_fermetures_solitaires_N_INCLUT_PAS_un_item_avec_DEUX_identites() -> None:
    """THE GATE'S PASSING CASE, asserted -- a refusal function that never refuses anything
    looks correct until it is shown a real case with TWO identities."""
    items = (_item("C5", "fait"),)
    commits = {
        "C5": (
            Commit(type="feat", modele="Claude Sonnet 5"),
            Commit(type="plan", modele="Claude Opus 5"),
        )
    }
    assert fermetures_solitaires(items, commits) == ()


def test_fermetures_solitaires_NOMME_un_item_ferme_SANS_AUCUN_commit_connu() -> None:
    """No known commit = no identity seen = the same case as "a single identity" --
    documented in the docstring, verified here: `modele=None`, not an exception."""
    items = (_item("Z9", "clos"),)
    resultat = fermetures_solitaires(items, {})
    assert resultat == (FermetureSolitaire(ident="Z9", modele=None),)


def test_fermetures_solitaires_un_commit_SANS_trailer_ne_compte_PAS_comme_une_identite() -> None:
    items = (_item("B2", "fait"),)
    commits = {"B2": (Commit(type="feat", modele=""), Commit(type="feat", modele=""))}
    resultat = fermetures_solitaires(items, commits)
    assert resultat == (FermetureSolitaire(ident="B2", modele=None),)


def test_fermetures_solitaires_PRESERVE_l_ordre_du_plan() -> None:
    items = (_item("Z1", "fait"), _item("A1", "fait"), _item("M1", "fait"))
    resultat = fermetures_solitaires(items, {})
    assert [s.ident for s in resultat] == ["Z1", "A1", "M1"]


def test_fermetures_solitaires_sur_le_REEL_B2_est_NOMME() -> None:
    """A second population, GENUINELY different from the fixtures above (the "test outside the
    population" protocol): the REAL repo, where `B2` was closed by a SINGLE identity measured
    directly (`git log`, not a fixture) before this module was written -- 5 commits, all
    `Claude Opus 5`."""
    from pathlib import Path

    from mnemosyne.production.plan_registry import scan_plans
    from mnemosyne.runtime.routage_journal_run import commits_par_ident

    from _invariants import REPO_ROOT

    projet = next(
        p for p in scan_plans(REPO_ROOT).projects if p.plan_path.parent.name == "docs"
    )
    commits = commits_par_ident(Path(REPO_ROOT))
    assert commits is not None, "the real git history must be readable for this witness"
    resultat = fermetures_solitaires(projet.reading.items, commits)
    idents = {s.ident for s in resultat}
    assert "B2" in idents, "B2 (measured: 5 commits, all Claude Opus 5) must stay named"
