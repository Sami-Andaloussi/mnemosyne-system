"""A2 — the obligation scale: what the registry PUBLISHES, and the four things it REFUSES.

 **The central witness of this file is the one about a BOUGHT GREEN**: an EMPTY population and
an ENTIRELY DECLARED population both read as "no target without a level". If the edge did not
refuse the first, an unreadable `Makefile` would read as a perfectly governed repo. That is the
fault this repo has already paid for elsewhere (*two absences of measurement compare equal*), and
it is the first thing this file arms.

The second witness is its exact opposite: a target **with no level** must NOT turn red (`rc 0`).
A2 writes it — *"the list is published, never refused"* — and a test that forgot it would turn a
level 1 into a barrier the day someone adds a target.
"""

from __future__ import annotations

import pytest

from mnemosyne.production.obligation import (
    Declaration,
    DeclarationItem,
    lignes_illisibles,
    lire_le_registre,
    rendre_items,
    verdict,
    verdict_items,
)
from mnemosyne.runtime import obligation_run

# A minimal Makefile, but of the SAME SHAPE as the real one: one documented target (`##`), one
# internal target (no `##`, hence outside the population), and a recipe. A degenerate fixture
# would test nothing.
MAKEFILE = """\
help: ## Show this help
\t@echo help
plans: ## Read the plan
\t@echo plans
internal:
\t@echo internal
"""


def _poser(racine, makefile: str, registre: str) -> None:
    """Write a fake repo: the Makefile at the root, the registry at its canonical place.

 **CARRIES A MINIMAL BUT READABLE PLAN, AND THIS IS AN AUDIT FIX (`G4`, D2/D3).** Since
 `main()` ALWAYS pulls both sections (the `make` registry AND `G4`), a fake repo with no
 `docs/PLAN.md` made `G4` read as "unreadable plan" — `rc 2` — and contaminated `rc` for EVERY
 test in this file, which nonetheless only tests the `make` registry. A minimal plan, zero
 items, reads as an EMPTY population (`rc 0`, `0/0`) — legitimate — never as an IMPOSSIBLE
 measurement. *A shared harness that leaks its first instruction into every later one.*"""
    (racine / "Makefile").write_text(makefile, encoding="utf-8")
    porte = racine / "docs" / "governance"
    porte.mkdir(parents=True, exist_ok=True)
    (porte / "OBLIGATION.md").write_text(registre, encoding="utf-8")
    (racine / "docs" / "PLAN.md").write_text("# PLAN -- test repo\n", encoding="utf-8")


def _lancer(tmp_path, monkeypatch, makefile: str, registre: str) -> int:
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    _poser(tmp_path, makefile, registre)
    return obligation_run.main([])


# --------------------------------------------------------------------------------------------
# What the registry PUBLISHES (and never refuses)
# --------------------------------------------------------------------------------------------


def test_une_cible_sans_niveau_est_NOMMEE_et_ne_fait_PAS_rougir(tmp_path, monkeypatch, capsys):
    """The heart of A2: `plans` is not declared, it is NAMED, and the return code stays 0."""
    rc = _lancer(tmp_path, monkeypatch, MAKEFILE, "| `make help` | 1 | push |\n")
    sortie = capsys.readouterr().out
    assert rc == 0, "a target without a level must refuse NOTHING (A2: publish, never punish)"
    assert "plans" in sortie
    assert "1 target(s) declare a level out of 2 documented in the Makefile" in sortie


def test_la_cible_interne_sans_double_diese_n_entre_PAS_dans_la_population(tmp_path, monkeypatch, capsys):
    """The population is the same one `make help` / `make arsenal` use — imported, never redefined here."""
    _lancer(tmp_path, monkeypatch, MAKEFILE, "")
    sortie = capsys.readouterr().out
    assert "internal" not in sortie, "an undocumented target is not an offer, so it is not judged"


# --------------------------------------------------------------------------------------------
# What it REFUSES: the impossible measurement (rc 2) — the green you do not get to buy
# --------------------------------------------------------------------------------------------


