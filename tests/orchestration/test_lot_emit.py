"""E4 -- the arc mandate is EMITTED, never hand-drafted.

 **THE BOUNDARY WITH `C4`**: this module produces the EMITTER, never the TEMPLATE -- `C4`
(`production/a_lire.py`) produces the mandate's SHAPE. `C4` is built: `rendre()` CONSUMES it.

 **MEASURED BEFORE WRITING**, on the real plan (`scan_plans`, the FOLDED reading -- `read_plan`
on the door alone renders an EMPTY population, the same trap this repo's own `G3` paid for that
same night): **11 arcs**, **0 overlapping pair**. This is the measurement the `test_le_REEL…`
witness freezes.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

from mnemosyne.production import lot_emit as le
from mnemosyne.production.parc import Lot
from mnemosyne.production.plan_format import PlanItem, read_plan
from mnemosyne.production.plan_registry import scan_plans

from _invariants import REPO_ROOT


def _reading(texte: str):
    return read_plan(texte)


# ---- THE PARTITION: derived, never hand-written -------------------------------------------------
def test_le_mandat_ne_prend_QUE_les_items_de_SON_arc() -> None:
    texte = "# PLAN — x\n\n## Les items\n\n- **B1** \U00002B1C **un.**\n- **C1** \U00002B1C **deux.**\n"
    m = le.mandat_pour_arc(_reading(texte), porte="x.md", arc="B")
    assert [i.ident for i in m.items] == ["B1"]


def test_arcs_du_plan_est_le_MEME_accesseur_que_G3() -> None:
    """*One home*: `lettre_d_arc` comes from `perimetre.py`, not a regex recopied here."""
    texte = "# PLAN — x\n\n## Les items\n\n- **B1** \U00002B1C **un.**\n- **AB2** \U00002B1C **deux.**\n"
    assert le.arcs_du_plan(_reading(texte)) == frozenset({"B", "AB"})


def test_un_item_a_l_identite_ILLISIBLE_n_appartient_a_AUCUN_arc() -> None:
    texte = "# PLAN — x\n\n## Les items\n\n- **99** \U00002B1C **sans lettre.**\n"
    assert le.arcs_du_plan(_reading(texte)) == frozenset()


def test_une_braise_n_est_PAS_un_arc_assignable() -> None:
    """ **ADDED (`E4` audit, reserve `d`): a UNIT, DIRECT witness, not just
 `test_le_REEL_...` in the background** — that one only proves the `BR` exclusion indirectly,
 via `frozenset("ABCDEFGHIJK")` over 11 arcs; no witness isolated the `!= _PREFIXE_BRAISE`
 clause itself on a minimal, controlled population."""
    from mnemosyne.production.perimetre import arcs_existants

    texte = (
        "# PLAN — x\n\n## Les items\n\n"
        "- **B1** \U00002B1C **un.**\n- **BR1** \U00002B1C **une braise.**\n- **C1** \U00002B1C **deux.**\n"
    )
    reading = _reading(texte)
    assert arcs_existants(reading) == frozenset({"B", "BR", "C"})
    assert le.arcs_du_plan(reading) == frozenset({"B", "C"})


# ---- THE OVERLAP: the real test, not just its absence --------------------------------------------
def test_deux_arcs_DISJOINTS_ne_se_recouvrent_sur_AUCUN_fichier() -> None:
    """ **RENAMED (spotted by the orchestrator, not by me): this witness tests FILES, its old
 name said `AUCUN_item`** -- a name that lies about what it measures fabricates the wrong cut
 the day someone reads the list without opening the body.

 **STRENGTHENED (`E4` audit, reserve `c`): two real and DIFFERENT `*Produit*` values, never
 two empty fields.** The old shape (B1/C1 with no `*Produit*`) rendered `∅ ∩ ∅ = ∅` under ANY
 implementation of `recouvrement` -- a witness that cannot tell a real disjoint apart from an
 absence of measurement tests nothing. Here both items cite a real, distinct file each: the
 witness only bites if `recouvrement` can actually say "two non-empty but disjoint sets."""
    texte = (
        "# PLAN — x\n\n## Les items\n\n"
        "- **B1** \U00002B1C **un.**\n  *Produit* : `system/lib/mnemosyne/production/carte.py`\n"
        "- **C1** \U00002B1C **deux.**\n  *Produit* : `system/lib/mnemosyne/production/perimetre.py`\n"
    )
    reading = _reading(texte)
    b = le.mandat_pour_arc(reading, porte="x.md", arc="B")
    c = le.mandat_pour_arc(reading, porte="x.md", arc="C")
    assert b.fichiers and c.fichiers, "the reinforcement only means something if BOTH sides are non-empty"
    assert le.recouvrement(b, c) == frozenset()


