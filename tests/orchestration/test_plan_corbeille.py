"""H3 — the corbeille moves an H1-retired item's bytes and never rewrites one, proven not promised.

Same discipline as its sibling `test_plan_archive.py`: the byte-exact guarantee
(`verify_roundtrip`) is sabotage-proven at the bottom of this file, not just asserted green. What
this module adds on top of the archiver's own proof: an item is only a candidate when H1's OWN
comment says so — never a bare `clos` glyph, which can mean anything.
"""

from __future__ import annotations

import pytest

from mnemosyne.production.plan_corbeille import (
    GLYPHE_RETRAIT,
    RETIRES_DIRNAME,
    RetraitCorbeilleError,
    plan_corbeille,
    retiree_filename,
    retrait_trouve,
    verify_readability,
    verify_roundtrip,
)
from mnemosyne.production.plan_format import ROLE_ARC, read_plan
from mnemosyne.production.plan_retrait import _GLYPHE_RETRAIT as _H1_GLYPHE
from mnemosyne.production.plan_retrait import applique_retrait

_ARC = """\
# Arc A

- **A1** \U00002B1C A normal item, never touched.
- **A2** \U00002B1C An item H1 will retire, then H3 will move.
  *Produit* : something concrete
  *Fini quand* : condition verified
- **A3** \U00002B1C A third item, never touched either.
"""


def _retire(items=("A2",), *, motif="test reason", cout="none", id_retrait="deadbeef0001"):
    """`_ARC` after a real H1 retrait — the SAME function `plan_retrait_run` calls, never a
    hand-typed comment: a fixture that types the comment itself could drift from what H1 really
    writes, which is exactly the class of bug this whole module exists to avoid."""
    return applique_retrait(
        _ARC, items, motif=motif, cout=cout, id_retrait=id_retrait, quand="2026-08-16T00:00:00+00:00"
    )


def _plan(text, **kwargs):
    options = {"source": "arc-a.md", "today": "2026-08-16", "remplace": "see H4"}
    options.update(kwargs)
    return plan_corbeille(text, **options)


# --- 0. the shared glyph — two independent constants, checked equal -------------------------------


def test_le_glyphe_de_ce_module_EST_celui_que_H1_ecrit() -> None:
    """Two independent constants (H1 does not export it publicly) that must say the same thing —
    a disagreement here would break `retrait_trouve` silently, never loudly."""
    assert GLYPHE_RETRAIT == _H1_GLYPHE


# --- 1. retrait_trouve — the front door, never a bare `clos` --------------------------------------


def test_retrait_trouve_LIT_le_commentaire_H1_reel() -> None:
    texte = _retire(motif="redundant item", cout="trivial")
    reading = read_plan(texte)
    item = next(it for it in reading.items if it.ident == "A2")

    trouve = retrait_trouve(item)

    assert trouve is not None
    assert trouve.id == "deadbeef0001"
    assert trouve.motif == "redundant item"
    assert trouve.cout == "trivial"


def test_retrait_trouve_est_NONE_sur_un_item_ouvert() -> None:
    reading = read_plan(_ARC)
    item = next(it for it in reading.items if it.ident == "A1")
    assert retrait_trouve(item) is None


def test_retrait_trouve_est_NONE_sur_un_clos_SANS_commentaire_H1() -> None:
    """An item can be `clos` for a completely different reason — that is none of this module's business."""
    texte = _ARC.replace(f"**A1** {chr(0x2b1c)}", f"**A1** {GLYPHE_RETRAIT}")
    reading = read_plan(texte)
    item = next(it for it in reading.items if it.ident == "A1")
    assert retrait_trouve(item) is None


# --- 2. plan_corbeille — the six refusals, each fired on its own -----------------------------------


def test_refuse_un_identifiant_ABSENT() -> None:
    planning = _plan(_ARC, ident="ZZZ")
    assert planning.blocked
    assert planning.refusal.reason == "item_absent"


def test_refuse_un_item_JAMAIS_RETIRE() -> None:
    planning = _plan(_ARC, ident="A1")
    assert planning.blocked
    assert planning.refusal.reason == "pas_retire_par_h1"


def test_refuse_un_clos_SANS_H1() -> None:
    texte = _ARC.replace(f"**A1** {chr(0x2b1c)}", f"**A1** {GLYPHE_RETRAIT}")
    planning = _plan(texte, ident="A1")
    assert planning.blocked
    assert planning.refusal.reason == "pas_retire_par_h1"


def test_refuse_un_commentaire_H1_ILLISIBLE() -> None:
    texte = _ARC.replace(
        f"- **A2** {chr(0x2b1c)} An item H1 will retire, then H3 will move.",
        f"- **A2** {GLYPHE_RETRAIT} An item H1 will retire, then H3 will move.\n"
        "  <!-- RETRAIT (H1) this does not match the expected format -->",
    )
    planning = _plan(texte, ident="A2")
    assert planning.blocked
    assert planning.refusal.reason == "commentaire_illisible"


def test_refuse_REMPLACE_vide() -> None:
    planning = _plan(_retire(), ident="A2", remplace="   ")
    assert planning.blocked
    assert planning.refusal.reason == "remplace_vide"


def test_ACCEPTE_remplace_AUCUN_comme_reponse_valide() -> None:
    """"AUCUN" is a valid, free response — same precedent as `*Prerequis*`."""
    planning = _plan(_retire(), ident="A2", remplace="AUCUN")
    assert not planning.blocked


