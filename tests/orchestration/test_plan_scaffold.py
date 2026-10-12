"""`make plan-nouveau` — a plan that is BORN conformant (D166 · C20-13).

What this suite holds, and what it refuses to take on faith:

* **the reader judges, never the scaffold.** Every "this is conformant" claim goes through
  ``read_plan`` + ``merge_plan`` + ``index_problems`` + ``is_readable`` — the SAME call sequence as
  ``read_plan_tree`` and the pre-commit hook. A producer that grades its own copy is the defect
  this repo has already measured;
* **every refusal is PRODUCED**, not merely named: a name is not a test, and a refusal that no
  input triggers is a promise nobody keeps;
* **recursion is proven by its FAILURE**: the test that matters is not "the sub-plan is
  readable," it is "without its parent's index entry, the reader accuses it" — otherwise the
  parent's indexing clause could disappear without a single line turning red.

Fixtures: never the real repo. Everything lives on ``tmp_path``, and what is judged is re-read
from disk once the command has written.
"""

from __future__ import annotations

import dataclasses
import hashlib

import pytest

from mnemosyne.production.plan_archive import slugify
from mnemosyne.production.plan_convert import index_entry
from mnemosyne.production.plan_format import (
    ARCS_DIRNAME,
    PLAN_FILENAME,
    ROLE_PLAN,
    index_problems,
    is_readable,
    live_lines,
    merge_plan,
    plan_entries,
    read_plan,
)
from mnemosyne.production.plan_scaffold import (
    DEFAULT_ARC_TITLE,
    REFUSAL_LABEL,
    ParentDoorUnreadable,
    ScaffoldMismatch,
    _DECLARING_LINE,
    _post_entry,
    arc_ident,
    blinding_characters,
    door_skeleton,
    plan_scaffold,
    verify_readability,
)
from mnemosyne.runtime.plan_new_run import _GESTE, apply_planning, main


# --- folding, written ONCE: it is the same one `read_plan_tree` and the hook use ------------------------


def fold(door_text: str, members: tuple[tuple[str, str], ...]):
    """Fold a door and its arcs the way the real reader does — a single `ident_seen`, `merge_plan`.

 Written here rather than imported from `plan_scaffold._fold` **on purpose**: a reference derived
 from what it checks checks nothing (D170). If the scaffold starts folding differently, this
 function will not follow, and the assertions below will fall.

 **AND THIS IS EXACTLY WHERE THIS COPY WAS LYING.** It folded EVERY member handed to it as if
 it were an arc of THIS plan — so, on a plan that carries a sub-plan, the sub-plan's arc entered
 the parent's identity registry. The copy and the code it copied shared exactly this defect,
 which is the definition of a reference that checks nothing: it let the refusal of a SECOND
 sibling sub-plan slip through. It now asks `plan_entries` — the sole enumeration — what belongs
 to this plan, the same way `read_plan_tree` does, and width (SIBLINGS, not just depth) is proven
 further down.
 """
    texts = dict(members)
    tree = tuple(texts)
    arc_paths, nested = plan_entries("", tree)
    seen: dict[str, str] = {}
    door = read_plan(door_text, ident_seen=seen)
    arcs = tuple(
        (f"{ARCS_DIRNAME}/{relative}", read_plan(
            texts[f"{ARCS_DIRNAME}/{relative}"],
            origin=f"{ARCS_DIRNAME}/{relative}",
            ident_seen=seen,
        ))
        for relative in arc_paths
    )
    return merge_plan(
        door, arcs, extra=index_problems(door_text, arc_paths + nested, folder_form=bool(tree))
    )


def members_of(planning) -> tuple[tuple[str, str], ...]:
    return tuple((arc.member, arc.text) for arc in planning.arcs)


# --- what the scaffold writes IS READABLE, according to the reader itself ---------------------------


def test_le_plan_echafaude_est_LISIBLE_pour_le_lecteur_qui_jugera_le_commit():
    """The mandate's criterion, in its shortest form: what is born passes the door."""
    planning = plan_scaffold(folder="projects/saas/alpha", cap="fermer l'arc 6")
    assert planning.refusals == ()
    reading = fold(planning.door_text, members_of(planning))
    assert is_readable(reading, role=ROLE_PLAN), reading.problems
    assert reading.problems == ()
    assert reading.project == "alpha" and reading.cap == "fermer l'arc 6"


def test_la_porte_ne_porte_AUCUN_item_et_reste_lisible_comme_porte():
    """Items live in the arcs — a door that carries them recreates the monolith (1310 lines)."""
    planning = plan_scaffold(folder="p/x")
    door = read_plan(planning.door_text)
    assert door.items == () and door.problems == ()
    assert door.readable_as_door and not door.readable_as_arc


def test_chaque_arc_echafaude_porte_au_moins_un_item():
    planning = plan_scaffold(folder="p/x", arcs=("Socle", "Les mesures", "La barrière"))
    for arc in planning.arcs:
        reading = read_plan(arc.text, origin=arc.member)
        assert reading.readable_as_arc, arc.member
        assert reading.problems == ()


def test_le_nom_du_projet_vient_du_DOSSIER_quand_on_ne_le_donne_pas():
    folder = "projects/research/example_research"
    assert plan_scaffold(folder=folder).project == "example_research"
    assert plan_scaffold(folder=folder, project="Example Research").project == "Example Research"


def test_le_cap_par_defaut_est_celui_du_squelette_mono_fichier():
    """One single voice for both shapes: two different placeholders would mean two formats."""
    from mnemosyne.production.plan_format import plan_skeleton
    from mnemosyne.production.plan_scaffold import DEFAULT_CAP

    assert DEFAULT_CAP in plan_skeleton("x")
    assert DEFAULT_CAP in plan_scaffold(folder="p/x").door_text


# --- D176: the Format CHOICE is ENCOUNTERED at every birth, never IMPOSED --------------------
# THE REAL DEFECT (entry of 2026-08-17): a plan born via `make plan-nouveau`, with no tweaks at
# all, declared ZERO mandatory fields -- `champs_requis_pour` returns `()` for it, so nothing
# obliges anyone to do anything. The naive fix (writing `**Format**` by default) would IMPOSE
# adoption and break D176 the other way. Choice made: the door ALWAYS explains the choice (D176
# block below), and only writes the `**Format**` line when the caller actually supplied one.
def test_SANS_format_declare_aucune_ligne_Format_mais_le_choix_est_RENCONTRE():
    """The behaviour from before this fix stays intact in SUBSTANCE (zero mandatory fields) --
    but never again in silence: the D176 block explains the choice at EVERY birth."""
    texte = door_skeleton("x", "cap", ())
    # NEITHER substring is enough on its own: the explanatory block QUOTES both `**Format**` AND
    # `> **Format** :` in prose ("add `> **Format** : ...`") -- an accusation by substring would
    # confuse the quotation with a real declaration. Only the READER'S OWN ACCESSOR (the one that
    # actually judges a commit) can settle it: `format_declare` must stay empty.
    assert "D176" in texte and "optional" in texte
    reading = read_plan(texte)
    assert reading.format_declare == ""


def test_AVEC_format_declare_la_ligne_EST_ECRITE_juste_sous_Cap():
    texte = door_skeleton("x", "cap", (), "produit, fini_quand")
    lignes = texte.splitlines()
    idx_cap = next(i for i, ligne in enumerate(lignes) if ligne.startswith("> **Cap**"))
    assert lignes[idx_cap + 1] == "> **Format** : produit, fini_quand"


def test_le_plan_ECHAFAUDE_AVEC_format_declare_reste_LISIBLE_et_LE_LECTEUR_LE_RETROUVE():
    """The full round-trip: what the scaffold WRITES is what the READER reads -- never two
    expressions of the same declaration."""
    planning = plan_scaffold(folder="p/x", format_declare="produit, fini_quand")
    assert planning.refusals == ()
    reading = fold(planning.door_text, members_of(planning))
    assert is_readable(reading, role=ROLE_PLAN), reading.problems
    assert reading.problems == ()
    assert reading.format_declare == "produit, fini_quand"


