"""G3 -- the negative perimeter: an exclusion names its recipient, or it is a hole.

 **THIS FILE CARRIED, FOR TWO COMMITS, THE PREMISE ITS OWN FIX WAS REPUDIATING** —
it announced "measured on the 10 real arcs of this plan: 9 out of 10". **The repo carries 30
unique ones**, and the majority write their recipient as a NUMBER (``l'arc 09``), not a letter.
*Fixing the code without fixing the sentence that produced the error leaves the premise available
to make the same mistake again.*

 **AND THE FIGURE IS ONLY EVER DRAWN FROM THE PRODUCTION PATH**: my two "0 dead pointers" claims
both came from a union script I had written myself. `python -m mnemosyne.runtime.plans_run` printed
**73**, all wrong. *The harness is a variable of the measurement* — the wiring witnesses
below therefore go through `_perimetre_block`, never a rewritten collection.

 And the item's asymmetry is the heart of it: **publish** what has no recipient (level 1),
**refuse** the DEAD pointer (level 2). *Publishing what is missing is not refusing.*
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mnemosyne.production import perimetre
from mnemosyne.production.plan_format import read_plan

from _invariants import REPO_ROOT

ARC = (
    "# ARC X\n\n"
    "- **X1** \U00002B1C **un item.**\n\n"
    "## Ce que cet arc ne porte PAS\n\n"
    "Il n'ordonne rien : c'est l'arc E. Et il ne juge pas la qualité — c'est l'arc C.\n"
)


def _lues(texte: str, source: str = "arc.md"):
    return perimetre.lire_exclusions(texte, source=source)


# ---- READING: the form that EXISTS ------------------------------------------------------
def test_les_destinataires_sont_lus_dans_la_forme_reelle() -> None:
    (excl,) = _lues(ARC)
    assert excl.destinataires == ("C", "E") and excl.routee


def test_le_GRAS_ne_cache_pas_le_destinataire() -> None:
    """Measured: 1 arc in 10 writes `vit dans l'arc **A**`. Without stripping the bold markup, it
    slipped through."""
    texte = ARC.replace("c'est l'arc E", "ça vit dans l'arc **A**")
    assert "A" in _lues(texte)[0].destinataires


def test_un_JAMAIS_assume_est_une_reponse_VALIDE_et_gratuite() -> None:
    """ Without this branch, the arc that says « ils illustrent, ils ne s'exécutent pas » would be
 accused of a hole it does not have. *An answer of "nobody will ever pick it back up" is still an
 answer.*"""
    texte = ARC.replace(
        "Il n'ordonne rien : c'est l'arc E. Et il ne juge pas la qualité — c'est l'arc C.",
        "Ils illustrent — ils ne seront JAMAIS traduits ici.",
    )
    (excl,) = _lues(texte)
    assert excl.destinataires == () and excl.jamais and excl.routee


def test_une_exclusion_SANS_destinataire_est_lue_comme_un_trou() -> None:
    texte = ARC.replace(
        "Il n'ordonne rien : c'est l'arc E. Et il ne juge pas la qualité — c'est l'arc C.",
        "Il les relie au plan, et rien d'autre.",
    )
    assert not _lues(texte)[0].routee


def test_un_exemple_en_BLOC_DE_CODE_ne_fabrique_pas_de_destinataire() -> None:
    """Same class of bug closed three times in arc F: *a text detector counts citations as
    instances.*"""
    texte = ARC.replace(
        "Il n'ordonne rien : c'est l'arc E. Et il ne juge pas la qualité — c'est l'arc C.",
        "Rien ici.\n\n```markdown\nc'est l'arc E\n```\n",
    )
    assert _lues(texte)[0].destinataires == ()


def test_une_SOUS_SECTION_appartient_a_son_exclusion() -> None:
    texte = ARC + "\n### Un détail\n\nqui renvoie à l'arc H.\n"
    assert "H" in _lues(texte)[0].destinataires


def test_un_fichier_SANS_section_d_exclusion_ne_rend_RIEN() -> None:
    assert _lues("# ARC X\n\n- **X1** \U00002B1C **un item.**\n") == ()


# ---- JUDGING: publish on one side, refuse on the other ------------------------------------
def test_le_pointeur_MORT_est_separe_de_l_orpheline() -> None:
    """ The item's asymmetry: one gets published, the other gets refused. Conflating them would
 refuse a plan for work that is simply still pending — *publishing what is missing is not
 refusing*."""
    excl = _lues(ARC)
    orph, morts = perimetre.juger(excl, frozenset({"C", "X"}))
    assert orph == () and [lettre for _, lettre in morts] == ["E"]


def test_aucun_pointeur_mort_quand_tous_les_arcs_existent() -> None:
    """Both directions: a gate that refused everything would still pass the first shot."""
    assert perimetre.juger(_lues(ARC), frozenset({"C", "E"})) == ((), ())


def test_les_arcs_existants_sont_TIRES_du_lecteur_jamais_ecrits_a_la_main() -> None:
    """ A copied list ages, and a NEW arc would then be declared nonexistent by a clause that
 refuses. *The right source is the judge's own accessor* — a lesson paid for last night on a
 tuple whose shape I had guessed."""
    reading = read_plan(
        "# PLAN — x\n\n## Ce que c'est\n\np.\n\n## Les items\n\n"
        "- **A1** \U00002B1C **un.**\n- **K9** \U00002B1C **deux.**\n"
    )
    # LETTERS ONLY, and the ABSENT `9` is the heart of this witness. My 1st fix also pulled
    # the NUMBER out of the identifier: a COINCIDENCE, not an arc. Another project's gate carries `P0..P13`,
    # whose numbers happened to resemble its arcs `00..13` with no link at all — measured by an
    # isolated audit, the entire level-2 check hinged on the existence of an item named `P10`. The
    # number is read from the FILE TREE. *A zero obtained by numbering coincidence is not a zero.*
    assert perimetre.arcs_existants(reading) == frozenset({"A", "K"})


def test_un_NUMERO_D_ITEM_ne_fabrique_PAS_un_arc(tmp_path: Path) -> None:
    """ THE DIRECTION THAT LET A REAL DEAD ONE THROUGH: with `P7` in the gate, `« c'est l'arc
 07 »` passed even though no arc `07` exists. The number comes from disk, never from an
 identifier."""
    reading = read_plan(
        "# PLAN — x\n\n## Ce que c'est\n\np.\n\n## Les items\n\n- **P7** \U00002B1C **un.**\n"
    )
    assert "7" not in perimetre.arcs_existants(reading)
    assert perimetre.arcs_de_l_arborescence([Path("09-bordereau.md"), Path("x.md")]) == frozenset(
        {"09"}
    )


def test_un_ident_a_PLUSIEURS_lettres_ne_perd_pas_son_arc() -> None:
    """ `_IDENTITY_RE` allows 1 to 4 letters. `ident[0]` returned `A` for `AB1`, so `l'arc AB`
 was declared orphaned and `l'arc A` declared alive even though no arc A exists."""
    reading = read_plan(
        "# PLAN — x\n\n## Ce que c'est\n\np.\n\n## Les items\n\n- **AB1** \U00002B1C **un.**\n"
    )
    assert "AB" in perimetre.arcs_existants(reading)


def test_un_arc_NUMEROTE_est_lu_comme_destinataire() -> None:
    """ THE REPO'S MAJORITY FORM, and my first measurement never saw it: 16 exclusions out of 33
 write `l'arc 09`. Production measurement before the fix: 14 FALSE accusations."""
    texte = ARC.replace("c'est l'arc E", "c'est l'arc 09")
    assert "09" in _lues(texte)[0].destinataires


def test_la_PROSE_FRANCAISE_ne_fabrique_pas_de_destinataire() -> None:
    """ THE DEFECT MY OWN FIX MANUFACTURED, and it was WORSE than the one it repaired.
 By widening to `[A-Za-z]`, `« l'arc ne porte pas »` returned `ne` as the recipient. Measured on
 another project: **57 false DEAD pointers**, against 0 before the widening. *Case settles it.*"""
    texte = ARC.replace(
        "Il n'ordonne rien : c'est l'arc E. Et il ne juge pas la qualité — c'est l'arc C.",
        "Ce que cet arc ne porte pas, et ce dont l'arc de sortie rend compte.",
    )
    assert _lues(texte)[0].destinataires == ()


def test_un_arc_ZERO_PADDE_est_le_MEME_arc() -> None:
    """ `l'arc 7` and arc `07` are one and the same arc. Without normalisation, the LEVEL 2 clause
 refused a plan over a perfectly alive pointer."""
    texte = ARC.replace("c'est l'arc E", "c'est l'arc 7")
    assert perimetre.juger(_lues(texte), frozenset({"C", "07"}))[1] == ()


# ---- RENDERING: it publishes, it does not refuse -------------------------------------------------
def test_le_rendu_NOMME_l_orpheline_et_le_pointeur_mort() -> None:
    excl = _lues(ARC)
    orph, morts = perimetre.juger(excl, frozenset({"C"}))
    lignes = perimetre.rendre(excl, orph, morts)
    assert any("1 exclusion(s)" in x for x in lignes)
    assert any("points at arc E, which does not exist" in x for x in lignes)


def test_un_plan_SANS_exclusion_ne_rend_AUCUNE_ligne() -> None:
    """No noise: a plan that writes no perimeter is not at fault, it is silent."""
    assert perimetre.rendre((), (), ()) == ()


# ---- THE REAL: what the repo really carries, FROZEN -----------------------------------------
def test_le_REEL_du_depot_est_gele() -> None:
    """ The frozen SET, never an inequality — *a one-sided rule guards one side*, and the two
 defects found in arc F were OVER-reads a `>=` would never have caught.

 **AND THIS FREEZE WAS RE-IMPLEMENTED TWICE, KILLED TWICE.** The 1st audit showed it was
 recopying `arcs_existants`; I fixed **that half** and left the other — the ASSEMBLY of the
 universe. Measured by the 3rd audit: the witness's universe **11 arcs**, production's universe
 **21**; the witness *refused what production accepts*, and stayed **GREEN while production
 was emitting 67 false refusals**. It now descends from `_perimetre_block` ITSELF.
 *Fixing half of a re-implementation leaves a re-implementation.*
 **AND THE `ProjectPlan` COMES FROM `scan_plans`, NOT ONE I BUILD MYSELF**: my 1st version
 built it with `read_plan(porte)`, and it **immediately accused arcs C, H, I of being
 dead** — because production's own `reading` is FOLDED (gate + arcs), not the bare gate.
 *Reconstructing a function's input is still re-implementing production.*"""
    from mnemosyne.production.plan_registry import scan_plans
    from mnemosyne.runtime.plans_run import _perimetre_block

    projet = next(p for p in scan_plans(REPO_ROOT).projects if p.plan_path.parent.name == "docs")
    lignes = _perimetre_block(projet)
    orph = {x.split("—")[0].strip(" ·") for x in lignes if "names neither an arc" in x}
    morts = [x for x in lignes if "which does not exist" in x]
    # **THE GUARANTEE FIRST, THE COUNT FREEZE NEVER HERE.** The orchestrator found the flaw by
    # sabotaging: `assert len(excl) == 11` preceded `assert morts == ()`, so its 1st sabotage —
    # which ADDED an exclusion — turned the COUNT red, and **the guarantee was never
    # evaluated**. It nearly reached the wrong conclusion IN BOTH DIRECTIONS. Reordering was not
    # enough: as long as the freeze lives in the same function, it stays hidden. So it now has its
    # own witness, below.
    # *The order of checks decides what gets judged — and a check placed first adds a cause,
    # it never removes one.*
    assert morts == [], morts
    assert orph == {
        "plan/04-le-parallelisme.md",
        "plan/09-l-emission-vers-les-projets.md",
    }, orph


