"""``I2`` — the harvest's trigger: what makes it BITE, and what it will never say.

**THE MEASUREMENT THAT GOVERNS THIS FILE, AND IT IS PUBLISHED**: as of 2026-08-15, the sibling project carries
**14 arcs and NONE is closed** (`0/14`, predicate `status == "fait"` over every item of an arc). A
suite that merely pulled the judge over the real tree would therefore return **green without
judging anything** — *a judge that goes fetch its own population can find it empty and hand down a
green.*

**So the population is INJECTED, and it has the SHAPE of the real thing**: the decisive witnesses
start from the sibling project's REAL arcs and close one of them, rather than from an invented fixture. What the
judge sees has the size, the identifiers, and the distribution of the real plan.

**AND NO WITNESS HERE ASSERTS "0 closed arcs"**: that would freeze the sibling project's state inside my suite,
and turn red the day an arc closes **for real** — which is to say exactly the day this trigger
starts to matter.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from mnemosyne.production import moisson_due as md
from mnemosyne.production.moisson_due import (
    NOMS_MAX,
    ArcVu,
    arcs_a_moissonner,
    arcs_moissonnes,
    candidats_sans_panne,
    est_ferme,
    moissons_sans_panne,
    resume,
    resume_candidats,
)
from mnemosyne.production.plan_registry import read_plan_tree

REPO = Path(__file__).resolve().parents[2]
# This whole file's decisive witnesses deliberately read a REAL project tree that lives under
# `projects/`, a root entirely outside this mirror's shipped content. That is a documented design
# choice of this file (see the module docstring above: population INJECTED with the shape of the
# real thing, never a fabricated fixture), not something a translation/redaction pass can safely
# rewrite into a synthetic fixture without risking a silently different test. The STRUCTURE is left
# exactly as in the source and only the codename is sanitised.
#
# THE NAME BELOW IS A SANITISED STAND-IN, AND IT THEREFORE NAMES NO FILE ON ANY DISK — not on a
# reader's, not on the author's. In the source repository this constant points at a real directory;
# the sanitising pass substitutes the project's codename, so the path it builds here is a
# well-formed string that resolves nowhere. Measured 2026-09-09 on this distribution:
# `find projects -type f` returns exactly ONE entry, `projects/README.md` (`.gitignore`: `projects/*`
# with `!projects/README.md`), so the corpus is absent BY DESIGN and absent from every fresh clone.
SIBLING = REPO / "projects" / "saas" / "Sibling Research"

#: **THE DEPENDENCY, DECLARED RATHER THAN ASSUMED.** Before this predicate existed, the four
#: corpus-reading witnesses below simply assumed the tree was there and fell over when it was not:
#: two on `assert reels` / `reels[0]` (an empty walk, then an `IndexError`), two on
#: `shutil.copy2(SIBLING / "PLAN.md", …)` raising `FileNotFoundError`. A red that says
#: "No such file or directory" about a path that CANNOT exist here is not a defect report, it is
#: the suite claiming a corpus it never shipped.
#:
#: **Option (a) — deriving the population from what is really on disk — was measured and REJECTED.**
#: What is really on disk here is `projects/README.md` and nothing else: a derived population would
#: hold ZERO arcs, `arcs_a_moissonner(())` returns `()`, and every assertion below about "a closed
#: arc is NAMED" would pass over an empty set. That is precisely the failure this file was written
#: to prevent — its own docstring says it in plain words: *"a judge that goes fetch its own
#: population can find it empty and hand down a green"*. Turning four honest reds into four vacuous
#: greens is a worse lie than the one being fixed. Option (b), the skip, is what the four sibling
#: files of this same suite already do (`test_derive_run.py`, `test_plancher_run.py`,
#: `test_plan_recul_run.py`, `test_plan_recul_signal1.py` all guard on a `projects/` predicate);
#: this file was the only one of the six the pass missed.
#:
#: The predicate asks ONLY "is the corpus shipped at all", never "is it intact": if `PLAN.md` is
#: present but the arc the end-to-end witnesses copy has been renamed, those witnesses must still
#: REDDEN on the author's disk. A skip that widened to cover rot would silence the very drift these
#: tests exist to catch.
SIBLING_CORPUS_ON_DISK: bool = (SIBLING / "PLAN.md").is_file()

needs_sibling_corpus = pytest.mark.skipif(
    not SIBLING_CORPUS_ON_DISK,
    reason=(
        "this distribution does not ship a project corpus: the witness tree "
        f"`{SIBLING.relative_to(REPO)}/PLAN.md` is absent, and `projects/` is gitignored by design "
        "(`projects/*`, `!projects/README.md`), hence empty in every fresh clone. The name is "
        "moreover a SANITISED stand-in for a private project, so it resolves on no disk at all, "
        "the author's included. Skipped, never silently passed: an unjudged population is not a "
        "safe population."
    ),
)

#: The witnesses the marker above is allowed to silence — **the SET, frozen, never a count.** A skip
#: that grows by one name nobody wrote down is how an exemption stops being an exemption and becomes
#: a habit.
CORPUS_WITNESSES: frozenset[str] = frozenset(
    {
        "test_sur_les_arcs_REELS_du_sibling_un_arc_ferme_est_NOMME",
        "test_le_meme_arc_reel_DEJA_moissonne_retombe_dans_le_silence",
        "test_de_BOUT_EN_BOUT_un_arc_REEL_du_sibling_ferme_produit_la_moisson",
        "test_le_CABLAGE_du_proposeur_fait_REMONTER_la_moisson_due",
    }
)


def test_le_SAUT_du_corpus_est_ANCRE_AU_DISQUE_et_sa_RAISON_nomme_ce_qui_MANQUE():
    """**A skip is a hole in the judgment; this witness is what keeps the hole honest.**

    Four things can rot in the marker above and NOT ONE of them would redden anywhere else in this
    suite — a `skipif` has no natural opponent, it fails by staying quiet:

    1. the predicate stops asking the DISK (`= True`, or an `or True`) — four witnesses are
       silenced forever and every run still says `passed`;
    2. the predicate asks about the WRONG file — a path that happens to exist here would let the
       four run again and fall over on `FileNotFoundError`, which is the defect this marker fixes;
    3. the condition is INVERTED (`SIBLING_CORPUS_ON_DISK` instead of `not …`) — the skip fires
       exactly where the corpus IS present, so the author's disk stops judging them;
    4. the reason goes mute or vague — the skip stops NAMING the absent corpus, and a reader is
       told a population was excluded without being told which one, or why.

    So: the predicate is pinned to a path this test re-states LITERALLY (never derived from
    ``SIBLING``, or the check would move with the bug), the reason must name the missing file, and
    the marker must still be ATTACHED to each frozen witness."""
    # (1)(2)(3) — the predicate is anchored to the disk, against an INDEPENDENTLY written path.
    attendu = REPO / "projects" / "saas" / "Sibling Research" / "PLAN.md"
    assert SIBLING_CORPUS_ON_DISK is attendu.is_file(), (
        f"the predicate has come loose from the disk: it says {SIBLING_CORPUS_ON_DISK}, "
        f"`{attendu}`.is_file() says {attendu.is_file()}"
    )
    # the marker must SKIP when the corpus is absent and RUN when it is present — both directions,
    # because a one-sided check leaves the inverted condition alive.
    assert needs_sibling_corpus.args[0] is (not attendu.is_file()), (
        "the skip condition must be the ABSENCE of the corpus, never its presence"
    )

    # (4) — the reason NAMES what is missing, so an excluded population is never a silent one.
    raison = needs_sibling_corpus.kwargs["reason"]
    assert "Sibling Research/PLAN.md" in raison, (
        f"the skip reason must name the absent witness tree; it reads: {raison!r}"
    )
    # NOT `"projects/" in raison`: that substring is already inside the PATH above, so the check
    # would pass over a reason that names the file and explains nothing — measured, it survived the
    # sabotage that deleted the whole explanation. The cause needs a phrase the path cannot supply.
    assert "gitignored by design" in raison, (
        f"the skip reason must name WHY the corpus is absent, not only WHICH file is: {raison!r}"
    )

    # the marker is still ATTACHED to every frozen witness, and each of them still EXISTS under
    # that name — a rename would otherwise drop a test out of this guard without a word.
    source = Path(__file__).read_text(encoding="utf-8")
    for nom in sorted(CORPUS_WITNESSES):
        assert f"\ndef {nom}(" in source, f"frozen witness {nom} no longer exists under that name"
        assert f"@needs_sibling_corpus\ndef {nom}(" in source, (
            f"{nom} reads the absent corpus but no longer carries `@needs_sibling_corpus`: it will "
            "fail on a FileNotFoundError instead of declaring the corpus missing"
        )
    # and the guarded set cannot be quietly emptied.
    assert len(CORPUS_WITNESSES) == 4, "the frozen set of corpus witnesses has changed size"


def _arcs_reels() -> tuple[ArcVu, ...]:
    """The sibling project's arcs as the SHARED reader renders them — never a second disk walk."""
    vus = []
    for plan in read_plan_tree(SIBLING, "Sibling"):
        lecture = plan.reading
        if lecture is None or not lecture.items:
            continue
        vus.append(
            ArcVu(
                identifiant=plan.name,
                total=len(lecture.items),
                faits=sum(1 for i in lecture.items if i.status == "fait"),
            )
        )
    return tuple(vus)