def test_UN_ITEM_du_plan_echafaude_QUI_NE_DECLARE_RIEN_est_REFUSE_par_le_JUGE_du_champ():
    """The complete loop, created -> judged: `champs_requis_pour` + `required_field_problems` on the
    plan exactly as the scaffold REALLY wrote it, never a hand reconstruction. This is
    exactly what `plan_gate_run.juger()` (D176, mon_lot) calls in production."""
    from mnemosyne.production.plan_format import champs_requis_pour, required_field_problems

    planning = plan_scaffold(folder="p/x", format_declare="produit")
    reading = fold(planning.door_text, members_of(planning))
    requis = champs_requis_pour(f"{planning.folder}/{PLAN_FILENAME}", reading.format_declare)
    refus = required_field_problems(reading, required=requis)
    assert len(refus) == 1 and "champ_requis_manquant" in refus[0].kind, refus


def test_SANS_format_declare_LE_MEME_ITEM_muet_N_EST_PAS_refuse():
    """The counterpart, and it closes the D176 loop: the same birth, with no declaration, must
    oblige NOTHING -- the behaviour from before this fix, intact."""
    from mnemosyne.production.plan_format import champs_requis_pour, required_field_problems

    planning = plan_scaffold(folder="p/x")
    reading = fold(planning.door_text, members_of(planning))
    requis = champs_requis_pour(f"{planning.folder}/{PLAN_FILENAME}", reading.format_declare)
    assert required_field_problems(reading, required=requis) == ()


# --- the index: a single expression of its shape, and it comes from the OTHER module -------------------


def test_l_entree_d_index_est_celle_de_l_UNIQUE_foyer_jamais_une_seconde_expression():
    """D170 was paid for exactly this: an entry's shape has only ONE author (`plan_convert`).

    A second expression here would calibrate the separator set on TWO writers — and that is
    exactly the derived reference that scored 12/12 against the tool and 2/10 against a human.
    """
    door = door_skeleton("x", "cap", (("plan/socle.md", "Socle"),))
    assert index_entry("plan/socle.md", "Socle") in door.splitlines()


def test_l_index_ecrit_est_reconnu_comme_une_DECLARATION_et_pas_comme_une_mention():
    """Staleness detection is structural (D167/D168): if the entry is not a declaration, an arc
    gone missing from disk would never be accused, and the index would silently stop being an index."""
    planning = plan_scaffold(folder="p/x", arcs=("Socle",))
    # The arc does NOT exist in the tree that was passed → `index_sans_fichier` must fire. If it
    # does not fire, that means the written line is not read as an entry.
    problems = index_problems(planning.door_text, (), folder_form=True)
    assert [p.kind for p in problems] == ["index_sans_fichier"], problems


def test_un_arc_present_et_NON_nomme_par_la_porte_est_accuse():
    """The complementary direction — without it, writing an arc and forgetting to index it would be silent."""
    planning = plan_scaffold(folder="p/x", arcs=("Socle",))
    problems = index_problems(planning.door_text, ("socle.md", "oublie.md"), folder_form=True)
    assert [p.kind for p in problems] == ["arc_hors_index"]
    assert "oublie.md" in problems[0].detail


# --- identities: one per arc, never a duplicate at the FOLDER scale -------------------------


def test_les_identites_de_deux_arcs_ne_se_marchent_jamais_dessus():
    """`id_duplique` applies to the FOLDER (D166 clause 5): numbering the arcs `A1 A2 A3` would have
    given every author a collision on their SECOND item — a defect caused by the scaffold."""
    planning = plan_scaffold(folder="p/x", arcs=("Un", "Deux", "Trois"))
    assert [arc.ident for arc in planning.arcs] == ["A1", "B1", "C1"]
    reading = fold(planning.door_text, members_of(planning))
    assert [p.kind for p in reading.problems] == []


def test_l_alphabet_des_identites_deborde_sans_collision_ni_identite_illisible():
    """The target scale is not 12 arcs: at the 27th, a malformed identity would become
    `identite_illisible` and the item would drop out of the count."""
    idents = [arc_ident(n) for n in range(60)]
    assert len(set(idents)) == 60
    assert idents[25] == "Z1" and idents[26] == "AA1"
    planning = plan_scaffold(folder="p/x", arcs=tuple(f"Arc numero {n}" for n in range(30)))
    reading = fold(planning.door_text, members_of(planning))
    assert reading.problems == ()
    assert len(reading.items) == 30


# --- RECURSION, proven by its failure ---------------------------------------------------------


def nested_pair():
    parent = plan_scaffold(folder="racine", cap="cap racine", arcs=("Socle",))
    sub = plan_scaffold(
        folder=f"racine/{ARCS_DIRNAME}/theorie-t001",
        project="T001",
        cap="cap du sous-plan",
        arcs=("Signaux",),
        existing=("racine/PLAN.md", f"racine/{ARCS_DIRNAME}/socle.md"),
        parent_door_text=parent.door_text,
    )
    return parent, sub


def test_un_sous_plan_recoit_l_entree_d_index_de_son_parent_dans_le_MEME_geste():
    parent, sub = nested_pair()
    assert sub.parent is not None
    assert sub.parent.member == f"{ARCS_DIRNAME}/theorie-t001/{PLAN_FILENAME}"
    assert sub.parent.entry == index_entry(sub.parent.member, "T001")
    assert sub.parent.entry in sub.parent.text.splitlines()


def test_SANS_cette_entree_le_sous_plan_naitrait_ORPHELIN_et_le_lecteur_l_accuse():
    """ The test that carries the clause. Without it, the parent's indexing could be removed
 without a single line turning red — and an orphaned sub-plan makes the barrier refuse the commit."""
    parent, sub = nested_pair()
    tree = (f"{ARCS_DIRNAME}/socle.md", f"{ARCS_DIRNAME}/theorie-t001/{PLAN_FILENAME}")
    arcs, nested = plan_entries("", tree)

    orphelin = index_problems(parent.door_text, arcs + nested, folder_form=True)
    assert [p.kind for p in orphelin] == ["arc_hors_index"], orphelin
    assert "theorie-t001" in orphelin[0].detail

    repare = index_problems(sub.parent.text, arcs + nested, folder_form=True)
    assert repare == (), repare


def test_le_sous_plan_a_sa_PROPRE_portee_d_identites():
    """Two different plans are each entitled to carry an `A1` — at the target scale, a hundred-odd
    theories will each name a strategy of the same name."""
    parent, sub = nested_pair()
    assert parent.arcs[0].ident == "A1" and sub.arcs[0].ident == "A1"
    verify_readability(
        sub,
        parent_members=(
            (f"{ARCS_DIRNAME}/socle.md", parent.arcs[0].text),
            (sub.parent.member, sub.door_text),
        ),
    )


# --- D176: a sub-plan INHERITS its parent's Format, never guessed, never imposed -------------
# FOUND BY AN ADVERSARIAL AUDIT, NOT BY ME (entry 16:3x): the declaration used not to inherit
# -- a sub-plan born under an ADOPTING parent used to be born NON-adopting, exactly where
# CLAUDE.md prescribes that an arc grown too big should be born (as a sub-plan). Measured on a real
# deployment (an internal handoff note): a declaration on the root door alone holds only
# 21/168 items (12.5%) without this inheritance.
def test_UN_SOUS_PLAN_HERITE_du_Format_DE_SON_PARENT_quand_il_n_en_declare_pas():
    parent = plan_scaffold(folder="racine", cap="cap racine", arcs=("Socle",), format_declare="produit")
    sub = plan_scaffold(
        folder=f"racine/{ARCS_DIRNAME}/theorie-t001",
        project="T001",
        arcs=("Signaux",),
        existing=("racine/PLAN.md", f"racine/{ARCS_DIRNAME}/socle.md"),
        parent_door_text=parent.door_text,
    )
    reading = read_plan(sub.door_text)
    assert reading.format_declare == "produit"


def test_UN_SOUS_PLAN_AVEC_SON_PROPRE_format_N_HERITE_JAMAIS_de_celui_du_parent():
    """EXPLICIT ALWAYS WINS: a sub-plan that wants a different format (or none) from its parent
    is never stuck with the inherited choice."""
    parent = plan_scaffold(folder="racine", cap="cap racine", arcs=("Socle",), format_declare="produit")
    sub = plan_scaffold(
        folder=f"racine/{ARCS_DIRNAME}/theorie-t001",
        project="T001",
        arcs=("Signaux",),
        existing=("racine/PLAN.md", f"racine/{ARCS_DIRNAME}/socle.md"),
        parent_door_text=parent.door_text,
        format_declare="fini_quand",
    )
    reading = read_plan(sub.door_text)
    assert reading.format_declare == "fini_quand"


