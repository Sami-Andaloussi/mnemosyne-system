"""G1 -- the DELIVERABLES list precedes the plan, with the requester's own CITATIONS.

 THE FAULT CLOSED, AND ITS MEASURED PRICE (an internal lesson dated 2026-07-28):
*"a plan is already a TRANSLATION; when I have it validated, the other person validates MY
UNDERSTANDING presented as a fact"* -- plan validated, two rounds of audit, **2 deliverables
built out of 10 requested**. *The check was derived from the very thing it was supposed to check.*

 **AND THE FORM WAS NOT IMPOSED, IT WAS MEASURED** (lesson: measure the population before
imposing a convention, or 3 plans out of 5 would have scored 0): **17 gates in this repo, only
ONE** carries a deliverables list, and it writes **sections with block citations**, not "one line
per deliverable". Imposing the line would have scored 0 out of 100% of the real population. The
witnesses below therefore exercise the form THAT EXISTS.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mnemosyne.production import livrables

from _invariants import REPO_ROOT

# TODO(public-mirror): needs human review -- this fixture stays partly in FRENCH on purpose.
# `livrables._SERVI` only recognises the literal French word "livrable(s)" (see the note above
# that regex in livrables.py), so every string below that is meant to be MATCHED by it (a heading
# whose deliverable-serving phrase is exercised, or an item text passed to `livrables_non_servis`)
# keeps its original French wording even though the surrounding test code and comments are
# translated. Translating those specific phrases would silently stop them from exercising the
# regex they exist to test.
REEL = (
    "# What the operator asked for\n\n"
    "## The framing\n\nprose, no citation.\n\n"
    "## 1. THE HARVESTER — a project reports its skills\n\n"
    "> « Periodically, at the end of big arcs, we analyse the projects. »\n\n"
    "**Status**: \U00002705 built\n\n"
    "## 2. THE INSTRUMENT THAT JUDGES\n\n"
    "> « something that judges whether a lesson is useful. »\n\n"
    "## 3. A DELIVERABLE WITHOUT A CITATION\n\nnothing but my own rewording.\n"
)


# ---- READING: the form THAT EXISTS, not the one I would impose -------------------------
def test_un_livrable_est_un_titre_et_son_numero_est_son_identite() -> None:
    lus = livrables.lire_livrables(REEL)
    assert [x.numero for x in lus] == ["1", "2", "3"], (
        "`## The framing` is PROSE, not a deliverable"
    )
    assert lus[0].titre.startswith("THE HARVESTER")


def test_un_livrable_SANS_citation_est_RENDU_pas_ignore() -> None:
    """ *A deliverable without the requester's own words is exactly the translation this file
 exists to prevent.* Staying silent about it would make it invisible; it is returned with
 `cite=False`."""
    lus = livrables.lire_livrables(REEL)
    assert [x.cite for x in lus] == [True, True, False]


def test_les_DEUX_noms_sont_acceptes(tmp_path: Path) -> None:
    """`LIVRABLES_DEMANDES.md` is the SOLE real instance in the repo: not accepting it would drop
    the measured population's score from 100% to 0."""
    for nom in livrables.NOMS_LIVRABLES:
        dossier = tmp_path / nom
        dossier.mkdir()
        (dossier / "PLAN.md").write_text("# PLAN — x\n", encoding="utf-8")
        (dossier / nom).write_text(REEL, encoding="utf-8")
        assert livrables.fichier_livrables(dossier / "PLAN.md") == dossier / nom


def test_une_porte_SANS_liste_rend_None(tmp_path: Path) -> None:
    (tmp_path / "PLAN.md").write_text("# PLAN — x\n", encoding="utf-8")
    assert livrables.fichier_livrables(tmp_path / "PLAN.md") is None


# ---- MATCHING IS STRICT, same lesson as the completeness clause ---------------------------
def test_un_item_qui_CITE_le_numero_sert_le_livrable() -> None:
    lus = livrables.lire_livrables(REEL)
    non_servis = livrables.livrables_non_servis(lus, ("cet item construit le livrable 1",))
    assert [x.numero for x in non_servis] == ["2", "3"]


