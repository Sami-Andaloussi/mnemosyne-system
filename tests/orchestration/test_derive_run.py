# SPDX-License-Identifier: MIT
"""The EDGE of `D1` — the one that opens `git`, where the judge itself reads nothing.

 These witnesses exist because the edge is NEW code that opens a subprocess and parses its
output: the three places where a measurement dies in silence. *A pure judge is tested by its
values; an edge is tested by what it does when the world does not answer.*
"""

from __future__ import annotations

from pathlib import Path

import pytest

import re
import subprocess
import tempfile
from unittest.mock import patch

from mnemosyne.production.plan_derive import Tour
from mnemosyne.runtime.derive_run import (
    DOSSIERS_PRODUIT,
    NOM_PRODUIT,
    RACINE_PRODUIT,
    _degnome,
    _pourcentages_distincts,
    _texte_non_nul,
    est_produit,
    lire_tours,
    population_disparue,
    predicat_produit,
    resume,
    resume_recent,
)


@pytest.mark.parametrize("dossier", DOSSIERS_PRODUIT)
def test_les_SIX_dossiers_declares_comptent_TOUS_comme_produit(dossier):
    """ **Six, not five.** `D2`: this FROZEN predicate is the population that validated `(c1)` —
 it no longer drives the measurement IN PROGRESS (see :func:`predicat_produit` below), but a
 historical verdict is never re-measured over a population that has moved under it, so it stays
 tested unchanged, injected explicitly everywhere `(c1)` is replayed."""
    assert est_produit(f"{RACINE_PRODUIT}{dossier}a/file.py")


def test_le_predicat_REFUSE_ce_que_CONCEPTION_ne_declare_pas():
    """ The half every predicate is missing: *test DIFFERENTIATION, not conformity.* An
 `est_produit` that always returned `True` would pass the witness above six times running."""
    assert not est_produit(f"{RACINE_PRODUIT}tooling/x.py"), "a 7th folder is not declared"
    assert not est_produit(f"{RACINE_PRODUIT}CONCEPTS.md"), "the bare root is not product"
    assert not est_produit("trading/widget/x.py"), "`widget/` outside the root is not product"
    assert not est_produit("saas/Other Project/widget/x.py"), "a DIFFERENT root is not product"


# ------------------------------------------------------------------------------------------------
# D2 — THE PRODUCT IS DECLARED BY THE PROJECT, NEVER HARDCODED: predicat_produit() reads PRODUIT.md
# ------------------------------------------------------------------------------------------------


def test_predicat_produit_rend_None_quand_RIEN_n_est_declare(tmp_path: Path):
    """ **`D2`'s clause, word for word**: a project that declares nothing receives the
 measurement DISABLED and NAMED — never a permissive predicate, never a predicate that refuses
 everything (both would be a FALSE number). ``None`` is the only honest answer to "nothing is
 declared"."""
    predicat, motifs = predicat_produit(tmp_path)
    assert predicat is None
    assert motifs == ()


def test_predicat_produit_LIT_la_declaration_a_cote_de_la_porte(tmp_path: Path):
    """The file lives at `projects/<RACINE_PRODUIT>/PRODUIT.md` — the same convention as this
    repository's own PEREMPTION doc (beside the plan's gate, never inside it: `*Produit*` is
    already taken there)."""
    dossier = tmp_path / "projects" / RACINE_PRODUIT
    dossier.mkdir(parents=True)
    (dossier / NOM_PRODUIT).write_text("- widget/\n- core/\n", encoding="utf-8")
    predicat, motifs = predicat_produit(tmp_path)
    assert predicat is not None
    assert motifs == ("widget/", "core/")
    assert predicat(f"{RACINE_PRODUIT}widget/x.py")
    assert not predicat(f"{RACINE_PRODUIT}engine/x.py"), "engine/ is NOT in THIS declaration"
    assert not predicat("elsewhere/widget/x.py"), "outside the declared root, the same pattern does not count"