def test_SOUS_UN_PARENT_NON_ADOPTANT_le_sous_plan_n_herite_de_RIEN():
    """The behaviour from before this fix, intact when there is nothing to inherit: a parent that
    has itself declared nothing passes on nothing -- D176 stays a choice, never imposed anywhere."""
    parent, sub = nested_pair()  # `nested_pair()` declares no `**Format**` at all
    assert read_plan(sub.door_text).format_declare == ""


def test_le_parent_choisi_est_le_plan_le_PLUS_PROCHE_jamais_l_ancetre():
    """`owning_plan`'s tie-break: notifying the grandparent would post the entry on a door nobody
    asked for it on, and would let the real parent lie."""
    existing = (
        "racine/PLAN.md",
        f"racine/{ARCS_DIRNAME}/t/PLAN.md",
        f"racine/{ARCS_DIRNAME}/t/{ARCS_DIRNAME}/socle.md",
    )
    interne = plan_scaffold(folder="racine", cap="c").door_text
    sub = plan_scaffold(
        folder=f"racine/{ARCS_DIRNAME}/t/{ARCS_DIRNAME}/s",
        existing=existing,
        parent_door_text=interne,
    )
    assert sub.parent is not None
    assert sub.parent.folder == f"racine/{ARCS_DIRNAME}/t"
    assert sub.parent.member == f"{ARCS_DIRNAME}/s/{PLAN_FILENAME}"


# --- EVERY refusal is PRODUCED, not merely named ----------------------------------------------------------


#: A real, readable parent door — just enough that `porte_parente_illisible` does not fire
#: and the neighbouring refusal can be proven ALONE.
PORTE_PARENTE = door_skeleton("Racine", "un cap", ((f"{ARCS_DIRNAME}/socle.md", "Socle"),))


def test_chaque_refus_declare_porte_un_GESTE_et_reciproquement():
    """The two tables are forcibly coupled: a refusal with no gesture would print a problem
    nobody can act on, a gesture with no refusal is dead text."""
    assert set(REFUSAL_LABEL) == set(_GESTE)


#: One entry per declared refusal, and it must produce it **ALONE**. The `set` on the left is
#: checked for exhaustiveness further down: adding a refusal without writing the entry that
#: triggers it here turns red.
_ENTREES_QUI_REFUSENT = [
    ({"folder": "", "project": "x"}, "chemin_manquant"),
    ({"folder": ".", "project": "x"}, "racine_du_depot"),
    ({"folder": "/ailleurs", "inside_repo": False}, "hors_depot"),
    ({"folder": "projects/mauvais-niveau"}, "profondeur_projet"),
    ({"folder": "projects/saas/alpha/sous-dossier"}, "profondeur_projet"),
    ({"folder": "p/x", "folder_is_file": True}, "chemin_occupe"),
    ({"folder": f"racine/{ARCS_DIRNAME}", "existing": ("racine/PLAN.md",)}, "dossier_des_arcs"),
    ({"folder": "p/x", "existing": ("p/x/PLAN.md",)}, "plan_existe"),
    ({"folder": "p/x", "existing": ("p/x/PLAN_COURANT.md",)}, "plan_existe"),
    # The file name of the DEFAULT arc, derived from the two constants that produce it rather
    # than retyped: this entry is the only one whose collision depends on what `plan_scaffold`
    # would write when no `arcs=` is given, so a rename of `DEFAULT_ARC_TITLE` used to make the
    # collision miss and this refusal stop being produced at all — green, proving nothing.
    (
        {"folder": "p/x", "existing": (f"p/x/{ARCS_DIRNAME}/{slugify(DEFAULT_ARC_TITLE)}.md",)},
        "arc_existe",
    ),
    ({"folder": "p/x", "arcs": ("Socle", "socle")}, "collision_de_nom"),
    ({"folder": "p/x", "arcs": ("Socle", "   ")}, "arc_sans_titre"),
    ({"folder": "a/ /"}, "nom_manquant"),
    ({"folder": "p/x", "cap": "un cap\n```"}, "texte_multiligne"),
    ({"folder": "p/x", "arcs": (f"Socle — {ARCS_DIRNAME}/fantome.md",)}, "texte_declare_un_chemin"),
    ({"folder": "p/x", "format_declare": "produit\n```"}, "texte_multiligne"),
    # MEASURED, NOT ASSUMED: unlike an arc title, `> **Format** : produit,
    # plan/fantome.md` does NOT trigger `texte_declare_un_chemin` -- `_declares()` requires one of
    # four structural shapes (bare column 0, list item, `—` separator, line = the path alone), and
    # a value after `> **Format** :` satisfies none of them. The `_text_refusals` guard is still
    # called regardless (same discipline as `cap`/`nom`), but this exact case does not fire on THIS
    # line -- verified by writing the test that follows, not assumed by symmetry with `cap`.
    (
        {"folder": f"racine/{ARCS_DIRNAME}/t", "existing": ("racine/PLAN.md",)},
        "porte_parente_illisible",
    ),
    (
        {
            "folder": f"racine/{ARCS_DIRNAME}/l'offre",
            "existing": ("racine/PLAN.md",),
            "parent_door_text": PORTE_PARENTE,
        },
        "chemin_non_indexable",
    ),
]


@pytest.mark.parametrize("kwargs, attendu", _ENTREES_QUI_REFUSENT)
def test_chaque_refus_est_PRODUCTIBLE_par_une_entree_qui_le_vise_et_TIRE_SEUL(kwargs, attendu):
    """ **ALONE**, and that is the assertion that changed. `nom_manquant` was declared, tested, and
 STRUCTURALLY unable to fire without `chemin_manquant` ahead of it: the only path that
 produced it was the empty path, which the other one catches first. So the user would read the
 neighbouring refusal's gesture — *"give a path"* — for a plan whose path had in fact been
 given. A refusal that cannot be the SOLE cause is not a cause: it was never proven on its own,
 and the day it truly fires, nobody has ever seen its sentence."""
    planning = plan_scaffold(**kwargs)
    assert {r.reason for r in planning.refusals} == {attendu}, planning.refusals
    assert planning.blocked


def test_profondeur_projet_NE_TIRE_PAS_sur_la_forme_correcte_bulle_projet():
    """ MANDATORY NEGATIVE CONTROL (measured by the isolated auditor, 3 agents, before this fix):
 `projects/<bubble>/<project>` must keep passing at RC 0. `scan_projects` reads exactly this
 depth (`plan_registry.py`: a bubble loop then a project loop, measured by reading its code)."""
    planning = plan_scaffold(folder="projects/saas/alpha")
    assert not planning.blocked, planning.refusals
    assert "profondeur_projet" not in {r.reason for r in planning.refusals}


def test_profondeur_projet_NE_TIRE_PAS_sur_un_sous_plan_reconnu():
    """A legitimate sub-plan (`owning_parent` recognises it, the same mechanism as
    `dossier_des_arcs`) can live at ANY depth under `projects/` without triggering this refusal —
    the clause targets ONLY paths that no existing mechanism already claims."""
    porte = door_skeleton("Alpha", "un cap", ((f"{ARCS_DIRNAME}/socle.md", "Socle"),))
    planning = plan_scaffold(
        folder=f"projects/saas/alpha/{ARCS_DIRNAME}/theories/t1",
        existing=("projects/saas/alpha/PLAN.md",),
        parent_door_text=porte,
    )
    assert "profondeur_projet" not in {r.reason for r in planning.refusals}, planning.refusals


def test_AUCUN_refus_declare_n_echappe_a_la_table_des_entrees_qui_le_produisent():
    """The only refusal no ENTRY produces is `squelette_illisible`, and that is its definition:
    it says the code has diverged, not that the request is at fault. It is proven by an injected
    divergence further down. Every other refusal must have an entry here that targets it — otherwise
    a refusal can be born declared, documented, and never once fire."""
    produits = {attendu for _, attendu in _ENTREES_QUI_REFUSENT}
    assert set(REFUSAL_LABEL) - produits == {"squelette_illisible"}


