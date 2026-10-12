# SPDX-License-Identifier: MIT
"""`G4` -- the EDGE: the caller probe (AST, disk) and extracting the module from `*Produit*`.

These witnesses exist because the edge is NEW code that touches the disk and parses free-form
prose: the two places where a measurement can lie without any pure test ever seeing it.
"""

from __future__ import annotations

from pathlib import Path

from mnemosyne.production.obligation import verdict_items
from mnemosyne.runtime.obligation_run import (
    _items_obligation,
    _module_produit,
    compter_appelants_runtime,
)

RACINE_REELLE = Path(__file__).resolve().parents[2]


# ------------------------------------------------------------------------------------------------
# THE CALLER PROBE -- the two EXACT reference points item G4 locks into the plan
# ------------------------------------------------------------------------------------------------


def test_la_sonde_rend_AU_MOINS_1_sur_plan_format_le_cas_CONNU_cable():
    """`G4`'s *Fini quand*: the probe must return `>= 1` for `plan_format` (7 known to the
    orchestrator; this particular measurement finds 5 by AST, direct from `runtime/` -- the hard
    requirement is `>= 1`, the `7` is only a landmark, not a target to reproduce to the exact
    number)."""
    n = compter_appelants_runtime("plan_format", RACINE_REELLE)
    assert n >= 1, f"plan_format must have at least 1 real caller, found {n}"


def test_la_sonde_mesure_plan_condition_REPRIS_par_carte_py_jamais_comme_PORTE():
    """**THIS WITNESS HAS ALREADY CHANGED TWICE IN ONE SESSION, AND THAT IS THE SIGNAL THAT
    MOVED ITS ASSERTION FROM `==` TO A `>=` FLOOR.** First `== 0` (true until commit `9d0fcb9`,
    `C3`: `plan_ordre.router()` imports `est_une_commande` to DERIVE the cognition axis). Then
    `== 4` (true until `runtime/orchestration_run.py` was added, `E2`: it imports `carte.py`,
    which already imports `plan_ordre.py`, which already imports `plan_condition.py` -- a
    TRANSITIVE import, zero line of `orchestration.py` touches `plan_condition`).

    **WHAT `compter_appelants_runtime` DOES NOT SEE, and this is a real limit, not a bug**: it
    measures the MODULE's reachability, never the USAGE of what it imports. A module picked up as
    a mere pure predicate elsewhere -- or reached by a chain of TRANSITIVE imports with no
    relation at all to its role -- becomes "called" exactly as if it were guarding a real gate.
    Checked by reading the code, not by guessing: `est_une_commande(texte) -> bool` is pure (no
    side effect, no refusal), the module's only other export is an internal self-test, and
    `carte.py` (the hub through which `orchestration.py` reaches it) contains NO call to
    `plan_condition` at all -- checked by grep, zero occurrences.

    **`C1` DOES NOT GO BACK UP to level 2.** And `carte.py` becomes an INCREASINGLY central
    module (B3, B4, E2, all on that same day): every new `runtime/*.py` that depends on it, even
    with no relation to `plan_condition`, will inflate this count by transitivity. **A floor, not
    an equality**: what matters is no longer the exact number, but that no future caller REFUSES
    anything through `plan_condition` -- a question only a reading of the code settles, never this
    count, whether with `==` or with `>=`."""
    n = compter_appelants_runtime("plan_condition", RACINE_REELLE)
    assert n >= 4, (
        f"plan_condition must stay reachable at least through the C3 chain (plan_ordre.router) -- "
        f"if this floor is no longer reached, something has REGRESSED (not just moved): found {n}."
    )


def test_la_sonde_est_INDIFFERENTE_a_un_module_qui_n_existe_pas():
    """A per-measurement guarantee that raises kills the batch (`G4` is level 1, it must never
    raise) -- an unknown module must return 0, not an exception."""
    assert compter_appelants_runtime("ce_module_n_existe_nulle_part_xyz", RACINE_REELLE) == 0


def test_la_sonde_est_scopee_a_RUNTIME_pas_a_PRODUCTION(tmp_path: Path):
    """The perimeter is DECLARED, not assumed: an import from `production/` alone, when NO
    `runtime/` file exists yet to seed a chain, must NOT count. `runtime/` stays the ONLY entry
    point; the TRANSITIVE closure once an entry point exists is covered by
    `test_la_sonde_SUIT_la_chaine_PRODUCTION_vers_PRODUCTION_jusqu_a_runtime` below (fixed on
    2026-08-15: this was the false positive on `B1`/`plan_ordre`, found by the orchestrator)."""
    lib = tmp_path / "system" / "lib" / "mnemosyne"
    (lib / "production").mkdir(parents=True)
    (lib / "runtime").mkdir(parents=True)
    (lib / "production" / "cible.py").write_text("X = 1\n", encoding="utf-8")
    (lib / "production" / "voisin.py").write_text(
        "from .cible import X\n", encoding="utf-8"
    )  # imports ONLY from production/, and NOTHING under runtime/ exists yet -- 0
    assert compter_appelants_runtime("cible", tmp_path) == 0
    (lib / "runtime" / "bord.py").write_text("from ..production.cible import X\n", encoding="utf-8")
    assert compter_appelants_runtime("cible", tmp_path) == 1