@pytest.mark.parametrize(
    "item",
    [
        "cet item parle du MOISSONNEUR",  # the title's word, without a number
        "cet item traite le point 1 de la section 2",  # NUMBERS, but no deliverable
        "voir la ligne 1 du tableau",
    ],
)
def test_un_item_qui_ne_CITE_pas_un_livrable_ne_le_SERT_pas(item: str) -> None:
    """ WITNESS REWRITTEN AFTER AN AUDIT: the old one passed an item **with no digit at all**, so
 it could only refute a match by WORD. Five sabotages of `_SERVI` survived it -- including "any
 bare number serves". *A witness that cannot see the fault it names is a name, not a test.*"""
    lus = livrables.lire_livrables(REEL)
    assert len(livrables.livrables_non_servis(lus, (item,))) == 3


def test_un_livrable_SANS_NUMERO_est_rendu_avec_SA_RAISON() -> None:
    """It can be served by no one. Saying so differs from implying no item wants it."""
    lus = livrables.lire_livrables(REEL)
    lus = livrables.lire_livrables("## NO NUMBER\n\n> « the requester's own words »\n")
    lignes = livrables.rendre(Path("plan/PLAN.md"), lus, livrables.livrables_non_servis(lus, ()))
    assert any("no number, so not citable" in ligne for ligne in lignes)


# ---- THE RENDER: it PUBLISHES, it NEVER refuses (level 1 on the existing population) ------------
def test_l_absence_de_liste_est_NOMMEE(tmp_path: Path) -> None:
    lignes = livrables.rendre(tmp_path / "PLAN.md", None, ())
    assert len(lignes) == 1 and "no LIVRABLES.md" in lignes[0]
    assert "TRANSLATION" in lignes[0], "the render must say WHY it matters, not only what"


def test_le_rendu_nomme_les_livrables_MUETS() -> None:
    lus = livrables.lire_livrables(REEL)
    lignes = livrables.rendre(Path("plan/PLAN.md"), lus, ())
    assert sum("NO citation from the requester" in ligne for ligne in lignes) == 1


def test_le_compte_publie_est_celui_des_CITATIONS_pas_des_titres() -> None:
    lus = livrables.lire_livrables(REEL)
    entete = livrables.rendre(Path("plan/PLAN.md"), lus, ())[0]
    assert "3 declared" in entete and "2 carry a citation" in entete


# ---- THE SIX FALSE READINGS FOUND BY THE ISOLATED AUDIT --------------------------------
def test_un_gabarit_dans_un_BLOC_DE_CODE_ne_fabrique_pas_de_livrables() -> None:
    """Measured: a `## 1.` shown as an example used to make **4 deliverables get read where there
    was only 1**."""
    texte = REEL + "\n```markdown\n## 1. <NAME>\n\n> « citation »\n\n## 2. <OTHER>\n```\n"
    assert len(livrables.lire_livrables(texte)) == len(livrables.lire_livrables(REEL))


def test_un_titre_de_niveau_4_ne_DISPARAIT_pas() -> None:
    """The docstring promises "returned rather than ignored". At `####`, it used to disappear
    WITHOUT A WORD."""
    assert [x.numero for x in livrables.lire_livrables("#### 2. DELIVERABLE\n\n> « x »\n")] == ["2"]


@pytest.mark.parametrize(
    "bloc",
    ["> **\U000026A0\U0000FE0F AGENT NOTE**: this is not a citation", "    > inside an indented code block"],
)
def test_un_bloc_CITATION_sans_guillemets_ne_compte_PAS(bloc: str) -> None:
    """ THE HEART OF G1: `>` alone does not distinguish the REQUESTER's own words from an
 admonition I WROTE MYSELF -- and the entire value of this file rests on that distinction. Not
 an imposed convention: **9 out of 9 cited deliverables** in the sole real file carry quotation
 marks."""
    assert livrables.lire_livrables(f"## 1. A\n\n{bloc}\n")[0].cite is False


def test_un_NUMERO_a_zero_non_significatif_est_SERVI() -> None:
    """Measured false accusation: `## 01.` cited by "deliverable 1" was declared NOT SERVED."""
    lus = livrables.lire_livrables("## 01. A\n\n> « x »\n")
    assert livrables.livrables_non_servis(lus, ("sert le livrable 1",)) == ()