def test_recouvrement_MORD_quand_deux_mandats_revendiquent_le_MEME_fichier() -> None:
    """ THE GATE'S PASSING CASE, asserted -- *I never assert the passing case* was the mistake
 paid for tonight: a refusal function that never refuses anything LOOKS correct until shown a
 real overlap.

 **RENAMED ALONGSIDE ITS NEIGHBOR (same class as the residue the orchestrator flagged):
 `MEME_item` already lied -- the two idents are DISTINCT, only the FILE is shared.** One flagged
 occurrence does not mean it was the only one; fixed together so they stay consistent with each
 other.

 **STRENGTHENED (`E4`'s gap closed): TWO DISTINCT items, never a shared object.** The old
 shape shared the `PlanItem` object between the two mandates -- a shortcut that no longer proves
 anything now that `recouvrement` compares FILES, not Python object identity. The real case that
 matters, measured on this repo's own plan, is two DIFFERENT idents whose `*Produit*` cites the
 same path -- exactly `A2`/`C3` on `OBLIGATION.md` before the `ouverts` scope split them apart
 by status."""
    item_a = PlanItem(
        ident="B1",
        status="a_faire",
        title="x",
        section="",
        line=1,
        fields=(("produit", "`system/lib/mnemosyne/production/partage.py`"),),
    )
    item_b = PlanItem(
        ident="C1",
        status="a_faire",
        title="y",
        section="",
        line=2,
        fields=(("produit", "`system/lib/mnemosyne/production/partage.py`"),),
    )
    a = le.Mandat(arc="B", porte="x.md", items=(item_a,))
    b = le.Mandat(arc="C", porte="y.md", items=(item_b,))
    assert le.recouvrement(a, b) == frozenset({"system/lib/mnemosyne/production/partage.py"})


def test_recouvrement_RESOUT_le_MEME_fichier_cite_a_deux_profondeurs() -> None:
    """ **ADDED (`E4` isolated audit, defect `a`): FALSE NEGATIVE PROVEN on the real plan** --
 `plan_format.py` is cited there under 3 different spellings, and the literal comparison (no
 `fichiers_reels`, the DEFAULT behavior) never makes them collide: each spelling is a distinct
 string for `frozenset.__and__`. This witness isolates the resolution: WITHOUT
 `fichiers_reels`, this exact case stays blind (asserted explicitly, not assumed); WITH it,
 `recouvrement` finds the shared file again by suffix."""
    item_a = PlanItem(
        ident="B1",
        status="a_faire",
        title="x",
        section="",
        line=1,
        fields=(("produit", "`plan_format.py`"),),
    )
    item_b = PlanItem(
        ident="C1",
        status="a_faire",
        title="y",
        section="",
        line=2,
        fields=(("produit", "`system/lib/mnemosyne/production/plan_format.py`"),),
    )
    a = le.Mandat(arc="B", porte="x.md", items=(item_a,))
    b = le.Mandat(arc="C", porte="y.md", items=(item_b,))
    assert le.recouvrement(a, b) == frozenset(), "without fichiers_reels: blind, BY DESIGN"
    fichiers_reels = frozenset(
        {"system/lib/mnemosyne/production/plan_format.py", "autre/dossier/fichier.py"}
    )
    assert le.recouvrement(a, b, fichiers_reels=fichiers_reels) == frozenset(
        {"system/lib/mnemosyne/production/plan_format.py"}
    )


def test_recouvrement_ne_FABRIQUE_jamais_une_collision_AMBIGUE() -> None:
    """A bare citation (`__init__.py`) whose suffix is shared by TWO real files must stay
    UNRESOLVED -- it must never accidentally unify with one of the two namesakes. Guards against
    the mirror risk of `a`: a remedy that resolves too broadly fabricates a FALSE POSITIVE, just as
    serious as a false negative -- it would block two chats that do not really overlap."""
    item_a = PlanItem(
        ident="B1",
        status="a_faire",
        title="x",
        section="",
        line=1,
        fields=(("produit", "`__init__.py`"),),
    )
    item_b = PlanItem(
        ident="C1",
        status="a_faire",
        title="y",
        section="",
        line=2,
        fields=(("produit", "`pkg_deux/__init__.py`"),),
    )
    a = le.Mandat(arc="B", porte="x.md", items=(item_a,))
    b = le.Mandat(arc="C", porte="y.md", items=(item_b,))
    fichiers_reels = frozenset({"pkg_un/__init__.py", "pkg_deux/__init__.py"})
    assert le.recouvrement(a, b, fichiers_reels=fichiers_reels) == frozenset()


# ---- THE ADMISSION: *To read* is published ABSENT, never invented or silenced --------------------
def test_le_champ_A_LIRE_vient_desormais_de_C4_PAS_de_l_aveu() -> None:
    """ `A_LIRE_EN_ATTENTE` stays exported for the record, but `rendre()` no longer prints it --
 `C4` (`a_lire.rendre_gabarit`) is built, the emitter CONSUMES it."""
    m = le.mandat_pour_arc(
        _reading("# PLAN — x\n\n## Les items\n\n- **B1** \U00002B1C **un.**\n"), porte="x.md", arc="B"
    )
    rendu = le.rendre(m, REPO_ROOT)
    assert le.A_LIRE_EN_ATTENTE not in rendu
    assert "NONE" in rendu  # fictional B1, no a_lire field -> the template names it honestly


