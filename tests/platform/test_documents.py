"""THE ORPHAN DOCUMENT DETECTOR GETS JUDGED (project 0  -  A3).

WHAT YOU NEED TO KNOW BEFORE READING THESE WITNESSES. A3 is a **report**, not a gate: it names
the documents that nothing cites and **moves nothing**. The plan required it - *"a report (that
proposes), never a gate (that moves)"* - because the "not modified in N days" threshold would have
fallen under A4 (*a ceiling on a generated output does not bound, it STEERS*). The criterion is
therefore THRESHOLD-FREE: citation. Age is only a sort order, and one witness below proves it.

THE FIRST WITNESS IS THE INNOCENT: without it, a detector that would NEVER accuse anyone
would pass every silent witness that follows.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from mnemosyne.production.documents import (
    DESTINATION,
    PORTES_D_ENTREE,
    compte_orphelins,
    documents_orphelins,
    liens_morts,
    rendre,
)
from mnemosyne.production.proposer import DocumentsOrphelinsReview

_RACINE = Path(__file__).resolve().parents[2]


def _ecrire(racine: Path, relatif: str, corps: str = "x", age_jours: int = 0) -> None:
    chemin = racine / relatif
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(corps, encoding="utf-8")
    if age_jours:
        vieux = chemin.stat().st_mtime - age_jours * 86_400
        os.utime(chemin, (vieux, vieux))


def test_l_INNOCENT_un_document_CITE_n_est_pas_accuse(tmp_path: Path) -> None:
    """The passing path must pass, or no witness below measures anything at all."""
    _ecrire(tmp_path, "docs/living.md")
    _ecrire(tmp_path, "docs/gateway.md", "see [the living doc](docs/living.md)")
    trouves = documents_orphelins(tmp_path, ("docs/living.md",), ("docs/gateway.md",))
    assert trouves == ()


def test_un_document_que_RIEN_ne_pointe_est_nomme(tmp_path: Path) -> None:
    _ecrire(tmp_path, "docs/dead.md")
    _ecrire(tmp_path, "docs/gateway.md", "this gateway doesn't mention anyone")
    trouves = documents_orphelins(tmp_path, ("docs/dead.md",), ("docs/gateway.md",))
    assert [o.chemin for o in trouves] == ["docs/dead.md"]


def test_un_document_ne_se_CITE_pas_lui_meme(tmp_path: Path) -> None:
    """A document's own name appears in its own text as soon as it carries a title or a relative
    link. Counting itself as its own citer would make the detector structurally mute - *zero
    refusals can mean the rule is being bypassed*."""
    _ecrire(tmp_path, "docs/alone.md", "# docs/alone.md - I talk about myself")
    trouves = documents_orphelins(tmp_path, ("docs/alone.md",), ("docs/alone.md",))
    assert [o.chemin for o in trouves] == ["docs/alone.md"]


def test_une_citation_par_le_seul_NOM_de_fichier_compte(tmp_path: Path) -> None:
    """THE DIRECTION OF THE ERROR IS CHOSEN, NOT SUFFERED. Also searching for the bare
    name UNDER-reports orphans (a mention in prose is enough to save a document). This is the right
    sense of the risk: wrongly proposing to archive a LIVING document costs on the operator's files;
    staying silent about a dead one costs in readability, and is recovered at the next pass."""
    _ecrire(tmp_path, "docs/cite-en-prose.md")
    _ecrire(tmp_path, "notes.md", "I mention it in cite-en-prose.md, without a markdown link")
    assert documents_orphelins(tmp_path, ("docs/cite-en-prose.md",), ("notes.md",)) == ()


def test_les_PORTES_D_ENTREE_ne_sont_JAMAIS_proposees(tmp_path: Path) -> None:
    """`README.md` and `ARCHITECTURE.md` are the repo's entry documents: they are cited BY
    CONVENTION, not by a link. Proposing them for archival would be absurd."""
    for nom in sorted(PORTES_D_ENTREE):
        _ecrire(tmp_path, nom)
    documents = tuple(sorted(PORTES_D_ENTREE))
    assert documents_orphelins(tmp_path, documents, ()) == ()


def test_ce_qui_est_DEJA_archive_ne_revient_pas_dans_le_rapport(tmp_path: Path) -> None:
    """Otherwise the report would carry a permanent noise that no gesture can extinguish: an
    archive is cited by no one, that is its definition."""
    _ecrire(tmp_path, "docs/archive/vieux-plan.md")
    assert documents_orphelins(tmp_path, ("docs/archive/vieux-plan.md",), ()) == ()


def test_l_AGE_trie_mais_ne_DECIDE_jamais(tmp_path: Path) -> None:
    """THE TRAP THE PLAN NAMED. A "not modified in N days" [threshold] would turn
    A3 into a ceiling (A4 / D165). Here a document from TODAY, uncited, is reported just like the
    others - only its RANK changes. No N exists, so no N steers."""
    _ecrire(tmp_path, "docs/brand-new.md", age_jours=0)
    _ecrire(tmp_path, "docs/very-old.md", age_jours=40)
    trouves = documents_orphelins(tmp_path, ("docs/brand-new.md", "docs/very-old.md"), ())
    assert [o.chemin for o in trouves] == ["docs/very-old.md", "docs/brand-new.md"], (
        "the oldest first"
    )
    assert len(trouves) == 2, "the new one is REPORTED, never filtered"
    assert trouves[0].jours >= 39


def test_le_rapport_PUBLIE_la_population_examinee(tmp_path: Path) -> None:
    """*A refusal is legible, an absence is taken on faith.* "0 orphans" out of 0
    documents examined would read exactly like a healthy repo - the examined count is what tells
    them apart."""
    empty = rendre((), examines=0)
    full = rendre((), examines=79)
    assert "0 document(s) examined" in empty
    assert "79 document(s) examined" in full
    assert empty != full, "two absences of a result must not render the SAME text"


def test_le_rapport_dit_qu_il_ne_DEPLACE_RIEN(tmp_path: Path) -> None:
    """A3 is a report. If it passed itself off as a tidy-up, no one would make the gesture - and
    *a check that only prints is not a gate*."""
    _ecrire(tmp_path, "docs/dead.md")
    texte = rendre(documents_orphelins(tmp_path, ("docs/dead.md",), ()), examines=1)
    assert "This report moves NOTHING" in texte
    assert DESTINATION in texte, "the proposed destination must be NAMED, not implied"


def test_le_compte_ne_rend_QU_UN_NOMBRE(tmp_path: Path) -> None:
    """The proposal nerve crosses the cloisonnement: a COUNT, never a path (inv. 22/D66)."""
    _ecrire(tmp_path, "docs/a.md")
    _ecrire(tmp_path, "docs/b.md")
    n = compte_orphelins(tmp_path, ("docs/a.md", "docs/b.md"), ())
    assert n == 2 and isinstance(n, int)


def test_le_nerf_est_SILENCIEUX_a_zero_et_PARLE_au_dela() -> None:
    """Silent when everything is cited (zero noise), and it NAMES the command when it does speak -
    *the message names the way out*, or the report stays a report that nobody acts on."""
    assert DocumentsOrphelinsReview(lambda: 0).scan() == ()
    drafts = DocumentsOrphelinsReview(lambda: 4).scan()
    assert len(drafts) == 1
    assert "4 documents" in drafts[0].summary
    assert "make documents" in drafts[0].summary


def test_la_surface_REFUSE_au_lieu_d_inventer_un_depot_SAIN(tmp_path: Path) -> None:
    """THE WITNESS THAT MATTERS MOST ON THIS SURFACE. Outside a git repo, `git
    ls-files` fails: rendering "no orphan documents" would be a GREEN bought on a measurement that
    was never taken. The rc must BITE (2) and the cause must be named."""
    env = {**os.environ, "PYTHONPATH": str(_RACINE / "system" / "lib")}
    r = subprocess.run(
        [sys.executable, "-m", "mnemosyne.runtime.documents_run", "--racine", str(tmp_path)],
        capture_output=True,
        text=True,
        env=env,
        cwd=tmp_path,
        timeout=120,
    )
    assert r.returncode == 2, f"rc={r.returncode} out={r.stdout[:300]}"
    assert "nothing was examined" in r.stderr, r.stderr[:300]
    assert "orphelin" not in r.stdout.lower(), "no verdict should come out of an impossible scan"


def test_le_tick_reste_SILENCIEUX_si_la_population_est_INTIRABLE(tmp_path: Path) -> None:
    """The tick is a nerve, not a gate: outside a git repo it stays silent (0) instead of breaking.
    Where the absence of a measurement MUST be stated is the surface pulled by hand - witness above."""
    from mnemosyne.runtime.tick import _compter_orphelins

    assert _compter_orphelins(tmp_path) == 0


def test_une_MENTION_suffit_meme_venant_d_un_RAPPORT(tmp_path: Path) -> None:
    """THE DETECTOR NEUTRALIZES ITSELF - MEASURED ONE HOUR AFTER IT LANDED.

    The report rendered 4 orphans; I named two of them in the plan to submit them to the operator,
    and the count dropped to 2 **without a single document having moved** - the only thing citing
    the missing two was the text that flagged them. *Talking about it IS citing it.*

    We ASSUME: a document the living plan names as awaiting a decision IS within the reading field -
    it is not dead, it is queued. This witness freezes that behavior as a DECISION so it stops being
    an accident, and what it forbids is reading the drop as a tidy-up: 4 -> 2 does not mean "two
    filed away".
    """
    _ecrire(tmp_path, "docs/dead.md")
    alone = documents_orphelins(tmp_path, ("docs/dead.md",), ())
    assert [o.chemin for o in alone] == ["docs/dead.md"], (
        "the innocent: an orphan for as long as nothing mentions it"
    )

    _ecrire(tmp_path, "docs/plan/arc.md", "to decide: `docs/dead.md` - archive it or cite it?")
    after = documents_orphelins(tmp_path, ("docs/dead.md",), ("docs/plan/arc.md",))
    assert after == (), "a document NAMED by the plan comes off the list - claimed, not suffered"


# --------------------------------------------------------------- DEAD LINKS (C2)
#
# THE INNOCENT FIRST, here too: a judge that never accuses would pass every silence.
# And the permanent check is the EXAMPLE link inside a code block - a document may carry a link
# like `[docs/FORMAT_PLAN.md](...)` inside an example JSON payload. A judge that counts it accuses
# the prose.


def test_liens_l_INNOCENT_un_lien_qui_RESOUT_n_est_pas_accuse(tmp_path: Path) -> None:
    _ecrire(tmp_path, "docs/cible.md")
    _ecrire(tmp_path, "docs/page.md", "see [the target](cible.md) and that's it")
    assert liens_morts(tmp_path, ("docs/page.md",)) == ()


def test_liens_un_lien_MORT_est_nomme_avec_sa_LIGNE_et_sa_CIBLE(tmp_path: Path) -> None:
    _ecrire(tmp_path, "docs/page.md", "titre\n\nvoir [ailleurs](parti.md)\n")
    (mort,) = liens_morts(tmp_path, ("docs/page.md",))
    assert (mort.document, mort.ligne, mort.cible, mort.gele) == (
        "docs/page.md",
        3,
        "parti.md",
        False,
    )


def test_liens_un_lien_dans_un_BLOC_DE_CODE_n_est_PAS_un_lien(tmp_path: Path) -> None:
    """The false positive measured on a real document, frozen here as a witness."""
    _ecrire(
        tmp_path, "docs/page.md", 'before\n```json\n"d": "[`FORMAT_PLAN.md`](...)"\n```\nafter\n'
    )
    assert liens_morts(tmp_path, ("docs/page.md",)) == ()


def test_liens_un_bloc_de_code_REFERME_ne_protege_plus_la_suite(tmp_path: Path) -> None:
    """Without the toggle, everything after a ``` would be ignored - the gate would go silent for
    nothing."""
    _ecrire(tmp_path, "docs/page.md", "```\n[x](inside.md)\n```\n[y](outside.md)\n")
    (mort,) = liens_morts(tmp_path, ("docs/page.md",))
    assert mort.cible == "outside.md" and mort.ligne == 4


def test_liens_une_URL_EXTERNE_n_est_JAMAIS_accusee(tmp_path: Path) -> None:
    _ecrire(tmp_path, "docs/page.md", "[a](https://x.dev) [b](http://y.dev) [c](mailto:z@x.dev)\n")
    assert liens_morts(tmp_path, ("docs/page.md",)) == ()


def test_liens_une_ANCRE_ne_change_pas_le_fichier_vise(tmp_path: Path) -> None:
    _ecrire(tmp_path, "docs/cible.md")
    _ecrire(tmp_path, "docs/page.md", "[a](cible.md#a-section)\n[b](absent.md#other)\n")
    (mort,) = liens_morts(tmp_path, ("docs/page.md",))
    assert mort.cible == "absent.md"


def test_liens_l_ARCHIVE_est_MARQUEE_gelee_jamais_ecartee_en_silence(tmp_path: Path) -> None:
    """An exemption that DELETES the measurement makes it uncontrollable - this one marks it
    instead."""
    _ecrire(tmp_path, "docs/archive/vieux.md", "[a](parti.md)\n")
    _ecrire(tmp_path, "docs/living.md", "[b](parti.md)\n")
    morts = liens_morts(tmp_path, ("docs/archive/vieux.md", "docs/living.md"))
    assert len(morts) == 2
    assert {m.document: m.gele for m in morts} == {
        "docs/archive/vieux.md": True,
        "docs/living.md": False,
    }
    assert morts[0].gele is False, "the LIVING field is read first"


def test_liens_le_rapport_DISTINGUE_le_champ_vivant_de_l_archive() -> None:
    from mnemosyne.production.documents import LienMort

    vivant = LienMort(document="docs/a.md", ligne=1, cible="x.md", gele=False)
    gele = LienMort(document="docs/archive/b.md", ligne=2, cible="y.md", gele=True)
    dit = rendre((), examines=2, morts=(vivant, gele))
    assert "in the live field" in dit
    assert "docs/a.md:1" in dit
    assert "INFO: 1" in dit and "VERBATIM" in dit
    assert "docs/archive/b.md" not in dit, "the archive is COUNTED, it is not spelled out"


def test_liens_le_rapport_dit_VERT_quand_le_champ_vivant_est_propre() -> None:
    from mnemosyne.production.documents import LienMort

    gele = LienMort(document="docs/archive/b.md", ligne=2, cible="y.md", gele=True)
    dit = rendre((), examines=1, morts=(gele,))
    assert "No dead link in the live field." in dit
    assert "INFO: 1" in dit


def test_liens_le_DEPOT_REEL_ne_porte_AUCUN_lien_mort_hors_archive() -> None:
    suivis = subprocess.run(
        ["git", "-C", str(_RACINE), "ls-files", "*.md"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()
    morts = liens_morts(_RACINE, tuple(suivis))
    vivants = [f"{m.document}:{m.ligne} -> {m.cible}" for m in morts if not m.gele]
    assert not vivants, f"dead links in the living field: {vivants}"


def test_liens_le_juge_MORD_sur_le_depot_REEL_sinon_le_vert_ne_prouve_rien() -> None:
    """The 23 frozen dead links under `docs/archive/` are proof the judge is not blind."""
    suivis = subprocess.run(
        ["git", "-C", str(_RACINE), "ls-files", "*.md"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()
    geles = [m for m in liens_morts(_RACINE, tuple(suivis)) if m.gele]
    assert len(geles) >= 10, (
        f"only {len(geles)} dead link(s) found in the archive - below this floor, "
        '"0 in the living field" could come from a judge that no longer resolves anything'
    )
