"""The EDGE of D6 -- the one that opens `git`, where the judge (`plan_ordre.duree_par_etape`) reads nothing.

 These witnesses exist because the edge is NEW code that opens a subprocess and parses its
output: the places where a measurement dies in silence. *A pure judge is tested by its values; an
edge is tested by what it does when history does not answer as expected.*

 **ISOLATED AUDIT OF 2026-08-16: NOT HELD on the clause, 4 real defects.** The fixtures below
all open on a DUMMY commit before creating the real content -- without it, the first real
commit IS the root commit, and Q2's fix (see `plan_duree_run._est_commit_racine`) would then
name cases these witnesses want to prove DATABLE instead.
"""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from mnemosyne.production.plan_format import read_plan
from mnemosyne.runtime.plan_duree_run import (
    _est_commit_racine,
    _relatif,
    date_fermeture,
    date_ouverture,
    duree_du_plan,
)


def _git(racine: Path, *a: str) -> None:
    subprocess.run(["git", *a], cwd=racine, check=True, capture_output=True)


def _init_avec_commit_dummy(racine: Path) -> None:
    """A first commit that creates NONE of the real content -- so that the real work, further
    down, never lands on the ROOT commit by fixture accident (see the warning at the top)."""
    _git(racine, "init", "-q")
    _git(racine, "config", "user.email", "t@t.t")
    _git(racine, "config", "user.name", "t")
    (racine / ".gitkeep").write_text("")
    _git(racine, "add", ".gitkeep")
    _git(racine, "commit", "-q", "-m", "dummy")


def _depot_avec_une_etape_fermee(racine: Path) -> None:
    """A minimal repo: a PRODUCT file created, then PLAN.md moves A1 from to two commits
 later -- the simplest population that distinguishes OPENING and CLOSING."""
    _init_avec_commit_dummy(racine)

    (racine / "PLAN.md").write_text(
        "# PLAN — demo\n\n> **Cap** : x\n\n"
        "- **A1** \U00002B1C an item.\n"
        "  *Produit* : `module.py`\n"
    )
    (racine / "module.py").write_text("# nothing yet\n")
    _git(racine, "add", "PLAN.md", "module.py")
    _git(racine, "commit", "-q", "-m", "open A1")

    (racine / "module.py").write_text("# real work\n")
    _git(racine, "add", "module.py")
    _git(racine, "commit", "-q", "-m", "work on A1")

    (racine / "PLAN.md").write_text(
        "# PLAN — demo\n\n> **Cap** : x\n\n"
        "- **A1** \U00002705 an item.\n"
        "  *Produit* : `module.py`\n"
    )
    _git(racine, "add", "PLAN.md")
    _git(racine, "commit", "-q", "-m", "close A1")


def test_relatif_LAISSE_un_chemin_relatif_INCHANGE():
    assert _relatif(Path("/repo"), "module.py") == "module.py"


def test_relatif_RAMENE_un_chemin_ABSOLU_sous_repo_root():
    """ The defect measured on a real project, isolated here without `git`: `git show <sha>:<chemin>`
 refuses an absolute path where `git log -- <chemin>` accepts it -- the function normalises
 BEFORE entering any command, whichever one follows."""
    assert _relatif(Path("/repo"), "/repo/plan/arc.md") == "plan/arc.md"


def test_relatif_chemin_HORS_repo_root_reste_TEL_QUEL():
    assert _relatif(Path("/repo"), "/ailleurs/x.py") == "/ailleurs/x.py"


def test_date_ouverture_REND_None_pour_un_chemin_QUI_N_A_JAMAIS_EXISTE():
    with tempfile.TemporaryDirectory() as td:
        racine = Path(td)
        _depot_avec_une_etape_fermee(racine)
        assert date_ouverture(racine, ("never-written.py",)) is None