@pytest.mark.parametrize(
    "item", ["construit les livrables 1 et 2", "sert les livrables 1, 2", "voir livrable #1 et n°2"]
)
def test_le_PLURIEL_francais_sert_bien_les_livrables(item: str) -> None:
    """ The most realistic false accusation on a French-speaking repo: "les livrables 1 et 2"
 ("deliverables 1 and 2") used to serve ZERO deliverables, because the `s` broke the match."""
    lus = livrables.lire_livrables("## 1. A\n\n> « x »\n\n## 2. B\n\n> « y »\n")
    assert livrables.livrables_non_servis(lus, (item,)) == ()


def test_un_NUMERO_porte_par_DEUX_livrables_est_NOMME() -> None:
    """The number is declared "its identity" and was never checked for uniqueness: a single
    citation used to serve two of them at once, in silence."""
    lus = livrables.lire_livrables("## 1. A\n\n> « x »\n\n## 1. B\n\n> « y »\n")
    lignes = livrables.rendre(Path("plan/PLAN.md"), lus, ())
    assert any("SEVERAL deliverables" in ligne for ligne in lignes)


def test_un_fichier_VIDE_ne_se_lit_PAS_comme_un_bulletin_sain() -> None:
    """ `touch LIVRABLES.md` USED TO SILENCE the warning and replace it with "0 · 0 · 0". The
 clause promised to name every plan without a LIST; it only named those without a FILE."""
    lignes = livrables.rendre(Path("plan/PLAN.md"), (), ())
    assert len(lignes) == 1 and "NO deliverable" in lignes[0] and "TRANSLATION" in lignes[0]


# ---- THE SEVEN DEFECTS OF THE SECOND AUDIT ROUND ---------------------------------------------
def test_les_guillemets_DROITS_comptent() -> None:
    """False accusation: `_GUILLEMETS` used to only recognise curly ones. Measured across the
    documentation tree: **19 blockquotes** carry straight quotation marks -- the default key on every keyboard."""
    assert livrables.lire_livrables('## 1. A\n\n> "the requester\'s own words"\n')[0].cite is True


def test_une_fence_IMBRIQUEE_ne_desynchronise_pas_la_bascule() -> None:
    """ A CLOSED defect was REOPENED: a `~~~` inside a ``` made the block's content readable
 again. And the pattern exists in this repo's own format-reference document, which is exactly
 the kind of document a template would be drawn from. *A boolean toggle does not remember WHO
 opened it.*"""
    texte = "## 1. REAL\n\n> « x »\n\n```markdown\n~~~\n## 2. FAKE\n~~~\n```\n"
    assert [x.numero for x in livrables.lire_livrables(texte)] == ["1"]


def test_un_BOM_ne_fait_pas_DISPARAITRE_le_premier_livrable() -> None:
    """ It does not raise, it LIES -- and that is worse than the crash: 2 declared, 1 read, in
 silence.
 The root cause lives in `plan_registry._read_text` (`utf-8` rather than `utf-8-sig`), so it
 is SHARED by every plan read in the repo. Here I close MY path; the other one is a separate
 arbitration."""
    texte = "﻿## 1. A\n\n> « x »\n\n## 2. B\n\n> « y »\n"
    assert [x.numero for x in livrables.lire_livrables(texte)] == ["1", "2"]


def test_un_SOUS_TITRE_ne_VOLE_pas_la_citation_de_son_parent() -> None:
    """ A class opened by MY OWN fix (`#{2,3}` -> `#{2,6}`): two false accusations at once -- the
 parent declared silent, the child declared not citable -- plus a phantom deliverable."""
    texte = "## 1. THE REAL DELIVERABLE\n\n### Context\n\n> « the operator's own words »\n"
    lus = livrables.lire_livrables(texte)
    assert [(x.numero, x.cite) for x in lus] == [("1", True)]