def test_le_COMPTE_du_depot_est_gele_A_PART() -> None:
    """The volume freeze, **separated from the guarantee** so it can never mask it.

 This witness will turn red the day a legitimate exclusion gets added — that is its job, and
 it is precisely why it must not cohabit with `morts == ()`. The SET rather than an
 inequality: *a one-sided rule guards one side.*"""
    from mnemosyne.production.plan_registry import scan_plans
    from mnemosyne.runtime.plans_run import _perimetre_block

    projet = next(p for p in scan_plans(REPO_ROOT).projects if p.plan_path.parent.name == "docs")
    lignes = _perimetre_block(projet)
    assert any("11 exclusion(s)" in x for x in lignes), lignes[:1]


# ---- WIRING: a witness that calls the function does not measure that it gets CALLED --------
def test_le_RAPPORT_RENDU_porte_le_bloc_G3(tmp_path: Path) -> None:
    """ A lesson paid for on `G1`: the first witness called `_perimetre_block` directly, so
 removing the call from the render path did not turn it red. This one asserts on the REPORT."""
    from mnemosyne.production.plan_registry import PlanRegistry, ProjectPlan
    from mnemosyne.runtime.plans_run import render_registry

    porte = tmp_path / "PLAN.md"
    porte.write_text(
        "# PLAN — epreuve\n\n## Ce que c'est\n\nprose.\n\n## Les items\n\n"
        "- **X1** \U00002B1C **un item.**\n\n## Ce que cet arc ne porte PAS\n\nIl les relie, rien d'autre.\n",
        encoding="utf-8",
    )
    projet = ProjectPlan(
        name="x",
        plan_path=porte,
        state="lisible",
        reading=read_plan(porte.read_text(encoding="utf-8")),
    )
    rendu = render_registry(PlanRegistry(projects=(projet,)), projects_root=tmp_path)
    assert "NEGATIVE PERIMETER" in rendu, "the G3 block has disappeared from the report — the wiring is dead"
    assert "names neither an arc nor an assumed JAMAIS" in rendu