def test_date_ouverture_REND_le_PREMIER_commit_qui_touche_le_fichier():
    with tempfile.TemporaryDirectory() as td:
        racine = Path(td)
        _depot_avec_une_etape_fermee(racine)
        ouverture = date_ouverture(racine, ("module.py",))
        assert ouverture is not None
        # The first commit that touches module.py (opening A1) must win, not the second.
        premiere_date = subprocess.run(
            ["git", "log", "--reverse", "--format=%aI", "--", "module.py"],
            cwd=racine, capture_output=True, text=True,
        ).stdout.splitlines()[0]
        assert ouverture == premiere_date


def test_date_ouverture_REND_None_quand_le_SEUL_commit_trouve_est_la_RACINE():
    """ 2026-08-16 AUDIT (Q2), the heaviest of the four defects: on a real project, 9 items out of 18
 both opened AND closed on the root commit ("fresh repo after object loss") and came out at
 `jours=0.0` -- indistinguishable from real lightning-fast work. One item (`F7`) itself carries
 "CLOSED on 2026-07-29", NINE DAYS before the visible history even begins."""
    with tempfile.TemporaryDirectory() as td:
        racine = Path(td)
        _git(racine, "init", "-q")
        _git(racine, "config", "user.email", "t@t.t")
        _git(racine, "config", "user.name", "t")
        (racine / "module.py").write_text("# already there at import\n")
        _git(racine, "add", "module.py")
        _git(racine, "commit", "-q", "-m", "base: fresh repo")
        assert date_ouverture(racine, ("module.py",)) is None


def test_est_commit_racine_distingue_LE_PREMIER_des_SUIVANTS():
    with tempfile.TemporaryDirectory() as td:
        racine = Path(td)
        _init_avec_commit_dummy(racine)
        (racine / "x.py").write_text("1\n")
        _git(racine, "add", "x.py")
        _git(racine, "commit", "-q", "-m", "second commit")
        racine_sha = subprocess.run(
            ["git", "log", "--reverse", "--format=%H"], cwd=racine, capture_output=True, text=True
        ).stdout.splitlines()[0]
        tete_sha = subprocess.run(
            ["git", "log", "-1", "--format=%H"], cwd=racine, capture_output=True, text=True
        ).stdout.strip()
        assert _est_commit_racine(racine, racine_sha) is True
        assert _est_commit_racine(racine, tete_sha) is False


def test_date_fermeture_REND_None_pour_un_item_QUI_NE_FERME_JAMAIS():
    with tempfile.TemporaryDirectory() as td:
        racine = Path(td)
        _depot_avec_une_etape_fermee(racine)
        assert date_fermeture(racine, "PLAN.md", "DOES-NOT-EXIST") is None


def test_date_fermeture_REND_le_PREMIER_commit_ou_le_statut_devient_ferme():
    with tempfile.TemporaryDirectory() as td:
        racine = Path(td)
        _depot_avec_une_etape_fermee(racine)
        fermeture = date_fermeture(racine, "PLAN.md", "A1")
        assert fermeture is not None
        derniere_date = subprocess.run(
            ["git", "log", "-1", "--format=%aI"], cwd=racine, capture_output=True, text=True
        ).stdout.strip()
        assert fermeture == derniere_date, "the last commit (closing A1) is the one that closes"


def test_date_fermeture_REND_la_DERNIERE_transition_PAS_LA_PREMIERE():
    """ 2026-08-16 AUDIT (Q4): an item that closes then REOPENS then closes again had its
 duration published on the FIRST closing -- 2 days instead of the real 19 in the audit's case,
 89 % of the step's cost lost. Reproduced here with explicit dates (`GIT_AUTHOR_DATE`)."""
    with tempfile.TemporaryDirectory() as td:
        racine = Path(td)
        _git(racine, "init", "-q")
        _git(racine, "config", "user.email", "t@t.t")
        _git(racine, "config", "user.name", "t")

        def commit(text: str, when: str) -> None:
            (racine / "PLAN.md").write_text(text)
            _git(racine, "add", "PLAN.md")
            env_commit = subprocess.run(
                ["git", "commit", "-q", "-m", "c", f"--date={when}"],
                cwd=racine, capture_output=True, text=True,
                env={"GIT_AUTHOR_DATE": when, "GIT_COMMITTER_DATE": when,
                     "PATH": subprocess.os.environ["PATH"]},
            )
            assert env_commit.returncode == 0, env_commit.stderr

        base = "# PLAN — demo\n\n> **Cap** : x\n\n- **E1** {glyphe} an item.\n  *Produit* : `x`\n"
        commit(base.format(glyphe="\U00002B1C"), "2026-01-01T00:00:00+00:00")
        commit(base.format(glyphe="\U00002705"), "2026-01-03T00:00:00+00:00")  # premature closing
        commit(base.format(glyphe="\U0001F504"), "2026-01-10T00:00:00+00:00")  # reopened
        commit(base.format(glyphe="\U00002705"), "2026-01-20T00:00:00+00:00")  # closed again, for good

        fermeture = date_fermeture(racine, "PLAN.md", "E1")
        assert fermeture is not None
        assert fermeture.startswith("2026-01-20"), (
            f"the LAST closing must win, not the first one (2026-01-03): {fermeture}"
        )