def test_une_seule_raison_bloque_TOUTE_la_naissance():
    """A half-written plan would be a plan the barrier refuses, and that would have to be repaired
    before anything else could be committed."""
    planning = plan_scaffold(folder="p/x", existing=("p/x/PLAN.md",), arcs=("Socle",))
    assert planning.blocked


def test_le_squelette_illisible_est_le_DERNIER_refus_et_il_leve():
    """`verify_readability` is the only judge that is not of this household. We hand it a
    sabotaged door: if it accepts it, that means the reader is no longer judging anything."""
    planning = plan_scaffold(folder="p/x", arcs=("Socle",))
    sans_cap = type(planning)(
        folder=planning.folder,
        project=planning.project,
        cap="",
        door_name=planning.door_name,
        door_text=planning.door_text.replace("> **Cap** :", "> Cap :"),
        arcs=planning.arcs,
    )
    with pytest.raises(ScaffoldMismatch, match="UNREADABLE"):
        verify_readability(sans_cap)


def test_verify_readability_MORD_sur_un_index_qui_ment():
    """Proof that the last guard is not decorative: we break the index entry by ONE character."""
    planning = plan_scaffold(folder="p/x", arcs=("Socle",))
    menteur = type(planning)(
        folder=planning.folder,
        project=planning.project,
        cap=planning.cap,
        door_name=planning.door_name,
        door_text=planning.door_text.replace("plan/socle.md", "plan/socle-absent.md"),
        arcs=planning.arcs,
    )
    with pytest.raises(ScaffoldMismatch) as refus:
        verify_readability(menteur)
    assert "index_sans_fichier" in str(refus.value)
    assert "arc_hors_index" in str(refus.value)


# --- the command: dry by default, writes under APPLY, never overwrites -------------------------------


def test_la_commande_SEC_n_ecrit_rien(tmp_path, capsys):
    code = main(["--repo-root", str(tmp_path), "projets/x"])
    assert code == 0
    assert not (tmp_path / "projets").exists()
    sortie = capsys.readouterr().out
    assert "Nothing was written" in sortie and "APPLY=1" in sortie


# DEFECT 1, FOUND BY AN AUTONOMY PROBE (D75, 2026-08-17), NOT BY ONE MORE AUDIT: a fresh
# agent, given the single instruction "adopt the standard," typed CAP= and FORMAT= and then
# copy-pasted the gesture the command proposed for APPLY=1 -- CAP= and FORMAT= had vanished,
# SILENTLY. The project believed it had adopted, the door that was born declared nothing, and
# everything stayed green.
def test_D1_le_geste_REJOUE_CAP_ET_FORMAT_recus(tmp_path, capsys):
    assert (
        main(
            [
                "--repo-root",
                str(tmp_path),
                "projets/x",
                "--cap",
                "fermer l'arc 6",
                "--format",
                "produit, fini_quand",
            ]
        )
        == 0
    )
    sortie = capsys.readouterr().out
    assert 'CAP="fermer l\'arc 6"' in sortie, sortie
    assert 'FORMAT="produit, fini_quand"' in sortie, sortie


def test_D1_le_geste_OMET_FORMAT_quand_rien_n_a_ete_recu(tmp_path, capsys):
    """Nothing received -> nothing replayed: `FORMAT=` absent, exactly the behaviour from before this."""
    assert main(["--repo-root", str(tmp_path), "projets/x"]) == 0
    assert "FORMAT=" not in capsys.readouterr().out


def test_D1_le_geste_OMET_FORMAT_quand_HERITE_du_parent(tmp_path, capsys):
    """A sub-plan that INHERITS (nothing explicit) must replay FORMAT= ABSENT, not the inherited
    value: the omission lets the inheritance reproduce IDENTICALLY on the second call (same parent,
    same disk) -- freezing it would silently disguise an inheritance as an explicit choice."""
    assert main(["--repo-root", str(tmp_path), "projets/x", "--format", "produit", "--apply"]) == 0
    capsys.readouterr()
    assert main(["--repo-root", str(tmp_path), "projets/x/plan/sous"]) == 0
    sortie = capsys.readouterr().out
    assert "WILL REFUSE this first item" in sortie, sortie  # the inheritance really is active
    assert "FORMAT=" not in sortie, sortie  # but never frozen into the replay


def test_D1_REJOUER_le_geste_montre_PRODUIT_EXACTEMENT_ce_qu_il_a_montre(tmp_path, capsys):
    """The strongest proof: do not trust the text -- extract CAP=/FORMAT= from the line that was
    shown, replay them for real with `--apply`, and re-read the result FROM DISK."""
    import re

    from mnemosyne.production.plan_registry import read_plan_tree

    assert (
        main(
            [
                "--repo-root",
                str(tmp_path),
                "projets/x",
                "--cap",
                "un cap précis",
                "--format",
                "produit",
            ]
        )
        == 0
    )
    geste = re.search(r"^make plan-nouveau .+$", capsys.readouterr().out, re.MULTILINE)
    assert geste, "no « Le geste » line found"
    cap = re.search(r'CAP="([^"]*)"', geste.group(0))
    fmt = re.search(r'FORMAT="([^"]*)"', geste.group(0))
    assert cap and fmt, geste.group(0)

    assert (
        main(
            [
                "--repo-root",
                str(tmp_path),
                "projets/x",
                "--cap",
                cap.group(1),
                "--format",
                fmt.group(1),
                "--apply",
            ]
        )
        == 0
    )
    lus = read_plan_tree(tmp_path / "projets" / "x", "x")
    assert lus[0].reading.cap == "un cap précis"
    assert lus[0].reading.format_declare == "produit"


# R3, ISOLATED AUDIT (D75): "readable" (D166) DOES NOT IMPLY "passes the D176 barrier once
# installed." The skeleton (`DEFAULT_ITEM`) fills in no field -- if `**Format**` is declared
# (supplied or inherited), the D176 barrier will refuse it as-is. Staying silent about this let
# people believe a formatted plan is ready to commit.
# THE NEGATIVE HALF BELOW IS THE ONE THAT ROTS: it stayed GREEN while the sentence it looks for
# had been reworded in the surface -- a needle that no longer exists anywhere is absent from every
# output, so the witness passes and measures NOTHING. Its twin just below is what proves the needle
# is still the surface's own words: the two must be read as a pair, never separately.
def test_R3_SANS_format_la_confirmation_NE_PORTE_PAS_l_avertissement_D176(tmp_path, capsys):
    assert main(["--repo-root", str(tmp_path), "projets/x", "--apply"]) == 0
    assert "WILL REFUSE this first item" not in capsys.readouterr().out


def test_R3_AVEC_format_la_confirmation_AVERTIT_que_le_squelette_sera_REFUSE(tmp_path, capsys):
    assert (
        main(["--repo-root", str(tmp_path), "projets/x", "--format", "produit", "--apply"]) == 0
    )
    sortie = capsys.readouterr().out
    assert "WILL REFUSE this first item" in sortie and "D176" in sortie


def test_la_commande_APPLY_ecrit_un_plan_que_le_lecteur_relit_DEPUIS_LE_DISQUE(tmp_path):
    """Nothing is judged on what the command claims to have written: the bytes laid down are re-read."""
    from mnemosyne.production.plan_registry import read_plan_tree

    assert main(["--repo-root", str(tmp_path), "projets/x", "--cap", "un cap", "--apply"]) == 0
    folder = tmp_path / "projets" / "x"
    assert (folder / PLAN_FILENAME).is_file()
    assert (folder / ARCS_DIRNAME / f"{slugify(DEFAULT_ARC_TITLE)}.md").is_file()

    lus = read_plan_tree(folder, "x")
    assert len(lus) == 1 and lus[0].state == "lisible", [p.why for p in lus]
    assert lus[0].reading.cap == "un cap"
    assert len(lus[0].reading.items) == 1


def test_la_commande_REFUSE_d_ecraser_un_plan_existant(tmp_path, capsys):
    assert main(["--repo-root", str(tmp_path), "projets/x", "--apply"]) == 0
    avant = (tmp_path / "projets" / "x" / PLAN_FILENAME).read_text(encoding="utf-8")
    assert main(["--repo-root", str(tmp_path), "projets/x", "--apply"]) == 1
    sortie = capsys.readouterr().out
    assert "plan_existe" in sortie and "inv. 2" in sortie
    assert (tmp_path / "projets" / "x" / PLAN_FILENAME).read_text(encoding="utf-8") == avant