def test_predicat_produit_UN_FICHIER_VIDE_est_une_DECLARATION_pas_une_ABSENCE(tmp_path: Path):
    """ **An absent file and an empty file are TWO different states.** A ``PRODUIT.md`` that
 exists but lists no pattern explicitly says "nothing, here, is product" — this is NOT the
 same answer as "the project has declared nothing", and conflating the two would be exactly the
 defect `Tour.faits` (``None`` vs ``frozenset()``) exists to avoid, one level up in this
 module."""
    dossier = tmp_path / "projects" / RACINE_PRODUIT
    dossier.mkdir(parents=True)
    (dossier / NOM_PRODUIT).write_text("", encoding="utf-8")
    predicat, motifs = predicat_produit(tmp_path)
    assert predicat is not None, "an EMPTY file is a declaration, not an absence"
    assert motifs == ()
    assert not predicat(f"{RACINE_PRODUIT}widget/x.py"), "no pattern declared: nothing is product"


def test_resume_NOMME_l_absence_de_declaration_plutot_que_de_deviner(tmp_path: Path):
    """`D2`, on the surface side: the `(a)`/`(b)` page must say "product not declared", not stay
    silent nor fall back on a hardcoded taxonomy — on a repository with NEITHER git NOR a
    declaration, it is the first refusal (`DEPOT` absent) that speaks, so this witness builds a
    minimal `.git` to reach the "product not declared" branch specifically."""
    depot = tmp_path / "projects" / ".git"
    depot.mkdir(parents=True)
    with patch("mnemosyne.runtime.derive_run.lire_tours", return_value=[Tour("a", "2026-08-01", ())]):
        page = resume(tmp_path, aujourdhui="2026-08-01")
    assert "PRODUCT SHARE NOT MEASURED" in page
    assert "PRODUIT.md" in page
    assert "%" not in page, "no percentage may come out of a disabled measurement"


def test_les_chemins_ENTRE_GUILLEMETS_sont_denudes():
    """ **65 paths out of 4,448 come out quoted** in the real population (the ones carrying a
 special character). Without this stripping, none would be recognized by the predicate: they
 would all fall on the "machinery" side **in silence**, and the product share would be
 published too low with no error ever appearing. *The silent loss lives where the FORM
 changes.*"""
    assert _degnome('"trading/FACTORY, Notion/x.md"') == "trading/FACTORY, Notion/x.md"
    assert _degnome("saas/a.py") == "saas/a.py", "a bare path must not be amputated"
    assert _degnome('"') == '"', "a SINGLE quote is not a pair — do not eat it"
    assert _degnome("") == ""


def test_un_depot_ABSENT_rend_None_et_JAMAIS_une_liste_vide(tmp_path: Path):
    """ *Two absences of measurement compare equal.* A window with no commit and an unreadable
 repository must read differently — otherwise the page publishes "no drift" when the truth is
 "I could not look", and that is how a detector dies without ever turning red."""
    assert lire_tours(tmp_path) is None


def test_le_resume_NOMME_son_incapacite_a_mesurer(tmp_path: Path):
    """ The edge does NOT stay silent when it fails: the output IS the surface (level 1). 
 Measured live: this behavior caught a wiring bug **within its first minute** — the map was
 passing `docs/` instead of the root, and the page screamed instead of rendering an empty
 section.

 **`tmp_path` (the path PYTEST manufactures, not `resume()`) can itself contain a
 digit** — its folder counter (`pytest-2857`, …) sometimes lands on a substring like
 `"85"`. Judging a bare substring over the WHOLE sentence confuses this harness noise with a
 real measurement number: the witness would no longer be measuring `resume()`, it would be
 measuring pytest's counter. So the injected path is stripped out BEFORE judging, and what
 remains must carry NO digit at all — the SHAPE of the claim ("zero digit outside the path"),
 not a value chosen at random."""
    phrase = resume(tmp_path, aujourdhui="2026-08-01")
    assert "NOT MEASURED" in phrase
    assert "could not look" in phrase, "the difference must be STATED, not merely known"
    hors_chemin = phrase.replace(str(tmp_path), "")
    assert not re.search(r"\d", hors_chemin), (
        "no measurement digit may come out of a measurement never taken -- "
        f"found outside the repository's path in {hors_chemin!r}"
    )