def test_un_Makefile_SANS_AUCUNE_cible_documentee_REFUSE_au_lieu_de_rendre_vert(
    tmp_path, monkeypatch, capsys
):
    """ THE CENTRAL WITNESS. Empty population -> "no target without a level" would be a BOUGHT green."""
    rc = _lancer(tmp_path, monkeypatch, "internal:\n\t@echo nothing\n", "| `make help` | 1 | x |\n")
    assert rc == 2, "an empty population must REFUSE, never read as a governed repo"
    assert "REFUSED" in capsys.readouterr().err


def test_un_Makefile_illisible_REFUSE(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path / "nulle-part"))
    assert obligation_run.main([]) == 2
    assert "Makefile" in capsys.readouterr().err


def test_un_registre_ABSENT_REFUSE_au_lieu_de_declarer_toutes_les_cibles_nues(
    tmp_path, monkeypatch, capsys
):
    """An absent registry would read as "the 94 targets declare nothing" — true by accident."""
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    (tmp_path / "Makefile").write_text(MAKEFILE, encoding="utf-8")
    assert obligation_run.main([]) == 2
    assert "registry" in capsys.readouterr().err


# --------------------------------------------------------------------------------------------
# What it REFUSES: a registry that lies to itself (rc 1) — four causes, four witnesses
# --------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "registre, attendu",
    [
        ("| `make fantome` | 1 | nothing |\n", "fantome"),
        ("| `make help` | 2 |  |\n", "help"),
        ("| `make help` | 7 | an invented level |\n", "help"),
        ("| `make help` | 1 | a |\n| `make help` | 1 | b |\n", "help"),
    ],
    ids=["nonexistent-target", "level-2-no-mechanism", "level-outside-scale", "duplicate"],
)
def test_les_quatre_incoherences_sont_NOMMEES(tmp_path, monkeypatch, capsys, registre, attendu):
    rc = _lancer(tmp_path, monkeypatch, MAKEFILE, registre)
    assert rc == 1, "a registry that lies to itself must exit with 1"
    erreur = capsys.readouterr().err
    assert attendu in erreur, "the cause must be NAMED, never a mute refusal"


def test_un_niveau_2_QUI_nomme_son_mecanisme_passe(tmp_path, monkeypatch):
    """The deliberate asymmetry: we harden what CLAIMS something, we do not punish what stays humble."""
    rc = _lancer(tmp_path, monkeypatch, MAKEFILE, "| `make help` | 2 | hook X consumes its rc |\n")
    assert rc == 0


def test_un_niveau_1_SANS_mecanisme_passe(tmp_path, monkeypatch):
    """A level 1 has nothing to prove — demanding its justification would manufacture content (measured: 5 invented clauses, 2 of them false)."""
    rc = _lancer(tmp_path, monkeypatch, MAKEFILE, "| `make help` | 1 |  |\n")
    assert rc == 0


def test_un_niveau_bavard_n_est_PAS_coerce_en_entier():
    """`2 (soon)` must turn red as unknown, never silently become a `2`."""
    r = verdict(("help",), lire_le_registre("| `make help` | 2 (soon) | later |\n"))
    assert r.niveaux_inconnus == ("help",)
    assert r.declarees == 0


# --------------------------------------------------------------------------------------------
# The reader: what is NOT a declaration
# --------------------------------------------------------------------------------------------


def test_ni_la_ligne_de_separation_ni_un_placeholder_ne_deviennent_des_declarations():
    """Without this, the document's own instructions would read as two ghost entries."""
    texte = (
        "| target | level | what obliges it |\n"
        "|---|---|---|\n"
        "of the shape `| `make <target>` | <level> | <the mechanism> |`\n"
        "| `make help` | 1 | push |\n"
    )
    assert lire_le_registre(texte) == (Declaration("help", "1", "push"),)


# --------------------------------------------------------------------------------------------
# THE REAL THING — the only witness that catches a typo in the real document
# --------------------------------------------------------------------------------------------


def test_le_VRAI_registre_est_coherent_avec_le_VRAI_Makefile(capsys):
    """No `CLAUDE_PROJECT_DIR`: the root is the repo's own. A misspelled target here turns red."""
    assert obligation_run.main([]) == 0
    sortie = capsys.readouterr().out
    assert "policy-approuver" in sortie, "the measured level-3 targets must appear on the page"


# --------------------------------------------------------------------------------------------
# THE WITNESSES THE ISOLATED AUDIT FOUND MISSING — 7 sabotages out of 24 survived
# --------------------------------------------------------------------------------------------


