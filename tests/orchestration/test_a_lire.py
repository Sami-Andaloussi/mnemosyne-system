"""C4 — the `*To read*` field: its load in bytes, without opening the item, and its mandate template.

 **THE FORM IS MEASURED, NOT INVENTED** — over the 53 real `*To read*` fields: 117 tokens between
backticks, 65 with `/`, **58 resolve** against three measured roots. Bare filenames (without `/`)
are **never** resolved: the repo carries several files with the same name in different places, and
guessing would attribute the wrong file's load, in silence.

 **Real population, frozen**: 52 items carry the field, 1 (`NONE`) does not; 14/52 have a
COMPLETE load (every one of their references resolved), the others are a named FLOOR.
"""

from __future__ import annotations

from pathlib import Path

from mnemosyne.production import a_lire as al
from mnemosyne.production.plan_format import PlanItem
from mnemosyne.production.plan_registry import scan_plans

from _invariants import REPO_ROOT


def _item(a_lire: str | None, **kw) -> PlanItem:
    fields = (("a_lire", a_lire),) if a_lire is not None else ()
    return PlanItem(
        ident=kw.get("ident", "B1"),
        status=kw.get("status", "a_faire"),
        title=kw.get("title", "titre"),
        section="",
        line=1,
        detail=kw.get("detail", ()),
        fields=fields,
    )


# ---- THE LOAD: NONE beats an invented zero -------------------------------------------
def test_un_item_SANS_champ_rend_AUCUN_jamais_zero() -> None:
    assert al.charge_en_octets(_item(None), REPO_ROOT) is None


def test_un_chemin_EXPLICITE_resout_et_compte_ses_octets(tmp_path: Path) -> None:
    (tmp_path / "sous").mkdir()
    (tmp_path / "sous" / "x.py").write_text("0123456789", encoding="utf-8")
    c = al.charge_en_octets(_item("`sous/x.py`"), tmp_path)
    assert c is not None and c.octets == 10 and c.complete


def test_un_BARE_FILENAME_sans_slash_n_est_JAMAIS_resolu(tmp_path: Path) -> None:
    """ The core of the design: `x.py` may exist in several places in the repo (measured:
 297 distinct `__init__.py`). Guessing would attribute a FALSE load, in silence —
 *an ambiguous path is not resolved, it is named unresolved.*"""
    (tmp_path / "x.py").write_text("0123456789", encoding="utf-8")
    c = al.charge_en_octets(_item("`x.py`"), tmp_path)
    assert c is not None and c.octets == 0 and not c.complete
    assert c.references_non_resolues == ("x.py",)


def test_un_chemin_QUI_N_EXISTE_PAS_est_NOMME_non_resolu(tmp_path: Path) -> None:
    c = al.charge_en_octets(_item("`dossier/fantome.py`"), tmp_path)
    assert c is not None and not c.complete and c.references_non_resolues == ("dossier/fantome.py",)


# ---- `base_projet`: a project cites ITS OWN files relative to ITSELF (2026-08-18) -----------
# The defect the SECOND adopter paid for: `_RACINES` named one sibling project's own folder in
# hard, written when it was the only one. The second adopter (`make lot-emit`) returned "9 unresolved
# references, total load 0 bytes" and had to prefix every citation with
# its own folder under `projects/personal/` -- its own files, addressed relative to Mnemosyne, so broken
# the day its repo is cloned alone.


def _projet(tmp_path: Path) -> Path:
    """A minimal project: one file at ITS root, another in a subfolder."""
    base = tmp_path / "projects" / "perso" / "monprojet"
    (base / "arcs").mkdir(parents=True)
    (base / "faits.md").write_text("0123456789", encoding="utf-8")
    (base / "arcs" / "01.md").write_text("01234", encoding="utf-8")
    return base


def test_SANS_base_projet_un_projet_ne_resout_RIEN_de_relatif_a_lui_meme(tmp_path: Path) -> None:
    """ THE WITNESS THAT BITES: this is EXACTLY what that second adopter went through. Without the base, the
 two natural forms of a project talking about itself are unresolved, and its load is ZERO."""
    _projet(tmp_path)
    c = al.charge_en_octets(_item("`faits.md` · `arcs/01.md`"), tmp_path)
    assert c is not None
    assert c.octets == 0, c.octets
    assert not c.complete
    assert c.references_non_resolues == ("faits.md", "arcs/01.md")