def test_refuse_REMPLACE_avec_un_caractere_de_controle() -> None:
    planning = _plan(_retire(), ident="A2", remplace="texte\x00corrompu")
    assert planning.blocked
    assert planning.refusal.reason == "remplace_illisible"


def test_refuse_une_COLLISION_de_nom_dans_la_corbeille() -> None:
    texte = _retire()
    filename = retiree_filename("2026-08-16", "A2")
    planning = _plan(texte, ident="A2", taken={filename})
    assert planning.blocked
    assert planning.refusal.reason == "corbeille_existe"


# --- 3. the REAL move, checked from both ends --------------------------------------------------------


def test_le_mouvement_EXTRAIT_exactement_le_bon_SPAN() -> None:
    """The moved body carries the bullet, the H1 comment, AND the item's own detail — never
 more (not A1, not A3), never less (not just the bullet with no detail)."""
    texte = _retire()
    planning = _plan(texte, ident="A2")

    assert not planning.blocked
    body = planning.move.body
    assert "**A2**" in body and GLYPHE_RETRAIT in body
    assert "RETRAIT (H1)" in body
    assert "*Produit* : something concrete" in body
    assert "*Fini quand* : condition verified" in body
    assert "A1" not in body and "A3" not in body


def test_la_corbeille_PORTE_motif_cout_ET_ce_qui_remplace() -> None:
    texte = _retire(motif="precise reason", cout="precise cost")
    planning = _plan(texte, ident="A2", remplace="precise replacement")
    corbeille = planning.corbeille_text()

    assert "precise reason" in corbeille
    assert "precise cost" in corbeille
    assert "precise replacement" in corbeille


def test_le_pointeur_laisse_dans_l_arc_NOMME_l_identifiant_et_le_lien() -> None:
    planning = _plan(_retire(), ident="A2")
    assert "A2" in planning.move.pointer
    assert planning.move.link in planning.move.pointer
    assert RETIRES_DIRNAME in planning.move.link


def test_verify_roundtrip_PASSE_sur_un_mouvement_reel() -> None:
    planning = _plan(_retire(), ident="A2")
    verify_roundtrip(planning)  # does not raise


def test_verify_roundtrip_REFUSE_d_etre_appele_sur_une_planification_bloquee() -> None:
    planning = _plan(_ARC, ident="A1")
    with pytest.raises(RetraitCorbeilleError):
        verify_roundtrip(planning)


def test_verify_readability_ACCEPTE_un_arc_qui_garde_au_moins_un_item() -> None:
    planning = _plan(_retire(), ident="A2")
    verify_roundtrip(planning)
    verify_readability(planning, role=ROLE_ARC)  # does not raise


def test_verify_readability_REFUSE_de_vider_un_arc_de_son_dernier_item() -> None:
    """Retiring the ONLY item of an arc makes it unreadable AS AN ARC — measured, not assumed: the
    round-trip (the bytes) still passes, it is verify_readability that must bite."""
    solo = "# Solo arc\n\n- **SOLO** \U00002B1C The only item of this arc.\n"
    apres_h1 = applique_retrait(
        solo, ("SOLO",), motif="m", cout="none", id_retrait="id1", quand="2026-08-16T00:00:00+00:00"
    )
    planning = plan_corbeille(
        apres_h1, source="x.md", ident="SOLO", remplace="nothing", today="2026-08-16"
    )
    assert not planning.blocked
    verify_roundtrip(planning)  # the bytes reconstruct fine
    with pytest.raises(RetraitCorbeilleError):
        verify_readability(planning, role=ROLE_ARC)


# --- 4. byte-exact restitution — rebuild from the corbeille, not just proclaim it -------------------


def test_LA_RESTITUTION_EST_PROUVEE_PAR_RECONSTRUCTION_REELLE_PAS_SEULEMENT_PROCLAMEE() -> None:
    """H3's *Fini quand*: "restorable byte for byte". This test does not take `verify_roundtrip`'s
    word for it: it replays the reconstruction itself, cutting the corbeille's VERBATIM body out
    and putting it back at the pointer, then compares against the arc BEFORE retirement."""
    from mnemosyne.production.plan_archive import VERBATIM_MARKER

    original = _retire()
    planning = _plan(original, ident="A2")
    corbeille_text = planning.corbeille_text()

    corps_recupere = corbeille_text.split(VERBATIM_MARKER, 1)[1]
    reconstruit = planning.remaining.replace(planning.move.pointer + "\n", corps_recupere, 1)

    assert reconstruit == original, "the manual reconstruction does not give back the original arc"


# --- 5. sabotage — the round-trip really BITES --------------------------------------------------------


def test_SABOTAGE_un_corps_TRONQUE_dans_la_corbeille_fait_MORDRE_verify_roundtrip(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Break `corbeille_text` so it omits the body's last line — `verify_roundtrip` MUST refuse.
    If this test passes without the `pytest.raises` assertion, the proof does not bite."""
    from mnemosyne.production import plan_corbeille as module

    planning = _plan(_retire(), ident="A2")
    original_corbeille_text = module.CorbeillePlanning.corbeille_text

    def sabotee(self):
        texte = original_corbeille_text(self)
        lignes = texte.splitlines(keepends=True)
        return "".join(lignes[:-1])  # truncate the last line of the verbatim body

    monkeypatch.setattr(module.CorbeillePlanning, "corbeille_text", sabotee)
    with pytest.raises(RetraitCorbeilleError):
        verify_roundtrip(planning)