def test_l_offre_s_imprime_MEME_quand_le_registre_est_incoherent(tmp_path, monkeypatch, capsys):
    """The offer written at the edge — and it survived a sabotage: no test read it.

    The scale is a READING page before it is a gate: a duplicate in the table must not deprive an
    agent of the whole scale. The four incoherence witnesses only asserted `stderr`.
    """
    rc = _lancer(tmp_path, monkeypatch, MAKEFILE, "| `make fantome` | 1 | x |\n")
    sortie = capsys.readouterr()
    assert rc == 1
    assert "Level 1 · PUSH" in sortie.out, "the offer must print BEFORE the refusal, always"
    assert "plans" in sortie.out, "and the list of no-level targets with it"


def test_une_population_ENTIEREMENT_declaree_le_DIT(tmp_path, monkeypatch, capsys):
    """The twin branch of the central witness: it ran in NO test at all.

    It is the one an empty `Makefile` would imitate — hence the `rc 2` next door. If nobody plays
    it, nobody sees that it and the refusal say opposite things.
    """
    registre = "| `make help` | 1 | x |\n| `make plans` | 1 | y |\n"
    rc = _lancer(tmp_path, monkeypatch, MAKEFILE, registre)
    sortie = capsys.readouterr().out
    assert rc == 0
    assert "No target without a level" in sortie
    assert "declare NO level at all" not in sortie


def test_DEUX_causes_simultanees_sont_TOUTES_les_deux_nommees(tmp_path, monkeypatch, capsys):
    """A registry with two faults where only one is named sends people to fix, come back, and find red again."""
    rc = _lancer(
        tmp_path, monkeypatch, MAKEFILE, "| `make fantome` | 1 | x |\n| `make help` | 9 | y |\n"
    )
    erreur = capsys.readouterr().err
    assert rc == 1
    assert "fantome" in erreur and "help" in erreur
    assert erreur.count("  - ") == 2, "each cause on its own line, never the first one alone"


def test_chaque_cause_est_nommee_PAR_SON_LIBELLE_pas_seulement_par_la_cible(
    tmp_path, monkeypatch, capsys
):
    """The labels could swap without any test turning red: only the target's name was asserted."""
    _lancer(tmp_path, monkeypatch, MAKEFILE, "| `make fantome` | 1 | x |\n")
    assert "target that does not exist" in capsys.readouterr().err
    _lancer(tmp_path, monkeypatch, MAKEFILE, "| `make help` | 2 |  |\n")
    assert "neither mechanism nor caller" in capsys.readouterr().err


def test_l_ancre_de_debut_de_ligne_est_ARMEE():
    """A line of PROSE citing a table must not become a declaration.

    The previous witness thought it proved the anchor: in reality its placeholder happened to land
    on the character class (`<target>` contains `<`). Here the line is a real, well-formed
    declaration, preceded by prose — only the `^` anchor can reject it.
    """
    assert lire_le_registre("see the line | `make help` | 1 | x | in the registry\n") == ()


def test_l_emphase_markdown_autour_du_niveau_est_TOLEREE():
    """Documented, never tested: the table is read by humans before it is read by any code."""
    assert lire_le_registre("| `make help` | **2** | hook X consumes its rc |\n") == (
        Declaration("help", "2", "hook X consumes its rc"),
    )


# --------------------------------------------------------------------------------------------
# THE SILENT LOSS — the class the audit found open
# --------------------------------------------------------------------------------------------


def test_une_ligne_SANS_troisieme_colonne_est_LUE_et_REFUSEE_au_lieu_de_disparaitre(
    tmp_path, monkeypatch, capsys
):
    """ THE MOST LIKELY HUMAN MISTAKE, and it used to disappear without a word.

 A three-column table filled in with two: the line matched nothing, the target read back as
 "not declared", and the guarantee the document SELLS ("a level 2/3 with no mechanism is
 refused") only bit if the column existed and was empty.
 """
    rc = _lancer(tmp_path, monkeypatch, MAKEFILE, "| `make help` | 2 |\n")
    assert rc == 1
    assert "neither mechanism nor caller" in capsys.readouterr().err