def test_AVEC_base_projet_les_DEUX_formes_resolvent_et_comptent(tmp_path: Path) -> None:
    """The fix: a path WITH `/` and a bare name, both relative to the project's own root."""
    _projet(tmp_path)
    c = al.charge_en_octets(
        _item("`faits.md` · `arcs/01.md`"), tmp_path, "projects/perso/monprojet"
    )
    assert c is not None and c.complete, c
    assert c.octets == 15, c.octets


def test_le_nom_NU_ne_resout_QUE_sous_base_projet_jamais_ailleurs(tmp_path: Path) -> None:
    """ THE BOUNDARY THAT STOPS THE FIX FROM WIDENING TOO FAR: the rule "a bare name is never
 resolved" exists against AMBIGUITY (`ligne.py` lives in 10 places). `base_projet` only lifts it
 WHERE ambiguity is impossible -- a single declared root. A namesake sitting ELSEWHERE in the
 repo must never be caught."""
    _projet(tmp_path)
    (tmp_path / "faits.md").write_text("x" * 999, encoding="utf-8")  # namesake at the repo root
    c = al.charge_en_octets(_item("`faits.md`"), tmp_path, "projects/perso/monprojet")
    assert c is not None and c.complete
    assert c.octets == 10, f"resolved the repo's namesake instead of the project's own file: {c.octets}"


def test_base_projet_PREND_LE_PAS_sur_un_homonyme_du_depot_et_c_est_VOULU(tmp_path: Path) -> None:
    """ THE WITNESS MY FIRST DRAFT DID NOT HAVE, AND AN ISOLATED AUDITOR DEMANDED: the base is
 tried FIRST, so the SAME token can resolve to a DIFFERENT file -- `complete` stays True, nothing
 signals the change. This is INTENTIONAL (a project's own files win, for ITS plan), but it is a
 change of MEANING, not only of reach.
 My first non-regression witness picked a file that existed ONLY at the root: it froze "it
 still resolves", never "it resolves to the SAME file". *A witness that cannot see the class does
 not cover it, even when it is green.*"""
    base = tmp_path / "projects" / "perso" / "monprojet"
    (base / "sous").mkdir(parents=True)
    (base / "sous" / "x.py").write_text("9" * 999, encoding="utf-8")
    (tmp_path / "sous").mkdir()
    (tmp_path / "sous" / "x.py").write_text("0123456789", encoding="utf-8")
    sans = al.charge_en_octets(_item("`sous/x.py`"), tmp_path)
    avec = al.charge_en_octets(_item("`sous/x.py`"), tmp_path, "projects/perso/monprojet")
    assert sans is not None and avec is not None
    assert sans.octets == 10, sans.octets
    assert avec.octets == 999, avec.octets
    assert sans.complete and avec.complete  # neither one SIGNALS anything


def test_base_projet_ne_RETIRE_jamais_une_resolution_qui_marchait(tmp_path: Path) -> None:
    """ Non-regression: this argument can only ADD a base. A path already resolvable from the
 repo root stays so, whether or not base_projet is supplied."""
    _projet(tmp_path)
    (tmp_path / "sous").mkdir()
    (tmp_path / "sous" / "x.py").write_text("0123456789", encoding="utf-8")
    sans = al.charge_en_octets(_item("`sous/x.py`"), tmp_path)
    avec = al.charge_en_octets(_item("`sous/x.py`"), tmp_path, "projects/perso/monprojet")
    assert sans is not None and avec is not None
    assert sans.octets == avec.octets == 10
    assert sans.complete and avec.complete


# ---- CONTAINMENT: found by an isolated audit, closed -----------------------------------------
def test_un_chemin_ABSOLU_n_est_JAMAIS_resolu(tmp_path: Path) -> None:
    """ FOUND BY AN ISOLATED AUDIT (D75): `pathlib` DROPS the left side of a `/` when the
 right-hand operand is absolute (`racine / "/etc/hosts"` equals `/etc/hosts`) -- not a
 `pathlib` bug, a behaviour `_resoudre` was not guarding against. Reproduced by the audit:
 returned `/etc/hosts` before the fix."""
    assert al._resoudre("/etc/hosts", tmp_path) is None


