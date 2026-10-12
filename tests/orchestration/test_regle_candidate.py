"""I3(a) - a rule invented by a project names the MEASURED failure it prevents.

 **THE FORM IS REUSED, NOT INVENTED**: `**Panne :**` is the sister of `**Barriere :**`, already
judged by `runtime/memoire.py` on lessons. *Inventing a second form for the same idea would be
the duplication the doctrine forbids.*

 **POPULATION MEASURED BEFORE WRITING** (`knowledge/proposals/`): **13 records**, of which **7
books** (out of scope for the clause), **6 candidate rules**, **0 declaring a failure**, **6 at
`status: draft`**. Hence the point where the clause bites - **promotion**, never the filing of a
draft: it would otherwise refuse **6 out of 6**, and *a catch rate with no false refusal is a
wall*.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mnemosyne.production import regle_candidate as rc

from _invariants import REPO_ROOT

REGLE = (
    "# Proposition\n\n**Panne :** le graphe se reconstruit pour chaque item — 31 s au lieu de 5.\n"
)


# ---- READING: what the record DECLARES ---------------------------------------------------------
def test_une_panne_CHIFFREE_est_lue_et_promouvable() -> None:
    c = rc.lire(REGLE, source="x.md")
    assert c.declaree and c.mesuree and not c.avouee and c.promouvable


def test_l_AVEU_est_une_reponse_VALIDE_et_GRATUITE() -> None:
    """ THE HEART OF THE DESIGN, and it comes from A2: without this branch, an author with no
 measurement would write any number at all to get through the gate. *A quota per record
 manufactures content.*"""
    c = rc.lire("**Panne :** AUCUNE MESURÉE — le motif vient d'une seule session.\n", source="x.md")
    assert c.declaree and c.avouee and not c.mesuree
    assert c.promouvable, "the admission must PASS, otherwise the clause manufactures failures"


def test_une_panne_SANS_chiffre_est_declaree_mais_PAS_promouvable() -> None:
    """The two halves are distinct: *declared* and *measured* are not the same fact."""
    c = rc.lire("**Panne :** ça finit toujours par mal se passer.\n", source="x.md")
    assert c.declaree and not c.mesuree and not c.avouee and not c.promouvable


def test_une_fiche_SANS_declaration_ne_declare_RIEN() -> None:
    c = rc.lire("# Proposition\n\nUne bonne idée, sans plus.\n", source="x.md")
    assert not c.declaree and not c.promouvable


def test_un_ENTIER_NU_n_est_PAS_une_mesure() -> None:
    """ *A name is not a test*, and a bare number is not a measurement: *"la panne 2"* ("failure
 2") would just cite a number. The real population always writes its unit (`11 004 lignes`,
 `2 sur 7`, `9,7 %`)."""
    assert not rc.lire("**Panne :** voir le cas 2 du dossier.\n", source="x.md").mesuree


def test_la_declaration_s_ARRETE_a_son_paragraphe() -> None:
    """ With no boundary, a number written A HUNDRED LINES further down would make any failure
 count as "measured" - *a text detector counts citations*."""
    texte = "**Panne :** ça casse.\n\n## Autre chose\n\nOn a mesuré 47 items ailleurs.\n"
    assert not rc.lire(texte, source="x.md").mesuree


# ---- THE REFUSAL: level 2, and its message NAMES the way out -----------------------------------
def test_le_refus_NOMME_les_DEUX_sorties_dont_l_aveu() -> None:
    """*The refusal message names the way out* - and it cites the admission, which is free.
    Without that, a cornered author invents a number."""
    with pytest.raises(rc.ReglePromotionRefusee) as e:
        rc.exiger_panne_declaree(rc.lire("rien du tout", source="x.md"))
    assert "AUCUNE MESUREE" in str(e.value) and "**Panne :**" in str(e.value)


def test_le_refus_DISTINGUE_non_declaree_et_non_chiffree() -> None:
    """Two causes, two messages: *the order of checks decides the verdict*, and a single message
    would send the author of an uncounted failure off to rewrite a declaration they already
    made."""
    with pytest.raises(rc.ReglePromotionRefusee) as absente:
        rc.exiger_panne_declaree(rc.lire("rien", source="x.md"))
    with pytest.raises(rc.ReglePromotionRefusee) as sans_chiffre:
        rc.exiger_panne_declaree(rc.lire("**Panne :** ça casse.\n", source="x.md"))
    assert "no failure declaration" in str(absente.value)
    assert "NO FIGURE" in str(sans_chiffre.value)


def test_une_candidature_promouvable_NE_LEVE_PAS() -> None:
    """ THE PASSING CASE, asserted - *I never assert the passing case* was the fault; a gate
 that refuses everything would sail through the two refusal witnesses above without a
 hitch."""
    rc.exiger_panne_declaree(rc.lire(REGLE, source="x.md"))
    rc.exiger_panne_declaree(rc.lire("**Panne :** AUCUNE MESURÉE.\n", source="x.md"))


def test_un_fichier_ILLISIBLE_ne_LEVE_pas_a_la_lecture(tmp_path: Path) -> None:
    """ The KILL paid on `G1`: a clause that kills the surface it annotates is worse than no
 clause. The unreadable becomes a NON-DECLARED candidature, which the gate refuses with its
 message."""
    f = tmp_path / "x.md"
    f.write_bytes(b"\xff\xfe binary")
    c = rc.lire_fiche(f)
    assert not c.declaree
    with pytest.raises(rc.ReglePromotionRefusee):
        rc.exiger_panne_declaree(c)


# ---- THE REAL THING: the repo's population, FROZEN ---------------------------------------------
def test_le_REEL_du_depot_est_gele() -> None:
    """ The frozen SET, never an inequality. And it says what the clause COSTS today:
 **7 candidate rules, 1 declaring a failure** - so the clause would refuse 6/7 if it bit at
 the repo level. It bites at **promotion**, and **0 of the 7 is promoted** (`status: draft`).
 *A new barrier is first tried against the corpus of innocents.*

 **THIS FREEZE MOVED ONCE, LEGITIMATELY, FOR `I3(b)`**: on 2026-08-15, the record
 `2026-08-09-proposition-harnais-de-sabotage.md` received the `**Panne :**` label - a
 BACKFILL, not an invention: its body already documented, since its creation, a measured
 failure (seven hand rewrites of the same harness in one day, four finding a defect
 invisible on re-read). This freeze turned red when the label was added - *a freeze that
 never reacts to a real change in the world is not one* - and it is re-measured here against
 the new state, not worked around.

 **AND A SECOND TIME, 2026-08-17, FOR THE PROJECT'S HARVEST**: chat 3 filed a verified
 candidate (absence confirmed on both sides of the repo). It does not declare a failure -
 it is not a rule invented by a project (I3(a)), it is a harvested tooling candidate (I2) -
 so `declarees` does not move, only the total count."""
    from mnemosyne.production.proposals import open_proposals

    dossier = REPO_ROOT / "knowledge" / "proposals"
    if not dossier.exists():  # pragma: no cover - corpus PERSO, gitignore par conception
        # THIS `skip` IS A KNOWN, DECLARED HOLE: in every clone and every CI run, `knowledge/`
        # is absent (gitignored), so this freeze **measures nothing anywhere except on the
        # operator's machine** - measured by an isolated audit in a fresh worktree:
        # `10 passed, 1 skipped, rc=0`. *An excluded population is not judged, it is absent from
        # judgment.* Making it RED would break every clone; staying silent about it would be
        # worse. So it is SAID, here and in the module.
        pytest.skip("knowledge/proposals absent — ce gel ne vaut QUE sur la machine du corpus")
    # THE JUDGE'S OWN ACCESSOR, not a reinvented `rglob`: `open_proposals()` is the read the
    # repo already does of this population (filters `status: draft`, skips README/MOC/INDEX).
    toutes = open_proposals(dossier)
    fiches = [f for f in toutes if not f.name.startswith(("finance-", "economics-"))]
    assert len(toutes) == 14 and len(fiches) == 7, (len(toutes), [f.name for f in fiches])
    declarees = [f.name for f in fiches if rc.lire_fiche(f).declaree]
    assert declarees == ["2026-08-09-proposition-harnais-de-sabotage.md"], declarees


# ---- THE TWO SURVIVING SABOTAGES, and the forms the population WRITES --------------------------
def test_la_borne_de_bloc_ferme_AUSSI_sur_un_TITRE() -> None:
    r""" SURVIVING SABOTAGE found by a third party: `_FIN_DE_BLOC` has **two** alternatives, and
 my witness wrote a blank line BEFORE the heading - so it died on `^\s*$` and **never**
 exercised `^#{1,6}\s`. Removing the "heading" half left 11/11 green.
 *A fixture that arms one branch COVERS the other: check WHICH ONE produced the green.*"""
    texte = "**Panne :** ça casse.\n## Autre chose\nOn a mesuré 47 items ailleurs.\n"
    assert not rc.lire(texte, source="x.md").mesuree


def test_le_refus_NOMME_la_fiche_en_cause() -> None:
    """ SURVIVING SABOTAGE: nothing asserted that the message carries the SOURCE. A report that
 says "refused" without saying *which one* sends the reader off searching - *a gate's
 evidence names the place*."""
    with pytest.raises(rc.ReglePromotionRefusee) as e:
        rc.exiger_panne_declaree(rc.lire("rien", source="ma-fiche.md"))
    assert "ma-fiche.md" in str(e.value)


def test_l_AVEU_est_lu_dans_la_forme_que_la_POPULATION_ecrit() -> None:
    """ MY ADMISSION FORM WAS INVENTED. I required `AUCUNE MESURÉE`; the 91 real sister
 declarations write *"aucune, et dite comme telle"* ("none, and said as such"). Measured:
 **81 refusals out of 91 (89%)** before the fix, **20 out of 91 (22%)** after - and the
 remaining 20 name CODE, not a number.

 **THIS WITNESS FREEZES THREE STRINGS COPIED FROM THIS MEASUREMENT - IT IS NOT THE
 REPLAY**: see :func:`test_eprouve_sur_les_declarations_SOEURS_reelles_de_la_memoire` just
 below for the REAL witness that re-reads the real population. Kept here because it tests
 something distinct and useful (the `**Panne :**` form, the module's origin), never removed
 so as not to lose its coverage - but its name should no longer suggest it replays the 91."""
    for forme in (
        "**Panne : aucune, et dite comme telle** (règle A2).",
        "**Panne :** aucune côté Mnémosyne.",
        "**Panne : partielle, et dite comme telle.**",
    ):
        assert rc.lire(forme, source="x.md").avouee, forme


# ---- PROVEN OUTSIDE THE POPULATION (hardening, 2026-08-16) --------------------------------------
def test_eprouve_sur_les_declarations_SOEURS_reelles_de_la_memoire() -> None:
    """ HARDENING - found by an isolated audit (D75): the module docstring CITES *"replayed
 against the 91 sister declarations (**Barriere :**) in the memory corpus,"* but NO witness
 replayed it - three FROZEN strings copied by hand from a past measurement stood in for it
 (see the previous witness). *A real, live test is not automatically a test on a
 DIFFERENT population - a citation in a docstring is never a witness*, the same lesson
 that brought down the `74/74` count from that night's census, applied here to my own
 module.

 **AND MY FIRST DRAFT OF THIS WITNESS HAD ITS OWN DEFECT, CAUGHT BY RUNNING IT (not
 assumed, measured: 90 real declarations found, 0 admissions)**: `_AVEU`/`_MESURE` require
 the word **`Panne`** in their own pattern (`\\*\\*\\s*Pannes?\\s*:`) - applying them to a
 block that still starts with `**Barriere :**` can NEVER match, whatever follows. A
 first draft that applies a module pattern to RAW TEXT rather than to the CONTENT it judges
 measures its own wiring mistake, never the question actually asked. Fixed: the witness
 substitutes `**Panne :**` for the keyword `**Barriere :**` (same content, same punctuation,
 only the keyword changes) and replays the REAL public entry point, `rc.lire()` - never
 hand-written private regexes.

 **THE CITED POPULATION STILL EXISTS, CLOSE TO 91**: measured today, **90** real
 `**Barriere :**` declarations (verified with `memoire.py`'s canonical accessor, never a
 homegrown `grep` - my own field `grep`, missing case-insensitivity, had first found only 4
 out of 90, the same class of error this witness fixes above). *The exact number is
 deliberately NOT frozen here*: unlike `knowledge/proposals/` (a near-static population,
 frozen in the previous witness), the memory folder grows every session - a frozen count
 would break at the next record written.

 The population differs from the original one (`knowledge/proposals/`, `**Panne :**` form,
 13 records from one project, frozen) in what the author did NOT have in view while writing
 this module: a DIFFERENT folder (personal memory, outside the repo), a DIFFERENT sister
 keyword, and a population that keeps moving under this witness rather than being frozen to
 one closed project.
 """
    from mnemosyne.runtime.memoire import _DECLARATION_DE_BARRIERE, dossier_de_memoire

    dossier = dossier_de_memoire(REPO_ROOT)
    if not dossier.is_dir():  # pragma: no cover - corpus PERSO, hors de ce depot par conception
        pytest.skip(
            "memory folder not found -- this witness is only valid on the corpus machine"
        )

    avouees = mesurees = 0
    ni_lun_ni_lautre: list[str] = []
    for chemin in sorted(dossier.glob("*.md")):
        if chemin.name in {"MEMORY.md", "MEMORY-2.md"}:
            continue
        texte = chemin.read_text(encoding="utf-8")
        m = _DECLARATION_DE_BARRIERE.search(texte)
        if m is None:
            continue
        lignes = texte[m.end() :].splitlines()
        corps = [lignes[0]]
        for ligne in lignes[1:]:
            if rc._FIN_DE_BLOC.match(ligne):
                break
            corps.append(ligne)
        # The sister keyword replaces `Barriere`, the CONTENT travels as-is -- tests whether the
        # judgment generalises to a different form of the same pattern, never a second parser
        # invented here.
        candidature = rc.lire("**Panne :" + "\n".join(corps), source=chemin.name)
        if candidature.avouee:
            avouees += 1
        elif candidature.mesuree:
            mesurees += 1
        else:
            ni_lun_ni_lautre.append(chemin.name)

    total = avouees + mesurees + len(ni_lun_ni_lautre)
    assert total > 0, "no Barriere declaration found -- the cited population has disappeared"
    assert avouees > 0, (
        f"no admission among the {total} real declarations -- the admission form no longer "
        f"generalises"
    )
    assert ni_lun_ni_lautre, (
        f"no 'neither admission nor number' declaration among the {total} real ones ({avouees} "
        f"admissions, {mesurees} measurements) -- the clause would capture 100% of this "
        f"population, which would contradict the '20 refusals out of 91' cited in the module "
        f"docstring"
    )


def test_un_FACTEUR_et_une_unite_d_UNE_lettre_sont_des_mesures() -> None:
    """ `x8` was cited **AS PROOF** in my comment and was NOT recognised; neither was `31 s`
 (my floor required two letters). *An example cited as proof must be PULLED, never
 assumed.*"""
    assert rc.lire("**Panne :** x8 par doublement.", source="x").mesuree
    assert rc.lire("**Panne :** 31 s au lieu de 5.", source="x").mesuree
    assert not rc.lire("**Panne :** voir le cas 2 du dossier.", source="x").mesuree


def test_une_declaration_COMMENTEE_ne_compte_PAS() -> None:
    """ The reuse was only half done: `memoire.py` strips HTML comments **before** judging,
 I did not - so an inert declaration was getting through the gate. *Reusing a form without
 reusing its PIPELINE is only half a reuse.*"""
    assert not rc.lire("<!-- **Panne :** 20 passes -->\nrien.", source="x").declaree