def test_un_titre_SANS_numero_NI_citation_est_de_la_PROSE() -> None:
    """On the sole real file, `## The framing` and `## Where things honestly stand` used to be
    counted as deliverables and each got TWO warnings. And the module contradicted itself: its
    docstring says "a deliverable is a heading that carries a citation", its code said "returned
    rather than ignored". *The written condition and the code now name the SAME population.*"""
    assert livrables.lire_livrables("## The framing\n\nprose.\n") == ()


@pytest.mark.parametrize("item", ["sert les livrables 1 à 3", "sert les livrables 1-3"])
def test_un_INTERVALLE_sert_ses_bornes(item: str) -> None:
    """Same family as the plural already fixed, on the same French-speaking repo: the fix had
    served `et`, `,`, `&` and stopped just short of `à`."""
    lus = livrables.lire_livrables("## 1. A\n\n> « x »\n\n## 3. C\n\n> « z »\n")
    assert livrables.livrables_non_servis(lus, (item,)) == ()


def test_une_citation_dans_un_BLOC_DE_CODE_de_l_item_ne_SERT_pas() -> None:
    """ ASYMMETRY: code blocks were neutralised on the DELIVERABLES side and not on the ITEM
 side -- the same fault on both sides."""
    lus = livrables.lire_livrables("## 2. B\n\n> « y »\n")
    item = "an item that shows code:\n```\nrendre(livrable 2)\n```\n"
    assert [x.numero for x in livrables.livrables_non_servis(lus, (item,))] == ["2"]


# ---- WIRING: the audit measured that G1 could be UNPLUGGED without a single red ----------------
# "`lines += _livrables_block(project)` -> `lines += ()`: 11/11 pass." G1 could be removed from
# `make plans` without a single witness complaining -- nothing was guarding the item's own
# DELIVERABLE. I had left this hole as an ABSTENTION on the grounds that a parallel session was
# editing `plans_run.py`. The reason was TOO BROAD -- covering the wiring only requires READING
# that file, not editing it. *An abstention is justified by a real collision, never by proximity.*
def test_le_CABLAGE_dans_make_plans_rend_bien_le_bloc(tmp_path: Path) -> None:
    from mnemosyne.production.plan_registry import ProjectPlan
    from mnemosyne.runtime.plans_run import _livrables_block

    porte = tmp_path / "PLAN.md"
    porte.write_text("# PLAN — x\n", encoding="utf-8")
    projet = ProjectPlan(name="x", plan_path=porte, state="lisible", reading=None)

    absent = _livrables_block(projet)
    assert absent and "no LIVRABLES" in absent[0], "the absence must be NAMED"

    (tmp_path / "LIVRABLES.md").write_text(REEL, encoding="utf-8")
    present = _livrables_block(projet)
    assert present and "3 declared" in present[0], present


def test_le_RAPPORT_RENDU_porte_le_bloc_G1(tmp_path: Path) -> None:
    """ THE WITNESS THAT REALLY KILLS THE UNPLUGGING. The previous one called `_livrables_block`
 DIRECTLY: removing the line `lines += _livrables_block(project)` from the render therefore did
 not turn it red -- measured, it survived. *A witness that calls the function does not measure
 that it is CALLED.* This one asserts on the REPORT that `make plans` produces."""
    from mnemosyne.production.plan_registry import PlanRegistry, ProjectPlan
    from mnemosyne.production.plan_format import read_plan
    from mnemosyne.runtime.plans_run import render_registry

    porte = tmp_path / "PLAN.md"
    porte.write_text(
        "# PLAN — trial\n\n## What this is\n\nprose.\n\n## The items\n\n"
        "- **A1** \U00002B1C **an item.**\n",
        encoding="utf-8",
    )
    projet = ProjectPlan(
        name="x",
        plan_path=porte,
        state="lisible",
        reading=read_plan(porte.read_text(encoding="utf-8")),
    )
    rendu = render_registry(PlanRegistry(projects=(projet,)), projects_root=tmp_path)
    assert "no LIVRABLES" in rendu, "the G1 block has disappeared from the report — the wiring is dead"

    (tmp_path / "LIVRABLES.md").write_text(REEL, encoding="utf-8")
    rendu2 = render_registry(PlanRegistry(projects=(projet,)), projects_root=tmp_path)
    assert "DELIVERABLES: 3 declared" in rendu2, rendu2