def test_une_TRAVERSEE_ne_s_echappe_PAS_du_depot(tmp_path: Path) -> None:
    """ SAME AUDIT: `is_file()` never normalises `..`, so a token `../outside-repo.txt` escaped
 the three roots to any file readable by the process. *"Without opening it" stayed true (only
 `stat().st_size` is read) -- but the load could count bytes from a file that nothing in the
 three roots justifies.*

 **MY FIRST DRAFT OF THIS WITNESS TESTED NOTHING**: the token joined to `racine` did not,
 once `..` was resolved, point at the file I had created outside the repo -- it passed (falsely)
 under BOTH versions of the code, fixed and sabotaged, because `is_file()` was False in both
 cases for a reason unrelated to containment. *A probe (or here, a shipped witness) that cannot
 tell healthy code from sabotaged code tests nothing* -- now verified by confirming the file
 really exists at the expected resolved path."""
    depot = tmp_path / "depot"
    depot.mkdir()
    (tmp_path / "hors-depot.txt").write_text("secret", encoding="utf-8")
    cible_hors_depot = (tmp_path / "hors-depot.txt").resolve()
    assert cible_hors_depot.is_file()  # the probe: the targeted file really exists
    assert al._resoudre("../hors-depot.txt", depot) is None


def test_une_traversee_qui_RESTE_dans_le_depot_est_LEGITIME(tmp_path: Path) -> None:
    """ Containment is about the REPO, not each sub-root: a `..` that leaves ITS sub-root without
 leaving the repo must stay resolved -- otherwise we refuse more than the audit asked for, and a
 guard that refuses wrongly gets disabled."""
    (tmp_path / "reel.py").write_text("12345", encoding="utf-8")
    (tmp_path / "system" / "lib" / "mnemosyne").mkdir(parents=True)
    c = al._resoudre("system/lib/mnemosyne/../../../reel.py", tmp_path)
    assert c is not None and c.stat().st_size == 5


def test_les_trois_racines_sont_toutes_essayees(tmp_path: Path) -> None:
    (tmp_path / "system" / "lib" / "mnemosyne").mkdir(parents=True)
    (tmp_path / "system" / "lib" / "mnemosyne" / "y.py").write_text("abc", encoding="utf-8")
    c = al.charge_en_octets(_item("`y.py`"), tmp_path)
    # without '/' -> never resolved, even under a real root: consistent with the design.
    assert c is not None and not c.complete
    (tmp_path / "sous" / "dossier").mkdir(parents=True)
    (tmp_path / "sous" / "dossier" / "z.py").write_text("abcd", encoding="utf-8")
    c2 = al.charge_en_octets(_item("`sous/dossier/z.py`"), tmp_path)
    assert c2 is not None and c2.complete and c2.octets == 4


def test_le_NUMERO_DE_LIGNE_est_retire_avant_resolution(tmp_path: Path) -> None:
    (tmp_path / "d").mkdir()
    (tmp_path / "d" / "x.py").write_text("12345", encoding="utf-8")
    c = al.charge_en_octets(_item("`d/x.py:42`"), tmp_path)
    assert c is not None and c.complete and c.octets == 5


def test_plusieurs_references_s_ADDITIONNENT(tmp_path: Path) -> None:
    (tmp_path / "sous").mkdir()
    (tmp_path / "sous" / "a.py").write_text("12345", encoding="utf-8")
    (tmp_path / "sous2").mkdir()
    (tmp_path / "sous2" / "b.py").write_text("1234567890", encoding="utf-8")
    c = al.charge_en_octets(_item("`sous/a.py` · `sous2/b.py`"), tmp_path)
    assert c is not None and c.complete and c.octets == 15


def test_une_reference_HORS_BACKTICKS_n_est_pas_lue() -> None:
    """ *A text detector counts citations* — a path cited in prose, without backticks, is not a
 readable reference: the real population always writes them between backticks."""
    assert al.references(_item("the file x.py without backticks")) == ()


# ---- THE TEMPLATE: composed, never drafted --------------------------------------------------
def test_le_gabarit_NOMME_AUCUN_pour_un_item_sans_lecture() -> None:
    rendu = al.rendre_gabarit((_item(None),), Path("."))
    assert "NONE" in rendu


def test_le_gabarit_distingue_RESOLU_et_NON_resolu(tmp_path: Path) -> None:
    (tmp_path / "reel.py").write_text("x", encoding="utf-8")
    rendu = al.rendre_gabarit((_item("`sous/reel.py` · `fantome.py`"),), tmp_path)
    assert "fantome.py` (reference NOT resolved" in rendu


def test_le_gabarit_porte_les_TROIS_clauses_anti_biais() -> None:
    """ The mandate-bias lessons: beliefs labelled, exit in two branches, what is ALREADY
 covered — all three, in EVERY emitted template."""
    rendu = al.rendre_gabarit((_item(None),), Path("."))
    assert "TWO branches" in rendu
    assert "ALREADY covered" in rendu
    assert "If it is wrong, say so and measure it" in rendu


def test_deja_couvert_est_NOMME_quand_fourni() -> None:
    rendu = al.rendre_gabarit((_item(None),), Path("."), deja_couvert=("the MECHANISM angle",))
    assert "the MECHANISM angle" in rendu
    assert "you are the first" not in rendu