def test_date_ouverture_REPLIE_sur_le_BASENAME_quand_le_chemin_direct_ne_rend_rien():
    """ 2026-08-16 AUDIT (Q1/Q3): `chemins_cites_par_produit` resolves nothing on disk by
 design -- a `*Produit*` citing `` `module.py` `` while the real file lives under
 `src/module.py` made `git log -- module.py` come back EMPTY (nothing at that root), and the
 item was counted as "opening not datable" even though a REAL path, just incomplete, existed
 (case measured: `pret_a_executer.py` cited for `validation/plan/pret_a_executer.py` on a real
 project, item `P13`)."""
    with tempfile.TemporaryDirectory() as td:
        racine = Path(td)
        _init_avec_commit_dummy(racine)
        (racine / "src").mkdir()
        (racine / "src" / "module.py").write_text("# nested\n")
        _git(racine, "add", "src/module.py")
        _git(racine, "commit", "-q", "-m", "create under src/")
        assert date_ouverture(racine, ("module.py",)) is not None, (
            "the **/module.py fallback must find src/module.py"
        )


def test_date_fermeture_accepte_un_chemin_ABSOLU_grace_a__relatif():
    """Reproduces the defect measured on a real project in a throwaway repo: without `_relatif`, this call
    used to return `None` (`git show` refusing the absolute path) -- sabotage-verified on this
    same witness."""
    with tempfile.TemporaryDirectory() as td:
        racine = Path(td)
        _depot_avec_une_etape_fermee(racine)
        chemin_absolu = str(racine / "PLAN.md")
        assert date_fermeture(racine, chemin_absolu, "A1") is not None


def test_duree_du_plan_BOUT_EN_BOUT_date_une_etape_REELLEMENT_fermee():
    with tempfile.TemporaryDirectory() as td:
        racine = Path(td)
        _depot_avec_une_etape_fermee(racine)
        reading = read_plan((racine / "PLAN.md").read_text(), origin="PLAN.md")
        duree = duree_du_plan(racine, reading, "PLAN.md")
        assert len(duree) == 1
        assert duree[0].ident == "A1"
        assert duree[0].jours is not None and duree[0].jours >= 0
        assert duree[0].raison_absence == ""


def test_duree_du_plan_NOMME_un_produit_SANS_CHEMIN_RECONNAISSABLE():
    """A `*Produit*` that cites no path (free prose) has nothing to ask `git log` --
    the opening is named non-datable, never guessed at zero."""
    with tempfile.TemporaryDirectory() as td:
        racine = Path(td)
        _init_avec_commit_dummy(racine)
        (racine / "PLAN.md").write_text(
            "# PLAN — demo\n\n> **Cap** : x\n\n"
            "- **A1** \U00002705 an item.\n"
            "  *Produit* : a sentence citing no path at all\n"
        )
        _git(racine, "add", "PLAN.md")
        _git(racine, "commit", "-q", "-m", "close directly")
        reading = read_plan((racine / "PLAN.md").read_text(), origin="PLAN.md")
        duree = duree_du_plan(racine, reading, "PLAN.md")
        assert len(duree) == 1
        assert duree[0].jours is None
        assert duree[0].raison_absence == "opening not datable"