def test_le_CABLAGE_ne_LEVE_pas_sur_un_fichier_illisible(tmp_path: Path) -> None:
    """ THE KILL FOUND BY THE AUDIT: a bare `read_text` used to make `make plans` exit with 1 and
 a traceback, and THE ENTIRE REPORT WAS LOST -- on a Latin-1 `LIVRABLES.md`, a realistic case. A
 level-1 clause that kills the surface it annotates is worse than no clause at all."""
    # TODO(public-mirror): needs human review -- the asserted substrings ("illisible", "ne
    # bloque pas") are produced by `plans_run.py`'s OWN encoding-error handling inside
    # `_livrables_block`, a file outside this sanitization lot, not by anything in `livrables.py`.
    # Left in French so the pairing with that (untranslated) producer stays correct.
    from mnemosyne.production.plan_registry import ProjectPlan
    from mnemosyne.runtime.plans_run import _livrables_block

    porte = tmp_path / "PLAN.md"
    porte.write_text("# PLAN — x\n", encoding="utf-8")
    (tmp_path / "LIVRABLES.md").write_bytes(b"## 1. A\n\n> \xab caf\xe9 latin-1 \xbb\n")
    lignes = _livrables_block(ProjectPlan(name="x", plan_path=porte, state="lisible", reading=None))
    assert lignes and "illisible" in lignes[0] and "ne bloque pas" in lignes[0]


# ---- THE LEVEL-2 HALF: the template WRITTEN AT BIRTH ---------------------------------------
def test_le_GABARIT_se_relit_par_SON_PROPRE_lecteur() -> None:
    """ THE WITNESS THAT DECIDES WHETHER THE LEVEL-2 HALF IS WORTH ANYTHING. A template the
 reader cannot read would teach the author a form the clause refuses -- and the item says
 *"one line per deliverable"* where the MEASUREMENT says "sections with block citations". The
 template follows the measurement, so it must read back correctly."""
    lus = livrables.lire_livrables(livrables.gabarit("A Project"))
    assert [(x.numero, x.cite) for x in lus] == [("1", True), ("2", True)]
    assert livrables.livrables_non_servis(lus, ("sert le livrable 1",))[0].numero == "2"


def test_le_gabarit_porte_la_MESURE_qui_le_justifie() -> None:
    """*A rule that does not name the failure it prevents recites itself without understanding
    itself.*"""
    g = livrables.gabarit("X")
    assert "2 deliverables" in g and "10 requested" in g, "the measured price must travel with the template"
    assert "VERBATIM" in g and "never reworded" in g


def test_un_plan_NEUF_recoit_sa_commande_et_un_SOUS_plan_NON() -> None:
    """ A sub-plan does not get its own request: the requester's own words bear on the PROJECT,
 not on one of its arcs -- giving it one would fabricate a SECOND source of truth.

 And the predicate matters: `planning.parent` is only populated if the parent gate is
 READABLE. Measured: on `essai/plan/T1` whose parent is unreadable, `parent is None` -- the
 sub-plan then used to receive a request. It is `owning_parent` that decides."""
    from mnemosyne.production.plan_scaffold import plan_scaffold

    racine = plan_scaffold(folder="essai", project="Essai", cap="x", existing=())
    assert racine.livrables_name == livrables.NOM_A_LA_NAISSANCE
    assert racine.livrables_text.startswith("# What Essai must deliver")

    sous = plan_scaffold(folder="essai/plan/T1", project="T1", cap="x", existing=("essai/PLAN.md",))
    assert sous.livrables_name == "" and sous.livrables_text == ""


def test_la_NAISSANCE_ecrit_vraiment_le_fichier(tmp_path: Path) -> None:
    """The planning can carry the text without anything writing it: *a barrier nothing calls
    guards nothing.* We exercise the real `apply_planning`."""
    from mnemosyne.production.plan_scaffold import plan_scaffold
    from mnemosyne.runtime.plan_new_run import apply_planning

    planning = plan_scaffold(folder="essai", project="Essai", cap="x", existing=())
    apply_planning(planning, tmp_path)
    ecrit = tmp_path / "essai" / livrables.NOM_A_LA_NAISSANCE
    assert ecrit.is_file(), sorted(str(p) for p in tmp_path.rglob("*"))
    assert livrables.lire_livrables(ecrit.read_text(encoding="utf-8"))