# --------------------------------------------------------------------------------------------
# WHAT SEPARATES A CLOSED ARC FROM AN EMPTY ARC — vacuity would manufacture a RED
# --------------------------------------------------------------------------------------------


def test_un_arc_SANS_AUCUN_item_n_est_pas_ferme():
    """"all its items are done" is TRUE by vacuity over zero items. Without the `total > 0`
    guard, the trigger would demand a harvest from an arc that never produced anything — the most
    expensive alarm there is, the one that looks legitimate."""
    assert not est_ferme(ArcVu("plan/vide", total=0, faits=0))
    assert arcs_a_moissonner([ArcVu("plan/vide", 0, 0)]) == ()


def test_un_arc_EN_COURS_n_est_jamais_nomme():
    assert not est_ferme(ArcVu("plan/03", total=20, faits=19))
    assert arcs_a_moissonner([ArcVu("plan/03", 20, 19)]) == ()


# --------------------------------------------------------------------------------------------
# THE WITNESS THAT ARMS THE GATE — on the REAL population, an arc closed for real
# --------------------------------------------------------------------------------------------


@needs_sibling_corpus
def test_sur_les_arcs_REELS_du_sibling_un_arc_ferme_est_NOMME():
    """The decisive witness: the population has the SHAPE of the real thing, and **one** arc in
    it is closed.

    Measured: the sibling project carries 14 arcs, 0 closed. Pulling the judge over this population as-is would
    return a green that measures nothing. So we close the first real arc — same identifiers, same
    sizes — and require the trigger to name it."""
    reels = _arcs_reels()
    assert reels, "The sibling project's plan must be readable by the shared reader"
    cible = reels[0]
    population = (ArcVu(cible.identifiant, cible.total, cible.total), *reels[1:])
    manquants = arcs_a_moissonner(population)
    assert cible.identifiant in manquants, (
        f"a real closed arc must be named; the judge returned {manquants}"
    )