@pytest.mark.skipif(
    not (Path(__file__).resolve().parents[2] / "projects/.git").exists(),
    reason="the real population for (c1) is not present on this host",
)
def test_sur_la_POPULATION_REELLE_la_bascule_du_21_juillet_SORT():
    """ **`(c1)`, run through a COMMAND, over the history the clause names.**

 This is the only witness in this file that touches the real thing, and it is the one that says
 whether `D1` holds: the clause requires **finding the July 21 tipping point without being
 handed it**, over `projects/.git`, the July 15-29 window, the `PAR_FICHIER` unit, the
 six-folder predicate.

 **It is `skipif`, and that is a DECLARED weakness**: `projects/` is gitignored, so this
 witness proves nothing on a host that does not carry the data. *A skipped witness is not a
 green witness* — it says so rather than rendering an empty green.
 """
    racine = Path(__file__).resolve().parents[2]
    tours = lire_tours(racine)
    assert tours is not None and len(tours) == 255, f"declared population: 255 commits, {tours=}"
    assert tours[0].date < tours[-1].date, "the series must read in TIME ORDER"
    assert all(t.faits is None for t in tours), (
        "git knows NOTHING about the plan's \U00002705 steps: non-null `faits` here would publish a "
        "manufactured stillness — \"N commits without a single identifier changing\", a sibling project's exact "
        "failure"
    )
    # D2: the FROZEN predicate is INJECTED explicitly — without it, `resume()` reads `PRODUIT.md`
    # (absent for the sibling project today) and would render "PRODUCT SHARE NOT MEASURED", not the tipping point.
    # A historical verdict is replayed over ITS population, never over what the disk carries TODAY.
    # `aujourdhui` is FROZEN (not `date.today()`): a historical verdict must replay identically
    # no matter which day this witness is run -- same discipline as `resume_recent` below.
    page = resume(racine, aujourdhui="2026-07-29", est_produit=est_produit)
    assert "2026-07-20 → 2026-07-21" in page, f"the declared tipping point does not come out:\n{page}"
    assert "85.6%" in page, "July 20 must render 85.6% (the plan publishes 85.8%)"
    assert "last measured day:" in page and "repository read:" in page, (
        f"the age and the repository must be NAMED, not just the content:\n{page}"
    )


# --------------------------- population_disparue: does the repository READ still carry the project? ---


def test_population_disparue_est_FAUX_sur_un_depot_ABSENT(tmp_path: Path):
    """A git invocation error must not disguise itself as a "vanished" verdict — same rule as
    `lire_tours`: an execution uncertainty and a measured fact do not read the same."""
    assert population_disparue(tmp_path) is False


@pytest.mark.skipif(
    not (Path(__file__).resolve().parents[2] / "projects/.git").exists(),
    reason="the real population is not present on this host",
)
def test_population_disparue_VRAI_pour_le_sibling_FAUX_pour_un_projet_encore_PRESENT():
    """ The exact scene measured by the orchestrator probe, 2026-08-17: a sibling project migrated to its
 own repository on 2026-07-29 ("one project, one repository") — `projects/.git` no longer
 carries ANY file under its root, while ANOTHER real project of the same repository is still
 present there. A witness that only ever triggered the TRUE branch would prove nothing:
 `population_disparue` could return `True` UNCONDITIONALLY and still pass."""
    racine = Path(__file__).resolve().parents[2]
    assert population_disparue(racine) is True, (
        "The sibling project has migrated — projects/.git no longer carries anything under its root, measured "
        "with `git --git-dir=projects/.git ls-files` under that project's former root"
    )
    assert population_disparue(racine, racine="trading/example_research") is False, (
        "trading/example_research is a real project still present in projects/.git — the witness must "
        "NOT say \"vanished\" for it"
    )


