"""`make orphelins` -- the PURE judge (:mod:`mnemosyne.production.orphelins`).

The edge (parsing `mon_lot:`, `git log`) is tested separately
(`tests/orchestration/test_orphelins_run.py`) -- here only the declared/measured comparison,
injected, never discovered.
"""

from __future__ import annotations

from mnemosyne.production.orphelins import PARTIES, recenser, rendre


def test_un_fichier_NON_declare_par_PERSONNE_est_ORPHELIN() -> None:
    r = recenser(["a.py"], declarations={}, modeles={})
    assert len(r.fichiers) == 1
    assert r.fichiers[0].orphelin is True
    assert r.orphelins == r.fichiers
    assert r.declares == ()


def test_un_fichier_declare_par_UNE_partie_n_est_PAS_orphelin() -> None:
    r = recenser(["a.py"], declarations={"chat-2": frozenset({"a.py"})}, modeles={})
    assert r.fichiers[0].orphelin is False
    assert r.fichiers[0].declare_par == ("chat-2",)
    assert r.declares == r.fichiers
    assert r.orphelins == ()


def test_un_fichier_declare_par_DEUX_parties_est_une_COLLISION() -> None:
    r = recenser(
        ["a.py"],
        declarations={"chat-1": frozenset({"a.py"}), "chat-3": frozenset({"a.py"})},
        modeles={},
    )
    assert r.fichiers[0].declare_par == ("chat-1", "chat-3"), "alphabetical, deterministic sort"
    assert r.collisions == r.fichiers
    assert r.orphelins == (), "a collision is NOT an orphan -- two distinct faults"


def test_JAMAIS_COMMITTE_est_DISTINCT_de_ORPHELIN() -> None:
    """A file declared but without a measured model (just created, never committed) is NOT an
    orphan -- the two questions are independent, never conflated."""
    r = recenser(["a.py"], declarations={"chat-2": frozenset({"a.py"})}, modeles={})
    assert r.fichiers[0].orphelin is False
    assert r.fichiers[0].jamais_committe is True
    assert r.fichiers[0].modeles_mesures == ()


def test_un_fichier_committe_mais_NON_declare_est_orphelin_PAS_jamais_committe() -> None:
    r = recenser(["a.py"], declarations={}, modeles={"a.py": ("Claude Opus 5",)})
    assert r.fichiers[0].orphelin is True
    assert r.fichiers[0].jamais_committe is False


def test_ZERO_ECART_EST_ATTEIGNABLE_quand_les_QUATRE_parties_couvrent_tout() -> None:
    """The routing clause, word for word: "zero gap must be a REACHABLE result".
    A population where EVERY file is declared exactly once by one of the four parties must
    return ZERO orphans and ZERO collisions -- otherwise this module manufactures a floor that
    never goes down, exactly the defect E2 named for a different wall."""
    fichiers = ["a.py", "b.py", "c.py", "d.py"]
    declarations = {
        "chat-1": frozenset({"a.py"}),
        "chat-2": frozenset({"b.py"}),
        "chat-3": frozenset({"c.py"}),
        "orchestrateur": frozenset({"d.py"}),
    }
    r = recenser(fichiers, declarations, modeles={})
    assert r.orphelins == (), r.orphelins
    assert r.collisions == (), r.collisions
    assert len(r.declares) == 4


def test_recenser_TRIE_les_fichiers_et_DEDUPLIQUE() -> None:
    r = recenser(["b.py", "a.py", "a.py"], declarations={}, modeles={})
    assert [f.chemin for f in r.fichiers] == ["a.py", "b.py"]


def test_PARTIES_porte_les_QUATRE_sans_en_oublier_UNE() -> None:
    """The exact clause the one-off census missed: three chats are not enough."""
    assert set(PARTIES) == {"chat-1", "chat-2", "chat-3", "orchestrateur"}
    assert len(PARTIES) == 4


def test_rendre_NOMME_le_compte_ET_les_chemins_pas_seulement_un_total() -> None:
    r = recenser(
        ["seul_orphelin.py", "declare.py"],
        declarations={"chat-2": frozenset({"declare.py"})},
        modeles={},
    )
    texte = rendre(r)
    assert "1 orphan(s)" in texte
    assert "seul_orphelin.py" in texte
    assert "declare.py" not in texte, "a declared file has no business in a LEVEL 1 render"


def test_rendre_BORNE_la_liste_et_DIT_combien_elle_cache() -> None:
    fichiers = [f"orph{i}.py" for i in range(15)]
    r = recenser(fichiers, declarations={}, modeles={})
    texte = rendre(r, profondeur=5)
    assert "… and 10 more" in texte, texte


def test_rendre_sur_ZERO_orphelin_le_DIT_explicitement() -> None:
    r = recenser(["a.py"], declarations={"chat-2": frozenset({"a.py"})}, modeles={})
    texte = rendre(r)
    assert "No orphan:" in texte