@pytest.mark.parametrize(
    "contenu", [b"\xff\xfe binaire", "## Ce que cet arc ne porte PAS\n".encode("latin-1")]
)
def test_le_CABLAGE_ne_LEVE_pas_sur_un_fichier_illisible(tmp_path: Path, contenu: bytes) -> None:
    """ The KILL paid for on `G1`: a LEVEL 1 clause that kills the surface it annotates is worse
 than no clause at all. The neighbour's reader is reused, it never raises."""
    from mnemosyne.production.plan_registry import ProjectPlan
    from mnemosyne.runtime.plans_run import _perimetre_block

    porte = tmp_path / "PLAN.md"
    porte.write_text("# PLAN — x\n\n## Les items\n\n- **X1** \U00002B1C **un.**\n", encoding="utf-8")
    (tmp_path / "plan").mkdir()
    (tmp_path / "plan" / "arc.md").write_bytes(contenu)
    projet = ProjectPlan(
        name="x",
        plan_path=porte,
        state="lisible",
        reading=read_plan(porte.read_text(encoding="utf-8")),
    )
    _perimetre_block(projet)  # must not raise


# ---- DOES LEVEL 2 STILL BITE? -- a zero obtained by no longer judging is not a zero --------
def _projet(tmp_path: Path, corps: str, arcs: tuple[str, ...] = ()):
    from mnemosyne.production.plan_registry import ProjectPlan

    porte = tmp_path / "PLAN.md"
    porte.write_text(
        "# PLAN — x\n\n## Ce que c'est\n\np.\n\n## Les items\n\n- **X1** \U00002B1C **un.**\n",
        encoding="utf-8",
    )
    (tmp_path / "plan").mkdir(exist_ok=True)
    (tmp_path / "plan" / "arc.md").write_text(corps, encoding="utf-8")
    for a in arcs:
        # **SIBLING** of the plan, not a child: `_perimetre_block` reads `dossier.parent.glob("*")`
        # for this exact case, and my 1st fixture created the arc UNDER `plan/` — so it armed
        # the other branch and left this one UNPROVEN. Sabotage measured by an isolated audit:
        # removing `dossier.parent.glob` took production from 0 to **67 false refusals**,
        # harness GREEN. *A witness named for a case may not actually exercise it.*
        (tmp_path.parent / a).mkdir(exist_ok=True)
    return ProjectPlan(
        name="x",
        plan_path=porte,
        state="lisible",
        reading=read_plan(porte.read_text(encoding="utf-8")),
    )