# ------------------------------------------------------------------------------------------------
# THE LIVE WINDOW — the one the TICK watches, distinct from `(c1)`'s frozen window
# ------------------------------------------------------------------------------------------------


def test_la_fenetre_RECENTE_est_SILENCIEUSE_quand_rien_n_a_bouge(tmp_path: Path):
    """ **Silence is a STATE, not a defect — and the distinction has been paid for in this
 repository.**

 *A clause with no caller looks like a satisfied clause; a clause with no population looks
 like a clause that is asleep.* The first is a defect, the second a fact. Here: no repository,
 hence no population, hence `None` — and the tick publishes nothing."""
    assert resume_recent(tmp_path, aujourdhui="2026-08-15") is None


@pytest.mark.skipif(
    not (Path(__file__).resolve().parents[2] / "projects/.git").exists(),
    reason="the real population is not present on this host",
)
def test_la_fenetre_RECENTE_PARLE_des_qu_elle_porte_une_chute():
    """ **BOTH HALVES, or the witness above measures its own silence.** A `resume_recent`
 that returned `None` **no matter what it is given** would pass the previous witness while
 proving nothing. So the same function is run on a date where the window does carry commits.

 And this is the same measurement `make carte` publishes over the frozen window — *the same
 judge, two populations* — exactly what a judge with an INJECTED population makes possible."""
    racine = Path(__file__).resolve().parents[2]
    aujourd_hui = resume_recent(racine, aujourdhui="2026-08-15", est_produit=est_produit)
    assert aujourd_hui is None, "nothing has been committed since 2026-07-29: the tick must stay silent"

    # D2: FROZEN predicate injected — see the note on `resume()`'s witness above.
    peuplee = resume_recent(racine, aujourdhui="2026-07-29", est_produit=est_produit)
    assert peuplee is not None, "a window carrying 255 commits cannot be mute"
    assert "2026-07-20 to 2026-07-21" in peuplee, f"the tipping point must be named: {peuplee}"
    assert "point(s)" in peuplee, "the drop is published IN POINTS, never as a fraction"


def test_le_CABLAGE_du_tick_fait_REMONTER_la_derive(tmp_path: Path, monkeypatch):
    """ **THIS SOURCE WILL STAY SILENT FOR THE FORESEEABLE FUTURE** — the watched repository
 has been frozen since 2026-07-29. Nothing, therefore, would distinguish a `derive_resume=`
 that was **never wired at all** from correct wiring: both render an identical tick,
 indefinitely. This witness is the only thing that holds the difference. *A silent source is
 indistinguishable from a source that was never wired.*"""
    from mnemosyne.runtime import tick as tick_mod

    def propositions():
        return tick_mod.run_tick(knowledge_root=tmp_path, repo_root=tmp_path)

    assert not any("product share" in p.summary for p in propositions()), (
        "without a watched repository, the source must stay SILENT"
    )

    monkeypatch.setattr(
        tick_mod, "resume_recent", lambda _r, **_k: "A sibling project's product share dropped by 38 point(s)"
    )
    remontees = [p.summary for p in propositions() if "product share" in p.summary]
    assert remontees, "the drift must SURFACE through the proposer, not only through the judge"


# ------------------------------------------------------------------------------------------------
# THE TWO DEFECTS FROM CHAT 3'S AUDIT (13:40, RESERVATIONS verdict) — reproduced, then closed
# ------------------------------------------------------------------------------------------------


