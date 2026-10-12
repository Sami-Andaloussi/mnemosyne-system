"""`make orphelins` -- the edge (:mod:`mnemosyne.runtime.orphelins_run`): parses the real
`mon_lot:` declarations, resolves `xxx/**` prefixes, measures `git log` on the REAL repo.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mnemosyne.runtime.orphelins_run import (
    _POSTE_PAR_PARTIE,
    _chemins_declares,
    _fichiers_reels,
    _resoudre,
    recensement,
    resume,
)

from _invariants import REPO_ROOT


def test_chemins_declares_lit_les_entrees_de_PREMIER_NIVEAU_seulement() -> None:
    texte = (
        "mon_lot:\n"
        "  - a.py\n"
        "  - b.py    \U00002696\U0000FE0F an annotation on the same line\n"
        "    indented annotation continuation, NOT an entry\n"
        "  - c.py\n"
        "pas_a_moi:\n"
        "  - d.py\n"
    )
    assert _chemins_declares(texte) == frozenset({"a.py", "b.py", "c.py"})


def test_chemins_declares_s_arrete_a_la_PROCHAINE_cle() -> None:
    """`pas_a_moi:` closes the section -- its entries are NOT declarations."""
    texte = "mon_lot:\n  - a.py\npas_a_moi:\n  - b.py\n"
    assert "b.py" not in _chemins_declares(texte)


def test_chemins_declares_rend_VIDE_sans_section_mon_lot() -> None:
    assert _chemins_declares("just some prose\nwith no structure\n") == frozenset()


def test_resoudre_un_chemin_LITTERAL_se_declare_LUI_MEME() -> None:
    reel = frozenset({"a.py", "b.py"})
    assert _resoudre(frozenset({"a.py"}), reel) == frozenset({"a.py"})


def test_resoudre_un_prefixe_GLOB_declare_TOUT_ce_qui_commence_par_lui() -> None:
    reel = frozenset({"dir/a.py", "dir/sub/b.py", "other/c.py"})
    assert _resoudre(frozenset({"dir/**"}), reel) == frozenset({"dir/a.py", "dir/sub/b.py"})


def test_resoudre_un_chemin_HORS_POPULATION_ne_matche_RIEN_jamais_une_erreur() -> None:
    """A `mon_lot:` may cite `docs/governance/**`, outside the `system/lib/` scope -- it must
    neither raise nor fabricate a phantom entry."""
    assert _resoudre(frozenset({"docs/governance/**"}), frozenset({"a.py"})) == frozenset()


def test_fichiers_reels_sur_un_depot_JETABLE(tmp_path: Path) -> None:
    (tmp_path / "system/lib/mnemosyne/production").mkdir(parents=True)
    (tmp_path / "system/lib/mnemosyne/runtime").mkdir(parents=True)
    (tmp_path / "system/lib/mnemosyne/production/a.py").write_text("x\n")
    (tmp_path / "system/lib/mnemosyne/runtime/b.py").write_text("x\n")
    cache = tmp_path / "system/lib/mnemosyne/production/__pycache__"
    cache.mkdir()
    (cache / "a.cpython-312.pyc").write_bytes(b"\x00")
    (tmp_path / "system/lib/mnemosyne/production/out_of_scope.txt").write_text("x\n")
    trouves = _fichiers_reels(tmp_path)
    assert trouves == frozenset(
        {"system/lib/mnemosyne/production/a.py", "system/lib/mnemosyne/runtime/b.py"}
    ), trouves


def test_POSTE_PAR_PARTIE_porte_les_QUATRE_fichiers_REELS() -> None:
    """The home the disposable census missed: `chat-0-orchestrateur.md` must be read as
    a SOURCE on the same footing as the three others."""
    for nom in _POSTE_PAR_PARTIE.values():
        chemin = REPO_ROOT / "docs" / "postes" / nom
        assert chemin.is_file(), f"{chemin} should exist -- the home is not where it is read from"


def test_resume_NOMME_son_incapacite_quand_le_dossier_est_ILLISIBLE(tmp_path: Path) -> None:
    texte = resume(tmp_path / "does-not-exist")
    assert "NOT MEASURED" in texte or "orphan" in texte.lower()


# --------------------------------------------------------------------------------------------
# THE REAL THING -- the proof that this module closes EXACTLY the hole from the 2026-08-16 census
#
# ONE SINGLE SHARED `recensement(REPO_ROOT)` (fixture `module`): every call scans `git log`
# over the whole real population (160+ files) -- redoing it per test would be the same cost paid
# N times for the same measurement, never a new proof.
# --------------------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def r_reel():
    return recensement(REPO_ROOT)


def test_sur_le_REEL_delegations_py_est_DESORMAIS_declare_par_ORCHESTRATEUR(r_reel) -> None:
    """THE proof this module exists to deliver: `production/delegations.py` is the example
    the routing cites -- declared in `chat-0-orchestrateur.md` since 2026-08-15 14:5x, and
    the three-party census rendered it "NOT DECLARED" forever. Here, not."""
    par_chemin = {f.chemin: f for f in r_reel.fichiers}
    cible = "system/lib/mnemosyne/production/delegations.py"
    assert cible in par_chemin, f"{cible} must be part of the real swept population"
    assert par_chemin[cible].declare_par == ("orchestrateur",), (
        f"delegations.py should be declared by the orchestrator alone; got "
        f"{par_chemin[cible].declare_par}"
    )


def test_sur_le_REEL_zero_COLLISION_un_fichier_un_auteur_tient(r_reel) -> None:
    """The "one file, one author" invariant measured as a FACT on the real mon_lot: declarations --
    not assumed to hold just because doctrine demands it."""
    assert r_reel.collisions == (), (
        f'"one file, one author" violated on {len(r_reel.collisions)} file(s): '
        f"{[f.chemin for f in r_reel.collisions]}"
    )


def test_sur_le_REEL_la_population_depasse_CENT_SOIXANTE_fichiers(r_reel) -> None:
    """Freezes a FLOOR, not an exact count -- a degenerate population otherwise (same discipline
    as C6: `>= 10`, never `== N`)."""
    assert len(r_reel.fichiers) >= 160, f"population too small: {len(r_reel.fichiers)} files"


def test_sabotage_UN_mon_lot_VIDE_fait_tomber_SES_declarations_a_ZERO(
    monkeypatch, tmp_path: Path
) -> None:
    """*I never assert the passing case.* If the `mon_lot:` parser were broken (always returning
    empty), this test must catch it: sabotages `_chemins_declares` so it never returns
    anything, and confirms that a normally-declared file becomes orphaned."""
    import mnemosyne.runtime.orphelins_run as orun

    monkeypatch.setattr(orun, "_chemins_declares", lambda _texte: frozenset())
    r = orun.recensement(REPO_ROOT)
    par_chemin = {f.chemin: f for f in r.fichiers}
    cible = "system/lib/mnemosyne/production/delegations.py"
    assert par_chemin[cible].orphelin is True, (
        "with the parser sabotaged, NO file should be declared any more -- "
        "if delegations.py stays declared, the sabotage did not bite"
    )