def test_une_ligne_INDENTEE_est_lue():
    assert lire_le_registre("  | `make help` | 1 | x |\n") == (Declaration("help", "1", "x"),)


def test_une_forme_ILLISIBLE_est_NOMMEE_au_lieu_d_etre_PERDUE(tmp_path, monkeypatch, capsys):
    """The class, not the case: what we do NOT know how to read must never be dropped in silence."""
    registre = "| [`make help`](../elsewhere.md) | 1 | a markdown link |\n"
    rc = _lancer(tmp_path, monkeypatch, MAKEFILE, registre)
    assert rc == 1
    assert "readable as a DECLARATION" in capsys.readouterr().err


def test_un_exemple_dans_un_bloc_CLOS_n_est_PAS_une_declaration():
    """The document already carries a ```make block: an instruction manual must not read like an order."""
    texte = "```\n| `make fantome` | 1 | an example |\n```\n| `make help` | 1 | real |\n"
    assert lire_le_registre(texte) == (Declaration("help", "1", "real"),)
    assert lignes_illisibles(texte) == ()


def test_une_ligne_a_DEUX_colonnes_n_AVALE_PAS_sa_voisine(tmp_path, monkeypatch, capsys):
    r""" THE BLOCKER from the second audit, and the previous witness could NOT see it.

 `\s` crosses the newline: with the 3rd column made optional, a badly filled line no longer
 disappeared — it **ate the next one**, perfectly well written, which dropped out of the
 registry without a word on an `rc 0`. The witness that claimed to cover this case used a
 registry of a **SINGLE LINE**: a fixture with no neighbour is degenerate for this defect.
 """
    registre = "| `make help` | 2 |\n| `make plans` | 1 | pushed by the hook |\n"
    rc = _lancer(tmp_path, monkeypatch, MAKEFILE, registre)
    sortie = capsys.readouterr()
    assert "plans" in sortie.out, "the neighbour must stay DECLARED, never get eaten"
    assert "declare NO level at all" not in sortie.out
    assert rc == 1 and "neither mechanism nor caller" in sortie.err, "and the faulty line is named"


def test_un_niveau_3_sans_mecanisme_est_REFUSE_lui_aussi(tmp_path, monkeypatch, capsys):
    """The document's promise is about "2 OR 3" — and only the 2 was armed, while the registry's
    4 real declarations are all level 3. *The only clause the real data exercised was the one
    nothing tested.*"""
    rc = _lancer(tmp_path, monkeypatch, MAKEFILE, "| `make help` | 3 |  |\n")
    assert rc == 1
    assert "neither mechanism nor caller" in capsys.readouterr().err


@pytest.mark.parametrize(
    "registre, libelle",
    [
        ("| `make help` | 9 | x |\n", "outside the scale"),
        ("| `make help` | 1 | a |\n| `make help` | 1 | b |\n", "declared twice"),
        ("| [`make help`](../x.md) | 1 | link |\n", "readable as a DECLARATION"),
    ],
    ids=["unknown-level", "duplicate", "unreadable"],
)
def test_les_TROIS_libelles_restants_sont_assertes(tmp_path, monkeypatch, capsys, registre, libelle):
    """Three causes out of five could swap their labels without any test turning red — the "labels"
    fix had closed 2 cases out of 5, not the class. *Close the class, not the case.*"""
    _lancer(tmp_path, monkeypatch, MAKEFILE, registre)
    assert libelle in capsys.readouterr().err


def test_le_COMPTE_publie_porte_sur_TOUS_les_niveaux(tmp_path, monkeypatch, capsys):
    """The count at the top of the page could go from 17 to 13 without any test moving: the only
    fixture that exercised it carried a single declaration, of level 1."""
    registre = "| `make help` | 1 | x |\n| `make plans` | 3 | /dev/tty, in the path |\n"
    _lancer(tmp_path, monkeypatch, MAKEFILE, registre)
    assert "2 target(s) declare a level out of 2" in capsys.readouterr().out


def test_l_ECHELLE_publiee_ne_peut_pas_MENTIR_sur_ses_propres_niveaux(tmp_path, monkeypatch, capsys):
    """Only "Level 1 · PUSH" was asserted: one could rename level 2 "refuses nothing" and publish
    a false scale, in green."""
    _lancer(tmp_path, monkeypatch, MAKEFILE, "| `make help` | 2 | hook X consumes its rc |\n")
    sortie = capsys.readouterr().out
    assert "Level 1 · PUSH — arrives unsolicited, refuses nothing" in sortie
    assert "Level 2 · BARRIER — refuses a repo state" in sortie
    assert "Level 3 · INCAPACITY — we CANNOT" in sortie