@needs_sibling_corpus
def test_le_meme_arc_reel_DEJA_moissonne_retombe_dans_le_silence():
    """The counterpart, and it is what prevents the alarm nobody can turn off.

    **THIS WITNESS TURNED RED ON 2026-09-08, AND IT WAS WRONG — FIXED HERE.** It required
    ``== ()``: *no* arc pending after declaring the target harvested. That equality is only true
    if the target is the ONLY closed arc in the real plan — a dependency on the sibling project's state,
    disguised as an assertion about the judge. This file's own docstring forbids exactly that, in
    plain words: *"no witness here asserts '0 closed arcs' […] that would freeze the sibling project's state
    inside my suite, and turn red the day an arc closes for real"*. **That day has come**: on
    2026-08-15 the sibling project carried 0 closed arcs out of 14; on 2026-09-08 it carries **3**, and the
    witness fell on the project's success, not on a defect in the judge. *A class closed in the
    prose stays open in the code that comes with it.*

    What it meant to say, and what it says now: **the TARGET is no longer named**. The judge is
    tested on its own effect, never on the cardinal of a population that lives its own life."""
    reels = _arcs_reels()
    cible = reels[0]
    population = (ArcVu(cible.identifiant, cible.total, cible.total), *reels[1:])
    avant = arcs_a_moissonner(population)
    apres = arcs_a_moissonner(population, {cible.identifiant})
    assert cible.identifiant in avant, "precondition: the target must be named without the registry"
    assert cible.identifiant not in apres, (
        f"an arc declared harvested must no longer be named; the judge returned {apres}"
    )
    assert set(apres) == set(avant) - {cible.identifiant}, (
        "declaring an arc harvested must change nothing ELSE in the population"
    )


# --------------------------------------------------------------------------------------------
# WHAT CROSSES, AND WHAT DOES NOT CROSS — the bound IS the confinement guarantee
# --------------------------------------------------------------------------------------------


def test_le_silence_est_un_None_pas_une_phrase_vide():
    """A source that speaks over emptiness manufactures noise; `None` is what the proposer knows
    how to keep silent."""
    assert resume(()) is None


def test_la_liste_est_BORNEE_et_le_reste_est_COMPTE():
    """Three plan paths are a pointer; fifty are a project's structure. It is the bound that
    makes NAMING compatible with invariant 22, not good intentions."""
    manquants = tuple(f"Sibling/plan/{n:02d}" for n in range(10))
    phrase = resume(manquants)
    assert phrase is not None
    nommes = [a for a in manquants if a in phrase]
    assert len(nommes) == NOMS_MAX, f"{len(nommes)} arcs named, the bound tolerates {NOMS_MAX}"
    assert "and 7 others" in phrase, phrase
    assert "10 closed arcs have" in phrase


def test_un_seul_arc_manquant_n_annonce_AUCUN_reste():
    phrase = resume(("Sibling/plan/03-captation",))
    assert phrase is not None and "other" not in phrase and "1 closed arc has" in phrase


# --------------------------------------------------------------------------------------------
# THE REGISTRY — identity comes from the DECLARED field, never the file name
# --------------------------------------------------------------------------------------------


def test_l_identite_d_une_moisson_vient_du_champ_arc_pas_du_NOM_du_fichier(tmp_path):
    """*Identity by SHAPE is impersonatable by any copy.* Two arcs from two different projects
    can produce the same file slug; the `arc:` field only collides if someone writes it twice —
    and then it IS the same arc."""
    (tmp_path / "any-old-name.md").write_text(
        'arc: "Sibling/plan/03-captation"\n\n# Moisson\n', encoding="utf-8"
    )
    (tmp_path / "sibling-plan-03-captation.md").write_text(
        "arc: Autre/plan/99-different\n\n# Moisson\n", encoding="utf-8"
    )
    vus = arcs_moissonnes(tmp_path)
    assert "Sibling/plan/03-captation" in vus, "the file with an unrelated name still declares the arc"
    assert "Autre/plan/99-different" in vus
    assert len(vus) == 2


def test_un_registre_ABSENT_rend_le_vide_sans_LEVER():
    """Level 1: this module publishes, it never refuses.

    **This witness declares what arms it, because it was passing for the WRONG reason.** The
    first draft had an `is_dir()` check before the `glob` call; the sabotage that removed it
    **survived**, because `Path.glob` on a missing folder does not raise — it returns nothing. The
    guard was a **dead branch**, and this witness measured only that. It has been removed: this
    witness now arms `glob`'s own behavior, and it will turn red the day that behavior changes."""
    assert arcs_moissonnes(Path("/n/existe/pas/du/tout")) == frozenset()


