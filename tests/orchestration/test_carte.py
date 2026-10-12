"""B3 — THE MAP: its property is not to be small, it is to NOT GROW.

 **The witness that decides is the CONSTANT SIZE one**: the `*Done when*` clause requires that
the map of a **168**-step plan and one for a **10,000**-step plan fit in the same number of
lines, **within ±10%** — measured, not assumed. A module that listed everything would pass every
other witness and fail this one.

 **AND THIS FILE'S OWN LIMIT IS STATED**: my 10,000-item fixture is **synthetic**. It has the
SIZE of the real thing, not its SHAPE (a real plan has arcs, potential cycles, expiry dates). The
witness therefore proves the constant-size property on a REGULAR population, and says nothing
about an irregular population of the same size. *A degenerate fixture tests nothing* — this one is
not, but it is not the real thing either, and it is up to the audit to decide what remains open.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from mnemosyne.production.carte import (
    PROFONDEUR,
    ArcEtat,
    carte_par_arc,
    lire,
    lire_peremption,
    rendre,
    replier,
)

#: The word the map PRINTS for an expiring item, aimed at the production constant instead of
#: recopied. It read `"PÉRISSABLE"` here while `carte._TETE_PERISSABLE` had already become
#: `"PERISHABLE"`, so the two witnesses below asserted a string production no longer emits.
#: Recopying the value closes the CASE; naming the constant closes the CLASS, and survives the
#: next translation of the word.
from mnemosyne.production.carte import _TETE_PERISSABLE
from mnemosyne.production.plan_format import ROLE_PLAN, fold_plan, is_readable
from mnemosyne.production.plan_registry import read_plan_tree
from mnemosyne.production.signalements import _PREFIXE_BRAISE

REPO = Path(__file__).resolve().parents[2]
#: The sibling project's plan is the population the clause NAMES. A witness that did without it would
#: measure an imitation -- that is exactly what let blocker #1 through.
SIBLING_PROJECT = REPO / "projects" / "saas" / "Sibling Project"

#: **THE ROOT, DERIVED — NOT PICKED BY EYE, BECAUSE I GOT IT WRONG TWICE.**
#: The first witness split columns with `split("  ", 3)[:3]` and asserted on NOTHING. The second,
#: written specifically to replace it, with eight lines calling itself "THE ASSERTION THAT
#: DECIDES," searched for a five-letter stem that was NOT inside every form it had to catch: it
#: only matched two of the six, never the conjugated one, which is exactly the form the whole
#: mechanism exists to remove. An
#: isolated third party showed this by replacing the translation with the identity function:
#: **23/23 still green**.
#: The root is now the longest common string across ALL known forms of the word, and the witness
#: below **tests the probe itself** before it is used. *A probe picked by eye is a probe never
#: measured; make it fail against its own targets first.*
#: **THE FORMS ARE THE ONES PRODUCTION EMITS TODAY, NOT THE ONES IT USED TO.** They were the
#: French conjugations while `RACINE_DU_MOT` had already become `"unblock"` -- so the probe
#: matched NONE of its own targets and this witness stayed red. `plan_ordre.py` composes its
#: reasons with "unblocks N step(s)" / "THE most unblocking": a form list in another language
#: than the output it guards measures nothing at all.
FORMES_DU_MOT_QUI_MENT = ("unblock", "unblocks", "unblocked", "unblocking", "unblockable")
RACINE_DU_MOT = "unblock"


def test_la_SONDE_du_mot_attrape_TOUTES_ses_formes_avant_qu_on_s_en_serve():
    """ **The witness that tests the probe.** Two successive assertions each turned out to be
 empty for lack of this one: the first was not looking at the right substring, the second
 searched for a prefix that appears in none of the conjugated forms. *A detector that has never
 been made to bite on its own targets only measures silence.*"""
    manquees = [f for f in FORMES_DU_MOT_QUI_MENT if RACINE_DU_MOT not in f]
    assert not manquees, f"the probe {RACINE_DU_MOT!r} does not catch: {manquees}"
    assert RACINE_DU_MOT not in "attendu par", "and it must not catch the CORRECT word"


def _plan(nb_items: int, *, dependances: bool = True) -> str:
    """A plan door carrying ``nb_items`` steps, in the FORM the reader requires."""
    lignes = ["# PLAN — fixture", "", "## The steps", ""]
    for n in range(nb_items):
        lignes.append(f"- **F{n}** \U00002B1C **Step {n}.**")
        lignes.append(f"  *Produit* : something {n}")
        lignes.append("  *Fini quand* : une commande le dit")
        # one dependency out of every seven, like a regular population
        depend = f"F{n - 1}" if dependances and n and n % 7 == 0 else "AUCUNE"
        lignes.append(f"  *Dépend de* : {depend}")
        lignes.append("  *Prérequis* : AUCUN")
    return "\n".join(lignes) + "\n"


def _lecture(texte: str):
    return fold_plan(texte, (), lambda _m: (None, "absent"), folder_form=False)


# --------------------------------------------------------------------------------------------
# THE DECIDING CLAUSE — size does NOT grow
# --------------------------------------------------------------------------------------------


def test_168_et_10000_etapes_rendent_le_MEME_nombre_de_lignes_a_10_pourcent():
    """ B3's `*Done when*` clause, word for word — measured, not assumed."""
    petite = rendre(lire(_lecture(_plan(168))), projet="fixture-168").splitlines()
    grande = rendre(lire(_lecture(_plan(10_000))), projet="fixture-10000").splitlines()
    ecart = abs(len(grande) - len(petite)) / max(len(petite), 1)
    assert ecart <= 0.10, (
        f"{len(petite)} lines for 168 steps against {len(grande)} for 10,000 — "
        f"gap {ecart:.1%}, the clause tolerates 10%"
    )


def test_le_VRAI_plan_ne_GROSSIT_pas_au_dela_de_la_fixture_de_10000():
    """ The property is to NOT GROW, not to be equal — and my first witness got this wrong.

 I had written "the real thing is within ±10% of the fixture." The clause does not say that:
 it compares **168 steps** to **10,000**. This repository's own plan carries **49**, and it
 renders **24 lines against 28** — a 16.7% gap, but **downward**. A smaller plan that renders a
 shorter map is not drift: some bounded sections simply have fewer than `PROFONDEUR` entries to
 show. *A wrongly-copied clause manufactures a red that does not exist.*
 """
    plans = read_plan_tree(REPO / "docs", "Mnémosyne")
    reading = plans[0].reading
    assert reading is not None and is_readable(reading, role=ROLE_PLAN), "this repository's own plan is unreadable"
    reel = rendre(lire(reading), projet="Mnémosyne").splitlines()
    fixture = rendre(lire(_lecture(_plan(10_000))), projet="fixture").splitlines()
    assert len(reel) <= len(fixture) * 1.10, (
        f"{len(reel)} lines for 49 steps against {len(fixture)} for 10,000 — the map is GROWING"
    )


# --------------------------------------------------------------------------------------------
# WHAT SEPARATES A SUMMARY FROM AN EXCERPT — every section SAYS what it hides
# --------------------------------------------------------------------------------------------


def test_chaque_section_bornee_DIT_combien_elle_cache():
    """*An excerpt is the worst of both worlds: too small to understand, big enough to believe
    you've seen it.* A truncated list with no remainder reads like a complete list."""
    rendu = rendre(lire(_lecture(_plan(10_000))), projet="fixture")
    assert "autre(s)" in rendu, "a bounded section must announce its remainder"


def test_un_plan_PLUS_PETIT_que_la_borne_n_annonce_AUCUN_reste():
    """The counterpart: on three items, saying "and 0 others" would be manufactured noise."""
    rendu = rendre(lire(_lecture(_plan(3, dependances=False))), projet="fixture")
    assert "et 0 autre" not in rendu


# --------------------------------------------------------------------------------------------
# "WHAT DOES NOT MOVE" — the only section whose ABSENCE reads as good news
# --------------------------------------------------------------------------------------------


def test_un_item_hors_du_courant_est_NOMME():
    """An item that nothing unblocks and that unblocks nothing is not "done": it is out of the
    current, and nobody ever notices it."""
    carte = lire(_lecture(_plan(4, dependances=False)))
    assert carte.immobile, "four items with no dependency at all are all motionless"
    assert "CE QUI NE BOUGE PAS" in rendre(carte, projet="fixture")


# --------------------------------------------------------------------------------------------
# THE EDGE — it refuses to draw on a broken plan
# --------------------------------------------------------------------------------------------


def test_le_bord_REFUSE_de_dessiner_sur_un_plan_ILLISIBLE(tmp_path, monkeypatch, capsys):
    """ *A correct view of a stale source is an exact lie.* Drawing a map on a broken plan
 would be worse than drawing nothing: it would look like an honest status report."""
    from mnemosyne.runtime import carte_run

    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "PLAN.md").write_text("pas de titre de plan du tout\n", encoding="utf-8")
    assert carte_run.main([]) == 1
    erreur = capsys.readouterr().err
    assert "UNREADABLE" in erreur and "an exact lie" in erreur


def test_le_bord_distingue_PAS_DE_PLAN_de_PLAN_CASSE(tmp_path, monkeypatch, capsys):
    """"No plan here" and "broken plan" are two different sentences — confusing them would send
    someone looking for a defect where there is none."""
    from mnemosyne.runtime import carte_run

    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    (tmp_path / "docs").mkdir()
    assert carte_run.main([]) == 2, "no door at all -> rc 2, never rc 1"
    assert "no plan door" in capsys.readouterr().err