def test_une_cible_FANTOME_n_apparait_PAS_dans_l_echelle_publiee(tmp_path, monkeypatch, capsys):
    """It is named as a ghost; it must not slip into the list of declared targets."""
    _lancer(tmp_path, monkeypatch, MAKEFILE, "| `make fantome` | 1 | nothing |\n")
    sortie = capsys.readouterr().out
    assert "`make fantome`" not in sortie


def test_le_filet_anti_perte_couvre_PLUSIEURS_formes_pas_une_seule():
    """The net used to rest on a single case (the markdown link): three sabotages disarmed it
    without turning red. A net with a single witness is not a net."""
    for forme in (
        "| [`make help`](../x.md) | 1 | a link |\n",
        "> | `make help` | 2 | inside a blockquote, a form this document itself uses |\n",
        "    | `make help` | 1 | indented by 4: Markdown turns this into a CODE BLOCK |\n",
        "| **make help** | 1 | in bold, no backticks |\n",
    ):
        assert lignes_illisibles(forme), f"lost in silence: {forme!r}"
        assert lire_le_registre(forme) == (), f"must not be READ either: {forme!r}"


@pytest.mark.parametrize(
    "bloc",
    [
        "```\n| `make help` | 1 | example |\n```\n",
        "```\n| `make help` | 1 | example |\n````\n",
        "````\n| `make help` | 1 | example |\n`````\n",
        "```\n| `make help` | 1 | example |\n",
        "~~~\n| `make help` | 1 | example |\n~~~\n",
    ],
    ids=["closes-3", "closes-4-CommonMark", "opens-4-closes-5", "NEVER-closed", "tildes"],
)
def test_aucune_forme_de_BLOC_CLOS_ne_FABRIQUE_une_declaration(bloc):
    """ The last silent manufacture, and it lied in the OPPOSITE direction from the loss.

 The regex version closed on a backreference, so it required a closing fence of exactly equal
 length. CommonMark allows longer, and an unclosed fence runs to the end: in all three cases the
 pedagogical example became a REAL declaration, `rc 0`, without a word. And `illisibles` could
 not catch it — the line IS readable.
 """
    assert lire_le_registre(bloc) == (), f"example MANUFACTURED into a declaration: {bloc!r}"


def test_la_borne_d_indentation_est_gelee_des_DEUX_cotes():
    """The "3 spaces" bound is Markdown's own rule; it was only frozen on one side — the only
    indented witness used 2 spaces, so it could drift to 2 and refuse a legitimate line."""
    assert lire_le_registre("   | `make help` | 1 | three spaces, READ |\n") == (
        Declaration("help", "1", "three spaces, READ"),
    )
    assert lire_le_registre("    | `make help` | 1 | four: code block |\n") == ()
    assert lignes_illisibles("    | `make help` | 1 | four: code block |\n"), "and NAMED"


def test_le_libelle_du_refus_n_AFFIRME_PAS_une_perte_qui_n_a_pas_lieu(tmp_path, monkeypatch, capsys):
    """The most likely victim is the LEVELS table itself, which cites a target as an example and
    declares nothing: the refusal sent people to fix a CORRECT line by claiming it would be lost.
    It is not — it is named right there, on screen."""
    _lancer(tmp_path, monkeypatch, MAKEFILE, "| **1 · PUSH** | refuses nothing | `make help` |\n")
    erreur = capsys.readouterr().err
    assert "LOST IN SILENCE" not in erreur
    assert "nothing is lost" in erreur and "take the line out of" in erreur


def test_le_VRAI_document_ne_perd_AUCUNE_ligne_en_silence():
    """The witness that catches the fault the day someone fills in the real table badly."""
    from pathlib import Path

    texte = Path("docs/governance/OBLIGATION.md").read_text(encoding="utf-8")
    assert lignes_illisibles(texte) == ()


# --------------------------------------------------------------------------------------------
# `G4` — the SAME question asked of a DIFFERENT population: plan items, not `make` targets.
# --------------------------------------------------------------------------------------------


