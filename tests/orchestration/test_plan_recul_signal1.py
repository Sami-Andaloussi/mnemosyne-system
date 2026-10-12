"""Signal 1 of D5 (`plan_recul_run.py`) — the JUDGE (`plan_derive.immobilite`) is already tested
elsewhere (D1); this file tests only the EDGE: building `Tour.faits` over the REAL history of
the sibling project's nested repo, never `projects/.git` (see the field correction, D5, third)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from mnemosyne.runtime.plan_recul_run import _sibling_faits, _sibling_tours, immobilite_sibling

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SIBLING_NICHE_ABSENT = not (
    _REPO_ROOT / "projects" / "saas" / "Sibling Research" / ".git"
).is_dir()


def _git(work_tree: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(work_tree), *args], capture_output=True, text=True, check=True
    )


def _init_sibling(tmp_path: Path) -> tuple[Path, Path]:
    """A minimal, real, nested repo for the sibling project, under ``tmp_path/projects/saas/Sibling Research/.git``."""
    work_tree = tmp_path / "projects" / "saas" / "Sibling Research"
    work_tree.mkdir(parents=True)
    _git(work_tree, "init", "--quiet")
    _git(work_tree, "config", "user.email", "t@t.example")
    _git(work_tree, "config", "user.name", "t")
    return work_tree / ".git", work_tree


def _commit(work_tree: Path, message: str, files: dict[str, str]) -> str:
    for chemin, contenu in files.items():
        cible = work_tree / chemin
        cible.parent.mkdir(parents=True, exist_ok=True)
        cible.write_text(contenu, encoding="utf-8")
    _git(work_tree, "add", "-A")
    _git(work_tree, "commit", "--quiet", "-m", message)
    return _git(work_tree, "rev-parse", "HEAD").stdout.strip()


def _item(ident: str, statut: str) -> str:
    return f"# {ident}\n\n- **{ident}** {statut} **Item title.** Body.\n"


# --------------------------------------------------------------------------------------------
# _sibling_faits
# --------------------------------------------------------------------------------------------


def test_sibling_faits_ne_compte_QUE_les_items_FAIT(tmp_path: Path) -> None:
    git_dir, work_tree = _init_sibling(tmp_path)
    sha = _commit(
        work_tree,
        "init",
        {
            "plan/A1.md": _item("A1", "\U00002705"),
            "plan/A2.md": _item("A2", "\U00002B1C"),
            "plan/A3.md": _item("A3", "\U00002705"),
            "plan/A4.md": _item("A4", "\U0001F504"),
        },
    )
    assert _sibling_faits(sha, git_dir, work_tree) == frozenset({"A1", "A3"})


def test_sibling_faits_ANCRE_en_debut_de_ligne_jamais_en_PROSE(tmp_path: Path) -> None:
    """A status mention in the MIDDLE of a paragraph (not an item bullet) must never
    count -- the same trap as A7 (a teaching example mistaken for a real item)."""
    git_dir, work_tree = _init_sibling(tmp_path)
    sha = _commit(
        work_tree,
        "init",
        {
            "plan/A1.md": (
                "# A1\n\n"
                "A paragraph that MENTIONS - **A1** \U00002705 right in the middle, never at the start of a line.\n\n"
                "- **A1** \U00002B1C **The real item.** Still open.\n"
            ),
        },
    )
    assert _sibling_faits(sha, git_dir, work_tree) == frozenset()


def test_sibling_faits_rend_ensemble_vide_quand_aucun_item_FAIT(tmp_path: Path) -> None:
    git_dir, work_tree = _init_sibling(tmp_path)
    sha = _commit(work_tree, "init", {"plan/A1.md": _item("A1", "\U00002B1C")})
    assert _sibling_faits(sha, git_dir, work_tree) == frozenset()


def test_sibling_faits_rend_None_sur_un_sha_inexistant(tmp_path: Path) -> None:
    git_dir, work_tree = _init_sibling(tmp_path)
    _commit(work_tree, "init", {"plan/A1.md": _item("A1", "\U00002705")})
    assert _sibling_faits("0" * 40, git_dir, work_tree) is None


# --------------------------------------------------------------------------------------------
# _sibling_tours / immobilite_sibling
# --------------------------------------------------------------------------------------------


def test_sibling_tours_rend_None_quand_le_depot_niche_est_absent(tmp_path: Path) -> None:
    assert _sibling_tours(tmp_path) is None
    assert immobilite_sibling(tmp_path) is None


def test_sibling_tours_HERITE_les_faits_sur_les_commits_HORS_plan(tmp_path: Path) -> None:
    """A commit that does NOT touch `plan/` cannot move the set of items -- it must
 carry EXACTLY the same set as the previous plan-touching commit, never `None` nor a
 set recomputed from empty."""
    _, work_tree = _init_sibling(tmp_path)
    _commit(work_tree, "plan: A1 done", {"plan/A1.md": _item("A1", "\U00002705")})
    _commit(work_tree, "code: unrelated to the plan", {"src/x.py": "print(1)\n"})
    tours = _sibling_tours(tmp_path)
    assert tours is not None
    assert len(tours) == 2
    assert tours[0].faits == frozenset({"A1"})
    assert tours[1].faits == frozenset({"A1"})  # inherited, not recomputed from empty


def test_sibling_tours_RECALCULE_sur_chaque_commit_touchant_plan(tmp_path: Path) -> None:
    _, work_tree = _init_sibling(tmp_path)
    _commit(work_tree, "plan: nothing done", {"plan/A1.md": _item("A1", "\U00002B1C")})
    _commit(work_tree, "plan: A1 closed", {"plan/A1.md": _item("A1", "\U00002705")})
    tours = _sibling_tours(tmp_path)
    assert tours is not None
    assert [t.faits for t in tours] == [frozenset(), frozenset({"A1"})]


def test_immobilite_sibling_trouve_LA_PLUS_LONGUE_suite_immobile(tmp_path: Path) -> None:
    """A synthetic but REAL replay (real git, real commits): A1 closes on the 2nd commit, then
    the set stops moving for 3 commits outside the plan -- that is the longest stillness."""
    _, work_tree = _init_sibling(tmp_path)
    _commit(work_tree, "plan: nothing", {"plan/A1.md": _item("A1", "\U00002B1C")})
    _commit(work_tree, "plan: A1 closed", {"plan/A1.md": _item("A1", "\U00002705")})
    _commit(work_tree, "code: x", {"src/x.py": "1\n"})
    _commit(work_tree, "code: y", {"src/y.py": "1\n"})
    _commit(work_tree, "code: z", {"src/z.py": "1\n"})
    longue = immobilite_sibling(tmp_path)
    assert longue is not None
    assert longue.commits == 4  # the closing commit + the 3 that follow without moving
    assert longue.ensemble == frozenset({"A1"})


@pytest.mark.skipif(
    _SIBLING_NICHE_ABSENT, reason="the sibling project's nested repo is not present on this host"
)
def test_sibling_faits_sur_la_POPULATION_REELLE_reproduit_le_chiffre_mesure_a_la_main() -> None:
    """ Reproduced by hand before writing a single line of code (`git grep ... HEAD -- plan/`):
 18 items marked DONE at HEAD on the sibling project's real nested repo."""
    from mnemosyne.runtime.plan_recul_run import _SIBLING_NICHE

    git_dir = _REPO_ROOT / "projects" / _SIBLING_NICHE / ".git"
    work_tree = _REPO_ROOT / "projects" / _SIBLING_NICHE
    head = _git(work_tree, "rev-parse", "HEAD").stdout.strip()
    faits = _sibling_faits(head, git_dir, work_tree)
    assert faits is not None
    assert len(faits) == 18, f"expected 18 DONE items at HEAD, measured: {len(faits)} ({sorted(faits)})"


@pytest.mark.skipif(
    _SIBLING_NICHE_ABSENT, reason="the sibling project's nested repo is not present on this host"
)
def test_immobilite_sibling_sur_la_POPULATION_REELLE_se_mesure_pas_se_tait() -> None:
    """The real nested repo must be measurable -- ``None`` would be a regression of the edge, not
    a legitimate absence (the repo exists, `plan/` exists, `git grep` works)."""
    longue = immobilite_sibling(_REPO_ROOT)
    assert longue is not None, "the real population must be measured, not stay silent"
    assert longue.commits >= 1