def test_un_pointeur_VRAIMENT_MORT_est_encore_refuse_PAR_LA_PRODUCTION(tmp_path: Path) -> None:
    """ THE WITNESS THAT STOPS YOU BUYING GREEN BY SWITCHING THE CLAUSE OFF. The fix took
 `make plans` from **73 refusals (73 wrong)** to **0**; without this witness, a clause that
 judges nothing at all would give that exact same 0. It goes through `_perimetre_block`, the
 production path."""
    from mnemosyne.runtime.plans_run import _perimetre_block

    lignes = _perimetre_block(
        _projet(tmp_path, "## Ce que cet arc ne porte PAS\n\nC'est l'arc 99.\n")
    )
    assert any("points at arc 99, which does not exist" in x for x in lignes), lignes


def test_un_arc_FRERE_qui_existe_n_est_PAS_accuse(tmp_path: Path) -> None:
    """ THE EXACT CAUSE OF THE 73 FALSE ONES: the universe of arcs was drawn from `project.reading`
 (the GATE alone) while the exclusions came from the whole subtree. Both must be drawn from the
 same files. Here arc `10` exists as a FOLDER — `rglob("*.md")` would never have seen it."""
    from mnemosyne.runtime.plans_run import _perimetre_block

    lignes = _perimetre_block(
        _projet(
            tmp_path,
            "## Ce que cet arc ne porte PAS\n\nC'est l'arc 10.\n",
            arcs=("10-ordonnancement-et-lot",),
        )
    )
    assert not any("which does not exist" in x for x in lignes), lignes


