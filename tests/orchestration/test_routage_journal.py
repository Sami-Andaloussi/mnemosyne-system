"""C6 -- ROUTING IS VERIFIED AFTER THE FACT (per the project's plan documentation on self-sufficiency and routing).

The pure witnesses for :mod:`mnemosyne.production.routage_journal`. The edge (git, I/O) is tested
separately in `tests/orchestration/test_routage_journal_run.py` -- the same split as the rest of
the repo between `production/` and `runtime/`.
"""

from __future__ import annotations

from mnemosyne.production.plan_format import PlanItem
from mnemosyne.production.routage_journal import (
    Commit,
    construire_entree,
    journal,
    taux_de_reprise,
)

from _invariants import REPO_ROOT

# An item whose BOTH axes fall to "low" -> case "sous_agent". Short title (low volume),
# no *Obligation*, a *Fini quand* that contains a real command (cognition "low").
_ITEM_SOUS_AGENT = PlanItem(
    ident="Z1",
    status="fait",
    title="un item court",
    section="",
    line=1,
    detail=(),
    fields=(("fini_quand", '`grep -c "^verdict: TIENT" chemin/vers/verdict.md` rend 1'),),
)

# The same, but *Obligation* level 2 -> cognition "high", volume still "low"
# -> case "sous_agent_capable".
_ITEM_SOUS_AGENT_CAPABLE = PlanItem(
    ident="Z2",
    status="fait",
    title="un item court, obligation forte",
    section="",
    line=2,
    detail=(),
    fields=(
        ("fini_quand", "une phrase sans commande"),
        ("obligation", "niveau 2 -- une barriere reelle"),
    ),
)

# No *Obligation*, no command in *Fini quand* -> cognition None -> router abstains.
_ITEM_SANS_CASE = PlanItem(
    ident="Z3",
    status="fait",
    title="un item dont la cognition ne se derive pas",
    section="",
    line=3,
    detail=(),
    fields=(("fini_quand", "une phrase sans commande ni obligation"),),
)

# Not closed yet.
_ITEM_OUVERT = PlanItem(
    ident="Z4", status="a_faire", title="pas fini", section="", line=4, detail=()
)


def test_construire_entree_rend_None_quand_item_pas_ferme() -> None:
    commits = (Commit(type="feat", modele="Claude Sonnet 5"),)
    assert construire_entree(_ITEM_OUVERT, REPO_ROOT, commits) is None


def test_construire_entree_rend_None_quand_router_abstient() -> None:
    """*No ruling on a guess*: without proof of cognition, no case -- hence no entry,
    never a guessed case."""
    commits = (Commit(type="feat", modele="Claude Sonnet 5"),)
    assert construire_entree(_ITEM_SANS_CASE, REPO_ROOT, commits) is None


def test_construire_entree_rend_None_quand_aucun_commit_de_tour() -> None:
    """Commits exist but none is feat/fix/test -- orch and docs are not attempts by the
    producer, the absence of a round is not zero, it is an absence of evidence."""
    commits = (Commit(type="orch", modele="Claude Opus 5"), Commit(type="docs", modele=""))
    assert construire_entree(_ITEM_SOUS_AGENT, REPO_ROOT, commits) is None


def test_construire_entree_MORD_le_cas_passant_case_sous_agent() -> None:
    commits = (Commit(type="feat", modele="Claude Sonnet 5"),)
    entree = construire_entree(_ITEM_SOUS_AGENT, REPO_ROOT, commits)
    assert entree is not None
    assert entree.case == "sous_agent"
    assert entree.tours == 1
    assert entree.modele == "Claude Sonnet 5"
    assert entree.verdict == "fait"


def test_construire_entree_MORD_le_cas_passant_case_sous_agent_capable() -> None:
    commits = (Commit(type="feat", modele="Claude Opus 5"),)
    entree = construire_entree(_ITEM_SOUS_AGENT_CAPABLE, REPO_ROOT, commits)
    assert entree is not None
    assert entree.case == "sous_agent_capable"


