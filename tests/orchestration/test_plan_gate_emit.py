"""J1 — `make plan-gate-emit`: the plan gate (D166 clause 4) becomes installable elsewhere.

**THE TWO PROOF SHOTS ARE THE ITEM'S PRODUCT**, not an extra: *"installed in the sibling project, it REFUSES
an unindexed arc AND LETS THROUGH an honest commit — both shots, never just one"*. They live here
in pytest, not only as manual commands in the emitted text — *a guard that refuses everything
passes the first shot*.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest
from _invariants import REPO_ROOT

from mnemosyne.production import plan_gate_shell as pgs
from mnemosyne.production.plan_format import FIELD_NAMES, prerequisite_problems
from mnemosyne.production.plan_registry import read_plan_tree
from mnemosyne.runtime import plan_gate_run as pgr


def _plan(tmp_path: Path, porte: str, arcs: dict[str, str] | None = None) -> Path:
    (tmp_path / "PLAN.md").write_text(porte, encoding="utf-8")
    if arcs:
        (tmp_path / "plan").mkdir(exist_ok=True)
        for nom, contenu in arcs.items():
            (tmp_path / "plan" / nom).write_text(contenu, encoding="utf-8")
    return tmp_path


# ---- THE PLAN-OF-PLANS: the sibling project's REAL structure, where the 1st-shot KILL was installed -----------
def _sous_plan_imbrique(tmp_path: Path) -> Path:
    """The sibling project's REAL shape: a root gate, an arc that is ITSELF a sub-plan with its OWN gate and its
    OWN items. `arc_tree()` alone flattens all of that -- this is exactly the KILL found by really
    installing this in the sibling project, never seen by the 12 previous witnesses because their fixture was
    flat, structurally degenerate against the real population."""
    # REAL shape measured in the sibling project's PLAN.md: `` `plan/00-arc/PLAN.md` `` -- the WHOLE path down
    # to the sub-plan's own gate, not just the folder name.
    _plan(
        tmp_path,
        "# PLAN — racine\n\n**Cap** : test\n\n## Les items\n\n- **P1** \U00002B1C un.\n\n"
        "`plan/00-arc/PLAN.md`\n",
    )
    sous = tmp_path / "plan" / "00-arc"
    sous.mkdir(parents=True)
    (sous / "PLAN.md").write_text(
        "# PLAN — sous-plan\n\n**Cap** : test\n\n## Les items\n\n- **A1** \U00002B1C un.\n\n"
        "voir `plan/interne.md`.\n",
        encoding="utf-8",
    )
    (sous / "plan").mkdir()
    (sous / "plan" / "interne.md").write_text("# interne\n", encoding="utf-8")
    return tmp_path


def test_KILL_un_sous_plan_HONNETE_ne_doit_PAS_etre_REFUSE(tmp_path: Path) -> None:
    """THE REAL DEFECT, found by installing the pointer in the sibling project and firing BOTH shots for
    real (gesture 2 of the post) -- not by an audit, by usage. On the sibling project (13 arcs, EACH one a
    sub-plan with its own gate), the 1st version composed `arc_tree()` (every `.md` under `plan/`,
    AT ANY DEPTH) directly with `index_problems`, which requires arcs relative to THIS gate. Real
    result: 155 false accusations, rc=2 on an honest state of the sibling project."""
    _sous_plan_imbrique(tmp_path)
    assert pgr.juger(tmp_path) == ()
    assert pgr.main([".", str(tmp_path)]) == 0


def test_un_ORPHELIN_dans_un_SOUS_plan_est_quand_meme_refuse(tmp_path: Path) -> None:
    """The fix must not over-correct: an arc that is genuinely orphaned AT THE SUB-PLAN LEVEL
    must keep biting -- otherwise the barrier refuses less than what D166 c4 requires."""
    _sous_plan_imbrique(tmp_path)
    (tmp_path / "plan" / "00-arc" / "plan" / "orphelin.md").write_text("# x\n", encoding="utf-8")
    refus = pgr.juger(tmp_path)
    assert any("orphelin.md" in r for r in refus), refus


# ---- THE TWO PROOF SHOTS — the item's product, not an extra -------------------------
def test_TIR_1_elle_MORD_sur_un_arc_NON_indexe(tmp_path: Path) -> None:
    """An arc exists on disk, the gate cites it nowhere — REFUSAL expected (rc=2)."""
    _plan(tmp_path, "# PLAN — Test\n\n**Cap** : test\n\n## Les items\n\n- **A1** \U00002B1C un.\n", {"orphelin.md": "# orphelin\n"})
    assert pgr.main([".", str(tmp_path)]) == 2


def test_TIR_2_elle_LAISSE_PASSER_un_commit_honnete(tmp_path: Path) -> None:
    """The same arc, cited in the gate — expected to LET THROUGH (rc=0). *Just one of the two
    shots is not enough: a guard that refuses everything passes the first shot.*"""
    _plan(
        tmp_path,
        "# PLAN — Test\n\n**Cap** : test\n\n## Les items\n\n- **A1** \U00002B1C un.\n\nvoir `plan/orphelin.md`.\n",
        {"orphelin.md": "# orphelin\n"},
    )
    assert pgr.main([".", str(tmp_path)]) == 0


# ---- FAIL-OPEN EVERYWHERE EXCEPT THE REFUSAL -------------------------------------------------------------
def test_dossier_ABSENT_ne_bloque_pas(tmp_path: Path) -> None:
    assert pgr.main([".", str(tmp_path / "n-existe-pas")]) == 0


def test_AUCUNE_porte_ne_bloque_pas(tmp_path: Path) -> None:
    assert pgr.main([".", str(tmp_path)]) == 0


def test_usage_INCORRECT_ne_bloque_pas() -> None:
    assert pgr.main([]) == 0
    assert pgr.main(["un-seul-argument"]) == 0


def test_plan_SANS_dossier_plan_ne_refuse_rien(tmp_path: Path) -> None:
    """A single-file plan: no `plan/` to check — `folder_form=False`."""
    _plan(tmp_path, "# PLAN — Test\n\n**Cap** : test\n\n## Les items\n\n- **A1** \U00002B1C un.\n")
    assert pgr.main([".", str(tmp_path)]) == 0


# ---- THE JUDGE IS index_problems, NOTHING RECOPIED ----------------------------------------------------
def test_juger_NOMME_le_bon_arc(tmp_path: Path) -> None:
    _plan(tmp_path, "# PLAN — Test\n\n**Cap** : test\n\n## Les items\n\n- **A1** \U00002B1C un.\n", {"perdu.md": "# x\n"})
    refus = pgr.juger(tmp_path)
    assert len(refus) == 1 and "plan/perdu.md" in refus[0] and "arc_hors_index" in refus[0]


def test_le_detail_du_refus_n_a_PAS_de_prefixe_DOUBLE(tmp_path: Path) -> None:
    """SURVIVING SABOTAGE found by probing: not stripping the `plan/` prefix from `arc_tree()`
    before passing it to `index_problems` (which adds it back itself) doubles the prefix
    (`plan/plan/orphelin.md`). My other witnesses checked a SUBSTRING (`"plan/perdu.md" in
    détail`), still true under the duplication — *a text detector counts citations*, including in
    my own witnesses. Strict equality, here."""
    _plan(tmp_path, "# PLAN — Test\n\n**Cap** : test\n\n## Les items\n\n- **A1** \U00002B1C un.\n", {"perdu.md": "# x\n"})
    (refus,) = pgr.juger(tmp_path)
    # format: "<plan_path> -- <where> : <kind> -- <detail>" -- the LAST segment is the detail.
    detail = refus.rsplit(" -- ", 1)[-1]
    assert detail == "plan/perdu.md", detail


def test_un_fichier_INDEXE_MAIS_absent_est_REFUSE_aussi() -> None:
    """`index_sans_fichier` — the other half of clause D166, the one the item's title does not
    name but `index_problems` already covers: do not lose it along the way."""
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        dossier = Path(d)
        (dossier / "plan").mkdir()
        (dossier / "plan" / "reel.md").write_text("# x\n", encoding="utf-8")
        # BARE shape required by `index_sans_fichier` (`_declares`): the list marker then the
        # path, NOTHING else between the two — "voir `x`" is a MENTION, not a DECLARATION.
        (dossier / "PLAN.md").write_text(
            "# PLAN — Test\n\n**Cap** : test\n\n## Les items\n\n- **A1** \U00002B1C un.\n\n- `plan/reel.md`\n- `plan/fantome.md`\n",
            encoding="utf-8",
        )
        refus = pgr.juger(dossier)
        assert any("index_sans_fichier" in r for r in refus), refus


# ---- D176: THE OBLIGATION OF FIELDS A GATE DECLARES ITSELF ------------------------------
# THE REAL DEFECT (post from 2026-08-17, triggered on a plan born from the REAL `make
# plan-nouveau`, never a fixture): `.githooks/pre-commit` (Mnemosyne) has called
# `required_field_problems` for a long time; THIS module -- what an ADOPTING project installs --
# NEVER called it. An item stripped of the two fields its own gate had declared mandatory
# passed, rc=0.
def test_D176_un_champ_requis_MANQUANT_est_REFUSE_quand_la_porte_le_declare(tmp_path: Path) -> None:
    _plan(tmp_path, "# PLAN — Test\n\n**Cap** : test\n\n> **Format** : produit\n\n## Les items\n\n- **A1** \U00002B1C un.\n")
    refus = pgr.juger(tmp_path)
    assert any("champ_requis_manquant" in r for r in refus), refus
    assert pgr.main([".", str(tmp_path)]) == 2


def test_D176_un_champ_requis_PRESENT_ne_refuse_rien(tmp_path: Path) -> None:
    _plan(
        tmp_path,
        "# PLAN — Test\n\n**Cap** : test\n\n> **Format** : produit\n\n## Les items\n\n- **A1** \U00002B1C un.\n  *Produit* : x\n",
    )
    assert pgr.juger(tmp_path) == ()
    assert pgr.main([".", str(tmp_path)]) == 0


def test_D176_SANS_declaration_rien_n_est_requis_comportement_inchange(tmp_path: Path) -> None:
    """The behavior from before this fix, intact: a gate that declares nothing refuses nothing
    on fields -- D176 is a CHOICE (D176), never imposed."""
    _plan(tmp_path, "# PLAN — Test\n\n**Cap** : test\n\n## Les items\n\n- **A1** \U00002B1C un.\n")
    assert pgr.juger(tmp_path) == ()
    assert pgr.main([".", str(tmp_path)]) == 0


def test_D176_CHAQUE_porte_de_l_arbre_declare_son_PROPRE_Format(tmp_path: Path) -> None:
    """A plan-of-plans (the sibling project's real shape): the root gate and the sub-plan declare DIFFERENT
    `**Format**` values -- the parent's declaration must never apply to the child, nor the
    reverse. Each is judged against what IT itself wrote."""
    _plan(
        tmp_path,
        "# PLAN racine\n\n> **Format** : produit\n\n## Les items\n\n- **P1** \U00002B1C un.\n"
        "  *Produit* : x\n\n`plan/00-arc/PLAN.md`\n",
    )
    sous = tmp_path / "plan" / "00-arc"
    sous.mkdir(parents=True)
    (sous / "PLAN.md").write_text(
        "# PLAN — sous-plan\n\n> **Format** : fini_quand\n\n## Les items\n\n- **A1** \U00002B1C un.\n",
        encoding="utf-8",
    )
    refus = pgr.juger(tmp_path)
    # P1 declares Produit (present) -> no refusal on P1. A1 does NOT declare Fini quand -> refused.
    assert not any("P1" in r for r in refus), refus
    assert any("A1" in r and "champ_requis_manquant" in r for r in refus), refus


# ---- THE THIRD OF THE SURFACE, ROUTED BY THE POST (2026-08-17) -----------------------------------
# `plan_format` produces 16 refusal kinds. Before this fragment, `juger()` filtered only 3 of
# them (arc_hors_index, index_sans_fichier, champ_requis_manquant) -- measured by an isolated
# auditor on a real case: `is_readable(reading) -> False` at Mnemosyne, `plan_gate_run -> rc 0` at
# the adopter, the SAME defect. Widened to the whole of READER_REFUSALS (12 kinds), the SAME rule
# `.githooks/pre-commit` already applies via `is_readable()` -- no more, no less.
def test_le_gate_MORD_desormais_sur_un_des_10_kinds_AJOUTES(tmp_path: Path) -> None:
    """`statut_inconnu` (a `**A1**` with no valid status glyph) is one of the 10 kinds never
    filtered before this fragment -- NEITHER of the two old kinds (D166 c4) would have seen it."""
    _plan(tmp_path, "# PLAN — Test\n\n**Cap** : test\n\n## Les items\n\n- **A1** un.\n")
    refus = pgr.juger(tmp_path)
    assert any("statut_inconnu" in r for r in refus), refus
    assert pgr.main([".", str(tmp_path)]) == 2


# GAP FOUND BY A 2nd ISOLATED AUDIT (D75, 2026-08-17): `is_readable()` IS A CONJUNCTION OF TWO
# HALVES -- `not unreadable_reasons(...) and not reading.problems` -- and the previous fragment
# had wired ONLY the second one. A plan with an EMPTY CAP (or an EMPTY TITLE, or NO ITEM) is
# refused by `.githooks/pre-commit` but was passing here IN SILENCE.
def test_le_gate_MORD_desormais_sur_un_CAP_VIDE(tmp_path: Path) -> None:
    """The OTHER half of `is_readable()`, never wired before this fragment: measured by the
    auditor on three mutations (empty cap, empty title, no item), replayed here on this one."""
    _plan(tmp_path, "# PLAN — Test\n\n## Les items\n\n- **A1** \U00002B1C un.\n")  # NO **Cap** line
    refus = pgr.juger(tmp_path)
    assert any("Cap" in r for r in refus), refus
    assert pgr.main([".", str(tmp_path)]) == 2


def test_le_gate_NE_MORD_TOUJOURS_PAS_sur_les_kinds_NIVEAU_2(tmp_path: Path) -> None:
    """`PREREQUISITE_REFUSALS` and `PRODUIT_REFUSALS` stay OUTSIDE this barrier -- `.githooks/
    pre-commit` (Mnemosyne) does not wire them either (`prerequisite_problems`/`produit_problems`
    never appear there): wiring them HERE would be STRICTER than what Mnemosyne imposes on
    itself. Positive proof first: an item WITHOUT `*Prerequis*` does trigger `prerequis_manquant`
    when the LEVEL 2 judge is called directly (so my fixture is a real trigger, not a case that
    never fires) -- but `juger()` never calls it."""
    _plan(tmp_path, "# PLAN — Test\n\n**Cap** : test\n\n## Les items\n\n- **A1** \U00002B1C un.\n")
    lus = read_plan_tree(tmp_path, tmp_path.name)
    assert any(
        p.kind == "prerequis_manquant" for p in prerequisite_problems(lus[0].reading)
    ), "the fixture does not even trigger the level-2 judge -- nothing proves the boundary"
    refus = pgr.juger(tmp_path)
    assert not any("prerequis" in r for r in refus), refus
    assert not any("produit_est_un_dossier" in r for r in refus), refus
    assert pgr.main([".", str(tmp_path)]) == 0


# ---- R1: THIS MODULE NEVER JUDGES MNEMOSYNE'S OWN PLAN -------------------------------
# REGRESSION FOUND BY THE ISOLATED AUDIT (D75), NOT BY ME. `porte = str(projet.plan_path)` is
# relative to whatever the CALLER typed -- and GESTE 2 of the emitted text (`plan_gate_shell.py`)
# LITERALLY suggests `"docs"` as an example name. `champs_requis_pour` unconditionally requires
# the SIX fields as soon as this path RESEMBLES Mnemosyne's own gate (`docs/PLAN.md`,
# `docs/plan/...`) -- an adopter whose plan folder is named `docs` was therefore being required to
# provide six fields it had never declared, and an explicit declaration of ONE field was silently
# overridden by the six.
def test_R1_une_porte_nommee_docs_N_EST_PAS_confondue_avec_celle_de_Mnemosyne(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dossier_docs = tmp_path / "docs"
    dossier_docs.mkdir()
    (dossier_docs / "PLAN.md").write_text(
        "# PLAN — Test\n\n**Cap** : test\n\n## Les items\n\n- **A1** \U00002B1C un.\n", encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)
    # The EXACT call GESTE 2 of the emitted text produces: a RELATIVE path named "docs".
    assert pgr.main([".", "docs"]) == 0


def test_R1_une_declaration_EXPLICITE_sous_docs_N_EST_PAS_ecrasee_par_les_SIX(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dossier_docs = tmp_path / "docs"
    dossier_docs.mkdir()
    (dossier_docs / "PLAN.md").write_text(
        "# PLAN — Test\n\n**Cap** : test\n\n> **Format** : produit\n\n## Les items\n\n- **A1** \U00002B1C un.\n  *Produit* : x\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    # Produit is provided -- none of the other five fields is required; if the six applied by
    # mistake, this commit would be refused on the five missing ones.
    assert pgr.main([".", "docs"]) == 0


def test_R1_un_sous_plan_sous_docs_N_EST_PAS_confondu_non_plus(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dossier_docs = tmp_path / "docs"
    (dossier_docs / "plan" / "sous").mkdir(parents=True)
    (dossier_docs / "PLAN.md").write_text(
        "# PLAN — Test\n\n**Cap** : test\n\n## Les items\n\n- **P1** \U00002B1C un.\n\n`plan/sous/PLAN.md`\n", encoding="utf-8"
    )
    (dossier_docs / "plan" / "sous" / "PLAN.md").write_text(
        "# PLAN — sous\n\n**Cap** : test\n\n## Les items\n\n- **A1** \U00002B1C un.\n", encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)
    assert pgr.main([".", "docs"]) == 0


# ---- R2: THE 3rd SHOT OF GESTURE 3 MUST BITE FOR THE RIGHT REASON ---------------------------------
def test_R2_le_TROISIEME_tir_de_GESTE_3_mord_sur_champ_requis_manquant_PAS_sur_arc_hors_index(
    tmp_path: Path,
) -> None:
    """FOUND BY THE ISOLATED AUDIT (D75), REPLAYED LITERALLY: without the `rm -f
    plan/orphelin.md` added ahead of the 3rd shot, `plan/orphelin.md` (created at the 1st shot)
    becomes once again an arc not cited by the new gate of the 3rd shot -- the shot returned
    `rc=2` even with D176 completely broken, for the WRONG reason (`arc_hors_index`, not
    `champ_requis_manquant`). Replays the EXACT sequence GESTE 3 describes, three shots, in the
    order written."""
    (tmp_path / "plan").mkdir()
    # SHOT 1 -- must BITE (arc not cited).
    (tmp_path / "PLAN.md").write_text(
        "# PLAN — Test\n\n**Cap** : test\n\n## Les items\n\n- **A1** \U00002B1C un.\n", encoding="utf-8"
    )
    (tmp_path / "plan" / "orphelin.md").write_text("# orphelin\n", encoding="utf-8")
    assert pgr.main([".", str(tmp_path)]) == 2
    # SHOT 2 -- must LET THROUGH (arc cited).
    (tmp_path / "PLAN.md").write_text(
        "# PLAN — Test\n\n**Cap** : test\n\n## Les items\n\n- **A1** \U00002B1C un.\n\nvoir `plan/orphelin.md`.\n", encoding="utf-8"
    )
    assert pgr.main([".", str(tmp_path)]) == 0
    # SHOT 3 -- the `rm` first, EXACTLY as the emitted text now prescribes.
    (tmp_path / "plan" / "orphelin.md").unlink()
    (tmp_path / "PLAN.md").write_text(
        "# PLAN — Test\n\n**Cap** : test\n\n> **Format** : produit\n\n## Les items\n\n- **A1** \U00002B1C un.\n", encoding="utf-8"
    )
    refus = pgr.juger(tmp_path)
    assert len(refus) == 1 and "champ_requis_manquant" in refus[0], refus
    assert pgr.main([".", str(tmp_path)]) == 2


def test_R2_le_rm_du_texte_EMIS_cible_le_MEME_fichier_que_le_printf_du_1er_tir() -> None:
    """FOUND BY THE SECOND ISOLATED AUDIT (D75, N2): the witness above replays the sequence by
    hand -- it PROVES nothing about the EMITTED TEXT itself. The audit sabotaged by renaming the
    target of the 1st shot's `printf` (`plan/orphelin.md` → `plan/autre.md`) WITHOUT touching the
    `rm -f plan/orphelin.md`: the R2 defect comes back identically (the 3rd shot bites again on
    `arc_hors_index`), and NO witness in this file turned red -- a hand-retyped copy drifts from
    the real text without anything seeing it (D163, one notch lower than usual: not the judge
    copying the text, but the WITNESS copying the judge).
    Fixed by READING both paths FROM `texte`, never retyping them here: if the 1st shot ever
    creates a different file, this witness learns it from the text itself and requires the `rm` to
    follow, instead of comparing two independent Python constants that can drift silently."""
    texte = pgs.contrat_emis("/chez/moi")
    cree = re.search(r"^#\s+printf '[^']*' > (plan/\S+)\s*$", texte, re.MULTILINE)
    supprime = re.search(r"^#\s+rm -f (\S+)\s*$", texte, re.MULTILINE)
    assert cree and supprime, "GESTE 3 structure (creation + rm) not found in the emitted text"
    assert cree.group(1) == supprime.group(1), (
        f"`rm -f` targets {supprime.group(1)!r} but the 1st shot of GESTE 3 creates "
        f"{cree.group(1)!r} -- R2 comes back as soon as these two paths diverge"
    )


# ---- GESTE 3, THE THREE SHOTS, REPLAYED FROM THE EMITTED BYTES -- NEVER A PARAPHRASE ------------
# FOUND BY THE ORCHESTRATOR (22:2x, 2026-08-17), CAUSED BY MY OWN FIX AT 20:3x (widening to
# `READER_REFUSALS`): the witnesses `test_TIR_1_...` / `test_TIR_2_...` /
# `test_R2_le_TROISIEME_tir_...` replay the SEQUENCE GESTE 3 describes, but with a PLAN.md body
# retyped by hand -- already valid (title + Cap present). GESTE 3's REAL printfs, though, write a
# bare `# PLAN\n`, with no title and no Cap: from BEFORE 20:3x, never revisited. Exactly the
# pattern `test_R2_le_rm_du_texte_EMIS_...` named at l. 331 -- closed ONLY for the `rm` path, never
# for the BODY. The three witnesses below EXTRACT GESTE 3's printfs from `contrat_emis()`, REPLAY
# them as-is, and require EXACTLY the `rc` the text promises.
def _geste_3_texte() -> str:
    """GESTE 3 alone, the real emitted text -- never retyped (D163). This is the LAST section of
    `contrat_emis()` (verified: `"MOVE 3"` appears only once in the whole text), so there is no
    end boundary to look for."""
    texte = pgs.contrat_emis(str(REPO_ROOT))
    debut = texte.find("MOVE 3")
    return texte[debut:] if debut >= 0 else ""


def _zone_dun_tir(marqueur_debut: str, marqueur_fin: str | None) -> str:
    """A single zone (one shot) of GESTE 3, bounded by the real text's own SENTENCES -- never by
 a line number, which drifts as soon as the text grows by one line (the same lesson as
 `_geste_1_seul`, bounded on `#!/usr/bin/env bash` rather than on a fragile end word).

 `find`, NEVER `index`: a marker the text stops carrying (a rename, a translation pass) makes
 `str.index` RAISE `ValueError` instead of failing -- the witness changes CATEGORY at the same
 time as colour, and a raise says only "substring not found", never WHICH marker. Returning ""
 hands the empty zone to `_printf_vers` below, whose OWN assertion names the missing target and
 prints the zone. Every caller of this helper reaches `_printf_vers` before anything else, so an
 empty zone can never turn into a silent PASS."""
    zone = _geste_3_texte()
    debut = zone.find(marqueur_debut)
    fin = zone.find(marqueur_fin, debut) if marqueur_fin else len(zone)
    if debut < 0 or fin < 0:
        return ""
    return zone[debut:fin]


def _printf_vers(zone: str, cible: str) -> str:
    """The EXACT content a `printf '...' > <cible>` in this zone would write -- extracted from
    the real text, never retyped (same discipline as `_geste_2_sans_hook_existant`, D163)."""
    trouve = re.search(r"printf '(.*?)' > " + re.escape(cible) + r"\s*$", zone, re.MULTILINE)
    assert trouve, f"no printf toward {cible!r} in this GESTE 3 zone:\n{zone}"
    return trouve.group(1).replace("\\n", "\n")


def test_GESTE_3_1er_tir_MORD_rejoue_depuis_le_texte_EMIS(tmp_path: Path) -> None:
    """The 1st shot ("must BITE") replays from the REAL bytes -- the text promises rc=2 for
    precisely the reason `arc_hors_index` (the orphan created by the 1st printf, never cited).

    FOUND BY THE ISOLATED AUDIT (D75, on 655ad02): this witness checked ONLY `rc==2` --
    exactly the defect this file already closes for the 3rd shot ("check the KIND, not just rc"),
    left OPEN here. A printf body that is once again bare (title/Cap lost) ALSO yields rc=2 (two
    different refusals, `titre`+`cap`) -- so this witness stayed GREEN facing a re-break of its
    own shot's body, blind to exactly the class this whole fragment exists to close. Same
    discipline as the 3rd shot now: name the KIND, not just rc."""
    zone = _zone_dun_tir("It must BITE (expected", "It must LET an honest commit THROUGH")
    (tmp_path / "plan").mkdir()
    (tmp_path / "PLAN.md").write_text(_printf_vers(zone, "PLAN.md"), encoding="utf-8")
    (tmp_path / "plan" / "orphelin.md").write_text(
        _printf_vers(zone, "plan/orphelin.md"), encoding="utf-8"
    )
    refus = pgr.juger(tmp_path)
    assert len(refus) == 1 and "arc_hors_index" in refus[0], (
        f"the emitted text promises A SINGLE refusal naming arc_hors_index for this shot -- got: {refus}"
    )
    assert pgr.main([".", str(tmp_path)]) == 2


def test_GESTE_3_2e_tir_LAISSE_PASSER_rejoue_depuis_le_texte_EMIS(tmp_path: Path) -> None:
    """THE REAL DEFECT (22:2x): this shot replays the EXACT body GESTE 3's 2nd printf writes
    -- before the fix, this body is `# PLAN\\n\\n## Les items...`, with no title and no Cap, and
    `plan_gate_run` refuses it (rc=2, two reasons) while the text promises rc=0. A real adopter who
    fires this shot to the letter would conclude the gate is broken and NOT INSTALL IT -- exactly
    the scenario the orchestrator named (example_research, day 1)."""
    zone1 = _zone_dun_tir("It must BITE (expected", "It must LET an honest commit THROUGH")
    zone2 = _zone_dun_tir("It must LET an honest commit THROUGH", "IF YOU DECLARE")
    (tmp_path / "plan").mkdir()
    (tmp_path / "plan" / "orphelin.md").write_text(
        _printf_vers(zone1, "plan/orphelin.md"), encoding="utf-8"
    )
    (tmp_path / "PLAN.md").write_text(_printf_vers(zone2, "PLAN.md"), encoding="utf-8")
    assert pgr.main([".", str(tmp_path)]) == 0, "the emitted text promises rc=0 for this shot"


def test_GESTE_3_3e_tir_Format_MORD_pour_UN_SEUL_refus_rejoue_depuis_le_texte_EMIS(
    tmp_path: Path,
) -> None:
    """The 3rd shot (D176, conditional) replays from the real bytes, `rm` INCLUDED (extracted,
    never assumed) -- the text promises rc=2 with A SINGLE refusal naming
    `champ_requis_manquant`. Before the fix, the bare body ALSO bites on `titre`/`cap`: THREE
    refusals, not one -- exactly the orchestrator's measurement."""
    zone1 = _zone_dun_tir("It must BITE (expected", "It must LET an honest commit THROUGH")
    zone3 = _zone_dun_tir("a third firing, it must BITE too", None)
    (tmp_path / "plan").mkdir()
    (tmp_path / "plan" / "orphelin.md").write_text(
        _printf_vers(zone1, "plan/orphelin.md"), encoding="utf-8"
    )
    (tmp_path / "PLAN.md").write_text(_printf_vers(zone3, "PLAN.md"), encoding="utf-8")
    cible_rm = re.search(r"rm -f (\S+)", zone3)
    assert cible_rm, "no `rm -f` in the 3rd shot's zone -- R2 requires one to be there"
    (tmp_path / cible_rm.group(1)).unlink()
    refus = pgr.juger(tmp_path)
    assert len(refus) == 1 and "champ_requis_manquant" in refus[0], (
        f"the emitted text promises A SINGLE refusal naming champ_requis_manquant -- got: {refus}"
    )
    assert pgr.main([".", str(tmp_path)]) == 2


# ---- THE EMITTED TEXT: a pointer, never a copy -----------------------------------------------
def test_le_contrat_EMIS_pointe_le_module_jamais_ne_le_recopie() -> None:
    texte = pgs.contrat_emis("/chez/moi")
    assert "plan_gate_run" in texte
    assert "/chez/moi/system/lib/mnemosyne/production/plan_format.py" in texte
    assert "READER_REFUSALS" in texte and "is_readable" in texte
    # Both proof shots are in the emitted text, in both directions.
    assert "rc=2" in texte or "MORDRE" in texte
    assert "rc=0" in texte or "LAISSE PASSER" in texte


def test_le_contrat_EMIS_decrit_desormais_AUSSI_D176_pas_seulement_D166() -> None:
    """The text used to promise "it judges NOTHING else" before `juger()` learned D176 -- an
    emitted contract that lies about what its own pointer does is exactly the defect this module
    exists to close (D163: the address must say what it points TO)."""
    texte = pgs.contrat_emis("/chez/moi")
    assert "champ_requis_manquant" in texte
    assert "**Format**" in texte
    assert "never imposed" in texte  # D176 is a CHOICE -- the text must say so in these words
    # R2: the 3rd shot must clean up the 1st shot's orphan before ruling on D176 alone -- proof
    # DERIVED from the real text in
    # test_R2_le_rm_du_texte_EMIS_cible_le_MEME_fichier_que_le_printf_du_1er_tir,
    # never a constant retyped here (found too weak by the second isolated audit, D75, N2).
    assert "rm -f" in texte


def test_le_contrat_EMIS_NOMME_desormais_ce_qu_il_ne_juge_PAS() -> None:
    """The third of the surface (2026-08-17): the text must say "I judge readability + D176" AND
    "I do NOT judge *Prerequisite*/*Product*, nor Mnemosyne itself" -- the admission that makes
    the contract honest, not just broader."""
    texte = pgs.contrat_emis("/chez/moi")
    # The two LEVEL-2 clauses must be named by their plan-format FIELD NAME, in the shape a plan
    # writes it. THE ASTERISKS ARE THE ASSERTION: without them, `"Prerequis"` is satisfied by the
    # English word `"Prerequisites"` -- a needle that matches a CITATION, not the token. The name
    # itself comes from `FIELD_NAMES` (production's own constant) rather than retyped here, so a
    # rename of the field carries this witness with it; the unaccented spelling stays admissible
    # because `plan_format` matches field names with their accents FOLDED.
    assert "*Prerequis*" in texte or f"*{FIELD_NAMES['prerequis']}*" in texte
    assert f"*{FIELD_NAMES['produit']}*" in texte
    assert "DOES NOT JUDGE" in texte


def test_le_contrat_EMIS_NE_DIT_PLUS_NI_PLUS_NI_MOINS_et_NOMME_ordonner_filiation() -> None:
    """GAP from the 2nd isolated audit (D75, 2026-08-17): "neither more nor less" claimed TOTAL
    parity with Mnemosyne's own hook -- false, `.githooks/pre-commit` also judges `ordonner()`,
    `filiation_problems`, `ARC_ILLISIBLE`, never wired here. The sentence must no longer appear;
    the three uncovered areas must be named."""
    texte = pgs.contrat_emis("/chez/moi")
    # The sentence may still be QUOTED inside the fix itself (keeping the discarded wording
    # verbatim) -- what must no longer exist is the ACTIVE CLAIM of total parity.
    # THE NEGATIVE GUARD DOES NOT SURVIVE TRANSLATION, AND SAYING SO IS THE HONEST ANSWER.
    # The private original forbade one exact FRENCH wording of the over-claim. This distribution is
    # English, so that wording can never appear here whatever the code does: the assertion was true
    # BY CONSTRUCTION -- green forever, including if the over-claim came back in English. It is
    # REMOVED rather than translated, because the discarded sentence was abrogated and has no
    # canonical English form in this corpus to aim at. What still bites is below: the three areas
    # the gate does NOT cover must be NAMED. A guard that cannot be carried across a translation is
    # better declared missing than kept as a green decoration.
    assert "ordonner" in texte
    assert "filiation" in texte.lower()
    assert "ARC_ILLISIBLE" in texte


def test_la_racine_est_INJECTEE_jamais_devinee() -> None:
    assert "/ailleurs" in pgs.contrat_emis("/ailleurs")
    assert "/chez/moi" not in pgs.contrat_emis("/ailleurs")


@pytest.mark.parametrize("racine", ["/a", "/b/c"])
def test_deux_racines_donnent_deux_textes_DIFFERENTS(racine: str) -> None:
    assert racine in pgs.contrat_emis(racine)


# ---- BR5: THE CONTRACT INSTALLED FOR REAL, IN AN INDEPENDENT REPO --------------------------
# Everything above calls `pgr.main()` DIRECTLY (TIR_1/TIR_2), or goes through a
# `git worktree add` OFF MNEMOSYNE'S OWN `.git` (`tests/platform/test_pre_commit_plan_gate.py`,
# fixture `worktree`). Neither proves what BR5 describes: a `git worktree` SHARES `.git/hooks`
# (or `core.hooksPath`, shared across worktrees unless an explicit `--worktree` config) with the
# repo that created it -- MNEMOSYNE'S OWN hook already bites there, even WITHOUT the emitted
# contract. A genuinely independent host (the sibling project) has NO relationship at all to Mnemosyne's
# `.git/hooks`: its only possible guard is the one IT installs itself. The three witnesses below
# create a fresh `git init` (zero inheritance from Mnemosyne), run GESTE 1 + GESTE 2 of
# `contrat_emis()` to the letter, and judge a REAL `git commit` -- never `pgr.main()` called by
# hand.
def _init_repo(chemin: Path) -> None:
    """An INDEPENDENT repo -- its own `.git`, no relationship to Mnemosyne's."""
    subprocess.run(["git", "init", "-q", "-b", "main", str(chemin)], check=True)
    subprocess.run(
        ["git", "-C", str(chemin), "config", "user.email", "test@example.invalid"], check=True
    )
    subprocess.run(["git", "-C", str(chemin), "config", "user.name", "Test"], check=True)


def _stage(repo: Path, relatif: str, contenu: str) -> None:
    cible = repo / relatif
    cible.parent.mkdir(parents=True, exist_ok=True)
    cible.write_text(contenu, encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "--", relatif], check=True)