def test_un_ITEM_CITE_route_l_exclusion_et_n_est_PAS_juge_existant(tmp_path: Path) -> None:
    """ THIS CLAUSE CARRIED **7 VERDICTS FROM THE REAL CORPUS WITH NOT A SINGLE WITNESS** — and it
 is the very one the 2nd fix added to close 6 false accusations. Two sabotages drawn TOGETHER
 (`_ITEM_CITE` silenced + `routee` without `items`) survived: **a hole, not a redundancy.**

 And the asymmetry is deliberate: a cited item ROUTES (level 1) but is **never** subject to
 level 2 — verifying that an item exists would require reading the whole corpus, which the
 clause does not do. *Claiming otherwise would fabricate a guarantee the measurement does not
 give.*"""
    texte = ARC.replace(
        "Il n'ordonne rien : c'est l'arc E. Et il ne juge pas la qualité — c'est l'arc C.",
        "Ça vit ailleurs : c'est `A03-12`.",
    )
    (excl,) = _lues(texte)
    assert excl.items == ("A03-12",) and excl.routee and excl.destinataires == ()
    assert perimetre.juger((excl,), frozenset()) == ((), ())


def test_le_rapport_NOMME_l_endroit_pas_seulement_le_FICHIER(tmp_path: Path) -> None:
    """ Without the relative path, **97 lines of the report said the same name for 13 different
 files** (`ce-que-cet-arc-ne-porte-pas.md`). The neighbour already closes this class; G3 was
 reopening it. This witness stayed absent after the fix -- a surviving sabotage showed it."""
    from mnemosyne.runtime.plans_run import _perimetre_block

    lignes = _perimetre_block(
        _projet(tmp_path, "## Ce que cet arc ne porte PAS\n\nIl les relie, rien d'autre.\n")
    )
    assert any("plan/arc.md" in x for x in lignes), lignes


def test_un_arc_entre_BACKTICKS_est_lu() -> None:
    """ 3 REAL occurrences, including another project's own gate: *« Son DESTINATAIRE est l'arc `11` »* — in
 the very section that cites `G3`'s own doctrine. It was declared recipient-less."""
    texte = ARC.replace("c'est l'arc E", "son destinataire est l'arc `11`")
    assert "11" in _lues(texte)[0].destinataires