def test_construire_entree_compte_SEULEMENT_feat_fix_test() -> None:
    """orch/plan/docs surround two REAL rounds -- the count must return 2, not 5."""
    commits = (
        Commit(type="orch", modele="Claude Opus 5"),
        Commit(type="feat", modele="Claude Sonnet 5"),
        Commit(type="docs", modele="Claude Sonnet 5"),
        Commit(type="fix", modele="Claude Sonnet 5"),
        Commit(type="plan", modele="Claude Opus 5"),
    )
    entree = construire_entree(_ITEM_SOUS_AGENT, REPO_ROOT, commits)
    assert entree is not None
    assert entree.tours == 2


def test_construire_entree_prend_le_modele_du_DERNIER_commit_NOMME() -> None:
    """The last commit that NAMES a model wins -- a commit with no Co-Authored-By (empty
    model) must not erase the last model actually found."""
    commits = (
        Commit(type="feat", modele="Claude Opus 5"),
        Commit(type="fix", modele="Claude Sonnet 5"),
        Commit(type="test", modele=""),
    )
    entree = construire_entree(_ITEM_SOUS_AGENT, REPO_ROOT, commits)
    assert entree is not None
    assert entree.modele == "Claude Sonnet 5"


def test_construire_entree_modele_inconnu_quand_AUCUN_commit_ne_le_nomme() -> None:
    commits = (Commit(type="feat", modele=""),)
    entree = construire_entree(_ITEM_SOUS_AGENT, REPO_ROOT, commits)
    assert entree is not None
    assert entree.modele == "inconnu"


def test_journal_ignore_les_items_NON_mesurables_garde_les_autres() -> None:
    items = (_ITEM_SOUS_AGENT, _ITEM_OUVERT, _ITEM_SANS_CASE, _ITEM_SOUS_AGENT_CAPABLE)
    commits_par_ident = {
        "Z1": (Commit(type="feat", modele="Claude Sonnet 5"),),
        "Z2": (Commit(type="feat", modele="Claude Opus 5"),),
        "Z3": (Commit(type="feat", modele="Claude Sonnet 5"),),  # closed but case undetermined
        # Z4: open, no commit provided -- absent from the dict, never a KeyError
    }
    j = journal(items, REPO_ROOT, commits_par_ident)
    assert [e.ident for e in j] == ["Z1", "Z2"]


def test_taux_de_reprise_publie_les_QUATRE_cases_MEME_ABSENTES() -> None:
    """Same principle as `plan_ordre.repartition`: a case missing from the dict would read as
    "never measured", not as "zero" -- so ALWAYS all four, n=0 if nothing falls into it."""
    resultat = taux_de_reprise(())
    assert {r.case for r in resultat} == {
        "sous_agent",
        "le_parc",
        "sous_agent_capable",
        "le_chat_d_arc",
    }
    assert all(r.n == 0 and r.tours_moyen is None and r.cout_excessif is False for r in resultat)


def test_taux_de_reprise_tours_moyen_et_cout_excessif_MESURES_pas_devines() -> None:
    """Three `sous_agent` entries at 1 round, one `le_parc` entry at 5 rounds -- the global
    average is (1+1+1+5)/4 = 2. `le_parc` (5 > 2) is cout_excessif; `sous_agent` (1 < 2) is not."""
    entrees = (
        _entree("A1", "sous_agent", 1),
        _entree("A2", "sous_agent", 1),
        _entree("A3", "sous_agent", 1),
        _entree("A4", "le_parc", 5),
    )
    resultat = {r.case: r for r in taux_de_reprise(entrees)}
    assert resultat["sous_agent"].n == 3
    assert resultat["sous_agent"].tours_moyen == 1.0
    assert resultat["sous_agent"].cout_excessif is False
    assert resultat["le_parc"].n == 1
    assert resultat["le_parc"].tours_moyen == 5.0
    assert resultat["le_parc"].cout_excessif is True
    assert resultat["sous_agent_capable"].n == 0
    assert resultat["sous_agent_capable"].cout_excessif is False


def _entree(ident: str, case: str, tours: int):
    from mnemosyne.production.routage_journal import EntreeJournal

    return EntreeJournal(ident=ident, case=case, modele="Claude Sonnet 5", tours=tours, verdict="fait")