def _commit(repo: Path, message: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), "commit", "-q", "-m", message],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )


def _geste_1_seul(texte: str) -> str:
    """The block GESTE 1 asks you to write -- never the whole `contrat_emis()`, which mixes the
    explanatory prose (unreadable as a script: the 1st line is not `#!`) with GESTE 2 and GESTE 3,
    two blocks of PROSE themselves, never meant for `.githooks/plan-gate`.

    Bounded on the PARAGRAPH (the blank line that follows), never on the script's last word -- an
    anchor on `exit $?` already broke this extraction once, when the body gained an exit-code
    filter that no longer genuinely ends with that word (BR5, the 2026-08-16 round)."""
    debut = texte.index("#!/usr/bin/env bash")
    fin = texte.index("\n\n", debut)
    return texte[debut:fin] + "\n"


def _installe_le_contrat(repo: Path, *, racine: str | None = None) -> None:
    """GESTE 1 + GESTE 2 of `contrat_emis()`, run TO THE LETTER -- never a variant.

    `racine` defaults to the real `REPO_ROOT` -- a healthy host. A caller that passes a BROKEN
    root simulates a `PYTHONPATH` that leads nowhere, without depending on an alternate python3
    installed on whatever machine runs the suite (see the FAIL-CLOSED witness further below)."""
    script = _geste_1_seul(pgs.contrat_emis(racine if racine is not None else str(REPO_ROOT)))
    porte = repo / ".githooks" / "plan-gate"
    porte.parent.mkdir(parents=True, exist_ok=True)
    porte.write_text(script, encoding="utf-8")
    porte.chmod(0o755)
    # GESTE 2, verbatim: `.githooks/plan-gate "docs" || exit 1` -- "docs" is THE folder where the
    # gate planted below by the witnesses lives.
    hook = repo / ".git" / "hooks" / "pre-commit"
    hook.write_text('#!/bin/sh\n.githooks/plan-gate "docs" || exit 1\n', encoding="utf-8")
    hook.chmod(0o755)