def test_la_commande_ecrit_un_SOUS_plan_et_met_a_jour_la_porte_du_parent(tmp_path):
    """Three levels, on disk, re-read by the reader — each one a plan in its own right."""
    from mnemosyne.production.plan_registry import read_plan_tree

    assert main(["--repo-root", str(tmp_path), "racine", "--apply"]) == 0
    assert main(["--repo-root", str(tmp_path), f"racine/{ARCS_DIRNAME}/t1", "--apply"]) == 0
    profond = f"racine/{ARCS_DIRNAME}/t1/{ARCS_DIRNAME}/s1"
    assert main(["--repo-root", str(tmp_path), profond, "--apply"]) == 0

    lus = read_plan_tree(tmp_path / "racine", "racine")
    etats = {plan.name: plan.state for plan in lus}
    assert set(etats.values()) == {"lisible"}, [(p.name, p.why) for p in lus]
    assert len(lus) == 3, etats


def test_la_commande_REFUSE_un_chemin_hors_du_depot(tmp_path, capsys):
    assert main(["--repo-root", str(tmp_path), "../dehors", "--apply"]) == 1
    assert "hors_depot" in capsys.readouterr().out
    assert not (tmp_path.parent / "dehors").exists()


def test_le_defaut_est_UN_arc_nomme_et_pas_un_plan_vide(tmp_path):
    planning = plan_scaffold(folder="p/x")
    assert [arc.title for arc in planning.arcs] == [DEFAULT_ARC_TITLE]


# --- WIDTH: SIBLINGS, not just depth -----------------------------------
#
# Depth was proven (root → t1 → s1) and width was not — TWO siblings under the
# same parent were never proven anywhere. This is exactly the hole that was killing recursion, the
# whole reason D166 exists: the SECOND sub-plan was refused, and the named cause was false.


def test_TROIS_sous_plans_FRERES_naissent_sous_le_MEME_parent_et_le_lecteur_les_voit_TOUS(tmp_path):
    """ The new criterion. Three siblings **and** one grandchild, written to disk and re-read by the
 real reader. What was breaking: the internal check walked the parent's `plan/` with its own
 `rglob` and returned 4 paths where `plan_entries` returns 1 + 2 — the first sibling's arc
 entered the PARENT's identity registry, and the parent's `A1` became an `id_duplique`.
 Two siblings are enough to show it; three are used so it isn't just "the second one.\""""
    from mnemosyne.production.plan_registry import read_plan_tree

    racine = "racine"
    assert main(["--repo-root", str(tmp_path), racine, "--apply"]) == 0
    for frere in ("t1", "t2", "t3"):
        chemin = f"{racine}/{ARCS_DIRNAME}/{frere}"
        assert main(["--repo-root", str(tmp_path), chemin, "--apply"]) == 0, frere
    petit_fils = f"{racine}/{ARCS_DIRNAME}/t2/{ARCS_DIRNAME}/s1"
    assert main(["--repo-root", str(tmp_path), petit_fils, "--apply"]) == 0

    lus = read_plan_tree(tmp_path / racine, racine)
    assert {plan.state for plan in lus} == {"lisible"}, [(p.name, p.why) for p in lus]
    assert len(lus) == 5, [p.name for p in lus]
    # Each plan keeps ITS OWN identity scope: five plans, five `A1`s, no `id_duplique`.
    assert [len(plan.reading.items) for plan in lus] == [1, 1, 1, 1, 1]

    porte = (tmp_path / racine / PLAN_FILENAME).read_text(encoding="utf-8")
    for frere in ("t1", "t2", "t3"):
        assert f"{ARCS_DIRNAME}/{frere}/{PLAN_FILENAME}" in porte, frere


def test_l_echafaudage_et_le_JUGE_plient_le_MEME_arbre_de_la_MEME_facon(tmp_path):
    """The class, held right where it lives: a single enumeration. The same tree is folded twice —
    in memory via the birth path, on disk via `read_plan_tree` — and the SAME item count and the
    SAME problems are required. Two disk walks are two opinions; the day they diverge, a file is
    judged by neither one (measured: the command was refusing what the barrier was accepting)."""
    from mnemosyne.production.plan_registry import arc_tree, read_plan_tree
    from mnemosyne.production.plan_scaffold import _fold

    assert main(["--repo-root", str(tmp_path), "racine", "--apply"]) == 0
    assert main(["--repo-root", str(tmp_path), f"racine/{ARCS_DIRNAME}/t1", "--apply"]) == 0
    folder = tmp_path / "racine"

    membres = tuple(
        (relative, (folder / relative).read_text(encoding="utf-8"))
        for relative in arc_tree(folder)
    )
    en_memoire = _fold((folder / PLAN_FILENAME).read_text(encoding="utf-8"), membres)
    sur_le_disque = read_plan_tree(folder, "racine")[0].reading

    assert len(en_memoire.items) == len(sur_le_disque.items) == 1
    assert en_memoire.problems == sur_le_disque.problems == ()
    assert en_memoire.parts == sur_le_disque.parts


# --- what birth touches OF THE WORLD: the parent door, and nothing else ----------------------


def _porte_avec_exemple_fence() -> str:
    """A door that SHOWS what an index looks like, inside a ```markdown block — what a door that
    documents its own shape actually writes."""
    door = door_skeleton("p", "cap", ((f"{ARCS_DIRNAME}/socle.md", "Socle"),))
    # A `.replace` whose anchor no longer exists is a fixture that SILENTLY BUILDS NOTHING: the
    # door came back untouched, the example block was never inserted, and the witness below stopped
    # measuring the case it was written for. Anchored on the door's own closing comment — asserted,
    # not assumed, so the day it moves this fixture says so instead of quietly going flat.
    ancre = "<!-- This plan"
    assert ancre in door, f"the door no longer opens its closing comment with {ancre!r}"
    return door.replace(
        ancre,
        f"```markdown\n- `{ARCS_DIRNAME}/exemple.md` — un EXEMPLE\n```\n\n{ancre}",
    )


def test_l_entree_se_pose_JUSTE_APRES_la_derniere_entree_VIVANTE_jamais_dans_un_exemple():
    """Two guarantees in a single position, and each one was held by nobody.

    * **the POSITION** — `lines.insert(last + 1, …)` replaced by `insert(0, …)` used to pass: the
      entry landed before the plan's title, an absurd door, reader AND barrier both green;
    * **the fact that it is LIVE** — the search ran over the raw lines, so the entry
      landed INSIDE the example block. Birth exit 0, commit exit 0, and nothing said so:
      `arc_hors_index` counts a mention anywhere, blocks included, ON PURPOSE (D167). The sub-plan
      was invisible in the rendered index.
    """
    door = _porte_avec_exemple_fence()
    entry = index_entry(f"{ARCS_DIRNAME}/t/{PLAN_FILENAME}", "T")
    out = _post_entry(door, entry)

    lignes = out.splitlines()
    n = lignes.index(entry)
    assert n > 0 and _DECLARING_LINE.search(lignes[n - 1]), f"placed at {n}: {lignes[max(n - 1, 0)]!r}"
    assert live_lines(out)[n], "the entry landed INSIDE a code block"
    # And the example has not moved: it stays inside its block, dead.
    exemple = lignes.index(f"- `{ARCS_DIRNAME}/exemple.md` — un EXEMPLE")
    assert not live_lines(out)[exemple]