def test_la_sonde_SUIT_la_chaine_PRODUCTION_vers_PRODUCTION_jusqu_a_runtime(tmp_path: Path):
    """**The 2026-08-15 false positive, reproduced in miniature.** `B1` (`plan_ordre.py`) is
    genuinely reached via `production/carte.py` -> `runtime/carte_run.py`, and the DIRECT-ONLY
    probe missed it -- `cible` here, reached ONLY through `intermediaire`, must now count as soon
    as `intermediaire` has a `runtime/` entry point, even with no direct import of `cible` from
    `runtime/`."""
    lib = tmp_path / "system" / "lib" / "mnemosyne"
    (lib / "production").mkdir(parents=True)
    (lib / "runtime").mkdir(parents=True)
    (lib / "production" / "cible.py").write_text("X = 1\n", encoding="utf-8")
    (lib / "production" / "intermediaire.py").write_text(
        "from .cible import X\n", encoding="utf-8"
    )
    (lib / "runtime" / "bord.py").write_text(
        "from ..production.intermediaire import X\n", encoding="utf-8"
    )  # imports intermediaire, NEVER cible directly
    assert compter_appelants_runtime("cible", tmp_path) >= 1, (
        "cible is reached via intermediaire -> bord, a production/production/runtime chain"
    )


def test_la_sonde_atteint_plan_ordre_TRANSITIVEMENT_via_carte_le_cas_reel_B1():
    """**A REAL reference, not synthetic -- the exact case the orchestrator measured by hand
    on 2026-08-15.** `B1` (`production/plan_ordre.py`) is CLOSED and genuinely exercised on every
    `make carte`, via `production/carte.py:36` (`from .plan_ordre import PlanOrdre, ...`) then
    `runtime/carte_run.py`. The direct-only version of the probe returned 0 here and published
    `B1` as "a barrier nothing calls" on an item already closed. If this witness turns red, it is
    the probe that is wrong, not `B1`."""
    n = compter_appelants_runtime("plan_ordre", RACINE_REELLE)
    assert n >= 1, f"plan_ordre (B1) must be reached transitively via carte.py, found {n}"


# ------------------------------------------------------------------------------------------------
# EXTRACTING THE MODULE -- the founding false positive (`juge.py` cited as a SKILL name)
# ------------------------------------------------------------------------------------------------


def test_extraction_REFUSE_un_mot_NU_meme_si_un_fichier_du_MEME_NOM_existe():
    """**The founding false positive, found while calibrating against the REAL population.**
    Item `F1` cites `` `distillateur` / `juge` / `veilleur` `` -- three SKILL names, an analogy --
    and `production/juge.py` REALLY does exist. Without the `.py` requirement, "juge" would have
    resolved into a false positive: F1 would have been judged on a module it does not claim.

    *A text detector counts citations as instances* -- this one must NOT."""
    stems = frozenset({"juge", "distillateur", "veilleur"})
    texte = "sur le patron de `distillateur` / `juge` / `veilleur`"
    assert _module_produit(texte, stems) == (None, None), "a BARE word must never resolve a module"


def test_extraction_ACCEPTE_un_chemin_COMPLET_avec_py():
    stems = frozenset({"plan_format"})
    texte = "`system/lib/mnemosyne/production/plan_format.py` — `PlanItem` étendu"
    assert _module_produit(texte, stems) == ("plan_format", None)


def test_extraction_ACCEPTE_un_nom_NU_SUFFIXE_py():
    stems = frozenset({"plan_derive"})
    texte = "un bloc `produit:` dans la porte du plan, lu par `plan_derive.py`"
    assert _module_produit(texte, stems) == ("plan_derive", None)


def test_extraction_NOMME_un_module_qui_n_existe_PAS_ENCORE_sans_le_resoudre():
    """D5b audit: `C5` cites `` `production/parc.py` `` unambiguously -- the file simply does
    not exist YET. Conflating that with "names nothing" published a FALSE sentence. The second
    element of the pair carries the cited name; the first stays `None` -- no caller probe on a
    file that does not exist."""
    stems = frozenset({"plan_format"})
    assert _module_produit("`production/parc.py` — émettre N mandats", stems) == (None, "parc")