def test_C8_une_variable_VOISINE_MECONNUE_est_REFUSEE_au_lieu_de_retomber_en_silence(
    tmp_path, monkeypatch, capsys
) -> None:
    """C8: `CHEMIN=` instead of `POUR=` used to fall back silently onto Mnémosyne's own plan and
    still draw a map, without a word about the wrong population."""
    from mnemosyne.runtime import carte_run

    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    monkeypatch.setenv("CHEMIN", "/un/chemin/quelconque")
    monkeypatch.delenv("POUR", raising=False)
    assert carte_run.main([]) == 2
    erreur = capsys.readouterr().err
    assert "CHEMIN=" in erreur and "POUR=" in erreur, erreur


def test_le_bord_rend_la_carte_du_VRAI_depot(capsys):
    """No `CLAUDE_PROJECT_DIR` at all: the root is this repository's own. The one end-to-end
    witness."""
    from mnemosyne.runtime import carte_run

    assert carte_run.main([]) == 0
    sortie = capsys.readouterr().out
    assert sortie.startswith("CARTE — Mnémosyne")
    assert "CE QUI NE BOUGE PAS" in sortie


@pytest.mark.parametrize("arcs", [4, 8, 14])
@pytest.mark.parametrize("taux_dep", [0.23, 0.55, 0.86])
def test_LA_CLAUSE_sur_TOUT_le_DOMAINE_le_pire_cas_decide(arcs, taux_dep):
    """ **THE CLAUSE WITH ITS DOMAIN — and the domain was DRAWN FROM THE REAL THING, not
 picked.**

 The clause said *"a 10,000-step fixture"* without saying **which one**: two honest readers
 got **6.5%** and **22.6%** on the same code. *The free parameter was neither the unit nor the
 predicate — it was **the witness population itself**.*

 **The arbitration refused to pick between the two fixtures** (*"that would be choosing the
 verdict"*) and instead wrote a domain measured on the two real plans: **≥ 4 arcs · dependency
 ratio in `[23%, 86%]` · all three statuses**. **It favored nobody**: the orchestrator's own
 fixture had 1 arc, mine had 14% dependencies — **neither one qualified**. *Had it been picked,
 this domain would have saved someone; it is precisely because it was drawn that it saves no
 one.*

 **The verdict holds for the WHOLE domain, so the WORST case decides** — one passing point
 says nothing about the other eight. Nine corners drawn; measured: **0.0% everywhere**."""
    plans = read_plan_tree(SIBLING_PROJECT, "Sibling Project")
    lectures = [p.reading for p in plans if p.reading is not None and p.reading.items]
    correspondance = {
        item.ident: plan.name
        for plan in plans
        if plan.reading is not None and plan.reading.items
        for item in plan.reading.items
    }
    sibling_project, _ = replier(lectures)
    reelle = rendre(lire(sibling_project, arcs=correspondance), projet="Sibling Project").splitlines()

    from mnemosyne.production.plan_banc import plan_de_banc

    banc = plan_de_banc(
        100, 100, arcs=arcs, faits=1800, en_cours=700, aretes_refusees=3, taux_dep=taux_dep
    )
    lue = _lecture(banc.texte)
    banc.verifie(len(lue.items))
    carte = lire(lue)
    # THE POPULATION IS CHECKED BEFORE BEING JUDGED, on all three axes of the domain.
    assert carte.arcs_total == arcs, f"{arcs} arcs requested, {carte.arcs_total} produced"
    statuts = dict(carte.par_statut)
    assert {"fait", "en_cours", "a_faire"} <= set(statuts), f"the 3 statuses: {statuts}"
    assert len(carte.refus) + carte.refus_caches == 3, "and the refused edges"

    fixture = rendre(carte, projet="banc").splitlines()
    ecart = abs(len(fixture) - len(reelle)) / max(len(reelle), 1)
    assert ecart <= 0.10, (
        f"arcs={arcs} taux_dep={taux_dep:.0%}: {len(reelle)} lines for {len(sibling_project.items)} "
        f"real steps against {len(fixture)} for {banc.items} — gap {ecart:.1%}"
    )


# **REMOVED on 2026-08-15: `test_LA_CLAUSE_sur_une_fixture_qui_a_la_FORME_du_reel…`.**
# It pulled the clause on `plan_de_banc(2, 5000, arcs=3, …)` — **3 arcs**, so **OUTSIDE the
# domain** the arbitration wrote (`>= 4 arcs`). It therefore returned a GREEN on a population the
# clause declares inadmissible: *a witness that passes on an out-of-domain population proves
# nothing and reassures anyway.*
# And it cost **69s on its own** — more than the domain's nine cases combined. Removing it
# drops no coverage: the sweep above contains it and widens it.

def test_LA_CLAUSE_le_VRAI_plan_du_projet_voisin_168_etapes_contre_10000_a_10_pourcent():
    """ **`B3`'S `*Done when*` CLAUSE, ON ITS REAL POPULATION — it had never had a left-hand
 side.** *"the map rendered on the sibling project's plan (168 steps) and on a 10,000-item fixture fit in the
 same number of lines, within ±10%."*

 The edge case kept `plans[0]`: on the sibling project it drew **21 steps out of 168**, `rc 0`, not a word.
 The two 0.0%-gap measurements published earlier were on a synthetic fixture and on THIS
 repository's own plan (49 items) — **never on the sibling project**. Invisible because Mnémosyne's plan is
 FLAT (`plans[0]` is 49/49 there) and the sibling project's is a TREE of 14 sub-plans.

 **This witness reads the REAL sibling project**, not an imitation: if its plan becomes unreadable, it
 reddens — and that is what we want, because the clause is talking about it."""
    plans = read_plan_tree(SIBLING_PROJECT, "Sibling Project")
    lectures = [p.reading for p in plans if p.reading is not None and p.reading.items]
    sibling_project, collisions = replier(lectures)
    assert not collisions, f"two plans share the same identifier: {collisions}"
    assert len(sibling_project.items) >= 100, (
        f"the fold must return the whole tree; it returns {len(sibling_project.items)} items for "
        f"{len(lectures)} plans — the edge case was only drawing the door's own"
    )
    reelle = rendre(lire(sibling_project), projet="Sibling Project").splitlines()
    fixture = rendre(lire(_lecture(_plan(10_000))), projet="fixture").splitlines()
    ecart = abs(len(fixture) - len(reelle)) / max(len(reelle), 1)
    assert ecart <= 0.10, (
        f"{len(reelle)} lines for {len(sibling_project.items)} sibling-project steps against {len(fixture)} "
        f"for 10,000 — gap {ecart:.1%}, the clause tolerates 10%"
    )


def test_le_BORD_dessine_l_arbre_ENTIER_et_le_DIT(capsys, monkeypatch):
    """The counter-test on the edge: `make carte POUR=…` must cover the whole tree and announce
    what it folded. *A count that is never published cannot be contested.*"""
    from mnemosyne.runtime import carte_run

    monkeypatch.setenv("POUR", str(SIBLING_PROJECT))
    assert carte_run.main([]) == 0
    sortie = capsys.readouterr().out
    plans = read_plan_tree(SIBLING_PROJECT, "Sibling Project")
    attendu = sum(len(p.reading.items) for p in plans if p.reading and p.reading.items)
    assert f"{attendu} étapes" in sortie, f"the edge case must announce the {attendu} folded steps"
    assert f"OÙ ON EN EST : {attendu} items" in sortie


def test_POUR_UN_AUTRE_PROJET_derive_et_routage_se_TAISENT_pas_les_chiffres_de_MNEMOSYNE(
    capsys, monkeypatch
):
    """ **The defect measured by the autonomy probe, 2026-08-17**: `make carte POUR=<another project>`
 rendered MNÉMOSYNE'S OWN numbers (`derive_resume`/`routage_resume`, both wired to
 `_racine()` unconditionally) under a map labeled for a different project — identical, character
 for character, to plain `make carte`'s own output with no `POUR=`. Triggered in the first
 direction: on a REAL sibling project, not one fragment of Mnémosyne's real pages must
 leak."""
    from mnemosyne.runtime.derive_run import resume as derive_resume
    from mnemosyne.runtime.routage_journal_run import resume as routage_resume
    from mnemosyne.runtime import carte_run

    from datetime import date

    vraie_derive = derive_resume(REPO, aujourdhui=date.today().isoformat())
    vraie_routage = routage_resume(REPO)

    monkeypatch.setenv("POUR", str(SIBLING_PROJECT))
    assert carte_run.main([]) == 0
    sortie = capsys.readouterr().out

    assert vraie_derive not in sortie, "Mnémosyne's own drift page leaked under the sibling project"
    assert vraie_routage not in sortie, "Mnémosyne's own routing journal leaked under the sibling project"
    assert "NOT RENDERED" in sortie
    assert "Sibling Project" in sortie