def test_UNE_PROSE_QUI_CITE_UN_CHEMIN_N_EST_PAS_UNE_ENTREE_BR2_a():
    """BR2(a), the REAL case from the defect report, reconstructed: a door whose closing paragraph
    explains why a path stays indexed (`` `plan/README.md` exists because… ``) is a LIVE line
    that NAMES that path — and the first shape of `_DECLARING_LINE` matched any live mention, so
    the new entry landed RIGHT IN THE MIDDLE of that sentence, cutting it in two. What this test
    proves: prose stays prose, the entry lands after the LAST REAL index entry, never after a
    sentence that merely quotes the same path."""
    door = door_skeleton("p", "cap", ((f"{ARCS_DIRNAME}/socle.md", "Socle"),))
    prose = (
        f"*(Cette dernière ligne n'est pas une coquetterie : `{ARCS_DIRNAME}/socle.md` existe "
        "parce que la porte l'exige. Le lecteur en a besoin.)*"
    )
    door_avec_prose = door.rstrip("\n") + "\n\n" + prose + "\n"
    entry = index_entry(f"{ARCS_DIRNAME}/t/{PLAN_FILENAME}", "T")

    out = _post_entry(door_avec_prose, entry)

    lignes = out.splitlines()
    n = lignes.index(entry)
    # The sentence was not cut in two: it still appears as a single block, AFTER the new entry.
    assert prose in out, "the prose was altered or split"
    assert out.index(entry) < out.index(prose), "the entry landed AFTER the prose, not before"
    # And the real anchor is indeed the last REAL index entry, not the line of prose.
    assert lignes[n - 1] == f"- `{ARCS_DIRNAME}/socle.md` — Socle", lignes[n - 1]


def test_la_porte_parente_en_CRLF_garde_ses_OCTETS_de_fin_de_ligne():
    """The parent door is the ONLY pre-existing file this command touches, and it used to rewrite
    bytes nobody asked to have changed: `splitlines()` + `"\\n".join()` converted a CRLF door to
    LF — measured, 24 carriage returns in, **0** out. Bytes get moved, not rewritten."""
    door = door_skeleton("p", "cap", ((f"{ARCS_DIRNAME}/socle.md", "Socle"),)).replace("\n", "\r\n")
    entry = index_entry(f"{ARCS_DIRNAME}/t/{PLAN_FILENAME}", "T")
    out = _post_entry(door, entry)

    assert out.count("\r\n") == door.count("\r\n") + 1, "the door changed its line-ending style"
    assert out.count("\n") == out.count("\r\n"), "a bare LF slipped into a CRLF door"
    assert door.rstrip("\r\n") in out.replace(f"{entry}\r\n", "")


def test_une_porte_parente_SANS_derniere_fin_de_ligne_n_en_gagne_pas_une():
    """The counterpart: the day the last index line IS the file's last line, the old
    code kept "no trailing newline"; the new one must keep it too, or it rewrites a byte."""
    door = door_skeleton("p", "cap", ((f"{ARCS_DIRNAME}/socle.md", "Socle"),))
    tronquee = door[: door.index(f"`{ARCS_DIRNAME}/socle.md`")] + f"`{ARCS_DIRNAME}/socle.md` — Socle"
    entry = index_entry(f"{ARCS_DIRNAME}/t/{PLAN_FILENAME}", "T")
    out = _post_entry(tronquee, entry)
    assert not out.endswith("\n")
    assert out.splitlines()[-1] == entry


# --- THE LAST GUARD BITES ALL THE WAY THROUGH THE COMMAND, and nothing is written -----------------------------


def _diverger(monkeypatch, casse):
    """Make the scaffold diverge from the reader, at the exact spot `squelette_illisible` names.

    This is the only honest way to prove this refusal now: everything a CALLER could get wrong has
    become a named refusal that accuses their input. What is left here is exactly what the name
    says — the scaffold and the reader have diverged, and nobody typed anything wrong.
    """
    from mnemosyne.runtime import plan_new_run as module

    vrai = module.plan_scaffold
    monkeypatch.setattr(module, "plan_scaffold", lambda **kw: casse(vrai(**kw)))


def test_la_commande_N_ECRIT_RIEN_quand_le_LECTEUR_refuse_les_octets(tmp_path, capsys, monkeypatch):
    """ The whole promise: the reader judges BEFORE the write. Removing the call to
 `verify_readability` used to survive the entire suite — the cost was then only paid at the
 NEXT commit, with a broken plan already on disk. Here the scaffold returns a door with no cap."""
    _diverger(
        monkeypatch,
        lambda p: dataclasses.replace(p, door_text=p.door_text.replace("> **Cap** :", "> Cap :")),
    )
    assert main(["--repo-root", str(tmp_path), "projets/x", "--apply"]) == 1
    assert not (tmp_path / "projets").exists(), "bytes were written despite the refusal"
    sortie = capsys.readouterr().out
    assert "squelette_illisible" in sortie, "the refusal does not print its token: nothing can pin it down"
    assert "UNREADABLE" in sortie


def test_la_porte_PARENTE_garde_ses_octets_quand_le_lecteur_refuse_le_resultat(
    tmp_path, capsys, monkeypatch
):
    """The second half of the same guard, on the only pre-existing file the command touches:
    the parent's index entry is erased from the resulting text, so the sub-plan would be born
    ORPHANED. Nothing must go out — neither the sub-plan, nor a single byte of the parent door."""
    assert main(["--repo-root", str(tmp_path), "racine", "--apply"]) == 0
    porte = tmp_path / "racine" / PLAN_FILENAME
    avant = hashlib.sha256(porte.read_bytes()).hexdigest()

    _diverger(
        monkeypatch,
        lambda p: dataclasses.replace(p, parent=dataclasses.replace(p.parent, text=p.parent.before)),
    )
    assert main(["--repo-root", str(tmp_path), f"racine/{ARCS_DIRNAME}/t1", "--apply"]) == 1
    assert not (tmp_path / "racine" / ARCS_DIRNAME / "t1").exists()
    assert hashlib.sha256(porte.read_bytes()).hexdigest() == avant
    assert "squelette_illisible" in capsys.readouterr().out


def test_une_porte_parente_DEJA_cassee_n_est_PAS_mise_sur_le_dos_de_Mnemosyne(tmp_path, capsys):
    """The named cause must be TRUE. A parent already unreadable — here, a code block that was
    never closed — used to print « it is a defect of Mnemosyne, not a mistake in your request » and
    send the caller off to file a false defect report. The parent is folded TWICE: once in the
    state it is already in, then in the state the birth would leave it in."""
    assert main(["--repo-root", str(tmp_path), "racine", "--apply"]) == 0
    porte = tmp_path / "racine" / PLAN_FILENAME
    porte.write_text(porte.read_text(encoding="utf-8") + "\n```markdown\n", encoding="utf-8")

    assert main(["--repo-root", str(tmp_path), f"racine/{ARCS_DIRNAME}/t1", "--apply"]) == 1
    sortie = capsys.readouterr().out
    assert "porte_parente_illisible" in sortie and "ALREADY unreadable" in sortie
    assert "make signaler" not in sortie
    assert "squelette_illisible" not in sortie


def test_la_distinction_porte_cassee_AVANT_vs_APRES_est_portee_par_DEUX_exceptions():
    """The counterpart of the test above, on the home: a healthy parent whose readability our
    entry would break remains OUR fault. Without both, the distinction would just be a word in a
    message."""
    parent, sub = nested_pair()
    membres = ((f"{ARCS_DIRNAME}/socle.md", parent.arcs[0].text), (sub.parent.member, sub.door_text))

    verify_readability(sub, parent_members=membres)  # the real state: nothing raises

    casse = dataclasses.replace(
        sub, parent=dataclasses.replace(sub.parent, text=sub.parent.before, before=sub.parent.before)
    )
    with pytest.raises(ScaffoldMismatch) as notre_faute:
        verify_readability(casse, parent_members=membres)
    assert not isinstance(notre_faute.value, ParentDoorUnreadable)

    deja = "# PLAN — p\n\nsans cap\n\n- `plan/socle.md` — Socle\n"
    with pytest.raises(ParentDoorUnreadable):
        verify_readability(
            dataclasses.replace(
                sub, parent=dataclasses.replace(sub.parent, before=deja, text=_post_entry(deja, sub.parent.entry))
            ),
            parent_members=membres,
        )


# --- invariant 2 AT THE SYSCALL: a file that appears between the scan and the write is never overwritten ---------


def test_un_ARC_apparu_entre_le_scan_et_l_ecriture_n_est_PAS_ecrase(tmp_path):
    """`open(..., "x")` replaced by `"w"` used to survive: the race between the existence scan and
    the write was proven by nobody, and it is the only thing defending invariant 2 once the scan
    has already answered. So the planner is lied to (`existing=()`) and the third party's file is
    placed on disk."""
    planning = plan_scaffold(folder="p/x", arcs=("Socle",))
    arc = tmp_path / "p" / "x" / ARCS_DIRNAME / "socle.md"
    arc.parent.mkdir(parents=True)
    arc.write_text("le travail de quelqu'un d'autre\n", encoding="utf-8")

    with pytest.raises(FileExistsError):
        apply_planning(planning, tmp_path)
    assert arc.read_text(encoding="utf-8") == "le travail de quelqu'un d'autre\n"