def test_la_PREVISUALISATION_montre_la_commande() -> None:
    """ *A write that is not shown is not approved.* The `DRY` run must name the file it will
 write — otherwise the operator validates a birth with a piece of it invisible."""
    # TODO(public-mirror): needs human review -- "la COMMANDE" is a literal string hardcoded in
    # `plan_new_run.py`'s own `render()` (outside this sanitization lot), not derived from
    # `livrables.gabarit()`'s output. Left in French so the pairing stays correct.
    from mnemosyne.production.plan_scaffold import plan_scaffold
    from mnemosyne.runtime.plan_new_run import render

    planning = plan_scaffold(folder="essai", project="Essai", cap="x", existing=())
    rendu = render(planning, applied=False, commit="abc1234", dirty=False)
    assert "essai/LIVRABLES.md" in rendu and "la COMMANDE" in rendu


# ---- G2: each ITEM points at its deliverable, or declares itself "my own idea" -------------
# BLOCKED on `plan_format.py` (not my lot, 3rd arbitration): these witnesses exercise the PURE
# logic over FABRICATED `(ident, valeur)` pairs -- never read from a real `*Serves*` field, which
# does not exist yet in the grammar. The day it does, only the entry point changes
# (`item.field("sert")` instead of a fixture); `juger_rattachements` and its render do not move.
_LIVRABLES_G2 = (
    livrables.Livrable(numero="1", titre="A", ligne=1, cite=True),
    livrables.Livrable(numero="2", titre="B", ligne=2, cite=True),
)


def test_une_valeur_ABSENTE_n_est_ni_rattachee_ni_idee_a_moi() -> None:
    """NORMAL state during adoption -- not yet a fault. Published, never refused (same reasoning
    as G1 on its own birth: refusing on absence would redden the entire population that does not
    have the field yet)."""
    jugements = livrables.juger_rattachements(_LIVRABLES_G2, (("A1", None),))
    assert jugements == (livrables.Rattachement("A1", None, None, False, None),)
    assert not any("REFUSED" in ligne for ligne in livrables.rendre_rattachements(jugements))


@pytest.mark.parametrize("valeur", ["idée à moi", "Idée À Moi", "IDEE A MOI", "  idee a moi  "])
def test_IDEE_A_MOI_est_reconnue_QUELLE_QUE_SOIT_LA_CASSE_ET_L_ACCENT(valeur: str) -> None:
    jugement = livrables.juger_rattachements(_LIVRABLES_G2, (("A1", valeur),))[0]
    assert jugement.idee_a_moi is True
    assert jugement.numero is None and jugement.cible_existe is None


def test_UN_NUMERO_EXISTANT_est_RATTACHE() -> None:
    jugement = livrables.juger_rattachements(_LIVRABLES_G2, (("A1", "sert le livrable 2"),))[0]
    assert jugement.numero == "2" and jugement.cible_existe is True and not jugement.idee_a_moi


def test_UN_NUMERO_AVEC_ZERO_NON_SIGNIFICATIF_est_replie_COMME_PARTOUT_AILLEURS() -> None:
    """Same accessor (`_NUMERO`) as `livrables_non_servis` -- not a second rule."""
    jugement = livrables.juger_rattachements(_LIVRABLES_G2, (("A1", "livrable 02"),))[0]
    assert jugement.numero == "2"


def test_UN_NUMERO_INEXISTANT_EST_LE_SEUL_REFUS_REEL_ET_IL_EST_NOMME() -> None:
    """*Done when* of G2: "an attachment to a deliverable that does NOT EXIST is refused by name."
 That is the ONLY case that produces a REFUSED line."""
    jugement = livrables.juger_rattachements(_LIVRABLES_G2, (("A1", "sert le livrable 47"),))[0]
    assert jugement.numero == "47" and jugement.cible_existe is False

    lignes = livrables.rendre_rattachements((jugement,))
    assert any("REFUSED" in ligne and "A1" in ligne and "47" in ligne for ligne in lignes), lignes