# ---- NO ORCHESTRATOR REASONING: the closing condition, word for word -----------------------------
def test_le_mandat_ne_compose_QU_avec_des_champs_DEJA_publies() -> None:
    """ `E4`'s closing condition: *"the mandate carries no orchestrator reasoning."* Checked
 structurally: every item line comes from `ident`/`status`/`title`, nothing else -- no
 `detail`, no `fields`, which carry an item's own prose."""
    item = PlanItem(
        ident="B1",
        status="a_faire",
        title="public title",
        section="",
        line=1,
        detail=("\U000026A0\U0000FE0F PRIVATE ORCHESTRATOR REASONING — must NEVER leak",),
        fields=(("produit", "OTHER REASONING THAT MUST NOT LEAK"),),
    )
    mandat = le.Mandat(arc="B", porte="x.md", items=(item,))
    rendu = le.rendre(mandat, REPO_ROOT)
    assert "REASONING" not in rendu, rendu


# ---- THE POSTS CONTRACT: pointed at, never recopied -----------------------------------------------
def test_rendre_POINTE_le_contrat_des_postes_jamais_ne_le_recopie() -> None:
    """ **ADDED (`E4` isolated audit: the line was present, functional, but 0 witness in
 `tests/` before this one -- confirmed by a repo-wide search).** Checks the ADDRESS (the
 constant, literal, in the rendered text) and its REACHABILITY (the file it names really
 exists) -- never its CONTENT: `rendre()` does not read it, it NAMES it (D163)."""
    m = le.mandat_pour_arc(
        _reading("# PLAN — x\n\n## Les items\n\n- **B1** \U00002B1C **un.**\n"), porte="x.md", arc="B"
    )
    rendu = le.rendre(m, REPO_ROOT)
    assert le.CONTRAT_DES_POSTES in rendu
    assert (REPO_ROOT / le.CONTRAT_DES_POSTES).is_file()


# ---- THE CHAT CEILING: why it travels HERE (measured on 2026-09-08) ------------------------------
# WHAT THESE WITNESSES HOLD. `make orchestration-borne` returned 3 for another project, which ran with 4
# chats + one orchestrator, and nothing said a word. The reflex "make that command REFUSE" is
# wrong: it is read-only and on the path of NO gesture at all -- a chat is not born from it, it is
# born from a MANDATE. The ceiling therefore stops being published once to the orchestrator and is
# instead repeated at every birth. This is NOT a barrier and the witnesses require it explicitly
# (see the last one).
def test_le_mandat_PORTE_le_plafond_de_chats_quand_on_le_lui_donne() -> None:
    m = le.mandat_pour_arc(
        _reading("# PLAN — x\n\n## Les items\n\n- **B1** \U00002B1C **un.**\n"), porte="x.md", arc="B"
    )
    assert "chat ceiling" in le.rendre(m, REPO_ROOT, borne=3)
    assert "chat ceiling for this plan: 3" in le.rendre(m, REPO_ROOT, borne=3)


def test_un_plafond_INCONNU_ne_s_invente_pas() -> None:
    """``None`` OMITS the line. A mandate that announced a guessed ceiling would be worse than
    silent: it would speak with authority about a number nobody measured."""
    m = le.mandat_pour_arc(
        _reading("# PLAN — x\n\n## Les items\n\n- **B1** \U00002B1C **un.**\n"), porte="x.md", arc="B"
    )
    assert "chat ceiling" not in le.rendre(m, REPO_ROOT)


def test_le_plafond_du_mandat_est_le_MEME_FOYER_que_orchestration_borne() -> None:
    """ Two readers of the same question drift apart -- measured elsewhere in this repo. So the
 mandate recomputes NOTHING: it renders whatever :func:`borne_chats` renders over the SAME
 reading."""
    from mnemosyne.production.orchestration import borne_chats

    lecture = _reading(
        "# PLAN — x\n\n## Les items\n\n- **B1** \U00002B1C **un.**\n- **C1** \U00002B1C **deux.**\n"
    )
    m = le.mandat_pour_arc(lecture, porte="x.md", arc="B")
    attendu = borne_chats(lecture)
    assert f"chat ceiling for this plan: {attendu}" in le.rendre(m, REPO_ROOT, borne=attendu)


def test_le_mandat_AVOUE_qu_il_ne_refuse_rien() -> None:
    """ THE WITNESS THAT HOLDS HONESTY (A2). Mnémosyne cannot see LIVE chats -- they live in
 the harness, no state here can see them. A mandate that let someone believe in a barrier would
 fabricate false security: the 4th chat would be launched believing a refusal would have
 stopped it. The admission is therefore PART of the remedy, never a footnote."""
    m = le.mandat_pour_arc(
        _reading("# PLAN — x\n\n## Les items\n\n- **B1** \U00002B1C **un.**\n"), porte="x.md", arc="B"
    )
    rendu = le.rendre(m, REPO_ROOT, borne=3)
    assert "Nothing here REFUSES" in rendu
    assert "CEILING, never a requirement" in rendu
    # ADDED AFTER SABOTAGE: this witness's first version only held half the admission. Removing
    # "Mnemosyne cannot see live chats" -- the clause that says WHY nothing refuses -- left it
    # GREEN. *Checking one value does not protect the clause next to it.*
    assert "cannot see live chats" in rendu
    assert "your call" in rendu