# ---- NO PRODUCER REASONING: same promise as E4 (lot_emit) ------------------------
def test_le_gabarit_NE_COMPOSE_QU_avec_des_champs_DEJA_publies() -> None:
    """ Same predicate as `test_lot_emit.py` — *two witnesses of the same promise diverging means
 the second one is lying*. `detail` and any `fields` entry other than `a_lire` must NEVER
 appear in an emitted template."""
    item = _item(
        "`x.py`",
        detail=("\U000026A0\U0000FE0F PRODUCER'S PRIVATE REASONING — must NEVER leak",),
    )
    rendu = al.rendre_gabarit((item,), Path("."))
    assert "REASONING" not in rendu, rendu


# ---- THE REAL THING: frozen, through the production accessor ----------------------------------------
def test_le_REEL_du_plan_est_gele() -> None:
    """ `scan_plans`, the FOLDED accessor — not `read_plan` on the door alone, which returns an
 EMPTY population (the trap paid for three times tonight on this same plan)."""
    projet = next(p for p in scan_plans(REPO_ROOT).projects if p.plan_path.parent.name == "docs")
    avec_champ = sum(
        1 for i in projet.reading.items if al.charge_en_octets(i, REPO_ROOT) is not None
    )
    sans_champ = len(projet.reading.items) - avec_champ
    completes = sum(
        1
        for i in projet.reading.items
        if (c := al.charge_en_octets(i, REPO_ROOT)) is not None and c.complete
    )
    # RE-FROZEN on 2026-08-16 at 08:5x (chat 1, orchestrator's "12 reds" mandate): the previous
    # measurement (60, 1) dated from when H3/H4/H5/G2 closed; one more item has since filled its
    # `*To read*`. SAME measurement on both sides (avec_champ, sans_champ, completes) -- checked
    # before re-freezing, not assumed: `sans_champ` is still carried by the SAME single item (`H2`,
    # unchanged) and `completes` did NOT move (still 20) -- a sign the accessor has not drifted,
    # only the population grew by one incomplete item.
    # RE-FROZEN on 2026-08-18 (orchestrator): (61, 1, 20) -> (66, 1, 21). The plan's population
    # went from 62 to 67 items during the night the "project engineering" ticket closed, all with
    # their `*To read*` filled in. SAME check as last time, done BEFORE re-freezing and not assumed:
    # `sans_champ` is still carried by the SAME single item, `H2` -- a sign the accessor has not
    # drifted, only the population grew.
    # AND THE FREEZE BECOMES A SET, NOT ONLY A COUNT: a count staying at 1 would let ANOTHER item
    # lose its field while `H2` regains one -- two opposite changes cancel out and the witness stays
    # green. The name itself does not cancel out.
    # RE-FROZEN on 2026-08-18 (2nd time that day): (66, 1, 21) -> (67, 1, 22). The population grew
    # by one more item, AND `completes` went UP by two -- for a reason worth writing down: two items
    # (`H5`, `B7`) carried PROSE in their `*To read*` field, and every word between backticks is
    # read there as a REFERENCE (`B1`, `0/6`, `B7`, `0/7` -- four "files" not found). Both items were
    # therefore FLOORS. The prose was moved out of the field.
    # It is `charge_en_octets` that caught it, not a re-read: the count moved, so it had to be
    # investigated. *A structured field is not a place to leave a comment.*
    idents_sans_champ = frozenset(
        i.ident for i in projet.reading.items if al.charge_en_octets(i, REPO_ROOT) is None
    )
    assert idents_sans_champ == frozenset({"H2"}), sorted(idents_sans_champ)
    assert (avec_champ, sans_champ) == (67, 1), (avec_champ, sans_champ)
    assert completes == 22, completes


def test_le_bare_filename_C4_lui_meme_est_NON_resolu_sans_deviner() -> None:
    """C4 cites its two internal lesson notes WITHOUT `/` (note names, not paths) — they must
    stay NOT resolved, neither silently ignored nor falsely counted."""
    projet = next(p for p in scan_plans(REPO_ROOT).projects if p.plan_path.parent.name == "docs")
    c4 = next(i for i in projet.reading.items if i.ident == "C4")
    charge = al.charge_en_octets(c4, REPO_ROOT)
    assert charge is not None and not charge.complete
    assert "the-mandate-template-that-paid-all-night" in charge.references_non_resolues