def test_UNE_VALEUR_ILLISIBLE_EST_PUBLIEE_JAMAIS_SILENCIEUSE() -> None:
    """Neither "my own idea" nor a number: *publishing what is missing is not refusing* (G1), but
    staying silent would be worse -- an item that writes gibberish must stay visible, not invisible."""
    jugement = livrables.juger_rattachements(_LIVRABLES_G2, (("A1", "see above"),))[0]
    assert jugement.numero is None and not jugement.idee_a_moi and jugement.valeur == "see above"

    lignes = livrables.rendre_rattachements((jugement,))
    assert any("unreadable" in ligne and "A1" in ligne for ligne in lignes), lignes
    assert not any("REFUSED" in ligne for ligne in lignes), "unreadable is not the same fault as an orphan"


def test_LE_COMPTE_PUBLIE_NE_COMPTE_QUE_LES_VRAIS_RATTACHEMENTS() -> None:
    items = (
        ("A1", "sert le livrable 1"),   # attached
        ("A2", "idée à moi"),           # neither attached nor refused
        ("A3", None),                   # not declared yet
        ("A4", "sert le livrable 99"),  # orphan -- REFUSED, not counted as attached
    )
    jugements = livrables.juger_rattachements(_LIVRABLES_G2, items)
    lignes = livrables.rendre_rattachements(jugements)
    assert "items_attached=1/4" in lignes[0], lignes
    assert any("own idea, no deliverable" in ligne and "A2" in ligne for ligne in lignes)
    assert any("REFUSED" in ligne and "A4" in ligne for ligne in lignes)


# ---- THE REAL THING: what the repo really carries ---------------------------------------------
def test_le_SEUL_precedent_du_depot_se_lit(tmp_path: Path) -> None:
    """ The witness that counts: the real form, not my own fixture. If it turns red, it is
 because I imposed a convention the population does not write."""
    fichier = livrables.fichier_livrables(REPO_ROOT / "docs" / "PLAN.md")
    assert fichier is not None and fichier.name == "LIVRABLES_DEMANDES.md"
    lus = livrables.lire_livrables(fichier.read_text(encoding="utf-8"))
    # The frozen SET, never an inequality: the audit measured that three `>=` (margins 2, 0, 0)
    # could NEVER turn red on an OVER-reading -- yet the two defects found (nested fence, sub-title
    # stealing a citation) are both over-readings. *A one-sided rule only guards one side.* This
    # freeze rises when the operator adds a deliverable; it does not move silently.
    assert [x.numero for x in lus] == [str(n) for n in range(1, 11)], [x.titre[:40] for x in lus]
    assert sum(1 for x in lus if x.cite) == 9, "the requester's own citations are no longer seen"


# ---- G2 -- WIRING: the *Serves* field exists (2026-08-16), same discipline as G1 above ---
# *A witness that calls the function does not measure that it is CALLED* (G1's lesson, verbatim
# above) -- the two witnesses that follow therefore test the WIRING, not only `juger_
# rattachements` in isolation (already done above, on fabricated pairs).


def test_un_LIVRABLES_SANS_AUCUN_NUMERO_ne_fabrique_PAS_de_refus(tmp_path: Path) -> None:
    """ AUDIT DELEGATED ON 2026-08-16 (G2, Q2): a readable `LIVRABLES` file with NO numbered
 heading at all (a realistic form -- G1 already names it "no number, so not citable") used to
 make every item citing a number get REFUSED, even the most legitimate one -- the wrong file
 was blamed. G1 stays silent on this case (no number = nothing to serve); G2 must match it."""
    from mnemosyne.production.plan_format import read_plan
    from mnemosyne.production.plan_registry import ProjectPlan
    from mnemosyne.runtime.plans_run import _rattachements_block

    porte = tmp_path / "PLAN.md"
    porte.write_text(
        "# PLAN — x\n\n> **Cap** : x\n\n- **A1** \U00002B1C un item.\n  *Sert* : sert le livrable 1\n",
        encoding="utf-8",
    )
    (tmp_path / "LIVRABLES.md").write_text(
        "# What I am requesting\n\n## A heading without a number\n\n> « cited words. »\n", encoding="utf-8"
    )
    projet = ProjectPlan(name="x", plan_path=porte, state="lisible", reading=read_plan(porte.read_text()))
    assert _rattachements_block(projet) == (), "with no number declared, nothing to judge -- like G1"


