"""C6 -- the edge (git, I/O) of :mod:`mnemosyne.runtime.routage_journal_run`.

The pure part (:mod:`mnemosyne.production.routage_journal`) is tested separately
(`tests/orchestration/test_routage_journal.py`) -- here only what the edge ADDS: parsing a real
`git log`, and publishing through `make carte` with no new surface.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

from mnemosyne.runtime import routage_journal_run as rjr

from _invariants import REPO_ROOT


def _git(racine: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=racine, check=True, capture_output=True)


def _depot_avec_commits(racine: Path) -> None:
    """A disposable, REAL repo (not a hand-rolled string): three `type(IDENT):` commits, one of
    which carries two successive Co-Authored-By trailers (the last one must win), one that
    references NO ident at all (noise to ignore), and the chronological order must survive
    `git log`'s reversal."""
    _git(racine, "init", "-q")
    _git(racine, "config", "user.email", "t@t.t")
    _git(racine, "config", "user.name", "t")

    (racine / "a.py").write_text("1\n")
    _git(racine, "add", "a.py")
    _git(
        racine,
        "commit",
        "-q",
        "-m",
        "feat(X1): first round\n\nCo-Authored-By: Claude Opus 5 <noreply@anthropic.com>",
    )

    (racine / "b.py").write_text("2\n")
    _git(racine, "add", "b.py")
    _git(racine, "commit", "-q", "-m", "chore: a commit with no ident -- pure noise")

    (racine / "c.py").write_text("3\n")
    _git(racine, "add", "c.py")
    _git(
        racine,
        "commit",
        "-q",
        "-m",
        "fix(X1): second round\n\nCo-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>",
    )

    (racine / "d.py").write_text("4\n")
    _git(racine, "add", "d.py")
    _git(racine, "commit", "-q", "-m", "orch(X1): routing -- never a round")


def test_commits_par_ident_rend_None_sur_un_depot_ABSENT(tmp_path: Path) -> None:
    assert rjr.commits_par_ident(tmp_path / "n-existe-pas") is None


def test_commits_par_ident_parse_type_et_modele_ignore_le_bruit(tmp_path: Path) -> None:
    _depot_avec_commits(tmp_path)
    commits = rjr.commits_par_ident(tmp_path)
    assert commits is not None
    assert set(commits) == {"X1"}, "the chore: commit with no ident must create NO key at all"
    assert [c.type for c in commits["X1"]] == ["feat", "fix", "orch"], (
        "CHRONOLOGICAL order expected -- git log returns the most recent first, the edge must reverse it"
    )
    assert commits["X1"][0].modele == "Claude Opus 5"
    assert commits["X1"][1].modele == "Claude Sonnet 5"
    assert commits["X1"][2].modele == "", "orch(X1) has no Co-Authored-By in this fixture"


# ------------------------------------------------------------------------------------------------
# `commits_dates_par_ident` -- EXACT sister, EXPOSED under urgency (chat 1 blocked 73 min rather
# than duplicate `_SUJET_RE`). The git-log hub is SHARED (`_lire_commits`) -- these witnesses prove it.
# ------------------------------------------------------------------------------------------------


def test_commits_dates_par_ident_rend_None_sur_un_depot_ABSENT(tmp_path: Path) -> None:
    assert rjr.commits_dates_par_ident(tmp_path / "n-existe-pas") is None


def test_commits_dates_par_ident_rend_les_DATES_dans_le_MEME_ordre_CHRONOLOGIQUE(
    tmp_path: Path,
) -> None:
    _depot_avec_commits(tmp_path)
    dates = rjr.commits_dates_par_ident(tmp_path)
    assert dates is not None
    assert set(dates) == {"X1"}, "the chore: commit with no ident must create NO key here either"
    assert len(dates["X1"]) == 3, "the THREE X1 commits (feat/fix/orch), same population as the sister"
    assert list(dates["X1"]) == sorted(dates["X1"]), (
        "increasing CHRONOLOGICAL order expected -- same reversal as commits_par_ident"
    )