def test_une_PORTE_apparue_entre_le_scan_et_l_ecriture_n_est_PAS_ecrasee(tmp_path):
    """The twin, on the other open call — a bare `"w"` there used to pass too."""
    planning = plan_scaffold(folder="p/x", arcs=("Socle",))
    porte = tmp_path / "p" / "x" / PLAN_FILENAME
    porte.parent.mkdir(parents=True)
    porte.write_text("# PLAN — le plan de quelqu'un d'autre\n", encoding="utf-8")

    with pytest.raises(FileExistsError):
        apply_planning(planning, tmp_path)
    assert porte.read_text(encoding="utf-8") == "# PLAN — le plan de quelqu'un d'autre\n"


# --- what the PATH must never do --------------------------------------------------------


def test_le_chemin_POINT_ne_pose_rien_a_la_RACINE_du_depot(tmp_path, capsys):
    """`CHEMIN="."` used to propose `./PLAN.md` and `./plan/socle.md` — i.e. a door and an arcs
    folder AT THE ROOT of Mnémosyne, a project named `.`, and the commit used to pass. `CLAUDE.md`
    forbids any addition at the root without an explicit test."""
    assert main(["--repo-root", str(tmp_path), ".", "--apply"]) == 1
    assert not (tmp_path / PLAN_FILENAME).exists()
    assert not (tmp_path / ARCS_DIRNAME).exists()
    sortie = capsys.readouterr().out
    assert "racine_du_depot" in sortie and "chemin_manquant" not in sortie


def test_le_chemin_qui_EST_le_dossier_d_arcs_d_un_plan_est_refuse_et_le_parent_reste_LISIBLE(
    tmp_path, capsys
):
    """A very plausible typo — `<project>/plan` instead of `<project>` — and it used to
    DESTROY the plan above it while announcing a success: birth exit 0, commit exit 0, then
    `make plans` answers « PLAN.md présent mais ILLISIBLE » with two `arc_hors_index`."""
    from mnemosyne.production.plan_registry import read_plan_tree

    assert main(["--repo-root", str(tmp_path), "racine", "--apply"]) == 0
    avant = hashlib.sha256((tmp_path / "racine" / PLAN_FILENAME).read_bytes()).hexdigest()

    assert main(["--repo-root", str(tmp_path), f"racine/{ARCS_DIRNAME}", "--apply"]) == 1
    sortie = capsys.readouterr().out
    assert "dossier_des_arcs" in sortie
    assert not (tmp_path / "racine" / ARCS_DIRNAME / PLAN_FILENAME).exists()
    assert hashlib.sha256((tmp_path / "racine" / PLAN_FILENAME).read_bytes()).hexdigest() == avant

    lus = read_plan_tree(tmp_path / "racine", "racine")
    assert [plan.state for plan in lus] == ["lisible"], [(p.name, p.why) for p in lus]


def test_un_SOUS_dossier_du_dossier_d_arcs_reste_parfaitement_legal(tmp_path):
    """The symmetrical hole of the refusal above, and it is named: refusing "any folder called
    `plan`" would have forbidden nesting itself. Only the arcs folder ITSELF is refused."""
    assert main(["--repo-root", str(tmp_path), "racine", "--apply"]) == 0
    assert main(["--repo-root", str(tmp_path), f"racine/{ARCS_DIRNAME}/t1", "--apply"]) == 0
    assert (tmp_path / "racine" / ARCS_DIRNAME / "t1" / PLAN_FILENAME).is_file()


# --- "your entry contains this" is not "the code has diverged" ---------------------------------


@pytest.mark.parametrize(
    "args, jeton, mot",
    [
        (["--arc", f"Socle — {ARCS_DIRNAME}/fantome.md"], "texte_declare_un_chemin", "fantome.md"),
        (["--nom", f"{ARCS_DIRNAME}/autre.md"], "texte_declare_un_chemin", "autre.md"),
        (["--cap", "un cap\n```"], "texte_multiligne", "un cap"),
        (["--format", "produit\n```"], "texte_multiligne", "produit"),
    ],
)
def test_une_entree_FAUTIVE_accuse_l_ENTREE_et_n_envoie_plus_signaler(
    tmp_path, capsys, args, jeton, mot
):
    """The three ordinary inputs that `squelette_illisible` used to blame on Mnémosyne. The
    measured consequence was not cosmetic: the agent would file a FALSE defect report into the
    user's queue and walk away with no plan, when one word of its own title was enough to explain it."""
    assert main(["--repo-root", str(tmp_path), "projets/x", *args, "--apply"]) == 1
    assert not (tmp_path / "projets").exists()
    sortie = capsys.readouterr().out
    assert jeton in sortie and mot in sortie
    assert "make signaler" not in sortie
    # A DEAD NEGATIVE PROBE, found on 2026-09-09: the needle was still the French sentence long
    # after the surface had reworded it, so it was absent from EVERY output and this line passed
    # without measuring anything. Kept SHORT on purpose — lengthening the needle of a `not in` is
    # what makes it easier to satisfy, never harder.
    assert "defect of Mnemosyne" not in sortie


# --- THE PATH is a value that lands in a DOCUMENT, so it goes through the SAME filter ----------


#: The seven folder names of the reproduction — four the index reader can read, three it cannot.
#: Written BY HAND and frozen here: a population derived from what the tool writes scores twelve
#: out of twelve against the tool and two out of ten against a human (D170).
NOMS_LISIBLES = ("Horizon Research", "Café", "go-to-market", "phase-1")
NOMS_AVEUGLANTS = {"l'offre": "'", "rapports (200)": "(", "phase 2, data": ","}


def _sous_plan(nom: str):
    """Scaffold a SUB-plan housed in a folder called `nom`, under a healthy parent."""
    return plan_scaffold(
        folder=f"racine/{ARCS_DIRNAME}/{nom}",
        existing=("racine/PLAN.md", f"racine/{ARCS_DIRNAME}/socle.md"),
        parent_door_text=PORTE_PARENTE,
    )


@pytest.mark.parametrize("nom", NOMS_LISIBLES)
def test_un_nom_de_dossier_ORDINAIRE_fait_naitre_un_sous_plan(nom):
    """The counterpart, and it comes FIRST: the new refusal must not eat the names that used to
    work.

    "Horizon Research" carries a space, "Café" an accent — two shapes the reader's character
    class admits ON PURPOSE (1775 of the 8165 paths under `projects/` carry a space)."""
    planning = _sous_plan(nom)
    assert planning.refusals == (), planning.refusals
    assert planning.parent is not None


@pytest.mark.parametrize("nom, caractere", sorted(NOMS_AVEUGLANTS.items()))
def test_un_nom_de_dossier_que_le_lecteur_ne_SAIT_PAS_LIRE_accuse_le_CHEMIN(nom, caractere):
    """ Three ORDINARY French names out of seven used to produce a FALSE DEFECT REPORT.

 `--nom`, `--cap` and `--arc` went through the caller filter; the PATH — the value the user
 types most often — went VERBATIM into the parent door's index entry and was filtered by
 nothing. It therefore reached the LAST guard, `squelette_illisible`, whose sentence says
 *« c'est un défaut de Mnémosyne, pas une faute de ta demande »* and sends the caller to
 `make signaler`: a false report in the user's queue, and no plan.

 What is asserted here is the NAMED CAUSE, not merely the block — that is the whole difference
 between a refusal and a false accusation."""
    planning = _sous_plan(nom)
    assert {r.reason for r in planning.refusals} == {"chemin_non_indexable"}, planning.refusals
    assert caractere in planning.refusals[0].detail, planning.refusals[0].detail
    assert "squelette_illisible" not in {r.reason for r in planning.refusals}