def _plante_un_orphelin(repo: Path, *, cite: bool) -> None:
    porte = "# PLAN — Test\n\n**Cap** : test\n\n## Les items\n\n- **A1** \U00002B1C un.\n"
    if cite:
        porte += "\nvoir `plan/orphelin.md`.\n"
    _stage(repo, "docs/PLAN.md", porte)
    _stage(repo, "docs/plan/orphelin.md", "# orphelin\n")


def test_SANS_le_contrat_installe_un_orphelin_passe_EN_SILENCE(tmp_path: Path) -> None:
    """The class BR5 describes, measured FOR REAL: an INDEPENDENT repo (never a worktree),
    without the contract installed, lets an orphan arc cross `git commit` without a word -- this
    is exactly "Mnemosyne's barrier structurally cannot see it"."""
    _init_repo(tmp_path)
    _plante_un_orphelin(tmp_path, cite=False)
    resultat = _commit(tmp_path, "orphelin sans garde")
    assert resultat.returncode == 0, f"expected: passes with no guard -- {resultat.stderr}"
    # IN SILENCE: no hook exists yet in this repo, so NOTHING should write to stderr -- the
    # witness's name promised this silence, the previous assertion alone did not check it (found
    # by the isolated audit, BR5, 2026-08-16).
    assert resultat.stderr == "", resultat.stderr


