"""THE ARSENAL GETS JUDGED (track 1 - B2 + B3).

WHAT IS TESTED, AND WHAT CANNOT BE. The CLASSIFICATION itself ("is this target a prompt the
frontier host already carries?") is a JUDGEMENT: no test can make it true. What the code holds, and
what these tests verify, is narrower, and it is the only honest floor:

1. **The bijection** - the table and the Makefile line up exactly, in BOTH directions. A new,
   unclassified target goes RED; an entry that names nothing goes RED. This is what stops the
   offer from rotting silently for 15 years.
2. **A label that CLAIMS must justify itself** - a weapon labelled `mnemosyne` without saying what
   makes it non-portable is refused. The asymmetry is intentional (harden what claims, not what
   steps aside): a test freezes it, or someone will "harmonise" the rule away one day.
3. **An EMPTY population must not read as a HEALTHY one** - the exact mistake this repo has already
   paid for (*two absences of measurement comparing equal*).

THE FIRST TEST IS THE INNOCENT: without it, a judge that refused EVERYTHING would pass every
accusing test that follows.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

from mnemosyne.production.arsenal import (
    ACHAT_MAX,
    ARSENAL,
    ATELIER,
    DEJA_PORTE,
    MNEMOSYNE,
    NATURES,
    RAYONS,
    RENVOIS,
    TITRE_DECLARATION,
    Arme,
    armes_declarees,
    lire_la_declaration,
    rendre,
    rendre_le_verdict,
    verdict,
)
from mnemosyne.production.plan_scaffold import door_skeleton
from mnemosyne.runtime.arsenal_run import cibles_documentees

_RACINE = Path(__file__).resolve().parents[2]
_MAKEFILE = _RACINE / "Makefile"

#: A MINIMAL, HEALTHY weapon, from which each test below derives A SINGLE fault. Building the
#: fixture from the real ARSENAL would make the test depend on the very table it judges.
_SAINE = Arme("cible-a", "demarrer", "what this buys", ATELIER)


# ── The innocent: without it, a judge that refuses everything would pass the rest ─────────────


def test_une_table_saine_ne_declenche_rien() -> None:
    v = verdict(["cible-a"], [_SAINE])
    assert v.sain
    assert rendre_le_verdict(v) == ""


# ── The bijection, in both directions ──────────────────────────────────────────────────────────


def test_une_cible_documentee_que_la_table_ignore_est_nommee() -> None:
    v = verdict(["cible-a", "cible-neuve"], [_SAINE])
    assert not v.sain
    assert v.non_classees == ("cible-neuve",)
    assert "cible-neuve" in rendre_le_verdict(v)


def test_une_entree_de_table_sans_cible_reelle_est_nommee() -> None:
    v = verdict(["cible-a"], [_SAINE, Arme("vanished", "demarrer", "a phantom", ATELIER)])
    assert not v.sain
    assert v.fantomes == ("vanished",)
    assert "vanished" in rendre_le_verdict(v)


def test_une_population_vide_ne_se_lit_pas_comme_une_table_saine() -> None:
    """THE EXACT MISTAKE THIS REFUSES: "no target" and "nothing to report" are EQUAL to a
    distracted judge. Here an empty population makes the WHOLE table phantom - a loud refusal."""
    v = verdict([], [_SAINE])
    assert not v.sain
    assert v.fantomes == ("cible-a",)


def test_une_table_vide_face_a_des_cibles_reelles_les_nomme_toutes() -> None:
    v = verdict(["cible-a", "cible-b"], [])
    assert not v.sain
    assert v.non_classees == ("cible-a", "cible-b")


def test_une_cible_classee_deux_fois_est_nommee() -> None:
    v = verdict(["cible-a"], [_SAINE, _SAINE])
    assert not v.sain
    assert v.doublons == ("cible-a",)


# ── The ceiling: bounds, does not drive - and it BITES at the edge ────────────────────────────


def test_un_achat_de_cent_et_un_caracteres_est_refuse() -> None:
    """THE LENGTH IS WRITTEN IN DIGITS, NOT DERIVED FROM ACHAT_MAX. A test that computes its
    expectation from the constant it judges follows the constant when it moves: it stops biting."""
    v = verdict(["cible-a"], [Arme("cible-a", "demarrer", "x" * 101, ATELIER)])
    assert not v.sain
    assert v.achats_trop_longs == ("cible-a",)


def test_un_achat_de_cent_caracteres_passe() -> None:
    v = verdict(["cible-a"], [Arme("cible-a", "demarrer", "x" * 100, ATELIER)])
    assert v.sain


def test_le_plafond_vaut_bien_cent() -> None:
    """If someone moves ACHAT_MAX, the two edge tests above stop bracketing the real limit
    without turning red. This test turns red in their place."""
    assert ACHAT_MAX == 100


def test_un_achat_vide_est_refuse() -> None:
    v = verdict(["cible-a"], [Arme("cible-a", "demarrer", "   ", ATELIER)])
    assert not v.sain
    assert v.achats_trop_longs == ("cible-a",)


def test_le_plafond_refuse_il_ne_tronque_pas() -> None:
    """A4 / D165: a ceiling that CUTS drives the output; this one refuses and leaves the full text."""
    trop_long = "y" * 140
    page = rendre([Arme("cible-a", "demarrer", trop_long, ATELIER)])
    assert trop_long in page


# ── A label that claims must justify itself - and the asymmetry is intentional ────────────────


def test_une_arme_mnemosyne_sans_pourquoi_est_refusee() -> None:
    v = verdict(["cible-a"], [Arme("cible-a", "demarrer", "I claim", MNEMOSYNE)])
    assert not v.sain
    assert v.sans_pourquoi == ("cible-a",)


def test_une_arme_mnemosyne_avec_pourquoi_passe() -> None:
    v = verdict(
        ["cible-a"], [Arme("cible-a", "demarrer", "I claim", MNEMOSYNE, "a gate refuses")]
    )
    assert v.sain


def test_une_arme_deja_portee_n_a_rien_a_justifier() -> None:
    """THE ASYMMETRY IS THE DESIGN, NOT AN OVERSIGHT: harden what CLAIMS (the revendication),
    never what steps aside. Without this test, someone will "harmonise" the rule and humility will cost."""
    v = verdict(["cible-a"], [Arme("cible-a", "demarrer", "your host already does it", DEJA_PORTE)])
    assert v.sain


def test_un_rayon_hors_liste_est_nomme() -> None:
    v = verdict(["cible-a"], [Arme("cible-a", "invented-rayon", "what this buys", ATELIER)])
    assert not v.sain
    assert v.rayons_inconnus == ("cible-a",)


def test_une_nature_hors_liste_est_nommee() -> None:
    v = verdict(["cible-a"], [Arme("cible-a", "demarrer", "what this buys", "awesome")])
    assert not v.sain
    assert v.natures_inconnues == ("cible-a",)


# ── The render: one line per weapon, the legend once, the detail on request ───────────────────


def test_le_rendu_donne_une_ligne_par_arme() -> None:
    page = rendre([_SAINE, Arme("cible-b", "savoir", "something else", ATELIER)])
    assert page.count("- `make ") == 2
    assert "- `make cible-a` \U0001F527 what this buys" in page


def test_la_legende_n_est_imprimee_qu_une_fois() -> None:
    """Repeating it on every line would rebuild the wall we just tore down."""
    page = rendre(ARSENAL)
    for _, _, legende in NATURES:
        assert page.count(legende) == 1


def test_sans_detail_le_pourquoi_reste_cache() -> None:
    arme = Arme("cible-a", "demarrer", "what this buys", MNEMOSYNE, "BECAUSE A GATE REFUSES")
    assert "BECAUSE A GATE REFUSES" not in rendre([arme])


def test_avec_detail_le_pourquoi_apparait() -> None:
    arme = Arme("cible-a", "demarrer", "what this buys", MNEMOSYNE, "BECAUSE A GATE REFUSES")
    assert "BECAUSE A GATE REFUSES" in rendre([arme], detail=True)


def test_un_rayon_vide_le_dit_au_lieu_de_disparaitre() -> None:
    page = rendre([_SAINE])
    assert page.count("_nothing in this rayon_") == len(RAYONS) - 1


# ── RENVOIS (adoption probe, 2026-08-17): a signpost, never a second entry ────────────────────


def test_un_renvoi_pointe_une_cible_classee_ailleurs_SANS_LA_RECOPIER() -> None:
    cible = Arme("plan-gate-emit", "mur", "emit the barrier", MNEMOSYNE, "a gate that refuses")
    page = rendre([_SAINE, cible], renvois=(("demarrer", "plan-gate-emit"),))
    demarrer = page.split("## You're starting a project")[1].split("## ")[0]
    assert "- \U000025B6 `make plan-gate-emit`" in demarrer
    assert "emit the barrier" in demarrer, "the achat must come from THE target, never recopied"
    assert 'filed under "You\'ve hit a wall"' in demarrer


def test_un_renvoi_N_EST_PAS_une_seconde_entree_pour_le_juge() -> None:
    """The mechanism that stops `plan-gate-emit` from counting twice: `verdict()` never sees
    `RENVOIS`, only `ARSENAL` - the target stays classified ONCE there (under `mur`)."""
    v = verdict([a.cible for a in ARSENAL], ARSENAL)
    assert v.doublons == (), rendre_le_verdict(v)
    assert [a.rayon for a in ARSENAL if a.cible == "plan-gate-emit"] == ["mur"]


def test_un_renvoi_NE_SE_LIT_PAS_COMME_UNE_ADOPTION() -> None:
    """A project that pastes `make arsenal`'s signpost into its door (the very gesture this
 module encourages) must not accidentally declare a target it only looked up - the `- `
 shape must stay OUTSIDE the vocabulary `lire_la_declaration` recognizes."""
    page = rendre(ARSENAL)
    panneau = next(ligne for ligne in page.splitlines() if ligne.startswith("- \U000025B6 `make "))
    porte = f"# PLAN - x\n\n> **Cap** : x\n\n## {TITRE_DECLARATION}\n\n{panneau}\n"
    assert lire_la_declaration(porte) == ()


def test_le_rendu_par_defaut_utilise_bien_RENVOIS_du_module() -> None:
    """Without the explicit argument, `rendre()` falls back to the real table - not an empty
    tuple that would silently drop the signpost if someone forgot to pass it."""
    assert "- \U000025B6 `make plan-gate-emit`" in rendre(ARSENAL)


def test_aucun_RENVOI_REEL_ne_pointe_un_fantome_ni_son_propre_rayon() -> None:
    par_cible = {a.cible: a.rayon for a in ARSENAL}
    for rayon_cible, cible in RENVOIS:
        assert cible in par_cible, f"{cible} exists in no rayon of ARSENAL"
        assert par_cible[cible] != rayon_cible, f"{cible} would point at its own rayon"


# ── Reading the Makefile, at the edge ──────────────────────────────────────────────────────────


def test_seules_les_cibles_documentees_entrent_dans_la_population() -> None:
    texte = "public: ## what it buys\n\ttrue\n\ninternal:\n\ttrue\n"
    assert cibles_documentees(texte) == ("public",)


def test_une_cible_declaree_deux_fois_n_est_comptee_qu_une() -> None:
    assert cibles_documentees("a: ## x\na: ## y\n") == ("a",)


# ── THE LIVE DOOR: the real table against the real Makefile ───────────────────────────────────


def test_le_vrai_makefile_et_la_vraie_table_se_recouvrent() -> None:
    """THIS IS THE BARRIER, NOT AN ILLUSTRATION. A target added to the Makefile without being
    classified turns THIS test red - it is what makes it impossible for a capability to be
    offered without saying what it buys.

    TODO(public-mirror): needs human review - this WILL turn red against this export's own
    Makefile, which drops six targets (bilan, tick, reprise, signaler, signalements,
    signalement-traite) that ARSENAL still classifies (see the matching TODO next to `ARSENAL`
    in system/lib/mnemosyne/production/arsenal.py). Left unchanged rather than silenced: a
    human should decide whether to trim the catalogue or accept this as a known, out-of-scope
    failure for the public copy."""
    v = verdict(cibles_documentees(_MAKEFILE.read_text(encoding="utf-8")), ARSENAL)
    assert v.sain, rendre_le_verdict(v)


def test_chaque_rayon_declare_porte_au_moins_une_arme() -> None:
    """An empty rayon in the real table is dead furniture: it costs a line on every read."""
    porteurs = {a.rayon for a in ARSENAL}
    assert [cle for cle, _ in RAYONS if cle not in porteurs] == []


def test_la_page_est_plus_courte_que_le_mur_qu_elle_remplace() -> None:
    """BOTH SIDES ARE MEASURED NOW, no figure is recopied from a past session: a borrowed
    verdict goes stale in silence."""
    docstrings = re.findall(
        r"^[a-zA-Z0-9_-]+:.*?## (.*)$", _MAKEFILE.read_text(encoding="utf-8"), re.M
    )
    mur = sum(len(d) for d in docstrings)
    assert len(rendre(ARSENAL)) < mur


def test_aucune_arme_ne_se_presente_comme_une_obligation() -> None:
    """WHAT WILL NEVER BECOME AN OBLIGATION (B1). An arsenal is not an absence of laws - but a
    hard rule filed among the optional things WOULD become optional, and the reverse is worse: a
    weapon phrased as a duty rebuilds the conscription this track is dismantling.

    THE POPULATION IS THE WEAPONS' OWN TEXT, NOT THE PAGE. A first draft read the whole page
    and accused its own header - the one that says "nothing here is mandatory". A TEXT detector
    counts citations as instances; so it is given the fields, not the prose."""
    devoirs = ("you must", "you need to", "is a fault", "mandatory", "forbidden to")
    coupables = [
        (a.cible, mot)
        for a in ARSENAL
        for mot in devoirs
        if mot in f"{a.achat} {a.pourquoi_ici}".lower()
    ]
    assert coupables == []


def test_la_page_dit_en_tete_que_les_regles_dures_n_y_sont_pas() -> None:
    """The POSITIVE counterpart of the previous test: without this sentence, a reader could
    believe this catalogue is the whole of what Mnemosyne expects from them."""
    entete = rendre(ARSENAL).split("## ")[0].lower()
    assert "nothing here is mandatory" in entete
    assert "hard rules" in entete


def _lancer(cwd: Path, **env: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "mnemosyne.runtime.arsenal_run"],
        capture_output=True,
        text=True,
        cwd=cwd,
        env={**os.environ, "PYTHONPATH": str(_RACINE / "system" / "lib"), **env},
    )


# NOTE (public-mirror): the subprocess tests below assert on literal strings that
# `mnemosyne.runtime.arsenal_run` (NOT in this file's own sanitization batch) prints to
# stdout/stderr. `arsenal_run` has since been translated, so those assertions were realigned
# onto the strings it really prints ("unreadable plan gate", "the Makefile is unreadable",
# "This plan declares nothing", "no documented target"). ONE is deliberately NOT realigned:
# "Bijection VERIFIEE" in `test_la_surface_sur_le_vrai_depot_sort_zero`, whose own TODO marks
# it as failing for a scope reason first - it prints "Bijection VERIFIED" today.


# ── B4: a project's plan DECLARES what it takes - and declaring nothing is valid ──────────────


def test_une_porte_neuve_ne_declare_RIEN() -> None:
    """THE FIRST-RUN BUG, FROZEN HERE. The generated door CITES a target as an example in its
    help comment; the first parser used to render ``('verbatim-check',)`` for a door nobody had
    filled in yet. A TEXT detector counts citations as instances - comments are therefore
    stripped before reading, instead of hoping nobody ever writes one."""
    porte = door_skeleton("Demo", "a cap", (("plan/socle.md", "Socle"),))
    assert f"## {TITRE_DECLARATION}" in porte
    assert "make verbatim-check" in porte, (
        "the example must really be present, or this test checks nothing"
    )
    assert lire_la_declaration(porte) == ()


def test_une_porte_sans_la_section_ne_declare_rien() -> None:
    assert lire_la_declaration("# PLAN\n\n## Les arcs\n\n- `plan/a.md` - A\n") == ()


def test_les_lignes_collees_depuis_l_arsenal_sont_lues_telles_quelles() -> None:
    """A project PASTES lines from `make arsenal`; hand-recopying them drifts (D170)."""
    ligne = next(x for x in rendre(ARSENAL).splitlines() if x.startswith("- `make verbatim-check`"))
    porte = f"# PLAN\n\n## {TITRE_DECLARATION}\n\n{ligne}\n"
    assert lire_la_declaration(porte) == ("verbatim-check",)


def test_la_declaration_s_arrete_a_la_section_suivante() -> None:
    porte = (
        f"# PLAN\n\n## {TITRE_DECLARATION}\n\n- `make judge` x\n\n"
        "## Les arcs\n\n- `make elsewhere` not a declaration\n"
    )
    assert lire_la_declaration(porte) == ("judge",)


def test_les_armes_retenues_suivent_l_ordre_du_catalogue_pas_de_la_declaration() -> None:
    retenues, inconnues = armes_declarees(("rangement", "describe"), ARSENAL)
    assert [a.cible for a in retenues] == ["describe", "rangement"]
    assert inconnues == ()


def test_une_declaration_qui_ne_designe_rien_est_nommee() -> None:
    retenues, inconnues = armes_declarees(("judge", "nonsense"), ARSENAL)
    assert [a.cible for a in retenues] == ["judge"]
    assert inconnues == ("nonsense",)


def test_ne_rien_declarer_n_est_pas_un_refus(tmp_path: Path) -> None:
    """B4 IS AN OFFER, NOT A FORM. A project that declares nothing must exit ZERO."""
    porte = tmp_path / "PLAN.md"
    porte.write_text("# PLAN\n\n## Les arcs\n\n- `plan/a.md` - A\n", encoding="utf-8")
    fait = _lancer(_RACINE, CLAUDE_PROJECT_DIR=str(_RACINE), POUR=str(porte))
    assert fait.returncode == 0, fait.stdout + fait.stderr
    assert "This plan declares nothing" in fait.stdout


def test_une_declaration_fautive_fait_sortir_un(tmp_path: Path) -> None:
    porte = tmp_path / "PLAN.md"
    porte.write_text(f"# PLAN\n\n## {TITRE_DECLARATION}\n\n- `make judged` x\n", encoding="utf-8")
    fait = _lancer(_RACINE, CLAUDE_PROJECT_DIR=str(_RACINE), POUR=str(porte))
    assert fait.returncode == 1
    assert "judged" in fait.stdout


def test_pour_ne_rend_que_les_armes_declarees(tmp_path: Path) -> None:
    porte = tmp_path / "PLAN.md"
    porte.write_text(f"# PLAN\n\n## {TITRE_DECLARATION}\n\n- `make judge` x\n", encoding="utf-8")
    fait = _lancer(_RACINE, CLAUDE_PROJECT_DIR=str(_RACINE), POUR=str(porte))
    assert fait.returncode == 0, fait.stdout + fait.stderr
    assert fait.stdout.count("- `make ") == 1
    assert "- `make judge`" in fait.stdout


def test_une_porte_illisible_refuse_au_lieu_de_rendre_une_page_vide(tmp_path: Path) -> None:
    fait = _lancer(_RACINE, CLAUDE_PROJECT_DIR=str(_RACINE), POUR=str(tmp_path / "absent.md"))
    assert fait.returncode == 2
    assert "unreadable plan gate" in fait.stderr


def test_C8_une_variable_VOISINE_MECONNUE_est_REFUSEE_au_lieu_de_retomber_en_silence(
    tmp_path: Path,
) -> None:
    """C8: `CHEMIN=` instead of `POUR=` used to silently fall back to the general offer, without
    a word about the ignored variable. `CHEMIN=`, not `RACINE=`: the first version of this test
    used a name absent from the real Makefile, found by an isolated audit -- fixed along with the
    code, not worked around."""
    fait = _lancer(_RACINE, CLAUDE_PROJECT_DIR=str(_RACINE), CHEMIN=str(tmp_path))
    assert fait.returncode == 2
    assert "CHEMIN=" in fait.stderr and "POUR=" in fait.stderr, fait.stderr


# ── B1: the doctrine OFFERS instead of commanding - and what these tests do NOT hold ──────────


def test_claude_md_porte_l_adresse_de_l_arsenal() -> None:
    """WITHOUT THIS LINE, THE OFFER DOES NOT EXIST. `CLAUDE.md` is the one text an agent reads
    without being asked; the arsenal is only reached through it. The repo's own rule applied to
    itself: *a document nothing points to does not exist*."""
    assert "make arsenal" in (_RACINE / "CLAUDE.md").read_text(encoding="utf-8")


def test_la_phrase_qui_commandait_ne_peut_pas_revenir() -> None:
    """THIS TEST CLOSES ONE CASE, NOT THE CLASS - and that has to be said.

    It freezes THE sentence that track 1 came to remove (*"Reinventing an existing capability is
    a fault, not an initiative"*), measured present in `CLAUDE.md` on 2026-08-09. It stops that
    ONE sentence from coming back, nothing more: someone could write a NEW obligation tomorrow,
    phrased differently, and this test would stay green. No barrier in this repo holds "the tone
    of a doctrine" - a text detector wide enough to catch that would also accuse the sentences
    that CITE the rule to explain it (measured right here: an early version of this test accused
    the arsenal's own header, which says "nothing here is mandatory"). The admission is the
    honest answer."""
    claude = (_RACINE / "CLAUDE.md").read_text(encoding="utf-8")
    # SAME LIMIT, DECLARED: the original asserted the absence of one exact FRENCH
    # sentence from CLAUDE.md. This distribution's CLAUDE.md is English, so the sentence is
    # unreachable by any path and the assertion measured nothing -- it would have stayed green with
    # the commanding tone fully restored, in English. The sentence is abrogated on both sides and
    # has no English rendering here to point at, so the guard is removed and its absence is stated.
    # The docstring above already admits the deeper truth: no barrier in this repo holds "the tone
    # of a doctrine", and a detector wide enough to catch it would accuse the sentences that quote
    # the rule in order to explain it.
    assert claude, "CLAUDE.md must at least be readable for any claim about it to mean anything"


def test_les_regles_dures_restent_dans_claude_md_et_pas_dans_l_arsenal() -> None:
    """THE ARSENAL MAKES THE TOOLING OPTIONAL, NEVER THE SAFETY. The six hard rules must stay
    where they are read without being asked - moving them to a page opened by choice would make
    them optional by construction.

    TODO(public-mirror): needs human review - this test's premise (that these six French phrases
    live verbatim in `CLAUDE.md`) holds for the PRIVATE repo's own doctrine file, not for this
    public mirror's independent, hand-authored, English `CLAUDE.md` (see the "Never touched by
    this sync" list in the sync contract). Left unchanged rather than guessed at: mapping each
    French hard rule onto whatever the export's generic template says is a product decision, not
    a translation one."""
    claude = (_RACINE / "CLAUDE.md").read_text(encoding="utf-8")
    for regle in (
        "Sensible-local",
        "Tout passe par le Garde",
        "Un mur se DÉCLARE, jamais ne se contourne",
        "Non-destructif",
        "Cloisonnement",
        "Producteur ≠ vérificateur",
    ):
        assert regle in claude, f"hard rule vanished from CLAUDE.md: {regle}"


# ── The surface: the offer always prints, a refusal names its cause ───────────────────────────


def test_la_surface_sur_le_vrai_depot_sort_zero() -> None:
    """TODO(public-mirror): needs human review - depends on the real bijection (see
    `test_le_vrai_makefile_et_la_vraie_table_se_recouvrent` above), so it is expected to fail
    against this export's own Makefile for the same, already-flagged reason."""
    fait = _lancer(_RACINE, CLAUDE_PROJECT_DIR=str(_RACINE))
    assert fait.returncode == 0, fait.stdout + fait.stderr
    assert "Bijection VERIFIEE" in fait.stdout


def test_un_makefile_absent_refuse_au_lieu_de_rendre_une_page_vide(tmp_path: Path) -> None:
    fait = _lancer(tmp_path, CLAUDE_PROJECT_DIR=str(tmp_path))
    assert fait.returncode == 2
    assert "the Makefile is unreadable" in fait.stderr
    assert "The arsenal" not in fait.stdout


def test_un_makefile_sans_cible_documentee_refuse(tmp_path: Path) -> None:
    """ZERO TARGETS IS NOT ZERO PROBLEM: with no population, the bijection asserts nothing."""
    (tmp_path / "Makefile").write_text("internal:\n\techo nothing\n", encoding="utf-8")
    fait = _lancer(tmp_path, CLAUDE_PROJECT_DIR=str(tmp_path))
    assert fait.returncode == 2
    assert "no documented target" in fait.stderr


def test_une_cible_neuve_non_classee_casse_la_surface_mais_l_offre_s_imprime(
    tmp_path: Path,
) -> None:
    """The page stays READABLE when the bijection breaks: a classification gap does not deprive
    anyone of the arsenal. The offer first, the gaps after, the exit code last."""
    (tmp_path / "Makefile").write_text(
        _MAKEFILE.read_text(encoding="utf-8")
        + "\ntarget-never-classified: ## a new weapon\n\ttrue\n",
        encoding="utf-8",
    )
    fait = _lancer(tmp_path, CLAUDE_PROJECT_DIR=str(tmp_path))
    assert fait.returncode == 1
    assert "The arsenal" in fait.stdout
    assert "target-never-classified" in fait.stdout
    assert "non_classees" in fait.stdout


def test_le_detail_s_allume_par_la_variable_d_environnement() -> None:
    sans = _lancer(_RACINE, CLAUDE_PROJECT_DIR=str(_RACINE))
    avec = _lancer(_RACINE, CLAUDE_PROJECT_DIR=str(_RACINE), DETAIL="1")
    assert len(avec.stdout) > len(sans.stdout)
    assert "↳" in avec.stdout and "↳" not in sans.stdout