def test_la_borne_traverse_REELLEMENT_la_CLI_pas_seulement_la_fonction() -> None:
    """ ADDED AFTER SABOTAGE, AND THIS IS THE WITNESS THAT WAS MISSING. The four witnesses
 above all call ``rendre()`` DIRECTLY: unwiring ``borne=borne_chats(lecture)`` inside
 ``lot_emit_run`` left them all GREEN, for a real mandate gone mute. This is the class *the
 barrier nothing calls* -- and it is EXACTLY the defect caught an hour earlier on the wiring of
 the report-aging field, reproduced here by its own author. A mechanism is only worth the real
 path that actually runs through it, so this witness pulls the CLI, never the function."""
    sortie = subprocess.run(
        ["make", "lot-emit", "ARC=A"],
        cwd=REPO_ROOT, capture_output=True, text=True, check=True,
    )
    assert "chat ceiling for this plan:" in sortie.stdout
    # THE NUMBER, not just the label (a line rendering "None" would otherwise pass) -- and it is
    # checked against the OTHER surface that publishes the same number, never against a value
    # written here: a hard-coded constant would go stale at the first closed item, and two
    # surfaces disagreeing on one ceiling is exactly the failure this wiring exists to prevent.
    dit_par_le_mandat = re.search(r"chat ceiling for this plan: (\d+)", sortie.stdout)
    assert dit_par_le_mandat, sortie.stdout[-400:]
    borne_cli = subprocess.run(
        ["make", "orchestration-borne"], cwd=REPO_ROOT, capture_output=True, text=True, check=True
    )
    dit_par_la_cible = re.search(r"chats to launch: (\d+)", borne_cli.stdout)
    assert dit_par_la_cible, borne_cli.stdout[-400:]
    assert dit_par_le_mandat.group(1) == dit_par_la_cible.group(1)


# ---- THE OPEN ONES: neither done nor closed -------------------------------------------------------
def test_ouverts_exclut_FAIT_et_CLOS_seulement() -> None:
    texte = (
        "# PLAN — x\n\n## Les items\n\n"
        "- **B1** \U00002B1C **a.**\n- **B2** \U00002705 **b.**\n- **B3** \U000026D4 **c.**\n- **B4** \U0001F504 **d.**\n"
    )
    m = le.mandat_pour_arc(_reading(texte), porte="x.md", arc="B")
    assert [i.ident for i in m.ouverts] == ["B1", "B4"]


def test_un_arc_SANS_item_rend_un_mandat_VIDE_pas_une_erreur() -> None:
    m = le.mandat_pour_arc(
        _reading("# PLAN — x\n\n## Les items\n\n- **B1** \U00002B1C **un.**\n"), porte="x.md", arc="Z"
    )
    assert m.items == () and m.ouverts == ()
    assert "Items (0" in le.rendre(m, REPO_ROOT)


# ---- THE REAL THING: 11 arcs, ZERO overlap, frozen -------------------------------------------------
def test_le_REEL_du_plan_est_gele_ZERO_recouvrement() -> None:
    """ The freeze goes through `scan_plans` (the PRODUCTION accessor), not `read_plan` on the
 door alone -- which renders `arcs=[]`, an EMPTY population. *The right source is the judge's
 own accessor.*

 **STRENGTHENED (`E4` isolated audit, defect `a`): frozen WITH resolution, not just
 literally.** The audit proved that a literal zero can be a zero from ABSENCE OF MEASUREMENT
 (different spellings masking a real collision) -- this witness now passes `fichiers_reels`
 (the `git ls-files` namespace, the same source `test_documents.py`'s own link reader uses) so
 that the zero frozen here is a zero over REAL paths, not their raw strings. Measured once more
 for this fix: still zero today, but for the first time a zero that actually looked."""
    projet = next(p for p in scan_plans(REPO_ROOT).projects if p.plan_path.parent.name == "docs")
    arcs = le.arcs_du_plan(projet.reading)
    assert arcs == frozenset("ABCDEFGHIJK"), sorted(arcs)
    mandats = {a: le.mandat_pour_arc(projet.reading, porte="docs/PLAN.md", arc=a) for a in arcs}
    sortie = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "ls-files"], capture_output=True, text=True, check=True
    )
    fichiers_reels = frozenset(sortie.stdout.splitlines())
    assert len(fichiers_reels) > 100, "suspicious namespace -- git ls-files returned too few lines"
    paires_en_recouvrement = [
        (a, b, le.recouvrement(mandats[a], mandats[b], fichiers_reels=fichiers_reels))
        for a in arcs
        for b in arcs
        if a < b and le.recouvrement(mandats[a], mandats[b], fichiers_reels=fichiers_reels)
    ]
    assert paires_en_recouvrement == [], paires_en_recouvrement


# ---- THE EDGE: end-to-end, refuses a nonexistent arc without raising -------------------------------
def test_le_bord_REFUSE_un_arc_inexistant_rc_2(capsys: pytest.CaptureFixture[str]) -> None:
    from mnemosyne.runtime.lot_emit_run import main

    rc = main(["ZZZ"])
    assert rc == 2
    assert "ZZZ" in capsys.readouterr().err


