"""Witnesses for ``P4`` — the ceiling AS A GATE, and the NON-DESTRUCTIVE rotation it forces.

The contract's **five** surfaces: the judge, the **return code**
(:func:`~mnemosyne.runtime.plafond_rotation_run.juger` and ``main``), the **published text**, the
**production values** (the real ceiling weighed against the files actually tracked by git), and the
**passing case**.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from mnemosyne.production.plafond_rotation import (
    COUPE_SANS_ARCHIVE,
    DOSSIER_ARCHIVE,
    NOMS_COUVERTS,
    PLAFOND_DEPASSE,
    PLAFOND_LIGNES,
    POPULATION_VIDE,
    TOLERANCE_COUPE_LIGNES,
    Fichier,
    archive_proposee,
    chemins_refuses,
    est_couvert,
    resume,
    verdict,
)
from mnemosyne.runtime import plafond_rotation_run as bord

RACINE = Path(__file__).resolve().parents[2]
JOUR = "2026-09-08"

# TODO(public-mirror): needs human review -- the `docs/postes/...` paths used throughout this file
# are not a free choice of this test suite: `PREFIXE_COUVERT = "docs/postes/"` and
# `DOSSIER_ARCHIVE = "docs/postes/archive/"` are hardcoded in the (out-of-scope)
# `plafond_rotation.py` production module, and `est_couvert()` matches on that exact prefix -- a
# fixture path not starting with it would silently test nothing (every witness would see an
# UNCOVERED file rather than the ceiling/rotation logic this file exists to prove). Left unchanged
# for that reason. `docs/postes/` is this repository's own real per-seat journal directory, not
# something this public mirror ships.


def _f(chemin="docs/postes/journal-chat-1.md", lignes=10, avant=None, archivees=0) -> Fichier:
    return Fichier(chemin=chemin, lignes=lignes, lignes_avant=avant, lignes_archivees=archivees)


# ── surface 1: THE JUDGE ───────────────────────────────────────────────────────────────────────


def test_le_perimetre_est_une_question_de_FORME_pas_une_table_de_chemins():
    """``journal-chat-4.md`` is born covered: a list of files always forgets one more file."""
    assert est_couvert("docs/postes/journal-chat-1.md")
    assert est_couvert("docs/postes/journal-chat-4.md")
    assert est_couvert("docs/postes/journal-chat-17.md")
    assert est_couvert("docs/postes/OBSERVATIONS.md")


def test_une_ARCHIVE_n_est_JAMAIS_couverte_sinon_la_rotation_se_refuserait_elle_meme():
    """ An archive's base name MATCHES the pattern: only the ``DOSSIER_ARCHIVE`` clause saves it.

 A saboteur who removes this clause makes the archive produced by :func:`archive_proposee`
 covered again — and rotation becomes impossible: archiving would trigger the very refusal
 archiving was meant to lift.
 """
    produite = archive_proposee("docs/postes/journal-chat-1.md", JOUR)
    assert produite.rsplit("/", 1)[-1].startswith("journal-chat-"), (
        "the fixture must MATCH the pattern"
    )
    assert not est_couvert(produite)
    assert not est_couvert("docs/postes/archive/OBSERVATIONS.md")
    assert not est_couvert("docs/postes/archive/n-importe-quoi.md")


def test_un_journal_NICHE_est_couvert_a_toute_PROFONDEUR():
    """A list of locations always forgets one more location."""
    assert est_couvert("docs/postes/2026/journal-chat-9.md")
    assert est_couvert("docs/postes/vieux/OBSERVATIONS.md")


def test_les_chemins_HORS_perimetre_declares_dans_l_en_tete_sont_bien_HORS():
    """The refused scope is also a deliverable: it is pinned down, or it drifts silently."""
    for hors in (
        "README.md",
        "docs/other-document.md",
        "docs/nested/other-document.md",
        "CLAUDE.md",
        "docs/postes/README.md",
        "docs/postes/chat-1.md",
    ):
        assert not est_couvert(hors), f"{hors} must NOT be covered"


def test_au_dessus_du_plafond_le_refus_NOMME_l_archive_a_creer():
    refus = verdict((_f(lignes=PLAFOND_LIGNES + 1),), jour=JOUR)
    assert [r.genre for r in refus] == [PLAFOND_DEPASSE]
    assert refus[0].archive_proposee == "docs/postes/archive/journal-chat-1-2026-09-08.md"


def test_la_borne_est_STRICTE_EXACTEMENT_au_plafond_passe():
    """An inequality rule only bounds one side: we pin down which."""
    assert verdict((_f(lignes=PLAFOND_LIGNES),), jour=JOUR) == ()
    assert verdict((_f(lignes=PLAFOND_LIGNES + 1),), jour=JOUR) != ()


def test_COUPER_sans_archiver_est_REFUSE_c_est_la_moitie_qui_compte():
    """ A ceiling ALONE would teach the wrong way out: cutting the start of the file."""
    coupe = _f(lignes=100, avant=5000, archivees=0)
    assert [r.genre for r in verdict((coupe,), jour=JOUR)] == [COUPE_SANS_ARCHIVE]


def test_TOURNER_LA_PAGE_passe_les_lignes_retirees_atterrissent_dans_l_archive():
    """The legitimate way out: what leaves the journal is found again, character for character,
    in the archive."""
    rotation = _f(lignes=100, avant=5000, archivees=4900)
    assert verdict((rotation,), jour=JOUR) == ()


def test_une_archive_INCOMPLETE_reste_refusee():
    """4899 for 4900 removed: one line is missing, so one line was DESTROYED."""
    assert [r.genre for r in verdict((_f(lignes=100, avant=5000, archivees=4899),), jour=JOUR)] == [
        COUPE_SANS_ARCHIVE
    ]


def test_une_petite_correction_sous_la_TOLERANCE_ne_declenche_pas_la_clause_de_coupe():
    """Derived from the population: 818 of 828 commits delete NOTHING, the worst case is 4 lines."""
    assert (
        verdict((_f(lignes=1000, avant=1000 + TOLERANCE_COUPE_LIGNES, archivees=0),), jour=JOUR)
        == ()
    )
    assert (
        verdict((_f(lignes=1000, avant=1000 + TOLERANCE_COUPE_LIGNES + 1, archivees=0),), jour=JOUR)
        != ()
    )


def test_un_fichier_qui_NAIT_n_a_rien_perdu():
    """``lignes_avant=None`` is not ``0`` — confusing them would fabricate a false cut on every
    creation."""
    assert verdict((_f(lignes=10, avant=None),), jour=JOUR) == ()


def test_les_DEUX_clauses_peuvent_tomber_ENSEMBLE_aucun_retour_anticipe():
    """A check placed first adds a cause, it never removes one."""
    gros = _f(chemin="docs/postes/journal-chat-2.md", lignes=PLAFOND_LIGNES + 1)
    coupe = _f(chemin="docs/postes/journal-chat-1.md", lignes=10, avant=5000, archivees=0)
    genres = [r.genre for r in verdict((gros, coupe), jour=JOUR)]
    assert set(genres) == {PLAFOND_DEPASSE, COUPE_SANS_ARCHIVE}


def test_une_POPULATION_VIDE_n_est_JAMAIS_un_vert():
    assert [r.genre for r in verdict((), jour=JOUR)] == [POPULATION_VIDE]
    assert [r.genre for r in verdict((_f(chemin="README.md", lignes=99999),), jour=JOUR)] == [
        POPULATION_VIDE
    ]


def test_le_gel_porte_sur_l_ENSEMBLE_des_chemins_car_un_ECHANGE_laisse_le_COMPTE_identique():
    a = (
        _f(chemin="docs/postes/journal-chat-1.md", lignes=PLAFOND_LIGNES + 1),
        _f(chemin="docs/postes/journal-chat-2.md", lignes=10),
    )
    b = (
        _f(chemin="docs/postes/journal-chat-1.md", lignes=10),
        _f(chemin="docs/postes/journal-chat-2.md", lignes=PLAFOND_LIGNES + 1),
    )
    assert len(verdict(a, jour=JOUR)) == len(verdict(b, jour=JOUR)) == 1
    assert chemins_refuses(verdict(a, jour=JOUR)) != chemins_refuses(verdict(b, jour=JOUR))


def test_le_JOUR_est_injecte_le_juge_ne_lit_aucune_horloge():
    assert archive_proposee("docs/postes/OBSERVATIONS.md", "1999-01-01").endswith(
        "OBSERVATIONS-1999-01-01.md"
    )


# ── surface 2: THE RETURN CODE / THE DECISION ───────────────────────────────────────────────────


def test_rc_0_sous_le_plafond():
    code, _ = bord.juger((_f(lignes=10),), jour=JOUR)
    assert code == 0


def test_rc_1_au_dessus_du_plafond():
    code, _ = bord.juger((_f(lignes=PLAFOND_LIGNES + 1),), jour=JOUR)
    assert code == 1


def test_rc_2_sur_une_population_VIDE_et_le_2_ne_s_ECRASE_PAS_sur_le_1():
    code, _ = bord.juger((), jour=JOUR)
    assert code == 2


def test_main_en_mode_PORTE_sort_0_a_VIDE_sans_appeler_git_une_fois_de_plus():
    """Zero cost when empty: a gate slower than the wall is never taken."""
    appels = []

    def git(args):
        appels.append(list(args))
        return 0, "docs/PLAN.md\nCLAUDE.md\n"

    assert bord.main(["--mis-en-scene"], git=git, jour=JOUR) == 0
    assert appels == [["diff", "--cached", "--name-only", "--no-renames"]]


def test_main_en_mode_PORTE_refuse_un_journal_trop_gros_mis_en_scene():
    trop = "\n".join(str(i) for i in range(PLAFOND_LIGNES + 5))

    def git(args):
        if args[0] == "diff" and "--name-only" in args:
            return 0, "docs/postes/journal-chat-1.md\n"
        if args[0] == "diff":  # numstat on the archive
            return 0, ""
        if args[0] == "show" and args[1].startswith(":"):
            return 0, trop
        if args[0] == "show":  # HEAD
            return 0, trop
        return 0, ""

    assert bord.main(["--mis-en-scene"], git=git, jour=JOUR) == 1


def test_main_en_mode_DEPOT_sort_2_quand_les_fichiers_couverts_ONT_DISPARU():
    """ This is THE case ``POPULATION_VIDE`` guards against: the commit gate gone blind in
 silence."""
    assert bord.main([], git=lambda a: (0, "docs/postes/README.md\n"), jour=JOUR) == 2


def _git_rotation(indexees: int, dans_head: int, archivees: int):
    """A fake git that replays a rotation: the journal shrinks, the archive gains ``archivees``
    lines."""

    def git(args):
        if args[0] == "diff" and "--name-only" in args:
            return 0, "docs/postes/journal-chat-1.md\n"
        if args[0] == "diff":  # numstat on docs/postes/archive/
            return 0, f"{archivees}\t0\tdocs/postes/archive/journal-chat-1-2026-09-08.md\n"
        if args[0] == "show" and args[1].startswith(":"):
            return 0, "x\n" * indexees
        if args[0] == "show":  # HEAD
            return 0, "x\n" * dans_head
        return 0, ""

    return git


def test_le_BORD_lit_les_lignes_ARCHIVEES_et_laisse_passer_une_vraie_rotation():
    """ If the edge stopped summing the archives' numstat, every rotation would be refused —
 and the only non-destructive way out would become impossible."""
    assert bord.main(["--mis-en-scene"], git=_git_rotation(100, 5000, 4900), jour=JOUR) == 0


def test_le_BORD_refuse_la_MEME_coupe_quand_l_archive_ne_recueille_RIEN():
    """Same population, a single difference: the archive is empty. This is the differentiation."""
    assert bord.main(["--mis-en-scene"], git=_git_rotation(100, 5000, 0), jour=JOUR) == 1


def test_le_BORD_en_mode_DEPOT_sort_2_quand_git_ne_peut_LIRE_aucun_journal():
    """ ``None`` is not ``0`` at the edge either.

 The journals are indeed tracked, but ``git show HEAD:`` fails (repo with no commit, missing
 object). Counting ``0`` lines would make them look like "four files, all tiny, all fine": the
 gate would return GREEN over a population it could not actually read.
 """

    def git(args):
        if args[0] == "ls-files":
            return 0, "docs/postes/journal-chat-1.md\ndocs/postes/OBSERVATIONS.md\n"
        return 128, ""

    assert bord.main([], git=git, jour=JOUR) == 2


def test_le_BORD_en_mode_DEPOT_n_INTERROGE_PAS_git_sur_les_chemins_HORS_perimetre():
    """The edge's filter is a COST filter: a gate slower than the wall is never taken.

    The judge re-filters anyway — so without this witness, removing the edge's filter would not
    redden anywhere, and the gate would pay for one ``git show`` per file under ``docs/postes/``.
    """
    interroges = []

    def git(args):
        if args[0] == "ls-files":
            return (
                0,
                "docs/postes/README.md\ndocs/postes/chat-1.md\ndocs/postes/journal-chat-1.md\n",
            )
        if args[0] == "show":
            interroges.append(args[1])
        return 0, "x\n" * 10

    bord.main([], git=git, jour=JOUR)
    assert interroges == ["HEAD:docs/postes/journal-chat-1.md"]


def test_le_BORD_ignore_un_chemin_SUPPRIME_de_l_index_au_lieu_de_planter():
    def git(args):
        if args[0] == "diff" and "--name-only" in args:
            return 0, "docs/postes/journal-chat-1.md\ndocs/postes/OBSERVATIONS.md\n"
        if args[0] == "diff":
            return 0, ""
        if args[0] == "show" and "journal-chat-1" in args[1]:
            return 128, ""  # no longer in the index: deleted in this commit
        return 0, "x\n" * 10

    assert bord.main(["--mis-en-scene"], git=git, jour=JOUR) == 0


# ── surface 3: THE PUBLISHED TEXT ───────────────────────────────────────────────────────────────


def test_le_texte_du_depassement_dit_TOURNE_LA_PAGE_et_JAMAIS_efface():
    texte = resume(
        (_f(lignes=PLAFOND_LIGNES + 1),), verdict((_f(lignes=PLAFOND_LIGNES + 1),), jour=JOUR)
    )
    assert "TURN THE PAGE" in texte
    assert "never erase" in texte
    assert "docs/postes/archive/journal-chat-1-2026-09-08.md" in texte


def test_le_texte_de_la_coupe_dit_qu_une_rotation_DEPLACE_et_ne_coupe_pas():
    coupe = (_f(lignes=100, avant=5000, archivees=0),)
    texte = resume(coupe, verdict(coupe, jour=JOUR))
    assert "A rotation MOVES, it does not cut" in texte
    assert DOSSIER_ARCHIVE in texte


def test_le_texte_d_une_population_vide_NOMME_le_perimetre_couvert():
    texte = resume((), verdict((), jour=JOUR))
    assert "INSTRUMENT FAILURE" in texte
    assert "docs/postes/" in texte
    assert "would pass GREEN without having looked at anything" in texte


def test_le_texte_vert_publie_le_plafond_ET_les_tailles():
    texte = resume((_f(lignes=42),), ())
    assert f"ceiling {PLAFOND_LIGNES} lines" in texte
    assert "journal-chat-1.md 42 ln." in texte
    assert "OK" in texte


# ── surface 4: THE PRODUCTION VALUES ────────────────────────────────────────────────────────────


def test_les_valeurs_de_production_sont_celles_qui_ont_ete_DERIVEES():
    assert PLAFOND_LIGNES == 2000
    assert TOLERANCE_COUPE_LIGNES == 10
    assert NOMS_COUVERTS == ("journal-chat-", "OBSERVATIONS.md")
    assert DOSSIER_ARCHIVE == "docs/postes/archive/"


def test_le_perimetre_REEL_attrape_les_fichiers_REELLEMENT_suivis_par_git():
    """ Injecting everywhere would leave the real value untested. Here, the population is the
 repo itself.

 This witness turns red the day the journals get renamed — i.e. the day the gate would go
 blind without anything saying so.
 """
    suivis = subprocess.run(
        ["git", "ls-files", "--", "docs/postes"], cwd=RACINE, capture_output=True, text=True
    ).stdout.splitlines()
    assert suivis, "instrument failure: git returned no file under docs/postes"
    couverts = {c for c in suivis if est_couvert(c)}
    assert couverts >= {
        "docs/postes/journal-chat-1.md",
        "docs/postes/journal-chat-2.md",
        "docs/postes/journal-chat-3.md",
        "docs/postes/OBSERVATIONS.md",
    }
    assert not any(c.startswith(DOSSIER_ARCHIVE) for c in couverts)


def test_le_plafond_REEL_REFUSE_les_journaux_REELS_d_aujourd_hui():
    """The measurement that opened the item: 6,038 to 7,199 lines, i.e. ×3 to ×3.6 the ceiling.

    Without a ceiling, the re-reading that ``docs/postes/README.md:59`` REQUIRES is impossible —
    and it silently became exactly that, within four days.
    """
    reels = []
    for chemin in (
        "docs/postes/journal-chat-1.md",
        "docs/postes/journal-chat-2.md",
        "docs/postes/journal-chat-3.md",
        "docs/postes/OBSERVATIONS.md",
    ):
        fichier = RACINE / chemin
        if not fichier.is_file():  # the repo has moved on: never judge against an absent population
            continue
        reels.append(
            _f(chemin=chemin, lignes=len(fichier.read_text(encoding="utf-8").splitlines()))
        )
    assert reels, "instrument failure: no real journal read"
    refus = verdict(tuple(reels), jour=JOUR)
    assert chemins_refuses(refus) == {f.chemin for f in reels}
    assert all(f.lignes > 2 * PLAFOND_LIGNES for f in reels)


# ── surface 5: THE PASSING CASE ─────────────────────────────────────────────────────────────────


def test_LE_CAS_LEGITIME_NE_ROUGIT_PAS():
    """A journal growing normally under the ceiling, with the module's REAL values."""
    normal = (
        _f(chemin="docs/postes/journal-chat-1.md", lignes=1500, avant=1490),
        _f(chemin="docs/postes/OBSERVATIONS.md", lignes=800, avant=800),
    )
    assert verdict(normal) == ()
    code, texte = bord.juger(normal, jour=JOUR)
    assert code == 0
    assert "REFUS" not in texte