def test_DA_une_chute_SOUS_le_point_ne_s_arrondit_PLUS_a_zero():
    """ **D-A, found by chat 3's isolated audit.** The calculation was honest
 (`plus_grande_chute` only requires `ampleur > 0`); the RESTITUTION was lying: `:.0f` rounded
 points to the nearest integer, so a 0.3-point drop displayed as *"0 point(s) dropped
 (100% -> 100%)"* — a sentence that asserts an event and shows two IDENTICAL numbers.

 *A line announcing a drop must be able to SHOW it.* Reproduced with the REAL function
 (`lire_tours` mocked, never git) — exactly the audit's fixture."""
    produit = ("saas/Sibling Research/sibling/a.py",)
    hors = ("tooling/x.py",)
    j1 = [Tour(f"a{i}", "2026-08-01", produit) for i in range(999)] + [Tour("a999", "2026-08-01", hors)]
    j2 = [Tour(f"b{i}", "2026-08-02", produit) for i in range(996)] + [
        Tour(f"b{i}", "2026-08-02", hors) for i in range(996, 1000)
    ]
    # D2: `repo_root=None` -- without an injected predicate, `predicat_produit(None)` would
    # crash on `None / "projects"`. The FROZEN predicate ((c1)'s population) matches the fixture's
    # paths (`saas/Sibling Research/sibling/…` vs `tooling/…`), so that is what gets injected.
    with patch("mnemosyne.runtime.derive_run.lire_tours", return_value=j1 + j2):
        phrase = resume_recent(None, aujourdhui="2026-08-02", est_produit=est_produit)
    assert phrase is not None
    assert "0.3 point" in phrase, f"the real magnitude (0.3 point) must survive rounding: {phrase}"
    assert "99.9%" in phrase and "99.6%" in phrase, f"the two percentages must DIFFER: {phrase}"


def _depot_avec_un_vrai_merge(racine):
    """A repository where a PRODUCT file exists ONLY in a merge's resolution — absent from BOTH
    parents. This is the audit's exact fixture."""
    def git(*a):
        subprocess.run(["git", *a], cwd=racine, check=True, capture_output=True)

    git("init", "-q")
    git("config", "user.email", "t@t.t")
    git("config", "user.name", "t")
    (racine / "a.py").write_text("1\n")
    git("add", "a.py")
    git("commit", "-q", "-m", "base")
    git("checkout", "-q", "-b", "branch")
    (racine / "b.py").write_text("2\n")
    git("add", "b.py")
    git("commit", "-q", "-m", "branch")
    ref = subprocess.run(
        ["git", "symbolic-ref", "--short", "HEAD"], cwd=racine, capture_output=True, text=True
    ).stdout.strip()
    git("checkout", "-q", "-")
    (racine / "c.py").write_text("3\n")
    git("add", "c.py")
    git("commit", "-q", "-m", "main")
    subprocess.run(
        ["git", "merge", "--no-ff", "-q", "-m", "merge", ref], cwd=racine, capture_output=True
    )
    (racine / "resolution.py").write_text("4\n")  # created INSIDE the resolution -- absent from both parents
    git("add", "resolution.py")
    git("commit", "-q", "--amend", "--no-edit")