# ---- THE THREE REASONS: an "unresolved" counter no longer aggregates three opposite ones -----------
# Found by a second chat (2026-08-16): "validly outside the repo" (memory note, function, item,
# command -- never a file), "short path" (the file EXISTS, blocked by the caution above,
# DELIBERATE), and "not found" (the only real defect) were getting the SAME word. Fixing the
# first two would break `_resoudre`; the word "unresolved" is therefore reserved for the third.
# `charge.references_non_resolues` KEEPS all three (see the C4 test just above — nothing changes
# there): only `rendre_gabarit` must now distinguish them, both on DISPLAY and in the TOTAL.


def test_un_fichier_REEL_sans_slash_est_chemin_court_jamais_non_resolu(tmp_path: Path) -> None:
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "reel.md").write_text("0123456789", encoding="utf-8")
    rendu = al.rendre_gabarit((_item("`reel.md`"),), tmp_path)
    assert "short path, not counted out of caution" in rendu
    assert "reel.md` (reference NOT resolved" not in rendu


def test_un_bare_sans_extension_est_hors_perimetre_jamais_non_resolu(tmp_path: Path) -> None:
    rendu = al.rendre_gabarit((_item("`une-fiche-memoire-plausible`"),), tmp_path)
    assert "outside the repo's scope" in rendu
    assert "une-fiche-memoire-plausible` (reference NOT resolved" not in rendu


def test_un_bare_AVEC_extension_introuvable_reste_NON_resolu(tmp_path: Path) -> None:
    rendu = al.rendre_gabarit((_item("`fantome-inconnu.md`"),), tmp_path)
    assert "fantome-inconnu.md` (reference NOT resolved — not found)" in rendu


def test_le_total_ne_compte_QUE_l_introuvable_et_le_chemin_ambigu(tmp_path: Path) -> None:
    """The FLOOR total must name what it counts -- never a single number for three things."""
    (tmp_path / "reel.md").write_text("x", encoding="utf-8")
    item = _item("`reel.md` · `une-fiche-memoire` · `dossier/fantome.py`")
    rendu = al.rendre_gabarit((item,), tmp_path)
    assert "1 unresolved reference(s)" in rendu  # dossier/fantome.py -- has a '/', unchanged
    assert "1 short path(s) not counted out of caution" in rendu  # reel.md
    # "une-fiche-memoire" is outside the repo's scope: must appear in NEITHER of the two counts.
    assert "2 unresolved" not in rendu and "2 short path" not in rendu


def test_le_gabarit_reel_isole_le_SEUL_bare_vraiment_introuvable_du_plan() -> None:
    """ On the real plan (2026-08-16): 59 unresolved bare tokens, of which 23 short-path-resolvable
 and 35 outside the repo's scope — only ONE is genuinely not found. A change that makes a second
 one appear or disappear must be seen here, not silently absorbed into an aggregated total."""
    projet = next(p for p in scan_plans(REPO_ROOT).projects if p.plan_path.parent.name == "docs")
    rendu = al.rendre_gabarit(projet.reading.items, REPO_ROOT)
    introuvables_bare = [
        line
        for line in rendu.splitlines()
        if "reference NOT resolved — not found" in line
    ]
    # RE-FROZEN on 2026-08-18 (orchestrator): ONE -> TWO, and the CONDITION IS NOT IDENTICAL --
    # which is why this is not a silent re-baseline. The READER was FIXED: a real `*To read*`,
    # hidden behind an un-indented fence on a real item, is finally read. So this is NOT a
    # reference that just appeared, it is a reference that was there and went unseen.
    # Diagnosis made by ANOTHER chat that named it without fixing it ("a_lire.py/test_a_lire.py
    # are not my lot") — in the project plan's own notes. Fixed here because this chat is parked
    # and nobody else would have done it.
    # `plan_registry.read_plan_tree` EXISTS (`production/plan_registry.py:286`): it is classed
    # "not found" and not "outside the repo's scope" because its prefix -- `module.function` --
    # makes it look like a path, whereas a bare `read_plan` is correctly classed outside the repo's
    # scope (next assertion). *A CLASSIFICATION defect named, not fixed here: fixing it would
    # change `a_lire`'s behaviour, not this witness's freeze.*
    # Compares a SET, not a list: the ORDER follows the plan's item order, which is incidental --
    # a freeze on order would turn red at the first moved item, for nothing.
    assert frozenset(introuvables_bare) == frozenset(
        {
            "  - `chantier-0-la-forme.md` (reference NOT resolved — not found)",
            "  - `plan_registry.read_plan_tree` (reference NOT resolved — not found)",
        }
    ), sorted(introuvables_bare)
    assert "read_plan` (outside the repo's scope" in rendu
    assert "Makefile` (short path, not counted out of caution" in rendu