def test_un_registre_qui_est_un_FICHIER_rend_le_vide_sans_LEVER(tmp_path):
    """The other form of the same edge — a path that exists but is not a folder.

    **This witness does NOT prove the module's `try/except` is useful**: measured here, `glob`
    on a file path does not raise either, and the sabotage that removes that `try` **survives**.
    The module admits this in plain words rather than calling it a barrier."""
    fichier = tmp_path / "pas-un-dossier.md"
    fichier.write_text("arc: X\n", encoding="utf-8")
    assert arcs_moissonnes(fichier) == frozenset()


def test_un_champ_arc_VIDE_n_entre_pas_dans_le_registre(tmp_path):
    """Found by sabotage: without the filter, an `arc: "  "` would deposit the EMPTY
    identifier.

    The tick would then name "a closed arc with no harvest" whose name is the empty string — a
    signal that looks legitimate and designates nothing. *A name is not a test*: what matters is
    that a field that is present but hollow is treated as ABSENT, not as one more arc."""
    (tmp_path / "creux.md").write_text('arc: "   "\n', encoding="utf-8")
    (tmp_path / "nu.md").write_text("arc:\n", encoding="utf-8")
    (tmp_path / "bon.md").write_text("arc: Sibling/plan/03-captation\n", encoding="utf-8")
    assert arcs_moissonnes(tmp_path) == frozenset({"Sibling/plan/03-captation"})


def test_un_fichier_MOJIBAKE_ne_tue_pas_le_LOT_et_son_voisin_passe(tmp_path):
    """**THE DEFECT THE SABOTAGE FOUND, AND IT WAS REAL**: `UnicodeDecodeError` is NOT an
    `OSError`. The first draft only caught `OSError` — a single mojibake file dropped into
    `docs/moissons/` would have killed the whole `tick`, which is to say exactly what the
    docstring promised had been closed.

    **And the assertion that matters is not "it does not raise": it is that the NEIGHBOR
    passes.** A witness that only checks the absence of an exception would be green with a
    `return frozenset()` at the top of the function. *A per-item guarantee that raises kills the
    lot* — so we measure the lot."""
    (tmp_path / "casse.md").write_bytes(b"arc: \xff\xfe ceci n'est pas de l'utf-8\n")
    (tmp_path / "bon.md").write_text('arc: "Sibling/plan/03-captation"\n', encoding="utf-8")
    assert arcs_moissonnes(tmp_path) == frozenset({"Sibling/plan/03-captation"})


def test_le_registre_REEL_du_depot_se_lit_sans_lever():
    """The registry lives in the repo: empty today, it must still be readable."""
    assert isinstance(arcs_moissonnes(REPO / "docs" / "moissons"), frozenset)


# --------------------------------------------------------------------------------------------
# WHAT THE SENTENCE NEVER SAYS — no item title crosses
# --------------------------------------------------------------------------------------------


@needs_sibling_corpus
def test_de_BOUT_EN_BOUT_un_arc_REEL_du_sibling_ferme_produit_la_moisson(tmp_path):
    """**CLAUSE (a) OF `I2`, EXERCISED**: *closing a real arc of the sibling project produces a harvest.*

 Nothing is simulated here except **the closure itself**: the arc, its items, its sub-pages and
 their identifiers are the sibling project's own, copied as-is. We close `11-catalogue-de-slots` by flipping
 its three sub-pages to `` — **inside a COPY**, never in the real plan: checking a box belongs
 to the orchestrator, and falsifying a plan to turn a witness green would be the worst kind of
 blindness.

 **And an item's status lives on ITS OWN PAGE, not on the arc's line.** My first attempt
 closed the `` in the arc file itself and the trigger **did not bite**: the shared reader
 resolves status from `source=`. This witness therefore closes the sub-pages — the only
 closure that is real.

 The three links are exercised in order: the closed arc is **named**, `make moisson` **emits**
 its contract for this project, and the registry entry **produces silence**."""
    from mnemosyne.production.harvest import build_harvest_contract
    from mnemosyne.runtime.tick import _moisson_due

    racine = tmp_path / "projects" / "saas" / "Sibling Research"
    racine.mkdir(parents=True)
    shutil.copy2(SIBLING / "PLAN.md", racine / "PLAN.md")
    arc = "11-catalogue-de-slots"
    shutil.copytree(SIBLING / "plan" / arc, racine / "plan" / arc)

    fermees = 0
    for page in sorted((racine / "plan" / arc / "plan").glob("*.md")):
        texte = page.read_text(encoding="utf-8")
        if "\U00002B1C" in texte:
            page.write_text(texte.replace("\U00002B1C", "\U00002705", 1), encoding="utf-8")
            fermees += 1
    assert fermees, "the chosen arc must carry open items, or this witness closes nothing"

    identifiant = f"Sibling Research/plan/{arc}"
    phrase = _moisson_due(tmp_path)
    assert phrase and identifiant in phrase, (
        f"a real closed arc must be named by the tick; it returned {phrase!r}"
    )
    assert "make moisson" in phrase, "and the sentence must name the command that produces it"

    # the next link: the command the sentence names does emit a contract for this project
    contrat = build_harvest_contract("projects/saas/Sibling Research")
    assert "PROJECT HARVEST" in contrat and "RECRUIT" in contrat

    # the last one: the registry entry produces silence — the alarm turns itself off
    (tmp_path / "docs" / "moissons").mkdir(parents=True)
    (tmp_path / "docs" / "moissons" / "peu-importe-le-nom.md").write_text(
        f'arc: "{identifiant}"\n', encoding="utf-8"
    )
    assert _moisson_due(tmp_path) is None


