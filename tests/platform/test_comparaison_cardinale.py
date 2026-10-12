"""Witnesses for the cardinal comparison (P7).

**THE DEFECT THEY GUARD, RE-TAKEN HERE**: `index_problems('# empty gate', ())` and
`index_problems(<valid gate>, ('arc-c.md',))` render **the same object** — `()`. A comparison
over zero pairs is true by construction, and nothing said so.

The FIVE surfaces: the pure judge · the published text · the PRODUCTION value (the default pair of
functions, judged without injection) · the passing case · and the "decision" surface, here the
:attr:`Comparaison.tient` property that separates a true green from a vacant one.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mnemosyne.production.comparaison_cardinale import Comparaison, comparer, rendre
from mnemosyne.production.plan_format import declared_paths, index_problems

_PORTE_VIDE = "# a gate that declares nothing\n"
_PORTE_UN_ARC = "- [x] `plan/arc-c.md` — an arc\n"


# --------------------------------------------------------------------------------------------
# 1. THE DEFECT ITSELF — the measurement this module is founded on, re-taken and not borrowed.
# --------------------------------------------------------------------------------------------


def test_le_JUGE_NU_rend_le_MEME_vert_sur_zero_paire_et_sur_une_paire() -> None:
    """This is the original measurement. If it ever stops being true, this module has no more
    reason to exist — and this witness is the only place where anyone would notice."""
    assert index_problems(_PORTE_VIDE, ()) == index_problems(_PORTE_UN_ARC, ("arc-c.md",)) == ()


def test_l_ENVELOPPE_les_distingue_la_ou_le_juge_nu_ne_le_peut_pas() -> None:
    vacante = comparer(_PORTE_VIDE, ())
    reelle = comparer(_PORTE_UN_ARC, ("arc-c.md",))
    assert vacante.problemes == reelle.problemes == ()
    assert vacante.vacante is True and reelle.vacante is False
    assert vacante.tient is False, "a vacant verdict is NOT a clean verdict"
    assert reelle.tient is True


# --------------------------------------------------------------------------------------------
# 2. THE JUDGE — the two cardinals, separately.
# --------------------------------------------------------------------------------------------


def test_le_CAS_PASSANT_une_porte_juste_compare_dans_LES_DEUX_sens() -> None:
    c = comparer(_PORTE_UN_ARC, ("arc-c.md",))
    assert c.arcs_compares == 1 and c.chemins_compares == 1 and c.paires == 2
    assert c.problemes == () and c.tient is True


def test_les_DEUX_cardinaux_sont_SEPARES_car_ils_repondent_a_deux_questions() -> None:
    """Publishing a single number would hide one of them: a gate with three arcs and zero
    declarations compares 3 on one side and **0** on the other — and it is that zero that lies."""
    c = comparer("prose with no declaration at all\n", ("a.md", "b.md", "c.md"))
    assert c.arcs_compares == 3 and c.chemins_compares == 0
    assert c.vacante is False, "3 confrontations did take place in the completeness sense"


def test_les_PROBLEMES_rendus_sont_EXACTEMENT_ceux_du_juge_jamais_retouches() -> None:
    """The wrapper adds no refusal: it adds a cardinal, and nothing else."""
    porte, arcs = "- `plan/fantome.md` — an arc\n", ("arc-c.md",)
    assert comparer(porte, arcs).problemes == index_problems(porte, arcs, folder_form=True)


def test_folder_form_FALSE_eteint_le_cardinal_des_declarations_comme_il_eteint_le_refus() -> None:
    """*A count that overshoots what the judge actually did is an exact lie*: the judge removes
    the staleness sense on a single-file plan, the cardinal must follow suit."""
    c = comparer(_PORTE_UN_ARC, (), folder_form=False)
    assert c.problemes == () and c.chemins_compares == 0 and c.vacante is True


def test_une_comparaison_a_ZERO_paire_dans_LES_DEUX_sens_est_VACANTE() -> None:
    assert comparer(_PORTE_VIDE, ()).vacante is True
    assert Comparaison(problemes=(), arcs_compares=0, chemins_compares=0).paires == 0


def test_un_verdict_avec_des_PROBLEMES_ne_tient_pas_meme_si_la_comparaison_a_eu_lieu() -> None:
    c = comparer("- `plan/fantome.md` — an arc\n", ("arc-c.md",))
    assert c.problemes and c.vacante is False and c.tient is False


# --------------------------------------------------------------------------------------------
# 3. THE PUBLISHED TEXT — the sentence, not just the data.
# --------------------------------------------------------------------------------------------


def test_le_texte_d_une_comparaison_VACANTE_ne_se_lit_pas_comme_un_vert() -> None:
    texte = rendre(comparer(_PORTE_VIDE, ()), ou="example/PLAN.md")
    assert "VACANT" in texte and "0 pair" in texte
    assert "example/PLAN.md" in texte
    assert "true by construction" in texte


def test_le_texte_d_un_VRAI_vert_porte_TOUJOURS_son_cardinal() -> None:
    """*A green does not say how many* — except here, and the detail says in WHICH direction."""
    texte = rendre(comparer(_PORTE_UN_ARC, ("arc-c.md",)))
    assert "2 pair(s)" in texte and "1 arc(s)" in texte and "1 declared path(s)" in texte


def test_le_texte_d_un_REFUS_porte_le_cardinal_ET_les_causes() -> None:
    texte = rendre(comparer("- `plan/fantome.md` — an arc\n", ("arc-c.md",)))
    assert "pair(s) compared" in texte
    assert "arc_hors_index" in texte and "index_sans_fichier" in texte


# --------------------------------------------------------------------------------------------
# 4. THE PRODUCTION VALUE — the default pair, without injection.
# --------------------------------------------------------------------------------------------


def test_les_defauts_de_production_SONT_le_juge_et_son_propre_accesseur() -> None:
    """*Measured through the JUDGE'S OWN ACCESSOR*: counting declarations with a pattern of my
    own would give a second opinion, hence two truths about what was compared. `declared_paths` is
    written in its own docstring as *"the JUDGE's question, not the regex's"*."""
    import inspect

    signature = inspect.signature(comparer)
    assert signature.parameters["juge"].default is index_problems
    assert signature.parameters["lecteur_de_declarations"].default is declared_paths


_PORTES_REELLES = sorted(Path(__file__).resolve().parents[2].glob("docs/**/PLAN.md"))


@pytest.mark.skipif(
    not _PORTES_REELLES,
    reason="no real plan gate under docs/ on this checkout — nothing to compare",
)
def test_sur_les_PORTES_REELLES_du_depot_la_comparaison_n_est_pas_VACANTE() -> None:
    """The production population: the gates actually present under `docs/`. If one of them
    became vacant, the commit gate would declare it "sound" without having compared anything."""
    racine = Path(__file__).resolve().parents[2]
    vacantes = []
    for porte in _PORTES_REELLES:
        dossier = porte.parent / "plan"
        arcs = tuple(sorted(p.name for p in dossier.glob("*.md"))) if dossier.is_dir() else ()
        c = comparer(porte.read_text(encoding="utf-8"), arcs, folder_form=dossier.is_dir())
        if c.vacante:
            vacantes.append(str(porte.relative_to(racine)))
    assert vacantes == [], f"gate(s) judged on ZERO pairs: {vacantes}"