def test_DB_un_fichier_PRODUIT_dans_un_MERGE_n_est_plus_invisible():
    """ **D-B, FIRST PASS (chat 3's isolated audit).** `git log --numstat` WITHOUT `-m` renders
 **no line at all** for a merge commit — a file genuinely written, created INSIDE a merge's
 resolution, **existed nowhere** in the series. Measured on the real population:
 `projects/.git` carries 0 merges today — zero impact, a LATENT hole.

 **3 turns, not 4** — since the `--first-parent` fix (2nd pass, see below), the `branch`
 commit is no longer visited AS A SEPARATE TURN: it is not on the main line. Its content
 (`b.py`) remains visible, carried by the MERGE's turn."""
    with tempfile.TemporaryDirectory() as td:
        racine = Path(td)
        _depot_avec_un_vrai_merge(racine)
        with patch("mnemosyne.runtime.derive_run.DEPOT", ".git"):
            tours = lire_tours(racine, depuis="2020-01-01", jusqua="2030-01-01")
    assert tours is not None
    assert len(tours) == 3, f"3 turns on the main line (base, main, merge): {[t.sha[:8] for t in tours]}"
    assert len({t.sha for t in tours}) == 3, "no sha may appear twice"
    assert any("resolution.py" in t.chemins for t in tours), "the merge's content must BE VISIBLE"
    assert any("b.py" in t.chemins for t in tours), "the merged branch's content must REMAIN visible"
    fusion = next(t for t in tours if "resolution.py" in t.chemins)
    assert len(fusion.chemins) == len(set(fusion.chemins)), "no path may repeat"
    assert len(fusion.lignes) == len(fusion.chemins), "lignes must stay ALIGNED with chemins"


def _depot_avec_un_merge_PROPRE(racine):
    """A merge WITHOUT conflict: `gros.py` comes entirely from the branch, nothing is resolved on
    main. This is the ORDINARY case, not the previous fixture's conflict resolution."""
    def git(*a):
        subprocess.run(["git", *a], cwd=racine, check=True, capture_output=True)

    git("init", "-q")
    git("config", "user.email", "t@t.t")
    git("config", "user.name", "t")
    (racine / "a.py").write_text("1\n")
    git("add", "a.py")
    git("commit", "-q", "-m", "base")
    git("checkout", "-q", "-b", "branch")
    (racine / "gros.py").write_text("2\n")
    git("add", "gros.py")
    git("commit", "-q", "-m", "add gros.py")
    ref = subprocess.run(
        ["git", "symbolic-ref", "--short", "HEAD"], cwd=racine, capture_output=True, text=True
    ).stdout.strip()
    git("checkout", "-q", "-")
    (racine / "c.py").write_text("3\n")
    git("add", "c.py")
    git("commit", "-q", "-m", "main moves forward")
    subprocess.run(
        ["git", "merge", "--no-ff", "-q", "-m", "clean merge", ref], cwd=racine, capture_output=True
    )


def test_DB_TROISIEME_passe_un_MERGE_PROPRE_ne_DOUBLE_COMPTE_plus_son_contenu():
    """ **D-B, THIRD PASS (chat 3, second re-run) — my 1st D-B fix opened a NEW window, on
 the ORDINARY case rather than the rare one.**

 `-m` alone diffs a merge against EACH parent. For a merge WITHOUT conflict (the most common
 case — a branch merged cleanly), the branch's content then appeared **TWICE**: once via the
 original commit on the branch (seen by `--all`), once via the merge's diff against the parent
 that did not have it (seen by `-m`). *A population counted twice is no longer a population,
 it is a bias.*

 **The previous fix (dedup by path, PER SHA) could not see this one**: the duplicate lives
 HERE between TWO different shas (the branch commit and the merge commit), not inside a single
 one. Closed by `--first-parent`: we walk the MAIN line of history, the branch commit is no
 longer visited as a separate turn — its content only ever crosses through the merge that
 integrated it."""
    with tempfile.TemporaryDirectory() as td:
        racine = Path(td)
        _depot_avec_un_merge_PROPRE(racine)
        with patch("mnemosyne.runtime.derive_run.DEPOT", ".git"):
            tours = lire_tours(racine, depuis="2020-01-01", jusqua="2030-01-01")
    assert tours is not None
    occurrences = sum(1 for t in tours for c in t.chemins if c == "gros.py")
    assert occurrences == 1, f"gros.py must appear EXACTLY ONCE, found {occurrences}: {tours}"
    assert len(tours) == 3, f"3 turns on the main line (base, main, merge): {[t.sha[:8] for t in tours]}"