@needs_sibling_corpus
def test_le_CABLAGE_du_proposeur_fait_REMONTER_la_moisson_due(tmp_path):
    """**THE BARRIER NOTHING CALLS.** The end-to-end witness above pulls `_moisson_due`
    **directly** — it goes through neither `MoissonDueReview`, nor the facade's port, nor the
    `if ... is not None` of the wiring. Without this one, a `moisson_due_resume=` that was never
    wired in would stay **green everywhere**: the judge would work, and nobody would ever call it.

    Same shape as its seven neighbors: the tree is isolated, so the source is too — a hardcoded
    defect would count the arcs of the REAL repo from inside a `tmp_path`. Both halves are
    exercised: **silence** on a tree with no arc, **surfacing** as soon as an arc in it is
    closed."""
    from mnemosyne.runtime.tick import run_tick

    def propositions():
        return run_tick(knowledge_root=tmp_path, repo_root=tmp_path)

    assert not any("moisson" in p.summary for p in propositions()), (
        "a tree with not a single project must propose nothing — silence is correct"
    )

    racine = tmp_path / "projects" / "saas" / "Sibling Research"
    racine.mkdir(parents=True)
    shutil.copy2(SIBLING / "PLAN.md", racine / "PLAN.md")
    arc = "11-catalogue-de-slots"
    shutil.copytree(SIBLING / "plan" / arc, racine / "plan" / arc)
    for page in sorted((racine / "plan" / arc / "plan").glob("*.md")):
        texte = page.read_text(encoding="utf-8")
        if "\U00002B1C" in texte:
            page.write_text(texte.replace("\U00002B1C", "\U00002705", 1), encoding="utf-8")

    remontees = [p.summary for p in propositions() if "moisson" in p.summary]
    assert remontees, "a closed arc must SURFACE through the proposer, not only through the judge"
    assert f"Sibling Research/plan/{arc}" in remontees[0]


def test_le_tick_PUBLIE_qu_il_n_a_pas_pu_mesurer_au_lieu_de_se_TAIRE(monkeypatch):
    """*Two absent measurements compare equal* — and that is how a detector dies without
    turning red. Here "no arc owes a harvest" (`None`) and "I could not check" MUST read
    differently, because this nerve has **no second surface** where the absence could be said: the
    tick IS the surface.

    Level 1 to the end: it publishes the failure, it does not raise and does not break the tick."""
    from mnemosyne.runtime import tick as tick_mod

    def explose(*_a, **_k):
        raise RuntimeError("the plan reader is broken")

    monkeypatch.setattr(tick_mod, "known_projects", explose)
    phrase = tick_mod._moisson_due(REPO)
    assert phrase is not None, "a measurement failure must NOT read as silence"
    # TODO(public-mirror): needs human review — kept in sync with this same batch's translation of
    # `_moisson_due`'s exception-path text in system/lib/mnemosyne/runtime/tick.py (checklist rule
    # 8): the source asserted the French "n'ont PAS pu etre mesures", updated here to the English
    # phrase that file now actually returns.
    assert "could NOT be measured" in phrase and "RuntimeError" in phrase


@pytest.mark.parametrize("champ", ["title", "label", "detail"])
def test_aucun_TITRE_d_item_ne_peut_traverser_le_juge(champ):
    """Structural, not declarative: `ArcVu` does not CARRY these fields, so nothing can publish
    them. *What does not enter here cannot leak further* — the only confinement guarantee that
    depends on nobody's vigilance."""
    assert champ not in ArcVu.__slots__


# ------------------------------------------------------------------------------------------------
# `I3(b)` — THE LINK: the caller that `regle_candidate.py` did not have
# ------------------------------------------------------------------------------------------------


def test_la_moisson_MUETTE_est_NOMMEE_et_celle_qui_MESURE_ne_l_est_pas():
    """**The caller that `regle_candidate.py` did not have.** Its own author measured this,
    AT THE TOP of their audit mandate: *"it refuses nothing to nobody: it refuses IF IT IS
    CALLED, and nothing calls it"*. Sixth occurrence of the class in one day in this repo.

    **This witness tests DIFFERENTIATION, not conformity**: three fiches, and the output must
    retain **exactly one** of them. A judge that named everything, or nothing, would pass a
    witness that only checked the mute one."""
    muette = ("m-03.md", "# Moisson\n\nRegle proposee : committer par fragment.\n")
    mesuree = ("m-04.md", "# Moisson\n\n**Panne :** 11 004 lignes recopiees dans 3 projets.\n")
    avouee = ("m-05.md", "# Moisson\n\n**Panne :** aucune mesuree cote Mnemosyne.\n")
    assert candidats_sans_panne([muette, mesuree, avouee]) == ("m-03.md",)


def test_l_AVEU_est_une_reponse_VALIDE_et_GRATUITE():
    """The half that decides whether the gate is useful or harmful. Requiring a FIGURE would
    make people write false figures; *admitting you have not measured is an answer, inventing one
    is not.* It is the ABSENCE of a declaration that gets flagged, never the absence of a
    measurement."""
    assert candidats_sans_panne([("m.md", "**Panne :** aucune, et dite comme telle.\n")]) == ()