def test_extraction_rend_None_None_sur_un_champ_VIDE():
    assert _module_produit("", frozenset({"plan_format"})) == (None, None)


# ------------------------------------------------------------------------------------------------
# THE REAL POPULATION -- replayed against THIS repo's OWN plan
# ------------------------------------------------------------------------------------------------


def test_la_population_REELLE_distingue_les_QUATRE_etats_et_C1_est_HORS_SCOPE():
    """`C1` was demoted to level 1 BY THIS VERY AUDIT -- it must therefore come out as
    `hors_scope` here, not `sans_appelant`: the page must not re-accuse an item already fixed."""
    items = _items_obligation(RACINE_REELLE)
    assert items is not None, "the real plan must be readable from the repo's root"
    par_ident = {it.ident: it for it in items}
    assert len(items) >= 40, f"degenerate population: {len(items)} items read"
    assert "C1" in par_ident and not par_ident["C1"].niveau_2_ou_plus, (
        "C1 has been level 1 since its closure -- a level 2 here would be a STALE reading"
    )


def test_le_JUGE_lui_meme_tourne_sur_la_population_REELLE_pas_seulement_le_lecteur():
    """**Gap found while surveying this module's own scope (2026-08-16)**: the witness above
    checks ONLY `_items_obligation` (the READER) against the real thing -- `verdict_items` (the
    JUDGE, G4) had never run on anything but synthetic, hand-written `DeclarationItem`s. A reader
    proves the POPULATION; it proves nothing about the JUDGE that consumes it. Same class the
    survey found in `plancher_run.py`: a reassuringly-named test that does not exercise what it
    claims to exercise.

    **RE-READ AND FIXED on 2026-08-16 (the "12 reds" mandate), EXACTLY as the original anchor
    asked**: *"if `C5` moves into `cablees`, this test must be re-read before being fixed -- that
    would mean someone wired up `parc.py`, good news"*. Someone did -- checked independently, not
    taken on the judge's own output alone: `git log` carries commit `09c3d95` (*"parc is WIRED UP
    in lot_emit"*), and `lot_emit.py` now imports
    `from .parc import Assemblage, Lot, assembler, decouper`. **`C5` now anchors `cablees`, not
    `sans_appelant`.**

    **And `sans_appelant` is now EMPTY on the real population** (measured, not assumed) --
    `coherent` therefore flips to `True`. *An empty `sans_appelant` today is not a permanent
    guarantee: the real population moves every turn, and nothing stops a future
    declared-but-never-called item from reappearing.* This instability is exactly why the
    guarantee "G4 never becomes a gate even with some `sans_appelant`" lives in the neighboring
    witness (`test_G4_rend_TOUJOURS_0_meme_avec_des_items_SANS_APPELANT`, a SYNTHETIC population,
    needs no state at all from the real repo to stay true) -- THIS witness keeps only one thing:
    that the JUDGE genuinely runs on the real POPULATION, not on hand-written `DeclarationItem`s,
    and `C5`/`A1` stay two real, independently checkable anchors for that."""
    items = _items_obligation(RACINE_REELLE)
    assert items is not None
    r = verdict_items(items)
    assert "C5" in r.cablees, (
        f"C5 (parc.py, wired up in lot_emit.py since 09c3d95) must be wired; got {r.cablees}"
    )
    assert "A1" in r.cablees, f"A1 (plan_format.py, known real caller) must be wired; got {r.cablees}"


# ------------------------------------------------------------------------------------------------
# LEVEL 1, AND THAT IS A DIRECTLY TESTED GUARANTEE -- not a fragile dependency on a real item
# ------------------------------------------------------------------------------------------------


def test_G4_rend_TOUJOURS_0_meme_avec_des_items_SANS_APPELANT(monkeypatch):
    """Audit reserve: the only witness protecting "G4 never becomes a gate" depended on `B1`
    (a REAL item) being `sans_appelant` TODAY -- if `B1` were demoted to level 1 (the exact
    gesture the item invites), this safety net would stop biting WITHOUT ANYONE noticing. This one
    builds its own synthetic population, entirely `sans_appelant`, and needs NO state at all from
    the real repo to stay true."""
    from mnemosyne.production.obligation import DeclarationItem
    from mnemosyne.runtime.obligation_run import _registre_g4

    population = tuple(
        DeclarationItem(ident=f"X{i}", niveau_2_ou_plus=True, module="plan_condition", appelants=0)
        for i in range(5)
    )
    monkeypatch.setattr(
        "mnemosyne.runtime.obligation_run._items_obligation", lambda _racine: population
    )
    assert _registre_g4(Path(".")) == 0, "level 1: even 100% sans_appelant must NEVER gate"
