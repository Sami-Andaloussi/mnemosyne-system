"""The banc generator — it must return a VERIFIABLE population, or it measures nothing."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "system" / "lib"))

from mnemosyne.production.plan_banc import plan_de_banc  # noqa: E402
from mnemosyne.production.plan_format import read_plan  # noqa: E402
from mnemosyne.production.plan_ordre import ordonner  # noqa: E402


@pytest.mark.parametrize(("vagues", "largeur"), [(1, 1), (3, 1), (1, 5), (4, 6), (10, 3)])
def test_le_banc_rend_EXACTEMENT_la_population_qu_il_annonce(vagues: int, largeur: int) -> None:
    """**A banc whose generator produces a refused population runs FAST and says nothing.**

    Measured three times in the same session: unreadable identifiers → **0 items**, "excellent"
    timings, no red at all. The only signal was an absurd count. This witness closes the class at
    the source: the generator announces its size, the reader must return it.
    """
    banc = plan_de_banc(vagues, largeur)
    lecture = read_plan(banc.texte)

    assert len(lecture.items) == banc.items == vagues * largeur, lecture.items
    assert not lecture.problems, lecture.problems
    banc.verifie(len(lecture.items))


def test_le_banc_produit_le_NOMBRE_DE_VAGUES_demande_et_pas_une_chaine() -> None:
    """Depth is the axis `B6` measures: a banc that returned a single wave would be measuring
    width while believing it measures depth."""
    banc = plan_de_banc(vagues=6, largeur=3)

    ordre = ordonner(read_plan(banc.texte))

    assert len(ordre.vagues) == banc.vagues == 6, [len(v) for v in ordre.vagues]
    assert all(len(vague) == 3 for vague in ordre.vagues), [len(v) for v in ordre.vagues]
    assert ordre.cycle == (), ordre.cycle


def test_le_banc_REFUSE_une_taille_qui_ne_correspond_pas() -> None:
    """`verifie` must BITE — a check that never refuses is a comment."""
    banc = plan_de_banc(vagues=2, largeur=2)

    banc.verifie(4)
    with pytest.raises(AssertionError, match="population is degenerate"):
        banc.verifie(0)


def test_deux_tirages_du_MEME_banc_rendent_le_MEME_texte() -> None:
    """That's this file's reason for existing: two actors must be able to replay THE SAME
    population.

    *Two figures about two populations don't contradict each other: they don't speak to each
    other* — 25s versus 0.049s under a single fixture name.
    """
    assert plan_de_banc(5, 4).texte == plan_de_banc(5, 4).texte
    assert plan_de_banc(5, 4).texte != plan_de_banc(4, 5).texte