def test_le_CABLAGE_G2_dans_make_plans_rend_bien_le_bloc(tmp_path: Path) -> None:
    from mnemosyne.production.plan_format import read_plan
    from mnemosyne.production.plan_registry import ProjectPlan
    from mnemosyne.runtime.plans_run import _rattachements_block

    porte = tmp_path / "PLAN.md"
    porte.write_text(
        "# PLAN — x\n\n> **Cap** : x\n\n"
        "- **A1** \U00002B1C un item.\n  *Sert* : sert le livrable 1\n"
        "- **A2** \U00002B1C un item.\n  *Sert* : idée à moi\n"
        "- **A3** \U00002B1C un item.\n",
        encoding="utf-8",
    )
    projet_sans = ProjectPlan(name="x", plan_path=porte, state="lisible", reading=read_plan(porte.read_text()))
    assert _rattachements_block(projet_sans) == (), "without LIVRABLES, G1 already names the gap -- G2 stays silent"

    (tmp_path / "LIVRABLES.md").write_text(REEL, encoding="utf-8")
    lignes = _rattachements_block(projet_sans)
    assert "items_attached=1/3" in lignes[0], lignes
    assert any("own idea, no deliverable" in ligne and "A2" in ligne for ligne in lignes), lignes


def test_le_RAPPORT_RENDU_porte_le_bloc_G2(tmp_path: Path) -> None:
    """ THE WITNESS THAT REALLY KILLS THE UNPLUGGING (same pattern as G1): asserts on the REPORT
 that `make plans` produces, not on a direct call to `_rattachements_block`."""
    from mnemosyne.production.plan_format import read_plan
    from mnemosyne.production.plan_registry import PlanRegistry, ProjectPlan
    from mnemosyne.runtime.plans_run import render_registry

    porte = tmp_path / "PLAN.md"
    porte.write_text(
        "# PLAN — trial\n\n## What this is\n\nprose.\n\n## The items\n\n"
        "- **A1** \U00002B1C **an item.**\n  *Sert* : sert le livrable 47\n",
        encoding="utf-8",
    )
    (tmp_path / "LIVRABLES.md").write_text(REEL, encoding="utf-8")
    projet = ProjectPlan(
        name="x", plan_path=porte, state="lisible", reading=read_plan(porte.read_text(encoding="utf-8"))
    )
    rendu = render_registry(PlanRegistry(projects=(projet,)), projects_root=tmp_path)
    assert "items_attached=0/1" in rendu, "the G2 block has disappeared from the report — the wiring is dead"
    assert "REFUSED" in rendu and "47" in rendu, "the non-existent target must be named in the REAL report"


def test_le_REEL_du_plan_de_MNEMOSYNE_n_orpheline_AUCUN_item() -> None:
    """ THE WITNESS THAT CARRIES G2'S REAL LEVEL 2 (same doctrine as G1/G3, see the comment
 block at the top of the section in `livrables.py`): `make plans` PUBLISHES, never refuses --
 the real barrier is HERE, frozen on the real population. If it turns red, an item cites a
 deliverable that does not exist and MUST be fixed, never silenced."""
    from mnemosyne.production.plan_registry import scan_plans

    registry = scan_plans(REPO_ROOT)
    porte = next(p for p in registry.projects if p.plan_path == REPO_ROOT / "docs" / "PLAN.md")
    fichier = livrables.fichier_livrables(porte.plan_path)
    assert fichier is not None
    declares = livrables.lire_livrables(fichier.read_text(encoding="utf-8"))
    paires = tuple((item.ident, item.field("sert")) for item in porte.reading.items if item.ident)
    jugements = livrables.juger_rattachements(declares, paires)
    orphelins = tuple(j for j in jugements if j.numero is not None and j.cible_existe is False)
    assert orphelins == (), [f"{j.ident} -> livrable {j.numero}" for j in orphelins]
