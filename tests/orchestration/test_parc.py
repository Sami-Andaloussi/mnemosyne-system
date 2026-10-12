"""C5 -- THE POOL: split the IN, assemble the OUT without routing it through the orchestrator
(a private planning doc; not part of this public mirror).

The pure witnesses for :mod:`mnemosyne.production.parc`. No edge (I/O, git, disk) to test
separately -- the whole module is two pure functions, exactly like the core of D1
(`plan_derive.py`): the disk belongs to whoever calls this module (`lot_emit.py`, E4), not here.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mnemosyne.production.parc import Assemblage, Lot, assembler, decouper
from mnemosyne.production.plan_registry import scan_plans


def test_decouper_une_sequence_VIDE_rend_un_tuple_VIDE() -> None:
    assert decouper([], taille=3) == ()


def test_decouper_repartit_en_lots_de_la_taille_demandee() -> None:
    lots = decouper(["a", "b", "c", "d"], taille=2)
    assert lots == (
        Lot(indice=0, items=("a", "b")),
        Lot(indice=1, items=("c", "d")),
    )


def test_decouper_le_DERNIER_lot_porte_le_reste_jamais_vide() -> None:
    lots = decouper(["a", "b", "c", "d", "e"], taille=2)
    assert [lot.items for lot in lots] == [("a", "b"), ("c", "d"), ("e",)]
    assert all(lot.items for lot in lots)


def test_decouper_les_indices_sont_SEQUENTIELS_et_ZERO_bases() -> None:
    lots = decouper(range(10), taille=3)
    assert [lot.indice for lot in lots] == [0, 1, 2, 3]


def test_decouper_est_DETERMINISTE_meme_entree_meme_sortie() -> None:
    items = ["x", "y", "z", "w", "v"]
    assert decouper(items, taille=2) == decouper(items, taille=2)


def test_decouper_refuse_une_taille_INFERIEURE_A_UN() -> None:
    try:
        decouper(["a"], taille=0)
    except ValueError:
        pass
    else:
        raise AssertionError("taille=0 should have raised ValueError")


def test_decouper_ne_PERD_ni_ne_DUPLIQUE_aucun_item() -> None:
    items = list("abcdefghij")
    lots = decouper(items, taille=3)
    reconstruit = [item for lot in lots for item in lot.items]
    assert reconstruit == items


def test_assembler_COMPLET_quand_chaque_lot_rend_une_sortie() -> None:
    lots = decouper(["a", "b", "c"], taille=1)
    resultat = assembler(lots, lambda lot: lot.items[0].upper())
    assert resultat == Assemblage(complet=True, rendus=("A", "B", "C"), manquants=())


def test_assembler_REFUSE_des_QU_UN_SEUL_lot_manque() -> None:
    lots = decouper(["a", "b", "c"], taille=1)

    def lire(lot: Lot[str]) -> str | None:
        return None if lot.items[0] == "b" else lot.items[0]

    resultat = assembler(lots, lire)
    assert resultat.complet is False
    assert resultat.manquants == (1,)
    assert resultat.rendus == ("a", "c")


def test_assembler_NOMME_TOUS_les_manquants_pas_seulement_le_premier() -> None:
    lots = decouper(["a", "b", "c", "d"], taille=1)

    def lire(lot: Lot[str]) -> str | None:
        return None if lot.items[0] in ("b", "d") else lot.items[0]

    resultat = assembler(lots, lire)
    assert resultat.manquants == (1, 3)


def test_assembler_une_sortie_VIDE_MAIS_RENDUE_n_est_PAS_un_manquant() -> None:
    lots = decouper(["a", "b"], taille=1)

    def lire(lot: Lot[str]) -> str:
        return ""  # falsy, but RETURNED -- not a None, so not a missing item

    resultat = assembler(lots, lire)
    assert resultat.complet is True
    assert resultat.manquants == ()
    assert resultat.rendus == ("", "")


def test_assembler_sur_AUCUN_lot_rend_COMPLET_vacuously() -> None:
    resultat = assembler((), lambda lot: "never called")
    assert resultat == Assemblage(complet=True, rendus=(), manquants=())


def test_assembler_APPELLE_lire_sortie_EXACTEMENT_une_fois_par_lot() -> None:
    lots = decouper(["a", "b", "c"], taille=1)
    appels: list[int] = []

    def lire(lot: Lot[str]) -> str:
        appels.append(lot.indice)
        return lot.items[0]

    assembler(lots, lire)
    assert appels == [0, 1, 2]


def test_assembler_les_rendus_PRESERVENT_l_ordre_des_lots_reussis() -> None:
    lots = decouper(["a", "b", "c", "d"], taille=1)

    def lire(lot: Lot[str]) -> str | None:
        return None if lot.items[0] == "a" else lot.items[0]

    resultat = assembler(lots, lire)
    assert resultat.rendus == ("b", "c", "d")


# SECOND POPULATION, GENUINELY DIFFERENT ("test outside the population" protocol): the 14
# witnesses above all run on hand-written string fixtures -- never on real `PlanItem`s, never on a
# source this module does not control. External Research's plan, read at its REAL root
# (`.../External Research/`, not `.../External Research/plan/` -- the error the orchestrator measured and
# retracted on 2026-08-16 09:4x), is that second population: a nested repo, written by a different
# process, never consulted while writing `parc.py`.
#
# WHAT THIS WITNESS DOES NOT REPLAY, AND WHY THAT IS A WRITTEN ADMISSION, NOT A HIDDEN DEBT: the
# "end to end" proof (emit -> disk -> 3 REAL agents dispatched -> assembly -> sabotage of one OUT ->
# NAMED refusal on the SAME real batch) was done ONCE, live, on 2026-08-16 09:5x -- a private
# session journal (not part of this public mirror) carries the three OUT files and their exact
# content. REPLAYING it on every `pytest` run would dispatch agents on every CI run, slow and
# non-deterministic: the pattern this repo has settled on (D75, D157) is to log the live proof ONCE
# and keep a FAST, DETERMINISTIC witness here against the SAME real population, with a controlled
# `lire_sortie`.
# What this witness therefore verifies, structurally: that `decouper`/`assembler` hold up against
# the REAL shape and content of External Research (heterogeneous idents, `*Produces*` sometimes empty -- F5/F6
# measured empty on 2026-08-16 -- never a fixture that assumes a field is always filled), not that
# agents ran (that is proven once, not on every run).
def _items_reels_externe_arc_f() -> tuple:
    racine = Path(__file__).resolve().parents[2]
    if not (racine / "projects" / "saas" / "External Research").is_dir():
        pytest.skip(
            "projects/saas/External Research absent on this machine (outside git tracking, D163) -- "
            "no second population available here, not an absence of measurement taken elsewhere"
        )
    reg = scan_plans(racine)
    projet = next(
        (p for p in reg.projects if str(p.plan_path).endswith("External Research/PLAN.md")), None
    )
    if projet is None or projet.reading is None:
        pytest.skip("External Research's root plan is not readable on this machine")
    items_f = tuple(i for i in projet.reading.items if i.ident.startswith("F"))
    if not items_f:
        pytest.skip("External Research's arc F is empty on this machine -- nothing to split")
    return items_f


def test_decouper_sur_le_lot_REEL_externe_arc_F_ne_perd_ni_ne_duplique_rien() -> None:
    items_f = _items_reels_externe_arc_f()
    lots = decouper(items_f, taille=3)
    reconstruit = tuple(item for lot in lots for item in lot.items)
    assert reconstruit == items_f
    assert all(lot.items for lot in lots)  # no empty batch, even the last one


def test_assembler_REFUSE_et_NOMME_sur_le_MEME_lot_REEL_externe_arc_F() -> None:
    """The sabotage half of the protocol, replayed against the real population -- not just the
    string fixtures above. Same batch as the previous test, `lire_sortie` CONTROLLED (no agent
    here, see the admission above): exactly one missing batch, and it must be NAMED, not just
    counted."""
    items_f = _items_reels_externe_arc_f()
    lots = decouper(items_f, taille=3)
    if len(lots) < 2:
        pytest.skip("fewer than 2 batches in the real population -- nothing to name as missing")
    indice_absent = lots[-1].indice

    def lire(lot: Lot) -> str | None:
        return None if lot.indice == indice_absent else f"seen {len(lot.items)} item(s)"

    resultat = assembler(lots, lire)
    assert resultat.complet is False
    assert resultat.manquants == (indice_absent,)
    assert len(resultat.rendus) == len(lots) - 1