# ---- THE EDGE: three genuinely different failures used to render the SAME wording ------------------
# Routed to chat 1: the closing audit measured `RC=2` everywhere for three distinct causes (a path
# outside the scope `scan_plans` covers / a real folder with no PLAN.md / a valid PLAN.md outside
# the repo), and nothing told the caller which move to make. Each case below is PROVOKED (a real
# `main()`, never deduced from the code), and the legitimate case (`test_le_bord_EMET_un_mandat_reel_rc_0`,
# further down, never monkeypatched) must stay RC=0 -- checked precisely by NOT touching it.
def test_le_bord_NOMME_un_chemin_hors_du_perimetre_que_scan_plans_couvre(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from mnemosyne.runtime import lot_emit_run

    monkeypatch.setattr(lot_emit_run, "_REPO_ROOT", tmp_path)
    rc = lot_emit_run.main(["A", "--plan", "personal/un-projet"])
    assert rc == 2
    erreur = capsys.readouterr().err
    assert "scan_plans" in erreur and "never sees it" in erreur


def test_le_bord_NOMME_un_dossier_reel_sans_PLAN_md(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from mnemosyne.runtime import lot_emit_run

    (tmp_path / "projects" / "personal" / "un-projet").mkdir(parents=True)
    monkeypatch.setattr(lot_emit_run, "_REPO_ROOT", tmp_path)
    rc = lot_emit_run.main(["A", "--plan", "projects/personal/un-projet"])
    assert rc == 2
    erreur = capsys.readouterr().err
    assert "carries no PLAN.md" in erreur


def test_le_bord_NOMME_un_plan_valide_hors_du_depot(
    tmp_path: Path,
    tmp_path_factory: pytest.TempPathFactory,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from mnemosyne.runtime import lot_emit_run

    depot = tmp_path / "depot"
    depot.mkdir()
    dehors = tmp_path_factory.mktemp("hors-depot")
    (dehors / "PLAN.md").write_text("# PLAN — dehors\n\n> **Cap** : x\n", encoding="utf-8")
    monkeypatch.setattr(lot_emit_run, "_REPO_ROOT", depot)
    rc = lot_emit_run.main(["A", "--plan", str(dehors)])
    assert rc == 2
    erreur = capsys.readouterr().err
    assert "the path is outside the repo's root" in erreur


def test_le_bord_NOMME_les_TROIS_causes_par_des_messages_DISTINCTS(
    tmp_path: Path,
    tmp_path_factory: pytest.TempPathFactory,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """ The measured defect: the three cases rendered the SAME text. A single witness that pulls
 all three and compares the messages against each other, so the class stays closed even if
 someone one day makes two branches converge by accident."""
    from mnemosyne.runtime import lot_emit_run

    depot = tmp_path / "depot"
    (depot / "projects" / "personal" / "un-projet").mkdir(parents=True)
    dehors = tmp_path_factory.mktemp("hors-depot-2")
    (dehors / "PLAN.md").write_text("# PLAN — dehors\n\n> **Cap** : x\n", encoding="utf-8")
    monkeypatch.setattr(lot_emit_run, "_REPO_ROOT", depot)

    lot_emit_run.main(["A", "--plan", "personal/un-projet"])
    msg_hors_perimetre = capsys.readouterr().err
    lot_emit_run.main(["A", "--plan", "projects/personal/un-projet"])
    msg_absent = capsys.readouterr().err
    lot_emit_run.main(["A", "--plan", str(dehors)])
    msg_hors_depot = capsys.readouterr().err

    messages = (msg_hors_perimetre, msg_absent, msg_hors_depot)
    assert len(set(messages)) == 3, messages


# ---- C9: same class as C8 (an unknown neighbor variable ignored in silence), one notch lower ------
def test_C9_une_variable_VOISINE_MECONNUE_est_REFUSEE_au_lieu_de_retomber_en_silence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """C9: `--plan` comes from a Makefile interpolation (`$(if $(PLAN),--plan "$(PLAN)",)`), not
    from reading the environment -- but `make POUR=... lot-emit` (the wrong variable name) never
    passes `--plan`, and used to fall back silently to `docs`: a COMPLETE, plausible MANDATE, for
    the wrong project -- worse than C8, which only rendered a number."""
    from mnemosyne.runtime import lot_emit_run

    monkeypatch.setattr(lot_emit_run, "_REPO_ROOT", tmp_path)
    monkeypatch.setenv("POUR", "/un/chemin/quelconque")
    monkeypatch.delenv("PLAN", raising=False)
    rc = lot_emit_run.main(["A"])
    assert rc == 2
    erreur = capsys.readouterr().err
    assert "POUR=" in erreur and "PLAN=" in erreur, erreur


def test_C9_PLAN_correct_prime_sur_un_voisin_present_par_accident(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """`--plan` set explicitly is never blocked by a neighbor variable lying around in the
    environment -- only the ABSENCE of `--plan` together with a present neighbor is a signal."""
    from mnemosyne.runtime import lot_emit_run

    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "PLAN.md").write_text(
        "# PLAN — voisin\n\n> **Cap** : x\n\n- **A1** \U00002B1C **un.**\n", encoding="utf-8"
    )
    monkeypatch.setattr(lot_emit_run, "_REPO_ROOT", tmp_path)
    monkeypatch.setenv("POUR", "/un/chemin/quelconque")
    rc = lot_emit_run.main(["A", "--plan", "docs"])
    assert rc == 0, capsys.readouterr().err


# ---- C9: a plan with NUMBERED sub-plan folders (D166 clause 3) was INVISIBLE to lot-emit ----------
def _plan_a_sous_plans_numerotes(tmp_path: Path) -> Path:
    """A PURE fixture (never `projects/`, never a real project's name): a root door with ONE flat item, and TWO
    numbered sub-plan FOLDERS, exactly the shape D166 clause 3 legitimizes and which blocked a
    real project orchestrator (`carte` saw 14, `lot-emit` saw 2)."""
    racine = tmp_path / "projects" / "bulle" / "gigogne"
    (racine / "plan").mkdir(parents=True)
    (racine / "PLAN.md").write_text(
        "# PLAN — gigogne\n\n> **Cap** : mesurer les sous-plans\n\n"
        "- plan/arc-a.md\n- plan/01-premier/PLAN.md\n- plan/02-second/PLAN.md\n",
        encoding="utf-8",
    )
    (racine / "plan" / "arc-a.md").write_text("- **A1** \U00002B1C **racine.**\n", encoding="utf-8")
    premier = racine / "plan" / "01-premier"
    premier.mkdir()
    (premier / "PLAN.md").write_text(
        "# PLAN — premier\n\n> **Cap** : x\n\n- **B1** \U00002B1C **un.**\n", encoding="utf-8"
    )
    second = racine / "plan" / "02-second"
    second.mkdir()
    (second / "PLAN.md").write_text(
        "# PLAN — second\n\n> **Cap** : x\n\n- **C1** \U00002B1C **un.**\n", encoding="utf-8"
    )
    return tmp_path


def test_C9_lot_emit_VOIT_desormais_les_arcs_DOSSIERS_que_carte_voit_deja(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The defect measured on a real project: `carte POUR=<project>` saw 14 arcs, `lot-emit
    PLAN=<project>` only 2 (`declare_seulement_ici` on the root side -- not a divergence, a
    BLIND SPOT). Here, on a pure fixture: the root carries `A1`, the two sub-plans carry `B1`/`C1`
    -- all three must be reachable through `lot-emit`, EACH UNDER ITS OWN ARC (the name of the
    sub-plan that carries it, D166 clause 3 -- the same home as `carte._arc_de`, never a letter)."""
    from mnemosyne.runtime import lot_emit_run

    depot = _plan_a_sous_plans_numerotes(tmp_path)
    monkeypatch.setattr(lot_emit_run, "_REPO_ROOT", depot)

    rc_a = lot_emit_run.main(["bulle/gigogne", "--plan", "projects/bulle/gigogne"])
    assert rc_a == 0, capsys.readouterr().err
    sortie_a = capsys.readouterr().out
    assert "A1" in sortie_a

    rc_b = lot_emit_run.main(
        ["bulle/gigogne/plan/01-premier", "--plan", "projects/bulle/gigogne"]
    )
    assert rc_b == 0, capsys.readouterr().err
    sortie_b = capsys.readouterr().out
    assert "B1" in sortie_b

    rc_c = lot_emit_run.main(
        ["bulle/gigogne/plan/02-second", "--plan", "projects/bulle/gigogne"]
    )
    assert rc_c == 0, capsys.readouterr().err
    sortie_c = capsys.readouterr().out
    assert "C1" in sortie_c


def test_C9_la_ligne_de_REFUS_nomme_desormais_les_TROIS_arcs_pas_UN_SEUL(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The "nonexistent arc" refusal cites `arcs_du_plan` -- same accessor, hence the same fix: the
    list of real arcs must now name the three SUB-PLANS by their own name, not three letters (a
    bare letter is no longer a valid key once more than one sub-plan is readable)."""
    from mnemosyne.runtime import lot_emit_run

    depot = _plan_a_sous_plans_numerotes(tmp_path)
    monkeypatch.setattr(lot_emit_run, "_REPO_ROOT", depot)

    rc = lot_emit_run.main(["ZZZ", "--plan", "projects/bulle/gigogne"])
    assert rc == 2
    erreur = capsys.readouterr().err
    assert (
        "bulle/gigogne," in erreur
        and "bulle/gigogne/plan/01-premier" in erreur
        and "bulle/gigogne/plan/02-second" in erreur
    ), erreur


def test_C9_deux_sous_plans_dont_les_LETTRES_COLLISIONNENT_restent_deux_arcs_distincts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The REAL defect measured on another project, not just the blindness `_plan_a_sous_plans_numerotes`
    reproduces: `A01-1` and `A03-1` share the same letter prefix (`A`, see `perimetre._PREFIXE`)
    but live in TWO distinct sub-plans. The old mechanism (`lettre_d_arc`, fallback alone) would
    have MELTED them into a single `ARC=A` mandate -- exactly the "12 folder-arcs melted into A"
    measured by the orchestrator on the real project. The new one must keep them separate AND
    refuse the bare letter, which is no longer a valid identity once more than one sub-plan is
    readable."""
    from mnemosyne.runtime import lot_emit_run

    racine = tmp_path / "projects" / "bulle" / "gigogne"
    (racine / "plan").mkdir(parents=True)
    (racine / "PLAN.md").write_text(
        "# PLAN — gigogne\n\n> **Cap** : x\n\n"
        "- plan/01-premier/PLAN.md\n- plan/02-second/PLAN.md\n",
        encoding="utf-8",
    )
    premier = racine / "plan" / "01-premier"
    premier.mkdir()
    (premier / "PLAN.md").write_text(
        "# PLAN — premier\n\n> **Cap** : x\n\n- **A01-1** \U00002B1C **un.**\n", encoding="utf-8"
    )
    second = racine / "plan" / "02-second"
    second.mkdir()
    (second / "PLAN.md").write_text(
        "# PLAN — second\n\n> **Cap** : x\n\n- **A03-1** \U00002B1C **un.**\n", encoding="utf-8"
    )
    monkeypatch.setattr(lot_emit_run, "_REPO_ROOT", tmp_path)

    rc_1 = lot_emit_run.main(
        ["bulle/gigogne/plan/01-premier", "--plan", "projects/bulle/gigogne"]
    )
    assert rc_1 == 0, capsys.readouterr().err
    sortie_1 = capsys.readouterr().out
    assert "A01-1" in sortie_1 and "A03-1" not in sortie_1

    rc_2 = lot_emit_run.main(
        ["bulle/gigogne/plan/02-second", "--plan", "projects/bulle/gigogne"]
    )
    assert rc_2 == 0, capsys.readouterr().err
    sortie_2 = capsys.readouterr().out
    assert "A03-1" in sortie_2 and "A01-1" not in sortie_2

    rc_lettre = lot_emit_run.main(["A", "--plan", "projects/bulle/gigogne"])
    assert rc_lettre == 2, capsys.readouterr().out


def test_C9_une_BRAISE_dans_un_sous_plan_n_entre_PAS_dans_le_mandat_de_son_arc(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """ REGRESSION FOUND BY THE ISOLATED AUDIT (D75), fixed in the same commit as this
 witness. `arc_par_item` maps EVERY readable item to its sub-plan, embers included -- correct
 for ITS OWN question, but `mandat_pour_arc` has promised since C8 that "an ember never enters
 any real arc mandate." On the flat fallback the invariant held by accident (the `"BR"` prefix
 never coincides with any arc letter); on a sub-plan that hosts both a real item and an ember,
 nothing played that role before the fix -- the ember would have ended up in the mandate of the
 chat assigned to that arc."""
    from mnemosyne.runtime import lot_emit_run

    racine = tmp_path / "projects" / "bulle" / "gigogne"
    (racine / "plan").mkdir(parents=True)
    (racine / "PLAN.md").write_text(
        "# PLAN — gigogne\n\n> **Cap** : x\n\n"
        "- plan/01-premier/PLAN.md\n- plan/02-second/PLAN.md\n",
        encoding="utf-8",
    )
    premier = racine / "plan" / "01-premier"
    premier.mkdir()
    (premier / "PLAN.md").write_text(
        "# PLAN — premier\n\n> **Cap** : x\n\n- **A1** \U00002B1C **un.**\n- **BR1** \U00002B1C **une braise.**\n",
        encoding="utf-8",
    )
    second = racine / "plan" / "02-second"
    second.mkdir()
    (second / "PLAN.md").write_text(
        "# PLAN — second\n\n> **Cap** : x\n\n- **B1** \U00002B1C **un.**\n", encoding="utf-8"
    )
    monkeypatch.setattr(lot_emit_run, "_REPO_ROOT", tmp_path)

    rc = lot_emit_run.main(["bulle/gigogne/plan/01-premier", "--plan", "projects/bulle/gigogne"])
    assert rc == 0, capsys.readouterr().err
    sortie = capsys.readouterr().out
    assert "A1" in sortie
    assert "BR1" not in sortie, "an ember slipped into its sub-plan's mandate"


# ---- C5 WIRED: decouper_mandat / rendre_lot / assembler_mandat, pure ------------------------------
def test_decouper_mandat_ne_decoupe_QUE_les_items_OUVERTS() -> None:
    """`fait`/`clos` have nothing to dispatch -- same filter as `.ouverts`, not a second one."""
    texte = (
        "# PLAN — x\n\n## Les items\n\n- **B1** \U00002B1C **a.**\n- **B2** \U00002705 **b.**\n- **B3** \U00002B1C **c.**\n"
    )
    m = le.mandat_pour_arc(_reading(texte), porte="x.md", arc="B")
    lots = le.decouper_mandat(m, taille=1)
    assert [i.ident for lot in lots for i in lot.items] == ["B1", "B3"]


def test_decouper_mandat_DELEGUE_a_parc_meme_forme_meme_determinisme() -> None:
    texte = (
        "# PLAN — x\n\n## Les items\n\n- **B1** \U00002B1C **a.**\n- **B2** \U00002B1C **b.**\n- **B3** \U00002B1C **c.**\n"
    )
    m = le.mandat_pour_arc(_reading(texte), porte="x.md", arc="B")
    lots = le.decouper_mandat(m, taille=2)
    assert [lot.indice for lot in lots] == [0, 1]
    assert [i.ident for i in lots[0].items] == ["B1", "B2"]
    assert [i.ident for i in lots[1].items] == ["B3"]


def test_rendre_lot_NE_COMPOSE_QU_avec_des_champs_DEJA_publies() -> None:
    """Same promise as `rendre()` (E4) -- not a second template that forgets the rule."""
    item = PlanItem(
        ident="B1",
        status="a_faire",
        title="public title",
        section="",
        line=1,
        detail=("\U000026A0\U0000FE0F PRIVATE ORCHESTRATOR REASONING — must NEVER leak",),
        fields=(("produit", "OTHER REASONING THAT MUST NOT LEAK"),),
    )
    lot = Lot(indice=0, items=(item,))
    rendu = le.rendre_lot(lot)
    assert "REASONING" not in rendu, rendu
    assert "B1" in rendu and "public title" in rendu


def test_assembler_mandat_REFUSE_et_NOMME_meme_comportement_que_parc() -> None:
    """Not a second completeness check -- just the pass-through to `parc.assembler`."""
    texte = "# PLAN — x\n\n## Les items\n\n- **B1** \U00002B1C **a.**\n- **B2** \U00002B1C **b.**\n"
    m = le.mandat_pour_arc(_reading(texte), porte="x.md", arc="B")
    lots = le.decouper_mandat(m, taille=1)

    def lire(lot: Lot) -> str | None:
        return None if lot.indice == 1 else "vu"

    assemblage = le.assembler_mandat(lots, lire)
    assert assemblage.complet is False
    assert assemblage.manquants == (1,)
    assert assemblage.rendus == ("vu",)


# ---- C5 WIRED, THE EDGE: --emettre-lots / --assembler-lots, a REAL refusal (not just a boolean) ---
def _arc_avec_au_moins_un_ouvert() -> str:
    """The first REAL arc of this repo's own plan that has at least one open item -- never a
    frozen number: the plan moves, so this choice must move with it rather than break a witness
    that has nothing to do with how many items a specific arc has open."""
    projet = next(p for p in scan_plans(REPO_ROOT).projects if p.plan_path.parent.name == "docs")
    for arc in sorted(le.arcs_du_plan(projet.reading)):
        m = le.mandat_pour_arc(projet.reading, porte="docs/PLAN.md", arc=arc)
        if m.ouverts:
            return arc
    pytest.skip("no arc of the real plan has an open item today -- nothing to split")


def test_le_bord_emet_puis_REFUSE_tant_qu_un_OUT_manque(tmp_path: Path) -> None:
    from mnemosyne.runtime.lot_emit_run import main

    arc = _arc_avec_au_moins_un_ouvert()
    dossier = tmp_path / "lots"
    rc = main([arc, "--emettre-lots", "1", "--dossier", str(dossier)])
    assert rc == 0
    fichiers_in = sorted(dossier.glob("lot_*_IN.md"))
    assert fichiers_in, "no batch emitted -- yet the chosen arc did not have 0 open items"

    rc = main([arc, "--assembler-lots", "1", "--dossier", str(dossier)])
    assert rc == 2, "no OUT written -- the assembly must REFUSE, not return an ignored boolean"


def test_le_bord_ASSEMBLE_et_REUSSIT_quand_TOUS_les_OUT_existent(tmp_path: Path) -> None:
    from mnemosyne.runtime.lot_emit_run import main

    arc = _arc_avec_au_moins_un_ouvert()
    dossier = tmp_path / "lots"
    main([arc, "--emettre-lots", "1", "--dossier", str(dossier)])
    for f in sorted(dossier.glob("lot_*_IN.md")):
        n = f.name.removeprefix("lot_").removesuffix("_IN.md")
        (dossier / f"lot_{n}_OUT.md").write_text("vu")

    rc = main([arc, "--assembler-lots", "1", "--dossier", str(dossier)])
    assert rc == 0


def test_le_bord_NOMME_le_lot_manquant_pas_juste_un_compte(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Sabotage-testable: if `--assembler-lots` merely counted the missing ones without naming
    them, this test would not see it -- it reads the exact INDEX in the output, not just an
    integer."""
    from mnemosyne.runtime.lot_emit_run import main

    arc = _arc_avec_au_moins_un_ouvert()
    dossier = tmp_path / "lots"
    main([arc, "--emettre-lots", "1", "--dossier", str(dossier)])
    fichiers_in = sorted(dossier.glob("lot_*_IN.md"))
    for f in fichiers_in:
        n = f.name.removeprefix("lot_").removesuffix("_IN.md")
        (dossier / f"lot_{n}_OUT.md").write_text("vu")
    premier_indice = fichiers_in[0].name.removeprefix("lot_").removesuffix("_IN.md")
    (dossier / f"lot_{premier_indice}_OUT.md").unlink()

    rc = main([arc, "--assembler-lots", "1", "--dossier", str(dossier)])
    assert rc == 2
    assert f"({premier_indice},)" in capsys.readouterr().err


def test_le_bord_EMET_un_mandat_reel_rc_0(capsys: pytest.CaptureFixture[str]) -> None:
    from mnemosyne.runtime.lot_emit_run import main

    rc = main(["B"])
    sortie = capsys.readouterr().out
    assert rc == 0
    assert "MANDATE — arc B" in sortie and "B1" in sortie
    assert "TWO branches" in sortie  # C4's template is indeed consumed, not the admission