def test_un_item_niveau2_AVEC_appelant_est_CABLE():
    it = DeclarationItem(ident="A1", niveau_2_ou_plus=True, module="plan_format", appelants=5)
    r = verdict_items([it])
    assert r.cablees == ("A1",)
    assert r.sans_appelant == () and r.non_verifiables == () and r.coherent


def test_un_item_niveau2_module_identifie_ZERO_appelant_est_NOMME_et_REFUSE():
    """ The heart of `G4`: a declared barrier that nothing calls must be NAMED, never silently
 downgraded. This is exactly the defect measured on `C1` before it closed."""
    it = DeclarationItem(ident="C1", niveau_2_ou_plus=True, module="plan_condition", appelants=0)
    r = verdict_items([it])
    assert r.sans_appelant == ("C1",)
    assert not r.coherent, "an item with no real caller must make the registry INCOHERENT"


def test_un_item_niveau2_SANS_module_identifiable_est_NON_VERIFIABLE_pas_suppose_bon():
    """ The half missing from any narrow-scope mechanism: `module=None` must NOT read as a
 success. Measured on the real population: it is the MOST frequent answer (25 level-2 items
 out of 29) — a mechanism that let it pass would have let everything pass."""
    it = DeclarationItem(ident="G1", niveau_2_ou_plus=True, module=None, appelants=None)
    r = verdict_items([it])
    assert r.non_verifiables == ("G1",)
    assert r.coherent, "unverifiable is not a refusal — it is a third, admitted state"
    assert r.cablees == () and r.sans_appelant == ()


def test_un_item_niveau_moins_de_2_est_HORS_SCOPE_jamais_juge():
    it = DeclarationItem(ident="A2", niveau_2_ou_plus=False)
    r = verdict_items([it])
    assert r.hors_scope == ("A2",)
    assert r.total_juge == 0, "an out-of-scope item must not inflate the judged denominator"


def test_un_item_qui_NOMME_un_module_PAS_ENCORE_CONSTRUIT_est_distingue():
    """ Audit D5b: `C5` names `` `production/parc.py` `` unambiguously, the file does not exist
 yet — this is NOT the same state as an item that names NOTHING. Conflating the two publishes a
 false sentence for the one that named its target."""
    it = DeclarationItem(ident="C5", niveau_2_ou_plus=True, module=None,
                          module_non_construit="parc")
    r = verdict_items([it])
    assert r.non_construits == (("C5", "parc"),)
    assert r.non_verifiables == (), "must NOT fall into the generic bucket"
    assert r.coherent, "naming a target not yet built is not a refusal"


def test_verdict_items_DIFFERENCIE_les_QUATRE_etats_sur_une_population_MELANGEE():
    """Tests DIFFERENTIATION, not conformity: the four categories must EACH receive the item that
    matches it, never a catch-all that conflates them."""
    population = [
        DeclarationItem("cable", True, "plan_format", 5),
        DeclarationItem("muet", True, "plan_condition", 0),
        DeclarationItem("opaque", True, None, None),
        DeclarationItem("hors", False),
    ]
    r = verdict_items(population)
    assert r.cablees == ("cable",)
    assert r.sans_appelant == ("muet",)
    assert r.non_verifiables == ("opaque",)
    assert r.hors_scope == ("hors",)
    assert r.total_juge == 3, "hors_scope does not count in the JUDGED total"


def test_rendre_items_NOMME_les_items_SANS_appelant_et_les_NON_VERIFIABLES():
    r = verdict_items([
        DeclarationItem("muet", True, "plan_condition", 0),
        DeclarationItem("opaque", True, None, None),
    ])
    page = rendre_items(r)
    assert "muet" in page and "NO real caller AT ALL" in page
    assert "opaque" in page and "NOT VERIFIABLE" in page
    assert "obligations_cablees=0/2" in page


def test_rendre_items_TAIT_le_hors_scope_du_denominateur():
    r = verdict_items([DeclarationItem("cable", True, "plan_format", 3),
                        DeclarationItem("dehors", False)])
    page = rendre_items(r)
    assert "obligations_cablees=1/1" in page, f"the out-of-scope item skewed the denominator: {page!r}"