@pytest.mark.parametrize("nom", [*NOMS_LISIBLES, *NOMS_AVEUGLANTS])
def test_LE_TROU_SYMETRIQUE_un_plan_de_PREMIER_NIVEAU_accepte_TOUS_ces_noms(nom):
    """ The hole dug by closing the other one, and it is just as serious.

 A top-level plan's own path never enters ANY document: its door only indexes
 `plan/<arc>.md`, never its own folder. A refusal that targeted the path without checking
 whether it actually lands anywhere would forbid `racine/l'offre` without any reader ever
 complaining — the rule filters a value BECAUSE IT LANDS somewhere, never because it exists."""
    planning = plan_scaffold(folder=f"racine/{nom}", existing=())
    assert planning.refusals == (), planning.refusals
    assert planning.parent is None


def test_les_caracteres_AVEUGLANTS_sont_LUS_chez_le_juge_jamais_ecrits_ici():
    """ The reference is not a list of characters: it is the judge itself, probed one character
 at a time. A list written here would age away from the regex that judges the commit — the
 class D170 was paid for (twelve out of twelve against the tool, two out of ten against a
 human).

 The check is a SET EQUALITY, in both directions: a character the probe declares blinding
 must really make an entry invisible, and a character it declares safe must really leave the
 entry visible. `>=` would let a character disappear in silence."""
    import string

    alphabet = sorted(set(string.printable.strip()) | {" ", "’", "é", "—"})
    aveuglants = set(blinding_characters("".join(alphabet)))
    #: The JUDGE's verdict on a real member carrying this character — the other reference, not
    #: derived from the probe: it goes through `index_problems`, the function the barrier runs.
    invisibles = {
        char
        for char in alphabet
        if index_problems(
            index_entry(f"{ARCS_DIRNAME}/dossier{char}x/{PLAN_FILENAME}", "t"),
            (f"dossier{char}x/{PLAN_FILENAME}",),
            folder_form=True,
        )
    }
    assert aveuglants == invisibles, (
        f"déclarés aveuglants et pourtant lisibles : {sorted(aveuglants - invisibles)} · "
        f"déclarés sûrs et pourtant invisibles : {sorted(invisibles - aveuglants)}"
    )
    # Non-vacuity floor: "the two sets are equal" is trivially true if they are both
    # empty, which is exactly the state of a probe that has stopped probing.
    assert len(aveuglants) >= 8, f"{len(aveuglants)} caractères aveuglants — la sonde ne sonde plus"
    assert "'" in aveuglants and "é" not in aveuglants and " " not in aveuglants


# --- refusing a TEXT aligns with the JUDGE's predicate, not with a bare regex -----------------


def test_un_titre_qui_MENTIONNE_un_chemin_sans_le_DECLARER_n_est_plus_refuse():
    """`texte_declare_un_chemin` used to ask `first_arc_reference` — *"does this text contain a
    path?"* — when the judge asks about POSITION. A title citing `racine/plan/arc-c.md` in the
    middle of a sentence used to be refused with a justification (*"it would demand a file
    nobody will ever write"*) that was FALSE for its class.

    The proof rests on two inseparable halves: the refusal disappears **and** the judge, on the
    door actually produced, returns nothing. The first half alone would only prove the check had
    been loosened."""
    titre = f"Socle — voir racine/{ARCS_DIRNAME}/arc-c.md pour le détail"
    planning = plan_scaffold(folder="p/x", arcs=(titre,))
    assert planning.refusals == (), planning.refusals
    tree = tuple(arc.member for arc in planning.arcs)
    assert index_problems(planning.door_text, tuple(t[len(ARCS_DIRNAME) + 1 :] for t in tree),
                          folder_form=True) == ()


def test_un_titre_qui_DECLARE_vraiment_un_chemin_est_TOUJOURS_refuse():
    """The counterpart of the test above, without which it would just be a loosening: behind
    the index entry's separator, the path IS a declaration, and the judge would raise
    `index_sans_fichier` for a file nobody will ever write."""
    planning = plan_scaffold(folder="p/x", arcs=(f"Socle — {ARCS_DIRNAME}/fantome.md",))
    assert {r.reason for r in planning.refusals} == {"texte_declare_un_chemin"}


def test_l_ORDRE_des_deux_refus_d_appelant_decide_de_la_CAUSE_nommee():
    """ This guarantee was written in a docstring and held by NOBODY: swapping the two blocks
 of `_text_refusals` left 462 tests green.

 A value carrying BOTH faults must accuse the LINE BREAK — that is what the caller must
 fix; the path is only a consequence of the line that got cut. *The order of my checks decides
 the cause that gets named.*"""
    planning = plan_scaffold(folder="p/x", cap=f"un cap\n{ARCS_DIRNAME}/x.md")
    assert {r.reason for r in planning.refusals} == {"texte_multiligne"}, planning.refusals


# --- the parent door's line ending is READ, on BOTH branches ----------------------------


def test_une_porte_parente_CRLF_dont_l_INDEX_EST_ENCORE_VIDE_garde_ses_octets():
    """The `last is None` branch — a door that names no arc yet, which is the case for a
    SINGLE-FILE plan at the exact moment it becomes a folder. It has no index line to copy a line
    ending from, so it is the ONLY one that consults `_line_ending`: hard-coding `"\\n"` used to
    survive 462 tests here, and would convert the door to LF (6 carriage returns instead of 7)."""
    door = door_skeleton("p", "cap", ()).replace("\n", "\r\n")
    entry = index_entry(f"{ARCS_DIRNAME}/t/{PLAN_FILENAME}", "T")
    out = _post_entry(door, entry)

    # `+ 2`: the blank line that separates the entry from what precedes it, then the entry itself.
    assert out.count("\r") == door.count("\r") + 2, "la porte a changé de style de fin de ligne"
    assert out.count("\n") == out.count("\r\n"), "un LF nu s'est glissé dans une porte CRLF"
    assert entry in out.splitlines()


def test_une_porte_parente_CRLF_SANS_fin_de_ligne_finale_garde_ses_octets():
    """The other branch that consults `_line_ending`: the last index line IS the file's last
    line, so it carries no line ending to copy. Same defect, same silence — 4 carriage returns
    returned instead of 5."""
    door = door_skeleton("p", "cap", ((f"{ARCS_DIRNAME}/socle.md", "Socle"),)).replace("\n", "\r\n")
    tronquee = door[: door.index(f"`{ARCS_DIRNAME}/socle.md`")] + f"`{ARCS_DIRNAME}/socle.md` — Socle"
    entry = index_entry(f"{ARCS_DIRNAME}/t/{PLAN_FILENAME}", "T")
    out = _post_entry(tronquee, entry)

    assert out.count("\r") == tronquee.count("\r") + 1, "la porte a changé de style de fin de ligne"
    assert not out.endswith(("\n", "\r")), "la porte a gagné une fin de ligne finale"
    assert out.splitlines()[-1] == entry


def test_le_chemin_du_PARENT_peut_porter_ces_caracteres_sans_gener_son_sous_plan():
    """The fine boundary of "because it LANDS somewhere": the index entry is relative to the
    parent's DOOR, so the parent's own path never enters it. A parent housed in
    `racine/l'offre (2)` perfectly welcomes a sub-plan `t1` — refusing there would be a false
    accusation carried by a path nobody writes in any document."""
    parent_folder = "racine/l'offre (2)"
    planning = plan_scaffold(
        folder=f"{parent_folder}/{ARCS_DIRNAME}/t1",
        existing=(f"{parent_folder}/PLAN.md", f"{parent_folder}/{ARCS_DIRNAME}/socle.md"),
        parent_door_text=PORTE_PARENTE,
    )
    assert planning.refusals == (), planning.refusals
    assert planning.parent is not None
    assert planning.parent.member == f"{ARCS_DIRNAME}/t1/{PLAN_FILENAME}"


def test_un_segment_INTERMEDIAIRE_du_membre_est_attrape_lui_aussi():
    """The counterpart: what matters is the WHOLE MEMBER, not just its last segment. A sub-plan
    housed two levels deeper writes `plan/<inter>/<feuille>/PLAN.md` into the door, so a blinding
    character in the middle makes the entry just as invisible — and fixing the CASE without
    closing the CLASS would have let exactly this shape through."""
    planning = plan_scaffold(
        folder=f"racine/{ARCS_DIRNAME}/l'inter/feuille",
        existing=("racine/PLAN.md",),
        parent_door_text=PORTE_PARENTE,
    )
    assert {r.reason for r in planning.refusals} == {"chemin_non_indexable"}, planning.refusals
    assert "'" in planning.refusals[0].detail