def test_une_declaration_COMMENTEE_ne_compte_PAS():
    """*Reusing a shape without reusing its PIPELINE is only a half-hearted reuse.* A
    declaration inside an HTML comment is **inert** — it is read nowhere — and it would still
    pass a gate that merely searched for the string."""
    inerte = ("m.md", "# Moisson\n\n<!-- **Panne :** 3 projets touches -->\n")
    assert candidats_sans_panne([inerte]) == ("m.md",)


def test_le_resume_est_BORNE_et_ne_laisse_traverser_que_des_NOMS(tmp_path):
    """Invariant 22: what crosses is a **harvest file name**, never its content. And the list
    is bounded — *three pointers read fine, fifty are a project's structure.*"""
    phrase = resume_candidats([f"m-{i:02d}.md" for i in range(9)])
    assert phrase is not None
    assert phrase.count(".md") == NOMS_MAX, f"bound at {NOMS_MAX} names: {phrase!r}"
    assert "and 6 others" in phrase, "the rest is COUNTED, it is never listed"


def test_le_registre_REEL_est_SILENCIEUX_et_le_README_n_est_pas_une_moisson():
    """**The passing case, the one I never assert.** The real registry carries only a
    `README.md`: the source must stay SILENT. If it named the registry's own instructions, it
    would manufacture an alarm nobody can turn off — *the defect `ProposalQueueReview` flags*, and
    the opposite of what `I2` was built to do."""
    reel = Path(__file__).resolve().parents[2] / "docs" / "moissons"
    assert moissons_sans_panne(reel) == (), "the real registry must be SILENT today"
    assert resume_candidats(moissons_sans_panne(reel)) is None


def test_un_dossier_ABSENT_ne_LEVE_pas(tmp_path):
    """*A per-item guarantee that raises kills the lot* — and this lot is the whole `tick`."""
    assert moissons_sans_panne(tmp_path / "nulle-part") == ()


def test_le_CABLAGE_du_proposeur_fait_REMONTER_la_moisson_SANS_PANNE(tmp_path):
    """**A SILENT SOURCE IS INDISTINGUISHABLE FROM AN UNWIRED SOURCE** — and that is exactly
    the class this link closes. The real registry carries no harvest, so
    `CandidatSansPanneReview` stays silent **today and every day to come**: without this witness,
    a `candidats_sans_panne_resume=` that was never wired in would stay **green everywhere**,
    indefinitely, and the gate in `regle_candidate.py` would keep looking like a satisfied clause.

    Both halves are exercised, as for its sibling: **silence** on a tree with no registry,
    **surfacing** as soon as a mute harvest is dropped into it."""
    from mnemosyne.runtime.tick import run_tick

    def propositions():
        return run_tick(knowledge_root=tmp_path, repo_root=tmp_path)

    assert not any("failure" in p.summary for p in propositions()), (
        "a tree with no harvest registry must propose nothing — silence is correct"
    )

    registre = tmp_path / "docs" / "moissons"
    registre.mkdir(parents=True)
    (registre / "README.md").write_text("# Le registre\n\nMode d'emploi.\n", encoding="utf-8")
    (registre / "m-declare.md").write_text(
        "arc: \"P/plan/01\"\n\n**Panne :** 11 004 lignes recopiees dans 3 projets.\n",
        encoding="utf-8",
    )
    assert not any("failure" in p.summary for p in propositions()), (
        "a harvest that DECLARES its failure — and the README — must trigger nothing"
    )

    (registre / "m-muette.md").write_text(
        "arc: \"P/plan/02\"\n\nRegle proposee : committer par fragment.\n", encoding="utf-8"
    )
    remontees = [p.summary for p in propositions() if "failure" in p.summary]
    assert remontees, "a MUTE harvest must SURFACE through the proposer, not only through the judge"
    assert "m-muette.md" in remontees[0]
    assert "m-declare.md" not in remontees[0], "the one that declares must not be named"