def test_POUR_UN_PLAN_NE_DE_MAINTENANT_derive_et_routage_se_TAISENT_AUSSI(
    tmp_path, capsys, monkeypatch
):
    """The probe's exact scene: a plan born 30 seconds earlier, with no history at all. No
    manufactured histogram, no recycled Mnémosyne number."""
    from mnemosyne.runtime.derive_run import resume as derive_resume
    from mnemosyne.runtime.routage_journal_run import resume as routage_resume
    from mnemosyne.runtime import carte_run

    from datetime import date

    vraie_derive = derive_resume(REPO, aujourdhui=date.today().isoformat())
    vraie_routage = routage_resume(REPO)

    (tmp_path / "PLAN.md").write_text(
        "# PLAN — fixture\n\n> **Cap** : fixture.\n\n## The steps\n\n- **A1** \U00002B1C one.\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("POUR", str(tmp_path))
    assert carte_run.main([]) == 0
    sortie = capsys.readouterr().out

    assert vraie_derive not in sortie
    assert vraie_routage not in sortie
    assert "NOT RENDERED" in sortie
    # "24.1%" / "31 item(s) closed" are Mnémosyne's own MEASURED numbers at the time this test
    # was written — a brand-new plan must manufacture NEITHER these values NOR any other in their
    # place.
    assert "24,1" not in sortie
    assert "31 item" not in sortie


def test_SANS_POUR_derive_et_routage_continuent_de_rendre_MNEMOSYNE_cas_passant(capsys):
    """ Do not break the passing case: with no `POUR=`, `make carte` must keep rendering
 Mnémosyne's REAL numbers — the silence added above must only bite on `POUR=`."""
    from mnemosyne.runtime.derive_run import resume as derive_resume
    from mnemosyne.runtime.routage_journal_run import resume as routage_resume
    from mnemosyne.runtime import carte_run

    from datetime import date

    vraie_derive = derive_resume(REPO, aujourdhui=date.today().isoformat())
    vraie_routage = routage_resume(REPO)

    assert carte_run.main([]) == 0
    sortie = capsys.readouterr().out

    assert vraie_derive in sortie
    assert vraie_routage in sortie
    # The needle is the marker `carte_run` prints TODAY. It read "NON RENDUS" until production
    # was translated, and a `not in` looking for a string that exists nowhere is a control that
    # has quietly stopped being taken.
    assert "NOT RENDERED" not in sortie


def test_replier_NOMME_les_identifiants_en_collision_au_lieu_de_les_avaler(tmp_path):
    """ Two plans sharing the same identifier would make the order wrong **silently**:
 `dependances` resolves by ident, so a dependency would point at the wrong item. Measured on
 The sibling project: 168 items, 168 idents, zero collisions — but *a freeze protects against forgetting,
 never against its own author*, and the caller must be able to say so."""
    un = _lecture(_plan(3, dependances=False))
    deux = _lecture(_plan(3, dependances=False))
    fusion, collisions = replier([un, deux])
    assert len(fusion.items) == 6, "the fold keeps both copies — it does not deduplicate"
    assert collisions == ("F0", "F1", "F2"), f"the three duplicated idents must be NAMED: {collisions}"


def test_replier_REFUSE_une_liste_VIDE_au_lieu_de_rendre_un_plan_vide():
    """*An empty population returns a green*: folding nothing into an empty reading would draw
    "0 items" as if that were a measured state."""
    with pytest.raises(ValueError, match="no reading"):
        replier([])


def test_une_arete_REFUSEE_est_DECLAREE_et_les_chiffres_disent_qu_ils_sont_AMPUTES():
    """ **SERIOUS #7.** `carte_run` only read `reading.problems` (the READER); `ordonner` has its
 OWN refusals, and the map never saw them. The auditor's measurement: three broken plans
 returned `rc 0`, and on an unknown dependency the map announced "2 parallelizable" while the
 refused edge had been **dropped** — the item entered as free with a confident reason.

 The map remains a PROPOSAL organ: it draws **and declares**, it does not refuse. *A wall is
 DECLARED, never worked around.*"""
    texte = (
        "# PLAN — fixture\n\n## The steps\n\n"
        "- **A** \U00002B1C **Depends on an unknown.**\n  *Produit* : x\n  *Fini quand* : c\n"
        "  *Dépend de* : ZZ-UNKNOWN\n  *Prérequis* : AUCUN\n"
        "- **B** \U00002B1C **Sound.**\n  *Produit* : x\n  *Fini quand* : c\n"
        "  *Dépend de* : AUCUNE\n  *Prérequis* : AUCUN\n"
    )
    carte = lire(_lecture(texte))
    assert carte.refus, "an unknown dependency is a refusal from the ORDER, it must surface"
    rendu = rendre(carte, projet="fixture")
    assert "ORDRE AMPUTÉ" in rendu, "and the reader must know the numbers are amputated"
    # The declaration fits in ONE line: listed like its neighbors, it pushed the sibling project's real map
    # from 28 to 33 lines (15.2%), past the clause's 10%. *A section that only appears on an
    # irregular population breaks the property exactly where it must hold.*
    portantes = [ln for ln in rendu.splitlines() if "AMPUTÉ" in ln]
    assert len(portantes) == 1, f"the declaration must fit in ONE line, not {len(portantes)}"


def _plan_dependant() -> str:
    """A TINY but NON-DEGENERATE plan: A is done, B depends on A, C depends on nothing.

 The original witness's `_plan(4, dependances=False)` fixture was **degenerate**: with no
 dependency at all, "nobody is waiting on it" and "it is not waiting on anyone" coincide, so a
 witness built on it passes even when one of the two halves is dead. *A population where both
 halves of an AND coincide never tests the AND.*"""
    return (
        "# PLAN — fixture\n\n## The steps\n\n"
        "- **A** \U00002705 **Already done.**\n  *Produit* : x\n  *Fini quand* : c\n"
        "  *Dépend de* : AUCUNE\n  *Prérequis* : AUCUN\n"
        "- **B** \U00002B1C **Depends on A.**\n  *Produit* : x\n  *Fini quand* : c\n"
        "  *Dépend de* : A\n  *Prérequis* : AUCUN\n"
        "- **C** \U00002B1C **Depends on nothing and nothing depends on it.**\n  *Produit* : x\n"
        "  *Fini quand* : c\n  *Dépend de* : AUCUNE\n  *Prérequis* : AUCUN\n"
    )


def test_faits_se_DERIVE_du_plan_et_le_defaut_VIDE_cachait_des_items_demarrables():
    """ **AUDIT BLOCKER #3.** `lire` carried `faits=frozenset()` and never populated it: the
 queue was computed as if NOTHING were done. Measured on this repository's own plan — **2
 ranks instead of 7**, with `D1`, `B3`, and `I2` startable and **absent** from the one surface
 that says where to start.

 **The witness tests DIFFERENTIATION, not conformity**: the two conventions must give two
 different answers on the same population. A witness that only checked the defect would also
 pass with `faits` frozen empty."""
    lecture = _lecture(_plan_dependant())
    derive = [r.ident for r in lire(lecture).tete]
    vide = [r.ident for r in lire(lecture, faits=frozenset()).tete]
    assert "B" in derive, f"A is done, so B is startable; the queue returns {derive}"
    assert "B" not in vide, "with `faits` empty, B must stay blocked — otherwise this witness measures nothing"


def test_un_item_qui_DECLARE_une_dependance_n_est_JAMAIS_dit_immobile():
    """ **AUDIT BLOCKER #2 — the clause was DEAD.** It read
 `attendus = {d for _, d in ordre.deblocages}` where `d` is the **count**: a set of `int`s
 compared to a `str`, so **always true**. The half "it is not waiting on anyone" was never
 tested. Measured on this repository's own plan: **17 of the 18** items named "does not move"
 were waiting on someone.

 **And it was the sabotage that proved it dead, not the reading**: replacing `immobiles` with
 "everything still to do" left **13/13 witnesses green**."""
    carte = lire(_lecture(_plan_dependant()))
    assert "B" not in carte.immobile, "B declares A as a dependency: it is waiting on someone"
    assert "C" in carte.immobile, "C waits on nobody and nobody waits on it — it is the motionless one"


def test_L_AVERTISSEMENT_de_collision_du_BORD_est_declare_NON_EPROUVE():
    """ **ADMISSION, and it stands in for a witness I did not manage to write.**

 The sabotage that cuts the edge case's collision warning **survives**: `replier` has its own
 witness (the pure function), but **the edge case's own branch is judged by nobody**.

 **I tried to reach it and did not manage to**, and the reason is instructive: triggering a
 collision needs two sub-plans sharing the same identifier, but **a sub-plan the door does not
 list makes the whole plan UNREADABLE** (`rc 1`) — the edge case refuses before ever reaching
 the fold. A hand-built door is rejected for yet another cause (the six fields). On the real
 tree: **0 collisions across 168 items**.

 **So this is NOT a witness, it is a declaration**: the branch exists, it reads correctly,
 and **nothing guards it**. *A lesson with no barrier is a wish, and the admission is the free,
 valid answer that stops a false barrier from being manufactured* — a witness that passed
 without exercising the branch would be worse than no witness at all.

 **AND IT MUST NOT COUNT AS COVERAGE — measured.** This check reads the SOURCE TEXT, so it
 **kills** the sabotage that DELETES the branch (`if collisions:` → `if False:`) and shows up as
 "KILLED" in a mutation battery. It would kill **nothing** for a defect that leaves the branch in
 place and breaks what it prints. *A text detector counts citations as instances* — here it
 counts one line of code as a guarantee of behavior. What it actually buys: nobody can REMOVE
 the branch silently. Nothing more.
 """
    from mnemosyne.runtime import carte_run

    source = (REPO / "system" / "lib" / "mnemosyne" / "runtime" / "carte_run.py").read_text(
        encoding="utf-8"
    )
    assert "if collisions:" in source, "the branch must exist, even if unproven"
    assert "MULTIPLE plans" in source, "and carry the message it would publish"
    assert carte_run.main is not None


def test_le_NIVEAU_ARC_nomme_ce_que_le_compte_GLOBAL_cache():
    """ **The 3rd component of the `*Produces*` — "by level: project → ARC → wave."** It existed
 in **no** output at all: `make carte` did not carry a single mention of an arc.

 **What it makes visible**: the global count reads a **FINISHED** arc exactly like a **NEVER
 OPENED** one. Here both are named — it is "what does not move" one level up, and it is the
 single most actionable piece of information on the plan.

 **"Never opened" = ALL its items are `a_faire`.** A single `pret` or `en_cours` takes it out
 — the orchestrator had counted one arc among the untouched ones while one of its items is
 `pret`. *An arc someone has already touched is not a never-opened arc, and confusing the two
 would send someone onto work already taken.*"""
    texte = "# PLAN — fixture\n\n## The steps\n\n"
    corps = "  *Produit* : x\n  *Fini quand* : c\n  *Dépend de* : AUCUNE\n  *Prérequis* : AUCUN\n"
    for ident, marque in (
        ("AA1", "\U00002705"), ("AA2", "\U00002705"),   # arc AA: FINISHED (and 2 letters — `ident[0]` would break it)
        ("B1", "\U00002B1C"), ("B2", "\U00002B1C"),     # arc B: NEVER OPENED
        ("C1", "\U0001F504"), ("C2", "\U00002B1C"),     # arc C: in progress — a single item taken is enough
    ):
        texte += f"- **{ident}** {marque} **Etape.**\n" + corps
    carte = lire(_lecture(texte))
    assert carte.arcs_total == 3, f"three arcs: AA, B, C — got {carte.arcs_total}"
    assert carte.arcs_finis == ("AA",), f"only AA is finished; got {carte.arcs_finis}"
    assert carte.arcs_vierges == ("B",), (
        f"only B is never opened — C carries an in-progress item; got {carte.arcs_vierges}"
    )
    ligne = next(ln for ln in rendre(carte, projet="f").splitlines() if ln.startswith("PAR ARC"))
    assert "3 arcs" in ligne and "1 fini (AA)" in ligne and "1 jamais ouvert (B)" in ligne
    assert "1 en cours" in ligne, f"and the rest is counted: {ligne!r}"


def test_le_niveau_ARC_tient_en_UNE_ligne_et_ne_fait_pas_GROSSIR_la_carte():
    """ **The bound is NON-NEGOTIABLE, and I already broke this clause once** by adding a
 section. Six components times three levels would triple the output; the item carries its own
 arbiter — *"depth where we're working, a summary everywhere else."* The arc level is therefore
 **a one-line summary**, bounded like its neighbors, no matter how many arcs there are."""
    peu = rendre(lire(_lecture(_plan(9, dependances=False))), projet="f").splitlines()
    lignes_arc = [ln for ln in peu if ln.startswith("PAR ARC")]
    assert len(lignes_arc) == 1, f"ONE line, not {len(lignes_arc)}"

    # 30 distinct arcs: the line must not list them all
    texte = "# PLAN — fixture\n\n## The steps\n\n"
    corps = "  *Produit* : x\n  *Fini quand* : c\n  *Dépend de* : AUCUNE\n  *Prérequis* : AUCUN\n"
    # The prefixes must be LETTERS: `Z0z1` would render every one of the thirty as arc `Z`
    # (measured -- my first fixture only carried ONE arc and the witness measured nothing).
    from string import ascii_uppercase

    for n in range(30):
        prefixe = ascii_uppercase[n // 26] + ascii_uppercase[n % 26]
        texte += f"- **{prefixe}1** \U00002B1C **Etape.**\n" + corps
    carte = lire(_lecture(texte))
    ligne = next(ln for ln in rendre(carte, projet="f").splitlines() if ln.startswith("PAR ARC"))
    assert len(carte.arcs_vierges) <= PROFONDEUR, "the list is BOUNDED like its neighbors"
    assert carte.arcs_vierges_caches, "and the rest is COUNTED, never silenced"
    assert f"+{carte.arcs_vierges_caches}" in ligne, f"the remainder must be STATED: {ligne!r}"


def test_l_ETIQUETTE_d_un_arc_est_ce_que_le_LECTEUR_connait():
    """ **REGRESSION REPORTED BY THE ORCHESTRATOR, measured between 07:41 and 08:26.** My fix for
 the COUNT had replaced arc letters with **file names**:

 before: 2 finis (F, K) · 3 jamais ouverts (C, D, J)
 after: 2 finis (05-l-enquete, prerequis) · 3 jamais ouverts (02-l-autosuffisance-…, …)

 Three casualties at once: unreadable (*a reader recognizes `C`, not `02-l-autosuffisance`*),
 the line went from **1 to 3 lines** — while my clause is about **size** — and an unrelated file
 started passing for an arc.

 *I fixed the count by breaking the names*: the same class as "a fix that repairs one shape by
 breaking the other," recorded two rounds earlier, under a different face.

 **THE LABEL IS NOT THE IDENTITY**: the arc is identified by its path (unique); what gets
 PRINTED is the **common prefix of its identifiers** — what the plan itself uses.

 What this witness covers stays true, but is **incomplete since 2026-08-15**: `lire`/
 `carte_par_arc` no longer call `_prefixe_commun` directly on the whole group -- they go through
 `_etiquette_de_arc` (majority vote by ident), for the reason and the witness given by
 `test_carte_par_arc_l_ETIQUETTE_survit_a_un_INTRUS` below."""
    from mnemosyne.production.carte import _prefixe_commun

    # the two real shapes, measured — and the rule must hold for BOTH
    assert _prefixe_commun(["C1", "C2", "C3"]) == "C", "FLAT plan: the arc letter"
    assert _prefixe_commun(["A02-1", "A02-10", "A02-11"]) == "A02", "TREE plan: the arc number"
    assert _prefixe_commun(["K1"]) == "K", "a single-item arc keeps its letter"
    # the ORDER trap: stripping the separator before looking for it used to return "A"
    assert _prefixe_commun(["A01-1", "A01-2"]) == "A01", "the separator is SEARCHED FOR before being stripped"
    assert _prefixe_commun([]) == "", "no items at all: no invented label"
    assert _prefixe_commun(["X1", "Y2"]) == "", "nothing in common: the caller falls back to the path"


# --------------------------------------------------------------------------------------------
# `carte_par_arc` (B4) — the per-arc view, NEVER TRUNCATED, with what each arc is waiting on
# --------------------------------------------------------------------------------------------


def test_carte_par_arc_ne_TRONQUE_JAMAIS_contrairement_a_Carte():
    """`Carte` is bounded to `PROFONDEUR` (SESSION context is the scarce resource, `B3`) --
    `ArcEtat` never is: a UI panel (`B4`) scrolls, it consumes no session context. Nine arcs,
    `PROFONDEUR=5`: `carte_par_arc` must return all NINE, not five plus a count."""
    assert PROFONDEUR < 9, "the clause only makes sense if the fixture exceeds Carte's bound"
    texte = "# PLAN — fixture\n\n## The steps\n\n"
    corps = "  *Produit* : x\n  *Fini quand* : c\n  *Dépend de* : AUCUNE\n  *Prérequis* : AUCUN\n"
    from string import ascii_uppercase

    for lettre in ascii_uppercase[:9]:
        texte += f"- **{lettre}1** \U00002B1C **Etape.**\n" + corps
    arcs = carte_par_arc(_lecture(texte))
    assert len(arcs) == 9, f"nine distinct arcs; got {len(arcs)}"
    assert all(isinstance(arc, ArcEtat) for arc in arcs), "each entry is an ArcEtat, not a bare dict"


def test_carte_par_arc_agrege_fait_en_cours_a_faire_et_l_etat():
    """Three arcs, three states — the same motif as `Carte` (finished/untouched/in-progress) but
    with NO truncation and with the detail (`fait`/`en_cours`/`a_faire`) `Carte` itself does not
    carry."""
    texte = "# PLAN — fixture\n\n## The steps\n\n"
    corps = "  *Produit* : x\n  *Fini quand* : c\n  *Dépend de* : AUCUNE\n  *Prérequis* : AUCUN\n"
    for ident, marque in (
        ("A1", "\U00002705"), ("A2", "\U00002705"),
        ("B1", "\U00002B1C"), ("B2", "\U00002B1C"),
        ("C1", "\U00002705"), ("C2", "\U0001F504"), ("C3", "\U00002B1C"),
    ):
        texte += f"- **{ident}** {marque} **Etape.**\n" + corps
    par_etiquette = {arc.etiquette: arc for arc in carte_par_arc(_lecture(texte))}
    assert par_etiquette["A"].etat == "fini"
    assert (par_etiquette["A"].fait, par_etiquette["A"].total) == (2, 2)
    assert par_etiquette["B"].etat == "vierge"
    assert (par_etiquette["B"].a_faire, par_etiquette["B"].fait) == (2, 0)
    assert par_etiquette["C"].etat == "en_cours"
    assert (par_etiquette["C"].fait, par_etiquette["C"].en_cours, par_etiquette["C"].a_faire) == (1, 1, 1)


def test_carte_par_arc_REUTILISE_file_d_attente_et_EXCLUT_les_items_EN_COURS_de_attend():
    """`attend` comes from `file_d_attente` (`B2`), not a second computation -- and it IGNORES
    `en_cours` items: they are already taken, the question "what is this arc waiting on" no longer
    applies to them (see `carte_par_arc`'s own docstring). Without the filter, the in-progress item
    would still carry a reason in `file_d_attente().ecartes` ("status 'in progress' — the question
    no longer applies"), and a leak would make the arc claim it is waiting on a STATUS, never a
    real dependency."""
    texte = (
        "# PLAN — fixture\n\n## The steps\n\n"
        "- **A1** \U00002B1C **Blocker.**\n  *Produit* : x\n  *Fini quand* : c\n"
        "  *Dépend de* : AUCUNE\n  *Prérequis* : AUCUN\n"
        "- **B1** \U00002B1C **Blocked, to do.**\n  *Produit* : x\n  *Fini quand* : c\n"
        "  *Dépend de* : A1\n  *Prérequis* : AUCUN\n"
        "- **B2** \U0001F504 **Blocked, in progress.**\n  *Produit* : x\n  *Fini quand* : c\n"
        "  *Dépend de* : A1\n  *Prérequis* : AUCUN\n"
    )
    par_etiquette = {arc.etiquette: arc for arc in carte_par_arc(_lecture(texte))}
    assert par_etiquette["B"].attend == ("waiting on A1",), (
        "B1 (still to do, blocked by A1) must be in it; B2 (in progress, same dependency) must NOT "
        f"be added; got {par_etiquette['B'].attend}"
    )


def test_carte_par_arc_demarrable_est_VRAI_des_QU_UN_SEUL_item_est_dans_la_file():
    """`demarrable` (`E2` -- "the current wave") reuses `file_d_attente(...).rangs`, the SAME pass
    as `attend`: an arc counts as soon as a SINGLE one of its items shows up there, never all of
    them."""
    texte = (
        "# PLAN — fixture\n\n## The steps\n\n"
        "- **A1** \U00002B1C **Free, nothing blocks it.**\n  *Produit* : x\n  *Fini quand* : c\n"
        "  *Dépend de* : AUCUNE\n  *Prérequis* : AUCUN\n"
        "- **B1** \U00002B1C **Blocked by A1.**\n  *Produit* : x\n  *Fini quand* : c\n"
        "  *Dépend de* : A1\n  *Prérequis* : AUCUN\n"
        "- **C1** \U00002705 **Already done, nothing left to start.**\n  *Produit* : x\n  *Fini quand* : c\n"
        "  *Dépend de* : AUCUNE\n  *Prérequis* : AUCUN\n"
        "- **D1** \U00002B1C **Free.**\n  *Produit* : x\n  *Fini quand* : c\n"
        "  *Dépend de* : AUCUNE\n  *Prérequis* : AUCUN\n"
        "- **D2** \U00002B1C **Blocked by A1, same arc as D1.**\n  *Produit* : x\n  *Fini quand* : c\n"
        "  *Dépend de* : A1\n  *Prérequis* : AUCUN\n"
    )
    par_etiquette = {arc.etiquette: arc for arc in carte_par_arc(_lecture(texte))}
    assert par_etiquette["A"].demarrable is True, "A1 is free: arc A is in the wave"
    assert par_etiquette["B"].demarrable is False, "B1 is blocked, the arc's only item: not in the wave"
    assert par_etiquette["C"].demarrable is False, "C1 is already done: nothing left to start"
    assert par_etiquette["D"].demarrable is True, "D1 alone is enough, even with D2 (same arc) blocked"


def test_carte_par_arc_l_ETIQUETTE_survit_a_un_INTRUS():
    """ **THE REAL REGRESSION, replayed as a fixture** (measured on the 2026-08-15 plan): an arc
 of eight `A*` items plus ONE ember (`BR1`, an ident sharing NOTHING with the other seven) used
 to make the old computation (`_prefixe_commun` applied to the WHOLE group) collapse to `""`
 and then to the arc's raw key -- here `grp`, at Mnémosyne a FILE PATH. `_etiquette_de_arc`
 (majority vote by ident) fixes it: eight votes for `A` against one for `BR`, the label stays
 `A`.

 The injected `arcs=` key simulates the PER-FILE grouping `carte_run` computes for a
 tree-shaped plan -- a text-only fixture cannot reproduce the bug on its own: with no `source`,
 an item groups by identifier PREFIX, and `BR1` would spontaneously land in its own arc instead
 of polluting `A1..A8`'s."""
    texte = "# PLAN — fixture\n\n## The steps\n\n"
    corps = "  *Produit* : x\n  *Fini quand* : c\n  *Dépend de* : AUCUNE\n  *Prérequis* : AUCUN\n"
    idents = [f"A{n}" for n in range(1, 9)] + ["BR1"]
    for ident in idents:
        texte += f"- **{ident}** \U00002B1C **Etape.**\n" + corps
    arcs_injectes = {ident: "grp" for ident in idents}
    (arc,) = carte_par_arc(_lecture(texte), arcs=arcs_injectes)
    assert arc.etiquette == "A", (
        f"eight votes for 'A' against one for 'BR': the label must stay 'A'; got {arc.etiquette!r}"
    )
    assert arc.total == 9, "all nine items stay COUNTED; the intruder is only excluded from the LABEL"


def test_la_LIGNE_des_arcs_tient_sur_UNE_ligne_sur_les_deux_plans_REELS(capsys, monkeypatch):
    """ The regression had pushed the line from **1 to 3** — and the item's clause is about
 SIZE. The witness pulls **both real plans**, not a fixture."""
    from mnemosyne.runtime import carte_run

    for pour in (None, str(SIBLING_PROJECT)):
        if pour is None:
            monkeypatch.delenv("POUR", raising=False)
        else:
            monkeypatch.setenv("POUR", pour)
        assert carte_run.main([]) == 0
        lignes = [ln for ln in capsys.readouterr().out.splitlines() if ln.startswith("PAR ARC")]
        assert len(lignes) == 1, f"ONE line, not {len(lignes)} (POUR={pour})"
        assert len(lignes[0]) < 200, f"and it must stay readable: {len(lignes[0])} characters"


def test_le_NIVEAU_ARC_est_JUSTE_sur_les_DEUX_formes_de_plan(capsys, monkeypatch):
    """ **THE DEFECT I SHIPPED, FOUND BY PULLING MY OWN SURFACE ON THE OTHER POPULATION.**

 The map announced **"3 arcs"** for the sibling project's plan, **which carries 14**: I was deriving the arc
 from the **identifier prefix**, and `A01-1`, `A03-5`, `A11-2` all collapse onto "A".

 **Three readings give THREE answers, measured**: the prefix → **3** · the `source` file →
 **149** (the sibling project carries one file per item at leaf level) · **the sub-plans → 14**, and that is
 what the plan itself calls an arc (*"# PLAN — ARC 11 — …"*).

 **The prefix gave 11/11 on Mnémosyne** — right exactly where I had tested it, wrong exactly
 where the clause applies. *A derivation that works on the shape in front of you is not a
 derivation: it is a coincidence of shape.*

 **And my first fix broke the other shape**: injecting the sub-plan on a FLAT plan (a single
 door) returned "1 arcs" for 11. *A fix that repairs one shape by breaking the other has not
 fixed anything, it has only moved it.* This witness therefore pulls **both**."""
    from mnemosyne.runtime import carte_run

    def compte(sortie: str) -> int:
        ligne = next(ln for ln in sortie.splitlines() if ln.startswith("PAR ARC"))
        return int(ligne.split()[3])

    monkeypatch.delenv("POUR", raising=False)
    assert carte_run.main([]) == 0
    plat = compte(capsys.readouterr().out)
    attendu_plat = len({i.source for i in read_plan_tree(REPO / "docs", "M")[0].reading.items})
    assert plat == attendu_plat, (
        f"FLAT plan: {plat} arcs announced for {attendu_plat} arc files"
    )

    monkeypatch.setenv("POUR", str(SIBLING_PROJECT))
    assert carte_run.main([]) == 0
    arbre = compte(capsys.readouterr().out)
    attendu_arbre = len([p for p in read_plan_tree(SIBLING_PROJECT, "A") if p.reading and p.reading.items])
    assert arbre == attendu_arbre, (
        f"TREE plan: {arbre} arcs announced for {attendu_arbre} sub-plans"
    )
    assert arbre != plat, "the two shapes must differ — otherwise this witness only measures one"


def test_la_LIGNE_RENDUE_porte_le_parallelisable_pas_le_total():
    """ Found by sabotage: replacing `carte.parallelisable` with `carte.total` **in the rendered
 line** still left **32/32 green**. *All my witnesses asserted on the DATACLASS; none read the
 sentence the operator reads.* A correct computation rendered by a wrong display reads exactly
 like a wrong computation."""
    carte = lire(_lecture(_plan(30)))
    ligne = next(ln for ln in rendre(carte, projet="f").splitlines() if "PARALLÉLISABLE" in ln)
    assert f": {carte.parallelisable} maintenant" in ligne, (
        f"the line must carry the parallelizable count ({carte.parallelisable}), nothing else: {ligne!r}"
    )
    assert carte.parallelisable != carte.total, (
        "and the population must DIFFERENTIATE the two — otherwise the witness would pass with the total too"
    )


def test_l_EN_TETE_annonce_la_borne_REELLEMENT_appliquee():
    """ `rendre` read the CONSTANT while `lire` was bounding with its PARAMETER:
 `lire(rd, profondeur=2)` rendered two lines under a header promising five.
 *A header that describes a constant instead of what was actually done is a title that lies —
 and a title is taken at its word, it is not recounted.*"""
    lecture = _lecture(_plan(30))
    rendu = rendre(lire(lecture, profondeur=2), projet="f")
    assert "les 2 premiers" in rendu, f"the header must announce 2: {rendu.splitlines()[5]!r}"
    rangs = [ln for ln in rendu.splitlines() if ln.startswith("   ") and ". " in ln[:8]]
    assert len(rangs) == 2, f"and it must show 2 of them; it shows {len(rangs)}"
    assert f"les {PROFONDEUR} premiers" in rendre(lire(lecture), projet="f"), "the default stays 5"


def test_un_item_EN_COURS_n_est_ni_a_commencer_ni_immobile():
    """ Found by sabotage: widening `_A_FAIRE` to include `en_cours` still left **32/32 green**.

 An item **in progress** is already taken by someone. Counting it in "where to start" would
 send two people onto the same work, and counting it in "what does not move" would say the
 opposite of the truth. *The status decides the POPULATION before any clause is even applied —
 so a status mis-sorted skews every section at once.*"""
    texte = (
        "# PLAN — fixture\n\n## The steps\n\n"
        "- **P** \U0001F504 **Somebody already holds it.**\n  *Produit* : x\n  *Fini quand* : c\n"
        "  *Dépend de* : AUCUNE\n  *Prérequis* : AUCUN\n"
        "- **Q** \U00002B1C **Free.**\n  *Produit* : x\n  *Fini quand* : c\n"
        "  *Dépend de* : AUCUNE\n  *Prérequis* : AUCUN\n"
    )
    carte = lire(_lecture(texte))
    assert dict(carte.par_statut).get("en_cours") == 1, "the fixture must carry one in-progress item"
    assert [r.ident for r in carte.tete] == ["Q"], (
        f"an in-progress item is not startable; the queue returns {[r.ident for r in carte.tete]}"
    )
    assert carte.immobile == ("Q",), f"nor motionless; got {carte.immobile}"


def test_un_item_que_PERSONNE_n_attend_n_entre_pas_dans_LE_PLUS_ATTENDU():
    """ Found by sabotage: dropping the `if n` filter still left **32/32 green** — and the
 section titled "WHAT IS MOST AWAITED" would have started listing items awaited by **zero**.
 *A title that lies about its content manufactures the wrong reading, and this one reads in one
 second: "here is what's blocking" on a list that blocks nothing.*"""
    carte = lire(_lecture(_plan(9)))  # 1 dependency out of 7: most items are awaited by 0
    attendus_par_zero = [ident for ident, n in carte.bloqueurs if n == 0]
    assert not attendus_par_zero, (
        f"the section only lists what IS awaited; it carries {attendus_par_zero}"
    )
    assert carte.bloqueurs, "and it is not empty on this population — otherwise nothing is measured"


def test_un_item_QU_ON_ATTEND_n_est_jamais_dit_immobile_lui_non_plus():
    """ **THE OTHER HALF OF THE AND, and it SURVIVED the sabotage.** The clause has two members:
 *nobody is waiting on it* **and** *it is not waiting on anyone*. A neighboring witness closes
 the second; dropping the FIRST (`not ordre.debloque(...)`) still left **32/32 green**.

 The population must make both members **separately observable**: it needs an item still
 **to do** that someone is waiting on — a item would be excluded by its status before ever
 reaching the clause, and the witness would measure the filter instead of the AND."""
    texte = (
        "# PLAN — fixture\n\n## The steps\n\n"
        "- **D** \U00002B1C **To do, and SOMEBODY is waiting on it.**\n  *Produit* : x\n  *Fini quand* : c\n"
        "  *Dépend de* : AUCUNE\n  *Prérequis* : AUCUN\n"
        "- **E** \U00002B1C **It waits on D.**\n  *Produit* : x\n  *Fini quand* : c\n"
        "  *Dépend de* : D\n  *Prérequis* : AUCUN\n"
        "- **Z** \U00002B1C **Nobody waits on it, it waits on nobody.**\n  *Produit* : x\n"
        "  *Fini quand* : c\n  *Dépend de* : AUCUNE\n  *Prérequis* : AUCUN\n"
    )
    carte = lire(_lecture(texte))
    assert "D" not in carte.immobile, "D is AWAITED by E: it is in the current"
    assert "E" not in carte.immobile, "E is WAITING on D: it is in the current too"
    assert carte.immobile == ("Z",), f"only Z is out of the current; got {carte.immobile}"


def test_le_REEL_confirme_la_clause_reparee_un_seul_item_hors_du_courant():
    """The real-population counter-test: the auditor, with their own tool, measured *"genuinely
 out of the current: 1: ['A4']."* The fixed map must say the same thing.

 **ADJUSTED (D4/I1, 2026-08-15)**: embers (`BR*`, `signalements._PREFIXE_BRAISE`) are
 motionless *BY CONSTRUCTION* -- `*Dépend de* : AUCUNE` and nothing waits on them, a property
 D4/I1 already proved and had audited three times, not a regression of this witness. Their
 count will grow with every new signalement converted (that is the mechanism's whole point), so
 the witness EXCLUDES them rather than bounding a total that would need raising on every
 checkout. Measured at `profondeur=1000` (no truncation) on 2026-08-15: outside embers, 0
 motionless items."""
    plans = read_plan_tree(REPO / "docs", "Mnémosyne")
    carte = lire(plans[0].reading, profondeur=1000)
    hors_braises = tuple(i for i in carte.immobile if not i.startswith(_PREFIXE_BRAISE))
    assert len(hors_braises) + carte.immobile_cache <= 3, (
        f"the section announced 18 items before the fix; it returns {hors_braises} "
        f"(embers excluded: {[i for i in carte.immobile if i.startswith(_PREFIXE_BRAISE)]})"
    )


# --------------------------------------------------------------------------------------------
# "WHAT'S EXPIRING" — the *Produces* component that shipped NOWHERE
# --------------------------------------------------------------------------------------------


def test_l_OBLIGATION_de_niveau_1_est_CABLEE_le_hook_INVOQUE_le_runner():
    """ **`B3`'S `*Obligation*` SAYS "level 1 — pushed by `SessionStart`."** It was NOT: an
 isolated audit measured `grep -rn carte .claude/hooks/` → **nothing**. The manual target
 existed and worked; the PUSHED half did not exist. *An obligation written down that no caller
 ever pulls is a wish, not a level 1.*

 **This witness judges the INVOCATION, not the word.** A plain `assert "carte" in hook` would
 pass on my own comment block alone — *a text detector counts citations as instances.* Comment
 lines are stripped out before searching for the module."""
    hook = (REPO / ".claude" / "hooks" / "session-start.sh").read_text(encoding="utf-8")
    executables = [
        ligne for ligne in hook.splitlines() if not ligne.lstrip().startswith("#")
    ]
    assert any("mnemosyne.runtime.carte_run" in ligne for ligne in executables), (
        "the hook must INVOKE the map's runner, not merely name it in a comment"
    )


def test_le_hook_reste_FAIL_OPEN_meme_si_la_carte_casse(tmp_path, monkeypatch):
    """ *A hook that breaks STAYS SILENT* — that is what the `*Obligation*` itself says, and it
 is exactly why `make carte` must remain pullable by hand. The witness checks that the map has
 not turned a fail-open channel into a gate: a failing runner must not fail the hook."""
    import subprocess

    hook = REPO / ".claude" / "hooks" / "session-start.sh"
    ligne = next(
        ln for ln in hook.read_text(encoding="utf-8").splitlines()
        if "mnemosyne.runtime.carte_run" in ln and not ln.lstrip().startswith("#")
    )
    assert ligne.lstrip().startswith("if ! "), (
        f"the invocation must be guarded by `if !` like its neighbors; line = {ligne!r}"
    )
    # and the whole hook returns 0 on this repository
    rc = subprocess.run(["bash", str(hook)], capture_output=True, cwd=str(REPO)).returncode
    assert rc == 0, "the SessionStart hook is fail-open: it must never block a session"


def test_une_PEREMPTION_declaree_remonte_l_item_en_TETE_avec_son_horloge():
    """ **The `*Produces*` component that did not exist.** `carte.lire` did pass `perissables` to
 `file_d_attente` — the wiring was correct — but **no caller ever populated it**: the
 `PERISHABLE` branch and the line's `` were **unreachable through `make carte`**.

 And this is NOT one more section: the mechanism already lives in `B2`, it only needed its
 population. *My last added section had pushed the sibling project's map from 28 to 33 lines and broken its
 own clause* — this one adds no line at all."""
    lecture = _lecture(_plan(9, dependances=False))
    sans = lire(lecture)
    assert not any(getattr(r, "perissable", False) for r in sans.tete), "no expiry declared at all"

    avec = lire(lecture, perissables={"F8": "window closes on 2026-09-01"})
    assert avec.tete[0].ident == "F8", (
        f"an expiring item moves in FRONT of the most-awaited one; the queue returns {[r.ident for r in avec.tete]}"
    )
    rendu = rendre(avec, projet="fixture")
    assert "\U000023F3" in rendu, "and its line carries the clock"
    assert _TETE_PERISSABLE in rendu and "2026-09-01" in rendu, (
        "and its REASON, written out, not a bare rank"
    )


def test_une_raison_TRONQUEE_dit_qu_elle_l_est():
    """ The "reason" column used to truncate **silently**, in a module whose docstring promises
 the opposite — while `plan_ordre`, to its credit, adds ` …` in the same case.

 **What surfaced it**: an EXPIRY's reason, the one field the item demands spelled out in
 full, was losing its date. *A silent cut eats, first, whatever was written with the most
 care.*"""
    longue = "window closes on 2026-09-01 and nothing ever reopens it, measured on 14 August"
    rendu = rendre(lire(_lecture(_plan(9, dependances=False)), perissables={"F8": longue}),
                   projet="fixture")
    ligne = next(ln for ln in rendu.splitlines() if "\U000023F3" in ln)
    assert ligne.rstrip().endswith("…"), f"a cut reason must SAY so: {ligne!r}"


def test_la_TAILLE_ne_bouge_pas_quand_une_peremption_est_declaree():
    """ The item's clause comes before everything: shipping one component must not make the map
 GROW. Measured — this is exactly the trap I fell into with the "AMPUTATED ORDER" section."""
    lecture = _lecture(_plan(168))
    sans = len(rendre(lire(lecture), projet="f").splitlines())
    avec = len(rendre(lire(lecture, perissables={"F3": "raison"}), projet="f").splitlines())
    assert sans == avec, f"{sans} lines with no expiry, {avec} with one — the map grew"


def test_une_entree_SANS_RAISON_n_entre_pas_dans_la_declaration():
    """ *A list with no reason keeps growing on its own, and that is how a priority list turns
 into a junk drawer* — the rule already written above the sibling project's own table. A bare-identifier line is
 **ignored**, never accepted empty."""
    texte = (
        "# PÉREMPTION\n\n"
        "- A03-4 : the vintages not captured cannot be rebuilt\n"
        "- `B7` : the archive window closes again\n"
        "- C9 :\n"
        "- D2\n"
        "some text that is not an entry\n"
    )
    lu = lire_peremption(texte)
    assert set(lu) == {"A03-4", "B7"}, f"only entries WITH a reason enter; got {lu}"
    assert lu["B7"] == "the archive window closes again", "the backticks are not part of the ident"


def test_le_BORD_lit_la_declaration_et_NOMME_une_peremption_PERIMEE(tmp_path, monkeypatch, capsys):
    """ An identifier declared as expiring but **absent from the plan** would vanish silently:
 `file_d_attente` ignores what it does not know. *A stale declaration that reddens nowhere is
 exactly the class this repository spends its nights closing.*"""
    from mnemosyne.runtime import carte_run

    shutil.copy2(SIBLING_PROJECT / "PLAN.md", tmp_path / "PLAN.md")
    shutil.copytree(SIBLING_PROJECT / "plan", tmp_path / "plan")
    # the target item is chosen FROM the queue: one still-blocked expiring item would not enter
    # it, and the witness would measure the filter instead of the wiring.
    from mnemosyne.production.carte import lire, replier

    plans = read_plan_tree(tmp_path, "X")
    lectures = [pl.reading for pl in plans if pl.reading is not None and pl.reading.items]
    premier = lire(replier(lectures)[0]).tete[0].ident
    (tmp_path / carte_run.NOM_DE_LA_PEREMPTION).write_text(
        f"- {premier} : les millesimes non captes ne se reconstruisent pas\n"
        "- ZZ-INEXISTANT : cet item n'est dans aucun plan\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("POUR", str(tmp_path))
    assert carte_run.main([]) == 0
    capture = capsys.readouterr()
    assert "ZZ-INEXISTANT" in capture.err, "an expiry targeting an absent ident must be NAMED"
    assert premier not in capture.err, "and the one targeting a real item must NOT be flagged"
    # **THIS ASSERTION WAS EMPTY — an isolated audit showed it.** It read
    # `"" in out or "A03-4" not in out`: the second member is TRUE as soon as the item is not
    # displayed at all, so the disjunction passed **without ever requiring the clock**. Measured
    # result: unplugging `perissables=` from the edge case still left **40/40 green**, and the
    # component became unreachable through `make carte` again -- exactly the defect this file
    # claims to close. *An `or` whose one member is almost always true is an assertion that never
    # actually runs.*
    # We therefore REQUIRE the clock, on an item chosen SPECIFICALLY to sit at the front of the queue.
    assert "\U000023F3" in capture.out, (
        f"the edge case must have READ the declaration and rendered the clock; output = {capture.out[:400]!r}"
    )
    assert _TETE_PERISSABLE in capture.out, "and the written reason with it"


def test_le_fichier_LIVRE_ne_declare_AUCUNE_peremption():
    """ **AN ISOLATED AUDIT'S BLOCKER, and it lived in the file I HAD WRITTEN.**

 The expiry-declaration document documents the shape inside a closed ```` ```markdown ```` block; its two
 example lines were read as **real declarations**. The command announced *"2 expiry
 declaration(s) on an ABSENT identifier,"* and on a plan where one of the two actually exists,
 the item **jumped to rank 1** — with a reason **manufactured from documentation prose**. The
 file itself states, three sections further down, *"why this file is EMPTY today"*: it was not.

 **And the barrier already existed in this repository, written that very night**
 (`obligation.hors_blocs`, fixed for this exact class). *Recording a lesson does not apply it —
 and a lesson whose barrier is already built gets re-violated by not looking at what is already
 at hand.*

 This witness guards the FILE, not just the function: it is the file that gets shipped."""
    from mnemosyne.runtime import carte_run

    texte = (REPO / "docs" / carte_run.NOM_DE_LA_PEREMPTION).read_text(encoding="utf-8")
    assert "```" in texte, "the file must genuinely carry a fenced example — otherwise nothing is tested"
    assert lire_peremption(texte) == {}, (
        f"the shipped file declares {lire_peremption(texte)} — its examples are read as real"
    )


def test_un_exemple_en_BLOC_CLOS_ne_declare_rien():
    """The same class, at the function level: a closed block is pedagogy, never an order."""
    texte = (
        "# PÉREMPTION\n\n## The shape\n\n```markdown\n"
        "- EXAMPLE-1 : this one is an example\n```\n\n"
        "- REAL-1 : this one is a genuine declaration\n"
    )
    assert lire_peremption(texte) == {"REAL-1": "this one is a genuine declaration"}


def test_le_depot_porte_sa_SURFACE_de_declaration():
    """*A document nothing points to does not exist* — and a mechanism whose entry point nobody
    knows is not shipped. The file may be EMPTY of entries; it may not be missing."""
    from mnemosyne.runtime import carte_run

    fichier = REPO / "docs" / carte_run.NOM_DE_LA_PEREMPTION
    assert fichier.is_file(), f"{fichier} must exist — it is this component's surface"
    assert "se RATTRAPE" in fichier.read_text(encoding="utf-8"), "and carry the test that decides"


def test_un_SOUS_PLAN_illisible_est_NOMME_et_le_compte_dit_qu_il_l_exclut(tmp_path, monkeypatch, capsys):
    """ **The SECOND audit's blocker.** The fold used to silently drop any unreadable sub-plan: a
 single invalid byte in one of the sibling project's arcs, and the command returned `rc 0`, "14 plans folded ·
 **167** steps" — **not a word** — for 168. The refusal existed, named, inside
 `reading.problems`, and **nobody was reading it**. *A guarantee dies at the caller that throws
 away its result.*

 We NAME it and still draw: refusing outright would blind us to the healthy arcs over a single
 broken one. But a count silent about what it lost is worse than a refusal."""
    from mnemosyne.runtime import carte_run

    # **THE REAL TREE, WHOLE.** Two smaller fixtures failed before this one, and their failure
    # teaches something: **the DOOR's own readability depends on its sub-plans being present**
    # (its items point at `source:` paths that must exist). A door copied alone is therefore judged
    # unreadable for a cause that has nothing to do with the defect under test. *A fixture rejected
    # for a DIFFERENT cause than the one under test returns a red that says nothing about the
    # defect.*
    shutil.copy2(SIBLING_PROJECT / "PLAN.md", tmp_path / "PLAN.md")
    shutil.copytree(SIBLING_PROJECT / "plan", tmp_path / "plan")
    # **THE LEAF, NOT THE ARC'S OWN DOOR** — third fixture, and the measurement is what settled
    # it: emptying an arc's `PLAN.md` loses NOTHING (its items live in its leaves, 168 stays 168).
    # The defect reproduces on an ITEM file. *Breaking at the wrong level measures a different
    # mechanism and returns a green that looks like proof.*
    feuilles = sorted((tmp_path / "plan" / "07-analyse-par-algorithme" / "plan").glob("*.md"))
    assert feuilles, "the chosen arc must carry leaves in the real tree"
    with feuilles[0].open("ab") as fichier:
        fichier.write(b"\xff\xfe")

    monkeypatch.setenv("POUR", str(tmp_path))
    assert carte_run.main([]) == 0, "a single broken arc must not blind the healthy ones"
    capture = capsys.readouterr()
    assert "ECARTE" in capture.err, f"the broken sub-plan must be NAMED; stderr = {capture.err!r}"
    assert "07-analyse-par-algorithme" in capture.err
    # `capture.out` carries `str(tmp_path)` (the "CARTE — …" banner and the drift/routage
    # refusal, see `carte_run.py`) — and pytest names its temp folders with a counter that CAN
    # contain "168" by coincidence. The path is therefore stripped out BEFORE judging: otherwise
    # this witness would stop measuring the displayed count and start measuring pytest's own temp
    # directory counter.
    hors_chemin = capture.out.replace(str(tmp_path), "")
    assert "168" not in hors_chemin, "and the displayed count must no longer claim 168"
    assert "NE LES COMPTENT PAS" in capture.err, "and the reader must know the count excludes it"


def test_PARALLELISABLE_compte_ce_que_la_FILE_juste_en_dessous_contient():
    """ **Wrong in BOTH directions, and my first fix only corrected one.**

 The original draft counted `vagues[0]` whole, so the items were in it ("8 now" above a
 queue of 2). I filtered out the done items — and the second audit measured the SYMMETRIC
 defect that filter left in place: `vagues[0]` only contains items with NO declared dependency
 at all, so an item whose only dependency is is startable and **is not in it**. Measured on
 this repository's own plan: "**1 now**" above a queue of **15**.

 *Two opposite-sign errors on the same number say the SOURCE is wrong, not that a filter is
 missing.* The queue IS the answer; `vagues[0]` answers a different question."""
    carte = lire(_lecture(_plan_dependant()))
    assert carte.parallelisable == len(carte.tete) + carte.tete_cachee, (
        f"the line announces {carte.parallelisable} above a queue of "
        f"{len(carte.tete) + carte.tete_cachee}"
    )
    # THE DIFFERENTIATION: B is NOT in `vagues[0]` (it declares a dependency), and it MUST be
    # counted — its dependency A is done. Without this assertion the witness would also pass with
    # the old source, which returned 1 instead of 2.
    from mnemosyne.production.plan_ordre import ordonner

    lecture = _lecture(_plan_dependant())
    assert "B" not in (ordonner(lecture).vagues[0] if ordonner(lecture).vagues else ()), (
        "B declares a dependency: it is not in the first topological wave"
    )
    assert "B" in [r.ident for r in carte.tete], "and yet it is startable — A is done"
    assert carte.parallelisable == 2, f"B and C are startable; got {carte.parallelisable}"


def test_PARALLELISABLE_n_est_pas_le_compte_des_items_DEJA_FAITS():
    """ **THIS WITNESS WAS FREEZING THE WRONG NUMBER, and a third party showed it.**

 It asserted `parallelisable == 1` explaining *"B is waiting on A"* — **wrong**: `A` is , so
 `B` is startable. And **forty lines above, the very same file** already asserted that `B` is
 in the queue. *Two witnesses in the same file can contradict each other with nothing turning
 red, as long as neither measures what the other measures.*

 What it must hold is the ORIGINAL defect, nothing more: a **DONE** item does not count as
 parallelizable. Measured on a population where it is observable — three done items, one
 remaining."""
    lignes = ["# PLAN — fixture", "", "## The steps", ""]
    for n in range(4):
        marque = "\U00002705" if n < 3 else "\U00002B1C"
        lignes += [
            f"- **F{n}** {marque} **Step {n}.**",
            "  *Produit* : x",
            "  *Fini quand* : c",
            "  *Dépend de* : AUCUNE",
            "  *Prérequis* : AUCUN",
        ]
    carte = lire(_lecture("\n".join(lignes) + "\n"))
    assert carte.parallelisable == 1, (
        f"three items done, one left: the answer is 1, not {carte.parallelisable}"
    )


# ------------------------------------------------------------------------------------------------
# E1 -- `plan_ordre.lots()` EXISTED AND HAD NO CALLER (found while measuring H5, routed here)
# ------------------------------------------------------------------------------------------------

#: A and B name the SAME `*Produces*` (x.py) -- they CANNOT share a batch. C is independent. All
#: three carry no dependency: startable from the first wave.
_PLAN_COLLISION = (
    "# PLAN — fixture\n\n## The steps\n\n"
    "- **A** \U00002B1C **One.**\n  *Produit* : `x.py`\n  *Fini quand* : c\n"
    "  *Dépend de* : AUCUNE\n  *Prérequis* : AUCUN\n"
    "- **B** \U00002B1C **Two, same file as A.**\n  *Produit* : `x.py`\n  *Fini quand* : c\n"
    "  *Dépend de* : AUCUNE\n  *Prérequis* : AUCUN\n"
    "- **C** \U00002B1C **Three, different file.**\n  *Produit* : `y.py`\n  *Fini quand* : c\n"
    "  *Dépend de* : AUCUNE\n  *Prérequis* : AUCUN\n"
)


def test_parallelisable_lots_DISTINGUE_le_compte_d_items_du_compte_de_LOTS():
    """`parallelisable` counts startable ITEMS; `parallelisable_lots` counts the COLLISION-FREE
    BATCHES they partition into -- two distinct numbers as soon as two startable items share a
    path in their `*Produces*`. Three items, TWO batches (A and B collide on `x.py`, C is alone):
    the raw count cannot express that difference."""
    carte = lire(_lecture(_PLAN_COLLISION))
    assert carte.parallelisable == 3, f"A, B, C are all startable; got {carte.parallelisable}"
    assert carte.parallelisable_lots == 2, (
        f"A and B collide on x.py, C is alone: 2 batches expected, got "
        f"{carte.parallelisable_lots}"
    )


def test_parallelisable_lots_MORD_prouve_par_SABOTAGE(monkeypatch):
    """*I never assert the passing case.* Direct sabotage at the call site: a stub that always
    returns a single batch, regardless of the real collision. If `lire()` computes
    `parallelisable_lots` through a different path than the `lots` name this module imports, the
    sabotage changes nothing and this witness does not bite."""
    import mnemosyne.production.carte as carte_module
    from mnemosyne.production.plan_ordre import Lots

    def _stub_un_seul_lot(reading, vague):
        return Lots(lots=(tuple(sorted(vague)),), separees=())

    monkeypatch.setattr(carte_module, "lots", _stub_un_seul_lot)
    carte = lire(_lecture(_PLAN_COLLISION))
    assert carte.parallelisable_lots == 1, (
        "the sabotaged stub must drop the count to 1 -- otherwise carte.py is not calling the "
        "function that was just sabotaged, and the wiring is only an appearance"
    )


def test_la_ligne_PARALLELISABLE_rendue_porte_les_DEUX_chiffres():
    """Non-regression + rendering: the text line must carry the item count (already covered by
    `test_la_LIGNE_RENDUE_porte_le_parallelisable_pas_le_total`, unchanged) AND now the batch
    count -- one must not stand in for the other."""
    carte = lire(_lecture(_PLAN_COLLISION))
    ligne = next(ln for ln in rendre(carte, projet="f").splitlines() if "PARALLÉLISABLE" in ln)
    assert f": {carte.parallelisable} maintenant" in ligne, ligne
    assert f"({carte.parallelisable_lots} lot(s) sans collision)" in ligne, ligne


def test_le_CYCLE_annonce_son_compte_COMPLET_pas_celui_du_tuple_tronque():
    """ **SERIOUS #4.** `rendre` was printing `len(carte.cycle)` — the length **already bounded**.
 The auditor's measurement: 10,000 steps all caught in one cycle, announced as **5**. It was the
 only section that truncated with no stated remainder, in a module whose docstring promises the
 opposite."""
    n = PROFONDEUR + 4
    lignes = ["# PLAN — fixture", "", "## The steps", ""]
    for k in range(n):  # a closed loop: each depends on the next, the last on the first
        lignes += [
            f"- **F{k}** \U00002B1C **Step {k}.**",
            "  *Produit* : x",
            "  *Fini quand* : c",
            f"  *Dépend de* : F{(k + 1) % n}",
            "  *Prérequis* : AUCUN",
        ]
    carte = lire(_lecture("\n".join(lignes) + "\n"))
    assert carte.cycle_total == n, f"{n} unreachable steps, the map counts {carte.cycle_total}"
    assert len(carte.cycle) == PROFONDEUR, "the LIST stays bounded — it is the COUNT that is complete"
    rendu = rendre(carte, projet="fixture")
    assert f"{n} étape(s) inatteignables" in rendu
    assert f"et {n - PROFONDEUR} autre(s)" in rendu, "and it STATES its remainder, like its neighbors"


def test_le_MOT_dit_ce_que_le_CHIFFRE_mesure_et_rien_de_plus():
    """ "unblocks N" WAS LYING: it is the out-degree — how many items DECLARE this one — not how
 many would actually become STARTABLE. Measured on this repository's own plan: `B1` is
 **awaited by 9** and makes **0** startable, because all nine have a second, still-open
 dependency. *Lifting one dependency only unblocks the items for which it was the LAST one.*

 The orchestrator had published "A1 unblocks 16" in two dashboards; the tool answers 10.
 The effective number is NOT published: it requires recomputing the queue once per blocker —
 **20s for five out of 10,000 items**. Renaming costs zero; recomputing kills a surface pushed
 at the start of every session.

 **This witness's declared scope**: the REASON on each rank is composed by `plan_ordre.py`
 — another chat's own batch — and it still reads "unblocks N." This witness therefore only
 arms **the map's own columns**, the ones I own. The rest is flagged, not fixed here.
 """
    rendu = rendre(lire(_lecture(_plan(60))), projet="fixture")
    porteuses = [ligne for ligne in rendu.splitlines() if "attendu par" in ligne]
    assert porteuses, "the map must publish the metric"
    assert "attendu(s) par au moins" in rendu, "and the remainder line uses the same word"
    # THE ASSERTION THAT DECIDES, AND IT COVERS THE WHOLE OUTPUT. The previous version split
    # each line with `split("  ", 3)[:3]` believing it isolated the columns; measured by the
    # auditor on a real line, it returns `['', ' 1. F1000', '']` — **the column is NEVER in
    # there**. The assertion was therefore empty no matter which word got printed: two sabotages
    # that reintroduced "unblocks" into the queue column AND into the blockers column both passed,
    # 13/13. *Searching inside a substring you never measured is asserting on nothing; we search
    # the WHOLE output.*
    assert RACINE_DU_MOT not in rendu, (
        "no part of the map — column, reason, title, or remainder line — must promise an "
        f"effective unblocking; found in: "
        f"{[ln for ln in rendu.splitlines() if RACINE_DU_MOT in ln]}"
    )


@pytest.mark.parametrize("section", ["OÙ ON EN EST", "CE QUI EST PARALLÉLISABLE", "PAR OÙ COMMENCER"])
def test_la_carte_porte_les_sections_que_le_Produit_nomme(section):
    """The `*Produces*` enumerates them; a map missing one would still pass the size bound."""
    assert section in rendre(lire(_lecture(_plan(20))), projet="fixture")


def test_la_PROFONDEUR_est_la_meme_pour_toutes_les_sections():
    """One bound per section, a single value: two bounds drifting apart is how the map grows."""
    carte = lire(_lecture(_plan(500)))
    assert len(carte.tete) <= PROFONDEUR
    assert len(carte.bloqueurs) <= PROFONDEUR
    assert len(carte.immobile) <= PROFONDEUR