def test_AVEC_le_contrat_installe_le_MEME_orphelin_est_REFUSE(tmp_path: Path) -> None:
    """GESTE 1 + GESTE 2 run FOR REAL in this independent repo -- the SAME commit the previous
    witness let through is now refused by `git commit` itself, never by `pgr.main()` called by
    hand. This is the BITE BR5 requires, proven by real sabotage: remove `_installe_le_contrat`
    from this witness and it reverts to the previous witness, wrongly green."""
    _init_repo(tmp_path)
    _installe_le_contrat(tmp_path)
    _plante_un_orphelin(tmp_path, cite=False)
    resultat = _commit(tmp_path, "orphelin avec garde")
    assert resultat.returncode != 0, "the installed contract should have refused this commit"
    # Brand-new repo, a single commit attempt -- if it was refused, HEAD resolves NOTHING at all
    # (never an "empty log" to confuse with "the wrong commit got erased").
    tete = subprocess.run(
        ["git", "-C", str(tmp_path), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert tete.returncode != 0, "a commit still landed in the history despite the refusal"


def test_AVEC_le_contrat_installe_un_commit_HONNETE_passe_encore(tmp_path: Path) -> None:
    """The second shot GESTE 3 requires, installed for real this time: *"just one of the two is
    not enough -- a guard that refuses EVERYTHING passes the first shot"*. Same repo, same
    contract installed, the arc is CITED this time -- must pass."""
    _init_repo(tmp_path)
    _installe_le_contrat(tmp_path)
    _plante_un_orphelin(tmp_path, cite=True)
    resultat = _commit(tmp_path, "arc honnete avec garde")
    assert resultat.returncode == 0, f"expected: an honest commit passes -- {resultat.stderr}"


# ---- DEFECT 2, FOUND BY AN AUTONOMY PROBE (D75, 2026-08-17), NOT BY ONE MORE AUDIT -----
# GESTE 2 only spoke to a host that ALREADY has a pre-commit. Measured on a real brand-new
# repo (the second sibling project): `.githooks` ABSENT, `.git/hooks/` EMPTY of anything but `.sample` files,
# `core.hooksPath` NOT SET. `_installe_le_contrat` above ALREADY gives itself a
# `.git/hooks/pre-commit` -- none of the previous witnesses could therefore see this class of
# host. The witnesses below write NOTHING by hand: they EXTRACT the "YOU HAVE NOTHING" branch
# from the real text (D163, same discipline as `_geste_1_seul`) and replay it on a fresh
# `git init`, never touched otherwise.
def _geste_2_sans_hook_existant(texte: str) -> str:
    """The exact content GESTE 2's "YOU HAVE NOTHING" branch says to write into
    `.git/hooks/pre-commit` -- extracted from the text, never retyped."""
    trouve = re.search(r"printf '(.+?)' > \.git/hooks/pre-commit", texte)
    assert trouve, "the \"YOU HAVE NOTHING\" branch was not found in the emitted text"
    return trouve.group(1).replace("\\n", "\n")


def _installe_SANS_hook_existant(repo: Path, *, racine: str | None = None) -> None:
    """GESTE 1 + GESTE 2 (the "YOU HAVE NOTHING" branch), run TO THE LETTER on a host that has NO
    hook YET AT ALL -- never `_installe_le_contrat`, which simulates the OTHER host class."""
    texte = pgs.contrat_emis(racine if racine is not None else str(REPO_ROOT))
    script = _geste_1_seul(texte)
    porte = repo / ".githooks" / "plan-gate"
    porte.parent.mkdir(parents=True, exist_ok=True)
    porte.write_text(script, encoding="utf-8")
    porte.chmod(0o755)
    hook = repo / ".git" / "hooks" / "pre-commit"
    hook.write_text(_geste_2_sans_hook_existant(texte), encoding="utf-8")
    hook.chmod(0o755)


def test_D2_SUR_UN_HOTE_SANS_AUCUN_HOOK_la_branche_TU_N_AS_RIEN_MORD(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    assert not (tmp_path / ".git" / "hooks" / "pre-commit").exists()  # confirms the NEUTRAL host
    assert not (tmp_path / ".githooks").exists()
    _installe_SANS_hook_existant(tmp_path)
    _plante_un_orphelin(tmp_path, cite=False)
    resultat = _commit(tmp_path, "orphelin sur hote neuf")
    assert resultat.returncode != 0, "expected: REFUSED -- " + resultat.stdout + resultat.stderr
    # `core.hooksPath` stays ABSENT: that is precisely what makes this gesture safe (the text says
    # so).
    config = subprocess.run(
        ["git", "-C", str(tmp_path), "config", "core.hooksPath"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert config.returncode != 0 and not config.stdout.strip(), config.stdout


def test_D2_SUR_UN_HOTE_SANS_AUCUN_HOOK_un_commit_honnete_PASSE(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    _installe_SANS_hook_existant(tmp_path)
    _plante_un_orphelin(tmp_path, cite=True)
    resultat = _commit(tmp_path, "orphelin cite, hote neuf")
    assert resultat.returncode == 0, f"expected: an honest commit passes -- {resultat.stderr}"


def test_D2_le_texte_NOMME_le_piege_core_hooksPath(tmp_path: Path) -> None:
    """Not just a safe gesture -- the trap MUST be named in plain words, or a host that prefers
    `core.hooksPath` (a legitimate reason: several hooks to manage) never learns why a
    mis-pointed folder would leave it with NO guard at all, in silence."""
    texte = pgs.contrat_emis("/chez/moi")
    assert "core.hooksPath" in texte
    # "silently" ALONE no longer pins this trap: the emitted text carries the word a SECOND
    # time, in an unrelated `TODO(public-mirror)` note -- deleting the core.hooksPath
    # sentence outright would leave this witness green. The verb goes with it.
    assert "silently disables" in texte.lower()
    assert "--no-verify" in texte or "no-verify" in texte


# ---- "YOUR PROJECT IS NOT A REPO", FOUND BY AN ADOPTION PROBE ON example_research ----------
# REAL MEASUREMENT (2026-08-17), NOT A HYPOTHESIS: `projects/trading/example_research` (one of the
# three projects the operator is about to launch) has NO `.git` of its own -- its
# `git rev-parse --show-toplevel` returns the SHARED repo (`projects/`), where
# `trading/example-factory` also lives. Following GESTE 2 to the letter would install the guard
# at the SHARED root, judging EVERY commit from EVERY neighbor.
def _geste_2_borne(texte: str) -> str:
    """The `if ... fi` block of the BOUNDED branch (b) -- extracted from the real text, never
    retyped."""
    lignes = texte.splitlines()
    debut = next(i for i, ligne in enumerate(lignes) if "if git diff --cached" in ligne)
    fin = next(i for i in range(debut + 1, len(lignes)) if re.match(r"^#\s*fi\s*$", lignes[i]))
    return "\n".join(re.sub(r"^#\s?", "", ligne) for ligne in lignes[debut : fin + 1])


def test_D3_le_bloc_BORNE_extrait_du_texte_ISOLE_un_voisin_qui_n_a_RIEN_adopte(
    tmp_path: Path,
) -> None:
    """THE MOST IMPORTANT TEST: a fresh SHARED repo (never a worktree), two projects inside --
    `trading/example_research` (BROKEN plan: no title, no cap, no item) and `trading/voisin` (adopted
    NOTHING). A commit that touches ONLY the neighbor must pass EVEN IF example_research's plan is
    completely broken -- otherwise the guard overreaches exactly as measured."""
    _init_repo(tmp_path)
    (tmp_path / "trading" / "example_research").mkdir(parents=True)
    (tmp_path / "trading" / "voisin").mkdir(parents=True)

    porte = tmp_path / ".githooks" / "plan-gate"
    porte.parent.mkdir(parents=True, exist_ok=True)
    porte.write_text(_geste_1_seul(pgs.contrat_emis(str(REPO_ROOT))), encoding="utf-8")
    porte.chmod(0o755)
    bloc = (
        _geste_2_borne(pgs.contrat_emis(str(REPO_ROOT)))
        .replace("<your-project>", "trading/example_research")
        .replace("<folder-of-YOUR-gate>", "trading/example_research")
    )
    hook = tmp_path / ".git" / "hooks" / "pre-commit"
    hook.write_text(f"#!/usr/bin/env bash\nset -e\n{bloc}\n", encoding="utf-8")
    hook.chmod(0o755)

    _stage(tmp_path, "trading/example_research/PLAN.md", "ceci n'est meme pas un plan\n")
    _stage(tmp_path, "trading/voisin/fichier.txt", "contenu du voisin\n")
    subprocess.run(["git", "-C", str(tmp_path), "reset", "-q", "--", "trading/example_research"], check=True)

    resultat = _commit(tmp_path, "voisin seul, example_research jamais touche par CE commit")
    assert resultat.returncode == 0, (
        f"expected: the neighbor passes EVEN IF example_research is broken -- {resultat.stderr}"
    )

    _stage(tmp_path, "trading/example_research/PLAN.md", "ceci n'est meme pas un plan\n")
    resultat = _commit(tmp_path, "example_research touche cette fois -- doit REFUSER")
    assert resultat.returncode != 0, "expected: example_research touched, its broken plan must refuse"
    assert "titre" in resultat.stderr or "Cap" in resultat.stderr, resultat.stderr


def test_le_contrat_EMIS_NOMME_desormais_le_cas_PROJET_PAS_DEPOT() -> None:
    """Routed by the adoption probe on example_research: the measurement (`show-toplevel`), the
    consequence (overreaches onto neighbors), and the 3 outcomes (never `git init` chosen in the
    operator's place)."""
    texte = pgs.contrat_emis("/chez/moi")
    # "show-toplevel" has an UNRELATED occurrence in GESTE 1 (the executable script itself) -- the
    # sentence that introduces THE MEASUREMENT for this new case is a specific one.
    assert "IS YOUR PROJECT ITS OWN REPOSITORY" in texte
    assert "neighbor" in texte.lower()
    assert "git init" in texte


# ---- FAIL-CLOSED ON INVOCATION, MADE LITERAL: a BROKEN ENVIRONMENT MUST block ---------
# REVERSED DOCTRINE (R3/R4, final audit, 2026-08-17) -- THIS WITNESS CHECKED THE OPPOSITE
# YESTERDAY, AND IT WAS RIGHT AT THE TIME. The original defect (D75, 2026-08-16) stayed real: the
# witnesses run under `uv run pytest`, which resolves `python3` to Mnemosyne's OWN `.venv` --
# never a bare, independent python3. On a real fresh host with an older python3 (Xcode CLT's
# `/usr/bin/python3`, 3.9, really measured):
# ModuleNotFoundError: No module named 'tomllib'   (mnemosyne/config.py, imported at entry)
# rc=1
# `plan_gate_run.main()` never returns anything but 0 or 2 (verified in its own code): any OTHER
# code is therefore ALWAYS an invocation failure, never a verdict from the judge -- that part has
# not changed.
# WHAT HAS CHANGED: yesterday, an "invocation failure" passed IN SILENCE (rc=0, like
# `garde_shell.py`, the pattern this module was modeled on). The final audit found that the sibling project, the
# reference adopter, had already settled this case in its OWN code the opposite way: *"Mnemosyne
# absent REFUSES, it does not skip -- `try/except ImportError: return 0` IS THE BUG."* And that
# `pre-commit` (~40 commits/day, nobody re-reads stderr) does not have the same reader an
# interactive Claude Code session does (where `garde_shell.py` gets installed). From now on: an
# invocation failure REFUSES (rc=2), with a message that NAMES the break and the standard escape
# hatch (`git commit --no-verify`) -- the guarantee is no longer lost in silence, it is replaced
# by an explicit choice from the committer, every time.
def test_FAIL_CLOSED_un_PYTHONPATH_casse_BLOQUE_le_commit(tmp_path: Path) -> None:
    """Simulates the SAME failure class the original audit measured (the python invocation fails
    BEFORE the judge can return a verdict) WITHOUT depending on an alternate python3 installed on
    this machine: a bogus root makes `PYTHONPATH` point nowhere, `import mnemosyne` fails, rc
    outside {0,2}. Now requires the REFUSAL, with the message naming the break and
    `--no-verify`."""
    _init_repo(tmp_path)
    _installe_le_contrat(tmp_path, racine="/n-existe-pas-vraiment")
    _plante_un_orphelin(tmp_path, cite=False)
    resultat = _commit(tmp_path, "orphelin avec garde CASSEE")
    assert resultat.returncode != 0, (
        f"a broken environment must now REFUSE (R3/R4) -- {resultat.stderr}"
    )
    assert "broken invocation" in resultat.stderr
    assert "no-verify" in resultat.stderr


def test_SANS_aucune_porte_installee_ca_ne_prouve_RIEN_sur_GESTE_1(tmp_path: Path) -> None:
    """WHAT THIS WITNESS DOES NOT PROVE, AND THAT IS ITS WHOLE POINT: without
    `_installe_le_contrat`, `.githooks/plan-gate` does not exist -- git runs NO hook at all, GESTE
    1 is NEVER reached. Nothing here tests the R3/R4 doctrine -- that is already covered, more
    strongly, by `test_SANS_le_contrat_installe_un_orphelin_passe_EN_SILENCE` (which ADDITIONALLY
    requires `stderr == ""`). Kept as scaffolding for the class below, never as proof of the
    doctrine itself."""
    _init_repo(tmp_path)
    _stage(tmp_path, "docs/ailleurs.md", "# rien a voir\n")
    resultat = _commit(tmp_path, "aucune porte, aucune garde installee")
    assert resultat.returncode == 0, f"with no gate installed, nothing should block -- {resultat.stderr}"


def test_FAIL_OPEN_reste_INCHANGE_quand_il_n_y_a_AUCUN_plan_MAIS_la_racine_est_SAINE(
    tmp_path: Path,
) -> None:
    """FOUND BY THE ISOLATED AUDIT (D75, on 11a131a), DEFECT D1: the previous witness (before
    the fix) was NOT testing what its docstring claimed -- vacuous, sabotage-proof confirmed it
    (GESTE 1 replaced with an UNCONDITIONAL refusal, this witness stayed GREEN). The "unchanged"
    HALF of the R3/R4 doctrine -- gate installed, HEALTHY root, no `PLAN.md` at all -- had no
    witness that genuinely reached it. This one installs the REAL GESTE 1 (real root) and writes
    NO `docs/PLAN.md` at all -- the invocation succeeds, `plan_gate_run.main()` finds nothing to
    judge, rc=0.

    FOUND BY THE 2nd ISOLATED AUDIT (D75, on ffc6bf9), the same class as BR5
    (`the-harness-is-a-variable-of-the-measurement.md`): a "HEALTHY root" alone is NOT enough --
    this witness ALSO depends, silently, on the `python3` running THIS suite (`uv run`, capable of
    importing `mnemosyne`). On a bare `python3` with no `tomllib` (Xcode CLT 3.9, already measured
    as a real case by BR5), this SAME witness would turn red -- not because the doctrine is
    wrong, but because the invocation would fail too, exactly as the neighboring FAIL_CLOSED
    witness anticipates. Named here rather than left silent: this witness checks "a healthy root
    AND a harness interpreter capable of importing mnemosyne", never the root alone."""
    _init_repo(tmp_path)
    _installe_le_contrat(tmp_path)
    _stage(tmp_path, "docs/ailleurs.md", "# rien a voir\n")
    resultat = _commit(tmp_path, "porte installee, aucun plan a juger")
    assert resultat.returncode == 0, (
        f"healthy root + no plan = nothing to judge, must pass -- {resultat.stderr}"
    )


def test_FAIL_CLOSED_gagne_quand_racine_CASSEE_ET_aucun_plan_a_la_fois(tmp_path: Path) -> None:
    """THE EDGE CASE THE COMMIT DID NOT DISCUSS (isolated audit, point 3): when the
    invocation failure AND the absence of a plan are BOTH true AT THE SAME TIME, the INVOCATION
    FAILURE wins -- the judge cannot know there is nothing to judge if it does not even run. The
    STALE docstring of the witness above claimed the opposite ("stays FAIL-OPEN, even with a
    broken root") -- fixed together with this gap. Replays case (e) of the audit: broken root, NO
    PLAN.md at all."""
    _init_repo(tmp_path)
    _installe_le_contrat(tmp_path, racine="/n-existe-pas-vraiment")
    _stage(tmp_path, "docs/ailleurs.md", "# rien a voir\n")
    resultat = _commit(tmp_path, "porte installee sur racine cassee, aucun plan")
    assert resultat.returncode != 0, (
        f"the broken invocation must refuse EVEN with no plan to judge -- {resultat.stderr}"
    )
    assert "broken invocation" in resultat.stderr