class TestMoissonsEnAttente:
    """`I2-bis` — a SELECTED candidate that nothing has put to the test must be NAMED.

    The measured defect these witnesses guard: the candidate selected on 2026-08-17 was never
    revisited, and the sibling project rebuilt it alone 16 days later. The `I2` trigger listened for the
    EXISTENCE of an entry; what was missing was listening to its PROGRESS.
    """

    def test_retenus_non_declare_est_nomme_jamais_silencieux(self) -> None:
        """"nothing pending" and "I could not check" do not read the same."""
        suivis = (md.SuiviMoisson(source="a.md", retenus=None, eprouves=None),)
        assert md.moissons_en_attente(suivis) == ("a.md",)

    def test_retenus_zero_est_un_silence_legitime(self) -> None:
        """The contract says an honest harvest may retain NOTHING at all — naming it would
        manufacture the alarm nobody can turn off, exactly what `arcs_a_moissonner` avoids."""
        suivis = (md.SuiviMoisson(source="a.md", retenus=0, eprouves=None),)
        assert md.moissons_en_attente(suivis) == ()

    def test_retenus_sans_epreuve_est_nomme(self) -> None:
        suivis = (md.SuiviMoisson(source="a.md", retenus=3, eprouves=None),)
        assert md.moissons_en_attente(suivis) == ("a.md",)

    def test_epreuve_partielle_est_nommee(self) -> None:
        """The case that distinguishes this judge from a boolean: 2 out of 3 tested still counts
        as pending."""
        suivis = (md.SuiviMoisson(source="a.md", retenus=3, eprouves=2),)
        assert md.moissons_en_attente(suivis) == ("a.md",)

    def test_tout_eprouve_est_silencieux(self) -> None:
        """THE PASSING CASE — without it, a judge that ALWAYS returns its population would
        pass green."""
        suivis = (md.SuiviMoisson(source="a.md", retenus=3, eprouves=3),)
        assert md.moissons_en_attente(suivis) == ()

    def test_le_juge_trie_et_ne_garde_que_les_dormantes(self) -> None:
        """DIFFERENTIATION, not conformity: over a mixed population, it returns only the dormant
        ones, sorted."""
        suivis = (
            md.SuiviMoisson(source="z.md", retenus=1, eprouves=0),
            md.SuiviMoisson(source="ok.md", retenus=5, eprouves=5),
            md.SuiviMoisson(source="a.md", retenus=2, eprouves=None),
            md.SuiviMoisson(source="vide.md", retenus=0, eprouves=0),
        )
        assert md.moissons_en_attente(suivis) == ("a.md", "z.md")

    def test_resume_est_borne_et_compte_le_reste(self) -> None:
        """inv. 22: three names at most, the rest is COUNTED — never listed in full."""
        phrase = md.resume_attente(tuple(f"m{i}.md" for i in range(7)), noms_max=3)
        assert phrase is not None
        assert phrase.count(".md") == 3
        assert "and 4 others" in phrase

    def test_resume_se_tait_quand_rien_ne_dort(self) -> None:
        assert md.resume_attente(()) is None

    def test_le_bord_lit_les_champs_declares(self, tmp_path) -> None:
        (tmp_path / "m.md").write_text(
            'arc: "P/plan/01"\ndate: 2026-09-08\nretenus: 4\neprouves: 1\n\n# corps\n',
            encoding="utf-8",
        )
        (suivi,) = md.suivi_des_moissons(tmp_path)
        assert (suivi.source, suivi.retenus, suivi.eprouves) == ("m.md", 4, 1)

    def test_le_bord_tolere_un_commentaire_apres_le_chiffre(self, tmp_path) -> None:
        """DEFECT MEASURED THE DAY THIS WAS WRITTEN: without this tolerance, `eprouves: 0  #
        rien` was read as NOT DECLARED. The tick still named the harvest — but **for the wrong
        reason**, and its message sent you to declare a field that was already written. *A
        witness that passes for the wrong reason proves nothing.*"""
        (tmp_path / "m.md").write_text(
            "arc: \"P/plan/01\"\nretenus: 2   # deux gardes\neprouves: 0   # aucune epreuve\n",
            encoding="utf-8",
        )
        (suivi,) = md.suivi_des_moissons(tmp_path)
        assert (suivi.retenus, suivi.eprouves) == (2, 0)

    def test_le_bord_saute_le_readme_et_survit_a_l_illisible(self, tmp_path) -> None:
        """*A per-item guarantee that raises kills the lot* — and this lot is the whole tick."""
        (tmp_path / "README.md").write_text("retenus: 99\n", encoding="utf-8")
        (tmp_path / "bin.md").write_bytes(b"\xff\xfe retenus: 7\n")
        (tmp_path / "ok.md").write_text("retenus: 1\neprouves: 0\n", encoding="utf-8")
        sources = {s.source for s in md.suivi_des_moissons(tmp_path)}
        assert sources == {"ok.md"}

    def test_le_bord_rend_vide_sur_un_dossier_absent(self, tmp_path) -> None:
        assert md.suivi_des_moissons(tmp_path / "nexiste-pas") == ()