def test_commits_dates_et_commits_PARTAGENT_le_MEME_ident_le_MEME_bruit_ignore(
    tmp_path: Path,
) -> None:
    """The two views must agree on WHO exists and HOW MANY -- if they diverge, it is no longer a
    sister, it is a second reading that has already started to drift."""
    _depot_avec_commits(tmp_path)
    dates = rjr.commits_dates_par_ident(tmp_path)
    commits = rjr.commits_par_ident(tmp_path)
    assert dates is not None and commits is not None
    assert set(dates) == set(commits)
    for ident in dates:
        assert len(dates[ident]) == len(commits[ident]), (
            f"{ident}: {len(dates[ident])} dates vs {len(commits[ident])} commits"
        )


def test_sabotage_UNE_SEULE_regex_fait_tomber_les_DEUX_vues_a_ZERO(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """*I never assert the passing case.* A single sabotage of `_SUJET_RE` must turn BOTH
    `commits_par_ident` AND `commits_dates_par_ident` red together -- direct proof that a single
    hub feeds them both, never two readings of `git log` that could drift apart."""
    monkeypatch.setattr(rjr, "_SUJET_RE", re.compile(r"(?!)"))  # never matches
    assert rjr.commits_par_ident(REPO_ROOT) == {}
    assert rjr.commits_dates_par_ident(REPO_ROOT) == {}


def test_resume_NOMME_son_incapacite_quand_le_depot_est_ILLISIBLE(tmp_path: Path) -> None:
    """Fail-open, NAMES itself rather than raising -- a folder with no .git has no history, never
    an exception that would take `make carte` down with it."""
    vide = tmp_path / "vide"
    vide.mkdir()
    (vide / "docs").mkdir()
    (vide / "docs" / "PLAN.md").write_text("# PLAN\n\n## The items\n\n- **A1** \U00002B1C one.\n")
    texte = rjr.resume(vide)
    assert "NOT MEASURED" in texte


# ---- THE REAL THING: at least 10 items, as the clause requires ------------------------------
def test_sur_le_REEL_le_journal_rend_AU_MOINS_10_items_mesures() -> None:
    """C6's *Fini quand*, word for word: "on at least 10 genuinely executed items". Locks in a
    FLOOR, not an exact count -- the plan keeps closing items under this witness."""
    commits = rjr.commits_par_ident(REPO_ROOT)
    assert commits is not None
    from mnemosyne.production.plan_registry import scan_plans
    from mnemosyne.production.routage_journal import journal

    projet = next(
        p for p in scan_plans(REPO_ROOT).projects if p.plan_path.parent == REPO_ROOT / "docs"
    )
    j = journal(projet.reading.items, REPO_ROOT, commits)
    assert len(j) >= 10, f"only {len(j)} measurable items -- the clause requires 10"


def test_sur_le_REEL_les_quatre_cases_sont_publiees_par_make_carte() -> None:
    texte = rjr.resume(REPO_ROOT)
    for case in ("sous_agent", "le_parc", "sous_agent_capable", "le_chat_d_arc"):
        assert case in texte, f"case {case!r} missing from the render -- publish it at n=0, don't omit it"


def test_sabotage_un_SUJET_RE_qui_ne_matche_RIEN_fait_tomber_le_compte_a_ZERO(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """*I never assert the passing case*: the 25 (or more) measured on the real thing is only
    proof if disarming it genuinely brings it down. Sabotage the regex, replay on the SAME real
    repo."""
    monkeypatch.setattr(rjr, "_SUJET_RE", __import__("re").compile(r"(?!)"))  # never matches
    commits = rjr.commits_par_ident(REPO_ROOT)
    assert commits == {}, "regex sabotaged -- no commit should attach to an ident anymore"


def test_commits_par_ident_EST_PUBLIQUE_un_second_appelant_peut_l_importer() -> None:
    """D5 (`production/plan_recul.py`, signal 3) is waiting to import this function rather than
    duplicate the `type(IDENT):` convention -- an underscore-prefixed name would have forbidden it."""
    assert not rjr.commits_par_ident.__name__.startswith("_")
    from mnemosyne.runtime.routage_journal_run import commits_par_ident as importee_par_son_nom_public

    assert importee_par_son_nom_public is rjr.commits_par_ident


# ------------------------------------------------------------------------------------------------
# REAL DEFECT confirmed on 2026-08-16: _SUJET_RE missed every hyphenated ident (150/288, 52% on
# another private project). Fixed; these witnesses prove the fix on REAL DATA, not a fixture.
# ------------------------------------------------------------------------------------------------


def _depot_avec_ident_a_tiret(racine: Path) -> None:
    """A disposable repo carrying ONE `feat(A01-1):` commit -- the exact shape that was missed
    before the fix (letters, digits, HYPHEN, digits), next to an ident WITHOUT a hyphen to prove
    the fix ADDS a shape, it removes none."""
    _git(racine, "init", "-q")
    _git(racine, "config", "user.email", "t@t.t")
    _git(racine, "config", "user.name", "t")
    (racine / "a.py").write_text("1\n")
    _git(racine, "add", "a.py")
    _git(racine, "commit", "-q", "-m", "feat(A01-1): hyphenated ident, digits on both sides")
    (racine / "b.py").write_text("2\n")
    _git(racine, "add", "b.py")
    _git(racine, "commit", "-q", "-m", "fix(P6): ident without a hyphen, already recognised before")


def test_commits_par_ident_RECONNAIT_desormais_un_ident_A_TIRET(tmp_path: Path) -> None:
    """The exact shape of the confirmed defect: `A01-1` (seen on another private project) was
    missed because of the hyphen alone."""
    _depot_avec_ident_a_tiret(tmp_path)
    commits = rjr.commits_par_ident(tmp_path)
    assert commits is not None
    assert set(commits) == {"A01-1", "P6"}, (
        f"both idents must be recognised, hyphen or not; got {set(commits)}"
    )


def test_le_CORRECTIF_ne_RETIRE_aucune_forme_deja_reconnue(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """*I never assert the passing case*: replay the SAME repo with the OLD pattern (without the
    optional hyphen) and confirm it already recognised `P6` -- the fix ADDS a shape, it replaces
    none. The reverse of the usual sabotage: here the old pattern is restored to prove it was not
    totally broken, only incomplete."""
    ancien = re.compile(r"^(feat|fix|test|docs|plan|orch)\(([A-Za-z]{1,4}\d+)\):")
    monkeypatch.setattr(rjr, "_SUJET_RE", ancien)
    _depot_avec_ident_a_tiret(tmp_path)
    commits = rjr.commits_par_ident(tmp_path)
    assert commits is not None
    assert set(commits) == {"P6"}, (
        f"the old pattern must miss A01-1 (that is the confirmed defect) and keep P6; got {set(commits)}"
    )


def test_sur_le_REEL_le_correctif_du_TIRET_recupere_des_commits_MNEMOSYNE_aussi() -> None:
    """The defect was not specific to that other project: measured directly on THIS repo, `git log`, that the
    old pattern (without a hyphen) already undercounted ITS OWN history (`C20-1`, etc.)."""
    ancien = re.compile(r"^(feat|fix|test|docs|plan|orch)\(([A-Za-z]{1,4}\d+)\):")
    sortie = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "log", "--format=%s"],
        capture_output=True,
        text=True,
        check=True,
    )
    sujets = sortie.stdout.splitlines()
    avec_ancien = sum(1 for s in sujets if ancien.match(s))
    avec_nouveau = sum(1 for s in sujets if rjr._SUJET_RE.match(s))
    assert avec_nouveau > avec_ancien, (
        f"the fixed pattern must recognise STRICTLY more subjects than the old one on this repo's "
        f"real history ({avec_nouveau} vs {avec_ancien}) -- otherwise the hyphen never appears in "
        f"OUR OWN convention, and the other project's measurement would be an isolated case"
    )


def test_sur_un_AUTRE_DEPOT_le_correctif_recupere_AU_MOINS_LA_MOITIE_des_commits_type() -> None:
    """The population that named the defect (another private project's own `git log`, not a
    fixture) -- locks in a proportional FLOOR, never the exact count: that project's history
    keeps growing under this witness. Measured at the time of writing: 288 `type(...)` commits,
    174 recognised by the fixed pattern (the old one would have recognised only 24 -- 150
    invisible from the hyphen alone, 52%).

    TODO(public-mirror): needs human review -- this measurement depends on a private sibling
    repository that is not part of this public mirror and has no disposable-fixture equivalent
    (a synthetic repo cannot reproduce a 200+ commit floor); skipped here rather than pointing
    the check at a path this export does not ship."""
    pytest.skip("depends on a private sibling repository outside this public mirror")