def test_DB_la_population_REELLE_est_INCHANGEE_par_first_parent():
    """ `--first-parent` replaces `--all`: verify that the population `(c1)` names (255
 commits) does NOT move — `projects/.git` carries only one ref (`main`), so the two traversals
 coincide. *A change of traversal must be measured on the real thing, not assumed.*"""
    racine = Path(__file__).resolve().parents[2]
    if not (racine / "projects/.git").exists():
        pytest.skip("the real population is not present on this host")
    tours = lire_tours(racine, depuis="2026-07-15", jusqua="2026-07-30")
    assert tours is not None and len(tours) == 255, f"declared population: 255 commits, {tours=}"


# ------------------------------------------------------------------------------------------------
# D-A, SECOND PASS — the orchestrator's 2nd verdict: the 1st fix moved a THRESHOLD
# ------------------------------------------------------------------------------------------------


def test_DA_le_PREMIER_correctif_deplacait_un_SEUIL_pas_ferme_la_CLASSE():
    """ **The 1st fix (`:.0f` -> `:.1f`) closed the CASE measured by the audit, not the
 CLASS.** The orchestrator's second verdict measured it exactly: `ampleur = 0.040 point` —
 BELOW the new 0.05 threshold — still displayed as *"0.0 point(s) (100.0% -> 100.0%)"*.

 *A fix that moves a threshold closes the case and leaves the class open.* Reproduced with
 the orchestrator's EXACT fixture (10,000 turns, 100.00% -> 99.96%): the class MUST hold here,
 or the 3rd fix is just a 4th threshold."""
    produit = ("saas/Sibling Research/sibling/a.py",)
    hors = ("tooling/x.py",)
    j1 = [Tour(f"a{i}", "2026-08-01", produit) for i in range(10000)]
    j2 = [Tour(f"b{i}", "2026-08-02", produit) for i in range(9996)] + [
        Tour(f"b{i}", "2026-08-02", hors) for i in range(9996, 10000)
    ]
    # D2: same injection as the previous D-A witness -- see its note.
    with patch("mnemosyne.runtime.derive_run.lire_tours", return_value=j1 + j2):
        phrase = resume_recent(None, aujourdhui="2026-08-02", est_produit=est_produit)
    assert phrase is not None
    assert "0.04 point" in phrase, f"the 0.040-point magnitude must survive: {phrase}"
    assert "100.00%" in phrase and "99.96%" in phrase, f"the percentages must DIFFER: {phrase}"


@pytest.mark.parametrize("ampleur_fraction", [0.5, 0.01, 0.001, 0.0001, 0.00001, 1e-9])
def test_DA_AUCUNE_precision_fixe_ne_peut_refermer_la_classe(ampleur_fraction):
    """ **The general property, not one more point.** The disagreement was between the
 condition that produces the object (`ampleur > 0`, strictly) and a FIXED display precision — a
 fix that picks ONE more digit recreates the same class one level lower. This witness sweeps
 six orders of magnitude, down to `1e-9`, and demands the property EVERY time: never
 "0 point(s)", never two identical percentages."""
    avant = 0.99999999
    apres = avant - ampleur_fraction
    assert apres > 0, "degenerate fixture"
    points = _texte_non_nul((avant - apres) * 100)
    avant_txt, apres_txt = _pourcentages_distincts(avant, apres)
    assert float(points) != 0, f"ampleur={ampleur_fraction} renders '{points}' — still zero"
    assert avant_txt != apres_txt, f"ampleur={ampleur_fraction} : {avant_txt} == {apres_txt}"


def test_DA_texte_non_nul_est_borne_et_JAMAIS_infini():
    """ The termination guard: the safety net at `max_decimales` must TRIGGER on a float that is
 strictly positive but indistinguishable from zero at any useful precision, without looping
 forever."""
    assert _texte_non_nul(1e-300, max_decimales=6) == "0.000000"
    assert _texte_non_nul(5.0, max_decimales=6) == "5.0"