class TestCeQueLAuditIsoleATrouve:
    """The seven defects returned by an isolated auditor on 2026-09-08 over `b2d2ee0`/`6c3781b`.

    None had a witness: all of them were found by MUTATION, not by reading. And the most
    serious one contradicted a docstring its own author had written IN BOLD.
    """

    def test_un_registre_ILLISIBLE_ne_se_lit_pas_comme_VIDE(self, tmp_path) -> None:
        """DEFECT No. 1. `Path.glob` DOES NOT RAISE on a folder with no permission (measured:
        glob returns 0 entries, iterdir and os.listdir raise PermissionError). The `except
        OSError` around the glob call was therefore a DEAD BRANCH, and the tick stayed silent
        exactly where its docstring asserted in bold that it never does."""
        d = tmp_path / "moissons"
        d.mkdir()
        (d / "m.md").write_text("retenus: 3\neprouves: 0\n", encoding="utf-8")
        d.chmod(0o000)
        try:
            assert md.suivi_des_moissons(d) is None, "unreadable must surface, never stay silent"
        finally:
            d.chmod(0o755)

    def test_un_registre_ABSENT_reste_un_silence_legitime(self, tmp_path) -> None:
        """THE BOUND: a registry that does not exist yet is a NORMAL state, not a failure.
        Without this witness, returning None everywhere would make the tick cry out on every new
        repo."""
        assert md.suivi_des_moissons(tmp_path / "jamais-cree") == ()

    def test_un_entier_DEMESURE_ne_tue_pas_le_LOT(self, tmp_path) -> None:
        """DEFECT No. 2. CPython refuses `int()` beyond 4,300 digits. A single file made the
        WHOLE edge raise, and *the HEALTHY neighbor was lost along with it* -- while its sibling
        `arcs_moissonnes` returned its arc without flinching on the very same folder."""
        d = tmp_path / "moissons"
        d.mkdir()
        (d / "aaa-sain.md").write_text("retenus: 1\neprouves: 0\n", encoding="utf-8")
        (d / "zzz.md").write_text("retenus: " + "9" * 5000 + "\n", encoding="utf-8")
        suivis = md.suivi_des_moissons(d)
        assert suivis is not None
        noms = {s.source for s in suivis}
        assert "aaa-sain.md" in noms, "the healthy neighbor must NEVER be swept away"
        illisible = next(s for s in suivis if s.source == "zzz.md")
        assert illisible.retenus is None, "a number that cannot be read is not declared"

    def test_le_README_ne_peut_pas_ETEINDRE_une_alarme(self, tmp_path) -> None:
        """DEFECT No. 4, AND IT IS THE MOST INSIDIOUS. The README shows the shape of an
        entry, example included: `arc: "Sibling/plan/03-captation"`. It was read as a harvest
        REALLY deposited -- so a real arc of that name saw its alarm turned off IN SILENCE.
        Measured the same day against the real registry: `arcs_moissonnes` did return this
        example arc. *A silence bought by an example looks like work done.*"""
        d = tmp_path / "moissons"
        d.mkdir()
        (d / "README.md").write_text('arc: "P/plan/01"\nretenus: 9\n', encoding="utf-8")
        assert md.arcs_moissonnes(d) == frozenset(), "the instructions are not a harvest"
        assert md.suivi_des_moissons(d) == ()
        arc = ArcVu("P/plan/01", 3, 3)  # a REAL arc, closed, sharing the example's name
        assert md.arcs_a_moissonner((arc,), md.arcs_moissonnes(d)) == ("P/plan/01",)

    def test_le_biais_des_deux_soeurs_est_OPPOSE_et_c_est_voulu(self, tmp_path) -> None:
        """DEFECT No. 1 HAS A COUNTERPART THAT MUST NOT BE "HARMONIZED". On an unreadable
        registry, `arcs_moissonnes` returns an EMPTY set -- so ALL closed arcs get named, a LOUD
        refusal. `suivi_des_moissons` returns `None` -- because there, an empty result would read
        as "nothing is dormant", a SILENCE. *A fail-safe is judged by the sense of its failure,
        never by the uniformity of its shape.*"""
        d = tmp_path / "moissons"
        d.mkdir()
        (d / "m.md").write_text('arc: "P/plan/01"\nretenus: 2\n', encoding="utf-8")
        d.chmod(0o000)
        try:
            assert md.arcs_moissonnes(d) == frozenset()  # loud: nothing is "already harvested"
            assert md.suivi_des_moissons(d) is None  # surfaces: otherwise it would be a silence
        finally:
            d.chmod(0o755)

    def test_la_BORNE_DE_PRODUCTION_est_gardee_pas_seulement_l_argument(self) -> None:
        """DEFECT No. 3: mutating the `noms_max` DEFAULT to 999 SURVIVED. The bound's witness
        passed `noms_max=3` explicitly -- it was testing its own argument, never the value
        PRODUCTION actually uses. *Checking a value does not protect the site that uses a
        different one.*"""
        phrase = md.resume_attente(tuple(f"m{i}.md" for i in range(9)))  # WITHOUT noms_max
        assert phrase is not None
        assert phrase.count(".md") == md.NOMS_MAX
        assert f"and {9 - md.NOMS_MAX} others" in phrase

    def test_les_ANCRES_du_motif_sont_gardees(self) -> None:
        """DEFECT No. 5: mutating `^` or `$` out of the pattern SURVIVED -- nothing pinned the
        anchors, so the correct refusal of prose in the middle of a line was guarded by nothing."""
        import re as _re

        assert md._RETENUS.search("retenus: 4\n").group(1) == "4"
        # EACH ANCHOR HAS ITS OWN CASE, AND IT TOOK A SABOTAGE TO IMPOSE THAT. The first
        # version tested both with a SINGLE counter-example ("the number of retenus: 4 is
        # wrong") -- but the `$` alone was enough to reject it, so removing `^` SURVIVED.
        # *Checking a value does not protect the site that uses a different one*, applied to a
        # regular expression.
        # without `^` alone: a mid-line prefix would pass (the end of line, though, is fine)
        assert md._RETENUS.search("xx retenus: 4\n") is None
        # without `$` alone: a suffix would pass (the start of line, though, is fine)
        assert md._RETENUS.search("retenus: 4 et des poussieres\n") is None
        assert isinstance(md._RETENUS, _re.Pattern)

    def test_SuiviMoisson_ne_peut_porter_AUCUN_contenu(self) -> None:
        """DEFECT No. 7: the sibling `ArcVu` has a structural confinement witness,
        `SuiviMoisson` does not. The type was poor IN FACT, never BY GUARANTEE -- and *identity by
        shape is impersonatable*: a field added tomorrow would cross all the way to the tick's
        output."""
        assert md.SuiviMoisson.__slots__ == ("source", "retenus", "eprouves")
        with pytest.raises(TypeError):
            md.SuiviMoisson(source="m.md", retenus=1, eprouves=0, titre="fuite")  # type: ignore[call-arg]
